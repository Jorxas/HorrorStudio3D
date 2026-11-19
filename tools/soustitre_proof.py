"""Preuve filmee des sous-titres surs : deux vraies videos 9:16 h264+aac, AUX MEMES SECONDES du meme
scenario, une sans la cle `caption_safe` et une avec. Plus une planche A/B des memes images, et la mesure
du recouvrement bouche/tete sur chacune.

    python tools/soustitre_proof.py --workers 2
    python tools/soustitre_proof.py --workers 2 --only avant
    python tools/soustitre_proof.py --leger-seul            (les copies 540x960 depuis les mp4 deja rendus)

CE QUI EST REUTILISE, et ce n'est pas un detail : tout le pipeline de preuve existe deja et il n'est pas
duplique ici. `p0_proof.frame_stats` / `audio_stats` extraient et mesurent les images, `p1_proof.ab_sheet`
assemble la planche aux memes instants, `p1_corps_proof.light_copy` fabrique la copie 540x960,
`hstudio.mediacheck.describe(full=True)` decode le fichier EN ENTIER, `hstudio.oneclick.run` rend. Ce
fichier n'ajoute que la variable testee : la cle `caption_safe`, posee puis retiree.

LE SCENARIO EST STABLE ET DEJA CONNU : `examples/scenes/portrait_peur.json`, la scene d'essai du lot voxel
premium du 25/10 -- quatre plans serres sur deux visages, c'est-a-dire exactement la situation ou le
proprietaire a vu le bandeau couvrir les bouches. Le corps est `voxel_premium`, le meme que les cinq
videos de ce lot-la. UNE SEULE CLE change d'un cote a l'autre.

LE DERNIER RENDU VALIDE DE `studio-integration` N'EST PAS TOUCHE : tout sort dans des repertoires neufs,
`projects/st_*_20261025/` et `docs/sous_titres/`.

CE QUE CE FICHIER NE PROUVE PAS. Il prouve que les fichiers existent, se decodent entierement, durent ce
qu'ils annoncent, et que le recouvrement mesure du bandeau sur les bouches tombe a zero. Il ne dit RIEN de
la valeur artistique du resultat : ou doit tomber un sous-titre est un jugement d'oeil, et il appartient
au proprietaire. Un controle informatique vert n'est pas une validation artistique -- c'est pourquoi
l'option reste opt-in.

IL NE CORRIGE PAS LE CRANE COUPE. Le haut du crane parfois coupe et les cheveux lateraux qui masquent le
visage sont des defauts de CADRAGE ; ils appartiennent au lot camera et ils sont encore visibles sur les
deux cotes de la planche A/B. Section "defauts non traites" du rapport.

Windows : corps derriere `if __name__ == '__main__'` (le rendu lance un pool « spawn »).
"""
import os, sys, json, copy, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))

from p0_proof import frame_stats, audio_stats                              # noqa: E402
from p1_proof import ab_sheet as _ab_sheet                                 # noqa: E402
import p1_corps_proof as PC                                                # noqa: E402

ASPECT = '9:16'
WANT = (1080, 1920)
OUTDIR = os.path.join(ROOT, 'docs', 'sous_titres')
LIGHT = os.path.join(OUTDIR, 'leger')
SCENES = os.path.join(ROOT, 'examples', 'scenes')
SCENE = 'portrait_peur.json'
BODY = 'voxel_premium'                 # le corps des cinq videos du 25/10 ou le defaut a ete vu


def use_scene(path):
    """la scene d'essai est chargee a la place d'une demo du catalogue, sans rien ecrire dans examples/demos"""
    from hstudio import demos as D
    sc = json.load(open(path, encoding='utf-8'))
    D.load = lambda demo_id, _sc=sc: copy.deepcopy(_sc)
    return sc


def apply_variant(ep, caption_safe):
    """UNE SEULE cle change d'une variante a l'autre : `caption_safe`. Tout le reste est le MEME episode."""
    ep = copy.deepcopy(ep)
    ep.pop('finish', None)                         # la finition couterait le carre du raster : hors sujet ici
    ep['body'] = BODY
    if caption_safe:
        ep['caption_safe'] = caption_safe
    else:
        ep.pop('caption_safe', None)
    return ep, [f'caption_safe {caption_safe!r}' if caption_safe else 'caption_safe ABSENTE (bandeau livre)']


def one(slug, title, caption_safe, workers, quality):
    from hstudio import demos as D, pipeline as P, oneclick as OC, mediacheck as MC
    from hstudio.engines.pixel3d import r3d
    import numpy as np
    print('\n' + '=' * 78); print('== ' + title); print('=' * 78)
    res = {'scene': SCENE, 'slug': slug, 'title': title, 'aspect': ASPECT, 'quality': quality,
           'caption_safe': caption_safe, 'body': BODY}

    use_scene(os.path.join(SCENES, SCENE))
    pr = D.prepare(os.path.splitext(SCENE)[0], slug=slug, name=title)
    ep = pr.read_json('episode.json') or {}
    ep, done = apply_variant(ep, caption_safe)
    pr.write_json('episode.json', ep)
    for f in ('mix.wav', 'qc_9x16.json', 'qc_16x9.json'):
        if pr.exists(f):
            os.remove(pr.p(f))
    res['variant'] = done
    res['keys'] = {'caption_safe': ep.get('caption_safe'), 'body': ep.get('body'),
                   'finish': ep.get('finish')}
    res['project_dir'] = pr.dir
    print('Variante : ' + '; '.join(done))
    print('Cle relue sur episode.json : caption_safe='
          + json.dumps(ep.get('caption_safe'), ensure_ascii=False)
          + '  body=' + json.dumps(ep.get('body'), ensure_ascii=False))

    lines = pr.read_json('lines.json') or []
    eng = P.make_engine('pixel3d', copy.deepcopy(ep), lines, np.zeros(10), P.duration_of(ep, lines), ASPECT)
    res['raster'] = [int(r3d.RW), int(r3d.RH)]
    res['body_preset'] = (eng.body or {}).get('name')
    # la preuve que la cle est passee jusqu'au MOTEUR, pas seulement jusqu'au fichier episode.json
    res['caps_actif'] = eng.caps is not None
    print(f"Relu sur le moteur : caption_safe actif = {res['caps_actif']}, "
          f"body={res['body_preset']}, raster={res['raster'][0]}x{res['raster'][1]}")

    # le plan de bandes, et la mesure du recouvrement aux memes instants des deux cotes
    import soustitre_qc as Q
    t0 = time.time()
    rows = Q.measure(eng, ASPECT, 2, {})
    res['qc_soustitres'] = rows
    res['qc_seconds'] = round(time.time() - t0, 1)
    n = max(1, len(rows))
    res['qc_resume'] = dict(
        n=len(rows),
        bouche=round(sum(r['bouche'] for r in rows) / n, 4),
        bouche_max=round(max([r['bouche'] for r in rows] or [0.]), 4),
        tete=round(sum(r['tete'] for r in rows) / n, 4),
        hors=round(sum(r['hors'] for r in rows) / n, 4),
        images_bouche=len([r for r in rows if r['bouche'] > .001]),
        images_tete=len([r for r in rows if r['tete'] > .001]),
        bandes=sorted({r['band'] for r in rows}))
    print('Recouvrement mesure : bouche %.2f %% (pire %.1f %%, %d/%d images), tete %.2f %%, '
          'hors zone sure %.2f %%, bandes %s'
          % (100 * res['qc_resume']['bouche'], 100 * res['qc_resume']['bouche_max'],
             res['qc_resume']['images_bouche'], res['qc_resume']['n'],
             100 * res['qc_resume']['tete'], 100 * res['qc_resume']['hors'],
             ', '.join(res['qc_resume']['bandes'])))
    if eng.caps is not None:
        res['plan'] = {str(k): {kk: vv for kk, vv in p.items() if kk not in ('zones', 'tried', 'info')}
                       for k, p in (eng.caps.get('_plan') or {}).items()}
        for k, p in sorted(res['plan'].items()):
            print(f"   plan {k} : demande \"{p.get('declared')}\" -> bande \"{p.get('band')}\" "
                  f"y={p.get('y_px')}  libre={p.get('clear')}  {p.get('reason')}")

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
    res['sample_times'] = [round(dur * f, 2) for f in (0.08, 0.26, 0.44, 0.62, 0.80, 0.94)]
    frows, sheet = frame_stats(mp4, res['sample_times'], OUTDIR, slug)
    res['frames'] = frows; res['sheet'] = sheet
    for r in frows:
        print('   t=%6.2f s  %s' % (r['t'], r.get('error') or
              ('%dx%d  luminosite %6.2f  ecart-type %6.2f' % (r['size'][0], r['size'][1], r['mean'], r['std']))))
    res['audio'] = audio_stats(mp4, pr.p('work'))
    print('   audio : ' + json.dumps(res['audio'], ensure_ascii=False))

    qc = pr.read_json(OC._qc_file(ASPECT)) or {}
    res['qc'] = {'score': qc.get('score'), 'shots': qc.get('shots'), 'duration': qc.get('duration'),
                 'encoded_ok': (qc.get('encoded') or {}).get('ok'),
                 'faces_readable': round(float(((qc.get('checks') or {}).get('faces_readable') or {}).get('value', 0.)), 3),
                 'failing': sorted(k for k, c in (qc.get('checks') or {}).items()
                                   if not c.get('ok') and not c.get('info'))}
    print('   QC mise en scene : ' + str(res['qc']['score']) + '/100, visages lisibles '
          + str(res['qc']['faces_readable']) + ', reproches : ' + (', '.join(res['qc']['failing']) or 'aucun'))
    res['ok'] = True
    return res


CASES = [
    ('st_sstitre_a_avant_20261025', 'A - AVANT : le bandeau livre (aucune cle "caption_safe")', None),
    ('st_sstitre_b_apres_20261025', 'B - APRES : "caption_safe": "auto"', 'auto'),
]
PAIRS = [('st_sstitre_a_avant_20261025', 'st_sstitre_b_apres_20261025', 'ab_soustitres_portrait.png')]


if __name__ == '__main__':
    from hstudio import ffmpeg_path as FF
    found = FF.ensure()
    miss = [t for t, p in found.items() if not p]
    if miss:
        print('ffmpeg introuvable (' + ', '.join(miss) + ') : ' + FF.INSTALL_HINT); sys.exit(1)
    print('ffmpeg : ' + found['ffmpeg'])
    PC.LIGHT = LIGHT                       # les copies legeres de CE lot vont dans docs/sous_titres/leger
    args = sys.argv[1:]
    workers = int(args[args.index('--workers') + 1]) if '--workers' in args else 2
    quality = args[args.index('--quality') + 1] if '--quality' in args else 'standard'
    only = args[args.index('--only') + 1] if '--only' in args else ''
    report = os.path.join(OUTDIR, 'mesures_soustitres_20261025.json')
    os.makedirs(OUTDIR, exist_ok=True)

    if '--leger-seul' in args:
        bad, done = 0, []
        for slug, title, cs in CASES:
            mp4 = os.path.join(ROOT, 'projects', slug, 'renders', slug + '_short_9x16.mp4')
            if not os.path.exists(mp4):
                print('  ABSENT ' + mp4); bad += 1; continue
            lc = PC.light_copy(mp4, slug); done.append(lc)
            print(('  OK    ' if lc['ok'] else '  ECHEC ') + lc['path'] + f"   {lc['size']} o"
                  + ('' if lc['ok'] else '  ' + str(lc['reason'])))
            bad += 0 if lc['ok'] else 1
        if done and os.path.exists(report):
            d = json.load(open(report, encoding='utf-8')); d['leger'] = done
            json.dump(d, open(report, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            print('  mesures mises a jour : ' + report)
        sys.exit(1 if bad else 0)

    print(f'workers = {workers} (sur {os.cpu_count()} coeurs logiques), qualite = {quality}')
    print('CPU partage avec d\'autres missions : 2 workers est le plafond voulu, pas une limite machine.')
    out, t0 = [], time.time()
    for slug, title, cs in CASES:
        if only and only not in slug:
            continue
        try:
            out.append(one(slug, title, cs, workers, quality))
        except Exception as e:
            import traceback; traceback.print_exc()
            out.append({'slug': slug, 'title': title, 'error': str(e)[:300]})

    by = {r['slug']: r for r in out if r.get('slug')}
    sheets = []
    for a_slug, b_slug, name in PAIRS:
        if by.get(a_slug, {}).get('ok') and by.get(b_slug, {}).get('ok'):
            import p1_proof
            p1_proof.OUTDIR = OUTDIR
            p = _ab_sheet(by[a_slug], by[b_slug], name)
            if p:
                sheets.append(p)
                print('\nplanche A/B (memes instants, pleine image) -> ' + p)

    print('\n-- copies legeres 540x960 (glissables a la main, AUCUNE publication) --')
    light = []
    for r in out:
        if r.get('ok'):
            try:
                lc = PC.light_copy(r['mp4'], r['slug']); light.append(lc)
                print(('  OK    ' if lc['ok'] else '  ECHEC ') + lc['path'] + f"   {lc['size']} o"
                      + ('' if lc['ok'] else '  ' + str(lc['reason'])))
            except Exception as e:
                print('  ECHEC copie legere : ' + str(e)[:200])

    # le verdict chiffre : le meme scenario, les memes instants, une seule cle de difference
    verdict = {}
    a, b = by.get(CASES[0][0]), by.get(CASES[1][0])
    if a and b and a.get('qc_resume') and b.get('qc_resume'):
        ra, rb = a['qc_resume'], b['qc_resume']
        verdict = dict(images=ra['n'],
                       bouche_avant=ra['bouche'], bouche_apres=rb['bouche'],
                       bouche_max_avant=ra['bouche_max'], bouche_max_apres=rb['bouche_max'],
                       tete_avant=ra['tete'], tete_apres=rb['tete'],
                       images_bouche_avant=ra['images_bouche'], images_bouche_apres=rb['images_bouche'],
                       images_tete_avant=ra['images_tete'], images_tete_apres=rb['images_tete'],
                       hors_avant=ra['hors'], hors_apres=rb['hors'],
                       bandes_avant=ra['bandes'], bandes_apres=rb['bandes'],
                       secondes_avant=a.get('pipeline_seconds'), secondes_apres=b.get('pipeline_seconds'))

    json.dump({'when': time.strftime('%Y-%m-%d %H:%M:%S'), 'aspect': ASPECT, 'quality': quality,
               'workers': workers, 'scene': SCENE, 'body': BODY, 'sheets': sheets, 'leger': light,
               'verdict': verdict, 'cases': out},
              open(report, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print('\n' + '=' * 78); print('BILAN  (%.0f s)' % (time.time() - t0))
    for r in out:
        print(('  OK    ' if r.get('ok') else '  ECHEC ') + r['slug']
              + ('' if r.get('ok') else '   ' + str(r.get('error'))))
        if r.get('mp4'):
            print('        ' + r['mp4'])
    if verdict:
        print('\n  LE BANDEAU SUR LES BOUCHES, memes instants, une seule cle de difference :')
        print('    bouche couverte  %6.2f %%  ->  %6.2f %%' % (100 * verdict['bouche_avant'],
                                                               100 * verdict['bouche_apres']))
        print('    images touchees  %d/%d      ->  %d/%d' % (verdict['images_bouche_avant'], verdict['images'],
                                                             verdict['images_bouche_apres'], verdict['images']))
        print('    tete couverte    %6.2f %%  ->  %6.2f %%' % (100 * verdict['tete_avant'],
                                                               100 * verdict['tete_apres']))
        print('    hors zone sure   %6.2f %%  ->  %6.2f %%' % (100 * verdict['hors_avant'],
                                                               100 * verdict['hors_apres']))
    print('  mesures : ' + report)
    sys.exit(0 if all(r.get('ok') for r in out) else 1)
