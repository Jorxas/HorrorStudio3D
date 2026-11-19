"""python tools/ps1_cast_sheet.py [--arch a,b | --looks mmmm/chr_nun,...] --out planche.png : personnages VOXEL (archétypes, looks) rendus en style PS1."""
import os, sys, time, argparse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from PIL import Image
from hstudio.pipeline import make_engine

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--arch', default=''); ap.add_argument('--looks', default=''); ap.add_argument('--out', default='ps1_cast.png'); a = ap.parse_args()
    items = [('arch:' + n, {'kind': 'creature', 'archetype': n}) for n in a.arch.split(',') if n] + [('look:' + n, {'b_look': n}) for n in a.looks.split(',') if n]
    ims = []
    for name, spec in items:
        ep = {'engine_version': 1, 'default_set': 's', 'sets': {'s': {'type': 'forest', 'seed': 2, 'props': []}}, 'cast': {'x': spec},
              'shots': [{'lines': [0, 0], 'actors': [{'id': 'x', 'at': [0., 6.], 'facing': '-z'}], 'actions': [], 'camera': {'shot': 'full', 'on': ['x']}}]}
        lines = [{'who': 'x', 'text': 'x', 'start': 0., 'end': 1.}]
        eng = make_engine('pixel3d', ep, lines, {}, 1.5, '16:9'); t0 = time.perf_counter(); ims.append(Image.fromarray(eng.render_lowres(.5)[0])); print(name, round(time.perf_counter() - t0, 2), 's')
    w, h = ims[0].size; cols = min(4, len(ims)); rows = (len(ims) + cols - 1) // cols; sh = Image.new('RGB', (w * cols, h * rows))
    for i, im in enumerate(ims): sh.paste(im, ((i % cols) * w, (i // cols) * h))
    sh.resize((sh.width * 2, sh.height * 2), Image.NEAREST).save(a.out); print(a.out)
