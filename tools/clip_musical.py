"""CLIP MUSICAL, étape 1 : une musique -> tout ce qu'il faut au directeur pour écrire le scénario dessus.

    python tools/clip_musical.py <musique> <dossier> [--debut 46] [--fin 105.9] [--fondu 0.6,1.6]

Écrit dans <dossier> :
  analysis.json         tempo, temps, premiers temps, sections, silences, énergie, phrases (hstudio/audio/music_analysis.py)
  musique.wav           l'extrait, fondus posés, 48 kHz stéréo, -14 LUFS / crête -1,5 dBTP : la bande son du clip
  FEUILLE_MUSIQUE.md    la partition lisible par le directeur (Claude ou un autre) : où couper, où frapper, où se taire

Étape 2 (le directeur) : écrire la scène dirigée en posant les plans sur la feuille (modèle : examples/clip_musical/
clip_demo.py), avec `music_cues` pour les coupes et les lumières qui battent, `"pulse"` pour la caméra.
Étape 3 : tools/render_film_dirigee.py <dossier dirige> ps1|voxel <sortie.mp4> --audio <dossier>/musique.wav
"""
import argparse, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.audio import music_clip as MCL             # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('musique'); ap.add_argument('dossier')
    ap.add_argument('--debut', type=float, default=0.); ap.add_argument('--fin', type=float, default=None)
    ap.add_argument('--fondu', default='0.6,1.6')
    ap.add_argument('--separer', action='store_true', help="sépare d'abord la voix (Demucs, GPU, ~1 min) dans <dossier>/stems")
    ap.add_argument('--voix', default=None, help='dossier de pistes déjà séparées (voix.wav, drums.wav, accompagnement.wav)')
    ap.add_argument('--ancre', type=float, default=None, help="instant (s, dans la chanson) connu pour être un premier temps : l'entrée du refrain")
    a = ap.parse_args()
    stems = a.voix
    if a.separer: stems = str(MCL.separate(a.musique, str(Path(a.dossier) / 'stems')))
    A = MCL.prepare(a.musique, a.dossier, a.debut, a.fin, tuple(float(x) for x in a.fondu.split(',')), stems=stems, anchor=a.ancre)
    print(f'tempo {A["tempo"]} BPM, {len(A["sections"])} sections, {len(A["silences"])} silences, sommet {A["climax"]} s -> {a.dossier}')


if __name__ == '__main__':
    main()
