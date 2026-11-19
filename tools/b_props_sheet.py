"""python tools/b_props_sheet.py [--kinds a,b,c | --all] [--out dossier] [--cols 6]

Convertit des décors de PIXEL 3D en boîtes VOXEL (hstudio/voxelgpu/b_props.py), peint chacun seul sur le plateau avec le moteur GPU et assemble
des planches de contrôle. Sans --kinds : le catalogue entier (217 types), par lots de 24 images. Écrit aussi rapport.json (échecs, boîtes, textures perdues)."""
import argparse, json, math, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw
from hstudio.voxelgpu import b_props as BP, contract as C, render

FPS = 24; DUR = .5; N = int(math.ceil(DUR * FPS))


def bounds(boxes):
    lo = [min(b[k] - b[s] / 2 for b in boxes) for k, s in (('x', 'w'), ('y', 'h'), ('z', 'd'))]; hi = [max(b[k] + b[s] / 2 for b in boxes) for k, s in (('x', 'w'), ('y', 'h'), ('z', 'd'))]
    return lo, hi


def contract_for(items):
    stages, t = [], 0.
    for i, (kind, props, lights) in enumerate(items):
        lo, hi = bounds(props[0]['boxes']) if props[0]['boxes'] else ([-.5, 0, -.5], [.5, 1, .5])
        c = [(lo[j] + hi[j]) / 2 for j in range(3)]; r = max(hi[j] - lo[j] for j in range(3)) / 2 + .15
        pos = [c[0] + r * .9, c[1] + r * .55 + .3, c[2] + r * 2.3 + .6]; look = [c[0], c[1] * .9, c[2]]
        cam = [[*pos, *look, 42., 0.] for _ in range(N)]
        stages.append(dict(id=f'p{i:03d}_{kind}'.replace(':', '_'), world='plateau', t0=round(t, 4), t1=round(t + DUR, 4), tail=0., dissolve=0., mood=None, look={}, camera=cam, actors={}, focus_actor=None,
                           props=props, lights=lights, env=dict(floor=0x74685a, bg=0x3a4660, ambient=1.2, key=1.4, fog=0.004), foley_steps={}))
        t += DUR
    return dict(schema=C.SCHEMA, title='planche', genre='neutral', aspect='16:9', fps=FPS, duration=round(t, 4), casts={}, expressions=['neutral'], actor_cols=C.ACTOR_COLS, stages=stages,
                fx=[], captions=[], caption_style={}, hud=None, cards=[], audio={})


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--kinds', default=''); ap.add_argument('--all', action='store_true'); ap.add_argument('--out', default=str(ROOT / 'projects' / 'b_props_sheets'))
    ap.add_argument('--cols', type=int, default=6); ap.add_argument('--batch', type=int, default=24); ap.add_argument('--no-render', action='store_true'); a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    kinds = [k for k in a.kinds.split(',') if k] if a.kinds else BP.catalogue()
    rep = dict(total=len(kinds), ok=[], failed={}, empty=[], textures_lost={}, boxes={}, lights={})
    items = []
    for k in kinds:
        st = dict(textures=0)
        try:
            props, lights = BP.convert_props([dict(type='b:' + k, at=[0, 0])], st)
        except Exception as e:
            rep['failed'][k] = f'{type(e).__name__}: {str(e)[:140]}'; continue
        nb = len(props[0]['boxes']); rep['boxes'][k] = nb; rep['lights'][k] = len(lights)
        if not nb: rep['empty'].append(k); continue
        if st.get('textures_lost'): rep['textures_lost'][k] = st['textures_lost']
        if props[0].get('decals'): rep.setdefault('decals', {})[k] = len(props[0]['decals'])
        rep['ok'].append(k); items.append((k, props, lights))
    print(f"conversion : {len(rep['ok'])} / {rep['total']} ok, {len(rep['failed'])} en échec, {len(rep['empty'])} vides, {len(rep['textures_lost'])} avec textures d'image non portées")
    (out / 'rapport.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8')
    if a.no_render: return
    for bi in range(0, len(items), a.batch):
        chunk = items[bi:bi + a.batch]; c = contract_for(chunk); errs = C.validate(c)
        if errs: print('contrat refusé :', errs[:3]); continue
        cp = out / f'contrat_{bi // a.batch:02d}.json'; C.save(c, cp); sd = out / f'stills_{bi // a.batch:02d}'
        times = [round(s['t0'] + .12, 2) for s in c['stages']]; t0 = time.time()
        render.run_painter(cp, None, 'nvidia', (480, 360), stills=times, stills_dir=sd, quiet=True, fallback=True)
        tw, th = 480, 360; rows = (len(chunk) + a.cols - 1) // a.cols; sheet = Image.new('RGB', (tw * a.cols, th * rows), (20, 20, 24)); d = ImageDraw.Draw(sheet)
        for j, ((k, _, _), t) in enumerate(zip(chunk, times)):
            im = Image.open(sd / f't_{t:.2f}.png').convert('RGB').resize((tw, th)); x, y = (j % a.cols) * tw, (j // a.cols) * th; sheet.paste(im, (x, y)); d.rectangle([x, y, x + 8 * len(k) + 10, y + 16], fill=(0, 0, 0)); d.text((x + 4, y + 2), k, fill=(255, 255, 255))
        sheet.save(out / f'planche_{bi // a.batch:02d}.jpg', quality=82); print(f'planche {bi // a.batch:02d} : {len(chunk)} décors en {time.time() - t0:.0f} s')


if __name__ == '__main__': main()
