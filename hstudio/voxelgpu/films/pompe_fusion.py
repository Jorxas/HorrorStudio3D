"""« La Dernière Pompe », partie 1 : le film de FUSION. Same story, same 44 cuts, same source audio as the continuity film (`pompe_continuite.py`, kept untouched), with the four lanes wired in:

  genre   the faceless man is a supernatural, non-human creature (`genre_intent.cast_entry`: tall hunched silhouette, hollow hood, long black fingers, black hands), NOT a man in a hood;
          « il disparaît » is a DECLARED vanish (`shadow`: the pump panels and the neon are out at 26.6 s, nobody walks anywhere) and « il est là » a declared reappearance at the cut of 27.3 s,
          beside the door (`vitre_porte_est`), verified by `genre_intent.audit_vanishes`. Mood `dread` (cold, no red added), dosed per shot so the creature stays readable.
  camera  the shots that carry a dramatic purpose (the man behind the glass, the hand on the glass, the vanish, the reappearance, the torch, the car and the three metres, the door behind, the
          choice A) are planned by `cinematic_intent` on THIS blocking and frozen in `examples/remakes/pompe_fusion_cameras.json` (`tools/fusion_cameras.py` rebuilds them); every other shot keeps
          the continuity film's camera. The frozen file is checked by `blocking.preflight` (camplan) like any frame.
  face    the human face model (`plan['face'] = {'model': 'human'}`), read at FILM time by `director.build` (the stage-time bug is fixed there).
  physics seats on flat feet (`director.SEAT_H`), no overlap between actors, no wall / floor crossing (`blocking.audit`), the planted gait only if `gait='planted'` is asked.
Nothing here renders: `episode()` builds the dict, `tools/fusion_film.py` renders and verifies it.
"""
import copy, json, math
from pathlib import Path
from . import pompe_continuite as N
from . import pompe_genre_preview as PG
from .. import blocking as BLK, genre_intent as G

FPS, CUTS, T, DUR, d = N.FPS, N.CUTS, N.T, N.DUR, N.d
ROOT = Path(__file__).resolve().parents[3]
CAMERAS_FILE = ROOT / 'examples' / 'remakes' / 'pompe_fusion_cameras.json'
# where he reappears: beside the door, outside, facing the shop (the anchor `vitre_porte_est` of the continuity story, reached without a walk)
VANISH = dict(who='ghost', t=26.6, do='vanish', how='shadow', lights=['panels', 'neon'], until=27.3, appear='cut', at=[1.75, 4.05], face=math.pi)
# the continuity story walks the creature into the dark (26.2 -> 27.3) and back (27.4 -> 29.0): both walks are replaced by the vanish above
VANISH_WINDOW = PG.VANISH_WINDOW
# dread, dosed per shot: a gain on the exposure and the key where the measured creature was too dark to read (docs/FUSION_FINALE_20261029.md); a shot id missing here keeps the preset as is
# `dread` as the preset ships it (hemi .8, fill .45, rim .3) made S09 / S14 / S15 unreadable (luminance 0.04-0.07, 92-95 % deep shadow): for THIS film the ambient and fill stay near the story's own,
# and a COLD rim (never red) is kept strong enough to draw the creature's silhouette against the night. Then each shot's exposure is levelled on measured pixels (tools/fusion_levels.py).
DREAD_WORLD = dict(hemi_k=1.0, fill_k=.8, key_k=1.0, rim_k=.8, exposure_k=1.0)
LEVELS_FILE = ROOT / 'examples' / 'remakes' / 'pompe_fusion_levels.json'
DREAD_SHOT_ENV = {}


def _levels():
    return json.loads(LEVELS_FILE.read_text(encoding='utf-8')) if LEVELS_FILE.exists() else {}


def plan():
    """the continuity story, with the two walks of the creature replaced by the declared vanish, and the human face model"""
    pl = N.plan(); pl, _gone = PG._vanish_plan(pl)
    for b in pl['beats']:
        if b.get('do') == 'vanish' and b['who'] == 'ghost': b.update(VANISH)
    pl['face'] = {'model': 'human'}
    return pl


def _cameras():
    if not CAMERAS_FILE.exists(): return {}
    return json.loads(CAMERAS_FILE.read_text(encoding='utf-8'))


def episode(cameras=True, dread=1., gait='planted', levels=True):
    ep = N.episode()
    ep['title'] = 'La Dernière Pompe — partie 1 (fusion)'
    pl = plan(); _p2, vs, _lives = G.split_plan(dict(pl, duration=ep['duration']))
    ghost = ep['casts']['ghost']
    ep['casts']['ghost'] = G.cast_entry('faceless_void', hood=ghost.get('hood'), vanishes=vs)
    ep['blocking']['plan'] = pl
    if dread:
        G.apply_preset(ep, 'dread', dread); ep['world_env'].update(DREAD_WORLD)
    lv = _levels() if levels else {}
    for s in ep['shots']:
        if s['id'] in DREAD_SHOT_ENV: s['env'] = {**s['env'], **DREAD_SHOT_ENV[s['id']]}
        if s['id'] in lv: s['env'] = {**s['env'], 'exposure_k': lv[s['id']]}
    if cameras:
        for sid, c in _cameras().items():
            s = next((x for x in ep['shots'] if x['id'] == sid), None)
            if s is None: continue
            s['frame'] = c['frame']; s['camera'] = c['camera']; s['shake'] = c.get('shake', s.get('shake', .1)); s['_camera_why'] = c.get('why')
    if gait: ep['gait'] = gait
    return ep
