"""Preuve audible A/B de la mise en scene sonore narrative (hstudio/audio/soundscape.py).

    python tools/soundscape_ab.py [--shots 21] [--episode examples/etage_zero_partie4] [--mp3]

Meme episode, meme voix locale (examples/etage_zero_partie4/voice.mp3, deja au depot), meme mixeur,
meme banque de bruitages CC0 activee des deux cotes. La SEULE difference entre A et B est le plan
produit par soundscape.plan() a partir du script :

  A  narration + sons actuels           (ce que le studio sort aujourd'hui : aucune ambiance,
                                         intensite fixe, aucun evenement en plus de ceux ecrits a la main)
  B  narration + mise en scene sonore   (ambiances contextuelles par espace, courbe de tension,
                                         silence anormal, evenements synchronises et spatialises)

Rien n'est reimplemente : ensure_ffmpeg / load_episode / cut_voice / rd viennent de
tools/sfx_episode_ab.py, le son de hstudio/audio/{synth,library,ambience}.py, le mix de
hstudio/audio/mixer.py (inchange). Aucun appel reseau, aucune API payante.
"""
import hashlib, json, os, shutil, subprocess, sys, tempfile, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

import hstudio.audio                                     # noqa: installe le provider de bruitages
from hstudio.audio import synth as S, library as L, mixer as MX, soundscape as SS
import sfx_episode_ab as AB                              # reuse: ffmpeg, chargement episode, lecture wav

SR = S.SR
OUT = os.path.join(ROOT, 'docs', 'audio_cinematique')


# ------------------------------------------------------------------ mesures
def loudness(path):
    """LUFS integre + true peak, mesures par ffmpeg (ebur128)"""
    r = subprocess.run(f'ffmpeg -hide_banner -nostats -i "{path}" -af ebur128=peak=true -f null -',
                       shell=True, capture_output=True, text=True).stderr
    tail = r[r.rfind('Integrated loudness'):] if 'Integrated loudness' in r else ''
    def grab(key):
        for ln in tail.splitlines():
            if ln.strip().startswith(key):
                try: return float(ln.split(':')[1].strip().split()[0])
                except Exception: return None
        return None
    return dict(lufs_i=grab('I:'), lra=grab('LRA:'), true_peak_dbtp=grab('Peak:'))


def rd2(path):
    """lecture stereo (L, R) sans moyenner les canaux : le panoramique doit rester mesurable"""
    import wave
    with wave.open(path) as w:
        ch = w.getnchannels(); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    a = a.reshape(-1, ch)
    return (a[:, 0], a[:, 1]) if ch > 1 else (a[:, 0], a[:, 0])


def rms(x):
    x = np.asarray(x, np.float64)
    return float(np.sqrt((x ** 2).mean())) if x.size else 0.


def db(x): return 20 * np.log10(max(x, 1e-12))
def d_db(b, a): return round(float(db(b) - db(a)), 2)


def voice_mask(lines, n):
    """echantillons ou la narration parle (segments ElevenLabs quand ils existent)"""
    m = np.zeros(n, bool)
    for l in lines:
        for a, b in (l.get('segs') or [[l['start'], l['end']]]):
            m[max(0, int(a * SR)):min(n, int(b * SR))] = True
    return m


def win(x, t0, t1):
    return x[max(0, int(t0 * SR)):max(0, int(t1 * SR))]


OCT_EDGES = (63, 125, 250, 500, 1000, 2000, 4000, 8000)
OCT_LABELS = '63|125|250|500|1k|2k|4k Hz'

def octaves(x, ref=None):
    """energie par octave, en dB : la signature spectrale d'un espace (une rue n'a pas le profil
    d'une cave). Mesure sur le signal difference, donc sur ce que la mise en scene a ajoute."""
    x = np.asarray(x, np.float64)
    if x.size < 64: return []
    X = np.abs(np.fft.rfft(x)) ** 2; f = np.fft.rfftfreq(x.size, 1 / SR)
    tot = X.sum() + 1e-20
    return [round(float(10 * np.log10(X[(f >= lo) & (f < hi)].sum() / tot + 1e-20)), 1)
            for lo, hi in zip(OCT_EDGES[:-1], OCT_EDGES[1:])]


# ------------------------------------------------------------------ mix
def mix(ep, lines, spans, dur, voice, out, tag):
    """un mix complet par le mixeur existant ; bibliotheque de bruitages ON des deux cotes"""
    ep = dict(ep, sfx_library=True)
    wd = os.path.join(tempfile.gettempdir(), f'hstudio_ss_{tag}')
    shutil.rmtree(wd, ignore_errors=True); os.makedirs(wd, exist_ok=True)
    L.LIB.used = {}
    t0 = time.time()
    MX.Mixer(voice, lines, ep, dur, ep.get('style', 'pixel3d'), wd).run(spans, out)
    secs = time.time() - t0
    shutil.rmtree(wd, ignore_errors=True)
    return dict(L.LIB.used), secs


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''): h.update(c)
    return h.hexdigest()


def main():
    av = sys.argv[1:]
    n_shots = int(av[av.index('--shots') + 1]) if '--shots' in av else 21
    root = av[av.index('--episode') + 1] if '--episode' in av else os.path.join('examples', 'etage_zero_partie4')
    root = root if os.path.isabs(root) else os.path.join(ROOT, root)
    os.makedirs(OUT, exist_ok=True)
    print(f'ffmpeg : {AB.ensure_ffmpeg()}')

    ep, lines, spans, dur = AB.load_episode(root, n_shots)
    script = [l.rstrip('\n') for l in open(os.path.join(root, 'script.txt'), encoding='utf-8')]
    print(f"episode {os.path.basename(root)} : {len(ep['shots'])} plans, {len(lines)} repliques, {dur:.2f} s")

    # ---- le plan, deduit du script seul
    t0 = time.time()
    pl = SS.plan(ep, lines, spans, script=script)
    plan_ms = (time.time() - t0) * 1000
    ep_b = pl.apply(ep)
    print(f"\nplan ({plan_ms:.1f} ms, preset {pl.preset}) : {len(pl.beats)} beats, {len(pl.zones)} espaces, "
          f"{len(pl.cues)} evenements, {len(pl.silences)} fenetres de silence")
    print(pl.storyboard())

    cues_a = sum(len(s.get('sfx') or []) for s in ep['shots'])
    cues_b = sum(len(s.get('sfx') or []) for s in ep_b['shots'])
    print(f"\ncues sfx : A {cues_a} (ecrites a la main) -> B {cues_b} (+{cues_b - cues_a} posees par le plan)")
    covered = sorted({c['name'] for c in pl.cues if L.LIB.has(c['name'])})
    print(f"evenements du plan servis par un vrai bruitage CC0 : {covered or 'aucun'}")

    # ---- deux mixes
    voice = os.path.join(tempfile.gettempdir(), 'hstudio_ss_voice.wav')
    AB.cut_voice(os.path.join(root, 'voice.mp3'), voice, dur)
    res = {}
    reuse = '--reuse' in av            # remesurer sans remixer (les autres worktrees calculent aussi)
    for name, e in (('A_actuel', ep), ('B_soundscape', ep_b)):
        p = os.path.join(OUT, f'{name}.wav')
        remixed = True
        if reuse and os.path.exists(p):
            used, secs, remixed = {}, None, False      # None, pas 0 : on n'a pas mesure, on n'invente pas
            print(f'  {name}: mix existant reutilise (--reuse)')
        else:
            used, secs = mix(e, lines, spans, dur, voice, p, name)
        lo = loudness(p); l_, r_ = rd2(p); m = (l_ + r_) / 2
        res[name] = dict(wav=p, remixe_ici=remixed,
                         seconds_to_mix=round(secs, 1) if secs is not None else None,
                         samples=len(m), sha256=sha(p),
                         rms=round(rms(m), 6), peak=round(float(np.abs(m).max()), 4),
                         peak_dbfs=round(db(float(np.abs(m).max())), 2),
                         clipped_samples=int((np.abs(np.stack([l_, r_])) >= .999).sum()),
                         used_library_samples=sum(used.values()) if remixed else None, **lo)
        print(f"\n{name}: {f'{secs:.1f} s de calcul' if secs is not None else 'mix reutilise'} | "
              f"LUFS {lo['lufs_i']} | true peak {lo['true_peak_dbtp']} dBTP | "
              f"pic {res[name]['peak_dbfs']:.2f} dBFS | clipping {res[name]['clipped_samples']} ech."
              f"{f' | bruitages reels servis {sum(used.values())}' if remixed else ''}")

    # ---- comparaisons
    la, ra = rd2(res['A_actuel']['wav']); lb, rb = rd2(res['B_soundscape']['wav'])
    n = min(len(la), len(lb)); la, ra, lb, rb = la[:n], ra[:n], lb[:n], rb[:n]
    a, b = (la + ra) / 2, (lb + rb) / 2
    vm = voice_mask(lines, n)

    cmp = dict(identical=bool(np.array_equal(a, b)),
               delta_global_db=d_db(rms(b), rms(a)),
               delta_pendant_voix_db=d_db(rms(b[vm]), rms(a[vm])),
               delta_hors_voix_db=d_db(rms(b[~vm]), rms(a[~vm])))
    print(f"\nA vs B : identiques ? {'oui' if cmp['identical'] else 'non'} | global {cmp['delta_global_db']:+.2f} dB | "
          f"pendant la narration {cmp['delta_pendant_voix_db']:+.2f} dB | hors narration {cmp['delta_hors_voix_db']:+.2f} dB")

    # ambiances : chaque espace doit avoir sa propre couleur (pas le meme fond partout).
    # On mesure dans les TROUS de narration : c'est la, et seulement la, que l'auditeur entend le fond.
    gaps = SS.narration_gaps(lines)
    gm = np.zeros(n, bool)
    for g0, g1 in gaps: gm[max(0, int(g0 * SR)):min(n, int(g1 * SR))] = True
    print(f"\ntrous de narration : {gm.sum() / SR:.1f} s sur {n / SR:.1f} s ({100 * gm.sum() / n:.0f} %)")
    # A et B sont tous deux normalises a -14 LUFS : comparer les niveaux absolus d'une zone est
    # trompeur (ajouter du son dans B fait baisser tout le reste de B au loudnorm). On mesure donc le
    # RAPPORT fond / narration propre a chaque mix, qui est invariant a la normalisation et qui est
    # exactement ce que l'oreille juge : "est-ce que j'entends quelque chose derriere la voix ?"
    ref_a, ref_b = rms(a[vm]), rms(b[vm])          # niveau de la narration dans chaque mix
    print(f"reference narration : A {db(ref_a):.2f} dBFS | B {db(ref_b):.2f} dBFS "
          f"(ecart {d_db(ref_b, ref_a):+.2f} dB : la voix reste au meme niveau)")

    # Le fond d'un mix est domine par les transitoires fortes (battements de coeur, cues ecrites a la
    # main) : un lit d'ambiance pose 18 dB sous le dialogue - ce qui est le bon niveau - ne deplace
    # presque pas le rms large bande. Pour mesurer ce que la mise en scene AJOUTE reellement, on
    # egalise les deux mixes sur la narration (la voix est la meme des deux cotes) et on soustrait :
    # le signal DIFFERENCE isole exactement les ambiances et les evenements ajoutes.
    k = ref_a / max(ref_b, 1e-12)
    dl, dr = lb * k - la, rb * k - ra
    dm = (dl + dr) / 2
    print(f"signal difference (B egalise - A) : {db(rms(dm)) - db(ref_a):+.2f} dB sous la narration ; "
          f"c'est tout ce que le plan ajoute")
    zones = []
    for z in pl.zones:
        t0z, t1z = z['t']
        sl = slice(max(0, int(t0z * SR)), min(n, int(t1z * SR)))
        g = gm[sl]
        qa, qb, qd = a[sl], b[sl], dm[sl]
        if not g.any(): continue
        fa, fb = db(rms(qa[g])) - db(ref_a), db(rms(qb[g])) - db(ref_b)
        add = db(rms(qd[g])) - db(ref_a)                       # ajout, dans les trous, / narration
        zones.append(dict(space=z['space'], ambience=z['ambience'], shots=list(z['shots']),
                          t=[round(t0z, 2), round(t1z, 2)],
                          fond_sur_narration_A_db=round(fa, 2), fond_sur_narration_B_db=round(fb, 2),
                          ajout_sur_narration_db=round(add, 2),
                          profil_octaves_db=octaves(qd[g])))
        print(f"  espace {z['space']:<10} ambiance {z['ambience']:<6} {t0z:5.1f}-{t1z:5.1f}s  "
              f"ajoute {add:+6.2f} dB / narration | octaves {zones[-1]['profil_octaves_db']}")
    print(f"  (octaves {OCT_LABELS} en dB sous la narration : deux espaces distincts "
          f"doivent montrer deux profils distincts)")

    # Silence anormal : le PLANCHER du fond doit tomber dans la fenetre, en B et pas en A. On prend le
    # 20e centile de l'enveloppe dans les trous de narration : un plancher, donc insensible aux
    # transitoires qui restent volontairement dans le creux (la goutte lointaine).
    def floor_db(x, t0f, t1f):
        i, j = max(0, int(t0f * SR)), min(n, int(t1f * SR))
        q = np.abs(x[i:j])[gm[i:j]]
        return db(float(np.percentile(q, 20))) if q.size > 32 else None

    print(f"\nsilence anormal (plancher du fond, 20e centile dans les trous) :")
    sil = []
    for s in pl.silences:
        s0 = spans[s['shot']][0]; t0s, t1s = s0 + s['start'], s0 + s['end']
        fa0, fb0 = floor_db(a, t0s - 3.0, t0s), floor_db(b, t0s - 3.0, t0s)
        fa1, fb1 = floor_db(a, t0s, t1s), floor_db(b, t0s, t1s)
        if None in (fa0, fb0, fa1, fb1): continue
        sil.append(dict(shot=s['shot'], t=[round(t0s, 2), round(t1s, 2)], floor_demande=s['floor'],
                        chute_A_db=round(fa1 - fa0, 2), chute_B_db=round(fb1 - fb0, 2)))
        print(f"  plan {s['shot']} {t0s:5.1f}-{t1s:5.1f}s : plancher A {fa0:.1f} -> {fa1:.1f} dB "
              f"({fa1 - fa0:+.2f} dB) | B {fb0:.1f} -> {fb1:.1f} dB ({fb1 - fb0:+.2f} dB)")

    # Panoramique, mesure sur le signal difference : la course doit partir a droite et revenir au
    # centre. Dans le mix complet la voix (centree, +15 dB) noie l'ecart L/R ; isole, il est net.
    runs = [c for c in pl.cues if c['beat'] == 'threat_run']
    pan = None
    if runs:
        def lr(t): return d_db(rms(win(dr, t - .02, t + .18)), rms(win(dl, t - .02, t + .18)))
        pan = dict(pas=[dict(t=c['t'], pan_demande=c['pan'], R_moins_L_db=lr(c['t'])) for c in runs])
        print(f"\npanoramique de la course (signal difference) :")
        for s in pan['pas']:
            print(f"  t={s['t']:6.2f}s  pan demande {s['pan_demande']:+.2f}  ->  R-L mesure {s['R_moins_L_db']:+6.2f} dB")
        mono_a = d_db(rms(win(ra, runs[0]['t'] - .02, runs[0]['t'] + .18)),
                      rms(win(la, runs[0]['t'] - .02, runs[0]['t'] + .18)))
        pan['temoin_A_premier_pas_db'] = mono_a
        print(f"  temoin : au meme instant, A est a {mono_a:+.2f} dB R-L (rien n'y est place)")

    # Synchronisation, mesure sur le signal difference. Deux precautions, sinon la mesure mesure
    # n'importe quoi : (1) la fenetre d'analyse est bornee a la moitie de l'ecart avec la cue voisine,
    # sinon l'analyse d'un pas verrouille sur le pas suivant (ils sont espaces de 215 ms) ;
    # (2) on cherche une ATTAQUE (premier franchissement de 25 % du maximum local) et non un pic
    # d'energie, sinon un son a attaque lente comme le grognement parait toujours en retard.
    LAG = .15
    sync = []
    for c in pl.cues:
        loc = db(rms(win(dm, c['t'] - .02, c['t'] + .20))) - db(ref_a)
        row = dict(name=c['name'], t_prevu=c['t'], niveau_sur_narration_db=round(loc, 2),
                   in_gap=c['in_gap'], methode='correlation croisee')
        # la forme d'onde attendue : exactement l'appel que le mixeur a fait (S.make est deterministe
        # pour un instant donne). Un son purement synthetise depend de l'etat du generateur : on ne
        # peut pas le reconstruire ici, on le signale au lieu d'inventer un chiffre.
        if not L.LIB.has(c['name']):
            row.update(methode='non mesurable ici', raison='son synthetise : forme d onde non reproductible hors mixeur')
            sync.append(row); continue
        s = np.asarray(S.make(c['name'], c.get('dur'), at=c['t']), np.float64)[:int(.2 * SR)]
        if s.size < 64: sync.append(row); continue
        s = s - s.mean()
        i0 = max(0, int((c['t'] - LAG) * SR)); i1 = min(n, int((c['t'] + LAG) * SR) + s.size)
        seg = np.asarray(dm[i0:i1], np.float64)
        if seg.size <= s.size: sync.append(row); continue
        cc = np.correlate(seg, s, 'valid')
        lag = (i0 + int(np.argmax(cc))) / SR - c['t']
        row.update(t_attaque_mesuree=round(c['t'] + lag, 4), ecart_ms=round(lag * 1000, 1),
                   correlation=round(float(cc.max() / (np.linalg.norm(s) * np.linalg.norm(seg) + 1e-12)), 4))
        sync.append(row)
    meas = [s for s in sync if s.get('ecart_ms') is not None]
    ok = sum(1 for s in meas if abs(s['ecart_ms']) <= 10)
    print(f"\nsynchronisation (correlation croisee sur le signal difference) : {ok}/{len(meas)} "
          f"evenements mesurables cales a moins de 10 ms du temps prevu")
    for s in sync:
        if s.get('ecart_ms') is None:
            print(f"  {s['name']:<10} prevu {s['t_prevu']:6.2f}s  {s.get('raison', s['methode'])}")
            continue
        print(f"  {s['name']:<10} prevu {s['t_prevu']:6.2f}s  mesure {s['t_attaque_mesuree']:8.3f}s  "
              f"ecart {s['ecart_ms']:+6.1f} ms  r={s['correlation']:.3f}  "
              f"niveau {s['niveau_sur_narration_db']:+6.2f} dB/narration"
              f"{'  [dans un trou]' if s['in_gap'] else ''}")

    if '--mp3' in av:
        for k, v in res.items():
            m = v['wav'][:-4] + '.mp3'
            subprocess.run(f'ffmpeg -v error -y -i "{v["wav"]}" -b:a 192k "{m}"', shell=True, check=True)
            v['mp3'] = m; v['sha256_mp3'] = sha(m)
            print(f'  -> {m}')

    rep = dict(episode=os.path.relpath(root, ROOT).replace('\\', '/'), shots=len(ep['shots']),
               lines=len(lines), seconds=round(dur, 2), preset=pl.preset,
               plan_ms=round(plan_ms, 1), cues_main=cues_a, cues_total_B=cues_b,
               beats=[dict(b) for b in pl.beats],
               zones=zones, silences=sil, pan=pan, sync=sync,
               cues=[{k: c[k] for k in ('name', 't', 'gain', 'pan', 'reverb', 'beat', 'why')} for c in pl.cues],
               mixes=res, comparaison=cmp,
               note=("Meme episode, meme voix locale, meme mixeur, meme banque CC0 des deux cotes. "
                     "Seule difference : le plan de soundscape applique a episode.json."))
    with open(os.path.join(OUT, 'soundscape_ab.json'), 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT, 'storyboard.txt'), 'w', encoding='utf-8') as f:
        f.write(pl.storyboard() + '\n')
    print(f"\n-> {OUT}\\A_actuel.wav, B_soundscape.wav, soundscape_ab.json, storyboard.txt")


if __name__ == '__main__':
    main()
