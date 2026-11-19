"""Measures directed locomotion on a scene or a demo scenario, with and without the "approach" option.

  python tools/locomotion_qc.py tests/scenes/approche_lea_tom.json
  python tools/locomotion_qc.py --demos                       # the ten demo scenarios
  python tools/locomotion_qc.py <scene> --json docs/mesures/locomotion_mesures.json

Nothing is rendered: only the acting layer is built and sampled, so this costs no API call and a few seconds.
Everything is read from the production code path (hstudio.pipeline.make_engine -> the real Acting), never from a
re-implementation of the walk.

What is measured, per character and per shot, at 30 i/s:

heading error    angle between the body heading and the direction the body actually travels, only while it moves
                 faster than .15 m/s. This is the defect the owner saw: a body that walks sideways.
foot slide       how far the stance foot (the lower of the two) moves in the world between two frames while the
                 walk cycle runs. The gait is driven by distance, so a planted foot should not move at all; what
                 is left is the skating. Reported twice: over the whole walk, and while actually translating
                 (turning on the spot does move the feet, on purpose, and that is not skating).
arrival          distance to the actor walked up to at the end of the shot, and the closest the two bodies ever
                 came (under .52 m two bodies interpenetrate).
final facing     how far off the body is from the person it walked up to, at the end.
reaction         time from the start of a walk until the body is within 10 deg of the direction it travels.
anticipation     the order in which the chain starts moving: head, then body heading, then the feet.
"""
import os, sys, json, math, argparse
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from hstudio.acting import rig                                    # noqa: E402
from hstudio.acting.timeline import wrap                          # noqa: E402

FPS = 30.
MOVING = .15          # m/s, below this the direction travelled is noise
BODY = .52            # m, two bodies closer than this interpenetrate


def scene_lines(ep):
    """same convention as tools/scene_sheet.py: one silent line per shot, "dur" seconds each"""
    out = []; t = 0.
    for i, s in enumerate(ep['shots']):
        d = float(s.get('dur', 4.)); txt = s.get('text', '')
        out.append({'tts': txt or '.', 'display': txt, 'text': txt, 'tags': [], 'dialogue': bool(s.get('speaker')),
                    'i': i, 'start': t + .05, 'end': t + d - .05, 'segs': [[t + .05, t + d - .05]]})
        if s.get('speaker'): ep.setdefault('lines', {})[str(i)] = dict(ep.get('lines', {}).get(str(i), {}), speaker=s['speaker'])
        t += d
    return out


def read_scene(path):
    ep = json.load(open(path, encoding='utf-8'))
    if 'script' in ep and 'episode' in ep:
        from hstudio.demos import timed_lines, state_after
        sc = ep; ep = sc['episode']; ep['style'] = sc.get('style', 'pixel3d')
        lines = timed_lines(sc['script'], float(sc.get('gap', .3)), float(sc.get('lead', .4)))
        if ep.get('series'): ep['series_state'] = state_after(sc['follows']) if sc.get('follows') else {}
        for i, s in enumerate(sc['script']):
            if s.get('who'): ep.setdefault('lines', {}).setdefault(str(i), {})['speaker'] = s['who']
        return ep, lines
    return ep, scene_lines(ep)


def feet_world(v, sk):
    """the two feet of a sampled character in world coordinates: (x, z, height above the floor)"""
    h = v['heading']; c, s = math.cos(h), math.sin(h); out = {}
    for tag in ('R', 'L'):
        f = sk.frames['foot' + tag][1]
        out[tag] = (v['x'] + float(f[0]) * c + float(f[2]) * s, v['z'] - float(f[0]) * s + float(f[2]) * c, float(f[1]))
    return out


def walk_targets(shot, tracks):
    """{who: target id} for every walk_to aimed at another character of the shot"""
    out = {}
    for a in (shot.get('actions') or []):
        if a.get('do') in ('walk_to', 'run_to', 'sneak_to', 'go') and isinstance(a.get('to'), str) and a['to'] in tracks:
            out[a.get('who', 'hero')] = a['to']
    return out


def measure(ep, lines, directed, style='pixel3d'):
    """build the episode through the production path and sample every shot"""
    import copy
    ep = copy.deepcopy(ep)
    if directed: ep['approach'] = 'directed'
    else: ep.pop('approach', None)
    from hstudio.pipeline import make_engine, duration_of
    dur = duration_of(ep, lines)
    eng = make_engine(style, ep, lines, np.zeros(10), dur, '16:9')
    ac = eng.ctx.get_acting() if hasattr(eng, 'ctx') else getattr(eng, 'acting', None)
    cast = ep.get('cast') or {}
    is_animal = lambda a: bool((cast.get(a) or {}).get('kind')) if isinstance(cast.get(a), dict) else False

    errs = []; slides = []; slides_mv = []; reactions = []; faces = []; arrivals = []
    closest = []; chain = []
    for k, sa in sorted(ac.shots.items()):
        tgts = walk_targets(ep['shots'][k], sa.tracks)
        ts = np.arange(0, sa.dur, 1. / FPS)
        hist = {}
        for t in ts:
            sm = sa.sample(float(t))
            for aid, v in sm.items():
                if is_animal(aid): continue
                sk = rig.solve(v['rig'])
                yaw = v['rig'].get('head', (0., 0.))[0]
                hist.setdefault(aid, []).append(dict(t=float(t), x=v['x'], z=v['z'], h=v['heading'],
                                                     gait=v['rig'].get('gait', 0.), feet=feet_world(v, sk),
                                                     gaze=v['heading'] + yaw))
            ids = [a for a in sm if not is_animal(a)]
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    a, b = sm[ids[i]], sm[ids[j]]
                    closest.append(math.hypot(a['x'] - b['x'], a['z'] - b['z']))
        for aid, H in hist.items():
            for i in range(1, len(H)):
                r, p = H[i], H[i - 1]
                dx, dz = r['x'] - p['x'], r['z'] - p['z']; sp = math.hypot(dx, dz) * FPS
                mv = sp > MOVING
                if mv: errs.append(abs(math.degrees(wrap(r['h'] - math.atan2(dx, dz)))))
                tag = 'R' if p['feet']['R'][2] <= p['feet']['L'][2] else 'L'
                sl = math.hypot(r['feet'][tag][0] - p['feet'][tag][0], r['feet'][tag][1] - p['feet'][tag][1]) * 100
                if r['gait'] > .5:
                    slides.append(sl)
                    if mv: slides_mv.append(sl)
            # reaction time and the order the chain starts, on the first walk of the shot
            tr = sa.tracks[aid]
            if tr.paths:
                t_start = min(min(p.t0 for p in tr.paths), min([x[0] for x in tr.turns], default=1e9))
                react = None; first = {}
                h0 = H[0]['h']; g0 = H[0]['gaze']
                for i in range(1, len(H)):
                    r, p = H[i], H[i - 1]
                    if r['t'] < t_start: h0 = r['h']; g0 = r['gaze']; continue
                    if 'gaze' not in first and abs(math.degrees(wrap(r['gaze'] - g0))) > 3: first['gaze'] = r['t']
                    if 'body' not in first and abs(math.degrees(wrap(r['h'] - h0))) > 3: first['body'] = r['t']
                    dx, dz = r['x'] - p['x'], r['z'] - p['z']
                    if math.hypot(dx, dz) * FPS > MOVING:
                        first.setdefault('move', r['t'])
                        if react is None and abs(math.degrees(wrap(r['h'] - math.atan2(dx, dz)))) < 10: react = r['t'] - t_start
                if react is not None: reactions.append(react)
                if len(first) == 3:
                    chain.append((first['body'] - first['gaze'], first['move'] - first['body']))
            # how the approach ended
            if aid in tgts:
                o = hist.get(tgts[aid])
                if o:
                    a_, b_ = H[-1], o[-1]
                    arrivals.append(math.hypot(a_['x'] - b_['x'], a_['z'] - b_['z']))
                    faces.append(abs(math.degrees(wrap(a_['h'] - math.atan2(b_['x'] - a_['x'], b_['z'] - a_['z'])))))
    pc = lambda v, q: (float(np.percentile(v, q)) if v else None)
    mx = lambda v: (float(max(v)) if v else None)
    return dict(
        frames=len(errs),
        err_max=mx(errs), err_p95=pc(errs, 95), err_mean=(float(np.mean(errs)) if errs else None),
        err_over_25=int(sum(1 for e in errs if e > 25)),
        slide_max=mx(slides), slide_p95=pc(slides, 95),
        slide_mv_max=mx(slides_mv), slide_mv_p95=pc(slides_mv, 95),
        reaction_max=mx(reactions), reaction_mean=(float(np.mean(reactions)) if reactions else None),
        arrive=[round(a, 3) for a in arrivals], face_err_max=mx(faces),
        closest=(float(min(closest)) if closest else None),
        overlaps=int(sum(1 for d in closest if d < BODY)),
        gaze_lead=(float(np.mean([c[0] for c in chain])) if chain else None),
        turn_lead=(float(np.mean([c[1] for c in chain])) if chain else None),
        chain=[tuple(round(x, 3) for x in c) for c in chain])


def show(tag, m):
    f = lambda v, n=2: ('-' if v is None else f'{v:.{n}f}')
    print(f'  {tag:<12} cap/deplacement  max {f(m["err_max"],1):>7} deg  p95 {f(m["err_p95"],1):>7}  moyenne {f(m["err_mean"],1):>6}'
          f'  images > 25 deg : {m["err_over_25"]}/{m["frames"]}')
    print(f'  {"":<12} glissement pied  max {f(m["slide_max"]):>7} cm/i  p95 {f(m["slide_p95"]):>7}'
          f'   | en translation  max {f(m["slide_mv_max"]):>6}  p95 {f(m["slide_mv_p95"]):>6}')
    print(f'  {"":<12} arrivee {m["arrive"]} m  cap final a {f(m["face_err_max"],1)} deg de la cible'
          f'  |  plus proche {f(m["closest"])} m  chevauchements {m["overlaps"]}')
    print(f'  {"":<12} reaction  max {f(m["reaction_max"])} s  moyenne {f(m["reaction_mean"])} s'
          f'  |  anticipation : regard avant corps {f(m["gaze_lead"],3)} s, corps avant deplacement {f(m["turn_lead"],3)} s')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('scene', nargs='?', default=os.path.join('tests', 'scenes', 'approche_lea_tom.json'))
    ap.add_argument('--demos', action='store_true', help='the ten demo scenarios instead of one scene')
    ap.add_argument('--json', default=None)
    a = ap.parse_args()
    out = {}
    targets = []
    if a.demos:
        from hstudio.demos import list_demos, DEMO_DIR
        targets = [(d['id'], os.path.join(DEMO_DIR, d['id'] + '.json')) for d in list_demos()]
    else:
        targets = [(os.path.splitext(os.path.basename(a.scene))[0], a.scene)]
    for name, path in targets:
        ep, lines = read_scene(path)
        print(f'{name}')
        res = {}
        for tag, directed in (('historique', False), ('approach', True)):
            res[tag] = measure(ep, lines, directed, ep.get('style', 'pixel3d'))
            show(tag, res[tag])
        out[name] = res
    if a.json:
        os.makedirs(os.path.dirname(a.json), exist_ok=True)
        json.dump(out, open(a.json, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
        print('->', a.json)


if __name__ == '__main__':
    main()
