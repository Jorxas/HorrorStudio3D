"""Collects the proofs of the environment variation increment into docs/world_variety/preuves.json.

  python tools/variety_proofs.py

Lists every artefact with its absolute Windows path, its size, its sha256 and (for a video) its real duration and
resolution read back from the file, plus the inventory of what the increment adds. It never re-renders anything:
it only measures what is on disk, so it cannot claim a proof that was not produced.
"""
import hashlib, json, os, re, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

OUT = os.path.join(ROOT, 'docs', 'world_variety')
FFMPEG = os.environ.get('HSTUDIO_FFMPEG', 'ffmpeg')

ARTEFACTS = [
    os.path.join(OUT, 'avant_apres_decors.png'),
    os.path.join(OUT, 'avant_apres_decors_16x9.mp4'),
    os.path.join(OUT, 'demo20_decors_16x9.mp4'),
    os.path.join(OUT, 'demo20_images.png'),
    os.path.join(OUT, 'console2d_palettes.png'),
    os.path.join(OUT, 'mesures_decors.json'),
    os.path.join(ROOT, 'projects', 'demo20_decors', 'renders', 'demo20_decors_long_16x9.mp4'),
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def media(path):
    try:
        p = subprocess.run([FFMPEG, '-i', path], capture_output=True, text=True, errors='replace')
        txt = p.stderr
    except Exception as e:
        return {'ffmpeg': str(e)}
    out = {}
    m = re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)', txt)
    if m:
        out['seconds'] = round(int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)), 2)
    m = re.search(r'Video: .*?, (\d+)x(\d+)', txt)
    if m:
        out['size'] = [int(m.group(1)), int(m.group(2))]
    m = re.search(r', (\d+(?:\.\d+)?) fps', txt)
    if m:
        out['fps'] = float(m.group(1))
    return out


def main():
    from hstudio.engines.pixel3d import environment_variation as EV
    from hstudio.engines.console import scene_palettes as SP
    rows = []
    for p in ARTEFACTS:
        if not os.path.exists(p):
            rows.append({'path': p, 'present': False})
            continue
        r = {'path': os.path.abspath(p).replace('/', os.sep), 'present': True,
             'bytes': os.path.getsize(p), 'sha256': sha256(p)}
        if p.lower().endswith('.mp4'):
            r.update(media(p))
        rows.append(r)
    qc = {}
    for a in ('16x9', '9x16'):
        q = os.path.join(ROOT, 'projects', 'demo20_decors', f'qc_{a}.json')
        if os.path.exists(q):
            d = json.load(open(q, encoding='utf-8'))
            qc[a] = {'score': d.get('score'), 'issues': d.get('issues', d.get('problemes'))}
    doc = {'artefacts': rows,
           'inventaire_pixel3d': EV.inventory(),
           'inventaire_console2d': SP.inventory(),
           'qc_demo20': qc,
           'comment_rejouer': ['python tools/check_variety.py',
                               'python tools/variety_sheet.py',
                               'python tools/variety_video.py --seconds 6',
                               'python tools/console_palette_sheet.py',
                               'python -m hstudio demo demo20_decors --aspect 16:9']}
    path = os.path.join(OUT, 'preuves.json')
    json.dump(doc, open(path, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print(path)
    for r in rows:
        print(('  OK  ' if r.get('present') else '  --  ') + os.path.basename(r['path']) +
              (f"  {r['bytes'] / 1e6:.1f} Mo" if r.get('present') else '  absent'))


if __name__ == '__main__':
    main()
