"""Habillage commun : les images peintes par VOXEL reçoivent le MÊME titre, horloge, cœurs, choix et sous-titres que le style PS1 (c'est le `compose` de PIXEL 3D qui les dessine).
Le décor et les personnages changent d'un style à l'autre ; l'interface, elle, ne change pas : un seul code, un seul dessin."""
import subprocess, sys, numpy as np
from .. import ffmpeg_path  # noqa : met ffmpeg dans le PATH de ce processus


def apply(eng, src, dst, fps, size, crf=16, progress=None):
    """`src` (vidéo sans habillage, `size` = (L, H)) -> `dst` : chaque image reçoit l'habillage de `eng` (un Pixel3DEngine du même épisode)"""
    from ..engines.pixel3d import frame as F
    W, H = size; ctx = eng.ctx; ff = 'ffmpeg'
    dec = subprocess.Popen([ff, '-v', 'error', '-i', str(src), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    enc = subprocess.Popen([ff, '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(fps), '-i', '-', '-c:v', 'libx264', '-crf', str(crf), '-preset', 'medium',
                            '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(dst)], stdin=subprocess.PIPE)
    n = 0; sz = W * H * 3
    while True:
        buf = dec.stdout.read(sz)
        if len(buf) < sz: break
        g = n / float(fps); frame = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        k, t0, t1 = ctx.tl.at(g); shot, T, span = F.apply_cut(ctx.ep['shots'][k], g - t0, t1 - t0); u = F.clamp(T / max(1e-3, span))
        im = eng.compose(frame, g, shot, T, u)
        enc.stdin.write(np.asarray(im.convert('RGB'), np.uint8).tobytes()); n += 1
        if progress and n % 60 == 0: progress(n)
    enc.stdin.close(); enc.wait(); dec.wait()
    if enc.returncode: raise RuntimeError('ffmpeg (habillage) a échoué')
    return n
