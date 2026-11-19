"""Local audio input: the owner's own recordings used as narration or as a character voice, with no TTS call.

Two flows, both entirely offline (only ffmpeg and ffprobe):

- **one whole track** -- `check` + `to_mp3` validate one local file and write `projects/<slug>/voice.mp3`.
  The alignment step then times the script on it (ElevenLabs forced alignment, Whisper, or silences: offline by
  default). This is what the CLI `new --voice` and the web import already did, now validated.
- **one clip per script line** -- a *voice sheet* (`voice_clips.json`) says which local file says which line, and
  for whom. `assemble` concatenates the validated clips and measures the timing of every line on the samples
  themselves, so no alignment step is needed and the lip-sync cannot drift.

Security rules kept here, in one place:

- nothing is ever handed to a shell: every ffmpeg/ffprobe call uses list arguments;
- a name that comes from a web request goes through `safe_name` (one plain file name, no separators);
- a path that comes from a voice sheet goes through `under` (relative, inside the project's `audio/` folder only),
  so neither a request nor a sheet can read an arbitrary file on the machine. The CLI, which is the owner's own
  shell, is the only place where an absolute path is accepted -- and it is copied in before being used.

Levels are left exactly as recorded: the final loudness is the mixer's job (-14 LUFS), and changing a take's
balance is an artistic decision, not this module's.
"""
import json, os, re, subprocess, tempfile, wave
import numpy as np

SR = 44100
EXTS = ('.mp3', '.wav', '.m4a', '.aac', '.ogg', '.oga', '.opus', '.flac', '.aif', '.aiff', '.wma', '.mp4', '.mov', '.webm', '.mkv')
MAX_BYTES = 512 * 1024 * 1024          # a take, not a film: 512 Mo is already far more than any narration
MAX_SECONDS = 2 * 3600.
MIN_SECONDS = .05                      # shorter than that is a click, not a line
JOIN_FADE = .005                       # 5 ms at both ends of a clip: removes the click at the joins
SHEET = 'voice_clips.json'
AUDIO_DIR = 'audio'


class AudioInputError(RuntimeError):
    """invalid local audio (message in French: it is shown to the owner as is)"""


# ------------------------------------------------------------------ names and paths
def safe_name(name):
    """one plain file name, as accepted from a web request: no folder, no '..', no shell character.
    Raises instead of silently rewriting, so a refused upload is visible."""
    n = (name or '').strip()
    if not n or n in ('.', '..'): raise AudioInputError('Nom de fichier vide.')
    if os.path.basename(n) != n or '/' in n or '\\' in n or ':' in n:
        raise AudioInputError(f'Nom de fichier refusé (pas de dossier dans un nom) : {name!r}')
    if not re.fullmatch(r'[A-Za-z0-9À-ɏ ._()-]{1,120}', n):
        raise AudioInputError(f'Nom de fichier refusé (lettres, chiffres, espace, . _ - ( ) seulement) : {name!r}')
    if os.path.splitext(n)[1].lower() not in EXTS:
        raise AudioInputError(f'Extension non gérée : {os.path.splitext(n)[1] or "(aucune)"}. Formats acceptés : {", ".join(EXTS)}')
    return n


def under(root, rel):
    """a relative path resolved inside `root` only (symlinks included). For the paths written in a voice sheet."""
    if not rel or not str(rel).strip(): raise AudioInputError('Chemin de clip vide.')
    rel = str(rel).strip().replace('\\', '/')
    # rooted ("/x") and drive-letter ("C:/x") forms are refused explicitly: since Python 3.13 ntpath.isabs no
    # longer calls "/x" absolute, and the containment check below must not be the only thing standing in the way.
    if rel.startswith('/') or os.path.isabs(rel) or re.match(r'^[A-Za-z]:', rel):
        raise AudioInputError(f'Chemin absolu refusé dans la feuille de voix : {rel!r} (mets le fichier dans le dossier audio du projet).')
    p = os.path.realpath(os.path.join(root, rel)); r = os.path.realpath(root)
    if p != r and not p.startswith(r + os.sep):
        raise AudioInputError(f'Chemin hors du dossier audio du projet : {rel!r}')
    return p


def audio_dir(project_dir, create=False):
    d = os.path.join(project_dir, AUDIO_DIR)
    if create: os.makedirs(d, exist_ok=True)
    return d


def clips_of(project_dir):
    """the clips available in the project's audio folder, sorted by name (the order a sheet is built from)"""
    d = audio_dir(project_dir)
    if not os.path.isdir(d): return []
    return sorted(f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f)) and os.path.splitext(f)[1].lower() in EXTS)


# ------------------------------------------------------------------ ffmpeg / ffprobe (list arguments, never a shell)
def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    except FileNotFoundError:
        raise AudioInputError(f'{cmd[0]} est introuvable : installe ffmpeg (il fournit ffmpeg et ffprobe).')


_TIME = re.compile(r'time=(\d+):(\d\d):(\d\d(?:\.\d+)?)')


def _decoded_duration(path):
    """exact duration by decoding, for a file whose header does not say it (some phone recordings, cut MP3s)"""
    r = _run(['ffmpeg', '-v', 'error', '-stats', '-i', path, '-vn', '-f', 'null', '-'])
    last = None
    for m in _TIME.finditer(r.stderr or ''): last = m
    if r.returncode or last is None: return None
    return int(last.group(1)) * 3600 + int(last.group(2)) * 60 + float(last.group(3))


def probe(path):
    """-> {duration, codec, channels, sample_rate, container}. Raises if the file holds no audio stream."""
    r = _run(['ffprobe', '-v', 'error', '-print_format', 'json', '-show_format', '-show_streams', '-select_streams', 'a:0', path])
    if r.returncode:
        raise AudioInputError(f'Fichier audio illisible : {os.path.basename(path)} ({(r.stderr or "").strip().splitlines()[-1] if r.stderr else "ffprobe a échoué"})')
    try: j = json.loads(r.stdout or '{}')
    except json.JSONDecodeError: raise AudioInputError(f'Fichier audio illisible : {os.path.basename(path)}')
    streams = j.get('streams') or []
    if not streams:
        raise AudioInputError(f'Aucune piste audio dans {os.path.basename(path)} (une image ou une vidéo muette ne peut pas servir de voix).')
    st = streams[0]; fmt = j.get('format') or {}
    dur = None
    for v in (st.get('duration'), fmt.get('duration')):
        try:
            if v is not None and float(v) > 0: dur = float(v); break
        except (TypeError, ValueError): pass
    if dur is None: dur = _decoded_duration(path)
    return {'duration': dur, 'codec': st.get('codec_name', '?'), 'channels': int(st.get('channels') or 0),
            'sample_rate': int(st.get('sample_rate') or 0), 'container': (fmt.get('format_name') or '?').split(',')[0]}


def check(path, min_seconds=MIN_SECONDS, max_seconds=MAX_SECONDS, max_bytes=MAX_BYTES):
    """every reason to refuse a local audio file, in one place -> the probe result, enriched with size and name.
    The messages are the ones the owner reads, so they say what to do."""
    if not path or not str(path).strip(): raise AudioInputError('Aucun fichier audio indiqué.')
    path = os.path.abspath(str(path))
    if os.path.isdir(path): raise AudioInputError(f'{path} est un dossier, pas un fichier audio.')
    if not os.path.isfile(path): raise AudioInputError(f'Fichier introuvable : {path}')
    if not os.access(path, os.R_OK): raise AudioInputError(f'Fichier non lisible (droits) : {path}')
    size = os.path.getsize(path)
    if size == 0: raise AudioInputError(f'Fichier vide : {os.path.basename(path)}')
    if size > max_bytes: raise AudioInputError(f'Fichier trop gros : {size / 1e6:.0f} Mo (maximum {max_bytes / 1e6:.0f} Mo).')
    ext = os.path.splitext(path)[1].lower()
    if ext not in EXTS: raise AudioInputError(f'Extension non gérée : {ext or "(aucune)"}. Formats acceptés : {", ".join(EXTS)}')
    info = probe(path)
    d = info['duration']
    if d is None: raise AudioInputError(f'Durée illisible : {os.path.basename(path)} (fichier incomplet ou corrompu ?)')
    if d < min_seconds: raise AudioInputError(f'Enregistrement trop court : {d:.3f} s (minimum {min_seconds:.2f} s).')
    if d > max_seconds: raise AudioInputError(f'Enregistrement trop long : {d / 60:.1f} min (maximum {max_seconds / 60:.0f} min).')
    info['path'] = path; info['name'] = os.path.basename(path); info['bytes'] = size
    return info


def to_mp3(src, dst, bitrate='256k'):
    """validated local file -> dst, in the studio's voice format (MP3 256k). Written aside then moved into place,
    so a failed conversion never leaves a half-written voice.mp3 (and src may be dst)."""
    os.makedirs(os.path.dirname(os.path.abspath(dst)) or '.', exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix='.mp3', dir=os.path.dirname(os.path.abspath(dst))); os.close(fd)
    try:
        r = _run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-vn', '-c:a', 'libmp3lame', '-b:a', bitrate, '-ar', str(SR), tmp])
        if r.returncode or not os.path.getsize(tmp):
            raise AudioInputError(f'Conversion impossible : {os.path.basename(src)} ({(r.stderr or "").strip()[-300:] or "ffmpeg a échoué"})')
        os.replace(tmp, dst)
    finally:
        if os.path.exists(tmp): os.remove(tmp)
    return dst


def mono(path, workdir, sr=SR):
    """-> float32 samples, mono, sr Hz. The clip is decoded once and measured on its samples (exact timing)."""
    os.makedirs(workdir, exist_ok=True)
    wav = os.path.join(workdir, '_clip_in.wav')
    r = _run(['ffmpeg', '-v', 'error', '-y', '-i', path, '-vn', '-ac', '1', '-ar', str(sr), '-c:a', 'pcm_s16le', wav])
    if r.returncode: raise AudioInputError(f'Décodage impossible : {os.path.basename(path)} ({(r.stderr or "").strip()[-300:]})')
    with wave.open(wav) as w: a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    os.remove(wav)
    if not len(a): raise AudioInputError(f'Clip silencieux ou vide après décodage : {os.path.basename(path)}')
    k = min(int(JOIN_FADE * sr), len(a) // 2)
    if k > 0:
        a = a.copy(); a[:k] *= np.linspace(0, 1, k, dtype=np.float32); a[-k:] *= np.linspace(1, 0, k, dtype=np.float32)
    return a


def write_mp3(sig, path, workdir, bitrate='256k', sr=SR):
    os.makedirs(workdir, exist_ok=True)
    wav = os.path.join(workdir, '_local_voice.wav')
    with wave.open(wav, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(sig, -1, 1) * 32767).astype(np.int16).tobytes())
    r = _run(['ffmpeg', '-v', 'error', '-y', '-i', wav, '-c:a', 'libmp3lame', '-b:a', bitrate, '-ar', str(sr), path])
    os.remove(wav)
    if r.returncode: raise AudioInputError(f'Écriture de la voix impossible ({(r.stderr or "").strip()[-300:]}).')
    return path


# ------------------------------------------------------------------ the voice sheet
def default_sheet(lines, names=None):
    """a sheet ready to fill in: the clips found in the audio folder, in name order, one per script line.
    `names` is that list; a line keeps its own speaker if the script already gives one ("LÉA : ...")."""
    names = list(names or [])
    return {'gap': .3, 'lead_in': .4,
            'clips': [{'line': i, 'text': (l.get('text') or '')[:60], 'speaker': l.get('speaker') or '',
                       'file': names[i] if i < len(names) else ''} for i, l in enumerate(lines)]}


def read_sheet(project_dir):
    p = os.path.join(project_dir, SHEET)
    if not os.path.exists(p):
        raise AudioInputError(f'Pas de feuille de voix : écris {SHEET} dans le projet (python -m hstudio audio sheet <projet>).')
    try: return json.load(open(p, encoding='utf-8'))
    except json.JSONDecodeError as e: raise AudioInputError(f'{SHEET} : JSON invalide ({e}).')


def write_sheet(project_dir, sheet):
    p = os.path.join(project_dir, SHEET)
    json.dump(sheet, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return p


def plan(project_dir, lines, sheet=None):
    """validates a whole sheet against the script *before* anything is written: every line covered exactly once,
    every file inside the project's audio folder, every clip real audio of a sane duration.
    -> list of {line, path, name, duration, speaker, gap_after}, in script order."""
    sheet = sheet if sheet is not None else read_sheet(project_dir)
    if not isinstance(sheet, dict) or not isinstance(sheet.get('clips'), list):
        raise AudioInputError(f'{SHEET} doit être un objet avec une liste "clips".')
    root = audio_dir(project_dir)
    gap = _num(sheet.get('gap', .3), 'gap', 0., 30.)
    seen = {}
    for k, c in enumerate(sheet['clips']):
        if not isinstance(c, dict): raise AudioInputError(f'{SHEET} : clip {k + 1} doit être un objet.')
        if 'line' not in c: raise AudioInputError(f'{SHEET} : clip {k + 1} sans "line" (numéro de la phrase, 0 pour la première).')
        try: i = int(c['line'])
        except (TypeError, ValueError): raise AudioInputError(f'{SHEET} : clip {k + 1}, "line" doit être un entier.')
        if not 0 <= i < len(lines):
            raise AudioInputError(f'{SHEET} : clip {k + 1} parle de la phrase {i}, le script en a {len(lines)} (0 à {len(lines) - 1}).')
        if i in seen: raise AudioInputError(f'{SHEET} : la phrase {i} a deux clips ({seen[i]} et {c.get("file")!r}).')
        if not str(c.get('file') or '').strip():
            raise AudioInputError(f'{SHEET} : la phrase {i} n\'a pas de fichier audio.')
        seen[i] = c['file']
    missing = [i for i in range(len(lines)) if i not in seen]
    if missing:
        raise AudioInputError(f'{SHEET} : {len(missing)} phrase(s) sans enregistrement : ' +
                              ', '.join(str(i) for i in missing[:12]) + ('...' if len(missing) > 12 else '') +
                              '. Chaque phrase du script a besoin de son clip (ou retire-la du script).')
    by_line = {int(c['line']): c for c in sheet['clips']}
    out = []
    for i, ln in enumerate(lines):
        c = by_line[i]; path = under(root, c['file'])
        info = check(path)
        out.append({'line': i, 'path': path, 'name': os.path.relpath(path, root).replace('\\', '/'),
                    'duration': info['duration'], 'codec': info['codec'], 'sample_rate': info['sample_rate'],
                    'speaker': str(c.get('speaker') or '').strip(),
                    'gap_after': _num(c.get('gap_after', gap * (2 if ln.get('pause_after') else 1)), f'clip {i} gap_after', 0., 60.)})
    return out


def _num(v, what, lo, hi):
    try: x = float(v)
    except (TypeError, ValueError): raise AudioInputError(f'{SHEET} : "{what}" doit être un nombre.')
    if not lo <= x <= hi: raise AudioInputError(f'{SHEET} : "{what}" = {x} hors limites ({lo} à {hi}).')
    return x


# ------------------------------------------------------------------ assembly
def assemble(items, lines, out_mp3, workdir, lead_in=.4, sr=SR, log=print):
    """the planned clips, one after the other -> out_mp3 and the exact timing of every line.

    Timings come from the decoded sample counts, not from the headers: what the renderer shows and what the mix
    plays are the same thing to the sample. -> (lines with start/end/segs/speaker, total duration)"""
    lead = max(0., float(lead_in))
    parts = []; t = lead
    for it in items:
        a = mono(it['path'], workdir, sr)
        parts.append((it, t, a)); t += len(a) / sr + it['gap_after']
    total = t + .2
    sig = np.zeros(int(total * sr) + 1, np.float32)
    out = []
    for it, t0, a in parts:
        i0 = int(round(t0 * sr)); sig[i0:i0 + len(a)] += a
        ln = dict(lines[it['line']])
        ln['start'] = round(i0 / sr, 4); ln['end'] = round((i0 + len(a)) / sr, 4)
        ln['segs'] = [[ln['start'], ln['end']]]
        ln.pop('word_times', None)                      # one clip per line: no word timing to pretend to have
        if it['speaker'] and not ln.get('speaker'): ln['speaker'] = it['speaker']
        if ln.get('speaker'): ln['dialogue'] = True
        ln['voice_clip'] = it['name']                   # which take says this line (shown in the log, useful to re-record)
        out.append(ln)
    peak = float(np.abs(sig).max()) if len(sig) else 0.
    if peak > 1.0:                                      # overlapping clips cannot happen here, but a hot take can clip
        log(f'Attention : crête à {peak:.2f} (écrêtage possible). Baisse le niveau de tes enregistrements, le studio ne touche pas à tes prises.')
    write_mp3(sig, out_mp3, workdir, sr=sr)
    return out, round(len(sig) / sr, 4)
