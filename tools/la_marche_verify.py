"""Technical check of the « La marche » MP4, measured on the file (never on the renderer's word).

    python tools/la_marche_verify.py FILE.mp4 [out_dir]

structure + ffprobe (size, fps, duration, codecs, audio) + FULL decode + exact frame count + loudness / peak /
silence of the decoded audio track + frames extracted from the MP4 at chosen instants (brightness, deviation) + the
frame-to-frame difference around every world change (a dissolve is smooth, a cut is a spike) + a contact sheet.
"""
import json, subprocess, sys, re, hashlib
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FPS = 24
T0 = [6, 12, 18, 24, 30, 36, 42, 48, 54]


def run(cmd): return subprocess.run(cmd, capture_output=True, text=True)


def frame_at(mp4, i, w, h):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(mp4), '-vf', f'select=eq(n\\,{i})', '-vframes', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(h, w, 3) if len(r.stdout) == w * h * 3 else None


def main():
    mp4 = Path(sys.argv[1]); out = Path(sys.argv[2]) if len(sys.argv) > 2 else mp4.parent / 'verification'; out.mkdir(parents=True, exist_ok=True)
    rep = {'file': str(mp4), 'bytes': mp4.stat().st_size, 'sha256': hashlib.sha256(mp4.read_bytes()).hexdigest()}
    from hstudio import mediacheck as M
    rep['mediacheck'] = M.describe(mp4, want=(720, 1280), full=True)
    pr = json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(mp4)]).stdout)
    rep['streams'] = [{k: s.get(k) for k in ('codec_type', 'codec_name', 'profile', 'width', 'height', 'pix_fmt', 'r_frame_rate', 'avg_frame_rate', 'duration', 'nb_frames', 'sample_rate', 'channels', 'bit_rate')} for s in pr['streams']]
    rep['format_duration'] = pr['format'].get('duration')
    cnt = json.loads(run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames', '-of', 'json', str(mp4)]).stdout)
    rep['frames_decoded'] = int(cnt['streams'][0]['nb_read_frames'])
    dec = run(['ffmpeg', '-v', 'error', '-i', str(mp4), '-f', 'null', '-']); rep['full_decode_errors'] = dec.stderr.strip()[:300]
    eb = run(['ffmpeg', '-nostats', '-i', str(mp4), '-vn', '-af', 'ebur128=peak=true,silencedetect=n=-50dB:d=0.5', '-f', 'null', '-']).stderr
    rep['audio'] = dict(lufs=re.findall(r'I:\s+(-?[\d.]+) LUFS', eb)[-1:], lra=re.findall(r'LRA:\s+([\d.]+) LU', eb)[-1:], true_peak_dbtp=re.findall(r'Peak:\s+(-?[\d.]+) dBFS', eb)[-1:],
                        silences=re.findall(r'silence_(?:start|end): ([\d.]+)', eb))
    # frames really extracted from the MP4
    W, H = 720, 1280; picks = [0, 20, 100, 150, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1380, 1420, 1463]
    stats = []; sheet = Image.new('RGB', (144 * 10, 256 * 2))
    for n, i in enumerate(picks):
        a = frame_at(mp4, i, W, H)
        if a is None: stats.append(dict(frame=i, error='absent')); continue
        stats.append(dict(frame=i, t=round(i / FPS, 3), mean=round(float(a.mean()), 1), std=round(float(a.std()), 1)))
        if n < 20 and n < 20: sheet.paste(Image.fromarray(a).resize((144, 256)), ((n % 10) * 144, (n // 10) * 256))
        if i in (100, 700): Image.fromarray(a).save(out / f'image_{i:04d}.png')
    sheet.save(out / 'echantillons.png'); rep['samples'] = stats
    # frame-to-frame difference, whole film, at low resolution
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(mp4), '-vf', 'scale=72:128', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True)
    v = np.frombuffer(r.stdout, np.uint8).reshape(-1, 128, 72, 3).astype(np.float32)
    d = np.abs(np.diff(v, axis=0)).mean((1, 2, 3)); rep['diff'] = dict(median=float(np.median(d)), p99=float(np.percentile(d, 99)), max=float(d.max()), argmax_t=float((d.argmax() + 1) / FPS))
    around = {}
    for t in T0:
        i = int(round(t * FPS)); seg = d[max(0, i - 3):i + int(1.2 * FPS) + 3]; around[str(t)] = dict(max=round(float(seg.max()), 2), x_median=round(float(seg.max() / max(np.median(d), 1e-6)), 2))
    rep['around_world_changes'] = around
    (out / 'verification.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
    print(json.dumps({k: rep[k] for k in ('bytes', 'frames_decoded', 'full_decode_errors', 'audio', 'diff')}, indent=1, ensure_ascii=False)); print(str(rep["mediacheck"]))


if __name__ == '__main__':
    main()
