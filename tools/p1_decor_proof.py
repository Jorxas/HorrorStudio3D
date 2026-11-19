"""La preuve de ce lot : deux scenes, chacune rendue deux fois, sur de vrais MP4.

    python tools/p1_decor_proof.py --workers 5 --quality standard
    python tools/p1_decor_proof.py --leger-seul

| paire | A | B | ce qui change |
|---|---|---|---|
| `rue_entree` | le rendu livre | + `env: riche` + `finish: net_rapide` + `body: minecraft` | les facades, l'image, le corps |
| `foret_neige` | le rendu livre | les memes trois cles | l'image et le corps SEULEMENT |

DEUX SCENES, ET LA SECONDE EST UN CONTROLE NEGATIF. La rue est la demonstration : des immeubles avec des
fenetres encadrees, des portes, des briques et des tuyaux, trois plans de profondeur et une entree eclairee.
La foret n'a pas un seul batiment, donc la cle `env` n'y change RIEN par construction -- et c'est
exactement pourquoi elle est la : sans elle, rien ne distinguerait ce que les facades apportent de ce que la
finition d'image apportait deja au lot precedent. Une paire qui ne prouve que la moitie de ce qu'elle
affiche n'est pas une preuve.

B EMPILE TROIS CLES, et il faut le lire avant de regarder : `env` (ce lot), plus `finish` et `body` (le lot
precedent, deja mesures). C'est voulu -- le proprietaire a demande a voir l'ENSEMBLE, pas a departager des
reglages. Ce que `env` apporte SEUL se lit sur `docs/p1_decor/facades_rue.png` (meme image, meme cadrage,
seule la cle `env` change) et dans le banc de `tools/finish_bench.py`.

POURQUOI `net_rapide` ET NON `net` : MainClip tourne sur cette machine pendant ce lot. `net` coute 8,8 s par
image sur la rue et 14,5 s sur la foret, `net_rapide` 3,4 et 5,6 -- et le lot precedent a mesure que
`net_rapide` prend l'essentiel du gain de nettete. Monopoliser la machine pour le tiers de gain restant
n'etait pas raisonnable. Le choix est un choix de charge, pas de qualite, et il est reversible.

AUCUNE DES DEUX SCENES N'EST UNE DEMO LIVREE : elles vivent dans `examples/scenes/`, donc hors du catalogue
du studio et hors des suites de non-regression. Aucune demo livree n'est modifiee.

Chaque variante passe le parcours en un clic complet (voix de brouillon locale, calage, mixage, rendu,
controle qualite, titres, miniatures), puis est verifiee comme en P0 : structure MP4, `ffprobe`, **decodage
integral**, images reellement extraites du fichier final, piste audio decodee. Des copies legeres 540x960
sont fabriquees dans `docs/p1_decor/leger/` et verifiees de la meme facon. Aucun reseau, aucune cle d'API,
aucun cout, AUCUNE publication.

Windows : corps derriere `if __name__ == '__main__'` (le rendu lance un pool « spawn »).
"""
import os, sys, json, copy, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))

from p0_proof import frame_stats, audio_stats, runtime_expressions          # noqa: E402
from p1_proof import ab_sheet as _ab_sheet                                  # noqa: E402
import p1_corps_proof as PC                                                 # noqa: E402

ASPECT = '9:16'
WANT = (1080, 1920)
OUTDIR = os.path.join(ROOT, 'docs', 'p1_decor')
LIGHT = os.path.join(OUTDIR, 'leger')
SCENES = os.path.join(ROOT, 'examples', 'scenes')

ENV = 'riche'
FINISH = 'net_rapide'
BODY = 'minecraft'


def use_scene(path):
    """la scene d'essai est chargee a la place d'une demo du catalogue, sans rien ecrire dans examples/demos"""
    from hstudio import demos as D
    sc = json.load(open(path, encoding='utf-8'))
    D.load = lambda demo_id, _sc=sc: copy.deepcopy(_sc)
    return sc


def apply_variant(ep, apres):
    """A = le rendu livre ; B = le meme episode avec les trois cles opt-in, et rien d'autre"""
    ep = copy.deepcopy(ep); done = []
    if apres:
        ep['env'] = ENV; ep['finish'] = FINISH; ep['body'] = BODY
        done.append(f'façades détaillées ("env": "{ENV}") -- LA CLE DE CE LOT')
        done.append(f'image nette ("finish": "{FINISH}") -- lot précédent')
        done.append(f'corps cubique ("body": "{BODY}") -- lot précédent')
    else:
        for k in ('env', 'finish', 'body'): ep.pop(k, None)
        done.append('aucune clé : le rendu livré')
    return ep, done


def keys_in(ep):
    return {'env': ep.get('env'), 'finish': ep.get('finish'), 'body': ep.get('body'),
            'lighting': ep.get('lighting'), 'weather': ep.get('weather')}


def one(scene_file, slug, title, apres, workers, quality):
    from hstudio import demos as D, pipeline as P, oneclick as OC, mediacheck as MC
    from hstudio.engines.pixel3d import r3d
    import numpy as np
    print('\n' + '=' * 78); print('== ' + title); print('=' * 78)
    res = {'scene': scene_file, 'slug': slug, 'title': title, 'aspect': ASPECT, 'quality': quality,
           'apres': bool(apres)}

    use_scene(os.path.join(SCENES, scene_file))
    pr = D.prepare(os.path.splitext(scene_file)[0], slug=slug, name=title)
    ep = pr.read_json('episode.json') or {}
    ep, done = apply_variant(ep, apres)
    pr.write_json('episode.json', ep)
    for f in ('mix.wav', 'qc_9x16.json', 'qc_16x9.json'):
        if pr.exists(f): os.remove(pr.p(f))
    res['variant'] = done; res['keys'] = keys_in(ep); res['project_dir'] = pr.dir
    print('Variante : ' + '; '.join(done))
    print('Cles relues sur episode.json : ' + json.dumps(res['keys'], ensure_ascii=False))

    lines = pr.read_json('lines.json') or []
    eng = P.make_engine('pixel3d', copy.deepcopy(ep), lines, np.zeros(10), P.duration_of(ep, lines), ASPECT)
    res['runtime'] = runtime_expressions(eng)
    res['env_preset'] = (eng.env or {}).get('name')
    res['env_ppm'] = (eng.env or {}).get('ppm')
    res['finish_preset'] = (eng.fin or {}).get('name')
    res['body_preset'] = (eng.body or {}).get('name')
    res['raster'] = [int(r3d.RW), int(r3d.RH)]
    # Combien de murs portent vraiment une facade, et combien de texels en tout : sans ce chiffre, une video
    # B identique a A passerait pour une preuve. C'est aussi ce qui rend le controle negatif lisible -- la
    # foret doit afficher ZERO des deux cotes.
    st = eng.ctx.get_set(ep.get('default_set', 'etage_zero'))
    try:
        sc_ = st.scene({}, 0., 0.)
        n_tex = sum(1 for b in sc_.boxes if getattr(b, 'tex', None))
        px = int(sum(sum(t.shape[0] * t.shape[1] for t in b.tex.values())
                     for b in sc_.boxes if getattr(b, 'tex', None)))
        n_box = len(sc_.boxes)
    except Exception as exc:
        n_tex = px = n_box = None
        print('   (comptage des murs impossible : ' + str(exc)[:90] + ')')
    res['murs_textures'] = n_tex; res['texels_facades'] = px; res['boites'] = n_box
    print(f"Relu sur le moteur : env={res['env_preset']} ({res['env_ppm']} texels/m) "
          f"finish={res['finish_preset']} body={res['body_preset']} "
          f"raster={res['raster'][0]}x{res['raster'][1]}")
    print(f"   murs textures : {n_tex} / {n_box} boites, {px} texels de facade au total")

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
    import numpy as _np
    from PIL import Image as _I
    tn, lum = [], []
    for r in rows:
        if not r.get('file'): continue
        a = _np.asarray(_I.open(os.path.join(OUTDIR, r['file'])).convert('RGB'))
        q = a.reshape(-1, 3).astype(_np.uint32)
        tn.append(int(_np.unique(q[:, 0] * 65536 + q[:, 1] * 256 + q[:, 2]).size))
        lum.append(float((a.astype(_np.float32) * _np.array([.3, .59, .11])).sum(-1).mean()))
    res['teintes_moy'] = int(sum(tn) / len(tn)) if tn else None
    res['luminance_moy'] = round(sum(lum) / len(lum), 2) if lum else None
    print('   couleurs distinctes (moyenne des 7 images du MP4) : %s   luminance moyenne : %s'
          % (res['teintes_moy'], res['luminance_moy']))
    res['audio'] = audio_stats(mp4, pr.p('work'))
    print('   audio : ' + json.dumps(res['audio'], ensure_ascii=False))

    qc = pr.read_json(OC._qc_file(ASPECT)) or {}
    res['qc'] = {'score': qc.get('score'), 'shots': qc.get('shots'), 'duration': qc.get('duration'),
                 'encoded_ok': (qc.get('encoded') or {}).get('ok'),
                 'faces_readable': round(float(((qc.get('checks') or {}).get('faces_readable') or {}).get('value', 0.)), 3),
                 'camera_blocked': ((qc.get('checks') or {}).get('camera_blocked') or {}).get('value'),
                 'failing': sorted(k for k, c in (qc.get('checks') or {}).items()
                                   if not c.get('ok') and not c.get('info'))}
    print('   QC mise en scene : ' + str(res['qc']['score']) + '/100, visages lisibles '
          + str(res['qc']['faces_readable']) + ', reproches : ' + (', '.join(res['qc']['failing']) or 'aucun'))
    res['vignettes'] = {}
    import shutil
    for src, dst in (('cover_9x16.jpg', slug + '_cover_9x16.jpg'), ('thumbnail_16x9.jpg', slug + '_thumbnail_16x9.jpg')):
        if pr.exists(src):
            os.makedirs(OUTDIR, exist_ok=True)
            shutil.copyfile(pr.p(src), os.path.join(OUTDIR, dst))
            res['vignettes'][dst] = os.path.getsize(pr.p(src))
    res['ok'] = True
    return res


CASES = [
    ('rue_entree.json', 'p1d_rue_a_livre_20261025', 'A - la rue, le rendu livre', False),
    ('rue_entree.json', 'p1d_rue_b_decor_20261025', 'B - la rue, facades detaillees + image nette', True),
    ('foret_neige.json', 'p1d_foret_a_livre_20261025', 'A - la foret, le rendu livre', False),
    ('foret_neige.json', 'p1d_foret_b_decor_20261025', 'B - la foret, les memes cles (controle negatif)', True),
]
PAIRS = [('p1d_rue_a_livre_20261025', 'p1d_rue_b_decor_20261025', 'ab_rue_decor.png'),
         ('p1d_foret_a_livre_20261025', 'p1d_foret_b_decor_20261025', 'ab_foret_decor.png')]


if __name__ == '__main__':
    from hstudio import ffmpeg_path as FF
    found = FF.ensure()
    miss = [t for t, p in found.items() if not p]
    if miss:
        print('ffmpeg introuvable (' + ', '.join(miss) + ') : ' + FF.INSTALL_HINT); sys.exit(1)
    print('ffmpeg : ' + found['ffmpeg'])
    PC.LIGHT = LIGHT
    args = sys.argv[1:]
    workers = int(args[args.index('--workers') + 1]) if '--workers' in args else 5
    quality = args[args.index('--quality') + 1] if '--quality' in args else 'standard'
    only = args[args.index('--only') + 1] if '--only' in args else ''
    report = os.path.join(OUTDIR, 'mesures_p1_decor_20261025.json')

    if '--leger-seul' in args:
        bad, done = 0, []
        for scene_file, slug, title, apres in CASES:
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

    os.makedirs(OUTDIR, exist_ok=True)
    print(f'workers = {workers} (sur {os.cpu_count()} coeurs logiques), qualite = {quality}')
    print('workers volontairement limites : MainClip tourne sur cette machine pendant ce lot')
    out, t0 = [], time.time()
    for scene_file, slug, title, apres in CASES:
        if only and only not in slug: continue
        try: out.append(one(scene_file, slug, title, apres, workers, quality))
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
            if p: sheets.append(p)

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

    json.dump({'when': time.strftime('%Y-%m-%d %H:%M:%S'), 'aspect': ASPECT, 'quality': quality,
               'workers': workers, 'env': ENV, 'finish': FINISH, 'body': BODY,
               'sheets': sheets, 'leger': light, 'cases': out},
              open(report, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print('\n' + '=' * 78); print('BILAN  (%.0f s)' % (time.time() - t0))
    for r in out:
        v = r.get('verify') or {}
        if r.get('ok'):
            print('  OK    %s  %.2f s, %.1f Mo, %s+%s, QC %s/100, raster %dx%d, parcours %.0f s'
                  % (os.path.basename(r['mp4']), v['duration'], v['size'] / 1e6, v['video'], v['audio'],
                     (r.get('qc') or {}).get('score'), r['raster'][0], r['raster'][1], r['pipeline_seconds']))
            print('        ' + r['mp4'])
        else:
            print('  ECHEC %s : %s' % (r.get('slug'), r.get('error')))
    for p in sheets: print('  planche A/B : ' + p)
    print('\nMesures : ' + report)
    sys.exit(0 if all(r.get('ok') for r in out) and all(l['ok'] for l in light) else 1)
