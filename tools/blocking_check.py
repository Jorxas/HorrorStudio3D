"""python tools/blocking_check.py <film module in hstudio/voxelgpu/films> [--json out.json]
The deterministic preflight of a blocked film, on its own: bodies (walls, solids, teleports, speed, doors), hands (reach), cameras (inside a wall,
through a wall, zoom, the thing the narration names whole and visible), framing (tight shots). No image is drawn, nothing needs the GPU.
Exit status 1 if anything is refused, with the list in French."""
import argparse, importlib, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu import blocking as BLK

ap = argparse.ArgumentParser(); ap.add_argument('film'); ap.add_argument('--json'); ap.add_argument('--quiet', action='store_true'); a = ap.parse_args()
mod = importlib.import_module(f'hstudio.voxelgpu.films.{a.film}')
try: ep = mod.episode()
except BLK.PlanError as e: print('PLAN REFUSÉ :', e); sys.exit(1)
C, geo = BLK.compile_episode(ep); fps = ep['fps']; t0 = 0.; shots = []
for s in ep['shots']: shots.append(dict(s, _t0=t0)); t0 += float(s['dur'])
viol, rep = BLK.preflight(ep, C, geo, [s for s in shots if s.get('frame')])
if a.json: Path(a.json).write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8')
if not a.quiet:
    for v in viol: print(v)
    for r in rep['shots']: print(f"{r['id']} {r['kind']:6s} fov {r['fov']} " + ' '.join(f"{k}:{'ok' if v['whole'] else 'COUPÉ'}/{v['share_w']}" for k, v in r['show'].items()) + ' ' + ' '.join(f"{k}:head {v['head_share']} face {v['face_angle']}°" for k, v in r['actors'].items()))
print(f"{len(viol)} problème(s) ; plans serrés {rep['tight_share'] * 100:.0f} % du film, inserts {rep['inserts']}")
sys.exit(1 if viol else 0)
