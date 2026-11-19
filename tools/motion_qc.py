"""Measurements of the acting layer on real episodes: head snaps and foot slide. Nothing is rendered.

  python tools/motion_qc.py                          # the ten demo scenarios
  python tools/motion_qc.py demo6_continuite demo9_tempete
  python tools/motion_qc.py --eyeline smooth         # same episodes with the gaze controller on (opt-in)
  python tools/motion_qc.py --json out.json          # also write every measurement
  python tools/motion_qc.py --bench                  # CPU cost of the régie with and without the two options

Two numbers, both in units a director can argue about:

  head_snap  degrees the gaze of a character turns from one 30 fps frame to the next, in the world (heading + head
             yaw). A real head turns at 200-300 deg/s, i.e. 7-10 deg per frame; anything above ~25 deg in one frame
             is a teleport the eye catches, whether it happens inside a shot (the head jumps to a new speaker) or
             across a cut (the next shot was framed for a gaze the body did not have yet).
  foot_slide centimetres the stance foot travels in the world while the gait says it is planted. The gait is
             distance-driven, so on a straight walk this is IK noise (~0.2 cm); it grows when the body rotates
             under a planted foot (a path corner) or when something moves the body outside the gait.

Both engines use the same acting layer, so these numbers cover pixel3d and console alike."""
import os, sys, json, math, argparse
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from hstudio.acting import rig
from hstudio.acting.timeline import wrap
from hstudio.acting.qc import ANIMALS

DEMOS = ['demo1_mouvement', 'demo2_dialogue', 'demo3_groupe', 'demo4_tension', 'demo5_console',
         'demo6_continuite', 'demo7_toits', 'demo8_ravin', 'demo9_tempete', 'demo10_console_saut']
FPS = 30.
SNAP_DEG = 25.                     # one-frame gaze change the eye reads as a teleport


def acting_of(demo_id, aspect='16:9', episode_patch=None):
    """(acting, episode, spans) of a demo scenario, built exactly as `python -m hstudio demo` builds it"""
    from hstudio import demos
    from hstudio.pipeline import make_engine, duration_of
    from hstudio.acting.qc import _acting
    sc = demos.load(demo_id)
    lines = demos.timed_lines(sc['script'], float(sc.get('gap', .3)), float(sc.get('lead', .4)))
    env = demos.draft_voice(sc, lines)[1]
    ep = demos.episode_of(sc, lines, log=lambda *a: None)
    if episode_patch: ep = episode_patch(ep)
    eng = make_engine(sc.get('style', 'pixel3d'), ep, lines, env, duration_of(ep, lines), aspect)
    ac = _acting(eng)
    spans = eng.ctx.tl.spans if hasattr(eng, 'ctx') else eng.tl.spans
    return ac, ep, spans


def ankle_world(s):
    """{side: (x, y, z)} of the two ankles in world coordinates, from one sample of the acting layer"""
    sk = rig.solve(s['rig'])
    R = rig.rot_y(s['heading']); base = np.array([s['x'], float(s.get('y', 0.)), s['z']], np.float32)
    out = {}
    for tag in ('L', 'R'):
        p = base + R @ sk.joints['an' + tag]
        out[tag] = (float(p[0]), float(p[1]), float(p[2]))
    return out


def in_stance(r, tag):
    """is this foot planted at this frame, according to the gait cycle itself (not from its height)"""
    if r.get('gait', 0.) < .5 or r.get('air', 0.) > .05 or r.get('sit', 0.) > .1: return False
    psi = r['phase'] + (0. if tag == 'R' else math.pi)
    return (psi / (2 * math.pi)) % 1. < rig.stance_beta(r.get('run', 0.))


def measure_demo(demo_id, aspect='16:9', episode_patch=None, fps=FPS):
    """(head snaps, foot slides) of one demo, sampled at fps over the whole episode"""
    return measure(*acting_of(demo_id, aspect, episode_patch), label=demo_id, fps=fps)


def measure(ac, ep, spans, label='', fps=FPS):
    """(head snaps, foot slides) of an already built Acting, sampled at fps over the whole episode"""
    demo_id = label
    cast = ep.get('cast') or {}                            # animals are not drawn on the human skeleton (qc.py)
    beasts = {a for a, c in cast.items() if isinstance(c, dict) and c.get('kind') in ANIMALS}
    dt = 1. / fps
    def shot_at(t):
        for i, (a, b) in enumerate(spans):
            if a <= t < b: return i
        return len(spans) - 1
    snaps = []; slides = []
    prev = {}                                              # id -> (shot, world gaze, yaw, {tag: ankle}, heading)
    t = 0.; end = spans[-1][1] if spans else 0.
    while t < end:
        k = shot_at(t); sa = ac.shots.get(k)
        if sa is None: prev.clear(); t += dt; continue
        sm = sa.sample(min(sa.dur, max(0., t - spans[k][0])))
        for aid, s in sm.items():
            if aid in beasts: continue
            if not s.get('visible', 1): prev.pop(aid, None); continue
            yaw, pitch = s['rig']['head']; g = s['heading'] + yaw
            ank = ankle_world(s); p = prev.get(aid)
            if p is not None:
                snaps.append({'demo': demo_id, 'who': aid, 't': round(t, 3), 'shot': k, 'cut': p[0] != k,
                              'deg': abs(math.degrees(wrap(g - p[1]))), 'yaw': math.degrees(yaw),
                              'yaw_prev': math.degrees(p[2])})
                for tag in ('L', 'R'):
                    if in_stance(s['rig'], tag) and p[3].get(tag) is not None and p[0] == k:
                        d = math.hypot(ank[tag][0] - p[3][tag][0], ank[tag][2] - p[3][tag][2])
                        slides.append({'demo': demo_id, 'who': aid, 't': round(t, 3), 'shot': k, 'foot': tag,
                                       'cm': d * 100, 'turn': abs(math.degrees(wrap(s['heading'] - p[4]))) / dt})
            prev[aid] = (k, g, yaw, {tag: (ank[tag] if in_stance(s['rig'], tag) else None) for tag in ('L', 'R')}, s['heading'])
        t += dt
    return snaps, slides


def stats(snaps, slides):
    d = np.array([s['deg'] for s in snaps]) if snaps else np.zeros(0)
    dy = np.array([abs(s['yaw'] - s['yaw_prev']) for s in snaps]) if snaps else np.zeros(0)
    cut = np.array([s['deg'] for s in snaps if s['cut']]) if snaps else np.zeros(0)
    cm = np.array([s['cm'] for s in slides]) if slides else np.zeros(0)
    straight = np.array([s['cm'] for s in slides if s['turn'] < 20.]) if slides else np.zeros(0)
    return {
        'frames': len(snaps),
        'snaps_over_25': int((d > SNAP_DEG).sum()),
        'snap_max': float(d.max()) if len(d) else 0.,
        'snap_p99': float(np.percentile(d, 99)) if len(d) else 0.,
        'snap_mean': float(d.mean()) if len(d) else 0.,
        'yaw_rate_max': float(dy.max()) if len(dy) else 0.,       # head alone, torso excluded
        'cuts': len(cut),
        'cut_max': float(cut.max()) if len(cut) else 0.,
        'cut_mean': float(cut.mean()) if len(cut) else 0.,
        'stance_frames': len(slides),
        'slide_median': float(np.median(cm)) if len(cm) else 0.,
        'slide_p95': float(np.percentile(cm, 95)) if len(cm) else 0.,
        'slide_max': float(cm.max()) if len(cm) else 0.,
        'slide_straight_p95': float(np.percentile(straight, 95)) if len(straight) else 0.,
    }


def report(snaps, slides, label=''):
    st = stats(snaps, slides); out = []
    out.append(f"saut de regard{label} : {st['snaps_over_25']} frame(s) > {SNAP_DEG:.0f} deg sur {st['frames']}, "
               f"max {st['snap_max']:.1f} deg, p99 {st['snap_p99']:.1f}, moyenne {st['snap_mean']:.2f}")
    out.append(f"   dont tete seule (hors rotation du corps) max {st['yaw_rate_max']:.1f} deg/frame ; "
               f"aux {st['cuts']} coupes max {st['cut_max']:.1f} deg, moyenne {st['cut_mean']:.2f}")
    for s in sorted(snaps, key=lambda s: -s['deg'])[:8]:
        if s['deg'] < 5.: break
        out.append(f"   {s['demo']:19s} t={s['t']:6.2f}s plan {s['shot']:2d} {s['who']:5s} {s['deg']:6.1f} deg"
                   f" ({'coupe' if s['cut'] else 'dans le plan'}, yaw {s['yaw_prev']:+6.1f} -> {s['yaw']:+6.1f})")
    out.append(f"glissement du pied porteur{label} : {st['stance_frames']} frames d'appui, median {st['slide_median']:.2f} cm/frame, "
               f"p95 {st['slide_p95']:.2f}, max {st['slide_max']:.2f} (p95 hors virage {st['slide_straight_p95']:.2f})")
    for s in sorted(slides, key=lambda s: -s['cm'])[:4]:
        out.append(f"   {s['demo']:19s} t={s['t']:6.2f}s plan {s['shot']:2d} {s['who']:5s} pied {s['foot']} {s['cm']:5.2f} cm"
                   f" (rotation du corps {s['turn']:5.1f} deg/s)")
    return '\n'.join(out)


OPTIONS = (('régie seule', {}), ('eyeline', {'eyeline': 'smooth'}),
           ('footing', {'footing': 'path'}), ('les deux', {'eyeline': 'smooth', 'footing': 'path'}))

def bench(ids=('demo2_dialogue', 'demo3_groupe', 'demo9_tempete', 'demo5_console'), aspect='16:9', n=7):
    """CPU cost of the acting layer itself: building the shots, then sampling them at 30 fps. No rendering.
    The rounds are interleaved and the minimum is kept: this machine runs several worktrees at once, so a single
    pass drifts by a factor of three. The minimum of n rounds is the closest thing to an uncontended reading."""
    import time
    acting_of(ids[0], aspect)                               # warm the imports and the set caches
    best = {}
    for _ in range(n):
        for d in ids:
            for label, over in OPTIONS:
                patch = (lambda ep, o=over: dict(ep, **o)) if over else None
                t0 = time.perf_counter(); ac, _ep, _sp = acting_of(d, aspect, patch); b = time.perf_counter() - t0
                t0 = time.perf_counter(); k = 0
                for sa in ac.shots.values():
                    for i in range(int(sa.dur * 30) + 1): sa.sample(min(sa.dur, i / 30.)); k += 1
                s_ = (time.perf_counter() - t0) / max(1, k)
                cur = best.get((d, label))
                best[(d, label)] = (min(b, cur[0]) if cur else b, min(s_, cur[1]) if cur else s_)
    return [(d, label, best[(d, label)][0], best[(d, label)][1] * 1e3) for d in ids for label, _o in OPTIONS]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('demos', nargs='*', default=None)
    ap.add_argument('--aspect', default='16:9'); ap.add_argument('--json', default=None)
    ap.add_argument('--eyeline', '--gaze', dest='eyeline', default=None, help='force episode["eyeline"] (ex: smooth, or a JSON object of options)')
    ap.add_argument('--footing', default=None, help='force episode["footing"] (ex: path)')
    ap.add_argument('--bench', action='store_true', help='CPU cost of the acting layer instead of the measurements')
    a = ap.parse_args()
    if a.bench:
        print(f"{'scénario':20s} {'option':12s} {'construction':>13s} {'échantillon':>13s}")
        for d, label, b, s_ in bench(aspect=a.aspect):
            print(f'{d:20s} {label:12s} {b * 1e3:10.1f} ms {s_:10.3f} ms')
        return
    ids = a.demos or DEMOS
    over = {}
    if a.eyeline is not None: over['eyeline'] = json.loads(a.eyeline) if a.eyeline.strip().startswith('{') else a.eyeline
    if a.footing is not None: over['footing'] = a.footing
    patch = (lambda ep: dict(ep, **over)) if over else None
    snaps = []; slides = []
    for d in ids:
        s, f = measure_demo(d, a.aspect, patch); snaps += s; slides += f
        st = stats(s, f)
        print(f"{d:20s} max {st['snap_max']:6.1f} deg, {st['snaps_over_25']:3d} saut(s), glissement p95 {st['slide_p95']:.2f} cm", flush=True)
    print()
    print(report(snaps, slides, '' if not over else ' (' + ', '.join(f'{k}={v}' for k, v in over.items()) + ')'))
    if a.json:
        json.dump({'label': over or 'reference', 'aspect': a.aspect, 'stats': stats(snaps, slides), 'snaps': snaps, 'slides': slides},
                  open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('->', a.json)


if __name__ == '__main__': main()
