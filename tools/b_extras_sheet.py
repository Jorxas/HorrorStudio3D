"""python tools/b_extras_sheet.py [--render] [--count 10] [--seeds 1,2,3] [--out dossier]

Figurants animés : mesures avant/après et, avec --render, le clip de test (rue de nuit, deux principaux qui parlent, figurants qui vivent la rue, un monstre apparaît au fond et tout le monde réagit)
et sa planche de 16 images. « Avant » = `extras.spacing: false` et `keep_clear` quasi nul (des figurants posés sans aucune garde) ; « après » = réglages par défaut."""
import argparse, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'tools'))
import b_extras_scene as S
from hstudio.voxelgpu import director, contract as C, render, b_extras as EX


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--render', action='store_true'); ap.add_argument('--count', type=int, default=10); ap.add_argument('--seeds', default='1,2,3'); ap.add_argument('--out', default=str(ROOT / 'projects' / 'b_extras'))
    a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True); rows = []
    for seed in [int(x) for x in a.seeds.split(',')]:
        for label, kw in (('avant', dict(keep=.01, spacing=False)), ('après', dict(keep=3.0, spacing=True))):
            ep = S.episode(count=a.count, seed=seed, keep=kw['keep'])
            ep['extras']['spacing'] = kw['spacing']; ep.pop('spacing', None)
            if kw['spacing']: ep['spacing'] = True
            t = time.time(); c = director.build(ep, '9:16', 24); dt = time.time() - t; r = EX.audit(c, keep=3.0); r.update(seed=seed, version=label, build_s=round(dt, 1)); rows.append(r)
            print(f"seed {seed} {label:6s} figurants {r['extras']:2d} : chevauchements {r['overlap_frames']:5d} img | min aux principaux {r['min_to_leads']} m | sous 2,7 m {r['below_keep_frames']:5d} img | dans un décor {r['penetration_frames']:4d} img | en mouvement {r['moving']}/{r['extras']} | entrées {r['entered']} sorties {r['exited']} | contrat {dt:.1f} s")
    (out / 'mesures.json').write_text(json.dumps(rows, indent=1), encoding='utf-8')
    if a.render:
        c = director.build(S.episode(count=a.count, seed=1), '9:16', 24); C.save(c, out / 'c.json'); t = time.time()
        render.run_painter(out / 'c.json', out / 'clip_video.mp4', 'nvidia', (540, 960), attest=out / 'att.json', crf=22, quiet=True, fallback=True, transport='b64'); print(f'clip rendu en {time.time() - t:.0f} s -> {out / "clip_video.mp4"}')
        import subprocess
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(out / 'clip_video.mp4'), '-vf', "select='not(mod(n,24))',scale=240:427,tile=8x2", '-frames:v', '1', str(out / 'planche.png')], check=True); print('planche :', out / 'planche.png')


if __name__ == '__main__': main()
