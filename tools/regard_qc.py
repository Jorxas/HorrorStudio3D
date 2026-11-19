"""Mesure OU REGARDENT les yeux d'un personnage PIXEL 3D, en degres, sur les vraies scenes jouees.

    python tools/regard_qc.py                                    # les six demos qui ont des personnages
    python tools/regard_qc.py --scene examples/demos/demo3_groupe.json --eyeline
    python tools/regard_qc.py --json docs/p1_regard/regard.json

POURQUOI UN OUTIL DE PLUS. `tools/cine_check.py` mesure si le VISAGE est tourne vers la camera, et
`tools/motion_qc.py` si la tete tourne trop vite. Aucun des deux ne dit si le personnage regarde la personne a
qui il parle : c'est un angle entre la direction du regard et la direction de la cible, et personne ne le
mesurait. Ce que l'outil trouve, avant toute correction :

| mesure | ce que c'est |
|---|---|
| `col` | part des echantillons ou la regie BUTE sur la limite du cou (0,95 rad) ou traine derriere sa cible |
| `la tete manque` | l'angle que la tete n'a pas livre, en degres, moyenne sur TOUS les echantillons |
| `reste apres les yeux` | ce qui reste de cet angle une fois les pupilles posees -- une pupille qui part trop loin compte comme une erreur, pas comme un rattrapage |
| `bon cote` | part des echantillons a cou court ou la pupille penche vers la cible (ou reste au centre quand il manque moins d'un demi-texel) |
| `faux mvt` | part des echantillons ou la pupille est decalee alors que la tete vise deja juste |
| `saut` | pire saut d'une image a la suivante, en texels de pupille (un saut se voit en gros plan) |
| `>2tx` | part des paires consecutives ou la pupille saute de plus de DEUX texels, soit plus du tiers de sa course |
| `moy` | saut moyen, en texels, sur toutes les paires consecutives |

Les trois configurations, et la premiere est le rendu livre :

    livre        -> aucune cle : les neuf etiquettes de `assets.GAZE`, declenchees des que |lacet| > 0,45 rad
    signe_seul   -> {"eye_aim": "signe_seul"} : la meme amplitude grossiere, mais du bon cote
    aim          -> {"eye_aim": true} : l'angle qui manque, converti en texels, du bon cote
    aim+saccade  -> la meme, plus {"eye_smooth": "saccade"} : le residu rejoue comme une saccade humaine
    aim+humain   -> la meme, plus {"eye_smooth": "humain"} : les vraies constantes humaines (70 ms, 2,2 ms/deg)
    aim+doux     -> la meme, plus {"eye_smooth": "doux"} : reaction plus longue encore, poursuite plus lente

LE CRITERE DU LISSAGE EST ECRIT ICI AVANT LA MESURE, comme celui du lot precedent. Est retenu le preset
`eye_smooth` qui, sur les six scenes et au pas du rendu (1/30 s), (a) divise AU MOINS PAR DEUX la part des
paires qui sautent de plus de deux texels, et (b) ne degrade pas `reste apres les yeux` de plus de 1 degre
en moyenne contre `aim`. Un lissage qui calme la pupille en la faisant regarder a cote n'est pas un progres.

Le signe du rendu livre n'est pas une opinion : `timeline` etiquette `'right'` quand le lacet est positif, un
lacet positif tourne la tete vers +x local, la camera voit +x a sa gauche, et `GAZE['right']` deplace l'iris
vers -x local, donc a sa droite. Les deux signes sont opposes. L'outil le compte au lieu de l'affirmer.

Aucun reseau, aucune cle d'API, aucun ffmpeg, aucune image rendue : tout est geometrique. Deterministe.
"""
import os, sys, json, math, copy, argparse

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

SCENES = ('demo2_dialogue', 'demo3_groupe', 'demo4_tension', 'demo6_continuite', 'demo9_tempete', 'demo20_decors')
# (etiquette, valeur de "eye_aim", valeur de "eye_smooth") -- la premiere est le rendu livre
CONFIGS = (('livre', None, None), ('aim', True, None), ('aim+saccade', True, 'saccade'))      # signe_seul / humain / doux supprimes le 31/10
STEP = 1 / 15.          # s entre deux echantillons, par defaut : celui du rapport P1 du 25 octobre


def samples(scene, eyeline=False, smooth=None, step=STEP):
    """-> [(plan, qui, t, residu lacet, residu tangage, etiquette gaze historique)] sur toute la scene.
    `smooth` est la valeur de la cle "eye_smooth" (acting/eyeflow.py) : elle change le RESIDU lui-meme,
    dans la couche de jeu, donc elle demande un montage a part -- contrairement a "eye_aim", qui ne fait
    que convertir ce residu en texels et peut donc etre rejoue en aval sur les memes echantillons."""
    from cadrage_qc import build
    keys = ([('eyeline', 'smooth')] if eyeline else []) + ([('eye_smooth', smooth)] if smooth else [])
    ep, lines, eng = build(copy.deepcopy(scene), '9:16', keys)
    ac = eng.ctx.get_acting()
    out = []
    for k, sa in sorted(ac.shots.items()):
        t = 0.
        while t < sa.dur:
            for aid, s in sa.sample(float(t)).items():
                e = s.get('eye') or (0., 0.)
                out.append((k, aid, round(float(t), 3), float(e[0]), float(e[1]), s.get('gaze')))
            t += step
    return out


def texels(cfg, res_yaw, res_pitch, gaze, size=48):
    """les texels de pupille que CHAQUE configuration applique, pour un echantillon donne"""
    from hstudio.engines.pixel3d import eyes as EY, assets as A
    if cfg is None:                      # le rendu livre : les neuf etiquettes, telles quelles
        gx, gy = A.GAZE.get(gaze, (0, 0))
        return (gx * 2, gy * 2) if size >= 48 else (gx, gy)
    was = EY.active()
    EY.use(EY.configure(cfg))
    try: return EY.offset({'eye': (res_yaw, res_pitch)}, size) or (0, 0)
    finally: EY.use(was)


def ref_of(rows):
    """{(plan, qui, t): residu VRAI} d'un montage sans lissage -- la reference contre laquelle un lissage est
    juge. Sans elle, un preset de lissage serait note contre le residu qu'il a lui-meme adouci, et tout
    lissage paraitrait gratuit : il faut comparer la pupille dessinee a l'angle que la tete manque VRAIMENT."""
    return {(k, aid, t): (ry, rp) for (k, aid, t, ry, rp, gz) in rows}


def measure(rows, cfg, st_yaw=.45, travel=3., ref=None):
    """-> le tableau de mesures d'une configuration, en degres et en texels.

    La mesure qui decide est `apres` : l'ecart qui RESTE entre la direction visee et la direction que la tete
    plus les pupilles expriment reellement. Elle compte une pupille qui part trop loin comme une erreur, pas
    comme un rattrapage -- sans quoi une configuration qui met les yeux a fond des que le cou est court
    gagnerait en exagerant, et c'est exactement ce que fait le preset `signe_seul`.

    `ref` : le residu VRAI, du montage sans lissage. Les texels sont lus sur `rows` (donc sur le residu
    lisse quand il y en a un), mais l'erreur est comptee contre `ref` -- le retard qu'un lissage introduit
    est donc compte CONTRE lui, et c'est la seule facon de juger un lissage honnetement."""
    tete, apres, bon, mal, faux, n_col, saut, pire = [], [], 0, 0, 0, 0, 0., 0.
    seuil = st_yaw / (2 * travel)        # un demi-texel de course : en dessous, zero EST la bonne reponse
    prev = {}; deltas = []
    for (k, aid, t, ry, rp, gz) in rows:
        gx, gy = texels(cfg, ry, rp, gz)
        if ref is not None: ry, rp = ref.get((k, aid, t), (ry, rp))     # juge contre le residu VRAI
        # l'angle que les pupilles expriment, signe : la course complete vaut `yaw` radians
        porte = (-gx / travel) * st_yaw
        err = abs(ry - porte)
        tete.append(math.degrees(abs(ry))); apres.append(math.degrees(err)); pire = max(pire, math.degrees(err))
        if abs(ry) > 1e-4:
            n_col += 1
            if gx == 0:
                if abs(ry) < seuil: bon += 1
                else: mal += 1
            elif (gx < 0) == (ry > 0): bon += 1
            else: mal += 1
        elif gx or gy:
            faux += 1
        key = (k, aid)
        if key in prev:
            d = abs(gx - prev[key]); saut = max(saut, d); deltas.append(d)
        prev[key] = gx
    n = len(rows)
    f = lambda v: round(sum(v) / len(v), 1) if v else 0.
    nd = max(1, len(deltas))
    return dict(n=n, col=round(100 * n_col / max(1, n), 1), tete=f(tete), apres=f(apres), pire=round(pire, 1),
                bon=round(100 * bon / max(1, n_col), 1), mauvais=round(100 * mal / max(1, n_col), 1),
                faux=round(100 * faux / max(1, n), 1), saut=int(saut),
                # la mesure que ce lot-ci corrige : combien de paires consecutives font sauter la pupille de
                # plus de DEUX texels, c'est-a-dire plus du tiers de sa course, d'une image a la suivante
                saut_gt2=round(100 * len([d for d in deltas if d > 2]) / nd, 2),
                saut_gt1=round(100 * len([d for d in deltas if d > 1]) / nd, 2),
                saut_moy=round(sum(deltas) / nd, 3), paires=len(deltas))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scene', default='')
    ap.add_argument('--eyeline', action='store_true', help='activer la regie du regard (le lacet traine aussi)')
    ap.add_argument('--step', type=float, default=STEP, help="s entre deux echantillons (1/30 = le pas du rendu)")
    ap.add_argument('--only', default='', help='ne mesurer que ces configurations, separees par des virgules')
    ap.add_argument('--json', default='')
    a = ap.parse_args()
    names = [a.scene] if a.scene else [os.path.join(ROOT, 'examples', 'demos', n + '.json') for n in SCENES]
    cfgs = [c for c in CONFIGS if not a.only or c[0] in a.only.split(',')]
    out = {}; moy = {}
    print(f'pas = {a.step:.4f} s ({1 / a.step:.0f} Hz), regie du regard = ' + ('oui' if a.eyeline else 'non'))
    print('scene                  configuration   echant.  cou court  la tete manque  reste apres les yeux  (pire)'
          '   bon cote  faux mvt  saut  >2tx  moy')
    for path in names:
        sc = json.load(open(path, encoding='utf-8'))
        if sc.get('style', (sc.get('episode') or {}).get('style', 'pixel3d')) != 'pixel3d': continue
        nm = os.path.basename(path).replace('.json', '')
        rows_by = {None: samples(sc, a.eyeline, None, a.step)}
        ref = ref_of(rows_by[None])
        for cfg_name, cfg, sm in cfgs:
            if sm not in rows_by: rows_by[sm] = samples(sc, a.eyeline, sm, a.step)
            m = measure(rows_by[sm], cfg, ref=ref)
            out.setdefault(nm, {})[cfg_name] = m
            moy.setdefault(cfg_name, []).append(m)
            print(f'{nm:22s} {cfg_name:14s} {m["n"]:7d}  {m["col"]:8.1f}%  {m["tete"]:11.1f} deg  {m["apres"]:14.1f} deg'
                  f'  ({m["pire"]:5.1f})   {m["bon"]:6.1f}%   {m["faux"]:6.1f}%   {m["saut"]:3d}'
                  f'  {m["saut_gt2"]:5.2f}%  {m["saut_moy"]:.3f}')
    if len(moy) and len(names) > 1:
        print('-' * 118)
        for cfg_name, ms in moy.items():
            g = lambda k: sum(x[k] for x in ms) / len(ms)
            print(f'{"MOYENNE des " + str(len(ms)):22s} {cfg_name:14s} {"":7s}  {"":9s}  {g("tete"):11.1f} deg'
                  f'  {g("apres"):14.1f} deg  ({max(x["pire"] for x in ms):5.1f})   {g("bon"):6.1f}%'
                  f'   {g("faux"):6.1f}%   {max(x["saut"] for x in ms):3.0f}  {g("saut_gt2"):5.2f}%  {g("saut_moy"):.3f}')
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        json.dump(dict(eyeline=a.eyeline, step=a.step, rows=out), open(a.json, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('  ecrit', a.json)
    return 0


if __name__ == '__main__': sys.exit(main())
