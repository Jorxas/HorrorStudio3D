"""Mesure, sur de VRAIES images rendues, la place que le corps d'un personnage prend dans son propre cadre.

    python tools/cadrage_qc.py examples/demos/demo20_decors.json --aspect 9:16
    python tools/cadrage_qc.py examples/demos/demo20_decors.json --set camera_clear_face --set camera_face_track
    python tools/cadrage_qc.py examples/demos/demo20_decors.json --face-detail hd --every .4 --json out.json

Pourquoi un outil de plus, alors que `tools/cine_check.py` existe deja : `cine_check` mesure des **angles** (le
visage est-il tourne vers la camera) a partir des observations du moteur. Il ne voit pas le defaut signale par le
proprietaire -- *l'avant-bras qui remplit les gros plans* -- parce que ce defaut n'est pas un angle de visage :
c'est une **surface d'image**, et elle ne se lit que sur l'image.

Ce que l'outil compte, pixel par pixel, sur le tampon d'indices du lanceur de rayons (pas sur les couleurs) :

| mesure | ce que c'est |
|---|---|
| `bras` | part de l'image occupee par les bras, mains et objet tenu du personnage lui-meme |
| `tete` | part de l'image occupee par sa tete (boite du crane + cheveux + chapeau) |
| `visage_mange` | part de sa tete que **son propre bras** cache -- mesuree en rendant deux fois, une fois avec les bras masques |
| `corps` | part de l'image occupee par le personnage entier |

Aucun reseau, aucune cle, aucun ffmpeg : le lanceur de rayons est appele directement en basse resolution
(216x384 en 9:16), la ou les pixels sont decides. Deterministe.
"""
import os, sys, json, copy, math, argparse
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

ARM_PARTS = ('upperL', 'upperR', 'foreL', 'foreR', 'handL', 'handR', 'hold')
HEAD_PARTS = ('head',)
TIGHT = ('close', 'extreme_close', 'medium', 'medium_full', 'ots', 'dialogue')


def build(scene, aspect, episode_keys=(), cast_keys=()):
    """le meme montage que tools/cine_check.py, plus des cles posees a la main (sans toucher au fichier de demo)"""
    from hstudio.demos import timed_lines, state_after
    from hstudio.pipeline import make_engine
    sc = scene if isinstance(scene, dict) else json.load(open(scene, encoding='utf-8'))   # dict: a scene already in memory
    if 'script' in sc and 'episode' in sc:
        ep = copy.deepcopy(sc['episode']); ep['style'] = sc.get('style', 'pixel3d')
        lines = timed_lines(sc['script'], float(sc.get('gap', .3)), float(sc.get('lead', .4)))
        if ep.get('series'): ep['series_state'] = state_after(sc['follows']) if sc.get('follows') else {}
        for i, s_ in enumerate(sc['script']):
            if s_.get('who'): ep.setdefault('lines', {}).setdefault(str(i), {})['speaker'] = s_['who']
    else:
        from scene_sheet import scene_lines
        ep = copy.deepcopy(sc); lines = scene_lines(ep)
    for k, v in episode_keys: ep[k] = v
    for k, v in cast_keys:
        for c in (ep.get('cast') or {}).values():
            if isinstance(c, dict): c[k] = v
    return ep, lines, make_engine(ep.get('style', 'pixel3d'), ep, lines, np.zeros(10), lines[-1]['end'] + .1, aspect)


def frame_parts(ctx, g):
    """-> (part de l'image par partie du corps, part de la tete cachee par le bras du personnage, plan)"""
    from hstudio.engines.pixel3d import r3d, rigfig
    from hstudio.engines.pixel3d.frame import build_frame
    rigfig.PARTS = parts = {}
    try:
        sc, cam, L, shot, T, u, k, state = build_frame(ctx, g)
    finally:
        rigfig.PARTS = None
    pos, yaw, pitch, roll, fov = cam
    pos = np.asarray(pos, np.float32)
    D = r3d.cam_dirs(yaw, pitch, roll, fov)
    ceil = sc.ceil_y if (sc.ceil_y is not None or getattr(sc, 'sky_fn', None) is None) else np.inf
    fy = float(getattr(sc, 'floor_y', 0.))

    def seen(boxes):
        bx = r3d.cull(boxes, pos, yaw, pitch, fov)
        _, ib = r3d.trace(pos, D, bx, fy, ceil, True, r3d._noise)
        out = {}
        for i, c in zip(*np.unique(ib, return_counts=True)):
            if int(i) >= 0: out[id(bx[int(i)])] = out.get(id(bx[int(i)]), 0) + int(c)
        return out, ib.size

    hits, n = seen(sc.boxes)
    share = {}
    for name, boxes in parts.items():
        share[name] = sum(hits.get(id(b), 0) for b in boxes) / n
    head0 = sum(share.get(p, 0.) for p in HEAD_PARTS)
    arms = [b for name in ARM_PARTS for b in parts.get(name, [])]
    eaten = 0.
    if head0 > 0 and arms:                      # la tete sans les bras : la difference est ce que le bras mange
        was = [b.hidden for b in arms]
        for b in arms: b.hidden = True
        try:
            hits2, _ = seen(sc.boxes)
        finally:
            for b, w in zip(arms, was): b.hidden = w
        head1 = sum(hits2.get(id(b), 0) for name in HEAD_PARTS for b in parts.get(name, [])) / n
        eaten = max(0., head1 - head0) / head1 if head1 > 0 else 0.
    return share, eaten, k, (shot.get('camera') or {}).get('shot')


def measure(ctx, duration, every=.5):
    rows = []
    g = 0.
    while g < duration:
        share, eaten, k, kind = frame_parts(ctx, g)
        rows.append(dict(t=round(g, 2), shot=k, kind=kind or 'auto',
                         bras=sum(share.get(p, 0.) for p in ARM_PARTS),
                         tete=sum(share.get(p, 0.) for p in HEAD_PARTS),
                         corps=sum(share.values()), visage_mange=eaten))
        g += every
    return rows


def summary(rows):
    per = {}
    for r in rows:
        p = per.setdefault(r['shot'], dict(kind=r['kind'], n=0, bras=0., tete=0., corps=0., mange=0., bras_max=0., mange_max=0., t_max=0.))
        p['n'] += 1
        for a, b in (('bras', 'bras'), ('tete', 'tete'), ('corps', 'corps'), ('mange', 'visage_mange')): p[a] += r[b]
        if r['bras'] > p['bras_max']: p['bras_max'] = r['bras']; p['t_max'] = r['t']
        p['mange_max'] = max(p['mange_max'], r['visage_mange'])
    return per


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('scene'); ap.add_argument('--aspect', default='9:16'); ap.add_argument('--every', type=float, default=.5)
    ap.add_argument('--set', action='append', default=[], help='cle d\'episode a poser (cle ou cle=valeur)')
    ap.add_argument('--face-detail', default=None, help='pose "face_detail" sur tout le casting')
    ap.add_argument('--json', default='')
    a = ap.parse_args()
    eks = []
    for it in a.set:
        k, _, v = it.partition('=')
        eks.append((k, True if v == '' else (json.loads(v) if v[0] in '[{"0123456789tfn' else v)))
    cks = [('face_detail', a.face_detail)] if a.face_detail else []
    ep, lines, eng = build(a.scene, a.aspect, eks, cks)
    rows = measure(eng.ctx, lines[-1]['end'], a.every)
    per = summary(rows)
    tight = [r for r in rows if r['kind'] in TIGHT]
    print(f"{os.path.basename(a.scene)}  {a.aspect}  {len(rows)} images  cles: {eks or 'aucune'} {cks or ''}")
    print('  plan  type           bras%  (max)   tete%  corps%  visage mange%  (max)')
    for k in sorted(per, key=lambda x: float(x)):
        p = per[k]; n = p['n']
        print(f"  {str(k):>4s}  {p['kind']:13s} {100*p['bras']/n:5.1f}  ({100*p['bras_max']:4.1f} a {p['t_max']}s)"
              f"  {100*p['tete']/n:5.1f}  {100*p['corps']/n:5.1f}   {100*p['mange']/n:5.1f}  ({100*p['mange_max']:4.1f})")
    if tight:
        print(f"  PLANS SERRES ({len(tight)} images) : bras {100*sum(r['bras'] for r in tight)/len(tight):.2f} %"
              f" de l'image, pire {100*max(r['bras'] for r in tight):.1f} %"
              f" | visage mange par son propre bras {100*sum(r['visage_mange'] for r in tight)/len(tight):.2f} %"
              f", pire {100*max(r['visage_mange'] for r in tight):.1f} %")
    if a.json:
        json.dump(dict(scene=a.scene, aspect=a.aspect, keys=eks, cast=cks, rows=rows,
                       per_shot={str(k): v for k, v in per.items()}), open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('  ecrit', a.json)


if __name__ == '__main__': main()
