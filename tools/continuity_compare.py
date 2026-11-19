"""python tools/continuity_compare.py
FACT CHECK of the claim "the first engine kept spatial continuity better": the same measurement (distance an actor jumps between the last frame of a shot and
the first frame of the next one, same world, same actor) on contracts produced by three paths:
  * the régie path (acting.timeline.ShotActing carries `end_states` from shot to shot): the demo films `la_marche`, `demo_genres`;
  * the direct-keyframe path of the first remakes (`tracks`, one key at t=0 per shot): remake_pompe, remake_sol;
  * the blocked film (one trajectory per actor for the whole film): pompe_continuite.
A jump is counted when it exceeds what the actor could walk in the time between the two frames (5 m/s) plus 0.35 m."""
import math, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu import director
from hstudio.voxelgpu.films import la_marche, demo_genres, remake_pompe, remake_sol, pompe_continuite


def jumps(c):
    fps = c['fps']; ix = {n: i for i, n in enumerate(c['actor_cols'])}; out = []; n_pairs = 0
    for a, b in zip(c['stages'][:-1], c['stages'][1:]):
        if a['world'] != b['world']: continue
        for aid in set(a['actors']) & set(b['actors']):
            na = int(round((a['t1'] - a['t0']) * fps)); ra = a['actors'][aid][min(na, len(a['actors'][aid])) - 1]; rb = b['actors'][aid][0]
            if not (ra[ix['vis']] and rb[ix['vis']]): continue
            gap = max(1 / fps, b['t0'] - (a['t0'] + (na - 1) / fps)); d = math.hypot(ra[ix['x']] - rb[ix['x']], ra[ix['z']] - rb[ix['z']]); n_pairs += 1
            if d > 5. * gap + .35: out.append((a['id'], b['id'], aid, round(d, 2)))
    return n_pairs, out


for name, ep in (('régie : la_marche', la_marche.episode()), ('régie : demo_genres', demo_genres.episode()), ('clés directes : remake_pompe', remake_pompe.episode()),
                 ('clés directes : remake_sol', remake_sol.episode()), ('blocage : pompe_continuite', pompe_continuite.episode())):
    c = director.build(ep, '9:16', ep.get('fps', 24)); n, j = jumps(c)
    print(f"{name:34s} {n:4d} raccords acteur/plan, {len(j):3d} sauts anormaux" + (f" (max {max(x[3] for x in j)} m)" if j else ''))
