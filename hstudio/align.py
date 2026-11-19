"""Timing of every script line (and every word) on the voice track.
Priority: ElevenLabs character timestamps (generated here) > ElevenLabs forced alignment (your own MP3)
> faster-whisper word timestamps (local, optional) > silence-based alignment (always available, offline)."""
import difflib, re, json, subprocess, wave, numpy as np
from .engines.common import norm

def _words_from_chars(al):
    words = []; cur = ''; s0 = None; e0 = None; in_tag = False
    for c, s, e in zip(al['characters'], al['starts'], al['ends']):
        if c == '[': in_tag = True
        if in_tag:
            if c == ']': in_tag = False
            if cur: words.append({'word': cur, 'start': s0, 'end': e0}); cur = ''
            continue
        if c.isspace():
            if cur: words.append({'word': cur, 'start': s0, 'end': e0}); cur = ''
            continue
        if not cur: s0 = s
        cur += c; e0 = e
    if cur: words.append({'word': cur, 'start': s0, 'end': e0})
    return [w for w in words if norm(w['word'])]

def words_from_alignment(al): return _words_from_chars(al)

def match_lines(lines, words):
    """attach start/end/word_times to each line by aligning the script words to the timed words"""
    script = []
    for li, l in enumerate(lines):
        for wi, w in enumerate(l['text'].split()):
            if norm(w): script.append((li, wi, norm(w)))
    timed = [norm(w['word']) for w in words]
    sm = difflib.SequenceMatcher(a=[s[2] for s in script], b=timed, autojunk=False)
    m = {}
    for a, b, n in sm.get_matching_blocks():
        for k in range(n): m[a + k] = b + k
    # interpolate unmatched words between matched neighbours
    idx = sorted(m)
    times = [None] * len(script)
    for k in range(len(script)):
        if k in m: times[k] = (words[m[k]]['start'], words[m[k]]['end'])
    for k in range(len(script)):
        if times[k] is None:
            prv = next((j for j in range(k - 1, -1, -1) if times[j] is not None), None)
            nxt = next((j for j in range(k + 1, len(script)) if times[j] is not None), None)
            a = times[prv][1] if prv is not None else 0.
            b = times[nxt][0] if nxt is not None else (a + .4)
            span = max(.05, b - a); nn = (nxt - prv - 1) if (prv is not None and nxt is not None) else 1
            pos = (k - prv) if prv is not None else 1
            t = a + span * (pos - .5) / max(1, nn); times[k] = (t, t + min(.35, span / max(1, nn)))
    out = []
    for li, l in enumerate(lines):
        wt = [times[k] for k, s in enumerate(script) if s[0] == li]
        if not wt: continue
        l = dict(l); l['start'] = float(wt[0][0]); l['end'] = float(wt[-1][1]); l['word_times'] = [[float(a), float(b)] for a, b in wt]
        l['segs'] = [[l['start'], l['end']]]
        out.append(l)
    for i, l in enumerate(out): l['i'] = i
    return out

# ------------------------------------------------------------------ offline: silence-based alignment
def silence_segments(audio, noise_db=-38, min_sil=.12):
    p = subprocess.run(['ffmpeg', '-hide_banner', '-i', audio, '-af', f'silencedetect=noise={noise_db}dB:d={min_sil}', '-f', 'null', '-'], capture_output=True, text=True)
    ev = []
    for l in p.stderr.split('\n'):
        mm = re.search(r'silence_(start|end): (-?[\d.e+-]+)', l)
        if mm: ev.append((mm.group(1), max(0, float(mm.group(2)))))
    dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', audio], capture_output=True, text=True).stdout or 0)
    segs = []; t = 0.
    for k, v in ev:
        if k == 'start':
            if v - t > .08: segs.append((t, v))
        else: t = v
    if dur - t > .1: segs.append((t, dur))
    return segs, dur

def silence_align(lines, audio):
    segs, dur = silence_segments(audio)
    ch = [max(1, len(l['text'])) for l in lines]
    speech = sum(b - a for a, b in segs); rate = speech / max(1, sum(ch))
    n, m = len(lines), len(segs)
    if m < n:          # not enough pauses detected: proportional split of the speech
        out = []; tot = sum(ch); t = segs[0][0] if segs else 0.; span = (segs[-1][1] - t) if segs else dur
        for l, c in zip(lines, ch):
            d = span * c / tot; l = dict(l); l['start'] = t; l['end'] = t + d * .92; l['segs'] = [[l['start'], l['end']]]; out.append(l); t += d
        return out
    INF = 1e18
    dp = [[INF] * (m + 1) for _ in range(n + 1)]; bk = [[0] * (m + 1) for _ in range(n + 1)]; dp[0][0] = 0
    for i in range(1, n + 1):
        exp = ch[i - 1] * rate
        for j in range(i, m + 1):
            for k in range(1, 6):
                if j - k < i - 1: break
                if dp[i - 1][j - k] >= INF: continue
                a = segs[j - k][0]; b = segs[j - 1][1]; d_ = sum(e - s for s, e in segs[j - k:j])
                c = ((d_ - exp) / max(exp, .5)) ** 2 + .15 * max(0, (b - a) - d_)
                if dp[i - 1][j - k] + c < dp[i][j]: dp[i][j] = dp[i - 1][j - k] + c; bk[i][j] = k
    j = m; res = []
    for i in range(n, 0, -1):
        k = bk[i][j]; res.append((segs[j - k][0], segs[j - 1][1], segs[j - k:j])); j -= k
    res.reverse(); out = []
    for l, (a, b, sg) in zip(lines, res):
        l = dict(l); l['start'] = float(a); l['end'] = float(b); l['segs'] = [[float(x), float(y)] for x, y in sg]; out.append(l)
    return out

# ------------------------------------------------------------------ optional: local whisper
def whisper_words(audio, model_size='large-v3', language='fr', device='auto'):
    from faster_whisper import WhisperModel          # pip install faster-whisper (optional)
    model = WhisperModel(model_size, device=device, compute_type='auto')
    segs, _ = model.transcribe(audio, language=language, word_timestamps=True, vad_filter=False)
    out = []
    for s in segs:
        for w in (s.words or []): out.append({'word': w.word.strip(), 'start': float(w.start), 'end': float(w.end)})
    return out

# ------------------------------------------------------------------ lip-sync envelope
def envelope(audio, fps=30, workdir='.'):
    wav = f'{workdir}/voice16.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', audio, '-ac', '1', '-ar', '16000', wav], check=True)
    w = wave.open(wav); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    hop = 16000 // fps; n = len(a) // hop
    env = np.array([np.sqrt((a[i * hop:(i + 1) * hop] ** 2).mean()) for i in range(n)])
    return np.clip(env / (np.percentile(env, 95) + 1e-6), 0, 1)
