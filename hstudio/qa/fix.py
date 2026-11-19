"""SAFE corrections of a directed scene, written into a COPY of the episode (never over the original), with a French summary of
every change (CORRECTIONS.md) and the report of what is left after the corrected copy has been checked again.

Only the issues marked `auto` are touched, and only in ways that do not re-stage the scene: re-stitch the shot coverage, rename
an unknown key to its obvious neighbour, move a camera key out of a wall along its own axis, push two static actors apart or a
static actor out of a wall, pass a held object to the other hand, stand a flat paper up to face the camera, brighten / darken a
shot, move a subtitle off a face, add the invisible track a keyed camera needs. Everything else stays for a human."""
import copy, json, math, re, shutil
from collections import defaultdict
from pathlib import Path
import numpy as np
from .report import BLOQUANT, A_REVOIR
from . import load as LD, probe as PB, checks as CK


UNDOABLE = ('objet.cache', 'soustitre.visage', 'image.sombre', 'image.brulee', 'camera.collee', 'texte.miroir', 'texte.envers')


def _path(ep, key):
    """'shots[3].tracks.moi[2].hold' -> (parent container, last segment)"""
    toks = re.findall(r'[^.\[\]]+|\[\d+\]', key)
    cur = ep
    for t in toks[:-1]:
        cur = cur[int(t[1:-1])] if t.startswith('[') else cur.setdefault(t, {}) if isinstance(cur, dict) else cur[t]
    last = toks[-1]
    return cur, (int(last[1:-1]) if last.startswith('[') else last)


class Fixer:
    def __init__(self, E, style):
        self.E = E; self.style = style; self.ep = copy.deepcopy(E.ep); self.changes = []; self._P = None; self._solids = {}

    def log(self, key, before, after, why):
        self.changes.append(dict(cle=key, avant=before, apres=after, pourquoi=why, issue=getattr(self, 'cur', None)))

    @property
    def P(self):
        if self._P is None: self._P = PB.Probe(self.E.ep, self.E.lines, self.E.aspect, self.E.duration)
        return self._P

    def solids(self, k):
        if k not in self._solids:
            from ..engines.pixel3d import frame as F
            P = self.P; shot = P.ep['shots'][k]; a, b = P.spans[k]; d = b - a
            st = P.ctx.get_set(shot.get('set', P.ep.get('default_set', 'etage_zero')))
            state = dict(P.ep.get('state', {}) or {}); state.update(shot.get('state', {}) or {}); state = F.apply_state_track(shot, F.resolve_state(state, .5), d * .5)
            sc = st.scene(state, a + d * .5, .5)
            self._solids[k] = ([b_ for b_ in sc.boxes if PB.solid(b_)], float(getattr(sc, 'floor_y', 0.)), sc.ceil_y)
        return self._solids[k]

    # ------------------------------------------------------------------------------------------------ time and names
    def restitch(self):
        shots = self.ep.get('shots') or []; n = len(self.E.lines); nxt = 0
        for k, s in enumerate(shots):
            l = s.get('lines')
            if not (isinstance(l, list) and len(l) == 2): l = [nxt, nxt]
            a, b = int(l[0]), int(l[1])
            if b < a: a, b = b, a
            na, nb = nxt, max(nxt, min(b, n - 1))
            if [na, nb] != [a, b]: self.log(f'shots[{k}].lines', l, [na, nb], 'plans recollés : aucun trou, aucun chevauchement')
            s['lines'] = [na, nb]; nxt = nb + 1
        if shots and nxt < n:
            self.log(f'shots[{len(shots) - 1}].lines[1]', shots[-1]['lines'][1], n - 1, 'le dernier plan va jusqu\'à la dernière phrase'); shots[-1]['lines'][1] = n - 1

    def set_value(self, i):
        try: cont, last = _path(self.ep, i.key)
        except (KeyError, IndexError, TypeError, ValueError): return False
        if i.code == 'cle.inconnue' and isinstance(cont, dict) and last in cont and last not in ('gesture', 'hold', 'face', 'subs', 'side'):
            cont[i.value] = cont.pop(last); self.log(i.key, last, i.value, 'clé inconnue renommée en son plus proche voisin connu'); return True
        before = cont.get(last) if isinstance(cont, dict) else (cont[last] if isinstance(last, int) and last < len(cont) else None)
        cont[last] = i.value; self.log(i.key, before, i.value, i.msg); return True

    # ------------------------------------------------------------------------------------------------ camera
    def cam_target(self, k, key):
        lk = key.get('look')
        if isinstance(lk, dict):
            sa = self.P.ctx.get_acting().shots.get(k)
            s = sa.sample(float(key.get('t', 0.))).get(lk.get('on')) if sa else None
            if s is None: return None
            return np.array([s['x'] + float(lk.get('dx', 0.)), float(s.get('y', 0.)) + float(lk.get('h', 1.4)), s['z'] + float(lk.get('dz', 0.))], np.float32)
        return np.array(lk, np.float32) if isinstance(lk, list) and len(lk) == 3 else None

    def near_share(self, k, pos, tgt, fov):
        from ..engines.pixel3d import frame as F
        r3d = PB._r3d(); sol, fy, ceil = self.solids(k)
        yaw, pitch = F.look_angles(tuple(pos), tuple(tgt))
        D = PB._dirs((pos, yaw, pitch, 0., fov), 12, 12)
        t, ib = r3d.trace(np.asarray(pos, np.float32), D, sol, fy, ceil, False, None)
        return float((np.isfinite(t) & (t < PB.NEAR) & (ib >= 0)).mean())

    def free_camera(self, i):
        m = re.match(r'shots\[(\d+)\]\.camera\.keys\[(\d+)\]', i.key or '')
        if not m: return False
        k, j = int(m.group(1)), int(m.group(2))
        keys = (self.ep['shots'][k].get('camera') or {}).get('keys') or []
        if j >= len(keys) or not isinstance(keys[j].get('pos'), list): return False
        key = keys[j]; pos = np.array(key['pos'], np.float32); tgt = self.cam_target(k, key)
        if tgt is None: return False
        sol, _fy, _c = self.solids(k); fov = float(key.get('fov', 56.))
        d = tgt - pos; L = float(np.linalg.norm(d))
        if L < .3: return False
        for f in [x * .04 for x in range(1, 19)] + [-x * .05 for x in range(1, 11)]:
            c = pos + d * f
            if f > 0 and np.linalg.norm(tgt - c) < .9: break
            if any(PB.inside(b, c, .02) for b in sol): continue
            if self.near_share(k, c, tgt, fov) > .05: continue
            new = [round(float(v), 3) for v in c]
            self.log(f'shots[{k}].camera.keys[{j}].pos', key['pos'], new, f'caméra sortie du décor le long de son axe ({f * L:+.2f} m vers la cible)')
            # a key copied after this one with the very same position (a held frame) moves with it
            for jj in range(j + 1, len(keys)):
                if keys[jj].get('pos') == key['pos'] and not keys[jj].get('cut'): keys[jj]['pos'] = list(new)
                else: break
            key['pos'] = new; return True
        return False

    # ------------------------------------------------------------------------------------------------ actors
    def _set_p(self, k, aid, fn, why):
        ks = (self.ep['shots'][k].get('tracks') or {}).get(aid) or []
        for x in ks:
            if isinstance(x.get('p'), list) and len(x['p']) == 3:
                old = list(x['p']); x['p'] = fn(x['p'])
                if old != x['p']: self.log(f'shots[{k}].tracks.{aid}[{ks.index(x)}].p', old, x['p'], why)

    def separate(self, i):
        k = i.shot; a, b = i.data.get('pair') or (None, None)
        tr = self.ep['shots'][k].get('tracks') or {}
        if a not in tr or b not in tr: return False
        pa = next(x['p'] for x in tr[a] if 'p' in x); pb = next(x['p'] for x in tr[b] if 'p' in x)
        v = np.array([pa[0] - pb[0], pa[2] - pb[2]], np.float64); dist = float(np.linalg.norm(v))
        need = float(i.data.get('need') or (2 * CK.BODY_R + .12))
        if dist >= need: return False
        v = v / dist if dist > 1e-3 else np.array([1., 0.])
        s = (need - dist) / 2. + .03
        self._set_p(k, a, lambda p: [round(float(p[0] + v[0] * s), 3), p[1], round(float(p[2] + v[1] * s), 3)], f'{a} et {b} se traversaient : écartés de {2 * s:.2f} m')
        self._set_p(k, b, lambda p: [round(float(p[0] - v[0] * s), 3), p[1], round(float(p[2] - v[1] * s), 3)], f'{a} et {b} se traversaient : écartés de {2 * s:.2f} m')
        return True

    def out_of_wall(self, i):
        k = i.shot; aid = i.who; tr = self.ep['shots'][k].get('tracks') or {}
        if aid not in tr: return False
        p = next((x['p'] for x in tr[aid] if 'p' in x), None)
        if p is None: return False
        sol, _fy, _c = self.solids(k)
        box = None; hint = i.data.get('box')
        for h in ([hint[1]] if hint else []) + [p[1] + 1.25, p[1] + 1.6, p[1] + .95]:
            pt = np.array([p[0], h, p[2]], np.float32)
            cands = [b for b in sol if PB.inside(b, pt, .0)]
            if hint: cands = sorted(cands, key=lambda b: float(np.linalg.norm(PB.world_center(b) - np.asarray(hint, np.float32))))
            if cands: box = cands[0]; break
        if box is None and hint:                                   # the torso box is off the actor's axis: take the box the engine named, at the actor's height
            near = [b for b in sol if float(np.linalg.norm(PB.world_center(b) - np.asarray(hint, np.float32))) < .06]
            if near: box = near[0]; pt = np.array([p[0], float(hint[1]), p[2]], np.float32)
        if box is None: return False
        q = pt if box.inst is None else (pt - box.inst.piv) @ box.inst.R
        best = None
        for ax in (0, 2):
            for sgn, edge in ((-1, box.lo[ax]), (1, box.hi[ax])):
                dd = abs(q[ax] - edge)
                if best is None or dd < best[0]: best = (dd, ax, sgn, edge)
        _dd, ax, sgn, edge = best
        q2 = q.copy(); q2[ax] = edge + sgn * (CK.BODY_R + .12)
        w = q2 if box.inst is None else box.inst.R @ q2 + box.inst.piv
        if any(PB.inside(b, np.array([w[0], pt[1], w[2]], np.float32), .0) for b in sol): return False
        dx, dz = float(w[0] - pt[0]), float(w[2] - pt[2])
        self._set_p(k, aid, lambda p_: [round(p_[0] + dx, 3), p_[1], round(p_[2] + dz, 3)], f'{aid} était dans un mur ou un meuble : sorti de {math.hypot(dx, dz):.2f} m')
        return True

    def other_hand(self, i):
        k = i.shot; aid = i.who; ks = (self.ep['shots'][k].get('tracks') or {}).get(aid) or []
        if not ks: return False
        T = i.t_shot or 0.
        cand = [x for x in ks if float(x.get('t', 0)) <= T + 1e-6 and ('hold' in x or 'gesture' in x)] or ks[:1]
        x = cand[-1]; before = x.get('side'); x['side'] = i.value
        self.log(f'shots[{k}].tracks.{aid}[{ks.index(x)}].side', before, i.value, f'l\'objet tenu par {aid} était caché : il passe dans l\'autre main')
        return True

    # ------------------------------------------------------------------------------------------------ image, subtitles, paper
    def exposure(self, k, factor, why):
        sh = self.ep['shots'][k]
        if self.style == 'voxel':
            lk = sh.setdefault('look', {}); before = lk.get('exposure'); lk['exposure'] = round(float(before or 1.) * factor, 3); self.log(f'shots[{k}].look.exposure', before, lk['exposure'], why)
        else:
            fx = sh.setdefault('fx', {}); before = fx.get('expo')
            if isinstance(before, list): return False
            fx['expo'] = round(float(before or 1.) * factor, 3); self.log(f'shots[{k}].fx.expo', before, fx['expo'], why)
        return True

    def stand_paper(self, i):
        """a flat `note` of the place read in mirror / upside down: stood up on its table, facing the camera"""
        tx = i.data.get('text') or {}; c = tx.get('center')
        if not c: return False
        cam = None
        for s_name, spec in (self.ep.get('sets') or {}).items():
            props = list(spec.get('props') or []) + [p for r in (spec.get('rooms') or []) for p in (r.get('props') or [])]
            for p in props:
                if not (isinstance(p, dict) and p.get('type') == 'note' and isinstance(p.get('at'), list)): continue
                if math.hypot(p['at'][0] - c[0], p['at'][1] - c[2]) > .5: continue
                if cam is None:
                    m = re.match(r'shots\[(\d+)\]\.camera\.keys\[(\d+)\]', i.key or '')
                    keys = (self.ep['shots'][int(m.group(1))].get('camera') or {}).get('keys') or [] if m else []
                    cam = keys[int(m.group(2))].get('pos') if m and int(m.group(2)) < len(keys) else None
                if not isinstance(cam, list): return False
                dx, dz = cam[0] - p['at'][0], cam[2] - p['at'][1]
                fronts = {0: (0, -1), 1: (-1, 0), 2: (0, 1), 3: (1, 0)}
                rot = max(fronts, key=lambda r: fronts[r][0] * dx + fronts[r][1] * dz)
                before = {k_: p.get(k_) for k_ in ('flat', 'rot')}
                p.pop('flat', None); p['rot'] = rot
                self.log(f'sets.{s_name}.props[note at {p["at"]}]', before, {'flat': None, 'rot': rot}, 'papier à plat lu en miroir : dressé sur la table, face à la caméra')
                return True
        return False


def apply(E, rep, style):
    """-> (corrected episode, [changes], [issues left for a human])"""
    F = Fixer(E, style); manual = []; done_shot = defaultdict(set)
    issues = rep.merged()
    if any(i.auto and i.code.startswith('temps.') and i.code != 'temps.duree' for i in issues): F.restitch()
    expo = defaultdict(list)
    for i in issues:
        if not i.auto: continue
        ok = False; F.cur = [i.code, i.shot, i.who]
        try:
            if i.code.startswith('temps.') and i.code != 'temps.duree': ok = True
            elif i.code in ('temps.duree', 'titre.incoherent', 'titre.etiquette', 'cle.inconnue', 'voxel.etat_milieu') and i.value is not None: ok = F.set_value(i)
            elif i.code == 'camera.path_sans_pistes':
                F.ep['shots'][i.shot]['tracks'] = {'_cam': [{'t': 0, 'p': [0., -50., -80.], 'yaw': 0., 'vis': 0}]}
                F.log(f'shots[{i.shot}].tracks', None, '_cam (piste invisible)', 'une caméra en clés n\'est lue que dans un plan qui a une piste'); ok = True
            elif i.code in ('camera.dans_decor', 'camera.collee'): ok = F.free_camera(i)
            elif i.code == 'acteurs.traversent': ok = F.separate(i)
            elif i.code == 'acteur.dans_decor': ok = F.out_of_wall(i)
            elif i.code == 'objet.cache':
                if 'side' not in done_shot[(i.shot, i.who)]: ok = F.other_hand(i); done_shot[(i.shot, i.who)].add('side')
                else: ok = True
            elif i.code in ('image.sombre', 'image.brulee'): expo[i.shot].append(i); ok = True
            elif i.code == 'soustitre.visage':
                if 'subs' not in done_shot[(i.shot, None)]:
                    ui = F.ep['shots'][i.shot].setdefault('ui', {}); before = ui.get('subs'); ui['subs'] = i.value
                    F.log(f'shots[{i.shot}].ui.subs', before, i.value, i.msg); done_shot[(i.shot, None)].add('subs')
                ok = True
            elif i.code.startswith('texte.'): ok = F.stand_paper(i)
        except Exception as e:
            ok = False; i.data['erreur_correction'] = f'{type(e).__name__} : {e}'
        if not ok: manual.append(i)
    for k, lst in expo.items():
        codes = {i.code for i in lst}; F.cur = [lst[0].code, k, None]
        if len(codes) > 1: manual += lst; continue
        f = max(i.value for i in lst) if 'image.sombre' in codes else min(i.value for i in lst)
        if not F.exposure(k, float(f), lst[0].msg): manual += lst
    return F.ep, F.changes, manual


def correct(folder, out=None, aspect=None, style=None, images=False, workers=6, log=print):
    """check, correct what is safe in a COPY, check the copy again. -> dict(out, changes, before, after)"""
    from .run import verify, write
    E = LD.load(folder, aspect, style)
    before = verify(folder, E.aspect, E.style, images=images, workers=workers, log=log, E=E)
    ep2, changes, manual = apply(E, before, E.style)
    src = Path(folder).resolve()
    dst = Path(out).resolve() if out else src.parent / (src.name + '_corrige')
    if dst == src: raise ValueError('le dossier corrigé doit être différent de l\'original (jamais d\'écrasement)')
    dst.mkdir(parents=True, exist_ok=True)
    (dst / 'episode.json').write_text(json.dumps(ep2, ensure_ascii=False, indent=1), encoding='utf-8')
    if (src / 'lines.json').exists(): shutil.copyfile(src / 'lines.json', dst / 'lines.json')
    E2 = LD.load(dst, E.aspect, E.style)
    after = verify(dst, E.aspect, E.style, images=images, workers=workers, log=log, E=E2)
    # a correction that did not make its problem go away is taken back (the copy keeps only what helped)
    still = {(i.code, i.shot, i.who) for i in after.merged() if i.severity in (BLOQUANT, A_REVOIR)}
    undo = [c for c in changes if c.get('issue') and tuple(c['issue']) in still and c['issue'][0] in UNDOABLE]
    if undo:
        for c in reversed(undo):
            try:
                cont, last = _path(ep2, c['cle'])
                if c['avant'] is None and isinstance(cont, dict): cont.pop(last, None)
                else: cont[last] = c['avant']
            except Exception: continue
            changes.remove(c)
        (dst / 'episode.json').write_text(json.dumps(ep2, ensure_ascii=False, indent=1), encoding='utf-8')
        after = verify(dst, E.aspect, E.style, images=images, workers=workers, log=log, E=LD.load(dst, E.aspect, E.style))
    for c in changes: c.pop('issue', None)
    write(before, dst / '_qa', 'rapport_avant'); write(after, dst / '_qa', 'rapport_apres')
    md = ['# Corrections automatiques', '', f'- Original (non modifié) : `{src}`', f'- Copie corrigée : `{dst}`',
          f'- Avant : {before.counts()}', f'- Après : {after.counts()}', '', f'## Changements ({len(changes)})', '']
    for c in changes: md.append(f'- `{c["cle"]}` : {json.dumps(c["avant"], ensure_ascii=False)} → {json.dumps(c["apres"], ensure_ascii=False)} — {c["pourquoi"]}')
    left = [i for i in after.merged() if i.severity in (BLOQUANT, A_REVOIR)]
    md += ['', f'## Reste à corriger à la main ({len(left)})', '']
    for i in sorted(left, key=lambda i: (i.severity != BLOQUANT, i.shot if i.shot is not None else -1)):
        md.append(f'- [{i.severity}] [{i.code}] {i.where()} : {i.msg} — {i.fix}')
    (dst / 'CORRECTIONS.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
    return dict(out=str(dst), changes=changes, before=before, after=after, manual=manual)
