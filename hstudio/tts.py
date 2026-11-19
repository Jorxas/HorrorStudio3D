"""ElevenLabs: text-to-speech with timestamps, and forced alignment of an existing audio file.
API key: settings 'elevenlabs_api_key' (or env ELEVENLABS_API_KEY)."""
import base64, json, os, subprocess, requests
API = 'https://api.elevenlabs.io/v1'

def _headers(key): return {'xi-api-key': key, 'accept': 'application/json'}

def list_voices(key):
    r = requests.get(f'{API}/voices', headers=_headers(key), timeout=60); r.raise_for_status()
    return [{'voice_id': v['voice_id'], 'name': v.get('name', ''), 'category': v.get('category', '')} for v in r.json().get('voices', [])]

def list_models(key):
    r = requests.get(f'{API}/models', headers=_headers(key), timeout=60); r.raise_for_status()
    return [{'model_id': m['model_id'], 'name': m.get('name', '')} for m in r.json()]

def _chunks(lines_tts, max_chars):
    out, cur = [], []
    for l in lines_tts:
        if cur and len('\n\n'.join(cur + [l])) > max_chars: out.append(cur); cur = []
        cur.append(l)
    if cur: out.append(cur)
    return out

def ffprobe_duration(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)

def voice_settings(stability=.5, similarity=.75, style=0., speed=1.0, speaker_boost=True):
    return {'stability': stability, 'similarity_boost': similarity, 'style': style, 'use_speaker_boost': speaker_boost, 'speed': speed}

DEFAULT_VOICE_SETTINGS = voice_settings()

def request_tts(key, voice_id, text, model_id='eleven_v3', voice_settings=None, timeout=600):
    """one text-to-speech request for one voice -> (mp3 bytes, raw ElevenLabs alignment dict)"""
    body = {'text': text, 'model_id': model_id, 'voice_settings': dict(voice_settings or DEFAULT_VOICE_SETTINGS)}
    def post():
        return requests.post(f'{API}/text-to-speech/{voice_id}/with-timestamps', params={'output_format': 'mp3_44100_192'},
                             headers={**_headers(key), 'Content-Type': 'application/json'}, data=json.dumps(body), timeout=timeout)
    r = post()
    if r.status_code == 422 or (r.status_code == 400 and 'speed' in r.text):
        body['voice_settings'].pop('speed', None); r = post()
    if r.status_code >= 400: raise RuntimeError(f'ElevenLabs {r.status_code}: {r.text[:500]}')
    j = r.json()
    return base64.b64decode(j['audio_base64']), (j.get('alignment') or j.get('normalized_alignment') or {})

def concat_mp3(parts, out_mp3, workdir):
    """the parts one after the other, in that exact order, into out_mp3"""
    if len(parts) == 1:
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', parts[0], '-c', 'copy', out_mp3], check=True)
    else:
        lst = os.path.join(workdir, 'concat.txt'); open(lst, 'w', encoding='utf-8').write(''.join(f"file '{os.path.abspath(p)}'\n" for p in parts))
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c:a', 'libmp3lame', '-b:a', '192k', out_mp3], check=True)

def synthesize(key, voice_id, lines_tts, out_mp3, workdir, model_id='eleven_v3', stability=.5, similarity=.75, style=0., speed=1.0,
               speaker_boost=True, max_chars=2500, log=print):
    """one single voice for the whole script -> alignment dict {characters, starts, ends} for the concatenated audio.
    For one voice per character see voices.synthesize_cast (same alignment shape)."""
    os.makedirs(workdir, exist_ok=True)
    vs = voice_settings(stability, similarity, style, speed, speaker_boost)
    chunks = _chunks(lines_tts, max_chars); parts = []; chars, starts, ends = [], [], []; offset = 0.
    for k, ch in enumerate(chunks):
        text = '\n\n'.join(ch)
        log(f'ElevenLabs : morceau {k + 1}/{len(chunks)} ({len(text)} caractères)')
        audio, al = request_tts(key, voice_id, text, model_id=model_id, voice_settings=vs)
        p = os.path.join(workdir, f'tts_{k:02d}.mp3')
        open(p, 'wb').write(audio); parts.append(p)
        for c, s, e in zip(al.get('characters', []), al.get('character_start_times_seconds', []), al.get('character_end_times_seconds', [])):
            chars.append(c); starts.append(s + offset); ends.append(e + offset)
        chars.append('\n'); starts.append(offset + ffprobe_duration(p)); ends.append(starts[-1])
        offset += ffprobe_duration(p)
    concat_mp3(parts, out_mp3, workdir)
    return {'characters': chars, 'starts': starts, 'ends': ends}

def forced_alignment(key, audio_path, text):
    """ElevenLabs Forced Alignment API: audio + exact text -> words with timings"""
    with open(audio_path, 'rb') as f:
        r = requests.post(f'{API}/forced-alignment', headers={'xi-api-key': key}, files={'file': (os.path.basename(audio_path), f)},
                          data={'text': text}, timeout=600)
    if r.status_code >= 400: raise RuntimeError(f'ElevenLabs alignement {r.status_code}: {r.text[:300]}')
    j = r.json()
    return [{'word': w['text'], 'start': float(w['start']), 'end': float(w['end'])} for w in j.get('words', []) if w.get('text', '').strip()]
