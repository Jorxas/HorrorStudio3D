"""Mix: ElevenLabs voice (+ per-line voice effects) + synthesized SFX cues + ambience bed + heartbeat,
ducked under the voice, then compressed and loudness-normalised to -14 LUFS (two-pass ffmpeg loudnorm).
Balance values are the ones validated on Étage Zéro part 3 v3 (voice clearly on top)."""
import os, json, math, wave, subprocess, tempfile, numpy as np
from . import synth as S
from . import music as M
from . import ambience as AMB
SR = S.SR

def rd(path):
    w = wave.open(path); n = w.getnframes(); ch = w.getnchannels()
    a = np.frombuffer(w.readframes(n), np.int16).astype(np.float32) / 32768
    return a.reshape(-1, ch).mean(1) if ch > 1 else a
def wr(path, a):
    a = a if a.ndim > 1 else a[:, None]
    pcm = (np.clip(a, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, 'wb') as o: o.setnchannels(pcm.shape[1]); o.setsampwidth(2); o.setframerate(SR); o.writeframes(pcm.tobytes())
def ff(cmd): subprocess.run(cmd, shell=True, check=True)

def pitch(f): return f"asetrate={int(SR * f)},aresample={SR},atempo={1 / f:.4f}"
VOICE_FX = {
    'double':  pitch(.917) + ",aecho=0.85:0.6:85|170:0.28|0.14",
    'creature': pitch(.8) + ",aecho=0.8:0.72:140|300|520:0.42|0.28|0.18,volume=1.2",
    'monster': pitch(.72) + ",aecho=0.8:0.75:140|300|520:0.45|0.3|0.2,volume=1.3",
    'inscription': f"asplit[a][b];[b]{pitch(.5)},volume=0.8[c];[a][c]amix=inputs=2:normalize=0,aecho=0.8:0.7:220|440:0.35|0.2",
    'console': "acrusher=bits=6:mode=log:aa=1:samples=4,highpass=f=250,lowpass=f=5000,volume=1.15",
    'muffled': "lowpass=f=900,aecho=0.8:0.6:60|120:0.3|0.15,volume=1.3",
    'phone': "highpass=f=320,lowpass=f=3300,acrusher=bits=10:mode=lin:samples=1,volume=1.2",
    'radio': "highpass=f=500,lowpass=f=2800,acrusher=bits=8:samples=2,volume=1.3",
    'echo': "aecho=0.8:0.7:180|360:0.35|0.2",
    'whisper': None,      # handled as an extra breathy layer
}
WHISPER_LAYER = {'creature', 'monster', 'whisper'}

class Mixer:
    def __init__(self, voice_path, lines, episode, duration, style, workdir):
        self.lines = lines; self.ep = episode; self.duration = duration; self.style = style; self.wd = workdir
        os.makedirs(workdir, exist_ok=True)
        self.N = int((duration + 1.0) * SR)
        ff(f'ffmpeg -v error -y -i "{voice_path}" -ac 1 -ar {SR} "{workdir}/voice44.wav"')
        v = rd(f'{workdir}/voice44.wav'); self.voice = np.zeros(self.N, np.float32); self.voice[:min(self.N, len(v))] = v[:self.N]
        self.L = np.zeros(self.N, np.float32); self.R = np.zeros(self.N, np.float32); self.REV = np.zeros(self.N, np.float32)
        S.reseed(int(episode.get('seed', 42)))
        from .. import profiles; profiles.apply(episode)         # "profile": "production" -> sfx_library entre autres
        from . import library as _library                        # real bruitages; opt-in per episode
        self.lib = _library.LIB; self.lib.seed = int(episode.get('seed', 42))
        # An episode that does not ask for the library keeps the synthesis it was validated with: a script written
        # before the library existed must not change sound on its own. `"sfx_library": true` opts in (the demos do),
        # and HSTUDIO_SFX_LIBRARY=1 opts in globally for a listening session without touching any episode file.
        self.lib.enabled = bool(episode.get('sfx_library', _library.env_default()))

    def put(self, sig, t, gain=1., pan=0., rev=.35):
        i = int(t * SR)
        if i >= self.N or len(sig) == 0: return
        if i < 0: sig = sig[-i:]; i = 0
        j = min(self.N, i + len(sig)); s = sig[:j - i] * gain
        self.L[i:j] += s * min(1, 1 - pan); self.R[i:j] += s * min(1, 1 + pan); self.REV[i:j] += s * rev

    # ---------------- voice effects
    def voice_fx(self):
        for li, ln in enumerate(self.lines):
            fx = ln.get('voice_fx')
            if not fx or fx == 'none': continue
            a = max(0, ln['start'] - .06); b = min(self.duration, ln['end'] + (1.0 if fx in ('creature', 'monster', 'inscription') else .5))
            i0, i1 = int(a * SR), int(b * SR)
            if i1 <= i0: continue
            filt = VOICE_FX.get(fx)
            if filt:
                wr(f'{self.wd}/fx_in.wav', self.voice[i0:i1])
                try:
                    ff(f'ffmpeg -v error -y -i "{self.wd}/fx_in.wav" -af "{filt}" -ar {SR} -ac 1 "{self.wd}/fx_out.wav"')
                    o = rd(f'{self.wd}/fx_out.wav')[:i1 - i0]; o = np.pad(o, (0, i1 - i0 - len(o)))
                    fade = np.ones(i1 - i0, np.float32); k = min(int(.02 * SR), (i1 - i0) // 2)
                    if k > 0: fade[:k] = np.linspace(0, 1, k); fade[-k:] = np.linspace(1, 0, k)
                    self.voice[i0:i1] = self.voice[i0:i1] * (1 - fade) + o * fade
                except subprocess.CalledProcessError:
                    pass
            if fx in WHISPER_LAYER:
                e = np.abs(self.voice[i0:i1]); k = int(.03 * SR); e = np.convolve(e, np.ones(k) / k, 'same')
                self.put(S.band(S.noise(i1 - i0), 2500, 9000) * e * 2.2, a, 1., 0, .6)

    # ---------------- cues
    def cue_time(self, cue, shot_t0):
        if 'line' in cue:
            li = max(0, min(int(cue['line']), len(self.lines) - 1))
            ln = self.lines[li]
            base = ln['end'] if cue.get('anchor') == 'end' else ln['start']
            return base + float(cue.get('offset', 0))
        return shot_t0 + float(cue.get('at', 0))

    def sfx_cues(self, spans):
        for k, shot in enumerate(self.ep['shots']):
            t0 = spans[k][0]
            for cue in (shot.get('sfx') or []):
                if isinstance(cue, str): cue = {'name': cue}
                t = self.cue_time(cue, t0); name = cue.get('name', '')
                sig = S.make(name, cue.get('dur'), at=t)
                rep = int(cue.get('repeat', 1)); gap = float(cue.get('gap', .5))
                for r in range(max(1, rep)):
                    tr = t + r * gap
                    # repeats (three knocks...) take another variant when the key has real samples; the
                    # procedural path keeps its single synthesis, so old episodes sound exactly as before
                    lib = getattr(self, 'lib', None)
                    s = sig if r == 0 or not (lib and lib.has(name)) else S.make(name, cue.get('dur'), at=tr)
                    self.put(s, tr, float(cue.get('gain', .8)), float(cue.get('pan', 0)), float(cue.get('reverb', .4)))
        for c in getattr(self, 'foley', None) or []:          # acting timeline: steps, objects, doors (acting/foley.py)
            self.put(S.make(c['name'], c.get('dur'), at=c['t']), c['t'], c.get('gain', .4), c.get('pan', 0.), .25)
        for li, ln in enumerate(self.lines):
            for cue in (ln.get('sfx') or []):
                if isinstance(cue, str): cue = {'name': cue}
                t = ln['start'] + float(cue.get('offset', 0))
                self.put(S.make(cue.get('name', ''), cue.get('dur'), at=t), t, float(cue.get('gain', .8)), float(cue.get('pan', 0)), float(cue.get('reverb', .4)))

    # ---------------- bed
    def intensity_curve(self, spans):
        t = np.arange(self.N) / SR
        xs, ys = [0.], [float(self.ep.get('intensity_start', .6))]
        for k, shot in enumerate(self.ep['shots']):
            a = shot.get('audio', {}) or {}
            if 'intensity' in a: xs.append(spans[k][0] + .01); ys.append(float(a['intensity']))
        xs.append(self.duration + 1); ys.append(ys[-1])
        return np.interp(t, xs, ys).astype(np.float32)

    def silence_mask(self, spans):
        mute = np.ones(self.N, np.float32)
        def drop(a, b, floor=0.):
            i, j = int(max(0, a) * SR), int(min(self.duration + 1, b) * SR); r = int(.03 * SR)
            if j <= i: return
            mute[i:j] = np.minimum(mute[i:j], floor)
            mute[max(0, i - r):i] = np.minimum(mute[max(0, i - r):i], np.linspace(1, floor, i - max(0, i - r)))
            mute[j:j + r] = np.minimum(mute[j:j + r], np.linspace(floor, 1, len(mute[j:j + r])))
        for k, shot in enumerate(self.ep['shots']):
            a = shot.get('audio', {}) or {}
            if a.get('silence'):
                s0, s1 = spans[k]
                f = float(a.get('silence_floor', 0.))
                if a.get('silence') == 'before_last_line' and shot['lines'][1] > shot['lines'][0]:
                    ln = self.lines[shot['lines'][1]]; drop(ln['start'] - .6, ln['start'] + .02, f)
                else: drop(s0 + float(a.get('silence_start', 0)), s0 + float(a.get('silence_end', s1 - s0)), f)
        for ln in self.lines:
            if ln.get('silence_before'): drop(ln['start'] - float(ln['silence_before']), ln['start'] + .02)
        return mute

    def music_map(self, spans):
        """per-sample music style: episode "music" (default horror), overridden per shot by audio.music"""
        base = self.ep.get('music') if self.ep.get('music') in M.NAMES else 'horror'
        names = [base]; ids = np.zeros(self.N, np.int16)
        for k, shot in enumerate(self.ep['shots']):
            m = (shot.get('audio', {}) or {}).get('music', base)
            if m not in M.NAMES: m = base
            if m not in names: names.append(m)
            ids[int(spans[k][0] * SR):int(spans[k][1] * SR)] = names.index(m)
        self.music_names, self.music_ids = names, ids
        return names, ids

    def ambience_track(self, spans):
        """place ambiences (birds, waves, city, rain...) with .5 s crossfades; nothing for the original horror episodes"""
        try: from ..engines.pixel3d.places import DEFAULT_AMBIENCE
        except Exception: DEFAULT_AMBIENCE = {}
        sets = self.ep.get('sets') or {}; base = self.ep.get('ambience')
        names = []; ids = np.full(self.N, -1, np.int16)
        for k, shot in enumerate(self.ep['shots']):
            a = (shot.get('audio', {}) or {}).get('ambience')
            if a is None:
                sp = sets.get(shot.get('set', self.ep.get('default_set', ''))) or {}
                w = shot.get('weather') or sp.get('weather') or self.ep.get('weather')
                a = sp.get('ambience') or ({'rain': 'rain', 'storm': 'storm', 'blizzard': 'wind'}.get(w)) or base or DEFAULT_AMBIENCE.get(sp.get('type'))
            if not a or a == 'none' or a not in AMB.AMBIENCES: continue
            if a not in names: names.append(a)
            ids[int(spans[k][0] * SR):int(spans[k][1] * SR)] = names.index(a)
        out = np.zeros(self.N, np.float32); w = int(.5 * SR)
        for i, name in enumerate(names):
            mask = np.convolve((ids == i).astype(np.float32), np.ones(w, np.float32) / w, 'same')
            tr = AMB.ambience(name, self.N, int(self.ep.get('music_seed', 0)) + i)
            tr *= .02 * float(self.ep.get('ambience_gain', 1.0)) / (float(np.sqrt((tr ** 2).mean())) + 1e-9)
            out += tr * mask
        return out

    def bed(self, intensity, mute):
        names, ids = self.music_names, self.music_ids
        if names == ['horror']: return self.horror_bed(intensity, mute)
        out = np.zeros(self.N, np.float32); w = int(.5 * SR)
        for i, name in enumerate(names):
            mask = np.convolve((ids == i).astype(np.float32), np.ones(w, np.float32) / w, 'same')      # .5 s crossfades
            if name == 'none' or not mask.any(): continue
            if name == 'horror': tr = self.horror_bed(intensity, np.ones(self.N, np.float32))
            else:                    # same loudness as the validated horror bed, so the voice stays on top
                tr = M.render(name, self.N, int(self.ep.get('music_seed', 0)), intensity)
                tr *= .03 * float(self.ep.get('music_gain', 1.0)) / (float(np.sqrt((tr ** 2).mean())) + 1e-9)
            out += tr * mask
        return out * mute

    def horror_bed(self, intensity, mute):
        N = self.N; t = np.arange(N) / SR
        if self.style == 'console':
            drone = (np.sin(2 * np.pi * 110 * t) * .5 + np.sin(2 * np.pi * 116.5 * t) * .35 + np.sin(2 * np.pi * 55 * t) * .4) * .03
            room = S.lp(S.brown(N), 200) * .25 + S.band(S.noise(N), 400, 3000) * .006
            chip = np.zeros(N, np.float32)
            notes = [440, 523.25, 659.25, 587.33, 523.25, 493.88, 440, 392]     # slow, slightly detuned lullaby (8-bit)
            step_ = .42; k = 0; tt = 1.0
            while tt < self.duration:
                f = notes[k % len(notes)] * (1 + .012 * math.sin(k * 1.7))
                S.addat(chip, int(tt * SR), S.chip_note(f, .36, .25, .05)); tt += step_; k += 1
            bed = (drone * (0.6 + .6 * intensity) + room + chip * (1.1 - .6 * intensity))
        else:
            rumble = S.lp(S.brown(N), 110)
            hum = np.zeros(N, np.float32)
            for k, a in ((1, 1.), (2, .55), (3, .35), (4, .22), (5, .12), (6, .08)): hum += a * np.sin(2 * np.pi * 100 * k * t + k)
            hum *= (1 + .25 * np.sin(2 * np.pi * .17 * t)) * .05
            drone = (np.sin(2 * np.pi * 277.2 * t + .4 * np.sin(2 * np.pi * .07 * t)) + .8 * np.sin(2 * np.pi * 293.7 * t) + .5 * np.sin(2 * np.pi * 311.1 * t + 1)
                     + .6 * np.sin(2 * np.pi * 138.6 * t)) * (.55 + .45 * np.sin(2 * np.pi * .045 * t)) * .035
            air = S.band(S.noise(N), 300, 2500) * .012
            tension = .4 + .8 * intensity
            bed = (rumble * .22 + hum * .7 + drone * tension + air) * tension
        calm = np.zeros(N, np.float32)
        for k, shot in enumerate(self.ep['shots']):
            a = shot.get('audio', {}) or {}
            if a.get('mood') == 'calm':
                pass
        return bed.astype(np.float32) * mute

    def calm_keys(self, spans):
        """soft melancholic piano for shots with audio.mood == 'calm' (epilogues)"""
        chords = [(220.0, 261.6, 329.6), (174.6, 220.0, 261.6), (196.0, 246.9, 293.7), (164.8, 207.7, 246.9)]
        def key_note(f, dur=3.5):
            n = int(dur * SR); t_ = np.arange(n) / SR
            s = (np.sin(2 * np.pi * f * t_) + .35 * np.sin(2 * np.pi * 2 * f * t_) + .12 * np.sin(2 * np.pi * 3 * f * t_)) * np.exp(-t_ * 1.3) * np.minimum(1, t_ / .005)
            return s.astype(np.float32) * .07
        ci = 0
        for k, shot in enumerate(self.ep['shots']):
            if (shot.get('audio', {}) or {}).get('mood') != 'calm': continue
            a, b = spans[k]; tt = a + .2
            while tt < b - .3:
                for j, f in enumerate(chords[ci % 4]): self.put(key_note(f), tt + j * .18, 1., (j - 1) * .3, .7)
                self.put(key_note(chords[ci % 4][0] / 2, 4.0), tt, .8, 0, .6); tt += 3.2; ci += 1

    def heartbeat_track(self, intensity, mute, spans):
        if self.ep.get('heartbeat', True) is False: return
        ids = getattr(self, 'music_ids', None); horror = [i for i, m in enumerate(getattr(self, 'music_names', ['horror'])) if m == 'horror']
        if self.ep.get('heartbeat') is not True and not horror: return
        calm = np.zeros(self.N, bool)
        for k, shot in enumerate(self.ep['shots']):
            if (shot.get('audio', {}) or {}).get('mood') == 'calm' or (shot.get('ui', {}) or {}).get('endcard'):
                calm[int(spans[k][0] * SR):int(spans[k][1] * SR)] = True
        tt = .6
        while tt < self.duration - 2:
            i = int(tt * SR)
            if i >= self.N: break
            if mute[i] > .5 and not calm[i] and (ids is None or self.ep.get('heartbeat') is True or int(ids[i]) in horror):
                self.put(S.heartbeat(.3 * (.6 + .6 * intensity[i])), tt, 1.0, 0, .12)
            bpm = 62 + 80 * float(intensity[i]); tt += 60. / bpm

    # ---------------- final mix
    def make_ir(self, dur=1.6, seed=0):
        r = np.random.default_rng(seed); n = int(dur * SR); t_ = np.arange(n) / SR
        ir = r.standard_normal(n).astype(np.float32) * np.exp(-t_ * 3.8); ir = S.lp(ir, 5000); ir[:int(.018 * SR)] = 0; return ir / np.abs(ir).sum() * 18
    def fconv(self, x, ir):
        n = len(x) + len(ir); nf = 1 << (n - 1).bit_length()
        return np.fft.irfft(np.fft.rfft(x, nf) * np.fft.rfft(ir, nf), nf)[:len(x)].astype(np.float32)

    def run(self, spans, out_path):
        self.voice_fx()
        self.sfx_cues(spans)
        intensity = self.intensity_curve(spans); mute = self.silence_mask(spans); self.music_map(spans)
        self.calm_keys(spans)
        self.heartbeat_track(intensity, mute, spans)
        bed = self.bed(intensity, mute)
        amb = self.ambience_track(spans) * mute
        revL = self.fconv(self.REV, self.make_ir(1.7, 1)); revR = self.fconv(self.REV, self.make_ir(1.7, 2))
        sfxL = self.L + revL * .35; sfxR = self.R + revR * .35
        ve = np.abs(self.voice); k = int(.04 * SR); ve = np.convolve(ve, np.ones(k) / k, 'same'); ve = np.convolve(ve, np.ones(k * 5) / (k * 5), 'same')
        duck = 1 - .62 * np.clip(ve / .025, 0, 1); sduck = 1 - .82 * np.clip(ve / .025, 0, 1)
        bedL = bed; bedR = np.roll(bed, 37)
        vrev = self.fconv(self.voice, self.make_ir(.9, 3)) * .12
        wr(f'{self.wd}/v_in.wav', self.voice)
        ff(f'ffmpeg -v error -y -i "{self.wd}/v_in.wav" -af acompressor=threshold=-22dB:ratio=3:attack=5:release=120:makeup=3dB "{self.wd}/v_out.wav"')
        vc = rd(f'{self.wd}/v_out.wav'); voice = np.pad(vc, (0, max(0, self.N - len(vc))))[:self.N] * float(self.ep.get('voice_gain', 1.3))
        bg = float(self.ep.get('background_gain', 1.0))
        bgL = (sfxL * .34 * sduck + bedL * .45 * duck + amb * .45 * sduck) * bg; bgR = (sfxR * .34 * sduck + bedR * .45 * duck + np.roll(amb, 53) * .45 * sduck) * bg
        mix = np.stack([voice + vrev + bgL, voice + vrev + bgR], 1)[:int((self.duration + .04) * SR)]
        mix = np.tanh(mix * 1.2) / 1.2
        wr(f'{self.wd}/mix_raw.wav', mix)
        loudnorm(f'{self.wd}/mix_raw.wav', out_path, self.wd)
        return out_path

def loudnorm(src, dst, wd, target=-14.0):
    ff(f'ffmpeg -v error -y -i "{src}" -af acompressor=threshold=-26dB:ratio=3.5:attack=8:release=250:makeup=5dB "{wd}/mix_comp.wav"')
    m = subprocess.run(f'ffmpeg -hide_banner -i "{wd}/mix_comp.wav" -af loudnorm=I={target}:TP=-1.5:LRA=11:print_format=json -f null -', shell=True, capture_output=True, text=True).stderr
    j = json.loads(m[m.rindex('{'):m.rindex('}') + 1])
    af = (f"loudnorm=I={target}:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}"
          f":measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
    ff(f'ffmpeg -v error -y -i "{wd}/mix_comp.wav" -af {af},alimiter=limit=0.89 -ar {SR} "{dst}"')
