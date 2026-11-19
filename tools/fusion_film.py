"""python tools/fusion_film.py [--only render|qa] [--size 1080x1920] [--crf 16] [--encoder x264|nvenc]
Renders and verifies the FUSION film (hstudio/voxelgpu/films/pompe_fusion.py) to projects/fusion_finale_20261029/film/ : contract.json, video_only.mp4, master.mp4 (the SOURCE's AAC copied untouched),
leger.mp4 (540x960), report.json, frames/ (stills extracted from the FINAL mp4 at the critical moments). The checks are measured on the files:
structure + full decode (qa.verify), 1080x1920 / 30 fps / duration of the source, audio identical to the source (decoded PCM md5), cuts of the source found in ours, caption changes of the source found in
ours (the subtitle sync), black frames (ffmpeg blackdetect), the contract audit (tools/fusion_audit.py: body, vanish, feet, faces, face sync) and the vanished creature really absent from the pixels' contract.
Reuses blocking_film's measurements; nothing is published."""
import argparse, hashlib, json, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'tools'))
import blocking_film as BF, fusion_audit
from hstudio.voxelgpu import director, render, qa, contract as C
from hstudio.voxelgpu.films import pompe_fusion as F
from hstudio.remake import cuts as CUTS

OUT = ROOT / 'projects' / 'fusion_finale_20261029' / 'film'
CRITICAL = [(2.0, 's00_facade'), (12.9, 's05_vitre'), (23.6, 's09_main_vitre'), (26.35, 's11_avant'), (26.9, 's11_disparu'), (27.5, 's12_apparu'), (28.6, 's12_apres'), (31.9, 's14_faisceau'), (33.55, 's15_epaule'),
            (47.5, 's24_coups'), (52.3, 's27_porte_service'), (62.8, 's33_voiture'), (65.6, 's34_trois_metres'), (70.8, 's36_porte_du_fond'), (76.0, 's39_choix'), (90.0, 's42_fin')]
run = BF.run


def blackdetect(path):
    r = run(['ffmpeg', '-v', 'info', '-i', str(path), '-vf', 'blackdetect=d=0.2:pix_th=0.04', '-an', '-f', 'null', '-']); return [l.strip() for l in r.stderr.splitlines() if 'black_start' in l]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--only', default='all'); ap.add_argument('--size', default='1080x1920'); ap.add_argument('--crf', type=int, default=16)
    ap.add_argument('--encoder', default='x264'); ap.add_argument('--qp', type=int, default=None); a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True); W, H = map(int, a.size.split('x')); src = BF.SOURCES['pompe']; rep_f = OUT / 'report.json'
    rep = json.loads(rep_f.read_text(encoding='utf-8')) if rep_f.exists() else {}
    got = hashlib.sha256(src.read_bytes()).hexdigest(); assert got == BF.SHA['pompe'], "la source n'est plus celle qui a été vérifiée"; rep['source'] = dict(file=str(src), sha256=got)
    if a.only in ('all', 'render'):
        t0 = time.time(); ep = F.episode(); c = director.build(ep, '9:16', ep['fps']); rep['contract_sha256'] = C.save(c, OUT / 'contract.json'); rep['preflight'] = c.get('preflight'); rep['build_s'] = round(time.time() - t0, 1)
        t1 = time.time(); rep['transport'] = 'bin'; rep['transport_attempts'] = []
        for tr in ('bin', 'b64'):                 # the binary transport is 2.4x faster and byte-identical (docs/PERF_VOXELGPU.md); if it fails mid-film the older path finishes the job, and the report says so
            try:
                render.run_painter(OUT / 'contract.json', OUT / 'video_only.mp4', 'nvidia', (W, H), attest=OUT / 'attestation.json', crf=a.crf, quiet=True, encoder=a.encoder, qp=a.qp, transport=tr); rep['transport'] = tr; break
            except RuntimeError as e:
                rep['transport_attempts'].append(dict(transport=tr, error=str(e)[:400])); print('rendu', tr, 'en échec :', str(e)[:200], flush=True)
        else: raise RuntimeError("aucun transport n'a abouti : " + json.dumps(rep['transport_attempts'], ensure_ascii=False))
        rep['render_s'] = round(time.time() - t1, 1); rep['encoder'] = a.encoder; rep['attestation'] = json.loads((OUT / 'attestation.json').read_text(encoding='utf-8'))
        for cmd in (['ffmpeg', '-y', '-v', 'error', '-i', str(OUT / 'video_only.mp4'), '-i', str(src), '-map', '0:v:0', '-map', '1:a:0', '-c', 'copy', '-movflags', '+faststart', str(OUT / 'master.mp4')],
                    ['ffmpeg', '-y', '-v', 'error', '-i', str(OUT / 'master.mp4'), '-vf', 'scale=540:960:flags=lanczos', '-c:v', 'libx264', '-crf', '27', '-preset', 'slow', '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart', str(OUT / 'leger.mp4')]):
            r = run(cmd); assert r.returncode == 0, r.stderr
        rep_f.write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8')
    if a.only in ('all', 'qa'):
        m = OUT / 'master.mp4'; sp = json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(src)]).stdout)['streams']
        sv = next(s for s in sp if s['codec_type'] == 'video'); dur = float(sv['duration'])
        v = qa.verify(m, W, H, 30, dur, True, OUT / 'qa_master.json'); rep['qa_master'] = v['checks']; rep['qa_ok'] = v['ok']; rep['audio_levels'] = v.get('audio'); rep['picture'] = v.get('picture')
        pr = json.loads(run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,codec_name,width,height,r_frame_rate,nb_frames,duration,sample_rate,channels', '-of', 'json', str(m)]).stdout)['streams']; rep['ffprobe'] = pr
        rep['audio_identical_to_source'] = BF.pcm_md5(m) == BF.pcm_md5(src)
        d = CUTS.diffs(m); cuts = list(F.CUTS[1:-1]); hit = [int(max(d[max(1, c - 2):c + 3]) > 6.) for c in cuts]; rep['cuts'] = dict(n=len(cuts), detected=int(sum(hit)), missed_frames=[c for c, h in zip(cuts, hit) if not h])
        cs, cr = BF.caption_changes(src), BF.caption_changes(m); sa, sb = BF.spikes(cs), BF.spikes(cr)
        rep['captions_sync'] = dict(source_changes=len(sa), remake_changes=len(sb), source_found_in_remake_within_2_frames=round(BF.match(sa, sb), 3), remake_found_in_source_within_2_frames=round(BF.match(sb, sa), 3),
                                    source_found_in_remake_within_5_frames=round(BF.match(sa, sb, 5), 3), frames=len(cs))
        rep['black_frames'] = blackdetect(m); rep['contract_audit'] = fusion_audit.main(['--out', str(OUT / 'audit_contract.json')])
        fd = OUT / 'frames'; fd.mkdir(exist_ok=True)
        for t, name in CRITICAL: run(['ffmpeg', '-y', '-v', 'error', '-ss', f'{t:.3f}', '-i', str(m), '-frames:v', '1', str(fd / f'{name}_{t:.2f}.png')])
        rep['master'] = dict(file=str(m), bytes=m.stat().st_size, sha256=hashlib.sha256(m.read_bytes()).hexdigest())
        rep['light'] = dict(file=str(OUT / 'leger.mp4'), bytes=(OUT / 'leger.mp4').stat().st_size, sha256=hashlib.sha256((OUT / 'leger.mp4').read_bytes()).hexdigest())
        rep_f.write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8')
        print(json.dumps({k: rep[k] for k in ('qa_ok', 'audio_identical_to_source', 'cuts', 'captions_sync', 'black_frames', 'render_s') if k in rep}, ensure_ascii=False))


if __name__ == '__main__': main()
