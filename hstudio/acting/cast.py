"""Persistent characters and series (both engines).

library/characters/<id>.json
  {"id": "lea", "name": "Léa", "look": {...pixel3d look keys: hood, jeans, hair, skin, hair_style, outfit, hat, glasses...},
   "voice": {"draft": "woman", "elevenlabs_voice_id": ""}, "personality": {"expressive": .8, "energy": .7, "shy": .1},
   "relations": {"tom": "meilleur ami"}, "notes": "..."}
library/series/<id>.json
  {"id": "...", "title": "...", "characters": ["lea", "tom"], "places": {...}, "episodes": [{"id", "title", "project"}],
   "state": {"lea": {"hold": "cle", "look": {"hat": "cap"}}}}     # narrative state carried to the next episode

An episode may also carry "series_state" (same shape as "state"): it then replays that exact point of the series
instead of the current library state (used by the demos so that they do not depend on the order of the renders).

In an episode: "series": "<id>" and "cast": {"lea": {"ref": "lea"}} (or "cast": {"lea": "@lea"}). Keys written in the
episode override the library (a deliberate change of costume for one episode); the series state adds lasting changes
(a scar, a new jacket, an object kept). Both engines read the resolved cast, so a character looks the same everywhere."""
import os, json, copy
from .. import paths

LIB = os.path.join(paths.ROOT, 'library')
CHAR_DIR = os.path.join(LIB, 'characters'); SERIES_DIR = os.path.join(LIB, 'series')

def _read(p):
    try: return json.load(open(p, encoding='utf-8'))
    except Exception: return None

def character(cid):
    return _read(os.path.join(CHAR_DIR, f'{cid}.json'))

def list_characters():
    if not os.path.isdir(CHAR_DIR): return []
    out = []
    for f in sorted(os.listdir(CHAR_DIR)):
        if f.endswith('.json'):
            c = _read(os.path.join(CHAR_DIR, f))
            if c: out.append(c)
    return out

def save_character(c):
    os.makedirs(CHAR_DIR, exist_ok=True)
    json.dump(c, open(os.path.join(CHAR_DIR, f"{c['id']}.json"), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

def series(sid): return _read(os.path.join(SERIES_DIR, f'{sid}.json')) if sid else None

def save_series(s):
    os.makedirs(SERIES_DIR, exist_ok=True)
    json.dump(s, open(os.path.join(SERIES_DIR, f"{s['id']}.json"), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

def resolve_cast(ep):
    """episode cast with library references expanded (in place on a copy); also returns voices and personalities"""
    cast = copy.deepcopy(ep.get('cast') or {})
    sr = series(ep.get('series')) or {}
    st = ep.get('series_state') if ep.get('series_state') is not None else (sr.get('state') or {})
    for cid in list(sr.get('characters') or []):
        cast.setdefault(cid, {'ref': cid}) if ep.get('series_cast', False) else None
    out = {}
    for cid, spec in cast.items():
        if isinstance(spec, str) and spec.startswith('@'): spec = {'ref': spec[1:]}
        spec = dict(spec or {})
        ref = spec.pop('ref', None)
        lib = character(ref) if ref else None
        look = {}
        if lib:
            look.update(lib.get('look') or {})
            if lib.get('personality'): look['personality'] = lib['personality']
            if lib.get('voice'): look['voice'] = lib['voice']
            look['name'] = lib.get('name', ref)
        lasting = (st.get(ref or cid) or {}).get('look') or {}
        look.update(lasting); look.update(spec)
        out[cid] = look
    return out

def apply(ep):
    """resolve the cast of an episode once (idempotent); used by both engines and the mixer"""
    if ep.get('_cast_resolved'): return ep
    ep['cast'] = resolve_cast(ep); ep['_cast_resolved'] = True
    return ep

def remember(ep, end_states, project_slug=None, title=None):
    """after an episode: store lasting state (objects kept) in its series"""
    sid = ep.get('series'); sr = series(sid)
    if not sr: return None
    st = sr.setdefault('state', {})
    for cid, s in (end_states or {}).items():
        if s.get('hold'): st.setdefault(cid, {})['hold'] = s['hold']
    if project_slug:
        eps = sr.setdefault('episodes', [])
        if not any(e.get('project') == project_slug for e in eps): eps.append({'id': project_slug, 'title': title or project_slug, 'project': project_slug})
    save_series(sr); return sr

def ensure_series(name, characters):
    """id of the series of a project (created in the library on first use, with its characters)"""
    import re, unicodedata
    if not name: return None
    sid = re.sub(r'[^a-z0-9]+', '_', unicodedata.normalize('NFD', name).encode('ascii', 'ignore').decode().lower()).strip('_')[:40]
    if not sid: return None
    sr = series(sid)
    if sr is None: sr = {'id': sid, 'title': name, 'characters': list(characters or []), 'episodes': [], 'state': {}}; save_series(sr)
    else:
        new = [c for c in characters or [] if c not in sr.get('characters', [])]
        if new: sr['characters'] = sr.get('characters', []) + new; save_series(sr)
    return sid
