"""Quality control of an episode, shared by both engines: measurable checks before (or after) a render.

  python -m hstudio qc <project> [--aspect 9:16]          -> projects/<slug>/qc_<aspect>.json + a summary in French

What is measured (each check has a value, a target and ok / not ok):
  speaker_visible   share of the speaking time where the speaker is in frame and not hidden, when the camera is on him
  faces_readable    share of the close / medium samples where the subject's face is turned towards the camera (a
                    cubic head filmed from the side or the back shows a blank slab instead of a face)
  (reported only)   a head taking more than HEAD_WIDE of the image width: the frame is too tight, typically in 9:16
  subjects_framed   share of the samples where every subject of the camera is in frame and visible
  collisions        samples where a standing character is inside a piece of furniture
  overlaps          samples where two standing characters are closer than 0.35 m
  camera_blocked    shots whose camera could not find a free, unobstructed position (solver score < 0.6)
  lens_widened      shots where the lens had to be widened beyond 79 degrees (camera backed into a wall)
  subtitle_speed    lines read faster than 17 characters per second
  continuity        characters that jump between two shots of the same set without an action (sets are compared by
                    name: both engines build a fresh World object per shot)
  head_snap         frames where a gaze turns more than 25 degrees in 1/30 s (a head cannot, the eye catches it).
                    Informational: it is measured and shown but does not move the score, so the scores recorded for
                    the existing episodes stay exactly what they were. See acting/gaze.py ("eyeline": "smooth", which
                    brings it to zero) and tools/motion_qc.py, which also measures the foot slide
  exposure          shots that are almost black or burnt (one low-resolution frame per shot)

The engine supplies observations through engine.qc_observe(t) (camera, people on screen) and the acting layer
(engine.ctx.get_acting() or engine.acting); nothing here depends on how the images are drawn."""
import math, json, os

TARGETS = {'speaker_visible': .85, 'subjects_framed': .9, 'faces_readable': .9}
# beyond this angle (degrees) between the face axis and the camera, a blocky head no longer reads as a face
FACE_CONE_DEG = {'extreme_close': 50., 'close': 60., 'medium': 68., 'medium_full': 75., 'ots': 60.}
HEAD_WIDE = .85      # a head wider than this share of the image is a frame nobody would cut (reported, not scored)
CPS_MAX = 17.
SNAP_DEG = 25.; SNAP_FPS = 30.; HEAD_LIMIT = .95
ANIMALS = {'dog', 'cat', 'bird', 'horse', 'cow', 'rabbit', 'chicken', 'pig', 'sheep', 'duck', 'spider', 'ghost'}

def _wrap(a): return (a + math.pi) % (2 * math.pi) - math.pi

def _acting(engine):
    if hasattr(engine, 'ctx') and hasattr(engine.ctx, 'get_acting'): return engine.ctx.get_acting()
    return getattr(engine, 'acting', None)

def _shot_of(spans, t):
    for k, (a, b) in enumerate(spans):
        if a <= t < b: return k
    return len(spans) - 1

def run(engine, ep, lines, every=.25, frames=True, log=None):
    """returns the QC report (dict); every: sampling step in seconds; frames: also check the exposure"""
    spans = engine.ctx.tl.spans if hasattr(engine, 'ctx') else engine.tl.spans
    ac = _acting(engine); issues = []
    def issue(level, code, msg, t=None, shot=None): issues.append({'level': level, 'code': code, 'message': msg, 't': None if t is None else round(t, 2), 'shot': shot})
    cast = ep.get('cast') or {}
    is_animal = lambda a: (cast.get(a) or {}).get('kind') in ANIMALS if isinstance(cast.get(a), dict) else False
    # ---------------------------------------------------------------- what the camera shows (engine observations)
    spk_n = spk_ok = fr_n = fr_ok = fc_n = fc_ok = 0; shot_cam = {}; per = {}; face_worst = {}; tight = {}
    t = 0.; end = spans[-1][1] if spans else 0.
    while t < end and hasattr(engine, 'qc_observe'):
        ob = engine.qc_observe(t)
        if ob:
            k = ob['shot']
            if ob.get('cam'): shot_cam.setdefault(k, ob['cam'])
            subj = [a for a in ob.get('subjects', []) if a in ob['people']]
            if subj:
                fr_n += 1; bad = [a for a in subj if not (ob['people'][a]['in_frame'] and ob['people'][a]['visible'])]
                if not bad: fr_ok += 1
            lim = FACE_CONE_DEG.get(((ob.get('cam') or {}).get('shot')) or '')
            for a in subj:                             # per shot and per character: how long in frame / hidden
                p = ob['people'][a]; c = per.setdefault((k, a), dict(n=0, out=0, hid=0, talk=0, talk_ok=0, t=t))
                if p.get('head_share') and p['head_share'] > tight.get(k, (0., None, None))[0]: tight[k] = (p['head_share'], a, t)
                if lim is not None and p.get('face_angle') is not None and p['in_frame']:
                    fc_n += 1
                    if p['face_angle'] <= lim: fc_ok += 1
                    elif p['face_angle'] > face_worst.get(k, (0., None, None))[0]: face_worst[k] = (p['face_angle'], a, t)
                c['n'] += 1; c['out'] += not p['in_frame']; c['hid'] += p['in_frame'] and not p['visible']
                if p.get('talking'):
                    spk_n += 1; c['talk'] += 1
                    if p['in_frame'] and p['visible']: spk_ok += 1; c['talk_ok'] += 1
        t += every
    for (k, a), c in sorted(per.items()):
        bad = (c['out'] + c['hid']) / c['n']
        if bad > .25:
            issue('warning' if bad > .5 else 'info', 'subject_hidden', f"plan {k} : {a} {'hors cadre' if c['out'] >= c['hid'] else 'masqué'} {100 * bad:.0f} % du plan", c['t'], k)
        if c['talk'] and c['talk_ok'] / c['talk'] < .6:
            issue('warning', 'speaker_offscreen', f"plan {k} : {a} parle mais n'est visible que {100 * c['talk_ok'] / c['talk']:.0f} % du temps", c['t'], k)
    for k, (hs_, a, t_) in sorted(tight.items()):
        if hs_ > HEAD_WIDE:
            issue('warning', 'framing_tight', f"plan {k} : la tête de {a} occupe {100 * hs_:.0f} % de la largeur de l'image (cadre trop serré)", t_, k)
    for k, (ang, a, t_) in sorted(face_worst.items()):
        issue('warning' if ang > 100 else 'info', 'face_hidden',
              f"plan {k} : le visage de {a} est tourné à {ang:.0f}° de la caméra (on voit le côté uni de la tête)", t_, k)
    checks = {}
    if fc_n: checks['faces_readable'] = {'value': round(fc_ok / fc_n, 3), 'target': TARGETS['faces_readable'], 'ok': fc_ok / fc_n >= TARGETS['faces_readable']}
    if spk_n: checks['speaker_visible'] = {'value': round(spk_ok / spk_n, 3), 'target': TARGETS['speaker_visible'], 'ok': spk_ok / spk_n >= TARGETS['speaker_visible']}
    if fr_n: checks['subjects_framed'] = {'value': round(fr_ok / fr_n, 3), 'target': TARGETS['subjects_framed'], 'ok': fr_ok / fr_n >= TARGETS['subjects_framed']}
    blocked = [k for k, c in shot_cam.items() if c.get('score') is not None and c['score'] < .6]
    wide = [k for k, c in shot_cam.items() if c.get('fov', 0) >= 79]
    for k in blocked: issue('warning', 'camera_blocked', f"plan {k} : caméra contrainte (score {shot_cam[k]['score']:.2f}), le décor gêne le cadrage", shot=k)
    for k in wide: issue('info', 'lens_widened', f"plan {k} : objectif élargi à {shot_cam[k]['fov']:.0f}° (pièce trop petite pour reculer)", shot=k)
    if shot_cam:
        checks['camera_blocked'] = {'value': len(blocked), 'target': 0, 'ok': not blocked}
        checks['lens_widened'] = {'value': len(wide), 'target': 0, 'ok': not wide}
    # ---------------------------------------------------------------- bodies in the set (acting layer only)
    if ac is not None and ac.shots:
        col = ovl = 0; seen = set()
        for k, sa in sorted(ac.shots.items()):
            obs = list(sa.world.obstacles() or [])
            for i in range(int(sa.dur / .2) + 1):
                tt = min(sa.dur, i * .2); sm = sa.sample(tt)
                stand = {a: s for a, s in sm.items() if s.get('visible', 1) and s['rig'].get('sit', 0.) < .05 and not is_animal(a)}
                for a, s in stand.items():
                    tr = sa.tracks.get(a)                # sliding onto a seat (legs under the table) is not a collision
                    if tr is not None and any(s0 - 1.2 <= tt <= s0 + 1. for (s0, _d, _a, b) in tr.sits if b > .5): continue
                    hit = next((o for o in obs if o[0] + .06 < s['x'] < o[2] - .06 and o[1] + .06 < s['z'] < o[3] - .06), None)
                    if hit:
                        col += 1
                        if (k, a, 'col') not in seen: seen.add((k, a, 'col')); issue('warning', 'collision', f"plan {k} : {a} traverse un meuble", spans[k][0] + tt, k)
                ids = list(stand)
                for x in range(len(ids)):
                    for y in range(x + 1, len(ids)):
                        a, b = stand[ids[x]], stand[ids[y]]
                        if math.hypot(a['x'] - b['x'], a['z'] - b['z']) < .35:
                            ovl += 1
                            if (k, 'ovl') not in seen: seen.add((k, 'ovl')); issue('warning', 'overlap', f"plan {k} : {ids[x]} et {ids[y]} se chevauchent", spans[k][0] + tt, k)
        checks['collisions'] = {'value': col, 'target': 0, 'ok': col == 0}
        checks['overlaps'] = {'value': ovl, 'target': 0, 'ok': ovl == 0}
        # continuity: positions at the cut between two acted shots of the same set
        jumps = 0; ks = sorted(ac.shots)
        for k0, k1 in zip(ks, ks[1:]):
            if k1 != k0 + 1: continue
            s0, s1 = ac.shots[k0], ac.shots[k1]
            sets = getattr(ac, 'set_of', None)            # engines rebuild a World per shot, so compare the set names
            if sets is not None:
                if sets.get(k0) != sets.get(k1): continue
            elif s0.world is not s1.world and getattr(s0.world, 'name', 0) != getattr(s1.world, 'name', 1): continue
            a_ = s0.sample(s0.dur); b_ = s1.sample(0.)
            placed = {x.get('id') for x in (ep['shots'][k1].get('actors') or []) if x.get('at') or x.get('on')}
            for aid in set(a_) & set(b_):
                d = math.hypot(a_[aid]['x'] - b_[aid]['x'], a_[aid]['z'] - b_[aid]['z'])
                if d > .3 and aid not in placed:
                    jumps += 1; issue('warning', 'continuity', f"plans {k0}->{k1} : {aid} saute de {d:.1f} m entre les plans", spans[k1][0], k1)
        checks['continuity'] = {'value': jumps, 'target': 0, 'ok': jumps == 0}
        # the gaze: how far a head turns in the world between two frames (the acting layer alone, no image needed)
        snaps = 0; worst = 0.; seen_s = set(); dt = 1. / SNAP_FPS
        for k, sa in sorted(ac.shots.items()):
            prev = {}
            for i in range(int(sa.dur / dt) + 1):
                tt = min(sa.dur, i * dt)
                for aid, (yaw, _pitch, hd) in sa.raw_heads(tt).items():
                    if is_animal(aid): continue
                    if sa.gaze is not None: yaw = sa.gaze.head(aid, tt, hd, yaw, _pitch)[0]
                    g = hd + max(-HEAD_LIMIT, min(HEAD_LIMIT, yaw))            # as the engines draw it
                    if aid in prev:
                        d = abs(math.degrees(_wrap(g - prev[aid]))); worst = max(worst, d)
                        if d > SNAP_DEG:
                            snaps += 1
                            if (k, aid) not in seen_s:
                                seen_s.add((k, aid))
                                issue('info', 'head_snap', f"plan {k} : le regard de {aid} saute de {d:.0f}° en une image "
                                      f"(tête figée puis téléportée ; \"gaze\": \"smooth\" lisse la régie du regard)", spans[k][0] + tt, k)
                    prev[aid] = g
        checks['head_snap'] = {'value': snaps, 'target': 0, 'ok': snaps == 0, 'worst_deg': round(worst, 1), 'info': True}
    # ---------------------------------------------------------------- subtitles
    fast = []
    for i, ln in enumerate(lines):
        txt = (ln.get('display') or ln.get('text') or '').strip(); d = max(.1, float(ln.get('end', 0)) - float(ln.get('start', 0)))
        if txt and len(txt) / d > CPS_MAX: fast.append(i); issue('info', 'subtitle_speed', f"ligne {i} : {len(txt) / d:.0f} caractères/s (lecture difficile au-delà de {CPS_MAX:.0f})", ln.get('start'))
    checks['subtitle_speed'] = {'value': len(fast), 'target': 0, 'ok': not fast}
    # ---------------------------------------------------------------- exposure (one small frame per shot)
    if frames and hasattr(engine, 'qc_image'):
        dark = []; burnt = []
        for k, (a, b) in enumerate(spans):
            im = engine.qc_image((a + b) / 2)
            if im is None: continue
            lum = (im[..., 0] * .3 + im[..., 1] * .59 + im[..., 2] * .11) / 255.
            if lum.mean() < .035: dark.append(k); issue('info', 'dark', f"plan {k} : image presque noire (luminance {lum.mean():.3f})", (a + b) / 2, k)
            if (lum > .97).mean() > .12: burnt.append(k); issue('warning', 'burnt', f"plan {k} : {100 * (lum > .97).mean():.0f} % de l'image brûlée", (a + b) / 2, k)
        checks['exposure'] = {'value': {'dark': dark, 'burnt': burnt}, 'target': 'aucun plan brûlé', 'ok': not burnt}
    # ---------------------------------------------------------------- score
    pen = 0.
    for name, c in checks.items():
        if c['ok'] or c.get('info'): continue        # an informational check is measured and shown, never scored
        if name in ('speaker_visible', 'subjects_framed'): pen += 40 * max(0., c['target'] - c['value'])
        elif name == 'faces_readable': pen += 20 * max(0., c['target'] - c['value'])
        elif name in ('collisions', 'overlaps'): pen += min(15, 2 + c['value'] * .5)
        elif name == 'exposure': pen += 5 * len(c['value']['burnt'])
        else: pen += 4 * (c['value'] if isinstance(c['value'], int) else 1)
    rep = {'version': 1, 'duration': round(end, 2), 'shots': len(spans), 'score': max(0, round(100 - pen)), 'checks': checks,
           'issues': sorted(issues, key=lambda i: (i['t'] if i['t'] is not None else -1))}
    if log: log(summary(rep))
    return rep

def summary(rep):
    names = {'speaker_visible': 'personnage qui parle visible', 'faces_readable': 'visages lisibles (gros plans)', 'subjects_framed': 'sujets dans le cadre', 'collisions': 'collisions avec le décor',
             'overlaps': 'personnages superposés', 'camera_blocked': 'caméras contraintes', 'lens_widened': 'objectif élargi',
             'subtitle_speed': 'sous-titres trop rapides', 'continuity': 'sauts de continuité', 'exposure': 'exposition',
             'head_snap': 'sauts de regard'}
    out = [f"Contrôle qualité : {rep['score']}/100 ({rep['shots']} plans, {rep['duration']:.1f} s)"]
    for k, c in rep['checks'].items():
        v = c['value']
        if isinstance(v, float): v = f'{100 * v:.0f} % (objectif {100 * c["target"]:.0f} %)'
        elif isinstance(v, dict): v = f"{len(v['burnt'])} plan(s) brûlé(s), {len(v['dark'])} très sombre(s)"
        if k == 'head_snap' and not c['ok']: v = f"{v} image(s), pire {c.get('worst_deg', 0):.0f}° (hors note ; \"eyeline\": \"smooth\" les lisse)"
        out.append(f"  {'OK ' if c['ok'] else ('-- ' if c.get('info') else '!! ')} {names.get(k, k)} : {v}")
    warn = [i for i in rep['issues'] if i['level'] == 'warning']
    for i in warn[:8]: out.append('  - ' + i['message'])
    if len(warn) > 8: out.append(f'  ... et {len(warn) - 8} autre(s) (voir qc.json)')
    return '\n'.join(out)

def save(rep, path):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    json.dump(rep, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return path
