"""Before / after of the directed locomotion: the same scene played without and with `"approach": "directed"`.

  python tools/approche_sheet.py                                   # 16:9, PNG + GIF + MP4 in docs/mesures/
  python tools/approche_sheet.py --aspect 9:16 --out docs/mesures/vertical
  python tools/approche_sheet.py tests/scenes/approche_lea_tom.json --no-video

Real frames of the production engine (`eng.frame(t)`), no mock and no still image dressed up as an animation. The
two versions are the *same scene file*: only the episode key `"approach"` differs, so the set, the light, the walk,
the timing of the line and the camera are the same on both sides.

Writes, for a scene named <name>:
  <name>_planche.png   contact sheet, one row per version, the same timestamps
  <name>_ab.mp4        the two versions side by side (this is the A/B the owner should watch)
  <name>_a_sans.mp4    version A alone (historical)
  <name>_b_avec.mp4    version B alone ("approach": "directed")
  <name>.gif           a short side-by-side window, for the report

ffmpeg is not in the PATH of the owner's machine: the binary shipped with the Python package imageio-ffmpeg is
used when `ffmpeg` cannot be found, exactly as tools/regie_sheet.py does.
"""
import os, sys, json, copy, time, math, argparse, subprocess, shutil
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))
from PIL import Image, ImageDraw, ImageFont                       # noqa: E402
from hstudio.pipeline import make_engine, duration_of             # noqa: E402
from hstudio.paths import FONT_MONTSERRAT                         # noqa: E402
from locomotion_qc import read_scene, measure                     # noqa: E402

TOPS = ('A  SANS l\'option : le corps garde le cap du depart, Lea avance de cote',
        'B  "approach": "directed" : le corps tourne vers la ou il va, et s\'arrete face a Tom')


def ffmpeg_exe():
    ff = shutil.which('ffmpeg')
    if ff: return ff
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


class Mp4:
    """an ffmpeg process fed frame by frame, so nothing big is kept in memory"""
    def __init__(self, ff, path, size, fps, crf=30):
        self.path = path; w, h = size; self.w = w - w % 2; self.h = h - h % 2; self.p = None
        if ff is None: return
        self.p = subprocess.Popen([ff, '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                                   '-s', f'{self.w}x{self.h}', '-r', str(fps), '-i', '-',
                                   '-c:v', 'libx264', '-preset', 'slower', '-crf', str(crf),
                                   '-pix_fmt', 'yuv420p', path], stdin=subprocess.PIPE)

    def write(self, im):
        if self.p: self.p.stdin.write(np.asarray(im.crop((0, 0, self.w, self.h)), np.uint8).tobytes())

    def close(self, n):
        if not self.p: return
        self.p.stdin.close()
        if self.p.wait(): print('  !! ffmpeg a echoue pour', self.path)
        else: print('  ->', self.path, f'({os.path.getsize(self.path) / 1e6:.2f} Mo, {n} images, {self.w}x{self.h})')


def engine_of(scene, lines, directed, aspect):
    ep = copy.deepcopy(scene)
    if directed: ep['approach'] = 'directed'
    else: ep.pop('approach', None)
    dur = duration_of(ep, lines)
    return make_engine(ep.get('style', 'pixel3d'), ep, lines, np.zeros(10), dur, aspect), ep, dur


def strip(w, text, h, font):
    im = Image.new('RGB', (w, h), (14, 16, 22))
    ImageDraw.Draw(im).text((8, (h - 20) // 2), text, fill=(232, 228, 214), font=font)
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('scene', nargs='?', default=os.path.join(ROOT, 'tests', 'scenes', 'approche_lea_tom.json'))
    ap.add_argument('--aspect', default='16:9')
    ap.add_argument('--out', default=os.path.join(ROOT, 'docs', 'mesures'))
    ap.add_argument('--fps', type=float, default=20.)
    ap.add_argument('--width', type=int, default=960)
    ap.add_argument('--cols', type=int, default=7)
    ap.add_argument('--gif-fps', type=float, default=10.)
    ap.add_argument('--clip', default=None, help='a,b secondes gardees pour le GIF')
    ap.add_argument('--no-video', action='store_true')
    ap.add_argument('--crf', type=int, default=30, help='qualite x264 (plus grand = plus petit fichier)')
    ap.add_argument('--ab-only', action='store_true', help='ecrire seulement la video cote a cote')
    a = ap.parse_args()

    scene, lines = read_scene(a.scene)
    name = os.path.splitext(os.path.basename(a.scene))[0]
    os.makedirs(a.out, exist_ok=True)
    try: font = ImageFont.truetype(FONT_MONTSERRAT, 19)
    except Exception: font = None

    print(f'{name}  ({a.aspect})')
    engines = []
    for directed in (False, True):
        eng, ep, dur = engine_of(scene, lines, directed, a.aspect)
        engines.append((eng, ep, dur))
    dur = engines[0][2]

    # The cinematographer solves the camera from the actors' headings, so the fix would move the camera and the two
    # halves of the A/B would not be comparable. The camera of version A -- chosen before the fix existed, so it
    # cannot have been picked to flatter B -- is solved once and imposed on both sides. Only the acting differs.
    engines[0][0].frame(0.)
    engines[1][0].ctx.cam_cache.update(engines[0][0].ctx.cam_cache)
    engines[1][0].ctx.cam_memory.update(engines[0][0].ctx.cam_memory)

    W = a.width; H = int(round(W * (9 / 16 if a.aspect == '16:9' else 16 / 9)))
    n_rendered = 0; t_start = time.perf_counter()

    def shot(i, t):
        nonlocal n_rendered
        n_rendered += 1
        return engines[i][0].frame(float(min(t, dur - .01))).resize((W, H), Image.LANCZOS)

    # ---------------------------------------------------------------- contact sheet
    ts = [dur * (i + .5) / a.cols for i in range(a.cols)]
    pad = 8; head = 30
    sheet = Image.new('RGB', (pad + a.cols * (W // 2 + pad), 2 * (head + H // 2 + pad) + pad), (14, 16, 22))
    d = ImageDraw.Draw(sheet)
    for r in (0, 1):
        y = pad + r * (head + H // 2 + pad)
        d.text((pad, y + 4), TOPS[r], fill=(232, 228, 214), font=font)
        for i, t in enumerate(ts):
            im = shot(r, t).resize((W // 2, H // 2), Image.LANCZOS)
            sheet.paste(im, (pad + i * (W // 2 + pad), y + head))
            d.text((pad + i * (W // 2 + pad) + 5, y + head + 3), f'{t:.1f}s', fill=(255, 220, 60), font=font)
    png = os.path.join(a.out, f'{name}_planche.png')
    sheet.quantize(colors=256, method=Image.MEDIANCUT).save(png, optimize=True)
    print('  ->', png, f'({os.path.getsize(png) / 1e6:.2f} Mo, {sheet.width}x{sheet.height})')

    if a.no_video:
        print(f'  {n_rendered} images rendues en {time.perf_counter() - t_start:.1f} s'); return

    # ---------------------------------------------------------------- the three videos, written as we render
    ff = ffmpeg_exe()
    if ff is None: print('  !! ffmpeg introuvable (ni dans le PATH, ni via imageio-ffmpeg) : pas de MP4')
    gap = 6
    vids = {'ab': Mp4(ff, os.path.join(a.out, f'{name}_ab.mp4'), (2 * W + gap, H + head), a.fps, a.crf)}
    if not a.ab_only:
        vids['a'] = Mp4(ff, os.path.join(a.out, f'{name}_a_sans.mp4'), (W, H), a.fps, a.crf)
        vids['b'] = Mp4(ff, os.path.join(a.out, f'{name}_b_avec.mp4'), (W, H), a.fps, a.crf)
    tops = (strip(W, TOPS[0], head, font), strip(W, TOPS[1], head, font))
    times = [i / a.fps for i in range(int(dur * a.fps))]
    lo, hi = (float(x) for x in a.clip.split(',')) if a.clip else (0., dur)
    k = max(1, int(round(a.fps / a.gif_fps))); gif_frames = []
    for n, t in enumerate(times):
        fa = shot(0, t); fb = shot(1, t)
        im = Image.new('RGB', (2 * W + gap, H + head), (14, 16, 22))
        im.paste(tops[0], (0, 0)); im.paste(tops[1], (W + gap, 0))
        im.paste(fa, (0, head)); im.paste(fb, (W + gap, head))
        ImageDraw.Draw(im).text((2 * W + gap - 70, 6), f'{t:5.1f}s', fill=(255, 220, 60), font=font)
        vids['ab'].write(im)
        if 'a' in vids: vids['a'].write(fa); vids['b'].write(fb)
        if lo <= t <= hi and n % k == 0:
            gif_frames.append(im.resize((im.width // 3, im.height // 3), Image.LANCZOS).convert('P', palette=Image.ADAPTIVE, colors=96))
    for key, v in vids.items(): v.close(len(times))
    if gif_frames:
        gif = os.path.join(a.out, f'{name}.gif')
        gif_frames[0].save(gif, save_all=True, append_images=gif_frames[1:], duration=int(1000 * k / a.fps), loop=0, optimize=True)
        print('  ->', gif, f'({os.path.getsize(gif) / 1e6:.2f} Mo, {len(gif_frames)} images, {lo:.1f}-{hi:.1f} s)')
    print(f'  {n_rendered} images rendues en {time.perf_counter() - t_start:.1f} s')


if __name__ == '__main__':
    main()
