"""python tools/catalogue_ps1_sheet.py [--per 8] [--cats decor,lieu,...] [--out dossier]

Planches de contrôle des miniatures PS1 du catalogue : quelques fiches de chaque préfixe (decor, lieu, perso, visage, craft, vox, look, monstre), peintes sur place
(sans pool), avec le nom dessous et les erreurs listées. À REGARDER : le PS1 doit ressembler à du PS1 (bas-pixel, tramé), pas à du VOXEL."""
import argparse, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw
from hstudio import catalogue as CT, catalogue_ps1 as P1


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--per', type=int, default=8); ap.add_argument('--cats', default='decor,lieu,perso,visage,craft,vox,look,monstre'); ap.add_argument('--cols', type=int, default=4)
    ap.add_argument('--out', default=str(ROOT / 'projects' / 'catalogue_ps1_sheets')); ap.add_argument('--offset', type=int, default=0); a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True); es = CT.entries(); groups = P1.char_groups()
    for cat in a.cats.split(','):
        sel = [e for e in es if e['id'].split('/', 1)[0] == cat and not e.get('reference')]
        step = max(1, len(sel) // a.per); sel = sel[a.offset::step][:a.per]; ims, errs = [], {}
        for e in sel:
            sp = P1.spec_of(e, groups)
            if sp is None: errs[e['id']] = 'sans spec'; continue
            t0 = time.time()
            try: im = P1.render(sp)
            except Exception as ex: errs[e['id']] = f'{type(ex).__name__}: {str(ex)[:100]}'; continue
            d = ImageDraw.Draw(im); d.rectangle([0, 0, 8 * len(e['name']) + 8, 14], fill=(0, 0, 0)); d.text((4, 2), e['name'], fill=(255, 255, 255)); ims.append((im, time.time() - t0))
        if not ims: print(cat, 'AUCUNE image', errs); continue
        cols = min(a.cols, len(ims)); rows = (len(ims) + cols - 1) // cols; sh = Image.new('RGB', (P1.W * cols, P1.H * rows), (20, 20, 24))
        for i, (im, _) in enumerate(ims): sh.paste(im, ((i % cols) * P1.W, (i // cols) * P1.H))
        sh.save(out / f'planche_{cat}.jpg', quality=85); print(f"{cat}: {len(ims)} images (moy {sum(t for _, t in ims) / len(ims):.2f} s), erreurs : {errs or 'aucune'}")


if __name__ == '__main__': main()
