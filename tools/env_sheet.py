"""La planche qui isole les facades : MEME scene, MEME instant, MEME cadrage, seule la cle « env » change.

    python tools/env_sheet.py docs/p1_decor/facades_rue.png
    python tools/env_sheet.py docs/p1_decor/facades_rue.png --at 1.2 --zoom 0.42

POURQUOI UNE PLANCHE DE PLUS. Les deux videos A/B du lot empilent trois cles (`env`, `finish`, `body`) parce
que le proprietaire a demande a voir l'ENSEMBLE. Elles ne disent donc pas ce que les facades apportent
SEULES. Cette planche le dit : les deux lignes partagent tout -- meme raster, meme corps, meme lumiere, meme
camera, meme seconde -- et ne different que par `env`. Si la difference ne se voit pas ici, elle n'existe
pas, et aucune video ne la fera apparaitre.

Deux rangees :
  - en haut, l'image entiere, pour juger la coherence du decor et de la lumiere ;
  - en bas, le MEME recadrage dans les deux colonnes, agrandi au plus proche voisin, pour que les
    encadrements, les appuis, les meneaux, les portes et les tuyaux soient lisibles au lieu d'etre devines.

Le recadrage n'est pas choisi a la main : c'est la zone ou les deux images different le plus, mesuree.
On ne choisit donc pas l'endroit qui arrange.

Aucun reseau, aucune cle d'API, aucun ffmpeg. Deterministe.
"""
import os, sys, argparse
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

from PIL import Image, ImageDraw                                            # noqa: E402

SCENE = os.path.join(ROOT, 'examples', 'scenes', 'rue_entree.json')
# tout est partage sauf `env` : c'est la seule facon de montrer ce que les facades valent seules
BASE = [('finish', 'net_rapide'), ('body', 'minecraft')]
ROWS = [('A  sans les facades detaillees  (cle "env" absente)', BASE),
        ('B  avec  "env": "riche"  --  SEULE cle qui change', BASE + [('env', 'riche')])]


def worst_window(a, b, frac):
    """le rectangle de taille `frac` ou les deux images different le plus (somme glissante, pas de choix)"""
    d = np.abs(a.astype(np.int32) - b.astype(np.int32)).sum(2)
    h, w = d.shape
    wh, ww = int(h * frac), int(w * frac)
    if wh < 8 or ww < 8: return (0, 0, w, h)
    ii = d.cumsum(0).cumsum(1)
    ii = np.pad(ii, ((1, 0), (1, 0)))
    best, pos = -1, (0, 0)
    step = max(8, min(wh, ww) // 6)
    for y in range(0, h - wh + 1, step):
        for x in range(0, w - ww + 1, step):
            s = ii[y + wh, x + ww] - ii[y, x + ww] - ii[y + wh, x] + ii[y, x]
            if s > best: best, pos = s, (x, y)
    return (pos[0], pos[1], pos[0] + ww, pos[1] + wh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--scene', default=SCENE)
    ap.add_argument('--at', type=float, default=1.2)
    ap.add_argument('--zoom', type=float, default=.36, help='part de l\'image prise par le recadrage du bas')
    ap.add_argument('--width', type=int, default=520, help='largeur d\'une colonne dans la planche')
    a = ap.parse_args()
    from cadrage_qc import build

    ims = []
    for lbl, keys in ROWS:
        _, _, eng = build(a.scene, '9:16', list(keys))
        ims.append((lbl, eng.frame(a.at).convert('RGB')))
    pix = [np.asarray(im) for _, im in ims]
    diff = int((np.abs(pix[0].astype(np.int16) - pix[1].astype(np.int16)).sum(2) > 0).sum())
    box = worst_window(pix[0], pix[1], a.zoom)
    print('instant %.2f s, %d pixels different sur %d (%.1f %%)'
          % (a.at, diff, pix[0].shape[0] * pix[0].shape[1],
             100. * diff / (pix[0].shape[0] * pix[0].shape[1])))
    print('recadrage retenu (la ou les deux images different le plus) :', box)

    W = a.width
    H = int(W * ims[0][1].height / ims[0][1].width)
    cw, chh = box[2] - box[0], box[3] - box[1]
    ZH = int(W * chh / cw)
    band = 26
    sheet = Image.new('RGB', (W * 2, band + H + band + ZH), (14, 14, 16))
    d = ImageDraw.Draw(sheet)
    for i, (lbl, im) in enumerate(ims):
        d.text((i * W + 6, 6), lbl, fill=(255, 220, 120))
        sheet.paste(im.resize((W, H), Image.LANCZOS), (i * W, band))
        # le cadre du recadrage, dessine sur l'image entiere, pour qu'on sache d'ou vient le zoom
        sc = W / im.width
        d.rectangle([i * W + box[0] * sc, band + box[1] * sc, i * W + box[2] * sc, band + box[3] * sc],
                    outline=(0, 255, 160), width=2)
    y2 = band + H
    d.text((6, y2 + 6), 'le MEME recadrage, agrandi : encadrements, appuis, meneaux, portes, tuyaux',
           fill=(255, 220, 120))
    for i, (lbl, im) in enumerate(ims):
        sheet.paste(im.crop(box).resize((W, ZH), Image.NEAREST), (i * W, y2 + band))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    sheet.save(a.out)
    print('ecrit', a.out, sheet.size)
    return 0


if __name__ == '__main__': sys.exit(main())
