"""La preuve du lot d'integration : UNE scene dirigee `dernier_bus`, corps cubique compact, avec les
options integrees par ce lot POSEES SUR CETTE SCENE SEULE (aucun defaut global touche).

    python tools/si_integration_proof.py [--workers 6] [--quality standard]

Ce que la video B (nouvelle) porte, et pourquoi c'est coherent :

| cle posee sur l'episode | lot d'origine | pourquoi ici |
|---|---|---|
| jeu `directed` (eyeline, footing, approach, camera_face_track, clear_face, head_room, lumiere) | P2 cinema `431ba75948ae` | la scene est DIRIGEE : c'est la variante C validee |
| `"body": "voxel_premium"` | P1 voxel 25/10 (`57e4e10`) | la silhouette cubique compacte « Minecraft », finie (poing, semelle, sourcils) ; c'est le corps des cinq videos du 25/10 |
| `"caption_safe": "auto"` | sous-titres surs (`4883d6105467`) | avec ce corps le bandeau `mid` couvrait la bouche en plan serre : la mesure du lot sous-titres l'a chiffre |
| `"sfx_library": true` + plan `soundscape` | soundscape (`84888722b44b`) + sfx-library | la scene n'avait AUCUNE ambiance ni aucun bruitage (0 cue) ; les beats sont FOURNIS par le realisateur (contrat section 2, `SOUND_BEATS` ci-dessous) : la detection par lexique, faite pour un script narre, ne trouvait qu'un beat dans cette scene toute en dialogue |
| `"foot_plant"` : NON ecrite | foot plant (`0699eaec6b6d`) | `footing: "path"` (deja dans `directed`) implique la foulee plantee (acting/timeline.py, `plant=tr.path_heading or ...`) ; l'ecrire serait redondant |

La reference A est le rendu REEL de la mission P2 (`projects/p2c_dernier_bus_c_directed_20261025`),
meme scenario, meme jeu `directed`, sans les cles de ce lot. La planche A/B compare les MEMES instants.

Ce qui est verifie, pas affirme :
 1. le MP4 9:16 H264/AAC se decode INTEGRALEMENT (hstudio.mediacheck, comme P0/P1/P2) ;
 2. la bouche n'est pas couverte : soustitre_qc.measure sur CE montage, cle absente vs posee,
    memes instants, memes visages (cache partage) ;
 3. les SFX sont dans le mix, a leur place : DEUX MIXES DU MEME PROJET (meme voix, meme musique, meme
    mixeur, seule difference = le plan sonore), et la PISTE DIFFERENCE B - A, qui est exactement la
    couche posee par le plan. Pour chaque cue : sa presence (rms de la difference dans sa fenetre,
    au-dessus du plancher de la difference), son rapport au contexte (voix + musique), et son
    emergence locale. Comparer les RMS absolues des deux MP4 finaux ne discrimine rien : les deux
    sont normalises a -14 LUFS et `music: horror` remplit les trous de narration des deux cotes
    (mesure, pas devine : plancher A -23,2 dB vs B -24,0 dB). Ce que la mesure ne tranche PAS :
    l'impression a l'oreille sous le ducking -15 dB de la voix (scene toute en dialogue, trous de
    ~0,3 s) et sous la musique -- c'est le juge humain, sur la copie legere ;
 4. la copie legere 540x960 se decode integralement elle aussi.

Aucun reseau, aucune API payante, aucune demo livree modifiee, aucun defaut global change.
Windows : corps sous `if __name__ == '__main__'` (le rendu lance un pool « spawn »).
"""
import copy, json, math, os, subprocess, sys, time, wave

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

import numpy as np

from p0_proof import frame_stats, audio_stats                                # noqa: E402
import p1_proof as P1                                                        # noqa: E402
import p1_corps_proof as PC                                                  # noqa: E402
import p2_cinema_proof as P2                                                 # noqa: E402
import soustitre_qc as SQ                                                    # noqa: E402

ASPECT = '9:16'
WANT = (1080, 1920)
OUTDIR = os.path.join(ROOT, 'docs', 'integration_v3')
LIGHT = os.path.join(OUTDIR, 'leger')
SLUG = 'si_dernier_bus_integre_20261026'
REF_SLUG = 'p2c_dernier_bus_c_directed_20261025'
REF_MP4 = os.path.join(ROOT, 'projects', REF_SLUG, 'renders', REF_SLUG + '_short_9x16.mp4')

# les cles de CE lot, posees sur CETTE scene seulement
EPISODE_KEYS = {'body': 'voxel_premium', 'caption_safe': 'auto', 'sfx_library': True}

# Les beats sonores du REALISATEUR, l'interface recommandee du contrat (docs/AUDIO_CINEMATIQUE_CONTRAT.md
# section 2) : la detection par lexique est faite pour un script NARRE ; cette scene est presque toute en
# dialogue et le lexique n'y trouvait qu'un beat (door_open ligne 10), d'ou un zonage inverse (la scene
# COMMENCE dehors) et zero evenement. Les indices sont ceux des repliques de `dernier_bus` compile.
SOUND_BEATS = [
    {'kind': 'nightfall',    'line': 0,  'text': 'nuit, rue apres la pluie'},
    {'kind': 'threat_near',  'line': 5,  'text': 'Il ne touche pas le sol.'},
    {'kind': 'threat_run',   'line': 9,  'text': 'Zoe, cours !'},
    {'kind': 'door_open',    'line': 10, 'text': 'La porte ! Ouvre la porte !'},
    {'kind': 'door_close',   'line': 11, 'text': 'On est dedans. Tom, ferme.'},
    {'kind': 'dead_silence', 'line': 14, 'text': 'Je n entends plus rien du tout.'},
    {'kind': 'threat_near',  'line': 16, 'text': 'Ne touche pas le sol.'},
]


def rms_db(x):
    x = np.asarray(x, np.float64)
    r = float(np.sqrt((x ** 2).mean())) if x.size else 0.
    return round(20 * math.log10(max(r, 1e-10)), 2)


def read_mono(mp4, wav):
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', mp4, '-vn', '-ac', '1', '-ar', '44100',
                    '-c:a', 'pcm_s16le', wav], check=True)
    with wave.open(wav) as w:
        sr = w.getframerate()
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.
    return a, sr


def read_wav_mono(path):
    with wave.open(path) as w:
        sr, ch = w.getframerate(), w.getnchannels()
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.
    return (a.reshape(-1, ch).mean(1) if ch > 1 else a), sr


def emergence_db(a, sr, t):
    """de combien la fenetre du cue depasse son propre contexte, DANS LA MEME piste (dB)"""
    win = a[max(0, int((t - .03) * sr)):int((t + .32) * sr)]
    ctx = a[max(0, int((t - .85) * sr)):max(1, int((t - .12) * sr))]
    return round(rms_db(win) - rms_db(ctx), 2)


def mix_pair(pr, ep_sans, ep_avec, lines, spans, dur, pl):
    """la preuve audible, comme tools/soundscape_ab.py : MEME projet, MEME voix, MEME musique, MEME
    mixeur -- la seule difference entre les deux WAV est le plan sonore. Pour chaque cue on compare
    l'emergence locale (cue vs contexte) de B a celle de A au meme instant."""
    from hstudio.audio import mixer as MX
    wavs = {}
    for tag, e in (('sans_plan', ep_sans), ('avec_plan', ep_avec)):
        out = pr.p('work', 'ab_mix_' + tag + '.wav')
        MX.Mixer(pr.p('voice.mp3'), lines, e, dur, e.get('style', 'pixel3d'), pr.p('work')).run(spans, out)
        wavs[tag] = read_wav_mono(out)
    (wa, sr), (wb, _) = wavs['sans_plan'], wavs['avec_plan']
    n = min(wa.size, wb.size)
    diff = wb[:n] - wa[:n]                   # mixes deterministes : la difference EST la couche du plan
    hop = int(sr * .05)
    env = [float(np.sqrt((diff[i:i + hop] ** 2).mean())) for i in range(0, n - hop, hop)]
    floor = round(20 * math.log10(max(float(np.percentile(env, 20)), 1e-10)), 2)
    print(f"   piste difference (B - A) : rms {rms_db(diff)} dB, plancher (20e centile) {floor} dB")
    rows = []
    for c in pl.cues:
        t = float(c['t'])
        if (t + .35) * sr > n: continue
        i0, i1 = max(0, int((t - .03) * sr)), int((t + .32) * sr)
        pres = round(rms_db(diff[i0:i1]) - floor, 2)                 # le son du plan est-il DANS le mix ?
        snr = round(rms_db(diff[i0:i1]) - rms_db(wa[i0:i1]), 2)      # ... et de combien il depasse le contexte
        ea, eb = emergence_db(wa, sr, t), emergence_db(wb, sr, t)
        rows.append(dict(t=round(t, 2), nom=c['name'], presence_dB=pres, snr_contexte_dB=snr,
                         emergence_A=ea, emergence_B=eb, delta_emergence=round(eb - ea, 2),
                         cale=bool(c.get('snapped'))))
        print(f"   {c['name']:<11} t={t:6.2f}s  presence {pres:+6.2f} dB  snr/contexte {snr:+6.2f} dB"
              f"  emergence {ea:+5.2f} -> {eb:+5.2f} dB"
              f"{'   [trou de narration]' if c.get('snapped') else ''}")
    sil = []
    for s in pl.silences:
        t0 = spans[s['shot']][0] + s['start']; t1 = spans[s['shot']][0] + s['end']
        fa = rms_db(wa[int(t0 * sr):int(t1 * sr)]); fb = rms_db(wb[int(t0 * sr):int(t1 * sr)])
        sil.append(dict(t0=round(t0, 2), t1=round(t1, 2), A_dB=fa, B_dB=fb, delta=round(fb - fa, 2)))
        print(f"   silence {t0:5.1f}-{t1:5.1f}s : fond A {fa:7.2f} dB   B {fb:7.2f} dB   delta {fb-fa:+6.2f} dB")
    return dict(diff_rms_dB=rms_db(diff), diff_plancher_dB=floor, cues=rows, silences=sil,
                cues_presents=len([r for r in rows if r['presence_dB'] > 10.]),
                cues_emergents=len([r for r in rows if r['delta_emergence'] > 3.]))


def floor_db(a, sr, gaps, dur):
    """plancher du fond : 20e centile de l'enveloppe RMS (50 ms) dans les trous de narration --
    la mesure meme du rapport soundscape (insensible aux bruitages ponctuels)"""
    hop = int(sr * .05)
    env = []
    for t0, t1 in gaps:
        t1 = min(t1, dur)
        if t1 - t0 < .3: continue
        seg = a[int(t0 * sr):int(t1 * sr)]
        env += [float(np.sqrt((seg[i:i + hop] ** 2).mean())) for i in range(0, max(0, seg.size - hop), hop)]
    if not env: return None
    return round(20 * math.log10(max(float(np.percentile(env, 20)), 1e-10)), 2)


def loudness(path):
    """LUFS integre + true peak (ffmpeg ebur128), comme tools/soundscape_ab.py"""
    r = subprocess.run(f'ffmpeg -hide_banner -nostats -i "{path}" -af ebur128=peak=true -f null -',
                       shell=True, capture_output=True, text=True).stderr
    tail = r[r.rfind('Integrated loudness'):] if 'Integrated loudness' in r else ''
    def grab(key):
        for ln in tail.splitlines():
            if ln.strip().startswith(key):
                try: return float(ln.split(':')[1].strip().split()[0])
                except Exception: return None
        return None
    return dict(lufs_i=grab('I:'), true_peak_dbtp=grab('Peak:'))


def mouth_ab(ep, lines, dur):
    """soustitre_qc sur CE montage : cle absente vs posee, memes instants, cache de visages partage"""
    from hstudio.pipeline import make_engine
    rows, cache = {}, {}
    for tag, cap in (('avant', None), ('apres', 'auto')):
        e = dict(ep)
        e.pop('caption_safe', None)
        if cap: e['caption_safe'] = cap
        eng = make_engine('pixel3d', e, lines, np.zeros(10), dur, ASPECT)
        rows[tag] = SQ.measure(eng, ASPECT, per_shot=2, cache=cache)
    out = {}
    for tag, rr in rows.items():
        n = max(1, len(rr))
        out[tag] = dict(n=len(rr),
                        bouche_moy=round(sum(r['bouche'] for r in rr) / n, 4),
                        bouche_max=round(max([r['bouche'] for r in rr] or [0.]), 4),
                        images_touchees=len([r for r in rr if r['bouche'] > .001]),
                        tete_moy=round(sum(r['tete'] for r in rr) / n, 4),
                        hors_zone_max=round(max([r['hors'] for r in rr] or [0.]), 4),
                        bandes={r['band'] for r in rr})
        out[tag]['bandes'] = sorted(out[tag]['bandes'])
    out['detail_apres'] = [{k: r[k] for k in ('t', 'shot', 'band', 'y', 'bouche', 'tete', 'hors')}
                           for r in rows['apres']]
    return out


def main():
    from hstudio import ffmpeg_path as FF, demos as D, pipeline as P, oneclick as OC, mediacheck as MC
    from hstudio.audio import soundscape as SS, library as L

    found = FF.ensure()
    miss = [t for t, p in found.items() if not p]
    if miss: print('ffmpeg introuvable : ' + ', '.join(miss)); sys.exit(1)
    print('ffmpeg : ' + found['ffmpeg'])

    args = sys.argv[1:]
    workers = int(args[args.index('--workers') + 1]) if '--workers' in args else 6
    quality = args[args.index('--quality') + 1] if '--quality' in args else 'standard'
    os.makedirs(OUTDIR, exist_ok=True)
    P1.OUTDIR = OUTDIR; PC.LIGHT = LIGHT
    print(f'workers = {workers} (sur {os.cpu_count()} coeurs logiques), qualite = {quality}')
    out = {'scene': P2.SCENE, 'aspect': ASPECT, 'slug': SLUG, 'reference': REF_MP4,
           'workers': workers, 'quality': quality, 'episode_keys': EPISODE_KEYS,
           'foot_plant': "non ecrite : 'footing': 'path' (jeu directed) implique la foulee plantee "
                         "(acting/timeline.py, plant=tr.path_heading or self.plant_stride)"}
    t_all = time.time()

    # ---- 1. le projet : scenario dirige, puis les cles de CE lot posees sur CET episode seulement
    P2.use_scenario('directed')
    pr = D.prepare('dernier_bus', slug=SLUG, name='LE DERNIER BUS - integration caption_safe + soundscape')
    ep = pr.read_json('episode.json') or {}
    ep.update(EPISODE_KEYS)
    out['_directed'] = ep.get('_directed')

    # ---- 2. la mise en scene sonore, deduite du script seul (le mixeur existant lira le plan)
    pr.write_json('episode.json', ep)
    lines, ep = P.merged_lines(pr); dur = P.duration_of(ep, lines)
    eng = P.make_engine('pixel3d', ep, lines, np.zeros(10), dur, ASPECT)
    spans = eng.ctx.tl.spans
    cues_before = sum(len(s.get('sfx') or []) for s in ep['shots'])
    pl = SS.plan(ep, lines, spans, beats=SOUND_BEATS)    # beats du realisateur (contrat section 2)
    ep_sans = copy.deepcopy(ep)                          # le meme episode, sans le plan : le A du mix
    ep = pl.apply(ep)
    pr.write_json('episode.json', ep)
    cues_after = sum(len(s.get('sfx') or []) for s in ep['shots'])
    out['soundscape'] = dict(preset=pl.preset, beats_fournis=SOUND_BEATS,
                             beats=[(round(b['t'], 2), b['kind']) for b in pl.beats],
                             zones=[(z['space'], z['shots']) for z in pl.zones],
                             silences=len(pl.silences), cues_avant=cues_before, cues_apres=cues_after,
                             cues=[(round(c['t'], 2), c['name'], round(c.get('gain', 1.), 2)) for c in pl.cues],
                             cues_cc0=sorted({c['name'] for c in pl.cues if L.LIB.has(c['name'])}))
    sb = pl.storyboard()
    open(os.path.join(OUTDIR, SLUG + '_storyboard_sonore.txt'), 'w', encoding='utf-8').write(sb + '\n')
    print(f"\nplan sonore (preset {pl.preset}) : {len(pl.beats)} beats, {len(pl.zones)} espaces, "
          f"cues {cues_before} -> {cues_after}, {len(pl.silences)} silence(s)")
    print(sb)

    # ---- 3. la bouche, cle absente vs posee, sur CE montage (aucun rendu : sondes basse resolution)
    print('\n-- sous-titres : bouche couverte, avant / apres, memes instants --')
    out['bouche'] = mouth_ab(ep, lines, dur)
    for tag in ('avant', 'apres'):
        m = out['bouche'][tag]
        print(f"  {tag:6s} bouche moy {100*m['bouche_moy']:5.1f} %  pire {100*m['bouche_max']:5.1f} %  "
              f"images touchees {m['images_touchees']}/{m['n']}  bandes {','.join(m['bandes'])}")

    # ---- 4. le parcours un clic (mixage, rendu, controle qualite, titres, miniatures)
    s = dict(P.load_settings()); s['workers'] = workers; s['quality'] = quality
    t0 = time.time()
    OC.run(pr, settings=s, opts={'aspects': [ASPECT], 'quality': quality}, job=None)
    out['pipeline_seconds'] = round(time.time() - t0, 1)

    have = OC._renders_of(pr, ASPECT)
    if not have:
        out['error'] = 'aucun rendu lisible'; _write(out); sys.exit(1)
    mp4 = pr.p('renders', have[0]); out['mp4'] = mp4

    print('\n-- verification (ffprobe puis decodage integral) --')
    v = MC.describe(mp4, want=WANT, full=True)
    out['verify'] = v; print(MC.summary(v))
    if not v['ok']:
        out['error'] = 'fichier refuse : ' + v['reason']; _write(out); sys.exit(1)

    times = [round(v['duration'] * f, 2) for f in (0.06, 0.20, 0.34, 0.48, 0.62, 0.76, 0.90)]
    out['sample_times'] = times
    rows_b, sheet_b = frame_stats(mp4, times, OUTDIR, SLUG)
    out['frames'] = rows_b; out['planche'] = sheet_b
    out['flat_frames'] = len([r for r in rows_b if 'std' in r and r['std'] < 3])
    out['audio'] = audio_stats(mp4, pr.p('work'))
    print('   audio : ' + json.dumps(out['audio'], ensure_ascii=False))

    qc = pr.read_json(OC._qc_file(ASPECT)) or {}
    out['qc'] = {'score': qc.get('score'), 'shots': qc.get('shots'), 'duration': qc.get('duration'),
                 'encoded_ok': (qc.get('encoded') or {}).get('ok'),
                 'failing': sorted(k for k, c in (qc.get('checks') or {}).items()
                                   if not c.get('ok') and not c.get('info'))}
    print('   QC mise en scene : ' + str(out['qc']['score']) + '/100, reproches : '
          + (', '.join(out['qc']['failing']) or 'aucun'))

    # ---- 5. A/B contre le rendu REEL de la mission P2 (meme scenario, jeu directed, sans ce lot)
    out['ab'] = None
    if os.path.exists(REF_MP4):
        print('\n-- planche A/B contre ' + REF_SLUG + ' (memes instants) --')
        rows_a, _ = frame_stats(REF_MP4, times, OUTDIR, REF_SLUG + '_ref')
        a = {'title': 'A - P2 directed, sans les cles de ce lot', 'frames': rows_a}
        b = {'title': 'B - directed + voxel_premium + caption_safe + soundscape', 'frames': rows_b}
        p = P1.ab_sheet(a, b, 'ab_directed_vs_integre.png')
        out['ab'] = p; print('  ' + (p or 'PLANCHE NON FABRIQUEE'))

        # contexte sur les MP4 finaux : LUFS et plancher (les deux sont normalises, music: horror
        # remplit les trous des deux cotes -- ces chiffres disent la conformite, pas l'audibilite)
        wa, sr = read_mono(REF_MP4, os.path.join(pr.p('work'), 'ab_a.wav'))
        wb, _ = read_mono(mp4, os.path.join(pr.p('work'), 'ab_b.wav'))
        d_min = min(wa.size, wb.size) / sr
        gaps = SS.narration_gaps(lines)
        fa, fb = floor_db(wa, sr, gaps, d_min), floor_db(wb, sr, gaps, d_min)
        la, lb = loudness(REF_MP4), loudness(mp4)
        print(f"   plancher du fond des MP4 (trous de narration) : A {fa} dB  ->  B {fb} dB")
        print(f"   LUFS integre : A {la['lufs_i']}  B {lb['lufs_i']}  (cible -14)")
        out['audio_mp4'] = dict(plancher_fond_A_dB=fa, plancher_fond_B_dB=fb, lufs_A=la, lufs_B=lb)
    else:
        print('\nATTENTION : reference P2 absente (' + REF_MP4 + ') : pas de planche A/B video')

    # ---- 5b. les SFX s'entendent : deux mixes du MEME projet, seule difference = le plan sonore
    print('\n-- audio A/B (meme projet, meme voix, meme musique ; seule difference : le plan) --')
    out['audio_ab'] = mix_pair(pr, ep_sans, ep, lines, spans, dur, pl)
    print(f"   cues PRESENTS dans le mix (> 10 dB au-dessus du plancher de la difference) :"
          f" {out['audio_ab']['cues_presents']} / {len(out['audio_ab']['cues'])}"
          f"   (emergents en RMS malgre voix+musique : {out['audio_ab']['cues_emergents']})")

    # ---- 6. copie legere, verifiee par decodage integral
    print('\n-- copie legere 540x960 --')
    lc = PC.light_copy(mp4, SLUG)
    out['leger'] = lc
    print(('  OK    ' if lc['ok'] else '  ECHEC ') + lc['path'] + f"   {lc['size']} o"
          + ('' if lc['ok'] else '  ' + str(lc['reason'])))

    out['total_seconds'] = round(time.time() - t_all, 1)
    _write(out)
    bad = (not v['ok']) or (not lc['ok']) or out['flat_frames'] or \
          out['bouche']['apres']['bouche_max'] > .001 or \
          out['audio_ab']['cues_presents'] < 3
    print('\n' + ('ECHEC : voir ' + _report()) if bad else '\nTout est verifie. ' + _report())
    sys.exit(1 if bad else 0)


def _report(): return os.path.join(OUTDIR, 'mesures_integration_20261026.json')


def _write(out):
    json.dump(out, open(_report(), 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)


if __name__ == '__main__':
    main()
