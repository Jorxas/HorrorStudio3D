"""Lieu prêt `phare_interieur` : l'intérieur de la tour du phare (15 novembre 2026, « Le Phare qui efface », parties 2 à 4).

Né pour la série d'horreur « Le Phare qui efface » (Alma, son frère Noé, le Veilleur), rangé ici pour toute histoire :
    LIEUX = {'tour': {'type': 'phare_interieur'},
             'tour_panne': {'type': 'phare_interieur', 'phare': 'panne'}}
Cohérent avec l'extérieur `phare_foret` : mêmes matériaux (chaux blanche et bandes rouge sombre, pierre, fer), même porte métallique riveinée
avec ses lampes grillagées, même nuit claire (ciel, lune) par les fenêtres. L'intérieur est plus grand que la tour vue du dehors (rayon 4,8 m :
c'est ce qu'il faut pour filmer en 9:16) ; on ne voit jamais les deux ensemble.

Repère (mètres) : centre de la tour en (0 ; 0), x vers la droite quand on regarde vers +z, y vers le haut. Angle θ en DEGRÉS comme un cap :
0 = +z (nord), 90 = +x (est), 180 = -z (sud, la PORTE), 270 = -x (ouest). Un point (r, θ) est (r sin θ ; r cos θ).
Rayon intérieur 4,8 m (mur de 0,5 m), deux niveaux :
  REZ (sol y = 0, plafond 3,9) coupé par une cloison est-ouest (z 0,5 à 0,7) percée d'un passage (x 1,4 à 2,6) :
    - ENTRÉE (au sud, z < 0,5) : face intérieure de la porte métallique (au sud, x -0,6 à 0,6, praticable : `porte`), béton humide (flaques),
      bas de l'escalier hélicoïdal (volée `montee`, le long du mur ouest, de θ 190 à 272), vieille horloge murale à balancier (cloison),
      tuyaux, caisses, cordages, établi à outils, tonneaux, jerricans, portemanteau et vieux ciré, extincteur, affiches ;
    - MACHINES (au nord, z > 0,7, « sous les pieds » de la salle des commandes) : BATTERIE de secours grosse comme un cercueil (2,1 x 0,8 m) et son
      afficheur rouge clignotant LISIBLE, gros câble qui traverse un TROU du mur (θ 20, au ras du sol) vers la terre humide dehors, GÉNÉRATEUR
      D'ESSAI adossé à la cloison (cabine à vitre dépolie où un acteur se tient, interrupteur à couteau, ÉTIQUETTE lisible, deux bobines de
      cuivre au sommet), établi, étagère de fusibles de rechange, vannes et manomètres, veilleuse de secours.
  ÉTAGE (sol y = 4,2, plafond 8,0) coupé par une cloison est-ouest (z 0,6 à 0,8) percée d'une porte (x -2,6 à -1,4, praticable : `porte_commandes`) :
    - PALIER (au sud, z < 0,6) : arrivée de la volée `montee` (trémie bordée d'une rambarde), départ de la volée `haut` vers la lanterne (le
      Veilleur en descend ; main courante), CERCLE DE LUMIÈRE au sol devant la porte (suspension en projecteur), réserve (étagère, bidons
      d'huile, lentilles de rechange) ;
    - SALLE DES COMMANDES (au nord, z > 0,8) : console contre le mur nord avec LEVIER ROUGE « ÉCHANGE » (`levier`), FUSIBLE NOIR « ARRÊT »
      (`fusible`), PLAQUE DE VERRE où la main de Noé est prisonnière d'une lumière blanche (`phare_foret.main_plaquee_blocs`), manomètres et
      voyants ; MUR GRAVÉ (7 traits dont 3 barrés et la phrase, LISIBLE en gros plan) ; horloge murale ; registre du gardien, lampe de bureau,
      radio, lampe à huile (reste allumée en panne) ; GRILLE au sol au-dessus de la batterie (lueur rouge d'en dessous) ; trois fenêtres.
Le niveau de la lanterne n'est pas construit : la volée `haut` disparaît par une trémie du plafond vers une lueur blanche.

Options (toutes facultatives) :
  phare           'allume' (défaut) | 'panne' | 'generateur' | 'brule' : état d'éclairage par défaut du lieu (le `state` du plan l'emporte)
  porte           'fermee' (défaut) | 'ouverte' : porte d'entrée par défaut ; porte_commandes 'ouverte' (défaut) | 'fermee'
  batterie_texte  lignes de l'afficheur (défaut ['SEPTIÈME ÉCLAIR', 'AUTOMATIQUE'], 15 caractères au plus par ligne)
  etiquette       lignes de l'étiquette du générateur (défaut : « MODE REFLET : MATÉRIALISE CE QUE LE VISITEUR DÉSIRE REVOIR. NE CONSTITUE
                  PAS UNE EXTRACTION. » en 6 lignes de 18 caractères au plus)
  gravure         lignes de la phrase gravée (défaut ['CE QUE LE FAISCEAU', 'PREND ATTEND', "DE L'AUTRE CÔTÉ"]) ; traits (7) ; barres (3)
  main_plaque     True (défaut) : la main gauche de Noé (cicatrice) derrière la plaque ; dict = arguments de `main_plaquee_blocs` ; False = aucune
  heure           '11:52' (défaut) : heure des deux horloges
  lampe_huile     True (défaut) ; dehors : True (défaut) : sol, rochers et pins vus par la porte et les fenêtres ; seed (défaut 7)

ÉTAT (`state` du plan ; les nombres s'animent : [a, b] sur le plan, [a, b, t0, t1] entre deux instants, ou `state_track`) :
  phare            'allume' | 'panne' | 'generateur' | 'brule' (lumières de service, veilleuses, voyant, générateur, bobines par défaut)
  porte            0 (fermée) .. 1 (ouverte, 100°) ; porte_commandes 0 .. 1 (ouverte vers la salle, 95°)
  levier           0 (haut) .. 1 (abaissé, tiré) ; fusible 1 (en place) .. 0 (arraché : absent de la console, l'acteur tient `od_fusible`)
  interrupteur     0 (haut, coupé) .. 1 (abaissé, en marche) — générateur d'essai
  bobines          'froides' | 'rouges' | 'etincelles' | 'brulees' ; cabine 0..2 (lumière pâle de la cabine du générateur) ; vitre 0 (nette) .. 1 (dépolie)
  voyant           'clignote' | 1 | 0 (afficheur de la batterie) ; horloge 0..1 (tremblement des aiguilles) ; lune 0..2
  eclair           0..3 (éclair blanc : fenêtres, ciel, voile blanc ; animable) ; eclairs [t, ...] (éclairs calés : instants du plan, double éclat)
  eclair_source    'fenetres' (défaut) | 'generateur' (le 7e éclair qui traverse la machine : cabine, bobines, salle des machines)
  balayage         1 | 0 : passage périodique du faisceau derrière les fenêtres (défaut 1 si `allume`) ; balayage_periode (s, défaut 8)
Repères (`anchors`, (x, z) au rez ; (x, y, z) à l'étage et en hauteur) et zones libres contrôlées : `ZONES_LIBRES`, `REPERES` plus bas.
Aides pour la mise en scène : `marche(volee, k)` (centre de la marche k, y = son dessus), `escalier(volee, s)` (point et cap le long de la volée),
`zone_de(p)` ; tests : tools/check_phare_interieur.py ; planches : tools/phare_interieur_sheet.py -> docs/catalogue/phare_interieur/.
"""
import copy, functools, math
import numpy as np

# ------------------------------------------------------------------ geometry
R_IN, R_OUT, CELL = 4.8, 5.3, .25
Y_ETAGE = 4.2; SLAB0 = 3.9; Y_PLAF = 8.0; ROOF = 8.3
PART_REZ = (.5, .7); PASS_REZ = (1.4, 2.6)                 # rez: entrée (south) | machines (north)
PART_ETA = (.6, .8); DOOR_ETA = (-2.6, -1.4)                # étage: palier (south) | commandes (north)
DOOR_W, DOOR_H = 1.2, 2.3                                   # entrance door, south wall (θ 180)
PASS_H = 2.6                                                # height of the inner openings (passage, control room door): the Veilleur's glass shows
STAIR_R = (3.7, 4.8); STAIR_RC = 4.25; NRISE = 17; RISE = Y_ETAGE / NRISE; DTH = 5.12
VOLEES = {'montee': dict(th0=190., sens=1, y0=0.), 'haut': dict(th0=222., sens=-1, y0=Y_ETAGE)}
HOLE_MONTEE = (230.5, 272.5)                                # étage floor hole over the upper steps of `montee`
HOLE_HAUT = (139., 203.)                                    # ceiling hole over the upper steps of `haut` (towards the lantern)
GRILLE = (-2.75, .95, -1.15, 1.55)                          # floor grate of the commandes, just inside its door, over the battery (x0, z0, x1, z1)
BATTERY = (-3.0, .74, -.9, 1.54)                            # x0, z0, x1, z1 ; height .85 ; against the rez partition, display facing north (+z)
GEN_X = (-.8, .8); GEN_Z = (3.42, 4.48)                     # generator against the north wall, facing SOUTH (-z) ; 2.7 m of free floor in front
CAB_X = (-.22, .78)                                         # booth (cabine) inside the generator ; the machine pillar is x -.8 .. -.27
CONSOLE = (-1.45, 3.7, 1.45, 4.55)                          # commandes console against the north wall
TROU_TH = 285.7                                             # cable hole through the wall (rez, at floor level), beside the battery's west end

# palette (same materials as phare_foret: whitewash, dark red band, stone, iron)
WHITE = (146, 144, 138); RED_B = (104, 38, 36); STONE = (118, 116, 110); STONE_D = (88, 86, 82); IRON = (48, 52, 58); IRON_L = (82, 86, 94)
CONC = (104, 102, 98); WOOD = (96, 74, 54); WOOD_D = (70, 52, 38); COPPER = (184, 110, 60); BRASS = (176, 146, 80); RUST = (120, 70, 46)
COAT_BLACK = (24, 26, 30); CAGE_W = (236, 240, 255)

# camera zones (also light zones): 0 outside, 1 entrée, 2 machines, 3 palier, 4 commandes
ZONES = {0: 'dehors', 1: 'entree', 2: 'machines', 3: 'palier', 4: 'commandes'}

# free places for the actors (name: (x, y, z, radius)) — no block at y + 0.5 / 1.0 / 1.6 (checked by tools/check_phare_interieur.py)
ZONES_LIBRES = {'entree': (-1.2, 0., -2.0, .55), 'entree.porte': (0., 0., -4.05, .3), 'escalier.pied': (-.3, 0., -4.1, .2),
                'machines': (.9, 0., 1.9, .55), 'machines.batterie': (-1.95, 0., 2.15, .3), 'machines.generateur': (.28, 0., 2.85, .3),
                'machines.cabine': (.28, .15, 3.95, .22), 'machines.trou': (-3.85, 0., 2.0, .2),
                'palier': (-2.0, Y_ETAGE, -.45, .45), 'palier.porte': (-2.0, Y_ETAGE, .3, .2), 'palier.arrivee': (-3.98, Y_ETAGE, .3, .18),
                'haut.pied': (-2.95, Y_ETAGE, -3.05, .2), 'commandes': (.4, Y_ETAGE, 2.0, .55), 'commandes.console': (0., Y_ETAGE, 3.3, .25),
                'commandes.porte': (-2.0, Y_ETAGE, 1.25, .2), 'commandes.mur': (1.2, Y_ETAGE, 1.6, .3)}


def pol(r, th):
    t = math.radians(th); return (r * math.sin(t), r * math.cos(t))


def ang(x, z):
    return math.degrees(math.atan2(x, z)) % 360.


def _in_arc(a, a0, a1):
    a = a % 360.; a0 = a0 % 360.; a1 = a1 % 360.
    return a0 <= a <= a1 if a0 <= a1 else (a >= a0 or a <= a1)


def block(at, size, color, material='plaster', **kw):
    return dict(at=[round(float(v), 4) for v in at], size=[round(float(v), 4) for v in size], color=[int(c) for c in color], material=material, **kw)


def _runs(pred, x0, x1, z0, z1, cell, axis='x'):
    """cells of a grid (cell centres) where pred(x, z) holds, merged into runs along x (or z) -> [(xa, xb, za, zb)]"""
    out = []
    nx = int(math.ceil((x1 - x0) / cell)); nz = int(math.ceil((z1 - z0) / cell))
    if axis == 'x':
        for j in range(nz):
            zc = z0 + (j + .5) * cell; start = None
            for i in range(nx + 1):
                xc = x0 + (i + .5) * cell
                ok = i < nx and pred(xc, zc)
                if ok and start is None: start = i
                if not ok and start is not None:
                    out.append((x0 + start * cell, x0 + i * cell, zc - cell / 2, zc + cell / 2)); start = None
    else:
        for i in range(nx):
            xc = x0 + (i + .5) * cell; start = None
            for j in range(nz + 1):
                zc = z0 + (j + .5) * cell
                ok = j < nz and pred(xc, zc)
                if ok and start is None: start = j
                if not ok and start is not None:
                    out.append((xc - cell / 2, xc + cell / 2, z0 + start * cell, z0 + j * cell)); start = None
    return out


def _slab(runs, y0, y1, col, mat='stone', **kw):
    return [block(((a + b) / 2, y0, (c + d) / 2), (b - a, y1 - y0, d - c), col, mat, **kw) for (a, b, c, d) in runs]


def _best_runs(pred, x0, x1, z0, z1, cell):
    a = _runs(pred, x0, x1, z0, z1, cell, 'x'); b = _runs(pred, x0, x1, z0, z1, cell, 'z')
    return a if len(a) <= len(b) else b


# ------------------------------------------------------------------ the stairs (for the director)
def _step_arc(volee, k):
    v = VOLEES[volee]
    if v['sens'] > 0: return v['th0'] + (k - 1) * DTH, v['th0'] + k * DTH
    return v['th0'] - k * DTH, v['th0'] - (k - 1) * DTH


def marche(volee, k):
    """centre (x, y, z) du dessus de la marche k (1..16) de la volée `montee` (rez -> étage) ou `haut` (étage -> lanterne), sur la ligne de foulée
    (rayon 4,25) ; k = 0 : le sol devant la première marche ; k = 17 : l'arrivée (palier, ou trémie du plafond pour `haut`)"""
    v = VOLEES[volee]; k = max(0, min(NRISE, int(k)))
    if k == 0: th = v['th0'] - v['sens'] * DTH * .6
    elif k == NRISE: th = v['th0'] + v['sens'] * DTH * (NRISE - 1 + .7)
    else: a, b = _step_arc(volee, k); th = (a + b) / 2
    x, z = pol(STAIR_RC, th)
    return (round(x, 3), round(v['y0'] + k * RISE, 3), round(z, 3))


def escalier(volee, s, descend=False):
    """point de la ligne de foulée de la volée à la fraction s (0 = pied, 1 = arrivée) -> (x, y, z, cap en radians) ; y monte d'une marche à
    l'autre (dessus de la marche sous le pied) ; le cap regarde vers le HAUT de la volée (`descend` : vers le bas)"""
    v = VOLEES[volee]; s = max(0., min(1., float(s)))
    kf = s * NRISE; k = int(math.floor(kf + 1e-6))
    th = v['th0'] + v['sens'] * DTH * (kf - .4)
    x, z = pol(STAIR_RC, th); y = v['y0'] + min(k, NRISE) * RISE
    tang = th + 90. * v['sens'] if not descend else th - 90. * v['sens']
    return (round(x, 3), round(y, 3), round(z, 3), round(math.radians(tang), 4))


def zone_de(p):
    """zone d'un point (x, y, z) : 0 dehors, 1 entrée, 2 machines, 3 palier, 4 commandes"""
    x, y, z = float(p[0]), float(p[1]), float(p[2])
    if math.hypot(x, z) > R_IN + .05: return 0
    if y < (SLAB0 + Y_ETAGE) / 2: return 1 if z < (PART_REZ[0] + PART_REZ[1]) / 2 else 2
    return 3 if z < (PART_ETA[0] + PART_ETA[1]) / 2 else 4


def _zone_fn(P):
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    out = np.where(y < (SLAB0 + Y_ETAGE) / 2, np.where(z < (PART_REZ[0] + PART_REZ[1]) / 2, 1, 2), np.where(z < (PART_ETA[0] + PART_ETA[1]) / 2, 3, 4))
    return np.where(np.hypot(x, z) > R_IN + .05, 0, out).astype(np.int32)


# ------------------------------------------------------------------ walls, floors, partitions
WINDOWS = [  # (name, θ, half width (m), y0, y1, zone) ; moon: the window looks at the moon (north-west)
    ('entree.fenetre', 135., .32, 1.5, 2.55, 1), ('entree.fenetre_haute', 228., .3, 2.55, 3.4, 1),
    ('machines.fenetre', 315., .32, 1.75, 2.75, 2),
    ('palier.fenetre', 250., .32, Y_ETAGE + 1.25, Y_ETAGE + 2.45, 3), ('palier.fenetre_est', 115., .32, Y_ETAGE + 1.35, Y_ETAGE + 2.45, 3),
    ('commandes.fenetre', 330., .36, Y_ETAGE + 1.2, Y_ETAGE + 2.55, 4), ('commandes.fenetre_est', 30., .36, Y_ETAGE + 1.2, Y_ETAGE + 2.55, 4),
    ('commandes.fenetre_lat', 75., .32, Y_ETAGE + 1.25, Y_ETAGE + 2.45, 4)]
MOON_WINDOWS = ('machines.fenetre', 'commandes.fenetre', 'palier.fenetre')


def _openings():
    """wall openings: (pred(x, z) on the ring cells, y0, y1)"""
    ops = []
    for (_, th, hw, y0, y1, _) in WINDOWS:
        ops.append(((lambda th_, hw_: (lambda x, z: _in_arc(ang(x, z), th_ - math.degrees(hw_ / R_IN), th_ + math.degrees(hw_ / R_IN))))(th, hw), y0, y1))
    ops.append(((lambda x, z: abs(x) < DOOR_W / 2 and z < 0), 0., DOOR_H))                     # entrance door (south)
    hw = math.degrees(.3 / R_IN)
    ops.append(((lambda x, z: _in_arc(ang(x, z), TROU_TH - hw, TROU_TH + hw)), .0, .6))         # cable hole (machines, floor level)
    return ops


def tower_walls():
    """the round wall of the two levels (voxel ring, cells of 25 cm), lower band dark red, whitewash above ; openings cut out.
    Cells untouched by an opening are merged into long runs (two boxes high per level) ; the cells of an opening are cut around it."""
    B = []
    ring = lambda x, z: R_IN <= math.hypot(x, z) < R_OUT
    ops = _openings()
    for (ya, yb, low) in ((0., SLAB0, 1.1), (Y_ETAGE, ROOF, Y_ETAGE + 1.1)):
        lv = [(p, max(a, ya), min(b, yb)) for (p, a, b) in ops if b > ya and a < yb]
        free = lambda x, z, lv_=lv: ring(x, z) and not any(p(x, z) for (p, _, _) in lv_)
        runs = _runs(free, -R_OUT, R_OUT, -R_OUT, R_OUT, CELL)
        B += _slab(runs, ya, low, RED_B, 'plaster') + _slab(runs, low, yb, WHITE, 'card')
        n = int(math.ceil(2 * R_OUT / CELL))
        for j in range(n):
            zc = -R_OUT + (j + .5) * CELL
            for i in range(n):
                xc = -R_OUT + (i + .5) * CELL
                if not ring(xc, zc): continue
                hit = [(a, b) for (p, a, b) in lv if p(xc, zc)]
                if not hit: continue
                ys = [ya]
                for (a, b) in sorted(hit): ys += [a, b]
                ys.append(yb)
                for y0, y1 in zip(ys[0::2], ys[1::2]):
                    if y1 - y0 < .01: continue
                    for (c0, c1, col, mt) in ((y0, min(y1, low), RED_B, 'plaster'), (max(y0, low), y1, WHITE, 'card')):
                        if c1 - c0 > .01: B.append(block((xc, c0, zc), (CELL, c1 - c0, CELL), col, mt))
    # the shaft above the hole of the upper flight (to the lantern, not built): closed on every side, open below
    sec = lambda x, z, m=0.: _in_arc(ang(x, z), HOLE_HAUT[0] - m, HOLE_HAUT[1] + m)
    solid = lambda x, z: math.hypot(x, z) < R_OUT and sec(x, z, 6.) and not (3.55 <= math.hypot(x, z) < R_IN + .05 and sec(x, z))
    B += _slab(_best_runs(solid, -R_OUT, R_OUT, -R_OUT, R_OUT, CELL), ROOF, 11.0, WHITE, 'plaster')
    B += _slab(_best_runs(lambda x, z: math.hypot(x, z) < R_OUT and sec(x, z, 6.), -R_OUT, R_OUT, -R_OUT, R_OUT, .5), 11.0, 11.3, STONE_D, 'stone')
    return B


def slabs():
    """the floor of the étage (with the hole of `montee` and the grate) and the ceiling of the étage (with the hole of `haut`) ; iron beams"""
    B = []
    def floor_pred(x, z):
        r = math.hypot(x, z)
        if r >= R_OUT: return False
        if STAIR_R[0] - .06 <= r < R_IN + .1 and _in_arc(ang(x, z), *HOLE_MONTEE): return False
        if GRILLE[0] <= x <= GRILLE[2] and GRILLE[1] <= z <= GRILLE[3]: return False
        return True
    B += _slab(_runs(floor_pred, -R_OUT, R_OUT, -R_OUT, R_OUT, CELL), SLAB0, Y_ETAGE, (112, 108, 100), 'stone')
    def roof_pred(x, z):
        r = math.hypot(x, z)
        if r >= R_OUT: return False
        if 3.55 <= r < R_IN + .1 and _in_arc(ang(x, z), *HOLE_HAUT): return False
        return True
    B += _slab(_runs(roof_pred, -R_OUT, R_OUT, -R_OUT, R_OUT, CELL), Y_PLAF, ROOF, (96, 94, 90), 'stone')
    for (y, xs, zmin) in ((SLAB0 - .22, (-2.4, 1.0), None), (Y_PLAF - .22, (-1.8, 1.6), -3.0)):     # iron beams under each ceiling (along z), clear of the holes
        for x in xs:
            h = math.sqrt(R_IN ** 2 - x * x) - .05
            za = -h if zmin is None else max(-h, zmin)
            B.append(block((x, y, (za + h) / 2), (.16, .22, h - za), IRON, 'metal'))
    # grate over the battery: frame and bars (top at the étage floor)
    x0, z0, x1, z1 = GRILLE
    B += [block(((x0 + x1) / 2, Y_ETAGE - .05, z0 - .02), (x1 - x0 + .08, .05, .04), IRON, 'metal'), block(((x0 + x1) / 2, Y_ETAGE - .05, z1 + .02), (x1 - x0 + .08, .05, .04), IRON, 'metal'),
          block((x0 - .02, Y_ETAGE - .05, (z0 + z1) / 2), (.04, .05, z1 - z0), IRON, 'metal'), block((x1 + .02, Y_ETAGE - .05, (z0 + z1) / 2), (.04, .05, z1 - z0), IRON, 'metal')]
    n = 6
    for i in range(n):
        z = z0 + (i + .5) * (z1 - z0) / n
        B.append(block(((x0 + x1) / 2, Y_ETAGE - .035, z), (x1 - x0, .035, .025), (56, 58, 62), 'metal'))
    for x in (x0 + (x1 - x0) / 3, x0 + 2 * (x1 - x0) / 3):
        B.append(block((x, Y_ETAGE - .07, (z0 + z1) / 2), (.03, .07, z1 - z0), (56, 58, 62), 'metal'))
    return B


def partitions():
    """rez partition (entrée | machines) with its passage, étage partition (palier | commandes) with the door frame ; the door leaves are dynamic"""
    B = []
    def wall_z(za, zb, y0, y1, gap, col_lo, col_hi):
        out = []
        xm = math.sqrt(R_IN ** 2 - max(abs(za), abs(zb)) ** 2) + .12
        segs = [(-xm, gap[0]), (gap[1], xm)]
        for (a, b) in segs:
            out.append(block(((a + b) / 2, y0, (za + zb) / 2), (b - a, 1.1, zb - za), col_lo, 'plaster'))
            out.append(block(((a + b) / 2, y0 + 1.1, (za + zb) / 2), (b - a, y1 - y0 - 1.1, zb - za), col_hi, 'card'))
        out.append(block(((gap[0] + gap[1]) / 2, y0 + PASS_H, (za + zb) / 2), (gap[1] - gap[0], y1 - y0 - PASS_H, zb - za), col_hi, 'card'))
        for gx in gap:                                                           # iron frame of the opening
            out.append(block((gx, y0, (za + zb) / 2), (.1, PASS_H + .04, zb - za + .06), IRON, 'metal'))
        out.append(block(((gap[0] + gap[1]) / 2, y0 + PASS_H - .02, (za + zb) / 2), (gap[1] - gap[0] + .1, .08, zb - za + .06), IRON, 'metal'))
        return out
    B += wall_z(PART_REZ[0], PART_REZ[1], 0., SLAB0, PASS_REZ, RED_B, WHITE)
    B += wall_z(PART_ETA[0], PART_ETA[1], Y_ETAGE, Y_PLAF, DOOR_ETA, RED_B, WHITE)
    return B


def stairs():
    """the two helical flights (cantilevered stone treads, voxel wedges), their stepped handrails on the inner edge, the railing of the hole"""
    B = []
    for volee in ('montee', 'haut'):
        v = VOLEES[volee]
        for k in range(1, NRISE):
            a, b = _step_arc(volee, k); top = v['y0'] + k * RISE
            pred = (lambda a_, b_: (lambda x, z: STAIR_R[0] <= math.hypot(x, z) < R_IN + .02 and _in_arc(ang(x, z), a_, b_)))(a, b)
            pts = [pol(r, t_) for r in (STAIR_R[0], R_IN + .1) for t_ in (a, (a + b) / 2, b)]
            c = .2; gx0 = math.floor((min(p[0] for p in pts) - c) / c) * c; gx1 = math.ceil((max(p[0] for p in pts) + c) / c) * c
            gz0 = math.floor((min(p[1] for p in pts) - c) / c) * c; gz1 = math.ceil((max(p[1] for p in pts) + c) / c) * c
            for bk in _slab(_best_runs(pred, gx0, gx1, gz0, gz1, c), top - .14, top, (128, 124, 116) if k % 2 else (120, 116, 108), 'stone', group=f'escalier.{volee}'):
                B.append(bk)
            # the handrail over the inner edge of the tread: a short bar along the dominant axis (a stepped, voxel rail), a post every third step
            hx, hz = pol(STAIR_R[0] + .06, (a + b) / 2); ex, ez = pol(STAIR_R[0] + .06, b); fx, fz = pol(STAIR_R[0] + .06, a)
            sx, sz = abs(ex - fx), abs(ez - fz)
            size = (sx + .06, .05, .05) if sx >= sz else (.05, .05, sz + .06)
            B.append(block((hx, top + .86, hz), size, (40, 42, 46), 'metal', group=f'rampe.{volee}'))
            if k % 3 == 1:
                B.append(block((hx, top, hz), (.04, .88, .04), (40, 42, 46), 'metal', group=f'rampe.{volee}'))
    # railing around the hole of `montee` on the étage floor (inner edge r = 3.6) and its end posts
    th = HOLE_MONTEE[0]
    while th <= HOLE_MONTEE[1] + 1e-6:
        x, z = pol(3.6, th)
        B.append(block((x, Y_ETAGE + .95, z), (.07, .05, .07), (40, 42, 46), 'metal', group='rambarde'))
        B.append(block((x, Y_ETAGE + .5, z), (.05, .04, .05), (40, 42, 46), 'metal', group='rambarde'))
        if int(round((th - HOLE_MONTEE[0]) / 3.)) % 3 == 0: B.append(block((x, Y_ETAGE, z), (.05, .95, .05), (40, 42, 46), 'metal', group='rambarde'))
        th += 3.
    for t_ in HOLE_MONTEE:
        x, z = pol(4.2, t_); B.append(block((x, Y_ETAGE, z), (.06, 1.0, .06), (40, 42, 46), 'metal', group='rambarde'))
    return B


# ------------------------------------------------------------------ details (rich set dressing)
def _coil(x, z, y=0., col=(150, 128, 92), r=.32, n=3):
    """a coiled rope: stacked octagonal rings, darker heart"""
    B = []
    for i in range(n):
        rr = r * (1 - .06 * i); yy = y + i * .07
        B += [block((x, yy, z), (2 * rr, .07, rr), col, 'fabric'), block((x, yy, z), (rr, .07, 2 * rr), col, 'fabric')]
    B.append(block((x, y + .005, z), (r * .7, n * .07 + .01, r * .7), (60, 50, 38), 'fabric'))
    return B


def _caged_lamp(x, y, z, col=CAGE_W, wall=None):
    """a caged bulkhead lamp (like the two lamps outside the door) ; `wall` '+z'|'-z'|'+x'|'-x' mounts it on a wall"""
    B = [block((x, y, z), (.14, .2, .14), col, 'light', emissive=1.5, no_shadow=True)]
    for dy in (-.02, .1, .2):
        B.append(block((x, y + dy, z), (.18, .025, .18), IRON, 'metal', no_shadow=True))
    for (dx, dz) in ((-.08, 0), (.08, 0), (0, -.08), (0, .08)):
        B.append(block((x + dx, y - .02, z + dz), (.02, .24, .02), IRON, 'metal', no_shadow=True))
    if wall:
        nx, nz = {'+z': (0, 1), '-z': (0, -1), '+x': (1, 0), '-x': (-1, 0)}[wall]
        B.append(block((x - nx * .14, y + .08, z - nz * .14), (.06 if nx == 0 else .2, .05, .2 if nx == 0 else .06), IRON, 'metal'))
    return B


def _pipe_v(x, z, y0, y1, d=.09, col=(70, 74, 80)):
    return [block((x, y0, z), (d, y1 - y0, d), col, 'metal')] + [block((x, yy, z), (d + .04, .05, d + .04), (50, 52, 58), 'metal') for yy in (y0 + .3, y1 - .4)]


def _gauge(x, y, z, face='-z', r=.09, needle=.3):
    """a pressure gauge (manomètre): brass rim, cream dial, red needle"""
    nx, nz = {'+z': (0, 1), '-z': (0, -1), '+x': (1, 0), '-x': (-1, 0)}[face]
    w = (2 * r, 2 * r, .04) if nx == 0 else (.04, 2 * r, 2 * r)
    B = [block((x, y - r, z), w, BRASS, 'metal'), block((x + nx * .021, y - r * .8, z + nz * .021), (w[0] * .8 if nx == 0 else .005, 1.6 * r, w[2] * .8 if nz == 0 else .005), (226, 220, 196), 'card')]
    s = math.sin(needle * 4 - 2); c = math.cos(needle * 4 - 2)
    lx, lz = (s * r * .35, 0.) if nx == 0 else (0., s * r * .35)
    B.append(block((x + nx * .025 + lx, y + c * r * .2 - .01, z + nz * .025 + lz), (.012 if nx == 0 else .006, r * .55, .006 if nx == 0 else .012), (190, 30, 30), 'card'))
    return B


def _valve(x, y, z, face='-z', col=(170, 40, 36)):
    nx, nz = {'+z': (0, 1), '-z': (0, -1), '+x': (1, 0), '-x': (-1, 0)}[face]
    B = [block((x, y - .04, z), (.08, .08, .08), IRON, 'metal')]
    for (a, b) in ((.22, .03), (.03, .22)):
        w = (a, b, .03) if nx == 0 else (.03, b, a)
        B.append(block((x + nx * .07, y - b / 2, z + nz * .07), w, col, 'metal'))
    return B


def _drip_stain(x, y, z, face='-z', h=1.2, col=RUST):
    nx, nz = {'+z': (0, 1), '-z': (0, -1), '+x': (1, 0), '-x': (-1, 0)}[face]
    return [block((x, y - h, z), (.06 if nx == 0 else .006, h, .006 if nx == 0 else .06), col, 'plaster'),
            block((x + (.05 if nx == 0 else 0), y - h * .6, z + (0 if nx == 0 else .05)), (.03 if nx == 0 else .006, h * .6, .006 if nx == 0 else .03), col, 'plaster')]


def _window_dress(name, th, hw, y0, y1):
    """deep stone sill, two iron bars, a rust streak under the sill"""
    B = []
    xi, zi = pol(R_IN - .02, th); xo, zo = pol((R_IN + R_OUT) / 2, th)
    w = 2 * hw + .16
    horiz = abs(math.cos(math.radians(th))) > .7                                 # facing roughly ±z: the sill runs along x
    sill = (w, .08, R_OUT - R_IN + .14) if horiz else (R_OUT - R_IN + .14, .08, w)
    B.append(block(((xi + xo) / 2, y0 - .08, (zi + zo) / 2), sill, STONE, 'stone'))
    for s in (-.33, .33):
        ox, oz = pol(hw * s * 2, th + 90.)
        bx, bz = xi + (xo - xi) * .6 + ox * .55, zi + (zo - zi) * .6 + oz * .55
        B.append(block((bx, y0, bz), (.035, y1 - y0, .035), (36, 36, 40), 'metal', no_shadow=True))
    mx, mz = xi + (xo - xi) * .6, zi + (zo - zi) * .6
    B.append(block((mx, y0 + (y1 - y0) * .55, mz), (2 * hw * .9 if horiz else .03, .03, .03 if horiz else 2 * hw * .9), (36, 36, 40), 'metal', no_shadow=True))
    return B


def entree_blocs(spec):
    """the entrance: door frame (the leaf is dynamic), doormat, coat rack with an old oilskin, crates, ropes, barrels, tool board, pipes,
    noticeboard, extinguisher, clock on the partition (dynamic hands and pendulum), lamps"""
    B = []
    zw = -R_IN + .02
    B += [block((-DOOR_W / 2 - .06, 0, zw + .05), (.12, DOOR_H + .1, .14), IRON, 'metal'), block((DOOR_W / 2 + .06, 0, zw + .05), (.12, DOOR_H + .1, .14), IRON, 'metal'),
          block((0, DOOR_H, zw + .05), (DOOR_W + .24, .14, .14), IRON, 'metal')]
    for yy in (.3, 1.1, 1.9):                                                     # hinges on the east post
        B.append(block((DOOR_W / 2 + .02, yy, zw + .1), (.06, .16, .05), (36, 36, 40), 'metal'))
    B.append(block((0, 0, zw + .55), (.9, .02, .55), (40, 36, 34), 'fabric'))                                    # doormat (inside)
    B += _caged_lamp(0., 2.62, zw + .22, wall='-z')
    # sign over the door, inside: « SORTIE » (texture box added by the class) ; coat rack + old black oilskin (it looks like the Veilleur's)
    cx, cz = 1.55, -4.05
    B += [block((cx, 0, cz), (.36, .05, .36), WOOD_D, 'wood'), block((cx, 0, cz), (.06, 1.8, .06), WOOD_D, 'wood'),
          block((cx, 1.62, cz), (.5, .04, .04), WOOD_D, 'wood'), block((cx, 1.62, cz), (.04, .04, .5), WOOD_D, 'wood'),
          block((cx + .16, .7, cz), (.12, .95, .34), (30, 32, 36), 'fabric', reflect=.12), block((cx + .17, 1.52, cz), (.14, .14, .2), (40, 42, 46), 'fabric'),
          block((cx - .2, 1.42, cz), (.2, .1, .2), (40, 60, 92), 'fabric')]                                    # a blue cap
    # boots under the rack
    B += [block((cx - .18, 0, cz + .12), (.12, .26, .22), (24, 24, 26), 'fabric'), block((cx - .02, 0, cz + .14), (.12, .26, .22), (24, 24, 26), 'fabric')]
    # crates (stacked), ropes, barrels, jerrycans, bucket on the east side
    for (x, z, s, h) in ((3.2, -2.6, .7, .55), (3.25, -2.6, .55, .45), (3.75, -1.6, .6, .5), (2.5, -3.5, .6, .5)):
        y0 = .55 if (x, z) == (3.25, -2.6) else 0.
        B += [block((x, y0, z), (s, h, s), (122, 94, 62), 'wood'), block((x, y0 + h * .45, z - s / 2 - .005), (s * .96, .06, .01), (90, 68, 44), 'wood'),
              block((x - s / 2 - .005, y0 + h * .45, z), (.01, .06, s * .96), (90, 68, 44), 'wood')]
    B += _coil(2.1, -2.3) + _coil(3.95, -.55, y=0., col=(140, 118, 86), r=.28) + _coil(3.75, -1.6, y=.5, r=.22, n=2)
    for (x, z, c) in ((-2.6, -.25, (70, 90, 70)), (-2.0, -.1, (120, 50, 40))):
        B += [block((x, 0, z), (.56, .86, .56), c, 'metal'), block((x, 0, z), (.6, .06, .6), (50, 50, 54), 'metal'), block((x, .78, z), (.6, .06, .6), (50, 50, 54), 'metal'),
              block((x + .12, .86, z + .1), (.1, .03, .1), (40, 40, 44), 'metal')]
    B += [block((-1.3, 0, -.05), (.26, .44, .17), (170, 40, 36), 'metal'), block((-1.3, .44, -.1), (.06, .06, .04), (40, 40, 44), 'metal'),
          block((-.95, 0, -.1), (.3, .3, .3), (90, 92, 98), 'metal'), block((-.95, .3, -.1), (.32, .03, .32), (60, 62, 68), 'metal')]
    # tool board on the partition (south face), east of the clock: hammer, wrench, saw, crowbar silhouettes
    zf = PART_REZ[0] - .03
    B += [block((.75, 1.0, zf), (1.0, .9, .04), (112, 86, 60), 'wood')]
    for (x, y, w, h, c) in ((.42, 1.45, .05, .34, (60, 44, 32)), (.42, 1.72, .18, .07, (70, 72, 78)), (.62, 1.3, .05, .45, (150, 152, 158)), (.62, 1.72, .12, .06, (150, 152, 158)),
                            (.85, 1.18, .28, .12, (160, 160, 166)), (.85, 1.3, .3, .02, (60, 44, 32)), (1.08, 1.12, .04, .62, (60, 62, 70)), (1.13, 1.7, .1, .04, (60, 62, 70))):
        B.append(block((x, y, zf - .03), (w, h, .02), c, 'metal'))
    # noticeboard and extinguisher on the partition, east of the passage
    B += [block((3.5, 1.0, PART_REZ[0] - .05), (.9, .7, .05), (120, 96, 66), 'wood'), block((3.5, 1.04, PART_REZ[0] - .08), (.82, .62, .01), (176, 150, 110), 'card')]
    B += [block((3.05, .5, PART_REZ[0] - .1), (.16, .5, .16), (190, 30, 30), 'metal'), block((3.05, 1.0, PART_REZ[0] - .1), (.06, .1, .06), (30, 30, 34), 'metal')]
    # pipes: two verticals in the south-east, a horizontal run along the partition, through the ceiling
    B += _pipe_v(4.1, -2.4, 0., SLAB0) + _pipe_v(3.85, -2.65, 0., SLAB0, .07, (120, 76, 50))
    B.append(block((.0, 3.45, PART_REZ[0] - .1), (8.6, .1, .1), (70, 74, 80), 'metal'))
    B += _valve(4.03, 1.3, -2.4, '-x') + _gauge(3.79, 1.6, -2.65, '-x', .08, .6)
    # bulb over the middle, a bench, a floor drain
    B += [block((.6, 3.3, -1.7), (.02, .6, .02), (30, 30, 30), 'metal'), block((.6, 3.18, -1.7), (.1, .12, .1), (255, 236, 196), 'light', emissive=1.6, no_shadow=True)]
    B += [block((-3.0, .42, -1.7), (.36, .06, 1.3), WOOD, 'wood'), block((-3.0, 0, -2.2), (.3, .42, .06), WOOD_D, 'wood'), block((-3.0, 0, -1.2), (.3, .42, .06), WOOD_D, 'wood')]
    B += [block((.9, 0, -1.0), (.32, .012, .32), (40, 40, 44), 'metal'), block((.9, .002, -1.0), (.24, .012, .02), (20, 20, 22), 'metal')]
    # damp stains / rust streaks on the inner wall and the partition
    B += _drip_stain(-1.9, 3.3, PART_REZ[0] - .015, '-z', 1.3) + _drip_stain(2.2, 3.4, PART_REZ[0] - .015, '-z', 1.6)
    return B


def machines_blocs(spec):
    """the machine room: battery-coffin against the partition (display: texture box of the class, facing the room), the cable through the
    hole in the wall beside it and the wet earth outside, the cable to the generator, the generator against the north wall facing south
    (pillar with gauges, booth with its frosted glass, header carrying the label ; switch, coils and glass are dynamic), workbench, shelves
    of spare fuses and bulbs, valves and gauges, drum and jerrycans, a puddle"""
    B = []
    x0, z0, x1, z1 = BATTERY; xc = (x0 + x1) / 2; zc = (z0 + z1) / 2
    B += [block((xc, 0, zc), (x1 - x0 - .1, .1, z1 - z0 - .1), (30, 30, 32), 'metal'),
          block((xc, .1, zc), (x1 - x0, .68, z1 - z0), (54, 60, 56), 'metal'),
          block((xc, .78, zc), (x1 - x0 + .06, .07, z1 - z0 + .06), (42, 46, 44), 'metal')]
    for i in range(7):                                                               # ribs on the front (north) face, around the display
        x = x0 + .12 + i * (x1 - x0 - .24) / 6
        if abs(x - xc) < .52: continue
        B.append(block((x, .14, z1 + .025), (.05, .6, .05), (44, 48, 46), 'metal'))
    B += [block((x0 + .3, .85, zc - .1), (.1, .12, .1), COPPER, 'metal'), block((x0 + .3, .97, zc - .1), (.12, .04, .12), (180, 30, 30), 'metal'),
          block((x1 - .3, .85, zc - .1), (.1, .12, .1), COPPER, 'metal'), block((x1 - .3, .97, zc - .1), (.12, .04, .12), (24, 24, 26), 'metal')]
    for i in range(6):                                                                # yellow / black warning band on the lid's front edge
        B.append(block((x0 + .2 + i * .34, .79, z1 + .035), (.17, .05, .01), (220, 180, 30) if i % 2 == 0 else (24, 24, 26), 'plaster'))
    B.append(block((xc, .29, z1 + .03), (.92, .45, .03), (20, 20, 22), 'metal'))                                   # display bezel
    # the cable: from the battery's west end, along the floor, through the hole in the wall, into the wet earth outside
    hx, hz = pol(R_IN, TROU_TH)
    B += [block((x0 - .05, .3, hz), (.08, .5, .08), (18, 18, 20), 'fabric'), block(((x0 - .05 + hx - .9) / 2, .02, hz), (x0 - hx + .85, .08, .08), (18, 18, 20), 'fabric'),
          block((hx - .55, .05, hz), (.9, .08, .08), (18, 18, 20), 'fabric')]
    B += [block((hx + .05, 0, hz + .3), (.2, .14, .14), STONE_D, 'stone'), block((hx + .02, .02, hz - .28), (.2, .1, .14), STONE_D, 'stone')]   # broken lips of the hole
    B += [block((hx - 1.3, 0, hz), (1.0, .42, 1.1), (92, 66, 44), 'stone', reflect=.15), block((hx - 1.35, .42, hz + .1), (.6, .16, .7), (104, 76, 50), 'stone'),
          block((hx - .85, .2, hz - .3), (.4, .04, .04), (110, 84, 58), 'wood'), block((hx - .95, .32, hz + .25), (.03, .03, .3), (110, 84, 58), 'wood'),
          block((hx + .4, 0, hz), (.6, .006, .7), (70, 86, 110), 'stone', reflect=.55)]                                    # earth mound, roots, seeping water
    # cable from the battery's east end to the generator
    gx0, gx1 = GEN_X; gz0, gz1 = GEN_Z
    B += [block((x1 + .05, .3, zc), (.08, .5, .08), (18, 18, 20), 'fabric'), block(((x1 + .05 - .5) / 2, .02, zc), (-.5 - x1 + .05, .07, .07), (18, 18, 20), 'fabric'),
          block((-.5, .02, (zc + gz0) / 2), (.07, .07, gz0 - zc), (18, 18, 20), 'fabric'),
          block((-.5, 0, gz0 - .25), (.28, .3, .22), (60, 62, 68), 'metal'), block((-.5, .3, gz0 - .25), (.2, .04, .16), (180, 160, 40), 'metal')]
    # the generator (static parts): machine pillar, booth frame, bright back plate, plinth, header that carries the label
    cx0, cx1 = CAB_X
    B += [block(((gx0 + cx0) / 2 - .02, 0, (gz0 + gz1) / 2), (cx0 - gx0 - .04, 2.15, gz1 - gz0), (64, 76, 72), 'metal'),
          block(((gx0 + gx1) / 2, 0, (gz0 + gz1) / 2), (gx1 - gx0, .15, gz1 - gz0), (40, 44, 44), 'metal')]
    B += [block((cx0 + .04, .15, (gz0 + gz1) / 2), (.08, 2.0, gz1 - gz0), (70, 82, 78), 'metal'), block((cx1 - .04, .15, (gz0 + gz1) / 2), (.08, 2.0, gz1 - gz0), (70, 82, 78), 'metal'),
          block(((cx0 + cx1) / 2, .15, gz1 - .03), (cx1 - cx0 - .16, 2.0, .04), (170, 182, 186), 'metal', reflect=.2)]          # bright back plate (the reflection chamber)
    B += [block((cx0 + .02, .12, gz0 + .02), (.12, 2.1, .1), (52, 62, 58), 'metal'), block((cx1 - .02, .12, gz0 + .02), (.12, 2.1, .1), (52, 62, 58), 'metal'),
          block(((cx0 + cx1) / 2, 1.98, gz0 + .02), (cx1 - cx0, .17, .1), (52, 62, 58), 'metal'), block(((cx0 + cx1) / 2, .15, gz0 + .02), (cx1 - cx0, .1, .1), (52, 62, 58), 'metal')]
    for (x, y) in ((cx0 + .02, .5), (cx0 + .02, 1.0), (cx0 + .02, 1.5), (cx1 - .02, .5), (cx1 - .02, 1.0), (cx1 - .02, 1.5)):
        B.append(block((x, y, gz0 - .035), (.04, .04, .02), (120, 124, 130), 'metal'))
    B += [block(((gx0 + gx1) / 2, 2.15, (gz0 + gz1) / 2), (gx1 - gx0 + .04, .8, gz1 - gz0), (52, 60, 58), 'metal'),
          block(((gx0 + gx1) / 2, 2.95, (gz0 + gz1) / 2), (gx1 - gx0, .06, gz1 - gz0), (40, 44, 44), 'metal')]
    px = (gx0 + cx0) / 2
    B += _gauge(px - .13, 1.85, gz0 - .02, '-z', .08, .2) + _gauge(px + .13, 1.85, gz0 - .02, '-z', .08, .75)
    for i, c in enumerate(((60, 200, 90), (230, 170, 40), (200, 40, 30))):           # pilot lights on the pillar (dimmed when the tower is dead)
        B.append(block((px - .14 + i * .14, 1.55, gz0 - .015), (.06, .06, .03), c, 'plaster', group='machines.pilotes'))
    B += [block((px, .55, gz0 - .01), (.3, .3, .02), (220, 180, 30), 'plaster')]                                       # DANGER plate (text: texture box)
    # workbench against the east wall (facing west): tools, spare fuses, an oil can
    bx_ = 3.6
    B += [block((bx_, .85, 1.85), (.62, .07, 1.3), WOOD, 'wood'), block((bx_, 0, 1.25), (.56, .85, .08), WOOD_D, 'wood'), block((bx_, 0, 2.45), (.56, .85, .08), WOOD_D, 'wood'),
          block((bx_, .25, 1.85), (.56, .04, 1.2), WOOD_D, 'wood')]
    for i in range(5):
        B += [block((bx_ - .1, .92, 1.4 + i * .1), (.16, .05, .05), (24, 24, 26), 'metal'), block((bx_ - .19, .92, 1.4 + i * .1), (.02, .055, .055), COPPER, 'metal')]
    B += [block((bx_, .92, 2.2), (.12, .14, .16), (60, 62, 70), 'metal'), block((bx_ + .05, .92, 1.95), (.1, .2, .14), (60, 110, 60), 'metal'), block((bx_ + .05, 1.12, 1.95), (.03, .12, .03), (60, 110, 60), 'metal')]
    # shelves of bulbs and jars on the partition (north face), east of the passage
    sx0, sx1 = 2.85, 3.95
    B += [block(((sx0 + sx1) / 2, 0, PART_REZ[1] + .2), (sx1 - sx0, .05, .36), WOOD_D, 'wood')]
    for y in (.0, .6, 1.2, 1.8):
        B.append(block(((sx0 + sx1) / 2, y, PART_REZ[1] + .2), (sx1 - sx0, .04, .36), WOOD, 'wood'))
    for x in (sx0 + .02, sx1 - .02):
        B.append(block((x, 0, PART_REZ[1] + .2), (.04, 1.85, .36), WOOD_D, 'wood'))
    for i in range(6):
        B.append(block((sx0 + .15 + i * .16, .64, PART_REZ[1] + .2), (.1, .16 + .04 * (i % 2), .1), ((120, 140, 90), (150, 120, 70), (90, 110, 130))[i % 3], 'plaster'))
        B.append(block((sx0 + .15 + i * .16, 1.24, PART_REZ[1] + .2), (.09, .09, .09), (230, 226, 200), 'plaster'))
    # pipes with a valve and a gauge on the north wall, a drum and jerrycans, a coiled cable
    B += _pipe_v(-2.0, 4.3, 0., SLAB0) + _pipe_v(-1.65, 4.44, 0., SLAB0, .07, (120, 76, 50))
    B += _valve(-2.0, 1.2, 4.2, '-z') + _gauge(-1.65, 1.55, 4.36, '-z', .08, .5) + _valve(-1.65, .8, 4.36, '-z', (40, 90, 160))
    B += [block((-3.0, 0, 3.0), (.56, .86, .56), (60, 66, 60), 'metal'), block((-3.0, .82, 3.0), (.6, .05, .6), (44, 46, 48), 'metal'),
          block((-2.3, 0, 3.8), (.26, .44, .17), (170, 40, 36), 'metal'), block((-1.2, 0, 4.25), (.26, .44, .17), (160, 120, 40), 'metal')]
    B += _coil(-1.4, 3.6, 0., (24, 24, 26), .3, 2)
    B += _drip_stain(-1.2, 3.6, math.sqrt(R_IN ** 2 - 1.2 ** 2) - .03, '-z', 1.5) + _drip_stain(2.1, 3.7, PART_REZ[1] + .015, '+z', 1.2)
    B += [block((1.0, 0, 2.2), (.9, .006, .7), (70, 86, 110), 'stone', reflect=.5)]                                  # a puddle in the middle
    return B


def palier_blocs(spec):
    """the landing: hanging lamp over the light circle (the spot itself is a light of the class), storage (shelf, oil drums, spare lenses),
    a sign on the door, bench"""
    B = []; y = Y_ETAGE
    B += [block((-2.0, Y_PLAF - .62, -.45), (.02, .62, .02), (30, 30, 30), 'metal'), block((-2.0, Y_PLAF - .78, -.45), (.34, .1, .34), IRON, 'metal'),
          block((-2.0, Y_PLAF - .86, -.45), (.16, .08, .16), (255, 244, 220), 'light', emissive=1.8, no_shadow=True)]
    # storage on the east: free-standing shelf (faces -x), oil drums, crates, a crate of spare lenses (pale glass discs)
    sx = 3.75
    B += [block((sx, y, -1.0), (.36, .05, 1.3), WOOD_D, 'wood')]
    for yy in (0., .55, 1.1, 1.65):
        B.append(block((sx, y + yy, -1.0), (.36, .04, 1.3), WOOD, 'wood'))
    for zz in (-1.63, -.37):
        B.append(block((sx, y, zz), (.36, 1.7, .04), WOOD_D, 'wood'))
    for i in range(4):
        B.append(block((sx, y + .59, -1.45 + i * .3), (.2, .26, .14), ((170, 40, 36), (60, 90, 60), (150, 120, 50), (90, 92, 98))[i], 'metal'))
        B.append(block((sx, y + 1.14, -1.45 + i * .3), (.06, .24, .24), (190, 214, 226), 'plaster', reflect=.3))   # spare lens discs, standing
    for (x, z) in ((3.0, -2.75), (2.45, -3.3)):
        B += [block((x, y, z), (.56, .86, .56), (120, 50, 40), 'metal'), block((x, y + .78, z), (.6, .06, .6), (50, 50, 54), 'metal')]
    B += [block((3.45, y, -2.0), (.6, .5, .6), (122, 94, 62), 'wood'), block((3.45, y + .5, -2.0), (.5, .4, .5), (112, 86, 58), 'wood')]
    B += _coil(1.4, -3.8, y, (150, 128, 92), .3)
    # bench against the partition (south face), east of the door
    zb = PART_ETA[0] - .22
    B += [block((.0, y + .42, zb), (1.3, .06, .34), WOOD, 'wood'), block((-.55, y, zb), (.06, .42, .3), WOOD_D, 'wood'), block((.55, y, zb), (.06, .42, .3), WOOD_D, 'wood')]
    B += _drip_stain(-3.5, y + 3.4, PART_ETA[0] - .015, '-z', 1.4) + _drip_stain(1.4, y + 3.5, PART_ETA[0] - .015, '-z', 1.0)
    B += [block((-1.0, y, -1.5), (.7, .006, .55), (70, 86, 110), 'stone', reflect=.5)]                                  # wet patch
    B += _pipe_v(4.6, -1.2, y, Y_PLAF, .08)
    lx, lz = pol(R_IN - .2, 172.); B += _caged_lamp(lx, y + 3.15, lz, wall='-z')
    return B


def commandes_blocs(spec):
    """the control room: console (desk, riser, gauges, indicator lights ; lever, fuse and glass plate are dynamic or texture boxes of the class),
    register, desk lamp, radio, oil lamp, coat rack, filing cabinet, poster, pipes"""
    B = []; y = Y_ETAGE
    x0, z0, x1, z1 = CONSOLE
    B += [block(((x0 + x1) / 2, y, (z0 + z1) / 2), (x1 - x0, .82, z1 - z0), (70, 74, 70), 'metal'),
          block(((x0 + x1) / 2, y + .82, (z0 + z1) / 2 - .05), (x1 - x0 + .06, .1, z1 - z0 + .1), (54, 58, 56), 'metal'),
          block(((x0 + x1) / 2, y + .92, 4.32), (x1 - x0, .08, .22), (60, 64, 62), 'metal')]
    # riser (back panel) with an opening for the glass plate (x -.32 .. .32, y 1.12 .. 1.74 above the floor)
    zr = 4.3
    B += [block((-.89 + 0., y + 1.0, zr), (1.12, 1.05, .14), (66, 70, 68), 'metal'), block((.89, y + 1.0, zr), (1.12, 1.05, .14), (66, 70, 68), 'metal'),
          block((0, y + 1.0, zr), (.66, .12, .14), (66, 70, 68), 'metal'), block((0, y + 1.74, zr), (.66, .31, .14), (66, 70, 68), 'metal'),
          block((0, y + 2.05, zr - .02), (x1 - x0 + .04, .08, .2), (50, 54, 52), 'metal')]
    # the white light behind the plate (niche) and its brass frame
    B += [block((0, y + 1.1, zr + .12), (.62, .66, .06), (240, 244, 250), 'light', emissive=1.25, no_shadow=True, group='plaque.lumiere'),
          block((-.34, y + 1.08, zr - .09), (.06, .7, .04), BRASS, 'metal'), block((.34, y + 1.08, zr - .09), (.06, .7, .04), BRASS, 'metal'),
          block((0, y + 1.08, zr - .09), (.74, .05, .04), BRASS, 'metal'), block((0, y + 1.74, zr - .09), (.74, .05, .04), BRASS, 'metal')]
    for (x, yy) in ((-.34, 1.12), (-.34, 1.7), (.34, 1.12), (.34, 1.7)):
        B.append(block((x, y + yy, zr - .115), (.03, .03, .01), (210, 200, 160), 'metal'))
    # gauges across the top of the riser, toggles and indicator lights on the desk (glow dynamic: group commandes.voyants)
    for i, xx in enumerate((-1.3, -.55, .55, 1.3)):
        B += _gauge(xx, y + 1.9, zr - .09, '-z', .09, (.2, .5, .7, .35)[i])
    for i in range(8):
        xx = -1.2 + i * .34
        if abs(xx) < .4: continue
        B.append(block((xx, y + .9, z0 + .14), (.05, .03, .05), ((60, 200, 90), (230, 170, 40), (60, 200, 90), (200, 40, 30))[i % 4], 'plaster', group='commandes.voyants'))
        B.append(block((xx + .12, y + .9, z0 + .14), (.03, .06, .03), (190, 190, 196), 'metal'))
    # lever housing (left) and fuse panel (right): the lever arm and the fuse cartridge are dynamic
    B += [block((-.95, y + .92, 4.02), (.24, .2, .26), (40, 42, 44), 'metal'), block((-.95, y + 1.12, 4.02), (.12, .04, .12), (30, 30, 32), 'metal')]
    B += [block((.95, y + 1.05, zr - .1), (.4, .42, .06), (22, 22, 24), 'metal')]
    for dx in (-.11, .11):
        B.append(block((.95 + dx, y + 1.2, zr - .14), (.05, .1, .04), COPPER, 'metal'))
    # register (od_book is a prop of the room, see props) ; filing cabinet, coat rack, poster frame, oil lamp table, pipes
    B += [block((-3.4, y, 2.5), (.5, 1.25, .55), (84, 88, 84), 'metal')]
    for yy in (.3, .65, 1.0):
        B += [block((-3.4, y + yy, 2.22), (.44, .3, .01), (96, 100, 96), 'metal'), block((-3.4, y + yy + .2, 2.215), (.12, .03, .01), (190, 190, 196), 'metal')]
    cx, cz = -3.6, 1.3
    B += [block((cx, y, cz), (.36, .05, .36), WOOD_D, 'wood'), block((cx, y, cz), (.06, 1.8, .06), WOOD_D, 'wood'), block((cx, y + 1.62, cz), (.5, .04, .04), WOOD_D, 'wood'),
          block((cx + .1, y + .75, cz + .1), (.36, .9, .14), (150, 120, 40), 'fabric', reflect=.1)]                       # the keeper's yellow oilskin
    B += [block((3.55, y, 2.5), (.6, .72, .5), WOOD, 'wood'), block((3.55, y + .72, 2.5), (.66, .05, .56), WOOD_D, 'wood')]
    B += _pipe_v(-4.2, 1.3, y, Y_PLAF, .08) + _pipe_v(4.05, 2.45, y, Y_PLAF, .07, (120, 76, 50))
    B.append(block((0., Y_PLAF - .3, 1.05), (8.4, .1, .1), (70, 74, 80), 'metal'))
    B += _drip_stain(-2.25, y + 2.5, 4.15, '-z', 1.2) + _drip_stain(2.3, y + 2.5, 4.15, '-z', 1.0) + _drip_stain(-.7, y + 3.4, PART_ETA[1] + .015, '+z', 1.5)
    B += [block((.0, Y_PLAF - .45, 2.3), (.02, .45, .02), (30, 30, 30), 'metal')] + _caged_lamp(0., Y_PLAF - .7, 2.3)
    return B


def dehors_blocs(spec):
    """what the door and the windows show: pines on several ranks, rocks, ferns (no tree within 9 m of the tower)"""
    if not spec.get('dehors', True): return []
    from . import phare_foret as PF
    rng = np.random.default_rng(int(spec.get('seed', 7)) * 31 + 5); B = []; placed = []
    for k in range(140):
        if len(placed) >= 46: break
        r = float(rng.uniform(9., 38.)); a = float(rng.uniform(0, 360)); x, z = pol(r, a); h = float(rng.uniform(8., 14.))
        rad = PF.pine_radius(h, r > 22)
        if any((x - px) ** 2 + (z - pz) ** 2 < (rad + pr) ** 2 for px, pz, pr in placed): continue
        placed.append((x, z, rad)); B += PF._pine(round(x, 2), round(z, 2), round(h, 2), k, far=r > 22)
    for k in range(10):
        x, z = pol(float(rng.uniform(6.2, 9.)), float(rng.uniform(0, 360)))
        B.append(block((x, 0, z), (.5 + .3 * (k % 2), .3, .45), (96, 94, 88), 'stone'))
    x, z = 0., -6.2
    B += [block((x, 0, z), (1.6, .02, 1.0), (70, 56, 42), 'stone')]                                                  # trodden earth in front of the door
    return B


# ------------------------------------------------------------------ texts (texture boxes built by the class)
GRAVURE = ['CE QUE LE', 'FAISCEAU PREND', 'ATTEND DE', "L'AUTRE CÔTÉ"]
ETIQUETTE = ['MODE REFLET :', 'MATÉRIALISE CE', 'QUE LE VISITEUR', 'DÉSIRE REVOIR.', 'NE CONSTITUE', 'PAS UNE', 'EXTRACTION.']
BATTERIE = ['SEPTIÈME', 'ÉCLAIR', 'AUTOMATIQUE']


def _font(size=8):
    from PIL import ImageFont
    from ...paths import FONT_PIXEL
    return ImageFont.truetype(FONT_PIXEL, size)


@functools.lru_cache(maxsize=8)
def gravure_tex(lines, traits=7, barres=3, W=128, H=116):
    """the engraved wall: seven strokes (the first `barres` crossed out) and the sentence, pale engraving on dark stone with a shadow"""
    from PIL import Image, ImageDraw
    rng = np.random.default_rng(11)
    base = np.zeros((H, W, 4), np.uint8); base[..., 3] = 255
    n = rng.random((H, W)) * 14 - 7
    base[..., 0] = np.clip(84 + n, 0, 255); base[..., 1] = np.clip(80 + n, 0, 255); base[..., 2] = np.clip(74 + n, 0, 255)
    im = Image.fromarray(base, 'RGBA'); d = ImageDraw.Draw(im); d.fontmode = '1'; f = _font(8)
    eng = (226, 218, 200, 255); sh = (34, 30, 28, 255)
    x0 = (W - (traits * 12 - 6)) // 2
    for i in range(traits):
        x = x0 + i * 12
        d.rectangle([x + 1, 8, x + 4, 37], fill=sh); d.rectangle([x, 7, x + 3, 36], fill=eng)
        if i < barres:
            for k in range(3):
                d.line([(x - 4, 31 - k + 1), (x + 8, 12 - k + 1)], fill=sh, width=1); d.line([(x - 4, 31 - k), (x + 8, 12 - k)], fill=eng, width=1)
    y = 47
    for l in lines:
        tw = d.textlength(l, font=f); xx = (W - tw) / 2
        d.text((xx + 1, y + 1), l, font=f, fill=sh); d.text((xx, y), l, font=f, fill=eng)
        y += 16
    a = np.array(im); return a


@functools.lru_cache(maxsize=16)
def plate_tex(lines, fg=(244, 238, 222), bg=(30, 32, 40), border=(170, 40, 36), W=None, lh=10, pad=5, bold=True):
    """a readable plate: CLEAR bold text on a dark background (the PS1 palette eats dark text on light), coloured border"""
    from PIL import Image, ImageDraw
    f = _font(8); lines = list(lines)
    W = W or max(16, max(8 * len(l) for l in lines) + 2 * pad + 2); H = len(lines) * lh + 2 * pad
    im = Image.new('RGBA', (W, H), tuple(bg) + (255,)); d = ImageDraw.Draw(im); d.fontmode = '1'
    if border: d.rectangle([0, 0, W - 1, H - 1], outline=tuple(border) + (255,), width=2)
    y = pad + 1
    for l in lines:
        tw = d.textlength(l, font=f); x = (W - tw) / 2
        d.text((x, y), l, font=f, fill=tuple(fg) + (255,))
        if bold: d.text((x + 1, y), l, font=f, fill=tuple(fg) + (255,))
        y += lh
    return np.array(im)


@functools.lru_cache(maxsize=8)
def display_tex(lines, on=True):
    """the battery's LED display: red bold text on black, dot-matrix rows (off: dim red ghost)"""
    from PIL import Image, ImageDraw
    f = _font(8); lines = list(lines); W = max(8 * len(l) for l in lines) + 12; H = len(lines) * 11 + 8
    im = Image.new('RGBA', (W, H), (10, 6, 6, 255)); d = ImageDraw.Draw(im); d.fontmode = '1'
    col = (255, 64, 44, 255) if on else (64, 20, 16, 255)
    y = 4
    for l in lines:
        tw = d.textlength(l, font=f); x = (W - tw) / 2
        d.text((x, y), l, font=f, fill=col); d.text((x + 1, y), l, font=f, fill=col); y += 11
    a = np.array(im); a[1::2, :, :3] = (a[1::2, :, :3] * .78).astype(np.uint8)
    return a


@functools.lru_cache(maxsize=4)
def dial_tex(S=40, rim=(60, 50, 40), face=(232, 224, 200), ink=(30, 28, 26)):
    """an old clock dial WITHOUT hands (the hands are boxes that tremble), roman-like strokes"""
    from PIL import Image, ImageDraw
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse([0, 0, S - 1, S - 1], fill=rim + (255,)); d.ellipse([3, 3, S - 4, S - 4], fill=face + (255,))
    c = (S - 1) / 2.
    for k in range(12):
        a = k * math.pi / 6; r0, r1 = (S / 2 - 8, S / 2 - 5) if k % 3 else (S / 2 - 11, S / 2 - 5)
        d.line([(c + math.sin(a) * r0, c - math.cos(a) * r0), (c + math.sin(a) * r1, c - math.cos(a) * r1)], fill=ink + (255,), width=1 if k % 3 else 2)
    for k in range(60):
        a = k * math.pi / 30; r = S / 2 - 4.5
        im.putpixel((int(round(c + math.sin(a) * r)), int(round(c - math.cos(a) * r))), ink + (255,))
    return np.array(im)


# ------------------------------------------------------------------ lights of the place (categories driven by `phare`)
def light_defs(spec):
    """[dict(p, col, pw, r, cat, zone, spot, flick)] ; cat: principal (electric), secours (emergency), led, plaque, cabine, flamme, lanterne, grille"""
    L = []
    def add(p, col, pw, r, cat, zone, spot=None, flick=None, zw=None):
        L.append(dict(p=tuple(float(v) for v in p), col=tuple(col), pw=float(pw), r=float(r), cat=cat, zone=zone, spot=spot, flick=flick, zw=zw))
    W_ = (1.0, .9, .74); C_ = (.86, .92, 1.0)
    add((0., 2.45, -R_IN + .45), C_, 1.25, 4.2, 'principal', 1)                              # caged lamp over the door
    add((.6, 3.0, -1.7), (1.0, .86, .66), 1.5, 4.6, 'principal', 1)                         # bulb in the middle of the entrance
    add((-1.5, 2.6, -3.2), W_, .6, 3.0, 'principal', 1)                                      # stair foot
    add((3.0, 2.5, -2.4), W_, .55, 3.0, 'principal', 1)
    add((0.5, 3.6, 2.0), (.8, 1.0, .9), 1.5, 4.8, 'principal', 2)                            # fluorescent tube of the machine room
    add((1.5, 2.6, 3.1), W_, .7, 3.0, 'principal', 2)
    add((3.2, 2.4, 1.9), W_, .55, 2.6, 'principal', 2)
    add((-2.0, Y_PLAF - 1.0, -.45), (1.0, .93, .8), 3.4, 5.5, 'principal', 3, spot=((0., -1., 0.), math.cos(math.radians(14)), math.cos(math.radians(24))))   # the light circle
    add((-2.0, Y_PLAF - 1.0, -.45), (1.0, .9, .76), .45, 3.4, 'principal', 3)                 # its spill
    add((2.6, Y_ETAGE + 2.5, -1.6), W_, .5, 3.0, 'principal', 3)
    lx, lz = pol(R_IN - .55, 172.); add((lx, Y_ETAGE + 3.0, lz), (.86, .92, 1.0), 1.1, 4.2, 'principal', 3)        # caged lamp over the upper flight
    add((0., Y_PLAF - .9, 2.3), (1.0, .9, .74), 1.5, 4.8, 'principal', 4)                    # caged lamp of the control room
    add((1.25, Y_ETAGE + 1.25, 3.85), (1.0, .86, .6), .55, 2.2, 'principal', 4)              # desk lamp
    add((-1.6, Y_ETAGE + 1.2, 3.0), (.5, 1.0, .6), .2, 1.8, 'principal', 4)                  # indicator lights glow
    # emergency (on in every state but `allume`, where they are dim)
    add((2.0, 2.3, .4), (.5, 1.0, .62), .55, 3.2, 'secours', 1)                               # green exit light over the passage (entrance side)
    add((2.0, 2.3, 1.0), (.5, 1.0, .62), .5, 3.0, 'secours', 2)                               # ... and on the machine side
    add((-1.0, 3.2, -4.2), (1.0, .62, .3), .55, 3.4, 'secours', 1)                            # amber emergency lamp
    add((-2.0, Y_ETAGE + 2.4, .2), (.5, 1.0, .62), .55, 3.2, 'secours', 3)                    # over the commandes door (palier)
    add((-2.0, Y_ETAGE + 2.4, 1.1), (.5, 1.0, .62), .45, 3.0, 'secours', 4)
    add((3.0, Y_ETAGE + 3.2, 2.0), (1.0, .62, .3), .55, 3.6, 'secours', 4)
    add((-2.4, 3.2, 2.2), (1.0, .62, .3), .55, 3.6, 'secours', 2)                             # amber emergency lamps: over the battery, by the generator
    add((1.5, 3.2, 2.9), (1.0, .62, .3), .5, 3.4, 'secours', 2)
    hx, hz = pol(R_IN - .25, TROU_TH); add((hx, .35, hz), (.6, .7, 1.0), .85, 1.8, 'lune', 2)   # cold night light coming in by the cable hole
    hx, hz = pol(R_IN + .9, TROU_TH); add((hx, .7, hz), (.62, .72, 1.0), 1.6, 1.8, 'lune', 0, zw=(1., 0., 0., 0., 0.))    # ... the moon on the wet earth outside
    # the battery's red display and LED, its glow through the grate (from below, seen from the control room)
    add((-1.95, .62, 1.95), (1.0, .14, .08), 1.25, 3.4, 'led', 2)
    add((-1.95, 1.3, 1.15), (1.0, .16, .1), 1.1, 1.6, 'led', 2)                                 # the red glow on the battery's lid (seen through the grate)
    add((-1.95, Y_ETAGE + .25, 1.25), (1.0, .16, .1), .55, 1.6, 'grille', 4)
    # Noé's hand in the white light (the plate) ; the booth of the generator ; the lantern above the shaft
    add((0., Y_ETAGE + 1.42, 3.95), (.92, .95, 1.0), .75, 2.0, 'plaque', 4)
    add((.28, 1.7, 3.95), (.84, .92, 1.0), 1.8, 4.5, 'cabine', 2)
    add((.28, 1.2, 3.0), (.84, .92, 1.0), 1.2, 3.5, 'cabine', 2)
    x, z = pol(4.0, 170.); add((x, 10.2, z), (1.0, .98, .92), 1.4, 4.0, 'lanterne', 3)
    return L


# ------------------------------------------------------------------ the place
def phare_interieur(spec):
    from .places import _base
    from . import phare_foret as PF
    spec = spec or {}
    zones = [{'circle': [0., 0., R_OUT + .1], 'ground': 'concrete'}, {'circle': [0., -6.2, 1.4], 'ground': 'dirt'}]
    o = _base(dict(spec), outdoor=True, sky='night', stars=True, ground='moss', backdrop=['hills', {'type': 'forest', 'height': 4.2}, 'forest'],
              fog=.012, ambience='night', fill=.5, clouds=.42, zones=zones, wet=True)
    o['sky'] = 'night'; o['stars'] = True; o['wet'] = True
    o['ambient'] = tuple(spec.get('ambient', (.2, .21, .27)))
    o['fog_color'] = tuple(spec.get('fog_color', (.1, .12, .18)))
    if 'fill' not in spec: o['fill'] = .5
    B = tower_walls() + slabs() + partitions() + stairs()
    for (name, th, hw, y0, y1, zn) in WINDOWS: B += _window_dress(name, th, hw, y0, y1)
    B += entree_blocs(spec) + machines_blocs(spec) + palier_blocs(spec) + commandes_blocs(spec) + dehors_blocs(spec)
    mp = spec.get('main_plaque', True)
    if mp:
        m = dict(x=0., y=Y_ETAGE + 1.42, z=4.205, cote='gauche', face='-z', cicatrice=True)
        if isinstance(mp, dict): m.update(mp)
        B += PF.main_plaquee_blocs(m.pop('x'), m.pop('y'), m.pop('z'), group='main_plaque', **m)
    o['blocks'] = list(spec.get('blocks', [])) + B
    y = Y_ETAGE
    props = [
        {'type': 'od_book', 'at': [-1.15, 3.98], 'y': y + .92, 'rot': 2, 'ouvert': True, 'titre': 'REGISTRE',
         'texte': list(spec.get('registre') or ['RELEVÉ', 'ÉCLAIR 1', 'ÉCLAIR 2', 'ÉCLAIR 3', 'ÉCLAIR 4 ?'])},
        {'type': 'od_desk_lamp', 'at': [1.25, 3.95], 'y': y + .92, 'rot': 2},
        {'type': 'od_radio', 'at': [3.55, 2.62], 'y': y + .77, 'rot': 1, 'allumee': False},
        {'type': 'od_mug', 'at': [-.75, 3.9], 'y': y + .92, 'rot': 0},
        {'type': 'od_keys', 'at': [3.4, 2.32], 'y': y + .77, 'rot': 0},
        {'type': 'qi_stool', 'at': [-2.0, 3.3], 'y': y, 'rot': 0},
        {'type': 'cobweb', 'at': [-4.0, 1.0], 'y': y + 1.0, 'rot': 3}, {'type': 'cobweb', 'at': [3.8, 1.0], 'y': y + 1.0, 'rot': 1},
        {'type': 'cobweb', 'at': [-3.6, -2.9], 'y': 1.0, 'rot': 3}, {'type': 'cobweb', 'at': [3.0, 3.6], 'y': .9, 'rot': 0},
        {'type': 'od_flashlight', 'at': [3.5, 2.05], 'y': .92, 'rot': 1}, {'type': 'od_crowbar', 'at': [3.55, 1.6], 'y': .92, 'rot': 1},
        {'type': 'jerrycan', 'at': [3.7, -.95], 'rot': 1}, {'type': 'bucket', 'at': [2.6, -1.1], 'rot': 0},
        {'type': 'exit_sign', 'at': [2.0, PART_REZ[0] - .01], 'y': PASS_H - 2.02, 'rot': 0}, {'type': 'exit_sign', 'at': [-2.0, PART_ETA[0] - .01], 'y': y + PASS_H - 2.02, 'rot': 0},
    ]
    if spec.get('lampe_huile', True):
        props.append({'type': 'od_candle', 'at': [3.5, 2.45], 'y': y + .77, 'rot': 0})
    o['props'] = o['props'] + [dict(p, objets=False) for p in props]
    o['_pi'] = dict(lights=light_defs(spec), phare=str(spec.get('phare', 'allume')), porte=1. if spec.get('porte') in ('ouverte', 'open', 1, True) else 0.,
                    porte_commandes=0. if spec.get('porte_commandes') in ('fermee', 'closed', 0, False) else 1.,
                    batterie=tuple(spec.get('batterie_texte') or BATTERIE), etiquette=tuple(spec.get('etiquette') or ETIQUETTE),
                    gravure=tuple(spec.get('gravure') or GRAVURE), traits=int(spec.get('traits', 7)), barres=int(spec.get('barres', 3)),
                    heure=str(spec.get('heure', '11:52')))
    a = {'start': (0., -3.4), 'entree': (-1.2, -2.0), 'porte': (0., -R_IN), 'entree.porte': (0., -4.05), 'escalier.pied': (-.3, -4.1),
         'horloge': (-.6, 2.35, PART_REZ[0]), 'machines': (.9, 1.9), 'batterie': ((BATTERY[0] + BATTERY[2]) / 2, (BATTERY[1] + BATTERY[3]) / 2),
         'batterie.ecran': (-1.95, .53, BATTERY[3] + .05), 'machines.batterie': (-1.95, 2.15), 'generateur': ((GEN_X[0] + GEN_X[1]) / 2, (GEN_Z[0] + GEN_Z[1]) / 2),
         'machines.generateur': (.28, 2.85), 'cabine': (.28, .15, 3.95), 'machines.cabine': (.28, .15, 3.95), 'vitre': (.28, 1.1, GEN_Z[0] + .02),
         'interrupteur': ((GEN_X[0] + CAB_X[0]) / 2, 1.25, GEN_Z[0] - .08), 'etiquette': (0., 2.56, GEN_Z[0] - .03), 'bobines': (0., 3.3, 3.95),
         'trou': pol(R_IN, TROU_TH), 'machines.trou': (-3.85, 2.0),
         'palier': (-2.0, Y_ETAGE, -.45), 'palier.porte': (-2.0, Y_ETAGE, .3), 'palier.arrivee': (-3.98, Y_ETAGE, .3), 'haut.pied': (-2.95, Y_ETAGE, -3.05),
         'escalier.haut': marche('montee', NRISE), 'haut.sommet': marche('haut', NRISE - 1),
         'commandes': (.4, Y_ETAGE, 2.0), 'commandes.console': (0., Y_ETAGE, 3.3), 'commandes.porte': (-2.0, Y_ETAGE, 1.25), 'commandes.mur': (1.2, Y_ETAGE, 1.6),
         'levier': (-.95, Y_ETAGE + 1.2, 4.02), 'fusible': (.95, Y_ETAGE + 1.25, 4.16), 'plaque': (0., Y_ETAGE + 1.42, 4.205),
         'mur_grave': (1.2, Y_ETAGE + 1.7, PART_ETA[1]), 'commandes.horloge': (3.0, Y_ETAGE + 2.2, PART_ETA[1]), 'grille': ((GRILLE[0] + GRILLE[2]) / 2, Y_ETAGE, (GRILLE[1] + GRILLE[3]) / 2)}
    for (name, th, hw, y0, y1, zn) in WINDOWS:
        x, z = pol(R_IN - .3, th); a[name] = (round(x, 3), round((y0 + y1) / 2, 3), round(z, 3))
    o['anchors'] = dict(o.get('anchors') or {}, **a)
    return o


def register(PLACES):
    """adds the place `phare_interieur` ; nothing is replaced"""
    if 'phare_interieur' not in PLACES: PLACES['phare_interieur'] = phare_interieur


# ------------------------------------------------------------------ dynamic parts (state)
def _num(state, key, u, default):
    from .frame import val
    v = state.get(key, default)
    if isinstance(v, bool): return 1. if v else 0.
    if isinstance(v, str):
        return {'ouverte': 1., 'open': 1., 'fermee': 0., 'closed': 0., 'haut': 0., 'bas': 1., 'on': 1., 'off': 0.}.get(v, default if isinstance(default, float) else 0.)
    try: return float(val(v, u, default))
    except Exception: return float(default)


MODE_DEFAULTS = {
    'allume':     dict(fusible=1., interrupteur=0., bobines='froides', voyant=0, cabine=0., balayage=1., ambient=(.15, .155, .19)),
    'panne':      dict(fusible=0., interrupteur=0., bobines='froides', voyant='clignote', cabine=0., balayage=0., ambient=(.22, .24, .36)),
    'generateur': dict(fusible=0., interrupteur=1., bobines='rouges', voyant='clignote', cabine=1., balayage=0., ambient=(.22, .24, .32)),
    'brule':      dict(fusible=0., interrupteur=1., bobines='brulees', voyant=0, cabine=0., balayage=0., ambient=(.2, .22, .33)),
}


def resolve(spec_pi, state, t, u, T=None):
    """the state of this frame: mode, door angles, lever, fuse, switch, coils, LED, booth light, frost, clock tremble, flash amount"""
    from . import frame as F
    st = state or {}
    mode = str(st.get('phare', spec_pi.get('phare', 'allume')))
    if mode not in MODE_DEFAULTS: mode = 'allume'
    d = MODE_DEFAULTS[mode]
    T = F.CUR_T[0] if T is None else T
    out = dict(mode=mode)
    out['porte'] = max(0., min(1., _num(st, 'porte', u, spec_pi.get('porte', 0.))))
    out['porte_commandes'] = max(0., min(1., _num(st, 'porte_commandes', u, spec_pi.get('porte_commandes', 1.))))
    out['levier'] = max(0., min(1., _num(st, 'levier', u, 0.)))
    out['fusible'] = max(0., min(1., _num(st, 'fusible', u, d['fusible'])))
    out['interrupteur'] = max(0., min(1., _num(st, 'interrupteur', u, d['interrupteur'])))
    out['bobines'] = str(st.get('bobines', d['bobines']))
    vo = st.get('voyant', d['voyant'])
    out['voyant'] = (1. if (t % 1.0) < .62 else .0) if vo == 'clignote' else max(0., min(1., _num({'v': vo}, 'v', u, 0.)))
    out['cabine'] = max(0., _num(st, 'cabine', u, d['cabine']))
    out['vitre'] = max(0., min(1., _num(st, 'vitre', u, .8)))
    out['horloge'] = max(0., _num(st, 'horloge', u, 0.))
    out['lune'] = max(0., _num(st, 'lune', u, 1.))
    out['balayage'] = max(0., _num(st, 'balayage', u, d['balayage']))
    out['periode'] = max(1., _num(st, 'balayage_periode', u, 8.))
    fl = max(0., _num(st, 'eclair', u, 0.))
    for te in (st.get('eclairs') or []):
        dt = T - float(te)
        if 0 <= dt < 1.2: fl = max(fl, 1.6 * (math.exp(-dt * 9) + .7 * math.exp(-max(0., dt - .22) * 12) * (dt > .22)))
    out['eclair'] = fl; out['eclair_source'] = str(st.get('eclair_source', 'fenetres'))
    out['ambient'] = d['ambient']
    return out


def _rot_axis(axis, a):
    from ...acting import rig
    return {'x': rig.rot_x, 'y': rig.rot_y, 'z': rig.rot_z}[axis](a)


def door_boxes(open_k):
    """the entrance door leaf (riveted, interior face), hinged on the east post, opening inwards (towards +z) up to 100°"""
    from .r3d import B, C, orient, M_METAL
    w, h, th = DOOR_W - .04, DOOR_H - .06, .07
    loc = [B((-w, 0., -th / 2), (w, h, th), (54, 58, 64), mat=M_METAL)]
    for yy in (.45, 1.15, 1.85):
        loc.append(B((-w + .04, yy, th / 2), (w - .08, .07, .03), (44, 46, 52), mat=M_METAL))
    for yy in (.2, .8, 1.5, 2.1):
        for xx in (-.1, -.4, -.7, -1.0):
            loc.append(C((xx, yy, th / 2 + .02), (.035, .035, .02), (110, 114, 122), mat=M_METAL))
    loc += [C((-w + .14, 1.1, th / 2 + .08), (.05, .3, .05), (150, 140, 116), mat=M_METAL), C((-w + .14, 1.1, th / 2 + .04), (.04, .04, .06), (150, 140, 116), mat=M_METAL),
            C((-w / 2, 1.62, th / 2 + .006), (.16, .04, .01), (16, 16, 18))]
    yaw = math.radians(100.) * float(open_k)                       # + : the free edge (local -x) swings towards +z, into the room
    return orient(loc, yaw, (DOOR_W / 2 - .02, 0., -R_IN + .06))


def cdoor_boxes(open_k):
    """the control room door (palier side), hinged at x -1.4, opening into the room (+z) up to 95° ; barred spy window"""
    from .r3d import B, C, orient, M_METAL
    w = DOOR_ETA[1] - DOOR_ETA[0] - .04; h = PASS_H - .06; th = .06
    loc = [B((-w, 0., -th / 2), (w, .95, th), (78, 70, 60), mat=M_METAL), B((-w, 1.35, -th / 2), (w, h - 1.35, th), (78, 70, 60), mat=M_METAL),
           B((-w, .95, -th / 2), (.3, .4, th), (78, 70, 60), mat=M_METAL), B((-.3, .95, -th / 2), (.3, .4, th), (78, 70, 60), mat=M_METAL)]
    for xx in (-.75, -.6, -.45):
        loc.append(B((xx, .95, -.01), (.025, .4, .02), (36, 36, 40), mat=M_METAL))
    loc += [C((-w + .12, 1.05, -th / 2 - .05), (.04, .04, .1), (160, 150, 120), mat=M_METAL), C((-w + .12, 1.05, th / 2 + .05), (.04, .04, .1), (160, 150, 120), mat=M_METAL)]
    for yy in (.2, h - .2):
        loc.append(B((-w + .02, yy, -th / 2 - .01), (w - .04, .05, .01), (60, 54, 46), mat=M_METAL))
    yaw = math.radians(95.) * float(open_k)
    return orient(loc, yaw, (DOOR_ETA[1] - .02, Y_ETAGE, (PART_ETA[0] + PART_ETA[1]) / 2))


def lever_boxes(k):
    """the red lever ÉCHANGE: arm on a pivot over its housing ; 0 = up (towards the wall), 1 = pulled down towards the operator"""
    from .r3d import C, orient, M_METAL
    loc = [C((0., .2, 0.), (.05, .42, .05), (160, 162, 168), mat=M_METAL), C((0., .44, 0.), (.1, .1, .1), (210, 30, 30)), C((0., .02, 0.), (.08, .08, .08), (40, 40, 44), mat=M_METAL)]
    a = math.radians(14. - 104. * float(k))                       # rot_x: + tips the top towards +z (the wall)
    return orient(loc, 0., (-.95, Y_ETAGE + 1.16, 4.02), R=_rot_axis('x', a))


def fuse_boxes(k):
    """the black fuse ARRÊT in its copper clips ; k = 1 seated, 0 < k < 1 being pulled out, 0 = gone (burn marks)"""
    from .r3d import C, M_METAL
    zr = 4.3 - .17
    if k <= 1e-3:
        return [C((.95, Y_ETAGE + 1.25, zr + .005), (.2, .06, .005), (10, 10, 10)), C((.88, Y_ETAGE + 1.3, zr + .004), (.05, .04, .004), (14, 12, 12))]
    dz = -(1. - float(k)) * .28
    return [C((.95, Y_ETAGE + 1.25, zr + dz), (.26, .085, .085), (20, 20, 22), mat=M_METAL), C((.83, Y_ETAGE + 1.25, zr + dz), (.03, .09, .09), COPPER, mat=M_METAL),
            C((1.07, Y_ETAGE + 1.25, zr + dz), (.03, .09, .09), COPPER, mat=M_METAL), C((.95, Y_ETAGE + 1.25, zr + dz - .044), (.12, .04, .004), (236, 232, 220))]


def switch_boxes(k):
    """the generator's knife switch (on the pillar, facing +z): 0 = up (off), 1 = pulled down (on)"""
    from .r3d import C, orient, M_METAL
    z = GEN_Z[0]; px = (GEN_X[0] + CAB_X[0]) / 2
    base = [C((px, 1.25, z - .02), (.26, .42, .04), (30, 30, 32)), C((px, 1.12, z - .05), (.1, .06, .04), COPPER, mat=M_METAL), C((px, 1.4, z - .05), (.1, .06, .04), COPPER, mat=M_METAL)]
    arm = [C((-.06, .12, .0), (.025, .26, .02), COPPER, mat=M_METAL), C((.06, .12, .0), (.025, .26, .02), COPPER, mat=M_METAL), C((0., .26, .0), (.16, .04, .04), (30, 30, 32)),
           C((0., .26, -.06), (.05, .05, .12), (190, 30, 30))]
    a = -math.radians(20. + 140. * float(k))                       # rot_x - : the top leans towards -z (the operator, facing the generator)
    return base + orient(arm, 0., (px, 1.16, z - .08), R=_rot_axis('x', a))


def coil_boxes(mode, t):
    """the two copper coils on top of the generator: froides | rouges (glowing) | etincelles (sparks) | brulees (charred, smoke)"""
    from .r3d import C, M_METAL
    out = []; yb = 3.01
    hot = mode in ('rouges', 'etincelles'); burnt = mode == 'brulees'
    for i, x in enumerate((-.42, .38)):
        z = 3.95
        out += [C((x, yb + .05, z), (.34, .1, .34), (200, 196, 180)), C((x, yb + .1 + .25, z), (.1, .5, .1), (60, 60, 64), mat=M_METAL)]
        for j in range(4):
            yy = yb + .14 + j * .1
            if burnt: col = (34, 28, 26) if (j + i) % 2 else (46, 36, 30); em = 0.
            elif hot: col = (230, 96 - 10 * j, 40) if j % 2 == 0 else (150, 52, 24); em = (.24 + .08 * math.sin(t * 7 + j + i * 2)) * (1. if j % 2 == 0 else .4)
            else: col = COPPER if j % 2 == 0 else (160, 92, 50); em = 0.
            out += [C((x, yy + .045, z), (.4, .09, .2), col, emis=em, mat=0 if em else M_METAL), C((x, yy + .045, z), (.2, .09, .4), col, emis=em, mat=0 if em else M_METAL)]
        out.append(C((x, yb + .62, z), (.1, .1, .1), (150, 152, 160) if not burnt else (40, 36, 34), mat=M_METAL))
        if burnt:
            for j in range(3):                                         # charred flakes and a thin smoke rising
                ph = (t * .35 + j * .33 + i * .17) % 1.
                out.append(C((x + .05 * math.sin(j + t), yb + .9 + ph * .8, z + .04 * math.cos(j * 2 + t)), (.16 + .1 * ph, .12, .16 + .1 * ph), (70, 70, 72), dissolve=.55 + .4 * ph, cast=False))
            out.append(C((x + .12, yb + .3, z - .15), (.03, .03, .03), (255, 90, 30), emis=1.5 * (.5 + .5 * math.sin(t * 5 + i)), cast=False))
    if mode == 'etincelles':
        rng = np.random.default_rng(int(t * 24) + 3)
        for j in range(10):
            x = -.42 + .8 * float(rng.random()); y = yb + .2 + .7 * float(rng.random()); z = 3.95 + (float(rng.random()) - .5) * .5
            out.append(C((x, y, z), (.03, .03, .03), (220, 236, 255), emis=3., cast=False))
        x0 = -.42 + .1 * math.sin(t * 11)
        for j in range(6):                                              # an arc between the two coils
            out.append(C((x0 + j * .13, yb + .58 + .06 * math.sin(t * 30 + j * 2.1), 3.95), (.13, .025, .025), (210, 230, 255), emis=3., cast=False))
    return out


def fan_boxes(on, t):
    """the cooling fan on the battery's lid: a housing and three blades turning while the battery lives (« quelque chose continue à tourner »)"""
    from .r3d import C, orient, M_METAL
    x, y, z = (BATTERY[0] + BATTERY[2]) / 2 + .35, .85, (BATTERY[1] + BATTERY[3]) / 2
    out = [C((x, y + .02, z), (.46, .04, .2), (34, 36, 38), mat=M_METAL), C((x, y + .02, z), (.2, .04, .46), (34, 36, 38), mat=M_METAL),
           C((x, y + .07, z), (.38, .06, .38), (24, 24, 26), mat=M_METAL), C((x, y + .12, z), (.06, .04, .06), (150, 150, 156), mat=M_METAL)]
    for k in range(8):                                                 # charge LEDs chasing along the lid
        lit = on and int(t * 6) % 8 == k
        out.append(C((BATTERY[0] + .25 + k * .1, y + .015, (BATTERY[1] + BATTERY[3]) / 2 + .25), (.05, .03, .05), (255, 50, 36) if lit else (90, 26, 20), emis=2.4 if lit else (.4 if on else 0.), cast=False))
    a = (t * 1.35 * 2 * math.pi) if on else .4
    blades = [C((.0, 0., .09), (.06, .015, .16), (120, 124, 130), mat=M_METAL), C((.0, 0., -.09), (.06, .015, .16), (120, 124, 130), mat=M_METAL)]
    for k in range(3):
        out += orient([copy.copy(b_) for b_ in blades][:1], a + k * 2 * math.pi / 3, (x, y + .11, z))
    return out


def booth_glass(frost, glow):
    """the booth's front glass: frosted (screen-door dither, `vitre` 0 clear .. 1 frosted) and lit from inside (`cabine`)"""
    from .r3d import B
    if frost <= .02: return []
    z = GEN_Z[0] + .02
    b = B((CAB_X[0] + .08, .25, z), (CAB_X[1] - CAB_X[0] - .16, 1.73, .025), (150, 168, 178), emis=.06 + .3 * min(1.5, glow), dissolve=max(.05, 1. - .85 * frost), cast=False)
    return [b]


def clock_boxes(cx, cy, cz, face, hh, tremble, t, size=.42, pendulum=False):
    """an old wall clock (stepped round case, dial without hands) whose hands are oriented boxes that tremble ; face '-z' | '+z'"""
    from .r3d import C, orient, M_METAL
    from . import objets as OB
    sgn = -1 if face == '-z' else 1; dep = .06
    img = dial_tex()
    out = []
    disc = OB._disk(cx, cy, cz, size, dep, (70, 52, 40), img, n=9, glass=True)      # back at cz, front at cz - dep (face -z)
    if sgn > 0:                                                    # faces +z: back at cz, front at cz + dep ; the engine mirrors the +z texture itself
        for b in disc:
            b.lo[2] = cz; b.hi[2] = cz + dep
            b.tex = {5: v for k, v in b.tex.items()}
    out += disc
    front = cz + sgn * dep
    if pendulum:                                                    # long case below with a swinging pendulum (régulateur)
        out += [C((cx, cy - size / 2 - .45, cz + sgn * .04), (size * .8, .9, .08), (70, 52, 40)), C((cx, cy - size / 2 - .45, cz + sgn * .085), (size * .55, .7, .01), (30, 26, 22))]
        sw = math.radians(8.) * math.sin(t * math.pi)              # one beat per second
        pend = [C((0., -.28, 0.), (.015, .5, .01), BRASS, mat=M_METAL), C((0., -.56, 0.), (.1, .1, .02), BRASS, mat=M_METAL)]
        out += orient(pend, 0., (cx, cy - size / 2 - .05, cz + sgn * .095), R=_rot_axis('z', sw))
    h, m = (int(v) for v in hh.split(':'))
    jit = tremble * (math.sin(t * 41.) * 7. + math.sin(t * 67. + 1.3) * 5. + math.sin(t * 13.) * 3.)
    a_m = math.radians(m * 6. + jit); a_h = math.radians(((h % 12) + m / 60.) * 30. + jit * .6)
    for i, (a, L, w, col) in enumerate(((a_h, size * .26, .024, (20, 18, 16)), (a_m, size * .4, .016, (20, 18, 16)),
                                        (a_m + 2.4 + tremble * math.sin(t * 23.) * .3, size * .42, .008, (190, 30, 30)))):
        hand = [C((0., L / 2 - .02, 0.), (w, L, .01), col)]
        out += orient(hand, 0., (cx, cy, front + sgn * (.007 + .004 * i)), R=_rot_axis('z', sgn * a))   # seen from the front: clockwise
    out.append(C((cx, cy, front + sgn * .02), (.03, .03, .01), (20, 18, 16)))
    return out


def _tex_box(at, size, face, img, glow, bg=(20, 20, 20)):
    from .r3d import Box
    x, y, z = at; w, h, d = size
    return Box([x - w / 2, y, z - d / 2], [x + w / 2, y + h, z + d / 2], tuple(bg), tex={face: img}, texemis=glow, cast=False)


# ------------------------------------------------------------------ PIXEL 3D: the set class
def make(name, spec):
    """make_set for `phare_interieur` (sets.py): the place expanded like any ready place, built by PhareInterieurSet"""
    from . import places as PL, environment_variation as EV, qt_street as QS
    o = QS.finish(EV.dress(PL.expand('phare_interieur', spec), 'phare_interieur', spec), 'phare_interieur', spec, name)
    return set_class()(o)


_CLS = {}


def moon_dir():
    from . import phare_foret as PF
    return PF.MOON_DIR


def _zw(zone):
    """zone weights of a light (index = zone of the lit point): a light lights its own zone, a little the neighbour behind an opening, never
    through a wall or a floor (sc.zone_fn)"""
    w = [0.] * 5; w[zone] = 1.
    if zone == 1: w[2] = .2
    if zone == 2: w[1] = .2
    if zone == 3: w[4] = .15
    if zone == 4: w[3] = .15
    return tuple(w)


def sweep(S, t):
    """the beam passing behind the windows (absolute time of the film): 0..1"""
    if S['balayage'] <= 0: return 0.
    ph = (t / S['periode']) % 1.
    return S['balayage'] * math.exp(-((min(ph, 1 - ph)) / .05) ** 2)


def frame_lights(spec_pi, prop_lights, S, t, cam_pos, fill):
    """the lights of one frame: (pos, col, power, radius, shadow, spot, zone weights) ; the camera fill light stays LAST (acted.py adjusts L[-1])"""
    mode = S['mode']; L = []
    fact = {'principal': .8 if mode == 'allume' else 0., 'secours': .35 if mode == 'allume' else 1.,
            'led': S['voyant'] * (1. if mode != 'allume' else .6), 'grille': S['voyant'] * (1. if mode != 'allume' else .5),
            'plaque': 0. if mode == 'brule' else 1., 'cabine': S['cabine'], 'flamme': 1., 'lanterne': 1. if mode == 'allume' else 0., 'lune': S['lune']}
    for l in list(spec_pi.get('lights') or []) + list(prop_lights or []):
        k = fact.get(l['cat'], 1.)
        if l.get('flick') == 'soft': k *= .84 + .16 * math.sin(t * 9.3 + l['p'][0] * 3.7) * math.sin(t * 5.1 + l['p'][2] * 2.3)
        if k <= 1e-3: continue
        L.append((l['p'], l['col'], l['pw'] * k, l['r'], False, l['spot'], l['zw'] or _zw(l['zone'])))
    mk = S['lune'] * (1.0 if mode == 'allume' else 1.5); md = moon_dir(); sw = sweep(S, t); fl = S['eclair']
    for (name, th, hw, y0, y1, zn) in WINDOWS:
        x, z = pol(R_IN - .2, th)
        if name in MOON_WINDOWS and mk > 0:                                   # moonlight entering by the north-west windows
            L.append(((x - md[0] * 1.2, (y0 + y1) / 2 - md[1] * 1.2, z - md[2] * 1.2), (.6, .7, 1.0), .9 * mk, 3.6, False, None, _zw(zn)))
        pw = sw * 1.6 + (fl * 4.5 if (S['eclair_source'] != 'generateur' or zn != 2) else 0.)
        if pw > .01:                                                          # the beam passing / the white flash entering by every window
            L.append(((x * .9, (y0 + y1) / 2, z * .9), (1.0, 1.0, .96), pw, 5.0, False, None, _zw(zn)))
    if fl > .01 and S['eclair_source'] == 'generateur':                        # the 7th flash going through the machine
        L.append(((.28, 1.4, 3.2), (1.0, 1.0, .98), fl * 7., 7., False, None, _zw(2)))
    L.append(((-60., 70., 110.), (.55, .65, 1.0), 1.6 * max(.3, S['lune']) + fl * 2., 400., False, None, (1., 0., 0., 0., 0.)))   # the moon, outside only
    L.append(((cam_pos[0], cam_pos[1] + .25, cam_pos[2]), (.95, .93, .9), float(fill), 3.0))
    return L


def set_class():
    if 'c' in _CLS: return _CLS['c']
    from .sets import RoomSet, SKIES
    from .r3d import C

    class PhareInterieurSet(RoomSet):
        """the inside of the tower: a RoomSet plus its texture boxes (engraving, labels, display), its dynamic parts (doors, lever, fuse,
        switch, coils, booth glass, clock hands, drips), its light zones (no light leaks through a wall or a floor: sc.zone_fn) and its
        states (`phare`...)"""
        name = 'phare_interieur'

        def build(self):
            super().build()
            from . import phare_foret as PF
            pi = self.spec.get('_pi') or {}; sc = self.base
            sc.ceil_y = None
            self._sky0 = PF.night_sky(self.spec, SKIES['night']['sun'])
            sc.sky_fn = self._sky0
            sc.zone_fn = _zone_fn
            self._pi_props = []                                              # lights of the od_* props, classified (flame / emergency / electric)
            for (p, c, pw, r, fl) in self.light_defs:
                flame = c[1] < .7 and c[2] < .4; green = c[1] > .9 and c[0] < .5
                cat = 'flamme' if flame else 'secours' if green else 'principal'
                self._pi_props.append(dict(p=tuple(p), col=tuple(c), pw=pw * (1.3 if flame else .9), r=r * (1.3 if flame else 1.), cat=cat, zone=zone_de(p), spot=None,
                                           flick='soft' if flame else None, zw=None))
            self.light_defs = []
            y = Y_ETAGE
            def add(bx, grp=None):
                sc.add(bx)
                if grp: self.groups.setdefault(grp, []).append(len(sc.boxes) - 1)
            add(_tex_box((1.2, y + .9, PART_ETA[1] + .02), (1.3, 1.18, .04), '+z', gravure_tex(tuple(pi.get('gravure', GRAVURE)), pi.get('traits', 7), pi.get('barres', 3)), .2, (84, 80, 74)), 'mur_grave')
            add(_tex_box((-.95, y + 1.66, 4.3 - .085), (.46, .17, .01), '-z', plate_tex(('ÉCHANGE',), (250, 240, 230), (150, 22, 24), (60, 10, 10)), .45, (150, 22, 24)), 'console.etiquettes')
            add(_tex_box((.95, y + 1.5, 4.3 - .085), (.4, .17, .01), '-z', plate_tex(('ARRÊT',), (244, 240, 230), (18, 18, 20), (200, 200, 200)), .45, (18, 18, 20)), 'console.etiquettes')
            add(_tex_box((0., 2.19, GEN_Z[0] - .025), (1.24, .72, .01), '-z', plate_tex(tuple(pi.get('etiquette', ETIQUETTE)), (246, 238, 214), (26, 30, 44), (190, 150, 60)), .4, (26, 30, 44)), 'etiquette')
            add(_tex_box((2.0, PASS_H + .1, PART_REZ[0] - .06), (.9, .18, .01), '-z', plate_tex(('MACHINES',), (240, 236, 220), (40, 44, 48), (220, 180, 30)), .35, (40, 44, 48)), 'panneaux')
            add(_tex_box((-2.0, y + PASS_H + .1, PART_ETA[0] - .06), (1.1, .17, .01), '-z', plate_tex(('COMMANDES',), (240, 236, 220), (40, 44, 48), (170, 40, 36)), .35, (40, 44, 48)), 'panneaux')
            add(_tex_box((0., 2.42, -R_IN + .16), (.62, .16, .01), '+z', plate_tex(('SORTIE',), (220, 255, 226), (20, 70, 40), (20, 40, 26)), .6, (20, 70, 40)), 'panneaux')
            add(_tex_box((3.5, 1.1, PART_REZ[0] - .09), (.76, .5, .01), '-z', plate_tex(('CONSIGNES', 'NE JAMAIS', 'REGARDER LE', 'FAISCEAU'), (238, 232, 214), (44, 40, 34), (150, 120, 70)), .15, (44, 40, 34)), 'panneaux')
            add(_tex_box(((GEN_X[0] + CAB_X[0]) / 2, .6, GEN_Z[0] - .03), (.26, .2, .005), '-z', plate_tex(('DANGER',), (24, 24, 26), (220, 180, 30), None, W=52), .25, (220, 180, 30)), 'panneaux')
            add(_tex_box((-3.4, y + 1.3, PART_ETA[1] + .02), (.7, .9, .01), '+z', plate_tex(('PHARE', 'DES PINS', '', 'SERVICE', 'DE NUIT'), (236, 230, 210), (40, 52, 70), (170, 40, 36)), .15, (40, 52, 70)), 'panneaux')

        # ---------------------------------------------------- per frame
        def frame_state(self, state, t, u):
            return resolve(self.spec.get('_pi') or {}, state or {}, t, u)

        def scene(self, state, t, u):
            sc = super().scene(state, t, u)
            pi = self.spec.get('_pi') or {}
            S = self.frame_state(state, t, u); mode = S['mode']
            extra = door_boxes(S['porte']) + cdoor_boxes(S['porte_commandes']) + lever_boxes(S['levier']) + fuse_boxes(S['fusible'])
            extra += switch_boxes(S['interrupteur']) + coil_boxes(S['bobines'], t) + booth_glass(S['vitre'], S['cabine']) + fan_boxes(mode != 'brule', t)
            hh = pi.get('heure', '11:52')
            extra += clock_boxes(-.6, 2.35, PART_REZ[0], '-z', hh, S['horloge'], t, .44, pendulum=True)
            extra += clock_boxes(3.0, Y_ETAGE + 2.2, PART_ETA[1], '+z', hh, S['horloge'], t, .42)
            on = S['voyant'] > .5                                               # the battery display (blinking) and its LED dot
            extra.append(_tex_box(((BATTERY[0] + BATTERY[2]) / 2, .36, BATTERY[3] + .05), (.8, .33, .01), '+z', display_tex(tuple(pi.get('batterie', BATTERIE)), on), 1.1 if on else .15, (10, 6, 6)))
            extra.append(C((BATTERY[0] + .12, .93, BATTERY[3] - .1), (.06, .06, .06), (255, 40, 30) if on else (70, 20, 16), emis=2.5 if on else 0., cast=False))
            if S['cabine'] > .01:                                               # the booth's lamp
                extra.append(C((.28, 2.06, 3.95), (.8, .04, .8), (220, 236, 255), emis=1.5 * min(1.5, S['cabine']), cast=False))
            boxes = list(sc.boxes)
            if mode != 'allume':                                                 # electric indicators off ; the plate's white light stays (Noé's hand)
                for i in set(self.groups.get('commandes.voyants', []) + self.groups.get('machines.pilotes', [])):
                    b = copy.copy(boxes[i]); b.col = b.col * .25; boxes[i] = b
            if mode == 'brule':
                for i in self.groups.get('plaque.lumiere', []):
                    b = copy.copy(boxes[i]); b.emis = .05; b.col = b.col * .2; boxes[i] = b
            for (x, y0, z, ph) in ((-2.25, Y_PLAF - .1, 4.0, 0.), (2.3, Y_PLAF - .1, 4.0, .4), (-1.2, SLAB0 - .05, 4.3, .7), (1.0, SLAB0 - .05, 2.2, .2)):
                k = (t * .9 + ph) % 1.; yl = Y_ETAGE if y0 > Y_ETAGE else 0.          # drops of water falling from the ceiling
                extra.append(C((x, y0 - k * (y0 - yl - .05), z), (.025, .05, .025), (170, 196, 220), emis=.3, cast=False))
            sc.boxes = boxes + extra
            amb = np.array(S['ambient'], np.float32); fl = S['eclair']; sw = sweep(S, t)
            if fl > 0 or sw > 0:                                                 # the white flash (and the beam passing): ambient, sky
                amb = amb + np.array([.5, .52, .56], np.float32) * min(1., fl * .45 + sw * .12)
                sc.sky_fn = lambda D, _b=self._sky0, _w=min(1., fl * .7 + sw * .25): _b(D) * (1 - _w) + np.array([1.0, 1.0, .97], np.float32)[None] * _w * 1.6
            sc.ambient = tuple(float(v) for v in amb)
            halos = []
            if mode == 'allume':                                                 # the cone of the light circle of the palier in the dust
                halos.append(dict(apex=(-2.0, Y_PLAF - .9, -.45), axis=(0., -1., 0.), half=22., length=3.6, col=(1.0, .93, .78), dens=.55, R0=.12))
            if S['lune'] > 0:                                                    # moon shafts by the north-west windows
                md = moon_dir()
                for (name, th, hw, y0, y1, zn) in WINDOWS:
                    if name in MOON_WINDOWS:
                        x, z = pol(R_IN, th)
                        halos.append(dict(apex=(x, (y0 + y1) / 2, z), axis=tuple(float(-v) for v in md), half=11., length=4.2, col=(.55, .66, 1.0),
                                          dens=.35 * S['lune'] * (1. if mode != 'allume' else .6), R0=.3))
            if fl > .05 and S['eclair_source'] != 'generateur':                    # white shafts of the flash by every window
                for (name, th, hw, y0, y1, zn) in WINDOWS:
                    x, z = pol(R_IN, th); dx, dz = pol(1., th)
                    halos.append(dict(apex=(x, (y0 + y1) / 2, z), axis=(-dx, -.25, -dz), half=14., length=4.5, col=(1.0, 1.0, .97), dens=1.6 * min(2., fl), R0=.3))
            sc.post_fn = lambda img, cam, _sc=sc, _h=halos, _f=fl: _post(img, cam, _sc, _h, _f)
            return sc

        def lights(self, state, t, u, cam_pos):
            S = self.frame_state(state, t, u)
            return frame_lights(self.spec.get('_pi') or {}, getattr(self, '_pi_props', []), S, t, cam_pos, self.spec.get('fill', .5))

    _CLS['c'] = PhareInterieurSet
    return PhareInterieurSet


def _post(img, cam, sc, halos, fl):
    """the place's pass after the ray tracing: light cones in the dust (phare_foret.place_post), white veil of the flash"""
    from . import phare_foret as PF
    out = PF.place_post(img, cam, sc, None, halos, 0.) if halos else img
    if fl > 0:
        out = out * (1. + .25 * min(2., fl)) + np.array([.95, .96, 1.0], np.float32)[None, None] * (.22 * min(2., fl))
    return out
