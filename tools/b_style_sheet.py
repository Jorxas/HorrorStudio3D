"""python tools/b_style_sheet.py [--models coffin,pumpkin_orange,lantern_standing,bench] [--targets 28,48,64] [--out dossier]

OUTIL DE RÉFÉRENCE (rien n'est écrit dans les banques) : une planche qui met nos décors de PIXEL 3D (lit, canapé, arbre, lampe) à côté de maillages KayKit voxélisés à plusieurs finesses
(`mesh_voxelize.voxelize(target=...)` : 28 = la banque actuelle, 48, 64), avec le nombre de boîtes et la note de `style_check` sous chaque image. Sert à COMPARER une référence à notre rendu,
pas à fabriquer des éléments de production."""
import argparse, json, shutil, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw
from hstudio.voxelgpu import b_props as BP, b_style as ST, craft as CR, vox_import as VI, mesh_voxelize as MV, contract as C, render
from hstudio import catalogue as CT

PACK = ROOT.parent / 'assets_externes' / 'kaykit' / 'KayKit-Halloween-Bits-1.0'


def find_gltf(name):
    for p in PACK.rglob(f'{name}.gltf'):
        if 'fbx(unity)' not in p.parts: return p
    raise FileNotFoundError(name)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--models', default='coffin,pumpkin_orange,lantern_standing,bench'); ap.add_argument('--targets', default='28,48,64'); ap.add_argument('--out', default=str(ROOT / 'projects' / 'b_style_sheet'))
    a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True); models = a.models.split(','); targets = [int(t) for t in a.targets.split(',')]
    items = []; notes = []
    for k in ('bed', 'sofa', 'tree', 'lamp'):
        p, lt = BP.convert_item(dict(type='b:' + k, at=[0, 0])); r = ST.check(p['boxes'], 'decor', CR.PAL); items.append((f'NOTRE {k}', [p], lt)); notes.append(f"{len(p['boxes'])} boîtes, note {r['score']}")
    tmp = Path(tempfile.mkdtemp(prefix='b_style_')); bank = tmp / 'ref'; bank.mkdir(); old = VI.BANKS; VI.BANKS = tmp; sc = {}
    try:
        for m in models:
            for t in targets:
                keys, cols, v = MV.voxelize(find_gltf(m), target=t); nm = f'{m}_{t}'; MV.write_vox(bank / f'{nm}.vox', keys, cols); sc[nm] = round(float(v), 5)
        (bank / 'SCALES.json').write_text(json.dumps(sc), encoding='utf-8')
        for m in models:
            for t in targets:
                p = VI.bset(f'ref/{m}_{t}', height=None); r = ST.check(p['boxes'], 'decor', CR.PAL); items.append((f'réf {m} @{t}', [p], [])); notes.append(f"{len(p['boxes'])} boîtes, note {r['score']}")
    finally: VI.BANKS = old; shutil.rmtree(tmp, ignore_errors=True)
    c = CT._contract(items); cp = out / 'c.json'; C.save(c, cp); times = [round(s['t0'] + .12, 2) for s in c['stages']]
    render.run_painter(cp, None, 'nvidia', (480, 360), stills=times, stills_dir=out / 's', quiet=True, fallback=True)
    cols = len(targets) + 1 if False else 4; rows = (len(items) + cols - 1) // cols; sh = Image.new('RGB', (480 * cols, 380 * rows), (20, 20, 24)); d = ImageDraw.Draw(sh)
    for j, ((k, _, _), t, n) in enumerate(zip(items, times, notes)):
        x, y = (j % cols) * 480, (j // cols) * 380; sh.paste(Image.open(out / 's' / f't_{t:.2f}.png').convert('RGB'), (x, y)); d.rectangle([x, y + 360, x + 480, y + 380], fill=(0, 0, 0)); d.text((x + 4, y + 364), f'{k} : {n}', fill=(255, 255, 255))
    sh.save(out / 'planche.jpg', quality=84); print('planche :', out / 'planche.jpg')


if __name__ == '__main__': main()
