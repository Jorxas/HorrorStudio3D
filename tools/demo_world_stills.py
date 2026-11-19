"""Stills of the demo worlds from hand-placed cameras (no actor, no audio): the quickest way to judge a world before a story uses it.
usage: python tools/demo_world_stills.py <set> [out_dir]    set = cite | astro | all
Each view is one 0.4 s shot rendered by the real painter on the GPU at 540x960; stills are PNG, a contact sheet is written beside them."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu import director, render, contract as C
from hstudio.remake.dsl import k, cam

CX, AX = 60., 190.
VIEWS = {
    'cite': [
        ('rue_large', 'cite', dict(), (CX - 30, 3.2, 8.5), (CX + 2, 2.2, -4), 62, dict(day=1)),
        ('terrasse', 'cite', dict(), (CX - 12, 1.7, 7.0), (CX - 1, 1.5, -4), 56, dict(day=1)),
        ('cafe_facade', 'cite', dict(), (CX + 4, 1.8, 6.5), (CX, 2.4, -6), 60, dict(day=1)),
        ('interieur', 'cite', dict(), (CX + 6.5, 1.8, -7.0), (CX - 2, 1.5, -13), 66, dict(day=1)),
        ('interieur_bar', 'cite', dict(), (CX - 5.5, 1.7, -7.0), (CX + 2, 1.6, -13.4), 62, dict(day=1)),
        ('ruelle', 'cite', dict(), (CX - 9.2, 1.7, -8), (CX - 9.2, 1.6, -34), 60, dict(day=1, alley=1)),
        ('rue_est', 'cite', dict(), (CX + 28, 3.0, 8.5), (CX - 4, 2.4, -3), 62, dict(day=1)),
        ('horloge', 'cite', dict(), (CX + 6, 1.7, 7.5), (CX + 14, 24, -9), 52, dict(day=1)),
        ('rue_nuit', 'cite', dict(), (CX - 30, 3.2, 8.5), (CX + 2, 2.2, -4), 62, dict(day=0, lit=1, lamps=1, cafe=1)),
    ],
    'astro': [
        ('toit_large', 'astroport', dict(), (AX + 18, 4.5, 20), (AX - 2, 2.5, 0), 62, dict(alt=0)),
        ('navette', 'astroport', dict(), (AX + 9, 1.8, 6), (AX, 2.4, -1), 58, dict(alt=0)),
        ('ascenseur', 'astroport', dict(), (AX - 12, 1.6, 6), (AX - 21, 1.5, 0), 60, dict(alt=0, lift_door=1)),
        ('ville_dessous', 'astroport', dict(), (AX + 10, 1.0, 20), (AX - 6, -12, 40), 70, dict(alt=0)),
        ('alt_mid', 'astroport', dict(), (AX + 14, 22, 12), (AX, 24, 0), 62, dict(alt=.45, lift=22, thrust=1, hatch=0)),
        ('alt_haut', 'astroport', dict(), (AX + 16, 80, 14), (AX, 84, 0), 62, dict(alt=.95, lift=80, thrust=1, hatch=0)),
    ],
}


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else 'cite'; out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / 'projects' / 'demo_narrative_20261029' / 'stills_worlds'
    out.mkdir(parents=True, exist_ok=True); views = VIEWS['cite'] + VIEWS['astro'] if which == 'all' else VIEWS[which]
    shots = []
    for name, world, _x, pos, look, fov, env in views:
        shots.append(dict(id=name, stage=world, dur=.4, camera=cam(k(0, pos, look, fov), k(.4, pos, look, fov)), actors=[], actions=[], env=env))
    ep = dict(title='stills', genre='neutral', aspect='9:16', fps=30, casts={'x': {'preset': 'npc'}}, shots=shots)
    # a hidden actor so that the contract has someone (the régie needs a cast to plan); it stands far away
    for s in shots: s['actors'] = [dict(id='x', at=[0, 0], facing='+x')]
    c = director.build(ep, '9:16', 30); cp = out / 'contract.json'; C.save(c, cp)
    times = [round(i * .4 + .2, 3) for i in range(len(views))]
    render.run_painter(cp, None, 'nvidia', size=(540, 960), stills=times, stills_dir=out, quiet=True)
    print('stills ->', out, sorted(p.name for p in out.glob('*.png'))[:20])


if __name__ == '__main__': main()
