"""Intérieurs à palette et détails, VERSION VOXEL NATIVE (règle des deux versions : docs/REGLE_DEUX_VERSIONS.md).

Les détails de vie posés par `pixel3d/qi_lieux.dress` (livres, plantes, cadres, rideaux, tapis, lampes, vaisselle, coussins, vases, tabourets, vitrine à gâteaux, rayons, mannequins, boîtes aux
lettres, ascenseur, escalier...) existent ici en AUTRE version : des volumes à la grille du peintre (blocs de 8 à 15 cm, aucune texture sauf un mot), pas les boîtes PS1 retraduites.
  PS1    un rayon de livres = UNE boîte + une texture de dos colorés ; un cadre = deux boîtes + un tableau peint ; un tapis = une dalle + un motif peint
  VOXEL  un rayon de livres = des blocs de couleurs et de hauteurs différentes ; un cadre = un cadre de blocs + un tableau en pixels-blocs ; un tapis = des bandes concentriques empilées
La coque de la pièce (murs, sol échantillonné, plafond, plinthes) reste la traduction de la version PS1 (les couleurs de la palette y sont) : seuls les OBJETS de vie sont natifs.

`native_hide(set)` : boîtes PS1 non converties (groupe `qi`) ; `native_bsets(set)` : accessoires `bset` VOXEL posés."""
import math
import numpy as np
from ..engines.pixel3d.r3d import B
from ..engines.pixel3d import sets as S, interieurs as I
from . import b_props as BP

K = BP.PROP_SCALE
BOOKS = ((200, 50, 50), (50, 90, 170), (240, 200, 60), (60, 140, 90), (240, 240, 232), (210, 110, 40), (110, 70, 150), (30, 30, 40), (60, 170, 180))
WOOD = (150, 94, 56)


def _c(c, f=1.): return tuple(int(max(0, min(255, v * f))) for v in c)
def _t(c, d): return tuple(int(v) for v in c) if c else d


def v_books(p):
    w = float(p.get('w', .7)); rng = np.random.default_rng(int(p.get('seed', 1))); out = []; x = -w / 2
    while x < w / 2 - .06:
        bw = .07 + .05 * rng.random(); bh = .18 + .12 * rng.random(); out.append(B((x, 0, -.12), (bw, bh, .18), BOOKS[int(rng.integers(0, len(BOOKS)))])); x += bw + .005
    return out


def v_bookcase(p):
    col = _t(p.get('color'), WOOD); w = float(p.get('w', .9)); h = float(p.get('h', 1.9)); rng = np.random.default_rng(int(p.get('seed', 1))); n = int(p.get('shelves', 5)); gap = (h - .08) / n
    out = [B((-w / 2, 0, -.16), (w, h, .06), _c(col, .75)), B((-w / 2, 0, -.18), (.08, h, .34), col), B((w / 2 - .08, 0, -.18), (.08, h, .34), col), B((-w / 2, h - .08, -.18), (w, .08, .34), col)]
    for i in range(n):
        y = i * gap; out.append(B((-w / 2, y, -.18), (w, .06, .34), col))
        if rng.random() < .75:
            x = -w / 2 + .1
            while x < w / 2 - .18:
                bw = .07 + .05 * rng.random(); bh = .2 + .1 * rng.random(); out.append(B((x, y + .06, -.3), (bw, min(bh, gap - .1), .2), BOOKS[int(rng.integers(0, len(BOOKS)))])); x += bw + .005
        else: out += [B((-.1, y + .06, -.26), (.2, .3, .16), BOOKS[int(rng.integers(0, len(BOOKS)))]), B((-.04, y + .36, -.2), (.08, .1, .08), (50, 140, 70))]
    return out


def v_plant(p):
    k = p.get('kind', 'monstera'); pot = _t(p.get('pot'), (176, 92, 60)); s = float(p.get('size', 1.)); g1, g2 = (44, 140, 66), (70, 170, 90)
    out = [B((-.2 * s, 0, -.2 * s), (.4 * s, .1 * s, .4 * s), _c(pot, .8)), B((-.17 * s, .1 * s, -.17 * s), (.34 * s, .3 * s, .34 * s), pot)]
    if k == 'cactus': out += [B((-.1 * s, .4 * s, -.1 * s), (.2 * s, .8 * s, .2 * s), (70, 150, 84)), B((.1 * s, .6 * s, -.05 * s), (.2 * s, .1 * s, .1 * s), (70, 150, 84)), B((.2 * s, .6 * s, -.05 * s), (.1 * s, .3 * s, .1 * s), (70, 150, 84)), B((-.05 * s, 1.2 * s, -.05 * s), (.1 * s, .1 * s, .1 * s), (240, 90, 140))]
    elif k == 'palm':
        out += [B((-.05 * s, .4 * s, -.05 * s), (.1 * s, .9 * s, .1 * s), (110, 84, 56))]
        for a in range(4): ang = a * math.pi / 2 + .4; out.append(B((math.cos(ang) * .35 * s - .2 * s, 1.3 * s + .05 * (a % 2), math.sin(ang) * .35 * s - .06), (.4 * s, .1, .12), g1 if a % 2 else g2))
    elif k == 'ficus': out += [B((-.04 * s, .4 * s, -.04 * s), (.08 * s, .7 * s, .08 * s), (110, 84, 56)), B((-.3 * s, 1.05 * s, -.3 * s), (.6 * s, .5 * s, .6 * s), g1), B((-.2 * s, 1.55 * s, -.2 * s), (.4 * s, .3 * s, .4 * s), g2)]
    else: out += [B((-.25 * s, .4 * s, -.25 * s), (.5 * s, .4 * s, .5 * s), g1), B((-.15 * s, .8 * s, -.1 * s), (.4 * s, .3 * s, .4 * s), g2), B((.1 * s, .55 * s, .15 * s), (.2 * s, .3 * s, .2 * s), g1)]
    return out


def v_frame(p):
    w = float(p.get('w', .7)); h = float(p.get('h', .85)); fr = _t(p.get('frame'), (40, 30, 24)); cols = [tuple(c) for c in (p.get('cols') or [(232, 170, 52), (52, 116, 108), (240, 232, 214)])]
    nx, ny = 5, 6; bw = (w - .12) / nx; bh = (h - .12) / ny; rng = np.random.default_rng(int(p.get('seed', 1))); art = p.get('art', 'soleil')
    out = [B((-w / 2, 0, -.04), (w, h, .04), fr), B((-w / 2 + .06, .06, -.065), (w - .12, h - .12, .025), (240, 236, 224))]
    for j in range(ny):
        for i in range(nx):
            if art == 'rayures': c = cols[i % 2] if j > 1 else cols[2 % len(cols)]
            elif art == 'soleil': c = cols[0] if ((i - 2) ** 2 + (j - 1.2) ** 2 < 2.2) else cols[1] if j > 3 else cols[2 % len(cols)]
            elif art == 'geo': c = cols[int(rng.integers(0, len(cols)))]
            else: c = cols[1] if j > 3 else cols[0] if (j > 1 and abs(i - 2) <= (j - 2)) else cols[2 % len(cols)]
            out.append(B((-w / 2 + .06 + i * bw, .06 + j * bh, -.085), (bw, bh, .02), c))
    return out


def v_curtain(p):
    w = float(p.get('w', 1.8)); h = float(p.get('h', 2.3)); col = _t(p.get('color'), (240, 226, 196)); pw = max(.4, w * .3); out = [B((-w / 2 - .08, h, -.16), (w + .16, .08, .08), (60, 50, 44))]
    for side in (-1, 1):
        for k in range(int(pw / .1)):
            x = (-w / 2 + k * .1) if side < 0 else (w / 2 - pw + k * .1); out.append(B((x, .1 + (k % 2) * .05, -.12 - (k % 2) * .03), (.1, h - .1 - (k % 2) * .05, .1), _c(col, .86 + .2 * (k % 2))))
    return out


def v_rug(p):
    w = float(p.get('w', 2.0)); d = float(p.get('d', 1.4)); c1, c2 = (p.get('cols') or ((232, 170, 52), (52, 116, 108))); c1 = _t(c1, (232, 170, 52)); c2 = _t(c2, (52, 116, 108))
    out = [B((-w / 2, 0, -d / 2), (w, .025, d), c1), B((-w / 2 + .12, .025, -d / 2 + .12), (w - .24, .02, d - .24), c2), B((-w / 2 + .26, .045, -d / 2 + .26), (w - .52, .02, d - .52), c1)]
    if p.get('pattern') == 'rayures':
        for k in range(1, 5): out.append(B((-w / 2 + .26 + k * (w - .52) / 5, .065, -d / 2 + .26), (.07, .015, d - .52), c2))
    else: out.append(B((-w / 4, .065, -d / 6), (w / 2, .015, d / 3), c2))
    return out


def v_lamp(p):
    sh = _t(p.get('shade'), (240, 170, 60)); s = float(p.get('size', 1.))
    if p.get('kind') == 'table': return [B((-.1, 0, -.1), (.2, .08, .2), (60, 50, 44)), B((-.03, .08, -.03), (.06, .26, .06), (60, 50, 44)), B((-.15, .34, -.15), (.3, .22, .3), sh, emis=1.1)]
    return [B((-.15, 0, -.15), (.3, .08, .3), (50, 46, 44)), B((-.03, .08, -.03), (.06, 1.45, .06), (50, 46, 44)), B((-.22, 1.5, -.22), (.44, .32, .44), sh, emis=1.2), B((-.16, 1.82, -.16), (.32, .06, .32), _c(sh, .8), emis=.5)]


def v_tableware(p):
    k = p.get('kind', 'dinner'); a = _t(p.get('acc'), (232, 170, 52)); W_ = (240, 236, 224)
    if k == 'fruit': return [B((-.18, 0, -.18), (.36, .08, .36), W_), B((-.12, .08, -.1), (.12, .12, .12), (230, 60, 50)), B((.02, .08, -.05), (.12, .12, .12), (250, 200, 50)), B((-.04, .08, .06), (.12, .12, .12), (110, 190, 70))]
    if k == 'coffee': return [B((-.06, 0, -.06), (.12, .2, .12), a), B((.16, 0, 0), (.1, .08, .1), W_), B((-.26, 0, -.1), (.1, .08, .1), W_), B((-.15, 0, .14), (.3, .02, .2), W_)]
    return [B((-.42, 0, -.14), (.28, .03, .28), W_), B((.14, 0, -.14), (.28, .03, .28), W_), B((-.36, .03, -.08), (.16, .02, .16), a), B((.2, .03, -.08), (.16, .02, .16), a), B((-.58, 0, -.04), (.08, .14, .08), W_), B((-.04, 0, .08), (.08, .26, .08), (60, 140, 90))]


def v_cushions(p):
    cols = [tuple(c) for c in (p.get('cols') or [(232, 170, 52), (52, 116, 108), (240, 226, 196)])]; w = float(p.get('w', 1.6)); n = max(2, int(w / .55)); out = []
    for i in range(n): out.append(B((-w / 2 + .1 + i * (w - .5) / max(1, n - 1), 0, -.14), (.42, .4, .14), cols[i % len(cols)]))
    return out


def v_vase(p):
    col = _t(p.get('color'), (60, 140, 190)); fl = [(236, 60, 90), (250, 210, 50), (250, 250, 250), (200, 90, 230)]
    return [B((-.08, 0, -.08), (.16, .28, .16), col), B((-.03, .28, -.03), (.06, .12, .06), (50, 140, 70))] + [B((-.14 + .09 * i, .4 + .04 * (i % 2), -.05 + .03 * (i % 3)), (.1, .1, .1), fl[i % 4]) for i in range(4)]


def v_stool(p):
    col = _t(p.get('color'), (232, 170, 52)); return [B((-.2, .62, -.2), (.4, .1, .4), col), B((-.04, .08, -.04), (.08, .54, .08), (60, 60, 66)), B((-.18, 0, -.18), (.36, .08, .36), (60, 60, 66))]


def v_menu(p):
    from ..engines.pixel3d.assets import text_tex
    w = float(p.get('w', .9)); h = float(p.get('h', 1.2)); t = [str(x) for x in (p.get('text') or ['MENU', 'CAFÉ 2', 'THÉ 3', 'GÂTEAU 4'])][:5]
    tx = text_tex(t, (72, 96), (250, 244, 226), (34, 44, 40, 255), 8, 6)
    return [B((-w / 2, 0, -.05), (w, h, .05), (130, 90, 56)), B((-w / 2 + .07, .07, -.075), (w - .14, h - .14, .025), (34, 44, 40), tex={'-z': tx})]


def v_cakecase(p):
    cols = ((236, 90, 120), (250, 214, 110), (130, 80, 56), (240, 240, 232), (110, 190, 110)); out = [B((-.6, 0, -.3), (1.2, .5, .6), (210, 210, 206)), B((-.6, .5, -.3), (1.2, .08, .6), (240, 240, 236))]
    for i in range(5): out += [B((-.54 + i * .22, .58, -.1), (.18, .06, .18), (240, 236, 224)), B((-.5 + i * .22, .64, -.06), (.1, .12, .1), cols[i % 5])]
    out += [B((-.6, .58, -.3), (.04, .5, .6), (150, 190, 214), emis=.25), B((.56, .58, -.3), (.04, .5, .6), (150, 190, 214), emis=.25), B((-.6, 1.08, -.3), (1.2, .04, .6), (210, 210, 206))]
    return out


def v_pendants(p):
    cols = [tuple(c) for c in (p.get('cols') or [(240, 170, 60), (240, 230, 200), (232, 90, 70)])]; y = float(p.get('y', 2.6)); out = []
    for i, dx in enumerate((-.4, 0., .4)):
        hh = .5 + .25 * (i % 2); out += [B((dx - .02, y - hh, -.02), (.04, hh, .04), (40, 40, 44)), B((dx - .16, y - hh - .22, -.16), (.32, .22, .32), cols[i % len(cols)], emis=1.3)]
    return out


def v_shelving(p):
    w = float(p.get('w', 1.4)); h = float(p.get('h', 1.7)); rng = np.random.default_rng(int(p.get('seed', 1))); pal = ((230, 60, 50), (250, 200, 50), (80, 170, 80), (70, 130, 220), (240, 240, 232), (240, 130, 40), (180, 90, 200))
    out = [B((-w / 2, 0, -.2), (.06, h, .4), (150, 150, 156)), B((w / 2 - .06, 0, -.2), (.06, h, .4), (150, 150, 156)), B((-w / 2, 0, -.2), (w, h, .05), (110, 100, 94)), B((-w / 2, h, -.2), (w, .06, .4), (150, 150, 156))]
    for r in range(4):
        y = .18 + r * (h - .3) / 4; out.append(B((-w / 2 + .06, y, -.2), (w - .12, .04, .4), (150, 150, 156)))
        x = -w / 2 + .1
        while x < w / 2 - .2: bw = .1 + .08 * rng.random(); out.append(B((x, y + .04, -.28), (bw, .14 + .1 * rng.random(), .16), pal[int(rng.integers(0, len(pal)))])); x += bw + .02
    return out


def v_crates(p):
    cols = ((230, 60, 50), (250, 200, 50), (80, 170, 80), (240, 130, 40)); out = []
    for i in range(3):
        x = -.7 + i * .7; out += [B((x - .3, 0, -.25), (.6, .3, .5), (150, 106, 66)), B((x - .22, .3, -.17), (.18, .12, .18), cols[(i + int(p.get('seed', 0))) % 4]), B((x + .02, .3, -.1), (.18, .12, .18), cols[(i + 1) % 4]), B((x - .1, .3, .02), (.18, .12, .16), cols[(i + 2) % 4])]
    return out


def v_mannequin(p):
    col = _t(p.get('color'), (232, 90, 120)); return [B((-.2, 0, -.2), (.4, .08, .4), (50, 50, 56)), B((-.03, .08, -.03), (.06, .82, .06), (50, 50, 56)), B((-.2, .9, -.12), (.4, .36, .24), _c(col, .7)), B((-.18, 1.26, -.11), (.36, .4, .22), col), B((-.07, 1.66, -.07), (.14, .16, .14), (232, 214, 190))]


def v_mailboxes(p):
    cols_ = int(p.get('cols', 4)); w = cols_ * .34; rng = np.random.default_rng(int(p.get('seed', 1))); pal = ((230, 60, 50), (250, 200, 50), (80, 170, 80), (70, 130, 220), (240, 130, 40), (180, 90, 200), (240, 240, 232), (60, 180, 180))
    out = [B((-w / 2, 0, -.14), (w, .9, .14), (60, 60, 68))]
    for r in range(3):
        for c_ in range(cols_): out += [B((-w / 2 + .03 + c_ * .34, .04 + r * .29, -.2), (.28, .24, .06), pal[int(rng.integers(0, len(pal)))]), B((-w / 2 + .1 + c_ * .34, .14 + r * .29, -.23), (.14, .03, .03), (30, 30, 36))]
    return out


def v_elevator(p):
    col = _t(p.get('color'), (176, 180, 188)); return [B((-.8, 0, -.14), (1.6, 2.4, .14), (50, 50, 56)), B((-.55, 0, -.24), (.55, 2.15, .1), col), B((0, 0, -.24), (.55, 2.15, .1), col), B((-.04, 0, -.26), (.08, 2.15, .04), (50, 50, 56)), B((-.3, 2.2, -.24), (.6, .16, .08), (20, 10, 6), emis=1.2), B((.68, .95, -.2), (.12, .24, .06), (255, 190, 70), emis=1.5)]


def v_stairs(p):
    n = int(p.get('n', 10)); w = float(p.get('w', 1.2)); rise = float(p.get('rise', .18)); run = float(p.get('run', .28)); col = _t(p.get('color'), (196, 150, 110)); rail = _t(p.get('rail'), (60, 60, 66))
    out = [B((-w / 2, 0, -(n - i) * run), (w, (i + 1) * rise, run), col if i % 2 == 0 else _c(col, .88)) for i in range(n)]
    for i in range(0, n, 2): out.append(B((w / 2, 0, -(n - i) * run), (.06, (i + 1) * rise + .9, .06), rail))
    out += [B((w / 2, .9, -n * run), (.06, n * rise + .06, .06), rail) if False else B((w / 2, .9 + rise, -n * run), (.06, .06, n * run), rail)]
    return out


def v_doormat(p):
    col = _t(p.get('color'), (52, 116, 108)); return [B((-.5, 0, -.3), (1.0, .03, .6), col), B((-.4, .03, -.22), (.8, .02, .44), _c(col, 1.3))]


VOX = {'qi_books': v_books, 'qi_bookcase': v_bookcase, 'qi_plant': v_plant, 'qi_frame': v_frame, 'qi_curtain': v_curtain, 'qi_rug': v_rug, 'qi_lamp': v_lamp, 'qi_tableware': v_tableware, 'qi_cushions': v_cushions,
       'qi_vase': v_vase, 'qi_stool': v_stool, 'qi_menu': v_menu, 'qi_cakecase': v_cakecase, 'qi_pendants': v_pendants, 'qi_shelving': v_shelving, 'qi_crates': v_crates, 'qi_mannequin': v_mannequin,
       'qi_mailboxes': v_mailboxes, 'qi_elevator': v_elevator, 'qi_stairs': v_stairs, 'qi_doormat': v_doormat}


def _props(st):
    return list(st.spec.get('props', [])) + list(getattr(st, 'qi_props', []))


def native_hide(st):
    """indices des boîtes PS1 non converties : les détails de vie (groupe `qi`)"""
    hide = set((getattr(st, 'groups', None) or {}).get('qi', []))
    hide |= set(getattr(st, 'qi_boxes', ()))                                                                  # l'appartement d'Ascenseur Zéro (classe à part) enregistre ses boîtes ici
    return hide


def native_bsets(st):
    boxes = []
    for p in _props(st):
        if p.get('group') == 'qi' and p['type'] in VOX:
            boxes += S.place(VOX[p['type']](p), float(p['at'][0]), float(p['at'][1]), int(p.get('rot', 0)), float(p.get('y', 0.)))
    return [BP.boxes_to_bset(boxes, 0, 0., 0., 0., K, {})] if boxes else []
