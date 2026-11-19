"""python tools/ps1_world_sheet.py --worlds station,bus --out planche.png [--cam x,y,z:lx,ly,lz] : mondes VOXEL rendus en style PS1."""
import os, sys, time, argparse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from PIL import Image
from hstudio.pipeline import make_engine

# monde -> (position de l'acteur, direction, plan) ; le plan est choisi par le directeur du studio, pas par une caméra libre
CAMS = {'station': ((1.9, -.8), '-z', 'wide'), 'bus': ((0., 5.), '-z', 'wide'), 'toit': ((0., 0.), '-z', 'wide'), 'talus': ((0., 5.), '-z', 'wide'),
        'cite': ((60., 2.), '-z', 'wide'), 'ville': ((0., -3.), '-z', 'wide'), 'parc': ((0., 1.), '-z', 'wide'), 'automne': ((0., 1.), '-z', 'wide'), 'pluie': ((0., -2.), '-z', 'wide'), 'glace': ((0., 1.), '-z', 'wide'), 'feu': ((0., 1.), '-z', 'wide'), 'bataille': ((0., 1.), '-z', 'wide'), 'invasion': ((0., -1.5), '-z', 'wide'), 'vaisseau': ((0., 0.), '-z', 'wide'), 'lune': ((0., 1.), '-z', 'wide'), 'astroport': ((130., 0.), '-z', 'wide'), 'selene': ((270., 0.), '-z', 'wide')}

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--worlds', default='station'); ap.add_argument('--out', default='ps1_worlds.png'); a = ap.parse_args(); ims = []
    for n in a.worlds.split(','):
        (ax, az), fc, sh = CAMS[n]
        ep = {'engine_version': 1, 'default_set': n, 'sets': {n: {'type': n}}, 'cast': {'x': {'preset': 'npc'}},
              'shots': [{'lines': [0, 0], 'actors': [{'id': 'x', 'at': [ax, az], 'facing': fc}], 'actions': [], 'camera': {'shot': sh, 'on': ['x']}}]}
        lines = [{'who': 'x', 'text': 'x', 'start': 0., 'end': 1.}]
        try:
            eng = make_engine('pixel3d', ep, lines, {}, 1.5, '16:9'); t0 = time.perf_counter(); ims.append(Image.fromarray(eng.render_lowres(.5)[0])); print(n, round(time.perf_counter() - t0, 1), 's')
        except Exception as e: print(n, 'ERREUR', repr(e)[:300])
    if ims:
        w, h = ims[0].size; cols = min(2, len(ims)); rows = (len(ims) + cols - 1) // cols; sh = Image.new('RGB', (w * cols, h * rows))
        for i, im in enumerate(ims): sh.paste(im, ((i % cols) * w, (i // cols) * h))
        sh.resize((sh.width * 2, sh.height * 2), Image.NEAREST).save(a.out); print(a.out)
