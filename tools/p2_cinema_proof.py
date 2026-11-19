"""La preuve de ce lot : UNE histoire d'horreur 9:16 entiere, fabriquee automatiquement, en vrais MP4.

    python tools/p2_cinema_proof.py --court                      # test cible : 3 plans, pour mesurer le cout
    python tools/p2_cinema_proof.py --workers 5 --quality standard
    python tools/p2_cinema_proof.py --only directed
    python tools/p2_cinema_proof.py --leger-seul                 # refabrique seulement les copies legeres

Le scenario est `examples/scenes/dernier_bus.json`. Il ne contient AUCUNE camera : chacun de ses dix-sept
beats dit seulement POURQUOI on coupe (etablir, suivre, devoiler, reagir, interagir, menacer, fuir,
quitter). `hstudio/director/narrative.py` en deduit la taille du plan, le mouvement et le cote, et
`hstudio/acting/cinema.py` place reellement la camera. Trois versions du MEME fichier sont tournees, et
chacune n'ajoute qu'une chose a la precedente -- c'est la seule facon de dire ce que chacune apporte :

| variante | ce qui est ecrit dans l'episode | ce que ca vaut |
|---|---|---|
| **A `legacy`**   | les beats, leur jeu, leurs repliques. **Zero camera.** | le moteur couvre la scene avec `cinema.auto_camera()`, c'est-a-dire les conventions normales de toute episode sans cle `camera`. Aucune option opt-in, aucun bloc `lighting`. |
| **B `intents`**  | + les 17 **intentions** de plan et la lumiere des plateaux | la mise en scene seule, sans une seule cle opt-in |
| **C `directed`** | + les cles opt-in validees par les lots precedents (`eyeline`, `footing`, `approach`, `camera_face_track`, `clear_face`, `head_room`) | la mise en scene et les options ensemble |

Chaque variante passe le parcours en un clic COMPLET (voix de brouillon locale, calage, mixage, rendu,
controle qualite, titres, miniatures), puis est verifiee comme en P0 et P1 : structure MP4, `ffprobe`,
**decodage integral**, images reellement extraites du fichier final, piste audio decodee. Des copies
legeres 540x960 sont fabriquees et verifiees de la meme facon. Aucun reseau, aucune cle d'API, aucun cout,
AUCUNE publication, aucune demo livree modifiee, aucun mode global active.

CE QUE CE FICHIER NE PROUVE PAS. Il prouve que les fichiers existent, se decodent entierement, durent ce
qu'ils annoncent, different les uns des autres, et que les mesures de mise en scene de
`tools/storyboard_qc.py` sont celles qui sont annoncees. Il ne dit RIEN de la valeur artistique du
resultat : cela se juge a l'oeil, sur les planches A/B et sur les videos, et par le proprietaire. Un
controle informatique vert n'est pas une validation artistique.

Windows : corps derriere `if __name__ == '__main__'` (le rendu lance un pool « spawn »).
"""
import os, sys, json, copy, time, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))

from p0_proof import frame_stats, audio_stats                                # noqa: E402
import p1_proof as P1                                                        # noqa: E402
import p1_corps_proof as PC                                                  # noqa: E402
import storyboard_qc as SB                                                   # noqa: E402

ASPECT = '9:16'
WANT = (1080, 1920)
OUTDIR = os.path.join(ROOT, 'docs', 'p2_cinema')
LIGHT = os.path.join(OUTDIR, 'leger')
SCENE = os.path.join(ROOT, 'examples', 'scenes', 'dernier_bus.json')

CASES = [
    ('legacy',   'p2c_dernier_bus_a_legacy_20261025',   'A - conventions normales (aucune camera ecrite)'),
    ('intents',  'p2c_dernier_bus_b_intents_20261025',  'B - intentions de mise en scene seules'),
    ('directed', 'p2c_dernier_bus_c_directed_20261025', 'C - intentions + options validees'),
]
PAIRS = [('p2c_dernier_bus_a_legacy_20261025', 'p2c_dernier_bus_c_directed_20261025', 'ab_legacy_vs_directed.png'),
         ('p2c_dernier_bus_b_intents_20261025', 'p2c_dernier_bus_c_directed_20261025', 'ab_intents_vs_directed.png')]


def use_scenario(options, beats=None):
    """la scene d'epreuve est compilee puis chargee a la place d'une demo du catalogue.

    Rien n'est ecrit dans `examples/demos/`, donc ni le catalogue du studio ni les suites de
    non-regression ne voient cette scene. `demos.load` est la seule porte par laquelle `prepare()`,
    `build()` et `state_after()` lisent un scenario, donc la remplacer suffit et ne duplique aucun chemin.
    `beats` coupe le scenario a ses N premiers beats : c'est le test court."""
    from hstudio import demos as D
    from hstudio.director import narrative as N
    sc = json.load(open(SCENE, encoding='utf-8'))
    if beats: sc['narrative'] = dict(sc['narrative'], beats=sc['narrative']['beats'][:beats])
    sc = N.scenario(sc, options=options)
    D.load = lambda demo_id, _sc=sc: copy.deepcopy(_sc)
    return sc


def one(options, slug, title, workers, quality, beats=None):
    from hstudio import demos as D, pipeline as P, oneclick as OC, mediacheck as MC
    print('\n' + '=' * 78); print('== ' + title); print('=' * 78)
    res = {'scene': os.path.basename(SCENE), 'slug': slug, 'title': title, 'aspect': ASPECT,
           'quality': quality, 'options': options, 'beats': beats}

    sc = use_scenario(options, beats)
    pr = D.prepare('dernier_bus', slug=slug, name=title)
    ep = pr.read_json('episode.json') or {}
    res['project_dir'] = pr.dir
    res['storyboard'] = sc.get('storyboard') or []
    res['directed'] = ep.get('_directed')
    res['cameras_ecrites'] = sum(1 for s in ep.get('shots') or [] if s.get('camera'))
    res['shots'] = len(ep.get('shots') or [])
    res['cles_opt_in'] = {k: ep.get(k) for k in ('eyeline', 'footing', 'approach', 'camera_face_track',
                                                 'clear_face') if ep.get(k) is not None}
    res['head_room_par_plan'] = sum(1 for s in ep.get('shots') or [] if (s.get('camera') or {}).get('head_room'))
    res['lighting'] = bool(ep.get('lighting'))
    res['sets'] = sorted((ep.get('sets') or {}))
    res['cast'] = sorted((ep.get('cast') or {}))
    print(f"Episode : {res['shots']} plans, {res['cameras_ecrites']} cameras ecrites, "
          f"decors {', '.join(res['sets'])}, acteurs {', '.join(res['cast'])}")
    print('Cles relues sur episode.json : ' + (json.dumps(res['cles_opt_in'], ensure_ascii=False) or '{}')
          + f"  lighting={res['lighting']}  head_room sur {res['head_room_par_plan']} plan(s)")

    s = dict(P.load_settings()); s['workers'] = workers; s['quality'] = quality
    t0 = time.time()
    OC.run(pr, settings=s, opts={'aspects': [ASPECT], 'quality': quality}, job=None)
    res['pipeline_seconds'] = round(time.time() - t0, 1)

    have = OC._renders_of(pr, ASPECT)
    if not have:
        res['error'] = 'aucun rendu lisible'
        print('ARRET : aucun rendu lisible'); return res
    mp4 = pr.p('renders', have[0]); res['mp4'] = mp4

    print('\n-- verification (ffprobe puis decodage integral) --')
    v = MC.describe(mp4, want=WANT, full=True)
    res['verify'] = v
    print(MC.summary(v))
    if not v['ok']:
        res['error'] = 'fichier refuse : ' + v['reason']; return res

    dur = v['duration']
    # les MEMES instants pour les trois variantes : une planche A/B n'a de sens qu'a images comparables
    res['sample_times'] = [round(dur * f, 2) for f in (0.06, 0.20, 0.34, 0.48, 0.62, 0.76, 0.90)]
    rows, sheet = frame_stats(mp4, res['sample_times'], OUTDIR, slug)
    res['frames'] = rows; res['sheet'] = sheet
    for r in rows:
        print('   t=%6.2f s  %s' % (r['t'], r.get('error') or
              ('%dx%d  luminosite %6.2f  ecart-type %6.2f' % (r['size'][0], r['size'][1], r['mean'], r['std']))))
    res['flat_frames'] = len([r for r in rows if 'std' in r and r['std'] < 3])
    res['audio'] = audio_stats(mp4, pr.p('work'))
    print('   audio : ' + json.dumps(res['audio'], ensure_ascii=False))

    qc = pr.read_json(OC._qc_file(ASPECT)) or {}
    res['qc'] = {'score': qc.get('score'), 'shots': qc.get('shots'), 'duration': qc.get('duration'),
                 'encoded_ok': (qc.get('encoded') or {}).get('ok'),
                 'faces_readable': round(float(((qc.get('checks') or {}).get('faces_readable') or {}).get('value', 0.)), 3),
                 'speaker_visible': round(float(((qc.get('checks') or {}).get('speaker_visible') or {}).get('value', 0.)), 3),
                 'subjects_framed': round(float(((qc.get('checks') or {}).get('subjects_framed') or {}).get('value', 0.)), 3),
                 'camera_blocked': ((qc.get('checks') or {}).get('camera_blocked') or {}).get('value'),
                 'lens_widened': ((qc.get('checks') or {}).get('lens_widened') or {}).get('value'),
                 'continuity': ((qc.get('checks') or {}).get('continuity') or {}).get('value'),
                 'subtitle_speed': ((qc.get('checks') or {}).get('subtitle_speed') or {}).get('value'),
                 'failing': sorted(k for k, c in (qc.get('checks') or {}).items()
                                   if not c.get('ok') and not c.get('info'))}
    print('   QC mise en scene : ' + str(res['qc']['score']) + '/100, visages lisibles '
          + str(res['qc']['faces_readable']) + ', sujets cadres ' + str(res['qc']['subjects_framed'])
          + ', reproches : ' + (', '.join(res['qc']['failing']) or 'aucun'))
    res['vignettes'] = {}
    for src, dst in (('cover_9x16.jpg', slug + '_cover_9x16.jpg'),
                     ('thumbnail_16x9.jpg', slug + '_thumbnail_16x9.jpg')):
        if pr.exists(src):
            os.makedirs(OUTDIR, exist_ok=True)
            shutil.copyfile(pr.p(src), os.path.join(OUTDIR, dst))
            res['vignettes'][dst] = os.path.getsize(pr.p(src))
    res['ok'] = True
    return res


def board(options, every=.5):
    """les mesures de storyboard de la variante, sur le MEME scenario (tools/storyboard_qc.py)"""
    r = SB.run_one(SCENE, options, ASPECT, every, log=lambda *a: None)
    return {'verdict': r['verdict'], 'motion': r['motion'], 'shots': r['shots']}


if __name__ == '__main__':
    from hstudio import ffmpeg_path as FF
    found = FF.ensure()
    miss = [t for t, p in found.items() if not p]
    if miss:
        print('ffmpeg introuvable (' + ', '.join(miss) + ') : ' + FF.INSTALL_HINT); sys.exit(1)
    print('ffmpeg : ' + found['ffmpeg'])
    P1.OUTDIR = OUTDIR                     # les planches A/B de CE lot
    PC.LIGHT = LIGHT                       # ... et ses copies legeres
    args = sys.argv[1:]
    workers = int(args[args.index('--workers') + 1]) if '--workers' in args else 5
    quality = args[args.index('--quality') + 1] if '--quality' in args else 'standard'
    only = args[args.index('--only') + 1] if '--only' in args else ''
    court = 3 if '--court' in args else None
    os.makedirs(OUTDIR, exist_ok=True)
    report = os.path.join(OUTDIR, ('mesures_p2_court' if court else 'mesures_p2_cinema') + '_20261025.json')

    if '--leger-seul' in args:
        bad, done = 0, []
        for options, slug, title in CASES:
            mp4 = os.path.join(ROOT, 'projects', slug, 'renders', slug + '_short_9x16.mp4')
            if not os.path.exists(mp4):
                print('  ABSENT ' + mp4); bad += 1; continue
            lc = PC.light_copy(mp4, slug); done.append(lc)
            print(('  OK    ' if lc['ok'] else '  ECHEC ') + lc['path'] + f"   {lc['size']} o"
                  + ('' if lc['ok'] else '  ' + str(lc['reason'])))
            bad += 0 if lc['ok'] else 1
        if done and os.path.exists(report):
            d = json.load(open(report, encoding='utf-8')); d['leger'] = done
            json.dump(d, open(report, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
        sys.exit(1 if bad else 0)

    cases = [c for c in CASES if not only or c[0] == only]
    out = {'scene': SCENE, 'aspect': ASPECT, 'workers': workers, 'quality': quality,
           'court': court, 'runs': {}, 'boards': {}}
    t0 = time.time()
    for options, slug, title in cases:
        if not court:
            print(f'\n-- storyboard "{options}" (aucun rendu, aucun fichier ecrit) --')
            out['boards'][options] = board(options)
        out['runs'][options] = one(options, slug + ('_court' if court else ''), title, workers, quality, court)
    out['total_seconds'] = round(time.time() - t0, 1)

    print('\n-- copies legeres 540x960 --')
    out['leger'] = []
    for options, slug, title in cases:
        r = out['runs'].get(options) or {}
        if not r.get('mp4'): continue
        lc = PC.light_copy(r['mp4'], slug + ('_court' if court else ''))
        out['leger'].append(dict(lc, options=options))
        print(('  OK    ' if lc['ok'] else '  ECHEC ') + lc['path'] + f"   {lc['size']} o"
              + ('' if lc['ok'] else '  ' + str(lc['reason'])))

    if not court:
        print('\n-- planches A/B (memes instants, pleine image, rien de recadre) --')
        out['ab'] = []
        by = {c[1]: out['runs'].get(c[0]) for c in cases}
        for a_slug, b_slug, name in PAIRS:
            a, b = by.get(a_slug), by.get(b_slug)
            if not a or not b: continue
            p = P1.ab_sheet(a, b, name)
            if p: out['ab'].append(p); print('  ' + p)

    json.dump(out, open(report, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
    print('\n' + report)
    bad = [k for k, r in out['runs'].items() if not r.get('ok')] + [l['path'] for l in out['leger'] if not l['ok']]
    print(('ECHECS : ' + ', '.join(str(b) for b in bad)) if bad else 'Tout est verifie.')
    print(f"Duree totale : {out['total_seconds']} s")
    sys.exit(1 if bad else 0)
