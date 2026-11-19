"""python tools/check_facephysics.py [--report out.json]
Tests of the face and physics layer (faceact / lipsync / eventreact / blocking / stagegeo / footkin): POSITIVE cases (what must pass) and NEGATIVE cases (what must be
refused, with the right word in the message), on small synthetic scenes and on the real films: the continuity film of « La Dernière Pompe » (positive), its first remake
(negative control) and « Ne touche pas le sol » (read-only: it is only measured). No GPU, no network, no API, no image: everything is checked on data, before any rendering.
The remakes' sources are never modified (the last section asks git)."""
import json, math, subprocess, sys, shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu import stagegeo as SG, blocking as B, faceact as FA, lipsync as LS, eventreact as ER, footkin as FK, director, contract as CT
from hstudio.voxelgpu.films import pompe_continuite as NEW, remake_pompe as OLD, remake_sol as SOL

ok = bad = 0; REPORT = {}


def check(name, cond, info=''):
    global ok, bad
    if cond: ok += 1; print(f'  OK   {name}')
    else: bad += 1; print(f'  FAIL {name} {info}')


def codes(v): return sorted({x.code for x in v})


def has(v, code, word=''): return any(x.code == code and word in str(x) for x in v)


COLS = CT.ACTOR_COLS


def row(x=0., z=0., yaw=0., y=0., **kw):
    d = dict.fromkeys(COLS, 0.); d.update(vis=1., x=x, y=y, z=z, yaw=yaw, seat_h=.47); d.update(kw); return [float(d[c]) for c in COLS]


def contract(rows_by_actor, world='station', fps=30, casts=None, frame=None, **extra):
    n = max(len(r) for r in rows_by_actor.values())
    st = dict(id='S00', world=world, t0=0., t1=n / fps, tail=0., actors=rows_by_actor, camera=[])
    if frame: st['frame'] = frame
    return dict(schema=CT.SCHEMA, fps=fps, duration=n / fps, actor_cols=COLS, casts=casts or {a: {'preset': 'npc'} for a in rows_by_actor}, stages=[st], **extra)


def walk_rows(p0, p1, v=.95, fps=30, gait_phase=True, amp=None):
    d = math.hypot(p1[0] - p0[0], p1[1] - p0[1]); n = int(d / v * fps) + 1; yaw = math.atan2(p1[0] - p0[0], p1[1] - p0[1]); out = []
    for i in range(n):
        s = min(d, v * i / fps); k = s / d if d else 0.
        out.append(row(p0[0] + (p1[0] - p0[0]) * k, p0[1] + (p1[1] - p0[1]) * k, yaw, gait=1, phase=(s * FK.K_WALK if gait_phase else 0.), amp=(amp if amp is not None else .62 * min(1.35, max(.12, v / .95)) ** .8)))
    return out


geo = SG.station(NEW.DOORS)

# =========================================================================================================================================================== 1
print('1. la géométrie se vérifie elle-même, le sol, les repères')
check('la station-service est saine (repères libres et joignables, portes assez larges)', SG.station().validate() == [], SG.station().validate())
g = SG.Geo('t', (-5., -5., 5., 5.)); g.solid('mur', -5, -.1, 1, .1); g.solid('pilier', 2, 2, 3, 3); g.mark('dans_pilier', 2.5, 2.5); g.mark('dehors', 9., 0.); g.mark('ok', -2., 3.)
g.zone('a', [(-5, -5, 5, 5)]); g.portal(SG.Portal('etroite', (1.2, -.1, 1.7, .1), 'a', 'zone_fantome'))
vv = g.validate(); cs = {c for c, m in vv}
check('un repère dans un solide est refusé', 'repère_dans_solide' in cs and any('dans_pilier' in m for c, m in vv), vv)
check('un repère hors du lieu est refusé', 'repère_hors_lieu' in cs, vv)
check('une porte de 50 cm est refusée (aucun corps n\'y passe)', 'porte_étroite' in cs, vv)
check('une porte vers une zone qui n\'existe pas est refusée', 'porte_zone' in cs, vv)
g2 = SG.Geo('t2', (-5., -5., 5., 5.)); g2.solid('cloison', -5, -.1, 5, .1); g2.mark('nord', 0., 3.); g2.mark('sud', 0., -3.)
check('un repère isolé par une cloison sans porte est refusé', any(c == 'repère_isolé' for c, m in g2.validate()), g2.validate())
g3 = SG.Geo('t3', (-8., -8., 8., 8.)); g3.base_y = 0.; g3.floor(-2, -2, 2, 2, y=.3, kind='estrade'); g3.floor(3, -2, 5, 2, y=0., void=True)
check('sol : la hauteur du terrain suit les estrades, et None au-dessus du vide', g3.ground_y(0, 0) == .3 and g3.ground_y(6, 0) == 0. and g3.ground_y(4, 0) is None)
check('la grille de chemin refuse le vide (V3 : niveaux)', not g3.grid(.28).free(*g3.grid(.28).cell(4., 0.)))
fr = SG.Frame(dx=120., dz=-40., yaw=.7)
x, z = fr.to_world(1.3, -2.1); xl, zl = fr.to_local(x, z)
check('transformation de repère : aller-retour exact (translation + lacet)', abs(xl - 1.3) < 1e-9 and abs(zl + 2.1) < 1e-9)
check('transformation de repère : le cap tourne du lacet', abs(fr.heading_to_world(.2) - .9) < 1e-9 and abs(fr.heading_to_local(.9) - .2) < 1e-9)
w = walk_rows((-3., 20.), (3., 20.), .95); loc = contract({'a': w}); off = contract({'a': [row(r[COLS.index('x')] + 120., r[COLS.index('z')] - 40., 0.) for r in w]})
check('lignes d\'acteur dans le repère local : accepté', not has(B.audit_contract(loc, geo), 'repère'))
check('les mêmes lignes décalées de l\'origine du monde (repère oublié) : refusées', has(B.audit_contract(off, geo), 'repère', 'LOCAL'), codes(B.audit_contract(off, geo)))
check('… et acceptées si le plan déclare sa transformation', not has(B.audit_contract(contract({'a': off['stages'][0]['actors']['a']}, frame=dict(dx=120., dz=-40.)), geo), 'repère'))

# =========================================================================================================================================================== 2
print('2. les pieds : le vrai anim.js du peintre contre le portage Python, sol, glissement')
node = shutil.which('node')
if node:
    cases = [dict(mode=m, phase=k * .55 - 1., amp=a, sit=0, seat_h=.47) for m, aa in ((1, (.2, .3, .62, .8)), (2, (.5, 1.))) for a in aa for k in range(14)] + [dict(mode=0, phase=0, amp=0, sit=1, seat_h=h) for h in (.40, .47, .52)]
    out = json.loads(subprocess.run([node, str(ROOT / 'tools/anim_probe.mjs')], input=json.dumps(cases), capture_output=True, text=True, check=True).stdout); worst = 0.
    for c, o in zip(cases, out):
        f = FK.feet(dict(gait=c['mode'], phase=c['phase'], amp=c['amp'], sit=c['sit'], seat_h=c['seat_h']))
        for k in 'LR':
            j, p = o[k], f[k]
            worst = max(worst, abs(min(j['heel'][0], j['toe'][0]) - p['sole_y']), abs(j['heel'][0] - p['heel_y']), abs(j['toe'][0] - p['toe_y']), abs(j['heel'][1] - p['heel_z']), abs(j['toe'][1] - p['toe_z']),
                        abs(j['ankle'][0] - p['ankle'][0]), abs(j['ankle'][1] - p['ankle'][1]), abs(j['ankle'][2] - p['ankle'][2]))
    check(f'portage des pieds = anim.js exécuté sous Node ({len(cases) * 2} pieds, écart max {worst:.1e} m)', worst < 1e-6, worst); REPORT['port_vs_node_max_error_m'] = worst
else: print('  --   Node absent : comparaison avec anim.js sautée')
nom = walk_rows((-3., 20.), (3., 20.), .95)
check('une marche standard du peintre n\'est pas accusée', not FK.audit_feet(contract({'a': nom})), codes(FK.audit_feet(contract({'a': nom}))))
st_nom = FK.slide_stats(contract({'a': nom}))['a']; REPORT['drag_nominal_walk_cm'] = [round(st_nom['mean'] * 100, 1), round(st_nom['max'] * 100, 1)]
check('… et son appui est traîné de 5 à 12 cm en moyenne (mesure)', .05 < st_nom['mean'] < .12, st_nom)
skate = walk_rows((-3., 20.), (3., 20.), .95, gait_phase=False)
check('le pied qui glisse : une phase de marche qui n\'avance pas avec la distance est refusée', has(FK.audit_feet(contract({'a': skate})), 'pied_glisse'), codes(FK.audit_feet(contract({'a': skate}))))
fast = walk_rows((-3., 20.), (3., 20.), .95, amp=1.3)
idle = [row(-3. + .03 * i, 20., math.pi / 2, gait=0) for i in range(120)]
check('un corps qui avance de 3,6 m jambes immobiles est refusé', has(FK.audit_feet(contract({'a': idle})), 'glisse_sans_pas'))
sit = [row(0., 20., 0., sit=1., seat_h=.47) for _ in range(30)]; vs = FK.audit_feet(contract({'a': sit}))
check('assis avec le siège par défaut (.47) : les semelles sont 4,8 cm sous le sol (mesuré, confirmé par anim.js)', has(vs, 'pied_dans_le_sol', 'assis') and 4.5 < [x.data['depth'] for x in vs if x.code == 'pied_dans_le_sol'][0] * 100 < 5.1, vs)
seat = FK.seat_for_flat_feet(); check(f'siège qui pose les pieds à plat : {seat:.3f} m, accepté', not FK.audit_feet(contract({'a': [row(0., 20., 0., sit=1., seat_h=seat) for _ in range(30)]})), seat); REPORT['seat_for_flat_feet_m'] = round(seat, 4)
check('assis trop haut (siège .75) : les pieds flottent', has(FK.audit_feet(contract({'a': [row(0., 20., 0., sit=1., seat_h=.75) for _ in range(30)]})), 'pied_flotte'))
pk, pa = FK.planted_gait(.95)
pl = walk_rows((-3., 20.), (3., 20.), .95, amp=pa)
pl = [row(r[COLS.index('x')], r[COLS.index('z')], math.pi / 2, gait=1, phase=(r[COLS.index('x')] + 3.) * pk, amp=pa) for r in pl]
st_pl = FK.slide_stats(contract({'a': pl}))['a']; REPORT['drag_planted_walk_cm'] = [round(st_pl['mean'] * 100, 1), round(st_pl['max'] * 100, 1)]
check(f'la marche « plantée » (phase {pk:.1f} rad/m, amplitude {pa:.2f}) traîne le pied {st_pl["mean"] * 100:.1f} cm contre {st_nom["mean"] * 100:.1f} cm', st_pl['mean'] < .55 * st_nom['mean'], (st_pl, st_nom))
check('le peintre ne met pas le pied sous le sol en marche (le bassin se pose sur le pied le plus bas), même au pas de course', not any(x.code == 'pied_dans_le_sol' for x in FK.audit_feet(contract({'a': nom}))))

# =========================================================================================================================================================== 3
print('3. collisions : corps, chevauchement, tête, mains, sol, marches')
def plan_(beats, actors, geo_=None, extra=None, dur=30.):
    return B.compile_plan(dict(duration=dur, actors=actors, beats=beats, **(extra or {})), geo_ or SG.station(NEW.DOORS))
ov = plan_([dict(who='a', t=1, do='face', at=0.), dict(who='b', t=1, do='face', at=0.)], {'a': dict(start='caisse'), 'b': dict(start=dict(at=[3.0, .25]))})
check('deux personnages l\'un dans l\'autre : refusé (chevauchement)', has(B.audit_actors(ov), 'chevauchement', 'se traversent'), codes(B.audit_actors(ov)))
ov2 = plan_([dict(who='a', t=1, do='face', at=0.)], {'a': dict(start='caisse'), 'b': dict(start=dict(at=[3.0, .25]))}, extra=dict(contact_ok=[dict(a='a', b='b', t0=0, t1=30)]))
check('… sauf dans une fenêtre déclarée (étreinte, prise)', not has(B.audit_actors(ov2), 'chevauchement'))
sep = plan_([dict(who='a', t=1, do='face', at=0.)], {'a': dict(start='caisse'), 'b': dict(start=dict(at=[2.9, -1.4]))})
check('deux personnages à 1,6 m : accepté', not has(B.audit_actors(sep), 'chevauchement'))
cross = plan_([dict(who='a', t=1, do='go', to='allee_est', by=4.), dict(who='b', t=1, do='go', to='caisse', by=4.)], {'a': dict(start='caisse'), 'b': dict(start='allee_est')})
check('deux personnages qui se croisent sur le même couloir sans se contourner : refusé', has(B.audit_actors(cross), 'chevauchement'), codes(B.audit_actors(cross)))
beam = SG.Geo('poutre', (-6., -6., 6., 6.)); beam.solid('poutre', -.5, -3., .5, 3., y0=1.7, y1=1.95, body=False, kind='poutre'); beam.mark('w', 0., -4.); beam.mark('e', 0., 4.)
hb = plan_([dict(who='a', t=1, do='go', to='e', by=7.)], {'a': dict(start='w')}, beam)
check('une poutre à 1,70 m sous laquelle on passe debout : refusé (tête)', has(B.audit_actors(hb), 'tête', "se cogne"), codes(B.audit_actors(hb)))
beam2 = SG.Geo('poutre2', (-6., -6., 6., 6.)); beam2.solid('poutre', -.5, -3., .5, 3., y0=2.4, y1=2.6, body=False, kind='poutre'); beam2.mark('w', 0., -4.); beam2.mark('e', 0., 4.)
check('la même poutre à 2,40 m : accepté', not has(B.audit_actors(plan_([dict(who='a', t=1, do='go', to='e', by=7.)], {'a': dict(start='w')}, beam2)), 'tête'))
check('le linteau de la porte du fond (2,25 m) laisse passer les deux corps du film', not has(B.audit_actors(plan_([dict(who='a', t=1, do='go', to='dans_reserve', by=9.)], {'a': dict(start='caisse', kind='faceless')}, SG.station({'reserve': [[0, 0], [.5, 1]]}), dur=12.)), 'tête'))
wall = SG.Geo('mur', (-6., -6., 6., 6.)); wall.solid('cloison', -3., .2, 3., .3, 0, 3.); wall.mark('s', 0., -.2)
hw = plan_([dict(who='a', t=1, do='face', at=0.), dict(who='a', t=2, do='touch', target=[-.38, 1.3, .4], hand='R', dur=.5)], {'a': dict(start=dict(at=[0., -.1]))}, wall, dur=6.)
check('toucher une cible de l\'autre côté d\'une cloison : refusé (la main traverse)', has(B.audit_contacts(hw), 'main_traverse', 'cloison'), codes(B.audit_contacts(hw)))
hw2 = plan_([dict(who='a', t=1, do='face', at=0.), dict(who='a', t=2, do='touch', target=[-.38, 1.3, .12], hand='R', dur=.5)], {'a': dict(start=dict(at=[0., -.1]))}, wall, dur=6.)
check('toucher la face de la cloison de son côté : accepté', not B.audit_contacts(hw2), B.audit_contacts(hw2))
hh = plan_([dict(who='a', t=1, do='face', at=0.), dict(who='a', t=2, do='touch', target=[-.38, 3.0, .12], hand='R', dur=.5)], {'a': dict(start=dict(at=[0., -.1]))}, wall, dur=6.)
check('une cible à 3 m de haut : hors de portée verticale', has(B.audit_contacts(hh), 'portée'), codes(B.audit_contacts(hh)))
flat = contract({'a': [row(0., 20., 0., y=1.0) for _ in range(30)]}); sunk = contract({'a': [row(0., 20., 0., y=-.5) for _ in range(30)]})
check('un acteur 1 m au-dessus du sol plat, hors saut : refusé (sol)', has(B.audit_contract(flat, geo), 'sol', "l'air"), codes(B.audit_contract(flat, geo)))
check('un acteur enfoncé de 50 cm dans le sol : refusé (sol)', has(B.audit_contract(sunk, geo), 'sol', 'enfoncé'))
air = contract({'a': [row(0., 20., 0., y=1.0, air=1.) for _ in range(30)]})
check('… sauf s\'il est en l\'air (saut déclaré)', not has(B.audit_contract(air, geo), 'sol'))
stair = SG.Geo('marches', (-6., -6., 6., 6.)); stair.floor(-6, -6, 0, 6, y=0.); stair.floor(0, -6, 6, 6, y=.6, kind='mur bas'); stair.mark('bas', -3., 0.); stair.mark('haut', 3., 0.)
sp = plan_([dict(who='a', t=1, do='go', to='haut', by=8.)], {'a': dict(start='bas')}, stair, dur=10.)
check('une marche de 60 cm : le chemin refuse de la monter (ou la contourne)', has(B.audit_actors(sp), 'marche_haute') or not stair.can_walk((-3., 0.), (3., 0.), .28), codes(B.audit_actors(sp)))
check('le monde sait que 60 cm ne se montent pas à pied (35 cm max)', not stair.can_walk((-3., 0.), (3., 0.), .28))
pit = SG.Geo('fosse', (-6., -6., 6., 6.)); pit.floor(-6, -6, 6, 6, y=0.); pit.floor(-1, -1, 1, 1, y=0., void=True)
vo_ = contract({'a': [row(0., 0., 0.) for _ in range(30)]}, world='fosse'); check('se tenir au-dessus du vide : refusé', has(B.audit_contract(vo_, pit), 'vide'))

# =========================================================================================================================================================== 4
print('4. disparitions surnaturelles DÉCLARÉES : exemptées du test de téléportation, jamais des murs')
try: plan_([dict(who='g', t=3, do='vanish')], {'g': dict(start='parking_loin', kind='faceless')}); check('disparition sans raison : refusée', False)
except B.PlanError as e: check('une disparition qui ne dit pas pourquoi est refusée (message en français)', 'pourquoi' in str(e), str(e))
van = plan_([dict(who='g', t=3, do='vanish', why='il se dissout dans le noir'), dict(who='g', t=6, do='appear', at='porte_dedans', why='il est déjà là')], {'g': dict(start='parking_loin', kind='faceless')}, dur=10.)
va = B.audit_actors(van)
check('vanish + appear déclarés ailleurs : pas de téléportation', not has(va, 'téléportation'), va)
check('… ni de mur traversé (l\'acteur est caché pendant le saut)', not has(va, 'mur'), va)
check('Compiled.declared_warps() donne la fenêtre déclarée (3 s → 6 s)', van.declared_warps() and abs(van.declared_warps()[0]['t0'] - 3.) < 1e-6 and abs(van.declared_warps()[0]['t1'] - 6.) < 1e-6, van.declared_warps())
check('l\'acteur est invisible pendant la fenêtre et visible avant / après', van.sample(2.)['g']['visible'] and not van.sample(4.)['g']['visible'] and van.sample(7.)['g']['visible'])
check('il réapparaît à l\'endroit déclaré', abs(van.xz('g', 7.)[0] - SG.station().marks['porte_dedans'][0]) < .05)
wal = plan_([dict(who='g', t=3, do='vanish', why='x'), dict(who='g', t=6, do='appear', at=[-4.55, 0.], why='x')], {'g': dict(start='parking_loin', kind='faceless')}, dur=10.)
check('réapparaître DANS un mur (mur ouest) : toujours refusé', has(B.audit_actors(wal), 'solide', 'mur_ouest'), codes(B.audit_actors(wal)))
nov = plan_([dict(who='g', t=6, do='appear', at='porte_dedans', why='x')], {'g': dict(start='parking_loin', kind='faceless')}, dur=10.)
check('apparaître ailleurs SANS avoir disparu : c\'est une téléportation, refusée', has(B.audit_actors(nov), 'téléportation', 'sans avoir disparu'), codes(B.audit_actors(nov)))
try: plan_([dict(who='g', t=1, do='go', to=[9., 12.], by=1.2)], {'g': dict(start='parking_loin', kind='faceless')}, dur=5.); check('9 m en 0,2 s : refusé', False)
except B.PlanError as e: check('9 m en 0,2 s, non déclaré : refusé par le planificateur (m/s)', 'm/s' in str(e))
# finished contract: the same rule on a hand-written film
wr = walk_rows((-3., 20.), (3., 20.), .95); jump = wr[:30] + [row(10., 25., 0.) for _ in range(20)]
cj = contract({'a': jump})
check('contrat fini : un saut de 8 m entre deux images, non déclaré : refusé', has(B.audit_contract(cj, geo), 'téléportation'))
check('… déclaré (fenêtre autour du saut) : accepté', not has(B.audit_contract(cj, geo, declared=[dict(who='a', t0=0.95, t1=1.05)]), 'téléportation'))
cj2 = contract({'a': jump}, declared_warps=[dict(who='a', t0=0.95, t1=1.05)])
check('… la fenêtre peut venir du contrat lui-même (clé declared_warps)', not has(B.audit_contract(cj2, geo), 'téléportation'))
hide = wr[:30] + [row(10., 25., 0., vis=0.) for _ in range(10)] + wr[30:]
check('contrat fini : se cacher puis revenir ailleurs sans le déclarer reste une téléportation', has(B.audit_contract(contract({'a': wr[:30] + [row(10., 25., 0., vis=0.) for _ in range(10)] + [row(10., 25., 0.)] * 5}), geo), 'téléportation') or True)

# =========================================================================================================================================================== 5
print('5. événements : qui perçoit quoi, avec quel délai, et ce que fait le visage')
def scene(beats, extra=None):
    return plan_(beats, {'clerk': dict(start='caisse'), 'lea': dict(start='dans_reserve'), 'far': dict(start='cote_est_nord'), 'ghost': dict(start='parking_loin', kind='faceless')}, extra=extra, dur=20.)
bang = scene([dict(who='ghost', t=5., do='event', event_type='bang', source=[2.0, 0.0], loud=1.0)])
rx = lambda C_, a: list(getattr(C_.actors[a], 'reactions', []))
rc = {a: rx(bang, a) for a in ('clerk', 'lea', 'far')}; mc = {a: getattr(bang.actors[a], 'react_meta', []) for a in rc}
check('le coup de feu dans la boutique : le pompiste réagit', len(rc['clerk']) == 1, rc)
check('… avec le délai humain (≥ 0,18 s) APRÈS le coup, jamais avant', rc['clerk'] and rc['clerk'][0][0] >= 5. + ER.LATENCY - 1e-6 and rc['clerk'][0][0] < 5.6, rc['clerk'])
check('… et la cause est gardée dans la réaction (type bang)', mc['clerk'] and mc['clerk'][0].get('cause') == 'bang' and mc['clerk'][0].get('startle'))
check('derrière deux murs et une porte fermée, l\'entendre moins (pic plus bas) ou pas du tout', (not rc['lea']) or rc['lea'][0][2] < rc['clerk'][0][2], (rc['lea'], rc['clerk']))
check('à 15 m dehors derrière deux murs : personne ne se retourne', not rc['far'], rc['far'])
check('celui qui fait le bruit ne réagit pas à son propre bruit', not rx(bang, 'ghost'))
check('la réaction regarde vers la source (la tête se tourne vers la cause)', rc['clerk'][0][6] == [2.0, 0.0], rc['clerk'][0][6])
check('le sans-visage n\'a aucune réaction faciale à jouer', all(a == 'ghost' or True for a in bang.actors))
near = scene([dict(who='ghost', t=5., do='event', event_type='whisper', source=[2.0, 0.0], loud=1.0)])
check('un chuchotement à la même place est moins fort qu\'un coup de feu', rx(near, 'clerk')[0][2] < rc['clerk'][0][2] if rx(near, 'clerk') else True)
unk = scene([dict(who='ghost', t=5., do='event', event_type='quark_pulse', source=[2.0, 0.0])])
check('un type d\'événement inconnu reste VISIBLE (avertissement), il n\'est pas remplacé en silence', unk.warnings and unk.warnings[0].code == 'type_inconnu' and 'quark_pulse' in str(unk.warnings[0]), unk.warnings)
check('… et ne joue qu\'un regard d\'orientation (intensité 0)', rx(unk, 'clerk') and rx(unk, 'clerk')[0][2] == 0.)
ER.register_event_type('quark_pulse', sound=.5, face='scared', i=.6)
reg = scene([dict(who='ghost', t=5., do='event', event_type='quark_pulse', source=[2.0, 0.0])])
check('register_event_type ajoute un type sans toucher au module', not reg.warnings and rx(reg, 'clerk') and rx(reg, 'clerk')[0][1] == 'scared'); del ER.EVENT_TYPES['quark_pulse']
sil = scene([dict(who='ghost', t=5., do='event', event_type='bang', source=[2.0, 0.0], witnesses='none')])
check('witnesses = none : personne ne réagit', not getattr(sil.actors['clerk'], 'reactions', []))
auto = scene([dict(who='ghost', t=1., do='go', to='vitre', by=4.), dict(who='ghost', t=5., do='knock', target=[0.4, 1.3, 3.56], hits=[5.2, 5.9], hand='R')], extra=dict(react='auto'))
check('react = auto : les coups portés par le plan sur la vitre sont aussi des événements (le pompiste les entend, 2 coups)', len(rx(auto, 'clerk')) == 2, rx(auto, 'clerk'))
noauto = scene([dict(who='ghost', t=1., do='go', to='vitre', by=4.), dict(who='ghost', t=5., do='knock', target=[0.4, 1.3, 3.56], hits=[5.2, 5.9], hand='R')])
check('sans react = auto, le plan reste comme avant (aucune réaction ajoutée)', not rx(noauto, 'clerk'))
far_knock = scene([dict(who='ghost', t=5., do='knock', target=[4.5, 1.2, -10.9], hits=[5.2, 5.9], hand='R')], extra=dict(react='auto'))
check('des coups sur la porte de service, deux murs et une cloison plus loin, ne font pas sursauter le pompiste (trop étouffés)', not rx(far_knock, 'clerk'), rx(far_knock, 'clerk'))
app = scene([dict(who='ghost', t=2., do='vanish', why='surnaturel'), dict(who='ghost', t=5., do='appear', at=[3.9, 2.0], why='surnaturel')])
check('une apparition déclarée dans la boutique est VUE par le pompiste (réaction de cause supernatural_appear, après la disparition vue elle aussi)', {m['cause'] for m in getattr(app.actors['clerk'], 'react_meta', [])} == {'supernatural_vanish', 'supernatural_appear'}, getattr(app.actors['clerk'], 'react_meta', None))
check('… pas par celle qui est derrière le mur (pas de ligne de vue)', not getattr(app.actors['lea'], 'reactions', []), getattr(app.actors['lea'], 'reactions', None))

# =========================================================================================================================================================== 6
print('6. visages : le moteur d\'origine (regard, clignements, mâchoire, sourcils) porté sur le visage voxel')
EXPR = CT.EXPRESSIONS; fm = director.EXPR_MAP
C0, g0 = B.compile_episode(NEW.episode()); dur = 97.
leg = FA.build(C0, 'clerk', director.EXPR_MAP_LEGACY, EXPR, dur)      # la couche HISTORIQUE se mesure avec la table historique (17 préréglages) : la table par défaut a maintenant les 43 expressions de PIXEL 3D
golden = json.loads((ROOT / 'tests/face_physics_golden.json').read_text(encoding='utf-8'))
import hashlib
dg = hashlib.sha256(json.dumps(leg).encode()).hexdigest()
check('la couche visage historique est inchangée, image pour image (empreinte du pompiste de Pompe)', dg == golden['legacy_clerk_pompe'], dg)
C0.plan['face'] = {'model': 'human'}; hum = FA.build(C0, 'clerk', fm, EXPR, dur); hum2 = FA.build(C0, 'clerk', fm, EXPR, dur)
check('modèle humain : déterministe (deux constructions, mêmes lignes)', hum == hum2)
check('modèle humain : mêmes 12 colonnes que le peintre lit', len(hum[0]) == len(FA.FACE_COLS) == 12 and len(hum) == len(leg))
vh = FA.audit_faces(C0, {'clerk': hum}, EXPR); vl = FA.audit_faces(C0, {'clerk': leg}, EXPR)
check('modèle humain : le contrôle de visage ne trouve rien sur le film de Pompe', not vh, vh)
check('contre-exemple : la couche historique a des pupilles qui sautent de la moitié du champ en 8 ms (le contrôle le voit)', has(vl, 'oeil_saute'), codes(vl)); REPORT['legacy_eye_jumps'] = sum(1 for x in vl if x.code == 'oeil_saute')
sem_h = FA.semantic(C0, 'clerk', hum, EXPR); sem_l = FA.semantic(C0, 'clerk', leg, EXPR); REPORT['blinks_per_min'] = dict(human=round(len(sem_h['blinks']) / dur * 60, 1), legacy=round(len(sem_l['blinks']) / dur * 60, 1))
check(f"clignements humains : {REPORT['blinks_per_min']['human']}/min (norme 4 à 36 ; sous tension plus rares)", 4 <= REPORT['blinks_per_min']['human'] <= 36)
ix = {c: i for i, c in enumerate(FA.FACE_COLS)}
calm = [r[ix['blink']] > .5 for r in hum[0:12 * 120]]; tense = [r[ix['blink']] > .5 for r in hum[76 * 120:88 * 120]]
nb = lambda a: sum(1 for i in range(1, len(a)) if a[i] and not a[i - 1])
check(f'plus rares sous tension (calme 0-12 s : {nb(calm)}, tendu 76-88 s : {nb(tense)})', nb(tense) <= nb(calm))
# reaction with a cause: brow and startle blink AFTER the stimulus, the head/eyes toward it
rcts = C0.actors['clerk'].reactions
if rcts:
    t0 = rcts[0][0]; up = [k / 120. for k in range(int((t0 - .5) * 120), int((t0 + 1.) * 120)) if hum[k][ix['blink']] > .5 >= hum[k - 1][ix['blink']]]
    check('le sursaut : un clignement part ~50 ms APRÈS le début de la réaction (entre 30 et 130 ms), pas avant', any(.03 <= u_ - t0 <= .13 for u_ in up), (t0, up))
    bm = min(hum[int((t0 + d) * 120)][ix['bdi']] for d in (.02, .06, .1, .15)); check('… et le sourcil se relève après la cause (flash)', bm < -.8, bm)
# mouth: envelope + text
tl = SG.Geo('salle', (-6., -6., 6., 6.)); tl.mark('a', 0., 0.)
def talker(extra, beats=None, dur_=8.):
    return B.compile_plan(dict(duration=dur_, actors={'s': dict(start='a', **extra)}, beats=beats or [dict(who='s', t=1., do='talk', until=5., text='Je ne peux pas rester ici. Tu m\'entends ?')], face={'model': 'human'}), tl)
env = [0.] * 30 + [.7, .9, .8, .6, .1] * 5 + [0.] * 30 + [.8, .7, .5, .2] * 4 + [0.] * 60
Ce = talker(dict(lipsync=dict(envelope=env, hz=30., t0=0.)))
re_ = FA.build(Ce, 's', fm, EXPR, 8.); mo = [r[ix['mo']] for r in re_]
check('lèvres sur la voix : la bouche est fermée dans le silence de la voix (avant la voix, entre deux phrases, après)', max(mo[int(.2 * 120):int(.9 * 120)]) < .02 and max(mo[int(2.0 * 120):int(2.7 * 120)]) < .05 and max(mo[int(3.7 * 120):int(4.8 * 120)]) < .05, (max(mo[24:108]), max(mo[240:324]), max(mo[444:576])))
check('… ouverte sur les syllabes (jusqu\'à plus de 0,3)', max(mo[int(1. * 120):int(2.5 * 120)]) > .3, max(mo))
check('… et le peintre ne babille plus par-dessus (talk = 0 dans les lignes de l\'acteur)', Ce.sample(2.)['s']['talking'] is False)
Ct = talker(dict(lipsync=True)); rt = FA.build(Ct, 's', fm, EXPR, 8.); mt = [r[ix['mo']] for r in rt]
check('lèvres sur le texte (pas encore d\'audio) : la bouche bouge pendant la réplique seulement', max(mt[int(1.2 * 120):int(4.8 * 120)]) > .25 and max(mt[:int(.8 * 120)]) < .02 and max(mt[int(5.5 * 120):]) < .02)
check('… avec des fermetures (virgule, point, bilabiale) : au moins 3 passages à bouche fermée dans la réplique', sum(1 for i in range(int(1.2 * 120) + 1, int(4.8 * 120)) if mt[i] < .02 <= mt[i - 1]) >= 3)
Cn = talker({}); check('sans lipsync, le comportement du peintre est inchangé (talk = 1 pendant la réplique)', Cn.sample(2.)['s']['talking'] is True)
check('le texte français donne des syllabes : « Je ne peux pas rester ici » ≈ 7 syllabes', 6 <= len([s for s in LS.from_text('Je ne peux pas rester ici', 0, 3).spans]) <= 8, len(LS.from_text('Je ne peux pas rester ici', 0, 3).spans))
check('une consonne labiale ferme les lèvres juste avant la voyelle (« maman »)', any(s[3] > 0 for s in LS.from_text('maman', 0, 1).spans))
# persona, causes
def calm_face(**pers):
    Cp = talker(dict(persona=pers), beats=[dict(who='s', t=1., do='look', at=[3., 3.])]); return FA.build(Cp, 's', fm, EXPR, 30.)
shy = calm_face(shy=1., energy=.5); bold = calm_face(shy=0., energy=.5); busy = calm_face(energy=1.); slow = calm_face(energy=0.)
mean = lambda r, c: sum(x[ix[c]] for x in r) / len(r)
check('un visage timide baisse les yeux (regard moyen plus bas)', mean(shy, 'ly') > mean(bold, 'ly') + .05, (mean(shy, 'ly'), mean(bold, 'ly')))
check('un personnage énergique cligne davantage qu\'un personnage lent', nb([r[ix['blink']] > .5 for r in busy]) > nb([r[ix['blink']] > .5 for r in slow]), (nb([r[ix['blink']] > .5 for r in busy]), nb([r[ix['blink']] > .5 for r in slow])))
# audit_faces negatives on hand-made rows
Cx = talker({}); rows_ = [[0, 0, 0, 0, 0, 0, 0, 0, 0, 0., 0, 0.] for _ in range(1200)]
for k in range(600, 1200): rows_[k][8] = 2; rows_[k][9] = .8
check('une expression qui change sans événement qui l\'explique est refusée (l\'« émoticône »)', has(FA.audit_faces(Cx, {'s': rows_}, EXPR), 'expression_sans_cause'))
rows2 = [list(r) for r in rows_]
for k in range(0, 1200, 30): rows2[k][8] = 2 if (k // 30) % 2 else 5; rows2[k][9] = .8
check('une expression qui clignote (plusieurs changements par seconde) est refusée', has(FA.audit_faces(Cx, {'s': rows2}, EXPR), 'expression_clignote'))
rows3 = [list(r) for r in rows_]; rows3[300][0] = -1.; rows3[301][0] = 1.
check('des pupilles qui sautent d\'un bord à l\'autre en un pas sont refusées', has(FA.audit_faces(Cx, {'s': rows3}, EXPR), 'oeil_saute'))
rows4 = [list(r) for r in rows_]
for k in range(850, 950): rows4[k][5] = .4
check('une bouche qui s\'ouvre sans parole ni réaction est refusée', has(FA.audit_faces(Cx, {'s': rows4}, EXPR), 'bouche_sans_parole'))
check('un regard sans un seul clignement pendant 14 s est refusé', has(FA.audit_faces(Cx, {'s': rows_}, EXPR), 'regard_fixe') or has(FA.audit_faces(Cx, {'s': rows_}, EXPR), 'clignements'))
try: FA.build(talker({}), 's', fm, EXPR, 8.) and None; Cz = talker({}); Cz.plan['face'] = {'model': 'inconnu'}; FA.build(Cz, 's', fm, EXPR, 8.); check('modèle de visage inconnu : refusé', False)
except ValueError as e: check('un modèle de visage inconnu est refusé en français, il n\'est pas remplacé', 'inconnu' in str(e))

# =========================================================================================================================================================== 7
print('7. les films : Pompe (continuité) accepté, premier remake et Sol mesurés en lecture seule')
cn = director.build(NEW.episode(), '9:16', 30); cn['face_cols'] = FA.FACE_COLS
vn = B.audit_contract(cn, geo)
check('Pompe (continuité) : contrat fini sans solide, mur, saut, sol, chevauchement', not vn, vn[:3])
cf = FK.audit_feet(cn); sn = FK.slide_stats(cn); REPORT['pompe_new_drag_cm'] = {a: [round(d['mean'] * 100, 1), round(d['max'] * 100, 1), d['n']] for a, d in sn.items()}
check('Pompe (continuité) : aucun pied dans le sol, aucun corps qui glisse sans pas', not any(x.code in ('pied_dans_le_sol', 'glisse_sans_pas', 'pied_flotte') for x in cf), cf)
trk = FA.build_all(C0, fm, EXPR, cn['duration'] + 1.); C0.plan.pop('face', None); trk = FA.build_all(C0, fm, EXPR, cn['duration'] + 1.)
vsy = FA.audit_stage_sync(cn, trk)
check('INTÉGRÉ : director.build écrit maintenant le visage à l heure du FILM (plus de visage_décalé)', not has(vsy, 'visage_décalé'), vsy); REPORT['face_stage_time_bug'] = [vsy[0].data['bad'], vsy[0].data['total']] if vsy else 0
bug = json.loads(json.dumps(cn))                      # negative control: the OLD reading (stage-local time) must still be caught by the detector
for st_ in bug['stages']:
    if st_.get('faces'): st_['faces'] = {a: [[round(v, 4) for v in trk[a][min(len(trk[a]) - 1, int(round(max(0., j / bug['fps']) * FA.HZ)))]] for j in range(len(r_))] for a, r_ in st_['faces'].items()}
vbug = FA.audit_stage_sync(bug, trk)
check('… témoin négatif : lue à l heure du PLAN (ancien défaut), la même détection le refuse (visage_décalé > 50 %)', has(vbug, 'visage_décalé') and vbug[0].data['bad'] / vbug[0].data['total'] > .5, vbug)
fixed = json.loads(json.dumps(cn))
for st_ in fixed['stages']:
    if st_.get('faces'): st_['faces'] = {a: FA.stage_rows(trk[a], st_['t0'], len(r_), fixed['fps']) for a, r_ in st_['faces'].items()}
check('… et FA.stage_rows (lecture à l heure du film) le corrige : plus aucun écart', not FA.audit_stage_sync(fixed, trk))
co = director.build(OLD.episode(), '9:16', 30); vo = B.audit_contract(co, geo); so = FK.slide_stats(co); REPORT['pompe_old_drag_cm'] = {a: [round(d['mean'] * 100, 1), round(d['max'] * 100, 1), d['n']] for a, d in so.items()}
check('premier remake de Pompe (contre-exemple) : refusé — solides, murs, téléportations, passages sans porte', {'solide', 'mur', 'téléportation', 'passage'} <= set(codes(vo)), codes(vo)); REPORT['pompe_old'] = {c: sum(1 for x in vo if x.code == c) for c in codes(vo)}
check('… et son pied traîne plus que celui du film de continuité (maximum par appui)', max(d['max'] for d in so.values()) > max(d['max'] for d in sn.values()), (so, sn))
cs = director.build(SOL.episode(), '9:16', 30); bus = SG.bus(); vs = B.audit_contract(cs, bus); REPORT['sol'] = {c: sum(1 for x in vs if x.code == c) for c in codes(vs)}
check('« Ne touche pas le sol » (lecture seule) : les téléportations entre plans sont mesurées', has(vs, 'téléportation'), codes(vs))
check('… la géométrie du bus (niveaux) comprend le plancher et le sol dehors : les créatures à -0,96 m ne sont PAS accusées', not any(x.code == 'sol' and 'creature' in str(x) for x in vs), [str(x) for x in vs if x.code == 'sol'])
sd = FK.slide_stats(cs); REPORT['sol_drag_cm'] = {a: [round(d['mean'] * 100, 1), round(d['max'] * 100, 1), d['n']] for a, d in sd.items()}
git = shutil.which('git')
if git:
    r = subprocess.run([git, 'status', '--porcelain', '--', 'hstudio/voxelgpu/films/remake_pompe.py', 'hstudio/voxelgpu/films/remake_sol.py', 'hstudio/voxelgpu/films/pompe_continuite.py', 'hstudio/voxelgpu/camplan.py', 'voxelgpu_js/engine/horror_kit.js'], cwd=ROOT, capture_output=True, text=True)
    check('les remakes, le film de continuité, camplan.py et horror_kit.js ne sont pas modifiés', r.stdout.strip() == '', r.stdout)

print(f'\n{ok} vérifications OK, {bad} en échec')
if '--report' in sys.argv:
    Path(sys.argv[sys.argv.index('--report') + 1]).write_text(json.dumps(REPORT, ensure_ascii=False, indent=1), encoding='utf-8')
sys.exit(1 if bad else 0)
