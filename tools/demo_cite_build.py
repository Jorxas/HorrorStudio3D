"""Build the contract of « Le Dernier Noyau » (with the full preflight: bodies, hands, blows, doors, cameras) and write it. usage: python tools/demo_cite_build.py"""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu import director, contract as C
from hstudio.voxelgpu.films import demo_cite_film as DF
WORK = ROOT / 'projects' / 'demo_narrative_20261029'
t = time.time(); ep, F = DF.episode(); print('épisode', round(time.time() - t, 1), 's', len(ep['shots']), 'plans')
(WORK / 'episode.json').write_text(json.dumps(ep, ensure_ascii=False, default=str), encoding='utf-8')
t = time.time()
try: c = director.build(ep, '9:16', 30)
except ValueError as e: print(str(e)[:6000]); sys.exit(1)
C.save(c, WORK / 'contract.json'); print('contrat', round(time.time() - t, 1), 's', len(c['stages']), 'stages ;', round((WORK / 'contract.json').stat().st_size / 1e6, 1), 'Mo')
