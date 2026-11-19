"""Bounded, silent visual proof of the existing renderer; no voice/mix/provider calls.

Reuses the interrupted integration episode without touching its project. Keeps absolute
source times so existing acting continuity and camera paths survive the edit.
    python tools/si_demo_muet.py --preview
    python tools/si_demo_muet.py --render --workers 6
    python tools/si_demo_muet.py --verify
"""
import argparse
import copy
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / 'projects' / 'demo_muet_20261028'
SOURCE = ROOT / 'projects' / 'si_dernier_bus_figurants_20261026'
FPS = 30
SHOTS = (0, 2, 4, 5, 8, 9, 10, 11, 12, 16)
ENGINE = None


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def no_network(*args, **kwargs):
    raise RuntimeError('Réseau interdit pendant la démonstration muette.')


def init_engine(ep, lines, duration):
    global ENGINE
    import numpy as np
    from hstudio.pipeline import make_engine
    socket.socket = no_network
    ENGINE = make_engine('pixel3d', copy.deepcopy(ep), lines, np.zeros(10), duration, '9:16')


def draw(t):
    return ENGINE.frame(t).convert('RGB').tobytes()


def prepare():
    from hstudio.pipeline import duration_of
    ep = json.loads((SOURCE / 'episode.json').read_text(encoding='utf-8'))
    lines = json.loads((SOURCE / 'lines.json').read_text(encoding='utf-8'))
    original = copy.deepcopy(ep)
    # Existing opt-ins, applied only to this copied episode, never to global defaults.
    ep.update(body='voxel_premium', env='riche', finish='net_rapide',
              eye_aim='aim_doux', eye_smooth='saccade')
    ep['hud'] = {'show': False}
    for key in ('music', 'sfx_library', 'soundscape', 'ambience_gain', 'caption_safe'):
        ep.pop(key, None)
    # Use the existing ensemble framing to include the left-side background walkers.
    ep['shots'][0]['camera'].update(on=['lea','tom','zoe','passante','mamie'],
                                    **{'from': [-0.8, 1.0]})
    ep['shots'][2]['lighting'] = {'mood': 'cold', 'fill': 0.35}
    for shot in ep['shots']:
        shot['ui'] = {'hud': False, 'subs': 'off'}
        for key in ('audio', 'sfx', 'ambience'):
            shot.pop(key, None)
    duration = duration_of(ep, lines)
    init_engine(ep, lines, duration)
    spans = ENGINE.ctx.tl.spans
    times, edit = [], []
    for k in SHOTS:
        a, b = spans[k]
        # Entire chosen shots, sampled at the original rate, no accelerated movement.
        start, end = round(a * FPS), round(b * FPS)
        edit.append(dict(shot=k, source_start=start/FPS, source_end=end/FPS,
                         output_start=len(times)/FPS, frames=end-start,
                         camera=ep['shots'][k].get('camera')))
        times.extend(i/FPS for i in range(start, end))
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / 'episode.json', ep)
    write_json(OUT / 'lines.json', lines)
    manifest = dict(source=str(SOURCE), source_episode_sha256=hashlib.sha256(
        (SOURCE / 'episode.json').read_bytes()).hexdigest(),
        source_git=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        frames=len(times), fps=FPS, duration=len(times)/FPS, edit=edit,
        applied={k:ep.get(k) for k in ('body','env','finish','eye_aim','eye_smooth',
                 'eyeline','footing','approach','camera_face_track','clear_face','extras')},
        source_episode_unchanged=(original == json.loads((SOURCE/'episode.json').read_text(encoding='utf-8'))),
        audio='Aucun fichier audio lu ou produit. Enveloppe nulle. Encodage -an.',
        raster=[432,768], output=[1080,1920])
    write_json(OUT / 'montage.json', manifest)
    return ep, lines, duration, times, manifest


def preview(manifest):
    from PIL import Image, ImageDraw
    sheet = Image.new('RGB', (5*270, 2*510), '#151515')
    rows = []
    for i, cut in enumerate(manifest['edit']):
        t = (cut['source_start'] + cut['source_end'])/2
        t0 = time.perf_counter()
        im = ENGINE.frame(t)
        elapsed = time.perf_counter()-t0
        im.save(OUT / f"preview_plan{cut['shot']:02}.png")
        sheet.paste(im.resize((270,480)), ((i%5)*270, (i//5)*510))
        ImageDraw.Draw(sheet).text(((i%5)*270+4, (i//5)*510+484),
            f"plan {cut['shot']} | source {t:.2f}s | {elapsed:.2f}s/image", fill='white')
        rows.append(dict(shot=cut['shot'],source=t,seconds=elapsed))
        print(f"Plan {cut['shot']} : {elapsed:.2f} s/image", flush=True)
    sheet.save(OUT / 'preview.png')
    write_json(OUT / 'preview_cost.json', rows)


def render(ep, lines, duration, times, workers):
    from hstudio.ffmpeg_path import ensure
    ff = ensure()['ffmpeg']
    target = OUT / 'demo_master_1080x1920.mp4'
    if target.exists():
        raise RuntimeError('Master déjà présent : vérifier avant tout nouveau rendu.')
    partial = OUT / 'demo_master_1080x1920.part.mp4'
    if partial.exists():
        raise RuntimeError('Rendu partiel présent : conserver et inspecter avant reprise.')
    cmd = [ff,'-v','error','-n','-f','rawvideo','-pix_fmt','rgb24','-s','1080x1920',
           '-r',str(FPS),'-i','-','-an','-c:v','libx264','-preset','medium',
           '-crf','18','-pix_fmt','yuv420p','-profile:v','high','-movflags','+faststart',str(partial)]
    t0 = time.perf_counter()
    sent = 0
    with (OUT/'ffmpeg.log').open('wb') as err:
        enc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=err)
        try:
            with mp.get_context('spawn').Pool(workers, initializer=init_engine,
                                             initargs=(ep,lines,duration)) as pool:
                for sent, data in enumerate(pool.imap(draw, times, chunksize=2), 1):
                    enc.stdin.write(data)
                    if sent % FPS == 0:
                        print(f'{sent}/{len(times)} images ; {time.perf_counter()-t0:.0f} s', flush=True)
            enc.stdin.close()
            if enc.wait(timeout=120):
                raise RuntimeError('Échec ffmpeg : voir ffmpeg.log')
        except BaseException:
            if enc.poll() is None:
                enc.terminate()
                try:
                    enc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    enc.kill(); enc.wait()
            raise
    # A partial is never promoted without checking exact frames and full decode.
    verify_file(partial, len(times), (1080,1920))
    partial.rename(target)
    write_json(OUT/'render_cost.json',dict(seconds=time.perf_counter()-t0,workers=workers,frames=sent))


def verify_file(path, expected, size):
    from hstudio.ffmpeg_path import ensure
    from hstudio import mediacheck
    ff = ensure()
    info = json.loads(subprocess.check_output([ff['ffprobe'],'-v','error','-count_frames',
        '-show_streams','-show_format','-of','json',str(path)], text=True, encoding='utf-8'))
    v = [s for s in info['streams'] if s['codec_type']=='video']
    a = [s for s in info['streams'] if s['codec_type']=='audio']
    assert len(v)==1 and not a, 'Un flux vidéo unique, zéro audio requis'
    assert v[0]['codec_name']=='h264' and (v[0]['width'],v[0]['height'])==size
    assert v[0]['avg_frame_rate']=='30/1' and int(v[0]['nb_read_frames'])==expected
    check = mediacheck.describe(str(path), want=size, full=True)
    assert check['ok'] and check['decoded'], check
    return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                ffprobe=info,integrity=check)


def deliver(manifest):
    from hstudio.ffmpeg_path import ensure
    from PIL import Image, ImageDraw
    import numpy as np
    ff = ensure()['ffmpeg']
    master = OUT/'demo_master_1080x1920.mp4'
    mobile = OUT/'demo_mobile_540x960.mp4'
    if not mobile.exists():
        subprocess.run([ff,'-v','error','-n','-i',str(master),'-map','0:v:0','-an',
            '-vf','scale=540:960:flags=lanczos','-c:v','libx264','-preset','slow',
            '-b:v','1200k','-maxrate','1500k','-bufsize','3000k','-pix_fmt','yuv420p',
            '-movflags','+faststart',str(mobile)],check=True)
    report = dict(master=verify_file(master,manifest['frames'],(1080,1920)),
                  mobile=verify_file(mobile,manifest['frames'],(540,960)), frames=[])
    sheet = Image.new('RGB',(5*270,510),'#151515')
    # Street, face, walking, running, door interaction: all from the encoded master.
    for i, k in enumerate((0,2,8,9,12)):
        cut = next(c for c in manifest['edit'] if c['shot']==k)
        frame = round(cut['output_start']*FPS) + min(21,cut['frames']//2)
        t = frame/FPS
        p = OUT/f'capture_{t:06.3f}s.png'
        subprocess.run([ff,'-v','error','-y','-i',str(master),
                        '-vf',f'select=eq(n\\,{frame})','-frames:v','1',str(p)],check=True)
        im = Image.open(p).convert('RGB')
        a = np.asarray(im)
        assert a.std()>3, 'Image plate'
        sheet.paste(im.resize((270,480)),(i*270,0))
        ImageDraw.Draw(sheet).text((i*270+6,485),f'{t:.3f} s | plan {k}',fill='white')
        report['frames'].append(dict(path=str(p),frame=frame,time=t,source_shot=k,
            mean=float(a.mean()),std=float(a.std())))
    sheet.save(OUT/'captures_timecodes.png')
    write_json(OUT/'verification.json',report)
    print('Master et mobile vérifiés : décodage intégral, zéro flux audio.',flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--preview',action='store_true')
    parser.add_argument('--render',action='store_true')
    parser.add_argument('--verify',action='store_true')
    parser.add_argument('--workers',type=int,default=6)
    args = parser.parse_args()
    if args.verify and not args.render and not args.preview:
        # Verification must preserve the recorded edit and its source revision.
        deliver(json.loads((OUT/'montage.json').read_text(encoding='utf-8')))
    else:
        if args.render and any((OUT/name).exists() for name in
                ('demo_master_1080x1920.mp4','demo_master_1080x1920.part.mp4')):
            parser.error('Rendu existant : utiliser --verify, aucun fichier remplacé.')
        ep, lines, duration, times, manifest = prepare()
        print(f"Montage : {len(times)} images, {len(times)/FPS:.2f} s, {len(SHOTS)} plans.",flush=True)
        if args.preview: preview(manifest)
        if args.render: render(ep,lines,duration,times,args.workers)
        if args.render or args.verify: deliver(manifest)
