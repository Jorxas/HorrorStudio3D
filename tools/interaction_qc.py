"""Mesure, en metres et sur les VRAIES poses jouees, si la main d'un personnage PIXEL 3D atterrit la ou elle
attrape -- la poignee d'une porte, la cle posee sur une table, la main de l'autre.

    python tools/interaction_qc.py                                  # les deux scenes, les trois configurations
    python tools/interaction_qc.py --scene examples/demos/demo1_mouvement.json
    python tools/interaction_qc.py --json docs/p1_interaction/interaction.json

POURQUOI UN OUTIL DE PLUS. `tools/corps_qc.py` mesure la silhouette, `tools/cadrage_qc.py` la place du corps
dans le cadre : aucun des deux ne voit le defaut que ce lot corrige, parce que ce n'est ni une proportion ni
une surface d'image. C'est une **distance** : la refonte du corps (`"body": "refit"`) rentre toute la chaine du
bras de 6,5 cm, alors que la cinematique inverse de `reach`, qui vit dans `acting/rig.py`, continue de viser la
poignee d'origine. La main DESSINEE manquait donc la poignee de 6,5 cm, et aucune mesure du lot precedent ne
pouvait l'apercevoir.

CE QUI EST MESURE, et comment :

| mesure | ce que c'est |
|---|---|
| `main_cible` | distance entre l'articulation de la main **telle que le rendu la dessine** et le point attrape, au moment ou la prise est pleine (poids d'interpolation 1) |
| `pire` | la pire de ces distances sur la scene |
| `os` | les longueurs d'os du bras lues sur le squelette : la correction ne doit pas etirer la chaine |
| `tete_cadre` | hauteur de la tete dans son propre cadre, lue sur l'image rendue (part de la hauteur depuis le haut) : la refonte change le corps, elle ne doit pas deplacer la composition |

La main n'est pas lue sur une intention : elle passe par `acted.arm_points`, c'est-a-dire par la meme
`bodies.solve` que `rigfig.build`, puis par la meme transformation (echelle du personnage, cap, position). Si
le rendu et cette mesure divergeaient un jour, `tools/check_corps.py` echouerait avant cet outil.

Trois configurations, la deuxieme etant le defaut garde mesurable (comme `tete_seule` pour les proportions) :

    defaut        -> aucune cle "body" : le rendu livre
    refit_defaut  -> {"style": "refit", "reach_fix": 0} : la refonte SANS la correction
    refit         -> {"style": "refit"} : la refonte avec

Aucun reseau, aucune cle d'API, aucun ffmpeg pour les distances (le lanceur de rayons n'est appele que pour
`tete_cadre`, en 216x384). Deterministe.
"""
import os, sys, json, copy, math, argparse

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

CONFIGS = [('defaut', None),
           # le corps cubique et sa finition premium (lots P1 Minecraft et P1 voxel premium) rejoignent la
           # mesure : ils elargissent les epaules au lieu de rentrer les bras (`arm_in` negatif), donc la
           # correction `aimed` les corrige dans l'autre sens, et `voxel_premium` ajoute un POING sous
           # l'articulation de la main. Aucun des deux ne doit eloigner la main de ce qu'elle attrape.
           ('minecraft', 'minecraft'),
           ('voxel_premium', 'voxel_premium')]

# la scene « porte » : demo1_mouvement, plus UNE action d'ouverture de porte dans son premier plan. La demo
# n'est pas modifiee sur le disque ; elle est chargee, copiee, et l'action est posee dans la copie. C'est le
# seul moyen de mesurer une poignee de porte, parce qu'aucune demo livree ne fait ouvrir une porte par un
# personnage en PIXEL 3D (les `open` de demo5 et demo11 sont le petit jeu 2D de l'ecran CONSOLE).
# `wait` d'abord : le carton de titre de l'episode couvre le milieu de l'image pendant les premieres secondes,
# et une planche prise dessous ne montrerait rien. La camera du plan est posee aussi, parce qu'un plan large
# ne montre pas une poignee de porte. Ni l'une ni l'autre ne change la mesure, qui est geometrique et ne
# regarde aucune image -- elles ne servent qu'a ce que la planche de `tools/interaction_sheet.py` soit lisible.
PORTE_ACTIONS = [{'who': 'lea', 'do': 'wait', 'dur': 3.4},
                 {'who': 'lea', 'do': 'open', 'door': 'porte', 'dur': 1.1}]
PORTE_CAMERA = {'shot': 'medium_full', 'on': ['lea']}
# la scene « gros plan ecrit a la main » : la meme demo, dont le dernier plan passe en camera preset `closeup`
# visant `lea`. Aucune demo livree n'utilise ce chemin (toutes passent par le cadreur automatique, qui connait
# deja la tete refondue) : c'est pourtant le chemin que le proprietaire emprunte des qu'il ecrit une camera a
# la main, et c'est la que la hauteur de visee 1,68 m etait restee une constante.
CLOSEUP_CAMERA = {'preset': 'closeup', 'subject': 'lea'}


def scenes(which='toutes'):
    """-> [(nom, scene en memoire)] : la demo telle quelle, et la meme avec une ouverture de porte"""
    base = json.load(open(os.path.join(ROOT, 'examples', 'demos', 'demo1_mouvement.json'), encoding='utf-8'))
    out = []
    if which in ('toutes', 'objet'): out.append(('demo1 / prendre la cle', copy.deepcopy(base)))
    if which in ('toutes', 'porte'):
        sc = copy.deepcopy(base)
        # posees EN TETE des actions du premier plan : une action ajoutee a la fin se joue apres la fin de la
        # fenetre du plan (7,2 s ici) et ne serait jamais rendue -- mesurable, mais invisible sur une planche
        sh = sc['episode']['shots'][0]
        sh['actions'] = [dict(a) for a in PORTE_ACTIONS] + list(sh.get('actions') or [])
        sh['camera'] = dict(PORTE_CAMERA)
        out.append(('demo1 + ouvrir la porte', sc))
    if which in ('toutes', 'closeup'):
        sc = copy.deepcopy(base)
        for sh in sc['episode']['shots'][1:]: sh['camera'] = dict(CLOSEUP_CAMERA)
        out.append(('demo1 + gros plan ecrit a la main', sc))
    return out


def grips(scene, body, aspect='16:9'):
    """toutes les prises d'une scene, pour une configuration de corps : [(plan, qui, quoi, cible, main, ecart)]"""
    from cadrage_qc import build
    from hstudio.engines.pixel3d import acted, bodies
    from hstudio.acting import rig
    keys = [('body', body)] if body else []
    ep, lines, eng = build(copy.deepcopy(scene), aspect, keys)
    st = bodies.configure(ep.get('body')) if ep.get('body') else None
    was = bodies.active(); bodies.use(st)
    try:
        ac = eng.ctx.get_acting()
        looks = ep.get('cast') or {}
        out = []
        for k, sa in sorted(ac.shots.items()):
            for aid, tr in sa.tracks.items():
                for (r0, rc, r1, side, tgt) in tr.reaches:
                    for t in (rc, min(rc + .08, r1)):               # poids plein : la prise est fermee
                        if tgt[0] == 'world': P = tuple(float(v) for v in tgt[1]); what = 'objet'
                        elif tgt[0] == 'door': P = tuple(float(v) for v in sa.door_handle(tgt[1], t)); what = 'porte'
                        else: continue
                        sm = sa.sample(float(t))
                        arms = acted.arm_points(sm, aid, looks)
                        if not arms: continue
                        hand = arms[1 if side > 0 else 0][3]         # arm_points: (gauche, droite), (ep, coude, mi, main)
                        d = math.dist(hand, P)
                        sk = bodies.solve(sm[aid]['rig'])
                        tag = 'R' if side > 0 else 'L'
                        os_ = (float(((sk.joints['sh' + tag] - sk.joints['el' + tag]) ** 2).sum() ** .5),
                               float(((sk.joints['el' + tag] - sk.joints['ha' + tag]) ** 2).sum() ** .5))
                        # a portee de bras, ou pas : sinon `two_bone` borne la cible et la main s'arrete en
                        # chemin, pour une raison qui n'a rien a voir avec la refonte (voir le rapport)
                        sh = arms[1 if side > 0 else 0][0]
                        out.append(dict(plan=k, qui=aid, quoi=what, t=round(float(t), 3),
                                        cible=[round(v, 4) for v in P], main=[round(v, 4) for v in hand],
                                        ecart=round(d, 4), os=[round(v, 6) for v in os_],
                                        bras=round(math.dist(sh, P), 4), portee=round(rig.UPPER + rig.FORE, 4),
                                        atteignable=math.dist(sh, P) <= rig.UPPER + rig.FORE))
        return out
    finally:
        bodies.use(was)


def head_in_frame(scene, body, aspect='9:16', every=.6):
    """ou la tete se place dans SON cadre, lue sur l'image rendue : part de la hauteur du cadre, comptee depuis
    le haut, du centre de la boite de tete (crane + cheveux) projetee par la camera du plan. C'est la mesure de
    la COMPOSITION : la refonte change le corps, elle ne doit pas deplacer le visage dans le cadre. Une tete
    qui se place plus haut que dans le rendu d'origine, c'est une camera qui vise trop bas."""
    from cadrage_qc import build
    from hstudio.engines.pixel3d import r3d, rigfig
    from hstudio.engines.pixel3d.frame import build_frame
    keys = [('body', body)] if body else []
    ep, lines, eng = build(copy.deepcopy(scene), aspect, keys)
    end = lines[-1]['end']
    per = {}
    g = .35
    while g < end:
        rigfig.PARTS = parts = {}
        try: sc, cam, L, shot, T, u, kk, state = build_frame(eng.ctx, g)
        finally: rigfig.PARTS = None
        pos, yaw, pitch, roll, fov = cam
        head = parts.get('head') or []
        vs, us = [], []
        for b in head:
            for cx in (b.wlo[0], b.whi[0]):
                for cy in (b.wlo[1], b.whi[1]):
                    for cz in (b.wlo[2], b.whi[2]):
                        u_, v_, zc = r3d.project(pos, yaw, pitch, roll, fov, (float(cx), float(cy), float(cz)))
                        if zc > .1: us.append(u_); vs.append(v_)
        cv = (1 - (max(vs) + min(vs)) / 2) / 2 if vs else None
        if vs and 0. < cv < 1.:                 # une tete hors cadre ne dit rien sur la composition
            per.setdefault(round(g, 2), dict(t=round(g, 2), centre_v=round(cv, 4),
                                             haut=round((1 - max(vs)) / 2, 4),
                                             coupe_haut=bool(max(vs) > 1.0)))
        g += every
    return [per[k] for k in sorted(per)]


def u_g(sa, t):
    return min(1., t / max(1e-3, sa.dur))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scene', default='toutes', choices=['toutes', 'objet', 'porte', 'closeup'])
    ap.add_argument('--fichier', default='', help="mesurer un scenario ecrit a la main plutot que les scenes d'essai")
    ap.add_argument('--json', default='')
    ap.add_argument('--cadre', action='store_true', help='mesurer aussi la tete dans son cadre (rend des images)')
    a = ap.parse_args()
    rows = {}
    todo = ([(os.path.basename(a.fichier), json.load(open(a.fichier, encoding='utf-8')))] if a.fichier
            else scenes(a.scene))
    for nm, sc in todo:
        print(f'\n{nm}')
        print('  configuration    ce qui est attrape   prises   main <-> cible, cm      pire   a portee   os du bras (m)')
        for cfg, body in CONFIGS:
            g = grips(sc, body)
            if not g:
                print(f'  {cfg:15s}  (aucune prise)'); continue
            rows.setdefault(nm, {})[cfg] = dict(prises=g)
            for quoi in sorted({r['quoi'] for r in g}):            # une poignee et un objet pose ne se melangent pas
                q = [r for r in g if r['quoi'] == quoi]
                ds = [r['ecart'] for r in q]; os_ = q[0]['os']
                at = sum(1 for r in q if r['atteignable'])
                print(f'  {cfg:15s}  {quoi:18s} {len(q):6d}   moyenne {100 * sum(ds) / len(ds):7.2f}   {100 * max(ds):7.2f}'
                      f'   {at}/{len(q)}      {os_[0]:.4f} / {os_[1]:.4f}')
                rows[nm][cfg][quoi] = dict(moyenne_cm=round(100 * sum(ds) / len(ds), 2), pire_cm=round(100 * max(ds), 2),
                                           atteignables=f'{at}/{len(q)}')
        if a.cadre:
            print('  --- la tete dans son cadre (9:16 rendu) : centre de la tete, part de la hauteur depuis le haut ---')
            ref = None
            for cfg, body in CONFIGS:
                hf = head_in_frame(sc, body)
                if ref is None: ref = {r['t']: r for r in hf}
                dd = [abs(r['centre_v'] - ref[r['t']]['centre_v']) for r in hf if r['t'] in ref]
                print(f'  {cfg:15s} ' + ' '.join(f"{r['t']}s:{r['centre_v']:.3f}" for r in hf)
                      + (f'   | ecart au defaut : moyen {sum(dd) / len(dd):.3f}, pire {max(dd):.3f}' if dd else ''))
                rows.setdefault(nm, {}).setdefault(cfg, {})['cadre'] = hf
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        json.dump(rows, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('\n  ecrit', a.json)
    return 0


if __name__ == '__main__': sys.exit(main())
