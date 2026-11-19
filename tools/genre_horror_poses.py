"""python tools/genre_horror_poses.py [--out dir] [--size 300x520] [--gpu nvidia]
Sheet of the creature's poses and of the figure it replaces, on the real painter: same actor, same place (« La Dernière Pompe », shot S04, 10.4 s), a camera that holds the
whole body 6 m in front of it. Columns: legacy (a man in a hood) / still / head_tilt / loom / stoop / reach / claw / twitch.
Prints the mean pixel difference of each picture to the `still` one (a pose that changes nothing scores 0). The skin colour of the hands is NOT measured on pixels (the lit floor and panels have skin hues): it is a data test in tools/check_genre_horror.py. No audio, no film."""
import argparse, copy, json, math, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import numpy as np
from PIL import Image, ImageDraw
from hstudio.voxelgpu import render, contract as C
from hstudio.voxelgpu.films import pompe_genre_preview as P

POSES = ['still', 'head_tilt', 'loom', 'stoop', 'reach', 'claw', 'twitch']
T0 = 10.4


def diff_to(im, ref):
    """mean absolute pixel difference (0..1) between a picture and the reference one: a pose that changes nothing scores 0"""
    return float(np.abs(np.asarray(im.convert('L')).astype(np.float32) - np.asarray(ref.convert('L')).astype(np.float32)).mean() / 255.)


def build(variant, pose, size):
    c = copy.deepcopy(P.contract(variant)); st = [s for s in c['stages'] if s['id'] == 'S04'][0]; ix = {n: i for i, n in enumerate(c['actor_cols'])}; rows = st['actors']['ghost']
    if pose and pose != 'still':
        m = c['casts']['ghost']['look']['monster']; m['poses'] = [dict(name=pose, t0=st['t0'], t1=st['t1'] + 1., k=1., ramp=.01)]
    for i, r in enumerate(rows):                        # a camera that follows the figure and holds its whole body
        x, z, yaw = r[ix['x']], r[ix['z']], r[ix['yaw']]; f = (math.sin(yaw), math.cos(yaw))
        if i >= len(st['camera']): break
        st['camera'][i] = [x + f[0] * 6.2, 1.5, z + f[1] * 6.2, x, 1.05, z, 46., 0.]
    st['mood'] = None; st['env'] = {**(st.get('env') or {}), 'outside': 1}
    c['hud'] = None; c['captions'] = []; c['cards'] = []
    return c


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default=str(ROOT / 'projects' / 'genre_horror_20261029' / 'poses')); ap.add_argument('--size', default='300x520'); ap.add_argument('--gpu', default='nvidia'); a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True); w, h = map(int, a.size.split('x')); ims = []; labels = []; res = {}
    for name, variant, pose in [('legacy', 'legacy', None)] + [(p, 'monster', p) for p in POSES]:
        c = build(variant, pose, (w, h)); d = out / name; d.mkdir(exist_ok=True); C.save(c, d / 'contract.json')
        render.run_painter(d / 'contract.json', None, a.gpu, (w, h), stills=[T0], stills_dir=d, quiet=True)
        im = Image.open(d / f't_{T0:.2f}.png').convert('RGB'); ims.append(im); labels.append(name)
        res[name] = {}
    ref = ims[1]
    for n, im in zip(labels, ims): res[n]['diff_to_still'] = round(diff_to(im, ref), 5)
    S = Image.new('RGB', (w * len(ims), h)); dr = ImageDraw.Draw(S)
    for k, (im, lb) in enumerate(zip(ims, labels)): S.paste(im, (k * w, 0)); dr.rectangle((k * w, 0, k * w + 80, 12), fill=(0, 0, 0)); dr.text((k * w + 3, 1), lb, fill=(255, 255, 0))
    S.save(out / 'sheet_poses.png'); (out / 'poses.json').write_text(json.dumps(res, indent=1), encoding='utf-8'); print(out / 'sheet_poses.png'); print(json.dumps(res, indent=1))
