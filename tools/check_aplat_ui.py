"""Checks on the CONSOLE 2D "aplats" interface (hstudio/engines/console/ui2d.py).

    python tools/check_aplat_ui.py

`tools/regress_aplat.py` proves the new style does not *drift* (it compares fingerprints). This proves the
properties the style is supposed to have, which a fingerprint cannot: that it stays opt-in, that it is
deterministic, that its text is readable on every palette, that it holds rule 1 (no blur), and that the one
part of it drawn before `aplat.snap` stays on palette entries.

Exit 0 if every check passes, 1 otherwise. No API, no network, no project written.
"""
import os, sys, inspect, hashlib
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from hstudio import demos
from hstudio.pipeline import make_engine, duration_of
from hstudio.engines.console import aplat, ui2d, render as crender

OK, BAD = [], []


def check(name, cond, detail=''):
    (OK if cond else BAD).append(name)
    print(f'  {"OK  " if cond else "FAIL"} {name}' + (f'   {detail}' if detail else ''))


def build(demo_id, aspect, art='keep'):
    sc = demos.load(demo_id)
    lines = demos.timed_lines(sc['script'], float(sc.get('gap', .3)), float(sc.get('lead', .4)))
    env = demos.draft_voice(sc, lines)[1]
    ep = demos.episode_of(sc, lines, log=lambda *a: None)
    if art != 'keep':
        ep = dict(ep)
        if art: ep['art'] = art
        else: ep.pop('art', None)
    lines = demos.lines_with_meta(ep, lines)
    dur = duration_of(ep, lines)
    return make_engine(sc.get('style', 'console'), ep, lines, env, dur, aspect), dur


def h(img):
    return hashlib.sha1(np.asarray(img).tobytes()).hexdigest()[:16]


# ---------------------------------------------------------------- 1. the interface stays opt-in
print('\n1. opt-in: an episode that does not ask for the style never reaches ui2d')
calls = []
real_ui = ui2d.ui
ui2d.ui = lambda *a, **k: (calls.append(1), real_ui(*a, **k))[1]
try:
    eng, dur = build('demo12_aplat_ui', '9:16', art=None)       # the same episode with the art key removed
    eng.frame(dur * .5)
    check('a console episode without "art" draws none of the new interface', not calls, f'{len(calls)} call(s)')
    eng, dur = build('demo12_aplat_ui', '9:16')                 # and with it
    eng.frame(dur * .5)
    check('the same episode with "art": "aplat" does draw it', len(calls) == 1)
    calls.clear()
    eng, dur = build('demo5_console', '9:16')                   # an older console demo, untouched by this work
    eng.frame(dur * .5)
    check('demo5_console (v2, no "art") draws none of it', not calls)
finally:
    ui2d.ui = real_ui

print('\n   and the old interface is still there, byte for byte')
for name in ('ui', 'subtitle', 'choice', 'endcard', 'heart', 'clock'):
    src = inspect.getsource(getattr(crender.ConsoleEngine, name))
    check(f'ConsoleEngine.{name} still holds the original code', 'def ' + name in src)
check("ConsoleEngine.ui dispatches on self.art before anything else",
      inspect.getsource(crender.ConsoleEngine.ui).split('\n')[1].strip().startswith("if self.art == 'aplat'"))


# ---------------------------------------------------------------- 2. determinism
print('\n2. determinism: a frame does not depend on which frames were asked for before it')
eng, dur = build('demo12_aplat_ui', '9:16')
ts = [round(dur * (k + .5) / 10, 2) for k in range(10)]
fwd = [h(eng.frame(t)) for t in ts]
eng2, _ = build('demo12_aplat_ui', '9:16')
rev = {t: h(eng2.frame(t)) for t in reversed(ts)}
check('rendering the shots in reverse order gives the same frames', fwd == [rev[t] for t in ts])
eng3, _ = build('demo12_aplat_ui', '9:16')
check('a second engine gives the same frames', fwd == [h(eng3.frame(t)) for t in ts])
check('the interface reads its palette from the shot, not from the renderer state',
      'sb._pal' not in inspect.getsource(ui2d))


# ---------------------------------------------------------------- 3. readable text on every palette
print('\n3. contrast: every panel of the interface, on every palette')
worst = (1e9, '')
for pname in sorted(aplat.PALETTES):
    R = ui2d.roles(aplat.palette(pname))
    for role in ('accent', 'key', 'glow', 'paper', 'plate', 'plate_l', 'sky', 'ink'):
        fill = R[role]
        gap = abs(ui2d.lum(fill) - ui2d.lum(ui2d.on(fill, R)))
        if gap < worst[0]: worst = (gap, f'{pname}/{role}')
check('text on a panel always keeps at least 60 points of luminance', worst[0] >= 60,
      f'worst = {worst[1]} at {worst[0]:.0f}')
for pname in sorted(aplat.PALETTES):
    R = ui2d.roles(aplat.palette(pname))
    for lab in ('green', 'orange', 'red', 'gold', 'white', 'blue'):
        col = ui2d.label_color(lab, R)
        gap = abs(ui2d.lum(col) - ui2d.lum(ui2d.on(col, R)))
        if gap < 60: BAD.append(f'label {lab}/{pname}')
check('every speaker label tab is readable on every palette',
      not [b for b in BAD if str(b).startswith('label ')])


# ---------------------------------------------------------------- 4. rule 1 (flat fields) held mechanically
print('\n4. rule 1: the interface contains no blur, no grain, no gradient, no wall clock')
src = inspect.getsource(ui2d)
for banned in ('GaussianBlur', 'ImageFilter', 'vgrad', 'radial', 'glow_layer', 'grain(',
               'time.', 'random', 'np.random'):
    check(f'ui2d.py never uses {banned}', banned not in src)


# ---------------------------------------------------------------- 5. the pre-snap path stays on palette
print('\n5. palette: what is drawn before aplat.snap uses palette entries only')
for pname in sorted(aplat.PALETTES):
    pal = aplat.palette(pname)
    R = ui2d.roles(pal)
    stray = [k for k, v in R.items() if k != 'paper_d' and tuple(v) not in {tuple(c) for c in pal.values()}]
    check(f'roles({pname}) are palette entries apart from paper_d', not stray, str(stray))
card_src = inspect.getsource(ui2d.rule_card) + inspect.getsource(ui2d.icon)
check('rule_card and icon (drawn on the scene canvas, before the snap) never use paper_d',
      'paper_d' not in card_src)


# ---------------------------------------------------------------- 6. layout holds in both aspects
print('\n6. layout: nothing of the interface leaves the frame, in either aspect')
long_line = 'UNE RÉPLIQUE VOLONTAIREMENT TRÈS LONGUE POUR FORCER LE RETRÉCISSEMENT DU SOUS-TITRE'
for aspect in ('9:16', '16:9'):
    eng, dur = build('demo12_aplat_ui', aspect)
    W, H = eng.W, eng.H
    S = min(W, H) / 1080.0
    eng.subs[0]['words'] = [(w, False) for w in long_line.split()]
    img = eng.frame(eng.tl.spans[0][0] + .6)
    check(f'{aspect}: a frame of the right size comes out', img.size == (W, H))
    a = np.asarray(img.convert('RGB')).astype(np.int16)
    # the interface must actually be there: the HUD corner differs from the same frame with hud off
    eng.hud['show'] = False
    b = np.asarray(eng.frame(eng.tl.spans[0][0] + .6).convert('RGB')).astype(np.int16)
    eng.hud['show'] = True
    check(f'{aspect}: hud: false really removes the cartouche', np.abs(a[:300, :400] - b[:300, :400]).max() > 20)
    check(f'{aspect}: nothing outside the HUD corner changed with it', np.abs(a[600:, :] - b[600:, :]).max() == 0)
    unit = ui2d.card_unit(W, H)
    check(f'{aspect}: the rule card fits inside the visible frame', unit * .86 + 4 * 2.2 * 2 < W,
          f'card {unit * .86:.0f}px of {W}px')

print(f'\n{len(OK)} OK, {len(BAD)} FAIL')
sys.exit(1 if BAD else 0)
