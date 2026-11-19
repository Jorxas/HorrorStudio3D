"""Checks the figurant PLAN without rendering anything: a few seconds, no ffmpeg, no API, no cost.

    python tools/check_background_plan.py
    python tools/check_background_plan.py --json docs/figurants/plan_figurants.json

What it asserts, and why each one is here rather than in a renderer:

  1. OFF BY DEFAULT.  `background.apply()` on an episode with no "extras" key returns THE SAME OBJECT. Every
     demo of examples/demos/ and every scene of examples/scenes/ is passed through it and must come out
     byte-identical, because this lot promises that no existing render moves.
  2. THE GLOBAL SWITCH.  HSTUDIO_EXTRAS=0 must make even a scene that asks for figurants come out unchanged.
  3. DETERMINISM.  The same scene expanded twice gives the same JSON, to the digit (the delays and the lateral
     offsets come from a hash of the seed and the figurant id, never from random).
  4. IDEMPOTENCE.  Expanding an already expanded episode adds nothing (make_engine is called once for the mix
     and once per render worker, on a pickled copy; a double expansion would double the troupe).
  5. WALKABLE GROUND.  Every lane waypoint, every standing spot and every point the plan aims at is re-measured
     against the REAL obstacles of the place (`SetWorld.obstacles()` built from the real boxes of the set), with
     the same body radius the path planner uses, and every straight lane segment is checked with the planner's
     own `line_free`. This is the check that would catch a place generator moving a bus shelter.
  6. DISTANCES ON PAPER.  No two planned points closer than MIN_GAP; no lane running closer to a lead than
     `clear`; every startle inside [threat, threat + REACT_WINDOW].
  7. FOUR DIFFERENT PEOPLE.  The troupe must differ by SILHOUETTE (outfit, hat, hair, scale) and not only by
     colour: four recolours of one hoodie would satisfy a diff and fail the eye.
  8. THE A/B PAIR.  extras_rue_vide.json must be extras_rue_vivante.json minus the single "extras" key.
  9. THE BRICK IS NOT PIXEL3D-SPECIFIC.  The same scene is built and drawn by BOTH engines, the figurants are
     in both casts, and CONSOLE 2D stays a visibly DIFFERENT drawing. This section also measures a defect of
     the shipped console engine that predates this lot (see the comment in `section_engines`).
 10. NO DEAD BEAT.  Every verb registered in `BEATS` is exercised, including the two the delivered scene does
     not use (`escort`, `hold`).

Exit code 0 only if every line of the report says OK.
"""
import os, sys, json, math, copy, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from hstudio.acting import background as BG                       # noqa: E402
from hstudio.acting.timeline import Grid                          # noqa: E402

SCENES = os.path.join(ROOT, 'examples', 'scenes')
DEMOS = os.path.join(ROOT, 'examples', 'demos')
VIVANTE = os.path.join(SCENES, 'extras_rue_vivante.json')
VIDE = os.path.join(SCENES, 'extras_rue_vide.json')
IGNORE_IN_PAIR = ('title', 'description', 'note')

bad = []


def check(ok, label, detail=''):
    print(('  OK    ' if ok else '  ECHEC ') + label + (('   ' + detail) if detail else ''))
    if not ok:
        bad.append(label)
    return ok


def scene_episode(path):
    sc = json.load(open(path, encoding='utf-8'))
    return sc, copy.deepcopy(sc.get('episode') or sc)


def world_of(ep, set_name):
    """the real world of a set of the episode, the very object the acting layer walks in"""
    from hstudio.engines.pixel3d import sets as S, places as PL, stage as ST
    spec = dict(((ep.get('sets') or {}).get(set_name) or {}))
    t = spec.pop('type', None)
    full = PL.PLACES[t](dict(spec, type=t)) if t in PL.PLACES else dict(spec)
    return ST.SetWorld(S.RoomSet(full))


# ------------------------------------------------------------------ 1-2. the switches
def section_switches():
    print('\n-- 1. desactive par defaut : tout episode sans cle "extras" ressort INCHANGE --')
    files = sorted(os.listdir(DEMOS)) + [f for f in sorted(os.listdir(SCENES)) if f != os.path.basename(VIVANTE)]
    same, n = 0, 0
    for f in files:
        p = os.path.join(DEMOS if os.path.exists(os.path.join(DEMOS, f)) else SCENES, f)
        if not f.endswith('.json'):
            continue
        sc, ep = scene_episode(p)
        before = json.dumps(ep, sort_keys=True, ensure_ascii=False)
        out = BG.apply(ep)
        n += 1
        if out is ep and json.dumps(out, sort_keys=True, ensure_ascii=False) == before:
            same += 1
        else:
            print('      change : ' + f)
    check(same == n, f'{same}/{n} episodes sans la cle ressortent identiques (meme objet)')

    print('\n-- 2. interrupteur global HSTUDIO_EXTRAS=0 --')
    sc, ep = scene_episode(VIVANTE)
    before = json.dumps(ep, sort_keys=True, ensure_ascii=False)
    os.environ['HSTUDIO_EXTRAS'] = '0'
    try:
        out = BG.apply(ep)
        check(out is ep and json.dumps(out, sort_keys=True, ensure_ascii=False) == before,
              'HSTUDIO_EXTRAS=0 : la scene VIVANTE elle-meme ressort inchangee')
    finally:
        os.environ.pop('HSTUDIO_EXTRAS', None)
    check(BG.enabled(), 'sans variable d environnement, l expansion est disponible (la cle de scene decide)')


# ------------------------------------------------------------------ 3-4. determinism and idempotence
def section_stability(ep):
    print('\n-- 3. determinisme et 4. idempotence --')
    a = BG.expanded(copy.deepcopy(ep))
    b = BG.expanded(copy.deepcopy(ep))
    check(json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(b, sort_keys=True, ensure_ascii=False),
          'deux expansions de la meme scene donnent le meme JSON')
    c = BG.apply(copy.deepcopy(a))
    n_a = sum(len(s.get('actions') or []) for s in a['shots'])
    n_c = sum(len(s.get('actions') or []) for s in c['shots'])
    check(n_a == n_c, 'reexpanser un episode deja expanse n ajoute rien',
          f'{n_a} actions avant, {n_c} apres')
    return a


# ------------------------------------------------------------------ 5. walkable ground
def section_ground(ep, pl, plan_points):
    print('\n-- 5. sol praticable, mesure sur les VRAIS obstacles du lieu --')
    set_name = pl.set
    w = world_of(ep, set_name)
    g = Grid(w)                                   # the planner's own grid: same body radius, same cell
    obs = w.obstacles()
    print(f'     lieu « {((ep.get("sets") or {}).get(set_name) or {}).get("type")} » : {len(obs)} obstacles, '
          f'bornes {[round(float(v), 1) for v in w.bounds()]}')
    free = []
    for tag, p in plan_points:
        i, j = g.cell(p[0], p[1])
        ok = g.free(i, j)
        free.append((tag, p, ok))
        if not ok:
            print(f'      bloque : {tag} {p}')
    check(all(o for _, _, o in free), f'{sum(1 for _, _, o in free if o)}/{len(free)} points du plan sont libres')

    segs = []
    for name, pts in sorted(pl.lanes.items()):
        if not isinstance(pts, list):
            continue
        for fid in pl.troupe:
            if BG.FIGURANTS[fid]['lane'] != name:
                continue
            line = pl.lane(fid)
            for k in range(len(line) - 1):
                ok = g.line_free(line[k], line[k + 1])
                segs.append(ok)
                if not ok:
                    print(f'      segment bloque sur « {name} » pour {fid} : {line[k]} -> {line[k + 1]}')
    check(all(segs), f'{sum(1 for s in segs if s)}/{len(segs)} segments de voie sont marchables en ligne droite')
    return w


# ------------------------------------------------------------------ 6. distances on paper
def section_distances(pl, plan_points, ep_exp):
    print('\n-- 6. distances et synchronisation, sur le plan --')
    worst = None
    for i in range(len(plan_points)):
        for j in range(i + 1, len(plan_points)):
            (ta, a), (tb, b) = plan_points[i], plan_points[j]
            if ta.split(':')[0] == tb.split(':')[0]:        # the same figurant at two moments: not a collision
                continue
            d = math.hypot(a[0] - b[0], a[1] - b[1])
            if worst is None or d < worst[0]:
                worst = (d, ta, tb)
    check(worst is None or worst[0] >= BG.MIN_GAP,
          f'deux points vises par deux figurants differents restent a >= {BG.MIN_GAP} m',
          f'le plus serre : {worst[0]:.2f} m ({worst[1]} / {worst[2]})' if worst else '')

    check(BG.PASS_GAP > BG.BODY + .2,
          'la distance de croisement reste au-dessus du seuil d interpenetration',
          f'PASS_GAP {BG.PASS_GAP} m contre BODY {BG.BODY} m')
    lc = pl.lane_clearance()
    print('     distance des voies au premier role : ' + ', '.join(f'{k} {v:.2f} m' for k, v in sorted(lc.items())))
    check(all(v >= pl.clear for v in lc.values()),
          f'aucune voie ne passe a moins de clear = {pl.clear:.2f} m d un premier role')

    threats = [(int(b['shot']), float(b.get('at', 0.))) for b in (pl.spec.get('beats') or [])
               if b.get('do') == 'threat']
    ev = [(s, f, k, t) for (s, f, k, t) in pl.events if k == 'react']
    ok = True
    for (s, f, k, t) in ev:
        at = next((a for (sh, a) in threats if sh == s), None)
        inside = at is not None and at <= t <= at + BG.REACT_WINDOW
        ok = ok and inside
        print(f'     plan {s} : {f:<9} sursaute a t = {t:.2f} s   (menace a {at:.2f} s, '
              f'retard {t - at:+.2f} s)' if at is not None else f'     plan {s} : {f} sans menace')
    check(ok and bool(ev), f'chaque sursaut tombe dans [menace, menace + {BG.REACT_WINDOW} s]')
    check(len({round(t, 2) for (_, _, _, t) in ev}) == len(ev),
          'les sursauts ne tombent pas tous sur la meme image (reactions individuelles)')

    shots_with = sorted({s for s in range(len(ep_exp['shots']))
                         if any(a.get('who') in pl.troupe for a in (ep_exp['shots'][s].get('actions') or []))})
    check(len(shots_with) >= 3, 'les figurants agissent dans au moins 3 plans', f'plans {shots_with}')


# ------------------------------------------------------------------ 7. four different people
def section_identities(pl):
    print('\n-- 7. quatre personnes differentes, pas quatre teintes --')
    rows = []
    for fid in pl.troupe:
        f = BG.FIGURANTS[fid]
        L = f['look']
        rows.append((fid, L.get('outfit'), L.get('hat', 'none'), L.get('hair_style'),
                     f.get('scale', 1.0), f['role']))
    for r in rows:
        print('     %-9s vetement %-7s couvre-chef %-7s cheveux %-7s echelle %.2f  role %s' % r)
    # what the eye actually reads at twelve metres in a 9:16 frame is the SILHOUETTE: the garment, the head, the
    # stature. So: no two figurants may share a head (hat + hair), no two may share a garment, and each of the
    # three families must offer at least three distinct values -- a troupe of five is allowed to repeat a bare
    # head once, it is not allowed to be five variations of one.
    heads = [(r[2], r[3]) for r in rows]
    check(len(set(heads)) == len(heads), 'aucune tete en double (couvre-chef + coiffure)', str(heads))
    outfits = [r[1] for r in rows]
    check(len(set(outfits)) == len(outfits), 'les vetements sont tous differents', str(outfits))
    for k, name, need in ((2, 'couvre-chefs', 3), (3, 'coiffures', 3)):
        vals = sorted({r[k] for r in rows})
        check(len(vals) >= min(need, len(rows)), f'au moins {need} {name} distincts', str(vals))
    check(len({r[4] for r in rows}) >= 3, 'au moins trois tailles differentes',
          str(sorted({r[4] for r in rows})))
    from hstudio.engines.pixel3d import poses as P
    okv = all(r[1] in P.OUTFITS for r in rows) and all(r[2] in P.HATS for r in rows) \
        and all(r[3] in P.HAIR_STYLES or r[3] in P.STRAND_STYLES for r in rows)
    check(okv, 'tous les habits/coiffures/chapeaux sont des valeurs que le moteur connait deja')


# ------------------------------------------------------------------ 8. the A/B pair
def section_pair():
    print('\n-- 8. la paire A/B ne differe que par la cle "extras" --')
    a = json.load(open(VIVANTE, encoding='utf-8'))
    b = json.load(open(VIDE, encoding='utf-8'))
    ok = 'extras' in (a.get('episode') or {}) and 'extras' not in (b.get('episode') or {})
    check(ok, 'VIVANTE porte la cle, VIDE ne la porte pas')
    a2 = copy.deepcopy(a)
    a2['episode'].pop('extras', None)
    for k in IGNORE_IN_PAIR:
        a2.pop(k, None)
        b = dict(b)
        b.pop(k, None)
    check(json.dumps(a2, sort_keys=True, ensure_ascii=False) == json.dumps(b, sort_keys=True, ensure_ascii=False),
          'hors titre/description/note, les deux fichiers sont identiques')


# ------------------------------------------------------------------ 9. the brick is not pixel3d-specific
def section_engines(scene):
    """La couche de jeu doit rester independante du moteur (AGENTS.md). `background.py` n'importe rien de
    pixel3d, et la preuve utile n'est pas de lire les imports : c'est de faire jouer la MEME scene par les DEUX
    moteurs. CONSOLE 2D doit rester distinct et inchange -- il dessine ses figurants avec sa propre figure a
    plat, a partir des memes cles de look, et une scene sans la cle doit lui donner exactement ce qu'elle lui
    donnait avant."""
    print('\n-- 9. les deux moteurs jouent la meme brique (CONSOLE 2D reste distinct) --')
    import numpy as np
    from hstudio.pipeline import make_engine, duration_of
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    from locomotion_qc import read_scene
    ep, lines = read_scene(scene)
    dur = duration_of(ep, lines)

    # DEFAUT HISTORIQUE, ANTERIEUR A CE LOT, mesure ici et pas corrige ici.
    # engines/console/render.py:686 fait `if on in samples` ou `on` est la valeur de `camera.on`. Le DSL
    # documente une LISTE (`"on": ["lea", "tom"]`), et une liste n'est pas hachable : le moteur CONSOLE leve
    # `TypeError: unhashable type: 'list'` sur tout plan qui en contient. Ce n'est pas une consequence des
    # figurants : `demo2_dialogue` et `demo3_groupe`, deux demos LIVREES, tombent exactement pareil (la seule
    # demo console du catalogue, `demo5_console`, n'utilise que des chaines, ce qui explique que personne ne
    # l'ait rencontre). Le correctif tient en une ligne, mais `engines/console/` appartient aux lots
    # CONSOLE 2D : il est propose dans docs/FIGURANTS_SCENES_VIVANTES.md, pas applique ici.
    broken = []
    for demo in ('demo2_dialogue', 'demo3_groupe'):
        from hstudio import demos as D
        sc = D.load(demo)
        e2 = copy.deepcopy(sc['episode'])
        e2['style'] = 'console'
        try:
            make_engine('console', e2, D.timed_lines(sc['script']), np.zeros(10),
                        duration_of(e2, D.timed_lines(sc['script'])), '9:16').frame(2.0)
        except TypeError as exc:
            broken.append((demo, str(exc)[:40]))
    print('     defaut historique du moteur CONSOLE (render.py:686, `camera.on` en liste) : '
          + (', '.join(f'{d} -> {m}' for d, m in broken) if broken else 'plus la (corrige ailleurs ?)'))
    print('     il frappe des demos LIVREES, donc il est anterieur a ce lot et n est pas corrige ici.')

    imgs = {}
    for style in ('pixel3d', 'console'):
        e = copy.deepcopy(ep)
        e['style'] = style
        if style == 'console':      # contournement du defaut ci-dessus, cote OUTIL, pour pouvoir mesurer
            for sh in e['shots']:
                c = sh.get('camera') or {}
                if isinstance(c.get('on'), list):
                    c['on'] = c['on'][0] if c['on'] else None
        try:
            eng = make_engine(style, e, lines, np.zeros(10), dur, '9:16')
            cast = sorted((eng.ctx.ep if hasattr(eng, 'ctx') else e).get('cast') or {})
            im = eng.frame(dur * .3).convert('RGB')
            imgs[style] = (im, cast)
            print(f'     {style:<8} image {im.size}   distribution : {", ".join(cast)}')
        except Exception as exc:
            print(f'     {style:<8} ECHEC : {type(exc).__name__}: {str(exc)[:120]}')
    check(len(imgs) == 2, 'les deux moteurs construisent et dessinent la scene avec figurants')
    if len(imgs) == 2:
        pl, _ = BG.plan(copy.deepcopy(ep))
        for style, (_, cast) in imgs.items():
            check(all(f in cast for f in pl.troupe), f'{style} : les quatre figurants sont bien dans sa distribution')
        a = np.asarray(imgs['pixel3d'][0].resize((108, 192))).astype(np.int16)
        b = np.asarray(imgs['console'][0].resize((108, 192))).astype(np.int16)
        d = float(np.abs(a - b).mean())
        check(d > 8., 'CONSOLE 2D reste un dessin DISTINCT de PIXEL 3D, pas une copie', f'ecart moyen {d:.1f}/255')


# ------------------------------------------------------------------ 10. no dead beat
def section_beats():
    """Chaque temps enregistre dans `BEATS` doit produire quelque chose. Un registre ou l'un des verbes ne
    serait jamais appele par la scene livree est exactement l'endroit ou du code mort s'installe : `escort`
    (un figurant suit un premier role) et `hold` ne sont pas utilises par extras_rue_vivante.json, ils sont
    donc exerces ici."""
    print('\n-- 10. tous les temps du registre produisent quelque chose --')
    base = {'default_set': 'rue', 'sets': {'rue': {'type': 'city_street'}},
            'cast': {'lea': {'ref': 'lea'}},
            'shots': [{'actors': [{'id': 'lea', 'at': [-0.9, 6.0]}]}, {}]}
    for name in sorted(BG.BEATS):
        ep = copy.deepcopy(base)
        b = {'shot': 1, 'do': name}
        if name == 'threat':
            b.update(at=0.6, **{'from': [0.4, 23.0]})
        if name == 'flee':
            b['from'] = [0.4, 23.0]
        if name == 'greet':
            b.update(who=['vendeur', 'mamie'], pair=['vendeur', 'mamie'])
        if name == 'escort':
            b['target'] = 'lea'
        ep['extras'] = {'seed': 5, 'troupe': ['passante', 'flaneur', 'vendeur', 'mamie'],
                        'beats': [{'shot': 0, 'do': 'life'}, b]}
        out = BG.expanded(ep)
        acts = [a for a in (out['shots'][1].get('actions') or []) if a.get('who') in BG.FIGURANTS]
        verbs = sorted({a.get('do') for a in acts})
        steps = [s for s in (BG.report(out) or {}).get('steps', []) if s[0] == 1]
        ok = bool(acts) or (name == 'hold' and bool(steps))
        check(ok, f'« {name} » produit quelque chose', f'{len(acts)} actions {verbs}' if acts else f'{len(steps)} traces')
    check(set(BG.BEATS) >= {'life', 'greet', 'threat', 'flee', 'escort', 'hold'},
          'les six temps documentes existent', str(sorted(BG.BEATS)))


def plan_points(pl, ep_exp):
    """every point the plan puts a body at or sends a body to, tagged `figurant:what`"""
    out = []
    for s in ep_exp['shots']:
        for a in s.get('actors') or []:
            if a.get('id') in pl.troupe:
                out.append((f'{a["id"]}:depart', (float(a['at'][0]), float(a['at'][1]))))
        for a in s.get('actions') or []:
            if a.get('who') in pl.troupe and isinstance(a.get('to'), list):
                out.append((f'{a["who"]}:{a.get("do")}', (float(a['to'][0]), float(a['to'][1]))))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', default='')
    ap.add_argument('--scene', default=VIVANTE)
    a = ap.parse_args()
    print('=' * 78)
    print('== PLAN DES FIGURANTS : ' + os.path.relpath(a.scene, ROOT))
    print('=' * 78)

    section_switches()
    sc, ep = scene_episode(a.scene)
    ep_exp = section_stability(ep)
    pl, _ = BG.plan(copy.deepcopy(ep))
    rep = BG.report(ep_exp) or {}
    print('\n     troupe : ' + ', '.join(f'{f} ({BG.FIGURANTS[f]["label"]})' for f in rep.get('troupe', [])))
    print('     graine : ' + str(rep.get('seed')) + '   voies : ' + str(rep.get('lanes'))
          + '   ecart lateral : ' + json.dumps(rep.get('lat', {})))
    for n in rep.get('notes') or []:
        print('     NOTE : ' + n)
    check(not (rep.get('notes') or []), 'le plan ne signale aucun probleme')
    print('\n     la trace du plan :')
    for (s, f, what, t) in rep.get('steps') or []:
        print(f'       plan {s}  t={t:5.2f} s  {f:<9} {what}')

    pts = plan_points(pl, ep_exp)
    w = section_ground(ep, pl, pts)
    section_distances(pl, pts, ep_exp)
    section_identities(pl)
    section_pair()
    section_engines(a.scene)
    section_beats()

    print('\n' + '=' * 78)
    print(('ECHEC : ' + ', '.join(bad)) if bad else 'Tout est OK.')
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        json.dump({'scene': os.path.relpath(a.scene, ROOT), 'rapport': rep,
                   'points': [[t, list(p)] for t, p in pts],
                   'obstacles': len(w.obstacles()), 'echecs': bad},
                  open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('mesures : ' + a.json)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
