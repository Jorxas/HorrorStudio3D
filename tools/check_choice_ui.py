"""Offline check of the A/B/C choice card, for both engines and both aspects (no video, no API).

Why it exists: the story layer (hstudio/director/story.py) can offer 3 branches, but the two renderers used to
draw only A and B, so a C option was silently lost on screen. This check proves two things at once:
  1. NON-REGRESSION: a 2-option card renders byte-for-byte as before the change (hashes captured on the old code);
  2. the 3-option card really draws a third button, inside the canvas, for PIXEL 3D and CONSOLE, 9:16 and 16:9.

  python tools/check_choice_ui.py              # run the checks
  python tools/check_choice_ui.py --capture    # reprint the reference hashes (only when the design changes)
"""
import os, sys, hashlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from PIL import Image, ImageDraw

FAIL = []
def check(name, ok, detail=''):
    print(f"{'OK   ' if ok else 'ÉCHEC'} {name}" + (f'  ({detail})' if detail and not ok else '')); ok or FAIL.append(name)

AB  = {'title': 'TU FAIS QUOI ?', 'cursor': 'A', 'A': ['OUVRIR'], 'B': ['RECULER']}
ABC = {'title': 'TU FAIS QUOI ?', 'cursor': 'A', 'A': ['OUVRIR'], 'B': ['RECULER'], 'C': ['ATTENDRE']}

def render_pixel3d(card, aspect):
    from hstudio.engines.pixel3d.render import Pixel3DEngine, Layout
    e = object.__new__(Pixel3DEngine); e.L = Layout(aspect); e.aspect = aspect
    im = Image.new('RGB', (e.L.W, e.L.H), (0, 0, 0)); d = ImageDraw.Draw(im)
    e.choice(d, card, 0.0)
    return im

def render_console(card, aspect):
    from hstudio.engines.console.render import ConsoleEngine
    e = object.__new__(ConsoleEngine); e.aspect = aspect
    e.W, e.H = (1080, 1920) if aspect == '9:16' else (1920, 1080)
    im = Image.new('RGB', (e.W, e.H), (0, 0, 0))
    e.choice(im, card, 0.0)
    return im

RENDER = {'pixel3d': render_pixel3d, 'console': render_console}
CASES = [(eng, asp) for eng in ('pixel3d', 'console') for asp in ('9:16', '16:9')]

def h(im): return hashlib.sha256(im.tobytes()).hexdigest()[:16]

# reference hashes of the 2-option card, captured with --capture on the code BEFORE the A/B/C change
REF_AB = {
    ('pixel3d', '9:16'): 'd2ec02472164d55b',
    ('pixel3d', '16:9'): '605ef2ae7a3acb90',
    ('console', '9:16'): 'cbf3b4cafe5697a0',
    ('console', '16:9'): 'dd70715971471557',
}

def ink(im):
    """number of pixels drawn on the black canvas, and the bounding box of everything drawn"""
    import numpy as np
    a = np.asarray(im)
    return int((a.any(axis=2)).sum()), im.getbbox()

if __name__ == '__main__':
    if '--capture' in sys.argv:
        for eng, asp in CASES: print(f"    ('{eng}', '{asp}'): '{h(RENDER[eng](AB, asp))}',")
        sys.exit(0)
    for eng, asp in CASES:
        R = RENDER[eng]
        ab = R(AB, asp); abc = R(ABC, asp)
        n_ab, _ = ink(ab); n_abc, bb = ink(abc)
        check(f'{eng} {asp} : carte 2 choix inchangée', h(ab) == REF_AB[(eng, asp)], f'{h(ab)} != {REF_AB[(eng, asp)]}')
        check(f'{eng} {asp} : la carte 3 choix diffère de la carte 2 choix', h(abc) != h(ab))
        check(f'{eng} {asp} : le 3e bouton ajoute des pixels', n_abc > n_ab, f'{n_abc} <= {n_ab}')
        W, H = abc.size
        check(f'{eng} {asp} : tout est dessiné dans le cadre',
              bb is not None and bb[0] >= 0 and bb[1] >= 0 and bb[2] <= W and bb[3] <= H, str(bb))
        # the label of C really reaches the canvas (not just a layout shift)
        other = dict(ABC, C=['PARTIR'])
        check(f'{eng} {asp} : le libellé de C est bien dessiné', h(R(other, asp)) != h(abc))
        # C can be the highlighted branch (the blink cursor must be able to land on it)
        check(f'{eng} {asp} : C peut être le choix surligné', h(R(dict(ABC, cursor='C'), asp)) != h(abc))
    print()
    if FAIL: print(f'{len(FAIL)} ÉCHEC(S) : ' + ', '.join(FAIL[:10])); sys.exit(1)
    print('Tout est bon.')
