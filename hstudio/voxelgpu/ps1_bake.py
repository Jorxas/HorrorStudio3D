"""Une seule logique, deux peintres : le style PS1 (PIXEL 3D) CALCULE la scène, le style VOXEL la PEINT.

Pour un épisode au format PIXEL 3D (`cast`, `set`, `lines`, `camera`, `actors`, `actions`...), on ne réécrit rien pour VOXEL : on fait tourner la régie, les caméras, les
collisions et les presets de PIXEL 3D tels quels, image par image, et on garde le résultat (qui est où, tourné vers où, quel geste, quelle expression, où est la caméra).
Ce résultat est ensuite posé dans le repère de VOXEL (le demi-tour et l'agrandissement `K` de `b_sets`) et peint par le moteur GPU avec ses propres graphismes.

    ep PIXEL 3D + lignes calées --bake()--> {plan: images [{acteurs, caméra, ...}]} --from_ps1.build()--> contrat VOXEL

Rien ici ne dessine. Rien n'est aléatoire.
"""
import math
import numpy as np

K = 1.1                       # b_props.PROP_SCALE : le monde de PIXEL 3D est agrandi de 10 % pour les personnages de VOXEL (~2 m)
HEAD_YAW0 = 0.


class BakedShot:
    """tout ce que la régie de PIXEL 3D a décidé pour un plan, image par image (repère de PIXEL 3D)"""

    def __init__(self, k, t0, t1, shot, set_name):
        self.k = k; self.t0 = t0; self.t1 = t1; self.shot = shot; self.set_name = set_name
        self.frames = []          # {'samp': {aid: sample}, 'cam': (pos, yaw, pitch, roll, fov), 'doors': {id: angle}, 'T': s}
        self.ids = []


def _clamp(x, a=0., b=1.): return max(a, min(b, x))


def _heading_of(fc, x, z, cam_z):
    """cap (atan2(dx, dz)) d'un acteur d'un plan classique, selon la clé `facing` : mêmes règles que `frame.actor_boxes`"""
    if fc in ('+z', 1, '1'): return 0.
    if fc in ('-z', -1, '-1'): return math.pi
    if fc == '+x': return math.pi / 2
    if fc == '-x': return -math.pi / 2
    if fc == 'away': return math.pi if cam_z > z else 0.
    return 0. if cam_z > z else math.pi              # 'camera' ou absent


def _classic_samples(ctx, shot, st, T, u, g, cam_z):
    """plan sans couche « acteurs » : les acteurs de `frame.eval_actors` deviennent des échantillons de la même forme que ceux de la régie"""
    from ..engines.pixel3d import frame as F
    from ..engines.pixel3d import poses as P
    actors = F.eval_actors(ctx, shot, st, T, u, g); out = {}
    for aid, ac in actors.items():
        a = ac['spec']; look = ac['look']
        vis = a.get('visible'); visible = True if vis is None else (vis[0] <= T <= vis[1])
        post = a.get('posture') if a.get('posture') in P.POSTURES else None
        gest = a.get('gesture') if a.get('gesture') in P.GESTURES else None
        mv = a.get('move', 'walk' if ac['moving'] else 'still')
        rig = dict(sit=1. if post == 'sit' else 0., crouch=1. if post in ('crouch', 'kneel') else 0., air=1. if post == 'jump' else 0., lean=0., slump=0., tension=0.,
                   run=1. if mv == 'run' else 0., gait=1. if (ac['moving'] or mv in ('run', 'walk', 'stumble')) and mv != 'still' else 0.,
                   head=(float(F.val(a.get('head_y'), u, 0.) or 0.), float(F.val(a.get('head_x'), u, 0.) or 0.)),
                   gestures=[(gest, 1., T)] if gest and gest != 'idle' else [], hands=None, back=False)
        kind = a.get('face', look.get('face', 'creature' if look.get('kind') == 'creature' else 'neutral'))
        for ch in a.get('face_changes', []) or []:
            if T >= float(ch.get('at', 1e9)): kind = ch.get('face', kind)
        talking = bool(a.get('lipsync') and ctx.mouth(g) > .12) or (a.get('mouth') is not None and float(F.val(a.get('mouth'), u, 0.) or 0.) > .12) or bool(a.get('laugh'))
        item = a.get('hold', look.get('hold'))
        out[aid] = dict(x=ac['x'], y=ac['yoff'], z=ac['z'], heading=_heading_of(a.get('facing', 'camera'), ac['x'], ac['z'], cam_z), face=kind, talking=talking,
                        visible=visible, rig=rig, hold=item, dissolve=float(F.val(a.get('dissolve'), u, 0.) or 0.))
    return out, actors


def bake_objects(ctx, shot, st, actors, cam, T, u, g):
    """-> (boîtes, lumières, calque dynamique) des `objects` d'un plan. Les objets de l'ancien catalogue (téléphone, débris, éclats...) sont ce que PIXEL 3D dessine, repris tels quels ;
    les effets V3 (foudre, effondrement, objets et créatures en vol : `effects.EFFECTS`) gardent la logique de PIXEL 3D (flash du ciel compris) mais sont dessinés en version VOXEL native (b_fx.py)"""
    from ..engines.pixel3d import frame as F, effects as FX
    from . import b_fx as BX
    try:
        if not BX.has_v3(shot):
            obx, olt = F.eval_objects(ctx, shot, st, actors, cam, T, u, g); return obx, olt, None
        legacy = dict(shot, objects=[o for o in (shot.get('objects') or []) if o.get('type') not in FX.EFFECTS])
        obx, olt = F.eval_objects(ctx, legacy, st, actors, cam, T, u, g)
        F.eval_objects(ctx, shot, st, actors, cam, T, u, g)                          # le flash du ciel (éclair) et le masquage des éléments sont ceux de PIXEL 3D
        return obx, olt, BX.frame(ctx, shot, st, actors, cam, T, u, g)
    except Exception as e:
        msg = f'objets du plan en échec ({type(e).__name__} : {e})'
        if msg not in BX.LIMITS: BX.LIMITS.append(msg)
        return [], [], None


def bake_frame(ctx, g):
    """-> (k, T, samp, cam, door_angles) : ce que `frame.build_frame` calcule AVANT de dessiner"""
    from ..engines.pixel3d import frame as F, world as W
    from ..engines.pixel3d import acted as AC
    from ..engines.pixel3d import effects as FX
    k, t0, t1 = ctx.tl.at(g)
    shot0 = ctx.ep['shots'][k]
    shot, T, span = F.apply_cut(shot0, g - t0, t1 - t0)
    u = _clamp(T / max(1e-3, span)); F.CUR_T[0] = T; W.TIME[0] = g
    ctx.hide_static = set(); ctx.fx_flash = 0.
    st = ctx.get_set(shot.get('set', ctx.ep.get('default_set', 'etage_zero')))
    state = dict(ctx.ep.get('state', {}) or {}); state.update(shot.get('state', {}) or {}); state = F.apply_state_track(shot, F.resolve_state(state, u), T)
    acting = ctx.get_acting()
    if k in acting.shots:
        sa = acting.shots[k]; Tt = g - t0; uu = _clamp(Tt / max(1e-3, t1 - t0))
        samp = sa.sample(Tt)
        for aid, (dx, dy, dz) in FX.carry_offsets(shot, Tt, sa).items():
            if aid in samp: samp[aid] = dict(samp[aid], x=samp[aid]['x'] + dx, y=samp[aid].get('y', 0.) + dy, z=samp[aid]['z'] + dz)
        looks = {aid: F.resolve_look(ctx, aid) for aid in samp}
        samp = AC.COS.add_spin(sa, samp, looks, Tt)                  # costumes (opt-in): spin rate -> skirt flare, the same as PS1 ; untouched without a costume
        res = AC.camera_acted(ctx, sa, shot, st, samp, looks, Tt, uu, g, k)
        if res is None:
            actors = {aid: dict(spec={'id': aid, 'facing': '+z' if math.cos(s['heading']) > 0 else '-z'}, look=looks[aid], x=s['x'], z=s['z'], swing=0.,
                                scale=float(looks[aid].get('scale', 1.)), yoff=0., moving=False) for aid, s in samp.items()}
            cam, _ = F.eval_camera(ctx, shot, st, actors, Tt, uu, g)
        else: cam, _ = res
        out = {}
        for aid, s in samp.items():
            spec = sa.spec_actors.get(aid, {})
            d = dict(s); d['dissolve'] = max(float(s.get('dissolve', 0.) or 0.), float(F.val(spec.get('dissolve'), uu, 0.) or 0.)); d['hold'] = s.get('hold'); out[aid] = d
        doors = {did: sa.door_angle(did, Tt) for did in getattr(sa, 'doors', {})}
        actors2 = {aid: dict(spec={'id': aid}, look=looks[aid], x=s['x'], z=s['z'], scale=float(looks[aid].get('scale', 1.)), yoff=0., heading=s['heading']) for aid, s in samp.items()}
        obx, olt, dyn = bake_objects(ctx, shot, st, actors2, cam, Tt, uu, g)           # objets du plan (téléphone, débris, éclats, yeux, lumières...) : ce que PS1 dessine, repris par VOXEL
        state = dict(state, _objs=obx, _olt=olt, _flash=float(getattr(ctx, 'fx_flash', 0.)), _dyn=dyn)
        if hasattr(st, 'stage_frame'): state['_stage'] = st.record(ctx, k, shot, {a: (v['x'], v.get('y', 0.), v['z']) for a, v in out.items() if v.get('visible', True)}, Tt, uu, g, state)     # théâtre : lumière de scène de l'image (theatre.py)
        return k, Tt, out, cam, doors, state
    actors0 = F.eval_actors(ctx, shot, st, T, u, g)
    cam, _ = F.eval_camera(ctx, shot, st, actors0, T, u, g)
    samp, actors1 = _classic_samples(ctx, shot, st, T, u, g, cam[0][2])
    obx, olt, dyn = bake_objects(ctx, shot, st, actors0, cam, T, u, g)
    state = dict(state, _objs=obx, _olt=olt, _flash=float(getattr(ctx, 'fx_flash', 0.)), _dyn=dyn)
    if hasattr(st, 'stage_frame'): state['_stage'] = st.record(ctx, k, shot, {a: (v['x'], v.get('y', 0.), v['z']) for a, v in samp.items() if v.get('visible', True)}, T, u, g, state)     # théâtre : lumière de scène de l'image
    return k, T, samp, cam, {}, state


def to_voxel(samp, cam):
    """repère de PIXEL 3D -> repère de VOXEL : demi-tour autour de l'axe vertical, puis agrandissement K (le même que `b_sets` et `b_props`)"""
    out = {}
    for aid, s in samp.items():
        d = dict(s); d['x'] = -K * s['x']; d['z'] = -K * s['z']; d['y'] = K * float(s.get('y', 0.)); d['heading'] = float(s['heading']) + math.pi
        out[aid] = d
    pos, yaw, pitch, roll, fov = cam
    tgt = (pos[0] + math.sin(yaw) * math.cos(pitch), pos[1] + math.sin(pitch), pos[2] + math.cos(yaw) * math.cos(pitch))
    p2 = (-K * pos[0], K * pos[1], -K * pos[2]); t2 = (-K * tgt[0], K * tgt[1], -K * tgt[2])
    return out, (p2, t2, float(fov), float(roll))


class BakedActing:
    """remplace `acting.timeline.ShotActing` dans le constructeur de contrat : les échantillons viennent de PIXEL 3D, déjà dans le repère de VOXEL"""

    def __init__(self, baked, fps, n):
        self.baked = baked; self.fps = fps; self.n = n
        self.dur = n / fps; self.lines = []; self.world = None
        ids = []
        for fr in baked.frames:
            for a in fr['samp']:
                if a not in ids: ids.append(a)
        self.tracks = {a: None for a in ids}
        self.doors = {}
        for fr in baked.frames:
            for d in fr['doors']: self.doors[d] = True

    def end_states(self): return {}

    def sample(self, t):
        j = int(round(t * self.fps)); j = max(0, min(len(self.baked.frames) - 1, j))
        return self.baked.frames[j]['samp']

    def position(self, tr, t): return (0., 0.)

    def door_angle(self, did, t):
        j = max(0, min(len(self.baked.frames) - 1, int(round(t * self.fps))))
        return self.baked.frames[j]['doors'].get(did, 0.)


def bake(eng, fps, log=print):
    """eng : un `Pixel3DEngine` configuré (épisode, lignes calées, durée) -> [BakedShot] ; images aux instants j/fps du film"""
    ctx = eng.ctx; spans = ctx.tl.spans; shots = []
    for k, (a, b) in enumerate(spans):
        shot = ctx.ep['shots'][k]
        shots.append(BakedShot(k, a, b, shot, shot.get('set', ctx.ep.get('default_set', 'etage_zero'))))
    for k, bs in enumerate(shots):
        n = int(math.ceil((bs.t1 - bs.t0) * fps - 1e-9))
        for j in range(n):
            g = bs.t0 + j / fps
            kk, T, samp, cam, doors, state = bake_frame(ctx, g)
            if kk != k: kk, T, samp, cam, doors, state = bake_frame(ctx, min(g, bs.t1 - 1e-4))
            s2, c2 = to_voxel(samp, cam)
            bs.frames.append(dict(samp=s2, cam=c2, doors=doors, T=T, state=state))
        for fr in bs.frames:
            for a in fr['samp']:
                if a not in bs.ids: bs.ids.append(a)
        if log: log(f'[ps1->voxel] plan {k} « {bs.set_name} » : {len(bs.frames)} images, acteurs {bs.ids}')
    return shots
