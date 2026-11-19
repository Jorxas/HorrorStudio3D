"""Le banc d'essai des proportions : la MEME scene rendue sous plusieurs configurations de corps, et toutes les
mesures qui doivent decider -- silhouette, place dans le cadre, controle qualite, vitesse.

    python tools/corps_bench.py examples/demos/demo6_continuite.json
    python tools/corps_bench.py examples/demos/demo20_decors.json --json docs/p1_corps/bench_demo20.json

Il n'y a aucune image ici : c'est l'outil qui sert a CHOISIR, pas celui qui sert a montrer (planches :
`tools/corps_sheet.py`). Quatre familles de mesures, parce qu'aucune ne suffit seule et qu'elles tirent dans
des sens opposes :

| famille | outil | ce qu'elle voit | ce qu'elle ne voit pas |
|---|---|---|---|
| silhouette | `tools/corps_qc.py` | les rapports sans unite du corps (tetes de haut, epaules, torse) | l'image |
| cadre | `tools/cadrage_qc.py` | la part d'image prise par le bras, la tete, le corps | les proportions |
| mise en scene | `hstudio/acting/qc.py` | visages lisibles, sujets cadres, cameras contraintes | les proportions ET le bras |
| cout | ici | les secondes par image du lanceur de rayons | tout le reste |

Une tete plus petite **rapproche** la camera (`cinema.HEAD_SHARE` lit la vraie largeur de tete que le moteur
annonce) : la part d'image prise par le corps **monte** alors que les proportions s'ameliorent. C'est pour cela
que les quatre familles sont imprimees cote a cote et qu'aucune n'est presentee comme la note du lot.

Aucun reseau, aucune cle, aucun ffmpeg, aucun projet ecrit.
"""
import os, sys, json, time, argparse

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

EXPR = [('face_detail', 'hd'), ('detail', True), ('hair2', [150, 96, 58]), ('iris', [96, 140, 120])]
LISIBLE = [('camera_clear_face', True)]
# les configurations explorees : jamais plus que ce qui peut etre juge sur une planche
CONFIGS = [
    ('A  defaut', [], []),
    ('B  cadrage lisible + visage expressif', LISIBLE, EXPR),
    # C a G (le corps humain avec cou `refit`, `refit_fort`, `tete_seule`) : supprimes le 31/10, rejetes
    # L'AUTRE direction, celle des images du proprietaire, et sa finition. H est le corps cubique nu ; I est le
    # meme corps PLUS les volumes premium (poing, semelle, epaules carrees, zip, poches) et la promotion des
    # cles de look que le moteur possedait deja. Les deux lignes sont la ensemble parce que la question posee
    # par ce lot est exactement « combien coute la finition », et une seule ligne n'y repond pas. H et I ne
    # portent PAS `EXPR` : la promotion de look est justement ce que I mesure, et la poser a la main sur les
    # deux lignes rendrait la comparaison aveugle.
    ('H  B + minecraft (le corps cubique nu)', LISIBLE + [('body', 'minecraft')], []),
    ('I  H + la finition premium (voxel_premium)', LISIBLE + [('body', 'voxel_premium')], []),
]


def cadre(eng, end, every):
    from cadrage_qc import measure, TIGHT
    rows = [r for r in measure(eng.ctx, end, every) if r['kind'] in TIGHT]
    if not rows: return {}
    n = len(rows)
    return dict(images=n,
                bras=round(100 * sum(r['bras'] for r in rows) / n, 2), bras_max=round(100 * max(r['bras'] for r in rows), 1),
                tete=round(100 * sum(r['tete'] for r in rows) / n, 2),
                corps=round(100 * sum(r['corps'] for r in rows) / n, 2),
                mange=round(100 * sum(r['visage_mange'] for r in rows) / n, 2),
                mange_max=round(100 * max(r['visage_mange'] for r in rows), 1))


def qualite(eng, ep, lines):
    from hstudio.acting import qc
    rep = qc.run(eng, ep, lines, every=.25, frames=True)
    ch = rep['checks']
    return dict(score=rep['score'],
                faces_readable=round(float(ch.get('faces_readable', {}).get('value', 0.)), 3),
                speaker_visible=round(float(ch.get('speaker_visible', {}).get('value', 0.)), 3),
                subjects_framed=round(float(ch.get('subjects_framed', {}).get('value', 0.)), 3),
                camera_blocked=ch.get('camera_blocked', {}).get('value'),
                reproches=sorted(k for k, c in ch.items() if not c.get('ok') and not c.get('info')),
                trop_serre=[i['message'] for i in rep['issues'] if 'trop serré' in i['message']])


def vitesse(eng, times, repeat=1):
    """secondes par image, MINIMUM de `repeat` passes : la moyenne d'une seule passe bouge de 5 a 10 % d'un
    lancement a l'autre sur cette machine, et comparer deux configurations avec ce bruit-la ne veut rien dire."""
    best = None
    for _ in range(max(1, repeat)):
        t0 = time.time()
        for t in times: eng.render_lowres(float(t))
        d = (time.time() - t0) / max(1, len(times))
        best = d if best is None else min(best, d)
    return round(best, 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('scene'); ap.add_argument('--aspect', default='9:16')
    ap.add_argument('--every', type=float, default=.5)
    ap.add_argument('--configs', default='', help='sous-ensemble par lettre (ex: A,D)')
    ap.add_argument('--repeat', type=int, default=1, help='passes de mesure du cout (le minimum est retenu)')
    ap.add_argument('--cout-seul', action='store_true', help='ne mesurer que le cout (rapide, re-mesurable seul)')
    ap.add_argument('--json', default='')
    a = ap.parse_args()
    from cadrage_qc import build
    from corps_qc import silhouette, POSES, LOOK
    keep = {s.strip().upper() for s in a.configs.split(',') if s.strip()}
    cfgs = [c for c in CONFIGS if not keep or c[0][0] in keep]
    out = []
    for lbl, eks, cks in cfgs:
        preset = dict(eks).get('body')
        if isinstance(preset, dict): preset = preset.get('style')      # une config reglee finement garde son preset
        ep, lines, eng = build(a.scene, a.aspect, eks, cks)
        end = lines[-1]['end']
        sil = silhouette(POSES['debout'], LOOK, preset)
        from hstudio.engines.pixel3d import bodies as BD
        BD.use(eng.body)                 # the silhouette pass above borrowed the module: give the engine its own back
        times = [end * f for f in (.08, .15, .22, .35, .45, .55, .65, .75, .85, .95)]
        r = dict(config=lbl, keys=[list(x) for x in eks], preset=preset or 'aucun',
                 silhouette={k: sil[k] for k in ('tetes', 'ep_haut', 'to_haut', 'tete_torse', 'cou', 'jonction', 'haut', 'ecart_humain', 'ecart_minecraft')},
                 cadre={} if a.cout_seul else cadre(eng, end, a.every),
                 qc={} if a.cout_seul else qualite(eng, ep, lines),
                 s_par_image=vitesse(eng, times, a.repeat))
        out.append(r)
        c = r['cadre']; q = r['qc']; s = r['silhouette']
        print(f"\n{lbl}")
        print(f"   silhouette : {s['tetes']:.2f} tetes, epaules/haut {s['ep_haut']:.3f}, torse/haut {s['to_haut']:.3f},"
              f" tete/torse {s['tete_torse']:.2f}, cou {s['cou']:+.3f} m, jonction {s['jonction']:+.3f} m,"
              f" ecart humain {s['ecart_humain']:.3f}, minecraft {s['ecart_minecraft']:.3f}")
        if c:
            print(f"   cadre      : bras {c.get('bras', 0):5.2f} % (pire {c.get('bras_max', 0):4.1f}), tete {c.get('tete', 0):5.2f} %,"
                  f" corps {c.get('corps', 0):5.2f} %, visage mange {c.get('mange', 0):4.2f} % (pire {c.get('mange_max', 0):4.1f})")
        if q:
            print(f"   mise en sc.: {q['score']}/100, visages lisibles {q['faces_readable']:.3f}, sujets cadres"
                  f" {q['subjects_framed']:.3f}, cameras contraintes {q['camera_blocked']}, reproches {q['reproches'] or 'aucun'}")
            for m in q['trop_serre']: print('                ! ' + m)
        print(f"   cout       : {r['s_par_image']:.3f} s / image (216x384)")
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        json.dump(dict(scene=a.scene, aspect=a.aspect, every=a.every,
                       when=time.strftime('%Y-%m-%d %H:%M:%S'), rows=out),
                  open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('\necrit ' + a.json)


if __name__ == '__main__': main()
