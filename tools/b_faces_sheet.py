"""python tools/b_faces_sheet.py [--all43 | --voxel | --names a,b] [--out dossier] [--cols 6] [--skin noe|lina]

Planche de contrôle des visages du moteur VOXEL : un gros plan par expression, peint par le GPU, avec le nom dessous.
  --all43  les 43 noms de PIXEL 3D (hstudio/director/validate.FACES), résolus par EXPR_MAP (HSTUDIO_EXPR_LEGACY=1 : l'ancienne table à 17 expressions)
  --voxel  les préréglages de face4.js dans l'ordre de contract.EXPRESSIONS
  --names  une liste de noms (de PIXEL 3D, ou de préréglages VOXEL si le nom n'est pas dans EXPR_MAP)
Écrit aussi les PNG bruts dans <out>/png/<nom>.png (sert à prouver qu'une modification ne change pas les visages existants : --compare dossier_de_référence)."""
import argparse, importlib, json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import numpy as np
from PIL import Image, ImageDraw
from hstudio.voxelgpu import contract as C, render
DIR = importlib.import_module('hstudio.voxelgpu.director')
ANGLE = 0.; FPS = 24; DUR = .5; N = int(np.ceil(DUR * FPS)); CI = {n: i for i, n in enumerate(C.ACTOR_COLS)}


def contract_for(names, skin):
    exprs = list(C.EXPRESSIONS); stages = []; t = 0.
    for i, nm in enumerate(names):
        vn = DIR.EXPR_MAP.get(nm, nm)
        if vn not in exprs: raise SystemExit(f'expression inconnue du contrat : {nm} -> {vn}')
        row = C.empty_frame(); row[CI['vis']] = 1; row[CI['expr']] = exprs.index(vn); row[CI['seat_h']] = .47
        cam = [[1.45 * np.sin(np.radians(ANGLE)), 1.74, 1.45 * np.cos(np.radians(ANGLE)), 0, 1.70, 0, 36., 0.] for _ in range(N)]
        stages.append(dict(id=f'f{i:02d}_{nm}', world='plateau', t0=round(t, 4), t1=round(t + DUR, 4), tail=0., dissolve=0., mood=None, look={}, camera=cam,
                           actors={'a': [list(row) for _ in range(N)]}, focus_actor='a', props=[], lights=[], env=dict(floor=0x4a4a52, bg=0x303846, ambient=1.4, key=1.6, fog=0.002), foley_steps={}))
        t += DUR
    return dict(schema=C.SCHEMA, face_style=('legacy' if os.environ.get('HSTUDIO_FACE_LEGACY') == '1' else 'natural'), title='planche de visages', genre='neutral', aspect='9:16', fps=FPS, duration=round(t, 4), casts={'a': {'preset': skin}}, expressions=exprs, actor_cols=C.ACTOR_COLS,
                stages=stages, fx=[], captions=[], caption_style={}, hud=None, cards=[], audio={})


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--all43', action='store_true'); ap.add_argument('--voxel', action='store_true'); ap.add_argument('--names', default='')
    ap.add_argument('--out', default=str(ROOT / 'projects' / 'b_faces')); ap.add_argument('--cols', type=int, default=6); ap.add_argument('--skin', default='noe'); ap.add_argument('--batch', type=int, default=24)
    ap.add_argument('--compare', default=''); ap.add_argument('--angle', type=float, default=0.); a = ap.parse_args(); globals()['ANGLE'] = a.angle
    if a.all43: names = sorted(importlib.import_module('hstudio.director.validate').FACES)
    elif a.voxel: names = list(C.EXPRESSIONS)
    else: names = [n for n in a.names.split(',') if n]
    out = Path(a.out); (out / 'png').mkdir(parents=True, exist_ok=True); sizes = (360, 360); sheets = []
    for bi in range(0, len(names), a.batch):
        chunk = names[bi:bi + a.batch]; c = contract_for(chunk, a.skin); errs = C.validate(c)
        if errs: raise SystemExit(f'contrat refusé : {errs[:3]}')
        cp = out / f'contrat_{bi // a.batch:02d}.json'; C.save(c, cp); sd = out / f'stills_{bi // a.batch:02d}'
        times = [round(s['t0'] + .3, 2) for s in c['stages']]
        render.run_painter(cp, None, 'nvidia', (480, 480), stills=times, stills_dir=sd, quiet=True, fallback=True)
        for nm, t in zip(chunk, times): Image.open(sd / f't_{t:.2f}.png').convert('RGB').save(out / 'png' / f'{nm}.png')
    rows = (len(names) + a.cols - 1) // a.cols; sheet = Image.new('RGB', (sizes[0] * a.cols, (sizes[1] + 18) * rows), (18, 18, 22)); d = ImageDraw.Draw(sheet)
    for j, nm in enumerate(names):
        x, y = (j % a.cols) * sizes[0], (j // a.cols) * (sizes[1] + 18); sheet.paste(Image.open(out / 'png' / f'{nm}.png').resize(sizes), (x, y)); vn = DIR.EXPR_MAP.get(nm, nm)
        d.text((x + 6, y + sizes[1] + 3), nm + ('' if vn == nm else f'  -> {vn}'), fill=(235, 235, 235))
    sheet.save(out / 'planche.jpg', quality=85); print('planche :', out / 'planche.jpg', len(names), 'visages')
    if a.compare:
        ref = Path(a.compare) / 'png'; diff = {}
        for nm in names:
            if (ref / f'{nm}.png').exists():
                A = np.asarray(Image.open(ref / f'{nm}.png').convert('RGB'), np.int16); B = np.asarray(Image.open(out / 'png' / f'{nm}.png').convert('RGB'), np.int16); diff[nm] = int(np.abs(A - B).max())
        bad = {k: v for k, v in diff.items() if v}; print(f'comparaison avec {ref} : {len(diff) - len(bad)} identiques, {len(bad)} différents', bad or '')
        sys.exit(1 if bad else 0)


if __name__ == '__main__': main()
