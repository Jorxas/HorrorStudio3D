"""Le THÉÂTRE de bal (lieu `theatre_bal`) : une vraie scène de théâtre du XVIIIe siècle, en deux versions natives (PS1 ici, VOXEL dans
voxelgpu/b_theatre.py) construites sur le MÊME plan (`plan()`).

Repère (celui de tous les lieux PIXEL 3D) : x vers la droite de l'image quand on regarde vers +z, y vers le haut, la salle (le public, la caméra)
du côté z < 0. Bord de scène à z = 0, mur de brique du fond à z = 10, scène de 16 m de large (x de -8 à 8) ; au-delà du bord, le noir.

    plateau tournant      centre (0, 4.6), anneau intérieur r < 1.8, anneau extérieur 1.8 < r < 4.0 ; angles : état `turn_inner` / `turn_outer`
    galerie du fond       à 3,5 m, de z = 8.4 à 10, sur toute la largeur, rambarde à deux lisses, cordages enroulés accrochés dessus
    tours latérales       deux échafaudages (x de ±6.7 à ±8.8) à deux niveaux (3,5 m et 6,9 m), croix de Saint-André, rambardes
    escalier gauche       de (−6.0, 2.5) au sol à (−6.0, 8.4) à 3,5 m (il monte vers le fond) ; escalier droit : de (1.9, 7.8) au sol à (6.7, 7.8) à 3,5 m
    bougies               quatre tables à gradin au pied du mur du fond, deux tables d'avant-scène, des grappes au sol, deux grands chandeliers
    lanternes             seize, suspendues à des chaînes à des hauteurs différentes
    projecteurs           deux rangées au-dessus de la galerie du fond, face à la salle (le « rideau de lumière », clé `stage_light.curtain`)

La lumière de scène (lavis, poursuite, rideau, noir) est écrite par plan (clé `stage_light`, voir stage_light.py) et appliquée ici par
`TheatreSet.stage_frame`, appelé par frame.build_frame / acted.build_acted SEULEMENT pour ce lieu : aucun autre lieu n'a cette méthode.
Rien d'aléatoire non semé : les bougies et les briques sortent d'un générateur à graine fixe, le scintillement est une fonction du temps.
"""
import functools, math
import numpy as np
from .r3d import B, C, Box, Scene, orient, M_WOODV, M_METAL, M_FABRIC, vnoise2, h2
from . import r3d
from . import stage_light as SL

W_HALF = 8.0; DEPTH = 10.0; BACK = 10.0; WALL_T = .4; WALL_X = 9.2; WALL_H = 11.5
GAL_Y = 3.5; GAL_Z = 8.4; UP_Y = 6.9
TOWER_IN = 6.7; TOWER_OUT = 8.8; TOWER_Z0 = 1.0
TT = (0., 4.6, 1.8, 4.0)                      # plateau tournant : centre x, z, rayon intérieur, rayon extérieur
STAIR_L = dict(x0=-6.55, x1=-5.45, z0=2.5, z1=GAL_Z, n=17)          # monte vers +z
STAIR_R = dict(x0=1.9, x1=TOWER_IN, z0=7.27, z1=8.37, n=17)          # monte vers +x
WOOD = (92, 64, 42); WOOD_D = (58, 40, 28); WOOD_L = (150, 112, 80); BRASS = (196, 150, 64); WAX = (232, 226, 210); FLAME = (255, 196, 112)
IRON = (34, 32, 34); ROPE = (150, 124, 86); GLASS = (255, 166, 72); BRICK = (88, 48, 36); MORTAR = (30, 24, 22)


APRON = 1.25                                  # le bord de scène est un arc : il avance de 1,25 m vers la salle au centre (0 aux côtés, x = ±8.6)


def edge_z(x):
    """z du bord de scène à l'abscisse x (arc convexe vers la salle)"""
    x = np.asarray(x, float); return -APRON * np.clip(1 - (x / 8.6) ** 2, 0, 1)


def _rng(seed): return np.random.default_rng(seed)


# ================================================================================================ le PLAN (commun aux deux styles)
@functools.lru_cache(maxsize=1)
def plan():
    """le lieu en éléments nommés (repère PIXEL 3D). Chaque style l'exécute avec son vocabulaire (PS1 : textures et matières ; VOXEL : blocs)."""
    P = dict(posts=[], beams=[], rails=[], braces=[], decks=[], stairs=[], tables=[], crates=[], candles=[], groups=[], stands=[],
             lanterns=[], ropes=[], coils=[], fixtures=[], studs=[])
    # --- poteaux (x, z, y0, y1)
    for x in (-6.75, -3.6, -.75, .75, 3.6, 6.75): P['posts'].append((x, GAL_Z + .09, 0., GAL_Y + 1.1))
    for sx in (-1, 1):
        for z in (TOWER_Z0 + .05, 3.6, 6.1):
            P['posts'].append((sx * (TOWER_IN + .09), z, 0., UP_Y + 1.1)); P['posts'].append((sx * (TOWER_OUT - .1), z, 0., UP_Y + 1.1))
        P['posts'].append((sx * (TOWER_OUT - .1), 9.6, 0., UP_Y + 1.1))
    # --- planchers (x0, z0, x1, z1, y) : galerie du fond, galeries latérales, niveau haut des tours
    P['decks'].append((-TOWER_OUT, GAL_Z, TOWER_OUT, BACK, GAL_Y))
    for sx in (-1, 1):
        x0, x1 = sorted((sx * TOWER_IN, sx * TOWER_OUT))
        P['decks'].append((x0, TOWER_Z0, x1, GAL_Z, GAL_Y)); P['decks'].append((x0, TOWER_Z0, x1, BACK, UP_Y))
    # --- poutres horizontales (p0, p1, section w, h) : sablières des galeries, liens hauts
    P['beams'].append(((-TOWER_OUT, GAL_Y - .19, GAL_Z + .09), (TOWER_OUT, GAL_Y - .19, GAL_Z + .09), .2, .38))
    P['beams'].append(((-WALL_X, UP_Y - .1, BACK - .12), (WALL_X, UP_Y - .1, BACK - .12), .2, .3))
    for sx in (-1, 1):
        for x in (TOWER_IN + .09, TOWER_OUT - .1):
            for y in (GAL_Y - .19, UP_Y - .19):
                P['beams'].append(((sx * x, y, TOWER_Z0 - .05), (sx * x, y, BACK - .2), .2, .38))
        for z in (TOWER_Z0 + .05, 3.6, 6.1):
            for y in (GAL_Y - .19, UP_Y - .19): P['beams'].append(((sx * TOWER_IN, y, z), (sx * TOWER_OUT, y, z), .2, .3))
    # --- rambardes (p0, p1) lisse haute + lisse médiane + balustres tous les ~1,1 m
    def railing(p0, p1, y):
        P['rails'].append(((p0[0], y + 1.02, p0[1]), (p1[0], y + 1.02, p1[1]), y))
        P['rails'].append(((p0[0], y + .52, p0[1]), (p1[0], y + .52, p1[1]), y))
    railing((STAIR_L['x1'] + .03, GAL_Z + .04), (TOWER_IN + .05, GAL_Z + .04), GAL_Y)                      # galerie du fond (ouverte en haut de l'escalier gauche)
    railing((-(TOWER_IN + .04), TOWER_Z0), (-(TOWER_IN + .04), GAL_Z), GAL_Y)                               # galerie latérale gauche
    railing((TOWER_IN + .04, TOWER_Z0), (TOWER_IN + .04, STAIR_R['z0'] - .03), GAL_Y)                       # galerie latérale droite (ouverte en haut de l'escalier droit)
    for sx in (-1, 1):
        railing((sx * (TOWER_IN + .04), TOWER_Z0), (sx * (TOWER_IN + .04), BACK - .2), UP_Y)
        railing((sx * TOWER_IN, TOWER_Z0 - .02), (sx * TOWER_OUT, TOWER_Z0 - .02), GAL_Y); railing((sx * TOWER_IN, TOWER_Z0 - .02), (sx * TOWER_OUT, TOWER_Z0 - .02), UP_Y)
    # --- croix de Saint-André sur la face intérieure des tours (p0, p1)
    for sx in (-1, 1):
        x = sx * (TOWER_IN + .09)
        for (za, zb) in ((TOWER_Z0 + .05, 3.6), (6.1, 9.6)):
            P['braces'].append(((x, .35, za), (x, GAL_Y - .45, zb))); P['braces'].append(((x, .35, zb), (x, GAL_Y - .45, za)))
        for (za, zb) in ((TOWER_Z0 + .05, 3.6), (3.6, 6.1), (6.1, 9.6)):
            P['braces'].append(((x, GAL_Y + .15, za), (x, UP_Y - .45, zb)))
    # --- poteaux muraux du fond (x, y0, y1) : planches verticales sur la brique
    for x in (-8.3, -5.1, -2.3, 2.3, 5.1, 8.3): P['studs'].append((x, 0., GAL_Y - .2))
    for x in (-7.6, -4.6, -1.6, 1.4, 4.4, 7.4): P['studs'].append((x, GAL_Y + .1, WALL_H))
    # --- escaliers (marches, limons, main courante)
    P['stairs'] = [dict(STAIR_L, axis='z'), dict(STAIR_R, axis='x')]
    # --- tables à bougies (x0, z0, x1, z1, h, gradin) et caisses (x, z, taille, rot)
    P['tables'] += [(-6.1, 9.12, -4.0, 9.72, .44, True), (-2.95, 9.12, -1.15, 9.72, .44, True), (1.15, 9.12, 2.65, 9.72, .44, True),
                    (3.75, 9.12, 5.75, 9.72, .44, True), (-7.95, 1.35, -6.85, 2.25, .78, False), (6.85, 2.1, 7.95, 3.0, .78, False)]
    P['crates'] += [(-4.75, 2.05, .55, 0), (-4.2, 2.45, .42, 1), (5.25, 5.9, .5, 0), (-7.5, 8.9, .6, 0), (7.6, 9.0, .55, 1)]
    # --- bougies : grappes (centre x, z, base y, étendue x, étendue z, nombre, graine)
    def cluster(cx, cz, y, ex, ez, n, seed, taper=.35):
        r = _rng(seed); out = []
        for i in range(n):
            x = cx + (i + .5) / n * ex * 2 - ex + r.uniform(-.04, .04); z = cz + r.uniform(-ez, ez)
            if r.random() < taper:
                st = r.uniform(.12, .38); out.append(dict(x=x, z=z, y=y, h=r.uniform(.2, .34), w=.036, stick=st))
            else: out.append(dict(x=x, z=z, y=y, h=r.uniform(.09, .42), w=r.choice([.06, .075, .09]), stick=0.))
        P['candles'].extend(out)
        P['groups'].append(dict(x=cx, y=y + .45, z=cz, n=n))
    for i, (x0, z0, x1, z1, h, step) in enumerate(P['tables']):
        cx = (x0 + x1) / 2; n = int((x1 - x0) / .16)
        cluster(cx, z0 + .16, h, (x1 - x0) / 2 - .1, .07, n, 11 + i)
        if step: cluster(cx, z1 - .14, h + .2, (x1 - x0) / 2 - .16, .05, max(4, n - 4), 31 + i, taper=.55)
    cluster(-4.75, 2.05, .55, .16, .1, 4, 51, taper=0.); cluster(5.25, 5.9, .5, .15, .1, 3, 52, taper=0.)
    cluster(-3.3, 9.0, 0., .35, .18, 7, 53, taper=0.); cluster(2.95, 9.0, 0., .3, .18, 6, 54, taper=0.); cluster(-7.3, 6.8, 0., .3, .3, 6, 55, taper=0.)
    cluster(7.3, 7.6, 0., .3, .3, 6, 56, taper=0.); cluster(0., 9.35, 0., .5, .2, 8, 57, taper=0.)
    # --- grands chandeliers sur pied (x, z, hauteur)
    P['stands'] += [(-6.2, .85, 1.35), (6.3, .95, 1.45), (-3.6, 8.75, 1.1), (3.4, 8.7, 1.2)]
    for (x, z, h) in P['stands']: P['candles'].append(dict(x=x, z=z, y=h, h=.32, w=.1, stick=0.)); P['groups'].append(dict(x=x, y=h + .5, z=z, n=1))
    # --- lanternes (x, y, z) : chaînes jusqu'aux cintres
    P['lanterns'] += [(-5.7, 6.7, 3.2), (-4.4, 4.9, 6.4), (-3.2, 7.6, 4.1), (-2.1, 5.7, 2.3), (-1.1, 4.5, 6.9), (.3, 7.1, 5.2), (1.2, 5.2, 3.3), (2.1, 8.0, 7.6),
                      (2.9, 4.7, 5.7), (3.9, 6.3, 2.7), (4.9, 5.4, 7.1), (5.9, 7.4, 4.6), (-6.3, 5.1, 7.9), (-2.7, 8.6, 8.1), (3.5, 8.8, 9.0), (-.6, 9.3, 3.0)]
    # --- cordages : cordes pendantes (x, z, y bas) et rouleaux accrochés aux rambardes (x, y haut, z, rayon)
    P['ropes'] += [(-7.95, .55, .1), (-7.7, .6, .1), (-7.45, .5, 2.2), (7.75, .62, .1), (7.98, .55, 1.4), (-6.9, 9.75, GAL_Y + .2), (6.95, 9.75, GAL_Y + .2)]
    for x in (-4.9, -4.25, -3.6, -2.95): P['coils'].append((x, GAL_Y + 1.02, GAL_Z - .02, .26))
    for x in (2.7, 3.35): P['coils'].append((x, GAL_Y + 1.02, GAL_Z - .02, .26))
    for z in (2.2, 2.85): P['coils'].append((TOWER_IN + .02, GAL_Y + 1.02, z, .25))
    P['coils'].append((-(TOWER_IN + .02), UP_Y + 1.02, 4.4, .24))
    # --- projecteurs du rideau de lumière : (position, direction) deux rangées au-dessus de la galerie du fond, face à la salle
    for row, (y, z, xs) in enumerate(((9.0, 9.35, [-5.4 + i * 1.8 for i in range(7)]), (7.75, 9.15, [-4.5 + i * 1.8 for i in range(6)]))):
        for x in xs:
            tgt = np.array([x * .72, 0., 2.6 + row * 1.2]); p = np.array([x, y, z]); d = tgt - p; d /= np.linalg.norm(d)
            P['fixtures'].append(dict(p=tuple(p), d=tuple(d), row=row))
    # --- niveaux praticables (pour la régie : pieds sur les marches et la galerie)
    walk = [dict(rect=[-TOWER_OUT, GAL_Z, TOWER_OUT, BACK], y=GAL_Y)]
    for sx in (-1, 1):
        x0, x1 = sorted((sx * TOWER_IN, sx * TOWER_OUT)); walk.append(dict(rect=[x0, TOWER_Z0, x1, GAL_Z], y=GAL_Y))
    for s in P['stairs']:
        n = s['n']; rise = GAL_Y / n
        for i in range(n):
            if s['axis'] == 'z': t = (s['z1'] - s['z0']) / n; walk.append(dict(rect=[s['x0'], s['z0'] + i * t, s['x1'], s['z0'] + (i + 1) * t], y=round((i + 1) * rise, 4)))
            else: t = (s['x1'] - s['x0']) / n; walk.append(dict(rect=[s['x0'] + i * t, s['z0'], s['x0'] + (i + 1) * t, s['z1']], y=round((i + 1) * rise, 4)))
    P['walkable'] = walk
    P['souffleur'] = (0., -APRON + .32)
    P['anchors'] = {'centre': (0., TT[1]), 'centre_scene': (0., TT[1]), 'avant_scene': (0., .4), 'bord_scene': (0., -.95), 'fond': (0., 7.6),
                    'cour': (4.6, 3.8), 'jardin': (-4.6, 3.8), 'escalier_gauche.bas': (-6.0, 2.2), 'escalier_gauche.haut': (-6.0, 8.9),
                    'escalier_droit.bas': (1.6, 7.8), 'escalier_droit.haut': (7.2, 7.8), 'galerie': (0., 9.2), 'galerie_gauche': (-7.7, 4.5), 'galerie_droite': (7.7, 4.5),
                    'bougies_fond_gauche': (-5.05, 8.8), 'bougies_fond_centre': (-2.05, 8.8), 'bougies_fond_droite': (4.75, 8.8),
                    'plateau.anneau': (0., TT[1] - 2.9), 'start': (0., -9.)}
    return P


# ================================================================================================ PS1 : textures et matières
@functools.lru_cache(maxsize=1)
def brick_tex():
    """le mur du fond (face -z) : briques sombres à trois tons, joints, coulures de suie ; 16 texels/m, rangée 0 = en haut"""
    ppm = 16; w = int(2 * WALL_X * ppm); h = int(WALL_H * ppm); r = _rng(7)
    img = np.zeros((h, w, 4), np.uint8); img[..., 3] = 255; img[..., :3] = MORTAR
    bh = 3; bw = 7                                                     # brique : 7 x 3 texels (44 x 19 cm) + joint d'un texel
    for row in range(0, h, bh + 1):
        off = 0 if (row // (bh + 1)) % 2 == 0 else (bw + 1) // 2
        for col in range(-off, w, bw + 1):
            k = r.uniform(.62, 1.15); tint = r.choice([0, 1, 2], p=[.6, .28, .12])
            c = np.array(BRICK, float) * k * ([1, 1, 1], [1.1, .9, .82], [.72, .74, .8])[tint]
            img[row:row + bh, max(0, col):max(0, col + bw), :3] = np.clip(c, 0, 255).astype(np.uint8)
    yy = np.arange(h)[:, None] / h; xx = np.arange(w)[None, :] / w
    soot = .55 + .45 * np.clip(1.2 - yy * 1.1, 0, 1) * (.8 + .2 * np.sin(xx * 40))
    img[..., :3] = (img[..., :3] * soot[..., None]).astype(np.uint8)
    return img


def floor_albedo(x, z, ang=(0., 0.)):
    """plancher de bois sombre ciré : lames le long de x, plateau tournant à deux anneaux (lames tournées avec l'anneau), joints sombres ; la salle (z < 0) est noire"""
    n = len(x); alb = np.zeros((n, 3), np.float32); refl = np.zeros(n, np.float32)
    cx, cz, r1, r2 = TT
    dx, dz = x - cx, z - cz; rr = np.sqrt(dx * dx + dz * dz)
    ring = np.where(rr < r1, 1, np.where(rr < r2, 2, 0))
    u = x.copy(); v = z.copy()
    for k, a in ((1, ang[0]), (2, ang[1])):                       # repère local de chaque anneau (tourne avec lui)
        m = ring == k
        if m.any():
            c, s = math.cos(a), math.sin(a); lu = dx[m] * c - dz[m] * s; lv = dx[m] * s + dz[m] * c
            if k == 2: lu, lv = lv, lu                                 # anneau extérieur : lames à 90° de l'intérieur (la rotation se voit)
            u[m] = lu + 11.3 * k; v[m] = lv + 7.1 * k
    pw = .16; row = np.floor(v / pw); L = 1.6 + .9 * h2(row, row * 0 + 3, 17)
    off = h2(row, row * 0 + 5, 19) * L; pid = np.floor((u + off) / L)
    tone = .72 + .36 * h2(pid, row, 23) + .10 * vnoise2(u * 3.1, v * 22., 29) + .05 * vnoise2(u * 18., v * 60., 31)
    base = np.where(ring[:, None] == 1, np.array((.30, .20, .135)), np.where(ring[:, None] == 2, np.array((.27, .182, .122)), np.array((.285, .19, .128))))
    a = base * tone[:, None]
    seam = ((v / pw) % 1 < .07) | (((u + off) / L) % 1 < .012)
    a[seam] *= .45
    rs = (np.abs(rr - r1) < .03) | (np.abs(rr - r2) < .035)          # joints des anneaux
    a[rs] = (.03, .025, .02)
    ez = edge_z(x); pit = (z < ez) | (np.abs(x) > WALL_X - .2) | (z > BACK + .05)
    lip = (z >= ez) & (z < ez + .07)
    a[lip] = (.36, .26, .17); a[pit] = (.006, .006, .007)
    alb[:] = a; refl[:] = np.where(pit, 0., np.where(seam, .05, .13))
    return alb, refl


def _beam_box(p0, p1, w, h, col, **kw):
    """une poutre de section w x h entre deux points (repère tourné : PS1 la trace exactement)"""
    R = beam_frame(p0, p1)
    L = float(np.linalg.norm(np.asarray(p1, float) - np.asarray(p0, float)))
    bx = [Box((-w / 2, -h / 2, 0.), (w / 2, h / 2, L), col, **kw)]
    return orient(bx, 0., tuple(float(v) for v in p0), R)


def beam_frame(p0, p1):
    """repère d'une poutre : colonnes (x local horizontal, y local vers le haut, z local le long de la poutre)"""
    d = np.asarray(p1, np.float32) - np.asarray(p0, np.float32); d = d / max(float(np.linalg.norm(d)), 1e-6)
    ex = np.cross(np.array([0, 1, 0], np.float32), d); n = float(np.linalg.norm(ex))
    ex = ex / n if n > 1e-4 else np.array([1, 0, 0], np.float32)
    return np.stack([ex, np.cross(d, ex), d], 1).astype(np.float32)


def _axis_beam(p0, p1, w, h, col, **kw):
    """poutre parallèle à un axe (section : w à l'horizontale, h à la verticale)"""
    p0 = np.asarray(p0, float); p1 = np.asarray(p1, float); ax = int(np.argmax(np.abs(p1 - p0)))
    c = (p0 + p1) / 2; half = {0: (abs(p1[0] - p0[0]) / 2, h / 2, w / 2), 1: (w / 2, abs(p1[1] - p0[1]) / 2, w / 2), 2: (w / 2, h / 2, abs(p1[2] - p0[2]) / 2)}[ax]
    return Box(c - np.array(half), c + np.array(half), col, **kw)


def ps1_build(P):
    """le plan -> (Scene de base, index des boîtes dont l'émission change : lentilles, flammes et vitres de lanternes)"""
    sc = Scene(); sc.ceil_y = None; sc.ambient = (.02, .03, .06); sc.fog = (.004, .007, .02); sc.fogk = .025
    add = sc.boxes.append; idx = dict(lens=[], flame=[], glass=[])
    # mur du fond : une boîte texturée, porte sombre au centre sous la galerie
    add(Box((-WALL_X, 0, BACK), (WALL_X, WALL_H, BACK + WALL_T), (70, 40, 30), tex={'-z': brick_tex()}, grain=.03))
    add(Box((-.72, 0, BACK - .03), (.72, 2.7, BACK), (8, 7, 7)))
    for (x, y0, y1) in P['studs']: add(Box((x - .13, y0, BACK - .1), (x + .13, y1, BACK), WOOD_D, mat=M_WOODV))
    for (x, z, y0, y1) in P['posts']: add(Box((x - .09, y0, z - .09), (x + .09, y1, z + .09), WOOD, mat=M_WOODV))
    for (x0, z0, x1, z1, y) in P['decks']:
        add(Box((x0, y - .14, z0), (x1, y, z1), WOOD, mat=M_WOODV))
    for (p0, p1, w, h) in P['beams']: add(_axis_beam(np.array(p0), np.array(p1), w, h, WOOD_D, mat=M_WOODV))
    for (p0, p1, y) in P['rails']:
        p0 = np.array(p0); p1 = np.array(p1); add(_axis_beam(p0, p1, .08, .08, WOOD, mat=M_WOODV))
        if abs(p0[1] - y - 1.02) < 1e-3:                                 # balustres sous la lisse haute
            L = float(np.linalg.norm(p1 - p0)); n = max(1, int(L / 1.1))
            for i in range(n + 1):
                q = p0 + (p1 - p0) * i / n; add(Box((q[0] - .045, y, q[2] - .045), (q[0] + .045, y + 1.02, q[2] + .045), WOOD, mat=M_WOODV))
    for (p0, p1) in P['braces']: sc.boxes.extend(_beam_box(p0, p1, .14, .12, WOOD_D, mat=M_WOODV))
    # escaliers : marches pleines (giron + contremarche sombre) et limons inclinés, main courante
    for s in P['stairs']:
        n = s['n']; rise = GAL_Y / n
        if s['axis'] == 'z':
            t = (s['z1'] - s['z0']) / n
            for i in range(n):
                z = s['z0'] + i * t; y = (i + 1) * rise
                add(Box((s['x0'] + .06, y - .05, z), (s['x1'] - .06, y, z + t + .03), WOOD_L, mat=M_WOODV))
                add(Box((s['x0'] + .07, y - rise, z), (s['x1'] - .07, y - .05, z + .025), WOOD_D))
            for x in (s['x0'] + .03, s['x1'] - .03):
                sc.boxes.extend(_beam_box((x, -.05, s['z0'] - .05), (x, GAL_Y + .05, s['z1'] + .05), .07, .3, WOOD_D, mat=M_WOODV))
            hx = s['x1'] - .03
            sc.boxes.extend(_beam_box((hx, 1.0, s['z0']), (hx, GAL_Y + 1.0, s['z1']), .07, .07, WOOD, mat=M_WOODV))
            for i in range(0, n, 4):
                z = s['z0'] + (i + .5) * t; y = (i + 1) * rise; add(Box((hx - .03, y, z - .03), (hx + .03, y + 1.0, z + .03), WOOD))
        else:
            t = (s['x1'] - s['x0']) / n
            for i in range(n):
                x = s['x0'] + i * t; y = (i + 1) * rise
                add(Box((x, y - .05, s['z0'] + .06), (x + t + .03, y, s['z1'] - .06), WOOD_L, mat=M_WOODV))
                add(Box((x, y - rise, s['z0'] + .07), (x + .025, y - .05, s['z1'] - .07), WOOD_D))
            for z in (s['z0'] + .03, s['z1'] - .03):
                sc.boxes.extend(_beam_box((s['x0'] - .05, -.05, z), (s['x1'] + .05, GAL_Y + .05, z), .07, .3, WOOD_D, mat=M_WOODV))
            hz = s['z0'] + .03
            sc.boxes.extend(_beam_box((s['x0'], 1.0, hz), (s['x1'], GAL_Y + 1.0, hz), .07, .07, WOOD, mat=M_WOODV))
            for i in range(0, n, 4):
                x = s['x0'] + (i + .5) * t; y = (i + 1) * rise; add(Box((x - .03, y, hz - .03), (x + .03, y + 1.0, hz + .03), WOOD))
    # tables à bougies, caisses
    for (x0, z0, x1, z1, h, step) in P['tables']:
        add(Box((x0, 0, z0), (x1, h, z1), WOOD_L, mat=M_WOODV)); add(Box((x0 - .03, h - .04, z0 - .03), (x1 + .03, h, z1 + .03), (170, 130, 94)))
        if step: add(Box((x0 + .04, h, z1 - .28), (x1 - .04, h + .2, z1), WOOD_L, mat=M_WOODV))
    for (x, z, s, rot) in P['crates']:
        y0 = .55 if s < .4 else 0.
        add(Box((x - s / 2, y0, z - s / 2), (x + s / 2, y0 + s, z + s / 2), (120, 88, 58), mat=M_WOODV))
    # grands chandeliers (pied de laiton)
    for (x, z, h) in P['stands']:
        add(Box((x - .16, 0, z - .16), (x + .16, .06, z + .16), BRASS, mat=M_METAL)); add(Box((x - .03, .06, z - .03), (x + .03, h - .05, z + .03), BRASS, mat=M_METAL))
        add(Box((x - .1, h - .06, z - .1), (x + .1, h, z + .1), BRASS, mat=M_METAL))
    # bougies : cire, mèche, flamme émissive ; chandelier de laiton pour les cierges fins
    for c in P['candles']:
        x, z, y, h, w, st = c['x'], c['z'], c['y'], c['h'], c['w'], c['stick']
        if st > 0:
            add(Box((x - .045, y, z - .045), (x + .045, y + .02, z + .045), BRASS, mat=M_METAL)); add(Box((x - .013, y + .02, z - .013), (x + .013, y + st, z + .013), BRASS, mat=M_METAL))
            add(Box((x - .03, y + st, z - .03), (x + .03, y + st + .025, z + .03), BRASS)); y = y + st + .025
        add(Box((x - w / 2, y, z - w / 2), (x + w / 2, y + h, z + w / 2), WAX, grain=.02))
        idx['flame'].append(len(sc.boxes)); add(Box((x - .014, y + h + .01, z - .014), (x + .014, y + h + .065, z + .014), FLAME, emis=3.2, cast=False))
    # lanternes : chaîne, chapeau, vitres émissives, montants, fond
    for (x, y, z) in P['lanterns']:
        add(Box((x - .012, y + .27, z - .012), (x + .012, 14., z + .012), IRON, cast=False))
        add(Box((x - .16, y + .17, z - .16), (x + .16, y + .23, z + .16), IRON, mat=M_METAL)); add(Box((x - .08, y + .23, z - .08), (x + .08, y + .29, z + .08), IRON))
        idx['glass'].append(len(sc.boxes)); add(Box((x - .1, y - .14, z - .1), (x + .1, y + .17, z + .1), GLASS, emis=.95, cast=False))
        for (ax, az) in ((-1, -1), (1, -1), (-1, 1), (1, 1)): add(Box((x + ax * .115 - .018, y - .16, z + az * .115 - .018), (x + ax * .115 + .018, y + .18, z + az * .115 + .018), IRON, cast=False))
        add(Box((x - .13, y - .2, z - .13), (x + .13, y - .14, z + .13), IRON))
    # cordages : cordes pendantes et rouleaux (anneaux de petits segments) accrochés aux rambardes
    for (x, z, yb) in P['ropes']: add(Box((x - .025, yb, z - .025), (x + .025, 14., z + .025), ROPE, mat=M_FABRIC, cast=False))
    for (x, y, z, r) in P['coils']:
        along_x = abs(z - (GAL_Z - .02)) < .05
        for k in range(14):
            a = k / 14 * 2 * math.pi; px = math.sin(a) * r; py = -r - math.cos(a) * r * 1.3
            if along_x: add(Box((x + px - .035, y + py - .035, z - .05), (x + px + .035, y + py + .035, z - .01), ROPE, mat=M_FABRIC))
            else: add(Box((x - .05 * (1 if x > 0 else -1) - .02, y + py - .035, z + px - .035), (x - .05 * (1 if x > 0 else -1) + .02, y + py + .035, z + px + .035), ROPE, mat=M_FABRIC))
    # boîte du souffleur au nez de scène (lueur chaude vers la scène)
    sx_, sz_ = P['souffleur']; add(Box((sx_ - .3, 0, sz_ - .15), (sx_ + .3, .12, sz_ + .2), (26, 22, 20))); add(Box((sx_ - .24, .08, sz_ - .17), (sx_ + .24, .11, sz_ - .14), (255, 196, 110), emis=.6, cast=False))
    # projecteurs (rideau de lumière) : barres, corps sombres, lentilles (émission pilotée par la lumière de scène)
    for y, z in ((9.0, 9.35), (7.75, 9.15)): add(Box((-6.4, y + .22, z - .03), (6.4, y + .28, z + .03), IRON, mat=M_METAL))
    for f in P['fixtures']:
        x, y, z = f['p']
        add(Box((x - .15, y - .15, z), (x + .15, y + .15, z + .38), (24, 24, 26), mat=M_METAL)); add(Box((x - .02, y + .15, z + .1), (x + .02, y + .28, z + .14), IRON))
        idx['lens'].append(len(sc.boxes)); add(Box((x - .12, y - .12, z - .03), (x + .12, y + .12, z), (20, 22, 26), cast=False))
    return sc, idx


# ================================================================================================ PS1 : le lieu
def flicker(t, seed):
    """scintillement d'une flamme, fonction du temps seule (aucun hasard)"""
    return .84 + .1 * math.sin(t * 9.1 + seed * 1.7) * math.sin(t * 5.3 + seed * .9) + .06 * math.sin(t * 23. + seed * 3.1)


WASH_POS = ((-5.5, 8.5, -3.2), (0., 9.2, -3.8), (5.5, 8.5, -3.2))
BACK_POS = (0., 9.6, 9.2)


class TheatreSet:
    """interface d'un lieu de PIXEL 3D (comme `RoomSet`) + `stage_frame` : la lumière de scène de l'image"""
    name = 'theatre_bal'

    def __init__(self, spec=None):
        P = plan()
        self.spec = dict(spec or {}); self.spec.setdefault('walkable', [dict(w) for w in P['walkable']]); self.spec.setdefault('ground_y', 0.); self.spec['ground_walkable'] = True
        self.spec.setdefault('outdoor', False)
        self.base = None; self.room_rects = []; self.light_defs = []; self.door_info = {}; self.groups = {}
        self.anchors = dict(P['anchors']); self.anchors.update({k: tuple(v) for k, v in (self.spec.get('anchors') or {}).items()})
        self.voxel_floor = False                      # VOXEL peint son propre plancher (plateau tournant en volumes) : b_sets ne l'échantillonne pas
        self.voxel_env = dict(floor=0x030303, floor_y=-1.32, bg=0x020306, fog_col=0x020306, fog=.02, ambient=.25, key=.2, exposure=1.0, sat=1.12)      # la salle 1,2 m sous la scène, noire

    def voxel_native(self):
        """VOXEL refait TOUT le lieu en blocs (voxelgpu/b_theatre.py) : aucune boîte PS1 n'est repeinte"""
        self.build(); return set(range(len(self.base.boxes))), []

    def voxel_bsets(self):
        from ...voxelgpu import b_theatre as BT
        return BT.native_bsets()

    def build(self):
        if self.base is None:
            self.base, self.idx = ps1_build(plan())
            self.base.floor_fn = lambda P_: floor_albedo(P_[:, 0], P_[:, 2]); self.base.ao_fn = _ao
        return self

    def scene(self, state, t, u):
        self.build(); sc = Scene(); sc.__dict__.update(self.base.__dict__); sc.boxes = list(self.base.boxes)
        ang = SL.turn_angles(state, t, u); sc.floor_fn = lambda P_, a=ang: floor_albedo(P_[:, 0], P_[:, 2], a)
        sc.turn = ang; self._sc = sc
        return sc

    def lights(self, state, t, u, cam_pos):
        """lumières du lieu SANS lumière de scène (avant `stage_frame`) : lavis bleu de nuit, bougies ; la dernière est la lumière douce de la caméra"""
        rec = SL.resolve(SL.BASE, state, {}, t, u)
        return self.stage_lights(rec, t, cam_pos)

    def stage_lights(self, rec, t, cam_pos):
        P = plan(); L = []
        wi = rec['wash_i']
        for p in WASH_POS:                                           # lavis : trois projecteurs larges de face, réglés sur l'aire de jeu (le haut du mur reste dans l'ombre)
            if wi > 1e-3:
                d = np.array([p[0] * .45, 0., 4.6]) - np.asarray(p); d /= np.linalg.norm(d)
                L.append((p, rec['wash'], 2.3 * wi, 18., False, (tuple(d.tolist()), math.cos(.5), math.cos(.86))))
            if wi > 1e-3 and p[0] != 0.:                           # le mur du fond et la galerie reçoivent un reste du lavis (la brique se lit)
                d = np.array([p[0] * -.2, 5.0, BACK]) - np.asarray(p); d /= np.linalg.norm(d)
                L.append((p, rec['wash'], .55 * wi, 22., False, (tuple(d.tolist()), math.cos(.3), math.cos(.62))))
        if rec['back_i'] > 1e-3: L.append((BACK_POS, rec['back'], 1.5 * rec['back_i'], 7.5))
        pr = rec['practicals']
        if pr > 1e-3:
            for i, g_ in enumerate(P['groups']):
                k = flicker(t, i) * pr * (.75 if g_['n'] > 3 else .45)
                L.append(((g_['x'], g_['y'], g_['z']), (1., .7, .4), k, 1.15 if g_['n'] > 3 else .8))
        for f in rec['follow']:
            if f['i'] <= 1e-3: continue
            src = np.asarray(f['src'], np.float32); d = np.asarray(f['aim'], np.float32) - src; d /= max(float(np.linalg.norm(d)), 1e-6); so = f.get('soft', 0.)
            half = f['half'] * (1 + .6 * so)
            L.append((tuple(src.tolist()), f['col'], 1.7 * f['i'] * (1 - .35 * so), 60., True, (tuple(d.tolist()), math.cos(half * (.86 - .6 * so)), math.cos(half))))
        for pl in rec.get('pools', ()):                                # disques au sol : douche verticale (le motif tacheté / l'anneau est peint dans le plancher)
            if pl['i'] <= 1e-3: continue
            half = math.atan2(pl['r'] * 1.05, 11.5)
            L.append(((pl['at'][0], 11.5, pl['at'][1]), pl['col'], 4.6 * pl['i'], 60., False, ((0., -1., 0.), math.cos(half * .9), math.cos(half))))
        cu = rec['curtain']
        if cu > 1e-3:
            for fx in P['fixtures']:
                if fx['row'] != 0: continue
                L.append((fx['p'], rec['curtain_col'], 2.6 * cu, 30., False, (fx['d'], math.cos(.12), math.cos(.2))))
        lum = .3 * wi + .2 * pr
        L.append(((cam_pos[0], cam_pos[1] + .25, cam_pos[2]), tuple(.5 + .5 * c for c in rec['wash']), .1 * lum, 2.6))
        return L

    def record(self, ctx, k, shot, who, T, u, g, state):
        """l'enregistrement de lumière de l'image (stage_light.evaluate) : plan k de l'épisode, `shot` = le plan effectif (coupes comprises)"""
        sp = ctx.tl.spans; prev_T = (sp[k - 1][1] - sp[k - 1][0]) if k > 0 else None
        return SL.evaluate(ctx.ep, ctx.ep['shots'], k, T, state, who, g, u, prev_T, shot=shot)

    def stage_frame(self, ctx, k, shot, who, cam, sc, L, nset, T, u, g, state):
        """LA lumière de scène de l'image -> ambiance, brume, lumières, lentilles, flammes, faisceaux ; rend la liste de lumières complète"""
        return self.apply_record(self.record(ctx, k, shot, who, T, u, g, state), cam, sc, L, nset, g)

    def apply_record(self, rec, cam, sc, L, nset, g):
        self.build(); self.last = rec
        amb = np.asarray(rec['ambient'], np.float32) * (.4 + .6 * min(1., rec['wash_i'] + .3 * rec['practicals']))
        sc.ambient = tuple(float(v) for v in amb); sc.fog = tuple(float(v) for v in rec['fog']); sc.fogk = .012 + .045 * rec['haze']
        bx = sc.boxes
        cu = rec['curtain']; cc = tuple(int(255 * min(1., v)) for v in rec['curtain_col'])
        for i in self.idx['lens']:
            b = bx[i]; bx[i] = Box(b.lo, b.hi, cc if cu > .02 else (20, 22, 26), emis=2.8 * cu if cu > .02 else 0., cast=False)
        pr = rec['practicals']
        if pr < .999:
            for key, e0 in (('flame', 3.2), ('glass', .95)):
                for i in self.idx[key]:
                    b = bx[i]; bx[i] = Box(b.lo, b.hi, tuple(int(c * 255 * max(.12, pr)) for c in b.col), emis=e0 * pr, cast=False)
        Ls = self.stage_lights(rec, g, cam[0])
        pools = [p_ for p_ in rec.get('pools', ()) if p_['i'] > 1e-3 and (p_['ring'] > .01 or p_['dapple'] > .01)]
        if pools: sc.floor_fn = functools.partial(_pool_floor, base=sc.floor_fn, pools=pools)
        sc.post_fn = functools.partial(beams_post, rec=rec)
        return Ls + list(L[nset:])


def _pool_floor(P_, base=None, pools=()):
    """le plancher sous un disque tacheté ou un anneau : le motif assombrit le bois là où le projecteur est masqué (gobo)"""
    alb, refl = base(P_); x, z = P_[:, 0], P_[:, 2]
    for p_ in pools:
        d = np.sqrt((x - p_['at'][0]) ** 2 + (z - p_['at'][1]) ** 2); m = d < p_['r'] * 1.1
        if not m.any(): continue
        k = np.ones(int(m.sum()), np.float32)
        if p_['dapple'] > .01: k *= 1 - p_['dapple'] * np.clip((vnoise2(x[m] * 2.4, z[m] * 2.4, 61) * .7 + vnoise2(x[m] * 6., z[m] * 6., 62) * .3 - .44) * 7., 0, 1)
        if p_['ring'] > .01: k *= np.clip((d[m] - p_['ring']) / .25, .15, 1)
        alb[m] = alb[m] * k[:, None]
    return alb, refl


def _ao(P, nrm, ib):
    y = P[:, 1]; ao = np.ones(len(y), np.float32)
    vert = (ib >= 0) & (np.abs(nrm[:, 1]) < .5)
    ao[vert] = .6 + .4 * np.clip(y[vert] / .6, 0, 1)
    return ao


# ================================================================================================ PS1 : faisceaux visibles dans la brume (passe à l'écran)
def beam_list(rec):
    """faisceaux visibles de l'image : [(sommet, direction, demi-angle, longueur, couleur, force)]"""
    out = []; haze = rec['haze']
    if haze <= 1e-3: return out
    cu = rec['curtain']
    if cu > 1e-3:
        for f in plan()['fixtures']: out.append((np.asarray(f['p'], float) + np.asarray(f['d']) * .05, np.asarray(f['d'], float), .12, 10.5, np.asarray(rec['curtain_col'], float), cu * haze * (1. if f['row'] == 0 else .8)))
    for f in rec['follow']:
        if f['i'] <= 1e-3 or f.get('soft', 0.) > .6: continue
        s = np.asarray(f['src'], float); t = np.asarray(f['aim'], float); d = t - s; L = float(np.linalg.norm(d)) + 1.2; d /= max(L, 1e-6)
        out.append((s, d, f['half'], L, np.asarray(f['col'], float), .3 * f['i'] * haze))
    return out


def beams_post(img, cam, rec=None):
    """ajoute la lumière diffusée par la brume le long de chaque faisceau (capsules projetées à l'écran, cachées par ce qui est devant)"""
    bl = beam_list(rec)
    if not bl or r3d.LAST_AUX is None: return img
    RH, RW = img.shape[:2]; pos, yaw, pitch, roll, fov = cam; pos = np.asarray(pos, float)
    th = math.tan(math.radians(fov) / 2) * r3d.FOV_K
    depth = np.asarray(r3d.LAST_AUX[1], np.float32).reshape(RH, RW); depth = np.where(np.isfinite(depth), depth, 1e9)
    out = img.copy(); n = 14
    for (A, d, half, L, col, k) in bl:
        ss = np.linspace(0., 1., n + 1); pts = A[None] + d[None] * (L * ss)[:, None]
        pr = [r3d.project(pos, yaw, pitch, roll, fov, p) for p in pts]
        sx = np.array([(p[0] + 1) / 2 * RW for p in pr]); sy = np.array([(1 - p[1]) / 2 * RH for p in pr]); zz = np.array([p[2] for p in pr])
        rad_w = .1 + L * ss * math.tan(half); rad_px = rad_w / np.maximum(zz, .05) / th * (RH / 2)
        dist = np.linalg.norm(pts - pos[None], axis=1)
        fall = (1 - ss) ** 1.3 * (.45 + .55 * np.exp(-ss * 2.5))
        ok = zz > .3
        if ok.sum() < 2: continue
        x0 = int(max(0, np.floor((sx - rad_px)[ok].min()))); x1 = int(min(RW, np.ceil((sx + rad_px)[ok].max()) + 1))
        y0 = int(max(0, np.floor((sy - rad_px)[ok].min()))); y1 = int(min(RH, np.ceil((sy + rad_px)[ok].max()) + 1))
        if x1 <= x0 or y1 <= y0: continue
        Y, X = np.mgrid[y0:y1, x0:x1].astype(np.float32) + .5; acc = np.zeros(X.shape, np.float32); D = depth[y0:y1, x0:x1]
        for j in range(n):
            if not (ok[j] and ok[j + 1]): continue
            ax, ay, bx_, by = sx[j], sy[j], sx[j + 1], sy[j + 1]; vx, vy = bx_ - ax, by - ay; ll = vx * vx + vy * vy + 1e-6
            tau = np.clip(((X - ax) * vx + (Y - ay) * vy) / ll, 0, 1); px = ax + vx * tau; py = ay + vy * tau
            dd = np.sqrt((X - px) ** 2 + (Y - py) ** 2); rp = rad_px[j] + (rad_px[j + 1] - rad_px[j]) * tau
            prof = np.clip(1 - (dd / np.maximum(rp, .5)) ** 2, 0, 1) ** 1.6
            fa = fall[j] + (fall[j + 1] - fall[j]) * tau; dz = dist[j] + (dist[j + 1] - dist[j]) * tau
            vis = np.where(D < dz - .4, .12, 1.)
            acc = np.maximum(acc, prof * fa * vis)
        out[y0:y1, x0:x1] += acc[..., None] * (col * .55 * k)[None, None]
    return out
