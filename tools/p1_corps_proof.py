"""La preuve du lot P1 « corps » : le meme episode rendu deux fois, UNE seule chose change, sur de vrais MP4.

    python tools/p1_corps_proof.py --workers 8 --quality standard
    python tools/p1_corps_proof.py --only demo20_decors

| paire | A | B | ce qui change |
|---|---|---|---|
| `demo6_continuite` | cadrage lisible + visage expressif | la meme + `"body": "refit"` | **les proportions du corps, rien d'autre** |

A n'est PAS le rendu par defaut : c'est l'etat de l'art a la fin du lot P1 visuel (`camera_clear_face`, qui
entraine `camera_face_track`, plus le visage 48x48 et les meches). La paire « defaut contre cadrage lisible »
a deja ete rendue et mesuree au lot precedent (docs/P1_PROTOTYPE_VISUEL_20261024.md, § 5). Ici, A et B
partagent **toutes** ces cles et ne different que par `body`, sinon la comparaison mesurerait trois lots a la
fois. L'attribution etage par etage, elle, est dans `tools/corps_bench.py` et sur les planches.

Les couleurs des personnages ne changent pas entre A et B (meme sweat, meme peau, memes cheveux).

Chaque variante passe le parcours en un clic complet (voix de brouillon locale, calage, mixage, rendu, controle
qualite, titres, miniatures), puis est verifiee comme en P0 : structure MP4, `ffprobe`, **decodage integral**,
images reellement extraites du fichier final, piste audio decodee. Des copies legeres 540x960 sont ensuite
fabriquees dans `docs/p1_corps/leger/` et verifiees de la meme facon. Aucun reseau, aucune cle d'API, aucun cout,
AUCUNE publication.

Windows : corps derriere `if __name__ == '__main__'` (le rendu lance un pool « spawn »).
"""
import os, sys, json, copy, time, subprocess, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))

from p0_proof import frame_stats, audio_stats, runtime_expressions          # noqa: E402
from p1_proof import ab_sheet as _ab_sheet                                  # noqa: E402

ASPECT = '9:16'
WANT = (1080, 1920)
OUTDIR = os.path.join(ROOT, 'docs', 'p1_corps')
LIGHT = os.path.join(OUTDIR, 'leger')

STRANDS = {'ponytail': 'strands_ponytail', 'long': 'strands_long'}
HAIR2 = (150, 96, 58)
IRIS = (96, 140, 120)
BODY = 'minecraft'          # 'refit' (le corps humain avec cou) supprime le 31/10


def apply_variant(ep, refit):
    """-> (episode modifie, ce qui a ete fait). A et B ont les memes cles sauf `body`."""
    ep = copy.deepcopy(ep); done = []
    ep['camera_clear_face'] = True
    done.append('cadrage degage du bras (camera_clear_face, entraine camera_face_track)')
    n = 0
    for c in (ep.get('cast') or {}).values():
        if not isinstance(c, dict): continue
        c['face_detail'] = 'hd'; c['detail'] = True; c['hair2'] = list(HAIR2); c['iris'] = list(IRIS)
        n += 1
    done.append(f'visage 48x48 + meches + vetement nuance sur {n} personnage(s)')
    if refit:
        ep['body'] = BODY
        done.append(f'proportions du corps refondues ("body": "{BODY}") -- LA SEULE DIFFERENCE AVEC A')
    else:
        ep.pop('body', None)
    return ep, done


def readable_look(ep):
    """les meches ont besoin du style de coiffure du personnage, qui vit dans library/characters"""
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
    return {'body': ep.get('body'), 'camera_clear_face': ep.get('camera_clear_face'),
            'camera_face_track': ep.get('camera_face_track'), 'cast': cast}


def silhouette_of(preset):
    from corps_qc import silhouette, POSES, LOOK
    s = silhouette(POSES['debout'], LOOK, preset)
    return {k: s[k] for k in ('tetes', 'ep_haut', 'to_haut', 'tete_torse', 'cou', 'jonction', 'haut', 'ecart_humain', 'ecart_minecraft')}


def cadrage(demo_json, episode_keys, cast_keys):
    """la mesure hors video, sur de vraies images rendues (tools/cadrage_qc.py)"""
    from cadrage_qc import build, measure, TIGHT
    ep, lines, eng = build(demo_json, ASPECT, episode_keys, cast_keys)
    rows = [r for r in measure(eng.ctx, lines[-1]['end'], .5) if r['kind'] in TIGHT]
    if not rows: return {}
    n = len(rows)
    return {'images_serrees': n,
            'bras_pct_moyen': round(100 * sum(r['bras'] for r in rows) / n, 2),
            'bras_pct_pire': round(100 * max(r['bras'] for r in rows), 1),
            'tete_pct_moyen': round(100 * sum(r['tete'] for r in rows) / n, 2),
            'corps_pct_moyen': round(100 * sum(r['corps'] for r in rows) / n, 2),
            'visage_mange_pct_moyen': round(100 * sum(r['visage_mange'] for r in rows) / n, 2),
            'visage_mange_pct_pire': round(100 * max(r['visage_mange'] for r in rows), 1)}


def one(demo_id, slug, title, refit, workers, quality):
    from hstudio import demos as D, pipeline as P, oneclick as OC, mediacheck as MC
    print('\n' + '=' * 78); print('== ' + title); print('=' * 78)
    res = {'demo': demo_id, 'slug': slug, 'title': title, 'aspect': ASPECT, 'quality': quality, 'refit': bool(refit)}

    pr = D.prepare(demo_id, slug=slug, name=title)
    ep = pr.read_json('episode.json') or {}
    ep, done = apply_variant(ep, refit)
    done += readable_look(ep)
    pr.write_json('episode.json', ep)
    for f in ('mix.wav', 'qc_9x16.json', 'qc_16x9.json'):
        if pr.exists(f): os.remove(pr.p(f))
    res['variant'] = done; res['keys'] = keys_in(ep); res['project_dir'] = pr.dir
    res['silhouette'] = silhouette_of(BODY if refit else None)
    print('Variante : ' + '; '.join(done))
    print('Cles relues sur episode.json : ' + json.dumps(res['keys'], ensure_ascii=False))
    print('Silhouette : ' + json.dumps(res['silhouette'], ensure_ascii=False))

    import numpy as np
    lines = pr.read_json('lines.json') or []
    eng = P.make_engine('pixel3d', copy.deepcopy(ep), lines, np.zeros(10), P.duration_of(ep, lines), ASPECT)
    res['runtime'] = runtime_expressions(eng)
    res['body_preset'] = (eng.body or {}).get('name')
    print('Preset de corps relu sur le moteur : ' + str(res['body_preset']))

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
                 'faces_readable': round(float(((qc.get('checks') or {}).get('faces_readable') or {}).get('value', 0.)), 3),
                 'camera_blocked': ((qc.get('checks') or {}).get('camera_blocked') or {}).get('value'),
                 'failing': sorted(k for k, c in (qc.get('checks') or {}).items()
                                   if not c.get('ok') and not c.get('info')),
                 'trop_serre': [i['message'] for i in (qc.get('issues') or []) if 'trop serré' in i.get('message', '')]}
    print('   QC mise en scene : ' + str(res['qc']['score']) + '/100, visages lisibles '
          + str(res['qc']['faces_readable']) + ', reproches : ' + (', '.join(res['qc']['failing']) or 'aucun'))
    for m in res['qc']['trop_serre']: print('     ! ' + m)
    # les deux miniatures du parcours, tirees du moteur (ce ne sont PAS des images de reference artistique)
    res['vignettes'] = {}
    for src, dst in (('cover_9x16.jpg', slug + '_cover_9x16.jpg'), ('thumbnail_16x9.jpg', slug + '_thumbnail_16x9.jpg')):
        if pr.exists(src):
            os.makedirs(OUTDIR, exist_ok=True)
            shutil.copyfile(pr.p(src), os.path.join(OUTDIR, dst))
            res['vignettes'][dst] = os.path.getsize(pr.p(src))
    res['ok'] = True
    return res


def light_copy(mp4, slug):
    """copie 540x960 glissable a la main, mise a l'echelle au plus proche voisin (le pixel art reste net),
    puis VERIFIEE par decodage integral comme l'original. Aucune publication, aucun tunnel, aucun reseau."""
    from hstudio import ffmpeg_path as FF, mediacheck as MC
    os.makedirs(LIGHT, exist_ok=True)
    out = os.path.join(LIGHT, slug + '_540x960.mp4')
    # crf 30 : mesure, pas devinette -- a crf 23 la copie pesait 12,9 Mo, soit a peine moins que l'original,
    # ce qui lui otait sa seule raison d'exister (etre glissable a la main dans une conversation)
    cmd = [FF.ensure()['ffmpeg'], '-y', '-v', 'error', '-i', mp4,
           '-vf', 'scale=540:960:flags=neighbor', '-c:v', 'libx264', '-crf', '30', '-preset', 'medium',
           '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '64k', '-movflags', '+faststart', out]
    subprocess.run(cmd, check=True)
    v = MC.describe(out, want=(540, 960), full=True)
    return {'path': out, 'size': os.path.getsize(out), 'ok': v['ok'], 'reason': v.get('reason'),
            'duration': v.get('duration'), 'video': v.get('video'), 'audio': v.get('audio')}


CASES = [
    ('demo6_continuite', 'p1c_demo6_a_lisible_20261024', 'A - demo 6, cadrage lisible (sans body)', False),
    ('demo6_continuite', 'p1c_demo6_b_corps_20261031', 'B - demo 6, la meme + body: minecraft', True),
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
    # --leger-seul : refaire uniquement les copies 540x960 a partir des MP4 deja rendus (pas de re-rendu)
    if '--leger-seul' in args:
        bad, done = 0, []
        for demo_id, slug, title, refit in CASES:
            mp4 = os.path.join(ROOT, 'projects', slug, 'renders', slug + '_short_9x16.mp4')
            if not os.path.exists(mp4):
                print('  ABSENT ' + mp4); bad += 1; continue
            lc = light_copy(mp4, slug); done.append(lc)
            print(('  OK    ' if lc['ok'] else '  ECHEC ') + lc['path'] + f"   {lc['size']} o"
                  + ('' if lc['ok'] else '  ' + str(lc['reason'])))
            bad += 0 if lc['ok'] else 1
        rp = os.path.join(OUTDIR, 'mesures_p1_corps_20261024.json')     # les mesures disent la verite ou rien
        if done and os.path.exists(rp):
            d = json.load(open(rp, encoding='utf-8')); d['leger'] = done
            json.dump(d, open(rp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            print('  mesures mises a jour : ' + rp)
        sys.exit(1 if bad else 0)
    os.makedirs(OUTDIR, exist_ok=True)
    print(f'workers = {workers} (sur {os.cpu_count()} coeurs logiques), qualite = {quality}')

    cases = [c for c in CASES if not only or c[0] == only]
    out, t0 = [], time.time()
    for demo_id, slug, title, refit in cases:
        try: out.append(one(demo_id, slug, title, refit, workers, quality))
        except Exception as e:
            import traceback; traceback.print_exc()
            out.append({'slug': slug, 'title': title, 'error': str(e)[:300]})

    # la mesure hors video, etage par etage : c'est elle qui dit QUI apporte quoi
    print('\n' + '=' * 78); print('== les proportions mesurees hors video')
    EXPR = [('face_detail', 'hd'), ('detail', True), ('hair2', list(HAIR2)), ('iris', list(IRIS))]
    steps = [('defaut', [], []),
             ('cadrage lisible (= A)', [('camera_clear_face', True)], EXPR),
             ('A + body: minecraft (= B)', [('camera_clear_face', True), ('body', 'minecraft')], EXPR)]
    bench = {}
    for demo_id in sorted({c[0] for c in cases}):
        p = os.path.join(ROOT, 'examples', 'demos', demo_id + '.json')
        bench[demo_id] = {}
        print('\n  ' + demo_id)
        for lbl, eks, cks in steps:
            m = cadrage(p, eks, cks); bench[demo_id][lbl] = m
            print(f"    {lbl:24s} bras {m.get('bras_pct_moyen', 0):5.2f} % (pire {m.get('bras_pct_pire', 0):4.1f})"
                  f"  tete {m.get('tete_pct_moyen', 0):5.2f} %  corps {m.get('corps_pct_moyen', 0):5.2f} %"
                  f"  visage mange {m.get('visage_mange_pct_moyen', 0):4.2f} % (pire {m.get('visage_mange_pct_pire', 0):4.1f})")

    by = {r['slug']: r for r in out if r.get('slug')}
    sheets = []
    for a_slug, b_slug, nm in (('p1c_demo6_a_lisible_20261024', 'p1c_demo6_b_corps_20261024', 'ab_demo6_corps.png'),):
        if by.get(a_slug, {}).get('ok') and by.get(b_slug, {}).get('ok'):
            import p1_proof
            p1_proof.OUTDIR = OUTDIR
            p = _ab_sheet(by[a_slug], by[b_slug], nm)
            if p: sheets.append(p)

    print('\n-- copies legeres 540x960 (glissables a la main, AUCUNE publication) --')
    light = []
    for r in out:
        if r.get('ok'):
            try:
                lc = light_copy(r['mp4'], r['slug']); light.append(lc)
                print(('  OK    ' if lc['ok'] else '  ECHEC ') + lc['path'] + f"   {lc['size']} o"
                      + ('' if lc['ok'] else '  ' + str(lc['reason'])))
            except Exception as e:
                print('  ECHEC copie legere : ' + str(e)[:200])

    report = os.path.join(OUTDIR, 'mesures_p1_corps_20261024.json')
    json.dump({'when': time.strftime('%Y-%m-%d %H:%M:%S'), 'aspect': ASPECT, 'quality': quality,
               'workers': workers, 'sheets': sheets, 'cadrage': bench, 'leger': light,
               'cases': out}, open(report, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print('\n' + '=' * 78); print('BILAN  (%.0f s)' % (time.time() - t0))
    for r in out:
        v = r.get('verify') or {}
        if r.get('ok'):
            print('  OK    %s  %.2f s, %.1f Mo, %s+%s, QC %s/100'
                  % (os.path.basename(r['mp4']), v['duration'], v['size'] / 1e6, v['video'], v['audio'],
                     (r.get('qc') or {}).get('score')))
            print('        ' + r['mp4'])
        else:
            print('  ECHEC %s : %s' % (r.get('slug'), r.get('error')))
    for p in sheets: print('  planche A/B : ' + p)
    print('\nMesures : ' + report)
    sys.exit(0 if all(r.get('ok') for r in out) and all(l['ok'] for l in light) else 1)
