"""The MEASUREMENT side of the scene QA: run the real PIXEL 3D engine (the logic shared by PS1 and VOXEL) at chosen instants and
read back what it decided -- who is where, which boxes belong to whom, where the camera is, what each pixel of a low-resolution
trace hits (the ray caster's own index buffer) and, in image mode, the low-resolution image of the real painter (`render_lowres`).

Nothing here changes the engine: the measurement hooks are module attributes swapped for the duration of ONE call and put back in
a `finally` (the same discipline as `rigfig.PARTS` in tools/cadrage_qc.py and captions/probe3d.py). A film rendered afterwards in
the same process is drawn exactly as before. Every result is plain JSON (it crosses process boundaries)."""
import copy, math
from contextlib import contextmanager
import numpy as np

CORE_PARTS = ('torso', 'head', 'thighL', 'thighR', 'skirt', 'neck')
NEAR = .45                       # metres: what is this close to the lens fills the frame
TEXT_MIN_PX = 10                 # textured face smaller than this (low-res pixels) is not legible anyway


def _r3d():
    from ..engines.pixel3d import r3d
    return r3d


@contextmanager
def hooks():
    """swap the measurement hooks in, ALWAYS put the originals back"""
    from ..engines.pixel3d import rigfig, costumes as COS, render as R
    r3d = _r3d()
    rec = dict(actors=[], trace=None, finite=True, frame=None)
    o_rb, o_cb, o_tr, o_re, o_bf = rigfig.build, COS.build, r3d.trace, r3d.render, R.build_frame
    depth = [0]

    def wrap(orig):
        def f(sample, look, face, *a, **kw):
            outer = depth[0] == 0
            if outer:
                saved = (rigfig.PARTS, COS.PARTS); rigfig.PARTS = {}; COS.PARTS = {}
            depth[0] += 1
            parts = {}
            try:
                res = orig(sample, look, face, *a, **kw)
            finally:
                depth[0] -= 1
                if outer:
                    for D in (rigfig.PARTS, COS.PARTS):
                        for nm, bx in (D or {}).items(): parts.setdefault(nm, []).extend(bx)
                    rigfig.PARTS, COS.PARTS = saved
            if outer: rec['actors'].append(dict(sample=sample, look=look, boxes=list(res[0]), parts=parts))
            return res
        return f

    def tr(O, D, boxes, floor_y=0., ceil_y=None, primary=True, noise=None, tmax=None, shadow=False):
        out = o_tr(O, D, boxes, floor_y, ceil_y, primary, noise, tmax, shadow)
        if primary and not shadow and rec['trace'] is None and D.shape[0] == r3d.RW * r3d.RH:
            rec['trace'] = (np.asarray(O, np.float32).reshape(-1, 3)[0].copy(), D, list(boxes), np.array(out[0]), np.array(out[1]))
        return out

    def re(sc, cam, lights=None):
        img = o_re(sc, cam, lights)
        if not np.isfinite(img).all(): rec['finite'] = False
        return img

    def bf(ctx, g):
        res = o_bf(ctx, g); rec['frame'] = res; return res

    rigfig.build, COS.build, r3d.trace, r3d.render, R.build_frame = wrap(o_rb), wrap(o_cb), tr, re, bf
    try:
        yield rec
    finally:
        rigfig.build, COS.build, r3d.trace, r3d.render, R.build_frame = o_rb, o_cb, o_tr, o_re, o_bf


def _dirs(cam, cw, ch):
    """r3d.cam_dirs for an arbitrary (coarse) grid"""
    r3d = _r3d(); pos, yaw, pitch, roll, fov = cam
    py, px = np.mgrid[0:ch, 0:cw].astype(np.float32)
    xn = ((px + .5) / cw * 2 - 1).ravel(); yn = (1 - (py + .5) / ch * 2).ravel()
    th = math.tan(math.radians(fov) / 2) * r3d.FOV_K
    x = xn * th * r3d.ASPECT; y = yn * th; z = np.ones_like(x)
    cr, sr = math.cos(roll), math.sin(roll); x, y = x * cr - y * sr, x * sr + y * cr
    cp, sp = math.cos(pitch), math.sin(pitch); y, z = y * cp + z * sp, -y * sp + z * cp
    cy, sy = math.cos(yaw), math.sin(yaw); x, z = x * cy + z * sy, -x * sy + z * cy
    d = np.stack([x, y, z], 1); return d / np.linalg.norm(d, axis=1, keepdims=True)


def world_center(b):
    c = (b.lo + b.hi) / 2.
    return c if b.inst is None else b.inst.R @ c + b.inst.piv


def inside(b, p, tol=0.):
    """is world point p inside box b (oriented boxes through their instance)"""
    q = np.asarray(p, np.float32)
    if b.inst is not None: q = (q - b.inst.piv) @ b.inst.R
    return bool(np.all(q > b.lo + tol) and np.all(q < b.hi - tol))


def solid(b):
    """boxes that stop a body or a lens: no reflection-only ghost, no light decal, nothing dissolving, nothing paper-thin"""
    if b.hidden or getattr(b, 'dissolve', 0.) > .3: return False
    if b.emis > 0 and not b.cast: return False
    sz = b.hi - b.lo
    return float(sz.min()) > .015 and float(sz[0] * sz[1] * sz[2]) > 2e-4


def _shrunk_points(b, k=.5):
    c = (b.lo + b.hi) / 2.; h = (b.hi - b.lo) / 2. * k
    pts = [c] + [c + h * np.array(s, np.float32) for s in ((1, 1, 1), (1, 1, -1), (1, -1, 1), (1, -1, -1), (-1, 1, 1), (-1, 1, -1), (-1, -1, 1), (-1, -1, -1))]
    if b.inst is None: return pts
    return [b.inst.R @ p + b.inst.piv for p in pts]


# texture axes per face key (see r3d.shade): direction of increasing texture column (u) and of increasing row (down the text), local
_TEX_AXES = {5: ((-1, 0, 0), (0, -1, 0)), 4: ((1, 0, 0), (0, -1, 0)), 1: ((0, 0, 1), (0, -1, 0)), 0: ((0, 0, -1), (0, -1, 0)),
             3: ((1, 0, 0), (0, 0, 1)), 2: ((1, 0, 0), (0, 0, 1))}
_FACE_NORMAL = {0: (-1, 0, 0), 1: (1, 0, 0), 2: (0, -1, 0), 3: (0, 1, 0), 4: (0, 0, -1), 5: (0, 0, 1)}


def face_ids(b, P):
    """which face of box b each world hit point P (n, 3) lies on (the rule of r3d.shade)"""
    p = P if b.inst is None else (P - b.inst.piv) @ b.inst.R
    dd = np.concatenate([np.abs(p - b.lo), np.abs(p - b.hi)], 1); f = dd.argmin(1)
    return (f % 3) * 2 + (f >= 3)


def text_orientation(b, key, cam):
    """how the texture on face `key` of box b reads from camera `cam`: 'ok', 'miroir', 'envers' (upside down), 'travers' (sideways)"""
    r3d = _r3d(); pos, yaw, pitch, roll, fov = cam
    u_dir, row_dir = (np.array(v, np.float32) for v in _TEX_AXES[key])
    n = np.array(_FACE_NORMAL[key], np.float32)
    c = (b.lo + b.hi) / 2. + n * (b.hi - b.lo) / 2.
    R = b.inst.R if b.inst is not None else np.eye(3, dtype=np.float32); piv = b.inst.piv if b.inst is not None else 0.
    W = lambda q: R @ q + piv
    ext = float(np.abs((b.hi - b.lo)).max()) * .25 + 1e-3
    P0 = r3d.project(pos, yaw, pitch, roll, fov, W(c)); Pu = r3d.project(pos, yaw, pitch, roll, fov, W(c + u_dir * ext)); Pr = r3d.project(pos, yaw, pitch, roll, fov, W(c + row_dir * ext))
    if min(P0[2], Pu[2], Pr[2]) < .05: return None
    du = (Pu[0] - P0[0], Pu[1] - P0[1]); dr = (Pr[0] - P0[0], Pr[1] - P0[1])
    if abs(du[1]) > 1.6 * abs(du[0]): return 'travers'
    right = du[0] > 0; down = dr[1] < 0
    if right and down: return 'ok'
    if not right and not down: return 'envers'
    return 'miroir'


class Probe:
    """one engine for one episode; `measure(g)` -> plain dict of what the engine shows at film time g"""

    def __init__(self, ep, lines, aspect, duration, env=None):
        from ..pipeline import make_engine
        ep = copy.deepcopy(ep)
        self.duration = float(duration); self.aspect = aspect
        self.eng = make_engine('pixel3d', ep, lines, np.zeros(int(duration * 30) + 90) if env is None else env, self.duration, aspect)
        self.ctx = self.eng.ctx; self.ep = self.eng.ep; self.spans = list(self.ctx.tl.spans)

    # ------------------------------------------------------------------------------------------------ the engine's switches
    def _use(self):
        from ..engines.pixel3d import render as R
        e = self.eng
        R.art.use(e.art); R.bodies.use(e.body); R.EY.use(e.eye); R.FIN.use(e.fin); R.FA.use(e.env); R.QT.use(e.qt)
        if e.fin is not None: _r3d().configure(self.aspect, R.FIN.scale())

    # ------------------------------------------------------------------------------------------------ one instant
    def measure(self, g, image=False, grid=(96, 54)):
        r3d = _r3d(); out = dict(g=float(g))
        try:
            with hooks() as rec:
                if image:
                    lo, shot, T, u = self.eng.render_lowres(g)
                    fr = rec['frame']
                else:
                    self._use(); from ..engines.pixel3d import render as R
                    fr = R.build_frame(self.ctx, g); lo = None
        except Exception as e:
            out['error'] = f'{type(e).__name__} : {e}'; return out
        sc, cam, L, shot, T, u, k, state = fr
        pos, yaw, pitch, roll, fov = cam
        out.update(k=int(k), T=float(T), cam=dict(pos=[float(v) for v in pos], yaw=float(yaw), pitch=float(pitch), roll=float(roll), fov=float(fov)))
        fx = shot.get('fx') or {}
        out['fx'] = {k_: (v if isinstance(v, (int, float, str, bool)) else None) for k_, v in fx.items() if k_ in ('black', 'fade_in', 'fade_out', 'dim', 'flash', 'expo', 'memory', 'vanish', 'eyelid')}
        span = self.spans[k]; out['span'] = [float(span[0]), float(span[1])]
        # ---------------------------------------------------------------- who owns which box
        owner = {}; actors = []
        for ai, a in enumerate(rec['actors']):
            s = a['sample']
            aid = self._aid_of(k, T, s)
            info = dict(id=aid, x=float(s['x']), y=float(s.get('y', 0.)), z=float(s['z']), heading=float(s['heading']), talking=bool(s.get('talking')),
                        face=s.get('face'), hold=s.get('hold'), left=bool((s.get('rig') or {}).get('left')), gesture=[x[0] for x in (s.get('rig') or {}).get('gestures') or []][:1],
                        sit=float((s.get('rig') or {}).get('sit', 0.)), lie=False)
            for nm, bx in a['parts'].items():
                for b in bx: owner[id(b)] = (ai, nm)
            for b in a['boxes']: owner.setdefault(id(b), (ai, 'body'))
            head = a['parts'].get('head') or []
            skin = next((b for b in head if 5 in (b.tex or {})), None) or (head[0] if head else None)
            if skin is not None:
                c = world_center(skin); R_ = skin.inst.R if skin.inst is not None else np.eye(3, dtype=np.float32)
                info['head'] = [float(v) for v in c]; info['face_n'] = [float(v) for v in R_[:, 2]]; info['head_up'] = [float(v) for v in R_[:, 1]]
                info['head_size'] = float(np.abs(skin.hi - skin.lo).max())
                info['lie'] = bool(R_[1, 1] < .5)
                hp = r3d.project(pos, yaw, pitch, roll, fov, c); top = r3d.project(pos, yaw, pitch, roll, fov, c + R_[:, 1] * info['head_size'] * .75)
                chin = r3d.project(pos, yaw, pitch, roll, fov, c - R_[:, 1] * info['head_size'] * .55)
                info['proj'] = dict(head=[float(hp[0]), float(hp[1]), float(hp[2])], top=[float(top[0]), float(top[1]), float(top[2])], chin=[float(chin[0]), float(chin[1]), float(chin[2])])
                tc = np.asarray(pos, np.float32) - c; dist = float(np.linalg.norm(tc))
                info['face_dot'] = float((tc / max(dist, 1e-6)) @ R_[:, 2]); info['dist'] = dist
            torso = (a['parts'].get('torso') or [None])[0]
            if torso is not None:
                tp = r3d.project(pos, yaw, pitch, roll, fov, world_center(torso)); info['proj_torso'] = [float(tp[0]), float(tp[1]), float(tp[2])]
            actors.append(info)
        set_boxes = [b for b in sc.boxes if id(b) not in owner]
        # ---------------------------------------------------------------- the lens: inside something?
        cam_in = []
        for b in set_boxes:
            if solid(b) and inside(b, pos, .02):
                sz = (b.hi - b.lo); cam_in.append(dict(size=[round(float(v), 2) for v in sz], center=[round(float(v), 2) for v in world_center(b)]))
        out['cam_inside'] = cam_in[:3]
        fy = float(getattr(sc, 'floor_y', 0.)); ceil = sc.ceil_y
        out['below_floor'] = bool(pos[1] < fy - .02)
        # outside the place: horizontal rays from the lens that meet no box at all (a closed place answers in every direction)
        if getattr(sc, 'sky_fn', None) is None:
            ang = np.arange(8) * (np.pi / 4); Dh = np.stack([np.sin(ang), np.zeros(8), np.cos(ang)], 1).astype(np.float32)
            th, ibh = r3d.trace(np.asarray(pos, np.float32), Dh, [b for b in set_boxes if not b.hidden], fy, None, False, None)
            n_out = int((~np.isfinite(th) | (np.asarray(ibh) < 0)).sum()); out['outside'] = n_out if n_out >= 3 else 0         # judged below with what the image sees (an open stage is not 'outside')
        else: out['outside'] = 0
        out['above_ceiling'] = bool(ceil is not None and getattr(sc, 'sky_fn', None) is None and pos[1] > float(ceil) + .02)
        # ---------------------------------------------------------------- actors inside the set / inside each other (box level)
        solids = [b for b in set_boxes if solid(b)]
        hits = []
        for ai, a in enumerate(rec['actors']):
            for part in ('torso', 'head', 'skirt'):
                for b in a['parts'].get(part) or []:
                    c = world_center(b)
                    for sb in solids:
                        wlo, whi = r3d.wbounds(sb)
                        if not (np.all(c > wlo - .01) and np.all(c < whi + .01)): continue
                        if inside(sb, c, .03):
                            sz = sb.hi - sb.lo
                            hits.append(dict(who=actors[ai]['id'], part=part, size=[round(float(v), 2) for v in sz], center=[round(float(v), 2) for v in world_center(sb)])); break
                    else: continue
                    break
        out['actor_in_set'] = hits
        pairs = []
        A = rec['actors']
        for i in range(len(A)):
            for j in range(i + 1, len(A)):
                si, sj = A[i]['sample'], A[j]['sample']
                if math.hypot(si['x'] - sj['x'], si['z'] - sj['z']) > 1.6: continue
                core_j = [b for p in CORE_PARTS for b in A[j]['parts'].get(p) or []]
                worst = None
                for p in CORE_PARTS:
                    for b in A[i]['parts'].get(p) or []:
                        pts = _shrunk_points(b)
                        for q in core_j:
                            n_in = sum(inside(q, x, .01) for x in pts)
                            if n_in >= 3 or inside(q, pts[0], .01):
                                cand = (n_in, p, owner.get(id(q), (None, '?'))[1])
                                if worst is None or cand[0] > worst[0]: worst = cand
                if worst: pairs.append(dict(a=actors[i]['id'], b=actors[j]['id'], depth=worst[0], part_a=worst[1], part_b=worst[2]))
        out['actor_pairs'] = pairs
        # ---------------------------------------------------------------- what the pixels hit
        if rec['trace'] is not None:
            O, D, bx, t, ib = rec['trace']; RW, RH = r3d.RW, r3d.RH
        else:
            cw, ch = grid if self.aspect == '16:9' else (grid[1], grid[0])
            D = _dirs(cam, cw, ch); RW, RH = cw, ch
            bx = r3d.cull(sc.boxes, np.asarray(pos, np.float32), yaw, pitch, fov)
            ceil_ = sc.ceil_y if (sc.ceil_y is not None or getattr(sc, 'sky_fn', None) is None) else np.inf
            t, ib = r3d.trace(np.asarray(pos, np.float32), D, bx, fy, ceil_, True, np.random.default_rng(3).random(D.shape[0]).astype(np.float32))
            O = np.asarray(pos, np.float32)
        N = D.shape[0]; out['raster'] = [int(RW), int(RH)]
        own = np.full(len(bx), -1, np.int32); part_of = {}; held = np.zeros(len(bx), bool)
        for i, b in enumerate(bx):
            o = owner.get(id(b))
            if o is not None: own[i] = o[0]; part_of[i] = o[1]; held[i] = o[1] == 'hold'
        ibv = np.asarray(ib).ravel(); tv = np.asarray(t).ravel()
        hit_box = ibv >= 0
        who = np.full(N, -2, np.int32); who[hit_box] = own[ibv[hit_box]]          # -2 floor/ceiling/sky, -1 set, >= 0 actor
        is_held = np.zeros(N, bool); is_held[hit_box] = held[ibv[hit_box]]       # an insert on a held object is not an occlusion
        near = np.isfinite(tv) & (tv < NEAR)
        out['near_set'] = float((near & (who == -1)).mean()); out['near_floor'] = float((near & (who == -2)).mean())
        out['near_actor'] = {actors[i]['id']: float((near & (who == i) & ~is_held).mean()) for i in range(len(actors)) if (near & (who == i) & ~is_held).any()}
        out['near_any'] = float(near.mean())
        out['box_share'] = float((who >= -1).mean())                              # share of the image that is a box (set or body), not floor / ceiling / void
        if out.get('outside') and out['box_share'] >= .25: out['outside'] = 0
        out['miss'] = float((~np.isfinite(tv)).mean())
        out['sky'] = getattr(sc, 'sky_fn', None) is not None
        P = (np.asarray(O, np.float32).reshape(-1, 3)[0] + D * np.where(np.isfinite(tv), tv, 0.)[:, None])
        wmask = None
        if lo is not None and lo.shape[0] == RH and lo.shape[1] == RW: wmask = (np.asarray(lo).min(-1) >= 246).ravel()
        for ai, info in enumerate(actors):
            m = who == ai; info['px'] = float(m.mean())
            if wmask is not None and m.any(): info['white'] = float(wmask[m].mean())
            hidx = [i for i, p in part_of.items() if own[i] == ai and p == 'head']
            hm = np.isin(ibv, hidx) if hidx else np.zeros(N, bool); info['head_px'] = float(hm.mean())
            if hm.any():
                ys, xs = np.divmod(np.nonzero(hm)[0], RW)
                info['head_rect'] = [float(xs.min()) / RW, float(xs.max() + 1) / RW, float(ys.min()) / RH, float(ys.max() + 1) / RH]
                skin_i = [i for i in hidx if 5 in (bx[i].tex or {})]
                fpx = 0
                for i in skin_i:
                    mm = ibv == i
                    if mm.any():
                        fid = face_ids(bx[i], P[mm]); fpx += int((fid == 5).sum())
                        if (fid == 5).any():
                            ys2, xs2 = np.divmod(np.nonzero(mm)[0][fid == 5], RW)
                            info['face_rect'] = [float(xs2.min()) / RW, float(xs2.max() + 1) / RW, float(ys2.min()) / RH, float(ys2.max() + 1) / RH]
                info['face_px'] = fpx / float(N)
            hold_i = [i for i, p in part_of.items() if own[i] == ai and p == 'hold']
            if hold_i:
                hm2 = np.isin(ibv, hold_i); info['hold_px'] = float(hm2.mean())
                tex_faces = 0; has_tex = False
                for i in hold_i:
                    if not bx[i].tex: continue
                    has_tex = True; mm = ibv == i
                    if mm.any(): tex_faces += int(np.isin(face_ids(bx[i], P[mm]), list(bx[i].tex)).sum())
                info['hold_tex'] = has_tex; info['hold_tex_px'] = tex_faces / float(N)
        # ---------------------------------------------------------------- text (any small textured box that is not a face)
        texts = []; head_ids = {i for i, p in part_of.items() if p == 'head'}
        for i in np.unique(ibv[hit_box]):
            b = bx[int(i)]
            if not b.tex or int(i) in head_ids: continue
            if float(np.abs(b.hi - b.lo).max()) > 1.6: continue
            mm = ibv == i
            fid = face_ids(b, P[mm])
            for key in b.tex:
                n_px = int((fid == key).sum())
                if n_px < TEXT_MIN_PX: continue
                o = text_orientation(b, key, cam)
                if o and o != 'ok':
                    texts.append(dict(orient=o, px=n_px / float(N), face=int(key), owner=actors[own[int(i)]]['id'] if own[int(i)] >= 0 else None,
                                      part=part_of.get(int(i)), center=[round(float(v), 2) for v in world_center(b)], size=[round(float(v), 3) for v in (b.hi - b.lo)]))
        for ai, info in enumerate(actors):                                       # a face read upside down (lying character seen from the head)
            if info.get('lie') and info.get('face_px', 0) > .002:
                skin_i = [i for i, p in part_of.items() if own[i] == ai and p == 'head' and 5 in (bx[i].tex or {})]
                if skin_i:
                    o = text_orientation(bx[skin_i[0]], 5, cam)
                    if o in ('envers', 'miroir'): texts.append(dict(orient=o, px=info['face_px'], face=5, owner=info['id'], part='visage'))
        out['texts'] = texts
        out['actors'] = actors
        out['invisible'] = self._invisible(k, T, {a['id'] for a in actors})
        # ---------------------------------------------------------------- the image of the real painter
        if lo is not None:
            out['image'] = image_stats(lo)
            out['image']['finite'] = bool(rec['finite'])
            out['subs_rect'] = self._subs_rect(lo, g, shot, T, u)
            out['lowres_shape'] = [int(lo.shape[1]), int(lo.shape[0])]
            self.last_image = lo
        return out

    def _aid_of(self, k, T, s):
        """the actor id of a built sample: the engine passes the sample dict (copies of it), matched on position"""
        ac = self.ctx.get_acting()
        if k not in ac.shots: return '?'
        best, bd = '?', 1e9
        for aid, v in ac.shots[k].sample(T).items():
            d = abs(v['x'] - s['x']) + abs(v['z'] - s['z']) + abs(float(v.get('y', 0.)) - float(s.get('y', 0.))) * .5
            if d < bd: best, bd = aid, d
        if bd > .8:                                                                # carried / costume-shifted: fall back on the nearest anyway
            pass
        return best

    def _invisible(self, k, T, seen):
        ac = self.ctx.get_acting()
        if k not in ac.shots: return []
        return sorted(a for a, v in ac.shots[k].sample(T).items() if a not in seen)

    def _subs_rect(self, lo, g, shot, T, u):
        """where the subtitle is drawn at g (normalised rect, y down) -- drawn by the engine's own compose() on a black image"""
        ui = dict(shot.get('ui') or {})
        if ui.get('endcard') or ui.get('subs') == 'off': return None
        sh2 = dict(shot, ui=dict(ui, hud=False, recap=None, choice=None, timer=None), fx={})
        try:
            im = np.asarray(self.eng.compose(np.zeros_like(lo), g, sh2, T, u).convert('L'))
        except Exception:
            return None
        m = im > 60
        if not m.any(): return None
        ys, xs = np.nonzero(m); H, W = m.shape
        return [float(xs.min()) / W, float(xs.max() + 1) / W, float(ys.min()) / H, float(ys.max() + 1) / H]


def image_stats(img):
    """luminance statistics of an RGB uint8 image (low resolution is enough)"""
    a = np.asarray(img).astype(np.float32)
    if a.ndim == 2: a = np.stack([a] * 3, -1)
    Y = a[..., 0] * .299 + a[..., 1] * .587 + a[..., 2] * .114
    white = (a.min(-1) >= 246)
    return dict(mean=float(Y.mean()), p05=float(np.percentile(Y, 5)), p50=float(np.percentile(Y, 50)), p95=float(np.percentile(Y, 95)), std=float(Y.std()),
                white=float(white.mean()), clip=float((Y >= 240).mean()), hi=float((Y > 200).mean()), dark=float((Y <= 10).mean()), squares=flat_squares(a),
                soft_squares=soft_squares(a, Y))


def flat_squares(a, min_side=None):
    """sharp-edged rectangles of ONE exact saturated colour (pure white or a non-finite value spread by a glow): [x0, x1, y0, y1] normalised.
    A light fixture is soft-edged or textured; a NaN smeared by the halo is a perfectly flat block."""
    H, W = a.shape[:2]; min_side = min_side or max(4, int(min(W, H) * .035))
    m = (a.min(-1) >= 254)
    if m.mean() < 1e-4 or m.sum() > 60000: return []
    out = []
    lab = np.zeros(m.shape, np.int32); cur = 0
    ys, xs = np.nonzero(m)
    seen = np.zeros(m.shape, bool)
    for y0, x0 in zip(ys, xs):
        if seen[y0, x0]: continue
        stack = [(y0, x0)]; seen[y0, x0] = True; pts = []
        while stack and len(pts) < 200000:
            y, x = stack.pop(); pts.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                yy, xx = y + dy, x + dx
                if 0 <= yy < H and 0 <= xx < W and m[yy, xx] and not seen[yy, xx]: seen[yy, xx] = True; stack.append((yy, xx))
        P_ = np.array(pts); y_lo, x_lo = P_.min(0); y_hi, x_hi = P_.max(0) + 1
        w, h = x_hi - x_lo, y_hi - y_lo
        if w >= min_side and h >= min_side and len(pts) >= .97 * w * h and .4 < w / h < 2.5:
            out.append([float(x_lo) / W, float(x_hi) / W, float(y_lo) / H, float(y_hi) / H])
        if len(out) > 5: break
    return out


def _components(m, max_px=40000):
    """4-connected components of a boolean mask -> [(ys, xs)] (no scipy in the venv); gives up on huge masks"""
    H, W = m.shape
    if m.sum() > max_px: return []
    seen = np.zeros_like(m); out = []
    for y0, x0 in zip(*np.nonzero(m)):
        if seen[y0, x0]: continue
        st = [(y0, x0)]; seen[y0, x0] = True; ys = []; xs = []
        while st:
            y, x = st.pop(); ys.append(y); xs.append(x)
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                yy, xx = y + dy, x + dx
                if 0 <= yy < H and 0 <= xx < W and m[yy, xx] and not seen[yy, xx]: seen[yy, xx] = True; st.append((yy, xx))
        out.append((np.array(ys), np.array(xs)))
    return out


def soft_squares(a, Y=None):
    """the bloomed version of a NaN square (what the VOXEL halo makes of it): a near-white, colourless, SQUARE plateau with a step down all
    around it. A lantern is small and orange, a candle is tiny, a lit dress is not a filled square. -> [[x0, x1, y0, y1, core]] normalised"""
    a = np.asarray(a, np.float32); H, W = a.shape[:2]
    if Y is None: Y = a[..., 0] * .299 + a[..., 1] * .587 + a[..., 2] * .114
    chroma = a.max(-1) - a.min(-1)
    m = (Y >= 200) & (chroma < 34)
    side = max(5, int(min(W, H) * .03)); out = []
    for ys, xs in _components(m):
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1; w, h = x1 - x0, y1 - y0
        if w < side or h < side or not (.6 < w / h < 1.6) or len(ys) < .8 * w * h: continue
        inside = float(Y[y0:y1, x0:x1].mean()); r = max(2, int(.15 * max(w, h)))
        Y0, Y1, X0, X1 = max(0, y0 - r), min(H, y1 + r), max(0, x0 - r), min(W, x1 + r)
        ring = Y[Y0:Y1, X0:X1].sum() - Y[y0:y1, x0:x1].sum(); n_ring = (Y1 - Y0) * (X1 - X0) - w * h
        if n_ring <= 0: continue
        if inside >= 215 and ring / n_ring <= inside - 45:
            out.append([float(x0) / W, float(x1) / W, float(y0) / H, float(y1) / H, round(float(Y[y0:y1, x0:x1].max()), 1)])
        if len(out) > 5: break
    return out
