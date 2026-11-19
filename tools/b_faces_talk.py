"""python tools/b_faces_talk.py [--out dossier] [--legacy] [--no-video]

Visages qui PARLENT avec une expression (colère, pleurs, dégoût, joie, fureur, douleur) : un plan de 2,2 s par cas, bouche animée par la parole (`speech`) PAR-DESSUS l'expression,
pour Noé, Lina et un personnage refondu (`b_look`). Écrit une planche d'images (4 instants par plan) et une courte vidéo témoin 9:16 sans son. --legacy = les visages d'avant."""
import argparse, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw
from hstudio.voxelgpu import director, contract as C, render

CASTS = {'noe': {'preset': 'noe'}, 'lina': {'preset': 'lina'}, 'nun': {'b_look': 'mmmm/chr_nun'}}
PLAN = [('noe', 'angry', True), ('lina', 'cry', True), ('nun', 'disgusted', False), ('noe', 'smile', True), ('lina', 'furious', True), ('noe', 'pain', False), ('lina', 'sad', True), ('nun', 'contempt', True)]


def episode():
    shots = []
    for who, face, talk in PLAN:
        s = dict(stage='plateau', dur=2.2, camera=dict(shot='extreme_close', on=[who]), env=dict(floor=0x7a7268, bg=0x6a7a98, ambient=2.0, key=2.0, fog=0.002),
                 actors=[dict(id=who, at=[0, 0], facing='+z', face=face)], actions=[], reset=True)
        if talk: s['speech'] = [[0.3, 2.0, who]]
        shots.append(s)
    return dict(title='visages qui parlent', genre='neutral', casts=CASTS, shots=shots, duration=round(2.2 * len(shots), 2))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default=str(ROOT / 'projects' / 'b_faces_talk')); ap.add_argument('--legacy', action='store_true'); ap.add_argument('--no-video', action='store_true'); a = ap.parse_args()
    if a.legacy: os.environ['HSTUDIO_FACE_LEGACY'] = '1'
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    c = director.build(episode(), '9:16', 24); cp = out / 'contrat.json'; C.save(c, cp); sd = out / 'stills'
    times = [round(s['t0'] + dt, 2) for s in c['stages'] for dt in (.45, .85, 1.25, 1.75)]
    render.run_painter(cp, None, 'nvidia', (360, 640), stills=times, stills_dir=sd, quiet=True, fallback=True)
    tw, th = 270, 480; sh = Image.new('RGB', (tw * 4, th * len(PLAN)), (20, 20, 24)); d = ImageDraw.Draw(sh)
    for r, (who, face, talk) in enumerate(PLAN):
        for k in range(4):
            t = times[r * 4 + k]; im = Image.open(sd / f't_{t:.2f}.png').convert('RGB').resize((tw, th)); sh.paste(im, (k * tw, r * th))
        d.rectangle([0, r * th, 190, r * th + 14], fill=(0, 0, 0)); d.text((4, r * th + 2), f"{who} {face} {'(parle)' if talk else '(muet)'}", fill=(255, 255, 255))
    sh.save(out / 'planche.jpg', quality=85); print('planche', out / 'planche.jpg', flush=True)
    if not a.no_video:
        t0 = time.time(); render.run_painter(cp, out / 'video.mp4', 'nvidia', (540, 960), crf=20, quiet=True, fallback=True); print(f'video {out / "video.mp4"} ({time.time() - t0:.0f} s)')


if __name__ == '__main__': main()
