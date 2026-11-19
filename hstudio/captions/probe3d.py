"""Ou sont les visages dans l'image, en PIXEL 3D. Lecture seule : ce module ne modifie rien du moteur.

POURQUOI PAS UNE PROJECTION. La premiere version projetait les huit coins de la boite englobante de la
tete avec `r3d.project`. Mesure faite, c'est faux en plan serre : la boite englobante MONDE d'une boite
tournee est bien plus grande que la boite, et en gros plan certains coins passent derriere le plan de la
camera -- la projection explose. Sur `examples/scenes/portrait_peur.json` elle rendait des x de -10336 a
1020 sur un cadre de 1080. Inutilisable.

CE QUI EST UTILISE A LA PLACE, et c'est un mecanisme qui EXISTE DEJA : `rigfig.PARTS`, le crochet de
mesure que `tools/cadrage_qc.py` a introduit, plus le tampon d'indices du lanceur de rayons. On rend la
scene une fois en basse resolution (216x384 en 9:16, la ou les pixels sont decides) et on lit quels
pixels appartiennent aux boites du groupe `head`. Resultat :

- exact, y compris en gros plan extreme ;
- **conscient des occlusions** : des cheveux lateraux devant la joue, un avant-bras devant le menton ou
  un mur qui coupe le visage retrecissent la boite mesuree, parce qu'on compte des pixels VISIBLES ;
- aucun reseau, aucun GPU, aucune detection : le moteur sait deja quelle boite a gagne chaque rayon.

LA BOUCHE ET LES YEUX. Le visage est une texture posee sur la face +z du cube de peau de la tete
(`rigfig` : `C((0,0,0), (.40,.40,.38), skin, tex={'+z': face})`). Dans cette texture, les yeux sont a la
rangee 11 sur 24 et la bouche a la rangee 17 sur 24 (`assets.face_tex`) ; la version 48x48 met 22 et 34,
soit **exactement les memes fractions** 0.458 et 0.708. Les bandes ci-dessous sont donc lues dans le
moteur, pas devinees.

CE QUE C'EST QUAND MEME : une ESTIMATION. Les fractions sont appliquees a l'etendue verticale VISIBLE du
cube de peau. Quand la tete est tournee de profil, ou coupee par le bord du cadre, cette etendue n'est
plus celle de la face +z et les bandes bouche/yeux glissent. C'est pour ca que la politique de
`geometry.py` protege AUSSI toute la boite de tete, qui elle n'a pas ce defaut : les bandes servent a
hierarchiser (couvrir une bouche coute plus cher que couvrir un front), la boite de tete sert de garde.
"""
import numpy as np

# fractions de l'etendue verticale du cube de peau, lues dans engines/pixel3d/assets.face_tex
# (24x24 : yeux rangee 11, bouche rangee 17 ; 48x48 : 22 et 34 -- memes fractions)
EYES_V = (9. / 24., 15. / 24.)      # 0.375 .. 0.625  : paupieres, sourcils compris
MOUTH_V = (15. / 24., 23. / 24.)    # 0.625 .. 0.958  : levres, bouche ouverte et menton

FACE_TEX_KEY = 5                    # r3d.FACES['+z'] : la face qui porte la texture de visage


def _bbox(ib, idmap, boxes, rw, rh):
    """boite des pixels VISIBLES de `boxes` dans le tampon d'indices -> (x0, x1, y0, y1) normalise, y bas"""
    idx = [idmap[id(b)] for b in boxes if id(b) in idmap]
    if not idx:
        return None, 0
    m = np.isin(ib, np.asarray(idx))
    n = int(m.sum())
    if not n:
        return None, 0
    ys, xs = np.nonzero(m)
    return (float(xs.min()) / rw, float(xs.max() + 1) / rw,
            float(ys.min()) / rh, float(ys.max() + 1) / rh), n


def faces_at(ctx, g, aspect='9:16'):
    """-> (liste de zones a proteger, infos). Une zone par personnage visible dans l'image a l'instant g.

    Chaque zone : {'rect': boite de tete, 'mouth': bande bouche, 'eyes': bande yeux, 'share': part de
    l'image, 'weight': 1.}  -- tout en coordonnees normalisees, y vers le bas.

    ATTENTION, cout : un trace basse resolution complet, mesure a ~0.11 s sur la machine de test. Les
    appelants le font quelques fois par PLAN, jamais par image (voir safe.py).
    """
    from ..engines.pixel3d import r3d, rigfig
    from ..engines.pixel3d.frame import build_frame, CUR_T

    keep_parts, keep_t = rigfig.PARTS, CUR_T[0]
    rigfig.PARTS = parts = {}
    try:
        sc, cam, L, shot, T, u, k, state = build_frame(ctx, g)
    finally:
        rigfig.PARTS = keep_parts
        CUR_T[0] = keep_t            # build_frame pose le temps du plan courant : on rend celui de l'appelant

    head = parts.get('head') or []
    if not head:
        return [], dict(shot=k, kind=(shot.get('camera') or {}).get('shot'), heads=0)

    pos, yaw, pitch, roll, fov = cam
    pos = np.asarray(pos, np.float32)
    D = r3d.cam_dirs(yaw, pitch, roll, fov)
    ceil = sc.ceil_y if (sc.ceil_y is not None or getattr(sc, 'sky_fn', None) is None) else np.inf
    fy = float(getattr(sc, 'floor_y', 0.))
    bx = r3d.cull(sc.boxes, pos, yaw, pitch, fov)
    _, ib = r3d.trace(pos, D, bx, fy, ceil, True, r3d._noise)
    rw, rh = r3d.RW, r3d.RH
    ib = ib.reshape(rh, rw)
    idmap = {id(b): i for i, b in enumerate(bx)}

    # `head` melange les tetes de TOUS les personnages du plan. On les sépare par instance rigide :
    # rigfig.orient() donne a chaque personnage son propre Instance, donc `b.inst` est l'identite du
    # personnage -- sans avoir a lui demander son nom (que le crochet de mesure ne porte pas).
    groups = {}
    for b in head:
        groups.setdefault(id(b.inst), []).append(b)

    zones = []
    for key, boxes in groups.items():
        rect, n = _bbox(ib, idmap, boxes, rw, rh)
        if rect is None:
            continue
        faceb = [b for b in boxes if FACE_TEX_KEY in (b.tex or {})]
        frect, _fn = _bbox(ib, idmap, faceb, rw, rh) if faceb else (None, 0)
        mouth = eyes = None
        if frect:
            y0, y1 = frect[2], frect[3]
            hh = y1 - y0
            mouth = (frect[0], frect[1], y0 + MOUTH_V[0] * hh, y0 + MOUTH_V[1] * hh)
            eyes = (frect[0], frect[1], y0 + EYES_V[0] * hh, y0 + EYES_V[1] * hh)
        zones.append(dict(rect=rect, mouth=mouth, eyes=eyes, face=frect,
                          share=round(n / float(rw * rh), 5), weight=1.))
    zones.sort(key=lambda z: -z['share'])
    return zones, dict(shot=k, kind=(shot.get('camera') or {}).get('shot'), heads=len(zones),
                       raster=(rw, rh))
