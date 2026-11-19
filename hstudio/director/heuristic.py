"""Offline director (no AI, free, instant): keyword rules -> episode JSON.
It gives a correct, watchable video; an AI director (Claude / Gemini / local model) gives a far better one."""
import re
from ..engines.common import norm

STOP = set('''le la les un une des de du d l au aux et ou mais donc or ni car que qui quoi dont où a à en dans sur sous par pour avec sans
ce cet cette ces son sa ses ton ta tes mon ma mes notre votre leur leurs tu te toi vous il elle ils elles on je me moi nous se lui y
ne pas plus est es suis sont était être avoir as ai ont fait faire comme si alors puis encore très trop tout tous toute toutes
même quand quelque quelques chose rien bien aussi c s n j m t qu cest'''.split())

def pick_keyword(text):
    ws = [w for w in re.findall(r"[\wÀ-ÿ'-]+", text)]
    cands = [w for w in ws if norm(w) not in STOP and len(norm(w)) > 3]
    if not cands: return []
    pri = ['double', 'miroir', 'reflet', 'porte', 'portes', 'sortie', 'créature', 'monstre', 'jamais', 'seul', 'mort', 'sang', 'cours',
           'sors', 'pause', 'console', 'chambre', 'téléphone', 'message', 'zéro', 'toujours', 'personne', 'voix', 'pas']
    for p in pri:
        for w in cands:
            if norm(w) == norm(p): return [w]
    return [max(cands, key=lambda w: len(w))]

def has(t, *words): return any(re.search(r'\b' + w, t) for w in words)

def choice_text(t):
    t = re.sub(r'(?i)^\s*choix\s*[ab]\s*[:\-]\s*', '', t).strip().rstrip('.!?…')
    ws = t.upper().split()
    l1, l2 = [], []
    for w in ws:
        if len(' '.join(l1 + [w])) <= 12 and not l2: l1.append(w)
        elif len(' '.join(l2 + [w])) <= 12: l2.append(w)
    return [' '.join(l1), ' '.join(l2)]

def common_meta(lines):
    meta = {}; choiceA = choiceB = None
    for i, l in enumerate(lines):
        m = {'keywords': pick_keyword(l['text'])}
        meta[str(i)] = m
        t = l['text'].lower()
        if re.match(r'\s*choix\s*a', t): choiceA = choice_text(l['text'])
        if re.match(r'\s*choix\s*b', t): choiceB = choice_text(l['text'])
    return meta, choiceA, choiceB

def pixel3d(lines, project):
    meta, cA, cB = common_meta(lines)
    shots = []; loc = 'cabin'; z = -1.2; recent_other = None; prev_choice = project.get('previous_choice')
    n = len(lines); hz = 2.0; intensity = .6
    for i, l in enumerate(lines):
        t = l['text'].lower(); m = meta[str(i)]; s = {'lines': [i, i]}
        if has(t, 'ascenseur', 'cabine', 'bouton', 'miroir'): loc = 'cabin'
        if has(t, 'couloir', 'sortie', 'escalier', 'cour'): loc = 'corridor'
        if has(t, 'double'): recent_other = 'double'
        if has(t, 'créature', 'creature', 'monstre', 'chose', 'silhouette', 'troisième'): recent_other = 'creature'
        if loc == 'corridor': hz = min(16.5, hz + 16.0 / max(8, n))
        hero = [0, -1.2] if loc == 'cabin' else [0, hz]
        if i == 0 and prev_choice and re.search(r'choisi', t):
            letter = (re.findall(r'\b([AB])\b', l['text']) or [prev_choice[:1]])[0]
            s.update(camera={'preset': 'wide', 'from': [0, hero[1] + 3.0], 'target': [0, 1.5, hero[1]], 'fov': 78, 'shake': .05},
                     actors=[{'id': 'hero', 'at': hero, 'face': 'scared', 'facing': '+z'}],
                     ui={'recap': {'title': 'TON CHOIX :', 'letter': letter, 'text': choice_text(project.get('previous_choice_text', prev_choice))}})
        elif i == n - 1:
            s.update(camera={'preset': 'wide', 'from': [0, 4], 'target': [0, 1.5, 9]}, fx={'black': True},
                     ui={'endcard': {'part': project.get('part_label', ''), 'headline': 'FIN' if has(t, 'fin') and len(t) < 8 else 'A OU B ?'}},
                     sfx=[{'name': 'boom', 'at': 0, 'gain': .7}])
        elif re.match(r'\s*(choix\s*[ab]|a\.\.\.|a ou b)', t) or (cA and cB and i > n - 6 and has(t, 'choix', 'choisir', 'décide')):
            s.update(camera={'preset': 'closeup', 'subject': 'hero', 'fov': 48}, actors=[{'id': 'hero', 'at': hero, 'face': 'scared'}],
                     ui={'choice': {'title': 'QUE FAIS-TU ?', 'A': cA or ['A', ''], 'B': cB or ['B', '']}}, fx={'dim': .25})
        elif l.get('dialogue') and recent_other:
            who = recent_other; m['label'] = 'TON DOUBLE' if who == 'double' else 'LA CRÉATURE'
            m['label_color'] = 'blue' if who == 'double' else 'red'; m['voice_fx'] = 'double' if who == 'double' else 'creature'
            at = [0, hero[1] + 1.4] if loc == 'corridor' else [0, -.2]
            s.update(camera={'preset': 'closeup', 'subject': who, 'fov': 50, 'shake': .05},
                     actors=[{'id': who, 'at': at, 'facing': 'camera', 'face': 'double' if who == 'double' else 'creature', 'lipsync': True}],
                     state={'red': .4} if who == 'creature' else {})
        elif l.get('dialogue'):
            m['label'] = 'TOI'; m['label_color'] = 'cream'
            s.update(camera={'preset': 'closeup', 'subject': 'hero', 'fov': 50}, actors=[{'id': 'hero', 'at': hero, 'face': 'urgent', 'lipsync': True}])
        elif has(t, 'téléphone', 'telephone', 'message', 'écran', 'vibre', 'sms', 'notification'):
            s.update(camera={'preset': 'pov', 'from': hero, 'target': [hero[0], .4, hero[1] + 4], 'fov': 66},
                     objects=[{'type': 'phone', 'header': 'INCONNU', 'messages': [l['text'].upper()[:60]], 'vibrate': 1 if has(t, 'vibre') else 0}],
                     ui={'subs': 'low'}, sfx=[{'name': 'phone_vibrate' if has(t, 'vibre') else 'notification', 'at': .2, 'gain': .6}])
        elif has(t, 'miroir', 'reflet'):
            s.update(set='etage_zero', camera={'preset': 'free', 'keys': [{'pos': [.3, 1.65, -.4], 'look': [0, 1.5, -2.4], 'fov': 70}, {'pos': [.2, 1.65, -.8], 'look': [0, 1.55, -2.4], 'fov': 64}]},
                     actors=[{'id': 'hero', 'at': [0, -1.3], 'facing': '-z', 'face': 'scared'}], state={'mirror': 'writing', 'crack': .6 if has(t, 'fissur') else .45},
                     sfx=[{'name': 'glass_crack', 'at': .3, 'gain': .7}] if has(t, 'fissur', 'brise', 'verre') else [])
        elif has(t, 'cour', 'fuis', 'fuir', 'courir', 'tire'):
            s.update(camera={'preset': 'pov', 'from': hero, 'target': [0, 1.5, 18], 'move': 'dolly_in', 'amount': 1.5, 'walk_bob': .03, 'shake': .2},
                     actors=([{'id': 'double', 'at': [0, hero[1] + 1.8], 'to': [0, hero[1] + 4], 'move': 'run', 'facing': '+z', 'face': 'urgent'}] if recent_other == 'double' else []),
                     sfx=[{'name': 'footsteps_run', 'at': 0, 'dur': 2.5, 'gain': .6}]); intensity = .95
        elif has(t, 'créature', 'creature', 'monstre', 'chose', 'visage', 'sourire', 'troisième', 'silhouette'):
            s.update(camera={'preset': 'closeup' if has(t, 'visage', 'sourire', 'yeux') else 'wide', 'subject': 'creature', 'fov': 46,
                             'from': [0, min(17, hz + 1.5)], 'target': 'creature.head'},
                     actors=[{'id': 'creature', 'at': [0, max(1, hz - 3)], 'facing': 'camera', 'face': 'creature', 'smile': 1 if has(t, 'sourire') else .8, 'crack': 1}],
                     state={'red': .6}, sfx=[{'name': 'sting', 'at': .2, 'gain': .6}, {'name': 'boom', 'at': .2, 'gain': .8}]); intensity = 1.
        elif has(t, 'porte', 'sortie'):
            if loc == 'cabin':
                s.update(camera={'preset': 'free', 'keys': [{'pos': [0, 1.55, -1.6], 'look': [0, 1.3, 2], 'fov': 90}]},
                         state={'elevator_doors': [0, .5] if has(t, 'ouvr', 'écart') else 0, 'door_judder': 1 if has(t, 'résist') else 0},
                         sfx=[{'name': 'metal_hit', 'at': .2, 'gain': .6}])
            else:
                s.update(camera={'preset': 'wide', 'from': [0, 16.2], 'target': 'exit_door', 'fov': 80},
                         state={'exit_door': [0, 1.05] if has(t, 'ouvr') else 0, 'lock': 'unlocked' if has(t, 'déverrouill') else 'locked'},
                         sfx=[{'name': 'lock_rattle' if has(t, 'verrouill', 'ferm') else 'door_open', 'at': .2, 'gain': .7}])
        elif has(t, 'bouton', 'appuie'):
            s.update(set='etage_zero', camera={'preset': 'free', 'keys': [{'pos': [.1, 1.15, -1.3], 'look': [1.0, 1.0, -1.3], 'fov': 85}]},
                     objects=[{'type': 'arm', 'target': [.86, .8, -1.25], 'time': .5}], sfx=[{'name': 'button', 'at': .4, 'gain': .8}])
        elif has(t, 'des pas', 'bruits? de pas', 'pas résonn', 'entend', 'résonn'):
            s.update(camera={'preset': 'wide', 'from': [0, hz], 'target': [0, 1.5, 0], 'fov': 84}, sfx=[{'name': 'footsteps_heavy', 'at': .1, 'dur': 2.5, 'gain': .5}])
        elif has(t, 'lumière', 'néon', 'noir', 'obscurité', 'éteign', 'éteint'):
            s.update(camera={'preset': 'wide', 'from': hero, 'target': [0, 2.2, hero[1] + 6], 'fov': 86},
                     state={'lights_off': [0, 1, 0, 2] if has(t, 'éteign', 'éteint') else 0, 'lights': 'flicker'}, sfx=[{'name': 'neon_buzz', 'at': .2, 'gain': .4}])
        elif has(t, 'silence', 'plus aucun bruit', 'soudain'):
            s.update(camera={'preset': 'pov', 'from': hero, 'target': [0, 1.6, 0], 'fov': 74}, audio={'silence': True, 'intensity': .2})
        else:
            k = i % 4
            if k == 0: s.update(camera={'preset': 'closeup', 'subject': 'hero', 'fov': 52, 'move': 'push_in', 'amount': .5}, actors=[{'id': 'hero', 'at': hero, 'face': 'scared'}])
            elif k == 1: s.update(camera={'preset': 'pov', 'from': hero, 'target': [0, 1.55, hero[1] + (6 if loc == 'corridor' else -3)], 'fov': 80, 'shake': .05})
            elif k == 2: s.update(camera={'preset': 'high_corner', 'from': [1.2, hero[1] + 2.5], 'target': [0, 1, hero[1]], 'fov': 90}, actors=[{'id': 'hero', 'at': hero, 'face': 'scared', 'facing': '+z'}])
            else: s.update(camera={'preset': 'ots', 'subject': 'hero', 'fov': 74}, actors=[{'id': 'hero', 'at': hero, 'face': 'scared', 'facing': '+z' if loc == 'corridor' else '-z'}])
        if loc == 'cabin' and 'set' not in s: s['set'] = 'etage_zero'
        s.setdefault('audio', {})['intensity'] = intensity
        shots.append(s)
    return {'style': 'pixel3d', 'default_set': 'etage_zero',
            'hud': {'title': [x.strip() for x in (project.get('hud_title') or "L'ÉTAGE 0|N'EXISTE PAS").split('|')], 'part': project.get('part_label', ''), 'hearts': [1, 1, 1]},
            'cast': {'hero': {}, 'double': {}, 'creature': {'kind': 'creature'}},
            'state': {'mirror': 'writing', 'elevator_doors': .5}, 'lines': meta, 'shots': shots,
            'summary': 'Mise en scène automatique (sans IA).'}

def console(lines, project):
    meta, cA, cB = common_meta(lines)
    shots = []; n = len(lines); rule_n = 0; prev_choice = project.get('previous_choice')
    for i, l in enumerate(lines):
        t = l['text'].lower(); m = meta[str(i)]; s = {'lines': [i, i]}
        if i == 0 and prev_choice and re.search(r'choisi', t):
            s.update(scene={'type': 'console', 'screen': {'type': 'menu', 'title': 'SAUVEGARDES', 'items': ['FICHIER 1'], 'cursor': 0, 'heart': 0}}, camera={'move': 'push_in'})
        elif i == n - 1:
            s.update(scene={'type': 'black'}, ui={'endcard': {'part': project.get('part_label', ''), 'headline': 'FIN' if has(t, 'fin') and len(t) < 8 else 'A OU B ?'}})
        elif re.match(r'\s*(choix\s*[ab]|qui crois)', t) or (cA and cB and i > n - 6 and has(t, 'choix', 'choisir', 'décide', 'crois')):
            s.update(scene={'type': 'door', 'light_under': 'warm', 'feet': True}, ui={'choice': {'title': 'QUI CROIS-TU ?', 'A': ' '.join(cA or ['A']), 'B': ' '.join(cB or ['B'])}})
        elif l.get('dialogue') and has(t, 'console', 'écran', 'jeu', 'pause', 'sauvegarde', 'joueur', 'niveau'):
            m.update(label='CONSOLE · FICHIER 1', label_color='green', voice_fx='console')
            s.update(scene={'type': 'screen', 'screen': {'type': 'text', 'speaker': 'CONSOLE', 'text': l['text'].strip('«»" ')}}, sfx=[{'name': 'chip_blip', 'at': 0, 'gain': .5}])
        elif l.get('dialogue'):
            m.update(label='VOIX DERRIÈRE LA PORTE', label_color='orange', voice_fx='muffled')
            s.update(scene={'type': 'door', 'light_under': 'orange', 'feet': True}, camera={'move': 'push_in'})
        elif has(t, 'règle'):
            rule_n += 1
            words = re.sub(r'(?i)règle\s*(numéro|n°)?\s*\w*\s*:?', '', l['text']).strip().upper().rstrip('.!')
            ws = words.split(); half = max(1, len(ws) // 2)
            s.update(scene={'type': 'rule_card', 'number': rule_n, 'lines': [' '.join(ws[:half]), ' '.join(ws[half:])], 'highlight': 1,
                            'icon': 'door_x' if has(t, 'porte', 'chambre', 'quitte') else 'eye_x' if has(t, 'regard', 'yeux') else 'console_x'},
                     sfx=[{'name': 'chip_alert', 'at': .1, 'gain': .5}])
        elif has(t, 'console', 'écran', 'manette', 'jeu', 'sauvegarde', 'pause'):
            s.update(scene={'type': 'console', 'screen': {'type': 'room' if has(t, 'chambre') else 'menu', 'figure': has(t, 'quelqu', 'silhouette')}}, camera={'move': 'push_in'})
        elif has(t, 'frapp', 'coup'):
            s.update(scene={'type': 'door', 'knock': [.2, .5, .8], 'light_under': 'warm'}, sfx=[{'name': 'knock', 'at': .2, 'gain': .9}])
        elif has(t, 'des pas', 'bruits? de pas', 'pas résonn', 'pieds', 'quelqu', 'ombre'):
            s.update(scene={'type': 'door', 'light_under': 'warm', 'feet': True, 'feet_move': has(t, 'bouge', 'march')}, sfx=[{'name': 'footsteps_walk', 'at': 0, 'dur': 2, 'gain': .4}])
        elif has(t, 'porte', 'poignée'):
            s.update(scene={'type': 'door', 'light_under': 'warm' if i % 2 else None, 'open': [0, .4] if has(t, 'ouvr') else 0}, sfx=[{'name': 'door_handle' if has(t, 'poignée') else 'creak', 'at': .3, 'gain': .6}])
        elif has(t, 'fenêtre', 'dehors'):
            s.update(scene={'type': 'window', 'silhouette': has(t, 'quelqu', 'silhouette', 'ombre')})
        elif has(t, 'souffle', 'peur', 'visage', 'regarde', 'yeux', 'cœur', 'coeur'):
            s.update(scene={'type': 'face', 'expression': 'scared' if not has(t, 'ferme') else 'closed', 'light': 'green'}, camera={'move': 'push_in'})
        elif has(t, 'lumière', 'noir', 'éteint', 'clignot'):
            s.update(scene={'type': 'room', 'figure': has(t, 'quelqu', 'silhouette')}, fx={'flicker': True})
        else:
            k = i % 3
            s.update(scene=[{'type': 'room'}, {'type': 'door', 'x': .55}, {'type': 'face', 'expression': 'wide', 'light': 'green'}][k],
                     camera={'move': ['drift', 'push_in', 'pan_right'][k]})
        shots.append(s)
    return {'style': 'console', 'hud': {'series': project.get('series', 'NE METS PAS PAUSE').upper(), 'level': project.get('part_label', 'NIVEAU 1'),
                                        'clock_start': '3:07', 'clock_rate': .125, 'hearts': [1, 1, 1]},
            'lines': meta, 'shots': shots, 'summary': 'Mise en scène automatique (sans IA).'}

GENRE_WORDS = {
    'horror': r"peur|terrif|sang|cr[ée]ature|monstre|fant[ôo]me|cri[s]?\b|hurle|mort|cadavre|miroir|ombre|t[ée]n[èe]bres|d[ée]mon",
    'comedy': r"rigol|dr[ôo]le|blague|ridicule|hilarant|[ée]clat\w* de rire|g[êe]nant|catastrophe",
    'romance': r"amour|amoureu|c[œo]eur|baiser|embrass|rendez-vous|coup de foudre|je t.aime",
    'adventure': r"tr[ée]sor|aventure|for[êe]t|carte|voyage|[ée]p[ée]e|dragon|qu[êe]te|montagne|[îi]le",
    'mystery': r"enqu[êe]te|indice|myst[èe]re|secret|disparu|d[ée]tective|suspect|[ée]nigme",
    'sad': r"triste|larme|pleur|adieu|perdu|manque|souvenir|seul[e]?\b",
    'action': r"course|poursuite|explosion|combat|fuir|sauter|vite|attaque|bagarre",
}
def genre_of(lines, project):
    if project.get('genre') in GENRE_WORDS: return project['genre']
    text = ' '.join(l['text'].lower() for l in lines)
    score = {g: len(re.findall(p, text)) for g, p in GENRE_WORDS.items()}
    score['horror'] *= 1.3                              # the channel's home genre wins ties
    g = max(score, key=score.get)
    return g if score[g] > 0 else 'horror'

# line text -> (expression, gesture, object): body language for the offline director
EMOTIONS = [
    (r"[ée]clat\w* de rire|rigol|\bri[ts]?\b|rient|ricane|mort de rire", 'joy', 'laugh', None),
    (r"pleur|larme|sanglot", 'crying', 'cover_face', None),
    (r"furieu|enrag|hors de (lui|toi|elle)", 'furious', None, None),
    (r"col[èe]re|[ée]nerv|agac", 'angry', 'cross_arms', None),
    (r"choqu|bouche b[ée]e|horrifi", 'shocked', 'hands_mouth', None),
    (r"surpri|[ée]tonn|stup[ée]fait|incroyable", 'surprised', None, None),
    (r"amoureu|coup de foudre|bisou|c[œo]eur (bat|s.emball)", 'love', 'hand_chest', None),
    (r"g[êe]n[ée]|rougi|timide", 'shy', 'hands_behind', None),
    (r"r[ée]fl[ée]chi|se demande|h[ée]sit", 'thinking', 'think', None),
    (r"fatigu|[ée]puis|b[âa]ill", 'tired', 'stretch', None),
    (r"\bdor[ts]\b|endormi|sommeil", 'sleeping', None, None),
    (r"salue|coucou|au revoir|fait signe", 'happy', 'wave', None),
    (r"applaudi", 'joy', 'clap', None),
    (r"\bdans[ea]\b|danser", 'joy', 'dance', None),
    (r"victoire|gagn[ée]|r[ée]ussi", 'excited', 'victory', None),
    (r"haus\w* les [ée]paules|je (ne )?sais pas", 'confused', 'shrug', None),
    (r"\bprie|pri[èe]re", 'calm', 'pray', None),
    (r"c[âa]lin|serre dans (ses|tes|mes) bras|enlace", 'happy', 'hug', None),
    (r"frappe [àa] la porte|toque", 'neutral', 'knock', None),
    (r"t[ée]l[ée]phone|appelle|d[ée]croche", 'neutral', 'phone', 'phone'),
    (r"tremble|grelott|froid", 'scared', 'shiver', None),
    (r"d[ée]go[ûu]t|beurk", 'disgusted', None, None),
    (r"m[ée]fi|suspicieu", 'suspicious', 'cross_arms', None),
    (r"ennui|ennuie", 'bored', 'pockets', None),
    (r"\bfi[eè]re?\b", 'proud', 'hands_hips', None),
    (r"d[ée]termin|courage", 'determined', None, None),
    (r"douleur|a[ïi]e\b|bless", 'pain', None, None),
    (r"nerveu|stress|angoiss", 'nervous', None, None),
    (r"souri|heureu|joie|content", 'happy', None, None),
    (r"montre|d[ée]signe|pointe", None, 'point', None),
    (r"lampe|torche", None, 'point', 'flashlight'),
]
HORROR_FACES = {'double', 'grin', 'creature'}

def act(ep, lines, genre):
    """give the actors a face / gesture / object that fits the words of their shot"""
    for s in ep.get('shots', []):
        a, b = s['lines']; t = ' '.join(lines[i]['text'].lower() for i in range(a, b + 1))
        hit = next(((f, g, h) for p, f, g, h in EMOTIONS if re.search(p, t)), None)
        if not hit: continue
        face, gest, item = hit
        preset = (s.get('camera') or {}).get('preset')
        for ac in s.get('actors') or []:
            if ac.get('face') in HORROR_FACES or (ep.get('cast', {}).get(ac.get('id'), {}) or {}).get('kind') == 'creature': continue
            if face: ac['face'] = face
            if gest and preset not in ('pov', 'insert') and not ac.get('to'): ac['gesture'] = gest
            if item and preset not in ('pov', 'insert'): ac['hold'] = item
            break
    return ep

MUSIC = {'horror': 'horror', 'comedy': 'comedy', 'romance': 'romance', 'adventure': 'adventure', 'mystery': 'mystery', 'sad': 'sad', 'action': 'action'}

PLACE_WORDS = [
    ('space_station', r"station spatiale|vaisseau|l.espace\b|fus[ée]e|astronaute"), ('graveyard', r"cimeti[èe]re|tombe"), ('castle', r"ch[âa]teau|royaume|chevalier|donjon"),
    ('throne_room', r"tr[ôo]ne"), ('volcano', r"volcan|lave"), ('island', r"\b[îi]le\b|naufrag"), ('beach', r"plage|\bmer\b|oc[ée]an|sable|vagues"),
    ('snowy_forest', r"for[êe]t enneig|sapins? (couverts|enneig)"), ('snow_village', r"village enneig|no[ëe]l"), ('forest', r"for[êe]t|\bbois\b|arbres"),
    ('mountain', r"montagne|sommet|falaise"), ('desert', r"d[ée]sert|dunes?"), ('campsite', r"camping|\btente\b|feu de camp"), ('lake', r"\blac\b|[ée]tang"),
    ('river', r"rivi[èe]re|fleuve|\bpont\b"), ('countryside', r"\bferme\b|campagne|\bchamps?\b"), ('village', r"village"), ('park', r"\bparc\b|jardin public|balan[çc]oire"),
    ('city_street', r"\brue\b|en ville|trottoir|boulevard|carrefour"), ('classroom', r"\bclasse\b|[ée]cole|ma[îi]tresse|professeur|\bprof\b"),
    ('hospital_room', r"h[ôo]pital|infirmi[èe]re"), ('library', r"biblioth[èe]que"), ('cafe', r"\bcaf[ée]\b|restaurant|serveu"), ('shop', r"magasin|supermarch[ée]|boutique|caisse"),
    ('office', r"\bbureau\b|coll[èe]gue|r[ée]union"), ('lab', r"laboratoire|exp[ée]rience|scientifique"), ('cave', r"grotte|caverne"), ('attic', r"grenier"),
    ('basement', r"sous-sol|\bcave\b"), ('kitchen', r"cuisine|frigo"), ('bathroom', r"salle de bain|douche|baignoire"), ('living_room', r"salon|canap[ée]|t[ée]l[ée]"),
    ('kid_bedroom', r"chambre d.enfant|doudou"), ('bedroom', r"chambre|\blit\b|r[ée]veil")]
ANIMAL_WORDS = [('dog', r"\bchiens?\b|chiot"), ('cat', r"\bchats?\b|chaton"), ('horse', r"cheval|chevaux"), ('dragon', r"dragon"), ('bird', r"oiseau"),
                ('rabbit', r"lapin"), ('ghost', r"fant[ôo]me"), ('spider', r"araign[ée]e")]

def place_of(lines, project):
    text = ' '.join(l['text'].lower() for l in lines)
    if project.get('place'): return project['place']
    if re.search(r"ascenseur|[ée]tage z[ée]ro|[ée]tage 0", text): return None        # the Étage 0 series keeps its own sets
    hits = [(len(re.findall(p, text)), -i, name) for i, (name, p) in enumerate(PLACE_WORDS)]
    best = max(hits)
    return best[2] if best[0] > 0 else None

def place_episode(lines, project, place, genre):
    """offline director for any ready-made place: hero near the main anchor, rotating framings, emotions and an animal"""
    from ..engines.pixel3d.sets import make_set
    st = make_set(place, {'type': place}); anc = st.anchors
    sx, sz = anc.get('start', (0, 0)); keys = [k for k in anc if k != 'start' and not k.split('.')[-1] in ('front', 'back', 'left', 'right', 'center')]
    from ..engines.pixel3d import world as WD
    import numpy as np
    def dry(k):                                    # never put the hero in the sea, a lake or lava
        x, z = anc[k]; g = st.spec.get('ground')
        for zn in st.spec.get('zones') or []:
            if WD.zone_mask(zn, np.array([x], np.float32), np.array([z], np.float32))[0]: g = zn.get('ground')
        return g not in ('water', 'lava')
    keys = [k for k in keys if dry(k)]
    meta, cA, cB = common_meta(lines); n = len(lines); prev_choice = project.get('previous_choice')
    text = ' '.join(l['text'].lower() for l in lines)
    pet = next((a for a, p in ANIMAL_WORDS if re.search(p, text)), None)
    shots = []; spot = 0
    def hero_at(i):
        k = keys[min(len(keys) - 1, (i * len(keys)) // max(1, n))] if keys else None
        x, z = anc[k] if k else (sx, sz + 4)
        if (x - sx) ** 2 + (z - sz) ** 2 < 4: z = sz + 3.5
        return [round(x + .6, 2), round(z - .8, 2)]
    for i, l in enumerate(lines):
        t = l['text'].lower(); s = {'lines': [i, i]}; hero = hero_at(i)
        acts = [{'id': 'hero', 'at': hero, 'facing': 'camera', 'face': 'neutral'}]
        if pet and (i % 3 == 1 or re.search(dict(ANIMAL_WORDS)[pet], t)):
            acts.append({'id': 'compagnon', 'at': [hero[0] + .9, hero[1] - .3], 'facing': 'camera'})
        frame = ['wide', 'medium', 'closeup', 'full', 'medium', 'ots'][i % 6]
        if frame == 'wide': cam = {'preset': 'free', 'keys': [{'pos': [hero[0] - 1.2, 1.6, hero[1] - 4.5], 'look': [hero[0], 1.2, hero[1]], 'fov': 62}], 'move': 'push_in', 'amount': .3}
        elif frame == 'ots': cam = {'preset': 'ots', 'subject': 'hero', 'fov': 70}; acts[0]['facing'] = '+z'
        else: cam = {'preset': frame, 'subject': 'hero', 'move': 'push_in', 'amount': .4}
        s.update(camera=cam, actors=acts)
        if i == 0 and prev_choice and re.search(r'choisi', t):
            letter = (re.findall(r'\b([AB])\b', l['text']) or [prev_choice[:1]])[0]
            s['ui'] = {'recap': {'title': 'TON CHOIX :', 'letter': letter, 'text': choice_text(project.get('previous_choice_text', prev_choice))}}
        elif i == n - 1:
            s.update(fx={'black': True}, ui={'endcard': {'part': project.get('part_label', ''), 'headline': 'FIN' if has(t, 'fin') and len(t) < 8 else 'A OU B ?'}})
        elif re.match(r'\s*(choix\s*[ab]|a ou b)', t):
            s.update(camera={'preset': 'closeup', 'subject': 'hero'}, ui={'choice': {'title': 'QUE FAIS-TU ?', 'A': cA or ['A', ''], 'B': cB or ['B', '']}})
        if re.search(r"\bpas\b.*(approch|march)|marche|avance", t): s['sfx'] = [{'name': 'footsteps_grass' if place in ('forest', 'park', 'countryside', 'village', 'lake', 'river') else 'footsteps_walk', 'dur': 1.6, 'gain': .5}]
        shots.append(s)
    ep = {'style': 'pixel3d', 'default_set': place, 'sets': {place: {'type': place, 'seed': int(project.get('seed', 0))}},
          'hud': {'title': [w.upper() for w in (project.get('hud_title') or "L'HISTOIRE|C'EST TOI").split('|')][:2], 'part': project.get('part_label', ''), 'hearts': [1, 1, 1]},
          'cast': {'hero': {}, 'compagnon': {'kind': pet} if pet else {}}, 'lines': meta, 'shots': shots,
          'summary': 'Mise en scène automatique (sans IA).'}
    return ep

def direct(lines, project):
    if project.get('style', 'pixel3d') != 'pixel3d': return console(lines, project)
    genre = genre_of(lines, project); place = place_of(lines, project)
    ep = act(place_episode(lines, project, place, genre) if place else pixel3d(lines, project), lines, genre)
    ep['genre'] = genre
    if genre != 'horror':
        ep['music'] = MUSIC[genre]; ep['grade'] = {'saturation': .95, 'exposure': 1.1}
        for s in ep['shots']:
            for ac in s.get('actors') or []:
                if ac.get('face') == 'scared' and not ac.get('gesture'): ac['face'] = 'neutral'
    return ep
