"""python tools/b_sets_sheet.py [--places | --episode episode.json] [--only a,b] [--out dossier] [--shot wide|medium|close|full]

Peint des lieux de PIXEL 3D avec le moteur VOXEL, un plan par lieu avec un personnage, par le directeur (caméra automatique, obstacles, ancres) -> planches de contrôle.
  --places : les lieux prêts de PIXEL 3D (38)      --episode : les `sets` d'un épisode PIXEL 3D (ex. la maison de « Léo dort déjà »)"""
import argparse, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw
from hstudio.voxelgpu import director, contract as C, render, b_sets as BS


def start_of(bs):
    if bs.indoor:                                  # dans une pièce : le centre (un « start » est souvent contre un mur, le personnage y serait de profil)
        for k, v in bs.world.a.items():
            if k.endswith('.center') or k == 'center': return v
    for k in ('start', 'path.start', 'sidewalk.left', 'shore', 'center', 'center.center'):
        p = bs.world.anchor(k)
        if p: return p
    if not bs.indoor and bs.world.a: return next(iter(bs.world.a.values()))
    for k, v in bs.world.a.items():
        if k.endswith('.center'): return v
    x0, z0, x1, z1 = bs.world.rect; return ((x0 + x1) / 2, (z0 + z1) / 2)


def episode(items, shot):
    sets = {n: s for n, s in items}; shots = []
    for n, s in items:
        bs = BS.get(n, s); x, z = start_of(bs)
        shots.append(dict(set=n, dur=.6, camera=dict(shot=shot, on=['lea']), actors=[dict(id='lea', at=[round(x, 2), round(z, 2)], facing='+z', face='neutral')], actions=[]))
    return dict(title='planche de lieux', genre='neutral', casts={'lea': {'preset': 'lina'}}, sets=sets, shots=shots, duration=round(.6 * len(shots), 2))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--places', action='store_true'); ap.add_argument('--episode'); ap.add_argument('--only', default=''); ap.add_argument('--out', default=str(ROOT / 'projects' / 'b_sets_sheets'))
    ap.add_argument('--shot', default='wide'); ap.add_argument('--cols', type=int, default=4); ap.add_argument('--batch', type=int, default=12); a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    if a.episode: items = list((json.loads(Path(a.episode).read_text(encoding='utf-8')).get('sets') or {}).items())
    else:
        from hstudio.engines.pixel3d import sets as S
        items = [(n, {'type': n}) for n in S.PLACE_TYPES]
    if a.only: keep = set(a.only.split(',')); items = [i for i in items if i[0] in keep]
    rep = dict(ok=[], failed={}, limits={})
    for bi in range(0, len(items), a.batch):
        chunk = []
        for n, s in items[bi:bi + a.batch]:
            try: bs = BS.get(n, s); chunk.append((n, s)); rep['limits'][n] = bs.limits
            except Exception as e: rep['failed'][n] = f'{type(e).__name__}: {str(e)[:160]}'; print('ÉCHEC', n, rep['failed'][n])
        if not chunk: continue
        try: c = director.build(episode(chunk, a.shot), '16:9', 24)
        except Exception as e:
            for n, _ in chunk: rep['failed'][n] = f'directeur : {type(e).__name__}: {str(e)[:200]}'
            print('ÉCHEC directeur', e); continue
        cp = out / f'contrat_{bi // a.batch:02d}.json'; C.save(c, cp); sd = out / f'stills_{bi // a.batch:02d}'
        times = [round(s['t0'] + .3, 2) for s in c['stages']]; t0 = time.time()
        render.run_painter(cp, None, 'nvidia', (640, 360), stills=times, stills_dir=sd, quiet=True, fallback=True)
        tw, th = 640, 360; rows = (len(chunk) + a.cols - 1) // a.cols; sheet = Image.new('RGB', (tw * a.cols, th * rows), (20, 20, 24)); d = ImageDraw.Draw(sheet)
        for j, ((n, _), t) in enumerate(zip(chunk, times)):
            im = Image.open(sd / f't_{t:.2f}.png').convert('RGB').resize((tw, th)); x, y = (j % a.cols) * tw, (j // a.cols) * th; sheet.paste(im, (x, y)); d.rectangle([x, y, x + 8 * len(n) + 10, y + 16], fill=(0, 0, 0)); d.text((x + 4, y + 2), n, fill=(255, 255, 255)); rep['ok'].append(n)
        sheet.save(out / f'planche_{bi // a.batch:02d}.jpg', quality=82); print(f'planche {bi // a.batch:02d} : {len(chunk)} lieux en {time.time() - t0:.0f} s')
    (out / 'rapport.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8'); print(f"{len(rep['ok'])} peints, {len(rep['failed'])} en échec")


if __name__ == '__main__': main()
