"""Shot-boundary detection on a source video, with the subtitle band and the HUD strip masked out so that a new caption
chunk is not taken for a cut. Reads the video through ffmpeg (raw gray frames at low resolution), so it is cheap and exact
on the frame grid: a cut is reported as the index of the FIRST frame of the new shot."""
import subprocess
import numpy as np

W, H = 90, 160


def frames(path, w=W, h=H):
    r = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', str(path), '-vf', f'scale={w}:{h}:flags=area,format=gray', '-f', 'rawvideo', '-'], stdout=subprocess.PIPE)
    n = w * h
    while True:
        b = r.stdout.read(n)
        if len(b) < n: break
        yield np.frombuffer(b, np.uint8).reshape(h, w).astype(np.float32)
    r.wait()


def diffs(path, mask_rows=((0, .07), (.40, .60), (.62, .85))):
    """per-frame mean absolute difference with the previous frame, outside the masked row bands (fractions of the height)"""
    keep = np.ones(H, bool)
    for a, b in mask_rows: keep[int(a * H):int(b * H)] = False
    prev = None; out = [0.]
    for f in frames(path):
        if prev is not None: out.append(float(np.abs(f[keep] - prev[keep]).mean()))
        prev = f
    return np.array(out)


def find_cuts(d, ratio=3.2, floor=9.0):
    """frame indices where the jump is large in absolute terms AND against the local motion (so fast camera moves are not cuts)"""
    cuts = []
    for i in range(1, len(d)):
        loc = np.r_[d[max(1, i - 4):i], d[i + 1:i + 5]]
        base = float(np.median(loc)) if len(loc) else 0.
        if d[i] > floor and d[i] > ratio * max(base, 1.0): cuts.append(i)
    return cuts
