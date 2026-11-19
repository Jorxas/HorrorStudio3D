"""Contrôles du lieu `phare_interieur`, du Veilleur, du projecteur de la lampe torche et des objets de la suite (15/11/2026, « Le Phare qui efface »).

    PYTHONIOENCODING=utf-8 .venv\\Scripts\\python.exe tools/check_phare_interieur.py [--sans-images]

Opt-in (lieux d'avant intacts, personnage ordinaire inchangé), repères, zones libres des acteurs, collisions (rien dans le mur rond, marches et
dégagement de tête des deux volées, portes et ouvertures praticables, trémies, grille), textes lisibles (contenu, longueur des lignes, face tournée
vers la pièce, sept traits dont trois barrés), états (`phare`, porte, levier, fusible, interrupteur, bobines, voyant, éclairs), zones de lumière
(aucune fuite par un mur ou un plancher), le Veilleur (taille, pas d'yeux, verre fêlé, reptation au sol), la torche (le faisceau part de la lampe),
la main tenue, la radio, la maison d'Alma, la lanterne éteinte, le fusible tenu, la traduction VOXEL ; puis (sauf --sans-images) de vraies images
PS1 9:16 mesurées : luminance moyenne ≥ 50 et noir bouché < 1/3, y compris dans la PANNE."""
import json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import numpy as np

OK = []; BAD = []


def check(name, cond, detail=''):
    (OK if cond else BAD).append(name)
    print(('ok   ' if cond else 'ÉCHEC'), name, ('' if cond else f': {detail}'))


from hstudio.engines.pixel3d import places as PL, sets as S, phare_interieur as PI, phare_foret as PF, rigfig, veilleur as VE, objets as OD
from hstudio.engines.pixel3d.r3d import wbounds


def box_of(b):
    (x, y, z), (w, h, d) = b['at'], b['size']
    return (x - w / 2, y, z - d / 2, x + w / 2, y + h, z + d / 2)


def inside(blocks, p, tol=0., skip=None):
    for b in blocks:
        if skip and skip(b): continue
        x0, y0, z0, x1, y1, z1 = box_of(b)
        if x0 - tol <= p[0] <= x1 + tol and y0 <= p[1] <= y1 and z0 - tol <= p[2] <= z1 + tol: return b
    return None


def inside_box(boxes, p):
    for b in boxes:
        lo, hi = wbounds(b)
        if b.inst is not None:                                          # oriented box: test in its local frame
            q = (np.asarray(p, np.float32) - b.inst.piv) @ b.inst.R; lo, hi = b.lo, b.hi
        else: q = np.asarray(p, np.float32)
        if np.all(q >= lo) and np.all(q <= hi): return b
    return None


# 1. registration, opt-in
check('lieu « phare_interieur » enregistré', 'phare_interieur' in PL.PLACES and PL.PLACES['phare_interieur'] is PI.phare_interieur)
check('lieux d\'avant toujours là (phare_foret, cinema_salle, forest...)', all(n in PL.PLACES and PL.PLACES[n] is not PI.phare_interieur for n in ('phare_foret', 'cinema_salle', 'forest', 'lycee_riviere')))
check('opt-in : un autre lieu prêt reste un RoomSet ordinaire, phare_foret reste PhareSet', type(S.make_set('forest', {'type': 'forest'})).__name__ == 'RoomSet'
      and type(S.make_set('x', {'type': 'phare_foret'})).__name__ == 'PhareSet')
st = S.make_set('tour', {'type': 'phare_interieur'}); st.build()
check('phare_interieur construit par sa classe (PhareInterieurSet), assez riche, pas trop lourd', type(st).__name__ == 'PhareInterieurSet' and 1200 < len(st.base.boxes) < 3200,
      f'{type(st).__name__}, {len(st.base.boxes)} boîtes')

# 2. expanded place
O = PL.expand('phare_interieur', {})
Bk = O['blocks']
check('déterministe : deux expansions identiques', json.dumps(PL.expand('phare_interieur', {}), sort_keys=True, default=str) == json.dumps(O, sort_keys=True, default=str))
check('nuit, étoiles, aucune pluie, aucune mer', O.get('sky') == 'night' and O.get('stars') and not O.get('weather') and not any(z.get('ground') == 'water' for z in O.get('zones', [])))
need = ('start', 'entree', 'porte', 'entree.porte', 'escalier.pied', 'horloge', 'machines', 'batterie', 'batterie.ecran', 'machines.batterie', 'generateur', 'cabine',
        'machines.generateur', 'vitre', 'interrupteur', 'etiquette', 'bobines', 'trou', 'machines.trou', 'palier', 'palier.porte', 'palier.arrivee', 'haut.pied',
        'escalier.haut', 'haut.sommet', 'commandes', 'commandes.console', 'commandes.porte', 'commandes.mur', 'levier', 'fusible', 'plaque', 'mur_grave',
        'commandes.horloge', 'grille', 'commandes.fenetre', 'palier.fenetre')
missing = [a for a in need if a not in O['anchors']]
check(f'les {len(need)} repères demandés', not missing, str(missing))
check('repères de l\'étage à y 4,2 (palier, commandes), cabine du générateur à y 0,15', O['anchors']['palier'][1] == PI.Y_ETAGE and O['anchors']['commandes'][1] == PI.Y_ETAGE
      and abs(O['anchors']['cabine'][1] - .15) < 1e-6)
check('rayon intérieur ≥ 3,5 m, plafonds ≥ 3 m (rez 3,9 ; étage 3,8)', PI.R_IN >= 3.5 and PI.SLAB0 >= 3. and PI.Y_PLAF - PI.Y_ETAGE >= 3.)

# 3. free zones, collisions
props = O['props']
def prop_boxes_world():
    out = []
    for p in props:
        for b in S.place(S.prop_boxes(p.get('type', 'crate'), p), p['at'][0], p['at'][1], int(p.get('rot', 0)), float(p.get('y', 0.))): out.append(b)
    return out
PB = prop_boxes_world()
sc0 = st.scene({}, 1.0, .5)
dyn = sc0.boxes[len(st.base.boxes):]
bad_z = []
for name, (x, y, z, rad) in PI.ZONES_LIBRES.items():
    for dx, dz in ((0, 0), (rad, 0), (-rad, 0), (0, rad), (0, -rad)):
        for h in (.5, 1.0, 1.6):
            p = (x + dx, y + h, z + dz)
            b = inside(Bk, p)
            if b is not None: bad_z.append((name, p, 'bloc', b['at'])); break
            b2 = inside_box(PB + dyn, p)
            if b2 is not None: bad_z.append((name, p, 'objet/pièce mobile')); break
check(f'zones libres des acteurs ({len(PI.ZONES_LIBRES)} : entrée, pied de l\'escalier, machines, cabine, palier, porte, commandes, console, mur gravé...)', not bad_z, str(bad_z[:3]))
inner = [b for b in Bk if not b.get('group', '').startswith('escalier') and not b.get('group', '').startswith('rampe') and b['material'] not in ('card',)]
furn = [('batterie', PI.BATTERY), ('generateur', (PI.GEN_X[0], PI.GEN_Z[0], PI.GEN_X[1], PI.GEN_Z[1])), ('console', PI.CONSOLE)]
bad_w = [(n, r) for n, r in furn if max(math.hypot(x, z) for x in (r[0], r[2]) for z in (r[1], r[3])) > PI.R_IN - .02]
check('batterie, générateur et console entièrement dans la tour (aucun coin dans le mur rond)', not bad_w, str(bad_w))
ps_out = [(p['type'], p['at']) for p in props if math.hypot(*p['at']) > PI.R_IN - .1]
check(f'objets détaillés posés ({len(props)}) à l\'intérieur du mur', not ps_out, str(ps_out[:3]))
door_free = all(inside(Bk, (x, y, -PI.R_IN - .25)) is None for x in (-.4, 0., .4) for y in (.3, 1.2, 2.1))
check('porte d\'entrée : ouverture réelle dans le mur (sud), praticable', door_free)
dc = (PI.DOOR_ETA[0] + PI.DOOR_ETA[1]) / 2
check('porte des commandes : ouverture libre de 2,6 m (le verre du Veilleur, 2,37 m, se voit dans l\'encadrement)',
      PI.PASS_H >= 2.45 and all(inside(Bk, (dc + dx, PI.Y_ETAGE + y, .7)) is None for dx in (-.4, 0., .4) for y in (.3, 1.3, 2.4)))
check('passage entrée -> machines : ouverture libre', all(inside(Bk, ((PI.PASS_REZ[0] + PI.PASS_REZ[1]) / 2 + dx, y, .6)) is None for dx in (-.4, 0., .4) for y in (.3, 1.3, 2.4)))
op = st.scene({'porte': 1., 'porte_commandes': 1.}, 1.0, .5).boxes[len(st.base.boxes):]
check('portes ouvertes : les battants dégagent le passage (entrée et commandes)', inside_box(op, (0., 1.2, -4.3)) is None and inside_box(op, (dc, PI.Y_ETAGE + 1.2, 1.1)) is None
      and inside_box(op, (dc, PI.Y_ETAGE + 1.2, .7)) is None)
cl = st.scene({'porte': 0., 'porte_commandes': 0.}, 1.0, .5).boxes[len(st.base.boxes):]
check('portes fermées : les battants bouchent l\'ouverture', inside_box(cl, (0., 1.2, -PI.R_IN + .06)) is not None and inside_box(cl, (dc, PI.Y_ETAGE + 1.2, .7)) is not None)
for (name, th, hw, y0, y1, zn) in PI.WINDOWS:
    x, z = PI.pol((PI.R_IN + PI.R_OUT) / 2, th)
    if inside(Bk, (x, (y0 + y1) / 2, z), skip=lambda b: b['material'] == 'metal') is not None:
        check(f'fenêtre {name} percée dans le mur', False, str((x, z))); break
else: check(f'les {len(PI.WINDOWS)} fenêtres sont percées dans le mur (l\'éclair entre)', True)
hx, _ = PI.pol((PI.R_IN + PI.R_OUT) / 2, PI.TROU_TH); _, hz = PI.pol(PI.R_IN, PI.TROU_TH)
cable = inside(Bk, (hx, .05, hz))
check('trou du câble : percé dans le mur au ras du sol, le câble le traverse vers la terre dehors', inside(Bk, (hx, .35, hz), skip=lambda b: b['material'] == 'fabric') is None
      and cable is not None and cable['material'] == 'fabric' and any(b['color'][0] > 80 and b['at'][1] == 0 and math.hypot(b['at'][0], b['at'][2]) > PI.R_OUT for b in Bk if b['material'] == 'stone'))
gx, gz = (PI.GRILLE[0] + PI.GRILLE[2]) / 2, (PI.GRILLE[1] + PI.GRILLE[3]) / 2
check('grille au sol des commandes : trémie dans la dalle, barreaux, au-dessus de la batterie (« sous tes pieds »)',
      inside(Bk, (gx + .02, PI.SLAB0 + .1, gz + .03), skip=lambda b: b['material'] == 'metal') is None and len([b for b in Bk if b['material'] == 'metal' and abs(b['at'][1] - (PI.Y_ETAGE - .035)) < .01]) >= 6
      and PI.BATTERY[0] < gx < PI.BATTERY[2] and PI.BATTERY[1] - .2 < gz < PI.BATTERY[3] + .2)
# stairs: treads, head room, arrival
steps = {v: [b for b in Bk if b.get('group') == f'escalier.{v}'] for v in PI.VOLEES}
ok_t = True; worst = {}
for v, vv in PI.VOLEES.items():
    for k in range(1, PI.NRISE):
        x, y, z = PI.marche(v, k)
        b = inside(steps[v], (x, y - .05, z))
        if b is None or abs(b['at'][1] + b['size'][1] - y) > 1e-3: ok_t = False
        clear = None
        for h in np.arange(.06, 2.6, .04):
            if inside([bb for bb in Bk if not bb.get('group', '').startswith(('escalier', 'rampe'))], (x, y + h, z)) is not None: clear = h; break
        worst[v] = min(worst.get(v, 9.), clear if clear is not None else 9.)
check('escalier : 16 marches par volée, dessus à k x 0,247 m, sur la ligne de foulée (rayon 4,25)', ok_t)
check(f'escalier : dégagement de tête ≥ 1,9 m sur la volée « montee », ≥ 2,45 m sur « haut » (le Veilleur en descend) ; mesuré {worst}',
      worst['montee'] >= 1.9 and worst['haut'] >= 2.45, str(worst))
xa, ya, za = PI.marche('montee', PI.NRISE)
check('arrivée de la volée au palier : sol plein (y 4,2), pas dans la trémie', inside(Bk, (xa, PI.Y_ETAGE - .1, za)) is not None and inside(Bk, (xa, PI.Y_ETAGE + 1., za)) is None)
check('`escalier()` : y monte de 0 à 4,2 sur la volée, le cap regarde le haut (montée) ou le bas (`descend`)',
      PI.escalier('montee', 0)[1] == 0. and abs(PI.escalier('montee', 1)[1] - 4.2) < 1e-6
      and abs(math.cos(PI.escalier('montee', .5)[3] - PI.escalier('montee', .5, True)[3]) + 1) < 1e-6)
check('rambarde de la trémie et mains courantes des deux volées', len([b for b in Bk if b.get('group') == 'rambarde']) >= 20 and all(len([b for b in Bk if b.get('group') == f'rampe.{v}']) >= 16 for v in PI.VOLEES))

# 4. readable texts
txt = [b for b in st.base.boxes if b.tex]
etq = ' '.join(PI.ETIQUETTE)
check('étiquette du générateur = la phrase du récit, lignes ≤ 15 caractères', etq == 'MODE REFLET : MATÉRIALISE CE QUE LE VISITEUR DÉSIRE REVOIR. NE CONSTITUE PAS UNE EXTRACTION.'
      and max(len(l) for l in PI.ETIQUETTE) <= 15, etq)
check('phrase gravée = « CE QUE LE FAISCEAU PREND ATTEND DE L\'AUTRE CÔTÉ », lignes ≤ 14 caractères', ' '.join(PI.GRAVURE) == "CE QUE LE FAISCEAU PREND ATTEND DE L'AUTRE CÔTÉ"
      and max(len(l) for l in PI.GRAVURE) <= 14)
check('afficheur de la batterie = « SEPTIÈME ÉCLAIR AUTOMATIQUE »', ' '.join(PI.BATTERIE) == 'SEPTIÈME ÉCLAIR AUTOMATIQUE')
g = PI.gravure_tex(tuple(PI.GRAVURE)); row = g[34, :, :3].astype(int).sum(-1) > 500; strokes = int(np.sum(row[1:] & ~row[:-1]))
cross = (g[14:30, :, :3].astype(int).sum(-1) > 500)
x0g = (g.shape[1] - (7 * 12 - 6)) // 2; gap = lambda i: int(cross[:, x0g + i * 12 + 5:x0g + i * 12 + 9].sum())
check('mur gravé : 7 traits gravés (texture), les 3 premiers barrés (traits obliques entre les traits)', strokes == 7 and all(gap(i) > 0 for i in (0, 1, 2)) and gap(4) == 0 and gap(5) == 0,
      f'{strokes} traits, interstices {[gap(i) for i in range(6)]}')
for (name, grp, face) in (('mur gravé', 'mur_grave', '+z'), ('étiquettes ÉCHANGE / ARRÊT', 'console.etiquettes', '-z'), ('étiquette du générateur', 'etiquette', '-z')):
    ids = st.groups.get(grp, [])
    ok_f = bool(ids)
    for i in ids:
        b = st.base.boxes[i]; c = (b.lo + b.hi) / 2; n = {'+z': (0, 0, .5), '-z': (0, 0, -.5)}[face]
        p = c + np.array(n, np.float32)
        ok_f = ok_f and (({'+z': 5, '-z': 4}[face]) in b.tex) and math.hypot(p[0], p[2]) < PI.R_IN and inside(Bk, p) is None
    check(f'{name} : texte sur la face tournée vers la pièce, rien devant', ok_f)
ds = [b for b in sc0.boxes[len(st.base.boxes):] if b.tex and 5 in b.tex]
check('afficheur de la batterie : texte tourné vers la salle des machines (+z), rien devant', ds and inside(Bk, ((ds[0].lo + ds[0].hi) / 2 + np.array([0, 0, .5], np.float32))) is None)

# 5. states
R_ = lambda st_, t=1.0: PI.resolve(O['_pi'], st_, t, .5, T=t)
s_a, s_p, s_g, s_b = R_({}), R_({'phare': 'panne'}), R_({'phare': 'generateur'}), R_({'phare': 'brule'})
check('états par défaut : allumé = fusible en place ; panne = fusible arraché + voyant qui clignote ; générateur = interrupteur abaissé, bobines rouges, '
      'cabine éclairée ; brûlé = bobines brûlées, voyant éteint', s_a['fusible'] == 1 and s_p['fusible'] == 0 and s_g['interrupteur'] == 1 and s_g['bobines'] == 'rouges'
      and s_g['cabine'] > 0 and s_b['bobines'] == 'brulees' and s_b['voyant'] == 0)
check('voyant « clignote » : allumé puis éteint au fil du temps', R_({'phare': 'panne'}, .2)['voyant'] == 1 and R_({'phare': 'panne'}, .8)['voyant'] == 0)
check('nombres animables : levier [0, 1] à mi-plan entre les deux, `state` l\'emporte sur le lieu', 0 < PI.resolve(O['_pi'], {'levier': [0, 1]}, 1., .5)['levier'] < 1
      and R_({'phare': 'panne', 'fusible': 1})['fusible'] == 1)
e1 = R_({'eclairs': [.5]}, .52)['eclair']; e2 = R_({'eclairs': [.5]}, 1.9)['eclair']; e0 = R_({'eclairs': [.5]}, .4)['eclair']
check('éclair calé (`eclairs`) : éclat au bon instant, rien avant ni longtemps après', e1 > 1. and e0 == 0 and e2 == 0, f'{e0} {e1} {e2}')
lv = lambda k: max(float(wbounds(b)[1][1]) for b in PI.lever_boxes(k))
check('levier ÉCHANGE : haut à 0, tiré vers l\'opérateur et abaissé à 1', lv(0) > lv(1) + .2)
check('fusible ARRÊT : cartouche en place à 1, sortie à 0,5, absente à 0 (Alma tient `od_fusible`)', len(PI.fuse_boxes(1.)) == 4 and len(PI.fuse_boxes(0.)) == 2
      and float(PI.fuse_boxes(.5)[0].lo[2]) < float(PI.fuse_boxes(1.)[0].lo[2]) - .1 and 'od_fusible' in OD.HELD and 'od_fusible' in OD.KINDS)
sw = lambda k: max(float(wbounds(b)[1][1]) for b in PI.switch_boxes(k)[3:])
check('interrupteur du générateur : levé à 0, abaissé à 1', sw(0) > sw(1) + .1)
em = lambda m: max(float(b.emis) for b in PI.coil_boxes(m, 1.))
check('bobines : froides sans lueur, rouges rougeoient, étincelles (plus de boîtes), brûlées noires', em('froides') == 0 and em('rouges') > .1
      and len(PI.coil_boxes('etincelles', 1.)) > len(PI.coil_boxes('rouges', 1.)) + 10 and em('brulees') <= 1.6
      and max(float(b.col.mean()) for b in PI.coil_boxes('brulees', 1.) if abs(float(b.hi[1] - b.lo[1]) - .09) < 1e-3) < .25)
g1, g0 = PI.booth_glass(1., 0.), PI.booth_glass(0., 0.)
check('vitre de la cabine : dépolie à 1 (trame dense), nette à 0 (rien)', len(g1) == 1 and g1[0].dissolve < .2 and not g0 and PI.booth_glass(.5, 0.)[0].dissolve > g1[0].dissolve)
hands = lambda tr: [b for b in PI.clock_boxes(0., 2., .5, '-z', '11:52', tr, 1.3) if b.inst is not None and abs(float(b.hi[1] - b.lo[1])) > .05]
check('horloges : aiguilles orientées qui tremblent avec `horloge`, immobiles sans', not np.allclose(hands(1.)[0].inst.R, hands(0.)[0].inst.R)
      and np.allclose(PI.clock_boxes(0., 2., .5, '-z', '11:52', 0., 1.3)[-2].inst.R, PI.clock_boxes(0., 2., .5, '-z', '11:52', 0., 2.7)[-2].inst.R))
# 6. light zones
L_a = st.lights({}, 1.0, .5, (0., 1.6, -2.)); L_p = st.lights({'phare': 'panne'}, 1.0, .5, (0., 1.6, -2.))
check('lumières : chacune porte ses poids de zone (5 zones), la lumière de remplissage de la caméra reste la DERNIÈRE',
      all(len(l) >= 7 and len(l[6]) == 5 for l in L_a[:-1]) and len(L_a[-1]) == 4 and L_a[-1][0][2] == -2.)
check('aucune fuite : la lune du dehors n\'éclaire que le dehors ; une lampe du rez n\'éclaire pas l\'étage', any(l[3] >= 399 and tuple(l[6]) == (1., 0., 0., 0., 0.) for l in L_a)
      and all(l[6][3] == 0 and l[6][4] == 0 for l in L_a[:-1] if l[0][1] < 3.9 and l[3] < 50))
P = np.array([[0, 1, -3], [0, 1, 3], [0, 5, -3], [0, 5, 3], [0, 1, -6], [2, 6, 2]], np.float32)
check('zones du lieu : dehors / entrée / machines / palier / commandes', list(PI._zone_fn(P)) == [1, 2, 3, 4, 0, 4] and PI.zone_de((0, 5, 3)) == 4)
pw = lambda L, cat_y: sum(l[2] for l in L[:-1] if l[3] < 50)
check('PANNE : plus de lumière principale (moins de puissance), restent veilleuses, voyant, lune, plaque', pw(L_p, 0) < pw(L_a, 0)
      and any(abs(l[1][1] - .14) < 1e-6 or (l[1][0] == 1.0 and l[1][1] < .2) for l in L_p))
L_f = st.lights({'eclairs': [.9]}, 1.0, .5, (0., 1.6, -2.)) if False else None
S1 = PI.resolve(O['_pi'], {'eclairs': [.9]}, 1.0, .5, T=1.0)
check('éclair : lumière blanche entrant par chaque fenêtre', len(PI.frame_lights(O['_pi'], [], S1, 1.0, (0, 1.6, 0), .5)) > len(PI.frame_lights(O['_pi'], [], R_({}), 1.0, (0, 1.6, 0), .5)))

# 7. the Veilleur
look = {'kind': 'veilleur'}
def vb(xp=None, gait=0., ph=0., t=1.):
    s = dict(x=0., z=0., y=0., heading=0., rig=dict(t=t, phase=ph, gait=gait, head=(0., 0.)), xp=xp or {})
    return rigfig.build(s, look, None, {}, {}, [])[0]
def bounds(bx): return np.min([wbounds(b)[0] for b in bx], 0), np.max([wbounds(b)[1] for b in bx], 0)
lo, hi = bounds(vb())
check(f'Veilleur debout : très grand ({hi[1]:.2f} m, entre 2,2 et 2,45), pieds au sol', 2.2 <= hi[1] <= 2.45 and lo[1] > -.03, f'{lo[1]:.2f} {hi[1]:.2f}')
cyan = [b for b in vb() if b.emis > .5 and b.col[2] > .7 and b.col[0] < .5]
check('Veilleur : aucun œil (aucune boîte cyan lumineuse), gants blancs, tête de verre texturée et pâle', not cyan and any(b.col.mean() > .85 for b in vb())
      and any(b.tex and 5 in b.tex and b.emis > 0 for b in vb()))
lo, hi = bounds(vb({'rampe': 1.}, 1., 1.3))
check(f'Veilleur à quatre pattes (`x_rampe` 1) : ventre au ras du sol ({hi[1]:.2f} m), rien sous le sol', hi[1] < 1.5 and lo[1] > -.08, f'{lo[1]:.2f} {hi[1]:.2f}')
mv = [bounds(vb({'rampe': 1.}, 1., ph))[1][2] for ph in (0., 1.5, 3.)]
check('Veilleur qui rampe : les mains avancent l\'une après l\'autre (la pose change avec la distance parcourue)', max(mv) - min(mv) > .05, str(mv))
t0, t1 = VE.glass_tex(0), VE.glass_tex(16)
check('fissure en sourire : rien à 0, une fêlure sombre au milieu et aux coins à 1 (canal d\'émission coupé dessus)', (t0[..., 4] == 0).sum() == 0 and (t1[..., 4] == 0).sum() > 40
      and t1[18:24, 11, :3].mean() < t1[5, 11, :3].mean())
nb = rigfig.build(dict(x=0., z=0., y=0., heading=0., rig=dict(t=1., phase=0., gait=0., head=(0., 0.))), {'outfit': 'coat'}, None, {}, {}, [])[0]
check('opt-in : un personnage ordinaire n\'est pas un Veilleur (autre nombre de boîtes, pas de tête de verre)', len(nb) != len(vb()) and not any(b.tex and 5 in b.tex and b.emis > 0 for b in nb))
from hstudio.acting import cast as CAST
rc = CAST.resolve_cast({'cast': {'veilleur': {'ref': 'veilleur'}}})['veilleur']
check('bibliothèque : `{"ref": "veilleur"}` donne le Veilleur (kind veilleur, ≈ 2,37 m)', rc.get('kind') == 'veilleur' and abs(rc.get('scale', 0) - 1.2) < 1e-6)

parts = {}
rigfig.PARTS = parts
try: rigfig.build(dict(x=0., z=0., y=0., heading=0., rig=dict(t=1.3, phase=0., gait=0., head=(0., 0.))), look, None, {}, {}, [])
finally: rigfig.PARTS = None
check('Veilleur : parties nommées pour le contrôle de scène (torse, tête, cuisses...) ; les gouttes à part (jamais « torse dans une marche »)',
      all(n in parts for n in ('torso', 'head', 'thighL', 'handR')) and 'gouttes' in parts and min(float(wbounds(b)[0][1]) for b in parts['torso']) > .2)

# 7 bis. the kit's scene QA on a synthetic directed scene (geometry): the Veilleur on the stairs, behind the door, crawling ; Noé in the booth
import tempfile
from hstudio.qa import run as QR
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phare_interieur_sheet as SH
Kq = SH.K; Yq = PI.Y_ETAGE; h0 = PI.escalier('haut', .45, True); h1 = PI.escalier('haut', .06, True)
cam = lambda p, l, f: {'rig': 'path', 'keys': [dict(t=0., pos=p, look=l, fov=f), dict(t=3., pos=p, look=l, fov=f)]}
shots = [dict(lines=[0, 0], set='tour', camera=cam([-1.0, Yq + 1.6, .25], [-.9, Yq + 1.9, -3.4], 62.),
              tracks={'veilleur': [Kq(h0[:3], h0[3]), Kq(h1[:3], h1[3], t=3.)], 'alma': [Kq(PI.ZONES_LIBRES['palier.arrivee'][:3], 1.6, hold='flashlight')]}),
         dict(lines=[1, 1], set='tour', camera=cam([-1.7, Yq + 1.55, 3.7], [-2.0, Yq + 1.7, .6], 58.),
              tracks={'veilleur': [Kq((-2.0, Yq, .22), 0., x_fissure=0.), Kq((-2.0, Yq, .22), 0., x_fissure=1., t=2.5)]}, state={'eclairs': [.6]}),
         dict(lines=[2, 2], set='tour_panne', camera=cam([2.7, 1.65, 2.8], [-1.0, .5, 1.6], 64.),
              tracks={'veilleur': [Kq((1.6, 0, 1.45), -1.62, x_rampe=1.), Kq((.4, 0, 1.6), -1.62, x_rampe=1., t=3.)], 'alma': [Kq((-1.95, 0, 2.2), 1.7, hold='flashlight')]}),
         dict(lines=[3, 3], set='tour_panne', camera=cam([.45, 1.55, 1.15], [.1, 1.7, 3.6], 62.),
              tracks={'noe': [Kq((.28, .15, 3.95), math.pi)], 'alma': [Kq((-.9, 0, 2.4), .4, hold='flashlight')]}, state={'cabine': .5, 'vitre': .5})]
for s_ in shots: s_.update(fx={}, ui={'hud': False}); s_.setdefault('state', {})
epq = {'style': 'pixel3d', 'profile': 'production', 'genre': 'horror', 'music': 'none', 'title': 'TOUR', 'hud': {'title': ['TOUR'], 'part': '', 'hearts': []},
       'sets': {'tour': {'type': 'phare_interieur'}, 'tour_panne': {'type': 'phare_interieur', 'phare': 'panne'}}, 'default_set': 'tour',
       'cast': {'alma': SH.ALMA, 'noe': SH.NOE, 'veilleur': SH.VEILLEUR}, 'grade': {'saturation': .82, 'exposure': 1.2}, 'diversite': False, 'shots': shots}
lq = [{'start': i * 3. + .1, 'end': i * 3. + 2.9, 'text': f'Phrase {i + 1}.', 'speaker': 'narrateur', 'tone': 'serious'} for i in range(4)]
with tempfile.TemporaryDirectory() as td:
    json.dump(epq, open(os.path.join(td, 'episode.json'), 'w', encoding='utf-8')); json.dump(lq, open(os.path.join(td, 'lines.json'), 'w', encoding='utf-8'))
    rq = QR.verify(td, aspect='9:16', style='ps1', images=False, workers=1, log=lambda *a: None)
codes = [(i.code, i.shot, i.who) for i in rq.issues if i.code.startswith(('acteur.dans', 'camera.', 'acteurs.'))]
check('contrôle de scène du kit (géométrie) : Veilleur qui descend, derrière la porte, qui rampe ; Noé dans la cabine : aucun corps dans le décor, aucune caméra dans un mur', not codes, str(codes[:3]))

# 8. the torch: a spot from the lens that follows the hand
def torch(look_, heading=0.):
    L = []
    s = dict(x=1., z=2., y=0., heading=heading, rig=dict(t=1., phase=0., gait=0., head=(0., 0.)), hold='flashlight')
    rigfig.build(s, dict(look_, outfit='coat'), None, {}, {}, L)
    return L
Lt = torch({'torche': True}); Ln = torch({})
sp = [l for l in Lt if len(l) > 5 and l[5] is not None]
check('torche (clé de cast `torche`) : un PROJECTEUR qui part de la lentille, à la main (≤ 45 cm du poing), dirigé devant', len(sp) == 1
      and math.hypot(sp[0][0][0] - 1., sp[0][0][2] - 2.) < .75 and .7 < sp[0][0][1] < 1.4 and sp[0][5][0][2] > .9, str(sp[:1]))
sp2 = [l for l in torch({'torche': True}, math.pi / 2) if len(l) > 5 and l[5] is not None]
check('torche : le faisceau tourne avec le corps (cap +x -> faisceau vers +x)', sp2 and sp2[0][5][0][0] > .9)
check('sans la clé `torche` : la lampe d\'avant, inchangée (aucun projecteur)', not [l for l in Ln if len(l) > 5] and len(Ln) == 1)

# 9. objects of part 4: held hand, radio, Alma's house, dead lantern
MT = PF.main_tenue_blocs
h1, h0 = MT(0, 1., 0, cicatrice=True), MT(0, 1., 0, cicatrice=False)
check('main tenue paume en l\'air : cicatrice en croissant (5 blocs) ou paume LISSE (aucun), même main sinon', len(h1) == len(h0) + 5
      and len([b for b in h1 if b['color'] == list(PF.SCAR)]) == 5 and not [b for b in h0 if b['color'] == list(PF.SCAR)])
palm = h0[0]; thumb = [b for b in h0 if b['size'] in ([.02, .018, .045], [.045, .018, .02])][0]
check('main gauche paume en l\'air : dessus de la paume à y, pouce à GAUCHE des doigts (doigts vers +z -> pouce côté -x)', abs(palm['at'][1] + palm['size'][1] - 1.) < 1e-6
      and thumb['at'][0] < -.03)
alma = [b for b in h0 if b['color'] == list(PF.ALMA_SKIN)]
check('la main d\'Alma dessous (paume plus basse) et ses doigts qui remontent sur le bord', alma and min(b['at'][1] for b in alma) < palm['at'][1] - .02 and len(alma) >= 9)
check('main tenue : `cap` 90 tourne les doigts vers +x', max(b['at'][0] for b in MT(0, 1., 0, cap=90.)[3:11]) > .08)
OM = PL.expand('phare_foret', {'maison_alma': True, 'voiture': {'radio': True}, 'lanterne': 'eteinte', 'mains_tenues': {'cicatrice': False}})
check('maison d\'Alma : seuil (perron), porte, voiture garée à côté, repères', all(a in OM['anchors'] for a in ('maison', 'maison.seuil', 'maison.porte', 'maison.perron'))
      and OM['_phare']['car']['z'] == 106. and len([b for b in OM['blocks'] if b.get('group') == 'maison_alma.perron']) >= 7)
mx = OM['anchors']['maison']; trees = OM['_phare']['trees']
check('maison d\'Alma : aucun arbre dans la maison, son perron ou la voiture', not [t for t in trees if 4.3 - t[2] < t[0] < 12.8 + t[2] and mx[1] - 7.5 - t[2] < t[1] < mx[1] + 3.6 + t[2]])
check('maison d\'Alma : lampe de porche allumée, paillasson, boîte aux lettres', any(b.get('group') == 'maison_alma' and b['material'] == 'light' for b in OM['blocks'])
      and any(b['material'] == 'fabric' and b.get('group') == 'maison_alma.perron' for b in OM['blocks']))
check('main tenue posée par l\'option `mains_tenues` (groupe)', len([b for b in OM['blocks'] if b.get('group') == 'mains_tenues']) == len(h0))
check('voiture : autoradio (+ 4 blocs) seulement avec `radio`', len(PF.voiture_blocs(radio=True)) == len(PF.voiture_blocs()) + 4 and len(PF.voiture_blocs(radio=True)) <= 128)
check('lanterne éteinte pour toujours : plus de faisceau, lentille noire', OM['_phare']['faisceau'] is None and all(b.get('emissive', 0) == 0 for b in OM['blocks'] if b.get('group') == 'lentille'))
sf = S.make_set('x', {'type': 'phare_foret'}); sf.build()
Ld, La = sf.lights({'lanterne_eteinte': 1}, 1.0, .5, (0., 1.6, 0.)), sf.lights({}, 1.0, .5, (0., 1.6, 0.))
check('`state.lanterne_eteinte` : dans un plan, faisceau et lumières de la lanterne coupés', len([l for l in Ld if len(l) > 5 and l[5] is not None]) < len([l for l in La if len(l) > 5 and l[5] is not None])
      and sum(l[2] for l in Ld) < sum(l[2] for l in La))
sr = S.make_set('x', {'type': 'phare_foret', 'voiture': {'radio': True}}); sr.build()
r0 = [b.emis for b in sr.scene({}, 1.0, .5).boxes if False]
check('radio de la voiture : voyant et cadran (groupe voiture.radio) qui grésillent avec `state.radio`', len(sr.groups.get('voiture.radio', [])) == 2
      and len({round(float(sr.scene({'radio': 1}, t, .5).boxes[sr.groups['voiture.radio'][0]].emis), 3) for t in np.arange(0, 2, .1)}) > 1)

# 10. VOXEL: the place translates
from hstudio.voxelgpu import b_sets as BS
bv = BS.get('phare_interieur', {'type': 'phare_interieur'})
check('VOXEL : lieu traduit sans erreur (blocs, ciel)', len(bv.props) >= 1)

# 11. real PS1 images, measured (allumé and PANNE must stay readable)
if '--sans-images' not in sys.argv:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import phare_interieur_sheet as SH
    for v in ('entree', 'commandes_panne', 'machines_panne', 'rampe'):
        _, img, m = SH.render((v, 270, 480))
        check(f'image PS1 « {v} » : lisible (luminance ≥ 50/255, noir bouché < 1/3)', m['luminance'] >= 50 and m['noir'] < .33, str(m))

print(f'\n{len(OK)} contrôles OK, {len(BAD)} en échec')
sys.exit(1 if BAD else 0)
