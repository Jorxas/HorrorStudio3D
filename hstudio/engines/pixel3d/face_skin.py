"""Pixel-art heads, « Minecraft skin » style (opt-in costume key `face_skin`): ONE painter for both styles.

The head is painted on a 16 x 16 grid per face of the head cube: front (face), sides (ears, hair, nape), back, top.
What moves is not baked into the base: the painter also returns SPRITES that are pasted over it every frame,
  * eyes  open / half / closed / wide, the iris shifted by the gaze (dx -1, 0, +1)
  * brows by inner and outer offset (-1, 0, +1 each: joy, pain, anger, surprise read from the expression)
  * mouth closed / smile / frown / open1 / open2 (teeth) / open3 (shout) / smile_open
PS1 composes them here (`texture`); VOXEL receives the same data in the contract (`b_costumes.py`) and composes
them in `b_costumes.js` from the face layer of the painter (blink, mo, ms, lx, bi, bo). Pure functions, no clock.

Grid: column 0 = left of the image when one looks at the face; rows from the top. Eyes on rows 6-7 (left eye
columns 3-5, right eye 10-12), brows around row 4, nose rows 8-9, mouth rows 10-14, jaw and chin rows 12-15.
"""
import functools, json
import numpy as np

N = 16
EYES = (3, 10)                        # first column of the left and right eye (3 wide)
BROWS = ((5, 4, 3, 2), (10, 11, 12, 13))   # inner -> outer
MOUTHS = ('closed', 'smile', 'frown', 'open1', 'open2', 'open3', 'smile_open')
EYE_STATES = ('open', 'half', 'closed', 'wide')

# per-role traits, read on the reference stills (kept to what a 16 x 16 skin can say)
TRAITS = {
    'angelica': dict(brow='thick', arch=True, iris=(46, 26, 16), lips='full', nose='wide', cheek=True, lash=True, hairline='curls_long', dimples=False),
    'eliza': dict(brow='medium', arch=True, iris=(92, 62, 38), lips='thin', lip=(196, 104, 112), nose='slim', cheek=True, lash=True, hairline='part'),
    'eliza_souvenir': dict(brow='medium', arch=True, iris=(92, 62, 38), lips='thin', lip=(196, 104, 112), nose='slim', cheek=True, lash=True, hairline='part'),
    'peggy': dict(brow='medium', arch=True, iris=(52, 32, 20), lips='full', nose='medium', cheek=True, lash=True, hairline='part_curls', dimples=True),
    'hamilton': dict(brow='thick', arch=False, iris=(54, 34, 20), lips='thin', nose='strong', cheek=True, jaw=True, hairline='peak', sideburn=True),
    'laurens': dict(brow='medium', arch=False, iris=(60, 38, 22), lips='medium', nose='medium', jaw=True, hairline='curls_short', dimples=True, sideburn=True),
    'lafayette': dict(brow='thick', arch=False, iris=(40, 24, 16), lips='full', nose='wide', jaw=True, hairline='puff', sideburn=True),
    'washington': dict(brow='medium', arch=False, iris=(40, 24, 16), lips='full', nose='wide', cheek=True, jaw=True, hairline='shaved'),
    'homme_chauve_rouge': dict(brow='medium', arch=False, iris=(38, 22, 14), lips='full', nose='wide', jaw=True, hairline='shaved', dimples=True),
}
HAIRLINE_OF = {'big_curls': 'curls_long', 'updo': 'part', 'side_ponytail': 'part', 'updo_curls': 'part_curls', 'queue': 'slick', 'short': 'slick',
               'shaved': 'shaved', 'puff': 'puff', 'afro_crown': 'puff'}


def _c(c): return tuple(int(max(0, min(255, round(v)))) for v in c[:3])
def _mul(c, k): return _c([v * k for v in c])
def _mix(a, b, k): return _c([a[i] + (b[i] - a[i]) * k for i in range(3)])


def traits(cs, name=None):
    """the face of a costume: the role's traits when the preset is a known role, else derived from skin and hair"""
    dark = sum(cs['skin']) < 420
    base = dict(brow='thin' if cs['type'] == 'gown' else 'medium', arch=cs['type'] == 'gown', iris=_mix(cs['hair_color'], (70, 46, 30), .5),
                lips='full' if dark else 'medium', nose='wide' if dark else 'medium', cheek=True, jaw=cs['type'] == 'coat', lash=cs['type'] == 'gown',
                hairline=HAIRLINE_OF.get(cs['hair'], 'slick'), dimples=False, sideburn=cs['type'] == 'coat')
    base.update(TRAITS.get(name or cs.get('preset') or '', {}))
    return base


def palette(cs, tr):
    s = cs['skin']; dark = sum(s) < 420; h = cs['hair_color']
    lip = tr.get('lip') or (_mix(s, (150, 50, 60), .38) if not dark else _mix(s, (70, 26, 30), .42))
    return dict(S=s, S1=_mul(s, .86), S2=_mul(s, .72), SH=_mix(s, (255, 236, 220), .07), H=h, H2=cs.get('hair2') or _mix(h, (120, 90, 64), .3), HD=_mul(h, .7),
                B=cs.get('brow') or _mul(h, .9), W=(226, 222, 214) if not dark else (214, 206, 196), I=_c(tr['iris']), P=_mul(tr['iris'], .45), K=_mul(h, .6) if sum(h) < 200 else (34, 26, 24),
                L1=_c(lip), L2=_mix(lip, (255, 214, 204), .14 if not dark else .2), MI=(56, 18, 22), T=(236, 232, 222), ST=_mix(s, h, .3), ST2=_mix(s, h, .5), G=(214, 172, 70))


def _grid(fill='S'): return [[fill] * N for _ in range(N)]


def _put(g, x, y, c):
    if 0 <= x < N and 0 <= y < N: g[y][x] = c


def _stubble(g, rows, cols):
    for y in rows:
        for x in cols: g[y][x] = 'ST2' if (x * 3 + y * 5) % 7 == 0 else 'ST'


def front(cs, tr):
    g = _grid()
    # light: a highlight on the forehead, the bridge of the nose and the cheekbones; shade on the jaw and under the chin
    for x in range(6, 10): _put(g, x, 3, 'SH')
    for y in range(5, 9): _put(g, 7, y, 'SH'); _put(g, 8, y, 'SH') if tr['nose'] != 'slim' else None
    if tr.get('cheek'):
        for x in (2, 3, 12, 13): _put(g, x, 8, 'SH')
        for x in (1, 2, 13, 14): _put(g, x, 9, 'S1')
    for y in range(8, 16): _put(g, 0, y, 'S1'); _put(g, 15, y, 'S1')
    if tr.get('jaw'):
        for y in range(11, 16): _put(g, 1, y, 'S1'); _put(g, 14, y, 'S1')
        _put(g, 0, 15, 'S2'); _put(g, 15, 15, 'S2')
    for x in range(3, 13): _put(g, x, 15, 'S1')
    for x in (3, 4, 5, 10, 11, 12): _put(g, x, 5, 'S1')           # eye sockets (the lash line of the sprites paints over)
    # nose
    n = tr['nose']
    if n == 'slim': _put(g, 7, 9, 'S1'); _put(g, 8, 9, 'SH')
    elif n == 'medium': _put(g, 6, 9, 'S1'); _put(g, 9, 9, 'S1'); _put(g, 7, 9, 'S1'); _put(g, 8, 9, 'S1')
    elif n == 'wide': _put(g, 6, 9, 'S2'); _put(g, 9, 9, 'S2'); _put(g, 7, 9, 'S1'); _put(g, 8, 9, 'S1'); _put(g, 5, 9, 'S1'); _put(g, 10, 9, 'S1')
    else:                                                          # strong: a long shadow on one side of the bridge, nostrils
        for y in range(6, 10): _put(g, 6, y, 'S1')
        _put(g, 6, 9, 'S2'); _put(g, 9, 9, 'S2'); _put(g, 7, 9, 'S1'); _put(g, 8, 9, 'S1')
    _put(g, 7, 10, 'S1') if n != 'slim' else None
    # hairline
    hl = tr['hairline']
    if hl in ('slick', 'peak'):
        for x in range(N): _put(g, x, 0, 'H')
        for x in list(range(0, 5)) + list(range(11, 16)): _put(g, x, 1, 'H')
        if hl == 'peak': _put(g, 7, 1, 'H'); _put(g, 8, 1, 'H')
        for x in (0, 1, 14, 15): _put(g, x, 2, 'H')
        for y in range(3, 9 if tr.get('sideburn') else 6): _put(g, 0, y, 'H'); _put(g, 15, y, 'H')
        _put(g, 2, 1, 'H2'); _put(g, 12, 0, 'H2')
    elif hl in ('part', 'part_curls'):
        for x in range(N): _put(g, x, 0, 'H')
        _put(g, 7, 0, 'HD')
        for x in list(range(0, 6)) + list(range(10, 16)): _put(g, x, 1, 'H')
        for x in (0, 1, 2, 3, 12, 13, 14, 15): _put(g, x, 2, 'H')
        for x in (0, 1, 14, 15): _put(g, x, 3, 'H')
        for y in range(4, 8): _put(g, 0, y, 'H'); _put(g, 15, y, 'H')
        for x, y in ((3, 1), (12, 1), (1, 3)): _put(g, x, y, 'H2')
        if hl == 'part_curls':
            for x, y in ((1, 2), (14, 2), (0, 8), (15, 8), (5, 1), (10, 1)): _put(g, x, y, 'H2')
    elif hl == 'curls_long':
        for y in (0, 1):
            for x in range(N): _put(g, x, y, 'H2' if (x + 2 * y) % 5 == 0 else 'H')
        for x in (0, 1, 2, 3, 12, 13, 14, 15): _put(g, x, 2, 'H')
        for y in range(3, 14):
            for x in (0, 1, 14, 15): _put(g, x, y, 'H2' if (x + y) % 4 == 0 else ('HD' if (x * 7 + y) % 5 == 0 else 'H'))
        for y in (3, 4, 10, 11, 12): _put(g, 2, y, 'H'); _put(g, 13, y, 'H')
    elif hl == 'curls_short':
        for x in range(N): _put(g, x, 0, 'H2' if x % 4 == 1 else 'H')
        for x in list(range(0, 5)) + list(range(11, 16)): _put(g, x, 1, 'H')
        for y in range(2, 7): _put(g, 0, y, 'H'); _put(g, 15, y, 'H')
    elif hl == 'puff':
        for x in range(N): _put(g, x, 0, 'H')
        for x in list(range(0, 4)) + list(range(12, 16)): _put(g, x, 1, 'H')
        for y in range(2, 8): _put(g, 0, y, 'H'); _put(g, 15, y, 'H')
        _put(g, 5, 0, 'H2'); _put(g, 11, 0, 'H2')
    elif hl == 'shaved':
        _stubble(g, (0,), range(1, 15))
        for y in (1, 2, 3, 4): _put(g, 0, y, 'ST'); _put(g, 15, y, 'ST')
    # beard (the mouth sprite is pasted over it)
    bd = cs.get('beard')
    if bd == 'goatee':
        for x in range(5, 11): _put(g, x, 10, 'H')                # moustache
        for y in (11, 12): _put(g, 5, y, 'H'); _put(g, 10, y, 'H')  # down to the chin
        for y in (13, 14):
            for x in range(6, 10): _put(g, x, y, 'H')
        for x in (7, 8): _put(g, x, 15, 'H')
        _put(g, 6, 13, 'HD'); _put(g, 9, 14, 'H2')
    elif bd == 'short_full':
        for x in range(4, 12): _put(g, x, 10, 'H')
        for y in range(9, 16):
            for x in (0, 1, 2, 13, 14, 15): _put(g, x, y, 'H' if (x + y) % 3 else 'HD')
        for y in range(12, 16):
            for x in range(2, 14): _put(g, x, y, 'H' if (x * 5 + y) % 4 else 'HD')
    elif bd == 'mustache':
        for x in range(5, 11): _put(g, x, 10, 'H')
    elif bd == 'stubble':
        _stubble(g, range(11, 16), range(1, 15))
    return g


def side(cs, tr):
    """the side of the head, front edge at column 0: hair above, ear in the middle, nape at the back"""
    g = _grid(); hl = tr['hairline']; shaved = hl == 'shaved'
    for y in range(0, 6):
        for x in range(N):
            g[y][x] = 'H'
    for y in range(6, 12):
        for x in range(9, N): g[y][x] = 'H'
    if shaved: _stubble(g, range(0, 12), range(N)); [_put(g, x, y, 'S') for y in range(6, 12) for x in range(0, 9)]
    if tr.get('sideburn') and not shaved:
        for y in range(6, 10): _put(g, 0, y, 'H'); _put(g, 1, y, 'H')
    for y in range(6, 11):                                         # ear
        _put(g, 6, y, 'S1'); _put(g, 8, y, 'S1')
    for y in (6, 10): _put(g, 7, y, 'S1')
    for y in (7, 8, 9): _put(g, 7, y, 'S2')
    for y in range(12, 16):
        for x in range(0, 4): _put(g, x, y, 'S1')
        for x in range(11, 16): _put(g, x, y, 'S1')
    if cs.get('earrings'): _put(g, 7, 11, 'G'); _put(g, 7, 12, 'G')
    return g


def back(cs, tr):
    g = _grid('H')
    if tr['hairline'] == 'shaved':
        _stubble(g, range(0, 11), range(N))
        for x in range(N): _put(g, x, 11, 'S2' if x % 3 else 'S1')
        for y in range(12, 16):
            for x in range(N): _put(g, x, y, 'S1' if x in (0, 1, 14, 15) else 'S')
    else:
        for y in range(12, 16):
            for x in range(N): _put(g, x, y, 'S1')
        for x in range(N): _put(g, x, 11, 'HD')
    return g


def top(cs, tr):
    g = _grid('H')
    if tr['hairline'] == 'shaved':
        _stubble(g, range(N), range(N))
        for x, y in ((9, 4), (10, 4), (9, 5)): _put(g, x, y, 'SH')
    return g


def eye_sprites(tr):
    """{state_dx: [(x, y, colour)]} for both eyes; dx = gaze -1 / 0 / +1 (to the right of the image). An eye is 3 wide: the white
    outside, a 2-wide iris inside (towards the nose) when looking ahead; both irises slide together with the gaze"""
    out = {}
    for st in EYE_STATES:
        for dx in (-1, 0, 1):
            px = []
            for x0 in EYES:
                left = x0 == EYES[0]
                off = (1 if left else 0) if dx == 0 else (0 if dx < 0 else 1)
                iris = (x0 + off, x0 + off + 1); pupil = iris[1] if left else iris[0]
                if st == 'closed':
                    px += [(x0 + i, 6, 'S1') for i in range(3)] + [(x0 + i, 7, 'K' if tr.get('lash') else 'S2') for i in range(3)]
                    continue
                for i in range(3):
                    x = x0 + i
                    top = 'S1' if st == 'half' else ('I' if x in iris else 'W')
                    bot = ('P' if x == pupil else 'I') if x in iris else 'W'
                    px += [(x, 6, top), (x, 7, bot)]
                if st == 'wide': px += [(x0 + i, 5, 'W') for i in range(3)]
                elif tr.get('lash'):
                    px += [(x0 + i, 5, 'K') for i in range(3)] + [(x0 - 1 if left else x0 + 3, 5, 'K')]
            out[f'{st}_{dx}'] = px
    return out


def brow_sprites(tr):
    """{"di_do": pixels}: di / do = offset of the inner / outer end (-1 up, +1 down)"""
    out = {}; two = {'thin': (), 'medium': (2,), 'thick': (1, 2)}[tr['brow']]      # pixels of the brow drawn two rows high (0 = inner end)
    for di in (-1, 0, 1):
        for do in (-1, 0, 1):
            px = []
            for cols in BROWS:
                for k, x in enumerate(cols):
                    y = 4 + round(di + (do - di) * k / 3)
                    if tr.get('arch') and k == 2: y -= 1                  # arched: the peak on the outer third, both ends lower
                    y = max(2, min(5, y)); px.append((x, y, 'B'))
                    if k in two and y + 1 <= 5: px.append((x, y + 1, 'B'))
            out[f'{di}_{do}'] = px
    return out


def mouth_sprites(tr):
    lips = tr['lips']; up = range(5, 11) if lips != 'thin' else range(6, 10); lo = range(5, 11) if lips == 'full' else range(6, 10)
    def closed(px):
        px += [(x, 11, 'L1') for x in up] + [(x, 12, 'L2') for x in lo]
        if lips == 'full': px += [(x, 13, 'S1') for x in range(6, 10)]
        return px
    o = {}
    o['closed'] = closed([])
    sm = [(4, 10, 'L1'), (11, 10, 'L1')] + [(x, 11, 'L1') for x in range(5, 11)] + [(x, 12, 'L2') for x in range(6, 10)]
    if tr.get('dimples'): sm += [(3, 11, 'S1'), (12, 11, 'S1')]
    o['smile'] = sm
    o['frown'] = [(x, 11, 'L1') for x in range(6, 10)] + [(5, 12, 'L1'), (10, 12, 'L1')] + [(x, 12, 'L2') for x in range(6, 10)]
    side = lambda rows: [(5, y, 'L1') for y in rows] + [(10, y, 'L1') for y in rows]
    o['open1'] = [(x, 11, 'L1') for x in range(5, 11)] + [(x, 12, 'MI') for x in range(6, 10)] + side((12,)) + [(x, 13, 'L2') for x in range(6, 10)]
    o['open2'] = [(x, 11, 'L1') for x in range(5, 11)] + [(x, 12, 'T') for x in range(6, 10)] + [(x, 13, 'MI') for x in range(6, 10)] + side((12, 13)) + [(x, 14, 'L2') for x in range(6, 10)]
    o['open3'] = [(x, 11, 'L1') for x in range(5, 11)] + [(x, 12, 'T') for x in range(6, 10)] + [(x, y, 'MI') for x in range(6, 10) for y in (13, 14)] + side((12, 13, 14)) + [(x, 15, 'L2') for x in range(6, 10)]
    o['smile_open'] = [(4, 10, 'L1'), (11, 10, 'L1')] + [(x, 11, 'L1') for x in range(5, 11)] + [(x, 12, 'T') for x in range(5, 11)] + [(x, 13, 'MI') for x in range(6, 10)] + [(x, 14, 'L2') for x in range(6, 10)]
    return o


@functools.lru_cache(maxsize=128)
def _skin_json(raw):
    d = json.loads(raw); cs = d['cs']
    for k, v in list(cs.items()):
        if isinstance(v, list) and v and isinstance(v[0], (int, float)): cs[k] = tuple(v)
    tr = traits(cs, d['name']); tr.update(d.get('over') or {})
    pal = palette(cs, tr)
    grids = dict(front=front(cs, tr), side=side(cs, tr), back=back(cs, tr), top=top(cs, tr))
    if d.get('grid'):                                             # an explicit 16 x 16 grid written in the cast: letters -> palette names
        rows = d['grid']; legend = d.get('legend') or {}
        for y, row in enumerate(rows[:N]):
            for x, ch in enumerate(row[:N]):
                if ch in legend: grids['front'][y][x] = legend[ch]
    for k, v in (d.get('colors') or {}).items(): pal[k] = _c(v)
    return dict(pal=pal, grids=grids, eyes=eye_sprites(tr), brows=brow_sprites(tr), mouth=mouth_sprites(tr), traits=tr)


def _raw(cs):
    fs = cs.get('face_skin')
    name = fs if isinstance(fs, str) else (cs.get('preset') or '')
    d = {'cs': {k: list(v) if isinstance(v, tuple) else v for k, v in cs.items() if k in ('skin', 'hair_color', 'hair2', 'brow', 'beard', 'earrings', 'type', 'hair', 'preset')},
         'name': (fs.get('like') or cs.get('preset') or '') if isinstance(fs, dict) else name}
    if isinstance(fs, dict):
        d['over'] = {k: v for k, v in fs.items() if k in ('brow', 'arch', 'iris', 'lips', 'lip', 'nose', 'cheek', 'jaw', 'lash', 'hairline', 'dimples', 'sideburn')}
        d['grid'] = fs.get('grid'); d['legend'] = fs.get('legend'); d['colors'] = fs.get('colors')
    return json.dumps(d, sort_keys=True)


def skin_of(cs):
    """costume (costumes.spec_of) -> the painted head, or None when the costume has no `face_skin`"""
    if not cs or not cs.get('face_skin'): return None
    return _skin_json(_raw(cs))


# ------------------------------------------------------------------ states (PS1 reads the expression name, VOXEL the face layer)
PS1_STATES = {   # expression -> (brow di, brow do, mouth, eyes)
    'happy': (0, 0, 'smile', 'open'), 'grin': (0, -1, 'smile_open', 'open'), 'smirk': (0, 0, 'smile', 'half'), 'sad': (-1, 1, 'frown', 'half'),
    'crying': (-1, 1, 'open1', 'closed'), 'scared': (-1, -1, 'open1', 'wide'), 'shocked': (-1, -1, 'open2', 'wide'), 'surprised': (-1, -1, 'open1', 'wide'),
    'nervous': (-1, 0, 'frown', 'open'), 'pain': (-1, 1, 'open1', 'closed'), 'evil': (1, -1, 'smile', 'half'), 'angry': (1, -1, 'frown', 'open'),
    'closed': (0, 0, 'closed', 'closed'), 'sleeping': (0, 0, 'closed', 'closed'), 'talk': (0, 0, 'open1', 'open')}


def ps1_state(sample, mouth_env):
    kind = sample.get('face', 'neutral'); di, do, mouth, eyes = PS1_STATES.get(kind, (0, 0, 'closed', 'open'))
    if sample.get('talking') and mouth in ('closed', 'smile', 'frown'):
        m = float(mouth_env or 0.); mouth = 'closed' if m < .15 else 'open1' if m < .5 else 'open2'
    if sample.get('blink') and eyes != 'closed': eyes = 'closed'
    return di, do, mouth, eyes, 0


def compose(skin, di, do, mouth, eyes, dx=0):
    """the front face for one state -> 16 x 16 grid of palette names"""
    g = [row[:] for row in skin['grids']['front']]
    for (x, y, c) in skin['brows'][f'{di}_{do}']: g[y][x] = c
    for (x, y, c) in skin['eyes'][f'{eyes}_{dx}']: g[y][x] = c
    for (x, y, c) in skin['mouth'][mouth]: g[y][x] = c
    return g


@functools.lru_cache(maxsize=4096)
def _tex(raw, state):
    skin = _skin_json(raw)
    if state[0] == 'grid': g = skin['grids'][state[1]]
    else: g = compose(skin, *state)
    pal = skin['pal']; a = np.zeros((N, N, 4), np.uint8)
    for y in range(N):
        for x in range(N): a[y, x, :3] = pal[g[y][x]]; a[y, x, 3] = 255
    return a


def textures(cs, sample, mouth_env=0.):
    """PS1: {'+z': face, '-x' / '+x': sides, '-z': back, '+y': top} as RGBA arrays (r3d box textures), or None"""
    if not cs or not cs.get('face_skin'): return None
    raw = _raw(cs); st = ps1_state(sample, mouth_env); sd = _tex(raw, ('grid', 'side'))
    return {'+z': _tex(raw, st), '-x': sd, '+x': np.ascontiguousarray(sd[:, ::-1]), '-z': _tex(raw, ('grid', 'back')), '+y': _tex(raw, ('grid', 'top'))}


def to_contract(skin):
    """the painted head for the VOXEL painter: palette as hex, grids as strings of palette indices (base 36), sprites as [x, y, i]"""
    names = list(skin['pal']); ix = {n: i for i, n in enumerate(names)}
    enc = lambda g: [''.join('0123456789abcdefghijklmnopqrstuvwxyz'[ix[c]] for c in row) for row in g]
    sp = lambda d: {k: [[x, y, ix[c]] for (x, y, c) in v] for k, v in d.items()}
    return dict(pal=['#%02x%02x%02x' % skin['pal'][n] for n in names], grids={k: enc(v) for k, v in skin['grids'].items()},
                eyes=sp(skin['eyes']), brows=sp(skin['brows']), mouth=sp(skin['mouth']))
