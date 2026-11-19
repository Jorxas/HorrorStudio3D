"""Proof of the two extra CONSOLE 2D palettes and the two extra silhouettes, rendered by the real console engine.

  python tools/console_palette_sheet.py [out.png]      (default docs/world_variety/console2d_palettes.png)

The engine's own `SceneBuilder` draws every tile. `scene_palettes.apply()` installs a palette before a column and
`reset()` puts the shipped one back afterwards, so this tool proves the palettes work without editing render.py,
which is being rewritten on another branch. The last row shows the three silhouettes side by side on one background.
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from PIL import Image, ImageDraw, ImageFont
from hstudio.paths import FONT_MONTSERRAT
from hstudio.engines.console import render as RD
from hstudio.engines.console import scene_palettes as SP

SCENES = [('room', {'type': 'room', 'console_on_bed': True, 'door': True}, 'chambre'),
          ('door', {'type': 'door', 'x': .55, 'open': .18, 'light_under': 'warm'}, 'porte entrouverte'),
          ('hallway', {'type': 'hallway', 'figure': True}, 'couloir')]


def tile(pal, typ, sc, size=(300, 533)):
    SP.apply(pal)
    try:
        sb = RD.SceneBuilder(size[0], size[1])
        im = sb.render((pal, typ), dict(sc), 1.2, .4, 1.2).convert('RGB')
    finally:
        SP.reset()
    return im.resize(size, Image.LANCZOS)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'docs', 'world_variety', 'console2d_palettes.png')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    W, H = 300, 533
    pad, head, foot = 10, 46, 190
    cols = list(SP.NAMES)
    sheet = Image.new('RGB', (pad + len(cols) * (W * len(SCENES) + pad) + pad * (len(cols) - 1),
                              head + H + pad + foot), (12, 13, 18))
    try:
        f = ImageFont.truetype(FONT_MONTSERRAT, 19)
        fs = ImageFont.truetype(FONT_MONTSERRAT, 15)
    except Exception:
        f = fs = None
    d = ImageDraw.Draw(sheet)
    x = pad
    for pal in cols:
        d.text((x, 10), SP.palette(pal)['label'], fill=(236, 232, 218), font=f)
        for (typ, sc, lab) in SCENES:
            sheet.paste(tile(pal, typ, sc, (W, H)), (x, head))
            d.text((x + 8, head + H - 24), lab, fill=(220, 216, 206), font=fs)
            x += W
        x += pad * 2
    # the silhouettes, on the sepia background, drawn by scene_palettes itself
    y = head + H + pad
    strip = Image.new('RGB', (sheet.width - 2 * pad, foot - pad), tuple(SP.palette('nuit_sepia')['wall'][1]))
    sd = ImageDraw.Draw(strip)
    for i, name in enumerate(SP.SIL_NAMES):
        cx = (i + .5) * strip.width / len(SP.SIL_NAMES)
        SP.silhouette(sd, name, cx, strip.height - 30, strip.height - 50)
        sd.text((cx - 110, strip.height - 22), SP.SILHOUETTES[name]['label'][:52], fill=(226, 198, 150), font=fs)
    sheet.paste(strip, (pad, y))
    sheet.save(out)
    print(out)
    print({'palettes': list(SP.NAMES), 'silhouettes': list(SP.SIL_NAMES), 'wired_into_production': False})


if __name__ == '__main__':
    main()
