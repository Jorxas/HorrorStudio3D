"""Measures what the figurants REALLY do, sampled at 30 i/s on the production acting layer.

    python tools/check_background_motion.py
    python tools/check_background_motion.py --json docs/figurants/mouvement_figurants.json

Nothing is rendered: the episode is built through `hstudio.pipeline.make_engine` -- the same call the mix and
every render worker make, so the "extras" expansion that is measured here is the one that will be in the video --
and then every shot is sampled. A few seconds, no ffmpeg, no API, no cost.

What is measured, and which claim each number defends:

  les corps bougent VRAIMENT      distance walked per figurant per shot. A figurant that is "animated" by a
                                  camera pan and never moves would read 0.00 m here. This is the anti-fake-pan
                                  number.
  glissement du pied              how far the stance foot moves in the world between two frames while the walk
                                  cycle runs (cm/image). The gait is driven by distance, so a planted foot should
                                  not move: what is left is skating. Measured the same way as
                                  tools/locomotion_qc.py, and the LEAD is measured next to the figurants so the
                                  figure is read against the body the owner already accepted.
  cap contre deplacement          angle between the body heading and the direction it travels while it moves.
  plus proche approche            the closest any two bodies ever come, over every frame of every shot, and the
                                  same figure restricted to figurant-against-lead. Under 0.52 m two bodies
                                  interpenetrate (BODY).
  rayon d'ecoute                  distance from the speaker to the nearest figurant at every line start.
                                  ShotActing.speech() makes a speaker turn towards the nearest person within
                                  3.5 m: above that radius, no figurant can steal the lead's eyeline.
  sursaut mesure                  the frame at which each figurant's hands actually leave their resting height
                                  after the threat -- the startle as the RENDERER will draw it, not as the JSON
                                  asked for it -- against the scheduled time and against the threat.
  dans le cadre                   who is really INSIDE the 9:16 frame at ten instants, and how many pixels tall,
                                  using the engine's own solved camera and the engine's own projection. A dark
                                  PNG cannot be read by eye; this can, and it is what turned a staging with two
                                  figurants per shot into one with four on the two shots that matter.
  la ville vide, meme jeu         the lead's trajectory in the VIVANTE scene against her trajectory in the VIDE
                                  scene. Adding four bodies to the street must not move the lead's BODY by one
                                  millimetre. Her HEAD does move -- she glances at the passers-by -- and that is
                                  measured and printed too, because it is what makes a POV camera unusable for
                                  the A/B plate (see tools/check_background_proof.py).

The foot-slide threshold is not a constant written down here: `baseline_slide()` measures the LEAD walking a
straight free line of the same set at each speed the troupe uses, in this very process, and each figurant is
judged against that. The slide grows with speed in the shipped engine (4.92 cm/image at `walk`, 14.44 at
`run`), so comparing a running figurant to a walking lead would blame this lot for a defect it did not
introduce.
"""
import os, sys, json, math, copy, argparse
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from hstudio.acting import rig, background as BG                      # noqa: E402
from hstudio.acting.timeline import wrap                              # noqa: E402
from locomotion_qc import read_scene, feet_world                      # noqa: E402

FPS = 30.
MOVING = .15            # m/s, below this the direction travelled is noise
LISTENER = 3.5          # m, the radius of ShotActing.speech()
SCENES = os.path.join(ROOT, 'examples', 'scenes')
VIVANTE = os.path.join(SCENES, 'extras_rue_vivante.json')
VIDE = os.path.join(SCENES, 'extras_rue_vide.json')

bad = []


def check(ok, label, detail=''):
    print(('  OK    ' if ok else '  ECHEC ') + label + (('   ' + detail) if detail else ''))
    if not ok:
        bad.append(label)
    return ok


def hands_y(v, sk):
    """height of the two hands above the floor: what a startle actually lifts"""
    return max(float(sk.frames['handR'][1][1]), float(sk.frames['handL'][1][1]))


def sample_scene(path, aspect='9:16'):
    """-> (episode expanded as the renderer will see it, {shot: {aid: [frames]}}, acting)"""
    from hstudio.pipeline import make_engine, duration_of
    ep, lines = read_scene(path)
    dur = duration_of(ep, lines)
    eng = make_engine(ep.get('style', 'pixel3d'), ep, lines, np.zeros(10), dur, aspect)
    ac = eng.ctx.get_acting() if hasattr(eng, 'ctx') else getattr(eng, 'acting', None)
    cast = (eng.ctx.ep if hasattr(eng, 'ctx') else ep).get('cast') or {}
    hist = {}
    for k, sa in sorted(ac.shots.items()):
        H = hist.setdefault(k, {})
        for t in np.arange(0, sa.dur, 1. / FPS):
            sm = sa.sample(float(t))
            for aid, v in sm.items():
                sk = rig.solve(v['rig'])
                H.setdefault(aid, []).append(dict(t=float(t), x=v['x'], z=v['z'], h=v['heading'],
                                                  head=float((v['rig'].get('head') or (0., 0.))[0]),
                                                  gait=v['rig'].get('gait', 0.), feet=feet_world(v, sk),
                                                  hands=hands_y(v, sk)))
    return (eng.ctx.ep if hasattr(eng, 'ctx') else ep), hist, ac, cast, eng


def is_creature(cast, aid):
    c = cast.get(aid)
    return bool(c.get('kind')) if isinstance(c, dict) else False


def per_body(H, aid):
    """(metres walked, foot slide samples, heading error samples)"""
    T = H[aid]
    walked = 0.
    slides, errs = [], []
    for i in range(1, len(T)):
        r, p = T[i], T[i - 1]
        dx, dz = r['x'] - p['x'], r['z'] - p['z']
        step = math.hypot(dx, dz)
        walked += step
        sp = step * FPS
        if sp > MOVING:
            errs.append(abs(math.degrees(wrap(r['h'] - math.atan2(dx, dz)))))
        tag = 'R' if p['feet']['R'][2] <= p['feet']['L'][2] else 'L'
        if r['gait'] > .5:
            slides.append(math.hypot(r['feet'][tag][0] - p['feet'][tag][0],
                                     r['feet'][tag][1] - p['feet'][tag][1]) * 100)
    return walked, slides, errs


def in_frame(path, times, aspect='9:16'):
    """-> [{t, shot, bodies: {aid: hauteur en pixels}}] : who is really INSIDE the 9:16 frame, and how big.

    The camera is the engine's own (`build_frame` returns the solved camera for that instant) and the projection
    is the engine's own (`r3d.project`), so this is the frame the renderer will draw and not a reconstruction.
    Occlusion is not resolved -- a body behind a wall still counts -- which is why the sheet of real extracted
    frames stays part of the proof; what this measures, and what squinting at a dark PNG cannot, is whether a
    figurant is in the field of view at all and whether it is two pixels tall or two hundred."""
    from hstudio.pipeline import make_engine, duration_of
    from hstudio.engines.pixel3d import r3d
    from hstudio.engines.pixel3d.frame import build_frame
    ep, lines = read_scene(path)
    dur = duration_of(ep, lines)
    eng = make_engine(ep.get('style', 'pixel3d'), ep, lines, np.zeros(10), dur, aspect)
    out = []
    for t in times:
        built = build_frame(eng.ctx, float(t))        # `g` is the absolute time in seconds, not a fraction
        cam, shot, T, k = built[1], built[3], built[4], built[6]
        pos, yaw, pitch, roll, fov = cam
        sa = eng.ctx.get_acting().shots[k]
        sm = sa.sample(max(0., min(T, sa.dur)))
        row = {'t': round(t, 2), 'shot': k, 'bodies': {}}
        for aid, v in sm.items():
            top = r3d.project(pos, yaw, pitch, roll, fov, (v['x'], 1.75 * float(v.get('scale', 1.)), v['z']))
            foot = r3d.project(pos, yaw, pitch, roll, fov, (v['x'], 0., v['z']))
            if top[2] <= 0 or foot[2] <= 0:
                continue
            uu = (top[0] + foot[0]) / 2
            if abs(uu) > 1.05 or (top[1] < -1.05 and foot[1] < -1.05) or (top[1] > 1.05 and foot[1] > 1.05):
                continue
            row['bodies'][aid] = int(round(abs(top[1] - foot[1]) / 2 * r3d.RH * (1080. / max(1, r3d.RW))))
        out.append(row)
    return out


def baseline_slide(ep, set_name, lead, speeds):
    """{speed: foot slide of the LEAD walking a straight free line of the same set at that speed}.

    Measured here and not written down as a constant, because the number is a property of the shipped engine and
    not of this lot: the gait is driven by distance and the stride grows with speed, so a planted foot moves more
    per frame the faster the body goes. `run` slides about three times as much as `walk` on the character the
    owner has already accepted. A figurant is therefore judged against the SAME body at the SAME speed, which is
    the only comparison that says anything about the figurants."""
    from hstudio.pipeline import make_engine, duration_of
    out = {}
    for sp in sorted(set(speeds)):
        e = {'engine_version': 2, 'default_set': set_name, 'body': ep.get('body'),
             'sets': copy.deepcopy(ep.get('sets') or {}), 'cast': {lead: copy.deepcopy((ep.get('cast') or {})[lead])},
             'shots': [{'lines': [0, 0], 'actors': [{'id': lead, 'at': [-0.9, 2.0], 'facing': '+z'}],
                        'actions': [{'who': lead, 'do': 'walk_to', 'to': [-0.9, 14.0], 'speed': sp}],
                        'camera': {'shot': 'wide', 'on': [lead]}}]}
        lines = [{'tts': '.', 'display': '', 'text': '', 'tags': [], 'dialogue': False, 'i': 0,
                  'start': .1, 'end': 11.9, 'segs': [[.1, 11.9]]}]
        eng = make_engine('pixel3d', e, lines, np.zeros(10), duration_of(e, lines), '9:16')
        sa = (eng.ctx.get_acting()).shots[0]
        T = []
        for t in np.arange(0, sa.dur, 1. / FPS):
            v = sa.sample(float(t))[lead]
            sk = rig.solve(v['rig'])
            T.append(dict(x=v['x'], z=v['z'], gait=v['rig'].get('gait', 0.), feet=feet_world(v, sk), hands=0.))
        sl = []
        for i in range(1, len(T)):
            r, p = T[i], T[i - 1]
            tag = 'R' if p['feet']['R'][2] <= p['feet']['L'][2] else 'L'
            if r['gait'] > .5:
                sl.append(math.hypot(r['feet'][tag][0] - p['feet'][tag][0],
                                     r['feet'][tag][1] - p['feet'][tag][1]) * 100)
        out[sp] = round(max(sl), 2) if sl else None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', default='')
    a = ap.parse_args()
    print('=' * 78)
    print('== MOUVEMENT DES FIGURANTS, mesure sur la couche de jeu de production')
    print('=' * 78)

    ep, H, ac, cast, eng = sample_scene(VIVANTE)
    rep = BG.report(ep) or {}
    troupe = list(rep.get('troupe') or [])
    leads = [aid for aid in cast if aid not in troupe and not is_creature(cast, aid)]
    res = {'scene': os.path.relpath(VIVANTE, ROOT), 'troupe': troupe, 'leads': leads,
           'body': (eng.body or {}).get('name'), 'finish': (eng.fin or {}).get('name'), 'shots': {}}

    print(f"\n     corps : {res['body']}   image : {res['finish']}")
    print('     premiers roles : ' + ', '.join(leads) + '   figurants : ' + ', '.join(troupe))
    check(len(troupe) >= 3, 'au moins trois figurants dans la scene', f'{len(troupe)}')
    check(res['body'] == 'voxel_premium',
          'un SEUL corps pour tout le monde (pas de modele mixte)', str(res['body']))
    check(all(not is_creature(cast, f) for f in troupe),
          'aucun figurant n est une creature : ce sont des figures humaines du meme moteur')

    # ---------------- les corps bougent vraiment, et sans glisser
    print('\n-- les corps bougent vraiment (metres parcourus par plan) --')
    walked = {aid: {} for aid in list(troupe) + leads}
    allslides, allerrs = {}, {}
    for k in sorted(H):
        line = []
        for aid in list(troupe) + leads:
            if aid not in H[k]:
                continue
            w, sl, er = per_body(H[k], aid)
            walked[aid][k] = round(w, 3)
            allslides.setdefault(aid, []).extend(sl)
            allerrs.setdefault(aid, []).extend(er)
            line.append(f'{aid} {w:5.2f}')
        print(f'     plan {k} : ' + '  '.join(line))
    res['walked'] = walked
    movers = [f for f in troupe if BG.FIGURANTS[f]['role'] == 'walker']
    tot = {aid: round(sum(v.values()), 3) for aid, v in walked.items()}
    print('     total : ' + '  '.join(f'{k} {v:.2f} m' for k, v in tot.items()))
    check(all(tot.get(f, 0) > 2.0 for f in movers),
          'chaque figurant marcheur parcourt plus de 2 m dans la scene', str({f: tot.get(f) for f in movers}))
    check(all(tot.get(f, 0) > 0.5 for f in troupe),
          'meme les figurants postes finissent par se deplacer (ils fuient)', str(tot))

    print('\n-- glissement du pied (cm/image pendant le cycle de marche) et cap/deplacement --')
    pct = lambda v, q: (round(float(np.percentile(v, q)), 2) if v else None)
    res['slide'] = {}
    res['heading'] = {}
    for aid in list(troupe) + leads:
        sl, er = allslides.get(aid) or [], allerrs.get(aid) or []
        res['slide'][aid] = {'max': pct(sl, 100), 'p95': pct(sl, 95), 'n': len(sl)}
        res['heading'][aid] = {'max': pct(er, 100), 'p95': pct(er, 95), 'n': len(er)}
        print(f'     {aid:<9} glissement max {str(pct(sl, 100)):>6} cm/i  p95 {str(pct(sl, 95)):>6}'
              f'   |  cap max {str(pct(er, 100)):>7} deg  p95 {str(pct(er, 95)):>7}  ({len(er)} images)')
    print('     (le cap de « lea » monte a 180 deg par construction : son dernier plan est un "backwards": true,')
    print('      elle recule face a la menace -- ce n est pas une erreur de direction mais la direction demandee)')
    fastest = {}
    for f in troupe:
        used = {BG.FIGURANTS[f]['speed']}
        for s in ep['shots']:
            for act in s.get('actions') or []:
                if act.get('who') == f and act.get('speed'):
                    used.add(act['speed'])
        fastest[f] = max(used, key=lambda s: BG.SPEED_ORDER.get(s, 0))
    base = baseline_slide(ep, (ep.get('extras') or {}).get('set') or ep.get('default_set'),
                          leads[0], list(fastest.values()))
    res['baseline_slide'] = base
    res['fastest'] = fastest
    print('\n     reference : le MEME corps (« ' + leads[0] + ' ») marchant droit sur le meme decor')
    print('     ' + '   '.join(f'{k} {v} cm/i' for k, v in sorted(base.items(), key=lambda kv: BG.SPEED_ORDER.get(kv[0], 0))))
    over = []
    for f in troupe:
        ref = base.get(fastest[f])
        got = res['slide'][f]['max'] or 0
        if ref is not None and got > ref * 1.10 + .5:
            over.append(f'{f} {got:.2f} > {ref:.2f} ({fastest[f]})')
    check(not over, 'aucun figurant ne glisse plus que la reference a SA vitesse (+10 % et 0,5 cm/i de marge)',
          '; '.join(over) or ', '.join(f'{f}:{fastest[f]}' for f in troupe))

    # ---------------- collisions and distance keeping
    print('\n-- plus proche approche entre deux corps, sur toutes les images --')
    worst, worst_fl = (1e9, None), (1e9, None)
    for k in sorted(H):
        ids = [i for i in H[k] if not is_creature(cast, i)]
        n = min(len(H[k][i]) for i in ids) if ids else 0
        for f in range(n):
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    A, B = H[k][ids[i]][f], H[k][ids[j]][f]
                    d = math.hypot(A['x'] - B['x'], A['z'] - B['z'])
                    tag = (k, ids[i], ids[j], round(A['t'], 2))
                    if d < worst[0]:
                        worst = (d, tag)
                    if (ids[i] in leads) != (ids[j] in leads) and d < worst_fl[0]:
                        worst_fl = (d, tag)
    res['closest'] = {'all': round(worst[0], 3), 'where': worst[1],
                      'figurant_vs_lead': round(worst_fl[0], 3), 'where_fl': worst_fl[1]}
    print(f'     deux corps quelconques : {worst[0]:.2f} m   ({worst[1]})')
    print(f'     figurant contre role   : {worst_fl[0]:.2f} m   ({worst_fl[1]})')
    check(worst[0] >= BG.BODY, f'aucune interpenetration : >= {BG.BODY} m entre deux corps')
    check(worst_fl[0] >= BG.KEEP_CLEAR,
          f'les figurants gardent leurs distances avec le role principal (>= {BG.KEEP_CLEAR} m)')

    # ---------------- the listener radius
    print('\n-- rayon d ecoute de ShotActing.speech() : personne ne vole le regard du role --')
    rows = []
    for k, sa in sorted(ac.shots.items()):
        for (l0, l1, who, li) in sa.lines:
            if who not in sa.tracks:
                continue
            x, z = sa.position(sa.tracks[who], l0)
            near = None
            for aid in troupe:
                if aid not in sa.tracks:
                    continue
                ox, oz = sa.position(sa.tracks[aid], l0)
                d = math.hypot(ox - x, oz - z)
                if near is None or d < near[0]:
                    near = (d, aid)
            if near:
                rows.append((k, who, round(l0, 2), round(near[0], 2), near[1]))
                print(f'     plan {k}  « {who} » parle a t={l0:5.2f} s : figurant le plus proche '
                      f'{near[1]} a {near[0]:5.2f} m')
    res['listener'] = rows
    check(bool(rows) and all(r[3] > LISTENER for r in rows),
          f'a chaque replique, le figurant le plus proche est au-dela de {LISTENER} m')

    # ---------------- the startle, as the renderer draws it
    print('\n-- sursaut mesure sur le squelette (les mains quittent leur hauteur de repos) --')
    threat = next((b for b in ((ep.get('extras') or {}).get('beats') or []) if b.get('do') == 'threat'), None)
    sched = {f: t for (s, f, kind, t) in (rep.get('events') or []) if kind == 'react'}
    rows = []
    if threat is not None:
        k = int(threat['shot'])
        at = float(threat.get('at', 0.))
        for aid in troupe + leads:
            T = H[k].get(aid) or []
            base = np.median([r['hands'] for r in T if r['t'] < at]) if any(r['t'] < at for r in T) else None
            hit = next((r['t'] for r in T if r['t'] >= at and base is not None and r['hands'] > base + .12), None)
            rows.append((aid, at, sched.get(aid), None if hit is None else round(hit, 2),
                         None if hit is None else round(hit - at, 2)))
            print(f'     {aid:<9} menace a {at:.2f} s   prevu {str(sched.get(aid)):>5} s   '
                  f'mains levees a {str(None if hit is None else round(hit, 2)):>5} s   '
                  f'retard {str(None if hit is None else round(hit - at, 2)):>5} s')
    res['startle'] = rows
    figs = [r for r in rows if r[0] in troupe]
    check(bool(figs) and all(r[3] is not None for r in figs),
          'le sursaut de chaque figurant est VISIBLE sur le squelette, pas seulement dans le JSON')
    check(all(r[4] is not None and 0 <= r[4] <= BG.REACT_WINDOW + .25 for r in figs),
          f'chaque sursaut mesure tombe dans [menace, menace + {BG.REACT_WINDOW + .25} s]')
    check(len({r[4] for r in figs}) > 1, 'les figurants ne sursautent pas tous sur la meme image')

    # ---------------- who is really inside the 9:16 frame
    print('\n-- figurants reellement DANS le cadre 9:16 (hauteur a l image, en pixels sur 1920) --')
    from hstudio.pipeline import duration_of as _dur
    total = _dur(ep, read_scene(VIVANTE)[1])
    times = [round(total * f, 2) for f in (.06, .14, .24, .34, .44, .54, .64, .74, .84, .94)]
    vis = in_frame(VIVANTE, times)
    res['in_frame'] = vis
    shots_ok = {}
    for r in vis:
        figs = {a: h for a, h in r['bodies'].items() if a in troupe and h >= 24}
        shots_ok.setdefault(r['shot'], 0)
        shots_ok[r['shot']] = max(shots_ok[r['shot']], len(figs))
        print(f"     t={r['t']:5.2f} s  plan {r['shot']}  " +
              '  '.join(f'{a}:{h}px' for a, h in sorted(r['bodies'].items(), key=lambda kv: -kv[1])))
    res['figurants_per_shot'] = shots_ok
    print('     figurants d au moins 24 px par plan : ' + str(shots_ok))
    check(max(shots_ok.values()) >= 3, 'au moins 3 figurants lisibles dans un meme plan', str(shots_ok))
    check(sum(1 for v in shots_ok.values() if v >= 2) >= 3,
          'au moins 3 plans montrent 2 figurants ou plus', str(shots_ok))

    # ---------------- the lead is not disturbed by the crowd
    print('\n-- la ville VIDE joue exactement le meme role principal --')
    _, H0, _, _, _ = sample_scene(VIDE)
    diffs, gaze = [], []
    for k in sorted(H0):
        for aid in leads:
            A, B = H0[k].get(aid) or [], H[k].get(aid) or []
            for u, v in zip(A, B):
                diffs.append(max(abs(u['x'] - v['x']), abs(u['z'] - v['z']), abs(wrap(u['h'] - v['h']))))
                gaze.append(abs(wrap(u['head'] - v['head'])))
    res['lead_drift'] = round(max(diffs), 9) if diffs else None
    res['lead_gaze_drift_rad'] = round(max(gaze), 4) if gaze else None
    print(f'     corps (position et cap) de {leads} : ecart maximal {res["lead_drift"]}')
    print(f'     TETE : ecart maximal {res["lead_gaze_drift_rad"]} rad '
          f'({math.degrees(res["lead_gaze_drift_rad"] or 0):.0f} deg)')
    print('     la tete BOUGE, et c est voulu : ShotActing.raw_head() fait regarder celui qui parle vers la')
    print('     personne la plus proche, donc Lea jette un oeil aux passants. Le CORPS, lui, ne bouge pas d un')
    print('     millimetre. Mais cela suffit a deplacer une camera POV, et c est pour cela que la planche de')
    print('     tools/check_background_proof.py mesure sa camera plan par plan au lieu de la supposer identique.')
    check(diffs and max(diffs) < 1e-6,
          'ajouter quatre figurants ne deplace pas le CORPS du role principal d un millimetre')

    print('\n' + '=' * 78)
    print(('ECHEC : ' + '; '.join(bad)) if bad else 'Tout est OK.')
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        res['echecs'] = bad
        json.dump(res, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
        print('mesures : ' + a.json)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
