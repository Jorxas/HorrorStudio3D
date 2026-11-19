"""La preuve du parcours en un clic : deux vrais MP4 fabriques dans projects/, un par moteur, puis mesures.

Rien de nouveau n'est teste ici : on lance le parcours comme le proprietaire le lancerait, puis on mesure le
fichier obtenu (ffprobe, decodage ffmpeg complet, taille, duree) et on relit le score du controle qualite.

    python tools/oneclick_proof.py                 # 9:16 PIXEL 3D + 16:9 CONSOLE 2D, qualite standard
    python tools/oneclick_proof.py --quality max
"""
import os, sys, json, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from hstudio import oneclick as OC, pipeline as P

QUALITY = 'standard'
for i, a in enumerate(sys.argv):
    if a == '--quality' and i + 1 < len(sys.argv): QUALITY = sys.argv[i + 1]

CASES = [
    ('preuve_un_clic_pixel3d', 'pixel3d', 'horror',  2, '9:16', 3),
    ('preuve_un_clic_console', 'console', 'mystery', 3, '16:9', 5),
]


class Job:
    def write(self, m): print('   ' + str(m))
    def prog(self, p, d=''): print('\r   %5.1f%% %s' % (float(p) * 100, d), end='', flush=True)


def probe(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', path],
                       capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 else None


def decodes(path):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'null', '-'], capture_output=True, text=True)
    return r.returncode == 0 and not r.stderr.strip(), (r.stderr or '').strip()[:300]


if __name__ == '__main__':
    # Obligatoire : sous Windows, `step_render` lance ses processus de rendu en « spawn » et ceux-ci
    # reimportent ce module. Sans cette garde, chaque worker refabriquerait les projets de la preuve.
    rows = []
    for slug, engine, genre, nch, aspect, seed in CASES:
        print('\n=== %s (%s, %s) ===' % (slug, engine, aspect))
        pr = P.Project(slug)
        if not os.path.isdir(pr.dir):
            data = {'brief': dict(genre=genre, duration_s=30, voice_mode='voice', engine=engine, n_choices=nch,
                                  seed=seed, series='Preuve un clic', part_label='PARTIE 1',
                                  premise='une porte qui ne devrait pas etre la'),
                    'name': slug, 'voice_mode': 'draft'}
            pr, outline = OC.project_from_brief(data, log=lambda m: print('   ' + str(m)))
        res = OC.run(pr, opts={'aspects': [aspect], 'quality': QUALITY}, job=Job())
        mp4 = pr.p('renders', res['renders'][aspect][0])
        info = probe(mp4) or {}
        v = next((s for s in info.get('streams', []) if s.get('codec_type') == 'video'), {})
        au = next((s for s in info.get('streams', []) if s.get('codec_type') == 'audio'), {})
        ok, err = decodes(mp4)
        qc = pr.read_json(OC._qc_file(aspect)) or {}
        rows.append(dict(slug=slug, engine=engine, aspect=aspect, path=os.path.abspath(mp4),
                         bytes=os.path.getsize(mp4), seconds=float(info.get('format', {}).get('duration', 0)),
                         video='%s %sx%s' % (v.get('codec_name'), v.get('width'), v.get('height')),
                         fps=v.get('r_frame_rate'), audio='%s %s ch %s Hz' % (au.get('codec_name'), au.get('channels'), au.get('sample_rate')),
                         decode=('OK' if ok else 'ERREUR: ' + err), qc=qc.get('score'),
                         optin=sorted({k for k in ('lighting', 'eyeline', 'footing', 'faces', 'sfx_library', 'camera_face_track', 'face_track')
                                       if ('"%s"' % k) in json.dumps(pr.read_json('episode.json') or {})})))

    print('\n\n================ PREUVE ================')
    for r in rows:
        print('\n%s  (%s, %s)' % (r['slug'], r['engine'], r['aspect']))
        print('  chemin Windows : ' + r['path'])
        print('  taille         : %.1f Mo (%d octets)' % (r['bytes'] / 1e6, r['bytes']))
        print('  duree          : %.2f s' % r['seconds'])
        print('  video          : %s, %s' % (r['video'], r['fps']))
        print('  audio          : ' + r['audio'])
        print('  decodage       : ' + r['decode'])
        print('  controle qualite : %s/100' % r['qc'])
        print('  options opt-in dans episode.json : ' + (', '.join(r['optin']) or 'aucune'))
    print()
