"""Étape APERÇU du kit : une image basse définition de CHAQUE cadrage (chaque plan et chaque coupe dans un plan), dans
les deux formats, assemblées en planches de 12 avec le numéro du plan, les phrases, l'instant et le début du texte dit.
Chaque image est aussi mesurée (trop sombre, brûlée, uniforme = caméra dans un mur ou face à un mur nu) : les alertes
sont écrites dans planches/apercu_<version>.json et affichées. REGARDE les planches : la mesure ne remplace pas l'œil.

    python -m hstudio.histoire apercu <dossier> [--format 16:9|9:16|tous] [--plans 10-20] [--chaque 2.5] [--workers 6]
    -> planches/apercu_long_16x9_00.jpg ... ; planches/apercu_complet_9x16_00.jpg ..."""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .common import ENGINE, KitError, Story, read_json, write_json
from . import projet as PJ
from . import rendu as RD

THUMB = {'16:9': (640, 360), '9:16': (360, 640)}
COLS = {'16:9': 3, '9:16': 6}
PER = 12


def stats(a):
    """mean luminance, contrast, share of near-black and of blown pixels, share of the most common coarse colour"""
    y = a[..., 0] * .299 + a[..., 1] * .587 + a[..., 2] * .114
    q = (a // 32).reshape(-1, 3); _, cnt = np.unique(q[:, 0] * 64 + q[:, 1] * 8 + q[:, 2], return_counts=True)
    return dict(lum=round(float(y.mean()), 1), contraste=round(float(y.std()), 1), noir=round(float((y < 12).mean()), 3),
                brule=round(float((y > 248).mean()), 3), couleur_dominante=round(float(cnt.max() / q.shape[0]), 3))


def alerts(s):
    out = []
    if s['lum'] < 14: out.append('très sombre')
    if s['brule'] > .06: out.append(f"{s['brule'] * 100:.0f} % brûlé")
    if s['contraste'] < 9 or s['couleur_dominante'] > .8: out.append('image presque uniforme (caméra dans un mur, ou mur nu ?)')
    return out


def _font(size):
    try:
        from hstudio.paths import FONT_PIXEL
        return ImageFont.truetype(FONT_PIXEL, size)
    except Exception:
        return ImageFont.load_default()


def sheet(st, v, items, frames, tag='apercu'):
    """items: [(shot k, [l0, l1], t)] ; frames: {t: array} -> list of jpg paths"""
    lines = read_json(os.path.join(st.version_dir(v['id']), 'lines.json'))
    w, h = THUMB[v['aspect']]; cols = COLS[v['aspect']]; f = _font(12); paths = []
    os.makedirs(st.planches, exist_ok=True)
    for n0 in range(0, len(items), PER):
        chunk = items[n0:n0 + PER]; rows = (len(chunk) + cols - 1) // cols
        im = Image.new('RGB', (cols * w, rows * (h + 34)), (12, 12, 14)); d = ImageDraw.Draw(im)
        for i, (k, ln, t) in enumerate(chunk):
            x, y = (i % cols) * w, (i // cols) * (h + 34)
            im.paste(Image.fromarray(frames[t]), (x, y + 34))
            first = v['lines'][0]
            d.text((x + 4, y + 3), f"P{k}  phrases {ln[0] + first}-{ln[1] + first}  {t + v['t0']:.1f} s", font=f, fill=(236, 230, 210))
            li = next((j for j, l in enumerate(lines) if l['start'] - .2 <= t <= l['end'] + .3), None)
            if li is not None:
                txt = lines[li]['text']
                while txt and d.textlength(txt, font=f) > w - 10: txt = txt[:-2]
                d.text((x + 4, y + 18), txt if txt == lines[li]['text'] else txt + '…', font=f, fill=(170, 170, 160))
        p = os.path.join(st.planches, f"{tag}_{v['id']}_{n0 // PER:02d}.jpg"); im.save(p, quality=88); paths.append(p)
    return paths


def make(folder, fmt='tous', plans=None, every=None, log=print, workers=RD.MAX_PS1_WORKERS, habille=False):
    st = Story(folder)
    dec, mod = PJ.build(folder, log, quiet=True)
    vs = [v for v in dec['versions'] if v['id'] in ('long_16x9', 'complet_9x16') and (fmt in (None, 'tous') or v['aspect'] == fmt)]
    if not vs: raise KitError(f'aucune version à montrer pour le format {fmt}')
    p0, p1 = (None, None)
    if plans:
        a, _, b = str(plans).partition('-'); p0, p1 = int(a), int(b or a)
    report = {}
    for v in vs:
        items = RD.sample_times(st.version_dir(v['id']))
        if p0 is not None: items = [it for it in items if p0 <= it[0] <= p1]
        if every:
            extra = []; t = 0.; ep = read_json(os.path.join(st.version_dir(v['id']), 'episode.json'))
            from hstudio.engines.pixel3d.frame import Timeline
            tl = Timeline(ep, read_json(os.path.join(st.version_dir(v['id']), 'lines.json')), float(ep['duration']))
            while t < v['dur']:
                k = tl.at(t)[0]
                if p0 is None or p0 <= k <= p1: extra.append((k, ep['shots'][k]['lines'], round(t, 3)))
                t += float(every)
            merged = []
            for k, l, t in sorted({(k, tuple(l), t) for k, l, t in list(items) + extra}, key=lambda it: it[2]):
                if not merged or t - merged[-1][2] > .15: merged.append((k, list(l), t))      # no near-duplicate instants
            items = merged
        if not items: continue
        times = [t for _, _, t in items]; size = THUMB[v['aspect']]
        log(f"aperçu {v['id']} : {len(times)} images ({dec['style'].upper()})…")
        frames = RD.voxel_stills(st, v, times, size, habille=habille) if dec['style'] == 'voxel' else RD.ps1_stills(st, v, times, size, workers)
        paths = sheet(st, v, items, frames)
        rows = []
        for k, ln, t in items:
            s = stats(frames[t]); al = alerts(s)
            rows.append(dict(plan=k, phrases=ln, t=t, **s, alertes=al))
            if al: log(f"  ! P{k} à {t:.1f} s : {', '.join(al)}")
        report[v['id']] = dict(planches=paths, images=rows)
        write_json(os.path.join(st.planches, f"apercu_{v['id']}.json"), report[v['id']])
        for p in paths: log('  ' + p)
    log('REGARDE chaque planche (visages, cibles dans le champ, objets, raccords, sous-titres) avant de rendre. Puis : verifier')
    return report
