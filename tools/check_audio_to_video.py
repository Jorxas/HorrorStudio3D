"""End-to-end check of the vertical slice "the audio I provide -> an animated video", entirely offline and free:
no API key is read, no TTS is called, no paid provider is contacted. The narration fixture is synthesised here
(amplitude-modulated tone bursts separated by real silences), so the repository carries no audio asset.

  python tools/check_audio_to_video.py            # alignment + mise en scène + mix + a real MP4 (pixel3d)
  python tools/check_audio_to_video.py --no-render # everything except the MP4 (a few seconds)

The path under test is the one the owner follows:
  python -m hstudio audio video ma_voix.mp3 --script script.txt --director heuristic

Honest about transcription: there is no speech-to-text in the studio. The script is given by the owner next to
the audio, and the lines are timed on the silences (offline). If faster-whisper is installed, step_align uses it
instead, word by word -- this test asserts which method actually ran, it never pretends to transcribe.
"""
import hashlib, io, json, os, shutil, subprocess, sys, tempfile, time, wave
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
FAIL = []
SR = 44100

def check(name, ok, detail=''):
    print(f"{'OK   ' if ok else 'ÉCHEC'} {name}" + (f'  ({detail})' if detail else '')); ok or FAIL.append(name)

def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

# ------------------------------------------------------------------ the narration the owner would bring
UTTERANCES = (1.8, 2.2, 1.5)        # three lines spoken
LEAD, GAP, TAIL = .30, .60, .35     # silence before, between, after
SCRIPT = ("La porte du sous-sol était déjà ouverte.\n"
          "Personne n'habite ici depuis des années.\n"
          "Et pourtant, la lumière était allumée.\n")

def narration(path_wav, path_mp3):
    """speech-like bursts and real silences: what a silence-based aligner must be able to cut into three lines.
    Deterministic (fixed seed), so the measured timings below are stable."""
    rng = np.random.default_rng(7)
    out = [np.zeros(int(LEAD * SR), np.float32)]
    spans = []; t = LEAD
    for k, d in enumerate(UTTERANCES):
        n = int(d * SR); tt = np.arange(n) / SR
        syll = .5 + .5 * np.sin(2 * np.pi * 4.3 * tt + k)                 # syllable rate
        voiced = np.sin(2 * np.pi * (165 + 25 * k) * tt) + .4 * np.sin(2 * np.pi * 2 * (165 + 25 * k) * tt)
        seg = (voiced * syll * .35 + rng.standard_normal(n).astype(np.float32) * .004 * syll).astype(np.float32)
        seg[:int(.02 * SR)] *= np.linspace(0, 1, int(.02 * SR), dtype=np.float32)
        seg[-int(.02 * SR):] *= np.linspace(1, 0, int(.02 * SR), dtype=np.float32)
        out.append(seg); spans.append((t, t + d)); t += d
        if k < len(UTTERANCES) - 1: out.append(np.zeros(int(GAP * SR), np.float32)); t += GAP
    out.append(np.zeros(int(TAIL * SR), np.float32)); t += TAIL
    sig = np.concatenate(out)
    with wave.open(path_wav, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(sig, -1, 1) * 32767).astype(np.int16).tobytes())
    r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', path_wav, '-c:a', 'libmp3lame', '-b:a', '192k', path_mp3], capture_output=True, text=True)
    if r.returncode: raise RuntimeError(f'ffmpeg (fixture) : {r.stderr[-300:]}')
    return spans, t

def ffprobe(path, *entries, stream=None):
    cmd = ['ffprobe', '-v', 'error']
    if stream: cmd += ['-select_streams', stream]
    cmd += ['-show_entries', ','.join(entries), '-of', 'json', path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(r.stdout or '{}')

def loudness(path):
    """integrated loudness measured by ffmpeg, to prove the mix really is normalised"""
    r = subprocess.run(['ffmpeg', '-hide_banner', '-i', path, '-af', 'loudnorm=print_format=json', '-f', 'null', '-'],
                       capture_output=True, text=True)
    m = r.stderr
    try: return float(json.loads(m[m.rindex('{'):m.rindex('}') + 1])['input_i'])
    except Exception: return None

# ------------------------------------------------------------------ the run
def main(render=True):
    d = tempfile.mkdtemp(prefix='hstudio_a2v_')
    os.environ['HSTUDIO_PROJECTS'] = os.path.join(d, 'projects')      # before importing hstudio.paths
    try:
        src_wav = os.path.join(d, 'ma_narration.wav'); src = os.path.join(d, 'ma_narration.mp3')
        spans, total = narration(src_wav, src)
        src_sha = sha(src)
        script = os.path.join(d, 'script.txt'); io.open(script, 'w', encoding='utf-8').write(SCRIPT)

        from hstudio import pipeline as P, audio_in as AI
        # no key is ever read: the settings are built here, offline director, offline alignment
        st = {'alignment': 'auto', 'whisper_model': 'large-v3', 'director': 'heuristic', 'quality': 'standard', 'workers': 0}

        info = AI.check(src)
        check('audio fourni : accepté et mesuré', abs(info['duration'] - total) < .1, f"{info['duration']:.2f} s pour {total:.2f} s attendues")

        pr = P.Project.create('Audio fourni', 'pixel3d', director='heuristic')
        io.open(pr.p('script.txt'), 'w', encoding='utf-8').write(SCRIPT)
        P.import_voice(pr, src, log=lambda m: None)
        check('import : voice.mp3 créé dans le projet', pr.exists('voice.mp3'))
        check('import : le fichier source n\'est pas touché', sha(src) == src_sha)
        check('import : la voix source garde sa durée', abs(AI.probe(pr.p('voice.mp3'))['duration'] - total) < .15,
              f"{AI.probe(pr.p('voice.mp3'))['duration']:.2f} s")

        logs = []
        lines = P.step_align(pr, st, log=logs.append)
        how = ' | '.join(logs)
        check('calage : fait hors ligne, sans API', 'silences' in how.lower() or 'whisper' in how.lower(), how)
        check('calage : aucune transcription prétendue', 'transcri' not in how.lower(), how)
        check('calage : une phrase par réplique du script', len(lines) == 3, str(len(lines)))
        ok_order = all(lines[i]['end'] <= lines[i + 1]['start'] + 1e-6 for i in range(len(lines) - 1))
        check('calage : phrases dans l\'ordre, sans chevauchement', ok_order, str([(round(l['start'], 2), round(l['end'], 2)) for l in lines]))
        near = all(abs(l['start'] - a) < .35 and abs(l['end'] - b) < .35 for l, (a, b) in zip(lines, spans))
        check('calage : chaque phrase tombe sur sa prise de son', near,
              f"mesuré {[(round(l['start'], 2), round(l['end'], 2)) for l in lines]} vs réel {[(round(a, 2), round(b, 2)) for a, b in spans]}")
        check('calage : tout tient dans la bande audio', lines[-1]['end'] <= total + .05, f"{lines[-1]['end']:.2f} > {total:.2f}")

        ep = P.step_direct(pr, st, log=lambda m: None)
        covered = sorted({i for s in ep['shots'] for i in range(s['lines'][0], s['lines'][1] + 1)})
        check('mise en scène : hors ligne (heuristique), toutes les phrases couvertes', covered == [0, 1, 2], str(covered))
        # a shot without "set" inherits default_set (the DSL's own rule), so both forms are legitimate here
        resolved = [s.get('set') or ep.get('default_set') for s in ep['shots']]
        check('mise en scène : décors fournis par le moteur, rien à construire à la main',
              bool(ep.get('sets')) and all(r in ep['sets'] for r in resolved),
              f"décors {list((ep.get('sets') or {}).keys())}, plans sur {sorted(set(resolved))}")
        check('mise en scène : le son de la voix source n\'est pas remplacé', pr.exists('voice.mp3') and sha(src) == src_sha)

        P.step_mix(pr, st, log=lambda m: None)
        dur = P.duration_of(ep, P.merged_lines(pr)[0])
        check('mixage : mix.wav produit', pr.exists('mix.wav'))
        mdur = ffprobe(pr.p('mix.wav'), 'format=duration')['format']['duration']
        check('mixage : couvre toute la narration', float(mdur) >= lines[-1]['end'], f'{float(mdur):.2f} s pour une fin à {lines[-1]["end"]:.2f} s')
        lu = loudness(pr.p('mix.wav'))
        check('mixage : normalisé autour de -14 LUFS', lu is not None and -16.5 < lu < -11.5, f'{lu} LUFS')

        if render:
            t0 = time.time()
            out = P.step_render(pr, st, '9:16', 'standard', log=lambda m: None)
            secs = time.time() - t0
            check('rendu : MP4 écrit', os.path.isfile(out) and os.path.getsize(out) > 50_000,
                  f'{os.path.getsize(out) / 1e6:.2f} Mo en {secs:.0f} s' if os.path.exists(out) else 'absent')
            v = ffprobe(out, 'stream=codec_name,width,height,r_frame_rate', stream='v:0').get('streams', [{}])[0]
            a = ffprobe(out, 'stream=codec_name,channels', stream='a:0').get('streams', [{}])[0]
            check('rendu : vidéo h264 1080x1920 à 30 i/s', v.get('codec_name') == 'h264' and (v.get('width'), v.get('height')) == (1080, 1920)
                  and v.get('r_frame_rate') == '30/1', str(v))
            check('rendu : piste audio aac présente', a.get('codec_name') == 'aac' and int(a.get('channels') or 0) == 2, str(a))
            vdur = float(ffprobe(out, 'format=duration')['format']['duration'])
            check('rendu : durée = celle de la narration mise en scène', abs(vdur - dur) < .6, f'{vdur:.2f} s pour {dur:.2f} s')
            check('rendu : la narration fournie est toujours intacte', sha(src) == src_sha)
            keep = os.path.join(ROOT, 'tests', 'out'); os.makedirs(keep, exist_ok=True)
            shutil.copy(out, os.path.join(keep, 'audio_to_video_9x16.mp4'))     # tests/out/ is gitignored
            print(f"      preuve conservée : tests/out/audio_to_video_9x16.mp4 ({os.path.getsize(out) / 1e6:.2f} Mo)")
        else:
            print('(rendu MP4 ignoré : --no-render)')

        P.step_metadata(pr, st, log=lambda m: None)
        md = pr.read_json('metadata.json', {})
        check('publication : titres et hashtags produits hors ligne', bool(md.get('titles')) and bool(md.get('hashtags')), str(list(md)))

        # the same provided audio drives the CONSOLE engine too (quality control only: no second render to pay for)
        pr2 = P.Project.create('Audio fourni console', 'console', director='heuristic')
        io.open(pr2.p('script.txt'), 'w', encoding='utf-8').write(SCRIPT)
        P.import_voice(pr2, src, log=lambda m: None)
        P.step_align(pr2, st, log=lambda m: None)
        ep2 = P.step_direct(pr2, st, log=lambda m: None)
        rep = P.step_qc(pr2, st, '16:9', log=lambda m: None, frames=True)
        check('CONSOLE 2D : le même audio fourni traverse l\'autre moteur', bool(ep2['shots']) and rep.get('score') is not None,
              f"{len(ep2['shots'])} plans, score {rep.get('score')}")
        check('PIXEL 3D / CONSOLE : les deux moteurs servis par le même import', pr.meta['style'] == 'pixel3d' and pr2.meta['style'] == 'console')
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print(f"\n{'Tout est OK' if not FAIL else str(len(FAIL)) + ' échec(s) : ' + ', '.join(FAIL)}")
    return 1 if FAIL else 0

if __name__ == '__main__':
    try: import hstudio  # noqa: F401    # render-toolchain lot: puts a per-user ffmpeg on PATH for this process
    except Exception: pass
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        sys.exit('ffmpeg et ffprobe sont nécessaires pour ce test.')
    sys.exit(main(render='--no-render' not in sys.argv))
