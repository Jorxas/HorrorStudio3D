"""python -m hstudio.histoire <étape> <dossier> [options] — le kit de production d'une histoire narrée.

Mode d'emploi : python -m hstudio.histoire --help ; guide complet : docs/GUIDE_HISTOIRE_POUR_IA.md.
(hstudio/__main__.py n'est pas modifié : il est épinglé par le manifeste SHA-256 de tools/check_voxelgpu.py.)"""
import sys

from .cli import main

if __name__ == '__main__':
    sys.exit(main())
