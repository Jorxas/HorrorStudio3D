"""python tools/b_chars_sheet.py [--what outfits,hats,hair,hold,presets,animals | all] [--out dossier] [--only a,b]

Peint les tenues, chapeaux, coiffures, objets en main, personnages prêts et animaux de PIXEL 3D avec le moteur VOXEL, par le directeur (la vraie chaîne : `casts` -> b_chars.py -> contrat -> peintre),
un plan large + un gros plan (ou un plan de côté pour les animaux) par élément, et assemble des planches de contrôle (rapport.json : échecs)."""
import argparse, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw
from hstudio.voxelgpu import director, contract as C, render
from hstudio.engines.pixel3d import poses as P, creatures as CR

BASE = dict(preset='npc', variant=2)


def groups():
    return {
        'outfits': [(o, dict(BASE, outfit=o, hood=[70, 90, 150] if o not in ('lab_coat', 'apron', 'spacesuit') else None)) for o in P.OUTFITS],
        'hats': [(h, dict(BASE, outfit='shirt', hat=h)) for h in P.HATS if h != 'none'],
        'hair': [(s, dict(BASE, outfit='tshirt', hair_style=s, hair=[150, 90, 40])) for s in P.HAIR_STYLES],
        'hold': [(h, dict(BASE, outfit='shirt', hold=h)) for h in P.HOLD_ITEMS],
        'presets': [(n, dict(b_preset=n, variant=2)) for n in CR.PRESETS],
        'animals': [(a, dict(kind='animal', animal=a)) for a in CR.ANIMALS] + [('bird_fly', dict(kind='animal', animal='bird', posture='fly')), ('dragon_fly', dict(kind='animal', animal='dragon', posture='fly')),
                                                                                  ('dog_sit', dict(kind='animal', animal='dog', posture='sit')), ('cat_lie', dict(kind='animal', animal='cat', posture='lie'))],
    }


def episode(chunk, animal):
    casts, shots = {}, []
    for i, (label, cast) in enumerate(chunk):
        cid = f'c{i}'; casts[cid] = {k: v for k, v in cast.items() if v is not None}
        for kind, cam in (('wide', dict(shot='full', on=[cid])), ('close', dict(shot='medium', on=[cid]))):
            shots.append(dict(stage='plateau', dur=.5, camera=cam, env=dict(floor=0x7a7268, bg=0x6a7a98, ambient=2.2, key=2.2, fog=0.002), actors=[dict(id=cid, at=[0, 0], facing='+z', face='neutral')], actions=[], reset=True))
    return dict(title='planche', genre='neutral', casts=casts, shots=shots, duration=round(.5 * len(shots), 2))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--what', default='all'); ap.add_argument('--only', default=''); ap.add_argument('--out', default=str(ROOT / 'projects' / 'b_chars_sheets')); ap.add_argument('--batch', type=int, default=12)
    a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    G = groups(); names = list(G) if a.what == 'all' else a.what.split(',')
    rep = dict(ok=[], failed={})
    for g in names:
        items = [i for i in G[g] if not a.only or i[0] in a.only.split(',')]
        for bi in range(0, len(items), a.batch):
            chunk = items[bi:bi + a.batch]; tag = f'{g}_{bi // a.batch:02d}'
            try:
                c = director.build(episode(chunk, g == 'animals'), '16:9', 24)
                for j, st in enumerate(c['stages']):                 # cadre à la main : même distance pour tous (les animaux ne sont pas à l'échelle humaine)
                    lab = chunk[j // 2][0]; wide = j % 2 == 0
                    if g == 'animals':
                        pos = [1.6, 1.0, 3.2] if wide else [2.2, .7, 1.2]; look = [0, .55, 0]
                        if lab in ('horse', 'cow'): pos = [3.4, 1.6, 6.6] if wide else [4.2, 1.2, 3.2]; look = [0, .9, 0]
                        if 'dragon' in lab: pos = [4.5, 2.6, 8.5] if wide else [6, 2.4, 4.5]; look = [0, 1.4, 0]
                        if lab == 'bird_fly': look = [0, 1.9, 0]; pos = [1.6, 2.0, 3.2] if wide else [2.0, 1.9, 1.5]
                    else: pos = [1.2, 1.35, 5.6] if wide else [0.5, 1.75, 2.1]; look = [0, 1.0, 0] if wide else [0, 1.65, 0]
                    st['camera'] = [[*pos, *look, 40., 0.] for _ in st['camera']]
                cp = out / f'contrat_{tag}.json'; C.save(c, cp); sd = out / f'stills_{tag}'
                times = [round(s['t0'] + .25, 2) for s in c['stages']]; t0 = time.time()
                render.run_painter(cp, None, 'nvidia', (360, 480), stills=times, stills_dir=sd, quiet=True, fallback=True)
                tw, th = 360, 480; cols = 6; rows = (len(chunk) * 2 + cols - 1) // cols; sheet = Image.new('RGB', (tw * cols, th * rows), (20, 20, 24)); d = ImageDraw.Draw(sheet)
                for j, t in enumerate(times):
                    im = Image.open(sd / f't_{t:.2f}.png').convert('RGB').resize((tw, th)); x, y = (j % cols) * tw, (j // cols) * th; sheet.paste(im, (x, y))
                    lab = chunk[j // 2][0] + (' (plan large)' if j % 2 == 0 else ' (gros plan)'); d.rectangle([x, y, x + 7 * len(lab) + 8, y + 15], fill=(0, 0, 0)); d.text((x + 4, y + 2), lab, fill=(255, 255, 255))
                sheet.save(out / f'planche_{tag}.jpg', quality=84); rep['ok'] += [i[0] for i in chunk]; print(f'planche {tag} : {len(chunk)} éléments en {time.time() - t0:.0f} s')
            except Exception as e:
                for i in chunk: rep['failed'][f'{g}/{i[0]}'] = f'{type(e).__name__}: {str(e)[:200]}'
                print('ÉCHEC', tag, type(e).__name__, str(e)[:300])
    (out / 'rapport.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8'); print(f"{len(rep['ok'])} peints, {len(rep['failed'])} en échec")


if __name__ == '__main__': main()
