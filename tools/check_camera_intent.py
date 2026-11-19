"""python tools/check_camera_intent.py
Tests of the artistic camera layer: hstudio/voxelgpu/camplan.py (measurements and audit) + hstudio/voxelgpu/cinematic_intent.py (shot grammar, preflight, events).
POSITIVE tests: a beat gets a shot chosen for its purpose that passes the preflight, with the measured property the purpose asks for.
NEGATIVE tests: the framings the owner rejected (car too small or cut, door and car gap unreadable, wall in the lens, menace hidden behind the subject, flat shot,
wrong size of shot, an event not filmed, a POV that sees what the body is turned away from) are REFUSED by the same audit, in French.
REGRESSION: the cameras of the continuity film at 19e2211 are reproduced identically (tests/camera/pompe_cameras_19e2211.json): nothing changed for existing films.
No GPU, no network, no API, no full render."""
import json, math, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'tools'))
from hstudio.voxelgpu import stagegeo, blocking as B, camplan as CP, cinematic_intent as CI
from hstudio.voxelgpu.films import pompe_continuite as N, remake_pompe as OLD

ok = bad = 0
T = OLD.T


def check(name, cond, info=''):
    global ok, bad
    if cond: ok += 1; print(f'  OK   {name}')
    else: bad += 1; print(f'  FAIL {name} {info}')


geo = stagegeo.station(N.DOORS); C = B.compile_plan(N.plan(), geo)


def shot(frame, pos, look, fov, t0, dur=2., cam=None, sid='X'):
    keys = [dict(t=0., pos=list(pos), look=list(look), fov=fov, roll=0.), dict(t=dur, pos=list(pos), look=list(look), fov=fov, roll=0.)]
    return dict(id=sid, dur=dur, _t0=t0, frame=frame, camera=cam or {'rig': 'path', 'keys': keys})


def codes(s): v, m = CP.audit_shot(s, C, geo); return {x.code for x in v}, v, m


def beat(i, **kw): return dict(id=f'S{i:02d}', t0=T[i], t1=T[i + 1], **kw)


print('1. non-regression : rien ne change pour les films existants')
snap = json.load(open(ROOT / 'tests/camera/pompe_cameras_19e2211.json', encoding='utf-8')); ep = N.episode()
new = {s['id']: s['camera'] for s in ep['shots']}
check('les 44 caméras du film de continuité (19e2211) sont identiques au centième', json.dumps(new, sort_keys=True) == json.dumps(snap, sort_keys=True))
Cn, g2 = B.compile_episode(ep); shots = []; t0 = 0.
for s in ep['shots']: shots.append(dict(s, _t0=t0)); t0 += float(s['dur'])
viol, rep = B.preflight(ep, Cn, g2, [s for s in shots if s.get('frame')])
check('la préparation du film de continuité reste à 0 problème', not viol, viol[:2])
check('les cadres existants n\'utilisent aucune clé artistique (comportement inchangé)', not any(k in (s.get('frame') or {}) for s in ep['shots'] for k in CP.EXTRA_KEYS))

print('2. la distance porte / voiture : ce que dit le scénario et ce que mesure la géométrie')
gap_near = CP.floor_gap(geo, 'entree', 'voiture'); ca = geo.land('entree'); cb = geo.land('voiture')
centre_to_edge = math.dist(((ca[0] + ca[3]) / 2, ca[2]), (min(max((ca[0] + ca[3]) / 2, cb[0]), cb[3]), min(max(ca[2], cb[2]), cb[5])))
check(f'de la porte à la voiture : {gap_near:.2f} m entre les deux bords les plus proches, {centre_to_edge:.2f} m du centre de la porte au bord de la voiture (« trois mètres »)', abs(centre_to_edge - 3.) < .25, centre_to_edge)
check('la voiture du lieu a les dimensions du peintre (1,9 x 4,4 m tournée de 0,25 rad : boîte 2,92 x 4,73 m)', abs((cb[3] - cb[0]) - 2.92) < .02 and abs((cb[5] - cb[2]) - 4.74) < .02, (cb[3] - cb[0], cb[5] - cb[2]))

print('3. NÉGATIF : les cadrages que le propriétaire a refusés')
fr_car = dict(show=['voiture'], kind='wide', scale={'voiture': [.28, .85]}, preflight=True)
c, v, m = codes(shot(fr_car, (4.2, 1.6, 36.), (4.2, 1.0, 7.3), 64., T[22], 1.5))
check('la voiture trop loin (une tache) : refusée', 'échelle_trop_petite' in c, c)
c, v, m = codes(shot(fr_car, (4.2, 1.4, 12.2), (4.2, 1.0, 7.3), 64., T[22], 1.5))
check('la voiture trop près (coupée) : refusée', 'échelle_trop_grande' in c or 'repère_coupé' in c, c)
fr_gap = dict(show=['entree', 'voiture'], kind='wide', gap=dict(a='entree', b='voiture', min=.075), preflight=True)
# among the cameras that show the door AND the whole car, the gap is read well from one and badly from another: the measure must tell them apart
ts34 = [T[34], (T[34] + T[35]) / 2, T[35]]; pts34 = [((b_[0] + b_[3]) / 2, (b_[1] + b_[4]) / 2, (b_[2] + b_[5]) / 2) for b_ in (geo.land('entree'), geo.land('voiture'))] + [(*C.xz('clerk', t_)[:1], 1.35, C.xz('clerk', t_)[1]) for t_ in ts34]
aim34 = (sum(p_[0] for p_ in pts34) / len(pts34), 1.3, sum(p_[2] for p_ in pts34) / len(pts34)); seen = []
fr_seen = dict(show=['entree', 'voiture'], actors=['clerk'], kind='wide', preflight=True)
for px in range(-12, 16, 2):
    for pz in range(-9, 30, 2):
        for fv in (66., 72.):
            if geo.solid_at_point((px, 1.7, pz), .25): continue
            okk, _sc, _why = CP._eval(geo, C, (px, 1.7, pz), aim34, fv, CP.ASPECT['9:16'], ts34, ['entree', 'voiture'], ['clerk'], 'wide', fr_seen, pts34, None)
            if okk: seen.append((CP.gap_len(geo, (px, 1.7, pz), aim34, fv, CP.ASPECT['9:16'], 'entree', 'voiture'), px, pz, fv))
seen.sort(); worst, best = seen[0], seen[-1]
print(f'       {len(seen)} caméras montrent la porte et la voiture entières : écart lisible de {worst[0]:.3f} (pire) à {best[0]:.3f} (meilleur) hauteur d\'image')
check('parmi elles, la mesure sépare la pire (écart illisible) de la meilleure (écart lisible)', worst[0] < .075 <= best[0], (worst, best))
c, v, m = codes(shot(fr_gap, (worst[1], 1.7, worst[2]), aim34, worst[3], T[34], T[35] - T[34]))
check('la pire de ces caméras : refusée pour « écart illisible »', 'écart_illisible' in c, c)
c, v, m = codes(shot(dict(fr_gap, actors=['clerk'], scale={'voiture': [.2, .9]}), (best[1], 1.7, best[2]), aim34, best[3], T[34], T[35] - T[34]))
check('la meilleure : l\'écart ne fait pas partie des refus', 'écart_illisible' not in c, c)
c, v, m = codes(shot(dict(actors=['clerk'], kind='medium', preflight=True), (3.9, 1.55, -6.55), (3.9, 1.5, -7.2), 60., T[34], 2.))
check('un mur à 0,6 m dans l\'objectif : refusé', 'mur_dans_l_objectif' in c or 'écran_bouché' in c, c)
c, v, m = codes(shot(dict(actors=['clerk'], kind='medium'), (-6., 1.5, 0.), (2.3, 1.5, 2.9), 60., T[34], 2.))
check('caméra à travers le mur ouest : refusée', bool(c & {'caméra_dans_solide', 'acteur_masqué', 'écran_bouché'}), c)
t = T[9]; cx_, cz_ = C.xz('clerk', t + 1); gx_, gz_ = C.xz('ghost', t + 1); d_ = math.hypot(cx_ - gx_, cz_ - gz_); u_ = ((cx_ - gx_) / d_, (cz_ - gz_) / d_)
behind = (cx_ + u_[0] * 1.6, 1.6, cz_ + u_[1] * 1.6)
c, v, m = codes(shot(dict(actors=['clerk'], kind='medium', threat=dict(id='ghost', hidden=[0., .6]), preflight=True), behind, (gx_, 1.4, gz_), 60., t, 2.))
check('la menace cachée derrière le sujet lui-même : refusé (menace illisible ou trop cachée)', bool(c & {'menace_illisible', 'menace_trop_cachée'}), c)
c, v, m = codes(shot(dict(actors=['clerk'], kind='wide', threat=dict(id='ghost', hidden=[.3, .9]), preflight=True), (-5., 1.6, 12.), (.4, 1.3, 3.9), 64., T[9], 1.5))
check('menace entièrement à découvert alors que le plan devait la cacher en partie : refusé', 'menace_trop_visible' in c, c)
px_, pz_ = C.xz('clerk', T[28] + 1.)
c, v, m = codes(shot(dict(actors=['clerk'], kind='medium', min_layers=2, preflight=True), (px_ - 3.4, 1.5, pz_), (px_, 1.45, pz_), 60., T[28], 2.))
check('sujet collé contre le mur de l\'affiche, sans fond ni premier plan : « plan plat » refusé', 'plan_plat' in c, c)
w = (T[32], T[33]); sz = dict(subject='clerk', body_h=list(CP.BODY_H['close']), name='close')
c, v, m = codes(shot(dict(actors=['clerk'], kind='close', size=sz, preflight=True), (2.3, 1.7, 11.), (2.3, 1.4, 3.), 62., w[0], 1.4))
check('un plan annoncé « close » qui est en réalité un plan large : refusé', 'taille_de_plan' in c, c)
c, v, m = codes(shot(dict(show=['voiture'], kind='wide', preflight=True), (7.8, 1.4, 5.6), (4.2, 1., 7.3), 66., T[22], 1.5))
c2, v2, m2 = codes(shot(dict(show=['voiture'], kind='wide', preflight=True), (4.2, 2.2, -4.), (4.2, 1., 7.3), 70., T[22], 1.5))
check('la voiture vue derrière le comptoir (cachée en partie) : refusée', bool(c2 & {'repère_en_partie_masqué', 'repère_masqué', 'écran_bouché'}), c2)
fx, fz = C.xz('clerk', T[32] + .7)
c, v, m = codes(shot(dict(actors=['clerk'], kind='medium', avoid=[-.1, .2]), (fx, 1.95, fz + 2.3), (fx, 1.95, fz), 60., T[32], 1.4))
check('visage dans la bande des sous-titres : refusé', 'bandeau_sur_visage' in c, c)
try:
    CI.plan_shot(CI.Ctx(geo, C), CI.normalise(beat(39, purpose='pov', pov='clerk', sees='comptoir'), geo, C), 'pov'); check('POV vers ce que le corps tourne le dos : refusé', False)
except B.PlanError as e: check('POV vers ce que le corps tourne le dos : refusé en français', 'pov' in str(e).lower() or 'regard' in str(e) or 'tourné' in str(e), str(e)[:200])
try: CI.normalise(dict(id='Z', purpose='danger', t0=1, t1=2, subject='clerk'), geo, C); check('danger sans menace : refusé', False)
except B.PlanError as e: check('danger sans menace : refusé en français', 'menace' in str(e), str(e))
try: CI.normalise(dict(id='Z', purpose='relation', t0=1, t1=2, subject='nobody'), geo, C); check('sujet inconnu : refusé', False)
except B.PlanError as e: check('sujet inconnu : refusé, nommé', 'nobody' in str(e), str(e))

print('4. POSITIF : un plan choisi pour son but')
ctx = CI.Ctx(geo, C, '9:16', avoid=[-.1, .2])
s34 = CI.plan_shot(ctx, CI.normalise(beat(34, purpose='relation', subject='clerk', show=['entree', 'voiture'], gap=('entree', 'voiture'), tension=.7), geo, C))
met = s34['metrics']; ex = [e for e in met['extra'] if e]
check('S34 : la porte et la voiture entières', met['show']['entree']['whole'] and met['show']['voiture']['whole'], met['show'])
check('S34 : l\'écart de 3 m se lit (≥ 0,075 hauteur d\'image)', min(e['gap'] for e in ex) >= .075, [e['gap'] for e in ex])
check('S34 : la voiture prend entre 28 et 85 % de la largeur', .28 <= met['show']['voiture']['share_w'] <= .85, met['show']['voiture'])
check('S34 : le pompiste est dans l\'image', met['actors']['clerk']['inframe'])
check('S34 : aucun zoom, focale ≥ 56° et constante', met['fov'][0] >= 56 and abs(met['fov'][1] - met['fov'][0]) < .01, met['fov'])
check('S34 : aucune violation de préparation', not s34['violations'], s34['violations'][:2])
s09 = CI.plan_shot(ctx, CI.normalise(beat(9, purpose='danger', subject='clerk', threat='ghost', tension=.9, occlude=True), geo, C))
check('S09 : plan de danger choisi (menace nommée dans le style), préparation propre', 'danger' in s09['style'] and not s09['violations'], s09['style'])
th = [e['threat'] for e in s09['metrics']['extra'] if e and 'threat' in e]
check('S09 : la tête de la menace est lisible à tous les instants mesurés', th == [] or all(x['head'] for x in th), th)
sh = {k: v for k, v in s09.items() if k in ('style', 'relaxed')}; print('       ', sh)
s11 = CI.plan_shot(ctx, CI.normalise(beat(11, purpose='disappear', witness='clerk', event=dict(kind='vanish', who='ghost', t=26.5), tension=.9), geo, C))
keys = s11['camera']['keys']
check('S11 disparition : caméra FIXE (aucun suivi de marche)', not isinstance(keys[0]['pos'], dict) and math.dist(keys[0]['pos'], keys[1]['pos']) < 1e-6)
check('S11 disparition : le corps est dans l\'image à l\'instant de l\'événement, le témoin aussi', not CI.audit_event(s11, C, geo), CI.audit_event(s11, C, geo))
check('S11 disparition : l\'endroit est dans l\'image (point d\'intérêt)', all(p['inframe'] for e in s11['metrics']['extra'] if e for p in e['points']))
fol = dict(s11, camera={'rig': 'path', 'keys': [dict(t=0., pos=dict(on='ghost', dx=-2., dz=3., h=1.6), look=dict(on='ghost', h=1.4), fov=62., roll=0.), dict(t=1., pos=dict(on='ghost', dx=-2., dz=3., h=1.6), look=dict(on='ghost', h=1.4), fov=62., roll=0.)]})
check('NÉGATIF : une caméra qui SUIT le corps pendant l\'événement : refusée', any(v.code == 'disparition_suivie' for v in CI.audit_event(fol, C, geo)))
late = dict(s11, camera=CI.camera_keys(s11['dur'], (-3., 1.6, -4.), (8., 1.3, -4.), 60.))
check('NÉGATIF : l\'acteur hors de l\'image à l\'instant : « événement non filmé »', any(v.code == 'événement_non_filmé' for v in CI.audit_event(late, C, geo)))
evs = CI.audit_blocking_events(C, [dict(kind='vanish', who='ghost', t=26.4), dict(kind='appear', who='ghost', t=27.6)])
check('INTERFACE blocage : le film marche encore 2 m après « il disparaît » : signalé (à retirer côté blocage)', any(v.code == 'disparition_marchée' for v in evs), evs)
s39 = CI.plan_shot(ctx, CI.normalise(beat(39, purpose='pov', pov='clerk', sees='porte_reserve', tension=.8), geo, C), 'pov')
check('S39 POV : la caméra suit l\'œil du pompiste, devant son visage, et voit la porte du fond', isinstance(s39['camera']['keys'][0]['pos'], dict) and s39['camera']['keys'][0]['pos'].get('on') == 'clerk' and s39['metrics']['show']['porte_reserve']['whole'])

print('5. tailles de plan dynamiques, rythme, champ / contre-champ')
its = [dict(id=f'R{k}', purpose=p, t0=T[a], t1=T[a + 1], subject='clerk', tension=tn, threat='ghost' if p == 'danger' else None) for k, (p, a, tn) in enumerate(
    [('establish', 0, .2), ('danger', 14, .55), ('reaction', 32, .5), ('reaction', 33, .8), ('reaction', 34, .85), ('relation', 33, .6), ('reaction', 38, .95), ('reaction', 41, .95)])]
for i in its:
    if i['threat'] is None: i.pop('threat')
its[0].update(show=['vitrine'], subject='ghost'); its[5].update(show=['voiture', 'vitrine'])
sz = CI.assign_sizes([CI.normalise(i, geo, C) for i in its], tight_max=.2)
print('       ', sz)
check('au moins 3 tailles de plan différentes dans la séquence', len(set(sz)) >= 3, sz)
check('jamais le même gros plan deux fois de suite sur le même sujet', all(not (a == b == 'close') for a, b in zip(sz, sz[1:])), sz)
tot = sum(i['t1'] - i['t0'] for i in its)
tight = sum(i['t1'] - i['t0'] for i, s_ in zip(its, sz) if s_ == 'close')
check(f'les gros plans restent sous 20 % du temps ({tight / tot * 100:.0f} %) sans être interdits', tight / tot <= .2 + 1e-9 and 'close' in CI.assign_sizes([CI.normalise(i, geo, C) for i in its], tight_max=.6))
fake = lambda i, kind, side, who=('clerk', 'ghost'): dict(id=i, kind=kind, t0=0., dur=1., subjects=list(who), purpose='dialogue', side=side, violations=[], event=None, camera={'keys': [dict(pos=[0., 1.6, 0.])]})
sv = CI.audit_sequence([fake('A', 'ots', 1), fake('B', 'ots', -1)], C, geo)
check('NÉGATIF : champ / contre-champ qui change de côté de l\'axe : refusé (180°)', any(v.code == 'axe_franchi' for v in sv), sv)
check('POSITIF : même côté de l\'axe : accepté', not any(v.code == 'axe_franchi' for v in CI.audit_sequence([fake('A', 'ots', 1), fake('B', 'ots', 1)], C, geo)))
jc = lambda i, x, z, t0_: dict(id=i, kind='full', t0=t0_, dur=1., subjects=['clerk'], purpose='reaction', side=None, violations=[], event=None, camera={'keys': [dict(pos=[x, 1.6, z])]})
check('NÉGATIF : deux plans de même taille sur le même sujet, caméra déplacée de quelques degrés : « saut de plan » refusé',
      any(v.code == 'saut_de_plan' for v in CI.audit_sequence([jc('J1', 2.3, 8., 60.), jc('J2', 2.7, 8., 61.)], C, geo)))
check('POSITIF : la même paire avec la caméra 90° plus loin : acceptée', not any(v.code == 'saut_de_plan' for v in CI.audit_sequence([jc('J1', 2.3, 8., 60.), jc('J2', 8., 2.9, 61.)], C, geo)))
mono = [fake(f'M{i}', 'full', 0, ('clerk',)) for i in range(3)]
check('NÉGATIF : trois plans de la même taille de suite : refusé (rythme)', any(v.code == 'rythme_monotone' for v in CI.audit_sequence(mono, C, geo)))

print('6. refus honnête, déterminisme, banc d\'essai')
try:
    CI.plan_shot(CI.Ctx(geo, C, degrade=False), CI.normalise(beat(34, purpose='relation', subject='clerk', show=['porte_service', 'voiture'], gap=('porte_service', 'voiture')), geo, C), 'wide')
    check('un plan impossible est refusé en français (porte de service et voiture : deux côtés du bâtiment)', False)
except B.PlanError as e: check('un plan impossible est refusé en français, avec la raison', 'aucun plan' in str(e) and ('refusée' in str(e) or 'caméra' in str(e)), str(e)[:160])
a1 = CI.plan_shot(CI.Ctx(geo, C, avoid=[-.1, .2]), CI.normalise(beat(34, purpose='relation', subject='clerk', show=['entree', 'voiture'], gap=('entree', 'voiture'), tension=.7), geo, C))
check('déterministe : deux planifications, mêmes clés de caméra', json.dumps(a1['camera'], sort_keys=True) == json.dumps(s34['camera'], sort_keys=True))
rp = ROOT / 'docs/camera_intent/report.json'
if rp.exists():
    R = json.load(open(rp, encoding='utf-8')); tt = R['totals']
    check(f"banc d'essai commité : INTENT {tt['INTENT']['beats_ok']}/{tt['INTENT']['beats']} plans acceptés, 0 violation de sécurité", tt['INTENT']['safety_violations'] == 0 and tt['INTENT']['beats_ok'] >= 8)
    check('… et mieux que E1, E1+geo, E2 et le solveur actuel sur le même critère', all(tt['INTENT']['beats_ok'] > tt[n]['beats_ok'] for n in ('E1', 'E1+geo', 'E2', 'SOLVER')), {n: tt[n]['beats_ok'] for n in tt})
    check('… avec plus de violations de sécurité chez E1 et E2 que chez INTENT (E1 ne connaît pas le lieu)', tt['E1']['safety_violations'] > 0 and tt['E2']['safety_violations'] > 0)
else: check('banc d\'essai commité (docs/camera_intent/report.json)', False, 'lancer tools/camera_benchmark.py')
print(f'\n{ok} vérifications OK, {bad} en échec'); sys.exit(1 if bad else 0)
