"""Genre intent: what a horror script MEANS, and the data the painter and the integrator need to show it. Owner: the genre-horror lane.

Three problems, three parts, no change to the shared director / blocking / camplan / faceact / renderer (the integrator wires the hooks listed at the end):

1. INTERPRETATION  `interpret(text, genre)`  French narration -> entities and events.
   « un homme noir sous une capuche, pas de visage, le néant » is a SUPERNATURAL presence, not a man in a coat: it gets a monster spec (abnormal
   silhouette, long dark fingers, a void under the hood, unnatural stillness) and a flag `human_default_forbidden`. A plain « homme en manteau » stays human.
   « homme noir » alone is ambiguous in French (it can describe a Black person): it is NEVER turned into a monster on that phrase alone, it needs another cue
   (hood, no face, void, shadow...), otherwise the entity stays human and a warning asks the author. Skin colour is never used to cast a creature.

2. DISAPPEARANCE  « il disparaît » does not mean « he walks to a door and leaves ». Five declared categories (CATEGORIES), each with a condition the
   spatial verifier can check, and ONE rule for ordinary actors: they never vanish or relocate (only `cut` / `offscreen` masks over a valid trajectory).
        sudden     in plain view, with a visible cause (a light dips within 0.6 s)                        supernatural only
        shadow     melts into darkness: the lights that reach his place are low at that instant             supernatural only
        blackout   every named light is cut (it dropped by >= .4 within 2.5 s before)                    supernatural only
        cut        the film cuts: the vanish and the reappearance are on shot boundaries                  any, no relocation for ordinary actors
        offscreen  nobody can see it: not in any camera frame while it changes                            any, no relocation for ordinary actors
   The story declares it with a beat `{'who','t','do':'vanish','how',...}` in `blocking.plan.beats`. `split_plan` cuts the actor's trajectory into LIVES
   (`ghost`, `ghost#1`): each life is planned and audited by `blocking.py` unchanged (walls, speed, solids), so nothing teleports by accident, and the
   one declared relocation is checked here (free spot, reachable through open doors unless `through_walls`). `VanishView` is the compiled plan seen
   as ONE actor per id with a visibility flag, the interface `director.build` already reads.

3. MOOD  `MOOD_PRESETS`, `mood_for(genre)`: data on keys the painter already honours (stage `mood`, stage `look`, world `env`). A preset never imposes red neon,
   and keeps A's own materials and bloom: it only chooses motivated light (cold moon key, warm practical lamps, no unmotivated rim) and a restrained grade.

Everything is deterministic: no clock, no random.
"""
import math
import re
import unicodedata

from . import blocking as BLK

PX = 1. / 16.
_PREFLIGHT0 = BLK.preflight            # the originals, kept here so a caller may replace the module's own names by ours without recursion
_COMPILE_EPISODE0 = BLK.compile_episode


class IntentError(ValueError):
    """the declaration cannot be honoured; the message is French and names what to change"""


# ------------------------------------------------------------------------------------------------------------- 1. interpretation
def fold(s):
    """lower case, no accents, curly quotes straight: the form every pattern is written in"""
    s = unicodedata.normalize('NFD', (s or '').lower().replace('’', "'").replace('œ', 'oe'))
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')


# a cue is (name, regex on folded text). STRONG: enough alone in a horror text. WEAK: counts only together with another cue.
STRONG = [
    ('sans_visage', r"\b(sans visage|pas de visage|ni visage|aucun visage|plus de visage|visage (vide|noir|efface)|n'a pas (de )?(visage|yeux))"),
    ('neant', r"\b(neant|le vide|vide absolu|gouffre|abime)\b"),
    ('rien_sous_capuche', r"(rien|vide|noir|neant)\b[^.!?]{0,40}\b(sous|dans)\b[^.!?]{0,20}\bcapuche|capuche[^.!?]{0,40}\b(rien|neant|vide)\b"),
    ('creature', r"\b(creature|monstre|entite|apparition|spectre|fantome|demon|abomination|chose)\b"),
    ('ombre_vivante', r"\b(ombre (vivante|qui bouge|qui marche)|silhouette (sans|sans-)|forme (sans|inhumaine))"),
    ('inhumain', r"\b(inhumain|pas humain|plus humain|trop (grand|long|maigre)|doigts (trop )?longs?)\b"),
]
APPEARANCE = [      # how the figure looks: weak alone, they need a second cue
    ('capuche', r"\bcapuche\b"),
    ('silhouette', r"\bsilhouette\b"),
    ('ombre', r"\bombre\b"),
    ('tout_de_noir', r"\b(tout de noir|vetu de noir|en noir|figure noire|forme noire)\b"),
    ('main_noire', r"\b(main noire|mains noires|doigts)\b"),
]
CONTEXT = [         # where / how it stands: they only reinforce an appearance cue, never make a creature on their own
    ('immobile', r"\b(immobile|sans bouger|ne bouge pas|attendait|attend)\b"),
    ('vitre_nuit', r"\b(derriere la vitre|dans le noir|dans la nuit)\b"),
]
WEAK = APPEARANCE + CONTEXT
# « homme noir » / « homme en noir »: an ambiguous description. Never a cue by itself.
AMBIGUOUS = re.compile(r"\b(homme|femme|garcon|type|mec|personne|silhouette)\s+(noir|noire)\b")
ENTITY_WORDS = re.compile(r"\b(l'homme|un homme|cet homme|l'inconnu|un inconnu|la silhouette|une silhouette|la creature|une creature|le monstre|la femme|une femme|l'ombre|la chose|la forme|l'entite|le spectre|le fantome)\b")
PRONOUN = re.compile(r"\b(il|elle)\b")

VANISH_RE = re.compile(r"\b(disparai(t|ssent|ssait|tre|ssant)|disparu|s'evanou(it|issent)|s'efface|s'effacent|se dissout|se dissolvent|s'est evapore|fond dans (la nuit|l'ombre|le noir)|est avale par|n'est plus la|plus personne)\b")
HOW_HINTS = [   # (category, regex on the sentence that carries the vanish and its neighbour) ; first match wins
    ('blackout', r"(lumieres?|neons?|lampadaires?|ampoules?|plafonnier|courant)[^.!?]{0,40}(s'eteign|eteint|coupe|noir complet)|panne|coupure de courant|plus de lumiere"),
    ('shadow', r"dans (la nuit|l'ombre|l'obscurite|le noir|les tenebres)|avale par (la nuit|l'ombre|le noir)|fond dans|se fond"),
    ('offscreen', r"hors champ|hors-champ|sort du champ|quitte le cadre|derriere (toi|le mur|la porte)|plus personne"),
    ('sudden', r"soudain|d'un coup|en un clin d'oeil|clignote|une seconde plus tard|sans un bruit|en un instant"),
]


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?…])\s+|\n+", text) if s.strip()]


def interpret(text, genre='horror'):
    """French narration -> {genre, entities, events, warnings, mood}.

    entity: {label, nature: 'supernatural'|'human'|'ambiguous', cues, strong, weak, human_default_forbidden, monster (spec or None), reason}
    event:  {kind: 'vanish', sentence, subject, how_candidates, how, needs_declaration, requires_walk: False, allowed, why}
    """
    f = fold(text); genre = fold(genre or '')
    horror = genre in ('horror', 'horreur', 'thriller', 'epouvante')
    strong = [n for n, rx in STRONG if re.search(rx, f)]
    app = [n for n, rx in APPEARANCE if re.search(rx, f)]; ctx = [n for n, rx in CONTEXT if re.search(rx, f)]; weak = app + ctx
    amb = AMBIGUOUS.search(f)
    warnings = []; entities = []
    has_subject = bool(ENTITY_WORDS.search(f) or amb or 'capuche' in f)
    if has_subject or strong:
        # supernatural: a strong cue (in a horror text, or two of them anywhere), or in a horror text an appearance cue backed by a second cue.
        # « homme noir » is never a cue by itself: it only counts as a second cue once an appearance cue is there.
        n_app = len(app) + (1 if amb and app else 0)
        supernatural = bool(strong and (horror or len(strong) >= 2)) or bool(horror and has_subject and app and n_app + len(ctx) >= 2)
        nature = 'supernatural' if supernatural else 'human'
        if amb and not strong:
            if nature == 'human':
                nature = 'ambiguous'
                warnings.append("« %s » peut décrire une personne noire : sans autre indice (capuche, pas de visage, néant, ombre) il n'est pas traité comme un monstre. "
                                "Écrire par exemple « silhouette noire sans visage » pour demander une présence surnaturelle." % amb.group(0))
            else:
                warnings.append("« %s » est lu comme une silhouette sombre à cause de %s, pas à cause de la couleur de peau d'une personne : si le personnage est une personne noire, "
                                "retirer ces indices ou le déclarer `human` dans le plan." % (amb.group(0), ', '.join(app + ctx)))
        m_ = ENTITY_WORDS.search(f) or amb or re.search(r'capuche', f); label = m_.group(0) if m_ else 'une présence'
        cues = strong + weak + (['homme_noir_ambigu'] if amb else [])
        ent = dict(label=label, nature=nature, cues=cues, strong=strong, weak=weak, score=len(strong) * 2 + len(weak),
                   human_default_forbidden=nature == 'supernatural', monster=None, reason=_why(nature, strong, weak, horror))
        if nature == 'supernatural': ent['monster'] = monster_spec('faceless_void')
        entities.append(ent)
    events = []
    for i, s in enumerate(_sentences(f)):
        if not VANISH_RE.search(s): continue
        around = ' '.join(_sentences(f)[max(0, i - 1): i + 2])
        cands = [h for h, rx in HOW_HINTS if re.search(rx, around)]
        subj = entities[0] if entities else None
        ok, why = True, 'catégorie à déclarer dans le plan (beat `vanish`)'
        if subj is None or subj['nature'] != 'supernatural':
            ok = False; why = "sujet non surnaturel : un acteur ordinaire ne disparaît pas, il sort par une porte (marche vérifiée), par le hors-champ ou par une coupe"
        events.append(dict(kind='vanish', sentence=s, subject=subj['label'] if subj else None, how_candidates=cands,
                           how=cands[0] if cands else None, needs_declaration=True, requires_walk=False, allowed=ok, why=why))
    return dict(genre=genre or None, entities=entities, events=events, warnings=warnings, mood=mood_for(genre or 'neutral'))


def _why(nature, strong, weak, horror):
    if nature == 'supernatural': return 'indices forts %s%s : présence surnaturelle, silhouette anormale, pas un humain en manteau' % (strong or '-', (' + faibles %s' % weak) if weak else '')
    if nature == 'ambiguous': return "description ambiguë sans indice surnaturel : reste humain, à confirmer par l'auteur"
    return 'aucun indice surnaturel suffisant (%s, %s) : reste humain' % (strong or 'forts: aucun', weak or 'faibles: aucun')


# ------------------------------------------------------------------------------------------------------------- monster data
# Parameters read by voxelgpu_js/engine/horror_monster.js through the cast's `look.monster` (the one channel the shared renderer passes to buildFaceless).
# Lengths are multipliers of A's character at scale 1; angles in radians; every motion is a function of the film time (no random).
ARCHETYPES = {
    # « homme noir / capuche / sans visage / néant »: tall, narrow, stooped; skin and shoes pure dark; hood hollow; hands too big with fingers 1.9x long and thin
    'faceless_void': dict(archetype='faceless_void', stretch=[0.88, 1.16, 0.88], head=1.08, hunch=0.16, head_tilt=0.2, shoulder_drop=0.1, hand_scale=1.22,
                          finger_len=1.9, finger_thin=0.7, finger_twitch=0.5, stillness=0.85, void_depth=1.0, skin=0x08080b, hood=0x14161c, boots=0x0a0a0c),
    # taller still, almost no hood, arms hang too low: for a second beat, a reveal
    'long_walker': dict(archetype='long_walker', stretch=[0.78, 1.34, 0.78], head=0.96, hunch=0.26, head_tilt=0.34, shoulder_drop=0.2, hand_scale=1.35,
                        finger_len=2.2, finger_thin=0.62, finger_twitch=0.7, stillness=0.9, void_depth=0.8, skin=0x0c0b0d, hood=0x1c1a20, boots=0x08080a),
}
# poses of the creature, each a delta on the base stance (joint -> radians), applied by horror_monster.js `MONSTER_POSES` (names must match)
MONSTER_POSES = ('still', 'head_tilt', 'loom', 'reach', 'claw', 'stoop', 'twitch')


def monster_spec(name='faceless_void', **over):
    if name not in ARCHETYPES: raise IntentError("archétype inconnu : %r (connus : %s)" % (name, ', '.join(ARCHETYPES)))
    spec = dict(ARCHETYPES[name]); spec.update(over); return spec


def _hexs(v): return '#%06x' % v if isinstance(v, int) else v


def cast_entry(monster='faceless_void', *, hood=None, top=None, pants=None, vanishes=(), **over):
    """the `casts[id]` entry of a creature for the contract. `look.monster` is the channel; kind 'faceless' keeps the shared branch of film_unified.js."""
    m = monster_spec(monster, **over) if isinstance(monster, str) else dict(monster)
    m = {k: (_hexs(v) if k in ('skin', 'hood', 'boots') else v) for k, v in m.items()}
    m['vanish'] = [[round(w[0], 4), round(w[1], 4), w[2], w[3]] for w in windows(vanishes)] if vanishes else []
    m['supernatural'] = True
    hc = m.get('hood', 0x14161c)
    return dict(preset='npc', kind='faceless', hood=hc, look=dict(top=top or dict(type='coat', color=hc), pants=pants or dict(color='#0c0c10'), monster=m))


# ------------------------------------------------------------------------------------------------------------- 2. disappearance
CATEGORIES = ('sudden', 'shadow', 'blackout', 'cut', 'offscreen')
ORDINARY_OK = ('cut', 'offscreen')
SUPERNATURAL_ONLY = ('sudden', 'shadow', 'blackout')
DARK, DROP, DIP_WINDOW, FLICKER = .25, .4, 2.5, .6
MIN_GAP = 0.0


def is_supernatural(spec):
    """an actor spec of the plan: kind 'faceless' is a creature unless the author says `human_hooded: True`; `supernatural: True` makes any kind one"""
    if spec.get('supernatural') is True: return True
    return spec.get('kind') == 'faceless' and not spec.get('human_hooded')


def _tv(tab, t, d=0.):
    if tab is None: return d
    if isinstance(tab, (int, float)): return float(tab)
    if t <= tab[0][0]: return tab[0][1]
    for i in range(len(tab) - 1):
        if t < tab[i + 1][0]:
            k = (t - tab[i][0]) / max(1e-6, tab[i + 1][0] - tab[i][0]); return tab[i][1] + (tab[i + 1][1] - tab[i][1]) * k
    return tab[-1][1]


def light_level(tables, t):
    """brightest of the named light tables at time t (a place is dark only when every light that reaches it is low)"""
    return max((_tv(tb, t, 1.) for tb in tables), default=1.)


def _dipped(tables, t, win=FLICKER):
    """a light fell below DARK*2 and lost >= DROP within `win` seconds of t (a flicker, a bulb that goes)"""
    for k in range(int(-win * 20), int(win * 20) + 1):
        tt = t + k / 20.
        if light_level(tables, tt) <= DARK * 2 and light_level(tables, tt - .5) - light_level(tables, tt) >= DROP: return True
    return False


def _norm(b, plan_actors):
    v = dict(b); v['t'] = float(b['t']); v['how'] = b.get('how')
    v['until'] = None if b.get('until') is None else float(b['until'])
    v['appear'] = b.get('appear') or v['how']
    v['lights'] = list(b.get('lights') or []); v['through_walls'] = bool(b.get('through_walls'))
    v['super'] = is_supernatural(plan_actors[b['who']])
    return v


def split_plan(plan, geo=None):
    """plan with `vanish` beats -> (plain plan for blocking.compile_plan, [normalised vanishes], lives).

    Every actor that vanishes is cut into lives `id`, `id#1`... Beats after a reappearance are given to the new life; names of actors used as targets (`at`,
    `face`) are resolved to the life that exists at that time. A beat of the vanishing actor inside its invisible window is refused (an invisible
    actor does nothing). Raises IntentError in French; never repairs silently."""
    actors = plan['actors']; beats = [dict(b) for b in plan['beats']]
    raw = [b for b in beats if b.get('do') == 'vanish']
    rest = [b for b in beats if b.get('do') != 'vanish']
    vs = []
    for b in raw:
        if b.get('who') not in actors: raise IntentError("vanish à t=%s : acteur inconnu %r" % (b.get('t'), b.get('who')))
        if b.get('how') not in CATEGORIES:
            raise IntentError("vanish de %s à t=%s : catégorie %r inconnue ou absente (choisir parmi %s). Une disparition doit être déclarée, jamais devinée." % (b['who'], b.get('t'), b.get('how'), ', '.join(CATEGORIES)))
        v = _norm(b, actors); a = actors[v['who']]
        if not v['super']:
            if v['how'] not in ORDINARY_OK or v.get('at') is not None or v['through_walls']:
                raise IntentError("%s est un acteur ordinaire : il ne disparaît pas et ne change pas de place sans marcher (catégories permises : %s, sans `at`). "
                                  "Pour qu'il quitte le lieu, planifier un déplacement vers une porte." % (v['who'], ', '.join(ORDINARY_OK)))
        if v['until'] is not None and v['until'] < v['t']: raise IntentError("vanish de %s : `until` (%.2f) avant la disparition (%.2f)" % (v['who'], v['until'], v['t']))
        if v['until'] is None and v.get('at') is not None: raise IntentError("vanish de %s : `at` sans `until` (où et quand réapparaît-il ?)" % v['who'])
        vs.append(v)
    vs.sort(key=lambda v: (v['who'], v['t']))
    lives = {}
    for who in sorted({v['who'] for v in vs}):
        mine = [v for v in vs if v['who'] == who]; out = []; on = -1e9; prev_until = -1e9
        for i, v in enumerate(mine):
            if v['t'] < prev_until - 1e-9: raise IntentError("%s : deux disparitions se chevauchent (t=%.2f)" % (who, v['t']))
            out.append((who if i == 0 else '%s#%d' % (who, i), on, v['t']))
            if v['until'] is None: on = None; break
            on = prev_until = v['until']
        if on is not None: out.append(('%s#%d' % (who, len(out)), on, 1e9))
        lives[who] = out
    actors2 = {k: dict(v) for k, v in actors.items()}
    for who, ls in lives.items():
        mine = [v for v in vs if v['who'] == who]
        for i, (lid, t_on, t_off) in enumerate(ls[1:]):
            v = mine[i]; sp = dict(actors[who]); face = v.get('face')
            sp['start'] = _start_of(v['at'] if v.get('at') is not None else _held_start(rest, who, v['t'], actors[who]), face)
            actors2[lid] = sp
    out_b = []
    for b in rest:
        who = b['who']
        if who in lives:
            t = float(b['t']); life = _life_at(lives[who], t)
            if life is None:
                raise IntentError("%s : beat %r à t=%.2f pendant qu'il est invisible (un acteur invisible n'agit pas ; déplacer le beat ou la disparition)" % (who, b.get('do'), t))
            b = dict(b, who=life)
            if b.get('do') in ('go', 'run') and float(b.get('by', t)) > lives[who][[l[0] for l in lives[who]].index(life)][2] + 1e-9:
                raise IntentError("%s : le déplacement de t=%.2f à %.2fs dépasse sa disparition (t=%.2f)" % (who, t, float(b['by']), lives[who][[l[0] for l in lives[who]].index(life)][2]))
        for key in ('at', 'face', 'look', 'look_at'):
            tgt = b.get(key)
            if isinstance(tgt, str) and tgt in lives:
                lf = _life_at(lives[tgt], float(b['t']))
                b[key] = lf if lf is not None else tgt
        out_b.append(b)
    plan2 = dict(plan, actors=actors2, beats=out_b)
    return plan2, vs, lives


def _life_at(ls, t):
    for lid, a, b in ls:
        if a - 1e-9 <= t < b - 1e-9 or (a == b and abs(t - a) < 1e-9): return lid
    return None


def _start_of(pos, face=None):
    """blocking.compile_plan wants a mark name or {'at': [x, z], 'yaw'}"""
    if isinstance(pos, str): return pos
    if isinstance(pos, dict): return dict(pos, **({'yaw': float(face)} if isinstance(face, (int, float)) else {}))
    return dict(at=[float(pos[0]), float(pos[1])], yaw=float(face) if isinstance(face, (int, float)) else 0.)


def _held_start(beats, who, t, spec):
    """where a life that reappears without `at` starts: where the previous life stood (its last `go` destination before t, else its start)"""
    pos = spec['start']
    for b in sorted([b for b in beats if b['who'] == who and b.get('do') in ('go', 'run') and float(b['t']) < t], key=lambda b: float(b['t'])): pos = b['to']
    return pos


def windows(vs):
    """[(t0, t1, how)] where the creature is not drawn; a reappearance by `shadow` / `sudden` rises from the floor, handled by the painter from the same table"""
    out = []
    for v in vs:
        out.append((v['t'], v['until'] if v.get('until') is not None else 1e9, v['how'], v.get('appear') or v['how']))
    return out


class VanishView:
    """a compiled plan (with lives) seen as one actor per id; `visible` is False while the actor is not there. Same surface as blocking.Compiled for what
    director.py / camplan.py / faceact.py read. `.C` is the real compile (every life), used by `preflight`."""

    def __init__(self, C, vanishes, lives):
        self.C = C; self.vanishes = vanishes; self.lives = lives; self.actors = {a: C.actors[a] for a in C.actors if '#' not in a}
        self.plan, self.geo, self.dur = C.plan, C.geo, C.dur
        self.contacts = [dict(c, who=c['who'].split('#')[0]) for c in C.contacts]
        self.events = [dict(e, who=str(e.get('who', '')).split('#')[0]) for e in C.events]

    def __getattr__(self, k): return getattr(self.C, k)

    def _life(self, aid, t):
        ls = self.lives.get(aid)
        if not ls: return aid, True
        lid = _life_at(ls, t)
        if lid is not None: return lid, True
        past = [l for l in ls if l[2] <= t + 1e-9]
        return (past[-1][0] if past else ls[0][0]), False                  # held where it was last seen

    def _row_of(self, aid, t):
        lid, vis = self._life(aid, t); r = self.C._row(self.C.actors[lid], t); r['visible'] = bool(vis); return r

    def visible(self, aid, t): return self._life(aid, t)[1]
    def vanishes_of(self, aid): return [v for v in self.vanishes if v['who'] == aid]
    def sample(self, t): return {a: self._row_of(a, t) for a in self.actors}
    def xz(self, aid, t): r = self._row_of(aid, t); return r['x'], r['z']
    def _row(self, A, t): return self._row_of(A.id.split('#')[0], t)
    def end_states(self): return {}
    def position(self, tr, t): return (0., 0.)
    def pos(self, aid, t): return self.C.actors[self._life(aid, t)[0]].pos(t)


def compile_episode(ep):
    """drop-in for `blocking.compile_episode(ep)`: (VanishView, geo). Episodes without `vanish` beats compile exactly as before (the View is then transparent)."""
    geo = BLK.geo_of(ep); plan = dict(ep['blocking']['plan']); plan.setdefault('duration', ep.get('duration'))
    plan2, vs, lives = split_plan(plan, geo)
    C = BLK.compile_plan(plan2, geo)
    return VanishView(C, vs, lives), geo


BODY_CODES = ('solide', 'téléportation', 'mur', 'vitesse', 'passage', 'portée', 'orientation', 'cause')


def preflight(ep, view, geo, shots_abs, aspect='9:16', strict=True):
    """drop-in for `blocking.preflight`. Cameras and framing are judged on the MERGED view (one actor per id, where it really is); the BODY checks of an actor
    that vanishes are made on each of its lives (so a normal actor can never teleport and a creature cannot hide a walk through a wall), plus the declared vanishes."""
    v, rep = _PREFLIGHT0(ep, view, geo, shots_abs, aspect, strict)
    if isinstance(view, VanishView) and view.lives:
        v = [x for x in v if not (x.code in BODY_CODES and x.who in view.lives)]
        v += [x for x in BLK.audit(view.C) if (x.who or '').split('#')[0] in view.lives]
        vv = audit_vanishes(view, geo, world_env=ep.get('world_env') or {}, cuts=sorted(set((ep.get('blocking') or {}).get('cuts') or []) | set(_cuts_from_shots(ep))), fps=float(ep.get('fps', 30)))
        v += vv
        rep['violations'] = [x.to_json() for x in v]; rep['vanishes'] = [dict(who=x['who'], t=x['t'], how=x['how'], until=x['until']) for x in view.vanishes]
    return v, rep


def _cuts_from_shots(ep):
    t = 0.; out = [0.]
    for s in ep['shots']: t += float(s['dur']); out.append(round(t, 4))
    return out


def audit_vanishes(view, geo, *, world_env=None, cuts=(), in_view=None, fps=30.):
    """the verifier for the declared vanishes: category, cause, relocation. Returns blocking.Violation list; [] when the story is physically honest.
    `in_view(aid, t) -> bool` is required for `offscreen` (see `in_view_from_contract`); without it an `offscreen` vanish is reported as not verifiable."""
    V = BLK.Violation; out = []; env = world_env or {}; tol = 1.6 / fps; cuts = list(cuts) or [0.]
    near_cut = lambda t: min(abs(t - c) for c in cuts) <= tol
    for v in view.vanishes:
        who, t, how, back = v['who'], v['t'], v['how'], v['until']
        tabs = []
        for k in v['lights']:
            if k not in env: out.append(V('lumière_inconnue', "vanish de %s : la table de lumière %r n'existe pas dans world_env (connues : %s)" % (who, k, ', '.join(sorted(env)) or 'aucune'), t, who))
            else: tabs.append(env[k])
        def need_lights(label):
            if not v['lights']: out.append(V('cause_absente', "%s (%s) de %s à t=%.2f : déclarer `lights` (les tables de world_env qui éclairent sa place)" % (label, how, who, t), t, who)); return False
            return len(tabs) == len(v['lights'])
        def check(how_, tt, role):
            if how_ in SUPERNATURAL_ONLY and not v['super']:
                out.append(V('disparition_interdite', "%s est un acteur ordinaire : « %s » est réservé aux présences surnaturelles" % (who, how_), tt, who)); return
            if how_ == 'cut':
                if not near_cut(tt): out.append(V('coupe_absente', "%s par coupe : aucune coupe à t=%.2f (coupes : %s)" % (role, tt, ', '.join('%.2f' % c for c in cuts[:8])), tt, who))
            elif how_ == 'offscreen':
                if in_view is None: out.append(V('non_vérifiable', "%s hors champ de %s à t=%.2f : fournir `in_view` (caméras du contrat) pour le vérifier" % (role, who, tt), tt, who))
                else:
                    seen = [s for s in (tt - .15, tt - .05, tt, tt + .05, tt + .15) if in_view(who, s)]
                    if seen: out.append(V('visible_à_l_écran', "%s hors champ de %s à t=%.2f : il est dans le cadre à t=%.2f" % (role, who, tt, seen[0]), tt, who))
            elif how_ in ('shadow', 'blackout'):
                if not need_lights(role): return
                lv = light_level(tabs, tt)
                if lv > DARK: out.append(V('pas_dans_le_noir', "%s par %s de %s à t=%.2f : la lumière qui l'éclaire est à %.2f (maximum %.2f)" % (role, how_, who, tt, lv, DARK), tt, who, level=lv))
                if how_ == 'blackout' and role == 'disparition' and light_level(tabs, tt - DIP_WINDOW) - lv < DROP:
                    out.append(V('coupure_absente', "blackout de %s à t=%.2f : la lumière n'a pas été coupée (elle ne baisse que de %.2f dans les %.1f s avant)" % (who, tt, light_level(tabs, tt - DIP_WINDOW) - lv, DIP_WINDOW), tt, who))
            elif how_ == 'sudden':
                if not need_lights(role): return
                if not _dipped(tabs, tt): out.append(V('cause_absente', "%s soudaine de %s à t=%.2f : aucune cause visible (une lumière doit chuter à ±%.1f s)" % (role, who, tt, FLICKER), tt, who))
        check(how, t, 'disparition')
        if back is not None:
            check(v['appear'], back, 'réapparition')
            mine = view.vanishes_of(who); i = mine.index(v); ls = view.lives[who]
            if i + 1 < len(ls) and v.get('at') is not None:
                x0, z0 = view.C.actors[ls[i][0]].pos(t - 1e-6); x1, z1 = view.C.actors[ls[i + 1][0]].pos(back + 1e-6)
                r = view.actors[who].r
                hit = geo.hit_body(x1, z1, r - .03, back)
                if hit: out.append(V('solide', "%s réapparaît dans %r en (%.2f, %.2f)" % (who, hit, x1, z1), back, who))
                zn = geo.zone_at(x1, z1)
                if zn is None and not v['through_walls']: out.append(V('hors_lieu', "%s réapparaît hors de toute zone connue (%.2f, %.2f)" % (who, x1, z1), back, who))
                if not v['through_walls'] and not _reachable(geo, (x0, z0), (x1, z1), r, back):
                    out.append(V('passage', "%s change de place par disparition entre (%.1f, %.1f) et (%.1f, %.1f) sans chemin par des portes ouvertes à t=%.1f : déclarer `through_walls` si la créature traverse" % (who, x0, z0, x1, z1, back), back, who))
    return out


def _reachable(geo, a, b, r, t):
    open_now = tuple(p.id for p in geo.portals.values() if p.open_at(t))
    try:
        seg = geo.grid(r + .04, open_now).path(a, b)
    except Exception:
        return False
    return bool(seg) and all(not geo.seg_free(seg[i], seg[i + 1], r - .02, None, skip_portals=True) for i in range(len(seg) - 1))


def in_view_from_contract(c, margin=.05):
    """a function `in_view(aid, t)` from the cameras of a FINISHED contract: any of feet / chest / head of the actor inside the frame (occlusion is not tested:
    the question is whether the frame could show him)"""
    from .camplan import project
    ix = {n: i for i, n in enumerate(c['actor_cols'])}; ar = {'9:16': 9 / 16, '16:9': 16 / 9}[c['aspect']]; fps = c['fps']

    def f(aid, t):
        for st in c['stages']:
            if not (st['t0'] - 1e-9 <= t < st['t1'] + st.get('tail', 0.) - 1e-9): continue
            n = len(st['camera']); i = min(n - 1, max(0, int(round((t - st['t0']) * fps))))
            rows = st['actors'].get(aid)
            if not rows: continue
            r = rows[min(len(rows) - 1, i)]
            if not r[ix['vis']]: continue
            cam = st['camera'][i]; x, z = r[ix['x']], r[ix['z']]
            for (nx, ny, d) in project(cam[0:3], cam[3:6], cam[6], ar, [(x, .05, z), (x, 1.45, z), (x, 2.1, z)]):
                if d > 0 and abs(nx) <= 1 + margin and abs(ny) <= 1 + margin: return True
        return False
    return f


def mask_contract(c, vanishes, fade=.35):
    """for a producer that builds its own contract: hide the actor in the vanish windows (`vis` = 0) and give the painter the windows (cast `look.monster.vanish`).
    Returns the number of rows hidden. It does NOT move anybody: whatever the trajectory was, it stays continuous."""
    ix = {n: i for i, n in enumerate(c['actor_cols'])}; fps = c['fps']; n = 0
    for who in {v['who'] for v in vanishes}:
        ws = windows([v for v in vanishes if v['who'] == who])
        for st in c['stages']:
            rows = st['actors'].get(who) or []
            for i, r in enumerate(rows):
                t = st['t0'] + i / fps
                if any(a - 1e-9 <= t < b - 1e-9 for a, b, *_ in ws) and r[ix['vis']]: r[ix['vis']] = 0.; n += 1
        look = c['casts'].setdefault(who, {'preset': 'npc'}).setdefault('look', {}); m = look.setdefault('monster', {}); m['vanish'] = [[round(a, 4), round(b, 4), h, ap] for a, b, h, ap in ws]; m['fade'] = fade
    return n


def audit_declared(c, geo, vanishes, **kw):
    """`blocking.audit_contract` on a finished contract, minus the jumps that a VERIFIED declared vanish explains. A jump with no declaration stays an error."""
    base = BLK.audit_contract(c, geo, kw.get('vmax')); out = []
    ws = {v['who']: windows([x for x in vanishes if x['who'] == v['who']]) for v in vanishes if v.get('super')}         # only a creature's declared vanish explains a jump
    for x in base:
        if x.code in ('téléportation', 'passage') and x.who in ws and any(a - .5 <= (x.t or 0) <= (b if b < 1e8 else 1e9) + .5 for a, b, *_ in ws[x.who]): continue
        out.append(x)
    ix = {n: i for i, n in enumerate(c['actor_cols'])}
    for who, wl in ws.items():
        for a, b, how, _ap in wl:
            for st in c['stages']:
                for i, r in enumerate(st['actors'].get(who) or []):
                    t = st['t0'] + i / c['fps']
                    if a + .05 < t < min(b, 1e9) - .05 and r[ix['vis']]:
                        out.append(BLK.Violation('disparition_visible', "%s devrait être invisible à t=%.2f (disparition %s déclarée) mais il est dessiné" % (who, t, how), t, who)); break
                else: continue
                break
    return out


# ------------------------------------------------------------------------------------------------------------- 3. mood
# keys: `mood` = [[name, weight]] among contract.MOODS ; `look` = stage look (film_unified LOOK_KEYS + fog_d, fog_color, key_i, hemi_i, key_color) ;
# `env` = world env keys the horror worlds read (station: rim_col, fog, fog_col, neon, neon_col, sign, bg, lift, rain, lamps, canopy;
# every world: exposure_k, key_k, hemi_k, fill_k, rim_k, lamp_k, sat_k, key_dir, key_col, tint, shadow_tint read by horror_kit.js `grade`; the stage `look` REPLACES a value, so it is used for
# contrast / vignette / grain / sat / shadow_tint (a LIGHT cool multiplier, not a dark colour), never for exposure). No preset sets a red hemisphere, red rim or red neon.
MOOD_PRESETS = {
    'dread': dict(label='angoisse / nuit sombre', genres=['horror', 'horreur', 'thriller'],
                  mood=[['drama', .4]],
                  look=dict(contrast=.34, vignette=.6, grain=.05, sat=.85, shadow_tint='#9fb0d4'),
                  env=dict(exposure_k=.92, key_k=.9, hemi_k=.8, fill_k=.45, rim_k=.3, rim_col='#7f93c8', neon=.18, neon_col=[2.6, 2.5, 2.3], fog_col='#34425e'),
                  light='cold moon key, warm sodium practicals untouched, the rim only a faint cold edge, no red anywhere in the grade'),
    'menace': dict(label='menace / tension', genres=['horror', 'thriller'],
                   mood=[['drama', .55], ['noir', .2]],
                   look=dict(contrast=.4, vignette=.66, grain=.055, sat=.75, shadow_tint='#a4b4c4'),
                   env=dict(exposure_k=.85, key_k=.95, hemi_k=.65, fill_k=.35, rim_k=.2, rim_col='#8aa0c0', neon=.12, neon_col=[2.4, 2.6, 2.4], fog_col='#2c384c'),
                   light='hard key, deep shadows, greenish-white fluorescents instead of red'),
    'liminal': dict(label='malaise calme (lieu vide, fluorescent)', genres=['horror', 'drama'],
                    mood=[['drama', .35]],
                    look=dict(contrast=.2, vignette=.4, grain=.03, sat=.7),
                    env=dict(exposure_k=1.08, key_k=.8, hemi_k=1.15, fill_k=1., rim_k=0., neon=.5, neon_col=[2.5, 2.9, 2.6], fog_col='#4a5c54'),
                    light='flat, pale green fluorescent, nothing dramatic: the wrongness is the lack of shadow'),
    # not horror: the same worlds and materials with another light
    'calm_day': dict(label='jour clair (comédie)', genres=['comedy', 'comedie', 'slice_of_life'],
                     mood=[['comedy', .8], ['warm', .3]],
                     look=dict(contrast=.16, vignette=.2, grain=.012, sat=1.15),
                     env=dict(exposure_k=1.35, key_k=2.6, hemi_k=1.9, fill_k=1.3, rim_k=0., rain=0, lamps=0, canopy=0, neon=.05, neon_col=[2.2, 2.2, 2.2], fog=.006, fog_col='#cfe0f2', bg='#9ec4ec', lift='#506070', key_col='#fff3e0', key_dir=[-.35, .9, .3]),
                     light='high sun, soft sky fill, no practicals needed'),
    'golden_hour': dict(label='heure dorée (romance)', genres=['romance'],
                        mood=[['romance', .6], ['dusk', .6]],
                        look=dict(contrast=.22, vignette=.38, grain=.015, sat=1.1),
                        env=dict(exposure_k=1.2, key_k=2.2, hemi_k=1.6, fill_k=1., rim_k=1.4, rim_col='#ffb878', rain=0, lamps=.3, canopy=.3, neon=.1, neon_col=[2.6, 2.1, 1.6], fog=.01, fog_col='#e8b890', bg='#e0a070', lift='#503830', key_col='#ffc088', key_dir=[-.85, .3, .3]),
                        light='low warm key, long soft rim, peach fog'),
    'cold_dawn': dict(label='aube froide (drame)', genres=['drama', 'drame'],
                      mood=[['drama', .9]],
                      look=dict(contrast=.28, vignette=.5, grain=.03, sat=.72),
                      env=dict(exposure_k=1.2, key_k=1.9, hemi_k=1.5, fill_k=.8, rim_k=.6, rim_col='#a8c0e8', rain=.3, lamps=.4, canopy=.5, neon=.1, neon_col=[2.3, 2.4, 2.6], fog=.02, fog_col='#8a9aae', bg='#6a7a90', key_col='#c8d8f0', key_dir=[-.3, .7, .5]),
                      light='overcast blue-grey, restrained colours'),
    'clean_future': dict(label='futur propre (science-fiction)', genres=['scifi', 'sci-fi'],
                         mood=[['scifi', .8]],
                         look=dict(contrast=.26, vignette=.35, grain=.02, sat=1.05),
                         env=dict(exposure_k=1.15, key_k=1.5, hemi_k=1.2, fill_k=1., rim_k=2., rim_col='#40d0ff', rain=0, lamps=.5, canopy=1, neon=.6, neon_col=[1.6, 2.6, 3.0], fog=.012, fog_col='#2a4a6a', bg='#1a3050', key_col='#c0e0ff'),
                         light='cyan edge light on a cool key'),
}
DEFAULT_PRESET = {'horror': 'dread', 'horreur': 'dread', 'thriller': 'menace', 'comedy': 'calm_day', 'comedie': 'calm_day', 'slice_of_life': 'calm_day', 'romance': 'golden_hour',
                  'drama': 'cold_dawn', 'drame': 'cold_dawn', 'scifi': 'clean_future', 'sci-fi': 'clean_future'}
FORBIDDEN_ENV_RED = ('panel_red', 'red')           # keys that tint a whole world red; a preset must not set them above .05


def mood_for(genre):
    """preset name for a genre word, or None (the genre keeps the shared MOODS entry)"""
    return DEFAULT_PRESET.get(fold(genre or ''))


def preset(name, k=1.):
    """-> {mood, look, env}: the three dicts to merge into a shot (mood, look) and into the world env, scaled by k (0 = nothing, 1 = full) where it is a number.
    Colours stay strings; numbers are blended with their neutral (1.0 for gains, the preset value otherwise)."""
    if name not in MOOD_PRESETS: raise IntentError("ambiance inconnue : %r (connues : %s)" % (name, ', '.join(MOOD_PRESETS)))
    p = MOOD_PRESETS[name]; k = max(0., min(1., k))
    return dict(mood=[[m, round(w * k, 4)] for m, w in p['mood']], look=dict(p['look']), env={a: (list(b) if isinstance(b, list) else b) for a, b in p['env'].items()})


def apply_preset(ep, name, k=1., shots=None, keep_env=True):
    """merge a preset into an episode dict (in place) and return it: the shots' `mood` and `look`, and `world_env`. A value the episode already sets in a shot's
    own `env` / `look` wins when `keep_env` (the story's light is never overridden by a genre)."""
    pr = preset(name, k); ids = None if shots is None else set(shots)
    ep.setdefault('world_env', {})
    for key, v in pr['env'].items():
        if not (keep_env and key in ep['world_env']): ep['world_env'][key] = v
    for s in ep['shots']:
        if ids is not None and s.get('id') not in ids: continue
        s['mood'] = pr['mood']; s['look'] = {**pr['look'], **(s.get('look') or {})}
    return ep


def audit_preset(name):
    """a preset that would tint the world red is a bug, not a style: returns the list of problems"""
    p = MOOD_PRESETS[name]; bad = []
    for key in FORBIDDEN_ENV_RED:
        if (p['env'].get(key) or 0) > .05: bad.append('%s = %s teinte tout le monde en rouge' % (key, p['env'][key]))
    nc = p['env'].get('neon_col')
    if nc and nc[0] > 1.5 * max(nc[1], nc[2]): bad.append('néon rouge imposé : %s' % nc)
    rc = p['env'].get('rim_col')
    if isinstance(rc, str) and int(rc[1:3], 16) > 1.6 * max(int(rc[3:5], 16), int(rc[5:7], 16)) and name in ('dread', 'menace', 'liminal'): bad.append('rim rouge imposé : %s' % rc)
    return bad


def hooks():
    """what the integrator wires (one line each), kept next to the code that implements it"""
    return dict(
        compile_episode="director.build: `blk, geo = BLK.compile_episode(ep)` -> `genre_intent.compile_episode(ep)` (transparent without `vanish` beats)",
        preflight="director.build: `BLK.preflight(ep, blk, geo, abs_shots, aspect)` -> `genre_intent.preflight(...)` (audits every life + the declared vanishes)",
        cast="casts[id] = genre_intent.cast_entry('faceless_void', vanishes=view.vanishes_of(id)) for a creature; painter reads look.monster",
        mood="genre_intent.apply_preset(ep, genre_intent.mood_for(genre))  or per shot: shot['mood'], shot['look'] from preset(name)",
        painter="voxelgpu_js/engine/horror_kit.js: buildFaceless (creature), buildExtras (poses, vanish windows), horror worlds read env rim_k/fill_k/hemi_k/sat_k/tint/shadow_tint/key_dir",
        contract="genre_intent.mask_contract(c, vanishes) + audit_declared(c, geo, vanishes) for a contract built elsewhere")
