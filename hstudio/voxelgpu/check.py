"""`python -m hstudio.voxelgpu check`: does the unified engine work on THIS machine? Builds a two-actor scene from an episode,
renders 24 frames in both formats on the requested GPU, and proves (from what WebGL reports) which GPU painted them."""
import json, tempfile
from pathlib import Path
from . import contract as C, director, render, qa

EP = {'title': 'check', 'genre': 'comedy', 'casts': {'a': {'preset': 'noe'}, 'b': {'preset': 'lina'}},
      'shots': [{'stage': 'parc', 'dur': 1.0, 'actors': [{'id': 'a', 'at': [-3, 0.4], 'facing': '+x'}, {'id': 'b', 'at': [1.5, 0.2], 'facing': '-x'}],
                 'actions': [{'who': 'a', 'do': 'walk_to', 'to': 'b', 'stop_dist': 1.3}, {'who': 'b', 'do': 'gesture', 'name': 'wave', 'at': .2, 'dur': .8}],
                 'camera': {'shot': 'two_shot', 'on': ['a', 'b']}}]}


def run(gpu='nvidia'):
    ok = True
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for asp in C.ASPECTS:
            c = director.build(EP, asp, 24); C.save(c, td / f'{asp[:1]}.json'); assert not C.validate(c)
            att = td / f'att{asp[:1]}.json'; mp4 = td / f'm{asp[:1]}.mp4'
            render.run_painter(td / f'{asp[:1]}.json', mp4, gpu, attest=att, quiet=True)
            a = json.loads(att.read_text(encoding='utf-8')); w, h = render.SIZES[asp]
            r = qa.verify(mp4, w, h, 24, 1.0, need_audio=False)
            want = {'nvidia': 'NVIDIA', 'intel': 'Intel'}.get(gpu)
            gpu_ok = want is None or want in a['webgl']['renderer']
            print(f"{asp}: {a['webgl']['renderer']} | {a['fps_render']:.1f} i/s | contrôle MP4 {'OK' if r['ok'] else r['checks']} | GPU demandé {gpu}: {'OK' if gpu_ok else 'NON'}")
            ok &= r['ok'] and gpu_ok
    print('check', 'OK' if ok else 'ÉCHEC')
    return 0 if ok else 1
