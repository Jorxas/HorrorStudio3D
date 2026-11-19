"""Narrative director: story INTENTIONS -> the shot list a cinematographer can actually shoot.

What was missing, and what this adds
------------------------------------
The studio already owned three of the four layers of a scene:

  * the **actors**: `acting/timeline.py` (verbs, paths, gaze, gestures, reactions, `footing`, `approach`);
  * the **cinematographer**: `acting/cinema.py` (a camera *intention* -> a camera *placement*, probes, the
    180-degree rule, no zoom ever);
  * the **light**: `engines/pixel3d/lighting.py` (a narrative lighting block per episode and per shot).

What nobody owned was the **director**: the layer that decides, beat by beat, *why* we cut and therefore
*which* intention the cinematographer receives. Two things filled that hole, and neither is a director:

  * `cinema.auto_camera()` -- the coverage planner used when a shot carries no camera at all. It is a
    reasonable default (wide on entering a set, follow on whoever moves, dialogue when two people talk) but
    it reads only the current shot: it cannot establish a place, reveal something in the background, or
    remember that the last three shots were the same size;
  * a hand-written `"camera"` dict per shot in `examples/**.json`. That works and it is what the delivered
    demos do -- but a hand-placed camera is not a director either, it is a storyboard already drawn.

This module is the missing layer and nothing else. It reads a **narrative scenario** (beats with an
intention, named stage marks, business, a threat) and emits a normal `engine_version: 2` episode. Every
camera it writes is an *intention* (`shot` / `move` / `on` / `from`), never a position, a target or a lens:
the cinematographer keeps the last word, so a camera this module asks for that cannot see its subject is
still re-solved, re-probed and re-framed by `cinema.solve` exactly as a hand-written one would be.

The grammar (a `"narrative"` block, in place of `"episode"`)
-----------------------------------------------------------
{"options": "directed" | "legacy" | {...},      which validated opt-ins to switch on (see OPTION_SETS)
 "style": "pixel3d", "music": "...", "hud": {...}, "series": "...",
 "cast": {"lea": {"ref": "lea", "role": "protagonist"}, ...},
 "stages": {"rue": {"set": {"type": "city_street", ...},      the set spec, as usual
                    "look": [x, z],                           the centre of the action on that stage
                    "open": [x, z],                           the open side: where a wide shot may stand
                    "ring": 6.5,                              radius the wide shots orbit on (default RING)
                    "marks": {"porte": [x, z], ...},          named spots, so a beat never writes coordinates
                    "light": {...},                           lighting intention of the stage
                    "weather": "rain" | "none",               the weather of THIS place (indoors: "none")
                    "weather_amount": 0..1}},
 "beats": [{"stage": "rue",                     which stage (defaults to the previous beat's)
            "intent": "establish",              WHY we cut -- the only camera decision a beat makes
            "who": "tom", "text": "...", "dur": 2.8,          the line (who speaks, what, how long)
            "on": ["lea", "tom"],               whom the shot is about (default: the speaker, or the stage cast)
            "place": {"lea": "porte", ...},     put actors on named marks (first beat of a stage, or a jump)
            "do": [{"who": "lea", "walk_to": "porte"}, ...],  business, using marks instead of coordinates
            "threat": "ombre",                  a mark (or a character) the reveal / the low angle is about
            "light": {...} | "none",            lighting intention of this beat alone
            "react": false}]}                   turn off the automatic listener reaction of this beat

A beat's `do` entries are the engine's own verbs (`walk_to`, `look_at`, `turn_to`, `face`, `gesture`,
`react`, `open`, ...) written as `{"who": ..., "<verb>": <argument>}`; a named mark is resolved to its
coordinates, `at` / `dur` are filled in from the length of the line when the beat does not say. Faces and
listener reactions that the beat does not spell out are derived from the words by the tables of
`director/scene.py` -- the same tables the offline library director already uses, not a second copy.

Two guarantees this module owes the rest of the studio
-----------------------------------------------------
1. **Nothing is activated behind anyone's back.** `"options"` names one of the three sets of OPTION_SETS,
   and the compiled episode records what it asked for under `"_directed"`. `"legacy"` writes no camera and
   no opt-in key at all: the same beats, the same business, the same lines, covered by the engine's own
   conventions. That is what makes an honest A/B possible from a single scenario file.
2. **The camera travels.** Between two consecutive shots the point the wide family films from drifts
   around the action, in one direction, by at least MIN_TURN radians (coming back to the angle we just left
   is a jump cut) and never beyond MAX_TURN of the open side (crossing the line is a mistake, not a style);
   at that wall the drift turns round. For the tight family the module writes no side at all: there the face
   decides, and `cinema.solve` already follows it. Three further rules refuse a shot the SET cannot hold
   (`_fits`, `_pair_shot`) and aim the subject at the lens on a reveal (`_face_the_lens`) -- each of them
   written only after the defect it prevents had been rendered, measured and looked at. The result is
   measurable end to end: `tools/storyboard_qc.py` reads the camera the engine really solved.
"""
import json, math, re

from . import scene as SC

RING = 6.0              # default radius (m) the wide family orbits the action on
MIN_TURN = .33          # rad: a cut must move the wide camera at least this far around the action (~19 deg)
MAX_TURN = 1.25         # rad: ... and never further (~72 deg), so the line of action is not crossed
REVEAL_BACK = 2.0       # m: how far behind the subject (away from the threat) the reveal camera is aimed from

# ---------------------------------------------------------------- the intentions a beat may carry
# size      : the shot the cinematographer is asked for
# move      : the camera move (ALL of them are translations -- cinema.apply_move never touches the lens)
# amount    : 0..1, how far the move goes
# subjects  : 'speaker' | 'all' | 'threat' | 'mover'  -> who the shot is about when the beat does not say
# wide      : True when the shot belongs to the family the director gives a side to (`from`); False lets the
#             cinematographer pick the side from the face, which is what a tight shot must do
INTENTS = {
    'establish':  dict(size='establishing', move='crane_down', amount=.35, subjects='all',     wide=True,
                       why="situer le lieu : le decor d'abord, les personnages dedans"),
    'situate':    dict(size='wide',         move='static',     amount=0.,  subjects='all',     wide=True,
                       why="situer l'action dans le lieu deja etabli"),
    'follow':     dict(size='full',         move='follow',     amount=.5,  subjects='mover',   wide=True,
                       why='suivre celui qui se deplace, la camera marche avec lui'),
    'approach':   dict(size='medium_full',  move='dolly_in',   amount=.55, subjects='speaker', wide=True,
                       why="s'approcher : la camera avance physiquement, elle ne zoome pas"),
    'interact':   dict(size='two_shot',     move='static',     amount=0.,  subjects='all',     wide=False,
                       size2='medium_full', eyes=True,
                       why="deux corps qui agissent ensemble, cadres jusqu'a la taille"),
    'exchange':   dict(size='dialogue',     move='static',     amount=0.,  subjects='all',     wide=False,
                       eyes=True, why='un echange : plan-contrechamp, le regard reste du bon cote'),
    'shoulder':   dict(size='ots',          move='static',     amount=0.,  subjects='all',     wide=False,
                       eyes=True, why="par-dessus l'epaule : on ecoute avec celui qui ecoute"),
    'react':      dict(size='close',        move='static',     amount=0.,  subjects='speaker', wide=False,
                       why='une reaction : le visage, assez pres pour la lire'),
    'realize':    dict(size='close',        move='dolly_in',   amount=.4,  subjects='speaker', wide=False,
                       why='il comprend : la camera se resserre en avancant'),
    # `wide`, not `full`, and the reason is measurable: a reveal is a shot with TWO things in it, and at a
    # 2.25 m image height the subject fills a 9:16 frame from mid-thigh up -- rendered and looked at, the
    # threat four metres behind her was entirely hidden by her own body. At 4.2 m she takes about a third
    # of the height and the background she is standing in front of exists again.
    'reveal':     dict(size='wide',         move='dolly_out',  amount=.35, subjects='speaker', wide=True,
                       why='devoiler : la camera se place pour que la menace soit DERRIERE le sujet'),
    'threaten':   dict(size='medium',       move='dolly_in',   amount=.35, subjects='threat',  wide=True,
                       angle='low', why="la menace, vue d'en bas : elle domine le cadre"),
    'flee':       dict(size='full',         move='track',      amount=.6,  subjects='mover',   wide=True,
                       why='la fuite : la camera glisse lateralement, elle ne tourne pas sur elle-meme'),
    'leave':      dict(size='full',         move='dolly_out',  amount=.45, subjects='all',     wide=True,
                       why='on quitte le lieu : la camera recule et le decor reprend la place'),
}

# ---------------------------------------------------------------- what a run is allowed to switch on
# Three named sets, so that the SAME scenario file can be shot three ways and the three can be compared. Each
# one adds exactly one thing to the one above it, which is the only way to say what each contributes:
#
#   legacy    the plain conventions: the beats, their business, their lines -- and NO camera at all. The
#             engine then covers the scene with `cinema.auto_camera()`, which is what every episode without a
#             "camera" key has always got. No opt-in key, no lighting block. Historical behaviour.
#   intents   + the camera INTENTIONS this module derives from each beat's intent (establish, reveal, react...)
#             and the lighting intention of the stages. Still not one opt-in key.
#   directed  + the opt-in keys that earlier lots delivered and measured, listed below.
#
# `keys` are keys the engines ALREADY read; this module invents no behaviour, it only decides whether to write
# them. Nothing here is ever switched on globally: it is written on ONE episode, by name, and recorded in
# `episode["_directed"]` so a reader can see what was asked for.
OPTION_SETS = {
    'legacy':   dict(camera=False, light=False, keys={}),
    'intents':  dict(camera=True,  light=True,  keys={}),
    'directed': dict(camera=True,  light=True,  keys={
        'profile': 'production',        # hstudio/profiles.py   : env riche, vrais bruitages, sous-titres surs, regard (31/10)
        'eyeline': 'smooth',            # acting/gaze.py       : the head turns instead of snapping
        'footing': 'path',              # acting/timeline.py   : the body faces where it walks
        'approach': 'directed',         # acting/approach.py   : the walk aims, slows down, arrives
        'camera_face_track': True,      # acting/cinema.py     : the camera is placed so the face is seen
        'camera_clear_face': True,      # engines/pixel3d/acted.py : ... and not behind the subject's own arm (était écrit 'clear_face', clé que personne ne lit)
        'head_room': True,              # acting/cinema.py     : ... and the whole head fits across 9:16
    }),
}


def options_of(nar):
    """-> (the option set to apply, its name). A dict is taken as a hand-written `keys` set."""
    o = nar.get('options', 'directed')
    if isinstance(o, dict): return dict(camera=True, light=True, keys=dict(o)), 'sur mesure'
    name = str(o or 'legacy')
    if name not in OPTION_SETS:
        raise ValueError(f'jeu d\'options inconnu : {name} (connus : {", ".join(OPTION_SETS)})')
    s = OPTION_SETS[name]
    return dict(camera=s['camera'], light=s['light'], keys=dict(s['keys'])), name


# ---------------------------------------------------------------- stages: named marks, a centre, an open side
class Stage:
    """one location of the scenario: its set spec, where the action is, and the names a beat may use"""
    def __init__(st, name, spec):
        st.name = name; st.spec = spec
        st.set = dict(spec.get('set') or {'type': 'park'})
        st.marks = {k: [float(v[0]), float(v[1])] for k, v in (spec.get('marks') or {}).items()}
        st.look = [float(v) for v in (spec.get('look') or _mid(st.marks) or [0., 6.])]
        op = spec.get('open')
        st.open = [float(v) for v in op] if op else [st.look[0], st.look[1] - RING]
        st.ring = float(spec.get('ring', RING))
        st.light = spec.get('light')
        # weather belongs to the PLACE, not to the episode. An episode-level "rain" falls on every set it
        # owns, indoors included -- measured on the first cut of this scenario: the corridor of the hall was
        # rendered with rain streaks across it. A stage that says nothing inherits the episode's weather.
        st.weather = spec.get('weather')
        st.weather_amount = spec.get('weather_amount')
        st.az0 = math.atan2(st.open[0] - st.look[0], st.open[1] - st.look[1])   # the open side, as an azimuth
        st.bounds = st._bounds()
        st.lateral = st._lateral(spec.get('lateral'))

    def _bounds(st):
        """(x0, z0, x1, z1) of the set the engine really builds, or None when it cannot be built here"""
        try:
            from ..engines.pixel3d.sets import make_set
            from ..engines.pixel3d.stage import SetWorld
            return tuple(float(v) for v in SetWorld(make_set(st.set.get('type', 'park'), st.set)).bounds())
        except Exception:
            return None

    def room(st, p, d):
        """metres of set available from point p walking in direction d (unit) before hitting the bounds.

        This is the question every camera question reduces to: a shot needs a certain standoff from its
        subject, and either the room exists in that direction or the shot does not exist. None bounds means
        the set could not be built here, and then the answer is "plenty" -- a director must not refuse a
        shot on a guess."""
        if st.bounds is None: return 1e9
        x0, z0, x1, z1 = st.bounds
        tmax = 1e9
        for c, lo, hi, k in ((p[0], x0, x1, d[0]), (p[1], z0, z1, d[1])):
            if abs(k) < 1e-6:
                if not (lo <= c <= hi): return 0.
                continue
            tmax = min(tmax, max((lo - c) / k, (hi - c) / k))
        return max(0., tmax)

    def _lateral(st, given):
        """how many metres of set there are ACROSS the viewing axis, centred on the action.

        This is the number that decides which shots the stage can physically hold. A 9:16 frame of image
        height h is h * 9/16 wide, and that width has to exist in the set at the plane of the subjects: ask a
        15 x 2.6 m corridor for an establishing shot and `cinema.solve` has no choice but to back into a wall
        and widen the lens past 79 degrees, which the studio's own quality control reports as a defect
        (`lens_widened`). Read off the set the engine really builds, not declared by hand -- a scenario that
        changes a corridor's `width` gets the new answer for free. `lateral` in the stage spec overrides it
        (and keeps the compiler usable when the engine cannot be imported)."""
        if given is not None: return float(given)
        if st.bounds is None: return 1e9    # unknown: never downgrade a shot on a guess
        x0, z0, x1, z1 = st.bounds
        rx, rz = math.cos(st.az0), -math.sin(st.az0)        # across the viewing axis
        half = min(abs(c - v) for c, v, k in ((st.look[0], x0, rx), (st.look[0], x1, rx),
                                              (st.look[1], z0, rz), (st.look[1], z1, rz)) if abs(k) > .3)
        return 2 * max(.5, half)

    def point(st, az, r=None):
        """a point on the ring around the action, at azimuth az -- what a beat writes as "from" """
        r = st.ring if r is None else r
        return [round(st.look[0] + math.sin(az) * r, 2), round(st.look[1] + math.cos(az) * r, 2)]

    def resolve(st, v):
        """a named mark, a [x, z] pair, or a set anchor name (left to the engine) -> what the episode writes"""
        if isinstance(v, (list, tuple)) and len(v) == 2: return [round(float(v[0]), 2), round(float(v[1]), 2)]
        if isinstance(v, str) and v in st.marks: return list(st.marks[v])
        return v


def _mid(marks):
    if not marks: return None
    xs = [p[0] for p in marks.values()]; zs = [p[1] for p in marks.values()]
    return [sum(xs) / len(xs), sum(zs) / len(zs)]


# ---------------------------------------------------------------- business: {"who", "<verb>": arg} -> an action
# The verbs are the engine's own (director/validate.py: VERBS). What this table says is only WHERE the
# argument of each verb goes, so that a beat can write a mark name instead of a pair of coordinates.
ARG_OF = {'walk_to': 'to', 'run_to': 'to', 'sneak_to': 'to', 'go': 'to', 'enter': 'set', 'exit': 'set',
          'turn_to': 'target', 'look_at': 'target', 'follow': 'target', 'give': 'to',
          'face': 'name', 'gesture': 'name', 'react': 'kind', 'open': 'door', 'close': 'door',
          'pick': 'what', 'take': 'what', 'put': 'what', 'sit': 'what', 'stand': 'what'}
PLACED = ('walk_to', 'run_to', 'sneak_to', 'go', 'turn_to', 'look_at')     # verbs whose argument may be a mark
MOVERS = ('walk_to', 'run_to', 'sneak_to', 'go')


def _actions(beat, stage, dur, cast_ids):
    """the `actions` of a beat: its own business, then the acting the words imply (faces, listener reactions)"""
    out = []; movers = []
    for b in beat.get('do') or []:
        b = dict(b); who = b.pop('who', None) or beat.get('who')
        at = b.pop('at', None); d = b.pop('dur', None)
        verb = next((k for k in b if k in ARG_OF), None)
        if verb is None: raise ValueError(f'action sans verbe connu : {b!r} (verbes : {", ".join(sorted(ARG_OF))})')
        arg = b.pop(verb)
        a = {'who': who, 'do': verb, ARG_OF[verb]: stage.resolve(arg) if verb in PLACED else arg}
        a.update({k: v for k, v in b.items() if not k.startswith('_')})
        if at is not None: a['at'] = round(float(at), 2)
        if d is not None: a['dur'] = round(float(d), 2)
        elif verb in ('look_at', 'turn_to', 'gesture'): a['dur'] = round(min(2.2, max(1.1, dur * .55)), 2)
        out.append(a)
        if verb in MOVERS and who: movers.append(who)
    # what the words say, with the tables director/scene.py already uses (one source, not a copy)
    txt = (beat.get('text') or '').lower(); who = beat.get('who')
    if who and beat.get('feel') is not False:
        f = beat.get('feel') or next((f for p, f in SC.FACES if re.search(p, txt)), None)
        if f and not any(a['do'] == 'face' and a['who'] == who for a in out):
            out.append({'who': who, 'do': 'face', 'name': f})
        g = next(((g, dd) for p, g, dd in SC.GESTURES if re.search(p, txt)), None)
        if g and not any(a['do'] == 'gesture' and a['who'] == who for a in out):
            out.append({'who': who, 'do': 'gesture', 'name': g[0], 'at': round(min(.4, dur * .15), 2), 'dur': g[1]})
        if beat.get('react') is not False and f in ('surprised', 'scared'):
            other = next((c for c in cast_ids if c != who and not any(a['who'] == c and a['do'] == 'react' for a in out)), None)
            if other: out.append({'who': other, 'do': 'react', 'kind': 'gasp' if f == 'surprised' else 'flinch',
                                  'at': round(max(.3, min(dur * .6, dur - .6)), 2)})
    return out, movers


def _eyes(acts, subjects, dur):
    """two characters in the same frame who talk to each other LOOK at each other.

    Without this the blocking of the stage decides: everyone faces the centre of the action, the camera of a
    two-shot stands perpendicular to the line between them, and one of the two shows the camera the flat
    back of a cubic head. Measured on the street `interact` of `dernier_bus` before and after the rule, with
    nothing else changed: worst face angle 148 -> 121 deg, and the samples outside the readable cone over
    the whole scene 10/68 -> 0/46. It does not fix every frame by itself -- `_pair_shot` and the blocking of
    the stage do the rest -- but it removes the systematic cause. Only added when the beat's own business
    says nothing about where these two look: a beat that aims a gaze somewhere keeps it."""
    if len(subjects) != 2: return acts
    a, b = subjects[:2]
    for who, other in ((a, b), (b, a)):
        if any(x['who'] == who and x['do'] in ('look_at', 'turn_to') for x in acts): continue
        acts.append({'who': who, 'do': 'look_at', 'target': other, 'at': .1,
                     'dur': round(max(1.2, dur * .8), 2)})
    return acts


def _face_the_lens(acts, who, point, dur):
    """aim a character's body and gaze at a point -- used by `reveal`, and only by it.

    A reveal is the one shot of the grammar where the audience is told something the CHARACTER has not
    seen: the threat is behind her, in the frame, and her face is what the shot is for. That only works if
    she is looking somewhere else, towards the lens. Rendered and looked at before this rule existed, both
    reveals of `dernier_bus` showed the back of a cubic head -- a blank slab -- because the scenario's own
    business had turned her towards the threat, which is the instinctive thing to write and the exact
    opposite of what the shot needs.

    The point is the camera the DIRECTOR chose, which is why this lives here and not in the scenario: the
    scenario does not know where the camera will stand, and a coordinate written by hand would be wrong the
    moment anything moves. Any turn or gaze the beat gave this character is replaced, not stacked."""
    out = [a for a in acts if not (a['who'] == who and a['do'] in ('turn_to', 'look_at'))]
    out.insert(0, {'who': who, 'do': 'turn_to', 'target': list(point), 'at': .15,
                   'dur': round(min(1.6, max(.9, dur * .5)), 2)})
    out.insert(1, {'who': who, 'do': 'look_at', 'target': list(point), 'at': .25,
                   'dur': round(max(1.2, dur * .85), 2)})
    return out


# ---------------------------------------------------------------- the director itself
def _subjects(beat, rec, stage, cast_ids, movers):
    on = beat.get('on')
    if on: return [c for c in on if c in cast_ids] or cast_ids[:1]
    rule = rec['subjects']
    if rule == 'threat':
        th = beat.get('threat')
        return [th] if th in cast_ids else cast_ids[:1]
    if rule == 'mover' and movers: return movers[:1]
    if rule == 'speaker' and beat.get('who') in cast_ids: return [beat['who']]
    return list(cast_ids)


def _side_az(stage, state, intent, beat, subjects, positions):
    """where the wide family films from, as an azimuth around the action.

    The rule is physical, not decorative. Between two shots the camera **drifts around the action in one
    direction**, by at least MIN_TURN (coming back to the angle we just left is a jump cut) and never
    beyond az0 +- MAX_TURN of the open side of the set -- crossing the line of action is a mistake, not a
    style. When the drift reaches that wall it turns round and comes back the other way, which is what a
    crew does on a real set and what keeps a long scene from showing the same two angles over and over.

    A reveal is the exception that proves the rule: there the azimuth is dictated by the geometry -- the
    camera stands on the far side of the subject from the threat, because that is the only place from which
    the threat is BEHIND him in the frame. `state` is the per-stage drift: {'az', 'dir'}."""
    if intent == 'reveal' and beat.get('threat') is not None:
        # the threat is either a named mark of the stage or a character, in which case it is wherever the
        # business has left him: a reveal must be computed on the geometry of the moment, not of the file
        th = positions.get(beat['threat']) or stage.resolve(beat['threat'])
        sub = next((positions[c] for c in subjects if c in positions), None)
        if isinstance(th, (list, tuple)) and len(th) == 2 and sub:
            dx, dz = sub[0] - th[0], sub[1] - th[1]; L = math.hypot(dx, dz) or 1.
            # the camera on the subject's far side from the threat, aiming back down the same axis
            az = math.atan2((sub[0] + dx / L * REVEAL_BACK) - stage.look[0],
                            (sub[1] + dz / L * REVEAL_BACK) - stage.look[1])
            return az, dict(state or {'dir': 1}, az=az)
    if not state: return stage.az0, {'az': stage.az0, 'dir': 1}
    step = MIN_TURN + (MAX_TURN - MIN_TURN) * (.42 if intent in ('follow', 'flee', 'leave') else .19)
    d0 = (state['az'] - stage.az0 + math.pi) % (2 * math.pi) - math.pi
    dirn = state['dir']
    if abs(d0 + dirn * step) > MAX_TURN: dirn = -dirn            # the wall of the 180-degree rule: turn round
    az = stage.az0 + max(-MAX_TURN, min(MAX_TURN, d0 + dirn * step))
    return az, {'az': az, 'dir': dirn}


ASPECT_9x16 = 9 / 16.          # the format this studio ships; the lateral room a shot needs is h * this
SHRINK = ('establishing', 'wide', 'full', 'medium_full', 'medium')       # from the widest down
# the frame has to fit across the set AND the camera has to stand clear of the walls behind it. Measured on
# the hall of `dernier_bus` (a 3.6 m corridor, 4.6 m of lateral room): without the margin an establishing
# shot needing 4.22 m was accepted, `cinema.solve` scored it 0.53 and widened the lens to 75 deg; with it
# the shot comes down to `wide` and the same corridor is filmed at 68 deg with a clean score.
FIT_MARGIN = 1.25


def _fits(size, stage, aspect_k=ASPECT_9x16):
    """the widest shot of SHRINK, starting at `size`, whose frame fits across the stage. A shot the set
    cannot hold is not a style choice, it is a widened lens and a cropped skull -- so it is not asked for."""
    from ..acting.cinema import SIZES
    if size not in SHRINK: return size
    for k in range(SHRINK.index(size), len(SHRINK)):
        if SIZES[SHRINK[k]] * aspect_k * FIT_MARGIN <= stage.lateral: return SHRINK[k]
    return SHRINK[-1]


OTS_ROOM = 1.7          # m behind the listener an over-the-shoulder needs (cinema.solve tries 0.8 to 1.45)
PAIR_MARGIN = .9        # m of frame around the two bodies, so a two-shot is a shot and not a squeeze


def _standoff(vis, shot):
    """metres the camera must stand back from its subject for a frame `vis` metres tall, on this shot's lens.
    The same arithmetic `cinema.solve` does (`dist = (vis / 2) / tan(fov / 2)`), on the same LENS table."""
    from ..acting.cinema import LENS
    return (vis / 2) / math.tan(math.radians(LENS.get(shot, 52)) / 2)


def _pair_shot(stage, subjects, positions, size='medium_full'):
    """two people in one frame: `two_shot`, `ots` or a single `close` -- decided by the ROOM, not by taste.

    A two-shot films ACROSS the line between the two and so needs its standoff perpendicular to that line;
    an over-the-shoulder films ALONG the line and needs its room behind the listener. The two directions
    are not interchangeable in a corridor: there, across is a wall and along is fifteen metres.

    Measured cost of not asking this question, on `dernier_bus` shot 12 (two characters 2.5 m apart in a
    3.6 m corridor): `cinema.solve` was asked for a two-shot, found no position that saw both bodies, and
    returned its best effort -- score **0.05**, the lens widened to **80 deg** (the studio's own quality
    control calls that `lens_widened`), the camera **0.42 m** from the speaker's face and his head drawn at
    **436 % of the image width**. Nothing downstream could repair that, because by then the shot had
    already been promised. Asking first costs one ray-box intersection per beat."""
    from ..acting.cinema import SIZES
    ps = [positions.get(c) for c in subjects[:2]]
    if len(ps) < 2 or not all(ps): return 'close'
    mid = ((ps[0][0] + ps[1][0]) / 2, (ps[0][1] + ps[1][1]) / 2)
    dx, dz = ps[1][0] - ps[0][0], ps[1][1] - ps[0][1]
    L = math.hypot(dx, dz)
    if L < .25: return 'two_shot'                       # shoulder to shoulder: it is one subject, really
    ux, uz = dx / L, dz / L
    vis = max(SIZES.get(size, SIZES['medium_full']), (L + PAIR_MARGIN) / ASPECT_9x16)
    need = _standoff(vis, 'medium_full')
    across = max(stage.room(mid, (-uz, ux)), stage.room(mid, (uz, -ux)))
    if across >= need: return 'two_shot'
    behind = max(stage.room(ps[0], (-ux, -uz)), stage.room(ps[1], (ux, uz)))
    return 'ots' if behind >= OTS_ROOM else 'close'


def _camera(beat, rec, stage, subjects, drift, positions, keys=None):
    """the camera INTENTION of a beat: a size, a move, subjects, and -- for the wide family -- a side.

    No position, no target, no lens: those stay the cinematographer's job (acting/cinema.py), which is what
    keeps a shot asked for here honest -- if it cannot see its subject it is re-solved, not rendered wrong."""
    keys = keys or {}
    cam = {'shot': _fits(rec['size'], stage), 'on': list(subjects)}
    if rec.get('size2') and len(subjects) >= 2:
        cam['shot'] = _pair_shot(stage, subjects, positions, rec['size2'])
        if cam['shot'] == 'close': cam['on'] = [beat.get('who') or subjects[0]]
        else: cam['size'] = rec['size2']
    elif rec.get('size2'): cam['shot'] = rec['size2']          # one subject: a two-shot has no second body
    if cam['shot'] in ('dialogue', 'ots', 'two_shot'): cam['speaker'] = beat.get('who') or subjects[0]
    if rec.get('angle'): cam['angle'] = rec['angle']
    if rec['move'] != 'static':
        cam['move'] = rec['move']; cam['amount'] = round(float(beat.get('amount', rec['amount'])), 2)
    az = None; st2 = None
    if rec['wide']:
        az, st2 = _side_az(stage, drift, beat['intent'], beat, subjects, positions)
        cam['from'] = stage.point(az)
    # `head_room` is read by cinema.solve off the SHOT's camera dict (it has no episode-level reader in the
    # engine, unlike eyeline / footing / camera_face_track): the director writes it on each shot it owns.
    if keys.get('head_room') is not None: cam['head_room'] = keys['head_room']
    for k in ('size', 'height', 'roll', 'shake', 'fov', 'side', 'turn'):     # a beat may still insist
        if (beat.get('camera') or {}).get(k) is not None: cam[k] = beat['camera'][k]
    return cam, az, st2


def compile_narrative(nar, log=None):
    """a `narrative` block -> (episode dict, [storyboard rows]). The episode is a normal engine_version 2
    episode: it goes through director/validate.py and the production pipeline like any other."""
    log = log or (lambda *a: None)
    stages = {k: Stage(k, v) for k, v in (nar.get('stages') or {}).items()}
    if not stages: raise ValueError('scenario narratif sans "stages"')
    cast = nar.get('cast') or {}
    if not cast: raise ValueError('scenario narratif sans "cast"')
    beats = nar.get('beats') or []
    if not beats: raise ValueError('scenario narratif sans "beats"')
    opt, opt_name = options_of(nar)
    keys = opt['keys']

    ep = {'engine_version': 2,
          'cast': {k: {x: y for x, y in v.items() if x != 'role'} for k, v in cast.items()},
          'sets': {n: dict(s.set) for n, s in stages.items()},
          'default_set': beats[0].get('stage') or next(iter(stages)),
          'music': nar.get('music', 'mystery')}
    for k in ('hud', 'series', 'weather', 'weather_amount', 'summary'):
        if nar.get(k) is not None: ep[k] = nar[k]
    ep.update({k: v for k, v in keys.items() if k != 'head_room'})     # per-shot only, written in _camera
    ep['_directed'] = {'options': opt_name, 'keys': sorted(keys), 'camera': opt['camera'],
                       'light': opt['light'], 'intents': [b.get('intent') for b in beats]}

    shots = []; board = []; cur = None; prev_az = {}; positions = {}; placed = set()
    for i, beat in enumerate(beats):
        name = beat.get('stage') or cur or ep['default_set']
        if name not in stages: raise ValueError(f'beat {i} : plateau inconnu "{name}"')
        st = stages[name]; new_stage = name != cur; cur = name
        intent = beat.get('intent') or ('establish' if new_stage else 'interact')
        if intent not in INTENTS:
            raise ValueError(f'beat {i} : intention inconnue "{intent}" (connues : {", ".join(sorted(INTENTS))})')
        rec = INTENTS[intent]
        dur = float(beat.get('dur') or 2.8)
        s = {'lines': [i, i]}
        if name != ep['default_set'] or new_stage: s['set'] = name

        # who stands where: only when the scenario says so (first beat of a stage, or an explicit jump)
        place = dict(beat.get('place') or {})
        if new_stage and not place: place = {a: a for a in cast if a in st.marks}
        if place:
            actors = []
            for a, m in place.items():
                p = st.resolve(m)
                if not (isinstance(p, list) and len(p) == 2):
                    raise ValueError(f'beat {i} : repere inconnu "{m}" sur le plateau {name}')
                positions[a] = p
                fc = (beat.get('facing') or {}).get(a)
                actors.append({'id': a, 'at': p,
                               'facing': st.resolve(fc) if fc else [round(st.look[0], 2), round(st.look[1], 2)]})
            s['actors'] = actors; placed |= set(place)
        elif not placed:
            raise ValueError('le premier beat doit placer les acteurs ("place")')

        acts, movers = _actions(beat, st, dur, list(cast))
        if acts: s['actions'] = acts
        for a in acts:                      # remember where the business leaves people, for the next reveal
            if a['do'] in MOVERS and isinstance(a.get('to'), list): positions[a['who']] = a['to']

        subjects = _subjects(beat, rec, st, list(cast), movers)
        if rec.get('eyes') and beat.get('eyes') is not False:
            acts = _eyes(acts, subjects, dur)
            s['actions'] = acts
        cam, az, drift = _camera(beat, rec, st, subjects, prev_az.get(name), positions, keys)
        if drift is not None: prev_az[name] = drift
        # "legacy": the intention is computed (the storyboard still reports it) but NOT written. The engine
        # then covers the beat with cinema.auto_camera(), i.e. the plain conventions, which is the only
        # honest A side of an A/B: same story, same business, same lines, no direction.
        if opt['camera']:
            s['camera'] = cam
            if intent == 'reveal' and cam.get('from') and subjects:
                acts = _face_the_lens(acts, subjects[0], cam['from'], dur)
                s['actions'] = acts

        lt = beat.get('light', st.light if new_stage else None)
        if lt is not None and opt['light']: s['lighting'] = lt
        if beat.get('weather') is not None: s['weather'] = beat['weather']
        elif st.weather is not None: s['weather'] = st.weather
        if beat.get('weather_amount') is not None: s['weather_amount'] = beat['weather_amount']
        elif st.weather_amount is not None and s.get('weather') not in (None, 'none'):
            s['weather_amount'] = st.weather_amount
        for k in ('fx', 'sfx', 'world', 'state', 'objects', 'props'):
            if beat.get(k) is not None: s[k] = beat[k]
        shots.append(s)
        board.append({'i': i, 'stage': name, 'intent': intent, 'why': rec['why'], 'shot': cam['shot'],
                      'move': cam.get('move', 'static'), 'on': list(subjects), 'from': cam.get('from'),
                      'az_deg': None if az is None else round(math.degrees(az), 1), 'dur': dur,
                      'asked': bool(opt['camera']), 'text': beat.get('text', '')})
    ep['shots'] = shots
    base = nar.get('light') or (stages[ep['default_set']].light if ep['default_set'] in stages else None)
    if base is not None and opt['light']: ep['lighting'] = base
    sizes = sorted({b['shot'] for b in board})
    log(f'Realisateur narratif : {len(shots)} plans, {len(stages)} plateau(x), options "{opt_name}"'
        + (f' ({", ".join(sorted(keys))})' if keys else ' (aucune cle opt-in)')
        + (f' ; tailles demandees : {", ".join(sizes)}' if opt['camera']
           else ' ; AUCUNE camera ecrite (couverture automatique du moteur)'))
    return ep, board


# ---------------------------------------------------------------- the scenario file
def script_of(nar):
    """the `script` of the scenario, read off the beats: a beat IS a line (who says what, how long)"""
    out = []
    for b in nar.get('beats') or []:
        s = {'text': b.get('text', '')}
        if b.get('who'): s['who'] = b['who']
        if b.get('dur'): s['dur'] = float(b['dur'])
        if b.get('gap') is not None: s['gap'] = float(b['gap'])
        out.append(s)
    return out


def scenario(path_or_dict, options=None, log=None):
    """a narrative scenario file -> a scenario dict the production path already understands.

    `options` overrides the scenario's own `options` (that is what makes A/B one file, two runs)."""
    sc = (json.load(open(path_or_dict, encoding='utf-8')) if isinstance(path_or_dict, str)
          else json.loads(json.dumps(path_or_dict)))
    nar = sc.get('narrative')
    if nar is None: return sc                # an ordinary scenario: nothing to compile, nothing to change
    if options is not None: nar = dict(nar, options=options)
    ep, board = compile_narrative(nar, log)
    sc['episode'] = ep
    sc.setdefault('script', script_of(nar))
    sc.setdefault('style', nar.get('style', sc.get('style', 'pixel3d')))
    sc['storyboard'] = board
    return sc
