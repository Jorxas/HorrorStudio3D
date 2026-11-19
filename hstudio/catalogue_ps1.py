"""Miniatures PS1 du catalogue : chaque fiche est peinte par le moteur PIXEL 3D (lancer de rayons sur boîtes, bas-pixel), même cadrage et même nom de fichier que la version VOXEL.

Une fiche devient une « spec » légère (dict sérialisable) ; `render(spec)` en fait une image 320x240 ; `build(entries, ...)` les peint en parallèle (pool de processus),
uniquement celles qui manquent (`force=True` : toutes). Un élément absent du style PS1 (`styles.of_entry(e)['ps1']` vide) n'a pas de miniature PS1.

Types de spec :
  prop   {'t': 'prop',  'kind': 'bed', 'ground': 'concrete'}                      décor natif PS1 (sets.prop_boxes)
  elem   {'t': 'elem',  'kind': 'craft:oak_tree' | 'vox:bank/nom', 'p': {...}}     élément né dans VOXEL, converti par ps1_elements
  place  {'t': 'place', 'name': 'forest'}                                          lieu complet, un personnage au point de départ
  cast   {'t': 'cast',  'cast': {...}, 'shot': 'full', 'face': 'neutral'}          personnage / créature / visage en plan serré
"""
import json, os, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'catalogue'
DIR = 'thumbs_ps1'
W, H = 320, 240
NATURE = ('Arbres', 'Plantes', 'Champignons', 'Cultures', 'Roches', 'Minerais', 'Blocs')


def slug(s): return re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_')


def thumb_rel(entry_id): return f'{DIR}/{slug(entry_id)}.jpg'


# ------------------------------------------------------------------ spec d'une fiche
def spec_of(e, groups=None):
    """fiche de catalogue -> spec de rendu PS1, ou None (l'élément n'a pas de version PS1 ou n'a pas de miniature d'image)"""
    from . import styles
    if styles.of_entry(e).get('ps1') in (None, ''): return None
    i = str(e.get('id', '')); pre = i.split('/', 1)[0]; key = e.get('key', '')
    if pre == 'decor': return {'t': 'prop', 'kind': key, 'ground': 'concrete'}
    if pre == 'lieu': return {'t': 'place', 'name': key}
    if pre == 'visage': return {'t': 'cast', 'cast': {'preset': 'npc', 'variant': 2}, 'shot': 'close', 'face': key}
    if pre == 'craft':
        nm, sd = key.split(':'); return {'t': 'elem', 'kind': 'craft:' + nm, 'p': {'seed': int(sd)}, 'ground': 'grass' if e.get('group') in NATURE else 'dirt'}
    if pre == 'vox':
        p = {'height': 2.0} if e.get('category') == 'Personnages' else {}
        return {'t': 'elem', 'kind': 'vox:' + key, 'p': p, 'ground': 'dirt'}
    if pre in ('look', 'monstre'):
        c = e.get('cast') or ({'b_look': key} if pre == 'look' else {'kind': 'creature', 'archetype': key}); return {'t': 'cast', 'cast': dict(c), 'shot': 'full' if pre == 'look' else 'wide'}
    if pre == 'perso':
        g, label = key.split('/', 1); c = (groups or {}).get(g, {}).get(label)
        if c is None: return None
        c = dict(c)
        if c.get('kind') == 'animal':                                        # PS1 : le « kind » est le nom de l'animal
            a = c.pop('animal'); c.pop('kind'); c = dict(c, kind=a)
        return {'t': 'cast', 'cast': c, 'shot': 'full' if g != 'hold' else 'medium_full'}
    return None


def char_groups():
    """{'outfits': {nom: cast}, ...} de tools/b_chars_sheet.groups() (même source que les miniatures VOXEL)"""
    sys.path.insert(0, str(ROOT / 'tools'))
    import b_chars_sheet as CS
    return {g: {l: {k: v for k, v in c.items() if v is not None} for l, c in items} for g, items in CS.groups().items()}


# ------------------------------------------------------------------ rendu (dans un processus de travail)
def _bounds(boxes):
    import numpy as np
    lo = np.min([b.lo for b in boxes], 0); hi = np.max([b.hi for b in boxes], 0); return lo, hi


def _free_camera(boxes):
    lo, hi = _bounds(boxes); c = (lo + hi) / 2; r = float((hi - lo).max()) / 2 + .15
    pos = [round(float(c[0] - r * 1.0), 2), round(float(c[1] + r * .7 + .35), 2), round(float(c[2] - r * 3.0 - .8), 2)]
    look = [round(float(c[0]), 2), round(float(c[1] * .9), 2), round(float(c[2]), 2)]
    return {'preset': 'free', 'keys': [{'pos': pos, 'look': look, 'fov': 42}]}


def _set(ground, props): return {'type': 'room', 'outdoor': True, 'ground': ground, 'sky': 'day', 'props': props}


def _cast_camera(shot):
    """caméra libre devant l'acteur posé en (0, 5) : le plan « full » cadre un corps entier (les grandes créatures comprises), « close » le visage"""
    if shot == 'close': pos, look, fov = [0., 1.62, 3.3], [0., 1.6, 5.], 40
    elif shot == 'medium_full': pos, look, fov = [.3, 1.25, 0.8], [0., 1.0, 5.], 46
    elif shot == 'wide': pos, look, fov = [.6, 1.7, -1.3], [0., 1.3, 5.], 46
    else: pos, look, fov = [.4, 1.4, 0.2], [0., 1.05, 5.], 46
    return {'preset': 'free', 'keys': [{'pos': pos, 'look': look, 'fov': fov}]}


def _episode(spec):
    t = spec['t']
    if t in ('prop', 'elem'):
        if t == 'prop':
            from .engines.pixel3d import sets as S
            kind = spec['kind']; boxes = S.prop_boxes(kind, {}); prop = {'type': kind, 'at': [0, 0], 'id': 'p'}
        else:
            from .engines.pixel3d import ps1_elements as PE
            kind = spec['kind']; p = dict(spec.get('p') or {}); boxes = PE.boxes(kind, p); prop = dict({'type': kind, 'at': [0, 0], 'id': 'p'}, **p)
        if not boxes: raise ValueError('aucune boîte')
        return {'engine_version': 1, 'default_set': 's', 'sets': {'s': _set(spec.get('ground', 'concrete'), [prop])}, 'cast': {'x': {'preset': 'npc'}},
                'shots': [{'lines': [0, 0], 'actors': [], 'actions': [], 'camera': _free_camera(boxes)}]}
    if t == 'place':
        from .engines.pixel3d import sets as S, places as PL
        n = spec['name']; st = PL.START.get(n)
        if st is None:
            ss = S.make_set(n, {'type': n})
            if getattr(ss, 'base', None) is None: ss.build()
            a = ss.anchors; st = next((a[k] for k in ('start', 'path.start', 'sidewalk.left', 'shore', 'center', 'center.center') if k in a), None)
            if st is None: st = next((v for k, v in a.items() if k.endswith('.center')), next(iter(a.values()), (0., 0.)))
        x, z = round(float(st[0]), 2), round(float(st[1]), 2)                    # la caméra se tient au point de départ du lieu (à l'intérieur : au centre de la pièce) et regarde vers l'intérieur
        return {'engine_version': 1, 'default_set': n, 'sets': {n: {'type': n}}, 'cast': {'x': {'preset': 'npc', 'variant': 2}},
                'shots': [{'lines': [0, 0], 'actors': [], 'actions': [], 'camera': {'preset': 'free', 'keys': [{'pos': [x, 1.55, z], 'look': [x, 1.35, round(z + 10. * spec.get('dir', 1), 2)], 'fov': 72}]}}]}
    if t == 'cast':
        return {'engine_version': 1, 'default_set': 's', 'sets': {'s': _set('concrete', [])}, 'cast': {'x': spec['cast']},
                'shots': [{'lines': [0, 0], 'actors': [{'id': 'x', 'at': [0., 5.], 'facing': '-z', 'face': spec.get('face', 'neutral')}], 'actions': [], 'camera': _cast_camera(spec.get('shot', 'full'))}]}
    raise ValueError(f'spec inconnue : {t}')


def render(spec):
    """spec -> image PIL 320x240 (bas-pixel agrandi proprement) ; un lieu qui regarde un mur (image presque unie) est retourné de l'autre côté"""
    im = _render(spec)
    if spec.get('t') == 'place' and spec.get('dir', 1) == 1:
        import numpy as np
        if float(np.asarray(im, np.float32).std()) < 14.:
            b = _render(dict(spec, dir=-1))
            if float(np.asarray(b, np.float32).std()) > float(np.asarray(im, np.float32).std()) + 4: return b
    return im


def _render(spec):
    from PIL import Image
    from .pipeline import make_engine
    ep = _episode(spec); lines = [{'who': 'x', 'text': 'x', 'start': 0., 'end': 1.}]
    eng = make_engine('pixel3d', ep, lines, {}, 1.5, '16:9'); a = eng.render_lowres(.5)[0]
    im = Image.fromarray(a).convert('RGB'); iw, ih = im.size
    im = im.resize((iw * 2, ih * 2), Image.NEAREST).resize((int(round(iw * H / ih)), H), Image.LANCZOS)          # 16:9 -> hauteur 240, puis recadrage central en 4:3
    x0 = (im.width - W) // 2; im = im.crop((x0, 0, x0 + W, H))
    import numpy as np
    m = float(np.asarray(im).mean())
    if m < 45.:                                                              # scène de nuit : exposition automatique de la miniature (le rendu du film, lui, reste sombre)
        k = min(4., 70. / max(m, 4.)); im = Image.fromarray(np.clip(np.asarray(im, np.float32) * k, 0, 255).astype(np.uint8))
    return im


def _job(args):
    """(id, spec, chemin de sortie) -> (id, None) ou (id, message d'erreur) ; tourne dans un processus de travail"""
    eid, spec, out = args
    try:
        sys.path.insert(0, str(ROOT)); os.environ.setdefault('PYTHONUTF8', '1')
        im = render(spec); Path(out).parent.mkdir(parents=True, exist_ok=True); im.save(out, quality=84); return eid, None
    except Exception as ex: return eid, f'{type(ex).__name__}: {str(ex)[:140]}'


def build(entries, force=False, log=print, workers=None, only=None):
    """peint les miniatures PS1 manquantes ; renvoie {'ok': n, 'failed': {id: message}, 'skipped': n, 'seconds': s}"""
    import multiprocessing as mp
    t0 = time.time(); groups = None; jobs = []; skipped = 0
    for e in entries:
        if only and str(e['id']).split('/', 1)[0] not in only: continue
        if str(e['id']).startswith(('son/', 'sonreel/', 'console/')): continue
        if str(e['id']).startswith('perso/') and groups is None: groups = char_groups()
        sp = spec_of(e, groups)
        if sp is None: skipped += 1; continue
        out = OUT / thumb_rel(e['id'])
        if force or not out.exists(): jobs.append((e['id'], sp, str(out)))
    ok, failed = 0, {}
    if jobs:
        n = workers or max(1, min(16, (os.cpu_count() or 4) - 2)); log(f'PS1 : {len(jobs)} miniatures à peindre sur {n} processus')
        ctx = mp.get_context('spawn'); done = 0
        with ctx.Pool(n) as pool:
            for eid, err in pool.imap_unordered(_job, jobs, chunksize=4):
                done += 1
                if err: failed[eid] = err
                else: ok += 1
                if done % 100 == 0: log(f'  PS1 {done}/{len(jobs)} ({time.time() - t0:.0f} s)')
    log(f'PS1 : {ok} peintes, {len(failed)} en échec, {skipped} sans version PS1 ({time.time() - t0:.0f} s)')
    return dict(ok=ok, failed=failed, skipped=skipped, seconds=round(time.time() - t0, 1))
