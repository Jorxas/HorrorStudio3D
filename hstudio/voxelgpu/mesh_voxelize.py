"""Voxélisation de modèles 3D (glTF 2.0) -> fichiers MagicaVoxel (.vox) lisibles par `vox_import.py`.

Pourquoi : les banques de modèles libres (CC0) sont presque toutes en maillages ; le moteur VOXEL, lui, ne sait peindre que des boîtes. Un maillage est donc
échantillonné sur ses triangles (couleur prise dans la texture ou le facteur de couleur du matériau), rangé dans une grille de voxels, puis écrit en .vox. Le résultat
a le grain « bloc » du reste du moteur ; c'est une conversion, pas une copie fidèle : les courbes deviennent des marches, les détails plus petits qu'un voxel disparaissent.

Lit : .gltf (+ .bin et image externes) et .glb ; hiérarchie de noeuds avec translation / rotation / échelle / matrice ; plusieurs primitives ; `baseColorTexture`
(+ `TEXCOORD_0`) ou `baseColorFactor`. Les personnages animés sont pris dans leur pose de repos (peaux et animations ignorées).
Repère : glTF Y vers le haut, face avant vers +z -> MagicaVoxel Z vers le haut, face avant vers -Y (inverse exact de `vox_import`).
"""
import base64, json, struct
from pathlib import Path
import numpy as np
from PIL import Image

_COMP = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
_NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


def _load(path):
    path = Path(path); raw = path.read_bytes()
    if raw[:4] == b'glTF':                                      # .glb : en-tête, puis morceaux JSON et BIN
        o = 12; js = None; binc = None
        while o < len(raw):
            n, t = struct.unpack_from('<II', raw, o); body = raw[o + 8:o + 8 + n]
            if t == 0x4E4F534A: js = json.loads(body.decode('utf-8'))
            elif t == 0x004E4942 and binc is None: binc = body
            o += 8 + n
        g = js; buffers = [binc]
    else:
        g = json.loads(raw.decode('utf-8')); buffers = []
        for b in g.get('buffers', []):
            u = b.get('uri', '')
            buffers.append(base64.b64decode(u.split(',', 1)[1]) if u.startswith('data:') else (path.parent / u).read_bytes())
    return g, buffers


def _accessor(g, buffers, idx):
    a = g['accessors'][idx]; bv = g['bufferViews'][a['bufferView']]; dt = np.dtype(_COMP[a['componentType']]); nc = _NCOMP[a['type']]
    off = bv.get('byteOffset', 0) + a.get('byteOffset', 0); n = a['count']; stride = bv.get('byteStride') or dt.itemsize * nc
    buf = buffers[bv['buffer']]
    if stride == dt.itemsize * nc: arr = np.frombuffer(buf, dt, count=n * nc, offset=off).reshape(n, nc)
    else: arr = np.stack([np.frombuffer(buf, dt, count=nc, offset=off + i * stride) for i in range(n)])
    arr = arr.astype(np.float64) if a.get('normalized') or dt.kind == 'f' else arr.astype(np.int64)
    if a.get('normalized'): arr = arr / float(np.iinfo(dt).max if dt.kind in 'iu' else 1.)
    return arr


def _node_matrix(nd):
    if 'matrix' in nd: return np.array(nd['matrix'], float).reshape(4, 4).T
    t = np.array(nd.get('translation', [0, 0, 0]), float); q = np.array(nd.get('rotation', [0, 0, 0, 1]), float); s = np.array(nd.get('scale', [1, 1, 1]), float)
    x, y, z, w = q / (np.linalg.norm(q) or 1.)
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)], [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    M = np.eye(4); M[:3, :3] = R * s; M[:3, 3] = t; return M


def triangles(path):
    """-> liste de (sommets (n,3), uv (n,2) ou None, indices (m,3), matériau) en coordonnées monde de la scène"""
    g, buffers = _load(path); out = []
    base = Path(path).parent
    imgs = {}
    def image(i):
        if i not in imgs:
            im = g['images'][i]
            if 'uri' in im and not im['uri'].startswith('data:'): imgs[i] = np.asarray(Image.open(base / im['uri']).convert('RGBA'))
            elif 'uri' in im: imgs[i] = np.asarray(Image.open(__import__('io').BytesIO(base64.b64decode(im['uri'].split(',', 1)[1]))).convert('RGBA'))
            else: bv = g['bufferViews'][im['bufferView']]; o = bv.get('byteOffset', 0); imgs[i] = np.asarray(Image.open(__import__('io').BytesIO(buffers[bv['buffer']][o:o + bv['byteLength']])).convert('RGBA'))
        return imgs[i]
    def material(mi):
        if mi is None or mi >= len(g.get('materials', [])): return dict(factor=(.7, .7, .7, 1.), tex=None)
        pm = g['materials'][mi].get('pbrMetallicRoughness', {}); f = tuple(pm.get('baseColorFactor', (1, 1, 1, 1))); t = None
        if 'baseColorTexture' in pm: t = image(g['textures'][pm['baseColorTexture']['index']]['source'])
        return dict(factor=f, tex=t)
    def visit(ni, M):
        nd = g['nodes'][ni]; M = M @ _node_matrix(nd)
        if 'mesh' in nd:
            for pr in g['meshes'][nd['mesh']]['primitives']:
                if pr.get('mode', 4) != 4: continue
                P = _accessor(g, buffers, pr['attributes']['POSITION']); P = (np.c_[P, np.ones(len(P))] @ M.T)[:, :3]
                uv = _accessor(g, buffers, pr['attributes']['TEXCOORD_0']) if 'TEXCOORD_0' in pr['attributes'] else None
                I = _accessor(g, buffers, pr['indices']).astype(int).reshape(-1, 3) if 'indices' in pr else np.arange(len(P)).reshape(-1, 3)
                out.append((P, uv, I, material(pr.get('material'))))
        for c in nd.get('children', []): visit(c, M)
    sc = g['scenes'][g.get('scene', 0)]
    for n in sc['nodes']: visit(n, np.eye(4))
    return out


def voxelize(path, voxel=None, target=28, vmin=.03, vmax=.125, color_bits=5):
    """-> (voxels (n,4) entiers x, y, z (repère glTF, Y haut), couleurs (n,3) uint8, taille de voxel en mètres)"""
    tris = triangles(path)
    if not tris: raise ValueError(f'{Path(path).name} : aucun triangle')
    allp = np.vstack([t[0] for t in tris]); lo, hi = allp.min(0), allp.max(0); dim = float((hi - lo).max())
    v = voxel or float(np.clip(dim / target, vmin, vmax))
    acc = {}                                                       # voxel -> [somme rgb, n]
    for P, uv, I, mat in tris:
        A, B, Cc = P[I[:, 0]], P[I[:, 1]], P[I[:, 2]]
        area = .5 * np.linalg.norm(np.cross(B - A, Cc - A), axis=1); ns = np.clip(np.ceil(area / (v * v) * 3.).astype(int), 1, 4000)
        for k in range(len(I)):
            n = ns[k]; r1 = np.sqrt(np.random.default_rng(k).random(n)); r2 = np.random.default_rng(k + 7).random(n)
            if n == 1: r1, r2 = np.array([.5]), np.array([.5])
            w0, w1, w2 = 1 - r1, r1 * (1 - r2), r1 * r2
            pts = w0[:, None] * A[k] + w1[:, None] * B[k] + w2[:, None] * Cc[k]
            if mat['tex'] is not None and uv is not None:
                u = w0[:, None] * uv[I[k, 0]] + w1[:, None] * uv[I[k, 1]] + w2[:, None] * uv[I[k, 2]]
                h, w_ = mat['tex'].shape[:2]; xi = np.clip((u[:, 0] % 1.0 * w_).astype(int), 0, w_ - 1); yi = np.clip((u[:, 1] % 1.0 * h).astype(int), 0, h - 1)
                col = mat['tex'][yi, xi, :3].astype(float) * np.array(mat['factor'][:3])
            else: col = np.tile(np.array(mat['factor'][:3]) * 255., (n, 1))
            cell = np.floor((pts - lo) / v).astype(int)
            for c, cc in zip(map(tuple, cell), col):
                e = acc.get(c)
                if e is None: acc[c] = [cc.copy(), 1]
                else: e[0] += cc; e[1] += 1
    keys = np.array(list(acc.keys())); cols = np.array([acc[tuple(k)][0] / acc[tuple(k)][1] for k in keys])
    sh = 8 - color_bits; cols = (np.clip(cols, 0, 255).astype(np.uint8) >> sh << sh) | (1 << max(0, sh - 1))      # quantification : moins de couleurs = plus de fusion
    return keys, cols.astype(np.uint8), v


def write_vox(path, keys, cols):
    """voxels (repère glTF) + couleurs -> fichier .vox (Z haut, face avant vers -Y), palette de 255 couleurs"""
    # glTF (x, y haut, z devant) -> MagicaVoxel (x, y = -z, z = y)
    x = keys[:, 0]; z = keys[:, 1]; y = (keys[:, 2].max() - keys[:, 2])
    xyz = np.column_stack([x, y, z]).astype(int); xyz -= xyz.min(0)
    im = Image.new('RGB', (len(cols), 1)); im.putdata([tuple(int(c) for c in rgb) for rgb in cols])
    q = im.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE); idx = np.asarray(q, np.uint8).reshape(-1) + 1
    pal = np.asarray(q.getpalette()[:255 * 3], np.uint8).reshape(-1, 3)
    pal = np.vstack([pal, np.zeros((255 - len(pal), 3), np.uint8)])
    size = xyz.max(0) + 1
    xyzi = b''.join(struct.pack('<BBBB', int(a), int(b), int(c), int(i)) for (a, b, c), i in zip(xyz, idx))
    rgba = b''.join(struct.pack('<BBBB', int(r), int(g_), int(b_), 255) for r, g_, b_ in pal) + b'\x00' * 4
    def chunk(cid, content, children=b''): return cid + struct.pack('<ii', len(content), len(children)) + content + children
    main = chunk(b'MAIN', b'', chunk(b'SIZE', struct.pack('<iii', *map(int, size))) + chunk(b'XYZI', struct.pack('<i', len(xyz)) + xyzi) + chunk(b'RGBA', rgba))
    Path(path).write_bytes(b'VOX ' + struct.pack('<i', 150) + main)
    return int(len(xyz)), tuple(int(s) for s in size)
