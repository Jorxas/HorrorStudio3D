"""La preuve de l'integration des figurants : la MEME scene dirigee que la preuve du lot precedent
(`dernier_bus`, jeu `directed`, voxel_premium, caption_safe, soundscape), plus UNE cle : `"extras"`.

    python tools/si_figurants_proof.py                  # mesures + rendu + planche A/B
    python tools/si_figurants_proof.py --plan-seul      # les mesures seules, aucun rendu (≈ 2 min)

Le A de la paire est le rendu VERIFIE du lot precedent (`projects/si_dernier_bus_integre_20261026`) :
il n'est PAS re-rendu. B est le meme episode plus la troupe. La geometrie de la troupe a ete choisie
sur les positions MESUREES des quatre premiers roles (plans de rue 0-10, ados a x <= 2.6) :

| figurant | ou | pourquoi c'est sur |
|---|---|---|
| `passante`, `flaneur` | voie gauche x = -5.0 | a >= 5.7 m lateralement des ados : hors du rayon d'ecoute de 3,5 m de `ShotActing.speech()` quoi qu'il arrive |
| `vendeur` | `porte_loin` (-6.2, 17.0) | >= 9 m de tout premier role |
| `mamie` | `bordure_loin` (3.4, 16.4) | 4,08 m de Tom, le plus proche -- au-dessus des 3,5 m, et elle fuit au plan 5 |
| (voie droite) | NON utilisee | elle passe a 1,63 m de Tom (4.0, 13.2) : un marcheur y volerait le regard d'un dialogue |

Les beats suivent l'histoire : la rue vit (plans 0-2), la menace -- l'ombre, a sa position reelle
echantillonnee (1.2, 16.2) -- fait sursauter la figuration (plan 4), qui fuit (plan 5) et a quitte la
rue AVANT que les ados ne fuient a gauche (plans 8-10) et ne s'enferment dans le hall (plans 11-16).

Ce qui est verifie, pas affirme :
 1. les figurants BOUGENT (metres marches par figurant, couche de jeu echantillonnee a 30 i/s, comme
    `tools/check_background_motion.py`) et ils ont QUITTE la scene : aucun figurant dans les
    echantillons des plans du hall ;
 2. personne ne vole le regard : a CHAQUE depart de replique des plans de rue, la distance du locuteur
    au figurant le plus proche est > 3,5 m ;
 3. la bouche reste libre avec six corps dans la rue : `soustitre_qc.measure` sur l'episode B ;
 4. le MP4 B 9:16 H264/AAC se decode INTEGRALEMENT ; planche A/B aux memes instants que la preuve du
    lot precedent ; copie legere verifiee ;
 5. le cout : secondes de rendu B contre les 626 s mesurees de A (meme machine, meme qualite), et
    l'ecart de taille de distribution (2 -> 6 corps en rue).

La camera du jeu `directed` N'EST PAS identique entre A et B et ne peut pas l'etre : `blocked_at`
(engines/pixel3d/acted.py) ecarte les positions ou un corps non-sujet gene -- quatre figurants
deplacent l'objectif. C'est documente par le lot figurants (section 8 de son rapport) ; la planche
A/B montre donc DEUX mises en scene de la meme histoire, pas deux rendus de la meme camera.

Aucun reseau, aucune API payante, aucune demo livree modifiee, aucun defaut global change.
Windows : corps sous `if __name__ == '__main__'` (le rendu lance un pool « spawn »).
"""
import json, math, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

import numpy as np

from p0_proof import frame_stats, audio_stats                                # noqa: E402
import p1_proof as P1                                                        # noqa: E402
import p1_corps_proof as PC                                                  # noqa: E402
import p2_cinema_proof as P2                                                 # noqa: E402
import si_integration_proof as SI                                            # noqa: E402
import soustitre_qc as SQ                                                    # noqa: E402

ASPECT = '9:16'
WANT = (1080, 1920)
OUTDIR = os.path.join(ROOT, 'docs', 'integration_v3')
LIGHT = os.path.join(OUTDIR, 'leger')
SLUG = 'si_dernier_bus_figurants_20261026'
REF_SLUG = 'si_dernier_bus_integre_20261026'
REF_MP4 = os.path.join(ROOT, 'projects', REF_SLUG, 'renders', REF_SLUG + '_short_9x16.mp4')
REF_RENDER_S = 626                 # secondes du rendu de A, journal du 26/10 (meme machine, 6 workers, standard)
FPS = 30
TROUPE = ('passante', 'flaneur', 'vendeur', 'mamie')
STREET_SHOTS = range(0, 11)
HALL_SHOTS = range(11, 17)

EXTRAS = {
    'set': 'rue', 'lanes': 'city_street', 'seed': 5, 'clear': 3.6,
    'troupe': list(TROUPE),
    'enter': {'passante': [-5.0, 4.6], 'flaneur': [-5.0, 21.0]},
    'spots': {'vendeur': 'porte_loin', 'mamie': 'bordure_loin'},
    'beats': [
        {'shot': 0, 'do': 'life', 'dist': 4.0},
        {'shot': 2, 'do': 'life', 'who': ['passante', 'flaneur'], 'dist': 4.0},
        {'shot': 4, 'do': 'threat', 'at': 0.5, 'from': [1.2, 16.2]},
        {'shot': 5, 'do': 'flee', 'from': [1.2, 16.2], 'at': 0.1},
    ],
}


def acting_measures(ep, lines, dur):
    """couche de jeu echantillonnee a 30 i/s (aucun rendu) : qui bouge, qui est trop pres, qui est parti"""
    from hstudio.pipeline import make_engine
    eng = make_engine('pixel3d', ep, lines, np.zeros(10), dur, ASPECT)
    ac = eng.ctx.get_acting()
    ep2 = eng.ctx.ep                                      # l'episode tel que le moteur le voit (extras ecrits)
    spans = eng.ctx.tl.spans
    hist = {}
    for k, sa in sorted(ac.shots.items()):
        H = hist.setdefault(k, {})
        for t in np.arange(0, sa.dur, 1. / FPS):
            for aid, v in sa.sample(float(t)).items():
                H.setdefault(aid, []).append((float(t), v['x'], v['z']))
    out = {'notes': (ep2.get('_extras_plan') or {}).get('notes', []),
           'troupe_au_cast': [f for f in TROUPE if f in (ep2.get('cast') or {})]}

    walked = {}
    for f in TROUPE:
        m = 0.
        for k in STREET_SHOTS:
            T = (hist.get(k) or {}).get(f) or []
            m += sum(math.hypot(T[i][1] - T[i - 1][1], T[i][2] - T[i - 1][2]) for i in range(1, len(T)))
        walked[f] = round(m, 2)
    out['metres_marches'] = walked

    ghosts = sorted({f for k in HALL_SHOTS for f in (hist.get(k) or {}) if f in TROUPE})
    out['figurants_dans_le_hall'] = ghosts

    # a chaque depart de replique des plans de rue : locuteur -> figurant le plus proche
    rows = []
    for i, l in enumerate(lines):
        g = float(l['start']) + .02
        k, a, _b = eng.ctx.tl.at(g)
        rel = g - a
        if k not in STREET_SHOTS: continue
        sm = ac.shots[k].sample(min(rel, ac.shots[k].dur - .01))
        spk = (ep2.get('lines') or {}).get(str(i), {}).get('speaker')
        if not spk or spk not in sm: continue
        best = None
        for f in TROUPE:
            if f not in sm: continue
            d = math.hypot(sm[f]['x'] - sm[spk]['x'], sm[f]['z'] - sm[spk]['z'])
            if best is None or d < best[1]: best = (f, d)
        rows.append(dict(ligne=i, plan=k, locuteur=spk,
                         figurant=best and best[0], distance=best and round(best[1], 2)))
    out['rayon_ecoute'] = rows
    out['distance_min_locuteur'] = min([r['distance'] for r in rows if r['distance'] is not None] or [None])
    return out


def main():
    from hstudio import ffmpeg_path as FF, demos as D, pipeline as P, oneclick as OC, mediacheck as MC
    from hstudio.audio import soundscape as SS

    found = FF.ensure()
    miss = [t for t, p in found.items() if not p]
    if miss: print('ffmpeg introuvable : ' + ', '.join(miss)); sys.exit(1)
    print('ffmpeg : ' + found['ffmpeg'])

    args = sys.argv[1:]
    workers = int(args[args.index('--workers') + 1]) if '--workers' in args else 6
    quality = args[args.index('--quality') + 1] if '--quality' in args else 'standard'
    plan_seul = '--plan-seul' in args
    os.makedirs(OUTDIR, exist_ok=True)
    P1.OUTDIR = OUTDIR; PC.LIGHT = LIGHT
    out = {'scene': P2.SCENE, 'aspect': ASPECT, 'slug': SLUG, 'reference': REF_MP4,
           'workers': workers, 'quality': quality,
           'episode_keys': dict(SI.EPISODE_KEYS, extras='(la troupe ci-dessous)'), 'extras': EXTRAS}
    t_all = time.time()

    # ---- 1. le MEME episode que la preuve precedente, plus la cle "extras"
    P2.use_scenario('directed')
    pr = D.prepare('dernier_bus', slug=SLUG, name='LE DERNIER BUS - figurants + options integrees')
    ep = pr.read_json('episode.json') or {}
    ep.update(SI.EPISODE_KEYS)
    pr.write_json('episode.json', ep)
    lines, ep = P.merged_lines(pr); dur = P.duration_of(ep, lines)
    eng0 = P.make_engine('pixel3d', dict(ep), lines, np.zeros(10), dur, ASPECT)   # spans (sans extras : cle absente)
    pl = SS.plan(ep, lines, eng0.ctx.tl.spans, beats=SI.SOUND_BEATS)
    ep = pl.apply(ep)
    ep['extras'] = EXTRAS
    pr.write_json('episode.json', ep)
    out['soundscape'] = dict(preset=pl.preset, cues=len(pl.cues), silences=len(pl.silences))

    # ---- 2. la couche de jeu, mesuree avant tout rendu
    print('\n-- couche de jeu : qui bouge, qui est trop pres, qui est parti --')
    m = acting_measures(ep, lines, dur)
    out['jeu'] = m
    for n in m['notes']: print('   note du plan figurants : ' + n)
    print('   troupe au cast : ' + ', '.join(m['troupe_au_cast']))
    print('   metres marches (plans de rue) : ' + json.dumps(m['metres_marches']))
    print('   figurants encore la dans le hall : ' + (', '.join(m['figurants_dans_le_hall']) or 'AUCUN'))
    for r in m['rayon_ecoute']:
        print(f"   replique {r['ligne']:2d} (plan {r['plan']:2d}, {r['locuteur']:5s}) : "
              f"figurant le plus proche {r['figurant']} a {r['distance']} m")
    print(f"   distance minimale locuteur->figurant : {m['distance_min_locuteur']} m  (seuil speech() : 3,5 m)")

    # ---- 3. la bouche, cle posee, avec six corps en rue
    print('\n-- sous-titres avec figurants : bouche couverte ? --')
    from hstudio.acting import background as BG
    eng_b = P.make_engine('pixel3d', BG.expanded(ep), lines, np.zeros(10), dur, ASPECT)
    rows = SQ.measure(eng_b, ASPECT, per_shot=2, cache={})
    n = max(1, len(rows))
    out['bouche'] = dict(n=len(rows),
                         bouche_moy=round(sum(r['bouche'] for r in rows) / n, 4),
                         bouche_max=round(max([r['bouche'] for r in rows] or [0.]), 4),
                         images_touchees=len([r for r in rows if r['bouche'] > .001]),
                         bandes=sorted({r['band'] for r in rows}))
    b = out['bouche']
    print(f"   bouche moy {100*b['bouche_moy']:5.2f} %  pire {100*b['bouche_max']:5.2f} %  "
          f"images touchees {b['images_touchees']}/{b['n']}  bandes {','.join(b['bandes'])}")

    bad_plan = bool(m['figurants_dans_le_hall']) or \
        (m['distance_min_locuteur'] is not None and m['distance_min_locuteur'] <= 3.5) or \
        min(m['metres_marches'].values()) < 1.0 or len(m['troupe_au_cast']) != len(TROUPE) or \
        b['bouche_max'] > .001
    if plan_seul:
        _write(out)
        print('\n' + ('ECHEC (mesures) : voir ' + _report() if bad_plan else
                      'Mesures OK (aucun rendu demande). ' + _report()))
        sys.exit(1 if bad_plan else 0)
    if bad_plan:
        _write(out)
        print('\nECHEC avant rendu : voir ' + _report()); sys.exit(1)

    # ---- 4. le parcours un clic, rendu chronometre
    s = dict(P.load_settings()); s['workers'] = workers; s['quality'] = quality
    t0 = time.time()
    OC.run(pr, settings=s, opts={'aspects': [ASPECT], 'quality': quality}, job=None)
    out['pipeline_seconds'] = round(time.time() - t0, 1)

    have = OC._renders_of(pr, ASPECT)
    if not have:
        out['error'] = 'aucun rendu lisible'; _write(out); sys.exit(1)
    mp4 = pr.p('renders', have[0]); out['mp4'] = mp4

    print('\n-- verification (ffprobe puis decodage integral) --')
    v = MC.describe(mp4, want=WANT, full=True)
    out['verify'] = v; print(MC.summary(v))
    if not v['ok']:
        out['error'] = 'fichier refuse : ' + v['reason']; _write(out); sys.exit(1)

    st = pr.read_json('oneclick.json') or {}
    rd = ((st.get('stages') or {}).get('render') or {}).get('detail') or ''
    out['rendu_seconds_B'] = rd; out['rendu_seconds_A'] = REF_RENDER_S
    print(f"   cout : rendu B {rd or '?'} contre A {REF_RENDER_S} s (meme machine, meme qualite, 2 -> 6 corps en rue)")

    times = [round(v['duration'] * f, 2) for f in (0.06, 0.20, 0.34, 0.48, 0.62, 0.76, 0.90)]
    out['sample_times'] = times
    rows_b, sheet_b = frame_stats(mp4, times, OUTDIR, SLUG)
    out['frames'] = rows_b; out['planche'] = sheet_b
    out['flat_frames'] = len([r for r in rows_b if 'std' in r and r['std'] < 3])
    out['audio'] = audio_stats(mp4, pr.p('work'))
    print('   audio : ' + json.dumps(out['audio'], ensure_ascii=False))

    qc = pr.read_json(OC._qc_file(ASPECT)) or {}
    out['qc'] = {'score': qc.get('score'), 'shots': qc.get('shots'),
                 'failing': sorted(k for k, c in (qc.get('checks') or {}).items()
                                   if not c.get('ok') and not c.get('info'))}
    print('   QC mise en scene : ' + str(out['qc']['score']) + '/100, reproches : '
          + (', '.join(out['qc']['failing']) or 'aucun'))

    out['ab'] = None
    if os.path.exists(REF_MP4):
        print('\n-- planche A/B contre ' + REF_SLUG + ' (memes instants ; cameras du solveur, voir en-tete) --')
        rows_a, _ = frame_stats(REF_MP4, times, OUTDIR, REF_SLUG + '_reffig')
        a = {'title': 'A - lot precedent : directed + options, SANS figurants', 'frames': rows_a}
        bb = {'title': 'B - la meme scene, plus la troupe "extras"', 'frames': rows_b}
        p = P1.ab_sheet(a, bb, 'ab_integre_vs_figurants.png')
        out['ab'] = p; print('  ' + (p or 'PLANCHE NON FABRIQUEE'))

    print('\n-- copie legere 540x960 --')
    lc = PC.light_copy(mp4, SLUG)
    out['leger'] = lc
    print(('  OK    ' if lc['ok'] else '  ECHEC ') + lc['path'] + f"   {lc['size']} o")

    out['total_seconds'] = round(time.time() - t_all, 1)
    _write(out)
    bad = (not v['ok']) or (not lc['ok']) or out['flat_frames']
    print('\n' + ('ECHEC : voir ' + _report() if bad else 'Tout est verifie. ' + _report()))
    sys.exit(1 if bad else 0)


def _report(): return os.path.join(OUTDIR, 'mesures_figurants_integration_20261026.json')


def _write(out):
    json.dump(out, open(_report(), 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)


if __name__ == '__main__':
    main()
