"""Contrôles du lieu `phare_foret` et de l'effet `effacement` (14/11/2026, « Le Phare qui efface »).

    PYTHONIOENCODING=utf-8 .venv\\Scripts\\python.exe tools/check_phare_foret.py [--sans-images]

Structure, options, opt-in, collisions (aucun arbre sur la route, une maison, la tour, un autre arbre ; aucun décor dans un tronc), zones libres des
acteurs, voiture (assemblage valide, habitacle libre), faisceau, effet d'effacement, déterminisme, traduction VOXEL ; puis (sauf --sans-images) deux
vraies images PS1 9:16 mesurées : luminance moyenne et part de noir bouché."""
import json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import numpy as np

OK = []; BAD = []


def check(name, cond, detail=''):
    (OK if cond else BAD).append(name)
    print(('ok   ' if cond else 'ÉCHEC'), name, ('' if cond else f': {detail}'))


from hstudio.engines.pixel3d import places as PL, sets as S, phare_foret as PF, effects as FX, effacement as EF


def box_of(b):
    (x, y, z), (w, h, d) = b['at'], b['size']
    return (x - w / 2, y, z - d / 2, x + w / 2, y + h, z + d / 2)


def inside(blocks, p, tol=0.):
    for b in blocks:
        x0, y0, z0, x1, y1, z1 = box_of(b)
        if x0 - tol <= p[0] <= x1 + tol and y0 <= p[1] <= y1 and z0 - tol <= p[2] <= z1 + tol: return b
    return None


def overlap(a, b, m=0.):
    return a[0] < b[3] - m and b[0] < a[3] - m and a[1] < b[4] - m and b[1] < a[4] - m and a[2] < b[5] - m and b[2] < a[5] - m


# 1. registration, opt-in
check('lieu « phare_foret » enregistré', 'phare_foret' in PL.PLACES and PL.PLACES['phare_foret'] is PF.phare_foret)
for n in ('forest', 'cinema_salle', 'lycee_riviere', 'cimetiere_calme', 'village', 'quartier'):
    check(f'lieu d\'avant « {n} » toujours là (autre fonction)', n in PL.PLACES and PL.PLACES[n] is not PF.phare_foret)
check('effet « effacement » enregistré, les effets d\'avant intacts', 'effacement' in FX.EFFECTS and all(k in FX.EFFECTS for k in ('lightning_bolt', 'collapse', 'mover')))
check('opt-in : un autre lieu prêt reste un RoomSet ordinaire', type(S.make_set('forest', {'type': 'forest'})).__name__ == 'RoomSet')
st = S.make_set('phare_foret', {'type': 'phare_foret'}); st.build()
check('phare_foret construit par sa classe (PhareSet) avec boîtes et lumières', type(st).__name__ == 'PhareSet' and len(st.base.boxes) > 1500 and len(st.light_defs) >= 18,
      f'{type(st).__name__}, {len(st.base.boxes)} boîtes, {len(st.light_defs)} lumières')

# 2. the expanded place
O = PL.expand('phare_foret', {})
check('extérieur, nuit, étoiles, aucune pluie, aucune mer', O.get('outdoor') and O.get('sky') == 'night' and O.get('stars') and not O.get('weather')
      and not any(z.get('ground') == 'water' for z in O.get('zones', [])))
need = ('start', 'route', 'voiture', 'voiture.conducteur', 'voiture.passager', 'voiture.tableau', 'voiture.plancher', 'cabane', 'cabane.marches', 'phare', 'phare.porte',
        'phare.pied', 'phare.vitre', 'phare.vitre_route', 'phare.lentille', 'boulangerie', 'boulangerie.seuil', 'boulangerie.mur', 'traces.debut', 'traces.fin', 'foret', 'maison0')
missing = [a for a in need if a not in O['anchors']]
check('tous les repères demandés', not missing, str(missing))
check('repères en hauteur : vitre (y 20,2), lentille (y 21,4), tableau de bord (y 0,79)', O['anchors']['phare.vitre'][1] == 20.2 and O['anchors']['phare.lentille'][1] == 21.4
      and abs(O['anchors']['voiture.tableau'][1] - .79) < 1e-6)
Bk = O['blocks']
check('déterministe : deux expansions identiques', json.dumps(PL.expand('phare_foret', {}), sort_keys=True, default=str) == json.dumps(O, sort_keys=True, default=str))
check('autre graine = autre forêt', json.dumps(PL.expand('phare_foret', {'seed': 9})['blocks'], default=str) != json.dumps(Bk, default=str))

# 3. options and groups
grp = lambda bl, g: [b for b in bl if b.get('group') == g]
ce = PL.expand('phare_foret', {'cabane': 'effacee'})['blocks']
check('cabane intacte : murs et toit (groupe cabane) + trois marches (groupe cabane.marches)', len(grp(Bk, 'cabane')) > 30 and len([b for b in grp(Bk, 'cabane.marches') if b['size'][1] < .1 and b['size'][0] < .4]) >= 3)
tr = [b for b in grp(ce, 'cabane.marches') if b['material'] == 'wood']
check('cabane effacée : plus de murs ni de toit, seulement les trois marches EN L\'AIR', not grp(ce, 'cabane') and len(tr) == 3 and min(b['at'][1] for b in tr) > .1, str([b['at'] for b in tr]))
check('marches identiques intacte / effacée (raccord de l\'effacement)', sorted(json.dumps(b, sort_keys=True) for b in grp(Bk, 'cabane.marches')) == sorted(json.dumps(b, sort_keys=True) for b in grp(ce, 'cabane.marches')))
check('cabane effacée : la clôture et la boîte aux lettres restent', inside(ce, (-4.95, .39, 11.0)) is not None and inside(ce, (PF.MAILBOX[0], 1.1, PF.MAILBOX[1])) is not None)
check('`cabane: False` : aucune cabane', not [b for b in PL.expand('phare_foret', {'cabane': False})['blocks'] if str(b.get('group', '')).startswith('cabane')])
be = PL.expand('phare_foret', {'boulangerie': 'effacee'})['blocks']
check('boulangerie effacée : contour du mur invisible (fin, pâle, peu lumineux) + trois marches, plus de bâtiment',
      not grp(be, 'boulangerie') and len(grp(be, 'boulangerie.contour')) >= 8 and all(min(b['size']) <= .03 and b.get('emissive', 0) <= .25 for b in grp(be, 'boulangerie.contour'))
      and len(grp(be, 'boulangerie.marches')) == 3)
check('boulangerie intacte : pas de contour', not grp(Bk, 'boulangerie.contour'))
m6 = PL.expand('phare_foret', {'maisons': 6, 'maisons_effacees': [1]})
check('maisons : 6 au plus, `maisons_effacees` n\'en laisse que les marches',
      len([p for p in m6['props'] if p.get('type') == 'house']) == 5 and not [p for p in m6['props'] if p.get('group') == 'maison1'] and len(grp(m6['blocks'], 'maison1.marches')) == 3)
check('`voiture: False` / `traces: False` les retirent', len(PL.expand('phare_foret', {'voiture': False, 'traces': False})['blocks']) < len(Bk) - 80)

# 4. the car
VB = PF.voiture_blocs()
from hstudio.engines.pixel3d import assemblage as AS
try:
    AS.validate({'type': 'mover', 'thing': 'prop:assemblage', 'blocks': VB}); ok_as = len(AS.boxes({'blocks': VB})) == len(VB) if hasattr(AS, 'boxes') else True; err = ''
except Exception as e: ok_as = False; err = str(e)
check('voiture : ≤ 128 blocs, nombres finis, `emissive` numérique (assemblage valide)', len(VB) <= 128 and ok_as and all(isinstance(b.get('emissive', 0), (int, float)) and not isinstance(b.get('emissive', 0), bool) for b in VB), f'{len(VB)} {err}')
car = [b for b in Bk if abs(b['at'][0] - 1.4) < 1.05 and abs(b['at'][2]) < 2.4 and b['at'][1] < 1.6 and b.get('group') is None and b['size'][1] < 2]
drv = [(1.0, .75, 0.), (1.0, 1.0, -.02), (1.0, 1.25, -.05), (1.0, .55, .4), (.95, 1.45, -.05)]
hit = [p for p in drv if inside(car, p)]
check('voiture : siège conducteur réellement libre (bassin, torse, tête, genoux)', not hit, str([(p, inside(car, p)['at']) for p in hit]))
from hstudio.acting import rig as RG
hj = RG.solve({'sit': 1.0}).joints['head']                       # seated head joint, local frame (x right, z forward)
rest = [b for b in car if b['size'] == [.28, .2, .1]]              # the two headrests
for who in ('voiture.conducteur', 'voiture.passager'):
    px, py, pz = O['anchors'][who]
    hx, hy, hz = px + float(hj[0]), py + float(hj[1]), pz + float(hj[2])
    head = (hx - .25, hy - .22, hz - .25, hx + .25, hy + .3, hz + .25)             # PS1 head cube with its hair
    gaps = []
    for b in rest:
        r = box_of(b)
        if abs((r[0] + r[3]) / 2 - px) > .3: continue
        gaps.append(max(r[0] - head[3], head[0] - r[3], r[1] - head[4], head[1] - r[4], r[2] - head[5], head[2] - r[5]))
    check(f'voiture : {who} {O["anchors"][who]} (sit=1, cap +z) : tête assise à ≥ 5 cm de l\'appui-tête', gaps and min(gaps) >= .05, f'écart {gaps}')
check('voiture : pare-brise et vitres ouverts (pas de bloc entre l\'habitacle et dehors)', not inside(car, (1.4, 1.2, .6)) and not inside(car, (2.3, 1.2, 0.)) and not inside(car, (.5, 1.2, 0.)))
sb = [b for b in st.base.boxes if b.tex and abs(float(b.lo[2]) - .596) < .01 and abs(float(b.lo[0]) - 1.25) < .01]
check('voiture : écran du tableau de bord texturé, tourné vers l\'habitacle (-z)', len(sb) == 1 and 4 in sb[0].tex, str(len(sb)))

# 4 bis. the hand pressed on a pane (object of the series)
MH = PF.main_plaquee_blocs
h = MH(16.27, 21.45, 32.47)
check('main plaquée : 17 blocs (paume, manchette, avant-bras, 4 doigts + ongles, pouce, cicatrice de 5), 12 sans cicatrice',
      len(h) == 17 and len(MH(0, 1, 0, cicatrice=False)) == 12 and len([b for b in h if b['color'] == list(PF.SCAR)]) == 5
      and not [b for b in MH(0, 1, 0, cicatrice=False) if b['color'] == list(PF.SCAR)])
thumb = lambda bl: [b for b in bl if b['size'] in ([.02, .045, .02],)][0]['at']
palm = lambda bl: bl[0]['at']
check('main plaquée : pouce vers le corps (main gauche face -z : pouce côté -x ; main droite : côté +x)',
      thumb(MH(0, 1, 0, 'gauche', '-z'))[0] < palm(MH(0, 1, 0, 'gauche', '-z'))[0] and thumb(MH(0, 1, 0, 'droite', '-z'))[0] > palm(MH(0, 1, 0, 'droite', '-z'))[0])
check('main plaquée : face +z / -x / +x : pouce de la main gauche vers +x / +z / -z',
      thumb(MH(0, 1, 0, 'gauche', '+z'))[0] > 0 and thumb(MH(0, 1, 0, 'gauche', '-x'))[2] > 0 and thumb(MH(0, 1, 0, 'gauche', '+x'))[2] < 0)
arm = lambda bl: bl[2]['at']
check('main plaquée : l\'avant-bras part derrière la vitre, à l\'opposé de la face (-z -> +z, +x -> -x)',
      arm(MH(0, 1, 0, face='-z'))[2] > .05 and arm(MH(0, 1, 0, face='+z'))[2] < -.05 and arm(MH(0, 1, 0, face='+x'))[0] < -.05 and arm(MH(0, 1, 0, face='-x'))[0] > .05)
check('main plaquée : tournée -x, la paume est mince en x et large en z', MH(0, 1, 0, face='-x')[0]['size'][0] < .03 and MH(0, 1, 0, face='-x')[0]['size'][2] > .07)
check('main plaquée : la cicatrice est sur la face vue (devant la paume)', all(b['at'][2] < 32.47 - .005 for b in h if b['color'] == list(PF.SCAR)))
check('main plaquée : `echelle` 2 double la paume', abs(MH(0, 1, 0, echelle=2.)[0]['size'][0] - .156) < 1e-6)
try: MH(0, 1, 0, face='haut'); bad_face = False
except ValueError: bad_face = True
check('main plaquée : une face inconnue est refusée en clair', bad_face)
mv = lambda sp: [b for b in PL.expand('phare_foret', sp)['blocks'] if b.get('group') == 'main_vitre']
check('option `main_vitre` : True = la main gauche de Noé sur la vitre -z de la lanterne ; liste = plusieurs mains ; absente = aucune',
      len(mv({'main_vitre': True})) == 17 and len(mv({'main_vitre': [{}, {'cote': 'droite', 'x': 15.7}]})) == 34 and not mv({})
      and abs(mv({'main_vitre': True})[0]['at'][2] - 32.47) < 1e-6)

# 5. collisions: trees, props, structures
trees = O['_phare']['trees']; Rr, Cc = PF.obstacles({})
bad_road = [(x, z) for x, z, r, h, f in trees if abs(x) - r < 4.3]
check(f'aucun arbre ({len(trees)}) sur la route ni ses bas-côtés (couronne comprise)', not bad_road, str(bad_road[:3]))
bad_tt = []
for i, (x, z, r, h, f) in enumerate(trees):
    for (x2, z2, r2, h2, f2) in trees[i + 1:]:
        if (x - x2) ** 2 + (z - z2) ** 2 < (r + r2) ** 2 - 1e-6: bad_tt.append((x, z, x2, z2))
check('aucune couronne de pin dans une autre', not bad_tt, str(bad_tt[:3]))
struct = PF.cabane_blocs('intacte')[0] + PF.enclos_blocs() + PF.phare_blocs({})[0] + PF.boulangerie_blocs('intacte', {})[0] + PF.maisons({})[1] + PF.route_blocs({})[0] + PF.traces_blocs()
bad_ts = []
for (x, z, r, h, f) in trees:
    tb = (x - r, 0., z - r, x + r, h, z + r)
    for b in struct:
        if overlap(tb, box_of(b), .01): bad_ts.append(((x, z), b['at'])); break
check('aucun arbre dans la cabane, la clôture, la tour, la boulangerie, les maisons, un poteau, un panneau ou une trace', not bad_ts, str(bad_ts[:3]))
hp = [p for p in O['props'] if p.get('type') == 'house']
bad_h = [(p['at'], (x, z)) for p in hp for (x, z, r, h, f) in trees if abs(p['at'][0] - x) < 2.7 + r and abs(p['at'][1] - z) < 2.7 + r]
check('aucun arbre dans une maison', not bad_h, str(bad_h[:2]))
und = [p for p in O['props'] if p.get('type') in ('rock', 'stump', 'bush', 'boulder', 'rock_pile')]
bad_u = [p['at'] for p in und if any((p['at'][0] - x) ** 2 + (p['at'][1] - z) ** 2 < (.2 + .3) ** 2 for x, z, r, h, f in trees) or abs(p['at'][0]) < 4.3]
check(f'rochers, souches, buissons ({len(und)}) : ni dans un tronc ni sur la route', not bad_u, str(bad_u[:3]))
bad_l = [(x, z) for (x, z, hx, hz) in O['_phare']['logs'] if abs(x) - hx < 4.3 or any(abs(x - tx) < hx + .2 and abs(z - tz) < hz + .2 for tx, tz, r, h, f in trees)]
check(f'troncs couchés ({len(O["_phare"]["logs"])}) : ni sur la route ni dans un arbre', not bad_l, str(bad_l))
clr = [(x, z) for x, z, r, h, f in trees if (x - 16) ** 2 + (z - 34) ** 2 < (7.5 + r) ** 2]
check('clairière du phare dégagée (rayon 7,5 m)', not clr, str(clr[:3]))
lane = [(x, z) for x, z, r, h, f in trees if PF._seg_d(x, z, *PF.VIEW_LANES[0][:2]) < PF.VIEW_LANES[0][2] + r]
check('le phare se voit depuis la voiture : couloir de vue sans arbre', not lane, str(lane[:3]))

# 6. free zones for the actors
allb = Bk
bad_z = []
for name, (x, z, rad) in PF.ZONES_LIBRES.items():
    for dx, dz in ((0, 0), (rad, 0), (-rad, 0), (0, rad), (0, -rad)):
        for y in (.5, 1.0, 1.6):
            b = inside(allb, (x + dx, y, z + dz))
            if b is not None: bad_z.append((name, (x + dx, y, z + dz), b['at'])); break
check('zones libres des acteurs (porte conducteur, devant la cabane, pied et porte du phare, départ des traces, mur de la boulangerie, route...)', not bad_z, str(bad_z[:3]))
door = inside(Bk, (13.44, 1.2, 34.0))
check('porte du phare : au niveau du socle (bas à y 0,45, devant libre), deux marches pour y monter', door is not None and abs(door['at'][1] - .45) < .01
      and inside(Bk, (12.2, .1, 34.0)) is not None and inside(Bk, (12.6, .25, 34.0)) is not None)
check('lanterne : place libre pour l\'enfant aux deux vitres (rien entre 20,25 et 21,9 m)', all(inside(Bk, (16.0, y, 32.85)) is None and inside(Bk, (14.85, y, 34.0)) is None for y in (20.4, 21.0, 21.6)))

# 7. the beam
bm = PF._beam_state(PF.DEFAULT_BEAM, {}, .5, 0.)
check('faisceau : allumé par défaut, blanc, part de la lentille', bm is not None and bm['col'][0] > .9 and bm['col'][1] > .9 and np.allclose(bm['origin'], (16, 21.4, 34)))
b2 = PF._beam_state(PF.DEFAULT_BEAM, {'faisceau_angle': -90., 'faisceau_pente': 0.}, .5, 0.)
check('faisceau : angle -90° = vers -x (la route)', np.allclose(b2['dirs'][0], (-1, 0, 0), atol=1e-6))
b3 = PF._beam_state(PF.DEFAULT_BEAM, {'faisceau_angle': 0., 'faisceau_vitesse': 30., 'faisceau_pente': 0.}, .5, 3.)
check('faisceau : `vitesse` tourne avec le temps absolu (30°/s x 3 s = 90°)', np.allclose(b3['dirs'][0], (1, 0, 0), atol=1e-6))
check('faisceau : `faisceau: 0` l\'éteint, `rouge` le colore, `double` en fait deux', PF._beam_state(PF.DEFAULT_BEAM, {'faisceau': 0}, .5, 0.) is None
      and PF._beam_state(PF.DEFAULT_BEAM, {'faisceau_couleur': 'rouge'}, .5, 0.)['col'][1] < .3 and len(PF._beam_state(PF.DEFAULT_BEAM, {'faisceau_double': True}, .5, 0.)['dirs']) == 2)
L1 = st.lights({}, 1.0, .5, (0., 1.6, -5.)); L0 = st.lights({'faisceau': 0}, 1.0, .5, (0., 1.6, -5.))
spots = lambda L: [l for l in L if len(l) > 5 and l[5] is not None]
check('faisceau : un projecteur de plus quand il est allumé, la lumière de remplissage reste la DERNIÈRE', len(spots(L1)) == len(spots(L0)) + 1 and L1[-1][3] < 5 and L1[-1][0][2] == -5.)
sc = st.scene({}, 1.0, .5)
check('passe du lieu posée (faisceau, cônes des lampes, brume basse)', getattr(sc, 'post_fn', None) is not None)

# 8. the erasure effect
class Ctx: hide_static = set(); fx_flash = 0.
def run(o, T, setobj=st):
    c = Ctx(); c.hide_static = set()
    out, L = FX.EFFECTS['effacement'](FX.Fx(c, {}, setobj, {}, None, T, .5, 10. + T), o)
    return c.hide_static, out, L
hs, out, L = run({'type': 'effacement', 'target': 'cabane', 'at': 1.0, 'dur': .6}, .5)
check('effacement : avant `at`, rien ne bouge', not hs and not out)
ids_c = {id(st.base.boxes[i]) for i in st.groups['cabane']}; ids_m = {id(st.base.boxes[i]) for i in st.groups['cabane.marches']}
hs, out, L = run({'type': 'effacement', 'target': 'cabane', 'at': 1.0, 'dur': .6}, 1.3)
check('effacement : à mi-course, la cabane est retirée du décor fixe et redessinée en partie (front qui descend, pixels), une lueur froide', ids_c <= hs and not (ids_m & hs) and len(out) > 10 and L and L[0][2] > .5)
check('effacement : des boîtes qui se défont en pixels (dissolve) au front', any(getattr(b, 'dissolve', 0) > .3 for b in out))
hs, out, L = run({'type': 'effacement', 'target': 'cabane', 'at': 1.0, 'dur': .6}, 2.0)
check('effacement : fini, il ne reste rien de la cabane (les marches restent dans le décor)', ids_c <= hs and not (ids_m & hs) and not out)
check('effacement : les lumières de la cabane baissent avec elle', st._efface_frame[1].get('cabane') == 0. and len(st.light_groups.get('cabane', [])) >= 2)
hs, out, L = run({'type': 'effacement', 'target': 'boulangerie', 'at': 0., 'dur': .8}, 2.0)
check('effacement de la boulangerie : le contour du mur invisible apparaît (identique à la variante `effacee`)', len(out) == len(PF.bakery_contour_blocks()))
hs, out, L = run({'type': 'effacement', 'target': 'maison0', 'at': 0., 'dur': .8}, .4)
check('effacement d\'une maison (décor `house` + fenêtres + boîte aux lettres)', len(hs) > 8)
check('effacement : aucun son par défaut, un son sur demande', EF._sounds({'at': 1.}) == [] and EF._sounds({'at': 1., 'son': {'name': 'whoosh'}})[0][1] == 'whoosh')

# 9. VOXEL: the place translates
from hstudio.voxelgpu import b_sets as BS
bv = BS.get('phare_foret', {'type': 'phare_foret'})
check('VOXEL : lieu traduit (décor, sol, ciel de nuit dessiné)', len(bv.props) >= 3 and any(isinstance(p, dict) and p.get('type') == 'bdome' for p in bv.props))

# 10. real PS1 images, measured
if '--sans-images' not in sys.argv:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import phare_foret_sheet as SH
    for v, lim in (('route_large', 52.), ('cabane', 52.)):
        _, img, m = SH.render((v, 270, 480))
        check(f'image PS1 « {v} » : nuit lisible (luminance ≥ {lim:.0f}/255, noir bouché < 1/3)', m['luminance'] >= lim and m['noir'] < .33, str(m))

print(f'\n{len(OK)} contrôles OK, {len(BAD)} en échec')
sys.exit(1 if BAD else 0)
