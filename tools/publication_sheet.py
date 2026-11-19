"""Readable publication sheet of a project: `publication.txt` next to its `metadata.json` (copy-paste, no upload).

  python tools/publication_sheet.py <slug|chemin_du_projet>     # écrit et affiche la fiche
  python tools/publication_sheet.py <slug> --print              # affiche seulement

An old project whose metadata.json has no `platforms` block gets it rebuilt here from episode.json +
project.json (offline, no API call, metadata.json itself is left untouched)."""
import os, sys, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from hstudio import paths, publish

def sheet(d):
    d = d if os.path.isdir(d) else os.path.join(paths.PROJECTS, d)
    if not os.path.isdir(d):
        raise SystemExit(f'Projet introuvable : {d}')
    load = lambda f: json.load(open(os.path.join(d, f), encoding='utf-8')) if os.path.exists(os.path.join(d, f)) else {}
    md = load('metadata.json')
    if not md:
        raise SystemExit(f'Pas de metadata.json dans {d} : lance d’abord l’étape « métadonnées ».')
    pack = md.get('platforms') or publish.pack(load('project.json'), load('episode.json'), md)
    return d, publish.as_text(pack)

if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    if not args:
        raise SystemExit(__doc__)
    d, txt = sheet(args[0])
    if '--print' not in sys.argv:
        open(os.path.join(d, 'publication.txt'), 'w', encoding='utf-8').write(txt + '\n')
        print(f'Écrit : {os.path.join(d, "publication.txt")}\n')
    print(txt)
