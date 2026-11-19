"""python tools/vox_sheet.py [--prefix chr_] [--out dossier] [--batch 24]  -> planches de contrôle des modèles .vox importés (voxelgpu_js/assets_vox/), peints par le moteur VOXEL (GPU)."""
import argparse, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'tools'))
from PIL import Image, ImageDraw
from hstudio.voxelgpu import vox_import as V, contract as C, render
import b_props_sheet as S


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--prefix', default=''); ap.add_argument('--out', default=str(ROOT / 'projects' / 'vox_sheets')); ap.add_argument('--batch', type=int, default=24); ap.add_argument('--cols', type=int, default=6)
    a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    names = sorted(p.parent.name + '/' + p.stem for b in V.BANKS.glob('*') for p in b.glob('*.vox') if p.stem.startswith(a.prefix))
    items, bad = [], {}
    for n in names:
        try:
            kw = dict(height=2.0) if '/chr_' in n or '/mob_' in n and False else {}
            items.append((n.split('/')[1], [V.bset(n, **kw)], []))
        except Exception as e: bad[n] = f'{type(e).__name__}: {str(e)[:100]}'
    print(f'{len(items)} modèles lus, {len(bad)} en échec', bad if bad else '')
    for bi in range(0, len(items), a.batch):
        chunk = items[bi:bi + a.batch]; c = S.contract_for(chunk); cp = out / f'c_{a.prefix}{bi // a.batch:02d}.json'; C.save(c, cp); sd = out / f's_{a.prefix}{bi // a.batch:02d}'
        times = [round(s['t0'] + .12, 2) for s in c['stages']]
        render.run_painter(cp, None, 'nvidia', (480, 360), stills=times, stills_dir=sd, quiet=True, fallback=True)
        rows = (len(chunk) + a.cols - 1) // a.cols; sh = Image.new('RGB', (480 * a.cols, 360 * rows), (20, 20, 24)); d = ImageDraw.Draw(sh)
        for j, ((k, _, _), t) in enumerate(zip(chunk, times)):
            x, y = (j % a.cols) * 480, (j // a.cols) * 360; sh.paste(Image.open(sd / f't_{t:.2f}.png').convert('RGB').resize((480, 360)), (x, y)); d.rectangle([x, y, x + 8 * len(k) + 10, y + 16], fill=(0, 0, 0)); d.text((x + 4, y + 2), k, fill=(255, 255, 255))
        sh.save(out / f'planche_{a.prefix}{bi // a.batch:02d}.jpg', quality=82); print('planche', bi // a.batch)


if __name__ == '__main__': main()
