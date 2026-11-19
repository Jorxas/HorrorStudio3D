"""Avant / apres de l'ECLAIRAGE NARRATIF (PIXEL 3D) : la meme scene, les memes plans, les memes acteurs,
rendus deux fois par le vrai moteur. Seule difference : les blocs "lighting" de l'episode et des plans
(voir hstudio/engines/pixel3d/lighting.py), retires pour la version AVANT.

  python tools/light_sheet.py                  planche PNG + mesures (rapide)
  python tools/light_sheet.py --mp4            en plus : 3 MP4 9:16 reels (avant, apres, cote a cote)
  python tools/light_sheet.py --fps 24 --mp4   (defaut 20 ips pour la video, 1080x1920)

Sorties : docs/eclairage/avant_apres_eclairage.png (planche, versionnee)
          tests/out/eclairage/*.mp4 et *.png    (rendus lourds, hors depot)
"""
import os, sys, json, time, copy, argparse, subprocess
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from PIL import Image, ImageDraw, ImageFont
from hstudio.pipeline import make_engine
from hstudio.paths import FONT_MONTSERRAT

SCENE = os.path.join(ROOT, 'tests', 'scenes', 'eclairage_narratif.json')
SHEET = os.path.join(ROOT, 'docs', 'eclairage', 'avant_apres_eclairage.png')
OUT = os.path.join(ROOT, 'tests', 'out', 'eclairage')
TAGS = ['halo vert + contre-jour', 'alarme rouge, 7 Hz', 'orage + contre-jour']


def scene():
    return json.load(open(SCENE, encoding='utf-8'))


def strip_lighting(ep):
    """la version AVANT : exactement le meme episode sans aucune intention d'eclairage"""
    ep = copy.deepcopy(ep); ep.pop('lighting', None)
    for s in ep.get('shots', []):
        s.pop('lighting', None)
        for c in s.get('cuts', []) or []: c.pop('lighting', None)
    return ep


def lines_of(ep):
    """une ligne de narration muette par plan, aux durees du plan (pas de voix : aucun appel TTS)"""
    out = []; t = .05
    for i, s in enumerate(ep['shots']):
        d = float(s.get('dur', 4.))
        out.append({'tts': '.', 'display': '', 'text': '', 'tags': [], 'dialogue': False, 'i': i,
                    'start': round(t, 3), 'end': round(t + d, 3), 'segs': [[round(t, 3), round(t + d, 3)]]})
        t += d
    return out


def engine(ep, aspect='9:16'):
    lines = lines_of(ep)
    return make_engine('pixel3d', ep, lines, np.zeros(10), lines[-1]['end'] + .2, aspect)


def shot_times(ep, per_shot=2):
    """quelques instants bien choisis dans chaque plan (dont le creux et la crete du clignotement)"""
    ts = []; t = .05
    picks = {0: (.55, .9), 1: (.25, .62), 2: (.2, .78)}
    for i, s in enumerate(ep['shots']):
        d = float(s.get('dur', 4.))
        for f in picks.get(i, (.3, .7))[:per_shot]: ts.append(round(t + d * f, 3))
        t += d
    return ts


# ------------------------------------------------------------------ mesures
def measure_ab(before_ep, after_ep, ts, aspect='9:16', rounds=5):
    """ms par image basse resolution (ray-cast + shading), AVANT et APRES mesures en alternance.

    Mesurer les deux versions l'une apres l'autre donne ici n'importe quoi : la frequence du processeur
    derive (turbo, autres rendus en cours sur la machine) et on lit un ecart de 100 % entre deux rendus
    identiques. On alterne donc avant/apres image par image, et on garde le meilleur temps de chaque."""
    eb, ea = engine(before_ep, aspect), engine(after_ep, aspect)
    for t in ts: eb.render_lowres(t); ea.render_lowres(t)   # chauffe : decor construit, plans de camera en cache
    best = {'avant': [float('inf')] * len(ts), 'apres': [float('inf')] * len(ts)}
    imgs = {'avant': [None] * len(ts), 'apres': [None] * len(ts)}
    for _ in range(rounds):
        for i, t in enumerate(ts):
            for key, eng in (('avant', eb), ('apres', ea)):
                t0 = time.perf_counter(); img = eng.render_lowres(t)[0]; dt = (time.perf_counter() - t0) * 1000
                if dt < best[key][i]: best[key][i] = dt
                imgs[key][i] = img
    return best, imgs


def nlights(ep, ts):
    """nombre de lumieres reellement envoyees au shader, et celles qui lancent des rayons d'ombre"""
    from hstudio.engines.pixel3d.frame import build_frame
    eng = engine(ep); out = []
    for t in ts:
        L = build_frame(eng.ctx, t)[2]
        out.append((len(L), sum(1 for l in L if len(l) > 4 and l[4])))
    return out


def stats(a, b):
    """difference de rendu entre deux images uint8 : luminance moyenne, pixels changes, teinte"""
    a = a.astype(np.float32); b = b.astype(np.float32)
    lum = lambda x: (x * np.array([.3, .59, .11], np.float32)).sum(-1)
    d = np.abs(a - b).max(-1)
    return dict(lum_before=float(lum(a).mean() / 255), lum_after=float(lum(b).mean() / 255),
                changed=float((d > 8).mean()), mean_abs=float(d.mean()),
                rgb_before=[round(float(a[..., i].mean()), 1) for i in range(3)],
                rgb_after=[round(float(b[..., i].mean()), 1) for i in range(3)])


# ------------------------------------------------------------------ planche
def sheet(before, after, ts, path, cell=(216, 384)):
    W, H = cell; pad = 8; head = 46; foot = 30
    n = len(ts)
    im = Image.new('RGB', (pad + n * (W + pad), head + 2 * (H + foot + pad) + pad), (14, 16, 22))
    d = ImageDraw.Draw(im)
    try: f = ImageFont.truetype(FONT_MONTSERRAT, 20); fs = ImageFont.truetype(FONT_MONTSERRAT, 14)
    except Exception: f = fs = None
    d.text((pad, 8), "ECLAIRAGE NARRATIF (PIXEL 3D, 9:16) - meme scene, memes plans, seuls les blocs \"lighting\" changent", fill=(232, 228, 214), font=f)
    for r, (title, imgs) in enumerate((('AVANT : decor + lumiere de remplissage seuls', before), ('APRES : intention d\'eclairage (ambiance, halo, contre-jour, clignotement, orage)', after))):
        y = head + r * (H + foot + pad)
        d.text((pad, y), title, fill=(200, 230, 200) if r else (210, 210, 220), font=fs)
        for i, a in enumerate(imgs):
            im.paste(Image.fromarray(a).resize((W, H), Image.NEAREST), (pad + i * (W + pad), y + 22))
            if r == 1:
                d.text((pad + i * (W + pad), y + 22 + H + 2), f"t={ts[i]:.2f}s  {TAGS[min(i // 2, len(TAGS) - 1)]}", fill=(150, 160, 170), font=fs)
    os.makedirs(os.path.dirname(path), exist_ok=True); im.save(path)
    return path


# ------------------------------------------------------------------ MP4 (ffmpeg du poste, sinon celui d'imageio-ffmpeg)
def ffmpeg_exe():
    import shutil
    ff = shutil.which('ffmpeg')
    if ff: return ff
    try:
        import imageio_ffmpeg; return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception: return None


def encode(frames_iter, path, size, fps):
    ff = ffmpeg_exe()
    if ff is None: print('  (pas de ffmpeg : MP4 ignore)'); return None
    cmd = [ff, '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{size[0]}x{size[1]}', '-r', str(fps),
           '-i', '-', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for fr in frames_iter: p.stdin.write(np.ascontiguousarray(fr, dtype=np.uint8).tobytes())
    p.stdin.close(); p.wait()
    return path if p.returncode == 0 else None


def video(ep, path, fps, aspect='9:16'):
    eng = engine(ep, aspect); dur = lines_of(ep)[-1]['end']
    n = int(dur * fps)
    t0 = time.perf_counter()
    def frames():
        for i in range(n): yield np.asarray(eng.frame(i / fps))
    out = encode(frames(), path, (1080, 1920) if aspect == '9:16' else (1920, 1080), fps)
    return out, n, time.perf_counter() - t0


def video_side_by_side(a_ep, b_ep, path, fps):
    ea, eb = engine(a_ep), engine(b_ep); dur = lines_of(b_ep)[-1]['end']
    n = int(dur * fps)
    def frames():
        for i in range(n):
            t = i / fps
            la = np.asarray(Image.fromarray(ea.render_lowres(t)[0]).resize((540, 960), Image.NEAREST))
            lb = np.asarray(Image.fromarray(eb.render_lowres(t)[0]).resize((540, 960), Image.NEAREST))
            top = np.concatenate([la, lb], 1)
            yield np.concatenate([np.zeros((480, 1080, 3), np.uint8), top, np.zeros((480, 1080, 3), np.uint8)], 0)
    return encode(frames(), path, (1080, 1920), fps), n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mp4', action='store_true'); ap.add_argument('--fps', type=int, default=20)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    after_ep = scene(); before_ep = strip_lighting(after_ep)
    ts = shot_times(after_ep)
    print('plans :', len(after_ep['shots']), ' instants mesures :', ts)

    best, imgs = measure_ab(before_ep, after_ep, ts)
    imgs_b, imgs_a = imgs['avant'], imgs['apres']
    print("\nPERF (image basse resolution 216x384, avant/apres en alternance, meilleur de 5 passes)")
    for i, t in enumerate(ts):
        b, a_ = best['avant'][i], best['apres'][i]
        print(f"  t={t:5.2f}s  avant {b:7.1f} ms   apres {a_:7.1f} ms   ({(a_ / b - 1) * 100:+5.1f} %)")
    ms_b = sum(best['avant']) / len(ts); ms_a = sum(best['apres']) / len(ts)
    print(f"  moyenne   avant {ms_b:7.1f} ms   apres {ms_a:7.1f} ms   ({(ms_a / ms_b - 1) * 100:+5.1f} %)")

    lb, la = nlights(before_ep, ts), nlights(after_ep, ts)
    print("\nLUMIERES (total / avec rayons d'ombre)")
    for t, (nb, sb), (na, sa) in zip(ts, lb, la):
        print(f"  t={t:5.2f}s  avant {nb:2d}/{sb}   apres {na:2d}/{sa}")

    print("\nDIFFERENCE DE RENDU (image finale basse resolution)")
    rows = []
    for t, A_, B_ in zip(ts, imgs_b, imgs_a):
        s = stats(A_, B_); rows.append((t, s))
        print(f"  t={t:5.2f}s  luminance {s['lum_before']:.3f} -> {s['lum_after']:.3f}   "
              f"pixels changes {s['changed'] * 100:5.1f} %   RGB {s['rgb_before']} -> {s['rgb_after']}")

    p = sheet(imgs_b, imgs_a, ts, SHEET)
    print('\nplanche :', p)
    for t, A_, B_ in zip(ts, imgs_b, imgs_a):
        Image.fromarray(A_).resize((432, 768), Image.NEAREST).save(os.path.join(OUT, f'avant_{t:05.2f}.png'))
        Image.fromarray(B_).resize((432, 768), Image.NEAREST).save(os.path.join(OUT, f'apres_{t:05.2f}.png'))
    print('images plein cadre :', OUT)

    json.dump(dict(ms_before=ms_b, ms_after=ms_a, ms_before_frames=best['avant'], ms_after_frames=best['apres'],
                   lights_before=lb, lights_after=la, frames=[dict(t=t, **s) for t, s in rows]),
              open(os.path.join(OUT, 'mesures.json'), 'w', encoding='utf-8'), indent=1)

    if a.mp4:
        print('\nMP4 9:16 reels...')
        for name, ep in (('avant', before_ep), ('apres', after_ep)):
            path, n, dt = video(ep, os.path.join(OUT, f'eclairage_{name}.mp4'), a.fps)
            if path: print(f"  {path}  ({n} images, {n / a.fps:.1f} s, rendu en {dt:.1f} s = {dt / n * 1000:.0f} ms/image pleine)")
        path, n = video_side_by_side(before_ep, after_ep, os.path.join(OUT, 'eclairage_avant_apres.mp4'), a.fps)
        if path: print(f"  {path}  (cote a cote, {n} images)")


if __name__ == '__main__':
    main()
