"""Reading script.txt, the narration as the owner writes it.

    # rythme appel 1.06        a new VOICE PART starts here, generated at speed 1.06 (ElevenLabs: 0.7 to 1.2)
    [serious]                  an ElevenLabs tag alone on its line: the tone of what follows (it is sent to the voice)
    À deux heures treize du matin, le téléphone de la chambre 313 se met à sonner.

    Tu fixes l'écran.
    # coupe                    a Short (9:16 part) MAY begin at the next phrase: put it after a moment of suspense
    Une femme murmure :

Every other line that starts with « # » is a comment: never read aloud, never billed. One phrase = one line of text
(a paragraph); the blank lines between them are kept in what is sent, as in « Chambre 313 »."""
import re
from .common import KitError

TAG_LINE = re.compile(r'^\s*\[([^\]]+)\]\s*$')
RYTHME = re.compile(r'^#\s*rythme\s+(\S+)\s+([0-9]+(?:[.,][0-9]+)?)\s*$', re.I)
COUPE = re.compile(r'^#\s*coupe\b', re.I)
SPEED_MIN, SPEED_MAX = .7, 1.2


def clean(s):
    return re.sub(r'\s+', ' ', re.sub(r'\[[^\]]*\]', '', s)).strip()


def parse(path, default_speed=1.06):
    """-> dict(parts=[{name, speed, text, chars, phrases: [indices]}], phrases=[{text, tone, part, coupe}], warnings=[])"""
    try:
        raw = open(path, encoding='utf-8-sig').read()
    except UnicodeDecodeError:
        raise KitError(f"{path} n'est pas en UTF-8 : enregistre-le en UTF-8.")
    parts, phrases, warns = [], [], []
    cur = dict(name='debut', speed=float(default_speed), lines=[], phrases=[]); tone = 'neutre'; coupe_next = False
    for n, line in enumerate(raw.splitlines(), 1):
        s = line.strip()
        if s.startswith('#'):
            m = RYTHME.match(s)
            if m:
                sp = float(m.group(2).replace(',', '.'))
                if not SPEED_MIN <= sp <= SPEED_MAX:
                    raise KitError(f'script.txt ligne {n} : vitesse {sp} hors de [{SPEED_MIN}, {SPEED_MAX}] (limite ElevenLabs)')
                if cur['lines'] or cur['phrases']: parts.append(cur)
                cur = dict(name=m.group(1), speed=sp, lines=[], phrases=[])
            elif COUPE.match(s):
                coupe_next = True
            elif s.lower().startswith('# rythme'):
                raise KitError(f'script.txt ligne {n} : écris « # rythme NOM VITESSE », par exemple « # rythme urgence 1.13 »')
            continue
        cur['lines'].append(line.rstrip())
        t = TAG_LINE.match(s)
        if t: tone = t.group(1); continue
        c = clean(s)
        if not c: continue
        lt = re.match(r'^\s*\[([^\]]+)\]', s)
        cur['phrases'].append(len(phrases))
        phrases.append(dict(text=c, tone=lt.group(1) if lt else tone, part=cur['name'], coupe=coupe_next, script_line=n))
        coupe_next = False
    if cur['lines'] or cur['phrases']: parts.append(cur)
    out = []
    for p in parts:
        txt = '\n'.join(p['lines']).strip()
        if not p['phrases']:
            if txt: warns.append(f"partie de voix « {p['name']} » sans phrase : ignorée")
            continue
        out.append(dict(name=p['name'], speed=p['speed'], text=txt, chars=len(txt), phrases=p['phrases']))
    names = [p['name'] for p in out]
    for nm in sorted({x for x in names if names.count(x) > 1}): warns.append(f'nom de partie de voix « {nm} » répété : les fichiers seront numérotés quand même')
    if coupe_next: warns.append('« # coupe » à la fin du script : ignoré (aucune phrase après)')
    if not phrases: raise KitError(f'{path} : aucune phrase (une phrase = une ligne de texte)')
    if phrases[0]['coupe']: phrases[0]['coupe'] = False
    return dict(parts=out, phrases=phrases, warnings=warns)
