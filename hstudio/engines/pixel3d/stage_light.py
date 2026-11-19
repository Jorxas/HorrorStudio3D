"""Lumière de scène d'un théâtre : la clé `stage_light` (épisode et/ou plan), lue par le lieu `theatre_bal` (theatre.py) et par lui seul.

Une même fonction (`evaluate`) dit, pour un instant d'un plan, ce que fait la lumière ; PS1 (theatre.py) et VOXEL (voxelgpu/b_theatre.py)
la PEIGNENT chacun à leur façon. Rien d'aléatoire, aucune horloge : fonction pure du plan, de l'instant, de l'état du monde et de la
position des acteurs.

Écriture (toutes les clés sont facultatives) :
    "stage_light": "ambre"                                         raccourci : un lavis prédéfini
    "stage_light": {"wash": "bleu_nuit", "wash_i": 1.0,            lavis (couleur de face) et sa force
                    "back": "#ff40a0", "back_i": 0.8,             contre-jour (couleur du fond et des bords des silhouettes)
                    "ambient": [0.02, 0.03, 0.06], "fog": "#05070f",
                    "haze": 0.4,                                   brume : rend les faisceaux visibles (0 = air pur)
                    "practicals": 1.0,                             lanternes et bougies du décor (0 = éteintes, 1 = normales)
                    "curtain": 1.0 | {"i": 1, "color": "#4ab0ff"},  rideau de lumière : rangée de projecteurs face caméra, faisceaux dans la brume
                    "follow": "eliza" | {"on": "eliza", "r": 0.9, "i": 1, "color": "#fff2dc", "src": "face"|"haut"|[x, y, z], "soft": 0..1} | [...],
                                                                   poursuite (2 au plus) ; `soft` = clé douce (bord flou, pas de faisceau visible) ; `at` [x, z] au lieu de `on` : point fixe
                    "pools": [{"at": [x, z] | "on": "eliza", "r": 2.5, "ring": 0, "color": "#ffb060", "i": 1, "dapple": 0.6}],
                                                                   disques de lumière au sol vus d'en haut (3 au plus) ; `ring` = rayon intérieur (anneau) ; `dapple` = tacheté (motif de feuillage)
                    "fade_in": 0.8}                                fondu depuis la lumière de la fin du plan précédent (secondes)
    "stage_light": [{"t": 0, "wash": "bleu_nuit"}, {"t": 2.5, "wash": "ambre", "follow": "eliza"}]     clés dans le temps du plan :
                    chaque clé hérite de la précédente ; nombres et couleurs glissent (smoothstep) d'une clé à l'autre ; "cut": true saute.

L'épisode peut porter un `stage_light` par défaut : le plan s'écrit PAR-DESSUS (clé par clé). Sans aucune clé : lavis `bleu_nuit`.
État du monde (`state` / `state_track`, une valeur par image) : `light_i` (maître), `wash_i`, `back_i`, `curtain`, `practicals`, `haze`, `follow_i`
REMPLACENT la valeur écrite (`light_i` et `follow_i` la multiplient) ; `turn_inner` / `turn_outer` (degrés) tournent les deux anneaux du plateau,
ou `turn_inner_rate` / `turn_outer_rate` (degrés par seconde, sur le temps du FILM : la rotation continue d'un plan à l'autre).
"""
import math

# lavis prédéfinis (couleurs linéaires 0..1)
PRESETS = {
    'bleu_nuit':   dict(wash=(.22, .40, 1.0), wash_i=1.0, back=(.30, .48, 1.0), back_i=.9, ambient=(.016, .024, .066), fog=(.004, .007, .024)),
    'ambre':       dict(wash=(1.0, .64, .32), wash_i=.8, back=(1.0, .74, .44), back_i=.8, ambient=(.052, .034, .018), fog=(.020, .012, .006)),
    'violet':      dict(wash=(.44, .34, 1.0), wash_i=1.0, back=(.62, .34, 1.0), back_i=.95, ambient=(.036, .016, .052), fog=(.014, .005, .022)),
    'blanc_froid': dict(wash=(.86, .92, 1.0), wash_i=1.0, back=(.80, .88, 1.0), back_i=.75, ambient=(.040, .045, .056), fog=(.010, .012, .016)),
    'noir':        dict(wash=(.20, .32, .90), wash_i=0.0, back=(.20, .32, .90), back_i=0.0, ambient=(.0015, .002, .004), fog=(0., 0., 0.)),
    'magenta':     dict(wash=(.95, .30, .82), wash_i=.95, back=(1.0, .26, .70), back_i=.95, ambient=(.046, .014, .040), fog=(.018, .004, .016)),
    'lavande':     dict(wash=(.66, .58, 1.0), wash_i=.9, back=(.74, .62, 1.0), back_i=.8, ambient=(.034, .030, .058), fog=(.012, .010, .022)),
    'bleu_violet': dict(wash=(.42, .36, 1.0), wash_i=1.0, back=(.70, .40, 1.0), back_i=.9, ambient=(.024, .020, .064), fog=(.008, .006, .024)),
    'rose':        dict(wash=(1.0, .52, .60), wash_i=.85, back=(1.0, .62, .70), back_i=.8, ambient=(.050, .026, .030), fog=(.020, .009, .011)),
}
ALIASES = {'bleu': 'bleu_nuit', 'nuit': 'bleu_nuit', 'blue': 'bleu_nuit', 'night': 'bleu_nuit', 'or': 'ambre', 'chaud': 'ambre', 'amber': 'ambre', 'warm': 'ambre', 'gold': 'ambre',
           'purple': 'violet', 'pink': 'rose', 'lavender': 'lavande', 'blanc': 'blanc_froid', 'froid': 'blanc_froid', 'white': 'blanc_froid', 'cold': 'blanc_froid',
           'black': 'noir', 'blackout': 'noir', 'off': 'noir'}
CURTAIN_COL = (.16, .52, 1.0)
FOLLOW_COL = (1.0, .95, .86)
POOL_COL = (1.0, .74, .40)
BASE = dict(PRESETS['bleu_nuit'], haze=.35, practicals=1., curtain=0., curtain_col=CURTAIN_COL, follow=(), pools=())
NUM = ('wash_i', 'back_i', 'haze', 'practicals', 'curtain')
COL = ('wash', 'back', 'ambient', 'fog', 'curtain_col')
KEYS = set(NUM) | set(COL) | {'follow', 'pools', 'fade_in', 't', 'cut'}
NOTES = []          # avertissements en français, une fois chacun (`[lumiere] ...`)


def _note(msg):
    if msg not in NOTES: NOTES.append(msg); print('[lumiere] ' + msg)


def smooth(k): k = max(0., min(1., k)); return k * k * (3 - 2 * k)


def color(v, default=(1., 1., 1.)):
    """'#rrggbb' | [r, g, b] (0..1, ou 0..255 si une valeur dépasse 1) | nom de lavis -> (r, g, b) 0..1"""
    if v is None: return tuple(default)
    if isinstance(v, str):
        s = v.strip().lstrip('#')
        if len(s) == 6:
            try: return tuple(int(s[i:i + 2], 16) / 255. for i in (0, 2, 4))
            except ValueError: pass
        n = ALIASES.get(s, s)
        if n in PRESETS: return tuple(PRESETS[n]['wash'])
        _note(f'couleur « {v} » illisible : {default} gardée'); return tuple(default)
    if isinstance(v, (list, tuple)) and len(v) >= 3:
        c = [float(x) for x in v[:3]]
        if max(c) > 1.001: c = [x / 255. for x in c]
        return tuple(c)
    _note(f'couleur {v!r} illisible : {default} gardée'); return tuple(default)


def _follow(v):
    """une poursuite écrite -> liste normalisée [{on|at, i, r, col, src}]"""
    if v is None or v is False or v == []: return ()
    items = v if isinstance(v, (list, tuple)) and (not v or not isinstance(v[0], (int, float))) else [v]
    out = []
    for it in items:
        if isinstance(it, str): it = {'on': it}
        if not isinstance(it, dict): _note(f'poursuite {it!r} illisible : ignorée'); continue
        f = dict(i=float(it.get('i', 1.)), r=float(it.get('r', .9)), col=color(it.get('color'), FOLLOW_COL), src=it.get('src', 'face'), soft=float(it.get('soft', 0.)))
        if it.get('on') is not None: f['on'] = str(it['on'])
        elif it.get('at') is not None: f['at'] = [float(x) for x in it['at']]
        else: _note('poursuite sans « on » ni « at » : ignorée'); continue
        out.append(f)
    if len(out) > 2: _note('plus de 2 poursuites : les 2 premières sont gardées')
    return tuple(out[:2])


def apply(base, spec):
    """état de lumière `base` + champs écrits `spec` -> nouvel état (un nom de lavis pose toutes ses couleurs, les autres clés passent par-dessus)"""
    s = dict(base)
    if spec is None: return s
    if isinstance(spec, str): spec = {'wash': spec}
    if not isinstance(spec, dict): _note(f'stage_light {spec!r} illisible : ignoré'); return s
    for k in spec:
        if k not in KEYS: _note(f'clé « {k} » de stage_light inconnue : ignorée (connues : {", ".join(sorted(KEYS))})')
    w = spec.get('wash')
    if isinstance(w, str) and ALIASES.get(w.lstrip('#'), w) in PRESETS:
        s.update(PRESETS[ALIASES.get(w, w)])
    elif isinstance(w, str) and not w.startswith('#'):
        _note(f'lavis « {w} » inconnu : bleu_nuit (connus : {", ".join(PRESETS)})'); s.update(PRESETS['bleu_nuit'])
    elif w is not None: s['wash'] = color(w, s['wash'])
    for k in NUM:
        if k == 'curtain' and isinstance(spec.get(k), dict):
            c = spec[k]; s['curtain'] = float(c.get('i', 1.))
            if c.get('color') is not None: s['curtain_col'] = color(c['color'], CURTAIN_COL)
        elif spec.get(k) is not None: s[k] = float(spec[k])
    for k in ('back', 'ambient', 'fog'):
        if spec.get(k) is not None: s[k] = color(spec[k], s[k])
    if 'follow' in spec: s['follow'] = _follow(spec['follow'])
    if 'pools' in spec: s['pools'] = _pools(spec['pools'])
    return s


def _pools(v):
    """disques de lumière au sol (douche vue d'en haut) : [{at|on, r, ring, i, col, dapple}] (3 au plus)"""
    if not v: return ()
    items = v if isinstance(v, (list, tuple)) else [v]; out = []
    for it in items:
        if isinstance(it, str): it = {'on': it}
        if not isinstance(it, dict): _note(f'disque {it!r} illisible : ignoré'); continue
        f = dict(i=float(it.get('i', 1.)), r=float(it.get('r', 2.5)), ring=float(it.get('ring', 0.)), col=color(it.get('color'), POOL_COL), dapple=float(it.get('dapple', 0.)))
        if it.get('on') is not None: f['on'] = str(it['on'])
        else: a = it.get('at', [0., 4.6]); f['at'] = [float(x) for x in a]
        out.append(f)
    if len(out) > 3: _note('plus de 3 disques au sol : les 3 premiers sont gardés')
    return tuple(out[:3])


def blend(a, b, k):
    """deux états -> l'état à la fraction k (nombres et couleurs linéaires ; poursuites appariées par acteur, une poursuite qui apparaît monte de 0)"""
    if k <= 0: return a
    if k >= 1: return b
    o = {}
    for n in NUM: o[n] = a[n] + (b[n] - a[n]) * k
    for n in COL: o[n] = tuple(x + (y - x) * k for x, y in zip(a[n], b[n]))
    key = lambda f: f.get('on') or tuple(f.get('at', ()))
    fa = {key(f): f for f in a['follow']}; fb = {key(f): f for f in b['follow']}; fl = []
    for kk in list(fa) + [x for x in fb if x not in fa]:
        x, y = fa.get(kk), fb.get(kk)
        if x and y: fl.append(dict(y, i=x['i'] + (y['i'] - x['i']) * k, r=x['r'] + (y['r'] - x['r']) * k, col=tuple(p + (q - p) * k for p, q in zip(x['col'], y['col']))))
        elif x: fl.append(dict(x, i=x['i'] * (1 - k)))
        else: fl.append(dict(y, i=y['i'] * k))
    o['follow'] = tuple(fl)
    pa = {key(f): f for f in a.get('pools', ())}; pb = {key(f): f for f in b.get('pools', ())}; pl = []
    for kk in list(pa) + [x for x in pb if x not in pa]:
        x, y = pa.get(kk), pb.get(kk)
        if x and y: pl.append(dict(y, i=x['i'] + (y['i'] - x['i']) * k, r=x['r'] + (y['r'] - x['r']) * k, ring=x['ring'] + (y['ring'] - x['ring']) * k, dapple=x['dapple'] + (y['dapple'] - x['dapple']) * k,
                                   col=tuple(p + (q - p) * k for p, q in zip(x['col'], y['col']))))
        elif x: pl.append(dict(x, i=x['i'] * (1 - k)))
        else: pl.append(dict(y, i=y['i'] * k))
    o['pools'] = tuple(pl)
    return o


def _keys(base, spec):
    """spec de plan -> [(t, état, cut)] (une seule clé si ce n'est pas une liste)"""
    if isinstance(spec, list):
        out = []; cur = base
        for kk in sorted((k for k in spec if isinstance(k, dict)), key=lambda k: float(k.get('t', 0.))):
            cur = apply(cur, kk); out.append((float(kk.get('t', 0.)), cur, bool(kk.get('cut'))))
        return out or [(0., base, False)]
    return [(0., apply(base, spec), False)]


def _fade_in(spec):
    if isinstance(spec, dict): return float(spec.get('fade_in', 0.) or 0.)
    if isinstance(spec, list) and spec and isinstance(spec[0], dict): return float(spec[0].get('fade_in', 0.) or 0.)
    return 0.


def at_keys(keys, T):
    j = 0
    while j + 1 < len(keys) and keys[j + 1][0] <= T: j += 1
    if j + 1 >= len(keys) or T <= keys[j][0]: return keys[j][1]
    tb, sb, cut = keys[j + 1]
    if cut: return keys[j][1]
    return blend(keys[j][1], sb, smooth((T - keys[j][0]) / max(1e-6, tb - keys[j][0])))


def shot_state(ep, shot, T, prev=None, prev_T=None):
    """état de lumière écrit (avant l'état du monde et les acteurs) à l'instant T du plan ; `prev`/`prev_T` : le plan précédent et sa durée (pour `fade_in`)"""
    base = apply(BASE, (ep or {}).get('stage_light'))
    spec = shot.get('stage_light')
    cur = at_keys(_keys(base, spec), T)
    fi = _fade_in(spec)
    if fi > 0 and prev is not None and T < fi:
        pk = _keys(base, prev.get('stage_light'))
        return blend(at_keys(pk, float(prev_T or 0.)), cur, smooth(T / fi))
    return cur


def _num(state, key, u=0.):
    v = (state or {}).get(key)
    if isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v): return v[0] + (v[1] - v[0]) * smooth(u)
    return float(v) if isinstance(v, (int, float)) else None


def turn_angles(state, g, u=0.):
    """(anneau intérieur, anneau extérieur) en radians : angle écrit, sinon vitesse x temps du film"""
    out = []
    for ring in ('inner', 'outer'):
        a = _num(state, 'turn_' + ring, u)
        if a is None:
            r = _num(state, f'turn_{ring}_rate', u); a = (r or 0.) * float(g)
        out.append(math.radians(a))
    return tuple(out)


def resolve(s, state, who, g, u=0.):
    """état écrit + état du monde (`state_track`) + positions des acteurs {id: (x, y, z)} -> enregistrement complet de l'image (repère PIXEL 3D)"""
    r = dict(s)
    for k in ('wash_i', 'back_i', 'curtain', 'practicals', 'haze'):
        v = _num(state, k, u)
        if v is not None: r[k] = v
    m = _num(state, 'light_i', u)
    if m is not None:
        for k in ('wash_i', 'back_i', 'curtain'): r[k] *= m
    fm = _num(state, 'follow_i', u); fm = 1. if fm is None else fm
    if m is not None: fm *= m
    fl = []
    for f in s['follow']:
        if 'on' in f:
            p = (who or {}).get(f['on'])
            if p is None: _note(f"poursuite sur « {f['on']} » : acteur absent du plan, poursuite éteinte"); continue
            tgt = (float(p[0]), float(p[1]), float(p[2]))
        else:
            a = f['at']; tgt = (a[0], 0., a[1]) if len(a) == 2 else (a[0], a[1], a[2])
        src = f.get('src', 'face')
        if src == 'haut': sp = (tgt[0] + .2, tgt[1] + 11.5, tgt[2] - 1.6)
        elif isinstance(src, (list, tuple)) and len(src) == 3: sp = tuple(float(x) for x in src)
        else: sp = (tgt[0] * .35, 10.5, -11.)               # poursuite de salle : haut, devant la scène
        aim = (tgt[0], tgt[1] + 1.0, tgt[2])                   # visée à la poitrine (le visage reste dans le cercle), cercle au sol autour des pieds
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(aim, sp)))
        fl.append(dict(target=tgt, aim=aim, src=sp, half=math.atan2(max(f['r'], .5) * 1.15, dist), r=f['r'], i=f['i'] * fm, col=f['col'], on=f.get('on'), soft=f.get('soft', 0.)))
    r['follow'] = tuple(fl)
    pl = []
    for f in s.get('pools', ()):
        if 'on' in f:
            p = (who or {}).get(f['on'])
            if p is None: _note(f"disque au sol sur « {f['on']} » : acteur absent du plan, disque éteint"); continue
            c = (float(p[0]), float(p[2]))
        else: c = (f['at'][0], f['at'][-1])
        pl.append(dict(at=c, r=f['r'], ring=f['ring'], i=f['i'] * (m if m is not None else 1.), col=f['col'], dapple=f['dapple']))
    r['pools'] = tuple(pl)
    r['turn'] = turn_angles(state, g, u)
    return r


def evaluate(ep, shots, k, T, state, who, g, u=0., prev_T=None, shot=None):
    """LE point d'entrée : plan k de l'épisode, instant T du plan -> enregistrement de lumière (repère PIXEL 3D)"""
    shot = shot if shot is not None else shots[k]; prev = shots[k - 1] if k > 0 else None
    return resolve(shot_state(ep, shot, T, prev, prev_T), state, who, g, u)
