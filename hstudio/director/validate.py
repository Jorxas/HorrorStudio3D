"""Repair an episode JSON produced by a model so that the renderer never fails:
contiguous line coverage, known values, clamped numbers, existing sets/anchors/sfx. Returns (episode, warnings)."""
import copy
from ..audio.synth import SFX
from ..engines.pixel3d.sets import EtageZero, Apartment, RoomSet, make_set, PLACE_TYPES, PROP_TYPES
from ..engines.pixel3d import world as WD, creatures as CR
from ..audio import music as MU, ambience as AMB
from ..engines.pixel3d.assets import FACE_KINDS, GAZE
from ..engines.pixel3d import poses as P
from ..acting.timeline import OFF_WORDS

PRESETS = {'closeup', 'medium', 'full', 'ots', 'pov', 'insert', 'wide', 'high_corner', 'low', 'free'}
MOVES = {'static', 'push_in', 'pull_out', 'dolly_in', 'dolly_out', 'pan_left', 'pan_right', 'tilt_up', 'tilt_down', 'crane_up',
         'crane_down', 'track_left', 'track_right', 'orbit_left', 'orbit_right', 'whip_turn', 'look_around', 'handheld', 'drift', 'pan_up', 'pan_down'}
FACES = set(FACE_KINDS)
BODY_KEYS = {'gesture': set(P.GESTURES), 'posture': set(P.POSTURES), 'hold': set(P.HOLD_ITEMS), 'gaze': set(k for k in GAZE if k),
             'outfit': set(P.OUTFITS), 'hair_style': set(P.HAIR_STYLES), 'hat': set(P.HATS)}
SCENES = {'console', 'screen', 'door', 'room', 'rule_card', 'face', 'split', 'hallway', 'window', 'black'}
# V3, CONSOLE 2D art direction (engines/console/aplat.py). Opt-in: an episode without "art" keeps the original
# look, byte for byte. An unknown value is reported rather than silently accepted, because falling back to the
# old style without saying so is exactly the kind of silent substitution the story-first rule forbids.
ARTS = {'aplat'}
ART_PALETTES = {'night', 'alert', 'game', 'dawn'}
# shared acting layer (engine_version 2 / "actions"), see acting/timeline.py and acting/cinema.py
VERBS = {'walk_to', 'run_to', 'sneak_to', 'go', 'enter', 'exit', 'turn_to', 'look_at', 'look_around', 'gesture', 'face', 'react',
         'pick', 'take', 'put', 'give', 'sit', 'stand', 'open', 'close', 'follow', 'wait'}
SHOTS = {'establishing', 'wide', 'full', 'medium_full', 'medium', 'close', 'extreme_close', 'two_shot', 'dialogue', 'group', 'ots', 'pov', 'insert'}
MOVES2 = {'static', 'dolly_in', 'dolly_out', 'push', 'follow', 'track', 'orbit', 'handheld', 'crane_up', 'crane_down'}
REACT_KINDS = {'startle', 'gasp', 'flinch', 'laugh', 'nod', 'shake_head', 'sigh', 'cheer', 'shiver'}

def known_verbs():
    """core verbs + verbs registered by acting/motion.py and extensions (the registry, not a frozen list)"""
    from ..acting.timeline import VERBS as REGISTERED
    return VERBS | set(REGISTERED)

def check_actions(s, tag, W, gestures, faces):
    acts = []; verbs = known_verbs()
    for a in s.get('actions') or []:
        if not isinstance(a, dict) or a.get('do') not in verbs: W.append(f'{tag} : action inconnue {a}'); continue
        if a['do'] == 'gesture' and a.get('name') not in gestures: W.append(f'{tag} : geste "{a.get("name")}" inconnu'); continue
        if a['do'] == 'face' and a.get('name') not in faces: W.append(f'{tag} : expression "{a.get("name")}" inconnue -> neutral'); a['name'] = 'neutral'
        if a['do'] == 'react' and a.get('kind', 'startle') not in REACT_KINDS: a['kind'] = 'startle'
        a.setdefault('who', 'hero'); acts.append(a)
    s['actions'] = acts
VOICE_FX = {'double', 'creature', 'monster', 'inscription', 'console', 'muffled', 'phone', 'radio', 'echo', 'whisper', 'none'}

def _num(v, lo, hi):
    if isinstance(v, (int, float)): return max(lo, min(hi, v))
    if isinstance(v, list) and all(isinstance(x, (int, float)) for x in v):
        if len(v) == 2: return [max(lo, min(hi, v[0])), max(lo, min(hi, v[1]))]
        if len(v) == 4: return [max(lo, min(hi, v[0])), max(lo, min(hi, v[1])), v[2], v[3]]
    return None

def validate(ep, n_lines, style):
    from ..capabilities.extensions import ensure_loaded; ensure_loaded()     # names provided by stable extensions are known
    ep = copy.deepcopy(ep) if isinstance(ep, dict) else {}
    W = []
    ep['style'] = style
    from .. import profiles; profiles.apply(ep)        # "profile": "production" : ses cles sont validees comme si elles etaient ecrites
    shots = [s for s in ep.get('shots', []) if isinstance(s, dict)]
    def first(s):
        l = s.get('lines', [0, 0])
        if isinstance(l, int): l = [l, l]
        try: return int(l[0])
        except Exception: return 0
    for s in shots:
        l = s.get('lines', [0, 0])
        if isinstance(l, int): l = [l, l]
        if not isinstance(l, list) or len(l) == 0: l = [0, 0]
        if len(l) == 1: l = [l[0], l[0]]
        s['lines'] = [max(0, min(n_lines - 1, int(l[0]))), max(0, min(n_lines - 1, int(l[-1])))]
        if s['lines'][1] < s['lines'][0]: s['lines'][1] = s['lines'][0]
    shots.sort(key=first)
    fixed = []; nxt = 0
    for s in shots:
        a, b = s['lines']
        if b < nxt: W.append(f'plan {a}-{b} en doublon supprimé'); continue
        if a != nxt:
            if a > nxt and fixed: fixed[-1]['lines'][1] = a - 1; W.append(f'trou lignes {nxt}-{a - 1} : rattachées au plan précédent')
            elif a > nxt: a = nxt
            else: a = nxt
            s['lines'][0] = a
        fixed.append(s); nxt = s['lines'][1] + 1
    if not fixed: fixed = [{'lines': [0, n_lines - 1]}]; W.append('aucun plan valide : un plan unique a été créé')
    if nxt < n_lines: fixed[-1]['lines'][1] = n_lines - 1; W.append(f'lignes {nxt}-{n_lines - 1} non couvertes : rattachées au dernier plan')
    ep['shots'] = fixed
    sets = ep.get('sets') or {}
    known_sets = {'etage_zero', 'apartment', 'pompe_station', 'hotel_nuit', 'theatre_bal'} | set(sets) | set(PLACE_TYPES)
    if ep.get('music') and ep['music'] not in MU.NAMES: W.append(f'musique "{ep["music"]}" inconnue -> horror'); ep.pop('music')
    if ep.get('ambience') and ep['ambience'] not in AMB.AMBIENCES: W.append(f'ambiance "{ep["ambience"]}" inconnue, ignorée'); ep.pop('ambience')
    if ep.get('weather') and ep['weather'] not in WD.WEATHERS + ('none',): W.append(f'météo "{ep["weather"]}" inconnue, ignorée'); ep.pop('weather')
    # "art": the two engines gave the same episode key two different meanings, and both are opt-in prototypes.
    # CONSOLE 2D wants "aplat" (+ "palette", engines/console/aplat.py); PIXEL 3D wants one of the presets of
    # engines/pixel3d/art.py, as a name or as {"style": name, ...}. Left as two separate blocks, whichever one
    # ran first would strip the other engine's value and call it unknown -- and from the episode author's side
    # that is silent. Hence ONE block that dispatches on the style: each engine judges only its own values, and
    # a value meant for the other engine is refused out loud, naming both engines. See
    # docs/RAPPORT_INTEGRATION_ART_OPTIN_20261024.md; tools/check_art_optin.py fails if this is flattened back.
    if 'art' in ep and not ep['art']:
        ep.pop('art')                        # "art": null / false / "" = the original look, in both engines
    elif ep.get('art') is not None:
        av = ep['art']
        nm = av if isinstance(av, str) else (av.get('style') or av.get('preset') if isinstance(av, dict) else None)
        if style == 'pixel3d':
            from ..engines.pixel3d.art import PRESETS as ART_PRESETS
            if nm not in ART_PRESETS:
                hint = " (c'est la direction artistique du moteur console)" if nm in ARTS else ''
                W.append(f'direction artistique "{nm}" inconnue en pixel3d{hint}, ignorée (ancien rendu conservé)')
                ep.pop('art')
        elif not (isinstance(av, str) and av in ARTS):
            from ..engines.pixel3d.art import PRESETS as ART_PRESETS
            hint = " (c'est une direction artistique du moteur pixel3d)" if nm in ART_PRESETS else ''
            W.append(f'direction artistique "{nm}" inconnue en console{hint}, ignorée -> style d\'origine')
            ep.pop('art')
    # "body": the refit of the PIXEL 3D body proportions (engines/pixel3d/bodies.py), opt-in exactly like "art".
    # Same discipline as the block above: the key is judged by the engine it belongs to, a value meant for the
    # other engine is refused out loud, and an unknown value never activates anything. CONSOLE 2D draws flat
    # shapes from the same skeleton joints and has no voxel volumes to refit, so it refuses the key by saying so.
    if 'body' in ep and not ep['body']:
        ep.pop('body')                       # "body": null / false / "" = le corps d'origine, comme "art"
    elif ep.get('body') is not None:
        bv = ep['body']
        bn = bv if isinstance(bv, str) else ((bv.get('style') or bv.get('preset')) if isinstance(bv, dict) else None)
        from ..engines.pixel3d.bodies import PRESETS as BODY_PRESETS
        if style != 'pixel3d':
            W.append(f'proportions de corps "{bn}" : refonte du moteur pixel3d, le moteur console dessine des '
                     f'aplats depuis le même squelette, ignorée (ancien rendu conservé)')
            ep.pop('body')
        elif bn not in BODY_PRESETS:
            W.append(f'proportions de corps "{bn}" inconnues, ignorées (ancien rendu conservé) ; connues : '
                     + ', '.join(sorted(BODY_PRESETS)))
            ep.pop('body')
    # "eye_aim": the pupils carry the part of the aim the neck could not (engines/pixel3d/eyes.py), opt-in
    # exactly like "body" above. CONSOLE 2D paints its eyes from its own expression table
    # (engines/console/expression.py, which has its own `gaze_amt`) and knows nothing of this one, so it
    # refuses the key by saying so instead of ignoring it quietly.
    if 'eye_aim' in ep and not ep['eye_aim']:
        ep.pop('eye_aim')                    # "eye_aim": null / false / "" = les pupilles d'origine
    elif ep.get('eye_aim') is not None:
        xv = ep['eye_aim']
        xn = 'aim' if xv is True else (xv if isinstance(xv, str) else
                                       ((xv.get('style') or xv.get('preset') or 'aim') if isinstance(xv, dict) else None))
        from ..engines.pixel3d.eyes import PRESETS as EYE_PRESETS
        if style != 'pixel3d':
            W.append(f'visée du regard "{xn}" : option du moteur pixel3d, le moteur console peint ses yeux '
                     f'depuis sa propre table d\'expressions, ignorée (ancien rendu conservé)')
            ep.pop('eye_aim')
        elif xn not in EYE_PRESETS:
            W.append(f'visée du regard "{xn}" inconnue, ignorée (ancien rendu conservé) ; connues : '
                     + ', '.join(sorted(EYE_PRESETS)))
            ep.pop('eye_aim')
    # "finish": la finition de l'image (engines/pixel3d/finish.py), opt-in exactement comme "art", "body" et
    # "eye_aim". Elle ne change ni la geometrie ni la mise en scene : elle decide combien de rayons le
    # lanceur tire et comment l'image arrive en 1080x1920. CONSOLE 2D ne lance aucun rayon -- il dessine des
    # aplats a la taille finale -- donc la cle y est refusee a voix haute au lieu d'etre acceptee sans effet.
    if 'finish' in ep and not ep['finish']:
        ep.pop('finish')                     # "finish": null / false / "" = l'image livree, au bit pres
    elif ep.get('finish') is not None:
        fv = ep['finish']
        fn = 'net' if fv is True else (fv if isinstance(fv, str) else
                                       ((fv.get('style') or fv.get('preset') or 'net') if isinstance(fv, dict) else None))
        from ..engines.pixel3d.finish import PRESETS as FIN_PRESETS
        if style != 'pixel3d':
            W.append(f'finition "{fn}" : option du moteur pixel3d, qui lance des rayons ; le moteur console '
                     f'dessine des aplats a la taille finale et n\'a pas de raster natif, ignorée '
                     f'(ancien rendu conservé)')
            ep.pop('finish')
        elif fn not in FIN_PRESETS:
            W.append(f'finition "{fn}" inconnue, ignorée (ancien rendu conservé) ; connues : '
                     + ', '.join(sorted(FIN_PRESETS)))
            ep.pop('finish')
    # "env": les facades des batiments (engines/pixel3d/facades.py), opt-in exactement comme "finish". Elle
    # ne change ni la mise en scene ni la geometrie : elle redessine la TEXTURE des murs. CONSOLE 2D dessine
    # des aplats et n'a pas de facade texturee, donc la cle y est refusee a voix haute.
    if 'env' in ep and not ep['env']:
        ep.pop('env')                        # "env": null / false / "" = les facades livrees, au bit pres
    elif ep.get('env') is not None:
        ev = ep['env']
        en = 'riche' if ev is True else (ev if isinstance(ev, str) else
                                         ((ev.get('style') or ev.get('preset') or 'riche') if isinstance(ev, dict) else None))
        from ..engines.pixel3d.facades import PRESETS as ENV_PRESETS
        if style != 'pixel3d':
            W.append(f'décors "{en}" : option du moteur pixel3d, qui texture les murs de ses immeubles ; '
                     f'le moteur console dessine des aplats, ignorée (ancien rendu conservé)')
            ep.pop('env')
        elif en not in ENV_PRESETS:
            W.append(f'décors "{en}" inconnus, ignorés (ancien rendu conservé) ; connus : '
                     + ', '.join(sorted(ENV_PRESETS)))
            ep.pop('env')
    # "diversite": quartiers a identite et interieurs a palette (engines/pixel3d/quartiers.py), opt-in comme "env". Elle change les LIEUX (pixel3d et voxel) ; le moteur console n'a
    # pas de lieu 3D : la cle y est refusee a voix haute. Valeur inconnue = ignoree, lieux d'avant conserves.
    if 'diversite' in ep and not ep['diversite']:
        ep.pop('diversite')                  # null / false / "" = les lieux livres, au pixel pres
    elif ep.get('diversite') is not None:
        dv = ep['diversite']
        dn = 'decors' if dv is True else (dv if isinstance(dv, str) else ((dv.get('style') or dv.get('preset') or 'decors') if isinstance(dv, dict) else None))
        from ..engines.pixel3d.quartiers import PRESETS as DIV_PRESETS
        if style == 'console':
            W.append(f'diversité "{dn}" : option des lieux 3D (pixel3d et voxel) ; le moteur console dessine une chambre fixe, ignorée (ancien rendu conservé)')
            ep.pop('diversite')
        elif dn not in DIV_PRESETS:
            W.append(f'diversité "{dn}" inconnue, ignorée (ancien rendu conservé) ; connues : ' + ', '.join(sorted(DIV_PRESETS)))
            ep.pop('diversite')
    # "objets": objets detailles (engines/pixel3d/objets.py, voxelgpu/b_objets.py), opt-in comme "diversite" (01/11/2026). Ils sont dessines par les moteurs 3D (pixel3d et voxel) ;
    # le moteur console a ses propres aplats : la cle y est refusee a voix haute. Valeur inconnue = ignoree, objets d'avant conserves.
    if 'objets' in ep and not ep['objets']:
        ep.pop('objets')                     # null / false / "" = les objets livres, au pixel pres
    elif ep.get('objets') is not None:
        ov = ep['objets']
        on_ = 'detailles' if ov is True else (ov if isinstance(ov, str) else ((ov.get('style') or ov.get('preset') or 'detailles') if isinstance(ov, dict) else None))
        from ..engines.pixel3d.objets import PRESETS as OD_PRESETS
        if style == 'console':
            W.append(f'objets "{on_}" : option des moteurs 3D (pixel3d et voxel) ; le moteur console dessine ses objets en aplats, ignorée (ancien rendu conservé)')
            ep.pop('objets')
        elif on_ not in OD_PRESETS:
            W.append(f'objets "{on_}" inconnus, ignorés (ancien rendu conservé) ; connus : ' + ', '.join(sorted(OD_PRESETS)))
            ep.pop('objets')
    # "eye_smooth": le lissage des pupilles (acting/eyeflow.py), opt-in. Il vit dans la couche de jeu, mais il
    # ne lisse QUE le résidu de visée, que seul le moteur pixel3d consomme ("eye_aim") : sur console il ne
    # changerait pas un pixel, donc la clé y est refusée à voix haute au lieu d'être acceptée sans effet.
    if 'eye_smooth' in ep and (not ep['eye_smooth']
                               or (isinstance(ep['eye_smooth'], str) and ep['eye_smooth'] in OFF_WORDS)):
        ep.pop('eye_smooth')                 # null / false / "" / "snap" = les pupilles image par image
    elif ep.get('eye_smooth') is not None:
        sv = ep['eye_smooth']
        sn = 'saccade' if sv is True else (sv if isinstance(sv, str) else
                                           ((sv.get('style') or sv.get('preset') or 'saccade') if isinstance(sv, dict) else None))
        from ..acting.eyeflow import PRESETS as FLOW_PRESETS
        if style != 'pixel3d':
            W.append(f'lissage du regard "{sn}" : il ne lisse que la visée des pupilles du moteur pixel3d, '
                     f'le moteur console peint ses yeux depuis sa propre table d\'expressions, ignoré '
                     f'(ancien rendu conservé)')
            ep.pop('eye_smooth')
        elif sn not in FLOW_PRESETS:
            W.append(f'lissage du regard "{sn}" inconnu, ignoré (ancien rendu conservé) ; connus : '
                     + ', '.join(sorted(FLOW_PRESETS)))
            ep.pop('eye_smooth')
        elif not ep.get('eye_aim'):
            W.append('lissage du regard actif sans "eye_aim" : il lisse la visée des pupilles, et sans '
                     '"eye_aim" personne ne la dessine — le rendu est inchangé')
    if style != 'pixel3d' and ep.get('palette') and ep['palette'] not in ART_PALETTES:
        W.append(f'palette "{ep["palette"]}" inconnue, ignorée -> nuit'); ep.pop('palette')
    if style == 'pixel3d':
        if ep.get('default_set') not in known_sets: ep['default_set'] = 'etage_zero'
        for name, sp in list(sets.items()):
            if not isinstance(sp, dict): sets.pop(name); W.append(f'décor {name} invalide supprimé'); continue
            sp.setdefault('type', 'room')
    anchors = {'etage_zero': set(EtageZero.anchors), 'apartment': set(Apartment.anchors)}
    for name in PLACE_TYPES:
        if name not in sets: anchors[name] = set(make_set(name, {'type': name}).anchors)
    for name, sp in sets.items():
        if sp.get('weather') and sp['weather'] not in WD.WEATHERS + ('none',): W.append(f'décor {name} : météo "{sp["weather"]}" inconnue'); sp.pop('weather')
        if sp.get('sky') and sp['sky'] not in WD.SKY_NAMES: W.append(f'décor {name} : ciel "{sp["sky"]}" inconnu -> day'); sp['sky'] = 'day'
        for p in list(sp.get('props') or []) + [p for r in (sp.get('rooms') or []) for p in (r.get('props') or [])]:
            if isinstance(p, dict) and p.get('type') not in PROP_TYPES: W.append(f'décor {name} : objet "{p.get("type")}" inconnu (cube gris)')
        try: anchors[name] = set(make_set(name, sp).anchors)
        except Exception as e: W.append(f'décor {name} : {e}'); anchors[name] = set()
    for k, s in enumerate(ep['shots']):
        tag = f'plan {k} (lignes {s["lines"][0]}-{s["lines"][1]})'
        for o in s.get('objects') or []:
            if isinstance(o,dict) and o.get('ecran')=='image' and (not o.get('image_locale') or len(str(o.get('image_sha256','')))!=64):
                W.append(f'{tag} : écran image sans chemin local ou empreinte SHA-256 valide')
            if isinstance(o, dict) and o.get('type') == 'mover' and o.get('thing') == 'prop:assemblage':
                from ..engines.pixel3d.assemblage import validate as validate_assembly
                try: validate_assembly(o)
                except ValueError as e: W.append(f'{tag} : {e}')
        if style == 'pixel3d':
            if s.get('set') and s['set'] not in known_sets: W.append(f'{tag} : décor "{s["set"]}" inconnu -> {ep["default_set"]}'); s['set'] = ep['default_set']
            setn = s.get('set', ep.get('default_set'))
            cam = s.get('camera') if isinstance(s.get('camera'), dict) else {}
            v2 = int(ep.get('engine_version', 1)) >= 2 or bool(s.get('actions'))
            if v2: check_actions(s, tag, W, set(P.GESTURES), FACES)
            if cam.get('shot') is not None and cam['shot'] not in SHOTS: W.append(f'{tag} : plan "{cam["shot"]}" inconnu -> medium'); cam['shot'] = 'medium'
            if cam.get('preset') not in PRESETS and not (v2 and (cam.get('shot') or not cam.get('preset'))): cam['preset'] = 'wide'
            if cam.get('move') and cam['move'] not in MOVES and not (v2 and cam['move'] in MOVES2): cam['move'] = 'static'
            if 'fov' in cam:
                v = _num(cam['fov'], 20, 115); cam['fov'] = v if v is not None else 70
            if 'shake' in cam:
                v = _num(cam['shake'], 0, .8); cam['shake'] = v if v is not None else 0
            if cam.get('preset') == 'free' and not cam.get('keys'): cam['preset'] = 'wide'
            if 'face_track' in cam: cam['face_track'] = bool(cam['face_track'])      # cadrage conscient du visage (option)
            if 'clear_face' in cam: cam['clear_face'] = bool(cam['clear_face'])      # cadrage degage du bras du sujet (option)
            if 'head_room' in cam and not isinstance(cam['head_room'], bool):       # tete entiere en 9:16 sur un plan d'epaule (option)
                v = _num(cam['head_room'], .2, 1.); cam['head_room'] = v if v is not None else True
            au = s.get('audio') if isinstance(s.get('audio'), dict) else None
            if au:
                if au.get('music') and au['music'] not in MU.NAMES: au.pop('music')
                if au.get('ambience') and au['ambience'] not in AMB.AMBIENCES: au.pop('ambience')
            if s.get('weather') and s['weather'] not in WD.WEATHERS + ('none',): W.append(f'{tag} : météo "{s["weather"]}" inconnue'); s.pop('weather')
            ids = set()
            acts = [a for a in (s.get('actors') or []) if isinstance(a, dict)]
            for a in acts:
                a.setdefault('id', 'hero'); ids.add(a['id'])
                if a.get('face') and a['face'] not in FACES: W.append(f'{tag} : expression "{a["face"]}" inconnue -> neutral'); a['face'] = 'neutral'
                for ch in a.get('face_changes') or []:
                    if isinstance(ch, dict) and ch.get('face') not in FACES: ch['face'] = 'neutral'
                if a.get('facing') not in (None, 'camera', 'away', '+z', '-z', '+x', '-x', 1, -1) and not (v2 and isinstance(a.get('facing'), (str, int, float))): a['facing'] = 'camera'
                for key, ok in BODY_KEYS.items():
                    if a.get(key) is not None and a[key] not in ok: W.append(f'{tag} : {key} "{a[key]}" inconnu, ignoré'); a.pop(key)
                for key in ('at', 'to'):
                    v = a.get(key)
                    if isinstance(v, str) and v not in anchors.get(setn, set()) and v.split('.')[0] not in anchors.get(setn, set()):
                        W.append(f'{tag} : repère "{v}" inconnu dans "{setn}"'); a[key] = [0, 0] if key == 'at' else None
                if a.get('to') is None: a.pop('to', None)
            s['actors'] = acts
            if cam.get('subject') and cam['subject'] not in ids and cam.get('preset') in ('closeup', 'medium', 'full', 'ots') and not v2:
                W.append(f'{tag} : sujet "{cam["subject"]}" absent du plan -> plan large'); cam['preset'] = 'wide'
            s['camera'] = cam
        else:
            sc = s.get('scene') if isinstance(s.get('scene'), dict) else {}
            if sc.get('type') not in SCENES: sc['type'] = 'door'; W.append(f'{tag} : scène inconnue -> porte')
            if sc.get('palette') and sc['palette'] not in ART_PALETTES:
                W.append(f'{tag} : palette "{sc["palette"]}" inconnue, ignorée'); sc.pop('palette')
            s['scene'] = sc
        cues = []
        for c in s.get('sfx') or []:
            if isinstance(c, str): c = {'name': c}
            if not isinstance(c, dict) or c.get('name') not in SFX: W.append(f'{tag} : bruitage inconnu {c}'); continue
            if 'gain' in c: c['gain'] = max(0., min(1.6, float(c['gain'])))
            cues.append(c)
        s['sfx'] = cues
    meta = ep.get('lines') if isinstance(ep.get('lines'), dict) else {}
    for k, m in list(meta.items()):
        if not isinstance(m, dict): meta.pop(k); continue
        if m.get('voice_fx') and m['voice_fx'] not in VOICE_FX: m['voice_fx'] = None
        try:
            if not (0 <= int(k) < n_lines): meta.pop(k)
        except ValueError: meta.pop(k)
    ep['lines'] = meta
    for cid, lk in list((ep.get('cast') or {}).items()):
        if not isinstance(lk, dict): ep['cast'][cid] = {}; continue
        kd = lk.get('kind') or lk.get('preset')
        if kd and kd not in CR.ANIMALS and kd not in CR.PRESETS and kd != 'creature': W.append(f'personnage {cid} : type "{kd}" inconnu, ignoré'); lk.pop('kind', None); lk.pop('preset', None)
        for key in ('outfit', 'hair_style', 'hat'):
            if lk.get(key) is not None and lk[key] not in BODY_KEYS[key]: W.append(f'personnage {cid} : {key} "{lk[key]}" inconnu, ignoré'); lk.pop(key)
        if lk.get('costume'):                                  # costumes XVIIIe (opt-in, engines/pixel3d/costumes.py) : un costume illisible est retiré ET dit
            from ..engines.pixel3d import costumes as COS
            n0 = len(COS.WARN)
            if COS.spec_of(lk) is None: W.append(f'personnage {cid} : costume {lk["costume"]!r} illisible, ignoré'); lk.pop('costume')
            W += [f'personnage {cid} : {m}' for m in COS.WARN[n0:]]
    ep.setdefault('hud', {})
    return ep, W
