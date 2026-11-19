"""python tools/check_objets_drame.py [--planches [--out DOSSIER] [--styles ps1,voxel]]

Contrôle ciblé du lot d'objets détaillés « drame » (engines/pixel3d/objets_drame.py + voxelgpu/b_objets_drame.py) : od_carnet (posé, et tenu
od_carnet / od_carnet_ouvert / od_carnet_montre), od_bouquet, od_billet. tools/check_objets.py vérifie déjà tous les lots avec leurs réglages par
défaut ; ici, TOUTES les variantes (ouvert, mouillé, chaque dessin, légende, couleurs nommées, debout, sans photo, lisse, texte) sont vérifiées, SANS GPU :
  1. présence des deux versions (PS1 et VOXEL), posées et tenues ;
  2. échelle réelle (carnet 0,21 x 0,15 x 0,02, bouquet ~0,45, billet 0,15 x 0,07) et mêmes dimensions en PS1 et en VOXEL, coût (boîtes) ;
  3. déterminisme (deux constructions = mêmes boîtes, mêmes images) ;
  4. textes et images lisibles (rendus de face sur le lanceur de rayons PS1, comparés à leurs miroirs) ; règle flat() ; décalcomanies VOXEL
     jamais enfouies ; tranches d'une image découpée (billet froissé, toile de part et d'autre de l'élastique) redistribuées en miroir pour VOXEL ;
  5. objets tenus : le carnet fermé DEVANT le poing (visible avec le geste `hold`), pages du carnet ouvert vers soi / vers l'avant ;
  6. contenu par la clé d'épisode : le réglage d'`od_carnet` vaut pour les trois carnets tenus, un réglage propre passe devant ; couleurs nommées
     (même passées par `objets.held`, qui fait tuple(« brun »)) ;
  7. opt-in : le lot n'ajoute que des noms `od_` neufs, ne touche aucun nom d'avant ; rien d'aléatoire dans ses sources.
`--planches` : planches des variantes et des inserts serrés (PS1 + VOXEL), dans docs/catalogue/objets_drame/ ; rendus VOXEL sous le verrou GPU commun
C:\\Users\\demo\\Videos\\studio_horreur_v3\\_verrous\\gpu.lock (attendu s'il existe, posé, retiré). Un insert VOXEL se filme à 1 m au moins avec un objectif
serré (fov 9 à 14) : la mise au point VOXEL ne descend pas sous 1 m (voxelgpu_js/engine/film_unified.js), plus près l'objet est flou."""
import json, math, os, sys, time, hashlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))
import numpy as np
FAIL = []


def check(name, ok, detail=''):
    print(('OK   ' if ok else 'FAIL ') + name + (f'   {detail}' if detail else ''), flush=True)
    if not ok: FAIL.append(name)


def sig(boxes):
    h = hashlib.sha1()
    for b in boxes:
        h.update(np.concatenate([np.asarray(b.lo, np.float32), np.asarray(b.hi, np.float32), np.asarray(b.col, np.float32), [b.emis, float(b.grain), float(b.dissolve)]]).astype(np.float32).tobytes())
        for k in sorted(b.tex or {}): h.update(np.ascontiguousarray(b.tex[k]).tobytes())
    return h.hexdigest()[:12]


def bbox(bx):
    v = [b for b in bx if not b.hidden]; return np.min([b.lo for b in v], 0), np.max([b.hi for b in v], 0)


POSED = {'od_carnet': [{}, {'ouvert': True}, {'ouvert': True, 'legende': 'LINA, 6 ANS'}, {'ouvert': True, 'dessin': 'deux_amis', 'legende': 'NOUS DEUX'},
                       {'ouvert': True, 'dessin': 'trois_amis', 'couleur': 'brun'}, {'ouvert': True, 'dessin': 'vide'}, {'mouille': True}, {'ouvert': True, 'mouille': True, 'legende': 'LINA'},
                       {'couleur': [120, 40, 40]}, {'ouvert': True, 'dessin': 'portrait'}],
         'od_bouquet': [{}, {'debout': True}, {'photo': False}, {'photo': 'vide'}, {'couleur': 'rose', 'ruban': [200, 200, 200]}, {'debout': True, 'papier': 'blanc'}],
         'od_billet': [{}, {'froisse': False}, {'texte': ['PARIS', 'VOIE 4', '2E CLASSE']}, {'couleur': 'rose', 'froisse': True}]}
HELD = {'od_carnet': [{}, {'mouille': True}, {'vers_soi': True}, {'couleur': 'brun'}], 'od_carnet_ouvert': [{}, {'dessin': 'deux_amis'}, {'montre': True}, {'mouille': True}],
        'od_carnet_montre': [{}, {'legende': 'LINA, 6 ANS'}, {'vers_soi': True}], 'od_bouquet': [{}, {'photo': False}, {'vers_soi': True}],
        'od_billet': [{}, {'froisse': False}, {'vers_soi': True}]}


def held_ps1(OD, name, cfg):
    OD.use({'name': 'detailles', 'decors': True, 'tenus': True, 'contenu': {name: dict(cfg)}})
    try: return OD.held(name, (0., 1., 0.), 1, {})
    finally: OD.use(None)


def held_vox(OD, BO, name, cfg, mirror=False):
    OD.use({'name': 'detailles', 'decors': True, 'tenus': True, 'contenu': {name: dict(cfg)}})
    try: return BO.held_contract(name, mirror=mirror)
    finally: OD.use(None)


def main():
    from hstudio.engines.pixel3d import sets as S, objets as OD, objets_tex as T, r3d, objets_drame as D
    from hstudio.voxelgpu import b_objets as BO, b_props as BP, b_objets_drame as V
    import check_objets as CO
    OD.configure(None)
    print('\n1. deux versions, posées et tenues')
    for k in POSED: check(f'{k} posé : PS1 et VOXEL', k in OD.KINDS and k in BO.VOX)
    for h in HELD: check(f'{h} tenu : PS1 et VOXEL', h in OD.HELD and h in BO.HELD_VOX)
    check('lot chargé (PS1 et VOXEL), noms tous neufs (od_)', 'objets_drame' in [n for n, _ in OD.LOTS] and 'b_objets_drame' in [n for n, _ in BO.LOTS] and all(n.startswith('od_') for n in list(POSED) + list(HELD)))

    print('\n2. échelle réelle, mêmes dimensions PS1 / VOXEL, coût')
    lo, hi = bbox(D.b_carnet_ferme(D.COVERS['bleu_vert'], False)[:4]); sz = hi - lo
    check('carnet fermé : 0,21 x 0,15 x 0,02 m (plats, pages, couverture)', abs(sz[0] - .21) < .01 and abs(sz[2] - .15) < .01 and abs(sz[1] - .02) < .004, f'{sz.round(3)}')
    lo, hi = bbox(OD.prop('od_carnet', {'ouvert': True})); check('carnet ouvert : deux pages, 0,42 m de large', .41 < hi[0] - lo[0] < .46, f'{(hi - lo).round(3)}')
    lo, hi = bbox(OD.prop('od_bouquet', {'debout': True})); check('bouquet debout : 0,45 m de haut environ, penché vers +z', .42 < hi[1] - lo[1] < .5 and hi[2] > .15, f'{(hi - lo).round(3)}')
    lo, hi = bbox(OD.prop('od_billet', {'froisse': False})); check('billet : 0,15 x 0,07 m', abs(hi[0] - lo[0] - .15) < .005 and abs(hi[2] - lo[2] - .07) < .005)
    bad = []; cost = []
    for k, ps in POSED.items():
        for p in ps:
            a = [b for b in OD.prop(k, p) if not b.hidden]; v = BO.native_boxes(k, p)
            (pl, ph), (vl, vh) = bbox(a), bbox(v); r = np.maximum(vh - vl, .02) / np.maximum(ph - pl, .02); dc = np.abs((vl + vh) / 2 - (pl + ph) / 2).max()
            if not ((.7 < r).all() and (r < 1.4).all() and dc < .03): bad.append(f'{k}{p}:{r.round(2)}')
            if len(a) > 220 or len(v) > 2200: bad.append(f'{k}{p}: {len(a)} PS1 / {len(v)} VOXEL')
            cost.append(f'{k}:{len(a)}/{len(v)}')
    check('chaque variante : VOXEL aux dimensions de PS1 (x0,7..1,4), PS1 < 220 boîtes, VOXEL < 2 200 blocs', not bad, '; '.join(bad[:4]) or ' '.join(sorted(set(cost))[:6]))

    print('\n3. déterminisme')
    nd = []
    for k, ps in POSED.items():
        for p in ps:
            if sig(OD.prop(k, p)) != sig(OD.prop(k, p)) or sig(BO.native_boxes(k, p)) != sig(BO.native_boxes(k, p)): nd.append(f'{k}{p}')
    for h, cs in HELD.items():
        for c in cs:
            if sig(held_ps1(OD, h, c)) != sig(held_ps1(OD, h, c)) or json.dumps(held_vox(OD, BO, h, c), sort_keys=True) != json.dumps(held_vox(OD, BO, h, c), sort_keys=True): nd.append(f'{h}{c}')
    check('mêmes réglages = mêmes boîtes, images et contrats (toutes variantes)', not nd, str(nd[:4]))
    src = open(D.__file__, encoding='utf-8').read() + open(V.__file__, encoding='utf-8').read()
    check('sources du lot sans hasard ni horloge', not any(w in src for w in ('random', 'time.time', 'datetime')))

    print('\n4. textes et images dans le bon sens')
    r3d.configure('16:9'); n_ok = n_all = 0; worst = []; flat_bad = []
    for k, ps in POSED.items():
        for p in ps:
            bx = [b for b in OD.prop(k, p) if not b.hidden]
            for (b, key) in CO.textured(bx):
                r = CO.read_face(bx, b, key)
                if r is None or (r[0] < .25 and max(r[1], r[2]) < .25): continue
                n_all += 1; good = r[0] > max(r[1], r[2]) + .05; n_ok += good
                if not good: worst.append(f'{k}{p}:{key}:{r[0]:.2f}/{r[1]:.2f}/{r[2]:.2f}')
            for src_, bb in (('ps1', bx), ('voxel', BO.native_boxes(k, p))):
                for b in bb:
                    for key, tx in (b.tex or {}).items():
                        if (key == 3) != T.is_flat(tx): flat_bad.append(f'{src_}:{k}{p}')
    for h, cs in HELD.items():
        for c in cs:
            bx = held_ps1(OD, h, c)
            for (b, key) in CO.textured(bx):
                r = CO.read_face(bx, b, key)
                if r is None or (r[0] < .25 and max(r[1], r[2]) < .25): continue
                n_all += 1; good = r[0] > max(r[1], r[2]) + .05; n_ok += good
                if not good: worst.append(f'{h}{c}:{key}:{r[0]:.2f}/{r[1]:.2f}/{r[2]:.2f}')
            for b in bx:
                for key, tx in (b.tex or {}).items():
                    if (key == 3) != T.is_flat(tx): flat_bad.append(f'tenu:{h}{c}')
    check('PS1 : chaque image (dessins, légendes, photo, billet) se lit de face, pas en miroir', n_ok == n_all and n_all >= 20, f'{n_ok}/{n_all} images mesurées' + (f' ; échecs {worst[:3]}' if worst else ''))
    check('règle flat() : images du dessus seulement (PS1 et VOXEL, toutes variantes)', not flat_bad, str(sorted(set(flat_bad))[:4]))
    bad = []
    for k, ps in POSED.items():
        for p in ps:
            pr = BP.boxes_to_bset([b for b in BO.native_boxes(k, p)], 0, 0., 0., 0., BP.PROP_SCALE, {})
            for dcl in pr.get('decals', []):
                n = (math.sin(dcl['ry']), 0., math.cos(dcl['ry'])); q = (dcl['x'] + n[0] * .003, dcl['y'], dcl['z'] + n[2] * .003)
                if any('ry' not in bb and all(abs(q[i] - bb[a]) < bb[s_] / 2 - 1e-4 for i, (a, s_) in enumerate((('x', 'w'), ('y', 'h'), ('z', 'd')))) for bb in pr['boxes']): bad.append(f'{k}{p}')
    for h, cs in HELD.items():
        for c in cs:
            for mir in (False, True):
                hc = held_vox(OD, BO, h, c, mir)
                for dcl in hc['decals']:
                    n = (math.sin(dcl['ry']), math.cos(dcl['ry'])); q = (dcl['x'] + n[0] * .003, dcl['y'], dcl['z'] + n[1] * .003)
                    if any(not bb.get('alpha') and all(abs(q[i] - bb[a]) < bb[s_] / 2 - 1e-4 for i, (a, s_) in enumerate((('x', 'w'), ('y', 'h'), ('z', 'd')))) for bb in hc['boxes']): bad.append(f'{h}{c}')
    check('VOXEL : aucune décalcomanie enfouie (posés, tenus main droite et gauche)', not bad, str(sorted(set(bad))[:4]))
    img = D.ticket(D.TICKET, True); segs = D.segs(4, img.shape[1])
    st = sorted([b for b in BO.native_boxes('od_billet', {}) if 3 in (b.tex or {})], key=lambda b: float(b.lo[0]))
    ok1 = len(st) == 4 and all(np.array_equal(np.flipud(np.asarray(b.tex[3])), D.cols(img, *segs[3 - i])) for i, b in enumerate(st))
    st = sorted([b for b in OD.prop('od_billet', {}) if 3 in (b.tex or {})], key=lambda b: float(b.lo[0]))
    ok2 = len(st) == 4 and all(np.array_equal(np.flipud(np.asarray(b.tex[3])), D.cols(img, *segs[i])) for i, b in enumerate(st))
    check('billet froissé : tranches dans l\'ordre en PS1, redistribuées en miroir pour VOXEL (qui place les décalcomanies en miroir)', ok1 and ok2)

    print('\n5. objets tenus')
    hc = held_vox(OD, BO, 'od_carnet', {}); zs = [b['z'] - b['d'] / 2 for b in hc['boxes']]
    check('VOXEL : carnet fermé tenu DEVANT le poing (> 10 cm devant la paume), couverture vers l\'avant', min(zs) > .1 and any(abs(d_['ry']) < 1e-3 and d_['tw'] > 30 for d_ in hc['decals']), f'avant {min(zs):.3f} m')
    bx = held_ps1(OD, 'od_carnet', {}); check('PS1 : carnet fermé tenu devant le poing (cube de 12 cm)', min(float(b.lo[2]) for b in bx) > .06 - 1e-4)
    big = lambda hc: max(hc['decals'], key=lambda d_: d_['tw'] * d_['th'])
    check('VOXEL : od_carnet_ouvert, pages vers celui qui le tient ; od_carnet_montre, pages vers l\'avant', abs(abs(big(held_vox(OD, BO, 'od_carnet_ouvert', {}))['ry']) - math.pi) < 1e-3 and abs(big(held_vox(OD, BO, 'od_carnet_montre', {}))['ry']) < 1e-3)
    bx = held_ps1(OD, 'od_bouquet', {}); lo, hi = bbox(bx)
    ph = [b for b in bx if b.tex and any(np.asarray(t).shape[:2] == (40, 32) for t in b.tex.values())]
    check('bouquet tenu : fleurs en haut, photo au-dessus du poing (cube de 12 cm) et tournée vers l\'avant', hi[1] - 1. > .4 and ph and float(ph[0].lo[1]) > 1.06 and 5 in ph[0].tex)

    print('\n6. contenu par la clé d\'épisode, couleurs nommées')
    OD.use({'name': 'detailles', 'decors': True, 'tenus': True, 'contenu': {'od_carnet': {'dessin': 'trois_amis', 'legende': 'LES TROIS', 'couleur': 'brun'}, 'od_carnet_montre': {'dessin': 'deux_amis'}}})
    try:
        o = OD.held('od_carnet_ouvert', (0., 1., 0.), 1, {}); m = OD.held('od_carnet_montre', (0., 1., 0.), 1, {}); c = OD.held('od_carnet', (0., 1., 0.), 1, {})
        hv = BO.held_contract('od_carnet')
    finally: OD.use(None)
    has = lambda bx, im: any(any(t is im or (np.asarray(t).shape == im.shape and np.array_equal(np.asarray(t), im)) for t in (b.tex or {}).values()) for b in bx)
    check('le réglage d\'od_carnet vaut pour od_carnet_ouvert ; celui d\'od_carnet_montre passe devant', has(o, D.spread('trois_amis', 'LES TROIS', False)) and has(m, D.spread('deux_amis', 'LES TROIS', False)))
    check('couleur nommée « brun » (tuple(« brun ») passé par objets.held) : PS1 et VOXEL sans erreur', any(np.allclose(np.asarray(b.col) * 255, D.COVERS['brun'], atol=1) for b in c) and hv is not None)
    check('pick : nom, [r, g, b], tuple de lettres, rien', D.pick('brun', None, (0, 0, 0), D.COVERS) == D.COVERS['brun'] and D.pick([1, 2, 3], None, (0, 0, 0), D.COVERS) == (1, 2, 3)
          and D.pick(tuple('rose'), None, (0, 0, 0), D.FLOWERS) == D.FLOWERS['rose'] and D.pick(None, None, (9, 9, 9), D.COVERS) == (9, 9, 9))

    print('\n7. opt-in')
    mine = set(POSED) | set(HELD)
    check('aucun nom d\'avant ne devient un objet du lot', not any(v[0] in mine for v in OD.UP_HELD.values()) and not any(k in mine for k in OD.UP_PROPS))
    print('\n' + ('Tout est OK' if not FAIL else f'{len(FAIL)} ÉCHEC(S) : ' + '; '.join(FAIL)))
    return 1 if FAIL else 0


# ================================================================== planches (--planches)
LOCK = r'C:\Users\demo\Videos\studio_horreur_v3\_verrous\gpu.lock'


class GpuLock:
    """verrou GPU commun : attendu s'il existe (jamais supprimé s'il n'est pas à nous), posé avec une ligne d'identité, retiré à la fin"""
    def __init__(s, cmd): s.cmd = cmd; s.mine = False

    def __enter__(s):
        t0 = time.time(); said = False
        while True:
            try:
                fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, f'session=check_objets_drame heure={time.strftime("%Y-%m-%d %H:%M:%S")} cmd={s.cmd}\n'.encode('utf-8')); os.close(fd); s.mine = True; return s
            except FileExistsError:
                if not said: print(f'[gpu] verrou pris ({open(LOCK, errors="ignore").read()[:120].strip()}), j\'attends...', flush=True); said = True
                if time.time() - t0 > 3 * 3600: raise TimeoutError('verrou GPU jamais libéré')
                time.sleep(10)

    def __exit__(s, *a):
        if s.mine:
            try:
                if 'session=check_objets_drame' in open(LOCK, errors='ignore').read(): os.remove(LOCK)
            except FileNotFoundError: pass


SHEET_POSES = [('od_carnet', {}, 'ferme'), ('od_carnet', {'ouvert': True, 'legende': 'LINA, 6 ANS'}, 'ouvert'), ('od_carnet', {'ouvert': True, 'legende': 'LINA, 6 ANS'}, 'INSERT dessin enfant'),
               ('od_carnet', {'ouvert': True, 'mouille': True, 'legende': 'LINA, 6 ANS'}, 'INSERT mouille'), ('od_carnet', {'ouvert': True, 'dessin': 'deux_amis', 'legende': 'NOUS DEUX'}, 'INSERT deux_amis'),
               ('od_carnet', {'ouvert': True, 'dessin': 'trois_amis', 'couleur': 'brun', 'legende': 'LES TROIS'}, 'INSERT trois_amis'),
               ('od_carnet', {'mouille': True, 'couleur': 'brun'}, 'ferme mouille brun'), ('od_bouquet', {}, 'couche'), ('od_bouquet', {}, 'INSERT photo'),
               ('od_bouquet', {'debout': True}, 'debout (stele derriere)'), ('od_billet', {}, 'INSERT froisse'), ('od_billet', {'froisse': False, 'texte': ['PARIS', 'VOIE 4']}, 'INSERT lisse')]
SHEET_HELD = [('od_carnet', 'hold', 'face'), ('od_carnet', 'chest', 'face'), ('od_carnet_ouvert', 'hold', 'ots'), ('od_carnet_montre', 'hold', 'face'),
              ('od_bouquet', 'hold', 'face'), ('od_bouquet', 'show', 'face'), ('od_billet', 'show', 'face')]
LOOK = {'od_carnet': (0, .08, .1), 'od_carnet_montre': (-.24, 0, .06), 'od_carnet_ouvert': (.08, .1, 0), 'od_bouquet': (0, .2, 0), 'od_billet': (0, .05, .08)}


def pose_ep(items, style):
    import objets_sheet as OS
    from hstudio.engines.pixel3d import objets as OD
    sets = {}; shots = []; lines = []
    for i, (k, p, lab) in enumerate(items):
        lo, hi = OS._bbox(k, p); size = float(np.max(hi - lo)); h = float(hi[1] - lo[1])
        table = not (k == 'od_bouquet' and p.get('debout')); y = .8 if table else 0.
        props = [dict({'type': k, 'at': [0, 2.2], 'rot': 0, 'y': y}, **p)]
        if table: props.insert(0, {'type': 'table', 'at': [0, 2.3]})
        else: props.append({'type': 'gravestone', 'at': [0, 2.55], 'text': 'A JAMAIS'})
        sets[f's{i}'] = {'type': 'room', 'rooms': [{'id': 'r', 'origin': [0, 0], 'size': [5, 5], 'walls': 'plaster_blue', 'floor': 'wood', 'light': 'warm', 'light_power': 2.2, 'props': props}], 'fill': .8}
        c = (lo + hi) / 2 + np.array([0, y, 2.2]); fov = 50
        if lab.startswith('INSERT'):                                     # >= 1 m, objectif serré : la mise au point VOXEL ne descend pas sous 1 m
            fov, d, az, el = 14, 1.05, 0., math.radians(72)
            if k == 'od_carnet': c = np.array([.105 if style == 'ps1' else -.105, y + .012, 2.2])          # la page du dessin (VOXEL : monde en miroir)
            elif k == 'od_bouquet':
                ph = [b for b in OD.prop(k, p) if b.tex and any(np.asarray(v).shape[:2] == (40, 32) for v in b.tex.values())][0]
                c = (np.asarray(ph.lo) + np.asarray(ph.hi)) / 2 + np.array([0, y, 2.2]); fov = 9
            else: fov = 11
        else:
            d = max(.34, size * 1.5 + .15); el = math.radians(55 if h < .06 else (50 if table else 22)); az = math.radians(-28)
        pos = [float(c[0] + math.sin(az) * d * math.cos(el)), float(c[1] + d * math.sin(el)), float(c[2] - math.cos(az) * d * math.cos(el))]
        shots.append({'lines': [i, i], 'set': f's{i}', 'actors': [], 'camera': {'preset': 'free', 'keys': [{'pos': pos, 'look': [float(v) for v in c], 'fov': fov}]}})
        lines.append({'who': 'x', 'text': 'x', 'start': float(i), 'end': float(i) + .99})
    return {'engine_version': 1, 'default_set': 's0', 'sets': sets, 'cast': {}, 'state': {}, 'title': 'objets drame', 'shots': shots, 'mood': 'neutral', 'hud': {'show': False}, 'objets': 'detailles'}, lines


def held_ep(items, contenu):
    from hstudio.acting import rig
    shots = []; lines = []; i = 0
    for (it, g, view) in items:
        pr = dict(sit=0., crouch=0., air=0., lean=0., slump=0., tension=0., run=0., gait=0., head=(0., 0.), gestures=[(g, 1., 1.)] if g != 'idle' else [], hands=None, back=False)
        hand = np.asarray(rig.solve(pr).joints['haR'], float) + np.array([0, 0, 3.]); tgt = hand + np.array(LOOK.get(it, (0, 0, 0)))
        cam_c = (np.array([.9, 2.0, 2.45]), tgt, 40) if view == 'ots' else (tgt + np.array([-.15, .12, 1.0]), tgt, 40)
        for (pos, look, fov) in (cam_c, (np.array([.2, 1.45, 3 + 2.2]), np.array([0, 1.15, 3.]), 48)):
            tr = {'lea': [{'t': 0, 'p': [0., 0., 3.], 'yaw': 0., 'gesture': g, 'hold': it, 'face': 'neutral'}]}
            shots.append({'lines': [i, i], 'set': 'r', 'tracks': tr, 'camera': {'rig': 'path', 'keys': [{'t': 0, 'pos': [float(v) for v in pos], 'look': [float(v) for v in look], 'fov': fov}]}, 'ui': {'hud': False, 'subs': 'off'}})
            lines.append({'who': 'lea', 'text': '', 'start': float(i), 'end': float(i) + .99}); i += 1
    return {'engine_version': 2, 'default_set': 'r', 'title': 'objets drame', 'hud': {'show': False}, 'mood': 'neutral',
            'sets': {'r': {'type': 'room', 'rooms': [{'id': 'r', 'origin': [0, 0], 'size': [6, 7], 'walls': 'plaster_blue', 'floor': 'wood', 'light': 'warm', 'light_power': 2.4}], 'fill': .85}},
            'cast': {'lea': {'hood': [110, 128, 160], 'jeans': [50, 52, 62], 'hair': [60, 40, 28], 'hair_style': 'short', 'outfit': 'shirt', 'headphones': False, 'backpack': False}}, 'shots': shots,
            'objets': {'style': 'detailles', 'contenu': contenu}}, lines


def planches(out, styles):
    import objets_sheet as OS
    os.makedirs(out, exist_ok=True)
    for st in styles:
        def run(ep, lines, aspect, size):
            if st == 'ps1': return OS.render_ps1(ep, lines, aspect, size)
            with GpuLock('tools/check_objets_drame.py --planches'): return OS.render_voxel(ep, lines, aspect, size)
        ep, lines = pose_ep(SHEET_POSES, st); ims = run(ep, lines, '16:9', (480, 270))
        for n, part in enumerate(OS.chunks(list(range(len(SHEET_POSES))), 3)):
            p = os.path.join(out, f'drame_variantes_{st}_{n + 1}.png')
            OS.grid([[ims[j] for j in part]], [f'{SHEET_POSES[j][0]} {SHEET_POSES[j][2]}' for j in part], (480, 270), f'LOT DRAME - variantes et inserts, style {st.upper()}').save(p); print(p)
        ep, lines = held_ep(SHEET_HELD, {'od_carnet': {'dessin': 'enfant', 'legende': 'LINA, 6 ANS', 'mouille': True}}); ims = run(ep, lines, '9:16', (270, 480))
        for n, (a, b) in enumerate(((0, 4), (4, 7))):
            p = os.path.join(out, f'drame_tenus_{st}_{n + 1}.png')
            OS.grid([ims[2 * a:2 * b:2], ims[2 * a + 1:2 * b:2]], [f'{h[0]} ({h[1]})' for h in SHEET_HELD[a:b]], (270, 480), f'LOT DRAME - tenus, style {st.upper()} : gros plan / plan de face a 2,2 m').save(p); print(p)


if __name__ == '__main__':
    if '--planches' in sys.argv:
        a = sys.argv; out = a[a.index('--out') + 1] if '--out' in a else os.path.join(ROOT, 'docs', 'catalogue', 'objets_drame')
        planches(out, (a[a.index('--styles') + 1] if '--styles' in a else 'ps1,voxel').split(','))
        sys.exit(0)
    sys.exit(main())
