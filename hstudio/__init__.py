"""Horror Studio - pipeline local pour fabriquer des histoires d'horreur en vidéo (styles PIXEL 3D et CONSOLE)."""
__version__ = "1.0.0"

# Un ffmpeg installé pour l'utilisateur n'est pas visible des shells ouverts avant l'installation : on le retrouve
# ici, pour ce processus seulement (voir ffmpeg_path.py). Sans effet si ffmpeg est déjà dans le PATH.
from . import ffmpeg_path as _ffmpeg_path
_ffmpeg_path.ensure()
