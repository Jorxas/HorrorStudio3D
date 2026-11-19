"""Before / after of the environment variation pass, at strictly identical framing, plus the render cost.

  python tools/variety_sheet.py                      # the full sheet + measures in docs/world_variety/
  python tools/variety_sheet.py --only bedroom       # one case
  python tools/variety_sheet.py --aspect 9:16

For every case the same camera (same position, same target, same lens) renders the shipped place and the same place
with its "variation" key, so the two images differ only by what the pass added. The numbers (boxes, lights, seconds
per frame, ratio) are written next to the images in `mesures.json`.

Cases:
  bedroom / living_room / basement / kitchen   a shipped room, plain vs dressed (the owner's complaint)
  corridor / stairwell / parking / alley       the four new archetypes, against the nearest shipped place
"""
import argparse, json, os, sys, time
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from PIL import Image, ImageDraw, ImageFont
from hstudio.paths import FONT_MONTSERRAT

OUT = os.path.join(ROOT, 'docs', 'world_variety')

# name -> (before spec, after spec, camera (pos, look, fov), caption)
CASES = {
    'bedroom': (
        {'type': 'bedroom'}, {'type': 'bedroom', 'variation': {'mood': 'haunted', 'seed': 4}},
        ((1.55, 1.62, 0.55), (-1.0, 1.20, 4.3), 66),
        'CHAMBRE : recette livree / variation "haunted"'),
    'living_room': (
        {'type': 'living_room'}, {'type': 'living_room', 'variation': {'mood': 'lived_in', 'seed': 7}},
        ((1.95, 1.64, 0.55), (-1.2, 1.15, 4.6), 68),
        'SALON : recette livree / variation "lived_in"'),
    'basement': (
        {'type': 'basement'}, {'type': 'basement', 'variation': {'mood': 'abandoned', 'seed': 2}},
        ((2.45, 1.58, 0.6), (-1.6, 1.05, 5.8), 70),
        'CAVE : recette livree / variation "abandoned"'),
    'kitchen': (
        {'type': 'kitchen'}, {'type': 'kitchen', 'variation': {'mood': 'ransacked', 'seed': 5}},
        ((1.55, 1.62, 0.55), (-1.1, 1.15, 4.4), 66),
        'CUISINE : recette livree / variation "ransacked"'),
    'corridor': (
        {'type': 'apartment'}, {'type': 'corridor', 'seed': 3},
        ((0.0, 1.60, 0.6), (0.0, 1.35, 12.0), 58),
        'COULOIR : prefab "apartment" / nouvel archetype "corridor"'),
    'stairwell': (
        {'type': 'basement'}, {'type': 'stairwell', 'seed': 2},
        ((0.30, 1.66, 0.45), (-1.05, 2.20, 4.30), 74),
        'ESCALIER : "basement" (le plus proche livre) / nouvel archetype "stairwell"'),
    'parking': (
        {'type': 'basement', 'dirty': True}, {'type': 'parking', 'seed': 6},
        ((0.0, 1.62, 0.9), (0.6, 1.15, 12.0), 68),
        'PARKING : "basement" / nouvel archetype "parking"'),
    'alley': (
        {'type': 'city_street', 'sky': 'night'}, {'type': 'alley', 'seed': 4},
        ((0.0, 1.60, 0.8), (0.3, 1.5, 13.0), 62),
        'EXTERIEUR : "city_street" nuit / nouvel archetype "alley" (ruelle)'),
}


def look_at(pos, target):
    import math
    dx, dy, dz = (target[i] - pos[i] for i in range(3))
    yaw = math.atan2(dx, dz)
    pitch = math.atan2(dy, math.hypot(dx, dz))
    return yaw, pitch


def prepare(spec, cam, aspect):
    """(scene, camera tuple, lights, builder) ready to render"""
    from hstudio.engines.pixel3d import r3d, sets
    r3d.configure(aspect)
    st = sets.make_set(spec.get('type', 'room'), spec)
    st.build()
    pos, target, fov = cam
    yaw, pitch = look_at(pos, target)
    lights = st.lights({}, 0., 0., np.array(pos, np.float32))
    sc = st.scene({}, 0., 0.)
    return sc, (pos, yaw, pitch, 0., float(fov)), lights, st   # fov in degrees, like build_frame / cam_dirs


def grade(rgb):
    """the same grade as render.render_lowres, minus the per-shot effects"""
    from hstudio.engines.pixel3d import r3d, render as RD
    img = r3d.glow(rgb)
    lum = (img * np.array([.3, .59, .11], np.float32)).sum(-1, keepdims=True)
    img = lum + (img - lum) * RD.SAT
    img = img * RD.EXPO * np.array([1.0, .98, .9], np.float32) + np.array([.014, .012, .010], np.float32)
    return Image.fromarray(r3d.pixelate(np.clip(img, 0, None) ** 1.08, gamma=1.0))


def ab(before, after, cam, aspect, rounds=4):
    """render both, then time them interleaved so thermal drift hits the two sides equally; keep the best round"""
    from hstudio.engines.pixel3d import r3d
    A = prepare(before, cam, aspect)
    B = prepare(after, cam, aspect)
    ia = grade(r3d.render(A[0], A[1], A[2]))
    ib = grade(r3d.render(B[0], B[1], B[2]))
    ta, tb = [], []
    for _ in range(rounds):
        t0 = time.perf_counter(); r3d.render(A[0], A[1], A[2]); ta.append(time.perf_counter() - t0)
        t0 = time.perf_counter(); r3d.render(B[0], B[1], B[2]); tb.append(time.perf_counter() - t0)
    return (ia, len(A[0].boxes), len(getattr(A[3], 'light_defs', []) or A[2]), min(ta),
            ib, len(B[0].boxes), len(getattr(B[3], 'light_defs', []) or B[2]), min(tb))


def seeds_sheet(name, mood, seeds, aspect, scale):
    """the same place, the same camera, four seeds: proof that two bedrooms no longer look like one bedroom"""
    from hstudio.engines.pixel3d import r3d
    cam = CASES[name][2]
    ims = []
    for sd in seeds:
        spec = {'type': name} if sd is None else {'type': name, 'variation': {'mood': mood, 'seed': sd}}
        sc, c, L, st = prepare(spec, cam, aspect)
        ims.append((grade(r3d.render(sc, c, L)), 'recette livree' if sd is None else f'variation seed {sd}',
                    len(sc.boxes)))
    w, h = ims[0][0].size
    W_, H_ = w * scale, h * scale
    head, pad = 30, 8
    sheet = Image.new('RGB', (pad + len(ims) * (W_ + pad), head + H_ + pad), (14, 16, 22))
    d = ImageDraw.Draw(sheet)
    try:
        f = ImageFont.truetype(FONT_MONTSERRAT, 18)
    except Exception:
        f = None
    d.text((pad, 6), f'{name} / mood "{mood}" — meme cadrage, graines differentes', fill=(232, 228, 214), font=f)
    for i, (im, lab, nb) in enumerate(ims):
        x = pad + i * (W_ + pad)
        sheet.paste(im.resize((W_, H_), Image.NEAREST), (x, head))
        d.text((x + 6, head + 4), f'{lab}  ({nb} boites)',
               fill=(190, 200, 220) if i == 0 else (255, 220, 120), font=f)
    out = os.path.join(OUT, f'graines_{name}.png')
    sheet.save(out)
    print(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--aspect', default='16:9')
    ap.add_argument('--only', default='')
    ap.add_argument('--scale', type=int, default=3)
    ap.add_argument('--seeds', default='', help='ex. bedroom:haunted or living_room:lived_in')
    a = ap.parse_args()
    if a.seeds:
        nm, _, md = a.seeds.partition(':')
        os.makedirs(OUT, exist_ok=True)
        seeds_sheet(nm, md or 'lived_in', [None, 1, 4, 9], a.aspect, a.scale)
        return
    names = [a.only] if a.only else list(CASES)
    os.makedirs(OUT, exist_ok=True)
    rows = []
    measures = {}
    for n in names:
        before, after, cam, cap = CASES[n]
        ib, nb, lb, tb, ia, na, la, ta = ab(before, after, cam, a.aspect)
        rows.append((cap, ib, ia, nb, na, tb, ta))
        measures[n] = {'before': {'spec': before, 'boxes': nb, 'lights': lb, 's_per_frame': round(tb, 4)},
                       'after': {'spec': after, 'boxes': na, 'lights': la, 's_per_frame': round(ta, 4)},
                       'ratio_boxes': round(na / max(1, nb), 2), 'ratio_time': round(ta / max(1e-6, tb), 2),
                       'camera': {'pos': cam[0], 'look': cam[1], 'fov': cam[2]}, 'aspect': a.aspect}
        print(f'{n:12s} boxes {nb:4d} -> {na:4d} (x{na / max(1, nb):.2f})   '
              f'{tb * 1000:6.1f} ms -> {ta * 1000:6.1f} ms (x{ta / max(1e-6, tb):.2f})', flush=True)
    k = a.scale
    w, h = rows[0][1].size
    W_, H_ = w * k, h * k
    head, pad = 34, 8
    sheet = Image.new('RGB', (pad + 2 * (W_ + pad), pad + len(rows) * (head + H_ + pad)), (14, 16, 22))
    d = ImageDraw.Draw(sheet)
    try:
        f = ImageFont.truetype(FONT_MONTSERRAT, 20)
        fs = ImageFont.truetype(FONT_MONTSERRAT, 15)
    except Exception:
        f = fs = None
    for r, (cap, ib, ia, nb, na, tb, ta) in enumerate(rows):
        y = pad + r * (head + H_ + pad)
        d.text((pad, y + 4), cap, fill=(232, 228, 214), font=f)
        for c, (im, nbx, t) in enumerate(((ib, nb, tb), (ia, na, ta))):
            x = pad + c * (W_ + pad)
            sheet.paste(im.resize((W_, H_), Image.NEAREST), (x, y + head))
            d.text((x + 6, y + head + 4), f'{"AVANT" if c == 0 else "APRES"}  {nbx} boites  {t * 1000:.0f} ms',
                   fill=(255, 220, 120) if c else (190, 200, 220), font=fs)
    suf = '' if a.aspect == '16:9' else '_9x16'
    name = (a.only + '_') if a.only else ''
    p = os.path.join(OUT, f'avant_apres_{name}decors{suf}.png')
    sheet.save(p)
    mp = os.path.join(OUT, f'mesures_{name}decors{suf}.json')
    json.dump(measures, open(mp, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print(p)
    print(mp)


if __name__ == '__main__':
    main()
