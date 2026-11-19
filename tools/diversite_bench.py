"""python tools/diversite_bench.py [--n 5] : le COÛT de la diversité des décors, en millisecondes par image PS1 (médiane de n rendus chauds, rendus entrelacés).

Trois colonnes par scène, même caméra, même image :
  livré       aucun profil : le lieu d'avant le chantier
  production  `profile: production` AVEC `diversite: false` : l'état d'avant le chantier pour un épisode neuf (façades riches, etc.)
  diversite   `profile: production` : quartiers à identité et intérieurs à palette
Le coût d'une image PS1 est proportionnel au nombre de boîtes que les rayons rencontrent ; la colonne `boîtes` le dit. Le rendu VOXEL est un rendu GPU : son coût ne dépend pas
(à cette échelle) du nombre de boîtes, voir tools/bench_voxelgpu.py."""
import argparse, json, statistics, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))

STREET = ([0, 1.7, 1], [0, 2.5, 25])
SCENES = {
    'rue de jour':  ({'type': 'city_street', 'sky': 'day'},   STREET, {'quartier': 0}),
    'rue de nuit':  ({'type': 'city_street', 'sky': 'night'}, STREET, {'quartier': 7}),
    'quartier pastel': ({'type': 'city_street', 'sky': 'day'}, STREET, {'set': {'type': 'quartier', 'identite': 'crepi_pastel', 'sky': 'day'}}),
    'hall':         ({'type': 'apartment', 'lobby': True}, ([0, 1.6, 1.0], [0, 1.4, 8]), {'set': {'type': 'hall_immeuble', 'ambiance': 'menthe'}, 'cam': ([0, 1.6, .8], [0, 1.4, 7])}),
    'appartement':  ({'type': 'apartment'}, ([0, 1.6, 9.6], [0, 1.3, 15]), {'set': {'type': 'appartement', 'disposition': 'familial', 'ambiance': 'bleu_canard'}, 'cam': ([0, 1.6, .5], [0, 1.3, 5.5])}),
    'salon':        ({'type': 'living_room'}, ([0, 1.6, .5], [0, 1.3, 5]), {'seed': 3}),
    'café':         ({'type': 'cafe'}, ([0, 1.6, .5], [0, 1.3, 6]), {'set': {'type': 'cafe_quartier', 'ambiance': 'bordeaux'}}),
}


def episode(spec, cam, profile, div):
    ep = {'engine_version': 1, 'default_set': 's', 'sets': {'s': spec}, 'cast': {}, 'state': {}, 'title': 'bench diversite',
          'shots': [{'lines': [0, 0], 'set': 's', 'actors': [], 'camera': {'preset': 'free', 'keys': [{'pos': cam[0], 'look': cam[1], 'fov': 75}]}}]}
    if profile: ep['profile'] = profile
    if div is not None: ep['diversite'] = div
    return ep


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--n', type=int, default=5); ap.add_argument('--out', default=''); a = ap.parse_args()
    from hstudio.pipeline import make_engine
    rows = {}
    for name, (spec, cam, ex) in SCENES.items():
        variants = {'livré': episode(spec, cam, None, None), 'production': episode(spec, cam, 'production', False),
                    'diversite': episode(ex.get('set', spec), ex.get('cam', cam), 'production', dict(style='decors', **({'seed': ex['seed']} if 'seed' in ex else {'seed': ex.get('quartier', 0)})))}
        engs = {}; boxes = {}
        for k, ep in variants.items():
            e = make_engine('pixel3d', ep, [{'who': 'x', 'text': 'x', 'start': 0., 'end': 1.}], {}, 1.5, '16:9'); e.render_lowres(.5); engs[k] = e
            from hstudio.engines.pixel3d import frame as F
            boxes[k] = len(e.ctx.get_set('s').base.boxes)
        t = {k: [] for k in engs}
        for _ in range(a.n):
            for k, e in engs.items():
                t0 = time.perf_counter(); e.render_lowres(.5); t[k].append(time.perf_counter() - t0)
        rows[name] = {k: (round(statistics.median(v) * 1000), boxes[k]) for k, v in t.items()}
        r = rows[name]; print(f"{name:16s} livré {r['livré'][0]:5d} ms ({r['livré'][1]:4d} boîtes) | production {r['production'][0]:5d} ms ({r['production'][1]:4d}) | diversité {r['diversite'][0]:5d} ms ({r['diversite'][1]:4d})  x{r['diversite'][0] / r['livré'][0]:.1f} / x{r['diversite'][0] / r['production'][0]:.1f}", flush=True)
    if a.out: Path(a.out).write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__': main()
