"""python tools/style_check.py (--craft nom[:graine] | --all | --bset fichier.json | --vox banque/nom | --decor nom) [--kind decor|item|creature|structure] [--json]

Note un élément contre NOTRE style (docs/STYLE_GUIDE_STUDIO.md, hstudio/voxelgpu/style_reference.json) et sort des alertes lisibles. Ne modifie rien.
  --craft oak_tree:3   une recette `craft` (graine 3)      --all   toutes les recettes `craft` enregistrées, un tableau, code de sortie 1 si une alerte « à revoir »
  --bset f.json        un accessoire `bset` ({"boxes": [...]}) ou une liste de boîtes     --vox mmmm/chr_nun   un modèle importé, MESURÉ comme référence (il n'est pas destiné à la production)
  --decor bed          un de nos décors de PIXEL 3D (contrôle : il doit passer)
Niveaux : « à revoir » (écart net : à corriger avant de livrer) et « attention » (écart à regarder)."""
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu import b_style as ST, craft as CR


def show(label, r, kind, as_json=False):
    if as_json: return dict(label=label, kind=kind, score=r['score'], alerts=r['alerts'], metrics=r['metrics'])
    m = r['metrics']
    head = f"{label:<28} [{kind}] note {r['score']:>3}" + (f"   {m['n_boxes']} boîtes, {m['n_colors']} couleurs, S {m['S_mean']:.2f}, V {m['V_mean']:.2f}, petits cubes {m['micro_cube_share']:.0%}, {m['extent_m']:.2f} m" if m else '')
    print(head)
    for lv, t in r['alerts']: print(f"    {'✗' if lv == 'à revoir' else '!'} {lv} : {t}")
    return None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--craft'); ap.add_argument('--all', action='store_true'); ap.add_argument('--bset'); ap.add_argument('--vox'); ap.add_argument('--decor'); ap.add_argument('--kind', default='')
    ap.add_argument('--json', action='store_true'); ap.add_argument('--quiet', action='store_true', help='avec --all : ne détaille que les éléments avec alertes'); a = ap.parse_args()
    out, bad = [], 0
    if a.craft or a.all:
        CR.load_all(); jobs = []
        if a.all:
            for n, r in sorted(CR.REG.items()):
                for s in range(r['variants']): jobs.append((n, s))
        else:
            n, _, s = a.craft.partition(':'); jobs.append((n, int(s or 0)))
        for n, s in jobs:
            kind = a.kind or CR.REG[n]['kind']
            try: boxes, _ = CR.build(n, s)
            except Exception as e: print(f'{n}#{s} : ERREUR {type(e).__name__}: {e}'); bad += 1; continue
            r = ST.check(boxes, kind, CR.PAL); bad += any(lv == 'à revoir' for lv, _ in r['alerts']); out.append(show(f'{n}#{s}', r, kind, a.json)) if (a.json or not a.quiet or r['alerts']) else None
        if a.all and not a.json: print(f'\n{len(jobs)} éléments, {bad} à revoir')
    elif a.bset:
        d = json.loads(Path(a.bset).read_text(encoding='utf-8')); boxes = d['boxes'] if isinstance(d, dict) else d
        r = ST.check(boxes, a.kind or 'decor', CR.PAL); bad += any(lv == 'à revoir' for lv, _ in r['alerts']); out.append(show(Path(a.bset).stem, r, a.kind or 'decor', a.json))
    elif a.vox:
        from hstudio.voxelgpu import vox_import as VI
        p = VI.bset(a.vox); r = ST.check(p['boxes'], a.kind or 'decor', CR.PAL); out.append(show(a.vox, r, a.kind or 'decor', a.json))
    elif a.decor:
        from hstudio.voxelgpu import b_props as BP
        p, _ = BP.convert_item(dict(type='b:' + a.decor, at=[0, 0])); r = ST.check(p['boxes'], a.kind or 'decor', CR.PAL); out.append(show(a.decor, r, a.kind or 'decor', a.json))
    else: ap.print_help(); return 2
    if a.json: print(json.dumps(out, ensure_ascii=False, indent=1))
    return 1 if bad else 0


if __name__ == '__main__': sys.exit(main())
