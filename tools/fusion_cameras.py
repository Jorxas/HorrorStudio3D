"""python tools/fusion_cameras.py [--only S05,S12] [--out examples/remakes/pompe_fusion_cameras.json]
Plans, with `cinematic_intent`, the cameras of the shots of the fusion film that carry a dramatic purpose, ON THE FUSION BLOCKING (the creature vanishes and reappears, it does not walk),
and freezes them in examples/remakes/pompe_fusion_cameras.json (id -> frame, camera, shake, why, relaxed). Deterministic; ~6 s per shot, no GPU.
Every plan is the planner's own: the same `camplan.audit_shot` that the film's preflight runs; what was relaxed (comfort levels) is written next to it, never hidden. If a shot cannot be
planned the planner says why in French and the shot keeps the continuity film's camera (reported, not silent)."""
import argparse, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu import cinematic_intent as CI, genre_intent as G
from hstudio.voxelgpu.films import pompe_fusion as F, remake_pompe as OLD

T = OLD.T
CAPTION_BAND = [-.1, .2]               # image y (ndc) of the caption band (caption_style y = .47 of the height, two lines)
V, A = F.VANISH['t'], F.VANISH['until']
# purpose of each beat: what the narration needs seen. S11 holds the vanish (one fixed shot), S12 the reappearance.
# Planned by the planner, then JUDGED on rendered stills (tools/fusion_preview.py), and rejected when the picture was worse than the continuity film's own camera:
REJECTED = {'S05': "plan d'intention dégradé (confort 1) : la créature, noire, y fait une dalle qui couvre la moitié de l'image ; la caméra de continuité (large, lieu lisible) est gardée",
            'S14': "plan d'intention : la tête du pompiste, grande et coupée, cache le faisceau et la créature ; la caméra de continuité (large, faisceau à travers la vitre) est gardée"}
# Written by hand because no planner purpose says « the long black hand on the glass »: outside, left of the creature, 2.4 m from the glass, fixed (no zoom, no travelling); it passes the same preflight.
MANUAL = {'S09': dict(frame=dict(actors=['ghost'], kind='medium'), shake=.08, kind='medium', relaxed=[], degraded=None, event_violations=[],
                      why="la main noire aux doigts longs posée sur la vitre, vue de l'extérieur de côté, la boutique éclairée derrière (jugé sur images, variante F de la planche s09)",
                      camera={'rig': 'path', 'keys': [dict(t=0., pos=[-1.7, 1.4, 4.8], look=[.7, 1.5, 3.7], fov=58., roll=0.), dict(t=2.0, pos=[-1.7, 1.4, 4.8], look=[.7, 1.5, 3.7], fov=58., roll=0.)]})}
BEATS = [
    dict(id='S11', purpose='disappear', witness='clerk', event=dict(kind='vanish', who='ghost', t=V), tension=.9),
    dict(id='S12', purpose='disappear', witness='clerk', event=dict(kind='appear', who='ghost', t=A), tension=.9),
    dict(id='S33', purpose='relation', subject='clerk', show=['voiture', 'vitrine'], tension=.6, min_share={'voiture': .3}),
    dict(id='S34', purpose='relation', subject='clerk', show=['entree', 'voiture'], gap=('entree', 'voiture'), tension=.7),
    dict(id='S35', purpose='relation', subject='clerk', show=['porte_reserve'], tension=.8),
    dict(id='S39', purpose='pov', pov='clerk', sees='porte_reserve', tension=.8),
]


def plan_all(only=None, verbose=True):
    ep = F.episode(cameras=False); view, geo = G.compile_episode(ep)
    ctx = CI.Ctx(geo, view, '9:16', avoid=CAPTION_BAND); out = {}; refused = {}
    for b in BEATS:
        if only and b['id'] not in only: continue
        i = int(b['id'][1:]); it = dict(b, t0=T[i], t1=T[i + 1])
        t0 = time.time()
        try:
            s = CI.plan_shot(ctx, CI.normalise(it, geo, view), CI.base_size(CI.normalise(it, geo, view)))
        except CI.PlanError as e:
            refused[b['id']] = str(e)
            if verbose: print(f"  {b['id']} REFUSÉ : {e}")
            continue
        ev = [x.to_json() for x in CI.audit_event(dict(id=s['id'], t0=T[i], dur=s['dur'], camera=s['camera'], event=b['event']), view, geo)] if b.get('event') else []
        out[b['id']] = dict(frame=s['frame'], camera=s['camera'], shake=s['shake'], why=s['why'], kind=s['kind'], relaxed=list(s.get('relaxed') or []), degraded=s.get('degraded'), event_violations=ev)
        if verbose: print(f"  {b['id']} {s['kind']:10s} {time.time() - t0:4.1f}s relaxed={s.get('relaxed')} event_violations={len(ev)}", flush=True)
    return out, refused


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--only', default=''); ap.add_argument('--out', default=str(F.CAMERAS_FILE)); a = ap.parse_args()
    only = set(a.only.split(',')) if a.only else None
    out, refused = plan_all(only)
    for k, v in MANUAL.items():
        if not only or k in only:
            dur = T[int(k[1:]) + 1] - T[int(k[1:])]; v['camera']['keys'][-1]['t'] = round(dur, 4); out[k] = v
    p = Path(a.out); old = json.loads(p.read_text(encoding='utf-8')) if (only and p.exists()) else {}
    old.update(out); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(old, indent=1, ensure_ascii=False, default=float), encoding='utf-8')
    print('écrit', p, '; refusés :', refused or 'aucun')
