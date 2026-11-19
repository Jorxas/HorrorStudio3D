"""Ready-made places. Each generator turns a short spec ({"type": "forest", "seed": 3, "sky": "day"}) into a full
room/outdoor spec for RoomSet: ground and zones, scattered props, backdrop, lights, weather, ambience and anchors.
The camera usually starts near z = 0 looking towards +z; anchors give the useful spots."""
import numpy as np
from .world import scatter

def _base(spec, **kw):
    out = {'type': 'room', 'generated': True, 'textured_ground': True, 'rooms': [], 'props': [], 'zones': [], 'fog': .02, 'fill': .45}
    out.update(kw)
    for k in ('sky', 'backdrop', 'clouds', 'weather', 'fog', 'seed', 'stars', 'ambience', 'sun', 'fill', 'ambient', 'wet', 'ground'):
        if k in spec: out[k] = spec[k]
    out['props'] = out['props'] + list(spec.get('props', []))
    out['blocks'] = list(spec.get('blocks', []))
    if spec.get('anchors'): out['anchors'] = dict(out.get('anchors', {}), **spec['anchors'])
    return out

def _night(spec): return spec.get('sky') == 'night'

# ------------------------------------------------------------------ outdoors
def forest(spec):
    s = int(spec.get('seed', 0)); night = _night(spec)
    path = [[0, -2], [.6, 6], [-.8, 13], [.4, 22], [0, 34]]
    o = _base(spec, outdoor=True, sky='day', ground='grass', backdrop=['hills', 'forest'], fog=.035, ambience='night' if night else 'forest', stars=night, fill=.5,
              zones=[{'path': path, 'width': 2.0, 'ground': 'dirt'}, {'circle': [0, 14, 3.2], 'ground': 'leaves'}],
              anchors={'path.start': (0, 1), 'path.mid': (.2, 8), 'clearing': (0, 14), 'path.end': (.3, 24), 'deep': (-5, 18)})
    o['props'] += scatter([{'type': ['tree_round', 'pine', 'birch', 'tree_round'], 'count': 46, 'area': [-16, -1, 16, 40], 'min_dist': 2.6, 'avoid': [[-2.2, -3, 2.2, 36], [-3.5, 11, 3.5, 17]]},
                           {'type': ['bush', 'rock', 'tall_grass', 'flowers', 'mushroom', 'stump'], 'count': 40, 'area': [-10, 0, 10, 30], 'min_dist': 1.0, 'avoid': [[-1.3, -3, 1.3, 36]], 'size': [.7, 1.2]},
                           {'type': 'log', 'count': 2, 'area': [-3, 12, 3, 16], 'avoid': [[-1, 13, 1, 15]]}], s)
    return o

def snowy_forest(spec):
    o = forest(dict(spec)); o.update(ground='snow', backdrop=['snow_mountains', 'forest'], weather=spec.get('weather', 'snow'), ambience='snow')
    o['zones'] = [{'path': [[0, -2], [.6, 6], [-.8, 13], [.4, 22], [0, 34]], 'width': 1.8, 'ground': 'stone'}]
    for p in o['props']:
        if p['type'] in ('tree_round', 'birch', 'pine'): p['type'] = 'snow_pine'
        elif p['type'] in ('flowers', 'mushroom', 'tall_grass'): p['type'] = 'rock'
    o['props'].append({'type': 'snowman', 'at': [2.5, 9], 'rot': 2})
    return o

def beach(spec):
    s = int(spec.get('seed', 0))
    o = _base(spec, outdoor=True, sky='day', ground='sand', backdrop=['islands'], fog=.012, ambience='beach',
              zones=[{'rect': [-60, 12, 60, 200], 'ground': 'water'}, {'rect': [-60, 10.8, 60, 12], 'ground': 'mud'}],
              anchors={'sand': (0, 4), 'shore': (0, 10.5), 'sea': (0, 14), 'towel': (-2.2, 6), 'umbrella': (-2.2, 6.6), 'dock.end': (6, 17), 'palms': (-7, 4)})
    o['props'] += [{'type': 'beach_umbrella', 'at': [-2.2, 6.6]}, {'type': 'beach_towel', 'at': [-2.2, 5.6], 'color': [60, 150, 220]},
                   {'type': 'beach_towel', 'at': [-.9, 5.8], 'color': [240, 180, 40]}, {'type': 'sandcastle', 'at': [1.6, 8.5]},
                   {'type': 'dock', 'at': [6, 9], 'length': 9}, {'type': 'boat', 'at': [7.6, 15], 'rot': 1}, {'type': 'rock_pile', 'at': [-8, 11]}]
    o['props'] += scatter([{'type': 'palm', 'count': 9, 'area': [-16, -2, 16, 7], 'min_dist': 3.5, 'avoid': [[-4, -3, 4, 10]], 'size': [.9, 1.3]},
                           {'type': ['rock', 'tall_grass'], 'count': 8, 'area': [-14, 0, 14, 9], 'avoid': [[-3, 3, 3, 10]]}], s)
    return o

def island(spec):
    o = beach(spec); o['backdrop'] = []; o['zones'] = [{'circle': [0, 4, 15], 'ground': 'sand'}]; o['ground'] = 'water'
    o['props'] = [p for p in o['props'] if p['type'] != 'dock'] + [{'type': 'chest', 'at': [0, 2], 'open': spec.get('open_chest', False)}]
    o['anchors']['treasure'] = (0, 2); return o

def mountain(spec):
    s = int(spec.get('seed', 0)); snow = spec.get('snow', True)
    o = _base(spec, outdoor=True, sky='day', ground='snow' if snow else 'rock', backdrop=[{'type': 'snow_mountains', 'height': 20}, 'mountains'], fog=.02, ambience='wind',
              zones=[{'path': [[0, -2], [1.5, 8], [-1, 18], [2, 30]], 'width': 1.6, 'ground': 'rock'}],
              anchors={'trail.start': (0, 1), 'trail.mid': (1.2, 9), 'summit': (1.5, 26), 'cliff': (6, 14)})
    o['props'] += scatter([{'type': ['boulder', 'rock', 'rock_pile'], 'count': 26, 'area': [-16, 0, 16, 40], 'min_dist': 2.5, 'avoid': [[-2, -3, 3, 32]]},
                           {'type': 'snow_pine' if snow else 'pine', 'count': 14, 'area': [-18, 6, 18, 40], 'min_dist': 3, 'avoid': [[-3, 0, 4, 32]]}], s)
    o['props'].append({'type': 'flag', 'at': [1.5, 27], 'color': [220, 40, 40]})
    return o

def desert(spec):
    s = int(spec.get('seed', 0))
    o = _base(spec, outdoor=True, sky='day', ground='sand', backdrop=['dunes', {'type': 'dunes', 'height': 1.6, 'haze': .1}], fog=.012, ambience='wind',
              anchors={'dunes': (0, 6), 'ruins': (4, 16), 'oasis': (-8, 20), 'far': (0, 30)}, clouds=.1,
              zones=[{'circle': [-8, 20, 3.5], 'ground': 'water'}, {'circle': [-8, 20, 5.2], 'ground': 'grass'}])
    o['zones'] = list(reversed(o['zones']))
    o['props'] += [{'type': 'ruins', 'at': [4, 16]}, {'type': 'palm', 'at': [-11, 19]}, {'type': 'palm', 'at': [-5, 23]}, {'type': 'palm', 'at': [-9, 24]}]
    o['props'] += scatter([{'type': ['cactus', 'rock', 'dead_tree', 'rock_pile'], 'count': 18, 'area': [-18, 1, 18, 40], 'min_dist': 3.5, 'avoid': [[-13, 15, -3, 26], [1, 13, 7, 19], [-2, -2, 2, 10]]}], s)
    return o

def city_street(spec):
    s = int(spec.get('seed', 0)); night = _night(spec); wet = spec.get('wet', night)
    o = _base(spec, outdoor=True, sky='day', ground='stone', backdrop=[{'type': 'city', 'height': 12, 'density': 40}], fog=.03, ambience='city', stars=night, wet=wet,
              zones=[{'rect': [-3.2, -10, 3.2, 120], 'ground': 'road'}],
              anchors={'sidewalk.left': (-4.5, 6), 'sidewalk.right': (4.5, 6), 'crossing': (0, 10), 'bus_stop': (4.6, 14), 'shop.left': (-6, 8), 'shop.right': (6, 20), 'street.far': (0, 28)})
    cols = [(170, 150, 130), (130, 140, 160), (180, 130, 110), (150, 160, 140), (120, 110, 130)]
    names = ['BOULANGERIE', 'CAFÉ', 'PHARMACIE', 'LIBRAIRIE', 'BOUTIQUE', 'FLEURS', 'PIZZA', 'CINÉMA']
    rng = np.random.default_rng(s)
    for i, z in enumerate(range(2, 44, 6)):
        for side in (-1, 1):
            if (i + (side > 0)) % 2 == 0:
                o['props'].append({'type': 'shop', 'at': [side * 8.0, z + 3], 'rot': 3 if side < 0 else 1, 'color': cols[(i + side) % 5], 'sign': names[int(rng.integers(0, len(names)))],
                                   'awning': [(190, 50, 50), (40, 110, 170), (60, 140, 70), (230, 170, 40)][int(rng.integers(0, 4))]})
            else:
                o.setdefault('buildings', []).append({'rect': [side * 8.0 - 2.5 if side > 0 else side * 8.0 - 2.5, z, side * 8.0 + 2.5, z + 6], 'height': 6 + float(rng.uniform(0, 8)), 'color': list(cols[(i * 3 + side) % 5])})
    o['props'] += [{'type': 'streetlight', 'at': [x, z]} for z in range(0, 44, 8) for x in (-3.8, 3.8)]
    o['props'] += [{'type': 'traffic_light', 'at': [3.6, 9.5], 'state': spec.get('traffic', 'red')}, {'type': 'bus_stop', 'at': [5, 14], 'rot': 1},
                   {'type': 'trash_can', 'at': [-4.2, 4]}, {'type': 'hydrant', 'at': [4.2, 6]}, {'type': 'mailbox', 'at': [-4.3, 12]},
                   {'type': 'car', 'at': [-2.2, 18], 'color': [40, 80, 160]}, {'type': 'car', 'at': [2.2, 30], 'color': [200, 200, 205]}, {'type': 'billboard', 'at': [-6.5, 34]}]
    for z in range(9, 12): o['zones'].append({'rect': [-3.2, z - .2 + .0, 3.2, z + .2], 'ground': 'snow'})   # zebra crossing
    return o

def village(spec):
    s = int(spec.get('seed', 0)); night = _night(spec)
    o = _base(spec, outdoor=True, sky='day', ground='grass', backdrop=['hills', 'forest'], fog=.025, ambience='night' if night else 'village', stars=night,
              zones=[{'circle': [0, 12, 6], 'ground': 'cobble'}, {'path': [[0, -2], [0, 7]], 'width': 2.2, 'ground': 'dirt'}, {'path': [[0, 17], [3, 30]], 'width': 2, 'ground': 'dirt'}],
              anchors={'square': (0, 12), 'well': (0, 12), 'road.in': (0, 2), 'house.1': (-7, 9), 'house.2': (7, 14), 'market': (3.5, 10)})
    o['props'] += [{'type': 'well', 'at': [0, 12]}, {'type': 'market_stall', 'at': [3.8, 10], 'rot': 1}, {'type': 'signpost', 'at': [1.5, 3], 'text': spec.get('name', 'VILLAGE')},
                   {'type': 'house', 'at': [-7.5, 9], 'rot': 3, 'night': night}, {'type': 'house', 'at': [7.5, 14], 'rot': 1, 'color': [210, 190, 150], 'roof': [100, 70, 60], 'night': night},
                   {'type': 'house', 'at': [-3, 21], 'color': [190, 200, 180], 'night': night}, {'type': 'house', 'at': [6, 23], 'roof': [60, 80, 120], 'night': night},
                   {'type': 'barrel', 'at': [-2.5, 9]}, {'type': 'barrel', 'at': [-2.9, 9.4]}, {'type': 'hay_bale', 'at': [9, 7]}, {'type': 'lantern', 'at': [2.6, 14]}, {'type': 'lantern', 'at': [-2.6, 14]}]
    o['props'] += scatter([{'type': ['tree_round', 'bush', 'flowers'], 'count': 22, 'area': [-18, 0, 18, 34], 'min_dist': 2.5, 'avoid': [[-6.5, 5, 6.5, 19], [-11, 5, -4, 13], [4, 10, 11, 18], [-6, 17, 9, 27], [-1.5, -3, 1.5, 7]]}], s)
    return o

def park(spec):
    s = int(spec.get('seed', 0)); night = _night(spec)
    o = _base(spec, outdoor=True, sky='day', ground='grass', backdrop=[{'type': 'city', 'height': 8}, 'forest'], fog=.02, ambience='night' if night else 'park', stars=night,
              zones=[{'path': [[0, -2], [0, 30]], 'width': 2.4, 'ground': 'stone'}, {'path': [[-12, 12], [12, 12]], 'width': 2.2, 'ground': 'stone'}, {'circle': [-7, 21, 3], 'ground': 'water'}],
              anchors={'path.start': (0, 1), 'fountain': (0, 12), 'bench': (2.2, 6), 'playground': (7, 20), 'pond': (-7, 21), 'lawn': (-6, 6)})
    o['props'] += [{'type': 'fountain', 'at': [0, 12]}, {'type': 'bench', 'at': [2.4, 6], 'rot': 1}, {'type': 'bench', 'at': [-2.4, 17], 'rot': 3},
                   {'type': 'swing', 'at': [7, 20]}, {'type': 'slide', 'at': [10, 18], 'rot': 1}, {'type': 'lantern', 'at': [1.6, 3]}, {'type': 'lantern', 'at': [-1.6, 9]},
                   {'type': 'lantern', 'at': [1.6, 20]}, {'type': 'trash_can', 'at': [-1.6, 5]}, {'type': 'picnic', 'at': [-6, 6]}, {'type': 'flowers', 'at': [3, 13]}, {'type': 'flowers', 'at': [-3, 11]}]
    o['props'] += scatter([{'type': ['tree_round', 'blossom_tree', 'birch'], 'count': 18, 'area': [-18, -1, 18, 34], 'min_dist': 3.5, 'avoid': [[-2.5, -3, 2.5, 32], [-14, 10, 14, 14], [-11, 17, -3, 25], [4, 16, 12, 24], [-9, 3, -3, 9]]},
                           {'type': ['bush', 'flowers'], 'count': 14, 'area': [-15, 0, 15, 30], 'min_dist': 1.6, 'avoid': [[-2, -3, 2, 32], [-14, 10.5, 14, 13.5]]}], s)
    return o

def countryside(spec):
    s = int(spec.get('seed', 0))
    o = _base(spec, outdoor=True, sky='day', ground='grass', backdrop=['hills', {'type': 'hills', 'height': 2, 'haze': .1}], fog=.015, ambience='countryside',
              zones=[{'path': [[0, -2], [1, 10], [4, 22], [5, 40]], 'width': 2.4, 'ground': 'dirt'}, {'rect': [-20, 8, -6, 26], 'ground': 'dirt'}],
              anchors={'road': (0, 3), 'farm': (8, 16), 'field': (-12, 16), 'barn': (12, 22), 'fence': (-4.5, 10)})
    o['props'] += [{'type': 'house', 'at': [9, 15], 'rot': 1, 'color': [230, 220, 200], 'roof': [120, 60, 50]}, {'type': 'house', 'at': [13, 24], 'rot': 1, 'color': [170, 50, 40], 'roof': [80, 70, 70]},
                   {'type': 'scarecrow', 'at': [-12, 16], 'rot': 2}, {'type': 'horse_cart', 'at': [4, 10], 'rot': 1}, {'type': 'well', 'at': [6, 19]}]
    o['props'] += [{'type': 'fence', 'at': [-4.6, z], 'rot': 1} for z in range(8, 27, 3)] + [{'type': 'hay_bale', 'at': [x, z], 'rot': (x * 3 + z) % 4} for x, z in ((-9, 11), (-14, 20), (-17, 13), (-10, 23))]
    o['props'] += scatter([{'type': ['tree_round', 'autumn_tree'], 'count': 12, 'area': [-25, 26, 25, 50], 'min_dist': 4},
                           {'type': 'tall_grass', 'count': 30, 'area': [-19.5, 8.5, -6.5, 25.5], 'min_dist': 1.2, 'colors': [[200, 170, 70], [190, 160, 60]]}], s)
    return o

def lake(spec):
    s = int(spec.get('seed', 0)); night = _night(spec)
    o = _base(spec, outdoor=True, sky='day', ground='grass', backdrop=['mountains', 'forest'], fog=.02, ambience='night' if night else 'river', stars=night,
              zones=[{'circle': [0, 18, 9], 'ground': 'water'}, {'circle': [0, 18, 10.3], 'ground': 'sand'}],
              anchors={'shore': (0, 7.5), 'dock.end': (3, 13), 'boat': (5, 16), 'lake': (0, 18), 'trees': (-9, 8)})
    o['zones'] = list(reversed(o['zones']))
    o['props'] += [{'type': 'dock', 'at': [3, 7], 'length': 6}, {'type': 'boat', 'at': [5, 16]}, {'type': 'bench', 'at': [-3, 5.5]}, {'type': 'rock_pile', 'at': [-7, 10]}]
    o['props'] += scatter([{'type': ['pine', 'tree_round', 'birch'], 'count': 26, 'area': [-22, 0, 22, 40], 'min_dist': 3.2, 'avoid': [[-11, 6, 11, 30], [-4, 0, 6, 8]]}], s)
    return o

def river(spec):
    s = int(spec.get('seed', 0))
    riv = [[-30, 14], [-10, 12], [0, 15], [10, 13], [30, 16]]
    o = _base(spec, outdoor=True, sky='day', ground='grass', backdrop=['hills', 'forest'], fog=.02, ambience='river',
              zones=[{'path': riv, 'width': 7.5, 'ground': 'sand'}, {'path': riv, 'width': 6, 'ground': 'water'}, {'path': [[0, -2], [0, 30]], 'width': 1.8, 'ground': 'dirt'}],
              anchors={'path': (0, 4), 'bridge': (0, 14.5), 'bank': (3, 10), 'other_side': (0, 22)})
    o['props'] += [{'type': 'bridge', 'at': [0, 14.5], 'length': 8}, {'type': 'rock', 'at': [6, 11.5]}, {'type': 'rock', 'at': [-5, 17]}]
    o['props'] += scatter([{'type': ['tree_round', 'birch', 'bush', 'tall_grass'], 'count': 30, 'area': [-20, 0, 20, 34], 'min_dist': 2.5, 'avoid': [[-30, 9, 30, 19.5], [-1.5, -3, 1.5, 32]]}], s)
    return o

def campsite(spec):
    o = forest(dict(spec, sky=spec.get('sky', 'night'))); o.update(ambience='campfire', weather=spec.get('weather', 'fireflies' if _night(dict(spec, sky=spec.get('sky', 'night'))) else None), stars=True)
    o['sky'] = spec.get('sky', 'night')
    o['props'] = [p for p in o['props'] if not (-4 <= p['at'][0] <= 4 and 10 <= p['at'][1] <= 18)]
    o['props'] += [{'type': 'campfire', 'at': [0, 14]}, {'type': 'tent', 'at': [-2.8, 16.5], 'rot': 1, 'color': [200, 120, 40]}, {'type': 'tent', 'at': [3, 16.8], 'rot': 3},
                   {'type': 'log', 'at': [0, 12.3]}, {'type': 'log', 'at': [-1.6, 14], 'rot': 1}, {'type': 'lantern', 'at': [2.2, 12]}]
    o['anchors'].update({'campfire': (0, 14), 'tent.1': (-2.8, 16.5), 'tent.2': (3, 16.8), 'log': (0, 12.3)})
    return o

def graveyard(spec):
    s = int(spec.get('seed', 0))
    o = _base(spec, outdoor=True, sky='night', ground='grass', backdrop=['forest', {'type': 'castle', 'at': .4, 'height': 10}], fog=.07, ambience='night', stars=True,
              zones=[{'path': [[0, -2], [0, 30]], 'width': 1.8, 'ground': 'dirt'}],
              anchors={'gate': (0, 1.5), 'path': (0, 8), 'grave': (2.5, 12), 'crypt': (0, 24), 'tree': (-6, 15)})
    o['props'] += [{'type': 'gate', 'at': [0, 1], 'open': True}, {'type': 'castle_wall', 'at': [-7.5, 1], 'length': 10, 'height': 2.2}, {'type': 'castle_wall', 'at': [7.5, 1], 'length': 10, 'height': 2.2},
                   {'type': 'dead_tree', 'at': [-6, 15]}, {'type': 'dead_tree', 'at': [7, 22], 'rot': 1}, {'type': 'lantern', 'at': [1.5, 5]}, {'type': 'statue', 'at': [-4, 21]},
                   {'type': 'tower', 'at': [0, 27], 'height': 4.5, 'roof': True}]
    for i, z in enumerate(np.arange(5, 22, 2.6)):
        for x in (-5, -2.8, 2.8, 5):
            if (i * 7 + int(x * 3) + s) % 5 != 0: o['props'].append({'type': 'gravestone' if (i + int(x)) % 3 else 'cross', 'at': [x, float(z)], 'rot': 0, 'text': 'R.I.P'})
    return o

def castle(spec):
    s = int(spec.get('seed', 0)); night = _night(spec)
    o = _base(spec, outdoor=True, sky='day', ground='cobble', backdrop=['mountains', 'forest'], fog=.02, ambience='night' if night else 'village', stars=night,
              anchors={'courtyard': (0, 10), 'gate': (0, 2), 'keep': (0, 19), 'tower.left': (-9, 18), 'tower.right': (9, 18), 'well': (-4, 9)})
    o['props'] += [{'type': 'gate', 'at': [0, 0], 'open': True}, {'type': 'castle_wall', 'at': [-6.5, 0], 'length': 8}, {'type': 'castle_wall', 'at': [6.5, 0], 'length': 8},
                   {'type': 'castle_wall', 'at': [-10.5, 10], 'length': 20, 'rot': 1}, {'type': 'castle_wall', 'at': [10.5, 10], 'length': 20, 'rot': 1},
                   {'type': 'tower', 'at': [-10.5, 0], 'lit': night}, {'type': 'tower', 'at': [10.5, 0], 'lit': night}, {'type': 'tower', 'at': [-10, 20], 'height': 9}, {'type': 'tower', 'at': [10, 20], 'height': 9},
                   {'type': 'house', 'at': [0, 22], 'color': [140, 136, 128], 'roof': [60, 50, 90]}, {'type': 'well', 'at': [-4, 9]}, {'type': 'market_stall', 'at': [5, 8], 'rot': 1},
                   {'type': 'flag', 'at': [-3, 18], 'color': [180, 30, 40]}, {'type': 'flag', 'at': [3, 18], 'color': [180, 30, 40]}, {'type': 'barrel', 'at': [-8.5, 6]}, {'type': 'barrel', 'at': [-8.9, 6.6]},
                   {'type': 'torch_wall', 'at': [-1.8, .7], 'rot': 2}, {'type': 'torch_wall', 'at': [1.8, .7], 'rot': 2}, {'type': 'horse_cart', 'at': [6.5, 14], 'rot': 1}]
    return o

def snow_village(spec):
    o = village(spec); o.update(ground='snow', backdrop=['snow_mountains', 'forest'], weather=spec.get('weather', 'snow'), ambience='snow')
    o['zones'] = [{'circle': [0, 12, 6], 'ground': 'ice'}, {'path': [[0, -2], [0, 7]], 'width': 2.2, 'ground': 'stone'}]
    for p in o['props']:
        if p['type'] == 'house': p['roof'] = [236, 240, 248]
        if p['type'] in ('tree_round', 'bush', 'flowers'): p['type'] = 'snow_pine'
        if p['type'] == 'market_stall': p['type'] = 'christmas_tree'
    o['props'] += [{'type': 'snowman', 'at': [2.5, 6]}, {'type': 'igloo', 'at': [-10, 22]}]
    return o

def volcano(spec):
    o = desert(spec); o.update(ground='rock', backdrop=[{'type': 'volcano', 'at': .2}, 'mountains'], sky=spec.get('sky', 'sunset'), weather=spec.get('weather', 'ash'), ambience='wind')
    o['zones'] = [{'path': [[-20, 26], [-4, 20], [6, 24], [20, 18]], 'width': 2.2, 'ground': 'lava'}]
    o['props'] = [p for p in o['props'] if p['type'] not in ('palm', 'cactus')] + [{'type': 'dead_tree', 'at': [3, 8]}]
    return o

# ------------------------------------------------------------------ indoors (one room, the camera usually stands near the S wall)
DARK_ROOMS = ('attic', 'basement', 'cave', 'throne_room')
def _room(spec, rid, size, walls, floor, light='warm', dark=False, **kw):
    room = {'id': rid, 'origin': [0, 0], 'size': size, 'walls': walls, 'floor': floor, 'light': light, 'light_power': 1.6, 'clean': not (dark or spec.get('dirty'))}
    room.update(kw)
    o = _base(spec, rooms=[room], fog=.03, textured_ground=False)
    o['height'] = float(room.get('height', 2.6)) + .05      # far ceiling just above the room's own (clean) ceiling
    o['ambient'] = spec.get('ambient', (.13, .12, .12) if (dark or spec.get('mood') == 'dark') else (.17, .16, .15))
    o['fill'] = spec.get('fill', .35 if dark else .6)
    if spec.get('wall_color'): room['wall_color'] = spec['wall_color']
    if spec.get('light'): room['light'] = spec['light']
    return o, room

def bedroom(spec):
    o, r = _room(spec, 'chambre', [5, 5], 'wallpaper', 'wood', windows=[{'wall': 'N', 'pos': .7, 'night': spec.get('night', True)}], doors=[{'id': 'porte', 'wall': 'W', 'pos': .3}])
    r['props'] = [{'type': 'bed', 'at': [-1.5, 3.6], 'rot': 0, 'id': 'lit'}, {'type': 'nightstand', 'at': [-.6, 4.5]}, {'type': 'desk', 'at': [1.6, 1.2], 'rot': 1, 'id': 'bureau'},
                  {'type': 'chair', 'at': [1.1, 1.2], 'rot': 3}, {'type': 'wardrobe', 'at': [1.9, 3.6], 'rot': 1}, {'type': 'rug', 'at': [0, 2.4]}, {'type': 'plant', 'at': [-2.1, .5]},
                  {'type': 'curtains', 'at': [.95, 4.95], 'rot': 0}]
    o['anchors'] = {'lit': (-1.5, 3.6), 'bureau': (1.6, 1.2), 'fenetre': (1, 4.6), 'porte': (-2.3, 1.5), 'centre': (0, 2.4)}
    return o

def kid_bedroom(spec):
    o = bedroom(spec); r = o['rooms'][0]; r['walls'] = 'plaster_blue'; r['wall_color'] = spec.get('wall_color', [120, 170, 210])
    r['props'] = [p for p in r['props'] if p['type'] not in ('desk', 'chair')] + [{'type': 'toy', 'at': [.6, 2.8]}, {'type': 'ball', 'at': [-.4, 1.6], 'color': [230, 80, 60]},
                  {'type': 'bunk_bed', 'at': [1.9, 1.8], 'rot': 1}, {'type': 'bookshelf', 'at': [-2.2, 1.8], 'rot': 3}]
    for p in r['props']:
        if p['type'] == 'bed': p['type'] = 'crib' if spec.get('baby') else 'bed'
    return o

def living_room(spec):
    o, r = _room(spec, 'salon', [6, 6], 'wallpaper', 'wood', windows=[{'wall': 'N', 'pos': .25, 'night': spec.get('night', False)}, {'wall': 'N', 'pos': .75, 'night': spec.get('night', False)}],
                 doors=[{'id': 'porte', 'wall': 'E', 'pos': .2}])
    r['props'] = [{'type': 'sofa', 'at': [0, 2.0], 'rot': 0, 'id': 'canape'}, {'type': 'tv_stand', 'at': [0, .5], 'rot': 2}, {'type': 'rug', 'at': [0, 1.3]}, {'type': 'armchair', 'at': [-2.2, 1.4], 'rot': 3},
                  {'type': 'bookshelf', 'at': [-2.75, 4], 'rot': 3}, {'type': 'fireplace', 'at': [2.75, 4], 'rot': 1}, {'type': 'plant', 'at': [2.5, .5]}, {'type': 'lamp', 'at': [-2.5, 5.5]},
                  {'type': 'clock', 'at': [0, 5.95], 'rot': 0}, {'type': 'table', 'at': [0, 4.4]}]
    o['anchors'] = {'canape': (0, 2.0), 'tv': (0, .5), 'cheminee': (2.75, 4), 'fenetre': (-1.5, 5.6), 'porte': (2.8, 1.2), 'table': (0, 4.4)}
    return o

def kitchen(spec):
    o, r = _room(spec, 'cuisine', [5, 5], 'tiles', 'checker', light='neon', windows=[{'wall': 'N', 'pos': .5, 'night': spec.get('night', False)}], doors=[{'id': 'porte', 'wall': 'W', 'pos': .3}])
    r['props'] = [{'type': 'counter_long', 'at': [0, 4.6]}, {'type': 'stove', 'at': [-1.4, 4.6]}, {'type': 'sink', 'at': [.9, 4.6]}, {'type': 'fridge', 'at': [2.1, 3.2], 'rot': 1},
                  {'type': 'dining_table', 'at': [0, 2.0]}, {'type': 'chair', 'at': [-.6, 1.3], 'rot': 2}, {'type': 'chair', 'at': [.6, 2.7]}, {'type': 'washing_machine', 'at': [2.1, 1.0], 'rot': 1}]
    o['anchors'] = {'table': (0, 2.0), 'four': (-1.4, 4.0), 'evier': (.9, 4.0), 'frigo': (1.6, 3.2), 'porte': (-2.3, 1.5)}
    return o

def bathroom(spec):
    o, r = _room(spec, 'sdb', [3.5, 3.5], 'tiles', 'tiles', light='cold', doors=[{'id': 'porte', 'wall': 'S', 'pos': .25}])
    r['props'] = [{'type': 'bathtub', 'at': [-.9, 2.9]}, {'type': 'toilet', 'at': [1.3, 2.9]}, {'type': 'sink', 'at': [1.4, 1.4], 'rot': 1}, {'type': 'mirror', 'at': [1.72, 1.4], 'rot': 1}]
    o['anchors'] = {'baignoire': (-.9, 2.9), 'miroir': (1.2, 1.4), 'porte': (-.9, .3)}
    return o

def classroom(spec):
    o, r = _room(spec, 'classe', [8, 7], 'plaster_green', 'linoleum', light='neon', windows=[{'wall': 'E', 'pos': p_, 'night': False} for p_ in (.25, .5, .75)], doors=[{'id': 'porte', 'wall': 'W', 'pos': .85}])
    r['props'] = [{'type': 'blackboard', 'at': [0, 6.95], 'rot': 0, 'text': spec.get('board', ['LEÇON DU JOUR', '2 + 2 = 4'])}, {'type': 'desk', 'at': [-2.5, 5.6], 'rot': 2, 'id': 'bureau_prof'}]
    for i, (x, z) in enumerate([(x, z) for z in (1.4, 2.7, 4.0) for x in (-2.4, -.8, .8, 2.4)]): r['props'].append({'type': 'school_desk', 'at': [x, z], 'rot': 2})
    r['props'] += [{'type': 'bookshelf', 'at': [3.75, .8], 'rot': 1}, {'type': 'clock', 'at': [2.5, 6.98], 'rot': 0}, {'type': 'plant', 'at': [-3.6, .5]}]
    o['anchors'] = {'tableau': (0, 6.3), 'prof': (-2.5, 5.6), 'eleve.1': (-2.4, 1.4), 'eleve.2': (.8, 2.7), 'fond': (0, .6), 'porte': (-3.8, 6)}
    return o

def office(spec):
    o, r = _room(spec, 'bureau', [7, 6], 'plaster', 'carpet', light='neon', windows=[{'wall': 'N', 'pos': p_, 'night': spec.get('night', False)} for p_ in (.3, .7)], doors=[{'id': 'porte', 'wall': 'S', 'pos': .15}])
    r['props'] = [{'type': 'computer', 'at': [x, z]} for x in (-2, 0, 2) for z in (2.0, 4.0)] + [{'type': 'chair', 'at': [x, z - .7], 'rot': 2} for x in (-2, 0, 2) for z in (2.0, 4.0)]
    r['props'] += [{'type': 'whiteboard', 'at': [3.45, 3], 'rot': 1}, {'type': 'plant', 'at': [-3.1, .5]}, {'type': 'vending_machine', 'at': [3, .6], 'rot': 1}]
    o['anchors'] = {'poste': (0, 2.0), 'tableau': (2.9, 3), 'fenetre': (0, 5.6), 'machine': (2.5, .6), 'porte': (-2.5, .4)}
    return o

def hospital_room(spec):
    o, r = _room(spec, 'chambre', [5, 5], 'hospital', 'linoleum', light='cold', windows=[{'wall': 'E', 'pos': .5, 'night': spec.get('night', False)}], doors=[{'id': 'porte', 'wall': 'W', 'pos': .3}])
    r['props'] = [{'type': 'hospital_bed', 'at': [0, 3.2], 'id': 'lit'}, {'type': 'hospital_monitor', 'at': [-.9, 4.2]}, {'type': 'iv_stand', 'at': [.9, 4.0]}, {'type': 'chair', 'at': [1.4, 2.4], 'rot': 1},
                  {'type': 'wheelchair', 'at': [-1.9, 1.0], 'rot': 3}, {'type': 'curtains', 'at': [2.45, 2.5], 'rot': 1}]
    o['anchors'] = {'lit': (0, 3.2), 'chaise': (1.4, 2.4), 'fenetre': (2.2, 2.5), 'porte': (-2.2, 1.5)}
    return o

def shop_interior(spec):
    o, r = _room(spec, 'magasin', [8, 7], 'plaster', 'tiles', light='neon', doors=[{'id': 'entree', 'wall': 'S', 'pos': .5}])
    r['props'] = [{'type': 'shelf', 'at': [x, z], 'rot': 1} for x in (-2.5, 0, 2.5) for z in (3.0, 5.0)] + [{'type': 'counter', 'at': [2.5, 1.2]}, {'type': 'cash_register', 'at': [2.5, 1.2], 'rot': 2},
                  {'type': 'vending_machine', 'at': [-3.5, 1], 'rot': 3}]
    o['anchors'] = {'caisse': (2.5, 1.8), 'rayon.1': (-1.2, 3.0), 'rayon.2': (1.2, 5.0), 'entree': (0, .4)}
    return o

def cafe(spec):
    o, r = _room(spec, 'cafe', [8, 7], 'wood', 'checker', light='warm', windows=[{'wall': 'S', 'pos': p_, 'night': spec.get('night', False)} for p_ in (.2, .8)], doors=[{'id': 'porte', 'wall': 'S', 'pos': .5}])
    r['props'] = [{'type': 'bar', 'at': [0, 6.0]}] + [{'type': 'cafe_table', 'at': [x, z]} for x in (-2.5, 0, 2.5) for z in (2.0, 3.8)] + [{'type': 'chair', 'at': [x + .55, z], 'rot': 1} for x in (-2.5, 0, 2.5) for z in (2.0, 3.8)]
    r['props'] += [{'type': 'plant', 'at': [-3.6, .5]}, {'type': 'sign', 'at': [0, 6.98], 'rot': 0, 'text': spec.get('name', 'CAFÉ'), 'color': [40, 30, 26]}]
    o['anchors'] = {'comptoir': (0, 5.3), 'table.1': (-2.5, 2.0), 'table.2': (0, 3.8), 'entree': (0, .4)}
    return o

def library(spec):
    o, r = _room(spec, 'bibliotheque', [8, 8], 'wood', 'carpet', light='warm', windows=[{'wall': 'N', 'pos': .5, 'night': spec.get('night', False)}])
    r['props'] = [{'type': 'bookshelf', 'at': [x, z], 'rot': 0} for x in (-3, -1.6, 1.6, 3) for z in (3.5, 5.5)] + [{'type': 'bookshelf', 'at': [-3.75, z], 'rot': 3} for z in (1.2, 2.4)]
    r['props'] += [{'type': 'dining_table', 'at': [0, 1.8]}, {'type': 'chair', 'at': [-.6, 1.1], 'rot': 2}, {'type': 'chair', 'at': [.6, 2.5]}, {'type': 'lamp', 'at': [3.4, 1.0]}]
    o['anchors'] = {'table': (0, 1.8), 'rayons': (0, 4.5), 'fond': (0, 7)}
    return o

def throne_room(spec):
    o, r = _room(spec, 'salle', [10, 14], 'brick', 'marble', light='warm', light_power=1.0, height=5, ceiling='rock', ceiling_color=[96, 92, 86])
    r['wall_color'] = spec.get('wall_color', [120, 110, 100])
    r['props'] = [{'type': 'throne', 'at': [0, 12.6], 'id': 'trone'}, {'type': 'rug', 'at': [0, 6], 'color': [150, 30, 40], 'size': 1}] + \
                 [{'type': 'column', 'at': [x, z]} for x in (-3, 3) for z in (2, 5, 8, 11)] + [{'type': 'torch_wall', 'at': [x, z], 'rot': 3 if x < 0 else 1, 'light_power': .45} for x in (-4.85, 4.85) for z in (3.5, 9.5)] + \
                 [{'type': 'flag', 'at': [-1.8, 13.5], 'color': [150, 30, 40]}, {'type': 'flag', 'at': [1.8, 13.5], 'color': [150, 30, 40]}, {'type': 'chest', 'at': [3.8, 12.8], 'open': True}]
    o['anchors'] = {'trone': (0, 12.6), 'allee': (0, 6), 'entree': (0, 1), 'tresor': (3.8, 12.2)}
    return o

def attic(spec):
    o, r = _room(spec, 'grenier', [6, 7], 'wood', 'wood', dark=True, light='warm', light_power=.8, height=2.3, ceiling='wood', ceiling_color=[110, 80, 56], windows=[{'wall': 'N', 'pos': .5, 'night': spec.get('night', True)}])
    r['props'] = [{'type': 'boxes', 'at': [-2, 5]}, {'type': 'chest', 'at': [1.8, 5.5]}, {'type': 'toy', 'at': [.5, 3]}, {'type': 'mirror', 'at': [-2.9, 3], 'rot': 3}, {'type': 'boxes', 'at': [2.1, 2], 'rot': 1},
                  {'type': 'armchair', 'at': [-1.5, 1.6], 'color': [110, 90, 70]}, {'type': 'candles', 'at': [.2, 4.4]}]
    o['anchors'] = {'malle': (1.8, 5.5), 'miroir': (-2.5, 3), 'fenetre': (0, 6.6), 'centre': (0, 3.5)}
    return o

def basement(spec):
    o, r = _room(spec, 'cave', [7, 7], 'concrete', 'concrete', dark=True, light='neon', light_flicker=bool(spec.get('flicker', False)), height=2.4)
    r['props'] = [{'type': 'boxes', 'at': [-2.5, 5]}, {'type': 'shelf', 'at': [3.2, 4], 'rot': 1}, {'type': 'washing_machine', 'at': [3.2, 1.6], 'rot': 1}, {'type': 'barrel', 'at': [-3, 1.5]},
                  {'type': 'stairs', 'at': [-1.9, 3], 'rot': 3, 'height': 2.4}, {'type': 'crate', 'at': [1, 5.8]}]
    o['anchors'] = {'escalier': (.1, 3), 'fond': (0, 6), 'etagere': (2.6, 4)}
    return o

def lab(spec):
    o, r = _room(spec, 'labo', [8, 7], 'hospital', 'tiles', light='cold')
    r['props'] = [{'type': 'counter_long', 'at': [0, 3.2]}, {'type': 'computer', 'at': [-1.4, 3.2]}, {'type': 'control_panel', 'at': [0, 6.6]}, {'type': 'cage', 'at': [3, 5.6]},
                  {'type': 'crystal', 'at': [1.3, 3.2], 'size': .5}, {'type': 'whiteboard', 'at': [-3.95, 3.5], 'rot': 3, 'text': ['E = MC²']}, {'type': 'cauldron', 'at': [-2.8, 5.8], 'color': [90, 200, 255]}]
    o['anchors'] = {'paillasse': (0, 2.5), 'panneau': (0, 6), 'cage': (3, 5)}
    return o

def space_station(spec):
    o, r = _room(spec, 'station', [8, 10], 'concrete', 'tiles', light='blue', height=3)
    r['wall_color'] = [150, 156, 170]
    r['props'] = [{'type': 'control_panel', 'at': [0, 9.6]}, {'type': 'space_window', 'at': [0, 9.95]}, {'type': 'space_window', 'at': [-3.95, 5], 'rot': 3},
                  {'type': 'computer', 'at': [3, 4], 'rot': 1}, {'type': 'chair', 'at': [0, 8.6], 'rot': 2}, {'type': 'locker', 'at': [3.6, 1.5], 'rot': 1}]
    o['anchors'] = {'poste': (0, 8.6), 'hublot': (0, 9.2), 'couloir': (0, 1.5)}
    return o

def cave(spec):
    s = int(spec.get('seed', 0))
    o, r = _room(spec, 'grotte', [9, 14], 'dark', 'concrete', dark=True, light='none', height=3.2)
    r['wall_color'] = [70, 66, 62]; r['ceiling'] = 'rock'; r['ceiling_color'] = [64, 60, 56]; o['textured_ground'] = True; o['ground'] = 'rock'; r['floor'] = 'none'
    o['ambient'] = spec.get('ambient', (.16, .15, .15)); o['fill'] = spec.get('fill', .5)
    r['props'] = [{'type': 'torch_wall', 'at': [-4.4, z], 'rot': 3} for z in (3, 9)] + [{'type': 'torch_wall', 'at': [4.4, 6], 'rot': 1}] + [{'type': 'crystal', 'at': [3.5, 11], 'size': 1.2}, {'type': 'crystal', 'at': [2.8, 12.4]},
                  {'type': 'chest', 'at': [0, 12.8], 'open': spec.get('open_chest', False)}]
    r['props'] += scatter([{'type': ['rock', 'boulder', 'rock_pile'], 'count': 16, 'area': [-4, 1, 4, 13], 'min_dist': 1.8, 'avoid': [[-1.3, -1, 1.3, 14]]}], s)
    o['anchors'] = {'entree': (0, 1), 'tresor': (0, 12.2), 'cristaux': (3, 11), 'milieu': (0, 7)}
    o['ambience'] = spec.get('ambience', 'cave')
    return o

PLACES = {'forest': forest, 'snowy_forest': snowy_forest, 'beach': beach, 'island': island, 'mountain': mountain, 'desert': desert, 'city_street': city_street,
          'village': village, 'park': park, 'countryside': countryside, 'lake': lake, 'river': river, 'campsite': campsite, 'graveyard': graveyard,
          'castle': castle, 'snow_village': snow_village, 'volcano': volcano, 'bedroom': bedroom, 'kid_bedroom': kid_bedroom, 'living_room': living_room,
          'kitchen': kitchen, 'bathroom': bathroom, 'classroom': classroom, 'office': office, 'hospital_room': hospital_room, 'shop': shop_interior,
          'cafe': cafe, 'library': library, 'throne_room': throne_room, 'attic': attic, 'basement': basement, 'lab': lab, 'space_station': space_station, 'cave': cave}
DEFAULT_AMBIENCE = {'forest': 'forest', 'snowy_forest': 'snow', 'beach': 'beach', 'island': 'beach', 'mountain': 'wind', 'desert': 'wind', 'city_street': 'city',
                    'village': 'village', 'park': 'park', 'countryside': 'countryside', 'lake': 'river', 'river': 'river', 'campsite': 'campfire', 'graveyard': 'night',
                    'castle': 'village', 'snow_village': 'snow', 'volcano': 'wind', 'office': 'office', 'cafe': 'cafe', 'classroom': 'school', 'space_station': 'space',
                    'cave': 'cave', 'basement': 'cave', 'library': 'room', 'shop': 'room', 'throne_room': 'room'}

from . import ps1_worlds as _PW; _PW.register(PLACES)      # mondes nés dans VOXEL (station, bus, toit, talus, cité, astroport, Lune)
START = {'castle': (0, 3.5), 'graveyard': (0, 3.2), 'beach': (0, 1), 'island': (0, -6), 'lake': (0, 2), 'river': (0, 1), 'city_street': (0, 1)}
from . import qt_street as _QS; _QS.register(PLACES)       # quartiers à identité (qt_street.py) : lieu `quartier`, détails qt_* ; rien n'est remplacé
from . import cinema_salle as _CS; _CS.register(PLACES)    # 6/11/2026 : lieu `cinema_salle` (série « Le Cinéma des Absents », cinema_salle.py) ; rien n'est remplacé
from . import lycee_riviere as _LR; _LR.register(PLACES)   # 9/11/2026 : lieu `lycee_riviere` (série « Le Choix de Demain », lycee_riviere.py) ; rien n'est remplacé
from . import cimetiere_calme as _CC; _CC.register(PLACES) # 9/11/2026 : lieu `cimetiere_calme` (cimetière paisible, drame ; cimetiere_calme.py) ; rien n'est remplacé
from . import phare_foret as _PF; _PF.register(PLACES)     # 14/11/2026 : lieu `phare_foret` (série « Le Phare qui efface », phare_foret.py) + effet `effacement` ; rien n'est remplacé
from . import phare_interieur as _PI; _PI.register(PLACES) # 15/11/2026 : lieu `phare_interieur` (intérieur de la tour, même série, phare_interieur.py) ; rien n'est remplacé

def expand(name, spec):
    o = PLACES[name](spec or {})
    a = o.setdefault('anchors', {})
    if 'start' not in a:          # where a camera can stand to see the place
        if o.get('rooms'): r = o['rooms'][0]; a['start'] = (r['size'][0] * .3, .45)
        else: a['start'] = START.get(name, (0, 0))
    return o
