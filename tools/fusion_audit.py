"""python tools/fusion_audit.py [--out report.json]
Audits the FINISHED contract of the fusion film (what the painter will read), not the intentions: body (solid, wall, teleport, speed, overlap, head in lintel, hand through glass), declared vanish,
feet (in the floor, floating, slide without a step, drag per stance), faces (blink rate, stare, jumping pupils, expression without cause, mouth without speech) and the FILM-time sync of the faces."""
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu import director, blocking as B, faceact as FA, footkin as FK, genre_intent as G, stagegeo, contract as C
from hstudio.voxelgpu.films import pompe_fusion as F

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default=''); ap.add_argument('--gait', default='planted'); a = ap.parse_args(argv)
    ep = F.episode(gait=a.gait if a.gait != 'none' else None); c = director.build(ep, '9:16', 30); geo = stagegeo.station(F.N.DOORS)
    view, _ = G.compile_episode(ep); vs = view.vanishes
    rep = dict(preflight_violations=[repr(v) for v in c['preflight']['violations']], vanishes=c['preflight'].get('vanishes'))
    m = c                                     # director.build already hides the creature (vis = 0) in its vanish window and gives the painter the windows (cast look.monster.vanish)
    body = G.audit_declared(c, geo, vs)
    rep['body'] = [repr(v) for v in body]
    feet = FK.audit_feet(m); rep['feet'] = [repr(v) for v in feet]; rep['foot_drag_cm'] = {k: [round(v['mean'] * 100, 1), round(v['max'] * 100, 1), v['n']] for k, v in FK.slide_stats(m).items()}
    tr = FA.build_all(view, director.EXPR_MAP, list(C.EXPRESSIONS), c['duration'] + 1.)
    rep['faces'] = [repr(v) for v in FA.audit_faces(view, tr, list(C.EXPRESSIONS))]; rep['face_stage_sync'] = [repr(v) for v in FA.audit_stage_sync(c, tr)]
    rep['face_semantic'] = {k: {kk: vv for kk, vv in FA.semantic(view, k, tr[k], list(C.EXPRESSIONS)).items() if kk in ('blinks', 'reactions', 'model')} for k in tr}
    ix = {n: i for i, n in enumerate(c['actor_cols'])}; walk = []
    for v in vs:                                  # the creature must not move while it is not drawn
        for st in c['stages']:
            g = st['actors'].get(v['who']) or []
            hid = [(st['t0'] + j / c['fps'], r[ix['x']], r[ix['z']], r[ix['gait']]) for j, r in enumerate(g) if not r[ix['vis']] and v['t'] - .01 <= st['t0'] + j / c['fps'] <= v['until'] + .05]
            walk += [h for h in hid if h[3] != 0]
    rep['walking_while_vanished_frames'] = len(walk)
    vis = {}
    for st in c['stages']:
        for j, r in enumerate(st['actors'].get('ghost') or []):
            t = st['t0'] + j / c['fps']
            if 26.3 <= t <= 27.4: vis.setdefault(round(t, 2), r[ix['vis']])
    rep['ghost_vis_26.3_27.4'] = {'first_hidden': min([t for t, v in vis.items() if not v] or [None]), 'last_hidden': max([t for t, v in vis.items() if not v] or [None]), 'frames_hidden': sum(1 for v in vis.values() if not v)}
    rep['ok'] = not (rep['preflight_violations'] or rep['body'] or rep['faces'] or rep['face_stage_sync'] or rep['walking_while_vanished_frames'] or any(('pied_dans_le_sol' in x or 'glisse_sans_pas' in x or 'pied_flotte' in x) for x in rep['feet']))
    print(json.dumps(rep, indent=1, ensure_ascii=False))
    if a.out: Path(a.out).write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8')
    return rep


if __name__ == '__main__': main()
