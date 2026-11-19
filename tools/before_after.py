"""Before / after: the same walk of the same character in the same place, with the original actor model (v1 DSL:
"at" -> "to", "move": "walk") and with the shared acting layer (v2: walk_to, skeleton, cinematographer).

  python tools/before_after.py [out.png]      (default docs/catalogue/avant_apres_marche.png)"""
import os, sys, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from PIL import Image, ImageDraw, ImageFont
from hstudio.pipeline import make_engine
from hstudio.paths import FONT_MONTSERRAT

LINES = [{'tts': '.', 'display': '', 'text': '', 'tags': [], 'dialogue': False, 'i': 0, 'start': .05, 'end': 5.0, 'segs': [[.05, 5.0]]}]
BASE = {'style': 'pixel3d', 'default_set': 'salon', 'sets': {'salon': {'type': 'living_room'}}, 'cast': {'lea': {'ref': 'lea'}},
        'hud': {'title': [], 'hearts': []}, 'lines': {}}
V1 = dict(BASE, shots=[{'lines': [0, 0], 'actors': [{'id': 'lea', 'at': [-1.6, 4.2], 'to': [1.2, 3.0], 'move': 'walk', 'facing': '+x'}],
                        'camera': {'preset': 'full', 'subject': 'lea'}, 'ui': {'hud': False, 'subs': 'off'}}])
V2 = dict(BASE, engine_version=2, shots=[{'lines': [0, 0], 'actors': [{'id': 'lea', 'at': [-1.6, 4.2], 'facing': '+x'}],
                                           'actions': [{'who': 'lea', 'do': 'walk_to', 'to': [1.2, 3.0]}, {'who': 'lea', 'do': 'look_around', 'dur': 1.4}],
                                           'camera': {'shot': 'full', 'on': ['lea']}, 'ui': {'hud': False, 'subs': 'off'}}])

def strip(ep, ts):
    eng = make_engine('pixel3d', ep, LINES, np.zeros(10), 5.2, '16:9')
    return [Image.fromarray(eng.render_lowres(t)[0]).resize((480, 270), Image.NEAREST) for t in ts]

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'docs', 'catalogue', 'avant_apres_marche.png')
    ts = [.6, 1.2, 1.8, 2.4, 3.6, 4.6]
    rows = [('AVANT (v1) : l\'acteur glisse, membres figés, caméra fixe', strip(V1, ts)),
            ('APRÈS (v2) : pas posés au sol, bras et genoux, arrêt, regard autour, caméra qui accompagne', strip(V2, ts))]
    W, H = 480, 270; pad = 10; head = 40
    sheet = Image.new('RGB', (pad + len(ts) * (W + pad), 2 * (head + H) + pad * 3), (14, 16, 22)); d = ImageDraw.Draw(sheet)
    try: f = ImageFont.truetype(FONT_MONTSERRAT, 24)
    except Exception: f = None
    for r, (title, ims) in enumerate(rows):
        y = pad + r * (head + H + pad); d.text((pad, y + 6), title, fill=(232, 228, 214), font=f)
        for i, im in enumerate(ims): sheet.paste(im, (pad + i * (W + pad), y + head))
    os.makedirs(os.path.dirname(out), exist_ok=True); sheet.save(out); print(out)

if __name__ == '__main__': main()
