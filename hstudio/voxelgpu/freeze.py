"""Frozen SHA-256 manifests of the two source engines (read-only: nothing is ever written into A or B).

    python -m hstudio.voxelgpu.freeze a  out.json     # engine A (JS/Three.js): sources only, no node_modules / media
    python -m hstudio.voxelgpu.freeze b  out.json     # engine B (this worktree): git-tracked sources of hstudio/ tools/
    python -m hstudio.voxelgpu.freeze check manifest.json [root]   # compare the disk with a manifest

A has no git history, so this manifest is its only traceable state.
"""
import hashlib, json, os, subprocess, sys
from pathlib import Path

A_ROOT_DEFAULT = Path(r'C:\Users\demo\Videos\moteur_voxel')
B_ROOT = Path(__file__).resolve().parents[2]
A_SKIP_DIRS = {'node_modules', 'node', 'images', 'images_marche', 'images_marche2', 'montage', 'test_images', '.git', '__pycache__'}
A_SKIP_EXT = {'.mp4', '.zip', '.jpg', '.png', '.wav', '.mp3', '.m4a', '.onnx'}


def sha256(p, chunk=1 << 20):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(chunk), b''): h.update(b)
    return h.hexdigest()


def manifest_a(root=A_ROOT_DEFAULT):
    root = Path(root); files = {}
    for dp, dn, fn in os.walk(root):
        dn[:] = sorted(d for d in dn if d not in A_SKIP_DIRS)
        for f in sorted(fn):
            p = Path(dp) / f
            if p.suffix.lower() in A_SKIP_EXT: continue
            rel = p.relative_to(root).as_posix()
            files[rel] = {'sha256': sha256(p), 'bytes': p.stat().st_size}
    return {'engine': 'A voxel V4.1 (three.js r170)', 'root': str(root), 'files': files}


def manifest_b(root=B_ROOT):
    root = Path(root)
    head = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    out = subprocess.run(['git', '-C', str(root), 'ls-files', 'hstudio', 'tools', 'tests', 'docs/FORMAT_EPISODE.md', 'AGENTS.md'],
                         capture_output=True, text=True).stdout.split('\n')
    files = {}
    for rel in sorted(x for x in out if x):
        p = root / rel
        if p.is_file(): files[rel] = {'sha256': sha256(p), 'bytes': p.stat().st_size}
    return {'engine': 'B Horror Studio (NumPy CPU)', 'root': str(root), 'git_head': head, 'files': files}


def check(manifest, root=None):
    m = json.loads(Path(manifest).read_text(encoding='utf-8')); root = Path(root or m['root']); bad = []
    for rel, d in m['files'].items():
        p = root / rel
        if not p.is_file(): bad.append((rel, 'absent'))
        elif sha256(p) != d['sha256']: bad.append((rel, 'modifie'))
    return bad


if __name__ == '__main__':
    a = sys.argv[1:]
    if a and a[0] in ('a', 'b'):
        m = manifest_a(*(a[2:3] or [])) if a[0] == 'a' else manifest_b()
        Path(a[1]).write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding='utf-8')
        print(a[0].upper(), len(m['files']), 'fichiers ->', a[1])
    elif a and a[0] == 'check':
        bad = check(a[1], a[2] if len(a) > 2 else None); print('OK' if not bad else bad); sys.exit(1 if bad else 0)
    else: print(__doc__)
