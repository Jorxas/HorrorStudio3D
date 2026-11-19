"""Extension "helicopter": a helicopter for the PIXEL 3D engine and the sound of its rotor.

Built for the request library/extensions/requests/prop_helicopter.json (the planner found "hélicoptère" in
« Léa saute vers un hélicoptère » and the engine had none). Local frame: origin on the cabin floor, nose towards +z
(so that a "mover" flies it nose first), left door open (-x side) so that a character can be seen boarding.
Animated when it is a mover (p["_t"] = time): rotor blades in four positions, blinking lights. Deterministic."""
import math
import numpy as np
from hstudio.engines.pixel3d.r3d import C, M_METAL
from hstudio.audio import synth as S

def _blade(cx, y, cz, ang, R, step=.42, w=.14):
    """a blade through the hub as small boxes along its direction (diagonals read as pixel-art stairs)"""
    out = []; ca, sa = math.cos(ang), math.sin(ang); n = int(2 * R / step)
    for k in range(n + 1):
        r = -R + k * step
        out.append(C((cx + ca * r, y, cz + sa * r), (abs(ca) * step + w, .04, abs(sa) * step + w), (38, 38, 42)))
    return out

def build(p, c):
    t = float(p.get('_t', 0.)); body = tuple(c) if c else (196, 36, 36); white = (236, 236, 236); dark = tuple(int(v * .7) for v in body)
    m = dict(mat=M_METAL)
    out = [C((x, -.85, .25), (.09, .09, 3.3), (50, 52, 56), **m) for x in (-.85, .85)]                     # skids
    out += [C((x * .78, -.45, z), (.07, .8, .07), (50, 52, 56)) for x in (-1, 1) for z in (-.7, 1.1)]
    out += [C((0, -.22, .3), (1.84, .45, 3.4), body, **m),                                                 # belly
            C((.93, .8, .1), (.08, 1.6, 2.8), body, **m),                                                  # right wall
            C((-.93, .8, 1.25), (.08, 1.6, .26), body, **m), C((-.93, .8, -1.2), (.08, 1.6, .32), body, **m),   # door pillars (left open)
            C((0, .8, -1.42), (1.84, 1.6, .1), body, **m), C((0, 1.66, .1), (1.92, .12, 3.0), body, **m),
            C((0, .86, 2.0), (1.72, 1.2, 1.0), (70, 110, 150), refl=.4, emis=.12),                        # cockpit glass
            C((0, .3, 2.62), (1.4, .7, .5), body, **m), C((0, 1.96, -.45), (1.0, .5, 1.6), dark, **m),     # nose, engine
            C((0, 1.1, -3.45), (.42, .42, 4.2), body, **m), C((0, 1.72, -5.35), (.1, 1.15, .62), body, **m),   # tail boom, fin
            C((0, 1.18, -5.0), (1.3, .08, .42), dark, **m),
            C((.975, .62, .1), (.01, .2, 2.8), white), C((.975, .62, .1), (.012, .2, .2), white),            # stripe
            C((0, .15, .1), (1.7, .02, 2.6), (60, 62, 66)), C((0, .5, -1.05), (1.5, .5, .5), (40, 40, 46)),     # cabin floor, bench
            C((0, 2.32, -.35), (.12, .32, .12), (90, 92, 98), **m)]                                        # mast
    k = int(t * 30) % 4; ang = k * math.pi / 4                                                             # main rotor: 4 positions
    out += _blade(0., 2.5, -.35, ang, 5.0) + _blade(0., 2.5, -.35, ang + math.pi / 2, 5.0)
    tail = [C((.26, 1.72, -5.4), (.04, 1.1, .12), (38, 38, 42)), C((.26, 1.72, -5.4), (.04, .12, 1.1), (38, 38, 42))]
    out.append(tail[int(t * 30) % 2])
    out += [C((-1.0, 1.0, 1.35), (.1, .1, .1), (255, 40, 40), emis=3., cast=False), C((1.0, 1.0, 1.35), (.1, .1, .1), (40, 255, 90), emis=3., cast=False),
            C((0, -.42, 2.45), (.34, .2, .34), (255, 250, 220), emis=3.5, cast=False)]                     # nav lights, searchlight
    if int(t * 2.5) % 3 == 0: out.append(C((0, 2.0, -5.6), (.12, .12, .12), (255, 255, 255), emis=4., cast=False))   # strobe
    return out

LIGHTS = [((0, -.7, 3.2), (1., .96, .86), 3.2, 16., False), ((0, 1.35, .1), (.9, .95, 1.), .7, 3.2, False)]

def rotor(dur=6.):
    n = int(dur * S.SR); t = np.arange(n) / S.SR
    chop = (.5 + .5 * np.cos(2 * np.pi * 17.5 * t)) ** 6
    x = S.lp(S.brown(n), 420) * (.35 + 1.1 * chop) + np.sin(2 * np.pi * 35 * t) * chop * .25 + np.sin(2 * np.pi * 2150 * t) * .012
    fade = np.clip(t / .8, 0, 1) * np.clip((dur - t) / .8, 0, 1)
    return (x * fade * .7).astype(np.float32)

def register(api):
    api.prop('helicopter', build, lights=LIGHTS, terms=['helicoptere', 'helico', 'helicopter', 'chopper'], label='hélicoptère (rotor animé, projecteur, feux)')
    api.sfx('rotor', rotor, 'rotor d\'hélicoptère (durée)', long=True, terms=['rotor', 'bruit d\'helicoptere'])
