"""Shared helpers of the story kit: the folder layout, JSON in UTF-8, ffmpeg measurements, and the lookup of another
Python interpreter when the studio's venv lacks a package (reportlab for the PDF, elevenlabs + dotenv for the key)."""
import json
import os
import re
import shutil
import subprocess
import sys

ENGINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = sys.executable
FPS = 30
VERSION_RE = re.compile(r'^(long_16x9|complet_9x16|partie\d+_9x16)$')


class KitError(RuntimeError):
    """an error the kit explains in French (no traceback for the user)"""


class Story:
    """the folder of one story and every path the kit reads or writes"""

    def __init__(self, folder):
        self.dir = os.path.abspath(folder)
        p = lambda *a: os.path.join(self.dir, *a)
        self.script = p('script.txt'); self.histoire = p('histoire.py'); self.readme = p('LISEZMOI.txt')
        self.voix_json = p('voix.json')
        self.voix = p('voix'); self.voice = p('voix', 'voix.mp3'); self.alignment = p('voix', 'alignement.json'); self.lignes = p('voix', 'lignes.json')
        self.phrases_md = p('PHRASES.md')
        self.construit = p('construit'); self.decoupe = p('construit', 'decoupe.json'); self.cues = p('construit', 'bruitages.json')
        self.planches = p('planches'); self.rendus = p('rendus'); self.mix = p('mix'); self.livraison = p('LIVRAISON')

    def version_dir(self, vid): return os.path.join(self.construit, vid)
    def video_only(self, vid): return os.path.join(self.rendus, f'{vid}.video.mp4')
    def mix_wav(self, vid): return os.path.join(self.mix, f'mix_{vid}.wav')

    def need(self, path, hint):
        if not os.path.exists(path): raise KitError(f'Fichier manquant : {path}\n→ {hint}')
        return path


def read_json(path):
    with open(path, encoding='utf-8') as f: return json.load(f)


def write_json(path, data, indent=1):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=indent)
    os.replace(tmp, path)


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f: f.write(text)


def version_hash(vdir):
    """sha1 of what a painter reads for one version (episode.json + lines.json): tells whether a render is still current"""
    import hashlib
    h = hashlib.sha1()
    for f in ('episode.json', 'lines.json'):
        with open(os.path.join(vdir, f), 'rb') as fh: h.update(fh.read())
    return h.hexdigest()


def slug(title):
    import unicodedata
    s = unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode('ascii').upper()
    return re.sub(r'[^A-Z0-9]+', '_', s).strip('_') or 'HISTOIRE'


# ------------------------------------------------------------------ another Python
def other_python(modules, env_var):
    """an interpreter that imports `modules`: this one, then $env_var, then `python` / `py -3` on the PATH; None if none"""
    code = 'import ' + ', '.join(modules)
    cands = [[PY]]
    if os.environ.get(env_var): cands.insert(0, [os.environ[env_var]])
    for exe in ('python', 'python3'):
        w = shutil.which(exe)
        if w and 'WindowsApps' not in w: cands.append([w])
    w = shutil.which('py')
    if w: cands.append([w, '-3'])
    w = shutil.which('python')
    if w: cands.append([w])                         # the Store shim last: it may still be a real interpreter
    seen = set()
    for c in cands:
        k = tuple(c)
        if k in seen: continue
        seen.add(k)
        try:
            r = subprocess.run(c + ['-c', code], capture_output=True, timeout=60)
            if r.returncode == 0: return c
        except (OSError, subprocess.TimeoutExpired):
            continue
    return None


# ------------------------------------------------------------------ ffmpeg measurements
def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', **kw)


def probe(path):
    j = json.loads(run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', path]).stdout or '{}')
    if not j.get('streams'): raise KitError(f'fichier illisible par ffprobe : {path}')
    v = next((s for s in j['streams'] if s['codec_type'] == 'video'), None); a = next((s for s in j['streams'] if s['codec_type'] == 'audio'), None)
    out = dict(duree=round(float(j['format']['duration']), 3), taille_mo=round(os.path.getsize(path) / 1048576, 2),
               debit_kbps=round(int(j['format'].get('bit_rate', 0) or 0) / 1000), audio=(a or {}).get('codec_name'))
    if v: out.update(image=f"{v['width']}x{v['height']}", ips=v.get('r_frame_rate'), video=v['codec_name'])
    return out


def decode_ok(path):
    """full decode: (True, '') when ffmpeg reads every frame and sample without a single error"""
    e = run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'null', '-']).stderr.strip()
    return e == '', e[:400]


def loudness(path):
    """(integrated LUFS, true peak dBTP, LRA LU) by ffmpeg's ebur128"""
    e = run(['ffmpeg', '-hide_banner', '-nostats', '-i', path, '-vn', '-af', 'ebur128=peak=true', '-f', 'null', '-']).stderr
    t = e[e.rfind('Summary:'):]
    m_i = re.search(r'I:\s+(-?[\d.]+) LUFS', t); m_p = re.search(r'Peak:\s+(-?[\d.]+|-inf) dBFS', t); m_l = re.search(r'LRA:\s+(-?[\d.]+) LU', t)
    if not m_i: raise KitError(f'mesure de sonie impossible : {path}')
    pk = m_p.group(1) if m_p else '-inf'
    return float(m_i.group(1)), (-99. if pk == '-inf' else float(pk)), (float(m_l.group(1)) if m_l else 0.)


def duration(path):
    r = run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path])
    try: return float(r.stdout.strip())
    except ValueError: raise KitError(f'durée illisible : {path}')
