"""Tests du lieu `theatre_bal` et de la lumière de scène `stage_light` (PS1 : engines/pixel3d/theatre.py, stage_light.py ; VOXEL : voxelgpu/b_theatre.py,
voxelgpu_js/engine/theatre_kit.js).   python tools/check_theatre.py [--gpu]

Sans GPU : opt-in (aucun autre lieu n'a la méthode, aucun module chargé sans le lieu, contrat inchangé, le réalisateur IA ne connaît pas les clés),
déterminisme (enregistrement de lumière, image PS1, contrat VOXEL), clés (lavis, clés dans le temps, coupe, fondu depuis le plan précédent, poursuite
qui suit l'acteur, état du monde `state_track`, plateau tournant), géométrie (dimensions, niveaux praticables, ancres, éléments), et que chaque clé
CHANGE réellement l'image PS1. `--gpu` ajoute : deux rendus VOXEL identiques octet pour octet, et le rideau de lumière qui change l'image.
Code de sortie 0 seulement si tout passe ; chaque ligne dit ce qui a été mesuré."""
import copy, hashlib, importlib.util, json, math, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import numpy as np

RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail)); print(('OK    ' if ok else 'ECHEC ') + name + (f' : {detail}' if detail else ''), flush=True)


def demo():
    spec = importlib.util.spec_from_file_location('theatre_demo', ROOT / 'examples' / 'theatre' / 'theatre_demo.py'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def h(a): return hashlib.sha1(np.ascontiguousarray(a).tobytes()).hexdigest()[:16]


# ------------------------------------------------------------------------------------------------- opt-in
def optin_tests():
    code = ("import sys; sys.path.insert(0, r'%s'); import json, numpy as np\n"
            "from hstudio.pipeline import make_engine\n"
            "d = r'%s'; ep = json.load(open(d + '/episode.json', encoding='utf-8')); ln = json.load(open(d + '/lines.json', encoding='utf-8'))\n"
            "e = make_engine('pixel3d', ep, ln, np.zeros(10), ln[-1]['end'] + 1.5, '16:9'); e.frame(9.5)\n"
            "print(json.dumps([m for m in ('hstudio.engines.pixel3d.theatre', 'hstudio.engines.pixel3d.stage_light', 'hstudio.voxelgpu.b_theatre') if m in sys.modules]))") % (ROOT, ROOT / 'tests' / 'fixtures' / 'partie4')
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, cwd=str(ROOT))
    try: loaded = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception: loaded = ['?', r.stderr[-300:]]
    check('opt-in : un épisode sans théâtre ne charge ni theatre.py, ni stage_light.py, ni b_theatre.py', loaded == [], str(loaded))
    from hstudio.engines.pixel3d import sets as S, places as PL
    others = [n for n in list(PL.PLACES) + ['etage_zero', 'apartment', 'pompe_station', 'room'] if hasattr(S.make_set(n, {'type': n} if n != 'room' else {'type': 'room', 'rooms': [{'size': [4, 5]}]}), 'stage_frame')]
    check('opt-in : aucun autre lieu n\'a la lumière de scène (stage_frame)', not others, f'{len(PL.PLACES) + 4} lieux testés' if not others else str(others))
    from hstudio.voxelgpu import from_ps1
    ep = {'style': 'pixel3d', 'default_set': 's', 'sets': {'s': {'type': 'apartment'}}, 'cast': {'a': {}}, 'shots': [{'lines': [0, 0], 'pre': 0., 'set': 's', 'tracks': {'a': [{'t': 0, 'p': [0, 0, 12.5], 'yaw': 3.14}]},
          'camera': {'rig': 'path', 'keys': [{'t': 0, 'pos': [0, 1.6, 10.5], 'look': [0, 1.4, 12.5], 'fov': 50}]}}]}
    c = from_ps1.build(ep, [{'start': 0., 'end': 1., 'text': ''}], 1., '16:9', 24, lambda *_: None)
    bad = [k for k in ('spot_pool', 'point_pool') if k in c] + [s['id'] for s in c['stages'] if 'theatre' in s] + [p.get('type') for s in c['stages'] for p in s.get('props') or [] if p.get('type') == 'btheatre']
    check('opt-in : le contrat VOXEL d\'un autre lieu n\'a ni `theatre`, ni `spot_pool`/`point_pool`, ni accessoire `btheatre`', not bad, str(bad))
    js = (ROOT / 'voxelgpu_js/engine/main_unified.js').read_text(encoding='utf-8')
    check('peintre : 4 lumières et 2 projecteurs sans la clé du contrat (Math.max(4, … | 0), Math.max(2, … | 0))', 'Math.max(4, Math.min(12, contract.point_pool | 0))' in js and 'Math.max(2, Math.min(8, contract.spot_pool | 0))' in js)
    from hstudio.director import prompts, heuristic
    sent = '\n'.join(v for k, v in vars(prompts).items() if k.isupper() and isinstance(v, str))
    code_ = (ROOT / 'hstudio/director/prompts.py').read_text(encoding='utf-8') + (ROOT / 'hstudio/director/heuristic.py').read_text(encoding='utf-8')
    check('le réalisateur IA ne connaît ni `stage_light` ni `theatre_bal` (option non jugée)', all(k not in sent and k not in code_ for k in ('stage_light', 'theatre_bal')))


# ------------------------------------------------------------------------------------------------- clés de lumière
def key_tests():
    from hstudio.engines.pixel3d import stage_light as SL
    for n in SL.PRESETS:
        s = SL.apply(SL.BASE, n); check(f'lavis « {n} » : couleurs posées', s['wash'] == SL.PRESETS[n]['wash'] and s['back'] == SL.PRESETS[n]['back'])
    SL.NOTES.clear(); s = SL.apply(SL.BASE, 'arc_en_ciel')
    check('lavis inconnu : bleu_nuit gardé, et dit en français', s['wash'] == SL.PRESETS['bleu_nuit']['wash'] and any('inconnu' in n for n in SL.NOTES), SL.NOTES[-1] if SL.NOTES else '')
    check('alias : « or » = ambre, « bleu » = bleu_nuit, « lavender » = lavande', SL.apply(SL.BASE, 'or')['wash'] == SL.PRESETS['ambre']['wash'] and SL.apply(SL.BASE, 'bleu')['wash'] == SL.PRESETS['bleu_nuit']['wash'] and SL.apply(SL.BASE, 'lavender')['wash'] == SL.PRESETS['lavande']['wash'])
    check('couleur écrite : "#ff8000" et [255, 128, 0] donnent la même chose', SL.color('#ff8000') == SL.color([255, 128, 0]))
    shot = {'stage_light': [{'t': 0, 'wash': 'bleu_nuit'}, {'t': 2, 'wash': 'ambre'}]}
    mid = SL.shot_state({}, shot, 1.0); a, b = SL.PRESETS['bleu_nuit']['wash'], SL.PRESETS['ambre']['wash']
    check('clés dans le temps : à mi-chemin la couleur est la moyenne (smoothstep)', all(abs(m - (x + y) / 2) < 1e-6 for m, x, y in zip(mid['wash'], a, b)), str(tuple(round(v, 3) for v in mid['wash'])))
    check('clés dans le temps : avant la 1re clé = 1re clé, après la dernière = dernière', SL.shot_state({}, shot, -1)['wash'] == a and SL.shot_state({}, shot, 5)['wash'] == b)
    cut = {'stage_light': [{'t': 0, 'wash': 'bleu_nuit'}, {'t': 2, 'wash': 'ambre', 'cut': True}]}
    check('coupe : la lumière saute à la clé (pas de fondu)', SL.shot_state({}, cut, 1.99)['wash'] == a and SL.shot_state({}, cut, 2.0)['wash'] == b)
    prev = {'stage_light': 'violet'}; cur = {'stage_light': {'wash': 'ambre', 'fade_in': 1.0}}
    s0 = SL.shot_state({}, cur, 0., prev, 3.); s1 = SL.shot_state({}, cur, 1.0, prev, 3.)
    check('fade_in : le plan part de la lumière de la fin du plan précédent et arrive à la sienne', s0['wash'] == SL.apply(SL.BASE, 'violet')['wash'] and s1['wash'] == SL.apply(SL.BASE, 'ambre')['wash'])
    check('épisode : `stage_light` par défaut, le plan s\'écrit par-dessus', SL.shot_state({'stage_light': {'wash': 'ambre', 'haze': .8}}, {'stage_light': {'curtain': 1}}, 0.)['haze'] == .8)
    s = SL.apply(SL.BASE, {'follow': {'on': 'lea', 'r': 1.2}})
    r = SL.resolve(s, {}, {'lea': (2.0, 0., 5.0)}, 3.)
    f = r['follow'][0]
    check('poursuite : le cercle suit l\'acteur (cible = ses pieds, visée = sa poitrine)', f['target'] == (2.0, 0., 5.0) and abs(f['aim'][1] - 1.0) < 1e-9, f"cible {f['target']}")
    r2 = SL.resolve(s, {}, {'lea': (-3.0, 3.5, 9.0)}, 3.)
    check('poursuite : l\'acteur sur la galerie (y = 3,5) est suivi en hauteur', r2['follow'][0]['target'][1] == 3.5)
    SL.NOTES.clear(); r3 = SL.resolve(s, {}, {}, 3.)
    check('poursuite sur un acteur absent : éteinte, et dit en français', r3['follow'] == () and any('absent' in n for n in SL.NOTES))
    st = SL.resolve(SL.apply(SL.BASE, {'curtain': .2}), {'curtain': .7, 'light_i': .5, 'practicals': 0.}, {}, 0.)
    check('état du monde (state_track) : curtain remplacé puis multiplié par light_i, practicals remplacé', abs(st['curtain'] - .35) < 1e-9 and st['practicals'] == 0., f"curtain {st['curtain']}")
    t1 = SL.turn_angles({'turn_inner_rate': 10., 'turn_outer': 30.}, 4.5)
    check('plateau tournant : vitesse x temps du film (anneau intérieur), angle écrit (extérieur)', abs(t1[0] - math.radians(45.)) < 1e-9 and abs(t1[1] - math.radians(30.)) < 1e-9)
    pl = SL.resolve(SL.apply(SL.BASE, {'pools': [{'on': 'lea', 'r': 2., 'ring': .8, 'dapple': .6}]}), {}, {'lea': (1., 0., 4.)}, 0.)['pools'][0]
    check('disque au sol : centré sur l\'acteur, anneau et tacheté gardés', pl['at'] == (1., 4.) and pl['ring'] == .8 and pl['dapple'] == .6)
    e1 = SL.evaluate({}, [shot], 0, 1.3, {}, {}, 2.); e2 = SL.evaluate({}, [shot], 0, 1.3, {}, {}, 2.)
    check('déterminisme : même plan, même instant -> même enregistrement', e1 == e2)
    from hstudio.engines.pixel3d import theatre as TH
    check('scintillement : fonction du temps seule', TH.flicker(3.21, 4) == TH.flicker(3.21, 4) and TH.flicker(3.21, 4) != TH.flicker(3.25, 4))


# ------------------------------------------------------------------------------------------------- géométrie
def geometry_tests():
    from hstudio.engines.pixel3d import theatre as TH, sets as S, stage as STG
    P = TH.plan(); st = S.make_set('theatre_bal', {'type': 'theatre_bal'}); st.build()
    check('dimensions : scène de 16 m (x -8..8), 10 m de profondeur, galerie à 3,5 m', TH.W_HALF * 2 == 16. and TH.DEPTH == 10. and TH.GAL_Y == 3.5)
    check('plateau tournant : deux anneaux concentriques (r 1,8 et 4,0) au centre de la scène', TH.TT == (0., 4.6, 1.8, 4.0))
    sw = STG.SetWorld(st, None, None, st.spec)
    steps = [w for w in P['walkable'] if w['rect'][0] == TH.STAIR_L['x0']]
    rises = np.diff([0.] + [w['y'] for w in steps])
    check('escalier gauche : 17 marches, contremarche < 35 cm (la régie les monte)', len(steps) == 17 and rises.max() < .35, f'{rises.max():.3f} m')
    check('niveaux : galerie à 3,5 m, milieu de l\'escalier gauche ~1,75 m, scène à 0', sw.ground_y(0., 9.2) == 3.5 and abs(sw.ground_y(-6.0, 5.45) - 1.85) < .25 and sw.ground_y(0., 4.) == 0., f"{sw.ground_y(-6.0, 5.45)}")
    need = ('centre', 'avant_scene', 'bord_scene', 'escalier_gauche.bas', 'escalier_gauche.haut', 'escalier_droit.bas', 'escalier_droit.haut', 'galerie', 'bougies_fond_gauche', 'start')
    check('ancres du lieu', all(a in st.anchors for a in need), ', '.join(need))
    check('éléments : 16 lanternes, ≥ 100 bougies, 13 projecteurs, ≥ 8 rouleaux de corde', len(P['lanterns']) == 16 and len(P['candles']) >= 100 and len(P['fixtures']) == 13 and len(P['coils']) >= 8,
          f"{len(P['lanterns'])} / {len(P['candles'])} / {len(P['fixtures'])} / {len(P['coils'])}")
    check('bord de scène en arc : 1,25 m d\'avancée au centre, 0 aux côtés', abs(float(TH.edge_z(0.)) + 1.25) < 1e-9 and abs(float(TH.edge_z(8.6))) < 1e-9)
    alb, _ = TH.floor_albedo(np.array([0., 0.]), np.array([-2., 2.]))
    check('au-delà du bord de scène : le noir', alb[0].max() < .01 and alb[1].max() > .05)
    from hstudio.voxelgpu import b_theatre as BT
    s, d = BT.native()
    fin = all(all(math.isfinite(b[k]) for k in ('x', 'y', 'z', 'w', 'h', 'd')) for b in s['boxes'] + d['inner'] + d['outer'])
    check('VOXEL natif : briques, poutres, marches, bougies en blocs (boîtes finies)', fin and len(s['boxes']) > 2500, f"{len(s['boxes'])} blocs fixes, {len(d['inner']) + len(d['outer'])} lames du plateau tournant")
    check('VOXEL natif : aucune boîte PS1 repeinte (tout est refait en blocs)', st.voxel_native()[0] == set(range(len(st.base.boxes))))


# ------------------------------------------------------------------------------------------------- rendu PS1 et contrat VOXEL
def render_tests():
    m = demo(); ep, lines = m.episode()
    from hstudio.pipeline import make_engine
    def eng(e=None): return make_engine('pixel3d', copy.deepcopy(e or ep), lines, np.zeros(10), ep['duration'], '16:9')
    E = eng(); a = E.render_lowres(9.0)[0]; b = E.render_lowres(9.0)[0]; c = eng().render_lowres(9.0)[0]
    check('PS1 : même image deux fois, et dans un moteur neuf (déterminisme)', h(a) == h(b) == h(c), h(a))
    def variant(k, **sl):
        e2 = copy.deepcopy(ep); e2['shots'][k]['stage_light'] = dict(e2['shots'][k]['stage_light'] if isinstance(e2['shots'][k]['stage_light'], dict) else {'wash': e2['shots'][k]['stage_light']}, **sl); return e2
    t4 = 4 * m.DUR + 1.
    on = eng().render_lowres(t4)[0].astype(np.int16); off = eng(variant(4, curtain=0.)).render_lowres(t4)[0].astype(np.int16)
    check('PS1 : le rideau de lumière change réellement l\'image', np.abs(on - off).mean() > 2., f'écart moyen {np.abs(on - off).mean():.1f}/255')
    t3 = 3 * m.DUR + 1.
    on = eng().render_lowres(t3)[0].astype(np.int16); off = eng(variant(3, follow=None)).render_lowres(t3)[0].astype(np.int16)
    check('PS1 : la poursuite change réellement l\'image (noir sans elle)', np.abs(on - off).mean() > .5 and off.mean() < on.mean(), f'écart moyen {np.abs(on - off).mean():.1f}/255, moyenne {on.mean():.1f} -> {off.mean():.1f}')
    e3 = copy.deepcopy(ep); e3['state'] = {'turn_inner': 0., 'turn_outer': 0.}; e4 = copy.deepcopy(ep); e4['state'] = {'turn_inner': 40., 'turn_outer': -25.}
    x1 = eng(e3).render_lowres(1.0)[0].astype(np.int16); x2 = eng(e4).render_lowres(1.0)[0].astype(np.int16)
    check('PS1 : tourner le plateau change le plancher', np.abs(x1 - x2).mean() > .2, f'écart moyen {np.abs(x1 - x2).mean():.2f}/255')
    w0 = eng(variant(0, wash='bleu_nuit')).render_lowres(1.0)[0].astype(float).mean((0, 1)); w1 = eng(variant(0, wash='ambre')).render_lowres(1.0)[0].astype(float).mean((0, 1))
    check('PS1 : lavis bleu = image bleue, lavis ambre = image chaude', w0[2] > w0[0] and w1[0] > w1[2], f'bleu RGB {w0.round(0)}, ambre RGB {w1.round(0)}')
    from hstudio.voxelgpu import from_ps1, contract as C
    c1 = from_ps1.build(copy.deepcopy(ep), lines, ep['duration'], '16:9', 24, lambda *_: None); c2 = from_ps1.build(copy.deepcopy(ep), lines, ep['duration'], '16:9', 24, lambda *_: None)
    check('VOXEL : même contrat deux fois (déterminisme)', C.digest(c1) == C.digest(c2), C.digest(c1)[:16])
    ok = all(len(s['theatre']['frames']) == len(s['camera']) for s in c1['stages'])
    check('VOXEL : une ligne de lumière par image de caméra, dans chaque plan', ok, f"{sum(len(s['theatre']['frames']) for s in c1['stages'])} lignes")
    check('VOXEL : le contrat ouvre 8 projecteurs et 8 lumières (théâtre seulement)', c1.get('spot_pool') == 8 and c1.get('point_pool') == 8)
    check('VOXEL : décor écrit une seule fois (prop_sets), taille du contrat raisonnable', len(c1.get('prop_sets') or {}) == 1 and len(C.dumps(c1)) < 3e6, f'{len(C.dumps(c1)) / 1e6:.2f} Mo')
    from hstudio.voxelgpu import b_theatre as BT
    row = c1['stages'][3]['theatre']['frames'][10]; nf = int(row[22]); npl = int(row[23 + nf * 16])
    check('VOXEL : ligne de lumière = COLS + 16 par poursuite + 1 + 9 par disque', len(row) == len(BT.COLS) + 16 * nf + 1 + 9 * npl and nf == 1, f'{len(row)} nombres, {nf} poursuite(s), {npl} disque(s)')
    return c1


def gpu_tests(c):
    from hstudio.voxelgpu import contract as C, render
    with tempfile.TemporaryDirectory() as td:
        td = Path(td); cp = td / 'c.json'; C.save(c, cp); t = round(c['stages'][4]['t0'] + .9, 2)
        c2 = copy.deepcopy(c)
        for row in c2['stages'][4]['theatre']['frames']: row[16] = 0.
        cp2 = td / 'c2.json'; C.save(c2, cp2)
        render.run_painter(cp, None, 'nvidia', (640, 360), stills=[t], stills_dir=td / 'a', quiet=True, fallback=True)
        render.run_painter(cp, None, 'nvidia', (640, 360), stills=[t], stills_dir=td / 'b', quiet=True, fallback=True)
        render.run_painter(cp2, None, 'nvidia', (640, 360), stills=[t], stills_dir=td / 'c', quiet=True, fallback=True)
        from PIL import Image
        A, B, D = (np.asarray(Image.open(td / d / f't_{t:.2f}.png').convert('RGB')).astype(np.int16) for d in ('a', 'b', 'c'))
        check('GPU : deux rendus VOXEL identiques (même contrat, même image)', np.array_equal(A, B), h(A))
        check('GPU : le rideau de lumière change réellement l\'image VOXEL', np.abs(A - D).mean() > 1., f'écart moyen {np.abs(A - D).mean():.1f}/255')


if __name__ == '__main__':
    optin_tests(); key_tests(); geometry_tests(); c = render_tests()
    if '--gpu' in sys.argv: gpu_tests(c)
    bad = [r for r in RESULTS if not r[1]]
    print(f'\n{len(RESULTS) - len(bad)}/{len(RESULTS)} vérifications OK')
    sys.exit(1 if bad else 0)
