"""Style PS1 : les mondes qui n'existaient que dans VOXEL (station-service, bus de nuit, toit du bus, talus, cité, astroport, surface de la Lune).

La géométrie vient de VOXEL lui-même : `voxelgpu_js/dump_world_boxes.js` construit le monde dans le moteur et écrit ses boîtes dans `ps1_worlds/raw/<monde>.json`
(centre, taille, couleur moyenne, émission, en repère local du monde). Ici chaque boîte devient un bloc PS1 (`blocks` de RoomSet) : même plan, mêmes dimensions dans les deux styles.
VOXEL regarde vers -z, PS1 vers +z : le z est inversé (un plan écrit pour l'un se lit à l'envers dans l'autre sans cette inversion).
Perdu à la conversion : les images collées sur les faces (texte d'une enseigne, affiche) deviennent leur couleur moyenne ; les reflets de l'eau et de l'asphalte mouillé sont ceux du sol PS1."""
import os, json, functools

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ps1_worlds', 'raw')
MAX_LIGHTS = 10
LIGHT_K = .3
FLOOR = (58, 60, 66)

# monde -> réglages du lieu PS1 (ciel, météo, sol) ; les bornes viennent de voxelgpu/worlds.py
LOOK = {
    'station':   dict(sky='night', stars=True, weather='rain', ground='asphalt', wet=True, fog=.03, ambience='rain', ambient=(.05, .055, .09), fill=.2),
    'bus':       dict(sky='night', ground='concrete', fog=.03, ambience='night', ambient=(.10, .09, .11), fill=.2),
    'toit':      dict(sky='night', stars=True, weather='rain', ground='water', ground_y=-1.2, walkable=[{'rect': [-6.5, -1.4, 6.5, 1.4], 'y': 0.}], fog=.02, ambience='rain', fill=.22),
    'talus':     dict(sky='night', stars=True, weather='rain', ground='grass', wet=True, fog=.02, ambience='rain', fill=.22),
    'cite':      dict(sky='day', ground='asphalt', fog=.012, ambience='city'),
    'astroport': dict(sky='day', ground='concrete', fog=.01, ambience='wind'),
    'selene':    dict(sky='night', ground='sand', fog=.004, stars=True, ambience='wind', fill=.22),
    # les dix mondes de base de VOXEL, extraits de la même façon (plus d'approximation par un autre lieu PS1)
    'ville':     dict(sky='day', ground='asphalt', fog=.012, ambience='city', ambient=(.32, .34, .38), fill=.6),
    'parc':      dict(sky='day', ground='grass', fog=.01, ambience='wind'),
    'automne':   dict(sky='sunset', ground='grass', fog=.012, ambience='wind'),
    'pluie':     dict(sky='night', weather='rain', wet=True, ground='asphalt', fog=.02, ambience='rain', ambient=(.12, .13, .2), fill=.5),
    'glace':     dict(sky='day', weather='snow', ground='snow', fog=.012, ambience='wind'),
    'feu':       dict(sky='night', ground='concrete', fog=.02, ambience='wind', fill=.3),
    'bataille':  dict(sky='overcast', ground='grass', fog=.012, ambience='wind'),
    'invasion':  dict(sky='sunset', ground='sand', fog=.012, ambience='wind', ambient=(.2, .17, .15), fill=.4),
    'vaisseau':  dict(sky='night', ground='concrete', fog=.02, ambience='room', ambient=(.3, .32, .4), fill=.8),
    'lune':      dict(sky='night', ground='sand', fog=.004, stars=True, ambience='wind', fill=.22),
}
MAX_BLOCKS = 1500                          # au-delà, les plus petites boîtes (feuillage, détails) sont retirées : le coût d'un rayon est proportionnel au nombre de boîtes


@functools.lru_cache(maxsize=8)
def raw(name):
    with open(os.path.join(RAW, name + '.json'), encoding='utf-8') as f: return json.load(f)


def blocks_of(name, flip=True):
    """boîtes du monde en `blocks` PS1 ; la liste des lumières est celle des plus fortes boîtes émissives"""
    out = []; glow = []
    for lo, hi, rgb, em in raw(name)['boxes']:
        w, h, d = hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]
        if max(w, d) > 60: continue                                    # le sol, la route : le sol PS1 s'en charge
        h = max(h, .03); cx, cz = (lo[0] + hi[0]) / 2., (lo[2] + hi[2]) / 2.
        if list(rgb) == [255, 255, 255] and em == 0.: rgb = FLOOR if (hi[1] - lo[1]) < .1 else rgb            # matière sans couleur propre (sol brillant, route mouillée) : un sol sombre
        b = {'at': [round(cx, 3), round(lo[1], 3), round(-cz if flip else cz, 3)], 'size': [round(max(w, .03), 3), round(h, 3), round(max(d, .03), 3)], 'color': list(rgb), 'no_shadow': em > 0.}
        if em > .3: b['emissive'] = round(min(2.5, em), 2)
        out.append(b)
        if em >= 1.: glow.append((em * max(w * d, .01), len(out) - 1))
    if len(out) > MAX_BLOCKS:
        keep = sorted(range(len(out)), key=lambda i: -(out[i]['size'][0] * out[i]['size'][1] * out[i]['size'][2] + (5. if out[i].get('emissive') else 0.)))[:MAX_BLOCKS]
        keep = sorted(keep); remap = {i: k for k, i in enumerate(keep)}; out = [out[i] for i in keep]; glow = [(g, remap[i]) for g, i in glow if i in remap]
    for _, i in sorted(glow, reverse=True)[:MAX_LIGHTS]:
        b = out[i]; b['light'] = LIGHT_K; b['light_radius'] = 5.; b['light_color'] = tuple(round(c / 255., 2) for c in b['color'])
    return out


def place(name, spec):
    """spec d'un lieu PS1 pour le monde VOXEL `name`"""
    from ...voxelgpu.worlds import WORLDS
    x0, z0, x1, z1 = WORLDS[name]['bounds']; cx, cz = (x0 + x1) / 2., -(z0 + z1) / 2.
    ys = sorted([-z0, -z1]); near, far = ys[0], ys[1]
    a = dict(LOOK[name]); o = {'type': 'room', 'generated': True, 'outdoor': True, 'textured_ground': True, 'rooms': [], 'props': [], 'zones': [], 'fill': .45, 'blocks': blocks_of(name),
                                'anchors': {'centre': (round(cx, 2), round(cz, 2)), 'devant': (round(cx, 2), round(near + .6, 2)), 'fond': (round(cx, 2), round(far - .6, 2)),
                                            'gauche': (round(x0 + .6, 2), round(cz, 2)), 'droite': (round(x1 - .6, 2), round(cz, 2))}}
    o.update(a)
    for k in ('sky', 'weather', 'fog', 'seed', 'stars', 'ambience', 'wet', 'ground'):
        if k in spec: o[k] = spec[k]
    o['blocks'] = o['blocks'] + list(spec.get('blocks', [])); o['props'] = o['props'] + list(spec.get('props', []))
    if spec.get('anchors'): o['anchors'] = dict(o['anchors'], **spec['anchors'])
    return o


# mondes de VOXEL sans équivalent exact en PS1 : le lieu PS1 le plus proche, avec le ciel et la météo du monde (statut « approx » dans le registre)
ALIAS = {
    'ville': ('city_street', dict(sky='day')), 'parc': ('park', dict(sky='day')), 'automne': ('park', dict(sky='sunset')),
    'pluie': ('city_street', dict(sky='night', weather='rain', wet=True)), 'glace': ('snowy_forest', dict(weather='snow')),
    'feu': ('volcano', {}), 'bataille': ('countryside', dict(sky='overcast')), 'invasion': ('desert', dict(sky='sunset')),
    'vaisseau': ('space_station', {}), 'lune': ('mountain', dict(sky='night', stars=True, snow=False)),
}


def register(PLACES):
    base = dict(PLACES)
    for n in LOOK:
        if os.path.exists(os.path.join(RAW, n + '.json')): PLACES[n] = (lambda nm: (lambda spec: place(nm, spec)))(n)
    for n, (target, over) in ALIAS.items():
        if n not in PLACES and target in base: PLACES[n] = (lambda t, o: (lambda spec: base[t](dict(o, **(spec or {})))))(target, over)
