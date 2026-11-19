"""Tiny helpers to write a remake scene file: camera keys, a held pose, an animation table in absolute film time."""


def k(t, pos, look, fov=60., roll=0.):
    """one camera key; t in seconds from the start of the shot"""
    pt = lambda v: v if isinstance(v, dict) else list(v)          # a point, or {"on": actor, "h": height} read from the actor's track
    return dict(t=round(t, 4), pos=pt(pos), look=pt(look), fov=fov, roll=roll)


def cam(*keys):
    """camera by keys (absolute positions, smoothstep between keys): the painter's `path` rig, no cinematographer involved"""
    return {'rig': 'path', 'keys': list(keys)}


def hold(p, yaw, **kw):
    """one key of a track: the actor stands at p with heading yaw (0 faces +z) and whatever else kw says (face, gesture, head, hands...)"""
    return [dict(t=0, p=list(p), yaw=yaw, **kw)]


def table(t0, *pairs):
    """animation table [[t_abs, value], ...] from (t_relative, value) pairs of a shot that starts at t0"""
    return [[round(t0 + t, 4), v] for t, v in pairs]


def pulse(t0, t1, period, lo=0., hi=1., phase=0.):
    """square pulse table between t0 and t1 (absolute): hi for half a period, then lo; used for blinking lights"""
    out = []; t = t0; i = 0
    while t < t1:
        out.append([round(t, 4), hi if (i + int(phase)) % 2 == 0 else lo]); out.append([round(t + period / 2 - 1e-3, 4), hi if (i + int(phase)) % 2 == 0 else lo]); t += period / 2; i += 1
    return out
