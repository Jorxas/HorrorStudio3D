"""Le parcours en un clic : d'un brief (ou d'un projet existant) jusqu'aux packs de publication.

Ceci n'est PAS un second pipeline. Chaque étape appelle la fonction `step_*` de `hstudio/pipeline.py` qui
existait déjà, dans l'ordre que le propriétaire enchaînait à la main :

    script -> voix -> calage -> mise en scène -> mixage -> rendu -> contrôle qualité -> titres -> miniatures

Ce que ce module ajoute, et rien de plus :

- **un état lisible** : `plan(pr, opts)` dit, pour chaque étape, si elle est déjà faite — la réponse est lue sur
  les fichiers du projet, jamais dans une mémoire à part, donc elle reste vraie après un redémarrage ;
- **la reprise** : une étape déjà faite n'est pas refaite, donc relancer après une erreur repart de l'étape
  fautive sans toucher à ce qui précède. Rien n'est écrasé sans un `force` explicite ;
- **des erreurs explicites** : `preflight()` refuse de démarrer en disant en français ce qui manque, plutôt que
  d'échouer au milieu du rendu ;
- **un journal** : `oneclick.json` dans le projet garde l'étape atteinte, la dernière erreur et l'horodatage.

Aucun appel réseau n'est ajouté ici. La voix ElevenLabs reste la seule étape payante et elle n'est tentée que si
le projet la demande (`voice_mode` vide **et** une clé présente) ; `voice_mode = "draft"` ou `"local"` reste
entièrement hors ligne. Aucune option opt-in (visages HD, éclairage narratif, eyeline/footing, visages CONSOLE,
bibliothèque de bruitages) n'est activée par le parcours : il ne fait que lancer les étapes existantes.
"""
import os, time

from . import pipeline as P

STATE_FILE = 'oneclick.json'
ASPECTS = ('9:16', '16:9')
VOICE_MODES = {'draft': 'Voix de brouillon (gratuite, locale)', 'local': 'Voix locale (mes enregistrements)',
               '': 'Voix ElevenLabs (ta clé)'}


# ---------------------------------------------------------------- read on the project's files
def _script_text(pr):
    return P.read_script(pr) if pr.exists('script.txt') else ''


def _n_lines(pr):
    """how many narration lines the script holds (the parser the pipeline already uses)"""
    from .script import parse_script
    return len(parse_script(_script_text(pr)))


def _covered(pr):
    """the last script line an episode's shots really cover, -1 when there is no usable episode"""
    ep = pr.read_json('episode.json') or {}
    shots = [s for s in (ep.get('shots') or []) if isinstance(s, dict)]
    if not shots: return -1
    last = shots[-1].get('lines') or [0, 0]
    if isinstance(last, int): last = [last, last]
    try: return int(last[-1])
    except Exception: return -1


def _episode_ok(pr):
    """an episode is usable when it exists and covers every line of the current script"""
    if not pr.exists('episode.json'): return False
    n = _n_lines(pr)
    return n > 0 and _covered(pr) >= n - 1


def _renders_of(pr, aspect):
    """Les rendus **lisibles** de ce format. Un `.mp4` au bon nom ne suffit pas.

    C'est ici que la reprise se jouait et se perdait : un encodage tué laisse un MP4 sans « moov », et cette
    fonction le comptait comme un rendu fini. L'étape « rendu » se déclarait faite, le parcours sautait par
    dessus, le contrôle qualité notait la mise en scène, et le studio annonçait « terminé » sur un fichier de
    48 octets. La vérification est structurelle (aucun sous-processus), donc l'interface peut la payer à chaque
    sondage. Les fichiers écartés portent « .ECARTE- » et ne sont jamais comptés."""
    tag = 'short_9x16' if aspect == '9:16' else 'long_16x9'
    d = pr.p('renders')
    if not os.path.isdir(d): return []
    from . import mediacheck as MC
    return sorted(f for f in os.listdir(d)
                  if f.endswith('.mp4') and tag in f and '.ECARTE-' not in f and MC.playable(os.path.join(d, f)))


def broken_renders(pr, aspect):
    """Les `.mp4` présents mais illisibles, pour que l'interface puisse le dire au lieu de les ignorer."""
    tag = 'short_9x16' if aspect == '9:16' else 'long_16x9'
    d = pr.p('renders')
    if not os.path.isdir(d): return []
    from . import mediacheck as MC
    out = []
    for f in sorted(os.listdir(d)):
        if not f.endswith('.mp4') or tag not in f or '.ECARTE-' in f: continue
        st = MC.structure(os.path.join(d, f))
        if not st['ok']: out.append({'file': f, 'size': st['size'], 'reason': st['reason']})
    return out


def _qc_file(aspect):
    return 'qc_' + aspect.replace(':', 'x') + '.json'


def _qc_done(pr, aspect):
    """Un contrôle qualité compte comme fait seulement s'il parle du rendu qui est là **maintenant**.

    Le rapport garde le score de la mise en scène (calculé sans rendu) et un bloc `encoded` sur le fichier. Un
    rapport écrit alors que l'encodage avait été tué décrit un fichier qui n'existe plus : le garder, c'était
    dire « contrôle qualité fait » sur une vidéo refabriquée depuis. Un rapport d'avant ce bloc (`encoded`
    absent) est donc rejoué — il ne coûte pas de rendu."""
    rep = pr.read_json(_qc_file(aspect))
    if not isinstance(rep, dict): return False
    enc = rep.get('encoded')
    if not isinstance(enc, dict): return not _renders_of(pr, aspect)   # rapport d'avant : vrai seulement sans rendu
    if enc.get('ok') is None: return not _renders_of(pr, aspect)       # il disait « aucun rendu » : encore vrai ?
    return bool(enc.get('ok')) and os.path.basename(enc.get('path') or '') in _renders_of(pr, aspect)


def _voice_mode(pr):
    # Demos predating voice_mode record their local babble under voice instead.
    # An explicit modern choice (including ElevenLabs via '') always wins.
    if 'voice_mode' not in pr.meta and pr.meta.get('voice') == 'brouillon':
        return 'draft'
    m = pr.meta.get('voice_mode') or ''
    return m if m in VOICE_MODES else ''


# ---------------------------------------------------------------- the stages
def _run_voice(pr, s, opts, log):
    m = _voice_mode(pr)
    if m == 'draft': P.step_draft_voice(pr, s, log)
    elif m == 'local': P.step_local_voice(pr, s, log)
    else: P.step_voice(pr, s, log)                     # ElevenLabs : la seule étape payante, refusée sans clé


def _run_direct(pr, s, opts, log):
    """la mise en scène : le plan d'histoire s'il y en a un, sinon le metteur en scène du projet"""
    if pr.exists('outline.json'): rebuild_episode(pr, log)
    else: P.step_direct(pr, s, log)


def _run_render(pr, s, opts, log, job=None):
    from . import mediacheck as MC
    todo = []
    for a in opts['aspects']:
        have = _renders_of(pr, a)
        for b in broken_renders(pr, a):               # un rendu mort est écarté sous un autre nom, jamais supprimé
            kept = MC.quarantine(pr.p('renders', b['file']), b['reason'])
            log('Rendu ' + a + ' illisible trouvé (' + b['file'] + ', ' + str(b['size']) + ' o : ' + b['reason']
                + '). Écarté sous ' + os.path.basename(kept) + ', il va être refait.')
        if have and not opts.get('force_render'): log('Rendu ' + a + ' déjà présent : ' + ', '.join(have) + ' (conservé).')
        else: todo.append(a)
    for k, a in enumerate(todo):
        # deux formats partagent la part de barre du rendu : elle avance, elle ne revient pas en arrière
        prog = (lambda p, d='', k=k: job.prog((k + max(0., min(1., float(p)))) / len(todo), d)) if job else None
        P.step_render(pr, s, a, opts.get('quality'), prog, log, frames=opts.get('frames'))


def _run_qc(pr, s, opts, log):
    for a in opts['aspects']:
        if _qc_done(pr, a) and not opts.get('force_qc'):
            log('Contrôle qualité ' + a + ' déjà fait (conservé).'); continue
        P.step_qc(pr, s, a, log)


STAGES = [
    ('script',    'Script',              lambda pr, o: bool(_script_text(pr).strip()), None),
    ('voice',     'Voix',                lambda pr, o: pr.exists('voice.mp3'), _run_voice),
    ('align',     'Calage voix / texte', lambda pr, o: pr.exists('lines.json'), lambda pr, s, o, log: P.step_align(pr, s, log)),
    ('direct',    'Mise en scène',       lambda pr, o: _episode_ok(pr), _run_direct),
    ('mix',       'Mixage du son',       lambda pr, o: pr.exists('mix.wav'), lambda pr, s, o, log: P.step_mix(pr, s, log)),
    ('render',    'Rendu vidéo',         lambda pr, o: all(_renders_of(pr, a) for a in o['aspects']), _run_render),
    ('qc',        'Contrôle qualité',    lambda pr, o: all(_qc_done(pr, a) for a in o['aspects']), _run_qc),
    ('metadata',  'Titres et packs',     lambda pr, o: bool((pr.read_json('metadata.json') or {}).get('platforms')),
                                         lambda pr, s, o, log: P.step_metadata(pr, s, log)),
    ('thumbnail', 'Miniatures',          lambda pr, o: pr.exists('thumbnail_16x9.jpg'), lambda pr, s, o, log: P.step_thumbnail(pr, s, log)),
]
KEYS = [k for k, _, _, _ in STAGES]
# le rendu coûte l'essentiel du temps : la barre de progression ne doit pas mentir
WEIGHT = {'script': .2, 'voice': 2., 'align': 1., 'direct': 1., 'mix': 2., 'render': 10., 'qc': 1.5, 'metadata': .5, 'thumbnail': 1.}


def options(opts=None):
    """les options du parcours, nettoyées : jamais d'aspect inventé, jamais zéro aspect, jamais de qualité inconnue.

    Ce qui arrive d'une requête web passe par ici : `force` est la seule source de vérité du forçage, et `frames`
    (le rendu écourté des tests) est refusé s'il n'est pas un nombre d'images positif."""
    o = dict(opts or {})
    asp = [a for a in (o.get('aspects') or ['9:16']) if a in ASPECTS]
    o['aspects'] = asp or ['9:16']
    if o.get('quality') not in P.QUALITY: o.pop('quality', None)
    try: n = int(o.get('frames'))
    except (TypeError, ValueError): n = 0
    if n > 0: o['frames'] = n
    else: o.pop('frames', None)
    o.pop('force_render', None); o.pop('force_qc', None)
    forced = [k for k in (o.get('force') or []) if k in KEYS]
    o['force'] = forced
    if 'render' in forced: o['force_render'] = True
    if 'qc' in forced: o['force_qc'] = True
    return o


# ---------------------------------------------------------------- what the interface shows
def plan(pr, opts=None):
    """l'état de chaque étape, lu sur les fichiers du projet. Aucun effet de bord."""
    o = options(opts); st = read_state(pr)
    stages = []
    for key, label, done, fn in STAGES:
        try: ok = bool(done(pr, o))
        except Exception: ok = False
        rec = (st.get('stages') or {}).get(key) or {}
        stages.append({'key': key, 'label': label, 'done': ok, 'forced': key in o['force'],
                       'state': 'done' if ok else ('error' if st.get('failed') == key else 'todo'),
                       'at': rec.get('at'), 'detail': rec.get('detail') or ''})
    todo = [x['key'] for x in stages if (not x['done'] or x['forced']) and x['key'] != 'script']
    mode = _voice_mode(pr)
    return {'aspects': o['aspects'], 'voice_mode': mode, 'voice_label': VOICE_MODES[mode],
            'stages': stages, 'next': todo[0] if todo else None, 'complete': not todo,
            'failed': st.get('failed'), 'error': st.get('error'), 'updated': st.get('updated'),
            'renders': {a: _renders_of(pr, a) for a in o['aspects']},
            'broken': {a: broken_renders(pr, a) for a in o['aspects']},
            'problems': preflight(pr, None, o)}


def _key_of(director):
    return {'claude': 'anthropic_api_key', 'gemini': 'gemini_api_key'}.get(director, '')


def preflight(pr, settings=None, opts=None):
    """ce qui empêcherait le parcours d'aboutir, dit avant de démarrer plutôt qu'au milieu du rendu.

    Un message qui commence par « Metteur en scène » est un avertissement : le parcours continue, hors ligne."""
    o = options(opts); s = settings if settings is not None else P.load_settings()
    prob = []
    if not _script_text(pr).strip():
        prob.append("Le script est vide : écris-le (ou pars d'un brief) avant de lancer le parcours.")
    mode = _voice_mode(pr)
    if not pr.exists('voice.mp3'):
        if mode == '' and not s.get('elevenlabs_api_key'):
            prob.append('Pas de voix et pas de clé ElevenLabs : choisis la voix de brouillon (gratuite, locale), '
                        'importe tes enregistrements, ou renseigne la clé dans Réglages.')
        if mode == 'local':
            from . import audio_in as AI
            if not os.path.exists(os.path.join(pr.dir, AI.SHEET)):
                prob.append('Voix locale demandée mais il n\'y a pas de feuille de voix (' + AI.SHEET + ') : '
                            'dépose tes clips dans ' + AI.AUDIO_DIR + '/ puis génère la feuille.')
    if not _episode_ok(pr) and not pr.exists('outline.json'):
        d = pr.meta.get('director') or s.get('director', 'heuristic')
        if d != 'heuristic' and not s.get(_key_of(d)):
            prob.append('Metteur en scène « ' + d + ' » demandé sans clé : le parcours basculera sur la mise en '
                        'scène automatique du studio (gratuite, hors ligne).')
    try:
        from . import ffmpeg_path as FF
        miss = [t for t, p in FF.ensure().items() if not p]
        if miss: prob.append('Introuvable sur cette machine : ' + ', '.join(miss) + '. ' + FF.INSTALL_HINT)
    except Exception as e: prob.append('Vérification de ffmpeg impossible : ' + str(e))
    return prob


# ---------------------------------------------------------------- the journal
def read_state(pr):
    return pr.read_json(STATE_FILE, {}) or {}


def _write_state(pr, st):
    st['updated'] = time.time(); pr.write_json(STATE_FILE, st); return st


# ---------------------------------------------------------------- brief -> project
def rebuild_episode(pr, log=print):
    """réécrit episode.json depuis outline.json (le plan d'histoire), sur le script courant.

    C'est la mise en scène du parcours quand il part d'un brief : les intentions du plan (cadre, mouvement,
    action, note) traversent le validateur existant, et `check_episode` dit ce qui aurait été perdu."""
    import shutil
    from .director import story as ST
    from .director.validate import validate
    from .script import parse_script
    o = ST.Outline.from_dict(pr.read_json('outline.json') or {})
    lines = parse_script(_script_text(pr))
    if not lines: raise RuntimeError('Le script est vide : impossible de remettre la mise en scène en place.')
    style = pr.meta.get('style', 'pixel3d')
    ep, W = validate(o.to_episode(len(lines), series=pr.meta.get('series') or ''), len(lines), style)
    if pr.exists('episode.json'):                      # jamais écraser sans garder l'ancienne version
        shutil.copy(pr.p('episode.json'), pr.p('episode_backup_' + str(int(time.time())) + '.json'))
    pr.write_json('episode.json', ep); pr.write_json('episode_warnings.json', W)
    lost = o.check_episode(ep)
    log('Mise en scène du plan d\'histoire (' + o.generator + ') : ' + str(len(ep['shots'])) + ' plans, '
        + str(len(W)) + ' correction(s), ' + str(len(lost)) + ' intention(s) perdue(s).')
    for x in (W[:10] + lost[:10]): log('  - ' + x)
    if pr.exists('mix.wav'): os.remove(pr.p('mix.wav'))
    return ep


def project_from_brief(data, settings=None, log=print):
    """Un brief -> un projet prêt à être fabriqué : script.txt, outline.json, episode.json.

    `provider='mock'` est le gabarit déterministe hors ligne de `director/story.py` : il n'écrit pas une histoire,
    il remplit un squelette dramatique avec les mots du brief. Tout autre provider appelle une IA (payante)."""
    from .director import story as ST
    brief = ST.Brief.from_dict(data.get('brief') or data)
    bad = brief.problems()
    if bad: raise RuntimeError('Brief incomplet : ' + ' ; '.join(bad))
    provider = (data.get('provider') or 'mock').strip() or 'mock'
    o = ST.build(brief, provider=provider, settings=settings if settings is not None else P.load_settings(), log=log)
    bad = o.problems()
    if bad: raise RuntimeError('Plan d\'histoire inutilisable : ' + ' ; '.join(bad[:6]))

    style = brief.resolve_engine()
    voice_mode = data.get('voice_mode') if data.get('voice_mode') in VOICE_MODES else 'draft'
    name = (data.get('name') or '').strip() or (o.summary[:60].strip() or (brief.resolve_genre() + ' ' + brief.part_label).strip())
    pr = P.Project.create(name, style, series=brief.series, part_label=brief.part_label,
                          previous_choice=brief.previous_choice, notes=brief.premise, director='heuristic',
                          hud_title=data.get('hud_title') or ("L'ÉTAGE 0|N'EXISTE PAS" if style == 'pixel3d' else 'TU|DÉCIDES'))
    pr.meta['voice_mode'] = voice_mode
    speakers = [ST.slug(x) for x in o.speakers()]
    if speakers: pr.meta['cast'] = speakers            # « LÉA : ... » devient un locuteur, pas du texte lu
    if style == 'pixel3d': pr.meta['place'] = o.place
    pr.meta['story'] = {'generator': o.generator, 'genre': brief.resolve_genre(), 'duration_s': brief.duration_s,
                        'voice_style': brief.voice_mode, 'n_choices': brief.n_choices}
    pr.save()
    open(pr.p('script.txt'), 'w', encoding='utf-8').write(o.to_script_text() + '\n')
    pr.write_json('outline.json', o.to_dict())
    rebuild_episode(pr, log)
    log('Projet « ' + name + ' » créé (' + pr.slug + ') : ' + str(len(o.beats)) + ' lignes, '
        + str(len(o.choices)) + ' choix, ' + ('%.0f' % o.seconds()) + ' s estimées, moteur ' + style
        + ', ' + VOICE_MODES[voice_mode].lower() + '.')
    return pr, o


# ---------------------------------------------------------------- the one click
class _SubJob:
    """ce que `step_render` attend d'un job : `prog` et `write`, rapportés dans la part de barre du rendu"""
    def __init__(self, prog, write): self.prog = prog; self.write = write


def run(pr, settings=None, opts=None, job=None):
    """enchaîne les étapes qui restent à faire. Lève une erreur française explicite à la première qui échoue,
    sans toucher aux étapes déjà faites : relancer repart de l'étape fautive."""
    o = options(opts); s = settings if settings is not None else P.load_settings()
    log = job.write if job else print
    bad = [p for p in preflight(pr, s, o) if not p.startswith('Metteur en scène')]
    if bad: raise RuntimeError(' ; '.join(bad))

    st = read_state(pr); st.setdefault('version', 1); st.setdefault('stages', {})
    st['aspects'] = o['aspects']; st['started'] = st.get('started') or time.time()
    st['failed'] = None; st['error'] = None; st['complete'] = False; _write_state(pr, st)

    todo = []
    for key, label, done, fn in STAGES:
        if fn is None: continue
        if key in o['force'] or not done(pr, o): todo.append((key, label, fn))
    total = sum(WEIGHT.get(k, 1.) for k, _, _ in todo) or 1.
    log('Parcours en un clic : ' + str(len(todo)) + ' étape(s) à faire — '
        + (', '.join(l for _, l, _ in todo) if todo else 'rien, tout est déjà fait')
        + ' | formats ' + ', '.join(o['aspects']))

    acc = 0.
    for key, label, fn in todo:
        st['stages'][key] = {'state': 'running', 'at': time.time()}; st['stage'] = key; _write_state(pr, st)
        log('--- ' + label + ' ---')
        t0 = time.time(); base = acc / total; w = WEIGHT.get(key, 1.) / total
        if job: job.prog(base, label)
        sub = (lambda p, d='': job.prog(base + w * max(0., min(1., float(p))), label + ' — ' + d)) if job else None
        try:
            if key == 'render': fn(pr, s, o, log, job=(_SubJob(sub, log) if sub else None))
            else: fn(pr, s, o, log)
        except Exception as e:
            st['stages'][key] = {'state': 'error', 'at': time.time(), 'detail': str(e)[:400]}
            st['failed'] = key; st['error'] = label + ' : ' + str(e); _write_state(pr, st)
            raise RuntimeError('Étape « ' + label + ' » en échec : ' + str(e) + '. Les étapes précédentes sont '
                               'intactes, relance le parcours pour repartir de celle-ci.') from e
        acc += WEIGHT.get(key, 1.)
        st['stages'][key] = {'state': 'done', 'at': time.time(), 'detail': ('%.0f s' % (time.time() - t0))}
        _write_state(pr, st)
        if job: job.prog(acc / total, label)

    st['stage'] = None; st['complete'] = True; _write_state(pr, st)
    try: P.remember_series(pr, log)                    # la série garde ce qui dure (objets tenus), comme `run_all`
    except Exception as e: log('Mémoire de série impossible (' + str(e) + ').')
    outs = {a: _renders_of(pr, a) for a in o['aspects']}
    log('Parcours terminé. ' + ' · '.join(a + ' : ' + (', '.join(v) or 'aucun rendu') for a, v in outs.items()))
    return {'renders': outs, 'complete': plan(pr, o)['complete'], 'aspects': o['aspects']}
