"""python tools/fusion_demo.py [out_dir] [16:9 9:16]  -> « Dix mondes, dix genres » on the unified engine (GPU), with its own music and sound effects."""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu.films import demo_genres
from hstudio.voxelgpu import render, qa

out = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'projects' / 'fusion_20261029' / 'demo'); out.mkdir(parents=True, exist_ok=True)
aspects = sys.argv[2:] or ['16:9', '9:16']
for asp in aspects:
    tag = asp.replace(':', 'x'); w, h = render.SIZES[asp]; mp4 = out / f'dix_mondes_dix_genres_{tag}_{w}x{h}_24fps.mp4'
    rep = render.render_film(demo_genres.episode(), mp4, out / f'work_{tag}', 'nvidia', asp)
    q = qa.verify(mp4, w, h, 24, demo_genres.episode()['duration'], out_json=out / f'verification_{tag}.json')
    print(asp, json.dumps(dict(ok=q['ok'], checks={k: v['detail'] for k, v in q['checks'].items()}, render_s=rep['render_s']), ensure_ascii=False))
