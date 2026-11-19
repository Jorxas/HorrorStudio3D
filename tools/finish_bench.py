"""Combien coute une image PIXEL 3D plus nette, et ce qu'elle rapporte -- mesure, pas opinion.

    python tools/finish_bench.py
    python tools/finish_bench.py --scene examples/scenes/couloir_poignee.json --json docs/.../bench.json
    python tools/finish_bench.py --sheet docs/.../finesse.png          # les memes images cote a cote

POURQUOI UN OUTIL DE PLUS. `tools/corps_bench.py` mesure le cout d'une refonte de CORPS, `tools/cadrage_qc.py`
la place du sujet dans le cadre : aucun des deux ne regarde la NETTETE de l'image, qui est le reproche
principal des images de reference du proprietaire (geometrie cubique, image lisse). Ce qui est mesure ici :

| mesure | ce que c'est | pourquoi elle ne peut pas etre flattee |
|---|---|---|
| `s/img` | secondes par image, mediane de `--repeat` rendus du MEME instant | c'est le prix, et il grandit comme le carre du facteur |
| `rayons` | largeur x hauteur du raster natif | le nombre d'echantillons reellement calcules, pas la taille du fichier |
| `ecart_ref` | ecart quadratique moyen (0-255) contre une image de REFERENCE, rendue a x4 sans palette | c'est la mesure standard du crenelage : on ne juge pas une image a l'oeil, on la compare a la mieux echantillonnee de la serie |
| `ecart_flou` | le meme ecart apres un flou 3x3 sur les deux images | le grain de pellicule est tire PAR PIXEL, donc sa trame change avec le raster et laisse un plancher d'ecart qui ne descend jamais a zero ; le flou l'enleve et ne laisse que la structure. C'est celle des deux qui dit si la serie converge |
| `plats` | part des paires de pixels voisins RIGOUREUSEMENT egales, horizontalement | un agrandissement x5 au plus proche voisin en fabrique 4 sur 5 par construction ; une image resolue beaucoup moins |
| `teintes` | nombre de couleurs distinctes dans l'image finale | une palette quantifiee en a peu ; attention, un tramage en fabrique aussi beaucoup, donc ce chiffre se lit AVEC `plats` |
| `profondeur` | ecart-type de la luminance sur la moitie haute moins celle du quart central | un decor a plusieurs plans a du contraste loin du sujet ; un fond plat n'en a pas |

Toutes sont lues sur l'image FINALE 1080x1920, celle qui part dans le MP4 : c'est la seule qui compte, et
c'est celle ou le raster natif x5 au plus proche voisin se voit.

LA REFERENCE EST L'UNE DES CONFIGURATIONS, ET IL FAUT LE DIRE : `net_max` (x4, sans palette) sert d'image
de comparaison, donc ses deux ecarts valent 0 par construction et ne prouvent rien sur elle-meme. Ce qu'ils
prouvent, c'est de combien les AUTRES s'en ecartent, et a quel prix chacune s'en rapproche.

ET IL FAUT DIRE AUSSI QU'ELLE N'EST PAS UNE VERITE : rien ici ne demontre que x4 est converge. La serie peut
etre lue dans les deux sens -- si `ecart_flou` s'ecrase quand le facteur monte, les rayons suivants ne
rapportent plus grand-chose ; s'il ne s'ecrase pas, c'est que le raster n'est pas la seule limite.

Aucun reseau, aucune cle d'API, aucun ffmpeg, aucun projet ecrit. Deterministe.
"""
import os, sys, json, time, copy, argparse, statistics

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

import numpy as np

SCENE = os.path.join(ROOT, 'examples', 'scenes', 'couloir_poignee.json')
# (etiquette, valeur de la cle "finish") -- la premiere est le rendu livre
CONFIGS = [('livre', None),
           ('lisse_seul', 'lisse_seul'),
           ('net_rapide', 'net_rapide'),
           ('net', 'net'),
           ('net_palette', 'net_palette'),
           ('net_max', 'net_max')]


def flat_pairs(a):
    """part des paires de pixels horizontalement voisins RIGOUREUSEMENT egales.

    Un agrandissement x5 au plus proche voisin en fabrique 4 sur 5 (80 %) rien que par construction, quelle
    que soit la scene : c'est la signature arithmetique du defaut, pas une impression. Une image reellement
    resolue a 1080 de large n'a d'egalites que la ou le decor est vraiment uni."""
    q = a.reshape(a.shape[0], a.shape[1], 3)
    eq = np.all(q[:, 1:] == q[:, :-1], axis=-1)
    return float(eq.mean())


def rms(a, ref):
    """ecart quadratique moyen (0-255) entre deux images finales de meme taille"""
    if ref is None or a.shape != ref.shape: return None
    d = a.astype(np.float32) - ref.astype(np.float32)
    return float(np.sqrt((d * d).mean()))


def _blur3(a):
    """flou 3x3 separable, pour retirer le grain tire par pixel sans toucher a la structure"""
    f = a.astype(np.float32)
    f = (f[:, :-2] + f[:, 1:-1] + f[:, 2:]) / 3.
    f = (f[:-2] + f[1:-1] + f[2:]) / 3.
    return f


def rms_blur(a, ref):
    """le meme ecart, grain retire : c'est lui qui dit si la serie converge"""
    if ref is None or a.shape != ref.shape: return None
    d = _blur3(a) - _blur3(ref)
    return float(np.sqrt((d * d).mean()))


def depth(a):
    """contraste loin du sujet moins contraste au centre : un decor a plusieurs plans en a, un fond plat non"""
    g = a.astype(np.float32).mean(-1)
    h, w = g.shape
    far = g[:h // 2]
    mid = g[h // 3: 2 * h // 3, w // 3: 2 * w // 3]
    return float(far.std() - mid.std())


def tones(a):
    """nombre de couleurs distinctes dans l'image finale"""
    q = a.reshape(-1, 3).astype(np.uint32)
    return int(np.unique(q[:, 0] * 65536 + q[:, 1] * 256 + q[:, 2]).size)


def one(scene, fin, at, repeat, extra):
    from cadrage_qc import build
    from hstudio.engines.pixel3d import finish as FIN, r3d
    keys = list(extra) + ([('finish', fin)] if fin else [])
    ep, lines, eng = build(copy.deepcopy(scene), '9:16', keys)
    eng.frame(at)                                       # une fois pour remplir les caches, jamais chronometree
    ts = []
    for _ in range(repeat):
        t0 = time.perf_counter(); im = eng.frame(at); ts.append(time.perf_counter() - t0)
    a = np.asarray(im.convert('RGB'))
    st = FIN.active()
    return dict(raster=[int(r3d.RW), int(r3d.RH)], rayons=int(r3d.RW * r3d.RH),
                rayons_x=round(r3d.RW * r3d.RH / (216 * 384), 2),
                secondes=round(statistics.median(ts), 3), min_s=round(min(ts), 3), max_s=round(max(ts), 3),
                plats=round(flat_pairs(a), 4), teintes=tones(a),
                profondeur=round(depth(a), 2), image=im, pixels=a,
                preset=(st or {}).get('name'), scale=(st or {}).get('scale', 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scene', default=SCENE)
    ap.add_argument('--at', type=float, default=8.0, help='instant (s) rendu par toutes les configurations')
    ap.add_argument('--repeat', type=int, default=3)
    ap.add_argument('--only', default='')
    ap.add_argument('--body', default='', help='preset de corps applique partout (ex. minecraft)')
    ap.add_argument('--env', default='', help='preset de facades applique partout (ex. riche)')
    ap.add_argument('--json', default='')
    ap.add_argument('--sheet', default='')
    a = ap.parse_args()
    scene = json.load(open(a.scene, encoding='utf-8'))
    cfgs = [c for c in CONFIGS if not a.only or c[0] in a.only.split(',')]
    extra = ([('body', a.body)] if a.body else []) + ([('env', a.env)] if a.env else [])
    print(f'scene {os.path.basename(a.scene)}, instant {a.at:.2f} s, {a.repeat} rendus par configuration'
          + (f', corps "{a.body}"' if a.body else '') + (f', decors "{a.env}"' if a.env else ''))
    rows = {}; ims = []; pix = {}
    for name, fin in cfgs:
        r = one(scene, fin, a.at, a.repeat, extra)
        ims.append((name, r.pop('image'))); pix[name] = r.pop('pixels')
        rows[name] = r
    ref = pix.get('net_max')                       # l'image convergee : la mieux echantillonnee qu'on sache faire
    print('configuration   raster      rayons   xlivre   s/img   (min-max)    ecart_ref ecart_flou  plats   teintes  profondeur')
    for name, _ in ims:
        r = rows[name]
        r['ecart_ref'] = None if ref is None else round(rms(pix[name], ref), 2)
        r['ecart_flou'] = None if ref is None else round(rms_blur(pix[name], ref), 2)
        e = '    --' if r['ecart_ref'] is None else f'{r["ecart_ref"]:6.2f}'
        eb = '    --' if r['ecart_flou'] is None else f'{r["ecart_flou"]:6.2f}'
        print(f'{name:14s} {r["raster"][0]:4d}x{r["raster"][1]:<5d} {r["rayons"]:8d} {r["rayons_x"]:6.2f}x '
              f'{r["secondes"]:7.3f} ({r["min_s"]:.3f}-{r["max_s"]:.3f})  {e}     {eb}  {100 * r["plats"]:5.1f}% '
              f'{r["teintes"]:8d} {r["profondeur"]:10.2f}')
    if a.sheet:
        from PIL import Image, ImageDraw
        band = 26; cols = len(ims); w = 420
        h = int(w * ims[0][1].height / ims[0][1].width)
        out = Image.new('RGB', (w * cols, h + band), (16, 16, 18))
        d = ImageDraw.Draw(out)
        for i, (nm, im) in enumerate(ims):
            out.paste(im.resize((w, h), Image.LANCZOS), (i * w, band))
            r = rows[nm]
            d.text((i * w + 6, 6), f'{nm}  {r["raster"][0]}x{r["raster"][1]}  {r["secondes"]:.2f}s/img', fill=(255, 220, 120))
        os.makedirs(os.path.dirname(os.path.abspath(a.sheet)), exist_ok=True)
        out.save(a.sheet); print('planche :', a.sheet, out.size)
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        json.dump(dict(scene=a.scene, at=a.at, repeat=a.repeat, body=a.body, rows=rows),
                  open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('mesures :', a.json)
    return 0


if __name__ == '__main__': sys.exit(main())
