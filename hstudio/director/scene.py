"""Offline director for scenes played by library characters (no AI, free, local).

A script where each line starts with a character's name ("LÉA : Salut !") becomes an episode of the acting layer
(engine_version 2): the characters of library/characters keep their look in both engines, the place is one of the
ready-made places (PIXEL 3D) or the console bedroom, and the coverage follows the conversation: an establishing
shot, over-the-shoulder shots and singles on the speaker, a reaction on strong lines, a final two-shot or group
shot. Faces and gestures come from the words; the cinematographer and the quality control do the rest."""
import re, math, unicodedata
from ..acting import cast as CAST

FACES = [(r"\?!|!\?|quoi \?|hein \?|s[ée]rieux \?", 'surprised'), (r"peur|terrifi|au secours|aidez|j'entends", 'scared'),
         (r"haha|mdr|trop dr[ôo]le|je rigole", 'laugh'), (r"merci|super|g[ée]nial|trop bien|g[ée]ant|youpi", 'happy'),
         (r"d[ée]sol[ée]|triste|pardon|snif|me manque", 'sad'), (r"arr[êe]te|jamais|laisse-moi|t'es nul", 'angry'),
         (r"bizarre|[ée]trange|myst[èe]re|louche", 'suspicious'), (r"ensemble|promis|on y va|allons-y|c'est parti", 'determined'),
         (r"je sais pas|aucune id[ée]e|peut-[êe]tre|hmm", 'thinking')]
GESTURES = [(r"^(salut|bonjour|coucou|hey|bonsoir)", 'wave', 1.4), (r"regarde|tiens|voil[àa]", 'show', 1.8), (r"je sais pas|aucune id[ée]e", 'shrug', 1.4),
            (r"oh non|c'est pas vrai|pas possible", 'facepalm', 1.6), (r"l[àa]-bas|par l[àa]|derri[èe]re toi", 'point', 1.6),
            (r"bravo|g[ée]nial|trop fort", 'thumbs_up', 1.4), (r"chut", 'stop', 1.4), (r"r[ée]fl[ée]chi|attends", 'think', 1.8)]

def _norm(s):
    s = unicodedata.normalize('NFD', str(s)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '', s)

def names_of(cast_ids):
    """{normalised name or id: character id} for the characters of a project"""
    out = {}
    for cid in cast_ids or []:
        c = CAST.character(cid) or {'id': cid}
        out[_norm(cid)] = cid
        if c.get('name'): out[_norm(c['name'])] = cid; out[_norm(c['name'].split()[0])] = cid
    return out

SPEAKER = re.compile(r"^\s*([^:«»\"]{1,24}?)\s*:\s+(.+)$")
def split_speaker(text, names):
    """'LÉA : Salut' -> ('lea', 'Salut') when LÉA is a character of the project, else (None, text)"""
    m = SPEAKER.match(text or '')
    if m and _norm(m.group(1)) in names: return names[_norm(m.group(1))], m.group(2).strip()
    return None, text

def _free_spot(place, seed, radius):
    """a point of the place with room around it for the characters (not in the water, not in the furniture)"""
    from ..engines.pixel3d.sets import make_set
    from ..engines.pixel3d.stage import SetWorld
    from ..engines.pixel3d import world as WD
    import numpy as np
    st = make_set(place, {'type': place, 'seed': seed}); sw = SetWorld(st); obs = sw.obstacles(); x0, z0, x1, z1 = sw.bounds()
    anc = st.anchors; sx, sz = anc.get('start', ((x0 + x1) / 2, (z0 + z1) / 2))
    rooms = (st.spec or {}).get('rooms') or []
    if rooms:
        r = rooms[0]; ox, oz = r.get('origin', [0, 0]); w, d = r['size']; c0 = (ox, oz + d / 2); lim = (ox - w / 2 + .3, oz + .3, ox + w / 2 - .3, oz + d - .3)
    else:
        c0 = (sx, sz + 4.); lim = (x0, z0, x1, z1)
    def wet(x, z):
        g = st.spec.get('ground')
        for zn in st.spec.get('zones') or []:
            if WD.zone_mask(zn, np.array([x], np.float32), np.array([z], np.float32))[0]: g = zn.get('ground')
        return g in ('water', 'lava')
    def clear(x, z):
        d = min(x - lim[0], lim[2] - x, z - lim[1], lim[3] - z)
        for o in obs:
            dx = max(o[0] - x, 0., x - o[2]); dz = max(o[1] - z, 0., z - o[3]); d = min(d, math.hypot(dx, dz))
        return d
    best = None
    for i in range(-16, 17):
        for j in range(-16, 17):
            x, z = c0[0] + i * .25, c0[1] + j * .25
            if not (lim[0] <= x <= lim[2] and lim[1] <= z <= lim[3]): continue
            cl = min(clear(x, z), 2.5)
            if cl < radius + .35 or wet(x, z): continue
            sc = cl - .18 * math.hypot(x - c0[0], z - c0[1])
            if best is None or sc > best[0]: best = (sc, x, z)
    c = (best[1], best[2]) if best else c0
    fx, fz = sx - c[0], sz - c[1]; L = math.hypot(fx, fz)                # the open side of the stage: where one comes in
    return c, ((fx / L, fz / L) if L > .5 else (0., -1.))

def blocking(ids, center, front=(0., -1.)):
    """two characters face to face across the open side; three or more on an arc open towards the camera side
    (nobody turns his back to the audience), all facing a point just in front of the centre"""
    cx, cz = center; fx, fz = front; rx, rz = -fz, fx; n = len(ids)
    if n == 1: return {ids[0]: [round(cx, 2), round(cz, 2)]}, (cx + fx * .5, cz + fz * .5)
    if n == 2: return {ids[0]: [round(cx - rx * .72, 2), round(cz - rz * .72, 2)], ids[1]: [round(cx + rx * .72, 2), round(cz + rz * .72, 2)]}, (cx, cz)
    r = 1.05 if n == 3 else 1.2; spread = {3: (-58, 0, 58), 4: (-72, -24, 24, 72)}.get(n) or tuple(-80 + 160 * k / (n - 1) for k in range(n)); out = {}
    for a, deg in zip(ids, spread):
        t = math.radians(deg); bx, bz = -fx, -fz                     # behind the centre, spread left and right
        dx, dz = bx * math.cos(t) - bz * math.sin(t), bx * math.sin(t) + bz * math.cos(t)
        out[a] = [round(cx + dx * r, 2), round(cz + dz * r, 2)]
    return out, (cx + fx * .45, cz + fz * .45)

def _title(project):
    t = project.get('hud_title') or ''
    if not t or t == "L'ÉTAGE 0|N'EXISTE PAS":                  # the default title of the horror series: use the series name
        w = (project.get('series') or 'TU DÉCIDES').upper().split(); h = (len(w) + 1) // 2
        return [' '.join(w[:h]), ' '.join(w[h:])] if len(w) > 1 else w
    return [x.upper() for x in t.split('|')][:2]

def _face(t):
    return next((f for p, f in FACES if re.search(p, t)), None)

def direct(lines, project):
    """lines: lines.json with 'speaker' (character id) when known; project: meta with cast, place, style"""
    ids = [c for c in (project.get('cast') or []) if CAST.character(c)]
    if not ids: raise ValueError('aucun personnage de la bibliothèque')
    style = project.get('style', 'pixel3d'); n = len(lines)
    people = [c for c in ids if (CAST.character(c) or {}).get('look', {}).get('kind') is None]
    pets = [c for c in ids if c not in people]
    spk = [l.get('speaker') if l.get('speaker') in ids else None for l in lines]
    meta = {str(i): {'speaker': s} for i, s in enumerate(spk) if s}
    for i, s in enumerate(spk):
        if s: meta[str(i)].update(label=(CAST.character(s) or {}).get('name', s).upper(), label_color=['orange', 'blue', 'green', 'pink', 'white'][ids.index(s) % 5])
    ep = {'engine_version': 2, 'style': style, 'cast': {c: {'ref': c} for c in ids}, 'lines': meta, 'summary': 'Mise en scène automatique avec les personnages de la bibliothèque (sans IA).'}
    sid = CAST.ensure_series(project.get('series'), ids) if project.get('series') else None
    if sid: ep['series'] = sid
    shots = []
    if style == 'console':
        spots = {1: ['center'], 2: ['left', 'right'], 3: ['left', 'center', 'right']}.get(len(people), ['left', 'center', 'right', 'front'])
        actors = [{'id': c, 'at': spots[k % len(spots)], 'facing': 'camera'} for k, c in enumerate(people[:4])]
        if len(actors) == 2: actors[0]['facing'] = '+x'; actors[1]['facing'] = '-x'
        ep.update(hud={'series': (project.get('series') or 'NE METS PAS PAUSE').upper(), 'level': project.get('part_label') or 'NIVEAU 1'})
        for i, l in enumerate(lines):
            s = {'lines': [i, i], 'scene': {'type': 'room'}, 'camera': {'move': 'push_in', 'amount': .5}}
            if i == 0: s['actors'] = actors
            if spk[i]: s['camera']['on'] = spk[i]
            acts = _acting_of(l, spk[i], spk, i, people)
            if acts: s['actions'] = acts
            shots.append(s)
    else:
        place = project.get('place') or 'park'
        center, front = _free_spot(place, int(project.get('seed', 0)), .9 if len(people) <= 2 else 1.2)
        pos, look = blocking(people, center, front); look = [round(look[0], 2), round(look[1], 2)]
        side = [round(center[0] + front[0] * 4, 2), round(center[1] + front[1] * 4, 2)]          # where the wide shots film from
        actors = [{'id': c, 'at': pos[c], 'facing': look} for c in people]
        for k, c in enumerate(pets): actors.append({'id': c, 'at': [round(center[0] + front[0] * .9 + .45 * k, 2), round(center[1] + front[1] * .9, 2)], 'facing': [round(center[0], 2), round(center[1], 2)]})
        ep.update(default_set='lieu', sets={'lieu': {'type': place, 'seed': int(project.get('seed', 0))}}, music=project.get('music', 'calm'),
                  hud={'title': _title(project), 'part': project.get('part_label', ''), 'hearts': []})
        prev = None
        for i, l in enumerate(lines):
            s = {'lines': [i, i]}; who = spk[i]; t = l.get('text', '').lower()
            if i == 0:
                s['actors'] = actors; s['camera'] = {'shot': 'group' if len(people) > 2 else 'wide' if len(people) == 2 else 'full', 'on': people, 'from': side}
            elif i == n - 1 and n > 2:
                s['camera'] = {'shot': 'two_shot' if len(people) == 2 else 'group', 'on': people, 'move': 'dolly_out', 'amount': .35, 'from': side}
            elif who is None:
                s['camera'] = {'shot': 'group' if len(people) > 2 else 'two_shot', 'on': people, 'from': side}
            elif re.search(r"!|\?!", t) and prev and prev != who and i % 2 == 0:
                s['camera'] = {'shot': 'close', 'on': [who], 'move': 'dolly_in', 'amount': .35}
            elif len(people) == 2:
                s['camera'] = {'shot': 'dialogue', 'on': people, 'speaker': who} if i % 4 != 3 else {'shot': 'close', 'on': [who]}
            else:
                s['camera'] = {'shot': 'medium', 'on': [who]} if i % 3 else {'shot': 'group', 'on': people, 'from': side}
            acts = _acting_of(l, who, spk, i, people)
            if acts: s['actions'] = acts
            shots.append(s); prev = who or prev
    ep['shots'] = shots
    return ep

def _acting_of(l, who, spk, i, people):
    """face and gesture of the speaker from the words; the listeners react to strong lines"""
    t = (l.get('text') or '').lower(); acts = []
    if not who: return acts
    f = _face(t)
    if f: acts.append({'who': who, 'do': 'face', 'name': f})
    g = next(((g, d) for p, g, d in GESTURES if re.search(p, t)), None)
    if g: acts.append({'who': who, 'do': 'gesture', 'name': g[0], 'at': .25, 'dur': g[1]})
    if f in ('surprised', 'scared'):
        for c in people:
            if c != who: acts.append({'who': c, 'do': 'react', 'kind': 'gasp' if f == 'surprised' else 'flinch', 'at': .6}); break
    elif f in ('laugh', 'happy'):
        for c in people:
            if c != who: acts.append({'who': c, 'do': 'face', 'name': 'happy' if f == 'happy' else 'laugh', 'at': .8}); break
    return acts
