"""Virtual cinematographer, shared by both engines: camera intentions -> camera placement.

"camera": {"shot": "establishing|wide|full|medium|close|extreme_close|two_shot|dialogue|group|ots|pov|insert",
           "on": ["lea", "tom"] (subjects; default: the characters of the shot), "speaker": "lea" (for ots / dialogue),
           "angle": "front|three_quarter|side|back|low|high", "side": "left|right" (which side of the line of action),
           "from": [x, z] or an anchor name (the side of the set the camera films from; the solver keeps it if it can),
           "move": "static|dolly_in|dolly_out|follow|track|orbit|handheld|crane_up|crane_down", "amount": 0..1}

Principles: frame by moving the camera (distance from the wanted image height and the lens), never by zooming;
eye line on the upper third; three-quarter views by default; the camera stays on one side of the line between two
characters who talk (180-degree rule, kept from shot to shot); every subject must be visible: candidate positions are
tested with probes supplied by the engine and the camera never stands inside the set.
9:16 and 16:9 are framed natively: the image height drives the distance, the width is checked so that every subject
fits; in a narrow 9:16 frame a conversation becomes over-the-shoulder shots instead of a far two-shot."""
import math

SIZES = {'extreme_close': .32, 'close': .62, 'medium': 1.15, 'medium_full': 1.55, 'full': 2.25, 'wide': 4.2, 'establishing': 7.5}
LENS = {'extreme_close': 42, 'close': 46, 'medium': 50, 'medium_full': 52, 'full': 55, 'wide': 62, 'establishing': 68,
        'ots': 46, 'pov': 70, 'insert': 50}
# how far the face may be turned away from the camera before the flat side of the blocky head fills the frame (rad)
FACE_CONE = {'extreme_close': .88, 'close': 1.05, 'medium': 1.20, 'medium_full': 1.35, 'ots': 1.05}
FACE_TRACK_DEFAULT = False      # engines ask for face-aware framing per episode ("camera_face_track") or per shot ("face_track")
# share of the image width a head may take, by size of shot: a blocky head is much wider than a real one, and in a
# narrow 9:16 frame it is the width that sets the distance, so a close shot built for a real head crops the skull
HEAD_SHARE = {'extreme_close': .85, 'close': .66, 'medium': .40, 'medium_full': .30}

def wrap(a): return (a + math.pi) % (2 * math.pi) - math.pi
def smooth(x): x = min(1., max(0., x)); return x * x * (3 - 2 * x)

class Subject:
    __slots__ = ('id', 'x', 'z', 'heading', 'eye', 'height', 'base', 'gaze', 'gazes', 'head_w', 'arms')
    def __init__(s, id_, x, z, heading, eye=1.62, height=1.85, base=0., gaze=None, gazes=(), head_w=None, arms=()):
        s.id = id_; s.x = x; s.z = z; s.heading = heading; s.eye = eye; s.height = height; s.base = base      # base: level of the feet (V3)
        s.gaze = gaze                                                  # absolute azimuth the face points at (body heading + head yaw); None: unknown
        s.gazes = tuple(gazes) or ((gaze,) if gaze is not None else ())  # that azimuth sampled over the shot (the head turns while it plays)
        s.head_w = head_w                                              # real width of the head in metres; None: the historical table decides
        s.arms = tuple(arms)        # where his OWN elbows / forearms / hands are, one tuple of world points per
                                    # sampled moment of the shot. Empty: the engine says nothing and nothing changes.

def face_offs(s, pos):
    """angles between the face axis of a subject and the direction of the camera (rad), one per sampled moment of
    the shot. None when the engine did not say where the face looks: then nothing changes, the body heading decides."""
    if s.gaze is None: return None
    a = math.atan2(pos[0] - s.x, pos[2] - s.z)
    return [abs(wrap(a - g)) for g in s.gazes]

def face_penalty(s, pos, limit):
    """0 when the gaze is unknown; otherwise prefers camera angles that keep the front of the head towards the
    camera for most of the shot (a cubic head seen from the side has no face), the mean guiding the choice and the
    share of moments outside the readable cone being paid for."""
    offs = face_offs(s, pos)
    if not offs: return 0.
    mean = sum(offs) / len(offs)
    over = (sum(1 for o in offs if o > limit) / len(offs)) if limit else 0.
    return .5 * min(1., mean / math.pi) + .9 * over

HEAD_ROOM_DEFAULT = HEAD_SHARE['close']     # share of the image width a head may take in an over-the-shoulder


def head_room(cam):
    """the cap on the share of the image width a head may take in an OTS, or None for the historical framing.

    Opt-in, per episode (written onto every shot by the narrative director) or per shot: `"head_room": true`
    for the default above, a number to tune it, absent / false for exactly what the studio shipped before.

    Why this key exists at all, and why it is an over-the-shoulder key. In a 9:16 frame the WIDTH is what
    runs out first, and `solve` already knows it: the HEAD_SHARE table above sets the distance of a shot on
    ONE subject from the real width of the head, precisely so a close-up built for a human head does not
    crop a cubic skull. The over-the-shoulder branch never got that treatment, because it does not work
    from a wanted image height at all: it places the camera a fixed 0.8-1.45 m BEHIND the listener, and the
    speaker lands wherever the two characters happen to be standing. Measured on `dernier_bus`, shot 12 --
    two characters 1.65 m apart in a corridor -- the speaker head came out at **134 % of the image
    width**: a cropped head, on the shot whose whole job is to show a face. With the key the same shot
    frames the head inside the cap and nothing else about the shot changes."""
    v = cam.get('head_room')
    if v is None or v is False: return None
    if v is True: return HEAD_ROOM_DEFAULT
    try: return max(.2, min(1., float(v)))
    except (TypeError, ValueError): return None


ARM_R = .11         # half-width of a pixel3d forearm / hand with its sleeve, in metres
HEAD_R = .30        # half-width of the blocky head with its hair (HEAD_W / 2 in the pixel3d engine)
ARM_NEAR = .22      # a limb this much nearer the lens than the face (as a share of the face distance) is paid in full
ARM_SHARE = .4      # share of the sampled moments the verdict is averaged over, worst first


def arm_penalty(s, pos, th):
    """How much the subject's OWN arm takes the frame away from his face, seen from pos; `th` is the horizontal
    half-tangent of the lens. 0 when the engine said nothing about the arms, so nothing changes without the key.

    The regie gives a speaking character a gesture from a small table, and two of the five (`point`, `extend`)
    throw the hand ~0.55 m along the axis the body faces. A tight shot is placed on that very axis: the hand then
    sits half a metre nearer the lens than the head and the shoulder-to-hand chain is drawn clean across the
    image. Measured on the corridor close-up of `demo20_decors`: head at 1.72 m, hand at 1.33 m, the arm spanning
    25.3 deg of a 29.4 deg frame -- 86 % of the width. No probe could see it: probes test the set and the OTHER
    characters, never the subject's own limbs.

    Three different defects are paid, and the worst of them wins:
      - **bulk**: a limb nearer than the face, spanning a large share of the frame (the forearm beam);
      - **blob**: a hand pointed straight at the lens -- barely any span, but drawn as big as the head;
      - **eclipse**: a hand parked on the disc of the head (the face behind a fist).
    Within a moment the worse arm counts -- one is enough to ruin the frame -- and the moments are averaged: one
    bad frame in ten is not the same defect as ten in ten. A resting arm hangs *behind* the head distance and
    costs exactly nothing, which is why the option does not simply push every camera back."""
    if not s.arms: return 0.
    hx, hy, hz = s.x, s.eye, s.z
    ux, uy, uz = hx - pos[0], hy - pos[1], hz - pos[2]
    dH = math.sqrt(ux * ux + uy * uy + uz * uz)
    if dH < 1e-3: return 0.
    ux, uy, uz = ux / dH, uy / dH, uz / dH
    # the real half-width of the head when the engine knows it (a refitted PIXEL 3D head is much smaller than
    # the historical blocky one, and a penalty measured on the wrong head radius would over-report the eclipse)
    aH = math.atan((s.head_w / 2 if s.head_w else HEAD_R) / dH)
    wide = 2 * math.atan(max(th, 1e-3))                     # horizontal field of the frame, in radians
    per = []
    for moment in s.arms:
        worst = 0.
        for arm in moment:                                  # one arm = (shoulder, elbow, mid-forearm, hand)
            v = []
            for (ax, ay, az) in arm:
                dx, dy, dz = ax - pos[0], ay - pos[1], az - pos[2]
                d = math.sqrt(dx * dx + dy * dy + dz * dz)
                if d > 1e-3: v.append((dx / d, dy / d, dz / d, d))
            if len(v) < 3: continue
            near = dH / min(q[3] for q in v[1:]) - 1.       # the shoulder never offends: it belongs to the body
            if near <= .02: continue                        # level with the face or behind it: an ordinary arm
            span = 0.
            for i in range(len(v)):
                for j in range(i + 1, len(v)):
                    span = max(span, math.acos(max(-1., min(1., v[i][0] * v[j][0] + v[i][1] * v[j][1] + v[i][2] * v[j][2]))))
            lead = min(1., near / ARM_NEAR)
            bulk = min(1., span / wide * 1.4) * lead          # the arm drawn right across the frame
            blob = 0.; ecl = 0.
            for (cx, cy, cz, d) in v[1:]:
                if d >= dH: continue
                aA = math.atan(ARM_R / d)
                blob = max(blob, min(1., (aA / aH) / .55) * lead)   # ...or pointed at the lens: short, but a blob
                sep = math.acos(max(-1., min(1., cx * ux + cy * uy + cz * uz)))
                ecl = max(ecl, max(0., (aH + aA - sep) / (aH + aA)) * min(1., .3 + near * 3.))
            worst = max(worst, min(1., max(bulk, blob, ecl)))
        per.append(worst)
    if not per: return 0.
    per.sort(reverse=True)
    k = max(1, int(round(len(per) * ARM_SHARE)))             # the worst moments, not the average of all of them:
    return sum(per[:k]) / k                                  # two bad seconds in five is the defect being reported


ARM_SLACK = .20     # how much of the rest of the score the arm pass may spend. Beyond that the frame was better.
ARM_FACE_EPS = .02  # ...and it may never spend ANY of the face term: that is the one thing it must not trade


def arm_pick(pool):
    """Second pass of the opt-in framing: among the candidates the cinematographer already judged *almost as
    good as its own best one*, and that see the face at least as well, take the one where the subject's arm
    bothers the least.

    It is a second pass and not one more term in the score, on purpose. Measured on `demo6_continuite`: added
    as a plain term, the arm cost did buy 21.5 % -> 14.0 % of forearm in the frame -- and paid for it out of
    the engine's own quality control, `faces_readable` 0.969 -> 0.815 and `camera_blocked` 1 -> 4. An arm cost
    of 0.3 simply outranks a visibility gap of 0.2, and nothing in a weighted sum can stop that. Two guards do:
    a frame that sees the face better than the winner is never a candidate (`ARM_FACE_EPS`), and the rest of
    the score has a fixed budget (`ARM_SLACK`).

    pool: [(score without the arm term, arm penalty, face penalty, *rest)] -> the chosen entry, or None."""
    if not pool or not any(p[1] > .02 for p in pool): return None
    top = max(p[0] for p in pool); fp0 = max(p[2] for p in pool if p[0] >= top - 1e-9)
    keep = [p for p in pool if p[0] >= top - ARM_SLACK and p[2] <= fp0 + ARM_FACE_EPS]
    if not keep: return None
    return min(keep, key=lambda p: (round(p[1], 3), -p[0]))


def solve(cam, subjects, aspect_k, fov_k, probe=None, blocked=None, memory=None, key=None):
    """cam: the "camera" dict; subjects: [Subject] (already filtered to the subjects of the shot);
    aspect_k = image width / height; fov_k: vertical field factor of the engine (tan(v/2) = tan(fov/2) * fov_k);
    probe(pos, point) -> True if the point is seen from pos; blocked(pos) -> True if the camera would be inside the set.
    memory: dict kept by the engine between shots (line-of-action side). Returns dict(pos, target, fov, score)."""
    memory = memory if memory is not None else {}
    shot = cam.get('shot', 'medium'); n = len(subjects)
    if not subjects: return None
    if shot == 'dialogue' and n == 2 and aspect_k < 1:                  # 9:16: alternating clean singles (an OTS fills a narrow frame)
        spk = next((s_ for s_ in subjects if s_.id == cam.get('speaker')), subjects[0])
        cam = dict(cam, _partner=next(s_ for s_ in subjects if s_ is not spk), size=cam.get('size', 'medium')); subjects = [spk]; n = 1; shot = 'medium'
    if shot == 'dialogue': shot = 'ots' if n == 2 else 'two_shot'    # blocky faces read best from the front: over-the-shoulder
    if shot == 'two_shot' and n == 1: shot = 'medium'
    size_name = cam.get('size', {'two_shot': 'medium_full', 'group': 'full', 'ots': 'close'}.get(shot, shot))
    if size_name not in SIZES: size_name = 'medium'
    fov = float(cam.get('fov', LENS.get(shot, LENS.get(size_name, 50))))
    tv = math.tan(math.radians(fov) / 2) * fov_k; th = tv * aspect_k
    if shot == 'pov':
        s = subjects[0]; h = s.heading + float(cam.get('yaw', 0)) * math.pi / 180
        pos = (s.x + math.sin(h) * .12, s.eye + .02, s.z + math.cos(h) * .12)
        tgt = cam.get('target_point') or (s.x + math.sin(h) * 5, s.eye - .15, s.z + math.cos(h) * 5)
        return dict(pos=pos, target=tgt, fov=float(cam.get('fov', 70)), score=1., shot='pov')
    # line of action (two subjects) and the side of the camera, remembered between shots of the same pair
    pair = None
    if n >= 2:
        a, b = subjects[0], subjects[1]; pair = tuple(sorted((a.id, b.id)))
        la = math.atan2(b.x - a.x, b.z - a.z)
        side = cam.get('side')
        if side is None: side = memory.get(('side', pair))
        if side is None:
            side = 'right'
        memory[('side', pair)] = side
        sgn = 1 if side == 'right' else -1
    # wanted image height and look-at point
    vis = SIZES[size_name]
    width = {'extreme_close': .42, 'close': .62, 'medium': .9, 'medium_full': 1.05}.get(size_name, 1.2)   # what must fit across
    hw = max([s_.head_w for s_ in subjects if s_.head_w], default=0.)
    if hw and n == 1 and size_name in HEAD_SHARE:                        # one head: it needs that much room across.
        width = max(width, hw / HEAD_SHARE[size_name])                   # several subjects: their spread decides, below
    vis = max(vis, width / aspect_k)                                    # narrow 9:16 frame: the width decides
    if shot == 'ots':
        spk = next((s for s in subjects if s.id == cam.get('speaker')), subjects[0])
        lst = next((s for s in subjects if s is not spk), None)
        if lst is None: shot = 'close'
        else:
            d = math.atan2(spk.x - lst.x, spk.z - lst.z)                  # listener -> speaker
            rx, rz = math.cos(d), -math.sin(d)                            # right of that direction
            if pair:
                la = math.atan2(subjects[1].x - subjects[0].x, subjects[1].z - subjects[0].z)
                side_sgn = sgn if abs(wrap(d - la)) < math.pi / 2 else -sgn
            else: side_sgn = 1
            best = None; pool = []
            kl = min(1., .45 + .55 * aspect_k)                              # narrow frame: closer to the line
            tgt = (spk.x, spk.eye - vis / 6, spk.z)
            cands = [(b_, l_, h_, sd, pen) for (sd, pen) in ((side_sgn, 0.), (-side_sgn, .12))         # other side: breaks the 180 rule
                     for h_ in (.1, .3) for (b_, l_) in ((1.25, .62), (1.1, .55), (1.45, .7), (.95, .5), (.8, .75), (1.1, .85), (1.3, .95), (1.0, 1.05))]
            for back, lat, hh, sd, pen in cands:
                lat *= kl
                pos = (lst.x - math.sin(d) * back + rx * lat * sd, lst.eye + hh, lst.z - math.cos(d) * back + rz * lat * sd)
                sc = _score(pos, [(spk.x, spk.eye, spk.z), (spk.x, spk.eye - .35, spk.z)], probe, blocked) - pen - (.05 if hh > .2 else 0.)
                sc -= face_penalty(spk, pos, FACE_CONE['ots'])         # the speaker's face, not the side of his head
                ax, ay, az_ = spk.x - pos[0], spk.eye - pos[1], spk.z - pos[2]; bx, by, bz = lst.x - pos[0], lst.eye - pos[1], lst.z - pos[2]
                la_, lb_ = math.sqrt(ax * ax + ay * ay + az_ * az_), math.sqrt(bx * bx + by * by + bz * bz)
                sep = math.acos(max(-1., min(1., (ax * bx + ay * by + az_ * bz) / (la_ * lb_ + 1e-9))))
                need = math.atan(.36 / max(lb_, .3)) + math.atan(.2 / max(la_, .3))         # the big blocky heads (hair, headphones) must not overlap
                if sep < need: sc -= .8 * (1 - sep / need)
                if best is None or sc > best[0]: best = (sc, pos, tgt)
                if spk.arms: pool.append((sc, arm_penalty(spk, pos, th), face_penalty(spk, pos, FACE_CONE['ots']), pos, tgt))
                elif sc >= .99: break
            alt = arm_pick(pool)
            if alt is not None: best = (alt[0], alt[3], alt[4])
            hr = head_room(cam)
            if hr is not None and best[0] >= .75:
                # the speaker head must fit across the frame: back the camera off ALONG ITS OWN AXIS until
                # it does. Moving along the axis changes nothing about the composition except the distance --
                # the shoulder stays where it was in the frame -- and the step is abandoned the moment the
                # new position is inside the set or loses sight of the face, so a cramped set keeps the old
                # framing rather than getting a camera in a wall.
                hw2 = (spk.head_w or 2 * HEAD_R)
                need = (hw2 / hr / 2) / max(th, 1e-3)              # distance at which the head takes `hr` of the width
                px, py, pz = best[1]
                dx, dy, dz = px - spk.x, py - spk.eye, pz - spk.z
                have = math.sqrt(dx * dx + dy * dy + dz * dz)
                if have > 1e-3 and need > have:
                    ux, uy, uz = dx / have, dy / have, dz / have
                    keep = best[1]
                    for f in (.25, .5, .75, 1.):
                        g = have + (need - have) * f
                        cand = (spk.x + ux * g, spk.eye + uy * g, spk.z + uz * g)
                        if blocked is not None and blocked(cand): break
                        if probe is not None and not probe(cand, (spk.x, spk.eye, spk.z)): break
                        keep = cand
                    best = (best[0], keep, best[2])
            if best[0] >= .75: return dict(pos=best[1], target=best[2], fov=fov, score=best[0], shot='ots')
            cam = dict(cam, _partner=lst); subjects = [spk]; n = 1; shot = 'close'   # no room behind the listener: clean single
    partner = cam.get('_partner')
    if partner is not None and n == 1 and shot in ('close', 'extreme_close', 'medium', 'medium_full'):
        s0 = subjects[0]; pr_ = tuple(sorted((s0.id, partner.id)))
        d = math.atan2(partner.x - s0.x, partner.z - s0.z)                 # subject -> partner
        side = cam.get('side') or memory.get(('side', pr_)) or 'right'; memory[('side', pr_)] = side
        la = math.atan2(partner.x - s0.x, partner.z - s0.z) if pr_[0] == s0.id else math.atan2(s0.x - partner.x, s0.z - partner.z)
        sg = (1 if side == 'right' else -1) * (1 if abs(wrap(d - la)) < math.pi / 2 else -1)
        dist0 = (vis / 2) / tv; best = None; pool = []; tgt = (s0.x, s0.eye - vis / 6, s0.z)
        rings = [d] if s0.gaze is None else [d, s0.gaze]     # around the partner, and around the face: a head turned
        angles = (.42, .55, .32, .7, .22, .85, 1.0)          # only part of the way (the yaw is limited) keeps its face
        # an outstretched hand is not always dodgeable by turning: stepping back shrinks it faster than the face
        dmuls = (1., 1.15, 1.32) if s0.arms else (1.,)
        for k_, (ref, ang, dm) in enumerate([(r_, a_, m_) for m_ in dmuls for a_ in angles for r_ in rings]):
            az = ref + sg * ang; dist = dist0 * dm
            pos = (s0.x + math.sin(az) * dist, s0.eye - .04, s0.z + math.cos(az) * dist)
            sc = _score(pos, [(s0.x, s0.eye, s0.z), (s0.x, s0.eye - .3, s0.z)], probe, blocked) - .03 * k_
            sc -= face_penalty(s0, pos, FACE_CONE.get(size_name, 1.2))
            vx, vz = pos[0] - s0.x, pos[2] - s0.z; L2 = vx * vx + vz * vz          # the partner's head must not fill the frame
            u_ = ((partner.x - s0.x) * vx + (partner.z - s0.z) * vz) / max(L2, 1e-6)
            if 0. < u_ < 1.:
                lat = abs((partner.x - s0.x) * vz - (partner.z - s0.z) * vx) / math.sqrt(L2)
                if lat < .6: sc -= .7 * (1 - lat / .6)
            if best is None or sc > best[0]: best = (sc, pos, az)
            if s0.arms: pool.append((sc, arm_penalty(s0, pos, th), face_penalty(s0, pos, FACE_CONE.get(size_name, 1.2)), pos, az))
            elif sc > .95: break
        alt = arm_pick(pool)
        if alt is not None: best = (alt[0], alt[3], alt[4])
        if best and best[0] > .4: return dict(pos=best[1], target=tgt, fov=fov, score=best[0], shot=shot, az=best[2])
    xs = [s.x for s in subjects]; zs = [s.z for s in subjects]
    cx, cz = sum(xs) / n, sum(zs) / n
    eye = sum(s.eye for s in subjects) / n
    g0 = min(s.base for s in subjects)                                   # the level the subjects stand on (roofs, ledges: V3)
    if size_name in ('full', 'medium_full', 'wide', 'establishing') or shot in ('group', 'two_shot'):
        top = max(s.eye for s in subjects) + .25
        tgt_y = top - vis * .5 + vis * (.18 if size_name in ('full', 'medium_full') else .05)
        if size_name in ('wide', 'establishing'): tgt_y = g0 + (top - g0) * .5 + .15          # people in the middle of a wide frame
        tgt_y = max(g0 + .75, tgt_y)
        if max(s.base for s in subjects) - g0 > .3:                     # V3: the subject changes level (climb, jump down)
            vis = max(vis, top - g0 + .3); tgt_y = (top + g0) / 2        # the frame holds the whole vertical move
    else:
        tgt_y = eye - vis / 6
    # preferred viewing direction (camera looks along -dir towards the subjects)
    if n == 1:
        base = subjects[0].heading
        if subjects[0].gaze is not None and size_name in ('extreme_close', 'close', 'medium', 'medium_full'):
            base = subjects[0].gaze                                      # a close shot follows the face, not the shoulders
    elif n == 2:
        base = la + sgn * math.pi / 2                                    # perpendicular to the line, on the chosen side
        fa = subjects[0].heading; fb = subjects[1].heading
        if abs(wrap(base - fa)) > math.pi / 2 and abs(wrap(base - fb)) > math.pi / 2 and cam.get('side') is None and not memory.get(('fixed', pair)):
            base = wrap(base + math.pi); memory[('side', pair)] = 'left' if sgn > 0 else 'right'
        memory[('fixed', pair)] = True
    else:
        sx = sum(math.sin(s.heading) for s in subjects); sz = sum(math.cos(s.heading) for s in subjects)
        base = math.atan2(sx, sz) if math.hypot(sx, sz) > .3 else math.atan2(-cx, -cz + 100)
    ang = cam.get('angle', 'three_quarter')
    off = {'front': 0., 'three_quarter': .42, 'side': 1.35, 'back': math.pi, 'low': .3, 'high': .3}.get(ang, .42)
    if cam.get('_from_az') is not None: base = cam['_from_az']; off = 0.; ang = 'front' if ang in ('three_quarter', 'side', 'back') else ang   # "from": the director chose the side
    if n >= 2 and shot in ('two_shot', 'dialogue') and not isinstance(ang, (int, float)) and ang == 'three_quarter': off = .38
    if n >= 2 and shot == 'two_shot' and cam.get('turn') is None:       # favour the face of the speaker (or of the first subject)
        key = cam.get('speaker') or subjects[0].id; s0 = next((s_ for s_ in subjects if s_.id == key), subjects[0])
        lr = 1 if math.cos(wrap(s0.heading - (base + off))) >= math.cos(wrap(s0.heading - (base - off))) else -1
        cam = dict(cam, turn='right' if lr > 0 else 'left')
    if isinstance(ang, (int, float)): off = math.radians(float(ang))
    lr = 1 if cam.get('turn', 'right') == 'right' else -1
    height = {'low': -.55, 'high': .9}.get(ang, 0.) + float(cam.get('height', 0.))
    # distance: image height, then width so that everybody fits
    dist = (vis / 2) / tv
    if n >= 2:
        pts = [(s.x, s.z) for s in subjects]
    best = None
    cands = [(0., 1.), (.25, 1.), (-.25, 1.), (.5, 1.), (-.5, 1.), (0., .8), (.8, 1.), (-.8, 1.), (.25, .7), (-.25, .7), (1.2, 1.), (-1.2, 1.), (1.7, 1.), (-1.7, 1.), (math.pi, 1.)]
    prefer = cam.get('_prefer_az')
    if prefer is not None:                               # continuity with the previous key of a follow shot
        a0 = base + lr * off
        cands = sorted(cands, key=lambda c_: abs(wrap(a0 + c_[0] - prefer)))
    poi_pair = n >= 2 and any(s_.id == 'poi' for s_ in subjects)
    if poi_pair or (n == 1 and cam.get('turn') is None):             # free choice of side: try both
        cands = [(c_[0] + extra, c_[1]) for c_ in cands for extra in (0., -2 * lr * off)] + ([(c_[0] + math.pi, c_[1]) for c_ in cands[:5]] if poi_pair else [])
    cands = [(c_[0], c_[1], i_) for i_, c_ in enumerate(cands)]      # (azimuth offset, distance factor, order cost)
    if n == 1 and subjects[0].arms and size_name in ('extreme_close', 'close', 'medium', 'medium_full'):
        # Turning around an outstretched hand is not always possible (a corridor, a wall behind the camera);
        # stepping back shrinks the hand faster than the face. These carry the order cost of the angle they come
        # from plus a small one of their own, so they are a relief and never a first choice.
        cands = cands + [(c_[0], c_[1] * m_, c_[2] + o_) for (m_, o_) in ((1.15, 2), (1.32, 5)) for c_ in cands[:18]]
    use_arms = any(s_.arms for s_ in subjects); pool = []
    for k, (da, dk, ko) in enumerate(cands):
        az = base + lr * off + da
        dx, dz = math.sin(az), math.cos(az)
        d = dist
        if n >= 2:                                                       # width: project the spread on the image plane
            rx, rz = math.cos(az), -math.sin(az)
            lat = [(p[0] - cx) * rx + (p[1] - cz) * rz for p in pts]; dep = [(p[0] - cx) * dx + (p[1] - cz) * dz for p in pts]
            need = (max(lat) - min(lat)) / 2 + .45
            d = max(d, need / th + max(dep), dist + max(dep) * 1.1)     # the nearest subject must fit too
        d *= dk
        cy = max(g0 + .35, tgt_y + height + (eye - tgt_y) * .35 if size_name not in ('wide', 'establishing') else tgt_y + .35 + height)
        tgt = (cx, tgt_y + (height * .35 if ang in ('low', 'high') else 0.), cz)
        at = lambda m: (cx + dx * d * m, cy, cz + dz * d * m)
        m = 1.
        if blocked is not None and blocked(at(1.)):      # back up only as far as the set allows...
            lo_, hi_ = .0, 1.
            for _ in range(12):
                mid = (lo_ + hi_) / 2
                if blocked(at(mid)): hi_ = mid
                else: lo_ = mid
            m = lo_
        if m * d < .35: continue
        f_eff = fov if m > .98 else min(80., math.degrees(2 * math.atan(math.tan(math.radians(fov) / 2) / m)))   # ...then a wider lens
        pos = at(m)
        pts3 = [(s.x, s.eye, s.z) for s in subjects] + [(s.x, s.eye - .5, s.z) for s in subjects]
        sc = _score(pos, pts3, probe, blocked) - .02 * ko - .35 * (1 - m) - (.4 if f_eff >= 79.9 and m < .9 else 0.)
        low = {'full': .15, 'wide': .15, 'establishing': .15, 'medium_full': None, 'medium': None}.get(size_name, 'none')
        body = []                                                       # the whole head, and the body the size of shot promises
        for s_ in subjects:
            if s_.id == 'poi': continue
            body.append((s_.x, s_.eye, s_.z))
            if low != 'none':
                body.append((s_.x, s_.eye + .2, s_.z)); body.append((s_.x, s_.base + low if low is not None else s_.eye - (1.0 if size_name == 'medium_full' else .55), s_.z))
        sc -= .6 * (1 - _in_frame(pos, tgt, body, f_eff, aspect_k, fov_k))
        people = [s_ for s_ in subjects if s_.id != 'poi']; fz = 1.; fp = 0.
        if people and ang != 'back':                                    # faces towards the camera, not backs
            last = {}
            for s_ in people: last[s_.id] = s_                          # latest sample of each character
            seen = [math.sin(s_.heading) * (pos[0] - s_.x) + math.cos(s_.heading) * (pos[2] - s_.z) > .15 * math.hypot(pos[0] - s_.x, pos[2] - s_.z) for s_ in last.values()]
            frac = sum(seen) / len(seen); fz = 1. if frac > .99 else -1.
            sc -= .45 * (1 - frac)
            lim = FACE_CONE.get(size_name) if n == 1 else None          # a turned head: no close-up on the flat side.
            if lim is not None:                                          # two people facing each other are seen in profile
                fp = max(face_penalty(s_, pos, lim) for s_ in last.values())     # whatever the camera does: leave the
                sc -= fp                                                 # two-shot and the group to the historical logic
                if fp > .25: fz = -1.
        if prefer is not None: sc -= .3 * abs(wrap(az - prefer)) / math.pi
        if best is None or sc > best[0]: best = (sc, pos, tgt, f_eff, az)
        if use_arms: pool.append((sc, max((arm_penalty(s_, pos, th) for s_ in people), default=0.), fp, pos, tgt, f_eff, az))
        elif sc >= .97 and fz >= 0: break
    alt = arm_pick(pool)                                         # the opt-in second pass: see arm_pick
    if alt is not None: best = (alt[0], alt[3], alt[4], alt[5], alt[6])
    if (best is None or best[0] < .55) and aspect_k < 1 and n == 2 and shot in ('two_shot', 'medium_full', 'full') and not poi_pair and not cam.get('_fallback'):
        key = cam.get('speaker') or subjects[0].id; s0 = next((s_ for s_ in subjects if s_.id == key), subjects[0])
        alt = solve(dict(cam, shot='medium', size='medium', _partner=next(s_ for s_ in subjects if s_ is not s0), _fallback=True, turn=None),
                    [s0], aspect_k, fov_k, probe, blocked, memory)                 # narrow frame, no room to back up: favour one face
        if alt is not None and (best is None or alt['score'] > best[0]): return dict(alt, fallback='single', focus=s0.id)
    if best is None: return None
    return dict(pos=best[1], target=best[2], fov=best[3], score=best[0], shot=shot, az=best[4])

def _in_frame(pos, tgt, pts, fov, aspect_k, fov_k):
    """share of the points (heads) that fall inside the image for a camera at pos looking at tgt"""
    if not pts: return 1.
    fx, fy, fz = tgt[0] - pos[0], tgt[1] - pos[1], tgt[2] - pos[2]; L = math.sqrt(fx * fx + fy * fy + fz * fz) + 1e-9; fx, fy, fz = fx / L, fy / L, fz / L
    rx, rz = fz, -fx; rl = math.hypot(rx, rz) + 1e-9; rx, rz = rx / rl, rz / rl          # right (horizontal)
    ux, uy, uz = -rz * fy, rz * fx - rx * fz, rx * fy                                      # up = right x forward
    tv = math.tan(math.radians(fov) / 2) * fov_k; th = tv * aspect_k; ok = 0
    for (x, y, z) in pts:
        dx, dy, dz = x - pos[0], y - pos[1], z - pos[2]; zc = dx * fx + dy * fy + dz * fz
        if zc <= .1: continue
        if abs((dx * rx + dz * rz) / zc) <= th * .92 and abs((dx * ux + dy * uy + dz * uz) / zc) <= tv * .92: ok += 1
    return ok / len(pts)

def _score(pos, pts, probe, blocked):
    if blocked is not None and blocked(pos): return -1.
    if probe is None: return 1.
    ok = sum(1 for p in pts if probe(pos, p))
    return ok / max(1, len(pts))

def apply_move(sol, cam, u, T, follow_delta=(0., 0.)):
    """camera motion over the shot (u = 0..1). Moves are slow and purposeful; no zoom."""
    mv = cam.get('move', 'static'); amt = float(cam.get('amount', .5)); e = smooth(u)
    px, py, pz = sol['pos']; tx, ty, tz = sol['target']
    vx, vy, vz = tx - px, ty - py, tz - pz; L = math.sqrt(vx * vx + vy * vy + vz * vz) + 1e-6
    if mv in ('dolly_in', 'push'):
        k = min(.3, .22 * amt * 2) * e
        if L < 1.6: k *= .5                                  # already close: a gentle push only
        px, py, pz = px + vx * k, py + vy * k, pz + vz * k
    elif mv == 'dolly_out':
        k = min(.45, .28 * amt * 2) * e; px, py, pz = px - vx * k, py - vy * k, pz - vz * k
    elif mv == 'track':
        rx, rz = vz / L, -vx / L; k = (e - .5) * 1.2 * amt; px, pz = px + rx * k, pz + rz * k
    elif mv == 'orbit':
        a = (e - .5) * .45 * amt; c, s = math.cos(a), math.sin(a); dx, dz = px - tx, pz - tz
        px, pz = tx + dx * c + dz * s, tz - dx * s + dz * c
    elif mv in ('crane_up', 'crane_down'):
        py += (.7 if mv == 'crane_up' else -.5) * amt * e
    elif mv == 'follow':
        px += follow_delta[0]; pz += follow_delta[1]; tx += follow_delta[0]; tz += follow_delta[1]
    if mv == 'handheld' or cam.get('handheld'):
        a = float(cam.get('shake', .5 * amt))
        px += .018 * a * (math.sin(T * 1.7) + .5 * math.sin(T * 3.1 + 1)); py += .012 * a * math.sin(T * 2.3 + .4)
        tx += .03 * a * math.sin(T * 1.1 + 2); ty += .02 * a * math.sin(T * 1.9)
    return (px, py, pz), (tx, ty, tz)

def auto_camera(shot, actor_ids, speaking, moving, first_in_set, emotion=None, aspect_k=1.):
    """default camera intention when the director gives none (coverage planner)"""
    if first_in_set and len(actor_ids) >= 1: return {'shot': 'wide', 'on': actor_ids, 'move': 'static'}
    if moving: return {'shot': 'full', 'on': moving[:1], 'move': 'follow'}
    if speaking and len(actor_ids) >= 2: return {'shot': 'dialogue', 'on': actor_ids[:2], 'speaker': speaking[0]}
    if len(actor_ids) >= 3: return {'shot': 'group', 'on': actor_ids}
    if emotion in ('scared', 'shocked', 'crying', 'sad', 'surprised'): return {'shot': 'close', 'on': actor_ids[:1], 'move': 'dolly_in', 'amount': .4}
    return {'shot': 'medium', 'on': actor_ids[:1]}
