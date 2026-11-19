"""Le kit de production d'une histoire narrée, en script : même chose que « python -m hstudio.histoire ».

    python tools/histoire.py <étape> <dossier> [options]       (étapes : nouveau, voix, phrases, construire, apercu,
                                                                verifier, rendre, mixer, livrer, etat, catalogue)
Guide : docs/GUIDE_HISTOIRE_POUR_IA.md."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == '__main__':
    from hstudio.histoire.cli import main
    sys.exit(main())
