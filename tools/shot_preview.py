"""python tools/shot_preview.py PROJET PLAN [--move dolly_in] [--shot close] [--face lea=scared ...] [--transition cut|fade|flash] [--aspect 9:16|16:9] [--seconds 5] [--show] [--options]

Rend un court clip d'UN plan (numéro à partir de 1) avec le réglage demandé, SANS rien enregistrer dans le projet : c'est l'aperçu avant validation du studio.
Le clip est écrit dans <projet>/preview_clips/ ; la ligne finale est le JSON de `hstudio.shot_preview.render_shot_clip`.
  --options   affiche seulement ce que le style du projet sait faire (cadrages, mouvements, expressions, transitions)
  --show      ouvre le clip une fois rendu
  --purge     supprime les clips d'aperçu du projet"""
import argparse, json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
os.environ.setdefault('PYTHONUTF8', '1')
from hstudio import shot_preview as SP, pipeline as P


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('project'); ap.add_argument('shot', nargs='?', type=int, help='numéro du plan (à partir de 1)')
    ap.add_argument('--move'); ap.add_argument('--shot', dest='size'); ap.add_argument('--face', action='append', default=[], metavar='ACTEUR=EXPRESSION')
    ap.add_argument('--transition'); ap.add_argument('--note'); ap.add_argument('--aspect', default='9:16'); ap.add_argument('--seconds', type=float, default=5.)
    ap.add_argument('--options', action='store_true'); ap.add_argument('--show', action='store_true'); ap.add_argument('--purge', action='store_true'); a = ap.parse_args()
    pr = P.Project(a.project)
    if not pr.meta: sys.exit(f'Projet « {a.project} » introuvable.')
    style = SP.style_of(pr.meta, P.load_settings())
    if a.purge: print(f'{SP.purge_clips(a.project) / 1e6:.1f} Mo libérés.'); return
    if a.options: print(json.dumps(dict(style=style, **SP.options(style)), ensure_ascii=False, indent=1)); return
    if a.shot is None: sys.exit('Donne le numéro du plan (à partir de 1).')
    patch = {}
    if a.move or a.size: patch['camera'] = {k: v for k, v in (('shot', a.size), ('move', a.move)) if v}
    if a.face: patch['actors'] = [dict(id=f.split('=')[0], face=f.split('=')[1]) for f in a.face]
    if a.transition: patch['transition'] = a.transition
    if a.note is not None: patch['note'] = a.note
    try: r = SP.render_shot_clip(a.project, a.shot - 1, patch, a.aspect, a.seconds, progress=lambda f, m: print(f'  {int(f * 100):>3} %  {m}', flush=True), log=lambda m: print('  ' + str(m), flush=True))
    except ValueError as e: sys.exit(str(e))
    print(json.dumps(r, ensure_ascii=False))
    if a.show: os.startfile(os.path.join(pr.dir, r['file']))


if __name__ == '__main__': main()
