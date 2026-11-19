"""Les deux styles 3D du studio et ce que chaque élément y est.

PS1   = moteur PIXEL 3D (lancer de rayons sur boîtes, rendu bas-pixel façon console de 1995), choix `render_engine: "pixel3d"` d'un projet.
VOXEL = moteur GPU (Three.js), choix `render_engine: "voxel"`.
Un épisode s'écrit une fois ; le choix du style décide quelle version de chaque élément est peinte. Statuts :
  native    dessiné tel quel par ce style
  converted construit à partir de la version de l'autre style, mêmes dimensions (le rendu est celui de ce style)
  approx    silhouette approchée : même taille, tenue et couleurs, pas la même animation
(un style absent d'une fiche = l'élément n'existe pas dans ce style)."""

STYLES = ('ps1', 'voxel')
LABELS = {'ps1': 'Style PS1', 'voxel': 'Style VOXEL', 'native': 'natif', 'converted': 'converti', 'approx': 'approché'}

# préfixe d'identifiant du catalogue -> (statut PS1, statut VOXEL)
BY_PREFIX = {
    'decor': ('native', 'converted'), 'lieu': ('native', 'converted'), 'perso': ('native', 'converted'), 'visage': ('native', 'converted'),
    'son': ('native', 'native'), 'sonreel': ('native', 'native'),
    'craft': ('converted', 'native'), 'vox': ('converted', 'native'), 'look': ('converted', 'native'), 'monstre': ('approx', 'native'),
}


# éléments écrits en DEUX versions natives (chantier « bâtiments et intérieurs variés », 31/10/2026 ; objets détaillés `od_*`, 01/11/2026) : préfixe d'identifiant du catalogue
NATIVE_PAIRS = ('decor/qt_', 'decor/qi_', 'decor/od_', 'perso/hold/od_', 'lieu/quartier', 'lieu/appartement', 'lieu/salon_maison', 'lieu/cafe_quartier', 'lieu/boutique', 'lieu/hall_immeuble', 'lieu/escalier_immeuble', 'lieu/theatre_bal')


def of_entry(e):
    """fiche de catalogue -> {"ps1": statut, "voxel": statut}"""
    i = str(e.get('id', ''))
    if i.startswith(NATIVE_PAIRS): return {'ps1': 'native', 'voxel': 'native'}
    p = i.split('/', 1)[0]; a, b = BY_PREFIX.get(p, ('native', 'native'))
    return {'ps1': a, 'voxel': b}


def describe(st):
    return ' · '.join(f"{LABELS[k]} : {LABELS[v]}" for k, v in st.items())
