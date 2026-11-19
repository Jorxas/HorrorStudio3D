"""Épisode au format PIXEL 3D (le format du studio) -> contrat VOXEL, SANS réécrire l'épisode.

La régie, la caméra, les collisions, la parole, les gestes, les expressions viennent de PIXEL 3D (`ps1_bake.py`) ; VOXEL ne fait que peindre : ses personnages, ses visages, sa lumière,
ses décors (les lieux de PIXEL 3D traduits par `b_sets`). Choisir « VOXEL » pour un projet ne change donc que les graphismes.
"""
import copy, json, math
from . import contract as C, ps1_bake as PB, b_sets as BS, b_props as BP, b_chars as BC, b_monsters as BM, b_fx as BX, b_costumes as BCO, b_objets as BO
from ..engines.pixel3d import costumes as COS
from .director import RowMaker, EXPR_MAP, ASPECT_K, _eff_fov, _scale_of


LAST_ENGINE = None


def is_ps1(ep):
    """vrai pour un épisode écrit pour PIXEL 3D : `cast` (et non `casts`), des plans en `lines`, ou un lieu nommé par `set`"""
    if not ep.get('shots'): return False
    if ep.get('style') == 'console': return False
    if ep.get('voxel_dsl'): return False                 # opt-out : épisode écrit directement dans le DSL bas niveau de VOXEL (mood, spots, tracks...)
    return 'cast' in ep or ep.get('style') == 'pixel3d' or 'default_set' in ep


def _env_from_lines(lines, duration):
    import numpy as np
    n = int(duration * 30) + 60; env = np.zeros(n, np.float32)
    for l in lines:
        a = int(l['start'] * 30); b = int(l['end'] * 30)
        for i in range(max(0, a), min(n, b)): env[i] = .55 + .45 * abs(math.sin(i * .9))
    return env


def build(ep, lines, duration, aspect='9:16', fps=24, log=print, extras=None):
    """ep (PIXEL 3D) + lignes calées (`lines.json` fusionné) -> contrat VOXEL"""
    from ..engines.pixel3d.render import Pixel3DEngine
    from ..engines.pixel3d import frame as F, places as PL
    ep = copy.deepcopy(ep); extras = extras or {}
    global LAST_ENGINE
    eng = Pixel3DEngine(ep, lines, _env_from_lines(lines, duration), duration, aspect); LAST_ENGINE = eng       # l'habillage commun (overlay.py) est dessiné par ce moteur
    ctx = eng.ctx; ep = eng.ep
    baked = PB.bake(eng, fps, log)
    aspect_k, fov_k = ASPECT_K[aspect]
    exprs = list(C.EXPRESSIONS)
    ids = []
    for bs in baked:
        for a in bs.ids:
            if a not in ids: ids.append(a)
    casts = {}
    for a in ids:
        look = {k: v for k, v in F.resolve_look(ctx, a).items()}
        if look.get('kind') == 'faceless':                      # l'homme sans visage : en VOXEL, le spectre à capuche du catalogue de monstres (version native, pas le même objet)
            look = dict(kind='creature', archetype='wraith', height=2.1 * float(look.get('scale', 1.12) or 1.12), eyes=[0, 0, 0])
        casts[a] = BM.resolve(a, BC.resolve(a, look))
        casts[a].setdefault('preset', 'npc')
    if any(COS.wants(F.resolve_look(ctx, a)) for a in ids):              # costumes XVIIIe (opt-in `costume`) : version VOXEL native, b_costumes.py / b_costumes.js
        BCO.resolve_casts(casts, {a: F.resolve_look(ctx, a) for a in ids}, baked)
    held_map = BO.add_held(casts, baked, {a: F.resolve_look(ctx, a) for a in ids}, ids)     # objets tenus détaillés, image par image (`od_*`, ou les noms d'avant sous la clé `objets`) ; vide sinon
    stages = []; props_state = {}
    from . import lip_layer as LL
    lip = LL.prepare(ep, ids)                                          # synchro labiale sur une voix (opt-in `lipsync`) : couche visage des acteurs qui chantent / parlent
    v3c = BX.collapse_targets(baked); towers = {}                    # V3 : les tours qui s'effondrent sont refaites en VOXEL par le lieu (étages à `t1`), le reste du lieu est inchangé
    for bs in baked:
        shot = bs.shot; name = bs.set_name
        spec = dict((ep.get('sets') or {}).get(name, {}) or {})
        if 'type' not in spec: spec['type'] = name if (name in ('etage_zero', 'apartment', 'pompe_station', 'theatre_bal', 'hotel_nuit') or name in PL.PLACES) else 'room'
        hide = tuple(sorted(v3c.get(name, {}))); bset = BS.get(name, spec, hide) if hide else BS.get(name, spec)
        n = len(bs.frames); dur = bs.t1 - bs.t0
        sa = PB.BakedActing(bs, fps, n)
        makers = {a: RowMaker(fps, _scale_of(casts, a), False) for a in bs.ids}
        actors = {a: [] for a in bs.ids}; camera = []; diss = {a: [] for a in bs.ids}
        for j in range(n + 2):
            fr = bs.frames[min(j, n - 1)]; tt = j / fps
            for a in bs.ids:
                s = fr['samp'].get(a)
                if s is None: s = dict(x=0., y=0., z=0., heading=0., face='neutral', talking=False, visible=False, rig={})
                actors[a].append(makers[a].row(tt, s, exprs)); diss[a].append(round(float(s.get('dissolve', 0.)), 3))
            pos, tgt, fov, roll = fr['cam']
            camera.append([round(float(v), 5) for v in (*pos, *tgt, _eff_fov(fov, fov_k), roll)])
        part = bset.stage_parts(bs.t0, bs.t1 + 2. / fps)
        if hide:
            if name not in towers: towers[name] = [p_ for gid in hide for p_ in BX.tower_props(bset, spec, gid, v3c[name][gid])]
            part['props'] = part['props'] + copy.deepcopy(towers[name])
        dyn_all = [(bs.frames[min(j, n - 1)]['state'].get('_dyn')) for j in range(n + 2)]                   # calque dynamique : effets V3 de PIXEL 3D en VOXEL natif (b_fx.py)
        dyn_all = [dict(b=d[0], l=d[1]) if (d and (d[0] or d[1])) else None for d in dyn_all] if any(d and (d[0] or d[1]) for d in dyn_all) else None
        base_stage = dict(world='plateau', tail=0., dissolve=0., mood=shot.get('mood', ep.get('mood')), look=shot.get('look') or {}, focus_actor=(bs.ids or [None])[0])
        for kk in ('dof', 'mblur'):            # 9/11/2026, opt-in episode / shot keys: depth of field and motion blur of the painter (0 = sharp everywhere) ; absent = painter defaults (0.35 / 0.15)
            vv = shot.get(kk, ep.get(kk))
            if vv is not None: base_stage[kk] = float(vv)
        env = dict(part['env'])
        wk = shot.get('weather', env.get('weather'))
        if wk and wk != 'none':
            amt = float(shot.get('weather_amount', ep.get('weather_amount', 1.)))
            zf = getattr(getattr(bset.st, 'base', None), 'zone_fn', None)
            if zf is not None:                    # lieu à zones (station) : VOXEL ne sait pas masquer la pluie par zone ; à l'intérieur on la réduit (PS1 la masque exactement)
                import numpy as _np
                cp = bs.frames[len(bs.frames) // 2]['cam'][0]; px, pz = -cp[0] / PB.K, -cp[2] / PB.K
                if zf(_np.asarray([[px, 1.5, pz]], _np.float32))[0] > 0: amt *= .3
            env['weather'] = wk; env['weather_amount'] = amt
        arrays = dict(camera=camera, actors={a: [[round(v, 5) for v in row] for row in rows] for a, rows in actors.items()}, diss={a: d for a, d in diss.items() if any(v > 0 for v in d)})
        steps = {a: [[round(bs.t0 + s_[0], 4), *s_[1:]] for s_ in makers[a].steps] for a in bs.ids if makers[a].steps}
        mob = getattr(bset.st, 'mobile', None)
        cuts = [(0, n + 2)]
        has_objs = any(f['state'].get('_objs') for f in bs.frames)
        if mob is not None or has_objs:                       # éléments mobiles (voiture, écran, téléphone) : le plan est découpé en tranches quand leur état change ; chaque tranche porte son décor
            def key_of(j):
                s_ = bs.frames[min(j, n - 1)]['state']; c_ = s_.get('car')
                oh = tuple((tuple(round(float(v), 2) for v in b.lo), tuple(round(float(v), 2) for v in b.hi)) for b in (s_.get('_objs') or []))
                ad = tuple(round(float(s_.get(k) or 0.), 1) for k in ('apt_door', 'elevator_doors', 'dim'))
                return (oh, ad, round(float(c_[1]) * 4) if c_ else None, c_ and c_[3], c_ and c_[4], s_.get('monitor'), (-1 if s_.get('monitor_feed') is None else s_['monitor_feed']) // 2, s_.get('handset'), tuple(round(v, 2) for v in s_['handset_pos']) if s_.get('handset_pos') else None, s_.get('landline_ring', 0) > 0, s_.get('phone_photo'), round(float(s_.get('phone_y', 0.)) * 5),
                        bset.st.mobile_key(s_) if hasattr(bset.st, 'mobile_key') else None)      # lieu dont l'état change beaucoup (hotel_nuit) : sa propre clé de tranche
            cuts = []; i0 = 0
            for j in range(1, n):                              # une tranche commence toujours dans le plan (j < n) : à n ou n + 1, son t0 dépasserait celui du plan suivant (« t0 recule »)
                if j - i0 >= 6 and key_of(j) != key_of(i0): cuts.append((i0, j)); i0 = j
            cuts.append((i0, n + 2))
        for si, (i0, i1) in enumerate(cuts):
            last = si == len(cuts) - 1; e1 = min(n + 2, i1 + 2)
            st_ = bs.frames[min(i0, n - 1)]['state']; props = copy.deepcopy(part['props']); lights = list(part['lights'])
            ob_ = st_.get('_objs')
            if ob_:
                ob_, od_ = BO.split(ob_)                                  # objets détaillés du plan : version VOXEL native (la même liste sans eux)
                props.append(BP.boxes_to_bset([BS._copy_box(b) for b in ob_], 0, 0., 0., 0., BS.K, {}))
                if od_: props.append(BP.boxes_to_bset(od_, 0, 0., 0., 0., BS.K, {}))
                for l in st_.get('_olt') or []: lights.append(BP.light_to_voxel(l[0], l[1], l[2], l[3], gain=2.2))
            if mob is not None:
                nat = getattr(bset.st, 'mobile_native', None)
                if nat is not None:
                    mb, ml, items = nat(st_, bs.t0 + i0 / fps)
                    if items: props.extend(BP.convert_props([dict(it, at=[-BS.K * it['at'][0], -BS.K * it['at'][-1]]) for it in items])[0])
                else: mb, ml = mob(st_, bs.t0 + i0 / fps)
                if mb:
                    mb, od_ = BO.split(mb)                                # éléments mobiles détaillés (téléphone, standard de l'hôtel sous la clé `objets`) : version native
                    props.append(BP.boxes_to_bset([BS._copy_box(b) for b in mb], 0, 0., 0., 0., BS.K, {}))
                    if od_: props.append(BP.boxes_to_bset(od_, 0, 0., 0., 0., BS.K, {}))
                for (pos_, col_, pw_, rad_) in ml: lights.append(BP.light_to_voxel(pos_, col_, pw_, rad_, gain=2.2))
            stage = dict(base_stage, id=f'{bs.k:02d}_{name}' + (f'_{si}' if len(cuts) > 1 else ''), t0=bs.t0 + i0 / fps, t1=bs.t0 + (i1 if not last else n) / fps,
                         camera=arrays['camera'][i0:e1], actors={a: rows[i0:e1] for a, rows in arrays['actors'].items()}, props=props, lights=lights, env=dict(env))
            if (st_.get('monitor_feed') or -1) >= 0 or st_.get('monitor_feed') == 0: stage['dof'] = 0.; stage['mblur'] = 0.          # l'image de la caméra de surveillance doit rester nette
            if len(stage['camera']) < 2: continue
            if bset.doors: stage['doors'] = bset.door_tracks(sa, n + 2, 0, fps) if len(cuts) == 1 else {}
            if dyn_all is not None and any(f is not None for f in dyn_all[i0:e1]): stage['dyn'] = dict(frames=dyn_all[i0:e1])
            if arrays['diss']: stage['dissolve_tracks'] = {a: d[i0:e1] for a, d in arrays['diss'].items()}
            stage['foley_steps'] = {a: [x for x in st if stage['t0'] - 1e-6 <= x[0] < stage['t1'] + 2. / fps] for a, st in steps.items()}
            BCO.add_stage_tracks(stage, casts, bs.frames, i0, e1, n)          # costumes : évasement de la jupe et accessoires, image par image (rien sans costume)
            BCO.add_floor_poses(stage, bs.frames, bs.ids, i0, e1, n)          # scènes dirigées `kneel` / `sit_floor` : une valeur par image (rien sans la clé)
            if held_map: BO.add_stage_held(stage, held_map, bs.frames, i0, e1, n)       # objet tenu détaillé par image (rien sans objet détaillé)
            if lip is not None: lip.add_stage(stage, stage['t0'], fps)
            if hasattr(bset.st, 'stage_frame'):                    # théâtre : lumière de scène image par image (b_theatre.frame_row), peinte par theatre_kit.js
                from . import b_theatre as BT
                stage['theatre'] = dict(cols=BT.COLS, follow_cols=BT.FOLLOW_COLS, pool_cols=BT.POOL_COLS, frames=[BT.frame_row(bs.frames[min(j, n - 1)]['state']['_stage']) for j in range(i0, e1)])
            stages.append(stage)
    fxs = list(ep.get('fx') or []); seg = None                                                                      # flashs (éclairs) calculés par PS1 : un événement `flash` par séquence d'images allumées
    for bs in baked:
        for j, fr in enumerate(bs.frames):
            v = float(fr['state'].get('_flash', 0.)); t = bs.t0 + j / fps
            if v > .04:
                if seg is None: seg = [t, t, v, v]
                else: seg[1] = t; seg[2] = max(seg[2], v)
            elif seg is not None and t - seg[1] > 1.5 / fps:
                fxs.append(dict(type='flash', t0=round(seg[0], 3), t1=round(seg[1] + 1. / fps, 3), **{'from': 1., 'to': 0.}, peak=round(min(1., seg[2]), 3))); seg = None
    if seg is not None: fxs.append(dict(type='flash', t0=round(seg[0], 3), t1=round(seg[1] + 1. / fps, 3), **{'from': 1., 'to': 0.}, peak=round(min(1., seg[2]), 3)))
    prop_sets = {}
    if any(isinstance(v_, dict) and v_.get('type') in ('composed', 'theatre_bal') for v_ in (ep.get('sets') or {}).values()):     # (théâtre : des milliers de briques)         # V3 : lieux composés (villes, falaises) lourds : les décors d'un même lieu ne sont écrits qu'une fois
        import hashlib
        for s in stages:
            pr = s.get('props'); raw = json.dumps(pr, sort_keys=True, separators=(',', ':')) if pr else ''
            if len(raw) > 100000:
                key = hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]; prop_sets[key] = pr; s['props_ref'] = key; del s['props']
    sfx_v3 = [dict(t=round(bs.t0 + t, 3), name=name, gain=round(float(gain), 3), dur=dur) for bs in baked for (t, name, gain, dur) in BX.sounds(bs.shot, bs.t0)]      # sons des effets V3 (tonnerre, effondrement, rotor, ailes) : ceux de PIXEL 3D, à ses instants
    mirror = BX.wants_mirror(ep)
    if mirror:                                                       # V3 : l'image 3D est retournée par le peintre (contrat `mirror`) : les textes peints dans le décor sont retournés d'avance
        for s in stages: BX.mirror_text_props(s.get('props'))
        for pr in prop_sets.values(): BX.mirror_text_props(pr)
    genre = ep.get('genre', extras.get('genre', 'neutral'))
    for s in stages:
        if not s.get('mood') and genre: s['mood'] = C.GENRES.get(genre, 'neutral')
    out = dict(schema=C.SCHEMA, face_style='natural', title=ep.get('title', 'sans titre'), genre=genre, aspect=aspect, fps=fps, duration=float(duration), casts=casts, expressions=exprs,
               actor_cols=C.ACTOR_COLS, stages=stages, fx=fxs, captions=[], caption_style=ep.get('caption_style') or {}, hud=None, overlay='ps1',
               cards=ep.get('cards') or [], audio=dict(extras.get('audio') or {}, **({'sfx': list((extras.get('audio') or {}).get('sfx') or []) + sfx_v3} if sfx_v3 else {})))
    if prop_sets: out['prop_sets'] = prop_sets
    if ep.get('words'): out['words'] = C.clean_words(ep['words'])         # mots 3D d'un clip musical ; avec `mirror`, le peintre les retourne d'avance pour qu'ils se relisent
    if mirror: out['mirror'] = True
    if lip is not None and lip.used: out['face_cols'] = LL.FACE_COLS
    if any(s.get('theatre') for s in stages): out['spot_pool'] = 8; out['point_pool'] = 8           # théâtre : le peintre ouvre 8 projecteurs et 8 lumières (main_unified.js) ; absent = 2 et 4, comme avant
    probs = C.validate(out)
    if probs: raise ValueError('contrat invalide : ' + '; '.join(probs[:5]))
    return out
