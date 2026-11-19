"""Backend check of the one-click path: the real FastAPI app, no network, no key, nothing paid.

Only the API surface is exercised here, with no render at all (the full chain down to the MP4 is
`tools/check_oneclick.py`). What this proves:

- `POST /api/story/project` turns a brief into a real project and refuses a bad brief with a French reason ;
- `GET  /api/projects/<slug>/oneclick` answers the state of every stage, read on the project's files ;
- `POST /api/projects/<slug>/run/oneclick` refuses to start when something is missing, with the reason, rather
  than failing in the middle of the render ;
- the path never touches another project, and never writes outside the project it was given ;
- nothing is launched by `run: false`, and a second job on the same project is refused (409).

Everything is written in a throw-away projects folder and deleted at the end.

  python tools/check_oneclick_api.py         # exit 1 on any failure
"""
import os, sys, json, shutil, tempfile
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(tempfile.gettempdir(), 'hstudio_check_oneclick_api')
os.environ['HSTUDIO_PROJECTS'] = OUT                     # avant tout import de hstudio.paths

from fastapi.testclient import TestClient                # noqa: E402
from hstudio.web.server import app                       # noqa: E402
from hstudio import oneclick as OC                       # noqa: E402

FAIL = []


def check(n, ok, d=''):
    print(('OK   ' if ok else 'ÉCHEC') + ' ' + n + (('  (' + str(d) + ')') if d and not ok else ''))
    if not ok: FAIL.append(n)


BRIEF = dict(genre='horror', duration_s=40, voice_mode='voice', engine='pixel3d', n_choices=2, seed=4,
             series='Essai API', part_label='PARTIE 1', premise='une porte au mauvais étage')


def main():
    c = TestClient(app)
    r = c.get('/')
    check('page servie (200)', r.status_code == 200, r.status_code)
    check('le panneau du parcours est dans la page', 'Parcours en un clic' in r.text and 'oc-steps' in r.text)
    check('le formulaire de brief est dans la page', "D'un brief à la vidéo" in r.text and 'runBrief(' in r.text)
    check('les étapes manuelles restent dans la page', "run('align')" in r.text and "run('render'" in r.text)

    o = c.get('/api/story/options')
    check('les valeurs du brief viennent du backend', o.status_code == 200 and 'horror' in o.json()['genres']
          and [s['key'] for s in o.json()['stages']] == OC.KEYS, o.text[:120])

    # ---- un brief devient un projet, rien n'est lancé
    r = c.post('/api/story/project', json={'brief': BRIEF, 'name': 'API un clic', 'voice_mode': 'draft',
                                           'opts': {'aspects': ['9:16']}, 'run': False})
    check('brief accepté (200)', r.status_code == 200, r.text[:200])
    d = r.json(); slug = d.get('slug')
    check('le projet est créé avec le bon moteur', d.get('style') == 'pixel3d', json.dumps(d.get('style')))
    check('les deux choix sont annoncés', d.get('choices') == ['A', 'B'], json.dumps(d.get('choices')))
    check('le générateur du plan est dit', d.get('generator') == 'mock', json.dumps(d.get('generator')))
    check('rien n\'est lancé sans « run »', not d.get('started') and not (c.get('/api/projects/' + slug + '/job').json() or {}).get('name'))
    check('l\'état du parcours arrive avec la réponse', d['plan']['next'] == 'voice', json.dumps(d['plan']['next']))

    # ---- l'état, lu sur les fichiers
    p = c.get('/api/projects/' + slug + '/oneclick?aspects=9:16').json()
    check('état du parcours (9 étapes)', [s['key'] for s in p['stages']] == OC.KEYS, json.dumps([s['key'] for s in p['stages']]))
    check('le script et la mise en scène sont déjà faits',
          {s['key'] for s in p['stages'] if s['done']} == {'script', 'direct'}, json.dumps([s['key'] for s in p['stages'] if s['done']]))
    check('rien ne bloque le départ', not p['problems'], '; '.join(p['problems'])[:160])
    check('la voix annoncée est la voix de brouillon', p['voice_mode'] == 'draft', p['voice_label'])
    # Legacy demo metadata must not select a paid voice provider during resume.
    legacy = OC.P.Project(slug)
    saved = dict(legacy.meta)
    try:
        legacy.meta.pop('voice_mode', None)
        legacy.meta['voice'] = 'brouillon'
        legacy.save()
        old = c.get('/api/projects/' + slug + '/oneclick?aspects=9:16').json()
        check('ancienne démo : le babillage reste annoncé comme brouillon',
              old['voice_mode'] == 'draft' and 'brouillon' in old['voice_label'], old['voice_label'])
        with patch.object(OC.P, 'step_draft_voice') as draft, patch.object(OC.P, 'step_voice') as paid:
            OC._run_voice(legacy, {}, {}, lambda *a: None)
            check('ancienne démo : la reprise ne choisit pas ElevenLabs', draft.called and not paid.called)
        legacy.meta['voice_mode'] = ''
        check('un choix ElevenLabs explicite prime sur le marqueur historique', OC._voice_mode(legacy) == '')
        legacy.meta['voice_mode'] = 'local'
        check('un choix audio local explicite prime sur le marqueur historique', OC._voice_mode(legacy) == 'local')
    finally:
        legacy.meta = saved
        legacy.save()
    p2 = c.get('/api/projects/' + slug + '/oneclick?aspects=9:16,16:9').json()
    check('demander deux formats ajoute le rendu et le QC des deux', p2['aspects'] == ['9:16', '16:9'], json.dumps(p2['aspects']))
    p3 = c.get('/api/projects/' + slug + '/oneclick?aspects=4:3').json()
    check('un format inconnu retombe sur 9:16', p3['aspects'] == ['9:16'], json.dumps(p3['aspects']))

    # ---- les refus, en français, avant de démarrer
    r = c.post('/api/story/project', json={'brief': dict(BRIEF, genre='inconnu', n_choices=7)})
    check('un brief faux est refusé (400) avec la raison', r.status_code == 400 and 'genre inconnu' in r.json()['detail'], r.text[:200])
    before = sorted(os.listdir(OUT))
    r = c.post('/api/story/project', json={'brief': dict(BRIEF, duration_s=2)})
    check('une durée hors bornes est refusée (400)', r.status_code == 400 and 'durée' in r.json()['detail'], r.text[:200])
    check('un brief refusé ne laisse aucun projet derrière lui', sorted(os.listdir(OUT)) == before, str(set(os.listdir(OUT)) - set(before)))

    empty = c.post('/api/projects', json={'name': 'Vide API', 'style': 'pixel3d'}).json()['slug']
    r = c.post('/api/projects/' + empty + '/run/oneclick', json={'aspects': ['9:16']})
    check('un projet vide est refusé (400) avant tout travail',
          r.status_code == 400 and 'script est vide' in r.json()['detail'], r.text[:200])
    check('le refus nomme aussi la voix manquante', 'ElevenLabs' in r.json()['detail'], r.text[:200])
    check('rien n\'a été écrit dans le projet vide',
          not os.path.exists(os.path.join(OUT, empty, 'voice.mp3')) and not os.path.exists(os.path.join(OUT, empty, OC.STATE_FILE)))
    r = c.post('/api/projects/' + slug + '/run/inconnue', json={})
    check('une étape inconnue est refusée (404)', r.status_code == 404, r.status_code)
    r = c.get('/api/projects/_nexistepas_/oneclick')
    check('un projet inconnu est refusé (404)', r.status_code == 404, r.status_code)

    # ---- le parcours ne touche pas aux autres projets
    other = c.post('/api/story/project', json={'brief': dict(BRIEF, engine='console', seed=9), 'name': 'Autre',
                                               'voice_mode': 'draft', 'run': False}).json()['slug']
    check('deux briefs donnent deux projets distincts', other != slug, other)
    snap = {f: os.path.getmtime(os.path.join(OUT, other, f)) for f in os.listdir(os.path.join(OUT, other))}
    c.get('/api/projects/' + slug + '/oneclick?aspects=9:16')
    check('consulter l\'état d\'un projet ne touche pas l\'autre',
          snap == {f: os.path.getmtime(os.path.join(OUT, other, f)) for f in os.listdir(os.path.join(OUT, other))})
    check('le moteur du second projet est bien CONSOLE 2D',
          json.load(open(os.path.join(OUT, other, 'project.json'), encoding='utf-8'))['style'] == 'console')

    # ---- une tâche à la fois par projet
    import hstudio.jobs as J
    J.JOBS[slug] = J.Job(slug, 'Tâche de test')             # une tâche en cours, sans rien exécuter
    r = c.post('/api/projects/' + slug + '/run/oneclick', json={'aspects': ['9:16']})
    check('une deuxième tâche sur le même projet est refusée (409)', r.status_code == 409, r.status_code)
    J.JOBS.pop(slug, None)

    # ---- aucun fournisseur d'IA n'est appelé par le gabarit hors ligne
    # (les sockets ne sont pas coupées ici : TestClient a besoin des siennes. La preuve « sockets coupées » sur
    #  tout le parcours est dans tools/check_oneclick.py, qui n'utilise pas de client HTTP.)
    from hstudio.director import providers
    real = providers.call
    def refuse(*a, **k): raise AssertionError('un fournisseur d\'IA a été appelé par le parcours hors ligne')
    providers.call = refuse
    try:
        r = c.post('/api/story/project', json={'brief': dict(BRIEF, seed=11), 'voice_mode': 'draft'})
        check('le gabarit « mock » n\'appelle aucun fournisseur d\'IA', r.status_code == 200, r.text[:200])
        r = c.get('/api/projects/' + slug + '/oneclick?aspects=9:16')
        check('consulter l\'état n\'appelle aucun fournisseur d\'IA', r.status_code == 200, r.text[:200])
    finally:
        providers.call = real


if __name__ == '__main__':
    shutil.rmtree(OUT, ignore_errors=True); os.makedirs(OUT, exist_ok=True)
    print('Dossier de test : ' + OUT)
    try: main()
    finally: shutil.rmtree(OUT, ignore_errors=True)
    print()
    if FAIL:
        print(str(len(FAIL)) + ' ÉCHEC(S) : ' + ', '.join(FAIL[:10])); sys.exit(1)
    print('Tout est bon.')
