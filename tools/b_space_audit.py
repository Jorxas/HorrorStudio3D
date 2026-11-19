"""python tools/b_space_audit.py [--spacing on|off|both] [--cases a,b,...] [--projects test_maison_v4,test_moteur_v4]

Mesure les collisions et la distance de dialogue (hstudio/voxelgpu/b_space.py : `audit`) sur des cas écrits exprès, des épisodes du studio et des films existants, avec la séparation
éteinte (« avant ») ou allumée (« après »). Colonnes : images, images où deux corps se chevauchent (< distance physique), images où l'on parle plus près que 85 % de la distance de
conversation, images où un acteur est dans l'emprise d'un décor, distance minimale entre deux acteurs."""
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu import director, b_space as SP

CASTS = {'lea': {'preset': 'lina'}, 'tom': {'preset': 'noe'}, 'zed': {'b_preset': 'zombie'}}
ENV = dict(floor=0x4a4640, bg=0x1a2030, ambient=1.0, key=0.8, fog=0.005)


def shot(dur=4., actors=(), actions=(), speech=(), props=(), cam=None, **kw):
    return dict(stage='plateau', dur=dur, env=ENV, camera=cam or dict(shot='wide', on=[a['id'] for a in actors]), actors=list(actors), actions=list(actions), speech=[list(s) for s in speech], props=list(props), **kw)


def cases():
    A = lambda i, x, z, f='+z': dict(id=i, at=[x, z], facing=f, face='neutral')
    return {
        'face_a_face_trop_pres': dict(shots=[shot(5, [A('lea', -.3, 0, '+x'), A('tom', .3, 0, '-x')], speech=[(.3, 2.2, 'lea'), (2.6, 4.5, 'tom')])]),
        'course_vers_l_autre': dict(shots=[shot(6, [A('lea', 0, 0), A('tom', -6, 0, '+x')], [dict(who='tom', do='run_to', to='lea', at=.2)], speech=[(.2, 5, 'lea')])]),
        'marche_vers_l_autre': dict(shots=[shot(6, [A('lea', 0, 0), A('tom', -5, 0, '+x')], [dict(who='tom', do='walk_to', to='lea', at=.2)], speech=[(3, 5.5, 'tom')])]),
        'croisement': dict(shots=[shot(6, [A('lea', -5, .1, '+x'), A('tom', 5, -.1, '-x')], [dict(who='lea', do='walk_to', to=[5, .1], at=.2), dict(who='tom', do='walk_to', to=[-5, -.1], at=.2)])]),
        'meuble_sur_le_chemin': dict(shots=[shot(6, [A('lea', -5, 0, '+x')], [dict(who='lea', do='walk_to', to=[5, 0], at=.2)],
                                                 props=[dict(type='b:table', at=[0, 0], rot=0), dict(type='craft:oak_tree', at=[-2, .2], seed=1), dict(type='b:sofa', at=[2.4, -.1])])]),
        'trois_en_discussion': dict(shots=[shot(6, [A('lea', -.4, 0, '+x'), A('tom', .4, 0, '-x'), A('zed', 0, .5, '-z')], speech=[(.2, 2, 'lea'), (2.2, 4, 'tom'), (4.2, 5.8, 'zed')])]),
        'etreinte_intimite': dict(intimacy=True, shots=[shot(5, [A('lea', -.6, 0, '+x'), A('tom', .6, 0, '-x')], [dict(who='lea', do='gesture', name='hug', at=1, dur=3), dict(who='tom', do='gesture', name='hug', at=1, dur=3)])]),
    }


def project_contract(slug, spacing):
    from hstudio import pipeline as P
    from hstudio.voxelgpu import studio_bridge as VB
    return VB.contract_of(P.Project(slug), '16:9', spacing=spacing)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--spacing', default='both'); ap.add_argument('--cases', default=''); ap.add_argument('--projects', default='test_maison_v4,test_moteur_v4'); ap.add_argument('--films', default='demo_genres')
    ap.add_argument('--json', default=''); a = ap.parse_args(); modes = [False, True] if a.spacing == 'both' else [a.spacing == 'on']
    rows = []
    C0 = cases()
    for name in ([n for n in a.cases.split(',') if n] or list(C0)):
        for mode in modes:
            ep = dict(title=name, genre='neutral', casts=CASTS, spacing=mode, **{k: v for k, v in C0[name].items()})
            c = director.build(ep, '16:9', 24); rows.append((name, mode, SP.audit(c, intimacy=bool(ep.get('intimacy')))))
    for slug in [s for s in a.projects.split(',') if s]:
        for mode in modes:
            try: c = project_contract(slug, mode); rows.append((slug, mode, SP.audit(c)))
            except Exception as e: print('projet ignoré', slug, type(e).__name__, str(e)[:120])
    for film in [f for f in a.films.split(',') if f]:
        try:
            import importlib; m = importlib.import_module(f'hstudio.voxelgpu.films.{film}'); ep = m.episode()
        except Exception as e: print('film ignoré', film, e); continue
        for mode in modes:
            c = director.build(dict(ep, spacing=mode), '16:9', 24); rows.append((film, mode, SP.audit(c)))
    print(f"{'cas':<26}{'sép.':<6}{'images':>7}{'chevauch.':>10}{'parle trop près':>17}{'dans un décor':>15}{'min (m)':>9}")
    for name, mode, r in rows: print(f"{name:<26}{'ON' if mode else 'off':<6}{r['frames']:>7}{r['pair_frames_below_phys']:>10}{r['pair_frames_below_conv_talking']:>17}{r['penetration_frames']:>15}{(r['min_pair'] if r['min_pair'] is not None else '-')!s:>9}")
    if a.json: Path(a.json).write_text(json.dumps([dict(case=n, spacing=m, **{k: v for k, v in r.items() if k != 'stages'}) for n, m, r in rows], indent=1), encoding='utf-8')


if __name__ == '__main__': main()
