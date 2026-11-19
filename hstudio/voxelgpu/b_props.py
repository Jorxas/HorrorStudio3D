"""Les décors de PIXEL 3D (V3) dans le peintre VOXEL : un seul catalogue, pas deux.

PIXEL 3D fabrique chaque meuble, arbre ou véhicule avec une fonction qui rend des boîtes colorées (`sets.prop_boxes`). VOXEL sait
peindre des boîtes (accessoire `bset`, voxelgpu_js/engine/b_kit.js). Ce module appelle la fonction D'ORIGINE (aucune copie des 217 recettes :
une correction dans PIXEL 3D profite aux deux) et traduit sa sortie :

  * repère : un décor PIXEL 3D a sa face avant vers -z (la caméra de PIXEL 3D est de ce côté) ; la caméra de VOXEL est du côté +z. Le décor est
    donc tourné d'un demi-tour autour de son propre pied avant d'être posé : posé sans rotation, il regarde la caméra, comme dans PIXEL 3D.
    `rot` (quarts de tour) garde le sens de PIXEL 3D, `at` est le repère de VOXEL.
  * échelle : les personnages de VOXEL font environ 2,0 m contre 1,85 m pour ceux de PIXEL 3D ; les décors sont agrandis de PROP_SCALE autour de leur pied
    pour garder les proportions (une porte reste plus haute qu'un personnage).
  * matière : couleur et émission sont gardées (l'émission fait les néons, lampes, écrans) ; les images de face (enseignes, tableaux, fenêtres) deviennent
    des plaques texturées ; reflets, grain et matières procédurales ne sont pas portés (voir `stats` : rien n'est perdu en silence).
  * lumières : `PROP_LIGHTS` de PIXEL 3D (lampes, néons, bougies) deviennent des lumières de plan.

Un nom qui existe aussi côté VOXEL (`door`, `boxes`, `sign`...) reste celui de VOXEL ; écrire `b:door` pour la version PIXEL 3D.
"""
import base64, math
import numpy as np

PROP_SCALE = 1.1
NATIVE = {'sign', 'poster_plan', 'breaker_box', 'door', 'alarm_button', 'price_sign', 'tube', 'hand', 'mirror_eyes', 'room', 'boxes', 'bset',
          'beacon', 'clockface', 'mover', 'shuttle'}
HALF = np.array([[-1, 0, 0], [0, 1, 0], [0, 0, -1]], np.float32)


def catalogue():
    """tous les types de décor de PIXEL 3D (recettes de base, bibliothèque, enrichissement)"""
    from ..engines.pixel3d import sets as S
    return list(S.PROP_TYPES)


def is_b(kind):
    return kind.startswith('b:') or (kind not in NATIVE and kind in set(catalogue()))


def _hex(c):
    r, g, b = (int(round(min(1., max(0., float(v))) * 255)) for v in c[:3]); return (r << 16) | (g << 8) | b


def _yaw_of(R):
    R = np.asarray(R, float)
    if abs(R[1][1] - 1) < 1e-4 and abs(R[0][1]) < 1e-4 and abs(R[1][0]) < 1e-4: return math.atan2(R[0][2], R[0][0])
    return None


def _turn(x, z, rot):
    rot %= 4
    return (x, z) if rot == 0 else (z, -x) if rot == 1 else (-x, -z) if rot == 2 else (-z, x)


def _to_voxel(b, k):
    """une boîte de PIXEL 3D (coin bas + coin haut, éventuellement dans un repère tourné) -> boîte VOXEL (centre + dimensions)"""
    if getattr(b, 'hidden', False): return None
    inst = b.inst; ry = 0.
    lo, hi = np.asarray(b.lo, float), np.asarray(b.hi, float)
    if inst is not None:
        yaw = _yaw_of(inst.R)
        if yaw is None: lo, hi = np.asarray(b.wlo, float), np.asarray(b.whi, float)          # repère penché : la boîte englobante
        else:
            c = (lo + hi) / 2; c = np.asarray(inst.R, float) @ c + np.asarray(inst.piv, float); sz = hi - lo; ry = yaw; lo, hi = c - sz / 2, c + sz / 2
    c = (lo + hi) / 2 * k; sz = np.abs(hi - lo) * k
    if (sz <= 1e-5).any(): return None
    o = dict(x=round(float(c[0]), 4), y=round(float(c[1]), 4), z=round(float(c[2]), 4), w=round(float(sz[0]), 4), h=round(float(sz[1]), 4), d=round(float(sz[2]), 4), color=_hex(b.col))
    if b.emis and b.emis > 0: o['emis'] = round(float(b.emis), 3)
    if ry: o['ry'] = round(ry, 4)
    if getattr(b, 'mat', 0) == 77: o['alpha'] = round(max(.05, 1. - float(b.dissolve or 0.)), 3)     # objets détaillés VOXEL (b_objets.glass) : vapeur, verre, faisceau ; aucune boîte PS1 n'a ce matériau
    return o


def _decals(boxes, rot, x, y, z, k, stats):
    """images de face (enseignes, tableaux, fenêtres) -> plaques posées sur la face, dans le repère de PIXEL 3D d'avant le demi-tour"""
    out = []
    for b in boxes:
        for key, tx in (b.tex or {}).items():
            tx = np.asarray(tx)
            if key not in (0, 1, 4, 5) or b.inst is not None or tx.ndim != 3 or tx.shape[2] < 4: stats['textures_lost'] = stats.get('textures_lost', 0) + 1; continue
            lo, hi = np.asarray(b.lo, float), np.asarray(b.hi, float); cx, cy, cz = (lo + hi) / 2; e = .004
            c, n, w = {4: ((cx, cy, lo[2] - e), (0, -1), hi[0] - lo[0]), 5: ((cx, cy, hi[2] + e), (0, 1), hi[0] - lo[0]),
                       0: ((lo[0] - e, cy, cz), (-1, 0), hi[2] - lo[2]), 1: ((hi[0] + e, cy, cz), (1, 0), hi[2] - lo[2])}[key]
            px, pz = _turn(-c[0], -c[2], rot); qx, qz = _turn(-n[0], -n[1], rot)                                  # demi-tour puis quarts de tour, comme les boîtes
            rgba = np.ascontiguousarray(tx.astype(np.uint8)[::-1, :, :4])                                          # rangées de bas en haut (DataTexture)
            out.append(dict(x=round(px * k + x, 4), y=round(c[1] * k + y, 4), z=round(pz * k + z, 4), w=round(w * k, 4), h=round((hi[1] - lo[1]) * k, 4), ry=round(math.atan2(qx, qz), 4),
                            tw=int(rgba.shape[1]), th=int(rgba.shape[0]), rgba=base64.b64encode(rgba.tobytes()).decode('ascii'), **({'emis': round(float(b.texemis), 3)} if b.texemis else {})))
    return out


FLAT_ROT = 2                       # quarts de tour appliqués à l'image d'une face horizontale (réglé sur une planche de contrôle : le mot du comptoir de la station)
def _flats(boxes, rot, x, y, z, k):
    """images posées À PLAT sur le dessus d'une boîte (un mot sur un comptoir, un dessin sur une couverture) : plaque horizontale"""
    out = []
    for b in boxes:
        tx = (b.tex or {}).get(3)
        if tx is None or b.inst is not None: continue
        tx = np.asarray(tx)
        if tx.ndim != 3 or tx.shape[2] < 4: continue
        lo, hi = np.asarray(b.lo, float), np.asarray(b.hi, float); cx, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
        px, pz = _turn(-cx, -cz, rot)
        a = np.rot90(tx.astype(np.uint8)[:, :, :4], FLAT_ROT)[:, ::-1]          # + miroir gauche-droite (le demi-tour VOXEL)
        rgba = np.ascontiguousarray(a[::-1])
        out.append(dict(x=round(px * k + x, 4), y=round(hi[1] * k + y + .004, 4), z=round(pz * k + z, 4), w=round((hi[0] - lo[0]) * k, 4), d=round((hi[2] - lo[2]) * k, 4),
                        tw=int(rgba.shape[1]), th=int(rgba.shape[0]), rgba=base64.b64encode(rgba.tobytes()).decode('ascii'), **({'emis': round(float(b.texemis), 3)} if b.texemis else {})))
    return out


def boxes_to_bset(boxes, rot=0, x=0., y=0., z=0., k=PROP_SCALE, stats=None):
    """boîtes de PIXEL 3D (repère local d'un décor, ou d'un lieu entier) -> ({"type": "bset", boxes, decals}, [boîtes déjà tournées pour les lumières n'en ont pas besoin])
    demi-tour autour de l'origine, agrandissement `k`, puis `rot` quarts de tour et décalage (x, y, z)."""
    from ..engines.pixel3d import sets as S
    stats = stats if stats is not None else {}
    decals = _decals(boxes, rot, x, y, z, k, stats); flats = _flats(boxes, rot, x, y, z, k)
    for b in boxes:
        if b.inst is None:
            lo, hi = b.lo.copy(), b.hi.copy(); b.lo = np.array([-hi[0], lo[1], -hi[2]], np.float32); b.hi = np.array([-lo[0], hi[1], -lo[2]], np.float32)
        else:                                                         # boîte dans un repère tourné : on tourne le repère, pas la boîte
            b.inst = type(b.inst)(R=HALF @ np.asarray(b.inst.R, np.float32), piv=HALF @ np.asarray(b.inst.piv, np.float32))
            cs = np.array([[a, c, d] for a in (b.lo[0], b.hi[0]) for c in (b.lo[1], b.hi[1]) for d in (b.lo[2], b.hi[2])], np.float32) @ b.inst.R.T + b.inst.piv
            b.wlo, b.whi = cs.min(0), cs.max(0)
    if rot % 4 and all(b.inst is None for b in boxes): boxes = S.place(boxes, 0., 0., rot)
    out = []
    for b in boxes:
        v = _to_voxel(b, k)
        if v is None: continue
        if rot % 4 and b.inst is not None:
            px, pz = _turn(v['x'], v['z'], rot); v['x'], v['z'] = round(px, 4), round(pz, 4); v['ry'] = round(v.get('ry', 0.) + [0, math.pi / 2, math.pi, -math.pi / 2][rot % 4], 4)
        v['x'] = round(v['x'] + x, 4); v['y'] = round(v['y'] + y, 4); v['z'] = round(v['z'] + z, 4); out.append(v)
    prop = dict(type='bset', boxes=out)
    if decals: prop['decals'] = decals
    if flats: prop['flats'] = flats
    return prop


def light_to_voxel(lp, col, pw, rad, rot=0, x=0., y=0., z=0., k=PROP_SCALE, gain=2.2):
    lx, lz = _turn(-float(lp[0]) * k, -float(lp[2]) * k, rot)
    return dict(at=[round(x + lx, 3), round(y + float(lp[1]) * k, 3), round(z + lz, 3)], color=_hex(col), i=round(float(pw) * gain, 3), dist=round(float(rad) * 1.5, 2), decay=1.4)


def _native_boxes(kind, p):
    """boîtes de la version VOXEL native d'un décor `qt_*` (b_quartiers.VOX) ou `qi_*` (b_interieurs.VOX), ou None"""
    if kind.startswith('qt_'):
        from . import b_quartiers as BQ; fn = BQ.VOX.get(kind)
    elif kind.startswith('qi_'):
        from . import b_interieurs as BI; fn = BI.VOX.get(kind)
    else:
        from . import b_objets as BO                                    # objets détaillés : `od_*` toujours, un nom d'avant (tv, plant...) sous la clé `objets`
        if kind.startswith('od_'): return BO.native_boxes(kind, p)
        from ..engines.pixel3d import objets as OD
        if OD.active() is not None and OD.active().get('decors') and p.get('objets') is not False:
            if kind in OD.UP_PROPS: k2, p2 = OD.UP_PROPS[kind](dict(p), None); return BO.native_boxes(k2, p2)
            if kind in OD.UP_RAW: return BO.native_boxes('_raw:' + kind, dict(p))
        return None
    return fn(p) if fn else None


def convert_item(it, stats=None):
    """{"type": "sofa", "at": [x, z] | [x, y, z], "rot": 0..3, "color": [r, g, b], ...} -> ({"type": "bset", "boxes": [...]}, [lumière de plan, ...])"""
    from ..engines.pixel3d import sets as S, world as W
    stats = stats if stats is not None else {}
    kind = it['type'][2:] if it['type'].startswith('b:') else it['type']
    p = {k: v for k, v in it.items() if k not in ('type', 'at', 'rot', 'y', 't0', 't1')}
    at = list(it.get('at') or [0, 0]); x, z = float(at[0]), float(at[-1]); y = float(it.get('y', at[1] if len(at) == 3 else 0.)); rot = int(it.get('rot', 0))
    nat = _native_boxes(kind, p)                                       # décors à DEUX versions natives (quartiers, intérieurs) : la version VOXEL, pas les boîtes PS1 retraduites
    prop = boxes_to_bset(nat if nat is not None else S.prop_boxes(kind, p), rot, x, y, z, stats=stats)
    for k in ('t0', 't1'):
        if k in it: prop[k] = it[k]
    return prop, [light_to_voxel(lp, col, pw, rad, rot, x, y, z) for (lp, col, pw, rad, fl) in W.PROP_LIGHTS.get(kind, [])]


def convert_props(items, stats=None):
    """une liste de `props` de plan : les types de PIXEL 3D deviennent des `bset` ; le reste passe tel quel -> (props, lumières)"""
    props, lights = [], []
    for it in items or []:
        t = it.get('type') if isinstance(it, dict) else None
        if isinstance(t, str) and (t == 'vox' or t.startswith('vox:')):          # modèle .vox importé (banques de voxelgpu_js/assets_vox) : {"type": "vox:kk_halloween/coffin", "at": [x, z], "rot": 0, "height": 2.0}
            from . import vox_import as VI
            at = list(it.get('at') or [0, 0]); name = t[4:] if t.startswith('vox:') else it['model']
            p = VI.bset(name, scale=it.get('scale'), height=it.get('height'), length=it.get('length'), at=(float(at[0]), float(at[-1])), y=float(it.get('y', at[1] if len(at) == 3 else 0.)), rot=int(it.get('rot', 0)))
            for k in ('t0', 't1'):
                if k in it: p[k] = it[k]
            props.append(p)
        elif isinstance(t, str) and t.startswith('craft:'):                  # élément « craft » dessiné ici (craft.py) : {"type": "craft:oak_tree", "at": [x, z], "rot": 0, "scale": 1, "seed": 3}
            from . import craft as CR
            CR.load_all(); at = list(it.get('at') or [0, 0])
            p, lt = CR.bset(t[6:], at=(float(at[0]), float(at[-1])), y=float(it.get('y', at[1] if len(at) == 3 else 0.)), rot=int(it.get('rot', 0)), scale=float(it.get('scale', 1.)), seed=int(it.get('seed', 0)))
            for k in ('t0', 't1'):
                if k in it: p[k] = it[k]
            props.append(p); lights += lt
        elif isinstance(t, str) and is_b(t):
            p, lt = convert_item(it, stats); props.append(p); lights += lt
        else: props.append(it)
    return props, lights
