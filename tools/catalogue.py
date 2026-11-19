"""Contact sheets of the pixel3d body language (docs/catalogue/*.png): expressions, gestures, postures, held
objects, looks, outdoor skies. Run after adding an expression or a gesture:  python tools/catalogue.py [all|faces|...]"""
import sys, os, json, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from hstudio.engines.pixel3d import r3d, poses as P, assets as A
from hstudio.engines.pixel3d.render import Pixel3DEngine
from hstudio import paths
LINES = [{'tts': '.', 'display': '.', 'text': '.', 'tags': [], 'dialogue': False, 'i': 0, 'start': 0.0, 'end': 3.0, 'segs': [[0.0, 3.0]]}]
OUT = os.path.join(ROOT, 'docs', 'catalogue'); os.makedirs(OUT, exist_ok=True)
ROOM = {'type': 'room', 'fog': .01, 'rooms': [{'id': 'r', 'origin': [0, 0], 'size': [6, 6], 'walls': 'plaster', 'wall_color': [96, 104, 132],
        'floor': 'wood', 'light': 'neon', 'light_power': 1.5}]}
GRADE = {'saturation': .95, 'exposure': 1.0}

def set_res(rw, rh, fov_k):
    """le catalogue dessine des vignettes a sa propre taille : il passe par r3d.set_raster pour que le
    registre du raster reste vrai (sinon un r3d.configure() suivant se croit deja a jour et ne fait rien)"""
    r3d.set_raster(rw, rh, fov_k)

def shot_img(actor, cam, rw=120, rh=144, extra=None, t=1.0, cast=None, sets=None):
    sp = json.loads(json.dumps(ROOM))
    if extra: sp['rooms'][0]['props'] = extra
    ep = {'style': 'pixel3d', 'default_set': 'r', 'sets': {'r': sp}, 'hud': {}, 'grade': GRADE, 'cast': cast or {'hero': {}},
          'state': {}, 'lines': {}, 'shots': [{'lines': [0, 0], 'camera': cam, 'actors': [actor],
                                               'lights': [{'at': [.8, 2.2, 3.4], 'color': [1, .95, .9], 'power': .8, 'radius': 3}]}]}
    eng = Pixel3DEngine(ep, LINES, np.zeros(10), 4.0, '9:16'); set_res(rw, rh, 1.0)
    return Image.fromarray(eng.render_lowres(t)[0])

FONT = ImageFont.truetype(paths.FONT_MONTSERRAT, 15)
def sheet(items, cols, scale, name, title):
    tiles = []
    for label, im in items:
        im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
        t = Image.new('RGB', (im.width, im.height + 26), (20, 20, 26)); t.paste(im, (0, 0))
        d = ImageDraw.Draw(t); d.text((t.width / 2, im.height + 4), label, font=FONT, fill=(240, 236, 220), anchor='ma'); tiles.append(t)
    tw, th = tiles[0].size; rows = (len(tiles) + cols - 1) // cols
    sh = Image.new('RGB', (tw * cols, th * rows + 44), (20, 20, 26)); d = ImageDraw.Draw(sh)
    d.text((12, 10), title, font=ImageFont.truetype(paths.FONT_MONTSERRAT, 24), fill=(255, 200, 72))
    for i, t in enumerate(tiles): sh.paste(t, ((i % cols) * tw, 44 + (i // cols) * th))
    sh.save(f'{OUT}/{name}.png'); print(name, sh.size)

CLOSE = {'preset': 'free', 'keys': [{'pos': [0, 1.68, 2.2 + .78], 'look': [0, 1.67, 2.2], 'fov': 44}]}
BODY = {'preset': 'free', 'keys': [{'pos': [1.25, 1.2, 2.2 + 2.9], 'look': [0, 1.0, 2.2], 'fov': 50}]}

def faces():
    items = []
    for k in A.FACE_KINDS:
        if k in ('talk',): continue
        a = {'id': 'hero', 'at': [0, 2.2], 'facing': 'camera', 'face': k}
        if k in ('creature',): a['crack'] = 1
        items.append((k, shot_img(a, CLOSE, 96, 96)))
    for gz in ('left', 'right', 'up', 'down'):
        items.append(('gaze ' + gz, shot_img({'id': 'hero', 'at': [0, 2.2], 'facing': 'camera', 'face': 'neutral', 'gaze': gz}, CLOSE, 96, 96)))
    sheet(items, 8, 2, 'expressions', 'EXPRESSIONS  ("face")  +  REGARD  ("gaze")')

def gestures(names=None):
    items = []
    for gname in names or [g for g in P.GESTURES if g not in ('idle', 'arm_up', 'extend', 'chest')]:
        hold = 'phone' if gname == 'phone' else None
        items.append((gname, shot_img({'id': 'hero', 'at': [0, 2.2], 'facing': 'camera', 'face': 'neutral', 'gesture': gname, 'hold': hold}, BODY)))
    sheet(items, 8, 2, 'gestes', 'GESTES  ("gesture")')

def postures():
    items = []
    for post, extra in (('stand', None), ('sit', [{'type': 'chair', 'at': [0, 2.13], 'rot': 2}]), ('kneel', None), ('crouch', None), ('jump', None),
                        ('lie', [{'type': 'bed', 'at': [0, 2.2], 'rot': 1}])):
        a = {'id': 'hero', 'at': [0, 2.2], 'facing': 'camera', 'face': 'sleeping' if post == 'lie' else 'neutral', 'posture': post}
        if post == 'lie': a.update(y=.48, head_to='-x')
        items.append((post, shot_img(a, BODY if post != 'lie' else {'preset': 'free', 'keys': [{'pos': [.2, 2.4, 4.6], 'look': [0, .5, 2.2], 'fov': 50}]}, extra=extra)))
    sheet(items, 6, 2, 'postures', 'POSTURES  ("posture")')

def held():
    items = []
    for it in P.HOLD_ITEMS:
        gest = {'phone': 'show', 'cup': 'hold', 'book': 'hold', 'flashlight': 'point', 'candle': 'hold', 'key': 'show', 'letter': 'show',
                'flower': 'show', 'gift': 'hold', 'sword': 'arm_up', 'ball': 'hold', 'bag': None, 'umbrella': 'show', 'balloon': None, 'microphone': 'show'}.get(it, 'hold')
        a = {'id': 'hero', 'at': [0, 2.2], 'facing': 'camera', 'face': 'happy', 'hold': it}
        if gest: a['gesture'] = gest
        items.append((it, shot_img(a, BODY)))
    sheet(items, 8, 2, 'objets', 'OBJETS EN MAIN  ("hold")')

def looks():
    items = []
    looks_ = [('hoodie', {}), ('tshirt', {'outfit': 'tshirt', 'hood': [200, 60, 60]}), ('shirt', {'outfit': 'shirt', 'hood': [90, 130, 190]}),
              ('suit', {'outfit': 'suit', 'hood': [40, 42, 52], 'jeans': [40, 42, 52], 'headphones': False, 'backpack': False}),
              ('dress', {'outfit': 'dress', 'hood': [170, 70, 140], 'hair_style': 'long', 'headphones': False, 'backpack': False}),
              ('coat', {'outfit': 'coat', 'hood': [120, 90, 60], 'headphones': False}),
              ('ponytail', {'hair_style': 'ponytail', 'hair': [120, 70, 30], 'headphones': False}), ('bun', {'hair_style': 'bun', 'headphones': False}),
              ('spiky', {'hair_style': 'spiky', 'hair': [230, 200, 80], 'headphones': False}), ('curly', {'hair_style': 'curly', 'headphones': False}),
              ('bald + beard', {'hair_style': 'bald', 'beard': True, 'headphones': False}), ('cap', {'hat': 'cap', 'headphones': False}),
              ('beanie', {'hat': 'beanie', 'hat_color': [60, 150, 90]}), ('hood', {'hat': 'hood'}), ('tophat', {'hat': 'tophat', 'outfit': 'suit', 'headphones': False}),
              ('crown', {'hat': 'crown', 'headphones': False}), ('glasses', {'glasses': True, 'headphones': False}), ('sunglasses', {'glasses': 'sun'}),
              ('mustache', {'beard': 'mustache', 'headphones': False}), ('child', {'scale': .72})]
    for label, lk in looks_:
        items.append((label, shot_img({'id': 'perso', 'at': [0, 2.2], 'facing': 'camera', 'face': 'happy'}, BODY, cast={'perso': lk})))
    sheet(items, 8, 2, 'apparences', 'APPARENCES  (dans "cast")')

def skies():
    items = []
    for sky in ('day', 'sunset', 'dawn', 'night'):
        sp = {'type': 'room', 'outdoor': True, 'sky': sky, 'ground': 'grass', 'rooms': [],
              'props': [{'type': 'tree', 'at': [-2.5, 6]}, {'type': 'tree', 'at': [3, 9]}, {'type': 'bench', 'at': [1.4, 4.5]}, {'type': 'streetlight', 'at': [-1.4, 3.5]},
                        {'type': 'car', 'at': [4, 12], 'rot': 1}, {'type': 'fence', 'at': [0, 14]}],
              'buildings': [{'rect': [-8, 16, -2, 22], 'height': 9, 'color': [150, 120, 100]}, {'rect': [2, 18, 9, 24], 'height': 12, 'color': [120, 130, 150]}]}
        ep = {'style': 'pixel3d', 'default_set': 'p', 'sets': {'p': sp}, 'hud': {}, 'grade': {'saturation': 1.0, 'exposure': 1.1}, 'cast': {'hero': {}},
              'state': {}, 'lines': {}, 'shots': [{'lines': [0, 0], 'camera': {'preset': 'free', 'keys': [{'pos': [0.5, 1.5, 0.5], 'look': [0, 1.3, 8], 'fov': 60}]},
                                                   'actors': [{'id': 'hero', 'at': [0.3, 3.2], 'facing': 'camera', 'face': 'joy', 'gesture': 'wave'}]}]}
        eng = Pixel3DEngine(ep, LINES, np.zeros(10), 4.0, '16:9'); set_res(192, 112, .72)
        items.append((sky, Image.fromarray(eng.render_lowres(1.0)[0])))
    sheet(items, 4, 2, 'ciels', 'EXTÉRIEUR  ("outdoor": true, "sky")')

from hstudio.engines.pixel3d import sets as SETS, creatures as CR, world as WD
GRASS = {'type': 'room', 'outdoor': True, 'sky': 'day', 'ground': 'grass', 'textured_ground': True, 'rooms': [], 'fog': .01, 'fill': .5, 'backdrop': ['hills']}

def scene_img(spec, actors, cam, rw=128, rh=96, t=1.0, cast=None, ep_extra=None):
    ep = {'style': 'pixel3d', 'default_set': 's', 'sets': {'s': spec}, 'hud': {}, 'grade': {'saturation': .95, 'exposure': 1.05}, 'cast': cast or {'hero': {}},
          'state': {}, 'lines': {}, 'shots': [{'lines': [0, 0], 'camera': cam, 'actors': actors}]}
    ep.update(ep_extra or {})
    eng = Pixel3DEngine(ep, LINES, np.zeros(10), 4.0, '16:9'); set_res(rw, rh, .72)
    return Image.fromarray(eng.render_lowres(t)[0])

def props_sheets():
    kinds = [k for k in SETS.PROP_TYPES if k not in ('door', 'window')]
    items = []
    for kd in kinds:
        params = {'blocks': [{'at': [0, 0, 0], 'size': [1.5, .15, 1.1], 'color': [112, 96, 76], 'material': 'wood'},
                             {'at': [-.65, .15, 0], 'size': [.15, 1.4, 1.1], 'color': [112, 96, 76], 'material': 'wood'}]} if kd == 'assemblage' else {}
        bl = SETS.prop_boxes(kd, params)
        lo = np.min([b.lo for b in bl], 0); hi = np.max([b.hi for b in bl], 0); size = float(max(hi - lo)); cy = float((lo[1] + hi[1]) / 2)
        d = max(1.6, size * 1.5)
        sp = dict(GRASS, props=[{'type': kd, 'at': [0, 3.0], 'rot': 0, **params}])
        cam = {'preset': 'free', 'keys': [{'pos': [d * .55, cy + d * .35, 3.0 - d], 'look': [0, cy, 3.0], 'fov': 50}]}
        items.append((kd, scene_img(sp, [], cam)))
    half = (len(items) + 1) // 2
    sheet(items[:half], 10, 2, 'decor_1', 'OBJETS DE DÉCOR  ("props": [{"type": ...}])  1/2')
    sheet(items[half:], 10, 2, 'decor_2', 'OBJETS DE DÉCOR  ("props": [{"type": ...}])  2/2')

def places_sheet():
    items = []
    for name in SETS.PLACE_TYPES:
        st = SETS.make_set(name, {'type': name, 'seed': 1}); st.build()
        if st.spec.get('rooms') and not st.spec.get('outdoor'):
            r = st.spec['rooms'][0]; w, d = r['size']; cam = {'preset': 'free', 'keys': [{'pos': [w * .3, 1.75, .35], 'look': [-w * .1, 1.0, d * .7], 'fov': 74}]}
        else:
            sx, sz = st.anchors.get('start', (0, 0)); cam = {'preset': 'free', 'keys': [{'pos': [sx + .4, 1.7, sz - .5], 'look': [sx, 1.2, sz + 10], 'fov': 64}]}
        items.append((name, scene_img({'type': name, 'seed': 1}, [], cam, 192, 104)))
    sheet(items, 6, 2, 'lieux', 'LIEUX PRÊTS  ("sets": {"x": {"type": ...}})')

def animals_sheet():
    items = []
    cam = {'preset': 'free', 'keys': [{'pos': [1.6, 1.3, .2], 'look': [0, .6, 3.0], 'fov': 50}]}
    for kd in CR.ANIMALS:
        big = kd in ('dragon', 'horse', 'cow')
        c = {'preset': 'free', 'keys': [{'pos': [4.5, 3.0, -2.5], 'look': [0, 1.5, 3.0], 'fov': 55}]} if kd == 'dragon' else (cam if not big else {'preset': 'free', 'keys': [{'pos': [2.6, 1.8, -.6], 'look': [0, 1.0, 3.0], 'fov': 52}]})
        a = {'id': 'a', 'at': [0, 3.0], 'facing': '+x' if kd in ('horse', 'cow', 'dragon', 'pig', 'sheep') else 'camera', 'posture': 'fly' if kd == 'bird' else None}
        items.append((kd, scene_img(GRASS, [a], c, cast={'a': {'kind': kd}})))
    sheet(items, 7, 2, 'animaux', 'ANIMAUX ET CRÉATURES  (cast: {"kind": ...})')

def presets_sheet():
    items = []
    cam = {'preset': 'free', 'keys': [{'pos': [1.2, 1.25, .3], 'look': [0, 1.0, 3.0], 'fov': 50}]}
    for pr in CR.PRESETS:
        items.append((pr, scene_img(GRASS, [{'id': 'p', 'at': [0, 3.0], 'facing': 'camera'}], cam, 96, 120, cast={'p': {'kind': pr}})))
    sheet(items, 10, 2, 'personnages', 'PERSONNAGES TYPES  (cast: {"kind": ...})')

def weather_sheet():
    items = []
    for wk, sky, place in (('rain', 'storm', 'city_street'), ('storm', 'storm', 'forest'), ('snow', 'overcast', 'snowy_forest'), ('blizzard', 'overcast', 'mountain'),
                           ('leaves', 'day', 'park'), ('petals', 'day', 'park'), ('fireflies', 'night', 'lake'), ('embers', 'sunset', 'volcano'), ('sparkles', 'night', 'forest')):
        st = SETS.make_set(place, {'type': place, 'seed': 2}); sx, sz = st.anchors.get('start', (0, 0))
        cam = {'preset': 'free', 'keys': [{'pos': [sx + .4, 1.7, sz - .5], 'look': [sx, 1.2, sz + 10], 'fov': 64}]}
        items.append((wk, scene_img({'type': place, 'seed': 2, 'sky': sky, 'weather': wk, 'stars': True}, [{'id': 'hero', 'at': [sx + .5, sz + 4], 'facing': 'camera', 'face': 'surprised'}], cam, 192, 104, t=1.4)))
    sheet(items, 5, 2, 'meteo', 'MÉTÉO  ("weather")  +  CIELS  ("sky")')

def side_sheet():
    items = []
    cam = {'preset': 'free', 'keys': [{'pos': [0, 1.2, -.5], 'look': [0, .9, 3.0], 'fov': 55}]}
    for fc, mv in (('+x', 'walk'), ('-x', 'run')):
        items.append((f'facing {fc}', scene_img({'type': 'park', 'seed': 3}, [{'id': 'hero', 'at': [-.4, 3.0], 'facing': fc, 'move': mv, 'to': [.4, 3.0], 'face': 'happy'},
                                                                                {'id': 'rex', 'at': [.7, 3.2], 'facing': fc, 'move': mv, 'to': [1.2, 3.2]}], cam, 192, 104, t=.8, cast={'hero': {}, 'rex': {'kind': 'dog'}})))
    sheet(items, 2, 2, 'profil', 'DE PROFIL  ("facing": "+x" / "-x")')

if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if what in ('all', 'faces'): faces()
    if what in ('all', 'gestures'): gestures()
    if what in ('all', 'postures'): postures()
    if what in ('all', 'held'): held()
    if what in ('all', 'looks'): looks()
    if what in ('all', 'skies'): skies()
    if what in ('all', 'props'): props_sheets()
    if what in ('all', 'places'): places_sheet()
    if what in ('all', 'animals'): animals_sheet()
    if what in ('all', 'presets'): presets_sheet()
    if what in ('all', 'weather'): weather_sheet()
    if what in ('all', 'side'): side_sheet()
