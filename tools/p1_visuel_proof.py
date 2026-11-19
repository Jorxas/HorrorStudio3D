"""La preuve du lot P1 « visuel » : le meme episode rendu deux fois, une seule chose change, sur de vrais MP4.

    python tools/p1_visuel_proof.py --workers 8 --quality standard
    python tools/p1_visuel_proof.py --only demo6_continuite

| paire | moteur | A | B |
|---|---|---|---|
| `demo6_continuite` (deux gros plans, cuisine) | pixel3d | aucune cle | cadrage lisible + visage/cheveux expressifs |
| `demo20_decors` (quatre lieux, marches) | pixel3d | aucune cle | idem |

Le « cadrage lisible » est **un** nom pour **trois** cles opt-in, et le rapport ne pretend pas le contraire :

| cle | d'ou elle vient | ce qu'elle fait |
|---|---|---|
| `camera_clear_face` (episode) | NOUVELLE dans ce lot | la camera evite les angles ou le bras du sujet barre son propre visage ; elle entraine `camera_face_track` |
| `camera_face_track` (episode) | existait deja, jamais jugee | la camera est jugee sur l'axe reel du visage et sur la largeur reelle de la tete |
| `face_detail` / `hair2` / `iris` / `detail` / `hair_style` en meches (personnage) | existaient deja, jamais jugees | visage 48x48 (sourcils, iris, bouche), cheveux en meches etagees, vetement nuance |

Les couleurs du personnage ne changent PAS entre A et B (meme sweat, meme peau, memes cheveux) : sinon la
comparaison mesurerait un changement de costume et pas un changement de rendu.

Chaque variante passe le parcours en un clic complet (voix de brouillon locale, calage, mixage, rendu, controle
qualite, titres, miniatures), puis est verifiee comme en P0 : structure MP4, `ffprobe`, **decodage integral**,
images reellement extraites du fichier final, piste audio decodee. Aucun reseau, aucune cle d'API, aucun cout.

Windows : corps derriere `if __name__ == '__main__'` (le rendu lance un pool « spawn »).
"""
import os, sys, json, copy, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))

from p0_proof import frame_stats, audio_stats, runtime_expressions          # noqa: E402
from p1_proof import ab_sheet as _ab_sheet                                  # noqa: E402

ASPECT = '9:16'
WANT = (1080, 1920)
OUTDIR = os.path.join(ROOT, 'docs', 'p1_visuel')

STRANDS = {'ponytail': 'strands_ponytail', 'long': 'strands_long'}
HAIR2 = (150, 96, 58)          # meche claire, derivee du brun des deux personnages de la serie
IRIS = (96, 140, 120)


def apply_variant(ep, readable):
    """-> (episode modifie, ce qui a ete fait). A : rien. B : les trois cles, et rien d'autre."""
    ep = copy.deepcopy(ep); done = []
    if not readable:
        ep.pop('camera_clear_face', None); ep.pop('camera_face_track', None)
        for c in (ep.get('cast') or {}).values():
            if isinstance(c, dict):
                for k in ('face_detail', 'hair2', 'iris', 'detail'): c.pop(k, None)
        return ep, done
    ep['camera_clear_face'] = True
    done.append('cadrage degage du bras (camera_clear_face, entraine camera_face_track)')
    n = 0
    for c in (ep.get('cast') or {}).values():
        if not isinstance(c, dict): continue
        c['face_detail'] = 'hd'; c['detail'] = True; c['hair2'] = list(HAIR2); c['iris'] = list(IRIS)
        n += 1
    done.append(f'visage 48x48 + meches + vetement nuance sur {n} personnage(s)')
    return ep, done


def readable_look(pr, ep):
    """les meches ont besoin du style de coiffure du personnage, qui vit dans library/characters : on le lit
    et on le remplace par sa variante en meches, sans toucher au fichier de la bibliotheque."""
    from hstudio.acting import cast as CAST
    out = []
    for aid, c in (ep.get('cast') or {}).items():
        if not isinstance(c, dict): continue
        ref = CAST.character(c.get('ref') or aid)
        look = (ref or {}).get('look') if isinstance(ref, dict) else None
        style = (c.get('hair_style') or (look or {}).get('hair_style') or 'short')
        c['hair_style'] = STRANDS.get(style, 'strands')
        out.append(f'{aid}: {style} -> {c["hair_style"]}')
    return out


def keys_in(ep):
    cast = {a: {k: v for k, v in c.items() if k in ('face_detail', 'detail', 'hair_style', 'hair2', 'iris')}
            for a, c in (ep.get('cast') or {}).items() if isinstance(c, dict)}
    return {'camera_clear_face': ep.get('camera_clear_face'), 'camera_face_track': ep.get('camera_face_track'),
            'cast': cast}


def cadrage(demo_json, episode_keys, cast_keys):
    """la mesure du defaut, sur de vraies images rendues hors video (tools/cadrage_qc.py)"""
    from cadrage_qc import build, measure, TIGHT
    ep, lines, eng = build(demo_json, ASPECT, episode_keys, cast_keys)
    rows = [r for r in measure(eng.ctx, lines[-1]['end'], .5) if r['kind'] in TIGHT]
    if not rows: return {}
    return {'images_serrees': len(rows),
            'bras_pct_moyen': round(100 * sum(r['bras'] for r in rows) / len(rows), 2),
            'bras_pct_pire': round(100 * max(r['bras'] for r in rows), 1),
            'tete_pct_moyen': round(100 * sum(r['tete'] for r in rows) / len(rows), 2),
            'visage_mange_pct_moyen': round(100 * sum(r['visage_mange'] for r in rows) / len(rows), 2),
            'visage_mange_pct_pire': round(100 * max(r['visage_mange'] for r in rows), 1)}


def one(demo_id, slug, title, readable, workers, quality):
    from hstudio import demos as D, pipeline as P, oneclick as OC, mediacheck as MC
    print('\n' + '=' * 78); print('== ' + title); print('=' * 78)
    res = {'demo': demo_id, 'slug': slug, 'title': title, 'aspect': ASPECT, 'quality': quality,
           'readable': bool(readable)}

    pr = D.prepare(demo_id, slug=slug, name=title)
    ep = pr.read_json('episode.json') or {}
    ep, done = apply_variant(ep, readable)
    if readable: done += readable_look(pr, ep)
    pr.write_json('episode.json', ep)
    for f in ('mix.wav', 'qc_9x16.json', 'qc_16x9.json'):
        if pr.exists(f): os.remove(pr.p(f))
    res['variant'] = done; res['keys'] = keys_in(ep); res['project_dir'] = pr.dir
    print('Variante : ' + ('; '.join(done) or 'aucune cle (reference)'))
    print('Cles relues sur episode.json : ' + json.dumps(res['keys'], ensure_ascii=False))

    import numpy as np
    lines = pr.read_json('lines.json') or []
    eng = P.make_engine('pixel3d', copy.deepcopy(ep), lines, np.zeros(10), P.duration_of(ep, lines), ASPECT)
    res['runtime'] = runtime_expressions(eng)

    s = dict(P.load_settings()); s['workers'] = workers; s['quality'] = quality
    t0 = time.time()
    OC.run(pr, settings=s, opts={'aspects': [ASPECT], 'quality': quality}, job=None)
    res['pipeline_seconds'] = round(time.time() - t0, 1)

    have = OC._renders_of(pr, ASPECT)
    if not have:
        res['error'] = 'aucun rendu lisible'; print('ARRET : aucun rendu lisible'); return res
    mp4 = pr.p('renders', have[0]); res['mp4'] = mp4

    print('\n-- verification (ffprobe puis decodage integral) --')
    v = MC.describe(mp4, want=WANT, full=True)
    res['verify'] = v
    print(MC.summary(v))
    if not v['ok']:
        res['error'] = 'fichier refuse : ' + v['reason']; return res

    dur = v['duration']
    res['sample_times'] = [round(dur * f, 2) for f in (0.06, 0.22, 0.38, 0.54, 0.70, 0.86, 0.96)]
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
                 'failing': sorted(k for k, c in (qc.get('checks') or {}).items()
                                   if not c.get('ok') and not c.get('info'))}
    print('   QC mise en scene : ' + str(res['qc']['score']) + '/100, reproches : '
          + (', '.join(res['qc']['failing']) or 'aucun'))
    res['ok'] = True
    return res


CASES = [
    ('demo6_continuite', 'p1v_demo6_a_defaut_20261024', 'A - demo 6, aucune cle (reference)', False),
    ('demo6_continuite', 'p1v_demo6_b_lisible_20261024', 'B - demo 6, cadrage lisible + visage expressif', True),
    ('demo20_decors', 'p1v_demo20_a_defaut_20261024', 'A - demo 20, aucune cle (reference)', False),
    ('demo20_decors', 'p1v_demo20_b_lisible_20261024', 'B - demo 20, cadrage lisible + visage expressif', True),
]


if __name__ == '__main__':
    from hstudio import ffmpeg_path as FF
    found = FF.ensure()
    miss = [t for t, p in found.items() if not p]
    if miss:
        print('ffmpeg introuvable (' + ', '.join(miss) + ') : ' + FF.INSTALL_HINT); sys.exit(1)
    print('ffmpeg : ' + found['ffmpeg'])

    args = sys.argv[1:]
    workers = int(args[args.index('--workers') + 1]) if '--workers' in args else 6
    quality = args[args.index('--quality') + 1] if '--quality' in args else 'standard'
    only = args[args.index('--only') + 1] if '--only' in args else ''
    os.makedirs(OUTDIR, exist_ok=True)
    print(f'workers = {workers} (sur {os.cpu_count()} coeurs logiques), qualite = {quality}')

    cases = [c for c in CASES if not only or c[0] == only]
    out, t0 = [], time.time()
    for demo_id, slug, title, readable in cases:
        try: out.append(one(demo_id, slug, title, readable, workers, quality))
        except Exception as e:
            import traceback; traceback.print_exc()
            out.append({'slug': slug, 'title': title, 'error': str(e)[:300]})

    # la mesure du defaut, hors video, pour chaque etage de la pile : c'est elle qui dit QUI apporte quoi
    print('\n' + '=' * 78); print('== le defaut mesure sur de vraies images (tools/cadrage_qc.py)')
    EXPR = [('face_detail', 'hd'), ('detail', True), ('hair2', list(HAIR2)), ('iris', list(IRIS))]
    steps = [('defaut', [], []),
             ('camera_face_track seul', [('camera_face_track', True)], []),
             ('camera_clear_face (= + le bras)', [('camera_clear_face', True)], []),
             ('cadrage lisible complet', [('camera_clear_face', True)], EXPR)]
    bench = {}
    for demo_id in sorted({c[0] for c in cases}):
        p = os.path.join(ROOT, 'examples', 'demos', demo_id + '.json')
        bench[demo_id] = {}
        print('\n  ' + demo_id)
        for lbl, eks, cks in steps:
            m = cadrage(p, eks, cks)
            bench[demo_id][lbl] = m
            print(f"    {lbl:34s} bras {m.get('bras_pct_moyen', 0):5.2f} % (pire {m.get('bras_pct_pire', 0):4.1f} %)"
                  f"  tete {m.get('tete_pct_moyen', 0):5.2f} %"
                  f"  visage mange {m.get('visage_mange_pct_moyen', 0):4.2f} % (pire {m.get('visage_mange_pct_pire', 0):4.1f} %)")

    by = {r['slug']: r for r in out if r.get('slug')}
    sheets = []
    for a_slug, b_slug, nm in (('p1v_demo6_a_defaut_20261024', 'p1v_demo6_b_lisible_20261024', 'ab_demo6_cadrage.png'),
                               ('p1v_demo20_a_defaut_20261024', 'p1v_demo20_b_lisible_20261024', 'ab_demo20_cadrage.png')):
        if by.get(a_slug, {}).get('ok') and by.get(b_slug, {}).get('ok'):
            import p1_proof
            p1_proof.OUTDIR = OUTDIR
            p = _ab_sheet(by[a_slug], by[b_slug], nm)
            if p: sheets.append(p)

    report = os.path.join(OUTDIR, 'mesures_p1_visuel_20261024.json')
    merged = {}
    if os.path.exists(report):
        try:
            for c in (json.load(open(report, encoding='utf-8')).get('cases') or []):
                if c.get('slug'): merged[c['slug']] = c
        except Exception: pass
    for c in out:
        if c.get('slug'): merged[c['slug']] = c
    json.dump({'when': time.strftime('%Y-%m-%d %H:%M:%S'), 'aspect': ASPECT, 'quality': quality,
               'workers': workers, 'sheets': sheets, 'cadrage': bench,
               'cases': [merged[k] for k in sorted(merged)]},
              open(report, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print('\n' + '=' * 78); print('BILAN  (%.0f s)' % (time.time() - t0))
    for r in out:
        v = r.get('verify') or {}
        if r.get('ok'):
            print('  OK    %s  %.2f s, %.1f Mo, %s+%s, QC %s/100'
                  % (os.path.basename(r['mp4']), v['duration'], v['size'] / 1e6,
                     v['video'], v['audio'], (r.get('qc') or {}).get('score')))
            print('        ' + r['mp4'])
        else:
            print('  ECHEC %s : %s' % (r.get('slug'), r.get('error')))
    for p in sheets: print('  planche A/B : ' + p)
    print('\nMesures : ' + report)
    sys.exit(0 if all(r.get('ok') for r in out) else 1)
