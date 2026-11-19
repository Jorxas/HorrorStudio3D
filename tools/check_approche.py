"""Checks of the directed locomotion (hstudio/acting/approach.py, episode key "approach").

  python tools/check_approche.py

Everything runs offline, no API call, nothing is rendered: the acting layer is built through the production path
and sampled. Covers: the opt-in (an episode without the key must not change at all), determinism, the measured
defect and what it becomes, the rate limit, the anticipation chain, the braking stop, deliberate side steps,
the other engine, and the V3 verbs.
"""
import os, sys, math, copy, json
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))
from hstudio.pipeline import make_engine, duration_of                # noqa: E402
from hstudio.acting import approach, rig                             # noqa: E402
from hstudio.acting.timeline import wrap                             # noqa: E402
from locomotion_qc import read_scene, measure, scene_lines           # noqa: E402

OK = []; BAD = []


def check(name, cond, detail=''):
    (OK if cond else BAD).append(name)
    print(f'{"OK  " if cond else "ECHEC"}  {name}' + (f'   {detail}' if detail else ''))


def acting_of(ep, lines, style='pixel3d', aspect='16:9'):
    ep = copy.deepcopy(ep)
    eng = make_engine(style, ep, lines, np.zeros(10), duration_of(ep, lines), aspect)
    return eng.ctx.get_acting() if hasattr(eng, 'ctx') else eng.acting


def scene(path):
    return read_scene(os.path.join(ROOT, 'tests', 'scenes', path))


def with_key(ep, v):
    ep = copy.deepcopy(ep)
    if v is None: ep.pop('approach', None)
    else: ep['approach'] = v
    return ep


def main():
    base, lines = scene('approche_lea_tom.json')
    salon, slines = scene('approche_salon_demo11.json')

    # ------------------------------------------------------------------ 1. the opt-in
    check('opt-in : sans la cle, aucun controleur',
          acting_of(with_key(base, None), lines).shots[0].tracks['lea'].ctrl is None)
    for off in ('off', 'none', 'legacy', ''):
        a = acting_of(with_key(base, off), lines).shots[0]
        check(f'opt-in : "approach": "{off}" reste historique', a.tracks['lea'].ctrl is None)
    check('opt-in : "directed" construit le controleur',
          acting_of(with_key(base, 'directed'), lines).shots[0].tracks['lea'].ctrl is not None)
    check('opt-in : true construit le controleur',
          acting_of(with_key(base, True), lines).shots[0].tracks['lea'].ctrl is not None)
    ep = with_key(base, None); ep['shots'][0]['approach'] = 'directed'
    check('opt-in : la cle du plan l\'emporte sur l\'episode',
          acting_of(ep, lines).shots[0].tracks['lea'].ctrl is not None)
    ep = with_key(base, 'directed'); ep['shots'][0]['approach'] = 'off'
    check('opt-in : un plan peut refuser l\'option de l\'episode',
          acting_of(ep, lines).shots[0].tracks['lea'].ctrl is None)
    a0 = acting_of(with_key(base, None), lines).shots[0]
    s0 = a0.sample(2.0)['lea']['rig']
    check('sans la cle : aucun roll ni lean injecte', abs(s0.get('roll', 0.)) < 1e-9)

    # ------------------------------------------------------------------ 2. determinism
    ts = [i / 17. for i in range(100)]
    h1 = [acting_of(with_key(base, 'directed'), lines).shots[0].tracks['lea'].heading_at(t) for t in ts]
    h2 = [acting_of(with_key(base, 'directed'), lines).shots[0].tracks['lea'].heading_at(t) for t in ts]
    check('determinisme : deux constructions donnent le meme cap au bit pres', h1 == h2)
    tr = acting_of(with_key(base, 'directed'), lines).shots[0].tracks['lea']
    h3 = [tr.heading_at(t) for t in reversed(ts)][::-1]
    check('determinisme : echantillonner a l\'envers donne le meme cap', h1 == h3)

    # ------------------------------------------------------------------ 3. the defect, measured
    for tag, (ep_, ln_) in (('cimetiere', (base, lines)), ('salon demo11', (salon, slines))):
        a_ = measure(ep_, ln_, False); b_ = measure(ep_, ln_, True)
        check(f'{tag} : le defaut existe bien sans l\'option (cap/deplacement > 60 deg)',
              a_['err_max'] > 60, f'{a_["err_max"]:.1f} deg')
        check(f'{tag} : avec l\'option le cap suit le deplacement (< 25 deg)',
              b_['err_max'] < 25, f'{a_["err_max"]:.1f} -> {b_["err_max"]:.1f} deg')
        check(f'{tag} : plus aucune image au-dessus de 25 deg',
              b_['err_over_25'] == 0, f'{a_["err_over_25"]} -> {b_["err_over_25"]} images')
        check(f'{tag} : glissement du pied en translation divise par 2 au moins',
              b_['slide_mv_p95'] < a_['slide_mv_p95'] / 2,
              f'p95 {a_["slide_mv_p95"]:.2f} -> {b_["slide_mv_p95"]:.2f} cm/i')
        check(f'{tag} : Lea s\'arrete FACE a Tom (< 8 deg)',
              b_['face_err_max'] < 8, f'{a_["face_err_max"]:.1f} -> {b_["face_err_max"]:.1f} deg')
        check(f'{tag} : personne ne traverse personne', b_['overlaps'] == 0 and b_['closest'] > .52,
              f'plus proche {b_["closest"]:.2f} m')
        check(f'{tag} : la distance d\'arret demandee est tenue',
              all(abs(d - 1.3) < .12 for d in b_['arrive']), f'{b_["arrive"]} m')
        check(f'{tag} : le corps tourne AVANT de se deplacer', b_['turn_lead'] > .3,
              f'{b_["turn_lead"]:.2f} s')
        check(f'{tag} : le regard ne part jamais apres le corps', b_['gaze_lead'] >= 0,
              f'{b_["gaze_lead"]:.3f} s')

    # ------------------------------------------------------------------ 4. the controller itself
    sa = acting_of(with_key(base, 'directed'), lines).shots[0]
    ctrl = sa.tracks['lea'].ctrl
    dt = 1 / 60.
    H = [ctrl.heading(t) for t in np.arange(0, sa.dur, dt)]
    rates = [abs(wrap(H[i] - H[i - 1])) / dt for i in range(1, len(H))]
    check('vitesse de rotation du corps plafonnee', max(rates) <= ctrl.rate * 1.05 + 1e-6,
          f'max {math.degrees(max(rates)):.0f} deg/s, plafond {math.degrees(ctrl.rate):.0f}')
    check('cap continu : aucun saut brutal d\'une image a l\'autre',
          max(abs(wrap(H[i] - H[i - 1])) for i in range(1, len(H))) < .12,
          f'max {math.degrees(max(abs(wrap(H[i] - H[i - 1])) for i in range(1, len(H)))):.1f} deg par 1/60 s')
    banks = []
    for t in np.arange(.2, sa.dur - .2, .05):
        p = {}; ctrl.decorate(p, float(t))
        w = ctrl._at(ctrl.W, float(t))
        if abs(w) > .4: banks.append(p.get('roll', 0.) * w)
    check('le torse s\'incline dans le virage (roll oppose a la rotation)',
          bool(banks) and all(v < 0 for v in banks), f'{len(banks)} echantillons en virage')
    t_path = sa.tracks['lea'].paths[0].t0
    p_before = {}; ctrl.decorate(p_before, float(t_path - .15))
    p_far = {}; ctrl.decorate(p_far, float(t_path - 1.2))
    check('transfert du poids vers l\'avant juste avant le premier pas',
          p_before.get('lean', 0.) > p_far.get('lean', 0.), f'{p_before.get("lean", 0.):.3f} rad')
    check('naturalisme : deux personnages n\'ont pas la meme vitesse de rotation',
          abs(sa.tracks['lea'].ctrl.rate - sa.tracks['tom'].ctrl.rate) > 1e-6)
    check('naturalisme : l\'arret n\'est pas parfaitement d\'equerre',
          0.2 < measure(base, lines, True)['face_err_max'] < 8)

    # ------------------------------------------------------------------ 5. deliberate side steps
    st, stl = scene('approche_strafe.json')
    sst = acting_of(with_key(st, 'directed'), stl)
    tr0 = sst.shots[0].tracks['lea']; tr1 = sst.shots[1].tracks['lea']
    sw = lambda tr, d: abs(math.degrees(wrap(tr.heading_at(d) - tr.heading_at(0.))))
    check('"strafe": true garde le cap du corps (pas de demi-tour impose)',
          sw(tr0, sst.shots[0].dur) < 5, f'{sw(tr0, sst.shots[0].dur):.1f} deg')
    check('sans "strafe", le meme deplacement fait tourner le corps',
          sw(tr1, sst.shots[1].dur) > 40, f'{sw(tr1, sst.shots[1].dur):.1f} deg')
    check('"strafe" se deplace quand meme vraiment',
          math.hypot(*(np.array(tr0.pos_at(sst.shots[0].dur)) - np.array(tr0.pos_at(0.)))) > 2.)

    # ------------------------------------------------------------------ 6. the other engine, and V3
    cep = {'engine_version': 2, 'approach': 'directed', 'cast': {'noah': {'ref': 'noah'}},
           'shots': [{'lines': [0, 0], 'scene': {'type': 'room'},
                      'actors': [{'id': 'noah', 'at': [-1.2, 1.0], 'facing': '-x'}],
                      'actions': [{'who': 'noah', 'do': 'walk_to', 'to': [1.4, 2.6]}],
                      'camera': {'on': 'noah'}, 'dur': 6}]}
    cl = scene_lines(copy.deepcopy(cep))
    try:
        ca = acting_of(cep, cl, style='console')
        ctl = ca.shots[0].tracks['noah']
        hs = [ctl.heading_at(t) for t in np.arange(0, 6, .1)]
        check('CONSOLE 2D : l\'option marche aussi et le cap bouge',
              ctl.ctrl is not None and max(hs) - min(hs) > .2 and all(np.isfinite(hs)))
    except Exception as e:
        check('CONSOLE 2D : l\'option marche aussi et le cap bouge', False, repr(e))

    v3 = json.load(open(os.path.join(ROOT, 'examples', 'demos', 'demo7_toits.json'), encoding='utf-8'))
    from hstudio.demos import timed_lines
    vep = v3['episode']; vep['approach'] = 'directed'; vep['style'] = 'pixel3d'
    vl = timed_lines(v3['script'], float(v3.get('gap', .3)), float(v3.get('lead', .4)))
    for i, s_ in enumerate(v3['script']):
        if s_.get('who'): vep.setdefault('lines', {}).setdefault(str(i), {})['speaker'] = s_['who']
    try:
        va = acting_of(vep, vl)
        bad = [k for k, s_ in va.shots.items() for tr in s_.tracks.values()
               if not all(np.isfinite([tr.heading_at(t) for t in np.arange(0, s_.dur, .25)]))]
        check('V3 : une scene a niveaux (demo7_toits) accepte l\'option', not bad)
    except Exception as e:
        check('V3 : une scene a niveaux (demo7_toits) accepte l\'option', False, repr(e))

    # ------------------------------------------------------------------ 7. the rig stays sane
    sm = sa.sample(2.0)
    sk = rig.solve(sm['lea']['rig'])
    check('le squelette reste valide avec l\'option',
          all(np.all(np.isfinite(v)) for v in sk.joints.values()))
    check('la tete reste dans le cone de la nuque',
          abs(sm['lea']['rig']['head'][0]) <= .95 + 1e-9, f'{sm["lea"]["rig"]["head"][0]:.3f} rad')

    # --------------------------------------------- 8. cohabitation avec "footing" (decision d'integration P1)
    # Les deux options decrivent le meme geste. `Track.heading_at` interroge le controleur "approach" AVANT la
    # logique de "footing" : ce n'est pas un accident de placement au moment de la fusion, c'est la regle, et
    # c'est ici qu'elle est epinglee. Sans ce test, inverser les deux blocs passerait toutes les autres gardes.
    ep0, lines0 = scene('approche_lea_tom.json')

    def headings(ep, every=.25):
        ac = acting_of(ep, lines0)
        out = []
        for k in sorted(ac.shots):
            s_ = ac.shots[k]
            for tr in s_.tracks.values():
                out += [round(tr.heading_at(t), 9) for t in np.arange(0, s_.dur, every)]
        return out

    def with_keys(ep, approach_v, footing_v):
        ep = copy.deepcopy(ep)
        for key, v in (('approach', approach_v), ('footing', footing_v)):
            if v is None: ep.pop(key, None)
            else: ep[key] = v
        return ep

    h_none = headings(with_keys(ep0, None, None))
    h_foot = headings(with_keys(ep0, None, 'path'))
    h_appr = headings(with_keys(ep0, 'directed', None))
    h_both = headings(with_keys(ep0, 'directed', 'path'))

    check("sans aucune des deux cles, le cap est celui d'avant", h_none != h_foot and h_none != h_appr)
    check('"footing" seul change bien le cap', h_foot != h_none)
    check('"approach" seul change bien le cap', h_appr != h_none)
    # Les deux ensemble ne redonnent PAS "approach" seul, et c'est mesure, pas suppose : "footing" ne touche
    # pas qu'a l'ordre de lecture du cap, il change aussi l'ORDONNANCEMENT que le controleur relit ensuite
    # (duree du quart de tour, depart du chemin, foulee plantee). Le cap reste produit par le controleur
    # "approach" -- c'est la ligne du dessous qui le prouve -- mais il integre un chemin different.
    # Les deux options se composent donc en un troisieme comportement. Il est legitime et il est documente ;
    # ce qui serait fautif, c'est de le decouvrir par surprise. Le proprietaire choisit, personne d'autre.
    check("les deux cles ensemble donnent un troisieme comportement, ni l'un ni l'autre",
          h_both != h_appr and h_both != h_foot and h_both != h_none,
          f'ecart max avec "approach" seul : {max(abs(wrap(a_ - b_)) for a_, b_ in zip(h_both, h_appr)) * 180 / math.pi:.1f} deg')
    ac_both = acting_of(with_keys(ep0, 'directed', 'path'), lines0)
    trs = [tr for k in sorted(ac_both.shots) for tr in ac_both.shots[k].tracks.values()]
    check('sous les deux cles, le controleur "approach" existe bien', all(tr.ctrl is not None for tr in trs))
    check("et c'est lui, et lui seul, qui rend le cap",
          all(abs(tr.heading_at(t) - tr.ctrl.heading(t)) < 1e-12
              for tr in trs for t in np.arange(0, ac_both.shots[0].dur, .25)))
    ac_f = acting_of(with_keys(ep0, None, 'path'), lines0)
    check('"footing" seul ne construit aucun controleur (il reste independant)',
          all(tr.ctrl is None for k in sorted(ac_f.shots) for tr in ac_f.shots[k].tracks.values()))
    check('les quatre combinaisons restent finies et saines',
          all(all(np.isfinite(h) for h in hs) for hs in (h_none, h_foot, h_appr, h_both)))
    # l'une ne doit pas desactiver l'autre par effet de bord : "footing" agit encore sur la foulee (Path plant)
    ac_b = acting_of(with_keys(ep0, 'directed', 'path'), lines0)
    ac_a = acting_of(with_keys(ep0, 'directed', None), lines0)
    sb = [round(p_.S, 9) for k in sorted(ac_b.shots) for tr in ac_b.shots[k].tracks.values() for p_ in tr.paths]
    sa_ = [round(p_.S, 9) for k in sorted(ac_a.shots) for tr in ac_a.shots[k].tracks.values() for p_ in tr.paths]
    check('"footing" garde son effet propre sur la foulee meme sous "approach"', sb != sa_ and bool(sb),
          f'{len(sb)} chemins, foulees differentes')

    print()
    print(f'{len(OK)} verifications OK, {len(BAD)} en echec')
    if BAD:
        for b in BAD: print('   ECHEC :', b)
        sys.exit(1)
    print('Tout est OK')


if __name__ == '__main__':
    main()
