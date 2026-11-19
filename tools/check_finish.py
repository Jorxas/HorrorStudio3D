"""Tests hors ligne du prototype Minecraft : la finition d'image (cle « finish ») et le corps cubique
(preset de corps « minecraft »).

    python tools/check_finish.py

Ce que ca verifie, et pourquoi chaque point est la :

1. **inerte sans les cles** -- `finish.active()` est None, `scale()` vaut 1, `levels()` rend None (« garde ton
   defaut »), le filtre est NEAREST, et une image rendue est identique **au bit pres** a celle d'avant. C'est
   ce qui protege les trois suites de non-regression ;
2. **`r3d.configure` est idempotent et reversible** -- il ne reconstruit ses tables par pixel que quand le
   raster change vraiment (il est appele a chaque image et a chaque echantillon du controle qualite), et
   repasser a x1 rend exactement le raster livre ;
3. **la cle fait ce qu'elle dit** -- le raster natif est bien multiplie, l'image finale reste 1080x1920, et
   le nombre de paires de pixels voisins egales s'effondre (c'est la signature arithmetique de
   l'agrandissement x5 au plus proche voisin : 4 pixels sur 5) ;
4. **le corps « minecraft » vise la grille du modele de reference, et c'est mesure** -- tete aussi large que
   le torse, aucun cou, epaules a la moitie de la hauteur, 4 tetes de haut ; et il est PLUS proche de cette
   reference que le rendu livre, la ou `refit` en est beaucoup plus loin ;
5. **le squelette partage n'est pas touche** -- longueurs d'os identiques au millionieme, pieds au sol :
   `acting/rig.py` est aussi le squelette de CONSOLE 2D ;
6. **CONSOLE 2D n'est pas touche** -- une image console avec les deux cles est identique au bit pres a la
   meme sans, et le validateur les refuse en nommant les deux moteurs ;
7. **les cles sont validees** -- un nom inconnu n'active rien, un reglage fin est borne, `arm_in` est la
   seule valeur signee et elle accepte le negatif (une epaule plus LARGE que le torse) ;
8. **le realisateur IA ne connait pas les cles** (regle AGENTS.md) ;
9. **deterministe, et ca traverse le pool de rendu « spawn »** -- sans ce test, une video B identique a la
   video A passerait inapercue.

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


def check(label, cond, detail=''):
    ok = bool(cond)
    (OK if ok else BAD)[0] += 1
    print(('  OK   ' if ok else '  ECHEC ') + label + (f'   [{detail}]' if detail else ''))
    return ok


def img(scene, keys, t, cast=()):
    from cadrage_qc import build
    _, _, eng = build(scene, '9:16', list(keys), list(cast))
    return np.asarray(eng.frame(t).convert('RGB'))


def flat_pairs(a):
    return float(np.all(a[:, 1:] == a[:, :-1], axis=-1).mean())


def main():
    from hstudio.engines.pixel3d import finish as FIN, r3d, bodies
    from hstudio.director.validate import validate
    from PIL import Image

    print('1. inerte sans les cles')
    FIN.use(None)
    check('finish.active() est None au repos', FIN.active() is None)
    check('scale() vaut 1', FIN.scale() == 1)
    check('levels(d) rend None (« garde ton defaut »)', FIN.levels((12, 5, 20.)) is None)
    check('resample() est NEAREST', FIN.resample() == Image.NEAREST)
    for off in (None, False, ''):
        check(f'configure({off!r}) n\'active rien', FIN.configure(off) is None)
    check('un nom inconnu n\'active rien', FIN.configure('coucou') is None)
    FIN.use(None)

    a1 = img(SCENE, [], 8.0)
    a2 = img(SCENE, [('finish', False)], 8.0)
    check('sans la cle et avec "finish": false : identiques au bit pres', np.array_equal(a1, a2))
    b1 = img(SCENE, [('finish', 'net')], 8.0)
    check('la cle change reellement l\'image', not np.array_equal(a1, b1))
    b2 = img(SCENE, [('finish', 'net')], 8.0)
    check('deterministe : deux rendus identiques au bit pres', np.array_equal(b1, b2))
    c1 = img(SCENE, [('body', 'minecraft')], 8.0)
    check('le corps "minecraft" change reellement l\'image', not np.array_equal(a1, c1))
    check('  et sans la cle "body" le rendu est celui d\'avant',
          np.array_equal(a1, img(SCENE, [('body', False)], 8.0)))

    print('\n2. r3d.configure est idempotent et reversible')
    r3d.configure('9:16')
    base = (r3d.RW, r3d.RH, r3d.FOV_K)
    check('raster livre 9:16', base == (216, 384, 1.0), str(base))
    xn0 = r3d._xn
    r3d.configure('9:16')
    check('rappel a l\'identique : les tables par pixel ne sont pas reconstruites', r3d._xn is xn0)
    r3d.configure('9:16', 3)
    check('x3 : raster 648x1152', (r3d.RW, r3d.RH) == (648, 1152), f'{r3d.RW}x{r3d.RH}')
    check('  et le champ de vision ne bouge pas', r3d.FOV_K == 1.0)
    r3d.configure('16:9', 2)
    check('x2 en 16:9 : raster 768x432 et FOV_K conserve', (r3d.RW, r3d.RH, r3d.FOV_K) == (768, 432, .72),
          f'{r3d.RW}x{r3d.RH} fov {r3d.FOV_K}')
    r3d.configure('9:16')
    check('retour a x1 : exactement le raster livre', (r3d.RW, r3d.RH, r3d.FOV_K) == base)
    check('  et les tables par pixel ont la bonne taille', r3d._xn.size == 216 * 384 and r3d.BAYER_T.shape == (384, 216))

    print('\n3. la cle fait ce qu\'elle dit')
    for name, want in (('lisse_seul', 1), ('net_rapide', 2), ('net', 3), ('net_max', 4)):
        st = FIN.configure(name)
        check(f'preset "{name}" : raster x{want}', st and int(st['scale']) == want, str(st and st['scale']))
    FIN.configure('net')
    check('palette 0 -> aucun palier de palette', FIN.levels((12, 5, 20.)) is False)
    check('resample() est LANCZOS', FIN.resample() == Image.LANCZOS)
    FIN.configure('net_palette')
    check('palette 1 -> le call site garde son propre defaut', FIN.levels((12, 5, 20.)) is None)
    FIN.configure({'style': 'net', 'palette': .5})
    lv = FIN.levels((12, 5, 20.))
    check('palette intermediaire -> une palette plus FINE, jamais plus grossiere',
          lv and lv[0] > 12 and lv[1] > 5 and lv[2] < 20., str(lv))
    FIN.use(None)

    from PIL import Image as _I
    ia = _I.fromarray(a1); ib = _I.fromarray(b1)
    check('l\'image finale reste 1080x1920 dans les deux cas', ia.size == (1080, 1920) == ib.size,
          f'{ia.size} / {ib.size}')
    fa, fb = flat_pairs(a1), flat_pairs(b1)
    # un agrandissement x5 au plus proche voisin fabrique 4 paires egales sur 5 par construction
    check('le rendu livre est bien a ~80 % de paires de pixels egales', fa > .70, f'{100 * fa:.1f} %')
    check('  et la finition "net" les effondre', fb < fa / 3., f'{100 * fa:.1f} % -> {100 * fb:.1f} %')

    print('\n4. le corps "minecraft" vise la grille du modele de reference')
    import corps_qc as CQ
    r_def = CQ.silhouette(CQ.POSES['debout'], CQ.LOOK, None)
    r_mc = CQ.silhouette(CQ.POSES['debout'], CQ.LOOK, 'minecraft')
    ref = CQ.REF_MC
    check('aucun cou, comme le modele de reference', r_mc['cou'] == 0., f"{r_mc['cou']:+.3f} m")
    check('  et aucun trou sous le crane (il recouvre le torse)', r_mc['jonction'] < 0, f"{r_mc['jonction']:+.3f} m")
    check('tete aussi large que le torse (reference 1,00)', abs(r_mc['tete_torse'] - ref['tete_torse']) <= .05,
          f"{r_mc['tete_torse']:.2f}")
    check('epaules a la moitie de la hauteur (reference 0,500)', abs(r_mc['ep_haut'] - ref['ep_haut']) <= .03,
          f"{r_mc['ep_haut']:.3f}")
    check('4 tetes de haut (reference 4,00)', abs(r_mc['tetes'] - ref['tetes']) <= .25, f"{r_mc['tetes']:.2f}")
    check('torse au quart de la hauteur (reference 0,250)', abs(r_mc['to_haut'] - ref['to_haut']) <= .03,
          f"{r_mc['to_haut']:.3f}")
    check('PLUS proche de la reference que le rendu livre',
          r_mc['ecart_minecraft'] < r_def['ecart_minecraft'],
          f"minecraft {r_mc['ecart_minecraft']:.3f} < livre {r_def['ecart_minecraft']:.3f}")

    print('\n5. le squelette partage n\'est pas touche')
    bad = [k for k, v in r_mc['os'].items() if abs(v - r_def['os'][k]) > 1e-6]
    check('longueurs d\'os identiques au millionieme', not bad, ', '.join(bad) or f"{len(r_mc['os'])} os")
    check('pied le plus bas au sol, comme le rendu livre', abs(r_mc['pied_y'] - r_def['pied_y']) < 1e-6,
          f"{r_mc['pied_y']:+.4f} / {r_def['pied_y']:+.4f}")
    check('aucune boite en plus ni en moins (pas de cou, pas de deltoides)',
          r_mc['boites'] == r_def['boites'], f"{r_mc['boites']} / {r_def['boites']}")

    print('\n6. CONSOLE 2D n\'est pas touche')
    c0 = img(CONSOLE, [], 6.)
    c1 = img(CONSOLE, [('finish', 'net'), ('body', 'minecraft')], 6.)
    check('une image console est identique au bit pres avec les deux cles', np.array_equal(c0, c1))
    ep, W = validate({'shots': [{'lines': [0, 0]}], 'finish': 'net'}, 1, 'console')
    check('le validateur refuse "finish" en console', 'finish' not in ep)
    check('  et il le dit en nommant les deux moteurs',
          any('pixel3d' in w and 'console' in w for w in W), ' | '.join(W)[:110])
    ep, W = validate({'shots': [{'lines': [0, 0]}], 'body': 'minecraft'}, 1, 'console')
    check('le validateur refuse "body" en console', 'body' not in ep)

    print('\n7. les cles sont validees en pixel3d')
    ep, W = validate({'shots': [{'lines': [0, 0]}], 'finish': 'net'}, 1, 'pixel3d')
    check('un preset connu passe', ep.get('finish') == 'net')
    ep, W = validate({'shots': [{'lines': [0, 0]}], 'finish': 'coucou'}, 1, 'pixel3d')
    check('un nom inconnu est retire', 'finish' not in ep)
    check('  et les presets connus sont nommes', any('net_rapide' in w for w in W), ' | '.join(W)[:110])
    ep, W = validate({'shots': [{'lines': [0, 0]}], 'body': 'minecraft'}, 1, 'pixel3d')
    check('le corps "minecraft" passe', ep.get('body') == 'minecraft')
    st = FIN.configure({'style': 'net', 'scale': 99})
    check('un facteur demesure est borne a 4', st and st['scale'] == 4, str(st and st['scale']))
    st = FIN.configure({'style': 'net', 'scale': 0})
    check('  et un facteur nul est borne a 1', st and st['scale'] == 1, str(st and st['scale']))
    st = FIN.configure({'style': 'net', 'filter': 'coucou'})
    check('un filtre inconnu garde celui du preset', st and st['filter'] == 'lanczos', str(st and st['filter']))
    FIN.use(None)
    st = bodies.configure({'style': 'minecraft', 'arm_in': -.09})
    check('`arm_in` accepte le negatif (epaule plus LARGE que le torse)', st and st['arm_in'] == -.09,
          str(st and st['arm_in']))
    st = bodies.configure({'style': 'minecraft', 'head': -3})
    check('  mais une echelle reste positive (une boite ne se retourne pas)', st and st['head'] == 0.,
          str(st and st['head']))
    bodies.use(None)
    check('les presets de corps attendus existent',
          set(bodies.PRESETS) >= {'minecraft', 'voxel_premium'} and not set(bodies.PRESETS) & {'refit', 'refit_fort', 'tete_seule'}, ', '.join(sorted(bodies.PRESETS)))
    FIN.register('essai_check', scale=2)
    check('un preset de finition peut etre enregistre (registre, pas if/elif)', FIN.PRESETS['essai_check']['scale'] == 2)
    FIN.PRESETS.pop('essai_check')

    print('\n8. le realisateur IA ne connait pas les cles')
    src = ''
    for f in ('prompts.py', 'heuristic.py'):
        src += open(os.path.join(ROOT, 'hstudio', 'director', f), encoding='utf-8').read()
    check('"finish" n\'apparait ni dans prompts.py ni dans heuristic.py', 'finish' not in src)
    check('"minecraft" non plus', 'minecraft' not in src)

    print('\n9. le pool de rendu « spawn »')
    check_spawn()

    print(f'\n{OK[0]} OK, {BAD[0]} echec(s)')
    return 1 if BAD[0] else 0


def check_spawn():
    """Le rendu repart dans des processus neufs : les cles doivent traverser. Sans ce test, une cle qui ne
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
    ep_on = dict(ep); ep_on['body'] = 'minecraft'; ep_on['finish'] = 'net_rapide'
    eng = make_engine('pixel3d', ep_on, lines, env, dur, '9:16')
    check('le moteur a bien resolu les deux presets',
          (eng.fin or {}).get('name') == 'net_rapide' and (eng.body or {}).get('name') == 'minecraft',
          f"finish={(eng.fin or {}).get('name')} body={(eng.body or {}).get('name')}")
    frames = (150,)
    here = [eng.frame(i / 30.).convert('RGB').tobytes() for i in frames]
    off = [make_engine('pixel3d', dict(ep), lines, env, dur, '9:16').frame(i / 30.).convert('RGB').tobytes()
           for i in frames]
    ctx = mp.get_context('spawn')
    with ctx.Pool(2, initializer=pipeline._init_worker, initargs=('pixel3d', ep_on, lines, env, dur, '9:16')) as pool:
        there = list(pool.imap(pipeline._render_one, frames))
    check('deux workers « spawn » rendent les memes octets qu\'ici', there == here,
          'identique' if there == here else 'DIFFERENT : les cles ne traversent pas le pool')
    check('  et ce ne sont pas les octets du rendu livre', there != off)


if __name__ == '__main__': sys.exit(main())
