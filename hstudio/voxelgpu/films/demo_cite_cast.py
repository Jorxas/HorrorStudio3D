"""Casting and crowd of « Le Dernier Noyau » : the three protagonists, the look of every extra, and the generator of a living street.

The crowd is data + a deterministic generator (no random module, no clock): `pedestrian()` writes a back-and-forth walk along a LANE (a fixed z on a pavement) with stops, `bystander()` a person who
stands, glances and gestures. Lanes are chosen so that two people never share a lane in opposite directions (the blocking's overlap audit would refuse it) and so that the heroes' own lanes are free.
"""
import math

PAL_TOP = [0x3a6ab0, 0x2a8a5a, 0xd8a03a, 0x6a3a8a, 0xc84a3a, 0x4a4a52, 0xe8e4dc, 0x2a2a30, 0x8a3a2a, 0x3a8a8a, 0xb8508a, 0x6a7a3a, 0x2a4a7a, 0xd0c070, 0x7a4a2a, 0x9aa0a8]
PAL_PANTS = [0x2a3a5a, 0x2a2a30, 0x5a4a3a, 0x3a3a42, 0x4a5a3a, 0x6a5a4a, 0x1a2030, 0x7a6a5a]
SKIN = [0xf0a874, 0xc88a5a, 0x8a5a3a, 0xf2c4a0, 0x6a4028, 0xe8b088, 0xd89868, 0xa8704a]
HAIR_C = [0x1a1210, 0x2a1a14, 0x5a3a20, 0xc8a050, 0x8a5a2a, 0xb8b0a8, 0x3a2a1a, 0x7a3a1a]
HAIR_S = ['curly', 'long', 'longStraight', 'curly', 'long']
TOP_T = ['hoodie', 'jacketOpen', 'coat', 'hoodie', 'jacketOpen']


def _h(i, k):
    x = math.sin(i * 12.9898 + k * 78.233) * 43758.5453
    return x - math.floor(x)


def extra_cast(i, role='npc'):
    """a deterministic look for extra number i (skin, hair, top, trousers, shoes, stature, sometimes a beanie)"""
    pick = lambda lst, k: lst[int(_h(i, k) * len(lst)) % len(lst)]
    look = dict(skin=pick(SKIN, 1), hair=dict(style=pick(HAIR_S, 2), color=pick(HAIR_C, 3), color2=pick(HAIR_C, 4)), top=dict(type=pick(TOP_T, 5), color=pick(PAL_TOP, 6), shirt=pick(PAL_TOP, 7)),
                pants=dict(color=pick(PAL_PANTS, 8)), shoes=dict(type='sneaker', color=pick(PAL_PANTS, 9), sole=0xeeeeee))
    if _h(i, 10) < .25: look['hat'] = dict(type='beanie', color=pick(PAL_TOP, 11), fur=0xf2eee8)
    return dict(preset='npc', variant=i % 6, look=look, scale=round(.93 + .12 * _h(i, 12), 3))


HEROES = {
    'ines': dict(preset='lina'),
    'malo': dict(preset='noe', look=dict(top=dict(type='jacketOpen', color=0x2f4a6a, shirt=0xe8e4dc), pants=dict(color=0x2a2a30))),
    'vorn': dict(preset='npc', variant=2, look=dict(skin=0xc88a5a, hair=dict(style='curly', color=0x1a1210, color2=0x2a1a14), top=dict(type='coat', color=0x1c3a2a), pants=dict(color=0x1a1a1e), shoes=dict(type='boot', color=0x2a1a10)), scale=1.0),
}


def pedestrian(aid, lane_z, x_a, x_b, v, phase, t_end, stops=(), t0=0.):
    """-> (start spec, beats) of a person walking back and forth between x_a and x_b on the lane z = lane_z at v m/s, starting `phase` (0..1) of the way, with `stops` = [(leg, seconds)] standing
    in front of a window (a look + a pause). Legs are `go` beats written back to back; every beat ends at its own time so the next starts exactly there."""
    x = x_a + (x_b - x_a) * phase; d = 1. if phase < .5 else -1.; beats = []; t = t0; leg = 0; start = dict(at=[x, lane_z], yaw=math.pi / 2 if d > 0 else -math.pi / 2)
    while t < t_end - .2:
        tgt = x_b if d > 0 else x_a; dist = abs(tgt - x); dur = dist / v
        if dur < .8: d = -d; continue
        beats.append(dict(who=aid, t=round(t, 3), do='go', to=[tgt, lane_z], by=round(t + dur, 3)))
        t += dur + .05; x = tgt; d = -d; leg += 1
        for (lg, sec) in stops:
            if lg == leg:
                beats.append(dict(who=aid, t=round(t, 3), do='look', at=[x, lane_z - 4.]))
                t += sec; beats.append(dict(who=aid, t=round(t, 3), do='look'))
    return start, beats


def bystander(aid, at, yaw, t_end, looks=(), emotes=()):
    """a person who stands where he is: glances at points of interest at given times"""
    beats = []
    for (t, tgt) in looks: beats.append(dict(who=aid, t=t, do='look', at=tgt) if tgt is not None else dict(who=aid, t=t, do='look'))
    for (t, f) in emotes: beats.append(dict(who=aid, t=t, do='emote', face=f))
    return dict(at=list(at), yaw=yaw), beats
