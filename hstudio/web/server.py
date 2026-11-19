"""Local web interface (FastAPI). Start with: python -m hstudio (http://127.0.0.1:8767)."""
import os, json, shutil, glob, time
from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from .. import paths, pipeline as P, jobs, tts, audio_in as AI, oneclick as OC
from ..director.validate import validate
from ..compile import compile_long

app = FastAPI(title='Horror Studio')

from fastapi import Request
import hmac

def _publication_access(request):
    from ..publication_bridge import config
    conf = config()
    if not conf or not hmac.compare_digest(str(request.headers.get('authorization','')), 'Bearer '+conf['apiKey']):
        raise HTTPException(403,'Accès refusé.')

@app.post('/api/publication/automation/inspect')
def publication_automation_inspect(request: Request, data: dict = Body(...)):
    _publication_access(request)
    from .. import publication_automation as PA
    try: return PA.inspect(data)
    except (ValueError, KeyError) as exc: raise HTTPException(409,str(exc)) from None

@app.post('/api/publication/automation/start')
def publication_automation_start(request: Request, data: dict = Body(...)):
    _publication_access(request)
    from .. import publication_automation as PA
    try: return PA.start(data.get('requestId'),data.get('input') or {},data.get('authorization') or {})
    except (ValueError, KeyError) as exc: raise HTTPException(409,str(exc)) from None

@app.get('/api/publication/automation/voices')
def publication_automation_voices(request: Request):
    _publication_access(request)
    from .. import publication_automation as PA
    try: return PA.voices()
    except ValueError as exc: raise HTTPException(409,str(exc)) from None

@app.get('/api/publication/automation/requests/{request_id}')
def publication_automation_status(request_id: str, request: Request):
    _publication_access(request)
    from .. import publication_automation as PA
    try: return PA.view(request_id)
    except KeyError as exc: raise HTTPException(404,str(exc)) from None

@app.post('/api/publication/automation/requests/{request_id}/resume')
def publication_automation_resume(request_id: str, request: Request):
    _publication_access(request)
    from .. import publication_automation as PA
    try: return PA.resume(request_id)
    except (ValueError, KeyError) as exc: raise HTTPException(409,str(exc)) from None

@app.post('/api/publication/automation/requests/{request_id}/cancel')
def publication_automation_cancel(request_id: str, request: Request):
    _publication_access(request)
    from .. import publication_automation as PA
    try: return PA.cancel(request_id)
    except KeyError as exc: raise HTTPException(404,str(exc)) from None

@app.post('/api/publication/automation/requests/{request_id}/reconcile')
def publication_automation_reconcile(request_id: str, request: Request):
    _publication_access(request)
    from .. import publication_automation as PA
    try: return PA.reconcile(request_id)
    except (ValueError, KeyError) as exc: raise HTTPException(409,str(exc)) from None

@app.get('/api/publication/status')
def publication_status():
    from ..publication_bridge import status
    return status()

@app.post('/api/projects/{slug}/publication')
def publication_prepare(slug: str, data: dict = Body(...)):
    from ..publication_bridge import prepare
    try:
        return prepare(_proj(slug), str(data.get('filename', '')), data.get('language', 'fr'))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None

@app.get('/publication_bridge.js')
def publication_bridge_js():
    return FileResponse(os.path.join(STATIC, 'publication_bridge.js'), media_type='application/javascript', headers={'Cache-Control': 'no-cache'})
STATIC = os.path.join(os.path.dirname(__file__), 'static')
SECRET_KEYS = ('elevenlabs_api_key', 'anthropic_api_key', 'gemini_api_key')

def _proj(slug):
    pr = P.Project(slug)
    if not os.path.isdir(pr.dir): raise HTTPException(404, 'projet introuvable')
    return pr

@app.get('/', response_class=HTMLResponse)
def index(): return open(os.path.join(STATIC, 'studio.html'), encoding='utf-8').read()          # nouvelle interface (31/10/2026)

@app.get('/studio_extras.js')
def studio_extras_js():
    """catalogue, espace disque et « voir avant de valider » de la nouvelle interface (chargé par studio.html)"""
    return FileResponse(os.path.join(STATIC, 'studio_extras.js'), media_type='application/javascript', headers={'Cache-Control': 'no-cache'})

@app.get('/classique', response_class=HTMLResponse)
def index_classique(): return open(os.path.join(STATIC, 'index.html'), encoding='utf-8').read()        # l'ancienne interface, gardée le temps de la transition

# ---------------- catalogue : tout ce que le moteur sait peindre (hstudio/catalogue.py), miniatures comprises
@app.get('/catalogue')
def catalogue_page():
    from fastapi.responses import RedirectResponse
    return RedirectResponse('/#catalogue')                       # le catalogue vit dans la nouvelle interface ; l'ancienne page noire reste sur /catalogue-classique

@app.get('/catalogue-classique', response_class=HTMLResponse)
def catalogue_classique(): return open(os.path.join(STATIC, 'catalogue.html'), encoding='utf-8').read()

@app.get('/api/catalogue')
def catalogue_index():
    from .. import catalogue as CT
    return CT.load()

@app.get('/catalogue/sounds/{name}')
def catalogue_sound(name: str):
    from .. import catalogue as CT
    d = os.path.realpath(os.path.join(str(CT.OUT), 'sounds')); f = os.path.realpath(os.path.join(d, os.path.basename(name)))
    if not f.startswith(d) or not os.path.isfile(f): raise HTTPException(404)
    return FileResponse(f, media_type='audio/mpeg')

@app.get('/catalogue/thumbs/{name}')
def catalogue_thumb(name: str):
    from .. import catalogue as CT
    f = os.path.realpath(os.path.join(str(CT.THUMBS), os.path.basename(name)))
    if not f.startswith(os.path.realpath(str(CT.THUMBS))) or not os.path.isfile(f): raise HTTPException(404)
    return FileResponse(f, headers={'Cache-Control': 'max-age=3600'})

@app.get('/catalogue/{folder}/{name}')
def catalogue_thumb_style(folder: str, name: str):
    """miniatures des autres styles : thumbs_ps1/ (moteur PIXEL 3D), thumbs_console/ (Console 2D)"""
    from .. import catalogue as CT
    if folder not in ('thumbs_ps1', 'thumbs_console'): raise HTTPException(404)
    d = os.path.realpath(os.path.join(str(CT.OUT), folder)); f = os.path.realpath(os.path.join(d, os.path.basename(name)))
    if not f.startswith(d) or not os.path.isfile(f): raise HTTPException(404)
    return FileResponse(f, headers={'Cache-Control': 'max-age=3600'})

# ---------------- settings
@app.get('/api/settings')
def get_settings():
    s = P.load_settings()
    return {k: (('•••• ' + v[-4:]) if (k in SECRET_KEYS and v) else v) for k, v in s.items()} | {'_has': {k: bool(s.get(k)) for k in SECRET_KEYS}}

@app.post('/api/settings')
def set_settings(data: dict = Body(...)):
    data = {k: v for k, v in data.items() if not (k in SECRET_KEYS and (not v or str(v).startswith('••••')))}
    P.save_settings(data); return {'ok': True}

@app.get('/api/voices')
def voices():
    s = P.load_settings()
    if not s.get('elevenlabs_api_key'): raise HTTPException(400, 'Clé ElevenLabs manquante')
    try: return {'voices': tts.list_voices(s['elevenlabs_api_key']), 'models': tts.list_models(s['elevenlabs_api_key'])}
    except Exception as e: raise HTTPException(400, str(e))

# ---------------- projects
@app.get('/api/projects')
def list_projects():
    os.makedirs(paths.PROJECTS, exist_ok=True); out = []
    for d in sorted(os.listdir(paths.PROJECTS)):
        pr = P.Project(d)
        if pr.meta: out.append({'slug': d, **{k: pr.meta.get(k) for k in ('name', 'style', 'render_engine', 'series', 'part_label', 'created')}, 'status': pr.status(),
                                'preview': os.path.isfile(pr.p('preview', 'shot_000.jpg'))})       # lets the rail skip thumbnails that do not exist (no 404 in the console)
    out.sort(key=lambda x: -(x.get('created') or 0)); return out

ACTOR_KEYS = ('cast', 'place', 'voice_mode', 'director', 'music')

@app.post('/api/projects')
def create_project(data: dict = Body(...)):
    pr = P.Project.create(data.get('name') or 'Nouvel épisode', data.get('style', 'pixel3d'), **{k: v for k, v in data.items() if k not in ('name', 'style')})
    extra = {k: data[k] for k in ACTOR_KEYS if data.get(k)}          # scenes with library characters (acting layer)
    if extra: pr.meta.update(extra); pr.save()
    if data.get('script'): open(pr.p('script.txt'), 'w', encoding='utf-8').write(data['script'])
    return {'slug': pr.slug}

@app.post('/api/projects/{slug}/duplicate')
def duplicate(slug: str, data: dict = Body(...)):
    src = _proj(slug); meta = dict(src.meta); meta.pop('created', None)
    pr = P.Project.create(data.get('name') or (src.meta.get('name', '') + ' (suite)'), meta.get('style', 'pixel3d'), **{k: v for k, v in meta.items() if k not in ('name', 'style')})
    return {'slug': pr.slug}

def _read_caps(pr):
    """capabilities.json of a project (what the story needs vs what the engines have), None when absent or unreadable.
    Gaps found by the audit of the episode have no extension request in the file (only the planner's needs do): they get
    one here, built by the planner itself and returned under 'gap_requests' (the file on disk is never modified)."""
    try: cap = pr.read_json('capabilities.json', None)
    except (OSError, ValueError): return None
    if isinstance(cap, dict):
        try:
            from ..capabilities import planner
            au = cap.get('audit') or {}; style = au.get('style') or 'pixel3d'
            have = {q.get('id') for q in ((cap.get('plan') or {}).get('requests') or []) + ((au.get('requires') or {}).get('requests') or [])}
            extra = []
            for g in au.get('gaps') or []:
                rid = f"{g['kind']}_{g['name']}"
                if rid in have: continue
                have.add(rid)
                q = planner.request({'kind': g['kind'], 'name': g['name'], 'terms': [g.get('where', '')]}, style, f"{g.get('where', '')} : {g.get('consequence', '')}")
                extra.append(dict(q, need='manquant'))
            if extra: cap['gap_requests'] = extra
        except Exception: pass                                   # an odd file must never break the project page
    return cap

@app.get('/api/projects/{slug}')
def get_project(slug: str):
    pr = _proj(slug)
    rd = lambda f: open(pr.p(f), encoding='utf-8').read() if pr.exists(f) else ''
    return {'slug': slug, 'meta': pr.meta, 'status': pr.status(), 'script': P.read_script(pr) if pr.exists('script.txt') else '', 'episode': rd('episode.json'),
            'lines': pr.read_json('lines.json', []), 'warnings': pr.read_json('episode_warnings.json', []),
            'metadata': pr.read_json('metadata.json', None), 'job': jobs.get(slug), 'qc': _qc_of(pr),
            'capabilities': _read_caps(pr),
            'previews': sorted(os.path.basename(f) for f in glob.glob(pr.p('preview', '*.jpg')))}

@app.put('/api/projects/{slug}/meta')
def put_meta(slug: str, data: dict = Body(...)):
    pr = _proj(slug); pr.meta.update(data); pr.save(); return {'ok': True}

@app.put('/api/projects/{slug}/script')
def put_script(slug: str, data: dict = Body(...)):
    pr = _proj(slug); open(pr.p('script.txt'), 'w', encoding='utf-8').write(data.get('script', ''))
    return {'ok': True}

@app.put('/api/projects/{slug}/episode')
def put_episode(slug: str, data: dict = Body(...)):
    pr = _proj(slug); lines = pr.read_json('lines.json', [])
    try: ep = json.loads(data.get('episode', ''))
    except json.JSONDecodeError as e: raise HTTPException(400, f'JSON invalide : {e}')
    ep, W = validate(ep, len(lines), pr.meta.get('style', 'pixel3d'))
    pr.write_json('episode.json', ep); pr.write_json('episode_warnings.json', W)
    if pr.exists('mix.wav'): os.remove(pr.p('mix.wav'))
    return {'ok': True, 'warnings': W}

# ---------------- local audio input (the owner's own recordings, no TTS)
# An uploaded file is never trusted: the name it carries is dropped (ours is used), the bytes are written with a
# size cap, and the file is validated by audio_in.check before anything replaces the project's voice. Nothing is
# ever passed to a shell, and no endpoint here accepts a path -- only a plain name inside the project's audio/.
def _save_upload(file, dst, max_bytes=AI.MAX_BYTES):
    """streams an upload to dst (a path we chose), refusing anything over the cap"""
    n = 0
    with open(dst, 'wb') as f:
        while True:
            chunk = file.file.read(1 << 20)
            if not chunk: break
            n += len(chunk)
            if n > max_bytes:
                f.close(); os.remove(dst)
                raise HTTPException(400, f'Fichier trop gros (maximum {max_bytes / 1e6:.0f} Mo).')
            f.write(chunk)
    if not n:
        os.remove(dst); raise HTTPException(400, 'Fichier vide.')
    return dst

def _upload_ext(file):
    """the extension of the uploaded name, checked against the allowlist; the rest of the name is discarded"""
    ext = os.path.splitext(file.filename or '')[1].lower()
    if ext not in AI.EXTS: raise HTTPException(400, f'Format non géré : {ext or "(aucune extension)"}. Acceptés : {", ".join(AI.EXTS)}')
    return ext

@app.post('/api/projects/{slug}/voice')
async def upload_voice(slug: str, file: UploadFile = File(...)):
    """one local audio file as the whole voice track (import, validation, conversion to voice.mp3)"""
    pr = _proj(slug); tmp = pr.p('upload_voix' + _upload_ext(file))
    try:
        _save_upload(file, tmp)
        info = P.import_voice(pr, tmp)
    except AI.AudioInputError as e: raise HTTPException(400, str(e))
    finally:
        if os.path.exists(tmp): os.remove(tmp)
    return {'ok': True, 'duration': info['duration'], 'codec': info['codec'], 'name': file.filename}

@app.get('/api/projects/{slug}/audio')
def list_clips(slug: str):
    """the clips of projects/<slug>/audio/ and the voice sheet, for the per-line local voice"""
    pr = _proj(slug); root = AI.audio_dir(pr.dir); out = []
    for n in AI.clips_of(pr.dir):
        try:
            i = AI.check(os.path.join(root, n)); out.append({'name': n, 'duration': i['duration'], 'codec': i['codec'], 'bytes': i['bytes']})
        except AI.AudioInputError as e: out.append({'name': n, 'error': str(e)})
    sheet = None
    if os.path.exists(os.path.join(pr.dir, AI.SHEET)):
        try: sheet = AI.read_sheet(pr.dir)
        except AI.AudioInputError as e: sheet = {'error': str(e)}
    return {'clips': out, 'sheet': sheet, 'folder': AI.AUDIO_DIR}

@app.post('/api/projects/{slug}/audio')
async def upload_clip(slug: str, file: UploadFile = File(...)):
    """one clip into projects/<slug>/audio/ : the name is rebuilt by us, the audio is validated before it is kept"""
    pr = _proj(slug); d = AI.audio_dir(pr.dir, create=True)
    # the name is checked, never repaired: a browser sends a plain file name, so anything else is worth a visible
    # refusal rather than a silent rename that hides what the client really sent.
    try: name = AI.safe_name(file.filename)
    except AI.AudioInputError as e: raise HTTPException(400, str(e))
    _upload_ext(file)
    dst = os.path.join(d, name)
    try:
        _save_upload(file, dst)
        info = AI.check(dst)
    except AI.AudioInputError as e:
        if os.path.exists(dst): os.remove(dst)
        raise HTTPException(400, str(e))
    return {'ok': True, 'name': name, 'duration': info['duration'], 'codec': info['codec']}

@app.post('/api/projects/{slug}/audio/sheet')
def build_sheet(slug: str):
    """a voice sheet ready to fill in (one line per phrase, the clips found in audio/ in name order)"""
    pr = _proj(slug)
    try: return {'ok': True, 'sheet': P.voice_sheet(pr, log=lambda m: None)}
    except AI.AudioInputError as e: raise HTTPException(400, str(e))
    except RuntimeError as e: raise HTTPException(400, str(e))

@app.put('/api/projects/{slug}/audio/sheet')
def put_sheet(slug: str, data: dict = Body(...)):
    """saves a voice sheet, refused unless it covers the whole script with real audio inside audio/"""
    pr = _proj(slug); sheet = data.get('sheet', data)
    try:
        P.check_sheet(pr, sheet)
        AI.write_sheet(pr.dir, sheet)
    except AI.AudioInputError as e: raise HTTPException(400, str(e))
    except RuntimeError as e: raise HTTPException(400, str(e))
    return {'ok': True}

@app.get('/api/projects/{slug}/file/{path:path}')
def get_file(slug: str, path: str):
    pr = _proj(slug); f = os.path.realpath(pr.p(path))
    if not f.startswith(os.path.realpath(pr.dir)) or not os.path.isfile(f): raise HTTPException(404)
    return FileResponse(f)

def _qc_of(pr):
    from ..acting.qc import summary
    out = {}
    for a in ('9:16', '16:9'):
        r = pr.read_json(f"qc_{a.replace(':', 'x')}.json")
        if r and r.get('engine') == 'voxel-v4':       # rapport du moteur VOXEL V4 (hstudio/voxelgpu/studio_bridge.py)
            e = r.get('encoded') or {}
            out[a] = {'score': None, 'summary': 'VOXEL V4 (GPU) — ' + r.get('staging', '') + (' — fichier : ' + ('lisible' if e.get('ok') else str(e.get('reason', 'à vérifier'))) if e else '')}
        elif r: out[a] = {'score': r.get('score'), 'summary': summary(r)}
    return out

STEPS = {
    'voice': ('Voix ElevenLabs', lambda pr, s, j, o: P.step_voice(pr, s, j.write)),
    'draft_voice': ('Voix de brouillon (gratuite)', lambda pr, s, j, o: P.step_draft_voice(pr, s, j.write) and None),
    'local_voice': ('Voix locale (mes enregistrements)', lambda pr, s, j, o: P.step_local_voice(pr, s, j.write) and None),
    'qc': ('Contrôle qualité', lambda pr, s, j, o: P.step_qc(pr, s, o.get('aspect', '9:16'), j.write) and None),
    'align': ('Calage de la voix', lambda pr, s, j, o: P.step_align(pr, s, j.write) and None),
    'direct': ('Mise en scène', lambda pr, s, j, o: P.step_direct(pr, s, j.write) and None),
    'preview': ('Aperçu des plans', lambda pr, s, j, o: P.step_preview(pr, s, o.get('aspect', '9:16'), j.write)),
    'mix': ('Mixage du son', lambda pr, s, j, o: P.step_mix(pr, s, j.write)),
    'render': ('Rendu vidéo', lambda pr, s, j, o: os.path.basename(P.step_render(pr, s, o.get('aspect', '9:16'), o.get('quality'), j.prog, j.write))),
    'metadata': ('Titres et hashtags', lambda pr, s, j, o: P.step_metadata(pr, s, j.write)),
    'thumbnail': ('Miniatures', lambda pr, s, j, o: P.step_thumbnail(pr, s, j.write)),
    'all': ('Tout automatiquement', lambda pr, s, j, o: [os.path.basename(x) for x in P.run_all(pr, s, tuple(o.get('aspects', ['9:16'])), j.write, j.prog)]),
    'oneclick': ('Parcours en un clic', lambda pr, s, j, o: OC.run(pr, s, o, j)),
}

@app.post('/api/projects/{slug}/run/{step}')
def run_step(slug: str, step: str, opts: dict = Body(default={})):
    pr = _proj(slug)
    if step not in STEPS: raise HTTPException(404, 'étape inconnue')
    name, fn = STEPS[step]; s = P.load_settings()
    if opts.get('director'): pr.meta['director'] = opts['director']; pr.save()
    if step == 'oneclick':
        # ce qui manque est dit AVANT de lancer la tâche : un refus lisible vaut mieux qu'une erreur au rendu
        bad = [p for p in OC.preflight(pr, s, opts) if not p.startswith('Metteur en scène')]
        if bad: raise HTTPException(400, ' ; '.join(bad))
    try: jobs.start(slug, name, lambda j: fn(pr, s, j, opts))
    except RuntimeError as e: raise HTTPException(409, str(e))
    return {'ok': True}

@app.get('/api/projects/{slug}/oneclick')
def oneclick_plan(slug: str, aspects: str = '9:16'):
    """l'état du parcours : une étape par ligne, lu sur les fichiers du projet (aucun effet de bord)"""
    pr = _proj(slug)
    return OC.plan(pr, {'aspects': [a for a in aspects.split(',') if a]})

@app.get('/api/story/options')
def story_options():
    """les valeurs que le brief accepte, lues dans le code (jamais recopiées dans l'interface)"""
    from ..director import story as ST
    return {'genres': sorted(ST.GENRES), 'voice_modes': list(ST.VOICE_MODES), 'engines': list(ST.ENGINES),
            'voice_sources': OC.VOICE_MODES, 'qualities': sorted(P.QUALITY), 'aspects': list(OC.ASPECTS),
            'stages': [{'key': k, 'label': l} for k, l, _, _ in OC.STAGES]}

@app.post('/api/story/project')
def story_project(data: dict = Body(default={})):
    """un brief -> un projet prêt à fabriquer (script, plan d'histoire, épisode validé), et le parcours au besoin.

    `provider` reste `mock` par défaut : le gabarit déterministe hors ligne de `director/story.py`, sans clé et
    sans coût. Un autre provider appelle une IA payante, à la demande explicite de l'appelant."""
    s = P.load_settings()
    try: pr, outline = OC.project_from_brief(data, s, log=lambda m: None)
    except RuntimeError as e: raise HTTPException(400, str(e))
    except Exception as e: raise HTTPException(400, f'Brief inutilisable : {e}')
    opts = OC.options(data.get('opts') or {})
    out = {'slug': pr.slug, 'style': pr.meta.get('style'), 'beats': len(outline.beats),
           'choices': [c.letter for c in outline.choices], 'seconds': round(outline.seconds(), 1),
           'generator': outline.generator, 'place': outline.place, 'summary': outline.summary,
           'plan': OC.plan(pr, opts)}
    if data.get('run'):
        bad = [p for p in OC.preflight(pr, s, opts) if not p.startswith('Metteur en scène')]
        if bad: raise HTTPException(400, ' ; '.join(bad))
        name, fn = STEPS['oneclick']
        try: jobs.start(pr.slug, name, lambda j: fn(pr, s, j, opts))
        except RuntimeError as e: raise HTTPException(409, str(e))
        out['started'] = True
    return out

@app.get('/api/projects/{slug}/job')
def job(slug: str): return jobs.get(slug) or {}

@app.delete('/api/projects/{slug}')
def delete_project(slug: str, definitif: bool = False):
    """`definitif=true` : supprime le dossier pour de bon (l'espace est rendu). Sans lui : corbeille (récupérable, ne libère rien)."""
    from .. import storage as ST
    _proj(slug)
    try: freed = ST.delete(slug, trash=not definitif)
    except (RuntimeError, ValueError) as e: raise HTTPException(409, str(e))
    return {'ok': True, 'freed': freed, 'definitif': bool(definitif)}

# ---------------- voir le résultat d'un plan AVANT de le valider (hstudio/shot_preview.py)
def _style_of_project(pr):
    from .. import shot_preview as SP, pipeline as P
    return SP.style_of(pr.meta, P.load_settings())

@app.get('/api/shot_preview/options')
def shot_preview_options(style: str, slug: str = '', index: int = -1):
    """ce que le style sait faire (cadrages, mouvements, expressions, transitions) ; avec `slug` + `index` : les réglages actuels du plan en plus"""
    from .. import shot_preview as SP
    ep = None
    if slug and index >= 0: ep = _proj(slug).read_json('episode.json', None)
    ok = bool(ep) and index < len(ep.get('shots') or [])
    try: out = SP.options(style, ep if ok else None, index if ok else None)
    except ValueError as e: raise HTTPException(400, str(e))
    if ok: out['current'] = SP.current(ep, index, style)
    return out

@app.post('/api/projects/{slug}/shot_preview')
def shot_preview(slug: str, data: dict = Body(...)):
    """fabrique un court clip du plan avec le réglage en attente ; RIEN n'est enregistré dans le projet"""
    from .. import shot_preview as SP
    pr = _proj(slug); index = data.get('index'); patch = data.get('patch') or {}; aspect = data.get('aspect') or '9:16'
    if not isinstance(index, int): raise HTTPException(400, "Numéro de plan manquant.")
    try: SP.apply_patch(pr.read_json('episode.json', {}), index, patch, _style_of_project(pr))     # on refuse tout de suite un réglage impossible
    except ValueError as e: raise HTTPException(400, str(e))
    def work(j): return SP.render_shot_clip(slug, index, patch, aspect, progress=j.prog, log=j.write)
    try: jobs.start(slug, f'Aperçu du plan {index + 1}', work)
    except RuntimeError as e: raise HTTPException(409, str(e))
    return {'started': True}

@app.post('/api/projects/{slug}/shot_apply')
def shot_apply(slug: str, data: dict = Body(...)):
    """valide : le MÊME réglage est appliqué à l'épisode du projet et enregistré"""
    from .. import shot_preview as SP
    pr = _proj(slug); index = data.get('index'); lines = pr.read_json('lines.json', [])
    if not isinstance(index, int): raise HTTPException(400, "Numéro de plan manquant.")
    try: ep = SP.apply_patch(pr.read_json('episode.json', {}), index, data.get('patch') or {}, _style_of_project(pr))
    except ValueError as e: raise HTTPException(400, str(e))
    ep, W = validate(ep, len(lines), pr.meta.get('style', 'pixel3d'))
    pr.write_json('episode.json', ep); pr.write_json('episode_warnings.json', W)
    if pr.exists('mix.wav'): os.remove(pr.p('mix.wav'))
    return {'ok': True, 'warnings': W}

# ---------------- espace disque (hstudio/storage.py)
@app.get('/api/storage')
def storage_info(refresh: bool = False):
    from .. import storage as ST
    sz = ST.sizes(max_age=0. if refresh else 30.); tr = ST.trash_list()
    return {'projects': sz, 'trash': tr, 'trash_bytes': sum(t['size'] for t in tr), 'total_bytes': sum(v['total'] for v in sz.values())}

@app.post('/api/projects/{slug}/clean')
def clean_project(slug: str):
    """libère les fichiers que le studio sait refaire (vidéos, travail du moteur, aperçus, mixage) ; garde script, voix, calage, plans, réglages"""
    from .. import storage as ST
    _proj(slug)
    try: return {'ok': True, 'freed': ST.clean(slug)}
    except (RuntimeError, ValueError) as e: raise HTTPException(409, str(e))

@app.delete('/api/trash')
def trash_empty():
    from .. import storage as ST
    return {'ok': True, 'freed': ST.trash_empty()}

@app.post('/api/trash/{name}/restore')
def trash_restore(name: str):
    from .. import storage as ST
    try: return {'ok': True, 'slug': ST.trash_restore(name)}
    except FileNotFoundError as e: raise HTTPException(404, str(e))

# ---------------- long compilation
@app.get('/api/longs')
def longs():
    out = []
    for p in list_projects():
        for r in p['status']['renders']:
            if '16x9' in r: out.append({'slug': p['slug'], 'name': p['name'], 'part_label': p.get('part_label'), 'file': r})
    return out

@app.post('/api/compile')
def compile_api(data: dict = Body(...)):
    items = data.get('items', [])
    if len(items) < 1: raise HTTPException(400, 'choisis au moins une vidéo')
    out_dir = os.path.join(paths.PROJECTS, '_compilations'); os.makedirs(out_dir, exist_ok=True)
    name = P.slugify(data.get('title') or 'compilation')
    def fn(j):
        lst = [(P.Project(it['slug']).p('renders', it['file']), it.get('chapter') or it['slug']) for it in items]
        if data.get('intro'): lst.insert(0, (data['intro'], 'Introduction'))
        out, chapters = compile_long(lst, os.path.join(out_dir, f'{name}.mp4'), data.get('title', ''), log=j.write)
        open(os.path.join(out_dir, f'{name}_chapitres.txt'), 'w', encoding='utf-8').write(chapters)
        j.write('Chapitres pour la description YouTube :\n' + chapters)
        return {'file': os.path.basename(out), 'chapters': chapters}
    try: jobs.start('_compile', 'Compilation longue', fn)
    except RuntimeError as e: raise HTTPException(409, str(e))
    return {'ok': True}

@app.get('/api/compile/job')
def compile_job(): return jobs.get('_compile') or {}

@app.get('/api/compile/file/{name}')
def compile_file(name: str):
    f = os.path.join(paths.PROJECTS, '_compilations', os.path.basename(name))
    if not os.path.isfile(f): raise HTTPException(404)
    return FileResponse(f)

# ---------------- demos, characters, places (studio demo version)
@app.get('/api/demos')
def list_demos_api():
    from .. import demos
    out = []
    for d in demos.list_demos():
        pr = P.Project(d['id'])
        st = pr.status() if pr.meta else {'renders': []}
        out.append(dict(d, renders=st['renders'], qc=_qc_of(pr) if pr.meta else {}, job=jobs.get('demo:' + d['id'])))
    return out

@app.post('/api/demos/{demo_id}/run')
def run_demo(demo_id: str, opts: dict = Body(default={})):
    from .. import demos
    if demo_id not in [d['id'] for d in demos.list_demos()]: raise HTTPException(404, 'démo inconnue')
    aspects = [a for a in (opts.get('aspects') or demos.load(demo_id).get('aspects', ['16:9'])) if a in ('9:16', '16:9')]
    qc_only = bool(opts.get('qc_only'))
    def fn(j):
        pr, outs = demos.build(demo_id, aspects, opts.get('quality', 'standard'), j.write, j.prog, qc_only=qc_only)
        return [os.path.basename(o) for o in outs]
    try: jobs.start('demo:' + demo_id, ('Contrôle qualité : ' if qc_only else 'Démo : ') + demo_id, fn)
    except RuntimeError as e: raise HTTPException(409, str(e))
    return {'ok': True}

@app.get('/api/demos/{demo_id}/job')
def demo_job(demo_id: str): return jobs.get('demo:' + demo_id) or {}

@app.get('/api/characters')
def characters():
    from ..acting import cast
    return [{k: c.get(k) for k in ('id', 'name', 'notes', 'voice', 'personality', 'relations')} | {'kind': (c.get('look') or {}).get('kind')} for c in cast.list_characters()]

@app.get('/api/characters/{cid}/portrait.png')
def character_portrait(cid: str):
    from ..engines.pixel3d.portrait import portrait
    f = portrait(os.path.basename(cid))
    if not f: raise HTTPException(404)
    return FileResponse(f, media_type='image/png')

@app.get('/api/places')
def places():
    from ..engines.pixel3d.places import PLACES
    return sorted(PLACES)

# ---------------- V3: what a scene needs, what the engines have, extension requests
@app.post('/api/plan')
def plan_scene(opts: dict = Body(default={})):
    from ..capabilities import planner, extensions
    rep = planner.plan(str(opts.get('text', ''))[:20000], engine=opts.get('engine', 'pixel3d') if opts.get('engine') in ('pixel3d', 'console') else 'pixel3d')
    if opts.get('requests'): rep['written'] = [os.path.basename(p) for p in planner.write_requests(rep)]
    rep['extensions'] = [{'id': m['id'], 'title': m.get('title', ''), 'status': m.get('status'), 'loaded': m['id'] in extensions.LOADED,
                          'problem': extensions.PROBLEMS.get(m['id'])} for m in extensions.manifests()]
    return rep

# ---------------- clip musical (31/10/2026) : une musique -> analyse + feuille de temps pour le directeur (hstudio/audio/music_clip.py)
CLIPS = os.path.join(paths.PROJECTS, '_clips_musicaux')
_CLIP_FILES = {'musique.wav': 'audio/wav', 'FEUILLE_MUSIQUE.md': 'text/markdown; charset=utf-8', 'analysis.json': 'application/json'}

def _clip_dir(slug):
    import re
    if not re.fullmatch(r'[a-z0-9_]{1,60}', slug or ''): raise HTTPException(400, 'nom de clip refusé')
    return os.path.join(CLIPS, slug)

def _clip_summary(slug):
    d = _clip_dir(slug); a = os.path.join(d, 'musique', 'analysis.json')
    if not os.path.isfile(a): return None
    A = json.load(open(a, encoding='utf-8')); ev = A['energy']['v']; step = max(1, len(ev) // 240)
    return {'slug': slug, 'source': A.get('source'), 'tempo': A['tempo'], 'duration': A['duration'], 'climax': A['climax'],
            'sections': A['sections'], 'silences': A['silences'], 'downbeats': A['downbeats'], 'phrases': (A.get('vocal') or {}).get('phrases', []),
            'energy': ev[::step], 'energy_hz': A['energy']['hz'] / step,
            'films': sorted(os.path.basename(f) for f in glob.glob(os.path.join(d, '*.mp4')))}

@app.get('/api/clips')
def clips_list():
    if not os.path.isdir(CLIPS): return []
    out = [_clip_summary(s) for s in sorted(os.listdir(CLIPS)) if os.path.isdir(os.path.join(CLIPS, s))]
    return [c for c in out if c]

@app.post('/api/clips')
async def clip_new(nom: str = 'clip', debut: float = 0., fin: float = 0., file: UploadFile = File(...)):
    """une musique (son nom est refait par nous) -> projects/_clips_musicaux/<nom>/musique/ : analyse, extrait, feuille"""
    import re, unicodedata
    from ..audio import music_clip as MCL
    slug = re.sub(r'[^a-z0-9]+', '_', unicodedata.normalize('NFKD', nom).encode('ascii', 'ignore').decode().lower()).strip('_')[:60] or 'clip'
    ext = _upload_ext(file); d = os.path.join(_clip_dir(slug), 'musique'); os.makedirs(d, exist_ok=True)
    src = os.path.join(d, 'source' + ext)
    _save_upload(file, src)
    if fin and fin <= debut: raise HTTPException(400, 'la fin doit venir après le début')
    try: MCL.prepare(src, d, float(debut), float(fin) if fin else None, label=os.path.basename(file.filename or '')[:120] or None)
    except Exception as e: raise HTTPException(400, f'analyse impossible : {e}')
    return _clip_summary(slug)

@app.get('/api/clips/{slug}/file/{name}')
def clip_file(slug: str, name: str):
    d = _clip_dir(slug)
    if name in _CLIP_FILES: f = os.path.join(d, 'musique', name); mt = _CLIP_FILES[name]
    elif name.endswith('.mp4') and os.path.basename(name) == name: f = os.path.join(d, name); mt = 'video/mp4'
    else: raise HTTPException(404)
    if not os.path.isfile(f): raise HTTPException(404)
    return FileResponse(f, media_type=mt)
