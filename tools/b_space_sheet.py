"""python tools/b_space_sheet.py [--out dossier]  -> planche avant/après : mêmes plans, séparation éteinte (haut) puis allumée (bas), peints par le moteur VOXEL (GPU)."""
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'tools'))
from PIL import Image, ImageDraw
from hstudio.voxelgpu import director, contract as C, render
import b_space_audit as AU

PICKS = [('face_a_face_trop_pres', 2.0), ('marche_vers_l_autre', 4.5), ('croisement', 3.0), ('meuble_sur_le_chemin', 3.0), ('trois_en_discussion', 3.0)]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default=str(ROOT / 'projects' / 'b_space_sheet')); a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    C0 = AU.cases(); rows = []
    for mode in (False, True):
        shots, picks, t = [], [], 0.
        for name, rel in PICKS:
            for s in C0[name]['shots']: shots.append(dict(s, reset=True)); picks.append(round(t + rel, 2)); t += s['dur']
        ep = dict(title='b_space', genre='neutral', casts=AU.CASTS, spacing=mode, shots=shots, duration=t)
        c = director.build(ep, '16:9', 24); cp = out / f'c_{int(mode)}.json'; C.save(c, cp); sd = out / f's_{int(mode)}'
        render.run_painter(cp, None, 'nvidia', (640, 360), stills=picks, stills_dir=sd, quiet=True, fallback=True)
        rows.append([Image.open(sd / f't_{p:.2f}.png').convert('RGB') for p in picks])
    W, H = 640, 360; sh = Image.new('RGB', (W * len(PICKS), H * 2 + 20), (16, 16, 20)); d = ImageDraw.Draw(sh)
    for r, label in enumerate(('AVANT (séparation éteinte)', 'APRÈS (séparation allumée)')):
        for i, im in enumerate(rows[r]):
            sh.paste(im.resize((W, H)), (i * W, r * H + 20 * (r > 0))); d.rectangle([i * W, r * H + 20 * (r > 0), i * W + 330, r * H + 18 + 20 * (r > 0)], fill=(0, 0, 0)); d.text((i * W + 4, r * H + 3 + 20 * (r > 0)), f'{PICKS[i][0]} — {label}', fill=(255, 255, 255))
    sh.save(out / 'avant_apres.jpg', quality=85); print('planche :', out / 'avant_apres.jpg')


if __name__ == '__main__': main()
