"""python tools/check_shot_preview.py [--render]

Contrôle de l'aperçu d'un plan (hstudio/shot_preview.py). Sans option : tout ce qui ne demande ni GPU ni rendu (le patch est pur) ; --render rend un vrai clip par style
(PS1, VOXEL, Console 2D) sur des projets existants et le mesure. Sort 1 au premier écart."""
import copy, json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT)); os.environ.setdefault('PYTHONUTF8', '1')
from hstudio import shot_preview as SP

FAILS = []


def check(name, cond, detail=''):
    print(('  ok   ' if cond else '  FAIL ') + name + ('' if cond else f'  -> {detail}'))
    if not cond: FAILS.append(name)


def raises(fn, text):
    try: fn()
    except ValueError as e: return text in str(e)
    return False


def acted():
    return {'engine_version': 2, 'cast': {'lea': {}, 'tom': {}}, 'shots': [
        {'camera': {'shot': 'wide', 'on': ['lea']}, 'actors': [{'id': 'lea', 'at': [0, 0], 'face': 'neutral'}, {'id': 'tom', 'at': [1, 1]}], 'lines': [0, 0]},
        {'camera': {'shot': 'medium', 'on': ['lea'], 'move': 'dolly_in'}, 'actors': [], 'lines': [1, 1]},
        {'camera': {'shot': 'close', 'on': ['tom']}, 'actors': [{'id': 'tom', 'face': 'sad'}], 'lines': [2, 2], 'fx': {'fade_out': 1.0}}]}


def classic():
    return {'cast': {'lea': {}}, 'shots': [{'camera': {'preset': 'wide'}, 'actors': [{'id': 'lea', 'at': [0, 0]}], 'lines': [0, 0]},
                                           {'camera': {'preset': 'medium', 'subject': 'lea', 'move': 'push_in'}, 'actors': [{'id': 'lea', 'face': 'sad'}], 'lines': [1, 1]},
                                           {'camera': {'preset': 'wide'}, 'actors': [], 'lines': [2, 2]}]}


def console():
    return {'style': 'console', 'shots': [{'camera': {'move': 'push_in'}, 'actors': [{'id': 'noah', 'face': 'tired'}], 'lines': [0, 0]}, {'camera': {}, 'lines': [1, 1]}]}


def main():
    print('options par style')
    for st in SP.STYLES:
        o = SP.options(st)
        check(f'{st} : transitions = coupe, fondu, flash', [t[0] for t in o['transitions']] == ['cut', 'fade', 'flash'])
        check(f'{st} : expressions non vides et traduites', o['faces'] and all(f[1] for f in o['faces']))
    check('console : cadrages = zoom 3 niveaux', [s[0] for s in SP.options('console')['sizes']] == ['wide', 'medium', 'close'])
    check('PS1 et VOXEL proposent exactement les mêmes expressions', SP.options('ps1')['faces'] == SP.options('voxel')['faces'])
    check('style inconnu refusé', raises(lambda: SP.options('blender'), 'Style inconnu'))

    print('apply_patch : ne touche pas à l\'original')
    ep = acted(); keep = copy.deepcopy(ep)
    out = SP.apply_patch(ep, 1, {'camera': {'shot': 'close', 'move': 'dolly_out'}, 'transition': 'fade'}, 'ps1')
    check('original intact', ep == keep)
    check('cadrage + mouvement écrits (mise en scène)', out['shots'][1]['camera']['shot'] == 'close' and out['shots'][1]['camera']['move'] == 'dolly_out')
    check('fondu : fade_in ce plan + fade_out plan précédent', out['shots'][1]['fx'] == {'fade_in': SP.FADE_S} and out['shots'][0]['fx'] == {'fade_out': SP.FADE_S})
    out2 = SP.apply_patch(out, 1, {'transition': 'cut'}, 'ps1')
    check('coupe retire le fondu des deux plans', 'fx' not in out2['shots'][1] and 'fx' not in out2['shots'][0])
    out3 = SP.apply_patch(ep, 2, {'transition': 'flash'}, 'voxel')
    check('flash remplace sans casser les autres effets (fade_out du plan gardé)', out3['shots'][2]['fx'] == {'fade_out': 1.0, 'flash': SP.FLASH})
    check('mouvement static retire la clé', 'move' not in SP.apply_patch(ep, 1, {'camera': {'move': 'static'}}, 'ps1')['shots'][1]['camera'])
    check('cadrage seul : mouvement inchangé', SP.apply_patch(ep, 1, {'camera': {'shot': 'wide'}}, 'ps1')['shots'][1]['camera']['move'] == 'dolly_in')
    p = SP.apply_patch(ep, 1, {'actors': [{'id': 'lea', 'face': 'scared'}]}, 'ps1')
    check('expression d\'un personnage déjà en scène : ajoutée au plan', p['shots'][1]['actors'] == [{'id': 'lea', 'face': 'scared'}])
    check('même patch : même résultat (aperçu = validation)', json.dumps(p, sort_keys=True) == json.dumps(SP.apply_patch(ep, 1, {'actors': [{'id': 'lea', 'face': 'scared'}]}, 'ps1'), sort_keys=True))
    check('personnage inconnu refusé', raises(lambda: SP.apply_patch(ep, 1, {'actors': [{'id': 'zoe', 'face': 'sad'}]}, 'ps1'), 'n\'est pas dans ce plan'))
    check('expression inconnue refusée', raises(lambda: SP.apply_patch(ep, 1, {'actors': [{'id': 'lea', 'face': 'xxx'}]}, 'ps1'), 'indisponible'))
    check('plan inexistant refusé', raises(lambda: SP.apply_patch(ep, 9, {}, 'ps1'), "n'existe pas"))
    check('réglage inconnu refusé', raises(lambda: SP.apply_patch(ep, 1, {'volume': 3}, 'ps1'), 'inconnu'))
    check('note enregistrée puis retirée', SP.apply_patch(ep, 0, {'note': ' bien '}, 'ps1')['shots'][0]['note'] == 'bien' and 'note' not in SP.apply_patch(SP.apply_patch(ep, 0, {'note': 'x'}, 'ps1'), 0, {'note': ''}, 'ps1')['shots'][0])
    d = acted(); d['shots'][1]['camera'] = {'rig': 'path', 'keys': [1]}
    check('caméra écrite à la main : pas de réglage de caméra', raises(lambda: SP.apply_patch(d, 1, {'camera': {'move': 'dolly_in'}}, 'ps1'), 'écrite à la main'))
    check('...mais l\'expression et la transition restent possibles', SP.apply_patch(d, 1, {'actors': [{'id': 'lea', 'face': 'sad'}], 'transition': 'flash'}, 'ps1')['shots'][1]['fx']['flash'])

    print('anciens épisodes PS1 (preset)')
    c = classic(); o = SP.options('ps1', c, 1)
    check('vocabulaire propre aux anciens épisodes', o['mode'] == 'classic' and 'closeup' in [s[0] for s in o['sizes']] and 'two_shot' not in [s[0] for s in o['sizes']])
    q = SP.apply_patch(c, 1, {'camera': {'shot': 'closeup', 'move': 'dolly_in'}}, 'ps1')['shots'][1]['camera']
    check('écrit `preset` (pas `shot`, que ces épisodes ignorent)', q.get('preset') == 'closeup' and 'shot' not in q and q['move'] == 'dolly_in', q)
    check('cadrage sans personnage cadré refusé', raises(lambda: SP.apply_patch(c, 2, {'camera': {'shot': 'closeup'}}, 'ps1'), 'personnage cadré'))
    check('"dialogue" n\'existe pas dans ces épisodes', raises(lambda: SP.apply_patch(c, 1, {'camera': {'shot': 'dialogue'}}, 'ps1'), 'indisponible'))
    check('expression seulement pour les personnages du plan', raises(lambda: SP.apply_patch(c, 2, {'actors': [{'id': 'lea', 'face': 'sad'}]}, 'ps1'), "n'est pas dans ce plan"))
    cur = SP.current(c, 1, 'ps1')
    check('current : classique', cur['mode'] == 'classic' and cur['size'] == 'medium' and cur['move'] == 'push_in' and cur['faces'] == {'lea': 'sad'}, cur)

    print('Console 2D')
    k = console(); o = SP.options('console', k, 0)
    check('mode console', o['mode'] == 'console' and 'dolly_in' not in [m[0] for m in o['moves']])
    q = SP.apply_patch(k, 1, {'camera': {'shot': 'close', 'move': 'static'}, 'actors': [{'id': 'noah', 'face': 'happy'}] if False else []}, 'console')['shots'][1]['camera']
    check('zoom + mouvement fixe EXPLICITE (sinon le moteur dérive)', q == {'zoom': SP.ZOOM['close'], 'move': 'static'}, q)
    check('mouvement 3D refusé en console', raises(lambda: SP.apply_patch(k, 0, {'camera': {'move': 'dolly_in'}}, 'console'), 'indisponible'))
    check('current console', SP.current(k, 0, 'console')['move'] == 'push_in' and SP.current(k, 1, 'console')['move'] == 'drift')

    print('traduction des transitions pour VOXEL')
    c0 = {'stages': [{'id': '00_room', 't0': 0., 't1': 2.}, {'id': '01_room_0', 't0': 2., 't1': 3.}, {'id': '01_room_1', 't0': 3., 't1': 4.}, {'id': '02_room', 't0': 4., 't1': 6.}]}
    e = {'shots': [{'fx': {'fade_out': .5}}, {'fx': {'fade_in': .5}}, {'fx': {'flash': .8}}]}
    r = SP.apply_to_contract(c0, e)
    ev = r['fx']
    check('fondu entrant au début du plan, sortant à sa fin, flash au début', ev[0] == {'type': 'fade', 't0': 1.5, 't1': 2., 'from': 1., 'to': 0.} and ev[1]['t0'] == 2. and ev[1]['to'] == 1. and ev[2]['type'] == 'flash' and ev[2]['t0'] == 4., ev)
    check('un plan en plusieurs tranches : fenêtre du plan entier', ev[1]['t1'] == 2.5)
    check('sans effet de plan : contrat renvoyé tel quel', SP.apply_to_contract(c0, {'shots': [{}, {}, {}]}) is c0)
    check('étapes sans numéro de plan : on ne devine pas', SP.apply_to_contract({'stages': [{'id': 'a', 't0': 0, 't1': 1}]}, e) == {'stages': [{'id': 'a', 't0': 0, 't1': 1}]})

    if '--render' in sys.argv: render_checks()
    print('\n' + ('TOUT PASSE' if not FAILS else f'{len(FAILS)} ÉCART(S) : ' + ', '.join(FAILS)))
    sys.exit(1 if FAILS else 0)


def render_checks():
    import subprocess
    print('rendus réels')
    from hstudio import pipeline as P
    for slug, idx, patch in (('demo2_dialogue', 2, {'camera': {'shot': 'close', 'move': 'dolly_in'}, 'transition': 'fade'}),
                              ('demo5_console', 2, {'camera': {'shot': 'close', 'move': 'pull_out'}, 'transition': 'flash'}),
                              ('test_moteur_v4', 2, {'camera': {'move': 'dolly_in'}, 'transition': 'fade'})):
        if not P.Project(slug).meta: print(f'  (projet {slug} absent : ignoré)'); continue
        r = SP.render_shot_clip(slug, idx, patch, '9:16', 3., progress=None, log=lambda m: None)
        f = os.path.join(P.Project(slug).dir, r['file'])
        check(f'{slug} : clip lisible', os.path.exists(f) and r['seconds'] > 1.5 and r['size'][1] >= 270, r)
        again = SP.render_shot_clip(slug, idx, patch, '9:16', 3.)
        check(f'{slug} : deuxième appel identique = cache', again['cached'] and again['file'] == r['file'])
        print(f'    {r["style"]}  {r["seconds"]} s  {r["size"]}  rendu en {r["elapsed"]} s')


if __name__ == '__main__': main()
