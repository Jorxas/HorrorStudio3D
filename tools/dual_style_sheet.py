"""python tools/dual_style_sheet.py episode.json [--out planche.jpg] : le MÊME épisode peint en style PS1 (ligne du haut) et en style VOXEL (ligne du bas), un plan par colonne.

L'épisode est écrit une fois (sets, cast, plans) ; `render_engine` du projet ne change que le peintre. Sert à vérifier que les éléments (décors craft, modèles .vox, looks, monstres, lieux) existent dans les deux styles."""
import argparse, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw


def to_voxel_coords(ep):
    """les positions d'un épisode PS1 (caméra vers +z) -> celles de VOXEL (caméra vers -z, lieux agrandis de K) : x et z changent de signe, le regard se retourne"""
    from hstudio.voxelgpu.b_sets import K
    f = lambda p: [round(-K * p[0], 3), round(-K * p[1], 3)]
    flip = {'+z': '-z', '-z': '+z', '+x': '-x', '-x': '+x'}
    for sh in ep.get('shots', []):
        for a in sh.get('actors', []):
            if a.get('at'): a['at'] = f(a['at'])
            if a.get('facing') in flip: a['facing'] = flip[a['facing']]
        for ac in sh.get('actions', []):
            if isinstance(ac.get('to'), list) and len(ac['to']) == 2: ac['to'] = f(ac['to'])
    return ep


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('episode'); ap.add_argument('--out', default=str(ROOT / 'projects' / 'dual_style.jpg')); ap.add_argument('--t', type=float, default=.5); a = ap.parse_args()
    ep = json.loads(Path(a.episode).read_text(encoding='utf-8')); n = len(ep['shots']); tw, th = 640, 360; sheet = Image.new('RGB', (tw * n, th * 2), (20, 20, 24)); d = ImageDraw.Draw(sheet)
    from hstudio.pipeline import make_engine
    for i, sh in enumerate(ep['shots']):
        sh['dur'] = sh.get('dur', 1.5); one = json.loads(json.dumps(ep)); one['shots'] = [dict(sh, lines=[0, 0])]
        lines = [{'who': next(iter(ep.get('cast') or ep.get('casts') or {'x': 0})), 'text': 'x', 'start': 0., 'end': sh['dur']}]
        t0 = time.time(); eng = make_engine('pixel3d', json.loads(json.dumps(one)), lines, {}, sh['dur'] + .5, '16:9'); im = Image.fromarray(eng.render_lowres(a.t)[0]).convert('RGB').resize((tw, th), Image.NEAREST)
        sheet.paste(im, (i * tw, 0)); print(f'PS1   plan {i} : {time.time() - t0:.1f} s', flush=True)
    from hstudio.voxelgpu import director, contract as C, render
    v = to_voxel_coords(json.loads(json.dumps(ep))); v['casts'] = v.pop('cast', v.get('casts', {})); v.setdefault('genre', 'neutral'); v.setdefault('title', 'dual'); v['duration'] = sum(s.get('dur', 1.5) for s in v['shots'])
    c = director.build(v, '16:9', 24); cp = ROOT / 'projects' / 'dual_contract.json'; C.save(c, cp); sd = ROOT / 'projects' / 'dual_stills'
    times = [round(s['t0'] + a.t, 2) for s in c['stages']]; t0 = time.time(); render.run_painter(cp, None, 'nvidia', (tw, th), stills=times, stills_dir=sd, quiet=True, fallback=True)
    print(f'VOXEL {len(times)} plans : {time.time() - t0:.0f} s', flush=True)
    for i, t in enumerate(times): sheet.paste(Image.open(sd / f't_{t:.2f}.png').convert('RGB').resize((tw, th)), (i * tw, th))
    d.text((6, 4), 'PS1', fill=(255, 255, 255)); d.text((6, th + 4), 'VOXEL', fill=(255, 255, 255)); sheet.save(a.out, quality=84); print(a.out)


if __name__ == '__main__': main()
