"""Offline checks of the local audio input (hstudio/audio_in.py + the pipeline steps). No API, no key, no cost:
the test clips are synthesised here with ffmpeg. Exit 1 on any failure.

  python tools/check_audio_input.py

What is covered: validation (format, duration, size, no audio stream, unreadable), security (a name from a web
request, a path from a voice sheet, traversal, absolute path, shell metacharacters), the voice sheet (missing
lines, duplicates, out of range), the assembly (exact timings measured on the samples, order, speakers, gaps),
the whole-track import, and the web endpoints with FastAPI's test client when it is available."""
import io, json, os, shutil, subprocess, sys, tempfile, wave
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
FAIL = []

def check(name, ok, detail=''):
    print(f"{'OK   ' if ok else 'ÉCHEC'} {name}" + (f'  ({detail})' if detail and not ok else '')); ok or FAIL.append(name)

def raises(name, fn, needle=''):
    from hstudio.audio_in import AudioInputError
    try:
        fn(); check(name, False, 'aucune erreur levée')
    except AudioInputError as e:
        check(name, needle.lower() in str(e).lower(), f'message « {e} » sans « {needle} »')
    except Exception as e:
        check(name, False, f'{type(e).__name__} au lieu de AudioInputError : {e}')

# ------------------------------------------------------------------ fixtures made with ffmpeg (no asset in the repo)
def tone(path, seconds, freq=440, rate=44100, args=()):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'sine=frequency={freq}:duration={seconds}:sample_rate={rate}',
                        *args, path], capture_output=True, text=True)
    if r.returncode: raise RuntimeError(f'ffmpeg (fixture {path}) : {r.stderr[-400:]}')
    return path

def silent_video(path, seconds=1.0):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'color=c=black:s=64x64:d={seconds}',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', path], capture_output=True, text=True)
    if r.returncode: raise RuntimeError(f'ffmpeg (fixture vidéo) : {r.stderr[-400:]}')
    return path

def wav_seconds(path):
    with wave.open(path) as w: return w.getnframes() / w.getframerate()

# ------------------------------------------------------------------ validation
def validation_checks(d):
    from hstudio import audio_in as AI
    good = tone(os.path.join(d, 'bonne.wav'), 1.25)
    i = AI.check(good)
    check('validation : durée mesurée', abs(i['duration'] - 1.25) < .02, f"{i['duration']}")
    check('validation : codec et échantillonnage lus', i['codec'].startswith('pcm') and i['sample_rate'] == 44100, f"{i['codec']} {i['sample_rate']}")
    check('validation : taille rapportée', i['bytes'] == os.path.getsize(good))
    mp3 = tone(os.path.join(d, 'bonne.mp3'), .8, args=('-c:a', 'libmp3lame', '-b:a', '128k'))
    check('validation : MP3 accepté', AI.check(mp3)['codec'] == 'mp3')
    raises('refus : fichier introuvable', lambda: AI.check(os.path.join(d, 'néant.wav')), 'introuvable')
    raises('refus : dossier', lambda: AI.check(d), 'dossier')
    raises('refus : chemin vide', lambda: AI.check(''), 'aucun fichier')
    vide = os.path.join(d, 'vide.wav'); open(vide, 'wb').close()
    raises('refus : fichier vide', lambda: AI.check(vide), 'vide')
    txt = os.path.join(d, 'script.txt'); io.open(txt, 'w', encoding='utf-8').write('pas du son')
    raises('refus : extension non gérée', lambda: AI.check(txt), 'extension')
    faux = os.path.join(d, 'faux.wav'); io.open(faux, 'w', encoding='utf-8').write('ceci n\'est pas un wav')
    raises('refus : extension audio mais contenu non audio', lambda: AI.check(faux), 'illisible')
    muet = silent_video(os.path.join(d, 'muet.mp4'))
    raises('refus : vidéo sans piste audio', lambda: AI.check(muet), 'aucune piste audio')
    court = tone(os.path.join(d, 'court.wav'), .02)
    raises('refus : trop court', lambda: AI.check(court), 'trop court')
    raises('refus : trop long (limite abaissée)', lambda: AI.check(good, max_seconds=.5), 'trop long')
    raises('refus : trop gros (limite abaissée)', lambda: AI.check(good, max_bytes=1000), 'trop gros')
    # a video that does carry audio is accepted: a phone recording is often a .mp4
    av = os.path.join(d, 'avec_son.mp4')
    r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=64x64:d=1',
                        '-f', 'lavfi', '-i', 'sine=frequency=330:duration=1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', av],
                       capture_output=True, text=True)
    check('validation : vidéo avec piste audio acceptée', r.returncode == 0 and AI.check(av)['channels'] >= 1, r.stderr[-200:])

# ------------------------------------------------------------------ security
def security_checks(d):
    from hstudio import audio_in as AI
    root = os.path.join(d, 'projet', 'audio'); os.makedirs(root, exist_ok=True)
    tone(os.path.join(root, 'clip.wav'), .3)
    check('sécurité : nom simple accepté', AI.safe_name('prise_01.wav') == 'prise_01.wav')
    check('sécurité : accents acceptés', AI.safe_name('réplique léa (2).mp3') == 'réplique léa (2).mp3')
    for bad, needle in (('../../voice.mp3', 'dossier'), ('a/b.wav', 'dossier'), (r'a\b.wav', 'dossier'),
                        ('C:/Windows/win.ini', 'dossier'), ('', 'vide'), ('..', 'vide'),
                        ('prise" & calc.exe & ".wav', 'refusé'), ("prise';rm -rf ~;'.wav", 'refusé'),
                        ('prise.txt', 'extension'), ('prise', 'extension')):
        raises(f'sécurité : nom web refusé {bad!r}', (lambda b=bad: AI.safe_name(b)), needle)
    check('sécurité : chemin relatif résolu dans le dossier', AI.under(root, 'clip.wav') == os.path.realpath(os.path.join(root, 'clip.wav')))
    for bad, needle in (('../../../../Windows/win.ini', 'hors du dossier'), ('..', 'hors du dossier'),
                        ('/etc/passwd', 'absolu'), ('C:\\Windows\\win.ini', 'absolu'), ('', 'vide')):
        raises(f'sécurité : chemin de feuille refusé {bad!r}', (lambda b=bad: AI.under(root, b)), needle)
    sub = os.path.join(root, 'prises'); os.makedirs(sub, exist_ok=True); tone(os.path.join(sub, 'a.wav'), .3)
    check('sécurité : sous-dossier du dossier audio autorisé', AI.under(root, 'prises/a.wav').endswith(os.path.join('prises', 'a.wav')))

# ------------------------------------------------------------------ voice sheet and assembly
def project(d, slug, script, clips, **meta):
    """a real Project under the temporary projects/ folder (HSTUDIO_PROJECTS, set before any import), with its
    script and its audio clips"""
    from hstudio import pipeline as P
    pr = P.Project.create(slug); pr.meta.update(meta); pr.save()
    io.open(pr.p('script.txt'), 'w', encoding='utf-8').write(script)
    from hstudio import audio_in as AI
    ad = AI.audio_dir(pr.dir, create=True)
    for name, seconds, freq in clips: tone(os.path.join(ad, name), seconds, freq)
    return P, pr

def sheet_checks(d):
    from hstudio import audio_in as AI
    # "[long pause]" alone on a line is the script's pause marker (a blank line is simply ignored by parse_script)
    script = 'Première phrase.\nDeuxième phrase.\n[long pause]\nTroisième phrase.\n'
    P, pr = project(d, 'feuille', script, [('a.wav', .5, 300), ('b.wav', .8, 400), ('c.wav', .4, 500)])
    lines = P.script_lines(pr)
    check('script : 3 phrases, pause après la 2e', len(lines) == 3 and lines[1].get('pause_after'),
          str([(l['text'], l.get('pause_after')) for l in lines]))
    raises('feuille : absente', lambda: AI.plan(pr.dir, lines), 'pas de feuille')
    P.voice_sheet(pr, log=lambda m: None)
    sh = AI.read_sheet(pr.dir)
    check('feuille : une ligne par phrase, fichiers préremplis dans l\'ordre',
          [c['file'] for c in sh['clips']] == ['a.wav', 'b.wav', 'c.wav'], str(sh['clips']))
    items = AI.plan(pr.dir, lines)
    check('feuille : durées lues sur les clips', [round(i['duration'], 2) for i in items] == [.5, .8, .4], str([i['duration'] for i in items]))
    check('feuille : pause du script -> intervalle doublé', abs(items[1]['gap_after'] - .6) < 1e-6 and abs(items[0]['gap_after'] - .3) < 1e-6,
          str([i['gap_after'] for i in items]))
    raises('feuille : phrase sans clip', lambda: AI.plan(pr.dir, lines, {'clips': [{'line': 0, 'file': 'a.wav'}]}), 'sans enregistrement')
    raises('feuille : deux clips pour la même phrase',
           lambda: AI.plan(pr.dir, lines, {'clips': [{'line': 0, 'file': 'a.wav'}, {'line': 0, 'file': 'b.wav'}, {'line': 1, 'file': 'b.wav'}, {'line': 2, 'file': 'c.wav'}]}), 'deux clips')
    raises('feuille : phrase hors du script',
           lambda: AI.plan(pr.dir, lines, {'clips': [{'line': 9, 'file': 'a.wav'}]}), 'le script en a 3')
    raises('feuille : fichier manquant',
           lambda: AI.plan(pr.dir, lines, {'clips': [{'line': i, 'file': f} for i, f in enumerate(['a.wav', 'b.wav', 'absent.wav'])]}), 'introuvable')
    raises('feuille : clip hors du dossier audio',
           lambda: AI.plan(pr.dir, lines, {'clips': [{'line': i, 'file': f} for i, f in enumerate(['a.wav', 'b.wav', '../../../script.txt'])]}), 'hors du dossier')
    raises('feuille : "line" manquant', lambda: AI.plan(pr.dir, lines, {'clips': [{'file': 'a.wav'}]}), 'sans "line"')
    raises('feuille : JSON qui n\'est pas une feuille', lambda: AI.plan(pr.dir, lines, [1, 2]), 'liste "clips"')
    raises('feuille : intervalle absurde',
           lambda: AI.plan(pr.dir, lines, {'gap': 999, 'clips': [{'line': i, 'file': f} for i, f in enumerate(['a.wav', 'b.wav', 'c.wav'])]}), 'hors limites')
    return P, pr, lines

def assembly_checks(d):
    from hstudio import audio_in as AI
    script = 'LÉA : Tu as vu la lumière ?\nIl ne répond pas.\nTOM : Cours.\n'
    P, pr = project(d, 'assemblage', script, [('lea.wav', .9, 300), ('narr.wav', 1.4, 200), ('tom.wav', .5, 420)], cast=['lea', 'tom'])
    lines = P.script_lines(pr)
    check('script : le nom en tête de ligne donne le locuteur', [l.get('speaker') for l in lines] == ['lea', None, 'tom'], str([l.get('speaker') for l in lines]))
    AI.write_sheet(pr.dir, {'gap': .25, 'lead_in': .5,
                            'clips': [{'line': 0, 'file': 'lea.wav'},
                                      {'line': 1, 'file': 'narr.wav', 'speaker': ''},
                                      {'line': 2, 'file': 'tom.wav', 'gap_after': .1}]})
    out = P.step_local_voice(pr, {}, log=lambda m: None)
    check('assemblage : lines.json écrit', pr.exists('lines.json') and len(pr.read_json('lines.json')) == 3)
    check('assemblage : voice.mp3 écrit', pr.exists('voice.mp3') and os.path.getsize(pr.p('voice.mp3')) > 1000)
    starts = [l['start'] for l in out]; ends = [l['end'] for l in out]
    want = [.5, .5 + .9 + .25, .5 + .9 + .25 + 1.4 + .25]
    check('assemblage : départs exacts (silence de tête puis intervalles)', all(abs(a - b) < .01 for a, b in zip(starts, want)), f'{starts} != {want}')
    check('assemblage : durée de chaque phrase = durée du clip', all(abs((e - s) - dd) < .02 for s, e, dd in zip(starts, ends, [.9, 1.4, .5])), f'{[round(e - s, 3) for s, e in zip(starts, ends)]}')
    check('assemblage : phrases dans l\'ordre, sans chevauchement', all(ends[i] <= starts[i + 1] for i in range(2)))
    check('assemblage : segs cohérents avec start/end', all(l['segs'] == [[l['start'], l['end']]] for l in out))
    check('assemblage : locuteurs conservés', [l.get('speaker') for l in out] == ['lea', None, 'tom'], str([l.get('speaker') for l in out]))
    check('assemblage : le clip qui dit la phrase est noté', [l['voice_clip'] for l in out] == ['lea.wav', 'narr.wav', 'tom.wav'])
    check('assemblage : pas de faux horodatage par mot', all('word_times' not in l for l in out))
    check('assemblage : enveloppe de lip-sync écrite', pr.exists('env.npy'))
    dur = AI.probe(pr.p('voice.mp3'))['duration']
    check('assemblage : la bande couvre la dernière phrase', dur >= ends[-1] - .05, f'{dur} < {ends[-1]}')
    # a sheet that names a speaker for a line the script does not attribute
    AI.write_sheet(pr.dir, {'clips': [{'line': 0, 'file': 'lea.wav'}, {'line': 1, 'file': 'narr.wav', 'speaker': 'tom'}, {'line': 2, 'file': 'tom.wav'}]})
    out2 = P.step_local_voice(pr, {}, log=lambda m: None)
    check('assemblage : la feuille peut attribuer une phrase à un personnage', out2[1].get('speaker') == 'tom', str(out2[1].get('speaker')))
    check('assemblage : la feuille ne vole pas un locuteur déjà écrit dans le script', out2[0].get('speaker') == 'lea')
    # determinism: the same sheet gives the same timings and the same bytes
    out3 = P.step_local_voice(pr, {}, log=lambda m: None)
    check('assemblage : déterministe (mêmes minutages)', [(l['start'], l['end']) for l in out2] == [(l['start'], l['end']) for l in out3])
    return P, pr

def import_checks(d):
    from hstudio import audio_in as AI
    P, pr = project(d, 'import', 'Une phrase.\nUne autre.\n', [])
    src = tone(os.path.join(d, 'ma_narration.m4a'), 2.0, 220, args=('-c:a', 'aac'))
    pr.write_json('lines.json', [{'i': 0}]); io.open(pr.p('mix.wav'), 'wb').write(b'x')
    pr.write_json('tts_alignment.json', {'characters': []})
    info = P.import_voice(pr, src, log=lambda m: None)
    check('import : voice.mp3 écrit', pr.exists('voice.mp3') and os.path.getsize(pr.p('voice.mp3')) > 1000)
    check('import : converti en MP3', AI.probe(pr.p('voice.mp3'))['codec'] == 'mp3')
    check('import : durée conservée', abs(AI.probe(pr.p('voice.mp3'))['duration'] - 2.0) < .1, str(info['duration']))
    check('import : le calage et le mixage précédents sont oubliés',
          not any(pr.exists(f) for f in ('lines.json', 'mix.wav', 'tts_alignment.json')))
    old = open(pr.p('voice.mp3'), 'rb').read()
    raises('import : fichier refusé, la voix en place n\'est pas touchée', lambda: P.import_voice(pr, os.path.join(d, 'script.txt'), log=lambda m: None), 'extension')
    check('import : voix précédente intacte après un refus', open(pr.p('voice.mp3'), 'rb').read() == old)
    # the whole-track flow then aligns offline on the silences
    out = P.step_align(pr, {'alignment': 'auto'}, log=lambda m: None)
    check('import : calage hors ligne possible derrière l\'import', len(out) == 2 and out[0]['start'] >= 0 and out[-1]['end'] > out[0]['start'], str(out))
    # clips added by the CLI land in audio/ with a validated name
    added = P.add_clips(pr, [tone(os.path.join(d, 'prise 1.wav'), .4)], log=lambda m: None)
    check('ajout de clip : copié dans audio/ sous un nom validé',
          added[0]['name'] == 'prise 1.wav' and os.path.isfile(os.path.join(AI.audio_dir(pr.dir), 'prise 1.wav')))
    return P, pr

# ------------------------------------------------------------------ web endpoints (only if the test client is there)
def web_checks(d):
    try:
        from fastapi.testclient import TestClient
    except Exception as e:
        print(f'(ignoré) client de test FastAPI indisponible : {e}'); return
    from hstudio import audio_in as AI
    P, pr = project(d, 'web', 'Une phrase.\n', [])
    from hstudio.web import server
    c = TestClient(server.app)
    good = tone(os.path.join(d, 'web_bonne.wav'), .7)
    r = c.post(f'/api/projects/{pr.slug}/voice', files={'file': ('bonne.wav', open(good, 'rb'), 'audio/wav')})
    check('web : import de la bande voix accepté', r.status_code == 200 and pr.exists('voice.mp3'), f'{r.status_code} {r.text[:200]}')
    # the name carried by the upload is never used to build a command
    r = c.post(f'/api/projects/{pr.slug}/voice', files={'file': ('x" & copie.txt & ".wav', open(good, 'rb'), 'audio/wav')})
    marker = os.path.join(os.getcwd(), 'copie.txt')
    check('web : nom piégé sans effet (pas de shell)', r.status_code == 200 and not os.path.exists(marker), f'{r.status_code}')
    check('web : aucun fichier upload_* laissé derrière', not [f for f in os.listdir(pr.dir) if f.startswith('upload_')], str(os.listdir(pr.dir)))
    r = c.post(f'/api/projects/{pr.slug}/voice', files={'file': ('note.txt', io.BytesIO(b'pas du son'), 'text/plain')})
    check('web : format non géré refusé en 400', r.status_code == 400 and 'ormat' in r.text, f'{r.status_code} {r.text[:200]}')
    r = c.post(f'/api/projects/{pr.slug}/voice', files={'file': ('faux.wav', io.BytesIO(b'pas du son'), 'audio/wav')})
    check('web : faux wav refusé en 400', r.status_code == 400, f'{r.status_code} {r.text[:200]}')
    r = c.post(f'/api/projects/{pr.slug}/audio', files={'file': ('../../evasion.wav', open(good, 'rb'), 'audio/wav')})
    check('web : nom avec dossier refusé en 400', r.status_code == 400, f'{r.status_code} {r.text[:200]}')
    check('web : rien n\'est écrit hors du projet', not os.path.exists(os.path.join(d, 'evasion.wav')))
    r = c.post(f'/api/projects/{pr.slug}/audio', files={'file': ('prise_01.wav', open(good, 'rb'), 'audio/wav')})
    check('web : clip accepté dans audio/', r.status_code == 200 and os.path.isfile(os.path.join(AI.audio_dir(pr.dir), 'prise_01.wav')), f'{r.status_code} {r.text[:200]}')
    r = c.get(f'/api/projects/{pr.slug}/audio')
    check('web : liste des clips avec leur durée', r.status_code == 200 and r.json()['clips'][0]['name'] == 'prise_01.wav' and r.json()['clips'][0]['duration'] > .5, r.text[:200])
    r = c.post(f'/api/projects/{pr.slug}/audio/sheet')
    check('web : feuille de voix construite', r.status_code == 200 and r.json()['sheet']['clips'][0]['file'] == 'prise_01.wav', r.text[:200])
    r = c.put(f'/api/projects/{pr.slug}/audio/sheet', json={'sheet': {'clips': [{'line': 0, 'file': '../../../script.txt'}]}})
    check('web : feuille avec échappement refusée en 400', r.status_code == 400, f'{r.status_code} {r.text[:200]}')
    r = c.put(f'/api/projects/{pr.slug}/audio/sheet', json={'sheet': {'clips': [{'line': 0, 'file': 'prise_01.wav'}]}})
    check('web : feuille valable enregistrée', r.status_code == 200 and os.path.exists(os.path.join(pr.dir, AI.SHEET)), f'{r.status_code} {r.text[:200]}')
    check('web : étape « voix locale » exposée', 'local_voice' in server.STEPS)
    r = c.get(f'/api/projects/{pr.slug}/file/../../../AGENTS.md')
    check('web : lecture hors projet toujours refusée', r.status_code in (403, 404), f'{r.status_code}')

if __name__ == '__main__':
    # a per-user ffmpeg is invisible to a shell opened before the install: the render-toolchain lot finds it and
    # prepends it to PATH for this process. Importing hstudio is enough (it calls ffmpeg_path.ensure()) and it does
    # not read HSTUDIO_PROJECTS, so the env var set just below is still honoured.
    try: import hstudio  # noqa: F401
    except Exception: pass
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        sys.exit('ffmpeg et ffprobe sont nécessaires pour ces tests (ils fabriquent les clips de test).')
    d = tempfile.mkdtemp(prefix='hstudio_audio_in_')
    os.environ['HSTUDIO_PROJECTS'] = os.path.join(d, 'projects')   # before any hstudio import: paths reads it once
    try:
        for fn in (validation_checks, security_checks, sheet_checks, assembly_checks, import_checks, web_checks): fn(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print(f"\n{'Tout est OK' if not FAIL else str(len(FAIL)) + ' échec(s) : ' + ', '.join(FAIL)}")
    sys.exit(1 if FAIL else 0)
