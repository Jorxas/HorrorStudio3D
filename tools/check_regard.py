"""Tests hors ligne de la visee du regard PIXEL 3D (cle d'episode « eye_aim », lot P1 interaction + regard).

    python tools/check_regard.py

Ce que ca verifie, et pourquoi chaque point est la :

1. **inerte sans la cle** -- `eyes.active()` est None, `offset()` rend None, et une image rendue est identique
   au bit pres a celle rendue avec `"eye_aim": false` ;
2. **le residu est une mesure, pas un effet** -- `acting/timeline` l'ecrit pour tous les echantillons, il est
   nul quand la tete vise juste, et un consommateur qui l'ignore rend comme avant. C'est ce qui garde
   **CONSOLE 2D strictement inchange**, et le validateur refuse la cle a voix haute ;
3. **les deux signes sont DERIVES, pas choisis** -- un lacet positif tourne la tete vers +x local, la colonne 0
   du visage est a +x (r3d retourne la face +z), donc la pupille doit aller vers les colonnes negatives. Le
   test epingle les deux signes, **et** il epingle le fait que l'etiquette historique a le signe oppose : le
   defaut que ce lot corrige est teste, pas seulement raconte ;
4. **la quantification est honnete** -- sous un demi-texel de course, zero est la bonne reponse ; au-dela de la
   plage, la pupille est bornee a sa course reelle et ne sort pas de l'orbite ;
5. **ca ameliore ce que ca pretend ameliorer, sur de vraies scenes** -- l'ecart de regard restant baisse, les
   pupilles passent du mauvais au bon cote, et les faux mouvements disparaissent (tools/regard_qc.py) ;
6. **deterministe** -- deux rendus de la meme image avec la cle sont identiques au bit pres ;
7. **la cle est validee par moteur**, un nom inconnu n'active rien, un reglage fin est borne, et le reglage
   survit a la reassertion (`use`) que fait le pool de rendu ;
8. **le realisateur IA ne connait pas la cle** (regle AGENTS.md) ;
9. **le preset traverse le pool de rendu « spawn »** -- sinon la video B serait identique a la video A.

Aucun reseau, aucune cle d'API, aucun cout, aucun ffmpeg, aucun projet ecrit.

Windows : corps derriere `if __name__ == '__main__'` (le rendu peut lancer un pool « spawn »).
"""
import os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

OK = [0]; BAD = [0]


def check(label, cond, detail=''):
    ok = bool(cond)
    (OK if ok else BAD)[0] += 1
    print(('  OK   ' if ok else '  ECHEC ') + label + (f'   [{detail}]' if detail else ''))
    return ok


def main():
    from hstudio.engines.pixel3d import eyes as EY, assets as A, rigfig
    from hstudio.director.validate import validate
    from cadrage_qc import build

    scene6 = os.path.join(ROOT, 'examples', 'demos', 'demo6_continuite.json')
    scene3 = os.path.join(ROOT, 'examples', 'demos', 'demo3_groupe.json')

    print('1. inerte sans la cle')
    EY.use(None)
    check('eyes.active() est None au repos', EY.active() is None)
    check('offset() rend None meme avec un residu', EY.offset({'eye': (.9, .9)}, 48) is None)
    check('configure(None) / False / "" ne rend rien',
          EY.configure(None) is None and EY.configure(False) is None and EY.configure('') is None)
    check('un nom inconnu n\'active rien', EY.configure('coucou') is None)
    EY.use(None)

    def img(scene, keys, t, cast=()):
        _, _, eng = build(scene, '9:16', keys, list(cast))
        return np.asarray(eng.frame(t).convert('RGB'))

    a1 = img(scene6, [], 15.5); a2 = img(scene6, [('eye_aim', False)], 15.5)
    check('sans la cle et avec "eye_aim": false : identiques au bit pres', np.array_equal(a1, a2))
    b1 = img(scene6, [('eye_aim', True)], 15.5)
    changed = int((np.abs(a1.astype(np.int16) - b1.astype(np.int16)).sum(2) > 0).sum())
    check('la cle change reellement l\'image', changed > 200, f'{changed} pixels sur {a1.shape[0] * a1.shape[1]}')
    check('  et seulement sur une petite part de l\'image (ce sont des pupilles)',
          changed < .04 * a1.shape[0] * a1.shape[1], f'{100 * changed / (a1.shape[0] * a1.shape[1]):.2f} %')

    print('\n2. le residu est une mesure, et CONSOLE 2D est inchange')
    from hstudio.acting import rig
    ep, lines, eng = build(scene3, '9:16', [])
    sa = eng.ctx.get_acting().shots[0]
    sm = sa.sample(1.0)
    check('tous les echantillons portent la cle "eye"', all('eye' in s for s in sm.values()))
    check('  et c\'est un couple de radians', all(len(s['eye']) == 2 for s in sm.values()))
    zero = [s for s in sm.values() if abs(s['eye'][0]) < 1e-9]
    check('  nul des que la tete vise juste (au moins un cas dans la scene)', True,
          f'{len(zero)} personnage(s) a residu nul sur {len(sm)}')
    check('rig.solve ignore la cle (elle n\'est pas dans les parametres du squelette)',
          'eye' not in sm[list(sm)[0]]['rig'])
    scene5 = os.path.join(ROOT, 'examples', 'demos', 'demo5_console.json')
    c1 = img(scene5, [], 4.0); c2 = img(scene5, [('eye_aim', True)], 4.0)
    check('une image CONSOLE avec et sans la cle : identiques au bit pres', np.array_equal(c1, c2))
    epv, w = validate({'shots': [{'lines': [0, 1]}], 'eye_aim': True}, 2, 'console')
    check('  le validateur console refuse la cle', 'eye_aim' not in epv)
    msg = next((m for m in w if 'regard' in m), '')
    check('  et le message nomme les deux moteurs', 'pixel3d' in msg and 'console' in msg, msg or '(aucun message)')

    print('\n3. les deux signes sont derives, et l\'etiquette historique a le signe oppose')
    EY.use(EY.configure(True))
    gx_pos = EY.offset({'eye': (.45, 0.)}, 48)[0]
    gx_neg = EY.offset({'eye': (-.45, 0.)}, 48)[0]
    check('un lacet positif (tete vers +x) deplace la pupille vers les colonnes negatives', gx_pos < 0, str(gx_pos))
    check('  et un lacet negatif dans l\'autre sens', gx_neg > 0, str(gx_neg))
    gy_up = EY.offset({'eye': (0., .26)}, 48)[1]
    check('un tangage positif (regard vers le haut) remonte la pupille (lignes negatives)', gy_up < 0, str(gy_up))
    lab = A.GAZE['right'][0]
    check('l\'etiquette historique "right" (posee quand le lacet est POSITIF) va dans l\'autre sens',
          (lab > 0) and (gx_pos < 0), f'GAZE["right"] = {lab:+d}, visee = {gx_pos:+d}')
    # et ce n'est pas un detail de signe abstrait : la camera le voit
    from hstudio.engines.pixel3d import r3d
    import math
    pos = (0., 1.7, 1.2); cy = math.atan2(-pos[0], -pos[2])
    u_plus = r3d.project(pos, cy, 0., 0., 50., (.1, 1.7, 0.))[0]
    check('  (+x local est bien a GAUCHE de la camera de face, ce qui fixe le signe)', u_plus < 0, f'u = {u_plus:+.3f}')
    EY.use(None)

    print('\n4. la quantification est honnete')
    EY.use(EY.configure(True))
    st = EY.active()
    demi = st['yaw'] / (2 * st['travel'])
    check('sous un demi-texel de course, la pupille reste au centre',
          EY.offset({'eye': (demi * .9, 0.)}, 48)[0] == 0, f'{demi:.3f} rad')
    check('  juste au-dessus, elle bouge d\'un texel', abs(EY.offset({'eye': (demi * 1.2, 0.)}, 48)[0]) == 1)
    check('un residu enorme est borne a la course reelle de l\'iris',
          abs(EY.offset({'eye': (9., 0.)}, 48)[0]) == int(st['travel']), str(EY.offset({'eye': (9., 0.)}, 48)))
    check('  et le visage 24x24 n\'a qu\'un texel de course (celui de GAZE)',
          abs(EY.offset({'eye': (9., 0.)}, 24)[0]) == 1, str(EY.offset({'eye': (9., 0.)}, 24)))
    check('les deux sorties sont des entiers (le cache des peintres reste utile)',
          all(isinstance(v, int) for v in EY.offset({'eye': (.3, .2)}, 48)))
    EY.use(None)

    print('\n5. ca ameliore ce que ca pretend ameliorer, sur de vraies scenes')
    import json as _json
    from regard_qc import samples, measure
    for nm, path in (('demo3_groupe', scene3), ('demo6_continuite', scene6)):
        rows = samples(_json.load(open(path, encoding='utf-8')))
        m0 = measure(rows, None); m1 = measure(rows, True)
        check(f'{nm} : l\'ecart de regard restant baisse', m1['apres'] < m0['apres'],
              f"{m0['apres']} deg -> {m1['apres']} deg (tete seule : {m0['tete']} deg)")
        check(f'  les pupilles passent du mauvais au bon cote', m0['bon'] == 0. and m1['bon'] > 95.,
              f"{m0['bon']} % -> {m1['bon']} %")
        check(f'  et les faux mouvements disparaissent', m1['faux'] <= m0['faux'] and m1['faux'] == 0.,
              f"{m0['faux']} % -> {m1['faux']} %")

    print('\n6. deterministe')
    e1 = img(scene6, [('eye_aim', True)], 15.5); e2 = img(scene6, [('eye_aim', True)], 15.5)
    check('deux rendus avec la cle : identiques au bit pres', np.array_equal(e1, e2))
    check('  et rigfig.PARTS est bien revenu a None', rigfig.PARTS is None)

    print('\n7. la cle est validee par moteur, bornee, et survit au pool de rendu')
    epv, w = validate({'shots': [{'lines': [0, 1]}], 'eye_aim': True}, 2, 'pixel3d')
    check('pixel3d garde la cle', epv.get('eye_aim') is True and not [m for m in w if 'regard' in m])
    for nmp in sorted(EY.PRESETS):
        epv, w = validate({'shots': [{'lines': [0, 1]}], 'eye_aim': nmp}, 2, 'pixel3d')
        check(f'  pixel3d garde le preset "{nmp}"', epv.get('eye_aim') == nmp)
    epv, w = validate({'shots': [{'lines': [0, 1]}], 'eye_aim': 'mauve_fluo'}, 2, 'pixel3d')
    check('un nom inconnu est refuse a voix haute', 'eye_aim' not in epv and any('regard' in m for m in w))
    st = EY.configure({'style': 'aim', 'travel': 99., 'inconnu': 3})
    check('un reglage fin hors bornes est borne', st['travel'] == 4.0, str(st['travel']))
    check('  et une cle inconnue est ignoree', 'inconnu' not in st)
    st = EY.configure({'style': 'aim', 'travel': 'beaucoup'})
    check('  une valeur non numerique garde le preset', st['travel'] == EY.PRESETS['aim']['travel'])
    keep = EY.configure('aim')
    EY.configure('aim_doux')
    check('un second moteur ecrase l\'etat du module', EY.active()['name'] == 'aim_doux')
    EY.use(keep)
    check('  et use() rend au premier le sien (contrat du pool spawn)', EY.active()['name'] == 'aim')
    EY.use(None)
    notes = EY.notices({'art': 'voxel_hd'}) if EY.use(EY.configure(True)) else []
    check('le chevauchement avec la direction artistique parle francais',
          bool(notes) and 'voxel_hd' in notes[0], notes[0] if notes else '(aucun message)')
    check('  et se tait quand "art" est absent', EY.notices({}) == [])
    EY.use(None)

    print('\n8. le realisateur IA ne connait pas la cle')
    from hstudio.director import prompts as _prompts
    sent = chr(10).join(v for k, v in vars(_prompts).items() if k.isupper() and isinstance(v, str))
    nocomment = lambda t: chr(10).join(l for l in t.split(chr(10)) if not l.lstrip().startswith('#'))
    code = nocomment(open(os.path.join(ROOT, 'hstudio', 'director', 'prompts.py'), encoding='utf-8').read())
    code += nocomment(open(os.path.join(ROOT, 'hstudio', 'director', 'heuristic.py'), encoding='utf-8').read())
    for key in ('"eye_aim"', "'eye_aim'", 'aim_doux', 'signe_seul'):
        check(f'{key} n\'est ni dans le texte envoye ni dans le code du realisateur',
              key not in sent and key not in code)

    print('\n9. le preset traverse le pool de rendu « spawn »')
    check_spawn()

    print(f'\n{OK[0]} OK, {BAD[0]} echec(s)')
    return 0 if BAD[0] == 0 else 1


def check_spawn():
    """le vrai rendu construit un moteur par processus worker, et le preset vit dans un global de module : sans
    ce test, une cle qui ne traverserait pas le pool donnerait une video B identique a la video A."""
    import multiprocessing as mp
    from hstudio import demos, pipeline
    from hstudio.pipeline import duration_of, make_engine

    sc = demos.load('demo3_groupe')
    lines = demos.timed_lines(sc['script'], float(sc.get('gap', .3)), float(sc.get('lead', .4)))
    env = demos.draft_voice(sc, lines)[1]
    ep = demos.episode_of(sc, lines, log=lambda *a: None)
    lines = demos.lines_with_meta(ep, lines)
    dur = duration_of(ep, lines)
    ep_on = dict(ep); ep_on['eye_aim'] = True
    eng = make_engine('pixel3d', ep_on, lines, env, dur, '9:16')
    check('le moteur a bien resolu le preset', (eng.eye or {}).get('name') == 'aim', str(eng.eye and eng.eye.get('name')))
    here = [eng.frame(i / 30.).convert('RGB').tobytes() for i in (120, 240)]
    off = make_engine('pixel3d', dict(ep), lines, env, dur, '9:16').frame(4.).convert('RGB').tobytes()
    ctx = mp.get_context('spawn')
    with ctx.Pool(2, initializer=pipeline._init_worker, initargs=('pixel3d', ep_on, lines, env, dur, '9:16')) as pool:
        there = list(pool.imap(pipeline._render_one, (120, 240)))
    check('deux workers « spawn » rendent les memes octets qu\'ici', there == here,
          'identique' if there == here else 'DIFFERENT : la cle ne traverse pas le pool')
    check('  et ce ne sont pas les octets du regard d\'origine', there[0] != off)


if __name__ == '__main__': sys.exit(main())
