"""Places composed from procedural elements instead of ready-made recipes (V3).

A composed set is pure data, so a director (AI or rules) can describe a place that no recipe has:
  {"type": "composed", "ground_y": -24, "ground": "asphalt", "sky": "night", "weather": "rain",
   "elements": [{"kind": "building", "id": "toit", "rect": [-5, -2, 5, 9], "top": 0, "style": "brick", "roof": {...}},
                {"kind": "district", "area": [-70, -50, 70, 90], "count": 40, "top": [-14, 30], "seed": 3}, ...]}
expand() turns it into a RoomSet spec (blocks, props, zones, lights, anchors) and records where characters can stand:
"walkable": [{"rect": [x0, z0, x1, z1], "y": top}]. Outside the walkable levels the ground lies at ground_y; when it is
deep (rooftops, a ravine) it is a void that the acting layer does not walk into (jump, climb and fall cross it).

Every element is a generator with parameters, reusable for other places: the same "building" makes a rooftop, a tower
of a skyline or, with the "rock" style, a cliff over a river.

Elements (rect = [x0, z0, x1, z1] in metres; N is +z, S is -z, W is -x, E is +x)
  building, tower  rect, top (y of the roof), base (default ground_y), style (brick, concrete, office, glass, old, rock,
                   ice), color, lit (share of lit windows at night), seed, windows (false to remove them), walkable,
                   parapet: height | {"height", "sides": "NSWE"}, roof: {"floor": tar|gravel|concrete|metal|wood|grass|helipad,
                   "furniture": [names or {"type", "at", "rot"}], "count", "clear": [rects kept free], "seed"}
  platform         rect, y (top), thickness, material, color, floor (roof texture), rails: true | "NSWE", supports, walkable
  district         area, avoid [rects], count, size [min, max], top [min, max], styles, lit, seed: a skyline of real
                   buildings around the action (rects of the other elements are avoided automatically)
  street           rect on the ground: road, sidewalks, street lights and parked cars (seed, cars, lights)
  prop             any library prop on any level: {"type", "at": [x, z], "y" (default: the level under it), "rot", ...}
  scatter          {"rules": [world.scatter rules], "y", "seed"}
Unknown element kinds are not replaced silently: expand() lists them in spec["_unknown_elements"] (capability audit)."""
import functools, math
import numpy as np
from .world import scatter

STYLES = {   # body colour, lit / dark window colours, storey height, bay width, window share of the bay (w, h), material
    'brick':    dict(color=(128, 68, 54), win=(255, 206, 132), dark=(26, 30, 42), floor=3.0, bay=2.6, ww=.42, wh=.45, material='plaster'),
    'concrete': dict(color=(126, 126, 122), win=(255, 226, 170), dark=(30, 34, 44), floor=3.0, bay=2.4, ww=.5, wh=.42, material='plaster'),
    'office':   dict(color=(84, 96, 112), win=(200, 226, 255), dark=(22, 30, 44), floor=3.4, bay=1.7, ww=.78, wh=.62, material='metal'),
    'glass':    dict(color=(52, 76, 98), win=(180, 220, 255), dark=(18, 28, 42), floor=3.4, bay=1.4, ww=.9, wh=.8, material='metal'),
    'old':      dict(color=(166, 146, 116), win=(255, 196, 120), dark=(34, 30, 34), floor=3.2, bay=3.0, ww=.36, wh=.5, material='plaster'),
    'rock':     dict(color=(104, 96, 86), windows=False, material='stone'),
    'ice':      dict(color=(186, 206, 226), windows=False, material='plaster'),
}
ROOF_COLORS = {'tar': (52, 52, 56), 'gravel': (96, 94, 90), 'concrete': (118, 116, 112), 'metal': (92, 96, 102), 'wood': (110, 80, 54),
               'grass': (54, 92, 46), 'helipad': (58, 60, 64), 'rock': (110, 102, 92), 'snow': (226, 230, 238)}
FURNITURE = ['water_tank', 'ac_unit', 'ac_unit', 'roof_vent', 'roof_vent', 'antenna', 'satellite_dish', 'skylight', 'chimney_stack']
ELEMENTS = ('building', 'tower', 'platform', 'district', 'street', 'prop', 'scatter')
PPM = 4                                   # facade texture pixels per metre (pixel art: one window is a few pixels)

# ------------------------------------------------------------------ textures (cached: a district reuses a few sizes)
@functools.lru_cache(maxsize=512)
def facade_tex(width, height, style, lit, seed, night, face):
    """RGBA facade of one side: windows only (alpha 0 elsewhere, the body colour shows through)"""
    st = STYLES.get(style, STYLES['concrete'])
    tw = max(4, min(320, int(round(width * PPM)))); th = max(4, min(640, int(round(height * PPM))))
    a = np.zeros((th, tw, 4), np.uint8)
    if st.get('windows', True) is False: return a
    rng = np.random.default_rng(seed * 131 + face * 17 + 3)
    floors = max(1, int(height // st['floor'])); bays = max(1, int(width // st['bay']))
    lit_rows = rng.random(floors) < .35                    # some storeys are mostly lit (offices still at work)
    for f in range(floors):
        y0 = f * st['floor'] + st['floor'] * .32; y1 = y0 + st['floor'] * st['wh']
        r0 = max(0, th - int(round(y1 * th / height))); r1 = min(th, th - int(round(y0 * th / height)))
        if r1 <= r0: r1 = min(th, r0 + 1)
        for b in range(bays):
            cx = (b + .5) * width / bays; hw = width / bays * st['ww'] / 2
            c0 = max(0, int(round((cx - hw) * tw / width))); c1 = min(tw, max(c0 + 1, int(round((cx + hw) * tw / width))))
            on = night and rng.random() < lit * (1.8 if lit_rows[f] else .7)
            col = st['win'] if on else st['dark'] if night else (110, 140, 168)
            if on: col = tuple(int(c * (.8 + .2 * rng.random())) for c in col)
            a[r0:r1, c0:c1, :3] = col; a[r0:r1, c0:c1, 3] = 255 if on else (200 if night else 230)
    return a

@functools.lru_cache(maxsize=128)
def roof_tex(kind, width, depth, seed):
    """RGBA top texture: seams, patches, markings (alpha 0 elsewhere)"""
    tw = max(4, min(192, int(round(width * 6)))); th = max(4, min(192, int(round(depth * 6))))
    a = np.zeros((th, tw, 4), np.uint8); rng = np.random.default_rng(seed * 7 + 1)
    yy, xx = np.mgrid[0:th, 0:tw]
    if kind == 'tar':
        for _ in range(max(2, tw * th // 300)):
            x0, y0 = rng.integers(0, tw), rng.integers(0, th); w, h = rng.integers(3, 12), rng.integers(3, 12)
            a[y0:y0 + h, x0:x0 + w] = (44, 44, 48, 255) if rng.random() < .5 else (64, 63, 66, 255)
        a[(xx % 12) == 0] = (70, 70, 74, 255)
    elif kind in ('gravel', 'snow'):
        m = rng.random((th, tw)) < .18; a[m] = (130, 126, 120, 255) if kind == 'gravel' else (250, 252, 255, 255)
    elif kind == 'concrete':
        a[((xx % 18) == 0) | ((yy % 18) == 0)] = (88, 86, 84, 255)
    elif kind == 'metal':
        a[((xx + yy) % 6 == 0) & ((xx - yy) % 6 == 0)] = (130, 136, 142, 255)
    elif kind == 'wood':
        a[(yy % 4) == 0] = (78, 56, 38, 255)
    elif kind == 'grass':
        m = rng.random((th, tw)) < .25; a[m] = (70, 120, 56, 255)
    elif kind == 'helipad':                                  # the yellow circle and the white H (markings only)
        cx, cy = tw / 2, th / 2; r = min(tw, th) * .4
        d = np.hypot(xx - cx, yy - cy); a[(d < r) & (d > r - max(2, r * .12))] = (236, 196, 40, 255)
        hw, hh = r * .42, r * .55; t_ = max(1, int(r * .12))
        bar = (np.abs(yy - cy) < hh) & ((np.abs(xx - (cx - hw)) < t_) | (np.abs(xx - (cx + hw)) < t_))
        a[bar | ((np.abs(yy - cy) < t_) & (np.abs(xx - cx) < hw))] = (240, 240, 236, 255)
        for k in range(12):                                  # edge lights
            ang = k * math.pi / 6; px, py = int(cx + math.cos(ang) * (r + 3)), int(cy + math.sin(ang) * (r + 3))
            a[max(0, py - 1):py + 1, max(0, px - 1):px + 1] = (120, 255, 140, 255)
    return a

def block_textures(bk):
    """(tex dict, texemis) for a free block with "facade" (four sides) or "roof" (top).

    The facade generator is asked of engines/pixel3d/facades.py first: with the episode key "env" it hands
    back a richer, higher-resolution wall (frames, sills, doors, courses) carrying its own emission channel;
    without the key it hands back None and the shipped `facade_tex` below runs exactly as it always did."""
    from . import facades as FA
    w, h, d = (float(v) for v in bk.get('size', (1, 1, 1)))
    if bk.get('facade') and bk['facade'].get('quartier'):          # façade d'un quartier à identité (qt_props.py) : le plan du bâtiment fait les textures
        from . import qt_props as _QP
        return _QP.block_tex(bk)
    if bk.get('facade'):
        f = bk['facade']; style = f.get('style', 'concrete'); lit = float(f.get('lit', .3)); seed = int(f.get('seed', 0)); night = bool(f.get('night', True))
        body = tuple(int(c) for c in bk.get('color', STYLES.get(style, STYLES['concrete'])['color']))
        def one(wd, ht, face):
            return FA.tex(wd, ht, style, lit, seed, night, face, body) if FA.active() else \
                facade_tex(round(wd, 1), round(ht, 1), style, lit, seed, night, face)
        tex = {'-z': one(w, h, 0), '+z': one(w, h, 1), '-x': one(d, h, 2), '+x': one(d, h, 3)}
        return tex, (1.25 if night else 0.)
    kind = bk['roof']
    return {'+y': roof_tex(kind, round(w, 1), round(d, 1), int(bk.get('seed', 0)))}, (.6 if kind == 'helipad' else 0.)

# ------------------------------------------------------------------ elements
class _Ctx:
    def __init__(self, spec):
        self.gy = float(spec.get('ground_y', -20.)); self.seed = int(spec.get('seed', 0))
        self.night = bool(spec.get('night', spec.get('sky', 'night') in ('night', 'storm')))
        self.blocks = []; self.props = []; self.zones = []; self.walkable = []; self.anchors = {}; self.occupied = []; self.unknown = []
        self.n = 0
    def level(self, x, z):
        best = None
        for w in self.walkable:
            x0, z0, x1, z1 = w['rect']
            if x0 <= x <= x1 and z0 <= z <= z1 and (best is None or w['y'] > best): best = w['y']
        return self.gy if best is None else best

def _rect(e):
    x0, z0, x1, z1 = (float(v) for v in e['rect']); return min(x0, x1), min(z0, z1), max(x0, x1), max(z0, z1)

def _edge_anchors(c, gid, x0, z0, x1, z1, inset=.9):
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    c.anchors.update({gid: (cx, cz), gid + '.N': (cx, z1 - inset), gid + '.S': (cx, z0 + inset), gid + '.W': (x0 + inset, cz), gid + '.E': (x1 - inset, cz),
                      gid + '.NW': (x0 + inset, z1 - inset), gid + '.NE': (x1 - inset, z1 - inset), gid + '.SW': (x0 + inset, z0 + inset), gid + '.SE': (x1 - inset, z0 + inset)})

def _sides(v, default='NSWE'):
    if v is True or v is None: return default
    if v is False: return ''
    return str(v).upper()

def building(e, c):
    x0, z0, x1, z1 = _rect(e); w, d = x1 - x0, z1 - z0; cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    top = float(e.get('top', 0.)); base = float(e.get('base', c.gy)); style = e.get('style', 'concrete'); st = STYLES.get(style, STYLES['concrete'])
    gid = e.get('id') or f'batiment{c.n}'; seed = int(e.get('seed', c.seed + c.n * 7)); rock = style in ('rock', 'ice')
    body = {'at': [cx, base, cz], 'size': [w, top - base - .02, d], 'material': st['material'], 'color': list(e.get('color', st['color'])), 'group': gid}
    if st.get('windows', True) is not False and e.get('windows', True):
        body['facade'] = {'style': style, 'lit': float(e.get('lit', .3)), 'seed': seed, 'night': c.night}
    c.blocks.append(body)
    roof = e.get('roof') or {}; rk = roof.get('floor', 'rock' if style == 'rock' else 'snow' if style == 'ice' else 'tar')
    skin = {'at': [cx, top - .02, cz], 'size': [w, .02, d], 'material': 'stone' if rock else 'plaster', 'color': list(roof.get('color', ROOF_COLORS.get(rk, (90, 90, 90)))), 'group': gid, 'seed': seed}
    if rk not in ('rock',): skin['roof'] = rk
    c.blocks.append(skin)
    ph = e.get('parapet', 0. if rock else .9); sides = 'NSWE'
    if isinstance(ph, dict): sides = _sides(ph.get('sides')); ph = float(ph.get('height', .9))
    ph = float(ph or 0.); t = .22; pc = [int(v * .82) for v in body['color']]
    if ph > 0:
        for s in sides:
            if s == 'N': c.blocks.append({'at': [cx, top, z1 - t / 2], 'size': [w, ph, t], 'color': pc, 'material': st['material'], 'group': gid})
            if s == 'S': c.blocks.append({'at': [cx, top, z0 + t / 2], 'size': [w, ph, t], 'color': pc, 'material': st['material'], 'group': gid})
            if s == 'W': c.blocks.append({'at': [x0 + t / 2, top, cz], 'size': [t, ph, d - 2 * t], 'color': pc, 'material': st['material'], 'group': gid})
            if s == 'E': c.blocks.append({'at': [x1 - t / 2, top, cz], 'size': [t, ph, d - 2 * t], 'color': pc, 'material': st['material'], 'group': gid})
    if rock:                                              # outcrops break the box silhouette of a cliff (they stay below the top)
        rng = np.random.default_rng(seed + 5)
        for _ in range(int(e.get('outcrops', 6))):
            side = rng.integers(0, 4); hgt = rng.uniform(.25, .8) * (top - base); ow, od = rng.uniform(1.2, 3.), rng.uniform(.6, 1.6)
            ox = rng.uniform(x0 + 1, x1 - 1) if side < 2 else (x0 - od / 2 + .2 if side == 2 else x1 + od / 2 - .2)
            oz = rng.uniform(z0 + 1, z1 - 1) if side >= 2 else (z0 - od / 2 + .2 if side == 0 else z1 + od / 2 - .2)
            sz = [ow, hgt - 1., od] if side < 2 else [od, hgt - 1., ow]
            c.blocks.append({'at': [ox, base, oz], 'size': sz, 'material': 'stone', 'color': [int(v * rng.uniform(.82, 1.05)) for v in body['color']], 'group': gid})
    furn = roof.get('furniture', [] if rock else 'auto')
    if furn == 'auto' or (isinstance(furn, list) and furn and all(isinstance(f, str) for f in furn)):
        kinds = FURNITURE if furn == 'auto' else furn
        n = int(roof.get('count', max(1, int(w * d / 22))))
        clear = [list(r) for r in roof.get('clear', [])]
        for p in scatter([{'type': kinds, 'count': n, 'area': [x0 + 1.3, z0 + 1.3, x1 - 1.3, z1 - 1.3], 'min_dist': 2.6, 'avoid': clear, 'size': [.85, 1.1]}], int(roof.get('seed', seed))):
            p['y'] = top; p['group'] = gid; c.props.append(p)
    elif isinstance(furn, list):
        for f in furn:
            p = dict(f); p.setdefault('y', top); p['group'] = gid; c.props.append(p)
    if e.get('walkable', True):
        ins = .26 if ph > 0 else .12
        c.walkable.append({'rect': [x0 + ins, z0 + ins, x1 - ins, z1 - ins], 'y': top, 'id': gid})
    _edge_anchors(c, gid, x0, z0, x1, z1, float(e.get('anchor_inset', .9)))
    c.occupied.append((x0, z0, x1, z1))

def platform(e, c):
    x0, z0, x1, z1 = _rect(e); w, d = x1 - x0, z1 - z0; cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    y = float(e.get('y', 0.)); th = float(e.get('thickness', .2)); gid = e.get('id') or f'plateforme{c.n}'
    mat = e.get('material', 'metal'); col = list(e.get('color', {'metal': (96, 100, 106), 'wood': (120, 86, 56), 'stone': (128, 124, 116)}.get(mat, (110, 110, 110))))
    c.blocks.append({'at': [cx, y - th, cz], 'size': [w, th, d], 'material': mat, 'color': col, 'group': gid})
    if e.get('floor'): c.blocks.append({'at': [cx, y - .01, cz], 'size': [w, .012, d], 'color': list(ROOF_COLORS.get(e['floor'], col)), 'roof': e['floor'], 'group': gid, 'seed': int(e.get('seed', 0))})
    for s in _sides(e.get('rails', False), 'NSWE'):
        rc = [70, 72, 76]
        if s in 'NS':
            zz = z1 - .03 if s == 'N' else z0 + .03; c.blocks.append({'at': [cx, y + .95, zz], 'size': [w, .06, .06], 'material': 'metal', 'color': rc, 'group': gid})
            c.blocks += [{'at': [px, y, zz], 'size': [.06, 1.0, .06], 'material': 'metal', 'color': rc, 'group': gid} for px in np.linspace(x0 + .05, x1 - .05, max(2, int(w / 1.5) + 1))]
        else:
            xx = x0 + .03 if s == 'W' else x1 - .03; c.blocks.append({'at': [xx, y + .95, cz], 'size': [.06, .06, d], 'material': 'metal', 'color': rc, 'group': gid})
            c.blocks += [{'at': [xx, y, pz], 'size': [.06, 1.0, .06], 'material': 'metal', 'color': rc, 'group': gid} for pz in np.linspace(z0 + .05, z1 - .05, max(2, int(d / 1.5) + 1))]
    if e.get('supports'):
        for px in (x0 + .2, x1 - .2):
            for pz in (z0 + .2, z1 - .2): c.blocks.append({'at': [px, c.gy, pz], 'size': [.2, y - th - c.gy, .2], 'material': 'metal', 'color': col, 'group': gid})
    if e.get('walkable', True): c.walkable.append({'rect': [x0 + .05, z0 + .05, x1 - .05, z1 - .05], 'y': y, 'id': gid})
    _edge_anchors(c, gid, x0, z0, x1, z1, min(.6, w / 3, d / 3))
    c.occupied.append((x0, z0, x1, z1))

def district(e, c):
    rng = np.random.default_rng(int(e.get('seed', c.seed + 11)))
    ax0, az0, ax1, az1 = (float(v) for v in e.get('area', [-60, -40, 60, 90]))
    avoid = [tuple(float(v) for v in r) for r in e.get('avoid', [])] + [(o[0] - 3, o[1] - 3, o[2] + 3, o[3] + 3) for o in c.occupied]
    smin, smax = e.get('size', [6, 14]); tmin, tmax = e.get('top', [-12, 30]); styles = e.get('styles', ['concrete', 'brick', 'office', 'old', 'glass'])
    gap = float(e.get('gap', 2.5)); placed = []; tries = 0; n = int(e.get('count', 36))
    while len(placed) < n and tries < n * 40:
        tries += 1; w, d = rng.uniform(smin, smax), rng.uniform(smin, smax); x = rng.uniform(ax0, ax1 - w); z = rng.uniform(az0, az1 - d)
        r = (x, z, x + w, z + d)
        if any(r[0] < a[2] and r[2] > a[0] and r[1] < a[3] and r[3] > a[1] for a in avoid): continue
        if any(r[0] < p[2] + gap and r[2] > p[0] - gap and r[1] < p[3] + gap and r[3] > p[1] - gap for p in placed): continue
        placed.append(r)
    gid = e.get('id', 'quartier')
    for k, (x0, z0, x1, z1) in enumerate(placed):
        style = styles[int(rng.integers(0, len(styles)))]; st = STYLES.get(style, STYLES['concrete'])
        top = float(rng.uniform(tmin, tmax)); col = [int(v * rng.uniform(.85, 1.1)) for v in st['color']]
        cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
        c.blocks.append({'at': [cx, c.gy, cz], 'size': [x1 - x0, top - c.gy, z1 - z0], 'material': st['material'], 'color': col, 'group': gid,
                         'facade': {'style': style, 'lit': float(e.get('lit', .25)), 'seed': int(rng.integers(0, 9999)), 'night': c.night}})
        c.blocks.append({'at': [cx, top, cz], 'size': [x1 - x0 + .3, .35, z1 - z0 + .3], 'material': 'plaster', 'color': [int(v * .7) for v in col], 'group': gid})
        if rng.random() < .3: c.props.append({'type': 'antenna', 'at': [cx + rng.uniform(-1, 1), cz + rng.uniform(-1, 1)], 'y': top + .35, 'height': float(rng.uniform(2, 6)), 'group': gid})
        elif rng.random() < .3: c.props.append({'type': 'water_tank', 'at': [cx, cz], 'y': top + .35, 'size': 1.1, 'group': gid})

def street(e, c):
    x0, z0, x1, z1 = _rect(e); rng = np.random.default_rng(int(e.get('seed', c.seed + 23)))
    along_z = (z1 - z0) >= (x1 - x0)
    c.zones.append({'rect': [x0 - 2.5, z0, x1 + 2.5, z1] if along_z else [x0, z0 - 2.5, x1, z1 + 2.5], 'ground': 'stone'})
    c.zones.append({'rect': [x0, z0, x1, z1], 'ground': 'road'})
    if e.get('lights', True):
        for v in np.arange((z0 if along_z else x0) + 4, (z1 if along_z else x1), 12.):
            for side in (-1, 1):
                at = [((x0 + x1) / 2 + side * ((x1 - x0) / 2 + .8)), float(v)] if along_z else [float(v), (z0 + z1) / 2 + side * ((z1 - z0) / 2 + .8)]
                c.props.append({'type': 'streetlight', 'at': at, 'y': c.gy, 'group': e.get('id', 'rue')})
    for k in range(int(e.get('cars', 6))):
        v = rng.uniform(z0 + 2, z1 - 2) if along_z else rng.uniform(x0 + 2, x1 - 2); lane = rng.choice([-1, 1])
        at = [(x0 + x1) / 2 + lane * (x1 - x0) / 4, v] if along_z else [v, (z0 + z1) / 2 + lane * (z1 - z0) / 4]
        c.props.append({'type': 'car', 'at': at, 'y': c.gy, 'rot': 0 if along_z else 1, 'color': [int(x) for x in rng.integers(30, 220, 3)], 'group': e.get('id', 'rue')})

def prop(e, c):
    p = {k: v for k, v in e.items() if k != 'kind'}
    if 'y' not in p: p['y'] = c.level(float(p['at'][0]), float(p['at'][1]))
    if p.get('id'): c.anchors[p['id']] = tuple(p['at'])
    c.props.append(p)

def scatter_el(e, c):
    y = float(e.get('y', c.gy))
    for p in scatter(e.get('rules', []), int(e.get('seed', c.seed))): p['y'] = y; c.props.append(p)

BUILDERS = {'building': building, 'tower': building, 'platform': platform, 'district': district, 'street': street, 'prop': prop, 'scatter': scatter_el}

def expand(spec):
    """composed spec -> RoomSet spec (see the module docstring)"""
    c = _Ctx(spec)
    els = [e for e in spec.get('elements', []) if isinstance(e, dict)]
    order = sorted(range(len(els)), key=lambda i: 1 if els[i].get('kind') in ('district',) else 0)    # the skyline avoids the explicit buildings
    for i in order:
        e = els[i]; fn = BUILDERS.get(e.get('kind'))
        if fn is None: c.unknown.append(e.get('kind')); continue
        c.n += 1; fn(e, c)
    out = {'type': 'room', 'composed': True, 'outdoor': True, 'ground_y': c.gy, 'ground': spec.get('ground', 'asphalt'), 'textured_ground': True,
           'rooms': [], 'fog': .022, 'fill': .45, 'sky': spec.get('sky', 'night')}
    for k in ('sky', 'backdrop', 'clouds', 'weather', 'fog', 'fog_color', 'seed', 'stars', 'ambience', 'sun', 'fill', 'ambient', 'wet', 'ground_walkable', 'items'):
        if k in spec: out[k] = spec[k]
    out['props'] = c.props + list(spec.get('props', []))
    out['blocks'] = c.blocks + list(spec.get('blocks', []))
    out['zones'] = c.zones + list(spec.get('zones', []))
    out['walkable'] = c.walkable + list(spec.get('walkable', []))
    a = dict(c.anchors); a.update(spec.get('anchors') or {})
    if 'start' not in a: a['start'] = next(iter(c.anchors.values()), (0., 0.))
    out['anchors'] = a
    if c.unknown: out['_unknown_elements'] = c.unknown
    return out
