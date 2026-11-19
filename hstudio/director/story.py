"""V3 story layer: structured narrative instructions -> the EXISTING script and episode inputs.

This is a BRIDGE, not a second pipeline. Nothing here renders, mixes or calls the network.

    Brief   (genre, indicative duration, voice mode, engine, 2 or 3 choices)
      -> Outline (Beats: one line of story + the INTENTION behind it: camera, action, keyword, note)
         -> to_script_text()  : plain text read by the existing hstudio/script.py:parse_script
         -> to_episode(lines) : episode dict accepted as-is by hstudio/director/validate.py:validate

The point of the Beat is that an intention is never thrown away: a camera intent (shot / move / on), an action
intent (a verb of acting/timeline.py) and a free-text "note" (why this beat exists) travel from the brief all the
way into the episode JSON, and check_episode() proves it survived the validator.

mock_outline() is a DETERMINISTIC TEST FIXTURE, not a writer. It fills a fixed dramatic skeleton with words taken
from the brief. It invents nothing and must never be presented as an AI-written story: it exists so the bridge can
be tested offline, for free, with no API key. Real writing goes through an LLM: build(brief, provider='claude')
reuses hstudio/director/providers.py with STORY_SYSTEM; that path is NOT exercised by the offline tests.
"""
import copy, json, re, unicodedata
from dataclasses import dataclass, field, asdict
from .validate import FACES, SHOTS, MOVES2, REACT_KINDS, known_verbs

SPEECH_WPS = 2.6                 # French narration, ElevenLabs pace: words per second
LINE_PAUSE = .45                 # breath between two lines (one line = one breath, see script.py)
DURATION_TOL = .30               # a duration is "indicative": +/- 30 % is on target
VOICE_MODES = ('voice', 'dialogue', 'hybrid')
ENGINES = ('pixel3d', 'console', 'auto')
ROLES = ('hook', 'setup', 'turn', 'escalation', 'reveal', 'choice', 'outro')

# genre -> house look. Every name below is checked against the engines by check_story.py (music.NAMES,
# places.PLACES, assets.FACE_KINDS, ambience.AMBIENCES): nothing here may invent a value the renderer lacks.
GENRES = {
    'horror':    dict(music='horror',    places=('basement', 'attic', 'graveyard', 'cave'),             face='scared',     ambience='night',       weather='none'),
    'adventure': dict(music='adventure', places=('forest', 'mountain', 'island', 'cave'),               face='determined', ambience='forest',      weather='none'),
    'comedy':    dict(music='comedy',    places=('kitchen', 'classroom', 'park', 'cafe'),               face='laugh',      ambience='park',        weather='none'),
    'romance':   dict(music='romance',   places=('park', 'cafe', 'beach', 'lake'),                      face='shy',        ambience='beach',       weather='none'),
    'mystery':   dict(music='mystery',   places=('library', 'office', 'attic', 'village'),              face='suspicious', ambience='room',        weather='none'),
    'sad':       dict(music='sad',       places=('bedroom', 'river', 'graveyard', 'park'),              face='sad',        ambience='rain',        weather='rain'),
    'action':    dict(music='action',    places=('city_street', 'lab', 'space_station', 'volcano'),     face='urgent',     ambience='city',        weather='none'),
    'epic':      dict(music='epic',      places=('castle', 'throne_room', 'mountain', 'volcano'),       face='proud',      ambience='wind',        weather='none'),
    'calm':      dict(music='calm',      places=('lake', 'countryside', 'beach', 'library'),            face='calm',       ambience='countryside', weather='none'),
}
# role -> console scene type (validate.SCENES). The CONSOLE engine ignores the 3D camera, so the intent is kept
# on the shot anyway (validate's console branch only rewrites "scene", it leaves camera/actions untouched).
CONSOLE_SCENE = {'hook': 'door', 'setup': 'room', 'turn': 'hallway', 'escalation': 'hallway',
                 'reveal': 'face', 'choice': 'screen', 'outro': 'black'}
# role -> default camera intention (shot in validate.SHOTS, move in validate.MOVES2)
ROLE_CAMERA = {'hook': ('establishing', 'dolly_in'), 'setup': ('medium', 'static'), 'turn': ('medium_full', 'push'),
               'escalation': ('close', 'handheld'), 'reveal': ('extreme_close', 'dolly_in'),
               'choice': ('two_shot', 'static'), 'outro': ('wide', 'crane_up')}


def slug(s):
    s = unicodedata.normalize('NFD', str(s)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '_', s).strip('_') or 'hero'


def words(text):
    return len(re.findall(r"[\wÀ-ÿ'-]+", text or ''))


def line_seconds(text):
    """indicative length of one narration line (one breath)"""
    return words(text) / SPEECH_WPS + LINE_PAUSE


def card_lines(text, width=12):
    """a choice label as the renderer wants it: max 2 lines of 12 upper-case characters (see ui.choice)"""
    out = ['', '']
    for w in re.sub(r'(?i)^\s*choix\s*[abc]\s*[:\-]\s*', '', text or '').upper().split():
        k = 0 if len((out[0] + ' ' + w).strip()) <= width else 1
        if len((out[k] + ' ' + w).strip()) <= width: out[k] = (out[k] + ' ' + w).strip()
    return out


# ---------------------------------------------------------------- the IR


@dataclass
class Brief:
    """what one click gives us: a genre, a length, a way of speaking, an engine, a number of choices"""
    genre: str = 'horror'
    duration_s: float = 60.
    voice_mode: str = 'voice'            # voice (narration) | dialogue (characters) | hybrid
    engine: str = 'auto'                 # pixel3d | console | auto
    hero: str = 'Toi'
    other: str = 'Léa'                   # the second voice, used by dialogue / hybrid
    place: str = ''                      # '' -> picked from the genre
    premise: str = ''                    # one sentence from the owner, optional
    series: str = ''
    part_label: str = ''
    n_choices: int = 2                   # 2 or 3
    previous_choice: str = ''
    seed: int = 7

    def resolve_engine(self):
        if self.engine in ('pixel3d', 'console'): return self.engine
        t = f'{self.premise} {self.place} {self.series}'.lower()
        return 'console' if re.search(r'console|jeu vid|manette|pixel game|écran de jeu|ecran de jeu', t) else 'pixel3d'

    def resolve_genre(self):
        return self.genre if self.genre in GENRES else 'horror'

    def look(self):
        return GENRES[self.resolve_genre()]

    def resolve_place(self):
        if self.place: return self.place
        p = self.look()['places']
        return p[self.seed % len(p)]

    def problems(self):
        P = []
        if self.genre not in GENRES: P.append(f'genre inconnu : {self.genre}')
        if self.voice_mode not in VOICE_MODES: P.append(f'mode de voix inconnu : {self.voice_mode}')
        if self.engine not in ENGINES: P.append(f'moteur inconnu : {self.engine}')
        if self.n_choices not in (2, 3): P.append(f'{self.n_choices} choix : il en faut 2 ou 3')
        if not (10 <= float(self.duration_s) <= 1800): P.append(f'durée hors bornes : {self.duration_s} s')
        return P

    to_dict = asdict

    @staticmethod
    def from_dict(d):
        return Brief(**{k: v for k, v in (d or {}).items() if k in Brief.__dataclass_fields__})


@dataclass
class Beat:
    """one line of story + the intention behind it. One beat == one narration line == one shot."""
    role: str = 'setup'
    text: str = ''
    speaker: str = ''                    # '' = narrator (voice over); otherwise the character's display name
    shot: str = 'medium'                 # camera intent, validate.SHOTS
    move: str = 'static'                 # camera intent, validate.MOVES2
    on: str = ''                         # who the camera is on (actor id)
    action: dict = field(default_factory=dict)   # action intent: {"do": <verb of acting/timeline>, ...}
    face: str = ''
    keyword: str = ''
    place: str = ''                      # '' = the outline's place
    sfx: list = field(default_factory=list)
    note: str = ''                       # WHY this beat exists, in French: the intention, kept in the episode
    choice_letter: str = ''              # 'A' / 'B' / 'C' when role == 'choice'

    def seconds(self):
        return line_seconds(self.script_line())

    def script_line(self):
        """the line as the existing script parser will read it (dialogue = "NOM : réplique", see director/scene.py)"""
        t = re.sub(r'\s+', ' ', (self.text or '').strip())
        return f'{self.speaker.upper()} : {t}' if self.speaker else t

    def problems(self):
        P = []
        if not (self.text or '').strip(): P.append('réplique vide')
        if '[' in (self.text or '') or ']' in (self.text or ''): P.append('une balise [..] dans le texte casserait 1 beat = 1 ligne')
        if '\n' in (self.text or ''): P.append('un retour à la ligne casserait 1 beat = 1 ligne')
        if self.role not in ROLES: P.append(f'rôle inconnu : {self.role}')
        if self.shot not in SHOTS: P.append(f'intention de plan inconnue : {self.shot}')
        if self.move not in MOVES2: P.append(f'mouvement de caméra inconnu : {self.move}')
        if self.face and self.face not in FACES: P.append(f'expression inconnue : {self.face}')
        if self.action:
            if self.action.get('do') not in known_verbs(): P.append(f'verbe inconnu : {self.action.get("do")}')
            if self.action.get('do') == 'react' and self.action.get('kind') not in REACT_KINDS: P.append(f'réaction inconnue : {self.action.get("kind")}')
        return P

    to_dict = asdict

    @staticmethod
    def from_dict(d):
        d = dict(d or {})
        return Beat(**{k: v for k, v in d.items() if k in Beat.__dataclass_fields__})


@dataclass
class Choice:
    """a branch offered to the viewer. "reason" is the dramatic argument: two choices must not mean the same thing."""
    letter: str = 'A'
    text: str = ''                       # the line said out loud ("Choix A : ...")
    label: str = ''                      # short wording shown on the card
    reason: str = ''                     # why this branch is tempting (kept, never rendered)
    consequence: str = ''                # where it would lead (kept for the next episode of the series)

    def card(self):
        return card_lines(self.label or self.text)

    def problems(self):
        P = []
        if self.letter not in ('A', 'B', 'C'): P.append(f'lettre de choix invalide : {self.letter}')
        if not (self.text or '').strip(): P.append(f'choix {self.letter} sans réplique')
        if not (self.reason or '').strip(): P.append(f'choix {self.letter} sans raison (choix non raisonné)')
        if any(len(l) > 12 for l in self.card()): P.append(f'choix {self.letter} : carte > 12 caractères')
        return P

    to_dict = asdict

    @staticmethod
    def from_dict(d):
        return Choice(**{k: v for k, v in (d or {}).items() if k in Choice.__dataclass_fields__})


@dataclass
class Outline:
    brief: Brief = field(default_factory=Brief)
    beats: list = field(default_factory=list)
    choices: list = field(default_factory=list)
    summary: str = ''
    place: str = ''
    music: str = ''
    generator: str = 'mock'              # 'mock' = test fixture; otherwise the provider that wrote it

    @property
    def is_mock(self):
        return self.generator == 'mock'

    def hero_id(self):
        return slug(self.brief.hero)

    def speakers(self):
        return [s for s in dict.fromkeys(b.speaker for b in self.beats if b.speaker)]

    def seconds(self):
        return sum(b.seconds() for b in self.beats)

    # ---- conversion to the EXISTING inputs

    def to_script_text(self):
        """the script, exactly in the format hstudio/script.py:parse_script already reads (one line = one breath)"""
        return '\n'.join(b.script_line() for b in self.beats)

    def to_episode(self, n_lines=None, series='', series_state=None):
        """an episode dict for hstudio/director/validate.py:validate(ep, n_lines, style).

        One beat -> one shot covering its own line, so the mapping beat i <-> shot i <-> line i is exact and the
        intention can be checked afterwards (check_episode).

        series / series_state: the series memory of director/saga.py. `series_state` is the FLAT shape the engines
        already read (acting/timeline.py seeds what a character holds from it); giving it here replays exactly one
        branch of the arc. Left out, the episode is written exactly as before."""
        br = self.brief; style = br.resolve_engine(); look = br.look()
        n = len(self.beats) if n_lines is None else int(n_lines)
        hero = self.hero_id()
        cast = {hero: {}}
        for s in self.speakers(): cast.setdefault(slug(s), {})
        if series:
            for cid in cast: cast[cid].setdefault('ref', cid)      # library identity: same look and voice every episode
        meta, shots = {}, []
        for i, b in enumerate(self.beats):
            who = slug(b.speaker) if b.speaker else (b.on or hero)
            m = {}
            if b.keyword: m['keywords'] = [b.keyword]
            if b.speaker: m['label'] = b.speaker.upper()
            if m: meta[str(i)] = m
            sh = {'lines': [i, i], 'camera': {'shot': b.shot, 'move': b.move, 'on': who},
                  'actors': [{'id': who, 'face': b.face or look['face']}],
                  'intent': {'role': b.role, 'note': b.note}}       # free key: the validator keeps unknown keys
            if b.action: sh['actions'] = [dict(b.action, who=b.action.get('who') or who)]
            if b.sfx: sh['sfx'] = [dict(c) if isinstance(c, dict) else {'name': c} for c in b.sfx]
            if style == 'pixel3d': sh['set'] = b.place or self.place
            else: sh['scene'] = {'type': CONSOLE_SCENE.get(b.role, 'room')}
            if self.choices and b.role == 'choice' and b.choice_letter == self.choices[0].letter:
                sh['ui'] = {'choice': self._ui_choice()}
            shots.append(sh)
        if shots:
            last = shots[-1].setdefault('ui', {})
            last['endcard'] = {'part': br.part_label or 'PARTIE 1', 'headline': 'A OU B ?' if len(self.choices) == 2 else 'A, B OU C ?',
                               'cta': 'VOTE EN COMMENTAIRE', 'button': 'ABONNE-TOI'}
        ep = {'style': style, 'engine_version': 2, 'music': self.music or look['music'], 'summary': self.summary,
              'cast': cast, 'lines': meta, 'shots': shots, 'hud': {},
              'choices': [c.to_dict() for c in self.choices],       # the reasoned branches, kept for the series
              'story_brief': br.to_dict(), 'generator': self.generator}
        if series: ep['series'] = series
        if series_state is not None: ep['series_state'] = copy.deepcopy(series_state)
        if style == 'pixel3d':
            ep['default_set'] = self.place
            ep['sets'] = {self.place: {'type': self.place, 'seed': br.seed}}
            if look.get('ambience') and look['ambience'] != 'none': ep['ambience'] = look['ambience']
            if look.get('weather') and look['weather'] != 'none': ep['weather'] = look['weather']
        if n != len(shots) and shots: shots[-1]['lines'][1] = max(shots[-1]['lines'][0], n - 1)
        return ep

    def _ui_choice(self):
        ui = {'title': 'TU FAIS QUOI ?', 'cursor': 'blink'}
        for c in self.choices: ui[c.letter] = c.card()
        return ui

    # ---- checks

    def problems(self):
        """everything that would make this outline unusable or unfaithful to the brief"""
        P = list(self.brief.problems())
        P += [f'beat {i} : {p}' for i, b in enumerate(self.beats) for p in b.problems()]
        P += [p for c in self.choices for p in c.problems()]
        if not self.beats: P.append('aucun beat')
        if len(self.choices) not in (2, 3): P.append(f'{len(self.choices)} choix : il en faut 2 ou 3')
        if len(self.choices) != self.brief.n_choices: P.append(f'{len(self.choices)} choix pour {self.brief.n_choices} demandés')
        seen = {}
        for c in self.choices:
            k = slug(c.label or c.text)
            if k in seen: P.append(f'choix {c.letter} et {seen[k]} identiques : les choix doivent différer')
            seen[k] = c.letter
        letters = [c.letter for c in self.choices]
        if len(set(letters)) != len(letters): P.append('lettres de choix en double')
        if self.brief.resolve_engine() == 'pixel3d' and not self.place: P.append('décor manquant')
        d, want = self.seconds(), float(self.brief.duration_s)
        if abs(d - want) > want * DURATION_TOL: P.append(f'durée estimée {d:.0f} s pour {want:.0f} s demandées (±{DURATION_TOL:.0%})')
        if self.brief.voice_mode == 'voice' and self.speakers(): P.append('mode voix off mais des répliques sont attribuées')
        if self.brief.voice_mode == 'dialogue' and any(not b.speaker for b in self.beats): P.append('mode dialogue mais des lignes sans locuteur')
        if self.brief.voice_mode == 'hybrid' and (not self.speakers() or all(b.speaker for b in self.beats)):
            P.append('mode hybride : il faut à la fois de la voix off et des répliques')
        return P

    def check_episode(self, ep):
        """what the validator lost: returns the intentions of the outline missing from the validated episode"""
        lost = []
        shots = ep.get('shots') or []
        if len(shots) != len(self.beats):
            lost.append(f'{len(shots)} plans pour {len(self.beats)} beats')
            return lost
        for i, (b, s) in enumerate(zip(self.beats, shots)):
            cam = s.get('camera') or {}
            if list(s.get('lines') or []) != [i, i] and not (i == len(shots) - 1 and (s.get('lines') or [0, 0])[0] == i):
                lost.append(f'beat {i} : ligne {s.get("lines")} au lieu de [{i}, {i}]')
            if cam.get('shot') != b.shot: lost.append(f'beat {i} : plan "{b.shot}" perdu ({cam.get("shot")})')
            if cam.get('move') != b.move: lost.append(f'beat {i} : mouvement "{b.move}" perdu ({cam.get("move")})')
            if (s.get('intent') or {}).get('note') != b.note: lost.append(f'beat {i} : intention perdue')
            if b.action and not s.get('actions'): lost.append(f'beat {i} : action "{b.action.get("do")}" perdue')
        if len(ep.get('choices') or []) != len(self.choices): lost.append('choix perdus')
        return lost

    # ---- serialisation

    def to_dict(self):
        return {'brief': self.brief.to_dict(), 'beats': [b.to_dict() for b in self.beats],
                'choices': [c.to_dict() for c in self.choices], 'summary': self.summary,
                'place': self.place, 'music': self.music, 'generator': self.generator}

    def to_json(self, indent=2):
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @staticmethod
    def from_dict(d):
        d = d or {}
        br = Brief.from_dict(d.get('brief'))
        o = Outline(brief=br, beats=[Beat.from_dict(b) for b in d.get('beats') or []],
                    choices=[Choice.from_dict(c) for c in d.get('choices') or []],
                    summary=d.get('summary', ''), place=d.get('place') or br.resolve_place(),
                    music=d.get('music') or br.look()['music'], generator=d.get('generator', 'mock'))
        return o

    @staticmethod
    def from_json(txt):
        return Outline.from_dict(json.loads(txt))


# ---------------------------------------------------------------- MOCK (test fixture, NOT a writer)

MOCK_TAG = '[MOCK]'
# A fixed dramatic skeleton. {hero} {other} {place} {thing} are filled from the brief: no invention, no variation
# beyond the seed picking inside these fixed tables. This exists to test the conversion, nothing else.
MOCK_THING = {'horror': 'la porte', 'adventure': 'la carte', 'comedy': 'le gâteau', 'romance': 'la lettre',
              'mystery': 'le carnet', 'sad': 'la photo', 'action': 'le signal', 'epic': 'la couronne', 'calm': 'le silence'}
MOCK_PLACE_FR = {'basement': 'la cave', 'attic': 'le grenier', 'graveyard': 'le cimetière', 'cave': 'la grotte',
                 'forest': 'la forêt', 'mountain': 'la montagne', 'island': "l'île", 'kitchen': 'la cuisine',
                 'classroom': 'la salle de classe', 'park': 'le parc', 'cafe': 'le café', 'beach': 'la plage',
                 'lake': 'le lac', 'library': 'la bibliothèque', 'office': 'le bureau', 'village': 'le village',
                 'bedroom': 'la chambre', 'river': 'la rivière', 'city_street': 'la rue', 'lab': 'le laboratoire',
                 'space_station': 'la station', 'volcano': 'le volcan', 'castle': 'le château',
                 'throne_room': 'la salle du trône', 'countryside': 'la campagne'}
MOCK_BODY = [
    ('setup', "Tu avances vers {thing} sans faire de bruit.", 'look_around', 'avancer'),
    ('setup', "Rien ne bouge dans {place}, et c'est bien ça le problème.", None, 'bouge'),
    ('escalation', "Un bruit sec, juste derrière {thing}.", 'react', 'bruit'),
    ('escalation', "Tu retiens ton souffle et tu comptes jusqu'à trois.", 'wait', 'souffle'),
    ('escalation', "{other} te fait signe de ne surtout pas t'arrêter.", 'gesture', 'signe'),
    ('setup', "Chaque pas dans {place} te coûte un peu plus.", 'walk_to', 'pas'),
]
MOCK_CHOICES = [
    ('A', "Choix A : ouvrir {thing} tout de suite.", 'OUVRIR', "l'impatience : savoir maintenant, quitte à tout déclencher", 'la confrontation immédiate'),
    ('B', "Choix B : reculer et prévenir {other}.", 'RECULER', "la prudence : ne rien affronter seul, mais perdre du temps", "l'alliance, plus tard"),
    ('C', "Choix C : éteindre la lumière et attendre.", 'ATTENDRE', "la ruse : laisser venir plutôt que provoquer", "l'observation, le piège retourné"),
]


def mock_outline(brief):
    """DETERMINISTIC TEST FIXTURE. Fills a fixed skeleton from the brief; it does not invent a story.
    Same brief -> byte-identical outline. Used by tools/check_story.py so the bridge is testable with no API."""
    br = brief if isinstance(brief, Brief) else Brief.from_dict(brief)
    g = br.resolve_genre(); look = GENRES[g]; place = br.resolve_place()
    ctx = {'hero': br.hero, 'other': br.other, 'place': MOCK_PLACE_FR.get(place, place.replace('_', ' ')),
           'thing': MOCK_THING.get(g, 'la porte')}
    def F(s): return s.format(**ctx)
    mode = br.voice_mode if br.voice_mode in VOICE_MODES else 'voice'
    def spk(i, role):
        """who says the line: voice over, a character, or both alternating (hybrid)"""
        if mode == 'voice': return ''
        if mode == 'dialogue': return br.hero if (i % 2 == 0 or role == 'choice') else br.other
        return br.other if (i % 3 == 2 and role not in ('hook', 'outro')) else ''
    beats = [Beat(role='hook', text=F("Tu n'aurais jamais dû revenir dans {place}."), shot=ROLE_CAMERA['hook'][0],
                  move=ROLE_CAMERA['hook'][1], face=look['face'], keyword='jamais',
                  note="ouvrir sur le lieu et poser l'interdit", action={'do': 'look_around'})]
    n = 3 if br.n_choices == 3 else 2
    tail = [F("{thing} n'était pas fermée.")] + [F(t) for _, t, _, _, _ in MOCK_CHOICES[:n]] + ["C'est toi qui décides."]
    target = float(br.duration_s) - sum(line_seconds(t) for t in tail)
    k = 0
    while sum(b.seconds() for b in beats) < max(0., target):
        role, tpl, verb, kw = MOCK_BODY[k % len(MOCK_BODY)]; k += 1
        act = {}
        if verb == 'react': act = {'do': 'react', 'kind': 'startle'}
        elif verb == 'gesture': act = {'do': 'gesture', 'name': 'point'}
        elif verb == 'walk_to': act = {'do': 'walk_to', 'to': 'start'}
        elif verb: act = {'do': verb}
        beats.append(Beat(role=role, text=F(tpl), speaker=spk(len(beats), role), shot=ROLE_CAMERA[role][0],
                          move=ROLE_CAMERA[role][1], face=look['face'], keyword=kw, action=act,
                          note=f'tenir la tension ({role})'))
        if k > 400: break
    beats.append(Beat(role='reveal', text=F("{thing} n'était pas fermée."), shot=ROLE_CAMERA['reveal'][0],
                      move=ROLE_CAMERA['reveal'][1], face='shocked', keyword='fermée',
                      note='la révélation, en très gros plan', sfx=[{'name': 'sting', 'gain': .9}]))
    choices = [Choice(letter=l, text=F(t), label=lb, reason=F(rz), consequence=cq) for l, t, lb, rz, cq in MOCK_CHOICES[:n]]
    for c in choices:
        beats.append(Beat(role='choice', text=c.text, speaker=spk(len(beats), 'choice'), shot=ROLE_CAMERA['choice'][0],
                          move=ROLE_CAMERA['choice'][1], face=look['face'], keyword=slug(c.label).upper()[:12] or 'CHOIX',
                          note=f'proposer la branche {c.letter} : {c.reason}', choice_letter=c.letter))
    beats.append(Beat(role='outro', text="C'est toi qui décides.", shot=ROLE_CAMERA['outro'][0],
                      move=ROLE_CAMERA['outro'][1], face=look['face'], keyword='décides', note='carte de fin et appel au vote'))
    if mode == 'dialogue':                   # every line must be said by someone
        for i, b in enumerate(beats):
            if not b.speaker: b.speaker = br.hero if i % 2 == 0 else br.other
    elif mode == 'hybrid':                   # hybrid must really mix voice over and characters
        if not any(b.speaker for b in beats) and len(beats) > 2: beats[1].speaker = br.other
        if all(b.speaker for b in beats): beats[0].speaker = ''
    return Outline(brief=br, beats=beats, choices=choices, place=place, music=look['music'], generator='mock',
                   summary=f"{MOCK_TAG} Fixture déterministe ({g}, {mode}, {place}) : squelette de test, aucune histoire inventée.")


def mock_timing(lines, gap=.30, head=.15):
    """OFFLINE TEST STUB, not an alignment: gives each parsed line a plausible start/end so an episode can be
    rendered without ElevenLabs. The real timings come from pipeline.step_voice + step_align and are word-accurate;
    these ones are only the indicative estimate of line_seconds(). Never use this for a published video."""
    t = head
    for l in lines:
        d = max(.6, words(l.get('text', '')) / SPEECH_WPS)
        l['start'] = round(t, 3); l['end'] = round(t + d, 3); l['segs'] = [[l['start'], l['end']]]
        t = l['end'] + gap
    return lines


# ---------------------------------------------------------------- real writing (not used by the offline tests)

STORY_SYSTEM = """Tu écris le plan d'un court épisode interactif en français, à la deuxième personne.
Réponds UNIQUEMENT par un objet JSON : {"summary": "...", "place": "<nom de décor>", "music": "<musique>",
"beats": [{"role": "hook|setup|turn|escalation|reveal|choice|outro", "text": "<une ligne, un souffle>",
"speaker": "<nom ou vide pour la voix off>", "shot": "<cadre>", "move": "<mouvement>", "face": "<expression>",
"keyword": "<un mot>", "action": {"do": "<verbe>"}, "note": "<pourquoi ce beat>", "choice_letter": "A|B|C|"}],
"choices": [{"letter": "A", "text": "Choix A : ...", "label": "<12 car. max>", "reason": "<pourquoi c'est tentant>",
"consequence": "<où ça mène>"}]}
Une ligne de texte = un souffle, sans balise [..] et sans retour à la ligne. Les choix doivent être réellement
différents (pas deux formulations de la même idée). Respecte le genre, la durée indicative et le mode de voix."""


def build(brief, provider='mock', settings=None, log=print):
    """Brief -> Outline. provider='mock' is the offline fixture and makes NO network call.
    Any other provider goes through hstudio/director/providers.py (paid APIs: never used by the tests)."""
    br = brief if isinstance(brief, Brief) else Brief.from_dict(brief)
    if provider in (None, '', 'mock', 'heuristic'): return mock_outline(br)
    from . import providers
    user = (f"GENRE: {br.resolve_genre()}\nDURÉE INDICATIVE: {br.duration_s:.0f} s\nMODE DE VOIX: {br.voice_mode}\n"
            f"MOTEUR: {br.resolve_engine()}\nDÉCOR: {br.resolve_place()}\nHÉROS: {br.hero}\nAUTRE: {br.other}\n"
            f"NOMBRE DE CHOIX: {br.n_choices}\nSÉRIE: {br.series} {br.part_label}\n"
            f"CHOIX PRÉCÉDENT: {br.previous_choice}\nPRÉMISSE: {br.premise}")
    data = providers.parse_json(providers.call(provider, settings or {}, STORY_SYSTEM, user, log=log))
    data['brief'] = br.to_dict(); data['generator'] = provider
    return Outline.from_dict(data)
