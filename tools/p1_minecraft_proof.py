"""La preuve de ce lot : deux scenes, chacune rendue deux fois, sur de vrais MP4.

    python tools/p1_minecraft_proof.py --workers 8 --quality standard
    python tools/p1_minecraft_proof.py --leger-seul

| paire | A | B | ce qui change |
|---|---|---|---|
| `couloir_poignee` | le rendu livre | + `"body": "minecraft"` + `"finish": "net"` | le corps cubique et l'image nette |
| `ruelle_pluie` | le rendu livre | idem | la meme chose sur un decor profond, sous la pluie |

DEUX SCENES PARCE QU'ELLES NE MONTRENT PAS LA MEME CHOSE. Le couloir est serre sur un visage : c'est la que
les proportions du corps et la grosse tete cubique se jugent. La ruelle est un exterieur de nuit avec de la
pluie, une lumiere froide et une ville au fond : c'est la que le raster natif de 216x384 se voit le plus,
parce qu'un arriere-plan lointain est exactement ce qu'un agrandissement x5 au plus proche voisin detruit.
Une seule des deux aurait prouve la moitie du lot.

B CHANGE DEUX CHOSES A LA FOIS, et il faut le lire avant de regarder : le corps ET l'image. Ce n'est pas une
mesure, c'est une demonstration -- le proprietaire a demande a voir la limite de qualite, pas a departager
deux reglages. Les deux sont separes ligne par ligne sur `docs/p1_minecraft/corps_minecraft.png` (le corps
seul, puis le corps plus l'image) et chiffres separement par `tools/corps_qc.py` et `tools/finish_bench.py`.

AUCUNE DES DEUX SCENES N'EST UNE DEMO LIVREE : elles vivent dans `examples/scenes/`, donc hors du catalogue
du studio et hors des suites de non-regression. Aucune demo livree n'est modifiee.

Chaque variante passe le parcours en un clic complet (voix de brouillon locale, calage, mixage, rendu,
controle qualite, titres, miniatures), puis est verifiee comme en P0 : structure MP4, `ffprobe`, **decodage
integral**, images reellement extraites du fichier final, piste audio decodee. Des copies legeres 540x960
sont fabriquees dans `docs/p1_minecraft/leger/` et verifiees de la meme facon. Aucun reseau, aucune cle
d'API, aucun cout, AUCUNE publication.

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
OUTDIR = os.path.join(ROOT, 'docs', 'p1_minecraft')
LIGHT = os.path.join(OUTDIR, 'leger')
SCENES = os.path.join(ROOT, 'examples', 'scenes')

BODY = 'minecraft'
FINISH = 'net'


def use_scene(path):
    """la scene d'essai est chargee a la place d'une demo du catalogue, sans rien ecrire dans examples/demos"""
    from hstudio import demos as D
    sc = json.load(open(path, encoding='utf-8'))
    D.load = lambda demo_id, _sc=sc: copy.deepcopy(_sc)
    return sc


def apply_variant(ep, apres):
    """A = le rendu livre ; B = le meme episode avec les deux cles opt-in de ce lot, et rien d'autre"""
    ep = copy.deepcopy(ep); done = []
    if apres:
        ep['body'] = BODY; ep['finish'] = FINISH
        done.append(f'corps cubique ("body": "{BODY}") -- grosse tete carree, pas de cou, membres epais')
        done.append(f'image nette ("finish": "{FINISH}") -- raster natif x3, palette supprimee, lanczos')
    else:
        ep.pop('body', None); ep.pop('finish', None)
        done.append('aucune cle : le rendu livre, raster 216x384 agrandi x5 au plus proche voisin')
    return ep, done


def keys_in(ep):
    return {'body': ep.get('body'), 'finish': ep.get('finish'),
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
    res['body_preset'] = (eng.body or {}).get('name')
    res['finish_preset'] = (eng.fin or {}).get('name')
    res['raster'] = [int(r3d.RW), int(r3d.RH)]
    res['rayons'] = int(r3d.RW * r3d.RH)
    print(f"Relu sur le moteur : body={res['body_preset']} finish={res['finish_preset']} "
          f"raster={res['raster'][0]}x{res['raster'][1]} ({res['rayons']} rayons par image)")

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
    # la mesure de CE lot, lue sur les images reellement extraites du MP4 final : la part de paires de
    # pixels voisins egales, signature arithmetique de l'agrandissement au plus proche voisin
    import numpy as _np
    from PIL import Image as _I
    fl = []
    for r in rows:
        if not r.get('file'): continue
        a = _np.asarray(_I.open(os.path.join(OUTDIR, r['file'])).convert('RGB'))
        fl.append(float(_np.all(a[:, 1:] == a[:, :-1], axis=-1).mean()))
    res['plats'] = round(sum(fl) / len(fl), 4) if fl else None
    print('   paires de pixels voisins egales (sur les images du MP4) : '
          + (f'{100 * res["plats"]:.1f} %' if res['plats'] is not None else 'n/a'))
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
    ('couloir_poignee.json', 'p1m_couloir_a_livre_20261025', 'A - le couloir, le rendu livre', False),
    ('couloir_poignee.json', 'p1m_couloir_b_proto_20261025', 'B - le couloir, corps cubique + image nette', True),
    ('ruelle_pluie.json', 'p1m_ruelle_a_livre_20261025', 'A - la ruelle sous la pluie, le rendu livre', False),
    ('ruelle_pluie.json', 'p1m_ruelle_b_proto_20261025', 'B - la ruelle, corps cubique + image nette', True),
]
PAIRS = [('p1m_couloir_a_livre_20261025', 'p1m_couloir_b_proto_20261025', 'ab_couloir_minecraft.png'),
         ('p1m_ruelle_a_livre_20261025', 'p1m_ruelle_b_proto_20261025', 'ab_ruelle_minecraft.png')]


if __name__ == '__main__':
    from hstudio import ffmpeg_path as FF
    found = FF.ensure()
    miss = [t for t, p in found.items() if not p]
    if miss:
        print('ffmpeg introuvable (' + ', '.join(miss) + ') : ' + FF.INSTALL_HINT); sys.exit(1)
    print('ffmpeg : ' + found['ffmpeg'])
    PC.LIGHT = LIGHT                       # les copies legeres de CE lot vont dans docs/p1_minecraft/leger
    args = sys.argv[1:]
    workers = int(args[args.index('--workers') + 1]) if '--workers' in args else 6
    quality = args[args.index('--quality') + 1] if '--quality' in args else 'standard'
    only = args[args.index('--only') + 1] if '--only' in args else ''
    report = os.path.join(OUTDIR, 'mesures_p1_minecraft_20261025.json')

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
               'workers': workers, 'body': BODY, 'finish': FINISH,
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
