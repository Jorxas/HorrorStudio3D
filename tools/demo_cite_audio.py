"""Compose the sound of « Le Dernier Noyau » (music, ambiences, SFX, steps, dialogue with ducking) from the built contract and measure it. usage: python tools/demo_cite_audio.py"""
import json, subprocess, sys, wave
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu import audio, contract as C
WORK = ROOT / 'projects' / 'demo_narrative_20261029'
c = C.load(WORK / 'contract.json'); out = WORK / 'audio.wav'
audio.compose(c, out)
with wave.open(str(out)) as w: n = w.getnframes(); sr = w.getframerate(); x = np.frombuffer(w.readframes(n), '<i2').astype(np.float32).reshape(-1, 2).mean(1) / 32768.
print('audio', round(n / sr, 2), 's, crête', round(float(np.abs(x).max()), 3), ', RMS', round(float(np.sqrt((x * x).mean())), 4))
r = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(out), '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True); print([l for l in r.stderr.splitlines() if 'I:' in l or 'Peak' in l][-2:])
# the voice must stay clearly above the bed: compare the RMS of the voice track alone and of the whole mix in the voiced stretches
v = WORK / 'voice_mix' / 'voice.wav'
with wave.open(str(v)) as w: vn = w.getnframes(); vx = np.frombuffer(w.readframes(vn), '<i2').astype(np.float32) / 32768.
m = min(len(vx), len(x)); act = np.abs(vx[:m]) > .01
print('voix : %.1f %% du film parlé ; RMS voix %.4f, RMS mélange pendant la voix %.4f, RMS mélange hors voix %.4f' % (100 * act.mean(), np.sqrt((vx[:m][act] ** 2).mean()), np.sqrt((x[:m][act] ** 2).mean()), np.sqrt((x[:m][~act] ** 2).mean())))
