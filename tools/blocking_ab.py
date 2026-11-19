"""python tools/blocking_ab.py
Before / after on the same instants of the story: source | first remake (counter-example) | continuity film, frames really extracted from the three MP4 files.
Writes projects/pompe_continuite_20261029/film/avant_apres_*.png (3 sheets of 6 moments). Moments are chosen where the owner saw the errors: the clerk by the door,
the torch, the lot lights, the knocks, the plan, the car, the door that creaks, the choice."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw
from hstudio.remake import sheets

BASE = ROOT / 'projects' / 'remakes_voxelgpu_20261029'; NEW = ROOT / 'projects' / 'pompe_continuite_20261029' / 'film'
SRC, OLD, CUR = BASE / 'source' / 'pompe' / 'LA_DERNIERE_POMPE_partie1_sans_miniature.mp4', BASE / 'pompe' / 'master.mp4', NEW / 'master.mp4'
MOM = [(2.8, "la caisse"), (14.6, "il verrouille la porte"), (23.6, "main sur la vitre"), (30.3, "la lampe torche"), (32.0, "il l'éclaire"), (35.0, "il recule encore"),
       (43.0, "le parking s'éteint"), (50.4, "les trois coups"), (55.0, "le plan électrique"), (59.0, "la réserve"), (62.8, "la voiture"), (65.5, "trois mètres d'obscurité"),
       (68.8, "la porte grince"), (71.5, "la main noire"), (78.0, "choix A"), (84.0, "choix B"), (88.0, "dernière lumière"), (91.5, "A ou B ?")]
W, H = 220, 391
frames = {}
for name, p in (('source', SRC), ('premier remake', OLD), ('continuité', CUR)): frames[name] = sheets.grab(p, [int(t * 30) for t, _ in MOM], W, H)
for part in range(3):
    sel = MOM[part * 6:(part + 1) * 6]; S = Image.new('RGB', (len(sel) * (W + 4), 3 * (H + 20) + 4), (16, 16, 16)); d = ImageDraw.Draw(S)
    for k, (t, lab) in enumerate(sel):
        for r, name in enumerate(('source', 'premier remake', 'continuité')):
            x, y = k * (W + 4), r * (H + 20) + 2; d.text((x + 3, y + 3), f'{t:.1f}s {lab} - {name}' if r == 0 else name, fill=(255, 255, 0)); S.paste(frames[name][int(t * 30)], (x, y + 18))
    S.save(NEW / f'avant_apres_{part}.png'); print(NEW / f'avant_apres_{part}.png')
