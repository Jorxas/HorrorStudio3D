import argparse, json, sys
from pathlib import Path
from . import contract as C


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m hstudio.voxelgpu', description='Moteur unifié : B dirige, A peint (GPU).')
    sub = ap.add_subparsers(dest='cmd')
    b = sub.add_parser('build', help='épisode -> contrat JSON'); b.add_argument('episode'); b.add_argument('out'); b.add_argument('--aspect', choices=C.ASPECTS)
    r = sub.add_parser('render', help='épisode ou contrat -> MP4'); r.add_argument('src'); r.add_argument('out'); r.add_argument('--aspect', choices=C.ASPECTS)
    r.add_argument('--gpu', default='nvidia', choices=['nvidia', 'intel', 'auto', 'software']); r.add_argument('--audio', help='WAV existant à utiliser tel quel')
    r.add_argument('--no-audio', action='store_true'); r.add_argument('--work')
    r.add_argument('--encoder', default='x264', choices=['x264', 'nvenc']); r.add_argument('--qp', type=int); r.add_argument('--fallback', action='store_true', help='sans NVIDIA : Intel/AMD puis rendu logiciel')
    v = sub.add_parser('verify', help="contrôle d'un MP4"); v.add_argument('mp4'); v.add_argument('--size'); v.add_argument('--fps', type=float); v.add_argument('--dur', type=float); v.add_argument('--json')
    k = sub.add_parser('check', help='attestation GPU + micro rendu'); k.add_argument('--gpu', default='nvidia')
    sub.add_parser('gpus', help='adaptateurs vidéo')
    a = ap.parse_args(argv)
    if a.cmd == 'build':
        from . import director
        c = director.build(json.loads(Path(a.episode).read_text(encoding='utf-8')), a.aspect); print('contrat', C.save(c, a.out)[:16], '->', a.out)
    elif a.cmd == 'render':
        from . import render
        out = Path(a.out); rep = render.render_film(a.src, out, a.work or out.with_suffix('.work'), a.gpu, a.aspect, a.audio, a.no_audio, encoder=a.encoder, qp=a.qp, fallback=a.fallback)
        print(json.dumps({'file': rep['file'], 'render_s': rep['render_s'], 'gpu': rep['attestation']['webgl']['renderer']}, ensure_ascii=False))
    elif a.cmd == 'verify':
        from . import qa
        w, h = (map(int, a.size.split('x')) if a.size else (None, None)); rep = qa.verify(a.mp4, w, h, a.fps, a.dur, out_json=a.json)
        print(json.dumps({k: (rep['checks'][k]['ok'], rep['checks'][k]['detail']) for k in rep['checks']}, indent=1, ensure_ascii=False)); sys.exit(0 if rep['ok'] else 1)
    elif a.cmd == 'gpus':
        from . import gpu
        for x in gpu.adapters(): print(x)
        print(gpu.nvidia_smi())
    elif a.cmd == 'check':
        from . import check
        sys.exit(check.run(a.gpu))
    else: ap.print_help()


if __name__ == '__main__': main()
