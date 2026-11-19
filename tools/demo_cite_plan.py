"""Compile and audit the blocking of « Le Dernier Noyau » WITHOUT rendering: python tools/demo_cite_plan.py
Prints the timeline (anchors), every violation of the blocking audit (bodies, hands, blows, doors) in French, and the speed/length of each walk."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu import blocking as BLK, stagegeo
from hstudio.voxelgpu.films import demo_cite as D, demo_cite_story as S


def doors_of(F):
    ev = F.ev
    def sw(*iv):
        iv = sorted(iv); m = []
        for a, b in iv:                                    # overlapping or touching windows are one window
            if m and a - .5 <= m[-1][1] + .5: m[-1] = (m[-1][0], max(m[-1][1], b))
            else: m.append((a, b))
        return D.swing((0, 0), *[p for (a, b) in m for p in ((a - .5, 0), (a, 1), (b, 1), (b + .5, 0))])
    return {'cafe_porte': sw(ev['door1'], ev['door2'], ev['door3']), 'monte_charge': sw(ev['lift_open']), 'lift_toit': sw(ev['lift_roof'])}


def main():
    V = D.voice(); F = S.story(V); doors = doors_of(F)
    for w in getattr(F, 'speed_warn', []) + getattr(F, 'shift_warn', []): print('NOTE', w)
    plan = dict(actors=F.actors, beats=F.beats, duration=F.duration)
    geo = stagegeo.GEOS['demo'](doors)
    C = BLK.compile_plan(plan, geo)
    print('durée', round(F.duration, 1), 's ; lignes de voix', len(F.placed), '; repères', {k: round(v, 2) for k, v in F.notes.items() if isinstance(v, float)})
    v = BLK.audit(C)
    for x in v: print(repr(x))
    print(len(v), 'violation(s)')
    return C, F


if __name__ == '__main__': main()
