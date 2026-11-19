"""The ONE full render of « Le Dernier Noyau » (1080x1920, 30 fps, AAC) and the checks measured on the files. usage: python tools/demo_cite_render.py [--only render|qa] [--crf 16]
Rebuilds nothing: it reads projects/demo_narrative_20261029/contract.json (tools/demo_cite_build.py) and audio.wav (tools/demo_cite_audio.py). Renders with the binary transport first and falls back to
the base64 transport when it fails (it fails on this film at 1080x1920, see the report), muxes the sound (loudnorm -14 LUFS), makes the 540x960 light copy, then verifies the MASTER: structure, full decode,
resolution, fps, duration, audio level, black / frozen frames, plus the contract audit and stills extracted from the final file at the critical instants."""
import argparse, hashlib, json, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu import render, qa, contract as C
WORK = ROOT / 'projects' / 'demo_narrative_20261029'; OUT = WORK / 'film'; OUT.mkdir(exist_ok=True)
run = lambda cmd: subprocess.run(cmd, capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--only', default='all'); ap.add_argument('--crf', type=int, default=16); ap.add_argument('--try-bin', action='store_true'); a = ap.parse_args()
    c = C.load(WORK / 'contract.json'); dur = float(c['duration']); rep_f = OUT / 'report.json'; rep = json.loads(rep_f.read_text(encoding='utf-8')) if rep_f.exists() else {}
    if a.only in ('all', 'render'):
        rep['contract_sha256'] = hashlib.sha256((WORK / 'contract.json').read_bytes()).hexdigest(); t1 = time.time(); rep['transport_attempts'] = []
        for tr in (('bin', 'b64') if a.try_bin else ('b64',)):                     # the binary transport failed on this film at 1080x1920 in every attempt (clips of 14 s and 10 s, 'Failed to fetch'): the base64 path is used directly
            try:
                render.run_painter(WORK / 'contract.json', OUT / 'video_only.mp4', 'nvidia', (1080, 1920), attest=OUT / 'attestation.json', crf=a.crf, quiet=True, transport=tr); rep['transport'] = tr; break
            except RuntimeError as e:
                rep['transport_attempts'].append(dict(transport=tr, error=str(e)[:300])); print('rendu', tr, 'en échec :', str(e)[:160], flush=True); t1 = time.time()
        else: raise RuntimeError('aucun transport n\'a abouti')
        rep['render_s'] = round(time.time() - t1, 1); rep['attestation'] = json.loads((OUT / 'attestation.json').read_text(encoding='utf-8'))
        render.mux(OUT / 'video_only.mp4', WORK / 'audio.wav', OUT / 'master.mp4', dur)
        r = run(['ffmpeg', '-y', '-v', 'error', '-i', str(OUT / 'master.mp4'), '-vf', 'scale=540:960:flags=lanczos', '-c:v', 'libx264', '-crf', '27', '-preset', 'slow', '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart', str(OUT / 'leger.mp4')]); assert r.returncode == 0, r.stderr
        rep_f.write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8')
    if a.only in ('all', 'qa'):
        m = OUT / 'master.mp4'; v = qa.verify(m, 1080, 1920, 30, dur, True, OUT / 'qa_master.json'); rep['qa_master'] = v['checks']; rep['qa_ok'] = v['ok']; rep['audio_levels'] = v.get('audio'); rep['picture'] = v.get('picture')
        rep['ffprobe'] = json.loads(run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,codec_name,profile,width,height,r_frame_rate,nb_frames,duration,sample_rate,channels', '-of', 'json', str(m)]).stdout)['streams']
        r = run(['ffmpeg', '-v', 'info', '-i', str(m), '-vf', 'blackdetect=d=0.2:pix_th=0.04', '-an', '-f', 'null', '-']); rep['black_segments'] = [l.strip() for l in r.stderr.splitlines() if 'black_start' in l]
        fd = OUT / 'frames'; fd.mkdir(exist_ok=True); [p.unlink() for p in fd.glob('*.png')]
        for t, name in CRITICAL: run(['ffmpeg', '-y', '-v', 'error', '-ss', f'{t:.3f}', '-i', str(m), '-frames:v', '1', str(fd / f'{name}_{t:05.1f}.png')])
        rep['master'] = dict(file=str(m), bytes=m.stat().st_size, sha256=hashlib.sha256(m.read_bytes()).hexdigest()); lt = OUT / 'leger.mp4'; rep['light'] = dict(file=str(lt), bytes=lt.stat().st_size, sha256=hashlib.sha256(lt.read_bytes()).hexdigest())
        rep['commit'] = run(['git', 'rev-parse', 'HEAD']).stdout.strip()
        rep_f.write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8')
        print(json.dumps({k: rep[k] for k in ('qa_ok', 'audio_levels', 'black_segments', 'render_s', 'transport') if k in rep}, ensure_ascii=False))


CRITICAL = [(1.5, 'a_ville'), (5.0, 'a_course'), (10.0, 'b_dialogue'), (18.0, 'b_mallette'), (22.0, 'c_vol'), (27.0, 'c_cafe_poursuite'), (33.0, 'd_vorn'), (38.7, 'e_poing'), (41.0, 'e_epee'), (45.4, 'e_lancer'),
            (47.3, 'e_choc_lames'), (49.6, 'e_desarme'), (62.0, 'f_trottoir'), (71.0, 'f_ruelle'), (79.0, 'g_ascenseur'), (89.0, 'g_toit'), (96.5, 'h_decollage'), (101.0, 'h_montee'), (105.0, 'h_espace'),
            (109.0, 'i_lune'), (116.0, 'i_console'), (120.5, 'i_balise'), (124.0, 'i_terre'), (130.0, 'j_ville_nuit')]

if __name__ == '__main__': main()
