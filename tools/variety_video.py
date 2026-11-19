"""Before / after as a real video: the same camera move, in the shipped place and in the varied one, side by side.

  python tools/variety_video.py                       # docs/world_variety/avant_apres_decors_16x9.mp4
  python tools/variety_video.py --cases bedroom,alley --seconds 8

This is not a slideshow: both halves are rendered frame by frame at 30 fps with a continuous dolly, through the same
`render_lowres` path the production pipeline uses, then upscaled to 1080p and encoded with ffmpeg. The two halves
share one camera track to the metre, so any difference you see is the decor and nothing else.
"""
import argparse, json, math, os, subprocess, sys, time
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from PIL import Image, ImageDraw, ImageFont
from hstudio.paths import FONT_MONTSERRAT

OUT = os.path.join(ROOT, 'docs', 'world_variety')

# name -> (before, after, camera track [(pos, look, fov) start, (pos, look, fov) end], caption)
MOVES = {
    'bedroom': ({'type': 'bedroom'}, {'type': 'bedroom', 'variation': {'mood': 'haunted', 'seed': 4}},
                (((1.70, 1.62, 0.40), (-1.0, 1.25, 4.30), 66), ((0.70, 1.56, 1.45), (-0.9, 1.20, 4.60), 62)),
                'CHAMBRE  —  recette livree / variation "haunted"'),
    'living_room': ({'type': 'living_room'}, {'type': 'living_room', 'variation': {'mood': 'lived_in', 'seed': 7}},
                    (((2.10, 1.64, 0.45), (-1.3, 1.15, 4.70), 68), ((0.90, 1.60, 1.70), (-1.1, 1.15, 5.00), 64)),
                    'SALON  —  recette livree / variation "lived_in"'),
    'basement': ({'type': 'basement'}, {'type': 'basement', 'variation': {'mood': 'abandoned', 'seed': 2}},
                 (((2.45, 1.58, 0.55), (-1.6, 1.05, 5.80), 70), ((1.30, 1.54, 2.10), (-1.4, 1.05, 6.10), 66)),
                 'CAVE  —  recette livree / variation "abandoned"'),
    'alley': ({'type': 'city_street', 'sky': 'night'}, {'type': 'alley', 'seed': 4},
              (((0.00, 1.60, 0.70), (0.3, 1.50, 13.0), 62), ((0.30, 1.58, 4.20), (-0.2, 1.45, 16.0), 62)),
              'EXTERIEUR  —  "city_street" nuit / nouvel archetype "alley"'),
    'corridor': ({'type': 'apartment'}, {'type': 'corridor', 'seed': 3},
                 (((0.00, 1.60, 0.55), (0.0, 1.35, 12.0), 58), ((0.10, 1.58, 4.00), (0.0, 1.35, 15.0), 58)),
                 'COULOIR  —  prefab "apartment" / nouvel archetype "corridor"'),
    'parking': ({'type': 'basement', 'dirty': True}, {'type': 'parking', 'seed': 6},
                (((0.00, 1.62, 0.80), (0.6, 1.15, 12.0), 68), ((0.60, 1.60, 4.60), (0.2, 1.15, 16.0), 68)),
                'PARKING  —  "basement" / nouvel archetype "parking"'),
}


def lerp(a, b, t):
    return [a[i] + (b[i] - a[i]) * t for i in range(len(a))]


def cam_at(track, t):
    (p0, l0, f0), (p1, l1, f1) = track
    e = t * t * (3 - 2 * t)                       # ease in / out, like the engine's camera moves
    pos, look = lerp(p0, p1, e), lerp(l0, l1, e)
    dx, dy, dz = (look[i] - pos[i] for i in range(3))
    return (tuple(pos), math.atan2(dx, dz), math.atan2(dy, math.hypot(dx, dz)), 0., f0 + (f1 - f0) * e)


def build(spec, aspect):
    from hstudio.engines.pixel3d import r3d, sets
    r3d.configure(aspect)
    st = sets.make_set(spec.get('type', 'room'), spec)
    st.build()
    return st


def frame(st, cam, half):
    """one native low-res frame, graded like render.render_lowres, cropped (never squashed) to the panel shape"""
    from hstudio.engines.pixel3d import r3d, render as RD
    sc = st.scene({}, 0., 0.)
    L = st.lights({}, 0., 0., np.array(cam[0], np.float32))
    img = r3d.glow(r3d.render(sc, cam, L))
    lum = (img * np.array([.3, .59, .11], np.float32)).sum(-1, keepdims=True)
    img = lum + (img - lum) * RD.SAT
    img = img * RD.EXPO * np.array([1.0, .98, .9], np.float32) + np.array([.014, .012, .010], np.float32)
    im = Image.fromarray(r3d.pixelate(np.clip(img, 0, None) ** 1.08, gamma=1.0))
    w, h = im.size
    want = half[0] / half[1]
    if w / h > want:                              # a central crop of the wide raster, same pixels, same scale
        cw = int(round(h * want))
        im = im.crop(((w - cw) // 2, 0, (w - cw) // 2 + cw, h))
    else:
        ch = int(round(w / want))
        im = im.crop((0, (h - ch) // 2, w, (h - ch) // 2 + ch))
    return im.resize(half, Image.NEAREST)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--aspect', default='16:9')
    ap.add_argument('--cases', default='bedroom,living_room,basement,corridor,parking,alley')
    ap.add_argument('--seconds', type=float, default=7.0)
    ap.add_argument('--fps', type=int, default=30)
    ap.add_argument('--out', default='')
    ap.add_argument('--ffmpeg', default=os.environ.get('HSTUDIO_FFMPEG', 'ffmpeg'))
    a = ap.parse_args()
    names = [n for n in a.cases.split(',') if n]
    os.makedirs(OUT, exist_ok=True)
    work = os.path.join(OUT, '_work')
    os.makedirs(work, exist_ok=True)
    W_, H_ = (1920, 1080) if a.aspect == '16:9' else (1080, 1920)
    half = (W_ // 2, H_)                          # each side fills the full height: the frame is not letterboxed
    try:
        f = ImageFont.truetype(FONT_MONTSERRAT, 26)
        fs = ImageFont.truetype(FONT_MONTSERRAT, 22)
    except Exception:
        f = fs = None
    n_per = int(a.seconds * a.fps)
    k = 0
    t0 = time.perf_counter()
    for name in names:
        before, after, track, cap = MOVES[name]
        A = build(before, a.aspect)
        B = build(after, a.aspect)
        for i in range(n_per):
            t = i / max(1, n_per - 1)
            cam = cam_at(track, t)
            ia = frame(A, cam, half)
            ib = frame(B, cam, half)
            sheet = Image.new('RGB', (W_, H_), (10, 11, 15))
            sheet.paste(ia, (0, 0))
            sheet.paste(ib, (W_ // 2, 0))
            d = ImageDraw.Draw(sheet)
            d.line([W_ // 2, 0, W_ // 2, H_], fill=(10, 11, 15), width=6)
            d.rectangle([0, 0, W_, 58], fill=(10, 11, 15))
            d.rectangle([0, H_ - 54, W_, H_], fill=(10, 11, 15))
            d.text((22, 16), cap, fill=(236, 232, 218), font=f)
            d.text((22, H_ - 44), 'AVANT', fill=(186, 196, 214), font=fs)
            d.text((W_ // 2 + 22, H_ - 44), 'APRES', fill=(255, 214, 112), font=fs)
            sheet.save(os.path.join(work, f'f_{k:05d}.png'))
            k += 1
        print(f'{name}: {n_per} images ({time.perf_counter() - t0:.0f} s cumulées)', flush=True)
    out = a.out or os.path.join(OUT, f'avant_apres_decors_{"16x9" if a.aspect == "16:9" else "9x16"}.mp4')
    cmd = [a.ffmpeg, '-y', '-framerate', str(a.fps), '-i', os.path.join(work, 'f_%05d.png'),
           '-c:v', 'libx264', '-preset', 'slow', '-crf', '21', '-pix_fmt', 'yuv420p', out]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for fn in os.listdir(work):
        os.remove(os.path.join(work, fn))
    os.rmdir(work)
    print(out)
    print(json.dumps({'frames': k, 'fps': a.fps, 'seconds': round(k / a.fps, 2), 'size': [W_, H_],
                      'cases': names, 'bytes': os.path.getsize(out)}))


if __name__ == '__main__':
    main()
