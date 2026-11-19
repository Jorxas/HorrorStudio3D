"""Petit MP4 de la meme scene, pour ecouter la mise en scene sonore sur l'image.

    python tools/soundscape_video.py [--shots 21] [--workers 6] [--fps 30] [--crf 31] [--height 540]
    python tools/soundscape_video.py --from-master        # re-derive sans refaire le rendu

La video est rendue UNE SEULE FOIS et encodee UNE SEULE FOIS (avec le mix B). La version A reutilise
le meme flux video en copie (-c:v copy) : aucune image n'est recalculee ni reencodee pour le second
fichier. Les deux MP4 ne different donc que par leur piste audio, ce qui est exactement la preuve
voulue. Les mixes viennent de tools/soundscape_ab.py (a lancer avant).

Le rendu reutilise le pool du studio (hstudio.pipeline._init_worker / _render_one) : aucun chemin de
rendu n'est reecrit ici. `--workers` est volontairement bas par defaut : d'autres worktrees calculent
en parallele sur la meme machine.
"""
import hashlib, json, os, re, subprocess, sys, time
import multiprocessing as mp
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

from hstudio.pipeline import _init_worker, _render_one
import sfx_episode_ab as AB

OUT = os.path.join(ROOT, 'docs', 'audio_cinematique')


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''): h.update(c)
    return h.hexdigest()


def probe(p):
    r = subprocess.run(f'ffprobe -v error -show_entries stream=codec_name,codec_type,width,height,duration'
                       f' -of json "{p}"', shell=True, capture_output=True, text=True)
    return json.loads(r.stdout or '{}')


def decode_check(p):
    """decodage complet : la seule preuve qu'on peut regarder le fichier en entier"""
    r = subprocess.run(f'ffmpeg -v error -xerror -i "{p}" -f null -', shell=True, capture_output=True, text=True)
    return (r.returncode == 0), (r.stderr or '').strip()[:300]


def main():
    av = sys.argv[1:]
    def opt(k, d, cast=int): return cast(av[av.index(k) + 1]) if k in av else d
    n_shots, workers, fps, crf = opt('--shots', 21), opt('--workers', 6), opt('--fps', 30), opt('--crf', 31)
    aspect = '16:9'
    print(f'ffmpeg : {AB.ensure_ffmpeg()}')

    mix_b = os.path.join(OUT, 'B_soundscape.wav'); mix_a = os.path.join(OUT, 'A_actuel.wav')
    for p in (mix_a, mix_b):
        if not os.path.exists(p):
            raise SystemExit(f'mix absent : {p}\nLancer d abord : python tools/soundscape_ab.py --shots {n_shots}')

    root = os.path.join(ROOT, 'examples', 'etage_zero_partie4')
    ep, lines, spans, dur = AB.load_episode(root, n_shots)
    script = [l.rstrip('\n') for l in open(os.path.join(root, 'script.txt'), encoding='utf-8')]
    for i, l in enumerate(lines):                      # les sous-titres ont besoin du texte des repliques
        l['text'] = re.sub(r'\[[^\]]*\]', '', script[i]).strip()

    W, H = (1920, 1080) if aspect == '16:9' else (1080, 1920)
    N = int(dur * fps)
    master = os.path.join(OUT, 'scene_master_16x9.mp4')      # lourd, jamais versionne
    out_b = os.path.join(OUT, 'scene_B_soundscape_16x9.mp4')
    out_a = os.path.join(OUT, 'scene_A_actuel_16x9.mp4')
    height = opt('--height', 540)    # la video n'est la que pour ecouter en regardant : 540p suffit

    secs = None                        # None quand on n'a pas rendu : on ne publie pas un zero faux
    if '--from-master' in av and os.path.exists(master):
        print(f'rendu saute : master existant reutilise ({os.path.getsize(master) / 1e6:.1f} Mo)')
    else:
        print(f'rendu : {N} images {W}x{H} a {fps} fps, {workers} processus, {dur:.1f} s de scene')
        cmd = ['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
               '-r', str(fps), '-i', '-', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18',
               '-pix_fmt', 'yuv420p', '-r', str(fps), '-an', master]
        t0 = time.time()
        enc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        ctx = mp.get_context('spawn')
        with ctx.Pool(workers, initializer=_init_worker,
                      initargs=('pixel3d', ep, lines, np.zeros(10), dur, aspect)) as pool:
            for k, b in enumerate(pool.imap(_render_one, range(N), chunksize=4)):
                enc.stdin.write(b)
                if k % 150 == 0: print(f'  {k}/{N} images ({time.time() - t0:.0f} s)', flush=True)
        enc.stdin.close()
        if enc.wait() != 0: raise SystemExit('encodage du master en echec')
        secs = time.time() - t0
        print(f'-> master {os.path.getsize(master) / 1e6:.1f} Mo en {secs:.0f} s (non versionne)')

    # UN SEUL encodage video a la taille de livraison, avec le mix B
    subprocess.run(f'ffmpeg -v error -y -i "{master}" -i "{mix_b}" -map 0:v:0 -map 1:a:0 '
                   f'-vf scale=-2:{height} -c:v libx264 -preset medium -crf {crf} -pix_fmt yuv420p '
                   f'-c:a aac -b:a 192k -ac 2 -shortest -movflags +faststart "{out_b}"',
                   shell=True, check=True)
    print(f'-> {out_b}  ({os.path.getsize(out_b) / 1e6:.1f} Mo)')

    # version A : le MEME flux video, copie bit a bit, seule la piste audio change
    subprocess.run(f'ffmpeg -v error -y -i "{out_b}" -i "{mix_a}" -map 0:v:0 -map 1:a:0 '
                   f'-c:v copy -c:a aac -b:a 192k -ac 2 -shortest -movflags +faststart "{out_a}"',
                   shell=True, check=True)
    print(f'-> {out_a}  (video copiee sans reencodage, {os.path.getsize(out_a) / 1e6:.1f} Mo)')

    rep = {}
    for tag, p in (('B_soundscape', out_b), ('A_actuel', out_a)):
        okd, err = decode_check(p)
        st = probe(p).get('streams', [])
        rep[tag] = dict(path=p, octets=os.path.getsize(p), sha256=sha(p), decodage_complet=okd,
                        erreur=err or None, flux=st)
        v = next((s for s in st if s.get('codec_type') == 'video'), {})
        au = next((s for s in st if s.get('codec_type') == 'audio'), {})
        print(f"  {tag}: {v.get('codec_name')} {v.get('width')}x{v.get('height')} + "
              f"{au.get('codec_name')} | decodage complet {'OK' if okd else 'ECHEC ' + err}")
    # preuve que seule la bande son change : l'empreinte du FLUX VIDEO doit etre la meme des deux cotes
    def vhash(p):
        r = subprocess.run(f'ffmpeg -v error -i "{p}" -map 0:v:0 -f md5 -', shell=True,
                           capture_output=True, text=True)
        return (r.stdout or '').strip().replace('MD5=', '')
    hb, ha = vhash(out_b), vhash(out_a)
    rep['flux_video_identique'] = dict(md5_B=hb, md5_A=ha, identique=bool(hb and hb == ha))
    print(f"  flux video identique dans les deux MP4 : "
          f"{'oui' if rep['flux_video_identique']['identique'] else 'NON'} (md5 {hb[:16]}...)")
    rep['note'] = ('Une seule passe de rendu et un seul encodage video. Le fichier A reutilise le flux '
                   'video de B en copie : les deux MP4 ne different que par la piste audio.')
    rep['rendu'] = dict(images=N, fps=fps, taille_rendue=[W, H], hauteur_livree=height, crf=crf,
                        secondes_de_calcul=round(secs, 1) if secs is not None else None,
                        master_reutilise=secs is None, workers=workers)
    with open(os.path.join(OUT, 'soundscape_video.json'), 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print(f'-> {OUT}\\soundscape_video.json')


if __name__ == '__main__':
    main()
