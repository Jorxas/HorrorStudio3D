"""The jaw and the lips of a speaking face, as data: from the voice itself when it is known, from the text when it is not.

What the first engine did: the mouth followed the REAL envelope of the voice (30 values per second, `engines/pixel3d/frame.py` `ctx.mouth`), opening on a vowel and
closing on silence. The voxel painter instead babbles a sinusoid whenever `talk` is on (voxelgpu_js/engine/chars4.js): the mouth moves for as long as the line
lasts, whatever is said, and is never closed on a pause or a bilabial. This module restores what the first engine had and adds what it did not:

  * ENVELOPE  `Envelope(values, hz)`: the voice's amplitude (the same 30 Hz table the first engine's mixer produces) -> jaw opening, with a fast attack (35 ms) and a
              slower release (75 ms), a floor under which the mouth is closed (breath, room tone), and emphasis marks where a stressed syllable follows a pause;
  * TEXT      `from_text(text, t0, t1)`: no audio yet (the draft stage): French syllables from the vowel groups of the line, an opening per vowel (a wide, o / ou
              rounded, i narrow), a lip closure before m / b / p, pauses on punctuation, the total spread over the line's real duration, so the mouth is at least
              consistent with what is said and silent where the line is silent.

Both give the same thing: `Mouth.at(t) -> (open 0..1, pressed 0..1, emphasis 0..1)`. faceact.py turns it into the painter's columns. Deterministic; no clock, no randomness.
"""
import json, math, re
from pathlib import Path

ATTACK, RELEASE = .035, .075          # s: the jaw opens faster than it closes
FLOOR = .07                           # envelope under which the mouth stays shut
VOWELS = 'aeiouyàâäéèêëîïôöùûüœ'
OPEN = {'a': .95, 'à': .95, 'â': .95, 'ä': .9, 'o': .7, 'ô': .7, 'œ': .6, 'u': .45, 'ù': .45, 'û': .45, 'ü': .4, 'e': .5, 'é': .5, 'è': .7, 'ê': .7, 'ë': .55, 'i': .35, 'î': .35, 'ï': .35, 'y': .35}
PAUSE = {',': 1.4, ';': 1.6, ':': 1.4, '.': 2.4, '!': 2.4, '?': 2.4, '…': 3., '—': 1.4, '-': .0}
SYLLABLE = re.compile(r'([bcdfghjklmnpqrstvwxzç\']*)([' + VOWELS + r']+)([bcdfghjklmnpqrstvwxzç]*)', re.I)


def _sm(k): k = max(0., min(1., k)); return k * k * (3 - 2 * k)


class Mouth:
    """a mouth track: `at(t)` -> (open, pressed, emphasis); built from an envelope or from text, never both"""

    def __init__(self, spans, kind): self.spans = spans; self.kind = kind; self._t = [s[0] for s in spans]

    def at(self, t):
        o = p = e = 0.
        for (a, b, lvl, press, emph) in self.spans:
            if t < a - .12: break
            if t > b + .2: continue
            if lvl > 0:                                         # a syllable / a voiced stretch: attack, hold, release
                up = _sm((t - a) / ATTACK); down = 1. - _sm((t - b) / RELEASE)
                o = max(o, lvl * up * down)
            if press > 0 and a - .07 <= t < a: p = max(p, press * _sm((t - (a - .07)) / .05))          # the lips close just before a bilabial burst
            if emph > 0 and a <= t <= a + .25: e = max(e, emph * (1. - _sm((t - a) / .25)))
        return o, p, e


def from_envelope(values, hz=30., t0=0., gain=1., silence=.35):
    """Mouth from the voice's amplitude table (0..1, `hz` values per second, starting at `t0`). A stretch above FLOOR is a voiced span whose opening follows the
    envelope; the first span after at least `silence` seconds of quiet carries an emphasis mark (the brow flicks on a stressed beginning)."""
    spans = []; n = len(values); i = 0; last_end = -9.
    while i < n:
        if values[i] > FLOOR:
            j = i; peak = 0.
            while j < n and values[j] > FLOOR: peak = max(peak, values[j]); j += 1
            # one span per local rise inside a long voiced stretch, so a sentence does not become one open mouth
            k0 = i
            for k in range(i + 1, j):
                if values[k] < .55 * max(values[k0:k] or [0.]) and values[k] <= values[k - 1] and (k + 1 >= j or values[k + 1] > values[k]):
                    spans.append(_span(values, k0, k, hz, t0, gain, silence, last_end)); last_end = t0 + k / hz; k0 = k
            spans.append(_span(values, k0, j, hz, t0, gain, silence, last_end)); last_end = t0 + j / hz; i = j
        else: i += 1
    return Mouth(spans, 'envelope')


def _span(values, i, j, hz, t0, gain, silence, last_end):
    a, b = t0 + i / hz, t0 + j / hz; seg = values[i:j]; lvl = min(1., gain * (sum(seg) / len(seg)) * 1.25 + .1 * max(seg))
    return (a, b, max(.12, lvl), 0., (.6 + .4 * lvl) if a - last_end >= silence else 0.)


def from_text(text, t0, t1, gain=1.):
    """Mouth from a French line spread over [t0, t1]: syllables from the vowel groups, an opening per vowel, a lip closure before m / b / p, pauses on punctuation"""
    words = re.findall(r"[\wÀ-ÿ'’]+|[,;:.!?…—]", text.lower()); items = []                 # ('syl', open, bilabial) | ('pause', weight)
    for w in words:
        if w in PAUSE: items.append(('pause', PAUSE[w])); continue
        sy = SYLLABLE.findall(w)
        if not sy: items.append(('syl', .4, False)); continue
        for k, (onset, vow, coda) in enumerate(sy):
            v = vow[0]; lvl = OPEN.get(v, .5)
            if len(vow) > 1 and vow[:2] in ('ou', 'eu', 'au', 'eau'): lvl = .55
            if k == len(sy) - 1 and v == 'e' and len(sy) > 1 and not coda: lvl = .0                  # a mute final e does not open the jaw
            items.append(('syl', lvl, bool(onset) and onset[-1] in 'mbp'))
        items.append(('gap', .35))
    total = sum(1. if it[0] == 'syl' else it[1] for it in items) or 1.; unit = (t1 - t0) / total; t = t0; spans = []; after_pause = True
    for it in items:
        if it[0] == 'syl':
            a, b = t, t + unit * .78
            if it[1] > 0: spans.append((a, b, min(1., it[1] * gain), .7 if it[2] else 0., .8 if after_pause else 0.))
            t += unit; after_pause = False
        else:
            t += unit * it[1]; after_pause = it[0] == 'pause'
    return Mouth(spans, 'text')


def load_envelope(spec):
    """an envelope given in a plan: a list, a path to a .json list (or {'env': [...], 'hz': ...}), or a dict {envelope, hz, t0, gain} -> (values, hz, t0, gain)"""
    hz = 30.; t0 = 0.; gain = 1.; v = spec
    if isinstance(spec, dict):
        hz = float(spec.get('hz', 30.)); t0 = float(spec.get('t0', 0.)); gain = float(spec.get('gain', 1.)); v = spec.get('envelope', spec.get('env'))
    if isinstance(v, (str, Path)):
        d = json.loads(Path(v).read_text(encoding='utf-8'))
        if isinstance(d, dict): hz = float(d.get('hz', hz)); v = d.get('env', d.get('envelope'))
        else: v = d
    return [float(x) for x in v], hz, t0, gain


def track_for(A, duration):
    """the mouth track of an actor, or None: its plan spec `lipsync` = {'envelope': [...] | path, 'hz', 't0', 'gain'} (the voice), or True / {'text': True} (the text of its
    `talk` beats, `text` key). With neither, the painter's own babble keeps running (nothing changes)."""
    ls = A.spec.get('lipsync')
    if not ls: return None
    if isinstance(ls, dict) and (ls.get('envelope') is not None or ls.get('env') is not None):
        vals, hz, t0, gain = load_envelope(ls)
        m = from_envelope(vals, hz, t0, gain)
        # outside the actor's talk windows the mouth stays shut whatever the track says (an envelope also contains the other speakers)
        if A.talk: m.spans = [s for s in m.spans if any(a - .15 <= s[0] <= b + .15 for a, b in A.talk)]
        return m
    spans = []; gain = float(ls.get('gain', 1.)) if isinstance(ls, dict) else 1.
    for (a, b, text, loud) in getattr(A, 'talk_info', []):
        if text: spans += from_text(text, a, b, gain).spans
    return Mouth(spans, 'text') if spans else None
