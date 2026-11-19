"""Tests hors ligne du KIT HISTOIRE (hstudio/histoire, hstudio/audio/fabriques.py) : aucun rendu, aucun réseau, aucune voix.

    python tools/check_histoire.py

Couvre : lecture de script.txt (parties de rythme, « # coupe », vitesses), caméra qui cadre (hauteur couverte exacte
dans les deux formats), découpe en Shorts (moins de parties, équilibrées, refus expliqué), sons fabriqués (déterministes,
indépendants de l'ordre d'appel, absents de synth.SFX), construction complète du modèle `nouveau` sur des phrases
synthétiques (versions, titres, étiquettes PARTIE, phrases contiguës), contrôles du kit sans le contrôle de scène."""
import io
import json
import math
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np

OK = []; BAD = []


def check(name, cond, detail=''):
    (OK if cond else BAD).append(name)
    print(('  ok   ' if cond else '  ÉCHEC ') + name + (f'  ({detail})' if detail and not cond else ''))


def t_script(tmp):
    from hstudio.histoire import script as SC
    from hstudio.histoire.common import KitError
    p = os.path.join(tmp, 'script.txt')
    open(p, 'w', encoding='utf-8').write('# commentaire\n# rythme debut 1.06\n[serious]\nUne.\n\nDeux.\n# coupe\n[whispers]\nTrois.\n# rythme vite 1.13\n[urgent]\nQuatre [softly] encore.\n')
    sc = SC.parse(p)
    check('script : 4 phrases, 2 parties de rythme', len(sc['phrases']) == 4 and [x['name'] for x in sc['parts']] == ['debut', 'vite'])
    check('script : « # coupe » sur la phrase suivante seulement', [x['coupe'] for x in sc['phrases']] == [False, False, True, False])
    check('script : ton et balise en ligne retirée du texte', sc['phrases'][2]['tone'] == 'whispers' and sc['phrases'][3]['text'] == 'Quatre encore.')
    check('script : les commentaires ne sont pas envoyés', all('#' not in x['text'] for x in sc['parts']))
    open(p, 'w', encoding='utf-8').write('# rythme trop 1.5\nUne.\n')
    try: SC.parse(p); check('script : vitesse hors limites refusée', False)
    except KitError: check('script : vitesse hors limites refusée', True)


def t_frame():
    from hstudio.histoire import lib
    for asp in ('16:9', '9:16'):
        F = lib.Film(asp)
        for H, f35 in ((1.0, 50), (1.8, 28), (3.0, 35)):
            t, pos, look, fov, kw = F.frame(0., (0., 1.6, 5.), H, f35, look_yaw=0., el=0.)
            d = math.dist(pos, look); cov = lib.covered_height(d, fov, asp)
            check(f'frame {asp} H={H} f35={f35} : hauteur couverte exacte', abs(cov - H) < .01 * H, f'{cov:.3f}')
        t, pos, look, fov, kw = F.frame(0., (0., 1.6, 5.), 1., 35, facing=lib.PI, angle=0., el=0.)
        check(f'frame {asp} : devant un sujet qui regarde vers -z, la caméra est à -z', pos[2] < 5. and abs(pos[0]) < 1e-6)
        t, pos, look, fov, kw = F.frame(0., (0., 1.6, 5.), 1., 35, facing=0., angle=30., el=0.)
        check(f'frame {asp} : angle + = côté droit du sujet (+x quand il regarde vers +z)', pos[0] > 0 and pos[2] > 5.)


def t_cuts():
    from hstudio.histoire import projet as PJ
    from hstudio.histoire.common import KitError
    lines = [dict(start=i * 10. + .1, end=i * 10. + 8., text=f'p{i}') for i in range(40)]      # 40 phrases, 400 s
    D = lines[-1]['end'] + 1.4
    check('sans limite : récit entier malgré les marques de coupe', PJ.choose_cuts(lines, list(range(1, 40)), D, 0) == [])
    check('sans limite : None accepte aussi un récit long sans marques', PJ.choose_cuts(lines, [], 36000., None) == [])
    cuts = PJ.choose_cuts(lines, list(range(1, 40)), D, 180.)
    bounds = [0] + cuts + [40]
    durs = [(D if b >= 40 else min(lines[b - 1]['end'] + 1., lines[b]['start'] - .03)) - (0. if a == 0 else lines[a]['start'] - .12) for a, b in zip(bounds, bounds[1:])]
    check('découpe : 3 parties pour 400 s (le minimum)', len(durs) == 3, str(durs))
    check('découpe : chaque partie ≤ 180 s', max(durs) <= 180.)
    check('découpe : équilibrée (écart ≤ 20 s)', max(durs) - min(durs) <= 20., str([round(d) for d in durs]))
    check('découpe : rien à couper sous 180 s', PJ.choose_cuts(lines[:10], [3, 6], lines[9]['end'] + 1.4, 180.) == [])
    try: PJ.choose_cuts(lines, [5], D, 180.); check('découpe impossible : refus expliqué', False)
    except KitError as e: check('découpe impossible : refus expliqué', '# coupe' in str(e))


def t_sounds():
    from hstudio.audio import fabriques as FB, synth as S
    a1 = {k: FB.make(k, 3.) for k in FB.SOUNDS}
    for k in reversed(list(FB.SOUNDS)): FB.make(k, 2.)
    S.reseed(999); _ = S.noise(1000)                                          # disturb the shared generator
    a2 = {k: FB.make(k, 3.) for k in reversed(list(FB.SOUNDS))}
    check('sons fabriqués : déterministes et indépendants de l\'ordre d\'appel', all(np.array_equal(a1[k], a2[k]) for k in FB.SOUNDS))
    check('sons fabriqués : finis, non muets', all(np.isfinite(a).all() and np.abs(a).max() > 1e-3 for a in a1.values()))
    check('sons fabriqués : nappes à la durée demandée', all(abs(len(a1[k]) / FB.SR - 3.) < .01 for k, v in FB.SOUNDS.items() if v['kind'] == 'bed'))
    check('sons fabriqués : absents de synth.SFX (aucun épisode existant ne change)', not any(k in S.SFX for k in FB.SOUNDS))
    check('sons fabriqués : anciens noms de Chambre 313 acceptés', all(FB.has(k) for k in ('alarm', 'siren', 'hum', 'wind', 'cough')))


def t_build(tmp):
    from hstudio.histoire import cli, projet as PJ, verif as VF
    from hstudio.histoire.common import Story, write_json, read_json
    d = os.path.join(tmp, 'HISTOIRE_TEST')
    with redirect_stdout(io.StringIO()): cli.nouveau(d, 'LE TEST')
    st = Story(d)
    check('nouveau : script, histoire.py, voix.json, dossiers', all(os.path.exists(p) for p in (st.script, st.histoire, st.voix_json, st.voix, st.livraison)))
    lines = []; t = .1
    for i in range(30):
        lines.append(dict(start=round(t, 3), end=round(t + 7., 3), text=f'Phrase numéro {i}.', tone='serious', part='debut', coupe=i in (9, 19), speaker='narrateur')); t += 7.5
    write_json(st.lignes, lines)
    with redirect_stdout(io.StringIO()): dec, mod = PJ.build(d, print)
    default_parts = [v for v in dec['versions'] if v['id'].startswith('partie')]
    check('nouveau : durée illimitée, récit entier au-delà de 3 min', dec['partie_max'] == 0 and len(default_parts) == 1 and default_parts[0]['lines'] == [0, 29] and default_parts[0]['dur'] > 180 and not default_parts[0]['label'])
    with redirect_stdout(io.StringIO()): unlimited_check = VF.check(d, scene=False, log=print)
    check('vérifier : récit entier de plus de 3 min accepté', not unlimited_check['erreurs'])
    # Retain coverage of explicit caps for the exceptional, deliberately requested split.
    src = open(st.histoire, encoding='utf-8').read()
    open(st.histoire, 'w', encoding='utf-8').write(src.replace('PARTIE_MAX = 0 ', 'PARTIE_MAX = 180 '))
    with redirect_stdout(io.StringIO()): dec, mod = PJ.build(d, print)
    ids = [v['id'] for v in dec['versions']]
    check('construire : long 16:9, vertical complet, Shorts', ids[:2] == ['long_16x9', 'complet_9x16'] and any(i.startswith('partie') for i in ids), str(ids))
    parts = [v for v in dec['versions'] if v['id'].startswith('partie')]
    check('construire : Shorts ≤ 180 s, coupés sur les « # coupe »', all(v['dur'] <= 180 for v in parts) and all(v['lines'][0] in (0, 9, 19) for v in parts))
    check('construire : phrases contiguës d\'une partie à l\'autre', all(a['lines'][1] + 1 == b['lines'][0] for a, b in zip(parts, parts[1:])) and parts[-1]['lines'][1] == 29)
    eps = {v['id']: read_json(os.path.join(st.version_dir(v['id']), 'episode.json')) for v in dec['versions']}
    check('construire : titre unique partout', {e['title'] for e in eps.values()} == {'LE TEST'})
    check('construire : pas de PARTIE sur le film long, PARTIE N sur les Shorts', eps['long_16x9']['hud']['part'] == '' and all(eps[v['id']]['hud']['part'] == f'PARTIE {k}' for k, v in enumerate(parts, 1)))
    l2 = read_json(os.path.join(st.version_dir(parts[1]['id']), 'lines.json'))
    check('construire : phrases d\'une partie recalées sur son début', abs(l2[0]['start'] - .12) < 1e-6)
    with redirect_stdout(io.StringIO()): out = VF.check(d, scene=False, log=print)
    check('vérifier : le modèle passe sans erreur', not out['erreurs'], str(out['erreurs'][:3]))
    with redirect_stdout(io.StringIO()): dec2, _ = PJ.build(d, print)
    check('construire : déterministe (même découpe deux fois)', json.dumps(dec2, sort_keys=True) == json.dumps(dec, sort_keys=True))
    check('construire PS1 : ni « lipsync » ni « mood » (rien de VOXEL dans un épisode PS1)', all('lipsync' not in e and 'mood' not in e for e in eps.values()))
    src = open(st.histoire, encoding='utf-8').read(); open(st.histoire, 'w', encoding='utf-8').write(src.replace("STYLE = 'ps1'", "STYLE = 'voxel'"))
    with redirect_stdout(io.StringIO()): dec3, _ = PJ.build(d, print)
    p2 = [v for v in dec3['versions'] if v['id'] == 'partie2_9x16'][0]; e2 = read_json(os.path.join(st.version_dir('partie2_9x16'), 'episode.json'))
    check('construire VOXEL : mood neutre (pas tout rouge) et voix de la bouche décalée du début du Short',
          e2.get('mood') == 'neutral' and abs(e2['lipsync']['offset'] + p2['t0']) < 1e-6 and e2['lipsync']['wav'].endswith('voix.mp3'))


def main():
    tmp = tempfile.mkdtemp(prefix='check_histoire_')
    try:
        print('script.txt'); t_script(tmp)
        print('caméra qui cadre'); t_frame()
        print('découpe en Shorts'); t_cuts()
        print('sons fabriqués'); t_sounds()
        print('construction et vérification'); t_build(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f'\n{len(OK)} contrôles réussis, {len(BAD)} échec(s)')
    sys.exit(1 if BAD else 0)


if __name__ == '__main__':
    main()
