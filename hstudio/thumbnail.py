"""Thumbnails: YouTube 1280x720 + vertical cover 1080x1920, built from the episode's most striking shot."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from .paths import FONT_PIXEL, FONT_BEBAS, FONT_MONTSERRAT
from .publish import choices as episode_choices, episode_label

def _font(path, s, var=None):
    f = ImageFont.truetype(path, s)
    if var:
        try: f.set_variation_by_name(var)
        except Exception: pass
    return f

def _outlined(im, xy, s, fnt, fill, out=8, glow=None):
    layer = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(layer); x, y = xy
    for dx in range(-out, out + 1, 2):
        for dy in range(-out, out + 1, 2):
            if dx * dx + dy * dy <= out * out: d.text((x + dx, y + dy), s, font=fnt, fill=(0, 0, 0, 255))
    d.text((x, y), s, font=fnt, fill=fill + (255,))
    if glow:
        gl = Image.new('RGBA', im.size, (0, 0, 0, 0)); ImageDraw.Draw(gl).text((x, y), s, font=fnt, fill=glow + (255,))
        gl = gl.filter(ImageFilter.GaussianBlur(14)); im.alpha_composite(gl)
    im.alpha_composite(layer)

def _best_time(eng, ep):
    spans = eng.ctx.tl.spans if hasattr(eng, 'ctx') else eng.tl.spans
    th = ep.get('thumbnail') or {}
    k = th.get('shot')
    if k is None:          # most "scary" shot: creature / double close-up, else the middle shot
        score = []
        for i, s in enumerate(ep['shots']):
            sc = 0; cam = s.get('camera', {}) or {}
            for a in s.get('actors', []) or []:
                if a.get('face') in ('creature', 'grin'): sc += 3
                if a.get('face') == 'double': sc += 2
            if cam.get('preset') in ('closeup',): sc += 2
            if (s.get('scene') or {}).get('type') in ('face', 'door'): sc += 1
            if (s.get('ui') or {}).get('endcard') or (s.get('fx') or {}).get('black'): sc -= 10
            score.append(sc)
        k = int(np.argmax(score))
    k = max(0, min(len(spans) - 1, int(k))); a, b = spans[k]
    return a + (b - a) * float(th.get('time', .6))

def _vote_badge(ep):
    """'A OU B ?' / 'A, B OU C ?' only when the episode really writes a choice; '' otherwise (nothing is invented)"""
    ls = [c['letter'] for c in episode_choices(ep)]
    if not ls:
        return ''
    return ((', '.join(ls[:-1]) + ' OU ' + ls[-1]) if len(ls) > 2 else ' OU '.join(ls)) + ' ?'


def _part_badge(meta, ep, vote):
    """the label written by the owner ('PARTIE 4', 'NIVEAU 2'), else the one of the episode; an episode that ends
    on a choice is never announced as a complete story"""
    meta = meta or {}
    return (meta.get('part_label') or episode_label(meta, ep) or ('À SUIVRE' if vote else 'HISTOIRE COMPLÈTE')).upper()


def make_thumbnails(pr, ep, lines, env, dur, text_lines=None, log=print):
    from .pipeline import make_engine
    style = pr.meta.get('style', 'pixel3d')
    hud = ep.get('hud', {}) or {}
    title = hud.get('title') or [pr.meta.get('series', '')]
    vote = _vote_badge(ep)
    # an episode that ends on a choice is not a complete story: say the episode, or "à suivre"
    part = _part_badge(pr.meta, ep, vote)
    for aspect, (W, H), name in (('16:9', (1280, 720), 'thumbnail_16x9.jpg'), ('9:16', (1080, 1920), 'cover_9x16.jpg')):
        eng = make_engine(style, ep, lines, env, dur, aspect)
        g = _best_time(eng, ep)
        bg = eng.raw_frame(g).resize((W, H), Image.NEAREST if style == 'pixel3d' else Image.LANCZOS)
        a = np.asarray(bg).astype(np.float32)
        if aspect == '16:9':
            xx = np.arange(W)[None, :, None] / W; a *= np.clip(.15 + 1.2 * (xx - .05), .15, 1.0)
        else:
            yy = np.arange(H)[:, None, None] / H; a *= np.clip(.25 + 1.4 * (yy - .1), .25, 1.0)
        im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert('RGBA')
        d = ImageDraw.Draw(im)
        if style == 'pixel3d':
            f1 = _font(FONT_PIXEL, 64 if aspect == '16:9' else 84); f2 = _font(FONT_PIXEL, 40 if aspect == '16:9' else 56)
            x0, y0 = (48, 120) if aspect == '16:9' else (60, 170)
            badge = part
            fb = _font(FONT_PIXEL, 24 if aspect == '16:9' else 34); bw = d.textlength(badge, font=fb)
            d.rectangle([x0 - 4, y0 - 84, x0 + bw + 26, y0 - 26], fill=(214, 22, 22, 255), outline=(0, 0, 0, 255), width=4)
            d.text((x0 + 12, y0 - 68), badge, font=fb, fill=(255, 255, 255, 255))
            y = y0
            for i, t in enumerate((text_lines or title)[:3]):
                fnt = f1 if i == 0 else f2
                _outlined(im, (x0, y), t.upper(), fnt, (240, 34, 30) if i == 1 and len(title) > 1 and text_lines is None else (245, 240, 228),
                          8, (255, 30, 20) if i == 0 else None)
                y += (110 if i == 0 else 80) if aspect == '16:9' else (150 if i == 0 else 110)
            if vote:                       # same pixel font as the rest of the engine, no vector lettering here
                fv = _font(FONT_PIXEL, 30 if aspect == '16:9' else 44)
                # 16:9 bottom left (the duration badge sits on the right); 9:16 under the title, clear of the
                # caption and the buttons that TikTok / Shorts draw over the lower part of the cover
                vw = d.textlength(vote, font=fv); vy = H - 104 if aspect == '16:9' else min(y + 30, H - 420)
                d.rectangle([x0 - 4, vy - 16, x0 + vw + 30, vy + (50 if aspect == '16:9' else 72)],
                            fill=(12, 12, 14, 240), outline=(214, 22, 22, 255), width=4)
                d.text((x0 + 13, vy), vote, font=fv, fill=(245, 240, 228, 255))
        else:
            fb = _font(FONT_BEBAS, 150 if aspect == '16:9' else 220); fs = _font(FONT_MONTSERRAT, 40 if aspect == '16:9' else 60, 'Black')
            x0, y0 = (56, 90) if aspect == '16:9' else (70, 200)
            tl = text_lines or [hud.get('series', pr.meta.get('series', 'NE METS PAS PAUSE'))]
            y = y0
            for i, t in enumerate(tl[:3]):
                _outlined(im, (x0, y), t.upper(), fb, (255, 201, 60) if i == len(tl[:3]) - 1 else (240, 240, 245), 6)
                y += (140 if aspect == '16:9' else 210)
            _outlined(im, (x0 + 4, y + 10), (pr.meta.get('part_label') or hud.get('level', '') or part).upper(), fs, (232, 52, 64), 4)
            if vote:                       # flat vector style: no pixel font on the console engine
                fv = _font(FONT_BEBAS, 76 if aspect == '16:9' else 110)
                _outlined(im, (x0, y + (54 if aspect == '16:9' else 76)), vote, fv, (255, 201, 60), 5)
        im.convert('RGB').save(pr.p(name), quality=92)
    log('Miniature YouTube (1280x720) et couverture verticale (1080x1920) créées.')
