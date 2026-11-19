"""Mise en scene sonore narrative : un PLAN (ambiances, courbe de tension, silences anormaux,
evenements minutes) deduit des beats du recit, puis rendu par le mixeur EXISTANT.

Ce module ne mixe rien et ne synthetise rien : tout le son vient deja de
audio/synth.py + audio/library.py (bruitages CC0) et de audio/ambience.py (lits d'ambiance),
et c'est audio/mixer.py qui le rend - ducking, compression, loudnorm -14 LUFS compris.
Ce qui manquait n'etait pas le son, c'etait la *mise en scene* : jusqu'ici l'ambiance, l'intensite,
les silences et les cues devaient etre ecrits a la main dans episode.json, plan par plan.

    plan = soundscape.plan(ep, lines, spans)      # beats detectes dans le script
    ep_b = plan.apply(ep)                         # episode.json enrichi
    Mixer(voice, lines, ep_b, dur, style, wd).run(spans, out)   # mixeur inchange

Contrat d'integration (realisateur de cinema, acting, camera) : rien a importer d'ici, il suffit de
fournir des beats explicites : plan(..., beats=[{'kind': 'door_close', 'line': 14}, ...]).
Les cles ecrites (audio.ambience, audio.intensity, audio.silence*, shots[].sfx) sont celles que le
mixeur lit deja : aucun gain global, aucune voix validee n'est touchee. Entierement deterministe.
"""
import copy, re, unicodedata
from dataclasses import dataclass, field

# ------------------------------------------------------------------ espaces (interieur / exterieur)
# Un espace fixe l'ambiance de fond, la reverberation des evenements qui s'y produisent et leur
# niveau : le meme pas ne sonne pas pareil dans la rue, dans un couloir etroit ou dans un hall vide.
SPACES = {
    'street':    dict(ambience='city',  reverb=.16, gain=1.00, label='exterieur, rue animee'),
    'threshold': dict(ambience='city',  reverb=.30, gain=.85,  label='interieur, porte ouverte sur la rue'),
    'corridor':  dict(ambience='room',  reverb=.46, gain=.95,  label='interieur etroit, ferme'),
    'hollow':    dict(ambience='cave',  reverb=.70, gain=.80,  label='interieur vaste et vide'),
    'outside':   dict(ambience='wind',  reverb=.22, gain=.90,  label='exterieur, vent lointain'),
    'night':     dict(ambience='night', reverb=.34, gain=.90,  label='exterieur, nuit'),
}

# Niveau du lit d'ambiance. Mesure sur Etage Zero partie 4 (tools/soundscape_ab.py) : le mixeur
# normalise chaque ambiance a rms .02, ce qui la place vers -42 dB dans le mix final, soit 6 dB SOUS
# le lit musical et 13 dB sous la narration : inaudible. x2.4 (+7.6 dB) la met juste sous la musique,
# donc presente dans les trous de narration et effacee des que la voix parle (le ducking existant
# s'en charge). C'est la cle `ambience_gain` que le mixeur lit deja ; aucun gain voix/musique touche.
AMBIENCE_GAIN = 2.4

# ------------------------------------------------------------------ beats narratifs
# Vocabulaire volontairement court : un beat = une cause dans l'histoire. Chacun dit ou l'on est
# (espace), quelle tension il installe, et quels evenements sonores il declenche.
@dataclass
class BeatKind:
    space: str = None            # changement d'espace provoque par le beat (None = on reste)
    tension: float = None        # cible de la courbe d'intensite (None = inchangee)
    silence: float = None        # creux anormal : niveau plancher du fond (0 = plus rien)
    label: str = ''
    cooldown: float = 5.         # une situation qui se prolonge sur 3 repliques ne redeclenche pas 3 fois

BEATS = {
    'door_open':    BeatKind(space='threshold', tension=.45, label="une porte ouverte laisse entrer le dehors"),
    'door_close':   BeatKind(space='corridor',  tension=.70, label="la porte se referme, le dehors est coupe"),
    'threat_run':   BeatKind(                   tension=.95, label="la menace se met a courir", cooldown=6.),
    'grab':         BeatKind(                   tension=.82, label="geste brusque, contact, vetement", cooldown=2.5),
    'dead_silence': BeatKind(space='hollow',    tension=.15, silence=.05, label="silence anormal", cooldown=12.),
    'threat_near':  BeatKind(                   tension=1.0, label="la menace est la, tout pres", cooldown=9.),
    'calm':         BeatKind(                   tension=.30, label="retour au calme"),
    'go_outside':   BeatKind(space='outside',   tension=.55, label="on sort"),
    'nightfall':    BeatKind(space='night',     tension=.50, label="la nuit tombe"),
}

# Detection automatique : lexique FR, insensible aux accents et a la casse. Premier beat trouve par
# ligne, dans l'ordre de priorite ci-dessous (le plus specifique d'abord).
LEXICON = (
    ('dead_silence', ('plus aucun bruit', 'plus un bruit', 'plus un son', 'silence total', 'silence absolu',
                      'aucun bruit', 'le silence se fait')),
    ('door_close',   ('porte se referme', 'porte se ferme', 'porte claque', 'refermes la porte',
                      'referme la porte', 'claque la porte')),
    ('door_open',    ('porte ouverte', "porte s'ouvre", 'ouvres la porte', 'ouvre la porte', 'porte beante')),
    ('threat_run',   ('se met a courir', 'se mettent a courir', 'se precipite', 'court vers', 'fonce vers',
                      'se jette sur', 'commence a courir')),
    ('grab',         ('tu attrapes', 'tu projettes', 'tu pousses', 'attrape', 'projette', 'empoigne',
                      'saisit', 'repousse')),
    ('threat_near',  ("s'approche", 's approche', 'a quelques metres', 'face a la creature', 'face a elle',
                      'incline lentement la tete', 'juste derriere toi', 'tout pres')),
    ('go_outside',   ('tu sors', 'vous sortez', 'dehors', 'dans la rue')),
    ('nightfall',    ('la nuit tombe', 'il fait nuit')),
    ('calm',         ('tu respires', 'tout redevient', 'enfin calme')),
)

def _norm(s):
    """minuscules sans accents, didascalies [tense] / (a part) retirees"""
    s = unicodedata.normalize('NFD', (s or '').lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', re.sub(r'[\[\(][^\]\)]*[\]\)]', ' ', s))

def detect(texts):
    """beats deduits du script : [{'kind', 'line', 'text'}], au plus un par replique. Deterministe."""
    out = []
    for i, raw in enumerate(texts or []):
        t = _norm(raw)
        if not t: continue
        for kind, keys in LEXICON:
            if any(k in t for k in keys):
                out.append(dict(kind=kind, line=i, text=(raw or '').strip())); break
    return out

# ------------------------------------------------------------------ evenements sonores d'un beat
# Un beat produit 0..n cues, placees par rapport a la replique (jamais en absolu) : si la voix est
# reenregistree et que les timings bougent, le son reste synchrone. 5 sons d'evenement en tout,
# tous deja presents dans la banque (bruitage CC0 quand la cle en a un, synthese sinon).
def _cues_door_close(b, sp):
    return [dict(name='door_slam', line=b['line'], anchor='end', offset=.06, gain=1.15, pan=-.18, snap=True,
                 why="la porte claque juste apres la replique qui la dit")]

def _cues_threat_run(b, sp, steps=7):
    # la creature arrive de derriere-droite et se rapproche : le pas monte en niveau et revient au centre.
    # Une course a un tempo : ces pas ne sont PAS recales sur les trous de narration, ils garderaient
    # leur rythme de toute facon (snap=False) ; ils passent sous la voix, que le ducking garde devant.
    out = []
    for i in range(steps):
        f = i / (steps - 1)
        out.append(dict(name='step_hard', line=b['line'], anchor='start', offset=round(1.05 + .215 * i, 3),
                        gain=round(.60 + .70 * f, 3), pan=round(.62 * (1 - f) ** 1.4, 3),
                        why="un pas de course, de plus en plus proche, de la droite vers le centre"))
    return out

def _cues_grab(b, sp):
    return [dict(name='cloth', line=b['line'], anchor='start', offset=.42, gain=1.05, pan=.12,
                 why="froissement de vetement sur le geste"),
            dict(name='step_hard', line=b['line'], anchor='start', offset=.66, gain=.80, pan=-.25,
                 why="appui au sol pendant le geste")]

def _cues_dead_silence(b, sp):
    # Dans le creux, une seule goutte tres lointaine : c'est elle qui fait entendre le vide. Placee
    # juste apres la replique, dans le trou de narration ou le fond est deja coupe : c'est le seul
    # endroit du mix ou un son aussi discret s'entend parfaitement.
    return [dict(name='drip', line=b['line'], anchor='end', offset=.18, gain=.55, pan=-.55, reverb=.85, snap=True,
                 why="une goutte lointaine, seule, pour donner la taille du vide")]

def _cues_threat_near(b, sp):
    return [dict(name='growl', line=b['line'], anchor='start', offset=-.25, gain=.75, pan=.20, dur=1.8,
                 why="grognement bas, anticipe sur la replique")]

CUE_RULES = {'door_close': _cues_door_close, 'threat_run': _cues_threat_run, 'grab': _cues_grab,
             'dead_silence': _cues_dead_silence, 'threat_near': _cues_threat_near}

# ------------------------------------------------------------------ presets reutilisables
# Un preset = un point de depart (espace, tension) par genre : aucune intervention par episode.
PRESETS = {
    'horror_indoor': dict(space='corridor', tension=.50),
    'horror_street': dict(space='street',   tension=.40),
    'calm':          dict(space='corridor', tension=.25),
}

def pick_preset(ep):
    """preset choisi sur l'episode (musique / style), jamais a la main"""
    if (ep.get('music') or 'horror') != 'horror': return 'calm'
    return 'horror_indoor'

# ------------------------------------------------------------------ trous de narration
# La narration est prioritaire : le mixeur attenue deja les bruitages de ~11 dB quand la voix parle.
# Un son bref et important (une porte qui claque) gagne a tomber dans un trou de la narration plutot
# qu'a lutter contre elle. On ne deplace QUE les cues marquees snap, et de moins d'une demi-seconde :
# la cause reste lisible, et on ne touche ni au niveau de la voix ni au ducking.
def narration_gaps(lines, floor=.20):
    """[(debut, fin)] des silences de la narration, segments ElevenLabs quand ils existent"""
    segs = []
    for l in lines:
        for a, b in (l.get('segs') or [[l['start'], l['end']]]): segs.append((float(a), float(b)))
    segs.sort()
    gaps, prev = [], 0.
    for a, b in segs:
        if a - prev >= floor: gaps.append((prev, a))
        prev = max(prev, b)
    gaps.append((prev, prev + 1e4))
    return gaps

# Le mixeur attenue les bruitages de ~15 dB des que la narration parle (sduck = 1 - .82 * enveloppe
# de la voix, mesure : 0.18 en parole continue, 1.0 dans les trous). Un evenement qui DOIT tomber
# pendant une replique (les pas d'une course ont un tempo, on ne les deplace pas) serait donc inaudible
# au niveau naturel. On le compense de ~13 dB : il redevient present, et reste quand meme sous la voix,
# que le ducking, le compresseur de voix et le loudnorm gardent devant. Les sons places dans un trou
# ne sont pas compenses : ils y sont deja au niveau plein.
DUCK_COMPENSATION = 4.5

def in_gap(t, gaps, need=.12):
    """vrai si t tombe dans un trou de narration assez large pour y poser un son"""
    return any(a <= t <= b - min(need, (b - a) / 2) for a, b in gaps)

def _snap(t, gaps, taken, back=.25, fwd=.50, pad=.05):
    """recale t dans le trou de narration le plus proche ; (t, False) si aucun ne convient"""
    best = None
    for a, b in gaps:
        if b - a < 2 * pad or (a, b) in taken: continue
        c = min(max(t, a + pad), b - pad)                 # au plus pres de t, a l'interieur du trou
        d = c - t
        if -back <= d <= fwd and (best is None or abs(d) < abs(best[1])): best = ((a, b), d, c)
    if best is None: return t, False
    taken.add(best[0])
    return round(best[2], 3), True

# ------------------------------------------------------------------ plan
@dataclass
class Plan:
    zones: list = field(default_factory=list)       # [{'space','ambience','shots':(a,b),'t':(t0,t1)}]
    tension: list = field(default_factory=list)     # [{'shot','value','t','why'}]
    silences: list = field(default_factory=list)    # [{'shot','start','end','floor','t'}]
    cues: list = field(default_factory=list)        # cues resolues (avec 't' absolu, pour le rapport)
    beats: list = field(default_factory=list)
    preset: str = ''
    ambience_gain: float = AMBIENCE_GAIN

    # --- n'ecrit que ce que le mixeur lit deja, et rien d'autre
    def apply(self, ep):
        """episode enrichi : ambiances, intensites, silences et cues AJOUTEES (rien n'est ecrase)"""
        out = copy.deepcopy(ep)
        shots = out['shots']
        if self.zones and out.get('ambience_gain') is None:    # une valeur ecrite a la main gagne
            out['ambience_gain'] = self.ambience_gain
        for z in self.zones:
            for k in range(z['shots'][0], z['shots'][1] + 1):
                if k < len(shots): shots[k].setdefault('audio', {})['ambience'] = z['ambience']
        for s in self.tension:
            if s['shot'] < len(shots): shots[s['shot']].setdefault('audio', {})['intensity'] = s['value']
        for s in self.silences:
            if s['shot'] >= len(shots): continue
            a = shots[s['shot']].setdefault('audio', {})
            a['silence'] = True; a['silence_start'] = s['start']
            a['silence_end'] = s['end']; a['silence_floor'] = s['floor']
        for c in self.cues:
            k = c['shot']
            if k >= len(shots): continue
            cue = {x: c[x] for x in ('name', 'line', 'anchor', 'offset', 'gain', 'pan', 'reverb', 'dur')
                   if c.get(x) is not None}
            shots[k].setdefault('sfx', []).append(cue)
        return out

    def storyboard(self):
        """storyboard causal, lisible : ce que l'on entend, quand, et pourquoi"""
        rows = []
        for z in self.zones:
            rows.append((z['t'][0], f"ESPACE  {SPACES[z['space']]['label']} -> lit d'ambiance \"{z['ambience']}\" "
                                    f"(plans {z['shots'][0]}-{z['shots'][1]}, {z['t'][0]:.1f}-{z['t'][1]:.1f} s)"))
        for b in self.beats:
            rows.append((b['t'], f"BEAT    {b['kind']} : {BEATS[b['kind']].label}  \"{b['text'][:58]}\""))
        for s in self.tension:
            rows.append((s['t'], f"TENSION {s['value']:.2f}  ({s['why']})"))
        for s in self.silences:
            rows.append((s['t'], f"SILENCE fond coupe a {s['floor']:.2f} pendant {s['end'] - s['start']:.1f} s"))
        for c in self.cues:
            rows.append((c['t'], f"SON     {c['name']:<11} t={c['t']:6.2f}s gain={c['gain']:.2f} "
                                 f"pan={c['pan']:+.2f} rev={c.get('reverb', .4):.2f}"
                                 f"{' [cale dans un trou de narration]' if c.get('snapped') else ''}  {c['why']}"))
        return '\n'.join(txt for _, txt in sorted(rows, key=lambda r: r[0]))

def _line_shot_map(ep, nshots):
    m = {}
    for k, s in enumerate(ep['shots'][:nshots]):
        a, b = s.get('lines', [0, 0])
        for i in range(a, b + 1): m.setdefault(i, k)
    return m

def plan(ep, lines, spans, script=None, beats=None, preset=None):
    """PLAN sonore d'un episode. `beats` explicites (contrat d'integration) sinon detectes dans
    `script` (liste de textes alignee sur `lines`), sinon sur les textes portes par `lines`."""
    nshots = len(spans)
    if beats is None:
        texts = script if script is not None else [l.get('text', '') for l in lines]
        beats = detect(texts)
    name = preset or pick_preset(ep)
    pr = PRESETS.get(name, PRESETS['horror_indoor'])
    l2s = _line_shot_map(ep, nshots)
    last_line = max((s.get('lines', [0, 0])[1] for s in ep['shots'][:nshots]), default=0)

    bs = []
    for b in beats:
        li = int(b.get('line', 0))
        if li > last_line or li >= len(lines) or b.get('kind') not in BEATS: continue
        ln = lines[li]
        bs.append(dict(kind=b['kind'], line=li, shot=l2s.get(li, 0), text=b.get('text', ''),
                       t=float(ln['start']), t_end=float(ln['end'])))
    bs.sort(key=lambda b: b['t'])
    kept, last = [], {}                      # cooldown : le meme beat qui se prolonge ne rejoue pas
    for b in bs:
        k = b['kind']
        if k in last and b['t'] - last[k] < BEATS[k].cooldown: continue
        last[k] = b['t']; kept.append(b)
    bs = kept

    p = Plan(beats=bs, preset=name)

    # --- espaces : on part du preset, chaque beat qui deplace l'action ouvre une zone
    cuts = [dict(space=pr['space'], shot=0)]
    for b in bs:
        sp = BEATS[b['kind']].space
        if not sp or sp == cuts[-1]['space']: continue
        if b['shot'] > cuts[-1]['shot']: cuts.append(dict(space=sp, shot=b['shot']))
        elif len(cuts) == 1: cuts[0]['space'] = sp      # un beat sur le plan 0 remplace l'espace de depart
    for i, c in enumerate(cuts):
        a = c['shot']; z = (cuts[i + 1]['shot'] - 1) if i + 1 < len(cuts) else nshots - 1
        if z < a: continue
        p.zones.append(dict(space=c['space'], ambience=SPACES[c['space']]['ambience'], shots=(a, z),
                            t=(float(spans[a][0]), float(spans[z][1]))))
    space_of = {}
    for z in p.zones:
        for k in range(z['shots'][0], z['shots'][1] + 1): space_of[k] = z['space']

    # --- tension : une cible par beat, le mixeur interpole entre les plans (intensity_curve)
    for b in bs:
        v = BEATS[b['kind']].tension
        if v is None: continue
        if p.tension and p.tension[-1]['shot'] == b['shot']:
            p.tension[-1].update(value=v, why=BEATS[b['kind']].label)
        else:
            p.tension.append(dict(shot=b['shot'], value=v, t=float(spans[b['shot']][0]),
                                  why=BEATS[b['kind']].label))

    # --- silences anormaux : le creux tient sur la replique qui le dit et sur la suivante
    for b in bs:
        f = BEATS[b['kind']].silence
        if f is None: continue
        s0, s1 = spans[b['shot']]
        p.silences.append(dict(shot=b['shot'], start=round(max(0., b['t'] - s0 - .15), 3),
                               end=round(s1 - s0, 3), floor=f, t=float(b['t'])))
        if b['shot'] + 1 < nshots:
            n0, n1 = spans[b['shot'] + 1]
            p.silences.append(dict(shot=b['shot'] + 1, start=0., end=round(n1 - n0, 3), floor=f, t=float(n0)))

    # --- evenements, reverberes et doses selon l'espace ou ils tombent
    gaps, taken = narration_gaps(lines), set()
    for b in bs:
        rule = CUE_RULES.get(b['kind'])
        if not rule: continue
        sp = SPACES[space_of.get(b['shot'], pr['space'])]
        for c in rule(b, sp):
            ln = lines[c['line']]
            base = float(ln['end'] if c.get('anchor') == 'end' else ln['start'])
            t = base + float(c.get('offset', 0.))
            snapped = False
            if c.pop('snap', False): t, snapped = _snap(t, gaps, taken)
            free = in_gap(t, gaps)                                 # dans un trou : niveau naturel
            c = dict(c, shot=b['shot'], beat=b['kind'], snapped=snapped, in_gap=free,
                     reverb=round(c.get('reverb', sp['reverb']), 3),
                     gain=round(c['gain'] * sp['gain'] * (1. if free else DUCK_COMPENSATION), 3),
                     offset=round(t - base, 3), t=round(t, 3))     # l'offset reste relatif a la replique
            p.cues.append(c)
    p.cues.sort(key=lambda c: c['t'])
    return p
