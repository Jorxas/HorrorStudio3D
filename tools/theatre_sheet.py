"""python tools/theatre_sheet.py [--out dossier] [--styles voxel,ps1] [--only 0,3] [--ref dossier_vignettes]

Planches du lieu `theatre_bal` : les plans de l'épisode d'exemple (examples/theatre/theatre_demo.py : plan large au lavis bleu, ambre, violet, poursuite
seule dans le noir, rideau de lumière, plan moyen devant les bougies, escalier et galerie, disque tacheté), chacun rendu en 1920x1080 dans chaque style,
et une planche de comparaison par plan : notre image à gauche, la vignette de référence la plus proche à droite (inspiration d'ambiance seulement).
Le rendu VOXEL passe par le peintre GPU (un seul passage pour toutes les images) : un seul rendu lourd à la fois sur la machine."""
import argparse, importlib.util, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import numpy as np
from PIL import Image, ImageDraw, ImageFont

LABELS = ['Plan large, lavis bleu de nuit', 'Plan large, ambre chaud', 'Plan large, violet (contre-plongée)', 'Poursuite seule dans le noir', 'Rideau de lumière',
          'Plan moyen devant les bougies', 'Escalier et galerie', 'Disque tacheté au sol (retour en arrière)']


def demo():
    spec = importlib.util.spec_from_file_location('theatre_demo', ROOT / 'examples' / 'theatre' / 'theatre_demo.py'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def font(sz):
    for f in (r'C:\Windows\Fonts\segoeui.ttf', r'C:\Windows\Fonts\arial.ttf'):
        if os.path.exists(f): return ImageFont.truetype(f, sz)
    return ImageFont.load_default()


def compare(ours, ref, title, style, out):
    W = 1280; a = ours.resize((W, 720), Image.LANCZOS); b = ref.resize((W, int(ref.height * W / ref.width)), Image.LANCZOS) if ref else Image.new('RGB', (W, 683), (20, 20, 20))
    H = max(a.height, b.height) + 60; im = Image.new('RGB', (2 * W + 20, H), (14, 14, 18)); im.paste(a, (0, 60)); im.paste(b, (W + 20, 60))
    d = ImageDraw.Draw(im); d.text((12, 12), f'{style} — {title}', font=font(30), fill=(240, 232, 214)); d.text((W + 32, 12), 'référence (ambiance seulement)', font=font(30), fill=(170, 170, 176))
    im.save(out, quality=92)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default=str(ROOT / 'projects' / 'theatre_planches')); ap.add_argument('--styles', default='voxel,ps1'); ap.add_argument('--only', default='')
    ap.add_argument('--ref', default=r'C:\Users\demo\Desktop\videpgene\CLIP_SATISFIED_VOXEL\reference\vignettes'); a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True); m = demo(); ep, lines = m.episode()
    only = [int(x) for x in a.only.split(',')] if a.only else list(range(len(m.SHOTS)))
    ts = {i: round(i * m.DUR + 1.0, 2) for i in only}
    refs = {i: (Image.open(Path(a.ref) / f"{m.SHOTS[i]['ref']}.jpg").convert('RGB') if (Path(a.ref) / f"{m.SHOTS[i]['ref']}.jpg").exists() else None) for i in only}
    for style in a.styles.split(','):
        t0 = time.time(); ims = {}
        if style == 'voxel':
            from hstudio.voxelgpu import from_ps1, contract as C, render
            c = from_ps1.build(ep, lines, ep['duration'], '16:9', 30, lambda *_: None); cp = out / '_contrat_theatre.json'; C.save(c, cp)
            sd = out / '_stills'; render.run_painter(cp, None, 'nvidia', (1920, 1080), stills=list(ts.values()), stills_dir=sd, quiet=True, fallback=True)
            for i, t in ts.items(): ims[i] = Image.open(sd / f't_{t:.2f}.png').convert('RGB')
        else:
            from hstudio.pipeline import make_engine
            eng = make_engine('pixel3d', ep, lines, np.zeros(10), ep['duration'], '16:9')
            for i, t in ts.items(): ims[i] = eng.raw_frame(t).convert('RGB').resize((1920, 1080), Image.NEAREST)
        for i, im in ims.items():
            name = f"{style}_{i + 1:02d}_{m.SHOTS[i]['name']}"
            im.save(out / f'{name}.png'); compare(im, refs[i], LABELS[i], style.upper(), out / f'comparaison_{name}.jpg')
        print(f'[theatre] {style} : {len(ims)} images en {time.time() - t0:.0f} s -> {out}', flush=True)


if __name__ == '__main__':
    main()
