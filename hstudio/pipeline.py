"""Project pipeline: script -> voice -> alignment -> mise en scène -> mix -> render -> thumbnail/metadata -> compilation."""
import os, json, re, time, shutil, subprocess, multiprocessing as mp, unicodedata
import numpy as np
from . import paths, script as S, tts, align, voices as V, mediacheck as M
from .director import direct, metadata
from .audio.mixer import Mixer, loudnorm

DEFAULT_SETTINGS = {
    'elevenlabs_api_key': '', 'elevenlabs_voice_id': '', 'elevenlabs_narrator_voice_id': '', 'elevenlabs_model': 'eleven_v3',
    'voice_stability': .5, 'voice_similarity': .75, 'voice_style': 0., 'voice_speed': 1.0,
    'director': 'claude', 'anthropic_api_key': '', 'claude_model': 'claude-opus-5-5', 'claude_effort': 'high', 'claude_fallbacks': True,
    'gemini_api_key': '', 'gemini_model': 'gemini-2.5-pro',
    'ollama_host': 'http://localhost:11434', 'ollama_model': 'qwen2.5:32b-instruct', 'ollama_ctx': 32768,
    'local_base_url': 'http://localhost:1234/v1', 'local_model': 'local-model',
    'alignment': 'auto', 'whisper_model': 'large-v3',
    'workers': 0, 'quality': 'max',
}

def load_env_file(path=None):
    """keys from a local .env (written by `npx @elevenlabs/cli onboard connect`, ignored by Git, never in the code).

    python-dotenv when it is installed, otherwise a minimal reader. A variable already set in the environment wins,
    and a missing file is not an error: with no key at all the studio keeps working in draft-voice mode."""
    path = path or os.path.join(paths.ROOT, '.env')
    if not os.path.exists(path): return
    try:
        from dotenv import load_dotenv
        load_dotenv(path); return
    except Exception: pass
    try:
        for raw in open(path, encoding='utf-8'):
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k, v = line.split('=', 1); k = k.strip()
            if k.startswith('export '): k = k[7:].strip()
            v = v.strip().strip('"\'')
            if k and not os.environ.get(k): os.environ[k] = v
    except Exception: pass

def load_settings():
    s = dict(DEFAULT_SETTINGS)
    load_env_file()
    if os.path.exists(paths.SETTINGS_FILE):
        try:
            with open(paths.SETTINGS_FILE, encoding='utf-8') as stream: s.update(json.load(stream))
        except Exception: pass
    private_settings = os.path.join(paths.CONFIG, 'settings.local.json')
    if os.path.exists(private_settings):
        try:
            with open(private_settings, encoding='utf-8') as stream: s.update(json.load(stream))
        except (OSError, ValueError): pass
    # config/settings.json ships with "COLLE_ICI_..." placeholders: treat them as empty
    s = {k: ('' if isinstance(v, str) and v.startswith('COLLE_ICI') else v) for k, v in s.items()}
    for k, env in (('elevenlabs_api_key', 'ELEVENLABS_API_KEY'), ('anthropic_api_key', 'ANTHROPIC_API_KEY'), ('gemini_api_key', 'GEMINI_API_KEY')):
        if not s.get(k) and os.environ.get(env): s[k] = os.environ[env]
    return s

def save_settings(upd):
    s = load_settings(); s.update({k: v for k, v in upd.items() if k in DEFAULT_SETTINGS})
    os.makedirs(paths.CONFIG, exist_ok=True)
    # Keys loaded from .env must never be copied into the tracked settings template when saving the UI.
    private_settings = os.path.join(paths.CONFIG, 'settings.local.json')
    fd = os.open(private_settings, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream: json.dump(s, stream, indent=1)
    return s

def read_script(pr):
    raw = open(pr.p('script.txt'), 'rb').read()
    try: return raw.decode('utf-8-sig')
    except UnicodeDecodeError: return raw.decode('cp1252')      # script saved as "ANSI" by an old Windows editor

def slugify(name):
    s = unicodedata.normalize('NFD', name.lower()); s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', '_', s).strip('_') or 'projet'

class Project:
    def __init__(self, slug):
        self.slug = slug; self.dir = os.path.join(paths.PROJECTS, slug)
        self.meta = json.load(open(self.p('project.json'), encoding='utf-8')) if os.path.exists(self.p('project.json')) else {}
    def p(self, *a): return os.path.join(self.dir, *a)
    def save(self): os.makedirs(self.dir, exist_ok=True); json.dump(self.meta, open(self.p('project.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    def exists(self, f): return os.path.exists(self.p(f))
    def read_json(self, f, default=None): return json.load(open(self.p(f), encoding='utf-8')) if self.exists(f) else default
    def write_json(self, f, data): json.dump(data, open(self.p(f), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    @staticmethod
    def create(name, style='pixel3d', **kw):
        slug = slugify(kw.get('slug') or name); base = slug; k = 2
        while os.path.exists(os.path.join(paths.PROJECTS, slug)): slug = f'{base}_{k}'; k += 1
        pr = Project(slug); os.makedirs(pr.dir, exist_ok=True)
        pr.meta = {'name': name, 'style': style, 'series': kw.get('series', ''), 'part_label': kw.get('part_label', ''),
                   'hud_title': kw.get('hud_title', "L'ÉTAGE 0|N'EXISTE PAS"), 'previous_choice': kw.get('previous_choice', ''),
                   'previous_choice_text': kw.get('previous_choice_text', ''), 'bible': kw.get('bible', ''), 'previous': kw.get('previous', ''),
                   'notes': kw.get('notes', ''), 'director': kw.get('director', ''), 'created': time.time()}
        pr.save(); return pr
    def status(self):
        # « renders » ne liste que des vidéos **lisibles** : le dossier contient aussi les rendus écartés et
        # leur note de raison, et un lecteur vidéo pointé sur l'un d'eux n'afficherait rien sans rien expliquer.
        d = self.p('renders')
        vids = [f for f in sorted(os.listdir(d)) if f.endswith('.mp4') and '.ECARTE-' not in f
                and M.playable(os.path.join(d, f))] if os.path.isdir(d) else []
        st = {'script': self.exists('script.txt'), 'voice': self.exists('voice.mp3'), 'lines': self.exists('lines.json'),
              'episode': self.exists('episode.json'), 'mix': self.exists('mix.wav'), 'thumbnail': self.exists('thumbnail_16x9.jpg'),
              'metadata': self.exists('metadata.json'), 'renders': vids}
        return st

# ------------------------------------------------------------------ steps
def script_lines(pr):
    """lines of the script; with library characters, "LÉA : ..." gives the speaker and is removed from the voice"""
    lines = S.parse_script(read_script(pr))
    if pr.meta.get('cast'):
        from .director.scene import names_of, split_speaker
        names = names_of(pr.meta['cast'])
        for l in lines:
            who, rest = split_speaker(l['display'], names)
            if who:
                l['speaker'] = who; l['display'] = rest; l['text'] = rest.replace('*', '')
                l['tts'] = split_speaker(l['tts'], names)[1]; l['dialogue'] = True
    return lines

def step_draft_voice(pr, settings, log=print):
    """free local "draft" voice (babble with each character's timbre) and its exact timings: no API, no cost.
    Replace it later with the ElevenLabs voice (step voice) for the real episode."""
    from .audio import scratch_voice as SV
    from .acting import cast as CAST
    lines = script_lines(pr)
    if not lines: raise RuntimeError('Le script est vide.')
    t = .4; out = []
    for i, l in enumerate(lines):
        d = max(1.2, min(6., .45 + .068 * len(l['text'])))
        out.append(dict(l, start=round(t, 3), end=round(t + d, 3), segs=[[round(t, 3), round(t + d, 3)]])); t += d + (.6 if l.get('pause_after') else .3)
    voices = {}
    for c in pr.meta.get('cast') or []:
        v = ((CAST.character(c) or {}).get('voice') or {}).get('draft')
        if v: voices[c] = v
    sig, env = SV.render(out, [l.get('speaker') or '_narrateur' for l in out], dict(voices, _narrateur='man'), out[-1]['end'] + 1.2)
    os.makedirs(pr.p('work'), exist_ok=True); SV.write_mp3(sig, pr.p('voice.mp3'), pr.p('work')); np.save(pr.p('env.npy'), env)
    pr.write_json('lines.json', out)
    for f in ('mix.wav', 'tts_alignment.json'):
        if pr.exists(f): os.remove(pr.p(f))
    log(f'Voix de brouillon (gratuite, locale) : {len(out)} lignes, {out[-1]["end"]:.1f} s. Remplace-la par la voix ElevenLabs pour l\'épisode final.')
    return out

def step_voice(pr, settings, log=print):
    """ElevenLabs voice: one voice_id per character and a distinct narrator (see voices.py); a project that casts
    no voice keeps the single global voice."""
    lines = script_lines(pr)
    if not lines: raise RuntimeError('Le script est vide.')
    key = settings.get('elevenlabs_api_key')
    speakers = V.speakers_of(lines)
    voices = V.resolve(pr.meta, settings, speakers)
    missing = [v['name'] for v in voices.values() if not v['voice_id']]
    if not key or missing:
        raise RuntimeError('Clé ElevenLabs ou voix manquante (Réglages)' + (f" : {', '.join(missing)}" if missing else '') + '.')
    for sp in speakers:
        v = voices[sp]; log(f"Voix de {v['name']} : {v['voice_id']} ({v['source']})")
    vs = tts.voice_settings(float(settings.get('voice_stability', .5)), float(settings.get('voice_similarity', .75)),
                            float(settings.get('voice_style', 0.)), float(settings.get('voice_speed', 1.)))
    al = V.synthesize_cast(key, lines, voices, pr.p('voice.mp3'), pr.p('work'),
                           model_id=pr.meta.get('tts_model') or settings.get('elevenlabs_model', 'eleven_v3'), vs=vs, log=log)
    pr.write_json('tts_alignment.json', al)
    for f in ('lines.json', 'mix.wav'):
        if pr.exists(f): os.remove(pr.p(f))
    log(f'Voix générée : {tts.ffprobe_duration(pr.p("voice.mp3")):.1f} s')

def step_align(pr, settings, log=print):
    lines = script_lines(pr)
    if not lines: raise RuntimeError('Le script est vide.')
    audio = pr.p('voice.mp3')
    if not os.path.exists(audio): raise RuntimeError('Pas de voix : génère-la (ElevenLabs) ou importe ton MP3.')
    method = settings.get('alignment', 'auto'); out = None
    if pr.exists('tts_alignment.json') and method in ('auto', 'tts'):
        out = align.match_lines(lines, align.words_from_alignment(pr.read_json('tts_alignment.json'))); log('Alignement : horodatage ElevenLabs (au mot près).')
    if out is None and method in ('auto', 'elevenlabs') and settings.get('elevenlabs_api_key'):
        try:
            words = tts.forced_alignment(settings['elevenlabs_api_key'], audio, '\n'.join(l['text'] for l in lines))
            out = align.match_lines(lines, words); log('Alignement : ElevenLabs Forced Alignment (au mot près).')
        except Exception as e: log(f'Alignement ElevenLabs impossible ({e}).')
    if out is None and method in ('auto', 'whisper'):
        try:
            words = align.whisper_words(audio, settings.get('whisper_model', 'large-v3'))
            out = align.match_lines(lines, words); log('Alignement : faster-whisper local (au mot près).')
        except ImportError:
            if method == 'whisper': log('faster-whisper n\'est pas installé (pip install faster-whisper).')
        except Exception as e: log(f'Whisper impossible ({e}).')
    if out is None:
        out = align.silence_align(lines, audio); log('Alignement : silences entre les phrases (hors ligne).')
    for l, src in zip(out, lines):
        if src.get('speaker'): l['speaker'] = src['speaker']
    pr.write_json('lines.json', out)
    np.save(pr.p('env.npy'), align.envelope(audio, 30, pr.p('work') if os.path.isdir(pr.p('work')) else pr.dir))
    log(f'{len(out)} lignes calées, de {out[0]["start"]:.2f} s à {out[-1]["end"]:.2f} s.')
    return out

# ------------------------------------------------------------------ local audio input (the owner's own recordings, no TTS)
def _forget_voice(pr, keep_lines=False):
    """what stops being true as soon as the voice track changes"""
    for f in ('tts_alignment.json', 'mix.wav') + (() if keep_lines else ('lines.json',)):
        if pr.exists(f): os.remove(pr.p(f))

def import_voice(pr, source, log=print):
    """one local audio file as the whole voice track: validated, then converted into voice.mp3. No API, no cost.
    The alignment step times the script on it afterwards (silences, offline, if no key is set)."""
    from . import audio_in as AI
    info = AI.check(source)
    AI.to_mp3(info['path'], pr.p('voice.mp3'))
    _forget_voice(pr)
    log(f"Voix importée : {info['name']} ({info['duration']:.1f} s, {info['codec']} {info['sample_rate']} Hz, "
        f"{info['channels']} canal(aux), {info['bytes'] / 1e6:.1f} Mo) -> voice.mp3. Cale-la ensuite (étape Calage).")
    return info

def add_clips(pr, sources, log=print):
    """validated copies of local files into projects/<slug>/audio/, the only folder a voice sheet may read"""
    import shutil
    from . import audio_in as AI
    d = AI.audio_dir(pr.dir, create=True); out = []
    for src in sources:
        info = AI.check(src); name = AI.safe_name(info['name']); dst = os.path.join(d, name)
        if os.path.realpath(info['path']) != os.path.realpath(dst): shutil.copyfile(info['path'], dst)
        out.append(dict(info, name=name)); log(f"Clip ajouté : {name} ({info['duration']:.2f} s)")
    return out

def voice_sheet(pr, log=print):
    """a voice sheet ready to fill in: the clips of projects/<slug>/audio/, in name order, one per script line"""
    from . import audio_in as AI
    lines = script_lines(pr)
    if not lines: raise RuntimeError('Le script est vide.')
    names = AI.clips_of(pr.dir)
    sheet = AI.default_sheet(lines, names); p = AI.write_sheet(pr.dir, sheet)
    log(f'{os.path.basename(p)} : {len(lines)} phrase(s), {len(names)} clip(s) trouvé(s) dans {AI.AUDIO_DIR}/.'
        + ('' if len(names) >= len(lines) else f' Il en manque {len(lines) - len(names)} : complète la colonne "file".'))
    return sheet

def check_sheet(pr, sheet):
    """validates a voice sheet against the project's script without writing anything -> the planned clips"""
    from . import audio_in as AI
    lines = script_lines(pr)
    if not lines: raise RuntimeError('Le script est vide.')
    return AI.plan(pr.dir, lines, sheet)

def step_local_voice(pr, settings, log=print):
    """the owner's own recordings, one clip per script line (narration or character voice): no TTS, no API, no cost.

    The whole voice sheet is validated before anything is written, and the timings are measured on the decoded
    samples, so lines.json is exact and the alignment step is not needed at all."""
    from . import audio_in as AI
    lines = script_lines(pr)
    if not lines: raise RuntimeError('Le script est vide.')
    items = AI.plan(pr.dir, lines)
    os.makedirs(pr.p('work'), exist_ok=True)
    sheet = AI.read_sheet(pr.dir)
    out, dur = AI.assemble(items, lines, pr.p('voice.mp3'), pr.p('work'),
                           lead_in=float(sheet.get('lead_in', .4)), log=log)
    pr.write_json('lines.json', out)
    np.save(pr.p('env.npy'), align.envelope(pr.p('voice.mp3'), 30, pr.p('work')))
    _forget_voice(pr, keep_lines=True)
    who = sorted({l.get('speaker') or 'narrateur' for l in out})
    log(f'Voix locale : {len(out)} clip(s) assemblés, {dur:.1f} s, voix de {", ".join(who)}. Aucun appel TTS.')
    return out

def step_direct(pr, settings, log=print):
    lines = pr.read_json('lines.json')
    if not lines: raise RuntimeError('Aligne d\'abord la voix.')
    project = dict(pr.meta); project['style'] = pr.meta.get('style', 'pixel3d')
    raw = []
    ep, W, used = direct(project, lines, settings, log=log, raw_out=raw)
    if pr.exists('episode.json'): shutil.copy(pr.p('episode.json'), pr.p(f'episode_backup_{int(time.time())}.json'))
    pr.write_json('episode.json', ep); pr.write_json('episode_warnings.json', W)
    log(f'Mise en scène ({used}) : {len(ep["shots"])} plans, {len(W)} corrections automatiques.')
    for w in W[:20]: log('  - ' + w)
    try:                                   # V3: what the scene asked for and what the engines lack (nothing replaced silently)
        from .capabilities.audit import report_project
        pr.write_json('capabilities.json', report_project(raw[0] if raw else ep, project['style'], '\n'.join(l.get('text', '') for l in lines), log))
    except Exception as e: log(f'Audit des capacités impossible ({e}).')
    if pr.exists('mix.wav'): os.remove(pr.p('mix.wav'))
    return ep

def merged_lines(pr):
    lines = pr.read_json('lines.json'); ep = pr.read_json('episode.json')
    meta = ep.get('lines', {}) or {}
    out = []
    for i, l in enumerate(lines):
        l = dict(l); m = meta.get(str(i), {}) or {}
        for k in ('keywords', 'label', 'label_color', 'voice_fx', 'sfx', 'no_subtitle', 'silence_before'):
            if m.get(k) is not None: l[k] = m[k]
        out.append(l)
    return out, ep

def duration_of(ep, lines):
    last = ep['shots'][-1]
    extra = 3.0 if (last.get('ui') or {}).get('endcard') else 1.2
    return float(lines[-1]['end'] + extra)

def make_engine(style, ep, lines, env, duration, aspect):
    # opt-in background life (acting/background.py): an episode carrying "extras" gets its figurants written out
    # here, once, on the single path both the mix and the render go through. Without that key -- which is to say
    # for every episode, demo and test of the repository -- `apply` returns the very same object and nothing
    # happens at all. HSTUDIO_EXTRAS=0 closes it globally.
    from .acting import background as _bg
    from . import profiles; profiles.apply(ep)
    ep = _bg.apply(ep)
    if style == 'console':
        from .engines.console.render import ConsoleEngine
        return ConsoleEngine(ep, lines, env, duration, aspect)
    from .engines.pixel3d.render import Pixel3DEngine
    return Pixel3DEngine(ep, lines, env, duration, aspect)

def _voxel(pr, settings):
    """le projet demande-t-il le moteur VOXEL V4 (GPU) ? Sinon rien ne change : PIXEL 3D reste le chemin par défaut."""
    from .voxelgpu import studio_bridge as VB
    return VB if VB.wants_voxel(pr, settings) else None

def step_mix(pr, settings, log=print):
    VB = _voxel(pr, settings)
    if VB: return VB.step_mix(pr, settings, log)
    lines, ep = merged_lines(pr); dur = duration_of(ep, lines)
    eng = make_engine(pr.meta.get('style', 'pixel3d'), ep, lines, np.zeros(10), dur, '9:16')
    spans = eng.ctx.tl.spans if hasattr(eng, 'ctx') else eng.tl.spans
    os.makedirs(pr.p('work'), exist_ok=True)
    mx = Mixer(pr.p('voice.mp3'), lines, ep, dur, pr.meta.get('style', 'pixel3d'), pr.p('work'))
    if hasattr(eng, 'acting_events'):
        from .acting import foley
        mx.foley = foley.cues(eng.acting_events())
    mx.run(spans, pr.p('mix.wav'))
    log(f'Mixage terminé ({dur:.1f} s, -14 LUFS).')

# ------------------------------------------------------------------ rendering
_ENG = None
def _init_worker(style, ep, lines, env, duration, aspect):
    global _ENG
    os.environ.setdefault('OMP_NUM_THREADS', '1')
    _ENG = make_engine(style, ep, lines, env, duration, aspect)
def _render_one(i): return _ENG.frame(i / 30.).convert('RGB').tobytes()

QUALITY = {
    'max': ['-c:v', 'libx264', '-preset', 'slow', '-crf', '17'],
    'standard': ['-c:v', 'libx264', '-preset', 'medium', '-crf', '20'],
    'tiktok': ['-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-maxrate', '1300k', '-bufsize', '2600k'],
}

def step_render(pr, settings, aspect='9:16', quality=None, progress=None, log=print, frames=None, verify='full'):
    """Rend un format et **vérifie le fichier produit** avant de le déclarer terminé.

    `verify='full'` (le défaut) va jusqu'au décodage complet : c'est la seule preuve qu'on peut regarder la
    vidéo en entier. `verify='quick'` s'arrête à la structure et à ffprobe. Un rendu qui ne passe pas est
    **écarté sous un autre nom** (jamais supprimé) pour qu'il ne puisse pas passer pour un artefact valide."""
    VB = _voxel(pr, settings)
    if VB: return VB.step_render(pr, settings, aspect, quality, progress, log, frames, verify)
    lines, ep = merged_lines(pr); dur = duration_of(ep, lines)
    if not pr.exists('mix.wav'): step_mix(pr, settings, log)
    env = np.load(pr.p('env.npy')) if pr.exists('env.npy') else np.zeros(10)
    style = pr.meta.get('style', 'pixel3d'); q = quality or settings.get('quality', 'max')
    W, H = (1080, 1920) if aspect == '9:16' else (1920, 1080)
    os.makedirs(pr.p('renders'), exist_ok=True)
    tag = 'short_9x16' if aspect == '9:16' else 'long_16x9'
    out = pr.p('renders', f'{pr.slug}_{tag}{"_tiktok" if q == "tiktok" else ""}.mp4')
    N = int(dur * 30) if frames is None else frames
    workers = int(settings.get('workers') or 0) or max(1, (os.cpu_count() or 2))
    cmd = ['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', '30', '-i', '-', '-i', pr.p('mix.wav'),
           *QUALITY.get(q, QUALITY['max']), '-pix_fmt', 'yuv420p', '-profile:v', 'high', '-r', '30',
           '-c:a', 'aac', '-b:a', '256k' if q == 'max' else '192k', '-ac', '2', '-shortest', '-movflags', '+faststart', out]
    os.makedirs(pr.p('work'), exist_ok=True)
    # ffmpeg tourne en '-v error' : son journal fait quelques lignes. Il part dans un fichier, pas dans un tuyau
    # que personne ne lit -- un tuyau plein bloquerait l'encodeur, et la panne serait pire que l'absence de trace.
    errlog = pr.p('work', f'ffmpeg_{tag}.log')
    t0 = time.time(); sent = 0; early = False; failure = None
    with open(errlog, 'wb') as ef:
        enc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=ef)
        ctx = mp.get_context('fork') if hasattr(os, 'fork') else mp.get_context('spawn')
        try:
            with ctx.Pool(workers, initializer=_init_worker, initargs=(style, ep, lines, env, dur, aspect)) as pool:
                for k, b in enumerate(pool.imap(_render_one, range(N), chunksize=4)):
                    enc.stdin.write(b); sent = k + 1
                    if k % 30 == 0 and progress: progress(k / N, f'{k}/{N} images, {k / max(1e-3, time.time() - t0):.1f} img/s')
        except BrokenPipeError:
            early = True                 # ffmpeg s'est arrêté avant la dernière image : son journal dira pourquoi
        except BaseException as e:
            # Un worker qui meurt, ou un Ctrl-C, et le rendu s'arrête au milieu. Deux dégâts à empêcher :
            # ffmpeg resterait **orphelin** à tourner sur la machine, et s'il finissait proprement son fichier
            # il écrirait un `moov` — un MP4 court mais valide, que la reprise accepterait comme un rendu fini.
            # On l'arrête donc, et le fichier partiel sera écarté plus bas au lieu de passer pour une vidéo.
            failure = e
        finally:
            try: enc.stdin.close()
            except OSError: pass
            if failure is not None and enc.poll() is None: enc.terminate()
            try: enc.wait(timeout=120)
            except subprocess.TimeoutExpired: enc.kill(); enc.wait()
    if failure is not None:
        kept = M.quarantine(out, f'rendu interrompu après {sent}/{N} images : {type(failure).__name__} : {str(failure)[:200]}')
        if kept != out: log(f'Rendu {aspect} interrompu : fichier partiel conservé sous {os.path.basename(kept)}, rien n\'est supprimé.')
        log(f'Rendu {aspect} interrompu après {sent}/{N} images ; ffmpeg a été arrêté, aucun processus laissé derrière.')
        raise failure
    why = ''
    try: why = open(errlog, encoding='utf-8', errors='replace').read().strip()[:400]
    except OSError: pass

    # Le verdict appartient au fichier, pas à la plomberie : un code de retour nul ne prouve rien (un encodage
    # tué laisse un MP4 sans « moov » et personne ne s'en plaint), et une fin anticipée n'est pas forcément une
    # panne (l'audio peut être la piste la plus courte). On regarde donc ce qui est vraiment sur le disque.
    v = M.describe(out, want=(W, H), full=verify == 'full') if not enc.returncode else M.describe(out, want=(W, H))
    if enc.returncode or not v['ok']:
        reason = v['reason'] or 'ffmpeg a échoué'
        if enc.returncode:
            reason = (f'ffmpeg a échoué (code {enc.returncode}) et n\'a produit aucun fichier'
                      if not os.path.exists(out) else f'ffmpeg a échoué (code {enc.returncode}) : {reason}')
        if why: reason += ' | journal ffmpeg : ' + why
        kept = M.quarantine(out, reason)
        if kept != out: log(f'Rendu {aspect} écarté (conservé sous {os.path.basename(kept)}), rien n\'est supprimé.')
        raise RuntimeError(f'Rendu {aspect} inutilisable : {reason}. Le fichier douteux a été écarté sous un '
                           f'autre nom ; relance le rendu pour le refabriquer.')
    pr.write_json(f'verify_{tag}.json', dict(v, frames_sent=sent, frames_expected=N, seconds=round(time.time() - t0, 1)))
    if early or sent < N:
        log(f'Note : ffmpeg a fermé son entrée après {sent}/{N} images (piste la plus courte). '
            f'Le fichier produit est vérifié et lisible.')
    log(f'Rendu {aspect} terminé : {os.path.basename(out)} ({time.time() - t0:.0f} s). ' + M.summary(v))
    return out

def step_qc(pr, settings, aspect='9:16', log=print, frames=True):
    """quality control of the staging (acting/qc.py): measured checks saved in qc_<aspect>.json

    Le score mesure la **mise en scène**, et il se calcule sans rendu : c'est voulu, et c'est aussi le piège.
    Il a déjà été de 92/100 pour un projet dont le MP4 faisait 48 octets. Le rapport porte donc maintenant un
    bloc `encoded` qui dit l'état du fichier réellement sur le disque. Le score ne bouge pas (il ne parle pas
    du même objet) ; ce qui change, c'est qu'un rendu mort n'est plus passé sous silence."""
    import numpy as np
    from .acting import qc
    VB = _voxel(pr, settings)
    if VB: return VB.step_qc(pr, settings, aspect, log, frames)
    lines, ep = merged_lines(pr)
    eng = make_engine(pr.meta.get('style', 'pixel3d'), ep, lines, np.zeros(10), duration_of(ep, lines), aspect)
    rep = qc.run(eng, ep, lines, frames=frames); rep['aspect'] = aspect; rep['engine'] = pr.meta.get('style', 'pixel3d')

    want = (1080, 1920) if aspect == '9:16' else (1920, 1080)
    tag = 'short_9x16' if aspect == '9:16' else 'long_16x9'
    d = pr.p('renders')
    found = sorted(os.path.join(d, f) for f in (os.listdir(d) if os.path.isdir(d) else [])
                   if f.endswith('.mp4') and tag in f and '.ECARTE-' not in f)
    if not found:
        rep['encoded'] = {'ok': None, 'reason': 'aucun rendu ' + aspect + ' sur le disque : le score ne parle '
                                                'que de la mise en scène'}
        log('Contrôle du fichier : aucun rendu ' + aspect + ' encore produit.')
    else:
        v = M.describe(found[-1], want=want)
        rep['encoded'] = v
        log('Contrôle du fichier : ' + M.summary(v))
        if not v['ok']:
            rep.setdefault('issues', []).append(
                {'level': 'error', 'code': 'render_unusable', 't': None, 'shot': None,
                 'message': 'le rendu ' + os.path.basename(v['path']) + ' n\'est pas lisible : ' + v['reason']
                            + ' — le score ci-dessus ne concerne que la mise en scène, pas ce fichier'})
    qc.save(rep, pr.p(f"qc_{aspect.replace(':', 'x')}.json")); log(qc.summary(rep))
    return rep

def step_preview(pr, settings, aspect='9:16', log=print):
    """one frame per shot (middle) -> contact sheet + individual JPEGs"""
    from PIL import Image
    VB = _voxel(pr, settings)
    if VB: return VB.step_preview(pr, settings, aspect, log)
    lines, ep = merged_lines(pr); dur = duration_of(ep, lines)
    env = np.load(pr.p('env.npy')) if pr.exists('env.npy') else np.zeros(10)
    eng = make_engine(pr.meta.get('style', 'pixel3d'), ep, lines, env, dur, aspect)
    spans = eng.ctx.tl.spans if hasattr(eng, 'ctx') else eng.tl.spans
    d = pr.p('preview'); os.makedirs(d, exist_ok=True)
    for f in os.listdir(d): os.remove(os.path.join(d, f))
    thumbs = []
    for k, (a, b) in enumerate(spans):
        t = a + (b - a) * .6
        im = eng.frame(t); im.save(os.path.join(d, f'shot_{k:03d}.jpg'), quality=88)
        thumbs.append(im.resize((im.width // 5, im.height // 5)))
    cols = 10 if aspect == '9:16' else 6
    tw, th = thumbs[0].size; sheet = Image.new('RGB', (tw * cols, th * ((len(thumbs) + cols - 1) // cols)))
    for k, im in enumerate(thumbs): sheet.paste(im, ((k % cols) * tw, (k // cols) * th))
    sheet.save(pr.p('preview_sheet.jpg'), quality=85)
    log(f'Aperçu : {len(thumbs)} plans.')
    return [round(a, 2) for a, b in spans]

def step_thumbnail(pr, settings, log=print):
    VB = _voxel(pr, settings)
    if VB: return VB.step_thumbnail(pr, settings, log)
    from .thumbnail import make_thumbnails
    lines, ep = merged_lines(pr); dur = duration_of(ep, lines)
    env = np.load(pr.p('env.npy')) if pr.exists('env.npy') else np.zeros(10)
    md = pr.read_json('metadata.json', {}) or {}
    make_thumbnails(pr, ep, lines, env, dur, md.get('thumbnail_text'), log)

def step_metadata(pr, settings, log=print):
    lines, ep = merged_lines(pr)
    project = dict(pr.meta)
    md = metadata(project, lines, ep, settings, log)
    pr.write_json('metadata.json', md)
    log('Titres, description et hashtags prêts.')
    return md

def run_all(pr, settings, aspects=('9:16',), log=print, progress=None):
    if pr.meta.get('voice_mode') == 'draft' and not (pr.exists('voice.mp3') and pr.exists('lines.json')): step_draft_voice(pr, settings, log)
    if pr.meta.get('voice_mode') == 'local' and not (pr.exists('voice.mp3') and pr.exists('lines.json')): step_local_voice(pr, settings, log)
    if not pr.exists('voice.mp3'): step_voice(pr, settings, log)
    if not pr.exists('lines.json'): step_align(pr, settings, log)
    if not pr.exists('episode.json'): step_direct(pr, settings, log)
    if not pr.exists('mix.wav'): step_mix(pr, settings, log)
    outs = [step_render(pr, settings, a, progress=progress, log=log) for a in aspects]
    step_metadata(pr, settings, log); step_thumbnail(pr, settings, log)
    remember_series(pr, log)
    return outs

def end_states(ep, lines, style='pixel3d'):
    """state of the characters at the end of an episode (acting layer only, nothing is rendered): {id: {hold, ...}}"""
    import numpy as np, copy
    raw = ep.get('cast') or {}; ep = copy.deepcopy(ep)
    eng = make_engine(style, ep, lines, np.zeros(10), duration_of(ep, lines), '16:9')
    ac = eng.ctx.get_acting() if hasattr(eng, 'ctx') else getattr(eng, 'acting', None)
    if ac is None or not ac.shots: return {}
    ends = ac.shots[max(ac.shots)].end_states()
    ref = lambda a: raw[a].get('ref', a) if isinstance(raw.get(a), dict) else (raw[a][1:] if isinstance(raw.get(a), str) and raw[a].startswith('@') else a)
    return {ref(a): {k: v for k, v in s.items() if k in ('hold', 'face', 'posture')} for a, s in ends.items()}

def remember_series(pr, log=print):
    """after an episode of a series: store what lasts (objects kept by the characters) for the next episodes"""
    from .acting.cast import remember
    if _voxel(pr, None): return None          # la mémoire de série lit l'état des acteurs PIXEL 3D : pas applicable au moteur voxel
    lines, ep = merged_lines(pr)
    if not ep.get('series') or ep.get('series_state') is not None: return None     # a replayed state is not written back
    ends = end_states(ep, lines, pr.meta.get('style', 'pixel3d'))
    if not ends: return None
    sr = remember(ep, ends, pr.slug, pr.meta.get('name'))
    if sr: log(f"Série {ep['series']} : état mémorisé pour l'épisode suivant.")
    return sr
