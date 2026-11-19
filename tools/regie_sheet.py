"""Before / after of the actor direction: the same scene played by the régie alone and by the régie with the
gaze controller and the path footing switched on (`"eyeline": "smooth"`, `"footing": "path"`).

  python tools/regie_sheet.py                                  # the default scene, PNG + GIF + MP4 in docs/mesures/
  python tools/regie_sheet.py tests/scenes/regie_acteurs.json --aspect 9:16 --no-video
  python tools/regie_sheet.py --clip 13.5,20.5 --fps 20 --out docs/mesures

It renders real frames with the production engine (no mock, no still image dressed up as an animation), writes
  <name>_planche.png   a contact sheet, one row per version, the same timestamps
  <name>.gif           the two versions side by side around the cut and the walk
  <name>.mp4           the whole scene side by side (needs ffmpeg; imageio_ffmpeg's binary is used if found)
and prints the measurements of tools/motion_qc.py for both versions."""
import os, sys, json, copy, time, argparse, subprocess, shutil
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))
from PIL import Image, ImageDraw, ImageFont
from hstudio.pipeline import make_engine
from hstudio.acting.qc import _acting
from hstudio.paths import FONT_MONTSERRAT
from scene_sheet import scene_lines
from motion_qc import measure, stats

ON = {'eyeline': 'smooth', 'footing': 'path'}
LABELS = ("AVANT - regie seule : la tete se teleporte d'une cible a l'autre, le corps garde le cap du quart de tour",
          'APRES - "eyeline": "smooth" + "footing": "path" : le regard glisse et anticipe la coupe, le corps suit le chemin')
TOPS = ('AVANT  regie v2/v3', 'APRES  "eyeline": "smooth" + "footing": "path"')


def engine_of(scene, over, aspect):
    ep = copy.deepcopy(scene); lines = scene_lines(ep); ep.update(copy.deepcopy(over))
    dur = lines[-1]['end'] + .2
    eng = make_engine(ep.get('style', 'pixel3d'), ep, lines, np.zeros(10), dur, aspect)
    return eng, ep, dur


def label_strip(w, text, h=34, font=None):
    im = Image.new('RGB', (w, h), (14, 16, 22)); d = ImageDraw.Draw(im)
    d.text((8, 6), text, fill=(232, 228, 214), font=font); return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('scene', nargs='?', default=os.path.join(ROOT, 'tests', 'scenes', 'regie_acteurs.json'))
    ap.add_argument('--aspect', default='16:9'); ap.add_argument('--out', default=os.path.join(ROOT, 'docs', 'mesures'))
    ap.add_argument('--fps', type=float, default=20.); ap.add_argument('--cols', type=int, default=7)
    ap.add_argument('--width', type=int, default=480)
    ap.add_argument('--clip', default=None, help='a,b seconds: window kept for the GIF (default: the whole scene)')
    ap.add_argument('--gif-fps', type=float, default=10.); ap.add_argument('--no-video', action='store_true')
    a = ap.parse_args()
    scene = json.load(open(a.scene, encoding='utf-8'))
    name = os.path.splitext(os.path.basename(a.scene))[0]
    os.makedirs(a.out, exist_ok=True)
    try: font = ImageFont.truetype(FONT_MONTSERRAT, 19)
    except Exception: font = None

    engines = []
    for over in ({}, ON):
        eng, ep, dur = engine_of(scene, over, a.aspect)
        sn, sl = measure(_acting(eng), ep, eng.ctx.tl.spans if hasattr(eng, 'ctx') else eng.tl.spans, name)
        engines.append((eng, ep, dur, stats(sn, sl)))
    dur = engines[0][2]
    print(f'scene {name} ({dur:.1f} s, aspect {a.aspect})')
    for (lbl, (_e, _ep, _d, st)) in zip(('avant', 'apres'), engines):
        print(f"  {lbl:6s} saut de regard max {st['snap_max']:6.1f} deg ({st['snaps_over_25']} frame(s) > 25), "
              f"aux coupes moyenne {st['cut_mean']:5.2f} deg ; glissement du pied p95 {st['slide_p95']:5.2f} cm, max {st['slide_max']:5.2f}")

    W = a.width; H = int(round(W * (9 / 16 if a.aspect == '16:9' else 16 / 9)))
    t0 = time.perf_counter(); n_rendered = 0
    def shot(eng, t):
        nonlocal n_rendered
        n_rendered += 1
        return eng.frame(float(min(t, dur - .01))).resize((W, H), Image.LANCZOS)

    # ---------------------------------------------------------------- contact sheet
    ts = [dur * (i + .5) / a.cols for i in range(a.cols)]
    rows = [(LABELS[i], [shot(engines[i][0], t) for t in ts]) for i in (0, 1)]
    pad = 8; head = 30
    sheet = Image.new('RGB', (pad + a.cols * (W + pad), 2 * (head + H + pad) + pad), (14, 16, 22)); d = ImageDraw.Draw(sheet)
    for r, (title, ims) in enumerate(rows):
        y = pad + r * (head + H + pad); d.text((pad, y + 4), title, fill=(232, 228, 214), font=font)
        for i, im in enumerate(ims):
            sheet.paste(im, (pad + i * (W + pad), y + head))
            ImageDraw.Draw(sheet).text((pad + i * (W + pad) + 5, y + head + 3), f'{ts[i]:.1f}s', fill=(255, 220, 60), font=font)
    png = os.path.join(a.out, f'{name}_planche.png')
    sheet.quantize(colors=256, method=Image.MEDIANCUT).save(png, optimize=True)   # voxel art: 256 colours lose nothing
    print(' ->', png, f'({os.path.getsize(png) / 1e6:.2f} Mo, {sheet.width}x{sheet.height})')

    if a.no_video:
        print(f'{n_rendered} images rendues en {time.perf_counter() - t0:.1f} s'); return

    # ---------------------------------------------------------------- side by side animation
    head = 30; gap = 6
    frames = []
    times = [i / a.fps for i in range(int(dur * a.fps))]
    tops = [label_strip(W, TOPS[0], head, font), label_strip(W, TOPS[1], head, font)]
    for t in times:
        im = Image.new('RGB', (2 * W + gap, H + head), (14, 16, 22))
        im.paste(tops[0], (0, 0)); im.paste(tops[1], (W + gap, 0))
        im.paste(shot(engines[0][0], t), (0, head)); im.paste(shot(engines[1][0], t), (W + gap, head))
        ImageDraw.Draw(im).text((2 * W + gap - 62, 6), f'{t:5.1f}s', fill=(255, 220, 60), font=font)
        frames.append(im)
    gif = os.path.join(a.out, f'{name}.gif')
    k = max(1, int(round(a.fps / a.gif_fps)))
    lo, hi = (float(x) for x in a.clip.split(',')) if a.clip else (0., dur)
    keep = [f for f, t in zip(frames, times) if lo <= t <= hi][::k]
    small = [f.resize((f.width // 2, f.height // 2), Image.LANCZOS).convert('P', palette=Image.ADAPTIVE, colors=96) for f in keep]
    small[0].save(gif, save_all=True, append_images=small[1:], duration=int(1000 * k / a.fps), loop=0, optimize=True)
    print(' ->', gif, f'({os.path.getsize(gif) / 1e6:.2f} Mo, {len(small)} images, {lo:.1f}-{hi:.1f} s)')

    ff = shutil.which('ffmpeg')
    if ff is None:
        try:
            import imageio_ffmpeg; ff = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception: ff = None
    if ff is None:
        print(' !! ffmpeg introuvable : pas de MP4 (installe ffmpeg ou le paquet imageio-ffmpeg)')
    else:
        mp4 = os.path.join(a.out, f'{name}.mp4')
        w, h = frames[0].size; w -= w % 2; h -= h % 2
        cmd = [ff, '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{w}x{h}', '-r', str(a.fps),
               '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '26', '-pix_fmt', 'yuv420p', mp4]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for f in frames: p.stdin.write(np.asarray(f.crop((0, 0, w, h)), np.uint8).tobytes())
        p.stdin.close()
        if p.wait(): print(' !! ffmpeg a échoué')
        else: print(' ->', mp4, f'({os.path.getsize(mp4) / 1e6:.2f} Mo, {len(frames)} images)')
    print(f'{n_rendered} images rendues en {time.perf_counter() - t0:.1f} s')


if __name__ == '__main__': main()
