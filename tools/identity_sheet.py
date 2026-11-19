"""Identity sheet of a PIXEL 3D character: the face textures of every expression, V2 (24x24) next to the
expressive opt-in path (48x48), plus the same framing rendered by the engine before / after.

    python tools/identity_sheet.py                       # faces: docs/catalogue/identity_lea_faces.png
    python tools/identity_sheet.py --shot                # engine render: identity_<id>_shot_{avant,apres}.png
    python tools/identity_sheet.py --char lea --hd lea_hd --out docs/catalogue

No API, no cost: everything is drawn locally by the engine.
"""
import os, sys, argparse, json, time
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hstudio.engines.pixel3d import assets as A                     # noqa: E402
from hstudio.acting import cast as CAST                             # noqa: E402

ZOOM = 4
PAD = 4


def _look(cid):
    c = CAST.character(cid) or {}
    return dict(c.get('look') or {})


def faces_sheet(look_v2, look_hd, kinds, cols=8):
    """grid: every expression, V2 texture above, expressive texture below, same cell size"""
    cell = 48 * ZOOM // 2
    rows = (len(kinds) + cols - 1) // cols
    W = cols * (cell + PAD) + PAD
    H = rows * (2 * cell + 3 * PAD) + PAD
    sheet = Image.new('RGB', (W, H), (18, 18, 24))
    skin_v2 = tuple(look_v2.get('skin', A.SKIN)); hair_v2 = tuple(look_v2.get('hair', A.HAIR))
    skin_hd = tuple(look_hd.get('skin', A.SKIN)); hair_hd = tuple(look_hd.get('hair', A.HAIR))
    for i, kind in enumerate(kinds):
        r, c = divmod(i, cols)
        x = PAD + c * (cell + PAD); y = PAD + r * (2 * cell + 3 * PAD)
        a = A.face_tex(kind, 0, .8, .0, skin=skin_v2, hair=hair_v2)
        b = A.face_tex_hd(kind, 0, .0, skin=skin_hd, hair=hair_hd,
                          iris=tuple(look_hd.get('iris', (96, 62, 44))),
                          fringe=True, lips=tuple(look_hd['lips']) if look_hd.get('lips') else None)
        for j, arr in enumerate((a, b)):
            im = Image.fromarray(arr).convert('RGB').resize((cell, cell), Image.NEAREST)
            sheet.paste(im, (x, y + j * (cell + PAD)))
    return sheet


def shot_pair(cid_v2, cid_hd, out_dir):
    """the same medium shot, same camera, rendered with the V2 character then the expressive one"""
    from hstudio.engines.pixel3d.portrait import portrait, CACHE
    import shutil
    shutil.rmtree(CACHE, ignore_errors=True)      # the cache keys on the character file, not on the engine code
    paths = []
    for cid in (cid_v2, cid_hd):
        t0 = time.perf_counter()
        p = portrait(cid)
        dt = time.perf_counter() - t0
        if not p:
            print(f'  {cid}: no character file'); continue
        dst = os.path.join(out_dir, f'identity_{cid}_shot.png')
        Image.open(p).save(dst)
        paths.append((cid, dst, dt))
        print(f'  {cid}: {dst}  ({dt:.2f}s)')
    return paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--char', default='lea', help='V2 character id (reference)')
    ap.add_argument('--hd', default='lea_hd', help='character id with the expressive look')
    ap.add_argument('--out', default=os.path.join('docs', 'catalogue'))
    ap.add_argument('--shot', action='store_true', help='also render the engine before/after pair')
    ap.add_argument('--clip', action='store_true', help='also render a short animated GIF (both aspects)')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    lv, lh = _look(a.char), _look(a.hd)
    kinds = A.HD_KINDS
    sheet = faces_sheet(lv, lh, kinds)
    dst = os.path.join(a.out, f'identity_{a.char}_faces.png')
    sheet.save(dst)
    print(f'{len(kinds)} expressions (V2 above / expressive below) -> {dst}')
    if a.shot:
        shot_pair(a.char, a.hd, a.out)
    if a.clip:
        for asp in ('9:16', '16:9'):
            clip(a.hd, a.out, aspect=asp)




def clip(cid, out_dir, seconds=4.0, fps=12, aspect='9:16'):
    """a short animated GIF of the character through the real engine: the face changes expression, the mouth
    follows a synthetic envelope, the acting layer adds blinks and breathing. Proves the look is animated,
    not a poster. No TTS, no API: the envelope is a test signal, never a publishable voice."""
    import numpy as np
    from hstudio.pipeline import make_engine
    from hstudio.acting import cast as CAST
    c = CAST.character(cid) or {}
    faces = ['neutral', 'happy', 'surprised', 'angry', 'sad', 'joy']
    n = len(faces)
    lines, shots = [], []
    for i, fk in enumerate(faces):
        t0 = i * seconds / n; t1 = (i + 1) * seconds / n
        lines.append({'tts': '.', 'display': '', 'text': '', 'tags': [], 'dialogue': True,
                      'i': i, 'start': t0 + .02, 'end': t1 - .02, 'segs': [[t0 + .02, t1 - .02]]})
        shots.append({'lines': [i, i], 'actors': [{'id': cid, 'at': [0, 3.0], 'facing': '-z', 'face': fk,
                                                   'gaze': ['center', 'left', 'up', 'right', 'down', 'center'][i]}],
                      'camera': {'shot': 'medium', 'on': [cid], 'angle': 'three_quarter'},
                      'ui': {'hud': False, 'subs': 'off'},
                      'lights': [{'at': [.9, 2.1, 1.7], 'y': 2.1, 'color': [1, .93, .82], 'power': 1.5, 'radius': 3.5},
                                 {'at': [-1.2, 1.6, 2.0], 'y': 1.6, 'color': [.55, .5, 1], 'power': .8, 'radius': 3.}]})
    ep = {'engine_version': 2, 'style': 'pixel3d', 'default_set': 'studio', 'cast': {cid: {'ref': cid}},
          'hud': {'title': [], 'hearts': []},
          'sets': {'studio': {'type': 'room', 'rooms': [{'id': 'studio', 'origin': [0, 0], 'size': [6, 6],
                                                         'walls': 'plaster', 'floor': 'wood', 'light': 'neon',
                                                         'light_power': 1.3, 'clean': True}]}},
          'lines': {}, 'shots': shots}
    sr = 200
    t = np.arange(int(seconds * sr)) / sr
    env = (.5 + .5 * np.sin(t * 2 * np.pi * 3.1)) * (.5 + .5 * np.sin(t * 2 * np.pi * 1.7))   # test signal only
    eng = make_engine('pixel3d', ep, lines, env.astype(np.float32), seconds, aspect)
    frames = []
    for i in range(int(seconds * fps)):
        lo = eng.render_lowres(i / fps)[0]
        im = Image.fromarray(lo)
        frames.append(im.resize((im.width * 2, im.height * 2), Image.NEAREST))
    dst = os.path.join(out_dir, f'clip_{cid}_{aspect.replace(":", "x")}.gif')
    frames[0].save(dst, save_all=True, append_images=frames[1:], duration=int(1000 / fps), loop=0)
    print(f'  clip: {dst}  ({len(frames)} frames, {aspect})')
    return dst


if __name__ == '__main__':
    main()
