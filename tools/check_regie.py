"""Tests of the actor direction added on top of the régie: the gaze controller (acting/gaze.py) and the path
footing (acting/timeline.py, "eyeline": "smooth" / "footing": "path"). No rendering, no network, no API: the shared acting layer only.

  python tools/check_regie.py            # exit 1 on the first failure

What is checked
  opt-in            an episode that asks for nothing is bit-for-bit the old behaviour, on both engines
  determinism       building the same episode twice gives the same angles, and sampling order does not matter
  gaze speed        the head never turns faster than the configured speed (plus whatever the body itself turns)
  gaze snaps        the measured one-frame gaze jumps collapse on real episodes
  anticipation      before a cut the gaze has already left for the target of the next shot
  continuity        a cut inside a set does not reset the head
  neck limit        the solved gaze stays inside the cone the engines draw (no +54 -> -54 flip)
  footing heading   a character walking a path faces where they walk, not where the quarter turn left them
  foot plant        the stance foot stops sliding, and a walk ends with the feet together
  cast / animals    several actors keep working, animals are left to their own drawing
  console 2D        the console engine still builds its acted shots with both options on
"""
import os, sys, math, json, copy
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))
from hstudio.acting import timeline as TL, gaze as GZ, rig
from hstudio.acting.qc import _acting
from hstudio.pipeline import make_engine
from scene_sheet import scene_lines
from motion_qc import measure, stats, acting_of, in_stance, ankle_world

FAIL = []
def check(ok, label, detail=''):
    print(f'{"OK  " if ok else "FAIL"}  {label}{"  " + detail if detail else ""}')
    if not ok: FAIL.append(label)

SCENE = os.path.join(ROOT, 'tests', 'scenes', 'regie_acteurs.json')


def built(over=None, scene=SCENE, aspect='16:9'):
    ep = json.load(open(scene, encoding='utf-8')) if isinstance(scene, str) else copy.deepcopy(scene)
    lines = scene_lines(ep)
    if over: ep.update(copy.deepcopy(over))
    eng = make_engine(ep.get('style', 'pixel3d'), ep, lines, np.zeros(10), lines[-1]['end'] + .2, aspect)
    spans = eng.ctx.tl.spans if hasattr(eng, 'ctx') else eng.tl.spans
    return _acting(eng), ep, spans


def angles(ac, step=.05):
    """every (shot, id, t) -> (yaw, pitch, heading, x, z) of a built Acting, as a flat dict"""
    out = {}
    for k, sa in sorted(ac.shots.items()):
        for i in range(int(sa.dur / step) + 1):
            t = min(sa.dur, i * step)
            for aid, s in sa.sample(t).items():
                out[(k, aid, round(t, 4))] = (s['rig']['head'][0], s['rig']['head'][1], s['heading'], s['x'], s['z'])
    return out


# ---------------------------------------------------------------- opt-in
def t_optin():
    ref = angles(built()[0])
    for spec in (None, False, 'snap', 'off'):
        ep = json.load(open(SCENE, encoding='utf-8')); ep['eyeline'] = spec; ep['footing'] = spec
        same = angles(built(None, ep)[0]) == ref
        check(same, f'opt-in : "eyeline"/"footing" = {spec!r} ne change rien')
    on = angles(built({'eyeline': 'smooth'})[0])
    check(on != ref, 'opt-in : "eyeline": "smooth" change bien le regard')
    check(angles(built({'footing': 'path'})[0]) != ref, 'opt-in : "footing": "path" change bien le corps')
    check(GZ.options(None) is None and GZ.options('smooth') is not None, 'opt-in : gaze.options() par défaut éteint')
    check(TL.footing({}, {}) is False and TL.footing({'footing': 'path'}, {}) is True, 'opt-in : timeline.footing() par défaut éteint')
    # a shot may switch it on alone
    ep = json.load(open(SCENE, encoding='utf-8')); ep['shots'][1]['eyeline'] = 'smooth'
    ac, _e, _s = built(None, ep)
    check(ac.shots[1].gaze is not None and ac.shots[0].gaze is None, 'opt-in : un plan peut activer le regard seul')


# ---------------------------------------------------------------- determinism
def t_determinism():
    a = angles(built({'eyeline': 'smooth', 'footing': 'path'})[0])
    b = angles(built({'eyeline': 'smooth', 'footing': 'path'})[0])
    check(a == b, 'déterminisme : deux constructions identiques')
    ac = built({'eyeline': 'smooth', 'footing': 'path'})[0]
    sa = ac.shots[2]; ts = [i * .037 for i in range(int(sa.dur / .037))]
    fwd = [sa.sample(t)['lea']['rig']['head'] for t in ts]
    bwd = list(reversed([sa.sample(t)['lea']['rig']['head'] for t in reversed(ts)]))
    check(fwd == bwd, "déterminisme : l'ordre d'échantillonnage ne change rien")


# ---------------------------------------------------------------- the gaze itself
def t_gaze_speed():
    ac, ep, spans = built({'eyeline': 'smooth'})
    worst = 0.; worst_body = 0.
    for k, sa in sorted(ac.shots.items()):
        prev = {}
        for i in range(int(sa.dur * 60) + 1):
            t = min(sa.dur, i / 60.)
            for aid, s in sa.sample(t).items():
                g = s['heading'] + s['rig']['head'][0]
                if aid in prev:
                    worst = max(worst, abs(TL.wrap(g - prev[aid][0])) * 60.)
                    worst_body = max(worst_body, abs(TL.wrap(s['heading'] - prev[aid][1])) * 60.)
                prev[aid] = (g, s['heading'])
    budget = GZ.DEFAULTS['speed'] + worst_body + .35          # its own speed plus what the body carries it through
    check(worst <= budget, 'vitesse : la tête reste sous la limite',
          f'{math.degrees(worst):.0f} deg/s mesuré, plafond {math.degrees(budget):.0f} (corps {math.degrees(worst_body):.0f})')


def t_gaze_snaps():
    before = stats(*measure(*built(), label='scene'))
    after = stats(*measure(*built({'eyeline': 'smooth'}), label='scene'))
    check(before['snap_max'] > 40., 'scène de test : le défaut est bien présent sans option', f"{before['snap_max']:.1f} deg/frame")
    check(after['snaps_over_25'] == 0 and after['snap_max'] < before['snap_max'] / 3.,
          'regard : plus aucun saut > 25 deg/frame', f"{before['snap_max']:.1f} -> {after['snap_max']:.1f} deg")


def t_anticipation():
    """how far the head is, on the first frame of a shot, from where the régie wants it there"""
    def late(ac):
        out = []
        for k in sorted(ac.shots):
            if k == 0: continue
            sa = ac.shots[k]; want = sa.raw_heads(0.); got = sa.sample(0.)
            for aid, (yaw, _p, hd) in want.items():
                out.append(abs(TL.wrap(hd + yaw - got[aid]['heading'] - got[aid]['rig']['head'][0])))
        return sum(out) / max(1, len(out))
    on = late(built({'eyeline': 'smooth'})[0]); no = late(built({'eyeline': {'anticipate': False}})[0])
    check(on < no * .75, "anticipation : à la coupe, la tête est déjà sur la cible du plan suivant",
          f'retard moyen {math.degrees(no):.1f} deg sans anticipation -> {math.degrees(on):.1f} deg avec')


def t_continuity():
    def jump(ac):
        out = 0.
        for k in sorted(ac.shots):
            if k + 1 not in ac.shots: continue
            a_, b_ = ac.shots[k], ac.shots[k + 1]
            end = a_.sample(a_.dur); start = b_.sample(0.)
            for i in set(end) & set(start):
                out = max(out, abs(TL.wrap(start[i]['heading'] + start[i]['rig']['head'][0]
                                           - end[i]['heading'] - end[i]['rig']['head'][0])))
        return out
    on = jump(built({'eyeline': 'smooth'})[0]); off = jump(built({'eyeline': {'carry': False}})[0])
    check(math.degrees(on) < 2., 'continuité : la coupe ne remet pas la tête à zéro', f'{math.degrees(on):.2f} deg')
    check(on < off, 'continuité : sans "carry" la coupe se voit davantage', f'{math.degrees(off):.1f} deg sans report')


def t_neck_limit():
    ac, _e, _s = built({'eyeline': 'smooth', 'footing': 'path'})
    bad = 0; worst = 0.
    for k, sa in sorted(ac.shots.items()):
        for i in range(int(sa.dur * 60) + 1):
            for aid, s in sa.sample(min(sa.dur, i / 60.)).items():
                y = abs(s['rig']['head'][0]); worst = max(worst, y)
                if y > GZ.DEFAULTS['limit'] + 1e-6: bad += 1
    check(bad == 0, "nuque : le regard résolu reste dans le cône dessiné", f'max {math.degrees(worst):.1f} deg')


# ---------------------------------------------------------------- the body and the feet
def t_footing_heading():
    """angle between the direction a character actually travels in and the direction their body faces"""
    def worst_err(over):
        ac, _e, _s = built(over)
        sa = ac.shots[2]; tr = sa.tracks['lea']
        p = [q for q in tr.paths if q.D > 1.][0]
        errs = []
        for i in range(24):
            t = p.t0 + (p.t1 - p.t0) * (.12 + .76 * i / 23)
            a = sa.position(tr, t - .08); b = sa.position(tr, t + .08)
            if math.hypot(b[0] - a[0], b[1] - a[1]) < 1e-3: continue
            errs.append(abs(TL.wrap(TL.heading_of(b[0] - a[0], b[1] - a[1]) - tr.heading_at(t))))
        return math.degrees(max(errs))
    no = worst_err({}); on = worst_err({'footing': 'path'})
    check(no > 15., 'cap : sans option le corps marche de travers (historique)', f'écart max {no:.0f} deg')
    check(on < 10., 'cap : avec "footing" le corps suit le chemin parcouru', f'écart max {on:.0f} deg')
    check(on < no / 2., 'cap : au moins deux fois mieux', f'{no:.0f} -> {on:.0f} deg')


def t_foot_plant():
    before = stats(*measure(*built(), label='scene'))
    after = stats(*measure(*built({'footing': 'path'}), label='scene'))
    check(after['slide_p95'] < before['slide_p95'] * .6, 'pieds : le glissement du pied porteur diminue',
          f"p95 {before['slide_p95']:.2f} -> {after['slide_p95']:.2f} cm/frame")
    check(after['slide_max'] < before['slide_max'] * .6, 'pieds : le pire glissement diminue',
          f"max {before['slide_max']:.2f} -> {after['slide_max']:.2f} cm/frame")
    # a walk must end with the feet together, not mid-stride
    ac, _e, _s = built({'footing': 'path'})
    sa = ac.shots[2]; tr = sa.tracks['lea']; p = [q for q in tr.paths if q.D > 1.][0]
    s = sa.sample(min(sa.dur, p.t1 - .01))['lea']
    sk = rig.solve(s['rig']); spread = abs(float(sk.joints['anL'][2] - sk.joints['anR'][2]))
    check(spread < .22, "pieds : la marche se termine pieds joints", f'écart {100 * spread:.0f} cm entre les chevilles')


# ---------------------------------------------------------------- cast, animals, console
def t_cast_and_animals():
    snaps, _sl = measure(*acting_of('demo3_groupe', '16:9', lambda ep: dict(ep, eyeline='smooth', footing='path')), label='d3')
    who = {s['who'] for s in snaps}
    check({'lea', 'tom', 'zoe'} <= who, 'distribution : les trois acteurs sont toujours joués', ', '.join(sorted(who)))
    check(max(s['deg'] for s in snaps) < 25., 'distribution : aucun saut de regard à trois acteurs',
          f"max {max(s['deg'] for s in snaps):.1f} deg")
    ac, ep, _s = acting_of('demo3_groupe', '16:9', lambda ep: dict(ep, eyeline='smooth'))
    check('rex' in ac.shots[0].tracks, "animaux : le chien reste dans la régie (son rendu lui est propre)")


def t_console():
    for over in ({}, {'eyeline': 'smooth', 'footing': 'path'}):
        ac, ep, spans = acting_of('demo5_console', '9:16', (lambda ep, o=over: dict(ep, **o)) if over else None)
        check(ac is not None and len(ac.shots) > 0, f'console 2D : les plans joués se construisent {over or "sans option"}',
              f'{len(ac.shots)} plan(s)')
    a = stats(*measure(*acting_of('demo5_console', '9:16'), label='c'))
    b = stats(*measure(*acting_of('demo5_console', '9:16', lambda ep: dict(ep, eyeline='smooth', footing='path')), label='c'))
    check(b['snap_max'] <= a['snap_max'], 'console 2D : le regard ne se dégrade pas',
          f"{a['snap_max']:.1f} -> {b['snap_max']:.1f} deg")


if __name__ == '__main__':
    for fn in (t_optin, t_determinism, t_gaze_speed, t_gaze_snaps, t_anticipation, t_continuity, t_neck_limit,
               t_footing_heading, t_foot_plant, t_cast_and_animals, t_console):
        print(f'-- {fn.__name__[2:]}')
        fn()
    print()
    print('Tout est OK' if not FAIL else f'{len(FAIL)} échec(s) : ' + ', '.join(FAIL))
    sys.exit(1 if FAIL else 0)
