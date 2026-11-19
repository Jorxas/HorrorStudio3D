"""Espace disque des projets : mesurer, libérer, supprimer pour de bon, corbeille.

Un projet pèse vite plusieurs Go (la vidéo finale, le dossier de travail du moteur, les aperçus). La suppression d'avant ne faisait que DÉPLACER le projet dans `corbeille/` :
l'espace n'était jamais rendu. Ici :
  * `clean(slug)`  libère les fichiers FABRICABLES (vidéos, travail du moteur, aperçus, mixage) et garde ce qui est à l'utilisateur (script, voix, calage, plans, réglages) ;
  * `delete(slug)` supprime le projet entièrement (définitif) ; `delete(slug, trash=True)` le met dans la corbeille (récupérable, ne libère rien) ;
  * `trash_*`      liste, vide ou restaure la corbeille.
Rien ne sort du dossier des projets ; un projet dont une tâche tourne n'est jamais touché."""
import glob, os, shutil, time
from . import paths, jobs

# Fichiers et dossiers d'un projet que le studio sait refaire (mesuré : le dossier `work/` seul pèse souvent 200 Mo à 1 Go).
GENERATED = ('work', 'renders', 'preview', 'preview_clips', 'preview_sheet.jpg', 'mix.wav', 'thumbnail_16x9.jpg', 'cover_9x16.jpg')
GENERATED_GLOBS = ('verify_*.json', 'qc_*.json', 'tts_alignment.json.tmp')
_CACHE = {'t': 0., 'v': None}


def trash_dir(): return os.path.realpath(os.path.join(paths.PROJECTS, '..', 'corbeille'))
def _root(): return os.path.realpath(paths.PROJECTS)


def _safe_dir(slug):
    if not slug or os.path.basename(slug) != slug or slug in ('.', '..'): raise ValueError('nom de projet invalide')
    d = os.path.realpath(os.path.join(_root(), slug))
    if os.path.dirname(d) != _root() or not os.path.isdir(d): raise FileNotFoundError('projet introuvable')
    return d


def _busy(slug):
    j = jobs.get(slug)
    if j and j.get('state') == 'running': raise RuntimeError(f"Une tâche est en cours sur ce projet ({j.get('name')}) : attends qu'elle finisse.")


def dir_size(path):
    total = 0
    try:
        with os.scandir(path) as it:
            for e in it:
                try:
                    if e.is_symlink(): continue
                    total += dir_size(e.path) if e.is_dir(follow_symlinks=False) else e.stat(follow_symlinks=False).st_size
                except OSError: pass
    except OSError: pass
    return total


def _generated_paths(d):
    out = [os.path.join(d, g) for g in GENERATED if os.path.exists(os.path.join(d, g))]
    for pat in GENERATED_GLOBS: out += glob.glob(os.path.join(d, pat))
    return out


def sizes(max_age=30.):
    """{slug: {"total": octets, "generated": octets}} (mis en cache quelques secondes : parcourir des Go de fichiers n'est pas gratuit)"""
    if _CACHE['v'] is not None and time.time() - _CACHE['t'] < max_age: return _CACHE['v']
    out = {}
    if os.path.isdir(_root()):
        for slug in sorted(os.listdir(_root())):
            d = os.path.join(_root(), slug)
            if not os.path.isdir(d) or not os.path.isfile(os.path.join(d, 'project.json')): continue          # seuls les vrais projets (pas les dossiers d'essai ni le cache)
            gen = sum(dir_size(p) if os.path.isdir(p) else os.path.getsize(p) for p in _generated_paths(d))
            out[slug] = {'total': dir_size(d), 'generated': gen}
    _CACHE.update(t=time.time(), v=out); return out


def _forget(): _CACHE['t'] = 0.


def clean(slug):
    """libère les fichiers fabricables ; -> octets rendus"""
    d = _safe_dir(slug); _busy(slug); freed = 0
    for p in _generated_paths(d):
        freed += dir_size(p) if os.path.isdir(p) else os.path.getsize(p)
        shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    _forget(); return freed


def delete(slug, trash=False):
    """supprime le projet (définitif) ou le met à la corbeille ; -> octets rendus (0 pour la corbeille)"""
    d = _safe_dir(slug); _busy(slug); size = dir_size(d)
    if trash:
        os.makedirs(trash_dir(), exist_ok=True); shutil.move(d, os.path.join(trash_dir(), f'{slug}__{int(time.time())}')); _forget(); return 0
    shutil.rmtree(d); _forget(); return size


def trash_list():
    t = trash_dir(); out = []
    if os.path.isdir(t):
        for n in sorted(os.listdir(t)):
            p = os.path.join(t, n)
            if os.path.isdir(p): out.append({'name': n, 'size': dir_size(p), 'slug': n.rsplit('__', 1)[0] if '__' in n else n.rsplit('_', 1)[0]})
    return out


def trash_empty():
    freed = 0; t = trash_dir()
    if os.path.isdir(t):
        for n in os.listdir(t):
            p = os.path.join(t, n)
            if os.path.isdir(p): freed += dir_size(p); shutil.rmtree(p)
    return freed


def trash_restore(name):
    t = trash_dir(); src = os.path.realpath(os.path.join(t, name))
    if os.path.dirname(src) != t or not os.path.isdir(src): raise FileNotFoundError('élément introuvable dans la corbeille')
    slug = name.rsplit('__', 1)[0] if '__' in name else name.rsplit('_', 1)[0]; dst = os.path.join(_root(), slug); k = 2
    while os.path.exists(dst): dst = os.path.join(_root(), f'{slug}_{k}'); k += 1
    shutil.move(src, dst); _forget(); return os.path.basename(dst)
