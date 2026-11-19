"""Links between the game in the console and the real room ("Ne mets pas pause").

"links": [{"when": "open:door1" | "open:*" | "enemy" | "hp" | "light_off" | "pick:*" | "gameover" | "world:door" | ...,
           "then": [{"world": "door", "value": .4, "dur": 2.0, "dt": .3},      # the real door opens a little, .3 s later
                    {"world": "feet", "value": true}, {"world": "light_under", "value": "orange"},
                    {"world": "flicker", "dur": 1.2}, {"world": "dim", "value": .5}, {"world": "knock", "times": [0, .3, .6]},
                    {"sfx": "creak", "gain": .6}, {"game": {"do": "open", "door": "door2"}}]}]
Default links (turned off by "links_default": false) make the story coherent without writing anything:
a door opened in the game creaks open in the room, an enemy in the game puts two feet under the real door, a heart lost
in the game makes the lamp flicker, the game light going out dims the room... World events of a shot
("world": [{"at": 1.0, "door": .5}] / {"feet": true} / {"knock": [0, .4]}) can in turn act on the game ("world:door")."""
import fnmatch

DEFAULT_LINKS = [
    {'when': 'open:*', 'then': [{'world': 'door', 'value': .35, 'dur': 2.2, 'dt': .25}, {'sfx': 'door_handle', 'gain': .5, 'dt': .05}, {'sfx': 'creak', 'gain': .6, 'dt': .3}]},
    {'when': 'enemy', 'then': [{'world': 'feet', 'value': True, 'dt': .4}, {'world': 'light_under', 'value': 'warm'}, {'sfx': 'footsteps_walk', 'dur': 1.8, 'gain': .35, 'dt': .2}]},
    {'when': 'hide_enemy', 'then': [{'world': 'feet', 'value': False}]},
    {'when': 'hp', 'then': [{'world': 'flicker', 'dur': 1.3}, {'sfx': 'chip_alert', 'gain': .45}]},
    {'when': 'light_off', 'then': [{'world': 'dim', 'value': .5, 'dt': .15}, {'sfx': 'click', 'gain': .5, 'dt': .1}]},
    {'when': 'light_on', 'then': [{'world': 'dim', 'value': 0.}]},
    {'when': 'pick:*', 'then': [{'sfx': 'chip_save', 'gain': .4}]},
    {'when': 'gameover', 'then': [{'world': 'dim', 'value': .75, 'dur': 1.5}, {'sfx': 'chip_gameover', 'gain': .6}]},
    {'when': 'mode:pause', 'then': [{'sfx': 'chip_pause', 'gain': .5}]},
]

def smooth(x): x = min(1., max(0., x)); return x * x * (3 - 2 * x)

class World:
    """state of the real room over the episode, from world events and game -> world links"""
    def __init__(self, episode, spans, game):
        rules = (DEFAULT_LINKS if episode.get('links_default', True) else []) + list(episode.get('links') or [])
        self.changes = []; self.sfx = []; self.extra_game = []
        evs = []
        for k, shot in enumerate(episode['shots']):
            t0 = spans[k][0]
            for w in shot.get('world') or []:
                t = t0 + float(w.get('at', 0.))
                for key in ('door', 'feet', 'light_under', 'dim', 'flicker', 'knock'):
                    if key in w:
                        self.add(t, key, w[key], float(w.get('dur', 1.0)))
                        evs.append((t, 'world:' + key, w))
        if game is not None: evs += list(game.events)
        for (t, name, data) in sorted(evs, key=lambda e: e[0]):
            for r in rules:
                if not fnmatch.fnmatch(name, r.get('when', '')): continue
                for c in r.get('then') or []:
                    tt = t + float(c.get('dt', 0.))
                    if 'world' in c: self.add(tt, c['world'], c.get('value', True if c['world'] != 'knock' else c.get('times', [0, .35, .7])), float(c.get('dur', 1.0)))
                    if 'sfx' in c: self.sfx.append((tt, 'sfx', None, {'name': c['sfx'], 'gain': float(c.get('gain', .6)), 'dur': c.get('dur')}))
                    if 'game' in c: self.extra_game.append((tt, c['game']))
        self.changes.sort(key=lambda c: c[0])

    def add(self, t, key, value, dur):
        self.changes.append((t, key, value, dur))

    def at(self, g):
        """-> dict(door=0..1, feet, light_under, dim, flicker, knock=[relative times])"""
        st = {'door': 0., 'feet': False, 'light_under': None, 'dim': 0., 'flicker': False, 'knock': [], 'touched': set()}
        for (t, key, v, dur) in self.changes:
            if g < t: break
            st['touched'].add(key)
            if key == 'door': st['door'] = st['door'] + (float(v) - st['door']) * smooth((g - t) / max(dur, 1e-3))
            elif key == 'dim': st['dim'] = st['dim'] + (float(v) - st['dim']) * smooth((g - t) / .4)
            elif key == 'flicker': st['flicker'] = g < t + dur
            elif key == 'knock': st['knock'] = [t + float(x) for x in (v if isinstance(v, list) else [0, .35, .7])]
            else: st[key] = v
        return st
