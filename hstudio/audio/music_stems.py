"""CLIP MUSICAL avec les PISTES SÉPARÉES (voix, batterie, accompagnement) : phrases chantées et attaques de syllabes réelles,
premiers temps de mesure par grosse caisse + changements d'accord, et ancrage sur l'entrée du refrain.

    from hstudio.audio import music_stems as MS
    A = MS.analyse_with_stems('chanson.m4a', 'stems/', anchor=42.70)     # stems/ = sortie de tools/separate_voice.py

Repris du module « représentation musicale » (tools/analyze_music.py, refait le 31/10/2026 : l'original est perdu). Sans
pistes séparées, `music_analysis.analyse` donne une voix seulement ESTIMÉE ; ici elle est mesurée sur la voix seule."""
import math, os
import numpy as np
from . import music_analysis as MA


def voice_track(path, dur):
    """phrases chantées et attaques de syllabes, sur la voix SEULE"""
    y = MA.decode(path)
    S = MA._stft_mag(y)
    rms = np.sqrt((S ** 2).mean(1)); env = rms / (np.percentile(rms, 98) + 1e-9)
    envs = MA._smooth(env, int(.12 * MA.FPS))
    phrases = MA._runs(envs > .12, MA.FPS, .45, .35)
    f = np.linspace(0, MA.SR / 2, S.shape[1]); band = (f >= 150.) & (f <= 5000.)
    W, fc = MA._mel_bank(48, 150., 5000.)
    mel = np.log1p(20. * (S @ W.T)); flux = np.maximum(0., np.diff(mel, axis=0, prepend=mel[:1])).mean(1)
    flux = flux / (np.percentile(flux, 99) + 1e-9)
    ons = [i / MA.FPS for i in MA._peaks(flux, gap=int(.09 * MA.FPS), rel=.12, wmean=8)
           if envs[min(len(envs) - 1, i + 2)] > .1 and any(a - .05 <= i / MA.FPS <= b for a, b in phrases)]
    hz = 50; n = int(math.ceil(dur * hz)); idx = np.minimum(len(envs) - 1, (np.arange(n) / hz * MA.FPS).astype(int))
    r3 = lambda a: [round(float(x), 3) for x in a]
    return {'phrases': phrases, 'onsets': r3(ons), 'env': {'hz': hz, 'v': r3(np.clip(envs[idx], 0, 1))}, 'source': os.path.basename(path)}


def downbeats_from_bass(A, bass_path):
    """la phase de mesure (1 temps sur 4) dont les temps portent le plus d'attaques de basse SÉPARÉE"""
    y = MA.decode(bass_path); S = MA._stft_mag(y)
    W, _ = MA._mel_bank(24, 30., 300.)
    mel = np.log1p(10. * (S @ W.T)); fl = np.maximum(0., np.diff(mel, axis=0, prepend=mel[:1])).mean(1)
    b = np.array(A['beats']); idx = np.clip((b * MA.FPS).astype(int), 0, len(fl) - 1)
    near = lambda i: fl[max(0, i - 3):i + 4].max()
    sc = [float(np.mean([near(i) for i in idx[ph::4]])) for ph in range(4)]
    ph = int(np.argmax(sc))
    return [round(float(x), 3) for x in b[ph::4]], sc


def _chroma(S, fmin=60., fmax=2000.):
    f = np.linspace(0, MA.SR / 2, S.shape[1]); ok = (f >= fmin) & (f <= fmax)
    pc = np.round(12 * np.log2(f[ok] / 440.)).astype(int) % 12
    C = np.zeros((S.shape[0], 12), np.float32)
    for k in range(12): C[:, k] = (S[:, ok][:, pc == k] ** 2).sum(1)
    return C / (np.linalg.norm(C, axis=1, keepdims=True) + 1e-9)


def downbeats_from_stems(A, stems):
    """la phase de mesure dont les temps portent à la fois la grosse caisse (batterie séparée) et les changements
    d'accord (accompagnement séparé) : un premier temps est là où l'harmonie change et où la caisse frappe"""
    b = np.array(A['beats']); bi = (b * MA.FPS).astype(int)
    feats = []
    drums = os.path.join(stems, 'drums.wav')
    if os.path.exists(drums):
        S = MA._stft_mag(MA.decode(drums)); W, _ = MA._mel_bank(16, 30., 150.)
        mel = np.log1p(10. * (S @ W.T)); fl = np.maximum(0., np.diff(mel, axis=0, prepend=mel[:1])).mean(1)
        k = np.array([fl[max(0, i - 3):i + 4].max() for i in np.clip(bi, 0, len(fl) - 1)]); feats.append(k / (k.mean() + 1e-9))
    acc = os.path.join(stems, 'accompagnement.wav')
    if os.path.exists(acc):
        C = _chroma(MA._stft_mag(MA.decode(acc))); n = len(C); bi2 = np.clip(bi, 1, n - 1)
        h = np.zeros(len(b))
        for j in range(1, len(b) - 1):
            pre = C[bi2[j - 1]:bi2[j]].mean(0); post = C[bi2[j]:bi2[j + 1]].mean(0)
            h[j] = 1. - float(pre @ post / (np.linalg.norm(pre) * np.linalg.norm(post) + 1e-9))
        feats.append(h / (h.mean() + 1e-9))
    if not feats: return None, None
    F = np.sum(feats, 0)
    sc = [float(F[ph::4].mean()) for ph in range(4)]; ph = int(np.argmax(sc))
    return [round(float(x), 3) for x in b[ph::4]], sc


def analyse_with_stems(song, stems_dir, anchor=None):
    """analyse de la chanson ENTIÈRE avec ses pistes séparées -> même format que music_analysis.analyse, `vocal` mesuré.
    `anchor` : un instant qu'on SAIT être un premier temps (l'entrée du refrain) : il fixe la phase de mesure quand la
    batterie, la basse et les accords ne la départagent pas (ballade). Le suivi de temps peut glisser d'une section à l'autre :
    l'ancre vaut pour la minute qui l'entoure."""
    voice = os.path.join(stems_dir, 'voix.wav')
    if not os.path.exists(voice): raise FileNotFoundError(f"{voice} : lance d'abord tools/separate_voice.py")
    A = MA.analyse(song)
    A['vocal'] = voice_track(voice, A['duration'])
    d, sc = downbeats_from_stems(A, stems_dir)
    if anchor is not None:
        b = A['beats']; ia = min(range(len(b)), key=lambda i: abs(b[i] - anchor))
        A['downbeats'] = [b[i] for i in range(ia % 4, len(b), 4)]; A['downbeats_from'] = f'ancre {anchor} s (temps n°{ia})'
    elif d:
        A['downbeats'] = d; A['downbeats_from'] = "grosse caisse + changements d'accord (pistes séparées) " + str([round(x, 3) for x in sc])
    A['method'] = MA.__doc__.splitlines()[0] + ' ; voix et batterie séparées (tools/separate_voice.py)'
    return A
