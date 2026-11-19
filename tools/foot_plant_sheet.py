"""Avant / apres du glissement des semelles : la meme scene jouee sans et avec `"foot_plant": true`.

  python tools/foot_plant_sheet.py                                  # 9:16, PNG + MP4 dans docs/mesures
  python tools/foot_plant_sheet.py --aspect 16:9 --no-video
  python tools/foot_plant_sheet.py --seconds 1.4,3.0                # ne garder que la fenetre du defaut

Vraies images du moteur de production (`eng.frame(t)`), aucun mock, aucune image fixe deguisee en animation. Les
deux versions sont le MEME fichier de scene : seule la cle d'episode "foot_plant" change, donc le decor, la
lumiere, le trajet, la vitesse, la duree du plan et la camera sont les memes des deux cotes.

La camera est resolue UNE fois sur la version A -- choisie avant que le correctif existe, elle ne peut donc pas
avoir ete cadree pour flatter B -- puis imposee a B. Elle est fixe ("move": "static") et cadre les deux acteurs :
le corps traverse donc reellement le cadre, et son deplacement dans l'espace n'est pas masque par un suivi ou un
zoom. Les deux pieds restent dans l'image du debut a la fin.

Ecrit, pour une scene nommee <name> :
  <name>_planche.png     planche contact : une ligne par version aux memes horodatages, puis une ligne de ZOOM
                         sur les semelles aux images ou la mesure place le defaut (l'arret de fin de trajet)
  <name>_ab_<aspect>.mp4 les deux versions cote a cote (c'est l'A/B a regarder)
  <name>_a_sans.mp4      version A seule (historique)
  <name>_b_avec.mp4      version B seule ("foot_plant": true)
"""
import os, sys, copy, time, math, argparse, subprocess, shutil
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))
from PIL import Image, ImageDraw, ImageFont                       # noqa: E402
from hstudio.pipeline import make_engine, duration_of             # noqa: E402
from hstudio.paths import FONT_MONTSERRAT                         # noqa: E402
from hstudio.acting import rig                                    # noqa: E402
from locomotion_qc import read_scene                              # noqa: E402
from foot_plant_qc import sole_world, in_stance                   # noqa: E402

TOPS = ('A  SANS l\'option : a l\'arrivee les deux semelles sont tirees dans le sol',
        'B  "foot_plant": true : la foulee finit sur la pose, les semelles restent plantees')


def ffmpeg_exe():
    ff = shutil.which('ffmpeg')
    if ff: return ff
    try:
        from hstudio.ffmpeg_path import ensure
        return (ensure() or {}).get('ffmpeg')
    except Exception:
        pass
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


class Mp4:
    """un process ffmpeg nourri image par image, pour ne rien garder de gros en memoire"""
    def __init__(self, ff, path, size, fps, crf=28):
        self.path = path; w, h = size; self.w = w - w % 2; self.h = h - h % 2; self.p = None
        if ff is None: return
        self.p = subprocess.Popen([ff, '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                                   '-s', f'{self.w}x{self.h}', '-r', str(fps), '-i', '-',
                                   '-c:v', 'libx264', '-preset', 'medium', '-crf', str(crf),
                                   '-pix_fmt', 'yuv420p', '-movflags', '+faststart', path], stdin=subprocess.PIPE)

    def write(self, im):
        if self.p: self.p.stdin.write(np.asarray(im.crop((0, 0, self.w, self.h)).convert('RGB'), np.uint8).tobytes())

    def close(self, n):
        if not self.p: return
        self.p.stdin.close()
        if self.p.wait(): print('  !! ffmpeg a echoue pour', self.path)
        else: print('  ->', self.path, f'({os.path.getsize(self.path) / 1e6:.2f} Mo, {n} images, {self.w}x{self.h})')


def engine_of(scene, lines, plant, aspect):
    ep = copy.deepcopy(scene)
    if plant: ep['foot_plant'] = True
    else: ep.pop('foot_plant', None)
    dur = duration_of(ep, lines)
    return make_engine(ep.get('style', 'pixel3d'), ep, lines, np.zeros(10), dur, aspect), ep, dur


# ------------------------------------------------------------------ ou est le defaut, et ou sont les pieds
def worst_moments(eng, spans, who='lea', fps=30.):
    """[(t absolu, cm/image)] trie, glissement de la semelle en appui mesure sur CE montage"""
    from hstudio.acting.qc import _acting
    ac = _acting(eng); out = []
    for k, sa in sorted(ac.shots.items()):
        if who not in sa.tracks: continue
        t0 = spans[k][0]; prev = None
        for i in range(int(sa.dur * fps)):
            t = i / fps; s = sa.sample(t)[who]; sk = rig.solve(s['rig'])
            cur = (sole_world(s, sk), {g: in_stance(s['rig'], g) for g in ('L', 'R')})
            if prev is not None:
                for g in ('L', 'R'):
                    if cur[1][g] and prev[1][g]:
                        d = math.hypot(cur[0][g][0] - prev[0][g][0], cur[0][g][2] - prev[0][g][2]) * 100
                        out.append((t0 + t, d, k))
            prev = cur
    out.sort(key=lambda r: -r[1]); return out


def sole_uv(eng, t, who='lea'):
    """(u, v) normalises de la semelle la plus basse de `who` a l'instant t, dans l'image de CE moteur"""
    from hstudio.engines.pixel3d import r3d
    from hstudio.engines.pixel3d.frame import build_frame
    sc, cam, L, shot, T, u_, k_, state = build_frame(eng.ctx, float(t))
    pos, yaw, pitch, roll, fov = cam
    from hstudio.acting.qc import _acting
    ac = _acting(eng)
    for k, sa in sorted(ac.shots.items()):
        if who not in sa.tracks: continue
        rel = min(sa.dur - 1e-3, max(0., t - eng.ctx.tl.spans[k][0]))
        if not (0. <= t - eng.ctx.tl.spans[k][0] <= sa.dur): continue
        s = sa.sample(rel)[who]; sk = rig.solve(s['rig']); so = sole_world(s, sk)
        g = 'R' if so['R'][1] <= so['L'][1] else 'L'
        uu, vv, dd = r3d.project(pos, yaw, pitch, roll, fov, so[g])
        if dd > 1e-3 and abs(uu) < 9.: return uu, vv
    return None


def zoom(im, uv, k=3.2):
    """recadrage agrandi autour d'un point normalise (u droite, v haut) de l'image"""
    W, H = im.size
    cx = (uv[0] + 1) / 2 * W; cy = (1 - uv[1]) / 2 * H
    w, h = W / k, H / k
    x0 = min(max(0, cx - w / 2), W - w); y0 = min(max(0, cy - h / 2), H - h)
    return im.crop((int(x0), int(y0), int(x0 + w), int(y0 + h))).resize((int(w * k) // 2 * 2, int(h * k) // 2 * 2), Image.NEAREST)


def strip(w, text, h, font):
    im = Image.new('RGB', (w, h), (14, 16, 22))
    ImageDraw.Draw(im).text((8, (h - 20) // 2), text, fill=(232, 228, 214), font=font)
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('scene', nargs='?', default=os.path.join(ROOT, 'tests', 'scenes', 'course_lea_foot_plant.json'))
    ap.add_argument('--aspect', default='9:16')
    ap.add_argument('--out', default=os.path.join(ROOT, 'docs', 'mesures'))
    ap.add_argument('--fps', type=float, default=20.)
    ap.add_argument('--width', type=int, default=432)
    ap.add_argument('--cols', type=int, default=6)
    ap.add_argument('--who', default='lea')
    ap.add_argument('--seconds', default=None, help='a,b : ne rendre que cette fenetre de la video')
    ap.add_argument('--no-video', action='store_true')
    ap.add_argument('--crf', type=int, default=28)
    ap.add_argument('--zoom', type=float, default=6.0, help='facteur de grossissement de la ligne ZOOM')
    a = ap.parse_args()

    scene, lines = read_scene(a.scene)
    name = os.path.splitext(os.path.basename(a.scene))[0]
    os.makedirs(a.out, exist_ok=True)
    try: font = ImageFont.truetype(FONT_MONTSERRAT, 15)
    except Exception: font = None

    print(f'{name}  ({a.aspect})')
    engines = [engine_of(scene, lines, p, a.aspect) for p in (False, True)]
    dur = engines[0][2]
    spans = engines[0][0].ctx.tl.spans

    # la camera de A, resolue une fois, imposee a B : seul le jeu differe
    engines[0][0].frame(0.)
    engines[1][0].ctx.cam_cache.update(engines[0][0].ctx.cam_cache)
    engines[1][0].ctx.cam_memory.update(engines[0][0].ctx.cam_memory)

    W = a.width; H = int(round(W * (9 / 16 if a.aspect == '16:9' else 16 / 9)))
    H += H % 2; W += W % 2
    n_rendered = 0; t_start = time.perf_counter()

    def shot(i, t):
        nonlocal n_rendered
        n_rendered += 1
        return engines[i][0].frame(float(min(t, dur - .01))).resize((W, H), Image.LANCZOS)

    # ou le defaut est le plus fort sur la version A, un instant par plan
    worst = worst_moments(engines[0][0], spans, a.who)
    per_shot = {}
    for t, cm, k in worst: per_shot.setdefault(k, (t, cm))
    picks = [(k, per_shot[k][0], per_shot[k][1]) for k in sorted(per_shot)]
    print('  defaut mesure sur A : ' + ', '.join(f'plan {k} t={per_shot[k][0]:.2f}s {per_shot[k][1]:.2f} cm/i' for k in sorted(per_shot)))
    after = worst_moments(engines[1][0], spans, a.who)
    aft = {}
    for t, cm, k in after: aft.setdefault(k, cm)
    print('  au meme endroit sur B : ' + ', '.join(f'plan {k} {aft.get(k, 0.):.2f} cm/i' for k in sorted(per_shot)))

    # ---------------------------------------------------------------- planche contact
    # Lignes 1-2 : le plan entier, memes horodatages. Lignes suivantes : le defaut dure ~0.3 s, une image isolee
    # ne peut donc rien montrer -- on prend NSEQ images 30 i/s CONSECUTIVES autour de l'instant mesure, zoomees
    # sur la semelle, A au-dessus de B. Le glissement se lit alors comme un deplacement d'une case a l'autre.
    NSEQ = 5
    ts = [dur * (i + .5) / a.cols for i in range(a.cols)]
    cw = W // 2; ch = H // 2; pad = 6; head = 26
    ncol = max(a.cols, NSEQ)
    rows = 2 + 2 * len(picks)
    sheet = Image.new('RGB', (pad + ncol * (cw + pad), rows * (head + ch + pad) + pad), (14, 16, 22))
    d = ImageDraw.Draw(sheet)
    for r in (0, 1):
        y = pad + r * (head + ch + pad)
        d.text((pad, y + 4), TOPS[r], fill=(232, 228, 214), font=font)
        for i, t in enumerate(ts):
            sheet.paste(shot(r, t).resize((cw, ch), Image.LANCZOS), (pad + i * (cw + pad), y + head))
            d.text((pad + i * (cw + pad) + 4, y + head + 2), f'{t:.2f}s', fill=(255, 220, 60), font=font)
    row = 2
    for (k_, t0_, cm) in picks:
        seq = [t0_ - 1 / 30. + j / 30. for j in range(NSEQ)]
        uv = sole_uv(engines[0][0], t0_, a.who) or (0., -.2)
        for i in (0, 1):
            y = pad + row * (head + ch + pad)
            tag = 'A SANS' if i == 0 else 'B AVEC'
            d.text((pad, y + 4), f'ZOOM SEMELLES {tag} -- {NSEQ} images 30 i/s consecutives autour de t={t0_:.2f}s '
                                 f'(glissement mesure {cm if i == 0 else aft.get(k_, 0.):.2f} cm/image)',
                   fill=(255, 150, 150) if i == 0 else (150, 255, 170), font=font)
            for j, t in enumerate(seq):
                sheet.paste(zoom(shot(i, t), uv, a.zoom).resize((cw, ch), Image.LANCZOS), (pad + j * (cw + pad), y + head))
                d.text((pad + j * (cw + pad) + 4, y + head + 2), f'{t:.3f}s', fill=(255, 220, 60), font=font)
            row += 1
    png = os.path.join(a.out, f'{name}_planche.png')
    sheet.quantize(colors=256, method=Image.MEDIANCUT).save(png, optimize=True)   # ~1 Mo, comme approche_sheet.py
    print('  ->', png, f'({os.path.getsize(png) / 1e6:.2f} Mo, {sheet.width}x{sheet.height})')

    if a.no_video:
        print(f'  {n_rendered} images rendues en {time.perf_counter() - t_start:.1f} s'); return

    # ---------------------------------------------------------------- les videos
    ff = ffmpeg_exe()
    if ff is None: print('  !! ffmpeg introuvable : pas de MP4')
    lo, hi = (float(x) for x in a.seconds.split(',')) if a.seconds else (0., dur)
    times = [t for t in (i / a.fps for i in range(int(dur * a.fps))) if lo <= t <= hi]
    gap = 6
    asp = a.aspect.replace(':', 'x')
    vids = {'ab': Mp4(ff, os.path.join(a.out, f'{name}_ab_{asp}.mp4'), (2 * W + gap, H + head), a.fps, a.crf),
            'a': Mp4(ff, os.path.join(a.out, f'{name}_a_sans_{asp}.mp4'), (W, H), a.fps, a.crf),
            'b': Mp4(ff, os.path.join(a.out, f'{name}_b_avec_{asp}.mp4'), (W, H), a.fps, a.crf)}
    tops = (strip(W, 'A  SANS l\'option', head, font), strip(W, 'B  "foot_plant": true', head, font))
    for t in times:
        fa = shot(0, t); fb = shot(1, t)
        im = Image.new('RGB', (2 * W + gap, H + head), (14, 16, 22))
        im.paste(tops[0], (0, 0)); im.paste(tops[1], (W + gap, 0))
        im.paste(fa, (0, head)); im.paste(fb, (W + gap, head))
        ImageDraw.Draw(im).text((2 * W + gap - 62, 5), f'{t:5.2f}s', fill=(255, 220, 60), font=font)
        vids['ab'].write(im); vids['a'].write(fa); vids['b'].write(fb)
    for v in vids.values(): v.close(len(times))
    print(f'  {n_rendered} images rendues en {time.perf_counter() - t_start:.1f} s')


if __name__ == '__main__':
    main()
