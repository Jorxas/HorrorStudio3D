"""Mesure, sur de VRAIES images, ce que le bandeau de sous-titres couvre : bouche, yeux, tete, cadre.

    python tools/soustitre_qc.py examples/scenes/portrait_peur.json
    python tools/soustitre_qc.py examples/scenes/portrait_peur.json --ab --json docs/sous_titres/qc.json
    python tools/soustitre_qc.py examples/demos/demo2_dialogue.json --aspect 16:9 --set body=voxel_premium

POURQUOI UN OUTIL DE PLUS, alors que `tools/cadrage_qc.py` existe deja. `cadrage_qc` mesure la part de
l'image prise par un BRAS, une TETE, un CORPS : il repond a « l'avant-bras remplit-il le gros plan ». Il
ne voit pas le defaut signale ici, parce que ce defaut n'est pas une part d'image : c'est un
RECOUVREMENT entre deux rectangles, le bandeau de texte et la bouche. Les deux outils lisent la meme
mesure de base (le crochet `rigfig.PARTS` et le tampon d'indices du lanceur de rayons) ; ils en tirent
deux chiffres differents. Rien n'est duplique : la mesure des visages vient de
`hstudio/captions/probe3d.py`, que le moteur utilise lui aussi.

CE QUE LA SORTIE VEUT DIRE, colonne par colonne :

| colonne | ce que c'est |
|---|---|
| `bouche%` | part du RECTANGLE DE TEXTE qui tombe sur la bande de la bouche. **C'est la colonne du defaut.** 0 = la bouche est libre. |
| `yeux%` | idem pour la bande des yeux |
| `tete%` | part du rectangle de texte qui tombe sur la boite de tete (crane + cheveux), toutes tetes confondues |
| `hors%` | part du rectangle de texte qui sort de la zone sure 9:16 (`captions/geometry.SAFE`) |
| `y` | hauteur du haut du texte, en pixels |
| `bande` | la bande choisie (`mid`, `low`, `top`, `sous_menton`, `sur_front`, `bas_zone_sure`) |

`--ab` mesure DEUX FOIS la meme scene aux memes instants, une fois sans la cle `caption_safe` et une fois
avec, et imprime la difference. C'est la comparaison qui repond a la question du proprietaire.

CE QUE CET OUTIL NE MESURE PAS. Il ne dit rien du haut du crane coupe ni des cheveux lateraux qui
masquent le visage : ce sont des defauts de CADRAGE, ils appartiennent au lot camera. La boite de tete
mesuree ici etant celle des pixels VISIBLES, une tete coupee par le bord du cadre se lit dans la colonne
`tete%` comme une tete plus petite -- ce qui est honnete mais n'est pas une correction.

Aucun reseau, aucune cle, aucun ffmpeg : le lanceur de rayons est appele directement en basse resolution
(216x384 en 9:16). Deterministe.
"""
import os, sys, json, copy, argparse

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

from cadrage_qc import build                                               # noqa: E402
from hstudio.captions import geometry as G                                 # noqa: E402
from hstudio.captions import safe as CAPS                                  # noqa: E402
from hstudio.captions.probe3d import faces_at                              # noqa: E402


def sub_times(eng, per_shot=2):
    """les instants mesures : quelques repliques par plan, au milieu de la replique.

    On mesure la ou un sous-titre est AFFICHE -- mesurer une image sans sous-titre ne dit rien du
    recouvrement. Deterministe : les memes instants avant et apres, pour pouvoir soustraire."""
    out = []
    for k, (t0, t1) in enumerate(eng.ctx.tl.spans):
        cues = [s for s in eng.subs if s['b'] > t0 and s['a'] < t1]
        if not cues:
            continue
        pick = cues if len(cues) <= per_shot else [cues[int(round(i * (len(cues) - 1) / (per_shot - 1)))]
                                                   for i in range(per_shot)] if per_shot > 1 else [cues[0]]
        for s in pick:
            g = (max(s['a'], t0) + min(s['b'], t1)) / 2.
            out.append((round(g, 3), k, s))
    # un instant ne figure qu'une fois, meme si deux repliques se touchent
    seen = set(); uniq = []
    for g, k, s in out:
        if g in seen:
            continue
        seen.add(g); uniq.append((g, k, s))
    return uniq


def text_box(eng, g, s, draw):
    """le rectangle de texte REELLEMENT dessine a l'instant g, tel que le moteur le dessine.

    On ne reimplemente pas la mise en page : on appelle la meme police, la meme mesure de largeur et, si
    la cle est posee, le meme `place3d` que `engines/pixel3d/render.compose`."""
    from hstudio.engines.pixel3d.render import F
    L = eng.L
    shot = eng.ep['shots'][eng.ctx.tl.at(g)[0]]
    ui = shot.get('ui') or {}
    pos = ui.get('subs', 'mid')
    if pos == 'off':
        return None, None, None
    fnt = F(56)
    text = ' '.join(w for w, _ in s['words'])
    tw = draw.textlength(text, font=fnt)
    y = L.sub_y['choice'] if ui.get('choice') else L.sub_y.get(pos, L.sub_y['mid'])
    band = 'choice' if ui.get('choice') else pos
    if getattr(eng, 'caps', None) is not None and not ui.get('choice'):
        y, fnt, tw = CAPS.place3d(eng.caps, eng, g, pos, s, draw, F, y)
        p = (eng.caps.get('_plan') or {}).get(eng.ctx.tl.at(g)[0]) or {}
        band = p.get('band', pos)
    h = fnt.size * 1.15
    lab = 52. if (eng.lines[s['line']].get('label')) else 0.
    rect = (max(0., (L.W - tw) / 2) / L.W, min(L.W, (L.W + tw) / 2) / L.W, (y - lab) / L.H, (y + h) / L.H)
    return rect, y, band


def outside_safe(rect, aspect):
    """part du rectangle de texte qui sort de la zone sure"""
    safe = G.SAFE.get(aspect, G.SAFE['9:16'])
    inside = (safe['side'], 1. - safe['side'], safe['top'], safe['bottom'])
    a = G.area(rect)
    return 0. if a <= 0 else max(0., 1. - G.inter(rect, inside) / a)


def measure(eng, aspect, per_shot=2, cache=None):
    rows = []
    from PIL import Image, ImageDraw
    draw = ImageDraw.Draw(Image.new('RGB', (8, 8)))
    for g, k, s in sub_times(eng, per_shot):
        rect, y, band = text_box(eng, g, s, draw)
        if rect is None:
            continue
        zones = cache.get(g) if cache is not None else None
        if zones is None:
            zones, _info = faces_at(eng.ctx, g, aspect)
            if cache is not None:
                cache[g] = zones
        mouth = sum(G.covered(rect, z.get('mouth')) for z in zones)
        eyes = sum(G.covered(rect, z.get('eyes')) for z in zones)
        head = sum(G.covered(rect, z['rect']) for z in zones)
        kind = ((eng.ep['shots'][k].get('camera') or {}).get('shot') or 'auto')
        rows.append(dict(t=g, shot=k, kind=kind, band=band, y=round(float(y), 1),
                         texte=' '.join(w for w, _ in s['words']),
                         bouche=round(min(1., mouth), 4), yeux=round(min(1., eyes), 4),
                         tete=round(min(1., head), 4), hors=round(outside_safe(rect, aspect), 4),
                         rect=[round(v, 4) for v in rect], heads=len(zones)))
    return rows


def table(rows, title):
    print(f'  {title}')
    print('   t(s)  plan  type           bande           y     bouche%  yeux%   tete%   hors%  texte')
    for r in rows:
        print(f"  {r['t']:6.2f}  {r['shot']:4d}  {r['kind']:13s} {r['band']:14s} {r['y']:6.0f}"
              f"  {100*r['bouche']:7.1f} {100*r['yeux']:6.1f} {100*r['tete']:7.1f} {100*r['hors']:6.1f}"
              f"  {r['texte'][:28]}")
    n = max(1, len(rows))
    agg = dict(bouche=sum(r['bouche'] for r in rows) / n, yeux=sum(r['yeux'] for r in rows) / n,
               tete=sum(r['tete'] for r in rows) / n, hors=sum(r['hors'] for r in rows) / n,
               bouche_max=max([r['bouche'] for r in rows] or [0.]),
               tete_max=max([r['tete'] for r in rows] or [0.]),
               n_bouche=len([r for r in rows if r['bouche'] > .001]),
               n_tete=len([r for r in rows if r['tete'] > .001]), n=len(rows))
    print(f"   MOYENNE sur {agg['n']} images : bouche {100*agg['bouche']:.2f} % (pire {100*agg['bouche_max']:.1f} %,"
          f" {agg['n_bouche']} images touchees) | tete {100*agg['tete']:.2f} % (pire {100*agg['tete_max']:.1f} %,"
          f" {agg['n_tete']} images) | yeux {100*agg['yeux']:.2f} % | hors zone sure {100*agg['hors']:.2f} %")
    return agg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('scene')
    ap.add_argument('--aspect', default='9:16')
    ap.add_argument('--per-shot', type=int, default=2, help='repliques mesurees par plan')
    ap.add_argument('--ab', action='store_true', help='mesure sans PUIS avec la cle caption_safe')
    ap.add_argument('--safe', default='auto', help='valeur de caption_safe pour le cote "apres"')
    ap.add_argument('--set', action='append', default=[], help="cle d'episode a poser (cle ou cle=valeur)")
    ap.add_argument('--json', default='')
    a = ap.parse_args()

    eks = []
    for it in a.set:
        k, _, v = it.partition('=')
        eks.append((k, True if v == '' else (json.loads(v) if v[0] in '[{"0123456789tfn' else v)))

    print(f"{os.path.basename(a.scene)}  {a.aspect}  cles posees : {eks or 'aucune'}")
    cache = {}
    out = {'scene': a.scene, 'aspect': a.aspect, 'keys': eks}

    _ep, lines, eng = build(a.scene, a.aspect, eks)
    before = measure(eng, a.aspect, a.per_shot, cache)
    out['avant'] = {'rows': before, 'agg': table(before, 'AVANT  (sans "caption_safe" : le bandeau livre)')}

    if a.ab:
        print()
        safe_val = a.safe if a.safe not in ('1', 'true', 'True') else True
        _ep2, _l2, eng2 = build(a.scene, a.aspect, eks + [('caption_safe', safe_val)])
        if eng2.caps is None:
            print(f'  ARRET : "caption_safe": {safe_val!r} refuse par configure() -- rien a comparer')
            sys.exit(2)
        after = measure(eng2, a.aspect, a.per_shot, cache)
        out['apres'] = {'rows': after, 'agg': table(after, f'APRES  ("caption_safe": {safe_val!r})'),
                        'caption_safe': safe_val}
        out['plan'] = {str(k): {kk: vv for kk, vv in p.items() if kk not in ('zones', 'tried', 'info')}
                       for k, p in (eng2.caps.get('_plan') or {}).items()}
        b, c = out['avant']['agg'], out['apres']['agg']
        print('\n  DIFFERENCE (apres - avant), sur les MEMES instants :')
        for key, lab in (('bouche', 'bouche couverte'), ('yeux', 'yeux couverts'),
                         ('tete', 'tete couverte'), ('hors', 'hors zone sure')):
            print(f"    {lab:18s} {100*b[key]:6.2f} %  ->  {100*c[key]:6.2f} %   "
                  f"({100*(c[key]-b[key]):+.2f} pt)")
        print(f"    images ou le texte touche la bouche : {b['n_bouche']}/{b['n']}  ->  {c['n_bouche']}/{c['n']}")
        print(f"    images ou le texte touche une tete  : {b['n_tete']}/{b['n']}  ->  {c['n_tete']}/{c['n']}")
        out['verdict'] = dict(bouche_avant=b['bouche'], bouche_apres=c['bouche'],
                              images_bouche_avant=b['n_bouche'], images_bouche_apres=c['n_bouche'],
                              images_tete_avant=b['n_tete'], images_tete_apres=c['n_tete'],
                              hors_apres=c['hors'])

    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        json.dump(out, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('\n  ecrit', os.path.abspath(a.json))


if __name__ == '__main__':
    main()
