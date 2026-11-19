"""Contact sheets of a source video: frames at given indices (or before/after pairs around candidate cuts), labelled with the
time, so a human (or the director) can look at what is really there before writing the scene file."""
import subprocess
import numpy as np
from PIL import Image, ImageDraw

try: from PIL import ImageFont; FONT = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 15)
except Exception: FONT = None


def grab(path, idxs, w=120, h=213, fps=30):
    """frames at the given frame indices -> {index: PIL image}. One decode of the whole file, only the wanted frames are kept
    (a select filter with hundreds of terms is refused by ffmpeg)"""
    want = sorted(set(max(0, int(i)) for i in idxs)); keep = set(want); out = {}
    r = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', str(path), '-vf', f'scale={w}:{h}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    n = w * h * 3; i = 0; last = want[-1] if want else -1
    while i <= last:
        b = r.stdout.read(n)
        if len(b) < n: break
        if i in keep: out[i] = Image.fromarray(np.frombuffer(b, np.uint8).reshape(h, w, 3).copy())
        i += 1
    r.kill(); r.wait()
    return out


def sheet(path, groups, out, cols=6, w=120, h=213, fps=30):
    """groups: list of (label, [frame indices]); each group is one tile row cell made of its frames side by side"""
    need = [i for _, g in groups for i in g]; im = grab(path, need, w, h, fps)
    gw = max(len(g) for _, g in groups) * w; rows = (len(groups) + cols - 1) // cols
    S = Image.new('RGB', (cols * (gw + 6), rows * (h + 22)), (20, 20, 20)); d = ImageDraw.Draw(S)
    for k, (lab, g) in enumerate(groups):
        x0 = (k % cols) * (gw + 6); y0 = (k // cols) * (h + 22)
        d.text((x0 + 2, y0 + 2), lab, fill=(255, 255, 0), font=FONT)
        for j, i in enumerate(g):
            if i in im: S.paste(im[i], (x0 + j * w, y0 + 20))
    S.save(out); return out
