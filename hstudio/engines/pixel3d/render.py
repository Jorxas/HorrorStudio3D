"""PIXEL 3D engine: low-res ray-traced frame -> grade -> pixelation -> x5 upscale -> HUD/subtitles/UI.
Both formats: '9:16' (216x384 -> 1080x1920, TikTok/Shorts) and '16:9' (384x216 -> 1920x1080, YouTube)."""
import math, numpy as np
from PIL import Image, ImageDraw
from . import r3d
from . import world as W
from . import art
from . import bodies
from . import eyes as EY
from . import finish as FIN
from . import facades as FA
from . import quartiers as QT
from . import objets as OD
from .frame import FrameContext, build_frame, val, clamp, ease, apply_cut
from ..common import build_subs, active_sub, outlined, hearts_at, font
from ...paths import FONT_PIXEL

CREAM = (238, 232, 212); RED = (232, 64, 48); BLUE = (120, 176, 255); BLACK = (6, 6, 10)
LABEL_COLORS = {'cream': CREAM, 'red': RED, 'blue': BLUE, 'green': (120, 230, 140), 'orange': (255, 150, 70)}
EXPO = 1.0; SAT = .5


def epaule_genou(spec):
    """episode `grade.epaule`: None / False / 0 -> off (the shipped hard clip, bit for bit) ; True -> knee 0.72 ; a number in
    [0.4, 0.95] -> that knee. Anything else -> off (a bad value never changes the image silently: check_epaule tests it)."""
    if spec is True: return .72
    if isinstance(spec, bool) or not isinstance(spec, (int, float)) or not spec: return 0.
    return min(.95, max(.4, float(spec)))


def epaule(img, knee=.72, expo=1.0):
    """hue-keeping soft shoulder, replacing the per-channel hard clip of the shipped grade when the episode asks for it.
    WHY: with a strong exposure (a "very bright" version, measured on LE PHARE QUI EFFACE at exposure 1.85) the shipped path
    clips R, G and B separately: a lit face goes white and brown hair turns orange-blond, i.e. the character changes.
    HOW: the brightest channel m is rolled off above `knee` (slope 1 at the knee, asymptote 1) and the three channels are
    scaled by the same ratio, so hue and saturation are kept. Only the real light sources (scene value above 1 BEFORE the
    exposure: a lamp, a lantern, a screen) still burn out towards white, the way a practical does on film."""
    m = img.max(-1, keepdims=True)
    src = np.clip((m / max(float(expo), 1e-3) - 1.0) / 1.0, 0, 1) * .6       # scene-referred: only practicals bleach
    img = img + (m - img) * src
    m = np.maximum(img.max(-1, keepdims=True), 1e-5)
    w = 1. - knee
    mo = np.where(m > knee, knee + w * (1. - np.exp(-(m - knee) / w)), m)
    return img * (mo / m)

def F(sz): return font(FONT_PIXEL, sz)

HEART = ["0110110", "1111111", "1111111", "0111110", "0011100", "0001000"]
def heart(d, x, y, full, px=6):
    for r, row in enumerate(HEART):
        for c, v in enumerate(row):
            if v != '1': continue
            if full: d.rectangle([x + c * px, y + r * px, x + c * px + px - 1, y + r * px + px - 1], fill=(228, 40, 52))
            elif r in (0,) or c in (0, 6) or r == 5 or (r, c) in ((1, 1), (1, 5), (2, 1), (2, 5), (3, 1), (3, 5), (4, 2), (4, 4)):
                d.rectangle([x + c * px, y + r * px, x + c * px + px - 1, y + r * px + px - 1], fill=(190, 190, 200))
ZERO = ["0111110", "1100011", "1100011", "1100011", "1100011", "1100011", "1100011", "1100011", "1100011", "1100011", "1100011", "0111110"]
def big_zero(d, cx, y, px=18, col=(232, 40, 40)):
    for r, row in enumerate(ZERO):
        for c, v in enumerate(row):
            if v == '1': d.rectangle([cx - 3.5 * px + c * px, y + r * px, cx - 3.5 * px + c * px + px - 1, y + r * px + px - 1], fill=col)
def tri(d, x, y, s, col): d.polygon([(x, y), (x + s, y + s), (x, y + 2 * s)], fill=col)

class Layout:
    def __init__(self, aspect):
        self.aspect = aspect
        if aspect == '9:16':
            self.W, self.H = 1080, 1920
            self.hud = (52, 52); self.hearts_x = lambda W: W - 52 - 150; self.sub_y = {'mid': 880, 'low': 1560, 'top': 420, 'choice': 1060}
        else:
            self.W, self.H = 1920, 1080
            self.hud = (48, 44); self.hearts_x = lambda W: W - 48 - 150; self.sub_y = {'mid': 800, 'low': 950, 'top': 300, 'choice': 700}

def surface_at(spec, x, z):
    for r in spec.get('rooms', []) or []:
        ox, oz = r.get('origin', [0, 0]); w, d = r.get('size', [4, 5])
        if ox - w / 2 <= x <= ox + w / 2 and oz <= z <= oz + d: return r.get('floor', 'wood') if r.get('floor') != 'none' else spec.get('ground', 'wood')
    return spec.get('ground', 'asphalt' if spec.get('outdoor') else 'concrete')

class Pixel3DEngine:
    name = 'pixel3d'
    def __init__(self, episode, lines, env, duration, aspect='9:16'):
        from ...capabilities.extensions import ensure_loaded; ensure_loaded()     # stable, fingerprinted extensions (V3)
        from ... import profiles; profiles.apply(episode)  # "profile": "production" pose les modules utiles (setdefault, rien sans la cle)
        self.fin = FIN.configure(episode.get('finish'))     # finition de l'image : opt-in aussi (cle "finish")
        self.env = FA.configure(episode.get('env'))         # facades des batiments : opt-in aussi (cle "env")
        self.qt = QT.configure(episode.get('diversite'), episode)   # quartiers et interieurs varies : opt-in aussi (cle "diversite")
        self.od = OD.configure(episode.get('objets'), episode)      # objets detailles (telephones, tasses, lampes, ecrans...) : opt-in aussi (cle "objets")
        r3d.configure(aspect, FIN.scale())                  # raster natif x1 sans la cle, au pixel pres
        self.art = art.configure(episode.get('art'))   # art direction v2: off unless the episode asks for it (opt-in)
        self.body = bodies.configure(episode.get('body'))   # refonte des proportions du corps: opt-in aussi (cle "body")
        self.eye = EY.configure(episode.get('eye_aim'))     # visee du regard: opt-in aussi (cle "eye_aim")
        from ...acting.cast import apply as _cast; _cast(episode)          # library characters (persistent identities)
        from . import ps1_elements as _PE; _PE.normalize_episode(episode)   # éléments nés dans VOXEL (b_look, b_preset, archétypes) : version PS1
        # where this art direction and the V2 expressive look overlap, say it in French instead of in silence
        self.art_warnings = (art.notices(episode.get('cast') or {}) + bodies.notices(episode)
                             + EY.notices(episode) + FIN.notices(episode) + FA.notices(episode) + QT.notices(episode) + OD.notices(episode))
        for _m in self.art_warnings: print(f'[art] {_m}')
        self.ep = episode; self.lines = lines; self.duration = duration; self.aspect = aspect
        self.ctx = FrameContext(episode, lines, env, duration)
        self.L = Layout(aspect)
        self.subs = build_subs(lines, 15, 4, True)
        self.hud = episode.get('hud', {}) or {}
        # sous-titres surs : opt-in aussi (cle "caption_safe"). None = le bandeau livre, au pixel pres.
        from ...captions import safe as CAPS
        self.caps = CAPS.configure(episode.get('caption_safe'))
        for _m in CAPS.notices(episode): print(f'[sous-titres] {_m}')

    def acting_events(self):
        """timeline events of acted shots in absolute time, with the floor under the feet (for footsteps)"""
        acting = self.ctx.get_acting(); out = []
        for k, sa in acting.shots.items():
            t0 = self.ctx.tl.spans[k][0]; spec = getattr(sa.world.st, 'spec', {}) or {}
            for (t, kind, who, d) in sa.all_events():
                d = dict(d)
                if kind == 'step':
                    x, z = sa.position(sa.tracks[who], t); d['surface'] = surface_at(spec, x, z)
                    look = (self.ep.get('cast') or {}).get(who, {})
                    if look.get('kind') in ('dog', 'cat', 'bird', 'horse', 'cow', 'rabbit', 'chicken', 'pig', 'sheep', 'duck', 'spider', 'ghost'): continue
                out.append((t0 + t, kind, who, d))
            for ev in getattr(sa, 'world_events', []): out.append((t0 + ev[0], ev[1], None, ev[2]))
        from .effects import sounds
        for k, shot in enumerate(self.ep['shots']):                 # V3 effects: thunder of a strike, a collapse, wings, a rotor
            for (t, name, gain, dur) in sounds(shot, self.ctx.tl.spans[k][0]):
                out.append((self.ctx.tl.spans[k][0] + t, 'sfx', None, {'name': name, 'gain': gain, 'dur': dur}))
        return sorted(out, key=lambda e: e[0])

    # ------------------------------------------------------------ quality control (acting/qc.py)
    def qc_observe(self, g):
        """what the camera shows at time g in an acted shot: subjects of the camera, people in frame / hidden"""
        from ...acting import rig, cinema
        from .acted import _probe_fn, capsule, cam_boxes
        from . import acted as ACT
        from . import creatures as CR
        bodies.use(self.body)                  # the QC builds frames too: same proportions as the renderer
        EY.use(self.eye)                       # ... and the same pupils
        FIN.use(self.fin)                      # ... and the same raster
        FA.use(self.env)                       # ... and the same facades
        QT.use(self.qt)                        # ... and the same districts / interiors
        OD.use(self.od)                        # ... and the same detailed objects
        if self.fin is not None: r3d.configure(self.aspect, FIN.scale())
        ctx = self.ctx; k, t0, t1 = ctx.tl.at(g); ac = ctx.get_acting()
        if k not in ac.shots: return None
        fr = build_frame(ctx, g); cam, shot = fr[1], fr[3]
        sm = ac.shots[k].sample(g - t0)
        plan = ctx.cam_cache.get((k, r3d.RW)) or {}; sol = plan.get('sol') or {}; c = plan.get('cam') or {}
        ids = list(plan.get('ids') or []); kind = sol.get('shot', c.get('shot'))
        talking = [a for a, s in sm.items() if s['talking']]
        if kind in ('pov', 'insert') or not plan: subjects = []
        elif kind == 'ots' or (c.get('shot') == 'dialogue' and kind != 'two_shot'):
            spk = c.get('speaker') if c.get('speaker') in ids else next((a for a in talking if a in ids), ids[0] if ids else None)
            subjects = [spk] if spk else []
        elif sol.get('focus') in ids: subjects = [sol['focus']]          # narrow frame: the cinematographer favoured one face
        else: subjects = ids
        pos, yaw, pitch, roll, fov = cam
        st = ctx.get_set(shot.get('set', ctx.ep.get('default_set', 'etage_zero')))
        cast = ctx.ep.get('cast') or {}; people = {}
        for a, s in sm.items():
            if not s.get('visible', 1): continue
            if (cast.get(a) or {}).get('kind') in CR.ANIMALS: hp = (s['x'], .45, s['z'])
            else:
                sc_ = float((cast.get(a) or {}).get('scale', 1.))
                hd = rig.solve(s['rig']).joints['head'] * sc_; ch, sh = math.cos(s['heading']), math.sin(s['heading'])
                hp = (s['x'] + hd[0] * ch + hd[2] * sh, float(hd[1]) + bodies.head_lift() * sc_ + s.get('y', 0.), s['z'] - hd[0] * sh + hd[2] * ch)
            u_, v_, zc = r3d.project(pos, yaw, pitch, roll, fov, hp)
            inside = zc > .1 and abs(u_) < .95 and abs(v_) < .95
            if inside and kind not in ('close', 'extreme_close', 'ots', 'pov', 'insert') and (cast.get(a) or {}).get('kind') not in CR.ANIMALS:
                inside = r3d.project(pos, yaw, pitch, roll, fov, (hp[0], hp[1] + .2, hp[2]))[1] < .97      # the top of the head too
            others = [capsule(v) for b, v in sm.items() if b != a and not (kind == 'ots' and b in ids) and (cast.get(b) or {}).get('kind') not in CR.ANIMALS]
            fa = hs_ = None
            if (cast.get(a) or {}).get('kind') not in CR.ANIMALS:        # how far the face is turned away from the camera
                fz = s['heading'] + float(s['rig'].get('head', (0., 0.))[0])
                toc = math.atan2(pos[0] - s['x'], pos[2] - s['z'])
                fa = round(abs(math.degrees(cinema.wrap(toc - fz))), 1)
                hw = ACT.HEAD_W * bodies.head_scale() * float((cast.get(a) or {}).get('scale', 1.))    # share of the image width the head takes
                e1 = r3d.project(pos, yaw, pitch, roll, fov, (hp[0] + math.cos(toc) * hw / 2, hp[1], hp[2] - math.sin(toc) * hw / 2))
                e2 = r3d.project(pos, yaw, pitch, roll, fov, (hp[0] - math.cos(toc) * hw / 2, hp[1], hp[2] + math.sin(toc) * hw / 2))
                if e1[2] > .1 and e2[2] > .1: hs_ = round(abs(e1[0] - e2[0]) / 2, 3)
            people[a] = dict(in_frame=inside, visible=bool(inside and _probe_fn(st, others, cam_boxes(st, ac.shots[k], [g - t0]))(pos, hp)), talking=bool(s['talking']), uv=(round(u_, 3), round(v_, 3)), face_angle=fa, head_share=hs_)
        return dict(shot=k, subjects=subjects, people=people, cam=dict(fov=float(fov), score=plan.get('score'), shot=kind))

    def qc_image(self, g): return self.render_lowres(g)[0]

    # ------------------------------------------------------------ low-res render
    def render_lowres(self, g):
        art.use(self.art)                      # this engine's art direction, even if another engine was built since
        bodies.use(self.body)                  # ... and its body proportions, same contract (spawn pool, several engines)
        EY.use(self.eye)                       # ... and its eye aim, same contract
        FIN.use(self.fin)                      # ... and its image finish: the raster, the palette, the filter
        FA.use(self.env)                       # ... and its building facades, same contract
        QT.use(self.qt)                        # ... and its districts / interiors, same contract
        OD.use(self.od)                        # ... and its detailed objects, same contract
        # only when the key is on: without it this call did not exist, and a tool that sizes the raster
        # itself between two frames (tools/catalogue.py) must keep being able to
        if self.fin is not None: r3d.configure(self.aspect, FIN.scale())
        RW, RH = r3d.RW, r3d.RH
        sc, cam, L, shot, T, u, k, state = build_frame(self.ctx, g)
        fx = shot.get('fx', {}) or {}
        if fx.get('black'): return np.zeros((RH, RW, 3), np.uint8), shot, T, u
        if art.on('decor'): sc.boxes = sc.boxes + art.decor(sc.boxes, sc.ceil_y)   # art v2 set dressing (cached per set)
        img = r3d.render(sc, cam, lights=L)
        if getattr(sc, 'post_fn', None) is not None: img = sc.post_fn(img, cam)      # passe d'un lieu (théâtre : faisceaux dans la brume) ; aucun autre lieu n'en pose
        img = r3d.glow(img) if not art.on('grade') else img      # art v2 replaces the glow with its own halation
        mem = float(val(fx.get('memory'), u, 0.) or 0.)
        if mem:
            gy = img.mean(-1, keepdims=True)
            img = (img * (1 - mem) + gy * np.array([.85, 1.0, .85]) * mem * 1.1) * (1 + .35 * mem)
            img *= (0.85 + .15 * np.sin(np.arange(RH)[:, None, None] * 2.2))
        if fx.get('tint'): img = img * np.array(fx['tint'], np.float32)
        bl = float(val(fx.get('bloom'), u, 0.) or 0.)
        if bl: img = img + bl * np.array([1., .86, .6])
        sat = float(self.ep.get('grade', {}).get('saturation', SAT)); expo = float(self.ep.get('grade', {}).get('exposure', EXPO)) * float(val(fx.get('expo'), u, 1.) or 1.)
        if art.on('grade'):                      # art v2 owns the whole finish: saturation and exposure once, not twice
            out = art.grade(img, sat, expo, int(g * 30), levels=FIN.levels((18, 7, 12.)))
        else:
            lum = (img * np.array([.3, .59, .11], np.float32)).sum(-1, keepdims=True)
            img = lum + (img - lum) * sat
            img = img * expo * np.array([1.0, .98, .9], np.float32) + np.array([.014, .012, .010], np.float32)
            kn = epaule_genou(self.ep.get('grade', {}).get('epaule'))
            if kn: img = epaule(img, kn, expo)        # opt-in: a strong exposure no longer bleaches skins nor turns brown hair orange
            img = np.clip(img, 0, None) ** 1.08
            img = img + (np.random.default_rng(int(g * 30) + 7).random(img.shape[:2], np.float32)[..., None] - .5) * .035
            out = r3d.pixelate(img, gamma=1.0, levels=FIN.levels((12, 5, 20.)))
        # flashes: number for the whole shot, or [[at_seconds, amount, duration], ...]
        fl = fx.get('flash')
        f_amt = 0.
        if isinstance(fl, (int, float)): f_amt = float(fl) * clamp(1 - T / .25)
        elif isinstance(fl, list):
            for e in fl:
                at, amtv, dur = (list(e) + [.25])[:3] if isinstance(e, (list, tuple)) else (0, float(e), .25)
                if at <= T < at + dur: f_amt = max(f_amt, float(amtv) * (1 - (T - at) / dur))
        f_amt = max(f_amt, getattr(self.ctx, 'fx_flash', 0.))          # V3: an effect lit the whole sky (lightning strike)
        if f_amt > 0: out = np.clip(out.astype(np.float32) * (1 - f_amt) + 255 * f_amt, 0, 255).astype(np.uint8)
        gl = fx.get('glitch', 0)
        if gl == 'pulse': gl = .5 if int(g * 8) % 3 == 0 else 0
        gl = float(val(gl, u, 0.) or 0.)
        if gl:
            r = np.random.default_rng(int(g * 30)); out = out.copy()
            for _ in range(int(3 + gl * 8)):
                y = r.integers(0, RH - 8); h = r.integers(2, 14); dx = r.integers(-int(6 + gl * 20), int(6 + gl * 20) + 1)
                out[y:y + h] = np.roll(out[y:y + h], dx, axis=1)
            out[..., 0] = np.roll(out[..., 0], 2, axis=1); out[..., 2] = np.roll(out[..., 2], -2, axis=1)
        wk = shot.get('weather')                      # rain, snow, leaves, fireflies... (shot > set > episode)
        if wk is None:
            st_ = self.ctx.get_set(shot.get('set', self.ep.get('default_set', 'etage_zero')))
            wk = (getattr(st_, 'spec', {}) or {}).get('weather') or self.ep.get('weather')
        if wk and wk != 'none':
            wo = W.weather(out, wk, g, float(shot.get('weather_amount', self.ep.get('weather_amount', 1.))))
            zf = getattr(sc, 'zone_fn', None); aux = r3d.LAST_AUX
            if zf is not None and aux is not None:        # lieu à zones (station) : la pluie ne tombe que là où le pixel voit le dehors, pas à l'intérieur de la boutique
                P_, t_ = aux; mk = ((zf(P_) == 0) | ~np.isfinite(t_)).reshape(RH, RW)
                wo = np.where(mk[..., None], wo, out)
            out = wo
        if fx.get('vanish'):
            v_ = clamp(T / float(fx.get('vanish_time', 1.6))) if fx['vanish'] is True else float(val(fx['vanish'], u, 0.))
            nz = r3d.BAYER_T * .25 + np.random.default_rng(int(g * 30)).random((RH, RW)) * .75
            out = out.copy(); out[nz < v_] = 0
            sp = (nz >= v_) & (nz < v_ + .025); out[sp] = (230, 226, 220)
        ey = fx.get('eyelid')
        if ey:
            if ey == 'close': e_ = ease(clamp(T / float(fx.get('eyelid_time', 1.3))))
            elif ey == 'open': e_ = 1 - ease(clamp(T / float(fx.get('eyelid_time', .6))))
            elif ey == 'blink': e_ = 1 - abs(((T % 3) - .15) / .15) if (T % 3) < .3 else 0
            else: e_ = float(val(ey, u, 0.))
            hh = int(e_ * RH / 2 + .5); out = out.copy()
            if hh > 0: out[:hh] = 0; out[RH - hh:] = 0
            if 0 < hh < RH // 2:
                for kk in range(1, 7):
                    a0 = max(0, hh - 1 + kk); a1 = min(RH - 1, RH - hh - kk)
                    out[a0] = (out[a0] * (kk / 7)).astype(np.uint8); out[a1] = (out[a1] * (kk / 7)).astype(np.uint8)
        if fx.get('fade_in'): out = (out.astype(np.float32) * clamp(T / float(fx['fade_in']))).astype(np.uint8)
        if fx.get('fade_out'):
            k0, k1 = self.ctx.tl.spans[k]
            out = (out.astype(np.float32) * clamp((k1 - g) / float(fx['fade_out']))).astype(np.uint8)
        yy, xx = np.mgrid[0:RH, 0:RW]; v = 1 - .48 * (((xx - RW / 2) / (RW / 2)) ** 2 + ((yy - RH / 2) / (RH / 2)) ** 2) / 2
        out = (out.astype(np.float32) * np.clip(v, .3, 1)[..., None]).astype(np.uint8)
        return out, shot, T, u

    # ------------------------------------------------------------ UI
    def center(self, d, y, text, fnt, fill, shadow=True):
        w = d.textlength(text, font=fnt); x = (self.L.W - w) / 2
        if shadow: outlined(d, (x, y), text, fnt, fill)
        else: d.text((x, y), text, font=fnt, fill=fill)

    def recap(self, d, r):
        W = self.L.W; v = self.aspect == '9:16'
        x0, x1 = (72, W - 72) if v else (W / 2 - 430, W / 2 + 430); y0 = 425 if v else 190
        d.rectangle([x0, y0, x1, y0 + 288 if v else y0 + 250], fill=(8, 8, 12), outline=CREAM, width=6)
        self.center(d, y0 + 37 if v else y0 + 32, r.get('title', 'TON CHOIX :'), F(40), CREAM, False)
        yb = y0 + (115 if v else 100)
        d.rectangle([x0 + 40, yb, x1 - 40, yb + (135 if v else 122)], fill=(30, 6, 8), outline=RED, width=6)
        d.text((x0 + 78, yb + 40), str(r.get('letter', 'A'))[:1].upper(), font=F(56), fill=RED)
        tx = r.get('text', ['', '']); tx = tx if isinstance(tx, list) else [tx]
        for i, s in enumerate(tx[:2]): d.text((x0 + 188, yb + 22 + i * 56), s.upper(), font=F(40), fill=CREAM)

    def choice(self, d, c, g):
        W = self.L.W; v = self.aspect == '9:16'
        if v:
            d.rectangle([72, 375, W - 72, 520], fill=(8, 8, 12), outline=CREAM, width=6)
            self.center(d, 425, c.get('title', 'QUE FAIS-TU ?').upper(), F(52), CREAM, False)
        else:
            d.rectangle([W / 2 - 430, 170, W / 2 + 430, 300], fill=(8, 8, 12), outline=CREAM, width=6)
            self.center(d, 210, c.get('title', 'QUE FAIS-TU ?').upper(), F(52), CREAM, False)
        letters = [L_ for L_ in ('A', 'B', 'C') if c.get(L_)] or ['A', 'B']      # 3 branches: A/B/C (story layer)
        sel = c.get('cursor', 'blink')
        if sel in ('blink', '?'): sel = letters[int(g * 1.5) % len(letters)]
        n = len(letters); h = 150 if n < 3 else 145                              # 2 options: unchanged layout
        for k, L_ in enumerate(letters):
            lines = c.get(L_, ['', '']); lines = lines if isinstance(lines, list) else [lines]
            on = sel == L_
            if v: x0, x1, y = 72, W - 72, (1440 + k * 180) if n < 3 else (1380 + k * 170)
            elif n < 3: x0 = 150 + k * 840; x1 = x0 + 780; y = 870
            else: w = (W - 180 - 40 * (n - 1)) / n; x0 = 90 + k * (w + 40); x1 = x0 + w; y = 870
            d.rectangle([x0, y, x1, y + h], fill=(26, 6, 8) if on else (8, 8, 12), outline=RED if on else (200, 200, 205), width=7 if on else 4)
            if on and int(g * 4) % 2 == 0: tri(d, x0 + 26, (y + 52) if n < 3 else (y + h / 2 - 23), 24, CREAM)
            d.text((x0 + 76, y + 47), L_, font=F(56), fill=RED if on else CREAM)
            for i, s in enumerate(lines[:2]): d.text((x0 + 186, y + 30 + i * 54), s.upper(), font=F(40), fill=CREAM if on else (190, 190, 196))

    def endcard(self, im, d, e, g):
        v = self.aspect == '9:16'; W = self.L.W
        title = self.hud.get('title', ["L'ÉTAGE 0"]) or ['']
        if e.get('logo'): logo = e['logo']
        elif title[0].endswith(' 0'): logo = [title[0].rsplit(' ', 1)[0], '0', self.hud.get('title', ['', "N'EXISTE PAS"])[-1]]   # L'Étage 0: big red zero
        else: logo = [title[0], '', title[-1] if len(title) > 1 else '']                                                  # any other series
        y = 380 if v else 120
        self.center(d, y, logo[0].upper(), F(72 if v else 64), CREAM)
        big = logo[1] if len(logo) > 2 else ''
        if big == '0': big_zero(d, W / 2, y + 120 if v else y + 95, 20 if v else 16)
        elif big: self.center(d, y + 150 if v else y + 120, big.upper(), F(140 if v else 110), (232, 40, 40))
        y2 = (780 if v else 440) if big else (y + (130 if v else 100))
        self.center(d, y2, logo[-1].upper(), F(56 if v else 52), CREAM)
        self.center(d, y2 + (100 if v else 80), (e.get('part') or self.hud.get('part', '')).upper(), F(36 if v else 32), (170, 170, 160), False)
        self.center(d, 1090 if v else 630, e.get('headline', 'A OU B ?').upper(), F(88 if v else 80), CREAM)
        self.center(d, 1300 if v else 790, e.get('cta', 'VOTE EN COMMENTAIRE').upper(), F(36 if v else 32), RED, False)
        bw = 330 if v else 300; by = 1380 if v else 850
        d.rectangle([W / 2 - bw, by, W / 2 + bw, by + (90 if v else 80)], outline=CREAM, width=6)
        self.center(d, by + (29 if v else 25), e.get('button', 'ABONNE-TOI').upper(), F(32 if v else 30), CREAM, False)

    def messages(self, d, m, T):
        """opt-in `ui.messages` (9/11/2026): a clean, readable phone conversation card drawn in 2D (same for PS1 and VOXEL).
        {"nom": "LINA", "heure": "17:42", "couleur": [r,g,b], "messages": ["text", {"texte": "...", "at": 0.6, "de": "moi"}, ...],
         "typing": [t0, t1] | true, "vibre": [t, ...], "entree": true, "y": top (px)} ; times are seconds from the start of the shot (or cut)."""
        v = self.aspect == '9:16'; W = self.L.W
        fs = 30 if v else 26; lh = fs + 12; pad = 26
        x0, x1 = (110, W - 110) if v else (W / 2 - 430, W / 2 + 430)
        y0 = float(m.get('y', 300 if v else 120))
        if m.get('entree'):                                                     # the card slides up at the start of the shot
            k = clamp(T / .35); y0 += (1 - ease(k)) * 260
        vib = 0.
        for tv in (m.get('vibre') or []):                                        # the phone buzzes: a short shake
            if 0 <= T - float(tv) < .45: vib = 9 * math.sin((T - float(tv)) * 95)
        x0 += vib; x1 += vib
        msgs = []
        for it in (m.get('messages') or []):
            it = {'texte': it} if isinstance(it, str) else dict(it)
            if T >= float(it.get('at', 0.)): msgs.append(it)
        fnt = F(fs); maxw = (x1 - x0) * .78 - 2 * pad
        def wrap(t):
            out, cur = [], ''
            for w in str(t).split():
                c2 = (cur + ' ' + w).strip()
                if cur and d.textlength(c2, font=fnt) > maxw: out.append(cur); cur = w
                else: cur = c2
            if cur: out.append(cur)
            return out or ['']
        blocks = [(wrap(it.get('texte', '')), it.get('de', 'elle')) for it in msgs]
        ty = m.get('typing'); typing = bool(ty) and (ty is True or (isinstance(ty, (list, tuple)) and float(ty[0]) <= T < float(ty[1])))
        hh = 112 if v else 96
        body = sum(len(l) * lh + 2 * 18 - 12 + 18 for l, _ in blocks) + ((lh + 24 + 18) if typing else 0)
        y1 = y0 + hh + 18 + max(body, 60)
        bg = (250, 249, 246); dark = (32, 34, 42); col = tuple(m.get('couleur', (90, 140, 220)))
        d.rounded_rectangle([x0 + 10, y0 + 12, x1 + 10, y1 + 12], 34, fill=(20, 20, 26))           # shadow
        d.rounded_rectangle([x0, y0, x1, y1], 34, fill=bg, outline=(214, 214, 220), width=3)
        d.rounded_rectangle([x0, y0, x1, y0 + hh], 34, fill=(240, 240, 244)); d.rectangle([x0, y0 + hh - 34, x1, y0 + hh], fill=(240, 240, 244))
        d.line([x0, y0 + hh, x1, y0 + hh], fill=(214, 214, 220), width=3)
        r = (hh - 36) / 2; cx, cy = x0 + pad + r, y0 + hh / 2
        nom = str(m.get('nom', '')).upper()
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
        ini = nom[:1] or '?'; iw = d.textlength(ini, font=F(fs + 6)); d.text((cx - iw / 2, cy - (fs + 6) / 2 + 1), ini, font=F(fs + 6), fill=(255, 255, 255))
        d.text((cx + r + 22, cy - fs / 2), nom, font=F(fs + 2), fill=dark)
        if m.get('heure'):
            hw_ = d.textlength(str(m['heure']), font=F(fs - 8)); d.text((x1 - pad - hw_, cy - (fs - 8) / 2), str(m['heure']), font=F(fs - 8), fill=(120, 122, 132))
        y = y0 + hh + 18
        for lines_, who in blocks:
            bw = max(d.textlength(l, font=fnt) for l in lines_) + 2 * pad; bh = len(lines_) * lh + 2 * 18 - 12
            mine = who == 'moi'
            bx0 = x1 - pad - bw if mine else x0 + pad; bx1 = bx0 + bw
            d.rounded_rectangle([bx0, y, bx1, y + bh], 26, fill=(64, 128, 236) if mine else (228, 230, 236))
            for i, l in enumerate(lines_): d.text((bx0 + pad, y + 18 + i * lh), l, font=fnt, fill=(255, 255, 255) if mine else dark)
            y += bh + 18
        if typing:
            d.rounded_rectangle([x0 + pad, y, x0 + pad + 150, y + lh + 24], 26, fill=(228, 230, 236))
            for i in range(3):
                on = int(T * 4) % 3 == i; cc = (120, 122, 132) if on else (176, 178, 186)
                d.ellipse([x0 + pad + 32 + i * 36, y + (lh + 24) / 2 - 9, x0 + pad + 50 + i * 36, y + (lh + 24) / 2 + 9], fill=cc)

    def appel(self, d, a, T):
        """opt-in `ui.appel` (9/11/2026): a phone CALL card drawn in 2D (same for PS1 and VOXEL) — who is on the line, a running call timer,
        a voice waveform that moves while the other person speaks, the call buttons.
        {"nom": "NORA", "sous_titre": "SECOURS 112", "couleur": [r,g,b], "debut": 12 (seconds already elapsed at the start of the shot),
         "parle": [[t0, t1], ...] (the remote voice speaks), "etat": "en_cours" | "sonne" (incoming) | "appelle" (outgoing, ringing) | "sans_reponse" |
         "termine", "termine": t, "sans_reponse": t, "entree": true, "y": top (px)} ;
        times are seconds from the start of the shot (or cut)."""
        v = self.aspect == '9:16'; W = self.L.W
        fs = 30 if v else 26; pad = 28
        x0, x1 = (110, W - 110) if v else (W / 2 - 430, W / 2 + 430)
        y0 = float(a.get('y', 300 if v else 120))
        if a.get('entree'):
            k = clamp(T / .35); y0 += (1 - ease(k)) * 260
        etat = a.get('etat', 'en_cours')
        if a.get('sans_reponse') is not None and T >= float(a['sans_reponse']): etat = 'sans_reponse'
        if a.get('decroche') is not None and T >= float(a['decroche']) and etat in ('sonne', 'appelle'): etat = 'en_cours'
        if a.get('termine') is not None and T >= float(a['termine']): etat = 'termine'
        hh = 300 if v else 250; y1 = y0 + hh
        bg = (250, 249, 246); dark = (32, 34, 42); grey = (120, 122, 132); col = tuple(a.get('couleur', (220, 70, 60)))
        d.rounded_rectangle([x0 + 10, y0 + 12, x1 + 10, y1 + 12], 34, fill=(20, 20, 26))
        d.rounded_rectangle([x0, y0, x1, y1], 34, fill=bg, outline=(214, 214, 220), width=3)
        r = 54 if v else 46; cx, cy = x0 + pad + r, y0 + pad + r
        if etat in ('sonne', 'appelle'):                                        # ringing (incoming or outgoing): pulsing rings around the avatar
            for k in range(2):
                ph = (T * 1.6 + k * .5) % 1.; rr = r + 10 + ph * 34
                d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=tuple(int(c * (1 - ph) + 250 * ph) for c in col), width=4)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
        nom = str(a.get('nom', '')).upper(); ini = nom[:1] or '?'
        iw = d.textlength(ini, font=F(fs + 14)); d.text((cx - iw / 2, cy - (fs + 14) / 2 + 1), ini, font=F(fs + 14), fill=(255, 255, 255))
        tx = cx + r + 26
        d.text((tx, cy - fs - 6), nom, font=F(fs + 4), fill=dark)
        if a.get('sous_titre'): d.text((tx, cy + 6), str(a['sous_titre']).upper(), font=F(fs - 8), fill=grey)
        secs = max(0., float(a.get('debut', 0.)) + T)
        status = {'sonne': 'APPEL ENTRANT', 'appelle': 'APPEL...' + '.' * (int(T * 2) % 3), 'sans_reponse': 'PAS DE REPONSE',
                  'termine': 'APPEL TERMINE'}.get(etat, 'APPEL EN COURS  %02d:%02d' % (int(secs) // 60, int(secs) % 60))
        sy = y0 + 2 * r + pad + 22
        d.text((x0 + pad, sy), status, font=F(fs - 6), fill=(46, 160, 90) if etat == 'en_cours' else (col if etat in ('sonne', 'appelle') else
                                                                   ((210, 60, 56) if etat == 'sans_reponse' else grey)))
        # the voice waveform: bars that move while the other person speaks, flat otherwise
        speaking = etat == 'en_cours' and any(float(p[0]) <= T < float(p[1]) for p in (a.get('parle') or []))
        n = 22; bx0, bx1 = x0 + pad, x1 - pad - (230 if v else 200); wy = sy + fs + 26
        for i in range(n):
            amp = (.25 + .75 * abs(math.sin(T * 9.1 + i * 1.7) * math.sin(T * 3.3 + i * .6))) if speaking else .12
            h = 6 + amp * (46 if v else 38); xb = bx0 + (bx1 - bx0) * i / n
            d.rounded_rectangle([xb, wy + 26 - h / 2, xb + (bx1 - bx0) / n * .55, wy + 26 + h / 2], 4, fill=col if speaking else (196, 198, 206))
        # the call buttons: speaker, mute, and the red hang-up
        by = wy + 26; br = 30 if v else 26
        for j, c_ in enumerate(((226, 60, 56), (228, 230, 236), (228, 230, 236))):
            bx = x1 - pad - br - j * (br * 2 + 16)
            d.ellipse([bx - br, by - br, bx + br, by + br], fill=c_)
            if j == 0: d.rounded_rectangle([bx - 13, by - 5, bx + 13, by + 5], 4, fill=(255, 255, 255))      # hang-up handset
            else: d.ellipse([bx - 7, by - 7, bx + 7, by + 7], fill=(120, 122, 132))

    def compose(self, lo, g, shot, T, u):
        W, H = self.L.W, self.L.H
        im = Image.fromarray(lo).resize((W, H), FIN.resample())
        fx = shot.get('fx', {}) or {}; ui = shot.get('ui', {}) or {}
        dim = float(val(fx.get('dim'), u, 0.) or 0.)
        if dim: im = Image.blend(im, Image.new('RGB', (W, H), BLACK), dim)
        d = ImageDraw.Draw(im)
        if ui.get('endcard'):
            self.endcard(im, d, ui['endcard'] if isinstance(ui['endcard'], dict) else {}, g)
            fo = max(0., (g - (self.duration - 1.3)) / 1.3)
            if fo > 0: im = Image.blend(im, Image.new('RGB', (W, H), BLACK), min(1., fo * .85))
            return im
        if ui.get('hud', True) and self.hud.get('show', True):
            x0, y0 = self.L.hud; title = self.hud.get('title', ["L'ÉTAGE 0", "N'EXISTE PAS"])
            for i, t_ in enumerate(title[:2]): outlined(d, (x0, y0 + i * 48), t_.upper(), F(40), CREAM, 4)
            if self.hud.get('part'): outlined(d, (x0, y0 + 104), self.hud['part'].upper(), F(24), RED, 3)
            clk = self.hud.get('clock')                                  # horloge de caméscope : [[temps, "02:58"], ...] (film Le Remplaçant)
            if clk:
                ct = [c_[1] for c_ in clk if g >= float(c_[0])]; ct = ct[-1] if ct else clk[0][1]
                w2 = d.textlength(ct, font=F(28)); outlined(d, (W - (52 if self.aspect == '9:16' else 52) - w2, y0 + 68), ct, F(28), CREAM, 3)
            hs = hearts_at(self.ep, self.lines, g)
            hb = ui.get('heart_break')
            if hb:
                at = float(hb.get('at', 0)) if isinstance(hb, dict) else 0.
                if T >= at and (T - at) < 1.2 and int((T - at) * 12) % 2: hs = [0] + hs[1:] if hs else hs
            hx = self.L.hearts_x(W)
            for i, v in enumerate(hs[:3]): heart(d, hx + i * 50, y0 + 4, v, 6)
            if sum(hs) == 1 and self.hud.get('last_life_label', 'DERNIÈRE VIE'):
                lab = self.hud.get('last_life_label', 'DERNIÈRE VIE').upper(); w2 = d.textlength(lab, font=F(20))
                d.text((W - (52 if self.aspect == '9:16' else 48) - w2, y0 + 60), lab, font=F(20), fill=RED)
        if ui.get('messages'): self.messages(d, ui['messages'], T)            # opt-in (9/11/2026) : messages de téléphone lisibles
        if ui.get('appel'): self.appel(d, ui['appel'], T)                     # opt-in (9/11/2026) : écran d'appel (qui parle, minuteur, voix)
        if ui.get('recap'):
            r = ui['recap']
            if T <= float(r.get('until', 1e9)): self.recap(d, r)
        if ui.get('choice'): self.choice(d, ui['choice'], g)
        if ui.get('timer'):
            k0, k1 = self.ctx.tl.spans[self.ctx.tl.at(g)[0]]
            t = max(0., (ui['timer'].get('end') if isinstance(ui['timer'], dict) and ui['timer'].get('end') else k1 - g) if True else 0)
            s = f"00:0{int(min(t, 9))}.{int((t % 1) * 10)}"
            if int(g * 6) % 2 == 0 or t < 1.5: self.center(d, 260 if self.aspect == '9:16' else 200, s, F(64), RED)
        sub_pos = ui.get('subs', 'mid')
        if sub_pos != 'off':
            s = active_sub(self.subs, g)
            if s:
                words = s['words']; fnt = F(56)
                text = ' '.join(w for w, _ in words); tw = d.textlength(text, font=fnt); x = (W - tw) / 2
                y = self.L.sub_y['choice'] if ui.get('choice') else self.L.sub_y.get(sub_pos, self.L.sub_y['mid'])
                # sous-titres surs (opt-in, captions/safe.py) : la bande du plan courant, decidee une fois
                # pour tout l'episode, plus l'ajustement de largeur. La carte de choix garde sa place a
                # elle : c'est une mise en page, pas un bandeau de dialogue.
                if self.caps is not None and not ui.get('choice'):
                    from ...captions import safe as CAPS
                    y, fnt, tw = CAPS.place3d(self.caps, self, g, sub_pos, s, d, F, y)
                    x = (W - tw) / 2
                ln = self.lines[s['line']]
                if ln.get('label'):
                    lc = LABEL_COLORS.get(ln.get('label_color', 'blue'), BLUE); lab = ln['label'].upper()
                    if not lab.startswith('-'): lab = f'- {lab} -'
                    w2 = d.textlength(lab, font=F(24)); outlined(d, ((W - w2) / 2, y - 52), lab, F(24), lc, 3)
                for w, kf in words:
                    outlined(d, (x, y), w, fnt, RED if kf else CREAM, 5); x += d.textlength(w + ' ', font=fnt)
        return im

    def frame(self, g):
        lo, shot, T, u = self.render_lowres(g)
        return self.compose(lo, g, shot, T, u)

    def raw_frame(self, g):
        """image without HUD / subtitles (thumbnails)"""
        lo = self.render_lowres(g)[0]
        return Image.fromarray(lo).resize((self.L.W, self.L.H), FIN.resample())
