"""PIXEL 3D eye aim -- EXPERIMENTAL, OPT-IN ONLY (episode key "eye_aim").

The shipped eyes stay the default and are never touched by this module. Without the key `active()` returns
None, `offset()` returns None, and the face painters put the pupils exactly where they have always put them,
bit for bit (tools/regress.py, tools/regress_v2.py, tools/check_regard.py).

WHY. The régie aims the HEAD at what a character looks at (acting/timeline.raw_head), and
`acting/gaze.py` plays that aim like an actor would when the episode asks. Nothing aims the EYES. Two
consequences, both measured by tools/regard_qc.py on real scenes before a line of this module was written:

1. **the neck runs out of travel and the eyes do not take over.** The régie clamps the head yaw at 0.95 rad.
   Measured over the shipped demos: `demo3_groupe` is clamped on 33 % of its samples and misses its target by
   **70 degrees on average there (worst 126)**, `demo20_decors` by 53 degrees on 6 % of them. The character is
   addressing somebody he is demonstrably not looking at;
2. **the historical coarse offset pushes the pupils to the WRONG SIDE.** `timeline` labels the gaze
   `'right'` when the head yaw is positive; a positive yaw turns the head towards local +x, which the camera
   sees on its left, while `assets.GAZE['right']` moves the iris towards local -x, i.e. the camera's right.
   The two signs are opposite, so on the 81 % of `demo6_continuite` samples where that label fires, the pupils
   sit on the side **away** from the person being spoken to. The sign is not touched in the shipped path (it
   would change every delivered video); with this key on, the pupils follow the aim instead of the label.

WHAT IT IS, AND WHAT IT IS NOT. The eyes carry **what the head could not**: `acting/timeline` now records, for
every sampled character, the part of the aim the neck failed to deliver -- the clamp of (1) and the slew lag of
the gaze controller when it is on, in radians, in the head's own frame. That residual is a pure measurement,
written next to `gaze` and `blink`, and a consumer that ignores it renders as before (CONSOLE 2D ignores it).
This module turns it into a pupil offset in face texels, and nothing else:

- no new geometry, no eyeball: the pupils are painted inside the 24x24 or 48x48 face texture, exactly where
  `assets.GAZE` already moved them, only by the right amount and in the right direction;
- no saccade, no micro-movement, no vergence, no lid coupling. The eye does not blink differently, the brows do
  not move. Those are other lots, and pretending otherwise in a close shot would be visible;
- the travel is **3 texels** of a 48-wide face at full deflection (1 on a 24-wide one, which is all it has):
  an iris 6 texels wide inside an 11-texel socket cannot do better, and this is the ceiling the measurement in
  docs/P1_INTERACTION_REGARD_20261025.md reports. An eye that needs more than `yaw` radians is simply pinned at
  full deflection, and the tool says by how much it still misses.
"""
_STATE = None

# `yaw` / `pitch`: the angle, in radians, at which the pupils reach full deflection (0.45 rad = 26 degrees
# sideways, 0.26 = 15 up or down -- a human eye does more, this style has 3 texels). `travel`: texels of iris
# travel at full deflection on a 48-wide face. `amount`: global scale, for a softer look without changing the
# geometry. `sign` is NOT a setting: the direction is derived from the texture mapping and tested.
PRESETS = {
    # the configuration retained after measurement -- see docs/P1_INTERACTION_REGARD_20261025.md
    'aim': dict(yaw=.45, pitch=.26, travel=3., amount=1.),
    # the same aim, half the travel: measured, kept reachable, NOT the retained one
    'aim_doux': dict(yaw=.45, pitch=.26, travel=2., amount=1.),
}
KEYS = tuple(sorted(PRESETS['aim']))


def register(name, **spec):
    """an extension adds its own eye preset (registry, not if/elif -- see AGENTS.md)"""
    PRESETS[name] = dict(PRESETS['aim'], **{k: v for k, v in spec.items() if k in PRESETS['aim']})
    return PRESETS[name]


def configure(spec):
    """`spec` is the episode's `eye_aim` key: None / False (off), True, a preset name, or {"style": name, ...}.
    Returns the resolved preset or None. Called once per engine, exactly like bodies.configure(ep['body'])."""
    global _STATE
    _STATE = None
    if not spec: return None
    if spec is True: name, over = 'aim', {}
    elif isinstance(spec, str): name, over = spec, {}
    elif isinstance(spec, dict):
        name = spec.get('style') or spec.get('preset') or 'aim'
        over = {k: v for k, v in spec.items() if k not in ('style', 'preset')}
    else: return None
    if name not in PRESETS: return None
    st = dict(PRESETS[name])
    for key, v in over.items():
        if key not in st: continue
        try: st[key] = max(0., min(4., float(v)))
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


def notices(ep):
    """what this aim cannot carry, said in French on the render log instead of in silence"""
    if not _STATE: return []
    out = []
    art = (ep or {}).get('art')
    nm = art if isinstance(art, str) else ((art.get('style') or art.get('preset')) if isinstance(art, dict) else None)
    if nm and nm != 'grade_only':
        out.append(f'regard "{_STATE["name"]}" : la direction artistique "{nm}" peint son propre visage '
                   f'(art.face_hd), qui garde ses pupilles d\'origine ; la visée des yeux ne s\'y applique pas')
    return out


def residual(sample):
    """-> (yaw, pitch) in radians the HEAD failed to deliver, or None. That is the whole input of this module,
    and it is measured by acting/timeline, not guessed here."""
    e = (sample or {}).get('eye')
    if not e: return None
    try: y, p = float(e[0]), float(e[1])
    except (TypeError, ValueError, IndexError): return None
    return (y, p) if (abs(y) > 1e-4 or abs(p) > 1e-4) else None


def offset(sample, size=48):
    """-> (gx, gy) pupil offset in texels of a `size`-wide face texture, or None when inert (no key, no
    residual). Integers, so the painters' lru_cache keeps working.

    SIGNS, derived and tested, not chosen (tools/check_regard.py pins both). A face texture lives on the +z
    face of the head box and `r3d` mirrors that face (`uu = 1 - uu`), so texture column 0 is at local +x and
    the columns grow towards local -x. A positive yaw turns the head towards local +x. The pupils must go the
    same way as the aim, so a positive residual yaw gives a NEGATIVE gx. Texture rows grow downwards and a
    positive pitch looks up, so a positive residual pitch gives a negative gy."""
    st = _STATE
    if not st: return None
    r = residual(sample)
    if r is None: return None
    k = float(st['amount'])
    sx = max(-1., min(1., r[0] / max(1e-6, float(st['yaw'])))) * k
    sy = max(-1., min(1., r[1] / max(1e-6, float(st['pitch'])))) * k
    # how much room the pupils actually have: 3 texels sideways and 2 up/down inside the 48x48 socket
    # (an 11-texel socket around a 6-texel iris), and exactly ONE on the 24x24 face, which is all the room
    # `assets.GAZE` has ever had there. Rounding is what keeps a residual below half a texel at zero.
    tr, trv = (float(st['travel']), float(st['travel']) * .66) if size >= 48 else (1., 1.)
    return (int(round(-sx * tr)), int(round(-sy * trv)))
