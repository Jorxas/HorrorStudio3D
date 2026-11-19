"""Who notices what, and how the face answers it: events of the story -> micro-reactions of the people who could perceive them.

The first engine gave a character a reaction table (`acting.timeline.REACTS`: startle, gasp, flinch, laugh...) that the SCRIPT triggered one by one. Here the
STORY says what happens in the world (a bang, a knock on the service door, the light going out, somebody appearing) and this module decides, for every character,
whether he perceived it and how: by ear (distance, walls and glass in between, a closed door), by eye (line of sight at head height, inside the field of view),
and with a human delay (0.18 s of reaction + the sound's travel time at 343 m/s). The output is a list of `react` beats (hstudio/voxelgpu/faceact.py plays them:
latency, attack, hold, decay, brow flash, startle blink, head turned to the cause), so a character who hears a bang a long way off, behind two walls, may only
look up, and one who is in the room jumps.

Interface (optional, independent of any other module): a beat may carry
    {'do': 'event', 't': 47.1, 'event_type': 'bang', 'source': 'porte_service' | [x, z] | 'ghost', 'loud': 1.0, 'witnesses': 'auto' | ['clerk'] | 'none'}
or any other beat may carry `event_type` (and `source`, `loud`) to make the action itself the event. `plan['react'] = 'auto'` additionally turns the plan's own
knocks / glass touches into events. Unknown event types are NOT replaced by something else: they are listed in `Compiled.warnings` (code `type_inconnu`) and play
only an orienting glance, so the story keeps what it asked for and the gap stays visible. `register_event_type(name, **spec)` adds one.
Nothing is random; no clock.
"""
import math

SPEED_OF_SOUND = 343.
LATENCY = .18                      # human reaction time to a sudden stimulus (s)
HEARING_FLOOR = .08                # audibility under which nobody turns his head
FOV = math.radians(105)            # half field of view for noticing a visual event without turning

# face: faceact preset name (director.EXPR_MAP names are accepted); i: peak intensity; startle: blink + inhale; look: head turns to the source; sound / visual: modality
EVENT_TYPES = {
    'bang':         dict(sound=1.0, face='scared', i=.9, attack=.07, hold=.55, decay=1.3, startle=True, look=True),
    'gunshot':      dict(sound=1.2, face='scared', i=1.0, attack=.06, hold=.7, decay=1.5, startle=True, look=True),
    'door_slam':    dict(sound=.9, face='surprised', i=.8, attack=.08, hold=.4, decay=1.0, startle=True, look=True),
    'scream':       dict(sound=1.1, face='scared', i=.95, attack=.1, hold=.9, decay=1.6, startle=True, look=True),
    'knock':        dict(sound=.55, face='worried', i=.7, attack=.12, hold=.6, decay=1.2, startle=True, look=True),
    'glass_touch':  dict(sound=.18, visual=True, face='worried', i=.5, attack=.14, hold=.5, decay=1.1, startle=False, look=True),
    'creak':        dict(sound=.3, face='worried', i=.45, attack=.15, hold=.5, decay=1.2, startle=False, look=True),
    'footsteps':    dict(sound=.2, face='worried', i=.3, attack=.2, hold=.4, decay=1.0, startle=False, look=True),
    'whisper':      dict(sound=.12, face='worried', i=.4, attack=.2, hold=.6, decay=1.2, startle=False, look=True),
    'voice':        dict(sound=.5, face='neutral', i=0., attack=.2, hold=.3, decay=.8, startle=False, look=True),
    'crash':        dict(sound=1.0, face='surprised', i=.85, attack=.07, hold=.5, decay=1.3, startle=True, look=True),
    'light_off':    dict(visual=True, face='worried', i=.55, attack=.15, hold=.8, decay=1.4, startle=False, look=False),
    'flash':        dict(visual=True, face='surprised', i=.7, attack=.06, hold=.3, decay=.9, startle=True, look=True),
    'appear':       dict(visual=True, face='scared', i=1.0, attack=.1, hold=1.0, decay=1.8, startle=True, look=True),
    'supernatural_appear': dict(visual=True, face='scared', i=1.0, attack=.1, hold=1.2, decay=2.0, startle=True, look=True),
    'supernatural_vanish': dict(visual=True, face='surprised', i=.85, attack=.1, hold=.9, decay=1.6, startle=False, look=True),
}
IMPLICIT = {'knock': 'knock', 'touch': 'glass_touch'}            # plan['react'] == 'auto': a plan's own actions that make a noise


def register_event_type(name, **spec):
    """an extension adds its own event type (registry, not if/elif -- see AGENTS.md)"""
    base = dict(sound=0., visual=False, face='worried', i=.5, attack=.12, hold=.5, decay=1.2, startle=False, look=True); base.update(spec); EVENT_TYPES[name] = base; return base


def _heading_estimate(A, t):
    m = A.moving(t)
    if m is not None: return m['path'].tangent(m['path'].dist(t)) + (math.pi if m['back'] else 0.)
    h = A.yaw0
    for (tt, f) in A.faces:
        if tt <= t and f[0] == 'yaw': h = f[1]
    for m in A.moves:
        if m.get('warp') or m['t1'] > t: continue
        if m['fin'] is not None and isinstance(m['fin'], (int, float)): h = float(m['fin'])
        else: h = m['path'].tangent(m['path'].D) + (math.pi if m['back'] else 0.)
    return h


def _solid_factor(s):
    """what a solid keeps of a sound: glass .7; a post or a pole (shorter than a metre in plan) .9; a wall (2.4 m high or more) .3; lower furniture or a car .85"""
    if s.kind == 'glass': return .7
    if max(s.x1 - s.x0, s.z1 - s.z0) < 1.: return .9
    return .3 if s.y1 - s.y0 >= 2.4 else .85


def occlusion(geo, a, b, t=None):
    """fraction of a sound that gets from a to b (2D) through the solids in between: a wall keeps .3, glass .7, a closed door .4 (one factor per solid met)"""
    n = max(2, int(math.hypot(b[0] - a[0], b[1] - a[1]) / .05)); met = {}; f = 1.
    for k in range(n + 1):
        x = a[0] + (b[0] - a[0]) * k / n; z = a[1] + (b[1] - a[1]) * k / n
        for s in geo.solids:
            if s.body and s.id not in met and s.contains(x, z): met[s.id] = _solid_factor(s)
        for p in geo.portals.values():
            if p.id not in met and (t is None or not p.open_at(t)) and p.rect[0] <= x <= p.rect[2] and p.rect[1] <= z <= p.rect[3]: met[p.id] = .4
    for v in met.values(): f *= v
    return f


def audibility(geo, src, listener, loud, t):
    d = math.hypot(src[0] - listener[0], src[1] - listener[1])
    return loud / (1. + d / 8.) * occlusion(geo, src, listener, t), d


def sees(geo, src, listener, heading, t):
    """line of sight from the listener's head (1.7 m) to the source (1.2 m), inside the field of view"""
    if geo.ray((listener[0], 1.7, listener[1]), (src[0], 1.2, src[1]), t=t) is not None: return False
    bear = math.atan2(src[0] - listener[0], src[1] - listener[1]); d = (bear - heading + math.pi) % (2 * math.pi) - math.pi
    return abs(d) <= FOV or math.hypot(src[0] - listener[0], src[1] - listener[1]) < .6


def source_of(geo, actors, spec, t, default=None):
    """a source: a mark, an actor id (where he is at t), [x, z] or [x, y, z]; None -> default"""
    if spec is None: return default
    if isinstance(spec, str):
        if spec in actors: return actors[spec].pos(t)
        if spec in geo.marks: return geo.marks[spec][:2]
        if spec in geo.items: a = geo.items[spec]['at']; return (a[0], a[2])
        b = geo.landmarks.get(spec)
        if b: return ((b[0] + b[3]) / 2, (b[2] + b[5]) / 2)
        raise ValueError(f"source d'événement inconnue : {spec!r}")
    if len(spec) == 3: return (float(spec[0]), float(spec[2]))
    return (float(spec[0]), float(spec[1]))


def collect(plan, beats, actors, geo, events):
    """-> list of (t, event_type, source xz, loud, who_made_it, witnesses spec) the story makes, from `event` beats, `event_type` keys and (react: auto) the plan's own actions"""
    out = []
    for b in beats:
        if b.get('do') in ('vanish', 'appear') and b.get('witnesses') != 'none':               # a declared supernatural event is always something the others can witness
            t = float(b['t']); et = b.get('event_type', 'supernatural_' + b['do'])
            src = source_of(geo, actors, b.get('at') if b['do'] == 'appear' and b.get('at') is not None else b.get('source'), t, actors[b['who']].pos(t))
            out.append((t, et, src, float(b.get('loud', 1.)), b['who'], b.get('witnesses', 'auto'))); continue
        et = b.get('event_type')
        if et is None and plan.get('react') == 'auto' and b.get('do') in IMPLICIT: et = IMPLICIT[b['do']]
        if not et or b.get('witnesses') == 'none': continue
        t = float(b['t']) + float(b.get('event_at', 0.)) if b.get('do') != 'knock' else float(b['hits'][0])
        if b.get('do') == 'knock':
            for h in b['hits']: out.append((float(h), et, source_of(geo, actors, b.get('source', b.get('target')), float(h)), float(b.get('loud', 1.)), b['who'], b.get('witnesses', 'auto')))
            continue
        src = source_of(geo, actors, b.get('source', b.get('target') if b.get('do') in ('touch', 'take') and isinstance(b.get('target'), str) else None), t, actors[b['who']].pos(t))
        out.append((t, et, src, float(b.get('loud', 1.)), b['who'], b.get('witnesses', 'auto')))
    return out


def derive(plan, beats, actors, geo, events, warnings=None):
    """-> extra `react` beats (and nothing else) for the plan; each carries `cause` = the event type and `look` = the source, so the face can turn to it"""
    extra = []; names = list(actors)
    for (t, et, src, loud, maker, wit) in collect(plan, beats, actors, geo, events):
        spec = EVENT_TYPES.get(et)
        if spec is None:
            if warnings is not None: warnings.append(('type_inconnu', f"type d'événement inconnu {et!r} à t={t:.2f}s : seul un regard d'orientation est joué (connus : {', '.join(sorted(EVENT_TYPES))})", t))
            spec = dict(sound=.4, face='neutral', i=0., attack=.2, hold=.3, decay=.8, startle=False, look=True)
        who = names if wit in ('auto', None) else [w for w in wit if w in actors]
        for aid in who:
            A = actors[aid]
            if aid == maker or A.kind == 'faceless' or A.spec.get('deaf') or not A.visible_at(t): continue
            p = A.pos(t); aud, d = audibility(geo, src, p, loud * spec.get('sound', 0.), t) if spec.get('sound') else (0., math.hypot(src[0] - p[0], src[1] - p[1]))
            seen = bool(spec.get('visual')) and sees(geo, src, p, _heading_estimate(A, t), t)
            noticed = aud >= HEARING_FLOOR or seen
            if not noticed: continue
            lat = LATENCY + (d / SPEED_OF_SOUND if aud >= HEARING_FLOOR and not seen else 0.)
            peak = spec['i'] * min(1., .35 + .9 * min(1., aud * 1.6 if not seen else 1.))
            b = dict(who=aid, t=t, do='react', face=spec['face'], i=round(peak, 3), attack=spec['attack'], hold=spec['hold'], decay=spec['decay'], latency=round(lat, 4),
                     cause=et, startle=bool(spec.get('startle')), audibility=round(aud, 3), seen=seen)
            if spec.get('look') and math.hypot(src[0] - p[0], src[1] - p[1]) > .3: b['look'] = [round(src[0], 3), round(src[1], 3)]
            extra.append(b)
    return extra
