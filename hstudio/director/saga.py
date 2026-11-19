"""Series memory (V3): which episode follows which, who voted what, and what the next episode inherits.

The library already remembers a series (`acting/cast.py`): `library/series/<id>.json` holds one FLAT state,
`{acteur: {"hold": ..., "look": {...}}}`, written by `cast.remember()` after a render and read by
`acting/timeline.py`. That works for ONE straight line of episodes. An interactive series is a TREE: the audience
votes A, B or C and the story forks. Two arcs written into one flat state overwrite each other, and re-rendering an
episode erases its neighbour.

This module adds the tree WITHOUT touching `cast.py` and WITHOUT replacing `cast.remember()`:

    library/sagas/<serie>.json        the arc: nodes indexed by their branch path ("", "A", "A/B", "A/B/C")
                                      each node = one episode: its choices, THE VOTE, what it leaves behind
    Arc.state_at(path)                what a branch inherits: only its own ancestors, never a sibling
    to_series_state(state)            the flat shape the engines already read -> episode["series_state"]

Three rules it refuses to break:
  1. A vote is never invented. `next_path()` on a node whose vote is undefined raises `VoteUndefined` and
     `proposal()` hands back the options that were actually written, for a human (or the audience) to pick.
  2. A branch inherits from its ancestors only. `state_at("A/B")` never sees anything written on "B".
  3. Regenerating a branch is idempotent: `put()` replaces that node alone, keeps its recorded vote when the vote
     is still one of its choices, and leaves its children and its siblings untouched.

The end of a story is a property of a node (`ending`, a reason in French), not a number of episodes to reach:
nothing here counts episodes or pushes towards a target.
"""
import os, json, copy, datetime
from dataclasses import dataclass, field, asdict
from .. import paths

VERSION = 1
SAGA_DIR = os.path.join(paths.ROOT, 'library', 'sagas')
LETTERS = ('A', 'B', 'C')


class SagaError(RuntimeError): pass
class UnknownBranch(SagaError): pass


class VoteUndefined(SagaError):
    """the next episode cannot be written: nobody has said which branch won"""
    def __init__(self, path, options):
        self.path = path; self.options = options
        opts = ', '.join('{} = {}'.format(o.get('letter'), o.get('label') or o.get('text', '')) for o in options)
        super().__init__('vote non defini pour la branche "{}" : {}'.format(path or 'pilote', opts))


class StoryEnded(SagaError):
    def __init__(self, path, reason):
        self.path = path; self.reason = reason
        super().__init__('la branche "{}" est terminee : {}'.format(path or 'pilote', reason))


def canon(path):
    """'', 'A', 'A/B'... canonical branch path. Accepts a list of letters or a string in any case."""
    if path is None: return ''
    parts = list(path) if isinstance(path, (list, tuple)) else str(path).replace('\\', '/').split('/')
    out = []
    for p in parts:
        p = str(p).strip().upper()
        if not p: continue
        if p not in LETTERS: raise UnknownBranch('lettre de branche invalide : ' + p)
        out.append(p)
    return '/'.join(out)


def parent_of(path):
    p = canon(path)
    return p.rsplit('/', 1)[0] if '/' in p else ('' if p else None)


def ancestors(path):
    """['', 'A', 'A/B'] for 'A/B' : the branch read from the root, in order"""
    p = canon(path); out = ['']; acc = []
    for letter in [x for x in p.split('/') if x]:
        acc.append(letter); out.append('/'.join(acc))
    return out


# ---------------------------------------------------------------- the inherited state


@dataclass
class State:
    """what one episode leaves to the next ON ITS OWN BRANCH. Everything here is additive and merge-able."""
    characters: dict = field(default_factory=dict)   # {id: {"hold": "cle", "look": {...}, "knows": [...], "gone": bool}}
    items: dict = field(default_factory=dict)        # {"cle": "lea"} : who (or what place) holds an object
    places: dict = field(default_factory=dict)       # {"basement": {"visited": 2, "changed": {"porte": "ouverte"}}}
    events: list = field(default_factory=list)       # what happened and must stay true ("la cave est ouverte")
    constraints: list = field(default_factory=list)  # what the narration may no longer do ("Tom ne fait plus confiance")
    missing: list = field(default_factory=list)      # capabilities the V3 planner called missing on this branch

    to_dict = asdict

    @staticmethod
    def from_dict(d):
        d = d or {}
        return State(characters=copy.deepcopy(d.get('characters') or {}), items=dict(d.get('items') or {}),
                     places=copy.deepcopy(d.get('places') or {}), events=list(d.get('events') or []),
                     constraints=list(d.get('constraints') or []), missing=list(d.get('missing') or []))

    def evolve(self, delta):
        """a NEW state = this one plus what the episode changed (never mutates self, never mutates delta)"""
        d = delta.to_dict() if isinstance(delta, State) else (delta or {})
        out = State.from_dict(self.to_dict())
        for cid, ch in (d.get('characters') or {}).items():
            cur = out.characters.setdefault(cid, {})
            for k, v in (ch or {}).items():
                if k == 'look': cur.setdefault('look', {}).update(v or {})
                elif k == 'knows': cur['knows'] = list(dict.fromkeys(list(cur.get('knows') or []) + list(v or [])))
                else: cur[k] = v
        out.items.update(d.get('items') or {})
        for name, pl in (d.get('places') or {}).items():
            cur = out.places.setdefault(name, {})
            cur['visited'] = int(cur.get('visited', 0)) + int((pl or {}).get('visited', 0))
            if (pl or {}).get('changed'): cur.setdefault('changed', {}).update(pl['changed'])
        for key in ('events', 'constraints', 'missing'):
            merged = list(getattr(out, key)) + list(d.get(key) or [])
            setattr(out, key, list(dict.fromkeys(merged)))
        for item, owner in (d.get('items') or {}).items():    # an object given to someone is what they now hold
            if owner in out.characters: out.characters[owner]['hold'] = item
        return out

    def holders(self):
        return {cid: ch.get('hold') for cid, ch in self.characters.items() if ch.get('hold')}

    def summary_fr(self):
        """one readable line, for a log or for the narration brief"""
        bits = ['{} a {}'.format(cid, obj) for cid, obj in self.holders().items()]
        if self.events: bits.append('; '.join(self.events[-3:]))
        if self.constraints: bits.append('contraintes : ' + '; '.join(self.constraints[-2:]))
        return ' | '.join(bits) or 'rien de retenu'


def to_series_state(state, cast_refs=None):
    """the FLAT shape the engines already understand (acting/timeline.py, acting/cast.py):
    {acteur: {"hold": ..., "look": {...}}} -> goes into episode["series_state"]. No new contract for the engines."""
    st = state if isinstance(state, State) else State.from_dict(state)
    out = {}
    for cid, ch in st.characters.items():
        e = {}
        if ch.get('hold'): e['hold'] = ch['hold']
        if ch.get('look'): e['look'] = copy.deepcopy(ch['look'])
        if e: out[(cast_refs or {}).get(cid, cid)] = e
    return out


# ---------------------------------------------------------------- nodes and arc


@dataclass
class Node:
    path: str = ''                     # '' = the pilot
    title: str = ''
    summary: str = ''
    generator: str = ''                # 'mock' or the provider that wrote it; never claimed to be more
    project: str = ''                  # slug of the rendered project, when there is one
    choices: list = field(default_factory=list)      # [{'letter','label','text','reason','consequence'}]
    vote: str = ''                     # '' = NOT VOTED YET. Never guessed.
    ending: str = ''                   # '' = the story goes on; otherwise the reason it ends, in French
    state_after: dict = field(default_factory=dict)  # State.to_dict() AFTER this episode, on this branch only
    brief: dict = field(default_factory=dict)
    created: str = ''

    to_dict = asdict

    @staticmethod
    def from_dict(d):
        d = dict(d or {})
        return Node(**{k: v for k, v in d.items() if k in Node.__dataclass_fields__})

    def letters(self):
        return [c.get('letter') for c in self.choices if c.get('letter') in LETTERS]

    def state(self):
        return State.from_dict(self.state_after)

    def problems(self):
        P = []
        try: canon(self.path)
        except UnknownBranch as e: P.append(str(e))
        if self.vote and self.vote not in self.letters():
            P.append('vote "{}" absent des choix {}'.format(self.vote, self.letters()))
        if self.ending and self.choices: P.append('un episode de fin ne doit pas proposer de choix')
        if not self.ending and len(self.choices) not in (2, 3):
            P.append('{} choix : il en faut 2 ou 3 (ou marquer la fin)'.format(len(self.choices)))
        seen = set()
        for c in self.choices:
            L = c.get('letter')
            if L not in LETTERS: P.append('lettre de choix invalide : {}'.format(L))
            if L in seen: P.append('lettre {} en double'.format(L))
            seen.add(L)
            if not (c.get('reason') or '').strip(): P.append('choix {} sans raison'.format(L))
        return P


@dataclass
class Arc:
    series: str = ''
    title: str = ''
    characters: list = field(default_factory=list)
    nodes: dict = field(default_factory=dict)        # {path: Node}
    version: int = VERSION

    # ---- reading

    def node(self, path):
        return self.nodes.get(canon(path))

    def must(self, path):
        n = self.node(path)
        if n is None: raise UnknownBranch('branche inconnue : "{}"'.format(canon(path)))
        return n

    def branch(self, path):
        """the nodes from the pilot down to `path`, in order. Only ancestors: never a sibling."""
        return [self.nodes[p] for p in ancestors(path) if p in self.nodes]

    def children(self, path):
        p = canon(path)
        return {n.path.rsplit('/', 1)[-1]: n for n in self.nodes.values() if n.path and parent_of(n.path) == p}

    def state_at(self, path):
        """what the episode at `path` INHERITS: the state left by its parent, nothing else."""
        par = parent_of(path)
        if par is None: return State()
        n = self.node(par)
        return n.state() if n else State()

    def is_canonical(self, path):
        """True when every step of this branch is the letter the audience actually voted. An alternate arc kept
        beside it is legitimate (it is what stops one playthrough from erasing another) but it is not canonical."""
        p = canon(path)
        for a in ancestors(p)[:-1] if p else []:
            par = self.nodes.get(a)
            nxt = canon(p).split('/')[len(ancestors(a)) - 1]
            if par is None or par.vote != nxt: return False
        return True

    def is_ended(self, path):
        n = self.node(path)
        return bool(n and n.ending)

    def endings(self):
        return sorted([n for n in self.nodes.values() if n.ending], key=lambda n: n.path)

    def open_branches(self):
        """branches that could continue: a node, not an ending, whose vote is recorded but has no child yet"""
        out = [n for n in self.nodes.values()
               if not n.ending and n.vote and canon(n.path + '/' + n.vote) not in self.nodes]
        return sorted(out, key=lambda n: n.path)

    def waiting_for_vote(self):
        return sorted([n for n in self.nodes.values() if not n.ending and not n.vote], key=lambda n: n.path)

    def proposal(self, path):
        """the options actually written on this node. This module never adds, ranks or picks one."""
        n = self.must(path)
        if n.ending: raise StoryEnded(n.path, n.ending)
        return copy.deepcopy(n.choices)

    # ---- writing

    def put(self, node):
        """idempotent: replaces THAT branch only. Keeps a vote already recorded when it is still offered.
        Never touches the siblings, never deletes the children."""
        node = node if isinstance(node, Node) else Node.from_dict(node)
        node.path = canon(node.path)
        old = self.nodes.get(node.path)
        if old is not None and not node.vote and old.vote in node.letters(): node.vote = old.vote
        if not node.created: node.created = (old.created if old else datetime.date.today().isoformat())
        P = node.problems()
        if P: raise SagaError('noeud "{}" invalide : {}'.format(node.path or 'pilote', ' ; '.join(P)))
        self.nodes[node.path] = node
        return node

    def record_vote(self, path, letter):
        """the audience has decided. Refuses a letter that was not offered; never invents one."""
        n = self.must(path)
        if n.ending: raise StoryEnded(n.path, n.ending)
        L = str(letter or '').strip().upper()
        if L not in n.letters():
            raise SagaError('le choix "{}" n\'existe pas sur cette branche (offerts : {})'.format(letter, n.letters()))
        n.vote = L
        return n

    def clear_vote(self, path):
        self.must(path).vote = ''

    def next_path(self, path):
        """the branch the next episode must be written on. Raises rather than guessing."""
        n = self.must(path)
        if n.ending: raise StoryEnded(n.path, n.ending)
        if not n.vote: raise VoteUndefined(n.path, n.choices)
        return canon(n.path + '/' + n.vote)

    def mark_ending(self, path, reason):
        """a natural end: a reason, not a quota. The node keeps no open choice."""
        n = self.must(path)
        if not (reason or '').strip(): raise SagaError('une fin doit porter une raison')
        if self.children(n.path):
            raise SagaError('la branche "{}" a deja une suite : on ne peut pas la declarer finie'.format(n.path or 'pilote'))
        n.ending = reason.strip(); n.choices = []; n.vote = ''
        return n

    # ---- serialisation

    def to_dict(self):
        return {'version': VERSION, 'series': self.series, 'title': self.title, 'characters': list(self.characters),
                'nodes': {p: n.to_dict() for p, n in sorted(self.nodes.items())}}

    def to_json(self, indent=1):
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @staticmethod
    def from_dict(d):
        d = migrate(d)
        a = Arc(series=d.get('series', ''), title=d.get('title', ''), characters=list(d.get('characters') or []),
                version=VERSION)
        for p, nd in (d.get('nodes') or {}).items():
            nd = dict(nd); nd['path'] = canon(nd.get('path', p))
            a.nodes[nd['path']] = Node.from_dict(nd)
        return a

    @staticmethod
    def from_json(txt):
        return Arc.from_dict(json.loads(txt))

    def problems(self):
        P = []
        for p, n in sorted(self.nodes.items()):
            P += ['{} : {}'.format(p or 'pilote', x) for x in n.problems()]
            if p and parent_of(p) not in self.nodes:
                P.append('{} : parent "{}" absent'.format(p, parent_of(p)))
            if p:
                par = self.nodes.get(parent_of(p)); letter = p.rsplit('/', 1)[-1]
                if par and letter not in par.letters():
                    P.append('{} : la branche {} n\'est pas offerte par son parent'.format(p, letter))
        return P


# ---------------------------------------------------------------- migrations (old saves stay readable)


def migrate(raw):
    """reads any earlier shape. v0 = no "version" key: either an empty file or the flat library series."""
    d = dict(raw or {})
    v = int(d.get('version', 0))
    if v == 0:
        if 'nodes' not in d and 'state' in d:                 # a legacy library/series/<id>.json handed over as-is
            d = legacy_series_to_arc(d)
        d.setdefault('nodes', {})
        d['version'] = 1
    if int(d.get('version', 1)) > VERSION:
        raise SagaError('sauvegarde ecrite par une version plus recente ({} > {}) : mets a jour Horror Studio'
                        .format(d['version'], VERSION))
    return d


IMPORT_ENDING = "import d'une memoire de serie a plat : la suite n'a pas encore de branche"


def legacy_series_to_arc(sr):
    """a flat `library/series/<id>.json` becomes the PILOT node of an arc, without losing anything.
    The original file is never modified: cast.remember() keeps writing it exactly as before."""
    delta = State(characters={cid: {k: v for k, v in (c or {}).items() if k in ('hold', 'look')}
                              for cid, c in (sr.get('state') or {}).items()})
    st = State().evolve(delta)
    eps = sr.get('episodes') or []
    node = Node(path='', title=(eps[0].get('title') if eps else '') or sr.get('title', ''),
                summary='Reprise de la memoire de serie a plat (avant les branches).',
                generator='import', project=(eps[0].get('project') if eps else ''),
                choices=[], vote='', ending=IMPORT_ENDING, state_after=st.to_dict(),
                created=datetime.date.today().isoformat())
    return {'version': 1, 'series': sr.get('id', ''), 'title': sr.get('title', ''),
            'characters': list(sr.get('characters') or []), 'nodes': {'': node.to_dict()}}


# ---------------------------------------------------------------- the store


def path_of(series_id, root=None):
    return os.path.join(root or SAGA_DIR, '{}.json'.format(series_id))


def load(series_id, root=None):
    """the arc of a series; an empty one if it has never been saved. Imports the flat library state on first read."""
    p = path_of(series_id, root)
    if os.path.exists(p):
        with open(p, encoding='utf-8') as f: return Arc.from_dict(json.load(f))
    from ..acting import cast as CAST
    sr = CAST.series(series_id)
    if sr and (sr.get('state') or sr.get('episodes')):
        return Arc.from_dict(legacy_series_to_arc(sr))
    return Arc(series=series_id, title=(sr or {}).get('title', ''), characters=list((sr or {}).get('characters') or []))


def save(arc, root=None):
    P = arc.problems()
    if P: raise SagaError("arc incoherent, rien n'a ete ecrit : " + ' ; '.join(P[:4]))
    d = (root or SAGA_DIR); os.makedirs(d, exist_ok=True)
    p = path_of(arc.series, d); tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f: f.write(arc.to_json())
    os.replace(tmp, p)                                        # never a half-written save
    return p


# ---------------------------------------------------------------- bridge to the story layer (director/story.py)


def brief_for(arc, path, off_vote=False, **overrides):
    """the Brief of the episode at `path`. The parent's vote becomes `previous_choice`.

    Refuses rather than guesses: VoteUndefined when nobody has voted, StoryEnded when the branch is closed,
    SagaError when the branch asked for is not the one the audience chose."""
    from . import story
    p = canon(path); par = parent_of(p)
    base = {'series': arc.series}
    if par is not None:
        prev = arc.node(par)
        if prev is None: raise UnknownBranch('branche inconnue : "{}"'.format(par))
        if prev.ending: raise StoryEnded(prev.path, prev.ending)
        if not prev.vote: raise VoteUndefined(prev.path, prev.choices)
        letter = p.rsplit('/', 1)[-1]
        if letter != prev.vote and not off_vote:
            raise SagaError('branche {} demandee alors que le public a choisi {} '
                            '(passe off_vote=True pour ecrire un arc alternatif exprès)'.format(letter, prev.vote))
        chosen = next(c for c in prev.choices if c.get('letter') == prev.vote)
        base.update(prev.brief or {})
        base['previous_choice'] = '{} : {}'.format(prev.vote, chosen.get('label') or chosen.get('text', ''))
    base['part_label'] = 'PARTIE {}'.format(len(ancestors(p)))
    base.update(overrides)
    return story.Brief.from_dict(base)


def episode_for(arc, path, outline, n_lines=None, cast_refs=None):
    """(episode valide, avertissements) for `path`, carrying ONLY what its own ancestors left behind."""
    from .validate import validate
    inherited = to_series_state(arc.state_at(path), cast_refs)
    ep = outline.to_episode(n_lines, series=arc.series, series_state=inherited)
    return validate(ep, n_lines if n_lines is not None else len(outline.beats), outline.brief.resolve_engine())


def node_from_outline(arc, path, outline, delta=None, title='', project='', ending=''):
    """the Node for `path`: the inherited state plus what this episode changed. Does not write it into the arc."""
    st = arc.state_at(path).evolve(delta or {})
    return Node(path=canon(path), title=title or (outline.brief.part_label or ''), summary=outline.summary,
                generator=outline.generator, project=project,
                choices=[] if ending else [c.to_dict() for c in outline.choices],
                ending=ending, state_after=st.to_dict(), brief=outline.brief.to_dict())


def plan_missing(text, engine='pixel3d', caps=None):
    """capabilities the V3 planner calls missing in this text -> State.missing (nothing is silently simplified)"""
    from ..capabilities import planner
    rep = planner.plan(text, engine=engine, caps=caps)
    return sorted({'{}:{}'.format(n['kind'], n['name']) for n in rep.get('needs') or [] if n.get('status') == 'missing'})
