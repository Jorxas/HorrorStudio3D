"""PIXEL 3D image finish -- EXPERIMENTAL, OPT-IN ONLY (episode key "finish").

The shipped PIXEL 3D image stays the default and is never touched by this module. Without the key `active()`
returns None, `scale()` is 1, `levels()` hands back whatever default it was given, `filter()` is NEAREST, and
every frame is the same bytes it was before (tools/regress.py, tools/regress_v2.py, tools/check_finish.py).

WHY. The owner's reference images are cubic geometry in a SMOOTH, clean, anti-aliased image. This engine
draws the first and cannot draw the second, and the reason is one number: the 3D image is ray-cast at
**216x384** (82 944 rays) and blown up to 1080x1920 with `Image.NEAREST`. Every edge is therefore a 5-pixel
staircase, every shadow boundary is 5 pixels wide, and every procedural material is sampled five times too
coarsely. No grading, no palette and no lighting intention can undo that, because the information was never
computed. The three knobs below are the three places where it is thrown away:

| knob | what it is | what it buys | what it costs |
|---|---|---|---|
| `scale` | multiplier on the native raster (`r3d.configure`) | anti-aliasing, finer shadows, finer materials, real depth in the set | rays grow as the SQUARE: scale 2 = 4x the ray budget |
| `palette` | the ordered-dither palette step of `r3d.pixelate` / `art.quantise` | smooth gradients instead of banding on walls, skin and fog | nothing measurable |
| `filter` | the resampling filter from the raster to 1080x1920 | NEAREST keeps the staircase; LANCZOS resolves the supersampled edge | nothing measurable |

WHAT THIS IS NOT. It is not a new renderer, not a GPU path and not a mesh pipeline. It spends more rays on
the renderer that exists, so what it buys is sampling, never new geometry and never new material.

AND THE SERIES IS NOT CONVERGED AT `scale` 4, which is the honest reading of the measurement and not the one
I expected. Against the best raster measured (x4), the structural error of a frame falls 13.4 -> 7.2 -> 4.7
-> 3.1 for x1-smooth, x2, x3. Each step still removes error; it just costs the SQUARE of the factor, so the
error removed per second collapses. Nothing here establishes where more rays would stop paying, because the
series was never pushed past x4 -- only the cost curve is established. See
docs/P1_MINECRAFT_PROTO_20261025.md.

THE CHEAPEST STEP IS NOT SUPERSAMPLING. Removing the palette step and resampling with LANCZOS, at the
SHIPPED raster (`lisse_seul`), takes that error from 13.4 to 7.2 -- half the distance -- for no measurable
time at all (it even skips an HSV round trip). Supersampling is what buys the second half, and it is what
costs.

DELIBERATELY NOT PIXELATED, and that is the point of `palette`. The shipped look quantises to 12 values /
5 saturations / 20 degree hue steps on a 4x4 dither -- a deliberate pixel-art move. The reference images are
not pixel art: they are cubes, cleanly lit and cleanly resolved. `palette: 0` removes the step entirely;
`palette: 0.5` keeps a fine one. Neither touches the geometry, which stays cubic to the millimetre.

    "finish": "net"                                   the retained preset (see PRESETS)
    "finish": {"style": "net", "scale": 3}            same, tuned
    "finish": false | absent                          the shipped image, bit for bit
"""
_STATE = None

# `scale` is an integer multiplier on the 216x384 (or 384x216) native raster. `palette` is how much of the
# shipped palette step survives: 0 = none (smooth), 1 = the shipped one; in between the levels are
# interpolated towards a finer palette. `filter` names the PIL resampling used to reach 1080x1920.
PRESETS = {
    # the configuration retained after measurement -- see docs/P1_MINECRAFT_PROTO_20261025.md
    'net': dict(scale=3, palette=0., filter='lanczos'),
    # half the rays of `net`, for a machine in a hurry: measured, kept reachable
    'net_rapide': dict(scale=2, palette=0., filter='lanczos'),
    # the biggest raster measured. It is the yardstick the others are compared against, NOT a converged
    # image and NOT the retained preset: at ~7.4 s per frame it is there to show the shape of the cost curve
    'net_max': dict(scale=4, palette=0., filter='lanczos'),
    # the supersampling alone, shipped palette kept: isolates what the palette step costs in smoothness
    'net_palette': dict(scale=3, palette=1., filter='lanczos'),
    # the resampling alone, shipped raster: isolates what NEAREST costs, and shows it is NOT the main defect
    'lisse_seul': dict(scale=1, palette=0., filter='lanczos'),
}
KEYS = tuple(sorted(PRESETS['net']))
FILTERS = ('nearest', 'lanczos', 'box', 'bicubic')


def register(name, **spec):
    """an extension adds its own finish preset (registry, not if/elif -- see AGENTS.md)"""
    PRESETS[name] = dict(PRESETS['net'], **{k: v for k, v in spec.items() if k in PRESETS['net']})
    return PRESETS[name]


def configure(spec):
    """`spec` is the episode's `finish` key: None / False (off), a preset name, or {"style": name, ...}.
    Returns the resolved preset or None. Called once per engine, exactly like art.configure(ep['art'])."""
    global _STATE
    _STATE = None
    if not spec: return None
    if spec is True: name, over = 'net', {}
    elif isinstance(spec, str): name, over = spec, {}
    elif isinstance(spec, dict):
        name = spec.get('style') or spec.get('preset') or 'net'
        over = {k: v for k, v in spec.items() if k not in ('style', 'preset')}
    else: return None
    if name not in PRESETS: return None
    st = dict(PRESETS[name])
    for key, v in over.items():
        if key not in st: continue
        if key == 'filter':
            if isinstance(v, str) and v.lower() in FILTERS: st[key] = v.lower()
            continue
        if key == 'scale':
            try: st[key] = max(1, min(4, int(round(float(v)))))
            except (TypeError, ValueError): pass
            continue
        try: st[key] = max(0., min(1., float(v)))
        except (TypeError, ValueError): pass
    st['name'] = name
    _STATE = st
    return st


def use(state):
    """re-assert a resolved preset before rendering (the spawn pool rebuilds the engine per worker)"""
    global _STATE
    _STATE = state
    return state


def active(): return _STATE


def scale():
    """the native raster multiplier; 1 without the key, so `r3d.configure(aspect, finish.scale())` is the
    shipped raster to the integer"""
    return int(_STATE['scale']) if _STATE else 1


def levels(default):
    """`default` is the (vlev, slev, hstep) the call site would have used. -> what it must use now.

    Returns `None` (meaning "keep your own default", so the call is bit-identical) when inert; `False` (no
    palette step at all) at `palette: 0`; otherwise a finer triple interpolated towards it. The call site
    never has to know which preset is on."""
    if not _STATE: return None
    p = float(_STATE['palette'])
    if p <= 0.: return False
    if p >= 1.: return None
    v, s, h = default
    # towards a palette fine enough to stop banding: 4x the value steps, 3x the saturations, 4x the hue steps
    return (int(round(v + (v * 4 - v) * (1 - p))), int(round(s + (s * 3 - s) * (1 - p))),
            float(h / (1 + 3 * (1 - p))))


def resample():
    """the PIL resampling filter from the native raster to the delivered frame; NEAREST without the key"""
    from PIL import Image
    if not _STATE: return Image.NEAREST
    return {'nearest': Image.NEAREST, 'lanczos': Image.LANCZOS,
            'box': Image.BOX, 'bicubic': Image.BICUBIC}.get(_STATE['filter'], Image.NEAREST)


def notices(ep):
    """what this finish costs and what it cannot do, said in French on the render log instead of in silence"""
    if not _STATE: return []
    n = int(_STATE['scale'])
    out = [f'finition "{_STATE["name"]}" : raster natif x{n} ({n * n}x les rayons du rendu livré), '
           f'palette {"supprimée" if float(_STATE["palette"]) <= 0 else "réduite"}, '
           f'rééchantillonnage "{_STATE["filter"]}"']
    if n >= 4:
        out.append('finition : x4 est le plus gros raster mesuré, et la série n\'y est PAS convergée ; '
                   'chaque pas enlève encore de l\'erreur, mais il coûte le carré du facteur — '
                   'voir docs/P1_MINECRAFT_PROTO_20261025.md')
    return out
