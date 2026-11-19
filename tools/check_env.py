"""Tests hors ligne des facades detaillees (cle d'episode « env », engines/pixel3d/facades.py).

    python tools/check_env.py

Ce que ca verifie, et pourquoi chaque point est la :

1. **inerte sans la cle** -- `facades.active()` est None, `tex()` rend None, `ppm()` vaut le 4 livre, et une
   image rendue est identique **au bit pres** a celle d'avant. C'est ce qui protege les trois suites de
   non-regression ;
2. **le cinquieme canal fait ce qu'il dit** -- une texture a 5 canaux emet par son canal 4 et NON par son
   alpha, sinon un appui de fenetre en pierre brillerait aussi fort que la vitre allumee a cote. Une
   texture a 4 canaux garde exactement l'ancien comportement ;
3. **la texture contient vraiment ce qu'elle annonce** -- des encadrements, des vitres allumees, des portes
   au rez-de-chaussee, des tuyaux ; et surtout **AUCUNE emission** en dehors du verre et des lampes ;
4. **la luminosite du mur est conservee** -- la texture est opaque alors que l'ancienne laissait passer la
   couleur du bloc. Si elle ne retombait pas sur la meme luminance, la paire A/B serait biaisee par un
   simple assombrissement et ne prouverait plus rien ;
5. **ca ajoute reellement des texels la ou il y a des batiments, et RIEN ailleurs** -- la rue passe de 9 a
   16 murs textures, la foret reste a zero des deux cotes (c'est le controle negatif du lot) ;
6. **les immeubles de `city_street` recoivent une facade** -- ils etaient des boites peintes sans une seule
   fenetre, et c'est la forme la plus pure du « batiment generique » ;
7. **ca ne coute rien par image** -- la texture est construite une fois et mise en cache ; le rendu ne fait
   qu'une lecture de texture dans les deux cas ;
8. **CONSOLE 2D n'est pas touche** et le validateur refuse la cle en nommant les deux moteurs ;
9. **la cle est validee**, un nom inconnu n'active rien, un reglage fin est borne ;
10. **le realisateur IA ne connait pas la cle** (regle AGENTS.md) ;
11. **deterministe, et ca traverse le pool de rendu « spawn »**.

Aucun reseau, aucune cle d'API, aucun cout, aucun ffmpeg, aucun projet ecrit.

Windows : corps derriere `if __name__ == '__main__'` (le rendu peut lancer un pool « spawn »).
"""
import os, sys, json, copy, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

OK = [0]; BAD = [0]
RUE = os.path.join(ROOT, 'examples', 'scenes', 'rue_entree.json')
FORET = os.path.join(ROOT, 'examples', 'scenes', 'foret_neige.json')
CONSOLE = os.path.join(ROOT, 'examples', 'demos', 'demo5_console.json')
W_LUM = np.array([.30, .59, .11], np.float32)


def check(label, cond, detail=''):
    ok = bool(cond)
    (OK if ok else BAD)[0] += 1
    print(('  OK   ' if ok else '  ECHEC ') + label + (f'   [{detail}]' if detail else ''))
    return ok


def img(scene, keys, t):
    from cadrage_qc import build
    _, _, eng = build(scene, '9:16', list(keys))
    return np.asarray(eng.frame(t).convert('RGB'))


def walls(scene, keys):
    """(murs textures, texels de facade, boites) du decor d'une scene"""
    from cadrage_qc import build
    ep, lines, eng = build(scene, '9:16', list(keys))
    sc = eng.ctx.get_set(ep.get('default_set')).scene({}, 0., 0.)
    n = sum(1 for b in sc.boxes if getattr(b, 'tex', None))
    px = int(sum(sum(t.shape[0] * t.shape[1] for t in b.tex.values())
                 for b in sc.boxes if getattr(b, 'tex', None)))
    return n, px, len(sc.boxes)


def main():
    from hstudio.engines.pixel3d import facades as FA, r3d
    from hstudio.engines.pixel3d.compose import facade_tex, STYLES
    from hstudio.director.validate import validate

    print('1. inerte sans la cle')
    FA.use(None)
    check('facades.active() est None au repos', FA.active() is None)
    check('ppm() rend le 4 livre', FA.ppm() == 4)
    check('tex() rend None', FA.tex(9., 12., 'brick', .3, 1, True, 2) is None)
    check('cap() rend les bornes livrees', FA.cap() == (320, 640), str(FA.cap()))
    for off in (None, False, ''):
        check(f'configure({off!r}) n\'active rien', FA.configure(off) is None)
    check('un nom inconnu n\'active rien', FA.configure('coucou') is None)
    FA.use(None)
    a1 = img(RUE, [], 1.2)
    check('sans la cle et avec "env": false : identiques au bit pres',
          np.array_equal(a1, img(RUE, [('env', False)], 1.2)))
    b1 = img(RUE, [('env', 'riche')], 1.2)
    changed = int((np.abs(a1.astype(np.int16) - b1.astype(np.int16)).sum(2) > 0).sum())
    check('la cle change reellement l\'image', changed > 20000,
          f'{changed} pixels sur {a1.shape[0] * a1.shape[1]}')
    check('deterministe : deux rendus identiques au bit pres',
          np.array_equal(b1, img(RUE, [('env', 'riche')], 1.2)))

    print('\n2. le cinquieme canal : l\'emission n\'est plus l\'alpha')
    from hstudio.engines.pixel3d.r3d import Box
    t5 = np.zeros((4, 4, 5), np.uint8); t5[..., :4] = 255; t5[1, 1, 4] = 255
    t4 = np.zeros((4, 4, 4), np.uint8); t4[...] = 255
    check('une texture a 5 canaux est acceptee par Box', Box((0, 0, 0), (1, 1, 1), (9, 9, 9), tex={'+z': t5}) is not None)
    FA.configure('riche')
    tx = FA.tex(9.7, 16.0, 'brick', .35, 7, True, 2, (110, 84, 74))
    check('la facade riche a bien 5 canaux', tx.shape[2] == 5, str(tx.shape))
    opaque = tx[..., 3] == 255
    check('  et elle est entierement opaque (le mur est dessine, pas laisse transparent)',
          opaque.all(), f'{100 * opaque.mean():.1f} % opaques')
    em = tx[..., 4]
    check('  des texels emettent (des vitres allumees)', (em > 0).any(), f'{(em > 0).sum()} texels')
    check('  mais une petite minorite : le mur ne brille pas', (em > 0).mean() < .22,
          f'{100 * (em > 0).mean():.1f} % de la facade')
    # les texels emissifs doivent etre clairs : une pierre sombre qui brille serait le defaut a eviter
    lum = (tx[..., :3].astype(np.float32) * W_LUM).sum(-1)
    check('  et ce sont les texels CLAIRS qui emettent (du verre, pas de la pierre)',
          float(lum[em > 0].mean()) > float(lum[em == 0].mean()) + 40,
          f'{lum[em > 0].mean():.0f} contre {lum[em == 0].mean():.0f}')
    check('la facade livree reste a 4 canaux (rien ne change pour elle)',
          facade_tex(9.7, 16.0, 'brick', .35, 7, True, 2).shape[2] == 4)

    print('\n3. la texture contient ce qu\'elle annonce')
    for preset, want in (('riche_rapide', 8), ('riche', 12), ('riche_max', 18)):
        st = FA.configure(preset)
        check(f'preset "{preset}" : {want} texels/m', st and st['ppm'] == want, str(st and st['ppm']))
    FA.configure('riche')
    big = FA.tex(9.7, 16.0, 'brick', .35, 7, True, 2, (110, 84, 74))
    small = facade_tex(9.7, 16.0, 'brick', .35, 7, True, 2)
    check('la facade riche a bien plus de texels que la livree',
          big.shape[0] * big.shape[1] > 8 * small.shape[0] * small.shape[1],
          f'{big.shape[1]}x{big.shape[0]} contre {small.shape[1]}x{small.shape[0]}')
    # Le rez-de-chaussee contient-il des portes ? Compter des texels « bruns » ne le dit PAS -- un mur de
    # brique est brun, et la premiere version de ce test mesurait le mur, pas la porte (85,9 % contre
    # 79,2 % : aucun pouvoir de discrimination). Ce qui identifie une porte sans ambiguite, c'est la
    # couleur exacte de son encadrement de pierre, qui n'est dessinee nulle part ailleurs sur la facade.
    SURROUND = np.array([176, 168, 152])

    def surrounds(t):
        band = t[int(t.shape[0] * .80):, :, :3].astype(np.int16)
        return int((np.abs(band - SURROUND).sum(-1) < 12).sum())

    n_door = surrounds(big)
    check('le rez-de-chaussee contient des portes (encadrements de pierre)', n_door > 20,
          f"{n_door} texels d'encadrement dans la bande basse")
    FA.configure('dense_seul')
    flat = FA.tex(9.7, 16.0, 'brick', .35, 7, True, 2, (110, 84, 74))
    check('  et "dense_seul" (doors: false) n\'en met aucune', surrounds(flat) == 0,
          f"{surrounds(flat)} texels d'encadrement")
    check('  les deux rez-de-chaussee different donc reellement',
          not np.array_equal(big[int(big.shape[0] * .80):], flat[int(flat.shape[0] * .80):]))
    FA.configure('riche')
    check('un style sans fenetre (rock) ne dessine ni vitre ni porte',
          not (FA.tex(9., 12., 'rock', .3, 2, True, 2, (104, 96, 86))[..., 4] > 0).any())

    print('\n4. la luminosite du mur est conservee (sinon l\'A/B est biaise)')
    for style, body in (('brick', (110, 84, 74)), ('old', (124, 84, 74)), ('concrete', (88, 80, 72))):
        t = FA.tex(9.7, 16.0, style, .35, 7, True, 2, body)
        lw = float((t[..., :3].astype(np.float32) * W_LUM).sum(-1).mean())
        lb = float((np.array(body, np.float32) * W_LUM).sum())
        check(f'  {style}: le mur retombe sur la luminance du bloc', abs(lw - lb) < 12.,
              f'{lw:.1f} contre {lb:.1f} (ecart {lw - lb:+.1f})')
    # deux couleurs de bloc differentes doivent donner deux murs differents : sinon la rue redevient generique
    t1 = FA.tex(9.7, 16.0, 'brick', .35, 7, True, 2, (150, 120, 100))
    t2 = FA.tex(9.7, 16.0, 'brick', .35, 7, True, 2, (90, 86, 84))
    check('deux couleurs de bloc donnent deux murs differents', not np.array_equal(t1[..., :3], t2[..., :3]))
    check('  et deux graines donnent deux facades differentes',
          not np.array_equal(FA.tex(9.7, 16.0, 'brick', .35, 7, True, 2, (110, 84, 74))[..., :3],
                             FA.tex(9.7, 16.0, 'brick', .35, 9, True, 2, (110, 84, 74))[..., :3]))
    FA.use(None)

    print('\n5. des texels la ou il y a des batiments, et rien ailleurs')
    na, pa, _ = walls(RUE, [])
    nb, pb, _ = walls(RUE, [('env', 'riche')])
    check('la rue gagne des murs textures', nb > na, f'{na} -> {nb} murs')
    check('  et beaucoup plus de texels', pb > 8 * pa, f'{pa} -> {pb} texels')
    fa, fpa, _ = walls(FORET, [])
    fb, fpb, _ = walls(FORET, [('env', 'riche')])
    check('la foret n\'a aucun mur texture, avec ou sans la cle (controle negatif)',
          fa == fb == 0 and fpa == fpb == 0, f'A {fa}/{fpa}, B {fb}/{fpb}')
    check('  donc la cle y est strictement sans effet, au bit pres',
          np.array_equal(img(FORET, [], 1.2), img(FORET, [('env', 'riche')], 1.2)))

    print('\n6. les immeubles de city_street recoivent une facade')
    from hstudio.engines.pixel3d.sets import make_set
    spec = {'type': 'city_street', 'seed': 5, 'sky': 'night'}
    FA.use(None)
    s0 = make_set('rue', dict(spec)).scene({}, 0., 0.)
    FA.configure('riche')
    s1 = make_set('rue', dict(spec)).scene({}, 0., 0.)
    n0 = sum(1 for b in s0.boxes if getattr(b, 'tex', None))
    n1 = sum(1 for b in s1.boxes if getattr(b, 'tex', None))
    check('ils passaient sans une seule fenetre, ils en ont maintenant', n1 > n0, f'{n0} -> {n1} murs textures')
    check('  et le nombre de boites ne change pas (aucune geometrie ajoutee)',
          len(s0.boxes) == len(s1.boxes), f'{len(s0.boxes)} / {len(s1.boxes)}')
    FA.use(None)

    print('\n7. ca ne coute rien par image')
    FA.configure('riche')
    FA._tex.cache_clear()
    t0 = time.perf_counter(); FA.tex(9.7, 16.0, 'brick', .35, 7, True, 2, (110, 84, 74)); build_ms = 1000 * (time.perf_counter() - t0)
    t0 = time.perf_counter(); FA.tex(9.7, 16.0, 'brick', .35, 7, True, 2, (110, 84, 74)); cache_ms = 1000 * (time.perf_counter() - t0)
    check('la construction est payee une fois, la relecture est gratuite', cache_ms < build_ms / 50.,
          f'construction {build_ms:.1f} ms, relecture {cache_ms:.3f} ms')
    FA.use(None)

    print('\n8. CONSOLE 2D n\'est pas touche')
    c0 = img(CONSOLE, [], 6.); c1 = img(CONSOLE, [('env', 'riche')], 6.)
    check('une image console est identique au bit pres avec la cle', np.array_equal(c0, c1))
    ep, W = validate({'shots': [{'lines': [0, 0]}], 'env': 'riche'}, 1, 'console')
    check('le validateur refuse la cle en console', 'env' not in ep)
    check('  et il le dit en nommant les deux moteurs',
          any('pixel3d' in w and 'console' in w for w in W), ' | '.join(W)[:110])

    print('\n9. la cle est validee en pixel3d')
    ep, W = validate({'shots': [{'lines': [0, 0]}], 'env': 'riche'}, 1, 'pixel3d')
    check('un preset connu passe', ep.get('env') == 'riche')
    ep, W = validate({'shots': [{'lines': [0, 0]}], 'env': 'coucou'}, 1, 'pixel3d')
    check('un nom inconnu est retire', 'env' not in ep)
    check('  et les presets connus sont nommes', any('riche_rapide' in w for w in W), ' | '.join(W)[:110])
    st = FA.configure({'style': 'riche', 'ppm': 99})
    check('un ppm demesure est borne a 24', st and st['ppm'] == 24, str(st and st['ppm']))
    st = FA.configure({'style': 'riche', 'ppm': 1})
    check('  et un ppm nul est borne a 4', st and st['ppm'] == 4, str(st and st['ppm']))
    st = FA.configure({'style': 'riche', 'doors': False})
    check('doors peut etre coupe', st and st['doors'] is False)
    check('les quatre presets existent',
          sorted(FA.PRESETS) == ['dense_seul', 'riche', 'riche_max', 'riche_rapide'], ', '.join(sorted(FA.PRESETS)))
    FA.register('essai_check', ppm=6)
    check('un preset peut etre enregistre (registre, pas if/elif)', FA.PRESETS['essai_check']['ppm'] == 6)
    FA.PRESETS.pop('essai_check')
    FA.use(None)

    print('\n10. le realisateur IA ne connait pas la cle')
    src = ''
    for f in ('prompts.py', 'heuristic.py'):
        src += open(os.path.join(ROOT, 'hstudio', 'director', f), encoding='utf-8').read()
    check('"env" n\'apparait ni dans prompts.py ni dans heuristic.py',
          '"env"' not in src and "'env'" not in src)
    check('"riche" non plus', 'riche' not in src)

    print('\n11. le pool de rendu « spawn »')
    check_spawn()

    print(f'\n{OK[0]} OK, {BAD[0]} echec(s)')
    return 1 if BAD[0] else 0


def check_spawn():
    """Le rendu repart dans des processus neufs : la cle doit traverser. Sans ce test, une cle qui ne
    traverserait pas le pool donnerait une video B identique a la video A, et personne ne le verrait."""
    import multiprocessing as mp
    from hstudio import demos, pipeline
    from hstudio.pipeline import duration_of, make_engine

    sc = json.load(open(RUE, encoding='utf-8'))
    demos.load = lambda _id, _sc=sc: copy.deepcopy(_sc)
    lines = demos.timed_lines(sc['script'], float(sc.get('gap', .3)), float(sc.get('lead', .4)))
    env = demos.draft_voice(sc, lines)[1]
    ep = demos.episode_of(sc, lines, log=lambda *a: None)
    lines = demos.lines_with_meta(ep, lines)
    dur = duration_of(ep, lines)
    ep_on = dict(ep); ep_on['env'] = 'riche'
    eng = make_engine('pixel3d', ep_on, lines, env, dur, '9:16')
    check('le moteur a bien resolu le preset', (eng.env or {}).get('name') == 'riche',
          str((eng.env or {}).get('name')))
    frames = (36,)
    here = [eng.frame(i / 30.).convert('RGB').tobytes() for i in frames]
    off = [make_engine('pixel3d', dict(ep), lines, env, dur, '9:16').frame(i / 30.).convert('RGB').tobytes()
           for i in frames]
    ctx = mp.get_context('spawn')
    with ctx.Pool(2, initializer=pipeline._init_worker, initargs=('pixel3d', ep_on, lines, env, dur, '9:16')) as pool:
        there = list(pool.imap(pipeline._render_one, frames))
    check('deux workers « spawn » rendent les memes octets qu\'ici', there == here,
          'identique' if there == here else 'DIFFERENT : la cle ne traverse pas le pool')
    check('  et ce ne sont pas les octets du rendu livre', there != off)


if __name__ == '__main__': sys.exit(main())
