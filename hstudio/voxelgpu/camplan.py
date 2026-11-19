"""The camera of a blocked film: a solver that FRAMES THE SITUATION, and the audit that refuses frames the story cannot use.

The remakes' camera was a table of absolute coordinates typed per shot (`rig: path`). Nothing checked that the camera stood outside the walls,
that the thing the narration names was in the picture, that it was whole, that an actor was not hidden behind a shelf, or how tight the lens was:
a sentence about the car got a close-up of a bumper, a sentence about the glass got a handprint.

A shot says WHAT MUST BE SEEN, not where the camera is:

    frame = {'show': ['voiture', 'boutique'],        # landmarks (stagegeo) that must be entirely in the picture, unobstructed
             'actors': ['hero'],                      # characters that must be visible (head and chest in frame, not behind anything)
             'kind': 'wide',                          # wide | medium | close | insert  -> the size band the audit enforces
             'face': ['hero'],                        # characters whose face should be turned towards the lens (angle <= 100 deg)
             'from': {'at': [x, z], 'r': 3.},         # where the camera may stand (a hint, never a licence to enter a wall)
             'fov': 60}

`solve()` searches candidate positions on a deterministic grid, rejects every one the audit would refuse, and returns the best; if there is none it
raises PlanError in French saying which constraint nothing could satisfy, so the story or the set is fixed instead of the picture being cheated.
`audit_shot()` applies the very same measurements to a camera written by hand.

Artistic layer (all of it behind keys the original film does not use, so its cameras and its audit stay identical): a frame may also say
    'points':  [[x, y, z], ...]           places that must be in the picture (the spot where somebody vanished)
    'fg':      ['clerk']                  characters allowed to stand in the foreground (over-the-shoulder): they never count as an occluder
    'threat':  {'id': 'ghost', 'hidden': [0, .5], 'edge': [.3, .9]}   a menace that may be PARTLY hidden by the set (share of the body hidden in `hidden`),
                                          whose head must stay readable, optionally standing towards the edge of the picture; never used for what the story requires seen
    'gap':     {'a': 'entree', 'b': 'voiture', 'min': .12}   the floor distance between two landmarks must be legible in the picture (frame heights)
    'scale':   {'voiture': [.3, .85]}     the apparent width (share of the picture) a landmark must have: not a speck, not cut
    'min_layers': 2                       foreground / subject / background: a flat shot has one
    'preflight': True                     no wall in the lens, nothing closer than 1 m dead ahead
`cinematic_intent.py` writes those frames from the dramatic intention of a beat.
"""
import math
import numpy as np
from .blocking import PlanError, Violation


def _V(code, msg, t=None, sid=None, **data):
    who = data.pop('who', sid); return Violation(code, msg, t, who, **data)

ASPECT = {'9:16': 9 / 16, '16:9': 16 / 9}
HEAD_W, HEAD_TOP, CHEST, FEET = .5, 2.2, 1.45, 0.        # A's head is a 0.5 m cube, the top of the head is at 2.2 m at scale 1 (chars4.js)
BANDS = {'wide': (46., 82.), 'medium': (46., 82.), 'close': (40., 82.), 'insert': (34., 82.),
         'establishing': (50., 86.), 'full': (46., 82.), 'ots': (40., 82.), 'pov': (50., 90.)}
HEAD_SHARE_MAX = {'wide': .27, 'medium': .5, 'close': .95, 'insert': 1.2,
                  'establishing': .12, 'full': .45, 'ots': .95, 'pov': .6}   # head width / frame width
BODY_SAMPLES = (.12, .5, .9, 1.25, 1.5, 1.75, 2.05)       # heights (m at scale 1) along a body where a sight line is cast: feet, knees, hips, belly, chest, neck, head
ARTISTIC_CODES = ('menace_illisible', 'menace_trop_cachée', 'menace_trop_visible', 'menace_mal_placée', 'menace_pas_au_fond', 'point_hors_cadre', 'point_masqué', 'écart_illisible',
                   'échelle_trop_petite', 'échelle_trop_grande', 'plan_plat', 'mur_dans_l_objectif', 'taille_de_plan', 'acteur_illisible', 'repère_en_partie_masqué', 'acteur_au_bord', 'bandeau_sur_visage')
EXTRA_KEYS = ('points', 'threat', 'gap', 'scale', 'min_layers', 'preflight', 'fg', 'size', 'legible', 'avoid')
# how much of the picture HEIGHT a standing character (feet to top of head) takes, by size of shot: >1 means the frame is cropped inside the body (waist up, shoulders up)
BODY_H = {'establishing': (0., .16), 'wide': (.14, .46), 'full': (.44, .82), 'medium': (.8, 1.12), 'close': (1.1, 2.0)}


def look_dir(pos, look):
    f = np.array(look, float) - np.array(pos, float); n = np.linalg.norm(f); return f / n if n > 1e-9 else np.array([0., 0., 1.])


def project(pos, look, fov, aspect, pts):
    """-> (ndc x, ndc y, depth) for each 3D point. Vertical fov in degrees, camera up = +y (no roll)"""
    pos = np.array(pos, float); f = look_dir(pos, look); r = np.cross(f, [0., 1., 0.]); r = r / (np.linalg.norm(r) + 1e-12); u = np.cross(r, f)
    t = math.tan(math.radians(fov) / 2.); out = []
    for p in pts:
        d = np.array(p, float) - pos; z = float(d @ f)
        if z < 1e-3: out.append((9., 9., z)); continue
        out.append((float(d @ r) / (z * t * aspect), float(d @ u) / (z * t), z))
    return out


def box_corners(b): return [(x, y, z) for x in (b[0], b[3]) for y in (b[1], b[4]) for z in (b[2], b[5])]


def smooth(k): k = max(0., min(1., k)); return k * k * (3 - 2 * k)


def cam_at(shot, t_rel, C=None, t_abs0=0.):
    """pose of a hand-written `path` camera (keys, smoothstep between them, `look` may follow an actor) -> (pos, look, fov)"""
    c = shot['camera']; keys = c['keys']; T = t_rel
    j = 0
    while j < len(keys) - 2 and T > keys[j + 1]['t']: j += 1
    a, b = keys[j], keys[min(j + 1, len(keys) - 1)]; k = smooth((T - a['t']) / max(1e-6, b['t'] - a['t'])) if b is not a else 0.
    if b is not a and (b.get('cut') or a.get('hold')): k = 0.

    def pt(v):
        if isinstance(v, dict):
            x, z = C.xz(v['on'], t_abs0 + t_rel); return (x + float(v.get('dx', 0.)), float(v.get('h', 1.4)), z + float(v.get('dz', 0.)))
        return tuple(v)
    mix = lambda p, q: tuple(p[i] * (1 - k) + q[i] * k for i in range(3))
    return mix(pt(a['pos']), pt(b['pos'])), mix(pt(a['look']), pt(b['look'])), a.get('fov', 50) * (1 - k) + b.get('fov', 50) * k


def _actor_pts(C, aid, t, scale=1.):
    x, z = C.xz(aid, t); return dict(head=(x, HEAD_TOP * scale - .25 * scale, z), top=(x, HEAD_TOP * scale, z), chest=(x, CHEST * scale, z), feet=(x, .05, z))


def measure(geo, C, pos, look, fov, aspect, t_abs, show=(), actors=(), fg=()):
    """everything the audit and the solver need about one camera at one time"""
    m = dict(pos=tuple(pos), fov=fov, inside=geo.solid_at_point(pos, .12), show={}, actors={})
    for name in show:
        b = geo.land(name); cs = project(pos, look, fov, aspect, box_corners(b)); xs = [c[0] for c in cs]; ys = [c[1] for c in cs]; dep = [c[2] for c in cs]
        whole = min(dep) > .3 and max(abs(v) for v in xs + ys) <= .96
        ctr = ((b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2)
        hit = geo.ray(pos, ctr, ignore=(name,)); w = (max(xs) - min(xs)) / 2 if min(dep) > .3 else 9.
        m['show'][name] = dict(whole=whole, share_w=w, share_h=(max(ys) - min(ys)) / 2 if min(dep) > .3 else 9., hidden_by=hit)
    for aid in actors:
        A = C.actors[aid]; P = _actor_pts(C, aid, t_abs, A.scale); pr = project(pos, look, fov, aspect, [P['head'], P['top'], P['chest'], P['feet']])
        inframe = all(abs(pr[i][0]) <= .98 and abs(pr[i][1]) <= .98 and pr[i][2] > .3 for i in (0, 2))
        occ = geo.ray(pos, P['head']) or geo.ray(pos, P['chest'])
        if not occ:                                                       # another character standing between the lens and this one's head (a vertical capsule)
            for oid, OA in C.actors.items():
                if oid == aid or OA.spec.get('role') == 'extra': continue          # passers-by (role extra) are the dressing of the street: one crossing the lens is not an occluder
                ox, oz = C.xz(oid, t_abs); ur = .3 if oid in fg else max(.34, OA.r + .06); a_ = np.array(pos, float); b_ = np.array(P['head'], float)
                dx, dz = b_[0] - a_[0], b_[2] - a_[2]; ll = dx * dx + dz * dz
                if ll < 1e-6: continue
                u = ((ox - a_[0]) * dx + (oz - a_[2]) * dz) / ll
                if .02 < u < .98 and math.hypot(a_[0] + dx * u - ox, a_[2] + dz * u - oz) < ur and a_[1] + (b_[1] - a_[1]) * u < 2.25 * OA.scale: occ = f'acteur:{oid}'; break
        row = C._row(A, t_abs); bear = math.atan2(pos[0] - row['x'], pos[2] - row['z']); face_angle = abs((bear - row['heading'] + math.pi) % (2 * math.pi) - math.pi)
        hw = abs(project(pos, look, fov, aspect, [(P['head'][0] + HEAD_W * A.scale / 2 * math.cos(bear), P['head'][1], P['head'][2] - HEAD_W * A.scale / 2 * math.sin(bear))])[0][0]
                 - project(pos, look, fov, aspect, [(P['head'][0] - HEAD_W * A.scale / 2 * math.cos(bear), P['head'][1], P['head'][2] + HEAD_W * A.scale / 2 * math.sin(bear))])[0][0]) / 2
        m['actors'][aid] = dict(inframe=inframe, hidden_by=occ, head_share=hw if pr[0][2] > .3 else 9., face_angle=math.degrees(face_angle), body_h=abs(pr[1][1] - pr[3][1]) / 2 if pr[3][2] > .3 and pr[1][2] > .3 else 9.,
                                head_ndc=(pr[0][0], pr[0][1]), depth=pr[0][2])
    return m


# ---------------------------------------------------------------------------------------------------------------------- artistic measurements
def actor_between(C, pos, p, skip, t, ignore=()):
    """the id of a character (a vertical capsule) standing on the sight line pos -> p, or None. `skip` = the one looked at, `ignore` = those allowed in front"""
    a_ = np.array(pos, float); b_ = np.array(p, float); dx, dz = b_[0] - a_[0], b_[2] - a_[2]; ll = dx * dx + dz * dz
    if ll < 1e-6: return None
    for oid, OA in C.actors.items():
        if oid == skip or oid in ignore or OA.spec.get('role') == 'extra': continue
        ox, oz = C.xz(oid, t); ur = max(.34, OA.r + .06); u = ((ox - a_[0]) * dx + (oz - a_[2]) * dz) / ll
        if .02 < u < .98 and math.hypot(a_[0] + dx * u - ox, a_[2] + dz * u - oz) < ur and a_[1] + (b_[1] - a_[1]) * u < 2.25 * OA.scale: return oid
    return None


def body_visibility(geo, C, pos, look, fov, aspect, aid, t, fg=()):
    """-> (share of the body samples that fall in the picture with a sight line clear of every view-blocking solid AND of every other character, head seen?,
    head (ndc x, ndc y), head depth). A menace hidden behind the very person the shot is about is not a menace in the picture."""
    A = C.actors[aid]; x, z = C.xz(aid, t); pts = [(x, h * A.scale, z) for h in BODY_SAMPLES]; pr = project(pos, look, fov, aspect, pts); seen = []
    for p, q in zip(pts, pr):
        inpic = q[2] > .3 and abs(q[0]) <= 1. and abs(q[1]) <= 1.
        seen.append(bool(inpic and not geo.ray(pos, p) and not actor_between(C, pos, p, aid, t)))
    return sum(seen) / len(seen), seen[-1], (pr[-1][0], pr[-1][1]), pr[-1][2]


def _hit_dist(geo, p0, p1, ceilings=True):
    """like Geo.ray_dist, but a ceiling is a surface too (an interior has a roof: a sight line that leaves through it is not 'deep')"""
    d = [p1[i] - p0[i] for i in range(3)]; L = math.sqrt(sum(v * v for v in d)) or 1.; best = None
    for s in geo.solids:
        if not s.view or (s.kind == 'ceiling' and not ceilings): continue
        t0, t1 = 0., 1.
        for lo, hi, o, dd in ((s.x0, s.x1, p0[0], d[0]), (s.y0, s.y1, p0[1], d[1]), (s.z0, s.z1, p0[2], d[2])):
            if abs(dd) < 1e-9:
                if o < lo or o > hi: t0 = 2.; break
            else:
                a, b = (lo - o) / dd, (hi - o) / dd
                if a > b: a, b = b, a
                t0, t1 = max(t0, a), min(t1, b)
                if t0 > t1: break
        if t0 <= t1 and t0 <= 1.0 and (best is None or t0 < best): best = t0
    return None if best is None else best * L


def depth_layers(geo, pos, look, fov, aspect, subj_depth, grid=(5, 9), far=40.):
    """-> dict(fg, bg, layers, flat): is there something near the lens framing the picture (a shelf edge, a door frame: 3..40 % of the sight lines stop
    at less than 60 % of the subject's distance), and room behind the subject (25 % of the sight lines reach 1.5x its distance + 1 m)?"""
    f = look_dir(pos, look); r = np.cross(f, [0., 1., 0.]); r = r / (np.linalg.norm(r) + 1e-12); u = np.cross(r, f); t = math.tan(math.radians(fov) / 2.); n = near = deep = 0
    for i in range(grid[0]):
        for j in range(grid[1]):
            x = (i / (grid[0] - 1) * 2 - 1) * .95; y = (j / (grid[1] - 1) * 2 - 1) * .6
            d = f + r * (x * t * aspect) + u * (y * t); d = d / np.linalg.norm(d); h = _hit_dist(geo, pos, np.array(pos, float) + d * far); h = far if h is None else h
            n += 1; near += h < min(.6 * subj_depth, 3.5); deep += h > 1.5 * subj_depth + 1.
    fgl = .03 <= near / n <= .4; bgl = deep / n >= .25
    return dict(fg=bool(fgl), bg=bool(bgl), layers=1 + int(fgl) + int(bgl), flat=not bgl, near=near / n, deep=deep / n)


def centre_clearance(geo, pos, look, reach=40.):
    """metres from the lens to the first solid straight ahead (a wall in the lens), `reach` if nothing"""
    f = look_dir(pos, look); h = geo.ray_dist(pos, np.array(pos, float) + f * reach); return reach if h is None else h


def floor_point(box, toward):
    """the point of a landmark's footprint nearest to `toward` (x, z), on the floor: where the gap between two things is measured from"""
    return (min(max(toward[0], box[0]), box[3]), 0., min(max(toward[1], box[2]), box[5]))


def _facing_points(geo, a, b):
    A, Bx = geo.land(a), geo.land(b); ca = ((A[0] + A[3]) / 2, (A[2] + A[5]) / 2); cb = ((Bx[0] + Bx[3]) / 2, (Bx[2] + Bx[5]) / 2)
    return floor_point(A, cb), floor_point(Bx, ca)


def floor_gap(geo, a, b):
    """metres between the facing sides of two landmarks, on the floor. The narration says « trois mètres » between the door and the car: what is it really?"""
    pa, pb = _facing_points(geo, a, b); return math.hypot(pa[0] - pb[0], pa[2] - pb[2])


def gap_len(geo, pos, look, fov, aspect, a, b):
    """length, in picture heights, of the floor segment that joins the facing sides of landmarks a and b as the camera sees it (0 if one is behind the lens).
    A shot taken from the axis of the two compresses the gap to nothing; a shot from the side shows it."""
    pa, pb = _facing_points(geo, a, b); pr = project(pos, look, fov, aspect, [pa, pb])
    if pr[0][2] < .3 or pr[1][2] < .3: return 0.
    return math.hypot((pr[0][0] - pr[1][0]) * aspect, pr[0][1] - pr[1][1]) / 2.


def landmark_share(pos, look, fov, aspect, box):
    """(share of the picture width, share of its height, whole?) of a landmark's box"""
    cs = project(pos, look, fov, aspect, box_corners(box)); xs = [c[0] for c in cs]; ys = [c[1] for c in cs]; dep = [c[2] for c in cs]
    if min(dep) <= .3: return 9., 9., False
    return (max(xs) - min(xs)) / 2, (max(ys) - min(ys)) / 2, max(abs(v) for v in xs + ys) <= .96


def _subject_depth(geo, C, frame, pos, look, fov, aspect, t):
    pts = [(C.xz(a, t)[0], 1.4, C.xz(a, t)[1]) for a in frame.get('actors', [])]
    pts += [((b[0] + b[3]) / 2, 1., (b[2] + b[5]) / 2) for b in (geo.land(nm) for nm in frame.get('show', []))]
    if not pts: return 6.
    return min(q[2] for q in project(pos, look, fov, aspect, pts))


def extra_metrics(geo, C, frame, pos, look, fov, aspect, t):
    """everything the artistic keys of a frame ask about one camera at one time -> dict (only the entries the frame uses)"""
    m = {}; th = frame.get('threat')
    if th:
        vis, head, ndc, dep = body_visibility(geo, C, pos, look, fov, aspect, th['id'], t, frame.get('fg', ()))
        m['threat'] = dict(vis=vis, head=head, ndc=ndc, depth=dep, hidden=1. - vis)
        if th.get('behind_by') is not None and frame.get('actors'):
            m['threat']['subject_depth'] = min(q[2] for q in project(pos, look, fov, aspect, [(C.xz(a, t)[0], 1.5, C.xz(a, t)[1]) for a in frame['actors']]))
    if frame.get('points'):
        pr = project(pos, look, fov, aspect, [tuple(p) for p in frame['points']])
        m['points'] = [dict(inframe=bool(q[2] > .3 and abs(q[0]) <= .98 and abs(q[1]) <= .98), hidden_by=geo.ray(pos, tuple(p))) for p, q in zip(frame['points'], pr)]
    if frame.get('gap'): m['gap'] = gap_len(geo, pos, look, fov, aspect, frame['gap']['a'], frame['gap']['b'])
    if frame.get('scale'): m['scale'] = {nm: landmark_share(pos, look, fov, aspect, geo.land(nm)) for nm in frame['scale']}
    if frame.get('legible'):
        m['legible'] = {}
        for aid in frame['legible']:
            A = C.actors[aid]; x, z = C.xz(aid, t); pr = project(pos, look, fov, aspect, [(x, HEAD_TOP * A.scale, z), (x, .0, z)])
            m['legible'][aid] = abs(pr[0][1] - pr[1][1]) / 2 if pr[0][2] > .3 and pr[1][2] > .3 else 9.
    if frame.get('size'):
        sz = frame['size']; A = C.actors[sz['subject']]; x, z = C.xz(sz['subject'], t); pr = project(pos, look, fov, aspect, [(x, HEAD_TOP * A.scale, z), (x, .0, z)])
        m['size'] = dict(body_h=abs(pr[0][1] - pr[1][1]) / 2 if pr[0][2] > .3 and pr[1][2] > .3 else 9., depth=pr[0][2])
    if frame.get('preflight') and frame.get('show'):
        m['show_vis'] = {}
        for nm in frame['show']:
            b = geo.land(nm); xs_, ys_, zs_ = [b[0] + (b[3] - b[0]) * k for k in (.08, .5, .92)], [b[1] + (b[4] - b[1]) * k for k in (.1, .5, .9)], [b[2] + (b[5] - b[2]) * k for k in (.08, .5, .92)]
            samp = [(x_, y_, z_) for x_ in xs_ for y_ in ys_ for z_ in zs_]
            m['show_vis'][nm] = sum(1 for q in samp if not geo.ray(pos, q, ignore=(nm,))) / len(samp)
    if frame.get('preflight') or frame.get('avoid'):
        m['edge'] = {}
        for aid in frame.get('actors', []):
            A = C.actors[aid]; x, z = C.xz(aid, t); pr = project(pos, look, fov, aspect, [(x, (HEAD_TOP - .25) * A.scale, z)])
            m['edge'][aid] = dict(margin=max(abs(pr[0][0]), abs(pr[0][1])), head_y=pr[0][1], ok=pr[0][2] > .3, head_w=HEAD_W * A.scale / (2 * max(pr[0][2], .3) * math.tan(math.radians(fov) / 2.) * aspect))
    if frame.get('min_layers') or frame.get('preflight'): m['layers'] = depth_layers(geo, pos, look, fov, aspect, _subject_depth(geo, C, frame, pos, look, fov, aspect, t))
    if frame.get('preflight'): m['clear'] = centre_clearance(geo, pos, look)
    return m


def extra_violations(frame, em, sid, t):
    """the artistic rules applied to the metrics of ONE instant -> [Violation]"""
    v = []; th = frame.get('threat')
    if th and 'threat' in em:
        e = em['threat']; lo, hi = th.get('hidden', [0., .6])
        if not e['head'] and not th.get('allow_headless'): v.append(_V('menace_illisible', f"{sid} : la tête de {th['id']} est cachée ou hors image : on ne lit plus la menace", t, sid, who=th['id']))
        if e['hidden'] > hi + 1e-6: v.append(_V('menace_trop_cachée', f"{sid} : {th['id']} est caché à {e['hidden'] * 100:.0f} % (maximum {hi * 100:.0f} %)", t, sid, who=th['id']))
        if e['hidden'] < lo - 1e-6: v.append(_V('menace_trop_visible', f"{sid} : {th['id']} est visible en entier alors que le plan devait le cacher en partie (au moins {lo * 100:.0f} %)", t, sid, who=th['id']))
        if th.get('edge') and not (th['edge'][0] <= abs(e['ndc'][0]) <= th['edge'][1]): v.append(_V('menace_mal_placée', f"{sid} : {th['id']} est à {abs(e['ndc'][0]):.2f} du centre (voulu {th['edge'][0]}..{th['edge'][1]})", t, sid, who=th['id']))
        if th.get('behind_by') and e['depth'] < e.get('subject_depth', 0.) + th['behind_by']:
            v.append(_V('menace_pas_au_fond', f"{sid} : {th['id']} est à {e['depth']:.1f} m de l'objectif, à moins de {th['behind_by']:.1f} m derrière le personnage ({e.get('subject_depth', 0.):.1f} m) : ce n'est pas une menace au fond du plan", t, sid, who=th['id']))
    for aid, lo in (frame.get('legible') or {}).items():
        b = em['legible'][aid]
        if b < lo: v.append(_V('acteur_illisible', f"{sid} : {aid} ne prend que {b * 100:.0f} % de la hauteur de l'image (minimum {lo * 100:.0f} %) : on ne lit ni son visage ni sa peur", t, sid, who=aid))
    for nm, sh in (em.get('show_vis') or {}).items():
        if sh < .7: v.append(_V('repère_en_partie_masqué', f"{sid} : « {nm} » n'est vu qu'à {sh * 100:.0f} % (un élément du décor passe devant) : le plan doit le montrer entier", t, sid, name=nm))
    for aid, e in (em.get('edge') or {}).items():
        if frame.get('preflight') and e['margin'] > frame.get('margin', .93): v.append(_V('acteur_au_bord', f"{sid} : la tête de {aid} est à {e['margin']:.2f} du centre de l'image (maximum {frame.get('margin', .93)}) : collé au bord", t, sid, who=aid))
        if frame.get('avoid') and e['head_w'] >= .08 and frame['avoid'][0] <= e['head_y'] <= frame['avoid'][1]: v.append(_V('bandeau_sur_visage', f"{sid} : la tête de {aid} est dans la bande des sous-titres (y image {e['head_y']:.2f}, bande {frame['avoid'][0]}..{frame['avoid'][1]})", t, sid, who=aid))
    sz = frame.get('size')
    if sz and 'size' in em:
        lo, hi = sz['body_h']; b = em['size']['body_h']
        if not (lo - 1e-6 <= b <= hi + 1e-6): v.append(_V('taille_de_plan', f"{sid} : {sz['subject']} prend {b * 100:.0f} % de la hauteur de l'image, le plan « {sz.get('name', '?')} » en demande {lo * 100:.0f}..{hi * 100:.0f} %", t, sid, who=sz['subject']))
    for i, p in enumerate(em.get('points', [])):
        if not p['inframe']: v.append(_V('point_hors_cadre', f"{sid} : le point {frame['points'][i]} (l'endroit où cela se passe) n'est pas dans l'image", t, sid))
        elif p['hidden_by']: v.append(_V('point_masqué', f"{sid} : le point {frame['points'][i]} est caché par {p['hidden_by']!r}", t, sid))
    g = frame.get('gap')
    if g and em.get('gap', 0.) < g.get('min', .12): v.append(_V('écart_illisible', f"{sid} : l'écart entre « {g['a']} » et « {g['b']} » ne fait que {em.get('gap', 0.):.2f} hauteur d'image (minimum {g.get('min', .12)}) : la distance ne se lit pas", t, sid))
    for nm, rng in (frame.get('scale') or {}).items():
        sh, _h, whole = em['scale'][nm]
        if sh < rng[0]: v.append(_V('échelle_trop_petite', f"{sid} : « {nm} » ne prend que {sh * 100:.0f} % de la largeur (minimum {rng[0] * 100:.0f} %) : une tache, pas une voiture", t, sid, name=nm))
        if sh > rng[1] or not whole: v.append(_V('échelle_trop_grande', f"{sid} : « {nm} » prend {min(sh, 9) * 100:.0f} % de la largeur ou sort de l'image (maximum {rng[1] * 100:.0f} %)", t, sid, name=nm))
    if frame.get('min_layers') and em['layers']['layers'] < frame['min_layers']:
        L = em['layers']; v.append(_V('plan_plat', f"{sid} : {L['layers']} plan(s) de profondeur (premier plan {'oui' if L['fg'] else 'non'}, fond {'oui' if L['bg'] else 'non'}), il en faut {frame['min_layers']}", t, sid))
    if frame.get('preflight') and em.get('clear', 99.) < 1.0: v.append(_V('mur_dans_l_objectif', f"{sid} : un solide à {em['clear']:.2f} m pile devant l'objectif", t, sid))
    return v


def foreground_blocked(geo, pos, look, fov, aspect, reach=2.2, grid=(5, 9)):
    """share of the picture whose sight line meets a solid (not a ceiling, not glass) within `reach` metres of the lens: a post, a shelf, a wall in the way"""
    f = look_dir(pos, look); r = np.cross(f, [0., 1., 0.]); r = r / (np.linalg.norm(r) + 1e-12); u = np.cross(r, f); t = math.tan(math.radians(fov) / 2.); n = 0; hit = 0
    for i in range(grid[0]):
        for j in range(grid[1]):
            x = (i / (grid[0] - 1) * 2 - 1) * .95; y = (j / (grid[1] - 1) * 2 - 1) * .95
            d = f + r * (x * t * aspect) + u * (y * t); d = d / np.linalg.norm(d); q = np.array(pos, float) + d * 40.
            n += 1; h = geo.ray_dist(pos, q)
            if h is not None and h < reach: hit += 1
    return hit / n


def audit_shot(shot, C, geo, aspect='9:16', n=6):
    """-> (violations, metrics) for one shot. `shot['frame']` declares what must be seen; the camera is `shot['camera']` (path keys)."""
    fr = shot.get('frame') or {}; ar = ASPECT[aspect]; dur = float(shot['dur']); sid = shot.get('id', '?'); t0 = shot['_t0']
    show = fr.get('show', []); actors = fr.get('actors', []); kind = fr.get('kind', 'medium'); v = []; ms = []; fovs = []; prev = None
    ts = [dur * k / (n - 1) for k in range(n)]
    for tr in ts:
        pos, look, fov = cam_at(shot, tr, C, t0); fovs.append(fov)
        m = measure(geo, C, pos, look, fov, ar, t0 + tr, show, actors, fr.get('fg', ())); ms.append(m)
        if any(k in fr for k in EXTRA_KEYS):
            m['extra'] = extra_metrics(geo, C, fr, pos, look, fov, ar, t0 + tr); v += extra_violations(fr, m['extra'], sid, t0 + tr)
        fb = foreground_blocked(geo, pos, look, fov, ar)
        if fb > .22: v.append(_V('écran_bouché', f"{sid} : {fb * 100:.0f} % de l'image est bouché par un solide à moins de 2 m de l'objectif (poteau, rayon, mur)", t0 + tr, sid))
        if m['inside']: v.append(_V('caméra_dans_solide', f"{sid} : la caméra est dans {m['inside']!r} en ({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f})", t0 + tr, sid))
        if pos[1] < .2 or pos[1] > 6.5: v.append(_V('caméra_hauteur', f"{sid} : caméra à {pos[1]:.2f} m", t0 + tr, sid))
        if prev is not None:
            for q in range(1, 9):
                u = q / 8; p = tuple(prev[i] * (1 - u) + pos[i] * u for i in range(3)); s = geo.solid_at_point(p, .05)
                if s: v.append(_V('caméra_traverse', f"{sid} : le travelling passe à travers {s!r}", t0 + tr, sid)); break
        prev = pos
    lo, hi = BANDS.get(kind, BANDS['medium'])
    if min(fovs) < lo - 1e-6 and not fr.get('allow_tele'): v.append(_V('zoom', f"{sid} : focale {min(fovs):.0f}° trop serrée pour un plan « {kind} » (minimum {lo:.0f}°) : on cadre en déplaçant la caméra, pas en zoomant", t0, sid))
    if max(fovs) > hi + 1e-6: v.append(_V('grand_angle', f"{sid} : focale {max(fovs):.0f}° déforme trop (maximum {hi:.0f}°)", t0, sid))
    if max(fovs) - min(fovs) > 6.: v.append(_V('zoom', f"{sid} : la focale varie de {max(fovs) - min(fovs):.0f}° dans le plan (zoom arbitraire)", t0, sid))
    for name in show:
        whole = sum(1 for m in ms if m['show'][name]['whole']); hid = [m['show'][name]['hidden_by'] for m in ms if m['show'][name]['hidden_by']]
        if whole < len(ms) - 0: v.append(_V('repère_coupé', f"{sid} : « {name} » n'est pas entier dans l'image ({whole}/{len(ms)} instants) alors que le plan doit le montrer", t0, sid, name=name))
        for nm_, mn in (fr.get('min_share') or {}).items():
            if nm_ == name and max(m['show'][name]['share_w'] for m in ms) < mn: v.append(_V('repère_trop_petit', f"{sid} : « {name} » ne prend que {max(m['show'][name]['share_w'] for m in ms) * 100:.0f} % de la largeur (minimum {mn * 100:.0f} %) : le plan doit le MONTRER", t0, sid, name=name))
        if hid: v.append(_V('repère_masqué', f"{sid} : « {name} » est caché par {hid[0]!r}", t0, sid, name=name))
    for aid in actors:
        out = sum(1 for m in ms if not m['actors'][aid]['inframe']); hid = [m['actors'][aid]['hidden_by'] for m in ms if m['actors'][aid]['hidden_by']]
        if out: v.append(_V('acteur_hors_cadre', f"{sid} : {aid} (tête et buste) sort de l'image à {out}/{len(ms)} instants", t0, sid, who=aid))
        if hid: v.append(_V('acteur_masqué', f"{sid} : {aid} est caché par {hid[0]!r}", t0, sid, who=aid))
        mx = max(m['actors'][aid]['head_share'] for m in ms)
        if mx > HEAD_SHARE_MAX.get(kind, .5) and not fr.get('allow_tight'): v.append(_V('plan_trop_serré', f"{sid} : la tête de {aid} prend {mx * 100:.0f} % de la largeur (maximum {HEAD_SHARE_MAX.get(kind) * 100:.0f} % pour « {kind} »)", t0, sid, who=aid))
    for aid in fr.get('face', []):
        ang = min(m['actors'][aid]['face_angle'] for m in ms) if aid in ms[0]['actors'] else 0.
        if ang > 100.: v.append(_V('visage_caché', f"{sid} : le visage de {aid} reste tourné à {ang:.0f}° de la caméra (maximum 100°)", t0, sid, who=aid))
    if kind in ('close', 'insert') and not fr.get('context') and dur > 2.6: v.append(_V('serré_sans_contexte', f"{sid} : plan « {kind} » de {dur:.1f}s sans contexte (ni autre repère, ni acteur voisin)", t0, sid))
    seen_ = set(); dd = []
    for x in v:                                                           # the same defect at six instants is one defect
        key = (x.code, x.who, x.data.get('name')) if x.code in ARTISTIC_CODES else (x.code, x.t, x.who, x.data.get('name'))
        if key not in seen_: seen_.add(key); dd.append(x)
    v = dd
    return v, dict(id=sid, kind=kind, extra=[m.get('extra') for m in ms] if any('extra' in m for m in ms) else None, fov=(round(min(fovs), 1), round(max(fovs), 1)), show={k: dict(whole=all(m['show'][k]['whole'] for m in ms), share_w=round(max(m['show'][k]['share_w'] for m in ms), 2)) for k in show},
                   actors={a: dict(inframe=all(m['actors'][a]['inframe'] for m in ms), head_share=round(max(m['actors'][a]['head_share'] for m in ms), 2), face_angle=round(min(m['actors'][a]['face_angle'] for m in ms)), body_h=round(max(m['actors'][a]['body_h'] for m in ms), 2)) for a in actors})


def audit_film(shots, C, geo, aspect='9:16', tight_max=.22, insert_max=8):
    """audit every shot, then the film as a whole: how much of the running time is tight, how many inserts"""
    v = []; rows = []; tight = 0.; tot = 0.; inserts = 0
    for s in shots:
        vs, m = audit_shot(s, C, geo, aspect); v += vs; rows.append(m); d = float(s['dur']); tot += d
        if m['kind'] in ('close', 'insert'): tight += d
        if m['kind'] == 'insert': inserts += 1
    if tot and tight / tot > tight_max: v.append(Violation('trop_de_gros_plans', f"{tight / tot * 100:.0f} % du film est en gros plan ou insert (maximum {tight_max * 100:.0f} %)"))
    if inserts > insert_max: v.append(Violation('trop_d_inserts', f"{inserts} inserts (maximum {insert_max})"))
    return v, rows, dict(tight_share=tight / tot if tot else 0., inserts=inserts)


# ---------------------------------------------------------------------------------------------------------------------- the solver
def solve(geo, C, frame, t_a, t_b, aspect='9:16', fov=60., prefer=None, heights=(1.3, 1.55, 1.8, 2.1, .9), rs=None, forbid=(), travel=0., cands=None, shifts=(0.,), look_at=None, top=1, track=None, follow=None):
    """the best camera for `frame` over [t_a, t_b] (absolute seconds), or a PlanError that says what nothing could satisfy.
    prefer = (x, z) the place the camera would like to stand (a hint); rs = radii around the subject to try.
    cands = explicit camera places [(x, z), ...] tried instead of the rings (a shot grammar knows where an over-the-shoulder stands);
    shifts = how far the aim is moved sideways, as a share of the half picture width (composition off the centre);
    look_at = (x, y, z) the point aimed at instead of the centre of what must be seen (a POV looks where the character looks);
    top = how many distinct valid cameras to return under 'alts' (best first);
    track = an actor id: the camera pans to keep aiming at him (the check is made with the aim he really has at each instant);
    follow = an actor id: the camera walks WITH him at a fixed offset (a steadicam: constant size and composition); candidate places are read as offsets"""
    if follow: track = follow
    ar = ASPECT[aspect]; show = frame.get('show', []); actors = frame.get('actors', []); kind = frame.get('kind', 'medium'); ts = [t_a, (t_a + t_b) / 2, t_b]
    pts = []
    for p in frame.get('points', []): pts.append(tuple(p))
    for nm in show:
        b = geo.land(nm); pts.append(((b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2))
    for a in actors:
        for t in ts: x, z = C.xz(a, t); pts.append((x, 1.35, z))
    if not pts: raise PlanError(f"{frame!r} : rien à cadrer")
    cx = sum(p[0] for p in pts) / len(pts); cz = sum(p[2] for p in pts) / len(pts); cy = sum(p[1] for p in pts) / len(pts)
    ext = max(math.hypot(p[0] - cx, p[2] - cz) for p in pts) + 1.
    rs = rs or [ext * k for k in (1.0, 1.3, 1.7, 2.2, 2.9, 3.8, 5.0)] + [3.0, 4.5, 6.5, 9.0]
    best = None; fails = {}; valid = []
    hint = frame.get('from')
    if cands is None:
        places = [(cx + r * math.sin(math.radians(deg)), cz + r * math.cos(math.radians(deg))) for r in sorted(set(round(x, 2) for x in rs)) for deg in range(0, 360, 8)]
    else: places = [tuple(c) for c in cands]
    aim = look_at if look_at is not None else (cx, min(cy, 1.45), cz)
    for fv in ([fov] if not frame.get('fovs') else frame['fovs']):
        for (px, pz) in places:
            if cands is None and hint and 'at' in hint and math.hypot(px - hint['at'][0], pz - hint['at'][1]) > hint.get('r', 4.): continue
            for h in heights:
                pos = (px, h, pz); poss = None; off = None
                if follow:
                    fx, fz = C.xz(follow, (t_a + t_b) / 2); off = (px - fx, pz - fz); poss = [(C.xz(follow, t)[0] + off[0], h, C.xz(follow, t)[1] + off[1]) for t in ts]
                    if any(geo.solid_at_point(q, .25) for q in poss): fails['dans un solide'] = fails.get('dans un solide', 0) + 1; continue
                elif geo.solid_at_point(pos, .25): fails['dans un solide'] = fails.get('dans un solide', 0) + 1; continue
                for sh in shifts:
                    look = _shift_aim(pos, aim, fv, ar, sh)
                    looks = [(C.xz(track, t)[0], 1.35, C.xz(track, t)[1]) for t in ts] if track else None
                    ok, score, why = _eval(geo, C, pos, look, fv, ar, ts, show, actors, kind, frame, pts, prefer, looks, poss)
                    if not ok: fails[why] = fails.get(why, 0) + 1; continue
                    valid.append((score, pos, look, fv, off))
                    if best is None or score < best[0]: best = (score, pos, look, fv, off)
    if best is None:
        worst = sorted(fails.items(), key=lambda kv: -kv[1])[:3]
        raise PlanError(f"aucune caméra ne montre {show + actors} en « {kind} » entre {t_a:.1f}s et {t_b:.1f}s : refusée surtout pour {', '.join(f'{k} ({n})' for k, n in worst)}")
    out = dict(pos=best[1], look=best[2], fov=best[3], score=best[0], offset=best[4])
    if top > 1: out['alts'] = [dict(pos=p, look=lk, fov=f, score=sc, offset=o) for sc, p, lk, f, o in sorted(valid, key=lambda v: v[0])[:top]]
    return out


def _shift_aim(pos, aim, fov, ar, shift):
    """the aim point moved sideways by `shift` x the half width of the picture at its distance (0 = unchanged: the subject stays centred)"""
    if not shift: return aim
    f = look_dir(pos, aim); r = np.cross(f, [0., 1., 0.]); r = r / (np.linalg.norm(r) + 1e-12); d = float(np.linalg.norm(np.array(aim, float) - np.array(pos, float)))
    off = r * (shift * d * math.tan(math.radians(fov) / 2.) * ar); return (aim[0] + float(off[0]), aim[1], aim[2] + float(off[2]))


def _eval(geo, C, pos, look, fov, ar, ts, show, actors, kind, frame, pts, prefer, looks=None, poss=None):
    # re-aim: centre the points that must be seen
    pr = project(pos, look, fov, ar, pts)
    if any(p[2] < .5 for p in pr): return False, 0., 'derrière la caméra'
    if min(math.hypot(pos[0] - p[0], pos[2] - p[2]) for p in pts) < (.9 if kind in ('wide', 'medium', 'full', 'establishing') else .6): return False, 0., 'trop près'
    if frame.get('preflight') and not looks and any(abs(p[0]) > .98 or abs(p[1]) > .98 for p in pr): return False, 0., 'hors cadre'        # cheap necessary test first
    if foreground_blocked(geo, pos, look, fov, ar) > (.2 if geo.indoor(pos[0], pos[2]) else .07): return False, 0., 'premier plan bouché'
    worst = 0.; last = None
    for ti, t in enumerate(ts):
        if looks: look = looks[ti]
        if poss: pos = poss[ti]
        m = measure(geo, C, pos, look, fov, ar, t, show, actors, frame.get('fg', ()))
        for nm, d in m['show'].items():
            if not d['whole']: return False, 0., f'{nm} coupé'
            if d['hidden_by']: return False, 0., f"{nm} masqué"
            if d['share_w'] < (frame.get('min_share') or {}).get(nm, 0.): return False, 0., f'{nm} trop petit'
            worst = max(worst, d['share_w'])
        for a, d in m['actors'].items():
            if not d['inframe']: return False, 0., f'{a} hors cadre'
            if d['hidden_by']: return False, 0., f'{a} masqué'
            if d['head_share'] > HEAD_SHARE_MAX.get(kind, .5): return False, 0., 'tête trop grande'
            if a in frame.get('face', []) and d['face_angle'] > 100.: return False, 0., 'visage caché'
        if any(k in frame for k in EXTRA_KEYS):
            last = extra_metrics(geo, C, frame, pos, look, fov, ar, t); bad = extra_violations(frame, last, 'solve', t)
            if bad: return False, 0., bad[0].code
    # prefer: closer to the hint, and a subject that is not stuck in a corner of the image
    score = 0.
    if prefer: score += math.hypot(pos[0] - prefer[0], pos[2] - prefer[1]) * .35
    if frame.get('compose') == 'thirds':      # the subject sits on a third, on the side opposite to where it looks (lead room), not dead centre
        want = frame.get('thirds_x', .33); xs = [p[0] for p in (pr[-3 * len(actors):] if actors else pr)]
        score += sum(abs(abs(x) - want) for x in xs) / len(xs) * .8 + sum(abs(p[1]) for p in pr) / len(pr) * .5
    else:
        score += sum(abs(p[0]) for p in pr) / len(pr) * .8 + sum(abs(p[1]) for p in pr) / len(pr) * .5
    score += 0 if kind != 'wide' else -worst * .2
    if last and 'layers' in last: score -= .12 * (last['layers']['layers'] - 1)       # depth is rewarded: a foreground frame and a room behind the subject
    return True, score, ''
