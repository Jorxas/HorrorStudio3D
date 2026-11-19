"""Voice casting: one stable ElevenLabs voice_id per character, plus a distinct narrator voice.

Still the same provider (ElevenLabs, `tts.py`): no new engine, no extra request beyond the ones the script needs.
A script line carries `speaker` (a character id of the project, set by `pipeline.script_lines`) or nothing, and a
line without a speaker is the narrator (`NARRATOR`).

Where a voice_id comes from, highest priority first:
  1. the project: `project.json` -> `"voices": {"lea": "<voice_id>", "_narrateur": "<voice_id>"}`
     (a key may also be a character name, accents and case ignored: `"Léa"` works);
  2. the episode cast, when one is already resolved: `cast[cid]["voice"]["elevenlabs_voice_id"]`;
  3. the character library: `library/characters/<cid>.json` -> `"voice": {"elevenlabs_voice_id": "..."}`;
  4. the narrator setting `elevenlabs_narrator_voice_id` (narrator only);
  5. the single global voice `project.json "voice_id"` then settings `elevenlabs_voice_id` (compatibility:
     a project that never casts a voice keeps behaving exactly as before, one voice for everything).

`synthesize_cast` groups consecutive lines that share a voice into one request, keeps the script order, concatenates
the parts in that order and shifts each part's character timestamps by the real duration of the parts before it, so
`align.words_from_alignment` sees one continuous track. Parts are cached on disk under `work/tts/<sha1>.mp3`; the
hash covers the voice_id, the model, the voice settings and the text, so changing one character's voice re-synthesises
that character's parts only and never reuses another voice's audio.
"""
import hashlib, json, os, unicodedata
from . import tts
from .acting import cast as CAST

NARRATOR = '_narrateur'
NARRATOR_NAME = 'Narrateur'
_NARRATOR_KEYS = (NARRATOR, 'narrateur', 'narrator', 'narration')


def _norm(s):
    s = unicodedata.normalize('NFD', str(s or '').strip().lower())
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')


def _name_keys(cast_ids):
    """{normalised name or id: character id}, so "Léa" in the project voices map reaches the character `lea`"""
    out = {}
    for cid in cast_ids or []:
        out[_norm(cid)] = cid
        c = CAST.character(cid) or {}
        if c.get('name'):
            out[_norm(c['name'])] = cid
            out[_norm(c['name'].split()[0])] = cid
    return out


def library_voice(cid, cast=None):
    """the voice_id cast for a character: episode cast first, then the character library (None if never cast)"""
    spec = (cast or {}).get(cid) or {}
    if not isinstance(spec, dict): spec = {}
    vid = ((spec.get('voice') or {}) if isinstance(spec.get('voice'), dict) else {}).get('elevenlabs_voice_id') or spec.get('voice_id')
    if not vid:
        lib = CAST.character(cid) or {}
        vid = (lib.get('voice') or {}).get('elevenlabs_voice_id')
    vid = str(vid or '').strip()
    return vid or None


def character_name(cid, cast=None):
    spec = (cast or {}).get(cid) or {}
    name = (spec.get('name') if isinstance(spec, dict) else None) or (CAST.character(cid) or {}).get('name')
    return name or cid


def speakers_of(lines):
    """the speakers of a script in order of first appearance, the narrator included when he speaks"""
    out = []
    for l in lines:
        sp = l.get('speaker') or NARRATOR
        if sp not in out: out.append(sp)
    return out


def resolve(meta, settings, speakers, cast=None):
    """-> {speaker: {'voice_id': str|'', 'source': str, 'name': str}} for each speaker (see the module docstring)"""
    meta = meta or {}; settings = settings or {}
    glob = str(meta.get('voice_id') or settings.get('elevenlabs_voice_id') or '').strip()
    narrator_set = str(meta.get('narrator_voice_id') or settings.get('elevenlabs_narrator_voice_id') or '').strip()
    names = _name_keys(list(meta.get('cast') or []) + [s for s in speakers if s != NARRATOR])
    over = {}
    for k, v in (meta.get('voices') or {}).items():
        v = str(v or '').strip()
        if not v: continue
        nk = _norm(k)
        over[names.get(nk, NARRATOR if nk in _NARRATOR_KEYS else nk)] = v
    out = {}
    for sp in speakers:
        if sp in over:
            out[sp] = {'voice_id': over[sp], 'source': 'projet', 'name': character_name(sp, cast) if sp != NARRATOR else NARRATOR_NAME}
            continue
        if sp == NARRATOR:
            vid, src = (narrator_set, 'narrateur (réglages)') if narrator_set else (glob, 'voix globale (repli)')
            out[sp] = {'voice_id': vid, 'source': src, 'name': NARRATOR_NAME}
            continue
        vid = library_voice(sp, cast)
        out[sp] = {'voice_id': vid or glob, 'source': 'bibliothèque' if vid else 'voix globale (repli)',
                   'name': character_name(sp, cast)}
    return out


def line_text(l):
    return str(l.get('tts') if l.get('tts') is not None else l.get('text', '')).replace('*', '')


def plan(lines, voices, max_chars=2500):
    """script order kept: consecutive lines sharing a voice_id become one request (chunked at max_chars)

    -> [{'voice_id', 'speakers': [...], 'lines': [index...], 'texts': [...]}, ...]"""
    fallback = (voices.get(NARRATOR) or {}).get('voice_id', '')
    segs = []
    for i, l in enumerate(lines):
        sp = l.get('speaker') or NARRATOR
        vid = (voices.get(sp) or {}).get('voice_id') or fallback
        txt = line_text(l)
        last = segs[-1] if segs else None
        if last and last['voice_id'] == vid and len('\n\n'.join(last['texts'] + [txt])) <= max_chars:
            last['lines'].append(i); last['texts'].append(txt)
            if sp not in last['speakers']: last['speakers'].append(sp)
        else:
            segs.append({'voice_id': vid, 'speakers': [sp], 'lines': [i], 'texts': [txt]})
    return segs


def _cache_key(voice_id, model_id, vs, text):
    h = hashlib.sha1()
    h.update(json.dumps([voice_id, model_id, vs, text], sort_keys=True, ensure_ascii=False).encode('utf-8'))
    return h.hexdigest()[:16]


def synthesize_cast(key, lines, voices, out_mp3, workdir, model_id='eleven_v3', vs=None, max_chars=2500, log=print,
                    request=None, duration=None, concat=None):
    """one voice per character -> alignment dict {characters, starts, ends, segments} for the concatenated audio.

    `request`/`duration`/`concat` are the provider and the audio tools; they are injected by the offline test."""
    request = request or tts.request_tts
    duration = duration or tts.ffprobe_duration
    concat = concat or tts.concat_mp3
    vs = vs or tts.DEFAULT_VOICE_SETTINGS
    segs = plan(lines, voices, max_chars)
    if not segs: raise RuntimeError('Le script est vide.')
    cache = os.path.join(workdir, 'tts'); os.makedirs(cache, exist_ok=True)
    parts = []; chars, starts, ends = [], [], []; offset = 0.; done = []
    for k, seg in enumerate(segs):
        text = '\n\n'.join(seg['texts'])
        p = os.path.join(cache, f"{_cache_key(seg['voice_id'], model_id, vs, text)}.mp3")
        meta_p = p + '.json'
        who = '+'.join((voices.get(s) or {}).get('name', s) for s in seg['speakers'])
        if os.path.exists(p) and os.path.getsize(p) > 0 and os.path.exists(meta_p):
            al = json.load(open(meta_p, encoding='utf-8'))
            log(f"Voix {k + 1}/{len(segs)} ({who}, {seg['voice_id']}) : déjà synthétisée, reprise du cache")
        else:
            log(f"Voix {k + 1}/{len(segs)} ({who}, {seg['voice_id']}) : {len(seg['lines'])} réplique(s), {len(text)} caractères")
            audio, al = request(key, seg['voice_id'], text, model_id=model_id, voice_settings=vs)
            open(p, 'wb').write(audio)
            json.dump(al, open(meta_p, 'w', encoding='utf-8'), ensure_ascii=False)
        d = float(duration(p))
        for c, s, e in zip(al.get('characters', []), al.get('character_start_times_seconds', []), al.get('character_end_times_seconds', [])):
            chars.append(c); starts.append(s + offset); ends.append(e + offset)
        chars.append('\n'); starts.append(offset + d); ends.append(offset + d)
        offset += d; parts.append(p)
        done.append({'voice_id': seg['voice_id'], 'speakers': list(seg['speakers']), 'lines': list(seg['lines']),
                     'start': round(offset - d, 3), 'end': round(offset, 3), 'file': os.path.basename(p)})
    concat(parts, out_mp3, workdir)
    return {'characters': chars, 'starts': starts, 'ends': ends, 'segments': done}
