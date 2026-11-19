"""Planches du lieu `phare_interieur`, du Veilleur et des objets de la suite (15/11/2026, « Le Phare qui efface », parties 2 à 4) : vraies
images PS1 9:16 rendues par le moteur (scène dirigée synthétique), une par point de vue clé, avec la luminance moyenne et la part de noir
bouché de chaque image.

    PYTHONIOENCODING=utf-8 .venv\\Scripts\\python.exe tools/phare_interieur_sheet.py [--vues entree,palier,...] [--sortie DOSSIER] [--workers 6]

Écrit <sortie>/<vue>.png (540 x 960), <sortie>/planche.jpg (et planche_2.jpg ... au-delà de 16 vues) et <sortie>/mesures.json."""
import argparse, json, math, multiprocessing as mp, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
Y = 4.2
ALMA = {'outfit': 'coat', 'hood': [46, 60, 100], 'jeans': [42, 44, 56], 'skin': [214, 172, 142], 'hair': [92, 62, 42], 'hair_style': 'short',
        'headphones': False, 'backpack': False, 'hat': 'none', 'torche': True}
NOE = {'outfit': 'hoodie', 'hood': [52, 86, 58], 'jeans': [46, 50, 64], 'skin': [206, 160, 128], 'hair': [70, 48, 32], 'hair_style': 'short',
       'headphones': False, 'backpack': False, 'hat': 'none', 'scale': .8}
VEILLEUR = {'ref': 'veilleur'}


def K(p, yaw, **kw): return dict(dict(t=0., p=list(p), yaw=yaw, face=kw.pop('face', 'neutral'), hold=kw.pop('hold', 'none')), **kw)


def toward(a, b): return math.atan2(b[0] - a[0], b[2] - a[2])


def esc(volee, s, descend=False):
    from hstudio.engines.pixel3d import phare_interieur as PI
    x, y, z, yaw = PI.escalier(volee, s, descend); return (x, y, z), yaw


TOUR = {'type': 'phare_interieur'}
# view -> (set spec, camera key, tracks, state, objects, t in the shot, fx)
def vues():
    V = {}
    (px, py, pz), pyaw = esc('haut', 5 / 17., True)
    V['entree'] = (TOUR, dict(pos=[-1.0, 1.7, -.6], look=[.1, 1.25, -4.7], fov=62.),
                   {'alma': [K((.15, 0, -3.7), 0.4, face='nervous', hold='flashlight')]}, {'porte': .35}, [], 1.0, {})
    V['entree_porte'] = (TOUR, dict(pos=[.9, 1.6, -1.4], look=[-.2, 1.2, -5.6], fov=60.),
                         {'alma': [K((-.25, 0, -4.2), math.pi, face='shocked', hold='flashlight')]}, {'porte': 1.}, [], 1.0, {})
    V['escalier_bas'] = (TOUR, dict(pos=[-.6, 1.3, -2.3], look=[-3.4, 4.6, -1.0], fov=64.),
                         {'veilleur': [K((-3.1, Y, -.6), -1.6)]}, {}, [], 1.0, {})
    V['horloge'] = (TOUR, dict(pos=[-.55, 2.1, -.9], look=[-.6, 2.0, .5], fov=36.), {}, {'horloge': 1.}, [], 1.13, {})
    (hx, hy, hz), hyaw = esc('haut', 6 / 17., True)
    V['palier'] = (TOUR, dict(pos=[-1.0, Y + 1.6, .25], look=[-.6, Y + 2.0, -3.6], fov=62.),
                   {'veilleur': [K((hx, hy, hz), hyaw, reach_l=[-.25, 1.05, .25, 1.])]}, {}, [], 1.0, {})
    V['palier_cercle'] = (TOUR, dict(pos=[.9, Y + 1.6, -1.6], look=[-2.0, Y + 1.25, -.45], fov=58.),
                          {'veilleur': [K((-2.0, Y, -.45), toward((-2.0, 0, -.45), (.9, 0, -1.6)), x_fissure=.3)]}, {}, [], 1.0, {})
    V['porte_veilleur'] = (TOUR, dict(pos=[-1.7, Y + 1.55, 3.7], look=[-2.0, Y + 1.7, .6], fov=58.),
                           {'veilleur': [K((-2.0, Y, .22), 0., x_fissure=1.)]}, {'eclairs': [.75]}, [], 1.25, {})
    V['commandes'] = (TOUR, dict(pos=[-2.6, Y + 1.75, 1.3], look=[.4, Y + 1.15, 4.0], fov=64.),
                      {'alma': [K((-.35, Y, 3.15), .05, face='nervous', hold='flashlight', head=[.2, 0.])]}, {}, [], 1.0, {})
    V['levier'] = (TOUR, dict(pos=[-.95, Y + 1.6, 2.85], look=[-.95, Y + 1.38, 4.25], fov=50.), {}, {'levier': 0.}, [], 1.0, {})
    V['fusible'] = (TOUR, dict(pos=[.95, Y + 1.5, 3.05], look=[.95, Y + 1.38, 4.25], fov=48.), {}, {}, [], 1.0, {})
    V['plaque'] = (TOUR, dict(pos=[0., Y + 1.45, 3.62], look=[0., Y + 1.42, 4.2], fov=34.), {}, {}, [], 1.0, {'expo': .55})
    V['mur_grave'] = (TOUR, dict(pos=[1.2, Y + 1.48, 3.25], look=[1.2, Y + 1.48, .8], fov=50.), {}, {}, [], 1.0, {})
    V['eclair_palier'] = (TOUR, dict(pos=[1.9, Y + 1.7, -1.3], look=[-2.6, Y + 1.5, -.9], fov=64.),
                          {'veilleur': [K((-2.0, Y, -.45), 1.4, x_fissure=0.)]}, {'eclairs': [.8]}, [], 1.0, {})
    # part 3: blackout
    V['commandes_panne'] = (TOUR, dict(pos=[1.9, Y + 1.7, 1.3], look=[-.3, Y + 1.25, 3.7], fov=62.),
                            {'alma': [K((-.45, Y, 2.95), -2.2, face='shocked', hold='flashlight')]}, {'phare': 'panne'}, [], 1.0, {})
    V['grille'] = (TOUR, dict(pos=[-1.95, Y + 1.55, 2.8], look=[-1.95, Y, 1.2], fov=54.), {}, {'phare': 'panne'}, [], 1.2, {})
    V['machines_panne'] = (TOUR, dict(pos=[2.7, 1.65, 2.8], look=[-1.8, .5, 1.5], fov=64.),
                           {'veilleur': [K((.9, 0, 1.55), -1.62, x_rampe=1.), K((.2, 0, 1.6), -1.62, x_rampe=1., t=2.)],
                            'alma': [K((-2.4, 0, 2.45), 1.75, face='shocked', hold='flashlight')]}, {'phare': 'panne'}, [], 1.0, {})
    V['batterie'] = (TOUR, dict(pos=[-1.95, .85, 3.1], look=[-1.95, .5, 1.6], fov=46.), {}, {'phare': 'panne'}, [], 1.2, {})
    V['rampe'] = (TOUR, dict(pos=[-1.1, .62, 1.95], look=[1.0, .5, 1.5], fov=56.),
                  {'veilleur': [K((1.6, 0, 1.4), -1.65, x_rampe=1.), K((.9, 0, 1.5), -1.65, x_rampe=1., t=2.)]}, {'phare': 'panne'}, [], 1.0, {})
    V['generateur'] = (TOUR, dict(pos=[.45, 1.55, 1.15], look=[.1, 1.7, 3.6], fov=62.),
                       {'noe': [K((.28, .15, 3.95), math.pi, face='nervous', reach_l=[.2, 1.2, .45, 1.])]}, {'phare': 'panne', 'cabine': .5, 'vitre': .55}, [], 1.0, {})
    V['etiquette'] = (TOUR, dict(pos=[0., 2.35, 1.05], look=[0., 2.55, 3.4], fov=54.), {}, {'phare': 'panne'}, [], 1.0, {})
    V['trou'] = (TOUR, dict(pos=[-3.55, .55, 1.95], look=[-4.9, .22, 1.3], fov=56.), {}, {'phare': 'panne'}, [], 1.0, {})
    # part 4: the generator on, the coils burnt
    V['generateur_allume'] = (TOUR, dict(pos=[-1.7, 1.6, 1.15], look=[.4, 1.3, 3.6], fov=62.),
                              {'noe': [K((.28, .15, 3.95), math.pi, face='neutral')], 'alma': [K((1.1, 0, 2.7), toward((1.1, 0, 2.7), (.28, 0, 3.95)), face='shocked', hold='flashlight')]},
                              {'phare': 'generateur', 'cabine': 1.3, 'vitre': .1}, [], 1.0, {})
    V['bobines'] = (TOUR, dict(pos=[0., 2.95, 2.0], look=[0., 3.3, 3.95], fov=52.), {}, {'phare': 'generateur', 'bobines': 'etincelles'}, [], 1.0, {})
    V['eclair_generateur'] = (TOUR, dict(pos=[1.8, 1.6, 1.0], look=[.1, 1.6, 3.6], fov=64.), {}, {'phare': 'generateur', 'eclairs': [.8], 'eclair_source': 'generateur',
                              'bobines': 'etincelles'}, [], 1.0, {})
    V['brule'] = (TOUR, dict(pos=[1.5, 1.7, 1.1], look=[0., 2.2, 3.8], fov=62.), {}, {'phare': 'brule'}, [], 1.0, {})
    V['torche'] = (TOUR, dict(pos=[2.4, Y + 1.65, 1.0], look=[-1.2, Y + 1.15, 3.2], fov=62.),
                   {'alma': [K((-1.6, Y, 2.2), .55, face='nervous', hold='flashlight')]}, {'phare': 'panne'}, [], 1.0, {})
    # part 4 outside (place phare_foret): the dead lantern, Alma's house and its threshold, the held hand (smooth palm), the car radio
    V['foret_phare_eteint'] = ({'type': 'phare_foret', 'lanterne': 'eteinte'}, dict(pos=[3.4, 1.75, -7.0], look=[9.0, 8.0, 34.0], fov=64.), {}, {}, [], 1.0, {})
    MA = {'type': 'phare_foret', 'maison_alma': True, 'voiture': {'radio': True}, 'lanterne': 'eteinte'}
    V['foret_seuil'] = (MA, dict(pos=[2.5, 1.55, 109.4], look=[6.6, 1.35, 112.0], fov=58.),
                        {'alma': [K((6.25, .6, 111.65), toward((6.25, 0, 111.65), (6.45, 0, 112.4)), face='nervous', hold='flashlight')],
                         'noe': [K((6.45, .6, 112.4), toward((6.45, 0, 112.4), (6.25, 0, 111.65)), face='happy')]}, {}, [], 1.0, {})
    V['foret_mains'] = (dict(MA, mains_tenues={'cicatrice': False}), dict(pos=[6.35, 2.1, 111.12], look=[6.35, 1.6, 111.52], fov=34.), {}, {}, [], 1.0, {'expo': .6})
    V['foret_mains_cicatrice'] = (dict(MA, mains_tenues={'cicatrice': True}), dict(pos=[6.35, 2.1, 111.12], look=[6.35, 1.6, 111.52], fov=34.), {}, {}, [], 1.0, {'expo': .6})
    V['foret_radio'] = (MA, dict(pos=[5.6, 1.02, 105.88], look=[5.5, .6, 106.6], fov=46.), {}, {'radio': 1.}, [], 1.0, {})
    # the Veilleur on his own (character sheet)
    V['veilleur_face'] = (TOUR, dict(pos=[-.6, 1.5, -.6], look=[-.6, 1.4, -3.6], fov=58.), {'veilleur': [K((-.6, 0, -3.0), 0.)]}, {}, [], 1.0, {})
    V['veilleur_fissure'] = (TOUR, dict(pos=[-.6, 2.15, -1.9], look=[-.6, 2.1, -3.0], fov=34.), {'veilleur': [K((-.6, 0, -3.0), 0., x_fissure=1.)]}, {}, [], 1.0, {})
    V['veilleur_profil'] = (TOUR, dict(pos=[1.5, 1.4, -2.4], look=[-1.2, 1.2, -2.4], fov=60.),
                            {'veilleur': [K((-1.8, 0, -2.4), math.pi / 2, gesture='none'), K((-.6, 0, -2.4), math.pi / 2, t=1.5)]}, {}, [], .9, {})
    return V


def episode(view):
    over, cam, tracks, state, objs, _, fx = VUES[view]
    spec = dict(over)
    if not tracks: tracks = {'_x': [dict(t=0., p=[0., 0., -60.], yaw=0., vis=0, face='neutral', hold='none')]}
    shot = {'lines': [0, 0], 'set': 'lieu', 'camera': {'rig': 'path', 'keys': [dict(t=0., **cam), dict(t=50., **cam)]}, 'state': state,
            'tracks': tracks, 'fx': dict(fx), 'ui': {'hud': False, 'subs': 'off'}, 'objects': objs}
    ep = {'style': 'pixel3d', 'profile': 'production', 'genre': 'horror', 'music': 'none', 'title': 'LE PHARE QUI EFFACE',
          'hud': {'title': ['LE PHARE', 'QUI EFFACE'], 'part': '', 'hearts': []}, 'sets': {'lieu': spec}, 'default_set': 'lieu',
          'cast': {'alma': ALMA, 'noe': NOE, 'veilleur': VEILLEUR}, 'grade': {'saturation': .82, 'exposure': 1.2},
          'diversite': False, 'shots': [shot], 'duration': 4.0}
    lines = [{'start': .1, 'end': 3.9, 'text': ' ', 'speaker': 'narrateur', 'tone': 'serious'}]
    return ep, lines


VUES = vues()


def render(args):
    view, w, h = args
    os.chdir(ROOT)
    from hstudio.pipeline import make_engine
    from PIL import Image
    ep, lines = episode(view); t = VUES[view][5]
    eng = make_engine('pixel3d', ep, lines, np.zeros(400, np.float32), ep['duration'], '9:16')
    eng.frame(max(0., t - .5)); t0 = time.time(); im = eng.frame(t).convert('RGB'); dt = time.time() - t0
    a = np.asarray(im, np.float32); lum = (a * np.array([.299, .587, .114], np.float32)).sum(-1)
    return view, np.asarray(im.resize((w, h), Image.BILINEAR), np.uint8), dict(luminance=round(float(lum.mean()), 1), noir=round(float((lum < 18).mean()), 3),
                                                                             blanc=round(float((lum > 245).mean()), 3), secondes=round(dt, 1))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--vues', default=','.join(VUES)); ap.add_argument('--sortie', default=os.path.join(ROOT, 'docs', 'catalogue', 'phare_interieur'))
    ap.add_argument('--workers', type=int, default=6); a = ap.parse_args()
    from PIL import Image, ImageDraw
    views = [v for v in a.vues.split(',') if v in VUES]; os.makedirs(a.sortie, exist_ok=True)
    with mp.Pool(max(1, min(6, a.workers, len(views)))) as pool:
        res = pool.map(render, [(v, 540, 960) for v in views], chunksize=1)
    mp_ = os.path.join(a.sortie, 'mesures.json')
    meas = json.load(open(mp_, encoding='utf-8')) if os.path.exists(mp_) else {}
    for v, img, m in res:
        Image.fromarray(img).save(os.path.join(a.sortie, f'{v}.png')); meas[v] = m; print(v, m)
    allv = [v for v in VUES if os.path.exists(os.path.join(a.sortie, f'{v}.png'))]
    for page in range(0, len(allv), 16):
        chunk = allv[page:page + 16]; cols = min(4, len(chunk)); rows = (len(chunk) + cols - 1) // cols; tw, th = 270, 480
        sheet = Image.new('RGB', (cols * tw, rows * (th + 18)), (12, 12, 14)); d = ImageDraw.Draw(sheet)
        for k, v in enumerate(chunk):
            x, y = (k % cols) * tw, (k // cols) * (th + 18); m = meas.get(v, {})
            sheet.paste(Image.open(os.path.join(a.sortie, f'{v}.png')).resize((tw, th), Image.BILINEAR), (x, y + 18))
            d.text((x + 4, y + 3), f"{v}  L{m.get('luminance', 0):.0f} noir {m.get('noir', 0) * 100:.0f}%", fill=(230, 230, 220))
        sheet.save(os.path.join(a.sortie, 'planche.jpg' if page == 0 else f'planche_{page // 16 + 1}.jpg'), quality=90)
    with open(mp_, 'w', encoding='utf-8') as f: json.dump(meas, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
