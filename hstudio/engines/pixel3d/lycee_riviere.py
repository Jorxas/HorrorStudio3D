"""Lieu prêt `lycee_riviere` : un lycée de petite ville, sa rue, la rivière et une passerelle piétonne (9 novembre 2026).

Né pour la série dramatique « Le Choix de Demain » (lycée des Amandiers, passerelle des Tilleuls, atelier des Rives), rangé ici pour toute histoire :
    LIEUX = {'lycee': {'type': 'lycee_riviere', 'sky': 'sunset', 'nom': ['LYCEE', 'DES AMANDIERS'], 'heure': '17:42', 'fete': True,
                       'passerelle': {'nom': ['PASSERELLE', 'DES TILLEULS'], 'fixation_rompue': True}, 'atelier': ['ATELIER', 'DES RIVES'],
                       'fenetre_classe': True}}

Uniquement des blocs (`blocks`), des décors (`props`) et des zones de sol : PS1 et VOXEL les dessinent de la même façon (aucune clé nouvelle du moteur).
Repère (mètres) : x vers la droite quand on regarde vers +z ; le sol est à y = 0.
  - le lycée : façade au nord du parvis, face avant à z = 0 (tournée vers +z, vers la rue), de x -15 à 15, 10 m de haut (rez-de-chaussée, 1er étage
    à y 3,4, 2e à 6,8) ; la tour de l'horloge au milieu (x -2,6 à 2,6, avancée jusqu'à z = 0,42), horloge à y ≈ 12,4, porte d'entrée et marches ;
  - la classe éclairée derrière une VRAIE fenêtre ouverte du 1er étage (option `fenetre_classe`) : ouverture x -8,3 à -6,7, y 4,3 à 5,9 ; plancher à y = 3,4 ;
    un personnage s'y tient à (x -7,5 ; y 3,4 ; z -0,9), tourné vers +z (il regarde la rue) ;
  - le parvis pavé (z 0 à 7,5) : amandiers en fleurs (x ±10 et ±13 : la fenêtre de la classe reste dégagée), bancs, pelouses ; une grille basse le ferme à z = 7,5 avec un portail ouvert (|x| < 2,5) ;
  - la rue (chaussée |x| < 3,5, trottoirs jusqu'à |x| = 6) part du portail vers +z, bordée de maisons (x ±6,5 à ±13), de lampadaires et de tilleuls ;
  - la rivière traverse la ville de z 46 à 54 (quais bas, parapets), la PASSERELLE la franchit au bout de la rue (x -1,3 à 1,3, z 44 à 56, tablier à y 0,45),
    pylônes à z 45 et 55, câbles et suspentes ; `fixation_rompue` : une suspente arrachée qui pend sous le tablier à z ≈ 50,5 (côté droit), fissure sur le tablier ;
  - l'atelier (option `atelier`) sur l'autre rive : x -12 à -2, z 58 à 66, grandes verrières chaudes, enseigne.

Options (toutes facultatives) :
  nom             ['LYCEE', 'DES AMANDIERS'] : enseigne au-dessus de la porte (lignes de 20 caractères au plus, sans accent)
  heure           '17:42' : l'heure de l'horloge de la tour (aiguilles)
  fete            True : banderole « FETE DE FIN D'ANNEE » sur le portail, guirlande de fanions, ballons ; liste = autre texte de banderole
  fenetre_classe  True : la classe éclairée derrière une fenêtre ouverte du 1er étage (voir ci-dessus)
  passerelle      True | {'nom': [...], 'fixation_rompue': True} : la passerelle piétonne ; False = pas de passerelle
  atelier         True | ['ATELIER', 'DES RIVES'] : le bâtiment de l'autre rive et son enseigne
  preau           True (9/11/2026) : le préau couvert à l'est du parvis (x 15,6 à 25,2 ; z -3 à 4,4 ; toit à y 3,2 sur piliers), mur du fond avec panneau
                  d'affichage, panneaux lumineux, deux bancs tournés vers le parvis (repères preau, preau.banc, preau.banc2), fontaine
  sky             'sunset' (défaut, fin d'après-midi dorée) | 'overcast' (ciel gris) | 'day' | 'storm' ; weather ('rain') comme tout lieu
Repères (`anchors`, x ; z) : start, parvis, porte, portail, rue, rue.milieu, rue.fin, passerelle, passerelle.milieu, fixation, rive.autre, atelier,
fenetre_classe, banc.gauche, banc.droit ; avec `preau` : preau, preau.banc, preau.banc2.
"""
import math

CREAM = (214, 190, 152); CREAM_D = (176, 152, 118); STONE = (150, 144, 136); ROOF = (150, 74, 54); WHITE = (236, 232, 222)
WOOD = (104, 70, 46); METAL = (70, 74, 82); RAIL = (196, 200, 206); GLASS_WARM = (255, 214, 150)


def block(at, size, color, material='plaster', **kw):
    return dict(at=[round(float(x), 3) for x in at], size=[round(float(x), 3) for x in size], color=list(color), material=material, **kw)


def _opt(v, default):
    """True -> default values ; dict -> its values on top ; falsy -> None"""
    if not v: return None
    return dict(default, **v) if isinstance(v, dict) else dict(default)


def _lines(v, default):
    if v is None or v is True: return list(default)
    return list(v) if isinstance(v, (list, tuple)) else [str(v)]


def _window(B, x, y0, z, w=1.5, h=1.6, lit=.35):
    """a closed window on the facade (z = front face): white frame, warm pane, sill"""
    B += [block((x, y0 - .08, z + .06), (w + .3, .1, .14), WHITE),
          block((x, y0, z + .03), (w + .16, h + .16, .06), WHITE),
          block((x, y0 + .08, z + .07), (w, h - .08, .03), GLASS_WARM, 'light', emissive=lit),
          block((x, y0 + .08, z + .09), (.06, h - .08, .03), WHITE), block((x, y0 + h * .55, z + .09), (w, .06, .03), WHITE)]


def school_blocks(spec):
    B = []
    classe = spec.get('fenetre_classe', True)
    # main body (behind the 3 m front band) and the front band, split around the classroom of `fenetre_classe`
    B.append(block((0, 0, -6.0), (30.0, 10.0, 6.0), CREAM))
    if classe:
        B += [block((-12.25, 0, -1.5), (5.5, 10.0, 3.0), CREAM), block((4.75, 0, -1.5), (20.5, 10.0, 3.0), CREAM),
              block((-7.5, 0, -1.5), (4.0, 3.4, 3.0), CREAM), block((-7.5, 6.8, -1.5), (4.0, 3.2, 3.0), CREAM)]
        # the classroom's front wall with its open window (x -8.3..-6.7, y 4.3..5.9)
        B += [block((-8.9, 3.4, -.15), (1.2, 3.4, .3), CREAM), block((-6.1, 3.4, -.15), (1.2, 3.4, .3), CREAM),
              block((-7.5, 3.4, -.15), (1.6, .9, .3), CREAM), block((-7.5, 5.9, -.15), (1.6, .9, .3), CREAM)]
        B += [block((-7.5, 4.22, .05), (1.9, .1, .16), WHITE), block((-7.5, 5.9, .02), (1.86, .1, .1), WHITE),
              block((-8.36, 4.3, .02), (.1, 1.6, .1), WHITE), block((-6.64, 4.3, .02), (.1, 1.6, .1), WHITE)]
        # inside: pale green walls, blackboard, desk, warm ceiling light (seen through the window)
        B += [block((-7.5, 3.4, -2.97), (3.9, 3.4, .06), (176, 196, 170)), block((-9.47, 3.4, -1.5), (.06, 3.4, 3.0), (176, 196, 170)),
              block((-5.53, 3.4, -1.5), (.06, 3.4, 3.0), (176, 196, 170)), block((-7.5, 6.74, -1.5), (3.9, .06, 3.0), (230, 228, 220)),
              block((-7.5, 4.3, -2.92), (2.2, 1.1, .05), (40, 70, 52)), block((-7.5, 3.4, -2.3), (1.4, .75, .6), WOOD, 'wood'),
              block((-7.5, 6.66, -1.6), (.5, .05, .5), (255, 236, 200), 'light', emissive=1.2, light=1.6),
              block((-7.5, 5.6, -.2), (.08, .04, .08), (255, 240, 214), 'light', emissive=1.0, light=1.1)]
    else:
        B.append(block((0, 0, -1.5), (30.0, 10.0, 3.0), CREAM))
    B += [block((0, 0, .05), (30.2, .45, .2), STONE, 'stone'),                                          # stone plinth
          block((0, 3.32, .04), (30.2, .14, .12), WHITE), block((0, 6.72, .04), (30.2, .14, .12), WHITE),   # string courses
          block((0, 10.0, -4.4), (30.8, .35, 9.6), ROOF, 'wood'), block((0, 10.35, -4.4), (28.0, .6, 7.0), ROOF, 'wood'),
          block((0, 10.95, -4.4), (24.0, .5, 4.0), ROOF, 'wood')]
    for x in (-13.5, -10.5, -4.5, 4.5, 7.5, 10.5, 13.5) + (() if classe else (-7.5,)):
        _window(B, x, 4.3, 0.0)
    for x in (-13.5, -10.5, -7.5, -4.5, 4.5, 7.5, 10.5, 13.5):
        _window(B, x, 7.7, 0.0, lit=.25)
    for x in (-13.5, -10.5, -7.5, 7.5, 10.5, 13.5):
        _window(B, x, 1.0, 0.0, lit=.3)
    # clock tower, door and steps
    B += [block((0, 0, -1.55), (5.2, 15.0, 3.9), CREAM_D), block((0, 0, .32), (5.4, .45, .2), STONE, 'stone'),
          block((0, 15.0, -1.55), (5.8, .3, 4.5), ROOF, 'wood'), block((0, 15.3, -1.55), (4.2, .8, 3.4), ROOF, 'wood'),
          block((0, 16.1, -1.55), (2.6, .7, 2.2), ROOF, 'wood'), block((0, 16.8, -1.55), (1.0, .6, .9), ROOF, 'wood'),
          block((0, 17.4, -1.55), (.08, 1.0, .08), METAL, 'metal')]
    B += [block((0, .45, .38), (2.6, 2.65, .12), (88, 56, 36), 'door'), block((0, .45, .45), (.06, 2.5, .04), (60, 38, 24), 'wood'),
          block((0, 3.1, .4), (3.0, .22, .2), WHITE), block((-.25, 1.6, .47), (.06, .3, .05), (200, 170, 90), 'metal'),
          block((.25, 1.6, .47), (.06, .3, .05), (200, 170, 90), 'metal')]
    for i in range(3):
        B.append(block((0, .15 * i, .85 + .35 * (2 - i)), (3.6 - .3 * i, .15, .35 + .0), STONE, 'stone'))
    for x in (-1.9, 1.9):
        B.append(block((x, 2.9, .48), (.16, .16, .1), (255, 226, 170), 'light', emissive=1.0, light=.9))      # door lamps
    # tower windows above the door
    for y in (4.4, 7.8):
        B += [block((0, y, .42), (1.2, 1.6, .06), WHITE), block((0, y + .08, .46), (1.0, 1.44, .03), GLASS_WARM, 'light', emissive=.3)]
    return B


def clock_blocks(heure, y=12.4, z=.43, R=1.15):
    """a tower clock in cubes (round white face, 12 marks, two hands at `heure`), facing +z"""
    B = []; n = 12
    for i in range(n):
        yc = -R + (i + .5) * 2 * R / n; hw = math.sqrt(max(0., R * R - yc * yc)) * 1.02
        B.append(block((0, y + yc - R / n, z), (2 * hw, 2 * R / n + .01, .08), WHITE))
    B.append(block((0, y - R - .12, z - .02), (2 * R + .3, 2 * R + .24, .06), (60, 58, 56)))            # dark square frame behind
    for k in range(12):
        a = k * math.pi / 6; r = R * .84; big = k % 3 == 0
        B.append(block((r * math.sin(a), y + r * math.cos(a) - (.07 if big else .04), z + .06), (.12 if big else .07, .14 if big else .08, .03), (34, 32, 30)))
    try:
        hh, mm = (int(v) for v in str(heure).split(':')[:2])
    except Exception:
        hh, mm = 17, 42
    am = mm / 60. * 2 * math.pi; ah = ((hh % 12) + mm / 60.) / 12. * 2 * math.pi
    for ang, L, wd in ((am, R * .80, .07), (ah, R * .52, .1)):
        for j in range(1, 9):
            r = L * j / 8.
            B.append(block((r * math.sin(ang), y + r * math.cos(ang) - wd / 2, z + .1), (wd, wd, .03), (24, 22, 22), 'metal'))
    B.append(block((0, y - .06, z + .11), (.14, .12, .04), (24, 22, 22), 'metal'))
    return B


def parvis_blocks(spec):
    B = []
    # low wall + railing along z = 7.5, open gate |x| < 2.5
    for sx in (-1, 1):
        B += [block((sx * 8.75, 0, 7.5), (12.5, .55, .35), STONE, 'stone'), block((sx * 8.75, 1.45, 7.5), (12.5, .07, .07), METAL, 'metal')]
        for k in range(26):
            B.append(block((sx * (2.8 + k * .48), .55, 7.5), (.05, .95, .05), METAL, 'metal'))
        B += [block((sx * 2.5, 0, 7.5), (.6, 2.4, .6), STONE, 'stone'), block((sx * 2.5, 2.4, 7.5), (.72, .14, .72), CREAM_D),
              block((sx * 2.5, 2.54, 7.5), (.26, .3, .26), (255, 226, 170), 'light', emissive=1.0, light=1.0)]
    fete = spec.get('fete')
    if fete:
        # bunting from the gate pillars to the facade, balloons on the pillars (the banner text is a `note` prop)
        cols = [(230, 80, 80), (250, 200, 70), (90, 170, 230), (120, 200, 120), (240, 140, 200)]
        for sx in (-1, 1):
            for k in range(14):
                t = k / 13.; z = 7.5 - t * 7.3; yy = 3.0 + 2.2 * t - 1.1 * math.sin(math.pi * t)
                B.append(block((sx * 2.5 + sx * t * 2.0, yy, z), (.18, .22, .03), cols[(k + (sx > 0)) % 5], 'fabric'))
            for j, (dx, dy, c) in enumerate(((.45, 3.3, 0), (.8, 3.55, 1), (.62, 3.9, 2))):
                bx = sx * (2.5 + dx)
                B += [block((bx, dy, 7.5), (.34, .4, .34), cols[(c + (sx > 0) * 2) % 5], 'fabric'), block((bx, 2.4, 7.5), (.02, dy - 2.4, .02), (240, 240, 240))]
        B += [block((-2.42, 2.84, 7.52), (.06, 1.45, .06), METAL, 'metal'), block((2.42, 2.84, 7.52), (.06, 1.45, .06), METAL, 'metal')]
    # lawns' kerbs around the almond trees
    for x in (-13.0, -10.0, 10.0, 13.0):
        B.append(block((x, 0, 3.6), (2.8, .12, 2.8), STONE, 'stone'))
    return B


def street_blocks(spec):
    B = []
    cols = [(212, 170, 132), (200, 150, 128), (222, 200, 160), (176, 160, 140), (226, 186, 150), (190, 170, 150), (214, 196, 170), (198, 164, 140)]
    for sx in (-1, 1):
        B.append(block((sx * 4.4, 0, 25.5), (.18, .14, 36.0), (120, 118, 114), 'stone'))                  # kerbs
        for i, (z0, z1, h) in enumerate(((9.5, 16.5, 9.0), (17.0, 23.5, 11.5), (24.0, 31.0, 8.0), (31.5, 38.0, 10.5), (38.5, 42.0, 7.5))):
            col = cols[(i * 2 + (sx > 0)) % len(cols)]
            B.append(block((sx * 9.75, 0, (z0 + z1) / 2), (6.5, h, z1 - z0 - .1), col, 'plaster',
                           facade={'style': 'old', 'lit': .32, 'night': False, 'seed': 7 * i + (3 if sx > 0 else 0)}))
            B.append(block((sx * 6.7, h, (z0 + z1) / 2), (.3, .5, z1 - z0 - .1), ROOF, 'wood'))
    return B


def river_blocks(spec):
    """quays (low parapets) along both banks of the river (z 46..54), with a gap for the footbridge"""
    B = []
    for zq in (45.6, 54.4):
        for sx in (-1, 1):
            B.append(block((sx * 21.6, 0, zq), (40.0, .85, .35), STONE, 'stone'))
            B.append(block((sx * 21.6, .85, zq), (40.0, .08, .45), (176, 170, 160), 'stone'))
    for sx in (-1, 1):
        for zq in (44.5, 55.5):
            B.append(block((sx * 4.5, 0, zq), (.25, 3.6, .25), METAL, 'metal'))
            B.append(block((sx * 4.5 - sx * .3, 3.5, zq - .3 if zq < 50 else zq + .3), (.6, .14, .6), (255, 226, 170), 'light', emissive=1.0, light=1.4))
    return B


def bridge_blocks(spec, pb):
    """the footbridge (x -1.3..1.3, z 44..56, deck y 0.45): planks, railings, two portal pylons, sagging cables and hangers"""
    B = []
    deck_y = .45; z0, z1 = 44.0, 56.0; W = 2.6
    B.append(block((0, deck_y - .15, (z0 + z1) / 2), (W, .15, z1 - z0), (92, 70, 52), 'wood'))
    for zp in (46.2, 53.8):                                                                                  # two piers near the banks
        B += [block((sx * .9, 0, zp), (.3, deck_y - .15, .3), (110, 106, 100), 'stone') for sx in (-1, 1)]
        B.append(block((0, deck_y - .3, zp), (W, .15, .3), (64, 92, 110), 'metal'))
    for k in range(int((z1 - z0) / .5)):
        z = z0 + .25 + k * .5
        B.append(block((0, deck_y, z), (W - .12, .03, .44), (150, 112, 78) if k % 2 else (138, 102, 70), 'wood'))
    for zz, h in ((43.4, .15), (43.0, .3)):                                                                  # small ramps at both ends
        B.append(block((0, 0, zz), (W, h, .45), (120, 116, 110), 'stone'))
        B.append(block((0, 0, z0 + z1 - zz), (W, h, .45), (120, 116, 110), 'stone'))
    broken = pb.get('fixation_rompue', True); zb = 50.5
    for sx in (-1, 1):
        for k in range(25):
            z = z0 + .25 + k * .48
            B.append(block((sx * 1.25, deck_y + .03, z), (.06, .95, .06), RAIL, 'metal'))
        B.append(block((sx * 1.25, deck_y + 1.0, (z0 + z1) / 2), (.1, .08, z1 - z0), RAIL, 'metal'))
        B.append(block((sx * 1.25, deck_y + .5, (z0 + z1) / 2), (.04, .04, z1 - z0), RAIL, 'metal'))
        for zp in (45.0, 55.0):                                                                              # portal pylons
            B.append(block((sx * 1.55, 0, zp), (.3, 5.6, .3), (64, 92, 110), 'metal'))
        # main cables: a sag from the pylon tops (y 5.5) to mid-span (y 1.9), as a chain of small cubes
        for k in range(41):
            z = 45.0 + k * .25; t = (z - 50.0) / 5.0; y = 1.9 + 3.6 * t * t
            B.append(block((sx * 1.4, y, z), (.07, .07, .27), (60, 64, 72), 'metal'))
        for k in range(1, 10):                                                                               # hangers every metre
            z = 45.0 + k
            t = (z - 50.0) / 5.0; ytop = 1.9 + 3.6 * t * t
            if broken and sx > 0 and abs(z - zb) < .6: continue
            B.append(block((sx * 1.4, deck_y + 1.0, z), (.035, max(.05, ytop - deck_y - 1.0), .035), (90, 94, 102), 'metal'))
    for zp in (45.0, 55.0):
        B.append(block((0, 5.45, zp), (3.4, .3, .3), (64, 92, 110), 'metal'))
    if broken:
        # the torn hanger: still hooked on the cable, torn off the deck, it swings OUTSIDE the railing and hangs below the deck;
        # its torn bracket (rust) and a dark hole on the deck edge, a bent piece of handrail, a crack across the planks
        t = (zb - 50.0) / 5.0; ytop = 1.9 + 3.6 * t * t; RUST = (150, 74, 44)
        n = 16
        for j in range(n):
            k = j / (n - 1.); y = ytop - .04 - k * (ytop - .1); x = 1.4 + .55 * k * k
            B.append(block((x, y, zb), (.06, (ytop - .1) / n + .03, .06), (96, 100, 110), 'metal'))
        B += [block((1.95, .02, zb), (.16, .2, .12), RUST, 'metal'), block((2.0, .14, zb + .07), (.05, .1, .05), RUST, 'metal'),
              block((1.33, deck_y - .16, zb), (.12, .18, .26), RUST, 'metal'), block((1.38, deck_y - .2, zb + .1), (.05, .08, .06), RUST, 'metal'),
              block((1.33, deck_y - .16, zb - .1), (.06, .1, .05), RUST, 'metal'), block((1.2, deck_y + .005, zb), (.14, .03, .16), (20, 16, 14), 'wood')]
        B += [block((1.32, deck_y + .86, zb + .05), (.1, .08, .6), (170, 172, 176), 'metal')]                       # handrail bent down and out
        for j, (dx, dz) in enumerate(((-1.0, -.04), (-.65, .03), (-.3, -.02), (.05, .04), (.4, -.03), (.75, .03), (1.05, .0))):
            B.append(block((dx, deck_y + .032, zb + dz), (.38, .014, .05), (30, 22, 18), 'wood'))
    return B


def atelier_blocks(spec):
    B = [block((-7.0, 0, 62.0), (10.0, 6.5, 8.0), (168, 100, 78)), block((-7.0, 6.5, 62.0), (10.4, .4, 8.4), (90, 90, 96), 'metal'),
         block((-7.0, 0, 57.95), (10.1, .5, .12), STONE, 'stone')]
    for x in (-10.5, -7.0, -3.5):
        B += [block((x, 1.0, 57.94), (2.4, 3.2, .06), (70, 72, 80), 'metal'), block((x, 1.08, 57.9), (2.2, 3.04, .03), GLASS_WARM, 'light', emissive=.55)]
        B += [block((x, 2.4, 57.88), (2.2, .05, .02), (70, 72, 80), 'metal'), block((x, 1.08, 57.88), (.05, 3.04, .02), (70, 72, 80), 'metal')]
    B += [block((-7.0, 6.9, 59.0), (.12, .9, .12), METAL, 'metal')]
    return B


def preau_blocks(spec):
    """the covered yard (préau) beside the school, on the east side of the parvis: x 15.6..25.2, z -3..4.4, roof at y 3.2 on stone pillars,
    a back wall with a notice board and a lit panel, two wooden benches facing the parvis (+z), a drinking fountain"""
    B = [block((20.45, 3.2, .7), (10.0, .28, 7.6), (96, 98, 106), 'metal'), block((20.45, 3.48, .7), (10.0, .1, 7.8), ROOF, 'wood'),
         block((20.4, 0, -3.0), (9.8, 3.2, .3), CREAM), block((25.35, 0, -1.0), (.3, 3.2, 4.0), CREAM),
         block((20.4, 0, -2.8), (9.6, .5, .12), CREAM_D)]
    for x in (15.9, 20.4, 24.9):
        B += [block((x, 0, 4.2), (.42, 3.2, .42), STONE, 'stone'), block((x, 3.0, 4.2), (.56, .2, .56), CREAM_D)]
    for x in (18.2, 22.6):                                                                                    # lit panels under the roof
        B.append(block((x, 3.12, .7), (1.6, .06, .5), (255, 236, 200), 'light', emissive=1.0, light=.9))
    B += [block((20.4, 1.0, -2.82), (2.6, 1.5, .06), (150, 110, 70), 'wood'), block((20.4, 1.08, -2.78), (2.4, 1.34, .04), (200, 170, 120), 'wood')]
    for (x, y_, c) in ((19.6, 1.9, (250, 250, 244)), (20.5, 1.5, (250, 236, 170)), (21.3, 1.95, (230, 240, 250)), (20.0, 1.25, (250, 220, 220))):
        B.append(block((x, y_, -2.75), (.42, .55, .02), c))                                                 # posters on the notice board
    B += [block((16.6, 0, -2.5), (.5, .9, .4), STONE, 'stone'), block((16.6, .9, -2.45), (.4, .08, .32), (176, 200, 210), 'metal')]
    return B


def lycee(spec):
    from .places import _base
    spec = spec or {}
    sky = spec.get('sky', 'sunset')
    o = _base(dict(spec, sky=sky), outdoor=True, sky=sky, ground='stone', backdrop=[{'type': 'city', 'height': 14, 'density': 30}, 'hills'], fog=.012,
              ambience='city', fill=.62, wet=bool(spec.get('weather') == 'rain'),
              zones=[{'rect': [-3.5, 7.5, 3.5, 43.0], 'ground': 'road'}, {'rect': [-15.5, 0, 15.5, 7.4], 'ground': 'cobble'},
                     {'rect': [-80, 45.8, 80, 54.2], 'ground': 'water'}, {'rect': [-80, 56.0, 80, 120], 'ground': 'grass'}]
                    + [{'rect': [x - 1.3, 2.3, x + 1.3, 4.9], 'ground': 'grass'} for x in (-13.0, -10.0, 10.0, 13.0)]
                    + [{'rect': [-3.5, z, 3.5, z + .45], 'ground': 'snow'} for z in (8.2, 9.0, 9.8)])
    pb = _opt(spec.get('passerelle', True), {'nom': ['PASSERELLE', 'DES TILLEULS'], 'fixation_rompue': True})
    B = school_blocks(spec) + clock_blocks(spec.get('heure', '17:42')) + parvis_blocks(spec) + street_blocks(spec) + river_blocks(spec)
    if pb: B += bridge_blocks(spec, pb)
    if spec.get('atelier', True): B += atelier_blocks(spec)
    if spec.get('preau'):
        B += preau_blocks(spec); o.setdefault('zones', []).append({'rect': [15.4, -3.0, 25.6, 7.4], 'ground': 'cobble'})
    o['blocks'] = list(spec.get('blocks', [])) + B
    P = o['props']
    P += [{'type': 'blossom_tree', 'at': [x, 3.6], 'size': 1.15} for x in (-13.0, -10.0, 10.0, 13.0)]
    P += [{'type': 'bench', 'at': [-4.6, 5.2], 'rot': 2}, {'type': 'bench', 'at': [4.6, 5.2], 'rot': 2}]
    P += [{'type': 'streetlight', 'at': [sx * 4.9, z]} for z in (12.0, 22.0, 32.0, 41.0) for sx in (-1, 1)]
    P += [{'type': 'tree_round', 'at': [sx * 5.2, z], 'size': .95, 'color': [70, 120, 56]} for z in (16.5, 27.0, 36.5) for sx in (-1, 1)]
    P += [{'type': 'tree_round', 'at': [x, z], 'size': 1.25, 'color': [78, 128, 60]} for (x, z) in ((-6.5, 43.2), (6.5, 43.2), (-9.0, 57.5), (5.5, 57.8), (12.0, 57.2))]
    P += [{'type': 'bicycle', 'at': [x, 6.6], 'rot': 1} for x in (9.0, 9.6, 10.2)] + [{'type': 'trash_can', 'at': [-4.0, 9.2]}]
    if spec.get('preau'):
        P += [{'type': 'bench', 'at': [x, 0.4], 'rot': 2} for x in (18.4, 22.4)]
    nom = _lines(spec.get('nom'), ['LYCEE', 'DES AMANDIERS'])
    # the place's signs are painted panels (`objets: False`): under the episode key `objets` a `note` would otherwise become a white printed A4 sheet
    P.append({'type': 'note', 'at': [0, .5], 'y': 1.75, 'rot': 2, 'w': 3.0, 'text': nom, 'fs': 8, 'color': [44, 52, 70], 'ink': [250, 226, 150], 'glow': .5, 'objets': False})
    if spec.get('fete'):
        txt = _lines(spec.get('fete'), ['FETE DE FIN', "D'ANNEE"]) if spec.get('fete') is not True else ['FETE DE FIN', "D'ANNEE"]
        for zz, rr in ((7.56, 2), (7.54, 0)):                                       # the banner reads from the street (+z) and from the parvis (-z)
            P.append({'type': 'note', 'at': [0, zz], 'y': 1.42, 'rot': rr, 'w': 4.6, 'text': txt, 'fs': 8, 'color': [250, 236, 200], 'ink': [190, 40, 60], 'glow': .35, 'objets': False})
    if pb:
        P.append({'type': 'note', 'at': [-2.4, 42.6], 'y': .8, 'rot': 0, 'w': 1.5, 'text': _lines(pb.get('nom'), ['PASSERELLE', 'DES TILLEULS']), 'fs': 7,
                  'color': [40, 70, 110], 'ink': [240, 240, 236], 'glow': .3, 'objets': False})
        B2 = [block((-2.4, 0, 42.62), (.08, 1.6, .08), METAL, 'metal')]
        o['blocks'] += B2
    if spec.get('atelier', True):
        P.append({'type': 'note', 'at': [-7.0, 57.85], 'y': 2.45, 'rot': 0, 'w': 3.2, 'text': _lines(spec.get('atelier'), ['ATELIER', 'DES RIVES']) if spec.get('atelier') is not True else ['ATELIER', 'DES RIVES'],
                  'fs': 8, 'color': [40, 36, 34], 'ink': [250, 230, 180], 'glow': .4, 'objets': False})
    o['anchors'] = dict(o.get('anchors') or {}, **{'start': (0., 12.0), 'parvis': (0., 4.0), 'porte': (0., 1.6), 'portail': (0., 7.5), 'rue': (0., 14.0),
                                                   'rue.milieu': (0., 26.0), 'rue.fin': (0., 42.0), 'passerelle': (0., 44.5), 'passerelle.milieu': (0., 50.0),
                                                   'fixation': (1.4, 50.5), 'rive.autre': (0., 57.5), 'atelier': (-7.0, 57.5), 'fenetre_classe': (-7.5, -.9),
                                                   'banc.gauche': (-4.6, 5.2), 'banc.droit': (4.6, 5.2)})
    if spec.get('preau'): o['anchors'].update({'preau': (20.4, 2.0), 'preau.banc': (18.4, .4), 'preau.banc2': (22.4, .4)})
    return o


def register(PLACES):
    """adds the place `lycee_riviere` ; nothing is replaced"""
    if 'lycee_riviere' not in PLACES: PLACES['lycee_riviere'] = lycee
