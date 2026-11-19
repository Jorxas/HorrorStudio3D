"""GEOMETRIC, CONTINUITY and IMAGE checks of a directed scene, from what the engine really decided (probe.py).

Two kinds of measurements feed them:
  * dense (10 Hz, every shot, cheap): the directed tracks and the keyed camera, read through the engine's own classes
    (`acting/directed.py`), against the solid boxes of the place -- a camera path through a wall, two bodies crossing,
    a body inside a wall, a position jump at a cut, the 180-degree line;
  * sparse (a few instants per camera setup): `Probe.measure` -- the engine's own frame build, the index buffer of a
    low-resolution trace and, in image mode, the low-resolution picture of the real painter.
Thresholds are named constants below; each Issue says the key to change."""
import math
import numpy as np
from .report import Issue, BLOQUANT, A_REVOIR, INFO
from . import probe as PB

DENSE_HZ = 10.
BODY_R = .21                     # half width of a PS1 body (torso .44 m)
GOWN_R = .45                     # a ball gown with panniers
JUMP_POS = .6                    # metres: a position change at a cut, same place, same actor, both seen
JUMP_YAW = math.radians(100)
PROMINENT = .07                  # a head taller than 7 % of the frame is a character the eye follows
NEAR_ACTOR_BLOCK, NEAR_ACTOR_WARN = .30, .15
NEAR_SET_BLOCK, NEAR_SET_WARN = .35, .12
DARK_MEAN, DARK_P95, BLACK_MEAN = 16., 34., 4.
BURN_WARN, BURN_BLOCK = .22, .45
WHITE_ACTOR = .30
SUB_FACE = .20
TIGHT_WARN, TIGHT_BLOCK = .55, .9


def _sev(cond_block): return BLOQUANT if cond_block else A_REVOIR


def active_key(keys, T):
    """index of the camera key in force at shot time T (the one before or at T)"""
    j = 0
    for i, k in enumerate(keys):
        if float(k.get('t', 0)) <= T + 1e-6: j = i
    return j


def setups(shot, dur):
    """camera setups of a shot: [(t0, t1)] split at keys with `cut`"""
    keys = ((shot.get('camera') or {}).get('keys') or []) if isinstance(shot.get('camera'), dict) else []
    starts = [0.] + [float(k['t']) for k in keys[1:] if k.get('cut') and 0 < float(k['t']) < dur]
    starts = sorted(set(starts))
    return [(a, (starts[i + 1] if i + 1 < len(starts) else dur)) for i, a in enumerate(starts)]


def sample_times(spans, shots, per_setup=3, every=1.6, cap=7):
    """[(g, k, setup)] -- a few instants per camera setup (start, middle, end, plus one every `every` s on long setups)"""
    out = []
    for k, (a, b) in enumerate(spans):
        if k >= len(shots): break
        for si, (s0, s1) in enumerate(setups(shots[k], b - a)):
            L = s1 - s0
            if L <= 0: continue
            ts = [s0 + min(.15, L * .3), s0 + L * .5, s1 - min(.12, L * .3)][:per_setup]
            if L > 2 * every:
                ts += [s0 + every * i for i in range(1, int(L / every)) if s0 + every * i < s1 - .3]
            ts = sorted(set(round(x, 3) for x in ts))
            if len(ts) > cap: ts = [ts[int(round(i * (len(ts) - 1) / (cap - 1)))] for i in range(cap)]
            out += [(a + x, k, si) for x in ts]
    return out


# ============================================================================================ dense checks
def dense(P, E, rep, style):
    """tracks + keyed camera at 10 Hz against the place's solid boxes"""
    from ..acting.directed import path_camera
    from ..engines.pixel3d import frame as F
    ctx = P.ctx; ac = ctx.get_acting(); shots = P.ep['shots']; cast = P.ep.get('cast') or {}
    radius = {aid: (GOWN_R if _gown(lk) else BODY_R) * float((lk or {}).get('scale', 1.) if isinstance(lk, dict) else 1.) for aid, lk in cast.items()}
    boundary = []                        # (k, setup, T, samp, cam) at each setup start / shot end: continuity + 180 degrees
    for k, (a, b) in enumerate(P.spans):
        if k not in ac.shots or k >= len(shots): continue
        sa = ac.shots[k]; shot = shots[k]; d = b - a
        cam = shot.get('camera') if isinstance(shot.get('camera'), dict) else {}
        try:
            st = ctx.get_set(shot.get('set', P.ep.get('default_set', 'etage_zero')))
            state = dict(P.ep.get('state', {}) or {}); state.update(shot.get('state', {}) or {}); state = F.apply_state_track(shot, F.resolve_state(state, .5), d * .5)
            solids = [bx for bx in st.scene(state, a + d * .5, .5).boxes if PB.solid(bx)]
        except Exception as e:
            rep.add(Issue('rendu.erreur', BLOQUANT, f'le lieu ne se construit pas ({type(e).__name__} : {e})', 'le rendu s\'arrêterait', 'vérifier `set` et `state` du plan', shot=k, t=a)); continue
        bounds = [(PB._r3d().wbounds(bx), bx) for bx in solids]
        n = max(2, int(d * DENSE_HZ) + 1)
        cam_in = []; close = {}; in_wall = {}
        su = setups(shot, d)
        for i in range(n):
            T = min(d - 1e-3, i / DENSE_HZ)
            samp = sa.sample(T)
            camT = None
            if cam.get('rig') == 'path' and cam.get('keys'):
                try:
                    pos_, tgt_, fov_, roll_, _s = path_camera(cam, samp, T); yaw_, pitch_ = F.look_angles(pos_, tgt_); camT = (pos_, yaw_, pitch_, roll_, fov_)
                except Exception: camT = None
            seen = lambda v: camT is None or _in_frame(camT, (v['x'], float(v.get('y', 0.)), v['z'])) or _in_frame(camT, (v['x'], float(v.get('y', 0.)), v['z']), 1.)
            # bodies crossing
            ids = [x for x in samp if samp[x].get('visible', True)]
            for p in range(len(ids)):
                for q in range(p + 1, len(ids)):
                    A, B = samp[ids[p]], samp[ids[q]]
                    if abs(float(A.get('y', 0.)) - float(B.get('y', 0.))) > 1.: continue
                    dd = math.hypot(A['x'] - B['x'], A['z'] - B['z'])
                    lim = radius.get(ids[p], BODY_R) + radius.get(ids[q], BODY_R) - .12
                    if dd < lim: close.setdefault((ids[p], ids[q]), []).append((T, dd, lim, seen(A) or seen(B)))
            # a body inside a wall (chest height; seated bodies are skipped: a chair back is not a wall)
            for x in ids:
                s = samp[x]
                if float(s['rig'].get('sit', 0.)) > .3 or float(s['rig'].get('kneel', 0.) or 0.) > .3: continue
                pt = np.array([s['x'], float(s.get('y', 0.)) + 1.25, s['z']], np.float32)
                for (lo, hi), bx in bounds:
                    if np.all(pt > lo) and np.all(pt < hi) and PB.inside(bx, pt, .05):
                        in_wall.setdefault(x, []).append((T, [round(float(v), 2) for v in PB.world_center(bx)], seen(s))); break
            # the keyed camera
            if camT is not None:
                pos = camT[0]
                if pos is not None:
                    pt = np.asarray(pos, np.float32)
                    for (lo, hi), bx in bounds:
                        if np.all(pt > lo) and np.all(pt < hi) and PB.inside(bx, pt, .02):
                            cam_in.append((T, [round(float(v), 2) for v in pos])); break
        for (x, y), lst in close.items():
            if len(lst) < 2: continue
            worst = min(lst, key=lambda e: e[1])
            deep = worst[1] < .5 * worst[2]; vis = any(e[3] for e in lst)
            rep.add(Issue('acteurs.traversent', _sev(deep) if vis else INFO, f'{x} et {y} se traversent ({worst[1]:.2f} m entre les centres, {len(lst) / DENSE_HZ:.1f} s)', 'deux corps ne peuvent pas occuper la même place : à l\'image l\'un entre dans l\'autre',
                          f'écarter leurs positions `p` d\'au moins {worst[2] + .12 - worst[1]:.2f} m (pistes {x} / {y})', shot=k, t=a + worst[0], t_shot=worst[0], who=f'{x} / {y}',
                          key=f'shots[{k}].tracks.{x}', auto=_static(shot, x) and _static(shot, y), pair=[x, y], dist=round(worst[1], 3), need=round(worst[2] + .12, 3)))
        for x, lst in in_wall.items():
            if len(lst) < 2: continue
            rep.add(Issue('acteur.dans_decor', BLOQUANT if any(e[2] for e in lst) else INFO, f'{x} est dans un mur ou un meuble (centre de la boîte {lst[0][1]}) pendant {len(lst) / DENSE_HZ:.1f} s' + ('' if any(e[2] for e in lst) else ' (hors du cadre)'), 'le corps traverse le décor',
                          f'déplacer `p` de {x} hors de l\'objet (voir le plan du lieu, docs/FORMAT_EPISODE.md)', shot=k, t=a + lst[0][0], t_shot=lst[0][0], who=x, key=f'shots[{k}].tracks.{x}', auto=_static(shot, x), box=lst[0][1]))
        if cam_in:
            T0 = cam_in[0][0]; j = active_key(cam.get('keys') or [], T0)
            rep.add(Issue('camera.dans_decor', BLOQUANT, f'la caméra passe dans un mur ou un meuble ({len(cam_in) / DENSE_HZ:.1f} s, position {cam_in[0][1]})', 'on voit l\'intérieur d\'une boîte, du noir ou l\'envers du décor',
                          f'déplacer `pos` de la clé de caméra {j} (ou ses voisines) de quelques dizaines de centimètres vers la cible', shot=k, t=a + T0, t_shot=T0, key=f'shots[{k}].camera.keys[{j}].pos', auto=True, cam=cam_in[0][1], setup=_setup_of(su, T0)))
        # boundary samples for continuity / 180 degrees
        if cam.get('rig') == 'path' and cam.get('keys'):
            for si, (s0, s1) in enumerate(su):
                for T, tag in ((min(d - 1e-3, s0 + .05), 'debut'), (max(0., s1 - .05), 'fin')):
                    samp = sa.sample(T)
                    try: pos, tgt, fov, _r, _s = path_camera(cam, samp, T)
                    except Exception: continue
                    yaw, pitch = F.look_angles(pos, tgt)
                    lk = (cam['keys'][active_key(cam['keys'], T)] or {}).get('look')
                    aim = lk.get('on') if isinstance(lk, dict) else min(((math.dist(lk, (v['x'], float(v.get('y', 0.)) + 1.55, v['z'])), x) for x, v in samp.items()), default=(9, None))
                    aim = aim if isinstance(aim, str) or aim is None else (aim[1] if aim[0] < .6 else None)
                    boundary.append(dict(k=k, setup=si, tag=tag, T=T, g=a + T, set=shot.get('set', P.ep.get('default_set')), cam=(pos, yaw, pitch, 0., fov), aim=aim,
                                         samp={x: (v['x'], float(v.get('y', 0.)), v['z'], v['heading'], bool(v.get('visible', True))) for x, v in samp.items()}))
    _continuity(boundary, rep)
    _line180(boundary, rep)


def _gown(lk):
    c = (lk or {}).get('costume') if isinstance(lk, dict) else None
    if not c: return False
    if isinstance(c, dict): c = c.get('preset') or c.get('type')
    return isinstance(c, str) and (c.startswith('dame') or c in ('gown', 'angelica', 'eliza', 'eliza_souvenir', 'peggy'))


def _static(shot, aid):
    ks = (shot.get('tracks') or {}).get(aid) or []
    ps = [tuple(round(v, 3) for v in x['p']) for x in ks if isinstance(x, dict) and isinstance(x.get('p'), list)]
    return len(set((p[0], p[2]) for p in ps)) <= 1


def _setup_of(su, T):
    for i, (a, b) in enumerate(su):
        if a <= T < b: return i
    return len(su) - 1


def _in_frame(cam, p, h=1.55):
    r3d = PB._r3d(); pos, yaw, pitch, roll, fov = cam
    u, v, z = r3d.project(pos, yaw, pitch, roll, fov, (p[0], p[1] + h, p[2]))
    return z > .2 and abs(u) < .95 and abs(v) < 1.0


def _continuity(B, rep):
    for e, f in zip(B, B[1:]):
        if e['tag'] != 'fin' or f['tag'] != 'debut' or e['set'] != f['set']: continue
        if not (f['k'] == e['k'] + 1 or (f['k'] == e['k'] and f['setup'] == e['setup'] + 1)): continue
        if f['g'] - e['g'] > .6: continue
        for x, pe in e['samp'].items():
            pf = f['samp'].get(x)
            if pf is None or not (pe[4] and pf[4]): continue
            seen_e, seen_f = _in_frame(e['cam'], pe), _in_frame(f['cam'], pf)
            dpos = math.hypot(pe[0] - pf[0], pe[2] - pf[2]); dyaw = abs((pe[3] - pf[3] + math.pi) % (2 * math.pi) - math.pi)
            if not (seen_e and seen_f): continue
            if max(_prominence(e['cam'], pe), _prominence(f['cam'], pf)) < PROMINENT: continue      # an extra far away in a wide shot: not noticeable
            if dpos > JUMP_POS:
                rep.add(Issue('raccord.position', A_REVOIR, f'{x} saute de {dpos:.2f} m à la coupe (de ({pe[0]:.2f}, {pe[2]:.2f}) à ({pf[0]:.2f}, {pf[2]:.2f}))', 'deux plans qui se suivent dans le même lieu : le spectateur voit le personnage se téléporter',
                              f'reprendre la position de fin ({pe[0]:.2f}, {pe[1]:.2f}, {pe[2]:.2f}) sur la première clé de {x} du plan {f["k"]}, ou montrer le déplacement', shot=f['k'], setup=f['setup'] or None, t=f['g'], who=x,
                              key=f'shots[{f["k"]}].tracks.{x}[0].p', value=[round(pe[0], 3), round(pe[1], 3), round(pe[2], 3)]))
            elif dyaw > JUMP_YAW:
                rep.add(Issue('raccord.orientation', A_REVOIR, f'{x} se retourne d\'un coup à la coupe ({math.degrees(dyaw):.0f}°)', 'à la coupe le personnage change de direction sans transition', f'reprendre `yaw` = {pe[3]:.2f} sur la première clé de {x} du plan {f["k"]}',
                              shot=f['k'], t=f['g'], who=x, key=f'shots[{f["k"]}].tracks.{x}[0].yaw', value=round(pe[3], 4)))


def _prominence(cam, p):
    """share of the frame height a head at p takes (a .6 m head with its hair)"""
    pos, _y, _p, _r, fov = cam; r3d = PB._r3d()
    dist = math.dist(pos, (p[0], p[1] + 1.55, p[2]))
    return .6 / max(dist, .1) / (2 * math.tan(math.radians(fov) / 2) * (r3d.FOV_K or 1.))


def _side(a, b, c):
    return (b[0] - a[0]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[0] - a[0])


def _line180(B, rep):
    starts = [e for e in B if e['tag'] == 'debut']
    for e, f in zip(starts, starts[1:]):
        if e['set'] != f['set'] or not (f['k'] == e['k'] + 1 or f['k'] == e['k']): continue
        ids = [x for x in e['samp'] if x in f['samp'] and e['samp'][x][4] and f['samp'][x][4]]
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                A, Bb = ids[i], ids[j]
                pa, pb = e['samp'][A], e['samp'][Bb]; qa, qb = f['samp'][A], f['samp'][Bb]
                if math.hypot(pa[0] - pb[0], pa[2] - pb[2]) > 4 or math.hypot(pa[0] - qa[0], pa[2] - qa[2]) > .5 or math.hypot(pb[0] - qb[0], pb[2] - qb[2]) > .5: continue
                se = [_in_frame(e['cam'], pa), _in_frame(e['cam'], pb)]; sf = [_in_frame(f['cam'], qa), _in_frame(f['cam'], qb)]
                if not (any(se) and any(sf)) or not (all(se) or all(sf) or (se[0] and sf[1]) or (se[1] and sf[0])): continue
                if not ({e.get('aim'), f.get('aim')} & {A, Bb}): continue                  # only the pair the cameras are about (a crowd is not a dialogue line)
                c1, c2 = e['cam'][0], f['cam'][0]
                s1, s2 = _side(pa, pb, c1), _side(qa, qb, c2)
                if abs(s1) < .15 or abs(s2) < .15 or s1 * s2 > 0: continue
                facing = _faces(pa, pb) and _faces(pb, pa)
                rep.add(Issue('raccord.180', _sev(facing), f'règle des 180° cassée entre {A} et {Bb} : la caméra passe de l\'autre côté de leur ligne', 'à la coupe les personnages échangent leur place à l\'écran : le spectateur perd qui regarde qui',
                              f'garder la caméra du même côté de la ligne {A}–{Bb} : déplacer `pos` du cadrage suivant de l\'autre côté (symétrique par rapport à la ligne)', shot=f['k'], setup=f['setup'] or None, t=f['g'],
                              who=f'{A} / {Bb}', key=f'shots[{f["k"]}].camera.keys'))


def _faces(p, q):
    h = p[3]; d = math.atan2(q[0] - p[0], q[2] - p[2])
    return abs((h - d + math.pi) % (2 * math.pi) - math.pi) < math.radians(50)


# ============================================================================================ sparse (probe) checks
def from_measures(M, E, rep, style, images):
    shots = E.ep.get('shots') or []
    for m in M:
        k = m.get('k'); g = m['g']
        if 'error' in m:
            rep.add(Issue('rendu.erreur', BLOQUANT, f'l\'image ne se calcule pas : {m["error"]}', 'le rendu s\'arrêterait sur cette image', 'lire le message : clé illisible, acteur absent, valeur hors limites', t=g)); continue
        shot = shots[k] if k is not None and k < len(shots) else {}
        T = m['T']; d = m['span'][1] - m['span'][0]; su = setups(shot, d); si = _setup_of(su, T)
        keys = ((shot.get('camera') or {}).get('keys') or []) if isinstance(shot.get('camera'), dict) else []
        j = active_key(keys, T); ck = f'shots[{k}].camera.keys[{j}]' if keys else f'shots[{k}].camera'
        W = dict(shot=k, setup=si or None, t=g, t_shot=T)
        # ---------------------------------------------------------------- the lens
        if m['cam_inside']:
            rep.add(Issue('camera.dans_decor', BLOQUANT, f'la caméra est dans un objet du décor (boîte de {m["cam_inside"][0]["size"]} m centrée en {m["cam_inside"][0]["center"]})', 'l\'image montre l\'intérieur d\'un mur ou d\'un meuble',
                          'avancer la caméra vers sa cible jusqu\'à sortir de l\'objet', key=ck + '.pos', auto=True, cam=m['cam']['pos'], **W))
        if m['below_floor'] or m['above_ceiling']:
            rep.add(Issue('camera.hors_lieu', BLOQUANT, 'la caméra est ' + ('sous le sol' if m['below_floor'] else 'au-dessus du plafond'), 'l\'image serait noire ou montrerait l\'envers du décor', 'remettre `pos[1]` entre le sol et le plafond (yeux : 1,5 à 1,7 m)', key=ck + '.pos', **W))
        if m.get('outside') and not m['sky']:
            rep.add(Issue('camera.hors_lieu', BLOQUANT, f'la caméra est hors des murs du lieu ({m["outside"]} directions sur 8 ne rencontrent aucun mur)', 'elle filme le vide autour du décor : image noire ou envers du décor',
                          'ramener `pos` dans le lieu (voir ses repères)', key=ck + '.pos', **W))
        elif m['miss'] > .6 and not m['sky']:
            rep.add(Issue('camera.hors_lieu', BLOQUANT, f'{m["miss"] * 100:.0f} % de l\'image ne touche rien', 'la caméra est hors du lieu ou regarde dans le vide : image noire', 'ramener `pos` dans le lieu et `look` vers l\'action (repères du lieu)', key=ck, **W))
        if m['near_set'] > NEAR_SET_WARN:
            rep.add(Issue('camera.collee', _sev(m['near_set'] > NEAR_SET_BLOCK), f'{m["near_set"] * 100:.0f} % de l\'image est un objet à moins de {PB.NEAR:.2f} m de l\'objectif', 'la caméra est collée à un mur, une cloison ou des planches : on ne voit rien',
                          'reculer ou décaler la caméra (≥ 0,5 m de tout objet), ou viser ailleurs', key=ck + '.pos', auto=m['near_set'] > NEAR_SET_BLOCK, **W))
        tgt = _target(shot, keys, j, m)
        for aid, share in (m.get('near_actor') or {}).items():
            if share < NEAR_ACTOR_WARN: continue
            rep.add(Issue('camera.bouchee', _sev(share > NEAR_ACTOR_BLOCK and aid != tgt), f'{aid} bouche {share * 100:.0f} % de l\'image (à moins de {PB.NEAR:.2f} m de l\'objectif)', 'un personnage collé à la caméra masque le plan (amorce trop grosse)',
                          f'éloigner la caméra de {aid} ou décaler {aid} (piste) hors de l\'axe', who=aid, key=ck + '.pos', **W))
        # ---------------------------------------------------------------- framing, speech, held objects
        acts = m.get('actors') or []
        on_screen = [a for a in acts if (a.get('proj') or {}).get('head') and a['proj']['head'][2] > .2 and abs(a['proj']['head'][0]) < 1.2 and abs(a['proj']['head'][1]) < 1.5]
        big = max(on_screen, key=lambda a: _head_share(a, m), default=None)
        for a in acts:
            pr = a.get('proj') or {}; hp = pr.get('head'); ch = pr.get('chin')
            if not hp: continue
            main = a['id'] == tgt or a.get('talking') or (big is not None and a['id'] == big['id'])
            visible_body = a.get('px', 1.) > .01 if 'px' in a else True
            if hp[2] > .2 and ch and ch[2] > .2 and abs(hp[0]) < 1. and hp[1] > .97 and abs(ch[0]) < 1. and ch[1] < .97 and visible_body and main:
                rep.add(Issue('cadre.tete_coupee', BLOQUANT, f'la tête de {a["id"]} est coupée par le haut du cadre (on voit le menton, pas les yeux)', 'tête coupée : le visage n\'est pas lisible',
                              'baisser `look[1]` (ou monter la caméra), ou élargir `fov`', who=a['id'], key=ck + '.look', **W))
            elif a['id'] == tgt and (hp[2] <= .2 or abs(hp[0]) > 1.08 or abs(hp[1]) > 1.08):
                rep.add(Issue('cadre.sujet_hors_cadre', BLOQUANT, f'{a["id"]}, visé par la caméra, est hors du cadre', 'le sujet du plan n\'est pas à l\'image', 'viser `{"on": "' + a['id'] + '", "h": 1.5}` ou corriger `look`', who=a['id'], key=ck + '.look', **W))
            elif main and hp[2] > .2 and .93 < abs(hp[0]) < 1.06 and abs(hp[1]) < 1.:
                rep.add(Issue('cadre.visage_bord', A_REVOIR, f'le visage de {a["id"]} est coupé par le bord {"droit" if hp[0] > 0 else "gauche"}', 'un visage à moitié dans le cadre se lit comme une erreur', 'recentrer `look` ou reculer la caméra', who=a['id'], key=ck + '.look', **W))
            size = _head_share(a, m)
            in_fr = hp[2] > .2 and abs(hp[0]) < .95 and abs(hp[1]) < .95
            if in_fr and main and size > TIGHT_WARN:
                rep.add(Issue('cadre.trop_serre', _sev(size > TIGHT_BLOCK), f'le visage de {a["id"]} prend {size * 100:.0f} % de la hauteur de l\'image', 'une tête PS1 / VOXEL est un gros cube : de trop près elle remplit l\'écran (règle : fov ≥ 56 depuis ≥ 1,5 m)',
                              'reculer la caméra (≥ 1,5 m du visage) ou élargir `fov`', who=a['id'], key=ck + '.pos', **W))
            if a.get('talking') and in_fr and size > .06:
                back = a.get('face_dot', 1.) < -.25 and (('face_px' not in a) or a.get('face_px', 0.) < .2 * max(a.get('head_px', 0.), 1e-9))
                if back:
                    rep.add(Issue('parole.dos', _sev(big is not None and a['id'] == big['id']), f'{a["id"]} parle mais on voit l\'arrière de sa tête', 'on entend parler quelqu\'un dont on ne voit que la nuque',
                                  f'tourner {a["id"]} vers la caméra (`yaw` de sa piste) ou placer la caméra devant son visage', who=a['id'], key=f'shots[{k}].tracks.{a["id"]}', **W))
            hold = a.get('hold')
            if hold and hold != 'none' and in_fr and size > .05 and 'hold_px' in a:
                if a['hold_px'] == 0 and a.get('px', 0.) > .02 and (a.get('gesture') or [None])[0] in ('show', 'phone', 'arm_up', 'extend', 'point', 'hold', 'reach'):
                    rep.add(Issue('objet.cache', A_REVOIR, f'l\'objet tenu par {a["id"]} ({hold}) est caché (mauvaise main pour ce cadrage)', 'l\'action de l\'objet n\'est pas visible : il est du côté opposé à la caméra',
                                  f'mettre `"side": "{"right" if a.get("left") else "left"}"` sur la clé de {a["id"]} (l\'objet passe dans l\'autre main)', who=a['id'], key=f'shots[{k}].tracks.{a["id"]}[side]',
                                  value='right' if a.get('left') else 'left', auto=style in ('ps1', 'console') or hold in ('flute', 'flute_pair', 'wine_glass', 'bouquet', 'fan', 'letter'), **W))
                elif a.get('hold_tex') and a['hold_px'] > .004 and a.get('hold_tex_px', 0.) == 0:
                    rep.add(Issue('objet.dos', _sev(a['hold_px'] > .03), f'on voit le dos de l\'objet tenu par {a["id"]} ({hold}) : son écran / son texte est de l\'autre côté', 'téléphone ou papier retourné : ce qu\'il doit montrer est invisible',
                                  f'tourner {a["id"]} (`yaw`) pour que l\'objet regarde la caméra, ou mettre la caméra devant l\'objet', who=a['id'], key=f'shots[{k}].tracks.{a["id"]}', **W))
        for tx in m.get('texts') or []:
            if tx.get('face') in (2, 3) and tx.get('part') != 'visage' and not _flat_note_near(E.ep, tx.get('center')):
                continue                       # a flat texture the ENGINE authored (keypad, printed log) is pre-transposed for its top face: only the scene's own flat notes are judged
            if tx.get('part') == 'visage':
                rep.add(Issue('visage.envers', A_REVOIR, f'le visage de {tx["owner"]} (allongé) est vu à l\'envers', 'vu depuis le haut de la tête, un visage allongé se lit à l\'envers', 'placer la caméra du côté des pieds', who=tx['owner'], key=ck + '.pos', **W)); continue
            what = {'miroir': 'en miroir', 'envers': 'à l\'envers', 'travers': 'de travers'}[tx['orient']]
            sev = BLOQUANT if (tx['orient'] != 'travers' and tx['px'] > .008 and tx.get('face') not in (2, 3)) else (A_REVOIR if tx['orient'] != 'travers' else INFO)
            held = tx.get('owner') is not None
            rep.add(Issue('texte.' + tx['orient'], sev, f'texte lu {what}' + (f' (objet tenu par {tx["owner"]})' if held else f' (objet du décor en {tx.get("center")})'), 'un papier, un écran ou un panneau illisible : le spectateur ne peut pas le lire',
                          ('tourner le personnage ou mettre la caméra devant l\'objet' if held else 'tourner l\'objet (`rot` + 2 dans le décor), ou le dresser au lieu de le poser à plat (`flat`)'),
                          who=tx.get('owner'), key=ck, auto=not held, text=tx, **W))
        for pr in m.get('actor_in_set') or []:
            pxa = next((a.get('px', 1.) for a in m.get('actors') or [] if a['id'] == pr['who']), 1.)
            rep.add(Issue('acteur.dans_decor', _sev(pr['part'] in ('torso', 'head')) if pxa > .002 else INFO, f'{pr["who"]} : {"le torse" if pr["part"] == "torso" else "la tête" if pr["part"] == "head" else "la robe"} est dans un objet du décor (boîte centrée en {pr["center"]})',
                          'le personnage traverse un mur, un meuble ou une cloison', f'déplacer `p` de {pr["who"]} hors de l\'objet', who=pr['who'], key=f'shots[{k}].tracks.{pr["who"]}', auto=_static(shot, pr['who']), box=pr['center'], **W))
        for pr in m.get('actor_pairs') or []:
            deep = pr['part_a'] in ('torso', 'head') and pr['part_b'] in ('torso', 'head')
            pxs = {a['id']: a.get('px', 1.) for a in m.get('actors') or []}
            vis = max(pxs.get(pr['a'], 1.), pxs.get(pr['b'], 1.)) > .002
            rep.add(Issue('acteurs.traversent', _sev(deep) if vis else INFO, f'{pr["a"]} et {pr["b"]} s\'interpénètrent ({pr["part_a"]} dans {pr["part_b"]})', 'deux corps occupent la même place à l\'image', f'écarter {pr["a"]} et {pr["b"]} (positions `p`)',
                          who=f'{pr["a"]} / {pr["b"]}', key=f'shots[{k}].tracks.{pr["a"]}', auto=_static(shot, pr['a']) and _static(shot, pr['b']), pair=[pr['a'], pr['b']], **W))
        if images and m.get('image'): _image(m, shot, rep, style, W, ck, big, tgt)


def _flat_note_near(ep, c, r=.45):
    if not c: return False
    for spec in (ep.get('sets') or {}).values():
        if not isinstance(spec, dict): continue
        for p in list(spec.get('props') or []) + [q for room in (spec.get('rooms') or []) for q in (room.get('props') or [])]:
            if isinstance(p, dict) and p.get('type') == 'note' and p.get('flat') and isinstance(p.get('at'), list) and math.hypot(p['at'][0] - c[0], p['at'][1] - c[2]) < r: return True
    return False


def _head_share(a, m):
    """share of the frame HEIGHT the head takes (projection; independent of occlusion)"""
    if 'dist' not in a or not m.get('cam'): return 0.
    fov = m['cam']['fov']; r3d = PB._r3d()
    return float(a.get('head_size', .4) * 1.5 / max(a['dist'], .05) / (2 * math.tan(math.radians(fov) / 2) * (r3d.FOV_K or 1.)))


def _target(shot, keys, j, m):
    """the actor the camera key aims at: `look.on`, or the actor whose head is within 0.7 m of the look point"""
    if not keys: return None
    lk = keys[j].get('look')
    if isinstance(lk, dict): return lk.get('on')
    if isinstance(lk, list) and len(lk) == 3:
        best = None; bd = .35
        for a in m.get('actors') or []:
            h = a.get('head')
            if h:
                dd = math.dist(h, lk)
                if dd < bd: best, bd = a['id'], dd
        return best
    return None


def _image(m, shot, rep, style, W, ck, big, tgt):
    im = m['image']; fx = m.get('fx') or {}; T = m['T']; span = m['span']
    if fx.get('black') or fx.get('flash') or fx.get('vanish') or fx.get('eyelid'): return
    if isinstance(fx.get('fade_in'), (int, float)) and T < float(fx['fade_in']) + .1: return
    if isinstance(fx.get('fade_out'), (int, float)) and (span[1] - m['g']) < float(fx['fade_out']) + .1: return
    expo_key = f'shots[{W["shot"]}].' + ('look.exposure' if style == 'voxel' else 'fx.expo')
    if not im.get('finite', True):
        rep.add(Issue('image.nan', BLOQUANT, 'des pixels de l\'image ne sont pas des nombres (NaN) : ils s\'étalent en carré lumineux', 'un calcul de lumière a divisé par zéro (lumière posée DANS un objet, rayon nul…)',
                      'chercher la lumière ou l\'objet émissif collé à la caméra ou à un personnage ; changer sa position ou sa taille', key=ck, **W))
    if style == 'voxel' and im.get('soft_squares') and not im.get('squares'):
        rep.add(Issue('image.carre', A_REVOIR, f'carré lumineux uni ({len(im["soft_squares"])}) entouré d\'un halo', 'c\'est la forme d\'un pixel non fini (NaN) étalé par le halo, ou d\'une source blanche carrée trop forte',
                      'regarder l\'image ; baisser `bloom` du `look` ou déplacer la lumière/poursuite en cause', key=f'shots[{W["shot"]}].look', squares=im['soft_squares'], **W))
    if style == 'voxel' and im.get('squares'):
        rep.add(Issue('image.carre', BLOQUANT, f'carré blanc uni à bords nets ({len(im["squares"])}) dans l\'image', 'c\'est la signature d\'un pixel non fini (NaN) étalé par le halo', 'baisser `bloom` du `look` du plan, ou déplacer la lumière/poursuite qui touche un objet de face', key=f'shots[{W["shot"]}].look', squares=im['squares'], **W))
    if im['mean'] < BLACK_MEAN and im['p95'] < 12:
        rep.add(Issue('image.noire', BLOQUANT, f'image noire (luminance moyenne {im["mean"]:.1f} / 255)', 'rien ne se voit : caméra hors du lieu, lumières éteintes ou objet devant l\'objectif', 'vérifier `pos` / `look` de la caméra et l\'éclairage du plan', key=ck, **W))
    elif im['mean'] < DARK_MEAN and im['p95'] < DARK_P95:
        rep.add(Issue('image.sombre', A_REVOIR, f'plan très sombre (95 % des pixels sous {im["p95"]:.0f} / 255)', 'même dans un film d\'horreur, il faut lire ce qui se passe', f'éclaircir : multiplier `{expo_key}` par {_brighten(im)} (ou ajouter une lumière)',
                      key=expo_key, value=_brighten(im), auto=True, p95=im['p95'], **W))
    burn = max(im['clip'], im.get('hi', 0.) * .75)                 # PS1 quantises and vignettes its highlights: a washed-out frame shows as > 200 rather than >= 240
    if burn > BURN_WARN:
        rep.add(Issue('image.brulee', _sev(burn > BURN_BLOCK), f'{im.get("hi", im["clip"]) * 100:.0f} % de l\'image est presque blanc (brûlé)', 'les détails disparaissent dans le blanc',
                      f'assombrir : multiplier `{expo_key}` par {_darken(im)}, ou baisser la lumière (poursuite `i`)',
                      key=expo_key, value=_darken(im), auto=True, clip=im['clip'], **W))
    if im['std'] < 5 and 18 < im['mean'] < 220:
        rep.add(Issue('image.voilee', A_REVOIR, f'image sans contraste (écart {im["std"]:.1f})', 'un nuage de fumée ou un brouillard au premier plan cache tout', 'baisser la densité de fumée près de la caméra, ou déplacer la caméra', key=f'shots[{W["shot"]}].state', **W))
    for a in m.get('actors') or []:
        if a.get('white', 0.) > WHITE_ACTOR and a.get('px', 0.) > .02:
            rep.add(Issue('image.blancs', A_REVOIR, f'{a["id"]} : {a["white"] * 100:.0f} % de ses pixels sont blanc pur (les blancs brillent)', 'vêtements ou visage brûlés par la lumière', 'baisser la poursuite (`i` ≤ 0,4 en gros plan) ou choisir des couleurs moins claires',
                          who=a['id'], key=f'shots[{W["shot"]}].stage_light', **W))
    sr = m.get('subs_rect')
    if sr:
        for a in m.get('actors') or []:
            fr = a.get('face_rect') if a.get('face_px', 0.) > .002 else None
            if not fr: continue
            it = _inter(sr, fr); ov = it / max(1e-9, (fr[1] - fr[0]) * (fr[3] - fr[2])); on_sub = it / max(1e-9, (sr[1] - sr[0]) * (sr[3] - sr[2]))
            if ov > SUB_FACE or on_sub > .5:
                main = a.get('talking') or a['id'] == tgt or (big is not None and a['id'] == big['id'])
                rep.add(Issue('soustitre.visage', _sev(main), f'le sous-titre est posé sur le visage de {a["id"]} ({on_sub * 100:.0f} % du texte sur le visage)', 'on ne voit plus la bouche ni les yeux de celui qu\'on regarde',
                              f'mettre `ui.subs` du plan à « {_best_band(sr, fr)} »', who=a['id'], key=f'shots[{W["shot"]}].ui.subs', value=_best_band(sr, fr), auto=True, face=fr, subs=sr, **W))


def _brighten(im):
    """exposure factor that brings the 95th percentile to ~55 / 255 (gamma 1.08 of the PS1 grade), capped"""
    return round(min(3.0, max(1.15, (70. / max(im['p95'], 4.)) ** (1 / 1.08))), 2)


def _darken(im):
    """exposure factor that brings the median near 90 / 255; the saturated share makes the median an underestimate, hence (1 - hi)"""
    return round(min(.85, max(.25, (90. / max(im['p50'], 1.)) ** (1 / 1.08) * (1. - im.get('hi', im['clip'])))), 2)


def _inter(a, b):
    return max(0., min(a[1], b[1]) - max(a[0], b[0])) * max(0., min(a[3], b[3]) - max(a[2], b[2]))


def _best_band(sr, fr):
    """the named subtitle band farthest from the face (y down: the face centre above the middle -> low)"""
    cy = (fr[2] + fr[3]) / 2.
    return 'low' if cy < .62 else 'top'
