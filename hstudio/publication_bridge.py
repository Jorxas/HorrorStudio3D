"""Prepare local renders in the independent Publication service. Never publishes."""
import os, json, hashlib, urllib.request, urllib.error
from . import paths

def config():
    try:
        with open(os.path.join(paths.CONFIG, 'publication.json'), encoding='utf-8') as stream:
            value = json.load(stream)
        return value if value.get('enabled') else None
    except (OSError, ValueError):
        return None

def status():
    value = config()
    return {'enabled': bool(value), 'publicUrl': value.get('publicUrl') if value else None}

def prepare(project, filename, language='fr'):
    conf = config()
    if not conf:
        raise ValueError('La régie Publication n’est pas configurée.')
    if language not in ('fr', 'en', 'de'):
        raise ValueError('Langue invalide.')
    root = os.path.realpath(project.p('renders'))
    media = os.path.realpath(project.p('renders', filename))
    if os.path.commonpath([root, media]) != root or not os.path.isfile(media) or not media.lower().endswith(('.mp4', '.mov', '.webm')):
        raise ValueError('Choisissez un rendu vidéo de ce projet.')
    metadata = project.read_json('metadata.json', {}) or {}
    platforms = metadata.get('platforms', {})
    tk = platforms.get('tiktok', {})
    yt = platforms.get('youtube_shorts', {})
    title = yt.get('title') or project.meta.get('name') or project.meta.get('title') or project.slug
    caption = tk.get('caption') or metadata.get('description') or title
    thumb = yt.get('thumbnail')
    if thumb and not os.path.isabs(thumb):
        thumb = project.p(thumb)
    if not thumb or not os.path.isfile(thumb):
        thumb = None
    payload = {'studio': 'horror', 'projectKey': project.slug + ':' + filename,
               'version': str(os.stat(media).st_mtime_ns) + '-' + hashlib.sha256((title+caption).encode()).hexdigest()[:12],
               'language': language, 'file': media, 'title': title, 'caption': caption,
               'description': yt.get('description') or metadata.get('description') or caption,
               'thumbnail': thumb, 'provenance': {'projectSlug': project.slug}}
    request = urllib.request.Request(conf['apiUrl'] + '/api/assets', data=json.dumps(payload).encode(),
                headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + conf['apiKey']}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return {**json.load(response), 'publicationUrl': conf['publicUrl'], 'published': False}
    except urllib.error.HTTPError as exc:
        try:
            message = json.load(exc).get('error', 'Préparation refusée.')
        except ValueError:
            message = 'La régie n’a pas répondu correctement.'
        raise ValueError(message) from None
    except urllib.error.URLError:
        raise ValueError('La régie Publication doit être démarrée.') from None
