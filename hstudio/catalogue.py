"""Catalogue du studio : tout ce que le moteur VOXEL sait peindre, avec une miniature, un nom, une licence et la ligne à copier dans un épisode.

Sources (lues en direct, jamais recopiées) :
  * décors de PIXEL 3D convertis      `b_props.catalogue()`                    -> {"type": "<nom>", "at": [x, z], "rot": 0}
  * lieux de PIXEL 3D convertis       `pixel3d.sets.PLACE_TYPES`               -> {"set": "<nom>"} (avec `sets` dans l'épisode)
  * modèles .vox importés (banques)   `voxelgpu_js/assets_vox/<banque>/`       -> {"type": "vox:<banque>/<nom>", "at": [x, z], "height": 2.0}
  * éléments ajoutés par d'autres modules : `catalogue/extra.json` (liste de fiches, miniatures dans `catalogue/thumbs/`)
Trois styles, trois jeux de miniatures (chaque fiche porte `styles` et `thumbs`) :
  * VOXEL       `thumbs/`          peintes par le moteur GPU (ce fichier)
  * PS1         `thumbs_ps1/`      peintes par PIXEL 3D, mêmes fiches que VOXEL, chacune dans son style (catalogue_ps1.py ; règle des deux versions, styles.py)
  * CONSOLE 2D  `thumbs_console/`  fiches propres à ce style : scènes, écrans, palettes, visages, personnages, interface (catalogue_console.py)
Les miniatures sont peintes une seule fois : `python -m hstudio.catalogue build [voxel] [ps1] [console] [decor lieu …] [force]` ne fait que ce qui manque.
Chaque fiche porte sa licence ; `commercial_ok` / `credit_required` viennent du `CREDITS.json` de la banque (voir tools/export_commercial.py).
"""
import json, math, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'catalogue'; THUMBS = OUT / 'thumbs'; INDEX = OUT / 'index.json'
BANK_LABEL = {'mmmm': 'Mini Mike — ville, personnages, véhicules', 'kk_halloween': 'KayKit — Halloween', 'kk_skeletons': 'KayKit — squelettes', 'kk_adventurers': 'KayKit — aventuriers',
              'kk_furniture': 'KayKit — mobilier', 'kk_dungeon': 'KayKit — donjon', 'kk_city': 'KayKit — ville', 'kk_restaurant': 'KayKit — restaurant', 'kk_space': 'KayKit — base spatiale',
              'kk_prototype': 'KayKit — prototypage', 'kk_medieval': 'KayKit — médiéval'}
MM_KIND = {'chr': 'personnages', 'alien': 'extraterrestres', 'veh': 'véhicules', 'scene': 'scènes', 'obj': 'objets', 'env': 'sols et nature', 'mob': 'animaux'}


def slug(s): return re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_')
def pretty(s): return re.sub(r'\s+', ' ', re.sub(r'[_\-]+', ' ', s)).strip()


def entries():
    """toutes les fiches (sans miniature encore) : id, catégorie, groupe, nom, licence, ligne à copier"""
    from .voxelgpu import b_props as BP, vox_import as VI
    from .engines.pixel3d import sets as S
    out = []
    for k in BP.catalogue():
        out.append(dict(id=f'decor/{k}', category='Décors', group='PIXEL 3D converti', name=pretty(k), key=k, license='PIXEL 3D (créé pour ce studio)', commercial_ok=True, credit_required=False, snippet=json.dumps({'type': 'b:' + k if k in BP.NATIVE else k, 'at': [0, 0], 'rot': 0}, ensure_ascii=False)))
    for k in S.PLACE_TYPES:
        out.append(dict(id=f'lieu/{k}', category='Lieux', group='PIXEL 3D converti', name=pretty(k), key=k, license='PIXEL 3D (créé pour ce studio)', commercial_ok=True, credit_required=False, snippet=json.dumps({'set': k, 'dur': 4}, ensure_ascii=False) + '   (+ "sets": {"%s": {"type": "%s"}} dans l\'épisode)' % (k, k)))
    for b in sorted(VI.BANKS.glob('*')):
        if not b.is_dir(): continue
        try: cr = json.loads((b / 'CREDITS.json').read_text(encoding='utf-8'))
        except (OSError, ValueError): cr = {}
        for p in sorted(b.glob('*.vox')):
            pre = p.stem.split('_')[0]; grp = BANK_LABEL.get(b.name, b.name)
            cat = 'Modèles voxel'
            if b.name == 'mmmm': cat = 'Personnages' if pre in ('chr',) else 'Animaux' if pre == 'mob' else 'Extraterrestres' if pre == 'alien' else 'Véhicules' if pre == 'veh' else 'Scènes' if pre == 'scene' else 'Objets et décors'
            elif b.name in ('kk_skeletons', 'kk_adventurers'): cat = 'Personnages'
            else: cat = 'Objets et décors'
            h = ', "height": 2.0' if cat == 'Personnages' else ''
            out.append(dict(id=f'vox/{b.name}/{p.stem}', reference=(cr.get('role') == 'reference'), category=cat, group=grp, name=pretty(re.sub(r'^(chr|obj|veh|scene|env|mob|alien)_', '', p.stem) if b.name == 'mmmm' else p.stem), key=f'{b.name}/{p.stem}',
                            license=cr.get('license', '?'), commercial_ok=bool(cr.get('commercial_ok', True)), credit_required=bool(cr.get('credit_required', False)), credit_text=cr.get('credit_text', ''), source=cr.get('source', ''),
                            snippet='{"type": "vox:%s/%s", "at": [0, 0], "rot": 0%s}' % (b.name, p.stem, h)))
    out += _char_entries()
    try:
        from .voxelgpu import b_monsters
        out += [dict(e, reference=False) for e in b_monsters.entries()]                # monstres animés dans notre rig (b_monsters.py)
    except Exception: pass
    try:
        from .voxelgpu import b_look
        out += [dict(e, reference=False) for e in b_look.entries()]                    # personnages refondus dans notre système (b_look.py) : ils sont à nous
    except Exception: pass
    try:
        from .director.validate import FACES
        out += [dict(id=f'visage/{f}', category='Visages', group='Expressions (43)', name=pretty(f), key=f, license='PIXEL 3D (créé pour ce studio)', commercial_ok=True, credit_required=False,
                     snippet='{"who": "lea", "do": "face", "name": "%s", "at": 0.3}' % f) for f in sorted(FACES)]
    except Exception: pass
    out += _sound_entries()
    try:
        from . import catalogue_sounds as CS
        out += CS.entries()                                                   # vrais sons enregistrés (library/audio_real), fiches fabriquées par catalogue_sounds.py
    except Exception: pass
    out += _craft_entries()
    try:
        from . import catalogue_console as CC
        out += CC.entries()                                                   # fiches CONSOLE 2D (hors règle des deux versions)
    except Exception: pass
    try: out += json.loads((OUT / 'extra.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): pass
    return out


CRAFT_CAT = {'decor': 'Nature et blocs', 'creature': 'Créatures', 'item': 'Objets créés ici', 'structure': 'Constructions'}


def _craft_entries():
    """éléments dessinés ici (craft.py et craft_*.py) : une fiche par recette et par variante (graine)"""
    try:
        from .voxelgpu import craft as CR
        rows = CR.catalogue()
    except Exception: return []
    out = []
    for name, group, label, kind, variants in rows:
        for v in range(max(1, variants)):
            out.append(dict(id=f'craft/{name}/{v}', category=CRAFT_CAT.get(kind, 'Objets créés ici'), group=group, name=label + (f' {v + 1}' if variants > 1 else ''), key=f'{name}:{v}',
                            license='créé pour ce studio (original)', commercial_ok=True, credit_required=False,
                            snippet='{"type": "craft:%s", "at": [0, 0], "rot": 0%s}' % (name, f', "seed": {v}' if v else '')))
    return out


def _sound_entries():
    """bruitages, ambiances et musiques synthétisés par le studio (aucun échantillon tiers) : lisibles dans la page"""
    try:
        from .audio import synth as SY, ambience as AMB, music as MU
    except Exception: return []
    L = dict(license='synthèse du studio (créée pour ce studio)', commercial_ok=True, credit_required=False)
    out = [dict(id=f'son/sfx/{k}', category='Sons', group='Bruitages', name=pretty(k), key=k, snippet='{"name": "%s", "at": 1.0, "gain": 0.8}   (dans la liste `sfx` d\'un plan)' % k, desc=str(getattr(SY, 'SFX_DESCRIPTIONS', {}).get(k, '')), **L) for k in sorted(SY.SFX)]
    out += [dict(id=f'son/amb/{k}', category='Sons', group='Ambiances', name=pretty(k), key=k, snippet='"audio": {"ambience": [{"t0": 0, "t1": 12, "name": "%s", "gain": 0.3}]}' % k, **L) for k in AMB.AMBIENCES]
    out += [dict(id=f'son/mus/{k}', category='Sons', group='Musiques', name=pretty(k), key=k, snippet='"audio": {"music": [{"t0": 0, "t1": 30, "style": "%s", "gain": 0.4}]}' % k, **L) for k in MU.STYLES]
    return out


def _sound_build(es, force, log):
    """un MP3 court et une forme d'onde (miniature) par son ; `audio` pointe le MP3"""
    import subprocess, wave
    import numpy as np
    from PIL import Image, ImageDraw
    from .audio import synth as SY, ambience as AMB, music as MU
    SY.SAMPLE_PROVIDER = None; (OUT / 'sounds').mkdir(parents=True, exist_ok=True); SR = SY.SR; n = 0
    for e in es:
        if not e['id'].startswith('son/'): continue
        e['thumb'] = f"thumbs/{slug(e['id'])}.jpg"; e['audio'] = f"sounds/{slug(e['id'])}.mp3"
        if not force and (OUT / e['thumb']).exists() and (OUT / e['audio']).exists(): continue
        try:
            kind, k = e['id'].split('/')[1:]
            if kind == 'sfx': x = np.asarray(SY.make(k, None, at=0.), np.float32)
            elif kind == 'amb': x = np.asarray(AMB.ambience(k, 4 * SR, seed=500), np.float32)[:4 * SR]
            else: x = np.asarray(MU.render(k, 8 * SR, seed=0), np.float32)[:8 * SR]
            x = x[:10 * SR]; pk = float(np.max(np.abs(x))) or 1.; x = x / pk * .9
            wp = OUT / 'sounds' / '_tmp.wav'
            with wave.open(str(wp), 'wb') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(x, -1, 1) * 32767).astype('<i2').tobytes())
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(wp), '-b:a', '96k', str(OUT / e['audio'])], check=True)
            im = Image.new('RGB', (320, 240), (24, 24, 32)); d = ImageDraw.Draw(im); m = len(x) // 320 or 1
            for i in range(320):
                seg = x[i * m:(i + 1) * m]; a = float(np.max(np.abs(seg))) if len(seg) else 0.; d.line([(i, 120 - a * 100), (i, 120 + a * 100)], fill=(214, 22, 26))
            im.save(OUT / e['thumb'], quality=80); n += 1
        except Exception as ex: log(f"  son ignoré {e['id']} : {type(ex).__name__}: {str(ex)[:80]}")
    log(f'sons : {n} fabriqués')


CHAR_CAT = {'presets': ('Personnages', 'Personnages animés (PIXEL 3D converti)'), 'outfits': ('Habits et accessoires', 'Tenues'), 'hats': ('Habits et accessoires', 'Chapeaux'),
            'hair': ('Habits et accessoires', 'Coiffures'), 'hold': ('Habits et accessoires', 'Objets en main'), 'animals': ('Animaux', 'Animaux animés (PIXEL 3D converti)')}


def _chars_mod():
    sys.path.insert(0, str(ROOT / 'tools'))
    import b_chars_sheet as CS
    return CS


def _char_entries():
    """personnages prêts, tenues, chapeaux, coiffures, objets en main, animaux : lus dans PIXEL 3D, peints par le pont `b_chars.py`"""
    try: G = _chars_mod().groups()
    except Exception: return []
    out = []
    for g, items in G.items():
        cat, grp = CHAR_CAT[g]
        for label, cast in items:
            cast = {k: v for k, v in cast.items() if v is not None}
            out.append(dict(id=f'perso/{g}/{label}', category=cat, group=grp, name=pretty(label), key=f'{g}/{label}', license='PIXEL 3D (créé pour ce studio)', commercial_ok=True, credit_required=False,
                            snippet='"casts": {"x": %s}' % json.dumps({k: v for k, v in cast.items() if k not in ('variant',) or g == 'presets'}, ensure_ascii=False)))
    return out


def _bounds(boxes):
    lo = [min(b[k] - b[s] / 2 for b in boxes) for k, s in (('x', 'w'), ('y', 'h'), ('z', 'd'))]; hi = [max(b[k] + b[s] / 2 for b in boxes) for k, s in (('x', 'w'), ('y', 'h'), ('z', 'd'))]; return lo, hi


def _contract(items, fps=24, dur=.5, bright=False):
    """un plan fixe par élément (props sur le plateau), cadré sur l'emprise de l'élément"""
    from .voxelgpu import contract as C
    n = int(math.ceil(dur * fps)); stages, t = [], 0.
    for i, (key, props, lights) in enumerate(items):
        lo, hi = _bounds(props[0]['boxes']) if props and props[0].get('boxes') else ([-.5, 0, -.5], [.5, 1, .5])
        c = [(lo[j] + hi[j]) / 2 for j in range(3)]; r = max(hi[j] - lo[j] for j in range(3)) / 2 + .1
        pos = [c[0] + r * .9, c[1] + r * .55 + .3, c[2] + r * 2.3 + .6]; look = [c[0], c[1] * .9, c[2]]
        stages.append(dict(id=f'p{i:04d}', world='plateau', t0=round(t, 4), t1=round(t + dur, 4), tail=0., dissolve=0., mood=None, look={}, camera=[[*pos, *look, 42., 0.] for _ in range(n)], actors={}, focus_actor=None,
                           props=props, lights=lights, env=dict(floor=0x8a7e6e if bright else 0x74685a, bg=0x5a6c8c if bright else 0x3a4660, ambient=2.0 if bright else 1.2, key=2.0 if bright else 1.4, fog=0.004), foley_steps={}))
        t += dur
    return dict(schema=C.SCHEMA, title='catalogue', genre='neutral', aspect='16:9', fps=fps, duration=round(t, 4), casts={}, expressions=['neutral'], actor_cols=C.ACTOR_COLS, stages=stages, fx=[], captions=[], caption_style={}, hud=None, cards=[], audio={})


def _place_contract(keys, fps=24):
    """un plan par lieu avec un personnage au point de départ, par le directeur (caméra automatique)"""
    from .voxelgpu import director, b_sets as BS
    shots = []
    for k in keys:
        bs = BS.get(k, {'type': k}); p = None
        for a in ('start', 'path.start', 'sidewalk.left', 'shore', 'center', 'center.center'):
            p = bs.world.anchor(a)
            if p: break
        if not p:
            for n, v in bs.world.a.items():
                if n.endswith('.center'): p = v; break
        if not p: x0, z0, x1, z1 = bs.world.rect; p = ((x0 + x1) / 2, (z0 + z1) / 2)
        shots.append(dict(set=k, dur=.6, camera=dict(shot='wide', on=['lea']), actors=[dict(id='lea', at=[round(p[0], 2), round(p[1], 2)], facing='+z' if not bs.indoor else '-z', face='neutral')], actions=[]))
    ep = dict(title='catalogue', genre='neutral', casts={'lea': {'preset': 'lina'}}, sets={k: {'type': k} for k in keys}, shots=shots, duration=round(.6 * len(keys), 2))
    return director.build(ep, '16:9', 24)


def _build_director(ep):
    from .voxelgpu import director
    return director.build(ep, '16:9', 24)


STYLE_FLAGS = ('voxel', 'ps1', 'console')


def thumbs_of(e):
    """{style: chemin relatif de la miniature} pour les styles dont la miniature existe sur le disque (chemin servi par /catalogue/<chemin>)"""
    from . import catalogue_ps1 as P1, catalogue_console as CC
    i = str(e['id']); out = {}
    if i.startswith('console/'): rel = CC.thumb_rel(i); return {'console': rel} if (OUT / rel).exists() else {}
    v = f"thumbs/{slug(i)}.jpg"
    if (OUT / v).exists(): out['voxel'] = v
    p = P1.thumb_rel(i)
    if (OUT / p).exists(): out['ps1'] = p
    return out


def build(only=None, force=False, batch=24, log=print):
    """peint les miniatures manquantes (JPEG 320x240) et écrit catalogue/index.json.
    `only` : styles (voxel, ps1, console) et/ou catégories (decor, lieu, vox, perso, visage, look, monstre, craft, son). Styles absents = tous ; catégories seules = VOXEL seulement (comme avant)."""
    from PIL import Image
    from .voxelgpu import b_props as BP, vox_import as VI, contract as C, render
    THUMBS.mkdir(parents=True, exist_ok=True)
    only = set(only or ()); flags = only & set(STYLE_FLAGS); kinds = only - flags
    do = flags or ({'voxel'} if kinds else set(STYLE_FLAGS))
    es = entries(); todo = {'decor': [], 'lieu': [], 'vox': [], 'perso': [], 'visage': [], 'look': [], 'monstre': [], 'craft': []}
    for e in es:
        kind = e['id'].split('/')[0]; e['thumb'] = f"thumbs/{slug(e['id'])}.jpg"
        if kind not in todo or 'voxel' not in do: continue
        if kinds and kind not in kinds: continue
        if force or not (OUT / e['thumb']).exists(): todo[kind].append(e)
    def stills(contract, tag, entries_):
        cp = OUT / f'_work_{tag}.json'; C.save(contract, cp); sd = OUT / f'_work_{tag}'; times = [round(s['t0'] + .12, 2) for s in contract['stages']]
        render.run_painter(cp, None, 'nvidia', (480, 360), stills=times, stills_dir=sd, quiet=True, fallback=True)
        for e, t in zip(entries_, times): Image.open(sd / f't_{t:.2f}.png').convert('RGB').resize((320, 240), Image.LANCZOS).save(OUT / e['thumb'], quality=80)
    t0 = time.time()
    for kind in ('decor', 'vox'):
        lst = todo[kind]
        for bi in range(0, len(lst), batch):
            chunk = lst[bi:bi + batch]; items = []; ok = []
            for e in chunk:
                try:
                    if kind == 'decor': p, lt = BP.convert_item(dict(type='b:' + e['key'], at=[0, 0])); items.append((e['key'], [p], lt))
                    else: items.append((e['key'], [VI.bset(e['key'], **({'height': 2.0} if e['category'] == 'Personnages' else {}))], []))
                    ok.append(e)
                except Exception as ex: log(f"  ignoré {e['id']} : {type(ex).__name__}: {str(ex)[:80]}")
            if ok: stills(_contract(items), f'{kind}{bi // batch}', ok)
            log(f'{kind} {min(bi + batch, len(lst))}/{len(lst)} ({time.time() - t0:.0f} s)')
    lst = todo['lieu']
    for bi in range(0, len(lst), 12):
        chunk = lst[bi:bi + 12]
        try: stills(_place_contract([e['key'] for e in chunk]), f'lieu{bi // 12}', chunk)
        except Exception as ex: log(f'  lieux ignorés ({type(ex).__name__}: {str(ex)[:100]})')
        log(f'lieu {min(bi + 12, len(lst))}/{len(lst)}')
    lst = todo['craft']
    if lst:
        from .voxelgpu import craft as CR
        CR.load_all()
        for bi in range(0, len(lst), batch):
            chunk = lst[bi:bi + batch]; items = []; ok = []
            for e in chunk:
                try:
                    nm, sd_ = e['key'].split(':'); p, lt = CR.bset(nm, seed=int(sd_)); items.append((e['key'], [p], lt)); ok.append(e)
                except Exception as ex: log(f"  ignoré {e['id']} : {type(ex).__name__}: {str(ex)[:80]}")
            if ok: stills(_contract(items, bright=True), f'craft{bi // batch}', ok)
            log(f'craft {min(bi + batch, len(lst))}/{len(lst)} ({time.time() - t0:.0f} s)')
    lst = todo['look'] + todo['monstre']
    if lst:
        CS = _chars_mod()
        for bi in range(0, len(lst), 12):
            chunk = lst[bi:bi + 12]
            try:
                ep = CS.episode([(e['key'], e['cast'] if 'cast' in e else {'b_look': e['key']}) for e in chunk], False); c = _build_director(ep)
                cp = OUT / '_work_look.json'; C.save(c, cp); sd = OUT / '_work_look'; times = [round(c['stages'][2 * i]['t0'] + .25, 2) for i in range(len(chunk))]
                render.run_painter(cp, None, 'nvidia', (480, 360), stills=times, stills_dir=sd, quiet=True, fallback=True)
                for e, t in zip(chunk, times): Image.open(sd / f't_{t:.2f}.png').convert('RGB').resize((320, 240), Image.LANCZOS).save(OUT / e['thumb'], quality=80)
            except Exception as ex: log(f'  looks ignorés ({type(ex).__name__}: {str(ex)[:100]})')
            log(f'look {min(bi + 12, len(lst))}/{len(lst)}')
    lst = todo['visage']
    if lst:
        sys.path.insert(0, str(ROOT / 'tools')); import b_faces_sheet as FS
        for bi in range(0, len(lst), 24):
            chunk = lst[bi:bi + 24]
            try:
                c = FS.contract_for([e['key'] for e in chunk], 'noe'); cp = OUT / '_work_visage.json'; C.save(c, cp); sd = OUT / '_work_visage'; times = [round(s['t0'] + .2, 2) for s in c['stages']]
                render.run_painter(cp, None, 'nvidia', (360, 480), stills=times, stills_dir=sd, quiet=True, fallback=True)
                for e, t in zip(chunk, times): Image.open(sd / f't_{t:.2f}.png').convert('RGB').resize((240, 320), Image.LANCZOS).crop((0, 40, 240, 280)).resize((320, 240), Image.LANCZOS).save(OUT / e['thumb'], quality=80)
            except Exception as ex: log(f'  visages ignorés ({type(ex).__name__}: {str(ex)[:100]})')
            log(f'visage {min(bi + 24, len(lst))}/{len(lst)}')
    lst = todo['perso']
    if lst:
        CS = _chars_mod(); G = CS.groups(); by = {f'perso/{g}/{l}': (g, c) for g, items in G.items() for l, c in items}
        for g in G:
            part = [e for e in lst if by[e['id']][0] == g]
            for bi in range(0, len(part), 12):
                chunk = part[bi:bi + 12]
                try:
                    ep = CS.episode([(e['key'].split('/', 1)[1], by[e['id']][1]) for e in chunk], g == 'animals'); c = _build_director(ep)
                    cp = OUT / '_work_perso.json'; C.save(c, cp); sd = OUT / '_work_perso'; times = [round(c['stages'][2 * i]['t0'] + .25, 2) for i in range(len(chunk))]
                    render.run_painter(cp, None, 'nvidia', (480, 360), stills=times, stills_dir=sd, quiet=True, fallback=True)
                    for e, t in zip(chunk, times): Image.open(sd / f't_{t:.2f}.png').convert('RGB').resize((320, 240), Image.LANCZOS).save(OUT / e['thumb'], quality=80)
                except Exception as ex: log(f'  {g} ignorés ({type(ex).__name__}: {str(ex)[:100]})')
                log(f'perso/{g} {min(bi + 12, len(part))}/{len(part)}')
    if 'voxel' in do and (not kinds or 'son' in kinds): _sound_build(es, force, log)
    if 'ps1' in do:
        from . import catalogue_ps1 as P1
        P1.build([e for e in es if not e.get('reference')], force=force, log=log, only=kinds or None)          # les banques importées (reference) restent sans miniature PS1 : inspiration seulement
    if 'console' in do:
        from . import catalogue_console as CC
        CC.build(es, force=force, log=log)
    kept = []
    for e in es:
        th = thumbs_of(e) if not str(e['id']).startswith(('son/', 'sonreel/')) else {}
        if th: e['thumbs'] = th; e['thumb'] = th.get('voxel') or next(iter(th.values()))
        elif not (OUT / e['thumb']).exists(): continue
        kept.append(e)
    es = kept
    INDEX.write_text(json.dumps(es, ensure_ascii=False), encoding='utf-8'); log(f'catalogue : {len(es)} éléments avec miniature -> {INDEX}')
    return es


def load():
    try: es = json.loads(INDEX.read_text(encoding='utf-8'))
    except (OSError, ValueError): return []
    from . import styles
    for e in es:
        if str(e['id']).startswith('console/'): e['styles'] = {'console': 'native'}          # style à part : pas de version PS1 / VOXEL
        else: e['styles'] = styles.of_entry(e)                                                 # quel élément passe dans quel style (PS1 / VOXEL)
        if not str(e['id']).startswith(('son/', 'sonreel/')): e['thumbs'] = thumbs_of(e)                    # miniature de chaque style, telle qu'elle existe sur le disque aujourd'hui
    return es


if __name__ == '__main__':
    sys.path.insert(0, str(ROOT))
    a = sys.argv[1:]
    if a[:1] == ['build']: build(only=(set(a[1:]) - {'force'}) or None, force='force' in a[1:])
    else: print('usage : python -m hstudio.catalogue build [voxel] [ps1] [console] [decor lieu vox perso visage look monstre craft son] [force]')
