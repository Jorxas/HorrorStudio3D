"""Mesure la SILHOUETTE d'un personnage PIXEL 3D : combien de tetes de haut, quelle largeur d'epaules, et ce
que la refonte des proportions (cle d'episode opt-in "body") change exactement.

    python tools/corps_qc.py                              # le tableau des presets, geometrie seule, instantane
    python tools/corps_qc.py --json docs/p1_corps/silhouette.json

Pourquoi un outil de plus. `tools/cadrage_qc.py` (lot P1 visuel) mesure la place que le corps prend dans
**son cadre** : c'est la bonne mesure pour un defaut de cadrage, et c'est la mauvaise pour un defaut de
proportions, parce qu'une camera qui recule fait baisser toutes ses valeurs sans rien corriger. Ici on ne
regarde pas l'image du tout : on lit les **boites reellement emises** par `rigfig.build` pour une pose donnee
et on en tire des rapports sans unite, que la camera ne peut pas flatter :

| mesure | ce que c'est | reference humaine |
|---|---|---|
| `tetes` | hauteur totale / hauteur du bloc tete (crane + cheveux + chapeau) | ~7,5 |
| `epaules/haut` | largeur hors-tout aux epaules (bras compris) / hauteur totale | ~0,25 |
| `torse/haut` | largeur du torse seul / hauteur totale | ~0,19 |
| `tete/torse` | largeur du bloc tete / largeur du torse | ~0,75 |
| `cou` | hauteur du bloc cou qui depasse du vetement du torse (m) | ~0,09 |
| `jonc` | bas du crane moins haut du cou : <= 0, sinon il y a un trou sous la tete | <= 0 |

Deux garde-fous, mesures et pas supposes, parce que la refonte est une mise a l'echelle de volumes et qu'une
mise a l'echelle mal posee casse une animation en silence :

- `os` : les longueurs d'os lues sur le squelette partage (`acting/rig.py`) avant et apres. Elles doivent etre
  identiques au centieme de millimetre : la refonte ne touche pas `rig.py` et n'amincit les membres que
  **en travers** de l'os (x et z locaux), jamais le long (y local) ;
- `pieds` : la hauteur du point le plus bas de la chaussure. Un corps dont les jambes ont maigri mais dont le
  pied flotte ou s'enfonce se verrait immediatement a la marche.

Aucun lanceur de rayons, aucun ffmpeg, aucun reseau. Deterministe.
"""
import os, sys, json, argparse
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

HEAD = ('head',)
TORSO = ('torso',)
ARMS = ('upperL', 'upperR', 'foreL', 'foreR', 'handL', 'handR')
FEET = ('footL', 'footR')
BONES = (('shR', 'elR'), ('elR', 'haR'), ('hipR', 'knR'), ('knR', 'anR'), ('pelvis', 'neck'), ('neck', 'head'))

# reference humaine, declaree AVANT de mesurer quoi que ce soit (sinon ce n'est plus une reference). `ecart`
# resume les CINQ rapports en un seul nombre, la moyenne des ecarts relatifs : il est imprime pour que le choix
# d'une configuration soit reproductible et pas choisi apres coup -- une configuration peut gagner sur trois
# rapports et perdre sur l'ensemble, et c'est exactement ce qui arrive entre `refit` et `refit_fort`. `jonc`
# n'entre pas dans `ecart` : ce n'est pas une proportion, c'est un defaut binaire (trou, ou pas de trou).
REF = dict(tetes=7.5, ep_haut=.25, to_haut=.19, tete_torse=.75, cou=.09)
# La SECONDE reference, celle des images du proprietaire : le personnage cubique de Minecraft, dont les
# proportions ne sont pas une opinion mais la grille du modele -- tete 8x8x8, torse 8 large x 12 haut x 4
# profond, membres 4 de large, total 32 de haut. D'ou : 4,0 tetes, epaules (4+8+4)/32, torse 8/32, tete
# aussi large que le torse, et AUCUN cou. `--ref minecraft` note les presets contre celle-la.
REF_MC = dict(tetes=32 / 8., ep_haut=(4 + 8 + 4) / 32., to_haut=8 / 32., tete_torse=8 / 8., cou=0.)
REFS = {'humain': REF, 'minecraft': REF_MC}

LOOK = dict(hood=[64, 72, 96], jeans=[46, 52, 70], skin=[214, 176, 148], hair=[92, 64, 44], outfit='hoodie',
            hair_style='short', headphones=False, backpack=False)

POSES = {
    'debout': {},
    'marche': dict(gait=1., phase=1.1, stride=1.25, t=1.3),
    'parle_point': dict(t=2.0, gestures=[('point', 1.0, .6)], head=(0., .05)),
}


def groups(sample, look, preset):
    """-> {nom de repere du squelette: [boites]} pour un personnage, avec ou sans refonte"""
    from hstudio.engines.pixel3d import rigfig, bodies, assets as A
    was = bodies.active()                      # NEVER clobber the preset of an engine that is being measured
    bodies.use(bodies.configure(preset) if preset else None)
    rigfig.PARTS = parts = {}
    try:
        face = A.face_tex('neutral', 0.)
        out, sk = rigfig.build(dict(x=0., y=0., z=0., heading=0., rig=dict(sample)), dict(look), face)
    finally:
        rigfig.PARTS = None; bodies.use(was)
    return parts, out, sk


def _bounds(boxes):
    if not boxes: return None
    lo = np.min([b.wlo for b in boxes], 0); hi = np.max([b.whi for b in boxes], 0)
    return lo, hi


def _ecart(vals, ref):
    """ecart moyen relatif aux cinq rapports d'une reference ; `cou` est en metres, donc rapporte a 9 cm
    d'echelle quelle que soit la reference, sans quoi une reference a cou nul diviserait par zero"""
    tot = 0.
    for kk, v in vals.items():
        r = ref[kk]
        tot += abs(v - r) / (r if r > 1e-6 else .09)
    return round(tot / len(ref), 3)


def silhouette(sample, look, preset):
    from hstudio.engines.pixel3d import bodies
    parts, out, sk = groups(sample, look, preset)
    allb = _bounds(out)
    head = _bounds([b for n in HEAD for b in parts.get(n, [])])
    torso = _bounds([b for n in TORSO for b in parts.get(n, [])])
    arms = _bounds([b for n in ARMS for b in parts.get(n, [])])
    feet = _bounds([b for n in FEET for b in parts.get(n, [])])
    H = float(allb[1][1] - allb[0][1])
    hh = float(head[1][1] - head[0][1]); hw = float(head[1][0] - head[0][0])
    neckb = _bounds([b for b in parts.get('neck', [])])      # neck + deltoid caps, their own group when refitted
    tw = float(torso[1][0] - torso[0][0])                    # the trunk alone: the caps are not in this group
    hi_x = max([arms[1][0], torso[1][0]] + ([neckb[1][0]] if neckb else []))
    lo_x = min([arms[0][0], torso[0][0]] + ([neckb[0][0]] if neckb else []))
    sw = float(hi_x - lo_x)
    was = bodies.active(); st = bodies.configure(preset) if preset else None; bodies.use(was)
    # the neck block, and the proof it bridges: a positive `jonction` would be a visible gap under the skull
    neck = float(neckb[1][1] - torso[1][1]) if neckb else 0.      # what shows ABOVE the garment, not the block
    jonc = float(head[0][1] - neckb[1][1]) if neckb else float(head[0][1] - torso[1][1])
    return dict(preset=preset or 'defaut', haut=round(H, 4), tete_h=round(hh, 4), tete_l=round(hw, 4),
                torse_l=round(tw, 4), epaules_l=round(sw, 4), pied_y=round(float(feet[0][1]), 4),
                cou=round(neck, 4), jonction=round(jonc, 4), tetes=round(H / hh, 2), ep_haut=round(sw / H, 3), to_haut=round(tw / H, 3),
                tete_torse=round(hw / tw, 2), boites=len(out),
                **{'ecart_' + rn: _ecart(dict(tetes=H / hh, ep_haut=sw / H, to_haut=tw / H,
                                              tete_torse=hw / tw, cou=neck), rf)
                   for rn, rf in REFS.items()},
                os={f'{a}-{b}': round(float(np.linalg.norm(sk.joints[a] - sk.joints[b])), 6) for a, b in BONES},
                spec={k: v for k, v in (st or {}).items() if k != 'name'})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--presets', default='defaut,minecraft,voxel_premium')
    ap.add_argument('--ref', default='humain', choices=sorted(REFS),
                    help='la reference notee par la colonne « ecart »')
    ap.add_argument('--pose', default='debout', choices=sorted(POSES) + ['toutes'])
    ap.add_argument('--json', default='')
    a = ap.parse_args()
    names = [p.strip() for p in a.presets.split(',') if p.strip()]
    poses = sorted(POSES) if a.pose == 'toutes' else [a.pose]
    rows = []
    for pose in poses:
        rf = REFS[a.ref]
        print(f'\npose « {pose} »   (reference « {a.ref} » : {rf["tetes"]:.2f} tetes, '
              f'epaules {rf["ep_haut"]:.3f}, torse {rf["to_haut"]:.3f}, '
              f'tete/torse {rf["tete_torse"]:.2f}, cou {rf["cou"]:.2f} m)')
        print('  preset        haut   tete   tetes  epaules/haut  torse/haut  tete/torse  cou(m)  jonc(m)  pied(m)  ecart  boites')
        for nm in names:
            r = silhouette(POSES[pose], LOOK, None if nm == 'defaut' else nm)
            r['pose'] = pose; rows.append(r)
            print(f"  {r['preset']:12s} {r['haut']:5.2f}  {r['tete_h']:5.3f}  {r['tetes']:5.2f}"
                  f"      {r['ep_haut']:5.3f}        {r['to_haut']:5.3f}       {r['tete_torse']:5.2f}"
                  f"   {r['cou']:+.3f}   {r['jonction']:+.3f}   {r['pied_y']:+.3f}  {r['ecart_' + a.ref]:5.3f}  {r['boites']:4d}")
    ref = {r['pose']: r['os'] for r in rows if r['preset'] == 'defaut'}      # same pose, refit vs stock body
    bad = [(r['preset'], r['pose'], k) for r in rows for k, v in r['os'].items()
           if r['pose'] in ref and abs(v - ref[r['pose']][k]) > 1e-5]
    print('\n  os du squelette partage (acting/rig.py) : ' + ('IDENTIQUES partout' if not bad else f'ECART {bad}'))
    print('  pied le plus bas : ' + ', '.join(f"{r['preset']}/{r['pose']} {r['pied_y']:+.3f}" for r in rows))
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        json.dump({'rows': rows, 'look': LOOK, 'os_identiques': not bad}, open(a.json, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('  ecrit', a.json)
    return 0 if not bad else 1


if __name__ == '__main__': sys.exit(main())
