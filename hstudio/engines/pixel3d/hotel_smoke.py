"""CHAMBRE 313 : la fumée de l'hôtel, un VOLUME peint après le lancer de rayons (style PS1, déterministe).

Le lancer de rayons de PIXEL 3D ne connaît que des boîtes opaques ; une fumée faite de boîtes serait un mur. Ici, pour chaque pixel,
on marche le long du rayon de la caméra jusqu'à ce qu'il touche (distance `t` du lancer, `r3d.LAST_AUX`), on accumule la densité
de fumée et la lumière que la fumée renvoie (les MÊMES lumières que la scène, avec leurs zones), puis on mélange :
    image = image * transmission + lumière diffusée
Le pas de marche est décalé par la trame de Bayer du moteur : les bords de fumée se tramaient comme le reste de l'image PS1.

Composantes (clés d'état du lieu `hotel_nuit`, toutes animables `[a, b, t0, t1]` ou par `state_track`) :
  smoke        0..1   fine fumée grise qui descend du plafond (couloir, hall, 3e étage) ; `smoke_low` = hauteur du bas de la couche (m)
  smoke_black  0..1   fumée noire épaisse qui envahit le couloir ; `smoke_front` = z du front (la fumée est au sud de ce z), absent = partout
  smoke_burst  0..1   le nuage noir qui JAILLIT de la porte de l'escalier sud (0 = rien, 1 = il remplit le début du couloir)
  stair_smoke  0..1   la cage de l'escalier sud pleine de fumée (par défaut 1 dès que sa porte s'ouvre ou que le nuage jaillit)
  under_door_smoke 0..1  fumée qui passe sous la porte 313 (3e étage, flash-back)
  window_smoke 0..1   panaches qui sortent des fenêtres de la façade (dehors)
Sans aucune de ces clés > 0, `params()` rend None : le lieu ne pose aucun post-traitement, l'image est celle du lancer, au bit près."""
import math
import numpy as np
from . import r3d

COR = (-1.2, 0., 9.0, 1.2, 2.7, 26.0)
LOB = (-7.0, 0., 0., 4.7, 3.0, 9.0)
STAIR = (1.3, 0., 9.1, 4.6, 5.0, 12.0)
STEPS = 12
def _puffs(n=14, seed=313):
    """the puffs of the burst, drawn once: (birth 0..1, out, up, along, radius); an early puff has travelled further"""
    r = np.random.default_rng(seed); out = []
    for i in range(n):
        out.append((i / n * .75, r.uniform(1.2, 2.4), r.uniform(.2, 1.3), r.uniform(-2.6, 2.6) * (.4 + .6 * i / n), r.uniform(.42, .7)))
    return tuple(out)
PUFFS = _puffs()
TMAX = 60.
ALB_GREY, ALB_BLACK = .5, .1           # how much light the smoke sends back: grey smoke, black smoke


def _f(s, k, d=0.):
    v = s.get(k, d)
    if isinstance(v, (list, tuple)): v = v[0] if v else d
    try: return float(v) if v is not None else d
    except (TypeError, ValueError): return d


def params(s):
    from . import hotel as H
    p = dict(smoke=_f(s, 'smoke'), low=_f(s, 'smoke_low', 1.9), black=_f(s, 'smoke_black'), front=s.get('smoke_front'), burst=_f(s, 'smoke_burst'),
             under=_f(s, 'under_door_smoke'), win=_f(s, 'window_smoke'), era=s.get('era', 'now'))
    st = s.get('stair_smoke')
    p['stair'] = float(st) if st is not None else (1. if (_f(s, 'stair_door') > .02 or p['burst'] > 0) else 0.)
    if p['stair'] > 0 and _f(s, 'stair_door') <= .02 and p['burst'] <= 0: p['stair'] = 0.        # a closed stairwell is never seen
    gd = _f(s, 'green_door'); p['door'] = p['black'] * min(1., gd * 1.6) if gd > .05 else 0.          # black smoke pours out of the open north door
    if max(p['smoke'], p['black'], p['burst'], p['stair'], p['under'], p['win']) <= 1e-3: return None
    p['third'] = (H.X3 - 1.3, 0., 0., H.X3 + 1.3, 2.6, 12.0); p['x3'] = H.X3; p['d313'] = H.D313
    p['wins'] = [(bx, lvl * 3.0 + 2.45, H.FZ, p['win']) for (bx, lvl) in H.FIRE_WINDOWS] if p['win'] > 0 else []
    if p['door'] > 0: p['wins'].append((0., 1.95, H.FZ - .05, 1.5 * p['door']))
    p['zw'] = H.zone_fn
    return p


# ------------------------------------------------------------------ 3D value noise from a small periodic table (deterministic)
_TAB = None
def _table():
    global _TAB
    if _TAB is None:
        r = np.random.default_rng(1313); a = r.random((32, 32, 32)).astype(np.float32)
        for _ in range(2):
            for ax in range(3): a = (np.roll(a, 1, ax) + a + np.roll(a, -1, ax)) / 3.
        a = (a - a.min()) / max(1e-6, (a.max() - a.min())); _TAB = a
    return _TAB


def noise3(x, y, z):
    T = _table(); n = 32
    fx, fy, fz = np.floor(x), np.floor(y), np.floor(z)
    tx, ty, tz = x - fx, y - fy, z - fz
    tx = tx * tx * (3 - 2 * tx); ty = ty * ty * (3 - 2 * ty); tz = tz * tz * (3 - 2 * tz)
    ix = fx.astype(np.int64) % n; iy = fy.astype(np.int64) % n; iz = fz.astype(np.int64) % n
    jx = (ix + 1) % n; jy = (iy + 1) % n; jz = (iz + 1) % n
    c00 = T[ix, iy, iz] * (1 - tx) + T[jx, iy, iz] * tx; c10 = T[ix, jy, iz] * (1 - tx) + T[jx, jy, iz] * tx
    c01 = T[ix, iy, jz] * (1 - tx) + T[jx, iy, jz] * tx; c11 = T[ix, jy, jz] * (1 - tx) + T[jx, jy, jz] * tx
    return (c00 * (1 - ty) + c10 * ty) * (1 - tz) + (c01 * (1 - ty) + c11 * ty) * tz


def _sstep(a, b, x):
    k = np.clip((x - a) / (b - a), 0., 1.); return k * k * (3 - 2 * k)


def _in(P, R, m=0.):
    return (P[:, 0] > R[0] - m) & (P[:, 0] < R[3] + m) & (P[:, 1] > R[1] - m) & (P[:, 1] < R[4] + m) & (P[:, 2] > R[2] - m) & (P[:, 2] < R[5] + m)


def _slab(O, D, R):
    """ray / AABB: (t_in, t_out) per ray (t_out < t_in = miss)"""
    lo = np.array(R[:3], np.float32); hi = np.array(R[3:], np.float32)
    inv = 1. / np.where(np.abs(D) < 1e-6, 1e-6, D)
    a = (lo - O) * inv; b = (hi - O) * inv
    return np.maximum.reduce(np.minimum(a, b), axis=1), np.minimum.reduce(np.maximum(a, b), axis=1)


class Post:
    """the smoke pass of one frame: called by the PS1 renderer right after the ray cast (render.py, `post_fn`)"""

    def __init__(self, p, g):
        self.p = p; self.g = float(g); self.lights = []          # the place's lights of this frame (set by HotelNuit.lights, called before the render)

    def regions(self):
        p = self.p; out = []
        if p['smoke'] > 0 or p['black'] > 0 or p['burst'] > 0: out += [COR, LOB]
        if p['stair'] > 0: out.append(STAIR)
        if p['smoke'] > 0 or p['under'] > 0: out.append(p['third'])
        if p['wins']:
            xs = [w[0] for w in p['wins']]; ys = [w[1] for w in p['wins']]
            out.append((min(xs) - 2.5, min(ys) - .6, p['wins'][0][2], max(xs) + 6.5, max(ys) + 14., p['wins'][0][2] + 9.))
        return out

    def density(self, P):
        """(sigma of grey smoke, sigma of black smoke) per metre at the points P (n, 3)"""
        p = self.p; g = self.g; n = len(P)
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        sg = np.zeros(n, np.float32); sb = np.zeros(n, np.float32)
        strata = noise3(x * .8 + g * .15, y * 4.6 - g * .05, z * .62 - g * .28)        # smoke settles in horizontal sheets
        turb = noise3(x * 2.7 - g * .35, y * 2.9 + g * .1, z * 2.7 + g * .22)
        nz = .6 * strata + .4 * turb
        wisp = np.clip(nz - .22, 0., None) ** 1.6 * 4.2 + .02            # contrast: thick wisps, thin gaps
        inside = _in(P, COR) | _in(P, LOB)
        thr = _in(P, p['third'])
        if p['smoke'] > 0:                                     # the layer that comes down from the ceiling
            m = inside | thr
            if m.any():
                low = p['low'] + (nz[m] - .5) * .6 + .35 * np.sin(z[m] * 1.7 + x[m] * .9 + g * .35)    # the bottom of the layer rolls
                k = _sstep(low - .1, low + .5, y[m]) * wisp[m]
                sg[m] += 1.05 * p['smoke'] * k
        if p['black'] > 0:
            m = inside | _in(P, STAIR)
            if m.any():
                fr = p['front']
                f = 1. if fr is None else _sstep(float(fr) + 1.2, float(fr) - 1.2, z[m] + (nz[m] - .5) * 2.2)
                k = wisp[m] * (.45 + .55 * _sstep(0., 2.2, y[m])) * f
                sb[m] += 2.2 * p['black'] * k
        if p['burst'] > 0:                                     # puffs rolling out of the stair door, eroded by turbulence: a lumpy black cloud
            b = min(1.2, p['burst']); m = inside
            if m.any():
                xm, ym, zm = x[m], y[m], z[m]; dens = np.zeros(len(xm), np.float32)
                for (born, dx_, dy_, dz_, r0) in PUFFS:
                    if b <= born: continue
                    sv = min(1., (b - born) / (1. - born)); sv = 1 - (1 - sv) ** 2                 # each puff shoots out, then slows down
                    cx, cy, cz = 1.3 - dx_ * sv, .95 + dy_ * sv, 10.05 + dz_ * sv; r = r0 * (.3 + .9 * sv)
                    dens += np.exp(-((xm - cx) ** 2 + ((ym - cy) * 1.15) ** 2 + (zm - cz) ** 2) / (r * r))
                k = np.clip(dens * 2.4 - 1.15 * turb[m] - .45, 0., 3.)           # sharp, eroded edges: it reads as puffs, not as fog
                sb[m] += 5.5 * k
        if p['stair'] > 0:
            m = _in(P, STAIR)
            if m.any(): sb[m] += 1.3 * p["stair"] * wisp[m]
        if p['under'] > 0 and thr.any():                      # seeping under door 313, creeping along the floor, curling up
            xd = p['x3'] - 1.3
            dx = np.maximum(0., x[thr] - xd); dz = z[thr] - p['d313']
            rise = np.exp(-np.maximum(0., y[thr] - .04 - .3 * dx) / (.12 + .25 * dx))
            k = rise * np.exp(-(dz / (.5 + .4 * dx)) ** 2) * np.exp(-dx / 2.0) * wisp[thr]
            sg[thr] += 2.6 * p['under'] * k
        if p['wins']:
            for (bx, y0, fz, amt) in p['wins']:
                h = y - y0
                m = (h > -.6) & (h < 16.) & (z > fz - .05) & (z < fz + 10.)
                if not m.any(): continue
                hm = np.maximum(h[m], 0.)
                ax_z = fz + .25 + .55 * np.sqrt(hm); ax_x = bx + .22 * hm + .4 * np.sin(hm * .7 + g * .5)
                r = .42 + .3 * hm
                d2 = ((x[m] - ax_x) ** 2 + (z[m] - ax_z) ** 2) / (r * r)
                k = np.exp(-d2 * (1.3 - .8 * nz[m])) * np.clip(1 - hm / 15., 0, 1) * _sstep(-.5, .3, h[m]) * wisp[m]
                sg[m] += 1.0 * amt * k / (1. + .1 * hm); sb[m] += .6 * amt * k / (1. + .1 * hm)     # grey enough to catch the fire and the beacons
        return sg, sb

    def __call__(self, img, cam, lights=None, g=None):
        """render.py calls `sc.post_fn(img, cam)` (the hook is shared with the theatre); the lights are the ones the place gave"""
        if lights is None: lights = self.lights
        aux = r3d.LAST_AUX
        if aux is None: return img
        regs = self.regions()
        if not regs: return img
        pos, yaw, pitch, roll, fov = cam
        O = np.asarray(pos, np.float32); D = r3d.cam_dirs(yaw, pitch, roll, fov).astype(np.float32)
        thit = np.where(np.isfinite(aux[1]), aux[1], TMAX).astype(np.float32)
        t0 = np.full(len(D), np.inf, np.float32); t1 = np.zeros(len(D), np.float32)
        for R in regs:
            a, b = _slab(O[None], D, R); a = np.maximum(a, 0.); ok = b > a
            t0 = np.where(ok, np.minimum(t0, a), t0); t1 = np.where(ok, np.maximum(t1, b), t1)
        t1 = np.minimum(t1, thit); hit = t1 > t0 + 1e-3
        if not hit.any(): return img
        idx = np.nonzero(hit)[0]; Dm = D[idx]; a0 = t0[idx]; ds = (t1[idx] - a0) / STEPS
        jit = r3d.BAYER_T.ravel()[idx].astype(np.float32)
        H = len(idx)
        ts = a0[None] + (np.arange(STEPS, dtype=np.float32)[:, None] + jit[None]) * ds[None]           # (STEPS, H)
        P = (O[None, None] + Dm[None] * ts[..., None]).reshape(-1, 3)
        sg, sb = self.density(P)
        sig = (sg + sb).reshape(STEPS, H); share = (sb / np.maximum(sg + sb, 1e-6)).reshape(STEPS, H)
        live = sig.reshape(-1) > 1e-4
        light = np.zeros((STEPS * H, 3), np.float32)
        if live.any():
            Pl = P[live]; zone = self.p['zw'](Pl); acc = np.zeros((len(Pl), 3), np.float32) + np.array((.05, .05, .06), np.float32)
            for L in lights:
                lp, lc, li, lr = L[:4]
                if li < 1e-3 or len(L) < 7: continue            # the camera fill and the actors' lights would make a veil right in front of the lens
                v = np.asarray(lp, np.float32)[None] - Pl; d2 = (v * v).sum(1)
                c = li / (1. + d2 / (lr * lr))
                zw = L[6] if len(L) > 6 else None
                if zw is not None: c = c * np.asarray(zw, np.float32)[zone]
                acc += c[:, None] * np.asarray(lc, np.float32)[None]
            light[live] = acc
        light = light.reshape(STEPS, H, 3)
        alb = (ALB_GREY * (1 - share) + ALB_BLACK / (1. + .8 * sb.reshape(STEPS, H)) * share)[..., None]      # a dense black core stays black near a lamp * np.array((1., .97, .93), np.float32)[None, None]
        trans = np.ones(H, np.float32); scat = np.zeros((H, 3), np.float32)
        for i in range(STEPS):
            a = 1. - np.exp(-sig[i] * ds)
            scat += (trans * a)[:, None] * alb[i] * light[i]
            trans *= (1. - a)
        out = img.reshape(-1, 3).copy()
        out[idx] = out[idx] * trans[:, None] + scat
        return out.reshape(img.shape)
