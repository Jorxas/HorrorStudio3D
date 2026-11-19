"""Contrôle qualité d'une scène dirigée (PS1 / VOXEL / CONSOLE) : détecte, explique en français, corrige ce qui est sûr.

    python tools/verifier_scene.py <dossier épisode> [--format 16:9|9:16] [--style ps1|voxel|console] [--images] [--corriger]
                                   [--sortie DOSSIER] [--rapport DOSSIER] [--workers 6]

<dossier épisode> contient episode.json + lines.json (scène dirigée : `tracks` + caméra `rig: path`).
  --format    16:9 ou 9:16 (sinon deviné du nom du dossier, « 9x16 », puis de `aspect`, puis 16:9)
  --style     ps1, voxel ou console (sinon deviné : `voxel_mirror` ou « voxel » dans le chemin -> voxel)
  --images    ajoute les contrôles sur des images basse définition du VRAI peintre (PS1 : le lanceur de rayons ;
              VOXEL : le peintre GPU, un seul rendu GPU à la fois ; CONSOLE : le moteur console) — plus lent
  --corriger  écrit une COPIE corrigée (défaut : <dossier>_corrige, jamais l'original) + CORRECTIONS.md + le rapport d'après
Rapport : <dossier>/_qa/rapport_qa.md et .json (ou --rapport). Code de sortie : 0 sans erreur bloquante, 2 sinon.
Lire docs/QA_SCENE.md pour comprendre le rapport et corriger à la main."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if not a or a[0] in ('-h', '--help'):
        print(__doc__); return 0
    opt = lambda k, d=None: (a.pop(a.index(k) + 1), a.pop(a.index(k)))[0] if k in a else d
    flag = lambda k: (a.remove(k), True)[1] if k in a else False
    aspect = opt('--format'); style = opt('--style'); out = opt('--sortie'); rdir = opt('--rapport'); workers = int(opt('--workers', 6))
    images = flag('--images'); fix = flag('--corriger')
    folder = a[0]
    if not os.path.exists(os.path.join(folder, 'episode.json')):
        print(f'pas de episode.json dans {folder}'); return 1
    from hstudio import qa
    from hstudio.qa.report import BLOQUANT, A_REVOIR
    t0 = time.time()
    if fix:
        res = qa.correct(folder, out, aspect=aspect, style=style, images=images, workers=workers)
        b, f = res['before'].counts(), res['after'].counts()
        print(f'avant : {b[BLOQUANT]} bloquant(s), {b[A_REVOIR]} à revoir — {len(res["changes"])} correction(s) automatique(s)')
        for c in res['changes'][:40]: print(f'  {c["cle"]} : {c["avant"]} -> {c["apres"]} ({c["pourquoi"]})')
        print(f'après : {f[BLOQUANT]} bloquant(s), {f[A_REVOIR]} à revoir — copie corrigée : {res["out"]} (CORRECTIONS.md)')
        print(f'{time.time() - t0:.0f} s')
        return 2 if f[BLOQUANT] else 0
    rep = qa.verify(folder, aspect, style, images=images, workers=workers)
    md, js = qa.write(rep, rdir or os.path.join(folder, '_qa'))
    c = rep.counts()
    print(f'{rep.style} {rep.aspect} : {c[BLOQUANT]} bloquant(s), {c[A_REVOIR]} à revoir, {c["info"]} info  ({time.time() - t0:.0f} s)')
    for i in rep.blocking()[:30]: print(f'  BLOQUANT [{i.code}] {i.where()} : {i.msg}\n           -> {i.fix}')
    print(f'rapport : {md}')
    return 2 if c[BLOQUANT] else 0


if __name__ == '__main__':
    sys.exit(main())
