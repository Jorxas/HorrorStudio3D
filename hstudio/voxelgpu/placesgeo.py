"""The geometry of the demo places, as DATA (see stagegeo.py for why): a city quarter with a walkable café, an alley and a freight lift; an airport pad on a roof with a
shuttle and a lift cab; the Moon with a landed shuttle and a beacon. The three places sit side by side in ONE frame (a film has one geometry), at the same offsets the painter
builds them (voxelgpu_js/engine/cite_kit.js: CX, AX, SX): the numbers below are the ones of that file, and `tools/check_demo_cite.py` greps them so the two cannot drift.

Coordinates are the painter's, local to the world, metres, x along the street, z towards the camera side of the street (south), y up.
  cité       centre x = 60  : north pavement z -5.5..-1.5, roadway -1.5..5.5, south pavement 5.5..9.5 ; café interior x[52.2, 67.8] z[-15.4, -5.9] (front glass z = -5.8, door x[64, 65.2]),
             alley x[49.6, 52] between the pharmacy and the café down to the freight lift at z = -34.5
  astroport  centre x = 130 : pad x[112, 148] z[-18, 18] (rail all round except the lift side), lift cab x[107, 111.7] z[-2.4, 2.4], shuttle at the centre, control tower and hangar
  selene     centre x = 200 : flat ground, shuttle landed at x = 191, beacon at (208, -1)
Nothing here is random and nothing reads a clock.
"""
import math
from .stagegeo import Geo, Portal, Solid

CX, AX, SX = 60., 190., 270.
NORTH_Z, ROAD0, ROAD1, SOUTH_Z = -5.5, -1.5, 5.5, 9.5
CAFE = dict(x0=CX - 7.8, x1=CX + 7.8, z0=-15.4, z1=-5.9)


def _zones_ok(geo, a, b, t):
    """a body goes from zone a to zone b if both are open air, or a portal joins them and is open at t"""
    if not (geo.zones[a]['indoor'] or geo.zones[b]['indoor']): return True
    return any({p.a, p.b} == {a, b} and p.open_at(t) for p in geo.portals.values())


def demo_world(door_swings=None):
    ds = door_swings or {}
    g = Geo('demo', (-20., -40., 246., 26.)); g.zones_ok = lambda a, b, t: _zones_ok(g, a, b, t)
    S = g.solid
    c = lambda x: CX + x
    # ================================================================ CITÉ
    # north row of buildings (bodies from the façade plane to far behind), the alley (x -10.4..-8) stays open, the café has its own walls
    for i, (a, b) in enumerate([(-62, -44), (-44, -30), (-30, -16), (-16, -10.4)]): S(f'bat_nord_{i}', c(a), -34.8, c(b), NORTH_Z, 0, 40)
    for i, (a, b) in enumerate([(8, 20), (20, 31), (31, 46), (46, 62)]): S(f'bat_nord_e{i}', c(a), -34.8, c(b), NORTH_Z, 0, 40)
    S('arriere_cafe', c(-8), -34.8, c(8), -15.4, 0, 40)
    S('mur_fond_ruelle_g', c(-10.4), -35.0, c(-10.2), -34.4, 0, 8); S('mur_fond_ruelle_d', c(-8.2), -35.0, c(-8.0), -34.4, 0, 8); S('haut_fond_ruelle', c(-10.2), -35.0, c(-8.2), -34.4, 2.55, 8, body=False)
    for i, (a, b) in enumerate([(-50, -34), (-34, -18), (-18, -2), (-2, 14), (14, 32), (32, 62)]): S(f'bat_sud_{i}', c(a), SOUTH_Z, c(b), 20., 0, 30)
    # café : façade vitrée (glass stops a body, not the view), side walls, back wall, the service door of the west wall (locked)
    zf0, zf1 = -5.9, -5.7
    S('cafe_vitre_g', c(-7.8), zf0, c(3.9), zf1, 0, 4.1, view=False, kind='glass'); S('cafe_vitre_d', c(5.3), zf0, c(7.8), zf1, 0, 4.1, view=False, kind='glass')
    S('cafe_cadre_porte', c(3.9), zf0, c(4.0), zf1, 0, 4.1); S('cafe_cadre_porte2', c(5.2), zf0, c(5.3), zf1, 0, 4.1); S('cafe_linteau_porte', c(4.0), zf0, c(5.2), zf1, 2.45, 4.1, body=False)
    S('cafe_mur_est', c(7.8), CAFE['z0'], c(8.0), zf1, 0, 4.1)
    S('cafe_mur_ouest_a', c(-8.0), CAFE['z0'], c(-7.8), -13.5, 0, 4.1); S('cafe_mur_ouest_b', c(-8.0), -12.5, c(-7.8), zf1, 0, 4.1)
    S('cafe_mur_fond', c(-8.0), -15.6, c(8.0), CAFE['z0'], 0, 4.1)
    S('cafe_plafond', c(-8.0), CAFE['z0'], c(8.0), zf1, 4.1, 4.4, body=False, kind='ceiling')
    g.portal(Portal('cafe_porte', (c(4.0), zf0, c(5.2), zf1), 'terrasse', 'cafe', y1=2.4, swing=ds.get('cafe_porte'), leaf='z'))
    g.portal(Portal('cafe_service', (c(-8.0), -13.5, c(-7.8), -12.5), 'cafe', 'ruelle', y1=2.1, swing=[[0., 0.]], locked=True, leaf='x'))
    g.portal(Portal('monte_charge', (c(-10.2), -34.8, c(-8.2), -34.4), 'ruelle', 'monte_charge_dehors', y1=2.4, swing=ds.get('monte_charge'), leaf='z'))
    # café furniture
    BZ = -13.6
    S('bar_comptoir', c(-5.2), BZ - .45, c(2.2), BZ + .45, 0, 1.15); S('bar_retour', c(1.9), BZ + .0, c(2.8), BZ + 3.25, 0, 1.15)
    for i in range(6): x = c(-4.2 + i * 1.15); S(f'tabouret_{i}', x - .19, BZ + 1.0, x + .19, BZ + 1.38, 0, .8)
    S('etageres_bar', c(-5.0), CAFE['z0'], c(2.0), CAFE['z0'] + .5, 0, 2.5); S('buffet', c(-7.6), -12.0, c(-7.0), -10.2, 0, 1.12)
    for i, (x, z) in enumerate([(-4.4, -8.6), (-0.4, -7.4), (2.6, -7.8), (4.6, -11.2), (6.3, -8.2)]):
        S(f'table_{i}', c(x) - .45, z - .45, c(x) + .45, z + .45, 0, .78)
        for j, (dx, dz) in enumerate([(.75, 0), (-.75, 0), (0, .75)]): S(f'chaise_{i}{j}', c(x + dx) - .21, z + dz - .21, c(x + dx) + .21, z + dz + .21, 0, .9)
    S('armure', c(6.2) - .27, -14.8, c(6.2) + .27, -14.4, 0, 2.5)
    for i, (x, z) in enumerate([(-7.0, -6.6), (7.0, -6.6), (7.0, -9.6)]): S(f'plante_cafe_{i}', c(x) - .3, z - .3, c(x) + .3, z + .3, 0, 1.9)
    # terrace (north pavement): tables with chairs, planters along the road side (gaps of 2.1 m between them)
    for i, (x, z) in enumerate([(-3.1, -3.0), (-0.2, -3.5), (2.6, -3.1)]):
        S(f'terrasse_table_{i}', c(x) - .4, z - .4, c(x) + .4, z + .4, 0, 1.05)
    for i in range(7): x = c(-7.8 + i * 2.6); S(f'jardiniere_{i}', x - .26, -1.9 - .26, x + .26, -1.9 + .26, 0, 1.3)
    # street furniture
    for x in range(-54, 55, 11): S(f'lampadaire_n{x}', c(x) - .12, -2.12, c(x) + .12, -1.88, 0, 5.2); S(f'lampadaire_s{x}', c(x + 5.5) - .12, 5.88, c(x + 5.5) + .12, 6.12, 0, 5.2)
    for i, x in enumerate([-40, -27, -13, 12, 27, 41]): S(f'arbre_n{i}', c(x) - .45, -1.45, c(x) + .45, -.55, 0, 5)
    for i, x in enumerate([-46, -31, -8, 3, 20, 36]): S(f'arbre_s{i}', c(x) - .45, 5.85, c(x) + .45, 6.75, 0, 5)
    for i, x in enumerate([-15, 22, -36]): S(f'banc_{i}', c(x) - .85, 8.4, c(x) + .85, 9.1, 0, .95)
    for i, x in enumerate([-12.5, 17, 38]): S(f'poubelle_{i}', c(x) - .27, -5.27, c(x) + .27, -4.73, 0, 1.1)
    for i, (x, z) in enumerate([(-10.8, 6.0), (30, 6.3)]): S(f'bouche_{i}', c(x) - .17, z - .17, c(x) + .17, z + .17, 0, .85)
    for x in (24, 28.2): S(f'abribus_poteau_{x}', c(x) - .06, 6.24, c(x) + .06, 6.36, 0, 2.5)
    S('abribus_banc', c(24.2), 7.25, c(28), 7.75, 0, .6); S('abribus_vitre', c(24.1), 7.88, c(28.1), 7.95, 0, 2.5, view=False, kind='glass')
    for i in range(4): x = -30 + i * 3.4; S(f'etal_{i}', c(x - 1.3), 7.45, c(x + 1.3), 8.55, 0, .6); S(f'etal_poteau_{i}', c(x - 1.3), 7.45, c(x - 1.2), 7.55, 0, 2.6); S(f'etal_poteau_b{i}', c(x + 1.2), 7.45, c(x + 1.3), 7.55, 0, 2.6)
    for i, x in enumerate([-34, -8, 6, 34, 46]): S(f'voiture_garee_{i}', c(x) - 1.95, 4.5 - .85, c(x) + 1.95, 4.5 + .85, 0, 1.25, kind='car')
    S('benne', c(-9.2) - .45, -21.1, c(-9.2) + .45, -18.9, 0, 1.3); S('caisses', c(-9.2) - 1.0, -15.4, c(-9.2) - .2, -14.2, 0, 1.0)
    S('horloge_pied', c(14) - 1.8, -10.8, c(14) + 1.8, -7.2, 0, 30, body=False)
    # zones (the smallest zone that holds a point wins)
    g.zone('cafe', [(CAFE['x0'], CAFE['z0'], CAFE['x1'], CAFE['z1'])], True)
    g.zone('terrasse', [(c(-8), -5.7, c(8), -1.5)])
    g.zone('ruelle', [(c(-10.4), -34.8, c(-8.0), -5.5)])
    g.zone('trottoir_nord', [(c(-62), -5.7, c(62), -1.5)]); g.zone('chaussee', [(c(-62), -1.5, c(62), 5.5)]); g.zone('trottoir_sud', [(c(-62), 5.5, c(62), 9.5)])
    g.zone('monte_charge_dehors', [(c(-10.2), -36.5, c(-8.2), -34.4)], True)
    # ================================================================ ASTROPORT
    a = lambda x: AX + x
    for i, (x0, z0, x1, z1) in enumerate([(-18.2, 17.9, 18.2, 18.1), (-18.2, -18.1, 18.2, -17.9), (17.9, -18.2, 18.1, 18.2), (-18.1, 3.0, -17.9, 18.2), (-18.1, -18.2, -17.9, -3.0)]):
        S(f'garde_corps_{i}', a(x0), z0, a(x1), z1, 0, 1.1, view=False, kind='rail')
    S('tour_pied', a(10.5), -14.5, a(13.5), -11.5, 0, 8.5); S('hangar', a(-12), -17.7, a(0), -12.7, 0, 5.4); S('reservoir', a(12.9), 11.9, a(15.1), 14.1, 0, 3.3); S('chariot', a(-12.8), 13.5, a(-11.2), 14.5, 0, 1.2)
    for i, (x, z) in enumerate([(-16, -16), (16, 16), (16, -16), (-16, 16)]): S(f'mat_{i}', a(x) - .11, z - .11, a(x) + .11, z + .11, 0, 8.2)
    S('mat_manche', a(16) - .05, 5.95, a(16) + .05, 6.05, 0, 4)
    S('navette_fuselage', a(-1.7), -6.9, a(1.7), 4.7, 0, 3.7); S('navette_ailes', a(-3.9), -1.4, a(3.9), 2.6, 0, 1.7)
    # the lift cab (x -23..-18.3), its door towards the pad
    S('cab_nord', a(-23.0), -2.6, a(-18.3), -2.4, 0, 3.1); S('cab_sud', a(-23.0), 2.4, a(-18.3), 2.6, 0, 3.1); S('cab_fond', a(-23.2), -2.6, a(-23.0), 2.6, 0, 3.1); S('cab_toit', a(-23.0), -2.4, a(-18.3), 2.4, 3.0, 3.2, body=False, kind='ceiling')
    S('cab_montant_n', a(-18.6), -2.4, a(-18.2), -1.0, 0, 3.1); S('cab_montant_s', a(-18.6), 1.0, a(-18.2), 2.4, 0, 3.1)
    g.portal(Portal('lift_toit', (a(-18.6), -1.0, a(-18.2), 1.0), 'cabine', 'pad', y1=2.4, swing=ds.get('lift_toit'), leaf='x'))
    g.zone('cabine', [(a(-22.9), -2.4, a(-18.6), 2.4)], True); g.zone('pad', [(a(-18.2), -18.2, a(18.2), 18.2)])
    # ================================================================ SELENE
    s = lambda x: SX + x
    S('lune_fuselage', s(-13.7), -1.7, s(-2.1), 1.7, 0, 3.7, kind='ship'); S('lune_ailes', s(-11.6), -3.9, s(-7.6), 3.9, 0, 1.7, kind='ship')
    S('balise_socle', s(6.5), -2.5, s(9.5), .5, 0, .8); S('balise_mat', s(7.7), -1.3, s(8.3), -.7, 0, 7); S('balise_pupitre', s(7.4), .25, s(8.6), .95, 0, 1.45)
    for i, (x, z) in enumerate([(-10, -3.4), (-8, 3.2), (9, 3.6), (-3, -3.8)]): S(f'rocher_lune_{i}', s(x) - .6, z - .5, s(x) + .6, z + .5, 0, .6)
    g.zone('lune', [(s(-30), -8, s(30), 8)])
    # ---- named places (x, z, yaw; yaw 0 faces +z = the south side of the street)
    M = g.mark
    M('rue_ouest', c(-38), -3.3, math.pi / 2); M('rue_est', c(38), -3.3, -math.pi / 2); M('trottoir_cafe', c(0.4), -2.6, math.pi)
    M('terrasse_gauche', c(-4.7), -3.6, math.pi / 2); M('terrasse_droite', c(-1.6), -3.0, -math.pi / 2); M('porte_cafe_dehors', c(4.6), -4.4, math.pi); M('porte_cafe_dedans', c(4.6), -7.0, 0.)
    M('salle_centre', c(0.0), -8.0, 0.); M('fond_cafe', c(5.0), -13.2, 0.); M('ruelle_entree', c(-9.2), -4.0, math.pi); M('ruelle_fond', c(-9.2), -33.0, math.pi)
    M('lift_alt', c(-9.2), -32.4, math.pi)
    M('toit_ascenseur', a(-19.8), 0., -math.pi / 2); M('pad_ascenseur', a(-15.0), 0., -math.pi / 2); M('rampe', a(4.5), -2.6, -math.pi / 2); M('pad_tour', a(6.0), -8.0, 0.)
    M('lune_navette', s(-6.4), 4.5, math.pi); M('lune_balise', s(5.0), 1.5, -math.pi / 2); M('lune_milieu', s(-2.0), 2.4, -math.pi / 2)
    # ---- what the camera may be asked to show: (x0, y0, z0, x1, y1, z1)
    L = g.landmarks
    L.update({'cafe_facade': (c(-8), 0., -5.9, c(8), 4.4, -5.7), 'cafe_porte': (c(4.0), 0., -5.9, c(5.2), 2.4, -5.7), 'terrasse': (c(-8), 0., -5.7, c(8), 2.2, -1.5), 'bar': (c(-5.2), 0., -14.05, c(2.2), 2.4, -13.15),
              'monte_charge': (c(-10.2), 0., -34.8, c(-8.2), 3.4, -34.4), 'horloge': (c(14) - 1.2, 22., -10.6, c(14) + 1.2, 26., -7.4), 'navette': (a(-3.9), 0., -6.9, a(3.9), 3.7, 4.7), 'tour': (a(10.5), 0., -14.5, a(13.5), 11., -11.5),
              'cabine': (a(-22.9), 0., -2.4, a(-18.6), 3.0, 2.4), 'balise': (s(6.5), 0., -2.5, s(9.5), 7.2, .5), 'lune_navette': (s(-13.7), 0., -3.9, s(-2.1), 3.7, 3.9), 'armure': (c(6.2) - .27, 0., -14.8, c(6.2) + .27, 2.5, -14.4),
              'rack_epees': (c(-7.4), 1.0, -15.4, c(-5.4), 2.6, -15.2)})
    g.items.update({'fente_balise': dict(at=(s(8.0), 1.22, .95), zone='lune'), 'epee_a': dict(at=(c(-6.9), 1.9, -15.28), zone='cafe'), 'epee_b': dict(at=(c(-6.1), 1.9, -15.28), zone='cafe'), 'mallette_buffet': dict(at=(c(-7.05), 1.27, -11.1), zone='cafe'), 'mallette': dict(at=(c(-3.1), 0.85, -3.0), zone='terrasse')})
    return g
