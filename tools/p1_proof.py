"""La preuve P1 : les deux acquis fusionnés, vus sur de vraies vidéos verticales, A contre B.

    python tools/p1_proof.py                      # les quatre variantes, 9:16
    python tools/p1_proof.py --workers 6
    python tools/p1_proof.py --only pixel3d

Même scénario, mêmes graines, même découpage, **un seul paramètre qui change** entre A et B. C'est tout l'intérêt
du parcours en un clic : la comparaison ne coûte qu'un rendu de plus.

| | moteur | scénario | A | B |
|---|---|---|---|---|
| décors + locomotion | pixel3d | `demo20_decors` (4 lieux, 4 marches) | aucune clé | `variation` + `approach` |
| locomotion seule | console | `demo5_console` | aucune clé | `approach` |

Chaque variante passe le **parcours complet** (voix de brouillon, calage, mixage, rendu, contrôle qualité,
titres, miniatures), puis est vérifiée comme en P0 : structure MP4, `ffprobe`, **décodage intégral**, images
réellement extraites du fichier final, piste audio décodée. Rien n'est déclaré bon avant la fin du décodage.

Honnêteté de la comparaison, deux réserves écrites ici parce qu'elles seront dans le rapport :

- les plans et les intentions de caméra sont identiques entre A et B (même scénario, mêmes graines), mais
  `approach` déplace légèrement les corps et leur minutage, et le cadreur réagit aux acteurs : **le cadre peut
  donc bouger un peu**. Ce n'est pas un défaut caché, c'est la conséquence de ce qu'on mesure ;
- les images sont extraites **en pleine résolution, sans recadrage ni zoom**. Un défaut reste visible.

Aucun réseau, aucune clé d'API, aucun coût : voix de brouillon locale.

Windows : corps derrière `if __name__ == '__main__'` (le rendu lance un pool « spawn » qui réimporte le module).
"""
import os, sys, json, copy, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))

from p0_proof import frame_stats, audio_stats, runtime_expressions          # noqa: E402

ASPECT = '9:16'
WANT = (1080, 1920)
OUTDIR = os.path.join(ROOT, 'docs', 'p1_preuve')


def strip_variation(ep):
    """variante A : le décor nu. On retire la clé d'habillage partout où elle se trouve (elle vit dans les sets)."""
    n = 0
    for spec in (ep.get('sets') or {}).values():
        if isinstance(spec, dict) and spec.pop('variation', None) is not None: n += 1
    return n


def apply_variant(ep, variation, approach):
    """renvoie (episode modifié, ce qui a été fait) -- une seule chose change entre A et B"""
    ep = copy.deepcopy(ep); done = []
    if not variation:
        k = strip_variation(ep)
        if k: done.append(f'habillage retiré de {k} décor(s)')
    else:
        k = sum(1 for s in (ep.get('sets') or {}).values() if isinstance(s, dict) and s.get('variation'))
        done.append(f'habillage gardé sur {k} décor(s)')
    if approach:
        ep['approach'] = 'directed'; done.append('locomotion dirigée activée')
    else:
        ep.pop('approach', None)
    return ep, done


def keys_in(ep):
    """les clés P1 réellement présentes dans l'épisode final, relues sur le fichier du projet"""
    sets = [k for k, s in (ep.get('sets') or {}).items() if isinstance(s, dict) and s.get('variation')]
    return {'approach': ep.get('approach'), 'footing': ep.get('footing'),
            'sets_with_variation': sorted(sets)}


def one(engine, demo_id, slug, title, variation, approach, workers, quality):
    from hstudio import demos as D, pipeline as P, oneclick as OC, mediacheck as MC
    print('\n' + '=' * 78); print('== ' + title); print('=' * 78)
    res = {'engine': engine, 'demo': demo_id, 'slug': slug, 'title': title, 'aspect': ASPECT,
           'quality': quality, 'variation': bool(variation), 'approach': bool(approach)}

    pr = D.prepare(demo_id, slug=slug, name=title)
    ep = pr.read_json('episode.json') or {}
    ep, done = apply_variant(ep, variation, approach)
    pr.write_json('episode.json', ep)
    for f in ('mix.wav', 'qc_9x16.json', 'qc_16x9.json'):      # la variante change la scène : on ne garde rien
        if pr.exists(f): os.remove(pr.p(f))
    res['variant'] = done; res['keys'] = keys_in(ep); res['project_dir'] = pr.dir
    print('Variante : ' + ('; '.join(done) or 'aucune clé (référence)'))
    print('Clés relues sur episode.json : ' + json.dumps(res['keys'], ensure_ascii=False))

    import numpy as np
    lines = pr.read_json('lines.json') or []
    eng = P.make_engine(engine, copy.deepcopy(ep), lines, np.zeros(10), P.duration_of(ep, lines), ASPECT)
    res['runtime'] = runtime_expressions(eng)
    print('Jeu mesuré : ' + json.dumps(res['runtime'], ensure_ascii=False)[:200])

    s = dict(P.load_settings()); s['workers'] = workers; s['quality'] = quality
    t0 = time.time()
    OC.run(pr, settings=s, opts={'aspects': [ASPECT], 'quality': quality}, job=None)
    res['pipeline_seconds'] = round(time.time() - t0, 1)

    have = OC._renders_of(pr, ASPECT)
    if not have:
        res['error'] = 'aucun rendu lisible'; print('ARRET : aucun rendu lisible'); return res
    mp4 = pr.p('renders', have[0]); res['mp4'] = mp4

    print('\n-- vérification (ffprobe puis décodage intégral) --')
    v = MC.describe(mp4, want=WANT, full=True)
    res['verify'] = v
    print(MC.summary(v))
    if not v['ok']:
        res['error'] = 'fichier refusé : ' + v['reason']; return res

    dur = v['duration']
    res['sample_times'] = [round(dur * f, 2) for f in (0.06, 0.22, 0.38, 0.54, 0.70, 0.86, 0.96)]
    rows, sheet = frame_stats(mp4, res['sample_times'], OUTDIR, slug)
    res['frames'] = rows; res['sheet'] = sheet
    for r in rows:
        print('   t=%6.2f s  %s' % (r['t'], r.get('error') or
              ('%dx%d  luminosité %6.2f  écart-type %6.2f' % (r['size'][0], r['size'][1], r['mean'], r['std']))))
    res['flat_frames'] = len([r for r in rows if 'std' in r and r['std'] < 3])
    res['audio'] = audio_stats(mp4, pr.p('work'))
    print('   audio : ' + json.dumps(res['audio'], ensure_ascii=False))

    qc = pr.read_json(OC._qc_file(ASPECT)) or {}
    res['qc'] = {'score': qc.get('score'), 'shots': qc.get('shots'), 'duration': qc.get('duration'),
                 'encoded_ok': (qc.get('encoded') or {}).get('ok'),
                 'failing': sorted(k for k, c in (qc.get('checks') or {}).items()
                                   if not c.get('ok') and not c.get('info'))}
    print('   QC mise en scène : ' + str(res['qc']['score']) + '/100, reproches : '
          + (', '.join(res['qc']['failing']) or 'aucun'))
    res['ok'] = True
    return res


def ab_sheet(a, b, name):
    """une planche A au-dessus de B, aux MEMES instants, en pleine image : rien n'est recadré ni zoomé"""
    from PIL import Image, ImageDraw
    fa = [r for r in (a.get('frames') or []) if r.get('file')]
    fb = [r for r in (b.get('frames') or []) if r.get('file')]
    if not fa or len(fa) != len(fb): return ''
    ims_a = [Image.open(os.path.join(OUTDIR, r['file'])).convert('RGB') for r in fa]
    ims_b = [Image.open(os.path.join(OUTDIR, r['file'])).convert('RGB') for r in fb]
    w, h = ims_a[0].size
    sc = 3
    tw, th = w // sc, h // sc
    band = 26
    sheet = Image.new('RGB', (tw * len(ims_a), th * 2 + band * 2), (16, 16, 18))
    d = ImageDraw.Draw(sheet)
    d.text((6, 6), 'A  ' + (a.get('title') or ''), fill=(235, 235, 235))
    for k, im in enumerate(ims_a): sheet.paste(im.resize((tw, th)), (k * tw, band))
    d.text((6, band + th + 6), 'B  ' + (b.get('title') or ''), fill=(235, 235, 235))
    for k, im in enumerate(ims_b): sheet.paste(im.resize((tw, th)), (k * tw, band * 2 + th))
    p = os.path.join(OUTDIR, name)
    sheet.save(p)
    return p


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
    print(f'workers = {workers} (sur {os.cpu_count()} coeurs logiques), qualité = {quality}')

    CASES = [
        ('pixel3d', 'demo20_decors', 'p1_decors_a_defaut_20261024',
         'A — décor nu, locomotion d\'origine (référence)', False, False),
        ('pixel3d', 'demo20_decors', 'p1_decors_b_options_20261024',
         'B — habillage « variation » + locomotion « approach »', True, True),
        ('console', 'demo5_console', 'p1_console2d_a_defaut_20261024',
         'A — CONSOLE 2D, aucune option (référence)', False, False),
        ('console', 'demo5_console', 'p1_console2d_b_approche_20261024',
         'B — CONSOLE 2D, locomotion « approach »', False, True),
    ]
    cases = [c for c in CASES if not only or c[0] == only]

    out, t0 = [], time.time()
    for engine, demo_id, slug, title, var, appr in cases:
        try: out.append(one(engine, demo_id, slug, title, var, appr, workers, quality))
        except Exception as e:
            import traceback; traceback.print_exc()
            out.append({'engine': engine, 'slug': slug, 'title': title, 'error': str(e)[:300]})

    by = {r['slug']: r for r in out if r.get('slug')}
    sheets = []
    for a_slug, b_slug, nm in (('p1_decors_a_defaut_20261024', 'p1_decors_b_options_20261024', 'ab_decors_locomotion.png'),
                               ('p1_console2d_a_defaut_20261024', 'p1_console2d_b_approche_20261024', 'ab_console2d_approche.png')):
        if by.get(a_slug, {}).get('ok') and by.get(b_slug, {}).get('ok'):
            p = ab_sheet(by[a_slug], by[b_slug], nm)
            if p: sheets.append(p)

    report = os.path.join(OUTDIR, 'mesures_p1_20261024.json')
    merged = {}
    if os.path.exists(report):
        try:
            for c in (json.load(open(report, encoding='utf-8')).get('cases') or []):
                if c.get('slug'): merged[c['slug']] = c
        except Exception: pass
    for c in out:
        if c.get('slug'): merged[c['slug']] = c
    json.dump({'when': time.strftime('%Y-%m-%d %H:%M:%S'), 'aspect': ASPECT, 'quality': quality,
               'workers': workers, 'sheets': sheets, 'cases': [merged[k] for k in sorted(merged)]},
              open(report, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print('\n' + '=' * 78); print('BILAN  (%.0f s)' % (time.time() - t0))
    for r in out:
        v = r.get('verify') or {}
        if r.get('ok'):
            print('  OK   %-9s %s  %.2f s, %.1f Mo, %s+%s, QC %s/100'
                  % (r['engine'], os.path.basename(r['mp4']), v['duration'], v['size'] / 1e6,
                     v['video'], v['audio'], (r.get('qc') or {}).get('score')))
            print('       ' + r['mp4'])
        else:
            print('  ECHEC %-9s %s : %s' % (r['engine'], r.get('slug'), r.get('error')))
    for p in sheets: print('  planche A/B : ' + p)
    print('\nMesures : ' + report)
    sys.exit(0 if all(r.get('ok') for r in out) else 1)
