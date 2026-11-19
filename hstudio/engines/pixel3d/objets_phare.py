"""OBJETS DÉTAILLÉS, LOT « phare » (15/11/2026, série « Le Phare qui efface »), version PS1 : le fusible noir « ARRÊT » de la salle des commandes.

Découvert tout seul par `objets._load_lots()` (fichier `objets_<lot>.py`) : aucune ligne à écrire ailleurs ; noms nouveaux seulement.
Posé (face avant vers -z, y = 0 posé ; la clé `y` du décor soulève) :
  od_fusible   cartouche noire de 26 cm couchée (axe x), deux culots de cuivre, bande blanche « ARRÊT » sur le dessus ; `brule` : culots noircis.
Tenu (`hold`) :
  od_fusible   le fusible ARRACHÉ, tenu au milieu, dans l'axe du bras (l'étiquette vers le haut) ; la cartouche de la console (lieu `phare_interieur`,
               `state.fusible` 0) a disparu au même moment : garder le même objet dans la même main d'un plan à l'autre.
VOXEL : pas de version native (l'objet tenu n'y est pas dessiné)."""
from .r3d import C, M_METAL
from . import objets as OD

_col = OD._col
COPPER = (184, 110, 60); BLACK = (20, 20, 22); LABEL = (236, 232, 220)


def k_fusible(p, c):
    cap = (40, 30, 24) if OD._g(p, 'brule', default=False) else COPPER
    col = _col(c, BLACK)
    return [C((0, .045, 0), (.2, .085, .085), col, mat=M_METAL), C((-.115, .045, 0), (.03, .09, .09), cap, mat=M_METAL), C((.115, .045, 0), (.03, .09, .09), cap, mat=M_METAL),
            C((0, .089, 0), (.12, .004, .05), LABEL), C((0, .0905, 0), (.07, .002, .012), (30, 30, 34))]


def h_fusible(P, F, k, lights, col, cfg):
    """the ripped fuse held in the fist, along the forearm (forward), label up"""
    c = _col(col, BLACK)
    return [C(P(0, .02, .05), (.085, .085, .2), c, mat=M_METAL, **k), C(P(0, .02, -.065), (.09, .09, .03), COPPER, mat=M_METAL, **k),
            C(P(0, .02, .165), (.09, .09, .03), COPPER, mat=M_METAL, **k), C(P(0, .064, .05), (.05, .004, .12), LABEL, **k),
            C(P(0, .0655, .05), (.012, .002, .07), (30, 30, 34), **k)]


def enregistrer(R):
    """un nom déjà pris est sauté (et dit)"""
    try: R.objet('od_fusible', k_fusible, 'fusible noir ARRÊT (cartouche)')
    except ValueError as e: print(e)
    try: R.tenu('od_fusible', h_fusible, 'fusible ARRÊT arraché, tenu')
    except ValueError as e: print(e)
