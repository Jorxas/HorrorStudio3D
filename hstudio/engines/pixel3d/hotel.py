"""CHAMBRE 313 : le lieu `hotel_nuit` du style PS1 (PIXEL 3D), un hôtel de nuit praticable d'un seul tenant.

Repère PIXEL 3D : x vers la droite quand on regarde vers +z, y vers le haut, mètres. Le rez-de-chaussée est à y = 0 ; la cour de
derrière (où descend l'escalier de secours, où se gare le camion) est en contrebas, à y = YARD = -1,8 (le plan du sol du moteur).

    z < 0          la rue de devant (vue à travers la porte vitrée)
    0 .. 9         le hall et la réception (comptoir à l'ouest, x = -3,4 ; le réceptionniste se tient vers x = -5,4)
    9 .. 26        le couloir (x de -1,2 à 1,2) : portes 01 à 08, porte de l'escalier principal (sud) à z = 10, mur est
    24,6           la cloison de chantier ; derrière elle, à z = 26, la vieille porte verte et le panneau rouge (à sa gauche)
    26,3 .. 30     le palier métallique et l'escalier extérieur qui descend dans la cour (y = -1,8)
    30 .. 43       la cour, la rue de derrière, le camion de pompiers ; la façade nord fait 4 niveaux (fenêtre murée au 3e)
    x ≈ 40         le couloir du 3e étage (porte 313), à part : murée aujourd'hui (`era: "now"`), normale vingt ans plus tôt (`era: "before"`)

Le lieu s'appelle `hotel_nuit` (`"sets": {"hotel": {"type": "hotel_nuit"}}`). Tout ce qui change se pilote par la clé `state` du plan
(ou `state_track`), voir `DEFAULTS` et `docs/FORMAT_EPISODE.md` (« Hôtel de nuit — Chambre 313 »). La fumée est un volume peint
après le lancer de rayons (`hotel_smoke.py`) : elle n'existe que si une clé de fumée est > 0. Rien d'aléatoire, aucune horloge :
tout dépend du temps du film et de l'état écrit."""
import math, copy, functools
import numpy as np
from PIL import Image, ImageDraw
from .r3d import B, C, Box, Scene, orient, M_WOODV, M_PLASTER, M_METAL, M_CEIL, M_DOOR, M_CARD, M_FABRIC, M_CLEAN, M_CEIL_CLEAN, vnoise2, fbm, h2
from . import hotel_cast as HC
from .hotel_cast import mini_text, mini_width, big_text, seg7, font

# ------------------------------------------------------------------ layout (metres)
YARD = -1.8                                   # back yard / street level (the engine's ground plane)
LX0, LZ0, LX1, LZ1, LH = -7.0, 0.0, 4.7, 9.0, 3.0     # lobby
CX, CZ0, CZ1, CH = 1.2, 9.0, 26.0, 2.7        # corridor half-width, start, inner face of the north facade, height
CLZ = 24.6                                    # building-site partition
GD = (-.45, .45)                              # green door opening (x)
RP = (-.8, 1.38)                              # red emergency panel centre (x, y) on the north wall, LEFT of the green door
SD = (9.6, 10.5)                              # main (south) stair door opening (z) in the east corridor wall
SW = (1.3, 9.1, 4.6, 12.0)                    # stairwell box
ROOMS = (('01', 1, 13.5), ('02', -1, 12.0), ('03', 1, 16.5), ('04', -1, 15.0), ('05', 1, 19.5), ('06', -1, 18.0), ('07', 1, 22.5), ('08', -1, 21.0))
RW = 4.7                                      # back walls of the rooms (x = +-RW)
BX0, BX1, TOP = -7.3, 5.0, 12.6               # building shell (x) and roof height
FZ = 26.3                                     # outer face of the north facade
LAND = 27.3                                   # outer edge of the metal landing
STEP_N, STEP_R, STEP_D = 10, .18, .28         # exterior stair: 10 risers of 18 cm, treads of 28 cm (bottom at z = 30.1)
STAIR_X = .62                                 # half width of the exterior stair
TRUCK = (-2.4, 36.0)                          # fire truck centre (x, z) when `truck_x` = 0; it faces -x
X3 = 40.0                                     # the 3rd-floor corridor (separate set piece)
D313 = 7.5                                    # door 313 (z) on the west wall of the 3rd-floor corridor
BAYS = (-5.6, -3.2, 0.0, 2.6)                 # window bays of the north facade
WALLED = (-3.2, 3)                            # bay and floor of the walled window (room 313)
FIRE_WINDOWS = ((0.0, 1), (2.6, 1), (2.6, 2))  # windows that glow and smoke (`window_fire`, `window_smoke`)
DESK_Y = .78; COUNTER = (-4.1, -3.4, 2.4, 7.2)     # counter front panel x0 x1 z0 z1
PHONE_COL, PHONE_DARK = (122, 34, 36), (60, 18, 20)    # the reception phone (burgundy) and its handset (hotel_cast `handset` has the same colour)
PHONE = (-4.42, 5.85); MONITOR = (-4.5, 4.75); BOARD = (-4.55, 3.55); LAMP = (-4.62, 6.72)
CLOCK = (5.8, 2.2); PLAN = (4.85, 1.62); PANEL = (5.8, 1.38); KEYS = (3.45, 1.66)    # back wall items: (z, y) centres on x = LX0
ALARM_BTN = (-1.19, 9.75)                     # manual call point (x, z), y = 1.4
TOOLBOX = (.82, 24.05)

ANCHORS = {
    'entree': (0., .6), 'hall': (0., 4.5), 'reception': (-3.0, 4.6), 'comptoir': (-3.75, 4.6), 'derriere_comptoir': (-5.4, 4.6),
    'standard': BOARD, 'telephone': PHONE, 'ecran': MONITOR, 'horloge': (-6.9, CLOCK[0]), 'plan_evacuation': (-6.9, PLAN[0]),
    'panneau_electrique': (-6.9, PANEL[0]), 'tableau_cles': (-6.9, KEYS[0]), 'fauteuils': (3.4, 3.7),
    'couloir.debut': (0., 9.6), 'couloir.milieu': (0., 17.0), 'couloir.fond': (0., 23.6), 'bouton_alarme': ALARM_BTN,
    'porte_escalier_sud': (1.2, 10.05), 'poignee_escalier_sud': (.95, 10.4), 'escalier_sud': (2.9, 10.6),
    'cloison': (0., CLZ), 'devant_cloison': (0., 23.7), 'caisse_outils': TOOLBOX, 'porte_verte': (0., 26.0), 'panneau_rouge': (RP[0], 25.9),
    'palier': (0., 26.8), 'escalier_ext.haut': (0., 27.4), 'escalier_ext.bas': (0., 30.4), 'cour': (0., 31.5), 'camion': TRUCK,
    'rue_derriere': (0., 37.5), 'facade': (0., 33.0),
    'etage3': (X3, 2.0), 'etage3.milieu': (X3, 6.0), 'porte_313': (X3 - 1.3, D313), 'devant_313': (X3 - .5, D313),
    'start': (1.6, 1.2),
}
for _n, _s, _z in ROOMS:
    ANCHORS[f'porte_{_n}'] = (_s * CX, _z); ANCHORS[f'devant_{_n}'] = (_s * .55, _z); ANCHORS[f'chambre_{_n}'] = (_s * 2.6, _z)
ANCHOR_Y = {'palier': 0., 'escalier_ext.haut': 0., 'escalier_ext.bas': YARD, 'cour': YARD, 'camion': YARD, 'rue_derriere': YARD, 'facade': YARD}

DEFAULTS = dict(
    moment='nuit', power=1., lobby=1., ceiling=1., ceiling_flicker=0., emergency=0., alarm=0., alarm_rate=1.1, alarm_button=0.,
    landline=1, landline_ring=0., handset=1, board_313=0., board_blink=0., board_lamps=(), screen='idle', screen_lines=None,
    clock='02:13', clock_on=1., panel_led=0., door_01=0., door_02=0., door_03=0., door_04=0., door_05=0., door_06=0., door_07=0.,
    door_08=0., room_lights=1., stair_door=0., stair_fire=0., smoke=0., smoke_low=1.9, smoke_black=0., smoke_front=None,
    smoke_burst=0., stair_smoke=None, cloison=0., cloison_hit=0., crowbar_in_box=1, red_glass=0., lever=0., green_door=0.,
    truck=0, truck_x=0., beacons=0., window_fire=0., window_smoke=0., hoses=0, street_lights=1.,
    era='now', under_door_smoke=0., under_door_glow=0., work_lamp=0., log_paper=0, covers=0, barrier=0, soot=0., lobby_dim=0.)
MORNING = dict(power=0., lobby=0., ceiling=0., screen='off', clock_on=0., log_paper=1, covers=1, barrier=1, soot=1., landline_ring=0.,
               street_lights=0., room_lights=0.)

ZONE_OUT, ZONE_LOBBY, ZONE_COR, ZONE_ROOM, ZONE_STAIR, ZONE_THIRD = range(6)


def _zw(*on, spill=None):
    """zone weights of a light: 1 in its zones, `spill` elsewhere listed as {zone: w}"""
    w = [0.] * 6
    for z in on: w[z] = 1.
    for z, v in (spill or {}).items(): w[z] = v
    return tuple(w)


# ================================================================== textures
def _rgba(w, h, col):
    im = Image.new('RGBA', (int(w), int(h)), tuple(col) + (255,)); return im, ImageDraw.Draw(im)


@functools.lru_cache(maxsize=32)
def wall_tex(npx, kind='corridor', h=32):
    """corridor / lobby wall: wallpaper above a chair rail, dark wood panelling below (one texture per wall length)"""
    W = max(4, int(npx))
    if kind == 'corridor': paper, stripe, rail, wood, wood2 = (150, 126, 96), (128, 100, 76), (92, 60, 40), (78, 48, 32), (64, 38, 26)
    elif kind == 'lobby': paper, stripe, rail, wood, wood2 = (52, 78, 66), (44, 66, 56), (150, 116, 60), (70, 44, 30), (58, 36, 24)
    elif kind == 'stair': paper, stripe, rail, wood, wood2 = (150, 150, 140), (140, 140, 132), (40, 120, 60), (110, 110, 104), (100, 100, 96)
    elif kind == 'room': paper, stripe, rail, wood, wood2 = (170, 150, 120), (160, 140, 112), (120, 96, 70), (150, 132, 104), (140, 122, 96)
    elif kind == 'old': paper, stripe, rail, wood, wood2 = (120, 100, 84), (104, 84, 70), (80, 52, 34), (70, 44, 30), (58, 36, 24)
    else: paper, stripe, rail, wood, wood2 = (152, 148, 140), (144, 140, 132), (128, 124, 116), (124, 120, 112), (116, 112, 104)
    im, d = _rgba(W, h, paper)
    for x in range(0, W, 4): d.line([(x, 0), (x, h - 1)], fill=stripe + (255,))
    if kind in ('corridor', 'lobby', 'old'):
        for x in range(2, W, 8):
            for y in range(3, int(h * .6), 6): d.point((x, y), fill=tuple(min(255, c + 22) for c in paper) + (255,))
    yr = int(h * .64)
    d.rectangle([0, yr, W - 1, yr + 1], fill=rail + (255,))
    d.rectangle([0, yr + 2, W - 1, h - 1], fill=wood + (255,))
    for x in range(0, W, 7): d.rectangle([x, yr + 4, x + 5, h - 3], outline=wood2 + (255,))
    d.rectangle([0, h - 2, W - 1, h - 1], fill=(30, 22, 18, 255))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def carpet_tex(L=17.0, kind='corridor'):
    W, H = 30, int(L * 14)
    base, edge, motif = ((96, 22, 30), (150, 110, 50), (126, 40, 42)) if kind == 'corridor' else ((40, 50, 90), (150, 130, 80), (60, 74, 120))
    im, d = _rgba(W, H, base)
    d.rectangle([0, 0, 2, H - 1], fill=edge + (255,)); d.rectangle([W - 3, 0, W - 1, H - 1], fill=edge + (255,))
    for y in range(4, H, 10):
        cx = W // 2; d.polygon([(cx, y), (cx + 5, y + 5), (cx, y + 10), (cx - 5, y + 5)], outline=motif + (255,))
        d.point((cx, y + 5), fill=edge + (255,))
    return np.array(im)


@functools.lru_cache(maxsize=2)
def marble_tex(nx=24, nz=18):
    """lobby floor: cream / black checker with a border"""
    W, H = nx * 6, nz * 6
    im, d = _rgba(W, H, (180, 170, 150))
    for i in range(nx):
        for j in range(nz):
            if (i + j) % 2: d.rectangle([i * 6, j * 6, i * 6 + 5, j * 6 + 5], fill=(34, 32, 32, 255))
            else:
                d.rectangle([i * 6, j * 6, i * 6 + 5, j * 6 + 5], fill=(186, 176, 156, 255)); d.point((i * 6 + (i * 7 + j * 3) % 5, j * 6 + 2), fill=(160, 150, 134, 255))
    d.rectangle([0, 0, W - 1, H - 1], outline=(70, 40, 30, 255)); d.rectangle([1, 1, W - 2, H - 2], outline=(70, 40, 30, 255))
    return np.array(im)


@functools.lru_cache(maxsize=2)
def concrete_tex(w=24, h=24, seed=3):
    r = np.random.default_rng(seed); a = np.full((h, w, 4), 255, np.uint8)
    g = (104 + r.integers(-10, 11, (h, w))).astype(np.uint8); a[..., 0] = g; a[..., 1] = g; a[..., 2] = (g * .96).astype(np.uint8)
    return a


@functools.lru_cache(maxsize=4)
def switchboard_tex():
    """the old switchboard: floors 0..3 x rooms 01..13, one lamp each (all off here: the lit ones are separate boxes)"""
    W, H = 72, 40
    im, d = _rgba(W, H, (54, 50, 44))
    d.rectangle([0, 0, W - 1, 6], fill=(30, 28, 26, 255)); mini_text(d, 2, 1, 'STANDARD', (200, 180, 120, 255))
    for c in range(13): mini_text(d, 9 + c * 5 - (2 if c >= 9 else 0), 8, str(c + 1) if c < 9 else '', (170, 160, 130, 255))
    for r_ in range(4):
        y = 15 + r_ * 6; mini_text(d, 2, y - 1, str(r_), (200, 180, 120, 255))
        for c in range(13):
            x = 9 + c * 5; d.rectangle([x, y, x + 2, y + 2], fill=(26, 20, 16, 255)); d.point((x + 1, y + 1), fill=(70, 50, 30, 255))
    mini_text(d, W - 15, 15 + 3 * 6 + 4, '313', (230, 210, 150, 255))
    d.rectangle([0, H - 3, W - 1, H - 1], fill=(30, 28, 26, 255))
    return np.array(im)


def board_lamp_uv(num):
    """(u, v) in 0..1 of the lamp of room `num` ("313") on the switchboard texture"""
    fl, rm = int(str(num)[0]), int(str(num)[1:])
    x = 9 + (rm - 1) * 5 + 1.5; y = 15 + fl * 6 + 1.5
    return x / 72., y / 40.


@functools.lru_cache(maxsize=32)
def screen_tex(mode='idle', clock='02:13', lines=None):
    W, H = 64, 48
    im, d = _rgba(W, H, (6, 10, 14))
    if mode == 'off': return np.array(im)
    if mode == 'call':
        d.rectangle([0, 0, W - 1, 8], fill=(160, 30, 24, 255)); mini_text(d, 3, 2, 'APPEL ENTRANT', (255, 236, 220, 255))
        big_text(d, 8, 13, 'CH', (120, 230, 150, 255)); big_text(d, 26, 13, '313', (255, 220, 120, 255))
        mini_text(d, 4, 28, 'APPEL', (120, 200, 140, 255)); mini_text(d, 28, 28, clock, (255, 255, 255, 255))
        mini_text(d, 4, 36, 'LIGNE 313 INT', (90, 160, 110, 255))
        d.rectangle([0, H - 4, W - 1, H - 1], fill=(30, 60, 40, 255))
    elif mode == 'log':
        rows = lines or ('23:52 CH106 00:18', '00:37 EXT   01:04', '02:13 CH313 00:47')
        mini_text(d, 2, 2, 'JOURNAL', (120, 220, 150, 255))
        for i, l in enumerate(rows[:6]): mini_text(d, 2, 10 + i * 7, l, (255, 120, 100, 255) if '313' in l else (150, 210, 170, 255))
    else:                                                    # idle: night booking screen
        d.rectangle([0, 0, W - 1, 8], fill=(26, 60, 110, 255)); mini_text(d, 3, 2, 'RECEPTION', (220, 230, 255, 255))
        mini_text(d, W - mini_width(clock) - 2, 2, clock, (255, 255, 255, 255))
        for i, l in enumerate(lines or ('NUIT  31/10', 'CLIENTS 6', 'ARRIVEES 0', 'ETAGE 3 FERME')):
            mini_text(d, 3, 12 + i * 8, l, (150, 190, 240, 255) if 'FERME' not in l else (240, 170, 90, 255))
    return np.array(im)


@functools.lru_cache(maxsize=16)
def clock_tex(hhmm='02:13', on=True):
    W, H = 54, 20
    im, d = _rgba(W, H, (10, 8, 8))
    if on: seg7(d, 4, 4, hhmm, (255, 56, 40, 255), dim=(26, 10, 9, 255), w=7, h=12, t=2)
    else: seg7(d, 4, 4, '88:88', (22, 11, 10, 255), w=7, h=12, t=2)
    return np.array(im)


@functools.lru_cache(maxsize=1)
def plan_tex():
    """the old evacuation plan (framed, behind the reception): the ground floor seen from above, north up; the north stair
    (the one the works condemned) is still drawn in green, with the arrows that lead to it; a red dot: you are here"""
    W, H = 104, 84
    im, d = _rgba(W, H, (232, 228, 212))
    d.rectangle([0, 0, W - 1, 10], fill=(28, 128, 66, 255)); t = "PLAN D'EVACUATION"; mini_text(d, (W - mini_width(t)) // 2, 3, t, (255, 255, 255, 255))
    zs = 2.45; xs = 2.45; ox = 6 - LX0 * xs; oy = 80                                          # metres -> texels, north (z) up
    def P(x, z): return (int(round(ox + x * xs)), int(round(oy - z * zs)))
    ink = (40, 40, 52, 255)
    d.rectangle([*P(LX0, LZ1)[:1], P(LX0, LZ1)[1], *P(LX1, LZ0)], outline=ink)                   # lobby
    d.rectangle([P(-CX, 26.)[0], P(-CX, 26.)[1], P(CX, 9.)[0], P(CX, 9.)[1]], fill=(250, 248, 236, 255), outline=ink)   # corridor
    for n, s_, z in ROOMS:
        x0, x1 = (CX, RW) if s_ > 0 else (-RW, -CX)
        a, b = P(x0, z + 1.5), P(x1, z - 1.5); d.rectangle([min(a[0], b[0]), a[1], max(a[0], b[0]), b[1]], outline=(130, 130, 140, 255))
    a, b = P(SW[0], SW[3]), P(SW[2], SW[1]); d.rectangle([a[0], a[1], b[0], b[1]], fill=(150, 220, 170, 255), outline=(28, 128, 66, 255))
    gx, gy = P(0, 26.4); d.rectangle([gx - 5, gy - 5, gx + 5, gy], fill=(40, 190, 90, 255), outline=(20, 100, 50, 255))   # north stair
    for zz in (12.5, 16.0, 19.5, 23.0):                                                          # arrows up the corridor
        ax, ay = P(0, zz); d.polygon([(ax, ay - 4), (ax - 3, ay), (ax + 3, ay)], fill=(28, 150, 74, 255)); d.line([(ax, ay), (ax, ay + 4)], fill=(28, 150, 74, 255))
    rx, ry = P(-4.4, 4.6); d.ellipse([rx - 3, ry - 3, rx + 3, ry + 3], fill=(220, 30, 30, 255))
    lx = 46                                                                                       # legend on the right
    d.rectangle([lx, 16, lx + 6, 21], fill=(40, 190, 90, 255)); mini_text(d, lx + 9, 16, 'ESCALIER', (28, 110, 60, 255)); mini_text(d, lx + 9, 23, 'NORD', (28, 110, 60, 255))
    d.rectangle([lx, 34, lx + 6, 39], fill=(150, 220, 170, 255)); mini_text(d, lx + 9, 34, 'ESCALIER', (28, 110, 60, 255)); mini_text(d, lx + 9, 41, 'SUD', (28, 110, 60, 255))
    d.ellipse([lx, 52, lx + 6, 58], fill=(220, 30, 30, 255)); mini_text(d, lx + 9, 52, 'VOUS ETES', (190, 30, 30, 255)); mini_text(d, lx + 9, 59, 'ICI', (190, 30, 30, 255))
    mini_text(d, lx, 72, 'REZ-DE-CH.', (90, 90, 96, 255))
    d.rectangle([0, 0, W - 1, H - 1], outline=(60, 50, 40, 255))
    return np.array(im)


@functools.lru_cache(maxsize=1)
def keypad_tex():
    im, d = _rgba(10, 14, (40, 14, 16))
    for r_ in range(4):
        for c in range(3): d.rectangle([1 + c * 3, 1 + r_ * 3, 2 + c * 3, 2 + r_ * 3], fill=(214, 206, 190, 255))
    return np.array(im)


@functools.lru_cache(maxsize=1)
def keys_tex():
    W, H = 48, 28
    im, d = _rgba(W, H, (96, 60, 38))
    for x in range(0, W, 3): d.line([(x, 0), (x, H - 1)], fill=(88, 54, 34, 255))
    for r_ in range(3):
        for c in range(8):
            x, y = 3 + c * 6, 3 + r_ * 9
            d.rectangle([x + 1, y, x + 2, y + 1], fill=(200, 170, 80, 255))
            if not (r_ == 2 and c == 7): d.rectangle([x, y + 2, x + 3, y + 6], fill=(214, 200, 150, 255)); d.point((x + 1, y + 4), fill=(140, 40, 30, 255))
    mini_text(d, W - 15, H - 8, '313', (240, 200, 120, 255))
    return np.array(im)


@functools.lru_cache(maxsize=1)
def panel_door_tex():
    W, H = 24, 32
    im, d = _rgba(W, H, (150, 152, 150))
    d.rectangle([1, 1, W - 2, H - 2], outline=(110, 112, 110, 255))
    d.polygon([(12, 5), (19, 17), (5, 17)], fill=(240, 190, 30, 255), outline=(20, 20, 20, 255))
    d.line([(12, 8), (10, 12), (14, 12), (12, 15)], fill=(20, 20, 20, 255))
    mini_text(d, 3, 21, 'ELEC', (40, 40, 44, 255))
    d.rectangle([W - 5, 14, W - 3, 18], fill=(60, 60, 64, 255))
    return np.array(im)


@functools.lru_cache(maxsize=8)
def sign_tex(kind):
    if kind == 'reception':
        im, d = _rgba(80, 12, (40, 26, 18)); w = mini_width('RECEPTION', 2); mini_text(d, (80 - w) // 2, 1, 'RECEPTION', (226, 186, 90, 255), 2)
    elif kind == 'sortie':
        im, d = _rgba(40, 12, (16, 120, 56)); mini_text(d, 3, 4, 'SORTIE', (230, 255, 236, 255))
        d.polygon([(30, 3), (36, 6), (30, 9)], fill=(230, 255, 236, 255)); d.rectangle([26, 5, 30, 7], fill=(230, 255, 236, 255))
    elif kind == 'escalier':
        im, d = _rgba(40, 10, (20, 110, 60)); mini_text(d, 3, 3, 'ESCALIER', (236, 255, 240, 255))
    elif kind == 'chantier':
        im, d = _rgba(40, 28, (236, 196, 30))
        for x in range(-28, 40, 8): d.line([(x, 27), (x + 10, 17)], fill=(20, 20, 20, 255), width=3)
        d.rectangle([2, 2, 37, 15], fill=(236, 196, 30, 255)); mini_text(d, 4, 3, 'CHANTIER', (20, 20, 20, 255)); mini_text(d, 4, 9, 'INTERDIT', (180, 20, 20, 255))
    elif kind == 'nord':
        im, d = _rgba(52, 8, (60, 64, 58)); t = 'ESCALIER N.'; mini_text(d, (52 - mini_width(t)) // 2, 2, t, (190, 196, 180, 255))
    elif kind == 'alarme':
        im, d = _rgba(16, 16, (200, 28, 24)); d.rectangle([2, 2, 13, 13], outline=(240, 220, 220, 255)); d.ellipse([5, 5, 10, 10], fill=(240, 230, 230, 255))
    elif kind == 'urgence':
        im, d = _rgba(32, 10, (210, 200, 180)); mini_text(d, 1, 0, 'BRISER', (180, 20, 20, 255)); mini_text(d, 1, 5, 'LA VITRE', (40, 40, 40, 255))
    elif kind == 'hotel':
        im, d = _rgba(8, 40, (30, 10, 10))
        for i, ch in enumerate('HOTEL'): mini_text(d, 2, 2 + i * 7, ch, (255, 70, 60, 255))
    elif kind == 'prive':
        im, d = _rgba(20, 6, (180, 150, 90)); mini_text(d, 1, 0, 'PRIVE', (40, 30, 20, 255))
    elif kind == 'baes':
        im, d = _rgba(24, 8, (236, 236, 232)); d.rectangle([2, 2, 21, 5], fill=(30, 160, 80, 255)); mini_text(d, 3, 2, 'SORTIE', (240, 255, 240, 255))
    elif kind == 'condamne':
        im, d = _rgba(40, 16, (0, 0, 0)); im.putalpha(0); d = ImageDraw.Draw(im)
        mini_text(d, 4, 2, '313', (200, 30, 30, 230), 2); mini_text(d, 1, 12, 'CONDAMNE', (200, 30, 30, 200))
    else: im, d = _rgba(8, 8, (128, 128, 128))
    return np.array(im)


@functools.lru_cache(maxsize=1)
def _paper_flat():
    """the printed log lying flat on the counter, readable from the lobby side (a reader at +x looking towards -x):
    on a +y face, texture columns follow x and rows follow z, so the readable page is simply transposed; a touch darker so it does not burn"""
    a = np.transpose(HC.log_tex(), (1, 0, 2)).astype(np.float32)
    a[..., :3] *= .82
    return np.ascontiguousarray(a.astype(np.uint8))


@functools.lru_cache(maxsize=1)
def walled_tex():
    """door 313 today: concrete blocks in the frame, the number and CONDAMNE sprayed in red paint, with drips"""
    im = Image.fromarray(blocks_tex(32, 64)); d = ImageDraw.Draw(im); red = (176, 26, 22, 255)
    mini_text(d, 5, 18, '313', red, 2)
    for x, l in ((7, 6), (15, 3), (24, 7)): d.line([(x, 28), (x, 28 + l)], fill=red)
    mini_text(d, 1, 40, 'CONDAMNE', red)
    d.line([(1, 47), (30, 45)], fill=red)
    return np.array(im)


@functools.lru_cache(maxsize=1)
def _lever_plate_tex():
    im, d = _rgba(28, 30, (236, 226, 200))
    mini_text(d, 5, 2, 'TIRER', (180, 24, 20, 255))
    d.polygon([(10, 25), (6, 19), (14, 19)], fill=(180, 24, 20, 255)); d.rectangle([9, 13, 11, 19], fill=(180, 24, 20, 255))
    mini_text(d, 5, 8, 'ESC.N', (40, 40, 40, 255))
    return np.array(im)


@functools.lru_cache(maxsize=16)
def plate_tex(num, old=False):
    im, d = _rgba(16, 8, (196, 160, 70) if not old else (170, 136, 60))
    d.rectangle([0, 0, 15, 7], outline=(120, 90, 30, 255)); w = mini_width(num); mini_text(d, (16 - w) // 2, 2, num, (40, 26, 10, 255))
    return np.array(im)


@functools.lru_cache(maxsize=2)
def door_tex(kind='room'):
    """room door leaf (seen from the corridor): two raised panels"""
    W, H = 14, 32
    base = (98, 60, 40) if kind == 'room' else (110, 70, 44)
    im, d = _rgba(W, H, base)
    for (y0, y1) in ((3, 13), (16, 29)): d.rectangle([2, y0, W - 3, y1], outline=tuple(int(c * .72) for c in base) + (255,))
    return np.array(im)


@functools.lru_cache(maxsize=1)
def green_door_tex():
    W, H = 18, 40
    im, d = _rgba(W, H, (52, 104, 70)); r = np.random.default_rng(13)
    for _ in range(40):
        x, y = int(r.integers(0, W)), int(r.integers(0, H)); d.point((x, y), fill=(88, 70, 46, 255))
    for x in (3, 9, 15):
        for y in range(H - 12, H, 2): d.point((x + int(r.integers(-1, 2)), y), fill=(110, 64, 34, 255))
    d.rectangle([1, 1, W - 2, H - 2], outline=(40, 80, 54, 255))
    d.rectangle([2, 14, W - 3, 25], outline=(44, 90, 60, 255))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def blocks_tex(w=16, h=24, kind='parpaing'):
    """concrete blocks (the walled door / window) with mortar joints"""
    if kind == 'brick': base, joint, bw, bh = (130, 66, 50), (150, 140, 128), 6, 3
    elif kind == 'clair': base, joint, bw, bh = (176, 174, 166), (120, 118, 112), 8, 4
    else: base, joint, bw, bh = (134, 132, 124), (100, 98, 92), 8, 4
    im, d = _rgba(w, h, joint); r = np.random.default_rng(7)
    for row in range(0, h, bh):
        off = (bw // 2) if (row // bh) % 2 else 0
        for x in range(-off, w, bw):
            c = tuple(int(v + r.integers(-10, 11)) for v in base)
            d.rectangle([x + 1, row + 1, x + bw - 1, row + bh - 1], fill=c + (255,))
    return np.array(im)


@functools.lru_cache(maxsize=2)
def facade_tex(W=148, H=174):
    """north facade, 12 px/m: rendered plaster with floor bands, stains running from the sills"""
    im, d = _rgba(W, H, (150, 138, 120)); r = np.random.default_rng(21)
    for y in range(H):
        for x in range(0, W, 3):
            if r.random() < .08: d.point((x, y), fill=(140, 128, 112, 255))
    for lvl in range(5):
        y = int(H - (lvl * 3.0 - YARD) * 12) - 1
        d.rectangle([0, y - 1, W - 1, y + 1], fill=(124, 112, 98, 255))
    d.rectangle([0, H - int(-YARD * 12) - 2, W - 1, H - 1], fill=(96, 92, 86, 255))                 # plinth (stone)
    for x in range(0, W, 10): d.line([(x, H - int(-YARD * 12)), (x, H - 1)], fill=(80, 78, 72, 255))
    return np.array(im)


@functools.lru_cache(maxsize=8)
def window_tex(kind='dark', seed=0):
    W, H = 12, 16; r = np.random.default_rng(abs(int(seed)))
    if kind == 'lit': im, d = _rgba(W, H, (190, 150, 90)); d.rectangle([0, 0, 2, H - 1], fill=(150, 60, 50, 255)); d.rectangle([W - 3, 0, W - 1, H - 1], fill=(150, 60, 50, 255))
    elif kind == 'blind': im, d = _rgba(W, H, (40, 44, 56)); [d.line([(0, y), (W - 1, y)], fill=(70, 74, 86, 255)) for y in range(1, H, 2)]
    else:
        im, d = _rgba(W, H, (18, 22, 34)); d.rectangle([0, 0, 2 + int(r.integers(0, 2)), H - 1], fill=(40, 34, 44, 255))
        d.line([(W - 3, 1), (W - 6, 6)], fill=(60, 70, 96, 255))
    d.line([(W // 2, 0), (W // 2, H - 1)], fill=(200, 200, 196, 255)); d.line([(0, H // 2), (W - 1, H // 2)], fill=(200, 200, 196, 255))
    return np.array(im)


@functools.lru_cache(maxsize=2)
def truck_side_tex():
    W, H = 96, 16
    im, d = _rgba(W, H, (196, 22, 24))
    d.rectangle([0, 9, W - 1, 11], fill=(236, 236, 236, 255))
    for x in range(30, W - 2, 16):
        d.rectangle([x, 1, x + 14, 8], fill=(170, 172, 176, 255))
        for y in range(2, 8, 2): d.line([(x + 1, y), (x + 13, y)], fill=(130, 132, 138, 255))
    mini_text(d, 3, 2, 'POMPIERS', (255, 255, 255, 255)); mini_text(d, 4, 12, '18', (30, 30, 30, 255))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def street_tex(W=100, H=64):
    im, d = _rgba(W, H, (40, 40, 44)); r = np.random.default_rng(5)
    d.rectangle([0, H - 12, W - 1, H - 1], fill=(92, 90, 86, 255))                                   # sidewalk at the hotel side (south edge = row H-1? no: +y rows go with z)
    for x in range(0, W, 4): d.line([(x, H - 12), (x, H - 1)], fill=(80, 78, 74, 255))
    for x in range(0, W, 12): d.rectangle([x, H - 34, x + 6, H - 33], fill=(180, 170, 120, 255))
    d.rectangle([0, 0, W - 1, 8], fill=(86, 84, 80, 255))
    return np.array(im)


@functools.lru_cache(maxsize=2)
def grating_tex():
    im, d = _rgba(12, 12, (40, 42, 46))
    for i in range(0, 12, 3): d.line([(i, 0), (i, 11)], fill=(84, 88, 94, 255)); d.line([(0, i), (11, i)], fill=(70, 74, 80, 255))
    return np.array(im)


# ================================================================== ground (back yard / street plane at YARD) and AO
def floor_fn(P):
    x, z = P[:, 0], P[:, 2]; n = len(x)
    g = .7 + .3 * fbm(x * 1.4, z * 1.4, 31, 3)
    alb = np.array((.075, .075, .085), np.float32)[None] * g[:, None]
    court = (z > FZ) & (z < 32.4)
    pav = np.array((.24, .23, .22), np.float32)[None] * (.85 + .2 * vnoise2(x * 3, z * 3, 47))[:, None]
    pj = (np.abs(x / .5 - np.round(x / .5)) < .05) | (np.abs(z / .5 - np.round(z / .5)) < .05)
    pav[pj] *= .55
    alb = np.where(court[:, None], pav, alb)
    curb = (z >= 32.4) & (z < 32.6); alb[curb] = (.30, .30, .29)
    dash = (np.abs(z - 37.0) < .07) & (((x / 3.) % 1) < .5); alb[dash] = (.55, .52, .4)
    far = z > 41.4; alb[far] = np.array((.2, .2, .2), np.float32) * g[far][:, None]
    pud = fbm(x * .45 + 3, z * .45, 33, 3)
    refl = np.where(pud > .55, .5, .22).astype(np.float32); refl = np.where(court, np.where(pud > .62, .35, .1), refl)
    alb = np.where(((pud > .55) & ~court)[:, None], alb * .6, alb)
    return alb.astype(np.float32), refl


def ao_fn(P, nrm, ib):
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    ao = np.ones(len(x), np.float32)
    vert = (ib >= 0) & (np.abs(nrm[:, 1]) < .5)
    if vert.any():
        yv = y[vert]; base = np.where(yv < -.05, YARD, np.where(x[vert] > 30, 0., 0.))
        ao[vert] = .5 + .5 * np.clip((yv - base) / .55, 0, 1)
    up = (ib >= 0) & (nrm[:, 1] > .5) & (np.abs(y) < .02)
    if up.any():                                          # interior floors: darker along the walls
        xu, zu = x[up], z[up]
        cor = (np.abs(xu) < CX + .01) & (zu > CZ0) & (zu < CZ1)
        dc = CX - np.abs(xu)
        dl = np.minimum.reduce([xu - LX0, LX1 - xu, zu - LZ0, LZ1 - zu])
        dw = np.where(cor, dc, np.where(xu > 30, (CX + .1) - np.abs(xu - X3), dl))
        ao[up] = .55 + .45 * np.clip(dw / .55, 0, 1)
    fl = ib == -1
    if fl.any(): ao[fl] = np.where(np.abs(z[fl] - FZ) < .6, .55 + .45 * np.abs(z[fl] - FZ) / .6, 1.)
    return ao


def zone_fn(P):
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    zz = np.zeros(len(x), np.int64)
    inside_y = (y > -.08)
    lob = (x > LX0 - .05) & (x < LX1 + .05) & (z > LZ0 - .03) & (z < LZ1 + .05) & (y < LH + .05) & inside_y
    zz[lob] = ZONE_LOBBY
    rooms = ((x > -RW - .05) & (x < -CX - .05) & (z > 10.45) & (z < 22.55)) | ((x > CX + .05) & (x < RW + .05) & (z > 11.95) & (z < 24.05))
    zz[rooms & inside_y & (y < CH + .1)] = ZONE_ROOM
    st = (x > SW[0] - .02) & (x < SW[2] + .05) & (z > SW[1] - .02) & (z < SW[3] + .05) & inside_y & (y < 5.)
    zz[st] = ZONE_STAIR
    cor = (np.abs(x) < CX + .05) & (z > CZ0 - .01) & (z < CZ1 + .07) & (y < CH + .1) & inside_y
    zz[cor] = ZONE_COR
    zz[(x > 30) & (y > -.1)] = ZONE_THIRD
    return zz


# ================================================================== static base
def _wall_x(sc, x0, x1, z0, z1, y0, y1, kind, face, col=(120, 110, 96), ppm=12):
    """wall box with the wallpaper texture on `face` ('+x' / '-x' / '+z' / '-z'); the texture length follows the box"""
    L = (z1 - z0) if face in ('+x', '-x') else (x1 - x0)
    tex = wall_tex(max(4, int(round(L * ppm))), kind, int(round((y1 - y0) * 12)))
    sc.add(Box((x0, y0, z0), (x1, y1, z1), col, tex={face: tex}, mat=M_CLEAN, grain=.04))


def _segments(a, b, holes):
    """split [a, b] around holes [(h0, h1)] -> list of (s0, s1)"""
    out = []; cur = a
    for h0, h1 in sorted(holes):
        if h0 > cur + .005: out.append((cur, h0))
        cur = max(cur, h1)
    if b > cur + .005: out.append((cur, b))
    return out


def _props():
    from .sets import prop_boxes, place
    return prop_boxes, place


def build_base():
    prop_boxes, place = _props()
    sc = Scene(); sc.floor_fn = floor_fn; sc.ao_fn = ao_fn; sc.zone_fn = zone_fn; sc.ceil_y = None; sc.floor_y = YARD
    sc.ambient = (.035, .034, .04); sc.fog = (.012, .012, .016); sc.fogk = .03
    from . import world as W
    from .sets import SKIES
    sc.sky_fn = W.make_sky({'sky': 'night', 'stars': True, 'clouds': .35, 'backdrop': [{'type': 'city', 'height': 9}]}, SKIES['night']['sun'])
    I = {}
    def mark(name): I[name] = len(sc.boxes)
    # ---------------------------------------------------------------- foundations, front street
    sc.add(B((BX0, YARD, -.3), (BX1 - BX0, -YARD - .05, FZ + .3), (70, 68, 64), mat=M_PLASTER))           # plinth / foundation block
    sc.add(Box((-26, YARD, -18), (26, 0., -.3), (60, 60, 62), tex={'+y': np.flipud(street_tex())}, grain=.05))   # front street at y = 0
    sc.add(B((-26, 0, -19), (52, 9.5, .6), (34, 34, 40), tex={'+z': _opposite_tex()}, texemis=.6))       # building across the street
    sc.add(C((-4.2, 1.9, -3.2), (.12, 3.8, .12), (40, 42, 46), mat=M_METAL), C((-4.2, 3.82, -2.9), (.3, .1, .6), (255, 196, 110), emis=2.0, cast=False))
    sc.add(B((-9.5, 0, -11.0), (4.2, 1.3, 1.8), (40, 44, 56), mat=M_METAL), B((-9.1, 1.3, -10.8), (3.2, .5, 1.4), (24, 28, 36)))   # parked car silhouette
    # ---------------------------------------------------------------- lobby shell
    sc.add(Box((LX0, -.05, LZ0), (LX1, 0., LZ1), (120, 110, 96), tex={'+y': marble_tex()}, refl=.14, grain=.03))
    sc.add(B((LX0, LH, LZ0 - .2), (LX1 - LX0, .15, LZ1 - LZ0 + .3), (176, 168, 150), mat=M_CEIL_CLEAN))
    for (a, b) in ((LX0 - .2, -6.2), (-2.4, -1.0), (1.0, LX1 + .1)): sc.add(B((a, 0, LZ0 - .2), (b - a, LH, .2), (60, 80, 70), mat=M_CLEAN))   # south wall
    sc.add(B((-6.2, 0, LZ0 - .2), (3.8, .9, .2), (60, 80, 70), mat=M_CLEAN), B((-6.2, 2.45, LZ0 - .2), (3.8, LH - 2.45, .2), (60, 80, 70), mat=M_CLEAN))
    sc.add(B((-1.0, 2.4, LZ0 - .2), (2.0, LH - 2.4, .2), (60, 80, 70), mat=M_CLEAN))
    _wall_x(sc, LX0 - .2, LX0, LZ0, LZ1, 0., LH, 'lobby', '+x')                                            # west wall (behind the counter)
    _wall_x(sc, LX1, LX1 + .2, LZ0, LZ1, 0., LH, 'lobby', '-x')                                            # east wall
    for (a, b) in ((LX0, -CX), (CX, LX1)): _wall_x(sc, a, b, LZ1, LZ1 + .12, 0., LH, 'lobby', '-z')        # north wall, corridor mouth between
    sc.add(B((-CX, CH, LZ1), (2 * CX, LH - CH, .12), (176, 168, 150), mat=M_CLEAN))
    for x in (-CX - .06, CX - .06): sc.add(B((x, 0, LZ1 - .04), (.12, CH, .2), (70, 44, 30), mat=M_WOODV))    # mouth jambs
    # south glazing: window frames, door frames (the glass itself is a screen-door pane, see dynamic)
    fr = (150, 146, 136)
    for x in (-6.2, -4.3, -2.45): sc.add(B((x, .9, LZ0 - .17), (.06, 1.55, .14), fr, mat=M_METAL))
    sc.add(B((-6.2, .88, LZ0 - .17), (3.8, .04, .2), fr, mat=M_METAL), B((-6.2, 2.42, LZ0 - .17), (3.8, .05, .14), fr, mat=M_METAL))
    for x in (-1.0, -.04, .96): sc.add(B((x, 0, LZ0 - .17), (.08, 2.4, .14), fr, mat=M_METAL))
    sc.add(B((-1.0, 2.36, LZ0 - .17), (2.0, .06, .14), fr, mat=M_METAL))
    for x in (-.24, .16): sc.add(B((x, .95, LZ0 + .0), (.08, .4, .04), (200, 190, 150), mat=M_METAL))      # door pull handles
    sc.add(B((-1.0, 2.43, LZ0 - .06), (2.0, .3, .02), (20, 20, 22), tex={'+z': _hotel_glass_tex()}, texemis=.5))   # gilded transom lettering
    # ---------------------------------------------------------------- reception: counter, desk, back wall
    x0, x1, z0, z1 = COUNTER
    sc.add(B((x0, 0, z0), (x1 - x0, 1.02, z1 - z0), (84, 50, 32), mat=M_WOODV))
    sc.add(B((x0 - .06, 1.02, z0 - .05), (x1 - x0 + .14, .06, z1 - z0 + .1), (196, 186, 166), refl=.02, grain=.03))     # marble top
    sc.add(B((x1, .1, z0), (.02, .04, z1 - z0), (190, 150, 70), mat=M_METAL, emis=.05), B((x1, .92, z0), (.02, .04, z1 - z0), (190, 150, 70), mat=M_METAL))
    for zz in np.arange(z0 + .5, z1, .8): sc.add(B((x1, .2, zz - .01), (.015, .66, .02), (60, 36, 24)))
    sc.add(B((-4.95, 0, z0), (.85, DESK_Y, z1 - z0), (60, 40, 28), mat=M_WOODV), B((-4.98, DESK_Y, z0 - .02), (.9, .03, z1 - z0 + .04), (74, 50, 34), mat=M_WOODV))
    sc.add(B((-3.92, 1.08, 4.58), (.14, .04, .14), (40, 40, 44), mat=M_METAL), C((-3.85, 1.13, 4.65), (.09, .05, .09), (210, 180, 90), mat=M_METAL))   # bell
    sc.add(B((-3.95, 1.08, 6.25), (.34, .03, .44), (120, 30, 30), mat=M_CARD), B((-3.93, 1.11, 6.27), (.3, .005, .4), (226, 220, 200)))   # guest register on the counter
    sc.add(C((-4.6, DESK_Y + .1, 2.75), (.2, .2, .22), (60, 62, 66), mat=M_METAL))                          # small printer
    # banker lamp
    lx, lz = LAMP
    sc.add(C((lx, DESK_Y + .03, lz), (.16, .03, .12), (190, 150, 70), mat=M_METAL), C((lx, DESK_Y + .16, lz), (.02, .26, .02), (190, 150, 70), mat=M_METAL))
    sc.add(C((lx + .03, DESK_Y + .31, lz), (.16, .06, .3), (20, 100, 56), refl=.2), C((lx + .03, DESK_Y + .275, lz), (.12, .015, .24), (255, 236, 180), emis=1.6, cast=False))
    # back wall items (faces +x at x = LX0)
    def wall_item(zc, yc, w, h, col, tex=None, depth=.04, texemis=0., emis=0.):
        sc.add(Box((LX0, yc - h / 2, zc - w / 2), (LX0 + depth, yc + h / 2, zc + w / 2), col, tex={'+x': tex} if tex is not None else None, texemis=texemis, emis=emis, cast=False if emis else None))
    wall_item(KEYS[0], KEYS[1], 1.55, .82, (96, 60, 38), keys_tex(), .05)
    for c_ in range(8):                                                         # keys hanging in relief (row 1)
        if c_ == 7: continue
        sc.add(C((LX0 + .07, KEYS[1] + .14, KEYS[0] - .62 + c_ * .19), (.02, .1, .045), (210, 196, 150), mat=M_METAL))
    wall_item(3.45, 2.52, 1.7, .26, (40, 26, 18), sign_tex('reception'), .03, .55)
    mark('plan'); wall_item(PLAN[0], PLAN[1], .66, .56, (230, 226, 210), plan_tex(), .03, .12)
    sc.add(Box((LX0, PLAN[1] - .31, PLAN[0] - .36), (LX0 + .025, PLAN[1] + .31, PLAN[0] + .36), (110, 80, 40), mat=M_WOODV))   # frame
    sc.add(Box((LX0, PANEL[1] - .42, PANEL[0] - .3), (LX0 + .16, PANEL[1] + .42, PANEL[0] + .3), (150, 152, 150), tex={'+x': panel_door_tex()}, mat=M_METAL))
    sc.add(Box((LX0, CLOCK[1] - .14, CLOCK[0] - .32), (LX0 + .07, CLOCK[1] + .14, CLOCK[0] + .32), (16, 14, 14), mat=M_METAL))   # clock housing
    sc.add(B((LX0, 0, 7.6), (.06, 2.15, .95), (70, 44, 30), mat=M_DOOR), B((LX0 + .06, 1.7, 7.88), (.01, .1, .3), (180, 150, 90), tex={'+x': sign_tex('prive')}))
    # ---------------------------------------------------------------- lobby furniture
    def P_(kind, x, z, rot=0, **kw):
        for b in place(prop_boxes(kind, dict(kw)), x, z, rot): sc.add(b)
    mark('chairs0')
    P_('armchair', 3.95, 2.7, 1, color=[110, 34, 36]); P_('armchair', 3.95, 4.7, 1, color=[110, 34, 36])
    mark('chairs1')
    sc.add(B((2.55, 0, 3.3), (.9, .42, .8), (60, 38, 26), mat=M_WOODV), B((2.5, .42, 3.25), (1.0, .04, .9), (74, 48, 32), mat=M_WOODV))   # low table
    sc.add(B((2.0, 0, 2.2), (2.5, .01, 3.0), (70, 30, 34), mat=M_FABRIC, cast=False))                      # rug
    P_('plant', 4.25, 7.9); P_('plant', 1.65, .65); P_('plant', -1.85, 8.55); P_('plant', -6.55, 8.6)
    sc.add(C((4.3, .75, 6.3), (.05, 1.5, .05), (60, 50, 40)), C((4.3, 1.55, 6.3), (.36, .32, .36), (236, 200, 150), emis=.9, cast=False))    # floor lamp
    for (zz, art) in ((2.4, 0), (5.6, 1)):
        sc.add(Box((LX1 - .05, 1.25, zz - .45), (LX1, 2.05, zz + .45), (90, 60, 30), mat=M_WOODV), Box((LX1 - .06, 1.32, zz - .38), (LX1 - .05, 1.98, zz + .38), (60, 70, 80), tex={'-x': _painting_tex(art)}))
    sc.add(B((-2.2, 0, 1.1), (.6, .05, .5), (190, 160, 80), mat=M_METAL), B((-2.15, .05, 1.15), (.5, .9, .05), (190, 160, 80), mat=M_METAL),
           B((-2.15, .95, 1.15), (.5, .04, .4), (190, 160, 80), mat=M_METAL), B((-2.1, .1, 1.2), (.4, .3, .3), (60, 40, 30), mat=M_CARD))     # luggage trolley
    for (x, z) in ((-1.0, 3.2), (2.0, 5.0)):
        sc.add(C((x, LH - .35, z), (.02, .7, .02), (40, 30, 20)))                                       # pendant stems (shades are dynamic)
    # ---------------------------------------------------------------- corridor shell
    sc.add(Box((-CX, -.05, CZ0), (CX, 0., CLZ), (96, 22, 30), tex={'+y': carpet_tex(round(CLZ - CZ0, 1))}, grain=.04))
    sc.add(Box((-CX, -.05, CLZ), (CX, 0., CZ1), (90, 90, 88), tex={'+y': concrete_tex()}, grain=.08))
    sc.add(B((-CX - .1, CH, CZ0), (2 * CX + .2, .15, CZ1 - CZ0 + .1), (170, 164, 150), mat=M_CEIL_CLEAN))
    for side in (-1, 1):
        holes = [(z - .5, z + .5) for (n, s, z) in ROOMS if s == side] + ([SD] if side > 0 else [])
        xin = side * CX; xa, xb = (xin, xin + .1) if side > 0 else (xin - .1, xin)
        face = '-x' if side > 0 else '+x'
        for (a, b) in _segments(CZ0, CZ1, holes): _wall_x(sc, xa, xb, a, b, 0., CH, 'corridor' if b <= CLZ + .01 else 'raw', face)
        for (a, b) in holes:
            sc.add(Box((xa, 2.1, a), (xb, CH, b), (150, 126, 96), mat=M_CLEAN))                         # lintel
            jx = xin - side * .03
            sc.add(Box((min(jx, jx - side * .035), 0, a - .06), (max(jx, jx - side * .035), 2.16, a + .02), (72, 46, 30), mat=M_WOODV))     # architrave
            sc.add(Box((min(jx, jx - side * .035), 0, b - .02), (max(jx, jx - side * .035), 2.16, b + .06), (72, 46, 30), mat=M_WOODV))
            sc.add(Box((min(jx, jx - side * .035), 2.1, a - .06), (max(jx, jx - side * .035), 2.18, b + .06), (72, 46, 30), mat=M_WOODV))
    # rooms behind the doors: floor, ceiling, back wall with a night window, bed, nightstand
    for n, s, zc in ROOMS:
        za, zb = zc - 1.5, zc + 1.5; xa, xb = (CX + .1, RW) if s > 0 else (-RW, -CX - .1)
        sc.add(Box((xa, -.05, za), (xb, 0., zb), (110, 86, 70), tex={'+y': carpet_tex(3.0, 'room')}, grain=.05))
        sc.add(Box((xa, CH, za), (xb, CH + .12, zb), (180, 172, 160), mat=M_CEIL_CLEAN))
        bw = (RW, RW + .1) if s > 0 else (-RW - .1, -RW)
        sc.add(Box((bw[0], 0, za), (bw[1], CH, zb), (170, 150, 120), tex={('-x' if s > 0 else '+x'): wall_tex(36, 'room', 32)}, mat=M_CLEAN))
        for zw_ in (za, zb - .1): sc.add(Box((xa, 0, zw_), (xb, CH, zw_ + .1), (170, 150, 120), tex={('+z' if zw_ == za else '-z'): wall_tex(42, 'room', 32)}, mat=M_CLEAN))
        wx = RW - .02 if s > 0 else -RW + .02
        sc.add(Box((min(wx, wx - s * .02), 1.0, zc - .1), (max(wx, wx - s * .02), 2.1, zc + .9), (20, 26, 44), tex={('-x' if s > 0 else '+x'): window_tex('dark', 3)}, texemis=.35))
        bx_ = s * 3.4
        sc.add(Box((bx_ - .9, 0, zb - 2.1), (bx_ + .9, .45, zb - .12), (210, 206, 196), mat=M_FABRIC), Box((bx_ - .9, .45, zb - .5), (bx_ + .9, .6, zb - .14), (230, 228, 220), mat=M_FABRIC))
        sc.add(Box((bx_ - .92, 0, zb - .2), (bx_ + .92, 1.0, zb - .1), (80, 52, 36), mat=M_WOODV))
        sc.add(Box((bx_ - .95, .44, zb - 1.7), (bx_ + .95, .52, zb - .55), (120, 40, 44) if int(n) % 2 else (50, 70, 110), mat=M_FABRIC))
        sc.add(Box((s * 2.1 - .2, 0, zb - .55), (s * 2.1 + .2, .5, zb - .15), (80, 52, 36), mat=M_WOODV))
    # stairwell (main / south): concrete, flight going up, landing
    x0, z0, x1, z1 = SW
    sc.add(Box((x0, -.05, z0), (x1, 0., z1), (90, 90, 88), tex={'+y': concrete_tex()}))
    sc.add(Box((x1, 0, z0), (x1 + .12, 5., z1), (140, 140, 132), mat=M_PLASTER), Box((x0, 0, z1), (x1, 5., z1 + .12), (140, 140, 132), mat=M_PLASTER))
    sc.add(Box((x0, 4.9, z0), (x1, 5.05, z1), (120, 120, 116), mat=M_PLASTER))
    for i in range(12):
        sc.add(Box((x0 + .2 + i * .25, 0, z1 - 1.25), (x0 + .2 + (i + 1) * .25, .2 * (i + 1), z1 - .1), (130, 130, 124), mat=M_PLASTER))
    sc.add(Box((x0 + .2, 2.4, z0 + .1), (x1, 2.6, z1 - 1.3), (126, 126, 120), mat=M_PLASTER))
    sc.add(Box((x0 + .3, .9, z1 - 1.3), (x1 - .1, .95, z1 - 1.26), (40, 120, 60), mat=M_METAL))
    # corridor fittings: extinguisher, painting, alarm button housing, room-number signage
    sc.add(C((-CX + .1, .55, 16.0), (.16, .5, .16), (190, 26, 24), mat=M_METAL), C((-CX + .1, .86, 16.0), (.06, .1, .06), (30, 30, 30)))
    sc.add(Box((CX - .03, 1.3, 18.0), (CX, 1.9, 18.8), (90, 60, 30), mat=M_WOODV), Box((CX - .04, 1.36, 18.06), (CX - .03, 1.84, 18.74), (60, 70, 80), tex={'-x': _painting_tex(2)}))
    sc.add(Box((-CX, 1.25, ALARM_BTN[1] - .09), (-CX + .06, 1.55, ALARM_BTN[1] + .09), (200, 28, 24), mat=M_METAL))
    # ---------------------------------------------------------------- north end: behind the partition
    sc.add(Box((-CX - .1, 0, CZ1), (GD[0], CH + .1, FZ), (110, 108, 104), mat=M_PLASTER), Box((GD[1], 0, CZ1), (CX + .1, CH + .1, FZ), (110, 108, 104), mat=M_PLASTER))
    sc.add(Box((GD[0], 2.05, CZ1), (GD[1], CH + .1, FZ), (110, 108, 104), mat=M_PLASTER))
    sc.add(Box((GD[0] - .07, 0, CZ1 - .04), (GD[0], 2.12, CZ1 + .02), (44, 70, 52), mat=M_METAL), Box((GD[1], 0, CZ1 - .04), (GD[1] + .07, 2.12, CZ1 + .02), (44, 70, 52), mat=M_METAL))
    sc.add(Box((GD[0] - .07, 2.05, CZ1 - .04), (GD[1] + .07, 2.12, CZ1 + .02), (44, 70, 52), mat=M_METAL))
    sc.add(Box((GD[0], 2.2, CZ1 - .02), (GD[1], 2.32, CZ1), (60, 64, 58), tex={'-z': sign_tex('nord')}))
    rx, ry = RP                                                                                      # red panel: a hollow red box (glass + lever are dynamic)
    red = (200, 30, 26)
    sc.add(Box((rx - .13, ry - .18, CZ1 - .02), (rx + .13, ry + .18, CZ1), red, mat=M_METAL))
    sc.add(Box((rx - .105, ry - .155, CZ1 - .025), (rx + .105, ry + .155, CZ1 - .02), (236, 226, 200), tex={'-z': _lever_plate_tex()}))   # instructions plate inside
    for (a0, a1, b0, b1) in ((-.13, -.105, -.18, .18), (.105, .13, -.18, .18), (-.105, .105, .155, .18), (-.105, .105, -.18, -.155)):
        sc.add(Box((rx + a0, ry + b0, CZ1 - .095), (rx + a1, ry + b1, CZ1 - .02), red, mat=M_METAL))
    sc.add(Box((rx - .1, ry - .34, CZ1 - .02), (rx + .1, ry - .22, CZ1 - .01), (210, 200, 180), tex={'-z': sign_tex('urgence')}))
    # building-site clutter: ladder, buckets, plastic sheet, toolbox (the crowbar on it is dynamic)
    sc.add(Box((CX - .12, 0, 23.1), (CX - .06, 2.4, 23.15), (170, 150, 90), mat=M_WOODV), Box((CX - .12, 0, 23.55), (CX - .06, 2.4, 23.6), (170, 150, 90), mat=M_WOODV))
    for i in range(6): sc.add(Box((CX - .12, .3 + i * .36, 23.15), (CX - .06, .34 + i * .36, 23.55), (170, 150, 90), mat=M_WOODV))
    sc.add(C((-.85, .17, 23.95), (.28, .34, .28), (220, 220, 214)), C((-.55, .14, 24.2), (.24, .28, .24), (200, 200, 196)), C((-.85, .345, 23.95), (.24, .01, .24), (120, 150, 190)))
    sc.add(Box((-CX, 0.005, 22.8), (CX, .012, 24.5), (170, 176, 180), refl=.2, cast=False, grain=.12))      # protective sheet on the carpet
    tx, tz = TOOLBOX
    sc.add(C((tx, .13, tz), (.52, .26, .24), (196, 34, 28), mat=M_METAL), C((tx, .27, tz), (.5, .03, .22), (150, 26, 22), mat=M_METAL))
    sc.add(C((tx, .34, tz), (.3, .03, .03), (30, 30, 34)), C((tx - .14, .31, tz), (.03, .08, .03), (30, 30, 34)), C((tx + .14, .31, tz), (.03, .08, .03), (30, 30, 34)))
    sc.add(C((tx + .3, .02, tz + .1), (.22, .03, .05), (60, 60, 66), mat=M_METAL), C((tx - .35, .02, tz - .05), (.04, .03, .28), (200, 160, 40)))   # spanner, tape measure
    # ---------------------------------------------------------------- exterior: facade, landing, stair, yard, street, truck parking
    _facade(sc)
    sc.add(Box((-.8, -.08, FZ), (.8, 0., LAND), (50, 52, 56), tex={'+y': grating_tex()}, mat=M_METAL))         # landing
    for (xa, xb) in ((-.8, -.74), (.74, .8)):
        sc.add(Box((xa, 0, FZ + .05), (xb, 1.0, LAND), (40, 42, 46), mat=M_METAL))
        sc.add(Box((xa, .95, FZ + .05), (xb, 1.02, LAND), (60, 64, 70), mat=M_METAL))
    for i in range(STEP_N - 1):
        y = -STEP_R * (i + 1); za = LAND + STEP_D * i
        sc.add(Box((-STAIR_X, y - .04, za), (STAIR_X, y, za + STEP_D), (54, 56, 60), tex={'+y': grating_tex()}, mat=M_METAL))
    for xs in (-STAIR_X - .04, STAIR_X):                                                                  # stringers and rails (stepped)
        for i in range(STEP_N - 1):
            y = -STEP_R * (i + 1); za = LAND + STEP_D * i
            sc.add(Box((xs, y - .22, za), (xs + .04, y + .02, za + STEP_D), (40, 42, 46), mat=M_METAL))
            sc.add(Box((xs, y + .9, za), (xs + .04, y + .96, za + STEP_D), (60, 64, 70), mat=M_METAL))
            if i % 3 == 0: sc.add(Box((xs, y, za), (xs + .04, y + .92, za + .04), (40, 42, 46), mat=M_METAL))
    sc.add(C((0, 2.38, FZ + .12), (.16, .2, .16), (40, 42, 46), mat=M_METAL))                              # caged lamp over the door
    I['door_lamp'] = len(sc.boxes); sc.add(C((0, 2.32, FZ + .14), (.1, .1, .1), (255, 210, 140), emis=1.6, cast=False))
    # yard and street furniture
    for (x, z) in ((-7.5, 32.2), (6.5, 32.2)):
        sc.add(C((x, YARD + 2.4, z), (.12, 4.8, .12), (40, 42, 46), mat=M_METAL), C((x, YARD + 4.8, z + .35), (.24, .08, .8), (40, 42, 46), mat=M_METAL))
        sc.add(C((x, YARD + 4.74, z + .6), (.2, .04, .4), (255, 170, 80), emis=2.2, cast=False))
    sc.add(B((-6.6, YARD, 28.6), (1.3, 1.2, .9), (40, 74, 52), mat=M_METAL), B((-5.0, YARD, 28.8), (.7, 1.0, .7), (56, 58, 64), mat=M_METAL))   # bins
    sc.add(B((3.2, YARD, 28.2), (1.2, .5, .5), (70, 70, 74), mat=M_CARD))
    for k_ in range(7):                                                                                    # houses across the back street
        hx = -24 + k_ * 7.2; hh = 7 + (k_ * 37 % 5)
        sc.add(B((hx, YARD, 44.0), (6.8, hh, 6.0), (36 + k_ % 3 * 6, 36, 42), tex={'-z': _back_houses_tex(k_)}, texemis=.5))
    sc.idx = I
    return sc


@functools.lru_cache(maxsize=1)
def _opposite_tex():
    im, d = _rgba(104, 20, (30, 30, 36)); r = np.random.default_rng(9)
    for x in range(2, 104, 6):
        for y in range(2, 20, 6):
            c = (210, 170, 100) if r.random() < .14 else (20, 22, 30)
            d.rectangle([x, y, x + 3, y + 3], fill=c + (255,))
    d.rectangle([0, 16, 103, 19], fill=(46, 30, 26, 255)); mini_text(d, 40, 16, 'TABAC', (220, 60, 40, 255))
    return np.array(im)


@functools.lru_cache(maxsize=8)
def _back_houses_tex(k):
    im, d = _rgba(14, 14, (36, 36, 42)); r = np.random.default_rng(40 + k)
    for x in range(1, 14, 4):
        for y in range(1, 12, 4):
            c = (200, 160, 96) if r.random() < .22 else (16, 18, 26)
            d.rectangle([x, y, x + 2, y + 2], fill=c + (255,))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def _painting_tex(art=0):
    im, d = _rgba(20, 16, (60, 70, 80))
    if art == 0: d.rectangle([0, 9, 19, 15], fill=(50, 80, 50, 255)); d.ellipse([12, 2, 17, 7], fill=(230, 200, 120, 255))
    elif art == 1: d.rectangle([0, 0, 19, 15], fill=(90, 60, 50, 255)); d.polygon([(2, 14), (10, 3), (18, 14)], fill=(140, 120, 100, 255))
    else: d.rectangle([0, 0, 19, 15], fill=(40, 50, 70, 255)); d.rectangle([6, 4, 13, 12], fill=(170, 150, 110, 255))
    d.rectangle([0, 0, 19, 15], outline=(30, 20, 14, 255))
    return np.array(im)


@functools.lru_cache(maxsize=1)
def _hotel_glass_tex():
    im, d = _rgba(40, 6, (16, 16, 18)); w = mini_width('HOTEL'); mini_text(d, (40 - w) // 2, 1, 'HOTEL', (206, 170, 90, 255)); return np.array(im)


def _facade(sc):
    """north facade, 4 levels: textured wall pieces around the green door, windows as boxes, the walled window of room 313"""
    tex = facade_tex(); H_, W_ = tex.shape[:2]; ppm = 12.
    def piece(x0, x1, y0, y1):
        c0 = int(round((x0 - BX0) * ppm)); c1 = int(round((x1 - BX0) * ppm)); r0 = int(round((TOP - y1) * ppm)); r1 = int(round((TOP - y0) * ppm))
        sub = tex[max(0, r0):max(r0 + 1, min(H_, r1)), max(0, c0):max(c0 + 1, min(W_, c1))]
        sc.add(Box((x0, y0, CZ1), (x1, y1, FZ), (110, 108, 104), tex={'+z': np.ascontiguousarray(np.fliplr(sub))}, mat=M_PLASTER, grain=.05))
    piece(BX0, GD[0], YARD, TOP); piece(GD[1], BX1, YARD, TOP); piece(GD[0], GD[1], 2.05 + .07, TOP); piece(GD[0], GD[1], YARD, 0.)
    sc.add(Box((BX0 - .3, YARD, -.3), (BX0, TOP, FZ), (104, 98, 88), mat=M_PLASTER), Box((BX1, YARD, -.3), (BX1 + .3, TOP, FZ), (104, 98, 88), mat=M_PLASTER))   # side walls
    sc.add(Box((BX0 - .4, TOP - .1, CZ1 - .1), (BX1 + .4, TOP + .25, FZ + .35), (120, 112, 100), mat=M_PLASTER))      # cornice
    sc.add(Box((BX0 - .3, TOP + .25, CZ1), (BX1 + .3, TOP + .9, FZ), (96, 92, 86), mat=M_PLASTER))               # parapet
    sc.add(Box((BX1 - 1.1, TOP + .5, 18.0), (BX1 - .3, TOP + 2.4, 20.0), (60, 60, 64), mat=M_METAL))              # roof box
    for lvl in range(4):
        y0 = lvl * 3.0
        for bx_ in BAYS:
            if lvl == 0 and abs(bx_) < .1: continue                                                   # the green door
            wa, wb = bx_ - .55, bx_ + .55; ya, yb = y0 + .95, y0 + 2.45
            if lvl == 0: ya, yb = y0 + 1.25, y0 + 2.35
            if (abs(bx_ - WALLED[0]) < .01 and lvl == WALLED[1]):                                     # room 313: walled with concrete blocks
                sc.add(Box((wa - .04, ya - .04, FZ), (wb + .04, yb + .04, FZ + .05), (150, 148, 140), tex={'+z': blocks_tex(16, 24, 'clair')}, grain=.06))
                sc.add(Box((wa - .06, ya - .08, FZ), (wb + .06, ya, FZ + .14), (120, 116, 106), mat=M_PLASTER))
                continue
            kind = 'blind' if lvl == 0 else ('lit' if (lvl == 2 and bx_ < -5) else 'dark')
            sc.add(Box((wa, ya, FZ), (wb, yb, FZ + .02), (20, 24, 34), tex={'+z': window_tex(kind, int(bx_ * 10) + lvl)}, texemis=.5 if kind == 'lit' else .12, refl=.25))
            sc.add(Box((wa - .06, ya - .08, FZ), (wb + .06, ya, FZ + .16), (176, 170, 156), mat=M_PLASTER))   # sill
            sc.add(Box((wa - .05, yb, FZ), (wb + .05, yb + .1, FZ + .07), (150, 142, 128), mat=M_PLASTER))   # lintel
            if lvl > 0:
                for s_ in (-1, 1): sc.add(Box((bx_ + s_ * .55 - (.3 if s_ < 0 else 0) - (0 if s_ < 0 else -0.), ya, FZ), (bx_ + s_ * .55 + (0 if s_ < 0 else .3), yb, FZ + .04), (60, 84, 96), mat=M_WOODV))   # shutters
    sc.add(Box((BX1 - .25, -1.0, FZ), (BX1 - .15, TOP, FZ + .1), (70, 72, 76), mat=M_METAL))                     # downpipe
    sc.add(Box((BX1 - .1, 4.0, FZ + .05), (BX1 + .02, 9.0, FZ + .5), (30, 10, 10), mat=M_METAL))               # vertical HOTEL sign (letters dynamic)


_BASE = None
_BASES = {}
def base():
    """le décor fixe ; construit une fois par état de la clé `objets` (les plantes du hall passent par `prop_boxes`) : sans la clé, le même objet qu'avant"""
    global _BASE
    from . import objets as OD
    sig = OD.signature()
    if not sig:
        if _BASE is None: _BASE = build_base()
        return _BASE
    if sig not in _BASES: _BASES[sig] = build_base()
    return _BASES[sig]


# ================================================================== dynamic parts (from the state, every frame)
def flick(g, rate, seed, p=.8):
    k = int(g * rate); r = ((k * 2654435761 + seed * 97) & 0xffff) / 65535.
    return r > p


def strobe(g, rate, phase=0.):
    """xenon alarm flash: a sharp double flash per period, then dark (0..1)"""
    f = (g * rate + phase) % 1.
    return 1. if f < .06 else (.55 if .14 < f < .19 else 0.)


def _leaf(boxes, yaw, piv): return orient(boxes, yaw, piv)


def _lvl(s, key):
    v = s.get(key, 0.) or 0.
    if isinstance(v, (list, tuple)): v = v[0] if v else 0.
    try: return float(v)
    except (TypeError, ValueError): return 0.


def dynamic(s, g):
    """boxes and lights of everything the state drives; lights are 7-tuples (pos, col, power, radius, shadow, spot, zone weights)"""
    bx = []; L = []
    pw = _lvl(s, 'power'); mode = s.get('lights')
    if mode == 'off': pw = 0.
    elif mode == 'dark': pw *= .15
    elif mode == 'flicker' and flick(g, 10, 3, .55): pw *= .2
    morning = s.get('moment') == 'matin'
    # ---------------------------------------------------------------- reception
    lob = _lvl(s, 'lobby') * pw * (1 - .7 * _lvl(s, 'lobby_dim'))
    for (x, z) in ((-1.0, 3.2), (2.0, 5.0)):
        bx.append(C((x, LH - .74, z), (.44, .2, .44), (150, 110, 60) if lob > .02 else (70, 60, 50), mat=M_FABRIC))
        bx.append(C((x, LH - .85, z), (.36, .02, .36), (255, 220, 160) if lob > .02 else (60, 56, 50), emis=1.3 * lob, cast=False))
        if lob > .02: L.append(((x, LH - 1.0, z), (1., .78, .5), .7 * lob, 3.6, False, None, _zw(ZONE_LOBBY, spill={ZONE_COR: .12})))
    lmp = pw * (1. if not morning else 0.)
    bx.append(C((LAMP[0] + .03, DESK_Y + .27, LAMP[1]), (.12, .015, .24), (255, 236, 180) if lmp > .02 else (60, 56, 40), emis=1.8 * lmp, cast=False))
    if lmp > .02:
        L.append(((LAMP[0] + .1, DESK_Y + .25, LAMP[1] - .1), (1., .8, .5), .95 * lmp, 1.9, True, None, _zw(ZONE_LOBBY)))
        L.append(((4.3, 1.55, 6.3), (1., .78, .5), .5 * lob, 2.4, False, None, _zw(ZONE_LOBBY)))
    # landline (ivory phone, ringing lamp), handset on the cradle
    from . import objets as OD
    od = (OD.active() or {}).get('decors')               # clé d'épisode `objets` : téléphone et standard détaillés (deux versions natives) ; sans elle, le code d'avant
    if s.get('landline', 1) and od:
        px, pz = PHONE; ring = _lvl(s, 'landline_ring'); on = ring > 0 and (g * 5.) % 1. < .55
        sh = (.003 * math.sin(g * 83.), .002 * abs(math.sin(g * 61.))) if ring > 0 else (0., 0.)
        from .sets import place
        bx += place(OD.prop('od_phone_desk', dict(combine=bool(s.get('handset', 1)), voyant=bool(on), ecran='CH 313' if ring > 0 else str(s.get('clock', '02:13'))), PHONE_COL), px + sh[0], pz, 1, DESK_Y + .03 + sh[1])
        if on: L.append(((px - .25, DESK_Y + .2, pz + .1), (1., .25, .12), .25, .8, False, None, _zw(ZONE_LOBBY)))
    elif s.get('landline', 1):                          # burgundy desk phone: base, keypad facing the receptionist (-x), handset on two cradle forks
        px, pz = PHONE; ring = _lvl(s, 'landline_ring'); on = ring > 0 and (g * 5.) % 1. < .55; y0 = DESK_Y + .03
        bx += [B((px - .1, y0, pz - .14), (.22, .06, .28), PHONE_COL), B((px - .11, y0, pz - .14), (.04, .035, .28), PHONE_DARK)]
        bx.append(Box((px - .1, y0 + .06, pz - .07), (px - .02, y0 + .065, pz + .07), PHONE_DARK, tex={'+y': keypad_tex()}))
        for dz in (-.1, .1): bx.append(C((px + .05, y0 + .075, pz + dz), (.06, .03, .04), PHONE_DARK))
        bx.append(C((px - .108, y0 + .045, pz + .1), (.01, .02, .03), (255, 60, 40) if on else (70, 20, 18), emis=3. if on else 0., cast=False))
        if s.get('handset', 1):
            sh = (.008 * math.sin(g * 83.), .006 * abs(math.sin(g * 61.))) if ring > 0 else (0., 0.)
            hx, hy = px + .05 + sh[0], y0 + .11 + sh[1]
            bx += [C((hx, hy, pz), (.05, .04, .22), PHONE_COL), C((hx, hy - .005, pz - .115), (.075, .05, .075), PHONE_COL), C((hx, hy - .005, pz + .115), (.075, .05, .075), PHONE_COL)]
        bx.append(C((px + .12, y0 + .01, pz + .05), (.03, .02, .03), (40, 14, 14)))          # coiled cord to the wall
        if on: L.append(((px - .25, DESK_Y + .2, pz + .1), (1., .25, .12), .25, .8, False, None, _zw(ZONE_LOBBY)))
    if s.get('handset_pos'):
        hx, hy, hz = s['handset_pos']; bx += [C((hx, hy, hz), (.06, .26, .06), PHONE_COL), C((hx, hy - .12, hz - .02), (.08, .06, .08), PHONE_COL), C((hx, hy + .12, hz - .02), (.08, .06, .08), PHONE_COL)]
    # switchboard: tilted console facing the receptionist (-x); lit lamps are small emissive boxes in front of the panel
    if od:                                                # standard détaillé (pupitre en gradins, voyants, jacks, fiches, cordons, clés, cadran) ; mêmes voyants que l'état
        sx, sz = BOARD; blink = _lvl(s, 'board_blink'); lit = []
        for num, lv in [('313', _lvl(s, 'board_313'))] + [(str(n), 1.) for n in (s.get('board_lamps') or ()) if str(n) != '313']:
            if lv <= .02 or (blink > 0 and int(g * blink * 2) % 2): continue
            lit.append(num)
            if num == '313': L.append(((sx - .25, DESK_Y + .32, sz + .25), (1., .5, .15), .22 * lv, .9, False, None, _zw(ZONE_LOBBY)))
        from .sets import place
        bx += place(OD.prop('od_switchboard', dict(etages=['3', '2', '1', '0'], chambres=13, allumes=lit, fiches=['104', '212']), None), sx, sz, 1, DESK_Y + .03)
    sx, sz = BOARD; tilt = math.radians(22); Rz = np.array([[math.cos(tilt), math.sin(tilt), 0], [-math.sin(tilt), math.cos(tilt), 0], [0, 0, 1]], np.float32)
    con = [B((-.04, 0, -.36), (.16, .44, .72), (64, 58, 50), mat=M_WOODV), Box((-.045, .03, -.34), (-.04, .41, .34), (54, 50, 44), tex={'-x': switchboard_tex()}, texemis=.25)]
    lit = [('313', _lvl(s, 'board_313'))] + [(str(n), 1.) for n in (s.get('board_lamps') or ()) if str(n) != '313']
    blink = _lvl(s, 'board_blink')
    for num, lv in lit:
        if lv <= .02: continue
        if blink > 0 and int(g * blink * 2) % 2: lv *= .15
        u, v = board_lamp_uv(num); lz = .34 - u * .68; ly = .41 - v * .38
        con.append(C((-.052, ly, lz), (.016, .036, .036), (255, 140, 30), emis=1.5 * lv, cast=False))
        if num == '313':
            p = Rz @ np.array([-.2, ly, lz], np.float32) + np.array([sx, DESK_Y + .02, sz], np.float32)
            L.append((tuple(float(c) for c in p), (1., .5, .15), .22 * lv, .9, False, None, _zw(ZONE_LOBBY)))
    if not od: bx += orient(con, 0., (sx, DESK_Y + .02, sz), R=Rz)
    # monitor (faces the receptionist), screen text by state
    mx, mz = MONITOR; scr = s.get('screen', 'idle') if pw > .02 or s.get('screen') == 'call' else 'off'
    if morning and s.get('screen') in (None, 'idle'): scr = 'off'
    bx += [B((mx - .1, DESK_Y + .03, mz - .14), (.2, .02, .28), (40, 40, 44), mat=M_METAL), B((mx - .02, DESK_Y + .05, mz - .03), (.05, .14, .06), (40, 40, 44), mat=M_METAL),
           B((mx - .08, DESK_Y + .18, mz - .27), (.16, .36, .54), (36, 36, 40), mat=M_METAL)]
    lines = tuple(s['screen_lines']) if s.get('screen_lines') else None
    bx.append(Box((mx - .085, DESK_Y + .21, mz - .245), (mx - .08, DESK_Y + .51, mz + .245), (6, 10, 14), tex={'-x': screen_tex(scr, str(s.get('clock', '02:13')), lines)}, texemis=.75 if scr != 'off' else 0., cast=False))
    if scr != 'off': L.append(((mx - .5, DESK_Y + .4, mz), (.55, .7, 1.) if scr != 'call' else (1., .55, .45), .28, 1.4, False, None, _zw(ZONE_LOBBY)))
    # wall clock (LED), electrical panel LED
    on = _lvl(s, 'clock_on') > .5
    bx.append(Box((LX0 + .07, CLOCK[1] - .11, CLOCK[0] - .27), (LX0 + .075, CLOCK[1] + .11, CLOCK[0] + .27), (10, 8, 8), tex={'+x': clock_tex(str(s.get('clock', '02:13')), on)}, texemis=1.3 if on else 0., cast=False))
    if on: L.append(((LX0 + .5, CLOCK[1], CLOCK[0]), (1., .15, .1), .12, .8, False, None, _zw(ZONE_LOBBY)))
    led = _lvl(s, 'panel_led'); led_on = led > 0 and (g * 2.2) % 1 < .5
    bx.append(C((LX0 + .17, PANEL[1] + .3, PANEL[0] + .2), (.02, .035, .035), (255, 40, 30) if led_on else (70, 20, 18), emis=3. * led if led_on else 0., cast=False))
    if led_on: L.append(((LX0 + .3, PANEL[1] + .3, PANEL[0] + .2), (1., .1, .06), .15 * led, .6, False, None, _zw(ZONE_LOBBY)))
    # lobby armchairs under dust sheets (morning), printed log on the counter, barrier tape
    if s.get('covers'):
        for zc in (2.7, 4.7):
            bx += [C((3.95, .42, zc), (1.0, .84, .98), (214, 212, 204), mat=M_FABRIC), C((4.2, .9, zc), (.5, .2, 1.02), (220, 218, 210), mat=M_FABRIC)]
        bx.append(C((3.0, .48, 3.7), (1.1, .12, 1.0), (214, 212, 204), mat=M_FABRIC))
    if s.get('log_paper'):
        at = s.get('log_paper_at') or (-3.72, 4.15)
        bx.append(Box((at[0] - .15, 1.081, at[1] - .105), (at[0] + .15, 1.086, at[1] + .105), (236, 234, 226), tex={"+y": _paper_flat()}, cast=False))
    if s.get('barrier'):
        for y in (.95, 1.25): bx.append(B((-CX, y, LZ1 - .02), (2 * CX, .05, .02), (230, 40, 30), tex={'-z': _tape_tex()}, emis=.1))
    # ---------------------------------------------------------------- corridor: ceiling lights, emergency, alarm
    cl = _lvl(s, 'ceiling') * pw; cf = _lvl(s, 'ceiling_flicker')
    for k, z in enumerate((10.5, 13.5, 16.5, 19.5, 22.5)):
        lv = cl
        if cf > 0 and flick(g, 12, 7 + k, 1 - .45 * cf): lv *= .15
        bx.append(C((0, CH - .03, z), (.38, .05, .38), (255, 236, 200) if lv > .02 else (90, 88, 84), emis=1.6 * lv, cast=False))
        if lv > .02: L.append(((0, CH - .25, z), (1., .86, .66), .85 * lv, 2.7, False, None, _zw(ZONE_COR, spill={ZONE_ROOM: .25, ZONE_LOBBY: .15 if z < 11 else 0.})))
    em = _lvl(s, 'emergency')
    for (x, z, face) in ((CX, 10.05, '-x'), (-CX, 17.0, '+x'), (-CX, 23.4, '+x'), (0., LZ1, '-z')):
        te = .35 + 1.0 * em
        if face == '-z': bx.append(Box((x - .17, 2.36, LZ1 - .06), (x + .17, 2.5, LZ1), (236, 236, 232), tex={'-z': sign_tex('baes')}, texemis=te, cast=False))
        else:
            xa, xb = (x, x + .06) if face == '+x' else (x - .06, x)
            bx.append(Box((xa, 2.36, z - .17), (xb, 2.5, z + .17), (236, 236, 232), tex={face: sign_tex('baes')}, texemis=te, cast=False))
            bx.append(Box((xa, 2.34, z - .1), (xb, 2.36, z + .1), (255, 255, 250) if em > .02 else (150, 150, 146), emis=2.2 * em, cast=False))     # the white lamp under the block
        if em > .02:
            lz_ = z if face != '-z' else LZ1 - .35; lx_ = x * .8 if face != '-z' else 0.
            zw_ = _zw(ZONE_COR, spill={ZONE_ROOM: .2, ZONE_LOBBY: .2}) if face != '-z' else _zw(ZONE_LOBBY, spill={ZONE_COR: .3})
            L.append(((lx_, 2.2, lz_), (.82, .92, 1.), .55 * em, 3.2, False, None, zw_))
            L.append(((lx_, 2.45, lz_), (.3, 1., .5), .08 + .1 * em, .9, False, None, zw_))
    if em > .02:                                      # the lobby has its own emergency blocks (over the door, over the reception)
        for (x, z) in ((0., .4), (-3.0, 7.6)): L.append(((x, 2.5, z), (.82, .92, 1.), .5 * em, 4.2, False, None, _zw(ZONE_LOBBY)))
    bx.append(Box((CX - .06, 2.13, SD[0] + .08), (CX - .01, 2.29, SD[1] - .08), (20, 110, 60), tex={'-x': sign_tex('sortie')}, texemis=.45 + .55 * em, cast=False))
    bx.append(Box((GD[0] + .05, 2.36, CZ1 - .05), (GD[1] - .05, 2.5, CZ1 - .01), (20, 110, 60), tex={'-z': sign_tex('sortie')}, texemis=.35 + .55 * em, cast=False))
    al = _lvl(s, 'alarm'); rate = float(s.get('alarm_rate', 1.1) or 1.1)
    for k, (x, y, z) in enumerate(((0., CH - .05, 11.2), (0., CH - .05, 17.8), (0., CH - .05, 23.6), (-1.6, LH - .05, 8.4))):
        f = strobe(g, rate, k * .23) * al
        bx.append(C((x, y, z), (.14, .08, .14), (255, 60, 40) if f > .05 else (110, 30, 26), emis=3.5 * f + .05 * al, cast=False))
        if f > .05: L.append(((x, y - .3, z), (1., .12, .07), 1.0 * f, 3.4, False, None, _zw(ZONE_COR if k < 3 else ZONE_LOBBY, spill={ZONE_LOBBY if k < 3 else ZONE_COR: .3, ZONE_ROOM: .3})))
    ab = _lvl(s, 'alarm_button')
    bx.append(Box((-CX + .06, 1.29, ALARM_BTN[1] - .07), (-CX + .068, 1.51, ALARM_BTN[1] + .07), (230, 230, 230) if ab < .5 else (60, 20, 20), tex={'+x': sign_tex('alarme')} if ab < .5 else None, refl=.3 if ab < .5 else 0.))
    if ab >= .5:
        for k in range(5): bx.append(C((-CX + .2 + .1 * (k % 3), .01, ALARM_BTN[1] - .1 + .06 * k), (.04, .01, .03), (200, 210, 220), refl=.5, cast=False))
    # room doors (leaf + number plate + handle) and their interiors' lamps
    rl = _lvl(s, 'room_lights')
    for n, side, zc in ROOMS:
        a = max(0., min(1.05, _lvl(s, f'door_{n}'))); ang = a * math.radians(92)
        hz = zc - .45; hx = side * (CX + .045)
        cor = -side                                        # corridor side of the leaf, in local x
        leaf = [B((-.025, 0, 0), (.05, 2.08, .88), (98, 60, 40), tex={('+x' if cor > 0 else '-x'): door_tex()}, mat=M_DOOR),
                C((cor * .03, 1.62, .44), (.01, .1, .18), (196, 160, 70), tex={('+x' if cor > 0 else '-x'): plate_tex(n)}, emis=.05),
                C((cor * .05, 1.0, .78), (.05, .04, .12), (200, 180, 120), mat=M_METAL), C((cor * .028, 1.45, .44), (.008, .02, .02), (20, 20, 20))]
        bx += _leaf(leaf, side * ang, (hx, 0., hz))
        if a > .05 and rl > .02:
            L.append(((side * 3.3, 1.0, zc + 1.1), (1., .76, .46), .7 * min(1., a * 2) * rl, 2.6, False, None, _zw(ZONE_ROOM, spill={ZONE_COR: .45})))
            bx.append(C((side * 2.1, .72, zc + 1.15), (.22, .26, .22), (255, 220, 160), emis=1.4 * rl, cast=False))
    # main stair door: hinged on its SOUTH jamb, it opens INTO the corridor (towards -x); seen from the corridor (north) the opening shows
    a = max(0., min(1.05, _lvl(s, 'stair_door'))); ang = a * math.radians(100)
    leaf = [B((-.025, 0, 0), (.05, 2.08, .88), (176, 170, 150), mat=M_METAL), C((-.03, 1.45, .44), (.01, .3, .22), (30, 34, 40), refl=.3),
            C((-.06, 1.0, .5), (.06, .05, .6), (190, 190, 196), mat=M_METAL), Box((-.031, 1.8, .2), (-.026, 1.92, .68), (20, 110, 60), tex={'-x': sign_tex('escalier')}, texemis=.4)]
    bx += _leaf(leaf, -ang, (CX + .045, 0., SD[0] + .02))
    fire = _lvl(s, 'stair_fire')
    if fire > .02:
        fl = .75 + .25 * math.sin(g * 9.1) * math.sin(g * 5.3 + 1.)
        L.append(((2.9, 1.2, 11.0), (1., .42, .12), 2.4 * fire * fl, 3.6, False, None, _zw(ZONE_STAIR, spill={ZONE_COR: .45 * min(1., a * 1.5)})))
        bx.append(C((3.6, 2.2, 11.3), (.8, .05, .8), (255, 120, 40), emis=2.5 * fire * fl, cast=False))
    # ---------------------------------------------------------------- the partition (planks), crowbar in the toolbox
    bx += _partition(s, g)
    if s.get('crowbar_in_box', 1):
        bx += [C((TOOLBOX[0] - .05, .3, TOOLBOX[1] - .06), (.7, .03, .03), (122, 26, 24), mat=M_METAL), C((TOOLBOX[0] + .3, .32, TOOLBOX[1] - .06), (.06, .05, .03), (70, 72, 78), mat=M_METAL)]
    # ---------------------------------------------------------------- red panel: glass, shards, lever ; green door
    rx, ry = RP; rg = _lvl(s, 'red_glass'); gz = CZ1 - .094
    if rg < .02:                                      # screen-door glass (a fifth of the pixels) + two highlights
        bx.append(Box((rx - .105, ry - .155, gz), (rx + .105, ry + .155, gz + .004), (190, 220, 232), refl=.5, dissolve=.8, cast=False))
        for (u0, v0, h_) in ((-.08, .02, .1), (-.05, -.06, .14)): bx.append(Box((rx + u0, ry + v0, gz - .002), (rx + u0 + .012, ry + v0 + h_, gz), (240, 250, 255), emis=.6, cast=False))
    else:
        r = np.random.default_rng(31); tt = min(1., rg) * .45
        for k in range(16):
            p0 = np.array([rx + r.uniform(-.09, .09), ry + r.uniform(-.13, .13), gz]); v = np.array([r.uniform(-.6, .6), r.uniform(-.2, .9), -r.uniform(.6, 1.6)])
            q = p0 + v * tt + np.array([0, -4.9 * tt * tt, 0])
            if rg >= 1.: q = np.array([rx + r.uniform(-.32, .32), .008, CZ1 - .16 - r.uniform(0, .5)])
            q[1] = max(q[1], .008); sz_ = r.uniform(.012, .026)
            bx.append(C(tuple(q), (sz_, .008 if rg >= 1 else sz_, sz_ * .8), (200, 226, 236), refl=.6, emis=.25, cast=False))
        for (u0, v0, w_, h_) in ((-.105, -.155, .03, .07), (.07, -.155, .035, .05), (-.105, .11, .025, .045), (.08, .12, .025, .035)):   # jagged pieces left in the frame
            bx.append(Box((rx + u0, ry + v0, gz), (rx + u0 + w_, ry + v0 + h_, gz + .004), (190, 220, 232), refl=.5, emis=.15, cast=False))
    lv = max(0., min(1., _lvl(s, 'lever'))); la = -math.radians(128) * lv          # rest: handle up; pulled: down and out towards the corridor
    lev = [C((0, .065, 0), (.022, .13, .022), (236, 196, 30), mat=M_METAL, emis=.15), C((0, .135, 0), (.06, .03, .035), (30, 30, 30)), C((0, 0, 0), (.05, .05, .03), (60, 60, 64), mat=M_METAL)]
    Rx = np.array([[1, 0, 0], [0, math.cos(la), -math.sin(la)], [0, math.sin(la), math.cos(la)]], np.float32)
    bx += orient(lev, 0., (rx, ry - .07, CZ1 - .05), R=Rx)
    a = max(0., min(1.05, _lvl(s, 'green_door'))); ang = a * math.radians(95)
    gw = GD[1] - GD[0] - .02
    leaf = [Box((-gw, 0, -.03), (0, 2.03, .03), (52, 104, 70), tex={'-z': green_door_tex(), '+z': green_door_tex()}, mat=M_METAL),
            C((-gw + .1, 1.02, -.07), (.04, .04, .08), (60, 60, 64), mat=M_METAL), C((-gw / 2, 1.02, -.09), (gw - .2, .05, .05), (150, 150, 140), mat=M_METAL)]
    bx += _leaf(leaf, ang, (GD[1] - .01, 0., CZ1 + .07))
    dl = _lvl(s, 'street_lights')
    o = base().boxes[base().idx['door_lamp']]
    bx.append(Box(o.lo, o.hi, (255, 210, 140), emis=1.6 * dl, cast=False))
    if dl > .02:
        L.append(((0, 2.15, FZ + .45), (1., .78, .5), .9 * dl, 3.6, True, None, _zw(ZONE_OUT, spill={ZONE_COR: .35 * min(1., a * 2)})))
        for (x, z) in ((-7.5, 32.2), (6.5, 32.2)): L.append(((x, YARD + 4.6, z + .6), (1., .6, .26), 1.3 * dl, 6.5, False, None, _zw(ZONE_OUT)))
        L.append(((-4.2, 3.6, -2.9), (1., .66, .32), 1.6 * dl, 7.5, False, None, _zw(ZONE_OUT, spill={ZONE_LOBBY: .3})))
    hl = pw if not morning else 0.
    bx.append(Box((BX1 - .02, 4.2, FZ + .2), (BX1 + .03, 8.8, FZ + .45), (30, 10, 10), tex={'+x': sign_tex('hotel')}, texemis=1.6 * hl if not flick(g, 6, 2, .93) else .3, cast=False))
    if hl > .02: L.append(((BX1 + .6, 6.5, FZ + .4), (1., .2, .15), .6 * hl, 3.5, False, None, _zw(ZONE_OUT)))
    # ---------------------------------------------------------------- exterior: fire in the windows, the truck, hoses
    wf = _lvl(s, 'window_fire')
    if wf > .02:
        for k, (bx_, lvl) in enumerate(FIRE_WINDOWS):
            fl = .7 + .3 * math.sin(g * (7.3 + k) + k) * math.sin(g * 4.1 + 2 * k)
            y0 = lvl * 3.0
            bx.append(Box((bx_ - .5, y0 + 1.0, FZ + .021), (bx_ + .5, y0 + 2.4, FZ + .03), (255, 130, 40), emis=2.2 * wf * fl, cast=False, dissolve=.25))
            L.append(((bx_, y0 + 1.6, FZ + 1.0), (1., .45, .12), .75 * wf * fl, 3.2, False, None, _zw(ZONE_OUT)))
    if s.get('truck'):
        tx = TRUCK[0] + _lvl(s, 'truck_x'); tz = TRUCK[1]
        bx += _truck(tx, tz)
        be = _lvl(s, 'beacons')
        if be > .02:
            for k, (ox, col) in enumerate(((-3.6, (.25, .35, 1.)), (-2.9, (1., .1, .08)), (3.9, (.25, .35, 1.)), (3.3, (1., .1, .08)))):
                ph = g * 2 * math.pi * 1.6 + k * 1.7
                lv_ = max(0., math.cos(ph)) ** 3
                bx.append(C((tx + ox, YARD + 3.42, tz), (.32, .16, .32), tuple(int(c * 255) for c in col), emis=(.4 + 3.2 * lv_) * be, cast=False))
                if lv_ > .05:
                    L.append(((tx + ox + math.sin(ph) * 1.2, YARD + 3.6, tz + math.cos(ph) * 1.6), col, 1.5 * lv_ * be, 8.5, False, None, _zw(ZONE_OUT)))
    if s.get('hoses'):
        for (x0, z0, x1, z1) in ((-1.0, 35.0, -1.0, 31.4), (-1.0, 31.4, -.2, 31.0), (-.2, 31.0, -.2, 29.8), (1.6, 35.0, 2.4, 33.0), (2.4, 33.0, 2.4, 28.6)):
            bx.append(Box((min(x0, x1) - .05, YARD, min(z0, z1) - .05), (max(x0, x1) + .05, YARD + .07, max(z0, z1) + .05), (190, 160, 110), mat=M_FABRIC))
    # ---------------------------------------------------------------- 3rd floor, now or twenty years earlier
    bx_, L_ = _third(s, g, pw); bx += bx_; L += L_
    return bx, L


@functools.lru_cache(maxsize=1)
def _tape_tex():
    im, d = _rgba(24, 2, (230, 40, 30))
    for x in range(0, 24, 6): d.rectangle([x, 0, x + 2, 1], fill=(240, 240, 236, 255))
    return np.array(im)


PLANK_N = 8; PLANK_W = 2 * CX / PLANK_N
REMOVE_ORDER = (3, 2, 1, 4, 0, 5)                       # cloison = 1: plank 3 off, 2: + plank 2 (the green door shows) ...


def _partition(s, g):
    bx = []
    cv = max(0., float(s.get('cloison', 0.) or 0.)); hit = _lvl(s, 'cloison_hit')
    shake = .025 * hit * math.sin(g * 61.) if hit else 0.
    state = {}
    for k_, p in enumerate(REMOVE_ORDER): state[p] = max(0., min(1., cv - k_))
    wood = ((168, 132, 86), (156, 120, 78), (176, 140, 94))
    for p in range(PLANK_N):
        x0 = -CX + p * PLANK_W; st = state.get(p, 0.); col = wood[p % 3]
        local = [B((-PLANK_W / 2 + .005, 0, -.02), (PLANK_W - .01, 2.66, .04), col, mat=M_WOODV),
                 B((-PLANK_W / 2, .45, -.06), (PLANK_W, .1, .04), (130, 98, 62), mat=M_WOODV), B((-PLANK_W / 2, 2.05, -.06), (PLANK_W, .1, .04), (130, 98, 62), mat=M_WOODV)]
        for yy in (.5, 2.1): local.append(C((0, yy, -.065), (.02, .02, .01), (60, 60, 64), mat=M_METAL))
        if p in (6, 7):
            if p == 6: local.append(Box((-PLANK_W / 2 + .03, 1.2, -.07), (PLANK_W * 1.5 - .03, 1.65, -.065), (236, 196, 30), tex={'-z': sign_tex('chantier')}))
        if st <= 0:
            jitter = shake * (1 if p % 2 else -.6)
            for b in local: b.lo = b.lo + np.array([x0 + PLANK_W / 2, 0, CLZ + jitter], np.float32); b.hi = b.hi + np.array([x0 + PLANK_W / 2, 0, CLZ + jitter], np.float32)
            bx += local
        else:                                                   # falling forward (towards -z), pivoting on its bottom edge, then lying on the carpet
            ang = math.radians(86) * (min(1., st) ** 1.6)
            yaw = math.radians((p - 3.5) * 4.)
            ca, sa = math.cos(ang), math.sin(ang)
            Rx = np.array([[1, 0, 0], [0, ca, sa], [0, -sa, ca]], np.float32)          # (0, 1, 0) -> (0, ca, -sa): it falls into the corridor
            cy, sy = math.cos(yaw), math.sin(yaw); Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], np.float32)
            lift = .05 * (min(1., st))
            bx += orient(local, 0., (x0 + PLANK_W / 2, lift, CLZ - .03), R=Ry @ Rx)
    # tape across the passage: whole, or torn and hanging once the partition is open
    torn = cv >= 2.
    for y in (1.05, 1.45):
        if not torn: bx.append(B((-CX, y, CLZ - .12), (2 * CX, .05, .01), (230, 40, 30), tex={'-z': _tape_tex()}, emis=.1))
        else:
            for sd in (-1, 1):
                bx.append(B((sd * CX - (0 if sd < 0 else .03), y - .5, CLZ - .12), (.03, .52, .01), (230, 40, 30), tex={'-z': _tape_tex()}, emis=.1))
    return bx


def _truck(tx, tz):
    """fire truck facing -x (cab at tx - 3.5), ladder on the roof; built in world coordinates on the street (y = YARD)"""
    bx = []; y = YARD; red = (196, 22, 24); L = 8.4; W = 2.5
    side = truck_side_tex()
    bx.append(Box((tx - L / 2 + 2.2, y + .55, tz - W / 2), (tx + L / 2, y + 2.9, tz + W / 2), red, tex={'+z': side, '-z': side}, mat=M_METAL, refl=.12))
    bx.append(Box((tx - L / 2, y + .55, tz - W / 2), (tx - L / 2 + 2.2, y + 2.95, tz + W / 2), red, mat=M_METAL, refl=.12))       # cab
    bx.append(Box((tx - L / 2 - .02, y + 1.75, tz - W / 2 + .1), (tx - L / 2 + .02, y + 2.7, tz + W / 2 - .1), (20, 26, 34), refl=.45))   # windshield
    for sd in (-1, 1):
        bx.append(Box((tx - L / 2 + .4, y + 1.8, tz + sd * W / 2 - (.02 if sd > 0 else -.02) - (0 if sd > 0 else .02)), (tx - L / 2 + 1.7, y + 2.6, tz + sd * W / 2 + (.02 if sd > 0 else 0.)), (20, 26, 34), refl=.4))
    bx.append(Box((tx - L / 2 - .08, y + .4, tz - W / 2), (tx - L / 2, y + .75, tz + W / 2), (60, 60, 64), mat=M_METAL))       # bumper
    for sd in (-.9, .9): bx.append(C((tx - L / 2 - .01, y + .95, tz + sd), (.04, .18, .3), (240, 236, 220), emis=.4, cast=False))
    bx.append(Box((tx - L / 2 + .3, y + 2.95, tz - W / 2 + .2), (tx - L / 2 + 1.9, y + 3.32, tz + W / 2 - .2), (40, 40, 44), mat=M_METAL))     # light bar base
    for k in range(3):                                                                                  # wheels
        wx = tx - L / 2 + 1.4 + k * 2.8 + (1.2 if k else 0)
        for sd in (-1, 1): bx.append(Box((wx - .5, y, tz + sd * W / 2 - (.32 if sd > 0 else 0)), (wx + .5, y + 1.0, tz + sd * W / 2 + (0 if sd > 0 else .32)), (20, 20, 22)))
    bx.append(Box((tx - L / 2 + 2.6, y + 2.95, tz - .55), (tx + L / 2 - .2, y + 3.05, tz - .45), (190, 192, 196), mat=M_METAL))      # ladder rails
    bx.append(Box((tx - L / 2 + 2.6, y + 2.95, tz + .45), (tx + L / 2 - .2, y + 3.05, tz + .55), (190, 192, 196), mat=M_METAL))
    for k in range(10): bx.append(Box((tx - L / 2 + 2.8 + k * .55, y + 2.97, tz - .45), (tx - L / 2 + 2.85 + k * .55, y + 3.03, tz + .45), (170, 172, 176), mat=M_METAL))
    bx.append(Box((tx + L / 2 - .05, y + .7, tz - .8), (tx + L / 2 + .02, y + 1.2, tz + .8), (170, 172, 176), mat=M_METAL))          # hose reel door
    return bx


def _third(s, g, pw):
    """3rd-floor corridor (x around X3): renovation now, intact twenty years earlier; door 313 walled or not"""
    bx = []; L = []; era = s.get('era', 'now'); before = era in ('before', 'avant', 'past')
    x0, x1, z0, z1, h = X3 - 1.3, X3 + 1.3, 0., 12., 2.6
    doors = ((-1, 3.5, '309'), (-1, D313, '313'), (1, 2.5, '310'), (1, 6.5, '312'), (1, 10.0, '314'))
    if before:
        bx.append(Box((x0, -.05, z0), (x1, 0., z1), (40, 50, 90), tex={'+y': carpet_tex(12.0, 'old')}))
    else:
        bx.append(Box((x0, -.05, z0), (x1, 0., z1), (96, 96, 92), tex={'+y': concrete_tex(24, 24, 8)}, grain=.1))
        for (a, b) in ((2.0, 5.0), (8.5, 11.0)): bx.append(Box((x0 + .3, 0., a), (x1 - .3, .012, b), (90, 110, 140), refl=.15, cast=False, grain=.15))   # tarps
    bx.append(Box((x0 - .1, h, z0), (x1 + .1, h + .15, z1), (160, 156, 146) if before else (130, 128, 122), mat=M_CEIL_CLEAN if before else M_CEIL))
    kind = 'old' if before else 'raw'
    for side in (-1, 1):
        holes = [(z - .5, z + .5) for (sd, z, n) in doors if sd == side]
        xa, xb = (x1, x1 + .1) if side > 0 else (x0 - .1, x0)
        face = '-x' if side > 0 else '+x'
        for (a, b) in _segments(z0, z1, holes): _wall_x(bx_list := _Acc(), xa, xb, a, b, 0., h, kind, face); bx += bx_list.boxes
        for (a, b) in holes: bx.append(Box((xa, 2.1, a), (xb, h, b), (120, 100, 84) if before else (118, 116, 110), mat=M_CLEAN))
    for zz, face in ((z0 - .1, '+z'), (z1, '-z')):
        bx.append(Box((x0 - .1, 0, zz), (x1 + .1, h, zz + .1), (120, 100, 84) if before else (118, 116, 110), tex={face: wall_tex(32, kind, 31)}, mat=M_CLEAN))
    if not before: bx.append(Box((X3 - .6, .9, z1 - .02), (X3 + .6, 2.2, z1), (110, 86, 60), mat=M_WOODV))     # boarded window at the end
    for (sd, z, n) in doors:
        xin = sd * 1.3 + X3; hx = xin - sd * .027; cor = -sd                                          # the leaf (5 cm thick) stands just in front of the dark opening
        if n == '313' and not before:                                                                   # walled: blocks flush in the frame, sprayed number
            bx.append(Box((min(xin, xin + sd * .1), 0, z - .5), (max(xin, xin + sd * .1), 2.1, z + .5), (130, 128, 120), tex={('+x' if sd < 0 else '-x'): walled_tex()}, grain=.07))
            bx.append(C((xin - sd * .02, 1.95, z), (.01, .1, .2), (150, 120, 60), tex={('+x' if sd < 0 else '-x'): plate_tex('313', True)}))
            continue
        if not before and n != '313':                                                                   # other doors removed, plastic sheeting over the openings
            bx.append(Box((min(xin, xin - sd * .02), 0, z - .48), (max(xin, xin - sd * .02), 2.08, z + .48), (150, 158, 166), refl=.18, cast=False))          # opaque milky sheet (a screen-door pane flickers like TV snow at this size)
            bx.append(Box((min(xin, xin + sd * .5), 0, z - .5), (max(xin, xin + sd * .5), 2.1, z + .5), (8, 8, 10)))
            continue
        leaf = [B((-.025, 0, 0), (.05, 2.08, .88), (88, 52, 34), tex={('+x' if cor > 0 else '-x'): door_tex('old')}, mat=M_DOOR),
                C((cor * .03, 1.62, .44), (.01, .1, .18), (196, 160, 70), tex={('+x' if cor > 0 else '-x'): plate_tex(n, True)}, emis=.05),
                C((cor * .05, 1.0, .78), (.05, .04, .12), (200, 180, 120), mat=M_METAL)]
        bx += orient(leaf, 0., (hx, 0., z - .45))
        bx.append(Box((min(xin, xin + sd * .4), 0, z - .5), (max(xin, xin + sd * .4), 2.1, z + .5), (6, 6, 8)))
        if n == '313':
            gl = _lvl(s, 'under_door_glow')
            if gl > .02:
                fl = .75 + .25 * math.sin(g * 8.3) * math.sin(g * 4.7 + 1.3)
                bx.append(Box((min(xin - sd * .055, xin - sd * .1), 0., z - .42), (max(xin - sd * .055, xin - sd * .1), .025, z + .42), (255, 120, 40), emis=3. * gl * fl, cast=False))
                L.append(((xin - sd * .25, .08, z), (1., .42, .12), 1.1 * gl * fl, 1.6, False, None, _zw(ZONE_THIRD)))
    if before:
        for z in (2.0, 6.0, 10.0):
            for sd in (-1, 1):
                bx.append(C((X3 + sd * 1.27, 1.85, z), (.05, .18, .14), (255, 200, 140), emis=1.2 * pw, cast=False))
            L.append(((X3, 1.9, z), (1., .74, .46), .85 * pw, 2.8, False, None, _zw(ZONE_THIRD)))
    else:
        wl = _lvl(s, 'work_lamp')
        for z in (2.6, 6.0, 9.4):
            bx += [C((X3, h - .2, z), (.01, .4, .01), (30, 30, 30)), C((X3, h - .45, z), (.07, .1, .07), (255, 230, 170), emis=1.6 * pw, cast=False)]
            L.append(((X3, h - .55, z), (1., .84, .6), 1.15 * pw, 3.4, False, None, _zw(ZONE_THIRD)))
        bx += [C((X3 + .8, .7, 5.0), (.03, 1.4, .03), (30, 30, 30)), C((X3 + .8, 1.45, 5.0), (.22, .16, .1), (40, 40, 40), mat=M_METAL), C((X3 + .8, 1.45, 4.94), (.18, .12, .01), (255, 250, 220), emis=2.6 * wl, cast=False)]
        if wl > .02: L.append(((X3 + .6, 1.5, 4.6), (1., .96, .86), 1.6 * wl, 4.0, True, None, _zw(ZONE_THIRD)))
        bx += [C((X3 + .9, .17, 9.2), (.3, .34, .3), (220, 220, 214)), C((X3 - .9, .14, 2.6), (.26, .28, .26), (200, 196, 190)), Box((X3 + 1.05, 0, 3.4), (X3 + 1.15, 2.3, 4.0), (170, 150, 90), mat=M_WOODV)]
    return bx, L


class _Acc:
    """collects boxes for _wall_x outside a Scene"""
    def __init__(self): self.boxes = []
    def add(self, *b): self.boxes.extend(b); return self


# ================================================================== the place
LIST_KEYS = ('handset_pos', 'board_lamps', 'log_paper_at', 'screen_lines')


def state_of(state, u=None):
    """defaults + the written state; a number written [a, b] slides from a to b over the shot (u = shot progress, like `sets.sv`).
    The VOXEL painter asks for its slices without the shot progress: there [a, b] counts as its middle -- write [a, b, t0, t1]
    (resolved by frame.resolve_state for both styles) or a `state_track` when the movement matters in VOXEL"""
    s = dict(DEFAULTS)
    if (state or {}).get('moment') == 'matin': s.update(MORNING)
    s.update({k: v for k, v in (state or {}).items() if v is not None or k in ('smoke_front', 'stair_smoke')})
    for k, v in list(s.items()):
        if k in LIST_KEYS or not isinstance(v, (list, tuple)) or len(v) != 2 or not all(isinstance(x, (int, float)) for x in v): continue
        e = .5 if u is None else max(0., min(1., float(u))); e = e * e * (3 - 2 * e)
        s[k] = v[0] + (v[1] - v[0]) * e
    return s


def cam_zone(p):
    x, y, z = p
    if x > 30: return ZONE_THIRD
    return int(zone_fn(np.asarray([[x, max(y, 0.), z]], np.float32))[0])


class HotelNuit:
    """interface of a PIXEL 3D place (like `RoomSet` / `PompeStation`): base, anchors, scene per frame, lights per frame"""
    name = 'hotel_nuit'

    def __init__(self, spec=None):
        HC.register()
        self.spec = dict(spec or {}); self.spec.setdefault('type', 'hotel_nuit'); self.base = None
        self.anchors = dict(ANCHORS); self.anchors.update({k: tuple(v) for k, v in (self.spec.get('anchors') or {}).items()})
        self.room_rects = []; self.light_defs = []; self.door_info = {}; self._sc = None; self._dyn = None

    def build(self):
        if self.base is None: self.base = base()
        return self

    def _state(self, state, u=None):
        s = dict(self.spec.get('state') or {}); s.update(state or {})
        return state_of(s, u)

    def scene(self, state, t, u):
        self.build(); s = self._state(state, u)
        bx, L = dynamic(s, t); self._dyn = (s, L)
        sc = copy.copy(self.base); sc.boxes = list(self.base.boxes) + bx
        if s.get('moment') == 'matin': sc.ambient = (.11, .11, .12)
        from . import hotel_smoke as HS
        prm = HS.params(s)
        if prm is not None: sc.post_fn = HS.Post(prm, t)
        self._sc = sc
        return sc

    def lights(self, state, t, u, cam_pos):
        self.build()
        if self._dyn is None: self.scene(state, t, u)
        s, L = self._dyn
        zc = cam_zone(cam_pos); morning = s.get('moment') == 'matin'
        sc = self._sc
        if sc is not None:
            if zc == ZONE_OUT: sc.ambient = (.05, .055, .08); sc.fog = (.02, .024, .036); sc.fogk = .018
            elif zc == ZONE_THIRD: sc.ambient = (.04, .036, .034); sc.fog = (.02, .016, .014); sc.fogk = .05
            else: sc.ambient = (.05, .048, .052) if not morning else (.17, .17, .18); sc.fog = (.012, .012, .016); sc.fogk = .035
        L = list(L)
        L.append(((-25., 30., 60.), (.30, .38, .62), .55, 90., False, None, _zw(ZONE_OUT)))                 # moonlight / city glow
        if morning:
            L.append(((0., 5., -9.), (.78, .82, .9), 2.4, 18., False, None, _zw(ZONE_OUT)))                               # grey daylight in the street
            L.append(((-3.6, 2.5, 1.3), (.78, .82, .9), 2.0, 9.0, False, None, _zw(ZONE_LOBBY, spill={ZONE_COR: .2})))      # what comes in by the window
            L.append(((.6, 2.6, 1.6), (.74, .78, .86), 1.5, 8.0, False, None, _zw(ZONE_LOBBY, spill={ZONE_COR: .2})))        # ... and by the glass door
        # keep the strongest lights at the camera (the ray caster pays per light and per pixel)
        p = np.asarray(cam_pos, np.float32)
        def score(l):
            d2 = float(((np.asarray(l[0], np.float32) - p) ** 2).sum()); zw = l[6] if len(l) > 6 and l[6] is not None else None
            w = 1. if zw is None else max(zw[zc], .05)
            return l[2] / (1 + d2 / (l[3] * l[3])) * w
        L = sorted(L, key=score, reverse=True)[:int(self.spec.get('max_lights', 14))]
        out = [l for l in L]
        fill = float(self.spec.get('fill', .32))
        out.append(((float(cam_pos[0]), float(cam_pos[1]) + .3, float(cam_pos[2])), (.66, .72, .95), fill if not morning else .5, 2.4))
        pf = getattr(sc, 'post_fn', None)
        if pf is not None and hasattr(pf, 'lights'): pf.lights = out              # the smoke is lit by the same lights (hotel_smoke.Post)
        return out

    # ---- VOXEL: everything the state drives is a mobile part (re-sliced when `mobile_key` changes)
    def mobile(self, state, t):
        s = self._state(state); bx, L = dynamic(s, t)
        return bx, [(tuple(float(v) for v in l[0]), l[1], float(l[2]), float(l[3])) for l in L]

    def mobile_key(self, state):
        s = self._state(state)
        keys = ('power', 'ceiling', 'emergency', 'alarm', 'landline_ring', 'handset', 'board_313', 'screen', 'clock', 'panel_led', 'stair_door', 'cloison',
                'red_glass', 'lever', 'green_door', 'truck', 'beacons', 'window_fire', 'era', 'covers', 'log_paper', 'crowbar_in_box', 'under_door_glow') + tuple(f'door_{n}' for n, _, _ in ROOMS)
        return tuple(round(float(s.get(k) or 0.), 1) if isinstance(s.get(k), (int, float)) else str(s.get(k)) for k in keys)
