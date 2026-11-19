"""Audit of the FINISHED contract of « Le Dernier Noyau » (what the painter will read, not the intentions): preflight violations, bodies (solid, wall, teleport, speed, overlap) re-measured on the rows,
feet, faces (blinks, stare, jumping pupils), face sync at film time, LIP-SYNC (correlation of the mouth with the voice envelope of each speaker), hands, blows, crowd counts, sound events.
usage: python tools/demo_cite_audit.py [--out report.json]"""
import argparse, json, math, sys, wave
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu import blocking as B, faceact as FA, footkin as FK, genre_intent as G, stagegeo, contract as C, combat
from hstudio.voxelgpu.films import demo_cite_film as DF
WORK = ROOT / 'projects' / 'demo_narrative_20261029'


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default=str(WORK / 'audit.json')); a = ap.parse_args(argv)
    c = C.load(WORK / 'contract.json'); ep = json.loads((WORK / 'episode.json').read_text(encoding='utf-8')); geo = stagegeo.GEOS['demo'](ep['blocking']['doors'])
    view, _ = G.compile_episode(ep); vs = view.vanishes; rep = {}
    rep['preflight_violations'] = [repr(v) for v in c['preflight']['violations']]
    declared = [dict(who=w['who'], t0=w['t0'], t1=w['t1']) for w in view.declared_warps()] if hasattr(view, 'declared_warps') else []
    ids = {a_: a_ for a_ in c['casts']}
    body = B.audit_contract(c, geo, vmax={k: 6. for k in c['casts']}, declared=declared); rep['body_on_rows'] = [repr(v) for v in body]
    rep['fight'] = [repr(v) for v in combat.audit_fight(view)]
    tr = FA.build_all(view, DF.director.EXPR_MAP if hasattr(DF, 'director') else __import__('hstudio.voxelgpu.director', fromlist=['x']).EXPR_MAP, list(C.EXPRESSIONS), c['duration'] + 1.)
    rep['faces'] = [repr(v) for v in FA.audit_faces(view, tr, list(C.EXPRESSIONS))]; rep['face_stage_sync'] = [repr(v) for v in FA.audit_stage_sync(c, tr)]
    feet = FK.audit_feet(c); rep['feet'] = [repr(v) for v in feet][:30]; rep['foot_drag_cm'] = {k: [round(v['mean'] * 100, 1), round(v['max'] * 100, 1), v['n']] for k, v in FK.slide_stats(c).items() if k in ('ines', 'malo', 'vorn', 'ines_r', 'malo_r', 'ines_m', 'malo_m')}
    # lip-sync: the mouth column of every speaker against the envelope of his voice (film time, 30 Hz)
    ix = {n: i for i, n in enumerate(FA.FACE_COLS)}; lips = {}
    for who, sp in (('ines', 'ines'), ('malo', 'malo'), ('vorn', 'vorn'), ('ines_r', 'ines'), ('malo_r', 'malo'), ('ines_m', 'ines'), ('malo_m', 'malo')):
        if who not in tr: continue
        env = json.loads(Path(ep['blocking']['plan']['actors'][who]['lipsync']['envelope']).read_text(encoding='utf-8'))['env']
        mo = np.array([max(r[ix['mo']], r[ix['ms']]) for r in tr[who]]); H = FA.HZ; n = len(mo); e = np.interp(np.arange(n) / H, np.arange(len(env)) / 30., env); m = mo
        win = np.zeros(n, bool)
        for (t0, t1) in view.actors[who].talk: win[int(t0 * H):int(t1 * H) + 1] = True
        if win.sum() > 5 and m[win].std() > 1e-6 and e[win].std() > 1e-6: lips[who] = dict(corr=round(float(np.corrcoef(m[win], e[win])[0, 1]), 3), talk_s=round(win.sum() / H, 1), mouth_open_mean=round(float(m[win].mean()), 3), mouth_shut_outside=round(float(m[~win].mean()), 4))
    rep['lipsync'] = lips
    # crowd and film
    st_n = {}; ix2 = {n: i for i, n in enumerate(c['actor_cols'])}
    for s in c['stages']: st_n[s['id']] = sum(1 for k, rows in s['actors'].items() if any(r[ix2['vis']] for r in rows[:1]))
    rep['actors_per_stage'] = st_n; rep['extras'] = sum(1 for k in c['casts'] if k.startswith('p') and k[1:].isdigit()); rep['stages'] = len(c['stages']); rep['duration'] = c['duration']
    # crowd really in the picture: extras whose chest projects inside the frame, per shot of the city (camera read at the middle of the shot)
    from hstudio.voxelgpu import camplan as CP
    crowd = {}; Cc = view.C if hasattr(view, 'C') else view
    for sh in ep['shots']:
        if sh['stage'] != 'cite': continue
        tm = sh['_t0'] + sh['dur'] / 2; r_ = CP.cam_at(sh, sh['dur'] / 2, Cc, sh['_t0']); pos, look, fov = r_[0], r_[1], r_[2]; n = 0
        for aid, spd in ep['blocking']['plan']['actors'].items():
            if spd.get('role') != 'extra': continue
            x, z = Cc.xz(aid, tm); q = CP.project(pos, look, fov, 9 / 16, [(x, 1.4, z)])[0]
            if q[2] > .5 and abs(q[0]) < .95 and abs(q[1]) < .95 and q[2] < 45: n += 1
        crowd[sh['id']] = n
    rep['extras_in_frame_per_city_shot'] = crowd; rep['extras_in_frame_mean'] = round(sum(crowd.values()) / max(1, len(crowd)), 2); rep['extras_in_frame_max'] = max(crowd.values())
    rep['events'] = {k: sum(1 for e in view.events if e['kind'] == k) for k in ('strike', 'clash', 'draw', 'take', 'touch', 'knock')}
    rep['sfx'] = len(c['audio']['sfx']); rep['sfx_names'] = sorted({e['name'] for e in c['audio']['sfx']})
    rep['ok'] = not (rep['preflight_violations'] or rep['body_on_rows'] or rep['fight'] or rep['faces'] or rep['face_stage_sync'])
    print(json.dumps({k: v for k, v in rep.items() if k != 'actors_per_stage'}, indent=1, ensure_ascii=False)); Path(a.out).write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8')
    return rep


if __name__ == '__main__': main()
