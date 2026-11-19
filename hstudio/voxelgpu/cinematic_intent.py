"""From the DRAMATIC INTENTION of a beat to a camera that has been checked: the cinematographer of the blocked film.

`camplan.solve` finds a camera that SEES what it is told to see, safely (no wall, no occluder, no zoom). It does not know WHY the shot exists, so
on its own it answers every beat with the same safe frame: centred, medium-wide, flat. The first engine's cinematographer (`acting/cinema.py`) knew shot
types (OTS, POV, close, establishing) but not the place; the hand-typed cameras of the remakes knew the story but not the walls. This module keeps both
halves: the shot grammar of the first, the geometric guarantees of `camplan`, and it adds what neither had: a shot is chosen for the beat's purpose.

    intent = dict(id='S14', t0=31.0, t1=34.0, purpose='danger',        # establish | relation | danger | reaction | reveal | pov | dialogue
                  subject='clerk', threat='ghost', tension=.8,          #   | disappear | aftermath | detail
                  show=['vitrine'], occlude=True)
    plan = plan_sequence(geo, C, [intent, ...], aspect='9:16')
    plan.shots[0]  ->  dict(id, t0, t1, dur, frame, camera={'rig': 'path', 'keys': [...]}, shake, kind, style, why, relaxed, rejected, metrics)

What the grammar adds (every item is measured, none is a convention):
  * SIZE follows the beat: `assign_sizes` gives each beat establishing / wide / full / medium / close from its purpose and tension, avoids the same size twice in
    a row on the same subject, and spends the close-ups where tension peaks while keeping them under `tight_max` of the running time. The size is a measured
    fraction of the picture height taken by the subject (`camplan.BODY_H`), never a lens: no zoom, the lens stays in 56..70 degrees.
  * RELATION shots put the camera on the SIDE of the axis between two things (the glass door and the car) so the distance reads in the picture, instead of on
    the axis where it collapses; the apparent size of the car and the length of the gap are checked (`gap`, `scale`).
  * DANGER shots put the menace in the BACK of the picture (behind the subject, `behind_by`), possibly PARTLY hidden by the set (`occlude`), with its head still
    readable and everything the story needs seen never hidden: the occlusion budget applies to the menace only.
  * REVEAL is progressive: the same menace over several beats, hidden 86 % then 55 % then 20 %, closer each time.
  * FIELD / COUNTER-FIELD: over-the-shoulder pairs on the same side of the axis (180 degrees rule, remembered between shots), POV that follows the character's
    eye and looks where his body is facing.
  * A SUPERNATURAL DISAPPEARANCE (or arrival) is filmed as an event: one still wide take that holds the body in the picture until the very moment of the event,
    with the witness's fear in the same frame, then the empty place and the face. The camera never follows a normal walk to a door.
Everything is preflighted with the same audit (`camplan.audit_shot`): a beat for which nothing passes raises PlanError in French, it never gets a cheated picture.
Deterministic: no randomness, no clock.
"""
import math
from . import camplan as CP
from .blocking import PlanError, Violation

LADDER = ['establishing', 'wide', 'full', 'medium', 'close']
FOV = dict(establishing=66., wide=64., full=62., medium=60., close=58., ots=58., pov=66.)
FOVS = dict(establishing=(66., 72., 78.), wide=(64., 70., 76.), full=(62., 66., 72.), medium=(60., 64.), close=(58., 62.), ots=(58., 62.))      # tried in this order; never below 56, never zoomed within a shot
PURPOSES = ('establish', 'relation', 'danger', 'reaction', 'reveal', 'pov', 'dialogue', 'disappear', 'aftermath', 'detail')
SIZE_CLASS = dict(establishing=0, wide=1, full=2, medium=3, close=4, ots=3, pov=3, insert=4)       # for the rhythm of a sequence
TIGHT = ('close', 'insert')


def _fail(msg): raise PlanError(msg)


# ---------------------------------------------------------------------------------------------------------------------- where things are
def where(geo, C, ref, t):
    """(x, z) of an actor id, a landmark name, [x, z] or (x, y, z)"""
    if isinstance(ref, str):
        if C is not None and ref in C.actors: return C.xz(ref, t)
        if ref in geo.landmarks: b = geo.landmarks[ref]; return ((b[0] + b[3]) / 2, (b[2] + b[5]) / 2)
        if ref in geo.marks: return geo.marks[ref][:2]
        _fail(f"« {ref} » n'est ni un acteur, ni un repère, ni une marque (acteurs : {', '.join(C.actors) if C else '-'} ; repères : {', '.join(geo.landmarks)})")
    return (ref[0], ref[-1]) if len(ref) == 3 else (ref[0], ref[1])


def ring(cx, cz, radii, step=10, arc=None):
    """camera places around (cx, cz): `arc` = (bearing deg, half width deg) keeps only that sector (bearing 0 = +z, 90 = +x)"""
    out = []
    for r in radii:
        for deg in range(0, 360, step):
            if arc is not None and abs((deg - arc[0] + 180) % 360 - 180) > arc[1]: continue
            out.append((cx + r * math.sin(math.radians(deg)), cz + r * math.cos(math.radians(deg))))
    return out


def bearing(a, b): return math.degrees(math.atan2(b[0] - a[0], b[1] - a[1])) % 360.


def _heading(C, aid, t): return math.degrees(C._row(C.actors[aid], t)['heading']) % 360.


def _side(a, b, cam):
    """which side of the line a -> b the camera stands on (+1 / -1): the 180 degrees rule asks for the same sign from shot to shot"""
    return 1 if (b[0] - a[0]) * (cam[1] - a[1]) - (b[1] - a[1]) * (cam[0] - a[0]) >= 0 else -1


# ---------------------------------------------------------------------------------------------------------------------- the intent
def normalise(it, geo, C):
    """validates an intent (French errors that name the beat) and fills the defaults"""
    i = dict(it); sid = i.get('id', '?')
    if i.get('purpose') not in PURPOSES: _fail(f"{sid} : intention « {i.get('purpose')} » inconnue (connues : {', '.join(PURPOSES)})")
    if not ('t0' in i and 't1' in i) or float(i['t1']) <= float(i['t0']): _fail(f"{sid} : fenêtre de temps absente ou vide")
    i['t0'], i['t1'] = float(i['t0']), float(i['t1']); i['dur'] = round(i['t1'] - i['t0'], 4); i.setdefault('tension', .5)
    subj = i.get('subject'); i['subjects'] = [subj] if isinstance(subj, str) else list(subj or [])
    for k in ('subject', 'threat', 'witness', 'pov', 'sees', 'toward'):
        v = i.get(k)
        for r in (v if isinstance(v, (list, tuple)) and v and isinstance(v[0], str) else [v]):
            if isinstance(r, str) and r not in C.actors and r not in geo.landmarks and r not in geo.marks: _fail(f"{sid} : « {k} » désigne « {r} », inconnu du lieu et de la distribution")
    for r in i.get('show', []):
        if r not in geo.landmarks: _fail(f"{sid} : repère « {r} » inconnu (connus : {', '.join(geo.landmarks)})")
    ev = i.get('event')
    if ev:
        if ev.get('kind') not in ('vanish', 'appear'): _fail(f"{sid} : événement « {ev.get('kind')} » inconnu (vanish | appear)")
        if ev['who'] not in C.actors: _fail(f"{sid} : l'événement vise « {ev['who']} », absent de la distribution")
    if i['purpose'] in ('danger', 'reveal') and not (i['subjects'] and i.get('threat')): _fail(f"{sid} : « {i['purpose']} » demande un sujet et une menace")
    if i['purpose'] == 'disappear' and not ev: _fail(f"{sid} : « disappear » demande un événement (kind, who, t)")
    if i['purpose'] == 'pov' and not (i.get('pov') and i.get('sees')): _fail(f"{sid} : « pov » demande qui regarde (pov) et ce qu'il voit (sees)")
    return i


def base_size(it):
    p, T = it['purpose'], float(it.get('tension', .5))
    if it.get('size'): return it['size']
    if p == 'establish': return 'establishing' if T < .5 else 'wide'
    if p == 'relation': return 'wide' if T < .7 else 'full'
    if p == 'danger': return 'wide' if T < .35 else 'full' if T < .8 else 'medium'
    if p in ('reaction', 'detail'): return 'full' if T < .3 else 'medium' if T < .75 else 'close'
    if p == 'reveal': k = it.get('stage', 0) / max(1, it.get('of', 3) - 1); return LADDER[1 + min(3, int(k * 3.999))]
    if p == 'pov': return 'pov'
    if p == 'dialogue': return 'ots'
    if p == 'disappear': return 'wide'
    if p == 'aftermath': return 'medium'
    return 'medium'


def assign_sizes(intents, tight_max=.2):
    """one size per beat: the purpose and the tension choose it, the rhythm corrects it (no two identical sizes in a row on the same subject, a run of
    three gets broken), and the close-ups are rationed to `tight_max` of the running time, the calmest first to go"""
    sizes = []
    for k, it in enumerate(intents):
        s = base_size(it); prev = sizes[k - 1] if k else None
        if s in LADDER and prev in LADDER and s == prev and intents[k - 1]['subjects'][:1] == it['subjects'][:1] and not it.get('size') and it['purpose'] in ('reaction', 'danger', 'reveal', 'detail'):
            i = LADDER.index(s); rising = it.get('tension', .5) >= intents[k - 1].get('tension', .5)
            s = LADDER[min(i + 1, len(LADDER) - 1)] if rising and s != 'close' else LADDER[max(i - 1, 1)]
        sizes.append(s)
    tot = sum(i['dur'] for i in intents) or 1.
    while sum(i['dur'] for i, s in zip(intents, sizes) if s in TIGHT) / tot > tight_max:
        cand = [(i.get('tension', .5), k) for k, (i, s) in enumerate(zip(intents, sizes)) if s in TIGHT and not intents[k].get('size')]
        if not cand: break
        sizes[min(cand)[1]] = 'medium'
    return sizes


# ---------------------------------------------------------------------------------------------------------------------- shot grammar: variants
class Variant:
    def __init__(self, name, kind, frame, cands=None, heights=(1.45, 1.7, 2.0), shifts=(0.,), look_at=None, rs=None, window=None, rank=None, why='', relaxed=(), track=None, fovs=None, follow=None):
        self.fovs = fovs; self.follow = follow
        self.name, self.kind, self.frame, self.cands, self.heights, self.shifts, self.look_at, self.rs, self.window, self.rank, self.why, self.relaxed, self.track = \
            name, kind, frame, cands, heights, shifts, look_at, rs, window, rank, why, list(relaxed), track


def _base_frame(it, kind, **kw):
    f = dict(kind=kind, preflight=True)
    if it.get('show'): f['show'] = list(it['show'])
    if it.get('min_share'): f['min_share'] = dict(it['min_share'])
    f.update(kw); return f


def _size(subject, kind):
    return dict(subject=subject, body_h=list(CP.BODY_H[kind]), name=kind) if kind in CP.BODY_H and subject else None


def _with_size(frame, subject, kind):
    s = _size(subject, kind)
    if s: frame['size'] = s
    return frame


def _mid(it): return (it['t0'] + it['t1']) / 2


def _mover(C, aid, it):
    """a walking subject is followed by a camera that walks with him (constant size and composition); a still one gets a still camera"""
    return dict(follow=aid, track=aid) if travel(C, aid, it['t0'], it['t1']) > 1.2 else {}


def travel(C, aid, t0, t1, n=8):
    """the farthest the actor gets from where he starts in [t0, t1] (m): above 1.2 m a fixed lens cannot hold him at a tight size, so the lens pans after him"""
    p0 = C.xz(aid, t0); return max(math.dist(p0, C.xz(aid, t0 + (t1 - t0) * k / n)) for k in range(1, n + 1))


def v_establish(ctx, it, kind):
    geo, C = ctx
    refs = list(it.get('show') or []) + it['subjects']
    pts = [where(geo, C, r, _mid(it)) for r in refs] or [(0., 0.)]; cx = sum(p[0] for p in pts) / len(pts); cz = sum(p[1] for p in pts) / len(pts)
    ext = max(math.hypot(p[0] - cx, p[1] - cz) for p in pts) + 2.
    radii = [ext * k for k in (1.4, 1.9, 2.5, 3.3)] + [9., 12., 16.]
    base = dict(actors=[a for a in it['subjects'] if a in C.actors])
    out = []
    for layers in (2, 1):
        f = _base_frame(it, kind, min_layers=layers, **base)
        if not f.get('show') and not f.get('actors'): f['show'] = ['boutique']
        out.append(Variant('établissement', kind, f, cands=ring(cx, cz, radii, 10), heights=(1.7, 2.3, 3.0, 4.0), shifts=(0., .2, -.2),
                           why='le lieu et la relation entre les choses avant de s\'approcher', relaxed=[] if layers == 2 else ['min_layers 2 → 1']))
    return out


def v_relation(ctx, it, kind):
    geo, C = ctx; g = it.get('gap')
    refs = list(it.get('show') or []) + [r for r in (g or ()) if isinstance(r, str)]
    a, b = (g if g else (None, None))
    if g: ca, cb = where(geo, C, a, _mid(it)), where(geo, C, b, _mid(it)); axis = bearing(ca, cb)
    else: pts = [where(geo, C, r, _mid(it)) for r in refs + it['subjects']]; ca, cb = pts[0], pts[-1]; axis = bearing(ca, cb)
    pts = [where(geo, C, r, _mid(it)) for r in refs + it['subjects']] or [ca, cb]; cx = sum(p[0] for p in pts) / len(pts); cz = sum(p[1] for p in pts) / len(pts)
    mem = ctx_memory(ctx).get(('relation', a, b)); out = []
    scale = dict(it.get('scale') or {})
    if 'voiture' in (it.get('show') or []) and 'voiture' not in scale: scale['voiture'] = [.35, .85]
    for sides, tag in (((mem,) if mem else (1, -1), 'côté mémorisé'), ((1, -1), 'deux côtés')):
        if tag == 'deux côtés' and not mem: continue
        cands = [(cx + r * math.sin(math.radians(axis + sd * 90 + off)), cz + r * math.cos(math.radians(axis + sd * 90 + off)))
                 for sd in sides for r in (4., 5., 6.5, 8., 10., 12.5, 15., 19., 24.) for off in (-60, -45, -30, -15, 0, 15, 30, 45, 60)]
        if not g:                         # nothing to read across: standing behind either end of the axis is the classic way to put the near thing against the far one
            cands += [(p[0] + math.sin(math.radians(a0 + da)) * r, p[1] + math.cos(math.radians(a0 + da)) * r) for p, a0 in ((ca, axis + 180), (cb, axis)) for r in (2., 3., 4.5, 6., 8., 11.) for da in (-25, -10, 0, 10, 25)]
        for layers in (2, 1):
            f = _base_frame(it, kind, actors=[x for x in it['subjects'] if x in C.actors], min_layers=layers)
            f['show'] = sorted(set(f.get('show', []) + [r for r in (a, b) if r]))
            if g: f['gap'] = dict(a=a, b=b, min=float(it.get('gap_min', .075)))
            if scale: f['scale'] = scale
            out.append(Variant('relation de côté', kind, f, cands=cands, heights=(1.45, 1.8, 2.3), shifts=(0.,), why=f"vue de côté ({tag}) : la distance entre « {a} » et « {b} » se lit dans l'image" if g else 'vue de côté',
                               relaxed=[] if layers == 2 else ['min_layers 2 → 1']))
    if g:           # last resort for a gap to read: any bearing, the solver's own rings (the gap rule still applies)
        f3 = dict(f, min_layers=1); out.append(Variant('relation, cadrage libre', kind, f3, cands=None, heights=(1.45, 1.8, 2.3), shifts=(0.,), why="le cadrage que le solveur trouve librement (la lisibilité de l'écart reste exigée)", relaxed=["côté de l'axe libre"]))
    if not g:
        f2 = dict(f); out.append(Variant('relation, cadrage libre', kind, f2, cands=None, heights=(1.45, 1.8, 2.3), shifts=(0.,), why="le cadrage que le solveur trouve librement autour des deux choses (plus de côté imposé)", relaxed=["côté de l'axe libre"]))
    return out


def ctx_memory(ctx): return ctx.memory if hasattr(ctx, 'memory') else {}


def v_danger(ctx, it, kind, threat_spec=None):
    geo, C = ctx; s = it['subjects'][0]; tid = it['threat']; tm = _mid(it)
    S, T = where(geo, C, s, tm), where(geo, C, tid, tm); d = math.hypot(S[0] - T[0], S[1] - T[1]) or 1.; u = ((S[0] - T[0]) / d, (S[1] - T[1]) / d); pe = (-u[1], u[0])
    backs = {'wide': (3.5, 5., 7.), 'full': (2.4, 3.2, 4.2), 'medium': (1.6, 2.1, 2.8), 'close': (1.1, 1.4, 1.8)}.get(kind, (2.4, 3.2, 4.2))
    cands = [(S[0] + u[0] * bk + pe[0] * lt, S[1] + u[1] * bk + pe[1] * lt) for bk in backs for lt in (-1.8, -1.1, -.5, .5, 1.1, 1.8)]
    cands += [(S[0] + u[0] * bk + pe[0] * lt, S[1] + u[1] * bk + pe[1] * lt) for bk in backs for lt in (-3., 3.)]
    lo, hi = it.get('threat_hidden') or ([.15, .6] if it.get('occlude') else [0., .6])
    spec = threat_spec or dict(id=tid, hidden=[lo, hi], behind_by=1.2)
    out = []
    for rel, tag in ((0, ''), (1, 'sans fond profond'), (2, 'sans occlusion voulue')):
        th = dict(spec)
        if rel >= 1: th['behind_by'] = .0
        if rel >= 2: th['hidden'] = [0., th['hidden'][1]]
        f = _base_frame(it, kind, actors=[s], threat=th, compose='thirds', min_layers=2 if rel == 0 else 1)
        _with_size(f, s, kind)
        out.append(Variant('danger', kind, f, cands=cands, heights=(1.45, 1.7, 2.0), shifts=(.28, -.28, 0.), **_mover(C, s, it), why='le sujet au premier plan, la menace au fond' + (' (cachée en partie)' if th['hidden'][0] > 0 else ''),
                           relaxed=[x for x in ([], ['fond profond'], ['fond profond', 'occlusion voulue'])[rel]]))
        if rel == 0 and not threat_spec:         # the reverse: the menace in the FOREGROUND, seen from behind and partly hiding the frame, the subject beyond it (over the shoulder of the menace)
            oc = [(T[0] - u[0] * bk + pe[0] * lt, T[1] - u[1] * bk + pe[1] * lt) for bk in (.9, 1.3, 1.8, 2.5) for lt in (-.7, -.4, .4, .7)]
            fo = _base_frame(it, kind, actors=[s], fg=[tid], compose='thirds', min_layers=1); _with_size(fo, s, kind if kind in ('wide', 'full') else 'full')
            out.append(Variant('danger par-dessus la menace', kind, fo, cands=oc, heights=(1.5, 1.75), shifts=(.3, -.3, 0.), track=s if travel(C, s, it['t0'], it['t1']) > 1.2 else None,
                               why="la menace au premier plan, vue de dos, et celui qu'elle regarde au-delà", relaxed=['menace au premier plan']))
    return out


def v_reveal(ctx, it, kind):
    k = it.get('stage', 0); n = max(2, it.get('of', 3)); f = k / (n - 1); hi = .86 - .66 * f; lo = max(0., hi - .35)
    spec = dict(id=it['threat'], hidden=[lo, hi], behind_by=1. + 2.5 * (1 - f), allow_headless=(k == 0))
    return v_danger(ctx, it, kind, threat_spec=spec)


def v_reaction(ctx, it, kind):
    geo, C = ctx; s = it['subjects'][0]; tm = _mid(it); S = where(geo, C, s, tm)
    radii = {'close': (1.0, 1.3, 1.7), 'medium': (1.7, 2.2, 2.9), 'full': (3.0, 4.0, 5.2), 'wide': (5., 7., 9.), 'establishing': (8., 11.)}.get(kind, (2., 3.))
    head = _heading(C, s, tm); out = []
    for arc, tag in (((head, 60), 'de face'), ((head, 100), 'de trois quarts'), (None, 'partout')):
        f = _base_frame(it, kind, actors=[s], face=[s], compose='thirds', min_layers=1)
        _with_size(f, s, kind)
        out.append(Variant('réaction', kind, f, cands=ring(S[0], S[1], radii, 10, arc), heights=(1.4, 1.6, 1.8), shifts=(.25, -.25, 0.), **_mover(C, s, it), why=f"le visage de {s} ({tag}) : la peur se lit",
                           relaxed=[] if arc and arc[1] == 60 else [tag]))
    return out


def v_ots(ctx, it, kind):
    geo, C = ctx; a = it.get('shoulder') or it['subjects'][0]; b = it.get('toward') or (it['subjects'][1] if len(it['subjects']) > 1 else None)
    if b is None: _fail(f"{it['id']} : « dialogue » demande deux sujets (celui dont on voit l'épaule, celui qu'on regarde)")
    tm = _mid(it); A, B = where(geo, C, a, tm), where(geo, C, b, tm); d = math.hypot(A[0] - B[0], A[1] - B[1]) or 1.; u = ((A[0] - B[0]) / d, (A[1] - B[1]) / d); pe = (-u[1], u[0])
    mem = ctx_memory(ctx).get(('side', tuple(sorted((a, b))), 'ots')); out = []
    for sides, tag in (((mem,) if mem else (1, -1), 'même côté de l\'axe'), ((1, -1), 'les deux côtés')):
        if tag == 'les deux côtés' and not mem: continue
        cands = [(A[0] + u[0] * bk + pe[0] * lt * sd, A[1] + u[1] * bk + pe[1] * lt * sd) for sd in sides for bk in (.9, 1.3, 1.8) for lt in (.35, .55, .8)]
        f = _base_frame(it, 'ots', actors=[b], fg=[a], face=[b], compose='thirds', thirds_x=.3)
        f['size'] = dict(subject=b, body_h=[.7, 3.2], name='ots')
        out.append(Variant('champ / contre-champ', 'ots', f, cands=cands, heights=(1.55, 1.7), shifts=(.3, -.3, .2, -.2), why=f"par-dessus l'épaule de {a}, {b} de face ({tag})", relaxed=[] if mem or tag != 'les deux côtés' else []))
    return out


def v_pov(ctx, it, kind):
    geo, C = ctx; a = it['pov']; sees = it['sees']; tm = _mid(it); f = _base_frame(it, 'pov', fg=[a])
    if sees in C.actors: f['actors'] = [sees]; hl = 1.55
    elif sees in geo.landmarks: f['show'] = sorted(set(f.get('show', []) + [sees]))
    elif isinstance(sees, (list, tuple)) and len(sees) == 3: f['points'] = [list(sees)]
    f['pov'] = a
    return [Variant('point de vue', 'pov', f, why=f"ce que {a} voit, depuis ses yeux")]


def v_disappear(ctx, it, kind):
    geo, C = ctx; ev = it['event']; who = ev['who']; te = float(ev['t']); wit = it.get('witness')
    spot = ev.get('spot')
    if spot is None: x, z = C.xz(who, te - .05 if ev['kind'] == 'vanish' else te + .15); spot = [x, 1.0, z]
    fx, fz = spot[0], spot[2]; tm = _mid(it)
    w = where(geo, C, wit, tm) if wit else None
    cx, cz = ((fx + w[0]) / 2, (fz + w[1]) / 2) if w else (fx, fz)
    ext = (math.hypot(fx - w[0], fz - w[1]) if w else 0.) + 1.5
    out = []
    for layers, (lw, lh) in ((2, (.24, .2)), (1, (.24, .2)), (1, (.15, .12))):
        f = _base_frame(it, 'wide', actors=[who] + ([wit] if wit else []), points=[list(spot)], min_layers=layers, legible={who: lh, **({wit: lw} if wit else {})})
        out.append(Variant('événement', 'wide', f, cands=ring(cx, cz, [ext * k for k in (1.3, 1.8, 2.4, 3.2)] + [6., 8., 11.], 10), heights=(1.5, 1.9), shifts=(0.,), fovs=(64., 72.),
                           window=(it['t0'], min(it['t1'], te + .1)) if ev['kind'] == 'vanish' else (max(it['t0'], te + .1), it['t1']), why=f"{who} {'disparaît' if ev['kind'] == 'vanish' else 'apparaît'} : un seul plan fixe tient le corps jusqu'à l'instant, et la peur de {wit} dans l'image",
                           relaxed=([] if layers == 2 else ['min_layers 2 → 1']) + ([] if lw > .2 else ['visages plus petits'])))
    return out


def v_aftermath(ctx, it, kind):
    geo, C = ctx; ev = it.get('event') or {}; wit = it.get('witness') or (it['subjects'][0] if it['subjects'] else None); spot = ev.get('spot') or it.get('spot')
    if spot is None and ev: x, z = C.xz(ev['who'], float(ev['t']) - .05); spot = [x, 1.0, z]
    if spot is None: _fail(f"{it['id']} : « aftermath » demande l'endroit vide (event.spot ou spot)")
    tm = _mid(it); W = where(geo, C, wit, tm) if wit else (spot[0], spot[2]); cx, cz = (spot[0] + W[0]) / 2, (spot[2] + W[1]) / 2; ext = math.hypot(spot[0] - W[0], spot[2] - W[1]) + 1.5
    out = []
    for layers in (2, 1):
        f = _base_frame(it, kind if kind in LADDER else 'medium', actors=[wit] if wit else [], points=[list(spot)], min_layers=layers)
        out.append(Variant('le vide', f['kind'], f, cands=ring(cx, cz, [ext * k for k in (1.2, 1.7, 2.3, 3.)] + [5., 7.], 10), heights=(1.5, 1.8), shifts=(0., .2), fovs=(60., 66.),
                           why='la place vide, et celui qui la regarde', relaxed=[] if layers == 2 else ['min_layers 2 → 1']))
    return out


BUILDERS = dict(establish=v_establish, relation=v_relation, danger=v_danger, reveal=v_reveal, reaction=v_reaction, detail=v_reaction, dialogue=v_ots, pov=v_pov,
                disappear=v_disappear, aftermath=v_aftermath)


# ---------------------------------------------------------------------------------------------------------------------- camera keys, ranking
class Ctx:
    def __init__(self, geo, C, aspect='9:16', memory=None, avoid=None, degrade=True): self.geo, self.C, self.aspect, self.memory, self.avoid, self.degrade = geo, C, aspect, memory if memory is not None else {}, avoid, degrade
    def __iter__(self): return iter((self.geo, self.C))


def camera_keys(dur, pos, look, fov, move='static', amount=.0, track=None, follow=None, offset=None):
    p0 = dict(on=follow, dx=round(float(offset[0]), 4), dz=round(float(offset[1]), 4), h=round(float(pos[1]), 4)) if follow else list(pos); l0 = dict(on=track, h=1.35) if track else list(look); p1 = p0 if follow else list(p0)
    if move in ('push', 'pull') and amount:
        f = [look[i] - pos[i] for i in range(3)]; n = math.sqrt(sum(v * v for v in f)) or 1.; sg = 1. if move == 'push' else -1.
        p1 = [pos[i] + sg * amount * f[i] / n for i in range(3)]
    k = lambda t, p: dict(t=round(t, 4), pos=p if follow else [round(float(v), 4) for v in p], look=l0 if track else [round(float(v), 4) for v in l0], fov=round(fov, 2), roll=0.)
    return {'rig': 'path', 'keys': [k(0., p0), k(dur, p1)]}


def _follow_keys(dur, who, look_ref, fov, h=1.62, sees_h=1.55, fwd=(0., 0.)):
    """a POV: the lens rides the character's eye (the painter reads {'on'} from the actor's track) and looks at what he looks at"""
    pt = lambda r, hh: dict(on=r, h=hh) if isinstance(r, str) else list(r)
    eye = dict(on=who, h=h, dx=round(fwd[0], 3), dz=round(fwd[1], 3))
    return {'rig': 'path', 'keys': [dict(t=0., pos=eye, look=pt(look_ref, sees_h), fov=fov, roll=0.), dict(t=round(dur, 4), pos=dict(eye), look=pt(look_ref, sees_h), fov=fov, roll=0.)]}


def _rank(ctx, it, var, alt):
    """what the solver's own score cannot know: the purpose of the shot. Lower is better."""
    geo, C = ctx; pen = 0.; tm = _mid(it); ar = CP.ASPECT[ctx.aspect]; pos, look, fov = alt['pos'], alt['look'], alt['fov']
    if it['purpose'] in ('relation',) and var.frame.get('gap'):
        g = CP.gap_len(geo, pos, look, fov, ar, var.frame['gap']['a'], var.frame['gap']['b']); pen -= min(g, .3) * 1.5
        for nm in (var.frame.get('scale') or {}): pen -= min(CP.landmark_share(pos, look, fov, ar, geo.land(nm))[0], .6) * .8      # the car as big as the rest allows
    if it['purpose'] in ('reaction', 'detail'):
        m = CP.measure(geo, C, pos, look, fov, ar, tm, (), var.frame['actors']); pen += m['actors'][var.frame['actors'][0]]['face_angle'] / 180. * .6
    if it['purpose'] in ('danger', 'reveal'):
        e = CP.extra_metrics(geo, C, var.frame, pos, look, fov, ar, tm).get('threat')
        if e: pen -= min(e['depth'], 14.) * .03; pen += 0.4 * abs(abs(e['ndc'][0]) - .5)           # deep in the picture, off the centre line
    if it['purpose'] == 'disappear':
        wit = it.get('witness')
        if wit:
            m = CP.measure(geo, C, pos, look, fov, ar, tm, (), [wit]); pen += m['actors'][wit]['face_angle'] / 180. * .8
    if ctx.memory.get('prev_pos'):                                              # a cut should move the camera: no jump cut on the same spot
        pp = ctx.memory['prev_pos']; pen -= min(math.hypot(pos[0] - pp[0], pos[2] - pp[1]), 4.) * .02
    pv = ctx.memory.get('prev')                                                 # same subject, same size as the shot before: the camera must move 30 degrees round him (the audit refuses less)
    if pv and it['subjects'][:1] and pv['subject'] == it['subjects'][0] and pv['kind'] == var.kind and pv['t1'] <= it['t0'] + 1e-6 and it['t0'] - pv['t1'] < .05:
        s0 = where(geo, C, it['subjects'][0], it['t0']); ang = abs((bearing(s0, (pos[0], pos[2])) - bearing(s0, pv['pos']) + 180) % 360 - 180)
        if ang < 30.: pen += 2. * (1. - ang / 30.) + .5
    return alt['score'] + pen + .012 * (alt['fov'] - min(FOVS.get(var.kind) or [alt['fov']]))


def _shot_for_audit(it, frame, cam, dur=None):
    return dict(id=it['id'], dur=dur or it['dur'], _t0=it['t0'], frame=frame, camera=cam)


def plan_shot(ctx, it, kind=None, tight_max=.2):
    """-> the shot plan of one beat; PlanError (French) if no variant of any acceptable size passes the preflight"""
    geo, C = ctx.geo, ctx.C; it = it if 'subjects' in it else normalise(it, geo, C); kind = kind or base_size(it); rejected = []
    kinds = [kind] + (LADDER[1:LADDER.index(kind)][::-1] if kind in LADDER and LADDER.index(kind) > 1 else [])      # then wider, one size at a time (down to 'wide'): never tighter than asked
    for level, kd in [(lv, k_) for lv in range(3 if ctx.degrade else 1) for k_ in kinds]:
        for var in BUILDERS[it['purpose']](ctx, it, kd):
            if ctx.avoid and var.frame.get('actors'): var.frame['avoid'] = list(ctx.avoid)
            if level: var.frame = soften(var.frame, level); var.relaxed = var.relaxed + [f'confort {level}']
            try:
                if var.kind == 'pov':
                    res = _try_pov(ctx, it, var)
                else:
                    t_a, t_b = var.window or (it['t0'], it['t1'])
                    fv = list(var.fovs or FOVS.get(var.kind) or [FOV.get(var.kind, 62.)]); fr = dict(var.frame, fovs=fv)
                    sol = CP.solve(geo, C, fr, t_a, t_b, ctx.aspect, fv[0], None, var.heights, None, (), 0., var.cands, var.shifts, var.look_at, top=80 if _after_same(ctx, it, var.kind) else 14, track=var.track, follow=var.follow)
                    alts = sorted(sol.get('alts') or [sol], key=lambda a: _rank(ctx, it, var, a))
                    res = None
                    for alt in alts[:6 if len(alts) <= 14 else 14]:
                        res = _finish(ctx, it, var, alt)
                        if res and not res['violations']: break
                    if res is None or res['violations']: raise PlanError('; '.join(str(x.msg) for x in (res or {}).get('violations', [])[:2]) or 'aucune caméra valide')
                res['relaxed'] = var.relaxed + ([f"taille {kind} → {kd}"] if kd != kind else []); res['rejected'] = rejected; res['why'] = var.why; res['degraded'] = level
                ctx.memory['prev_pos'] = (res['camera']['keys'][0]['pos'][0], res['camera']['keys'][0]['pos'][2]) if not isinstance(res['camera']['keys'][0]['pos'], dict) else None
                ctx.memory['prev'] = dict(subject=it['subjects'][0] if it['subjects'] else None, kind=res['kind'], pos=ctx.memory['prev_pos'], t1=it['t1']) if ctx.memory['prev_pos'] else None
                return res
            except PlanError as e:
                rejected.append(f"{var.name} ({kd}{', ' + ', '.join(var.relaxed) if var.relaxed else ''}) : {e}")
    raise PlanError(f"{it['id']} ({it['purpose']}, {kind}) : aucun plan ne passe la préparation. " + ' | '.join(rejected[:4]))


def soften(frame, level):
    """COMFORT rules relaxed, SAFETY and the story never: what must be seen stays seen, unhidden, with no wall and no zoom. Level 1: no caption band, a looser margin, no
    layer count, faces and gaps 30 % smaller, sizes of shot widened, the menace need not be behind. Level 2: faces and gaps 50 % smaller, no size of shot."""
    f = dict(frame); f.pop('avoid', None); f.pop('min_layers', None); f['margin'] = .97 if level == 1 else 1.
    k = .7 if level == 1 else .5
    if f.get('legible'): f['legible'] = {a: v * k for a, v in f['legible'].items()}
    if f.get('gap'): f['gap'] = dict(f['gap'], min=f['gap']['min'] * (.8 if level == 1 else .6))
    if f.get('size'):
        lo, hi = f['size']['body_h']; f['size'] = dict(f['size'], body_h=[lo * .8, hi * 1.25]) if level == 1 else None
        if not f['size']: f.pop('size')
    if f.get('threat'): f['threat'] = dict(f['threat'], behind_by=None if level else f['threat'].get('behind_by'), hidden=[0., f['threat']['hidden'][1]])
    return f


def _after_same(ctx, it, kind):
    """the shot just before was on the same subject at the same size and ends where this one starts: more candidates are needed to find one 30 degrees round"""
    pv = ctx.memory.get('prev')
    return bool(pv and it['subjects'][:1] and pv['subject'] == it['subjects'][0] and pv['kind'] == kind and abs(it['t0'] - pv['t1']) < .05)


def _finish(ctx, it, var, alt):
    geo, C = ctx.geo, ctx.C; push = it.get('move') in ('push', 'pull')
    for move, amt in ((it.get('move', 'static'), float(it.get('amount', .6))), ('static', 0.)) if push else (('static', 0.),):
        cam = camera_keys(it['dur'], alt['pos'], alt['look'], alt['fov'], move, amt, var.track, var.follow, alt.get('offset'))
        shot = _shot_for_audit(it, var.frame, cam, dur=(var.window[1] - it['t0']) if var.window and var.window[1] < it['t1'] else None)
        if var.window and var.window[0] > it['t0']: shot = dict(shot, _t0=var.window[0], dur=it['t1'] - var.window[0])
        viol, met = CP.audit_shot(shot, C, geo, ctx.aspect)
        if not viol: break
    side = None
    if it['purpose'] == 'dialogue':
        a = it.get('shoulder') or it['subjects'][0]; b = it.get('toward') or it['subjects'][1]; tm = _mid(it)
        side = _side(where(geo, C, a, tm), where(geo, C, b, tm), (alt['pos'][0], alt['pos'][2])); ctx.memory[('side', tuple(sorted((a, b))), 'ots')] = side
    if it['purpose'] == 'relation' and var.frame.get('gap'):
        g = var.frame['gap']; ca, cb = where(geo, C, g['a'], 0), where(geo, C, g['b'], 0); side = _side(ca, cb, (alt['pos'][0], alt['pos'][2])); ctx.memory[('relation', g['a'], g['b'])] = side
    return dict(id=it['id'], t0=it['t0'], t1=it['t1'], dur=it['dur'], purpose=it['purpose'], style=var.name, kind=var.kind, frame=var.frame, camera=cam, fov=alt['fov'],
                shake=round(.08 + .06 * float(it.get('tension', .5)), 3), violations=viol, metrics=met, side=side, subjects=it['subjects'], tension=it.get('tension', .5), event=it.get('event'))


def _try_pov(ctx, it, var):
    geo, C = ctx.geo, ctx.C; a = it['pov']; sees = it['sees']; fov = FOV['pov']
    look_ref = sees if isinstance(sees, str) and sees in C.actors else (list(sees) if isinstance(sees, (list, tuple)) else None)
    if look_ref is None:
        b = geo.land(sees); look_ref = [(b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2]
    hd0 = math.radians(_heading(C, a, _mid(it))); cam = _follow_keys(it['dur'], a, look_ref, fov, fwd=(math.sin(hd0) * .34, math.cos(hd0) * .34))     # in front of the face, not inside the head
    shot = _shot_for_audit(it, var.frame, cam); viol, met = CP.audit_shot(shot, C, geo, ctx.aspect)
    # the eye looks where the body is turned: a POV that sees what the character's back is to is not his
    tm = _mid(it); P = C.xz(a, tm); tgt = where(geo, C, sees, tm) if isinstance(sees, str) else (sees[0], sees[-1]); hd = _heading(C, a, tm)
    off = abs((bearing(P, tgt) - hd + 180) % 360 - 180)
    if off > 80.: viol.append(Violation('pov_incohérent', f"{it['id']} : {a} est tourné à {off:.0f}° de ce que le plan lui fait voir (maximum 80°) : ce n'est pas son regard", tm, a))
    if viol: raise PlanError('; '.join(x.msg for x in viol[:2]))
    return dict(id=it['id'], t0=it['t0'], t1=it['t1'], dur=it['dur'], purpose='pov', style=var.name, kind='pov', frame=var.frame, camera=cam, fov=fov,
                shake=round(.08 + .06 * float(it.get('tension', .5)), 3), violations=[], metrics=met, side=None, subjects=[a], tension=it.get('tension', .5), event=None)


# ---------------------------------------------------------------------------------------------------------------------- sequences and their audit
class Plan:
    def __init__(self, shots, violations, events, sizes): self.shots, self.violations, self.events, self.sizes = shots, violations, events, sizes

    def report(self):
        return dict(shots=[dict(id=s['id'], t0=s['t0'], t1=s['t1'], purpose=s['purpose'], style=s['style'], kind=s['kind'], fov=s['fov'], why=s['why'], relaxed=s['relaxed'],
                                shake=s['shake'], degraded=s.get('degraded', 0), metrics=s['metrics'], rejected=s['rejected'][:3]) for s in self.shots],
                    violations=[v.to_json() for v in self.violations], events=self.events, sizes=self.sizes)

    def episode_shots(self, stage='station'):
        """what the film builder (films/pompe_continuite.py `add`) needs: id, stage, dur, frame, camera, shake (the caller adds `env`: outside / inside)"""
        return [dict(id=s['id'], stage=stage, dur=s['dur'], frame=s['frame'], camera=s['camera'], shake=s['shake']) for s in self.shots]


def plan_sequence(geo, C, intents, aspect='9:16', tight_max=.2, memory=None, avoid=None, degrade=True):
    """a camera for every beat, then the audit of the sequence (rhythm, jump cuts, the 180 degrees rule, close-up budget, filmed events)"""
    ctx = Ctx(geo, C, aspect, memory, avoid, degrade); its = [normalise(i, geo, C) for i in intents]; sizes = assign_sizes(its, tight_max); shots = []
    for it, sz in zip(its, sizes): shots.append(plan_shot(ctx, it, sz, tight_max))
    events = [dict(ev, shot=s['id']) for s in shots if s.get('event') for ev in [s['event']]]
    return Plan(shots, audit_sequence(shots, C, geo, aspect, tight_max), events, sizes)


def audit_sequence(shots, C, geo, aspect='9:16', tight_max=.2):
    v = []; tot = sum(s['dur'] for s in shots) or 1.
    tight = sum(s['dur'] for s in shots if s['kind'] in TIGHT)
    if tight / tot > tight_max + 1e-9: v.append(Violation('trop_de_gros_plans', f"{tight / tot * 100:.0f} % du temps en gros plan (maximum {tight_max * 100:.0f} %)"))
    run = 1
    for k in range(1, len(shots)):
        a, b = shots[k - 1], shots[k]
        ca, cb = SIZE_CLASS.get(a['kind'], 2), SIZE_CLASS.get(b['kind'], 2)
        run = run + 1 if ca == cb else 1
        if run >= 3: v.append(Violation('rythme_monotone', f"{a['id']}…{b['id']} : trois plans de suite de la même taille « {b['kind']} »", b['t0'], None))
        if a['subjects'][:1] == b['subjects'][:1] and a['subjects'] and ca == cb and a['kind'] == b['kind']:
            pa, pb = _pos(a), _pos(b); s0 = where(geo, C, a['subjects'][0], b['t0'])
            if pa and pb:
                ang = abs((bearing(s0, pb) - bearing(s0, pa) + 180) % 360 - 180)
                if ang < 30.: v.append(Violation('saut_de_plan', f"{a['id']} → {b['id']} : même sujet, même taille, caméra déplacée de {ang:.0f}° seulement (minimum 30°) : un faux raccord", b['t0'], None))
        if a.get('side') and b.get('side') and a['purpose'] == b['purpose'] and set(a['subjects'][:2]) == set(b['subjects'][:2]) and a['side'] != b['side']:
            v.append(Violation('axe_franchi', f"{a['id']} → {b['id']} : la caméra change de côté de l'axe entre deux plans de la même paire (règle des 180°)", b['t0'], None))
    for s in shots:
        if s['violations']: v += s['violations']
        ev = s.get('event')
        if ev: v += audit_event(s, C, geo, aspect)
    return v


def _pos(s):
    p = s['camera']['keys'][0]['pos']
    return None if isinstance(p, dict) else (p[0], p[2])


def audit_event(s, C, geo, aspect='9:16'):
    """a vanish / appear beat must be FILMED as an event: still camera, the body in the picture up to (or from) the instant, the place seen, the witness there"""
    ev = s['event']; v = []; te = float(ev['t']); keys = s['camera']['keys']; sid = s['id']
    if any(isinstance(k['pos'], dict) for k in keys): v.append(Violation('disparition_suivie', f"{sid} : la caméra suit un acteur pendant l'événement : on filme une marche, pas la disparition", te, ev['who']))
    else:
        mv = math.dist(keys[0]['pos'], keys[-1]['pos'])
        if mv > .05: v.append(Violation('disparition_suivie', f"{sid} : la caméra bouge de {mv:.2f} m pendant l'événement : un plan fixe est exigé (on ne suit pas la marche)", te, ev['who']))
    ar = CP.ASPECT[aspect]; pos, look, fov = CP.cam_at(dict(camera=s['camera']), min(max(te - s['t0'], 0.), s['dur']), C, s['t0'])
    tt = te - .1 if ev['kind'] == 'vanish' else te + .15
    m = CP.measure(geo, C, pos, look, fov, ar, tt, (), [ev['who']])['actors'][ev['who']]
    if not m['inframe'] or m['hidden_by']: v.append(Violation('événement_non_filmé', f"{sid} : {ev['who']} n'est pas visible dans l'image à {tt:.2f} s : l'événement n'est pas filmé", tt, ev['who']))
    return v


def audit_blocking_events(C, events, walk_max=.9, window=2.):
    """INTERFACE FOR THE BLOCKING (not changed here): a body that is said to vanish must not WALK afterwards, and one that appears must not have walked in.
    -> [Violation]; the integrator removes the walk from the blocking (a `vanish` / `appear` beat that hides the actor) or accepts the report."""
    v = []
    for ev in events:
        te = float(ev['t']); a = ev['who']
        t_a, t_b = (te, te + window) if ev['kind'] == 'vanish' else (te - window, te)
        (x0, z0), (x1, z1) = C.xz(a, t_a), C.xz(a, t_b); d = math.hypot(x1 - x0, z1 - z0)
        if d > walk_max: v.append(Violation('disparition_marchée', f"{a} {'disparaît' if ev['kind'] == 'vanish' else 'apparaît'} à {te:.1f} s mais le blocage le fait marcher {d:.1f} m dans les {window:.0f} s {'suivantes' if ev['kind'] == 'vanish' else 'précédentes'} : un événement surnaturel n'est pas une marche", te, a, walk=d))
    return v
