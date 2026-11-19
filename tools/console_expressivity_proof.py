"""CONSOLE 2D expressivity — proofs from the real engine: before/after stills and a real animated clip.

Nothing is faked and nothing is zoomed: the same episode is rendered twice, once with the historical
flat face ("faces": "flat", the default) and once with the acted face ("faces": "expressive"), at the
very same times and the very same framing.

  python tools/console_expressivity_proof.py stills [out.png] [--case console_demo] [--aspect 9:16]
  python tools/console_expressivity_proof.py clip   [out.mp4] [--case console_demo] [--from 19.5]
                                                    [--dur 6] [--fps 24] [--faces expressive] [--gif]
  python tools/console_expressivity_proof.py compare [out.mp4] [--case console_demo] [--from 19.5]
                                                    [--dur 6] [--fps 24] [--gif]
  python tools/console_expressivity_proof.py bench  [--case console_demo] [--frames 10]
  python tools/console_expressivity_proof.py motion [--case console_demo] [--from 19.9] [--dur 6]

The clip is encoded with the ffmpeg that ships with imageio-ffmpeg when ffmpeg is not on PATH, so it
costs nothing and calls no service.
"""
import os, sys, json, time, shutil, subprocess, argparse
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from PIL import Image, ImageDraw, ImageFont
from hstudio.pipeline import make_engine
from hstudio.paths import FONT_MONTSERRAT

# a time inside each of the shots that shows a face, for the stills
STILLS = {'console_demo': [2.3, 9.0, 20.4, 22.0, 31.0, 48.8],
          'demo5_console': [1.6, 9.5, 24.9, 32.0]}


def build(case, faces, aspect='9:16'):
    """the same episode, rendered by the real engine, with the faces flat or expressive"""
    if case in ('console_demo', 'partie4', 'monde'):
        from regress import load
        ep, lines, env = load(case)
        dur = lines[-1]['end'] + 1.5
    else:
        from hstudio import demos
        from hstudio.pipeline import duration_of
        sc = demos.load(case)
        lines = demos.timed_lines(sc['script'], float(sc.get('gap', .3)), float(sc.get('lead', .4)))
        env = demos.draft_voice(sc, lines)[1]
        ep = demos.episode_of(sc, lines, log=lambda *a: None)
        dur = duration_of(ep, lines)
    ep = json.loads(json.dumps(ep))
    ep['faces'] = faces
    if faces == 'expressive':
        who = next(iter(ep.get('cast') or {}), None) or 'noah'
        ep.setdefault('cast', {}).setdefault(who, {'ref': who})
        for sh in ep['shots']:                                   # the close-ups get the same identity
            s = sh.get('scene') or {}
            if s.get('type') == 'face': s.setdefault('who', who)
    return make_engine('console', ep, lines, env, dur, aspect), dur


def stills(case, out, aspect='9:16', times=None, scale=.34):
    times = times or STILLS.get(case) or [2.3, 9.0, 20.4]
    rows = []
    for faces in ('flat', 'expressive'):
        eng, _ = build(case, faces, aspect)
        rows.append([eng.frame(t) for t in times])
    w = int(rows[0][0].size[0] * scale); h = int(rows[0][0].size[1] * scale)
    pad, head = 10, 44
    sheet = Image.new('RGB', (pad + len(times) * (w + pad), 2 * (head + h) + pad), (14, 16, 24))
    d = ImageDraw.Draw(sheet)
    try: f = ImageFont.truetype(FONT_MONTSERRAT, 22)
    except Exception: f = None
    labels = ['AVANT — "faces": "flat" (défaut, inchangé)',
              'APRÈS — "faces": "expressive" (paupières, regard, sourcils, parole, micro-mouvements)']
    for r, ims in enumerate(rows):
        y = r * (head + h) + pad
        d.text((pad, y + 8), labels[r], fill=(236, 232, 220), font=f)
        for i, im in enumerate(ims):
            sheet.paste(im.resize((w, h), Image.LANCZOS), (pad + i * (w + pad), y + head))
            d.text((pad + i * (w + pad) + 4, y + head + 2), f't={times[i]:g}s', fill=(190, 196, 214), font=f)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    sheet.save(out); print(out)
    return out


def ffmpeg_exe():
    exe = shutil.which('ffmpeg')
    if exe: return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def clip(case, out, t0=19.5, dur=6.0, fps=24, aspect='9:16', faces='expressive', gif=False):
    """a real animated clip of the real engine: one encoded frame per rendered frame, no slideshow"""
    eng, total = build(case, faces, aspect)
    n = int(round(dur * fps))
    W, H = eng.W, eng.H
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    exe = ffmpeg_exe()
    cmd = [exe, '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
           '-r', str(fps), '-i', '-', '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
           '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out]
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    frames = []
    t_start = time.perf_counter()
    for i in range(n):
        g = min(total - 1e-3, t0 + i / fps)
        im = eng.frame(g).convert('RGB')
        enc.stdin.write(np.asarray(im).tobytes())
        if gif: frames.append(im.resize((W // 3, H // 3), Image.LANCZOS))
    enc.stdin.close()
    err = enc.stderr.read().decode('utf-8', 'ignore')
    if enc.wait(): raise RuntimeError('ffmpeg: ' + err)
    secs = time.perf_counter() - t_start
    print(f'{out}  {n} frames @ {fps} fps = {n / fps:.2f} s  ({secs / n:.3f} s/frame rendered)')
    if gif:
        g_out = os.path.splitext(out)[0] + '.gif'
        frames[0].save(g_out, save_all=True, append_images=frames[1:], duration=int(1000 / fps),
                       loop=0, optimize=True)
        print(g_out)
    return out, secs / n


def compare_clip(case, out, t0=19.5, dur=6.0, fps=24, aspect='9:16', gif=False):
    """AVANT | APRÈS side by side, same times, same framing, one rendered frame per encoded frame"""
    ea, _ = build(case, 'flat', aspect)
    eb, total = build(case, 'expressive', aspect)
    n = int(round(dur * fps))
    half = 760 if aspect == '9:16' else 960
    hh = int(half * ea.H / ea.W) // 2 * 2                        # h264 wants even sides
    W, H = half * 2 + 12, hh + 46
    try: f = ImageFont.truetype(FONT_MONTSERRAT, 24)
    except Exception: f = None
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    cmd = [ffmpeg_exe(), '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
           '-s', f'{W}x{H}', '-r', str(fps), '-i', '-', '-an', '-c:v', 'libx264',
           '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out]
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    frames = []
    t_start = time.perf_counter()
    for i in range(n):
        g = min(total - 1e-3, t0 + i / fps)
        sheet = Image.new('RGB', (W, H), (12, 14, 22))
        d = ImageDraw.Draw(sheet)
        d.text((8, 10), 'AVANT  "faces": "flat"', fill=(200, 204, 218), font=f)
        d.text((half + 20, 10), 'APRES  "faces": "expressive"', fill=(156, 255, 122), font=f)
        sheet.paste(ea.frame(g).convert('RGB').resize((half, hh), Image.LANCZOS), (0, 44))
        sheet.paste(eb.frame(g).convert('RGB').resize((half, hh), Image.LANCZOS), (half + 12, 44))
        enc.stdin.write(np.asarray(sheet).tobytes())
        if gif and i % 2 == 0: frames.append(sheet.resize((W // 2, H // 2), Image.LANCZOS))
    enc.stdin.close()
    err = enc.stderr.read().decode('utf-8', 'ignore')
    if enc.wait(): raise RuntimeError('ffmpeg: ' + err)
    secs = time.perf_counter() - t_start
    print(f'{out}  {n} frames @ {fps} fps = {n / fps:.2f} s  ({secs / n:.3f} s/paire)')
    if gif:
        g_out = os.path.splitext(out)[0] + '.gif'
        frames[0].save(g_out, save_all=True, append_images=frames[1:], duration=int(2000 / fps),
                       loop=0, optimize=True)
        print(g_out)
    return out


def motion(case, t0=19.9, dur=6.0, fps=24, aspect='9:16', box=(.26, .24, .74, .60)):
    """how much the face really moves, flat vs expressive, with the film grain filtered out

    The engine adds per-frame grain, so a raw frame difference is never zero. Blurring both frames
    before the difference removes the grain and leaves the drawing: eyelids, pupils, brows, mouth."""
    from PIL import ImageFilter
    rows = []
    n = int(round(dur * fps))
    for faces in ('flat', 'expressive'):
        eng, total = build(case, faces, aspect)
        x0, y0, x1, y1 = [int(v * (eng.W if i % 2 == 0 else eng.H)) for i, v in enumerate(box)]
        prev = None; diffs = []
        for i in range(n):
            g = min(total - 1e-3, t0 + i / fps)
            im = eng.frame(g).convert('L').crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(2.5))
            a_ = np.asarray(im, np.int16)
            if prev is not None: diffs.append(float(np.abs(a_ - prev).mean()))
            prev = a_
        rows.append((faces, float(np.mean(diffs)), float(np.max(diffs)),
                     int(sum(1 for d in diffs if d < .05))))
    print(f'{case} {aspect}  fenêtre {t0}s..{t0 + dur}s, {n} images, zone visage {box}')
    for faces, m, mx, still in rows:
        print(f'  faces={faces:11s} mouvement moyen {m:6.3f}  pic {mx:6.3f}  images figées {still}/{n - 1}')
    if rows[0][1] > 0: print(f'  rapport APRES/AVANT : x{rows[1][1] / rows[0][1]:.2f}')
    return rows


def bench_once(case, faces, frames=10, aspect='9:16'):
    """one measurement, in this process: seconds per final 1080p frame"""
    eng, dur = build(case, faces, aspect)
    ts = [dur * (i + .5) / frames for i in range(frames)]
    eng.frame(ts[0])                                              # warm the caches
    t0 = time.perf_counter()
    for t in ts: eng.frame(t)
    return (time.perf_counter() - t0) / frames


def bench(case, frames=10, aspect='9:16', repeat=5):
    """cost of a frame, flat vs expressive.

    Each measurement runs in its own process and the two settings alternate: keeping both engines
    alive in one process doubles the scene caches and biases the second one by tens of percent.
    The minimum of the repeats is reported, it is the estimator least polluted by the machine."""
    runs = {'flat': [], 'expressive': []}
    for i in range(repeat):
        for faces in ('flat', 'expressive') if i % 2 == 0 else ('expressive', 'flat'):
            out = subprocess.run([sys.executable, os.path.abspath(__file__), 'one',
                                  '--case', case, '--aspect', aspect, '--faces', faces,
                                  '--frames', str(frames)], capture_output=True, text=True)
            if out.returncode: raise RuntimeError(out.stderr[-2000:])
            runs[faces].append(float(out.stdout.strip().splitlines()[-1]))
    for faces in ('flat', 'expressive'):
        v = sorted(runs[faces])
        print(f'{case:14s} {aspect:5s} faces={faces:11s} min {v[0]:6.3f}  médiane {v[len(v) // 2]:6.3f}'
              f'  max {v[-1]:6.3f} s/image  ({repeat} mesures)')
    lo = min(runs['flat']); hi = min(runs['expressive'])
    print(f'{"":14s} {"":5s} écart sur le minimum : {hi - lo:+.3f} s/image ({100 * (hi / lo - 1):+.1f} %)')
    return runs


def bench_face_only(n=400):
    """cost of the face drawing alone, historical vs expressive, away from the rest of the frame"""
    from PIL import Image as _I
    from hstudio.engines.console import flat as _flat
    sample = dict(x=0., z=1., y=0., heading=0., face='scared', talking=True, blink=False,
                  rig=dict(t=1., seed=.3, head=(.2, -.1)), gaze=None)
    out = {}
    for look in ({'faces': 'flat'}, {'faces': 'expressive'}):
        im = _I.new('RGB', (300, 300), (224, 172, 136)); d = ImageDraw.Draw(im)
        _flat.face(d, 150, 150, 110, sample, 1., look, (224, 172, 136), (24, 26, 46))   # warm
        t0 = time.perf_counter()
        for i in range(n):
            _flat.face(d, 150, 150, 110, dict(sample, rig=dict(sample['rig'], t=i * .03)),
                       i * .03, look, (224, 172, 136), (24, 26, 46))
        out[look['faces']] = (time.perf_counter() - t0) / n * 1000
    print(f'visage seul (r=110 px, {n} appels) : flat {out["flat"]:.3f} ms, '
          f'expressive {out["expressive"]:.3f} ms, soit {out["expressive"] - out["flat"]:+.3f} ms par visage')
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=('stills', 'clip', 'compare', 'bench', 'motion', 'one'))
    ap.add_argument('out', nargs='?', default=None)
    ap.add_argument('--case', default='console_demo')
    ap.add_argument('--aspect', default='9:16')
    ap.add_argument('--from', dest='t0', type=float, default=19.5)
    ap.add_argument('--dur', type=float, default=6.0)
    ap.add_argument('--fps', type=int, default=24)
    ap.add_argument('--faces', default='expressive', choices=('flat', 'expressive'))
    ap.add_argument('--frames', type=int, default=10)
    ap.add_argument('--gif', action='store_true')
    ap.add_argument('--repeat', type=int, default=5)
    ap.add_argument('--box', default='')
    ap.add_argument('--times', default='')
    a = ap.parse_args()
    D = os.path.join(ROOT, 'docs', 'proofs', 'console2d')
    if a.mode == 'stills':
        ts = [float(x) for x in a.times.split(',')] if a.times else None
        stills(a.case, a.out or os.path.join(D, f'avant_apres_{a.case}_{a.aspect.replace(":", "")}.png'),
               a.aspect, ts)
    elif a.mode == 'compare':
        compare_clip(a.case, a.out or os.path.join(D, f'compare_{a.case}_{a.aspect.replace(":", "")}.mp4'),
                     a.t0, a.dur, a.fps, a.aspect, a.gif)
    elif a.mode == 'clip':
        clip(a.case, a.out or os.path.join(D, f'clip_{a.case}_{a.faces}_{a.aspect.replace(":", "")}.mp4'),
             a.t0, a.dur, a.fps, a.aspect, a.faces, a.gif)
    elif a.mode == 'motion':
        motion(a.case, a.t0, a.dur, a.fps, a.aspect, tuple(float(v) for v in a.box.split(','))
               if a.box else (.26, .24, .74, .60))
    elif a.mode == 'one':
        print(f'{bench_once(a.case, a.faces, a.frames, a.aspect):.6f}')
    else:
        bench(a.case, a.frames, a.aspect, a.repeat)
        bench_face_only()
