"""Même scène dirigée, deux styles : tools/both_styles.py <dossier avec episode.json + lines.json> <sortie.jpg> t1 t2 ... [--aspect 16:9]
Ligne du haut = style PS1 (PIXEL 3D), ligne du bas = style VOXEL (peintre GPU). La logique (acteurs, caméras) est écrite une seule fois."""
import sys, os, json, time, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
from PIL import Image
from hstudio.voxelgpu import from_ps1, contract as C, render
from hstudio.pipeline import make_engine

def main():
    a = sys.argv[1:]; asp = '16:9'
    if '--aspect' in a: i = a.index('--aspect'); asp = a[i + 1]; del a[i:i + 2]
    pdir, outp, times = Path(a[0]), Path(a[1]), [float(x) for x in a[2:]]
    ep = json.loads((pdir / 'episode.json').read_text(encoding='utf-8')); lines = json.loads((pdir / 'lines.json').read_text(encoding='utf-8'))
    dur = float(lines[-1]['end']) + 1.2
    tw, th = (480, 270) if asp == '16:9' else (270, 480)
    top = []
    eng = make_engine('pixel3d', json.loads(json.dumps(ep)), lines, __import__('numpy').zeros(int(dur * 30) + 60), dur, asp)
    for t in times: top.append(Image.fromarray(eng.render_lowres(t)[0]).convert('RGB').resize((tw, th), Image.NEAREST))
    c = from_ps1.build(json.loads(json.dumps(ep)), lines, dur, asp, 24, lambda *_: None)
    tmp = Path(tempfile.mkdtemp()); cp = tmp / 'contract.json'; C.save(c, cp)
    w, h = render.SIZES[asp]
    render.run_painter(cp, None, 'nvidia', (w // 2, h // 2), stills=times, stills_dir=tmp, quiet=True, fallback=True)
    bot = [Image.open(tmp / f't_{t:.2f}.png').convert('RGB').resize((tw, th)) for t in times]
    sheet = Image.new('RGB', (tw * len(times), th * 2))
    for i, (x, y) in enumerate(zip(top, bot)): sheet.paste(x, (i * tw, 0)); sheet.paste(y, (i * tw, th))
    sheet.save(outp, quality=88); print('planche', outp, sheet.size)
main()
