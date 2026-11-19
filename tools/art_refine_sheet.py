"""Second increment of the PIXEL 3D art direction: the three named defects, side by side with the version they fix.

  python tools/art_refine_sheet.py --faces      docs/art_v2/refine_visages.png
  python tools/art_refine_sheet.py --heads      docs/art_v2/refine_tete_angles.png
  python tools/art_refine_sheet.py --sets       docs/art_v2/refine_decor.png
  python tools/art_refine_sheet.py --all

It renders the SAME frames twice in one process: once with the art.py of a git revision (`--ref`, HEAD by
default) and once with the working tree's art.py. The reference is written next to the engine as a throwaway
module so the two can live side by side, then deleted. Nothing here claims a verdict: the verdict is a human
looking at the sheet. The measurements printed are QC metrics, not an opinion.
"""
import os, sys, json, argparse, shutil, subprocess
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from PIL import Image, ImageDraw, ImageFont
from hstudio.paths import FONT_MONTSERRAT

PKG = os.path.join(ROOT, 'hstudio', 'engines', 'pixel3d')
REF_NAME = '_art_ref'
OUT_DIR = os.path.join(ROOT, 'docs', 'art_v2')
W = np.array([.299, .587, .114], np.float32)


def font(sz):
    try: return ImageFont.truetype(FONT_MONTSERRAT, sz)
    except Exception: return ImageFont.load_default()


def make_ref(rev):
    """write art.py of `rev` as a sibling module so both versions can be imported at once"""
    src = subprocess.run(['git', 'show', '%s:hstudio/engines/pixel3d/art.py' % rev], cwd=ROOT,
                         capture_output=True, check=True).stdout.decode('utf-8')
    path = os.path.join(PKG, REF_NAME + '.py')
    with open(path, 'w', encoding='utf-8') as f: f.write(src)
    from hstudio.engines.pixel3d import _art_ref
    return _art_ref, path


def drop_ref(path):
    for p in (path, os.path.join(PKG, '__pycache__')):
        if os.path.isdir(p): [os.remove(os.path.join(p, f)) for f in os.listdir(p) if f.startswith(REF_NAME)]
        elif os.path.exists(p): os.remove(p)


# ----------------------------------------------------------------------------- 1. faces and eyes
FACE_PICK = ('neutral', 'talk', 'urgent', 'scared', 'sad', 'suspicious', 'determined', 'nervous', 'happy', 'closed')


def faces(ref, out_path):
    from hstudio.engines.pixel3d import art, assets as A
    kinds = [k for k in FACE_PICK if k in A.FACE_KINDS] or list(A.FACE_KINDS[:10])
    art.configure('voxel_hd'); ref.configure('voxel_hd')
    z, ez = 4, 10
    cw = 48 * z; eh = 14 * ez
    rows = 3                                                     # stock 24x24, reference v2, working tree v2
    head = 20; lab = 16
    sheet = Image.new('RGB', (len(kinds) * (cw + 6) + 110, rows * (cw + lab) + eh * 2 + head + 30), (14, 16, 22))
    d = ImageDraw.Draw(sheet); f9 = font(10); f11 = font(12)
    d.text((6, 5), 'PIXEL 3D v2 - visages et zoom sur les yeux  (haut: livre 24x24 / milieu: v2 reference / bas: v2 arbre de travail)',
           font=f11, fill=(220, 224, 236))
    names = ('livre 24x24', 'v2 reference', 'v2 nouveau', 'oeil reference', 'oeil nouveau')
    ys = [head + 4, head + 4 + (cw + lab), head + 4 + 2 * (cw + lab)]
    ys += [ys[2] + cw + lab, ys[2] + cw + lab + eh + 6]
    for i, nm in enumerate(names): d.text((4, ys[i] + 4), nm, font=f9, fill=(170, 176, 196))
    for j, kind in enumerate(kinds):
        x = 108 + j * (cw + 6)
        stock = Image.fromarray(A.face_tex(kind)).convert('RGB').resize((cw, cw), Image.NEAREST)
        a = ref.face_hd(kind); b = art.face_hd(kind)
        ia = Image.fromarray(a).convert('RGB'); ib = Image.fromarray(b).convert('RGB')
        sheet.paste(stock, (x, ys[0])); sheet.paste(ia.resize((cw, cw), Image.NEAREST), (x, ys[1]))
        sheet.paste(ib.resize((cw, cw), Image.NEAREST), (x, ys[2]))
        d.text((x + 2, ys[2] + cw + 2), kind, font=f9, fill=(210, 214, 226))
        band = (0, 15, 48, 29)                                   # the eye band of the 48x48 plate
        sheet.paste(ia.crop(band).resize((48 * ez // 4 * 4 // 4, eh), Image.NEAREST).resize((cw, eh), Image.NEAREST), (x, ys[3]))
        sheet.paste(ib.crop(band).resize((cw, eh), Image.NEAREST), (x, ys[4]))
    sheet.save(out_path)
    # QC metric: how much of the open eye is still sclera (white), the defect was "an iris filling the lid slit"
    met = {}
    for kind in kinds:
        r = {}
        for tag, mod in (('ref', ref), ('new', art)):
            tex = mod.face_hd(kind)[..., :3].astype(np.float32)
            eye = tex[16:29, 6:43]
            lum = (eye / 255. * W).sum(-1)
            r[tag] = dict(white=round(float((lum > .80).mean()), 4), dark=round(float((lum < .18).mean()), 4),
                          mean=round(float(lum.mean()), 4))
        met[kind] = r
    return out_path, met


# ----------------------------------------------------------------------------- 2. the head from four angles
ANGLES = ('front', 'three_quarter', 'side', 'back')


def _head_episode(cid, angle, art_key):
    ep = {'engine_version': 2, 'style': 'pixel3d', 'default_set': 'studio', 'cast': {cid: {'ref': cid}},
          'hud': {'title': [], 'hearts': []},
          'sets': {'studio': {'type': 'room', 'rooms': [{'id': 'studio', 'origin': [0, 0], 'size': [6, 6],
                                                         'walls': 'plaster', 'floor': 'wood', 'light': 'neon',
                                                         'light_power': 1.3, 'clean': True}]}},
          'lines': {}, 'shots': [{'lines': [0, 0],
                                  'actors': [{'id': cid, 'at': [0, 3.0], 'facing': '-z', 'face': 'neutral'}],
                                  'camera': {'shot': 'close', 'on': [cid], 'angle': angle},
                                  'ui': {'hud': False, 'subs': 'off'},
                                  # lit from four sides on purpose: the point of this sheet is the hair geometry,
                                  # not the lighting. With a front key only, every "back" frame is a black
                                  # silhouette and nothing can be judged.
                                  'lights': [{'at': [1.3, 1.9, 1.9], 'y': 1.9, 'color': [1, .93, .82], 'power': 1.3, 'radius': 4.},
                                             {'at': [-1.3, 1.8, 2.1], 'y': 1.8, 'color': [.72, .80, 1], 'power': .8, 'radius': 4.},
                                             {'at': [1.3, 1.9, 4.2], 'y': 1.9, 'color': [.95, .92, .88], 'power': 1.0, 'radius': 4.},
                                             {'at': [-1.3, 1.9, 4.3], 'y': 1.9, 'color': [.88, .90, 1], 'power': 1.0, 'radius': 4.}]}]}
    if art_key: ep['art'] = art_key
    return ep


def _head_frame(cid, angle, art_key, ref=None):
    """one close shot of a character; with `ref` the reference art.py draws the body and the face"""
    from hstudio.pipeline import make_engine
    from hstudio.engines.pixel3d import art
    ep = _head_episode(cid, angle, art_key)
    lines = [{'tts': '.', 'display': '', 'text': '', 'tags': [], 'dialogue': False, 'i': 0,
              'start': .05, 'end': 1.0, 'segs': [[.05, 1.0]]}]
    saved = None
    if ref is not None:
        ref.configure(art_key)
        saved = (art.figure, art.face_hd, art.decor, art.grade)
        art.figure, art.face_hd, art.decor, art.grade = ref.figure, ref.face_hd, ref.decor, ref.grade
    try:
        eng = make_engine('pixel3d', ep, lines, np.zeros(10), 1.2, '16:9')
        img = eng.render_lowres(.6)[0]
    finally:
        if saved is not None:
            art.figure, art.face_hd, art.decor, art.grade = saved
            ref.configure(None)
    return img


def heads(ref, out_path, cid='lea'):
    z = 3
    cols = []
    for angle in ANGLES:
        cols.append((angle,
                     _head_frame(cid, angle, None),
                     _head_frame(cid, angle, 'voxel_hd', ref=ref),
                     _head_frame(cid, angle, 'voxel_hd')))
    h, w = cols[0][1].shape[:2]
    cw, ch = w * z, h * z
    head = 22; lab = 15
    sheet = Image.new('RGB', (len(cols) * (cw + 6) + 120, 3 * (ch + lab) + head + 10), (14, 16, 22))
    d = ImageDraw.Draw(sheet); f9 = font(10); f11 = font(12)
    d.text((6, 5), 'PIXEL 3D v2 - la tete de %s sous quatre angles (defaut 2: de dos, une masse sombre)' % cid,
           font=f11, fill=(220, 224, 236))
    met = {}
    for r, nm in enumerate(('livre (sans art)', 'v2 reference', 'v2 nouveau')):
        d.text((4, head + r * (ch + lab) + 4), nm, font=f9, fill=(170, 176, 196))
    for j, (angle, a, b, c) in enumerate(cols):
        x = 118 + j * (cw + 6)
        for r, im in enumerate((a, b, c)):
            sheet.paste(Image.fromarray(im).resize((cw, ch), Image.NEAREST), (x, head + r * (ch + lab)))
        d.text((x + 2, head + 3 * (ch + lab) - 11), angle, font=f9, fill=(210, 214, 226))
        met[angle] = {}
        for tag, im in (('ship', a), ('ref', b), ('new', c)):
            y = (im.astype(np.float32) / 255. * W).sum(-1)
            cy0, cy1 = int(h * .18), int(h * .62); cx0, cx1 = int(w * .30), int(w * .70)
            crop = y[cy0:cy1, cx0:cx1]                      # where the head is in a close shot
            met[angle][tag] = dict(head_mean=round(float(crop.mean()), 4),
                                   head_p05=round(float(np.percentile(crop, 5)), 4),
                                   head_p95=round(float(np.percentile(crop, 95)), 4),
                                   head_std=round(float(crop.std()), 4),
                                   head_dark=round(float((crop < .10).mean()), 4))
    sheet.save(out_path)
    return out_path, met


# ----------------------------------------------------------------------------- 3. the dressed set
def _demo_engine(demo_id, aspect, art_key):
    from hstudio import demos
    from hstudio.pipeline import make_engine, duration_of
    sc = demos.load(demo_id)
    lines = demos.timed_lines(sc['script'], float(sc.get('gap', .3)), float(sc.get('lead', .4)))
    env = demos.draft_voice(sc, lines)[1]
    ep = demos.episode_of(sc, lines, log=lambda *a: None)
    if art_key: ep['art'] = art_key
    else: ep.pop('art', None)
    dur = duration_of(ep, lines)
    return make_engine(sc.get('style', 'pixel3d'), ep, lines, env, dur, aspect), dur


def sets(ref, out_path, demo_id='demo13_art_pixel3d', aspect='16:9'):
    from hstudio.engines.pixel3d import art
    e_ship, dur = _demo_engine(demo_id, aspect, None)
    e_new, _ = _demo_engine(demo_id, aspect, 'voxel_hd')
    ts = [dur * f for f in (.08, .26, .44, .62, .80, .94)]
    ship = [e_ship.render_lowres(t)[0] for t in ts]
    new = [e_new.render_lowres(t)[0] for t in ts]
    saved = (art.figure, art.face_hd, art.decor, art.grade)
    ref.configure('voxel_hd')
    art.figure, art.face_hd, art.decor, art.grade = ref.figure, ref.face_hd, ref.decor, ref.grade
    try:
        e_ref, _ = _demo_engine(demo_id, aspect, 'voxel_hd')
        refs = [e_ref.render_lowres(t)[0] for t in ts]
    finally:
        art.figure, art.face_hd, art.decor, art.grade = saved
        ref.configure(None)
    h, w = ship[0].shape[:2]; z = 2
    cw, ch = w * z, h * z
    head = 22; lab = 14
    sheet = Image.new('RGB', (len(ts) * (cw + 6) + 120, 3 * (ch + lab) + head + 8), (14, 16, 22))
    d = ImageDraw.Draw(sheet); f9 = font(10); f11 = font(12)
    d.text((6, 5), 'PIXEL 3D v2 - %s %s : mobilier, accessoires et moulures' % (demo_id, aspect),
           font=f11, fill=(220, 224, 236))
    for r, nm in enumerate(('livre (sans art)', 'v2 reference', 'v2 nouveau')):
        d.text((4, head + r * (ch + lab) + 4), nm, font=f9, fill=(170, 176, 196))
    for j in range(len(ts)):
        x = 118 + j * (cw + 6)
        for r, im in enumerate((ship[j], refs[j], new[j])):
            sheet.paste(Image.fromarray(im).resize((cw, ch), Image.NEAREST), (x, head + r * (ch + lab)))
        d.text((x + 2, head + 3 * (ch + lab) - 10), 't=%.1fs' % ts[j], font=f9, fill=(210, 214, 226))
    sheet.save(out_path)
    met = []
    for j, t in enumerate(ts):
        row = dict(t=round(float(t), 2))
        for tag, im in (('ship', ship[j]), ('ref', refs[j]), ('new', new[j])):
            y = (im.astype(np.float32) / 255. * W).sum(-1)
            row[tag] = dict(mean=round(float(y.mean()), 4), p05=round(float(np.percentile(y, 5)), 4),
                            p95=round(float(np.percentile(y, 95)), 4),
                            colours=int(len(np.unique(im.reshape(-1, 3), axis=0))))
        row['changed_vs_ref'] = round(float((np.abs(new[j].astype(np.int16) - refs[j].astype(np.int16)).sum(-1) > 8).mean()), 4)
        met.append(row)
    return out_path, met


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ref', default='HEAD', help='git revision whose art.py is the reference')
    ap.add_argument('--faces', nargs='?', const=os.path.join(OUT_DIR, 'refine_visages.png'))
    ap.add_argument('--heads', nargs='?', const=os.path.join(OUT_DIR, 'refine_tete_angles.png'))
    ap.add_argument('--sets', nargs='?', const=os.path.join(OUT_DIR, 'refine_decor.png'))
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--demo', default='demo13_art_pixel3d')
    ap.add_argument('--metrics', default=os.path.join(OUT_DIR, 'refine_mesures.json'))
    a = ap.parse_args()
    if a.all:
        a.faces = a.faces or os.path.join(OUT_DIR, 'refine_visages.png')
        a.heads = a.heads or os.path.join(OUT_DIR, 'refine_tete_angles.png')
        a.sets = a.sets or os.path.join(OUT_DIR, 'refine_decor.png')
    if not (a.faces or a.heads or a.sets): a.faces = os.path.join(OUT_DIR, 'refine_visages.png')
    os.makedirs(OUT_DIR, exist_ok=True)
    ref, ref_path = make_ref(a.ref)
    out = {'ref_revision': subprocess.run(['git', 'rev-parse', '--short', a.ref], cwd=ROOT,
                                          capture_output=True).stdout.decode().strip()}
    try:
        if a.faces:
            p, m = faces(ref, a.faces); out['faces'] = m; print('visages   ->', p)
        if a.heads:
            p, m = heads(ref, a.heads); out['heads'] = m; print('tete      ->', p)
        if a.sets:
            p, m = sets(ref, a.sets, a.demo); out['sets'] = m; print('decor     ->', p)
    finally:
        drop_ref(ref_path)
    with open(a.metrics, 'w', encoding='utf-8') as f: json.dump(out, f, indent=1, ensure_ascii=False)
    print('mesures   ->', a.metrics)


if __name__ == '__main__':
    main()
