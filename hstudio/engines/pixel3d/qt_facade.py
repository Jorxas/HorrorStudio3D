"""Façades de quartier (V3, chantier « bâtiments et intérieurs variés ») : le PEINTRE de texture de PIXEL 3D.

Une façade n'est plus « un mur uni + des rectangles de fenêtres » : c'est la peau d'UN bâtiment décrit par son plan (`quartiers.plan_building`),
et le même plan est lu par le peintre VOXEL (`voxelgpu/b_quartiers.py`), qui construit les mêmes fenêtres, balcons et auvents en VRAIES boîtes.
Ici (PS1) tout ce qui n'est pas géométrie est PEINT, à 12 texels par mètre, avec un 5e canal d'émission (voir `r3d.shade`) :

  * la MATIÈRE du mur, par identité : briques à trois tons, crépi taché, bardage de planches, pierre appareillée, tôle ondulée, béton à panneaux
    colorés, mur-rideau de verre ;
  * des fenêtres de plusieurs FORMES (carrée, cintrée, haute, bandeau, hublot, vitre pleine), avec encadrement, linteau, appui, meneaux, volets ;
  * des INTÉRIEURS visibles : de nuit une pièce allumée (couleur de la pièce, rideaux, lampe avec abat-jour, silhouette, plante), de jour
    le ciel dans la vitre et le rideau derrière ;
  * le rez-de-chaussée : porte (numéro, lampe), vitrine éclairée avec ses rayons, rideau de fer rayé, arcade, hall vitré ;
  * les TAGS, les affiches, le lierre, les tuyaux de descente, les traînées d'humidité, le linge, les néons peints.

Aucun hasard non semé : tout vient de `rng` (graine du bâtiment). Les textures sont mises en cache par (bâtiment, face, résolution) ;
rien n'est reconstruit par image."""
import functools
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from ...paths import FONT_PIXEL

PPM = 12


def _c(c, f=1.):
    return tuple(int(max(0, min(255, v * f))) for v in c)


def _mx(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


@functools.lru_cache(maxsize=32)
def _font(px):
    return ImageFont.truetype(FONT_PIXEL, max(6, int(px)))


# ---------------------------------------------------------------------------------------------------- le mur
def _wall(kind, tw, th, ppm, col, trim, dark, rng, wear):
    yy, xx = np.mgrid[0:th, 0:tw]
    base = np.empty((th, tw, 3), np.float32)
    base[:] = col
    blot = np.kron(rng.random((th // 6 + 2, tw // 6 + 2)).astype(np.float32), np.ones((6, 6), np.float32))[:th, :tw]
    if kind == 'brick':
        ch = max(2, int(round(ppm * .25))); bw = ch * 2
        course = yy // ch; off = (course % 2) * (bw // 2); brick = (xx + off) // bw
        j = ((brick * 73856093) ^ (course * 19349663) ^ int(rng.integers(0, 9999))) % 1000 / 1000.
        tone = .78 + .42 * j + (blot - .5) * .12
        base = base * tone[..., None]
        mortar = ((yy % ch) == 0) | (((xx + off) % bw) == 0)
        base[mortar] = base[mortar] * .45 + np.array([218, 206, 184], np.float32) * .55
    elif kind == 'plaster':
        base = base * (.94 + (blot - .5) * .16)[..., None]
        s = max(4, int(ppm * 1.0))
        base[(yy % (s * 2)) == 0] *= .93                                           # joints de refend, très discrets
    elif kind == 'siding':
        bd = max(2, int(round(ppm * .2)))
        row = yy // bd; j = ((row * 2654435761) ^ int(rng.integers(0, 999))) % 1000 / 1000.
        base = base * (.9 + .16 * j)[..., None] * (.97 + (blot - .5) * .08)[..., None]
        base[(yy % bd) == 0] *= .62
        base[(yy % bd) == 1] *= 1.06
    elif kind == 'stone':
        bh = max(3, int(ppm * .6)); bwid = bh * 2
        row = yy // bh; off = (row % 2) * (bwid // 2)
        j = ((((xx + off) // bwid) * 83492791) ^ (row * 19349663)) % 1000 / 1000.
        base = base * (.9 + .16 * j + (blot - .5) * .08)[..., None]
        base[(yy % bh) == 0] *= .78; base[((xx + off) % bwid) == 0] *= .82
    elif kind == 'metal':
        base = base * (.9 + .12 * ((xx % 3) == 0))[..., None] * (.92 + (blot - .5) * .2)[..., None]
        base[(xx % 6) == 0] *= .8
        base[(yy % (ppm * 2)) == 0] *= .7                                           # les joints de plaques
    elif kind == 'panels':
        pw = max(6, int(ppm * 2.4)); ph = max(6, int(ppm * 3.0))
        base = base * (.95 + (blot - .5) * .1)[..., None]
        base[((xx % pw) == 0) | ((yy % ph) == 0)] *= .68
    elif kind == 'glass':
        base[:] = _c(dark, .9)
    if wear > 0 and kind != 'glass':                                                # traînées d'humidité sous les appuis
        runs = np.zeros(tw, np.float32)
        for _ in range(max(1, tw // 36)):
            c0 = int(rng.integers(0, tw)); w = int(rng.integers(1, 4)); runs[max(0, c0 - w):c0 + w] = .35 + .65 * rng.random()
        fall = np.clip(1 - yy / (th * .55), 0, 1) ** 1.3
        base *= (1 - .15 * wear * runs[None, :] * fall)[..., None]
    return np.clip(base, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------------------------------- les fenêtres
SKY_DAY = ((118, 168, 220), (196, 222, 244))
ROOMS = ((255, 214, 148), (255, 188, 130), (255, 226, 176), (210, 226, 255), (255, 176, 190), (190, 255, 214), (255, 238, 140), (226, 196, 255))


def _interior(d, de, g, cell, night, rng, I, ppm):
    """le verre d'une fenêtre : g = (x0, y0, x1, y1) en texels. Une pièce vue de la rue."""
    x0, y0, x1, y1 = g
    w, h = x1 - x0, y1 - y0
    if w < 2 or h < 2: return
    lit = night and cell.get('lit')
    office = cell.get('t') == 'pane'                                                 # mur-rideau : des bureaux, pas des chambres (ni rideaux, ni lampes)
    cu = None if office else cell.get('curt')
    if office:
        if lit:
            room = (226, 238, 255) if cell.get('who', 0) % 2 else (255, 240, 200)
            d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=_c(room, .86)); de.rectangle([x0, y0, x1 - 1, y1 - 1], fill=235)
            d.rectangle([x0, y0, x1 - 1, y0 + max(1, h // 8)], fill=room)                          # la rampe de plafonniers
            for k in range(x0 + 1, x1 - 2, max(3, w // 3)):                                        # bureaux, écrans, une silhouette
                d.rectangle([k, y1 - max(2, h // 4), k + max(2, w // 4), y1 - 1], fill=_c(room, .45)); de.rectangle([k, y1 - max(2, h // 4), k + max(2, w // 4), y1 - 1], fill=0)
                d.rectangle([k + 1, y1 - max(3, h // 3), k + 2, y1 - max(2, h // 4) - 1], fill=(90, 160, 255)); de.rectangle([k + 1, y1 - max(3, h // 3), k + 2, y1 - max(2, h // 4) - 1], fill=255)
            if cell.get('who') == 2 and w >= 6:
                sx = x0 + w // 2; d.ellipse([sx - 1, y1 - h // 2, sx + 1, y1 - h // 2 + 2], fill=(40, 44, 60)); d.rectangle([sx - 2, y1 - h // 2 + 3, sx + 2, y1 - 1], fill=(40, 44, 60)); de.rectangle([sx - 2, y1 - h // 2, sx + 2, y1 - 1], fill=0)
        elif night:
            for k in range(h):
                d.line([(x0, y0 + k), (x1 - 1, y0 + k)], fill=_mx((34, 52, 90), (14, 20, 40), k / max(1, h - 1)))
        else:
            a, b = I.get('glass_day') or SKY_DAY
            for k in range(h): d.line([(x0, y0 + k), (x1 - 1, y0 + k)], fill=_mx(a, b, k / max(1, h - 1)))
            d.line([(x0, y0 + h // 3), (x1 - 1, y0 + h // 3)], fill=_mx(a, (255, 255, 255), .35))
        return
    if lit:
        room = cell.get('in') or ROOMS[0]
        top = _c(room, .72)
        for k in range(h):                                                          # plafond plus sombre, sol plus chaud
            t = k / max(1, h - 1)
            d.line([(x0, y0 + k), (x1 - 1, y0 + k)], fill=_mx(top, room, min(1., t * 1.6)))
        de.rectangle([x0, y0, x1 - 1, y1 - 1], fill=255)
        who = cell.get('who', 0)
        if cu:                                                                      # rideaux de chaque côté
            cw = max(1, int(w * .28))
            d.rectangle([x0, y0, x0 + cw - 1, y1 - 1], fill=_c(cu, .95)); d.rectangle([x1 - cw, y0, x1 - 1, y1 - 1], fill=_c(cu, .95))
            for k in range(x0 + 1, x0 + cw, 2): d.line([(k, y0), (k, y1 - 1)], fill=_c(cu, .8))
            for k in range(x1 - cw + 1, x1, 2): d.line([(k, y0), (k, y1 - 1)], fill=_c(cu, .8))
            de.rectangle([x0, y0, x0 + cw - 1, y1 - 1], fill=150); de.rectangle([x1 - cw, y0, x1 - 1, y1 - 1], fill=150)
        if who == 1 and w >= 6:                                                      # une lampe : pied, abat-jour, ampoule
            lx = x0 + w // 2 + int(rng.integers(-w // 6, w // 6 + 1)); sh = cell.get('shade') or (230, 90, 70)
            d.rectangle([lx, y1 - max(2, h // 3), lx, y1 - 1], fill=(60, 50, 44))
            d.polygon([(lx - 2, y1 - max(2, h // 3)), (lx + 2, y1 - max(2, h // 3)), (lx + 3, y1 - max(2, h // 3) - 3), (lx - 3, y1 - max(2, h // 3) - 3)], fill=sh)
            de.rectangle([lx - 3, y1 - max(2, h // 3) - 3, lx + 3, y1 - max(2, h // 3)], fill=255)
        elif who == 2 and w >= 6 and h >= 8:                                         # une silhouette devant la lumière
            sx = x0 + w // 2 + int(rng.integers(-w // 5, w // 5 + 1)); hr = max(2, w // 7)
            d.ellipse([sx - hr, y1 - h // 2 - hr, sx + hr, y1 - h // 2 + hr], fill=(36, 30, 40)); de.ellipse([sx - hr, y1 - h // 2 - hr, sx + hr, y1 - h // 2 + hr], fill=0)
            d.polygon([(sx - hr * 2, y1 - 1), (sx + hr * 2, y1 - 1), (sx + hr, y1 - h // 2 + hr), (sx - hr, y1 - h // 2 + hr)], fill=(36, 30, 40))
            de.polygon([(sx - hr * 2, y1 - 1), (sx + hr * 2, y1 - 1), (sx + hr, y1 - h // 2 + hr), (sx - hr, y1 - h // 2 + hr)], fill=0)
        elif who == 3 and w >= 5:                                                    # une plante sur l'appui
            px = x0 + int(w * (.25 if rng.random() < .5 else .72))
            d.rectangle([px - 1, y1 - 3, px + 1, y1 - 1], fill=(170, 84, 56)); d.ellipse([px - 3, y1 - 8, px + 3, y1 - 3], fill=(40, 150, 70))
        elif who == 4 and w >= 6:                                                    # la télé : lueur bleue qui danse
            tx = x0 + w // 2 - w // 4
            d.rectangle([tx, y0 + h // 2, tx + w // 2, y1 - h // 6], fill=(120, 170, 255)); de.rectangle([tx, y0 + h // 2, tx + w // 2, y1 - h // 6], fill=255)
    elif night:                                                                     # éteint : le noir bleuté de la nuit, un reflet
        dk = (18, 24, 42)
        d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=dk)
        if cu and w >= 6: d.rectangle([x0, y0, x0 + max(1, int(w * .22)) - 1, y1 - 1], fill=_c(cu, .28))
        for k in range(0, max(1, w), 2):
            xx = x0 + k + h // 3
            if x0 <= xx < x1: d.line([(xx, y0), (max(x0, xx - h // 2), y1 - 1)], fill=(34, 42, 64))
    else:                                                                           # jour : le ciel dans la vitre, le rideau derrière
        a, b = I.get('glass_day') or SKY_DAY
        for k in range(h):
            d.line([(x0, y0 + k), (x1 - 1, y0 + k)], fill=_mx(a, b, k / max(1, h - 1)))
        if cu:
            cw = max(1, int(w * (.35 if cell.get('half') else .22)))
            d.rectangle([x0, y0, x0 + cw - 1, y1 - 1], fill=_c(cu, .9)); d.rectangle([x1 - cw, y0, x1 - 1, y1 - 1], fill=_c(cu, .9))
        if cell.get('who') == 3 and w >= 5:
            px = x0 + int(w * .3); d.rectangle([px - 1, y1 - 3, px + 1, y1 - 1], fill=(170, 84, 56)); d.ellipse([px - 3, y1 - 8, px + 3, y1 - 3], fill=(48, 150, 76))
        for k in range(0, max(1, w), 3):                                            # reflet en diagonale
            xx = x0 + k + h // 3
            if x0 <= xx < x1: d.line([(xx, y0), (max(x0, xx - h // 2), y1 - 1)], fill=_mx(b, (255, 255, 255), .5))


def _window(d, de, rect, cell, night, rng, I, ppm, trim, dark, shape='sq'):
    """rect = (x0, y0, x1, y1) en texels (haut = y petit). Encadrement, vitre, meneaux, appui, linteau."""
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    if w < 3 or h < 3:
        d.rectangle([x0, y0, x1, y1], fill=(60, 70, 90)); return
    fr = max(1, int(round(ppm * .07)))
    ft = cell.get('frame') or trim
    sh = cell.get('shut')
    if sh:                                                                          # volets de chaque côté, avec leurs lamelles
        sw = max(2, int(w * .46))
        for (a0, a1) in ((x0 - sw - fr, x0 - fr), (x1 + fr, x1 + sw + fr)):
            d.rectangle([a0, y0, a1 - 1, y1 - 1], fill=sh)
            for k in range(y0 + 1, y1 - 1, 2): d.line([(a0 + 1, k), (a1 - 2, k)], fill=_c(sh, .72))
    d.rectangle([x0 - fr, y0 - fr, x1 + fr - 1, y1 + fr - 1], fill=ft)             # encadrement
    g = (x0, y0, x1, y1)
    if shape == 'arch':
        r = w // 2
        d.rectangle([x0 - fr, y0 + r - fr, x1 + fr - 1, y1 + fr - 1], fill=ft)
        d.pieslice([x0 - fr, y0 - fr, x1 + fr - 1, y0 + 2 * r + fr], 180, 360, fill=ft)
        _interior(d, de, (x0, y0 + r, x1, y1), cell, night, rng, I, ppm)
        d.pieslice([x0, y0, x1 - 1, y0 + 2 * r], 180, 360, fill=_mx(I.get('glass_day', SKY_DAY)[0], (20, 26, 44), 1. if (night and not cell.get('lit')) else 0.) if not (night and cell.get('lit')) else _c(cell.get('in') or ROOMS[0], .8))
        if night and cell.get('lit'): de.pieslice([x0, y0, x1 - 1, y0 + 2 * r], 180, 360, fill=230)
        d.line([((x0 + x1) // 2, y0), ((x0 + x1) // 2, y1 - 1)], fill=ft)
    elif shape == 'round':
        d.ellipse([x0 - fr, y0 - fr, x1 + fr - 1, y1 + fr - 1], fill=ft)
        cx, cy, r = (x0 + x1) // 2, (y0 + y1) // 2, min(w, h) // 2
        _interior(d, de, (cx - r, cy - r, cx + r, cy + r), cell, night, rng, I, ppm)
        d.ellipse([cx - r - 1, cy - r - 1, cx + r, cy + r], outline=ft)
        for xy in ((x0 - 1, y0 - 1, x0 + r // 2 + 1, y0 + r // 2 + 1), (x1 - r // 2 - 1, y1 - r // 2 - 1, x1 + 1, y1 + 1)):
            d.rectangle(xy, fill=ft)
    else:
        _interior(d, de, g, cell, night, rng, I, ppm)
        mc = (x0 + x1) // 2
        if shape in ('sq', 'tall') and w >= 5:
            d.line([(mc, y0), (mc, y1 - 1)], fill=ft)                                # meneau
            if h >= 9: d.line([(x0, y0 + h // 3), (x1 - 1, y0 + h // 3)], fill=ft)   # traverse
            de.line([(mc, y0), (mc, y1 - 1)], fill=0)
            if h >= 9: de.line([(x0, y0 + h // 3), (x1 - 1, y0 + h // 3)], fill=0)
        elif shape == 'strip':
            for k in range(x0 + w // 4, x1, max(3, w // 4)):
                d.line([(k, y0), (k, y1 - 1)], fill=ft); de.line([(k, y0), (k, y1 - 1)], fill=0)
    sill = cell.get('sill') or _c(trim, 1.06)
    d.rectangle([x0 - fr - 1, y1 + fr, x1 + fr, y1 + fr + max(1, fr - 0 )], fill=sill)         # appui
    d.line([(x0 - fr - 1, y1 + fr + max(1, fr) + 1), (x1 + fr, y1 + fr + max(1, fr) + 1)], fill=_c(sill, .55))   # son ombre
    if cell.get('lintel'): d.rectangle([x0 - fr - 2, y0 - fr - max(2, fr + 1), x1 + fr + 1, y0 - fr - 1], fill=_c(cell['lintel'], 1.0))
    if cell.get('box'):                                                              # jardinière fleurie
        by = y1 + fr + max(2, fr) + 1
        d.rectangle([x0 - 1, by, x1, by + 2], fill=(112, 70, 44))
        for k in range(x0, x1, 2):
            d.rectangle([k, by - 2, k + 1, by - 1], fill=cell['box'][(k // 2) % len(cell['box'])])
        d.rectangle([x0, by - 3, x1 - 1, by - 3], fill=(44, 130, 62))


# ---------------------------------------------------------------------------------------------------- le rez-de-chaussée
def _door(d, de, rect, cell, night, rng, I, ppm, trim, dark):
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    if w < 4 or h < 6: return
    fr = max(1, int(round(ppm * .1)))
    d.rectangle([x0 - fr, y0 - fr, x1 + fr - 1, y1 - 1], fill=_c(trim, .97))
    col = cell.get('col') or (104, 66, 44)
    d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=col)
    for (a, b, c_, e) in ((x0 + 1, y0 + 1, x1 - 2, y0 + h // 2 - 1), (x0 + 1, y0 + h // 2 + 1, x1 - 2, y1 - 2)):
        if c_ > a and e > b: d.rectangle([a, b, c_, e], outline=_c(col, .7))
    if w >= 7:                                                                        # petit carreau en haut
        d.rectangle([x0 + 2, y0 + 2, x1 - 3, y0 + max(3, h // 4)], fill=(60, 80, 100) if not (night and cell.get('lit')) else (255, 220, 150))
        if night and cell.get('lit'): de.rectangle([x0 + 2, y0 + 2, x1 - 3, y0 + max(3, h // 4)], fill=230)
    d.rectangle([x1 - 3, y0 + h * 55 // 100, x1 - 2, y0 + h * 55 // 100 + 1], fill=(228, 200, 120))   # poignée
    d.rectangle([x0 - fr - 1, y1 - 1, x1 + fr, y1], fill=_c(trim, .8))               # seuil
    if cell.get('lamp'):                                                              # la lampe au-dessus, et sa flaque de lumière
        lx = (x0 + x1) // 2
        d.rectangle([lx - 1, y0 - fr - 4, lx + 1, y0 - fr - 2], fill=(255, 232, 170)); de.rectangle([lx - 1, y0 - fr - 4, lx + 1, y0 - fr - 2], fill=255 if night else 0)
        if night:
            for k in range(1, 7):
                a = max(0, 90 - k * 13)
                d.line([(lx - k, y0 - fr - 2 + k), (lx + k, y0 - fr - 2 + k)], fill=_mx((0, 0, 0), (255, 226, 160), 0))
                de.line([(lx - k, y0 - fr - 2 + k), (lx + k, y0 - fr - 2 + k)], fill=a // 3)


def _shop(d, de, rect, cell, night, rng, I, ppm, trim, dark):
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    if w < 8 or h < 8: return
    band = max(3, h // 5)
    acc = cell.get('col') or (160, 40, 40)
    d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=_c(dark, .9))
    d.rectangle([x0, y0, x1 - 1, y0 + band - 1], fill=acc)                          # bandeau (l'enseigne lisible est un objet 3D)
    d.line([(x0, y0 + band), (x1 - 1, y0 + band)], fill=_c(acc, .6))
    if cell.get('neon') and night:
        d.rectangle([x0 + 2, y0 + band // 2 - 1, x1 - 3, y0 + band // 2 + 1], fill=cell['neon']); de.rectangle([x0 + 2, y0 + band // 2 - 1, x1 - 3, y0 + band // 2 + 1], fill=255)
    gx0, gy0, gx1, gy1 = x0 + 2, y0 + band + 2, x1 - 2, y1 - max(3, h // 6)
    if gx1 > gx0 and gy1 > gy0:
        lit = cell.get('lit', True)
        if night and lit or not night:
            glass = (255, 226, 168) if night else _mx(SKY_DAY[0], SKY_DAY[1], .4)
            d.rectangle([gx0, gy0, gx1 - 1, gy1 - 1], fill=glass)
            if night: de.rectangle([gx0, gy0, gx1 - 1, gy1 - 1], fill=235)
            gh = gy1 - gy0
            for k in range(2):                                                         # rayons : barres de produits colorés
                yy = gy0 + gh // 3 * (k + 1)
                d.line([(gx0, yy), (gx1 - 1, yy)], fill=_c(dark, 1.1))
                xx = gx0 + 1
                while xx < gx1 - 2:
                    pw = int(rng.integers(1, 3)); ph = int(rng.integers(2, max(3, gh // 3)))
                    pc = ROOMS[int(rng.integers(0, len(ROOMS)))] if rng.random() < .5 else I['accents'][int(rng.integers(0, len(I['accents'])))]
                    d.rectangle([xx, yy - ph, xx + pw - 1, yy - 1], fill=pc); xx += pw + int(rng.integers(0, 2))
            if cell.get('who') == 2:                                                    # un client
                sx = (gx0 + gx1) // 2 + int(rng.integers(-3, 4)); d.rectangle([sx - 1, gy1 - gh // 2, sx + 1, gy1 - 1], fill=(40, 34, 44)); d.ellipse([sx - 1, gy1 - gh // 2 - 3, sx + 1, gy1 - gh // 2 - 1], fill=(40, 34, 44))
        else:
            d.rectangle([gx0, gy0, gx1 - 1, gy1 - 1], fill=(22, 26, 40))
        mc = (gx0 + gx1) // 2
        d.line([(mc, gy0), (mc, gy1 - 1)], fill=_c(dark, .8)); de.line([(mc, gy0), (mc, gy1 - 1)], fill=0)
    d.rectangle([x0, y1 - max(3, h // 6), x1 - 1, y1 - 1], fill=_c(acc, .6))        # soubassement


def _garage(d, de, rect, cell, night, rng, I, ppm, trim, dark):
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    if w < 6 or h < 6: return
    d.rectangle([x0 - 1, y0 - 1, x1, y1 - 1], fill=_c(dark, .8))
    col = cell.get('col') or (96, 112, 120)
    d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=col)
    for k in range(y0, y1, 2): d.line([(x0, k), (x1 - 1, k)], fill=_c(col, .78))   # lames
    hz = max(2, h // 8)
    for k in range(x0, x1, hz * 2):                                                  # bande de danger jaune et noire
        d.polygon([(k, y1 - hz), (k + hz, y1 - hz), (k + hz // 2, y1 - 1), (k - hz // 2, y1 - 1)], fill=(244, 196, 30))
    if cell.get('lamp'): d.rectangle([(x0 + x1) // 2 - 1, y0 - 3, (x0 + x1) // 2 + 1, y0 - 2], fill=(255, 240, 180)); de.rectangle([(x0 + x1) // 2 - 1, y0 - 3, (x0 + x1) // 2 + 1, y0 - 2], fill=255 if night else 0)


def _arch(d, de, rect, cell, night, rng, I, ppm, trim, dark):
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    if w < 6 or h < 8: return
    r = w // 2
    d.rectangle([x0 - 1, y0 + r, x1, y1 - 1], fill=_c(trim, 1.0)); d.pieslice([x0 - 1, y0 - 1, x1, y0 + 2 * r + 1], 180, 360, fill=_c(trim, 1.0))
    inner = (40, 32, 36) if not (night and cell.get('lit')) else (255, 200, 130)
    d.rectangle([x0 + 1, y0 + r, x1 - 2, y1 - 1], fill=inner); d.pieslice([x0 + 1, y0 + 1, x1 - 2, y0 + 2 * r - 1], 180, 360, fill=inner)
    if night and cell.get('lit'):
        de.rectangle([x0 + 1, y0 + r, x1 - 2, y1 - 1], fill=210); de.pieslice([x0 + 1, y0 + 1, x1 - 2, y0 + 2 * r - 1], 180, 360, fill=210)
    col = cell.get('col')
    if col: d.rectangle([x0 + 2, y0 + h // 3, x1 - 3, y1 - 1], fill=col)             # la porte de bois peinte, dans l'arcade
    if cell.get('plant'): d.ellipse([x0 + 1, y1 - 7, x0 + 5, y1 - 2], fill=(40, 150, 70)); d.rectangle([x0 + 2, y1 - 3, x0 + 4, y1 - 1], fill=(176, 90, 58))


def _lobby(d, de, rect, cell, night, rng, I, ppm, trim, dark):
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    if w < 6 or h < 6: return
    d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=_c(dark, .85))
    lit = night and cell.get('lit', True)
    d.rectangle([x0 + 1, y0 + 1, x1 - 2, y1 - 1], fill=(255, 236, 190) if lit else _mx(SKY_DAY[0], SKY_DAY[1], .5))
    if lit: de.rectangle([x0 + 1, y0 + 1, x1 - 2, y1 - 1], fill=235)
    for k in range(x0 + 1, x1 - 1, max(3, w // 3)):
        d.line([(k, y0), (k, y1 - 1)], fill=_c(dark, .7)); de.line([(k, y0), (k, y1 - 1)], fill=0)
    d.line([(x0, y0 + h // 4), (x1 - 1, y0 + h // 4)], fill=_c(dark, .7)); de.line([(x0, y0 + h // 4), (x1 - 1, y0 + h // 4)], fill=0)


# ---------------------------------------------------------------------------------------------------- les extras peints
def _tag(d, rng, x0, y0, x1, y1, ppm):
    """un tag : trait épais à la bombe, en deux couleurs, avec un dégoulinement"""
    pal = ((255, 60, 150), (40, 220, 255), (255, 220, 40), (150, 255, 80), (255, 120, 40), (180, 120, 255), (250, 250, 250))
    c1 = pal[int(rng.integers(0, len(pal)))]; c2 = pal[int(rng.integers(0, len(pal)))]
    n = int(rng.integers(4, 7)); xs = np.linspace(x0, x1, n); ys = y0 + (y1 - y0) * (.5 + .4 * np.sin(np.linspace(0, 5, n) + rng.random() * 6))
    pts = [(int(a), int(b)) for a, b in zip(xs, ys)]
    d.line(pts, fill=_c(c2, .45), width=3)
    d.line(pts, fill=c1, width=2)
    for (a, b) in pts[1::2]:                                                         # dégoulinures
        d.line([(a, b), (a, b + int(rng.integers(2, 6)))], fill=c1)
    d.line([(x0, y1 + 1), (x1, y1 + 1)], fill=c2)


def _poster(d, rng, x0, y0, w, h, I):
    pc = I['accents'][int(rng.integers(0, len(I['accents'])))]
    d.rectangle([x0, y0, x0 + w - 1, y0 + h - 1], fill=(244, 240, 228))
    d.rectangle([x0 + 1, y0 + 1, x0 + w - 2, y0 + h // 2], fill=pc)
    d.line([(x0 + 1, y0 + h - 3), (x0 + w - 2, y0 + h - 3)], fill=(90, 90, 100))


def _ivy(d, rng, tw, th, ppm, col=(52, 122, 60)):
    for _ in range(int(tw // ppm) + 1):
        x = int(rng.integers(0, tw)); hgt = int(rng.integers(ppm * 2, ppm * 5))
        for k in range(0, hgt, 2):
            ox = int(rng.integers(-2, 3)); d.rectangle([x + ox, th - 1 - k, x + ox + 1, th - 1 - k + 1], fill=_c(col, .8 + .4 * rng.random()))


def _pipe(d, de, x, th, ppm, col):
    d.line([(x, 0), (x, th - 1)], fill=col)
    for y in range(ppm, th, ppm * 3): d.line([(x - 1, y), (x + 1, y)], fill=_c(col, .7))


# ---------------------------------------------------------------------------------------------------- la façade entière
def paint(plan, face, night, ppm=PPM, role='front'):
    """plan = le plan d'UNE face (voir quartiers.plan_face) -> tableau (h, w, 5) uint8 : RVB + alpha 255 + émission.

    `plan` : W, H, kind (matière), col, trim, dark, bays, floors, fy (hauteur du bas de chaque étage), fhs, cells[f][b], I (identité), seed, near, extras."""
    I = plan['I']
    W_, H_ = plan['W'], plan['H']
    tw = max(8, min(960, int(round(W_ * ppm)))); th = max(8, min(1920, int(round(H_ * ppm))))
    rng = np.random.default_rng((plan['seed'] * 131 + face * 17 + 5) & 0x7fffffff)
    col, trim, dark = plan['col'], plan['trim'], plan['dark']
    img = Image.fromarray(_wall(plan['kind'], tw, th, ppm, col, trim, dark, rng, plan.get('wear', 1.)))
    em = Image.new('L', (tw, th), 0)
    d = ImageDraw.Draw(img); de = ImageDraw.Draw(em)
    sx = tw / W_; sy = th / H_
    Y = lambda y: th - 1 - int(round(y * sy))                                      # mètres depuis le sol -> texel (haut = 0)
    X = lambda u: int(round(u * sx))
    # bandes d'étage et corniche
    for (y, h, c) in plan.get('bands', []):
        d.rectangle([0, Y(y + h) + 1, tw - 1, Y(y)], fill=c)
    if plan.get('plinth'):
        d.rectangle([0, Y(plan['plinth'][0]), tw - 1, th - 1], fill=plan['plinth'][1])
    for (u0, u1, c) in plan.get('pilasters', []):
        d.rectangle([X(u0), 0, X(u1), th - 1], fill=c)
        d.line([(X(u0), 0), (X(u0), th - 1)], fill=_c(c, .78)); d.line([(X(u1), 0), (X(u1), th - 1)], fill=_c(c, .78))
    bays = plan['bays']; bw = W_ / bays
    for f, row in enumerate(plan['cells']):
        y0 = plan['fy'][f]; fh = plan['fhs'][f]
        for b, cell in enumerate(row):
            t = cell['t']
            if t == 'blank': continue
            cx = (b + .5) * bw
            ww = cell.get('w') or plan['ww']; hh = cell.get('h') or plan['wh']
            u0, u1 = cx - ww / 2, cx + ww / 2
            if t in ('win', 'bdoor'):
                sill = plan['sill'] if t == 'win' else .12
                wy0, wy1 = y0 + sill, y0 + sill + (hh if t == 'win' else min(fh - .25, 2.15))
                rect = (X(u0), Y(wy1), X(u1), Y(wy0))
                _window(d, de, rect, cell, night, rng, I, ppm, trim, dark, cell.get('shape', plan['shape']))
            elif t == 'door':
                _door(d, de, (X(u0), Y(y0 + 2.2), X(u1), Y(y0 + .05)), cell, night, rng, I, ppm, trim, dark)
            elif t == 'shop':
                _shop(d, de, (X(cx - bw / 2 + .12), Y(y0 + fh - .25), X(cx + bw / 2 - .12), Y(y0 + .05)), cell, night, rng, I, ppm, trim, dark)
            elif t == 'garage':
                _garage(d, de, (X(cx - bw / 2 + .3), Y(y0 + min(fh - .3, 3.2)), X(cx + bw / 2 - .3), Y(y0 + .05)), cell, night, rng, I, ppm, trim, dark)
            elif t == 'arch':
                _arch(d, de, (X(u0), Y(y0 + 2.6), X(u1), Y(y0 + .05)), cell, night, rng, I, ppm, trim, dark)
            elif t == 'lobby':
                _lobby(d, de, (X(cx - bw / 2 + .2), Y(y0 + fh - .2), X(cx + bw / 2 - .2), Y(y0 + .05)), cell, night, rng, I, ppm, trim, dark)
            elif t == 'pane':                                                       # mur-rideau : une vitre par travée et par étage
                px0, px1 = X(cx - bw / 2 + .04), X(cx + bw / 2 - .04)
                py0, py1 = Y(y0 + fh - .1), Y(y0 + .45)
                _interior(d, de, (px0, py0, px1, py1), cell, night, rng, I, ppm)
            elif t == 'panel':                                                      # panneau de couleur d'une cité (le mur entre les fenêtres)
                d.rectangle([X(cx - bw / 2 + .05), Y(y0 + fh - .05), X(cx + bw / 2 - .05), Y(y0 + .05)], fill=cell['col'])
            if cell.get('ac') and (plan['far'] or 'ac' in cell.get('flat', ())):
                a0 = X(cx - .35); d.rectangle([a0, Y(y0 + 1.0), a0 + int(.7 * sx), Y(y0 + .55)], fill=(226, 228, 230)); d.rectangle([a0 + 2, Y(y0 + .9), a0 + int(.7 * sx) - 3, Y(y0 + .8)], fill=(90, 96, 104))
            if cell.get('bal') and (plan['far'] or 'bal' in cell.get('flat', ())):                                     # balcon peint : dalle et rambarde
                bb = cell['bal']; a0 = X(cx - bb['w'] / 2)
                d.rectangle([a0, Y(y0 + .14), a0 + int(bb['w'] * sx), Y(y0 + .02)], fill=bb['slab'])
                d.rectangle([a0, Y(y0 + 1.1), a0 + int(bb['w'] * sx), Y(y0 + .14)], outline=bb['rail'])
    if plan.get('pipes'):
        for u in plan['pipes']: _pipe(d, de, X(u), th, ppm, plan['dark'] if plan['kind'] != 'brick' else (70, 68, 74))
    if plan.get('ivy'): _ivy(d, rng, tw, th, ppm)
    for (u, y, w, h) in plan.get('posters', []): _poster(d, rng, X(u), Y(y + h), max(3, int(w * sx)), max(4, int(h * sy)), I)
    for (u0, y0, u1, y1) in plan.get('tags', []): _tag(d, rng, X(u0), Y(y1), X(u1), Y(y0), ppm)
    for (u, y, c, wlen) in plan.get('neons', []):                                    # néons peints : un tube (émission pleine)
        if night:
            d.line([(X(u), Y(y)), (X(u + wlen), Y(y))], fill=c, width=2); de.line([(X(u), Y(y)), (X(u + wlen), Y(y))], fill=255, width=2)
    for (u, y, wl, c) in plan.get('strings', []):                                    # guirlande de lampions
        if night:
            for k in range(int(wl * 2)):
                xx = X(u + k * .5); yy = Y(y) + int(np.sin(k * .9) * 2) + 2
                d.rectangle([xx, yy, xx + 1, yy + 1], fill=c[k % len(c)]); de.rectangle([xx, yy, xx + 1, yy + 1], fill=255)
    return np.dstack([np.asarray(img), np.full((th, tw), 255, np.uint8), np.asarray(em)])
