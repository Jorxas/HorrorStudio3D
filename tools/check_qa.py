"""Tests du contrôle qualité des scènes dirigées (hstudio/qa, tools/verifier_scene.py).

    python tools/check_qa.py            # épisodes synthétiques : un par type d'erreur (détecté, et corrigé quand c'est prévu) + la barrière du rendu
    python tools/check_qa.py --reels    # en plus : passage sur Chambre 313 (3 dossiers) et Satisfied ; rapports dans docs/qa_scene/

Chaque épisode synthétique est une petite pièce (6 x 8 m) avec deux personnages et UN défaut. Rien n'est écrit hors d'un dossier temporaire
(sauf --reels : les rapports). Aucun réseau, aucune voix, aucun GPU (sauf --reels avec images VOXEL, non lancé ici)."""
import copy, json, math, os, shutil, subprocess, sys, tempfile, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np

PI = math.pi
RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok))); print(('OK    ' if ok else 'ÉCHEC ') + name + (f'  — {detail}' if detail else ''), flush=True)


def lines_of(n=3, step=2.0, ln=1.6, t0=.2):
    return [{'start': round(t0 + i * step, 3), 'end': round(t0 + i * step + ln, 3), 'text': f'Phrase {i}.', 'speaker': 'narrateur'} for i in range(n)]


def K(t, x, z, yaw, **kw): return dict({'t': t, 'p': [x, 0., z], 'yaw': yaw}, **kw)
def CAM(t, pos, look, fov=60, **kw): return dict({'t': t, 'pos': pos, 'look': look, 'fov': fov}, **kw)


def base(n=3):
    """a clean dialogue: a (west) and b (east) face each other in a lit room; the camera on the south side"""
    shots = []
    for i in range(n):
        shots.append({'lines': [i, i], 'set': 'piece', 'ui': {'subs': 'low'},
                      'tracks': {'a': [K(0, -.8, 4., PI / 2, face='neutral')], 'b': [K(0, .8, 4., -PI / 2, face='neutral')]},
                      'camera': {'rig': 'path', 'keys': [CAM(0, [0., 1.6, 1.0], [0., 1.45, 4.0], 60)]}})
    ep = {'style': 'pixel3d', 'title': 'TEST QA', 'hud': {'title': ['TEST QA'], 'part': '', 'hearts': [], 'show': False},
          'sets': {'piece': {'type': 'room', 'rooms': [{'id': 'r', 'origin': [0, 0], 'size': [6, 8], 'walls': 'plaster', 'floor': 'wood', 'light': 'warm',
                                                         'props': [{'type': 'wardrobe', 'at': [-2.2, 6.5], 'rot': 3, 'id': 'armoire'}, {'type': 'table', 'at': [1.6, 6.2], 'id': 'table'}]}]}},
          'default_set': 'piece', 'cast': {'a': {}, 'b': {'outfit': 'dress', 'hair_style': 'long', 'hood': [150, 60, 60]}}, 'shots': shots,
          'grade': {'saturation': .8, 'exposure': 1.1}}
    return ep


def write(d, ep, lines):
    os.makedirs(d, exist_ok=True)
    json.dump(ep, open(os.path.join(d, 'episode.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump(lines, open(os.path.join(d, 'lines.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    return d


def run_case(tmp, name, ep, lines, code, sev=None, auto=False, images=False, aspect='16:9', style='ps1', after=None, fixable=None):
    from hstudio.qa import run as R, fix as FX, load as LD
    d = write(os.path.join(tmp, name.replace(' ', '_')), ep, lines)
    E = LD.load(d, aspect, style)
    rep = R.verify(d, aspect, style, images=images, workers=1, log=None, E=E)
    hits = [i for i in rep.merged() if i.code == code]
    ok = bool(hits) and (sev is None or any(i.severity == sev for i in hits))
    check(f'{name} : détecté [{code}]' + (f' ({sev})' if sev else ''), ok, '' if ok else f'trouvé : {sorted({(i.code, i.severity) for i in rep.merged()})}')
    if not ok or not (auto or fixable):
        return rep, None
    ep2, changes, manual = FX.apply(E, rep, style)
    d2 = write(d + '_corrige', ep2, lines)
    rep2 = R.verify(d2, aspect, style, images=images, workers=1, log=None, E=LD.load(d2, aspect, style))
    left = [i for i in rep2.merged() if i.code == code and i.severity != 'info']
    good = bool(changes) and not left
    if after: good = good and after(ep2, rep2)
    check(f'{name} : corrigé automatiquement', good, f'{len(changes)} changement(s) ; reste {[(i.code, i.severity, i.msg[:60]) for i in left]}')
    return rep, rep2


def synthetic(tmp):
    L3 = lines_of(3)
    # ---------------------------------------------------------------- the clean scene must stay clean (no false blocking error)
    from hstudio.qa import run as R, load as LD
    d = write(os.path.join(tmp, 'propre'), base(), L3)
    rep = R.verify(d, '16:9', 'ps1', images=True, workers=1, log=None)
    check('scène propre : aucune erreur bloquante', rep.ok(), str([(i.code, i.msg[:70]) for i in rep.blocking()]))
    check('scène propre : le rapport markdown et json se construisent', '# Contrôle qualité' in rep.markdown() and json.dumps(rep.to_json(), ensure_ascii=False))
    # ---------------------------------------------------------------- time, formats, titles
    ep = base(); ep['shots'][1]['lines'] = [2, 2]; ep['shots'] = ep['shots'][:2]
    run_case(tmp, 'trou de phrases', ep, L3, 'temps.trou', 'bloquant', auto=True)
    ep = base(); ep['shots'][1]['lines'] = [0, 1]
    run_case(tmp, 'chevauchement', ep, L3, 'temps.chevauchement', 'bloquant', auto=True)
    ep = base(); ep['duration'] = 3.0
    run_case(tmp, 'durée qui coupe la voix', ep, L3, 'temps.duree', 'bloquant', auto=True)
    Ls = [{'start': .2 + 95 * i, 'end': 1.8 + 95 * i, 'text': f'P{i}.', 'speaker': 'narrateur'} for i in range(3)]
    from hstudio.qa import editorial as ED
    from hstudio.qa.report import Report
    d = write(os.path.join(tmp, 'vertical_long'), base(), Ls)
    rep = Report(d, '9:16', 'ps1', 'éditorial')
    ED.check(LD.load(d, '9:16', 'ps1'), rep)
    check('vertical de plus de 3 min : accepté sans découpe obligatoire', rep.ok(), str([(i.code, i.msg) for i in rep.blocking()]))
    ep = base(); ep['hud']['title'] = ['AUTRE TITRE']
    run_case(tmp, 'titre incohérent', ep, L3, 'titre.incoherent', 'bloquant', auto=True)
    par = os.path.join(tmp, 'histoire'); ep1 = base(); ep1['hud']['part'] = 'PARTIE 1'; ep2 = base(); ep2['title'] = 'UN AUTRE'; ep2['hud'] = dict(ep2['hud'], title=['UN AUTRE'], part='PARTIE 2')
    write(os.path.join(par, 'partie2_9x16'), ep2, L3)
    run_case(par, 'partie1_9x16', ep1, L3, 'titre.parties', 'bloquant', aspect='9:16')
    ep = base(); ep['hud']['part'] = 'PARTIE 2'
    run_case(os.path.join(tmp, 'h2'), 'partie1_9x16', ep, L3, 'titre.etiquette', 'bloquant', auto=True, aspect='9:16')
    # ---------------------------------------------------------------- names the engine would silently ignore
    ep = base(); ep['shots'][0]['tracks']['a'][0]['gesture'] = 'pointe'
    run_case(tmp, 'geste inconnu', ep, L3, 'cle.inconnue', 'bloquant', auto=True, after=lambda e, r: e['shots'][0]['tracks']['a'][0]['gesture'] == 'point')
    ep = base(); ep['shots'][0]['tracks']['a'][0]['hold'] = 'phonne'
    run_case(tmp, 'objet inconnu', ep, L3, 'cle.inconnue', 'bloquant', auto=True, after=lambda e, r: e['shots'][0]['tracks']['a'][0]['hold'] == 'phone')
    ep = base(); ep['shots'][0]['tracks']['a'][0]['yaww'] = 1.0
    run_case(tmp, 'clé de piste mal écrite', ep, L3, 'cle.inconnue', 'bloquant', auto=True, after=lambda e, r: 'yaw' in e['shots'][0]['tracks']['a'][0] and 'yaww' not in e['shots'][0]['tracks']['a'][0])
    ep = base(); ep['shots'][0]['tracks']['a'][0]['face'] = 'zzz'
    run_case(tmp, 'expression inconnue', ep, L3, 'cle.inconnue', 'a_revoir')
    ep = base(); del ep['shots'][0]['tracks']['a'][0]['p']
    run_case(tmp, 'piste sans position', ep, L3, 'piste.sans_position', 'bloquant')
    ep = base(); ep['shots'][0]['tracks']['a'] = [K(0, -2.5, 4., PI / 2), K(.5, 2.5, 4., PI / 2)]
    run_case(tmp, 'téléportation dans le plan', ep, L3, 'piste.vitesse')
    ep = base(); ep['shots'][0]['camera']['keys'][0]['look'] = {'on': 'zed', 'h': 1.5}
    run_case(tmp, 'caméra qui suit un absent', ep, L3, 'camera.cible_absente', 'bloquant')
    ep = base(); ep['shots'][0].pop('tracks')
    run_case(tmp, 'caméra en clés sans piste', ep, L3, 'camera.path_sans_pistes', 'bloquant', auto=True)
    ep = base(); ep['style'] = 'pixel3d'; ep['shots'][0]['state'] = {'dim': [0, 1]}
    run_case(tmp, 'état [a, b] en VOXEL', ep, L3, 'voxel.etat_milieu', 'a_revoir', auto=True, style='voxel')
    # ---------------------------------------------------------------- speech
    Lg = [{'start': .2, 'end': 1.0, 'text': 'Un.', 'speaker': 'narrateur'}, {'start': 3.6, 'end': 4.4, 'text': 'Deux.', 'speaker': 'narrateur'}, {'start': 5.0, 'end': 6.0, 'text': 'Trois.', 'speaker': 'narrateur'}]
    ep = base(); ep['shots'][0]['tracks']['a'][0]['talk'] = 1
    run_case(tmp, 'bouche qui parle sans voix', ep, Lg, 'parole.sans_voix', 'a_revoir')
    Lb = lines_of(3); Lb[1]['speaker'] = 'b'
    run_case(tmp, 'voix sans bouche', base(), Lb, 'parole.voix_sans_bouche', 'a_revoir')
    ep = base(); ep['shots'][0]['tracks']['a'] = [K(0, -.4, 3.0, 0., talk=1)]; ep['shots'][0]['tracks']['b'] = [K(0, 2.6, 6.5, PI)]
    ep['shots'][0]['camera']['keys'] = [CAM(0, [-.4, 1.6, 1.4], [-.4, 1.55, 3.0], 58)]; Ld = lines_of(3)
    run_case(tmp, 'on voit le dos de celui qui parle', ep, Ld, 'parole.dos', 'bloquant')
    # ---------------------------------------------------------------- bodies, walls, lens
    ep = base(); ep['shots'][0]['tracks']['a'] = [K(0, 0., 4., PI / 2)]; ep['shots'][0]['tracks']['b'] = [K(0, .05, 4.05, -PI / 2)]
    run_case(tmp, 'personnages qui se traversent', ep, L3, 'acteurs.traversent', 'bloquant', auto=True)
    ep = base(); ep['shots'][0]['tracks']['a'] = [K(0, -2.2, 6.5, PI)]
    ep['shots'][0]['camera']['keys'] = [CAM(0, [-.5, 1.6, 3.0], [-2.0, 1.3, 6.2], 60)]
    run_case(tmp, 'personnage dans une armoire', ep, L3, 'acteur.dans_decor', 'bloquant', auto=True)
    ep = base(); ep['shots'][0]['camera']['keys'] = [CAM(0, [-2.2, 1.5, 6.5], [0., 1.4, 4.0], 60)]
    run_case(tmp, 'caméra dans un meuble', ep, L3, 'camera.dans_decor', 'bloquant', auto=True)
    ep = base(); ep['shots'][0]['camera']['keys'] = [CAM(0, [0., 1.5, 7.85], [0., 1.4, 9.0], 60)]
    run_case(tmp, 'caméra collée au mur', ep, L3, 'camera.collee', 'bloquant')
    ep = base(); ep['shots'][0]['tracks']['b'] = [K(0, .05, 1.35, PI)]
    run_case(tmp, 'caméra bouchée par un personnage', ep, L3, 'camera.bouchee', 'bloquant')
    ep = base(); ep['shots'][0]['camera']['keys'] = [CAM(0, [-12., 1.6, 4.0], [-20., 1.6, 4.0], 60)]
    run_case(tmp, 'caméra hors du lieu', ep, L3, 'camera.hors_lieu', 'bloquant')
    # ---------------------------------------------------------------- framing
    ep = base(); ep['shots'][0]['tracks']['b'] = [K(0, 2.6, 7.0, PI)]
    ep['shots'][0]['camera']['keys'] = [CAM(0, [-.8, 1.0, 2.6], [-.8, 1.0, 4.0], 40)]
    run_case(tmp, 'tête coupée', ep, L3, 'cadre.tete_coupee', 'bloquant', aspect='9:16')
    ep = base(); ep['shots'][0]['tracks']['a'] = [K(0, -.8, 4., PI)]
    ep['shots'][0]['camera']['keys'] = [CAM(0, [-.8, 1.62, 3.35], {'on': 'a', 'h': 1.62}, 60)]
    run_case(tmp, 'visage trop serré', ep, L3, 'cadre.trop_serre', 'bloquant')
    # ---------------------------------------------------------------- 180 degrees and continuity
    ep = base(2); ep['shots'][0]['camera']['keys'] = [CAM(0, [-.3, 1.6, 2.6], {'on': 'b', 'h': 1.55}, 50)]
    ep['shots'][1]['camera']['keys'] = [CAM(0, [.3, 1.6, 5.4], {'on': 'a', 'h': 1.55}, 50)]
    run_case(tmp, 'règle des 180 degrés', ep, lines_of(2), 'raccord.180', 'bloquant')
    ep = base(2); ep['shots'][1]['tracks']['a'] = [K(0, -1.9, 4.6, PI / 2)]
    ep['shots'][1]['camera']['keys'] = [CAM(0, [0., 1.6, .8], [0., 1.4, 4.2], 70)]
    run_case(tmp, 'saut de position à la coupe', ep, lines_of(2), 'raccord.position', 'a_revoir')
    # ---------------------------------------------------------------- held objects, text
    ep = base(); ep['shots'][0]['tracks']['a'] = [K(0, -.8, 4., PI / 2, gesture='phone', hold='phone', face='neutral')]
    ep['shots'][0]['camera']['keys'] = [CAM(0, [-.8, 1.62, 5.6], {'on': 'a', 'h': 1.55}, 50)]
    run_case(tmp, 'objet dans la mauvaise main (caché)', ep, L3, 'objet.cache', 'a_revoir', auto=True)
    ep = base(); ep['sets']['piece']['rooms'][0]['props'].append({'type': 'note', 'at': [1.6, 6.2], 'y': .42, 'w': .5, 'text': ['NE PAS', 'OUVRIR'], 'fs': 10, 'flat': True})
    ep['shots'][0]['camera']['keys'] = [CAM(0, [1.6, 1.75, 5.2], [1.6, .8, 6.2], 50)]
    run_case(tmp, 'papier lu en miroir', ep, L3, 'texte.miroir', auto=True)
    # ---------------------------------------------------------------- image of the real painter
    ep = base(); ep['grade'] = {'saturation': .8, 'exposure': .3}
    run_case(tmp, 'plan trop sombre', ep, L3, 'image.sombre', 'a_revoir', images=True, fixable=True,
             after=lambda e, r: all(abs(float((s.get('fx') or {}).get('expo', 1.)) - 1.) > .05 for s in e['shots']))
    ep = base(); ep['grade'] = {'saturation': .8, 'exposure': 14.0}
    run_case(tmp, 'plan brûlé', ep, L3, 'image.brulee', images=True, fixable=True)
    ep = base(); ep['shots'][0]['ui'] = {'subs': 'mid'}; ep['shots'][0]['tracks']['b'] = [K(0, 2.6, 7.0, PI)]
    ep['shots'][0]['camera']['keys'] = [CAM(0, [-.8, 1.55, 2.3], {'on': 'a', 'h': 1.45}, 50)]
    ep['shots'][0]['tracks']['a'] = [K(0, -.8, 4., PI, talk=1)]
    run_case(tmp, 'sous-titre sur un visage', ep, lines_of(3), 'soustitre.visage', 'bloquant', images=True, auto=True, aspect='9:16')
    # ---------------------------------------------------------------- the image helpers themselves
    from hstudio.qa import probe as PB
    a = np.full((216, 384, 3), 40, np.uint8); a[50:80, 100:130] = 255
    check('carré blanc net (NaN étalé) : détecté', len(PB.flat_squares(a)) == 1)
    b = np.full((216, 384, 3), 40, np.uint8); yy, xx = np.mgrid[0:216, 0:384]; b[((yy - 60) ** 2 + (xx - 110) ** 2) < 400] = 200
    check('tache lumineuse douce (lampe) : pas un carré', not PB.flat_squares(b))
    st = PB.image_stats(np.zeros((216, 384, 3), np.uint8)); check('image noire : luminance nulle mesurée', st['mean'] == 0 and st['dark'] == 1.)
    c = np.full((270, 480, 3), 30., np.float32); yy, xx = np.mgrid[0:270, 0:480]
    c += 90. * np.exp(-(((yy - 100) / 40.) ** 2 + ((xx - 200) / 40.) ** 2))[..., None]   # the halo
    c[85:118, 185:218] = 236.; c[95:108, 195:208] = 250.                                  # the bloomed NaN square
    check('carré lumineux étalé par le halo (VOXEL) : détecté', len(PB.soft_squares(c.astype(np.uint8))) == 1)
    lan = np.full((270, 480, 3), 30, np.uint8); lan[60:68, 100:108] = (255, 190, 90)       # a lantern: small and orange
    check('lanterne orange : pas un carré', not PB.soft_squares(lan))
    real = r'C:\Users\demo\Desktop\videpgene\CLIP_SATISFIED_VOXEL\rendus\halo_264.jpg'
    if os.path.exists(real):
        from PIL import Image
        im = Image.open(real).convert('RGB'); a = np.asarray(im.resize((480, int(480 * im.size[1] / im.size[0])), Image.BILINEAR))
        check('vrai carré lumineux de Satisfied (rendus/halo_264.jpg) : détecté', len(PB.soft_squares(a)) >= 1)


def gate(tmp):
    """the render tool refuses a blocking error and renders with --forcer; the gate changes no image"""
    L3 = lines_of(3)
    ep = base(); ep['shots'][0]['tracks']['a'] = [K(0, 0., 4., PI / 2)]; ep['shots'][0]['tracks']['b'] = [K(0, .05, 4.05, -PI / 2)]
    d = write(os.path.join(tmp, 'barriere'), ep, L3); out = os.path.join(tmp, 'barriere.mp4')
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'render_film_dirigee.py'), d, 'ps1', out, '--seconds', '0.2', '--workers', '1'], capture_output=True, text=True, env=env, encoding='utf-8', errors='replace')
    check('barrière : rendu refusé sur erreur bloquante', r.returncode == 2 and not os.path.exists(out), (r.stdout + r.stderr)[-300:])
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'render_film_dirigee.py'), d, 'ps1', out, '--seconds', '0.2', '--workers', '1', '--forcer'], capture_output=True, text=True, env=env, encoding='utf-8', errors='replace')
    check('barrière : --forcer rend quand même', r.returncode == 0 and os.path.exists(out), (r.stdout + r.stderr)[-300:])
    d2 = write(os.path.join(tmp, 'propre_rendu'), base(), L3); out2 = os.path.join(tmp, 'propre.mp4')
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'render_film_dirigee.py'), d2, 'ps1', out2, '--seconds', '0.2', '--workers', '1'], capture_output=True, text=True, env=env, encoding='utf-8', errors='replace')
    check('barrière : scène propre rendue', r.returncode == 0 and os.path.exists(out2), (r.stdout + r.stderr)[-300:])
    # same frames with and without the QA having run in the process (the hooks are put back)
    from hstudio.pipeline import make_engine
    from hstudio.qa import run as R
    e1 = make_engine('pixel3d', copy.deepcopy(base()), L3, np.zeros(400), 6.6, '16:9'); f1 = np.asarray(e1.frame(1.0))
    R.verify(d2, '16:9', 'ps1', images=True, workers=1, log=None)
    e2 = make_engine('pixel3d', copy.deepcopy(base()), L3, np.zeros(400), 6.6, '16:9'); f2 = np.asarray(e2.frame(1.0))
    check('le contrôle ne change aucune image (crochets remis en place)', np.array_equal(f1, f2))
    # the original is never overwritten by --corriger
    before = open(os.path.join(d, 'episode.json'), encoding='utf-8').read()
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'verifier_scene.py'), d, '--corriger', '--workers', '1'], capture_output=True, text=True, env=env, encoding='utf-8', errors='replace')
    check('--corriger : original intact, copie + CORRECTIONS.md écrites', open(os.path.join(d, 'episode.json'), encoding='utf-8').read() == before
          and os.path.exists(os.path.join(d + '_corrige', 'CORRECTIONS.md')) and r.returncode == 0, (r.stdout + r.stderr)[-300:])


REELS = [(r'C:\Users\demo\Desktop\videpgene\HISTOIRE_CHAMBRE_313\dirige\long_16x9', 'ps1'), (r'C:\Users\demo\Desktop\videpgene\HISTOIRE_CHAMBRE_313\dirige\partie1_9x16', 'ps1'),
         (r'C:\Users\demo\Desktop\videpgene\HISTOIRE_CHAMBRE_313\dirige\partie2_9x16', 'ps1'), (r'C:\Users\demo\Desktop\videpgene\CLIP_SATISFIED_VOXEL\dirige\complet', 'voxel')]


def reels(images):
    from hstudio.qa import run as R
    out = os.path.join(ROOT, 'docs', 'qa_scene'); os.makedirs(out, exist_ok=True)
    for d, style in REELS:
        if not os.path.exists(os.path.join(d, 'episode.json')): print('absent :', d); continue
        t0 = time.time(); rep = R.verify(d, None, style, images=images and style == 'ps1', workers=6, log=None)
        name = ('chambre313_' if 'CHAMBRE' in d else 'satisfied_') + os.path.basename(d)
        R.write(rep, out, name); c = rep.counts()
        check(f'réel {name} : contrôle complet ({time.time() - t0:.0f} s) — {c["bloquant"]} bloquant(s), {c["a_revoir"]} à revoir', True)


if __name__ == '__main__':
    tmp = tempfile.mkdtemp(prefix='check_qa_')
    try:
        synthetic(tmp)
        gate(tmp)
        if '--reels' in sys.argv: reels('--images' in sys.argv)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = [n for n, ok in RESULTS if not ok]
    print(f'\n{len(RESULTS) - len(bad)} / {len(RESULTS)} OK' + (f' — ÉCHECS : {bad}' if bad else ''))
    sys.exit(1 if bad else 0)
