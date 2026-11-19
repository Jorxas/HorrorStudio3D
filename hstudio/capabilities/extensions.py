"""Extensions: new capabilities added to the engines without touching their stable code (V3, level 2).

An extension lives in library/extensions/<id>/:
  manifest.json   {"id", "title", "status": "candidate" | "stable", "module": "x.py", "sha256" (set at promotion),
                   "provides": [{"kind", "name", "terms": [...]}], "tests": [{"scene": "test_scene.json", "times": [...],
                   "aspect": "16:9"}], "requested_by": "...", "promoted": "YYYY-MM-DD"}
  <module>.py     def register(api): api.prop(...), api.sfx(...), api.effect(...), api.verb(...), api.place(...),
                  api.element(...), api.creature(...)
Safety rules
  - production loads only "stable" extensions whose module still has the sha256 recorded at promotion: an extension
    modified after its validation is not loaded (and the reason is reported), the stable engine never changes silently;
  - a candidate is only loaded by its own test, in a separate process (HSTUDIO_EXT_TRY), never during a production;
  - test(): renders the test scenes twice (determinism), checks the frames are not empty, checks the capability really
    registered, then runs the non-regression guard with the candidate loaded; promote() needs a passing report for the
    exact current file.
An extension request (planner.py) describes what to build; the code itself is written by a developer or a development
agent, then goes through test() and promote()."""
import os, json, hashlib, importlib.util, subprocess, sys, datetime
from .. import paths

EXT_DIR = os.path.join(paths.ROOT, 'library', 'extensions')
LOADED = {}          # id -> [provided capabilities]
PROBLEMS = {}        # id -> reason it was not loaded
_done = [False]

def sha256(path):
    """fingerprint of a module, line endings normalised (a git checkout may turn LF into CRLF)"""
    return hashlib.sha256(open(path, 'rb').read().replace(b'\r\n', b'\n')).hexdigest()

def manifests():
    out = []
    if not os.path.isdir(EXT_DIR): return out
    for d in sorted(os.listdir(EXT_DIR)):
        mf = os.path.join(EXT_DIR, d, 'manifest.json')
        if os.path.isfile(mf):
            try: m = json.load(open(mf, encoding='utf-8')); m['_dir'] = os.path.join(EXT_DIR, d); out.append(m)
            except Exception as e: PROBLEMS[d] = f'manifeste illisible : {e}'
    return out

class API:
    """what an extension may register (and nothing else): every call is recorded as a provided capability"""
    def __init__(self, ext_id): self.id = ext_id; self.provided = []
    def _rec(self, kind, name, **kw): self.provided.append(dict(kind=kind, name=name, source=f'extension:{self.id}', **kw))
    def prop(self, name, builder, lights=None, terms=(), label=''):
        """builder(p, color) -> boxes in local coordinates (bottom at y = 0, front towards -z at rot 0)"""
        from ..engines.pixel3d import world as W, sets as S
        W.PROPS[name] = builder
        if lights: W.PROP_LIGHTS[name] = lights
        if name not in S.PROP_TYPES: S.PROP_TYPES.append(name)
        self._rec('prop', name, terms=list(terms), label=label)
    def sfx(self, name, fn, description='', long=False, terms=()):
        from ..audio import synth as S
        S.SFX[name] = fn; S.SFX_DESCRIPTIONS[name] = description or name
        if long and name not in S.LONG_SFX: S.LONG_SFX = tuple(S.LONG_SFX) + (name,)
        self._rec('sound', name, terms=list(terms), label=description)
    def effect(self, name, fn, sounds=None, terms=(), label=''):
        from ..engines.pixel3d import effects as FX
        FX.EFFECTS[name] = fn
        if sounds is not None: FX.SOUNDS[name] = sounds
        self._rec('effect', name, terms=list(terms), label=label)
    def verb(self, name, fn, terms=(), label=''):
        from ..acting import timeline as TL
        TL.VERBS[name] = fn; self._rec('action', name, terms=list(terms), label=label)
    def place(self, name, generator, ambience=None, terms=(), label=''):
        from ..engines.pixel3d import places as PL, sets as S
        PL.PLACES[name] = generator
        if ambience: PL.DEFAULT_AMBIENCE[name] = ambience
        if name not in S.PLACE_TYPES: S.PLACE_TYPES.append(name)
        self._rec('place', name, terms=list(terms), label=label)
    def element(self, name, builder, terms=(), label=''):
        """builder(element, ctx) for composed sets (compose.py)"""
        from ..engines.pixel3d import compose as CO
        CO.BUILDERS[name] = builder; CO.ELEMENTS = tuple(CO.ELEMENTS) + (name,)
        self._rec('element', name, terms=list(terms), label=label)
    def creature(self, name, builder, terms=(), label=''):
        """builder(color, swing, t, k, posture) -> boxes facing +z, feet on y = 0"""
        from ..engines.pixel3d import creatures as CR
        CR.EXTRA[name] = builder
        if name not in CR.ANIMALS: CR.ANIMALS = tuple(CR.ANIMALS) + (name,)
        self._rec('creature', name, terms=list(terms), label=label)

def _load_one(m, check_hash=True):
    mod_path = os.path.join(m['_dir'], m.get('module', 'extension.py'))
    if not os.path.isfile(mod_path): PROBLEMS[m['id']] = 'module absent'; return False
    if check_hash and m.get('sha256') != sha256(mod_path):
        PROBLEMS[m['id']] = 'module modifié depuis sa validation (empreinte différente) : non chargé, relancer le test puis la promotion'; return False
    spec = importlib.util.spec_from_file_location(f"hstudio_ext_{m['id']}", mod_path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    api = API(m['id']); mod.register(api); LOADED[m['id']] = api.provided
    return True

def ensure_loaded():
    """load the stable extensions once per process (+ the candidates named in HSTUDIO_EXT_TRY, for their own test)"""
    if _done[0]: return
    _done[0] = True
    trying = [x for x in os.environ.get('HSTUDIO_EXT_TRY', '').split(',') if x]
    for m in manifests():
        try:
            if m.get('status') == 'stable': _load_one(m, check_hash=True)
            elif m.get('id') in trying: _load_one(m, check_hash=False)
        except Exception as e:
            PROBLEMS[m.get('id', '?')] = f'erreur au chargement : {e}'

def provided():
    ensure_loaded(); return [c for v in LOADED.values() for c in v]

# ------------------------------------------------------------------ test and promotion (outside production)
def _selftest(ext_id):
    """runs in its own process with HSTUDIO_EXT_TRY=<id>: loads the candidate, renders its test scenes twice"""
    import numpy as np
    from .. import demos
    from ..pipeline import make_engine, duration_of
    ensure_loaded()
    m = next(x for x in manifests() if x['id'] == ext_id); rep = {'id': ext_id, 'checks': [], 'ok': True}
    def check(name, ok, detail=''):
        rep['checks'].append(dict(name=name, ok=bool(ok), detail=detail)); rep['ok'] = rep['ok'] and bool(ok)
    check('chargement', ext_id in LOADED, PROBLEMS.get(ext_id, ''))
    got = {(c['kind'], c['name']) for c in LOADED.get(ext_id, [])}
    for p in m.get('provides', []): check(f"fournit {p['kind']}:{p['name']}", (p['kind'], p['name']) in got)
    from PIL import Image
    sheet = []
    for tst in m.get('tests', []):
        sc = json.load(open(os.path.join(m['_dir'], tst['scene']), encoding='utf-8'))
        lines = demos.timed_lines(sc['script'], float(sc.get('gap', .3)), float(sc.get('lead', .4)))
        ep = demos.episode_of(sc, lines, log=lambda *a: None)
        hashes = []
        for run in range(2):
            eng = make_engine(sc.get('style', 'pixel3d'), json.loads(json.dumps(ep)), lines, np.zeros(10), duration_of(ep, lines), tst.get('aspect', '16:9'))
            ims = [np.asarray(eng.frame(float(t)).convert('RGB')) for t in tst.get('times', [.5])]
            hashes.append([hashlib.sha1(a.tobytes()).hexdigest() for a in ims])
            if run == 0:
                check(f"{tst['scene']} : images non vides", all(a.std() > 4 for a in ims))
                sheet += [Image.fromarray(a).resize((a.shape[1] // 4, a.shape[0] // 4)) for a in ims]
        check(f"{tst['scene']} : rendu déterministe", hashes[0] == hashes[1])
    if sheet:
        w, h = sheet[0].size; im = Image.new('RGB', (w * len(sheet), h))
        for k, s in enumerate(sheet): im.paste(s, (k * w, 0))
        im.save(os.path.join(m['_dir'], 'test_sheet.png')); rep['sheet'] = 'test_sheet.png'
    return rep

def test(ext_id, log=print):
    m = next((x for x in manifests() if x['id'] == ext_id), None)
    if m is None: raise SystemExit(f'extension inconnue : {ext_id}')
    env = dict(os.environ, HSTUDIO_EXT_TRY=ext_id)
    log(f'Test de {ext_id} dans un processus séparé (le moteur stable n\'est pas modifié)...')
    out = subprocess.run([sys.executable, '-m', 'hstudio', 'extension', '_selftest', ext_id], cwd=paths.ROOT, env=env, capture_output=True, text=True, encoding='utf-8')
    try: rep = json.loads(out.stdout.strip().splitlines()[-1])
    except Exception: rep = {'id': ext_id, 'ok': False, 'checks': [dict(name='auto-test', ok=False, detail=(out.stderr or out.stdout)[-1500:])]}
    log('Garde de non-régression avec l\'extension chargée (tools/regress.py)...')
    base = 'tests/baseline_local.json' if os.path.exists(os.path.join(paths.ROOT, 'tests', 'baseline_local.json')) else 'tests/baseline.json'
    rg = subprocess.run([sys.executable, os.path.join('tools', 'regress.py'), 'check', base], cwd=paths.ROOT, env=env, capture_output=True, text=True, encoding='utf-8')
    rep['checks'].append(dict(name=f'non-régression ({base})', ok=rg.returncode == 0, detail=rg.stdout.strip()[-600:])); rep['ok'] = rep['ok'] and rg.returncode == 0
    rep['sha256'] = sha256(os.path.join(m['_dir'], m.get('module', 'extension.py')))
    json.dump(rep, open(os.path.join(m['_dir'], 'test_report.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for c in rep['checks']: log(f"  {'OK ' if c['ok'] else 'ÉCHEC'}  {c['name']}" + (f"  ({c['detail']})" if c.get('detail') and not c['ok'] else ''))
    log('Test réussi : l\'extension peut être promue.' if rep['ok'] else 'Test échoué : l\'extension reste candidate.')
    return rep

def promote(ext_id, log=print):
    m = next((x for x in manifests() if x['id'] == ext_id), None)
    if m is None: raise SystemExit(f'extension inconnue : {ext_id}')
    rp = os.path.join(m['_dir'], 'test_report.json')
    rep = json.load(open(rp, encoding='utf-8')) if os.path.exists(rp) else None
    cur = sha256(os.path.join(m['_dir'], m.get('module', 'extension.py')))
    if not rep or not rep.get('ok'): raise SystemExit('Promotion refusée : pas de test réussi (python -m hstudio extension test ' + ext_id + ').')
    if rep.get('sha256') != cur: raise SystemExit('Promotion refusée : le module a changé depuis le test réussi.')
    mf = os.path.join(m['_dir'], 'manifest.json'); data = json.load(open(mf, encoding='utf-8'))
    data.update(status='stable', sha256=cur, promoted=datetime.date.today().isoformat())
    json.dump(data, open(mf, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for p in data.get('provides', []):                       # the requests this extension answers are closed
        rq = os.path.join(EXT_DIR, 'requests', f"{p['kind']}_{p['name']}.json")
        if os.path.exists(rq):
            r = json.load(open(rq, encoding='utf-8')); r.update(status='réalisée', by=f'extension {ext_id}', date=data['promoted'])
            json.dump(r, open(rq, 'w', encoding='utf-8'), ensure_ascii=False, indent=1); log(f'Demande {os.path.basename(rq)} : réalisée.')
    log(f'{ext_id} est maintenant stable (empreinte {cur[:12]}…) : chargée par la production.')
