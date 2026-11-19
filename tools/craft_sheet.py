"""python tools/craft_sheet.py [--only a,b] [--group Nature] [--kind creature] [--out dossier] [--cols 6] [--batch 24]

Peint les éléments « craft » (hstudio/voxelgpu/craft.py) avec le moteur VOXEL (GPU), une image par recette et par variante (graine), nom dessous, en planches de contrôle.
Écrit rapport.json (recettes en échec, nombre de boîtes). À REGARDER avant de livrer : une recette qui ne ressemble à rien est une recette à refaire."""
import argparse, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw
from hstudio.voxelgpu import craft as CR, contract as C, render
from hstudio import catalogue as CT


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--only', default=''); ap.add_argument('--group', default=''); ap.add_argument('--kind', default=''); ap.add_argument('--out', default=str(ROOT / 'projects' / 'craft_sheets'))
    ap.add_argument('--cols', type=int, default=6); ap.add_argument('--batch', type=int, default=24); ap.add_argument('--variants', type=int, default=0); a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True); CR.load_all()
    names = [n for n, r in sorted(CR.REG.items()) if (not a.only or n in a.only.split(',')) and (not a.group or r['group'] == a.group) and (not a.kind or r['kind'] == a.kind)]
    rep = dict(ok={}, failed={}); items = []
    for n in names:
        for v in range(a.variants or CR.REG[n]['variants']):
            try:
                p, lt = CR.bset(n, seed=v); nb = len(p['boxes'])
                if not nb: raise ValueError('aucune boîte')
                items.append((f'{n}#{v}' if (a.variants or CR.REG[n]['variants']) > 1 else n, [p], lt)); rep['ok'][f'{n}#{v}'] = nb
            except Exception as e: rep['failed'][f'{n}#{v}'] = f'{type(e).__name__}: {str(e)[:120]}'
    print(f"{len(rep['ok'])} images, {len(rep['failed'])} en échec", rep['failed'] if rep['failed'] else '')
    for bi in range(0, len(items), a.batch):
        chunk = items[bi:bi + a.batch]; c = CT._contract(chunk); cp = out / f'c_{bi // a.batch:02d}.json'; C.save(c, cp); sd = out / f's_{bi // a.batch:02d}'
        times = [round(s['t0'] + .12, 2) for s in c['stages']]; render.run_painter(cp, None, 'nvidia', (480, 360), stills=times, stills_dir=sd, quiet=True, fallback=True)
        rows = (len(chunk) + a.cols - 1) // a.cols; sh = Image.new('RGB', (480 * a.cols, 360 * rows), (20, 20, 24)); d = ImageDraw.Draw(sh)
        for j, ((k, _, _), t) in enumerate(zip(chunk, times)):
            x, y = (j % a.cols) * 480, (j // a.cols) * 360; sh.paste(Image.open(sd / f't_{t:.2f}.png').convert('RGB').resize((480, 360)), (x, y)); d.rectangle([x, y, x + 8 * len(k) + 10, y + 16], fill=(0, 0, 0)); d.text((x + 4, y + 2), k, fill=(255, 255, 255))
        sh.save(out / f'planche_{bi // a.batch:02d}.jpg', quality=82); print('planche', bi // a.batch, flush=True)
    (out / 'rapport.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__': main()
