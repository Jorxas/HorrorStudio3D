"""python tools/check_objets.py [--vite] : les OBJETS DÉTAILLÉS (clé d'épisode `objets`) -- opt-in, déterminisme, deux versions natives, orientation des textes et des écrans.

Ce que l'outil garantit, SANS GPU (le rendu VOXEL se juge sur les planches de tools/objets_sheet.py) :
  1. opt-in : sans la clé, les noms d'avant (tv, plant, cups, phone, cup...) rendent les mêmes boîtes, une image PS1 est identique au bit près avec ou sans
     `objets: false`, le contrat VOXEL aussi (octet pour octet) ; l'hôtel aussi ; le profil `production` pose la clé, `objets: false` la retire ;
  2. avec la clé : les noms d'avant changent vraiment (PS1 et VOXEL), les objets tenus passent dans le contrat VOXEL image par image (`held`) ;
  3. déterminisme : deux constructions = mêmes boîtes, mêmes images, mêmes contrats ; la clé traverse le pool de rendu « spawn » ;
  4. deux versions natives : chaque objet (lots compris) a sa version VOXEL, posée ET tenue, aux mêmes dimensions ; les marqueurs retrouvent position et quart de tour ;
  5. textes et écrans : chaque image d'objet (PS1) est RENDUE de son côté lisible et comparée à l'image et à son miroir (gauche-droite et haut-bas) :
     elle doit ressembler à l'image, pas au miroir ; en VOXEL chaque décalcomanie regarde vers l'extérieur et n'est pas enfouie dans les cubes ; les aiguilles
     d'une horloge VOXEL sont tracées du bon côté ;
  6. branchements : profil, validateur, registre des capacités, styles, catalogue, réalisateur IA qui ignore la clé ; coût PS1 mesuré."""
import hashlib, json, math, os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import numpy as np
FAIL = []; VITE = '--vite' in sys.argv


def check(name, ok, detail=''):
    print(('OK   ' if ok else 'FAIL ') + name + (f'   {detail}' if detail else ''), flush=True)
    if not ok: FAIL.append(name)


def sig(boxes):
    h = hashlib.sha1()
    for b in boxes:
        h.update(np.concatenate([np.asarray(b.lo, np.float32), np.asarray(b.hi, np.float32), np.asarray(b.col, np.float32), [b.emis, float(b.grain), float(b.dissolve)]]).astype(np.float32).tobytes())
        for k in sorted(b.tex or {}): h.update(np.ascontiguousarray(b.tex[k]).tobytes())
    return h.hexdigest()[:12]


ON = {'name': 'detailles', 'decors': True, 'tenus': True, 'contenu': {}}
LEGACY_PROPS = ['tv', 'tv_stand', 'tv_old', 'nightstand', 'desk_lamp', 'computer', 'laptop', 'clock', 'wall_clock', 'plant', 'framed_photo', 'suitcase', 'candles', 'cups', 'bottles', 'note']


def room_ep(extra=None, hold='phone'):
    props = [{'type': 'nightstand', 'at': [-1.6, 3.8]}, {'type': 'tv', 'at': [1.2, 4.4], 'rot': 2}, {'type': 'plant', 'at': [1.7, 1.2]}, {'type': 'desk_lamp', 'at': [-1.2, 1.5], 'y': .76},
             {'type': 'table', 'at': [-1.2, 1.6]}, {'type': 'cups', 'at': [0.2, 2.6]}, {'type': 'clock', 'at': [0, 4.9]}, {'type': 'laptop', 'at': [-1.1, 1.75], 'y': .8}]
    ep = {'engine_version': 2, 'default_set': 's', 'title': 'objets', 'sets': {'s': {'type': 'room', 'rooms': [{'id': 'r', 'origin': [0, 0], 'size': [4.4, 5], 'walls': 'plaster', 'floor': 'wood', 'light': 'warm', 'props': props}]}},
          'cast': {'lea': {'hood': [110, 128, 160], 'headphones': False, 'backpack': False}},
          'shots': [{'lines': [0, 0], 'set': 's', 'tracks': {'lea': [{'t': 0, 'p': [0., 0., 2.0], 'yaw': math.pi, 'gesture': 'show', 'hold': hold}]},
                     'camera': {'rig': 'path', 'keys': [{'t': 0, 'pos': [.3, 1.5, .4], 'look': [0., 1.1, 3.0], 'fov': 70}]}}]}
    ep.update(extra or {})
    return ep, [{'who': 'lea', 'text': 'x', 'start': 0., 'end': 1.}]


def frame(ep, lines, t=.5, aspect='16:9'):
    from hstudio.pipeline import make_engine
    eng = make_engine('pixel3d', json.loads(json.dumps(ep)), lines, {}, 1.2, aspect); eng.render_lowres(t)
    t0 = time.perf_counter(); im = eng.render_lowres(t)[0]; return im, time.perf_counter() - t0


def cost(ep_a, ep_b, lines, n=5, t=.5):
    """ms par image de deux épisodes, médiane de n rendus chauds ENTRELACÉS (une machine chargée par d'autres rendus ralentit les deux pareil)"""
    from hstudio.pipeline import make_engine
    ea = make_engine('pixel3d', json.loads(json.dumps(ep_a)), lines, {}, 1.2, '16:9'); eb = make_engine('pixel3d', json.loads(json.dumps(ep_b)), lines, {}, 1.2, '16:9')
    ea.render_lowres(t); eb.render_lowres(t); ta, tb = [], []
    for _ in range(n):
        x = time.perf_counter(); ea.render_lowres(t); ta.append(time.perf_counter() - x)
        x = time.perf_counter(); eb.render_lowres(t); tb.append(time.perf_counter() - x)
    return float(np.median(ta)), float(np.median(tb))


def contract(ep, lines):
    from hstudio.voxelgpu import from_ps1
    return from_ps1.build(json.loads(json.dumps(ep)), lines, 1.2, '9:16', 24, None)


# ------------------------------------------------------------------ text orientation, measured on the ray caster
def _lum(a): a = np.asarray(a, np.float32); return a[..., :3].mean(-1) if a.ndim == 3 else a


def _corr(a, b):
    a = a - a.mean(); b = b - b.mean(); d = math.sqrt(float((a * a).sum() * (b * b).sum())) or 1.
    return float((a * b).sum() / d)


def read_face(boxes, b, key, intended=None):
    """rend la face `key` de la boîte `b` de son côté lisible (lecteur devant, à l'endroit) et la compare à l'image VOULUE (par défaut : l'image posée,
    remise à l'endroit pour une face du dessus) -> (corr image, corr miroir gauche-droite, corr miroir haut-bas) ou None"""
    from hstudio.engines.pixel3d import r3d
    from hstudio.engines.pixel3d.r3d import Scene, FACES
    inv = {v: k for k, v in FACES.items()}; kname = inv[key]
    tx = np.asarray(b.tex[key]); exp = (np.flipud(tx) if kname == '+y' else tx) if intended is None else np.asarray(intended)     # face du dessus : posée retournée (flat), on doit lire l'image d'origine
    lo, hi = np.asarray(b.lo, float), np.asarray(b.hi, float); c = (lo + hi) / 2; sz = hi - lo
    ax = {'-x': 0, '+x': 0, '-y': 1, '+y': 1, '-z': 2, '+z': 2}[kname]; sg = 1 if kname[0] == '+' else -1
    face_c = c.copy(); face_c[ax] = hi[ax] if sg > 0 else lo[ax]
    dims = [sz[i] for i in range(3) if i != ax]; size = max(dims)
    if min(dims) < .012: return None
    d = size * 1.5 + .05
    if kname == '+y': pos = face_c + np.array([0, d * math.sin(1.35), -d * math.cos(1.35)]); yaw, pitch = 0., -1.35
    else:
        n = np.zeros(3); n[ax] = sg; pos = face_c + n * d; dv = -n; yaw = math.atan2(dv[0], dv[2]); pitch = 0.
    sc = Scene(); sc.ceil_y = None; sc.ambient = (1., 1., 1.); sc.fog = (0, 0, 0); sc.fogk = 0.
    sc.floor_fn = lambda P: (np.full((len(P), 3), .02, np.float32), np.zeros(len(P), np.float32)); sc.add(*[x for x in boxes if not x.hidden])
    cam = (tuple(pos), yaw, pitch, 0., 40.)
    img = r3d.render(sc, cam, lights=[])
    corners = []
    for s0 in (-1, 1):
        for s1 in (-1, 1):
            q = face_c.copy(); oth = [i for i in range(3) if i != ax]; q[oth[0]] += s0 * sz[oth[0]] / 2 * .9; q[oth[1]] += s1 * sz[oth[1]] / 2 * .9
            u, v, dep = r3d.project(pos, yaw, pitch, 0., 40., q); corners.append(((u + 1) / 2 * r3d.RW, (1 - v) / 2 * r3d.RH))
    xs = [p[0] for p in corners]; ys = [p[1] for p in corners]
    x0, x1, y0, y1 = int(max(0, min(xs))), int(min(r3d.RW, max(xs))), int(max(0, min(ys))), int(min(r3d.RH, max(ys)))
    if x1 - x0 < 6 or y1 - y0 < 6: return None
    E = _small(exp); crop = _small(np.clip(img[y0:y1, x0:x1], 0, 1) * 255, shape=E.shape)
    return _corr(crop, E), _corr(crop, np.fliplr(E)), _corr(crop, np.flipud(E))


def _small(a, n=12, shape=None):
    """luminance réduite à une grille grossière (n x n au plus) : on compare la MISE EN PAGE (texte calé à gauche, heure en haut...), pas les lettres"""
    from PIL import Image
    a = np.asarray(a, np.float32); L = a[..., :3].mean(-1) if a.ndim == 3 else a
    h, w = L.shape; sw, sh = (max(2, min(n, w // 2)), max(2, min(n, h // 2))) if shape is None else (shape[1], shape[0])
    return np.asarray(Image.fromarray(L.astype(np.float32), mode='F').resize((sw, sh), Image.BOX), np.float32)


def textured(boxes):
    """les images dont le sens SE VOIT à l'échelle de la mise en page (une image presque symétrique ou en motif répété -- clavier, grille, neige -- ne dit rien)"""
    out = []
    for b in boxes:
        for key, tx in (b.tex or {}).items():
            tx = np.asarray(tx)
            if tx.ndim != 3 or tx.shape[0] * tx.shape[1] < 64: continue
            E = _small(tx)
            if E.std() < 6: continue
            if max(_corr(E, np.fliplr(E)), _corr(E, np.flipud(E))) > .7: continue
            out.append((b, key))
    return out


def probe():
    """contrôle du test lui-même : une image dissymétrique bien posée doit passer, la même retournée doit échouer (face avant et face du dessus)"""
    from hstudio.engines.pixel3d.r3d import B
    from hstudio.engines.pixel3d import objets_tex as T
    im = np.zeros((24, 32, 4), np.uint8); im[..., 3] = 255; im[..., :3] = 30; im[2:8, 2:20, :3] = 240; im[10:14, 2:12, :3] = 240; im[16:20, 2:26, :3] = 200
    res = []
    for key, img, good in (('-z', im, True), ('-z', np.ascontiguousarray(np.fliplr(im)), False), ('+y', T.flat(im), True), ('+y', im, False)):
        b = B((-.1, .2, -.05), (.2, .15, .1), (128, 128, 128), tex={key: img}); r = read_face([b], b, 3 if key == '+y' else 4, intended=im)
        res.append((r is not None and r[0] > max(r[1], r[2]) + .05) == good)
    return all(res)


def main():
    from hstudio.engines.pixel3d import sets as S, world as W, poses as P, objets as OD, objets_tex as T, hotel as H, hotel_cast as HC
    from hstudio.voxelgpu import b_objets as BO, b_props as BP
    from hstudio import profiles, styles
    OD.configure(None)
    print(f'lots chargés : PS1 {OD.LOTS or "aucun"} ; VOXEL {BO.LOTS or "aucun"} ; {len(OD.KINDS)} objets posés, {len(OD.HELD)} objets tenus')
    vox_lots = {n[2:] for n, _ in BO.LOTS}                                     # « b_objets_x » -> « objets_x »
    pending = set()
    for lot, names in OD.LOTS:                                                   # un lot dont le fichier VOXEL n'existe pas encore : vérifié en PS1 seulement
        if lot not in vox_lots: pending |= {n for n in names if n not in BO.VOX and n not in BO.HELD_VOX}
    if pending: print(f'lots en cours, sans fichier VOXEL : {sorted(pending)} -- vérifiés en PS1 seulement ; dès que leur b_objets_<lot>.py existe, tout manque devient un ÉCHEC')

    print('\n1. sans la clé, rien ne change')
    for k in LEGACY_PROPS:
        p = {'type': k}
        OD.use(None); a = sig(S.prop_boxes(k, dict(p))); OD.configure(False); b = sig(S.prop_boxes(k, dict(p)))
        OD.use(None); raw = W.PROPS[k](dict(p), None) if k in W.PROPS else None
        check(f'décor « {k} » : mêmes boîtes sans la clé', a == b and (raw is None or sig(raw) == a))
    bad = []
    for it in P.HOLD_ITEMS:
        if it.startswith('od_'): continue
        x = P.held_item(it, (.1, 1.0, .2), 1, {}, [], None); y = OD._ORIG['held_item'](it, (.1, 1.0, .2), 1, {}, [], None)
        if sig(x) != sig(y): bad.append(it)
    check('objets tenus d\'avant : mêmes boîtes sans la clé', not bad, str(bad))
    for name in ('bedroom', 'living_room', 'kitchen', 'office', 'cafe', 'hospital_room'):
        OD.use(None); st = S.make_set('x', {'type': name}); st.build(); a = sig(st.base.boxes)
        OD.configure(False); st2 = S.make_set('x', {'type': name}); st2.build(); OD.use(None)
        check(f'lieu « {name} » : aucun marqueur et mêmes boîtes sans la clé / avec `objets: false`', not OD.read_markers(st.base.boxes) and a == sig(st2.base.boxes), f'{len(st.base.boxes)} boîtes')
    ep, lines = room_ep()
    im0, t0 = frame(ep, lines); im1, _ = frame(dict(ep, objets=False), lines); im2, t2 = frame(dict(ep, objets='detailles'), lines)
    t0, t2 = cost(ep, dict(ep, objets='detailles'), lines)
    check('image PS1 identique avec `objets: false`', np.array_equal(im0, im1))
    d = np.abs(im0.astype(int) - im2.astype(int)).mean(); check('image PS1 différente avec `objets: detailles`', d > 2, f'écart moyen {d:.1f}/255')
    check('coût PS1 par image sous 3x (mesuré, rendu chaud)', t2 < 3 * t0 + .25, f'{t0 * 1000:.0f} ms -> {t2 * 1000:.0f} ms (x{t2 / max(t0, 1e-6):.2f})')
    if not VITE:
        c0 = contract(ep, lines); c1 = contract(dict(ep, objets=False), lines); c2 = contract(dict(ep, objets='detailles'), lines)
        j0, j1, j2 = (json.dumps(c, sort_keys=True) for c in (c0, c1, c2))
        check('contrat VOXEL identique (octet pour octet) avec `objets: false`', j0 == j1)
        check('  et sans piste `held` ni boîte translucide', '"held"' not in j0 and '"alpha"' not in j0)
        check('contrat VOXEL : avec la clé, l\'objet tenu passe image par image (`held`)', '"held"' in j2 and any('held' in s for s in c2['stages']))
        check('contrat VOXEL : avec la clé, les décors d\'avant sont refaits (plus de boîtes)', len(j2) > len(j0))
    OD.configure(None)
    st0 = H.HotelNuit({}); s = H.state_of({'board_313': 1, 'landline_ring': 1}); a, _ = H.dynamic(s, .5)
    OD.configure(False); b, _ = H.dynamic(s, .5); OD.configure('detailles'); c, _ = H.dynamic(s, .5); OD.configure(None)
    check('hôtel : téléphone et standard identiques sans la clé', sig(a) == sig(b))
    check('hôtel : avec la clé, téléphone et standard détaillés (marqueurs, plus de console penchée)', {m[1] for m in OD.read_markers(c)} >= {'od_phone_desk', 'od_switchboard'} and not any(x.inst is not None and abs(x.inst.R[0][1]) > .1 for x in c))
    base0 = H.base(); OD.configure('detailles'); base1 = H.base(); OD.configure(None); base2 = H.base()
    check('hôtel : le décor fixe est mis en cache PAR état de la clé (sans elle, le même objet qu\'avant)', base0 is base2 and base1 is not base0 and len(OD.read_markers(base1.boxes)) >= 4)
    p = profiles.PROFILES['production']; check('le profil `production` pose `objets`', p.get('objets') == 'detailles')
    e = {'profile': 'production', 'objets': False}; profiles.apply(e); check('`objets: false` à côté du profil gagne', e['objets'] is False)

    print('\n2. avec la clé, les noms d\'avant deviennent détaillés')
    OD.use(dict(ON))
    for k in LEGACY_PROPS:
        bx = S.prop_boxes(k, {'type': k}); m = OD.read_markers(bx)
        check(f'« {k} » -> {m[0][1] if m else "?"}', bool(m))
    for it in OD.UP_HELD:
        x = P.held_item(it, (.1, 1.0, .2), 1, {}, [], None); y = OD._ORIG['held_item'](it, (.1, 1.0, .2), 1, {}, [], None)
        check(f'objet tenu « {it} » -> {OD.UP_HELD[it][0]}', sig(x) != sig(y) and len(x) >= len(y))
    OD.configure(None)

    print('\n3. déterminisme')
    nd = []
    for k in OD.KINDS:
        if sig(OD.prop(k, {})) != sig(OD.prop(k, {})): nd.append(k)
        if k not in pending and sig(BO.native_boxes(k, {})) != sig(BO.native_boxes(k, {})): nd.append('vox:' + k)
    for h in OD.HELD:
        if sig(OD.held(h, (0, 1, 0), 1, {})) != sig(OD.held(h, (0, 1, 0), 1, {})): nd.append(h)
        if h not in pending and json.dumps(BO.held_contract(h), sort_keys=True) != json.dumps(BO.held_contract(h), sort_keys=True): nd.append('vox:' + h)
    check('mêmes réglages = mêmes boîtes, mêmes images (PS1 et VOXEL, posés et tenus)', not nd, str(nd[:5]))
    if not VITE: check_spawn()

    print('\n4. deux versions natives')
    for k in OD.KINDS:
        if k in pending: continue
        ps = [b for b in OD.prop(k, {}) if not b.hidden]; vx = BO.native_boxes(k, {})
        if not vx: check(f'{k} : version VOXEL écrite', False); continue
        pl, ph = np.min([b.lo for b in ps], 0), np.max([b.hi for b in ps], 0); vl, vh = np.min([b.lo for b in vx], 0), np.max([b.hi for b in vx], 0)
        se = np.maximum(ph - pl, .02); ve = np.maximum(vh - vl, .02); ratio = ve / se; dc = np.abs((vl + vh) / 2 - (pl + ph) / 2).max()
        nan = any(not np.isfinite(np.concatenate([b.lo, b.hi])).all() for b in vx)
        ok = (.55 < ratio).all() and (ratio < 1.8).all() and dc < .35 * se.max() + .02 and not nan
        check(f'{k} ({OD.LABELS.get(k, "")}) : VOXEL natif aux mêmes dimensions', ok, f'{len(ps)} boîtes PS1, {len(vx)} blocs VOXEL, taille x{ratio.min():.2f}..x{ratio.max():.2f}')
        if len(ps) > 220: check(f'{k} : PS1 sous 220 boîtes (coût du lancer de rayons)', False, f'{len(ps)}')
    for h in OD.HELD:
        if h in pending: continue
        hc = BO.held_contract(h); ok = hc is not None and len(hc['boxes']) > 0
        check(f'{h} : objet tenu VOXEL natif', ok, f'{len(hc["boxes"]) if hc else 0} blocs, {len(hc["decals"]) if hc else 0} images')
    from hstudio.engines.pixel3d.sets import place
    okm = True
    for rot in range(4):
        for k in ('od_tv', 'od_cup', 'od_switchboard'):
            bx = place(OD.prop(k, {}), 1.3, -2.7, rot, .76); m = OD.read_markers(bx)
            if not (m and m[0][1] == k and abs(m[0][3] - 1.3) < 1e-4 and abs(m[0][5] + 2.7) < 1e-4 and abs(m[0][4] - .76) < 1e-4 and m[0][6] == rot and m[0][7] == len(bx) - 2): okm = False
    check('marqueurs : objet, position, hauteur et quart de tour retrouvés (4 rotations)', okm)
    st = S.make_set('x', {'type': 'room', 'rooms': [{'id': 'r', 'origin': [0, 0], 'size': [4, 4], 'props': [{'type': 'od_tv', 'at': [1, 2], 'rot': 3}, {'type': 'od_plant', 'at': [-1, 1]}]}]}); st.build()
    hide, nat = BO.natives(st.base.boxes)
    check('VOXEL : les boîtes PS1 des objets détaillés sont cachées et remplacées par la version native', len(hide) == sum(2 + m[7] for m in OD.read_markers(st.base.boxes)) and len(nat) > len(hide))

    print('\n5. textes et écrans dans le bon sens')
    from hstudio.engines.pixel3d import r3d
    r3d.configure('16:9')
    n_ok = n_all = n_skip = 0; worst = []
    params = {'od_paper': {}, 'od_book': {}, 'od_book_open': {'ouvert': True}}
    for k in OD.KINDS:
        bx = [b for b in OD.prop(k, {}) if not b.hidden]
        for (b, key) in textured(bx):
            r = read_face(bx, b, key)
            if r is None: continue
            if r[0] < .25 and max(r[1], r[2]) < .25: n_skip += 1; continue                  # trop petit ou caché à cette distance : rien de mesurable
            n_all += 1; good = r[0] > max(r[1], r[2]) + .05
            n_ok += good
            if not good: worst.append(f'{k}:{key}:{r[0]:.2f}/{r[1]:.2f}/{r[2]:.2f}')
    for h in OD.HELD:
        bx = OD.held(h, (0., 1., 0.), 1, {})
        for (b, key) in textured(bx):
            r = read_face(bx, b, key)
            if r is None: continue
            if r[0] < .25 and max(r[1], r[2]) < .25: n_skip += 1; continue
            n_all += 1; good = r[0] > max(r[1], r[2]) + .05; n_ok += good
            if not good: worst.append(f'{h}:{key}:{r[0]:.2f}/{r[1]:.2f}/{r[2]:.2f}')
    check('contrôle du test : une image bien posée passe, la même en miroir échoue (face avant et dessus)', probe())
    check('PS1 : chaque image lisible (rendue de face, plus proche de l\'image que de ses miroirs)', n_ok == n_all and n_all >= 6, f'{n_ok}/{n_all} images mesurées, {n_skip} trop petites' + (f' ; échecs {worst[:4]}' if worst else ''))
    bad = []
    for k in OD.KINDS:
        for src, bx in (('ps1', OD.prop(k, {})), ('voxel', [] if k in pending else BO.native_boxes(k, {}) or [])):
            for b in bx:
                for key, tx in (b.tex or {}).items():
                    if (key == 3) != T.is_flat(tx): bad.append(f'{src}:{k}:{"dessus" if key == 3 else "côté"}')
    for h in OD.HELD:
        for b in OD.held(h, (0., 1., 0.), 1, {}):
            for key, tx in (b.tex or {}).items():
                if (key == 3) != T.is_flat(tx): bad.append(f'tenu:{h}')
    check("règle d'écriture : toute image posée sur une face du dessus passe par flat(), aucune image de côté (sinon elle se lirait en miroir)", not bad, str(sorted(set(bad))[:6]))
    bad = []
    for k in OD.KINDS:
        if k in pending: continue
        pr = BP.boxes_to_bset([b for b in BO.native_boxes(k, {})], 0, 0., 0., 0., BP.PROP_SCALE, {})
        for dcl in pr.get('decals', []):
            n = (math.sin(dcl['ry']), 0., math.cos(dcl['ry'])); q = (dcl['x'] + n[0] * .003, dcl['y'], dcl['z'] + n[2] * .003)
            for bb in pr['boxes']:
                if 'ry' in bb: continue
                if all(abs(q[i] - bb[a]) < bb[s] / 2 - 1e-4 for i, (a, s) in enumerate((('x', 'w'), ('y', 'h'), ('z', 'd')))): bad.append(k); break
    check('VOXEL posés : aucune image enfouie dans les cubes (devant sa face)', not bad, str(sorted(set(bad))[:6]))
    bad = []
    for h in OD.HELD:
        if h in pending: continue
        for mir in (False, True):
            hc = BO.held_contract(h, mirror=mir)
            for dcl in hc['decals']:
                n = (math.sin(dcl['ry']), math.cos(dcl['ry'])); q = (dcl['x'] + n[0] * .003, dcl['y'], dcl['z'] + n[1] * .003)
                for bb in hc['boxes']:
                    if bb.get('alpha'): continue
                    if all(abs(q[i] - bb[a]) < bb[s] / 2 - 1e-4 for i, (a, s) in enumerate((('x', 'w'), ('y', 'h'), ('z', 'd')))): bad.append(h); break
    check('VOXEL tenus : aucune image enfouie, main droite et gauche', not bad, str(sorted(set(bad))[:6]))
    def hand_x(hh):
        vb = BO.v_clock({'heure': hh}); hb = [b for b in vb if tuple(int(v) for v in np.asarray(b.col) * 255 + .5) == (30, 28, 26) and b.lo[2] < -.06]
        return sum(float(b.hi[0] - b.lo[0]) * (b.lo[0] + b.hi[0]) / 2 for b in hb)
    a3, a9 = hand_x('03:00'), hand_x('09:00')
    check('VOXEL : aiguilles tracées en miroir (3 h côté -x, 9 h côté +x : l\'image VOXEL est le miroir de PS1, l\'heure s\'y lit juste)', a3 < a9 - .002, f'{a3:.3f} / {a9:.3f}')
    hc = BO.held_contract('od_smartphone'); dz = [d_['ry'] for d_ in hc['decals']]
    check('VOXEL : écran du smartphone tenu tourné vers celui qui le tient (-z), écran « montré » vers l\'avant (+z)', any(abs(abs(r) - math.pi) < 1e-3 for r in dz) and any(abs(d_['ry']) < 1e-3 for d_ in BO.held_contract('od_smartphone_montre')['decals']))

    print('\n6. branchements')
    check('styles : décor et objet tenu `od_` natif / natif', styles.of_entry({'id': 'decor/od_tv'}) == {'ps1': 'native', 'voxel': 'native'} and styles.of_entry({'id': 'perso/hold/od_cup'}) == {'ps1': 'native', 'voxel': 'native'})
    from hstudio.capabilities import registry
    caps = registry.build(); check('registre des capacités : décors `od_*`, objets tenus et la clé', caps.get('prop:od_tv', {}).get('styles') == {'ps1': 'native', 'voxel': 'native'} and 'item:od_handset' in caps and 'feature:objets_detailles' in caps)
    from hstudio import catalogue
    ids = {e['id'] for e in catalogue.entries()}; check('catalogue : décors et objets tenus `od_*` listés', 'decor/od_switchboard' in ids and 'perso/hold/od_handset' in ids, f'{len([i for i in ids if "/od_" in i])} fiches')
    import importlib; validate = importlib.import_module('hstudio.director.validate')
    v, w = validate.validate({'objets': 'nimporte', 'shots': [{'lines': [0, 0]}]}, 1, 'pixel3d'); check('validateur : valeur inconnue ignorée à voix haute', 'objets' not in v and any('objets' in x for x in w))
    v, w = validate.validate({'objets': 'detailles', 'shots': [{'lines': [0, 0]}]}, 1, 'console'); check('validateur : refusée sur CONSOLE 2D', 'objets' not in v and any('console' in x for x in w))
    v, w = validate.validate({'objets': 'detailles', 'shots': [{'lines': [0, 0]}]}, 1, 'pixel3d'); check('validateur : acceptée sur PS1', v.get('objets') == 'detailles')
    prompts = importlib.import_module('hstudio.director.prompts')
    sent = ' '.join(str(getattr(prompts, n, '')) for n in dir(prompts) if n.isupper()); check('le réalisateur IA ne connaît pas la clé (opt-in jusqu\'au verdict humain)', '"objets"' not in sent and "'objets'" not in sent and 'detailles' not in sent)
    print('\n' + ('Tout est OK' if not FAIL else f'{len(FAIL)} ÉCHEC(S) : ' + '; '.join(FAIL)))
    return 1 if FAIL else 0


def check_spawn():
    """le rendu repart dans des processus neufs : la clé `objets` doit traverser le pool"""
    import multiprocessing as mp
    from hstudio import pipeline
    from hstudio.pipeline import make_engine
    ep, lines = room_ep({'profile': 'production'})
    eng = make_engine('pixel3d', json.loads(json.dumps(ep)), lines, {}, 1.2, '16:9'); here = [eng.frame(.4).convert('RGB').tobytes()]
    off = [make_engine('pixel3d', dict(json.loads(json.dumps(ep)), objets=False), lines, {}, 1.2, '16:9').frame(.4).convert('RGB').tobytes()]
    with mp.get_context('spawn').Pool(2, initializer=pipeline._init_worker, initargs=('pixel3d', json.loads(json.dumps(ep)), lines, {}, 1.2, '16:9')) as pool: there = list(pool.imap(pipeline._render_one, [12]))
    check('deux workers « spawn » rendent les mêmes octets qu\'ici (profil production)', there == here)
    check('  et ce ne sont pas les octets sans `objets`', there != off)


if __name__ == '__main__': sys.exit(main())
