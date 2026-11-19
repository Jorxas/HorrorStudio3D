"""python tools/b_monsters_sheet.py [--only slender,demon] [--out dossier] [--human] [--shots front,q34,back,close,walk]

Planches de contrôle des créatures non humanoïdes (hstudio/voxelgpu/b_monsters.py + voxelgpu_js/engine/b_monsters.js), par le directeur (la vraie chaîne : casts -> contrat -> peintre GPU) :
une ligne par archétype, une colonne par vue (face, 3/4, dos, gros plan, en marche). `--human` ajoute un personnage humain à côté pour juger l'échelle, l'ombre et la lumière."""
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw
from hstudio.voxelgpu import director, contract as C, render, b_monsters as BM

VIEWS = {
    'front': dict(label='face', facing='+z', cam=dict(shot='wide'), dur=.5, at=.25),
    'q34': dict(label='3/4', facing=0.9, cam=dict(shot='wide'), dur=.5, at=.25),
    'back': dict(label='dos', facing='-z', cam=dict(shot='wide'), dur=.5, at=.25),
    'close': dict(label='gros plan', facing='+z', cam=dict(shot='medium'), dur=.5, at=.25),
    'walk': dict(label='marche', facing='+x', cam=dict(shot='wide'), dur=1.6, at=1.1, walk=True),
}
ENV = dict(floor=0x5a564e, bg=0x3a4660, ambient=2.4, key=2.2, fog=0.004)


def episode(names, views, human):
    casts, shots = {}, []
    for i, n in enumerate(names):
        cid = f'm{i}'; casts[cid] = {'kind': 'creature', 'archetype': n}
        if human and i == 0: casts['h'] = {'preset': 'noe'}
        for v in views:
            V = VIEWS[v]; on = [cid] + (['h'] if human else [])
            actors = [dict(id=cid, at=[0, 0], facing=V['facing'])] + ([dict(id='h', at=[-1.4, 0.4], facing='+z', face='scared')] if human else [])
            actions = [dict(who=cid, do='walk_to', to=[3.2, 0], at=0.1, speed='slow')] if V.get('walk') else []
            shots.append(dict(stage='plateau', dur=V['dur'], camera=dict(V['cam'], on=on if human else [cid]), env=ENV, actors=actors, actions=actions, reset=True))
    return dict(title='planche', genre='neutral', casts=casts, shots=shots, duration=round(sum(s['dur'] for s in shots), 2))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--only', default=''); ap.add_argument('--out', default=str(ROOT / 'projects' / 'b_monsters_sheets')); ap.add_argument('--human', action='store_true')
    ap.add_argument('--shots', default='front,q34,back,close,walk'); ap.add_argument('--per', type=int, default=4); a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True); views = a.shots.split(',')
    names = [n for n in BM.ARCH if not a.only or n in a.only.split(',')]; rep = {'ok': [], 'failed': {}}
    for bi in range(0, len(names), a.per):
        chunk = names[bi:bi + a.per]
        try: c = director.build(episode(chunk, views, a.human), '16:9', 24)
        except Exception as e:
            rep['failed'][','.join(chunk)] = f'{type(e).__name__}: {str(e)[:200]}'; print('ÉCHEC', chunk, e); continue
        cp = out / f'c_{bi // a.per:02d}.json'; C.save(c, cp); sd = out / f's_{bi // a.per:02d}'
        times = [round(s['t0'] + VIEWS[views[j % len(views)]]['at'], 2) for j, s in enumerate(c['stages'])]
        print(f'rendu {chunk} ({len(times)} images)', flush=True)
        render.run_painter(cp, None, 'nvidia', (480, 360), stills=times, stills_dir=sd, quiet=True, fallback=True)
        tw, th = 480, 360; sheet = Image.new('RGB', (tw * len(views), th * len(chunk)), (20, 20, 24)); d = ImageDraw.Draw(sheet)
        for j, t in enumerate(times):
            r, k = divmod(j, len(views)); sheet.paste(Image.open(sd / f't_{t:.2f}.png').convert('RGB').resize((tw, th)), (k * tw, r * th))
            d.rectangle([k * tw, r * th, k * tw + 160, r * th + 16], fill=(0, 0, 0)); d.text((k * tw + 4, r * th + 2), f"{chunk[r]} — {VIEWS[views[k]]['label']}", fill=(255, 255, 255))
        sheet.save(out / f'planche_{bi // a.per:02d}.jpg', quality=84); rep['ok'] += chunk
    (out / 'rapport.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8'); print(f"{len(rep['ok'])} archétypes, {len(rep['failed'])} en échec")


if __name__ == '__main__': main()
