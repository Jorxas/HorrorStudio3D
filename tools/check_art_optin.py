"""Checks on the integration of the two art directions (PIXEL 3D voxel and CONSOLE 2D aplats).

    python tools/check_art_optin.py

Both refits were developed on their own branch, against the same base, and both claimed the same episode key
`"art"` with incompatible values. `tools/regress*.py` prove the two new styles do not drift and that the old
styles are untouched; they cannot see the things this file checks, which are exactly the ones a merge breaks
in silence:

1. **the key is dispatched on the engine**: a CONSOLE episode keeps `"art": "aplat"` and a PIXEL 3D episode
   keeps its preset. Merged as two separate blocks, whichever validator ran first stripped the other engine's
   value and called it unknown. This file fails if that ever comes back, in either direction;
2. **the two 48x48 faces coexist**: `"face_detail": "hd"` (lot 3) and the art direction's parametric face are
   two different images, both reachable, and the character key wins over the episode one -- a rule of scope,
   not an artistic verdict;
3. **the silent overlaps speak French**: what one refit cannot carry from the other is named on the render
   log, never dropped quietly;
4. **everything stays opt-in**: without the key, both engines are on their original path and the art modules
   are inert;
5. **the preset survives the spawn pool**: the real render builds one engine per worker process, and the art
   preset lives in a module global. That contract is asserted here on the real pool, not assumed.

Exit 0 if every check passes, 1 otherwise. No API, no network, no key, no project written.

Windows: the body is behind `if __name__ == '__main__'` on purpose. The render pool spawns, and a spawned
worker re-imports the main module; a tool whose body sits at module level re-runs itself inside every worker.
"""
import os, sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)

OK, BAD = [], []


def check(name, cond, detail=''):
    (OK if cond else BAD).append(name)
    print(f'  {"OK  " if cond else "FAIL"} {name}' + (f'   {detail}' if detail else ''))


# --------------------------------------------------------------------------- 1. the key, dispatched per engine
def check_dispatch():
    from hstudio.director.validate import validate
    from hstudio.engines.pixel3d.art import PRESETS as P3

    def run(art, style, **extra):
        ep = {'shots': [{'lines': [0, 1]}], **extra}
        if art is not ...: ep['art'] = art
        ep, w = validate(ep, 2, style)
        return ep, [m for m in w if 'artistique' in m or 'palette' in m]

    print('\n1. la clé "art" est dispatchée sur le moteur')
    ep, w = run('aplat', 'console', palette='alert')
    check('console garde "art": "aplat"', ep.get('art') == 'aplat', repr(ep.get('art')))
    check('console garde sa palette', ep.get('palette') == 'alert', repr(ep.get('palette')))
    check('console : aucun avertissement pour une valeur valide', not w, str(w))

    for pal in ('night', 'alert', 'game', 'dawn'):
        ep, w = run('aplat', 'console', palette=pal)
        check(f'console garde la palette "{pal}"', ep.get('palette') == pal and not w)

    for name in sorted(P3):
        ep, w = run(name, 'pixel3d')
        check(f'pixel3d garde le préset "{name}"', ep.get('art') == name and not w, str(w))

    ep, w = run({'style': 'voxel_hd', 'detail': .4, 'grade': False}, 'pixel3d')
    check('pixel3d garde la forme dict {style, overrides}', ep.get('art') == {'style': 'voxel_hd', 'detail': .4, 'grade': False}, str(w))

    # the two crossed cases: refused, and the message must name the other engine, not just say "unknown"
    ep, w = run('voxel_hd', 'console')
    check('console refuse un préset pixel3d', 'art' not in ep)
    check('  et le message nomme le moteur pixel3d', bool(w) and 'pixel3d' in w[0], w[0] if w else '(aucun message)')
    ep, w = run('aplat', 'pixel3d')
    check('pixel3d refuse la direction "aplat"', 'art' not in ep)
    check('  et le message nomme le moteur console', bool(w) and 'console' in w[0], w[0] if w else '(aucun message)')

    # plain unknowns, on both engines
    for style in ('pixel3d', 'console'):
        ep, w = run('mauve_fluo', style)
        check(f'{style} refuse une valeur inconnue, à voix haute', 'art' not in ep and bool(w), w[0] if w else '')

    # off means off, in both engines, without a spurious warning
    for style in ('pixel3d', 'console'):
        for val in (None, False, ''):
            ep, w = run(val, style)
            check(f'{style} : "art": {val!r} = ancien style, en silence', 'art' not in ep and not w, str(w))
        ep, w = run(..., style)
        check(f'{style} : pas de clé "art" du tout = rien à signaler', 'art' not in ep and not w)

    # a dict on the console side must be refused, not crash (a dict is unhashable: `x in {...}` raises)
    try:
        ep, w = run({'style': 'aplat'}, 'console')
        check('console refuse la forme dict sans lever TypeError', 'art' not in ep and bool(w), w[0] if w else '')
    except TypeError as e:
        check('console refuse la forme dict sans lever TypeError', False, f'TypeError: {e}')

    # an unknown palette is still reported on the console side
    ep, w = run('aplat', 'console', palette='mauve')
    check('console refuse une palette inconnue, à voix haute', 'palette' not in ep and bool(w), w[0] if w else '')


# --------------------------------------------------------------------------- 2. the two 48x48 faces coexist
def check_faces():
    from hstudio.engines.pixel3d import rigfig, art

    sample = {'x': 0., 'y': 0., 'z': 0., 'heading': 0., 'face': 'scared', 'talking': False,
              'rig': {'phase': 0., 'speed': 0., 'emotion': 'neutral'}}
    print('\n2. les deux visages 48x48 cohabitent')
    art.use(None)
    f_v2 = np.asarray(rigfig.face_for({}, sample))
    f_lot3 = np.asarray(rigfig.face_for({'face_detail': 'hd'}, sample))
    art.use(art.configure('voxel_hd'))
    f_art = np.asarray(rigfig.face_for({}, sample))
    f_both = np.asarray(rigfig.face_for({'face_detail': 'hd'}, sample))
    art.use(None)
    f_v2_again = np.asarray(rigfig.face_for({}, sample))

    check('sans rien demander : le visage d\'origine 24x24', f_v2.shape[:2] == (24, 24), str(f_v2.shape))
    check('"face_detail": "hd" seul : le visage du lot 3, 48x48', f_lot3.shape[:2] == (48, 48), str(f_lot3.shape))
    check('"art" seul : le visage de la direction artistique, 48x48', f_art.shape[:2] == (48, 48), str(f_art.shape))
    check('ce sont deux images différentes, pas le même visage', not np.array_equal(f_lot3, f_art))
    check('les deux demandés : la clé du personnage l\'emporte', np.array_equal(f_both, f_lot3))
    check('  et ce n\'est pas celui de la direction artistique', not np.array_equal(f_both, f_art))
    check('direction artistique éteinte : on revient au visage d\'origine', np.array_equal(f_v2_again, f_v2))


# --------------------------------------------------------------------------- 3. the silent overlaps speak
def check_notices():
    from hstudio.engines.pixel3d import art
    from hstudio.engines.console import aplat

    print('\n3. les recouvrements silencieux le disent en français')
    art.use(art.configure('voxel_hd'))
    msgs = art.notices({'lea': {'face_detail': 'hd'}, 'tom': {}})
    check('pixel3d : le choc des deux visages est signalé', any('face_detail' in m for m in msgs), str(msgs)[:90])
    check('  et le message nomme le personnage concerné', any('lea' in m for m in msgs))
    check('  et pas celui qui ne demande rien', not any('tom' in m for m in msgs))
    msgs = art.notices({'lea': {'hair2': (1, 2, 3), 'detail': True}})
    check('pixel3d : les clés hair2 / detail / accent non portées sont signalées',
          any('hair2' in m for m in msgs), str(msgs)[:90])
    check('rien demandé de spécial : aucun bruit', art.notices({'lea': {}}) == [])
    art.use(art.configure('grade_only'))
    check('un préset qui ne touche ni visage ni corps ne signale rien',
          art.notices({'lea': {'face_detail': 'hd', 'detail': True}}) == [])
    art.use(None)
    check('direction artistique éteinte : aucun message', art.notices({'lea': {'face_detail': 'hd'}}) == [])

    ep = {'faces': 'expressive', 'shots': [{'lines': [0, 0]}, {'lines': [1, 1], 'scene': {'type': 'face', 'faces': 'expressive'}}]}
    msgs = aplat.notices(ep, 'aplat', {'lea': {'faces': 'expressive'}})
    check('console : "faces": "expressive" perdu sous "aplat" est signalé', bool(msgs), str(msgs)[:90])
    check('  et le message nomme l\'épisode, le plan et le personnage',
          bool(msgs) and all(k in msgs[0] for k in ('épisode', 'plan 1', 'lea')))
    check('console : style d\'origine = aucun message', aplat.notices(ep, '', {'lea': {'faces': 'expressive'}}) == [])
    check('console : "aplat" sans visages expressifs = aucun message', aplat.notices({'shots': []}, 'aplat', {}) == [])


# --------------------------------------------------------------------------- 4. everything stays opt-in
def check_optin(build):
    from hstudio.engines.pixel3d import art
    from hstudio.director import prompts, heuristic

    print('\n4. tout reste optionnel, et le réalisateur n\'en sait rien')
    art.use(None)
    check('sans clé, le module d\'art est inerte', art.active() is None)
    check('  et aucune de ses fonctions n\'est activée', not any(art.on(f) for f in art.FEATURES))

    eng, _ = build('demo1_mouvement', '9:16')            # an old pixel3d demo, no art key
    check('une vieille démo pixel3d : aucun préset d\'art', eng.art is None)
    check('  et aucun message', eng.art_warnings == [])
    eng, _ = build('demo5_console', '16:9')              # an old console demo, no art key
    check('une vieille démo console : chemin d\'origine', eng.art == '')
    check('  et aucun message', eng.art_warnings == [])

    # Ce que le réalisateur peut écrire se juge sur DEUX choses, parce qu'aucune des deux ne suffit seule :
    #  - le **texte réellement envoyé** au LLM (les constantes de `prompts.py`, assemblées à l'import depuis les
    #    registres du moteur). C'est lui qui compte : une clé peut arriver là sans être écrite en clair dans le
    #    fichier. Et une note d'intégration mal placée atterrit dedans — c'est arrivé pendant la fusion P1, et
    #    c'est ce test qui l'a vu ;
    #  - le **code** des deux modules, commentaires retirés. Un commentaire ne part jamais chez le LLM, et
    #    interdire d'expliquer une décision en commentaire pousserait à ne plus l'expliquer du tout.
    from hstudio.director import prompts as _prompts
    sent = chr(10).join(v for k, v in vars(_prompts).items() if k.isupper() and isinstance(v, str))
    nocomment = lambda t: chr(10).join(l for l in t.split(chr(10)) if not l.lstrip().startswith('#'))
    code = nocomment(open(os.path.join(ROOT, 'hstudio', 'director', 'prompts.py'), encoding='utf-8').read())
    code += nocomment(open(os.path.join(ROOT, 'hstudio', 'director', 'heuristic.py'), encoding='utf-8').read())
    # « variation » (décors) rejoint la liste à l'intégration P1 : la branche apprenait la clé au réalisateur IA,
    # ce qui aurait activé de fait une direction de décor que le propriétaire n'a pas encore jugée.
    # « clear_face » (cadrage dégagé du bras, lot P1 visuel) rejoint la liste pour la même raison : elle change
    # le placement de la caméra sur les plans serrés, et ce placement n'a pas encore été jugé par le propriétaire.
    # « body » / « refit » (proportions du corps, lot P1 corps) rejoignent la liste pour la meme raison encore :
    # la cle change la silhouette de tous les personnages, et cette silhouette n'a pas encore ete jugee.
    # « eye_aim » (visee du regard, lot P1 interaction + regard) rejoint la liste pour la meme raison : la cle
    # deplace les pupilles de tous les personnages, et ce regard n'a pas encore ete juge par le proprietaire.
    # « env » / « riche » (facades detaillees, lot P1 decor urbain) rejoignent la liste pour la meme raison :
    # la cle redessine la texture de tous les murs d'immeuble, et ce decor n'a pas encore ete juge.
    # « voxel_premium » (la finition premium du corps cubique, lot P1 voxel premium) rejoint la liste pour la
    # meme raison : la cle ajoute 30 boites par personnage, promeut le visage 48x48 et les meches de cheveux de
    # TOUT le casting, et aucune de ces trois choses n'a encore ete jugee par le proprietaire sur une video.
    # « eye_smooth » (lissage des pupilles, lot P1 lissage) et « finish » / « minecraft » (prototype Minecraft)
    # rejoignent la liste pour la meme raison : la premiere deplace les pupilles, la deuxieme multiplie le cout
    # par image par neuf, la troisieme change la silhouette de tous les personnages. Aucune n'a encore ete jugee.
    # « extras » (figurants d'arriere-plan, lot scenes vivantes) rejoint la liste pour la meme raison : la cle
    # ajoute trois a cinq corps a la scene, donc ~40 boites par figurant et une mise en activite que le
    # proprietaire n'a pas encore jugee sur une video. Voir docs/FIGURANTS_SCENES_VIVANTES.md.
    for key in ('"art"', "'art'", 'aplat', 'voxel_hd', 'variation', 'clear_face', '"body"', "'body'", 'refit',
                '"extras"', "'extras'", 'figurant',
                '"eye_aim"', "'eye_aim'", 'aim_doux',
                '"eye_smooth"', "'eye_smooth'", 'saccade',
                '"finish"', "'finish'", 'net_rapide', '"minecraft"', "'minecraft'", '"voxel_premium"', "'voxel_premium'",
                '"env"', "'env'", 'riche'):
        check(f'le réalisateur n\'écrit jamais {key}', key not in sent and key not in code)

    # and the key really does something when asked for: the opt-in is not a no-op
    on, _ = build('demo13_art_pixel3d', '16:9')
    off, _ = build('demo13_art_pixel3d', '16:9', art=None)
    a = np.asarray(on.frame(1.0).convert('RGB')).astype(np.int16)
    b = np.asarray(off.frame(1.0).convert('RGB')).astype(np.int16)
    check('pixel3d : la clé "art" change réellement l\'image', np.abs(a - b).mean() > 1.0,
          f'écart moyen {np.abs(a - b).mean():.1f}/255')
    on, _ = build('demo11_aplat', '16:9')
    off, _ = build('demo11_aplat', '16:9', art=None)
    a = np.asarray(on.frame(on.tl.spans[0][0] + .6).convert('RGB')).astype(np.int16)
    b = np.asarray(off.frame(off.tl.spans[0][0] + .6).convert('RGB')).astype(np.int16)
    check('console : la clé "art" change réellement l\'image', np.abs(a - b).mean() > 1.0,
          f'écart moyen {np.abs(a - b).mean():.1f}/255')


# --------------------------------------------------------------------------- 5. the preset crosses the spawn pool
def check_spawn(build):
    """the real render builds one engine per worker process; the preset lives in a module global.

    Proven, not assumed: the same frame is rendered in this process and in a pool of two spawned workers, by
    the very functions step_render uses (`pipeline._init_worker` / `_render_one`), and the bytes must match."""
    import multiprocessing as mp
    from hstudio import demos, pipeline
    from hstudio.pipeline import duration_of

    print('\n5. le préset d\'art traverse le pool « spawn »')
    sc = demos.load('demo13_art_pixel3d')
    lines = demos.timed_lines(sc['script'], float(sc.get('gap', .3)), float(sc.get('lead', .4)))
    env = demos.draft_voice(sc, lines)[1]
    ep = demos.episode_of(sc, lines, log=lambda *a: None)
    lines = demos.lines_with_meta(ep, lines)
    dur = duration_of(ep, lines)
    check('la démo porte bien la clé', ep.get('art') == 'voxel_hd', repr(ep.get('art')))

    eng, _ = build('demo13_art_pixel3d', '16:9')
    here = [eng.frame(i / 30.).convert('RGB').tobytes() for i in (30, 45)]
    ep_off = dict(ep); ep_off.pop('art', None)
    eng_off = pipeline.make_engine('pixel3d', ep_off, lines, env, dur, '16:9')
    off = eng_off.frame(1.0).convert('RGB').tobytes()

    ctx = mp.get_context('spawn')
    with ctx.Pool(2, initializer=pipeline._init_worker, initargs=('pixel3d', ep, lines, env, dur, '16:9')) as pool:
        there = list(pool.imap(pipeline._render_one, (30, 45)))

    check('deux workers « spawn » rendent les mêmes octets qu\'ici', there == here,
          'identique' if there == here else 'DIFFÉRENT : le préset ne traverse pas le pool')
    check('  et ce n\'est pas l\'image sans direction artistique', there[0] != off)


if __name__ == '__main__':
    from hstudio import demos
    from hstudio.pipeline import make_engine, duration_of

    def build(demo_id, aspect, art='keep'):
        """one engine straight from a scenario, exactly like tools/check_aplat_ui.py does"""
        sc = demos.load(demo_id)
        lines = demos.timed_lines(sc['script'], float(sc.get('gap', .3)), float(sc.get('lead', .4)))
        env = demos.draft_voice(sc, lines)[1]
        ep = demos.episode_of(sc, lines, log=lambda *a: None)
        if art != 'keep':
            ep = dict(ep)
            if art: ep['art'] = art
            else: ep.pop('art', None)
        lines = demos.lines_with_meta(ep, lines)
        return make_engine(sc.get('style', 'pixel3d'), ep, lines, env, duration_of(ep, lines), aspect), ep

    check_dispatch()
    check_faces()
    check_notices()
    check_optin(build)
    check_spawn(build)
    print(f'\n{len(OK)} OK, {len(BAD)} FAIL')
    sys.exit(1 if BAD else 0)
