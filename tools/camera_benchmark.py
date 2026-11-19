"""python tools/camera_benchmark.py [--out docs/camera_intent] [--only S09,S34] [--no-images]

An OBJECTIVE comparison of the cameras of the engines, on the same beats of « La Dernière Pompe » (9:16), measured on the same blocking (the continuity film's
trajectories), with the same acceptance frame for every provider. The providers:

  E1        the first engine's cinematographer (`acting/cinema.solve`) exactly as `voxelgpu/director.py` calls it in the voxel studio: shot types, 180-degree rule,
            faces, OTS/POV; it knows the characters and NOTHING of the place (the voxel world hands it no wall: `VoxWorld.blocked_for_camera` is a big box).
  E1+geo    the same solver given the place (walls block the lens, the set hides what it hides): separates "the grammar" from "the geometry".
  E2        the second engine's cameras as the owner saw them: coordinates typed by hand per shot (`films/remake_pompe.py`, the first remake), no check of anything.
  SOLVER    `camplan.solve` + the hand-placed shots of the continuity film at 19e2211 (tests/camera/pompe_cameras_19e2211.json): safe, centred, same recipe everywhere.
  INTENT    `cinematic_intent.plan_sequence`: a shot chosen for the purpose of the beat, then preflighted with the same audit.

Every camera is audited by `camplan.audit_shot` against the beat's ACCEPTANCE frame (what the narration needs seen, written once, independent of the provider): the safety
rules (lens in a wall, travelling through a wall, an occluder, a zoom) AND the artistic ones (menace readable at the back, apparent size of the car, gap legible, depth
layers, faces legible, size of the shot, the event actually filmed). Output: report.json, summary.md, and the 9:16 geometry sheets (tools/geoview.py), no GPU.
"""
import argparse, json, math, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'tools'))
from hstudio.voxelgpu import stagegeo, blocking as B, camplan as CP, cinematic_intent as CI, director as DIR
from hstudio.voxelgpu.films import pompe_continuite as N, remake_pompe as OLD
from hstudio.acting import cinema

T = OLD.T
SPOT_G = None            # filled once the blocking is compiled (where the faceless man is when he vanishes)

BEATS = [
    dict(id='S00', purpose='establish', intent=dict(show=['vitrine'], subject='ghost', tension=.3), e1=dict(shot='establishing', on=['ghost']),
         accept=dict(show=['vitrine'], actors=['ghost'], kind='establishing', min_layers=1, preflight=True),
         say="le lieu : la façade, et l'homme qui attend au fond du parking"),
    dict(id='S05', purpose='danger', intent=dict(subject='clerk', threat='ghost', tension=.6), e1=dict(shot='two_shot', on=['clerk', 'ghost']),
         accept=dict(actors=['clerk'], fg=['ghost'], threat=dict(id='ghost', hidden=[0., .7]), legible={'clerk': .2}, min_layers=2, preflight=True),
         say="le pompiste va vers la porte, l'homme est juste derrière la vitre"),
    dict(id='S09', purpose='danger', intent=dict(subject='clerk', threat='ghost', tension=.9, occlude=True), e1=dict(shot='medium_full', on=['clerk', 'ghost']),
         accept=dict(actors=['clerk'], fg=['ghost'], face=['clerk'], threat=dict(id='ghost', hidden=[0., .7]), legible={'clerk': .4}, preflight=True),
         say="sa main se pose contre la vitre : le visage du pompiste et la menace derrière"),
    dict(id='S11', purpose='disappear', intent=dict(witness='clerk', event=dict(kind='vanish', who='ghost', t=26.5), tension=.9), e1=dict(shot='wide', on=['ghost', 'clerk']),
         accept=dict(actors=['ghost', 'clerk'], points='spot', legible={'ghost': .15, 'clerk': .15}, preflight=True), event=dict(kind='vanish', who='ghost', t=26.5),
         say="il disparaît : l'événement et la peur dans le même plan"),
    dict(id='S12', purpose='disappear', intent=dict(witness='clerk', event=dict(kind='appear', who='ghost', t=27.6), tension=.9), e1=dict(shot='wide', on=['ghost', 'clerk']),
         accept=dict(actors=['ghost', 'clerk'], points='spot', legible={'ghost': .15, 'clerk': .15}, preflight=True), event=dict(kind='appear', who='ghost', t=27.6),
         say="tu l'aperçois juste à côté de la porte : il est là sans avoir marché"),
    dict(id='S14', purpose='danger', intent=dict(subject='clerk', threat='ghost', tension=.85), e1=dict(shot='two_shot', on=['clerk', 'ghost']),
         accept=dict(actors=['clerk'], fg=['ghost'], threat=dict(id='ghost', hidden=[0., .7]), legible={'clerk': .2, 'ghost': .12}, min_layers=2, preflight=True),
         say="tu l'éclaires : le faisceau, le pompiste, l'homme qui recule"),
    dict(id='S32', purpose='reaction', intent=dict(subject='clerk', tension=.7), e1=dict(shot='close', on=['clerk']),
         accept=dict(actors=['clerk'], face=['clerk'], legible={'clerk': .8}, preflight=True), say="« un œil dehors » : le visage du pompiste"),
    dict(id='S33', purpose='relation', intent=dict(subject='clerk', show=['voiture', 'vitrine'], tension=.6, min_share={'voiture': .3}), e1=dict(shot='wide', on=['clerk']),
         accept=dict(show=['voiture', 'vitrine'], actors=['clerk'], scale={'voiture': [.3, .85]}, min_layers=1, preflight=True), say="la voiture entière devant la boutique, le pompiste derrière la vitre"),
    dict(id='S34', purpose='relation', intent=dict(subject='clerk', show=['entree', 'voiture'], gap=('entree', 'voiture'), tension=.7), e1=dict(shot='wide', on=['clerk']),
         accept=dict(show=['entree', 'voiture'], actors=['clerk'], gap=dict(a='entree', b='voiture', min=.075), scale={'voiture': [.3, .85]}, preflight=True), say="trois mètres d'obscurité entre la porte et la voiture"),
    dict(id='S35', purpose='relation', intent=dict(subject='clerk', show=['porte_reserve'], tension=.8), e1=dict(shot='wide', on=['clerk']),
         accept=dict(show=['porte_reserve'], actors=['clerk'], min_layers=2, preflight=True), say="« derrière toi » : le pompiste et, loin derrière lui, la porte du fond"),
    dict(id='S39', purpose='pov', intent=dict(pov='clerk', sees='porte_reserve', tension=.8), e1=dict(shot='pov', on=['clerk']),
         accept=dict(show=['porte_reserve'], fg=['clerk'], preflight=True), say="choix A : ce que le pompiste voit, la porte du fond"),
]
for b in BEATS: b['idx'] = int(b['id'][1:]); b['t0'], b['t1'] = T[b['idx']], T[b['idx'] + 1]


CAPTION_BAND = [-.1, .2]      # image y (ndc) of the caption band of the film (caption_style y = .47 of the height, two lines)


def accept_frame(b, geo, C):
    f = json.loads(json.dumps(b['accept'])); ev = b.get('event')
    if f.get('actors'): f['avoid'] = list(CAPTION_BAND)
    if f.get('points') == 'spot':
        x, z = C.xz(ev['who'], ev['t'] - .05 if ev['kind'] == 'vanish' else ev['t'] + .15); f['points'] = [[x, 1.0, z]]
    return f


# ---------------------------------------------------------------------------------------------------------------------- the providers
def keys_static(dur, pos, look, fov): return {'rig': 'path', 'keys': [dict(t=0., pos=list(pos), look=list(look), fov=fov, roll=0.), dict(t=round(dur, 4), pos=list(pos), look=list(look), fov=fov, roll=0.)]}


def e1_camera(geo, C, b, with_geo):
    """the first engine's solver, called as director.py calls it (same subjects, same constants), one sample at the middle of the beat"""
    tm = (b['t0'] + b['t1']) / 2; ids = b['e1']['on']; subj = []
    for a in ids:
        row = C._row(C.actors[a], tm); sc = C.actors[a].scale
        subj.append(cinema.Subject(a, row['x'], row['z'], row['heading'], eye=DIR.EYE * sc, height=DIR.HEIGHT * sc, gaze=row['heading'] + row['rig']['head'][0], head_w=DIR.HEAD_W * sc))
    x0, z0, x1, z1 = geo.bounds
    blocked = (lambda p: bool(geo.solid_at_point(p, .25))) if with_geo else (lambda p: not (x0 <= p[0] <= x1 and z0 <= p[2] <= z1 and .25 <= p[1] <= 14.))
    probe = (lambda pos, pt: not geo.ray(pos, pt)) if with_geo else None
    c = dict(shot=b['e1']['shot'])
    if c['shot'] == 'pov': c['target_point'] = (3.45, 1.4, -7.1)
    sol = cinema.solve(c, subj, 9 / 16, 1.0, probe, blocked, {})
    if sol is None: return None
    return keys_static(b['t1'] - b['t0'], sol['pos'], sol['target'], sol['fov'])


def provider_cameras(geo, C, b, snap, old_shots, plan_by_id):
    d = b['t1'] - b['t0']; out = {}
    out['E1'] = e1_camera(geo, C, b, False); out['E1+geo'] = e1_camera(geo, C, b, True)
    out['E2'] = old_shots[b['id']]['camera']; out['SOLVER'] = snap[b['id']]
    out['INTENT'] = plan_by_id[b['id']]['camera'] if b['id'] in plan_by_id else None
    return out


def sizes_of(rows):
    return sorted({min(range(5), key=lambda k: abs(math.log(max(r, 1e-3)) - math.log([.1, .3, .65, .95, 1.4][k]))) for r in rows if r})


def evaluate(geo, C, b, cam):
    if cam is None: return dict(ok=False, violations=[dict(code='aucune_caméra', msg='le fournisseur ne propose aucune caméra')], metrics={})
    frame = accept_frame(b, geo, C); shot = dict(id=b['id'], dur=b['t1'] - b['t0'], _t0=b['t0'], frame=frame, camera=cam)
    ev = b.get('event')
    if ev:        # the event is what matters: the body is judged up to (vanish) or from (appear) the instant, the walk that follows is not the shot's business
        t_a, t_b = (b['t0'], min(b['t1'], ev['t'] + .1)) if ev['kind'] == 'vanish' else (max(b['t0'], ev['t'] + .1), b['t1'])
        shot = dict(shot, _t0=t_a, dur=t_b - t_a, camera=cam)
    v, met = CP.audit_shot(shot, C, geo, '9:16'); out = [x.to_json() for x in v]
    if b.get('event'):
        s = dict(id=b['id'], t0=b['t0'], dur=shot['dur'], camera=cam, event=b['event']); out += [x.to_json() for x in CI.audit_event(s, C, geo)]
    ex = (met.get('extra') or [{}])[len(met.get('extra') or [{}]) // 2] or {}
    pos, look, fov = CP.cam_at(shot, shot['dur'] / 2, C, shot['_t0'])
    subj = (frame.get('actors') or [None])[0]; bh = ex.get('size', {}).get('body_h')
    if bh is None and subj:
        A = C.actors[subj]; x, z = C.xz(subj, (b['t0'] + b['t1']) / 2); pr = CP.project(pos, look, fov, 9 / 16, [(x, CP.HEAD_TOP * A.scale, z), (x, 0., z)]); bh = abs(pr[0][1] - pr[1][1]) / 2 if min(p[2] for p in pr) > .3 else 9.
    return dict(ok=not out, violations=out, metrics=dict(fov=round(fov, 1), body_h=None if bh is None else round(bh, 2), pos=[round(float(v), 2) for v in pos], layers=(ex.get('layers') or {}).get('layers'),
                                                    gap=ex.get('gap'), scale={k: round(v[0], 2) for k, v in (ex.get('scale') or {}).items()}, clear=ex.get('clear')))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default='docs/camera_intent'); ap.add_argument('--only', default=''); ap.add_argument('--no-images', action='store_true'); a = ap.parse_args()
    out = ROOT / a.out; out.mkdir(parents=True, exist_ok=True); t00 = time.time()
    geo = stagegeo.station(N.DOORS); C = B.compile_plan(N.plan(), geo); snap = json.load(open(ROOT / 'tests/camera/pompe_cameras_19e2211.json', encoding='utf-8')); old = {s['id']: s for s in OLD.episode()['shots']}
    beats = [b for b in BEATS if not a.only or b['id'] in a.only.split(',')]
    intents = [dict(dict(b['intent'], id=b['id'], purpose=b['purpose'], t0=b['t0'], t1=b['t1'])) for b in beats]
    print(f'INTENT : {len(intents)} plans à préparer ...', flush=True)
    ctx = CI.Ctx(geo, C, '9:16', avoid=CAPTION_BAND); its = [CI.normalise(i, geo, C) for i in intents]      # beat by beat: these beats are not consecutive in the film, so the sequence rhythm is not applied
    shots = []; refused = {}
    for it in its:
        try: shots.append(CI.plan_shot(ctx, it, CI.base_size(it)))
        except CI.PlanError as e: refused[it['id']] = str(e)            # an honest refusal is part of the result, not a crash
    by_id = {s['id']: s for s in shots}
    plan = CI.Plan(shots, CI.audit_sequence(shots, C, geo, '9:16', .3), [], [s['kind'] for s in shots])
    print(f'  préparés en {time.time() - t00:.0f} s ; violations de la séquence : {len(plan.violations)}')
    rep = dict(beats={}, providers=['E1', 'E1+geo', 'E2', 'SOLVER', 'INTENT'], refused=refused); sheet_rows = []; names = rep['providers']
    for b in beats:
        cams = provider_cameras(geo, C, b, snap, old, by_id); res = {n: evaluate(geo, C, b, cams[n]) for n in names}
        rep['beats'][b['id']] = dict(purpose=b['purpose'], say=b['say'], t=[round(b['t0'], 2), round(b['t1'], 2)], results=res, intent_why=by_id[b['id']]['why'] if b['id'] in by_id else None,
                                     intent_relaxed=by_id[b['id']]['relaxed'] if b['id'] in by_id else None)
        if not a.no_images:
            import geoview
            tm = (b['t0'] + b['t1']) / 2; imgs = []; frame = accept_frame(b, geo, C)
            for n in names:
                if cams[n] is None: imgs.append(None); continue
                pos, look, fov = CP.cam_at(dict(camera=cams[n]), (b['t1'] - b['t0']) / 2, C, b['t0'])
                imgs.append(geoview.render(geo, C, pos, look, fov, tm, label=f"{n} {len(res[n]['violations'])}x" if res[n]['violations'] else f'{n} OK', mark=frame.get('points') or ()))
            sheet_rows.append((b['id'], imgs))
        print(f"  {b['id']} {b['purpose']:9s} " + '  '.join(f"{n}:{'OK' if res[n]['ok'] else str(len(res[n]['violations'])) + 'x'}" for n in names), flush=True)
    # ---- the sequence-level figures
    tot = {}
    for n in names:
        rs = [rep['beats'][b['id']]['results'][n] for b in beats]; codes = {}
        for r in rs:
            for v in r['violations']: codes[v['code']] = codes.get(v['code'], 0) + 1
        safety = sum(n_ for c, n_ in codes.items() if c in ('caméra_dans_solide', 'caméra_traverse', 'écran_bouché', 'mur_dans_l_objectif', 'acteur_masqué', 'repère_masqué', 'zoom', 'grand_angle'))
        tot[n] = dict(beats_ok=sum(1 for r in rs if r['ok']), beats=len(rs), violations=sum(len(r['violations']) for r in rs), safety_violations=safety, codes=codes,
                      size_classes=len(sizes_of([r['metrics'].get('body_h') for r in rs if r['metrics']])), mean_fov=round(sum(r['metrics'].get('fov', 0) for r in rs if r['metrics']) / max(1, sum(1 for r in rs if r['metrics'])), 1))
    rep['totals'] = tot; rep['intent_sequence_violations'] = [v.to_json() for v in plan.violations]; rep['seconds'] = round(time.time() - t00)
    (out / 'report.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False, default=float), encoding='utf-8')
    L = ['# Benchmark caméra — La Dernière Pompe, 9:16 (généré par tools/camera_benchmark.py)', '', f"{len(beats)} plans, même blocage, même critère d'acceptation pour chaque fournisseur.", '',
         '| fournisseur | plans acceptés | violations | dont sécurité | tailles de plan distinctes | focale moyenne |', '|---|---|---|---|---|---|']
    for n in names: t = tot[n]; L.append(f"| {n} | {t['beats_ok']}/{t['beats']} | {t['violations']} | {t['safety_violations']} | {t['size_classes']} | {t['mean_fov']}° |")
    L += ['', '| plan | but | ' + ' | '.join(names) + ' |', '|---|---|' + '---|' * len(names)]
    for b in beats:
        r = rep['beats'][b['id']]['results']; L.append(f"| {b['id']} | {b['say']} | " + ' | '.join('OK' if r[n]['ok'] else ', '.join(sorted({v['code'] for v in r[n]['violations']}))[:60] for n in names) + ' |')
    (out / 'summary.md').write_text('\n'.join(L) + '\n', encoding='utf-8'); print('\n'.join(L))
    if sheet_rows:
        import geoview
        h = (len(sheet_rows) + 1) // 2
        for k, rows in enumerate((sheet_rows[:h], sheet_rows[h:])):
            if rows: geoview.sheet(rows, names, title='colonnes : ' + ' | '.join(names)).save(out / f'planche_{k + 1}.png')
    print(f'écrit dans {out} en {time.time() - t00:.0f} s')


if __name__ == '__main__': main()
