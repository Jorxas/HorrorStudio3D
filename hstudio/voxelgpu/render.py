"""Render a contract with the voxel painter on the GPU, add the sound, mux. No intermediate image is kept (pixels go from
WebGL to ffmpeg), so there is no stale-frame resume: a render either completes or leaves nothing usable behind."""
import json, os, shutil, subprocess, sys, time
from pathlib import Path
from . import contract as C, gpu as G

ROOT = Path(__file__).resolve().parents[2]
JS = ROOT / 'voxelgpu_js'
A_MODULES = Path(r'C:\Users\demo\Videos\moteur_voxel\node_modules')       # playwright is READ from engine A's folder when not installed here
SIZES = {'9:16': (720, 1280), '16:9': (1280, 720)}


def node_env():
    env = dict(os.environ)
    if not (JS / 'node_modules').exists() and A_MODULES.exists(): env['NODE_PATH'] = str(A_MODULES)
    return env


_ENC_OK = {}


def encoder_ok(encoder):
    """'x264' is always usable; 'nvenc' only if ffmpeg lists h264_nvenc AND a 1-frame test encode starts (driver / GPU present)"""
    e = (encoder or 'x264').lower()
    if e != 'nvenc': return True
    if e not in _ENC_OK:
        r = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=256x256:d=0.1', '-c:v', 'h264_nvenc', '-frames:v', '1', '-f', 'null', '-'], capture_output=True, text=True)
        _ENC_OK[e] = r.returncode == 0
    return _ENC_OK[e]


def run_painter(contract_path, out_mp4=None, gpu='nvidia', size=None, start=None, end=None, stills=None, stills_dir=None, attest=None, crf=14, preset=None, quiet=False,
                encoder='x264', qp=None, transport='bin', inflight=None, ranges=None, hash_file=None, profile=None, threads=None, fallback=False):
    """transport 'bin' (default) streams raw frames page -> local server -> ffmpeg; 'b64' is the previous slower path (kept for A/B).
    encoder 'x264' (default, CPU, the reference) or 'nvenc' (h264_nvenc on the GPU; falls back to x264 when unavailable).
    fallback=True: when no NVIDIA adapter is found, use Intel/AMD, then the software renderer, instead of stopping."""
    if fallback:
        try: flag, luid, ad = G.pick(gpu)
        except SystemExit:
            flag, luid, ad = G.pick_any()
            print(f'GPU « {gpu} » absent : repli sur « {flag} »')
    else: flag, luid, ad = G.pick(gpu)
    if (encoder or 'x264').lower() == 'nvenc' and not encoder_ok(encoder):
        print('NVENC indisponible : repli sur libx264'); encoder = 'x264'
    if preset is None: preset = 'p7' if (encoder or '').lower() == 'nvenc' else 'medium'
    contract_path = Path(contract_path).resolve(); out_mp4 = Path(out_mp4).resolve() if out_mp4 else None; attest = Path(attest).resolve() if attest else None
    stills_dir = Path(stills_dir).resolve() if stills_dir else None       # the painter runs from voxelgpu_js/: no relative path may reach it
    c = C.load(contract_path); w, h = size or SIZES[c['aspect']]
    cmd = ['node', str(JS / 'render_unified.js'), '--contract', str(contract_path), '--w', str(w), '--h', str(h), '--gpu', flag, '--crf', str(crf), '--preset', preset, '--transport', transport, '--encoder', encoder]
    if qp is not None: cmd += ['--qp', str(qp)]
    if inflight: cmd += ['--inflight', str(inflight)]
    if threads: cmd += ['--threads', str(threads)]
    if ranges: cmd += ['--ranges', ranges]
    if hash_file: cmd += ['--hash', str(Path(hash_file).resolve())]
    if profile: cmd += ['--profile', str(profile)]
    if luid: cmd += ['--luid', luid]
    if out_mp4: cmd += ['--out', str(out_mp4)]
    if start is not None: cmd += ['--start', str(start)]
    if end is not None: cmd += ['--end', str(end)]
    if stills: cmd += ['--stills', ','.join(str(s) for s in stills), '--stills-dir', str(stills_dir or '.')]
    if attest: cmd += ['--attest', str(attest)]
    if quiet: cmd += ['--quiet']
    r = subprocess.run(cmd, env=node_env(), cwd=str(JS), text=True, capture_output=True)
    sys.stdout.write(r.stdout[-1500:])
    if r.returncode: raise RuntimeError(f'rendu GPU en échec ({r.returncode}) : {r.stderr[-800:]}')
    return ad


def mux(video, wav, out, duration, lufs=-14.):
    """video + sound -> final MP4 (H.264 copied, AAC 48 kHz stereo, loudness normalised, exactly the film's duration)"""
    cmd = ['ffmpeg', '-y', '-v', 'error', '-i', str(video), '-i', str(wav), '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy',
           '-af', f'loudnorm=I={lufs}:TP=-1.5:LRA=11,aresample=48000,apad', '-c:a', 'aac', '-b:a', '256k', '-ac', '2', '-t', f'{duration:.3f}', '-movflags', '+faststart', str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: raise RuntimeError('mux en échec : ' + r.stderr[-600:])


def render_film(episode_or_contract, out_mp4, workdir, gpu='nvidia', aspect=None, wav=None, no_audio=False, size=None, crf=14, preset=None, quiet=False, encoder='x264', qp=None, fallback=False):
    """episode (B DSL + painter keys) or contract -> final MP4 + sidecar JSON (attestation, hashes, timings)"""
    from . import director, audio
    work = Path(workdir); work.mkdir(parents=True, exist_ok=True); out_mp4 = Path(out_mp4)
    ep = episode_or_contract if isinstance(episode_or_contract, dict) else json.loads(Path(episode_or_contract).read_text(encoding='utf-8'))
    t0 = time.time()
    c = ep if ep.get('schema') == C.SCHEMA else director.build(ep, aspect, ep.get('fps'))
    dig = C.save(c, work / 'contract.json'); t_build = time.time() - t0
    video = work / 'video_only.mp4'; att = work / 'attestation.json'
    ad = run_painter(work / 'contract.json', video, gpu, size, attest=att, crf=crf, preset=preset, quiet=quiet, encoder=encoder, qp=qp, fallback=fallback)
    t_render = time.time() - t0 - t_build
    a = c.get('audio') or {}
    if not no_audio and (wav or a):
        wavp = Path(wav) if wav else Path(audio.compose(c, work / 'audio.wav'))
        mux(video, wavp, out_mp4, c['duration'])
    else: shutil.copyfile(video, out_mp4)
    rep = dict(file=str(out_mp4), contract_sha256=dig, build_s=round(t_build, 2), render_s=round(t_render, 2), attestation=json.loads(att.read_text(encoding='utf-8')), adapter_requested=ad)
    out_mp4.with_suffix('.render.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8')
    return rep
