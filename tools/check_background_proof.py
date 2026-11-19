"""La preuve de ce lot : deux vraies videos 9:16, une planche VIDE / VIVANTE a camera epinglee, et le cout.

    python tools/check_background_proof.py --workers 2 --quality standard
    python tools/check_background_proof.py --planche-seule        # la planche et le cout, sans refaire les videos
    python tools/check_background_proof.py --leger-seul           # les copies 540x960 d'une video deja faite

| moitie | scene | ce qui change |
|---|---|---|
| A | `examples/scenes/extras_rue_vide.json`    | la rue, Lea, l'eclair, l'ombre -- personne d'autre |
| B | `examples/scenes/extras_rue_vivante.json` | la MEME chose plus la cle `"extras"` : quatre figurants |

Chaque moitie passe le parcours en un clic complet (voix de brouillon locale et gratuite, calage, mixage, rendu,
controle qualite, titres, miniatures), puis est verifiee comme les lots precedents : structure MP4, `ffprobe`,
DECODAGE INTEGRAL, images reellement extraites du fichier final, piste audio decodee. Des copies legeres
540x960 sont fabriquees et verifiees de la meme facon. Aucun reseau, aucune cle d'API, aucun cout, AUCUNE
PUBLICATION.

LA PLANCHE EST RENDUE A PART, AVEC UNE CAMERA FIXE DU MONDE, ET VOICI POURQUOI. Aucune INTENTION de camera ne
donne le meme objectif des deux cotes : le solveur place une camera en cherchant, et il ecarte les positions ou
un corps non-sujet gene (`blocked_at`), donc quatre figurants deplacent l'objectif meme quand `"on"` ne nomme que
Lea -- 5,19 m mesures. Un POV, lui, suit la TETE du sujet, et `ShotActing.raw_head()` fait jeter un oeil aux
passants : 0,84 et 0,91 rad d'ecart sur deux plans sur quatre, et sur les deux autres le POV ne montrait aucun
figurant (un cadre 9:16 est etroit, les trottoirs sont a +-5 m). La planche remplace donc la camera par UN tuple
fixe dans le vrai chemin de rendu : meme decor, meme lumiere, meme etalonnage, meme finition, meme raster.
Et elle ne se CONTENTE PAS de le promettre : `r3d.render` est espionne pendant la planche, la camera que le
lanceur de rayons recoit vraiment est enregistree des deux cotes, et la planche dit en clair si les deux
moities ont bien recu le meme tuple aux memes instants. L'ecart du solveur reste mesure et imprime a cote,
parce que c'est un resultat de ce lot et pas un detail d'outillage.

Windows : corps derriere `if __name__ == '__main__'` (le rendu lance un pool « spawn »).
"""
import os, sys, json, copy, time, argparse
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from p0_proof import frame_stats, audio_stats, runtime_expressions          # noqa: E402
import p1_corps_proof as PC                                                 # noqa: E402
from locomotion_qc import read_scene                                        # noqa: E402
from hstudio.acting import background as BG                                 # noqa: E402

ASPECT = '9:16'
WANT = (1080, 1920)
OUTDIR = os.path.join(ROOT, 'docs', 'figurants')
LIGHT = os.path.join(OUTDIR, 'leger')
SCENES = os.path.join(ROOT, 'examples', 'scenes')
STAMP = '20261025'

# THE CAMERA OF THE COMPARISON PLATE IS NOT A CAMERA OF THE FILM, and it is fixed in the world on purpose.
# Two attempts came before it and both failed, which is why the number is written here instead of a promise:
#   - `{"shot": "establishing", "on": ["lea"], "from": "crossing"}` -> the two halves land 5.19 m apart. The
#     solver PLACES a camera by searching, and one term of that search (`blocked_at`, engines/pixel3d/acted.py)
#     refuses positions where a body that is not a subject stands in the way: four figurants move the lens.
#   - `{"shot": "pov", "on": ["lea"]}` -> identical on two shots out of four, 0.84 and 0.91 rad apart on the
#     other two. A POV is computed from the subject's eye AND HEAD, and `ShotActing.raw_head()` makes a
#     speaking character glance at the nearest person: Lea looks at the passers-by, so her POV turns with them.
#     And on the two shots where it was identical, the POV showed no figurant at all -- a 9:16 frame is narrow,
#     the pavements are at +-5 m, they fall outside it. A plate that shows no difference proves nothing.
# So the plate substitutes ONE camera tuple, the same in both halves by construction, into the real render path
# (`render.build_frame` is wrapped for the time of the call and nothing else is touched: same scene, same lights,
# same grade, same finish, same raster). The images are `raw_frame`, i.e. without HUD or subtitles, because what
# is compared is a street and not a caption.
FIXED_CAM = ((0.0, 2.55, -1.40), 0.0, 0.085, 0.0, 74.0)      # (position, lacet, tangage, roulis, focale)
PLATE_SHOTS = (0, 1, 2, 3)        # one plate image per shot, at 55 % of the shot
# kept because the figure is a finding worth reporting, not because the plate uses it
PIN_CAMERA_TRIED = {'shot': 'pov', 'on': ['lea'], 'fov': 72}

CASES = [
    ('extras_rue_vide.json',    f'extras_rue_a_vide_{STAMP}',    'A - la rue vide, personne dans la ville'),
    ('extras_rue_vivante.json', f'extras_rue_b_vivante_{STAMP}', 'B - la meme rue, quatre figurants'),
]


def use_scene(path):
    """la scene d'essai est chargee a la place d'une demo du catalogue, sans rien ecrire dans examples/demos"""
    from hstudio import demos as D
    sc = json.load(open(path, encoding='utf-8'))
    D.load = lambda demo_id, _sc=sc: copy.deepcopy(_sc)
    return sc


def one(scene_file, slug, title, workers, quality):
    from hstudio import demos as D, pipeline as P, oneclick as OC, mediacheck as MC
    from hstudio.engines.pixel3d import r3d
    print('\n' + '=' * 78)
    print('== ' + title)
    print('=' * 78)
    res = {'scene': scene_file, 'slug': slug, 'title': title, 'aspect': ASPECT, 'quality': quality,
           'workers': workers}

    use_scene(os.path.join(SCENES, scene_file))
    pr = D.prepare(os.path.splitext(scene_file)[0], slug=slug, name=title)
    ep = pr.read_json('episode.json') or {}
    res['extras_key'] = ep.get('extras')
    res['project_dir'] = pr.dir
    for f in ('mix.wav', 'qc_9x16.json', 'qc_16x9.json'):
        if pr.exists(f):
            os.remove(pr.p(f))
    print('Cle "extras" relue sur episode.json : '
          + ('absente (moitie A)' if not ep.get('extras') else json.dumps(ep['extras'], ensure_ascii=False)[:200]))

    lines = pr.read_json('lines.json') or []
    eng = P.make_engine('pixel3d', copy.deepcopy(ep), lines, np.zeros(10), P.duration_of(ep, lines), ASPECT)
    res['runtime'] = runtime_expressions(eng)
    res['body_preset'] = (eng.body or {}).get('name')
    res['finish_preset'] = (eng.fin or {}).get('name')
    res['raster'] = [int(r3d.RW), int(r3d.RH)]
    res['cast'] = sorted((eng.ctx.ep.get('cast') or {}).keys())
    plan = BG.report(eng.ctx.ep)
    res['plan'] = plan
    print(f"Moteur : corps={res['body_preset']} image={res['finish_preset']} "
          f"raster={res['raster'][0]}x{res['raster'][1]}   distribution : {', '.join(res['cast'])}")
    if plan:
        print('Figurants ecrits par background.py :')
        for (s, f, what, t) in plan['steps']:
            print(f'   plan {s}  t={t:5.2f} s  {f:<9} {what}')

    s = dict(P.load_settings())
    s['workers'] = workers
    s['quality'] = quality
    t0 = time.time()
    OC.run(pr, settings=s, opts={'aspects': [ASPECT], 'quality': quality}, job=None)
    res['pipeline_seconds'] = round(time.time() - t0, 1)

    have = OC._renders_of(pr, ASPECT)
    if not have:
        res['error'] = 'aucun rendu lisible'
        print('ARRET : aucun rendu lisible')
        return res
    mp4 = pr.p('renders', have[0])
    res['mp4'] = mp4

    print('\n-- verification (ffprobe puis decodage integral) --')
    v = MC.describe(mp4, want=WANT, full=True)
    res['verify'] = v
    print(MC.summary(v))
    if not v['ok']:
        res['error'] = 'fichier refuse : ' + v['reason']
        return res

    dur = v['duration']
    res['sample_times'] = [round(dur * f, 2) for f in (0.08, 0.24, 0.40, 0.56, 0.70, 0.86, 0.96)]
    rows, sheet = frame_stats(mp4, res['sample_times'], OUTDIR, slug)
    res['frames'] = rows
    res['sheet'] = sheet
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
                 'failing': sorted(k for k, c in (qc.get('checks') or {}).items()
                                   if not c.get('ok') and not c.get('info'))}
    print('   QC mise en scene : ' + str(res['qc']['score']) + '/100, visages lisibles '
          + str(res['qc']['faces_readable']) + ', reproches : ' + (', '.join(res['qc']['failing']) or 'aucun'))
    res['ok'] = True
    return res


# ------------------------------------------------------------------ the pinned-camera plate
def fixed_camera_frames(scene_file, tag):
    """rend une image par plan avec FIXED_CAM -> ([fichiers], [temps de rendu], [corps dans le cadre])

    `render.build_frame` est enveloppe pour la duree de l'appel et SEULE la camera est remplacee : la scene,
    les lumieres, l'etalonnage, la finition et le raster restent ceux du rendu de production."""
    from hstudio.pipeline import make_engine, duration_of
    from hstudio.engines.pixel3d import render as RND, r3d
    path = os.path.join(SCENES, scene_file)
    ep, lines = read_scene(path)
    dur = duration_of(ep, lines)
    eng = make_engine(ep.get('style', 'pixel3d'), ep, lines, np.zeros(10), dur, ASPECT)
    os.makedirs(OUTDIR, exist_ok=True)
    files, secs, seen, times, used = [], [], [], [], []
    orig = RND.build_frame
    orig_render = r3d.render

    def patched(ctx, g):
        out = list(orig(ctx, g))
        out[1] = FIXED_CAM
        return tuple(out)

    def spy(sc, cam, lights=None):
        # la camera telle qu'elle arrive VRAIMENT au lanceur de rayons, pas celle qu'on croit lui donner :
        # c'est la seule forme de la phrase « les deux moities ont la meme camera » qui soit verifiable.
        used.append((tuple(float(v) for v in np.ravel(cam[0])),) + tuple(float(v) for v in cam[1:]))
        return orig_render(sc, cam, lights=lights)

    RND.build_frame = patched
    r3d.render = spy
    try:
        for k in PLATE_SHOTS:
            a, b = eng.ctx.tl.spans[k]
            t = a + (b - a) * .55
            times.append(round(float(t), 6))
            t0 = time.time()
            im = eng.raw_frame(float(t)).convert('RGB')      # sans HUD ni sous-titres : on compare une rue
            secs.append(round(time.time() - t0, 2))
            p = os.path.join(OUTDIR, f'planche_{tag}_plan{k}.png')
            im.save(p)
            files.append(p)
            # qui est dans ce cadre fixe, et de quelle taille
            sa = eng.ctx.get_acting().shots[k]
            sm = sa.sample(max(0., min(t - a, sa.dur)))
            pos, yaw, pitch, roll, fov = FIXED_CAM
            row = {}
            for aid, v in sm.items():
                top = r3d.project(pos, yaw, pitch, roll, fov, (v['x'], 1.75, v['z']))
                foot = r3d.project(pos, yaw, pitch, roll, fov, (v['x'], 0., v['z']))
                if top[2] <= 0 or abs((top[0] + foot[0]) / 2) > 1.0:
                    continue
                row[aid] = int(round(abs(top[1] - foot[1]) / 2 * 1920))
            seen.append(row)
            print(f'   {tag}  plan {k}  t={t:6.2f} s  {im.size}  {secs[-1]:5.2f} s   dans le cadre : '
                  + (', '.join(f'{a_}:{h}px' for a_, h in sorted(row.items(), key=lambda kv: -kv[1])) or 'personne'))
    finally:
        RND.build_frame = orig
        r3d.render = orig_render
    return files, secs, seen, times, used


def solver_camera_delta():
    """combien les quatre figurants deplacent la camera du solveur, avec la meme intention des deux cotes.
    Ce n'est pas la camera de la planche : c'est la mesure qui explique pourquoi la planche n'en utilise pas une."""
    from hstudio.pipeline import make_engine, duration_of
    from hstudio.engines.pixel3d.frame import build_frame
    cams = {}
    for tag, scene in (('vide', 'extras_rue_vide.json'), ('vivante', 'extras_rue_vivante.json')):
        ep, lines = read_scene(os.path.join(SCENES, scene))
        for k in PLATE_SHOTS:
            if k < len(ep['shots']):
                ep['shots'][k]['camera'] = dict(PIN_CAMERA_TRIED)
        dur = duration_of(ep, lines)
        eng = make_engine(ep.get('style', 'pixel3d'), ep, lines, np.zeros(10), dur, ASPECT)
        rows = []
        for k in PLATE_SHOTS:
            a, b = eng.ctx.tl.spans[k]
            cam = build_frame(eng.ctx, float(a + (b - a) * .55))[1]
            rows.append(([float(v) for v in np.ravel(cam[0])], float(cam[1])))
        cams[tag] = rows
    dpos = [round(max(abs(A[0][i] - B[0][i]) for i in range(3)), 4) for A, B in zip(cams['vide'], cams['vivante'])]
    dyaw = [round(abs(A[1] - B[1]), 4) for A, B in zip(cams['vide'], cams['vivante'])]
    print('\n-- de combien quatre figurants deplacent-ils la camera du solveur ? --')
    print('   intention identique des deux cotes : ' + json.dumps(PIN_CAMERA_TRIED))
    for i, k in enumerate(PLATE_SHOTS):
        print(f'     plan {k} : position {dpos[i]:7.4f} m   lacet {dyaw[i]:7.4f} rad')
    print('   cause : `blocked_at` (acted.py) ecarte l objectif des corps qui ne sont pas sujets, et un POV suit')
    print('   la TETE du sujet, que ShotActing.raw_head() tourne vers le passant le plus proche. C est pour cela')
    print('   que la planche ci-dessous utilise une camera fixe du monde et pas une intention de mise en scene.')
    return {'intention': PIN_CAMERA_TRIED, 'ecart_position_m': dpos, 'ecart_lacet_rad': dyaw}


def plate():
    """la planche VIDE / VIVANTE : meme camera des deux cotes, et la preuve chiffree que c'est bien la meme"""
    from PIL import Image, ImageDraw
    solver = solver_camera_delta()
    print('\n' + '=' * 78)
    print('== PLANCHE VIDE / VIVANTE, camera FIXE du monde ' + json.dumps(FIXED_CAM))
    print('=' * 78)
    fa, sa, va, ta, ua = fixed_camera_frames('extras_rue_vide.json', 'vide')
    fb, sb, vb, tb, ub = fixed_camera_frames('extras_rue_vivante.json', 'vivante')
    print(f'   cout du rendu d une image : vide {sa}  vivante {sb}')

    # LA VERIFICATION, pas la promesse : les deux moities doivent avoir donne au lanceur de rayons exactement
    # le meme tuple de camera, aux memes instants. Tant que cette ligne dit OUI, la planche compare deux
    # villes ; le jour ou elle dit NON, elle compare deux cadrages et il faut cesser de s'en servir.
    same_cam = (ua == ub) and len(set(ua)) == 1
    same_t = (ta == tb)
    print('   camera reellement recue par le lanceur de rayons : '
          + ('IDENTIQUE des deux cotes, et unique sur toute la planche' if same_cam
             else f'DIFFERENTE -- vide {sorted(set(ua))} / vivante {sorted(set(ub))}'))
    print('   instants echantillonnes : ' + ('identiques ' + str(ta) if same_t else f'DIFFERENTS {ta} / {tb}'))
    if not (same_cam and same_t):
        print('   ATTENTION : la planche ci-dessous ne compare PAS deux villes a camera egale.')

    ims_a = [Image.open(p).convert('RGB') for p in fa]
    ims_b = [Image.open(p).convert('RGB') for p in fb]
    w, h = ims_a[0].size
    sc = 3
    tw, th = w // sc, h // sc
    band = 28
    sheet = Image.new('RGB', (tw * len(ims_a), th * 2 + band * 3 + 18), (16, 16, 18))
    d = ImageDraw.Draw(sheet)
    d.text((6, 7), 'A  LA RUE VIDE       extras_rue_vide.json', fill=(235, 235, 235))
    for k, im in enumerate(ims_a):
        sheet.paste(im.resize((tw, th)), (k * tw, band))
    d.text((6, band + th + 7), 'B  LA RUE VIVANTE    la meme + "extras" (4 figurants)', fill=(235, 235, 235))
    for k, im in enumerate(ims_b):
        sheet.paste(im.resize((tw, th)), (k * tw, band * 2 + th))
    for i, k in enumerate(PLATE_SHOTS):                  # how many bodies each column really holds
        figs = {a_: h for a_, h in vb[i].items() if a_ in BG.FIGURANTS}
        d.text((i * tw + 6, band * 2 + th * 2 + 7),
               'plan %d : %d figurant%s dans le cadre  (%s)'
               % (k, len(figs), 's' if len(figs) > 1 else '',
                  ', '.join(f'{a_} {h}px' for a_, h in sorted(figs.items(), key=lambda kv: -kv[1])) or '-'),
               fill=(160, 220, 160) if figs else (230, 190, 120))
    d.text((6, band * 2 + th * 2 + 7 + 13),
           'MEME CAMERA FIXE des deux cotes %s  |  rendu d une image : vide %.2f s, vivante %.2f s (+%.0f %%)'
           % (json.dumps(FIXED_CAM), sum(sa) / len(sa), sum(sb) / len(sb), 100 * (sum(sb) / sum(sa) - 1)),
           fill=(190, 190, 190))
    p = os.path.join(OUTDIR, f'planche_vide_vivante_{STAMP}.png')
    sheet.save(p)
    print('   planche : ' + p)
    return {'planche': p, 'camera_fixe': list(FIXED_CAM), 'plans': list(PLATE_SHOTS),
            'camera_identique_verifiee': bool(same_cam and same_t),
            'camera_recue': {'vide': [list(c[0]) + list(c[1:]) for c in sorted(set(ua))],
                             'vivante': [list(c[0]) + list(c[1:]) for c in sorted(set(ub))]},
            'instants': {'vide': ta, 'vivante': tb},
            'camera_du_solveur': solver,
            'corps_dans_le_cadre': {'vide': va, 'vivante': vb},
            'secondes_par_image': {'vide': sa, 'vivante': sb},
            'surcout_par_image_pct': round(100 * (sum(sb) / sum(sa) - 1), 1) if sum(sa) else None,
            'images': {'vide': fa, 'vivante': fb}}


def cost():
    """le prix des quatre corps, mesure sur la scene elle-meme : boites a tracer et secondes par image"""
    from hstudio.pipeline import make_engine, duration_of
    from hstudio.engines.pixel3d.frame import build_frame
    out = {}
    for tag, scene in (('vide', 'extras_rue_vide.json'), ('vivante', 'extras_rue_vivante.json')):
        ep, lines = read_scene(os.path.join(SCENES, scene))
        dur = duration_of(ep, lines)
        eng = make_engine(ep.get('style', 'pixel3d'), ep, lines, np.zeros(10), dur, ASPECT)
        boxes = []
        for k in PLATE_SHOTS:
            a, b = eng.ctx.tl.spans[k]
            boxes.append(len(build_frame(eng.ctx, float(a + (b - a) * .55))[0].boxes))
        out[tag] = {'boites_par_plan': boxes, 'corps': len([c for c in (eng.ctx.ep.get('cast') or {})])}
    out['boites_en_plus'] = [b - a for a, b in zip(out['vide']['boites_par_plan'], out['vivante']['boites_par_plan'])]
    print('\n-- cout en geometrie --')
    print('   boites a tracer par plan : vide ' + str(out['vide']['boites_par_plan'])
          + '   vivante ' + str(out['vivante']['boites_par_plan']))
    print('   soit ' + str(out['boites_en_plus']) + ' boites de plus pour quatre figurants')
    return out


if __name__ == '__main__':
    from hstudio import ffmpeg_path as FF
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=2, help='2 par defaut : la machine est partagee')
    ap.add_argument('--quality', default='standard')
    ap.add_argument('--only', default='')
    ap.add_argument('--planche-seule', action='store_true')
    ap.add_argument('--leger-seul', action='store_true')
    a = ap.parse_args()

    found = FF.ensure()
    miss = [t for t, p in found.items() if not p]
    if miss:
        print('ffmpeg introuvable (' + ', '.join(miss) + ') : ' + FF.INSTALL_HINT)
        sys.exit(1)
    print('ffmpeg : ' + found['ffmpeg'])
    os.makedirs(OUTDIR, exist_ok=True)
    PC.LIGHT = LIGHT
    report = os.path.join(OUTDIR, f'mesures_figurants_{STAMP}.json')
    old = json.load(open(report, encoding='utf-8')) if os.path.exists(report) else {}

    if a.leger_seul:
        bad, done = 0, []
        for scene_file, slug, title in CASES:
            mp4 = os.path.join(ROOT, 'projects', slug, 'renders', slug + '_short_9x16.mp4')
            if not os.path.exists(mp4):
                print('  ABSENT ' + mp4)
                bad += 1
                continue
            lc = PC.light_copy(mp4, slug)
            done.append(lc)
            print(('  OK    ' if lc['ok'] else '  ECHEC ') + lc['path'] + f"   {lc['size']} o"
                  + ('' if lc['ok'] else '  ' + str(lc['reason'])))
            bad += 0 if lc['ok'] else 1
        if done:
            old['leger'] = done
            json.dump(old, open(report, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            print('  mesures mises a jour : ' + report)
        sys.exit(1 if bad else 0)

    if a.planche_seule:
        out = dict(old)
        out['planche'] = plate()
        out['cout'] = cost()
        json.dump(out, open(report, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
        print('\nmesures : ' + report)
        sys.exit(0)

    print(f'workers = {a.workers} (sur {os.cpu_count()} coeurs logiques, machine partagee), qualite = {a.quality}')
    out, t0 = [], time.time()
    for scene_file, slug, title in CASES:
        if a.only and a.only not in slug:
            continue
        try:
            out.append(one(scene_file, slug, title, a.workers, a.quality))
        except Exception as e:
            import traceback
            traceback.print_exc()
            out.append({'slug': slug, 'title': title, 'error': str(e)[:300]})

    print('\n-- copies legeres 540x960 (glissables a la main, AUCUNE publication) --')
    light = []
    for r in out:
        if r.get('ok'):
            try:
                lc = PC.light_copy(r['mp4'], r['slug'])
                light.append(lc)
                print(('  OK    ' if lc['ok'] else '  ECHEC ') + lc['path'] + f"   {lc['size']} o")
            except Exception as e:
                print('  ECHEC copie legere : ' + str(e)[:200])

    data = {'cas': out, 'leger': light, 'planche': plate(), 'cout': cost(),
            'total_secondes': round(time.time() - t0, 1)}
    json.dump(data, open(report, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
    print('\nmesures : ' + report)
    print('total : %.0f s' % data['total_secondes'])
    sys.exit(0 if all(r.get('ok') for r in out) else 1)
