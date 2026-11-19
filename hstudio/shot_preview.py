"""Aperçu d'un plan AVANT validation : le réglage en attente (cadrage, mouvement, expression, transition) est appliqué à une COPIE de l'épisode,
le plan est rendu en court clip (le style du projet : PS1, VOXEL ou Console 2D), l'utilisateur le regarde, puis valide (la route « valider » applique
le MÊME `apply_patch` et enregistre) ou annule. Rien du projet n'est modifié par un aperçu.

API
  options(style)                                  -> {"transitions", "moves", "faces", "sizes"} : [[id, libellé]] RÉELLEMENT implémentés par le style (`ps1`, `voxel`, `console`)
  apply_patch(episode, index, patch, style)       -> copie de l'épisode avec le patch (ValueError en français sinon)
  current(episode, index, style)                  -> réglages actuels du plan, pour pré-remplir l'interface
  render_shot_clip(slug, index, patch=None, ...)  -> dict JSON (fichier relatif au dossier du projet)
  purge_clips(slug)                               -> libère le dossier `preview_clips/` du projet
  apply_to_contract(contract, episode)            -> les fondus et flashs de plan, traduits pour le peintre VOXEL (appelé par studio_bridge.contract_of : l'aperçu
                                                     et le rendu final font la même chose)

Patch : {"camera": {"shot": "close", "move": "dolly_in"}, "actors": [{"id": "lea", "face": "scared"}], "transition": "cut|fade|flash", "note": "..."}
Forme enregistrée (déjà comprise par les moteurs, aucune clé inventée) :
  cadrage / mouvement   `camera.shot` / `camera.move` (absent = fixe) ; Console : `camera.zoom` (1, 1,25, 1,55) et `camera.move` (`static` explicite : la valeur par défaut de ce moteur est « drift »)
  expression            `actors[].face`
  transition            `fx.fade_in` (ce plan) + `fx.fade_out` (plan précédent) pour « Fondu au noir » ; `fx.flash` pour « Flash blanc » ; « Coupe » les retire.
                        PS1 et Console 2D lisent ces clés ; VOXEL les traduit en événements `fade` / `flash` du contrat (`apply_to_contract`).
Pas de « fondu enchaîné » : aucun des trois moteurs ne mélange deux plans (un seul plan est peint à chaque instant), il n'est donc pas proposé.
"""
import copy, hashlib, json, os, re, shutil, subprocess, tempfile, time
from pathlib import Path

STYLES = ('ps1', 'voxel', 'console')
FADE_S = .6                   # durée d'un fondu au noir (s)
FLASH = .9                    # intensité du flash blanc
SIZES_3D = [['wide', 'Plan large'], ['full', 'En pied'], ['medium', 'Plan moyen'], ['close', 'Gros plan'], ['extreme_close', 'Très gros plan'], ['two_shot', 'Deux personnages'],
            ['ots', "Par-dessus l'épaule"], ['dialogue', 'Dialogue'], ['pov', 'Vue du personnage'], ['insert', 'Détail (insert)']]
MOVES_3D = [['static', 'Caméra fixe'], ['dolly_in', 'Avance doucement'], ['dolly_out', 'Recule doucement'], ['track', 'Suit sur le côté'], ['orbit', 'Tourne autour'],
            ['crane_up', 'Monte'], ['crane_down', 'Descend'], ['follow', 'Suit le personnage']]
SIZES_CLASSIC = [['wide', 'Plan large'], ['full', 'En pied'], ['medium', 'Plan moyen'], ['closeup', 'Gros plan'], ['ots', "Par-dessus l'épaule"], ['pov', 'Vue du personnage'],
                 ['insert', 'Détail (insert)'], ['high_corner', "Vue d'en haut"], ['low', 'Vue basse']]
MOVES_CLASSIC = [['static', 'Caméra fixe'], ['dolly_in', 'Avance doucement'], ['dolly_out', 'Recule doucement'], ['push_in', 'Zoom avant'], ['pull_out', 'Zoom arrière'],
                 ['track_left', 'Glisse à gauche'], ['track_right', 'Glisse à droite'], ['pan_left', 'Tourne à gauche'], ['pan_right', 'Tourne à droite'], ['crane_up', 'Monte'],
                 ['crane_down', 'Descend'], ['orbit_left', 'Tourne autour (gauche)'], ['orbit_right', 'Tourne autour (droite)'], ['handheld', "Caméra à l'épaule"]]
NEEDS_SUBJECT = {'closeup', 'medium', 'full', 'ots'}      # anciens épisodes : ces cadrages se placent d'après `camera.subject`
SIZES_CONSOLE = [['wide', 'Plan large'], ['medium', 'Plan moyen'], ['close', 'Gros plan']]
ZOOM = {'wide': 1.0, 'medium': 1.25, 'close': 1.55}
MOVES_CONSOLE = [['static', 'Caméra fixe'], ['push_in', 'Avance doucement'], ['pull_out', 'Recule doucement'], ['pan_left', 'Glisse vers la gauche'], ['pan_right', 'Glisse vers la droite'],
                 ['pan_up', 'Glisse vers le haut'], ['pan_down', 'Glisse vers le bas'], ['drift', 'Dérive lente'], ['handheld', "Caméra à l'épaule"]]
TRANSITIONS = [['cut', 'Coupe'], ['fade', 'Fondu au noir'], ['flash', 'Flash blanc']]
FACE_FR = {'neutral': 'Neutre', 'calm': 'Calme', 'happy': 'Content', 'joy': 'Joyeux', 'smile_sad': 'Sourire triste', 'sad': 'Triste', 'crying': 'En pleurs', 'angry': 'En colère',
           'furious': 'Furieux', 'scared': 'Effrayé', 'nervous': 'Inquiet', 'shocked': 'Choqué', 'surprised': 'Surpris', 'grin': 'Sourire inquiétant', 'laugh': 'Rit', 'smirk': 'Sourire en coin',
           'excited': 'Excité', 'proud': 'Fier', 'determined': 'Déterminé', 'suspicious': 'Méfiant', 'thinking': 'Pense', 'confused': 'Perdu', 'tired': 'Fatigué', 'sleeping': 'Endormi',
           'closed': 'Yeux fermés', 'bored': "S'ennuie", 'cool': 'Détendu', 'disgusted': 'Dégoûté', 'dizzy': 'Étourdi', 'evil': 'Méchant', 'love': 'Amoureux', 'pain': 'A mal',
           'shy': 'Timide', 'silly': 'Rigolo', 'wink': 'Clin d\'œil', 'urgent': 'Pressé', 'talk': 'Parle', 'ko': 'K.O.', 'skull': 'Crâne', 'robot': 'Robot', 'alien': 'Extraterrestre',
           'creature': 'Monstre', 'double': 'Double'}


def _faces(style):
    if style == 'console':
        from .engines.console import figure2d as F2
        ids = list(F2.EXPR)
    else:
        from .director.validate import FACES
        ids = sorted(FACES, key=lambda f: (f not in ('neutral', 'happy', 'sad', 'scared', 'nervous', 'angry', 'shocked', 'surprised', 'grin', 'creature'), f))
    return [[f, FACE_FR.get(f, f.replace('_', ' ').capitalize())] for f in ids]


def _check_style(style):
    if style not in STYLES: raise ValueError(f"Style inconnu « {style} » (attendu : {', '.join(STYLES)}).")


def _mode(style, episode, index):
    """`console` | `acted` (mise en scène par intentions : `camera.shot` + `move`) | `classic` (anciens épisodes PS1 : `camera.preset` + `move`, autre vocabulaire)"""
    if style == 'console': return 'console'
    if episode is None: return 'acted'
    sh = episode['shots'][index]
    if style == 'voxel':
        from .voxelgpu import from_ps1
        if not from_ps1.is_ps1(episode): return 'acted'
    from .acting.timeline import uses_acting
    return 'acted' if uses_acting(episode, sh) else 'classic'


def options(style, episode=None, index=None):
    """ce que le style sait RÉELLEMENT faire ; une option absente n'est pas implémentée dans ce style. Avec `episode` et `index`, le vocabulaire de CE plan
    (un ancien épisode PS1 n'a pas les mêmes cadrages ni les mêmes mouvements qu'un épisode mis en scène) ; `mode` dit lequel."""
    _check_style(style); mode = _mode(style, episode, index)
    sizes, moves = {'console': (SIZES_CONSOLE, MOVES_CONSOLE), 'acted': (SIZES_3D, MOVES_3D), 'classic': (SIZES_CLASSIC, MOVES_CLASSIC)}[mode]
    return {'mode': mode, 'transitions': copy.deepcopy(TRANSITIONS), 'moves': copy.deepcopy(moves), 'faces': _faces(style), 'sizes': copy.deepcopy(sizes)}


def style_of(meta, settings=None):
    """métadonnées d'un projet -> 'ps1' | 'voxel' | 'console' (comme l'interface et le pipeline)"""
    if (meta or {}).get('style') == 'console': return 'console'
    if str((meta or {}).get('render_engine') or (settings or {}).get('render_engine') or 'pixel3d').lower() == 'voxel': return 'voxel'
    return 'ps1'


def _is_directed(sh):
    cam = sh.get('camera') or {}
    return cam.get('rig') == 'path' or bool(sh.get('tracks')) or (cam.get('preset') == 'free' and bool(cam.get('keys')))


def _ids(lst): return {x[0] for x in lst}


def apply_patch(episode, index, patch, style):
    """copie de `episode` avec `patch` appliqué au plan `index` ; ValueError (français) si le plan ou le réglage n'existe pas dans ce style"""
    _check_style(style)
    if not isinstance(episode, dict) or not episode.get('shots'): raise ValueError("Ce projet n'a pas encore de plans.")
    n = len(episode['shots'])
    if not isinstance(index, int) or not 0 <= index < n: raise ValueError(f"Le plan {index + 1 if isinstance(index, int) else index} n'existe pas (il y a {n} plans).")
    ep = copy.deepcopy(episode); sh = ep['shots'][index]; patch = patch or {}; opt = options(style, episode, index); mode = opt['mode']
    where = 'Console 2D' if style == 'console' else 'ce plan'
    unknown = set(patch) - {'camera', 'actors', 'transition', 'note'}
    if unknown: raise ValueError('Réglage inconnu : ' + ', '.join(sorted(unknown)) + '.')
    cam = patch.get('camera')
    if cam:
        if _is_directed(sh): raise ValueError("La caméra de ce plan est écrite à la main, image par image : elle ne se règle pas ici.")
        sz, mv = cam.get('shot'), cam.get('move')                # absent = inchangé ; `static` = caméra fixe
        if sz is not None and sz not in _ids(opt['sizes']): raise ValueError(f"Cadrage « {sz} » indisponible pour {where}.")
        if mv is not None and mv not in _ids(opt['moves']): raise ValueError(f"Mouvement « {mv} » indisponible pour {where}.")
        c = dict(sh.get('camera') or {})
        if mode == 'console':
            if sz is not None: c['zoom'] = ZOOM[sz]
            if mv is not None: c['move'] = mv                 # `static` explicite : sans clé, ce moteur dérive lentement
        else:
            if sz is not None:
                if mode == 'classic' and sz in NEEDS_SUBJECT and not c.get('subject'): raise ValueError("Ce cadrage a besoin d'un personnage cadré, et ce plan n'en désigne aucun.")
                if mode == 'classic': c['preset'] = sz
                else: c['shot'] = sz; c.pop('preset', None)
            if mv == 'static': c.pop('move', None)
            elif mv is not None: c['move'] = mv
        sh['camera'] = c
    for a in patch.get('actors') or []:
        aid, face = a.get('id'), a.get('face')
        if face not in _ids(opt['faces']): raise ValueError(f"Expression « {face} » indisponible pour {where}.")
        tgt = next((x for x in (sh.get('actors') or []) if isinstance(x, dict) and x.get('id') == aid), None)
        if tgt is None:
            known = any(isinstance(x, dict) and x.get('id') == aid for s_ in ep['shots'][:index] for x in (s_.get('actors') or [])) or aid in (ep.get('cast') or {})
            if mode == 'classic' or not known: raise ValueError(f"Le personnage « {aid} » n'est pas dans ce plan.")
            tgt = {'id': aid}; sh.setdefault('actors', []).append(tgt)       # il est déjà en scène depuis un plan précédent : seule son expression change
        tgt['face'] = face
    tr = patch.get('transition')
    if tr is not None:
        if tr not in _ids(opt['transitions']): raise ValueError(f"Transition « {tr} » indisponible dans ce style (proposées : {', '.join(_ids(opt['transitions']))}).")
        fx = dict(sh.get('fx') or {}); prev = ep['shots'][index - 1] if index else None; pfx = dict(prev.get('fx') or {}) if prev is not None else None
        for k in ('fade_in', 'flash'): fx.pop(k, None)
        if pfx is not None: pfx.pop('fade_out', None)
        if tr == 'fade':
            fx['fade_in'] = FADE_S
            if pfx is not None: pfx['fade_out'] = FADE_S
        elif tr == 'flash': fx['flash'] = FLASH
        for s_, f_ in ((sh, fx), (prev, pfx)):
            if s_ is None: continue
            if f_: s_['fx'] = f_
            else: s_.pop('fx', None)
    if 'note' in patch:
        note = str(patch['note'] or '').strip()
        if note: sh['note'] = note
        else: sh.pop('note', None)
    return ep


def current(episode, index, style):
    """réglages actuels du plan (pour pré-remplir l'interface) : {'size', 'move', 'faces': {acteur: expression}, 'transition', 'directed'}"""
    _check_style(style)
    sh = episode['shots'][index]; cam = sh.get('camera') or {}; fx = sh.get('fx') or {}; mode = _mode(style, episode, index)
    if mode == 'console':
        try: z = float(cam.get('zoom') or 1.)
        except (TypeError, ValueError): z = 1.                          # zoom animé (suite de valeurs) : proche du plan large
        size = min(ZOOM, key=lambda k: abs(ZOOM[k] - z)); move = cam.get('move', 'drift')
    elif mode == 'classic': size = cam.get('preset') or 'wide'; move = cam.get('move') or 'static'
    else:
        alias = {'closeup': 'close', 'high_corner': 'wide', 'low': 'full', 'push_in': 'dolly_in', 'pull_out': 'dolly_out', 'push': 'dolly_in'}
        size = cam.get('shot') or alias.get(cam.get('preset'), cam.get('preset')) or 'wide'; move = alias.get(cam.get('move'), cam.get('move') or 'static')
    faces = {}
    for s_ in episode['shots'][:index + 1]:                         # l'expression d'un personnage reste celle de sa dernière mention
        for a in (s_.get('actors') or []):
            if isinstance(a, dict) and a.get('id') and (a.get('face') or a['id'] not in faces): faces[a['id']] = a.get('face') or 'neutral'
    here = {a['id'] for a in (sh.get('actors') or []) if isinstance(a, dict) and a.get('id')} | {x for x in ([cam.get('on')] if isinstance(cam.get('on'), str) else cam.get('on') or []) if isinstance(x, str)}
    if mode == 'classic': here = {a['id'] for a in (sh.get('actors') or []) if isinstance(a, dict) and a.get('id')}          # ces épisodes : seuls les personnages listés dans le plan se règlent
    known = set(faces) | set(episode.get('cast') or {})
    return {'mode': mode, 'size': size, 'move': move, 'faces': {k: faces.get(k, 'neutral') for k in sorted(here) if k in known or mode == 'classic'},
            'transition': 'fade' if fx.get('fade_in') else 'flash' if fx.get('flash') else 'cut', 'directed': _is_directed(sh)}


# ------------------------------------------------------------------------------------------------------------ VOXEL : fondus et flashs
def apply_to_contract(c, ep):
    """`fx.fade_in` / `fx.fade_out` / `fx.flash` des plans de l'épisode -> événements `fade` / `flash` du contrat VOXEL (le peintre les lit ; le chemin PS1 -> VOXEL
    ne les traduisait pas). Sans ces clés, le contrat est rendu tel quel."""
    shots = (ep or {}).get('shots') or []
    if not any((s.get('fx') or {}).keys() & {'fade_in', 'fade_out', 'flash'} for s in shots if isinstance(s, dict)): return c
    win = {}
    for st in c.get('stages') or []:
        m = re.match(r'^(\d+)_', str(st.get('id', '')))
        if not m: return c                                               # étapes qui ne portent pas le numéro du plan (épisode VOXEL natif) : on ne devine pas
        i = int(m.group(1)); a, b = win.get(i, (1e9, -1e9)); win[i] = (min(a, st['t0']), max(b, st['t1']))
    ev = []
    for k, sh in enumerate(shots):
        fx = (sh.get('fx') or {}) if isinstance(sh, dict) else {}
        if k not in win: continue
        t0, t1 = win[k]
        if fx.get('fade_in'): ev.append({'type': 'fade', 't0': round(t0, 3), 't1': round(t0 + float(fx['fade_in']), 3), 'from': 0., 'to': 1.})
        if fx.get('fade_out'): ev.append({'type': 'fade', 't0': round(t1 - float(fx['fade_out']), 3), 't1': round(t1, 3), 'from': 1., 'to': 0.})
        if fx.get('flash'): ev.append({'type': 'flash', 't0': round(t0, 3), 't1': round(t0 + .25, 3), 'from': 1., 'to': 0., 'peak': round(min(1., float(fx['flash'])), 3)})
    if ev: c = dict(c, fx=list(c.get('fx') or []) + ev)
    return c


# ------------------------------------------------------------------------------------------------------------ rendu du clip
CLIPS = 'preview_clips'
PREVIEW_FPS = 12


def _project(slug):
    from . import pipeline as P
    pr = P.Project(slug)
    if not os.path.isdir(pr.dir) or not pr.meta: raise ValueError(f"Le projet « {slug} » n'existe pas.")
    for f, why in (('episode.json', "Pas encore de plans : propose les plans d'abord."), ('lines.json', "La voix n'est pas encore calée sur le script : cale la voix d'abord.")):
        if not pr.exists(f): raise ValueError(why)
    return pr


def _probe(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,r_frame_rate:format=duration', '-of', 'json', str(path)], capture_output=True, text=True)
    j = json.loads(r.stdout or '{}'); s = (j.get('streams') or [{}])[0]; n, d = (s.get('r_frame_rate') or '0/1').split('/')
    return dict(seconds=round(float(j.get('format', {}).get('duration', 0) or 0), 2), fps=round(float(n) / float(d or 1), 2) if float(d or 1) else 0, size=[s.get('width'), s.get('height')])


def _key(pr, patched, index, aspect, seconds, lead, style):
    h = hashlib.sha1(); h.update(json.dumps([patched, index, aspect, seconds, lead, style], sort_keys=True, ensure_ascii=False, default=str).encode())
    for f in ('lines.json', 'mix.wav', 'voice.mp3'):
        try: st = os.stat(pr.p(f)); h.update(f'{f}:{st.st_size}:{int(st.st_mtime)}'.encode())
        except OSError: pass
    h.update((pr.meta.get('render_engine') or '').encode()); return h.hexdigest()[:10]


def _audio_mux(video, wav, start, dur, out):
    """vidéo + extrait de `wav` calé sur [start, start + dur] -> mp4 (sans `wav` : la vidéo seule)"""
    if wav and os.path.exists(wav):
        cmd = ['ffmpeg', '-y', '-v', 'error', '-i', str(video), '-ss', f'{start:.3f}', '-t', f'{dur:.3f}', '-i', str(wav), '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k',
               '-ac', '2', '-af', f'afade=t=in:d=0.03,afade=t=out:st={max(0., dur - .05):.3f}:d=0.05', '-shortest', '-movflags', '+faststart', str(out)]
    else: cmd = ['ffmpeg', '-y', '-v', 'error', '-i', str(video), '-c:v', 'copy', '-movflags', '+faststart', str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: raise RuntimeError("Assemblage de l'extrait impossible : " + r.stderr[-300:])


# --- PS1 et Console : le moteur CPU, quelques processus, basse résolution -------------------------------------------
_W = {}


def _w_init(style, ep, lines, env, dur, aspect, size):
    os.environ.setdefault('OMP_NUM_THREADS', '1')
    from . import pipeline as P
    _W['eng'] = P.make_engine('console' if style == 'console' else 'pixel3d', ep, lines, env, dur, aspect); _W['size'] = size


def _w_frame(g):
    from PIL import Image
    im = _W['eng'].frame(g).convert('RGB')
    if im.size != tuple(_W['size']): im = im.resize(tuple(_W['size']), Image.LANCZOS)
    return im.tobytes()


def _render_cpu(pr, style, ep, lines, aspect, t_a, t_b, out_video, progress, log, workers=None):
    import multiprocessing as mp, numpy as np
    from . import pipeline as P
    dur = P.duration_of(ep, lines); env = np.load(pr.p('env.npy')) if pr.exists('env.npy') else np.zeros(10)
    size = (270, 480) if aspect == '9:16' else (480, 270); n = max(2, int(round((t_b - t_a) * PREVIEW_FPS)))
    times = [t_a + i / PREVIEW_FPS for i in range(n)]; workers = workers or max(1, min(6, (os.cpu_count() or 2) - 2))
    cmd = ['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{size[0]}x{size[1]}', '-r', str(PREVIEW_FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22',
           '-pix_fmt', 'yuv420p', str(out_video)]
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE); t0 = time.time()
    ctx = mp.get_context('spawn')
    try:
        with ctx.Pool(workers, initializer=_w_init, initargs=(style, ep, lines, env, dur, aspect, size)) as pool:
            for k, b in enumerate(pool.imap(_w_frame, times, chunksize=1)):
                enc.stdin.write(b)
                if progress and k % 3 == 0: progress(.1 + .8 * k / n, f'{k}/{n} images ({k / max(1e-3, time.time() - t0):.1f} i/s)')
    except BrokenPipeError: pass
    finally:
        try: enc.stdin.close()
        except OSError: pass
        enc.wait(timeout=60)
    if enc.returncode: raise RuntimeError("Encodage de l'aperçu impossible : " + (enc.stderr.read() or b'').decode('utf-8', 'replace')[-300:])
    return n / PREVIEW_FPS


# --- VOXEL : le peintre GPU, uniquement la fenêtre du plan ------------------------------------------------------------
def _render_voxel(pr, ep, lines, aspect, index, lead_s, seconds, progress, log, transition_wanted):
    from . import pipeline as P
    from .voxelgpu import studio_bridge as VB, render, contract as C
    shadow = tempfile.mkdtemp(prefix='_ombre_', dir=pr.p(CLIPS))
    try:
        for f in ('project.json', 'lines.json', 'script.txt', 'env.npy', 'voice.mp3'):
            if pr.exists(f): shutil.copy2(pr.p(f), os.path.join(shadow, f))
        sp = P.Project.__new__(P.Project); sp.slug = pr.slug; sp.dir = shadow; sp.meta = dict(pr.meta); sp.write_json('episode.json', ep)
        if progress: progress(.08, 'Mise en scène du plan')
        c = VB.contract_of(sp, aspect, log)
        stages = [s for s in c['stages'] if (re.match(r'^(\d+)_', str(s.get('id', ''))) and int(re.match(r'^(\d+)_', str(s['id'])).group(1)) == index)] or \
                 ([c['stages'][index]] if len(c['stages']) == len(ep['shots']) else [])
        if not stages: raise RuntimeError("Ce plan est introuvable dans le contrat VOXEL.")
        t0 = min(s['t0'] for s in stages); t1 = max(s['t1'] for s in stages)
        a = max(0., t0 - lead_s); b = min(t1, a + seconds)
        W, H = (540, 960) if aspect == '9:16' else (960, 540)
        cpath = Path(shadow) / 'contract.json'; C.save(c, cpath); vid = Path(shadow) / 'video_only.mp4'
        if progress: progress(.15, 'Peinture sur la carte graphique')
        for transport in ('bin', 'b64'):
            try: render.run_painter(cpath, vid, 'nvidia', (W, H), start=a, end=b, crf=20, quiet=True, fallback=True, transport=transport); break
            except RuntimeError as e:
                if transport == 'b64' or 'Failed to fetch' not in str(e): raise
                log('Transport binaire GPU refusé : nouvel essai en base64.')
        return vid, a, b, shadow
    except BaseException:
        shutil.rmtree(shadow, ignore_errors=True); raise


def render_shot_clip(slug, index, patch=None, aspect='9:16', seconds=None, lead=0.6, progress=None, log=print):
    """Clip du plan `index` avec `patch` appliqué (sans rien enregistrer) -> dict JSON :
    {file (relatif au dossier du projet), seconds, fps, size, style, supported (transitions), notes, cached, window, elapsed}"""
    from . import pipeline as P
    t_start = time.time(); seconds = float(seconds or 5.); lead = float(lead)
    if aspect not in ('9:16', '16:9'): raise ValueError("Format inconnu (attendu : 9:16 ou 16:9).")
    pr = _project(slug); settings = P.load_settings(); style = style_of(pr.meta, settings)
    episode = pr.read_json('episode.json'); patched = apply_patch(episode, int(index), patch or {}, style); index = int(index)
    transition_wanted = bool((patch or {}).get('transition')) or bool((patched['shots'][index].get('fx') or {}).keys() & {'fade_in', 'flash'}) or (index > 0 and 'fade_out' in (patched['shots'][index - 1].get('fx') or {}))
    lead_s = max(lead, 1.0) if transition_wanted else lead
    os.makedirs(pr.p(CLIPS), exist_ok=True)
    key = _key(pr, patched, index, aspect, seconds, lead_s, style); name = f's{index + 1:02d}_{key}.mp4'; out = pr.p(CLIPS, name); meta_f = out[:-4] + '.json'
    notes = []
    if os.path.exists(out) and os.path.exists(meta_f):
        info = json.load(open(meta_f, encoding='utf-8')); info.update(cached=True, elapsed=round(time.time() - t_start, 2)); return info
    lines, _ = P.merged_lines(pr); ep = patched
    tmp_video = None; shadow = None
    try:
        if style == 'voxel':
            tmp_video, a, b, shadow = _render_voxel(pr, patched, lines, aspect, index, lead_s, seconds, progress, log, transition_wanted)
            fps = 24
        else:
            import numpy as np
            dur = P.duration_of(ep, lines); eng = P.make_engine('console' if style == 'console' else 'pixel3d', copy.deepcopy(ep), lines, np.zeros(10), dur, aspect)
            spans = eng.ctx.tl.spans if hasattr(eng, 'ctx') else eng.tl.spans; del eng
            t0, t1 = spans[index]; a = max(0., t0 - lead_s); b = min(t1, a + seconds); shadow = tempfile.mkdtemp(prefix='_cpu_', dir=pr.p(CLIPS)); tmp_video = Path(shadow) / 'video_only.mp4'
            if progress: progress(.05, 'Préparation du moteur')
            _render_cpu(pr, style, copy.deepcopy(ep), lines, aspect, a, b, tmp_video, progress, log)
        if progress: progress(.94, 'Assemblage avec le son')
        wav = pr.p('mix.wav') if pr.exists('mix.wav') else None
        if not wav: notes.append("Pas de son : le mixage du projet n'existe pas encore.")
        _audio_mux(tmp_video, wav, a, b - a, out)
    finally:
        if shadow: shutil.rmtree(shadow, ignore_errors=True)
    info = dict(_probe(out), file=f'{CLIPS}/{name}', style=style, supported=[t[0] for t in options(style)['transitions']], notes=notes, cached=False,
                window=[round(a, 2), round(b, 2)], elapsed=round(time.time() - t_start, 1))
    if transition_wanted and index > 0: notes.append(f'Le clip commence {lead_s:g} s avant le plan, pour montrer la jonction avec le plan précédent.')
    json.dump(info, open(meta_f, 'w', encoding='utf-8'), ensure_ascii=False)
    if progress: progress(1., 'Aperçu prêt')
    return info


def purge_clips(slug):
    """supprime les clips d'aperçu d'un projet -> octets libérés"""
    from . import pipeline as P
    d = P.Project(slug).p(CLIPS); freed = 0
    if os.path.isdir(d):
        for r, _, fs in os.walk(d):
            for f in fs:
                try: freed += os.path.getsize(os.path.join(r, f))
                except OSError: pass
        shutil.rmtree(d, ignore_errors=True)
    return freed
