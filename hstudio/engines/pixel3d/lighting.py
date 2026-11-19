"""V3, PIXEL 3D: narrative lighting INTENTIONS per episode and per shot ("lighting" block).

The engine already owned the raw material: point lights from the set (`sets.py: lights()`), the per-shot
`lights` list and `objects: {"type": "light"}`, the `state` switches (`lights`, `lights_off`, `red`),
the deterministic `flicker_hash`, the window flashes of `world: [{"lightning": true}]`, `weather` for rain,
and the camera fill light that keeps faces readable. What was missing was a way for the STORY to say
*what the light means* in one place: a warm or cold mood, a coloured halo coming from an object,
a contre-jour, and variations synchronised with the scene.

This module is that layer, and nothing else: it re-tints and re-scales lights that already exist and adds
at most `MAX_EXTRA` point lights, never with a shadow ray (the two shadow-casting lights stay the ones the
set chose, see `frame.with_shadows`). Cost per frame is therefore a few vectorised Lambert terms, no new
`trace()` call.

Rules it follows:
  - opt-in: without a "lighting" block nothing is read and nothing changes, frame for frame;
  - deterministic: every variation comes from the frame time through `sets.flicker_hash` or `math.sin`;
  - readable faces: flicker never takes the camera fill light below `min_fill` of its nominal value;
  - explicit fallback: an unknown name or an out-of-range number is replaced by the documented default and
    reported in French on the render log (`[eclairage] ...`) and in `ctx.lighting_warnings`, never silently.

Grammar (episode "lighting" is the default, a shot's own "lighting" overrides it key by key;
`"lighting": "none"` in a shot turns the episode intention off for that shot):

{"mood": "warm|cold|neon|red|blue|green|none",   mood colour, taken from sets.LIGHTS
 "mood_power": 0..2,                             how far the mood pushes the ambience and the fill (1 = default)
 "fill": 0..2,                                   multiplies the camera fill light (face readability)
 "back": 0..2 | {"power", "color", "on", "y", "dist", "radius"},     contre-jour behind the subject
 "halo": {"from", "color", "power", "radius", "y", "flicker"} | [ ... ],   coloured halo from an object / an anchor
 "flicker": {"rate": Hz, "depth": 0..1, "shape": "square|sine|strobe|breathe", "seed", "phase",
             "on": ["halo", "set", "back", "mood"], "min_fill": 0..1},
 "storm": {"at": [s, ...] | "every": s, "power": 0..2, "flash": 0..1, "color": "cold"}}

`storm` only drives the mechanism that already exists (the double window flash of `world: lightning` plus the
full-frame flash `ctx.fx_flash`); rain stays the existing `"weather": "rain"`. A shot that already asks for
`world: [{"lightning": true}]` keeps it and `storm` is dropped with a warning (no double flash).
"""
import math
from .sets import LIGHTS, flicker_hash

MAX_EXTRA = 4                 # hard cap on the point lights this layer may add (CPU cost of shade())
MAX_HALOS = 3
MOODS = tuple(LIGHTS) + ('none',)
TARGETS = ('halo', 'set', 'back', 'mood')
KEYS = ('mood', 'mood_power', 'fill', 'back', 'halo', 'flicker', 'storm')

# ---------------------------------------------------------------- deterministic waveforms (registry, not if/elif)
SHAPES = {
    'square':  lambda t, rate, seed, ph: 0. if flicker_hash(t + ph, rate, seed) > .55 else 1.,
    'strobe':  lambda t, rate, seed, ph: float(int(t * rate * 2 + ph) % 2 == 0),
    'sine':    lambda t, rate, seed, ph: .5 + .5 * math.sin(2 * math.pi * rate * t + ph),
    'breathe': lambda t, rate, seed, ph: .5 + .5 * math.sin(2 * math.pi * rate * t + ph) * math.sin(2 * math.pi * rate * .37 * t + 1.3),
}

def wave(shape, t, rate, depth, seed=0, phase=0.):
    """variation factor in [1 - depth, 1]; `shape` names a deterministic waveform of SHAPES"""
    k = SHAPES.get(shape, SHAPES['square'])(t, max(.01, rate), int(seed), float(phase))
    return 1. - _clamp(depth, 0., 1.) * (1. - k)

# ---------------------------------------------------------------- small helpers
def _clamp(x, a, b): return a if x < a else (b if x > b else x)

def _num(ctx, where, v, default, lo, hi):
    try: x = float(v)
    except (TypeError, ValueError):
        _warn(ctx, f"{where} : « {v} » n'est pas un nombre, repli sur {default}"); return float(default)
    if not (lo <= x <= hi):
        y = _clamp(x, lo, hi); _warn(ctx, f"{where} : {x:g} hors de [{lo:g}, {hi:g}], ramené à {y:g}"); return y
    return x

def _color(ctx, where, v, default):
    """a name of sets.LIGHTS, or [r, g, b] in 0..1 (or 0..255)"""
    if v is None: return default
    if isinstance(v, str):
        if v in LIGHTS: return LIGHTS[v]
        _warn(ctx, f"{where} : couleur « {v} » inconnue (connues : {', '.join(LIGHTS)}), repli sur la couleur par défaut")
        return default
    if isinstance(v, (list, tuple)) and len(v) == 3:
        try: c = [float(x) for x in v]
        except (TypeError, ValueError):
            _warn(ctx, f"{where} : couleur « {v} » illisible, repli sur la couleur par défaut"); return default
        if max(c) > 1.001: c = [x / 255. for x in c]
        return tuple(_clamp(x, 0., 1.) for x in c)
    _warn(ctx, f"{where} : couleur « {v} » illisible, repli sur la couleur par défaut"); return default

def _warn(ctx, msg):
    """explicit fallback: said once per render, in French, and kept on the context for the tools"""
    seen = getattr(ctx, 'lighting_warnings', None)
    if seen is None: seen = []; setattr(ctx, 'lighting_warnings', seen)
    if msg not in seen:
        seen.append(msg); print(f'[eclairage] {msg}')

def _mix(c, col, k):
    return tuple(c[i] * (1 - k) + col[i] * k for i in range(3))

def _hue(c, col, k):
    """push c towards the hue of col while keeping about the same luminance (an ambience that tints, not darkens)"""
    lum = .3 * col[0] + .59 * col[1] + .11 * col[2]
    if lum <= 1e-4: return c
    n = [v / lum for v in col]
    return tuple(max(0., c[i] * (1 - k) + c[i] * n[i] * k) for i in range(3))

# ---------------------------------------------------------------- intention: read, merge, validate
def intent(ctx, shot):
    """episode "lighting" merged with the shot's own -> validated dict, or None when nothing is asked"""
    ep_i = (ctx.ep or {}).get('lighting')
    sh_i = shot.get('lighting')
    if isinstance(sh_i, str) and sh_i in ('none', 'off'): return None       # this shot opts out of the episode mood
    base = _as_dict(ctx, 'lighting (episode)', ep_i)
    over = _as_dict(ctx, 'lighting (plan)', sh_i)
    if base is None and over is None: return None
    out = dict(base or {}); out.update(over or {})
    for k in list(out):
        if k not in KEYS:
            _warn(ctx, f"lighting : clé « {k} » inconnue, ignorée (connues : {', '.join(KEYS)})"); out.pop(k)
    return out or None

def _as_dict(ctx, where, v):
    if v is None: return None
    if isinstance(v, dict): return v
    if isinstance(v, str):
        if v in MOODS: return {'mood': v}                                   # shorthand "lighting": "warm"
        _warn(ctx, f"{where} : « {v} » n'est ni une ambiance connue ({', '.join(MOODS)}) ni un bloc, intention ignorée"); return None
    _warn(ctx, f"{where} : bloc illisible ({type(v).__name__}), intention ignorée"); return None

def _flicker(ctx, it):
    f = it.get('flicker')
    if f is None: return None
    if f is True: f = {}
    elif isinstance(f, (int, float)): f = {'rate': float(f)}                # "flicker": 6 -> 6 Hz, usual depth
    elif not isinstance(f, dict):
        _warn(ctx, f"lighting.flicker : « {f} » illisible, scintillement ignoré"); return None
    shape = f.get('shape', 'square')
    if shape not in SHAPES:
        _warn(ctx, f"lighting.flicker.shape : « {shape} » inconnue (connues : {', '.join(SHAPES)}), repli sur square"); shape = 'square'
    on = f.get('on', ['halo'])
    if isinstance(on, str): on = [on]
    if not isinstance(on, (list, tuple)): on = ['halo']
    good = [t for t in on if t in TARGETS]
    for t in on:
        if t not in TARGETS: _warn(ctx, f"lighting.flicker.on : « {t} » inconnue (connues : {', '.join(TARGETS)}), ignorée")
    return dict(rate=_num(ctx, 'lighting.flicker.rate', f.get('rate', 6.), 6., .05, 40.),
                depth=_num(ctx, 'lighting.flicker.depth', f.get('depth', .7), .7, 0., 1.),
                shape=shape, seed=int(_num(ctx, 'lighting.flicker.seed', f.get('seed', 0), 0, -1e6, 1e6)),
                phase=_num(ctx, 'lighting.flicker.phase', f.get('phase', 0.), 0., -100., 100.),
                on=good or ['halo'], min_fill=_num(ctx, 'lighting.flicker.min_fill', f.get('min_fill', .55), .55, 0., 1.))

# ---------------------------------------------------------------- the camera fill light
def fill_index(L, cam_pos, nset):
    """index of the soft light the sets put at the camera so faces stay readable (None: this set has none)"""
    for i in range(min(nset, len(L)) - 1, -1, -1):
        p, c, inten, rad = L[i][:4]
        if rad <= 4.1 and math.hypot(p[0] - cam_pos[0], p[2] - cam_pos[2]) < .4: return i
    return None

# ---------------------------------------------------------------- subject of a contre-jour
def _subject(st, actors, cam, on):
    from .frame import anchor_xyz
    pos = cam[0]
    if on is not None:
        p = anchor_xyz(st, on, actors, 1.5)
        return (float(p[0]), float(p[1]), float(p[2]))
    best = None
    for a in (actors or {}).values():
        if 'x' not in a or 'z' not in a: continue
        d = math.hypot(a['x'] - pos[0], a['z'] - pos[2])
        if best is None or d < best[0]: best = (d, (a['x'], 1.5 + a.get('yoff', 0.), a['z']))
    if best is not None: return best[1]
    yaw = cam[1]
    return (pos[0] + math.sin(yaw) * 3., 1.5, pos[2] + math.cos(yaw) * 3.)

# ---------------------------------------------------------------- the one entry point
def plan(ctx, shot, st, actors, cam, sc, L, nset, T, u, g):
    """apply the shot's lighting intention.

    L: the lights of the frame, the first `nset` of them coming from the set (its fill light included).
    -> (L, extra): L keeps the shadow-casting candidates, `extra` is appended after `with_shadows`
    so the added lights never cost a shadow ray."""
    it = intent(ctx, shot)
    if not it: return L, []
    cam_pos = cam[0]
    fi = fill_index(L, cam_pos, nset)
    fk = _flicker(ctx, it)
    extra = []

    # ---- mood: re-tint the ambience and the fill light, no light added
    mood = it.get('mood', 'none')
    if not isinstance(mood, str) or mood not in MOODS:
        _warn(ctx, f"lighting.mood : « {mood} » inconnue (connues : {', '.join(MOODS)}), repli sur none"); mood = 'none'
    mp = _num(ctx, 'lighting.mood_power', it.get('mood_power', 1.), 1., 0., 2.)
    mcol = LIGHTS.get(mood)
    mk = 1.
    if fk and 'mood' in fk['on']: mk = wave(fk['shape'], g, fk['rate'], fk['depth'], fk['seed'], fk['phase'])
    if mcol is not None and mp > 0:
        k = _clamp(.5 * mp * mk, 0., 1.)
        sc.ambient = _hue(tuple(sc.ambient), mcol, k)
        sc.fog = _hue(tuple(sc.fog), mcol, k)

    # ---- set lights: synchronised variation (the fill keeps a floor so faces stay readable)
    dim_set = bool(fk and 'set' in fk['on'])
    if dim_set:
        k = wave(fk['shape'], g, fk['rate'], fk['depth'], fk['seed'], fk['phase'])
        for i in range(min(nset, len(L))):
            p, c, inten, rad = L[i][:4]
            if rad >= 50: continue                                   # the sun / the sky: a storm is not a loose contact
            L[i] = (p, c, inten * (max(k, fk['min_fill']) if i == fi else k), rad) + tuple(L[i][4:])

    # ---- fill: face readability, and the mood colour on the skin
    fmul = _num(ctx, 'lighting.fill', it.get('fill', 1.), 1., 0., 2.) if 'fill' in it else 1.
    if fi is not None:
        p, c, inten, rad = L[fi][:4]
        if mcol is not None and mp > 0: c = _mix(c, mcol, _clamp(.6 * mp, 0., 1.))
        L[fi] = (p, c, inten * fmul, rad) + tuple(L[fi][4:])
        if dim_set:
            # the set lights are being dimmed, so the soft light sitting at the camera would win the shadow-ray
            # budget of `frame.with_shadows` (expensive, and a light at the eye casts almost no visible shadow):
            # it leaves the shadow candidates and comes back as an extra light instead.
            extra.append(tuple(L[fi][:4]) + (False,)); L.pop(fi); nset -= 1; fi = None
    elif (fmul != 1. or (mcol is not None and mp > 0)) and len(extra) < MAX_EXTRA:
        c = _mix((.62, .72, 1.0), mcol, _clamp(.6 * mp, 0., 1.)) if mcol is not None else (.62, .72, 1.0)
        extra.append(((cam_pos[0], cam_pos[1] + .25, cam_pos[2]), c, .28 * fmul, 1.8, False))

    # ---- contre-jour: one light behind the subject, seen from the camera
    raw_back = it.get('back')
    if raw_back is not None and raw_back is not False:
        if isinstance(raw_back, dict): bk = raw_back
        elif isinstance(raw_back, (int, float)) and not isinstance(raw_back, bool): bk = {'power': raw_back}
        elif raw_back is True: bk = {}
        else:
            _warn(ctx, f"lighting.back : « {raw_back} » illisible, repli sur la puissance 1"); bk = {}
        bp = _num(ctx, 'lighting.back.power', bk.get('power', 1.), 1., 0., 2.)
        if bp > 1e-3:
            sx, sy, sz = _subject(st, actors, cam, bk.get('on'))
            dx, dz = sx - cam_pos[0], sz - cam_pos[2]
            d = math.hypot(dx, dz) or 1.
            dist = _num(ctx, 'lighting.back.dist', bk.get('dist', 1.6), 1.6, .2, 12.)
            y = _num(ctx, 'lighting.back.y', bk.get('y', 2.1), 2.1, .1, 20.)
            rad = _num(ctx, 'lighting.back.radius', bk.get('radius', 3.), 3., .3, 20.)
            col = _color(ctx, 'lighting.back.color', bk.get('color'), LIGHTS.get(mood) or (.86, .92, 1.0))
            k = wave(fk['shape'], g, fk['rate'], fk['depth'], fk['seed'], fk['phase']) if (fk and 'back' in fk['on']) else 1.
            if len(extra) < MAX_EXTRA:
                extra.append(((sx + dx / d * dist, y, sz + dz / d * dist), col, bp * k, rad, False))
            else: _warn(ctx, f"lighting.back : plus de {MAX_EXTRA} lumières ajoutées, contre-jour abandonné")

    # ---- halos: a coloured light that comes from an object (a console, an alarm, a fire)
    halos = it.get('halo')
    if halos is not None:
        if isinstance(halos, dict): halos = [halos]
        if not isinstance(halos, list):
            _warn(ctx, f"lighting.halo : « {halos} » illisible (attendu un bloc ou une liste), halo ignoré"); halos = []
        if len(halos) > MAX_HALOS:
            _warn(ctx, f"lighting.halo : {len(halos)} halos demandés, les {MAX_HALOS} premiers sont gardés (coût CPU)")
            halos = halos[:MAX_HALOS]
        for n, h in enumerate(halos):
            if not isinstance(h, dict):
                _warn(ctx, f"lighting.halo[{n}] : « {h} » illisible, halo ignoré"); continue
            if h.get('from') is None:
                _warn(ctx, f"lighting.halo[{n}] : « from » manquant (repère, acteur ou [x, z]), halo ignoré"); continue
            hp = _num(ctx, f'lighting.halo[{n}].power', h.get('power', .8), .8, 0., 3.)
            if hp <= 1e-3: continue
            from .frame import anchor_xyz
            # 80 m: a lantern, a tower top or a rooftop sign is a real light source (phare_foret: lantern at 21.5 m ; the old
            # bound of 20 m put the palm-insert halo 1.5 m BELOW the palm, outside its radius, so it lit nothing)
            hy = _num(ctx, f'lighting.halo[{n}].y', h.get('y', 1.1), 1.1, .02, 80.)
            p = anchor_xyz(st, h['from'], actors, hy)
            if 'y' in h: p = (p[0], hy, p[2])
            col = _color(ctx, f'lighting.halo[{n}].color', h.get('color', 'green'), LIGHTS['green'])
            rad = _num(ctx, f'lighting.halo[{n}].radius', h.get('radius', 2.2), 2.2, .2, 20.)
            hf = _flicker(ctx, h) if h.get('flicker') is not None else (fk if (fk and 'halo' in fk['on']) else None)
            k = wave(hf['shape'], g, hf['rate'], hf['depth'], hf['seed'] + n, hf['phase']) if hf else 1.
            if len(extra) >= MAX_EXTRA:
                _warn(ctx, f"lighting.halo[{n}] : plus de {MAX_EXTRA} lumières ajoutées, halo abandonné"); continue
            extra.append((tuple(float(v) for v in p), col, hp * k, rad, False))

    # ---- storm: the window flashes that already exist (world: lightning), driven by the intention
    storm = it.get('storm')
    if storm is True: storm = {}
    if storm is not None and not isinstance(storm, dict):
        _warn(ctx, f"lighting.storm : « {storm} » illisible, orage ignoré"); storm = None
    if storm is not None:
        if any(w.get('lightning') for w in (shot.get('world') or []) if isinstance(w, dict)):
            _warn(ctx, "lighting.storm : le plan demande déjà « world: lightning », orage de l'intention ignoré (pas de double éclair)")
        else:
            ats = storm.get('at')
            if ats is None and storm.get('every') is not None:
                ev = _num(ctx, 'lighting.storm.every', storm['every'], 2.5, .3, 60.)
                n0 = math.floor(T / ev); ats = [n0 * ev, (n0 - 1) * ev]
            elif isinstance(ats, (int, float)): ats = [float(ats)]
            elif not isinstance(ats, list):
                if ats is not None: _warn(ctx, f"lighting.storm.at : « {ats} » illisible, repli sur un éclair à 0 s")
                ats = [0.]
            sp = _num(ctx, 'lighting.storm.power', storm.get('power', 1.), 1., 0., 2.)
            fl = _num(ctx, 'lighting.storm.flash', storm.get('flash', .3), .3, 0., 1.)
            col = _color(ctx, 'lighting.storm.color', storm.get('color', 'cold'), (.72, .8, 1.0))
            for ts in ats:
                try: dt = T - float(ts)
                except (TypeError, ValueError):
                    _warn(ctx, f"lighting.storm.at : « {ts} » n'est pas un temps, éclair ignoré"); continue
                if not (0 <= dt < .9): continue
                k = math.exp(-dt * 9) + .7 * math.exp(-max(0., dt - .22) * 12) * (dt > .22)
                ctx.fx_flash = max(float(getattr(ctx, 'fx_flash', 0.)), fl * min(1., k))
                for wp in _storm_points(st)[:max(0, MAX_EXTRA - len(extra))]:
                    extra.append(((wp[0], 1.8, wp[1]), col, 7. * k * sp, 9., False))
    return L, extra

def _storm_points(st, n=2):
    """where a flash comes from: the windows of the set (the mechanism of world: lightning), else its centre"""
    from .acted import _windows
    return _windows(st)[:n]
