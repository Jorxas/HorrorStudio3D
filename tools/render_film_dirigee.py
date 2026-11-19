"""Film complet d'une scène dirigée dans UN style : tools/render_film_dirigee.py <dossier episode.json+lines.json> <voxel|ps1> <sortie.mp4> [--audio fichier] [--aspect 16:9] [--workers 8] [--seconds N] [--forcer]
Avant le rendu, le contrôle qualité (tools/verifier_scene.py, docs/QA_SCENE.md) vérifie la scène et REFUSE les erreurs bloquantes ; --forcer rend quand même.
voxel : contrat (logique PS1) -> peintre GPU -> habillage commun ; ps1 : lancer de rayons PIXEL 3D en parallèle -> habillage. Le son vient du fichier donné (le même pour tous les styles)."""
import sys, os, json, time, subprocess, tempfile, multiprocessing as mp
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
import numpy as np

FPS = 30


def load(d):
    d = Path(d); ep = json.loads((d / 'episode.json').read_text(encoding='utf-8')); lines = json.loads((d / 'lines.json').read_text(encoding='utf-8'))
    return ep, lines, float(ep.get('duration') or lines[-1]['end'] + 1.2)


_ENG = {}
def _engine(d, aspect):
    if 'e' not in _ENG:
        from hstudio.pipeline import make_engine
        ep, lines, dur = load(d); _ENG['e'] = make_engine('pixel3d', ep, lines, np.zeros(int(dur * 30) + 60), dur, aspect)
    return _ENG['e']


def _work(a):
    d, aspect, j = a
    return np.asarray(_engine(d, aspect).frame(j / FPS).convert('RGB'), np.uint8).tobytes()


def mux(video, audio, out, dur):
    cmd = ['ffmpeg', '-y', '-v', 'error', '-i', str(video)] + (['-i', str(audio)] if audio else []) + ['-c:v', 'copy'] + (['-c:a', 'aac', '-b:a', '256k', '-map', '0:v', '-map', '1:a'] if audio else []) + ['-t', f'{dur:.3f}', '-movflags', '+faststart', str(out)]
    subprocess.run(cmd, check=True)


def main():
    a = sys.argv[1:]; opt = lambda k, dflt=None: (a.pop(a.index(k) + 1), a.pop(a.index(k)))[0] if k in a else dflt
    force = '--forcer' in a
    if force: a.remove('--forcer')
    audio = opt('--audio'); aspect = opt('--aspect', '16:9'); workers = int(opt('--workers', 8)); secs = opt('--seconds')
    d, style, out = a[0], a[1], Path(a[2])
    # contrôle qualité de la scène AVANT tout rendu (hstudio/qa, docs/QA_SCENE.md) : il lit l'épisode, ne change rien, refuse les erreurs bloquantes sauf --forcer
    from hstudio import qa
    if not qa.gate(d, style='voxel' if style == 'voxel' else 'ps1', aspect=aspect, force=force): sys.exit(2)
    ep, lines, dur = load(d)
    if secs: dur = min(dur, float(secs))
    n = int(round(dur * FPS)); W, H = (1920, 1080) if aspect == '16:9' else (1080, 1920); t0 = time.time()
    tmp = Path(tempfile.mkdtemp(prefix='film_')); raw = tmp / 'raw.mp4'
    if style == 'voxel':
        from hstudio.voxelgpu import from_ps1, contract as C, render, overlay
        c = from_ps1.build(ep, lines, dur if not secs else float(ep.get('duration') or dur), aspect, FPS, lambda *_: None)
        cp = tmp / 'contract.json'; C.save(c, cp); print('contrat prêt', round(time.time() - t0), 's', flush=True)
        for transport in ('bin', 'b64'):        # le transport binaire échoue parfois (Failed to fetch) : le base64, plus lent, passe
            try:
                render.run_painter(cp, tmp / 'video_only.mp4', 'nvidia', (W, H), attest=tmp / 'att.json', crf=14, quiet=True, fallback=True, transport=transport); break
            except RuntimeError as e:
                if transport == 'b64' or 'Failed to fetch' not in str(e): raise
                print('transport binaire refusé : nouvel essai en base64', flush=True)
        print('peintre fini', round(time.time() - t0), 's', flush=True)
        overlay.apply(from_ps1.LAST_ENGINE, tmp / 'video_only.mp4', raw, FPS, (W, H), progress=lambda k: print('\rhabillage', k, end='', flush=True))
    else:
        if ep.get('words'): print(f"[mots 3D] {len(ep['words'])} mots dans l'épisode : ils ne sont peints que par VOXEL, ils manqueront en PS1", flush=True)
        enc = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-crf', '14', '-preset', 'medium', '-pix_fmt', 'yuv420p', str(raw)], stdin=subprocess.PIPE)
        with mp.Pool(workers) as pool:
            for j, buf in enumerate(pool.imap(_work, [(d, aspect, j) for j in range(n)], chunksize=2)):
                enc.stdin.write(buf)
                if j % 30 == 0: print(f'\rimage {j}/{n}  {round(time.time() - t0)} s', end='', flush=True)
        enc.stdin.close(); enc.wait()
    mux(raw, audio, out, dur); print('\nfini :', out, round(time.time() - t0), 's')


if __name__ == '__main__':
    main()
