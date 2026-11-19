"""Lieu prêt `cinema_salle` : la salle de cinéma de quartier de la série « Le Cinéma des Absents » (6 novembre 2026).

Né dans `HISTOIRE_LE_CINEMA_DES_ABSENTS_P2B\\histoire.py` (partie 2), rangé ici pour être réutilisé par n'importe quelle histoire :
    LIEUX = {'salle': {'type': 'cinema_salle', 'siege_releve': {'rang': 7, 'cote': -1}, 'haut_parleur': True, 'porte_secours': True, 'trappe': True}}

Uniquement des blocs (`blocks`) et des pièces (`rooms`) : PS1 et VOXEL les dessinent de la même façon (aucune clé nouvelle du moteur, rien n'est remplacé).
Repère (mètres) : x vers la droite quand on regarde vers +z ; la salle va de z = 0 (mur d'entrée) à z = 25 (mur de l'écran), x de -5,5 à 5,5, plafond 6,2 ;
le foyer est derrière la porte (z de -6 à 0) ; la cabine de projection est EN HAUT du mur d'entrée, l'escalier monte le long du mur de droite (z de 2 à 8) ;
11 rangées de 2 x 5 fauteuils face à l'écran (+z), allée centrale |x| < 1,15 ; le rang k est à z = 19 - 1,1 (k - 1) (rang 1 devant, rang 7 à z = 12,4) ;
l'écran est un plateau surélevé (y = 0,9) devant un panneau lumineux, entre deux rideaux déchirés.

Options (toutes facultatives ; sans option, la salle de la partie 1) :
  siege_releve  {'rang': 7, 'cote': -1, 'place': 0} : le fauteuil d'allée de ce rang est un siège SURÉLEVÉ sur quatre pieds (18 cm de vide dessous : on y cache un objet) ;
                dossier plus sombre ; `cote` -1 = gauche, +1 = droite ; `place` 0 = côté allée
  ecarpe        True : écharpe rouge posée sur le fauteuil `siege_releve` (dessus, retombée derrière le dossier)
  plaque        '7'  : un « 7 » clair en blocs sur le dossier du fauteuil `siege_releve` (seul le chiffre 7 est dessiné)
  haut_parleur  True | {'x': -1.2, 'z': 12.4} : haut-parleur suspendu à une tige, voyant rouge (par défaut au-dessus du `siege_releve`)
  porte_secours True | {'z': 12.4} : porte de secours dans le mur de DROITE (x = 5,5), barre anti-panique, bloc « SORTIE » vert, fuite de lumière froide
  trappe        True | {'x': 3.05, 'z': 23.3, 'taille': 1.34} : trappe dans le plateau de l'écran (lisière sombre + lueur froide ; le battant est un `mover` à poser dans le plan)
  film          False : sans les deux fauteuils du « film » sur le plateau (par défaut : présents, pour jouer un diorama sur l'écran)
  foyer_guichet True : le foyer détaillé (la porte d'entrée est une OUVERTURE dans le mur, sans vitre : la rue est visible) : guichet (comptoir, grille), caisse enregistreuse à fente de ticket, moniteur de contrôle au mur (silhouette d'Inès de dos devant l'écran),
                registre épais ouvert (od_book, trois noms), stylo et gomme, plaque gravée sur le comptoir, affiche déchirée, machine à pop-corn et grains par terre, porte d'entrée vitrée avec sa clochette
  rue           True : la rue derrière la porte de secours (mur de droite) : chaussée mouillée, trottoir, lampadaire (lumière chaude), façade d'en face aux fenêtres allumées, lueur froide de la pluie
  porte_secours {'battant': False} : sans le battant rouge (on l'ajoute comme `mover` dans le plan pour l'ouvrir : il glisse le long du mur)
  projecteurs   True : lumières de scène cachées en hauteur (blocs émissifs `light`, seule façon d'éclairer en VOXEL : un objet de plan `{'type': 'light'}` n'existe pas et est ignoré) : de face sur le diorama
                du plateau (dos des silhouettes lisibles), sur l'Opérateur sous la cabine, et dans l'allée au niveau des rangs 6 à 8 (visages)
  cabine        True | {'rampe': True, 'projecteur': True, 'x': 2.6} : la CABINE DE PROJECTION (ajoutée le 7/11/2026, partie 4) : une vraie pièce en blocs sur le mur d'entrée, au-dessus de l'allée (plancher à y = 3,0 comme
                le palier de l'escalier, x de -2,5 à 4,2, z de 0,12 à 2,95, plafond à 5,9) : parapet et verrière en ruban (ouverte, on voit la salle et l'écran depuis la cabine), piliers dessous, porte
                de plain-pied avec le palier (x = 4,2, z 0,55 à 1,65), projecteur (x 2,6 par défaut, près de la porte ; `x` le déplace) sur son socle (corps, deux bobines, optique à lentille lumineuse vers l'écran, bouton rouge), boîtes de bobines, étagère,
                trois plafonniers ; `rampe` : une main courante en blocs le long de l'escalier. Sans l'option, rien ne change (la fenêtre lumineuse du mur d'entrée reste seule)
  foyer_registre ['INES', 'MILO', 'OPERATEUR', ...] : texte du registre du foyer (10 caractères par ligne au plus ; par défaut INES / MILO / OPERATEUR)
  foyer_note    'FERMÉ' | ['SEANCE', 'OUVERTE'] : le panneau de la porte du foyer, texte tourné vers le mur (illisible depuis la rue, pas conçu pour être filmé) ; liste = plusieurs lignes ; False = aucun panneau (de la rue il se voit comme une feuille blanche sans texte)
  interphone    True : un interphone (boîtier, grille, voyant vert) fixé à la grille du guichet, côté foyer
  ticket        ['POSTE LIBRE', ...] : le ticket qui dépasse de la fente de la caisse, lisible (6 lignes de 11 caractères au plus)
Repères (`anchors`, x ; z) : guichet, caisse, moniteur, registre, affiche, machine_popcorn, porte_entree, rue, start, entree, foyer, allee.debut, rang1 … rang11, siege_releve, ecran, plateau, cabine, escalier, escalier.haut, porte_secours, trappe, rideau.gauche, rideau.droit,
cabine.projecteur, cabine.porte, cabine.fenetre (si `cabine`), interphone (si `interphone`).
"""
RED = (150, 28, 40); RED_D = (122, 20, 32); CURT = (112, 16, 28); WOODC = (70, 46, 32); METAL = (150, 154, 164)
SEAT_X = [1.45 + .55 * i for i in range(5)]       # centres des fauteuils d'un côté (|x|)


def block(at, size, color, material='wood', **kw):
    return dict(at=[round(float(x), 3) for x in at], size=[round(float(x), 3) for x in size], color=list(color), material=material, **kw)


def row_z(k):
    """z du rang k (1 = devant, près de l'écran)"""
    return 19.0 - (k - 1) * 1.1


def _opt(v, default):
    """True -> valeurs par défaut ; dict -> ses valeurs par-dessus ; faux -> None"""
    if not v: return None
    return dict(default, **v) if isinstance(v, dict) else dict(default)


def hall_blocks(spec=None):
    spec = spec or {}
    rangs = int(spec.get('rangs', 11))
    sp = _opt(spec.get('siege_releve'), {'rang': 7, 'cote': -1, 'place': 0})
    B = []
    for k in range(1, rangs + 1):
        z = row_z(k)
        for side in (-1, 1):
            special = sp and k == sp['rang'] and side == sp['cote']
            if special:
                # assise surélevée (x de -1,725 à -1,125 pour le côté gauche) sur quatre pieds : vide de 18 cm dessous
                B.append(block((side * 2.85, 0, z), (2.25, .44, .5), RED, 'fabric'))
                B.append(block((side * 1.425, .18, z), (.6, .26, .5), RED, 'fabric'))
                for lx in (side * 1.70, side * 1.15):
                    for lz in (z - .22, z + .22):
                        B.append(block((lx, 0, lz), (.05, .18, .05), (30, 30, 36), 'metal'))
            else:
                B.append(block((side * 2.55, 0, z), (2.85, .44, .5), RED, 'fabric'))                                  # assises
            for i, ax in enumerate(SEAT_X):
                x = side * ax
                dark = special and i == sp['place']
                B.append(block((x, .44, z - .22), (.50, .60, .12), (34, 28, 32) if dark else RED_D, 'fabric'))
            for j in range(6):
                x = side * (1.45 - .275 + .55 * j)
                B.append(block((x, .44, z - .02), (.06, .10, .44), WOODC, 'wood'))
    if sp:
        z7 = row_z(sp['rang']); sx = sp['cote']
        if spec.get('ecarpe'):
            B += [block((sx * 1.33, 1.04, z7 - .22), (.30, .07, .20), (255, 34, 46), 'fabric'),
                  block((sx * 1.33, .50, z7 - .31), (.24, .56, .06), (255, 34, 46), 'fabric'),
                  block((sx * 1.40, .30, z7 - .31), (.11, .30, .05), (214, 22, 34), 'fabric')]
        if spec.get('plaque') == '7':
            B += [block((sx * 1.56, .86, z7 - .35), (.13, .035, .02), (250, 244, 214), 'light', emissive=True),
                  block((sx * 1.52, .74, z7 - .35), (.035, .13, .02), (250, 244, 214), 'light', emissive=True),
                  block((sx * 1.56, .62, z7 - .35), (.035, .13, .02), (250, 244, 214), 'light', emissive=True)]
    # plateau-écran, panneau lumineux (le « film »), perforations de pellicule
    B += [block((0, 0, 23.2), (8.4, .9, 3.2), (40, 28, 24), 'wood'),
          block((0, .9, 23.2), (6.8, .03, 2.7), (118, 22, 30), 'fabric'),
          block((0, 1.0, 24.84), (6.6, 4.0, .12), (70, 92, 136), 'light', emissive=True),
          block((0, .9, 24.9), (7.4, 4.9, .08), (14, 14, 18), 'plaster'),
          block((0, 5.0, 24.8), (7.2, .22, .22), (36, 24, 22), 'wood'),
          block((-3.5, .95, 24.8), (.2, 4.1, .2), (36, 24, 22), 'wood'), block((3.5, .95, 24.8), (.2, 4.1, .2), (36, 24, 22), 'wood')]
    for i in range(9):
        for sx_ in (-3.18, 3.18):
            B.append(block((sx_, 1.2 + i * .43, 24.74), (.2, .2, .05), (18, 18, 24), 'plaster'))
    for sx_, hs in ((-1, (5.0, 4.4, 5.2, 3.9, 4.8)), (1, (4.6, 5.2, 4.1, 5.0, 4.4))):                              # rideaux déchirés
        for i, h in enumerate(hs):
            B.append(block((sx_ * (4.05 + i * .32), 0.9, 24.55), (.34, h, .3), CURT, 'fabric'))
    if spec.get('film', True):                                                                                      # fauteuils du film (diorama de l'écran)
        B += [block((-.98, .93, 23.95), (.5, .42, .5), (176, 180, 190), 'fabric'), block((-.98, 1.35, 23.7), (.5, .6, .12), (176, 180, 190), 'fabric'),
              block((-1.55, .93, 23.95), (.5, .42, .5), (176, 180, 190), 'fabric'), block((-1.55, 1.35, 23.7), (.5, .6, .12), (176, 180, 190), 'fabric')]
    for sx_ in (-1, 1):                                                                                             # haut-parleurs de salle
        B += [block((sx_ * 5.28, 2.6, 21.0), (.36, 1.0, .8), (22, 22, 26), 'metal'), block((sx_ * 5.12, 2.85, 21.0), (.1, .5, .5), METAL, 'metal'),
              block((sx_ * 5.1, 3.15, 21.0), (.08, .06, .08), (255, 40, 30), 'light', emissive=True), block((sx_ * 5.12, 2.45, 21.0), (.1, .25, .3), METAL, 'metal')]
    for z in (4.0, 9.0, 14.0, 19.0):                                                                                # appliques tamisées
        for sx_ in (-1, 1):
            B.append(block((sx_ * 5.38, 2.2, z), (.12, .30, .22), (255, 170, 90), 'light', emissive=True, light=.28))
    for z in (3., 6., 9., 12., 15., 18.):                                                                           # luminaires de plafond
        B.append(block((0, 3.3, z), (.14, .05, .14), (170, 190, 230), 'light', emissive=True, light=1.1))
    for z in (9., 12.4, 15.5):
        for sx_ in (-1, 1):
            B.append(block((sx_ * 2.7, 3.3, z), (.14, .05, .14), (170, 190, 230), 'light', emissive=True, light=.8))
    B.append(block((-3.4, 3.4, 18.6), (.12, .05, .12), (255, 214, 160), 'light', emissive=True, light=1.2))
    # fenêtre de la cabine (en haut du mur d'entrée), escalier le long du mur de droite, porte de cabine avec lumière dessous
    B += [block((0, 4.15, .06), (2.6, 1.15, .1), (255, 196, 110), 'light', emissive=True, light=.95),
          block((0, 4.05, .02), (2.9, 1.35, .06), (22, 20, 24), 'plaster'),
          block((-1.3, 4.05, .1), (.12, 1.35, .12), WOODC, 'wood'), block((1.3, 4.05, .1), (.12, 1.35, .12), WOODC, 'wood')]
    for i in range(11):
        B.append(block((4.95, 0, 8.2 - .55 * i), (.95, .27 * (i + 1), .55), (58, 46, 40), 'wood'))
    B += [block((4.8, 0, 1.2), (1.2, 3.0, 2.5), (58, 46, 40), 'wood'),
          block((4.8, 3.0, .07), (1.0, 2.0, .09), WOODC, 'door'),
          block((4.8, 3.0, .13), (.92, .03, .05), (255, 205, 120), 'light', emissive=True, light=.7)]
    B += [block((-2.4, 1.7, -.2), (.16, .30, .16), (255, 176, 96), 'light', emissive=True, light=.6),
          block((-2.4, 1.55, -.14), (.22, .08, .12), WOODC, 'wood')]
    B += [block((-4.75, 2.7, .08), (.9, .26, .06), (60, 235, 120), 'light', emissive=True, light=.12)]                # issue de secours du fond (près de l'entrée)
    # ---- options ----
    hp = _opt(spec.get('haut_parleur'), {'x': (sp['cote'] * 1.2) if sp else -1.2, 'z': row_z(sp['rang']) if sp else 12.4})
    if hp:
        x, z = hp['x'], hp['z']
        B += [block((x, 3.6, z), (.07, 2.6, .07), (20, 20, 24), 'metal'),
              block((x, 2.55, z), (.62, .78, .46), (22, 22, 26), 'metal'),
              block((x, 2.66, z - .24), (.50, .56, .03), METAL, 'metal'),
              block((x, 2.80, z - .26), (.30, .30, .02), (60, 62, 70), 'metal'),
              block((x, 2.33, z - .26), (.07, .06, .03), (255, 40, 30), 'light', emissive=True, light=.3)]
    ps = _opt(spec.get('porte_secours'), {'z': 12.4, 'battant': True})
    if ps:
        dz = ps['z']
        if not spec.get('rue'):                      # sans la rue : panneau plein décoratif ; avec la rue : le mur est percé (voir salle())
            B += [block((5.40, 0, dz), (.16, 2.45, 1.75), (30, 28, 34), 'plaster')]
        if ps['battant']:
            B += [block((5.36, 0, dz), (.10, 2.30, 1.50), (118, 26, 34), 'door'),
                  block((5.28, 1.0, dz), (.06, .09, 1.20), METAL, 'metal')]
        B += [
              block((5.30, 0, dz - .60), (.05, 2.2, .05), (20, 20, 24), 'metal'), block((5.30, 0, dz + .60), (.05, 2.2, .05), (20, 20, 24), 'metal'),
              block((5.34, 2.62, dz), (.10, .30, .86), (60, 235, 120), 'light', emissive=True, light=.55),
              block((5.28, 2.66, dz - .08), (.03, .20, .05), (240, 255, 240), 'light', emissive=True),
              block((5.28, 2.70, dz + .06), (.03, .12, .20), (240, 255, 240), 'light', emissive=True),
              block((5.29, .05, dz + .77), (.03, 2.2, .025), (120, 170, 255), 'light', emissive=True, light=.25)]       # la rue, derrière
    tr = _opt(spec.get('trappe'), {'x': 3.05, 'z': 23.3, 'taille': 1.34})
    if tr:
        x, z, t = tr['x'], tr['z'], float(tr['taille']); h = t / 2
        B += [block((x, .9, z), (t, .06, t), (16, 14, 18), 'wood'),
              block((x, .93, z), (t - .22, .03, t - .22), (170, 235, 255), 'light', emissive=True, light=.9),
              block((x - h + .08, .9, z), (.08, .16, t), (30, 22, 18), 'wood'), block((x + h - .08, .9, z), (.08, .16, t), (30, 22, 18), 'wood'),
              block((x, .9, z - h + .05), (t, .16, .08), (30, 22, 18), 'wood'), block((x, .9, z + h - .05), (t, .16, .08), (30, 22, 18), 'wood')]
    B += foyer_blocks(spec) + rue_blocks(spec) + cabine_blocks(spec)
    if spec.get('projecteurs'):
        # lumières de scène : blocs émissifs minuscules au plafond (le seul éclairage ponctuel que VOXEL et PS1 lisent) ; chacune garde sa propre `light`
        for (x, y, z, col, lt) in ((-1.2, 4.6, 20.6, (205, 215, 255), 2.6), (0.5, 4.6, 20.8, (255, 244, 224), 1.8),         # de face sur le diorama de l'écran
                                   (0.0, 3.4, 4.6, (255, 240, 214), 3.0), (0.0, 2.6, 3.4, (255, 250, 236), 2.4),            # sur l'Opérateur, sous la cabine
                                   (-0.6, 3.3, 14.0, (255, 246, 230), 2.0), (-0.6, 3.3, 10.8, (255, 246, 230), 1.6)):       # dans l'allée, rangs 6 à 8
            B.append(block((x, y, z), (.10, .04, .10), col, 'light', emissive=True, light=lt))
    return B


def cabine_blocks(spec):
    """la cabine de projection (option `cabine`) : voir la description des options en tête de fichier"""
    cb = _opt(spec.get('cabine'), {'rampe': True, 'projecteur': True})
    if not cb: return []
    DK = (40, 32, 30); WD = (58, 46, 40); MET = (120, 124, 134); BLK = (26, 26, 32)
    x0, x1, z0, z1 = -2.5, 4.2, .12, 2.95
    W = x1 - x0; cx = (x0 + x1) / 2; cz = (z0 + z1) / 2; D = z1 - z0
    B = [block((cx, 2.86, cz), (W, .14, D), WD, 'wood'),                                    # plancher (y 2,86 à 3,0 : même niveau que le palier)
         block((cx, 2.3, z1 - .06), (W, .56, .12), DK, 'wood'),                              # poutre sous le parapet
         block((x0, 3.0, cz), (.14, 2.9, D), DK, 'plaster'),                                 # mur de gauche
         block((cx, 3.0, z1 - .06), (W, .9, .12), WD, 'wood'), block((cx, 3.9, z1 - .06), (W, .05, .16), DK, 'wood'),   # parapet + tablette
         block((cx, 4.9, z1 - .06), (W, 1.0, .12), DK, 'plaster'),                           # linteau : la verrière est le ruban ouvert entre 3,9 et 4,9
         block((cx, 5.9, cz), (W, .12, D), DK, 'plaster')]                                   # plafond
    for x in (-1.3, 1.3, 3.0):
        B.append(block((x, 3.9, z1 - .06), (.12, 1.0, .12), DK, 'wood'))                     # meneaux de la verrière
    for x in (-2.4, 0.9, 4.1):
        B.append(block((x, 0, z1 - .1), (.14, 2.3, .14), (50, 40, 36), 'wood'))              # piliers qui portent la cabine
    # mur de droite avec sa porte (z 0,55 à 1,65, h 2 m) vers le palier de l'escalier
    B += [block((x1, 3.0, (z0 + .55) / 2), (.14, 2.9, .55 - z0), DK, 'plaster'), block((x1, 3.0, (1.65 + z1) / 2), (.14, 2.9, z1 - 1.65), DK, 'plaster'),
          block((x1, 5.0, 1.1), (.14, .9, 1.1), DK, 'plaster')]
    if cb.get('projecteur', True):
        px = float(cb.get('x', 2.6))                                                                                                # le projecteur près de la porte du palier (x 2,6 par défaut)
        B += [block((px, 3.0, 1.55), (.55, .95, .7), BLK, 'metal'),                                                                 # socle
              block((px, 3.95, 1.5), (.62, .52, 1.15), MET, 'metal'), block((px, 4.16, 2.07), (.5, .30, .03), BLK, 'plaster'),      # corps et plaque noire de face
              block((px, 4.07, 2.38), (.24, .24, .55), BLK, 'metal'),                                                               # fût de l'optique
              block((px, 4.07, 2.70), (.18, .18, .05), (255, 250, 232), 'light', emissive=True, light=1.4)]                          # lentille lumineuse vers l'écran
        for rz in (1.15, 1.85):                                                                                                     # les deux bobines, debout sur le corps
            B += [block((px, 4.47, rz), (.07, .64, .64), (54, 56, 64), 'metal'), block((px, 4.47, rz), (.075, .46, .46), (92, 62, 44), 'plaster'),
                  block((px, 4.47, rz), (.09, .16, .16), (150, 154, 164), 'metal')]
        B += [block((px + .34, 4.30, 1.0), (.07, .07, .07), (255, 46, 40), 'light', emissive=True, light=.3),                       # bouton de démarrage (côté EST, côté porte)
              block((px + .33, 4.12, 1.35), (.05, .30, .05), (210, 40, 40), 'plaster')]                                              # levier
    B += [block((-1.9, 3.0, .75), (.5, .12, .5), MET, 'metal'), block((-1.9, 3.12, .75), (.46, .12, .46), (110, 40, 40), 'metal'), block((-1.9, 3.24, .75), (.5, .12, .5), MET, 'metal'),
          block((-2.3, 3.9, 1.5), (.28, .06, 2.0), WD, 'wood'), block((-2.3, 3.96, 1.0), (.2, .3, .3), MET, 'metal'), block((-2.3, 3.96, 1.7), (.2, .3, .3), (110, 40, 40), 'metal')]
    for (x, z, lt) in ((0.0, 1.5, 2.4), (-1.7, 1.2, 1.6), (1.9, 1.6, 1.4)):
        B.append(block((x, 5.78, z), (.14, .05, .14), (255, 214, 160), 'light', emissive=True, light=lt))
    if cb.get('rampe', True):                                                                                                        # main courante de l'escalier (côté salle)
        for i in range(11):
            z = 8.2 - .55 * i; h = .27 * (i + 1)
            B += [block((4.42, h, z), (.04, .85, .04), METAL, 'metal'), block((4.42, h + .85, z), (.05, .05, .60), METAL, 'metal')]
        for (y, z, lt) in ((1.9, 7.4, 1.5), (3.3, 4.6, 1.4)):                                                                     # deux petites lampes pour voir l'escalier
            B.append(block((4.3, y, z), (.10, .04, .10), (255, 226, 176), 'light', emissive=True, light=lt))
    return B


def interphone_blocks(spec):
    """l'interphone fixé à la grille du guichet (option `interphone`), côté foyer"""
    if not (spec.get('foyer_guichet') and spec.get('interphone')): return []
    return [block((-3.10, 1.30, -3.70), (.10, .36, .24), (60, 62, 70), 'metal'), block((-3.10, 1.07, -3.70), (.06, .24, .06), (46, 48, 56), 'metal'),   # boîtier et son support
            block((-3.04, 1.38, -3.70), (.03, .05, .16), (14, 14, 18), 'plaster'), block((-3.04, 1.46, -3.70), (.03, .05, .16), (14, 14, 18), 'plaster'),
            block((-3.04, 1.54, -3.70), (.03, .05, .16), (14, 14, 18), 'plaster'),                                                                    # grille du haut-parleur
            block((-3.04, 1.61, -3.70), (.03, .04, .05), (80, 255, 130), 'light', emissive=True, light=.35)]


def foyer_blocks(spec):
    """le foyer détaillé (option `foyer_guichet`) : repère x vers la droite quand on regarde vers +z ; le foyer va de x -4 à 4 et de z -6 (rue) à 0 (salle) ;
    le guichet longe le mur de GAUCHE (x = -4), l'affiche et la machine à pop-corn sont sur le mur de DROITE, la porte d'entrée vitrée dans le mur du fond (z = -6)"""
    if not spec.get('foyer_guichet'): return []
    B = []
    WOOD_D = (62, 40, 28); WOOD_L = (112, 80, 54); BRASS = (190, 150, 70)
    # guichet : comptoir, plateau, grille de laiton
    B += [block((-3.35, 0, -3.1), (1.3, 1.0, 4.6), WOOD_D, 'wood'), block((-3.30, 1.0, -3.1), (1.4, .07, 4.7), WOOD_L, 'wood')]
    for z in (-5.2, -4.6, -4.0, -3.4, -2.8):                                 # pas de poteau côté registre (z > -2,4) : il barrerait la vue du registre
        B.append(block((-3.0, 1.07, z), (.04, 1.1, .04), BRASS, 'metal'))
    B.append(block((-3.0, 2.17, -3.1), (.05, .07, 4.3), BRASS, 'metal'))
    # caisse enregistreuse (fente du ticket sur le dessus, face tournée vers +x)
    B += [block((-3.30, 1.07, -2.6), (.55, .22, .50), (122, 100, 70), 'metal'),
          block((-3.30, 1.29, -2.6), (.45, .28, .40), (86, 72, 52), 'metal'),
          block((-3.05, 1.33, -2.6), (.06, .20, .34), (205, 195, 165), 'plaster'),
          block((-3.30, 1.57, -2.6), (.34, .14, .30), (60, 110, 70), 'light', emissive=True, light=.3),
          block((-3.30, 1.71, -2.6), (.20, .02, .12), (14, 14, 18), 'plaster')]                     # la fente par où sort le ticket
    # moniteur de contrôle au mur, au-dessus du comptoir : une silhouette d'Inès, de dos, qui lit un papier
    B += [block((-3.93, 2.35, -3.1), (.12, .95, 1.3), (24, 22, 28), 'plaster'),
          block((-3.85, 2.45, -3.1), (.05, .75, 1.1), (122, 150, 172), 'light', emissive=True, light=.35),
          block((-3.82, 2.77, -3.36), (.04, .15, .15), (60, 36, 26), 'plaster'),                  # tête (cheveux bruns)
          block((-3.82, 2.47, -3.36), (.04, .30, .20), (156, 150, 146), 'plaster'),               # buste
          block((-3.82, 2.57, -3.22), (.04, .10, .08), (236, 236, 228), 'light')]                 # le papier qu'elle lit
    # stylo et gomme près du registre
    B += [block((-3.12, 1.07, -1.30), (.022, .022, .22), (24, 24, 30), 'plaster'), block((-3.12, 1.07, -1.54), (.026, .026, .05), (190, 40, 40), 'plaster'),
          block((-3.02, 1.07, -1.62), (.09, .035, .06), (232, 160, 170), 'plaster')]
    # affiche déchirée (mur de droite) : fond crème, bandeau rouge, bobine, coins arrachés
    B += [block((3.82, 1.0, -4.0), (.10, 1.5, 1.0), (206, 196, 172), 'plaster'), block((3.76, 1.95, -4.0), (.06, .38, 1.0), (170, 28, 34), 'plaster'),
          block((3.76, 1.25, -4.0), (.06, .42, .42), (28, 26, 30), 'plaster'), block((3.74, 1.36, -4.0), (.06, .20, .20), (206, 196, 172), 'plaster'),
          block((3.80, 1.0, -3.55), (.14, .34, .30), (92, 62, 42), 'wood'), block((3.80, 2.15, -4.50), (.14, .35, .24), (92, 62, 42), 'wood'),
          block((3.84, .70, -4.30), (.04, .32, .13), (206, 196, 172), 'plaster'), block((3.76, 1.82, -3.52), (.04, .20, .14), (170, 28, 34), 'plaster')]
    # machine à pop-corn froide (mur de droite) et grains par terre
    B += [block((3.35, 0, -1.7), (.9, .9, .7), (150, 30, 36), 'metal'), block((3.35, .9, -1.7), (.8, .8, .6), (196, 214, 222), 'glass'),
          block((3.35, 1.7, -1.7), (.9, .2, .7), (190, 150, 70), 'metal'), block((3.35, .95, -1.7), (.6, .5, .45), (232, 214, 140), 'plaster')]
    for (x, z) in ((2.55, -2.2), (2.3, -2.5), (2.7, -2.7), (2.1, -2.05), (2.9, -2.35), (2.45, -2.9)):
        B.append(block((x, .0, z), (.08, .06, .08), (236, 218, 150), 'plaster'))
    # porte d'entrée (mur du fond, z = -6) : ouverture dans le mur, cadre et clochette en laiton ; pas de vitre en blocs (opaque), la rue est visible derrière
    B += [block((0, -.05, -9.0), (9.0, .10, 6.0), (30, 34, 44), 'stone')]                                 # le trottoir dehors
    B += [block((0, 2.40, -5.95), (2.4, .35, .10), (30, 24, 22), 'wood'), block((-1.14, 0, -5.95), (.14, 2.7, .10), (30, 24, 22), 'wood'), block((1.14, 0, -5.95), (.14, 2.7, .10), (30, 24, 22), 'wood'),
          block((0, 2.78, -5.82), (.16, .16, .16), BRASS, 'metal'), block((0, 2.66, -5.82), (.05, .09, .05), (230, 200, 110), 'metal'),
          block((0, 3.0, -7.6), (.10, .04, .10), (190, 210, 255), 'light', emissive=True, light=3.0), block((0.8, 2.2, -7.0), (.10, .04, .10), (190, 210, 255), 'light', emissive=True, light=1.8)]
    # lumières du foyer : blocs émissifs au plafond (seul éclairage ponctuel lu par VOXEL et PS1) : centre, guichet, affiche, entrée
    for (x, y, z, col, lt) in ((0.0, 3.2, -3.0, (255, 226, 176), 2.2), (-2.2, 3.2, -2.6, (255, 232, 190), 2.4), (-2.2, 3.2, -4.6, (255, 232, 190), 1.8),
                               (2.4, 3.2, -3.6, (255, 220, 170), 1.8), (0.0, 3.2, -5.0, (255, 226, 176), 1.4), (-1.6, 2.4, -2.2, (255, 244, 220), 1.8),
                               (-1.2, 2.0, -3.1, (255, 240, 210), 1.6)):
        B.append(block((x, y, z), (.10, .04, .10), col, 'light', emissive=True, light=lt))
    return B + interphone_blocks(spec)


def rue_blocks(spec):
    """la rue derrière la porte de secours (option `rue`) : chaussée mouillée, trottoir, lampadaire, façade d'en face aux fenêtres allumées"""
    if not spec.get('rue'): return []
    B = [block((9.5, -.05, 12.4), (7.0, .10, 16.0), (30, 34, 44), 'stone'), block((6.15, 0, 12.4), (.5, .16, 16.0), (86, 88, 98), 'stone'),
         block((8.3, .0, 11.0), (1.4, .02, 1.0), (84, 104, 140), 'glass'), block((9.4, .0, 14.2), (1.8, .02, 1.2), (84, 104, 140), 'glass')]       # flaques
    B += [block((7.2, 0, 10.0), (.14, 4.2, .14), (30, 30, 34), 'metal'), block((6.9, 4.1, 10.0), (.7, .08, .08), (30, 30, 34), 'metal'),
          block((6.6, 3.98, 10.0), (.5, .14, .5), (255, 232, 176), 'light', emissive=True, light=2.4)]
    B += [block((12.6, 0, 12.4), (.8, 7.0, 16.0), (46, 40, 48), 'plaster')]
    for (y, z) in ((1.2, 6.0), (1.2, 9.4), (1.2, 15.0), (3.4, 7.6), (3.4, 12.4), (3.4, 16.2), (5.4, 9.8), (5.4, 14.0)):
        B.append(block((12.18, y, z), (.06, .9, .7), (255, 200, 120) if int(y + z) % 2 else (150, 190, 230), 'light', emissive=True, light=.4))
    B.append(block((7.0, 2.6, 12.4), (.1, .1, .1), (170, 200, 255), 'light', emissive=True, light=1.6))             # lueur froide de la pluie, devant la porte
    B.append(block((6.9, .0, 10.2), (3.4, .02, 3.4), (150, 162, 190), 'light', emissive=True, light=1.4))            # flaque de lumière du lampadaire sur la chaussée
    return B


def _affiche_prop():
    return {'type': 'note', 'at': [3.70, 2.0], 'y': -.05, 'rot': 1, 'w': .62, 'text': ['LE PHARE', 'SEANCE DE', 'MINUIT'], 'fs': 7}


def foyer_props(spec):
    """objets lisibles du foyer (registre et plaque gravée) : `props` de la pièce « foyer », en coordonnées LOCALES à la pièce (origine [0, -6] : z local = z du monde + 6)"""
    if not spec.get('foyer_guichet'): return []
    P = [_affiche_prop(), {'type': 'od_book', 'at': [-3.2, 4.05], 'y': 1.07, 'rot': 2, 'ouvert': True, 'titre': 'REGISTRE',
             'texte': list(spec.get('foyer_registre') or ['INES', 'MILO', 'OPERATEUR'])},
            {'type': 'note', 'at': [-2.62, 2.9], 'y': -.85, 'rot': 3, 'w': .40, 'text': ['PERSONNE NE QUITTE', 'LA SEANCE TANT QUE', 'SON ROLE EST', 'DISTRIBUE'], 'fs': 6}]
    if spec.get('ticket'):                        # le ticket qui dépasse de la fente de la caisse (x -3,3 ; z -2,6 -> local z 3,4), face vers +x
        P.append({'type': 'note', 'at': [-3.24, 3.4], 'y': .55, 'rot': 3, 'w': .34, 'text': list(spec['ticket'])[:6], 'fs': 6})
    return P


def salle(spec):
    spec = spec or {}
    rooms = [
        {'id': 'salle', 'origin': [0, 0], 'size': [11, 25], 'height': 6.2, 'walls': 'plaster', 'wall_color': [78, 34, 40], 'clean': True,
         'floor': 'carpet', 'light': 'none',
         'doors': [{'id': 'entree', 'wall': 'S', 'pos': .5, 'width': 2.0, 'open': 1}]},
        {'id': 'foyer', 'origin': [0, -6], 'size': [8, 6], 'height': 3.4, 'walls': 'wood', 'wall_color': [92, 62, 42], 'clean': True,
         'floor': 'carpet', 'light': 'warm', 'light_power': .55,
         'doors': [{'id': 'foyer_salle', 'wall': 'N', 'pos': .5, 'width': 2.0, 'open': 1, 'opening_only': True}],
         'props': ([] if spec.get('foyer_note', 'FERMÉ') is False else [{'type': 'note', 'at': [1.8, -.12], 'y': 1.5, 'w': .6, 'text': (lambda n: list(n) if isinstance(n, (list, tuple)) else [n])(spec.get('foyer_note', 'FERMÉ')), 'fs': 9}]) + foyer_props(spec)},
    ]
    sp = _opt(spec.get('siege_releve'), {'rang': 7, 'cote': -1, 'place': 0})
    ps = _opt(spec.get('porte_secours'), {'z': 12.4}); tr = _opt(spec.get('trappe'), {'x': 3.05, 'z': 23.3, 'taille': 1.34})
    if spec.get('foyer_guichet'):               # la porte d'entrée vitrée : ouverture réelle dans le mur du fond du foyer
        rooms[1]['doors'].append({'id': 'rue_entree', 'wall': 'S', 'pos': .5, 'width': 2.2, 'open': 1})
    if spec.get('rue') and ps:                  # la porte de secours donne sur la rue : ouverture réelle dans le mur de droite (le battant se pose en `mover`)
        rooms[0]['doors'].append({'id': 'issue', 'wall': 'E', 'pos': round(ps['z'] / 25., 4), 'width': 1.5, 'open': 1})
    anchors = {'start': (0., 1.5), 'entree': (0., 1.5), 'foyer': (0., -3.), 'allee.debut': (0., 4.6), 'ecran': (0., 22.), 'plateau': (0., 23.2), 'cabine': (0., 1.7),
               'escalier': (4.95, 5.), 'escalier.haut': (4.8, 1.2), 'rideau.gauche': (-4.8, 24.), 'rideau.droit': (4.8, 24.)}
    for k in range(1, int(spec.get('rangs', 11)) + 1): anchors[f'rang{k}'] = (0., row_z(k))
    if sp: anchors['siege_releve'] = (sp['cote'] * 1.45, row_z(sp['rang']))
    if ps: anchors['porte_secours'] = (5.3, ps['z'])
    if tr: anchors['trappe'] = (tr['x'], tr['z'])
    if spec.get('foyer_guichet'): anchors.update({'guichet': (-2.4, -3.1), 'caisse': (-3.3, -2.6), 'moniteur': (-3.9, -3.1), 'registre': (-3.2, -1.95), 'affiche': (3.9, -4.0),
                                                   'machine_popcorn': (3.35, -1.7), 'porte_entree': (0., -5.9)})
    if spec.get('rue'): anchors['rue'] = (9., 12.4)
    if spec.get('cabine'): anchors.update({'cabine.projecteur': (float(_opt(spec.get('cabine'), {'x': 2.6})['x']), 1.5), 'cabine.porte': (4.2, 1.1), 'cabine.fenetre': (0., 2.9)})
    if spec.get('interphone'): anchors['interphone'] = (-3.1, -3.7)
    return {'type': 'room', 'height': 6.2, 'clean': True, 'ambient': [.40, .43, .60], 'fill': .85, 'fog': .02, 'rooms': rooms, 'blocks': hall_blocks(spec), 'anchors': anchors}


def register(PLACES):
    """ajoute le lieu `cinema_salle` ; rien n'est remplacé"""
    if 'cinema_salle' not in PLACES: PLACES['cinema_salle'] = salle
