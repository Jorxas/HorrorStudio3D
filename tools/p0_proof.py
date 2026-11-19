"""La preuve P0 : deux vraies vidéos courtes, une par moteur, mesurées sur le fichier et non sur la parole.

    python tools/p0_proof.py                      # les deux moteurs, 9:16
    python tools/p0_proof.py --workers 4          # part de processeur réduite (une autre branche rend en même temps)
    python tools/p0_proof.py --only pixel3d

Ce que cet outil refuse de faire, parce que la session précédente s'y est brûlée : conclure avant la fin. Un MP4
n'est déclaré bon que lorsque `ffprobe` **et** un décodage complet ont terminé sans une erreur. Le fichier de
48 octets qui a motivé tout ce chantier passait tous les tests « rapides ».

Ce qui est mesuré, dans cet ordre :

1. le parcours en un clic complet sur un scénario **non trivial** du catalogue (plusieurs plans, deux acteurs,
   plusieurs expressions et postures), sous un **nom de projet neuf** : aucun rendu existant n'est touché ;
2. le fichier : structure MP4, ffprobe, puis **décodage intégral** ;
3. des images réellement extraites du MP4 final (pas du moteur) : luminosité moyenne et écart-type par image,
   pour qu'un plan noir ou figé ne puisse pas passer pour une vidéo ;
4. la piste audio décodée du MP4 final : crête, RMS, part de silence. Mesurer n'est pas écouter, et ce
   fichier ne prétend pas le contraire — il dit des chiffres, le jugement reste humain ;
5. le contrôle qualité de la mise en scène, et le nombre d'expressions et de postures distinctes réellement
   demandées par l'épisode.

Le style **par défaut** est utilisé. Aucune direction artistique opt-in n'est activée : ni `art`, ni `hd` /
`face_detail`, ni `lighting`, ni `eyeline` / `footing`, ni `faces: expressive`, ni `sfx_library`. L'outil
vérifie cette absence et s'arrête si une clé apparaît. Activer un style est une décision humaine.

Aucun réseau, aucune clé, aucun coût : voix de brouillon locale.

Windows : le corps est derrière `if __name__ == '__main__'` à dessein — le rendu lance un pool « spawn » et un
worker réimporte le module principal. C'est ainsi qu'un premier MP4 tronqué est né sans erreur visible.
"""
import os, sys, json, subprocess, time, wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)

# scénarios du catalogue, style par défaut (surtout pas demo11/12/13 : ce sont les prototypes artistiques)
# `demo9_tempete`, `demo8_ravin` et `demo7_toits` sont plus fournis mais leur scénario demande `sfx_library` :
# c'est une option opt-in, donc ils sont exclus d'une preuve « style par défaut ». `demo3_groupe` est le
# scénario PIXEL 3D non trivial le plus riche qui n'en demande aucune : quatre personnages, dont un animal.
CASES = [
    ('pixel3d', 'demo3_groupe', 'p0_groupe_pixel3d_20261024', 'P0 — Groupe (PIXEL 3D, style par défaut)'),
    ('console', 'demo5_console', 'p0_console2d_20261024', 'P0 — Console (CONSOLE 2D, style par défaut)'),
]
OPTIN = ('art', 'hd', 'face_detail', 'lighting', 'eyeline', 'footing', 'sfx_library', 'camera_face_track', 'palette')
ASPECT = '9:16'
WANT = (1080, 1920)


def optin_keys(ep):
    """toute clé opt-in présente dans l'épisode, à n'importe quelle profondeur"""
    found = set()

    def walk(n):
        if isinstance(n, dict):
            for k, v in n.items():
                if k in OPTIN and v not in (None, False, ''): found.add(k)
                if k == 'faces' and v == 'expressive': found.add('faces: expressive')
                walk(v)
        elif isinstance(n, list):
            for v in n: walk(v)
    walk(ep)
    return sorted(found)


def expressions(ep):
    """les expressions et postures distinctes que l'épisode demande vraiment (pas une promesse, une lecture)"""
    faces, poses, moves, shots = set(), set(), set(), 0

    def walk(n):
        nonlocal shots
        if isinstance(n, dict):
            for k, v in n.items():
                if isinstance(v, str):
                    if k == 'face': faces.add(v)
                    elif k in ('posture', 'pose', 'hold'): poses.add(v)
                    elif k in ('move', 'action', 'gesture'): moves.add(v)
                walk(v)
        elif isinstance(n, list):
            for v in n: walk(v)
    walk(ep)
    shots = len(ep.get('shots') or [])
    return {'shots': shots, 'faces': sorted(faces), 'postures': sorted(poses), 'actions': sorted(moves)}


def runtime_expressions(engine, step=.2):
    """Ce que la couche de jeu produit **vraiment** image après image, et non ce que le scénario a épinglé.

    Un scénario peut ne fixer aucune expression et donner malgré tout un épisode vivant : les visages, les
    objets tenus et la direction du regard sont décidés par `hstudio/acting` à partir du dialogue. On les
    recense donc en échantillonnant la timeline, acteur par acteur."""
    ac = engine.ctx.get_acting() if hasattr(engine, 'ctx') else getattr(engine, 'acting', None)
    tl = engine.ctx.tl if hasattr(engine, 'ctx') else engine.tl
    if ac is None or not getattr(ac, 'shots', None): return {}
    faces, holds, gazes, actors, talk, pairs = set(), set(), set(), set(), set(), set()
    end = tl.spans[-1][1] if tl.spans else 0.
    t = 0.
    while t < end:
        k, t0, t1 = tl.at(t)
        if k in ac.shots:
            for a, st in (ac.shots[k].sample(t - t0) or {}).items():
                actors.add(a)
                if st.get('face'): faces.add(st['face']); pairs.add((a, st['face']))
                if st.get('hold'): holds.add(st['hold'])
                if st.get('gaze'): gazes.add(str(st['gaze']))
                if st.get('talking'): talk.add(a)
        t += step
    return {'sampled_every_s': step, 'actors': sorted(actors), 'speaking_actors': sorted(talk),
            'faces': sorted(faces), 'holds': sorted(holds), 'gazes': sorted(gazes),
            'distinct_actor_face_pairs': len(pairs)}


def frame_stats(mp4, times, outdir, tag):
    """extrait de vraies images du MP4 final et les mesure. Un plan noir ou figé ne doit pas passer."""
    from PIL import Image
    import numpy as np
    os.makedirs(outdir, exist_ok=True)
    rows, thumbs = [], []
    for k, t in enumerate(times):
        png = os.path.join(outdir, f'{tag}_t{t:06.2f}.png'.replace(' ', '0'))
        r = subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', f'{t:.3f}', '-i', mp4, '-frames:v', '1', png],
                           capture_output=True, text=True)
        if r.returncode or not os.path.exists(png):
            rows.append({'t': round(t, 2), 'error': (r.stderr or 'image non extraite').strip()[:120]}); continue
        im = Image.open(png).convert('RGB')
        a = np.asarray(im, dtype=np.float32)
        rows.append({'t': round(t, 2), 'size': list(im.size), 'mean': round(float(a.mean()), 2),
                     'std': round(float(a.std()), 2), 'file': os.path.basename(png)})
        thumbs.append(im.resize((im.width // 4, im.height // 4)))
    if thumbs:                                          # une planche pour que le propriétaire regarde vite
        tw, th = thumbs[0].size
        sheet = Image.new('RGB', (tw * len(thumbs), th))
        for k, im in enumerate(thumbs): sheet.paste(im, (k * tw, 0))
        sheet_path = os.path.join(outdir, tag + '_planche.png'); sheet.save(sheet_path)
    else:
        sheet_path = ''
    return rows, sheet_path


def audio_stats(mp4, workdir):
    """décode la piste audio du MP4 **final** et la mesure : crête, RMS, part de silence."""
    import numpy as np
    os.makedirs(workdir, exist_ok=True)
    wav = os.path.join(workdir, 'audio_mesure.wav')
    r = subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', mp4, '-vn', '-ac', '2', '-ar', '44100',
                        '-c:a', 'pcm_s16le', wav], capture_output=True, text=True)
    if r.returncode or not os.path.exists(wav):
        return {'error': (r.stderr or 'audio non décodé').strip()[:200]}
    with wave.open(wav, 'rb') as w:
        n, ch, sr = w.getnframes(), w.getnchannels(), w.getframerate()
        raw = w.readframes(n)
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.
    if a.size == 0: return {'error': 'piste audio vide'}
    mono = a.reshape(-1, ch).mean(axis=1) if ch > 1 else a
    peak = float(np.abs(mono).max())
    rms = float(np.sqrt((mono ** 2).mean()))
    win = max(1, sr // 20)                              # fenêtres de 50 ms
    k = (mono.size // win) * win
    env = np.sqrt((mono[:k].reshape(-1, win) ** 2).mean(axis=1)) if k else np.array([rms])
    db = lambda x: round(20 * float(np.log10(max(x, 1e-9))), 2)
    out = {'channels': ch, 'sample_rate': sr, 'seconds': round(mono.size / sr, 2),
           'peak_dbfs': db(peak), 'rms_dbfs': db(rms),
           'silence_ratio_50ms': round(float((env < 10 ** (-60 / 20)).mean()), 4),
           'loud_windows_ratio': round(float((env > 10 ** (-30 / 20)).mean()), 4)}
    try: os.remove(wav)
    except OSError: pass
    return out


def one(engine, demo_id, slug, title, workers, quality):
    from hstudio import demos as D, pipeline as P, oneclick as OC, mediacheck as MC
    print('\n' + '=' * 78)
    print('== ' + title)
    print('=' * 78)
    res = {'engine': engine, 'demo': demo_id, 'slug': slug, 'title': title, 'aspect': ASPECT, 'quality': quality}

    pr = D.prepare(demo_id, slug=slug, name=title)
    res['project_dir'] = pr.dir
    ep = pr.read_json('episode.json') or {}
    res['expressions'] = expressions(ep)
    res['optin_keys'] = optin_keys(ep)
    print('Scénario (clés épinglées) : ' + json.dumps(res['expressions'], ensure_ascii=False))
    if res['optin_keys']:
        print('ARRÊT : une option opt-in est présente dans l\'épisode : ' + ', '.join(res['optin_keys']))
        res['error'] = 'option opt-in présente'; return res
    print('Aucune option artistique opt-in : style par défaut confirmé.')

    import numpy as np
    lines = pr.read_json('lines.json') or []
    eng = P.make_engine(engine, ep, lines, np.zeros(10), P.duration_of(ep, lines), ASPECT)
    res['runtime_expressions'] = runtime_expressions(eng)
    print('Jeu mesuré sur la timeline : ' + json.dumps(res['runtime_expressions'], ensure_ascii=False))

    s = dict(P.load_settings()); s['workers'] = workers; s['quality'] = quality
    opts = {'aspects': [ASPECT], 'quality': quality}
    t0 = time.time()
    OC.run(pr, settings=s, opts=opts, job=None)
    res['pipeline_seconds'] = round(time.time() - t0, 1)

    have = OC._renders_of(pr, ASPECT)
    if not have:
        print('ARRÊT : aucun rendu lisible produit.'); res['error'] = 'aucun rendu lisible'; return res
    mp4 = pr.p('renders', have[0])
    res['mp4'] = mp4

    print('\n-- vérification du fichier (ffprobe puis décodage intégral ; cela prend le temps qu\'il faut) --')
    t0 = time.time()
    v = MC.describe(mp4, want=WANT, full=True)
    res['verify'] = v; res['verify_seconds'] = round(time.time() - t0, 1)
    print(MC.summary(v))
    if not v['ok']:
        res['error'] = 'fichier refusé : ' + v['reason']; return res

    dur = v['duration']
    times = [dur * f for f in (0.04, 0.2, 0.36, 0.52, 0.68, 0.84, 0.96)]
    print('\n-- images extraites du MP4 final --')
    rows, sheet = frame_stats(mp4, times, os.path.join(ROOT, 'docs', 'p0_preuve'), slug)
    res['frames'] = rows; res['sheet'] = sheet
    for r in rows:
        print('   t=%6.2f s  %s' % (r['t'], r.get('error') or
              ('%dx%d  luminosité moyenne %6.2f  écart-type %6.2f' % (r['size'][0], r['size'][1], r['mean'], r['std']))))
    flat = [r for r in rows if 'std' in r and r['std'] < 3]
    res['flat_frames'] = len(flat)
    print('   images plates (écart-type < 3, donc quasi uniformes) : ' + str(len(flat)) + ' sur ' + str(len(rows)))

    print('\n-- piste audio décodée du MP4 final --')
    res['audio'] = audio_stats(mp4, pr.p('work'))
    print('   ' + json.dumps(res['audio'], ensure_ascii=False))

    qc = pr.read_json(OC._qc_file(ASPECT)) or {}
    res['qc'] = {'score': qc.get('score'), 'shots': qc.get('shots'), 'duration': qc.get('duration'),
                 'encoded_ok': (qc.get('encoded') or {}).get('ok'),
                 'failing': sorted(k for k, c in (qc.get('checks') or {}).items() if not c.get('ok') and not c.get('info'))}
    print('\n-- contrôle qualité (mise en scène) : ' + str(res['qc']['score']) + '/100, reproches : '
          + (', '.join(res['qc']['failing']) or 'aucun'))

    md = pr.read_json('metadata.json') or {}
    res['metadata'] = {'titles': len(md.get('titles') or []), 'platforms': sorted((md.get('platforms') or {}).keys()),
                       'choices': len(((md.get('platforms') or {}).get('choices')) or [])}
    print('-- métadonnées : ' + json.dumps(res['metadata'], ensure_ascii=False))
    res['ok'] = True
    return res


if __name__ == '__main__':
    from hstudio import ffmpeg_path as FF
    found = FF.ensure()
    miss = [t for t, p in found.items() if not p]
    if miss:
        print('ffmpeg introuvable (' + ', '.join(miss) + ') : ' + FF.INSTALL_HINT); sys.exit(1)
    print('ffmpeg  : ' + found['ffmpeg'])
    print('ffprobe : ' + found['ffprobe'])

    args = sys.argv[1:]
    workers = int(args[args.index('--workers') + 1]) if '--workers' in args else 6
    quality = args[args.index('--quality') + 1] if '--quality' in args else 'standard'
    only = args[args.index('--only') + 1] if '--only' in args else ''
    cases = [c for c in CASES if not only or c[0] == only]
    print('workers = ' + str(workers) + ' (sur ' + str(os.cpu_count()) + ' coeurs logiques), qualité = ' + quality)

    out, t0 = [], time.time()
    for engine, demo_id, slug, title in cases:
        try: out.append(one(engine, demo_id, slug, title, workers, quality))
        except Exception as e:
            import traceback; traceback.print_exc()
            out.append({'engine': engine, 'demo': demo_id, 'slug': slug, 'error': str(e)[:300]})

    report = os.path.join(ROOT, 'docs', 'p0_preuve', 'mesures_p0_20261024.json')
    os.makedirs(os.path.dirname(report), exist_ok=True)
    # On fusionne par `slug` au lieu d'écraser : une relance `--only <moteur>` effaçait sinon, en silence, les
    # mesures de l'autre moteur -- et le rapport se serait retrouvé à parler d'une preuve qu'il n'avait plus.
    merged = {}
    if os.path.exists(report):
        try:
            for c in (json.load(open(report, encoding='utf-8')).get('cases') or []):
                if c.get('slug'): merged[c['slug']] = c
        except Exception: pass
    for c in out:
        if c.get('slug'): merged[c['slug']] = c
    json.dump({'when': time.strftime('%Y-%m-%d %H:%M:%S'), 'aspect': ASPECT, 'quality': quality,
               'workers': workers, 'cases': [merged[k] for k in sorted(merged)]},
              open(report, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print('\n' + '=' * 78)
    print('BILAN  (' + ('%.0f' % (time.time() - t0)) + ' s)')
    for r in out:
        v = r.get('verify') or {}
        if r.get('ok'):
            print('  OK   ' + r['engine'] + ' ' + ASPECT + ' : ' + os.path.basename(r['mp4'])
                  + '  ' + ('%.2f' % v['duration']) + ' s, ' + ('%.1f' % (v['size'] / 1e6)) + ' Mo, '
                  + v['video'] + '+' + v['audio'] + ', QC ' + str((r.get('qc') or {}).get('score')) + '/100')
            print('       ' + r['mp4'])
        else:
            print('  ÉCHEC ' + r['engine'] + ' : ' + str(r.get('error')))
    print('\nMesures : ' + report)
    print('Planches : ' + os.path.join(ROOT, 'docs', 'p0_preuve'))
    sys.exit(0 if all(r.get('ok') for r in out) else 1)
