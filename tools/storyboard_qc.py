"""Measure the STORYBOARD of a narrative scenario: did the direction actually direct? Nothing is rendered.

  python tools/storyboard_qc.py examples/scenes/dernier_bus.json
  python tools/storyboard_qc.py examples/scenes/dernier_bus.json --options legacy,intents,directed --json out.json
  python tools/storyboard_qc.py examples/scenes/dernier_bus.json --sheet docs/p2_cinema/board_directed.png

The numbers it reports, and why each one is the number that settles the argument:

  **plans distincts**  how many different shot sizes the engine really SOLVED (not the ones the file asked
                       for: `cinema.solve` may refuse a two-shot in a narrow 9:16 frame and give a single
                       instead, and the solved one is what the viewer sees). A scene shot entirely in
                       `medium` is covered, not directed.
  **voyage de camera** metres between the camera of one shot and the camera of the next, and metres the
                       camera travels WITHIN a shot. This is the answer to "the camera really moves in
                       space": a cut that does not move the camera is a jump cut, and a move of 0 m is a
                       static shot pretending otherwise.
  **zoom**             spread of the focal length inside one shot, in degrees. `cinema.apply_move` is built
                       so this is always 0 -- the measurement exists so that the claim "no zoom hides the
                       movement" is checked rather than repeated. Anything above ZOOM_EPS is a zoom.
  **tete coupee**      share of samples where the TOP of a subject's head is outside the frame, counted
                       separately above and to the SIDE (in a 9:16 frame it is the width that runs out, so
                       the side is the common one). This is the defect the engine's own `subjects_framed`
                       cannot see on a tight shot: `qc_observe` only tests the top of the head for wide
                       shots, exactly because a close-up is meant to crop -- but cropping the skull of a
                       cubic character is never meant. Only the subjects the camera is ON are counted; see
                       `head_tops` for why that exclusion is not a convenience.
  **regard**           the face angles of `tools/cine_check.py`, reused as they are (one source).
  **acteurs distincts**how many different characters the camera is ON over the scene. A scene that only ever
                       frames the protagonist has no secondary characters, whatever the cast says.
  **score**            the cinematographer's own confidence in each shot (`cinema.solve`). Below 0.6 it has
                       given its best effort rather than a shot: a camera backed into a wall, a lens widened
                       past 79 degrees, a subject half hidden. Invisible without this column, and the single
                       most useful number for deciding whether a set can hold the shot that was asked of it.

It also prints the intention of each beat next to the shot that was solved for it, which is the only way to
read whether the director's reasons survived the cinematographer -- and runs the head-snap / foot-slide
measurements of `tools/motion_qc.py` on the same build, so the A/B does not need a second pass.

No ffmpeg, no network, no API, no project written: it builds the engine exactly like tools/scene_sheet.py.
"""
import os, sys, json, math, argparse
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

import cine_check as CC                                                      # noqa: E402
import motion_qc as MQ                                                       # noqa: E402

ZOOM_EPS = .05          # degrees of focal spread inside one shot above which the move is a zoom, not a travel
CUT_EPS = .12           # metres below which two consecutive cuts film from the same point (a jump cut)
HEAD_TOP = .99          # |v| of the projected top of the head beyond which the skull is out of the frame
TIGHT = ('close', 'extreme_close', 'medium', 'medium_full', 'ots')


def build(path, options, aspect='9:16'):
    """(scenario, episode, lines, engine, storyboard) of a narrative scenario shot with one option set"""
    from hstudio.director import narrative as N
    from hstudio import demos as D
    from hstudio.pipeline import make_engine, duration_of
    sc = N.scenario(path, options=options)
    lines = D.timed_lines(sc['script'], float(sc.get('gap', .3)), float(sc.get('lead', .4)))
    ep = D.episode_of(sc, lines, log=lambda *a: None)
    env = D.draft_voice(sc, lines)[1]
    eng = make_engine(sc.get('style', 'pixel3d'), ep, lines, env, duration_of(ep, lines), aspect)
    return sc, ep, lines, eng, sc.get('storyboard') or []


def head_tops(eng, t):
    """(camera, [(who, |v|, |u| of the TOP of his head)]) at time t, for the SUBJECTS of the shot.

    Two deliberate restrictions, both of them the difference between a measurement and a complaint:

    * the head point `qc_observe` reports is the CENTRE of the head; the top is half a head higher. That is
      computed here rather than in the engine because it is a judgement about framing, not about geometry;
    * only the subjects the camera is ON count, and they are taken from `qc_observe` rather than from the
      shot's actor list. On an over-the-shoulder the listener's head is cropped by the frame edge ON
      PURPOSE -- that is what makes it an over-the-shoulder. Counting his head as a defect turns the single
      most readable shot of the grammar into the worst score in the report, which is how a metric starts
      lying. `qc_observe` already applies that rule (ots / narrow dialogue -> the speaker alone)."""
    from hstudio.acting import rig
    from hstudio.engines.pixel3d import r3d, acted as ACT, bodies
    from hstudio.engines.pixel3d.frame import build_frame
    ctx = eng.ctx; k, t0, t1 = ctx.tl.at(t); ac = ctx.get_acting()
    if k not in ac.shots: return None
    ob = eng.qc_observe(t) or {}
    ids = list(ob.get('subjects') or [])
    plan = ctx.cam_cache.get((k, r3d.RW)) or {}
    asked = (plan.get('cam') or {}).get('shot')
    solved = (ob.get('cam') or {}).get('shot')
    if asked in ('ots', 'dialogue') and solved in ('close', 'extreme_close', 'medium', 'medium_full'):
        # `cinema.solve` documents this fallback: no room behind the listener, so the over-the-shoulder
        # becomes a CLEAN SINGLE on the speaker. The partner is then deliberately out of frame, but
        # `qc_observe` still lists both ids as subjects -- its own test only special-cases a shot that came
        # back as `ots`. Counting the partner's head here would report a cropped head on every such
        # fallback, which is the opposite of what the fallback does.
        spk = (plan.get('cam') or {}).get('speaker')
        ids = [spk] if spk in ids else ids[:1]
    if not ids: return None
    fr = build_frame(ctx, t); cam = fr[1]
    pos, yaw, pitch, roll, fov = cam
    sm = ac.shots[k].sample(t - t0)
    out = []
    for a in ids:
        s = sm.get(a)
        if s is None or not s.get('visible', 1): continue
        sc_ = float(((ctx.ep.get('cast') or {}).get(a) or {}).get('scale', 1.))
        hd = rig.solve(s['rig']).joints['head'] * sc_
        ch, sh = math.cos(s['heading']), math.sin(s['heading'])
        hx = s['x'] + hd[0] * ch + hd[2] * sh
        hy = float(hd[1]) + bodies.head_lift() * sc_ + s.get('y', 0.)
        hz = s['z'] - hd[0] * sh + hd[2] * ch
        top = hy + ACT.HEAD_W * bodies.head_scale() * sc_ * .5          # a cubic head is as tall as it is wide
        u_, v_, zc = r3d.project(pos, yaw, pitch, roll, fov, (hx, top, hz))
        if zc <= .1: continue
        out.append((a, abs(float(v_)), abs(float(u_))))
    return dict(shot=k, cam=tuple(float(v) for v in pos), fov=float(fov), heads=out,
                score=float((plan.get('sol') or {}).get('score') or 1.))


def measure(eng, ep, lines, board, every=.25):
    """-> per-shot rows + a verdict dict. Everything is read off the engine, nothing is assumed."""
    spans = eng.ctx.tl.spans
    end = spans[-1][1]
    per = {}
    t = 0.
    while t < end:
        h = head_tops(eng, float(t))
        if h:
            p = per.setdefault(h['shot'], dict(n=0, cams=[], fovs=[], cut=0, cutx=0, cut_who=set(), ts=[]))
            p['n'] += 1; p['cams'].append(h['cam']); p['fovs'].append(h['fov']); p['ts'].append(round(t, 2))
            p['score'] = h['score']
            for (a, v_, u_) in h['heads']:
                # a cubic head leaves the frame two ways, and in 9:16 the second is the common one
                if v_ > HEAD_TOP: p['cut'] += 1; p['cut_who'].add(a)
                if u_ > HEAD_TOP: p['cutx'] += 1; p['cut_who'].add(a)
        t += every
    # the kind of shot really solved, and the subjects really framed: the engine's own observations
    samples, face_per = CC.measure(eng, ep, lines, every)
    rows = []
    prev_cam = None
    for k in sorted(per):
        p = per[k]; cams = p['cams']
        inside = max(math.dist(cams[0], c) for c in cams) if len(cams) > 1 else 0.
        fp = face_per.get(k) or {}
        b = next((x for x in board if x['i'] == k), {})
        # travel is only a number between two shots of the SAME stage: across a set change the two camera
        # positions are expressed in two different sets' coordinates, and the distance between them means
        # nothing at all. Reporting it would inflate the median with a number that is not a camera move.
        same = prev_cam is not None and prev_cam[1] == b.get('stage')
        travel = math.dist(prev_cam[0], cams[0]) if same else None
        prev_cam = (cams[-1], b.get('stage'))
        rows.append(dict(shot=k, intent=b.get('intent'), asked=b.get('shot'), asked_move=b.get('move'),
                         solved=fp.get('kind'), stage=b.get('stage'),
                         samples=p['n'], cam_in=round(inside, 3), cam_cut=None if travel is None else round(travel, 3),
                         fov=round(p['fovs'][0], 2), fov_spread=round(max(p['fovs']) - min(p['fovs']), 4),
                         score=round(p.get('score', 1.), 3),
                         head_cut=p['cut'], head_cut_x=p['cutx'], head_cut_who=sorted(p['cut_who']),
                         face_worst=fp.get('worst'), face_mean=None if not fp.get('n') else round(fp['sum'] / fp['n'], 1),
                         face_beyond=fp.get('bad'), face_n=fp.get('n'), out_of_frame=fp.get('out'),
                         hidden=fp.get('hid'), head_share=fp.get('hs')))
    solved = [r['solved'] for r in rows if r['solved']]
    cuts = [r['cam_cut'] for r in rows if r['cam_cut'] is not None]
    actors = sorted({s['who'] for s in samples})
    tight = [r for r in rows if r['solved'] in TIGHT]
    verdict = {
        'shots': len(rows),
        'plans_distincts': len(set(solved)), 'plans': sorted(set(solved)),
        'voyage_coupe_min_m': round(min(cuts), 3) if cuts else None,
        'voyage_coupe_median_m': round(float(np.median(cuts)), 3) if cuts else None,
        'coupes_sans_deplacement': sum(1 for c in cuts if c < CUT_EPS),
        'voyage_interne_max_m': round(max(r['cam_in'] for r in rows), 3) if rows else None,
        'plans_qui_bougent': sum(1 for r in rows if r['cam_in'] > CUT_EPS),
        'zoom_max_deg': round(max(r['fov_spread'] for r in rows), 4) if rows else None,
        'plans_avec_zoom': sum(1 for r in rows if r['fov_spread'] > ZOOM_EPS),
        'tete_coupee_images': sum(r['head_cut'] for r in rows),
        'tete_coupee_plans': sorted(r['shot'] for r in rows if r['head_cut']),
        'tete_coupee_cote_images': sum(r['head_cut_x'] for r in rows),
        'tete_coupee_cote_plans': sorted(r['shot'] for r in rows if r['head_cut_x']),
        'tete_part_max': round(max((r['head_share'] or 0) for r in rows), 3) if rows else None,
        'echantillons': sum(r['samples'] for r in rows),
        'acteurs_distincts': len(actors), 'acteurs': actors,
        'regard_hors_cone': sum(r['face_beyond'] or 0 for r in tight),
        'regard_echantillons_serres': sum(r['face_n'] or 0 for r in tight),
        'hors_cadre': sum(r['out_of_frame'] or 0 for r in rows),
        'caches': sum(r['hidden'] or 0 for r in rows),
        'tete_trop_large': sum(1 for r in rows if (r['head_share'] or 0) > .85),
        'duree_s': round(end, 2),
        'camera_contrainte': sorted(r['shot'] for r in rows if r['score'] < .6),
        'score_min': round(min(r['score'] for r in rows), 3) if rows else None,
    }
    return rows, verdict


def motion(eng, ep):
    """head snaps and foot slide of the SAME build (tools/motion_qc.py, not a second copy of the maths)"""
    from hstudio.acting.qc import _acting
    ac = _acting(eng)
    snaps, slides = MQ.measure(ac, ep, eng.ctx.tl.spans, label='storyboard')
    s = MQ.stats(snaps, slides)
    return {k: s[k] for k in ('frames', 'snaps_over_25', 'snap_max', 'snap_p99', 'cuts', 'cut_max',
                              'stance_frames', 'slide_median', 'slide_p95', 'slide_max')}


def sheet(eng, lines, out, every=2.0, cols=8):
    """a contact sheet of the whole scene at low resolution: the storyboard as the eye sees it"""
    from PIL import Image, ImageDraw
    end = eng.ctx.tl.spans[-1][1]
    ts = [i * every for i in range(int(end / every) + 1)]
    tiles = []
    for t in ts:
        im = Image.fromarray(eng.render_lowres(float(t))[0])
        ImageDraw.Draw(im).text((4, 2), f'{t:.1f}s', fill=(255, 255, 0)); tiles.append(im)
    w, h = tiles[0].size
    sh = Image.new('RGB', (w * cols, h * ((len(tiles) + cols - 1) // cols)))
    for i, im in enumerate(tiles): sh.paste(im, ((i % cols) * w, (i // cols) * h))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    sh.save(out)
    return out, len(tiles)


def run_one(path, options, aspect, every, sheet_path=None, sheet_every=2.0, log=print):
    sc, ep, lines, eng, board = build(path, options, aspect)
    rows, verdict = measure(eng, ep, lines, board, every)
    verdict['options'] = options
    verdict['cles_opt_in'] = sorted((ep.get('_directed') or {}).get('keys') or [])
    verdict['cameras_ecrites'] = sum(1 for s in ep['shots'] if s.get('camera'))
    verdict['mouvement'] = (ep.get('_directed') or {}).get('camera')
    mo = motion(eng, ep)
    log('')
    log(f'== {os.path.basename(path)}   options "{options}"   {aspect}   {verdict["duree_s"]} s')
    log(f'   cameras ecrites dans l-episode : {verdict["cameras_ecrites"]}/{len(ep["shots"])}'
        f'   cles opt-in : {", ".join(verdict["cles_opt_in"]) or "aucune"}')
    log('   plan intention      demande       -> resolu        voyage(coupe/interne)  fov  tete  regard')
    for r in rows:
        cut = '   -  ' if r['cam_cut'] is None else '%6.2f' % r['cam_cut']
        fw = '   -  ' if r['face_worst'] is None else '%5.1f' % r['face_worst']
        log(f"   {r['shot']:4d} {str(r['intent'] or '-'):11s} {str(r['asked'] or '(auto)'):13s} -> "
            f"{str(r['solved'] or '?'):13s} {cut} m /{r['cam_in']:6.2f} m  "
            f"{r['fov']:5.1f}  s={r['score']:.2f}  {r['head_cut']:2d}/{r['head_cut_x']:2d}  {fw} deg  "
            f"{'' if r['head_share'] is None else '%.0f%% largeur' % (100 * r['head_share'])}")
    log(f"   plans distincts resolus : {verdict['plans_distincts']} ({', '.join(verdict['plans'])})")
    log(f"   voyage de camera : median {verdict['voyage_coupe_median_m']} m par coupe, "
        f"min {verdict['voyage_coupe_min_m']} m, {verdict['coupes_sans_deplacement']} coupe(s) sans deplacement ; "
        f"{verdict['plans_qui_bougent']}/{verdict['shots']} plans ou la camera se deplace "
        f"(jusqu-a {verdict['voyage_interne_max_m']} m)")
    log(f"   zoom : spread focal max {verdict['zoom_max_deg']} deg, {verdict['plans_avec_zoom']} plan(s) avec zoom")
    log(f"   tete coupee : en haut {verdict['tete_coupee_images']}/{verdict['echantillons']}"
        + (f" (plans {verdict['tete_coupee_plans']})" if verdict['tete_coupee_plans'] else '')
        + f" ; sur le cote {verdict['tete_coupee_cote_images']}/{verdict['echantillons']}"
        + (f" (plans {verdict['tete_coupee_cote_plans']})" if verdict['tete_coupee_cote_plans'] else '')
        + f" ; part de largeur max {verdict['tete_part_max']}")
    log(f"   regard hors du cone lisible (plans serres) : {verdict['regard_hors_cone']}/{verdict['regard_echantillons_serres']}")
    log(f"   acteurs distincts cadres : {verdict['acteurs_distincts']} ({', '.join(verdict['acteurs'])})")
    log(f"   hors cadre {verdict['hors_cadre']}, caches {verdict['caches']}, tete > 85 % de la largeur : {verdict['tete_trop_large']} plan(s)")
    log(f"   camera contrainte par le decor (score < 0.6) : {verdict['camera_contrainte'] or 'aucun plan'}"
        f" ; score minimum {verdict['score_min']}")
    log(f"   regie : saccades de regard > 25 deg {mo['snaps_over_25']}/{mo['frames']} (pire {mo['snap_max']:.1f} deg), "
        f"glissement de pied median {mo['slide_median']:.2f} cm, p95 {mo['slide_p95']:.2f} cm, max {mo['slide_max']:.2f} cm")
    res = dict(verdict=verdict, motion=mo, shots=rows, storyboard=board)
    if sheet_path:
        p, n = sheet(eng, lines, sheet_path, sheet_every)
        res['sheet'] = p; log(f'   planche : {p} ({n} images)')
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('scene'); ap.add_argument('--aspect', default='9:16')
    ap.add_argument('--every', type=float, default=.25)
    ap.add_argument('--options', default='directed', help='un ou plusieurs jeux separes par des virgules')
    ap.add_argument('--json', default='')
    ap.add_argument('--sheet-dir', default='', help='ecrire une planche de contact par jeu d-options')
    ap.add_argument('--sheet-every', type=float, default=2.0)
    a = ap.parse_args()
    out = {}
    for opt in [x.strip() for x in a.options.split(',') if x.strip()]:
        sp = os.path.join(a.sheet_dir, f'board_{opt}.png') if a.sheet_dir else None
        out[opt] = run_one(a.scene, opt, a.aspect, a.every, sp, a.sheet_every)
    if len(out) > 1:
        print('\n== comparaison ==')
        keys = ('cameras_ecrites', 'plans_distincts', 'voyage_coupe_median_m', 'coupes_sans_deplacement',
                'plans_qui_bougent', 'plans_avec_zoom', 'tete_coupee_images', 'tete_coupee_cote_images',
                'tete_part_max', 'tete_trop_large', 'regard_hors_cone', 'acteurs_distincts',
                'hors_cadre', 'caches', 'score_min')
        w = max(len(k) for k in keys) + 2
        print('  ' + 'mesure'.ljust(w) + ''.join(o.rjust(12) for o in out))
        for k in keys:
            print('  ' + k.ljust(w) + ''.join(str(out[o]['verdict'].get(k)).rjust(12) for o in out))
        for k in ('snaps_over_25', 'snap_max', 'slide_p95'):
            print('  ' + k.ljust(w) + ''.join(f"{out[o]['motion'][k]:12.2f}" for o in out))
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        json.dump(out, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
        print('\n' + a.json)


if __name__ == '__main__':
    main()
