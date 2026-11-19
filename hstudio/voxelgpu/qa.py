"""Verification of a delivered MP4, measured on the file (never on the renderer's word): structure, ffprobe, FULL decode,
exact frame count, duration, resolution, fps, audio presence / loudness / peak / silence, picture statistics (not black, moving,
not frozen), and fingerprints (SHA-256 of the file + of downscaled frames every 12th frame, so two renders can be compared)."""
import hashlib, json, re, subprocess
from pathlib import Path
import numpy as np


def _run(cmd): return subprocess.run(cmd, capture_output=True, text=True)


def verify(mp4, want_w=None, want_h=None, want_fps=None, want_dur=None, need_audio=True, out_json=None):
    mp4 = Path(mp4); rep = dict(file=str(mp4), bytes=mp4.stat().st_size, sha256=hashlib.sha256(mp4.read_bytes()).hexdigest(), checks={}, ok=True)
    pr = json.loads(_run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(mp4)]).stdout)
    v = next((s for s in pr['streams'] if s['codec_type'] == 'video'), None); a = next((s for s in pr['streams'] if s['codec_type'] == 'audio'), None)

    def chk(name, ok, detail):
        rep['checks'][name] = dict(ok=bool(ok), detail=detail); rep['ok'] &= bool(ok)
    chk('video_stream', v is not None, v and f"{v['codec_name']} {v.get('profile')} {v['pix_fmt']}")
    if v:
        num, den = map(int, v['r_frame_rate'].split('/')); fps = num / den
        chk('resolution', want_w is None or (v['width'], v['height']) == (want_w, want_h), f"{v['width']}x{v['height']}")
        chk('fps', want_fps is None or abs(fps - want_fps) < .01, f'{fps:g}')
    dur = float(pr['format']['duration']); chk('duration', want_dur is None or abs(dur - want_dur) < .1, f'{dur:.3f} s (attendu {want_dur})')
    cnt = json.loads(_run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames', '-of', 'json', str(mp4)]).stdout)
    n = int(cnt['streams'][0]['nb_read_frames']); chk('frames', want_fps is None or want_dur is None or abs(n - want_fps * want_dur) <= 1, f'{n} images décodées')
    dec = _run(['ffmpeg', '-v', 'error', '-i', str(mp4), '-f', 'null', '-']); chk('decode', not dec.stderr.strip(), dec.stderr.strip()[:200] or 'aucune erreur')
    if need_audio or a:
        chk('audio_stream', a is not None, a and f"{a['codec_name']} {a['sample_rate']} Hz {a['channels']} ch")
        if a:
            eb = _run(['ffmpeg', '-nostats', '-i', str(mp4), '-vn', '-af', 'ebur128=peak=true,silencedetect=n=-50dB:d=1.0', '-f', 'null', '-']).stderr
            lufs = re.findall(r'I:\s+(-?[\d.]+) LUFS', eb); pk = re.findall(r'Peak:\s+(-?[\d.]+) dBFS', eb); sil = re.findall(r'silence_start: ([\d.]+)', eb)
            rep['audio'] = dict(lufs=float(lufs[-1]) if lufs else None, true_peak_dbfs=float(pk[-1]) if pk else None, silences_over_1s_at=sil)
            chk('audio_level', bool(lufs) and -24 < float(lufs[-1]) < -8, f'{lufs[-1:]} LUFS, crête {pk[-1:]} dBFS')
            adur = float(a.get('duration') or dur); chk('audio_duration', abs(adur - dur) < .25, f'{adur:.3f} s')
    if v:
        W, H = 72, int(round(72 * v['height'] / v['width']))
        r = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(mp4), '-vf', f'scale={W}:{H}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True)
        fr = np.frombuffer(r.stdout, np.uint8).reshape(-1, H, W, 3).astype(np.float32)
        mean = fr.mean((1, 2, 3)); d = np.abs(np.diff(fr, axis=0)).mean((1, 2, 3)) if len(fr) > 1 else np.zeros(1)
        rep['picture'] = dict(frames=len(fr), mean_min=float(mean.min()), mean_max=float(mean.max()), diff_median=float(np.median(d)), diff_max=float(d.max()),
                              frozen_frames=int((d < 1e-3).sum()), black_frames=int((mean < 4).sum()))
        chk('not_black', (mean > 4).mean() > .9, f"{int((mean < 4).sum())} images noires sur {len(fr)}")
        chk('moving', np.median(d) > .05 and (d < 1e-3).mean() < .2, f"écart médian {np.median(d):.3f}, images figées {int((d < 1e-3).sum())}")
        rep['fingerprints'] = {str(i): hashlib.sha256(fr[i].astype(np.uint8).tobytes()).hexdigest()[:16] for i in range(0, len(fr), 12)}
    if out_json: Path(out_json).write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8')
    return rep
