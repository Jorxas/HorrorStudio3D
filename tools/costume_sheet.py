"""Planches des costumes XVIIIe, dans les DEUX styles, par la vraie chaîne (scène dirigée -> PS1 ; scène dirigée -> contrat -> peintre VOXEL).

    python tools/costume_sheet.py voxel|ps1 [--what vues,tour,marche,gros,tetes] [--only angelica,eliza] [--out dossier]

  vues    chaque personnage de face / profil / dos (une image 1920x1080 par personnage)
  tour    tour sur soi : 6 images, la jupe s'évase (évasement = fonction de la vitesse de rotation)
  marche  marche de profil : 6 images sur un cycle de pas (la jupe suit le bassin, les jambes restent dedans)
  gros    gros plan visage + buste (dentelle, jabot, boucles d'oreilles)
  tetes   têtes de face et de trois quarts, à côté des vignettes de référence (ressemblance)
Rendu GPU : un seul peintre à la fois (ne pas lancer deux planches VOXEL en parallèle).
"""
import argparse, json, math, os, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from hstudio.engines.pixel3d import costumes as COS

PI = math.pi
OUT = Path(r'C:\Users\demo\Desktop\videpgene\CLIP_SATISFIED_VOXEL\planches\costumes')
REF = Path(r'C:\Users\demo\Desktop\videpgene\CLIP_SATISFIED_VOXEL\reference')
ALL = COS.PRINCIPAUX + COS.ENSEMBLE_DAMES + COS.ENSEMBLE_HOMMES
SET = {'atelier': {'type': 'room', 'height': 4.2, 'clean': True, 'ambient': [.40, .38, .36], 'fog': 0.0,
                   'rooms': [{'id': 'a', 'origin': [0, -10], 'size': [18, 16], 'walls': 'plaster', 'wall_color': [150, 140, 128], 'floor': 'wood', 'light': 'warm', 'light_power': 1.3, 'height': 4.2}]}}
# où regarder dans les vignettes de référence (fichier, boîte de recadrage x0, y0, x1, y1 sur 960x512)
REF_HEADS = {'angelica': ('p024.jpg', (300, 0, 640, 300)), 'eliza': ('p000.jpg', (560, 0, 960, 380)), 'hamilton': ('p030.jpg', (440, 0, 800, 330)),
             'peggy': ('p006.jpg', (240, 110, 500, 370)), 'laurens': ('p002.jpg', (300, 70, 500, 270)), 'homme_chauve_rouge': ('p002.jpg', (580, 120, 760, 300)),
             'eliza_souvenir': ('p046.jpg', (230, 0, 560, 330))}


def K(t, p, yaw, **kw): return dict({'t': round(t, 3), 'p': [round(v, 3) for v in p], 'yaw': round(yaw, 4)}, **kw)
def CAM(t, pos, look, fov): return {'t': t, 'pos': [round(v, 3) for v in pos], 'look': look if isinstance(look, dict) else [round(v, 3) for v in look], 'fov': fov}


class Ep:
    def __init__(self): self.cast = {}; self.shots = []; self.lines = []; self.t = 0.; self.marks = []

    def shot(self, dur, tracks, cam, stills, label, set_name='atelier', **extra):
        self.shots.append(dict({'lines': [len(self.shots)] * 2, 'pre': 0., 'set': set_name, 'ui': {'hud': False, 'subs': 'off'}, 'tracks': tracks, 'camera': {'rig': 'path', 'keys': cam}}, **extra))
        self.lines.append({'start': round(self.t, 3), 'end': round(self.t + dur, 3), 'text': '', 'speaker': 'n'})
        for (dt, name) in stills: self.marks.append((round(self.t + dt, 3), name, label))
        self.t += dur

    def episode(self):
        return {'style': 'pixel3d', 'voxel_mirror': True, 'genre': 'slice_of_life', 'music': 'none', 'duration': round(self.t, 3), 'cast': self.cast, 'default_set': 'atelier', 'sets': dict(SET, scene={'type': 'theatre_bal'}),
                'hud': {'title': [], 'part': '', 'hearts': []}, 'shots': self.shots}


def plan_vues(ids):
    E = Ep()
    for cid in ids:
        tr = {}
        for k, (x, yaw) in enumerate(((-2.1, PI), (0., PI / 2), (2.1, 0.))):
            a = f'{cid}__{k}'; E.cast[a] = {'costume': cid}; tr[a] = [K(0, [x, 0, 0], yaw, face='happy' if k == 0 else 'neutral')]
        E.shot(1.0, tr, [CAM(0, [0, 1.2, -6.6], [0, .98, 0], 40)], [(.5, f'vues_{cid}')], f'{cid} — face / profil / dos')
    return E


def plan_tour():
    E = Ep(); tr = {}
    steps = [0, .15, .55, 1.1, 1.6, 1.65, 1.65, 1.65, 1.65, 1.6, 1.3, .8, .35, .1]
    for a, x, cid in (('t_eliza', -1.05, 'eliza'), ('t_tartan', 1.05, 'dame_tartan')):
        E.cast[a] = {'costume': cid}; y = PI; ks = []
        for i, s in enumerate(steps): y += s; ks.append(K(i * .25, [x, 0, 0], y, face='happy'))
        tr[a] = ks
    times = [.1, .9, 1.4, 1.9, 2.4, 3.1]
    E.shot(3.5, tr, [CAM(0, [0, 1.35, -5.6], [0, .85, 0], 44)], [(t, f'tour_{i + 1}') for i, t in enumerate(times)], 'tour sur soi')
    return E


def plan_marche():
    """une marche de profil, caméra qui accompagne : six images sur un cycle de pas (robe), puis six (redingote)"""
    from hstudio.voxelgpu.director import K_WALK
    E = Ep(); v = 1.2; dur = 4.5; x0 = -v * dur / 2
    cyc = max(2 * PI / K_WALK / 1.1, 1.25) / v                 # un cycle de pas (le plus long des deux styles) en secondes
    for a, cid, tag in (('m_angelica', 'angelica', 'marche'), ('m_hamilton', 'hamilton', 'marche_redingote')):
        E.cast[a] = {'costume': cid}
        tr = {a: [K(0, [x0, 0, 0], PI / 2, face='happy'), K(dur, [-x0, 0, 0], PI / 2, face='happy')]}
        times = [1.6 + i * cyc / 6 for i in range(6)]
        cam = [CAM(0, [x0 + .35, 1.2, -5.0], [x0 + .2, .98, 0], 44), CAM(dur, [-x0 + .35, 1.2, -5.0], [-x0 + .2, .98, 0], 44)]
        E.shot(dur, tr, cam, [(t, f'{tag}_{i + 1}') for i, t in enumerate(times)], tag)
    return E


def plan_gros(ids):
    E = Ep()
    for cid in ids:
        a = f'g_{cid}'; E.cast[a] = {'costume': cid}
        E.shot(1.0, {a: [K(0, [0, 0, 0], PI, face='happy')]}, [CAM(0, [0, 1.62, -2.6], [0, 1.52, 0], 34)], [(.5, f'gros_{cid}')], f'{cid} — gros plan')
    return E


def plan_tetes(ids):
    E = Ep()
    for cid in ids:
        a = f'h_{cid}'; E.cast[a] = {'costume': cid}
        E.shot(1.0, {a: [K(0, [0, 0, 0], PI, face='happy')]}, [CAM(0, [0, 1.72, -1.9], [0, 1.66, 0], 30)], [(.5, f'tete_face_{cid}')], f'{cid} — face')
        E.shot(1.0, {a: [K(0, [0, 0, 0], PI - .75, face='happy')]}, [CAM(0, [0, 1.72, -1.9], [0, 1.66, 0], 30)], [(.5, f'tete_34_{cid}')], f'{cid} — trois quarts')
    return E


def plan_tetes2(ids):
    """itération 2 (têtes peintes) : face, trois quarts, bouche ouverte (chant), yeux fermés"""
    E = Ep()
    for cid in ids:
        a = f'h2_{cid}'; E.cast[a] = {'costume': cid}
        for tag, yaw, face in (('face', PI, 'neutral'), ('34', PI - .75, 'neutral'), ('bouche', PI, 'shout'), ('yeux', PI, 'closed')):
            E.shot(1.0, {a: [K(0, [0, 0, 0], yaw, face=face, noblink=True)]}, [CAM(0, [0, 1.70, -2.3], [0, 1.64, 0], 30)], [(.5, f'tete2_{tag}_{cid}')], f'{cid} — {tag}')
    return E


def plan_theatre(cid='angelica'):
    """face / profil / dos sur la scène du théâtre, sous deux lavis : bleu nuit et ambre"""
    E = Ep()
    for wash in ('bleu_nuit', 'ambre'):
        tr = {}
        for k, (x, yaw) in enumerate(((-2.1, PI), (0., PI / 2), (2.1, 0.))):
            a = f'th_{cid}_{k}'; E.cast[a] = {'costume': cid}; tr[a] = [K(0, [x, 0, 4.0], yaw, face='happy' if k == 0 else 'neutral')]
        E.shot(1.0, tr, [CAM(0, [0, 1.45, -3.6], [0, 1.05, 4.0], 40)], [(.5, f'theatre_{wash}_{cid}')], f'{cid} — {wash}', set_name='scene', stage_light=wash)
    return E


GESTES = [('toast_gauche', dict(gesture='arm_up', hold='flute', side='left'), 'toast bras gauche (side: left)'), ('bras_ecartes', dict(gesture='arms_wide'), 'bras écartés (arms_wide)'),
          ('bras_en_v', dict(gesture='arms_wide_up'), 'bras en V (arms_wide_up)'), ('a_genoux', dict(kneel=1.0), 'à genoux (kneel)'), ('assis_par_terre', dict(sit_floor=1.0), 'assis par terre (sit_floor)')]
# (une case « siège » se demande ainsi : ('assise_siege', dict(sit=1.0, _yaw=PI - .85), 'siège (sit), 3/4') ; la robe VOXEL y reste raide, voir docs/FORMAT_EPISODE.md)


def plan_gestes():
    """robe (Angelica) et redingote (Hamilton) côte à côte, face caméra (ou de trois quarts), pour chaque nouvelle clé de piste ; la pose arrive en 0,6 s"""
    E = Ep()
    for tag, keys, lab in GESTES:
        tr = {}
        for a, x, cid in ((f'gs_{tag}_a', -1.15, 'angelica'), (f'gs_{tag}_h', 1.15, 'hamilton')):
            E.cast[a] = {'costume': cid}; k0 = dict(keys); yaw = k0.pop('_yaw', PI); num = {k: v for k, v in k0.items() if k in ('kneel', 'sit_floor', 'sit')}
            first = dict({k: v for k, v in k0.items() if k not in num}, face='happy', **{k: 0.0 for k in num})
            tr[a] = [K(0, [x, 0, 0], yaw, **first), K(.6, [x, 0, 0], yaw, **dict(first, **num))]
        E.shot(1.4, tr, [CAM(0, [0, 1.25, -5.4], [0, .95, 0], 40)], [(1.0, f'geste_{tag}')], lab)
    return E


def _font(n):
    for f in ('arial.ttf', 'DejaVuSans.ttf'):
        try: return ImageFont.truetype(f, n)
        except OSError: pass
    return ImageFont.load_default()


def label(im, text):
    d = ImageDraw.Draw(im); f = _font(30); w = d.textlength(text, font=f)
    d.rectangle([0, 0, w + 24, 46], fill=(16, 16, 20)); d.text((12, 7), text, fill=(240, 236, 226), font=f); return im


def render_ps1(E, outdir, style_tag):
    from hstudio.pipeline import make_engine
    ep = E.episode(); e = make_engine('pixel3d', ep, E.lines, np.zeros(int(E.t * 30) + 60), E.t, '16:9'); res = {}
    for t, name, lab in E.marks:
        im = e.frame(t).convert('RGB').resize((1920, 1080), Image.NEAREST); res[name] = (im, lab)
    return res


def render_voxel(E, outdir, style_tag):
    from hstudio.voxelgpu import from_ps1, contract as C, render
    ep = E.episode(); c = from_ps1.build(ep, E.lines, E.t, '16:9', 24, lambda *_: None)
    for st in c['stages']: st['dof'] = 0.          # planche : tout net (le film garde la profondeur de champ de ses plans)
    td = Path(tempfile.mkdtemp(prefix='costumes_')); cp = td / 'contract.json'; C.save(c, cp)
    times = [t for t, _, _ in E.marks]
    render.run_painter(cp, None, 'nvidia', (1920, 1080), stills=times, stills_dir=td / 'stills', quiet=True, fallback=True)
    res = {}
    for t, name, lab in E.marks: res[name] = (Image.open(td / 'stills' / f't_{t:.2f}.png').convert('RGB'), lab)
    return res


def grid(frames, title):
    W, H = 1920, 1080; cw, chh = W // 3, (H - 50) // 2; g = Image.new('RGB', (W, H), (14, 14, 18)); d = ImageDraw.Draw(g)
    d.text((14, 8), title, fill=(240, 236, 226), font=_font(30))
    for i, (im, lab) in enumerate(frames):
        th = im.copy(); th.thumbnail((cw - 6, chh - 6)); x = (i % 3) * cw + (cw - th.width) // 2; y = 50 + (i // 3) * chh + (chh - th.height) // 2
        g.paste(th, (x, y)); d.text((x + 8, y + 6), lab, fill=(255, 240, 160), font=_font(22))
    return g


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('style', choices=('voxel', 'ps1')); ap.add_argument('--what', default='vues,tour,marche,gros,tetes')
    ap.add_argument('--only', default=''); ap.add_argument('--out', default=str(OUT)); ap.add_argument('--batch', type=int, default=6)
    a = ap.parse_args(); out = Path(a.out) / a.style; out.mkdir(parents=True, exist_ok=True)
    ids = [i for i in ALL if not a.only or i in a.only.split(',')]
    R = render_voxel if a.style == 'voxel' else render_ps1; tag = a.style.upper(); t0 = time.time()
    what = a.what.split(',')
    if 'vues' in what:
        for b in range(0, len(ids), a.batch):
            res = R(plan_vues(ids[b:b + a.batch]), out, tag)
            for name, (im, lab) in res.items(): label(im, f'{tag} — {lab}').save(out / f'{name}.png')
            print('vues', ids[b:b + a.batch], round(time.time() - t0), 's', flush=True)
    if 'tour' in what:
        res = R(plan_tour(), out, tag); fr = []
        for i in range(6):
            im, lab = res[f'tour_{i + 1}']; im.save(out / f'tour_{i + 1}.png'); fr.append((im, f'image {i + 1}'))
        grid(fr, f'{tag} — tour sur soi : la jupe s\'évase avec la vitesse de rotation (Eliza, dame tartan)').save(out / 'tour_6_images.png'); print('tour', round(time.time() - t0), 's', flush=True)
    if 'marche' in what:
        res = R(plan_marche(), out, tag)
        for key, title in (('marche', 'marche (un cycle de pas) : la jupe suit le bassin, les jambes restent dedans'), ('marche_redingote', 'marche (un cycle de pas) : les basques s\'écartent de la cuisse qui recule')):
            fr = []
            for i in range(6):
                im, lab = res[f'{key}_{i + 1}']; im.save(out / f'{key}_{i + 1}.png'); fr.append((im, f'image {i + 1}'))
            grid(fr, f'{tag} — {title}').save(out / f'{key}_6_images.png')
        print('marche', round(time.time() - t0), 's', flush=True)
    main_ids = [i for i in ids if i in COS.PRINCIPAUX]
    if 'gros' in what and main_ids:
        res = R(plan_gros(main_ids), out, tag)
        for name, (im, lab) in res.items(): label(im, f'{tag} — {lab}').save(out / f'{name}.png')
        print('gros plans', round(time.time() - t0), 's', flush=True)
    if 'tetes' in what and main_ids:
        res = R(plan_tetes(main_ids), out, tag)
        for name, (im, lab) in res.items(): im.save(out / f'{name}.png')
        rows = [cid for cid in main_ids]; W, rh = 1920, 360; sheet = Image.new('RGB', (W, 60 + rh * len(rows)), (14, 14, 18)); d = ImageDraw.Draw(sheet)
        d.text((14, 12), f'{tag} — têtes : référence (inspiration) | face | trois quarts', fill=(240, 236, 226), font=_font(30))
        for k, cid in enumerate(rows):
            y = 60 + k * rh
            if cid in REF_HEADS and (REF / 'vignettes' / REF_HEADS[cid][0]).exists():
                ref = Image.open(REF / 'vignettes' / REF_HEADS[cid][0]).convert('RGB').crop(REF_HEADS[cid][1]); ref.thumbnail((600, rh - 10)); sheet.paste(ref, (10, y + 5))
            for j, nm in enumerate((f'tete_face_{cid}', f'tete_34_{cid}')):
                im = res[nm][0].crop((420, 0, 1500, 1080)); im.thumbnail((640, rh - 10)); sheet.paste(im, (640 + j * 640, y + 5))
            d.text((20, y + rh - 40), cid, fill=(255, 240, 160), font=_font(26))
        sheet.save(out / 'tetes.png'); print('têtes', round(time.time() - t0), 's', flush=True)
    if 'tetes2' in what and main_ids:
        res = R(plan_tetes2(main_ids), out, tag)
        cols = ('face', '34', 'bouche', 'yeux'); W, rh = 1920, 330; sheet = Image.new('RGB', (W, 64 + rh * len(main_ids)), (14, 14, 18)); d = ImageDraw.Draw(sheet)
        d.text((14, 14), f'{tag} — têtes peintes (skin) : référence | face | trois quarts | bouche ouverte | yeux fermés', fill=(240, 236, 226), font=_font(30))
        for k, cid in enumerate(main_ids):
            y = 64 + k * rh
            if cid in REF_HEADS and (REF / 'vignettes' / REF_HEADS[cid][0]).exists():
                ref = Image.open(REF / 'vignettes' / REF_HEADS[cid][0]).convert('RGB').crop(REF_HEADS[cid][1]); ref.thumbnail((370, rh - 10)); sheet.paste(ref, (8, y + 5))
            for j, c in enumerate(cols):
                im = res[f'tete2_{c}_{cid}'][0]; im.save(out / f'tete2_{c}_{cid}.png'); im = im.crop((380, 0, 1540, 1080)); im.thumbnail((380, rh - 10)); sheet.paste(im, (386 + j * 384, y + 5))
            d.text((14, y + rh - 38), cid, fill=(255, 240, 160), font=_font(24))
        sheet.save(out / 'tetes_v2.png'); print('têtes v2', round(time.time() - t0), 's', flush=True)
    if 'theatre' in what:
        res = R(plan_theatre('angelica'), out, tag)
        for wash in ('bleu_nuit', 'ambre'):
            im, lab = res[f'theatre_{wash}_angelica']; label(im, f'{tag} — angelica sur la scène, lavis {wash} — face / profil / dos').save(out / (f'vues_angelica_v2.png' if wash == 'bleu_nuit' else f'vues_angelica_v2_{wash}.png'))
        print('théâtre', round(time.time() - t0), 's', flush=True)
    if 'gestes' in what:
        res = R(plan_gestes(), out, tag); fr = []
        for gt, _, lab in GESTES:
            im, _l = res[f'geste_{gt}']; label(im.copy(), f'{tag} — {lab}').save(out / f'geste_{gt}.png'); fr.append((im, lab))
        g6 = grid(fr, f'{tag} — nouvelles clés de piste : côté gauche, bras écartés, à genoux, assis par terre (robe et redingote)'); g6.save(out / 'gestes_controle.png')
        print('gestes', round(time.time() - t0), 's', flush=True)
    if COS.WARN: print('avertissements :', COS.WARN)


if __name__ == '__main__':
    main()
