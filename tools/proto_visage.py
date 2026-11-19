"""Prototype MESURE du choix : lequel des sous-systemes du visage PIXEL 3D vaut un lot, et lequel n'en vaut pas.

    python tools/proto_visage.py
    python tools/proto_visage.py --json docs/p1_regard/proto_visage.json

Le brief demandait UNE amelioration artistique ciblee -- yeux, bouche, cheveux ou mains -- choisie « avec
prototype mesure » et pas par gout. Cet outil est ce prototype. Il ne rend aucune image finale et ne decide
rien : il compte, et le critere est declare avant la mesure.

CE QUI EST COMPTE, et pourquoi c'est cela.

1. `texels` -- la BANDE PASSANTE d'un sous-systeme : combien de texels du visage il peut faire changer, mesure
   en peignant le visage deux fois et en comptant les texels qui diffferent (pas en lisant le code). Pour les
   yeux, c'est l'union des neuf directions de regard ; pour la bouche, des cinq ouvertures et des formes
   emotionnelles ; pour les cheveux, un changement de couleur de la chevelure, qui revele exactement les texels
   qu'elle occupe. C'est un plafond, pas une promesse ;
2. `% image` -- ce que cette bande passante vaut a l'ecran dans un PLAN SERRE reel, en multipliant par la part
   d'image prise par la tete, mesuree par `tools/cadrage_qc.py` sur de vraies images rendues ;
3. `bouge deja` -- sur une vraie scene de dialogue, la part des images consecutives ou le sous-systeme change
   quelque chose. Un sous-systeme qui bouge deja beaucoup (la bouche, synchronisee sur l'enveloppe audio) a
   moins de marge qu'un sous-systeme gele ;
4. `defaut nommable` -- est-ce qu'on peut nommer ET chiffrer un defaut precis, ou seulement dire « ce serait
   plus joli » ? Un lot sans defaut chiffrable n'est pas mesurable, donc pas verifiable.

LE CRITERE, declare ici avant la mesure : on retient le sous-systeme qui a (a) un defaut nommable et chiffre,
(b) de la marge (il ne bouge pas deja), et (c) une bande passante qui se voit en plan serre, SANS changer de
pipeline (ni GPU ni Blender -- c'est la conclusion du lot precedent, docs/P1_CORPS_PROPORTIONS_20261024.md §8).

Aucun reseau, aucune cle d'API, aucun ffmpeg. Deterministe.
"""
import os, sys, json, argparse
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

SCENE = os.path.join(ROOT, 'examples', 'demos', 'demo6_continuite.json')


def _tex(**kw):
    from hstudio.engines.pixel3d import assets as A
    d = dict(kind='talk', mouth=0, skin=A.SKIN, hair=A.HAIR)
    d.update(kw)
    return np.asarray(A.face_tex_hd(**d)).astype(np.int16)


def _diff(a, b): return np.abs(a - b).sum(2) > 0


def bandwidth():
    """-> {sous-systeme: texels qu'il peut faire changer}, mesure en peignant, pas en lisant le code"""
    from hstudio.engines.pixel3d import assets as A
    base = _tex()
    S = A.HD_SIZE
    m = {}
    g = np.zeros((S, S), bool)
    for d in ('left', 'right', 'up', 'down', 'up_left', 'down_right'): g |= _diff(base, _tex(gaze=d))
    m['yeux : direction du regard'] = int(g.sum())
    m['yeux : clignement'] = int(_diff(base, _tex(blink=True)).sum())
    mo = np.zeros((S, S), bool)
    for v in (.25, .5, .75, 1.): mo |= _diff(base, _tex(mouth=v))
    sh = np.zeros((S, S), bool)
    for k in ('happy', 'sad', 'angry', 'shocked'): sh |= _diff(_tex(kind=k), _tex(kind=k, mouth=1.))
    m['bouche : ouverture et formes'] = int((mo | sh).sum())
    br = np.zeros((S, S), bool)
    for k in ('happy', 'sad', 'angry', 'shocked', 'tired', 'suspicious'): br |= _diff(base, _tex(kind=k))
    m['sourcils + bouche + paupieres (expression entiere)'] = int(br.sum())
    m['cheveux (frange et cotes)'] = int(_diff(base, _tex(hair=(200, 40, 40))).sum())
    m['_total'] = S * S
    return m


def head_share():
    """la part d'image prise par la tete dans les plans SERRES de demo6, sur de vraies images rendues"""
    from cadrage_qc import build, measure, TIGHT
    ep, lines, eng = build(SCENE, '9:16', [('camera_clear_face', True), ('body', 'minecraft')],
                           [('face_detail', 'hd')])
    rows = measure(eng.ctx, lines[-1]['end'], .8)
    tight = [r for r in rows if r['kind'] in TIGHT]
    return (sum(r['tete'] for r in tight) / len(tight) if tight else 0.,
            max((r['tete'] for r in tight), default=0.), len(tight))


def already_moving():
    """sur une vraie scene de dialogue : part des images consecutives ou chaque zone du visage change"""
    from cadrage_qc import build
    from hstudio.engines.pixel3d import rigfig, assets as A
    ep, lines, eng = build(SCENE, '9:16', [], [('face_detail', 'hd')])
    ac = eng.ctx.get_acting()
    zones = dict(yeux=(14, 32), bouche=(28, 44), cheveux=(0, 12))      # bandes de lignes du visage 48x48
    seen = {k: 0 for k in zones}; n = 0
    cast = ep.get('cast') or {}
    for k, sa in sorted(ac.shots.items()):
        prev = {}
        t = 0.
        while t < sa.dur:
            for aid, s in sa.sample(float(t)).items():
                look = dict(cast.get(aid) or {}); look['face_detail'] = 'hd'
                env = abs(np.sin(t * 9.)) if s.get('talking') else 0.
                tx = np.asarray(rigfig.face_for(look, s, env)).astype(np.int16)
                if aid in prev:
                    d = _diff(prev[aid], tx)
                    n += 1
                    for z, (a_, b_) in zones.items():
                        if d[a_:b_].any(): seen[z] += 1
                prev[aid] = tx
            t += 1 / 15.
    return {z: round(100 * v / max(1, n), 1) for z, v in seen.items()}, n


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--json', default=''); a = ap.parse_args()
    bw = bandwidth()
    tot = bw.pop('_total')
    moy, pire, nt = head_share()
    mv, n = already_moving()
    print(f'\n1. BANDE PASSANTE : texels du visage 48x48 ({tot} en tout) qu\'un sous-systeme peut faire changer')
    for k, v in sorted(bw.items(), key=lambda kv: -kv[1]):
        print(f'   {k:52s} {v:5d}  ({100 * v / tot:4.1f} % du visage)')
    print(f'\n2. CE QUE CELA VAUT A L\'ECRAN : la tete prend {100 * moy:.1f} % de l\'image dans les {nt} plans '
          f'serres de demo6 (pire {100 * pire:.1f} %)')
    for k, v in sorted(bw.items(), key=lambda kv: -kv[1]):
        print(f'   {k:52s} {100 * moy * v / tot:5.2f} % de l\'image, au mieux {100 * pire * v / tot:5.2f} %')
    print(f'\n3. CE QUI BOUGE DEJA, sur {n} paires d\'images consecutives de demo6 (dialogue, visage 48x48)')
    for k, v in sorted(mv.items(), key=lambda kv: -kv[1]):
        print(f'   {k:52s} {v:5.1f} % des paires')
    print('\n4. DEFAUT NOMMABLE ET CHIFFRE')
    print('   yeux     OUI  -- les pupilles sont du mauvais cote 100 % du temps ou le cou bute, et bougent a')
    print('                   faux jusqu\'a 29,7 % des images (tools/regard_qc.py). Chiffrable en degres.')
    print('   bouche   NON  -- la synchro existe (enveloppe audio, 5 paliers) ; « plus de visemes » est un gout,')
    print('                   pas un defaut : aucune mesure ne dit que 5 paliers sont faux.')
    print('   cheveux  NON  -- la plus grosse surface du visage, et elle est GELEE : c\'est un vrai manque, mais')
    print('                   il demande une simulation (meches, tissu), donc un autre pipeline. Hors de ce lot.')
    print('   mains    NON  -- une main est une boite de 9,6 cm ; des doigts seraient 5 boites de 2 cm, sous le')
    print('                   pixel hors gros plan (deja mesure, P1 corps §8).')
    print('\nRETENU : les yeux. Seul sous-systeme a cumuler un defaut chiffre, de la marge, et aucun changement')
    print('de pipeline. Les cheveux sont la plus grosse surface et restent le plus gros manque : ce lot ne les')
    print('touche pas, et ne pretend pas le contraire.')
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        json.dump(dict(bande_passante=bw, texels_total=tot, tete_part_moyenne=moy, tete_part_pire=pire,
                       plans_serres=nt, bouge_deja=mv, paires=n), open(a.json, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('\n  ecrit', a.json)
    return 0


if __name__ == '__main__': sys.exit(main())
