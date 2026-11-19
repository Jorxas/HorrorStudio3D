"""Quick checks of the V3 capabilities (seconds, no rendering, no API): planner, audit, composer, vertical verbs,
extensions. Exit 1 on any failure.

  python tools/check_v3.py"""
import os, sys, math, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
FAIL = []
def check(name, ok, detail=''):
    print(f"{'OK   ' if ok else 'ÉCHEC'} {name}" + (f'  ({detail})' if detail and not ok else '')); ok or FAIL.append(name)

def planner_checks():
    from hstudio.capabilities import planner, registry
    caps = registry.build()
    st = lambda rep, key: next((n['status'] for n in rep['needs'] if f"{n['kind']}:{n['name']}" == key), None)
    rep = planner.plan("Léa court sur le toit d'un immeuble pendant une tempête. Derrière elle, un dragon gigantesque traverse les nuages. "
                       "Un éclair frappe la tour voisine, qui commence à s'effondrer. Léa saute vers un hélicoptère pendant que la caméra la suit dans le vide.", caps=caps)
    for key, want in (('action:jump', 'native'), ('effect:collapse', 'native'), ('effect:lightning_bolt', 'native'), ('effect:mover', 'native'),
                      ('element:building', 'composed'), ('feature:levels', 'composed'), ('camera_move:follow', 'native'), ('prop:helicopter', 'native')):
        check(f'plan (exemple du cahier des charges) : {key} {want}', st(rep, key) == want, st(rep, key))
    check('plan : « éclair frappe » n\'est pas une bagarre', st(rep, 'action:fight') is None)
    rep = planner.plan('Tom nage vers la ville sous-marine. Un requin géant surgit et une explosion secoue le sous-marin.', caps=caps)
    for key, want in (('action:swim', 'missing'), ('place:underwater', 'missing'), ('creature:shark', 'missing'), ('effect:explosion', 'partial'), ('feature:scale', 'native')):
        check(f'plan (scène absente) : {key} {want}', st(rep, key) == want, st(rep, key))
    check('plan : une demande d\'extension par manque', {r['id'] for r in rep['requests'] if r['need'] == 'manquant'} >= {'action_swim', 'place_underwater', 'creature_shark'})
    rep = planner.plan('Léa saute sur le lit.', engine='console', caps=caps)
    check('plan CONSOLE : jump disponible', st(rep, 'action:jump') == 'native')

def audit_checks():
    from hstudio.capabilities import audit
    from hstudio import demos
    for d in ('demo7_toits', 'demo8_ravin', 'demo9_tempete', 'demo10_console_saut'):
        sc = demos.load(d); rep = audit.audit_episode(sc['episode'], sc.get('style', 'pixel3d'))
        check(f'audit {d} : aucun manque', rep['ok'], '; '.join(f"{g['kind']}:{g['name']}" for g in rep['gaps']))
    ep = {'shots': [{'lines': [0, 0], 'actions': [{'who': 'lea', 'do': 'swim'}], 'objects': [{'type': 'tornado'}]}], 'sets': {'x': {'type': 'room', 'props': [{'type': 'submarine', 'at': [0, 0]}]}}}
    rep = audit.audit_episode(ep, 'pixel3d'); got = {(g['kind'], g['name']) for g in rep['gaps']}
    check('audit : verbe, effet et objet inconnus signalés', {('action', 'swim'), ('effect', 'tornado'), ('prop', 'submarine')} <= got, str(got))

def compose_checks():
    from hstudio.engines.pixel3d.sets import make_set
    from hstudio.engines.pixel3d.stage import SetWorld
    sc = json.load(open(os.path.join(ROOT, 'examples', 'demos', 'demo8_ravin.json'), encoding='utf-8'))
    st = make_set('ravin', sc['episode']['sets']['ravin']); w = SetWorld(st)
    check('lieu composé : niveaux', w.has_levels and abs(w.ground_y(0, 0) - 0.) < 1e-6 and abs(w.ground_y(0, 10) + .7) < 1e-6 and abs(w.ground_y(0, 14) - .9) < 1e-6)
    check('lieu composé : vide entre les falaises', w.ground_y(0, 6.8) is None)
    check('lieu composé : repères des éléments', st.anchors.get('falaise_a.N') is not None and st.anchors.get('corniche') is not None)
    check('lieu composé : le sol est bas', abs(float(getattr(st.base, 'floor_y', 0.)) + 30) < 1e-6)

def motion_checks():
    from hstudio.engines.pixel3d.sets import make_set
    from hstudio.engines.pixel3d.stage import SetWorld
    from hstudio.acting.timeline import ShotActing
    sc = json.load(open(os.path.join(ROOT, 'examples', 'demos', 'demo8_ravin.json'), encoding='utf-8'))
    w = SetWorld(make_set('ravin', sc['episode']['sets']['ravin']))
    shot = {'actors': [{'id': 'lea', 'at': [-1, -1.6], 'facing': '+z'}], 'actions': [{'who': 'lea', 'do': 'jump', 'to': [-1, 9.6]}]}
    sa = ShotActing(shot, w, {}, [], 6.); tr = sa.tracks['lea']; seg = tr.airs[0]
    apex = max(seg['y'](seg['t0'] + k * (seg['t1'] - seg['t0']) / 40) for k in range(41))
    check('saut : trajectoire au-dessus du vide', .2 < apex < 1.2, f'apex {apex:.2f}')
    x, z = sa.position(tr, 6.); check('saut : atterrit au bon endroit, au bon niveau', math.hypot(x + 1, z - 9.6) < .05 and abs(sa.level(tr, 6.) + .7) < 1e-6, f'{x:.2f},{z:.2f} y {sa.level(tr, 6.):.2f}')
    mid = (seg['t0'] + seg['t1']) / 2; s = sa.sample(mid)['lea']
    check('saut : pose en l\'air pendant le vol', s['rig'].get('air', 0) > .9 and s['y'] > 0)
    shot = {'actors': [{'id': 'lea', 'at': [-1, 9.6], 'facing': '+z'}], 'actions': [{'who': 'lea', 'do': 'climb', 'to': 'corniche'}]}
    sa = ShotActing(shot, w, {}, [], 8.); tr = sa.tracks['lea']
    check('escalade : finit sur la corniche', abs(sa.level(tr, 8.) - .9) < 1e-6 and tr.reaches, f'y {sa.level(tr, 8.):.2f}')
    shot = {'actors': [{'id': 'lea', 'at': [-1, -1.6], 'facing': '+z'}], 'actions': [{'who': 'lea', 'do': 'walk_to', 'to': [-1, 9.6]}]}
    sa = ShotActing(shot, w, {}, [], 12.); x, z = sa.position(sa.tracks['lea'], 12.)
    check('marche : ne traverse pas le vide', z < 5.2, f'z {z:.2f}')

def extension_checks():
    from hstudio.capabilities import extensions
    extensions.ensure_loaded()
    check('extension hélicoptère : stable et chargée', 'helicopter' in extensions.LOADED, extensions.PROBLEMS.get('helicopter', ''))
    from hstudio.engines.pixel3d import world as W
    check('extension hélicoptère : objet dessiné', len(W.PROPS['helicopter']({'_t': .5}, None)) > 20)

if __name__ == '__main__':
    for fn in (planner_checks, audit_checks, compose_checks, motion_checks, extension_checks): fn()
    print(f"\n{'Tout est OK' if not FAIL else str(len(FAIL)) + ' échec(s)'}"); sys.exit(1 if FAIL else 0)
