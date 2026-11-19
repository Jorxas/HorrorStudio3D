"""Non-regression of the VOXELGPU performance path.   python tools/check_voxelgpu_perf.py [--gpu nvidia] [--nvenc]

Real GPU rendering of a small scene (the MINI scene of check_voxelgpu.py), nothing synthetic:
  1. the fast binary transport and the previous base64 transport give the same RAW PIXELS (sha256 of every frame);
  2. with x264 they give the same MP4 bytes (so a delivered master does not change with the new path);
  3. the attestation says the requested adapter really rendered (WebGL renderer string);
  4. ffmpeg dying in the middle of a render stops the renderer with an error instead of hanging;
  5. (--nvenc) h264_nvenc: duration/frames/size are right and the picture stays close to the x264 one (PSNR >= 40 dB, SSIM >= 0.95).
Exit code 0 only if everything passes."""
import argparse, hashlib, json, re, subprocess, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu import contract as C, director, render, gpu as G
from tools.check_voxelgpu import MINI

RES = []


def check(name, ok, detail=''):
    RES.append(bool(ok)); print(('OK    ' if ok else 'ECHEC ') + name + (f' : {detail}' if detail else ''), flush=True)


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def metric(a, b):
    r = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(a), '-i', str(b), '-lavfi', '[0:v][1:v]ssim;[0:v][1:v]psnr', '-f', 'null', '-'], capture_output=True, text=True).stderr
    return float(re.search(r'SSIM.*All:([0-9.]+)', r).group(1)), float(re.search(r'average:([0-9.]+)', r).group(1))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--gpu', default='nvidia'); ap.add_argument('--nvenc', action='store_true'); a = ap.parse_args()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td); c = director.build(MINI, '9:16', 24); C.save(c, td / 'c.json'); size = (540, 960); rng = '0.5:1.25,4.0:4.5'      # 30 frames over two shots
        out = {}
        for tr in ('b64', 'bin'):
            render.run_painter(td / 'c.json', td / f'{tr}.mp4', a.gpu, size, attest=td / f'{tr}.att.json', quiet=True, transport=tr, ranges=rng, hash_file=td / f'{tr}.h')
            out[tr] = json.loads((td / f'{tr}.att.json').read_text(encoding='utf-8'))
        hb, hn = (td / 'b64.h').read_text(), (td / 'bin.h').read_text()
        check('pixels bruts : transport binaire == ancien transport (chaque image)', hb == hn and hb.count('\n') == 30, f'{hb.count(chr(10))} images comparées')
        check('MP4 x264 : octets identiques entre les deux transports', sha(td / 'b64.mp4') == sha(td / 'bin.mp4'), sha(td / 'bin.mp4')[:16])
        want = {'nvidia': 'NVIDIA', 'intel': 'Intel'}.get(a.gpu, '')
        check('attestation : le GPU demandé a bien rendu', want in out['bin']['webgl']['renderer'], out['bin']['webgl']['renderer'])
        check('attestation : transport et encodeur enregistrés', out['bin'].get('transport') == 'bin' and out['bin'].get('encoder') == 'x264')
        # ffmpeg killed mid-render: the renderer must fail, not hang. A bad encoder argument makes ffmpeg exit at once.
        t0 = time.time(); r = subprocess.run(['node', str(render.JS / 'render_unified.js'), '--contract', str(td / 'c.json'), '--w', '540', '--h', '960', '--gpu', 'software', '--ranges', '0:1', '--preset', 'no_such_preset', '--out', str(td / 'bad.mp4'), '--quiet'],
                           env=render.node_env(), cwd=str(render.JS), capture_output=True, text=True, timeout=240)
        check('ffmpeg en échec : le rendu s\'arrête avec une erreur (pas de blocage)', r.returncode != 0 and time.time() - t0 < 200, f'code {r.returncode} en {time.time() - t0:.0f} s')
        if a.nvenc:
            if not render.encoder_ok('nvenc'): check('NVENC disponible', False, 'h264_nvenc ne démarre pas')
            else:
                render.run_painter(td / 'c.json', td / 'nv.mp4', a.gpu, size, attest=td / 'nv.att.json', quiet=True, encoder='nvenc', ranges=rng)
                p = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_frames', '-show_entries', 'stream=nb_read_frames,width,height,codec_name', '-of', 'json', str(td / 'nv.mp4')], capture_output=True, text=True).stdout)['streams'][0]
                check('NVENC : 30 images, 540x960, h264', p['nb_read_frames'] == '30' and (p['width'], p['height']) == (540, 960) and p['codec_name'] == 'h264', str(p))
                s, ps = metric(td / 'nv.mp4', td / 'bin.mp4'); check('NVENC : image proche de x264 (SSIM >= 0.95, PSNR >= 40 dB)', s >= .95 and ps >= 40, f'SSIM {s:.4f}, PSNR {ps:.1f} dB')
    print(f'\n{sum(RES)}/{len(RES)} contrôles passés'); sys.exit(0 if all(RES) else 1)


if __name__ == '__main__': main()
