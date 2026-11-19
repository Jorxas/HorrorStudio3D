"""Étape CONSTRUIRE du kit : exécute histoire.py (la mise en scène écrite par l'IA) pour chaque format, vérifie que les
plans couvrent toutes les phrases, conserve le récit entier par défaut (découpe seulement sur demande explicite),
et écrit les épisodes que les peintres lisent :

    construit/long_16x9/      episode.json + lines.json   le film long (pas d'étiquette PARTIE)
    construit/complet_9x16/   episode.json + lines.json   toute l'histoire en vertical (pour l'aperçu et la vérification)
    construit/partieN_9x16/   episode.json + lines.json   livraison verticale entière, ou parties si demandées
    construit/bruitages.json  les bruitages au temps absolu du film (lus par l'étape mixer)
    construit/decoupe.json    les versions : début, durée, phrases, étiquette, fondus

    python -m hstudio.histoire construire <dossier>"""
import copy
import importlib.util
import math
import os
import sys

from . import lib
from .common import KitError, Story, read_json, write_json

PART_MAX = 0.            # no studio duration cap; keep the complete story by default
TAIL_LONG = 1.4          # seconds kept after the last phrase of the long film
HUD_LONG_SHOTS = 2       # the long film shows the title over its first shots only
STYLES = ('ps1', 'voxel')


def load_lines(st):
    st.need(st.lignes, "fais l'étape phrases (après la voix)")
    lines = read_json(st.lignes)
    if not lines: raise KitError(f'{st.lignes} est vide')
    return lines


def load_story(st, lines):
    st.need(st.histoire, 'crée-le avec « nouveau » (modèle commenté) puis écris la mise en scène')
    lib.use_lines(lines)
    name = 'histoire_' + str(abs(hash(st.dir)))
    spec = importlib.util.spec_from_file_location(name, st.histoire)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, st.dir)
    try:
        spec.loader.exec_module(mod)
    except KitError:
        raise
    except Exception as e:
        import traceback
        tb = traceback.extract_tb(e.__traceback__)
        where = next((f'{fr.filename}:{fr.lineno}' for fr in reversed(tb) if os.path.abspath(fr.filename) == os.path.abspath(st.histoire)), '')
        raise KitError(f'histoire.py ne se charge pas ({where}) : {type(e).__name__} : {e}')
    finally:
        if sys.path and sys.path[0] == st.dir: sys.path.pop(0)
    for k in ('TITRE', 'LIEUX', 'CAST'):
        if not getattr(mod, k, None): raise KitError(f'histoire.py : il manque {k} (voir le modèle)')
    if not callable(getattr(mod, 'build', None)): raise KitError('histoire.py : il manque la fonction build(F)')
    style = getattr(mod, 'STYLE', 'ps1')
    if style not in STYLES: raise KitError(f"histoire.py : STYLE = {style!r} ; valeurs : 'ps1' ou 'voxel' (CONSOLE 2D et Blender passent par d'autres chemins, voir le guide)")
    return mod


def _run_build(mod, aspect, lines):
    F = lib.Film(aspect, getattr(mod, 'STYLE', 'ps1'), next(iter(mod.LIEUX)))
    try:
        mod.build(F)
    except KitError:
        raise
    except Exception as e:
        import traceback
        tb = traceback.extract_tb(e.__traceback__)
        where = next((f'ligne {fr.lineno}' for fr in reversed(tb) if fr.filename.endswith('histoire.py')), '')
        raise KitError(f'histoire.py, build({aspect}) {where} : {type(e).__name__} : {e}')
    if not F.shots: raise KitError(f'histoire.py, build({aspect}) : aucun plan (appelle F.shot(...))')
    n = len(lines); prev = -1
    for k, sh in enumerate(F.shots):
        a, b = sh['lines']
        if a != prev + 1:
            what = f'phrases {prev + 1} à {a - 1} sans plan' if a > prev + 1 else f'phrases {a} à {prev} dans deux plans'
            raise KitError(f'{aspect} : plan P{k} (phrases {a}-{b}) : {what}. Chaque plan commence juste après le précédent.')
        prev = b
    if prev != n - 1: raise KitError(f'{aspect} : les phrases {prev + 1} à {n - 1} n\'ont pas de plan (le dernier plan doit finir sur la phrase {n - 1})')
    return F


def _hud_title(mod):
    lines_ = getattr(mod, 'TITRE_HUD', None)
    if lines_: return [str(x) for x in lines_][:2]
    words = str(mod.TITRE).split(); out = ['']
    for w in words:
        if out[-1] and len(out[-1]) + 1 + len(w) > 16 and len(out) < 2: out.append(w)
        else: out[-1] = (out[-1] + ' ' + w).strip()
    return out


def _episode(mod, shots, part_label, duration, lipsync=None):
    ep = {'style': 'pixel3d', 'profile': 'production', 'genre': 'horror', 'music': 'none', 'title': str(mod.TITRE),
          'hud': {'title': _hud_title(mod), 'part': part_label, 'hearts': []},
          'sets': copy.deepcopy(mod.LIEUX), 'default_set': next(iter(mod.LIEUX)), 'cast': copy.deepcopy(mod.CAST), 'shots': shots,
          'grade': {'saturation': .55, 'exposure': 1.08}, 'eye_aim': False, 'eye_smooth': False}
    if getattr(mod, 'STYLE', 'ps1') == 'voxel':
        ep['mood'] = 'neutral'     # VOXEL: genre « horror » alone paints everything red (night, noir, thriller... in EPISODE)
        ep['dof'] = 0.; ep['mblur'] = .04   # owner's decision 9/11/2026: no blur (no depth of field, light motion blur) ; EPISODE may set them back
    ep.update(copy.deepcopy(getattr(mod, 'EPISODE', {}) or {}))
    ep['title'] = str(mod.TITRE); ep['duration'] = round(duration, 3)
    ep['hud'] = dict(ep.get('hud') or {}, title=_hud_title(mod), part=part_label)      # EPISODE may add to the HUD (clock...), never change title / PARTIE
    if lipsync: ep['lipsync'] = lipsync
    return ep


def _keywords(mod, lines, a, b):
    """episode `lines` metadata (keywords coloured in the subtitle), re-indexed for the version starting at phrase a"""
    out = {}
    for key, words in (getattr(mod, 'MOTS_CLES', {}) or {}).items():
        i = lib.idx(key)
        if a <= i <= b: out[str(i - a)] = {'keywords': [words] if isinstance(words, str) else list(words)}
    return out


def _lines_json(lines, a, b, t0):
    return [dict(start=round(l['start'] - t0, 3), end=round(l['end'] - t0, 3), text=l['text'], speaker=l.get('speaker', 'narrateur'), tone=l.get('tone'))
            for l in lines[a:b + 1]]


def part_limit(mod):
    """Zero/None means unlimited; a positive cap is an explicit, exceptional request."""
    try:
        value = float(getattr(mod, 'PARTIE_MAX', PART_MAX) or 0)
    except (TypeError, ValueError):
        raise KitError('PARTIE_MAX : écrire 0 (sans limite) ou une durée positive en secondes.') from None
    if not math.isfinite(value) or value < 0:
        raise KitError('PARTIE_MAX : écrire 0 (sans limite) ou une durée positive finie.')
    return value


def choose_cuts(lines, cands, duration, part_max):
    """fewest parts of at most `part_max` seconds, cut only at candidate phrases; among them the most balanced.
    -> list of phrase indices where parts 2.. begin"""
    if part_max is None or part_max == 0: return []
    n = len(lines)
    start = lambda c: 0. if c == 0 else lines[c]['start'] - lib.PRE
    end_before = lambda c: duration if c >= n else min(lines[c - 1]['end'] + 1.0, lines[c]['start'] - .03)
    cands = sorted({c for c in cands if 0 < c < n})
    if duration <= part_max: return []
    P = [0] + cands + [n]
    best = [None] * len(P); best[0] = (0, 0., None)                 # (parts, longest part, previous position)
    for j in range(1, len(P)):
        for i in range(j):
            if best[i] is None: continue
            d = end_before(P[j]) - start(P[i])
            if d > part_max: continue
            cand = (best[i][0] + 1, max(best[i][1], d), i)
            if best[j] is None or cand[:2] < best[j][:2]: best[j] = cand
    if best[-1] is not None:
        out, j = [], len(P) - 1
        while best[j][2] is not None:
            j = best[j][2]
            if j: out.append(P[j])
        return sorted(out)
    # explain where a cut point is missing
    bounds = P
    for i in range(len(bounds) - 1):
        d = end_before(bounds[i + 1]) - start(bounds[i])
        if d > part_max:
            raise KitError(f"Impossible de faire des Shorts de {part_max:.0f} s au plus : de la phrase {bounds[i]} ({start(bounds[i]):.1f} s) "
                           f"à la phrase {bounds[i + 1] - 1} il y a {d:.0f} s sans point de coupe.\n"
                           f"→ ajoute « # coupe » dans script.txt juste avant une phrase de ce passage qui suit un moment de suspense, puis relance phrases.")
    raise KitError('découpe impossible : ajoute des « # coupe » dans script.txt')


def build(folder, log=print, quiet=False):
    st = Story(folder); lines = load_lines(st); mod = load_story(st, lines)
    n = len(lines); style = getattr(mod, 'STYLE', 'ps1')
    pmax = part_limit(mod)
    formats = tuple(getattr(mod, 'FORMATS', ('16:9', '9:16')))
    if not formats or any(f not in ('16:9', '9:16') for f in formats): raise KitError("histoire.py : FORMATS = ('16:9', '9:16') (ou un seul des deux)")
    D = round(lines[-1]['end'] + float(getattr(mod, 'FIN_MARGE', TAIL_LONG)), 3)
    voice = os.path.abspath(st.voice)
    lip = (lambda t0: {'wav': voice, 'actors': 'all', 'offset': round(-t0, 3)}) if style == 'voxel' else (lambda t0: None)
    films = {asp: _run_build(mod, asp, lines) for asp in formats}
    versions = []; os.makedirs(st.construit, exist_ok=True)
    # sound cues: from the 16:9 build when there is one (they must not depend on the format)
    F0 = films.get('16:9') or films['9:16']
    cues = sorted(F0.cues, key=lambda c: c['t'])
    if '16:9' in films and '9:16' in films and len(films['16:9'].cues) != len(films['9:16'].cues):
        log('! les bruitages diffèrent entre 16:9 et 9:16 : seuls ceux du 16:9 sont mixés (n\'utilise pas v() pour les sons)')
    write_json(st.cues, cues)

    def write_version(vid, aspect, ep, lj, a, b, t0, dur, label):
        d = st.version_dir(vid); os.makedirs(d, exist_ok=True)
        write_json(os.path.join(d, 'episode.json'), ep); write_json(os.path.join(d, 'lines.json'), lj)
        versions.append(dict(id=vid, aspect=aspect, t0=round(t0, 3), dur=round(dur, 3), lines=[a, b], label=label,
                             shots=len(ep['shots'])))

    if '16:9' in films:
        shots = copy.deepcopy(films['16:9'].shots)
        for k, s_ in enumerate(shots): s_.setdefault('ui', {}).setdefault('hud', k < HUD_LONG_SHOTS)
        if not any((shots[-1].get('fx') or {}).get(k) for k in ('fade_out', 'black')): shots[-1]['fx'] = dict(shots[-1].get('fx') or {}, fade_out=1.4)
        ep = _episode(mod, shots, '', D, lip(0.)); kw = _keywords(mod, lines, 0, n - 1)
        if kw: ep['lines'] = kw
        write_version('long_16x9', '16:9', ep, _lines_json(lines, 0, n - 1, 0.), 0, n - 1, 0., D, '')
    parts = []
    if '9:16' in films:
        G = films['9:16']; shots9 = G.shots
        ep = _episode(mod, copy.deepcopy(shots9), '', D, lip(0.)); kw = _keywords(mod, lines, 0, n - 1)
        if kw: ep['lines'] = kw
        write_version('complet_9x16', '9:16', ep, _lines_json(lines, 0, n - 1, 0.), 0, n - 1, 0., D, '')
        cands = [i for i, l in enumerate(lines) if l.get('coupe')] + [lib.idx(x) for x in (getattr(mod, 'COUPES', []) or [])]
        cuts = choose_cuts(lines, cands, D, pmax)
        starts = {sh['lines'][0]: k for k, sh in enumerate(shots9)}
        for c in cuts:
            if c not in starts:
                k = next(k for k, sh in enumerate(shots9) if sh['lines'][0] < c <= sh['lines'][1])
                raise KitError(f"9:16 : la coupe choisie avant la phrase {c} tombe au milieu du plan P{k} (phrases {shots9[k]['lines'][0]}-{shots9[k]['lines'][1]}).\n"
                               f"→ dans histoire.py, commence un nouveau plan à la phrase {c} (tout « # coupe » doit commencer un plan).")
        for c in sorted(set(cands)):
            if c not in starts and c not in cuts and 0 < c < n: log(f'! « # coupe » avant la phrase {c} : aucun plan ne commence là (non choisie cette fois, mais commence un plan à cette phrase)')
        bounds = [0] + cuts + [n]; multi = len(bounds) > 2
        for p in range(len(bounds) - 1):
            a, b1 = bounds[p], bounds[p + 1]; b = b1 - 1
            k0, k1 = starts[a], (starts[b1] if b1 < n else len(shots9))
            sub = copy.deepcopy(shots9[k0:k1])
            pre = float(sub[0].get('pre', lib.PRE))
            t0 = 0. if a == 0 else lines[a]['start'] - pre
            t_end = D if b1 >= n else min(lines[b]['end'] + 1.0, lines[b1]['start'] - .03)
            fade = round(max(.15, min(.6, t_end - lines[b]['end'] - .05)), 2)
            for s_ in sub: s_['lines'] = [s_['lines'][0] - a, s_['lines'][1] - a]
            if a > 0: sub[0]['fx'] = dict(sub[0].get('fx') or {}, fade_in=.4)
            if b1 < n: sub[-1]['fx'] = dict(sub[-1].get('fx') or {}, fade_out=fade)
            elif not any((sub[-1].get('fx') or {}).get(k) for k in ('fade_out', 'black')): sub[-1]['fx'] = dict(sub[-1].get('fx') or {}, fade_out=1.4)
            label = f'PARTIE {p + 1}' if multi else ''
            ep = _episode(mod, sub, label, t_end - t0, lip(t0)); kw = _keywords(mod, lines, a, b)
            if kw: ep['lines'] = kw
            vid = f'partie{p + 1}_9x16'
            write_version(vid, '9:16', ep, _lines_json(lines, a, b, t0), a, b, t0, t_end - t0, label)
            versions[-1].update(fade_out=fade if b1 < n else None, fade_in=.4 if a > 0 else None)
            parts.append(versions[-1])
    dec = dict(titre=str(mod.TITRE), style=style, formats=list(formats), duree_long=D, partie_max=pmax,
               versions=versions, n_phrases=n, bruitages=len(cues))
    write_json(st.decoupe, dec)
    if not quiet:
        log(f"« {mod.TITRE} » ({style.upper()}) : {n} phrases, film long {D:.1f} s")
        for v_ in versions:
            log(f"  {v_['id']:<14s} {v_['aspect']}  {v_['shots']:3d} plans  phrases {v_['lines'][0]}-{v_['lines'][1]}  début {v_['t0']:7.2f} s  durée {v_['dur']:6.1f} s  {v_['label']}")
        log(f'  {len(cues)} bruitages → {st.cues}')
    return dec, mod


def versions(st, which=None):
    """the versions of decoupe.json; `which` : None/'tous' = the deliverable ones (long + parts), '16:9', '9:16', or ids"""
    dec = read_json(st.need(st.decoupe, "fais l'étape construire"))
    vs = dec['versions']
    if which in (None, 'tous', 'all'): return [v for v in vs if v['id'] != 'complet_9x16']
    if which in ('16:9', '9:16'): return [v for v in vs if v['aspect'] == which and v['id'] != 'complet_9x16']
    ids = [x.strip() for x in str(which).split(',')]
    out = [v for v in vs if v['id'] in ids]
    if not out: raise KitError(f"version inconnue : {which} (versions : {', '.join(v['id'] for v in vs)})")
    return out
