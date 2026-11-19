"""Publication pack: one episode -> packaging per platform (YouTube Shorts title/description vs TikTok caption).

`director.metadata()` already writes `titles` / `description` / `hashtags` / `thumbnail_text` / `tags` (one neutral
set for every platform) and `thumbnail.py` already draws the 1280x720 miniature and the 1080x1920 cover with the
font of the engine. This module adds, on top of that and without touching it, what the two platforms really need
differently for the SAME episode:

- YouTube Shorts: a title (hard limit 100 chars, kept under 70 so nothing is cut in the feed), a description in
  paragraphs with the series/episode recall and the vote call, few hashtags (YouTube shows only the first three),
  and the YouTube `tags` field.
- TikTok: no title field at all, one caption that must open with the hook, carry the episode number inline and end
  with the hashtags (no `tags` field, no "#shorts").

Everything is derived from what is written in the episode (summary, `ui.choice`, `hud`) and in the project
(`series`, `part_label`, `previous_choice`): no invented promise, and `_declickbait` strips the usual lying
formulas if a provider wrote some. Standard library only, deterministic (same input -> same JSON), no API call.

Entry point: `pack(project, episode, base, lines=None)` -> the `platforms` block of `metadata.json`.
"""
import re
import unicodedata

YT_TITLE_MAX = 100          # YouTube hard limit
YT_TITLE_SOFT = 70          # kept shorter: beyond that the feed cuts the title
TIKTOK_CAPTION_SOFT = 150   # the caption is folded after ~150 chars in the app
LETTERS = ('A', 'B', 'C', 'D')

# the canned hooks of the offline director (`director.base_metadata`): the same sentence for every horror or
# non-horror episode. They say nothing about THIS episode, so the summary of the episode wins over them.
GENERIC_HOOKS = ("ne regarde pas derrière toi", "à toi de choisir", "tu n'aurais jamais dû faire ça",
                 "et toi, tu aurais fait quoi", "histoire interactive", "histoire d'horreur interactive",
                 "choisis a ou b", "a ou b")

# formulas that promise something the episode does not keep: removed from any inherited title/description
CLICKBAIT = (r"vous\s+n[e']\s*(le\s+)?croirez\s+jamais", r"tu\s+n[e']\s*(le\s+)?croiras\s+jamais", r"incroyable\s*!+",
             r"\b100\s*%\s*r[ée]el\b", r"\bchoquant\b", r"\bjamais\s+vu\b", r"\bg[ée]nial\b", r"\bmust\s*watch\b",
             r"\(?\s*histoire\s+vraie\s*\)?", r"\bvraiment\s+arriv[ée]\b", r"\bIA\s+interdite\b")


def _nfkd(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def _slug(s, keep_digits=True):
    """'L'Étage 0 n'existe pas' -> 'letage0nexistepas' (a hashtag has no space and no accent)"""
    s = _nfkd(str(s or '')).lower()
    s = re.sub(r'[^a-z0-9]+', '', s) if keep_digits else re.sub(r'[^a-z]+', '', s)
    return s


def _squeeze(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()


def _declickbait(s):
    """strip the lying formulas; the punctuation left dangling by a cut is removed too, otherwise the text is kept"""
    out = before = _squeeze(s)
    for pat in CLICKBAIT:
        out = re.sub(pat, '', out, flags=re.I)
    out = _squeeze(out)
    return _squeeze(re.sub(r'\s*([,;:!?.]\s*)+$', '', out)) if out != before else out


def _trim(s, n, tail='…'):
    """cut on a word boundary, never in the middle of a word"""
    s = _squeeze(s)
    if len(s) <= n:
        return s
    cut = s[:max(1, n - len(tail))]
    if ' ' in cut[int(n * .5):]:
        cut = cut[:cut.rstrip().rfind(' ')]
    return cut.rstrip(' ,;:-–—') + tail


def _first_sentence(s, n=90):
    s = _squeeze(s)
    m = re.split(r'(?<=[.!?…])\s+', s)
    return _trim(m[0] if m and m[0] else s, n)


# ------------------------------------------------------------------ what the episode says
def episode_number(project, episode=None):
    """episode number read from the project ('Partie 4', 'Épisode 03', '#5', part/episode keys) or from hud.part"""
    project = project or {}
    for k in ('episode_number', 'part_number', 'part', 'episode'):
        v = project.get(k)
        if isinstance(v, int):
            return v
        if isinstance(v, str) and v.strip().isdigit():
            return int(v.strip())
    hud = (episode or {}).get('hud') or {}
    for src in (project.get('part_label'), hud.get('part'), hud.get('level'), project.get('name')):
        m = re.search(r'\b(\d{1,3})\b', str(src or ''))
        if m:
            return int(m.group(1))
    return None


def episode_label(project, episode=None):
    """the label as written by the owner ('PARTIE 4', 'NIVEAU 2'), else 'Épisode N', else ''"""
    hud = (episode or {}).get('hud') or {}
    for src in ((project or {}).get('part_label'), hud.get('part'), hud.get('level')):
        if _squeeze(src):
            return _squeeze(src)
    n = episode_number(project, episode)
    return f'Épisode {n}' if n else ''


def series_name(project, episode=None):
    hud = (episode or {}).get('hud') or {}
    title = hud.get('title')
    if isinstance(title, (list, tuple)):
        title = ' '.join(str(t) for t in title)
    for src in ((project or {}).get('series'), (episode or {}).get('series'), hud.get('series'), title,
                (project or {}).get('hud_title', '').replace('|', ' ')):
        if _squeeze(src):
            return _squeeze(src)
    return ''


def choices(episode):
    """the 2 or 3 options of the final vote, ONLY if the episode writes them (`ui.choice`); else []

    Tolerated shapes (an older episode or a provider may use any of them):
      {"A": "LA CONSOLE", "B": "LA VOIX"}            -> text as a string
      {"A": ["SORTIR", "L'AFFRONTER"], "B": [...]}   -> text as (at most 2) thumbnail lines
      {"options": ["...", "..."]}                    -> list, lettered in order
    """
    episode = episode or {}
    last = None
    for s in episode.get('shots') or []:
        ui = s.get('ui') or {}
        if isinstance(ui.get('choice'), dict):
            last = ui['choice']
    if not last:
        return []
    out = []
    opts = last.get('options')
    if isinstance(opts, (list, tuple)) and not any(last.get(l) for l in LETTERS):
        for i, o in enumerate(opts[:len(LETTERS)]):
            out.append({'letter': LETTERS[i], 'text': _squeeze(' '.join(str(x) for x in o) if isinstance(o, (list, tuple)) else o)})
    else:
        for l in LETTERS:
            v = last.get(l)
            if v is None or (isinstance(v, (list, tuple)) and not any(_squeeze(x) for x in v)):
                continue
            out.append({'letter': l, 'text': _squeeze(' '.join(str(x) for x in v) if isinstance(v, (list, tuple)) else v)})
    out = [c for c in out if c['text']]
    return out if len(out) >= 2 else []


def choice_question(episode):
    for s in reversed(episode.get('shots') or []):
        ui = s.get('ui') or {}
        if isinstance(ui.get('choice'), dict) and _squeeze(ui['choice'].get('title')):
            return _squeeze(ui['choice']['title'])
    return ''


def previous_choice(project):
    """what the viewers voted at the end of the previous episode, as {'letter', 'text'} or None"""
    project = project or {}
    raw = _squeeze(project.get('previous_choice'))
    txt = _squeeze(project.get('previous_choice_text')) or raw
    if not raw and not txt:
        return None
    m = re.match(r'^\s*\(?([ABCD])\)?\b[\s:.\-–—]*(.*)$', raw, flags=re.I)
    letter = m.group(1).upper() if m else ''
    text = _squeeze(re.sub(r'^\s*\(?[ABCD]\)?\b[\s:.\-–—]*', '', txt, flags=re.I))
    if not text and m:
        text = _squeeze(m.group(2))
    return {'letter': letter, 'text': text}


def _vote_line(chs, question=''):
    """'A ou B ?' / 'A, B ou C ?' built on the options actually written"""
    if not chs:
        return ''
    ls = [c['letter'] for c in chs]
    letters = ' ou '.join([', '.join(ls[:-1]), ls[-1]]) if len(ls) > 2 else ' ou '.join(ls)
    q = _squeeze(question)
    if q and not q.endswith(('?', '!', '.', '…')):
        q += ' ?'
    return f'{q} {letters} ?' if q else f'{letters} ?'


def _is_generic(hook):
    """True when the hook is one of the canned sentences of the offline director (nothing episode-specific)"""
    k = _slug(hook)
    return any(_slug(g) in k for g in GENERIC_HOOKS) if k else True


def _hook(base, episode, chs):
    """the promise of THIS episode: the title written by the director if it says something, else the summary

    The offline director writes the same canned title for every episode of a genre; in that case the summary of
    the episode is more relevant and more honest, so it wins. A title written by an LLM is kept as it is.
    """
    cand = ''
    for t in [t for t in (base.get('titles') or []) if _squeeze(t)]:
        h = _declickbait(t)
        h = re.sub(r'^\s*[^:|]{0,40}(partie|épisode|ep\.?|niveau)\s*\d+\s*[:|–—-]\s*', '', h, flags=re.I)
        h = re.sub(r'\s*[\(\[]?\s*(partie|épisode|ep\.?|niveau)\s*\d+\s*[\)\]]?\s*$', '', h, flags=re.I)
        h = _squeeze(re.sub(r'\s*\|\s*.*$', '', h))
        if len(h) >= 12:
            cand = h
            break
    s = _declickbait(_first_sentence(episode.get('summary', ''))).rstrip(' .;,')
    if cand and not (_is_generic(cand) and s):
        return cand
    return s or cand or _vote_line(chs) or 'Histoire interactive'


# ------------------------------------------------------------------ hashtags per platform
def _hashtags(base, project, episode, platform, chs):
    """platform-specific list: YouTube shows only the first 3 and wants 'shorts'; TikTok wants the For You tags"""
    have = []
    seen = set()

    def add(*tags):
        for t in tags:
            t = _slug(t)
            if t and t not in seen and len(t) <= 30:
                seen.add(t)
                have.append(t)
    inherited = [h for h in (base.get('hashtags') or []) if _squeeze(h)]
    series_tag = _slug(series_name(project, episode))
    generic = {'fyp', 'pourtoi', 'foryou', 'foryoupage', 'shorts', 'short', 'viral', 'tiktok'}
    topical = [h for h in inherited if _slug(h) not in generic]
    if platform == 'youtube_shorts':
        add('shorts')
        add(*topical[:4])
        if series_tag:
            add(series_tag)
        if chs:
            add('choisistonhistoire')
        return have[:6]
    add(*topical[:4])
    if series_tag:
        add(series_tag)
    if chs:
        add('choisistonhistoire')
    add('pourtoi', 'fyp')
    return have[:8]


# ------------------------------------------------------------------ the two packages
def _recall(project, episode):
    """series continuity: one sentence recalling the previous episode and the choice that was voted"""
    prev = previous_choice(project)
    n = episode_number(project, episode)
    bits = []
    if prev:
        what = prev['text'] or prev['letter']
        bits.append(f"Vous avez choisi {prev['letter']} : {what}." if prev['letter'] and prev['text']
                    else f"Vous avez choisi : {what}.")
    if n and n > 1:
        bits.append(f"Épisode {n} de la série, la suite dépend de vos votes.")
    return ' '.join(bits)


def youtube_shorts(project, episode, base, chs, hook, vote):
    series = series_name(project, episode)
    label = episode_label(project, episode)
    n = episode_number(project, episode)
    short_label = f'Ép. {n}' if n else label
    head = ' — '.join([x for x in (series, short_label) if x])
    title = _trim(f'{head} : {hook}' if head else hook, YT_TITLE_SOFT)
    if len(title) > YT_TITLE_MAX:                      # belt and braces, the API refuses beyond 100
        title = _trim(title, YT_TITLE_MAX)
    paras = []
    summary = _declickbait(episode.get('summary', ''))
    if summary:
        paras.append(summary)
    recall = _recall(project, episode)
    if recall:
        paras.append(recall)
    if chs:
        paras.append('\n'.join([f"{c['letter']} — {c['text']}" for c in chs]))
        paras.append(f"{vote} Réponds en commentaire : le choix le plus voté est tourné dans le prochain épisode.")
    else:
        paras.append('Histoire interactive : les épisodes suivants sont écrits avec vos commentaires.')
    tags = _hashtags(base, project, episode, 'youtube_shorts', chs)
    desc = '\n\n'.join(paras) + '\n\n' + ' '.join('#' + t for t in tags[:3])
    return {'title': title, 'description': desc, 'hashtags': tags,
            'tags': [t for t in (base.get('tags') or []) if _squeeze(t)][:20],
            'pinned_comment': (vote + ' Ton vote décide de la suite.') if chs else '',
            'cover': 'cover_9x16.jpg', 'thumbnail': 'thumbnail_16x9.jpg'}


def tiktok(project, episode, base, chs, hook, vote):
    series = series_name(project, episode)
    n = episode_number(project, episode)
    label = f'Ép. {n}' if n else episode_label(project, episode)
    prev = previous_choice(project)
    head = _trim(hook, TIKTOK_CAPTION_SOFT - 40)
    bits = [head]
    tail = ' · '.join([x for x in (label, series) if x])
    if tail:
        bits.append(tail)
    if prev and prev['letter']:
        bits.append(f"(vous avez voté {prev['letter']})")
    if chs:
        bits.append(' / '.join([f"{c['letter']} {c['text']}" for c in chs]))
        bits.append(f'{vote} commente')
    tags = _hashtags(base, project, episode, 'tiktok', chs)
    caption = ' | '.join(b for b in bits if b) + ' ' + ' '.join('#' + t for t in tags)
    return {'caption': _squeeze(caption), 'hashtags': tags, 'cover': 'cover_9x16.jpg',
            'sound_hint': 'voix + SFX de l’épisode (pas de son tendance importé)'}


def pack(project, episode, base=None, lines=None):
    """the `platforms` block: same episode, one package per platform. Never raises on a partial episode."""
    project = dict(project or {})
    episode = dict(episode or {})
    base = dict(base or {})
    chs = choices(episode)
    vote = _vote_line(chs, choice_question(episode))
    hook = _hook(base, episode, chs)
    return {'series': series_name(project, episode), 'episode_number': episode_number(project, episode),
            'episode_label': episode_label(project, episode), 'style': project.get('style', 'pixel3d'),
            'interactive': bool(chs), 'choices': chs, 'vote_line': vote, 'hook': hook,
            'previous_choice': previous_choice(project), 'continuity': _recall(project, episode),
            'youtube_shorts': youtube_shorts(project, episode, base, chs, hook, vote),
            'tiktok': tiktok(project, episode, base, chs, hook, vote)}


def as_text(p):
    """the pack as a copy-paste sheet for the owner (one block per platform); pure text, nothing is published"""
    p = p or {}
    yt = p.get('youtube_shorts') or {}
    tk = p.get('tiktok') or {}
    head = ' · '.join(x for x in (p.get('series'), p.get('episode_label'), (p.get('style') or '').upper()) if x)
    L = [f'ÉPISODE : {head}' if head else 'ÉPISODE']
    if p.get('choices'):
        L.append('Vote : ' + (p.get('vote_line') or '') + '  ->  ' + ' / '.join(f"{c['letter']} {c['text']}" for c in p['choices']))
    else:
        L.append('Vote : aucun choix écrit dans cet épisode (rien n’est promis au public).')
    if p.get('continuity'):
        L.append('Continuité : ' + p['continuity'])
    L += ['', '--- YOUTUBE SHORTS ---', 'Titre : ' + yt.get('title', ''), '', 'Description :', yt.get('description', ''), '',
          'Hashtags : ' + ' '.join('#' + h for h in yt.get('hashtags') or []),
          'Tags : ' + ', '.join(yt.get('tags') or []),
          'Commentaire épinglé : ' + (yt.get('pinned_comment') or '—'),
          f"Images : {yt.get('thumbnail', '')} (16:9) · {yt.get('cover', '')} (9:16)", '',
          '--- TIKTOK ---', 'Légende :', tk.get('caption', ''), '',
          'Hashtags : ' + ' '.join('#' + h for h in tk.get('hashtags') or []),
          f"Image : {tk.get('cover', '')} (9:16)", 'Son : ' + (tk.get('sound_hint') or '—'), '',
          'Publication manuelle : rien n’est envoyé automatiquement à YouTube ou TikTok.']
    return '\n'.join(L)
