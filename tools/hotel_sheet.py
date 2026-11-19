"""Planches de contrôle du lieu `hotel_nuit` (CHAMBRE 313, style PS1) : chaque planche = quelques vues rendues par le VRAI moteur
(Pixel3DEngine, scène dirigée : caméra `rig: path` ou `free`, acteurs en clés `tracks`), légendées en français.

    python tools/hotel_sheet.py <dossier> [--aspect 9:16|16:9|both] [--only reception,couloir,...] [--workers 6] [--scale .5]

Planches : reception, inserts, couloir, escalier_sud, cloison, panneau_rouge, escalier_ext, exterieur, chambre_313, lendemain,
personnages_1, personnages_2 (une image par personnage). Rien d'aléatoire : deux exécutions donnent les mêmes images."""
import sys, os, math, time, json, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from PIL import Image, ImageDraw, ImageFont

CAST = {'rec': 'receptionniste', 'g1': 'cliente_agee', 'g2': 'client_pyjama', 'g3': 'cliente_peignoir', 'g4': 'client_tshirt', 'g5': 'cliente_nuisette',
        'g6': 'ado_pyjama', 'p1': 'pompier', 'p2': 'pompier_2', 'chef': 'chef_pompier', 'tech': 'technicien', 'mere': 'mere_fantome', 'fils': 'garcon_fantome'}
NAMES = {'rec': 'RÉCEPTIONNISTE', 'g1': 'CLIENTE ÂGÉE', 'g2': 'CLIENT PYJAMA', 'g3': 'CLIENTE PEIGNOIR', 'g4': 'CLIENT T-SHIRT', 'g5': 'CLIENTE NUISETTE',
         'g6': 'ADO', 'p1': 'POMPIER', 'p2': 'POMPIER 2', 'chef': 'CHEF POMPIER', 'tech': 'TECHNICIEN', 'mere': 'LA MÈRE', 'fils': 'LE PETIT GARÇON'}


def yaw_to(p, q): return math.atan2(q[0] - p[0], q[2] - p[2])


def actor(p, look_at=None, yaw=None, **kw):
    k = {'t': 0, 'p': list(p), 'yaw': yaw if yaw is not None else (yaw_to(p, look_at) if look_at is not None else 0.)}
    k.update(kw); return [k]


def V(title, pos, look, fov=60, state=None, tracks=None, flash=False, t=1.0, spec=None):
    return dict(title=title, pos=pos, look=look, fov=fov, state=state or {}, tracks=tracks or {}, flash=flash, t=t, spec=spec or {})


NIGHT = {'clock': '02:13'}
RING = dict(board_313=1, landline_ring=1, screen='call', clock='02:13')
X3 = 40.0


def planches():
    from hstudio.engines.pixel3d import hotel as H
    rec_desk = (-5.25, 0., 4.2)
    P = {}
    P['reception'] = [
        V('RÉCEPTION DE NUIT, 02:13 : LE STANDARD 313 S\'ALLUME', [2.4, 1.65, 1.2], [-4.6, 1.2, 4.5], 60, RING, {'rec': actor(rec_desk, yaw=math.pi / 2, face='shocked', head=[0., -.25])}),
        V('LE COMPTOIR DE PLUS PRÈS', [-2.2, 1.55, 2.5], [-5.0, 1.15, 4.4], 56, RING, {'rec': actor(rec_desk, look_at=(-4.55, 1.0, 3.55), face='scared')}),
        V('IL DÉCROCHE (COMBINÉ EN MAIN)', [-2.6, 1.6, 4.6], [-5.25, 1.5, 5.3], 50, dict(RING, landline_ring=0, handset=0),
          {'rec': actor((-5.25, 0., 5.3), yaw=math.pi / 2, gesture='phone', hold='handset', face='scared')}),
        V('DERRIÈRE LA RÉCEPTION : PLAN, HORLOGE, PANNEAU (VOYANT ROUGE)', [-4.4, 1.6, 4.9], [-7.0, 1.55, 5.0], 64, dict(NIGHT, panel_led=1, clock='02:14')),
    ]
    P['inserts'] = [
        V('INSERT STANDARD : VOYANT 313', [-5.85, 1.6, 3.35], [-4.55, 1.0, 3.5], 48, RING),
        V('INSERT ÉCRAN : APPEL CH 313 02:13', [-5.45, 1.32, 4.75], [-4.5, 1.12, 4.75], 46, RING),
        V('INSERT HORLOGE : 02:14', [-5.75, 1.95, 5.8], [-7.0, 2.15, 5.8], 40, dict(NIGHT, clock='02:14')),
        V('INSERT TÉLÉPHONE QUI SONNE', [-5.3, 1.4, 5.15], [-4.42, .86, 5.85], 46, RING),
        V('INSERT PLAN D\'ÉVACUATION : ESCALIER NORD', [-5.7, 1.62, 4.85], [-7.0, 1.62, 4.85], 50, NIGHT),
        V('INSERT PANNEAU ÉLECTRIQUE : VOYANT ROUGE', [-5.7, 1.6, 5.3], [-7.0, 1.45, 5.85], 52, dict(NIGHT, panel_led=1), t=.15),
        V('INSERT PORTABLE : 02:16', [-4.66, 1.62, 5.25], [-4.68, 1.6, 4.55], 30, dict(NIGHT, clock='02:16'),
          {'rec': actor((-5.1, 0., 4.3), yaw=0., gesture='show', hold='mobile', head=[.3, -.2])}),
    ]
    cor_cam = [.35, 1.6, 9.7]; cor_look = [-.1, 1.3, 24.0]
    guests = {'g2': actor((-.5, 0., 15.2), look_at=(0., 0., 10.)), 'g3': actor((.45, 0., 16.4), look_at=(0., 0., 10.)), 'g4': actor((-.35, 0., 18.3), look_at=(0., 0., 10.))}
    P['couloir'] = [
        V('COULOIR NORMAL (PLAFONNIERS)', cor_cam, cor_look, 62, NIGHT),
        V('FINE FUMÉE GRISE QUI DESCEND DU PLAFOND', cor_cam, cor_look, 62, dict(NIGHT, smoke=.55, smoke_low=1.75)),
        V('ALARME + ÉCLAIRAGE DE SECOURS, PORTES OUVERTES', cor_cam, cor_look, 62, dict(NIGHT, ceiling=0, emergency=1, alarm=1, smoke=.45, smoke_low=1.75,
          door_02=.9, door_03=.8, door_04=.85, alarm_button=1), guests, flash=True),
        V('COULOIR ENVAHI : LA FUMÉE NOIRE AVANCE', [-.3, 1.55, 23.3], [.1, 1.2, 10.0], 62, dict(NIGHT, ceiling=0, emergency=1, alarm=1, smoke=.5, smoke_low=1.6, smoke_black=1., smoke_front=17.0,
          door_02=.9, door_03=.8)),
    ]
    sd_cam = [.6, 1.6, 14.0]; sd_look = [.4, 1.2, 10.3]
    P['escalier_sud'] = [
        V('LA PORTE DE L\'ESCALIER PRINCIPAL (SUD)', sd_cam, sd_look, 66, dict(NIGHT, ceiling=1, alarm=1, smoke=.3), {'rec': actor((-.3, 0., 10.6), yaw=math.pi / 2 - .35, reach_r=[.15, 1.0, .5, .6])}),
        V('IL OUVRE : LE NUAGE NOIR JAILLIT', sd_cam, sd_look, 66, dict(NIGHT, alarm=1, smoke=.3, stair_door=.75, smoke_burst=.5, stair_fire=.8),
          {'rec': actor((-.5, 0., 11.0), yaw=math.pi / 2 - .5, face='shocked', gesture='cover_face', lean=-.3)}),
        V('LE NUAGE REMPLIT LE DÉBUT DU COULOIR', [-.35, 1.55, 16.6], [.3, 1.2, 10.0], 60, dict(NIGHT, alarm=1, smoke=.5, stair_door=.9, smoke_burst=1., stair_fire=1., smoke_black=.8, smoke_front=12.0),
          {'rec': actor((.15, 0., 14.2), look_at=(-.35, 0, 16.6), face='scared', gesture='cover_face')}),
    ]
    cl_cam = [.5, 1.55, 20.3]; cl_look = [-.1, 1.2, 25.3]
    P['cloison'] = [
        V('LA CLOISON DE CHANTIER, INTACTE', cl_cam, cl_look, 60, dict(NIGHT, ceiling=1)),
        V('PREMIER COUP (PIED-DE-BICHE)', [1.0, 1.5, 21.0], [-.3, 1.3, 24.6], 60, dict(NIGHT, cloison_hit=1., crowbar_in_box=0),
          {'rec': actor((.0, 0., 23.75), yaw=0., gesture='arm_up', hold='crowbar', face='determined')}, t=.4),
        V('DEUXIÈME COUP : UNE PLANCHE SE DÉTACHE', cl_cam, cl_look, 60, dict(NIGHT, cloison=1.45, crowbar_in_box=0),
          {'rec': actor((.65, 0., 23.4), yaw=-.35, gesture='hold', hold='crowbar', face='surprised')}),
        V('OUVERTE : LA VIEILLE PORTE VERTE', cl_cam, cl_look, 60, dict(NIGHT, cloison=4, crowbar_in_box=0, ceiling=0, emergency=1)),
    ]
    P['panneau_rouge'] = [
        V('LE PANNEAU ROUGE, À GAUCHE DE LA PORTE', [-.25, 1.5, 24.9], [-.7, 1.35, 26.0], 46, dict(NIGHT, cloison=4, ceiling=0, emergency=1)),
        V('LA VITRE SE BRISE', [-.3, 1.45, 25.05], [-.8, 1.35, 26.0], 40, dict(NIGHT, cloison=4, red_glass=.5, ceiling=0, emergency=1)),
        V('VITRE BRISÉE, LEVIER TIRÉ', [-.3, 1.45, 25.05], [-.8, 1.3, 26.0], 40, dict(NIGHT, cloison=4, red_glass=1, lever=1, ceiling=0, emergency=1)),
        V('LA PORTE S\'OUVRE SUR LA NUIT', [.1, 1.6, 23.2], [0., .8, 28.5], 64, dict(NIGHT, cloison=4, red_glass=1, lever=1, green_door=.85, ceiling=0, emergency=1)),
    ]
    P['escalier_ext'] = [
        V('L\'ESCALIER DE SECOURS DESCEND DANS LA NUIT', [.05, 1.75, 26.15], [0., -1.1, 31.5], 70, dict(NIGHT, cloison=4, green_door=1., ceiling=0, emergency=1)),
        V('DEPUIS LA COUR : LES CLIENTS DESCENDENT', [3.4, -.15, 33.2], [0., -.4, 27.6], 64, dict(NIGHT, cloison=4, green_door=1., ceiling=0, emergency=1, window_smoke=.5, window_fire=.4),
          {'g1': actor((0., -1.8, 31.0), look_at=(3, 0, 35)), 'g2': actor((.2, -1.08, 28.7), yaw=0.), 'g3': actor((-.15, -.54, 27.9), yaw=0.), 'rec': actor((0., 0., 26.75), yaw=0.)}),
        V('LA FUMÉE NOIRE SORT PAR LA PORTE QU\'ILS QUITTENT', [2.8, -.35, 36.2], [0., .6, 27.5], 62, dict(NIGHT, cloison=4, green_door=1., ceiling=0, emergency=1, smoke=1., smoke_low=.6, smoke_black=1.),
          {'rec': actor((.6, -1.8, 31.0), look_at=(0, 1, 26.3), face='shocked'), 'g6': actor((-1.0, -1.8, 31.6), look_at=(0, 1, 26.3)), 'g4': actor((1.6, -1.8, 31.9), look_at=(0, 1, 26.3))}),
    ]
    P['exterieur'] = [
        V('FAÇADE : LA FENÊTRE MURÉE AU 3E (313), FUMÉE AUX FENÊTRES', [7.0, -1.2, 43.5], [-1.6, 6.0, 26.3], 70, dict(NIGHT, truck=1, beacons=1, window_fire=1, window_smoke=1, hoses=1, green_door=1., cloison=4)),
        V('LA FENÊTRE MURÉE DE LA 313, VUE DE LA COUR', [-.6, -1.0, 32.5], [-3.2, 10.4, 26.3], 38, dict(NIGHT, truck=1, beacons=1, window_fire=1, window_smoke=.6)),
        V('LES POMPIERS, GYROPHARES', [7.5, -.2, 31.0], [-2.0, -.3, 36.0], 66, dict(NIGHT, truck=1, beacons=1, window_fire=1, window_smoke=1, hoses=1),
          {'p1': actor((1.0, -1.8, 33.0), look_at=(-.5, 0, 26)), 'p2': actor((2.6, -1.8, 31.6), look_at=(0, 0, 26)), 'chef': actor((4.4, -1.8, 33.4), look_at=(7.5, 0, 31.0))}),
        V('LE CHEF PREND DES NOTES', [2.9, -.25, 30.7], [4.3, -.45, 33.0], 54, dict(NIGHT, truck=1, beacons=1, window_smoke=.7),
          {'chef': actor((4.7, -1.8, 33.1), yaw=-math.pi / 2 - .35, gesture='hold', hold='notebook', face='suspicious'), 'rec': actor((3.45, -1.8, 32.85), yaw=math.pi / 2 - .2, face='nervous')}),
    ]
    P['chambre_313'] = [
        V('3E ÉTAGE AUJOURD\'HUI : LA 313 MURÉE', [X3 + .75, 1.55, 3.4], [X3 - 1.3, 1.15, 7.5], 62, dict(era='now')),
        V('LA PORTE MURÉE, DE PRÈS', [X3 + .4, 1.5, 6.2], [X3 - 1.3, 1.25, 7.5], 52, dict(era='now', work_lamp=1)),
        V('VINGT ANS PLUS TÔT : FUMÉE SOUS LA PORTE 313', [X3 + .75, 1.55, 3.4], [X3 - 1.3, .95, 7.5], 62, dict(era='before', under_door_smoke=1, under_door_glow=1, smoke=.35, smoke_low=1.8)),
        V('LA MÈRE ET SON FILS (APPARITION)', [X3 + .8, 1.45, 3.4], [X3 - .4, 1.1, 7.6], 56, dict(era='before', under_door_smoke=.6, under_door_glow=1., smoke=.3, smoke_low=1.9, power=.3),
          {'mere': actor((X3 - .45, 0., 7.9), look_at=(X3 + .8, 0, 3.6), dissolve=.12), 'fils': actor((X3 - .05, 0., 7.35), look_at=(X3 + .8, 0, 3.6), dissolve=.12)}),
    ]
    P['lendemain'] = [
        V('LE LENDEMAIN : HALL FERMÉ, HOUSSES, LUMIÈRE GRISE', [-1.3, 1.7, .9], [3.4, .9, 5.0], 66, dict(moment='matin')),
        V('LA RÉCEPTION, LE MATIN', [2.3, 1.6, 1.4], [-4.2, 1.1, 5.0], 62, dict(moment='matin')),
        V('LE JOURNAL DU STANDARD SUR LE COMPTOIR', [-3.05, 1.6, 4.15], [-3.72, 1.08, 4.15], 32, dict(moment='matin')),
        V('IL TIENT LE PAPIER', [-2.15, 1.75, 4.95], [-3.15, 1.6, 4.85], 38, dict(moment='matin', log_paper=0),
          {'rec': actor((-3.0, 0., 4.4), yaw=-math.pi / 2 + .25, gesture='show', hold='printout', face='sad'), 'tech': actor((-1.4, 0., 5.6), look_at=(-3.0, 0, 4.4))}),
    ]
    for k, grp in enumerate((list(CAST)[:7], list(CAST)[7:])):          # every character in full, one image each, lit like a casting
        P[f'personnages_{k + 1}'] = [V(NAMES[aid], [0., 1.0, 2.35], [0., .95, 5.0], 52, dict(NIGHT, lobby=1), {aid: actor((0., 0., 5.0), yaw=math.pi + .35)}, spec={'fill': .75})
                                     for aid in grp]
    return P


def episode(views):
    shots = []; lines = []; sets = {}
    for i, v in enumerate(views):
        lines.append(dict(start=i * 2.0, end=i * 2.0 + 1.9, text='', words=[]))
        name = 'hotel' if not v['spec'] else f'hotel_{i}'
        sets[name] = dict(v['spec'], type='hotel_nuit')
        sh = {'lines': [i, i], 'set': name, 'state': v['state'], 'ui': {'hud': False, 'subs': 'off'}}
        cam = {'pos': v['pos'], 'look': v['look'], 'fov': v['fov']}
        if v['tracks']: sh['tracks'] = v['tracks']; sh['camera'] = {'rig': 'path', 'keys': [dict(cam, t=0)]}
        else: sh['camera'] = {'preset': 'free', 'keys': [cam]}
        shots.append(sh)
    ep = {'style': 'pixel3d', 'hud': {'show': False}, 'sets': sets, 'default_set': 'hotel', 'shots': shots,
          'cast': {a: {'preset': p} for a, p in CAST.items()}}
    return ep, lines


def frame_time(i, v):
    g = i * 2.0 + v['t']
    if v['flash']:
        from hstudio.engines.pixel3d.hotel import strobe
        rate = float(v['state'].get('alarm_rate', 1.1))
        for k in range(160):
            gg = i * 2.0 + .2 + k * .01
            if strobe(gg, rate, 0.) > .5: return gg
    return g


def render_planche(args):
    name, aspect, scale = args
    from hstudio.pipeline import make_engine
    views = planches()[name]
    ep, lines = episode(views); dur = len(views) * 2.0
    eng = make_engine('pixel3d', ep, lines, np.zeros(int(dur * 30) + 60), dur, aspect)
    ims = []
    for i, v in enumerate(views): ims.append((v['title'], eng.frame(frame_time(i, v))))
    return name, aspect, ims


def compose(name, aspect, ims, out, scale):
    from hstudio.paths import FONT_PIXEL
    w, h = ims[0][1].size; W, H = int(w * scale), int(h * scale)
    n = len(ims); cols = min(n, (4 if n <= 4 else 7 if n == 7 else 4) if aspect == '9:16' else (2 if n <= 4 else 4)); rows = (n + cols - 1) // cols
    bar = 54 if aspect == '9:16' else 46
    sheet = Image.new('RGB', (W * cols, (H + bar) * rows), (12, 12, 14)); d = ImageDraw.Draw(sheet)
    f = ImageFont.truetype(FONT_PIXEL, 13 if aspect == '9:16' else 14)
    for k, (title, im) in enumerate(ims):
        x, y = (k % cols) * W, (k // cols) * (H + bar)
        sheet.paste(im.resize((W, H), Image.NEAREST), (x, y + bar))
        words = title.split(); line = ''; ly = y + 6
        for wd in words:
            if d.textlength(line + ' ' + wd, font=f) > W - 14 and line: d.text((x + 7, ly), line, font=f, fill=(236, 230, 210)); ly += 18; line = wd
            else: line = (line + ' ' + wd).strip()
        d.text((x + 7, ly), line, font=f, fill=(236, 230, 210))
    p = os.path.join(out, f"{name}_{aspect.replace(':', 'x')}.png"); sheet.save(p)
    return p


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('--aspect', default='both'); ap.add_argument('--only', default='')
    ap.add_argument('--workers', type=int, default=6); ap.add_argument('--scale', type=float, default=.5)
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    names = [n for n in planches() if not a.only or n in a.only.split(',')]
    aspects = ['9:16', '16:9'] if a.aspect == 'both' else [a.aspect]
    jobs = [(n, asp, a.scale) for n in names for asp in aspects]
    t0 = time.time()
    if a.workers > 1 and len(jobs) > 1:
        import multiprocessing as mp
        with mp.Pool(min(a.workers, len(jobs))) as pool:
            for name, asp, ims in pool.imap_unordered(render_planche, jobs):
                print('planche', compose(name, asp, ims, a.out, a.scale), round(time.time() - t0), 's', flush=True)
    else:
        for j in jobs:
            name, asp, ims = render_planche(j); print('planche', compose(name, asp, ims, a.out, a.scale), round(time.time() - t0), 's', flush=True)


if __name__ == '__main__':
    main()
