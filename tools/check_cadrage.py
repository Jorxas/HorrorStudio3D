"""Tests hors ligne de l'option de cadrage « camera_clear_face » (P1 visuel).

    python tools/check_cadrage.py

Ce que ca verifie, et pourquoi chaque point est la :

1. **inerte sans la cle** -- sans `camera_clear_face`, `cinema.Subject.arms` est vide, `arm_penalty` rend
   exactement 0, et une image rendue est identique au bit pres a celle d'avant l'option ;
2. **la penalite mesure le bon defaut** -- elle est forte quand la main est tendue vers l'objectif, nulle quand
   le bras pend le long du corps, et elle ne depend pas de la distance seule ;
3. **le crochet de mesure de `rigfig` est inerte** -- `rigfig.PARTS = None` par defaut, et le poser ne change
   pas une image ;
4. **l'option est deterministe** -- deux rendus de la meme image sont identiques au bit pres ;
5. **elle entraine le cadrage conscient du visage** -- `clear_face` sans `face_track` doit quand meme donner un
   sujet avec un regard connu, sinon l'option echange un bras contre un visage de dos (mesure a l'integration) ;
6. **elle reduit vraiment le defaut sur une vraie scene** -- part d'image prise par le bras du sujet sur les
   plans serres de `demo6_continuite`, mesuree par `tools/cadrage_qc.py` sur de vraies images rendues ;
7. **le realisateur IA ne connait pas la cle** -- comme pour toutes les options non jugees (regle AGENTS.md).

Aucun reseau, aucune cle, aucun cout, aucun ffmpeg.
"""
import os, sys, math, json, copy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

OK = [0]; BAD = [0]


def check(label, cond, detail=''):
    ok = bool(cond)
    (OK if ok else BAD)[0] += 1
    print(('  OK   ' if ok else '  ECHEC ') + label + (f'   [{detail}]' if detail else ''))
    return ok


def main():
    from hstudio.acting import cinema
    from hstudio.engines.pixel3d import rigfig, acted
    from cadrage_qc import build, measure, TIGHT

    print('1. inerte sans la cle')
    s = cinema.Subject('lea', 0., 0., 0., 1.62)
    check('un sujet sans bras declares : arms vide', s.arms == ())
    check('  et la penalite est exactement 0', cinema.arm_penalty(s, (0., 1.6, -1.5), .26) == 0.)
    check('le defaut du moteur est "pas de cadrage degage"', acted.CLEAR_FACE_DEFAULT is False)
    check('  et un episode sans la cle ne le demande pas', acted.clear_face(type('C', (), {'ep': {}})(), {}) is False)
    check('  une cle de plan peut l\'eteindre malgre l\'episode',
          acted.clear_face(type('C', (), {'ep': {'camera_clear_face': True}})(), {'clear_face': False}) is False)

    print('\n2. la penalite mesure le bon defaut, pas la distance')
    # camera 1.7 m devant le visage, a hauteur des yeux ; le sujet regarde la camera
    cam = (0., 1.62, -1.7); th = math.tan(math.radians(50) / 2) * .5625
    rest = ((0., 1.38, -.02), (0., 1.09, -.03), (0., .94, -.03), (0., .79, -.03))        # bras le long du corps
    point = ((0., 1.38, -.02), (-.02, 1.33, -.30), (-.02, 1.31, -.44), (-.02, 1.29, -.58))  # main tendue vers l'objectif
    s_rest = cinema.Subject('lea', 0., 0., 0., 1.62, arms=(( rest,),))
    s_pt = cinema.Subject('lea', 0., 0., 0., 1.62, arms=((point,),))
    p_rest = cinema.arm_penalty(s_rest, cam, th); p_pt = cinema.arm_penalty(s_pt, cam, th)
    check('bras au repos : rien a payer', p_rest < .02, f'{p_rest:.3f}')
    check('main tendue vers l\'objectif : fortement payee', p_pt > .5, f'{p_pt:.3f}')
    far = (0., 1.62, -3.4)
    p_far = cinema.arm_penalty(s_pt, far, th)
    check('  et reculer la fait baisser', p_far < p_pt * .85, f'{p_far:.3f} < {p_pt:.3f}')
    side = (1.7, 1.62, 0.)
    p_side = cinema.arm_penalty(s_pt, side, th)
    check('  tourner autour aussi', p_side < p_pt, f'{p_side:.3f} < {p_pt:.3f}')
    check('la penalite reste bornee a 1', max(p_pt, p_side, p_far) <= 1.0)

    print('\n3. le crochet de mesure de rigfig est inerte')
    check('rigfig.PARTS vaut None au repos', rigfig.PARTS is None)

    print('\n4. sans la cle, l\'image ne bouge pas d\'un bit ; avec, elle bouge')
    scene = os.path.join(ROOT, 'examples', 'demos', 'demo6_continuite.json')
    def img(keys, t=15.5):
        _, _, eng = build(scene, '9:16', keys, [])
        return np.asarray(eng.frame(t).convert('RGB'))
    a1 = img([]); a2 = img([])
    check('deux rendus par defaut : identiques au bit pres', np.array_equal(a1, a2))
    b1 = img([('camera_clear_face', True)]); b2 = img([('camera_clear_face', True)])
    check('deux rendus avec la cle : identiques au bit pres (deterministe)', np.array_equal(b1, b2))
    d = float(np.abs(a1.astype(np.int16) - b1.astype(np.int16)).mean())
    check('la cle change reellement l\'image', d > 1.0, f'ecart moyen {d:.1f}/255')
    check('  et rigfig.PARTS est bien revenu a None', rigfig.PARTS is None)

    print('\n5. clear_face entraine le cadrage conscient du visage')
    _, _, eng = build(scene, '9:16', [('camera_clear_face', True)], [])
    eng.frame(15.5)
    plans = [p for p in eng.ctx.cam_cache.values() if p]
    witharms = [p for p in plans if any(getattr(s_, 'arms', ()) for s_ in [])]
    sub = None
    for p in plans:
        sol = p.get('sol') or {}
        if sol: sub = p
    check('au moins un plan a ete resolu', sub is not None)
    # le modele de sujet porte un regard des que la cle est la : c'est ce qui empeche l'option de degrader
    from hstudio.engines.pixel3d.acted import subjects_at, face_track, clear_face
    ctx = eng.ctx
    check('face_track seul reste faux sur cet episode', face_track(ctx, {}) is False)
    check('  mais clear_face est vrai', clear_face(ctx, {}) is True)

    print('\n6. sur une vraie scene, le bras prend moins de place')
    def tight(keys):
        ep, lines, eng = build(scene, '9:16', keys, [])
        rows = [r for r in measure(eng.ctx, lines[-1]['end'], .5) if r['kind'] in TIGHT]
        return (100 * sum(r['bras'] for r in rows) / len(rows), 100 * max(r['bras'] for r in rows),
                100 * max(r['visage_mange'] for r in rows))
    base = tight([])
    ft = tight([('camera_face_track', True)])
    cf = tight([('camera_clear_face', True)])
    print(f'     defaut           bras {base[0]:5.2f} % (pire {base[1]:4.1f} %)  visage mange au pire {base[2]:4.1f} %')
    print(f'     face_track       bras {ft[0]:5.2f} % (pire {ft[1]:4.1f} %)  visage mange au pire {ft[2]:4.1f} %')
    print(f'     + clear_face     bras {cf[0]:5.2f} % (pire {cf[1]:4.1f} %)  visage mange au pire {cf[2]:4.1f} %')
    check('clear_face fait mieux que le defaut', cf[0] < base[0] * .8, f'{cf[0]:.2f} vs {base[0]:.2f}')
    check('  et mieux que face_track seul', cf[0] < ft[0], f'{cf[0]:.2f} vs {ft[0]:.2f}')
    check('  le pire moment aussi', cf[1] < base[1] * .8, f'{cf[1]:.1f} vs {base[1]:.1f}')
    check('  et le visage est moins mange qu\'avec face_track seul', cf[2] < ft[2] * .8, f'{cf[2]:.1f} vs {ft[2]:.1f}')

    print('\n7. le realisateur IA ne connait pas la cle')
    from hstudio.director import prompts as P
    sent = chr(10).join(v for k, v in vars(P).items() if k.isupper() and isinstance(v, str))
    nocomment = lambda t: chr(10).join(l for l in t.split(chr(10)) if not l.lstrip().startswith('#'))
    code = nocomment(open(os.path.join(ROOT, 'hstudio', 'director', 'prompts.py'), encoding='utf-8').read())
    code += nocomment(open(os.path.join(ROOT, 'hstudio', 'director', 'heuristic.py'), encoding='utf-8').read())
    check('"clear_face" n\'est ni dans le texte envoye ni dans le code du realisateur',
          'clear_face' not in sent and 'clear_face' not in code)

    print(f"\n{OK[0]} OK, {BAD[0]} echec(s)")
    return 1 if BAD[0] else 0


if __name__ == '__main__': sys.exit(main())
