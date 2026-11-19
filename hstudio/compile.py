"""Long YouTube video: several 16:9 episodes joined, with chapters (in the file and as description text)."""
import os, json, subprocess, time

def duration(p):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p], capture_output=True, text=True).stdout or 0)

def fmt(t):
    t = int(round(t)); h, m, s = t // 3600, (t % 3600) // 60, t % 60
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'

def compile_long(items, out, title='', crf=17, log=print):
    """items: [(video_path, chapter_title)] (videos must be 1920x1080 30 fps; others are scaled/padded)"""
    wd = os.path.dirname(out); os.makedirs(wd, exist_ok=True)
    parts = []; chapters = []; t = 0.
    for k, (p, name) in enumerate(items):
        d = duration(p); chapters.append((t, name)); t += d; parts.append(p)
    inputs = sum([['-i', p] for p in parts], [])
    fc = ''.join(f'[{i}:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v{i}];'
                 f'[{i}:a]aresample=44100,aformat=channel_layouts=stereo[a{i}];' for i in range(len(parts)))
    # episodes are already at -14 LUFS; the limiter only catches peaks above -1 dBFS (level=0: no auto gain)
    fc += ''.join(f'[v{i}][a{i}]' for i in range(len(parts))) + f'concat=n={len(parts)}:v=1:a=1[v][ac];[ac]alimiter=limit=0.891:attack=5:release=50:level=0[a]'
    meta = os.path.join(wd, 'chapters.ffmeta')
    with open(meta, 'w', encoding='utf-8') as f:
        f.write(';FFMETADATA1\n')
        if title: f.write(f'title={title}\n')
        for k, (a, name) in enumerate(chapters):
            b = chapters[k + 1][0] if k + 1 < len(chapters) else t
            f.write(f'[CHAPTER]\nTIMEBASE=1/1000\nSTART={int(a * 1000)}\nEND={int(b * 1000)}\ntitle={name}\n')
    cmd = ['ffmpeg', '-y', '-v', 'error', *inputs, '-i', meta, '-filter_complex', fc, '-map', '[v]', '-map', '[a]', '-map_metadata', str(len(parts)),
           '-c:v', 'libx264', '-preset', 'slow', '-crf', str(crf), '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '256k', '-movflags', '+faststart', out]
    t0 = time.time(); subprocess.run(cmd, check=True)
    txt = '\n'.join(f'{fmt(a)} {name}' for a, name in chapters)
    log(f'Compilation : {fmt(t)}, {os.path.getsize(out) / 1e6:.0f} Mo ({time.time() - t0:.0f} s).')
    return out, txt
