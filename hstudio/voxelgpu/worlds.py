"""What the director (B) must know about the worlds of the painter (A): a walkable rectangle, anchors, seats, the box the
camera may stand in. It is the `World` of the acting layer (acting/timeline.py), supplied by the voxel engine side.

The worlds themselves are built by engine A (sets5.js, ten of them). Coordinates are A's: x along the street (+x to the
right of a camera on the +z side), z towards the camera, y up; the camera looks towards -z, so characters facing the
camera have heading 0 and the scenery lies at negative z. Numbers come from reading sets5.js (corridors left free for the
walker at z ~ 0, benches, roads) and are checked by tests/test_voxelgpu.py (walkable, camera box, seats inside).
"""
import math
from ..acting.timeline import World

#            name        x0   z0    x1   z1     tags
_B = (-16., -3.2, 16., 3.0)
WORLDS = {
    'ville':    dict(bounds=(-16., -13., 16., 1.9), tags=['urban', 'day'], label='Ville au matin',
                     seats={}, note='trottoir de 3,8 m, route et voitures au-delà de z=-2'),
    'parc':     dict(bounds=(-16., -3.0, 16., 3.0), tags=['nature', 'day', 'spring'], label='Parc au printemps',
                     seats={'banc1': (-12., -1.55), 'banc2': (-4., -1.55), 'banc3': (4., -1.55), 'banc4': (12., -1.55)}),
    'automne':  dict(bounds=_B, tags=['nature', 'day', 'autumn'], label='Allée d\'automne'),
    'pluie':    dict(bounds=(-16., -4., 16., 1.9), tags=['urban', 'rain', 'night'], label='Ville sous la pluie'),
    'glace':    dict(bounds=_B, tags=['nature', 'snow', 'cold'], label='Glacier'),
    'feu':      dict(bounds=(-16., -7., 16., 3.0), tags=['disaster', 'fire', 'ruins'], label='Ruines en feu'),
    'bataille': dict(bounds=(-16., -6.5, 16., 3.0), tags=['war', 'day', 'field'], label='Champ de bataille'),
    'invasion': dict(bounds=(-16., -5.0, 16., 3.0), tags=['scifi', 'dusk', 'alien'], label='Invasion'),
    'vaisseau': dict(bounds=(-16., -2.4, 16., 2.4), tags=['scifi', 'interior'], label='Vaisseau spatial'),
    'lune':     dict(bounds=_B, tags=['scifi', 'space', 'night'], label='La Lune'),
    # horror kit (voxelgpu_js/engine/horror_kit.js): coordinates are the painter's, local to the world
    'station':  dict(bounds=(-4.5, -7., 4.5, 3.5), tags=['urban', 'rain', 'night', 'interior'], label='Station-service (supérette, parking, pompes)',
                     note='intérieur x[-4.5,4.5] z[-7,3.5], vitrine z=3.5, parking z>3.5, auvent et pompes vers (-11,12)'),
    'bus':      dict(bounds=(-1.4, -12.4, 1.4, .4), tags=['interior', 'night', 'vehicle'], label='Bus de nuit (intérieur)', note='allée x~0, z de 0 (arrière) à -12 (chauffeur), plancher y=0, sol extérieur y=-0.96'),
    'toit':     dict(bounds=(-6.5, -1.4, 6.5, 1.4), tags=['rain', 'night', 'roof', 'water'], label='Toit du bus sur l eau', note='dalle y=0, trappe en (2.2, 0), eau noire y=-1.2'),
    'talus':    dict(bounds=(-30., -3., 30., 12.), tags=['nature', 'rain', 'night', 'road'], label='Talus herbeux, route et bus', note='route z[-9.7,-2.3] avec le bus (x -0.5..12.5), herbe z>-3.2, tunnel en x=-62'),
    # demo narrative kit (voxelgpu_js/engine/cite_kit.js): coordinates are the painter's, local to the world; the places sit side by side in ONE frame (stagegeo.CITE_X / ASTRO_X)
    'cite':     dict(bounds=(60. - 62., -36., 60. + 62., 10.), tags=['urban', 'day', 'interior'], label='Cité (rue, café, ruelle, monte-charge)',
                     note='rue le long de x (centre x=60), trottoir nord z[-5.5,-1.5], chaussée z[-1.5,5.5], sud z[5.5,9.5] ; café intérieur x[52.2,67.8] z[-15.4,-5.9] ; ruelle x[49.6,52] ; monte-charge z=-34.5'),
    'astroport': dict(bounds=(190. - 24., -18., 190. + 18., 18.), tags=['scifi', 'roof', 'day'], label='Astroport sur un toit (navette, tour, ascenseur)', note='dalle x[112,148] z[-18,18] y=0, cabine ascenseur x[107,111.7], ville en contrebas'),
    'selene':   dict(bounds=(270. - 40., -8., 270. + 40., 8.), tags=['scifi', 'space', 'night'], label='Surface de la Lune (balise, navette posée)', note='sol y=0, navette posée en x=191 nez vers +x, balise en (208, -1)'),
    # B kit (voxelgpu_js/engine/b_kit.js) : un sol et une lumière réglables par `env` ; les décors de PIXEL 3D y sont posés par plan (b_props.py)
    'plateau':  dict(bounds=(-10., -8., 10., 8.), tags=['studio', 'interior', 'day', 'night'], label='Plateau (sol et lumière réglables, décors de PIXEL 3D posés par plan)',
                     note='sol y=0, rien d\'autre : tout vient de `props` (types de PIXEL 3D convertis, ou `room`), `env` : floor, bg, ambient, key, key_col, hemi_sky, fog'),
}
BENCH_H = .45


class VoxWorld(World):
    """the acting layer's World for one of A's worlds"""
    camera_heading = 0.             # characters facing the camera look towards +z

    def __init__(self, name, extra_anchors=None):
        if name not in WORLDS: raise KeyError(f'monde inconnu : {name!r} (disponibles : {", ".join(WORLDS)})')
        self.name = name; spec = WORLDS[name]; x0, z0, x1, z1 = spec['bounds']
        a = {'center': (0., 0.), 'left': (-5., 0.), 'right': (5., 0.), 'far_left': (-10., 0.), 'far_right': (10., 0.),
             'near': (0., z1 - .6), 'far': (0., z0 + .6), 'near_left': (-4., z1 - .6), 'near_right': (4., z1 - .6),
             'back_left': (-4., z0 + .6), 'back_right': (4., z0 + .6),
             'offscreen_left': (x0 - 2., 0.), 'offscreen_right': (x1 + 2., 0.)}
        a.update({k: tuple(v) for k, v in (extra_anchors or {}).items()})
        super().__init__(anchors=a, bounds=(x0 - 4., z0 - 1., x1 + 4., z1 + 1.))   # bounds of the A* grid; walking stays in the rectangle
        self.rect = spec['bounds']; self.seats = dict(spec.get('seats') or {})
        # the sides of the rectangle are not walls for paths that cross it, only for the planner's grid
        for k, (sx, sz) in self.seats.items(): self.a.setdefault(k, (sx, sz + .9))

    def _geo(self):
        """la géométrie de `stagegeo.py` pour les mondes dont elle existe (station : murs, rayons, comptoir, vitrine, portes) : le cinématographe ne place plus la caméra dans un mur"""
        if not hasattr(self, '_g'):
            from . import stagegeo
            self._g = stagegeo.station(None) if self.name == 'station' else None
        return self._g

    def obstacles(self):
        g = self._geo()
        return g.body_rects() if g is not None else []

    def seat(self, name):
        s = self.seats.get(name)
        return None if s is None else (s[0], s[1], 0., BENCH_H)          # bench back at -z: sitting people face +z (the camera)

    def camera_box(self):
        x0, z0, x1, z1 = self.rect
        if self.name == 'bus': return (x0 + .15, z0 + .2, x1 - .15, z1 - .1, .4, 2.3)       # dans le bus : l'allée fait 2,8 m de large, la caméra de dehors voyait les vitres noires
        if self.name == 'station': return (x0 - 6., z0, x1 + 6., z1 + 9., .3, 5.)             # la supérette et le parking devant la vitrine
        return (x0 - 12., -9., x1 + 12., 14., .25, 14.)                  # x0, z0, x1, z1, ymin, ymax

    def blocked_for_camera(self, p):
        bx0, bz0, bx1, bz1, y0, y1 = self.camera_box()
        if not (bx0 <= p[0] <= bx1 and bz0 <= p[2] <= bz1 and y0 <= p[1] <= y1): return True
        g = self._geo()
        return g is not None and g.solid_at_point(p, .2) is not None                     # jamais à l'intérieur d'un mur, d'un rayon ou du comptoir
