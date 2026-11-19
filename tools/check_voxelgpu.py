"""Tests of the unified engine (B directs, A paints).   python tools/check_voxelgpu.py [--gpu]

No GPU needed for the first group (contract, direction, determinism, worlds, consistency with engine A's files, integrity of
both originals, the QA's own sanity). `--gpu` adds the group that renders: GPU attestation (the adapter reported by WebGL
must be the requested one), 16:9 and 9:16 MP4s decoded and measured, pixel determinism of the painter (same contract, same
frames), and the contract really driving the picture (moving an actor moves the pixels, a different mood changes the light).
Exit code 0 only if everything passes; every line says what was measured."""
import copy, hashlib, json, math, re, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import numpy as np
from hstudio.voxelgpu import contract as C, director, worlds, qa
from hstudio.voxelgpu.films import la_marche as LM, demo_genres as DG

RESULTS = []
A_ROOT = Path(r'C:\Users\demo\Videos\moteur_voxel'); INTEG = Path(r'C:\Users\demo\.claude-code-bridge\worktrees\horror-studio-v2\studio-integration')


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail)); print(('OK    ' if ok else 'ECHEC ') + name + (f' : {detail}' if detail else ''), flush=True)


MINI = {'title': 'mini', 'genre': 'drama', 'casts': {'a': {'preset': 'noe'}, 'b': {'preset': 'lina'}},
        'shots': [{'stage': 'parc', 'dur': 3., 'actors': [{'id': 'a', 'at': [-4, .3], 'facing': '+x'}, {'id': 'b', 'at': [2, .2], 'facing': '-x', 'face': 'sad'}],
                   'actions': [{'who': 'a', 'do': 'walk_to', 'to': 'b', 'stop_dist': 1.2}, {'who': 'b', 'do': 'gesture', 'name': 'point', 'at': .5, 'dur': 1.}],
                   'camera': {'shot': 'two_shot', 'on': ['a', 'b']}},
                  {'stage': 'parc', 'dur': 5., 'dissolve': .5, 'actions': [{'who': 'b', 'do': 'sit', 'on': 'banc3'}], 'camera': {'shot': 'close', 'on': ['b']}}]}


def contract_tests():
    c = director.build(MINI, '9:16', 24)
    check('contrat valide (9:16)', not C.validate(c), f"{len(c['stages'])} plans, {sum(len(s['camera']) for s in c['stages'])} images de caméra")
    c2 = director.build(MINI, '16:9', 24); check('contrat valide (16:9)', not C.validate(c2))
    check('déterminisme de la direction', C.digest(director.build(MINI, '9:16', 24)) == C.digest(c), C.digest(c)[:16])
    check('16:9 et 9:16 : cadrages différents, mêmes acteurs', c['stages'][0]['camera'][0] != c2['stages'][0]['camera'][0] and list(c['stages'][0]['actors']) == list(c2['stages'][0]['actors']))
    bad = copy.deepcopy(c); bad['stages'][0]['actors']['a'][3][1] = float('nan'); check('contrat : une valeur NaN est refusée', any('non finie' in p for p in C.validate(bad)))
    bad = copy.deepcopy(c); bad['stages'][0]['mood'] = 'inconnue'; check('contrat : ambiance inconnue refusée', any('ambiance' in p for p in C.validate(bad)))
    bad = copy.deepcopy(c); bad['stages'][0]['actors']['zz'] = bad['stages'][0]['actors']['a']; check('contrat : acteur sans cast refusé', any('zz' in p for p in C.validate(bad)))
    bad = copy.deepcopy(c); bad['stages'][0]['camera'] = bad['stages'][0]['camera'][:3]; check('contrat : caméra trop courte refusée', any('caméra' in p for p in C.validate(bad)))
    try: director.build({'shots': [{'stage': 'nulle_part', 'dur': 1}]}, '9:16'); check('monde inconnu : refusé, jamais remplacé', False)
    except KeyError as e: check('monde inconnu : refusé, jamais remplacé', 'nulle_part' in str(e))
    ix = {n: i for i, n in enumerate(C.ACTOR_COLS)}; s1 = c['stages'][1]['actors']['b']
    check('assise sur le banc : sit=1 et siège à 0,45 m', abs(s1[-1][ix['sit']] - 1) < .05 and abs(s1[-1][ix['seat_h']] - worlds.BENCH_H) < 1e-6, f"sit={s1[-1][ix['sit']]:.2f}")
    a0 = c['stages'][0]['actors']['a']; v = [math.hypot(a0[i + 1][ix['x']] - a0[i][ix['x']], a0[i + 1][ix['z']] - a0[i][ix['z']]) * 24 for i in range(len(a0) - 1)]
    check('marche : vitesse bornée (< 2 m/s, pas de téléportation)', max(v) < 2.0, f'max {max(v):.2f} m/s')
    ph = [a0[i][ix['phase']] for i in range(len(a0))]; check('marche : la phase de pas ne recule jamais', all(b >= a - 1e-9 for a, b in zip(ph, ph[1:])))
    ey = [a0[i][ix['yaw']] for i in range(len(a0))]; check('marche : pas de saut de cap > 1 rad par image', max(abs((b - a + math.pi) % (2 * math.pi) - math.pi) for a, b in zip(ey, ey[1:])) < 1.0)


def worlds_tests():
    for n, w in worlds.WORLDS.items():
        x0, z0, x1, z1 = w['bounds']; ok = x0 < x1 and z0 < z1 and all(x0 <= sx <= x1 and z0 <= sz <= z1 for sx, sz in (w.get('seats') or {}).values())
        if not ok: check(f'monde {n} : rectangle et sièges cohérents', False)
    js = (ROOT / 'voxelgpu_js/engine/sets5.js').read_text(encoding='utf-8'); names = re.findall(r"mk\('(\w+)'", js)
    kit = (ROOT / 'voxelgpu_js/engine/horror_kit.js').read_text(encoding='utf-8'); extra = re.findall(r"mk\('(\w+)'", kit)
    cite = re.findall(r"mk\('(\w+)'", (ROOT / 'voxelgpu_js/engine/cite_kit.js').read_text(encoding='utf-8'))        # the demo kit (cité, astroport, Lune) added by the narrative demo mission
    bkit = re.findall(r"mk\('(\w+)'", (ROOT / 'voxelgpu_js/engine/b_kit.js').read_text(encoding='utf-8'))              # the B kit (plateau for the places and props of PIXEL 3D), added by the studio integration
    check('mondes : rectangles marchables et sièges cohérents (10 de A + kit horreur + kit démo + kit B)', len(worlds.WORLDS) == 10 + len(extra) + len(cite) + len(bkit), f'{len(worlds.WORLDS)} mondes, kit : {extra}, démo : {cite}, B : {bkit}')
    check('mondes de B = mondes de A (sets5.js) + kit horreur (horror_kit.js) + kit démo (cite_kit.js) + kit B (b_kit.js)', names + extra + cite + bkit == list(worlds.WORLDS), f'{names} + {extra} + {cite} + {bkit}')
    c = director.build(DG.episode(), '16:9', 24); box = worlds.VoxWorld('ville').camera_box(); out = 0
    for s in c['stages']:
        W = worlds.VoxWorld(s['world'])
        out += sum(1 for r in s['camera'] if W.blocked_for_camera((r[0], r[1], r[2])))
    check('clip démo : la caméra reste dans la boîte permise du monde', out == 0, f'{out} positions hors boîte')
    check('clip démo : durée <= 120 s, sans dialogue', c['duration'] <= 120 and not any(sh.get('speech') for sh in DG.episode()['shots']), f"{c['duration']} s")


def fidelity_tests():
    c = director.build(LM.episode(), '9:16', 24); ix = {n: i for i, n in enumerate(C.ACTOR_COLS)}
    worst = 0.; worstc = 0.
    for i, st in enumerate(c['stages']):
        for f in (0, 60, 120):
            T = LM.T0[i] + f / 24; x_a = (T - LM._mid(i)) * LM.V; r = st['actors']['noe'][f]; worst = max(worst, abs(r[ix['x']] - x_a))
            # engine A's camera (film_marche.js camAt) for the same instant
            K = LM.CAM; j = 0
            while j < len(K) - 2 and T > K[j + 1][0]: j += 1
            a, b = K[j], K[j + 1]; k = (T - a[0]) / (b[0] - a[0]); k = k * k * (3 - 2 * k); v = [a[n] * (1 - k) + b[n] * k for n in range(6)]
            px = x_a + math.cos(v[1]) * v[2]; pz = math.sin(v[1]) * v[2]; cam = st['camera'][f]
            worstc = max(worstc, abs(cam[0] - px), abs(cam[2] - pz), abs(cam[1] - v[3]), abs(cam[3] - (x_a + .25)), abs(cam[6] - v[5]))
    check("« La marche » : Noé est où le veut le script de A (0,95 m/s, 10 mondes)", worst < .02, f'écart max {worst * 100:.2f} cm')
    check("« La marche » : la caméra du brief est celle de film_marche.js", worstc < .02 + 1e-9, f'écart max {worstc:.4f}')
    check("« La marche » : fondus 1,2 s, 61 s, 24 i/s", [round(s['dissolve'], 2) for s in c['stages']] == [0.] + [1.2] * 9 and c['duration'] == 61 and c['fps'] == 24)
    js = (ROOT / 'voxelgpu_js/engine/film_unified.js').read_text(encoding='utf-8'); moods = re.search(r'export const MOODS = \{(.*?)\n\};', js, re.S).group(1)
    jsm = re.findall(r'^  (\w+):', moods, re.M); check('ambiances : Python = JavaScript', jsm == C.MOODS, f'{jsm}')
    f4 = (ROOT / 'voxelgpu_js/engine/face4.js').read_text(encoding='utf-8'); m = re.search(r'PRESETS\s*=\s*\{(.*?)\n\}', f4, re.S)
    names = set(re.findall(r'^\s{2}(\w+):', m.group(1), re.M)) if m else set()
    check('expressions : celles du contrat existent dans face4.js', set(C.EXPRESSIONS) <= names | {'blink', 'lookL', 'lookR'}, f'manquantes {sorted(set(C.EXPRESSIONS) - names)}')
    check('B -> A : toute expression de B a une image dans A', set(director.EXPR_MAP.values()) <= set(C.EXPRESSIONS))
    import importlib; FACES43 = importlib.import_module('hstudio.director.validate').FACES      # `hstudio.director.validate` est aussi le nom d'une fonction du paquet : import par importlib
    check('B -> A : les 46 expressions de PIXEL 3D (43 + fixed_smile, predator, predator_smile le 6/11/2026) ont chacune LEUR préréglage dans face4.js (aucune ne retombe sur une autre)', len(FACES43) == 46 and all(director.EXPR_MAP.get(f) == f for f in FACES43) and (FACES43 - names - {'blink'}) == set(),
          f"table {sorted(f for f in FACES43 if director.EXPR_MAP.get(f) != f)}, sans préréglage {sorted(FACES43 - names)}")
    check('contrat : les 17 expressions d\'origine gardent leurs indices (les films déjà faits restent les mêmes)', C.EXPRESSIONS[:17] == ['neutral', 'worried', 'scared', 'scaredL', 'scaredR', 'scream', 'shout', 'grit', 'determined', 'smile', 'relief', 'sad', 'cry', 'surprised', 'blink', 'lookL', 'lookR'])
    from hstudio.acting import gestures as G
    check('B -> A : toute pose de bras de B a une main dans A ou le repos', all(isinstance(director.HAND_OF.get(m, 0), int) for m, _ in G.GESTURES.values()))


def integrity_tests():
    from hstudio.voxelgpu import freeze
    man = ROOT / 'docs/voxelgpu/manifest_A_20261029.json'
    if A_ROOT.exists():
        bad = freeze.check(man); check('moteur A (dossier original) : identique au manifeste SHA-256 gelé', not bad, f'{len(json.loads(man.read_text(encoding="utf-8"))["files"])} fichiers' if not bad else str(bad[:3]))
    if INTEG.exists():
        r = subprocess.run(['git', '-C', str(INTEG), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
        st = subprocess.run(['git', '-C', str(INTEG), 'status', '--short'], capture_output=True, text=True).stdout.split('\n')
        check('studio-integration : HEAD 58ca501, aucun fichier suivi modifié', r.startswith('58ca501') and not any(l and not l.startswith('??') for l in st), f'{r[:7]}, {len([l for l in st if l])} non suivis')
    mb = ROOT / 'docs/voxelgpu/manifest_B_20261029.json'; mj = json.loads(mb.read_text(encoding='utf-8'))
    lf = lambda k: (ROOT / k).read_bytes().replace(bytes([13, 10]), bytes([10]))       # CRLF checkout vs the LF files the manifest was taken on
    changed = [k for k, d in mj['files'].items() if (ROOT / k).is_file() and hashlib.sha256(lf(k)).hexdigest() != d['sha256'] and hashlib.sha256((ROOT / k).read_bytes()).hexdigest() != d['sha256']]
    INTEGRATED = {'hstudio/pipeline.py', 'hstudio/web/server.py', 'hstudio/web/static/index.html', 'hstudio/acting/timeline.py',
                  'hstudio/capabilities/registry.py', 'hstudio/engines/pixel3d/assets.py', 'hstudio/engines/pixel3d/places.py',
                  'hstudio/engines/pixel3d/render.py', 'hstudio/engines/pixel3d/sets.py',
                  'hstudio/engines/pixel3d/r3d.py', 'hstudio/engines/pixel3d/frame.py', 'hstudio/engines/pixel3d/acted.py', 'hstudio/director/validate.py',
                  # 31/10 : scènes dirigées (gaze/eyeflow s'effacent), objets PS1 (world), suppression des options rejetées (bodies, eyes, eyeflow, safe),
                  # profil « production » (mixer, narrative) et les outils/docs qui les suivent
                  'hstudio/acting/gaze.py', 'hstudio/acting/eyeflow.py', 'hstudio/engines/pixel3d/world.py', 'hstudio/engines/pixel3d/bodies.py',
                  'hstudio/engines/pixel3d/eyes.py', 'hstudio/captions/safe.py', 'hstudio/audio/mixer.py', 'hstudio/director/narrative.py',
                  'AGENTS.md', 'docs/FORMAT_EPISODE.md', 'tools/check_finish.py', 'tools/check_lissage.py', 'tools/check_regard.py', 'tools/check_voxel.py',
                  'tools/corps_bench.py', 'tools/corps_qc.py', 'tools/interaction_qc.py', 'tools/p1_corps_proof.py', 'tools/proto_visage.py', 'tools/regard_qc.py',
                  'hstudio/engines/pixel3d/compose.py',
                  # 31/10/2026 (chantier « bâtiments et intérieurs variés ») : lexique (mots d'histoire -> quartier, hall, appartement, boutique) ; compose.py reçoit aussi le crochet des façades de quartier
                  'hstudio/capabilities/lexicon.py',
                  # 31/10/2026 (costumes du bal, clés de scène dirigée) : `side: left` (geste en miroir), `kneel`, `sit_floor` dans le squelette (rig.py, inertes sans
                  # les clés) ; gestes `arms_wide`, `arms_wide_up` (gestures.py) ; objet tenu dans la main gauche (rigfig.py) ; tools/check_costumes.py les vérifie
                  'hstudio/acting/rig.py', 'hstudio/acting/gestures.py', 'hstudio/engines/pixel3d/rigfig.py',
                  # 6/11/2026 : intégrations de la publication (régie, 1-2/11) et du directeur (prompts, providers) : légitimes, ajoutées à la liste sans affaiblir le garde-fou
                  'hstudio/__main__.py', 'hstudio/director/prompts.py', 'hstudio/director/providers.py',
                  # 6/11/2026 : objets du récit / catalogue (2-4/11) : poses.py (objets tenus du récit) et tools/catalogue.py (listes du catalogue)
                  'hstudio/engines/pixel3d/poses.py', 'tools/catalogue.py',
                  # 15/11/2026 (Le Phare qui efface) : borne de hauteur des halos d'objet relevée de 20 à 80 m (lanterne de phare) ; identique sous 20 m,
                  # vérifiée par tools/check_epaule.py
                  'hstudio/engines/pixel3d/lighting.py'}       # + 31/10 (V3 dans VOXEL) : compose.py (éléments composés des nouveaux quartiers, chantier décors)       # + moteur unique (31/10) : zones de lumière/projecteurs, table d'état, caméra en clés, lieu pompe_station       # + style PS1 (31/10/2026) : matrice PS1/VOXEL du registre, visage sans traits, mondes VOXEL reconstruits en lieux PS1       # changés exprès par l'intégration du moteur voxel dans le studio (docs/INTEGRATION_VOXEL_STUDIO.md) : tout AUTRE fichier changé reste un échec
    check('moteur B : seuls les fichiers de l\'intégration studio ont changé par rapport au manifeste', set(changed) <= INTEGRATED, str(sorted(set(changed) - INTEGRATED)[:3]))
    check("A copié dans voxelgpu_js/ : la copie ne contient ni Kodaline ni analysis.json", not (ROOT / 'voxelgpu_js/engine/assets/analysis.json').exists() and not (ROOT / 'voxelgpu_js/engine/film_musique.js').exists())


def qa_tests():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td); blk = td / 'noir.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=black:s=144x256:r=24:d=2', '-pix_fmt', 'yuv420p', str(blk)], check=True)
        r = qa.verify(blk, 144, 256, 24, 2.0); check('QA : refuse une vidéo noire et muette', not r['ok'] and not r['checks']['not_black']['ok'] and not r['checks']['audio_stream']['ok'])
        ok = td / 'ok.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=s=144x256:r=24:d=2', '-f', 'lavfi', '-i', 'sine=f=300:d=2', '-shortest', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(ok)], check=True)
        r = qa.verify(ok, 144, 256, 24, 2.0); check('QA : accepte une vidéo animée avec son', r['ok'], str({k: v['detail'] for k, v in r['checks'].items() if not v['ok']}))
        r = qa.verify(ok, 720, 1280, 24, 2.0); check('QA : refuse une mauvaise résolution', not r['checks']['resolution']['ok'])


def audio_tests():
    from hstudio.voxelgpu import audio
    c = director.build(DG.episode(), '9:16', 24)
    with tempfile.TemporaryDirectory() as td:
        p = audio.compose(c, Path(td) / 'a.wav'); h1 = hashlib.sha256(Path(p).read_bytes()).hexdigest(); p2 = audio.compose(c, Path(td) / 'b.wav')
        r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p], capture_output=True, text=True); d = float(r.stdout)
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', p, '-af', 'pan=mono|c0=0.5*c0+0.5*c1', '-f', 'f32le', '-'], capture_output=True).stdout; x = np.frombuffer(raw, np.float32)
        check('audio du clip : déterministe (même WAV, octet pour octet)', h1 == hashlib.sha256(Path(p2).read_bytes()).hexdigest(), h1[:16])
        check('audio du clip : durée du film, ni muet ni écrêté', abs(d - c['duration']) < 1 and np.abs(x).max() > .1 and np.abs(x).max() <= 1.0, f'{d:.1f} s, crête {np.abs(x).max():.2f}')
        seg = [float(np.sqrt((x[int(t0 * 44100):int((t0 + 2) * 44100)] ** 2).mean())) for t0 in range(0, int(c['duration']) - 2, 4)]
        check('audio du clip : aucune fenêtre de 2 s silencieuse', min(seg) > 1e-3, f'RMS min {min(seg):.4f}')


def gpu_tests(gpu):
    from hstudio.voxelgpu import render, gpu as G
    with tempfile.TemporaryDirectory() as td:
        td = Path(td); res = {}
        for asp in C.ASPECTS:
            c = director.build(MINI, asp, 24); C.save(c, td / f'{asp[:1]}.json'); w, h = render.SIZES[asp]
            att = td / f'att{asp[:1]}.json'; mp4 = td / f'{asp[:1]}.mp4'
            render.run_painter(td / f'{asp[:1]}.json', mp4, gpu, attest=att, quiet=True); a = json.loads(att.read_text(encoding='utf-8'))
            r = qa.verify(mp4, w, h, 24, 8.0, need_audio=False); want = {'nvidia': 'NVIDIA', 'intel': 'Intel'}.get(gpu, '')
            check(f'GPU {asp} : WebGL rapporte {gpu}', want in a['webgl']['renderer'], a['webgl']['renderer'])
            check(f'MP4 {asp} : décodé, {w}x{h}, 24 i/s, 8 s, animé', r['ok'], str({k: v['detail'] for k, v in r['checks'].items() if not v['ok']}))
        # determinism: the same frames twice
        c = director.build(MINI, '9:16', 24); C.save(c, td / 'd.json'); shots = []
        for k in range(2):
            render.run_painter(td / 'd.json', None, gpu, stills=[1.0, 3.5], stills_dir=td / f's{k}', quiet=True)
        from PIL import Image
        for t in ('1.00', '3.50'):
            A_ = np.asarray(Image.open(td / 's0' / f't_{t}.png')).astype(np.int16); B_ = np.asarray(Image.open(td / 's1' / f't_{t}.png')).astype(np.int16)
            check(f'peintre déterministe : image à {t} s identique (deux lancements)', np.abs(A_ - B_).max() <= 2, f'écart max {np.abs(A_ - B_).max()} / 255')
        # the contract drives the picture: move the actor, the pixels move; change the mood, the light changes
        c2 = copy.deepcopy(c); ix = {n: i for i, n in enumerate(C.ACTOR_COLS)}
        for r in c2['stages'][0]['actors']['a']: r[ix['x']] += 1.5
        C.save(c2, td / 'm.json'); render.run_painter(td / 'm.json', None, gpu, stills=[1.0], stills_dir=td / 'sm', quiet=True)
        c3 = copy.deepcopy(c); c3['stages'][0]['mood'] = 'noir'; C.save(c3, td / 'n.json'); render.run_painter(td / 'n.json', None, gpu, stills=[1.0], stills_dir=td / 'sn', quiet=True)
        base = np.asarray(Image.open(td / 's0' / 't_1.00.png')).astype(np.float32)
        mv = np.asarray(Image.open(td / 'sm' / 't_1.00.png')).astype(np.float32); nr = np.asarray(Image.open(td / 'sn' / 't_1.00.png')).astype(np.float32)
        check('le contrat pilote l\'image : déplacer un acteur change les pixels', np.abs(base - mv).mean() > 1.0, f'écart moyen {np.abs(base - mv).mean():.1f}')
        check('le contrat pilote la lumière : ambiance noir = image plus grise', nr[..., :3].std(axis=2).mean() < base[..., :3].std(axis=2).mean() * .6, f'écart entre canaux {nr[..., :3].std(axis=2).mean():.1f} vs {base[..., :3].std(axis=2).mean():.1f}')
        # software fallback must work too (no GPU at all)
        att = td / 'sw.json'; render.run_painter(td / 'd.json', td / 'sw.mp4', 'software', attest=att, end=.5, quiet=True)
        check('repli logiciel (SwiftShader) : rend aussi', qa.verify(td / 'sw.mp4', 720, 1280, 24, .5, need_audio=False)['ok'], json.loads(att.read_text(encoding='utf-8'))['webgl']['renderer'][:60])


def space_tests():
    """espace entre les acteurs et avec les décors (b_space.py) : sans réglage `spacing` rien ne bouge ; avec lui, les corps ne se traversent pas, on parle à distance de conversation, les décors du plan sont des obstacles"""
    from hstudio.voxelgpu import b_space as SP
    env = dict(floor=0x4a4640, bg=0x1a2030, ambient=1.0, key=0.8, fog=0.005); casts = {'lea': {'preset': 'lina'}, 'tom': {'preset': 'noe'}}
    A = lambda i, x, z, f='+z': dict(id=i, at=[x, z], facing=f, face='neutral')
    sh = lambda dur, actors, actions=(), speech=(), props=(), **kw: dict(stage='plateau', dur=dur, env=env, camera=dict(shot='wide', on=[a['id'] for a in actors]), actors=actors, actions=list(actions), speech=[list(s) for s in speech], props=list(props), **kw)
    def build(shots, spacing, **kw): return director.build(dict(title='t', genre='neutral', casts=casts, spacing=spacing, shots=shots, **kw), '16:9', 24)
    face = [sh(5, [A('lea', -.3, 0, '+x'), A('tom', .3, 0, '-x')], speech=[(.3, 2.2, 'lea'), (2.6, 4.5, 'tom')])]
    off = SP.audit(build(face, False)); on = SP.audit(build(face, True))
    check('espace : sans `spacing`, deux acteurs écrits à 0,6 m se chevauchent (comportement d\'avant conservé)', off['pair_frames_below_phys'] > 0 and off['min_pair'] < .7, f'{off["pair_frames_below_phys"]} images, min {off["min_pair"]} m')
    check('espace : avec `spacing`, aucun chevauchement de corps', on['pair_frames_below_phys'] == 0, f'min {on["min_pair"]} m')
    check('espace : avec `spacing`, on parle à distance de conversation (≥ 85 %)', on['pair_frames_below_conv_talking'] == 0 and on['min_pair'] >= SP.CONV * .85, f'min {on["min_pair"]} m')
    walk = [sh(6, [A('lea', 0, 0), A('tom', -5, 0, '+x')], [dict(who='tom', do='walk_to', to='lea', at=.2)], speech=[(3, 5.5, 'tom')])]
    w = SP.audit(build(walk, True)); check('espace : une approche vers un acteur s\'arrête à la distance de conversation (pas 0,95 m)', w['min_pair'] >= SP.CONV * .9, f'min {w["min_pair"]} m')
    hug = dict(intimacy=True); hs = [sh(5, [A('lea', -.55, 0, '+x'), A('tom', .55, 0, '-x')], speech=[(.3, 2, 'lea')])]
    h = SP.audit(build(hs, True, **hug), intimacy=True); check('espace : `intimacy` lève la distance de conversation mais pas la distance physique', h['pair_frames_below_phys'] == 0 and h['min_pair'] < SP.CONV * .85, f'min {h["min_pair"]} m')
    cross = [sh(6, [A('lea', -5, .1, '+x'), A('tom', 5, -.1, '-x')], [dict(who='lea', do='walk_to', to=[5, .1], at=.2), dict(who='tom', do='walk_to', to=[-5, -.1], at=.2)])]
    cr0 = SP.audit(build(cross, False)); cr1 = SP.audit(build(cross, True))
    check('espace : deux acteurs qui se croisent ne se traversent pas', cr0['pair_frames_below_phys'] > 0 and cr1['pair_frames_below_phys'] == 0, f'{cr0["pair_frames_below_phys"]} -> {cr1["pair_frames_below_phys"]} images, min {cr1["min_pair"]} m')
    furn = [sh(6, [A('lea', -5, 0, '+x')], [dict(who='lea', do='walk_to', to=[5, 0], at=.2)], props=[dict(type='b:table', at=[0, 0], rot=0), dict(type='b:sofa', at=[2.4, -.1])])]
    f0 = SP.audit(build(furn, False)); f1 = SP.audit(build(furn, True))
    check('espace : un acteur ne traverse pas les décors du plan (b:table, b:sofa)', f0['penetration_frames'] > 0 and f1['penetration_frames'] == 0, f'{f0["penetration_frames"]} -> {f1["penetration_frames"]} images dans un décor')
    c1 = build(face, True); c2 = build(face, True); check('espace : déterministe (deux constructions identiques)', C.digest(c1) == C.digest(c2))
    pa = [sh(5, [A('lea', 0, 0)], [dict(who='lea', do='walk_to', to=[3, 1], at=.2)])]; pa0 = build(pa, False); pa1 = build(pa, True)
    check('espace : un acteur seul n\'est pas modifié par `spacing`', C.digest(pa0['stages'][0]['actors']) == C.digest(pa1['stages'][0]['actors']))


def extras_tests():
    """figurants animés (b_extras.py) : opt-in, jamais dans un décor ni dans un corps, loin des principaux, en mouvement, entrées et sorties, déterminisme, plafond, hors caméra, réaction à une menace"""
    import warnings, math as _m
    sys.path.insert(0, str(ROOT / 'tools')); import b_extras_scene as XS
    from hstudio.voxelgpu import b_extras as EX, b_space as SP
    CI = {n: i for i, n in enumerate(C.ACTOR_COLS)}
    off = director.build(XS.episode(extras=False, spacing=True), '9:16', 24)
    check("figurants : sans la clé `extras`, rien n'est ajouté (opt-in)", 'extras' not in off and not any((c or {}).get('extra') for c in off['casts'].values()) and set(off['casts']) == {'noe', 'lina', 'slender'})
    rows = []
    for seed in (1, 2, 3):
        c = director.build(XS.episode(seed=seed), '9:16', 24); rows.append((seed, c, EX.audit(c, keep=3.0)))
    check('figurants : aucun corps ne se traverse (3 graines, 10 figurants)', all(r['overlap_frames'] == 0 for _, _, r in rows), str([r['overlap_frames'] for _, _, r in rows]))
    check("figurants : jamais à moins de keep_clear - 0,3 m d'un personnage principal", all(r['below_keep_frames'] == 0 and r['min_to_leads'] >= 2.7 for _, _, r in rows), str([r['min_to_leads'] for _, _, r in rows]))
    check("figurants : jamais dans l'emprise d'un décor du plan", all(r['penetration_frames'] == 0 for _, _, r in rows))
    check("figurants : ils bougent tous (plus d'un mètre parcouru)", all(r['moving'] == r['extras'] for _, _, r in rows), str([f"{r['moving']}/{r['extras']}" for _, _, r in rows]))
    ent = sum(EX.audit(director.build(XS.episode(seed=sd, monster=False), '9:16', 24))['entered'] for sd in (3, 4, 5)); ext = sum(r['exited'] for _, _, r in rows)
    check('figurants : entrées par les bords pendant le plan, sorties en fuyant', ent >= 3 and ext >= 1, f'{ent} entrées, {ext} sorties')
    c1 = director.build(XS.episode(seed=2), '9:16', 24); c2 = director.build(XS.episode(seed=2), '9:16', 24)
    check('figurants : déterministe (même épisode = même contrat)', C.digest(c1) == C.digest(c2))
    check('figurants : une autre graine change la troupe', C.digest(c1['stages'][0]['actors']) != C.digest(director.build(XS.episode(seed=3), '9:16', 24)['stages'][0]['actors']))
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always'); big = director.build(XS.episode(count=40, monster=False), '9:16', 24)
    check('figurants : plafond clair (40 demandés -> %d, avec message)' % EX.MAX, big['extras'][0]['capped'] and big['extras'][0]['placed'] <= EX.MAX and any('plafonnés' in str(x.message) for x in w), str(big['extras'][0].get('message', ''))[:80])
    e1 = XS.episode(extras=True, monster=False); e0 = XS.episode(extras=False, monster=False)
    for e in (e0, e1): e['shots'][0]['camera'] = dict(shot='wide')
    c0 = director.build(e0, '9:16', 24); cx = director.build(e1, '9:16', 24)
    d = _m.dist(c0['stages'][0]['camera'][0][:3], cx['stages'][0]['camera'][0][:3])
    check("figurants : la caméra ne les prend jamais pour sujets (même cadrage qu'avec les seuls principaux)", cx['stages'][0]['focus_actor'] in ('noe', 'lina') and d < 1.0, f'écart caméra {d:.2f} m')
    wall = [dict(type='b:table', at=[x, 0.], rot=1) for x in (-3., -1.5, 0., 1.5, 3.)] + [dict(type='b:sofa', at=[x, 0.4]) for x in (-4.5, 4.5)]

    def street(spacing):
        ep = dict(title='t', genre='neutral', casts={'a': {'preset': 'noe'}}, spacing=True, shots=[dict(stage='parc', dur=8, props=wall, env=dict(floor=0x4a4640, bg=0x1a2030, ambient=1.0, key=.8, fog=.005), camera=dict(shot='wide', on=['a']),
              actors=[dict(id='a', at=[-9., 2.])], actions=[])], extras=dict(count=4, seed=2, keep_clear=1.0, troupe='auto', lanes=[[[-12., 0.1], [12., 0.1]]], mix=dict(walk=1.), spacing=spacing))
        if not spacing: ep.pop('spacing')
        return director.build(ep, '16:9', 24)
    p0 = EX.audit(street(False)); p1 = EX.audit(street(True))
    check('figurants : une voie qui traverse des meubles (b:table, b:sofa) : traversés sans garde, contournés avec', p0['penetration_frames'] > 0 and p1['penetration_frames'] == 0, f"{p0['penetration_frames']} -> {p1['penetration_frames']} images")
    ep = XS.episode(monster=False, count=8); ep['extras']['mix'] = dict(talk_pairs=1.); ct = director.build(ep, '9:16', 24); at = SP.audit(ct)
    n_talk = sum(1 for v in ct['extras'][0]['roles'].values() if v == 'talk_pairs')
    check("figurants : discussions par deux, à distance de conversation, sans s'embrasser", n_talk >= 4 and at['pair_frames_below_conv_talking'] == 0 and at['pair_frames_below_phys'] == 0, f'{n_talk} bavards, min {at["min_pair"]} m')
    ps = dict(title='t', genre='neutral', casts={'a': {'preset': 'noe'}}, spacing=True, shots=[dict(stage='parc', dur=6, env=dict(floor=0x4a4640, bg=0x1a2030, ambient=1.0, key=.8, fog=.005), camera=dict(shot='wide', on=['a']),
              actors=[dict(id='a', at=[0., 1.5])], actions=[])], extras=dict(count=3, seed=4, keep_clear=2.0, mix=dict(sit=1.)))
    cs = director.build(ps, '16:9', 24); sat = sum(1 for a, rws in cs['stages'][0]['actors'].items() if a.startswith('fig_') and rws[-1][CI['sit']] > .5)
    check("figurants : ils s'asseyent sur les sièges libres du lieu (bancs du parc)", sat >= 2, f'{sat} assis sur 3')
    cm = director.build(XS.episode(seed=1, threat=6., dur=16.), '9:16', 24); A = cm['stages'][0]['actors']; sl = A['slender']; t0 = int(6.8 * 24); t1 = int(13. * 24)

    def dist_to_threat(a, j): return _m.hypot(A[a][j][CI['x']] - sl[j][CI['x']], A[a][j][CI['z']] - sl[j][CI['z']])
    fig = [a for a in A if a.startswith('fig_') and A[a][t0][CI['vis']] > .5]
    gain = [dist_to_threat(a, t1 if A[a][t1][CI['vis']] > .5 else max(j for j in range(len(A[a])) if A[a][j][CI['vis']] > .5)) - dist_to_threat(a, t0) for a in fig]
    check("figurants : à l'apparition du monstre ils fuient (au moins 60 % s'éloignent de 3 m ou sortent)", sum(1 for g in gain if g > 3.) >= .6 * len(fig), f'{sum(1 for g in gain if g > 3.)}/{len(fig)}')
    from hstudio.voxelgpu import b_sets as BS
    bs = BS.get('cafe', {'type': 'cafe'}); x0, z0, x1, z1 = bs.world.rect; cx, cz = (x0 + x1) / 2, (z0 + z1) / 2; cafe = []
    for sd in (1, 2, 3, 4):
        ce = dict(title='cafe', genre='neutral', casts={'a': {'preset': 'noe'}, 'b': {'preset': 'lina'}}, sets={'cafe': {'type': 'cafe'}}, spacing=True,
                  shots=[dict(set='cafe', dur=10, camera=dict(shot='wide', on=['a', 'b']), actors=[dict(id='a', at=[cx - .7, cz]), dict(id='b', at=[cx + .7, cz])], speech=[[.5, 3, 'a'], [3.3, 6, 'b']], actions=[])],
                  extras=dict(count=6, seed=sd, keep_clear=2.2, mix=dict(idle=.3, talk_pairs=.3, sit=.3, walk=.1)))
        cafe.append(EX.audit(director.build(ce, '9:16', 24), keep=2.2))
    check('figurants : dans un lieu intérieur converti (café), aucun chevauchement, aucun dans un meuble, à distance des principaux, jamais deux sur un même siège',
          all(r['overlap_frames'] == 0 and r['penetration_frames'] == 0 and r['below_keep_frames'] == 0 for r in cafe), str([(r['overlap_frames'], r['penetration_frames']) for r in cafe]))
    import time as _t
    t = _t.time(); c16 = director.build(XS.episode(count=16, monster=False), '9:16', 24); dt = _t.time() - t
    check('figurants : 16 figurants, contrat construit en moins de 60 s', dt < 60 and c16['extras'][0]['placed'] == 16, f'{dt:.1f} s, {len(C.dumps(c16)) / 1e6:.1f} Mo')


if __name__ == '__main__':
    for g in (contract_tests, worlds_tests, fidelity_tests, integrity_tests, qa_tests, audio_tests, space_tests, extras_tests): g()
    if '--gpu' in sys.argv: gpu_tests(sys.argv[sys.argv.index('--gpu') + 1] if len(sys.argv) > sys.argv.index('--gpu') + 1 and not sys.argv[sys.argv.index('--gpu') + 1].startswith('-') else 'nvidia')
    bad = [n for n, ok, _ in RESULTS if not ok]
    print(f'\n{len(RESULTS) - len(bad)}/{len(RESULTS)} vérifications OK' + (f' ; ÉCHECS : {bad}' if bad else ''))
    sys.exit(1 if bad else 0)
