"""python tools/objets_sheet.py [--only od_cup,od_tv] [--styles ps1,voxel] [--modes pose,tenu,avant_apres,hotel] [--out DOSSIER] [--name prefixe]

Planches des OBJETS DÉTAILLÉS (clé d'épisode `objets`, engines/pixel3d/objets.py + voxelgpu/b_objets.py), à REGARDER :
  * pose        : chaque objet posé (sur une table, au sol ou au mur selon sa taille), même caméra en PS1 et en VOXEL ;
  * tenu        : un personnage tient l'objet (geste adapté : combiné à l'oreille, écran vers celui qui le tient vu par-dessus l'épaule...), gros plan + plan moyen ;
  * avant_apres : les noms d'AVANT (tv, plant, cups, phone, cup...) sans la clé (rangée du haut) puis avec la clé (rangée du bas) ;
  * hotel       : la réception de « Chambre 313 » (standard, téléphone, le réceptionniste qui décroche) sans / avec la clé.
Un objet ajouté par un LOT (fichiers `objets_<lot>.py` + `b_objets_<lot>.py`) est pris tel quel : `--only od_mon_objet`. Caméra calculée sur la boîte
englobante de l'objet ; geste et vue d'un objet tenu inconnu : `show`, de face.
Rendus GPU : un seul à la fois, sous le verrou commun C:\\Users\\demo\\Desktop\\videpgene\\OBJETS_DETAILLES\\_gpu.lock (attendu, posé, retiré)."""
import argparse, contextlib, json, math, os, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import numpy as np
from PIL import Image, ImageDraw

OUT = Path(r'C:\Users\demo\Desktop\videpgene\OBJETS_DETAILLES')
LOCK = OUT / '_gpu.lock'


@contextlib.contextmanager
def gpu_lock(wait_max=3 * 3600):
    """verrou commun des rendus GPU (un seul peintre VOXEL à la fois entre agents) ; un verrou de plus de 2 h est considéré abandonné"""
    LOCK.parent.mkdir(parents=True, exist_ok=True); t0 = time.time(); said = False
    while True:
        try:
            fd = os.open(str(LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY); os.write(fd, f'{os.getpid()} objets_sheet {time.strftime("%H:%M:%S")}'.encode()); os.close(fd); break
        except FileExistsError:
            try:
                if time.time() - LOCK.stat().st_mtime > 7200: LOCK.unlink(); continue
            except FileNotFoundError: continue
            if not said: print(f'[gpu] verrou pris ({LOCK.read_text(errors="ignore")[:60]}), j\'attends...', flush=True); said = True
            if time.time() - t0 > wait_max: raise TimeoutError('verrou GPU jamais libéré')
            time.sleep(5)
    try: yield
    finally:
        try: LOCK.unlink()
        except FileNotFoundError: pass


# ------------------------------------------------------------------ what to show
HELD_POSE = {'od_handset': ('phone', 'side'), 'od_smartphone': ('show', 'ots'), 'od_smartphone_montre': ('show', 'face'), 'od_book_open': ('show', 'ots'),
             'od_notebook': ('show', 'ots'), 'od_crowbar': ('idle', 'face'), 'od_flashlight': ('point', 'face'), 'od_bag': ('idle', 'face'), 'od_suitcase': ('idle', 'face'),
             'od_keys': ('show', 'face')}
LEGACY_PROPS = ['tv', 'tv_old', 'nightstand', 'desk_lamp', 'computer', 'laptop', 'clock', 'wall_clock', 'plant', 'cups', 'bottles', 'framed_photo', 'suitcase', 'candles', 'note', 'tv_stand']
LEGACY_HELD = ['phone', 'mobile', 'handset', 'cup', 'book', 'notebook', 'printout', 'key', 'bottle', 'flashlight', 'candle', 'crowbar', 'bag']
LEGACY_POSE = {'handset': ('phone', 'side'), 'mobile': ('show', 'face'), 'notebook': ('show', 'face'), 'crowbar': ('idle', 'face'), 'flashlight': ('point', 'face'), 'bag': ('idle', 'face')}


def _bbox(kind, p):
    from hstudio.engines.pixel3d import sets as S, objets as OD
    st = OD.active(); OD.use({'name': 'detailles', 'decors': True, 'tenus': True, 'contenu': {}})
    try: bx = [b for b in S.prop_boxes(kind, dict(p)) if not b.hidden]
    finally: OD.use(st)
    lo = np.min([b.lo for b in bx], 0); hi = np.max([b.hi for b in bx], 0)
    return lo, hi


def pose_episode(kinds, objets='detailles', params=None):
    """un plan par objet, chacun dans sa pièce : sur une table s'il est petit, au sol sinon, à sa hauteur s'il est au mur ; caméra de trois quarts sur sa boîte englobante"""
    sets = {}; shots = []; lines = []
    for i, k in enumerate(kinds):
        p = dict((params or {}).get(k, {}))
        lo, hi = _bbox(k, p); size = float(np.max(hi - lo)); h = float(hi[1] - lo[1])
        wall = lo[1] > .3; table = not wall and h < .45 and float(max(hi[0] - lo[0], hi[2] - lo[2])) < .9
        y = .8 if table else 0.
        props = [dict({'type': k, 'at': [0, 2.2], 'rot': 0, 'y': y}, **p)]
        if table: props.insert(0, {'type': 'table', 'at': [0, 2.3]})
        sets[f's{i}'] = {'type': 'room', 'rooms': [{'id': 'r', 'origin': [0, 0], 'size': [5, 5], 'walls': 'plaster_blue', 'floor': 'wood', 'light': 'warm', 'light_power': 2.2, 'props': props}], 'fill': .8}
        c = (lo + hi) / 2 + np.array([0, y, 2.2]); flat = h < .06
        d = max(.34, size * 1.5 + .15); el = math.radians(55 if flat else 22); az = math.radians(-28)
        pos = [float(c[0] + math.sin(az) * d * math.cos(el)), float(c[1] + d * math.sin(el)), float(c[2] - math.cos(az) * d * math.cos(el))]
        shots.append({'lines': [i, i], 'set': f's{i}', 'actors': [], 'camera': {'preset': 'free', 'keys': [{'pos': pos, 'look': [float(v) for v in c], 'fov': 50}]}})
        lines.append({'who': 'x', 'text': 'x', 'start': float(i), 'end': float(i) + .99})
    ep = {'engine_version': 1, 'default_set': 's0', 'sets': sets, 'cast': {}, 'state': {}, 'title': 'objets detailles', 'shots': shots, 'mood': 'neutral', 'hud': {'show': False}}
    if objets is not None: ep['objets'] = objets
    return ep, lines


def held_episode(items, objets='detailles', poses=None):
    """deux plans par objet tenu (gros plan, plan moyen), scène dirigée (pistes `tracks`, caméra en clés) : le personnage regarde +z en (0, 0, 3)"""
    from hstudio.acting import rig
    shots = []; lines = []; i = 0
    for it in items:
        g, view = (poses or {}).get(it) or HELD_POSE.get(it) or ('show', 'face')
        pr = dict(sit=0., crouch=0., air=0., lean=0., slump=0., tension=0., run=0., gait=0., head=(0., 0.), gestures=[(g, 1., 1.)] if g != 'idle' else [], hands=None, back=False)
        hand = np.asarray(rig.solve(pr).joints['haR'], float) + np.array([0, 0, 3.])
        if view == 'ots': cam_c = (np.array([.42, 1.84, 3 - .42]), hand + np.array([-.02, .06, .06]), 46)
        elif view == 'side': cam_c = (np.array([1.05, 1.72, 3 + .8]), np.array([.2, 1.6, 3.04]), 44)
        else: cam_c = (hand + np.array([-.2, .14, .8]), hand + np.array([-.03, .05, .06]), 46)
        cam_m = (np.array([.45, 1.5, 3 + 2.5]), np.array([0, 1.2, 3.]), 48)
        for (pos, look, fov) in (cam_c, cam_m):
            tr = {'lea': [{'t': 0, 'p': [0., 0., 3.], 'yaw': 0., 'gesture': g, 'hold': it, 'face': 'neutral'}]}
            shots.append({'lines': [i, i], 'set': 'r', 'tracks': tr, 'camera': {'rig': 'path', 'keys': [{'t': 0, 'pos': [float(v) for v in pos], 'look': [float(v) for v in look], 'fov': fov}]}, 'ui': {'hud': False, 'subs': 'off'}})
            lines.append({'who': 'lea', 'text': '', 'start': float(i), 'end': float(i) + .99}); i += 1
    ep = {'engine_version': 2, 'default_set': 'r', 'title': 'objets detailles', 'hud': {'show': False}, 'mood': 'neutral',
          'sets': {'r': {'type': 'room', 'rooms': [{'id': 'r', 'origin': [0, 0], 'size': [6, 7], 'walls': 'plaster_blue', 'floor': 'wood', 'light': 'warm', 'light_power': 2.4}], 'fill': .85}},
          'cast': {'lea': {'hood': [110, 128, 160], 'jeans': [50, 52, 62], 'hair': [60, 40, 28], 'hair_style': 'short', 'outfit': 'shirt', 'headphones': False, 'backpack': False}}, 'shots': shots}
    if objets is not None: ep['objets'] = objets
    return ep, lines


def hotel_episode(objets='detailles'):
    from hstudio.engines.pixel3d import hotel as H
    bx, bz = H.BOARD; px, pz = H.PHONE
    views = [dict(pos=[-5.6, 1.45, bz - .55], look=[bx, H.DESK_Y + .2, bz], fov=50, state={'board_313': 1, 'board_lamps': ['104', '212']}),
             dict(pos=[-5.2, 1.35, pz - .45], look=[px, H.DESK_Y + .05, pz], fov=46, state={'landline_ring': 1, 'board_313': 1}),
             dict(pos=[-5.85, 1.6, 3.35], look=[-4.55, 1.0, 4.5], fov=60, state={'board_313': 1, 'landline_ring': 1, 'screen': 'call'}),
             dict(pos=[-3.4, 1.62, 5.2], look=[-5.4, 1.5, 5.85], fov=50, state={'board_313': 1, 'handset': 0},
                  tracks={'rec': [{'t': 0, 'p': [-5.4, 0., 5.85], 'yaw': math.pi / 2, 'hold': 'handset', 'gesture': 'phone', 'face': 'scared'}]})]
    shots = []; lines = []
    for i, v in enumerate(views):
        sh = {'lines': [i, i], 'set': 'hotel', 'state': v['state'], 'ui': {'hud': False, 'subs': 'off'}}
        cam = {'pos': v['pos'], 'look': v['look'], 'fov': v['fov']}
        if v.get('tracks'): sh['tracks'] = v['tracks']; sh['camera'] = {'rig': 'path', 'keys': [dict(cam, t=0)]}
        else: sh['camera'] = {'preset': 'free', 'keys': [cam]}
        shots.append(sh); lines.append({'who': 'rec', 'text': '', 'start': float(i), 'end': float(i) + .99})
    ep = {'style': 'pixel3d', 'hud': {'show': False}, 'sets': {'hotel': {'type': 'hotel_nuit'}}, 'default_set': 'hotel', 'shots': shots, 'mood': 'neutral', 'title': 'chambre 313',
          'cast': {'rec': {'preset': 'receptionniste'}}}
    if objets is not None: ep['objets'] = objets
    return ep, lines


# ------------------------------------------------------------------ renderers
def render_ps1(ep, lines, aspect, size):
    from hstudio.pipeline import make_engine
    eng = make_engine('pixel3d', json.loads(json.dumps(ep)), lines, {}, len(lines) + .2, aspect)
    return [Image.fromarray(eng.render_lowres(i + .5)[0]).convert('RGB').resize(size, Image.NEAREST) for i in range(len(lines))]


def render_voxel(ep, lines, aspect, size):
    from hstudio.voxelgpu import from_ps1, contract as C, render
    c = from_ps1.build(json.loads(json.dumps(ep)), lines, len(lines) + .2, aspect, 24, lambda *_: None)
    tmp = Path(tempfile.mkdtemp(prefix='objets_')); cp = tmp / 'c.json'; C.save(c, cp)
    times = [round(i + .5, 2) for i in range(len(lines))]
    with gpu_lock(): render.run_painter(cp, None, 'nvidia', size, stills=times, stills_dir=tmp, quiet=True, fallback=True)
    return [Image.open(tmp / f't_{t:.2f}.png').convert('RGB').resize(size) for t in times]


def grid(rows, labels, size, title, rlabels=None):
    W, H = size; cols = max(len(r) for r in rows)
    im = Image.new('RGB', (cols * W, len(rows) * H + 22), (16, 16, 20)); d = ImageDraw.Draw(im)
    d.text((6, 5), title, fill=(255, 255, 255))
    for r, row in enumerate(rows):
        for i, a in enumerate(row):
            im.paste(a, (i * W, 22 + r * H))
            lab = labels[i] if i < len(labels) else ''
            if rlabels: lab = f'{lab}  [{rlabels[r]}]'
            d.rectangle([i * W, 22 + r * H, i * W + 7 * len(lab) + 8, 22 + r * H + 13], fill=(0, 0, 0)); d.text((i * W + 3, 22 + r * H + 1), lab, fill=(255, 255, 255))
    return im


def chunks(l, n): return [l[i:i + n] for i in range(0, len(l), n)]


def main():
    from hstudio.engines.pixel3d import sets as S, objets as OD
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default=''); ap.add_argument('--styles', default='ps1,voxel'); ap.add_argument('--modes', default='pose,tenu')
    ap.add_argument('--out', default=str(OUT)); ap.add_argument('--name', default=''); ap.add_argument('--per', type=int, default=8)
    ap.add_argument('--lot', default='', help='objets_<lot> : seulement les objets de ce lot (ex. --lot cuisine) ; sans --only ni --lot : la base (objets.py)')
    a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True); styles = a.styles.split(','); modes = a.modes.split(',')
    only = [x for x in a.only.split(',') if x]
    lot_names = {n for _, names in OD.LOTS for n in names}
    if a.lot: only = only + [n for lot, names in OD.LOTS if lot in (a.lot, 'objets_' + a.lot) for n in names]
    kinds = [k for k in OD.KINDS if (k in only) if only] if only else [k for k in OD.KINDS if k not in lot_names]
    helds = [h for h in OD.HELD if h in only or (h.startswith(tuple(o + '_' for o in only)))] if only else [h for h in OD.HELD if h not in lot_names]
    pre = (a.name + '_') if a.name else ''
    def run(style, ep, lines, aspect, size):
        t0 = time.time(); ims = (render_ps1 if style == 'ps1' else render_voxel)(ep, lines, aspect, size)
        print(f'{style} : {len(lines)} images en {time.time() - t0:.0f} s', flush=True); return ims
    if 'pose' in modes and kinds:
        for n, part in enumerate(chunks(kinds, a.per)):
            ep, lines = pose_episode(part)
            for st in styles:
                ims = run(st, ep, lines, '16:9', (480, 270)); p = out / f'{pre}poses_{st}_{n + 1}.png'
                grid([ims], part, (480, 270), f'OBJETS DETAILLES POSES - style {st.upper()} (cle `objets`)').save(p); print(p)
    if 'tenu' in modes and helds:
        for n, part in enumerate(chunks(helds, a.per)):
            ep, lines = held_episode(part)
            for st in styles:
                ims = run(st, ep, lines, '9:16', (270, 480)); rows = [ims[0::2], ims[1::2]]; p = out / f'{pre}tenus_{st}_{n + 1}.png'
                grid(rows, [f'{h} ({(HELD_POSE.get(h) or ("show",))[0]})' for h in part], (270, 480), f'OBJETS TENUS - style {st.upper()} : gros plan (haut), plan moyen (bas)').save(p); print(p)
    if 'avant_apres' in modes:
        legacy = [k for k in LEGACY_PROPS if not only or k in only]
        for n, part in enumerate(chunks(legacy, a.per)):
            for st in styles:
                rows = []
                for key in (None, 'detailles'):
                    ep, lines = pose_episode(part, key); rows.append(run(st, ep, lines, '16:9', (480, 270)))
                p = out / f'{pre}avant_apres_poses_{st}_{n + 1}.png'
                grid(rows, part, (480, 270), f'AVANT (sans la cle, haut) / APRES (`objets: detailles`, bas) - decors, style {st.upper()}', ['avant', 'apres']).save(p); print(p)
        lh = [k for k in LEGACY_HELD if not only or k in only]
        for n, part in enumerate(chunks(lh, a.per)):
            for st in styles:
                rows = []
                for key in (None, 'detailles'):
                    ep, lines = held_episode(part, key, LEGACY_POSE); rows.append(run(st, ep, lines, '9:16', (270, 480))[0::2])
                p = out / f'{pre}avant_apres_tenus_{st}_{n + 1}.png'
                grid(rows, part, (270, 480), f'AVANT / APRES - objets tenus (gros plan), style {st.upper()}', ['avant', 'apres']).save(p); print(p)
    if 'hotel' in modes:
        for st in styles:
            rows = []
            for key in (None, 'detailles'):
                ep, lines = hotel_episode(key); rows.append(run(st, ep, lines, '16:9', (480, 270)))
            p = out / f'{pre}hotel_avant_apres_{st}.png'
            grid(rows, ['standard', 'telephone', 'reception', 'il decroche'], (480, 270), f'CHAMBRE 313 - reception sans / avec `objets`, style {st.upper()}', ['avant', 'apres']).save(p); print(p)


if __name__ == '__main__': main()
