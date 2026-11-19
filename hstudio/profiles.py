"""Profils d'épisode : UN mot-clé qui pose d'un coup les modules utiles, au lieu de les connaître un par un.

    "profile": "production"

Le profil ne fait que des `setdefault` : une clé écrite dans l'épisode garde toujours la main (mettre
`"eye_aim": false` à côté du profil coupe ce module seul). Sans la clé `profile`, rien n'est lu et rien ne
change, image pour image -- c'est ce qui garde les épisodes déjà livrés et `tools/regress.py` intacts.

Le profil « production » (décidé le 31/10/2026) ne contient QUE des modules qui améliorent sans changer le
style (PS1 reste PS1, VOXEL reste VOXEL) :
  - env riche          : façades des bâtiments détaillées (engines/pixel3d/facades.py)
  - diversite decors   : quartiers à identité (brique, pastel, bois, verre, art déco, industriel, méditerranéen, néon, cité) et intérieurs à palette
                         franche + détails, en PS1 comme en VOXEL (engines/pixel3d/quartiers.py ; ajouté le 31/10/2026). `"diversite": false` à côté
                         du profil rend les lieux d'avant
  - objets detailles   : téléphones (cadran, touches, combiné et cordon spiralé), smartphone à écran lisible, standard, tasses, verres, bouteilles,
                         lampes, écrans, télévision, radio, horloge à l'heure voulue, papiers lisibles... posés ET tenus en main, en PS1 comme
                         en VOXEL (engines/pixel3d/objets.py + voxelgpu/b_objets.py ; ajouté le 01/11/2026). `"objets": false` à côté du profil
                         rend les objets d'avant
  - sfx_library        : vrais bruitages au lieu des sons de synthèse (audio/library.py)
  - caption_safe auto  : le sous-titre évite les visages, mesuré par plan (captions/safe.py)
  - eye_aim + eye_smooth : les pupilles finissent le regard que le cou ne donne pas, sans saut (eyes.py, eyeflow.py)
  - eyeline, footing, approach, foot_plant : la tête tourne au lieu de sauter, le corps fait face à sa marche,
    la marche ralentit et s'arrête pieds posés (acting/gaze.py, timeline.py, approach.py) -- plans en
    `actions` seulement : un plan dirigé en clés (`tracks`) garde exactement ce que le directeur a écrit
  - camera_face_track, camera_clear_face, head_room : la caméra automatique voit le visage, pas derrière le
    bras, tête entière en 9:16 -- caméras d'intention seulement : une caméra `rig: path` n'est pas touchée
Restent HORS profil, exprès : `body`, `finish`, `face_detail` (ils changent le style), `lighting` (c'est une
intention de mise en scène, à écrire par plan) et `extras` (figurants : un choix de scène).
"""

PROFILES = {
    'production': {
        'env': 'riche',
        'diversite': 'decors',
        'objets': 'detailles',
        'sfx_library': True,
        'caption_safe': 'auto',
        'eye_aim': 'aim',
        'eye_smooth': 'saccade',
        'eyeline': 'smooth',
        'footing': 'path',
        'approach': 'directed',
        'foot_plant': True,
        'camera_face_track': True,
        'camera_clear_face': True,
        'head_room': True,
    },
}


def apply(ep):
    """pose les clés du profil demandé par l'épisode, sur place (idempotent). -> l'épisode"""
    if not isinstance(ep, dict): return ep
    name = ep.get('profile')
    if not name: return ep
    p = PROFILES.get(str(name))
    if p is None:
        print(f"[profil] « {name} » inconnu (connus : {', '.join(PROFILES)}), ignoré")
        return ep
    for k, v in p.items():
        ep.setdefault(k, v)
    return ep
