"""python tools/ps1_elements_sheet.py --names craft:oak_tree,vox:kk_halloween/coffin [--out planche.png]

Pose chaque élément VOXEL seul dans un décor PS1 (PIXEL 3D) et assemble une planche + les temps de rendu."""
import os, sys, json, time, argparse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import numpy as np
from PIL import Image
from hstudio import demos
from hstudio.pipeline import make_engine

CAST = {}

def episode(kind, extra=None):
    if '@' in kind: kind, h = kind.split('@'); extra = dict(extra or {}, height=float(h))
    p = {'type': kind, 'at': [0., 5.], 'id': 'el'}; p.update(extra or {})
    return {'engine_version': 1, 'default_set': 's', 'sets': {'s': {'type': 'forest', 'seed': 2, 'props': [p]}}, 'cast': {'lea': {'preset': 'npc'}, **CAST},
            'shots': [{'lines': [0, 0], 'actors': [{'id': 'lea', 'at': [3., 1.], 'facing': '+z'}], 'actions': [], 'camera': {'shot': 'wide', 'on': ['lea']}}]}

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--names', required=True); ap.add_argument('--out', default='ps1_planche.png'); ap.add_argument('--aspect', default='16:9')
    a = ap.parse_args(); ims = []
    for n in a.names.split(','):
        ep = episode(n); lines = [{'who': 'lea', 'text': 'x', 'start': 0., 'end': 1.}]
        eng = make_engine('pixel3d', ep, lines, {}, 1.5, a.aspect); t0 = time.perf_counter(); im = eng.render_lowres(.5)[0]
        print(n, round(time.perf_counter() - t0, 2), 's'); ims.append(Image.fromarray(im))
    w, h = ims[0].size; cols = min(3, len(ims)); rows = (len(ims) + cols - 1) // cols; sh = Image.new('RGB', (w * cols, h * rows))
    for i, im in enumerate(ims): sh.paste(im, ((i % cols) * w, (i // cols) * h))
    sh = sh.resize((sh.width * 2, sh.height * 2), Image.NEAREST); sh.save(a.out); print(a.out)
