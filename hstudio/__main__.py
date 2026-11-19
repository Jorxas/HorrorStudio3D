"""Horror Studio - command line.

  python -m hstudio                         interface web (http://127.0.0.1:8767)
  python -m hstudio new "Nom" --style pixel3d --script script.txt [--voice voix.mp3]
  python -m hstudio new "Nom" --script dialogue.txt --cast lea,tom --place park --draft-voice   (scène avec personnages)
  python -m hstudio run <projet> [--aspect 9:16 --aspect 16:9] [--director claude]
  python -m hstudio oneclick <projet> [--aspect 9:16] [--quality standard] [--force render]
                                            le parcours en un clic : reprend là où il en est, ne refait rien
  python -m hstudio brief --genre horror --duration 45 --engine pixel3d [--run]
                                            un brief -> un projet prêt (script, plan, mise en scène), puis le parcours
  python -m hstudio step <projet> voice|local_voice|align|direct|preview|mix|render|metadata|thumbnail [--aspect 16:9]
  python -m hstudio audio video <audio> --script script.txt [--style console] [--aspect 16:9] [--cast lea,tom]
                                            mon enregistrement + mon texte -> une vidéo animée, en une commande
  python -m hstudio audio check <fichier...>              vérifie des enregistrements locaux (format, durée, pistes)
  python -m hstudio audio import <projet> <fichier>       un fichier local = toute la bande voix (puis « step align »)
  python -m hstudio audio add <projet> <fichier...>       copie des clips dans projects/<projet>/audio/
  python -m hstudio audio list <projet>                   les clips du projet et leurs durées
  python -m hstudio audio sheet <projet>                  écrit voice_clips.json (un clip par phrase, à compléter)
  python -m hstudio audio build <projet>                  assemble la voix locale : voice.mp3 + lines.json exact
  python -m hstudio compile <projet1> <projet2> ... --title "Titre" --out long.mp4
  python -m hstudio list
  python -m hstudio demo                    liste des démos (examples/demos)
  python -m hstudio demo <id> [--aspect 16:9] [--quality standard]   fabrique la démo avec le vrai pipeline
  python -m hstudio demo <id> --qc          contrôle qualité seul (rapide, sans rendu vidéo)
  python -m hstudio qc <projet> [--aspect 16:9]                      contrôle qualité d'un projet (qc_16x9.json)
  python -m hstudio check                   vérifie l'installation (python, ffmpeg, dépendances, moteurs)
  python -m hstudio plan "texte de la scène" [--engine console] [--file histoire.txt] [--requests]
                                            besoins de la scène : disponibles, composés, partiels, manquants (V3)
  python -m hstudio capabilities [--kind action]                    ce que les moteurs savent représenter
  python -m hstudio extension list|test <id>|promote <id>          extensions (nouvelles capacités testées)
"""
import argparse, os, shutil, sys, webbrowser, threading

def main():
    ap = argparse.ArgumentParser(prog='hstudio', description='Horror Studio')
    sub = ap.add_subparsers(dest='cmd')
    w = sub.add_parser('web'); w.add_argument('--port', type=int, default=8767); w.add_argument('--host', default='127.0.0.1'); w.add_argument('--no-browser', action='store_true')
    n = sub.add_parser('new'); n.add_argument('name'); n.add_argument('--style', default='pixel3d', choices=['pixel3d', 'console'])
    n.add_argument('--script'); n.add_argument('--voice'); n.add_argument('--series', default=''); n.add_argument('--part', default='')
    n.add_argument('--previous-choice', default=''); n.add_argument('--previous-choice-text', default=''); n.add_argument('--episode')
    n.add_argument('--cast', default='', help='personnages de la bibliothèque, ex. lea,tom'); n.add_argument('--place', default='', help='lieu prêt (PIXEL 3D), ex. park')
    n.add_argument('--draft-voice', action='store_true', help='voix de brouillon gratuite au lieu d\'ElevenLabs')
    n.add_argument('--local-voice', action='store_true', help='mes propres enregistrements (un clip par phrase, voir « audio sheet »)')
    au = sub.add_parser('audio'); au.add_argument('action', choices=['check', 'video', 'import', 'add', 'list', 'sheet', 'build'])
    au.add_argument('args', nargs='*', help='projet puis fichier(s), selon l\'action')
    au.add_argument('--script', help='le texte de la narration, une phrase par ligne (obligatoire pour « video »)')
    au.add_argument('--name', default=''); au.add_argument('--style', default='pixel3d', choices=['pixel3d', 'console'])
    au.add_argument('--aspect', action='append'); au.add_argument('--quality', default='standard')
    au.add_argument('--place', default=''); au.add_argument('--cast', default='')
    au.add_argument('--director', default='heuristic', help='heuristic (gratuit, hors ligne) par défaut')
    r = sub.add_parser('run'); r.add_argument('project'); r.add_argument('--aspect', action='append'); r.add_argument('--director')
    oc = sub.add_parser('oneclick'); oc.add_argument('project'); oc.add_argument('--aspect', action='append'); oc.add_argument('--quality')
    oc.add_argument('--force', action='append', default=[], help='étape à refaire malgré son artefact existant (ex. render)')
    oc.add_argument('--plan', action='store_true', help='montre seulement l\'état des étapes, sans rien fabriquer')
    br = sub.add_parser('brief'); br.add_argument('--name', default=''); br.add_argument('--genre', default='horror')
    br.add_argument('--duration', type=float, default=45.); br.add_argument('--engine', default='auto', choices=['auto', 'pixel3d', 'console'])
    br.add_argument('--voice-mode', default='voice', choices=['voice', 'dialogue', 'hybrid'], help='façon de raconter')
    br.add_argument('--voice', default='draft', choices=['draft', 'local', 'elevenlabs'], help='source de la voix')
    br.add_argument('--hero', default='Toi'); br.add_argument('--other', default='Léa'); br.add_argument('--place', default='')
    br.add_argument('--premise', default=''); br.add_argument('--series', default=''); br.add_argument('--part', default='')
    br.add_argument('--choices', type=int, default=2, choices=[2, 3]); br.add_argument('--seed', type=int, default=7)
    br.add_argument('--provider', default='mock', help='mock = gabarit déterministe hors ligne (défaut) ; sinon une IA payante')
    br.add_argument('--run', action='store_true', help='enchaîne le parcours tout de suite')
    br.add_argument('--aspect', action='append'); br.add_argument('--quality')
    s = sub.add_parser('step'); s.add_argument('project'); s.add_argument('step'); s.add_argument('--aspect', default='9:16'); s.add_argument('--quality')
    c = sub.add_parser('compile'); c.add_argument('projects', nargs='+'); c.add_argument('--title', default=''); c.add_argument('--out', default='video_longue.mp4')
    sub.add_parser('list')
    d = sub.add_parser('demo'); d.add_argument('demo', nargs='?'); d.add_argument('--aspect', action='append'); d.add_argument('--quality', default='standard'); d.add_argument('--qc', action='store_true')
    q = sub.add_parser('qc'); q.add_argument('project'); q.add_argument('--aspect', action='append')
    sub.add_parser('check')
    pl = sub.add_parser('plan'); pl.add_argument('text', nargs='?', default=''); pl.add_argument('--file'); pl.add_argument('--engine', default='pixel3d', choices=['pixel3d', 'console'])
    pl.add_argument('--requests', action='store_true', help='écrit les demandes d\'extension dans library/extensions/requests'); pl.add_argument('--json', action='store_true')
    cp = sub.add_parser('capabilities'); cp.add_argument('--kind')
    ex = sub.add_parser('extension'); ex.add_argument('action', choices=['list', 'test', 'promote', '_selftest']); ex.add_argument('id', nargs='?')
    a = ap.parse_args()
    if a.cmd in ('plan', 'capabilities', 'extension'):
        return capabilities_cmd(a)
    from . import pipeline as P
    if a.cmd in (None, 'web'):
        import uvicorn
        from .web.server import app
        port = getattr(a, 'port', 8767); host = getattr(a, 'host', '127.0.0.1')
        if not getattr(a, 'no_browser', False): threading.Timer(1.5, lambda: webbrowser.open(f'http://127.0.0.1:{port}')).start()
        print(f'Horror Studio : http://127.0.0.1:{port}  (Ctrl+C pour arrêter)')
        uvicorn.run(app, host=host, port=port, log_level='warning'); return
    s = P.load_settings()
    if a.cmd == 'check':
        from .doctor import report
        sys.exit(0 if report(print) else 1)
    if a.cmd == 'audio':
        return audio_cmd(a, P, s)
    if a.cmd == 'demo':
        from . import demos
        if not a.demo:
            for dm in demos.list_demos(): print(f"{dm['id']:22s} {dm['style']:8s} {dm['title']}  —  {dm['description']}")
            return
        pr, outs = demos.build(a.demo, a.aspect, a.quality, print, lambda p, d_: print(f'\r{p * 100:5.1f}% {d_}', end='', flush=True), qc_only=a.qc)
        print('\n' + '\n'.join(outs)); return
    if a.cmd == 'qc':
        pr = P.Project(a.project)
        for asp in (a.aspect or ['9:16']): P.step_qc(pr, s, asp)
        return
    if a.cmd == 'list':
        os.makedirs(P.paths.PROJECTS, exist_ok=True)
        for d in sorted(os.listdir(P.paths.PROJECTS)):
            pr = P.Project(d)
            if pr.meta: print(f'{d:40s} {pr.meta.get("style"):8s} {pr.status()}')
    elif a.cmd == 'new':
        pr = P.Project.create(a.name, a.style, series=a.series, part_label=a.part, previous_choice=a.previous_choice, previous_choice_text=a.previous_choice_text)
        mode = 'local' if a.local_voice else ('draft' if a.draft_voice else '')
        extra = {k: v for k, v in (('cast', [c.strip() for c in a.cast.split(',') if c.strip()]), ('place', a.place), ('voice_mode', mode)) if v}
        if extra:
            if extra.get('cast') and 'hud_title' not in extra: pr.meta['hud_title'] = ''
            pr.meta.update(extra); pr.save()
        if a.script:
            shutil.copy(a.script, pr.p('script.txt'))
            txt = P.read_script(pr); open(pr.p('script.txt'), 'w', encoding='utf-8').write(txt)     # stored as UTF-8 whatever the source encoding
        if a.voice:
            from .audio_in import AudioInputError
            try: P.import_voice(pr, a.voice)
            except AudioInputError as e: sys.exit(str(e))
        if a.episode: shutil.copy(a.episode, pr.p('episode.json'))
        print(pr.slug)
    elif a.cmd == 'run':
        pr = P.Project(a.project)
        if a.director: pr.meta['director'] = a.director; pr.save()
        outs = P.run_all(pr, s, tuple(a.aspect or ['9:16']), print, lambda p, d: print(f'\r{p * 100:5.1f}% {d}', end='', flush=True))
        print('\n' + '\n'.join(outs))
    elif a.cmd in ('oneclick', 'brief'):
        return oneclick_cmd(a, P, s)
    elif a.cmd == 'step':
        pr = P.Project(a.project); st = a.step
        if st == 'voice': P.step_voice(pr, s)
        elif st in ('local_voice', 'voix_locale'): P.step_local_voice(pr, s)
        elif st == 'align': P.step_align(pr, s)
        elif st == 'direct': P.step_direct(pr, s)
        elif st == 'preview': P.step_preview(pr, s, a.aspect)
        elif st == 'qc': P.step_qc(pr, s, a.aspect)
        elif st == 'mix': P.step_mix(pr, s)
        elif st == 'render': print(P.step_render(pr, s, a.aspect, a.quality, lambda p, d: print(f'\r{p * 100:5.1f}% {d}', end='', flush=True)))
        elif st == 'metadata': P.step_metadata(pr, s)
        elif st == 'thumbnail': P.step_thumbnail(pr, s)
        else: sys.exit(f'étape inconnue : {st}')
    elif a.cmd == 'compile':
        from .compile import compile_long
        items = []
        for slug in a.projects:
            pr = P.Project(slug); rs = [f for f in pr.status()['renders'] if '16x9' in f]
            if not rs: sys.exit(f'{slug} : aucun rendu 16:9')
            items.append((pr.p('renders', rs[0]), pr.meta.get('part_label') or pr.meta.get('name', slug)))
        out, ch = compile_long(items, os.path.abspath(a.out), a.title)
        print(out); print(ch)

def oneclick_cmd(a, P, s):
    """le parcours en un clic en ligne de commande : même module que l'interface web (hstudio/oneclick.py)"""
    from . import oneclick as OC

    class Job:                                           # ce que le parcours attend : écrire et avancer
        def write(self, m): print(m)
        def prog(self, p, d=''): print(f'\r{float(p) * 100:5.1f}% {d}', end='', flush=True)

    opts = OC.options({'aspects': a.aspect or ['9:16'], 'quality': a.quality, 'force': list(getattr(a, 'force', []) or [])})
    if a.cmd == 'brief':
        data = {'brief': dict(genre=a.genre, duration_s=a.duration, voice_mode=a.voice_mode, engine=a.engine,
                              hero=a.hero, other=a.other, place=a.place, premise=a.premise, series=a.series,
                              part_label=a.part, n_choices=a.choices, seed=a.seed),
                'name': a.name, 'voice_mode': ('' if a.voice == 'elevenlabs' else a.voice), 'provider': a.provider}
        try: pr, outline = OC.project_from_brief(data, s)
        except RuntimeError as e: sys.exit(str(e))
        print(pr.slug)
        if not a.run: return
    else:
        pr = P.Project(a.project)
        if not os.path.isdir(pr.dir): sys.exit(f'Projet introuvable : {a.project}')
    pl = OC.plan(pr, opts)
    if getattr(a, 'plan', False):
        for i, st in enumerate(pl['stages'], 1):
            print(f"{i}. {st['label']:22s} {'faite' if st['done'] else ('EN ÉCHEC' if st['state'] == 'error' else 'à faire')}"
                  + (f"   ({st['detail']})" if st['detail'] else ''))
        for p in pl['problems']: print('! ' + p)
        if pl['error']: print('✗ ' + pl['error'])
        return
    for p in pl['problems']: print('! ' + p)
    try: res = OC.run(pr, s, opts, Job())
    except RuntimeError as e: sys.exit('\n' + str(e))
    print('\n' + '\n'.join(pr.p('renders', f) for v in res['renders'].values() for f in v))


def audio_cmd(a, P, s):
    """local audio input (no TTS, no API): check / import a whole track / add clips / list / voice sheet / assemble"""
    from . import audio_in as AI
    try:
        if a.action == 'check':
            if not a.args: sys.exit('Indique au moins un fichier audio.')
            bad = 0
            for f in a.args:
                try:
                    i = AI.check(f)
                    print(f"OK    {i['name']:40s} {i['duration']:7.2f} s  {i['codec']:8s} {i['sample_rate']} Hz  {i['channels']} canal(aux)  {i['bytes'] / 1e6:.1f} Mo")
                except AI.AudioInputError as e: bad += 1; print(f'REFUSÉ {f} : {e}')
            sys.exit(1 if bad else 0)
        if a.action == 'video':
            return audio_video(a, P, s)
        if not a.args: sys.exit('Indique le projet.')
        pr = P.Project(a.args[0]); rest = a.args[1:]
        if not os.path.isdir(pr.dir): sys.exit(f'Projet introuvable : {a.args[0]}')
        if a.action == 'import':
            if len(rest) != 1: sys.exit('Usage : python -m hstudio audio import <projet> <fichier>')
            P.import_voice(pr, rest[0])
        elif a.action == 'add':
            if not rest: sys.exit('Usage : python -m hstudio audio add <projet> <fichier...>')
            P.add_clips(pr, rest)
        elif a.action == 'list':
            names = AI.clips_of(pr.dir)
            if not names: print(f'Aucun clip dans {AI.audio_dir(pr.dir)} (ajoute-en avec « audio add »).')
            for n in names:
                try:
                    i = AI.check(os.path.join(AI.audio_dir(pr.dir), n)); print(f"{n:40s} {i['duration']:7.2f} s  {i['codec']}")
                except AI.AudioInputError as e: print(f'{n:40s} REFUSÉ : {e}')
        elif a.action == 'sheet':
            P.voice_sheet(pr)
        elif a.action == 'build':
            if pr.meta.get('voice_mode') != 'local': pr.meta['voice_mode'] = 'local'; pr.save()
            P.step_local_voice(pr, s)
    except AI.AudioInputError as e:
        sys.exit(str(e))

def audio_video(a, P, s):
    """mon enregistrement + mon texte -> une vidéo animée, en une commande.

    Rien de neuf dans la fabrication : on enchaîne les étapes existantes (import, calage, mise en scène, mixage,
    rendu). Le studio ne sait pas transcrire : le texte est donné par l'auteur à côté du son, et les phrases sont
    calées sur les silences (ou au mot près si faster-whisper est installé, voir docs/MODELES_LOCAUX.md)."""
    from . import audio_in as AI
    if not a.args: sys.exit('Usage : python -m hstudio audio video <fichier audio> --script script.txt')
    src = a.args[0]
    if not a.script:
        sys.exit("Il faut aussi le texte de la narration : --script script.txt (une phrase par ligne).\n"
                 "Le studio ne transcrit pas l'audio ; il cale ton texte sur ta voix.")
    if not os.path.isfile(a.script): sys.exit(f'Script introuvable : {a.script}')
    AI.check(src)                                        # refus immédiat et lisible avant de créer quoi que ce soit
    name = a.name or os.path.splitext(os.path.basename(src))[0]
    pr = P.Project.create(name, a.style, director=a.director)
    extra = {k: v for k, v in (('cast', [c.strip() for c in a.cast.split(',') if c.strip()]), ('place', a.place)) if v}
    if extra:
        if extra.get('cast'): pr.meta['hud_title'] = ''
        pr.meta.update(extra)
    pr.meta['director'] = a.director; pr.save()
    shutil.copy(a.script, pr.p('script.txt'))
    txt = P.read_script(pr)                                                       # lire avant de rouvrir en écriture
    open(pr.p('script.txt'), 'w', encoding='utf-8').write(txt)                    # stocké en UTF-8 quelle que soit la source
    P.import_voice(pr, src)
    s = dict(s); s['quality'] = a.quality
    outs = P.run_all(pr, s, tuple(a.aspect or ['9:16']), print, lambda p, d: print(f'\r{p * 100:5.1f}% {d}', end='', flush=True))
    print('\n' + '\n'.join(outs))

def capabilities_cmd(a):
    import json
    from .capabilities import registry, planner, extensions
    if a.cmd == 'plan':
        text = open(a.file, encoding='utf-8').read() if a.file else a.text
        rep = planner.plan(text, engine=a.engine)
        if a.json: print(json.dumps(rep, ensure_ascii=False, indent=1))
        else: print(planner.format_fr(rep))
        if a.requests:
            for p in planner.write_requests(rep): print('demande :', p)
    elif a.cmd == 'capabilities':
        caps = registry.build(); kinds = {}
        for c in caps.values(): kinds.setdefault(c['kind'], []).append(c['name'])
        for k in sorted(kinds):
            if a.kind and k != a.kind: continue
            print(f'{k:14s} {len(kinds[k]):4d}  ' + (', '.join(sorted(kinds[k])) if a.kind else ', '.join(sorted(kinds[k])[:12]) + (' ...' if len(kinds[k]) > 12 else '')))
        for e, why in extensions.PROBLEMS.items(): print(f'extension {e} non chargée : {why}')
    elif a.action == 'list':
        extensions.ensure_loaded()
        for m in extensions.manifests():
            st = 'chargée' if m['id'] in extensions.LOADED else extensions.PROBLEMS.get(m['id'], 'non chargée (candidate : seulement pendant son test)')
            print(f"{m['id']:16s} {m.get('status', '?'):10s} {st:12s} {m.get('title', '')}")
    elif a.action == '_selftest':
        print(json.dumps(extensions._selftest(a.id), ensure_ascii=False))
    elif a.action == 'test':
        sys.exit(0 if extensions.test(a.id)['ok'] else 1)
    elif a.action == 'promote':
        extensions.promote(a.id)

if __name__ == '__main__':
    main()
