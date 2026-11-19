"""Tests hors ligne de l'épaule douce de l'étalonnage PS1 (clé d'épisode `grade.epaule`, 15/11/2026) et de la hauteur des halos.

    python tools/check_epaule.py

Pourquoi : la version « caméra nette, très très claire » de LE PHARE QUI EFFACE (exposition 1,85) a été livrée avec des visages presque
blancs et des cheveux bruns devenus blond-orange : le chemin d'étalonnage livré écrête R, G et B SÉPARÉMENT. `grade.epaule` remplace cet
écrêtage par une épaule douce sur le canal le plus fort, appliquée aux trois canaux avec le même rapport (teinte gardée) ; seules les vraies
sources (valeur de scène > 1 avant l'exposition) blanchissent encore. Et un halo d'objet était plafonné à 20 m de haut (lanterne du phare
à 21,5 m : le halo tombait 1,5 m sous la paume et n'éclairait rien) : borne relevée à 80 m.

Ce que ça vérifie :
1. **inerte sans la clé** : image identique AU BIT PRÈS sans `epaule`, avec `epaule: 0`, `False`, `None` ou une valeur illisible ;
2. **la lecture de la clé** : True -> genou 0,72 ; nombre borné à [0,4 ; 0,95] ;
3. **la courbe** : identité sous le genou, monotone, jamais au-dessus de 1, pente continue au genou ;
4. **la teinte est gardée** : une peau et des cheveux bruns exposés à 1,85 gardent leurs rapports R:G:B (l'écrêtage les blanchit) ;
5. **seules les sources blanchissent** : une lampe chaude (valeur de scène > 1) va vers le blanc, une surface éclairée non ;
6. **sur une vraie image** : à l'exposition 1,85, moins de pixels brûlés qu'avec l'écrêtage, sans assombrir les ombres ;
7. **halo haut** : un halo à 21,5 m n'est plus ramené à 20 m (aucun avertissement), un halo à 200 m l'est toujours (borne 80 m).

Aucun réseau, aucune clé d'API, aucun ffmpeg, aucun projet écrit. Windows : corps derrière `if __name__ == '__main__'`.
"""
import os, sys, json, copy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

OK = [0]; BAD = [0]
SCENE = os.path.join(ROOT, 'examples', 'scenes', 'couloir_poignee.json')


def check(label, cond, detail=''):
    ok = bool(cond)
    (OK if ok else BAD)[0] += 1
    print(('  OK   ' if ok else '  ECHEC ') + label + (f'   [{detail}]' if detail else ''))
    return ok


def img(keys, t=8.0, scene=SCENE):
    from cadrage_qc import build
    _, _, eng = build(scene, '9:16', list(keys))
    return np.asarray(eng.frame(t).convert('RGB'))


def lum(a): return (a.astype(np.float32) * np.array([.299, .587, .114], np.float32)).sum(-1)


def main():
    from hstudio.engines.pixel3d.render import epaule, epaule_genou
    sc = json.load(open(SCENE, encoding='utf-8'))
    g0 = dict((sc.get('episode') or sc).get('grade') or {'saturation': .85, 'exposure': 1.1})

    print('1. inerte sans la clé')
    ref = img([('grade', g0)])
    for v in (0, False, None, 'beaucoup', [1]):
        check(f'grade.epaule = {v!r} : image identique au bit près', np.array_equal(ref, img([('grade', dict(g0, epaule=v))])))

    print('2. lecture de la clé')
    check('True -> genou 0,72', epaule_genou(True) == .72)
    check('0,6 -> 0,6', epaule_genou(.6) == .6)
    check('bornes [0,4 ; 0,95]', epaule_genou(.1) == .4 and epaule_genou(3) == .95)
    check('0 / False / None / texte -> éteint', not any(epaule_genou(v) for v in (0, False, None, 'x', [1])))

    print('3. la courbe')
    x = np.linspace(0, 6, 4001, dtype=np.float32)
    g = np.repeat(x[:, None], 3, 1)[None]
    y = epaule(g, .72, 1e6)[0, :, 0]                       # expo énorme : aucun blanchiment de source, la courbe seule
    below = x <= .72
    check('identité sous le genou', np.allclose(y[below], x[below], atol=1e-6))
    check('monotone (à 2 ulp float32 près, 1e-5 fois un niveau de gris)', bool(np.all(np.diff(y) >= -2.5e-7)))
    check('jamais au-dessus de 1', float(y.max()) <= 1.0 + 1e-6, f'max {y.max():.5f}')
    i = int(np.searchsorted(x, .72)); sl = (y[i + 2] - y[i + 1]) / (x[i + 2] - x[i + 1])
    check('pente continue au genou (≈ 1)', abs(sl - 1) < .02, f'pente {sl:.3f}')

    print('4. la teinte est gardée')
    expo = 1.85
    for name, c in (('peau', (.8, .6, .5)), ('cheveux bruns éclairés', (.65, .4, .25))):
        v = np.array(c, np.float32)[None, None] * expo
        o = epaule(v.copy(), .72, expo)[0, 0]; cl = np.clip(v, 0, 1)[0, 0]
        r_in = v[0, 0] / v[0, 0].max(); r_out = o / o.max(); r_cl = cl / cl.max()
        check(f'{name} : rapports R:G:B gardés', np.allclose(r_in, r_out, atol=.01), f'entrée {np.round(r_in, 2)} sortie {np.round(r_out, 2)}')
        check(f'{name} : l\'écrêtage, lui, les change (le défaut corrigé)', not np.allclose(r_in, r_cl, atol=.05),
              f'écrêté {np.round(r_cl, 2)}')
    skin = epaule(np.array([[[.8, .6, .5]]], np.float32) * expo, .72, expo)[0, 0]
    check('peau exposée à 1,85 : reste une peau (B < 0,7 R)', skin[2] < .7 * skin[0], f'{np.round(skin, 3)}')

    print('5. seules les sources blanchissent')
    lamp = epaule(np.array([[[3., 2., 1.]]], np.float32) * 1.2, .72, 1.2)[0, 0]
    lit = epaule(np.array([[[.9, .6, .3]]], np.float32) * 1.2, .72, 1.2)[0, 0]
    sat = lambda c: (c.max() - c.min()) / max(c.max(), 1e-6)
    check('lampe chaude (scène 3,0) : va vers le blanc', sat(lamp) < sat(np.array([3., 2., 1.])) - .2, f'saturation {sat(lamp):.2f}')
    check('surface éclairée (scène 0,9) : saturation gardée', abs(sat(lit) - sat(np.array([.9, .6, .3]))) < .01, f'saturation {sat(lit):.2f}')

    print('6. sur une vraie image (exposition 1,85)')
    hot = dict(g0, exposure=1.85)
    a = img([('grade', hot)]); b = img([('grade', dict(hot, epaule=True))])
    la, lb = lum(a), lum(b)
    check('l\'épaule change bien l\'image', not np.array_equal(a, b))
    check('moins de pixels brûlés', (lb > 245).mean() <= (la > 245).mean(), f'{(la > 245).mean():.4f} -> {(lb > 245).mean():.4f}')
    dark = la < 60
    check('ombres non assombries', abs(float(lb[dark].mean()) - float(la[dark].mean())) < 2.5 if dark.any() else True,
          f'{la[dark].mean():.1f} -> {lb[dark].mean():.1f}' if dark.any() else 'aucune ombre')
    check('déterministe', np.array_equal(b, img([('grade', dict(hot, epaule=True))])))

    print('7. halo haut')
    from hstudio.engines.pixel3d import lighting as LT

    class Ctx: pass
    for y, clamped in ((21.5, False), (200., True)):
        c = Ctx(); c.lighting_warnings = []
        v = LT._num(c, 'lighting.halo[0].y', y, 1.1, .02, 80.)
        check(f'halo à {y:g} m : {"ramené à 80" if clamped else "gardé"}', (v == 80.) if clamped else (v == y))
    src = open(os.path.join(ROOT, 'hstudio', 'engines', 'pixel3d', 'lighting.py'), encoding='utf-8').read()
    check('la borne du halo est bien 80 m dans le moteur', "h.get('y', 1.1), 1.1, .02, 80.)" in src)

    print(f'\n{OK[0]} OK, {BAD[0]} échec(s)')
    return 1 if BAD[0] else 0


if __name__ == '__main__':
    sys.exit(main())
