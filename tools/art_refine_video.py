"""A short, real A/B MP4: the same seconds of the same demo, shipped look on the left, art v2 on the right.

  python tools/art_refine_video.py --seconds 6 --aspect 16:9

Both sides come out of the production renderer (demos.prepare -> step_mix -> step_render), with the draft voice
(audio/scratch_voice.py). No ElevenLabs, no external API, no cost. The two halves are rendered one after the
other from the SAME project, by adding and removing the episode key "art" between the two passes, so nothing but
the art direction differs. ffmpeg then puts them side by side under a caption bar drawn with Pillow.
"""
import os, sys, json, shutil, argparse, subprocess
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from PIL import Image, ImageDraw, ImageFont
from hstudio import demos
from hstudio.pipeline import load_settings, step_mix, step_render
from hstudio.paths import FONT_MONTSERRAT

OUT_DIR = os.path.join(ROOT, 'docs', 'art_v2')


def ffmpeg():
    exe = shutil.which('ffmpeg')
    if exe: return exe
    import glob
    for pat in (os.path.expandvars(r'%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\**\bin\ffmpeg.exe'),):
        hit = glob.glob(pat, recursive=True)
        if hit: return hit[0]
    raise SystemExit('ffmpeg introuvable : ajoutez-le au PATH')


def label_bar(w, h, left, right):
    im = Image.new('RGBA', (w, h), (14, 16, 22, 255))
    d = ImageDraw.Draw(im)
    try: f = ImageFont.truetype(FONT_MONTSERRAT, int(h * .42))
    except Exception: f = ImageFont.load_default()
    d.text((w * .25, h * .28), left, font=f, fill=(226, 230, 240, 255), anchor='ma')
    d.text((w * .75, h * .28), right, font=f, fill=(226, 230, 240, 255), anchor='ma')
    d.rectangle([w // 2 - 1, 0, w // 2 + 1, h], fill=(60, 64, 78, 255))
    return im


def render_side(pr, settings, aspect, frames, art_key, tag, log):
    ep = pr.read_json('episode.json')
    if art_key: ep['art'] = art_key
    else: ep.pop('art', None)
    pr.write_json('episode.json', ep)
    out = step_render(pr, settings, aspect, 'standard', None, log, frames=frames)
    keep = pr.p('renders', 'ab_%s.mp4' % tag)
    shutil.move(out, keep)
    return keep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--demo', default='demo13_art_pixel3d')
    ap.add_argument('--aspect', default='16:9')
    ap.add_argument('--seconds', type=float, default=6.)
    ap.add_argument('--art', default='voxel_hd')
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    frames = int(a.seconds * 30)
    os.environ['PATH'] = os.path.dirname(ffmpeg()) + os.pathsep + os.environ.get('PATH', '')
    log = print
    pr = demos.prepare(a.demo, log)
    s = load_settings()
    step_mix(pr, s, log)
    try:
        left = render_side(pr, s, a.aspect, frames, None, 'ship', log)
        right = render_side(pr, s, a.aspect, frames, a.art, 'v2', log)
    finally:
        ep = pr.read_json('episode.json'); ep['art'] = a.art; pr.write_json('episode.json', ep)
    W, H = (1080, 1920) if a.aspect == '9:16' else (1920, 1080)
    hw, hh = W // 2, H // 2
    bar = 56
    bar_png = os.path.join(pr.p('renders'), 'ab_bar.png')
    label_bar(W, bar, 'ANCIEN STYLE (sans la cle "art")', 'PIXEL 3D v2  "art": "%s"' % a.art).save(bar_png)
    out = a.out or os.path.join(OUT_DIR, 'refine_ab_%s.mp4' % a.aspect.replace(':', 'x'))
    os.makedirs(OUT_DIR, exist_ok=True)
    cmd = [ffmpeg(), '-y', '-v', 'error', '-i', left, '-i', right, '-i', bar_png,
           '-filter_complex',
           '[0:v]scale=%d:%d[a];[1:v]scale=%d:%d[b];[a][b]hstack=inputs=2[s];'
           '[s]pad=%d:%d:0:%d:color=0x0e1016[p];[p][2:v]overlay=0:0[v]' % (hw, hh, hw, hh, W, hh + bar, bar),
           '-map', '[v]', '-map', '0:a', '-c:v', 'libx264', '-crf', '20', '-preset', 'medium',
           '-pix_fmt', 'yuv420p', '-r', '30', '-c:a', 'aac', '-b:a', '192k', '-shortest',
           '-movflags', '+faststart', out]
    subprocess.run(cmd, check=True)
    print('A/B ->', out, '(%d octets)' % os.path.getsize(out))
    print('cotes   ->', left, '|', right)


if __name__ == '__main__':
    main()
