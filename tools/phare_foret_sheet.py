"""Planches du lieu `phare_foret` (14/11/2026) : vraies images PS1 9:16 rendues par le moteur (scène dirigée synthétique), une par point de vue clé,
avec la luminance moyenne et la part de noir bouché de chaque image.

    PYTHONIOENCODING=utf-8 .venv\\Scripts\\python.exe tools/phare_foret_sheet.py [--vues route,habitacle,...] [--sortie DOSSIER] [--workers 6]

Écrit <sortie>/<vue>.png (540 x 960), <sortie>/planche.jpg et <sortie>/mesures.json."""
import argparse, json, math, multiprocessing as mp, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
W_ = -math.pi / 2; E_ = math.pi / 2
ALMA = {'outfit': 'coat', 'hood': [46, 60, 100], 'jeans': [42, 44, 56], 'skin': [214, 172, 142], 'hair': [92, 62, 42], 'hair_style': 'short',
        'headphones': False, 'backpack': False, 'hat': 'none'}
NOE = {'outfit': 'hoodie', 'hood': [52, 86, 58], 'jeans': [46, 50, 64], 'skin': [206, 160, 128], 'hair': [70, 48, 32], 'hair_style': 'short',
       'headphones': False, 'backpack': False, 'hat': 'none', 'scale': .8}
SIL = {'outfit': 'coat', 'hood': [22, 24, 30], 'jeans': [20, 22, 28], 'skin': [70, 74, 86], 'hair': [16, 16, 20], 'headphones': False, 'backpack': False, 'face_fade': .8}

# view -> (set spec overrides, camera key(s), tracks, state, objects, t in the shot)
def K(p, yaw, **kw): return dict(dict(t=0., p=list(p), yaw=yaw, face=kw.pop('face', 'neutral'), hold=kw.pop('hold', 'none')), **kw)
VUES = {
    'route': ({}, dict(pos=[3.4, 1.75, -7.0], look=[9.0, 8.0, 34.0], fov=64.),
              {'alma': [K((-.5, 0, .4), 0.3, face='scared')]}, {'faisceau_angle': -152., 'faisceau_pente': 22.}, [], 1.0),
    'route_large': ({}, dict(pos=[-1.2, 2.3, -24.0], look=[5.0, 7.0, 40.0], fov=60.),
                    {}, {'faisceau_angle': -120., 'faisceau_pente': 14.}, [], 1.0),
    'habitacle': ({}, dict(pos=[3.7, 1.35, .35], look=[1.0, 1.05, .1], fov=46.),
                  {'alma': [K((1.0, 0, .15), 0., sit=1, face='scared', head=[.35, .05])]}, {'faisceau_angle': -150., 'faisceau_pente': 22.}, [], 1.0),
    'ecran': ({}, dict(pos=[1.5, 1.02, -.12], look=[1.4, .79, .6], fov=46.),
              {'alma': [K((1.0, 0, .15), 0., sit=1, face='scared', vis=0)]}, {'faisceau': 0}, [], 1.0),
    'lanterne': ({}, dict(pos=[1.7, 1.25, .45], look=[16.0, 21.3, 32.85], fov=6.5),
                 {'noe': [K((16.0, 20.2, 32.85), math.pi, face='scared', gesture='stop', gw=1.0)]}, {'faisceau_angle': 30., 'faisceau_pente': 6.}, [], 1.0),
    'cabane': ({}, dict(pos=[-1.0, 1.6, 6.0], look=[-8.4, 1.8, 14.0], fov=56.),
               {}, {'faisceau_angle': -129., 'faisceau_pente': 30.}, [], 1.0),
    'cabane_effacement': ({}, dict(pos=[-1.0, 1.6, 6.0], look=[-8.4, 1.8, 14.0], fov=56.),
                          {}, {'faisceau_angle': -129., 'faisceau_pente': 30.}, [{'type': 'effacement', 'target': 'cabane', 'at': 0.5, 'dur': 1.0}], 1.0),
    'cabane_effacee': ({'cabane': 'effacee'}, dict(pos=[-1.0, 1.6, 6.0], look=[-8.4, 1.8, 14.0], fov=56.),
                       {}, {'faisceau_angle': -100., 'faisceau_pente': 18.}, [], 1.0),
    'boulangerie': ({}, dict(pos=[.4, 1.7, 46.5], look=[7.2, 2.6, 56.0], fov=58.),
                    {}, {'faisceau_angle': -60., 'faisceau_pente': 10.}, [], 1.0),
    'boulangerie_effacee': ({'cabane': 'effacee', 'boulangerie': 'effacee'}, dict(pos=[.4, 1.7, 46.5], look=[7.2, 2.0, 56.0], fov=58.),
                            {'sil1': [K((7.0, 0, 54.6), W_, gesture='knock', gw=1.)], 'sil2': [K((7.1, 0, 56.4), W_, gesture='stop', gw=1.)],
                             'sil3': [K((7.4, 0, 58.0), W_, gesture='knock', gw=1.)]}, {'faisceau_angle': -18., 'faisceau_pente': 30.}, [], 1.0),
    'village': ({}, dict(pos=[-1.6, 1.7, 33.0], look=[3.5, 2.6, 62.0], fov=56.), {}, {'faisceau_angle': 60., 'faisceau_pente': 8.}, [], 1.0),
    'traces': ({}, dict(pos=[10.6, 1.5, 36.4], look=[16.5, .1, 27.5], fov=58.), {}, {'faisceau_angle': 120., 'faisceau_pente': 8.}, [], 1.0),
    'pied_tour': ({}, dict(pos=[7.6, 1.8, 29.6], look=[14.0, 1.2, 32.4], fov=62.),
                  {'alma': [K((11.7, 0, 32.6), 1.2, face='scared')]}, {'faisceau_angle': 40., 'faisceau_pente': 6.}, [], 1.0),
}


def episode(view):
    over, cam, tracks, state, objs, _ = VUES[view]
    spec = dict({'type': 'phare_foret'}, **over)
    if not tracks: tracks = {'_x': [dict(t=0., p=[0., 0., -60.], yaw=0., vis=0, face='neutral', hold='none')]}
    shot = {'lines': [0, 0], 'set': 'lieu', 'camera': {'rig': 'path', 'keys': [dict(t=0., **cam), dict(t=50., **cam)]}, 'state': state,
            'tracks': tracks, 'fx': {}, 'ui': {'hud': False, 'subs': 'off'}, 'objects': objs}
    ep = {'style': 'pixel3d', 'profile': 'production', 'genre': 'horror', 'music': 'none', 'title': 'LE PHARE QUI EFFACE',
          'hud': {'title': ['LE PHARE', 'QUI EFFACE'], 'part': '', 'hearts': []}, 'sets': {'lieu': spec}, 'default_set': 'lieu',
          'cast': {'alma': ALMA, 'noe': NOE, 'sil1': SIL, 'sil2': SIL, 'sil3': SIL}, 'grade': {'saturation': .82, 'exposure': 1.2},
          'diversite': False, 'shots': [shot], 'duration': 4.0}
    lines = [{'start': .1, 'end': 3.9, 'text': ' ', 'speaker': 'narrateur', 'tone': 'serious'}]
    return ep, lines


def render(args):
    view, w, h = args
    os.chdir(ROOT)
    from hstudio.pipeline import make_engine
    from PIL import Image
    ep, lines = episode(view); t = VUES[view][5]
    eng = make_engine('pixel3d', ep, lines, np.zeros(400, np.float32), ep['duration'], '9:16')
    eng.frame(t - .5); t0 = time.time(); im = eng.frame(t).convert('RGB'); dt = time.time() - t0
    a = np.asarray(im, np.float32); lum = (a * np.array([.299, .587, .114], np.float32)).sum(-1)
    return view, np.asarray(im.resize((w, h), Image.BILINEAR), np.uint8), dict(luminance=round(float(lum.mean()), 1), noir=round(float((lum < 18).mean()), 3), secondes=round(dt, 1))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--vues', default=','.join(VUES)); ap.add_argument('--sortie', default=os.path.join(ROOT, 'docs', 'catalogue', 'phare_foret'))
    ap.add_argument('--workers', type=int, default=6); a = ap.parse_args()
    from PIL import Image, ImageDraw
    views = [v for v in a.vues.split(',') if v in VUES]; os.makedirs(a.sortie, exist_ok=True)
    with mp.Pool(max(1, min(6, a.workers, len(views)))) as pool:
        res = pool.map(render, [(v, 540, 960) for v in views], chunksize=1)
    meas = {}
    for v, img, m in res:
        Image.fromarray(img).save(os.path.join(a.sortie, f'{v}.png')); meas[v] = m; print(v, m)
    cols = min(4, len(res)); rows = (len(res) + cols - 1) // cols; tw, th = 270, 480
    sheet = Image.new('RGB', (cols * tw, rows * (th + 18)), (12, 12, 14)); d = ImageDraw.Draw(sheet)
    for k, (v, img, m) in enumerate(res):
        x, y = (k % cols) * tw, (k // cols) * (th + 18)
        sheet.paste(Image.fromarray(img).resize((tw, th), Image.BILINEAR), (x, y + 18)); d.text((x + 4, y + 3), f"{v}  L{m['luminance']:.0f} noir {m['noir'] * 100:.0f}%", fill=(230, 230, 220))
    sheet.save(os.path.join(a.sortie, 'planche.jpg'), quality=90)
    with open(os.path.join(a.sortie, 'mesures.json'), 'w', encoding='utf-8') as f: json.dump(meas, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
