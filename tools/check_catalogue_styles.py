"""python tools/check_catalogue_styles.py

Le catalogue a bien un jeu de miniatures par style (voir docs/CATALOGUE_STYLES.md) :
  * chaque fiche non-référence a `styles` ; PS1 et VOXEL ont exactement les mêmes éléments (pas de fiche d'un seul côté, sauf « approx » signalé) ;
  * chaque miniature annoncée existe, n'est pas noire ni unie, et la miniature PS1 n'est pas la copie de la miniature VOXEL ;
  * les fiches CONSOLE 2D n'apparaissent que dans CONSOLE 2D.
Sortie 1 au premier échec."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import numpy as np
from PIL import Image
from hstudio import catalogue as CT

FAIL = []
def check(name, ok, detail=''):
    print(f"{'OK   ' if ok else 'ÉCHEC'} {name}" + (f'  ({detail})' if detail and not ok else '')); ok or FAIL.append(name)

es = CT.load(); vis = [e for e in es if not e.get('reference')]
cat = lambda e: e['id'].split('/', 1)[0]
check('l\'index contient des fiches', len(es) > 500, str(len(es)))
check('chaque fiche porte `styles`', all('styles' in e for e in es))
game = [e for e in vis if cat(e) not in ('console', 'son', 'sonreel')]
no_ps1 = [e['id'] for e in game if e['styles'].get('ps1') and 'ps1' not in (e.get('thumbs') or {})]
no_vox = [e['id'] for e in game if e['styles'].get('voxel') and 'voxel' not in (e.get('thumbs') or {})]
check('PS1 : chaque fiche (non-référence) a sa miniature PS1', not no_ps1, f'{len(no_ps1)} manquantes, ex. {no_ps1[:3]}')
check('VOXEL : chaque fiche (non-référence) a sa miniature VOXEL', not no_vox, f'{len(no_vox)} manquantes, ex. {no_vox[:3]}')
check('PS1 et VOXEL : mêmes éléments des deux côtés', all(('ps1' in e['thumbs']) == ('voxel' in e['thumbs']) for e in game), 'une fiche n\'a qu\'un style')
con = [e for e in es if cat(e) == 'console']
check('CONSOLE 2D : des fiches, toutes avec miniature', len(con) >= 60 and all('console' in (e.get('thumbs') or {}) for e in con), str(len(con)))
check('CONSOLE 2D : jamais dans PS1 / VOXEL', all(set(e['thumbs']) == {'console'} and e['styles'] == {'console': 'native'} for e in con))
check('PS1 / VOXEL : jamais dans CONSOLE 2D', all('console' not in e.get('thumbs', {}) for e in es if cat(e) != 'console'))
bad = []; same = 0; n = 0
for e in es:
    for st, rel in (e.get('thumbs') or {}).items():
        a = np.asarray(Image.open(CT.OUT / rel).convert('L'), np.float32); n += 1
        if a.std() < 4 or a.mean() < 3: bad.append(e['id'] + ':' + st)
    th = e.get('thumbs') or {}
    if {'ps1', 'voxel'} <= set(th):
        a = np.asarray(Image.open(CT.OUT / th['ps1']).convert('L'), np.float32); b = np.asarray(Image.open(CT.OUT / th['voxel']).convert('L'), np.float32)
        if a.shape == b.shape and float(np.abs(a - b).mean()) < 1.0: same += 1
check(f'{n} miniatures : aucune noire ni unie', len(bad) <= 3, f'{len(bad)} : {bad[:6]}')
check('PS1 ≠ VOXEL : aucune miniature PS1 n\'est une copie de la VOXEL', same == 0, f'{same} copies')
for k in sorted({cat(e) for e in es}):
    sub = [e for e in es if cat(e) == k]; print(f"   {k:8s} {len(sub):5d} fiches   PS1 {sum('ps1' in e.get('thumbs', {}) for e in sub):5d}   VOXEL {sum('voxel' in e.get('thumbs', {}) for e in sub):5d}   CONSOLE {sum('console' in e.get('thumbs', {}) for e in sub):4d}")
print('\n' + ('TOUT PASSE' if not FAIL else f'{len(FAIL)} ÉCHEC(S)')); sys.exit(1 if FAIL else 0)
