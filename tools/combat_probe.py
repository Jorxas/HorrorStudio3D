"""A short fight in the café, planned by the blocking, audited, rendered as stills (jab, block, stagger, sword taken, slash, clash). Judges the combat verbs before a story uses them.
usage: python tools/combat_probe.py [out_dir]  -> blocking audit printed, stills + sheet written"""
import json, math, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu import blocking as BLK, director, render, contract as C
from hstudio.remake.dsl import k, cam

CX = 60.
SWORD = [{'bone': 'x'}]
SWORD_BOXES = [{'x': 0, 'y': 0, 'z': 9.5, 'w': 1.0, 'h': 2.4, 'd': 17, 'color': '#d8dce4'}, {'x': 0, 'y': 0, 'z': 0.6, 'w': 6, 'h': 1.0, 'd': 1.2, 'color': '#6a4a2a'}, {'x': 0, 'y': 0, 'z': -1.6, 'w': 1.4, 'h': 1.4, 'd': 3.4, 'color': '#3a2a1a'}]


def plan():
    c = lambda x: CX + x
    beats = [
        dict(who='vorn', t=.6, do='go', to=[c(-3.0), -10.9], by=1.4, face='ines'),
        dict(who='ines', t=.2, do='face', at='vorn'),
        dict(who='vorn', t=1.7, do='strike', at='ines', hand='R', kind='jab', height='chest', hit=False),
        dict(who='ines', t=1.7, do='guard', until=2.2, hand='L', at='vorn'),
        dict(who='ines', t=2.35, do='strike', at='vorn', hand='R', kind='cross', height='head', hit=True),
        dict(who='vorn', t=2.37, do='flinch', amount=-.7, dur=.45),
        dict(who='vorn', t=2.4, do='go', to=[c(-3.55), -10.9], by=2.9, backwards=True),
        dict(who='vorn', t=2.4, do='emote', face='pain'),
        dict(who='vorn', t=3.1, do='go', to=[c(-7.3), -11.07], by=4.2, face=[c(-9), -11.07]),
        dict(who='vorn', t=4.3, do='take', target='epee_a', hand='R', pose='grip', until=11.),
        dict(who='ines', t=3.2, do='go', to=[c(-5.3), -10.9], by=4.6, face='vorn'),
        dict(who='vorn', t=4.9, do='go', to=[c(-6.3), -10.9], by=5.4, face='ines'),
        dict(who='vorn', t=5.9, do='strike', at='ines', hand='R', kind='slash', height='chest', hit=False),
        dict(who='ines', t=5.9, do='go', to=[c(-4.6), -10.9], by=6.3, backwards=True),
        dict(who='vorn', t=6.6, do='go', to=[c(-5.6), -10.9], by=6.95, face='ines'),
        dict(who='vorn', t=7.0, do='strike', at='ines', hand='R', kind='overhead', height='head', hit=True),
        dict(who='ines', t=7.02, do='kneel', until=8.6, amount=.9),
        dict(who='ines', t=7.02, do='flinch', amount=-.5, dur=.4),
    ]
    return dict(actors={'ines': dict(start=dict(at=[c(-2.4), -10.9], yaw=-math.pi / 2)), 'vorn': dict(start=dict(at=[c(-4.4), -10.9], yaw=math.pi / 2), vmax=6.)}, beats=beats, duration=10.)


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'projects' / 'demo_narrative_20261029' / 'combat_probe'; out.mkdir(parents=True, exist_ok=True)
    ep = dict(title='combat probe', genre='adventure', aspect='9:16', fps=30, duration=10., casts={'ines': {'preset': 'lina'}, 'vorn': {'preset': 'npc', 'variant': 5}},
              shots=[], world_env={'day': 1, 'cafe': 1, 'lamps': 0}, blocking=dict(world='demo', doors={}, plan=plan(), audit='lenient', tight_max=1, insert_max=9))
    blk, geo = BLK.compile_episode(ep)
    for v in BLK.audit(blk): print(repr(v))
    ep['casts']['vorn']['extras'] = BLK.held_extras(blk, 'vorn', {'epee_a': SWORD_BOXES})
    side = (CX - 3.4, 1.6, -6.4), (CX - 3.4, 1.25, -11.0), 78
    cams = [(0, 's', *side), (1, 's', *side), (2, 's', *side)]
    seg = [(0., 3.4, 0), (3.4, 6.4, 1), (6.4, 10., 2)]
    for i, (t0, t1, ci) in enumerate(seg):
        _, nm, pos, look, fov = cams[ci]
        ep['shots'].append(dict(id=f'P{i}', stage='demo', dur=t1 - t0, camera=cam(k(0, pos, look, fov), k(t1 - t0, pos, look, fov)), env=dict(ep['world_env'])))
    for s in ep['shots']: s['stage'] = 'cite'
    c_ = director.build(ep, '9:16', 30); cp = out / 'contract.json'; C.save(c_, cp)
    times = [1.7, 2.3, 2.4, 2.7, 5.8, 6.0, 6.9, 7.0, 7.3]
    render.run_painter(cp, None, 'nvidia', size=(720, 1280), stills=times, stills_dir=out, quiet=True)
    print('stills', out)

c = lambda x: CX + x
if __name__ == '__main__': main()
