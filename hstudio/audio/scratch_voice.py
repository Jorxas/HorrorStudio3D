"""Draft voice ("voix de brouillon"): a free, local, syllabic babble timed on the lines, one pitch per character.

It is NOT a text-to-speech engine and never replaces ElevenLabs: it lets a scene be previewed with lip sync, speech
gestures and editing rhythm before any paid voice is generated. Vowels of the text drive the formants (so the babble
follows the sentence), punctuation drives pauses and intonation. Pure numpy (additive harmonics shaped by formants)."""
import math, re, unicodedata, numpy as np

SR = 22050
FORMANTS = {'a': (750, 1250, 2600), 'e': (480, 1550, 2550), 'i': (300, 2250, 3000), 'o': (520, 900, 2500), 'u': (320, 1650, 2300),
            'y': (300, 2000, 2800), 'é': (400, 2000, 2700), 'è': (560, 1750, 2550), 'ou': (330, 800, 2300), 'on': (450, 800, 2500),
            'an': (650, 1050, 2500), 'in': (550, 1600, 2600), 'eu': (420, 1400, 2400)}
VOICES = {'low': 105., 'man': 120., 'woman': 205., 'girl': 245., 'boy': 230., 'kid': 270., 'old_man': 110., 'old_woman': 185., 'robot': 140.}

def _syllables(text):
    t = text.lower()
    out = []
    for m in re.finditer(r"(ou|on|an|en|in|eu|au|ai|ei|oi|[aeiouyéèêàâîïôûù])|([.!?…]+)|([,;:—-]+)", t):
        if m.group(1):
            v = m.group(1)
            v = {'au': 'o', 'ai': 'è', 'ei': 'è', 'oi': 'a', 'en': 'an', 'ê': 'è', 'à': 'a', 'â': 'a', 'î': 'i', 'ï': 'i', 'ô': 'o', 'û': 'u', 'ù': 'u'}.get(v, v)
            prev = t[m.start() - 1] if m.start() > 0 else ' '
            out.append(('v', v, prev))
        elif m.group(2): out.append(('stop', m.group(2), ''))
        else: out.append(('pause', m.group(3), ''))
    return out

def _env_formant(freqs, fmt, bw=(90, 120, 160)):
    a = np.zeros_like(freqs)
    for f, b, g in zip(fmt, bw, (1., .55, .25)): a += g / (1 + ((freqs - f) / b) ** 2)
    return a

def synth_line(text, dur, f0=180., seed=0, question=None):
    """babble for one line, exactly dur seconds long"""
    syl = _syllables(text) or [('v', 'a', ' ')]
    n = int(dur * SR); out = np.zeros(n, np.float32)
    weights = [1. if k == 'v' else (2.2 if k == 'stop' else 1.3) for k, _, _ in syl]
    tot = sum(weights); unit = dur / max(tot, 1e-3); unit = min(unit, .26)
    rng = np.random.default_rng(seed); t = 0.
    q = text.strip().endswith('?') if question is None else question
    nv = sum(1 for k, _, _ in syl if k == 'v'); iv = 0
    for (kind, v, prev) in syl:
        if kind != 'v':
            t += unit * (2.2 if kind == 'stop' else 1.3) * .8; continue
        d = unit * (.85 + .3 * rng.random()); a = int(t * SR); b = min(n, int((t + d) * SR)); t += d
        if b - a < 40: continue
        m = b - a; tt = np.arange(m) / SR
        prog = iv / max(1, nv - 1); iv += 1
        contour = 1 + .10 * math.sin(prog * math.pi) - .12 * prog + (.25 * max(0., prog - .75) * 4 if q else 0.)
        f = f0 * contour * (1 + .02 * np.sin(2 * math.pi * 5.5 * tt)) * (1 + .03 * (rng.random() - .5))
        ph = 2 * math.pi * np.cumsum(f) / SR
        fmt = FORMANTS.get(v, FORMANTS['a']); sig = np.zeros(m, np.float32)
        K = int(min(40, 3800 / (f0 * contour)))
        for k_ in range(1, K + 1):
            g = float(_env_formant(np.array([k_ * f0 * contour]), fmt)[0]) / k_ ** .7
            sig += (g * np.sin(k_ * ph)).astype(np.float32)
        att = min(m, int(.025 * SR)); rel = min(m, int(.06 * SR)); env = np.ones(m, np.float32)
        env[:att] = np.linspace(0, 1, att); env[-rel:] *= np.linspace(1, 0, rel)
        if prev not in ' aeiouyéèêàâîïôûù\'-':                      # consonant onset: a short noise burst
            bl = min(m, int(.03 * SR)); nz = rng.standard_normal(bl).astype(np.float32)
            if prev in 'sfcxzjgh': nz = np.diff(np.concatenate([[0], nz])) * .9
            sig[:bl] += nz * np.linspace(.5, 0, bl) * .35
        out[a:b] += sig * env
    pk = float(np.abs(out).max()) or 1.
    return out / pk * .5

def render(lines, speakers, voices=None, total=None, seed=1):
    """lines: [{start, end, text}], speakers: [character id per line] -> (mono float32 at SR, mouth envelope 30 fps)"""
    voices = voices or {}; total = total or (lines[-1]['end'] + 1.)
    n = int(total * SR); out = np.zeros(n, np.float32)
    for i, ln in enumerate(lines):
        who = speakers[i] if i < len(speakers) else None
        if not who: continue
        v = voices.get(who, 'woman'); f0 = VOICES.get(v, v if isinstance(v, (int, float)) else 180.)
        d = max(.2, ln['end'] - ln['start'])
        sig = synth_line(ln.get('text') or ln.get('display') or '', d, float(f0), seed + i)
        a = int(ln['start'] * SR); out[a:a + len(sig)] += sig[:max(0, n - a)]
    hop = SR // 30; m = len(out) // hop
    env = np.sqrt((out[:m * hop].reshape(m, hop) ** 2).mean(1)); env = env / (env.max() + 1e-9)
    return out, np.clip(env * 1.4, 0, 1).astype(np.float32)

def write_mp3(sig, path, workdir):
    import os, subprocess, wave
    wav = os.path.join(workdir, '_scratch_voice.wav')
    with wave.open(wav, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(sig, -1, 1) * 32000).astype(np.int16).tobytes())
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', wav, '-ar', '44100', '-c:a', 'libmp3lame', '-b:a', '128k', path], check=True)
    os.remove(wav)
