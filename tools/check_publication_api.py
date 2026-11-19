"""Backend check of the publication panel: the real FastAPI app, no network, no key, nothing paid.

Builds a throw-away project in projects/, asks the API for it and checks that metadata.json carries the two
platform packs, then deletes it. An older project without `platforms` must still answer.

  python tools/check_publication_api.py        # exit 1 on any failure
"""
import os, sys, json, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from fastapi.testclient import TestClient
from hstudio import paths, director
from hstudio.web.server import app

FAIL = []
def check(n, ok, d=''):
    print(f"{'OK   ' if ok else 'ÉCHEC'} {n}" + (f'  ({d})' if d and not ok else '')); ok or FAIL.append(n)

SLUG = '_tmp_publication_check'

def main():
    d = os.path.join(paths.PROJECTS, SLUG)
    shutil.rmtree(d, ignore_errors=True); os.makedirs(d, exist_ok=True)
    ep = json.load(open(os.path.join(ROOT, 'examples', 'ne_mets_pas_pause_demo', 'episode.json'), encoding='utf-8'))
    meta = {'name': 'Check publication', 'style': 'console', 'series': 'NE METS PAS PAUSE', 'part_label': 'NIVEAU 1'}
    w = lambda f, o: json.dump(o, open(os.path.join(d, f), 'w', encoding='utf-8'), ensure_ascii=False)
    w('project.json', meta); w('episode.json', ep)
    md = director.metadata(meta, [{'text': 'x'}], ep, {'director': 'heuristic'}, log=lambda *a: None)
    w('metadata.json', md)
    try:
        c = TestClient(app)
        r = c.get('/')
        check('page servie (200)', r.status_code == 200, str(r.status_code))
        check('panneau publication présent dans la page', 'pubHtml(' in r.text and 'copier tout' in r.text)
        r = c.get(f'/api/projects/{SLUG}')
        check('API projet (200)', r.status_code == 200, str(r.status_code))
        pf = (r.json().get('metadata') or {}).get('platforms')
        check('API renvoie le bloc platforms', bool(pf and pf.get('youtube_shorts') and pf.get('tiktok')))
        check('API : titre YouTube et légende TikTok distincts', pf['youtube_shorts']['title'] != pf['tiktok']['caption'])
        check('API : choix A/B de l’épisode réel', [x['letter'] for x in pf['choices']] == ['A', 'B'], str(pf['choices']))
        w('metadata.json', {k: v for k, v in md.items() if k != 'platforms'})     # projet d'avant ce lot
        j2 = c.get(f'/api/projects/{SLUG}').json()
        check('ancien projet sans platforms : API répond quand même',
              j2['metadata'].get('platforms') is None and 'titles' in j2['metadata'])
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print('\n' + ('ÉCHECS : ' + ', '.join(FAIL) if FAIL else 'Tout est OK.'))
    return 1 if FAIL else 0

if __name__ == '__main__':
    sys.exit(main())
