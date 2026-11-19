"""python tools/voxelize_bank.py <dossier_du_pack> <nom_de_banque> --license "CC0" --author "..." --source URL [--credit "texte"] [--max 99999]

Voxélise tous les modèles glTF d'un pack (hstudio/voxelgpu/mesh_voxelize.py) vers voxelgpu_js/assets_vox/<banque>/<nom>.vox et écrit CREDITS.json
(licence, auteur, source, crédit exigé ou non : `commercial_ok` et `credit_required` servent à `tools/export_commercial.py`)."""
import argparse, json, re, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu import mesh_voxelize as MV


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('pack'); ap.add_argument('bank'); ap.add_argument('--license', default='CC0'); ap.add_argument('--author', default='?'); ap.add_argument('--source', default='')
    ap.add_argument('--credit', default=''); ap.add_argument('--credit-required', action='store_true'); ap.add_argument('--personal-only', action='store_true'); ap.add_argument('--max', type=int, default=10**6)
    ap.add_argument('--target', type=int, default=28); a = ap.parse_args()
    out = ROOT / 'voxelgpu_js' / 'assets_vox' / a.bank; out.mkdir(parents=True, exist_ok=True)
    files = {}
    for p in sorted(Path(a.pack).rglob('*')):
        if p.suffix.lower() not in ('.gltf', '.glb') or any(x in p.parts for x in ('.git', 'fbx(unity)')) or '/animations' in p.as_posix().lower() or 'rig_' in p.stem.lower(): continue
        k = re.sub(r'[^a-z0-9_]+', '_', p.stem.lower()).strip('_')
        if k not in files or (p.suffix.lower() == '.gltf' and files[k].suffix.lower() != '.gltf'): files[k] = p
    done, bad, t0, scales = 0, {}, time.time(), {}
    for k, p in list(files.items())[:a.max]:
        try:
            keys, cols, v = MV.voxelize(p, target=a.target); MV.write_vox(out / f'{k}.vox', keys, cols); scales[k] = round(float(v), 5); done += 1
        except Exception as e: bad[k] = f'{type(e).__name__}: {str(e)[:80]}'
        if (done + len(bad)) % 50 == 0: print(f'  {done + len(bad)}/{len(files)} ({time.time() - t0:.0f} s)', flush=True)
    meta = dict(name=a.bank, author=a.author, source=a.source, license=a.license, credit_required=a.credit_required, commercial_ok=not a.personal_only, personal_only=a.personal_only,
                credit_text=a.credit or (f'{a.author} — {a.license}' if a.credit_required else ''), voxel_m='variable : fixé par modèle (voxélisation de maillages)',
                changes='maillage 3D converti en voxels (échantillonnage des triangles, couleurs de la texture, palette réduite)', models=done)
    (out / 'CREDITS.json').write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding='utf-8')
    (out / 'SCALES.json').write_text(json.dumps(scales, indent=0), encoding='utf-8')      # mètres par voxel de chaque modèle (le .vox ne la garde pas)
    print(f'{a.bank} : {done} modèles voxélisés, {len(bad)} en échec ({time.time() - t0:.0f} s)', bad if bad else '')


if __name__ == '__main__': main()
