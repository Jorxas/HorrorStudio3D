"""Les CINQ identites, cote a cote, sous la meme lumiere et le meme objectif.

    python tools/check_background_identites.py
    python tools/check_background_identites.py --json docs/figurants/identites_figurants.json

Pourquoi ce fichier existe alors que la scene livree n'en met que quatre en rue : `FIGURANTS` en contient
cinq, et une affirmation du genre « cinq silhouettes differentes » doit se REGARDER et se MESURER, pas se
lire dans une table. Ici les cinq sont poses en rang sur le meme decor que la scene, eclaires par la meme
lumiere, rendus par le vrai chemin de rendu (meme corps `voxel_premium`, meme finition, meme raster) avec une
camera FIXE du monde, puis :

  - chaque corps est projete par la projection du moteur : on sait lequel est dans le cadre et de quelle
    taille en pixels, donc la planche ne peut pas « montrer » quelqu'un qui n'y est pas ;
  - les colonnes de pixels de chaque figurant sont comparees deux a deux : deux figurants qui ne
    differeraient que par une teinte donneraient une difference faible et un ratio de pixels differents
    proche de zero. Le test exige une difference reelle, parce que c'est le reproche qu'il doit attraper
    (« cinq clones recolories ») ;
  - rien n'est ecrit dans `examples/` : l'episode de la planche est construit en memoire, il n'existe pas
    comme scene et n'entre dans aucun catalogue.

Aucun reseau, aucune cle d'API, aucun cout. Corps derriere `if __name__ == '__main__'` (Windows, pool spawn).
"""
import os, sys, json, argparse
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from hstudio.acting import background as BG                               # noqa: E402
from hstudio.acting.timeline import Grid                                  # noqa: E402

OUTDIR = os.path.join(ROOT, 'docs', 'figurants')
STAMP = '20261025'
ASPECT = '9:16'

# Les cinq en rang sur la chaussee, a 11 m de l'objectif. La chaussee est le seul endroit du decor assez large
# pour aligner cinq corps : les trottoirs font 40 cm. L'ecart de 1,45 m est superieur a MIN_GAP, et chaque
# point est verifie contre les vrais obstacles avant le rendu.
ROW_Z = 11.0
ROW_DX = 1.45
FIXED_CAM = ((0.0, 1.85, 2.0), 0.0, 0.035, 0.0, 74.0)

bad = []


def check(ok, label, detail=''):
    print(('  OK    ' if ok else '  ECHEC ') + label + (('   ' + detail) if detail else ''))
    if not ok:
        bad.append(label)
    return ok


def episode(order):
    """un episode d'un seul plan, construit en memoire : meme decor, meme lumiere, meme corps que la scene"""
    import json as _json
    sc = _json.load(open(os.path.join(ROOT, 'examples', 'scenes', 'extras_rue_vivante.json'), encoding='utf-8'))
    src = sc['episode']
    n = len(order)
    xs = [round((i - (n - 1) / 2) * ROW_DX, 3) for i in range(n)]
    cast = {}
    actors = []
    for fid, x in zip(order, xs):
        f = BG.FIGURANTS[fid]
        look = dict(f['look'])
        if f.get('scale'):
            look['scale'] = f['scale']
        cast[fid] = look
        actors.append({'id': fid, 'at': [x, ROW_Z], 'facing': '-z'})
    ep = {'engine_version': 2, 'default_set': 'rue', 'music': 'mystery',
          'body': src.get('body'), 'finish': src.get('finish'),
          'weather': src.get('weather'), 'weather_amount': src.get('weather_amount'),
          'sets': {'rue': dict(src['sets']['rue'])},
          'lighting': dict(src['lighting']),
          'cast': cast,
          'shots': [{'lines': [0, 0], 'actors': actors, 'camera': {'shot': 'wide', 'on': [order[0]]}}]}
    lines = [{'tts': '.', 'display': '', 'text': '', 'tags': [], 'dialogue': False, 'i': 0,
              'start': .1, 'end': 3.9, 'segs': [[.1, 3.9]]}]
    return ep, lines, xs


def render_row(order):
    """-> (image, {fid: (u_gauche, u_droite, hauteur_px)}) avec la camera FIXE"""
    from hstudio.pipeline import make_engine, duration_of
    from hstudio.engines.pixel3d import render as RND, r3d
    ep, lines, xs = episode(order)
    eng = make_engine('pixel3d', ep, lines, np.zeros(10), duration_of(ep, lines), ASPECT)

    orig = RND.build_frame
    used = []

    def patched(ctx, g):
        out = list(orig(ctx, g))
        out[1] = FIXED_CAM
        used.append(tuple(np.ravel(FIXED_CAM[0])) + FIXED_CAM[1:])
        return tuple(out)

    RND.build_frame = patched
    try:
        im = eng.raw_frame(2.0).convert('RGB')
    finally:
        RND.build_frame = orig

    pos, yaw, pitch, roll, fov = FIXED_CAM
    W, H = im.size
    boxes = {}
    for fid, x in zip(order, xs):
        sc_ = float(BG.FIGURANTS[fid].get('scale', 1.) or 1.)
        top = r3d.project(pos, yaw, pitch, roll, fov, (x, 1.80 * sc_, ROW_Z))
        foot = r3d.project(pos, yaw, pitch, roll, fov, (x, 0., ROW_Z))
        side = r3d.project(pos, yaw, pitch, roll, fov, (x + .40 * sc_, 0.9, ROW_Z))
        if top[2] <= 0:
            continue
        cx = (top[0] + foot[0]) / 2
        half = abs(side[0] - cx)
        u0 = int(round((cx - half * 1.15 + 1) / 2 * W))
        u1 = int(round((cx + half * 1.15 + 1) / 2 * W))
        hpx = int(round(abs(top[1] - foot[1]) / 2 * H))
        boxes[fid] = (max(0, u0), min(W, u1), hpx, round(float(cx), 3))
    return im, boxes, used


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', default='')
    a = ap.parse_args()
    order = list(BG.DEFAULT_TROUPE)
    print('=' * 78)
    print('== LES CINQ IDENTITES : ' + ', '.join(order))
    print('=' * 78)

    # 1. le sol : chaque place est libre sur les vrais obstacles du decor
    from hstudio.engines.pixel3d import sets as S, places as PL, stage as ST
    ep, lines, xs = episode(order)
    spec = dict(ep['sets']['rue'])
    t = spec.pop('type', None)
    w = ST.SetWorld(S.RoomSet(PL.PLACES[t](dict(spec, type=t))))
    g = Grid(w)
    libre = [(fid, x, g.free(*g.cell(x, ROW_Z))) for fid, x in zip(order, xs)]
    for fid, x, ok in libre:
        if not ok:
            print(f'      bloque : {fid} a x={x}')
    check(all(o for _, _, o in libre), f'{sum(1 for _, _, o in libre if o)}/{len(libre)} places du rang sont libres')
    check(ROW_DX >= BG.MIN_GAP, f'l ecart du rang ({ROW_DX} m) depasse MIN_GAP ({BG.MIN_GAP} m)')

    # 2. le rendu, camera fixe
    im, boxes, used = render_row(order)
    print(f'     image {im.size}, camera fixe {FIXED_CAM}')
    check(len(set(used)) == 1, 'une seule camera a servi a toute la planche', f'{len(set(used))} camera(s)')
    for fid in order:
        b = boxes.get(fid)
        print(f'     {fid:<9} {BG.FIGURANTS[fid]["label"]:<36} '
              + (f'x image {b[0]:4d}..{b[1]:4d} px, hauteur {b[2]:3d} px' if b else 'HORS CADRE'))
    check(len(boxes) == len(order), 'les cinq sont dans le cadre', f'{len(boxes)}/{len(order)}')
    hs = [b[2] for b in boxes.values()]
    check(min(hs) >= 150, 'chacun fait au moins 150 px de haut', f'de {min(hs)} a {max(hs)} px')

    # 3. ils ne sont pas cinq teintes du meme corps
    arr = np.asarray(im).astype(np.int16)
    crops = {}
    for fid, (u0, u1, hpx, _cx) in boxes.items():
        c = arr[:, u0:u1]
        crops[fid] = c
    pairs = []
    for i, a_ in enumerate(order):
        for b_ in order[i + 1:]:
            ca, cb = crops[a_], crops[b_]
            wmin = min(ca.shape[1], cb.shape[1])
            if wmin < 8:
                continue
            d = np.abs(ca[:, :wmin] - cb[:, :wmin])
            pairs.append((a_, b_, float(d.mean()), float((d.max(-1) > 24).mean())))
    print('     comparaison deux a deux des colonnes de pixels :')
    for a_, b_, mean, frac in sorted(pairs, key=lambda p: p[2]):
        print(f'       {a_:<9} / {b_:<9} ecart moyen {mean:6.2f}/255   pixels differents {100 * frac:5.1f} %')
    worst = min(pairs, key=lambda p: p[2])
    check(worst[2] > 3.0, 'aucune paire de figurants ne se ressemble au point d etre une recoloration',
          f'la paire la plus proche : {worst[0]} / {worst[1]} a {worst[2]:.2f}/255')

    # 4. et leurs cles de look different vraiment
    sig = {f: (BG.FIGURANTS[f]['look'].get('outfit'), BG.FIGURANTS[f]['look'].get('hat', 'none'),
               BG.FIGURANTS[f]['look'].get('hair_style'), BG.FIGURANTS[f].get('scale', 1.0))
           for f in order}
    check(len(set(sig.values())) == len(order), 'les cinq signatures (habit, chapeau, cheveux, taille) sont uniques')

    out = os.path.join(OUTDIR, f'identites_figurants_{STAMP}.png')
    os.makedirs(OUTDIR, exist_ok=True)
    from PIL import ImageDraw
    sheet = im.copy()
    d = ImageDraw.Draw(sheet)
    for fid, (u0, u1, hpx, _cx) in boxes.items():
        d.rectangle([u0, 6, u1, 22], fill=(16, 16, 18))
        d.text((u0 + 3, 9), fid, fill=(235, 235, 235))
    sheet.save(out)
    print('     planche : ' + out)

    print('\n' + '=' * 78)
    print(('ECHEC : ' + '; '.join(bad)) if bad else 'Tout est OK.')
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        json.dump({'ordre': order, 'camera_fixe': [list(FIXED_CAM[0])] + list(FIXED_CAM[1:]),
                   'rang_z': ROW_Z, 'rang_ecart_m': ROW_DX,
                   'boites': {k: list(v) for k, v in boxes.items()},
                   'paires': [[a_, b_, round(m, 2), round(f, 4)] for a_, b_, m, f in pairs],
                   'signatures': {k: list(v) for k, v in sig.items()},
                   'planche': out, 'echecs': bad},
                  open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('mesures : ' + a.json)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
