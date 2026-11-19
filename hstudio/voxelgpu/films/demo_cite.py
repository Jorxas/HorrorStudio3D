"""« Le Dernier Noyau » : an original story of about 150 s, 9:16, for the fused engine (B directs, A paints), written as ONE blocking (`blocking.py`) in a city quarter with a café, an alley, a roof airport and the Moon.

Story (cause and effect):
  1. Morning in the city. Inès runs through the crowd to the café terrace where Malo waits: she brings the spare core of the Moon's beacon; without it the lights of the city die tonight, and the shuttle leaves at noon.
  2. She sets the case on a tall table to catch her breath. Vorn, who has been watching, lifts it from behind her and runs: through the terrace, into the café, to the back door -- which is locked.
  3. Cornered, Vorn puts the case on a cabinet to have both hands free. Inès arrives; fists (she parries, she lands a cross, he staggers); he draws a sword; Malo runs to the rack, takes a sword and throws it to her; two blades meet; she
     disarms him and holds the point at his throat; he flees. She takes the case back. Four minutes left.
  4. They run out of the café, along the pavement, down the alley to the freight lift; the doors close.  The lift opens on a roof: they run to the shuttle (the ramp). The shuttle lifts off, the city shrinks, the sky goes black.
  5. On the Moon they walk to the dead beacon; Inès slides the core into the console; the beacon lights; a last shot of the city lighting up.
The dialogue is a LOCAL voice (Windows speech, `localvoice.py`): a test voice, not the studio's voice. Everything the audio and the camera need is derived from the blocking and the voice durations.
Nothing here is random and nothing reads a clock.
"""
import json, math
from pathlib import Path
from .. import localvoice as LV
from . import demo_cite_cast as CAST
from ...remake.dsl import k as _k, cam

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'projects' / 'demo_narrative_20261029'
CX, AX, SX = 60., 190., 270.
c = lambda x: CX + x
a_ = lambda x: AX + x
s_ = lambda x: SX + x
PI = math.pi
FPS = 30

# ------------------------------------------------------------------------------------------------------------------------ the dialogue (local voice)
LINES = [
    dict(id='l01', speaker='ines', who='ines', text="Malo ! Je l'ai. Le noyau de rechange."),
    dict(id='l02', speaker='malo', who='malo', text="Enfin ! Il est presque midi moins vingt."),
    dict(id='l03', speaker='ines', who='ines', text="Sans lui, la balise de la Lune s'éteint, et la ville avec elle."),
    dict(id='l04', speaker='malo', who='malo', text="La navette part à midi !"),
    dict(id='l05', speaker='ines', who='ines', text="Au voleur ! Il a pris le noyau !"),
    dict(id='l06', speaker='malo', who='malo', text="Il file dans le café !"),
    dict(id='l07', speaker='vorn', who='vorn', text="Recule. Ça vaut plus que toute ta ville."),
    dict(id='l08', speaker='ines', who='ines', text="Rends-le. Ou je viens le chercher."),
    dict(id='l09', speaker='vorn', who='vorn', text="Alors voyons si tu sais te battre."),
    dict(id='l10', speaker='malo', who='malo', text="Inès ! Attrape !"),
    dict(id='l11', speaker='ines', who='ines', text="C'est fini, Vorn. Va-t'en."),
    dict(id='l12', speaker='malo', who='malo', text="Quatre minutes ! Par la ruelle !"),
    dict(id='l13', speaker='ines', who='ines_r', text="Si on rate la fenêtre, la Lune reste dans le noir."),
    dict(id='l14', speaker='malo', who='malo_r', text="On ne la ratera pas. Cours !"),
    dict(id='l15', speaker='ines', who='ines_m', text="Elle est éteinte depuis hier soir."),
    dict(id='l16', speaker='malo', who='malo_m', text="Insère-le. Doucement."),
    dict(id='l17', speaker='ines', who='ines_m', text="Allez. Éclaire-nous."),
    dict(id='l18', speaker='malo', who='malo_m', text="Regarde la Terre. Elle s'allume."),
]


def voice():
    """-> {id: {path, dur, ...}}"""
    return LV.synth_all(LINES, WORK / 'voice')


# ------------------------------------------------------------------------------------------------------------------------ the case and the swords (px boxes, held in the hand; world boxes for props)
CASE_PX = [{'x': 0, 'y': 0, 'z': 3.0, 'w': 5.0, 'h': 8.0, 'd': 3.0, 'color': '#4a5058'}, {'x': 0, 'y': 0, 'z': 4.6, 'w': 3.4, 'h': 5.4, 'd': .4, 'color': '#6ad8ff'}, {'x': 0, 'y': 4.4, 'z': 3.0, 'w': 2.4, 'h': .8, 'd': 1.2, 'color': '#c8c8c0'}]
SWORD_PX = [{'x': 0, 'y': 0, 'z': 9.5, 'w': 1.0, 'h': 2.4, 'd': 17, 'color': '#d8dce4'}, {'x': 0, 'y': 0, 'z': .6, 'w': 6, 'h': 1.0, 'd': 1.2, 'color': '#6a4a2a'}, {'x': 0, 'y': 0, 'z': -1.6, 'w': 1.4, 'h': 1.4, 'd': 3.4, 'color': '#3a2a1a'}]
CASE_W = [{'x': 0, 'y': 0.13, 'z': 0, 'w': .5, 'h': .26, 'd': .2, 'color': 0x4a5058}, {'x': 0, 'y': 0.13, 'z': .101, 'w': .34, 'h': .17, 'd': .01, 'color': 0x6ad8ff}, {'x': 0, 'y': .27, 'z': 0, 'w': .15, 'h': .05, 'd': .08, 'color': 0xc8c8c0}]
SWORD_W = [{'x': 0, 'y': 0, 'z': .6, 'w': .06, 'h': .02, 'd': 1.0, 'color': 0xd8dce4}, {'x': 0, 'y': 0, 'z': .05, 'w': .3, 'h': .06, 'd': .08, 'color': 0x6a4a2a}, {'x': 0, 'y': 0, 'z': -.15, 'w': .08, 'h': .08, 'd': .2, 'color': 0x3a2a1a}]


def swing(*pairs):
    """door table [[t, v], ...] from (t, v) pairs"""
    return [[round(t, 3), v] for t, v in pairs]


class Film:
    """collects the beats, the shots, the props and the sound of one film in absolute time"""

    def __init__(self, V):
        self.V = V; self.actors = {}; self.beats = []; self.props = []; self.sfx = []; self.notes = {}; self.talk = {}; self.placed = []; self.env = {}; self.lights = []; self.captions = []

    def actor(self, aid, start, **kw): self.actors[aid] = dict(start=start, **kw)
    def beat(self, who, t, do, **kw): b = dict(who=who, t=round(t, 3), do=do, **kw); self.beats.append(b); return b
    def go(self, who, t, to, by, **kw):
        pos = self.__dict__.setdefault('_pos', {}); prev = pos.get(who) or self.actors[who]['start']['at']; end = self.__dict__.setdefault('_end', {})
        if who in end and t < end[who] + .42:
            self.__dict__.setdefault('shift_warn', []).append(f"{who}: go t={t:.2f} décalé à {end[who] + .42:.2f} (le précédent finit à {end[who]:.2f})"); by += end[who] + .42 - t; t = end[who] + .42
        end[who] = by
        if not isinstance(to, str):
            d = math.hypot(to[0] - prev[0], to[1] - prev[1]); v = d * 1.1 / max(.05, by - t - .45); vm = self.actors[who].get('vmax', 3.8)
            if v > vm: self.__dict__.setdefault('speed_warn', []).append(f"{who} t={t:.1f}->{by:.1f}: {d:.1f} m droit, ~{v:.1f} m/s > {vm:.1f}  (il faut {d * 1.1 / vm + .45:.2f} s)")
            pos[who] = list(to)
        return self.beat(who, t, 'go', to=list(to) if not isinstance(to, str) else to, by=round(by, 3), **kw)
    def walk(self, who, t, to, v=4.2, **kw):
        """a `go` whose arrival time follows from its length (straight-line distance x 1.1 at v m/s, + the 0.45 s turn the planner allows); returns the arrival time"""
        pos = self.__dict__.setdefault('_pos', {}); prev = pos.get(who) or self.actors[who]['start']['at']
        end = self.__dict__.setdefault('_end', {}); t = max(t, end.get(who, -9.) + .42); d = math.hypot(to[0] - prev[0], to[1] - prev[1]); by = t + d * 1.1 / v + .45; self.go(who, t, to, by, **kw); return by
    def say(self, lid, t, event=None):
        L = next(l for l in LINES if l['id'] == lid); d = self.V[lid]['dur']; who = L['who']
        b = self.beat(who, t, 'talk', until=round(t + d, 3), text=L['text'])
        if event: b['event_type'] = event; b['loud'] = 1.2
        self.placed.append((t, self.V[lid])); self.talk[lid] = (t, t + d); self.captions.append(dict(t0=round(t, 3), t1=round(t + d + .15, 3), text=L['text'], who=who)); return t + d
    def sound(self, t, name, gain=.8, dur=None): self.sfx.append(dict(t=round(t, 3), name=name, gain=gain, dur=dur))
