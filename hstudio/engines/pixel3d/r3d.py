"""Tiny numpy ray-caster for axis-aligned boxes -> low-res pixel-art frames (PIXEL 3D style), v2:
procedural materials, shadow rays, cheap ambient occlusion, glow."""
import math, numpy as np
BAYER = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], np.float32) + .5) / 16
RW = RH = ASPECT = FOV_K = None
_xn = _yn = _noise = BAYER_T = None
_CFG = None

BASE = {'9:16': (216, 384, 1.0), '16:9': (384, 216, .72)}

def configure(aspect='9:16', scale=1):
    """Native raster: 216x384 for shorts (x5 -> 1080x1920), 384x216 for long videos (x5 -> 1920x1080).
    In 16:9 the vertical field of view is narrowed (FOV_K) so subjects keep the framing of the vertical cut
    while the camera shows more of the set on the sides.

    `scale` multiplies that native raster (engines/pixel3d/finish.py, opt-in episode key "finish"). It is the
    one knob that buys anti-aliasing, finer shadows and finer procedural materials, because every one of
    those is evaluated PER RAY: at scale 1 the whole image is 82 944 rays blown up x5 with NEAREST, and no
    amount of grading hides that. It costs what it says -- the ray count grows as the square. `scale=1` is
    the shipped raster to the integer, and every caller that never passes `scale` keeps it."""
    bw, bh, fk = BASE.get(aspect, BASE['16:9'])
    n = max(1, int(round(float(scale or 1))))
    set_raster(bw * n, bh * n, fk)


def set_raster(rw, rh, fov_k):
    """THE one place that sizes the raster and rebuilds the per-pixel tables, and the one that remembers what
    it did. Idempotent: those tables cost real time and `render_lowres` asks on every frame. Anything that
    changes the raster behind this function's back (a tool writing r3d.RW itself) leaves the registry lying,
    so there is no second place -- tools/catalogue.py goes through here too."""
    global RW, RH, ASPECT, FOV_K, _xn, _yn, _noise, BAYER_T, _CFG
    rw, rh = int(rw), int(rh)
    if _CFG == (rw, rh, fov_k): return
    RW, RH, FOV_K = rw, rh, fov_k
    ASPECT = RW / RH
    _CFG = (RW, RH, FOV_K)
    py, px = np.mgrid[0:RH, 0:RW].astype(np.float32)
    _xn = ((px + .5) / RW * 2 - 1).ravel(); _yn = (1 - (py + .5) / RH * 2).ravel()
    _noise = np.random.default_rng(3).random(RW * RH).astype(np.float32)
    BAYER_T = np.tile(BAYER, (RH // 4 + 1, RW // 4 + 1))[:RH, :RW]

configure('9:16')
FACES = {'+x': 1, '-x': 0, '+y': 3, '-y': 2, '+z': 5, '-z': 4}   # key -> axis*2+(sign>0)
M_NONE, M_WOODV, M_PLASTER, M_METAL, M_CEIL, M_DOOR, M_CARD, M_FABRIC, M_CLEAN, M_CEIL_CLEAN = range(10)

class Box:
    __slots__ = ('lo', 'hi', 'col', 'emis', 'refl', 'tex', 'hidden', 'dissolve', 'grain', 'texemis', 'mat', 'cast', 'noref', 'inst', 'wlo', 'whi')
    def __init__(s, lo, hi, col, emis=0., refl=0., tex=None, hidden=False, dissolve=0., grain=.07, texemis=0., mat=0, cast=None, noref=False):
        s.lo = np.array(lo, np.float32); s.hi = np.array(hi, np.float32)
        s.col = np.array(col, np.float32) / 255.; s.emis = emis; s.refl = refl
        s.tex = {FACES[k]: v for k, v in (tex or {}).items()}
        s.hidden = hidden; s.dissolve = dissolve; s.grain = grain; s.texemis = texemis; s.mat = mat
        s.cast = (emis == 0) if cast is None else cast
        s.noref = noref
        s.inst = None                      # Instance: lo/hi are then local to a rotated frame (see orient)

class Instance:
    """a rigid frame shared by boxes: world = R @ local + piv (characters turning, doors on hinges)"""
    __slots__ = ('R', 'piv')
    def __init__(s, yaw=0., piv=(0., 0., 0.), R=None):
        if R is None:
            c, n = math.cos(yaw), math.sin(yaw); R = [[c, 0, n], [0, 1, 0], [-n, 0, c]]
        s.R = np.asarray(R, np.float32); s.piv = np.asarray(piv, np.float32)

def yaw_matrix(yaw):
    c, n = math.cos(yaw), math.sin(yaw); return np.array([[c, 0, n], [0, 1, 0], [-n, 0, c]], np.float32)

def orient(boxes, yaw, piv, R=None):
    """turn boxes built around the local origin by yaw (radians, +z towards +x) or by a rotation matrix R, then move them to piv"""
    ins = Instance(yaw, piv, R)
    for b in boxes:
        b.inst = ins
        cs = np.array([[x, y, z] for x in (b.lo[0], b.hi[0]) for y in (b.lo[1], b.hi[1]) for z in (b.lo[2], b.hi[2])], np.float32) @ ins.R.T + ins.piv
        b.wlo = cs.min(0); b.whi = cs.max(0)
    return boxes

def wbounds(b): return (b.lo, b.hi) if b.inst is None else (b.wlo, b.whi)

def B(lo, size, col, **kw):
    return Box(lo, [lo[i] + size[i] for i in range(3)], col, **kw)
def C(center, size, col, **kw):   # centered box
    return Box([center[i] - size[i] / 2 for i in range(3)], [center[i] + size[i] / 2 for i in range(3)], col, **kw)

def cam_dirs(yaw, pitch, roll, fov):
    th = math.tan(math.radians(fov) / 2) * FOV_K
    x = _xn * th * ASPECT; y = _yn * th; z = np.ones_like(x)
    cr, sr = math.cos(roll), math.sin(roll); x, y = x * cr - y * sr, x * sr + y * cr
    cp, sp = math.cos(pitch), math.sin(pitch); y, z = y * cp + z * sp, -y * sp + z * cp
    cy, sy = math.cos(yaw), math.sin(yaw); x, z = x * cy + z * sy, -x * sy + z * cy
    d = np.stack([x, y, z], 1); return d / np.linalg.norm(d, axis=1, keepdims=True)

def project(pos, yaw, pitch, roll, fov, P):
    """world point -> normalised image coordinates (u, v in -1..1, right / up) and depth along the view (inverse of cam_dirs)"""
    x, y, z = (float(P[i]) - float(pos[i]) for i in range(3))
    cy, sy = math.cos(yaw), math.sin(yaw); x, z = x * cy - z * sy, x * sy + z * cy
    cp, sp = math.cos(pitch), math.sin(pitch); y, z = y * cp - z * sp, y * sp + z * cp
    cr, sr = math.cos(roll), math.sin(roll); x, y = x * cr + y * sr, -x * sr + y * cr
    th = math.tan(math.radians(fov) / 2) * FOV_K
    if z < 1e-4: return 9., 9., z
    return x / (z * th * ASPECT), y / (z * th), z

T_FAR, CHUNK = 250., 256
_TILES = {}
def _ray_groups(N):
    """groups of rays that are close on screen: 16x16 tiles for a full primary raster, runs of 256 otherwise"""
    if N == RW * RH:
        key = (RW, RH)
        if key not in _TILES:
            iy, ix = np.divmod(np.arange(N), RW); t = (iy // 16) * ((RW + 15) // 16) + ix // 16
            order = np.argsort(t, kind='stable'); cuts = np.nonzero(np.diff(t[order]))[0] + 1
            _TILES[key] = np.split(order, cuts)
        return _TILES[key]
    return [np.arange(a, min(N, a + CHUNK)) for a in range(0, N, CHUNK)]

def trace(O, D, boxes, floor_y=0., ceil_y=None, primary=True, noise=None, tmax=None, shadow=False):
    N = D.shape[0]; O = np.broadcast_to(np.asarray(O, np.float32), (N, 3))
    inv = 1 / np.where(np.abs(D) < 1e-6, 1e-6, D)
    tb = np.full(N, np.inf, np.float32) if tmax is None else tmax.astype(np.float32).copy()
    ib = np.full(N, -1 if not shadow else -5, np.int32)
    dy = D[:, 1]
    with np.errstate(divide='ignore', invalid='ignore'):
        tfl = np.where(dy < -1e-5, (floor_y - O[:, 1]) / dy, np.inf)
        tce = np.where(dy > 1e-5, ((ceil_y if ceil_y is not None else 1e9) - O[:, 1]) / dy, np.inf)
    act = [i for i, b in enumerate(boxes) if not ((b.hidden and (primary or shadow)) or (b.noref and not primary and not shadow) or (shadow and not b.cast))]
    # acceleration (exact): a box is only tested by the groups of rays whose segment can reach it. A segment stops at
    # its tmax (shadow rays) or at the floor / ceiling (anything farther is hidden by them), and at T_FAR.
    sel = None; local = {}
    if N >= 4 * CHUNK and len(act) > 6:
        tl = np.minimum(tb, T_FAR)
        if not shadow:
            tl = np.where(tfl > 1e-3, np.minimum(tl, tfl), tl); tl = np.where(tce > 1e-3, np.minimum(tl, tce), tl)
        E = O + D * tl[:, None]; a0 = np.minimum(O, E); a1 = np.maximum(O, E)
        groups = _ray_groups(N)
        if groups is not None:
            glo = np.stack([a0[g].min(0) for g in groups]); ghi = np.stack([a1[g].max(0) for g in groups])
            BL = np.stack([wbounds(boxes[i])[0] for i in act]); BH = np.stack([wbounds(boxes[i])[1] for i in act])
            ov = np.all((glo[:, None, :] <= BH[None] + 1e-4) & (ghi[:, None, :] >= BL[None] - 1e-4), axis=2)
            sel = (groups, ov)
    for j, i in enumerate(act):
        b = boxes[i]
        if sel is None: idx = None
        else:
            cs = np.nonzero(sel[1][:, j])[0]
            if len(cs) == 0: continue
            idx = None if len(cs) > .6 * len(sel[0]) else np.concatenate([sel[0][c] for c in cs])
        Oi = O if idx is None else O[idx]; Ii = inv if idx is None else inv[idx]; tbi = tb if idx is None else tb[idx]
        if b.inst is not None:              # rays into the box's local frame (rotation keeps the ray parameter t)
            ins = b.inst
            if idx is None:
                if ins not in local: Dl = D @ ins.R; local[ins] = ((O - ins.piv) @ ins.R, 1 / np.where(np.abs(Dl) < 1e-6, 1e-6, Dl))
                Oi, Ii = local[ins]
            else:
                Dl = D[idx] @ ins.R; Oi = (O[idx] - ins.piv) @ ins.R; Ii = 1 / np.where(np.abs(Dl) < 1e-6, 1e-6, Dl)
        tn = None; tf = None
        for k in range(3):
            a = (b.lo[k] - Oi[:, k]) * Ii[:, k]; c = (b.hi[k] - Oi[:, k]) * Ii[:, k]
            lo_, hi_ = np.minimum(a, c), np.maximum(a, c)
            tn = lo_ if tn is None else np.maximum(tn, lo_); tf = hi_ if tf is None else np.minimum(tf, hi_)
        hit = (tf >= tn) & (tn > 1e-3) & (tn < tbi)
        if b.dissolve > 0 and noise is not None: hit &= (noise if idx is None else noise[idx]) >= b.dissolve
        if idx is None: tb[hit] = tn[hit]; ib[hit] = i
        else: w = idx[hit]; tb[w] = tn[hit]; ib[w] = i
    if shadow: return ib >= 0
    h = (tfl > 1e-3) & (tfl < tb); tb[h] = tfl[h]; ib[h] = -1
    h = (tce > 1e-3) & (tce < tb); tb[h] = tce[h]; ib[h] = -2
    return tb, ib

# ------------------------------ noise ------------------------------
def h2(ix, iy, seed):
    h = (ix.astype(np.int64) * 73856093) ^ (iy.astype(np.int64) * 19349663) ^ (seed * 83492791)
    h = (h ^ (h >> 13)) * 1274126177
    return ((h >> 7) & 0xffff).astype(np.float32) / 65535.
def vnoise2(x, y, seed=0):
    ix = np.floor(x); iy = np.floor(y); fx = x - ix; fy = y - iy
    fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy)
    a = h2(ix, iy, seed); b = h2(ix + 1, iy, seed); c = h2(ix, iy + 1, seed); d = h2(ix + 1, iy + 1, seed)
    return (a + (b - a) * fx) * (1 - fy) + (c + (d - c) * fx) * fy
def fbm(x, y, seed=0, oct=3):
    s = 0; a = .5; f = 1.
    for o in range(oct): s = s + a * vnoise2(x * f, y * f, seed + o); f *= 2.1; a *= .5
    return s / (1 - .5 ** oct)
def _hash3(p, cell):
    q = np.floor(p / cell).astype(np.int64)
    h = (q[:, 0] * 73856093) ^ (q[:, 1] * 19349663) ^ (q[:, 2] * 83492791)
    return ((h & 0xffff) / 65535.).astype(np.float32)

def material(mat, p, ax, col):
    """returns albedo (n,3) for procedural material"""
    u = np.where(ax == 0, p[:, 2], p[:, 0]); v = np.where(ax == 1, p[:, 2], p[:, 1])
    if mat == M_WOODV:
        g = .55 * vnoise2(u * 9, v * .25, 1) + .3 * vnoise2(u * 37 + 3, v * .6, 2) + .15 * vnoise2(u * 90, v * 2., 3)
        f = (.62 + .62 * g) * (.72 + .28 * np.clip(v / .7, 0, 1))
        return col[None] * f[:, None]
    if mat == M_PLASTER:
        bl = fbm(u * 1.1, v * 1.1, 5, 3); st = np.clip((bl - .52) * 3.2, 0, 1)
        drip = vnoise2(u * 14, v * .3, 7) * np.clip(1.2 - v / 2.4, 0, 1)
        f = (.82 + .3 * vnoise2(u * 6, v * 6, 9)) * (1 - .45 * st) * (1 - .25 * np.clip((drip - .55) * 4, 0, 1))
        tint = np.stack([1 + .0 * st, 1 - .08 * st, 1 - .18 * st], 1)
        return col[None] * f[:, None] * tint
    if mat == M_METAL:
        f = .82 + .2 * vnoise2(u * 2, v * 70, 4) + .08 * vnoise2(u * 25, v * 5, 6)
        return col[None] * f[:, None]
    if mat == M_CEIL:
        fu = (p[:, 0] / .6) % 1; fz = (p[:, 2] / .6) % 1
        line = (fu < .045) | (fz < .045)
        f = (.8 + .25 * fbm(p[:, 0] * 2, p[:, 2] * 2, 11, 2)) * np.where(line, .45, 1.)
        st = np.clip((fbm(p[:, 0] * .7, p[:, 2] * .7, 13, 2) - .6) * 4, 0, 1)
        return col[None] * (f * (1 - .4 * st))[:, None] * np.stack([np.ones_like(st), 1 - .1 * st, 1 - .25 * st], 1)
    if mat == M_DOOR:
        g = .7 + .45 * vnoise2(u * 30, v * .4, 21)
        return col[None] * g[:, None]
    if mat == M_CARD:
        g = .85 + .2 * vnoise2(u * 12, v * 12, 31)
        return col[None] * g[:, None]
    if mat == M_FABRIC:
        g = .88 + .16 * vnoise2(u * 40, v * 40, 41)
        return col[None] * g[:, None]
    if mat == M_CLEAN:                       # painted wall without stains (non-horror rooms)
        g = .94 + .06 * vnoise2(u * 3, v * 3, 43) + .03 * vnoise2(u * 30, v * 30, 44)
        return col[None] * g[:, None]
    if mat == M_CEIL_CLEAN:
        fu = (p[:, 0] / .6) % 1; fz = (p[:, 2] / .6) % 1; line = (fu < .03) | (fz < .03)
        return col[None] * np.where(line, .7, .97)[:, None]
    return np.broadcast_to(col[None], (p.shape[0], 3))

class Scene:
    def __init__(s): s.boxes = []; s.lights = []; s.floor_fn = None; s.ceil_y = 2.7; s.ambient = (.05, .05, .07); s.fog = (.02, .03, .04); s.fogk = .06; s.ao_fn = None; s.sky_fn = None; s.zone_fn = None
    def add(s, *bs): s.boxes.extend(bs); return s

def shade(sc, boxes, O, D, t, ib, lights, shadows=True):
    N = D.shape[0]; O = np.broadcast_to(np.asarray(O, np.float32), (N, 3))
    P = O + D * np.where(np.isfinite(t), t, 0)[:, None]
    nrm = np.zeros((N, 3), np.float32); alb = np.zeros((N, 3), np.float32); em = np.zeros(N, np.float32)
    refl = np.zeros(N, np.float32); grain = np.full(N, .07, np.float32)
    m = ib == -1
    if m.any():
        nrm[m] = (0, 1, 0); a, r = sc.floor_fn(P[m]); alb[m] = a; refl[m] = r
    m = ib == -2
    if m.any():
        nrm[m] = (0, -1, 0); alb[m] = material(M_CEIL, P[m], np.ones(m.sum(), int), np.array((.42, .42, .40), np.float32)); grain[m] = .06
    for i in np.unique(ib[ib >= 0]):
        b = boxes[i]; m = ib == i; p = P[m]
        if b.inst is not None: p = (p - b.inst.piv) @ b.inst.R          # local hit point: materials and textures follow the box
        dd = np.concatenate([np.abs(p - b.lo), np.abs(p - b.hi)], 1)
        f = dd.argmin(1); ax = f % 3; sgn = np.where(f >= 3, 1., -1.).astype(np.float32)
        n = np.zeros((p.shape[0], 3), np.float32); n[np.arange(p.shape[0]), ax] = sgn
        nrm[m] = n if b.inst is None else n @ b.inst.R.T
        alb[m] = material(b.mat, p, ax, b.col) if b.mat else b.col
        em[m] = b.emis; refl[m] = b.refl; grain[m] = b.grain
        if b.tex:
            fid = ax * 2 + (sgn > 0); idx = np.nonzero(m)[0]; sz = b.hi - b.lo
            for key, tx in b.tex.items():
                sel = fid == key
                if not sel.any(): continue
                pp = p[sel]; a_ = key // 2
                if a_ == 0: uu = (pp[:, 2] - b.lo[2]) / max(sz[2], 1e-6); vv = (pp[:, 1] - b.lo[1]) / max(sz[1], 1e-6)
                elif a_ == 1: uu = (pp[:, 0] - b.lo[0]) / max(sz[0], 1e-6); vv = (pp[:, 2] - b.lo[2]) / max(sz[2], 1e-6)
                else: uu = (pp[:, 0] - b.lo[0]) / max(sz[0], 1e-6); vv = (pp[:, 1] - b.lo[1]) / max(sz[1], 1e-6)
                th, tw = tx.shape[:2]
                if key == 5: uu = 1 - uu
                if key == 0: uu = 1 - uu
                xi = np.clip((uu * tw).astype(int), 0, tw - 1); yi = np.clip(((1 - vv) * th).astype(int), 0, th - 1)
                if a_ == 1: yi = np.clip((vv * th).astype(int), 0, th - 1)
                tv = tx[yi, xi].astype(np.float32) / 255.
                al = tv[:, 3:4]; tgt = idx[sel]
                alb[tgt] = alb[tgt] * (1 - al) + tv[:, :3] * al
                # a texture may carry a FIFTH channel: the emission mask. Without it the alpha drives the
                # glow, which is what every shipped texture expects -- but it means an opaque window FRAME
                # glows exactly like the lit glass beside it. A facade that draws frames, sills and doors
                # (engines/pixel3d/facades.py) needs to say which texels are glass and which are stone.
                if b.texemis:
                    e_ = tv[:, 4] if tx.shape[2] > 4 else al[:, 0]
                    em[tgt] = np.maximum(em[tgt], e_ * b.texemis)
    g = _hash3(P, .1) - .5
    alb = alb * (1 + g[:, None] * grain[:, None] * 2)
    # ambient occlusion (cheap, scene supplied)
    ao = sc.ao_fn(P, nrm, ib) if sc.ao_fn is not None else np.ones(N, np.float32)
    col = np.tile(np.array(sc.ambient, np.float32), (N, 1)) * ao[:, None]
    zone = sc.zone_fn(P) if getattr(sc, 'zone_fn', None) is not None else None       # premier moteur : zones de lumière (dehors / boutique / réserve)
    for L in lights:
        lp, lc, li, lr = L[:4]; sh_ = len(L) > 4 and L[4] and shadows
        v = np.asarray(lp, np.float32) - P; d2 = (v * v).sum(1); d = np.sqrt(d2) + 1e-4
        lam = np.clip((v * nrm).sum(1) / d, 0, 1)
        c = lam * li / (1 + d2 / (lr * lr))
        spot = L[5] if len(L) > 5 else None; zw = L[6] if len(L) > 6 else None
        if spot is not None:       # projecteur : (direction, cos intérieur, cos extérieur) — phares, lampadaire, lampe torche
            dv = np.asarray(spot[0], np.float32); cs = -(v * dv).sum(1) / d
            c = c * np.clip((cs - spot[2]) / (spot[1] - spot[2]), 0, 1) ** 2
        if zw is not None and zone is not None: c = c * np.asarray(zw, np.float32)[zone]
        if sh_:
            msk = (c > .015) & np.isfinite(t)
            if msk.any():
                idx = np.nonzero(msk)[0]
                Ls = v[idx] / d[idx, None]
                occ = trace(P[idx] + nrm[idx] * 4e-3, Ls, sc.boxes, primary=False, tmax=d[idx] - .05, shadow=True)
                c[idx[occ]] *= .12
        col += c[:, None] * np.asarray(lc, np.float32) * (.55 + .45 * ao[:, None])
    rgb = alb * col + alb * em[:, None] * 1.4
    fogk = np.exp(-np.where(np.isfinite(t), t, 80) * sc.fogk)[:, None]
    rgb = rgb * fogk + np.asarray(sc.fog, np.float32) * (1 - fogk)
    if getattr(sc, 'sky_fn', None) is not None:          # painted sky for rays that hit nothing
        miss = ~np.isfinite(t)
        if miss.any(): rgb[miss] = sc.sky_fn(D[miss]); refl[miss] = 0
    return rgb, refl, nrm, P

def cull(boxes, pos, yaw, pitch, fov):
    f = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)], np.float32)
    out = []
    for b in boxes:
        lo, hi = wbounds(b); c = (lo + hi) / 2 - pos; r = np.linalg.norm(hi - lo) / 2
        if (c * f).sum() > -r - .05: out.append(b)
    return out

LAST_AUX = None
def render(sc, cam, lights=None):
    pos, yaw, pitch, roll, fov = cam
    pos = np.asarray(pos, np.float32)
    D = cam_dirs(yaw, pitch, roll, fov)
    bx = cull(sc.boxes, pos, yaw, pitch, fov)
    ceil = sc.ceil_y if (sc.ceil_y is not None or getattr(sc, 'sky_fn', None) is None) else np.inf   # open sky: no far ceiling
    fy = float(getattr(sc, 'floor_y', 0.))            # the ground plane can lie far below (rooftops, cliffs over a valley)
    t, ib = trace(pos, D, bx, fy, ceil, True, _noise)
    rgb, refl, nrm, P = shade(sc, bx, pos, D, t, ib, lights)
    global LAST_AUX; LAST_AUX = (P, t)                  # points touchés par le rayon de chaque pixel (météo par zone, voir render.py)
    m = refl > .02
    if m.any():
        idx = np.nonzero(m)[0]
        Dm = D[idx]; n = nrm[idx]
        R = Dm - 2 * (Dm * n).sum(1, keepdims=True) * n
        Om = P[idx] + n * 2e-3
        t2, ib2 = trace(Om, R, sc.boxes, fy, ceil, False, None)
        r2, _, _, _ = shade(sc, sc.boxes, Om, R, t2, ib2, lights, shadows=False)
        w = refl[idx][:, None]
        rgb[idx] = rgb[idx] * (1 - w) + r2 * w
    return rgb.reshape(RH, RW, 3)

def glow(img, thr=.55, k=.45):
    br = np.clip(img - thr, 0, None)
    s = br.reshape(RH // 8, 8, RW // 8, 8, 3).mean((1, 3))
    for _ in range(2):
        s = (s + np.roll(s, 1, 0) + np.roll(s, -1, 0) + np.roll(s, 1, 1) + np.roll(s, -1, 1)) / 5
    up = np.repeat(np.repeat(s, 8, 0), 8, 1)
    for _ in range(2):
        up = (up + np.roll(up, 4, 0) + np.roll(up, -4, 0) + np.roll(up, 4, 1) + np.roll(up, -4, 1)) / 5
    return img + up * k

# --------------------------- pixelation (hue steps, 5 sat, 12 val, Bayer 4x4) ---------------------------
def rgb2hsv(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx = a.max(-1); mn = a.min(-1); d = mx - mn + 1e-6
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    s = np.where(mx > 1e-5, (mx - mn) / (mx + 1e-6), 0); return h, s, mx
def hsv2rgb(h, s, v):
    c = v * s; hp = (h / 60) % 6; x = c * (1 - np.abs(hp % 2 - 1)); m = v - c
    z = np.zeros_like(h); out = np.zeros(h.shape + (3,), np.float32)
    for k, (r, g, b) in enumerate([(c, x, z), (x, c, z), (z, c, x), (z, x, c), (x, z, c), (c, z, x)]):
        sel = (hp >= k) & (hp < k + 1); out[sel] = np.stack([r[sel], g[sel], b[sel]], -1)
    return out + m[..., None]
def pixelate(rgb, gamma=1.0, vlev=12, slev=5, hstep=20., levels=None):
    """the shipped palette step. `levels` comes from engines/pixel3d/finish.py and says what to do with it:
    None keeps the three counts below (so a caller that passes nothing is bit-identical), a tuple
    (vlev, slev, hstep) replaces them with a finer palette, and False removes the step entirely -- smooth
    gradients instead of banding."""
    if levels is not None:
        if levels is False: return (np.clip(np.clip(rgb, 0, 1) ** gamma, 0, 1) * 255).astype(np.uint8)
        vlev, slev, hstep = levels
    a = np.clip(rgb, 0, 1) ** gamma
    h, s, v = rgb2hsv(a)
    h = np.round(h / hstep) * hstep
    s = np.clip(np.floor(s * (slev - 1) + BAYER_T * .7 + .5), 0, slev - 1) / (slev - 1)
    v = np.clip(np.floor(v * (vlev - 1) + BAYER_T), 0, vlev - 1) / (vlev - 1)
    return (np.clip(hsv2rgb(h, s, v), 0, 1) * 255).astype(np.uint8)
