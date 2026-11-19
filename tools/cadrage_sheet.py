"""Planche avant / apres du cadrage, aux MEMES instants, en pleine image, sans recadrage ni zoom.

    python tools/cadrage_sheet.py examples/demos/demo6_continuite.json docs/p1_visuel/avant_apres_demo6.png
    python tools/cadrage_sheet.py examples/demos/demo20_decors.json out.png --at 9.86,17.02,30.5,38.53

Une ligne par etage de la pile d'options, pour qu'on voie qui apporte quoi :
`defaut` -> `camera_face_track` (option existante) -> `+ camera_clear_face` (option de ce lot)
-> `+ visage et cheveux expressifs` (options existantes, cote personnage).

Les instants sont choisis sur le defaut : ce sont les pires moments mesures par `tools/cadrage_qc.py` (la part
d'image prise par le bras du sujet), un par plan serre. On ne choisit donc pas les images qui arrangent.

Aucun reseau, aucune cle, aucun ffmpeg.
"""
import os, sys, argparse
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

EXPR = [('face_detail', 'hd'), ('detail', True), ('hair2', [150, 96, 58]), ('iris', [96, 140, 120])]
STEPS = [('A  defaut', [], []),
         ('B  camera_face_track (option existante)', [('camera_face_track', True)], []),
         ('C  + camera_clear_face (ce lot)', [('camera_clear_face', True)], []),
         ('D  + visage et cheveux expressifs', [('camera_clear_face', True)], EXPR)]


def worst_times(scene, aspect, every, n):
    """les pires instants du rendu par defaut : un par plan serre, celui ou le bras prend le plus d'image"""
    from cadrage_qc import build, measure, TIGHT
    ep, lines, eng = build(scene, aspect, [], [])
    rows = [r for r in measure(eng.ctx, lines[-1]['end'], every) if r['kind'] in TIGHT]
    best = {}
    for r in rows:
        if r['bras'] > best.get(r['shot'], (0., 0.))[0]: best[r['shot']] = (r['bras'], r['t'])
    out = [t for _, t in sorted(best.values(), reverse=True)[:n]]
    return sorted(out) or [lines[-1]['end'] * .5]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('scene'); ap.add_argument('out')
    ap.add_argument('--aspect', default='9:16'); ap.add_argument('--every', type=float, default=.5)
    ap.add_argument('--at', default=''); ap.add_argument('--shots', type=int, default=4)
    ap.add_argument('--height', type=int, default=420)
    a = ap.parse_args()
    from cadrage_qc import build
    times = [float(x) for x in a.at.split(',') if x.strip()] or worst_times(a.scene, a.aspect, a.every, a.shots)
    print('instants (les pires du rendu par defaut) :', times)
    rows = []
    for lbl, eks, cks in STEPS:
        ep, lines, eng = build(a.scene, a.aspect, eks, cks)
        rows.append((lbl, [eng.frame(float(t)) for t in times]))
        print('  rendu', lbl)
    h = a.height
    sc = [[im.resize((int(im.size[0] * h / im.size[1]), h)) for im in ims] for _, ims in rows]
    W = sum(i.size[0] for i in sc[0]); band = 24
    out = Image.new('RGB', (W, (h + band) * len(rows)), (16, 16, 18)); y = 0
    for (lbl, _), ims in zip(rows, sc):
        d = ImageDraw.Draw(out); d.text((6, y + 6), lbl, fill=(255, 220, 120)); y += band
        x = 0
        for im, t in zip(ims, times):
            out.paste(im, (x, y)); ImageDraw.Draw(out).text((x + 5, y + 4), f'{t:.2f}s', fill=(255, 255, 0)); x += im.size[0]
        y += h
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    out.save(a.out); print('ecrit', a.out, out.size)


if __name__ == '__main__': main()
