"""Test HORS LIGNE du parcours en un clic (hstudio/oneclick.py) : brief -> MP4 -> QC -> packs de publication.

Ce que ce test prouve, sur les deux moteurs, sans clé, sans réseau et sans rien écrire hors de son dossier
temporaire :

1. un brief devient un projet complet (script, plan d'histoire, épisode validé) ;
2. le parcours enchaîne voix -> calage -> mise en scène -> mixage -> rendu -> contrôle qualité -> titres ->
   miniatures et produit un vrai MP4 que ffprobe décode ;
3. il est **idempotent** : relancé, il ne refait rien et ne touche pas un octet du MP4 déjà fabriqué ;
4. il **reprend sur erreur** : une étape qui échoue n'efface pas les précédentes, le journal dit laquelle, et la
   relance repart exactement de là ;
5. il n'active **aucune option opt-in** (visages HD, éclairage narratif, eyeline/footing, visages CONSOLE,
   bibliothèque de bruitages) : un épisode fabriqué par le parcours ne porte aucune de ces clés ;
6. il **n'appelle rien à distance** : les sockets sont coupées pendant tout le parcours ;
7. la série interactive et les choix A/B/C survivent jusqu'aux packs YouTube Shorts / TikTok.

Le rendu est volontairement coupé à quelques images (`frames`) : on vérifie la chaîne, pas la durée.

    python tools/check_oneclick.py              # ~2 min, les deux moteurs
    python tools/check_oneclick.py --keep       # garde le dossier temporaire pour regarder les fichiers
"""
import os, sys, json, time, shutil, socket, subprocess, tempfile, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

KEEP = '--keep' in sys.argv
FRAMES = 40                                   # un MP4 réel, mais court : le but est la chaîne, pas la durée
OUT = os.path.join(tempfile.gettempdir(), 'hstudio_check_oneclick')
os.environ['HSTUDIO_PROJECTS'] = OUT          # avant tout import : hstudio/paths.py lit l'environnement
# Rien de destructeur ici : sous Windows, `step_render` lance ses processus en « spawn » et ceux-ci réimportent
# ce module. Nettoyer le dossier au niveau du module effacerait le projet pendant son propre rendu.

from hstudio import oneclick as OC, pipeline as P          # noqa: E402
from hstudio.director import story as ST                   # noqa: E402

FAIL = []


def check(name, ok, detail=''):
    print(('OK   ' if ok else 'ÉCHEC') + ' ' + name + (('  (' + str(detail) + ')') if detail and not ok else ''))
    if not ok: FAIL.append(name)


def quiet(*a):
    pass


# ---------------------------------------------------------------- no network, at all
class _NoNetwork:
    """coupe les sockets : toute tentative d'appel distant devient une erreur visible, pas un coût"""
    def __enter__(self):
        self.real = socket.socket
        def refuse(*a, **k): raise OSError('appel réseau interdit pendant le parcours (test hors ligne)')
        socket.socket = refuse
        return self

    def __exit__(self, *a):
        socket.socket = self.real


# ---------------------------------------------------------------- the opt-in options that must stay off
OPTIN_SHOT = ('lighting', 'eyeline', 'footing', 'faces', 'sfx_library', 'camera_face_track', 'face_track')


def optin_keys(ep):
    """toutes les clés opt-in trouvées dans un épisode (il ne doit y en avoir aucune)"""
    found = set()
    def walk(node, path=''):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in OPTIN_SHOT: found.add(k)
                if k == 'hd' and v: found.add('hd')
                walk(v, path + '/' + str(k))
        elif isinstance(node, list):
            for v in node: walk(v, path)
    walk(ep)
    return sorted(found)


# ---------------------------------------------------------------- ffprobe: the MP4 really is one
def probe(path):
    cmd = ['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: return None
    return json.loads(r.stdout)


def decodes(path):
    """décodage complet, pas une lecture d'en-tête : ffmpeg doit sortir sans une seule erreur"""
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'null', '-'], capture_output=True, text=True)
    return r.returncode == 0 and not r.stderr.strip(), (r.stderr or '').strip()[:200]


# ---------------------------------------------------------------- one engine, the whole path
def one_engine(engine, genre, n_choices, aspect, tag):
    print('\n== ' + tag + ' ==')
    brief = dict(genre=genre, duration_s=30, voice_mode='voice', engine=engine, n_choices=n_choices, seed=3,
                 series='Test parcours', part_label='PARTIE 1', premise='une porte qui ne devrait pas être là')
    pr, outline = OC.project_from_brief({'brief': brief, 'name': 'Parcours ' + engine, 'voice_mode': 'draft'}, log=quiet)

    check(tag + ' : projet créé', os.path.isdir(pr.dir) and pr.meta.get('style') == engine, pr.meta.get('style'))
    check(tag + ' : script écrit', len(open(pr.p('script.txt'), encoding='utf-8').read().strip().split('\n')) == len(outline.beats))
    check(tag + ' : plan d\'histoire gardé', pr.exists('outline.json'))
    ep = pr.read_json('episode.json') or {}
    check(tag + ' : épisode validé couvre tout le script', OC._episode_ok(pr), OC._covered(pr))
    check(tag + ' : aucune intention perdue', not outline.check_episode(ep), '; '.join(outline.check_episode(ep))[:120])
    check(tag + ' : aucune option opt-in activée', not optin_keys(ep), ', '.join(optin_keys(ep)))
    check(tag + ' : série conservée', ep.get('series') == 'Test parcours', ep.get('series'))

    pl = OC.plan(pr, {'aspects': [aspect]})
    check(tag + ' : rien ne bloque le départ', not pl['problems'], '; '.join(pl['problems'])[:160])
    check(tag + ' : étape suivante = la voix', pl['next'] == 'voice', pl['next'])
    check(tag + ' : mise en scène déjà faite (le plan la fournit)',
          [s['done'] for s in pl['stages'] if s['key'] == 'direct'] == [True])

    opts = {'aspects': [aspect], 'quality': 'standard', 'frames': FRAMES}
    t0 = time.time()
    with _NoNetwork():
        res = OC.run(pr, opts=opts, job=None)
    print('   (' + ('%.0f' % (time.time() - t0)) + ' s, sockets coupées)')
    check(tag + ' : parcours complet', res['complete'] and res['renders'][aspect], json.dumps(res['renders']))

    mp4 = pr.p('renders', res['renders'][aspect][0])
    info = probe(mp4)
    v = next((s for s in (info or {}).get('streams', []) if s.get('codec_type') == 'video'), {})
    a = next((s for s in (info or {}).get('streams', []) if s.get('codec_type') == 'audio'), {})
    want = (1080, 1920) if aspect == '9:16' else (1920, 1080)
    check(tag + ' : MP4 présent et non vide', os.path.getsize(mp4) > 50_000, os.path.getsize(mp4))
    check(tag + ' : ' + aspect + ' h264 ' + str(want[0]) + 'x' + str(want[1]),
          v.get('codec_name') == 'h264' and (v.get('width'), v.get('height')) == want, json.dumps(v)[:120])
    check(tag + ' : piste audio AAC stéréo', a.get('codec_name') == 'aac' and int(a.get('channels', 0)) == 2, json.dumps(a)[:120])
    ok, err = decodes(mp4)
    check(tag + ' : décodage complet sans erreur', ok, err)

    qc = pr.read_json(OC._qc_file(aspect)) or {}
    check(tag + ' : contrôle qualité enregistré', isinstance(qc.get('score'), (int, float)) and qc.get('engine') == engine, json.dumps(qc.get('score')))

    md = pr.read_json('metadata.json') or {}
    pf = md.get('platforms') or {}
    check(tag + ' : titres et description', bool(md.get('titles')) and bool(md.get('description')))
    check(tag + ' : pack YouTube Shorts', bool((pf.get('youtube_shorts') or {}).get('title')) and bool((pf.get('youtube_shorts') or {}).get('description')))
    check(tag + ' : pack TikTok', bool((pf.get('tiktok') or {}).get('caption')))
    letters = sorted(c.get('letter') for c in (pf.get('choices') or []))
    check(tag + ' : les ' + str(n_choices) + ' choix arrivent jusqu\'aux packs',
          letters == sorted(c.letter for c in outline.choices), str(letters))
    ui = next((s['ui']['choice'] for s in ep['shots'] if (s.get('ui') or {}).get('choice')), {})
    check(tag + ' : la carte de choix porte les bonnes lettres',
          all(c.letter in ui for c in outline.choices), str(sorted(ui)))
    check(tag + ' : miniatures', pr.exists('thumbnail_16x9.jpg') and pr.exists('cover_9x16.jpg'))

    # ---- idempotence : relancer ne refait rien et ne touche pas le MP4
    before = (hashlib.sha1(open(mp4, 'rb').read()).hexdigest(), os.path.getmtime(mp4))
    logs = []
    with _NoNetwork():
        OC.run(pr, opts=opts, job=_FakeJob(logs))
    after = (hashlib.sha1(open(mp4, 'rb').read()).hexdigest(), os.path.getmtime(mp4))
    check(tag + ' : relance = aucune étape refaite', any('0 étape(s) à faire' in l for l in logs), ' | '.join(logs[:2])[:160])
    check(tag + ' : MP4 validé non réécrit', before == after)
    check(tag + ' : journal complet', (OC.read_state(pr) or {}).get('complete') is True)
    return pr, outline, mp4


class _FakeJob:
    def __init__(self, logs): self.log = logs; self.progress = []
    def write(self, m): self.log.append(str(m))
    def prog(self, p, d=''): self.progress.append(float(p))


# ---------------------------------------------------------------- resume after an error
def resume_test(pr, aspect):
    tag = 'reprise'
    print('\n== ' + tag + ' ==')
    opts = {'aspects': [aspect], 'quality': 'standard', 'frames': FRAMES}
    mp4 = pr.p('renders', OC._renders_of(pr, aspect)[0])
    os.remove(mp4); os.remove(pr.p('mix.wav'))
    voice_h = hashlib.sha1(open(pr.p('voice.mp3'), 'rb').read()).hexdigest()
    lines_h = hashlib.sha1(open(pr.p('lines.json'), 'rb').read()).hexdigest()
    ep_h = hashlib.sha1(open(pr.p('episode.json'), 'rb').read()).hexdigest()

    real = P.step_mix
    def boom(*a, **k): raise RuntimeError('panne simulée du mixage')
    P.step_mix = boom
    err = None
    try:
        with _NoNetwork(): OC.run(pr, opts=opts, job=None)
    except Exception as e: err = str(e)
    finally: P.step_mix = real

    check(tag + ' : le parcours échoue clairement', bool(err) and 'Mixage du son' in (err or '') and 'relance' in (err or ''), (err or '')[:160])
    st = OC.read_state(pr)
    check(tag + ' : le journal nomme l\'étape fautive', st.get('failed') == 'mix', json.dumps(st.get('failed')))
    check(tag + ' : la voix est intacte', hashlib.sha1(open(pr.p('voice.mp3'), 'rb').read()).hexdigest() == voice_h)
    check(tag + ' : le calage est intact', hashlib.sha1(open(pr.p('lines.json'), 'rb').read()).hexdigest() == lines_h)
    check(tag + ' : la mise en scène est intacte', hashlib.sha1(open(pr.p('episode.json'), 'rb').read()).hexdigest() == ep_h)
    pl = OC.plan(pr, opts)
    check(tag + ' : l\'interface repart du mixage', pl['next'] == 'mix' and pl['failed'] == 'mix', pl['next'])
    check(tag + ' : les étapes amont restent faites',
          all(s['done'] for s in pl['stages'] if s['key'] in ('script', 'voice', 'align', 'direct')))

    logs = []
    with _NoNetwork(): res = OC.run(pr, opts=opts, job=_FakeJob(logs))
    check(tag + ' : la relance termine le parcours', res['complete'] and res['renders'][aspect], json.dumps(res['renders']))
    check(tag + ' : elle ne refait que ce qui manquait',
          any('Mixage du son, Rendu vidéo' in l for l in logs), ' | '.join(logs[:2])[:200])
    check(tag + ' : le journal est nettoyé', not (OC.read_state(pr) or {}).get('failed'))


# ---------------------------------------------------------------- forcing a stage, and refusing to start
def force_and_refusals(pr, aspect):
    tag = 'garde-fous'
    print('\n== ' + tag + ' ==')
    opts = {'aspects': [aspect], 'quality': 'standard', 'frames': FRAMES}
    mp4 = pr.p('renders', OC._renders_of(pr, aspect)[0])
    m0 = os.path.getmtime(mp4)
    time.sleep(1.1)
    with _NoNetwork(): OC.run(pr, opts=dict(opts, force=['render']), job=None)
    check(tag + ' : « force » refabrique bien le rendu demandé', os.path.getmtime(mp4) > m0)
    check(tag + ' : une étape inconnue dans « force » est ignorée', OC.options({'force': ['nexistepas', 'qc']})['force'] == ['qc'])
    check(tag + ' : un format inconnu est ignoré', OC.options({'aspects': ['4:3']})['aspects'] == ['9:16'])
    check(tag + ' : une qualité inconnue est ignorée', 'quality' not in OC.options({'quality': 'ultra'}))

    empty = P.Project.create('Vide pour le test', 'pixel3d')
    pb = OC.preflight(empty, {'elevenlabs_api_key': ''})
    check(tag + ' : un script vide est refusé avec un message clair', any('script est vide' in p for p in pb), '; '.join(pb)[:160])
    open(empty.p('script.txt'), 'w', encoding='utf-8').write('Une phrase.\n')
    pb = OC.preflight(empty, {'elevenlabs_api_key': ''})
    check(tag + ' : pas de voix et pas de clé est refusé avec un message clair',
          any('clé ElevenLabs' in p for p in pb), '; '.join(pb)[:160])
    err = None
    try: OC.run(empty, settings={'elevenlabs_api_key': ''}, opts=opts)
    except Exception as e: err = str(e)
    check(tag + ' : le parcours refuse de démarrer plutôt que d\'échouer au rendu',
          bool(err) and 'ElevenLabs' in (err or ''), (err or '')[:160])
    check(tag + ' : rien n\'a été écrit dans ce projet', not empty.exists('voice.mp3') and not empty.exists('mix.wav'))
    empty.meta['voice_mode'] = 'draft'; empty.save()
    check(tag + ' : la voix de brouillon lève le blocage', not OC.preflight(empty, {'elevenlabs_api_key': ''}))
    empty.meta['voice_mode'] = 'local'; empty.save()
    pb = OC.preflight(empty, {'elevenlabs_api_key': ''})
    check(tag + ' : la voix locale sans feuille est refusée avec un message clair',
          any('feuille de voix' in p for p in pb), '; '.join(pb)[:160])


# ---------------------------------------------------------------- dialogue: the character voices survive
def dialogue_test():
    """un brief en dialogue : « NOM : réplique » doit devenir un LOCUTEUR, pas du texte lu à voix haute.

    Pas de rendu vidéo ici : une image suffit à prouver que le moteur accepte l'épisode, et c'est gratuit."""
    tag = 'dialogue'
    print('\n== ' + tag + ' ==')
    import numpy as np
    brief = dict(genre='mystery', duration_s=40, voice_mode='hybrid', engine='pixel3d', n_choices=2, seed=6,
                 hero='Léa', other='Tom', premise='deux voix dans le grenier')
    pr, o = OC.project_from_brief({'brief': brief, 'name': 'Parcours dialogue', 'voice_mode': 'draft'}, log=quiet)

    check(tag + ' : le plan a bien de la voix off ET des répliques',
          bool(o.speakers()) and any(not b.speaker for b in o.beats), str(o.speakers()))
    script = open(pr.p('script.txt'), encoding='utf-8').read()
    check(tag + ' : le script porte « NOM : réplique »', any(' : ' in l for l in script.split('\n')))
    check(tag + ' : les locuteurs sont inscrits dans le projet',
          set(pr.meta.get('cast') or []) == {ST.slug(x) for x in o.speakers()}, str(pr.meta.get('cast')))

    lines = P.script_lines(pr)
    spoken = [l for l in lines if l.get('speaker')]
    check(tag + ' : les répliques ont un locuteur', len(spoken) == len(
        [b for b in o.beats if b.speaker]), str(len(spoken)))
    check(tag + ' : le nom du personnage n\'est plus dans le texte lu',
          all(not l['tts'].strip().upper().startswith(l['speaker'].upper() + ' :') for l in spoken),
          '; '.join(l['tts'][:30] for l in spoken[:2]))
    check(tag + ' : la voix off reste sans locuteur', any(not l.get('speaker') for l in lines))

    ep = pr.read_json('episode.json') or {}
    check(tag + ' : chaque locuteur est dans le cast de l\'épisode',
          {ST.slug(x) for x in o.speakers()} <= set(ep.get('cast') or {}), str(sorted(ep.get('cast') or {})))
    labels = {m.get('label') for m in (ep.get('lines') or {}).values() if m.get('label')}
    check(tag + ' : les étiquettes de sous-titre portent les noms',
          labels == {x.upper() for x in o.speakers()}, str(sorted(labels)))

    timed = ST.mock_timing(P.script_lines(pr))
    eng = P.make_engine('pixel3d', ep, timed, np.zeros(10), timed[-1]['end'] + 1.5, '9:16')
    a = np.asarray(eng.frame(timed[len(timed) // 2]['start'] + .2))
    check(tag + ' : le moteur rend une image de la scène dialoguée', a.ndim == 3 and a.std() > 2, str(a.shape))
    check(tag + ' : aucune option opt-in dans un épisode dialogué', not optin_keys(ep), ', '.join(optin_keys(ep)))


# ---------------------------------------------------------------- the two engines stay apart
def engines_apart(pr3d, prcon):
    tag = 'moteurs séparés'
    print('\n== ' + tag + ' ==')
    e3, ec = pr3d.read_json('episode.json'), prcon.read_json('episode.json')
    check(tag + ' : PIXEL 3D garde ses décors, pas de scène CONSOLE',
          all('set' in s and 'scene' not in s for s in e3['shots']))
    check(tag + ' : CONSOLE garde ses scènes en aplats, pas de décor voxel',
          all('scene' in s and 'set' not in s for s in ec['shots']))
    check(tag + ' : CONSOLE sans l\'option « faces » (les aplats restent le défaut)',
          'faces' not in json.dumps(ec))
    check(tag + ' : aucune option opt-in d\'un côté ni de l\'autre',
          not optin_keys(e3) and not optin_keys(ec), ', '.join(optin_keys(e3) + optin_keys(ec)))


if __name__ == '__main__':
    if os.path.isdir(OUT): shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT, exist_ok=True)
    print('Dossier de test : ' + OUT)
    pr3d, out3d, mp43d = one_engine('pixel3d', 'horror', 2, '9:16', 'PIXEL 3D / horreur / 2 choix')
    prcon, outcon, mp4con = one_engine('console', 'mystery', 3, '16:9', 'CONSOLE 2D / mystère / 3 choix')
    engines_apart(pr3d, prcon)
    dialogue_test()
    resume_test(pr3d, '9:16')
    force_and_refusals(pr3d, '9:16')

    print('\nMP4 fabriqués par le parcours :')
    for p in (mp43d, mp4con):
        print('  ' + os.path.abspath(p) + '  (' + ('%.1f' % (os.path.getsize(p) / 1e6)) + ' Mo)')
    if not KEEP: shutil.rmtree(OUT, ignore_errors=True); print('(dossier de test effacé ; --keep pour le garder)')
    print()
    if FAIL:
        print(str(len(FAIL)) + ' ÉCHEC(S) : ' + ', '.join(FAIL[:10])); sys.exit(1)
    print('Tout est bon.')
