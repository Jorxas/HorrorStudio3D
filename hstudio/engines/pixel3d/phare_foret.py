"""Lieu prêt `phare_foret` : une route de forêt la nuit, un phare apparu au milieu des pins, sa lumière qui efface (14 novembre 2026).

Né pour la série d'horreur « Le Phare qui efface » (Alma, son frère Noé, le Veilleur), rangé ici pour toute histoire :
    LIEUX = {'route': {'type': 'phare_foret'},
             'route_cabane_effacee': {'type': 'phare_foret', 'cabane': 'effacee'},
             'route_boulangerie_effacee': {'type': 'phare_foret', 'cabane': 'effacee', 'boulangerie': 'effacee'}}
Canon de la série : forêt de pins À CENT KILOMÈTRES DE LA MER (aucune mer), nuit sans pluie, lumière BLANCHE = effacement, ROUGE = échange.
Exigences du propriétaire (14/11/2026) : une nuit LISIBLE (ciel bleu profond et clair, lune, nuages éclairés, lune froide qui sculpte, beaucoup de
lumières pratiques chaudes) et un décor RICHE (forêt en profondeur, poteaux et câbles, panneaux, catadioptres, glissière, boîte aux lettres, clôture,
rideaux derrière les vitres, ardoise, vélo, banc, présentoir, plaques et lierre, rochers, fougères, souches, troncs couchés, brume basse) ; aucun objet
qui en traverse un autre (contrôlé par tools/check_phare_foret.py).

Repère (mètres) : x vers la droite de l'image quand on regarde vers +z, y vers le haut, sol à y = 0.
  - route asphaltée le long de z (|x| < 3,2, z de -80 à 120), ligne médiane pointillée, lignes de rive, bas-côtés de terre (3,2 < |x| < 4,3),
    catadioptres (x ±4,0, tous les 16 m), lampadaires au sodium côté gauche (x -4,2 ; z -12, 22, 52, 82, bras au-dessus de la route),
    poteaux électriques en bois et trois câbles côté droit (x 5,4 ; z -38, -13, 12, 37, 62, 87), glissière côté gauche (z -50 à -24),
    borne kilométrique (-4,5 ; 4), panneau de virage (-4,7 ; 33), panneau d'entrée du village (4,7 ; 44) ;
  - la VOITURE d'Alma (berline bleu nuit) arrêtée sur la voie de droite, centre (1,4 ; 0), cap +z ; habitacle filmable : pare-brise et vitres SANS verre
    (montants seulement), sièges, volant à gauche, tableau de bord avec un ÉCRAN central lisible (texte réglable) tourné vers l'habitacle ;
    phares allumés (projecteur + faisceaux visibles dans la brume) et feux arrière ;
  - la CABANE en bois à gauche de la route, centre (-9 ; 14), porche et TROIS MARCHES vers la route (+x), fenêtres éclairées à rideaux, cheminée,
    tas de bois, clôture de bois autour du terrain (ouverte devant les marches), boîte aux lettres ; `effacee` : il ne reste que les trois marches,
    en l'air au-dessus de l'herbe (la clôture et la boîte aux lettres restent) ;
  - le PHARE : base au centre (16 ; 34) dans une clairière de terre retournée (rayon 7,5), socle de pierre, fût à bandes rouges et blanches de 5 m à 3,2 m
    de large, lierre, plaques, porte métallique face à la route (côté -x, x 13,5) entre deux lampes grillagées, armoire électrique, galerie et garde-corps
    à y 19,85, lanterne praticable (plancher y 20,2, montants sans verre), grosse lentille au centre (16 ; 21,4 ; 34), coupole et paratonnerre (≈ 25,7 m) ;
  - la BOULANGERIE à droite de la route, centre (9 ; 56), deux niveaux, façade vers la route (mur ouest, x 6,5) : vitrine éclairée avec pains, porte,
    auvent rayé, enseigne « BOULANGERIE », fenêtres à rideaux à l'étage, ardoise « PAIN FRAIS », présentoir, banc, vélo, pots de fleurs, trois marches ;
    `effacee` : il reste les trois marches et le CONTOUR très discret du mur invisible (arêtes pâles et froides) ;
  - les MAISONS du village au-delà de z 68, fenêtres à rideaux éclairées, boîtes aux lettres ; `maisons_effacees` : il n'en reste que les trois marches ;
  - les TRACES de pas d'enfant (baskets mouillées) du pied de la porte vers les pins au sud-est ;
  - la FORÊT de pins (déterministe, `seed`) : pins proches détaillés, rangs lointains, rochers, fougères, souches, troncs couchés, sol d'aiguilles et de mousse ;
    ciel de nuit clair (lune, nuages éclairés, étoiles), brume basse entre les troncs.

Options (toutes facultatives) :
  voiture       True (défaut) | False | {'x': 1.4, 'z': 0., 'cap': 0 (ou 180), 'couleur': [38, 50, 78], 'phares': True,
                'ecran': ['NOE', 'ALMA, NE', 'REGARDE PAS', 'LE 7e ECLAIR']}   (1re ligne = expéditeur ; lignes de 13 caractères au plus ; `ecran: False` = éteint)
  cabane        'intacte' (défaut) | 'effacee' | False
  boulangerie   'intacte' (défaut) | 'effacee' | False ; `enseigne` (défaut « BOULANGERIE », 12 caractères au plus)
  maisons       4 (défaut, 0 à 6) ; maisons_effacees : liste d'indices (0..) dont il ne reste que les marches
  village       nom du panneau d'entrée (défaut ['SAINT-ALBAN', 'DES-PINS']) ; borne : texte de la borne (défaut 'D 47')
  traces / lampadaires / poteaux / panneaux   True (défaut) | False
  plaque        None (défaut : plaque sans texte) | texte court sur la plaque de la porte du phare
  main_vitre    False (défaut) | True (la main GAUCHE de Noé plaquée sur la vitre -z de la lanterne, avec sa cicatrice) | dict des arguments de
                `main_plaquee_blocs` (x, y, z, cote, face, echelle, peau, manche, cicatrice) | liste de dicts (plusieurs mains) ; groupe `main_vitre`
  mains_tenues  False (défaut) | dict des arguments de `main_tenue_blocs` (x, y, z, cap, cicatrice...) | liste : la main gauche de Noé, PAUME EN
                L'AIR, tenue dans la main d'Alma (insert ; « paume lisse » : cicatrice False) ; groupe `mains_tenues` (15/11/2026)
  maison_alma   False (défaut) | True | {'z': 112., 'porte': 'fermee'|'ouverte', 'voiture': True} : la MAISON D'ALMA au bout du village (à droite
                de la route, façade vers -x) : perron de trois marches et palier, porte, lampe de porche allumée, paillasson, boîte aux lettres,
                fenêtres éclairées ; `voiture` (défaut vrai) gare la voiture d'Alma à côté (1,4 m de la route, cap +z) sauf `voiture` écrit avec x/z
  lanterne      'allumee' (défaut) | 'eteinte' : le phare éteint POUR TOUJOURS (lentille noire, plus de faisceau, lampes de la porte et lumière
                de la lanterne éteintes) ; dans un plan : `state.lanterne_eteinte` 1 (15/11/2026)
  voiture       ... 'radio': True ajoute l'autoradio sous l'écran du tableau de bord (voyant et cadran qui grésillent avec `state.radio` 0..1)
  lanterne_appoint  True (défaut) : lumière douce cachée devant la lanterne (côté -x) pour qu'un visage derrière les montants reste lisible
  brume_basse   1.0 (défaut) : brume au ras du sol entre les troncs (0 = aucune)
  lune          1.8 (défaut) : force de la lumière de lune
  faisceau      dict des réglages par défaut du FAISCEAU (voir ci-dessous) | False (éteint par défaut)
  seed          graine de la forêt (défaut 7) ; ambient / fill / fog comme tout lieu extérieur

LE FAISCEAU (passe de lieu PS1, `PhareSet`) — réglé plan par plan dans `state` (les nombres s'animent : `[a, b]` sur le plan, `[a, b, t0, t1]`) :
  faisceau          1 (allumé, défaut) | 0 (éteint) | intensité (0..2)
  faisceau_angle    cap en DEGRÉS, comme un `yaw` : 0 = vers +z, 90 = vers +x, -90 = vers -x (la route), ±180 = vers -z (vers la voiture)
  faisceau_vitesse  degrés par seconde (défaut 0) : l'angle tourne avec le temps ABSOLU du film (même position d'un plan à l'autre)
  faisceau_pente    degrés vers le bas (défaut 8 ; 25 à 40 pour que le faisceau balaie la route et les maisons proches)
  faisceau_largeur  demi-angle du cône en degrés (défaut 6)
  faisceau_couleur  'blanc' (défaut) | 'rouge' | [r, g, b] (0..1)
  faisceau_double   False (défaut) | True : un second faisceau à l'opposé
  faisceau_brume    densité de brume dans le faisceau (défaut 1.0)
  Repères d'angle depuis la lentille : vers la voiture ≈ -157°, vers la cabane ≈ -129°, vers la boulangerie ≈ -18°, vers la caméra : `toward`.
  Le faisceau part de la lentille, se voit dans la brume (volume avec les ombres des arbres et des personnages), éclaire ce qu'il touche (projecteur),
  et éblouit quand il passe sur la caméra. En VOXEL : le lieu, la lentille et les lumières fixes sont dessinés, PAS le faisceau ni la brume basse.
Effet d'EFFACEMENT dans le plan : objet de plan `effacement` (effacement.py), sur les groupes `cabane`, `boulangerie`, `maison0`... (les marches restent).

Repères (`anchors`, (x, z) ; ceux en hauteur sont (x, y, z)) :
  start (1,4 ; -7), route (0 ; 10), voiture (1,4 ; 0), voiture.conducteur (1,0 ; 0 ; 0,30) [p d'un acteur `sit=1` cap +z : bassin à z 0, tête à plus
  de 5 cm de l'appui-tête (0,15 mettait la tête DANS l'appui-tête)], voiture.passager (1,8 ; 0 ; 0,30), voiture.arriere (1,4 ; 0 ; -0,9), voiture.tableau (1,4 ; 0,79 ; 0,6) [centre de l'écran, tourné vers -z],
  voiture.plancher (1,0 ; 0,31 ; 0,3) [plancher côté conducteur], voiture.devant (1,4 ; 3,4), voiture.portiere (-0,3 ; 0,2) [libre, porte conducteur],
  cabane (-9 ; 14), cabane.marches (-5,55 ; 14), cabane.devant (-4,6 ; 14) [libre, entre la clôture et la route],
  phare (16 ; 34), phare.pied (11,7 ; 34) [libre, au bas des deux marches], phare.porte (13,05 ; 0,45 ; 34) [SUR le socle (y 0,45), devant la porte, libre],
  phare.vitre (16 ; 20,2 ; 32,85) [plancher de la lanterne, face tournée vers la VOITURE (-z) : l'enfant regarde -z],
  phare.vitre_route (14,85 ; 20,2 ; 34) [face tournée vers la route (-x) : l'enfant regarde -x], phare.lentille (16 ; 21,4 ; 34), phare.galerie (13,9 ; 19,85 ; 34),
  boulangerie (9 ; 56), boulangerie.seuil (5,45 ; 57,5), boulangerie.mur (6,1 ; 55,0) [devant le mur invisible, côté route, libre],
  boulangerie.vitrine (6,5 ; 55), traces.debut (12,4 ; 33,0), traces.fin (25,6 ; 22,6), foret (-12 ; 30), clairiere (11 ; 28), maison0 … maisonN.
  Zones libres contrôlées (aucun bloc à 0,5 / 1,0 / 1,6 m) : `ZONES_LIBRES` ci-dessous.
"""
import copy
import math
import numpy as np

# ------------------------------------------------------------------ palette
WHITE_T = (172, 168, 160); RED_T = (162, 40, 36); STONE = (118, 116, 110); STONE_D = (88, 86, 82); IRON = (48, 52, 58); IRON_L = (82, 86, 94)
WOOD_C = (96, 74, 54); WOOD_D = (70, 52, 38); ROOF_C = (62, 54, 50); GLASS_WARM = (255, 206, 132); SODIUM = (255, 196, 118)
CAR_BLUE = (50, 66, 102); CAR_IN = (46, 48, 56); CAR_DASH = (36, 38, 44)
PINE_COLS = ((30, 62, 48), (34, 68, 50), (28, 58, 54), (38, 72, 54), (32, 64, 46))

LIGHTHOUSE = (16.0, 34.0)                 # centre of the tower base
GALLERY_Y = 19.85; LANTERN_FLOOR = 20.2; LENS_Y = 21.4
CABIN = (-9.0, 14.0); BAKERY = (9.0, 56.0); CAR = (1.4, 0.0)
TRAIL = [(12.4, 33.0), (12.9, 30.2), (15.3, 28.3), (18.3, 26.7), (21.0, 25.0), (23.4, 23.6), (25.6, 22.6)]
HOUSES = [(-9.8, 71.0, 3), (9.8, 74.5, 1), (-10.4, 84.0, 3), (10.2, 88.0, 1), (-9.6, 97.0, 3), (9.9, 100.5, 1)]
LAMPS_Z = (-12.0, 22.0, 52.0, 82.0); POLES_Z = (-38.0, -13.0, 12.0, 37.0, 62.0, 87.0); POLE_X = 5.4
SIGN_CURVE = (-4.7, 33.0); SIGN_VILLAGE = (4.7, 44.0); BORNE = (-4.5, 4.0); MAILBOX = (-4.75, 11.9)
# free zones for the actors (x, z, radius): no block between 0.05 and 1.8 m there
# sight lanes kept free of trees: the lighthouse is seen from the car and from the road beside it ((x, z) -> (x, z), half width)
VIEW_LANES = (((3.0, -4.0), (12.5, 30.5), 3.2), ((4.5, 18.0), (11.0, 31.0), 2.6), ((4.5, 40.0), (10.5, 38.0), 2.2))
ZONES_LIBRES = {'voiture.portiere': (-.3, .2, .35), 'cabane.devant': (-4.6, 14.0, .3), 'phare.pied': (11.7, 34.0, .3), 'phare.porte': (13.05, 34.0, .2),
                'traces.debut': (12.4, 33.0, .25), 'boulangerie.mur': (6.1, 55.0, .25), 'boulangerie.seuil': (5.2, 57.5, .2), 'route': (0., 10., .5),
                'clairiere': (11.0, 28.0, .5), 'start': (1.4, -7.0, .5)}

DEFAULT_BEAM = {'angle': -140., 'vitesse': 0., 'pente': 8., 'largeur': 6., 'couleur': 'blanc', 'double': False, 'force': 1.0, 'brume': 1.0}
BEAM_COLORS = {'blanc': (1.0, .97, .90), 'white': (1.0, .97, .90), 'rouge': (1.0, .16, .10), 'red': (1.0, .16, .10)}
NIGHT_SKY = dict(zen=(.06, .11, .27), hor=(.20, .27, .44), moon=(1.0, .98, .9), cloud=(.36, .40, .53), shade=(.14, .17, .27), light=.55, cover=.42, stars=1.)
MOON_DIR = np.array([-.45, .42, .78], np.float32) / np.linalg.norm(np.array([-.45, .42, .78], np.float32))


def block(at, size, color, material='plaster', **kw):
    return dict(at=[round(float(x), 3) for x in at], size=[round(float(x), 3) for x in size], color=[int(c) for c in color], material=material, **kw)


def _oct(cx, cz, y, h, w, color, mat='plaster', **kw):
    """an octagonal prism approximated by three crossed boxes (width w, height h, bottom y)"""
    s = w * .5
    return [block((cx, y, cz), (w, h, s), color, mat, **kw), block((cx, y, cz), (s, h, w), color, mat, **kw),
            block((cx, y, cz), (w * .78, h, w * .78), color, mat, **kw)]


def _steps(x_top, dx, z, width, tops, thick, col, gid, mode):
    """three steps: the TREADS (group `<gid>.marches`, they stay when the element is erased) and the risers under them (group `<gid>`)"""
    B = []; mat = 'wood' if col == WOOD_D else 'stone'
    for k, top in enumerate(tops):
        x = x_top + dx * k
        B.append(block((x, top - thick, z), (abs(dx), thick, width), col, mat, group=gid + '.marches'))
        if mode != 'effacee' and top - thick > .005:
            B.append(block((x, 0, z), (abs(dx) * .94, top - thick, width * .94), tuple(int(c * .8) for c in col), mat, group=gid))
    return B


# ================================================================== the car (local frame: centre of the bottom, front towards +z)
def voiture_blocs(couleur=CAR_BLUE, phares=True, ecran=True, radio=False):
    """Alma's car as at most 128 blocks in its LOCAL frame (`at` = centre of the bottom of each block, front towards +z, driver on the LEFT, -x).
    The same list is the place's car and a `prop:assemblage` for a `mover` (a car that drives in and brakes):
        {'type': 'mover', 'thing': 'prop:assemblage', 'blocks': voiture_blocs(), 'path': [[1.4, 0, -30], [1.4, 0, 0]], 'dur': 3.0, 'pitch': 0, 'bank': 0}
    No glass: windscreen and side windows are open, so a camera inside sees out and a camera outside sees in."""
    c = tuple(couleur); cd = tuple(int(v * .72) for v in c); cl = tuple(min(255, int(v * 1.18)) for v in c)
    B = []
    for sx in (-1, 1):                                                                                                   # wheels, rims, arches
        for sz in (-1, 1):
            B += [block((sx * .84, 0, sz * 1.38), (.24, .64, .64), (20, 20, 22), 'fabric'), block((sx * .97, .17, sz * 1.38), (.02, .3, .3), (150, 152, 158), 'metal'),
                  block((sx * .87, .64, sz * 1.38), (.18, .06, .8), cd, 'metal')]
    B += [block((0, .3, 1.48), (1.82, .6, 1.44), c, 'metal'), block((0, .9, 1.53), (1.74, .06, 1.24), cl, 'metal'),     # front block + hood
          block((0, .3, -1.78), (1.82, .62, .84), c, 'metal'), block((0, .92, -1.83), (1.74, .05, .66), cl, 'metal'),   # trunk + lid
          block((-.87, .3, -.3), (.08, .62, 2.1), c, 'metal'), block((.87, .3, -.3), (.08, .62, 2.1), c, 'metal'),      # door panels
          block((-.87, .2, -.3), (.1, .1, 2.1), cd, 'metal'), block((.87, .2, -.3), (.1, .1, 2.1), cd, 'metal'),        # sills
          block((0, .2, -.3), (1.64, .1, 2.1), (30, 30, 32), 'fabric')]                                                  # cabin floor (top y .30)
    for sx in (-1, 1):                                                                                                    # door seams and handles
        B += [block((sx * .915, .34, -.52), (.01, .56, .02), cd, 'metal'), block((sx * .92, .74, .28), (.02, .04, .16), (170, 172, 178), 'metal'),
              block((sx * .92, .74, -.9), (.02, .04, .16), (170, 172, 178), 'metal')]
    B += [block((0, .26, 2.24), (1.86, .22, .08), (34, 34, 38), 'metal'), block((0, .5, 2.215), (.86, .22, .03), (18, 18, 20), 'metal'),
          block((0, .29, 2.285), (.5, .13, .01), (214, 214, 206), 'card')]
    for sx in (-1, 1):
        B += [block((sx * .64, .62, 2.225), (.36, .14, .03), (255, 246, 214), 'light', emissive=(2.4 if phares else .15), no_shadow=True),
              block((sx * .86, .5, 2.225), (.08, .08, .03), (255, 170, 60), 'light', emissive=.6, no_shadow=True)]
    B += [block((0, .26, -2.24), (1.86, .22, .08), (34, 34, 38), 'metal'), block((0, .34, -2.285), (.5, .13, .01), (214, 214, 206), 'card')]
    for sx in (-1, 1):
        B.append(block((sx * .64, .68, -2.225), (.4, .14, .03), (220, 26, 22), 'light', emissive=1.6, no_shadow=True))
    for sx in (-1, 1):                                                                                                    # windscreen frame, pillars, mirrors
        x = sx * .84
        B += [block((x, .95, .7), (.08, .2, .14), cd, 'metal'), block((x, 1.15, .53), (.08, .18, .18), cd, 'metal'),
              block((x, 1.33, .36), (.08, .17, .18), cd, 'metal'),
              block((sx * .86, .92, -.57), (.08, .58, .1), cd, 'metal'),
              block((x, .92, -1.48), (.08, .2, .22), cd, 'metal'), block((x, 1.12, -1.31), (.08, .2, .2), cd, 'metal'),
              block((x, 1.32, -1.14), (.08, .18, .18), cd, 'metal'),
              block((sx * .98, .98, .66), (.12, .12, .1), cd, 'metal')]
    B += [block((0, 1.5, -.42), (1.76, .07, 1.5), c, 'metal'), block((0, 1.43, .3), (1.6, .07, .12), cd, 'metal'),
          block((0, 1.43, -1.12), (1.6, .07, .14), cd, 'metal'), block((0, .92, .8), (1.6, .03, .1), cd, 'metal'),
          block((0, .92, -1.43), (1.6, .05, .2), CAR_IN, 'fabric'), block((0, 1.36, .27), (.24, .06, .04), (60, 62, 66), 'metal')]
    B += [block((0, .55, .79), (1.6, .37, .34), CAR_DASH, 'fabric'), block((-.4, .92, .79), (.46, .07, .18), (26, 26, 28), 'fabric'),
          block((-.4, .8, .615), (.32, .1, .01), (90, 130, 170), 'light', emissive=.45, no_shadow=True),
          block((.42, .62, .615), (.44, .16, .01), (44, 44, 48), 'fabric'), block((0, .67, .61), (.36, .25, .01), (14, 14, 16), 'metal')]
    if not ecran:
        B.append(block((0, .71, .604), (.3, .18, .005), (8, 10, 14), 'metal'))
    if radio:                                                                                           # 15/11/2026: the car radio under the screen (dial: texture of PhareSet)
        B += [block((0, .555, .606), (.28, .1, .02), (22, 22, 26), 'metal'), block((-.11, .585, .594), (.035, .035, .015), (170, 170, 176), 'metal'),
              block((.11, .585, .594), (.035, .035, .015), (170, 170, 176), 'metal'),
              block((.075, .62, .595), (.012, .012, .006), (255, 60, 40), 'light', emissive=1.2, no_shadow=True, group='voiture.radio')]
    B += [block((-.4, .8, .52), (.06, .06, .08), (20, 20, 22), 'metal'), block((-.4, 1.02, .46), (.36, .045, .04), (18, 18, 20), 'fabric'),
          block((-.4, .7, .46), (.36, .045, .04), (18, 18, 20), 'fabric'), block((-.56, .745, .46), (.04, .275, .04), (18, 18, 20), 'fabric'),
          block((-.24, .745, .46), (.04, .275, .04), (18, 18, 20), 'fabric'), block((-.4, .83, .46), (.12, .1, .04), (40, 40, 44), 'metal')]
    for sx in (-1, 1):                                                                                                    # front seats (cushion top .45)
        x = sx * .4
        B += [block((x, .3, -.13), (.5, .15, .5), CAR_IN, 'fabric'), block((x, .3, -.41), (.5, .8, .12), CAR_IN, 'fabric'),
              block((x, 1.12, -.43), (.28, .2, .1), (46, 46, 50), 'fabric')]
    B += [block((0, .3, -1.05), (1.5, .15, .5), CAR_IN, 'fabric'), block((0, .3, -1.33), (1.5, .7, .12), CAR_IN, 'fabric'),
          block((0, .3, .22), (.2, .26, .5), (28, 28, 30), 'fabric')]
    return B


def _car_world(blocks, cx, cz, cap):
    out = []
    flip = int(round(cap)) % 360 == 180
    for b in blocks:
        b = dict(b); x, y, z = b['at']
        if flip: x, z = -x, -z
        b['at'] = [round(cx + x, 3), y, round(cz + z, 3)]
        out.append(b)
    return out


def car_spec(spec):
    v = spec.get('voiture', True)
    if not v: return None
    v = {} if v is True else dict(v)
    v.setdefault('x', CAR[0]); v.setdefault('z', CAR[1]); v.setdefault('cap', 0); v.setdefault('couleur', list(CAR_BLUE)); v.setdefault('phares', True)
    v.setdefault('ecran', ['NOE', 'ALMA, NE', 'REGARDE PAS', 'LE 7e ECLAIR']); v.setdefault('radio', False)
    return v


# ================================================================== a hand pressed flat on a pane (object of the series, any place)
FACES = {'-z': (0., -1.), '+z': (0., 1.), '-x': (-1., 0.), '+x': (1., 0.)}
NOE_SKIN = (198, 146, 112); NOE_SLEEVE = (52, 90, 60); SCAR = (150, 62, 74)
MAIN_VITRE = {'x': 16.27, 'y': 21.45, 'z': 32.47, 'cote': 'gauche', 'face': '-z'}     # Noé's left hand on the -z pane of the lantern (default of `main_vitre`)


def main_plaquee_blocs(x, y, z, cote='gauche', face='-z', echelle=1.0, peau=NOE_SKIN, manche=NOE_SLEEVE, cicatrice=True, group=None):
    """A hand pressed FLAT on a pane, readable in an insert (a PS1 actor's hand is a tilted cube): palm, four slightly spread fingers with nail
    edges, thumb towards the body, cuff and forearm going back behind the pane, and (`cicatrice`) a crescent scar of five small blocks in the palm.
      (x, y, z)  centre of the palm, ON the pane (the palm block is centred on it in depth)
      face       where the palm faces = where its owner looks ('-z' | '+z' | '-x' | '+x'): the hand is seen from that side, the arm goes the other way
      cote       'gauche' | 'droite' : the owner's left or right hand (the thumb points to the owner's midline)
      echelle    1.0 = a 13-year-old's hand (palm 7.8 x 8.8 cm) ; peau, manche : colours [r, g, b]
    -> blocks (`at` = bottom centre) for a place's `blocks` (PS1 and VOXEL draw them the same way). Insert: camera on the `face` side at ~0.6 m,
    fov ~34 ; in front of a very bright lens use `fx.expo` ≈ 0.5 and `lighting.fill` ≈ 1.3, NO warm halo close to the palm: it burns it
    yellow-white (measured 15/11, power .5 already too much ; docs/PIEGES_MISE_EN_SCENE.md)."""
    if face not in FACES: raise ValueError(f'main plaquée : face « {face} » inconnue (-z, +z, -x, +x)')
    if cote not in ('gauche', 'droite'): raise ValueError(f'main plaquée : côté « {cote} » inconnu (gauche, droite)')
    nx, nz = FACES[face]
    rx, rz = nz, -nx                                                   # the owner's right, seen from where he looks (x right when looking +z)
    lx, lz = (-rx, -rz) if cote == 'gauche' else (rx, rz)              # lateral axis: the thumb lies at l < 0, i.e. towards the owner's midline
    k = float(echelle); skin = list(peau); dark = [int(round(c * f)) for c, f in zip(skin, (.808, .767, .75))]; sleeve = list(manche)
    def put(l, dy, d, size, col):
        """l along the lateral axis, dy height of the bottom, d depth behind the pane (towards the owner) ; size (lateral, height, depth)"""
        wx = x + (l * lx - d * nx) * k; wz = z + (l * lz - d * nz) * k
        sx, sy, sd = size
        sz_ = [sx * k, sy * k, sd * k] if abs(nz) > .5 else [sd * k, sy * k, sx * k]
        b = dict(at=[round(wx, 4), round(y + dy * k, 4), round(wz, 4)], size=[round(v, 4) for v in sz_], color=col, material='fabric')
        if group: b['group'] = group
        return b
    B = [put(0., -.045, 0., (.078, .088, .022), skin),                                     # palm
         put(.004, -.095, .03, (.07, .06, .07), sleeve),                                   # cuff
         put(.004, -.2, .1, (.085, .12, .2), sleeve)]                                      # forearm, back behind the pane
    for dl, ln in ((-.026, .05), (-.008, .058), (.01, .056), (.028, .046)):                # four fingers, slightly spread, nail edges at the tips
        l = dl + .002 * (dl / .02)
        B.append(put(l, .043, 0., (.016, ln, .02), skin))
        B.append(put(l, .043 + ln - .012, -.011, (.013, .01, .002), dark))
    B.append(put(-.05, -.03, 0., (.02, .045, .02), skin))                                  # thumb, towards the body
    if cicatrice:                                                                           # the crescent scar, mid palm, on the visible side
        for a in (2.35, 2.75, 3.15, 3.55, 3.95):
            B.append(put(.004 + .02 * math.cos(a), -.006 + .02 * math.sin(a), -.012, (.009, .009, .003), list(SCAR)))
    return B


ALMA_SKIN = (214, 172, 142); ALMA_SLEEVE = (46, 60, 100)


def main_tenue_blocs(x, y, z, cap=0., cicatrice=False, echelle=1.0, peau=NOE_SKIN, manche=NOE_SLEEVE, peau_alma=ALMA_SKIN, manche_alma=ALMA_SLEEVE,
                     alma=True, cote_alma='droite', group=None):
    """Noé's LEFT hand held PALM UP in Alma's hand, readable in an insert seen from above (« sa paume est lisse » : cicatrice=False ; with
    cicatrice=True the crescent scar of `main_plaquee_blocs`, same size and place).
      (x, y, z)  centre of the TOP of Noé's palm ; `cap` (degrees, like a yaw) = where his fingers point (0 = +z) ; his forearm and green cuff
                 go the other way ; a left hand palm up: the thumb lies on the left of the fingers' direction
      alma       Alma's hand under it (her palm under his, four fingers curling up over the little-finger side, thumb over the base of his thumb),
                 her navy coat sleeve coming from `cote_alma` ('droite' | 'gauche' of the fingers' direction)
    -> blocks for a place's `blocks` (PS1 and VOXEL draw them the same way). Insert: camera above (≈ 0,5 m), looking down, fov ≈ 34."""
    k = float(echelle); c, s_ = math.cos(math.radians(cap)), math.sin(math.radians(cap))
    fx, fz = s_, c                                                      # fingers' direction
    rx, rz = c, -s_                                                     # right of that direction (x right when looking +z)
    skin = list(peau); dark = [int(round(v * f)) for v, f in zip(skin, (.8, .76, .74))]; line = [int(v * .86) for v in skin]
    def put(f, l, dy, size, col, flat=True):
        """f along the fingers, l to the right, dy height of the bottom from the palm top ; size (along f, height, along l)"""
        wx = x + (f * fx + l * rx) * k; wz = z + (f * fz + l * rz) * k
        sf, sh, sl = size
        horiz = abs(fz) > .7
        sz_ = [sl * k, sh * k, sf * k] if horiz else [sf * k, sh * k, sl * k]
        b = dict(at=[round(wx, 4), round(y + dy * k, 4), round(wz, 4)], size=[round(v, 4) for v in sz_], color=list(col), material='fabric')
        if group: b['group'] = group
        return b
    B = [put(0., 0., -.022, (.088, .022, .078), skin),                                  # palm (its top at y)
         put(-.075, .0, -.03, (.07, .06, .07), manche), put(-.2, 0., -.05, (.2, .08, .085), manche)]   # cuff and forearm
    for dl, ln in ((.028, .05), (.01, .056), (-.008, .058), (-.026, .046)):              # four fingers (little finger on the right), a little curled
        B.append(put(.044 + ln / 2, dl, -.02, (ln, .018, .016), skin))
        B.append(put(.044 + ln - .006, dl, -.004, (.008, .004, .013), dark))           # nail edges seen from above at the tips
    B.append(put(.0, -.05, -.018, (.045, .018, .02), skin))                            # thumb, on the left
    B += [put(.005, .012, -.0005, (.05, .001, .004), line), put(-.012, -.006, -.0005, (.04, .001, .004), line)]   # two faint palm lines (a smooth palm still reads as a palm)
    if cicatrice:                                                                       # the crescent scar, mid palm
        for a in (2.35, 2.75, 3.15, 3.55, 3.95):
            B.append(put(.004 + .02 * math.sin(a), .006 + .02 * math.cos(a), -.001, (.009, .003, .009), list(SCAR)))
    if alma:
        sd = 1. if cote_alma == 'droite' else -1.
        ask = list(peau_alma)
        B.append(put(-.005, sd * .012, -.05, (.1, .026, .09), ask))                     # her palm under his
        for i, df in enumerate((-.03, -.01, .01, .03)):                                 # her four fingers curling up over the far edge
            B.append(put(df, sd * .056, -.045, (.017, .05, .018), ask))
            B.append(put(df, sd * .045, .004, (.017, .012, .02), ask))
        B.append(put(-.04, -sd * .045, -.004, (.04, .016, .02), ask))                  # her thumb over the base of his thumb
        B.append(put(-.01, sd * .16, -.07, (.09, .09, .2), manche_alma))                # her sleeve, coming from her side
    return B


def maison_alma_spec(spec):
    m = spec.get('maison_alma')
    if not m: return None
    m = {} if m is True else dict(m)
    m.setdefault('z', 112.); m.setdefault('porte', 'fermee'); m.setdefault('voiture', True); m.setdefault('lampe', True)
    return m


def maison_alma_blocs(m):
    """Alma's house at the end of the village (right of the road, facade towards -x): body and roof, porch landing and three steps, door
    (closed or ajar), porch lamp, doormat, mailbox, path. -> (blocks, windows, lights, anchors, texts)"""
    zc = float(m['z']); xf = 7.0; x1 = 12.0; z0, z1 = zc - 3.0, zc + 3.0
    wall = (122, 110, 96); trim = (96, 74, 54); roof = (92, 56, 48)           # mid-tone facade: a light one burns near its lamp (14/11 lesson)
    B = [block(((xf + x1) / 2, 0, zc), (x1 - xf, .6, z1 - z0), (110, 106, 100), 'stone', group='maison_alma'),
         block(((xf + x1) / 2 + .08, .6, zc), (x1 - xf - .16, 4.6, z1 - z0), wall, 'plaster', group='maison_alma')]
    # facade (x = xf): wall pieces around the door (z zc-.55 .. zc+.55, y .6 .. 2.75) and two windows (z zc-1.9, zc+1.9 ; y 1.2 .. 2.2)
    def fw(za, zb, ya, yb): return block((xf + .06, ya, (za + zb) / 2), (.12, yb - ya, zb - za), wall, 'plaster', group='maison_alma')
    B += [fw(z0, zc - 2.4, .6, 5.2), fw(zc - 1.4, zc - .55, .6, 5.2), fw(zc + .55, zc + 1.4, .6, 5.2), fw(zc + 2.4, z1, .6, 5.2),
          fw(zc - 2.4, zc - 1.4, .6, 1.2), fw(zc - 2.4, zc - 1.4, 2.2, 5.2), fw(zc + 1.4, zc + 2.4, .6, 1.2), fw(zc + 1.4, zc + 2.4, 2.2, 5.2),
          fw(zc - .55, zc + .55, 2.75, 5.2)]
    B.append(block((xf - .02, 2.7, zc), (.1, .08, 1.3), trim, 'wood', group='maison_alma'))                     # lintel
    for zz in (zc - .6, zc + .6): B.append(block((xf - .02, .6, zz), (.1, 2.18, .1), trim, 'wood', group='maison_alma'))
    if m.get('porte') == 'ouverte':
        B.append(block((xf + .55, .6, zc + .5), (1.0, 2.1, .06), (70, 48, 36), 'door', group='maison_alma'))     # the leaf open against the inside wall
        B.append(block((xf + 1.6, .6, zc), (.1, 2.1, 1.1), (60, 52, 46), 'plaster', group='maison_alma'))      # a dark hallway behind
    else:
        B += [block((xf + .02, .6, zc), (.06, 2.1, 1.08), (70, 48, 36), 'door', group='maison_alma'),
              block((xf - .02, 1.55, zc - .38), (.04, .05, .12), (190, 170, 110), 'metal', group='maison_alma'),
              block((xf - .015, 1.9, zc), (.02, .5, .6), (60, 42, 32), 'wood', group='maison_alma')]
    for zz in (zc - 1.9, zc + 1.9):                                                                              # window sills and shutters
        B += [block((xf - .06, 1.14, zz), (.14, .06, 1.1), trim, 'wood', group='maison_alma'),
              block((xf - .03, 1.2, zz - .62), (.04, 1.0, .2), (70, 96, 80), 'wood', group='maison_alma'), block((xf - .03, 1.2, zz + .62), (.04, 1.0, .2), (70, 96, 80), 'wood', group='maison_alma')]
    for i in range(5):                                                                                           # stepped gabled roof (ridge along z)
        w = 5.4 - i * 1.15
        B.append(block(((xf + x1) / 2, 5.2 + i * .34, zc), (max(.5, w), .34, z1 - z0 + .4), roof if i % 2 == 0 else (80, 48, 42), 'wood', group='maison_alma'))
    B += [block((x1 - 1.2, 5.6, zc + 1.6), (.5, 1.6, .5), (122, 94, 82), 'plaster', group='maison_alma')]                  # chimney
    # porch: landing (top .6) and three steps down towards the road (tops .45 .3 .15), small roof on two posts, lamp, doormat
    B += [block((xf - .5, 0, zc), (1.0, .6, 1.6), (114, 108, 100), 'stone', group='maison_alma.perron')]
    for kk, top in enumerate((.45, .3, .15)):
        B.append(block((xf - 1.15 - kk * .3, 0, zc), (.3, top, 1.4), (108, 102, 96), 'stone', group='maison_alma.perron'))
    B += [block((xf - .95, .6, zc - .75), (.08, 2.35, .08), trim, 'wood', group='maison_alma.perron'), block((xf - .95, .6, zc + .75), (.08, 2.35, .08), trim, 'wood', group='maison_alma.perron'),
          block((xf - .5, 2.95, zc), (1.2, .08, 1.8), roof, 'wood', group='maison_alma.perron'),
          block((xf - .45, .6, zc), (.6, .015, .8), (110, 84, 52), 'fabric', group='maison_alma.perron')]           # doormat
    B += [block((xf - .08, 2.25, zc + .78), (.06, .04, .1), (40, 40, 44), 'metal', group='maison_alma'),
          block((xf - .13, 2.05, zc + .78), (.12, .2, .12), (255, 214, 140), 'light', emissive=1.4 if m.get('lampe', True) else .1, no_shadow=True, group='maison_alma')]
    B += [block((5.6, 0, zc + 1.4), (.08, 1.05, .08), (70, 56, 42), 'wood', group='maison_alma'), block((5.6, 1.05, zc + 1.4), (.36, .3, .5), (60, 76, 110), 'metal', group='maison_alma')]
    windows = [dict(at=(xf - .025, 1.2, zz), size=(.02, 1.0, .9), face='-x', seed=61 + i, lit=True, group='maison_alma') for i, zz in enumerate((zc - 1.9, zc + 1.9))]
    windows += [dict(at=(xf - .02, 3.4, zz), size=(.02, .9, .8), face='-x', seed=63 + i, lit=(i == 0), group='maison_alma') for i, zz in enumerate((zc - 1.9, zc + 1.9))]
    lights = [((xf - 1.5, 2.0, zc + .7), (1.0, .8, .52), .65 if m.get('lampe', True) else 0., 4.2, False, 'maison_alma'),
              ((xf - 1.6, 1.6, zc - 1.9), (1.0, .76, .46), .5, 2.6, False, 'maison_alma'), ((xf - 1.6, 1.6, zc + 1.9), (1.0, .76, .46), .5, 2.6, False, 'maison_alma')]
    anchors = {'maison': (xf + 2.5, zc), 'maison.seuil': (xf - .5, .6, zc), 'maison.porte': (xf, .6, zc), 'maison.perron': (xf - 1.75, zc),
               'maison.allee': (xf - 2.6, zc)}
    return B, windows, lights, anchors


# ================================================================== the cabin
def cabane_blocs(mode):
    """-> (blocks, windows, lights) ; everything of the cabin is group `cabane`, the treads `cabane.marches` (fence and mailbox are not the cabin)"""
    if not mode: return [], [], []
    cx, cz = CABIN; x0, x1, z0, z1 = cx - 2.0, cx + 2.0, cz - 1.75, cz + 1.75
    steps = _steps(x1 + 1.15, .3, cz, 1.3, (.66, .44, .22), .08, WOOD_D, 'cabane', mode)
    mat = block((x1 + 1.15, .66, cz), (.26, .012, .5), (96, 76, 54), 'fabric', group='cabane.marches')
    if mode == 'effacee': return steps + [mat], [], []
    B = []
    for x in (x0 + .2, x1 - .2):
        for z in (z0 + .2, cz, z1 - .2): B.append(block((x, 0, z), (.3, .58, .3), STONE_D, 'stone'))
    B += [block((cx, .58, cz), (4.0, .12, 3.5), WOOD_D, 'wood'), block((x1 + .5, .58, cz), (1.0, .1, 2.6), WOOD_D, 'wood')]
    wall = (104, 84, 64); wall2 = (92, 74, 56)
    for k in range(7):                                                                         # plank courses on the south and north walls
        B += [block((cx, .7 + k * .33, z0 + .06), (4.0, .33, .12), wall if k % 2 == 0 else wall2, 'wood'),
              block((cx, .7 + k * .33, z1 - .06), (4.0, .33, .12), wall if k % 2 == 0 else wall2, 'wood')]
    B.append(block((x0 + .06, .7, cz), (.12, 2.3, 3.5), wall, 'wood'))
    # east wall (towards the road): door (z 13.55..14.45) and window (z 14.95)
    B += [block((x1 - .06, .7, z0 + .9), (.12, 2.3, 1.8), wall, 'wood'), block((x1 - .06, .7, 15.55), (.12, 2.3, .4), wall, 'wood'),
          block((x1 - .06, 2.75, 14.0), (.12, .25, .9), wall, 'wood'), block((x1 - .06, .7, 14.95), (.12, .8, .6), wall, 'wood'),
          block((x1 - .06, 2.2, 14.95), (.12, .8, .6), wall, 'wood'),
          block((x1 - .02, .7, 14.0), (.06, 2.05, .9), (74, 52, 38), 'door'), block((x1 + .02, 1.6, 13.7), (.04, .06, .1), (180, 160, 110), 'metal'),
          block((x1 - .08, 1.5, 14.95), (.04, .7, .6), GLASS_WARM, 'light', emissive=.8, no_shadow=True),
          block((x1 + .01, 1.47, 14.95), (.04, .04, .7), WOOD_D, 'wood'), block((x1 + .01, 2.2, 14.95), (.04, .04, .7), WOOD_D, 'wood')]
    # south wall window (seen from the road and from the car)
    B += [block((cx + .6, 1.5, z0 - .02), (.8, .7, .04), GLASS_WARM, 'light', emissive=.8, no_shadow=True),
          block((cx + .6, 1.46, z0 - .06), (.9, .04, .04), WOOD_D, 'wood'), block((cx + .6, 2.2, z0 - .06), (.9, .04, .04), WOOD_D, 'wood')]
    for i in range(6):                                                                         # gabled roof, stepped (ridge along z)
        w = 4.6 - i * .78
        B.append(block((cx, 3.0 + i * .3, cz), (max(.3, w), .3, 4.1), ROOF_C if i % 2 == 0 else (72, 60, 54), 'wood'))
    B += [block((x1 + .95, .68, cz - 1.2), (.1, 2.1, .1), WOOD_D, 'wood'), block((x1 + .95, .68, cz + 1.2), (.1, 2.1, .1), WOOD_D, 'wood'),
          block((x1 + .5, 2.78, cz), (1.2, .08, 2.8), ROOF_C, 'wood'),
          block((x1 + .08, 2.25, cz - .62), (.12, .18, .12), (255, 214, 140), 'light', emissive=1.6, no_shadow=True),
          block((x1 + .03, 2.43, cz - .62), (.12, .03, .12), (40, 40, 44), 'metal'),
          block((x0 + .5, 3.2, cz + .9), (.5, 2.3, .5), (104, 98, 92), 'stone'), block((x0 + .5, 5.5, cz + .9), (.58, .12, .58), (80, 76, 72), 'stone'),
          block((x0 - .45, 0, cz + .6), (.6, .5, 1.6), (88, 64, 44), 'wood'), block((x0 - .45, .5, cz + .6), (.5, .3, 1.4), (100, 74, 50), 'wood'),
          block((x0 - .45, 0, cz - 1.0), (.5, .45, .5), (84, 66, 48), 'wood'), block((x0 - .45, .45, cz - .9), (.04, .5, .04), (120, 96, 70), 'wood'),   # chopping block + axe
          block((x1 + .3, .68, cz + 1.0), (.45, .6, .45), (92, 64, 44), 'wood')]                                                                    # barrel on the porch
    B.append(mat)
    for b in B:
        if 'group' not in b: b['group'] = 'cabane'
    windows = [dict(at=(x1 + .02, 1.5, 14.95), size=(.02, .7, .6), face='+x', seed=3, lit=True, group='cabane'),
               dict(at=(cx + .6, 1.5, z0 - .05), size=(.8, .7, .02), face='-z', seed=5, lit=True, group='cabane')]
    lights = [((x1 + .3, 2.15, cz - .62), (1.0, .78, .48), 1.3, 4.2, False, 'cabane'), ((cx + .6, 1.8, z0 - .7), (1.0, .76, .46), .7, 2.6, False, 'cabane'),
              ((x1 + .6, 1.8, 14.95), (1.0, .76, .46), .6, 2.4, False, 'cabane')]
    return B + steps, windows, lights


def enclos_blocs():
    """fence around the cabin's yard (open in front of the steps) and the mailbox by the road: they stay when the cabin is erased"""
    B = []; fc = (96, 78, 58); x_f = -4.95
    def rail_x(x, za, zb):
        out = [block((x, .35, (za + zb) / 2), (.05, .08, zb - za), fc, 'wood'), block((x, .75, (za + zb) / 2), (.05, .08, zb - za), fc, 'wood')]
        n = max(1, int((zb - za) / 1.2)); out += [block((x, 0, za + (zb - za) * k / n), (.1, 1.0, .1), (84, 68, 50), 'wood') for k in range(n + 1)]
        return out
    def rail_z(z, xa, xb):
        out = [block(((xa + xb) / 2, .35, z), (xb - xa, .08, .05), fc, 'wood'), block(((xa + xb) / 2, .75, z), (xb - xa, .08, .05), fc, 'wood')]
        n = max(1, int((xb - xa) / 1.2)); out += [block((xa + (xb - xa) * k / n, 0, z), (.1, 1.0, .1), (84, 68, 50), 'wood') for k in range(n + 1)]
        return out
    B += rail_x(x_f, 9.6, 13.0) + rail_x(x_f, 15.0, 18.4) + rail_z(9.6, -12.6, x_f) + rail_z(18.4, -12.6, x_f) + rail_x(-12.6, 9.6, 18.4)
    x, z = MAILBOX
    B += [block((x, 0, z), (.08, 1.05, .08), (70, 56, 42), 'wood'), block((x, 1.05, z), (.36, .3, .5), (60, 76, 110), 'metal'),
          block((x + .19, 1.12, z + .12), (.02, .22, .05), (200, 40, 36), 'metal'), block((x - .19, 1.15, z), (.01, .06, .26), (20, 20, 22), 'metal')]
    return B


# ================================================================== the lighthouse
def phare_blocs(spec):
    cx, cz = LIGHTHOUSE; B = []
    B += _oct(cx, cz, 0, .45, 6.4, STONE, 'stone')
    B += [block((cx - 3.55, 0, cz), (.5, .15, 1.8), STONE_D, 'stone'), block((cx - 3.3, .15, cz), (.2, .15, 1.8), STONE_D, 'stone')]   # two steps (tops .15, .30)
    for k in range(12):                                                                       # heaved clods and torn roots: it came out of the ground
        a = k * 2 * math.pi / 12 + .3; r = 3.75 + .45 * ((k * 7) % 3) / 2
        x, z = cx + r * math.sin(a), cz + r * math.cos(a)
        if x < cx - 2.6 and abs(z - cz) < 2.0: continue
        if math.hypot(x - TRAIL[1][0], z - TRAIL[1][1]) < 1.2 or math.hypot(x - TRAIL[2][0], z - TRAIL[2][1]) < 1.2: continue
        B.append(block((x, 0, z), (.5 + .2 * (k % 2), .18 + .08 * (k % 3), .42), (64, 50, 38), 'stone'))
        if k % 3 == 0:
            horiz = abs(math.sin(a)) > .7
            B.append(block((x + .45 * math.sin(a), .04, z + .45 * math.cos(a)), (.7 if horiz else .08, .07, .08 if horiz else .7), (92, 70, 48), 'wood'))
    n = 16; y = .45; hseg = (19.65 - .45) / n
    for i in range(n):                                                                        # the shaft: red / white bands of two segments
        w = 5.0 - (5.0 - 3.2) * (i + .5) / n
        B += _oct(cx, cz, y, hseg + .002, w, RED_T if (i // 2) % 2 == 1 else WHITE_T, 'plaster')
        y += hseg
    width_at = lambda yy: 5.0 - 1.8 * (yy - .45) / 19.2
    for wy in (5.4, 9.8, 14.2):                                                               # small windows (road side and +z), rust streaks
        w = width_at(wy + .45); xf = cx - w / 2 - .02
        B += [block((xf, wy, cz), (.06, .9, .5), (22, 24, 30), 'metal'), block((xf - .02, wy + .9, cz), (.1, .08, .64), STONE, 'stone'),
              block((xf - .02, wy - .08, cz), (.1, .08, .64), STONE, 'stone'), block((xf - .005, wy - 1.0, cz + .14), (.03, .92, .06), (110, 70, 54), 'plaster')]
        B.append(block((cx, wy + 1.2, cz + width_at(wy + 1.6) / 2 + .02), (.5, .8, .06), (22, 24, 30), 'metal'))
    for k in range(14):                                                                       # ivy climbing the -x face and the -z face
        B.append(block((cx - width_at(.6 + .5 * k) / 2 - .03, .5 + .48 * k, cz - 1.0 + .22 * ((k * 5) % 5)), (.06, .52, .4 + .1 * (k % 3)), (44, 82, 42) if k % 2 else (38, 70, 36), 'fabric'))
    for k in range(9):
        B.append(block((cx + .9 - .2 * ((k * 3) % 4), .5 + .45 * k, cz - width_at(.6 + .45 * k) / 2 - .03), (.42, .48, .06), (42, 78, 40), 'fabric'))
    xd = cx - 2.5 - .02                                                                       # the metal door (face of the shaft at x 13.48)
    B += [block((xd - .03, .45, cz), (.06, 2.2, 1.1), (50, 54, 60), 'metal'),
          block((xd - .07, .45, cz - .62), (.1, 2.35, .14), IRON, 'metal'), block((xd - .07, .45, cz + .62), (.1, 2.35, .14), IRON, 'metal'),
          block((xd - .07, 2.65, cz), (.1, .16, 1.38), IRON, 'metal'), block((xd - .07, .45, cz), (.1, .05, 1.38), IRON, 'metal'),
          block((xd - .09, 1.35, cz + .36), (.05, .05, .2), (160, 150, 126), 'metal'), block((xd - .1, 1.25, cz + .44), (.04, .2, .04), (160, 150, 126), 'metal')]
    for ry in (.62, 1.5, 2.45):
        for rz in (-.44, -.15, .15, .44):
            B.append(block((xd - .07, ry, cz + rz), (.04, .04, .04), (100, 104, 112), 'metal'))
    B += [block((xd - .065, 1.02, cz), (.02, .03, 1.0), IRON_L, 'metal'), block((xd - .065, 1.95, cz), (.02, .03, 1.0), IRON_L, 'metal'),
          block((xd - .08, 2.12, cz - .2), (.02, .16, .4), (128, 110, 74), 'metal')]
    for sz in (-1, 1):                                                                        # two caged lamps either side of the door
        z = cz + sz * .95
        B += [block((xd - .12, 2.35, z), (.2, .04, .18), IRON, 'metal'), block((xd - .2, 2.1, z), (.14, .22, .14), (236, 240, 255), 'light', emissive=1.5, no_shadow=True, group='phare.lampes'),
              block((xd - .2, 2.05, z), (.18, .03, .18), IRON, 'metal'), block((xd - .2, 2.32, z), (.18, .03, .18), IRON, 'metal')]
    B += [block((cx - 1.2, .45, cz - 2.15), (.6, .9, .28), (92, 96, 100), 'metal'), block((cx - 1.2, .9, cz - 2.3), (.2, .18, .01), (230, 190, 40), 'metal'),   # electrical cabinet
          block((cx - 1.2, 1.36, cz - 2.06), (.06, 2.4, .06), (50, 50, 54), 'metal')]
    B += [block((cx - width_at(3.5) / 2 - .02, 3.4, cz + 1.2), (.03, .3, .45), (128, 110, 74), 'metal')]                                                 # a second plate
    for k in range(8):                                                                        # gallery corbels
        a = k * math.pi / 4
        B.append(block((cx + 1.75 * math.sin(a), 19.25, cz + 1.75 * math.cos(a)), (.35, .4, .35), STONE_D, 'stone'))
    B += _oct(cx, cz, 19.65, .2, 5.4, (44, 46, 50), 'metal')
    r = 2.45; rail = (30, 32, 36)
    for k in range(11):
        p = -r + k * (2 * r / 10)
        for (px, pz) in ((p, -r), (p, r), (-r, p), (r, p)):
            if abs(px) > r - .6 and abs(pz) > r - .6: continue
            B.append(block((cx + px, GALLERY_Y, cz + pz), (.05, 1.0, .05), rail, 'metal', no_shadow=True))
            if k % 2 == 0: B.append(block((cx + px, GALLERY_Y + .74, cz + pz), (.09, .05, .09), rail, 'metal', no_shadow=True))   # knobs: worked railing
    for (sx, sz, w, d) in ((0, -r, 2 * r - 1.2, .06), (0, r, 2 * r - 1.2, .06), (-r, 0, .06, 2 * r - 1.2), (r, 0, .06, 2 * r - 1.2)):
        B.append(block((cx + sx, GALLERY_Y + .98, cz + sz), (w, .06, d), rail, 'metal', no_shadow=True))
        B.append(block((cx + sx, GALLERY_Y + .5, cz + sz), (w, .04, d), rail, 'metal', no_shadow=True))
        B.append(block((cx + sx, GALLERY_Y + .12, cz + sz), (w, .03, d), rail, 'metal', no_shadow=True))
    for (sx, sz) in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
        for k in range(3):
            B.append(block((cx + sx * (r - .5 + .2 * k), GALLERY_Y + .98, cz + sz * (r - .1 - .2 * k)), (.24, .06, .24), rail, 'metal', no_shadow=True))
    L = 1.5
    B += [block((cx, GALLERY_Y, cz), (2 * L, LANTERN_FLOOR - GALLERY_Y, 2 * L), (36, 36, 40), 'metal')]
    for (sx, sz, w, d) in ((-L, 0, .1, 2 * L), (L, 0, .1, 2 * L), (0, -L, 2 * L, .1), (0, L, 2 * L, .1)):
        B.append(block((cx + sx, LANTERN_FLOOR, cz + sz), (w, .45, d), RED_T, 'plaster'))
        B.append(block((cx + sx, 22.75, cz + sz), (w, .1, d), (30, 30, 34), 'metal', no_shadow=True))
        B.append(block((cx + sx, LANTERN_FLOOR + .45, cz + sz), (w * 1.02 if w > .2 else .12, .05, d * 1.02 if d > .2 else .12), (30, 30, 34), 'metal', no_shadow=True))
    for m in (-1.1, -.45, .45, 1.1):                                                          # mullions: on the -x face the child stands between -.45 and .45
        for (px, pz) in ((-L, m), (L, m), (m, -L), (m, L)):
            B.append(block((cx + px, LANTERN_FLOOR + .45, cz + pz), (.06, 2.12, .06), (26, 26, 30), 'metal', no_shadow=True))
    for (px, pz) in ((-L, -L), (-L, L), (L, -L), (L, L)):
        B.append(block((cx + px, LANTERN_FLOOR, cz + pz), (.12, 2.65, .12), (26, 26, 30), 'metal', no_shadow=True))
    for i, w in enumerate((3.4, 2.9, 2.3, 1.6, .9)):
        B += _oct(cx, cz, 22.85 + i * .32, .32, w, (36, 38, 42) if i % 2 == 0 else (46, 48, 52), 'metal', no_shadow=True)
    B += [block((cx, 24.45, cz), (.45, .45, .45), (44, 46, 50), 'metal', no_shadow=True), block((cx, 24.9, cz), (.05, .8, .05), (64, 64, 68), 'metal', no_shadow=True),
          block((cx + .3, 24.9, cz), (.5, .03, .03), (64, 64, 68), 'metal', no_shadow=True)]
    B += [block((cx, LANTERN_FLOOR, cz), (.5, .55, .5), (62, 62, 68), 'metal', no_shadow=True)]
    lens = [block((cx, 20.75, cz), (.95, 1.3, .95), (255, 252, 240), 'light', emissive=1.7, no_shadow=True, group='lentille')]
    for k, yy in enumerate((20.8, 21.1, 21.4, 21.7, 21.95)):
        lens.append(block((cx, yy, cz), (1.08 - .04 * abs(k - 2), .07, 1.08 - .04 * abs(k - 2)), (210, 232, 255), 'light', emissive=1.6, no_shadow=True, group='lentille'))
    return B, lens


# ================================================================== the bakery (two floors)
def bakery_contour_blocks():
    """the outline of the bakery's invisible wall once it is erased: thin, pale, cold, barely glowing edges (group `boulangerie.contour`)"""
    cx, cz = BAKERY; x0, x1, z0, z1 = cx - 2.5, cx + 2.5, cz - 3.0, cz + 3.0; e = .028; col = (150, 186, 220); E = []
    kw = dict(no_shadow=True, group='boulangerie.contour')
    for (x, z) in ((x0, z0), (x0, z1), (x1, z0), (x1, z1)):
        E.append(block((x, 0, z), (e, 6.2, e), col, 'light', emissive=.17, **kw))
    E += [block((x0, 6.2, cz), (e, e, 6.0), col, 'light', emissive=.17, **kw), block((x0, .02, cz), (e, e, 6.0), col, 'light', emissive=.16, **kw),
          block((cx, 6.2, z0), (5.0, e, e), col, 'light', emissive=.18, **kw), block((cx, 6.2, z1), (5.0, e, e), col, 'light', emissive=.18, **kw),
          block((x0, 2.45, 55.0), (e, e, 2.6), col, 'light', emissive=.12, **kw), block((x0, .9, 55.0), (e, e, 2.6), col, 'light', emissive=.12, **kw)]
    return E


def boulangerie_blocs(mode, spec):
    """-> (blocks, windows, lights)"""
    if not mode: return [], [], []
    cx, cz = BAKERY; x0, x1, z0, z1 = cx - 2.5, cx + 2.5, cz - 3.0, cz + 3.0
    steps = _steps(x0 - .15, -.3, 57.5, 1.2, (.6, .45, .3), .08, (132, 126, 118), 'boulangerie', mode)
    if mode == 'effacee': return steps + bakery_contour_blocks(), [], []
    B = []; wall = (138, 126, 108); wall_up = (132, 120, 104); trim = (104, 82, 62); fw = .16
    B += [block((cx, 0, cz), (5.0, .6, 6.0), (112, 108, 102), 'stone'),
          block((cx + fw / 2, .6, cz), (5.0 - fw, 5.6, 6.0), wall, 'plaster'),                         # body behind the facade
          block((x0 + fw / 2, .6, z0 + .3), (fw, 3.0, .6), wall, 'plaster'), block((x0 + fw / 2, .6, z1 - .3), (fw, 3.0, .6), wall, 'plaster'),
          block((x0 + fw / 2, .6, 56.6), (fw, 3.0, .4), wall, 'plaster'),
          block((x0 + fw / 2, 2.45, 55.0), (fw, 1.15, 2.6), wall, 'plaster'), block((x0 + fw / 2, .6, 55.0), (fw, .3, 2.6), wall, 'plaster'),
          block((x0 + fw / 2, 2.55, 57.5), (fw, 1.05, 1.2), wall, 'plaster'),
          block((x0 + fw / 2, 3.6, cz), (fw, 2.6, 6.0), wall_up, 'plaster'),                                # upper floor facade
          block((x0 - .04, 3.55, cz), (.12, .1, 6.1), trim, 'wood')]                                       # string course between floors
    B += [block((x0 + .07, .9, 55.0), (.04, 1.55, 2.6), (120, 90, 60), 'wood'),
          block((x0 - .01, .86, 55.0), (.06, .06, 2.7), trim, 'wood'), block((x0 - .01, 2.43, 55.0), (.06, .06, 2.7), trim, 'wood'),
          block((x0 - .01, .9, 55.0), (.05, 1.55, .06), trim, 'wood'),
          block((x0 + .06, .6, 57.5), (.05, 1.95, 1.0), (92, 64, 44), 'door'), block((x0 + .02, 1.2, 57.5), (.03, 1.1, .7), (90, 70, 50), 'wood'),
          block((x0 - .01, 1.45, 57.85), (.03, .2, .04), (190, 170, 110), 'metal')]
    for k, yy in enumerate((1.25, 1.85)):                                                         # bread on shelves behind the window
        B.append(block((x0 + .15, yy, 55.0), (.1, .04, 2.4), trim, 'wood'))
        for j in range(5 + k):
            B.append(block((x0 + .15, yy + .04, 54.0 + j * .42), (.09, .1 + .04 * (j % 2), .3), (204, 144, 72), 'wood'))
    for j in range(12):                                                                           # striped awning
        B.append(block((x0 - .45, 2.55, 53.25 + j * .5), (.9, .1, .5), (182, 42, 40) if j % 2 == 0 else (238, 230, 212), 'fabric'))
    B += [block((x0 - .86, 2.42, cz), (.04, .14, 6.0), (182, 42, 40), 'fabric'), block((cx, 6.2, cz), (5.3, .2, 6.3), trim, 'wood')]
    for i in range(5):
        B.append(block((cx, 6.4 + i * .32, cz), (max(.5, 5.2 - i * 1.15), .32, 6.2), (126, 60, 46) if i % 2 == 0 else (110, 52, 42), 'wood'))
    B += [block((cx + 1.2, 6.8, cz + 2.0), (.5, 1.4, .5), (122, 94, 82), 'plaster'), block((cx + 1.2, 8.2, cz + 2.0), (.6, .1, .6), (90, 74, 66), 'plaster')]
    for z in (54.2, 57.8):                                                                        # upper windows: sills, shutters
        B += [block((x0 - .04, 4.2, z), (.1, .06, 1.0), trim, 'wood'), block((x0 - .02, 4.26, z - .62), (.04, 1.1, .2), (70, 96, 80), 'wood'),
              block((x0 - .02, 4.26, z + .62), (.04, 1.1, .2), (70, 96, 80), 'wood')]
    for z in (54.2, 57.8):                                                                        # gooseneck lamps over the sign
        B += [block((x0 - .25, 3.45, z), (.5, .04, .04), (40, 40, 44), 'metal'), block((x0 - .45, 3.3, z), (.14, .12, .14), (255, 220, 160), 'light', emissive=1.0, no_shadow=True)]
    # forecourt: display stand with baskets of bread, flower pots, slate board stand (its text is a texture box of PhareSet)
    B += [block((5.75, 0, 53.9), (.7, .75, 1.3), (110, 82, 58), 'wood'), block((5.75, .75, 53.9), (.78, .05, 1.4), (132, 100, 70), 'wood')]
    for j in range(3):
        B += [block((5.75, .8, 53.45 + j * .45), (.5, .12, .38), (150, 112, 70), 'fabric'), block((5.75, .92, 53.45 + j * .45), (.36, .08, .3), (210, 150, 80), 'wood')]
    for z in (56.55, 58.35):
        B += [block((x0 - .3, 0, z), (.35, .35, .35), (150, 84, 60), 'stone'), block((x0 - .3, .35, z), (.32, .22, .32), (54, 104, 50), 'fabric'),
              block((x0 - .3, .5, z), (.12, .08, .12), (230, 90, 110), 'fabric')]
    B += [block((5.05, 0, 59.6), (.06, .9, .06), (90, 70, 50), 'wood'), block((5.05, .6, 59.6), (.62, .8, .05), (40, 44, 42), 'wood')]   # slate board
    for b in B:
        if 'group' not in b: b['group'] = 'boulangerie'
    windows = [dict(at=(x0 - .02, 4.3, z), size=(.02, 1.0, .95), face='-x', seed=11 + k, lit=(k == 0), group='boulangerie') for k, z in enumerate((54.2, 57.8))]
    windows += [dict(at=(x0 + .04, .9, 55.0), size=(.02, 1.55, 2.6), face='-x', seed=0, lit=True, kind='boutique', group='boulangerie'),
                dict(at=(x0 + .0, 1.2, 57.5), size=(.02, 1.1, .7), face='-x', seed=1, lit=True, kind='porte', group='boulangerie')]
    lights = [((x0 - 1.7, 2.0, 55.2), (1.0, .76, .48), .48, 4.0, False, 'boulangerie'), ((x0 - .9, 3.1, 56.0), (1.0, .8, .52), .25, 2.4, False, 'boulangerie'),
              ((x0 - .6, 4.8, 54.2), (1.0, .76, .48), .5, 2.2, False, 'boulangerie')]
    return B + steps, windows, lights


# ================================================================== village houses
def maisons(spec):
    """-> (props, blocks, windows, lights, anchors)"""
    from .sets import _rot
    n = max(0, min(6, int(spec.get('maisons', 4)))); erased = set(int(i) for i in (spec.get('maisons_effacees') or []))
    props, blocks, windows, lights, anchors = [], [], [], [], {}
    cols = ((180, 164, 140), (156, 162, 166), (190, 176, 150), (166, 146, 126), (146, 156, 146), (184, 168, 154))
    roofs = ((92, 56, 48), (68, 66, 76), (100, 62, 50), (76, 62, 56), (84, 58, 52), (78, 68, 64))
    for i in range(n):
        x, z, rot = HOUSES[i]; anchors[f'maison{i}'] = (x, z); gid = f'maison{i}'
        face = 1 if rot == 3 else -1
        blocks += _steps(x + face * 2.15, face * .3, z, 1.1, (.45, .3, .15), .08, (130, 124, 116), gid, 'effacee' if i in erased else 'intacte')
        if i in erased: continue
        props.append({'type': 'house', 'at': [x, z], 'rot': rot, 'color': list(cols[i]), 'roof': list(roofs[i]), 'night': True, 'group': gid})
        for lx in (-1.6, 1.6):
            wx, wz = _rot(lx, -2.06, rot); nx, nz = _rot(0., -1., rot)
            fc = '+x' if nx > .5 else '-x' if nx < -.5 else '+z' if nz > .5 else '-z'
            size = (.02, .8, .9) if abs(nx) > .5 else (.9, .8, .02)
            windows.append(dict(at=(x + wx, 1.2, z + wz), size=size, face=fc, seed=31 + 7 * i + (lx > 0), lit=((i + (lx > 0)) % 3 != 2), group=gid))
        fx_, fz_ = _rot(0., -3.0, rot)
        lights.append(((x + fx_, 1.9, z + fz_), (1.0, .76, .46), .8, 3.4, False, gid))
        mx, mz = _rot(1.5, -3.6, rot)                                                              # mailbox by the path
        blocks += [block((x + mx, 0, z + mz), (.08, 1.0, .08), (70, 56, 42), 'wood', group=gid), block((x + mx, 1.0, z + mz), (.34, .28, .46), (110, 50, 40), 'metal', group=gid)]
    return props, blocks, windows, lights, anchors


# ================================================================== road furniture
def route_blocs(spec):
    """-> (blocks, lights, halos, texts) : edge lines, reflector posts, sodium lamps, poles and cables, guardrail, signs, milestone"""
    B, L, H, T = [], [], [], []
    for sx in (-1, 1):                                                                             # edge lines
        B.append(block((sx * 3.0, 0, 20.0), (.1, .004, 200.0), (196, 196, 186), 'stone'))
    if spec.get('lampadaires', True):
        for z in LAMPS_Z:
            x = -4.2
            B += [block((x, 0, z), (.16, .5, .16), (70, 72, 76), 'metal'), block((x, .5, z), (.12, 4.7, .12), (58, 60, 64), 'metal'),
                  block((x + .7, 5.1, z), (1.4, .1, .1), (58, 60, 64), 'metal'),
                  block((x + 1.35, 4.92, z), (.46, .16, .28), (64, 66, 70), 'metal'),
                  block((x + 1.35, 4.86, z), (.36, .06, .22), SODIUM, 'light', emissive=2.2, no_shadow=True)]
            L.append(((x + 1.35, 4.55, z), (1.0, .72, .40), 2.6, 8.5, False, None))
            H.append(dict(apex=(x + 1.35, 4.84, z), axis=(0., -1., 0.), half=40., length=4.9, col=(1.0, .72, .40), dens=1.0, R0=.18))
    poles = []
    if spec.get('poteaux', True):
        for z in POLES_Z:
            x = POLE_X; poles.append((x, z))
            B += [block((x, 0, z), (.26, 7.6, .26), (78, 62, 46), 'wood'), block((x, 6.9, z), (1.7, .12, .12), (72, 58, 44), 'wood')]
            for dx in (-.6, 0., .6):
                B.append(block((x + dx, 7.02 if dx else 7.6, z), (.07, .14, .07), (200, 204, 196), 'stone'))
            if z in (12.0, 62.0):                                                                  # a transformer on two poles
                B.append(block((x - .3, 5.6, z), (.42, .7, .42), (96, 104, 104), 'metal'))
        for (xa, za), (xb, zb) in zip(poles[:-1], poles[1:]):                                       # three sagging cables per span
            for dx, y0 in ((-.6, 7.16), (0., 7.74), (.6, 7.16)):
                n = 4
                for k in range(n):
                    t0, t1 = k / n, (k + 1) / n; tm = (t0 + t1) / 2
                    sag = .55 * 4 * tm * (1 - tm)
                    B.append(block((xa + dx, y0 - sag, za + (zb - za) * tm), (.035, .035, (zb - za) / n + .02), (24, 24, 26), 'metal', no_shadow=True))
    for z in range(-50, 100, 16):                                                                  # reflector posts on both sides
        for sx in (-1, 1):
            x = sx * 4.0
            if any(abs(z - zz) < 2.0 for zz in LAMPS_Z) and sx < 0: continue
            if sx < 0 and 9.0 < z < 19.0: continue                                                 # the cabin's path and mailbox
            if sx > 0 and 51.0 < z < 61.0: continue                                                # the bakery's forecourt
            if any(abs(z - p[1]) < 2.0 for p in (SIGN_CURVE, SIGN_VILLAGE, BORNE)) and sx * p_side(z) > 0: continue
            B += [block((x, 0, z), (.12, 1.0, .12), (226, 226, 220), 'plaster'), block((x, .7, z), (.125, .16, .125), (30, 30, 32), 'plaster'),
                  block((x, .74, z - .066), (.06, .1, .01), (255, 150, 40) if sx > 0 else (240, 240, 230), 'light', emissive=.55, no_shadow=True)]
    for z in range(-50, -23, 2):                                                                   # guardrail on the left (a ditch)
        B.append(block((-4.6, 0, z), (.1, .7, .1), (120, 124, 128), 'metal'))
    B += [block((-4.53, .42, -37.0), (.04, .3, 26.2), (150, 154, 158), 'metal')]
    if spec.get('panneaux', True):
        # curve warning sign (stepped red triangle with a white field and a black bend), facing -z
        x, z = SIGN_CURVE
        B.append(block((x, 0, z + .02), (.06, 2.0, .06), (120, 124, 128), 'metal'))
        for k in range(7):
            w = .9 * (1 - k / 7.)
            B.append(block((x, 2.0 + k * .1, z), (w, .1, .03), (196, 30, 30), 'plaster'))
            if 1 <= k <= 4: B.append(block((x, 2.0 + k * .1 + .02, z - .016), (max(.04, w - .2), .07, .005), (236, 236, 230), 'plaster'))
        for (dx, dy) in ((-.08, 2.13), (-.05, 2.2), (0., 2.27), (.05, 2.34)):
            B.append(block((x + dx, dy, z - .02), (.05, .07, .005), (20, 20, 22), 'plaster'))
        # village entry sign (texture added by PhareSet), two posts
        x, z = SIGN_VILLAGE
        B += [block((x - .4, 0, z + .02), (.06, 2.0, .06), (120, 124, 128), 'metal'), block((x + .4, 0, z + .02), (.06, 2.0, .06), (120, 124, 128), 'metal'),
              block((x, 1.45, z + .03), (1.06, .6, .03), (150, 154, 158), 'metal')]
        nm = spec.get('village', ['SAINT-ALBAN', 'DES-PINS'])
        T.append(dict(kind='village', at=(x, 1.48, z - .002), size=(1.0, .54, .02), face='-z', lines=[str(l)[:12] for l in (nm if isinstance(nm, list) else [nm])]))
        # milestone
        x, z = BORNE
        B += [block((x, 0, z), (.34, .55, .2), (226, 226, 220), 'plaster'), block((x, .55, z), (.34, .2, .2), (196, 36, 32), 'plaster')]
        T.append(dict(kind='borne', at=(x, .14, z - .105), size=(.3, .32, .01), face='-z', lines=[str(spec.get('borne', 'D 47'))[:6]]))
    return B, L, H, T


def p_side(z):
    """the side of the road a sign stands on at z (+1 right, -1 left, 0 none)"""
    for (x, zz) in (SIGN_CURVE, SIGN_VILLAGE, BORNE):
        if abs(z - zz) < 2.0: return 1 if x > 0 else -1
    return 0


def traces_blocs():
    """a child's wet sneaker prints from the foot of the door towards the pines (alternating left / right), each print three small blocks along its heading"""
    B = []; stride = .5; side = 1; acc = 0.
    for (ax, az), (bx, bz) in zip(TRAIL[:-1], TRAIL[1:]):
        L = math.hypot(bx - ax, bz - az); dx, dz = (bx - ax) / L, (bz - az) / L; s = acc
        while s < L:
            px, pz = ax + dx * s, az + dz * s
            ox, oz = -dz * .08 * side, dx * .08 * side
            for off, sz in ((-.055, .085), (.065, .1)):
                B.append(block((px + ox + dx * off, .002, pz + oz + dz * off), (sz, .006, sz), (14, 14, 18), 'stone', reflect=.6))
            side = -side; s += stride
        acc = s - L
    return B


# ================================================================== forest and undergrowth (no overlap: trees, road, buildings, clearing)
def _near_trail(x, z, d):
    for (ax, az), (bx, bz) in zip(TRAIL[:-1], TRAIL[1:]):
        vx, vz = bx - ax, bz - az; L2 = vx * vx + vz * vz
        t = max(0., min(1., ((x - ax) * vx + (z - az) * vz) / L2))
        if (x - ax - t * vx) ** 2 + (z - az - t * vz) ** 2 < d * d: return True
    return False


def obstacles(spec):
    """rects (x0, z0, x1, z1, name) and circles (x, z, r, name) that no tree and no prop may touch"""
    R = [(-4.3, -80., 4.3, 120., 'route'), (4.3, -80., 6.5, 120., 'ligne electrique')]
    if spec.get('cabane', 'intacte'): R.append((-12.8, 9.4, -4.75, 18.6, 'cabane'))
    if spec.get('boulangerie', 'intacte'): R.append((4.3, 52.4, 11.9, 60.1, 'boulangerie'))
    for i in range(max(0, min(6, int(spec.get('maisons', 4))))):
        x, z, _ = HOUSES[i]; R.append((x - 3.6, z - 3.0, x + 3.6, z + 3.0, f'maison{i}'))
    R.append((-4.9, -51., -4.3, -23., 'glissiere'))
    ma = maison_alma_spec(spec)
    if ma: R.append((4.3, ma['z'] - 7.5, 12.8, ma['z'] + 3.6, 'maison_alma'))
    Cc = [(LIGHTHOUSE[0], LIGHTHOUSE[1], 7.5, 'clairiere')]
    for (a_, b_, w_) in VIEW_LANES: R.append(('lane', a_, b_, w_, 'vue'))
    for z in POLES_Z: Cc.append((POLE_X, z, 1.1, 'poteau'))
    for z in LAMPS_Z: Cc.append((-4.2, z, .5, 'lampadaire'))
    for (x, z) in (SIGN_CURVE, SIGN_VILLAGE, BORNE, MAILBOX): Cc.append((x, z, .7, 'panneau'))
    return R, Cc


def _seg_d(x, z, a, b):
    vx, vz = b[0] - a[0], b[1] - a[1]; t = max(0., min(1., ((x - a[0]) * vx + (z - a[1]) * vz) / (vx * vx + vz * vz)))
    return math.hypot(x - a[0] - t * vx, z - a[1] - t * vz)


def _blocked(x, z, r, R, Cc, trail=1.3):
    for o in R:
        if o[0] == 'lane':
            if _seg_d(x, z, o[1], o[2]) < o[3] + r: return True
        elif o[0] - r <= x <= o[2] + r and o[1] - r <= z <= o[3] + r: return True
    if any((x - cx) ** 2 + (z - cz) ** 2 < (cr + r) ** 2 for cx, cz, cr, _ in Cc): return True
    return _near_trail(x, z, trail + r * .2)


def _pine(x, z, h, k, far=False):
    col = PINE_COLS[k % len(PINE_COLS)]; trunk = (64, 48, 36)
    if far:                                                                                        # a cheap silhouette far from the road
        return [block((x, 0, z), (.34, h * .3, .34), trunk, 'wood'), block((x, h * .22, z), (h * .3, h * .74, h * .3), col, 'fabric')]
    B = [block((x, 0, z), (.3, h * .38, .3), trunk, 'wood')]
    for i in range(3):
        w = h * .32 * (1 - i * .3); y = h * .26 + i * h * .21
        c = tuple(min(255, int(v * (1 + .08 * i))) for v in col)
        ox = .06 * ((k + i) % 3 - 1); oz = .06 * ((k * 3 + i) % 3 - 1)
        B.append(block((x + ox, y, z + oz), (w, h * .25, w), c, 'fabric'))
    B.append(block((x, h * .89, z), (.3, h * .13, .3), col, 'fabric'))
    return B


def pine_radius(h, far=False): return (h * .3 if far else h * .32) / 2 + .05


def foret(spec):
    """deterministic forest -> (blocks, props, trees [(x, z, r, h, far)], logs) ; no canopy over the road, a building, the clearing or another canopy"""
    R, Cc = obstacles(spec)
    rng = np.random.default_rng(int(spec.get('seed', 7)) * 131 + 17)
    cx, cz = LIGHTHOUSE
    trees = []
    def ok(x, z, r):
        if _blocked(x, z, r, R, Cc): return False
        return all((x - tx) ** 2 + (z - tz) ** 2 >= (r + tr) ** 2 for tx, tz, tr, _, _ in trees)
    for (x, z, h) in ((23.4, 21.2, 10.5), (24.8, 25.0, 9.5), (27.8, 21.6, 11.0), (21.0, 22.2, 8.5)):     # pines framing the end of the trail
        r = pine_radius(h)
        if ok(x, z, r): trees.append((x, z, r, h, False))
    for (area, n, far) in (((-27, -55, 34, 108), 230, False), ((-50, -70, 56, 125), 120, True)):
        tries = 0; m = 0
        while m < n and tries < n * 40:
            tries += 1; x = float(rng.uniform(area[0], area[2])); z = float(rng.uniform(area[1], area[3]))
            near = abs(x) - 4.3 <= 21 or (x - cx) ** 2 + (z - cz) ** 2 <= 23 ** 2
            if far == near: continue
            h = float(rng.uniform(7.0, 12.5)) if not far else float(rng.uniform(10., 15.))
            r = pine_radius(h, far); x, z, h = round(x, 2), round(z, 2), round(h, 2)
            if not ok(x, z, r): continue
            trees.append((x, z, r, h, far)); m += 1
    B = []
    for k, (x, z, r, h, far) in enumerate(trees): B += _pine(x, z, h, k, far)
    # undergrowth: rocks, ferns, stumps, bushes, boulders, fallen trunks ; never on a trunk, the road, a building or a footprint
    props = []; logs = []; sm = np.random.default_rng(int(spec.get('seed', 7)) * 7 + 3)
    kinds = (('rock', .45), ('fern', .35), ('stump', .3), ('bush', .55), ('fern', .35), ('rock', .45), ('boulder', 1.0), ('fern', .35))
    placed = []
    for j in range(260):
        if len(placed) >= 120: break
        x = float(sm.uniform(-24, 30)); z = float(sm.uniform(-40, 104))
        kind, r = kinds[j % len(kinds)]
        if _blocked(x, z, r, R, Cc, trail=.9): continue
        if any((x - tx) ** 2 + (z - tz) ** 2 < (.25 + r) ** 2 for tx, tz, _, _, _ in trees): continue
        if any((x - px) ** 2 + (z - pz) ** 2 < (r + pr + .1) ** 2 for px, pz, pr in placed): continue
        placed.append((x, z, r)); sz = round(.75 + .4 * float(sm.random()), 2)
        if kind == 'fern':                                                                         # a fern: two crossed fronds and a heart
            g = (40, 86, 46) if j % 2 else (34, 76, 42)
            B += [block((x, 0, z), (.7 * sz, .22 * sz, .18 * sz), g, 'fabric'), block((x, 0, z), (.18 * sz, .26 * sz, .7 * sz), g, 'fabric'),
                  block((x, .1 * sz, z), (.32 * sz, .26 * sz, .32 * sz), tuple(int(v * 1.15) for v in g), 'fabric')]
            continue
        p = {'type': kind, 'at': [round(x, 2), round(z, 2)], 'rot': j % 4, 'size': sz}
        if kind == 'bush': p['color'] = [34, 66, 38]
        props.append(p)
    for j in range(40):                                                                            # fallen trunks (along x or z)
        if len(logs) >= 9: break
        x = float(sm.uniform(-22, 28)); z = float(sm.uniform(-30, 100)); along_x = j % 2 == 0; Lg = float(sm.uniform(2.5, 4.5))
        hx, hz = (Lg / 2 + .2, .35) if along_x else (.35, Lg / 2 + .2)
        if _blocked(x, z, max(hx, hz), R, Cc, trail=1.0): continue
        if any((x - ccx) ** 2 + (z - ccz) ** 2 < (cr + max(hx, hz)) ** 2 for ccx, ccz, cr, _ in Cc): continue
        if any(abs(x - tx) < hx + .25 and abs(z - tz) < hz + .25 for tx, tz, _, _, _ in trees): continue
        if any(abs(x - px) < hx + pr and abs(z - pz) < hz + pr for px, pz, pr in placed): continue
        if _near_trail(x, z, 1.0 + max(hx, hz)): continue
        logs.append((x, z, hx, hz)); placed.append((x, z, max(hx, hz)))
        s = (Lg, .42, .42) if along_x else (.42, .42, Lg)
        B += [block((x, 0, z), s, (78, 58, 42), 'wood'), block((x + (Lg / 2 if along_x else 0), .05, z + (0 if along_x else Lg / 2)), (.03 if along_x else .34, .32, .34 if along_x else .03), (150, 120, 84), 'wood'),
              block((x - (Lg * .2 if along_x else 0), .42, z - (0 if along_x else Lg * .2)), (.5 if along_x else .3, .12, .3 if along_x else .5), (52, 84, 46), 'fabric')]
    return B, props, trees, logs


# ================================================================== the place
def phare_foret(spec):
    from .places import _base
    spec = spec or {}
    cab = spec.get('cabane', 'intacte'); bak = spec.get('boulangerie', 'intacte')
    zones = [{'rect': [-60, -90, -8, 130], 'ground': 'moss'}, {'rect': [8, -90, 60, 130], 'ground': 'moss'}]
    zones += [{'circle': [x, z, r], 'ground': 'leaves'} for (x, z, r) in ((-14, 4, 4.5), (-17, 30, 6.), (-12, 52, 4.), (20, 6, 5.), (27, 44, 5.5), (-20, 80, 6.), (22, 82, 5.))]
    zones += [{'rect': [-4.3, -90, -3.2, 130], 'ground': 'dirt'}, {'rect': [3.2, -90, 4.3, 130], 'ground': 'dirt'}, {'rect': [-3.2, -90, 3.2, 130], 'ground': 'road'},
              {'circle': [LIGHTHOUSE[0], LIGHTHOUSE[1], 7.2], 'ground': 'dirt'},
              {'path': [list(p) for p in TRAIL] + [[28.0, 21.0]], 'width': 1.3, 'ground': 'dirt'},
              {'path': [[-5.1, 14.0], [-4.3, 14.0]], 'width': 1.4, 'ground': 'dirt'},
              {'rect': [4.3, 52.6, 6.5, 59.8], 'ground': 'cobble'}]
    o = _base(dict(spec), outdoor=True, sky='night', stars=True, ground='grass', backdrop=['hills', {'type': 'forest', 'height': 4.2}, 'forest'],
              fog=.018, ambience='night', fill=.55, clouds=.42, zones=zones)
    o['sky'] = 'night'; o['stars'] = True
    o['ambient'] = tuple(spec.get('ambient', (.29, .32, .46)))
    o['fog_color'] = tuple(spec.get('fog_color', (.15, .19, .31)))
    if 'fill' not in spec: o['fill'] = .55
    B = []; lights = []; windows = []; texts = []; halos = []
    ma = maison_alma_spec(spec)
    if ma and ma.get('voiture', True):                                                             # Alma's car parked beside her house
        v0 = spec.get('voiture', True)
        if v0 is True or (isinstance(v0, dict) and 'x' not in v0 and 'z' not in v0):
            spec = dict(spec, voiture=dict(v0 if isinstance(v0, dict) else {}, x=5.5, z=ma['z'] - 6.0, cap=0))
    dead = str(spec.get('lanterne', 'allumee')) == 'eteinte'
    car = car_spec(spec)
    if car:
        B += _car_world(voiture_blocs(car['couleur'], car.get('phares', True), bool(car.get('ecran')), bool(car.get('radio'))), car['x'], car['z'], car['cap'])
        sgn = -1 if int(round(car['cap'])) % 360 == 180 else 1
        lights += [((car['x'] - .1, 1.05, car['z'] + sgn * .45), (.6, .74, 1.0), .95, 1.6, False, None), ((car['x'], .7, car['z'] - sgn * 2.7), (1.0, .12, .08), .8, 2.4, False, None)]
        if car.get('phares', True):
            for sx in (-1, 1):
                halos.append(dict(apex=(car['x'] + sx * .64 * sgn, .69, car['z'] + sgn * 2.26), axis=(0., -.07, sgn * 1.), half=17., length=17., col=(1.0, .95, .82), dens=.45, R0=.08))
    cb, cw, cl = cabane_blocs(cab); B += cb; windows += cw; lights += cl
    B += enclos_blocs()
    tower, lens = phare_blocs(spec)
    if dead:                                                                                       # dead forever: black lens, door lamps off
        lens = [dict(b, emissive=0., material='metal', color=[int(c * .16) for c in b['color']]) for b in lens]
        tower = [dict(b, emissive=.05) if b.get('material') == 'light' else b for b in tower]
    B += tower + lens
    if not dead: lights += [((LIGHTHOUSE[0] - 3.6, 2.2, LIGHTHOUSE[1] + sz * .95), (.85, .9, 1.0), .5, 3.2, False, 'phare.lampes') for sz in (-1, 1)]
    bb, bw, bl = boulangerie_blocs(bak, spec); B += bb; windows += bw; lights += bl
    hp, hb, hw, hl, ha = maisons(spec); B += hb; windows += hw; lights += hl
    rb, rl, rh, rt = route_blocs(spec); B += rb; lights += rl; halos += rh; texts += rt
    if spec.get('traces', True): B += traces_blocs()
    if ma:
        mb, mw, ml, mA = maison_alma_blocs(ma); B += mb; windows += mw; lights += ml
    mt = spec.get('mains_tenues')
    if mt:
        for m_ in (mt if isinstance(mt, list) else [mt]):
            m_ = dict(m_ if isinstance(m_, dict) else {})
            m_.setdefault('cap', 180.)
            B += main_tenue_blocs(m_.pop('x', 6.35), m_.pop('y', 1.62), m_.pop('z', (ma or {}).get('z', 112.) - .5), group='mains_tenues', **m_)
    mv = spec.get('main_vitre')
    if mv:
        for m in (mv if isinstance(mv, list) else [mv]):
            m = dict(MAIN_VITRE, **(m if isinstance(m, dict) else {}))
            B += main_plaquee_blocs(m.pop('x'), m.pop('y'), m.pop('z'), group='main_vitre', **m)
    fb, fp, trees, logs = foret(spec)
    B += fb
    o['blocks'] = list(spec.get('blocks', [])) + B
    if bak == 'intacte':                                                                           # bench and bicycle in front of the bakery
        hp = hp + [{'type': 'bench', 'at': [5.0, 55.6], 'rot': 1, 'group': 'boulangerie'}, {'type': 'bicycle', 'at': [4.75, 59.0], 'rot': 0, 'color': [150, 40, 40], 'group': 'boulangerie'}]
    o['props'] = o['props'] + hp + fp
    o['_phare'] = dict(lights=lights, windows=windows, texts=texts, halos=halos, car=car, cabane=cab, boulangerie=bak,
                       enseigne=str(spec.get('enseigne', 'BOULANGERIE'))[:12], plaque=spec.get('plaque'), appoint=spec.get('lanterne_appoint', True),
                       brume_basse=float(spec.get('brume_basse', 1.0)), lune=float(spec.get('lune', 2.4)), trees=trees, logs=logs, lanterne='eteinte' if dead else 'allumee',
                       faisceau=(dict(DEFAULT_BEAM, **(spec.get('faisceau') or {})) if (spec.get('faisceau', True) is not False and not dead) else None))
    if dead: o['_phare']['appoint'] = False
    cxr, czr = (car['x'], car['z']) if car else CAR
    a = {'start': (cxr, czr - 7.0), 'route': (0., 10.), 'voiture': (cxr, czr), 'voiture.conducteur': (cxr - .4, 0., czr + .30),
         'voiture.passager': (cxr + .4, 0., czr + .30), 'voiture.arriere': (cxr, 0., czr - .9), 'voiture.tableau': (cxr, .79, czr + .6),
         'voiture.plancher': (cxr - .4, .31, czr + .3), 'voiture.devant': (cxr, czr + 3.4), 'voiture.portiere': (cxr - 1.7, czr + .2),
         'cabane': CABIN, 'cabane.marches': (CABIN[0] + 3.45, CABIN[1]), 'cabane.devant': (CABIN[0] + 4.4, CABIN[1]),
         'phare': LIGHTHOUSE, 'phare.pied': (LIGHTHOUSE[0] - 4.3, LIGHTHOUSE[1]), 'phare.porte': (LIGHTHOUSE[0] - 2.95, .45, LIGHTHOUSE[1]),
         'phare.vitre': (LIGHTHOUSE[0], LANTERN_FLOOR, LIGHTHOUSE[1] - 1.15), 'phare.vitre_route': (LIGHTHOUSE[0] - 1.15, LANTERN_FLOOR, LIGHTHOUSE[1]),
         'phare.lentille': (LIGHTHOUSE[0], LENS_Y, LIGHTHOUSE[1]),
         'phare.galerie': (LIGHTHOUSE[0] - 2.1, GALLERY_Y, LIGHTHOUSE[1]),
         'boulangerie': BAKERY, 'boulangerie.seuil': (BAKERY[0] - 3.55, 57.5), 'boulangerie.mur': (BAKERY[0] - 2.9, 55.0), 'boulangerie.vitrine': (BAKERY[0] - 2.5, 55.0),
         'traces.debut': TRAIL[0], 'traces.fin': TRAIL[-1], 'foret': (-12., 30.), 'clairiere': (11., 28.)}
    a.update(ha)
    if ma: a.update(mA)
    o['anchors'] = dict(o.get('anchors') or {}, **a)
    return o


def register(PLACES):
    """adds the place `phare_foret` (and the shot effect `effacement`) ; nothing is replaced"""
    from . import effacement as _EF                       # noqa: F401  (registers the effect)
    if 'phare_foret' not in PLACES: PLACES['phare_foret'] = phare_foret


# ================================================================== textures (windows with curtains, signs, the dashboard screen)
def _window_tex(seed, lit=True, w=24, h=22):
    rng = np.random.default_rng(seed)
    yy = np.arange(h, dtype=np.float32)[:, None] / h; img = np.zeros((h, w, 4), np.uint8); img[..., 3] = 255
    if lit:
        top = np.array([255, 206, 128], np.float32); bot = np.array([214, 136, 70], np.float32)
        base = top[None, None] * (1 - yy[..., None]) + bot[None, None] * yy[..., None]
    else:
        base = np.broadcast_to(np.array([30, 38, 62], np.float32), (h, w, 3)).copy()
        base[:, :] += (np.arange(w)[None, :, None] * .6).astype(np.float32)
    img[..., :3] = np.clip(np.broadcast_to(base, (h, w, 3)), 0, 255).astype(np.uint8)
    kind = int(rng.integers(0, 3))                                                    # what stands behind the glass: a lamp, a plant, a shelf
    dark = (110, 64, 40) if lit else (18, 22, 36)
    if kind == 0:
        img[h - 8:h - 2, w // 2 - 1:w // 2 + 1, :3] = dark; img[h - 12:h - 8, w // 2 - 4:w // 2 + 4, :3] = (255, 236, 180) if lit else dark
    elif kind == 1:
        img[h - 5:h - 1, w // 2 - 3:w // 2 + 3, :3] = dark; img[h - 11:h - 5, w // 2 - 5:w // 2 + 5, :3] = (70, 96, 50) if lit else (20, 30, 30)
    else:
        img[h // 2:h // 2 + 1, 3:w - 3, :3] = dark; img[h // 2 - 4:h // 2, 5:9, :3] = dark; img[h // 2 - 3:h // 2, 12:15, :3] = dark
    cl = (170, 74, 52) if lit else (60, 46, 52); cl2 = tuple(int(c * .7) for c in cl)
    lw = int(rng.integers(5, 8)); rw = int(rng.integers(4, 7))
    for x in range(lw): img[1:h - 1, x, :3] = cl if x % 2 == 0 else cl2
    for x in range(w - rw, w): img[1:h - 1, x, :3] = cl if x % 2 == 0 else cl2
    img[1:3, :, :3] = cl2                                                             # valance
    fr = (64, 48, 36); img[0, :, :3] = fr; img[-1, :, :3] = fr; img[:, 0, :3] = fr; img[:, -1, :3] = fr
    img[:, w // 2, :3] = fr; img[int(h * .45), :, :3] = fr
    return img


def _shop_tex(kind):
    """the lit inside of the bakery seen through its window (shelves of bread, counter, baskets) or through its glazed door"""
    if kind == 'porte':
        w, h = 14, 22; img = np.zeros((h, w, 4), np.uint8); img[..., 3] = 255
        img[..., :3] = (200, 140, 80); img[2:h - 2, 2:w - 2, :3] = (226, 168, 100)
        img[:, 0, :3] = img[:, -1, :3] = (60, 44, 32); img[0, :, :3] = img[-1, :, :3] = (60, 44, 32); img[h // 2, :, :3] = (60, 44, 32)
        img[4:7, 4:10, :3] = (90, 60, 40)                                                # the opening hours card
        return img
    w, h = 64, 38; img = np.zeros((h, w, 4), np.uint8); img[..., 3] = 255
    yy = np.arange(h)[:, None] / h
    img[..., 0] = (222 - 40 * yy).astype(np.uint8); img[..., 1] = (164 - 46 * yy).astype(np.uint8); img[..., 2] = (96 - 34 * yy).astype(np.uint8)
    for k, y in enumerate((10, 20)):                                                     # two shelves of loaves, baguettes standing in a basket
        img[y, 2:w - 2, :3] = (96, 66, 42)
        for j in range(7 - k):
            x = 4 + j * 8 + 2 * k; img[y - 4:y, x:x + 5, :3] = (186, 116, 52) if (j + k) % 2 else (204, 134, 62)
            img[y - 4, x + 1:x + 4, :3] = (220, 160, 90)
    for j in range(5): img[22:31, 50 + j * 2, :3] = (196, 128, 60)
    img[26:h, 6:44, :3] = (128, 92, 62); img[25, 6:44, :3] = (170, 130, 90)              # the counter, the till
    img[21:25, 34:40, :3] = (60, 60, 66); img[20, 35:39, :3] = (120, 200, 140)
    img[:, 0, :3] = img[:, -1, :3] = (70, 50, 36); img[0, :, :3] = img[-1, :, :3] = (70, 50, 36)
    return img


def _sign_tex(kind, lines):
    from PIL import Image, ImageDraw, ImageFont
    from ...paths import FONT_PIXEL
    f = ImageFont.truetype(FONT_PIXEL, 8)
    if kind == 'village':
        W_, H_ = 80, 40; im = Image.new('RGBA', (W_, H_), (238, 238, 232, 255)); d = ImageDraw.Draw(im); d.fontmode = '1'
        d.rectangle([1, 1, W_ - 2, H_ - 2], outline=(200, 30, 30, 255), width=3)
        y = (H_ - len(lines) * 11) // 2 + 1
        for l in lines:
            tw = d.textlength(l, font=f); d.text(((W_ - tw) / 2, y), l, font=f, fill=(16, 16, 18, 255)); y += 11
        return np.array(im)
    if kind == 'borne':
        W_, H_ = 24, 26; im = Image.new('RGBA', (W_, H_), (232, 232, 226, 255)); d = ImageDraw.Draw(im); d.fontmode = '1'
        tw = d.textlength(lines[0], font=f); d.text(((W_ - tw) / 2, 4), lines[0], font=f, fill=(16, 16, 18, 255))
        return np.array(im)
    if kind == 'ardoise':
        W_, H_ = 40, 52; im = Image.new('RGBA', (W_, H_), (36, 40, 38, 255)); d = ImageDraw.Draw(im); d.fontmode = '1'
        d.rectangle([0, 0, W_ - 1, H_ - 1], outline=(120, 92, 62, 255), width=2)
        y = 6
        for i, l in enumerate(lines):
            tw = d.textlength(l, font=f); d.text(((W_ - tw) / 2, y), l, font=f, fill=(236, 236, 226, 255) if i < 2 else (230, 200, 120, 255)); y += 12
        return np.array(im)
    if kind == 'enseigne':
        W_, H_ = 112, 18; im = Image.new('RGBA', (W_, H_), (46, 30, 24, 255)); d = ImageDraw.Draw(im); d.fontmode = '1'
        d.rectangle([0, 0, W_ - 1, H_ - 1], outline=(150, 118, 70, 255), width=1)
        tw = d.textlength(lines[0], font=f); d.text(((W_ - tw) / 2, 5), lines[0], font=f, fill=(250, 222, 150, 255))
        return np.array(im)
    W_, H_ = 40, 16; im = Image.new('RGBA', (W_, H_), (150, 132, 90, 255)); d = ImageDraw.Draw(im); d.fontmode = '1'           # plaque
    tw = d.textlength(lines[0], font=f); d.text(((W_ - tw) / 2, 4), lines[0], font=f, fill=(40, 34, 24, 255))
    return np.array(im)


def _tex_box(at, size, face, img, glow, bg=(20, 20, 20)):
    """a thin box centred on `at` (x, y bottom, z) with an image on one face"""
    from .r3d import Box
    x, y, z = at; w, h, d = size
    return Box([x - w / 2, y, z - d / 2], [x + w / 2, y + h, z + d / 2], tuple(bg), tex={face: img}, texemis=glow, cast=False)


def _screen_tex(lines):
    """the dashboard screen: a message card (contact bar, bubble with the text)"""
    from PIL import Image, ImageDraw, ImageFont
    from ...paths import FONT_PIXEL
    W_, H_ = 132, 80
    im = Image.new('RGBA', (W_, H_), (10, 16, 30, 255)); d = ImageDraw.Draw(im); d.fontmode = '1'
    f = ImageFont.truetype(FONT_PIXEL, 8)
    lines = [str(l) for l in (lines or [])]
    d.rectangle([0, 0, W_, 14], fill=(30, 44, 70, 255)); d.ellipse([4, 2, 14, 12], fill=(120, 170, 120, 255))
    for ox in (0, 1): d.text((19 + ox, 3), lines[0] if lines else '', font=f, fill=(236, 240, 250, 255)); d.text((W_ - 28, 3), 'SMS', font=f, fill=(150, 170, 200, 255))
    body = lines[1:]
    if body:
        bh = len(body) * 11 + 8; d.rounded_rectangle([5, 19, W_ - 6, min(H_ - 3, 19 + bh)], 4, fill=(22, 32, 58, 255))
        for i, l in enumerate(body):                                                       # bold: the PS1 dither eats one-pixel strokes
            for ox in (0, 1): d.text((10 + ox, 23 + i * 11), l[:20], font=f, fill=(214, 224, 240, 255))
    return np.array(im)


def _radio_tex():
    """the car radio's dial: amber band with a frequency scale and a red needle"""
    W_, H_ = 28, 10
    img = np.zeros((H_, W_, 4), np.uint8); img[..., 3] = 255; img[..., :3] = (40, 24, 8)
    img[2:8, 1:W_ - 1, :3] = (230, 150, 50)
    for x in range(3, W_ - 2, 3): img[2:4, x, :3] = (60, 30, 10)
    img[1:9, 17, :3] = (255, 40, 30)
    return img


def night_sky(spec, sun):
    """the clear deep-blue night of the place: moonlit clouds, a moon with its halo, stars, the backdrop layers"""
    from . import world as W
    W.PALETTES.setdefault('nuit_claire', dict(NIGHT_SKY))
    base = W.make_sky(dict(spec, sky='nuit_claire', stars=True), sun)
    moon = np.array(NIGHT_SKY['moon'], np.float32)
    def fn(D):
        D = np.asarray(D, np.float32); col = base(D); cm = D @ MOON_DIR
        return col + (.55 * np.exp((cm - 1) * 900) + .16 * np.exp((cm - 1) * 60) + .05 * np.exp((cm - 1) * 8))[:, None] * moon[None]
    return fn


# ================================================================== the volumes drawn after the ray tracing (PS1 pass of the place)
def _beam_state(cfg, state, u, g):
    """the beam of this frame from the place defaults and the shot state -> None (off) or dict"""
    from .frame import val
    if cfg is None and 'faisceau' not in state: return None
    cfg = dict(DEFAULT_BEAM, **(cfg or {}))
    on = state.get('faisceau', 1)
    on = float(val(on, u, 1.) if isinstance(on, (list, tuple)) else (1. if on is True else 0. if on is False else on))
    if on <= 1e-3: return None
    num = lambda k, d: float(val(state.get('faisceau_' + k, cfg.get(k, d)), u, d))
    ang = num('angle', -140.) + num('vitesse', 0.) * float(g)
    tilt = num('pente', 8.); half = max(1., num('largeur', 6.))
    col = state.get('faisceau_couleur', cfg.get('couleur', 'blanc'))
    col = tuple(float(c) for c in col) if isinstance(col, (list, tuple)) else BEAM_COLORS.get(str(col), BEAM_COLORS['blanc'])
    dbl = bool(state.get('faisceau_double', cfg.get('double', False)))
    dirs = []
    for a in ([ang, ang + 180.] if dbl else [ang]):
        r, t = math.radians(a), math.radians(tilt)
        dirs.append(np.array([math.sin(r) * math.cos(t), -math.sin(t), math.cos(r) * math.cos(t)], np.float32))
    return dict(on=on, dirs=dirs, half=half, col=np.array(col, np.float32), brume=num('brume', 1.0) * float(cfg.get('force', 1.)),
                origin=np.array([LIGHTHOUSE[0], LENS_Y, LIGHTHOUSE[1]], np.float32))


def _basis(a):
    up = np.array([0., 1., 0.], np.float32)
    if abs(float(a[1])) > .95: up = np.array([1., 0., 0.], np.float32)
    r = np.cross(up, a); r /= (np.linalg.norm(r) + 1e-9); u = np.cross(a, r)
    return r.astype(np.float32), u.astype(np.float32)


def _march(O, D, idx, s0, s1, apex, axis, half, R0, S, jit, fall_len, shadow=None):
    """ray march of a cone (apex, axis, half-angle) for the rays `idx` between s0 and s1 -> accumulated density"""
    tan_h = math.tan(math.radians(half)); r_, u_ = _basis(axis)
    Dd = D[idx]; ds = (s1 - s0) / S; acc = np.zeros(len(idx), np.float32); jj = jit[idx]
    for i in range(S):
        s = s0 + (i + jj) * ds
        v = O[None] + Dd * s[:, None] - apex[None]
        al = v @ axis
        px = v @ r_; py = v @ u_
        rad = R0 + np.maximum(al, 0.) * tan_h
        prof = np.clip(1. - np.sqrt(px * px + py * py) / rad, 0., 1.) ** 1.6 * (al > 0)
        if not prof.any(): continue
        w = prof * (1. / (1. + al / fall_len)) * (1. + 1.4 * np.exp(-al / 2.5))
        if shadow is not None:
            depth, M, T = shadow
            alc = np.maximum(al, .05)
            ix = np.clip(((px / alc) / T * .5 + .5) * (M - 1) + .5, 0, M - 1).astype(np.int32)
            iy = np.clip(((py / alc) / T * .5 + .5) * (M - 1) + .5, 0, M - 1).astype(np.int32)
            w = w * (np.sqrt((v * v).sum(1)) < depth[iy, ix] + .2)
        acc += w * ds
    return acc


def place_post(img, cam, sc, beam, halos, mist):
    """the place's pass after the ray tracing: the turning beam (shadow-mapped volume), lamp and headlight cones in the haze, the low mist,
    the lens flare and the dazzle of the beam sweeping over the camera. Deterministic (dither = Bayer matrix of the engine)."""
    from . import r3d
    RW, RH = r3d.RW, r3d.RH; N = RW * RH
    pos, yaw, pitch, roll, fov = cam
    O = np.asarray(pos, np.float32); D = r3d.cam_dirs(yaw, pitch, roll, fov)
    aux = r3d.LAST_AUX
    th = aux[1] if aux is not None and len(aux[1]) == N else np.full(N, np.inf, np.float32)
    th = np.where(np.isfinite(th), th, 400.).astype(np.float32)
    jit = r3d.BAYER_T.ravel().astype(np.float32)
    out = img.reshape(-1, 3).astype(np.float32)
    # 1. low mist between the trunks: exponential height fog, integrated exactly along each ray
    if mist > 0:
        Hm = 1.15; dy = D[:, 1]; tt = np.minimum(th, 160.)
        e0 = math.exp(-float(O[1]) / Hm)
        with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
            integ = np.where(np.abs(dy) > 1e-4, e0 * Hm / dy * (1. - np.exp(np.clip(-dy * tt / Hm, -60, 60))), e0 * tt)
        integ = np.clip(integ, 0., 400.)
        a = 1. - np.exp(-.016 * mist * integ)
        out = out * (1. - .8 * a[:, None]) + a[:, None] * np.array([.33, .39, .53], np.float32)[None]
    # 2. lamp and headlight cones (bounding sphere of each cone, then a short march)
    for h in halos or []:
        apex = np.asarray(h['apex'], np.float32); ax = np.asarray(h['axis'], np.float32); ax = ax / np.linalg.norm(ax)
        Lc = float(h['length']); Rm = float(h.get('R0', .1)) + Lc * math.tan(math.radians(h['half']))
        if float(np.linalg.norm(apex - O)) > 70.: continue
        c = apex + ax * Lc / 2; rad = math.sqrt((Lc / 2) ** 2 + Rm * Rm)
        oc = O - c; b = D @ oc; cc = float(oc @ oc) - rad * rad; disc = b * b - cc
        m = disc > 0
        if not m.any(): continue
        sq = np.sqrt(np.where(m, disc, 0.)); s0 = np.maximum(-b - sq, 0.); s1 = np.minimum(-b + sq, th)
        m &= s1 > s0 + 1e-3
        idx = np.nonzero(m)[0]
        if not len(idx): continue
        acc = _march(O, D, idx, s0[idx], s1[idx], apex, ax, h['half'], float(h.get('R0', .1)), 14, jit, Lc * .45)
        k = 1. - np.exp(-acc * .32 * float(h.get('dens', 1.)))
        out[idx] += k[:, None] * np.asarray(h['col'], np.float32)[None] * .9
    # 3. the lighthouse beam (narrow and long: march around the closest approach of each ray to the axis, shadow map from the lens)
    dazzle = 0.; flare = 0.
    if beam is not None:
        L0 = beam['origin']; half = math.radians(beam['half']); tan_h = math.tan(half); R0 = .55
        boxes = [b for b in (sc.boxes or []) if getattr(b, 'cast', True) and not getattr(b, 'hidden', False)]
        add = np.zeros(N, np.float32)
        for a in beam['dirs']:
            r_, u_ = _basis(a)
            M = 64; T = tan_h * 1.35
            gx, gy = np.meshgrid(np.linspace(-T, T, M, dtype=np.float32), np.linspace(-T, T, M, dtype=np.float32))
            Dm = a[None] + gx.ravel()[:, None] * r_[None] + gy.ravel()[:, None] * u_[None]; Dm /= np.linalg.norm(Dm, axis=1, keepdims=True)
            tm, _ = r3d.trace(L0[None] + Dm * .75, Dm, boxes, 0., None, primary=False)
            depth = np.where(np.isfinite(tm), tm + .75, 1e4).reshape(M, M).astype(np.float32)
            w0 = O - L0; b = D @ a; d_ = D @ w0; e = float(w0 @ a); den = np.maximum(1 - b * b, 1e-4)
            sc_ = (b * e - d_) / den; lam = np.clip((e - b * d_) / den, 0., 160.)
            Rc = R0 + lam * tan_h
            dist2 = np.sum((O[None] + D * sc_[:, None] - (L0[None] + a[None] * lam[:, None])) ** 2, 1)
            hlen = np.minimum(Rc * 1.8 / np.sqrt(den), 110.)
            s0 = np.clip(sc_ - hlen, 0., None); s1 = np.minimum(sc_ + hlen, th)
            m = (s1 > s0 + 1e-3) & (dist2 < (Rc * 1.6) ** 2 + 1.)
            idx = np.nonzero(m)[0]
            if len(idx): add[idx] += _march(O, D, idx, s0[idx], s1[idx], L0, a, beam['half'], R0, 26, jit, 34., shadow=(depth, M, T))
            vc = O - L0; dc = float(np.linalg.norm(vc)) + 1e-6; cosc = float(vc @ a) / dc; cos_h = math.cos(half * 1.25)
            if cosc > cos_h: dazzle = max(dazzle, ((cosc - cos_h) / (1 - cos_h)) ** .7 / (1. + dc / 60.))
            flare = max(flare, max(0., (cosc - math.cos(half * 4)) / (1 - math.cos(half * 4))))
        vol = 1. - np.exp(-add * .085 * beam['brume'] * beam['on'])
        out += vol[:, None] * beam['col'][None] * 1.35
        u0, v0, zc = r3d.project(pos, yaw, pitch, roll, fov, L0)
        if zc > .5 and abs(u0) < 1.3 and abs(v0) < 1.3:
            px0 = (u0 + 1) / 2 * RW; py0 = (1 - v0) / 2 * RH
            inside = 0 <= px0 < RW and 0 <= py0 < RH
            if not inside or th[int(py0) * RW + int(px0)] > zc - 1.5:
                yy, xx = np.mgrid[0:RH, 0:RW].astype(np.float32)
                rr = np.sqrt((xx - px0) ** 2 + (yy - py0) ** 2) / (RH * (.012 + .018 * flare))
                g = (np.exp(-rr * rr) * (.3 + .9 * flare) + np.exp(-rr * .5) * .08 * flare) * beam['on']
                out += g.reshape(-1)[:, None] * beam['col'][None]
        if dazzle > 0: out = out * (1 - .35 * dazzle) + beam['col'][None] * (1.6 * dazzle * beam['on'])
    return out.reshape(RH, RW, 3)


# ================================================================== PIXEL 3D: the set class
def make(name, spec):
    """make_set for `phare_foret` (sets.py): the place expanded like any ready place, built by PhareSet"""
    from . import places as PL, environment_variation as EV, qt_street as QS
    o = QS.finish(EV.dress(PL.expand('phare_foret', spec), 'phare_foret', spec), 'phare_foret', spec, name)
    return set_class()(o)


_CLS = {}


def set_class():
    if 'c' in _CLS: return _CLS['c']
    from .sets import RoomSet, SKIES

    class PhareSet(RoomSet):
        """the lighthouse place: a RoomSet plus its texture boxes (windows with curtains, signs, the dashboard screen), its practical lights
        (with the group of the element they belong to), the car's headlights, the moon, and the place pass (beam, cones, low mist)"""
        name = 'phare_foret'

        def _add(self, box, group=None):
            self.base.add(box)
            if group: self.groups.setdefault(group, []).append(len(self.base.boxes) - 1)

        def build(self):
            super().build()
            ph = self.spec.get('_phare') or {}; sc = self.base
            sc.sky_fn = night_sky(self.spec, SKIES['night']['sun'])
            self.light_groups = {}
            for l in ph.get('lights') or []:
                if l[5]: self.light_groups.setdefault(l[5], []).append(len(self.light_defs))
                self.light_defs.append(tuple(l[:5]))
            for w in ph.get('windows') or []:
                img = _shop_tex(w['kind']) if w.get('kind') in ('boutique', 'porte') else _window_tex(w['seed'], w['lit'])
                self._add(_tex_box(w['at'], w['size'], w['face'], img, (.75 if w.get('kind') else .9) if w['lit'] else .12, (40, 40, 44)), w.get('group'))
            for t in ph.get('texts') or []:
                self._add(_tex_box(t['at'], t['size'], t['face'], _sign_tex(t['kind'], t['lines']), .32 if t['kind'] != 'borne' else .25, (200, 200, 196)))
            car = ph.get('car')
            if car and car.get('ecran'):
                flip = int(round(car.get('cap', 0))) % 360 == 180; sgn = -1 if flip else 1
                bx = _tex_box((car['x'], .7, car['z'] + sgn * .6), (.3, .182, .008), '+z' if flip else '-z', _screen_tex(car['ecran']), .42, (10, 16, 30))
                self._add(bx)
            if ph.get('boulangerie') == 'intacte':
                x0 = BAKERY[0] - 2.5
                self._add(_tex_box((x0 - .06, 2.74, 56.0), (.03, .6, 4.6), '-x', _sign_tex('enseigne', [ph.get('enseigne') or 'BOULANGERIE']), 1.0, (46, 30, 24)), 'boulangerie')
                self._add(_tex_box((5.05, .62, 59.57), (.56, .74, .01), '-z', _sign_tex('ardoise', ['PAIN', 'FRAIS', 'CROISSANT']), .28, (36, 40, 38)), 'boulangerie')
            if ph.get('plaque'):
                xd = LIGHTHOUSE[0] - 2.5 - .02
                self._add(_tex_box((xd - .095, 2.12, LIGHTHOUSE[1] - .2), (.01, .16, .4), '-x', _sign_tex('plaque', [str(ph['plaque'])[:8]]), .2, (150, 132, 90)))
            if ph.get('lanterne') != 'eteinte':
                self.light_groups.setdefault('lanterne', []).append(len(self.light_defs))
                self.light_defs.append(((LIGHTHOUSE[0], LENS_Y, LIGHTHOUSE[1]), (1.0, .97, .9), 1.6, 3.2, False))       # the lens lights the lantern room
            if ph.get('appoint', True):                                   # soft hidden lights in front of the two child windows (faces -z and -x)
                self.light_groups.setdefault('lanterne', []).extend([len(self.light_defs), len(self.light_defs) + 1])
                self.light_defs.append(((LIGHTHOUSE[0], LANTERN_FLOOR + 1.5, LIGHTHOUSE[1] - 2.5), (.9, .93, 1.0), 1.9, 2.6, False))
                self.light_defs.append(((LIGHTHOUSE[0] - 2.5, LANTERN_FLOOR + 1.5, LIGHTHOUSE[1]), (.9, .93, 1.0), 1.2, 2.3, False))
            if car and car.get('radio'):                                  # 15/11/2026: the car radio's dial (amber band, needle)
                flip = int(round(car.get('cap', 0))) % 360 == 180; sgn = -1 if flip else 1
                self._add(_tex_box((car['x'] - sgn * .0, .53, car['z'] + sgn * .595), (.14, .05, .004), '+z' if flip else '-z', _radio_tex(), .5, (20, 14, 8)), 'voiture.radio')
            self._radio = list(self.groups.get('voiture.radio', []))
            self._lens = list(self.groups.get('lentille', []))

        def outline(self, gid):
            """the outline left by an erased element (effacement.py): the invisible wall of the bakery ; nothing for the others"""
            from .sets import block_box
            return [block_box(b) for b in bakery_contour_blocks()] if gid == 'boulangerie' else []

        def _beam(self, state, u, g):
            return _beam_state((self.spec.get('_phare') or {}).get('faisceau'), state or {}, u, g)

        def _dead(self, state):
            return (self.spec.get('_phare') or {}).get('lanterne') == 'eteinte' or bool((state or {}).get('lanterne_eteinte'))

        def scene(self, state, t, u):
            sc = super().scene(state, t, u)
            ph = self.spec.get('_phare') or {}
            bm = self._beam(state, u, t); dead = self._dead(state)
            if bm is None or bm['col'][1] < .5 or dead:                  # off, or red: the lens follows ; dead forever: black glass
                sc.boxes = list(sc.boxes)
                for i in getattr(self, '_lens', []):
                    b0 = sc.boxes[i]; b = copy.copy(b0)
                    if dead: b.emis = 0.; b.col = b0.col * .16
                    elif bm is None: b.emis = .3; b.col = b0.col * .55
                    else: b.col = np.array(bm['col'], np.float32) * np.array([1., .9, .9], np.float32)
                    sc.boxes[i] = b
            if dead:                                                       # the caged lamps of the door go out with the lantern
                sc.boxes = list(sc.boxes)
                for i in self.groups.get('phare.lampes', []):
                    b = copy.copy(sc.boxes[i]); b.emis = .05; sc.boxes[i] = b
            rd = float((state or {}).get('radio', 0.) or 0.)
            if getattr(self, '_radio', None):                              # the car radio crackles: its LED and dial flicker
                sc.boxes = list(sc.boxes)
                fl = (.35 + .65 * (np.random.default_rng(int(t * 30) + 11).random() > .45)) if rd > 0 else 1.
                for i in self._radio:
                    b = copy.copy(sc.boxes[i]); b.emis = float(b.emis) * fl * (1. + rd * .6); b.texemis = float(b.texemis) * fl; sc.boxes[i] = b
            halos = ph.get('halos') or []; mist = float(ph.get('brume_basse', 1.)) * float((state or {}).get('brume_basse', 1.))
            sc.post_fn = lambda img, cam, _sc=sc, _bm=bm, _h=halos, _m=mist: place_post(img, cam, _sc, _bm, _h, _m)
            return sc

        def lights(self, state, t, u, cam_pos):
            ph = self.spec.get('_phare') or {}
            fade = getattr(self, '_efface_frame', None)
            saved = None
            if fade and abs(fade[0] - t) < 1e-6 and fade[1]:              # an element being erased in this frame: its own lights go down with it
                saved = self.light_defs; self.light_defs = list(saved)
                for gid, f in fade[1].items():
                    for i in self.light_groups.get(gid, []):
                        p, c, pw, r, fl = self.light_defs[i]; self.light_defs[i] = (p, c, pw * f, r, fl)
            if self._dead(state):                                          # dead forever (place option or `state.lanterne_eteinte`): its lights go out
                if saved is None: saved = self.light_defs; self.light_defs = list(saved)
                for gid in ('lanterne', 'phare.lampes'):
                    for i in self.light_groups.get(gid, []):
                        p_, c_, pw_, r_, fl_ = self.light_defs[i]; self.light_defs[i] = (p_, c_, 0., r_, fl_)
            try:
                L = super().lights(state, t, u, cam_pos)
            finally:
                if saved is not None: self.light_defs = saved
            L = [((l[0], l[1], l[2] * float(ph.get('lune', 2.4))) + tuple(l[3:])) if l[3] >= 399 else l for l in L]     # the moon sculpts the pines and the tower
            car = ph.get('car'); extra = []
            if car and car.get('phares', True):
                sgn = -1 if int(round(car.get('cap', 0))) % 360 == 180 else 1
                d = np.array([0., -.07, sgn * 1.], np.float32); d /= np.linalg.norm(d)
                extra.append(((car['x'], .7, car['z'] + sgn * 2.35), (1.0, .94, .8), 3.4, 17., False, (tuple(float(v) for v in d), .93, .78)))
            bm = None if self._dead(state) else self._beam(state, u, t)
            if bm is not None:
                for a in bm['dirs']:
                    p = bm['origin'] + a * .8
                    extra.append((tuple(float(v) for v in p), tuple(float(c) for c in bm['col']), 7.5 * bm['on'], 34., False,
                                  (tuple(float(v) for v in a), math.cos(math.radians(bm['half'] * .7)), math.cos(math.radians(bm['half'] * 1.2)))))
            return L[:-1] + extra + L[-1:] if L else extra                # keep the camera fill light LAST (acted.py adjusts L[-1])

    _CLS['c'] = PhareSet
    return PhareSet
