"""python tools/fusion_marche.py [out_dir]  -> « La marche » on the unified engine (GPU), 720x1280, 24 fps, 61 s, with score and footsteps."""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu.films import la_marche
from hstudio.voxelgpu import render, qa

out = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'projects' / 'fusion_20261029' / 'marche'); out.mkdir(parents=True, exist_ok=True)
wav = out / 'la_marche_musique.wav'
if not wav.exists():
    import subprocess; subprocess.run([sys.executable, str(ROOT / 'tools' / 'la_marche_music.py'), str(wav)], check=True)
rep = render.render_film(la_marche.episode(str(wav)), out / 'la_marche_unifie_720x1280_24fps.mp4', out / 'work', 'nvidia', '9:16')
q = qa.verify(out / 'la_marche_unifie_720x1280_24fps.mp4', 720, 1280, 24, 61.0, out_json=out / 'verification.json')
print(json.dumps(dict(ok=q['ok'], checks={k: v['detail'] for k, v in q['checks'].items()}, render_s=rep['render_s'], gpu=rep['attestation']['webgl']['renderer']), indent=1, ensure_ascii=False))
