"""python tools/check_blocking.py
The tests of the blocking layer (stagegeo / blocking / camplan / faceact): spatial continuity, collisions, hands and their causes, camera framing, face layer,
determinism, and the NEGATIVE CONTROL: the first remake of « La Dernière Pompe » (hstudio/voxelgpu/films/remake_pompe.py, shot-by-shot hand-typed coordinates) must be
REFUSED by the same audit, with the defects the owner saw named. No GPU, no network, no API."""
import json, math, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu import stagegeo, blocking as B, camplan as CP, faceact, director, contract as C
from hstudio.voxelgpu.films import pompe_continuite as NEW, remake_pompe as OLD

ok = bad = 0


def check(name, cond, info=''):
    global ok, bad
    if cond: ok += 1; print(f'  OK   {name}')
    else: bad += 1; print(f'  FAIL {name} {info}')


geo = stagegeo.station(NEW.DOORS)
print('1. la géométrie est celle du peintre')
sb = (ROOT / 'voxelgpu_js/engine/sets4b.js').read_text(encoding='utf-8'); rs = (ROOT / 'voxelgpu_js/engine/reserve.js').read_text(encoding='utf-8')
hk = (ROOT / 'voxelgpu_js/engine/horror_kit.js').read_text(encoding='utf-8'); p4 = (ROOT / 'voxelgpu_js/engine/props4.js').read_text(encoding='utf-8')
check('supérette : X0 X1 Z0 Z1 HH', 'X0 = -4.5, X1 = 4.5, Z0 = -7, Z1 = 3.5, HH = 3.2' in sb)
check('comptoir (3.3, 1.2, 1.8 x 0.7) et (3.95, -0.3, 0.7 x 2.4)', 'x: 3.3, y: 0.5, z: 1.2, w: 1.8, h: 1.0, d: 0.7' in sb and 'x: 3.95, y: 0.5, z: -0.3, w: 0.7, h: 1.0, d: 2.4' in sb)
a = [s for s in geo.solids if s.id == 'comptoir_a'][0]; b = [s for s in geo.solids if s.id == 'comptoir_b'][0]
check('comptoir : rectangles de stagegeo', abs(a.x0 - 2.35) < .06 and abs(a.x1 - 4.25) < .06 and abs(b.z0 + 1.5) < .06 and abs(b.z1 - .85) < .06)
check('rayons (-2.6, -0.6, 1.4, mur -4.3)', all(f'shelfUnit({u}' in sb for u in ('-2.6, -5.6, -0.6, 0.8', '-0.6, -5.6, -0.6, 0.8', '1.4, -5.6, -1.6, 0.8', '-4.3, -6.6, 2.0, 0.4')))
check('voiture : 1.9 x 4.4, place passée par le kit', 'w: 1.9, h: 0.5, d: 4.4' in p4 and 'carAt: [4.2, 7.3]' in hk and stagegeo.CAR_AT == (4.2, 7.3))
m = re.search(r'RESERVE = \{ x0: ([\d.]+), x1: ([\d.]+), z0: (-?[\d.]+), z1: (-?[\d.]+), h: ([\d.]+), door: \{ x: ([\d.]+), w: ([\d.]+)', rs)
check('arrière-boutique : mêmes bornes que reserve.js', bool(m) and tuple(map(float, m.groups())) == (.6, 4.4, -12., -7.2, 2.8, 3., .9), m and m.groups())
check('porte du fond : trou de 3.0 à 3.9 dans le mur du peintre', 'b.add({ x: 3.45, y: (2.25 + HH) / 2' in sb and geo.portals['reserve'].rect[0] == 3.0 and geo.portals['reserve'].rect[2] == 3.9)

print('2. les trajets')


def plan_(beats, doors=None, actors=None):
    return B.compile_plan(dict(duration=60., actors=actors or {'h': dict(start='caisse')}, beats=beats), stagegeo.station(doors or NEW.DOORS))


try: plan_([dict(who='h', t=1, do='go', to='dans_reserve', by=9)], {'reserve': [[0, 0]]}); check('porte fermée : refusé', False)
except B.PlanError as e: check('porte fermée : refusé en français, la porte nommée', 'reserve' in str(e) and 'fermé' in str(e), str(e))
try: plan_([dict(who='h', t=1, do='go', to=[-3.5, 3.0], by=3)]); check('trop rapide : refusé', False)
except B.PlanError as e: check('9 m en 2 s : refusé (vitesse maximale)', 'm/s' in str(e), str(e))
C1 = plan_([dict(who='h', t=1, do='go', to='dans_reserve', by=10)], {'reserve': [[0, 0], [.5, 1]]})
check('porte ouverte : le trajet franchit le chambranle (x 3.0..3.9) à z = -7.1', any(3.0 < C1.xz('h', t / 30)[0] < 3.9 and abs(C1.xz('h', t / 30)[1] + 7.1) < .1 for t in range(30, 300)))
check('et aucun solide traversé (audit des corps)', not B.audit_actors(C1))
check('un point dans le comptoir est un solide', geo.hit_body(3.0, 1.2, .28) == 'comptoir_a')
check('la vitrine arrête un corps mais pas le regard', bool(geo.hit_body(1.2, 3.5, .28)) and geo.ray((1.2, 1.5, 6.), (1.2, 1.5, 1.)) is None)
check('un mur arrête le regard', geo.ray((0., 1.5, 1.), (0., 1.5, -10.)) is not None)

print('3. les mains')
Cr = plan_([dict(who='h', t=2, do='touch', target=[3.0, 1.2, 1.58], hand='R')])
check('toucher à 0.9 m du buste : refusé (portée)', any(v.code == 'portée' for v in B.audit_contacts(Cr)))
Cok = plan_([dict(who='h', t=1, do='go', to='comptoir_clients', by=5, face=math.pi), dict(who='h', t=5.2, do='take', target='torche', hand='R', until=60)])
check('prendre la torche depuis le repère du comptoir : accepté', not B.audit_contacts(Cok), B.audit_contacts(Cok))
ct = B.contacts_for_painter(Cok, 0, 60)
check('le contact part de la pose normale (poids 0) pour y arriver (poids 1)', ct and ct[0]['keys'][0][4] == 0. and max(k[4] for k in ct[0]['keys']) == 1.)

print('4. le nouveau film')
ep = NEW.episode(); Cn, g2 = B.compile_episode(ep); shots = []; t0 = 0.
for s in ep['shots']: shots.append(dict(s, _t0=t0)); t0 += float(s['dur'])
viol, rep = B.preflight(ep, Cn, g2, [s for s in shots if s.get('frame')])
check('préparation : 0 problème (corps, mains, portes, caméras)', not viol, viol[:3])
check('44 plans, mêmes coupes que la source', len(ep['shots']) == 44 and NEW.CUTS == OLD.CUTS and abs(sum(s['dur'] for s in ep['shots']) - NEW.DUR) < 1e-3)
check('le pompiste reste DANS la boutique pendant tout le film', all(geo.zone_at(*Cn.xz('clerk', t / 10.)) == 'boutique' for t in range(0, 964, 3)))
check("le monstre reste DEHORS jusqu'à la porte de service (t < 53 s)", all(geo.zone_at(*Cn.xz('ghost', t / 10.)) not in ('boutique', 'reserve') for t in range(0, 530, 3)))
check("puis il entre par la porte de service et reste dans l'arrière-boutique", all(geo.zone_at(*Cn.xz('ghost', t / 10.)) == 'reserve' for t in range(600, 964, 3)))
check('il est à la porte de service avant le premier coup', abs(Cn.xz('ghost', 47.0)[0] - 5.1) < .1 and abs(Cn.xz('ghost', 47.0)[1] + 11.) < .1)
steps = [math.hypot(Cn.xz(a, (t + 1) / 30)[0] - Cn.xz(a, t / 30)[0], Cn.xz(a, (t + 1) / 30)[1] - Cn.xz(a, t / 30)[1]) for a in ('clerk', 'ghost') for t in range(0, 2893)]
check(f'aucun saut > 0.2 m entre deux images (max {max(steps):.3f} m)', max(steps) < .2)
cc = director.build(ep, '9:16', 30)
check('contrat valide, avec contacts et couche visage', not C.validate(cc) and any(st.get('contacts') for st in cc['stages']) and any(st.get('faces') for st in cc['stages']))
check('le contrat final, audité à la sortie, est propre', not B.audit_contract(cc, geo), B.audit_contract(cc, geo)[:2])
check('monde persistant : portes et lumières identiques dans les 44 plans', all(s['env'].get('res_door') == NEW.WORLD_ENV['res_door'] and s['env'].get('lamps') == NEW.WORLD_ENV['lamps'] for s in cc['stages']))
check('déterministe : deux constructions, même empreinte', C.digest(director.build(NEW.episode(), '9:16', 30)) == C.digest(cc))

print('5. contre-exemple : le premier remake')
oc = director.build(OLD.episode(), '9:16', 30); ov = B.audit_contract(oc, geo); codes = {}
for v in ov: codes[v.code] = codes.get(v.code, 0) + 1
print('      ', ', '.join(f'{k}: {n}' for k, n in codes.items()))
for v in ov[:6]: print('      ', v)
check('le premier remake est refusé', len(ov) > 0)
check('… pour des téléportations entre plans', codes.get('téléportation', 0) >= 3, codes)
check('… pour un personnage dans le comptoir', any(v.code == 'solide' and v.data.get('solid') == 'comptoir_a' for v in ov))
check('… pour un passage dedans/dehors sans porte', codes.get('passage', 0) >= 1, codes)
bad_shot = dict(id='X', dur=2., _t0=10., frame=dict(show=['voiture'], kind='wide'), camera=dict(rig='path', keys=[dict(t=0, pos=[4.6, 1.0, 9.0], look=[4.2, 1., 7.3], fov=62), dict(t=2., pos=[4.6, 1.0, 9.0], look=[4.2, 1., 7.3], fov=62)]))
vs, _ = CP.audit_shot(bad_shot, Cn, geo)
check("un cadrage serré sur la voiture : refusé (pas entière / dans un solide)", any(v.code in ('repère_coupé', 'caméra_dans_solide') for v in vs), vs)
wall = dict(bad_shot, frame=dict(actors=['clerk'], kind='medium'), camera=dict(rig='path', keys=[dict(t=0, pos=[-6., 1.5, 0.], look=[2.3, 1.5, 2.9], fov=60), dict(t=2., pos=[-6., 1.5, 0.], look=[2.3, 1.5, 2.9], fov=60)]))
vs, _ = CP.audit_shot(wall, Cn, geo)
check('une caméra à travers le mur ouest : refusée', any(v.code in ('caméra_dans_solide', 'acteur_masqué', 'écran_bouché') for v in vs), vs)
zoom = dict(bad_shot, frame=dict(show=['vitrine'], kind='wide'), camera=dict(rig='path', keys=[dict(t=0, pos=[0., 1.6, 20.], look=[0., 1.6, 3.5], fov=70), dict(t=2., pos=[0., 1.6, 20.], look=[0., 1.6, 3.5], fov=36)]))
vs, _ = CP.audit_shot(zoom, Cn, geo)
check('un zoom de 70° à 36° est refusé', any(v.code == 'zoom' for v in vs), vs)

print('6. les cadrages du nouveau film')
rows = {r['id']: r for r in rep['shots']}
for sid in ('S22', 'S33', 'S34', 'S40'): check(f"{sid} : la voiture est ENTIÈRE dans l'image", rows[sid]['show']['voiture']['whole'])
check("S34 : la porte d'entrée et la voiture ensemble", rows['S34']['show']['entree']['whole'] and rows['S34']['show']['voiture']['whole'])
check('S33 : la voiture prend au moins 30 % de la largeur, avec la vitrine entière', rows['S33']['show']['voiture']['share_w'] >= .3 and rows['S33']['show']['vitrine']['whole'])
check('S36 : la porte du fond entière', rows['S36']['show']['porte_reserve']['whole'])
check('S30/S31 : le tableau électrique entier', rows['S30']['show']['tableau_elec']['whole'] and rows['S31']['show']['tableau_elec']['whole'])
check('aucun zoom : focale ≥ 56° partout, jamais de variation', all(r['fov'][0] >= 56 and r['fov'][1] - r['fov'][0] < .01 for r in rows.values()))
check(f"gros plans : {rep['tight_share'] * 100:.0f} % du film, inserts : {rep['inserts']}", rep['tight_share'] <= .2 and rep['inserts'] <= 3)
check('visages : tête ≤ 50 % de la largeur partout', all(x['head_share'] <= .5 for r in rows.values() for x in r['actors'].values()))

print('7. les visages')
EX = C.EXPRESSIONS; fr = faceact.build(Cn, 'clerk', director.EXPR_MAP, EX, 96.5); ci = {n: i for i, n in enumerate(faceact.FACE_COLS)}
at = lambda t: fr[int(t * faceact.HZ)]
names = lambda t: (EX[int(at(t)[ci['e1']])], EX[int(at(t)[ci['e2']])])
check('la peur vient APRÈS le premier coup (47.1 s) : pas avant, là à 47.5 s', 'scared' not in names(47.0) or at(47.0)[ci['i1']] < at(47.5)[ci['i1']] + .3)
check('… et à 47.5 s le visage a changé', 'scared' in names(47.5))
check('le regard va vers la cause : regard à 47.8 s ≠ à 46.0 s', abs(at(47.8)[ci['lx']] - at(46.0)[ci['lx']]) > .05 or abs(at(47.8)[ci['ly']] - at(46.0)[ci['ly']]) > .05)
bl = lambda a, b: sum(1 for k in range(int(a * faceact.HZ), int(b * faceact.HZ)) if fr[k][ci['blink']] > .9 and fr[k - 1][ci['blink']] <= .9)
check(f'clignements plus rares sous tension (calme 0-12 s : {bl(0, 12)}, tendu 76-88 s : {bl(76, 88)})', bl(76, 88) <= bl(0, 12))
check('micro-expression : le sourcil se relève après la cause (37.1 s) puis retombe', fr[int(37.4 * faceact.HZ)][ci['bdi']] < fr[int(36.0 * faceact.HZ)][ci['bdi']] - .5 and abs(fr[int(39.5 * faceact.HZ)][ci['bdi']]) < abs(fr[int(37.4 * faceact.HZ)][ci['bdi']]))
check('visage déterministe', faceact.build(Cn, 'clerk', director.EXPR_MAP, EX, 96.5) == fr)
print(f'\n{ok} vérifications OK, {bad} en échec'); sys.exit(1 if bad else 0)
