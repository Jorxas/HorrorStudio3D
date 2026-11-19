"""Sous-titres surs : ou poser le bandeau pour qu'il ne couvre ni bouche, ni yeux, ni information
narrative, automatiquement et sans que l'utilisateur regle quoi que ce soit.

- `geometry.py` : la politique, en coordonnees normalisees. Aucun import moteur, donc testable sans rendre.
- `probe3d.py`  : ou sont les visages en PIXEL 3D, lu dans le tampon d'indices du lanceur de rayons.
- `safe.py`     : la cle d'episode "caption_safe" (opt-in) et le plan de bandes, un par plan de montage.

Sans la cle, rien de tout ceci n'est appele et le sous-titre est pose exactement ou il etait pose.
Voir docs/SUBTITLE_SAFE_9X16.md.
"""
