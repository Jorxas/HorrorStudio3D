"""Hand-to-hand and sword fighting as BLOCKING beats: the same discipline as `touch` / `knock` / `take` (blocking.py): a blow is a hand that really reaches a point of the world,
at a moment, from where the actor really stands, and the preflight refuses a blow that cannot land.

What a fight needs and the blocking did not have (docs/DEMO_NARRATIVE_RAPPORT_20261029.md §3):
  strike   {who, t, at: <actor>, hand 'R'|'L', kind, height, hit, dur}            one blow. kinds: jab | cross | hook (a fist), slash | thrust (a sword in the hand).
                                                                                  `hit: False` = the blow is blocked / dodged: the hand stops short of the body.
  clash    {t, a, b, hand_a, hand_b, dur}                                         two blades meet: both hands reach the same point between the fighters.
  guard    {who, t, until, hand}                                                  a hand held up in front of the face (a block, a parry) while the other keeps striking.
  flinch   {who, t, amount, dur}                                                  the torso's reaction to a blow: a backward (amount < 0) or forward (> 0) lean that rises fast and dies slowly.
  draw     {who, t, until, hand, at}                                                      the hand goes to the actor's own hip and comes up with a blade (the sword appears in the hand at t + 0.25, until `until`).
  kneel    {who, t, until, amount}                                                the actor goes down on a knee / crouches (a lying pose does not exist in the painter): ramps in 0.25 s, out in 0.4 s.
The victim's stagger is an ordinary `go` (with `backwards: True`) written by the story: it is a real path on the real grid, so a wall or a table stops it before any image.

Where the point of a blow is: straight ahead of the striking SHOULDER, along the line to the victim, at the victim's near surface, at head / chest / belly height. The painter's body is wide
(shoulders 0.38 m off the axis, arm 0.566 m), so a blow lands at 0.5-0.62 m between the two bodies; the audit (`blocking.audit_contacts`) already measures reach, facing and walls for every
contact, and `audit_fight` below adds what is specific to blows: distance at the instant of the blow, an attacker who is not facing the victim, a blow with no victim reaction, a fight with no sound.
Nothing here is random and nothing reads a clock.
"""
import math
from . import blocking as B

VERBS = ('strike', 'clash', 'guard', 'flinch', 'kneel', 'draw')
HEIGHT = {'head': 1.62, 'chest': 1.30, 'belly': 1.02, 'high': 1.75}
FIST_KINDS = ('jab', 'cross', 'hook', 'uppercut')
SWORD_KINDS = ('slash', 'thrust', 'overhead')
SOUND = {'jab': 'punch', 'cross': 'punch', 'hook': 'punch', 'uppercut': 'punch', 'slash': 'metal_hit', 'thrust': 'metal_hit', 'overhead': 'metal_hit'}
STRIKE_REACH = .62                                      # the audit's own limit (arm .566 + tolerance .06)


def _sm(k): k = max(0., min(1., k)); return k * k * (3 - 2 * k)


def pass2(A, b, t0, events):
    """called by blocking.compile_plan for a combat beat: validates the beat and records what later passes need (positions are not integrated yet)"""
    do = b['do']
    if do == 'strike':
        if b.get('kind', 'jab') not in FIST_KINDS + SWORD_KINDS: raise B.PlanError(f"strike t={t0}: coup inconnu {b.get('kind')!r} (connus : {', '.join(FIST_KINDS + SWORD_KINDS)})")
        if b.get('height', 'chest') not in HEIGHT: raise B.PlanError(f"strike t={t0}: hauteur inconnue {b.get('height')!r}")
        A.faces.append((t0 - float(b.get('turn', .45)), ('actor', b['at'])))                              # the striker turns to the victim BEFORE the blow
        events.append(dict(t=t0, who=A.id, kind='strike', at=b['at'], hand=b.get('hand', 'R'), hit=bool(b.get('hit', True)), blow=b.get('kind', 'jab'), height=b.get('height', 'chest'), dur=float(b.get('dur', .34)),
                           weapon=b.get('kind', 'jab') in SWORD_KINDS, loud=float(b.get('loud', 1.)), side=float(b.get('side', 0.))))
    elif do == 'clash':
        for who in (b['who'], b['b']): pass
        events.append(dict(t=t0, who=A.id, kind='clash', other=b['b'], hand=b.get('hand', 'R'), hand_b=b.get('hand_b', 'R'), dur=float(b.get('dur', .5)), h=float(b.get('h', 1.5)), loud=float(b.get('loud', 1.))))
        A.faces.append((t0 - .45, ('actor', b['b'])))
    elif do == 'guard':
        events.append(dict(t=t0, who=A.id, kind='guard', until=float(b['until']), hand=b.get('hand', 'L'), at=b.get('at')))
    elif do == 'flinch':
        events.append(dict(t=t0, who=A.id, kind='flinch', amount=float(b.get('amount', -.55)), dur=float(b.get('dur', .5))))
    elif do == 'kneel':
        events.append(dict(t=t0, who=A.id, kind='kneel', until=float(b['until']), amount=float(b.get('amount', 1.))))
    elif do == 'draw':
        A.faces.append((t0 - .45, ('actor', b['at'])))
        A.helds.append((t0 + .25, float(b.get('until', 1e9)), b.get('item', 'epee'), b.get('hand', 'R')))
        events.append(dict(t=t0, who=A.id, kind='draw', at=b['at'], hand=b.get('hand', 'R'), until=float(b.get('until', 1e9))))


def _pt(C, who, t): x, z = C.xz(who, t); return x, z


def resolve(C):
    """after the trajectories are integrated: turn the recorded blows into contacts (keys the painter reads) and the torso tracks (lean, crouch)"""
    from .blocking import SHOULDER_Y, SHOULDER_X, _keys, DT
    out = []
    for e in [e for e in C.events if e['kind'] in VERBS]:
        A = C.actors[e['who']]; t = e['t']
        if e['kind'] == 'strike':
            ax, az = _pt(C, e['who'], t); vx, vz = _pt(C, e['at'], t); d = math.hypot(vx - ax, vz - az) or 1.; fx, fz = (vx - ax) / d, (vz - az) / d; yaw = math.atan2(fx, fz)
            sh = B.shoulder_of(A, (ax, az), yaw, e['hand'], 0.); y_t = HEIGHT[e['height']] * A.scale
            reach = max(.2, min(STRIKE_REACH - .06, d - .30)) if e['hit'] else max(.2, min(.4, d - .55))                                   # a blocked blow stops short of the body
            if e['weapon']: reach = min(reach, .46)
            P = (sh[0] + fx * reach, y_t, sh[2] + fz * reach)
            side = -1. if e['hand'] == 'R' else 1.; rx, rz = math.cos(yaw), -math.sin(yaw)                                                   # the striker's own left-right axis on the ground
            kind = e['blow']; keys = []
            if kind in FIST_KINDS:
                back = (sh[0] - fx * .10 + side * rx * .06, sh[1] - .30 - (.1 if kind == 'uppercut' else 0.), sh[2] - fz * .10 + side * rz * .06)
                if kind == 'hook': back = (back[0] + side * rx * .22, back[1] + .10, back[2] + side * rz * .22)
                keys = [(t - .20, .95, back), (t - .04, .98, (back[0] * .4 + P[0] * .6, back[1] * .4 + P[1] * .6, back[2] * .4 + P[2] * .6)), (t, 1., P), (t + .09, .98, (P[0] - fx * .06, P[1], P[2] - fz * .06)), (t + e['dur'] - .06, .95, back)]
            else:                                                                                                                       # a sword: the hand sweeps, the blade is what meets the victim
                hi = (sh[0] + side * rx * -.05, sh[1] + .38, sh[2] - fz * .05 + side * rz * -.05)
                lo = (P[0] - side * rx * .22, y_t - .30, P[2] - side * rz * .22)
                if kind == 'thrust': hi = (sh[0], sh[1] - .05, sh[2]); lo = (P[0] + fx * .0, y_t - .1, P[2] + fz * .0)
                if kind == 'overhead': hi = (sh[0] + fx * .08, sh[1] + .42, sh[2] + fz * .08)
                keys = [(t - .24, .95, hi), (t - .05, .98, (hi[0] * .45 + P[0] * .55, hi[1] * .45 + P[1] * .55, hi[2] * .45 + P[2] * .55)), (t, 1., P), (t + .10, .98, lo), (t + e['dur'] - .06, .95, (sh[0] + fx * .25, sh[1] - .1, sh[2] + fz * .25))]
            t_a, t_b = keys[0][0] - .12, keys[-1][0] + .22
            C.contacts.append(dict(who=e['who'], hand=e['hand'], t0=t_a, t1=t_b, keys=_keys(t_a, t_b, keys, .12, .22), pose='grip' if e['weapon'] else 'fist', kind='strike', point=P, hits=[t]))
            e['_point'] = P; e['_d'] = d
            _lean(C, e['who'], t - .12, .30 if e['hit'] else .18, .45)                                                                  # the striker leans into the blow
        elif e['kind'] == 'clash':
            a, bb = e['who'], e['other']; ax, az = _pt(C, a, t); bx, bz = _pt(C, bb, t); d = math.hypot(bx - ax, bz - az) or 1.; fx, fz = (bx - ax) / d, (bz - az) / d
            M = ((ax + bx) / 2, e['h'], (az + bz) / 2); yaw_a = math.atan2(fx, fz); yaw_b = yaw_a + math.pi
            for who, hand, up in ((a, e['hand'], 0.), (bb, e['hand_b'], .06)):
                Aa = C.actors[who]; t_a, t_b = t - .35, t + e['dur'] + .25; P = (M[0], M[1] + up, M[2])
                sh0 = B.shoulder_of(Aa, (ax, az) if who == a else (bx, bz), yaw_a if who == a else yaw_b, hand, 0.); lo = (sh0[0] + (fx if who == a else -fx) * .30, sh0[1] - .25, sh0[2] + (fz if who == a else -fz) * .30)
                keys = [(t - .20, .95, lo), (t - .02, 1., P), (t + .04, 1., (P[0] + (-fx if who == a else fx) * .03, P[1] + .05, P[2])), (t + e['dur'] * .5, 1., P), (t + e['dur'], .95, lo)]
                C.contacts.append(dict(who=who, hand=hand, t0=t_a, t1=t_b, keys=_keys(t_a, t_b, keys, .15, .25), pose='grip', kind='clash', point=P, hits=[t]))
            e['_point'] = M; e['_d'] = d
        elif e['kind'] == 'guard':
            t0, t1 = t, e['until']; ts = [t0 + .0] + [t0 + (t1 - t0) * k / 6 for k in range(1, 7)]; ks = []
            for tt in ts:
                ax, az = _pt(C, e['who'], tt)
                tgt = e.get('at'); vx, vz = _pt(C, tgt, tt) if tgt in C.actors else (ax, az + 1.)
                d = math.hypot(vx - ax, vz - az) or 1.; fx, fz = (vx - ax) / d, (vz - az) / d; yaw = math.atan2(fx, fz); sh = B.shoulder_of(A, (ax, az), yaw, e['hand'], 0.)
                ks.append((tt, 1., (sh[0] + fx * .30, 1.52 * A.scale, sh[2] + fz * .30)))
            t_a, t_b = t0 - .18, t1 + .22
            C.contacts.append(dict(who=e['who'], hand=e['hand'], t0=t_a, t1=t_b, keys=_keys(t_a, t_b, ks, .18, .22), pose='fist', kind='guard', point=None, hits=[]))
        elif e['kind'] == 'draw':
            ax, az = _pt(C, e['who'], t); vx, vz = _pt(C, e['at'], t); d = math.hypot(vx - ax, vz - az) or 1.; fx, fz = (vx - ax) / d, (vz - az) / d; yaw = math.atan2(fx, fz); sh = B.shoulder_of(A, (ax, az), yaw, e['hand'], 0.)
            hip = (sh[0], sh[1] - .55 * A.scale, sh[2] - fz * .04); up = (sh[0] + fx * .30, sh[1] - .05, sh[2] + fz * .30); t_a, t_b = t - .22, t + .55
            C.contacts.append(dict(who=e['who'], hand=e['hand'], t0=t_a, t1=t_b, keys=_keys(t_a, t_b, [(t, .96, hip), (t + .16, .96, hip), (t + .38, .96, up)], .22, .17), pose='grip', kind='draw', point=hip, hits=[t]))
        elif e['kind'] == 'flinch':
            _lean(C, e['who'], t, e['amount'], e['dur'])
        elif e['kind'] == 'kneel':
            a = C.arr[e['who']]; n = len(a['x']); arr = a.setdefault('crouch', _zeros(n)); i0 = int(t / DT); i1 = min(n, int(e['until'] / DT))
            for i in range(i0, n):
                tt = i * DT
                up = _sm((tt - t) / .25); down = 1. - _sm((tt - e['until']) / .40) if tt >= e['until'] else 1.
                arr[i] = max(arr[i], e['amount'] * up * (down if tt >= e['until'] else 1.))
                if tt > e['until'] + .42: break


def _zeros(n):
    import numpy as np
    return np.zeros(n)


def _lean(C, who, t, amount, dur):
    from .blocking import DT
    a = C.arr[who]; n = len(a['lean']); i0 = max(0, int(t / DT)); i1 = min(n, int((t + dur * 2.2) / DT))
    for i in range(i0, i1):
        u = (i * DT - t) / dur
        a['lean'][i] += amount * (_sm(u / .22) if u < .22 else math.exp(-(u - .22) * 2.2)) * (1. if u >= 0 else 0.)


def audit_fight(C, fps=30):
    """what is specific to a fight, measured on the compiled blocking: a blow lands within reach (the contact audit already measures the arm), the victim is not behind the striker,
    every blow that hits has a victim who reacts (a flinch, a stagger or a kneel within 0.35 s), every blow has a sound (the SFX list is built from these events)"""
    v = []
    for e in C.events:
        if e['kind'] != 'strike': continue
        t = e['t']; d = e.get('_d', 9.)
        if d > STRIKE_REACH + .40: v.append(B.Violation('coup_trop_loin', f"{e['who']} frappe {e['at']} à {d:.2f} m : il ne l'atteint pas ({e['blow']})", t, e['who']))
        if e['hit']:
            vic = e['at']; ok = any(f['who'] == vic and f['kind'] in ('flinch', 'kneel') and -.05 <= f['t'] - t <= .35 for f in C.events) or any(m['t0'] <= t + .35 and m['t1'] >= t and m.get('back') for m in C.actors[vic].moves)
            if not ok: v.append(B.Violation('coup_sans_effet', f"{e['who']} touche {vic} (t={t:.2f}) mais {vic} ne réagit pas (ni recul, ni penché, ni à genoux dans les 0,35 s)", t, vic))
    return v
