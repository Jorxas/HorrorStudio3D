"""Portrait of a library character, drawn by the PIXEL 3D engine itself (no image API): a medium shot in a neutral
lit room, cached next to the projects and redrawn when the character file changes."""
import os, numpy as np
from PIL import Image
from ... import paths
from ...acting import cast as CAST

CACHE = os.path.join(paths.PROJECTS, '_cache', 'portraits')

def portrait(cid):
    """path of the PNG portrait of a character (made on first request)"""
    src = os.path.join(CAST.CHAR_DIR, f'{cid}.json')
    if not os.path.exists(src): return None
    out = os.path.join(CACHE, f'{cid}_{int(os.path.getmtime(src))}.png')
    if os.path.exists(out): return out
    from ...pipeline import make_engine
    c = CAST.character(cid) or {}
    animal = (c.get('look') or {}).get('kind') is not None
    ep = {'engine_version': 2, 'style': 'pixel3d', 'default_set': 'studio', 'cast': {cid: {'ref': cid}}, 'hud': {'title': [], 'hearts': []},
          'sets': {'studio': {'type': 'room', 'rooms': [{'id': 'studio', 'origin': [0, 0], 'size': [6, 6], 'walls': 'plaster', 'floor': 'wood',
                                                          'light': 'neon', 'light_power': 1.3, 'clean': True}]}},
          'lines': {}, 'shots': [{'lines': [0, 0], 'actors': [{'id': cid, 'at': [0, 3.0], 'facing': '-z', 'face': 'happy'}],
                                  'camera': {'shot': 'full' if animal else 'medium', 'on': [cid], 'angle': 'three_quarter'}, 'ui': {'hud': False, 'subs': 'off'},
                                  'lights': [{'at': [.9, 2.1, 1.7], 'y': 2.1, 'color': [1, .93, .82], 'power': 1.5, 'radius': 3.5},
                                             {'at': [-1.2, 1.6, 2.0], 'y': 1.6, 'color': [.7, .78, 1], 'power': .5, 'radius': 3.}]}]}
    lines = [{'tts': '.', 'display': '', 'text': '', 'tags': [], 'dialogue': False, 'i': 0, 'start': .05, 'end': 1.0, 'segs': [[.05, 1.0]]}]
    eng = make_engine('pixel3d', ep, lines, np.zeros(10), 1.2, '9:16')
    lo = eng.render_lowres(.6)[0]; h, w = lo.shape[:2]
    ob = eng.qc_observe(.6) or {}; uv = ((ob.get('people') or {}).get(cid) or {}).get('uv')        # the head, projected
    y0 = int((1 - uv[1]) / 2 * h - w * (.3 if animal else .38)) if uv else int(h * .12); y0 = max(0, min(h - w, y0))
    im = Image.fromarray(lo).crop((0, y0, w, y0 + w)).resize((w * 2, w * 2), Image.NEAREST)
    os.makedirs(CACHE, exist_ok=True)
    for f in os.listdir(CACHE):
        if f.startswith(cid + '_'): os.remove(os.path.join(CACHE, f))
    im.save(out); return out
