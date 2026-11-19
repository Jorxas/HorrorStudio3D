"""python tools/diversite_sheet.py [--out dossier] [--only rue_jour,hall] [--styles ps1,voxel] [--size 640x360] [--bench]

Planche AVANT / APRÈS de la diversité des décors (chantier « bâtiments et intérieurs variés », 31/10/2026) : la MÊME scène (même lieu écrit, même personnage, même caméra
d'intention) en style PS1 (PIXEL 3D) et en style VOXEL (peintre GPU), sans le profil (avant : les lieux livrés) puis avec `"profile": "production"` (après : la clé `diversite`
pose les quartiers à identité et les intérieurs à palette). Une planche par style, ligne du haut = avant, ligne du bas = après ; `--bench` mesure le coût PS1 (ms/image).
Les scènes marquées « explicite » écrivent un lieu NOUVEAU (quartier, hall, appartement...) : c'est ce que le profil ne devine pas.
Les rendus GPU doivent se faire sous le verrou de rendu du studio (un seul rendu lourd à la fois)."""
import argparse, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw

# nom -> (libellé, lieu AVANT, lieu APRÈS, position du personnage (repère PIXEL 3D), cap)
SCENES = {
    'rue_jour':   ('Rue de jour',        {'type': 'city_street', 'sky': 'day'},   {'type': 'city_street', 'sky': 'day'},   [0, 9], '-z', dict(cam=[0, -3], div=dict(style='decors', seed=0))),
    'rue_nuit':   ('Rue de nuit',        {'type': 'city_street', 'sky': 'night'}, {'type': 'city_street', 'sky': 'night'}, [0, 9], '-z', dict(cam=[0, -3], div=dict(style='decors', seed=7))),
    'pastel':     ('Quartier pastel',    {'type': 'city_street', 'sky': 'day'},   {'type': 'quartier', 'identite': 'crepi_pastel', 'sky': 'day'}, [0, 9], '-z', dict(cam=[0, -3])),
    'hall':       ("Hall d'immeuble",    {'type': 'apartment', 'lobby': True},    {'type': 'hall_immeuble', 'ambiance': 'menthe'},   [0, 4.2], '-z', dict(at_avant=[0, 5.0], cam_avant=[0, .9])),
    'appart_a':   ('Appartement A',      {'type': 'apartment'},                    {'type': 'appartement', 'disposition': 'studio', 'ambiance': 'moutarde'}, [0, 3.4], '-z', dict(at_avant=[0, 12.6], cam_avant=[0, 9.5])),
    'appart_b':   ('Appartement B',      {'type': 'apartment'},                    {'type': 'appartement', 'disposition': 'familial', 'ambiance': 'bleu_canard'}, [0, 3.6], '-z', dict(at_avant=[0, 12.6], cam_avant=[0, 9.5])),
    'cafe':       ('Café',               {'type': 'cafe'},                         {'type': 'cafe_quartier', 'ambiance': 'bordeaux'},  [0, 3.6], '-z', dict()),
    'salon':      ('Salon',              {'type': 'living_room'},                  {'type': 'living_room'},                             [0, 3.0], '-z', dict(div=dict(style='decors', seed=3))),
    'boutique':   ('Boutique',           {'type': 'shop'},                         {'type': 'boutique', 'theme': 'epicerie', 'ambiance': 'sauge'},        [0, 3.6], '-z', dict()),
    'escalier':   ("Cage d'escalier",    {'type': 'stairwell'},                    {'type': 'escalier_immeuble', 'ambiance': 'terracotta'}, [0, 4.5], '-z', dict()),
}
for _k, _lab in (('brique_rouge', 'Brique rouge'), ('crepi_pastel', 'Crépi pastel'), ('bois', 'Maisons de bois'), ('verre_acier', 'Verre et acier'), ('art_deco', 'Art déco'), ('industriel', 'Industriel'),
                 ('mediterraneen', 'Méditerranéen'), ('neon_nuit', 'Nuit au néon'), ('cite_couleurs', 'Cité colorée')):
    SCENES['id_' + _k] = (_lab, {'type': 'city_street'}, {'type': 'quartier', 'identite': _k}, [0, 9], '-z', dict(cam=[0, -3]))
for _k, _lab in (('terracotta', 'Terracotta'), ('bleu_canard', 'Bleu canard'), ('moutarde', 'Moutarde'), ('menthe', 'Menthe'), ('rose_poudre', 'Rose poudré'), ('sauge', 'Sauge'),
                 ('bordeaux', 'Bordeaux'), ('nordique', 'Nordique'), ('loft_brique', 'Loft brique'), ('noir_neon', 'Noir néon')):
    SCENES['pal_' + _k] = (_lab, {'type': 'living_room'}, {'type': 'salon_maison', 'ambiance': _k}, [0, 3.0], '-z', dict())
DEFAULT = ('rue_jour', 'rue_nuit', 'pastel', 'hall', 'appart_a', 'cafe')


def episode(spec, at, facing, profile, shot='wide', cam=None, div=None):
    ep = {'engine_version': 2, 'default_set': 's', 'sets': {'s': dict(spec)}, 'cast': {'lea': {'preset': 'lina'}}, 'title': 'diversite des decors',
          'shots': [{'lines': [0, 0], 'set': 's', 'dur': 1.5, 'actors': [{'id': 'lea', 'at': list(at), 'facing': facing, 'face': 'neutral'}], 'actions': [], 'camera': dict({'shot': shot, 'on': ['lea']}, **({'from': list(cam)} if cam else {}))}]}
    if profile: ep['profile'] = profile
    if profile and div: ep['diversite'] = dict(div)
    return ep


def render_ps1(ep, size, t=.5):
    from hstudio.pipeline import make_engine
    one = json.loads(json.dumps(ep)); lines = [{'who': 'lea', 'text': 'x', 'start': 0., 'end': 1.5}]
    eng = make_engine('pixel3d', one, lines, {}, 2.0, '16:9'); eng.render_lowres(t)
    t0 = time.perf_counter(); im = eng.render_lowres(t)[0]; dt = time.perf_counter() - t0
    return Image.fromarray(im).convert('RGB').resize(size, Image.NEAREST), dt


def render_voxel(eps, size, tmp):
    """une liste d'épisodes d'UN plan -> une image VOXEL chacun (un seul contrat, un seul passage du peintre)"""
    from hstudio.voxelgpu import director, contract as C, render
    sys.path.insert(0, str(ROOT / 'tools')); from dual_style_sheet import to_voxel_coords
    shots = []; sets = {}; casts = {}; profile = None
    out = []
    for k, ep in enumerate(eps):                                      # un contrat par épisode : l'état `diversite` est lu au moment de la construction
        v = to_voxel_coords(json.loads(json.dumps(ep))); v['casts'] = v.pop('cast')
        from hstudio.voxelgpu.b_sets import K
        for sh in v['shots']:                                                   # l'ancre `from` de la caméra est au repère de PIXEL 3D : même demi-tour que les acteurs
            cm = sh.get('camera') or {}
            if isinstance(cm.get('from'), list) and len(cm['from']) == 2: cm['from'] = [round(-K * cm['from'][0], 3), round(-K * cm['from'][1], 3)]
        v.setdefault('genre', 'neutral'); v['duration'] = 1.5
        c = director.build(v, '16:9', 24); cp = tmp / f'c_{k}.json'; C.save(c, cp); out.append((cp, c))
    ims = []
    for k, (cp, c) in enumerate(out):
        sd = tmp / f's_{k}'; t = round(c['stages'][0]['t0'] + .5, 2)
        render.run_painter(cp, None, 'nvidia', size, stills=[t], stills_dir=sd, quiet=True, fallback=True)
        ims.append(Image.open(sd / f't_{t:.2f}.png').convert('RGB').resize(size))
    return ims


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default=str(ROOT / 'projects' / 'diversite')); ap.add_argument('--only', default=','.join(DEFAULT))
    ap.add_argument('--styles', default='ps1,voxel'); ap.add_argument('--size', default='640x360'); ap.add_argument('--bench', action='store_true'); ap.add_argument('--name', default='planche'); ap.add_argument('--solo', action='store_true', help='une seule rangée (apres), en grille de 3 colonnes'); a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True); tw, th = (int(v) for v in a.size.split('x')); names = a.only.split(','); rep = {}
    for style in a.styles.split(','):
        rows = {'avant': [], 'apres': []}
        for key in (('apres',) if a.solo else ('avant', 'apres')):
            eps = []
            for n in names:
                lab, sb, sa, at, fc, ex = SCENES[n]; eps.append(episode(sb if key == 'avant' else sa, ex.get('at_avant', at) if key == 'avant' else at, fc, None if key == 'avant' else 'production', cam=(ex.get('cam_avant') if key == 'avant' and ex.get('cam_avant') else ex.get('cam')), div=ex.get('div')))
            if style == 'ps1':
                for n, ep in zip(names, eps):
                    im, dt = render_ps1(ep, (tw, th)); rows[key].append(im); rep.setdefault(n, {})[f'ps1_{key}_ms'] = round(dt * 1000)
                    print(f'PS1 {key:5s} {n:10s} {dt * 1000:6.0f} ms', flush=True)
            else:
                tmp = out / f'tmp_{key}'; tmp.mkdir(exist_ok=True); rows[key] = render_voxel(eps, (tw, th), tmp); print(f'VOXEL {key}: {len(names)} images', flush=True)
        if a.solo:
            cols = 3; rws = (len(names) + cols - 1) // cols; sheet = Image.new('RGB', (tw * cols, th * rws), (20, 20, 24)); d = ImageDraw.Draw(sheet)
            for i, n in enumerate(names):
                x, y = (i % cols) * tw, (i // cols) * th; sheet.paste(rows['apres'][i], (x, y)); d.rectangle([x, y, x + 9 * len(SCENES[n][0]) + 8, y + 15], fill=(0, 0, 0)); d.text((x + 4, y + 2), SCENES[n][0], fill=(255, 255, 255))
        else:
            sheet = Image.new('RGB', (tw * len(names), th * 2 + 18), (20, 20, 24)); d = ImageDraw.Draw(sheet)
            for i, n in enumerate(names):
                sheet.paste(rows['avant'][i], (i * tw, 0)); sheet.paste(rows['apres'][i], (i * tw, th + 18)); d.text((i * tw + 6, th + 3), SCENES[n][0] + '  (avant en haut, après en bas)', fill=(255, 255, 255))
        p = out / f'{a.name}_{style}.png'; sheet.save(p); print(p)
    (out / 'mesures.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__': main()
