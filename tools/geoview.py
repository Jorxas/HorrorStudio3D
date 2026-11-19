"""A deterministic 9:16 view of a camera on the GEOMETRY of the place (stagegeo boxes + the actors as blocks), no GPU, no browser.

It is not a render: it is what a camera sees of the data the director checks (walls, glass, counter, shelves, car, doors, actors). It answers visual questions the
numbers only hint at: is the car whole, is there a shelf in the lens, is the menace behind the subject, is the gap between the door and the car readable.
Painter's algorithm on clipped quads, Pillow only. Used by tools/camera_benchmark.py; `python tools/geoview.py` draws a self-test.
"""
import math
import numpy as np
from PIL import Image, ImageDraw

COL = dict(wall=(92, 96, 104), glass=(120, 170, 200), ceiling=(60, 62, 70), car=(150, 28, 36), floor=(26, 28, 34), sky=(8, 10, 18))
ACTOR = dict(clerk=((60, 150, 160), (225, 190, 160)), ghost=((10, 10, 12), (236, 236, 232)))


def _basis(pos, look):
    f = np.array(look, float) - np.array(pos, float); f /= (np.linalg.norm(f) + 1e-12); r = np.cross(f, [0., 1., 0.]); r /= (np.linalg.norm(r) + 1e-12); u = np.cross(r, f); return f, r, u


def _box_faces(x0, y0, z0, x1, y1, z1):
    c = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]; i = lambda a, b, d: c[a * 4 + b * 2 + d]
    return [([i(0, 0, 0), i(0, 1, 0), i(0, 1, 1), i(0, 0, 1)], (-1, 0, 0)), ([i(1, 0, 0), i(1, 1, 0), i(1, 1, 1), i(1, 0, 1)], (1, 0, 0)),
            ([i(0, 0, 0), i(1, 0, 0), i(1, 0, 1), i(0, 0, 1)], (0, -1, 0)), ([i(0, 1, 0), i(1, 1, 0), i(1, 1, 1), i(0, 1, 1)], (0, 1, 0)),
            ([i(0, 0, 0), i(1, 0, 0), i(1, 1, 0), i(0, 1, 0)], (0, 0, -1)), ([i(0, 0, 1), i(1, 0, 1), i(1, 1, 1), i(0, 1, 1)], (0, 0, 1))]


def _clip_near(poly, near=.12):
    out = []
    for a, b in zip(poly, poly[1:] + poly[:1]):
        da, db = a[2] - near, b[2] - near
        if da >= 0: out.append(a)
        if (da >= 0) != (db >= 0): t = da / (da - db); out.append(tuple(a[i] + (b[i] - a[i]) * t for i in range(3)))
    return out


def render(geo, C, pos, look, fov, t, size=(180, 320), actors=None, aspect=9 / 16, label='', mark=()):
    W, H = size; img = Image.new('RGB', size, COL['sky']); d = ImageDraw.Draw(img, 'RGBA'); f, r, u = _basis(pos, look); tn = math.tan(math.radians(fov) / 2.)
    P = np.array(pos, float)

    def to_screen(p):
        v = np.array(p, float) - P; z = float(v @ f)
        return z, (float(v @ r), float(v @ u), z)

    def proj(cam):
        x, y, z = cam; return ((x / (z * tn * aspect) + 1) / 2 * W, (1 - (y / (z * tn) + 1) / 2) * H)
    # ground
    g = [(-60, 0, -60), (60, 0, -60), (60, 0, 60), (-60, 0, 60)]; poly = _clip_near([to_screen(p)[1] for p in g])
    if len(poly) >= 3: d.polygon([proj(p) for p in poly], fill=COL['floor'] + (255,))
    faces = []
    boxes = [(s.x0, s.y0, s.z0, s.x1, s.y1, s.z1, s.kind) for s in geo.solids]
    for q in geo.portals.values():
        op = q.amount(t); x0, z0, x1, z1 = q.rect
        if op < .6: boxes.append((x0, 0., z0, x1, q.y1, z1, 'glass' if q.id == 'entree' else 'wall'))
    for b in boxes:
        for quad, n in _box_faces(*b[:6]):
            cam = [to_screen(p)[1] for p in quad]; poly = _clip_near(cam)
            if len(poly) < 3: continue
            cen = np.mean([[c[0], c[1], c[2]] for c in poly], axis=0); shade = .55 + .45 * max(0., float(np.dot(n, (-.4, .8, -.45))))
            kind = b[6] if b[6] in COL else 'wall'; base = COL[kind]
            faces.append((float(np.linalg.norm(cen)), [proj(p) for p in poly], tuple(int(c * shade) for c in base), 55 if kind == 'glass' else 255))
    if actors is None: actors = list(C.actors)
    for aid in actors:
        A = C.actors[aid]; x, z = C.xz(aid, t); body, head = ACTOR.get(aid, ((120, 120, 120), (230, 230, 230))); s = A.scale
        for (y0, y1, hw, col) in ((0., 1.55 * s, .22 * s, body), (1.55 * s, 2.15 * s, .27 * s, head)):
            for quad, n in _box_faces(x - hw, y0, z - hw, x + hw, y1, z + hw):
                poly = _clip_near([to_screen(p)[1] for p in quad])
                if len(poly) < 3: continue
                cen = np.mean([[c[0], c[1], c[2]] for c in poly], axis=0); sh = .6 + .4 * max(0., float(np.dot(n, (-.4, .8, -.45))))
                faces.append((float(np.linalg.norm(cen)) - .02, [proj(p) for p in poly], tuple(int(c * sh) for c in col), 255))
    for _, poly, col, a in sorted([f_ for f_ in faces if f_[3] == 255], key=lambda f_: -f_[0]):          # opaque things far to near ...
        d.polygon(poly, fill=col + (a,), outline=(20, 20, 24, 255))
    for _, poly, col, a in sorted([f_ for f_ in faces if f_[3] != 255], key=lambda f_: -f_[0]):          # ... then the glass over everything (a pane is thin: it tints, it does not hide)
        d.polygon(poly, fill=col + (a,))
    for p in mark:                                     # points of interest (the spot where somebody vanished)
        z, c = to_screen(p)
        if z > .12: x, y = proj(c); d.ellipse([x - 4, y - 4, x + 4, y + 4], outline=(255, 220, 0, 255))
    if label: d.rectangle([0, 0, W, 12], fill=(0, 0, 0, 190)); d.text((2, 1), label, fill=(255, 255, 255, 255))
    return img


def sheet(rows, col_labels, cell=(180, 320), pad=3, title=''):
    """rows = [(row label, [image or None, ...])] -> one picture"""
    W, H = cell; lw = 70; n = len(col_labels); top = 18
    out = Image.new('RGB', (lw + n * (W + pad) + pad, top + len(rows) * (H + pad) + pad), (16, 16, 20)); d = ImageDraw.Draw(out)
    d.text((4, 3), title, fill=(255, 255, 255))
    for j, c in enumerate(col_labels): d.text((lw + j * (W + pad) + 4, 3 + 0), '', fill=(255, 255, 255))
    for i, (lab, imgs) in enumerate(rows):
        y = top + pad + i * (H + pad); d.text((3, y + 4), lab, fill=(255, 220, 120))
        for j, im in enumerate(imgs):
            if im is not None: out.paste(im, (lw + j * (W + pad) + pad, y))
    return out


if __name__ == '__main__':
    import sys; sys.path.insert(0, '.')
    from hstudio.voxelgpu import stagegeo, blocking as B
    from hstudio.voxelgpu.films import pompe_continuite as N
    geo = stagegeo.station(N.DOORS); C = B.compile_plan(N.plan(), geo)
    render(geo, C, (-6, 1.6, 17), (1.5, 1.3, 5), 66, 20., label='autotest').save('geoview_selftest.png'); print('geoview_selftest.png')
