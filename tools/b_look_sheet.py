"""python tools/b_look_sheet.py [--bank mmmm|kk_adventurers|kk_skeletons|all] [--only a,b] [--out dossier] [--batch 12]

Planches de contrôle des personnages importés REFONDUS (hstudio/voxelgpu/b_look.py) : pour chaque look, la figurine d'origine (miniature du catalogue, si elle existe), puis NOTRE personnage
peint par le moteur (plan large, gros plan), par le directeur (la vraie chaîne : `casts: {"b_look": ...}` -> b_chars.py -> contrat -> peintre). rapport.json : échecs."""
import argparse, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'tools'))
from PIL import Image, ImageDraw
from hstudio.voxelgpu import director, contract as C, render, b_look as BL
import b_chars_sheet as CS
from hstudio import catalogue as CT

TW, TH = 220, 300


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--bank', default='all'); ap.add_argument('--only', default=''); ap.add_argument('--out', default=str(ROOT / 'projects' / 'b_look_sheets')); ap.add_argument('--batch', type=int, default=12)
    a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    banks = BL.BANK_CHARS if a.bank == 'all' else a.bank.split(',')
    items = [(e['key'], e) for e in BL.entries() if e['key'].split('/')[0] in banks and (not a.only or e['key'].split('/')[1] in a.only.split(','))]
    rep = dict(ok=[], failed={})
    for bi in range(0, len(items), a.batch):
        chunk = items[bi:bi + a.batch]; tag = f'{a.bank}_{bi // a.batch:02d}'
        try:
            ep = CS.episode([(k, {'b_look': k}) for k, _ in chunk], False); c = director.build(ep, '16:9', 24)
            for j, st in enumerate(c['stages']):
                wide = j % 2 == 0; pos = [1.2, 1.35, 5.6] if wide else [0.5, 1.75, 2.1]; look = [0, 1.0, 0] if wide else [0, 1.65, 0]
                st['camera'] = [[*pos, *look, 40., 0.] for _ in st['camera']]
            cp = out / f'contrat_{tag}.json'; C.save(c, cp); sd = out / f'stills_{tag}'; times = [round(s['t0'] + .25, 2) for s in c['stages']]; t0 = time.time()
            render.run_painter(cp, None, 'nvidia', (360, 480), stills=times, stills_dir=sd, quiet=True, fallback=True)
            per_row = 3; rows = (len(chunk) + per_row - 1) // per_row; sh = Image.new('RGB', (TW * 3 * per_row, TH * rows), (20, 20, 24)); d = ImageDraw.Draw(sh)
            for i, (k, e) in enumerate(chunk):
                x0, y0 = (i % per_row) * TW * 3, (i // per_row) * TH
                th = ROOT / 'catalogue' / 'thumbs' / (CT.slug('vox/' + k) + '.jpg')
                if th.exists(): sh.paste(Image.open(th).convert('RGB').resize((TW, int(TW * .75))), (x0, y0 + 20))
                for w in range(2): sh.paste(Image.open(sd / f't_{times[2 * i + w]:.2f}.png').convert('RGB').resize((TW, TH)), (x0 + TW * (w + 1), y0))
                lab = k.split('/')[1] + '  ->  ' + ' '.join(f'{kk}={vv}' for kk, vv in e['cast'].items() if kk in ('b_preset', 'outfit', 'hat', 'hair_style', 'hold', 'beard'))[:34]
                d.rectangle([x0, y0, x0 + TW * 3, y0 + 14], fill=(0, 0, 0)); d.text((x0 + 3, y0 + 1), lab, fill=(255, 255, 255))
            sh.save(out / f'planche_{tag}.jpg', quality=84); rep['ok'] += [k for k, _ in chunk]; print(f'planche {tag} : {len(chunk)} looks en {time.time() - t0:.0f} s', flush=True)
        except Exception as ex:
            for k, _ in chunk: rep['failed'][k] = f'{type(ex).__name__}: {str(ex)[:200]}'
            print('ÉCHEC', tag, type(ex).__name__, str(ex)[:300], flush=True)
    (out / 'rapport.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8'); print(f"{len(rep['ok'])} peints, {len(rep['failed'])} en échec")


if __name__ == '__main__': main()
