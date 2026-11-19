"""python tools/check_remake.py [--gpu]  -> tests of what the two remakes added to the unified studio. No API, no network, no source video needed
(the checks that read the source video are skipped, and said so, when it is absent). `--gpu` adds the micro-renders on the GPU (four new worlds, props, figures,
UI layer) with determinism and non-black checks.

What is tested: direct tracks (keyframes, cut, holds, determinism), prop sets and their errors, the camera `path` rig with `look: {on: actor}`, the JS kit's
registries read from the source file (worlds, props, figures) against the Python side, both film modules (cut frames, durations that add up to the source's,
HUD / cards / captions inside the film, no reuse of source pictures: no image path anywhere in the scene files), tools/remake_* syntax."""
import argparse, hashlib, json, math, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu import director, worlds, contract as C
from hstudio.voxelgpu.tracks import TrackActing
from hstudio.remake import dsl

BAD = []


def check(name, ok, detail=''):
    print(('OK   ' if ok else 'FAIL ') + name + (f' : {detail}' if detail else '')); ok or BAD.append(name)


def tests():
    # ---- direct tracks
    ta = TrackActing({'tracks': {'a': [dict(t=0, p=[0, 0, 0], yaw=0, face='neutral'), dict(t=2, p=[2, 0, 0], yaw=math.pi, face='scared', gesture='point', gw=1), dict(t=3, p=[2, 0, 0], cut=True)]}}, 4., {})
    s0, s1, s2 = ta.sample(0)['a'], ta.sample(1.)['a'], ta.sample(2.5)['a']
    check('tracks : position glisse entre deux clés (smoothstep, milieu = milieu)', abs(s1['x'] - 1.) < 1e-9 and s0['x'] == 0.)
    check('tracks : les noms (visage, geste) tiennent jusqu\'à la clé qui les change', s0['face'] == 'neutral' and s1['face'] == 'neutral' and s2['face'] == 'scared')
    ta2 = TrackActing({'tracks': {'a': [dict(t=0, p=[0, 0, 0], yaw=3.0), dict(t=1, p=[0, 0, 0], yaw=-3.0)]}}, 2., {})
    check('tracks : le cap tourne par le plus court chemin (3,0 -> -3,0 passe par pi)', abs(abs(ta2.sample(.5)['a']['heading']) - math.pi) < .01)
    ta3 = TrackActing({'tracks': {'a': [dict(t=0, p=[0, 0, 0]), dict(t=1, p=[5, 0, 0], cut=True)]}}, 2., {})
    check('tracks : `cut` fait sauter la position au lieu de la faire glisser', ta3.sample(.5)['a']['x'] == 0. and ta3.sample(1.)['a']['x'] == 5.)
    check('tracks : déterministe', json.dumps(ta.sample(1.3), sort_keys=True) == json.dumps(TrackActing({'tracks': {'a': ta.keys['a']}}, 4., {}).sample(1.3), sort_keys=True))
    try: TrackActing({'tracks': {'a': [dict(t=0)]}}, 1., {}); check('tracks : refuse une première clé sans position', False)
    except ValueError as e: check('tracks : refuse une première clé sans position (en français)', 'position' in str(e))
    # ---- prop sets and camera path
    check('prop_sets : un jeu se déroule, y compris imbriqué', director._expand_props([{'use': 'a'}, {'type': 'sign'}], {'a': [{'use': 'b'}], 'b': [{'type': 'tube'}]}) == [{'type': 'tube'}, {'type': 'sign'}])
    try: director._expand_props([{'use': 'zzz'}], {}); check('prop_sets : un jeu inconnu est refusé', False)
    except ValueError as e: check('prop_sets : un jeu inconnu est refusé, nommé, en français', 'zzz' in str(e) and 'inconnu' in str(e))
    ep = {'fps': 30, 'casts': {'x': {'preset': 'npc'}}, 'shots': [{'id': 'a', 'stage': 'station', 'dur': 1.0, 'tracks': {'x': dsl.hold([0, 0, 0], 0.)}, 'env': {'rain': 1}, 'props': [{'type': 'sign', 'text': 'T'}],
          'camera': dsl.cam(dsl.k(0, [0, 1.5, 5], {'on': 'x', 'h': 1.6}, 50), dsl.k(1., [1, 1.5, 5], {'on': 'x', 'h': 1.6}, 50))}]}
    c = director.build(ep, '9:16', 30); st = c['stages'][0]
    check('contrat : une piste directe donne une ligne par image et la caméra regarde l\'acteur (look {on})', len(st['camera']) >= 30 and abs(st['camera'][0][3] - 0.) < 1e-6 and abs(st['camera'][0][4] - 1.6) < 1e-6)
    check('contrat : env, props passent au peintre', st.get('env') == {'rain': 1} and st['props'][0]['type'] == 'sign')
    check('contrat : le monde station existe côté B', 'station' in worlds.WORLDS and 'bus' in worlds.WORLDS and 'toit' in worlds.WORLDS and 'talus' in worlds.WORLDS)
    # ---- the JS kit's registries
    js = (ROOT / 'voxelgpu_js/engine/horror_kit.js').read_text(encoding='utf-8')
    props = set(re.findall(r"^  (\w+): \(p\) =>", js, re.M)); check('kit JS : catalogue d\'accessoires lu dans le fichier', {'sign', 'poster_plan', 'breaker_box', 'door', 'alarm_button', 'price_sign', 'tube', 'hand', 'mirror_eyes', 'room', 'boxes'} <= props, str(sorted(props)))
    check('kit JS : figures faceless / creature et objets attachés (extras)', all(k in js for k in ('buildFaceless', 'buildCreature', 'buildExtras')))
    from hstudio.voxelgpu.films import remake_pompe as RP, remake_sol as RS
    used = set()
    for M in (RP, RS):
        e = M.episode()
        for sh in e['shots']:
            for p in director._expand_props(sh.get('props') or [], e.get('prop_sets') or {}): used.add(p['type'])
    check('films : tous les accessoires utilisés existent dans le kit', used <= props, f'{sorted(used - props)}')
    # ---- the two films
    for M, name, ncuts, dur in ((RP, 'pompe', 44, 2894 / 30), (RS, 'sol', 40, 3043 / 30)):
        e = M.episode(); sh = e['shots']; tot = sum(s['dur'] for s in sh)
        check(f'{name} : {ncuts} plans, durée = celle de la source ({dur:.3f} s)', len(sh) == ncuts and abs(tot - dur) < 1e-2, f'{len(sh)} plans, somme {tot:.4f}')
        starts = [round(sum(s['dur'] for s in sh[:i]) * 30) for i in range(len(sh))]
        check(f'{name} : chaque coupe tombe sur l\'image mesurée dans la source', starts == M.CUTS[:-1], f'écarts : {[(a, b) for a, b in zip(starts, M.CUTS) if a != b][:4]}')
        cc = director.build(e, '9:16', 30); probs = C.validate(cc)
        check(f'{name} : contrat valide, {len(cc["stages"])} plans, durée {cc["duration"]:.3f}', not probs and abs(cc['duration'] - dur) < 1e-2, str(probs[:2]))
        check(f'{name} : les mondes demandés existent', all(s['world'] in worlds.WORLDS for s in cc['stages']))
        txt = json.dumps(e, ensure_ascii=False)
        check(f'{name} : aucune image ni vidéo de la source dans la scène (pas de chemin .png/.jpg/.mp4 hors `audio.source`)', not re.search(r'\.(png|jpe?g|webp)\b', txt) and txt.count('.mp4') == 1, str(re.findall(r'[\w./-]+\.mp4', txt)))
        caps = e.get('captions') or []
        if caps:
            ok = all(c['t1'] > c['t0'] and c['t0'] >= 0 and c['t1'] <= dur + 1e-6 for c in caps) and all(caps[i]['t0'] >= caps[i - 1]['t0'] for i in range(1, len(caps)))
            check(f'{name} : {len(caps)} légendes ordonnées, dans la durée du film', ok)
        else: check(f'{name} : légendes présentes (examples/remakes/{name}_captions.json)', False, 'absentes')
        h = e['hud']; check(f'{name} : HUD (titre, horloge, pile/cœurs) et cartes dans la durée', h['title'] and h['corner']['clock'] and all(c['t0'] >= 0 and c['t1'] <= dur + 1e-6 for c in e['cards']))
    src = ROOT / 'projects/remakes_voxelgpu_20261029/source'
    if src.exists():
        for n, f, sha in (('pompe', 'pompe/LA_DERNIERE_POMPE_partie1_sans_miniature.mp4', '4880b9bfa1b69f2451c7c94711b10917b1761a5eca8cd05bafc8d15d026856b7'), ('sol', 'sol/NE_TOUCHE_PAS_LE_SOL_partie4.mp4', '4bfe08170821c7068f1e24a78da6983a779165c00c13b2b46ebd82de44c760c4')):
            check(f'source {n} : empreinte SHA-256 inchangée', hashlib.sha256((src / f).read_bytes()).hexdigest() == sha)
    else: print('SKIP sources absentes : empreintes non vérifiées')
    # the original engines stay as they were (frozen manifests are checked by tools/check_voxelgpu.py)
    for f in ('tools/remake_film.py', 'tools/remake_stills.py', 'tools/remake_calibrate.py', 'tools/read_subtitles.py'):
        try: compile((ROOT / f).read_text(encoding='utf-8'), f, 'exec'); check(f'{f} : compile', True)
        except SyntaxError as e: check(f'{f} : compile', False, str(e))


def gpu_tests():
    import subprocess, tempfile
    from hstudio.voxelgpu import render
    from PIL import Image
    import numpy as np
    ep = {'fps': 30, 'casts': {'clerk': {'preset': 'npc', 'extras': [{'bone': 'torso', 'boxes': [{'x': 0, 'y': 3, 'z': 0, 'w': 8.5, 'h': 1, 'd': 4.5, 'color': '#d8e2c8'}]}]}, 'ghost': {'preset': 'npc', 'kind': 'faceless'}, 'cr': {'preset': 'npc', 'kind': 'creature'}},
          'prop_sets': {'p': [{'type': 'sign', 'text': 'OK', 'at': [0, 1.5, 1], 'w': .6, 'h': .3}]},
          'shots': [{'id': 'st', 'stage': 'station', 'dur': 1., 'env': {'rain': 1}, 'camera': dsl.cam(dsl.k(0, [-1, 1.5, 2.5], [2.5, 1.2, .5], 62)), 'tracks': {'clerk': dsl.hold([2.4, 0, .9], 1.5708), 'ghost': dsl.hold([0, 0, 8.], 3.14)}, 'props': [{'use': 'p'}]},
                    {'id': 'bu', 'stage': 'bus', 'dur': 1., 'env': {'red': .4}, 'camera': dsl.cam(dsl.k(0, [0, 1.5, -5], [0, 1.4, -9], 52)), 'tracks': {'cr': dsl.hold([0, 0, -8.5], 0.)}},
                    {'id': 'to', 'stage': 'toit', 'dur': 1., 'camera': dsl.cam(dsl.k(0, [-1.5, 2.8, 4], [1.8, .2, .2], 56)), 'tracks': {'clerk': dsl.hold([1.6, 0, .6], 0.)}},
                    {'id': 'ta', 'stage': 'talus', 'dur': 1., 'camera': dsl.cam(dsl.k(0, [4, 1.8, 14], [0, 1.2, -6], 50)), 'tracks': {'clerk': dsl.hold([2, 0, 3], 0.)}}],
          'hud': {'x': .04, 'title': [{'text': 'TEST', 'color': '#fff', 'cw': .04, 'y': .035}], 'corner': {'clock': [{'t': 0, 'text': '00:00'}], 'battery': [{'t': 0, 'bars': 2}]}},
          'captions': [{'t0': 0, 't1': 4, 'text': 'UN DEUX', 'words': [['UN', False], ['DEUX', True]]}]}
    c = director.build(ep, '9:16', 30); tmp = Path(tempfile.mkdtemp()); C.save(c, tmp / 'c.json'); times = [.5, 1.5, 2.5, 3.5]
    for rep in (1, 2): render.run_painter(tmp / 'c.json', None, 'nvidia', (270, 480), stills=times, stills_dir=tmp / f's{rep}', quiet=True)
    for t, nm in zip(times, ('station', 'bus', 'toit', 'talus')):
        a = tmp / 's1' / f't_{t:.2f}.png'; b = tmp / 's2' / f't_{t:.2f}.png'; im = np.asarray(Image.open(a).convert('L'), float)
        check(f'GPU : monde {nm} : image non noire (moyenne {im.mean():.0f}) et déterministe (deux rendus identiques)', im.mean() > 6 and a.read_bytes() == b.read_bytes())


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--gpu', action='store_true'); a = ap.parse_args(); tests()
    if a.gpu: gpu_tests()
    print(f"\n{'TOUT EST OK' if not BAD else 'ÉCHECS : ' + str(BAD)}"); sys.exit(1 if BAD else 0)
