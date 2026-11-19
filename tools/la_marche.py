"""« La marche » on the Horror Studio V3 engine (pixel3d), rendered locally.

    python tools/la_marche.py still 3 20.5 out.png     # one frame of world 3 at absolute time 20.5 s
    python tools/la_marche.py frame 150 out.png        # one composited frame of the film
    python tools/la_marche.py render --workers 18      # the whole film -> projects/la_marche_20261028/
    python tools/la_marche.py verify FILE

What is the engine's and what is added here, in full:
  * the ten worlds are ordinary `engine_version 2` episodes (tools/la_marche_worlds.py), the characters, gait, faces,
    sets, lights, weather, body and image-finish options are the engine's own;
  * the camera table of the brief (angle / distance / heights / field, smoothstep between marks, roll of +-0.7 deg
    with a 16 s period) is a pure function evaluated here and handed to the engine's own renderer in place of
    `acted.camera_acted` (the engine's free camera interpolates two keys only; it cannot follow a walker);
  * footprints: one shoe print at every heel strike of Noe (the engine's own `step` events), added to the frame's boxes;
  * the dissolves, the fade from black and the white flash are done on the engine's raster, frame by frame.
No engine file is modified. Nothing here calls the network.
"""
import argparse, json, math, os, sys, time, subprocess, hashlib
from pathlib import Path

os.environ.setdefault('OMP_NUM_THREADS', '1'); os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'tools'))
import numpy as np
from PIL import Image
import la_marche_worlds as WD

OUT_DIR = ROOT / 'projects' / 'la_marche_20261028'
W_OUT, H_OUT = 720, 1280

# ------------------------------------------------------------------ engine hooks (module level, per process)
FOOT = {'color': None, 'alpha': 1., 't0': 0.}


def install_hooks():
    from hstudio.engines.pixel3d import acted, r3d
    if getattr(acted, '_marche_hooked', False): return
    orig_build = acted.build_acted

    def camera_acted(ctx, sa, shot, st, samp, looks, T, u, g, k):
        s = samp['noe']; pos, tgt, roll, fov = WD.camera_for(s['x'], s['z'], T)
        yaw, pitch = acted.look_angles(pos, tgt)
        return (tuple(float(v) for v in pos), yaw, pitch, roll, float(fov)), None

    def build(ctx, sa, shot, st, state, g, T, u, k):
        res = orig_build(ctx, sa, shot, st, state, g, T, u, k)
        if FOOT['color'] is not None:
            sc = res[0]; tr = sa.tracks['noe']
            steps = sorted(e[0] for e in tr.events if e[1] == 'step')
            col = FOOT['color']
            for i, ts in enumerate(steps):
                if ts > T or ts < FOOT['t0'] - 1e-6: continue
                x, z = sa.position(tr, ts); side = .13 if i % 2 == 0 else -.13
                x += side
                for (dx0, dx1, z0, z1) in ((-.045, .045, -.15, -.07), (-.055, .055, -.05, .14)):
                    sc.boxes.append(r3d.Box((x + dx0, .003, z + z0), (x + dx1, .013, z + z1), col, cast=False, grain=.02))
        return res
    acted.camera_acted = camera_acted; acted.build_acted = build; acted._marche_hooked = True


class World:
    def __init__(self, k):
        from hstudio.pipeline import make_engine
        install_hooks()
        ep, lines, w = WD.episode(k)
        self.k = k; self.foot = w.get('foot')
        self.eng = make_engine('pixel3d', ep, lines, np.zeros(10), WD.DUR, '9:16')

    def lowres(self, t):
        if self.foot:
            c, a = self.foot; FOOT['color'] = c; FOOT['alpha'] = a; FOOT['t0'] = WD.T0[self.k]
        else: FOOT['color'] = None
        return self.eng.render_lowres(t)[0]


_cache = {}
def world(k):
    if k not in _cache:
        for old in [o for o in _cache if o != k and len(_cache) >= 2]: _cache.pop(old)
        _cache[k] = World(k)
    return _cache[k]


def compose_lowres(t):
    """the raster of the film at absolute time t (uint8 HxWx3), before the final scaling"""
    k = max(i for i, a in enumerate(WD.T0) if a <= t + 1e-9)
    img = world(k).lowres(t).astype(np.float32)
    if k > 0 and t < WD.T0[k] + WD.XF:
        w = WD.smooth((t - WD.T0[k]) / WD.XF)
        old = world(k - 1).lowres(t).astype(np.float32)
        img = old * (1 - w) + img * w
    if t < .8: img *= WD.smooth(t / .8)
    if t >= 59.0:
        f = WD.smooth((t - 59.0) / 2.0); img = img * (1 + 1.5 * f); img = img + (255 - img) * f ** 1.5
    return np.clip(img, 0, 255).astype(np.uint8)


def to_output(lo):
    return Image.fromarray(lo).resize((W_OUT, H_OUT), Image.LANCZOS)


def frame_bytes(i):
    return to_output(compose_lowres(i / WD.FPS)).tobytes()


def _init():
    install_hooks()


def render(args):
    import multiprocessing as mp
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    N = int(round(WD.DUR * WD.FPS)) if args.frames is None else args.frames
    audio = OUT_DIR / 'la_marche_musique.wav'
    if not audio.exists(): raise SystemExit('Musique absente : python tools/la_marche_music.py')
    final = OUT_DIR / f'la_marche_{W_OUT}x{H_OUT}_{WD.FPS}fps.mp4'
    if final.exists(): raise SystemExit(f'{final} existe déjà : rien n\'est écrasé.')
    part = OUT_DIR / (final.stem + '.part.mp4')
    cmd = ['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W_OUT}x{H_OUT}', '-r', str(WD.FPS), '-i', '-', '-i', str(audio),
           '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-profile:v', 'high', '-r', str(WD.FPS), '-c:a', 'aac', '-b:a', '256k',
           '-shortest', '-movflags', '+faststart', str(part)]
    errlog = open(OUT_DIR / 'ffmpeg_render.log', 'wb')
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=errlog)
    t0 = time.time(); sent = 0; failure = None
    try:
        ctx = mp.get_context('spawn')
        with ctx.Pool(args.workers, initializer=_init) as pool:
            for k, b in enumerate(pool.imap(frame_bytes, range(N), chunksize=args.chunk)):
                enc.stdin.write(b); sent = k + 1
                if k % 24 == 0:
                    el = time.time() - t0
                    print(f'{k}/{N} images  {k / max(el, 1e-3):.2f} img/s  écoulé {el:.0f} s', flush=True)
    except BaseException as e:
        failure = e
    finally:
        try: enc.stdin.close()
        except OSError: pass
        if failure is not None and enc.poll() is None: enc.terminate()
        try: enc.wait(timeout=180)
        except subprocess.TimeoutExpired: enc.kill(); enc.wait()
        errlog.close()
    el = time.time() - t0
    if failure is not None or enc.returncode:
        raise SystemExit(f'Rendu interrompu après {sent}/{N} images ({failure!r}), fichier partiel conservé : {part}')
    part.rename(final)
    print(f'Terminé : {sent} images en {el:.0f} s = {sent / el:.2f} img/s. {final}')
    (OUT_DIR / 'render_time.json').write_text(json.dumps(dict(frames=sent, seconds=el, fps_render=sent / el, workers=args.workers), indent=1), encoding='utf-8')


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd')
    a = sub.add_parser('still'); a.add_argument('k', type=int); a.add_argument('t', type=float); a.add_argument('out')
    b = sub.add_parser('frame'); b.add_argument('i', type=int); b.add_argument('out')
    r = sub.add_parser('render'); r.add_argument('--workers', type=int, default=18); r.add_argument('--chunk', type=int, default=3); r.add_argument('--frames', type=int)
    args = ap.parse_args()
    if args.cmd == 'still':
        t = time.time(); lo = world(args.k).lowres(args.t); Image.fromarray(lo).resize((W_OUT, H_OUT), Image.LANCZOS).save(args.out)
        print(f'monde {args.k} t={args.t}: {time.time() - t:.1f} s, raster {lo.shape}')
    elif args.cmd == 'frame':
        t = time.time(); to_output(compose_lowres(args.i / WD.FPS)).save(args.out); print(f'{time.time() - t:.1f} s')
    elif args.cmd == 'render': render(args)
    else: ap.print_help()


if __name__ == '__main__':
    main()
