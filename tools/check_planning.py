"""Tests hors ligne de l'étape PLANIFIER du kit (hstudio/histoire/planning.py) : aucun rendu, aucun réseau, aucune voix.

    python tools/check_planning.py

Tout se passe dans un dossier temporaire ($HSTUDIO_PLANNING_DIR) : le vrai PLANNING n'est pas touché."""
import io
import json
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OK = []; BAD = []


def check(name, cond, detail=''):
    (OK if cond else BAD).append(name)
    print(('  ok   ' if cond else '  ÉCHEC ') + name + (f'  ({detail})' if detail and not cond else ''))


def run(*argv):
    from hstudio.histoire import cli
    buf = io.StringIO()
    with redirect_stdout(buf): code = cli.main(list(argv))
    return code, buf.getvalue()


def main():
    from PIL import Image
    from hstudio.histoire import planning as PL, voix as V
    from hstudio.histoire.common import KitError, Story, read_json
    tmp = tempfile.mkdtemp(prefix='check_planning_')
    os.environ['HSTUDIO_PLANNING_DIR'] = os.path.join(tmp, 'PLANNING')
    try:
        code, out = run('planifier')
        check('liste vide : explique comment prévoir une vidéo', code == 0 and 'aucune vidéo prévue' in out)

        code, out = run('planifier', '--ajouter', 'Le Couloir Rouge', '--date', '2026-11-09')
        d = os.path.join(tmp, 'PLANNING', '2026-11-09_LE_COULOIR_ROUGE')
        check('ajouter : dossier, fiche et script modèle créés', code == 0 and all(os.path.exists(os.path.join(d, f)) for f in ('fiche.json', 'script.txt')))
        check('ajouter : une date invalide est refusée', run('planifier', '--ajouter', 'X', '--date', '9 novembre')[0] == 1)
        check('ajouter : une même vidéo ne s\'écrase pas', run('planifier', '--ajouter', 'Le Couloir Rouge', '--date', '2026-11-09')[0] == 1)
        run('planifier', '--ajouter', 'Une Autre', '--date', '2026-11-12')

        code, out = run('planifier')
        check('liste : script vide et miniature absente signalés', 'script vide' in out and 'miniature absente' in out and 'incomplète' in out)
        check('liste : triée par date', out.index('2026-11-09') < out.index('2026-11-12'))
        check('produire : refuse une vidéo incomplète, rien n\'est créé',
              run('planifier', '--produire')[0] == 1 and not os.path.exists(os.path.join(tmp, 'HISTOIRE_LE_COULOIR_ROUGE')))

        with open(os.path.join(d, 'script.txt'), 'a', encoding='utf-8') as f:
            f.write('[serious]\nIl y avait un couloir.\n\nIl était rouge.\n')
        Image.new('RGB', (1280, 720), (120, 0, 0)).save(os.path.join(d, 'miniature.png'))
        code, out = run('planifier')
        check('liste : la vidéo devient prête, avec ses mesures', 'prête' in out and 'miniature 1280x720' in out, out)
        check('liste : « ► » marque la prochaine', '► 2026-11-09' in out)

        code, out = run('planifier', '--produire')
        story = os.path.join(tmp, 'HISTOIRE_LE_COULOIR_ROUGE')
        check('produire : le dossier de production est créé avec le script', code == 0 and open(os.path.join(story, 'script.txt'), encoding='utf-8').read().count('couloir') == 1, out)
        check('produire : le kit a posé histoire.py et voix.json', all(os.path.exists(os.path.join(story, f)) for f in ('histoire.py', 'voix.json')))
        check('produire : la miniature est copiée', os.path.exists(os.path.join(story, 'miniatures', 'LE_COULOIR_ROUGE.png')))
        auth = read_json(os.path.join(story, 'AUTORISATION_PRODUCTION.json'))
        check('autorisation : production oui, publication NON', auth['production_authorized'] is True and auth['publication_authorized'] is False)
        check('autorisation : voix autorisée par la programmation', auth['voix_autorisee_par_planning'] is True)
        check('autorisation : empreintes du script et de la miniature', len(auth['sources'][0]['sha256']) == 64 and len(auth['miniature_sha256']) == 64)
        check('fiche : passe en production et note le dossier', read_json(os.path.join(d, 'fiche.json'))['statut'] == 'en_production')
        check('produire : ne refait pas une vidéo déjà en production', run('planifier', '--produire', 'Le Couloir Rouge')[0] == 1)
        check('produire sans nom : prend la suivante, ici incomplète donc refus', run('planifier', '--produire')[0] == 1)

        check('voix : plus aucun plafond nulle part (code, fiche, autorisation)',
              not hasattr(V, '_check_planning_cap') and 'plafond_caracteres' not in read_json(os.path.join(d, 'fiche.json')) and 'voix_plafond_caracteres' not in auth)
        check('produire : annonce les caractères de la voix, sans plafond', 'sans plafond' in out and 'caractères à envoyer' in out)
        # a very long script is not refused: the only gate left is the missing script / thumbnail
        run('planifier', '--ajouter', 'Long', '--date', '2026-11-13')
        dl = os.path.join(tmp, 'PLANNING', '2026-11-13_LONG')
        open(os.path.join(dl, 'script.txt'), 'w', encoding='utf-8').write(('Une phrase de plus.\n' * 3000))
        Image.new('RGB', (1080, 1920), (0, 0, 90)).save(os.path.join(dl, 'miniature.jpg'))
        check('script de 60 000 caractères : prêt, aucun refus', '13' in run('planifier')[1] and read_json(os.path.join(dl, 'fiche.json'))['statut'] == 'prevue'
              and not PL.Entry(dl).missing)

        code, out = run('planifier', '--terminer', 'Couloir')
        check('terminer : statut terminée', code == 0 and read_json(os.path.join(d, 'fiche.json'))['statut'] == 'terminee')
        check('liste : la vidéo terminée n\'est plus « ► »', '► 2026-11-12' in run('planifier')[1])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f'\n{len(OK)} contrôles réussis, {len(BAD)} échec(s)')
    sys.exit(1 if BAD else 0)


if __name__ == '__main__':
    main()
