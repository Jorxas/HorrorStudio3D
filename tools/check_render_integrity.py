"""Vérifie qu'un encodage interrompu ne peut plus passer pour une vidéo finie.

    python tools/check_render_integrity.py

La panne reproduite ici est réelle, elle était sur le disque de cette machine : le projet `demo13_art_pixel3d`
portait un `renders/demo13_art_pixel3d_long_16x9.mp4` de **48 octets** — `ftyp`, `free`, un `mdat` vide, **pas
de `moov`** — et pourtant `qc_16x9.json` annonçait **92/100**. Trois maillons se trompaient ensemble :

1. `step_render` ne regardait que le code de retour de ffmpeg, puis la taille du fichier ;
2. `oneclick._renders_of` comptait un rendu fini dès qu'un `.mp4` portait le bon nom ;
3. `step_qc` mesure la mise en scène **sans rendu** — un score juste, sur un objet qui n'était pas le fichier.

Résultat : l'étape « rendu » se déclarait faite, le parcours sautait par dessus, et le studio annonçait
« terminé ». La reprise, la seule chose qui devait survivre à une erreur, était cassée exactement là.

Ce que ce fichier prouve, sur de vrais fichiers et un vrai rendu, jamais sur des suppositions :

- la structure MP4 est lue sans sous-processus, et nomme la panne (`moov` absent) ;
- un rendu abîmé n'est plus un rendu : `_renders_of` l'ignore, `plan()` repasse l'étape à faire, `broken_renders`
  le nomme en français ;
- un contrôle qualité écrit pour un fichier disparu ne compte plus comme fait ;
- un échec d'encodage lève une erreur française **et** écarte le fichier douteux sous un autre nom ;
- rien n'est jamais supprimé : le fichier écarté est toujours là, avec la raison à côté ;
- après la panne, relancer refabrique un MP4 que ffprobe et un décodage complet acceptent.

Sortie 0 si tout passe, 1 sinon. Aucun réseau, aucune clé, aucun coût, aucune option opt-in activée.

Windows : le corps est derrière `if __name__ == '__main__'` à dessein. Le rendu lance un pool « spawn » et un
worker réimporte le module principal ; un outil dont le corps est au niveau du module se rejoue dans chaque
worker (c'est ainsi qu'un premier MP4 tronqué de 25 ko est né, sans la moindre erreur visible).
"""
import os, sys, json, shutil, struct, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)

KEEP = '--keep' in sys.argv
# Les projets de ce test vivent dans un dossier temporaire, jamais dans `projects/` : ils s'y accumulaient à
# chaque exécution (24 Mo pièce) au milieu des projets du propriétaire. `hstudio/paths.py` lit cette variable,
# donc elle doit être posée **avant** le premier import de hstudio.
OUT = os.path.join(tempfile.gettempdir(), 'hstudio_check_render_integrity')
os.environ['HSTUDIO_PROJECTS'] = OUT

FRAMES = 24          # on prouve la chaîne, pas la durée : deux worktrees partagent ce processeur
WORKERS = 2

OK, BAD = [], []


def check(name, cond, detail=''):
    (OK if cond else BAD).append(name)
    print(f'  {"OK  " if cond else "FAIL"} {name}' + (f'   {detail}' if detail else ''))


def quiet(*a, **k):
    pass


# la signature exacte du fichier trouvé sur le disque : ftyp + free + un mdat vide, et pas de moov
KILLED = (struct.pack('>I', 32) + b'ftypisom' + struct.pack('>I', 512) + b'isomiso2avc1mp41'
          + struct.pack('>I', 8) + b'free' + struct.pack('>I', 0) + b'mdat')


# --------------------------------------------------------------------------- 1. lire la structure d'un MP4
def check_structure():
    from hstudio import mediacheck as MC
    print('\n1. la structure MP4, lue sans sous-processus')
    check('la signature du fichier tué fait bien 48 octets', len(KILLED) == 48, str(len(KILLED)) + ' o')

    d = tempfile.mkdtemp(prefix='hs_integ_')
    try:
        killed = os.path.join(d, 'tue.mp4')
        open(killed, 'wb').write(KILLED)
        st = MC.structure(killed)
        check('encodage tué : refusé', not st['ok'])
        check('encodage tué : « moov » vu absent', st['moov'] is False)
        check('encodage tué : la raison nomme « moov »', 'moov' in st['reason'], st['reason'][:70])
        check('encodage tué : les atomes sont lus', st['atoms'] == ['ftyp', 'free', 'mdat'], str(st['atoms']))
        check('encodage tué : playable() dit non', MC.playable(killed) is False)

        vide = os.path.join(d, 'vide.mp4'); open(vide, 'wb').close()
        check('fichier vide : refusé', not MC.structure(vide)['ok'])
        check('fichier vide : raison donnée', bool(MC.structure(vide)['reason']))

        pas = os.path.join(d, 'pas_un_mp4.mp4'); open(pas, 'wb').write(b'ceci est du texte' * 500)
        check('ce qui n\'est pas un MP4 : refusé', not MC.structure(pas)['ok'], MC.structure(pas)['reason'][:60])

        absent = os.path.join(d, 'jamais_ecrit.mp4')
        check('fichier absent : refusé sans lever', not MC.structure(absent)['ok'])
        check('fichier absent : playable() dit non', MC.playable(absent) is False)

        # un vrai MP4, versionné dans la branche : il doit passer, sinon la vérification est trop stricte
        vrai = os.path.join(ROOT, 'docs', 'art_v2', 'demo11_voxel_hd_16x9.mp4')
        if os.path.exists(vrai):
            st = MC.structure(vrai)
            check('un vrai MP4 : accepté', st['ok'], st['reason'][:70])
            check('un vrai MP4 : « moov » vu présent', st['moov'] is True)
            v = MC.describe(vrai, want=(1920, 1080))
            check('un vrai MP4 : ffprobe lit h264 1920x1080', v['ok'] and v['video'] == 'h264', MC.summary(v)[:90])
            check('un vrai MP4 : durée non nulle', v['duration'] > 1, '%.2f s' % v['duration'])
            w = MC.describe(vrai, want=(1080, 1920))
            check('le mauvais format est un échec, pas un détail', not w['ok'] and '1080x1920' in w['reason'], w['reason'][:70])

            # un vrai fichier coupé en deux : la queue manque, donc les atomes dépassent la taille réelle
            coupe = os.path.join(d, 'coupe.mp4')
            with open(vrai, 'rb') as a, open(coupe, 'wb') as b: b.write(a.read(200_000))
            st = MC.structure(coupe)
            check('un vrai MP4 tronqué : refusé', not st['ok'], st['reason'][:70])
        else:
            check('un vrai MP4 de référence est disponible', False, vrai)
    finally:
        shutil.rmtree(d, ignore_errors=True)


# --------------------------------------------------------------------------- 2. écarter sans supprimer
def check_quarantine():
    from hstudio import mediacheck as MC
    print('\n2. un rendu douteux est écarté, jamais supprimé')
    d = tempfile.mkdtemp(prefix='hs_integ_')
    try:
        p = os.path.join(d, 'episode_long_16x9.mp4')
        open(p, 'wb').write(KILLED)
        kept = MC.quarantine(p, 'raison de test')
        check('le fichier a changé de nom', kept != p and os.path.exists(kept), os.path.basename(kept))
        check('le nom d\'origine est libéré', not os.path.exists(p))
        check('le contenu est intact (rien n\'est supprimé)', open(kept, 'rb').read() == KILLED)
        check('« .ECARTE- » est dans le nom', '.ECARTE-' in os.path.basename(kept))
        check('l\'extension .mp4 est gardée', kept.endswith('.mp4'))
        note = kept + '.txt'
        check('la raison est écrite à côté', os.path.exists(note))
        if os.path.exists(note):
            txt = open(note, encoding='utf-8').read()
            check('la note dit la raison', 'raison de test' in txt)
            check('la note dit que rien n\'est supprimé', 'pas supprimé' in txt)

        # deux pannes dans la même seconde ne doivent pas s'écraser l'une l'autre
        open(p, 'wb').write(KILLED)
        k2 = MC.quarantine(p, 'deuxieme')
        check('deux écarts dans la même seconde cohabitent', k2 != kept and os.path.exists(k2) and os.path.exists(kept),
              os.path.basename(k2))
        check('écarter un fichier absent ne lève pas', MC.quarantine(os.path.join(d, 'rien.mp4')) is not None)
    finally:
        shutil.rmtree(d, ignore_errors=True)


# --------------------------------------------------------------------------- 3. la chaîne complète, vrai rendu
def check_pipeline(engine, aspect):
    from hstudio import pipeline as P, oneclick as OC, mediacheck as MC
    tag = 'short_9x16' if aspect == '9:16' else 'long_16x9'
    want = (1080, 1920) if aspect == '9:16' else (1920, 1080)
    label = engine + ' ' + aspect
    print('\n3. ' + label + ' : un vrai rendu, puis la panne reproduite')

    brief = dict(genre='horror' if engine == 'pixel3d' else 'mystery', duration_s=20, voice_mode='voice', engine=engine, n_choices=2, seed=5,
                 premise='un couloir qui revient sur ses pas')
    pr, _ = OC.project_from_brief({'brief': brief, 'name': 'Integrite ' + engine, 'voice_mode': 'draft'}, log=quiet)
    s = dict(P.load_settings()); s['workers'] = WORKERS; s['quality'] = 'standard'
    opts = {'aspects': [aspect], 'quality': 'standard', 'frames': FRAMES}

    OC.run(pr, settings=s, opts=opts, job=None)
    have = OC._renders_of(pr, aspect)
    check(label + ' : le parcours produit un rendu', len(have) == 1, ', '.join(have))
    if not have:
        return pr
    mp4 = pr.p('renders', have[0])
    v = MC.describe(mp4, want=want, full=True)
    check(label + ' : ffprobe + décodage complet acceptent le fichier', v['ok'], MC.summary(v)[:120])
    check(label + ' : le verdict est gardé dans le projet', pr.exists('verify_' + tag + '.json'))
    saved = pr.read_json('verify_' + tag + '.json') or {}
    check(label + ' : le verdict gardé dit « lisible »', saved.get('ok') is True)
    check(label + ' : le verdict gardé compte les images', saved.get('frames_expected') == FRAMES, str(saved.get('frames_sent')))
    qc = pr.read_json(OC._qc_file(aspect)) or {}
    check(label + ' : le contrôle qualité parle du fichier', (qc.get('encoded') or {}).get('ok') is True)
    check(label + ' : et garde son score de mise en scène', isinstance(qc.get('score'), (int, float)), str(qc.get('score')))
    check(label + ' : aucune erreur « rendu inutilisable »',
          not any(i.get('code') == 'render_unusable' for i in (qc.get('issues') or [])))
    before = MC.structure(mp4)['size']

    # --- la panne : l'encodage est tué, il ne reste que l'en-tête. Exactement le fichier trouvé sur le disque.
    open(mp4, 'wb').write(KILLED)
    check(label + ' : (panne simulée) le MP4 ne fait plus que 48 octets', os.path.getsize(mp4) == 48)
    check(label + ' : le rendu abîmé n\'est plus un rendu', OC._renders_of(pr, aspect) == [], str(OC._renders_of(pr, aspect)))
    brk = OC.broken_renders(pr, aspect)
    check(label + ' : il est nommé comme abîmé', len(brk) == 1 and brk[0]['size'] == 48, json.dumps(brk)[:90])
    check(label + ' : la raison est en français et nomme « moov »', brk and 'moov' in brk[0]['reason'], brk[0]['reason'][:60] if brk else '')
    check(label + ' : le contrôle qualité ne compte plus comme fait', OC._qc_done(pr, aspect) is False)

    pl = OC.plan(pr, {'aspects': [aspect]})
    check(label + ' : le parcours n\'est plus « terminé »', pl['complete'] is False)
    check(label + ' : l\'étape suivante redevient le rendu', pl['next'] == 'render', str(pl['next']))
    check(label + ' : l\'étape « rendu » est à refaire',
          [x['done'] for x in pl['stages'] if x['key'] == 'render'] == [False])
    check(label + ' : les étapes d\'avant restent intactes',
          all(x['done'] for x in pl['stages'] if x['key'] in ('script', 'voice', 'align', 'direct', 'mix')))
    check(label + ' : l\'interface reçoit la panne', bool((pl.get('broken') or {}).get(aspect)))

    # --- la reprise : relancer refait le rendu, écarte l'abîmé sans le supprimer, et repasse le contrôle
    OC.run(pr, settings=s, opts=opts, job=None)
    have = OC._renders_of(pr, aspect)
    check(label + ' : la reprise refabrique un rendu lisible', len(have) == 1, ', '.join(have))
    if have:
        v = MC.describe(pr.p('renders', have[0]), want=want, full=True)
        check(label + ' : décodage complet du rendu refait', v['ok'], MC.summary(v)[:120])
        check(label + ' : la taille est redevenue plausible', v['size'] > 50_000 and abs(v['size'] - before) < max(1, before),
              str(v['size']) + ' o contre ' + str(before) + ' o avant la panne')
    ecartes = [f for f in os.listdir(pr.p('renders')) if '.ECARTE-' in f and f.endswith('.mp4')]
    check(label + ' : le fichier abîmé est conservé sous un autre nom', len(ecartes) == 1, ', '.join(ecartes))
    if ecartes:
        check(label + ' : son contenu n\'a pas été touché', open(pr.p('renders', ecartes[0]), 'rb').read() == KILLED)
        check(label + ' : sa raison est écrite à côté', os.path.exists(pr.p('renders', ecartes[0] + '.txt')))
    qc = pr.read_json(OC._qc_file(aspect)) or {}
    check(label + ' : le contrôle qualité a été repassé sur le nouveau fichier',
          (qc.get('encoded') or {}).get('ok') is True and os.path.basename((qc['encoded'].get('path') or '')) in have)
    check(label + ' : le parcours est terminé de nouveau', OC.plan(pr, {'aspects': [aspect]})['complete'] is True)

    # --- idempotence : un parcours fini ne refait rien, et le fichier ne change pas d'un bit
    import hashlib
    h1 = hashlib.sha1(open(pr.p('renders', have[0]), 'rb').read()).hexdigest() if have else ''
    OC.run(pr, settings=s, opts=opts, job=None)
    h2 = hashlib.sha1(open(pr.p('renders', have[0]), 'rb').read()).hexdigest() if have else ''
    check(label + ' : relancer ne refait rien (sha1 identique)', h1 == h2 and bool(h1), h1[:12])
    check(label + ' : aucun écart de plus', len([f for f in os.listdir(pr.p('renders')) if '.ECARTE-' in f and f.endswith('.mp4')]) == 1)
    return pr


# --------------------------------------------------------------------------- 4. l'échec d'encodage lui-même
def check_encode_failure(pr, aspect):
    """ffmpeg à qui on donne un son illisible doit échouer en français, et n'laisser aucun artefact valide."""
    from hstudio import pipeline as P, oneclick as OC
    tag = 'short_9x16' if aspect == '9:16' else 'long_16x9'
    print('\n4. un encodage qui échoue vraiment (son illisible) ne laisse pas de faux rendu')
    if pr is None:
        check('un projet est disponible pour ce test', False); return

    renders = pr.p('renders')
    for f in list(os.listdir(renders)):               # on part d'un dossier sans rendu valide du format
        if f.endswith('.mp4') and tag in f and '.ECARTE-' not in f: os.remove(os.path.join(renders, f))
    before = set(os.listdir(renders))

    mix = pr.p('mix.wav'); backup = pr.p('work', 'mix_backup_integrite.wav')
    shutil.copy(mix, backup)
    try:
        open(mix, 'wb').write(b'RIFF' + b'\x00' * 400)     # un WAV qui n'en est pas un : ffmpeg refusera
        s = dict(P.load_settings()); s['workers'] = WORKERS
        err = None
        try:
            P.step_render(pr, s, aspect, 'standard', None, quiet, frames=FRAMES)
        except Exception as e:
            err = e
        check('l\'échec est signalé (pas un succès silencieux)', err is not None, type(err).__name__)
        msg = str(err or '')
        check('le message est en français et dit quoi faire', 'inutilisable' in msg and 'relance' in msg.lower(), msg[:110])
        check("le message ne prétend pas qu'un fichier existe", 'aucun fichier' in msg or 'moov' in msg, msg[:110])
        check('le message garde la trace de ffmpeg', 'ffmpeg' in msg.lower())
        check('aucun rendu valide n\'est laissé derrière', OC._renders_of(pr, aspect) == [])
        after = set(os.listdir(renders))
        normal = [f for f in after if f.endswith('.mp4') and tag in f and '.ECARTE-' not in f]
        check('aucun fichier au nom normal ne subsiste', normal == [], ', '.join(normal))
        # ffmpeg peut mourir avant d'ouvrir sa sortie : il n'y a alors rien à écarter, et c'est correct.
        # L'invariant est qu'il ne reste jamais d'octet sous le nom normal, et que ce qui existe est conservé.
        new_ec = [f for f in (after - before) if '.ECARTE-' in f and f.endswith('.mp4')]
        check('ce que ffmpeg a écrit est écarté, jamais supprimé', len(new_ec) <= 1,
              ('écarté : ' + ', '.join(new_ec)) if new_ec else "ffmpeg n'a créé aucun fichier de sortie")
        check('le journal de ffmpeg est gardé dans le projet', os.path.exists(pr.p('work', 'ffmpeg_' + tag + '.log')))
        log = ''
        try: log = open(pr.p('work', 'ffmpeg_' + tag + '.log'), encoding='utf-8', errors='replace').read()
        except OSError: pass
        check('le journal de ffmpeg n\'est pas vide', bool(log.strip()), log.strip()[:90])
    finally:
        shutil.copy(backup, mix); os.remove(backup)

    # et la reprise fonctionne encore une fois le son réparé
    s = dict(P.load_settings()); s['workers'] = WORKERS
    P.step_render(pr, s, aspect, 'standard', None, quiet, frames=FRAMES)
    check('le son réparé, le rendu repart et aboutit', len(OC._renders_of(pr, aspect)) == 1,
          ', '.join(OC._renders_of(pr, aspect)))


# --------------------------------------------------------------------------- 5. le rendu interrompu en plein vol
def check_interrupted(pr, aspect):
    """Un worker qui meurt au milieu du rendu : ffmpeg ne doit pas rester orphelin, et le MP4 partiel ne doit
    pas pouvoir passer pour une vidéo finie. C'est la panne d'origine, prise cette fois par le bon bout."""
    from hstudio import pipeline as P, oneclick as OC
    tag = 'short_9x16' if aspect == '9:16' else 'long_16x9'
    print(chr(10) + "5. un rendu interrompu en plein vol (worker en erreur)")
    if pr is None:
        check('un projet est disponible pour ce test', False); return

    renders = pr.p('renders')
    for f in list(os.listdir(renders)):
        if f.endswith('.mp4') and tag in f and '.ECARTE-' not in f: os.remove(os.path.join(renders, f))
    before = set(os.listdir(renders))

    # On interrompt le rendu **en plein flux**, depuis la boucle qui alimente ffmpeg : à ce moment des images
    # sont déjà encodées, donc il y a vraiment un fichier partiel sur le disque. Monkeypatcher `_render_one`
    # ne marcherait pas : un worker « spawn » réimporte le module et ne verrait jamais la version modifiée.
    N = 120
    boom = RuntimeError('rendu interrompu en plein vol (simulation)')

    def kill_midway(frac, detail=''):
        if frac > 0.3: raise boom

    err = None
    s = dict(P.load_settings()); s['workers'] = WORKERS
    try:
        P.step_render(pr, s, aspect, 'standard', kill_midway, quiet, frames=N)
    except Exception as e:
        err = e

    check("l'interruption remonte telle quelle, elle n'est pas avalée", err is boom, type(err).__name__ + ' : ' + str(err)[:60])
    check("aucun rendu valide n'est laissé derrière", OC._renders_of(pr, aspect) == [], str(OC._renders_of(pr, aspect)))
    after = set(os.listdir(renders))
    normal = [f for f in after if f.endswith('.mp4') and tag in f and '.ECARTE-' not in f]
    check('aucun fichier au nom normal ne subsiste', normal == [], ', '.join(normal))
    partial = [f for f in (after - before) if '.ECARTE-' in f and f.endswith('.mp4')]
    check('le fichier partiel est écarté, pas supprimé', len(partial) == 1, ', '.join(sorted(after - before)) or 'aucun fichier produit')
    if partial:
        # ffmpeg n'a encore rien vidé de son tampon : il ne reste que l'en-tête. C'est **exactement** le
        # fichier de 48 octets trouvé dans `projects/demo13_art_pixel3d` — la panne d'origine, reproduite.
        size = os.path.getsize(pr.p('renders', partial[0]))
        check('le fichier partiel est la signature du MP4 tué (en-tête seul)', size < 4096, str(size) + ' o')
        check('il porte la même signature que celui trouvé sur le disque',
              open(pr.p('renders', partial[0]), 'rb').read()[:8] == KILLED[:8], str(size) + ' o')
        from hstudio import mediacheck as MC
        st = MC.structure(pr.p('renders', partial[0]))
        check("et il est bien illisible (c'est tout le propos)", not st['ok'], st['reason'][:70])
        check('sa raison dit que le rendu a été interrompu',
              os.path.exists(pr.p('renders', partial[0] + '.txt'))
              and 'interrompu' in open(pr.p('renders', partial[0] + '.txt'), encoding='utf-8').read())
    orph = ffmpeg_orphans_for(pr.dir)
    check('aucun ffmpeg orphelin ne subsiste sur ce projet', not orph,
          ' | '.join(orph) if orph else "aucun (les ffmpeg des autres projets ne comptent pas)")

    s = dict(P.load_settings()); s['workers'] = WORKERS
    P.step_render(pr, s, aspect, 'standard', None, quiet, frames=FRAMES)
    check('après coup, le rendu repart et aboutit', len(OC._renders_of(pr, aspect)) == 1,
          ', '.join(OC._renders_of(pr, aspect)))


def ffmpeg_orphans_for(folder):
    """Les ffmpeg encore en vie qui travaillent **sur ce dossier**, et eux seuls.

    Compter tous les ffmpeg de la machine ne prouverait rien : d'autres worktrees et d'autres projets
    (MainClip, par exemple) encodent en même temps sur ce portable, et leurs processus ne nous regardent pas.
    On ne regarde donc que les lignes de commande qui citent le dossier du projet testé."""
    import subprocess as SP
    folder = os.path.abspath(folder)
    try:
        if os.name == 'nt':
            ps = ("Get-CimInstance Win32_Process -Filter \"Name='ffmpeg.exe'\" | "
                  "ForEach-Object { $_.CommandLine }")
            out = SP.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', ps],
                         capture_output=True, text=True, timeout=60).stdout
        else:
            out = SP.run(['ps', '-eo', 'args'], capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return []
    return [l.strip()[:120] for l in (out or '').splitlines() if folder.lower() in l.lower()]


if __name__ == '__main__':
    from hstudio import ffmpeg_path as FF
    miss = [t for t, p in FF.ensure().items() if not p]
    if miss:
        print('ffmpeg introuvable (' + ', '.join(miss) + ') : ' + FF.INSTALL_HINT); sys.exit(1)

    t0 = time.time()
    check_structure()
    check_quarantine()
    pr = check_pipeline('pixel3d', '9:16')
    check_encode_failure(pr, '9:16')
    check_interrupted(pr, '9:16')
    check_pipeline('console', '16:9')

    if not KEEP: shutil.rmtree(OUT, ignore_errors=True); print('\n(projets de test effacés ; --keep pour les garder)')
    print('\n' + '-' * 70)
    print(f'{len(OK)} OK, {len(BAD)} FAIL   ({time.time() - t0:.0f} s)')
    for b in BAD: print('  FAIL ' + b)
    sys.exit(1 if BAD else 0)
