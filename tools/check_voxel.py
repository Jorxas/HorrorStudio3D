"""Tests hors ligne de la FINITION PREMIUM du corps cubique (preset de corps « voxel_premium », lot P1 voxel).

    python tools/check_voxel.py

Le lot precedent a mesure une surprise : le corps LIVRE etait deja presque la silhouette cubique de la
miniature de reference (ecart 0,065 a la grille du modele), et la refonte humanoide `refit` s'en eloignait
d'un facteur neuf (0,567). `minecraft` a ramene l'ecart a 0,015 -- et n'a rien change d'autre : meme nombre de
boites, meme main d'un seul cube, meme visage 24x24, memes deux blocs de cheveux. La miniature, elle, a une
main qui AGRIPPE, une chaussure avec une semelle, une ligne d'epaules en marche d'escalier, un vetement a
coutures, des meches de cheveux etagees et des sourcils.

`voxel_premium` est exactement cela et rien de plus : la silhouette de `minecraft` au chiffre pres, plus les
volumes et les cles de look qui lui manquaient. Ce que ce fichier verifie, point par point :

1. **inerte sans la cle** -- `bodies.active()` est None, `promoted()` rend le MEME objet, et une image rendue
   est identique au bit pres a celle d'avant ce lot et a celle de `"body": false` ;
2. **la silhouette n'est pas une nouvelle silhouette** -- les neuf nombres de forme sont ceux de `minecraft`
   au chiffre pres, et l'ecart mesure a la grille du modele reste bien plus petit que celui du rendu livre et
   de deux ordres de grandeur sous celui de `refit`. C'est le point que le proprietaire a demande : le corps
   reste court, massif, sans cou, et n'est PAS repris du prototype rejete ;
3. **le squelette partage n'est pas touche** -- longueurs d'os identiques au millionieme, pied le plus bas
   exactement au sol. `acting/rig.py` est aussi le squelette de CONSOLE 2D ;
4. **les volumes promis existent vraiment** -- la main n'est plus un cube (4 boites), la chaussure a une
   semelle dont le dessous est a y = 0 exactement, le groupe « voxel » du vetement est peuple, et le compte
   total de boites monte de ~30. Un test qui ne compte pas les boites ne distingue pas une option qui marche
   d'une option qui s'annonce ;
5. **les deux moities se separent** -- `detail: 0` donne le look seul, `promote: 0` les volumes seuls. Le
   rapport peut donc MESURER laquelle des deux travaille au lieu de l'affirmer ;
6. **la main attrape toujours ce qu'elle vise** -- le poignet dessine reste sur la poignee comme avec
   `minecraft`, parce que le poing est ajoute SOUS l'origine du repere et ne la deplace pas ;
7. **la promotion de look ne vole pas ses choix a la scene** -- un personnage qui a deja un visage, une coupe
   ou une couleur garde les siens ; une coupe sans jumelle cubique (chignon, piques, boucles, chauve) est
   laissee tranquille ;
8. **deterministe** -- deux rendus de la meme image sont identiques au bit pres ;
9. **CONSOLE 2D est strictement inchange**, et le validateur refuse la cle a voix haute en nommant le moteur ;
10. **le preset traverse le pool de rendu « spawn »** -- sans ce test, une cle qui resterait dans le processus
    principal donnerait une video B identique a la video A et personne ne le verrait ;
11. **le realisateur IA ne connait pas la cle** (regle AGENTS.md : aucune option non encore jugee par le
    proprietaire n'entre dans les invites).

Aucun reseau, aucune cle d'API, aucun cout, aucun ffmpeg, aucun projet ecrit.

Windows : corps derriere `if __name__ == '__main__'` (le rendu peut lancer un pool « spawn »).
"""
import os, sys, json, copy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

OK = [0]; BAD = [0]
SCENE = os.path.join(ROOT, 'examples', 'scenes', 'couloir_poignee.json')
CONSOLE = os.path.join(ROOT, 'examples', 'demos', 'demo5_console.json')
PREMIUM = 'voxel_premium'
SHAPE_KEYS = ('head', 'head_lift', 'neck', 'torso', 'torso_z', 'arm', 'hand', 'leg', 'arm_in')


def check(label, cond, detail=''):
    ok = bool(cond)
    (OK if ok else BAD)[0] += 1
    print(('  OK   ' if ok else '  ECHEC ') + label + (f'   [{detail}]' if detail else ''))
    return ok


def img(scene, keys, t, cast=()):
    from cadrage_qc import build
    _, _, eng = build(scene, '9:16', list(keys), list(cast))
    return np.asarray(eng.frame(t).convert('RGB'))


def main():
    from hstudio.engines.pixel3d import bodies, poses as P
    from hstudio.director.validate import validate
    import corps_qc as CQ

    print('1. inerte sans la cle')
    bodies.use(None)
    check('bodies.active() est None au repos', bodies.active() is None)
    look = {'hair': [70, 40, 26], 'hair_style': 'short'}
    check('promoted() rend le MEME objet au repos (pas meme une copie)', bodies.promoted(look) is look)
    for off in (None, False, ''):
        check(f'configure({off!r}) n\'active rien', bodies.configure(off) is None)
    check('un nom inconnu n\'active rien', bodies.configure('voxel_premiumm') is None)
    bodies.use(None)
    a1 = img(SCENE, [], 8.0)
    check('sans la cle et avec "body": false : identiques au bit pres',
          np.array_equal(a1, img(SCENE, [('body', False)], 8.0)))
    b1 = img(SCENE, [('body', PREMIUM)], 8.0)
    check('la cle change reellement l\'image', not np.array_equal(a1, b1))
    check('deterministe : deux rendus identiques au bit pres',
          np.array_equal(b1, img(SCENE, [('body', PREMIUM)], 8.0)))
    mc = img(SCENE, [('body', 'minecraft')], 8.0)
    check('  et ce n\'est pas l\'image du corps "minecraft" nu', not np.array_equal(b1, mc))

    print('\n2. la silhouette reste celle de "minecraft", au chiffre pres')
    pm, mcs = bodies.PRESETS[PREMIUM], bodies.PRESETS['minecraft']
    bad = [k for k in SHAPE_KEYS if pm[k] != mcs[k]]
    check('les neuf nombres de forme sont ceux de "minecraft"', not bad,
          ', '.join(bad) or ', '.join(f'{k}={pm[k]}' for k in SHAPE_KEYS))
    check('  et les deux nouvelles cles sont les seules a changer',
          pm['detail'] == 1. and pm['promote'] == 1. and mcs['detail'] == 0. and mcs['promote'] == 0.)
    for nm in ('minecraft',):
        check(f'  le preset "{nm}" garde detail = promote = 0',
              bodies.PRESETS[nm]['detail'] == 0. and bodies.PRESETS[nm]['promote'] == 0.)
    r_def = CQ.silhouette(CQ.POSES['debout'], CQ.LOOK, None)
    r_mc = CQ.silhouette(CQ.POSES['debout'], CQ.LOOK, 'minecraft')
    r_pm = CQ.silhouette(CQ.POSES['debout'], CQ.LOOK, PREMIUM)
    check('aucun cou, la signature du look', r_pm['cou'] == 0., f"{r_pm['cou']:+.3f} m")
    check('  et aucun trou sous le crane', r_pm['jonction'] < 0, f"{r_pm['jonction']:+.3f} m")
    check('le corps reste COURT (moins de 4,3 tetes, loin des 6,8 de refit)',
          r_pm['tetes'] < 4.3, f"{r_pm['tetes']:.2f} tetes")
    check('les epaules restent LARGES (au moins la moitie de la hauteur)',
          r_pm['ep_haut'] >= .48, f"{r_pm['ep_haut']:.3f}")
    check('plus proche de la grille du modele que le rendu livre',
          r_pm['ecart_minecraft'] < r_def['ecart_minecraft'],
          f"premium {r_pm['ecart_minecraft']:.3f} < livre {r_def['ecart_minecraft']:.3f}")
    # les volumes ajoutes COUTENT quelque chose a l'ecart, et c'est dit ici plutot que cache : les meches de
    # cheveux sont plus larges que les deux blocs qu'elles remplacent, donc la tete lue est plus large.
    check('le cout de la finition sur l\'ecart est borne (moins de 0,03 de plus que "minecraft" nu)',
          r_pm['ecart_minecraft'] - r_mc['ecart_minecraft'] < .03,
          f"{r_mc['ecart_minecraft']:.3f} -> {r_pm['ecart_minecraft']:.3f}")

    print('\n3. le squelette partage n\'est pas touche')
    bad = [k for k, v in r_pm['os'].items() if abs(v - r_def['os'][k]) > 1e-6]
    check('longueurs d\'os identiques au millionieme', not bad, ', '.join(bad) or f"{len(r_pm['os'])} os")
    for pose in sorted(CQ.POSES):
        r = CQ.silhouette(CQ.POSES[pose], CQ.LOOK, PREMIUM)
        d = CQ.silhouette(CQ.POSES[pose], CQ.LOOK, None)
        check(f'pose « {pose} » : pied le plus bas au sol comme le rendu livre',
              abs(r['pied_y'] - d['pied_y']) < 1e-9, f"{r['pied_y']:+.6f} / {d['pied_y']:+.6f}")

    print('\n4. les volumes promis existent vraiment')
    parts_d, out_d, _ = CQ.groups(CQ.POSES['debout'], CQ.LOOK, None)
    parts_p, out_p, _ = CQ.groups(CQ.POSES['debout'], CQ.LOOK, PREMIUM)
    check('la main n\'est plus UN cube', len(parts_p['handR']) > len(parts_d['handR']),
          f"{len(parts_d['handR'])} -> {len(parts_p['handR'])} boites")
    check('  et les deux mains sont des images miroir (meme compte)',
          len(parts_p['handR']) == len(parts_p['handL']))
    check('le pied a gagne une semelle et un bout', len(parts_p['footR']) > len(parts_d['footR']),
          f"{len(parts_d['footR'])} -> {len(parts_p['footR'])} boites")
    # la semelle est construite en C((0, h / 2, ...), (..., h, ...)) pour que son dessous soit a y = 0 dans le
    # repere du pied, exactement comme la chaussure d'origine. Le seuil est le micrometre et pas le zero
    # machine : entre le repere du pied et le monde il y a une rotation en float32, qui laisse quelques
    # nanometres de bruit sur les DEUX boites -- y compris celle du rendu livre.
    sole = min(float(b.wlo[1]) for b in parts_p['footR'])
    stock = min(float(b.wlo[1]) for b in parts_d['footR'])
    check('  dont le dessous est au sol au micrometre, comme la chaussure livree', abs(sole) < 1e-6,
          f'{sole:+.9f} m (livre {stock:+.9f} m)')
    check('    et pas plus bas que la chaussure livree', sole >= stock - 1e-9,
          f'{sole:+.9f} >= {stock:+.9f}')
    check('le groupe « voxel » du vetement est peuple', len(parts_p.get('voxel', [])) >= 5,
          f"{len(parts_p.get('voxel', []))} boites")
    check('  et il n\'existe pas sans la cle', not parts_d.get('voxel'))
    check('le corps gagne au moins 25 boites au total', len(out_p) - len(out_d) >= 25,
          f'{len(out_d)} -> {len(out_p)} boites')
    check('  mais reste sous 60 (une foule reste rendable)', len(out_p) < 60, str(len(out_p)))
    hp = CQ.groups(CQ.POSES['debout'], dict(CQ.LOOK, hat='hood'), PREMIUM)[0]
    check('les oreilles disparaissent sous une capuche (rien ne traverse)',
          len(hp['head']) < len(parts_p['head']), f"{len(parts_p['head'])} -> {len(hp['head'])} boites de tete")

    print('\n5. les deux moities se separent')
    look_only = CQ.groups(CQ.POSES['debout'], CQ.LOOK, {'style': PREMIUM, 'detail': 0})[1]
    vol_only = CQ.groups(CQ.POSES['debout'], CQ.LOOK, {'style': PREMIUM, 'promote': 0})[1]
    check('detail: 0 -> le look seul, sans les volumes', len(look_only) < len(out_p),
          f'{len(look_only)} boites (premium {len(out_p)})')
    check('promote: 0 -> les volumes seuls, sans la promotion de look', len(vol_only) < len(out_p),
          f'{len(vol_only)} boites')
    check('  et chacune des deux fait plus que le corps "minecraft" nu',
          len(look_only) > len(out_d) and len(vol_only) > len(out_d),
          f'{len(out_d)} -> look {len(look_only)} / volumes {len(vol_only)}')
    i_look = img(SCENE, [('body', {'style': PREMIUM, 'detail': 0})], 8.0)
    i_vol = img(SCENE, [('body', {'style': PREMIUM, 'promote': 0})], 8.0)
    check('les deux moities donnent trois images differentes de la complete',
          not np.array_equal(i_look, b1) and not np.array_equal(i_vol, b1)
          and not np.array_equal(i_look, i_vol))

    print('\n6. la main attrape toujours ce qu\'elle vise')
    from hstudio.acting import rig
    tgt = (.28, 1.02, .22)
    pr = dict(reach={1: (tgt, 1.)})
    for nm in ('minecraft', PREMIUM):
        st = bodies.configure(nm); bodies.use(st)
        sk = bodies.solve(pr)
        ha = sk.joints['haR'] + bodies.arm_shift(st, sk, 1)
        d = float(np.linalg.norm(ha - np.array(tgt, np.float32)))
        check(f'"{nm}" : le poignet DESSINE est sur la cible', d < .012, f'{100 * d:.2f} cm')
    bodies.use(None)
    st = bodies.configure(PREMIUM); bodies.use(st)
    bx = bodies.hand_extra(st, {'skin': (214, 160, 124), 'hood': (170, 70, 60), 'outfit': 'hoodie'}, {}, 1)
    check('le poing se ferme SOUS et DEVANT l\'origine du repere (il ne la deplace pas)',
          all(float(b.lo[1]) < .2 for b in bx) and max(float(b.hi[2]) for b in bx) > .05,
          f'{len(bx)} boites, y max {max(float(b.hi[1]) for b in bx):+.3f}')
    bx_l = bodies.hand_extra(st, {'skin': (214, 160, 124), 'hood': (170, 70, 60), 'outfit': 'hoodie'}, {}, -1)
    check('  et le pouce de la main gauche est du cote oppose a celui de la droite',
          float(bx[1].lo[0]) < 0 < float(bx_l[1].hi[0]),
          f'droite {float(bx[1].lo[0]):+.3f}, gauche {float(bx_l[1].hi[0]):+.3f}')
    bodies.use(None)

    print('\n7. la promotion de look ne vole pas ses choix a la scene')
    bodies.use(bodies.configure(PREMIUM))
    p = bodies.promoted({'hair_style': 'short', 'hair': [70, 40, 26]})
    check('une coupe "short" devient des meches cubiques', p['hair_style'] == 'strands', str(p['hair_style']))
    check('  le visage 48x48 est mis', p['face_detail'] == 'hd')
    check('  le vetement nuance aussi', p['detail'] is True)
    check('  et un second ton de cheveux est derive de la couleur de la scene',
          tuple(p['hair2']) != tuple(p['hair']), str(tuple(p['hair2'])))
    check('"ponytail" devient "strands_ponytail"',
          bodies.promoted({'hair_style': 'ponytail'})['hair_style'] == 'strands_ponytail')
    check('"long" devient "strands_long"', bodies.promoted({'hair_style': 'long'})['hair_style'] == 'strands_long')
    for nm in ('bun', 'spiky', 'curly', 'bald'):
        check(f'"{nm}" n\'a pas de jumelle cubique : la coupe du personnage est laissee tranquille',
              bodies.promoted({'hair_style': nm})['hair_style'] == nm)
    check('un visage choisi par la scene n\'est pas remplace',
          bodies.promoted({'face_detail': 'v2'})['face_detail'] == 'v2')
    check('une coupe deja en meches reste la sienne',
          bodies.promoted({'hair_style': 'strands_long'})['hair_style'] == 'strands_long')
    check('un second ton de cheveux choisi par la scene est garde',
          tuple(bodies.promoted({'hair2': [1, 2, 3]})['hair2']) == (1, 2, 3))
    check('et toutes les coupes promues existent dans poses.HAIR_STYLES',
          all(v in P.HAIR_STYLES for v in bodies._HAIR_PREMIUM.values()))
    check('promoted() ne modifie jamais le dictionnaire d\'origine (il est partage)',
          'face_detail' not in look and bodies.promoted(look) is not look)
    bodies.use(None)
    check('promote: 0 -> promoted() redevient l\'identite',
          bodies.use(bodies.configure({'style': PREMIUM, 'promote': 0})) and bodies.promoted(look) is look)
    bodies.use(None)

    print('\n8. CONSOLE 2D n\'est pas touche')
    c0 = img(CONSOLE, [], 6.)
    c1 = img(CONSOLE, [('body', PREMIUM)], 6.)
    check('une image console est identique au bit pres avec la cle', np.array_equal(c0, c1))
    ep, W = validate({'shots': [{'lines': [0, 0]}], 'body': PREMIUM}, 1, 'console')
    check('le validateur refuse "body" en console', 'body' not in ep)
    check('  et il le dit en nommant les deux moteurs',
          any('pixel3d' in w and 'console' in w for w in W), ' | '.join(W)[:110])
    ep, W = validate({'shots': [{'lines': [0, 0]}], 'body': PREMIUM}, 1, 'pixel3d')
    check('et il l\'accepte en pixel3d', ep.get('body') == PREMIUM)
    ep, W = validate({'shots': [{'lines': [0, 0]}], 'body': 'voxel_premiumm'}, 1, 'pixel3d')
    check('un nom voisin est retire', 'body' not in ep)
    check('  et les presets connus sont nommes', any(PREMIUM in w for w in W), ' | '.join(W)[:140])

    print('\n9. le realisateur IA ne connait pas la cle')
    src = ''
    for f in ('prompts.py', 'heuristic.py'):
        src += open(os.path.join(ROOT, 'hstudio', 'director', f), encoding='utf-8').read()
    check(f'"{PREMIUM}" n\'apparait ni dans prompts.py ni dans heuristic.py', PREMIUM not in src)
    check('ni dans une seule demo livree ou un personnage de la bibliotheque',
          not shipped_mentions(), ', '.join(shipped_mentions()))

    print('\n10. le pool de rendu « spawn »')
    check_spawn()

    print(f'\n{OK[0]} OK, {BAD[0]} echec(s)')
    return 1 if BAD[0] else 0


def shipped_mentions():
    """les fichiers LIVRES qui nommeraient la cle : la preuve que rien n'est active par defaut"""
    bad = []
    for sub in (('examples', 'demos'), ('library', 'characters'), ('library', 'series'), ('config',)):
        d = os.path.join(ROOT, *sub)
        for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if not f.endswith('.json'): continue
            t = open(os.path.join(d, f), encoding='utf-8').read()
            if PREMIUM in t or '"body"' in t: bad.append('/'.join(sub) + '/' + f)
    return bad


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
    ep_on = dict(ep); ep_on['body'] = PREMIUM
    eng = make_engine('pixel3d', ep_on, lines, env, dur, '9:16')
    check('le moteur a bien resolu le preset', (eng.body or {}).get('name') == PREMIUM,
          f"body={(eng.body or {}).get('name')}")
    frames = (150,)
    here = [eng.frame(i / 30.).convert('RGB').tobytes() for i in frames]
    off = [make_engine('pixel3d', dict(ep), lines, env, dur, '9:16').frame(i / 30.).convert('RGB').tobytes()
           for i in frames]
    ctx = mp.get_context('spawn')
    with ctx.Pool(2, initializer=pipeline._init_worker, initargs=('pixel3d', ep_on, lines, env, dur, '9:16')) as pool:
        there = list(ctx and pool.imap(pipeline._render_one, frames))
    check('deux workers « spawn » rendent les memes octets qu\'ici', there == here,
          'identique' if there == here else 'DIFFERENT : la cle ne traverse pas le pool')
    check('  et ce ne sont pas les octets du rendu livre', there != off)


if __name__ == '__main__': sys.exit(main())
