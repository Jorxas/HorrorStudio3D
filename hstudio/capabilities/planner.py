"""Scene Capability Planner (V3): what a scene needs, what exists, what is missing, and how to get it.

plan(text, requires, engine) reads a scene (story text, a director's "requires" list) without simplifying it:
  1. finds the needs (lexicon.py, plus the "terms" of extensions), longest expressions first;
  2. looks each one up in the registry built from the code (registry.py);
  3. classifies: native (drawn as such), composed (built by a generator from parameters), partial (an approximation
     exists, said explicitly), missing;
  4. for every missing need, writes an extension request: what to build, where (the extension API hook), the contract
     and the acceptance test. A need is never replaced silently by something easier.
Without an AI the detection is lexical (it finds what the lexicon names); an AI director lists its needs in the
episode's "requires", which the planner resolves the same way (an unknown name is reported as missing)."""
import os, re, json, unicodedata
from . import registry, lexicon
from .. import paths

REQ_DIR = os.path.join(paths.ROOT, 'library', 'extensions', 'requests')
LABELS = {'native': 'disponible', 'composed': 'composé', 'partial': 'partiel', 'missing': 'manquant'}
HOOKS = {
    'prop': ('api.prop(name, builder, lights)', 'builder(p, color) -> boîtes r3d B()/C(), bas à y = 0, face avant vers -z (rot 0), moins de 80 boîtes ; '
             'animation possible avec p["_t"] (temps) quand l\'objet est un "mover"'),
    'creature': ('api.creature(name, builder)', 'builder(color, swing, t, k, posture) -> boîtes face à +z, pieds à y = 0 ; posture "fly" pour le vol'),
    'action': ('api.verb(name, fn)', 'fn(shot, track, action, t0) -> t1 : chemins (shot.walk), segments en l\'air (track.airs), flexions (track.squats), '
               'mains (track.reaches), événements sonores (track.events) ; partagé par PIXEL 3D et CONSOLE (acting/motion.py en exemple)'),
    'effect': ('api.effect(name, fn, sounds)', 'fn(fx, o) -> (boîtes, lumières) image par image, déterministe ; sounds(o) -> [(t, son, gain, durée)] ; '
               'fx.point(), fx.hide(élément) (effects.py en exemple)'),
    'place': ('api.place(name, generator, ambience)', 'generator(spec) -> spec RoomSet (places.py en exemple) ; ou un décor "composed" sans code'),
    'element': ('api.element(name, builder)', 'builder(e, ctx) ajoute blocs, objets, niveaux praticables (ctx.walkable) et repères (compose.py)'),
    'sound': ('api.sfx(name, fn, description, long)', 'fn([durée]) -> tableau float32 mono à 44 100 Hz, synthétisé (aucun échantillon)'),
}
CORE = {'camera_move': 'acting/cinema.py (cœur)', 'camera': 'acting/cinema.py (cœur)', 'weather': 'engines/pixel3d/world.py weather() (cœur)',
        'sky': 'engines/pixel3d/world.py PALETTES (cœur)', 'music': 'audio/music.py (cœur)', 'ground': 'engines/pixel3d/world.py ground() (cœur)'}

def normalize(s):
    s = unicodedata.normalize('NFD', str(s).lower().replace('’', "'"))
    return re.sub(r'\s+', ' ', ''.join(c for c in s if unicodedata.category(c) != 'Mn'))

def _entries(caps):
    out = [(terms, kind, name, info) for (terms, kind, name, info) in lexicon.LEX]
    for c in caps.values():                                  # extensions bring their own words
        if c.get('terms'): out.append((tuple(c['terms']), c['kind'], c['name'], {}))
    return out

def detect(text, caps):
    t = normalize(text); found = []
    for terms, kind, name, info in _entries(caps):
        for term in terms:                                   # "term*": a stem (s'effondr* -> s'effondre, s'effondrer...)
            pat = re.escape(normalize(term[:-1])) + r"[a-z]*" if term.endswith('*') else re.escape(normalize(term))
            for m in re.finditer(r"(?<![a-z])" + pat + r"(?![a-z])", t):
                found.append((m.start(), m.end(), term, kind, name, info))
    found.sort(key=lambda f: -(f[1] - f[0])); taken = []; needs = {}
    for (a, b, term, kind, name, info) in found:
        if any(a < y and b > x for x, y in taken): continue
        taken.append((a, b)); key = f'{kind}:{name}'
        if key not in needs: needs[key] = dict(kind=kind, name=name, terms=[term], info=info, at=a)
        elif term not in needs[key]['terms']: needs[key]['terms'].append(term)
    return sorted(needs.values(), key=lambda n: n['at'])

def resolve(need, caps, engine='pixel3d'):
    kind, name = need['kind'], need['name']; info = need.get('info') or {}
    c = caps.get(f'{kind}:{name}')
    if c and engine in c['engines']:
        st = c['engines'][engine]; note = c.get('note', '') if st == 'partial' else ''
        return dict(status=st, source=c['source'], note=note, how=info.get('how', ''))
    if c:                                                   # exists, but in the other engine only
        return dict(status='partial' if info.get('partial') else 'missing', source=c['source'],
                    note=f"existe dans {', '.join(c['engines'])} seulement" + (f" ; {info['partial']}" if info.get('partial') else ''), how='')
    if info.get('partial'): return dict(status='partial', source='', note=info['partial'], how='')
    return dict(status='missing', source='', note=info.get('note', ''), how='')

def request(need, engine, text=''):
    kind, name = need['kind'], need['name']; hook = HOOKS.get(kind)
    return dict(id=f'{kind}_{name}', kind=kind, name=name, engines=[engine], asked_by=need.get('terms', []), context=text[:400],
                approximation=need.get('note', ''),
                where=(f'extension library/extensions/{name}/ : ' + hook[0]) if hook else CORE.get(kind, 'cœur du moteur'),
                contract=hook[1] if hook else 'modification du cœur : garder les anciens épisodes identiques (tools/regress.py, tools/regress_v2.py)',
                acceptance=[f'une scène de test montre « {name} » dans un vrai rendu, dans les deux formats',
                            'rendu déterministe (deux rendus identiques)', 'anciens épisodes inchangés (garde de non-régression)',
                            'python -m hstudio extension test <id>, puis promote'],
                status='demandée')

def plan(text='', requires=None, engine='pixel3d', caps=None):
    caps = caps or registry.build()
    needs = detect(text, caps) if text else []
    for r in requires or []:                                 # a director's explicit list ("kind:name" or {"kind", "name", "why"})
        if isinstance(r, str) and ':' in r: k, n = r.split(':', 1); r = {'kind': k.strip(), 'name': n.strip()}
        if isinstance(r, dict) and r.get('kind') and r.get('name') and not any(x['kind'] == r['kind'] and x['name'] == r['name'] for x in needs):
            needs.append(dict(kind=r['kind'], name=r['name'], terms=[r.get('why', 'requires')], info={}))
    out = []
    for n in needs:
        res = resolve(n, caps, engine); n2 = {k: v for k, v in n.items() if k not in ('info', 'at')}; n2.update(res); out.append(n2)
    counts = {k: sum(1 for n in out if n['status'] == k) for k in LABELS}
    reqs = [dict(request(n, engine, text), need='manquant' if n['status'] == 'missing' else 'partiel (à rendre natif)') for n in out if n['status'] in ('missing', 'partial')]
    return dict(engine=engine, needs=out, counts=counts, requests=reqs)

def format_fr(rep):
    mark = {'native': '[OK]  ', 'composed': '[OK]  ', 'partial': '[~]   ', 'missing': '[MANQUE]'}
    lines = [f"Moteur {rep['engine']} : {len(rep['needs'])} besoins, " + ', '.join(f"{v} {LABELS[k]}" for k, v in rep['counts'].items() if v)]
    for n in rep['needs']:
        extra = n.get('note') or n.get('how') or ''
        lines.append(f"  {mark[n['status']]} {n['kind']}:{n['name']}  ({', '.join(n['terms'])})  {LABELS[n['status']]}" + (f" — {extra}" if extra else ''))
    if rep['requests']: lines.append(f"{len(rep['requests'])} demande(s) d'extension : " + ', '.join(r['id'] + ('' if r['need'] == 'manquant' else ' (amélioration)') for r in rep['requests']))
    return '\n'.join(lines)

def write_requests(rep, folder=REQ_DIR):
    os.makedirs(folder, exist_ok=True); out = []
    for r in rep['requests']:
        p = os.path.join(folder, r['id'] + '.json')
        if os.path.exists(p):                                # keep the history of who asked
            old = json.load(open(p, encoding='utf-8')); r['asked_by'] = sorted(set(old.get('asked_by', []) + r['asked_by']))
        json.dump(r, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1); out.append(p)
    return out
