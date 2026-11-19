"""The scene contract between the director (B) and the painter (A): `hs-unified/1`.

A contract is plain JSON. Everything the painter needs is in it and nothing is decided by the painter:

    schema, title, genre, aspect ("9:16" | "16:9"), fps, duration
    casts   {id: {preset: noe|lina|npc|alien, variant, look: {A character spec overrides}, scale, accessories, ...}}
    expressions   names, indexed by the "expr" column
    actor_cols    names of the columns of every actor frame (ACTOR_COLS)
    stages  [{id, world, t0, t1, tail, dissolve, mood, look, dof, mblur, focus_actor, prints, steps,
              camera: [[px,py,pz, lx,ly,lz, fov_deg, roll_rad], ...]           (one row per frame from t0, stage-local metres)
              actors: {id: [[...ACTOR_COLS...], ...]}}]                         (same rows)
    fx      [{type: fade|flash|shake|bars, t0, t1, ...}]
    captions [{t0, t1, text, words?}] , caption_style
    words   [{text, t0, t1, ndc, dist, size, color, in, out, lock, ...}]            (optional: 3D cube words of a music clip, see clean_words)
    audio   {music: {...}, sfx: [{t, name, gain}]}   (read by the Python side, not by the painter)

Coordinates are those of the A world named by the stage (x along the street, z towards the camera, y up, metres).
Yaw follows B's heading convention: atan2(dx, dz), the same as three.js rotation.y.
"""
import hashlib, json, math

SCHEMA = 'hs-unified/1'
ASPECTS = ('9:16', '16:9')
ACTOR_COLS = ['vis', 'x', 'y', 'z', 'yaw', 'gait', 'phase', 'amp', 'sit', 'seat_h', 'crouch', 'air', 'lean', 'expr', 'talk', 'hyaw', 'hpit',
              'armw', 'epx', 'epy', 'epz', 'hpx', 'hpy', 'hpz', 'enx', 'eny', 'enz', 'hnx', 'hny', 'hnz', 'handp', 'handn']
# the expressions of the voxel engine (engine/face4.js PRESETS): the 17 original ones, then (APPENDED, so the indices of every existing film stay the same) the 38 that complete the
# 43 faces of PIXEL 3D (hstudio/director/validate.FACES), each with its own preset
EXPRESSIONS = ['neutral', 'worried', 'scared', 'scaredL', 'scaredR', 'scream', 'shout', 'grit', 'determined', 'smile', 'relief', 'sad', 'cry', 'surprised', 'blink', 'lookL', 'lookR',
               'closed', 'talk', 'urgent', 'happy', 'grin', 'joy', 'laugh', 'excited', 'love', 'wink', 'silly', 'smirk', 'proud', 'shy', 'calm', 'shocked', 'nervous', 'crying', 'angry', 'furious',
               'disgusted', 'confused', 'suspicious', 'thinking', 'bored', 'tired', 'sleeping', 'evil', 'cool', 'pain', 'dizzy', 'smile_sad', 'ko', 'skull', 'robot', 'alien', 'creature', 'double',
  # V4 : expressions ajoutées (face4.js), à la fin pour que les indices des films existants ne bougent pas
  'contempt', 'sarcastic', 'mocking', 'hesitant', 'uneasy', 'adoring', 'dreamy', 'jealous', 'exhausted', 'drunk', 'shivering', 'lip_tremble', 'half_smile', 'grimace', 'sobbing', 'yawn', 'pout', 'smug', 'bitter', 'gloomy',
  # 6/11/2026 : les 3 expressions « objets du récit » de PIXEL 3D, ajoutées à la FIN (les indices des films existants ne bougent pas)
  'fixed_smile', 'predator', 'predator_smile']
MOODS = ['neutral', 'warm', 'comedy', 'romance', 'drama', 'adventure', 'noir', 'thriller', 'horror', 'scifi', 'fantasy', 'western', 'dusk', 'night']
GENRES = {  # default mood per genre word of an episode
    'comedy': 'comedy', 'comedie': 'comedy', 'romance': 'romance', 'drama': 'drama', 'drame': 'drama', 'adventure': 'adventure', 'aventure': 'adventure',
    'noir': 'noir', 'thriller': 'thriller', 'horror': 'horror', 'horreur': 'horror', 'scifi': 'scifi', 'sci-fi': 'scifi', 'fantasy': 'fantasy',
    'western': 'western', 'action': 'adventure', 'documentary': 'neutral', 'slice_of_life': 'warm', 'neutral': 'neutral'}


def empty_frame():
    return [0.] * len(ACTOR_COLS)


WORD_IN = ('pop', 'drop', 'rise', 'slide', 'assemble', 'type', 'none')
WORD_OUT = ('shrink', 'scatter', 'fall', 'cut')
WORD_KEYS = ('text', 't0', 't1', 'ndc', 'dist', 'size', 'color', 'glow', 'in', 'out', 'lock', 'yaw', 'pitch', 'roll', 'seed', 'tracking', 'stagger', 'float', 'align', 'maxw')


def clean_words(ws):
    """`ep["words"]` -> les mots 3D du contrat (typographie en cubes posée DANS la scène ; peinte par VOXEL seulement).
    Chaque mot : {text, t0, t1?, ndc: [x, y]?, dist?, size?, color?, glow?, in?, out?, lock?: "frame"|"world", yaw?, pitch?, roll?, seed?, tracking?, stagger?, float?, align?, maxw?}.
    Temps absolus du film. Lève ValueError (en français) à la première faute ; [] -> [] (le contrat n'a alors pas la clé)."""
    out = []
    for i, w in enumerate(ws or []):
        if not isinstance(w, dict): raise ValueError(f'mot {i} : un objet est attendu')
        bad = sorted(set(w) - set(WORD_KEYS))
        if bad: raise ValueError(f'mot {i} : clé(s) inconnue(s) {bad} (connues : {", ".join(WORD_KEYS)})')
        text = str(w.get('text', '')).strip()
        if not text: raise ValueError(f'mot {i} : texte absent')
        if len(text) > 40: raise ValueError(f'mot {i} : {len(text)} lettres, 40 au plus (un mot, pas une phrase)')
        try: t0 = float(w['t0'])
        except (KeyError, TypeError, ValueError): raise ValueError(f'mot {i} ({text}) : t0 absent ou illisible')
        t1 = float(w.get('t1', t0 + 1.2))
        if not t1 > t0: raise ValueError(f'mot {i} ({text}) : t1 doit être après t0')
        m = dict(w, text=text, t0=round(t0, 3), t1=round(t1, 3))
        if w.get('in', 'pop') not in WORD_IN: raise ValueError(f'mot {i} ({text}) : entrée « {w["in"]} » inconnue (connues : {", ".join(WORD_IN)})')
        if w.get('out', 'shrink') not in WORD_OUT: raise ValueError(f'mot {i} ({text}) : sortie « {w["out"]} » inconnue (connues : {", ".join(WORD_OUT)})')
        if w.get('lock', 'frame') not in ('frame', 'world'): raise ValueError(f'mot {i} ({text}) : lock = "frame" ou "world"')
        nd = w.get('ndc')
        if nd is not None and not (isinstance(nd, (list, tuple)) and len(nd) == 2 and all(isinstance(v, (int, float)) and -1.5 <= v <= 1.5 for v in nd)):
            raise ValueError(f'mot {i} ({text}) : ndc = [x, y] entre -1 et 1')
        for k in ('dist', 'size'):
            if k in w and not (isinstance(w[k], (int, float)) and w[k] > 0): raise ValueError(f'mot {i} ({text}) : {k} doit être un nombre positif')
        out.append(m)
    out.sort(key=lambda m: (m['t0'], m['text']))
    return out


def validate(c):
    """-> list of problems (French, for the log); [] if the contract can be painted"""
    bad = []
    if c.get('schema') != SCHEMA: bad.append(f"schéma inconnu : {c.get('schema')!r} (attendu {SCHEMA})")
    if c.get('aspect') not in ASPECTS: bad.append(f"format inconnu : {c.get('aspect')!r}")
    if not (isinstance(c.get('fps'), (int, float)) and 1 <= c['fps'] <= 120): bad.append('fps hors limites')
    if not (isinstance(c.get('duration'), (int, float)) and c['duration'] > 0): bad.append('durée absente')
    if c.get('actor_cols') != ACTOR_COLS: bad.append('colonnes d\'acteur différentes de ACTOR_COLS')
    if not c.get('stages'): bad.append('aucun plan (stages)')
    casts = c.get('casts') or {}
    prev = None
    for i, st in enumerate(c.get('stages') or []):
        n = len(st.get('camera') or [])
        need = int(math.ceil((st['t1'] + st.get('tail', 0.) - st['t0']) * c['fps'] - 1e-6)) if 't1' in st else 0
        if n < max(2, need): bad.append(f"plan {i} ({st.get('id')}) : {n} images de caméra pour {need} nécessaires")
        if st.get('mood') and not all((m[0] if isinstance(m, list) else m) in MOODS for m in (st['mood'] if isinstance(st['mood'], list) else [st['mood']])): bad.append(f"plan {i} : ambiance inconnue {st['mood']!r}")
        for aid, rows in (st.get('actors') or {}).items():
            if aid not in casts: bad.append(f"plan {i} : acteur {aid!r} absent de casts")
            if len(rows) < n: bad.append(f"plan {i} : acteur {aid!r} n'a que {len(rows)} lignes pour {n} images")
            if rows and len(rows[0]) != len(ACTOR_COLS): bad.append(f"plan {i} : acteur {aid!r} a {len(rows[0])} colonnes au lieu de {len(ACTOR_COLS)}")
            for r in rows[:: max(1, len(rows) // 50)]:
                if any(not math.isfinite(v) for v in r): bad.append(f"plan {i} : acteur {aid!r} a une valeur non finie"); break
        if prev is not None and st['t0'] < prev['t0'] - 1e-9: bad.append(f'plan {i} : t0 recule')
        prev = st
    return bad


def dumps(c):
    return json.dumps(c, ensure_ascii=False, separators=(',', ':'), sort_keys=True)


def digest(c):
    return hashlib.sha256(dumps(c).encode('utf-8')).hexdigest()


def save(c, path):
    with open(path, 'w', encoding='utf-8') as f: f.write(dumps(c))
    return digest(c)


def load(path):
    with open(path, encoding='utf-8') as f: return json.load(f)
