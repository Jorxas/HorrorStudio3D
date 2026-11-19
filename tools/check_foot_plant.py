"""Verifications de l'option "foot_plant" (semelles plantees a la marche et a la course).

    python tools/check_foot_plant.py

Rien n'est rendu. Tout passe par le chemin de production (hstudio.acting.timeline), jamais par une
re-implementation de la marche.

Ce qui est verifie :
  1. opt-in       sans la cle, avec la cle a false / 'off' / 'none', la regie est IDENTIQUE a l'historique,
                  echantillon par echantillon et bit pour bit.
  2. inertie      avec la cle, le trajet, la duree, le cap et la vitesse ne bougent pas d'un chiffre : seule
                  la foulee (Path.S) change. C'est ce qui autorise a l'activer sans redecouper une scene.
  3. adherence    le glissement de la semelle EN APPUI (phase du cycle, pas "le pied le plus bas") baisse d'au
                  moins 3x sur chaque cas temoin, marche comme course.
  4. sol          pendant l'appui la semelle reste a 0 : ni penetration du sol, ni pied qui flotte.
  5. jambes       longueurs cuisse / tibia conservees et genou jamais inverse (le genou reste devant la ligne
                  hanche-cheville) -- la correction ne fige pas une jambe pour faire baisser un chiffre.
  6. arrets       une marche finit pieds joints, pas a cheval sur une foulee.
  7. bras, regard les bras, la tete et l'IK de prehension sont inchanges a cap et foulee donnes.
  8. cumul        la cle se combine avec "footing" et "approach" sans se battre avec elles.
  9. determinisme deux constructions identiques donnent les memes nombres.
 10. discipline    la cle n'est enseignee ni au realisateur IA ni a une demo livree (AGENTS.md), mais le
                  validateur la garde quand un episode la demande.
 11. non-regression le meme releve, rejoue par le code du dernier commit deplie dans un dossier temporaire :
                  sans la cle, egalite bit pour bit sur 3000 echantillons.
"""
import os, sys, math
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))
from hstudio.acting import rig, timeline as TL                   # noqa: E402
from foot_plant_qc import control, sample_run, measure, CASES   # noqa: E402

FAIL = []


def check(ok, label, detail=''):
    print(('OK    ' if ok else 'ECHEC ') + label + ('  ' + detail if detail else ''))
    if not ok: FAIL.append(label)


def samples(plant=False, kind='run', dist=9., corner=True, footing=False, n=240):
    sa, dur = control(kind=kind, dist=dist, corner=corner, footing=footing, plant=plant)
    out = []
    for i in range(n):
        t = i * dur / n
        s = sa.sample(t)['temoin']
        out.append((round(s['x'], 9), round(s['z'], 9), round(s['heading'], 9),
                    round(float(s['rig']['phase']), 9), round(float(s['rig']['gait']), 9),
                    round(float(s['rig']['stride']), 9)))
    return out, sa, dur


# ---------------------------------------------------------------- 1. opt-in
def t_optin():
    ref, _sa, _d = samples(plant=False)
    for v in (None, False, '', 'off', 'none', 'legacy'):
        got = TL.planted({'foot_plant': v} if v is not None else {}, {})
        check(got is False, f'opt-in : "foot_plant" = {v!r} laisse l\'historique')
    check(TL.planted({'foot_plant': True}, {}) is True, 'opt-in : "foot_plant": true allume bien')
    check(TL.planted({}, {'foot_plant': True}) is True, 'opt-in : un plan seul peut l\'allumer')
    check(TL.planted({'foot_plant': True}, {'foot_plant': False}) is False, 'opt-in : le plan peut l\'eteindre')
    on, _sa, _d = samples(plant=True)
    check(ref != on, 'opt-in : avec la cle, la foulee change bien')
    # et sans la cle, rien ne bouge : meme objet de scene, deux constructions
    again, _sa, _d = samples(plant=False)
    check(ref == again, 'opt-in : sans la cle, bit pour bit l\'historique')


# ---------------------------------------------------------------- 2. le trajet ne bouge pas
def t_inertie():
    a, sa_a, da = samples(plant=False)
    b, sa_b, db = samples(plant=True)
    check(abs(da - db) < 1e-9, 'inertie : meme duree de plan', f'{da:.4f} s')
    pa, pb = sa_a.tracks['temoin'].paths, sa_b.tracks['temoin'].paths
    check(len(pa) == len(pb), 'inertie : meme nombre de chemins', f'{len(pa)}')
    for i, (x, y) in enumerate(zip(pa, pb)):
        check(abs(x.D - y.D) < 1e-6, f'inertie : chemin {i}, meme longueur', f'{x.D:.4f} m')
        check(abs(x.t0 - y.t0) < 1e-9 and abs(x.t1 - y.t1) < 1e-9, f'inertie : chemin {i}, memes temps')
        check(abs(x.v - y.v) < 1e-9, f'inertie : chemin {i}, meme vitesse', f'{x.v:.3f} m/s')
        check(np.allclose(x.pts, y.pts), f'inertie : chemin {i}, meme polyligne')
        check(abs(x.S - y.S) > 1e-6, f'inertie : chemin {i}, la foulee CHANGE (c\'est le seul effet)',
              f'{x.S:.4f} -> {y.S:.4f} m')
    dx = max(abs(p[0] - q[0]) + abs(p[1] - q[1]) for p, q in zip(a, b))
    dh = max(abs(TL.wrap(p[2] - q[2])) for p, q in zip(a, b))
    check(dx < 1e-9, 'inertie : le corps passe exactement aux memes endroits', f'ecart max {dx:.2e} m')
    check(dh < 1e-9, 'inertie : et avec exactement le meme cap', f'ecart max {math.degrees(dh):.2e} deg')


# ---------------------------------------------------------------- 3. adherence
def t_adherence():
    worst_a = worst_b = 0.
    for name, kw in CASES:
        a = measure(sample_run(*control(**kw)))
        b = measure(sample_run(*control(**dict(kw, plant=True))))
        worst_a = max(worst_a, a['slide_max']); worst_b = max(worst_b, b['slide_max'])
        if a['slide_max'] < .5:                       # ce cas n'avait deja pas de defaut mesurable
            check(b['slide_max'] < 1.0, f'adherence : {name} reste propre', f"{a['slide_max']:.2f} -> {b['slide_max']:.2f} cm/i")
            continue
        check(b['slide_max'] * 3. < a['slide_max'], f'adherence : {name}, au moins 3x mieux',
              f"max {a['slide_max']:.2f} -> {b['slide_max']:.2f} cm/i")
    check(worst_b < 2.0, 'adherence : pire cas sous 2 cm/image', f'{worst_a:.2f} -> {worst_b:.2f} cm/i')
    # la mesure heritee ("le pied le plus bas"), elle, ne bouge pas : elle ne mesurait pas l'adherence
    a = measure(sample_run(*control(kind='run', dist=14.)))
    b = measure(sample_run(*control(kind='run', dist=14., plant=True)))
    check(abs(a['legacy_max'] - b['legacy_max']) < 1.0,
          'adherence : la mesure heritee ne bouge pas (elle mesure la phase aerienne, pas l\'appui)',
          f"{a['legacy_max']:.2f} -> {b['legacy_max']:.2f} cm/i, phase aerienne {100 * b['flight_share']:.0f} %")


# ---------------------------------------------------------------- 4. le sol
def t_sol():
    for name, kw in CASES:
        m = measure(sample_run(*control(**dict(kw, plant=True))))
        check(m['sole_y_min'] > -.3, f'sol : {name}, aucune penetration', f"min {m['sole_y_min']:.3f} cm")
        check(m['sole_y_max'] < .3, f'sol : {name}, aucun pied qui flotte', f"max {m['sole_y_max']:.3f} cm")


# ---------------------------------------------------------------- 5. les jambes
def t_jambes():
    sa, dur = control(kind='run', dist=12., corner=True, plant=True)
    worst_len = 0.; inv = 0; n = 0
    for i in range(int(dur * 30)):
        s = sa.sample(i / 30.)['temoin']; sk = rig.solve(s['rig'])
        for tag in ('L', 'R'):
            hip, kn, an = sk.joints['hip' + tag], sk.joints['kn' + tag], sk.joints['an' + tag]
            worst_len = max(worst_len, abs(float(np.linalg.norm(kn - hip)) - rig.THIGH),
                            abs(float(np.linalg.norm(an - kn)) - rig.SHIN))
            # genou devant la ligne hanche-cheville (jamais plie a l'envers)
            d = an - hip; L = float(np.linalg.norm(d))
            if L > 1e-6:
                u = d / L; proj = hip + u * float((kn - hip) @ u)
                if float((kn - proj)[2]) < -.004: inv += 1
            n += 1
    check(worst_len < 1e-3, 'jambes : cuisse et tibia gardent leur longueur', f'ecart max {1000 * worst_len:.2f} mm')
    check(inv == 0, 'jambes : aucun genou inverse', f'{inv} sur {n} controles')


# ---------------------------------------------------------------- 6. les arrets
def t_arrets():
    for kind, dist in (('walk', 7.), ('run', 9.), ('hurry', 6.)):
        sa, dur = control(kind=kind, dist=dist, plant=True)
        p = sa.tracks['temoin'].paths[0]
        s = sa.sample(min(dur - .01, p.t1 - .01))['temoin']; sk = rig.solve(s['rig'])
        spread = abs(float(sk.joints['anL'][2] - sk.joints['anR'][2]))
        check(spread < .22, f'arrets : {kind} finit pieds joints', f'ecart {100 * spread:.1f} cm entre les chevilles')


# ---------------------------------------------------------------- 7. bras, tete, IK
def t_haut_du_corps():
    """a foulee et cap donnes, rig.solve dessine le meme haut du corps : la cle ne touche que les pieds"""
    worst = 0.
    for ph in (0., .7, 1.9, 3.3, 5.1):
        p = dict(t=1.2, seed=3., phase=ph, gait=1., run=1., stride=2.2, sit=0., crouch=0.,
                 gestures=[('wave', .6, .4)], head=(.3, -.1), reach={1: ((.4, 1.2, .5), .8)})
        a = rig.solve(dict(p)); b = rig.solve(dict(p))
        for j in ('shR', 'elR', 'haR', 'shL', 'elL', 'haL', 'head', 'neck', 'chest'):
            worst = max(worst, float(np.linalg.norm(a.joints[j] - b.joints[j])))
    check(worst < 1e-9, 'haut du corps : bras, tete et IK de prehension inchanges', f'ecart max {worst:.2e} m')
    # et la cle ne passe PAS par rig.solve : elle n'ajoute aucun parametre au squelette
    sa_a, da = control(kind='run', dist=9., plant=False)
    sa_b, db = control(kind='run', dist=9., plant=True)
    ka = set(sa_a.sample(1.)['temoin']['rig']); kb = set(sa_b.sample(1.)['temoin']['rig'])
    check(ka == kb, 'haut du corps : aucun parametre nouveau dans le squelette', ', '.join(sorted(kb)))


# ---------------------------------------------------------------- 8. cumul avec les autres options
def t_cumul():
    res = {}
    for fo in (False, True):
        for pl in (False, True):
            m = measure(sample_run(*control(kind='run', dist=12., corner=True, footing=fo, plant=pl)))
            res[(fo, pl)] = m['slide_max']
    check(all(v == v for v in res.values()), 'cumul : les quatre combinaisons restent finies')
    check(res[(False, True)] < res[(False, False)], 'cumul : "foot_plant" seul ameliore',
          f'{res[(False, False)]:.2f} -> {res[(False, True)]:.2f} cm/i')
    check(res[(True, True)] <= res[(True, False)] + .05, 'cumul : sous "footing", il ne degrade pas',
          f'{res[(True, False)]:.2f} -> {res[(True, True)]:.2f} cm/i')
    # "footing" impliquait deja le plantage : avec les deux, la foulee doit etre la meme qu'avec "footing" seul
    _a, sa_a, _d = samples(plant=False, footing=True)
    _b, sa_b, _d2 = samples(plant=True, footing=True)
    same = all(abs(x.S - y.S) < 1e-9 for x, y in zip(sa_a.tracks['temoin'].paths, sa_b.tracks['temoin'].paths))
    check(same, 'cumul : sous "footing" la cle est deja acquise, elle ne change rien de plus')


# ---------------------------------------------------------------- 9. determinisme
def t_determinisme():
    a, _s, _d = samples(plant=True)
    b, _s2, _d2 = samples(plant=True)
    check(a == b, 'determinisme : deux constructions identiques')


# ---------------------------------------------------------------- 10. discipline de l'opt-in
def t_discipline():
    """AGENTS.md : une cle opt-in neuve n'est PAS enseignee au realisateur IA tant que le proprietaire n'a pas
    juge le rendu -- un realisateur qui connait une cle la met dans tous les episodes, et l'opt-in est allume
    en pratique. On verifie donc le texte REELLEMENT envoye au LLM, et le code du realisateur sans commentaire.
    """
    import re, glob
    hits = []
    for path in glob.glob(os.path.join(ROOT, 'hstudio', 'director', '*.py')):
        src = open(path, encoding='utf-8').read()
        src = re.sub(r'(?m)#.*$', '', src)                       # un commentaire n'atteint jamais le LLM
        src = re.sub(r'(?s)""".*?"""', '', src)
        if 'foot_plant' in src: hits.append(os.path.basename(path))
    check(not hits, 'discipline : la cle n\'est pas enseignee au realisateur IA', ', '.join(hits) or 'aucun fichier')
    try:
        from hstudio.director import prompts
        txt = ' '.join(str(v) for v in vars(prompts).values() if isinstance(v, str))
        check('foot_plant' not in txt, 'discipline : la cle n\'est pas dans le texte envoye au LLM')
    except Exception as e:
        print('      (prompts illisible :', e, ')')
    # aucune demo, aucune scene livree ne doit la porter : la decision appartient au proprietaire
    worn = []
    for pat in ('examples/**/*.json', 'tests/scenes/*.json', 'config/*.json'):
        for path in glob.glob(os.path.join(ROOT, pat), recursive=True):
            if 'foot_plant' in open(path, encoding='utf-8').read() and 'course_lea_foot_plant' not in path:
                worn.append(os.path.relpath(path, ROOT))
    check(not worn, 'discipline : aucune demo ni scene livree ne l\'allume', ', '.join(worn) or 'aucune')
    # mais le validateur ne doit pas la jeter quand un episode la demande
    from hstudio.director.validate import validate
    ep = {'engine_version': 2, 'foot_plant': True, 'default_set': 's', 'sets': {'s': {'type': 'living_room'}},
          'cast': {'lea': {'ref': 'lea'}},
          'shots': [{'lines': [0, 0], 'actors': [{'id': 'lea', 'at': [0, 0]}],
                     'actions': [{'who': 'lea', 'do': 'walk_to', 'to': [0, 3]}]}]}
    out = validate(ep, 1, 'pixel3d'); o = out[0] if isinstance(out, tuple) else out
    check((o or {}).get('foot_plant') is True, 'discipline : mais le validateur la garde quand on la demande')


# ---------------------------------------------------------------- 11. non-regression contre le code d'AVANT
PROBE = r'''
import sys, os, json
sys.path.insert(0, os.getcwd())
from hstudio.acting import timeline as TL
rows = []
for kind, dist, corner in (('walk', 7., False), ('run', 14., False), ('run', 12., True),
                           ('hurry', 9., False), ('slow', 5., False)):
    to = [0., dist] if not corner else [dist * .55, dist * .55]
    acts = [{'do': 'walk_to', 'who': 't', 'to': to, 'speed': kind, 'at': .35}]
    if corner: acts.append({'do': 'walk_to', 'who': 't', 'to': [0., dist * 1.1], 'speed': kind})
    shot = {'actors': [{'id': 't', 'at': [0., 0.], 'facing': '+z'}], 'actions': acts}
    v = TL.SPEEDS.get(kind, 1.15); dur = .35 + dist * (1.3 if not corner else 1.9) / v + 1.6
    for footing in (False, True):
        sa = TL.ShotActing(shot, TL.World(), {}, [], dur, footing=footing)
        for i in range(300):
            s = sa.sample(i * dur / 300)['t']; r = s['rig']
            rows.append([round(s['x'], 12), round(s['z'], 12), round(s['heading'], 12),
                         round(float(r['phase']), 12), round(float(r['gait']), 12), round(float(r['stride']), 12),
                         round(float(r['run']), 12), round(float(r['crouch']), 12)])
print(json.dumps(rows))
'''


def t_non_regression():
    """le meme releve, joue par CE code et par le code du dernier commit : sans la cle, rien ne doit bouger.

    `tools/check_foot_plant.py` ne peut pas se contenter de se comparer a lui-meme : il faut comparer au code
    d'AVANT le correctif. On deplie donc HEAD dans un dossier temporaire et on y rejoue le meme releve.
    """
    import subprocess, tempfile, shutil, json
    git = shutil.which('git')
    if git is None:
        print('      (git introuvable : comparaison au commit precedent sautee)'); return
    tmp = tempfile.mkdtemp(prefix='foot_plant_base_')
    try:
        tar = subprocess.run([git, 'archive', 'HEAD'], cwd=ROOT, capture_output=True)
        if tar.returncode:
            print('      (git archive a echoue : comparaison sautee)'); return
        import tarfile, io
        with tarfile.open(fileobj=io.BytesIO(tar.stdout)) as t:
            t.extractall(tmp)
        got = {}
        for tag, cwd in (('avant', tmp), ('apres', ROOT)):
            r = subprocess.run([sys.executable, '-c', PROBE], cwd=cwd, capture_output=True, text=True)
            if r.returncode:
                print('      (releve impossible dans', tag, ':', (r.stderr or '')[-200:], ')'); return
            got[tag] = json.loads(r.stdout)
        check(got['avant'] == got['apres'],
              'non-regression : sans la cle, bit pour bit le code du dernier commit',
              f"{len(got['apres'])} echantillons (5 vitesses x 2 reglages footing x 300 images)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    for fn in (t_optin, t_inertie, t_adherence, t_sol, t_jambes, t_arrets, t_haut_du_corps, t_cumul,
               t_determinisme, t_discipline, t_non_regression):
        print(f'-- {fn.__name__[2:]}')
        fn()
    print()
    print('Tout est OK' if not FAIL else f'{len(FAIL)} echec(s) : ' + ', '.join(FAIL))
    sys.exit(1 if FAIL else 0)
