"""KIT HISTOIRE : une histoire narrée (script + voix ElevenLabs) -> film 16:9 + Shorts 9:16 livrés et mesurés.

    python -m hstudio.histoire <étape> <dossier> [options]

Étapes, dans l'ordre : nouveau, voix, phrases, construire, apercu, verifier, rendre, mixer, livrer
(+ etat, catalogue). Mode d'emploi complet pour une IA : docs/GUIDE_HISTOIRE_POUR_IA.md.
La chaîne généralise la production « Chambre 313 » (Desktop/videpgene/HISTOIRE_CHAMBRE_313).

Modules : cli (commande), common (dossiers, mesures ffmpeg, autre Python), script (lecture de script.txt),
voix (devis et génération ElevenLabs, import d'une voix existante), phrases (alignement -> phrases temporisées),
lib (aide à l'écriture de histoire.py), projet (construction des épisodes et découpe en parties), apercu, verif,
rendu, mixage, livraison, pdf_publication. Les sons fabriqués réutilisables sont dans hstudio/audio/fabriques.py."""
