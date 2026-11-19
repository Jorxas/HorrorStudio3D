"""Director: narration lines -> episode JSON (shots), with an AI provider or the offline rules."""
import json
from . import prompts, providers, heuristic
from .validate import validate

def _compact_shots(shots, n=6):
    return [{k: v for k, v in s.items() if k in ('lines', 'set', 'camera', 'actors', 'state')} for s in shots[-n:]]

def direct(project, lines, settings, log=print, raw_out=None):
    """raw_out (list): receives the episode as written by the director, before the validator repairs it (capability audit)"""
    style = project.get('style', 'pixel3d')
    keep = (lambda e: raw_out.append(json.loads(json.dumps(e)))) if raw_out is not None else (lambda e: None)
    provider = project.get('director') or settings.get('director', 'heuristic')
    if provider == 'heuristic' and project.get('cast'):             # library characters: the acting layer, no AI
        from . import scene
        ep = scene.direct(lines, project); keep(ep)
        ep, W = validate(ep, len(lines), style)
        return ep, W, 'heuristic (acteurs)'
    if provider == 'heuristic':
        ep = heuristic.direct(lines, project); keep(ep)
        ep, W = validate(ep, len(lines), style)
        return ep, W, 'heuristic'
    system = prompts.system_prompt(style)
    chunk = int(settings.get('director_chunk_lines', 200 if provider in ('claude', 'gemini') else 30))
    try:
        if len(lines) <= chunk:
            try:
                txt = providers.call(provider, settings, system, prompts.user_prompt(project, lines), log=log)
                ep = providers.parse_json(txt)
            except providers.ProviderError as e:
                if str(e) != 'TRUNCATED': raise
                chunk = 25; ep = None
        else: ep = None
        if ep is None:
            log(f'Mise en scène par morceaux de {chunk} lignes.')
            plan = providers.parse_json(providers.call(provider, settings, system, prompts.user_prompt(project, lines) + '\n\n' + prompts.PLAN_INSTRUCTION, log=log))
            plan.pop('shots', None); shots = []
            for a in range(0, len(lines), chunk):
                b = min(len(lines) - 1, a + chunk - 1)
                part = providers.parse_json(providers.call(provider, settings, system,
                                            prompts.user_prompt(project, lines, (a, b, _compact_shots(shots)), plan), log=log))
                shots += part.get('shots', []) if isinstance(part, dict) else []
                log(f'  lignes {a}-{b} : {len(shots)} plans au total')
            ep = dict(plan); ep['shots'] = shots
    except Exception as e:
        log(f'Mise en scène IA impossible ({e}). Utilisation de la mise en scène automatique.')
        if project.get('cast'):
            from . import scene
            ep = scene.direct(lines, project)
        else: ep = heuristic.direct(lines, project)
        provider = 'heuristic'
    keep(ep)
    ep, W = validate(ep, len(lines), style)
    return ep, W, provider

def base_metadata(project, lines, episode, settings, log=print):
    """the neutral packaging (titles / description / hashtags / thumbnail_text / tags), platform-agnostic"""
    provider = project.get('director') or settings.get('director', 'heuristic')
    story = '\n'.join(l['text'] for l in lines)
    user = (f"SERIES: {project.get('series', '')}\nEPISODE: {project.get('part_label', '')}\nSTYLE: {project.get('style')}\n"
            f"SUMMARY: {episode.get('summary', '')}\nSTORY:\n{story}")
    if provider != 'heuristic':
        try:
            return providers.parse_json(providers.call(provider, settings, prompts.METADATA_SYSTEM, user, log=log, max_tokens=8000))
        except Exception as e:
            log(f'Titres IA impossibles ({e}) : version automatique.')
    series = project.get('series', '') or 'Histoire'
    part = project.get('part_label', '')
    genre = episode.get('genre') or project.get('genre') or ('horror' if episode.get('music', 'horror') == 'horror' else 'other')
    if genre != 'horror':
        tags = {'comedy': ['comedie', 'humour', 'drole'], 'romance': ['romance', 'amour', 'histoiredamour'], 'adventure': ['aventure', 'quete', 'fantasy'],
                'mystery': ['mystere', 'enquete', 'suspense'], 'sad': ['emotion', 'histoiretriste', 'drame'], 'action': ['action', 'poursuite', 'suspense']}.get(genre, ['histoire', 'aventure', 'emotion'])
        return {'titles': [f'{series} - {part} : à toi de choisir', f'{series} {part} | Histoire interactive (choisis A ou B)', f'Et toi, tu aurais fait quoi ? ({series} {part})'],
                'description': f"{episode.get('summary', '')}\n\nUne histoire interactive en pixel 3D où c'est toi qui choisis la suite.\n\nA ou B ? Vote en commentaire !",
                'hashtags': ['histoireinteractive', 'choisistonhistoire'] + tags + ['pixelart', 'pixel3d', 'animation', 'storytime', 'histoire', 'aoub', 'fyp', 'pourtoi', 'shorts'][:13 - len(tags)],
                'thumbnail_text': ['A OU B ?', 'À TOI', 'DE CHOISIR'], 'tags': ['histoire interactive', 'choisis ton histoire', 'pixel art'] + tags}
    kw = [m.get('keywords', [''])[0] for m in episode.get('lines', {}).values() if m.get('keywords')]
    top = max(set(kw), key=kw.count).upper() if kw else 'LA PORTE'
    return {'titles': [f'{series} - {part} : ne regarde pas derrière toi', f'{series} {part} | Histoire d\'horreur interactive (choisis A ou B)',
                       f'Tu n\'aurais jamais dû faire ça... ({series} {part})'],
            'description': f"{episode.get('summary', '')}\n\nUne histoire d'horreur interactive où c'est toi qui choisis la suite.\n\nA ou B ? Vote en commentaire !",
            'hashtags': ['horreur', 'histoiredhorreur', 'creepypasta', 'choisistonhistoire', 'histoireinteractive', 'pixelart', 'indiehorror',
                         'horrorstory', 'scary', 'peur', 'frissons', 'mystere', 'retrogaming', 'animation', 'fyp'],
            'thumbnail_text': [top[:12], 'NE REGARDE', 'PAS'], 'tags': ['horreur', 'histoire', 'creepypasta']}

def metadata(project, lines, episode, settings, log=print):
    """`metadata.json`: the neutral keys as before + `platforms` (YouTube Shorts title/description vs TikTok caption).

    Additive and backwards compatible: every key written until now keeps its meaning and its value, `platforms` is
    computed offline from the episode (see `hstudio/publish.py`), so an old project re-run gives the same titles.
    """
    md = base_metadata(project, lines, episode, settings, log=log) or {}
    try:
        from .. import publish
        md['platforms'] = publish.pack(project, episode, md, lines)
    except Exception as e:                        # packaging is never worth losing the titles already obtained
        log(f'Déclinaison par plateforme impossible ({e}) : métadonnées communes seules.')
    return md
