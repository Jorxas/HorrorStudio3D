"""Étape RENDRE du kit : chaque version construite (film long 16:9, parties 9:16) -> rendus/<version>.video.mp4 (image
seule, 1920x1080 ou 1080x1920, 30 i/s, x264 CRF 16). Le son est posé à l'étape livrer.

PS1   : le lancer de rayons PIXEL 3D dans un pool de processus (au plus 6), une image = un appel sans état au moteur ;
        la bouche de qui a `talk` suit l'enveloppe de la voix (voix/voix.mp3, décalée du début de la version).
VOXEL : le peintre GPU par tools/render_film_dirigee.py (contrat logique PS1 -> peintre -> habillage commun) ;
        la bouche suit la voix par la clé `lipsync` que construire a posée. UN SEUL rendu GPU à la fois.

    python -m hstudio.histoire rendre <dossier> [--format 16:9|9:16|tous|<ids>] [--workers 6] [--secondes N] [--forcer]

Avant de dessiner, le contrôle de scène du moteur (hstudio/qa, docs/QA_SCENE.md) refuse les erreurs bloquantes ;
--forcer rend quand même (à éviter)."""
import multiprocessing as mp
import os
import subprocess
import sys
import time

import numpy as np

from .common import ENGINE, FPS, KitError, Story, read_json, write_json, version_hash
from . import projet as PJ

MAX_PS1_WORKERS = 6


# ------------------------------------------------------------------ the voice envelope (mouths of PS1 actors)
def voice_env_cache(st):
    """RMS of the voice per 1/30 s, 0..1 (97th percentile = 1), cached in voix/_env30.npy next to voix.mp3"""
    cache = os.path.join(st.voix, '_env30.npy')
    if os.path.exists(cache) and os.path.getmtime(cache) >= os.path.getmtime(st.voice): return cache
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', st.voice, '-ac', '1', '-ar', '16000', '-f', 's16le', '-'], capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.; hop = 16000 // FPS
    n = len(a) // hop; r = np.sqrt((a[:n * hop].reshape(n, hop) ** 2).mean(1)); r = np.clip(r / (np.percentile(r, 97) + 1e-6), 0, 1)
    np.save(cache, r.astype(np.float32))
    return cache


def env_for(cache, offset, dur):
    r = np.load(cache); j = int(round(offset * FPS))
    return np.concatenate([r[j:] if j >= 0 else np.concatenate([np.zeros(-j, np.float32), r]), np.zeros(int((dur + 10) * FPS), np.float32)])


# ------------------------------------------------------------------ PS1 workers (module level: Windows spawns)
_ENG = {}


def engine(vdir, aspect, env_cache, offset):
    key = (vdir, aspect, offset)
    if key not in _ENG:
        sys.path.insert(0, ENGINE)
        from hstudio.pipeline import make_engine
        ep = read_json(os.path.join(vdir, 'episode.json')); lines = read_json(os.path.join(vdir, 'lines.json')); dur = float(ep['duration'])
        env = env_for(env_cache, offset, dur) if env_cache else np.zeros(int((dur + 10) * FPS), np.float32)
        _ENG.clear(); _ENG[key] = make_engine('pixel3d', ep, lines, env, dur, aspect)
    return _ENG[key]


def _work_frame(a):
    vdir, aspect, env_cache, offset, j = a
    return np.asarray(engine(vdir, aspect, env_cache, offset).frame(j / FPS).convert('RGB'), np.uint8).tobytes()


def _work_still(a):
    vdir, aspect, env_cache, offset, t, w, h = a
    from PIL import Image
    im = engine(vdir, aspect, env_cache, offset).frame(t).convert('RGB')
    return t, np.asarray(im.resize((w, h), Image.BILINEAR), np.uint8)


def sample_times(vdir):
    """one instant per camera setup of every shot (shortly after the cut), from the engine's own timeline
    -> [(shot index, [l0, l1], time)]"""
    sys.path.insert(0, ENGINE)
    from hstudio.engines.pixel3d.frame import Timeline
    ep = read_json(os.path.join(vdir, 'episode.json')); lines = read_json(os.path.join(vdir, 'lines.json'))
    tl = Timeline(ep, lines, float(ep['duration'])); out = []
    for k, (sh, (a, b)) in enumerate(zip(ep['shots'], tl.spans)):
        keys = sh['camera']['keys']; starts = [0.] + [kk['t'] for kk in keys[1:] if kk.get('cut') and kk['t'] < b - a]
        for i, s0 in enumerate(starts):
            nxt = starts[i + 1] if i + 1 < len(starts) else b - a
            out.append((k, sh['lines'], round(a + s0 + min(.6, max(.05, (nxt - s0) * .45)), 3)))
    return out


def ps1_stills(st, v, times, size, workers=MAX_PS1_WORKERS):
    vdir = st.version_dir(v['id']); cache = voice_env_cache(st)
    args = [(vdir, v['aspect'], cache, v['t0'], t, size[0], size[1]) for t in times]
    with mp.Pool(max(1, min(workers, MAX_PS1_WORKERS, len(args)))) as pool:
        return dict(pool.map(_work_still, args, chunksize=1))


def voxel_stills(st, v, times, size, habille=False):
    """the GPU painter's stills at `times` (episode time) -> {t: array}; one GPU call.
    `habille` (9/11/2026, `apercu --habille`): each still also gets the final overlay (title, subtitles, ui.messages, choice...) drawn by
    the same `compose` as the render (otherwise a VOXEL preview shows the 3D image only)."""
    import tempfile
    from pathlib import Path
    from PIL import Image
    sys.path.insert(0, ENGINE)
    from hstudio.voxelgpu import from_ps1, contract as CT, render as R
    vdir = st.version_dir(v['id'])
    ep = read_json(os.path.join(vdir, 'episode.json')); lines = read_json(os.path.join(vdir, 'lines.json'))
    c = from_ps1.build(ep, lines, float(ep['duration']), v['aspect'], 24, lambda *_: None)
    tmp = Path(tempfile.mkdtemp(prefix='kit_vox_')); cp = tmp / 'contract.json'; CT.save(c, cp)
    w, h = R.SIZES[v['aspect']]
    R.run_painter(cp, None, 'nvidia', (w // 2, h // 2), stills=list(times), stills_dir=tmp, quiet=True, fallback=True)
    out = {}
    eng = from_ps1.LAST_ENGINE if habille else None
    for t in times:
        p = tmp / f't_{t:.2f}.png'
        if not p.exists(): out[t] = np.full((size[1], size[0], 3), (255, 0, 255), np.uint8); continue
        im = Image.open(p).convert('RGB')
        if eng is not None:
            from hstudio.engines.pixel3d import frame as FR
            k, t0, t1 = eng.ctx.tl.at(t); shot, T, span = FR.apply_cut(eng.ctx.ep['shots'][k], t - t0, t1 - t0)
            im = eng.compose(np.asarray(im), t, shot, T, FR.clamp(T / max(1e-3, span)))
        out[t] = np.asarray(im.resize(size, Image.BILINEAR), np.uint8)
    return out


# ------------------------------------------------------------------ full renders
def render_ps1(st, v, out, workers=MAX_PS1_WORKERS, seconds=None, log=print):
    vdir = st.version_dir(v['id']); dur = float(read_json(os.path.join(vdir, 'episode.json'))['duration'])
    if seconds: dur = min(dur, float(seconds))
    n = int(round(dur * FPS)); W, H = (1920, 1080) if v['aspect'] == '16:9' else (1080, 1920); t0 = time.time()
    cache = voice_env_cache(st); tmp = out + '.part.mp4'
    enc = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                            '-c:v', 'libx264', '-crf', '16', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', tmp], stdin=subprocess.PIPE)
    ok = False
    try:
        with mp.Pool(max(1, min(workers, MAX_PS1_WORKERS))) as pool:
            for j, buf in enumerate(pool.imap(_work_frame, [(vdir, v['aspect'], cache, v['t0'], j) for j in range(n)], chunksize=4)):
                enc.stdin.write(buf)
                if j % 300 == 0: log(f"  {v['id']} : image {j}/{n}  {round(time.time() - t0)} s")
        ok = True
    finally:
        try: enc.stdin.close()
        except OSError: pass
        if ok: enc.wait()
        else: enc.kill(); enc.wait()                 # never leave an orphan ffmpeg that would finish a truncated clip
    if enc.returncode != 0: raise KitError(f'encodage échoué ({v["id"]})')
    os.replace(tmp, out)
    log(f"  {v['id']} : {n} images en {round(time.time() - t0)} s -> {out}")


def render_voxel(st, v, out, seconds=None, force=False, log=print):
    vdir = st.version_dir(v['id']); t0 = time.time()
    cmd = [sys.executable, os.path.join(ENGINE, 'tools', 'render_film_dirigee.py'), vdir, 'voxel', out + '.part.mp4', '--aspect', v['aspect']]
    if seconds: cmd += ['--seconds', str(seconds)]
    if force: cmd += ['--forcer']                     # the tool runs the scene QA gate itself and refuses blocking errors
    r = subprocess.run(cmd, cwd=ENGINE, env=dict(os.environ, PYTHONIOENCODING='utf-8'))
    if r.returncode != 0: raise KitError(f'rendu VOXEL échoué ({v["id"]})')
    os.replace(out + '.part.mp4', out)
    log(f"  {v['id']} : VOXEL en {round(time.time() - t0)} s -> {out}")


def check_video(path, want_dur, aspect):
    """full decode + size + duration; a doubtful file is renamed, never deleted"""
    sys.path.insert(0, ENGINE)
    from .common import decode_ok, probe
    ok, err = decode_ok(path); info = probe(path)
    want = '1920x1080' if aspect == '16:9' else '1080x1920'
    bad = []
    if not ok: bad.append(f'décodage : {err}')
    if info.get('image') != want: bad.append(f"image {info.get('image')} au lieu de {want}")
    if abs(info['duree'] - want_dur) > .1: bad.append(f"durée {info['duree']:.2f} s au lieu de {want_dur:.2f} s")
    if bad:
        stamp = time.strftime('%Y%m%d-%H%M%S'); q = path.replace('.mp4', f'.ECARTE-{stamp}.mp4'); os.replace(path, q)
        raise KitError(f'rendu douteux, mis de côté sous {q} : ' + ' ; '.join(bad))
    return info


def qa_gate(st, v, style, force, log=print):
    """the engine's scene QA (hstudio/qa, docs/QA_SCENE.md) before drawing anything: blocking errors refuse the render"""
    try:
        from hstudio import qa
    except ImportError:
        log('  (contrôle de scène absent : rendu sans contrôle)'); return True
    quiet = lambda m: log('  ' + m) if not str(m).startswith('[art]') else None
    return qa.gate(st.version_dir(v['id']), style=style, aspect=v['aspect'], force=force, log=quiet)


def render(folder, which=None, workers=MAX_PS1_WORKERS, seconds=None, force=False, log=print):
    st = Story(folder)
    dec, mod = PJ.build(folder, log, quiet=True)
    os.makedirs(st.rendus, exist_ok=True)
    vs = PJ.versions(st, which)
    if dec['style'] != 'voxel':
        refused = [v['id'] for v in vs if not qa_gate(st, v, 'ps1', force, log)]
        if refused: raise KitError(f"rendu refusé par le contrôle de scène ({', '.join(refused)}) : corrige histoire.py (voir les rapports _qa), ou --forcer")
    for v in vs:
        out = st.video_only(v['id'])
        log(f"rendu {dec['style'].upper()} de {v['id']} ({v['aspect']}, {v['dur']:.1f} s)…")
        if dec['style'] == 'voxel': render_voxel(st, v, out, seconds, force, log)
        else: render_ps1(st, v, out, workers, seconds, log)
        info = check_video(out, min(v['dur'], float(seconds)) if seconds else v['dur'], v['aspect'])
        write_json(out.replace('.mp4', '.json'), dict(version=v['id'], episode_sha1=version_hash(st.version_dir(v['id'])), style=dec['style'],
                                                      secondes=seconds, duree=info['duree'], date=time.strftime('%Y-%m-%d %H:%M:%S')))
        log(f"  vérifié : décodage complet, {info['image']}, {info['duree']:.2f} s, {info['taille_mo']} Mo")
    log('Étape suivante : mixer (si ce n\'est pas fait), puis livrer')
