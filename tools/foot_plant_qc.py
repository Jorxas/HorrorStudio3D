"""Mesure du glissement des semelles sur un acteur temoin, a la marche et a la course.

  python tools/foot_plant_qc.py                           # les six cas temoins, avant/apres
  python tools/foot_plant_qc.py --json docs/mesures/foot_plant.json

Rien n'est rendu : seule la couche de jeu est construite et echantillonnee (quelques secondes, aucun appel API).
L'acteur temoin marche / court en ligne droite, puis dans un virage, avec la MEME vitesse (timeline.SPEEDS) et le
MEME pas de temps (30 i/s) que les demos.

Pourquoi un outil de plus a cote de tools/motion_qc.py et tools/locomotion_qc.py : les trois ne mesurent pas la
meme chose, et c'est tout le sujet.

  locomotion_qc.py   prend "le pied le plus bas des deux" des que le cycle tourne (gait > .5). A la course, le
                     cycle a une PHASE AERIENNE (stance_beta(1) = .35 par pied, donc 2 x .35 = .70 du cycle avec
                     un pied au sol et .30 sans aucun pied au sol) : pendant ces images-la, le "pied le plus bas"
                     est un pied qui vole, et son deplacement est compte comme du glissement. Le nombre obtenu
                     tend donc vers le deplacement moyen du corps, pas vers un defaut d'adherence.
  motion_qc.py       demande au cycle lui-meme si le pied est en appui (in_stance : phase, beta, air, sit). C'est
                     la bonne question, mais elle est posee sur des episodes entiers, ou le pas est noye dans les
                     virages, les arrets et les gestes.
  cet outil          pose la meme question sur un temoin isole, cas par cas, et separe les trois sources :
                     appui en ligne droite / appui pendant une rotation du corps / fin de marche.

Mesures par cas, en cm par image :

glissement appui   deplacement de la semelle (centre de la face inferieure du soulier, repere `foot` du rig) dans
                   le monde entre deux images, UNIQUEMENT quand le cycle dit ce pied en appui, et seulement entre
                   deux images ou il est en appui sans interruption. Un pied plante ne doit pas bouger.
reference corps    deplacement du corps par image, pour que le glissement se lise en proportion.
mesure heritee     le "pied le plus bas tant que gait > .5" de locomotion_qc.py, pour objectiver l'ecart.
phase aerienne     part des images ou le cycle ne met aucun pied en appui (normal a la course, nul a la marche).
semelle y          hauteur de la semelle pendant l'appui : < 0 = penetration du sol, > 0 = pied qui flotte.
"""
import os, sys, json, math, argparse
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from hstudio.acting import rig                                      # noqa: E402
from hstudio.acting import timeline as TL                           # noqa: E402

FPS = 30.
SOLE_Z = .03          # le soulier est dessine en (0, .04, .03) dans le repere `foot` (engines/pixel3d/rigfig.py)


# ------------------------------------------------------------------ le temoin
def control(kind='walk', dist=8., footing=False, corner=False, dur=None, plant=False):
    """un acteur seul qui part de l'origine face a +z et marche / court droit (ou en deux jambes de trajet)"""
    to = [0., dist] if not corner else [dist * .55, dist * .55]
    acts = [{'do': 'walk_to', 'who': 'temoin', 'to': to, 'speed': kind, 'at': .35}]
    if corner: acts.append({'do': 'walk_to', 'who': 'temoin', 'to': [0., dist * 1.1], 'speed': kind})
    shot = {'actors': [{'id': 'temoin', 'at': [0., 0.], 'facing': '+z'}], 'actions': acts}
    v = TL.SPEEDS.get(kind, 1.15)
    dur = dur or (.35 + dist * (1.3 if not corner else 1.9) / v + 1.6)
    sa = TL.ShotActing(shot, TL.World(), {}, [], dur, footing=footing, plant=plant)
    return sa, dur


def sole_world(s, sk):
    """{cote: (x, y, z)} du centre de la semelle dans le monde, tel que le moteur le dessine"""
    R = rig.rot_y(s['heading']); base = np.array([s['x'], float(s.get('y', 0.)), s['z']], np.float32)
    out = {}
    for tag in ('L', 'R'):
        Rf, o = sk.frames['foot' + tag]
        p = base + R @ (np.asarray(o, np.float32) + Rf @ np.array([0., 0., SOLE_Z], np.float32))
        out[tag] = (float(p[0]), float(p[1]), float(p[2]))
    return out


def in_stance(r, tag):
    """le cycle lui-meme : ce pied est-il en appui a cette image ? (meme regle que tools/motion_qc.py)"""
    if r.get('gait', 0.) < .5 or r.get('air', 0.) > .05 or r.get('sit', 0.) > .1: return False
    psi = r['phase'] + (0. if tag == 'R' else math.pi)
    return (psi / (2 * math.pi)) % 1. < rig.stance_beta(r.get('run', 0.))


def sample_run(sa, dur, fps=FPS):
    """[{t, x, z, h, rig, soles, stance}] image par image"""
    out = []
    for i in range(int(dur * fps)):
        t = i / fps
        s = sa.sample(t)['temoin']
        sk = rig.solve(s['rig'])
        out.append(dict(t=t, x=s['x'], z=s['z'], h=s['heading'], rg=s['rig'], soles=sole_world(s, sk),
                        stance={tag: in_stance(s['rig'], tag) for tag in ('L', 'R')}))
    return out


# ------------------------------------------------------------------ les mesures
def measure(frames):
    stance = []; legacy = []; body = []; sole_y = []; flight = 0; moving = 0; turn_rate = []
    for i in range(1, len(frames)):
        r, p = frames[i], frames[i - 1]
        d_body = math.hypot(r['x'] - p['x'], r['z'] - p['z']) * 100
        gait = r['rg'].get('gait', 0.)
        if gait > .5:
            moving += 1
            if not (r['stance']['L'] or r['stance']['R']): flight += 1
            body.append(d_body)
            lo = 'R' if p['soles']['R'][1] <= p['soles']['L'][1] else 'L'       # heuristique heritee
            legacy.append(math.hypot(r['soles'][lo][0] - p['soles'][lo][0], r['soles'][lo][2] - p['soles'][lo][2]) * 100)
        for tag in ('L', 'R'):
            if r['stance'][tag] and p['stance'][tag]:                           # appui ininterrompu entre p et r
                stance.append(math.hypot(r['soles'][tag][0] - p['soles'][tag][0], r['soles'][tag][2] - p['soles'][tag][2]) * 100)
                sole_y.append(r['soles'][tag][1] * 100)
                turn_rate.append(abs(math.degrees(TL.wrap(r['h'] - p['h']))) * FPS)
    f = lambda v, q: (float(np.percentile(v, q)) if v else 0.)
    g = lambda v: (float(np.mean(v)) if v else 0.)
    straight = [s for s, w in zip(stance, turn_rate) if w < 20.]
    rot = [s for s, w in zip(stance, turn_rate) if w >= 20.]
    return dict(
        frames=len(frames), moving=moving,
        body_mean=g(body), body_max=(float(max(body)) if body else 0.),
        stance_frames=len(stance),
        slide_mean=g(stance), slide_p95=f(stance, 95), slide_max=(float(max(stance)) if stance else 0.),
        slide_straight_p95=f(straight, 95), slide_straight_max=(float(max(straight)) if straight else 0.),
        slide_rot_p95=f(rot, 95), slide_rot_max=(float(max(rot)) if rot else 0.), rot_frames=len(rot),
        legacy_mean=g(legacy), legacy_p95=f(legacy, 95), legacy_max=(float(max(legacy)) if legacy else 0.),
        flight_share=(flight / moving if moving else 0.),
        sole_y_min=(float(min(sole_y)) if sole_y else 0.), sole_y_max=(float(max(sole_y)) if sole_y else 0.),
    )


CASES = [
    ('marche droite',   dict(kind='walk', dist=7.)),
    ('marche lente',    dict(kind='slow', dist=5.)),
    ('marche pressee',  dict(kind='hurry', dist=9.)),
    ('course droite',   dict(kind='run',  dist=14.)),
    ('course virage',   dict(kind='run',  dist=12., corner=True)),
    ('marche virage',   dict(kind='walk', dist=7.,  corner=True)),
]


def run_cases(cases=None, **kw):
    out = {}
    for name, c in (cases or CASES):
        sa, dur = control(**dict(c, **kw))
        out[name] = measure(sample_run(sa, dur))
        out[name]['speed'] = TL.SPEEDS.get(c.get('kind', 'walk'), 1.15)
    return out


def show(name, m):
    n = lambda v, k=2: f'{v:.{k}f}'
    print(f'  {name:<22} {m["speed"]:.2f} m/s   corps {n(m["body_mean"])} cm/i (max {n(m["body_max"])})'
          f'   phase aerienne {m["flight_share"] * 100:.0f} %')
    print(f'  {"":<22} glissement APPUI   moyen {n(m["slide_mean"])}  p95 {n(m["slide_p95"])}  max {n(m["slide_max"])} cm/i'
          f'   sur {m["stance_frames"]} images d appui')
    print(f'  {"":<22}   dont ligne droite max {n(m["slide_straight_max"])}'
          f'  |  sous rotation ({m["rot_frames"]} i) max {n(m["slide_rot_max"])}')
    print(f'  {"":<22} mesure heritee (pied le plus bas, gait > .5)  moyen {n(m["legacy_mean"])}  p95 {n(m["legacy_p95"])}'
          f'  max {n(m["legacy_max"])} cm/i')
    print(f'  {"":<22} semelle pendant l appui : de {n(m["sole_y_min"])} a {n(m["sole_y_max"])} cm du sol')


def compare(res_a, res_b):
    """tableau avant / apres sur le seul chiffre qui decrit le defaut : le glissement en appui"""
    print()
    print('  %-22s %22s %22s   %s' % ('cas', 'AVANT (historique)', 'APRES ("foot_plant")', 'gain'))
    print('  %-22s %22s %22s   %s' % ('', 'moyen / p95 / max cm/i', 'moyen / p95 / max cm/i', ''))
    worst_a = worst_b = 0.
    for k in res_a:
        a, b = res_a[k], res_b[k]
        worst_a = max(worst_a, a['slide_max']); worst_b = max(worst_b, b['slide_max'])
        g = ('%.1fx' % (a['slide_max'] / b['slide_max'])) if b['slide_max'] > 1e-6 else 'inf'
        print('  %-22s %7.2f %6.2f %6.2f %7.2f %6.2f %6.2f   max %s' % (
            k, a['slide_mean'], a['slide_p95'], a['slide_max'], b['slide_mean'], b['slide_p95'], b['slide_max'], g))
    print('  %-22s %21.2f %22.2f   max %s' % ('PIRE CAS', worst_a, worst_b,
          ('%.1fx' % (worst_a / worst_b)) if worst_b > 1e-6 else 'inf'))
    return worst_a, worst_b


def scan(kind='run', dists=(3., 4., 5., 6., 7., 8., 9., 10., 11., 12., 13., 14., 16., 18.)):
    """le defaut depend-il d'une distance malheureuse ? max du glissement en appui, avant / apres, par distance"""
    out = {}
    for d in dists:
        a = measure(sample_run(*control(kind=kind, dist=d)))
        b = measure(sample_run(*control(kind=kind, dist=d, plant=True)))
        out[f'{d:g} m'] = {'avant': round(a['slide_max'], 2), 'apres': round(b['slide_max'], 2)}
    return out


def show_scan(kind, sc):
    print(f'  {kind} : glissement en appui (max cm/image) selon la distance parcourue')
    print('    distance ' + ' '.join(f'{k:>7}' for k in sc))
    print('    avant    ' + ' '.join(f"{v['avant']:>7.2f}" for v in sc.values()))
    print('    apres    ' + ' '.join(f"{v['apres']:>7.2f}" for v in sc.values()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', default=None)
    ap.add_argument('--scan', action='store_true', help='balayer la distance parcourue, marche et course')
    a = ap.parse_args()
    print('acteur temoin, %.0f i/s, vitesses de hstudio/acting/timeline.py SPEEDS' % FPS)
    print()
    print('AVANT (comportement historique, aucune option)')
    before = run_cases()
    for name, m in before.items(): show(name, m)
    print()
    print('APRES (episode "foot_plant": true)')
    after = run_cases(plant=True)
    for name, m in after.items(): show(name, m)
    wa, wb = compare(before, after)
    scans = {}
    if a.scan or a.json:
        print()
        for kind in ('run', 'walk'):
            scans[kind] = scan(kind, (3., 4., 5., 6., 7., 8., 9., 10., 12., 14., 18.) if kind == 'run'
                               else (3., 4., 5., 6., 7., 8., 9., 10.))
            show_scan(kind, scans[kind])
    if a.json:
        os.makedirs(os.path.dirname(a.json) or '.', exist_ok=True)
        json.dump({'fps': FPS, 'avant': before, 'apres': after, 'balayage_distance': scans,
                   'pire_appui_avant_cm_par_image': wa, 'pire_appui_apres_cm_par_image': wb},
                  open(a.json, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
        print('->', a.json)


if __name__ == '__main__':
    main()
