"""Build the episode of « Le Dernier Noyau », solve every camera, run the full preflight WITHOUT rendering. usage: python tools/demo_cite_film.py [--preflight]"""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu.films import demo_cite_film as DF
t = time.time(); ep, F = DF.episode(); print('épisode construit en', round(time.time() - t, 1), 's :', len(ep['shots']), 'plans,', round(ep['duration'], 1), 's')
tot = 0.; prev = 0.
for s in ep['shots']: tot += s['dur']
print('somme des plans', round(tot, 3), 'durée du film', round(ep['duration'], 3))
Path(ROOT / 'projects' / 'demo_narrative_20261029').mkdir(exist_ok=True, parents=True)
(ROOT / 'projects' / 'demo_narrative_20261029' / 'episode.json').write_text(json.dumps(ep, ensure_ascii=False, default=str), encoding='utf-8')
