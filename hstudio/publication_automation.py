"""Durable A-to-Z orders over the existing oneclick pipeline. No mock story or draft voice is publishable."""
import os, json, sqlite3, hashlib, threading, time
from contextlib import contextmanager
from . import paths, pipeline as P, oneclick as OC, jobs
from . import publication_bridge as PB

_init_lock = threading.Lock()
_initialized = set()
_render_slot = threading.Semaphore(1)
_voice_cache = {'at':0,'key':None,'voices':[]}

def voices():
    from . import tts
    settings=P.load_settings();key=settings.get('elevenlabs_api_key')
    if not key: raise ValueError('Renseignez la connexion ElevenLabs du studio pour choisir une voix réelle.')
    fingerprint=hashlib.sha256(key.encode()).hexdigest()
    if _voice_cache['key']!=fingerprint or time.time()-_voice_cache['at']>300:
        try: items=tts.list_voices(key)
        except Exception: raise ValueError('Catalogue des voix indisponible. Vérifiez la connexion ElevenLabs dans le studio.') from None
        _voice_cache.update(at=time.time(),key=fingerprint,voices=items)
    return {'voices':_voice_cache['voices']}

@contextmanager
def _db():
    filename = os.path.join(paths.CONFIG, 'publication-orders.sqlite')
    os.makedirs(paths.CONFIG, exist_ok=True)
    db = sqlite3.connect(filename, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY, digest TEXT NOT NULL, input TEXT NOT NULL, authorization TEXT NOT NULL, status TEXT NOT NULL, phase TEXT NOT NULL, project TEXT, assets TEXT NOT NULL, error TEXT, cancelled INTEGER NOT NULL DEFAULT 0, updated REAL NOT NULL)')
        with _init_lock:
            if filename not in _initialized:
                db.execute("UPDATE orders SET status=CASE WHEN phase IN ('script','voice','direct','metadata') THEN 'reconciliation_required' ELSE 'interrupted' END,error='Studio interrompu. Aucune génération relancée automatiquement.' WHERE status IN ('queued','running','cancelling')")
                db.commit(); _initialized.add(filename)
        with db:
            yield db
    finally:
        db.close()

def _row(request_id):
    with _db() as db:
        row = db.execute('SELECT * FROM orders WHERE id=?', (request_id,)).fetchone()
    if row is None:
        raise KeyError('Commande non trouvée dans Horror Studio.')
    return dict(row)

def _patch(request_id, **values):
    values['updated'] = time.time()
    with _db() as db:
        db.execute('UPDATE orders SET ' + ','.join(k+'=?' for k in values) + ' WHERE id=?', (*values.values(), request_id))

def _project(slug):
    if not slug or os.path.basename(slug) != slug or slug in ('.', '..'):
        raise ValueError('Projet invalide.')
    pr = P.Project(slug)
    if not os.path.isdir(pr.dir): raise ValueError('Projet introuvable.')
    return pr

def inspect(data):
    settings = P.load_settings()
    providers = [name for name, key in [('claude','anthropic_api_key'), ('gemini','gemini_api_key')] if settings.get(key)]
    if os.environ.get('GOOGLE_CLOUD_PROJECT') and os.environ.get('GEMINI_MODEL'): providers.append('gemini_vertex')
    if settings.get('ollama_url'): providers.append('ollama')
    if settings.get('openai_local_url'): providers.append('openai_local')
    problems = []
    if data.get('projectSlug'):
        pr = _project(data['projectSlug'])
        if OC._voice_mode(pr) == 'draft': problems.append('Ce projet utilise une voix de brouillon. Une voix réelle est nécessaire pour la publication automatique.')
        if (pr.meta.get('story') or {}).get('generator') == 'mock': problems.append('Ce projet utilise le gabarit de test ; fournissez une histoire réelle dans le studio.')
        problems.extend(p for p in OC.preflight(pr, settings, {'aspects':data.get('aspects') or ['9:16']}) if not p.startswith('Metteur en scène'))
    elif data.get('premise'):
        from .director import story as ST
        brief = ST.Brief.from_dict({'premise':data['premise'], 'duration_s':data.get('duration',60), 'engine':data.get('engine','auto'), 'genre':'horror', 'n_choices':2})
        problems.extend(brief.problems())
        if data.get('provider') not in providers: problems.append('Choisissez un scénariste réel configuré dans le studio.')
        if not settings.get('elevenlabs_api_key'): problems.append('Clé ElevenLabs nécessaire pour la voix réelle de cette nouvelle histoire.')
        import re
        if not re.fullmatch(r'[a-zA-Z0-9_-]{10,100}',data.get('voiceId','')): problems.append('Choisissez une voix réelle pour la narration.')
        elif settings.get('elevenlabs_api_key') and data['voiceId'] not in [v['voice_id'] for v in voices()['voices']]: problems.append('La voix choisie ne fait pas partie du catalogue de ce compte.')
    else:
        problems.append('Décrivez une histoire ou indiquez un projet existant.')
    from . import ffmpeg_path as FF
    missing=[name for name, location in FF.ensure().items() if not location]
    if missing: problems.append('Outils nécessaires manquants : '+', '.join(missing))
    projects = []
    if os.path.isdir(paths.PROJECTS):
        for slug in sorted(os.listdir(paths.PROJECTS)):
            try:
                pr = _project(slug)
                if pr.meta: projects.append({'slug':slug,'name':pr.meta.get('name') or slug})
            except (ValueError,OSError): pass
    return {'ready':not problems,'problems':problems,'mode':'Parcours complet Horror Studio','languages':['fr'],
            'providers':providers,'projects':projects,'realVoiceRequired':True,'voiceSelectionRequired':True,
            'costNotice':'Le scénariste et la voix utilisent les fournisseurs configurés du studio. Le coût exact n’est pas chiffré ici ; aucune limite financière garantie n’est annoncée. Autorisez ces appels pour cette commande ou utilisez un projet avec script et voix réels déjà prêts.',
            'studioUrl':'https://studio.example.test:8767/'}

def view(request_id):
    row = _row(request_id)
    steps = []
    if row['project']:
        pr = _project(row['project'])
        plan = OC.plan(pr, {'aspects':json.loads(row['input']).get('aspects') or ['9:16']})
        steps = [{'id':s['key'],'status':'completed' if s['done'] else s['state']} for s in plan['stages']]
    return {'id':request_id,'status':row['status'],'phase':row['phase'], 'error':row['error'],
            'progress':round(100*sum(s['status']=='completed' for s in steps)/len(steps)) if steps else 0,
            'steps':steps,'assets':json.loads(row['assets']), 'projectSlug':row['project'],
            'studioUrl':'https://studio.example.test:8767/'}

def start(request_id, data, authorization):
    import re
    if not re.fullmatch(r'[a-zA-Z0-9-]{8,100}', request_id or ''): raise ValueError('Identifiant de commande invalide.')
    if authorization.get('generationConfirmed') is not True: raise ValueError('Autorisation de génération requise.')
    digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    try:
        previous = _row(request_id)
        if previous['status'] == 'cancelled': return view(request_id)
        if previous['digest'] != digest: raise ValueError('Cette commande existe avec une autre entrée.')
        return view(request_id)
    except KeyError: pass
    result = inspect(data)
    if not result['ready']: raise ValueError(' ; '.join(result['problems']))
    with _db() as db:
        created=db.execute('INSERT OR IGNORE INTO orders VALUES(?,?,?,?,?,?,?,?,?,?,?)', (request_id,digest,json.dumps(data),json.dumps(authorization),'queued','En attente du studio',data.get('projectSlug'),'[]',None,0,time.time())).rowcount==1
    if not created:
        previous=_row(request_id)
        if previous['status']!='cancelled' and previous['digest']!=digest: raise ValueError('Cette commande existe avec une autre entrée.')
        return view(request_id)
    _launch(request_id)
    return view(request_id)

class _Cancelled(RuntimeError): pass

def _check(request_id):
    if _row(request_id)['cancelled']: raise _Cancelled('Arrêt demandé ; aucun nouvel envoi.')

class _Progress:
    def __init__(self, request_id, job): self.request_id=request_id; self.job=job
    def write(self, message):
        _check(self.request_id)
        row=_row(self.request_id)
        if row['project']:
            state=OC.read_state(_project(row['project']))
            if state.get('stage'): _patch(self.request_id,phase=state['stage'])
        self.job.write(message)
    def prog(self, value, detail=''):
        _check(self.request_id); self.job.prog(value,detail)

def _publishable(pr, aspects):
    if OC._voice_mode(pr) == 'draft': raise ValueError('Une voix de brouillon ne peut pas être publiée automatiquement.')
    if (pr.meta.get('story') or {}).get('generator') == 'mock': raise ValueError('Un scénario de test ne peut pas être publié automatiquement.')
    for aspect in aspects:
        qc = pr.read_json(OC._qc_file(aspect), {}) or {}
        if qc.get('encoded',{}).get('ok') is not True or any(i.get('level')=='error' for i in qc.get('issues',[])):
            raise ValueError('Contrôle qualité bloquant pour '+aspect+'. Vérifiez le rendu dans le studio.')

def _execute(request_id, job):
    with _render_slot:
        row=_row(request_id)
        if row['cancelled']:
            _patch(request_id,status='cancelled',phase='Annulé avant exécution'); return {'cancelled':True}
        data=json.loads(row['input']); settings=P.load_settings()
        if data.get('voiceId'):
            settings={**settings,'elevenlabs_voice_id':data['voiceId'],'elevenlabs_narrator_voice_id':data['voiceId']}
        with _db() as db:
            claimed=db.execute("UPDATE orders SET status='running',error=NULL,updated=? WHERE id=? AND cancelled=0 AND status='queued'",(time.time(),request_id)).rowcount==1
        if not claimed: return {'claimed':False}
        progress=_Progress(request_id,job)
        try:
            if row['project']: pr=_project(row['project'])
            else:
                _patch(request_id,phase='script')
                pr, _ = OC.project_from_brief({'name':data.get('title'), 'provider':data['provider'], 'voice_mode':'',
                    'brief':{'premise':data['premise'],'duration_s':data.get('duration',60),'engine':data.get('engine','auto'),'genre':'horror','n_choices':2}}, settings, log=progress.write)
                _patch(request_id,project=pr.slug)
            _check(request_id)
            _patch(request_id,phase='Préparation des étapes')
            # These are the studio's real pipeline stages, with no preview frame limit or mock provider.
            aspects=data.get('aspects') or ['9:16']
            result=OC.run(pr,settings,{'aspects':aspects},progress)
            _check(request_id)
            if not result.get('complete'): raise ValueError('Le parcours du studio n’a pas livré tous les fichiers.')
            _publishable(pr,aspects)
            _patch(request_id,phase='Livraison à Publication')
            assets=[]
            for aspect in aspects:
                files=(result.get('renders') or {}).get(aspect) or []
                if not files: raise ValueError('Rendu manquant pour '+aspect)
                _check(request_id)
                prepared=PB.prepare(pr,files[-1],data.get('language','fr'))
                assets.append(prepared['asset']['id']); _patch(request_id,assets=json.dumps(assets))
            _patch(request_id,status='completed',phase='Vidéos validées livrées à Publication',error=None)
            return {'assets':assets}
        except Exception as exc:
            current=_row(request_id)
            if current['cancelled']: _patch(request_id,status='cancelled',error='Arrêt demandé. Les fichiers déjà créés sont conservés.')
            else:
                message=str(exc)
                for name,value in settings.items():
                    if 'api_key' in name and isinstance(value,str) and len(value)>8: message=message.replace(value,'[masqué]')
                _patch(request_id,status='reconciliation_required' if current['phase'] in ('script','voice','direct','metadata') else 'blocked',error=message[:800])
            raise

def _launch(request_id):
    jobs.start('publication:'+request_id,'Création complète et livraison',lambda job:_execute(request_id,job))

def resume(request_id):
    row=_row(request_id)
    if row['status'] not in ('blocked','interrupted'): raise ValueError('Une vérification manuelle est requise avant de reprendre cette génération.')
    if not row['project']: raise ValueError('Le scénario doit être vérifié avant un nouvel appel au fournisseur.')
    data=json.loads(row['input']); data['projectSlug']=row['project']; result=inspect(data)
    if not result['ready']: raise ValueError(' ; '.join(result['problems']))
    _patch(request_id,status='queued',cancelled=0,error=None,phase='Reprise demandée'); _launch(request_id); return view(request_id)

def reconcile(request_id):
    """Inspect existing artifacts only. Never repeats an uncertain provider request."""
    row=_row(request_id)
    if row['status']!='reconciliation_required': return view(request_id)
    job=jobs.get('publication:'+request_id)
    if job and job.get('state')=='running': return view(request_id)
    if not row['project']: return view(request_id)
    pr=_project(row['project']);phase=row['phase'];ready=False
    if phase=='voice' and pr.exists('voice.mp3'):
        from .tts import ffprobe_duration
        try: ready=ffprobe_duration(pr.p('voice.mp3'))>0
        except Exception: ready=False
    elif phase=='script': ready=bool(OC._script_text(pr).strip()) and pr.exists('outline.json') and OC._episode_ok(pr)
    elif phase=='direct': ready=OC._episode_ok(pr)
    elif phase=='metadata': ready=bool((pr.read_json('metadata.json',{}) or {}).get('platforms'))
    if ready: _patch(request_id,status='interrupted',phase='Fichiers existants vérifiés ; reprise possible',error=None)
    return view(request_id)

def cancel(request_id):
    try: row=_row(request_id)
    except KeyError:
        with _db() as db:
            db.execute('INSERT OR IGNORE INTO orders VALUES(?,?,?,?,?,?,?,?,?,?,?)',(request_id,'CANCELLED','{}','{}','cancelled','Annulé avant démarrage',None,'[]',None,1,time.time()))
            db.execute("UPDATE orders SET cancelled=1,status=CASE WHEN status='queued' THEN 'cancelled' ELSE CASE WHEN status IN ('completed','cancelled') THEN status ELSE 'cancelling' END END WHERE id=?",(request_id,))
        return view(request_id)
    if row['status'] in ('completed','cancelled'): return view(request_id)
    _patch(request_id,cancelled=1,status='cancelled' if row['status']=='queued' else 'cancelling',phase='Arrêt demandé')
    return view(request_id)
