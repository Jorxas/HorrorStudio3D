"""Tests hors ligne du lissage des pupilles (cle d'episode « eye_smooth », acting/eyeflow.py).

    python tools/check_lissage.py

Ce que ca verifie, et pourquoi chaque point est la :

1. **inerte sans la cle** -- aucun plan ne porte de solveur, le residu est le meme flottant qu'avant, et une
   image rendue est identique **au bit pres** a celle rendue sans le module. `"eye_smooth": false`, `""`,
   `"snap"` valent absent ;
2. **le refactoring de `timeline.neck()` n'a rien deplace** -- la nouvelle fonction partagee rend exactement
   le lacet, le tangage, le residu et l'etiquette `gaze` que la boucle d'avant ecrivait. C'est le point qui
   protege les deux moteurs : si `neck()` derivait d'un bit, tous les rendus livres changeraient ;
3. **`raw_eye()` est le residu de `sample()`, exactement** -- sinon le lissage lisserait un signal que le
   rendu n'a pas, et la planche ne montrerait pas ce que la video montre ;
4. **ca fait ce que ca dit** -- sur une vraie scene, le plus gros saut de pupille d'une image a la suivante
   tombe, et le residu reste borne a la course de l'oeil ;
5. **une saccade est balistique et monotone** -- elle part, elle arrive, elle ne recule pas en route et elle
   ne reste pas immobile une image sur deux (c'etait un vrai defaut de la premiere version) ;
6. **CONSOLE 2D n'est pas touche** -- une image console avec la cle est identique au bit pres a la meme sans,
   et le validateur refuse la cle en nommant les deux moteurs ;
7. **la cle est validee** -- un nom inconnu n'active rien, un reglage fin est accepte, et le validateur
   previent quand le lissage est demande sans `"eye_aim"` (il ne dessinerait rien) ;
8. **le realisateur IA ne connait pas la cle** (regle AGENTS.md) ;
9. **deterministe, et ca traverse le pool de rendu « spawn »** -- sans ce test, une video B identique a la
   video A passerait inapercue.

Aucun reseau, aucune cle d'API, aucun cout, aucun ffmpeg, aucun projet ecrit.

Windows : corps derriere `if __name__ == '__main__'` (le rendu peut lancer un pool « spawn »).
"""
import os, sys, math, json, copy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

OK = [0]; BAD = [0]
SCENE = os.path.join(ROOT, 'examples', 'scenes', 'couloir_poignee.json')
DEMO6 = os.path.join(ROOT, 'examples', 'demos', 'demo6_continuite.json')
BASE = [('body', 'refit'), ('eyeline', 'smooth'), ('eye_aim', True)]


def check(label, cond, detail=''):
    ok = bool(cond)
    (OK if ok else BAD)[0] += 1
    print(('  OK   ' if ok else '  ECHEC ') + label + (f'   [{detail}]' if detail else ''))
    return ok


def acting_of(scene, keys):
    from cadrage_qc import build
    ep, lines, eng = build(scene, '9:16', list(keys))
    return ep, eng, eng.ctx.get_acting()


def series(sa, aid, step=1 / 30.):
    """[(t, residu lacet)] d'un personnage sur tout le plan, lu par sample() comme le rendu le lit"""
    out = []; t = 0.
    while t < sa.dur:
        sm = sa.sample(float(t)).get(aid)
        if sm is not None: out.append((t, float((sm.get('eye') or (0., 0.))[0])))
        t += step
    return out


def main():
    from hstudio.acting import eyeflow as EF, timeline as TL
    from hstudio.director.validate import validate

    print('1. inerte sans la cle')
    _, _, ac0 = acting_of(SCENE, BASE)
    check('aucun plan ne porte de solveur sans la cle',
          all(sa.eyeflow is None for sa in ac0.shots.values()))
    for off in (False, '', 'snap', 'off', None):
        check(f'options({off!r}) rend None', EF.options(off) is None)
    check('un nom inconnu n\'active rien', EF.options('coucou') is None)
    _, _, ac_off = acting_of(SCENE, BASE + [('eye_smooth', 'snap')])
    check('"eye_smooth": "snap" ne pose aucun solveur',
          all(sa.eyeflow is None for sa in ac_off.shots.values()))

    from cadrage_qc import build
    def img(scene, keys, t, cast=()):
        _, _, eng = build(scene, '9:16', list(keys), list(cast))
        return np.asarray(eng.frame(t).convert('RGB'))

    a1 = img(SCENE, BASE, 5.08); a2 = img(SCENE, BASE + [('eye_smooth', False)], 5.08)
    check('sans la cle et avec "eye_smooth": false : identiques au bit pres', np.array_equal(a1, a2))
    a3 = img(SCENE, BASE + [('eye_smooth', 'snap')], 5.08)
    check('  et avec "eye_smooth": "snap" aussi', np.array_equal(a1, a3))
    b1 = img(SCENE, BASE + [('eye_smooth', 'saccade')], 5.08)
    changed = int((np.abs(a1.astype(np.int16) - b1.astype(np.int16)).sum(2) > 0).sum())
    check('la cle change reellement l\'image', changed > 0, f'{changed} pixels sur {a1.shape[0] * a1.shape[1]}')
    b2 = img(SCENE, BASE + [('eye_smooth', 'saccade')], 5.08)
    check('deterministe : deux rendus identiques au bit pres', np.array_equal(b1, b2))
    # sans "eye_aim", le lissage n'a rien a dessiner : le rendu doit etre inchange au bit pres
    noaim = [('body', 'refit'), ('eyeline', 'smooth')]
    check('sans "eye_aim", la cle ne change pas un bit',
          np.array_equal(img(SCENE, noaim, 5.08), img(SCENE, noaim + [('eye_smooth', 'saccade')], 5.08)))

    print('\n2. le refactoring de timeline.neck() n\'a rien deplace')
    check('les deux limites sont celles d\'avant', (TL.LIM_YAW, TL.LIM_PITCH) == (.95, .45))
    bad = 0; n = 0
    for k, sa in sorted(ac0.shots.items()):
        t = 0.
        while t < sa.dur:
            for aid, sm in sa.sample(float(t)).items():
                n += 1
                yaw, pitch = sm['rig']['head']
                # la boucle d'avant : clamp explicite, etiquette au-dela de 0.45 rad
                want_lbl = ('right' if yaw > 0 else 'left') if abs(yaw) > .45 else None
                if sm.get('gaze') != want_lbl: bad += 1
                if abs(yaw) > TL.LIM_YAW + 1e-12 or abs(pitch) > TL.LIM_PITCH + .06: bad += 1
            t += .25
    check('l\'etiquette gaze et les bornes sont celles de la boucle d\'avant', bad == 0, f'{n} echantillons, {bad} ecart(s)')

    print('\n3. raw_eye() est exactement le residu de sample()')
    bad = 0; n = 0
    for k, sa in sorted(ac0.shots.items()):
        t = 0.
        while t < sa.dur:
            raw = sa.raw_eye(float(t))
            for aid, sm in sa.sample(float(t)).items():
                n += 1
                e = sm.get('eye'); r = raw.get(aid)
                if r is None or e is None or e[0] != r[0] or e[1] != r[1]: bad += 1
            t += .2
    check('meme flottant, au bit pres, sur tous les echantillons', bad == 0, f'{n} echantillons, {bad} ecart(s)')

    print('\n4. ca fait ce que ca dit, sur une vraie scene')
    _, _, ac_on = acting_of(SCENE, BASE + [('eye_smooth', 'saccade')])
    reach = EF.PRESETS['saccade']['reach']
    worst_off = worst_on = 0.
    for k in sorted(ac0.shots):
        for aid in ac0.shots[k].tracks:
            s0 = series(ac0.shots[k], aid); s1 = series(ac_on.shots[k], aid)
            for i in range(1, len(s0)): worst_off = max(worst_off, abs(s0[i][1] - s0[i - 1][1]))
            for i in range(1, len(s1)): worst_on = max(worst_on, abs(s1[i][1] - s1[i - 1][1]))
    check('le pire saut de residu d\'une image a la suivante baisse', worst_on < worst_off * .75,
          'sans %.1f deg -> avec %.1f deg' % (math.degrees(worst_off), math.degrees(worst_on)))
    over = 0; n = 0
    for k in sorted(ac_on.shots):
        for aid in ac_on.shots[k].tracks:
            for (_, v) in series(ac_on.shots[k], aid):
                n += 1
                if abs(v) > reach + 1e-9: over += 1
    check('le residu lisse ne sort jamais de la course de l\'oeil', over == 0, f'{n} echantillons, {over} hors plage')

    print('\n5. une saccade est balistique, monotone, et ne bloque pas une image sur deux')
    sa = ac_on.shots[max(ac_on.shots, key=lambda k: ac_on.shots[k].dur)]
    aid = sorted(sa.tracks)[0]
    ys = sa.eyeflow.table[aid][0]
    dt = sa.eyeflow.dt
    # un pas de grille egal a zero EN PLEINE TRAVERSEE etait le defaut de la premiere version
    stalls = sum(1 for i in range(2, len(ys))
                 if abs(ys[i] - ys[i - 1]) < 1e-12 and abs(ys[i - 1] - ys[i - 2]) > math.radians(1.))
    check('aucun palier d\'une image en pleine traversee', stalls == 0, f'{stalls} palier(s) sur {len(ys)} pas')
    big = [i for i in range(1, len(ys)) if abs(ys[i] - ys[i - 1]) > math.radians(4.)]
    check('la scene contient bien des traversees a mesurer', len(big) > 0, f'{len(big)} pas rapides')
    backs = 0
    for i in big:
        d = ys[i] - ys[i - 1]
        if i + 1 < len(ys) and (ys[i + 1] - ys[i]) * d < -1e-12 and abs(ys[i + 1] - ys[i]) > math.radians(1.):
            backs += 1
    check('une traversee ne repart pas en arriere l\'image suivante', backs == 0, f'{backs} rebond(s)')
    full = EF.PRESETS['saccade']['base'] + EF.PRESETS['saccade']['gain'] * 2 * reach
    check('une traversee complete dure plus de deux images de rendu', full > 2 / 30.,
          '%.0f ms, soit %.1f images' % (full * 1000, full * 30))

    print('\n6. CONSOLE 2D n\'est pas touche')
    c_sc = os.path.join(ROOT, 'examples', 'demos', 'demo5_console.json')
    c0 = img(c_sc, [], 6.); c1 = img(c_sc, [('eye_smooth', 'saccade')], 6.)
    check('une image console est identique au bit pres avec la cle', np.array_equal(c0, c1))
    ep, W = validate({'shots': [{'lines': [0, 0]}], 'eye_smooth': 'saccade'}, 1, 'console')
    check('le validateur refuse la cle en console', 'eye_smooth' not in ep)
    check('  et il le dit en nommant les deux moteurs',
          any('pixel3d' in w and 'console' in w for w in W), ' | '.join(W)[:110])

    print('\n7. la cle est validee en pixel3d')
    ep, W = validate({'shots': [{'lines': [0, 0]}], 'eye_aim': True, 'eye_smooth': 'saccade'}, 1, 'pixel3d')
    check('un preset connu passe', ep.get('eye_smooth') == 'saccade')
    ep, W = validate({'shots': [{'lines': [0, 0]}], 'eye_aim': True, 'eye_smooth': 'coucou'}, 1, 'pixel3d')
    check('un nom inconnu est retire', 'eye_smooth' not in ep)
    check('  et les presets connus sont nommes', any('saccade' in w for w in W), ' | '.join(W)[:110])
    ep, W = validate({'shots': [{'lines': [0, 0]}], 'eye_smooth': 'saccade'}, 1, 'pixel3d')
    check('sans "eye_aim", le validateur previent que rien ne sera dessine',
          ep.get('eye_smooth') == 'saccade' and any('eye_aim' in w for w in W), ' | '.join(W)[:110])
    ep, W = validate({'shots': [{'lines': [0, 0]}], 'eye_aim': True,
                      'eye_smooth': {'style': 'saccade', 'latency': .05}}, 1, 'pixel3d')
    check('un reglage fin passe', isinstance(ep.get('eye_smooth'), dict))
    o = EF.options({'style': 'saccade', 'latency': .05, 'pursuit': .9})
    check('  et il est bien relu', o and abs(o['latency'] - .05) < 1e-9 and abs(o['pursuit'] - .9) < 1e-9)
    check('le preset retenu existe (humain / doux supprimes le 31/10)', sorted(EF.PRESETS) == ['saccade'], ', '.join(sorted(EF.PRESETS)))
    EF.register('essai_check', latency=.3)
    check('un preset peut etre enregistre (registre, pas if/elif)', EF.PRESETS['essai_check']['latency'] == .3)
    EF.PRESETS.pop('essai_check')

    print('\n8. le realisateur IA ne connait pas la cle')
    src = ''
    for f in ('prompts.py', 'heuristic.py'):
        src += open(os.path.join(ROOT, 'hstudio', 'director', f), encoding='utf-8').read()
    check('"eye_smooth" n\'apparait ni dans prompts.py ni dans heuristic.py', 'eye_smooth' not in src)

    print('\n9. le pool de rendu « spawn »')
    check_spawn()

    print(f'\n{OK[0]} OK, {BAD[0]} echec(s)')
    return 1 if BAD[0] else 0


def check_spawn():
    """Le rendu repart dans des processus neufs : la cle doit traverser. Sans ce test, une cle qui ne
    traverserait pas le pool donnerait une video B identique a la video A, et personne ne le verrait."""
    import multiprocessing as mp
    from hstudio import demos, pipeline
    from hstudio.pipeline import duration_of, make_engine

    sc = json.load(open(SCENE, encoding='utf-8'))
    demos.load = lambda _id, _sc=sc: copy.deepcopy(_sc)
    lines = demos.timed_lines(sc['script'], float(sc.get('gap', .3)), float(sc.get('lead', .4)))
    env = demos.draft_voice(sc, lines)[1]
    ep = demos.episode_of(sc, lines, log=lambda *a: None)
    lines = demos.lines_with_meta(ep, lines)
    dur = duration_of(ep, lines)
    base = dict(ep); base.update(body='refit', eyeline='smooth', eye_aim=True)
    ep_on = dict(base); ep_on['eye_smooth'] = 'saccade'
    eng = make_engine('pixel3d', ep_on, lines, env, dur, '9:16')
    names = {k: (sa.eyeflow.opt.get('name') if sa.eyeflow is not None else None)
             for k, sa in eng.ctx.get_acting().shots.items()}
    check('la regie a bien pose un solveur sur chaque plan',
          names and all(v == 'saccade' for v in names.values()), json.dumps(names))
    frames = (152, 153)
    here = [eng.frame(i / 30.).convert('RGB').tobytes() for i in frames]
    off_eng = make_engine('pixel3d', dict(base), lines, env, dur, '9:16')
    off = [off_eng.frame(i / 30.).convert('RGB').tobytes() for i in frames]
    ctx = mp.get_context('spawn')
    with ctx.Pool(2, initializer=pipeline._init_worker, initargs=('pixel3d', ep_on, lines, env, dur, '9:16')) as pool:
        there = list(pool.imap(pipeline._render_one, frames))
    check('deux workers « spawn » rendent les memes octets qu\'ici', there == here,
          'identique' if there == here else 'DIFFERENT : la cle ne traverse pas le pool')
    check('  et ce ne sont pas les octets du rendu sans lissage', there != off)


if __name__ == '__main__': sys.exit(main())
