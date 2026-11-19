"""A LOCAL voice for the demo: Windows' own speech synthesiser (System.Speech, the French voice « Microsoft Hortense »), no network, no API, no cost.

What it is and is not (the owner's rule, AGENTS.md: « the voice is always ElevenLabs with the owner's key »): this is NOT the studio's voice and is never presented as publishable. It exists so that a film can have
real speech (real timings, a real envelope for the lip-sync, a real dialogue mix) when no paid API may be called. Hortense is a single female voice: the other speakers are the same voice moved in pitch and
formant by ffmpeg (`asetrate` + `atempo`, `lowpass`), which gives distinct but obviously synthetic timbres. A line = (id, speaker, text); everything is cached by content hash so the film is reproducible.

    lines  -> synth_all()  -> {id: {path, dur, ...}}      per-line WAV (44.1 kHz mono), exact duration
    timeline [(t0, id)]    -> assemble()                   voice.wav (the film's voice track), per-speaker 30 Hz envelopes (JSON) for the lip-sync, a report
Deterministic: the same text and settings give the same bytes (the synthesiser has no randomness).
"""
import hashlib, json, math, subprocess, wave
from pathlib import Path
import numpy as np

SR = 44100
# speaker -> (pitch factor (1 = Hortense), SAPI rate -10..10, extra ffmpeg filter)
SPEAKERS = {
    'ines':  dict(pitch=1.04, rate=0, post='highpass=f=90'),
    'malo':  dict(pitch=.84, rate=0, post='highpass=f=70,lowpass=f=7600'),
    'vorn':  dict(pitch=.72, rate=-1, post='highpass=f=60,lowpass=f=6200,acompressor=threshold=-20dB:ratio=3'),
    'foule': dict(pitch=.95, rate=1, post='highpass=f=100'),
    'serveur': dict(pitch=.9, rate=0, post='highpass=f=80'),
    'speaker': dict(pitch=1.0, rate=0, post=''),
}
PS = r'''
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice('Microsoft Hortense Desktop')
$s.Rate = %d
$s.SetOutputToWaveFile('%s')
$s.Speak([IO.File]::ReadAllText('%s', [Text.Encoding]::UTF8))
$s.Dispose()
'''


def _key(speaker, text): return hashlib.sha1(json.dumps([speaker, text, SPEAKERS[speaker]], sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()[:14]


def synth_line(speaker, text, outdir):
    """-> path of the 44.1 kHz mono WAV of one line (cached)"""
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True); k = _key(speaker, text); final = outdir / f'{speaker}_{k}.wav'
    if final.exists(): return final
    sp = SPEAKERS[speaker]; raw = outdir / f'{speaker}_{k}_raw.wav'; txt = outdir / f'{speaker}_{k}.txt'; txt.write_text(text, encoding='utf-8')
    script = outdir / f'{speaker}_{k}.ps1'; script.write_text(PS % (sp['rate'], str(raw).replace("'", "''"), str(txt).replace("'", "''")), encoding='utf-8')
    r = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script)], capture_output=True, text=True)
    if r.returncode or not raw.exists(): raise RuntimeError('synthèse vocale locale en échec : ' + (r.stderr or r.stdout)[-400:])
    f = sp['pitch']; flt = f'asetrate={int(22050 * f)},aresample={SR},atempo={1. / f:.4f}' if abs(f - 1) > 1e-6 else f'aresample={SR}'
    if sp['post']: flt += ',' + sp['post']
    flt += ',loudnorm=I=-18:TP=-2:LRA=7'
    r = subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(raw), '-af', flt, '-ac', '1', '-ar', str(SR), '-c:a', 'pcm_s16le', str(final)], capture_output=True, text=True)
    if r.returncode: raise RuntimeError('ffmpeg (voix) en échec : ' + r.stderr[-400:])
    raw.unlink(missing_ok=True); script.unlink(missing_ok=True); txt.unlink(missing_ok=True)
    return final


def read_wav(path):
    with wave.open(str(path), 'rb') as w:
        n = w.getnframes(); x = np.frombuffer(w.readframes(n), '<i2').astype(np.float32) / 32768.
        if w.getnchannels() == 2: x = x.reshape(-1, 2).mean(1)
        return x, w.getframerate()


def trim_silence(x, thr=.012, pad=.04):
    idx = np.where(np.abs(x) > thr)[0]
    if not len(idx): return x
    a = max(0, idx[0] - int(pad * SR)); b = min(len(x), idx[-1] + int(pad * SR)); return x[a:b]


def synth_all(lines, outdir):
    """lines: [{id, speaker, text}] -> {id: {path, dur, speaker, text}} ; each line's leading and trailing silence is trimmed so the duration is the speech"""
    out = {}
    for L in lines:
        p = synth_line(L['speaker'], L['text'], outdir); x, sr = read_wav(p); x = trim_silence(x)
        tp = Path(outdir) / (p.stem + '_t.wav'); _write(tp, x)
        out[L['id']] = dict(path=str(tp), dur=len(x) / SR, speaker=L['speaker'], text=L['text'])
    return out


def _write(path, x):
    with wave.open(str(path), 'wb') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(x, -1, 1) * 32767).astype('<i2').tobytes())


def envelope(x, hz=30., win=.03):
    """voice amplitude 0..1 at `hz` values per second (RMS over `win`, normalised to the 98th percentile of the voiced stretches)"""
    n = int(len(x) / SR * hz) + 1; e = np.zeros(n)
    for i in range(n):
        a = int(i / hz * SR - win * SR / 2); b = int(i / hz * SR + win * SR / 2); seg = x[max(0, a):max(0, b)]
        e[i] = math.sqrt(float(np.mean(seg * seg))) if len(seg) else 0.
    ref = np.percentile(e[e > .01], 98) if (e > .01).any() else 1.; return np.clip(e / max(ref, 1e-6), 0, 1.2)


def assemble(placed, duration, outdir, gain=1.0):
    """placed: [(t0, line_dict)] -> writes voice.wav (mono, the whole film long) and {speaker}_env.json (30 Hz, film time); returns a report"""
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True); n = int((duration + 1.) * SR); mix = np.zeros(n, np.float32); per = {}
    for t0, L in placed:
        x, sr = read_wav(L['path']); i0 = int(t0 * SR); mix[i0:i0 + len(x)] += x[:max(0, n - i0)] * gain
        per.setdefault(L['speaker'], np.zeros(n, np.float32))[i0:i0 + len(x)] += x[:max(0, n - i0)]
    _write(outdir / 'voice.wav', np.clip(mix, -1, 1)); rep = dict(voice=str(outdir / 'voice.wav'), lines=len(placed), speakers={})
    for sp, x in per.items():
        e = envelope(x); p = outdir / f'{sp}_env.json'; p.write_text(json.dumps(dict(hz=30., env=[round(float(v), 3) for v in e])), encoding='utf-8'); rep['speakers'][sp] = dict(env=str(p), seconds=round(float((np.abs(x) > .01).sum() / SR), 2))
    return rep
