"""python tools/blocking_film.py pompe_continuite [--size 1080x1920] [--gpu nvidia] [--only render|qa|page] [--crf 16]
The blocked film (hstudio/voxelgpu/films/<film>.py, same cuts and same source audio as the first remake) to the delivered files, under projects/pompe_continuite_20261029/film/ :

  contract.json        what the painter reads (hs-unified/1), with its sha256 in report.json
  video_only.mp4       the 3D render (GPU, adapter attested in attestation.json)
  master.mp4           video_only + the SOURCE's AAC track copied untouched (no re-encode, no added music)
  leger.mp4            540x960 H.264 + the same AAC track, for sharing
  report.json          checks measured on the files: structure, full decode, frames, duration, audio identity (decoded PCM md5 == source),
                       cut positions vs the source's, caption timing correlation, brightness, render time
  comparaison/         sheets (source | remake at the middle of each shot) and the local side-by-side page

Nothing is published and no network is touched. The source video is only read."""
import argparse, hashlib, html, importlib, json, shutil, subprocess, sys, time
from pathlib import Path
import numpy as np, cv2
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu import director, render, qa, contract as C
from hstudio.remake import cuts as CUTS, sheets
from PIL import Image

BASE = ROOT / 'projects' / 'remakes_voxelgpu_20261029'
SOURCES = {'pompe': BASE / 'source' / 'pompe' / 'LA_DERNIERE_POMPE_partie1_sans_miniature.mp4', 'sol': BASE / 'source' / 'sol' / 'NE_TOUCHE_PAS_LE_SOL_partie4.mp4'}
SHA = {'pompe': '4880b9bfa1b69f2451c7c94711b10917b1761a5eca8cd05bafc8d15d026856b7', 'sol': '4bfe08170821c7068f1e24a78da6983a779165c00c13b2b46ebd82de44c760c4'}


def run(cmd): return subprocess.run(cmd, capture_output=True, text=True)


def pcm_md5(p):
    r = run(['ffmpeg', '-v', 'error', '-i', str(p), '-map', '0:a:0', '-f', 'md5', '-']); return r.stdout.strip()


def caption_changes(path, w=270, h=480):
    """per-frame change of the caption STROKE mask (white or red fill, thin strokes only) in the caption band: a caption appearing, changing or going away is a spike"""
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', str(path), '-vf', f'scale={w}:{h}:flags=area', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    n = w * h * 3; y0, y1 = int(.40 * h), int(.56 * h); k = 9; ker, ker2 = np.ones((k, k), np.uint8), np.ones((k + 4, k + 4), np.uint8); prev = None; out = [0.]
    def strokes(m):
        u = m.astype(np.uint8); return m & (cv2.dilate(cv2.erode(u, ker), ker2) == 0)
    while True:
        b = p.stdout.read(n)
        if len(b) < n: break
        a = np.frombuffer(b, np.uint8).reshape(h, w, 3)[y0:y1].astype(int); r, g, bl = a[..., 0], a[..., 1], a[..., 2]
        m = strokes((r > 215) & (g > 215) & (bl > 215)) | strokes((r > 170) & (g < 110) & (bl < 110))
        if prev is not None: out.append(float((m ^ prev).sum()))
        prev = m
    p.wait(); return np.array(out, float)


def spikes(x, k=6.):
    """frames where the change is well above the typical change (median of the non-zero values)"""
    nz = x[x > 0]; th = max(40., k * float(np.median(nz))) if len(nz) else 1e9
    return [i for i in range(1, len(x) - 1) if x[i] >= th and x[i] >= x[i - 1] and x[i] > x[i + 1]]


def match(a, b, tol=2):
    """share of the frames in a that have a frame of b within +-tol"""
    return sum(any(abs(i - j) <= tol for j in b) for i in a) / max(1, len(a))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('film'); ap.add_argument('--size', default='1080x1920'); ap.add_argument('--gpu', default='nvidia'); ap.add_argument('--crf', type=int, default=16)
    ap.add_argument('--only', default='all'); ap.add_argument('--preset', default='medium'); a = ap.parse_args()
    mod = importlib.import_module(f'hstudio.voxelgpu.films.{a.film}'); ep = mod.episode(); src = SOURCES['pompe']
    out = ROOT / 'projects' / 'pompe_continuite_20261029' / 'film'; out.mkdir(parents=True, exist_ok=True); W, H = map(int, a.size.split('x')); rep_f = out / 'report.json'
    rep = json.loads(rep_f.read_text(encoding='utf-8')) if rep_f.exists() else {}
    got = hashlib.sha256(src.read_bytes()).hexdigest(); assert got == SHA['pompe'], 'la source n\'est plus celle qui a été vérifiée'
    rep['source'] = dict(file=str(src), sha256=got)
    if a.only in ('all', 'render'):
        t0 = time.time(); c = director.build(ep, '9:16', ep['fps']); rep['contract_sha256'] = C.save(c, out / 'contract.json'); rep['preflight'] = c.get('preflight'); rep['build_s'] = round(time.time() - t0, 1)
        t1 = time.time(); render.run_painter(out / 'contract.json', out / 'video_only.mp4', a.gpu, (W, H), attest=out / 'attestation.json', crf=a.crf, preset=a.preset, quiet=True); rep['render_s'] = round(time.time() - t1, 1)
        rep['attestation'] = json.loads((out / 'attestation.json').read_text(encoding='utf-8'))
        r = run(['ffmpeg', '-y', '-v', 'error', '-i', str(out / 'video_only.mp4'), '-i', str(src), '-map', '0:v:0', '-map', '1:a:0', '-c', 'copy', '-movflags', '+faststart', str(out / 'master.mp4')]); assert r.returncode == 0, r.stderr
        r = run(['ffmpeg', '-y', '-v', 'error', '-i', str(out / 'master.mp4'), '-vf', 'scale=540:960:flags=lanczos', '-c:v', 'libx264', '-crf', '27', '-preset', 'slow', '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart', str(out / 'leger.mp4')]); assert r.returncode == 0, r.stderr
        rep_f.write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8')
    if a.only in ('all', 'qa'):
        m = out / 'master.mp4'; sp = json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(src)]).stdout)['streams']
        sv = next(s for s in sp if s['codec_type'] == 'video'); nsrc = int(sv['nb_frames']); dur = float(sv['duration'])
        v = qa.verify(m, W, H, 30, dur, True, out / 'qa_master.json'); rep['qa_master'] = {k: v['checks'][k] for k in v['checks']}; rep['qa_ok'] = v['ok']; rep['audio_levels'] = v.get('audio'); rep['picture'] = v.get('picture')
        rep['frames_expected_from_source'] = nsrc; rep['audio_pcm_md5_master'] = pcm_md5(m); rep['audio_pcm_md5_source'] = pcm_md5(src); rep['audio_identical_to_source'] = rep['audio_pcm_md5_master'] == rep['audio_pcm_md5_source']
        am = json.loads(run(['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=codec_name,sample_rate,channels,duration,bit_rate', '-of', 'json', str(m)]).stdout)['streams'][0]; rep['audio_master'] = am
        # cuts: the source's cut frames must show a jump in ours
        d = CUTS.diffs(m); cuts = [c for c in mod.CUTS[1:-1]]; hit = [int(max(d[max(1, c - 2):c + 3]) > 6.) for c in cuts]; rep['cuts'] = dict(n=len(cuts), detected=int(sum(hit)), missed_frames=[c for c, h in zip(cuts, hit) if not h])
        # captions: on/off series of the caption band, source vs remake
        cs, cr = caption_changes(src), caption_changes(m); sa, sb = spikes(cs), spikes(cr); rep['captions_sync'] = dict(source_changes=len(sa), remake_changes=len(sb), share_of_source_changes_found_in_remake_within_2_frames=round(match(sa, sb), 3), share_of_remake_changes_found_in_source_within_2_frames=round(match(sb, sa), 3), within_5_frames_source_in_remake=round(match(sa, sb, 5), 3), frames=len(cs))
        rep['light'] = dict(file=str(out / 'leger.mp4'), bytes=(out / 'leger.mp4').stat().st_size, sha256=hashlib.sha256((out / 'leger.mp4').read_bytes()).hexdigest())
        rep['master'] = dict(file=str(m), bytes=m.stat().st_size, sha256=hashlib.sha256(m.read_bytes()).hexdigest())
        rep_f.write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8')
        print(json.dumps({k: rep[k] for k in ('qa_ok', 'audio_identical_to_source', 'cuts', 'captions_sync', 'render_s') if k in rep}, ensure_ascii=False))
    if a.only in ('all', 'page'): page(a.film, mod, out, src, rep)


def page(film, mod, out, src, rep):
    cmpd = out / 'comparaison'; cmpd.mkdir(exist_ok=True); m = out / 'master.mp4'
    mids = [(mod.CUTS[i] + mod.CUTS[i + 1]) // 2 for i in range(len(mod.CUTS) - 1)]
    s_im = sheets.grab(src, mids, 180, 320); r_im = sheets.grab(m, mids, 180, 320); cols = 6
    for part in range(0, len(mids), 18):
        sel = mids[part:part + 18]; S = Image.new('RGB', (cols * 2 * 182, ((len(sel) + cols - 1) // cols) * 342), (16, 16, 16))
        for k, f in enumerate(sel):
            x, y = (k % cols) * 364, (k // cols) * 342; S.paste(s_im[f], (x, y + 20)); S.paste(r_im[f], (x + 182, y + 20))
            from PIL import ImageDraw; ImageDraw.Draw(S).text((x + 4, y + 4), f'S{part + k:02d} {f / 30:.1f}s  source | remake', fill=(255, 255, 0))
        S.save(cmpd / f'planches_{part // 18}.png')
    shutil.copyfile(m, cmpd / 'remake_master.mp4') if False else None
    for name, p in (('source.mp4', src), ('remake_leger.mp4', out / 'leger.mp4')):
        if not (cmpd / name).exists() or (cmpd / name).stat().st_size != p.stat().st_size: shutil.copyfile(p, cmpd / name)
    q = rep.get('qa_master', {}); rows = ''.join(f"<tr><td>{html.escape(k)}</td><td>{'OK' if v['ok'] else 'ÉCHEC'}</td><td>{html.escape(str(v['detail']))}</td></tr>" for k, v in q.items())
    sheets_html = ''.join(f'<img src="planches_{i}.png" style="max-width:100%">' for i in range((len(mids) + 17) // 18))
    (cmpd / 'index.html').write_text(f"""<!doctype html><meta charset="utf-8"><title>{html.escape(mod.__doc__.splitlines()[0])}</title>
<style>body{{background:#111;color:#ddd;font:14px system-ui;margin:16px}}video{{width:300px;background:#000}}table{{border-collapse:collapse}}td{{border:1px solid #444;padding:3px 8px}}.row{{display:flex;gap:12px}}button{{padding:6px 14px}}</style>
<h2>{html.escape(mod.__doc__.splitlines()[0])}</h2><p>Gauche : la vidéo d'origine (fournie, non modifiée). Droite : le remake 3D VOXELGPU (images rendues par le moteur unifié sur GPU, piste audio de l'origine copiée telle quelle).
Les deux lecteurs sont synchronisés. Les différences visuelles sont documentées dans <code>docs/REMAKES_VOXELGPU.md</code>.</p>
<div class="row"><div><b>Origine</b><br><video id="a" src="source.mp4" controls playsinline></video></div><div><b>Remake</b><br><video id="b" src="remake_leger.mp4" controls playsinline></video></div></div>
<p><button onclick="go()">▶ lecture synchronisée</button> <button onclick="a.pause();b.pause()">⏸</button> <button onclick="a.currentTime=b.currentTime=0">⏮</button> <span id="t"></span></p>
<script>const a=document.getElementById('a'),b=document.getElementById('b');b.muted=true;function go(){{b.currentTime=a.currentTime;a.play();b.play()}}
a.addEventListener('timeupdate',()=>{{if(Math.abs(a.currentTime-b.currentTime)>.12)b.currentTime=a.currentTime;document.getElementById('t').textContent=a.currentTime.toFixed(2)+' s'}});a.addEventListener('seeked',()=>b.currentTime=a.currentTime);</script>
<h3>Contrôles mesurés sur le fichier master</h3><table>{rows}</table>
<p>Audio identique à la source (PCM décodé, md5) : <b>{rep.get('audio_identical_to_source')}</b> · coupes retrouvées : {rep.get('cuts', {}).get('detected')}/{rep.get('cuts', {}).get('n')} · changements de légende de la source retrouvés dans le remake à ±2 images : {rep.get('captions_sync', {}).get('share_of_source_changes_found_in_remake_within_2_frames')} · rendu {rep.get('render_s')} s</p>
<h3>Planches : un plan sur deux colonnes (origine | remake)</h3>{sheets_html}""", encoding='utf-8')
    print('page :', cmpd / 'index.html')


if __name__ == '__main__': main()
