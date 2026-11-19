"""Import de modèles MagicaVoxel (.vox) dans le moteur VOXEL : fichier -> boîtes colorées -> accessoire `bset` (voxelgpu_js/engine/b_kit.js).

Format lu : en-tête « VOX », chunks MAIN / SIZE / XYZI / RGBA, et le graphe de scène (nTRN / nGRP / nSHP) des versions récentes (translations et rotations
de 90°). Les voxels voisins de même couleur sont fusionnés en grosses boîtes (fusion gloutonne en 3D) : un personnage de 3 000 voxels devient quelques centaines
de boîtes, rendues avec le même grain et le même liseré que le reste des décors.

Repère : MagicaVoxel est en Z vers le haut, la face avant du modèle vers -Y. Le modèle est tourné (jamais retourné en miroir) pour avoir Y vers le haut et sa face
avant vers +z, c'est-à-dire vers la caméra de VOXEL ; l'origine est posée au sol, au centre de l'emprise.

Licences : chaque banque a son `CREDITS.json` à côté de ses fichiers (source, auteur, licence, texte de crédit). `credits_for(noms)` rend les lignes à mettre dans la
description d'une vidéo qui utilise ces modèles : une licence CC BY l'EXIGE.
"""
import json, struct
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BANKS = ROOT / 'voxelgpu_js' / 'assets_vox'          # une banque = un dossier : <banque>/<nom>.vox + CREDITS.json
_CACHE = {}
DEFAULT_PALETTE = None


def _default_palette():
    global DEFAULT_PALETTE
    if DEFAULT_PALETTE is None:
        pal = np.zeros((256, 4), np.uint8)
        for i in range(255):                      # palette par défaut de MagicaVoxel : un dégradé fidèle suffit quand un fichier n'en porte pas
            pal[i + 1] = (255 - (i * 7) % 256, (i * 37 + 40) % 256, (i * 91 + 20) % 256, 255)
        DEFAULT_PALETTE = pal
    return DEFAULT_PALETTE


def _dict(buf, o):
    n = struct.unpack_from('<i', buf, o)[0]; o += 4; d = {}
    for _ in range(n):
        kl = struct.unpack_from('<i', buf, o)[0]; o += 4; k = buf[o:o + kl].decode('latin1'); o += kl
        vl = struct.unpack_from('<i', buf, o)[0]; o += 4; d[k] = buf[o:o + vl].decode('latin1'); o += vl
    return d, o


def parse(path):
    """-> {'models': [(size, voxels (n,4) uint8 x,y,z,i)], 'palette': (256,4) uint8, 'nodes': {...}} ; rien n'est deviné : un fichier illisible lève une erreur claire"""
    buf = Path(path).read_bytes()
    if buf[:4] != b'VOX ': raise ValueError(f'{Path(path).name} : pas un fichier MagicaVoxel')
    models, size, pal, nodes = [], None, None, {}
    o = 8
    def walk(o, end):
        nonlocal size, pal
        while o < end:
            cid = buf[o:o + 4].decode('latin1'); n, m = struct.unpack_from('<ii', buf, o + 4); c0 = o + 12; c1 = c0 + n
            if cid == 'SIZE': size = struct.unpack_from('<iii', buf, c0)
            elif cid == 'XYZI':
                k = struct.unpack_from('<i', buf, c0)[0]; v = np.frombuffer(buf, np.uint8, count=k * 4, offset=c0 + 4).reshape(k, 4); models.append((size, v.copy()))
            elif cid == 'RGBA': pal = np.zeros((256, 4), np.uint8); pal[1:] = np.frombuffer(buf, np.uint8, count=1024, offset=c0).reshape(256, 4)[:255]
            elif cid == 'nTRN':
                nid = struct.unpack_from('<i', buf, c0)[0]; d, p = _dict(buf, c0 + 4); child = struct.unpack_from('<i', buf, p)[0]; p += 16; nf = struct.unpack_from('<i', buf, p)[0]; p += 4
                fr = {}
                for _ in range(nf): fr, p = _dict(buf, p)
                nodes[nid] = ('t', child, fr)
            elif cid == 'nGRP':
                nid = struct.unpack_from('<i', buf, c0)[0]; d, p = _dict(buf, c0 + 4); nc = struct.unpack_from('<i', buf, p)[0]; p += 4
                nodes[nid] = ('g', [struct.unpack_from('<i', buf, p + 4 * j)[0] for j in range(nc)])
            elif cid == 'nSHP':
                nid = struct.unpack_from('<i', buf, c0)[0]; d, p = _dict(buf, c0 + 4); nm = struct.unpack_from('<i', buf, p)[0]; p += 4
                nodes[nid] = ('s', struct.unpack_from('<i', buf, p)[0])
            if m: walk(c1, c1 + m)
            o = c1 + m
    walk(20, len(buf))
    return dict(models=models, palette=pal if pal is not None else _default_palette(), nodes=nodes)


def _rot(byte):
    """octet de rotation de MagicaVoxel -> matrice 3x3 (lignes de la matrice, signes et permutation)"""
    r0 = (byte & 3); r1 = (byte >> 2) & 3; r2 = 3 - r0 - r1 if r0 != r1 else 2
    M = np.zeros((3, 3), int); M[0, r0] = -1 if byte & 16 else 1; M[1, r1] = -1 if byte & 32 else 1; M[2, r2] = -1 if byte & 64 else 1
    return M


def _instances(sc):
    """les modèles posés dans la scène -> [(index de modèle, translation (3,), rotation 3x3)] (un fichier sans graphe : le modèle 0 à l'origine)"""
    nodes = sc['nodes']
    if not nodes: return [(i, np.zeros(3), np.eye(3, dtype=int)) for i in range(len(sc['models']))]
    out = []
    def go(nid, T, R):
        nd = nodes.get(nid)
        if nd is None: return
        if nd[0] == 't':
            fr = nd[2]; t = np.array([float(v) for v in fr.get('_t', '0 0 0').split()]); r = _rot(int(fr['_r'])) if '_r' in fr else np.eye(3, dtype=int)
            go(nd[1], T + R @ t, R @ r)
        elif nd[0] == 'g':
            for c in nd[1]: go(c, T, R)
        else: out.append((nd[1], T, R))
    go(0, np.zeros(3), np.eye(3, dtype=int)); return out


def voxels(sc):
    """toutes les instances -> (n, 4) entiers x, y, z (repère MagicaVoxel, Z vers le haut) et index de couleur"""
    parts = []
    for mi, T, R in _instances(sc):
        size, v = sc['models'][mi]
        if not len(v): continue
        c = np.array(size, float) / 2.; xyz = v[:, :3].astype(float) + .5 - c            # centre du modèle
        w = (R @ xyz.T).T + T
        parts.append(np.column_stack([np.floor(w).astype(int), v[:, 3]]))
    return np.vstack(parts) if parts else np.zeros((0, 4), int)


def greedy(vox):
    """voxels (x, y, z, couleur) -> boîtes (x0, y0, z0, nx, ny, nz, couleur) : fusion gloutonne en 3D de voxels voisins de même couleur"""
    if not len(vox): return []
    mn = vox[:, :3].min(0); g = {tuple(p): int(c) for *p, c in (vox - np.array([*mn, 0]))}
    done = set(); boxes = []
    for p in sorted(g, key=lambda q: (q[2], q[1], q[0])):
        if p in done: continue
        c = g[p]; x, y, z = p; nx = 1
        while (x + nx, y, z) in g and g[(x + nx, y, z)] == c and (x + nx, y, z) not in done: nx += 1
        ny = 1
        while all((x + i, y + ny, z) in g and g[(x + i, y + ny, z)] == c and (x + i, y + ny, z) not in done for i in range(nx)): ny += 1
        nz = 1
        while all((x + i, y + j, z + nz) in g and g[(x + i, y + j, z + nz)] == c and (x + i, y + j, z + nz) not in done for i in range(nx) for j in range(ny)): nz += 1
        for i in range(nx):
            for j in range(ny):
                for k in range(nz): done.add((x + i, y + j, z + k))
        boxes.append((x, y, z, nx, ny, nz, c))
    return boxes, mn


def load(path):
    """un fichier .vox -> dict(boxes (en unités de voxel, Y vers le haut), size (en voxels), palette) gardé en mémoire"""
    key = str(path)
    if key in _CACHE: return _CACHE[key]
    sc = parse(path); v = voxels(sc); res = greedy(v)
    if not res: raise ValueError(f'{Path(path).name} : aucun voxel')
    boxes, mn = res; pal = sc['palette']
    # MagicaVoxel (x, y, z) -> VOXEL (x, z, -y) : Z devient le haut, la face avant (-Y) regarde vers +z
    out = []; mx = np.array([0, 0, 0])
    for (x, y, z, nx, ny, nz, c) in boxes:
        r, g, b, a = (int(t) for t in pal[c])
        out.append(dict(x0=x, y0=z, z0=-(y + ny), w=nx, h=nz, d=ny, color=(r << 16) | (g << 8) | b))
    xs0 = min(b['x0'] for b in out); xs1 = max(b['x0'] + b['w'] for b in out); ys0 = min(b['y0'] for b in out); ys1 = max(b['y0'] + b['h'] for b in out)
    zs0 = min(b['z0'] for b in out); zs1 = max(b['z0'] + b['d'] for b in out)
    _CACHE[key] = dict(boxes=out, size=(int(xs1 - xs0), int(ys1 - ys0), int(zs1 - zs0)), lo=(int(xs0), int(ys0), int(zs0)), n_voxels=int(len(v)), palette=pal)
    return _CACHE[key]


def find(name):
    """`banque/nom` ou `nom` -> chemin du .vox dans voxelgpu_js/assets_vox/"""
    if '/' in name:
        b, n = name.split('/', 1); p = BANKS / b / (n if n.endswith('.vox') else n + '.vox')
        if p.exists(): return p
    else:
        for b in sorted(BANKS.glob('*')):
            p = b / (name if name.endswith('.vox') else name + '.vox')
            if p.exists(): return p
    raise FileNotFoundError(f'modèle voxel « {name} » introuvable dans {BANKS}')


def bset(name, scale=None, height=None, length=None, at=(0., 0.), y=0., rot=0, facing=None):
    """un modèle .vox -> accessoire `bset` posé au sol en `at` = [x, z] (repère VOXEL), tourné de `rot` quarts de tour.
    Échelle : `scale` (mètres par voxel), ou `height` (hauteur finale en mètres), ou `length` (plus grande dimension horizontale) ; sinon la taille d'un voxel de la banque."""
    p = find(name); m = load(p); sx, sy, sz = m['size']
    if scale is None:
        scale = (height / sy) if height else (length / max(sx, sz)) if length else bank_scale(p)
    cx = m['lo'][0] + sx / 2.; cz = m['lo'][2] + sz / 2.; cy = m['lo'][1]
    ry = (facing if facing is not None else rot * np.pi / 2)
    c, s = np.cos(ry), np.sin(ry); boxes = []
    for b in m['boxes']:
        lx = ((b['x0'] + b['w'] / 2.) - cx) * scale; lz = ((b['z0'] + b['d'] / 2.) - cz) * scale
        o = dict(x=round(lx * c + lz * s + at[0], 4), y=round(((b['y0'] + b['h'] / 2.) - cy) * scale + y, 4), z=round(-lx * s + lz * c + at[1], 4),
                 w=round(b['w'] * scale, 4), h=round(b['h'] * scale, 4), d=round(b['d'] * scale, 4), color=b['color'])
        if ry: o['ry'] = round(ry, 4)
        boxes.append(o)
    return dict(type='bset', boxes=boxes, vox=Path(p).parent.name + '/' + Path(p).stem)


def bank_scale(path):
    """mètres par voxel de la banque (fichier `CREDITS.json`, clé `voxel_m`) : la même pour tous les modèles d'une banque pour garder leurs proportions entre eux"""
    d = Path(path).parent
    try:
        sc = json.loads((d / 'SCALES.json').read_text(encoding='utf-8'))          # banques voxélisées depuis des maillages : une échelle par modèle
        if Path(path).stem in sc: return float(sc[Path(path).stem])
    except (OSError, ValueError): pass
    try: return float(json.loads((d / 'CREDITS.json').read_text(encoding='utf-8')).get('voxel_m', .0625))
    except (OSError, ValueError, TypeError): return .0625


def credits_for(names):
    """noms de modèles utilisés -> lignes de crédit à publier (une par banque, texte exigé par la licence)"""
    seen, out = set(), []
    for n in names:
        b = Path(find(n)).parent
        if b.name in seen: continue
        seen.add(b.name)
        try: c = json.loads((b / 'CREDITS.json').read_text(encoding='utf-8'))
        except (OSError, ValueError): continue
        out.append(c.get('credit_text') or f"{c.get('name', b.name)} — {c.get('author', '?')} — {c.get('license', '?')}")
    return out
