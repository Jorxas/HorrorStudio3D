"""Quartiers à identité, VERSION VOXEL NATIVE (règle des deux versions : docs/REGLE_DEUX_VERSIONS.md).

Le PLAN d'un bâtiment (`pixel3d/quartiers.building` : grille de travées, fenêtres et leur intérieur, détails) est commun aux deux styles ; l'exécution
est différente :
  PS1    la façade est une TEXTURE (fenêtres, volets, vitrines peints, 12 texels/m) + quelques boîtes (balcons, auvents, enseignes)
  VOXEL  la façade est de la GÉOMÉTRIE : cadre, vitre en saillie, meneaux, appui, rideaux, lampe, silhouette, volets, jardinières, balcons à
         garde-corps plein, auvents de toile, enseignes, toits à marches fines avec lucarnes. Le mur lui-même porte sa matière (briques, bardage,
         crépi, pierre, tôle, panneaux) en plaque texturée posée sur la face : `qt_facade.paint` avec TOUTES les travées vides, à 6 texels/m.
Rien n'est repeint depuis la version PS1 : les boîtes sont d'autres boîtes (autres tailles, autres saillies), seules les COULEURS et les POSITIONS viennent du plan.

`native_hide(set)` dit quelles boîtes PS1 le peintre ne doit PAS convertir ; `native_bsets(set)` rend les accessoires `bset` VOXEL (repère de VOXEL déjà posé)."""
import math
import numpy as np
from ..engines.pixel3d.r3d import B, C, M_FABRIC
from ..engines.pixel3d import quartiers as Q, qt_facade as F, qt_props as P, sets as S
from . import b_props as BP

K = BP.PROP_SCALE
TREES = {'tree_round': 'oak_tree', 'blossom_tree': 'cherry_tree', 'autumn_tree': 'autumn_tree', 'birch': 'birch_tree', 'palm': 'palm_tree', 'pine': 'pine_tree'}
DK = (30, 30, 36)


def _sh(c, f): return tuple(int(max(0, min(255, v * f))) for v in c)


def vb(out, f, u0, u1, y0, y1, p0, p1, col, emis=0., tex=None, sheen=False):
    """une boîte posée sur la façade : u le long de la façade (vue de la rue), y en hauteur, p la saillie vers la rue (de p0 à p1, en mètres)"""
    cx, cz, sx, sz = f.box(u0, u1, -p1, -p0)
    out.append(B((cx - sx / 2, y0, cz - sz / 2), (max(sx, .02), max(y1 - y0, .02), max(sz, .02)), col, emis=emis, tex=tex, grain=.05))


# ------------------------------------------------------------------------------------------------- la matière du mur (plaque texturée)
def _wall_tex(d, role, night, face):
    plan = Q.plan_face(d, role, night)
    plan = dict(plan, cells=[[{'t': 'blank'}] * plan['bays'] for _ in plan['cells']], far=False)
    return F.paint(plan, face, night, ppm=6)[..., :4].copy()


# ------------------------------------------------------------------------------------------------- une fenêtre en volume
def _window(out, f, d, cell, uc, y0, I, night, kind='win'):
    ww = cell.get('w') or I['ww']; wh = I['wh']; sill = I['sill']
    trim = d['trim']; lit = night and cell.get('lit')
    if kind == 'bdoor': sill = .12; wh = min(2.15, d['fh'] - .3)
    if kind == 'pane':
        bw = d['W'] / d['bays']; u0, u1 = uc - bw / 2 + .05, uc + bw / 2 - .05; g0, g1 = y0 + .45, y0 + d['fh'] - .12
        col = (226, 238, 255) if lit else ((34, 52, 90) if night else (150, 196, 232))
        vb(out, f, u0, u1, g0, g1, 0, .16, col, emis=1.3 if lit else 0.)
        vb(out, f, u0 - .04, u0 + .04, g0, g1, 0, .22, trim); vb(out, f, u0, u1, g1 - .04, g1 + .08, 0, .24, trim)
        if lit and cell.get('who') == 2: vb(out, f, uc - .25, uc + .25, g0, g0 + 1.2, .17, .22, (40, 44, 60))
        return
    u0, u1 = uc - ww / 2, uc + ww / 2; g0, g1 = y0 + sill, y0 + sill + wh
    fr = .12
    shape = cell.get('shape', I['shape'])
    vb(out, f, u0 - fr, u1 + fr, g0 - fr, g1 + fr, 0, .10, cell.get('frame') or trim)                          # le cadre (en saillie)
    room = cell.get('in') or (255, 214, 148)
    if lit: gcol, ge = room, 1.5
    elif night: gcol, ge = (22, 28, 46), 0.
    else: gcol, ge = (140, 184, 226), 0.
    vb(out, f, u0, u1, g0, g1, 0, .15, gcol, emis=ge)                                                       # la vitre
    if shape == 'arch': vb(out, f, uc - ww * .3, uc + ww * .3, g1 + fr, g1 + fr + .22, 0, .12, cell.get('frame') or trim)    # clef d'arc
    cu = cell.get('curt')
    if cu and shape != 'pane':
        cw = ww * (.3 if lit else .22 if not cell.get('half') else .34)
        for (a0, a1) in ((u0, u0 + cw), (u1 - cw, u1)): vb(out, f, a0, a1, g0 + .04, g1 - .04, .15, .2, cu, emis=.3 if lit else 0.)
    mc = uc
    vb(out, f, mc - .03, mc + .03, g0, g1, .15, .22, _sh(trim, .7)); vb(out, f, u0, u1, g0 + wh * .62, g0 + wh * .62 + .05, .15, .22, _sh(trim, .7))
    who = cell.get('who', 0)
    if lit and who == 1: vb(out, f, uc - .07, uc + .07, g0, g0 + .5, .16, .2, (60, 50, 44)); vb(out, f, uc - .2, uc + .2, g0 + .5, g0 + .78, .16, .3, cell.get('shade') or (230, 90, 70), emis=1.2)
    elif lit and who == 2: vb(out, f, uc - .12, uc + .12, g0 + wh * .38, g0 + wh * .62, .16, .22, (36, 30, 40)); vb(out, f, uc - .24, uc + .24, g0, g0 + wh * .38, .16, .22, (36, 30, 40))
    elif who == 3: vb(out, f, uc - .35, uc - .13, g0, g0 + .2, .16, .38, (176, 92, 60)); vb(out, f, uc - .4, uc - .08, g0 + .2, g0 + .6, .16, .42, (44, 150, 70))
    elif lit and who == 4: vb(out, f, uc - ww * .25, uc + ww * .25, g0 + wh * .3, g0 + wh * .6, .16, .2, (120, 170, 255), emis=1.3)
    vb(out, f, u0 - fr - .08, u1 + fr + .08, g0 - fr - .09, g0 - fr, 0, .3, _sh(trim, 1.05))                       # l'appui
    if cell.get('shut'):                                                                                     # volets
        for (a0, a1) in ((u0 - fr - ww * .48, u0 - fr), (u1 + fr, u1 + fr + ww * .48)): vb(out, f, a0, a1, g0 - .05, g1 + .05, 0, .12, cell['shut']); vb(out, f, a0 + .04, a1 - .04, g0, g1, .12, .15, _sh(cell['shut'], .78))
    if cell.get('box'):
        vb(out, f, u0 - .05, u1 + .05, g0 - fr - .3, g0 - fr - .1, 0, .34, (112, 70, 44))
        for k, c in enumerate(cell['box']): vb(out, f, u0 + k * ww / 3 + .02, u0 + (k + 1) * ww / 3 - .02, g0 - fr - .1, g0 - fr + .18, .06, .3, c if k != 1 else (44, 140, 64))
    if cell.get('ac') and kind == 'win': vb(out, f, uc + ww * .55, uc + ww * .55 + .7, g0 - .45, g0 + .05, 0, .42, (226, 229, 232)); vb(out, f, uc + ww * .55 + .08, uc + ww * .55 + .62, g0 - .38, g0 - .1, .42, .46, (60, 66, 76))
    if cell.get('bal'):
        bl = cell['bal']; bwid = bl['w']
        vb(out, f, uc - bwid / 2, uc + bwid / 2, y0 - .02, y0 + .18, 0, 1.0, bl['slab'])
        if bl['kind'] == 'solid': vb(out, f, uc - bwid / 2, uc + bwid / 2, y0 + .18, y0 + 1.0, .9, 1.0, bl['rail']); vb(out, f, uc - bwid / 2, uc - bwid / 2 + .1, y0 + .18, y0 + 1.0, 0, 1.0, bl['rail']); vb(out, f, uc + bwid / 2 - .1, uc + bwid / 2, y0 + .18, y0 + 1.0, 0, 1.0, bl['rail'])
        else:
            vb(out, f, uc - bwid / 2, uc + bwid / 2, y0 + .98, y0 + 1.06, .92, 1.0, bl['rail'])
            for k in range(5): vb(out, f, uc - bwid / 2 + k * (bwid - .1) / 4, uc - bwid / 2 + k * (bwid - .1) / 4 + .1, y0 + .18, y0 + 1.0, .9, 1.0, bl['rail'])
        if bl['plants']: vb(out, f, uc - bwid / 2 + .15, uc - bwid / 2 + .5, y0 + .18, y0 + .62, .5, .85, (50, 150, 70)); vb(out, f, uc + bwid / 2 - .5, uc + bwid / 2 - .15, y0 + .18, y0 + .5, .5, .85, (236, 64, 96))
        if bl['laundry']:
            for k, c in enumerate(((240, 240, 236), (240, 90, 100), (90, 140, 230), (250, 210, 70))): vb(out, f, uc - bwid / 2 + .12 + k * .38, uc - bwid / 2 + .4 + k * .38, y0 + 1.1, y0 + 1.6, .92, .96, c)


def _ground(out, f, d, cell, uc, I, night):
    bw = d['W'] / d['bays']; gf = d['gf']; t = cell['t']; trim = d['trim']; col = cell.get('col') or (150, 60, 50)
    if t == 'door':
        vb(out, f, uc - .62, uc + .62, 0, 2.35, 0, .12, _sh(trim, .96)); vb(out, f, uc - .5, uc + .5, 0, 2.2, 0, .18, col)
        vb(out, f, uc - .4, uc + .4, 1.25, 2.05, .18, .21, _sh(col, .72)); vb(out, f, uc - .4, uc + .4, .15, 1.1, .18, .21, _sh(col, .72))
        vb(out, f, uc + .3, uc + .38, 1.0, 1.1, .2, .3, (228, 200, 120))
        if cell.get('lamp'): vb(out, f, uc - .12, uc + .12, 2.5, 2.74, 0, .3, (255, 232, 170), emis=1.6 if night else .6)
    elif t == 'shop':
        u0, u1 = uc - bw / 2 + .12, uc + bw / 2 - .12
        vb(out, f, u0, u1, 0, gf - .2, 0, .1, _sh(d['dark'], .9))
        lit = cell.get('lit', True)
        vb(out, f, u0 + .15, u1 - .15, .75, gf - 1.1, .1, .17, (255, 226, 168) if (night and lit) else (150, 184, 214), emis=1.6 if (night and lit) else 0.)
        for k in range(3): vb(out, f, u0 + .15 + k * (u1 - u0 - .3) / 2 - .03, u0 + .15 + k * (u1 - u0 - .3) / 2 + .03, .75, gf - 1.1, .17, .24, _sh(d['dark'], .8))
        for sh in (1.2, 1.85):
            vb(out, f, u0 + .2, u1 - .2, sh, sh + .05, .17, .3, _sh(d['dark'], 1.2)) if night and lit else None
        for k in range(4): vb(out, f, u0 + .3 + k * (u1 - u0 - .6) / 4, u0 + .3 + k * (u1 - u0 - .6) / 4 + .22, 1.25, 1.25 + .3 + .15 * (k % 3), .22, .3, I['accents'][k % len(I['accents'])], emis=.4 if night else 0.)
        vb(out, f, u0, u1, 0, .75, .1, .2, _sh(col, .6))
        tx = P._sign_tex(cell['name'], P._txtw(cell['name']), 16, (252, 244, 214), tuple(col))
        vb(out, f, u0 - .05, u1 + .05, gf - 1.0, gf - .35, 0, .24, col, emis=1.0 if night else 0., tex={f.front: tx})
        if cell.get('awn'):
            c1, c2 = cell['awn']
            for k in range(5):
                a0 = u0 - .05 + k * (u1 - u0 + .1) / 5
                vb(out, f, a0, a0 + (u1 - u0 + .1) / 5, gf - .38 - .12 * 0, gf - .3, .24, 1.2, c1 if k % 2 == 0 else c2)
                vb(out, f, a0, a0 + (u1 - u0 + .1) / 5, gf - .62, gf - .38, 1.14, 1.2, c1 if k % 2 == 0 else c2)
    elif t == 'garage':
        u0, u1 = uc - bw / 2 + .3, uc + bw / 2 - .3; h = min(gf - .3, 3.2)
        vb(out, f, u0 - .1, u1 + .1, 0, h + .1, 0, .12, _sh(d['dark'], .8))
        for k in range(8): vb(out, f, u0, u1, k * h / 8, (k + 1) * h / 8 - .04, .12, .2, col)
        for k in range(int((u1 - u0) / .8)): vb(out, f, u0 + k * .8, u0 + k * .8 + .4, 0, .3, .2, .24, (244, 196, 30) if k % 2 == 0 else DK)
    elif t == 'arch':
        u0, u1 = uc - I['ww'] / 2, uc + I['ww'] / 2
        vb(out, f, u0 - .1, u1 + .1, 0, 2.7, 0, .1, trim); vb(out, f, u0, u1, 0, 2.55, .1, .16, (40, 32, 36) if not (night and cell.get('lit')) else (255, 200, 130), emis=1.2 if (night and cell.get('lit')) else 0.)
        vb(out, f, u0 + .1, u1 - .1, 2.45, 2.62, .16, .2, (40, 32, 36))
        if cell.get('col'): vb(out, f, u0 + .1, u1 - .1, 0, 1.9, .16, .22, cell['col'])
    elif t == 'lobby':
        u0, u1 = uc - bw / 2 + .2, uc + bw / 2 - .2
        vb(out, f, u0, u1, 0, gf - .3, 0, .12, _sh(d['dark'], .85)); vb(out, f, u0 + .1, u1 - .1, 0, gf - .5, .12, .18, (255, 236, 190) if (night and cell.get('lit', True)) else (150, 190, 226), emis=1.4 if (night and cell.get('lit', True)) else 0.)
        for k in range(1, 4): vb(out, f, u0 + k * (u1 - u0) / 4 - .04, u0 + k * (u1 - u0) / 4 + .04, 0, gf - .5, .18, .24, _sh(d['dark'], .7))
    elif t == 'win': _window(out, f, d, cell, uc, 0., I, night)


# ------------------------------------------------------------------------------------------------- le toit
def _roof(out, f, d, night):
    I = Q.IDENTITES[d['ident']]; W, D, H = d['W'], d['D'], d['H']; kind = d['roof']; rc = d['roof_col']; trim = d['trim']; body = d['body']
    def blk(u0, u1, v0, v1, y0, y1, col, emis=0.):
        cx, cz, sx, sz = f.box(u0, u1, v0, v1); out.append(B((cx - sx / 2, y0, cz - sz / 2), (sx, y1 - y0, sz), col, emis=emis, grain=.05))
    blk(-.3, W + .3, -.3, D + .3, H - .18, H + .02, trim)                                                      # corniche en saillie
    top = H
    def pile(n, rise, along, ov=.35, ridge=.5, v0=0., col2=None):
        h = rise / n
        for k in range(n):
            t = k / n; col = rc if k % 2 == 0 else _sh(rc, .86)
            if along == 'u': a0, a1, b0, b1 = -ov + t * (W / 2 - ridge / 2 + ov), W + ov - t * (W / 2 - ridge / 2 + ov), v0 - ov, D + ov
            elif along == 'v': a0, a1, b0, b1 = -ov, W + ov, v0 - ov + t * ((D - v0) / 2 - ridge / 2 + ov), D + ov - t * ((D - v0) / 2 - ridge / 2 + ov)
            else: a0, a1, b0, b1 = -ov + t * (W / 2 - ridge / 2 + ov), W + ov - t * (W / 2 - ridge / 2 + ov), -ov + t * (D / 2 - ridge / 2 + ov), D + ov - t * (D / 2 - ridge / 2 + ov)
            blk(a0, a1, b0, b1, H + k * h, H + (k + 1) * h + .02, col)
        return H + rise
    if kind in ('gable', 'gable_front', 'hip', 'terracotta'):
        if kind == 'gable': top = pile(7, min(W * .36 + .6, 4.4), 'v')
        elif kind == 'gable_front':
            rise = min(W * .4 + .6, 4.6); top = pile(7, rise, 'u', v0=.4)
            n = 7
            for k in range(n): t = k / n; blk(t * W / 2, W - t * W / 2, -.06, .42, H + k * rise / n, H + (k + 1) * rise / n + .02, body if k % 2 else _sh(body, 1.05))
            blk(W / 2 - .35, W / 2 + .35, -.12, .3, H + rise * .28, H + rise * .28 + .7, (255, 214, 140) if night else (130, 170, 214), emis=1.4 if night else 0.)
        elif kind == 'hip': top = pile(7, min(min(W, D) * .32 + .5, 4.0), 'both', ridge=.7)
        else: top = pile(4, 1.6, 'both', ridge=1.4)
        for k, u in enumerate(np.linspace(W * .22, W * .78, 2 if W > 6 else 1)):                                       # lucarnes de toit
            if kind in ('gable', 'hip') and W > 5:
                blk(u - .6, u + .6, D * .22, D * .22 + .9, H + .5, H + 1.7, body); blk(u - .45, u + .45, D * .22 - .02, D * .22 + .02, H + .75, H + 1.5, (255, 214, 140) if night else (130, 170, 214), emis=1.3 if night else 0.)
                blk(u - .8, u + .8, D * .22 - .1, D * .22 + 1.0, H + 1.7, H + 1.9, rc)
    elif kind == 'sawtooth':
        n = max(2, int(D / 4.2)); tw = D / n
        for k in range(n):
            for s in range(4): blk(.3, W - .3, k * tw + s * tw * .2, k * tw + tw * .92, H + .4 + s * .45, H + .4 + (s + 1) * .45, _sh(rc, .8 + .08 * s))
            blk(.3, W - .3, k * tw + tw * .86, k * tw + tw * .96, H + .4, H + 2.2, (255, 226, 150) if night else (170, 220, 232), emis=1.0 if night else 0.)
        top = H + 2.2
    elif kind in ('stepped', 'stepped_glass'):
        y = H + .02
        for sc, hh in ([(.86, 2.8), (.66, 2.6), (.42, 3.2)] if kind == 'stepped' else [(.82, 2.4), (.5, 2.0)]):
            u0, u1 = W * (1 - sc) / 2, W * (1 + sc) / 2; v0, v1 = D * (1 - sc) / 2, D * (1 + sc) / 2
            blk(u0, u1, v0, v1, y, y + hh, body if kind == 'stepped' else _sh(body, .95)); blk(u0 - .12, u1 + .12, v0 - .12, v1 + .12, y + hh - .2, y + hh, trim)
            if kind == 'stepped':
                for uu in np.linspace(u0 + .3, u1 - .3, max(2, int((u1 - u0) / 1.1))): blk(uu - .08, uu + .08, v0 - .1, v0, y + .3, y + hh - .5, trim, emis=.8 if night else 0.)
            y += hh
        if kind == 'stepped':
            blk(W / 2 - .15, W / 2 + .15, D / 2 - .15, D / 2 + .15, y, y + 4.4, trim, emis=1.2 if night else 0.); top = y + 4.4
        else: top = y
    elif kind == 'dome':
        blue = I.get('blue_dome', (30, 100, 200)); r = min(W, D) * .36; cu, cv = W / 2, D / 2
        blk(0, W, 0, D, H, H + .55, trim); blk(cu - r - .3, cu + r + .3, cv - r - .3, cv + r + .3, H + .55, H + 1.0, trim)
        for k in range(8):
            s = r * math.sqrt(max(0., 1 - (k / 8) ** 2)) + .15; blk(cu - s, cu + s, cv - s, cv + s, H + 1.0 + k * .38, H + 1.0 + (k + 1) * .38, blue if k % 2 == 0 else _sh(blue, .88))
        blk(cu - .1, cu + .1, cv - .1, cv + .1, H + 4.0, H + 5.2, (246, 240, 226)); top = H + 5.2
    elif kind == 'terrace':
        blk(0, W, 0, .35, H, H + .8, trim); blk(0, W, D - .35, D, H, H + .8, trim); blk(0, .35, 0, D, H, H + .8, trim); blk(W - .35, W, 0, D, H, H + .8, trim)
        for k in range(3): blk(.4, W - .4, .6 + k * 1.0, .72 + k * 1.0, H + 2.3, H + 2.4, (110, 76, 50))
        for (u, v) in ((.5, .6), (W - .6, .6), (.5, 2.5), (W - .6, 2.5)): blk(u, u + .12, v, v + .12, H, H + 2.3, (110, 76, 50))
        for u in np.linspace(1., W - 1., 3): blk(u - .35, u + .35, D - 1.5, D - .8, H, H + .5, (176, 92, 60)); blk(u - .4, u + .4, D - 1.55, D - .75, H + .5, H + 1.1, (60, 160, 80))
        top = H + .8
    else:
        blk(0, W, 0, .3, H, H + .9, _sh(body, .85)); blk(0, W, D - .3, D, H, H + .9, _sh(body, .85)); blk(0, .3, .3, D - .3, H, H + .9, _sh(body, .85)); blk(W - .3, W, .3, D - .3, H, H + .9, _sh(body, .85))
        blk(.3, W - .3, .3, D - .3, H, H + .06, (60, 60, 66)); top = H + .06
        for k in range(int(W / 1.6)): blk(.35 + k * 1.6, .35 + k * 1.6 + .8, 0, .32, H + .9, H + 1.1, _sh(body, .8))           # créneaux de l'acrotère
    return top


# ------------------------------------------------------------------------------------------------- détails posés (version VOXEL des qt_*)
def v_fire_escape(p):
    n = int(p.get('n', 3)); fh = float(p.get('fh', 3.1)); w = float(p.get('w', 2.2)); y0 = float(p.get('y0', 0.)); col = tuple(p.get('col') or (30, 30, 36)); out = []
    for f_ in range(1, n + 1):
        y = y0 + f_ * fh - .08
        out += [B((-w / 2, y, -1.1), (w, .1, 1.1), col), B((-w / 2, y + .95, -1.1), (w, .1, .1), col), B((-w / 2, y + .1, -1.1), (.1, .85, 1.1), col), B((w / 2 - .1, y + .1, -1.1), (.1, .85, 1.1), col)]
        for k in range(5):
            if f_ < n: xs = (-w / 2 + k * (w - .4) / 5) if f_ % 2 == 0 else (w / 2 - .4 - k * (w - .4) / 5); out.append(B((xs, y + .1 + k * fh / 5.2, -.8), (.45, .12, .6), col))
    return out


def v_balcony(p):
    w = float(p.get('w', 2.0)); d = float(p.get('d', 1.0)); slab = tuple(p.get('slab') or (200, 196, 188)); rail = tuple(p.get('rail') or DK)
    out = [B((-w / 2, 0, -d), (w, .16, d), slab)]
    out += [B((-w / 2, .16, -d), (w, .85, .1), rail), B((-w / 2, .16, -d), (.1, .85, d), rail), B((w / 2 - .1, .16, -d), (.1, .85, d), rail)]
    if p.get('plants'): out += [B((-w / 2 + .15, .16, -d + .3), (.36, .4, .36), (176, 92, 60)), B((-w / 2 + .1, .56, -d + .25), (.46, .4, .46), (50, 150, 70))]
    return out


def v_awning(p):
    w = float(p.get('w', 2.4)); d = float(p.get('d', 1.15)); c1 = tuple(p.get('c1') or (200, 50, 50)); c2 = tuple(p.get('c2') or (244, 240, 230)); ns = max(3, int(round(w / .4))); sw = w / ns; out = []
    for i in range(ns):
        c = c1 if i % 2 == 0 else c2
        out += [B((-w / 2 + i * sw, 0, -.5), (sw, .1, .5), c), B((-w / 2 + i * sw, -.16, -.9), (sw, .1, .4), c), B((-w / 2 + i * sw, -.32, -d), (sw, .1, d - .9), c), B((-w / 2 + i * sw, -.62, -d), (sw, .32, .08), c)]
    return out


def v_lamp(p):
    st = p.get('style', 'old'); col = (30, 74, 66) if st == 'old' else (36, 36, 42)
    if st in ('modern',): return [B((-.1, 0, -.1), (.2, 5.2, .2), (88, 92, 100)), B((-.1, 5.0, -1.0), (.2, .2, 1.0), (88, 92, 100)), B((-.3, 4.86, -1.1), (.6, .16, .5), (240, 248, 255), emis=1.7)]
    if st == 'neon': return [B((-.1, 0, -.1), (.2, 4.6, .2), (30, 30, 40)), B((-1.0, 4.4, -.08), (1.1, .12, .12), (255, 60, 190), emis=2.4), B((-.1, 3.0, -.14), (.12, 1.2, .12), (60, 230, 255), emis=2.4)]
    return [B((-.15, 0, -.15), (.3, .5, .3), col), B((-.1, .5, -.1), (.2, 3.2, .2), col), B((-.3, 3.7, -.3), (.6, .55, .6), (255, 220, 150), emis=1.6), B((-.4, 4.25, -.4), (.8, .14, .8), col)]


def v_terrace(p):
    pc = tuple(p.get('col') or (210, 50, 50)); out = []
    for dx in (-.95, .95):
        out += [B((dx - .4, .72, -.4), (.8, .1, .8), (236, 232, 222)), B((dx - .06, 0, -.06), (.12, .72, .12), DK)]
        for s in (-1, 1): out.append(B((dx + s * .62 - .2, .4, -.2), (.4, .1, .4), (170, 110, 64)))
    out += [B((-.06, 0, -.06), (.12, 2.7, .12), DK)] + [B((-1.5 + k * .4, 2.7 + (.1 if k % 2 else 0), -1.5), (.4, .12, 3.0), pc if k % 2 == 0 else (244, 240, 230)) for k in range(8)]
    return out


def v_blade(p):
    text = str(p.get('text', 'BAR'))[:12]; col = tuple(p.get('col') or (230, 60, 60)); lit = bool(p.get('night'))
    tx = P._sign_tex(text, P._txtw(text), 16, (250, 240, 200), col)
    return [B((-.06, 0, -1.0), (.12, .1, 1.0), DK), B((-.08, -.7, -.95), (.16, .65, .85), col, emis=1.0 if lit else 0., tex={'-x': tx, '+x': tx})]


def v_neon(p):
    text = str(p.get('text', 'BAR'))[:7]; col = tuple(p.get('col') or (255, 40, 170)); h = float(p.get('h', 3.2)); tx = P._vert_tex(text, max(24, len(text.replace(' ', '')) * 11 + 6), tuple(min(255, int(v * .9 + 40)) for v in col), (16, 14, 28))
    e = 2.0 if p.get('night', True) else .3
    return [B((-.3, 0, -.3), (.6, h, .2), (16, 14, 28), tex={'-z': tx}, texemis=e), B((-.4, -.08, -.4), (.8, .1, .3), col, emis=e), B((-.4, h, -.4), (.8, .1, .3), col, emis=e), B((-.4, 0, -.4), (.1, h, .3), col, emis=e), B((.3, 0, -.4), (.1, h, .3), col, emis=e)]


def v_chimney(p):
    col = tuple(p.get('col') or (150, 72, 54)); h = float(p.get('h', 1.9))
    return [B((-.4, 0, -.4), (.8, h, .8), col), B((-.5, h, -.5), (1.0, .2, 1.0), (196, 190, 180)), B((-.22, h + .2, -.22), (.44, .4, .44), (150, 60, 46))]


def v_stoop(p):
    w = float(p.get('w', 1.4)); out = [B((-w / 2, k * .17, -(1.9 - k * .45)), (w, .17, 1.9 - k * .45), (196, 190, 178)) for k in range(4)]
    out += [B((-w / 2 - .1, 0, -1.9), (.1, 1.0, 1.9), DK), B((w / 2, 0, -1.9), (.1, 1.0, 1.9), DK)]
    if p.get('plant'): out += [B((-w / 2 - .6, 0, -1.7), (.45, .5, .45), (176, 92, 60)), B((-w / 2 - .65, .5, -1.75), (.55, .5, .55), (50, 150, 74))]
    return out


def v_porch(p):
    col = tuple(p.get('col') or (246, 244, 236)); roof = tuple(p.get('roof') or (92, 70, 60))
    out = [B((-1.7, 0, -2.0), (3.4, .3, 2.0), (170, 150, 128)), B((-.7, 0, -2.7), (1.4, .1, .7), (186, 166, 140))]
    out += [B((x, .3, -1.95), (.16, 2.2, .16), col) for x in (-1.7, 1.54)] + [B((-1.8, 2.5, -2.1), (3.6, .2, 2.1), roof), B((-1.5, 2.7, -1.8), (3.0, .2, 1.5), roof), B((-1.1, 2.9, -1.4), (2.2, .2, 1.0), roof)]
    out += [B((-1.7, .3, -1.95), (3.4, .08, .08), col), B((-1.7, 1.15, -1.95), (3.4, .08, .08), col)]
    return out


def v_canopy(p):
    w = float(p.get('w', 3.2)); return [B((-w / 2, 0, -1.7), (w, .16, 1.7), (210, 216, 224)), B((-w / 2, -.34, -1.7), (w, .34, .1), (250, 120, 30)), B((-w / 2 + .1, -3.0, -1.6), (.16, 3.0, .16), DK), B((w / 2 - .26, -3.0, -1.6), (.16, 3.0, .16), DK)]


def v_boug(p):
    w = float(p.get('w', 2.4)); h = float(p.get('h', 2.2)); rng = np.random.default_rng(int(p.get('seed', 1))); out = []
    for k in range(int(w * h * 1.8)):
        x = -w / 2 + rng.random() * (w - .3); y = rng.random() * (h - .3) * (.4 + .6 * rng.random()); out.append(B((x, y, -.3 - .1 * rng.random()), (.3, .3, .25), (214, 40, 124) if rng.random() < .62 else (52, 140, 66)))
    return out


def v_car(p):
    col = tuple(p.get('color') or (120, 30, 30)); out = [B((-.95, .25, -2.1), (1.9, .55, 4.2), col), B((-.85, .8, -1.2), (1.7, .6, 2.3), col), B((-.8, .86, -1.22), (1.6, .46, .06), (140, 190, 230)), B((-.8, .86, 1.04), (1.6, .46, .06), (140, 190, 230))]
    for s in (-1, 1):
        for z in (-1.35, 1.35): out.append(B((s * .95 - (.08 if s > 0 else -.0) - .12, 0, z - .35), (.24, .5, .7), (24, 24, 28)))
    out += [B((-.8, .5, -2.12), (.4, .2, .06), (255, 240, 190), emis=.9), B((.4, .5, -2.12), (.4, .2, .06), (255, 240, 190), emis=.9), B((-.8, .5, 2.06), (.4, .2, .06), (255, 60, 50), emis=.8), B((.4, .5, 2.06), (.4, .2, .06), (255, 60, 50), emis=.8)]
    return out


VOX = {'qt_fire_escape': v_fire_escape, 'qt_balcony': v_balcony, 'qt_awning': v_awning, 'qt_lamp': v_lamp, 'qt_lamp_cool': lambda p: v_lamp(dict(p, style=p.get('style', 'modern'))),
       'qt_lamp_neon': lambda p: v_lamp(dict(p, style='neon')), 'qt_terrace': v_terrace, 'qt_blade': v_blade, 'qt_neon': v_neon, 'qt_chimney': v_chimney, 'qt_stoop': v_stoop,
       'qt_porch': v_porch, 'qt_canopy': v_canopy, 'qt_boug': v_boug, 'car': v_car}


def _place(boxes, p):
    return S.place(boxes, float(p['at'][0]), float(p['at'][1]), int(p.get('rot', 0)), float(p.get('y', 0.)))


# ------------------------------------------------------------------------------------------------- le bâtiment entier, en volumes
def build_vox(d, night):
    f = P.Frame(d); I = Q.IDENTITES[d['ident']]; W, D, H = d['W'], d['D'], d['H']; out = []
    cx, cz, sx, sz = f.box(0, W, 0, D)
    tex = {}
    for face, k in (('-z', 0), ('+z', 1), ('-x', 2), ('+x', 3)):
        role = 'front' if face == d['front'] else 'back' if face == {'+x': '-x', '-x': '+x', '-z': '+z', '+z': '-z'}[d['front']] else 'side'
        tex[face] = _wall_tex(d, role, night, k)
    out.append(B((cx - sx / 2, 0, cz - sz / 2), (sx, H - .02, sz), d['body'], tex=tex, grain=.05))
    bw = W / d['bays']
    for fl, row in enumerate(d['cells']):
        y0 = d['fy'][fl]
        for b, cell in enumerate(row):
            uc = (b + .5) * bw; t = cell['t']
            if fl == 0: _ground(out, f, d, cell, uc, I, night)
            elif t in ('win', 'bdoor', 'pane'): _window(out, f, d, cell, uc, y0, I, night, kind=t)
            elif t == 'panel': vb(out, f, uc - bw / 2 + .05, uc + bw / 2 - .05, y0 + .05, y0 + d['fh'] - .05, 0, .1, cell['col'])
    props = []
    def prop(kind, u, y, v=0., **kw):
        x, z = f.pt(u, v); props.append(dict(type=kind, at=[x, z], y=y, rot=f.rot, **kw))
    if d['fire_bay'] is not None and d['floors'] >= 3: prop('qt_fire_escape', (d['fire_bay'] + .5) * bw, 0., n=d['floors'] - 1, fh=d['fh'], y0=d['gf'] - d['fh'], w=bw * .92)
    if d['porch']: prop('qt_porch', (d['door_bay'] + .5) * bw, 0.)
    if d['stoop'] and not d['porch']:
        cell = d['cells'][0][d['door_bay']]
        if cell['t'] == 'door': prop('qt_stoop', (d['door_bay'] + .5) * bw, 0., w=I['ww'] * 1.3, plant=bool(cell['lamp']))
    for nv in d['neon_vert']: prop('qt_neon', nv['u'], nv['y'], text=nv['text'], col=nv['col'], h=nv['h'], night=night)
    for cell_b, cell in enumerate(d['cells'][0]):
        if cell['t'] == 'shop' and cell.get('blade') and cell_b % 2 == 0: prop('qt_blade', (cell_b + .5) * bw + bw / 2 - .2, 3.0, text=cell['blade'], col=cell['col'], night=night)
        if cell['t'] == 'lobby' and d['canopy']: prop('qt_canopy', (cell_b + .5) * bw, d['gf'] - .4, w=bw)
        if cell['t'] == 'arch' and d['boug'] and cell_b % 2 == 0: prop('qt_boug', (cell_b + .5) * bw, 0., w=bw * .9, h=2.4, seed=d['seed'] + cell_b)
    top = _roof(out, f, d, night)
    for ch in d['chimneys']:
        x, z = f.pt(ch, D * .4); props.append(dict(type='qt_chimney', at=[x, z], y=H + (.2 if d['roof'] in ('flat', 'terrace', 'sawtooth') else (top - H) * .5), col=(150, 72, 54) if I['kind'] == 'brick' else _sh(d['body'], .7)))
    if d['roof'] in ('flat', 'terrace', 'stepped_glass', 'sawtooth'):
        for (kind, uf, vf) in d['roof_objs']:
            if kind == 'chimney_stack': continue
            x, z = f.pt(uf * W, vf * D)
            if kind == 'water_tank': out += [B((x - .8, top + .6, z - .8), (1.6, 1.6, 1.6), (120, 86, 60)), B((x - .9, top + .3, z - .9), (.12, .6, .12), DK), B((x + .78, top + .3, z + .78), (.12, .6, .12), DK), B((x - .9, top + 2.2, z - .9), (1.8, .22, 1.8), (90, 70, 54))]
            elif kind == 'antenna': out += [B((x - .06, top, z - .06), (.12, 4.0, .12), DK), B((x - .5, top + 3.2, z - .04), (1.0, .08, .08), DK), B((x - .35, top + 2.5, z - .04), (.7, .08, .08), DK)]
            elif kind == 'ac_unit': out += [B((x - .7, top, z - .5), (1.4, .8, 1.0), (214, 218, 222)), B((x - .5, top + .8, z - .3), (.6, .1, .6), (60, 66, 76))]
            elif kind == 'satellite_dish': out += [B((x - .05, top, z - .05), (.1, .9, .1), DK), B((x - .4, top + .9, z - .4), (.8, .8, .14), (232, 236, 238))]
            else: out += [B((x - .4, top, z - .4), (.8, .5, .8), (150, 154, 160)), B((x - .3, top + .5, z - .3), (.6, .1, .6), (100, 104, 110))]
    for p in props:
        fn = VOX.get(p['type'])
        if fn: out += _place(fn(p), p)
    return out


# ------------------------------------------------------------------------------------------------- l'interface appelée par le lieu
def native_hide(st):
    """indices des boîtes PS1 que le peintre VOXEL ne convertit pas : les bâtiments (groupes `qtb*`) et le mobilier de rue refait ici (`qts`)"""
    hide = set()
    for g, ix in st.groups.items():
        if g.startswith('qtb') or g == 'qts': hide.update(ix)
    return hide


def native_items(st):
    """éléments `craft:` du mobilier de rue (arbres) : repère de PIXEL 3D, convertis par BSet"""
    out = []
    for p in st.spec.get('props', []):
        if p.get('group') == 'qts' and p['type'] in TREES:
            out.append(dict(type='craft:' + TREES[p['type']], at=[p['at'][0], p['at'][1]], rot=int(p.get('rot', 0)), scale=float(p.get('size', 1.)) * 1.0, seed=int(abs(p['at'][0] * 7 + p['at'][1] * 3)) % 3))
    return out


def native_bsets(st):
    """accessoires `bset` VOXEL (repère de VOXEL posé, agrandissement K inclus) : tous les bâtiments d'un lieu `quartier` + le mobilier de rue"""
    q = st.spec.get('_qt') or {}; night = bool(q.get('night')); boxes = []
    for key in q.get('bkeys', []):
        ident, n, front, rect, near, seed, top = key
        boxes += build_vox(Q.building(ident, n, front, tuple(rect), bool(near), int(seed), top), night)
    for p in st.spec.get('props', []):
        if p.get('group') == 'qts' and p['type'] in VOX: boxes += _place(VOX[p['type']](p), p)
    stats = {}
    return [BP.boxes_to_bset(boxes, 0, 0., 0., 0., K, stats)] if boxes else []
