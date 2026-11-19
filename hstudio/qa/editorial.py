"""EDITORIAL checks of a directed scene: what can be judged on episode.json + lines.json alone, without the engine drawing
anything -- time (lines, shots, holes, overlaps, duration of a Short), titles, unknown names silently ignored by the engine,
camera keys, who speaks and who moves his mouth. Every check returns Issues (report.py); nothing here modifies the episode."""
import difflib, math, re, unicodedata
from .report import Issue, BLOQUANT, A_REVOIR, INFO
from .load import spans as _spans

SUBS = ('mid', 'low', 'top', 'off')
CAM_KEY_FIELDS = {'t', 'pos', 'look', 'fov', 'roll', 'shake', 'cut', 'hold'}
LOOK_FIELDS = {'on', 'h', 'dx', 'dz'}
NARRATORS = {'', 'narrateur', 'narratrice', 'narrator', 'voix', 'voice', 'off', None}


def known_names(style):
    """the names the engines really draw (registries read from the code, never a frozen copy)"""
    from ..acting import gestures as G, directed as D
    from ..engines.pixel3d import poses as P, assets as A, hotel_cast as HC, costumes as COS
    from ..engines.pixel3d import sets as _S  # Registers props after the sets module has finished importing.
    HC.register()
    from ..engines.pixel3d import objets as OD
    OD.register()
    gest = set(G.GESTURES) | set(P.GESTURES) | {'idle', 'none'}
    faces = set(A.FACE_KINDS)
    vox_faces = set()
    try:
        from ..voxelgpu.contract import EXPRESSIONS
        vox_faces = set(EXPRESSIONS) - faces
    except Exception: pass
    hold = set(P.HOLD_ITEMS) | set(HC.NEW_ITEMS) | set(COS.ITEMS) | {'none'}
    track = {'t', 'p', 'cut', 'y'} | set(D.NUM) | set(D.VEC) | set(D.HOLD)
    return dict(gesture=gest, face=faces, vox_face=vox_faces, hold=hold, track=track)


def _close(name, pool):
    m = difflib.get_close_matches(str(name), sorted(pool), n=1, cutoff=.75)
    return m[0] if m else None


def _norm_title(s):
    s = unicodedata.normalize('NFD', str(s or '')).encode('ascii', 'ignore').decode().upper()
    return re.sub(r'[^A-Z0-9]+', ' ', s).strip()


def held_values(keys, name):
    """[(t, value)] of a held key (face, gesture, talk...) along a track: the value holds until a later key changes it"""
    out = []
    for k in sorted(keys, key=lambda k: float(k.get('t', 0))):
        if name in k: out.append((float(k.get('t', 0)), k[name]))
    return out


def talk_intervals(keys, t_end):
    """[(a, b)] shot-relative intervals where the track has talk on"""
    out = []; cur = None
    for t, v in held_values(keys, 'talk'):
        on = bool(v)
        if on and cur is None: cur = t
        elif not on and cur is not None: out.append((cur, t)); cur = None
    if cur is not None: out.append((cur, t_end))
    return [(a, min(b, t_end)) for a, b in out if min(b, t_end) > a]


def check(E, rep):
    ep, lines, aspect, style = E.ep, E.lines, E.aspect, E.style
    shots = [s for s in ep.get('shots') or [] if isinstance(s, dict)]
    n = len(lines)
    # ---------------------------------------------------------------- lines (the voice timing)
    for i, ln in enumerate(lines):
        a, b = float(ln.get('start', 0)), float(ln.get('end', 0))
        if b < a: rep.add(Issue('temps.ligne', BLOQUANT, f'la phrase {i} finit avant de commencer ({a:.2f} → {b:.2f} s)', 'les plans sont calés sur les phrases : un plan aurait une durée négative',
                                'refaire l\'alignement (lines.json) ou corriger `start` / `end`', key=f'lines.json[{i}]'))
        if i and a < float(lines[i - 1].get('start', 0)) - 1e-6:
            rep.add(Issue('temps.ligne', BLOQUANT, f'la phrase {i} commence avant la phrase {i - 1}', 'l\'ordre des phrases fixe l\'ordre des plans', 'trier lines.json par `start`', key=f'lines.json[{i}].start'))
    # ---------------------------------------------------------------- shot coverage: contiguous, no hole, no overlap
    nxt = 0
    for k, s in enumerate(shots):
        l = s.get('lines')
        if not (isinstance(l, list) and len(l) == 2 and all(isinstance(x, int) for x in l)):
            rep.add(Issue('temps.plans', BLOQUANT, f'`lines` illisible : {l!r}', 'chaque plan couvre [première, dernière] phrase', 'écrire `"lines": [a, b]` avec deux entiers', shot=k, key=f'shots[{k}].lines', auto=True)); continue
        a, b = l
        if b < a: rep.add(Issue('temps.plans', BLOQUANT, f'`lines` à l\'envers : {l}', 'la dernière phrase est avant la première', f'écrire `[{b}, {a}]`', shot=k, key=f'shots[{k}].lines', value=[b, a], auto=True))
        if n and (a >= n or b >= n): rep.add(Issue('temps.plans', BLOQUANT, f'le plan couvre la phrase {max(a, b)} mais il n\'y a que {n} phrases', 'le moteur rattacherait le plan ailleurs sans le dire', f'borner `lines` à {n - 1}', shot=k, key=f'shots[{k}].lines', auto=True))
        if a > nxt: rep.add(Issue('temps.trou', BLOQUANT, f'trou : les phrases {nxt} à {a - 1} ne sont couvertes par aucun plan', 'le validateur les recollerait au plan précédent en silence : on verrait la mauvaise image', f'faire commencer le plan {k} à la phrase {nxt} ou ajouter un plan', shot=k, key=f'shots[{k}].lines[0]', value=nxt, auto=True))
        elif a < nxt: rep.add(Issue('temps.chevauchement', BLOQUANT, f'chevauchement : le plan {k} recommence à la phrase {a} alors que le plan précédent va jusqu\'à {nxt - 1}', 'deux plans sur la même phrase : l\'un des deux serait réduit à rien', f'faire commencer le plan {k} à la phrase {nxt}', shot=k, key=f'shots[{k}].lines[0]', value=nxt, auto=True))
        nxt = max(nxt, b + 1)
    if shots and n and nxt < n:
        rep.add(Issue('temps.trou', BLOQUANT, f'les dernières phrases ({nxt} à {n - 1}) n\'ont pas de plan', 'la fin de la voix tomberait sur le dernier plan sans le dire', f'prolonger le dernier plan jusqu\'à la phrase {n - 1}', shot=len(shots) - 1, key=f'shots[{len(shots) - 1}].lines[1]', value=n - 1, auto=True))
    if not shots: rep.add(Issue('temps.plans', BLOQUANT, 'aucun plan', 'rien à filmer', 'écrire `shots`'))
    # ---------------------------------------------------------------- duration, Shorts
    dur = E.duration
    if lines and dur < float(lines[-1]['end']) - .05:
        rep.add(Issue('temps.duree', BLOQUANT, f'`duration` ({dur:.2f} s) coupe la dernière phrase (fin à {lines[-1]["end"]:.2f} s)', 'la voix serait coupée', f'mettre `duration` à au moins {lines[-1]["end"] + .8:.2f}', key='duration', value=round(lines[-1]['end'] + .8, 2), auto=True))
    # Vertical framing does not impose a platform duration limit or require a story split.
    # ---------------------------------------------------------------- titles: one title per story, only the PART label changes
    hud = ep.get('hud') or {}; title = ep.get('title'); ht = ' '.join(hud.get('title') or [])
    if title and ht and _norm_title(title) != _norm_title(ht):
        rep.add(Issue('titre.incoherent', BLOQUANT, f'titre « {title} » mais le bandeau affiche « {ht} »', 'une histoire = un seul titre partout (règle du propriétaire)', f'mettre `hud.title` à {[title]}', key='hud.title', value=[title], auto=True))
    part = str(hud.get('part') or '')
    if part and not re.fullmatch(r'(PARTIE \d+|VIDÉO INTERACTIVE|VIDEO INTERACTIVE|FIN)', part.upper()):
        rep.add(Issue('titre.etiquette', A_REVOIR, f'étiquette « {part} » inhabituelle', 'seule l\'étiquette PARTIE N / VIDÉO INTERACTIVE change d\'une partie à l\'autre', 'écrire `"part": "PARTIE N"`', key='hud.part'))
    m = re.search(r'partie\s*_?(\d+)', E.dir.name.lower())
    if m and part and re.fullmatch(r'PARTIE \d+', part.upper()) and part.upper() != f'PARTIE {int(m.group(1))}':
        rep.add(Issue('titre.etiquette', BLOQUANT, f'le dossier est la partie {m.group(1)} mais l\'étiquette dit « {part} »', 'l\'étiquette de partie est la seule chose qui change entre les parties', f'mettre `hud.part` à « PARTIE {int(m.group(1))} »', key='hud.part', value=f'PARTIE {int(m.group(1))}', auto=True))
    _siblings(E, rep, title or ht)
    # ---------------------------------------------------------------- per shot: camera, tracks, names, speech
    K = known_names(style)
    try: sp = _spans(ep, lines, dur)
    except Exception as e:
        rep.add(Issue('temps.plans', BLOQUANT, f'calage des plans impossible ({type(e).__name__} : {e})', 'le moteur ne peut pas placer les plans dans le temps', 'vérifier `lines` des plans et lines.json')); sp = []
    voiced = [(float(l['start']), float(l['end'])) for l in lines if str(l.get('text', '')).strip()]
    clip = bool((ep.get('lipsync') or {}).get('wav'))            # music clip: the mouth follows the separated vocals, not the lines
    for k, s in enumerate(shots):
        a, b = sp[k] if k < len(sp) else (0., 0.)
        d = b - a
        tracks = s.get('tracks') or {}
        cam = s.get('camera') if isinstance(s.get('camera'), dict) else {}
        if d < .3 and k < len(sp):
            rep.add(Issue('temps.plan_court', A_REVOIR, f'plan de {d:.2f} s', 'un plan si court se lit comme un saut d\'image', 'regrouper la phrase avec le plan voisin', shot=k, t=a))
        if style != 'console':
            _camera(rep, k, s, cam, tracks, d, a)
        _tracks(rep, k, tracks, d, a, K, style)
        ui = s.get('ui') or {}
        if ui.get('subs') is not None and ui['subs'] not in SUBS:
            rep.add(Issue('cle.inconnue', BLOQUANT, f'`ui.subs` = {ui["subs"]!r} inconnu', 'le moteur mettrait le sous-titre au milieu sans le dire', f'une valeur parmi {", ".join(SUBS)}', shot=k, key=f'shots[{k}].ui.subs', value='low', auto=True))
        stype = ((ep.get('sets') or {}).get(s.get('set', ep.get('default_set'))) or {}).get('type', s.get('set', ep.get('default_set')))
        if style == 'voxel' and stype != 'theatre_bal':            # the theatre records its state per frame for VOXEL (stage.theatre.frames)
            for kk, v in (s.get('state') or {}).items():
                if isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v):
                    rep.add(Issue('voxel.etat_milieu', A_REVOIR, f'état `{kk}` = {v} : en VOXEL il vaut son milieu ({(v[0] + v[1]) / 2:g}) sur tout le plan', 'PS1 le fait glisser, VOXEL non : les deux styles ne montreraient pas la même chose',
                                  f'écrire `[{v[0]}, {v[1]}, 0, {round(d, 2)}]` (temps de début et de fin dans le plan)', shot=k, key=f'shots[{k}].state.{kk}', value=[v[0], v[1], 0, round(d, 2)], auto=True))
        # speech: a mouth that moves while nobody speaks, a line spoken by an actor whose mouth stays shut
        for aid, keys in tracks.items():
            if not isinstance(keys, list): continue
            for (ta, tb) in talk_intervals(keys, d):
                if clip: continue
                silent = _unvoiced(a + ta, a + tb, voiced)
                if silent > .6:
                    rep.add(Issue('parole.sans_voix', A_REVOIR, f'{aid} parle (`talk`) pendant {silent:.1f} s sans voix', 'la bouche bouge dans le vide : on croit à une erreur de synchro',
                                  f'mettre `"talk": 0` sur la clé de {aid} à t = {round(tb if tb < d else ta + .1, 2)} (ou caler `talk` sur la phrase)', shot=k, t=a + ta, t_shot=ta, who=aid, key=f'shots[{k}].tracks.{aid}[talk]'))
        ll = s.get('lines')
        rng = range(ll[0], ll[1] + 1) if isinstance(ll, list) and len(ll) == 2 and all(isinstance(x, int) for x in ll) else range(0)
        for i in rng:
            if not (0 <= i < n): continue
            who = _speaker(ep, lines, i)
            if who and who in tracks and not clip:
                la, lb = float(lines[i]['start']) - a, float(lines[i]['end']) - a
                if not any(ta < lb and tb > la for ta, tb in talk_intervals(tracks[who], d)):
                    rep.add(Issue('parole.voix_sans_bouche', A_REVOIR, f'la phrase {i} est dite par {who} mais sa bouche ne bouge pas', 'on entend parler un personnage à l\'image qui garde la bouche fermée',
                                  f'ajouter `"talk": 1` sur une clé de {who} à t = {max(0., round(la, 2))} et `"talk": 0` à t = {round(lb, 2)}', shot=k, t=float(lines[i]['start']), who=who, key=f'shots[{k}].tracks.{who}'))
    if ep.get('words') and style == 'ps1':
        rep.add(Issue('mots3d.ps1', INFO, f'{len(ep["words"])} mots 3D : ils ne sont peints que par VOXEL', 'le style PS1 ne les dessine pas', 'rendre en VOXEL, ou écrire le texte autrement'))


def _unvoiced(a, b, voiced):
    """seconds of [a, b] covered by no voiced line (with 0.25 s of tolerance at each line edge)"""
    if b <= a: return 0.
    cov = 0.
    for (s, e) in voiced:
        lo, hi = max(a, s - .25), min(b, e + .25)
        if hi > lo: cov += hi - lo
    return max(0., (b - a) - cov)


def _speaker(ep, lines, i):
    sp = str(lines[i].get('speaker') or '').strip().lower()
    lab = ((ep.get('lines') or {}).get(str(i)) or {}).get('label')
    cast = ep.get('cast') or {}
    for cand in (sp, str(lab or '').strip().lower()):
        if cand in NARRATORS: continue
        if cand in cast: return cand
    return None


def _camera(rep, k, s, cam, tracks, d, a):
    keys = cam.get('keys') or []
    if cam.get('rig') == 'path':
        if not tracks:
            rep.add(Issue('camera.path_sans_pistes', BLOQUANT, 'caméra en clés (`rig: path`) dans un plan sans `tracks`', 'le moteur ne lit une caméra `path` que dans un plan qui a des pistes : il en placerait une autre, ailleurs',
                          'ajouter une piste invisible (`"_cam": [{"t": 0, "p": [0, -50, -80], "yaw": 0, "vis": 0}]`) ou passer en `"preset": "free"`', shot=k, key=f'shots[{k}].tracks', auto=True))
        if not keys:
            rep.add(Issue('camera.sans_cles', BLOQUANT, 'caméra `path` sans clés', 'le moteur ne sait pas où mettre la caméra', 'écrire au moins une clé `{"t": 0, "pos": [...], "look": [...], "fov": 56}`', shot=k, key=f'shots[{k}].camera.keys')); return
    for j, ck in enumerate(keys):
        if not isinstance(ck, dict): continue
        bad = sorted(set(ck) - CAM_KEY_FIELDS)
        if bad: rep.add(Issue('cle.inconnue', A_REVOIR, f'clé(s) de caméra inconnue(s) {bad}', 'le moteur les ignore sans le dire', f'clés connues : {", ".join(sorted(CAM_KEY_FIELDS))}', shot=k, key=f'shots[{k}].camera.keys[{j}]'))
        if 'pos' not in ck or 'look' not in ck:
            rep.add(Issue('camera.cle_incomplete', BLOQUANT, f'clé de caméra {j} sans `pos` ou sans `look`', 'le rendu s\'arrêterait sur une erreur', 'écrire `pos` et `look`', shot=k, key=f'shots[{k}].camera.keys[{j}]'))
        lk = ck.get('look')
        if isinstance(lk, dict):
            if lk.get('on') not in tracks:
                rep.add(Issue('camera.cible_absente', BLOQUANT, f'la caméra suit {lk.get("on")!r}, absent des pistes du plan', 'le rendu s\'arrête (« l\'acteur n\'est pas dans le plan »)', f'viser un acteur du plan ({", ".join(sorted(tracks)) or "aucun"}) ou un point [x, y, z]', shot=k, key=f'shots[{k}].camera.keys[{j}].look.on'))
            bad = sorted(set(lk) - LOOK_FIELDS)
            if bad: rep.add(Issue('cle.inconnue', A_REVOIR, f'clé(s) de visée inconnue(s) {bad}', 'ignorées sans le dire', 'clés connues : on, h, dx, dz', shot=k, key=f'shots[{k}].camera.keys[{j}].look'))
        if j and isinstance(keys[j - 1], dict) and float(ck.get('t', 0)) < float(keys[j - 1].get('t', 0)):
            rep.add(Issue('camera.ordre', BLOQUANT, f'clés de caméra dans le désordre ({keys[j - 1].get("t")} puis {ck.get("t")})', 'la caméra sauterait en arrière', 'trier les clés par `t`', shot=k, key=f'shots[{k}].camera.keys[{j}].t'))
        f = ck.get('fov')
        if isinstance(f, (int, float)) and not (8 <= f <= 120):
            rep.add(Issue('camera.fov', BLOQUANT, f'`fov` = {f}', 'au-delà de 8 à 120 degrés l\'image se déforme ou devient un point', 'garder `fov` entre 20 et 100', shot=k, key=f'shots[{k}].camera.keys[{j}].fov'))
        if isinstance(ck.get('t'), (int, float)) and d > 0 and float(ck['t']) > d + .05 and j < len(keys) - 1 and float(ck['t']) < 400:
            rep.add(Issue('camera.cle_hors_plan', INFO, f'clé de caméra à t = {ck["t"]} après la fin du plan ({d:.2f} s)', 'elle ne sera jamais atteinte', 'la ramener dans le plan ou la supprimer', shot=k, key=f'shots[{k}].camera.keys[{j}].t'))


def _tracks(rep, k, tracks, d, a, K, style):
    for aid, keys in tracks.items():
        if not isinstance(keys, list) or not keys:
            rep.add(Issue('piste.vide', BLOQUANT, f'piste de {aid} vide', 'le rendu s\'arrêterait', 'écrire au moins une clé avec `p`', shot=k, who=aid, key=f'shots[{k}].tracks.{aid}')); continue
        ks = sorted((x for x in keys if isinstance(x, dict)), key=lambda x: float(x.get('t', 0)))
        if not ks or 'p' not in ks[0]:
            rep.add(Issue('piste.sans_position', BLOQUANT, f'la première clé de {aid} n\'a pas de position `p`', 'le rendu s\'arrête (« la première clé doit donner la position »)', 'ajouter `"p": [x, y, z]` à la première clé', shot=k, who=aid, key=f'shots[{k}].tracks.{aid}[0].p'))
        for j, x in enumerate(keys):
            if not isinstance(x, dict): continue
            bad = sorted(n for n in x if n not in K['track'] and not n.startswith('x_'))
            for nm in bad:
                sug = _close(nm, K['track'])
                rep.add(Issue('cle.inconnue', BLOQUANT if sug else A_REVOIR, f'clé de piste inconnue `{nm}` ({aid})', 'le moteur l\'ignore sans le dire : ce que la clé demandait n\'arrivera pas',
                              f'remplacer par `{sug}`' if sug else 'clés connues : ' + ', '.join(sorted(K['track'])), shot=k, who=aid, key=f'shots[{k}].tracks.{aid}[{j}].{nm}', value=sug, auto=bool(sug)))
            if 'p' in x and not (isinstance(x['p'], list) and len(x['p']) == 3 and all(isinstance(v, (int, float)) and math.isfinite(v) for v in x['p'])):
                rep.add(Issue('piste.position', BLOQUANT, f'position illisible {x["p"]!r} ({aid})', '`p` = [x, y, z] en mètres', 'écrire trois nombres', shot=k, who=aid, key=f'shots[{k}].tracks.{aid}[{j}].p'))
            for field, pool, sev in (('gesture', K['gesture'], BLOQUANT), ('hold', K['hold'], BLOQUANT), ('face', K['face'], A_REVOIR)):
                v = x.get(field)
                if v is None or v in pool: continue
                if field == 'face' and v in K['vox_face']:
                    if style == 'ps1':
                        rep.add(Issue('cle.visage_voxel', A_REVOIR, f'expression « {v} » ({aid}) : elle n\'existe qu\'en VOXEL', 'PS1 dessine alors un visage neutre', f'choisir une expression commune, par ex. « {_close(v, K["face"]) or "neutral"} »', shot=k, who=aid, key=f'shots[{k}].tracks.{aid}[{j}].face'))
                    continue
                sug = _close(v, pool)
                what = {'gesture': 'geste', 'hold': 'objet tenu', 'face': 'expression'}[field]
                rep.add(Issue('cle.inconnue', sev, f'{what} « {v} » inconnu ({aid})', f'le moteur l\'ignore sans le dire ({"rien en main" if field == "hold" else "pas de geste" if field == "gesture" else "visage neutre"})',
                              f'remplacer par « {sug} »' if sug else f'choisir dans la liste ({len(pool)} noms, docs/FORMAT_EPISODE.md)', shot=k, who=aid, key=f'shots[{k}].tracks.{aid}[{j}].{field}', value=sug, auto=bool(sug)))
            if x.get('side') is not None and x['side'] not in ('left', 'right'):
                rep.add(Issue('cle.inconnue', BLOQUANT, f'`side` = {x["side"]!r} ({aid})', 'seuls "left" et "right" existent', 'écrire "left" ou "right"', shot=k, who=aid, key=f'shots[{k}].tracks.{aid}[{j}].side'))
        # speed between two keys without a cut: a slide the walk cycle cannot follow
        pk = [(float(x.get('t', 0)), x['p'], bool(x.get('cut'))) for x in ks if isinstance(x.get('p'), list) and len(x['p']) == 3]
        for (t0, p0, _), (t1, p1, c1) in zip(pk, pk[1:]):
            if c1 or t1 <= t0: continue
            v = math.hypot(p1[0] - p0[0], p1[2] - p0[2]) / (t1 - t0)
            if v > 6.0:
                rep.add(Issue('piste.vitesse', BLOQUANT if v > 12 else A_REVOIR, f'{aid} se déplace à {v:.1f} m/s entre t = {t0:g} et t = {t1:g}', 'plus vite qu\'un sprint : les pieds glissent, on croit à une téléportation',
                              'espacer les clés, ou mettre `"cut": true` sur la seconde si c\'est un saut voulu', shot=k, t=a + t0, t_shot=t0, who=aid, key=f'shots[{k}].tracks.{aid}'))


def _siblings(E, rep, title):
    """the other parts of the same story (sibling folders with an episode.json) must carry the same title"""
    try:
        import json
        par = E.dir.parent; mine = _norm_title(title)
        if not mine: return
        for d in sorted(par.iterdir()):
            if d == E.dir or not (d / 'episode.json').exists(): continue
            o = json.loads((d / 'episode.json').read_text(encoding='utf-8'))
            ot = o.get('title') or ' '.join((o.get('hud') or {}).get('title') or [])
            if ot and _norm_title(ot) != mine and (re.search(r'partie|part', d.name.lower()) or re.search(r'partie|part', E.dir.name.lower())):
                rep.add(Issue('titre.parties', BLOQUANT, f'la partie voisine « {d.name} » s\'appelle « {ot} », celle-ci « {title} »', 'une histoire = un seul titre partout ; seule l\'étiquette PARTIE N change',
                              f'donner le même titre aux deux dossiers', key='title'))
    except Exception: pass
