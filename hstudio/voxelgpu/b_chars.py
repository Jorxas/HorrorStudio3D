"""Les personnages et créatures de PIXEL 3D (V3) dans le peintre VOXEL : tenues, chapeaux, coiffures, objets en main, personnages prêts, animaux.

Même principe que b_props.py / b_sets.py : on appelle les recettes D'ORIGINE de PIXEL 3D (`poses.hair_and_hat`, `poses.torso`, `poses.held_item`, `creatures.animal`,
`creatures.PRESETS`) et on traduit leurs boîtes dans le repère des os de VOXEL (chars4.js) ; rien n'est recopié.

Syntaxe d'un `casts` d'épisode voxel (tout est facultatif, un cast sans ces clés est rendu exactement comme avant) :
  {"b_preset": "zombie"}                                          un des 28 personnages prêts (creatures.PRESETS) ; les clés ci-dessous le surchargent
  {"preset": "npc", "outfit": "suit", "hat": "tophat", "hold": "book", "hair_style": "bun", "beard": true, "glasses": true, "cape": [150, 20, 30], "backpack": true}
  {"kind": "animal", "animal": "dog", "color": [150, 100, 60], "posture": "sit" | "lie" | "fly", "scale": 1.0}
  couleurs : [r, g, b] (0-255) ou "#rrggbb" ; `skin`, `hair`, `hood` (couleur du haut), `jeans`, `shirt`, `tie`, `hat_color`, `hold_color`.

Repères (mesurés sur chars4.js) : PIXEL 3D a la tête (centre à 1,68 m, 0,42 m de large) et le torse (1,12 m de haut au centre, 0,50 m de large) plus petits que VOXEL (tête 0,50 m,
torse 0,525 m de large et 0,76 m de haut) : tête x1,2 ; torse x1,05 en largeur et x1,19 en hauteur autour de la ceinture (0,80 m). La main principale de PIXEL 3D est la main droite du
personnage, c'est `handR` de VOXEL (x négatif quand il regarde +z), d'où le miroir en x de l'objet tenu. Les animaux regardent +z, comme les personnages de VOXEL : pas de demi-tour.

Ce qui reste fixe (dit sans fard) : cape, sac, lunettes, barbe, objets tenus suivent le corps mais ne s'animent pas ; la tête des animaux ne tourne pas ; les animaux marchent par séries
d'images (12 poses de marche, 12 de repos), pas par jambes articulées ; les coiffures `strands*` sont rendues par les coiffures `short`/`long` de VOXEL.
"""
import math, base64
import numpy as np
from . import b_props as BP

HEAD_K = 1.2          # tête de PIXEL 3D -> tête de VOXEL
HEAD_Y0 = 1.68        # centre de la tête de PIXEL 3D (m)
TORSO_KXZ, TORSO_KY, WAIST = 1.05, 1.19, .80
HOLD_K = 1.15
ANIMAL_K = 1.1
NW, NI = 12, 12       # images de marche / de repos des animaux
SWING = .22
IDLE_HZ = 8.
VARIANT_HAIR = [(26, 18, 16), (200, 160, 80), (90, 58, 32), (26, 26, 26), (138, 74, 32)]
KEYS = ('b_preset', 'outfit', 'hat', 'hat_color', 'hair_style', 'hold', 'hold_color', 'beard', 'glasses', 'cape', 'backpack', 'hood', 'jeans', 'shirt', 'tie', 'face', 'skin', 'hair', 'animal')
TORSO_OUTFITS = ('hoodie', 'tshirt', 'shirt', 'suit', 'dress', 'coat', 'armor', 'robe', 'apron', 'lab_coat', 'uniform', 'spacesuit')
FACE_SPEC = {   # `face` de PIXEL 3D -> couleur d'iris et réglages du visage de VOXEL (face4.js)
    'skull': dict(iris=0x050505, extra=dict(iris=1.9, brow=0)), 'robot': dict(iris=0x40e8ff, extra=dict(iris=1.5, brow=0)), 'alien': dict(iris=0x050505, extra=dict(iris=1.75, brow=0)),
    'evil': dict(iris=0xcc1c1c, extra=dict(iris=1.1)), 'tired': dict(extra=dict(eo=.7, low=.45)), 'happy': dict(extra={})}


def _rgb(c, d=None):
    """une couleur -> (r, g, b) 0-255 : entier 0xrrggbb, chaîne "#rrggbb", liste [r, g, b] en 0-255 ou en 0-1 (réels)"""
    if c is None or isinstance(c, bool): return d
    if isinstance(c, int): return ((c >> 16) & 255, (c >> 8) & 255, c & 255)
    if isinstance(c, str):
        c = c.lstrip('#'); return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    v = [float(x) for x in c[:3]]
    if any(isinstance(x, float) for x in c[:3]) and max(v) <= 1.0: v = [x * 255 for x in v]
    return tuple(int(round(x)) for x in v)


def _hex(c): return BP._hex([v / 255. for v in c])


def _diff(a, b):
    """les boîtes de `a` qui ne sont pas dans `b` (mêmes coins et même couleur)"""
    key = lambda x: (tuple(np.round(x.lo, 4)), tuple(np.round(x.hi, 4)), tuple(np.round(x.col, 3)))
    seen = {key(x) for x in b}
    return [x for x in a if key(x) not in seen]


def _box(c, s, col, emis=0., alpha=1.):
    o = dict(x=round(float(c[0]), 4), y=round(float(c[1]), 4), z=round(float(c[2]), 4), w=round(float(s[0]), 4), h=round(float(s[1]), 4), d=round(float(s[2]), 4), color=_hex(col))
    if emis: o['emis'] = round(float(emis), 3)
    if alpha < 1.: o['alpha'] = alpha
    return o


def _map(boxes, tf, sc):
    """boîtes de PIXEL 3D -> boîtes VOXEL : le centre par `tf`, les dimensions par `sc` = (sx, sy, sz)"""
    out = []
    for b in boxes:
        if getattr(b, 'hidden', False): continue
        c = (np.asarray(b.lo, float) + np.asarray(b.hi, float)) / 2; s = np.abs(np.asarray(b.hi, float) - np.asarray(b.lo, float))
        glass = bool(b.refl) and not b.cast and b.emis <= .1                  # verre (bulle de l'astronaute) : translucide
        out.append(_box(tf(c), (s[0] * sc[0], s[1] * sc[1], s[2] * sc[2]), tuple(np.asarray(b.col) * 255), b.emis, .35 if glass else 1.))
    return out


def head_boxes(hat, hat_col, top, hair, style):
    """chapeau (ou coiffure sans équivalent dans VOXEL) -> boîtes dans le repère du centre de la tête de VOXEL"""
    from ..engines.pixel3d import poses as P
    k = {}
    if hat and hat != 'none': bx = P.hair_and_hat(0, 0, 0, 1, hair, 'bald', hat, hat_col, top, k)
    elif style in ('ponytail', 'bun', 'spiky'): bx = _diff(P.hair_and_hat(0, 0, 0, 1, hair, style, None, None, top, k), P.hair_and_hat(0, 0, 0, 1, hair, 'short', None, None, top, k))
    else: return []
    return _map(bx, lambda c: (c[0] * HEAD_K, (c[1] - HEAD_Y0) * HEAD_K, c[2] * HEAD_K), (HEAD_K, HEAD_K, HEAD_K))


def torso_boxes(outfit, top, skin, tie, shirt, apron_color=None):
    from ..engines.pixel3d import poses as P
    return _map(P.torso(0, 0, 1, 0, outfit, top, skin, {}, tie, shirt, apron_color), lambda c: (c[0] * TORSO_KXZ, (c[1] - WAIST) * TORSO_KY, c[2] * TORSO_KXZ), (TORSO_KXZ, TORSO_KY, TORSO_KXZ))


def held_boxes(item, col):
    """-> (boîtes autour de la main principale en repère du personnage, lumières [(pos, couleur, puissance, rayon)])"""
    from ..engines.pixel3d import poses as P
    lights = []; bx = P.held_item(item, (0., 0., 0.), 1, {}, lights, col)
    out = _map(bx, lambda c: (-c[0] * HOLD_K, c[1] * HOLD_K, c[2] * HOLD_K), (HOLD_K, HOLD_K, HOLD_K))
    return out, [dict(at=[round(-p[0] * HOLD_K, 3), round(p[1] * HOLD_K, 3), round(p[2] * HOLD_K, 3)], color=_hex([int(v * 255) for v in c]), i=round(float(pw) * 2.2, 3), dist=round(float(rad) * 1.5, 2)) for (p, c, pw, rad) in lights]


def _face_boxes(glasses, beard, hair, face=None):
    """lunettes et barbe : PIXEL 3D les peint sur la texture du visage, VOXEL a son propre visage : on les pose en boîtes sur la face avant de la tête (repère du centre de la tête)"""
    bx = []; z = .262
    if face == 'skull':                                 # crâne : orbites creuses, trou du nez, dents (le visage de VOXEL ne sait pas faire un crâne)
        bx += [_box((s * .125, .035, z), (.17, .15, .016), (8, 8, 10)) for s in (-1, 1)] + [_box((0, -.04, z), (.05, .07, .016), (8, 8, 10)), _box((0, -.15, z), (.24, .075, .016), (8, 8, 10))]
        bx += [_box((x * .045, -.15, z + .006), (.02, .075, .01), (236, 232, 220)) for x in (-2, -1, 0, 1, 2)]
    if glasses:
        dark = (10, 10, 12) if glasses in ('sun', 'sunglasses') else (24, 24, 30)
        for s in (-1, 1):
            x = s * .125
            for dx, dy, w, h in ((0, .062, .17, .018), (0, -.062, .17, .018), (-.08, 0, .018, .13), (.08, 0, .018, .13)): bx.append(_box((x + dx, .03 + dy, z), (w, h, .014), dark))
            if dark == (10, 10, 12): bx.append(_box((x, .03, z), (.16, .12, .012), dark))
        bx.append(_box((0, .04, z), (.07, .016, .014), dark)); bx += [_box((s * .215, .045, z - .12), (.016, .016, .24), dark) for s in (-1, 1)]
    # La bouche du visage de VOXEL est dessinée à ~12 cm sous le centre de la tête (x ±5 à ±6 cm, de -17 à -10 cm de haut en cri) et le nez au-dessus : la barbe reste donc
    # SOUS y = -0,18 au milieu du visage, et monte seulement sur les côtés (joues, favoris) ; ni la bouche ni le nez ne sont recouverts.
    sh = lambda k: tuple(max(0, min(255, int(c * k))) for c in hair)               # léger grain : de légères variations de la couleur des cheveux
    if beard in (True, 'full', 'beard'):
        for x, k in ((-.145, .94), (-.049, 1.06), (.049, .97), (.145, 1.04)):      # menton et mâchoire, en quatre colonnes de grain différent
            bx.append(_box((x, -.218, .262), (.098, .07, .03), sh(k)))
        bx += [_box((s * .215, -.12, .26), (.07, .16, .03), sh(.92)) for s in (-1, 1)]               # joues et favoris, de la mâchoire jusque sous les yeux
        bx += [_box((s * .245, -.1, .14), (.03, .16, .26), sh(.88)) for s in (-1, 1)]                # côtés de la tête
        bx.append(_box((0, -.252, .13), (.42, .03, .27), sh(.9)))                                   # dessous du menton
        bx += [_box((s * .075, -.088, .264), (.075, .022, .022), sh(1.0)) for s in (-1, 1)]          # moustache en deux ailes, bouche et nez libres
    elif beard == 'mustache': bx.append(_box((0, -.088, .264), (.16, .026, .022), sh(1.0)))
    elif beard == 'stubble':
        bx += [_box((0, -.2, .258), (.36, .09, .012), sh(.85), alpha=.6)] + [_box((s * .215, -.12, .256), (.07, .15, .012), sh(.85), alpha=.6) for s in (-1, 1)]
    return bx


def _body_extras(cape, backpack, outfit):
    bx = []
    if backpack and outfit in (None, 'hoodie', 'tshirt', 'coat', 'suit', 'shirt'): bx.append(_box((0, (1.14 - WAIST) * TORSO_KY, -.22), (.38, .55, .15), (36, 40, 44)))
    if cape: bx.append(_box((0, (.92 - WAIST) * TORSO_KY, -.20), (.567, 1.25, .03), cape))
    return bx


def _animal_frames(kind, color, posture, size):
    from ..engines.pixel3d import creatures as CR
    def conv(bx):
        boxes, decals = [], []
        for b in bx:
            v = BP._to_voxel(b, ANIMAL_K * size)
            if v: boxes.append(v)
            for key, tx in (b.tex or {}).items():
                tx = np.asarray(tx)
                if key != 5 or tx.ndim != 3: continue
                lo, hi = np.asarray(b.lo, float) * ANIMAL_K * size, np.asarray(b.hi, float) * ANIMAL_K * size; c = (lo + hi) / 2
                rgba = np.ascontiguousarray(tx.astype(np.uint8)[::-1, :, :4])
                decals.append(dict(x=round(float(c[0]), 4), y=round(float(c[1]), 4), z=round(float(hi[2]) + .004, 4), w=round(float(hi[0] - lo[0]), 4), h=round(float(hi[1] - lo[1]), 4), ry=0., tw=int(rgba.shape[1]), th=int(rgba.shape[0]), rgba=base64.b64encode(rgba.tobytes()).decode('ascii')))
        return dict(boxes=boxes, decals=decals)
    walk = [conv(CR.animal(kind, color, SWING * math.sin(2 * math.pi * i / NW), i / NW * 1.5, {}, posture, 1.)) for i in range(NW)]
    idle = [conv(CR.animal(kind, color, 0., i / IDLE_HZ, {}, posture, 1.)) for i in range(NI)]
    if posture == 'fly': walk = idle
    return dict(walk=walk, idle=idle, idle_hz=IDLE_HZ)


TRIGGERS = ('b_look', 'b_preset', 'outfit', 'hat', 'hair_style', 'hold', 'beard', 'glasses', 'cape', 'backpack')      # seules clés qui font passer un cast par b_chars : les autres (`hood`, `skin`, `face`...) servent déjà aux films existants


def is_b(d):
    if not isinstance(d, dict) or d.get('kind') in ('faceless', 'creature'): return False
    return d.get('kind') == 'animal' or any(k in d for k in TRIGGERS)


def resolve(cid, d):
    """une entrée de `casts` -> la même, complétée de `look`, `face`, `bx` (humanoïdes) ou `frames` (animaux). Sans clé de PIXEL 3D : renvoyée telle quelle."""
    d = dict(d)
    if d.get('b_look'):                    # un personnage importé refondu (b_look.py, LOOKS.json de sa banque) : son cast, surchargé par les clés écrites à côté
        from . import b_look; d = b_look.expand(d)
    if not is_b(d): return d
    from ..engines.pixel3d import creatures as CR
    if d.get('kind') == 'animal':
        kind = d.get('animal', 'dog')
        if kind not in CR.ANIMALS: raise ValueError(f"animal inconnu : {kind!r} (disponibles : {', '.join(CR.ANIMALS)})")
        d['frames'] = _animal_frames(kind, _rgb(d.get('color')), d.get('posture'), float(d.get('size', 1.)))
        d.setdefault('scale', 1.); return d
    base = {}
    if d.get('b_preset'):
        if d['b_preset'] not in CR.PRESETS: raise ValueError(f"personnage prêt inconnu : {d['b_preset']!r} (disponibles : {', '.join(CR.PRESETS)})")
        base = dict(CR.PRESETS[d['b_preset']])
    base.update({k: v for k, v in d.items() if k in KEYS and k not in ('b_preset', 'animal')})
    if 'scale' in base and 'scale' not in d: d['scale'] = base.pop('scale')
    variant = int(d.get('variant', 0))
    outfit = base.get('outfit'); hat = base.get('hat'); style = base.get('hair_style') or 'short'
    hair = _rgb(base.get('hair'), VARIANT_HAIR[variant % len(VARIANT_HAIR)])
    top_c = _rgb(base.get('hood'), (74, 71, 78) if outfit in (None, 'hoodie') else (90, 90, 100)); skin = _rgb(base.get('skin'), (240, 168, 116))
    pants_c = skin if outfit == 'dress' else _rgb(base.get('jeans'), (44, 44, 50))
    look = {}
    if base.get('skin') is not None: look['skin'] = _hex(skin)
    if base.get('hood') is not None or outfit: look['top'] = dict(type={'hoodie': 'hoodie', 'coat': 'coat'}.get(outfit, 'plain'), color=_hex(top_c), shirt=_hex(_rgb(base.get('shirt'), (24, 24, 28))))
    if outfit == 'tshirt': look['top']['sleeve'] = 'short'
    elif outfit == 'dress': look['top']['sleeve'] = 'none'
    if base.get('jeans') is not None or outfit == 'dress': look['pants'] = dict(color=_hex(pants_c))
    bare = bool(hat and hat != 'none')
    if 'hair' in base or 'hair_style' in base or bare or style == 'bald':
        hid = hat in ('hood', 'helmet', 'astronaut')
        look['hair'] = None if (style == 'bald' or hid) else dict(style={'long': 'long', 'strands_long': 'long', 'curly': 'curly'}.get(style, 'short'), color=_hex(hair), color2=_hex(tuple(min(255, int(c * 1.25)) for c in hair)), bare=bare)
    fs = FACE_SPEC.get(base.get('face') or '', {})
    if 'iris' in fs: look['iris'] = fs['iris']
    if 'face' in d: pass
    elif fs.get('extra'): d['face'] = dict(fs['extra'])
    bx = {}
    hb = head_boxes(hat, _rgb(base.get('hat_color')), top_c, hair, style) + _face_boxes(base.get('glasses'), base.get('beard'), hair, base.get('face'))
    if d.get('headphones') == 'cou':                 # 9/11/2026 : headphones worn around the neck (opt-in value 'cou'), under the head, cups at the sides of the neck
        hb += [_box((s * .17, -.36, .05), (.09, .18, .18), (30, 30, 36)) for s in (-1, 1)] + [_box((s * .17, -.36, .05 + .092), (.05, .07, .01), (60, 62, 70)) for s in (-1, 1)] + [_box((0, -.39, -.13), (.44, .06, .07), (30, 30, 36))]
    if hb: bx['head'] = hb
    tb = torso_boxes(outfit, top_c, skin, _rgb(base.get('tie')), _rgb(base.get('shirt')),base.get('apron_color')) if outfit and outfit != 'hoodie' else []
    tb += _body_extras(_rgb(base.get('cape')), base.get('backpack'), outfit)
    if tb: bx['torso'] = tb
    if base.get('hold'):
        from . import b_objets as BO
        hc = BO.held_contract(base['hold'], _rgb(base.get('hold_color')))          # objets détaillés (01/11/2026) : `od_*` toujours, un nom d'avant sous la clé `objets` ; None sinon
        if hc is not None and hc['boxes']:
            bx['hold'] = hc['boxes']
            if hc['decals']: bx['hold_decals'] = hc['decals']
            if hc['lights']: bx['hold_lights'] = hc['lights']
        else:
            hb2, hl = held_boxes(base['hold'], _rgb(base.get('hold_color')))
            bx['hold'] = hb2
            if hl: bx['hold_lights'] = hl
    if bx: d['bx'] = bx
    if look: d['look'] = {**(d.get('look') or {}), **look}
    d.setdefault('preset', 'npc')
    return d
