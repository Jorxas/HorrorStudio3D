"""The game inside the console ("Ne mets pas pause"): a small deterministic simulation whose state lasts for the whole
episode, drawn on the 160x144 green screen, and linked to the real room of the player.

Shot keys
  "game": [{"at": 0.5, "do": "walk", "to": "door1" | "key" | [x, y]},  {"do": "open", "door": "door1"},
           {"do": "pick", "item": "key"}, {"do": "enemy", "pos": [x, y]}, {"do": "enemy_to", "to": [x, y]},
           {"do": "hp", "delta": -1}, {"do": "light", "on": false}, {"do": "say", "text": "...", "dur": 2.5},
           {"do": "mode", "mode": "explore|battle|inventory|gameover|pause"}]
  scene screen {"type": "game"} shows the simulation (any shot: console in the hands, full screen, split...)
Episode keys
  "game_map": "maison" | "foret" | ASCII rows,  "links": [{"when": "open:door1", "then": [...]}]   (see links.py)
Every game event is also an event of the episode (time, "game:open:door1"...) that links turn into consequences in
the room: the door creaks open, steps under the door, the lamp flickers, a heart is lost..."""
import math
from PIL import Image, ImageDraw
from ..common import font
from ...paths import FONT_PIXEL

SCR = [(8, 22, 14), (34, 74, 46), (104, 164, 86), (194, 232, 146)]
MAPS = {
 'maison': ["################",
            "#......#.......#",
            "#..k...#...E...#",
            "#......1.......#",
            "#......#.......#",
            "#......#########",
            "#......#.......#",
            "#..P...2...b...#",
            "#......#.......#",
            "################"],
 'foret':  ["################",
            "#T..T...TT..T..#",
            "#..T..k.....T..#",
            "#T...TT..T...E.#",
            "#..P......TT...#",
            "#T..T..T.....T.#",
            "#....TT...1....#",
            "################"],
}

def smooth(x): x = min(1., max(0., x)); return x * x * (3 - 2 * x)

class GameMap:
    def __init__(self, rows):
        self.rows = [r.ljust(16, '#') for r in rows]; self.h = len(self.rows); self.w = len(self.rows[0])
        self.items = {}; self.doors = {}; self.start = (1, 1); self.enemy0 = None
        for y, r in enumerate(self.rows):
            for x, ch in enumerate(r):
                if ch == 'P': self.start = (x, y)
                elif ch == 'E': self.enemy0 = (x, y)
                elif ch == 'k': self.items['key'] = (x, y)
                elif ch == 'b': self.items['book'] = (x, y)
                elif ch.isdigit(): self.doors['door' + ch] = (x, y)
    def solid(self, x, y, doors):
        if not (0 <= x < self.w and 0 <= y < self.h): return True
        ch = self.rows[y][x]
        if ch in '#T': return True
        if ch.isdigit(): return doors.get('door' + ch, 0.) < .5
        return False
    def path(self, a, b, doors):
        """BFS on tiles; closed doors are walkable only as the goal (the hero stops in front)"""
        from collections import deque
        a = (int(round(a[0])), int(round(a[1]))); b = (int(b[0]), int(b[1]))
        q = deque([a]); came = {a: None}
        while q:
            c = q.popleft()
            if c == b: break
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (c[0] + dx, c[1] + dy)
                if n in came: continue
                if n != b and self.solid(n[0], n[1], doors): continue
                came[n] = c; q.append(n)
        if b not in came: return [a]
        out = []; c = b
        while c is not None: out.append(c); c = came[c]
        out = out[::-1]
        if len(out) > 1 and self.solid(b[0], b[1], doors): out = out[:-1]           # stop in front of a closed door
        return out

class GameTimeline:
    """compiles the "game" events of every shot (absolute times) into a state you can query at any time"""
    def __init__(self, episode, spans, extra=None):
        m = episode.get('game_map', 'maison')
        self.map = GameMap(MAPS.get(m, MAPS['maison']) if isinstance(m, str) else m)
        self.events = []                      # (t, name, data)  ->  links
        self.walks = []; self.doors = {}; self.picks = {}; self.hp = []; self.light = []; self.says = []; self.modes = []
        self.enemy = []
        self.pos_ = self.map.start; self.t_free = 0.; self.dstate = {}
        self.max_hp = int(episode.get('game_hp', 3)); self.hp_v = self.max_hp
        extra = sorted(extra or [], key=lambda e: e[0])
        for k, shot in enumerate(episode['shots']):
            t0 = spans[k][0]
            for ev in shot.get('game') or []:
                t = t0 + float(ev['at']) if ev.get('at') is not None else max(t0, self.t_free)
                while extra and extra[0][0] <= t: self.apply(*extra.pop(0))
                self.apply(t, ev)
        for e in extra: self.apply(*e)
        self.events.sort(key=lambda e: e[0])

    def apply(self, t, ev):
        do = ev.get('do')
        if do == 'walk':
            tg = ev.get('to'); goal = self.map.doors.get(tg) or self.map.items.get(tg) or (tuple(tg) if isinstance(tg, (list, tuple)) else None)
            if goal is None: return
            pts = self.map.path(self.pos_, goal, self.dstate)
            if len(pts) > 1:
                sp = float(ev.get('speed', 3.5)); self.walks.append((t, sp, pts)); self.t_free = t + (len(pts) - 1) / sp; self.pos_ = pts[-1]
                self.events.append((t, 'walk', {}))
        elif do in ('open', 'close'):
            did = ev.get('door', 'door1'); v = 1. if do == 'open' else 0.
            self.doors.setdefault(did, []).append((t, v)); self.dstate[did] = v
            self.events.append((t, f'{do}:{did}', {'door': did})); self.t_free = max(self.t_free, t + .5)
        elif do == 'pick':
            it = ev.get('item', 'key'); self.picks[it] = t; self.events.append((t, f'pick:{it}', {'item': it}))
        elif do in ('enemy', 'enemy_to'):
            p = ev.get('pos', ev.get('to')); self.enemy.append((t, tuple(p) if p else None, float(ev.get('dur', 1.2))))
            if do == 'enemy': self.events.append((t, 'enemy', {}))
        elif do == 'hide_enemy': self.enemy.append((t, None, 0.)); self.events.append((t, 'hide_enemy', {}))
        elif do == 'hp':
            self.hp_v = max(0, min(self.max_hp, self.hp_v + int(ev.get('delta', -1)))); self.hp.append((t, self.hp_v)); self.events.append((t, 'hp', {'hp': self.hp_v}))
            if self.hp_v == 0: self.events.append((t + .2, 'gameover', {})); self.modes.append((t + .2, 'gameover', {}))
        elif do == 'light':
            on = bool(ev.get('on', False)); self.light.append((t, on)); self.events.append((t, 'light_on' if on else 'light_off', {}))
        elif do == 'say':
            self.says.append((t, t + float(ev.get('dur', 2.5)), str(ev.get('text', '')), ev.get('speaker'))); self.events.append((t, 'say', {}))
        elif do == 'mode':
            self.modes.append((t, ev.get('mode', 'explore'), ev)); self.events.append((t, 'mode:' + ev.get('mode', 'explore'), {}))

    # ---------------- state at time g
    def pos(self, g):
        p = self.map.start; moving = False; facing = (0, 1)
        for (t, sp, pts) in self.walks:
            if g < t: break
            f = (g - t) * sp
            if f >= len(pts) - 1: p = pts[-1]; facing = (pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1]) if len(pts) > 1 else facing; continue
            i = int(f); u = f - i; a, b = pts[i], pts[i + 1]
            p = (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u); moving = True; facing = (b[0] - a[0], b[1] - a[1])
        return p, moving, facing
    def door(self, did, g):
        v = 0.
        for (t, a) in self.doors.get(did, []):
            if g >= t: v = v + (a - v) * smooth((g - t) / .5)
        return v
    def hp_at(self, g):
        h = self.max_hp
        for (t, v) in self.hp:
            if g >= t: h = v
        return h
    def has_hp(self): return bool(self.hp)
    def light_at(self, g):
        on = True
        for (t, v) in self.light:
            if g >= t: on = v
        return on
    def enemy_at(self, g):
        p = None; prev = self.map.enemy0
        for (t, q, dur) in self.enemy:
            if g < t: break
            if q is None: p = None; continue
            src = p if p is not None else (q if prev is None else q)
            k = smooth((g - t) / max(dur, 1e-3)) if dur else 1.
            p = (src[0] + (q[0] - src[0]) * k, src[1] + (q[1] - src[1]) * k) if p is not None else q
            prev = q
        return p
    def mode_at(self, g):
        m = ('explore', {})
        for (t, mode, ev) in self.modes:
            if g >= t: m = (mode, ev)
        return m
    def say_at(self, g):
        for (a, b, txt, sp) in self.says:
            if a <= g < b: return txt, sp, g - a
        return None

# ---------------- drawing on the 160x144 screen
def _px(d, x, y, rows, col):
    for j, r in enumerate(rows):
        for i, c in enumerate(r):
            if c != '.': d.point((x + i, y + j), fill=SCR[int(c)])

HERO = [["..33..", ".3333.", ".3003.", ".3333.", "..22..", ".2222.", "2.22.2", "..22..", ".2..2.", ".2..2."],
        ["..33..", ".3333.", ".3003.", ".3333.", "..22..", ".2222.", "2.22.2", "..22..", "..22..", ".2..2."]]
SHADOW = ["..1111..", ".111111.", "11311311", "11111111", "11111111", "11111111", "1.11.11.", "........"]
KEY = ["..33....", ".3..3333", "..33.3.3"]
BOOK = ["2222", "2332", "2222"]

def draw_game(gt, g, W=160, H=144, title=None):
    im = Image.new('RGB', (W, H), SCR[0]); d = ImageDraw.Draw(im); d.fontmode = '1'; F8 = font(FONT_PIXEL, 8)
    mode, mev = gt.mode_at(g)
    if mode == 'gameover':
        d.text((40, 52), 'GAME OVER', fill=SCR[3], font=F8); d.text((34, 80), 'CONTINUER ? ' + str(max(0, 9 - int(g * 1.5) % 10)), fill=SCR[2]); return im
    p, moving, facing = gt.pos(g); T = 10
    ox = max(0, min(gt.map.w * T - W, int(p[0] * T + T / 2 - W / 2))); oy = max(0, min(gt.map.h * T - (H - 14), int(p[1] * T + T / 2 - (H - 14) / 2)))
    for y, r in enumerate(gt.map.rows):
        for x, ch in enumerate(r):
            X, Y = x * T - ox, y * T - oy + 14
            if X < -T or X > W or Y < 4 or Y > H: continue
            if ch == '#':
                d.rectangle([X, Y, X + T - 1, Y + T - 1], fill=SCR[1]); d.line([X, Y + T - 1, X + T - 1, Y + T - 1], fill=SCR[0])
            elif ch == 'T':
                d.polygon([(X + 5, Y), (X + 9, Y + 7), (X + 1, Y + 7)], fill=SCR[2]); d.rectangle([X + 4, Y + 7, X + 5, Y + 9], fill=SCR[1])
            elif ch.isdigit():
                o = gt.door('door' + ch, g)
                d.rectangle([X, Y, X + T - 1, Y + T - 1], fill=SCR[0])
                if o < .99: d.rectangle([X + int(8 * o), Y + 1, X + T - 2, Y + T - 2], fill=SCR[2]); d.point((X + T - 4, Y + 5), fill=SCR[3])
            else:
                if (x + y) % 2 == 0: d.point((X + 4, Y + 4), fill=SCR[1])
    for it, (ix, iy) in gt.map.items.items():
        if it in gt.picks and g >= gt.picks[it]: continue
        X, Y = ix * T - ox + 1, iy * T - oy + 17
        if (g * 3) % 2 < 1.6: _px(d, X, Y, KEY if it == 'key' else BOOK, None)
    e = gt.enemy_at(g)
    if e is not None:
        X, Y = int(e[0] * T - ox + 1), int(e[1] * T - oy + 15 + math.sin(g * 4) * 1.2); _px(d, X, Y, SHADOW, None)
    frame = HERO[int(g * 8) % 2] if moving else HERO[0]
    _px(d, int(p[0] * T - ox + 2), int(p[1] * T - oy + 14), frame, None)
    if not gt.light_at(g):                                   # darkness: only a small circle of light around the hero
        import numpy as np
        a = np.asarray(im).copy(); yy, xx = np.mgrid[0:H, 0:W]; cx, cy = p[0] * T - ox + 5, p[1] * T - oy + 19
        dark = ((xx - cx) ** 2 + (yy - cy) ** 2) > 22 ** 2; a[dark & (yy > 13)] = SCR[0]; im = Image.fromarray(a); d = ImageDraw.Draw(im); d.fontmode = '1'
    # HUD: hearts and inventory
    d.rectangle([0, 0, W, 12], fill=SCR[0]); d.line([0, 12, W, 12], fill=SCR[1])
    for i in range(gt.max_hp):
        x = 4 + i * 10; full = i < gt.hp_at(g)
        d.polygon([(x, 4), (x + 2, 2), (x + 4, 4), (x + 6, 2), (x + 8, 4), (x + 4, 9)], fill=SCR[3] if full else None, outline=SCR[2])
    inv = [it for it, t in gt.picks.items() if g >= t]
    for i, it in enumerate(inv[:4]): _px(d, W - 12 - i * 12, 4, KEY if it == 'key' else BOOK, None)
    if title: d.text((60, 3), title[:10], fill=SCR[2], font=F8)
    sy = gt.say_at(g)
    if sy:
        txt, sp, tl = sy; txt = txt.upper()[:max(1, int(len(txt) * min(1., tl / max(.5, len(txt) * .045))))]
        d.rectangle([3, H - 40, W - 4, H - 4], fill=SCR[0], outline=SCR[3])
        words = txt.split(); lines = []; cur = ''
        for w in words:
            if len(cur) + len(w) + 1 > 18: lines.append(cur); cur = w
            else: cur = (cur + ' ' + w).strip()
        if cur: lines.append(cur)
        for i, l in enumerate(lines[-3:]): d.text((8, H - 36 + i * 10), l, fill=SCR[3], font=F8)
    if mode == 'pause':
        d.rectangle([40, 50, 120, 90], fill=SCR[0], outline=SCR[3]); d.text((62, 58), 'PAUSE', fill=SCR[3], font=F8); d.text((48, 74), 'NE METS PAS', fill=SCR[2], font=F8)
    return im
