"""Analyse d'une musique pour le CLIP MUSICAL : tempo, temps, premiers temps de mesure, attaques, énergie,
sections, silences et phrases chantées (estimées).

    from hstudio.audio import music_analysis as MA
    A = MA.analyse('chanson.mp3', start=46.0, end=105.9)      # -> dict, temps relatifs au début de l'extrait
    MA.save(A, 'analysis.json')

Le format est celui de l'ancien module « représentation musicale » de moteur_voxel (engine/assets/analysis.json,
lu par engine/music.js) : `tempo`, `beat_period`, `beats`, `downbeats`, `onsets`, `energy {hz, v}`, `sections`,
`vocal {phrases, onsets, env}`, `duration`. Ajouts : `silences`, `climax`, `meter`, `method`.

numpy et ffmpeg seulement (le script d'origine, `tools/analyze_music.py`, n'a jamais été retrouvé). Déterministe :
la même musique donne le même fichier. Méthode, nommée pour qu'on sache ce qu'elle vaut :
  - attaques : flux spectral positif sur 64 bandes (échelle de Mel), sommé ;
  - tempo : les sommets de l'autocorrélation de ce flux, départagés par la force des attaques SUR les temps
    (un extrait s'analyse dans la chanson entière puis se découpe, `excerpt`) ;
  - temps : programmation dynamique d'Ellis (2007), le suivi de temps classique ;
  - premiers temps : mesure à 4 temps, la phase dont les temps portent le plus de basses ;
  - sections : rupture entre les 4 mesures avant et les 4 après (énergie, brillance, densité d'attaques) ;
  - voix : SANS séparation de sources -- la part d'énergie dans la bande 250-3500 Hz quand elle est soutenue.
    Sur un morceau instrumental, une mélodie dans cette bande sera prise pour une voix : c'est une estimation.
"""
import json, math, subprocess
import numpy as np

SR = 22050
HOP = 512
NFFT = 2048
FPS = SR / HOP              # images d'analyse par seconde (~43)


def decode(path, start=None, end=None, sr=SR):
    """-> mono float32 à `sr`, l'extrait [start, end] seulement (ffmpeg lit tout ce qu'il connaît)"""
    cmd = ['ffmpeg', '-v', 'error']
    if start: cmd += ['-ss', f'{float(start):.3f}']
    cmd += ['-i', str(path)]
    if end is not None: cmd += ['-t', f'{float(end) - float(start or 0.):.3f}']
    cmd += ['-ac', '1', '-ar', str(sr), '-f', 'f32le', '-']
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def _stft_mag(y):
    pad = NFFT // 2; y = np.pad(y.astype(np.float32), (pad, pad))
    n = max(1, 1 + (len(y) - NFFT) // HOP)
    win = np.hanning(NFFT).astype(np.float32)
    out = np.empty((n, NFFT // 2 + 1), np.float32)
    st = y.strides[0]
    for a in range(0, n, 1024):
        b = min(n, a + 1024)
        fr = np.lib.stride_tricks.as_strided(y[a * HOP:], shape=(b - a, NFFT), strides=(st * HOP, st))
        out[a:b] = np.abs(np.fft.rfft(fr * win, axis=1))
    return out


def _mel_bank(nb=64, fmin=30., fmax=8000.):
    mel = lambda f: 2595. * np.log10(1. + f / 700.)
    imel = lambda m: 700. * (10 ** (m / 2595.) - 1.)
    pts = imel(np.linspace(mel(fmin), mel(fmax), nb + 2))
    freqs = np.linspace(0, SR / 2, NFFT // 2 + 1)
    W = np.zeros((nb, len(freqs)), np.float32)
    for i in range(nb):
        a, c, b = pts[i], pts[i + 1], pts[i + 2]
        W[i] = np.clip(np.minimum((freqs - a) / max(c - a, 1e-6), (b - freqs) / max(b - c, 1e-6)), 0, None)
    return W, (pts[1:-1])


def _smooth(x, w):
    if w <= 1: return x
    k = np.hanning(w + 2)[1:-1]; k /= k.sum()
    return np.convolve(x, k, mode='same')


def _tempo_candidates(o, lo=50., hi=200., center=100., k=4):
    """les `k` meilleurs sommets de l'autocorrélation du flux (pondérée autour de `center`), en BPM"""
    o = o - o.mean()
    ac = np.correlate(o, o, mode='full')[len(o) - 1:]
    lags = np.arange(len(ac)); bpm = np.where(lags > 0, 60. * FPS / np.maximum(lags, 1), 0.)
    ok = (bpm >= lo) & (bpm <= hi)
    score = np.where(ok, ac * np.exp(-.5 * (np.log2(np.maximum(bpm, 1e-6) / center)) ** 2), -np.inf)
    tops = [L for L in range(2, len(ac) - 1) if ok[L] and score[L] > 0 and score[L] >= score[L - 1] and score[L] >= score[L + 1]]
    out = []
    for L in sorted(tops, key=lambda L: -score[L])[:k]:
        a, b, c = ac[L - 1], ac[L], ac[L + 1]; d = a - 2 * b + c         # sommet parabolique : le tempo n'est pas arrondi à l'image
        out.append(60. * FPS / (L + (.5 * (a - c) / d if abs(d) > 1e-12 else 0.)))
    return out or [center]


def _choose_tempo(o, center=100.):
    """le plus haut sommet pondéré. Mesuré juste sur des morceaux ENTIERS (96, 80 et 78,6 BPM retrouvés), faux sur
    un extrait court au début clairsemé (une ballade à 78 BPM prise pour 123) : un extrait s'analyse donc dans la
    chanson entière, puis se découpe (`excerpt`). Départager par la force des attaques sur les temps a été essayé
    et rejeté : le rapport « sur les temps / entre les temps » explose dès que l'entre-deux est silencieux."""
    return _tempo_candidates(o, center=center, k=1)[0]


def _onset(y):
    S = _stft_mag(y)
    W, fc = _mel_bank()
    mel = np.log1p(10. * (S @ W.T))                                       # (images, 64)
    flux = np.maximum(0., np.diff(mel, axis=0, prepend=mel[:1]))
    o = flux.mean(axis=1)
    o = np.maximum(0., o - _smooth(o, int(FPS)))                          # retire la pente lente (crescendos)
    return S, flux, o, fc


def excerpt(A, start, end=None):
    """l'analyse d'une chanson ENTIÈRE -> celle de l'extrait [start, end], temps ramenés à 0 au début de l'extrait.
    Le tempo, les temps et la place des premiers temps viennent de toute la chanson (plus sûr qu'un extrait seul) ;
    l'énergie reste relative à toute la chanson, donc « calme » / « fort » gardent leur sens d'un extrait à l'autre."""
    start = float(start or 0.); end = float(A['duration']) if not end else min(float(end), float(A['duration']))
    r3 = lambda x: round(float(x), 3)
    pts = lambda xs: [r3(x - start) for x in xs if start <= x < end]
    spans = lambda xs: [[r3(max(a, start) - start), r3(min(b, end) - start)] for a, b in xs if b > start and a < end]
    hz = A['energy']['hz']; v = A['energy']['v'][int(start * hz):int(math.ceil(end * hz))]
    vo = A['vocal']; vh = vo['env']['hz']
    secs = [dict(s, t0=r3(max(s['t0'], start) - start), t1=r3(min(s['t1'], end) - start)) for s in A['sections'] if s['t1'] > start and s['t0'] < end]
    sm = _smooth(np.array(v, float), 2 * int(hz)) if len(v) else np.zeros(1)
    return dict(A, beats=pts(A['beats']), downbeats=pts(A['downbeats']), onsets=pts(A['onsets']), sections=secs,
                silences=spans(A['silences']), climax=round(float(np.argmax(sm)) / hz, 2), energy={'hz': hz, 'v': v},
                duration=r3(end - start), excerpt={'start': r3(start), 'end': r3(end)},
                vocal={'phrases': spans(vo['phrases']), 'onsets': pts(vo['onsets']),
                       'env': {'hz': vh, 'v': vo['env']['v'][int(start * vh):int(math.ceil(end * vh))]}})


def _beats(o, tempo, tight=100.):
    period = 60. * FPS / tempo
    o = o / (o.std() + 1e-9)
    g = np.arange(-int(period), int(period) + 1)
    local = np.convolve(o, np.exp(-.5 * (g * 32. / period) ** 2), mode='same')
    n = len(local); cum = np.zeros(n); back = -np.ones(n, int)
    wr = np.arange(-int(round(2 * period)), -int(round(period / 2)) + 1)
    txc = -tight * np.log(-wr / period) ** 2
    for t in range(n):
        idx = t + wr; m = idx >= 0
        if not m.any(): cum[t] = local[t]; continue
        z = cum[idx[m]] + txc[m]; k = int(np.argmax(z))
        cum[t] = local[t] + z[k]; back[t] = idx[m][k]
    mx = [t for t in range(1, n - 1) if cum[t] >= cum[t - 1] and cum[t] >= cum[t + 1]]
    if not mx: return np.array([], int), local
    med = np.median(cum[mx]); end = max(t for t in mx if cum[t] >= .5 * med)
    out = [end]
    while back[out[-1]] >= 0: out.append(back[out[-1]])
    return np.array(out[::-1], int), local


def _peaks(x, gap, rel=.1, wmean=10):
    m = np.convolve(x, np.ones(2 * wmean + 1) / (2 * wmean + 1), mode='same')
    out = []; last = -10 ** 9
    for i in range(3, len(x) - 3):
        if x[i] == x[i - 3:i + 4].max() and x[i] > m[i] + rel and i - last >= gap:
            out.append(i); last = i
    return out


def _runs(mask, hz, min_len, join=0.):
    """intervalles [t0, t1] où `mask` est vrai au moins `min_len` s (trous de moins de `join` s recollés)"""
    runs = []; i = 0; n = len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j < n and mask[j]: j += 1
            runs.append([i / hz, j / hz]); i = j
        else: i += 1
    merged = []
    for r in runs:
        if merged and r[0] - merged[-1][1] < join: merged[-1][1] = r[1]
        else: merged.append(list(r))
    return [[round(a, 3), round(b, 3)] for a, b in merged if b - a >= min_len]


def analyse(path, start=None, end=None, tempo=None):
    """`tempo` : imposé si on le connaît ; sinon choisi sur le fichier (pour un extrait, voir `excerpt`)"""
    y = decode(path, start, end)
    if len(y) < SR: raise ValueError('musique trop courte (moins d\'une seconde)')
    dur = len(y) / SR
    S, flux, o, fc = _onset(y)
    bass = flux[:, fc < 200.].mean(axis=1)

    tempo = float(tempo) if tempo else _choose_tempo(o)
    bidx, local = _beats(o, tempo)
    rms = np.sqrt((S ** 2).mean(axis=1)) if len(S) else np.zeros(1)
    e_frame = rms / (np.percentile(rms, 98) + 1e-9)
    # énergie à 10 Hz, 0..1
    hz = 10; ne = int(math.ceil(dur * hz))
    fi = np.minimum(len(e_frame) - 1, (np.arange(ne) / hz * FPS).astype(int))
    energy = np.clip(_smooth(e_frame, 5)[fi], 0, 1)
    # les temps posés dans le silence ne sont pas des temps
    loud = e_frame > .04
    bidx = np.array([b for b in bidx if loud[max(0, b - 4):b + 5].any()], int)
    beats = bidx / FPS
    period = float(np.median(np.diff(beats))) if len(beats) > 2 else 60. / tempo

    # premiers temps de mesure (4/4) : la phase la plus chargée en basses
    downs = []
    if len(bidx) >= 8:
        sc = [float(np.mean([bass[max(0, b - 2):b + 3].max() + .5 * local[b] / (local.max() + 1e-9) for b in bidx[ph::4]])) for ph in range(4)]
        ph = int(np.argmax(sc)); downs = beats[ph::4]
    onsets = np.array(_peaks(o / (np.percentile(o, 99) + 1e-9), gap=int(.1 * FPS))) / FPS

    # sections : ruptures entre mesures
    sections = []
    db = list(downs) if len(downs) >= 3 else list(np.arange(0., dur, 4 * period))
    edges = [0.] + [d for d in db if 0. < d < dur] + [dur]
    cen = (S * np.arange(S.shape[1])).sum(1) / (S.sum(1) + 1e-9); cen = cen / (cen.max() + 1e-9)
    feat = []
    for a, b in zip(edges[:-1], edges[1:]):
        i0, i1 = int(a * FPS), max(int(a * FPS) + 1, int(b * FPS))
        dens = len([x for x in onsets if a <= x < b]) / max(b - a, 1e-3)
        feat.append([float(e_frame[i0:i1].mean()), float(cen[i0:i1].mean()), min(1., dens / 6.)])
    feat = np.array(feat); nb = len(feat); K = 4
    nov = np.zeros(nb)
    for k in range(2, nb - 1):
        a = feat[max(0, k - K):k].mean(0); b = feat[k:k + K].mean(0)
        nov[k] = float(np.linalg.norm((a - b) * [2., 1., 1.]))
    cut = []
    thr = nov.mean() + .5 * nov.std() if nb > 4 else 1e9
    for k in np.argsort(-nov):
        if nov[k] < thr: break
        if all(abs(k - c) >= K for c in cut): cut.append(int(k))
    bounds = sorted(float(edges[k]) for k in cut)
    for a_, b_ in _runs(energy < .06, hz, .8):                           # une reprise après un vrai silence ouvre une section
        if .5 < b_ < dur - 1.:
            bounds = [x for x in bounds if abs(x - b_) > 2.5 * period] + [float(b_)]
    bounds = [0.] + sorted(bounds) + [float(dur)]
    e_mean = []
    for a, b in zip(bounds[:-1], bounds[1:]):
        e_mean.append(float(energy[int(a * hz):max(int(a * hz) + 1, int(b * hz))].mean()))
    order = sorted(range(len(e_mean)), key=lambda i: e_mean[i]); rank = {i: r for r, i in enumerate(order)}
    flat = (max(e_mean) - min(e_mean)) < .08                                # tout au même niveau : rien n'est « fort »
    for i, ((a, b), e) in enumerate(zip(zip(bounds[:-1], bounds[1:]), e_mean)):
        fr = rank[i] / max(1, len(e_mean) - 1)
        lvl = 'moyen' if flat else ('calme' if fr < 1 / 3 else ('fort' if fr > 2 / 3 else 'moyen'))
        sections.append({'t0': round(a, 3), 't1': round(b, 3), 'energy': round(e, 3), 'niveau': lvl})

    # voix (estimée) : part d'énergie de la bande 250-3500 Hz, soutenue
    f = np.linspace(0, SR / 2, S.shape[1]); band = (f >= 250.) & (f <= 3500.)
    P = S ** 2; ratio = P[:, band].sum(1) / (P.sum(1) + 1e-9)
    vz = _smooth(ratio * (e_frame > .08), int(.25 * FPS))
    thr_v = float(np.percentile(vz, 40)) + .15 * float(vz.std())
    phrases = _runs(vz > thr_v, FPS, .8, .35)
    vflux = np.maximum(0., np.diff(np.log1p(10 * P[:, band].sum(1) ** .5), prepend=0.))
    von = [i / FPS for i in _peaks(vflux / (np.percentile(vflux, 99) + 1e-9), gap=int(.12 * FPS))
           if any(a <= i / FPS <= b for a, b in phrases)]
    vh = 50; nv = int(math.ceil(dur * vh)); vi = np.minimum(len(vz) - 1, (np.arange(nv) / vh * FPS).astype(int))
    venv = np.clip(vz[vi] / (vz.max() + 1e-9), 0, 1)

    silences = _runs(energy < .06, hz, .3)
    sm = _smooth(energy, 2 * hz)
    r3 = lambda a: [round(float(x), 3) for x in a]
    return {
        'tempo': round(float(60. / period if len(beats) > 2 else tempo), 2), 'beat_period': round(period, 4), 'meter': 4,
        'beats': r3(beats), 'downbeats': r3(downs), 'onsets': r3(onsets),
        'sections': sections, 'silences': silences, 'climax': round(float(np.argmax(sm)) / hz, 2),
        'energy': {'hz': hz, 'v': r3(energy)}, 'duration': round(dur, 3),
        'vocal': {'phrases': phrases, 'onsets': r3(von), 'env': {'hz': vh, 'v': r3(venv)}},
        'method': 'numpy : flux spectral Mel, autocorrélation, suivi de temps d\'Ellis ; voix estimée sans séparation',
    }


def save(A, path):
    with open(path, 'w', encoding='utf-8') as fh: json.dump(A, fh, ensure_ascii=False, separators=(',', ':'))
    return path
