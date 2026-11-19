"""Suite ciblee des sous-titres surs. Sortie 0 = tout vert, 1 = au moins un echec.

    python tools/check_soustitres.py
    python tools/check_soustitres.py --section 1      (une seule section)

Huit sections, et la premiere est la plus importante :

 1. SANS LA CLE, RIEN NE CHANGE -- au bit pres, sur les deux moteurs et les deux formats. C'est la
    garantie qui autorise a livrer une option non encore validee a l'oeil.
 2. la geometrie pure (`captions/geometry.py`) : intersections, rectangle de texte, zone sure, largeur.
 3. la politique : une bande qui couvre une bouche n'est jamais choisie s'il existe une bande libre, et
    l'ordre editorial est respecte a egalite.
 4. la stabilite : la bande est decidee par PLAN, et l'hysteresis empeche le bandeau de revenir en
    arriere d'un plan a l'autre quand sa bande precedente est encore libre.
 5. jamais hors cadre : quelle que soit la taille de la tete, la bande choisie reste dans la zone sure.
 6. le texte enorme : une replique plus large que les marges est rapetissee, et jamais en dessous du
    plancher d'accessibilite.
 7. la cle elle-meme : valeurs acceptees, valeurs refusees, et un refus se DIT (notices).
 8. le resultat mesure sur la scene du defaut : le recouvrement de la bouche tombe a zero, et le plan de
    bandes est le meme quelle que soit l'image par laquelle on entre (determinisme).

Aucun ffmpeg, aucun reseau. La section 8 rend des images basse resolution ; les autres ne rendent rien.
"""
import os, sys, json, hashlib, argparse
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

from hstudio.captions import geometry as G                                 # noqa: E402
from hstudio.captions import safe as CAPS                                  # noqa: E402

OK, BAD = [], []


def check(name, cond, detail=''):
    (OK if cond else BAD).append(name)
    print(('  OK    ' if cond else '  ECHEC ') + name + (('   ' + str(detail)) if detail else ''))
    return bool(cond)


def near(a, b, eps=1e-6):
    return abs(float(a) - float(b)) <= eps


# ---------------------------------------------------------------- 1
def section1():
    """sans la cle, l'image est la meme au bit pres -- sur les deux moteurs et les deux formats"""
    print('\n== 1. sans la cle "caption_safe", rien ne change (au bit pres) ==')
    from hstudio import demos as D
    from hstudio.pipeline import make_engine, duration_of
    import copy
    for demo_id in ('demo2_dialogue', 'demo5_console', 'demo12_aplat_ui'):
        sc = D.load(demo_id)
        lines = D.timed_lines(sc['script'], float(sc.get('gap', .3)), float(sc.get('lead', .4)))
        env = D.draft_voice(sc, lines)[1]
        ep = D.episode_of(sc, lines, log=lambda *a: None)
        dur = duration_of(ep, lines)
        for aspect in ('9:16', '16:9'):
            hs = []
            for keyed in (False, True):
                e2 = copy.deepcopy(ep)
                if keyed:
                    e2.pop('caption_safe', None)          # la cle ABSENTE des deux cotes : le test de reference
                eng = make_engine(sc.get('style', 'pixel3d'), e2, lines, env, dur, aspect)
                ts = [round(dur * (k + .5) / 3, 2) for k in range(3)]
                hs.append([hashlib.sha1(np.asarray(eng.frame(t)).tobytes()).hexdigest()[:16] for t in ts])
            check(f'{demo_id}@{aspect} : identique sans la cle', hs[0] == hs[1])
    # et la cle a false / null / "" doit se comporter exactement comme l'absence
    for v in (False, None, '', 0):
        check(f'configure({v!r}) -> None (le bandeau livre)', CAPS.configure(v) is None)


# ---------------------------------------------------------------- 2
def section2():
    print('\n== 2. geometrie pure ==')
    a = (0., .5, 0., .5)
    check('inter disjoints = 0', near(G.inter(a, (.6, 1., .6, 1.)), 0.))
    check('inter se touchant = 0', near(G.inter(a, (.5, 1., 0., .5)), 0.))
    check('inter quart', near(G.inter(a, (.25, .75, .25, .75)), .0625))
    check('inter avec None = 0', near(G.inter(a, None), 0.))
    check('covered moitie', near(G.covered((0., 1., 0., .2), (0., .5, 0., .2)), .5))
    check('covered rectangle vide = 0', near(G.covered((0., 0., 0., 0.), a), 0.))
    r = G.text_rect(.5, .6, .04)
    check('text_rect centre', near(r[0], .2) and near(r[1], .8), r)
    check('text_rect hauteur', near(r[2], .5) and near(r[3], .54), r)
    r2 = G.text_rect(.5, .6, .04, label_h=.03)
    check('text_rect pastille au-dessus', near(r2[2], .47) and near(r2[3], .54), r2)
    s = G.SAFE['9:16']
    check('zone sure 9:16 : haut 298 px sur 1920', near(round(s['top'] * 1920), 298), s['top'])
    check('zone sure 9:16 : bas 1690 px sur 1920', near(round(s['bottom'] * 1920), 1690), s['bottom'])
    check('la position livree "low" (1560) tient dans la zone sure',
          G.fits(1560 / 1920., 64 / 1920., 52 / 1920., s))
    check('la position livree "mid" (880) tient aussi (ce n\'est pas elle le probleme, c\'est ce qu\'elle couvre)',
          G.fits(880 / 1920., 64 / 1920., 52 / 1920., s))
    check('un texte pose a 1700 px est refuse (sous le rail de la plateforme)',
          not G.fits(1700 / 1920., 64 / 1920., 0., s))
    check('un texte pose a 200 px est refuse (dans le cartouche HUD)',
          not G.fits(200 / 1920., 64 / 1920., 52 / 1920., s))


# ---------------------------------------------------------------- 3
def section3():
    print('\n== 3. la politique : une bouche couverte n\'est jamais choisie s\'il existe une bande libre ==')
    named = {'mid': 880 / 1920., 'low': 1560 / 1920., 'top': 420 / 1920.}
    h, w = 64 / 1920., .72
    # un visage au milieu du cadre, comme un gros plan vertical
    face = dict(rect=(.17, .91, 230 / 1920., 940 / 1920.),
                mouth=(.17, .91, 700 / 1920., 920 / 1920.),
                eyes=(.17, .91, 500 / 1920., 640 / 1920.), weight=1.)
    r = G.choose(named, 'mid', [face], w, h, 52 / 1920., '9:16')
    check('gros plan : "mid" demande, une autre bande choisie', r['band'] != 'mid', r['band'])
    check('gros plan : la bande choisie est libre', r['clear'] is True, r)
    check('gros plan : "low" prefere (ordre editorial)', r['band'] == 'low', r['band'])
    # sans visage, la bande demandee est conservee telle quelle
    r2 = G.choose(named, 'mid', [], w, h, 52 / 1920., '9:16')
    check('aucun visage : "mid" conserve', r2['band'] == 'mid' and near(r2['y'], named['mid']), r2['band'])
    # visage sur le cote : "mid" est libre et doit etre conserve
    side = dict(rect=(.56, .98, 255 / 1920., 700 / 1920.), mouth=None, eyes=None, weight=1.)
    r3 = G.choose(named, 'mid', [side], .40, h, 0., '9:16')
    check('visage a droite, texte etroit : "mid" conserve', r3['band'] == 'mid' and r3['clear'], r3['band'])
    # la bouche coute plus cher que le front. Les deux hauteurs comparees sont DANS la zone sure (310 px
    # est juste sous le bord haut a 298) : sinon on comparerait une penalite de hors-cadre, pas un visage.
    cm, _, _ = G.cost(700 / 1920., w, h, 0., [face], G.SAFE['9:16'])      # sur la bouche
    cf, _, _ = G.cost(310 / 1920., w, h, 0., [face], G.SAFE['9:16'])      # sur le front
    check('couvrir la bouche coute plus cher que couvrir le front', cm > cf, (round(cm, 1), round(cf, 1)))
    check('les deux hauteurs comparees sont bien dans la zone sure',
          G.fits(700 / 1920., h, 0., G.SAFE['9:16']) and G.fits(310 / 1920., h, 0., G.SAFE['9:16']))


# ---------------------------------------------------------------- 4
def section4():
    print('\n== 4. stabilite : pas de saut brusque ==')
    named = {'mid': 880 / 1920., 'low': 1560 / 1920., 'top': 420 / 1920.}
    h, w = 64 / 1920., .72
    side = dict(rect=(.56, .98, 255 / 1920., 700 / 1920.), mouth=None, eyes=None, weight=1.)
    # plan precedent : "low". Ici "mid" serait libre -- mais on ne doit PAS revenir en arriere.
    r = G.choose(named, 'mid', [side], .40, h, 0., '9:16', prev=('low', named['low']))
    check('bande precedente encore libre : elle est maintenue', r['band'] == 'low', r['band'])
    check('et la raison le dit', 'maintenue' in (r['reason'] or ''), r['reason'])
    # une bande precedente qui n'est PLUS libre doit etre abandonnee
    low_face = dict(rect=(.0, 1., 1500 / 1920., 1680 / 1920.), mouth=None, eyes=None, weight=1.)
    r2 = G.choose(named, 'mid', [low_face], w, h, 0., '9:16', prev=('low', named['low']))
    check('bande precedente devenue occupee : elle est abandonnee', r2['band'] != 'low', r2['band'])
    check('et la nouvelle est libre', r2['clear'] is True, r2)
    # la penalite de deplacement ne peut jamais faire preferer une bouche couverte
    face = dict(rect=(.17, .91, 230 / 1920., 940 / 1920.),
                mouth=(.17, .91, 700 / 1920., 920 / 1920.), eyes=None, weight=1.)
    r3 = G.choose(named, 'mid', [face], w, h, 0., '9:16', prev=('mid', named['mid']))
    check('hysteresis n\'impose jamais une bande qui couvre la bouche', r3['band'] != 'mid', r3['band'])


# ---------------------------------------------------------------- 5
def section5():
    print('\n== 5. jamais hors cadre, quelle que soit la tete ==')
    named = {'mid': 880 / 1920., 'low': 1560 / 1920., 'top': 420 / 1920.}
    safe = G.SAFE['9:16']
    h, w, lab = 64 / 1920., .72, 52 / 1920.
    worst = []
    for top in range(0, 1800, 60):
        for bot in range(top + 60, 1921, 120):
            face = dict(rect=(.05, .95, top / 1920., bot / 1920.),
                        mouth=(.05, .95, (top + .6 * (bot - top)) / 1920., (top + .95 * (bot - top)) / 1920.),
                        eyes=None, weight=1.)
            r = G.choose(named, 'mid', [face], w, h, lab, '9:16')
            if not G.fits(r['y'], h, lab, safe):
                worst.append((top, bot, r['band'], r['y']))
    check(f'{len(range(0, 1800, 60))} x tetes : la bande reste toujours dans la zone sure',
          not worst, worst[:3])
    # un visage qui remplit TOUT le cadre : il n'y a plus de bande libre, et il faut le DIRE
    full = dict(rect=(0., 1., 0., 1.), mouth=(0., 1., .6, .95), eyes=(0., 1., .4, .55), weight=1.)
    r = G.choose(named, 'mid', [full], w, h, lab, '9:16')
    check('visage plein cadre : aucune bande libre, et le rapport le declare',
          r['clear'] is False and 'aucune bande libre' in (r['reason'] or ''), r['reason'])
    check('visage plein cadre : la bande reste quand meme dans la zone sure',
          G.fits(r['y'], h, lab, safe), r['y'] * 1920)
    check('visage plein cadre : on evite la bouche plutot que les yeux ou le front',
          G.covered(G.text_rect(r['y'], w, h, lab), full['mouth']) < .5,
          round(G.covered(G.text_rect(r['y'], w, h, lab), full['mouth']), 3))


# ---------------------------------------------------------------- 6
def section6():
    print('\n== 6. texte enorme : rapetisse, mais jamais illisible ==')
    check('texte qui tient : facteur 1.0', near(G.fit_width(.8, '9:16'), 1.0))
    k = G.fit_width(1.6, '9:16')
    check('texte deux fois trop large : rapetisse', k < 1.0, round(k, 3))
    check('et il tient apres coup', 1.6 * k <= 1. - 2 * G.SAFE['9:16']['side'] + 1e-9, round(1.6 * k, 4))
    check('plancher d\'accessibilite : jamais sous 0.55', G.fit_width(99., '9:16') >= .55 - 1e-9,
          G.fit_width(99., '9:16'))
    check('largeur nulle : facteur 1.0', near(G.fit_width(0., '9:16'), 1.0))


# ---------------------------------------------------------------- 7
def section7():
    print('\n== 7. la cle "caption_safe" ==')
    check('true -> preset "auto"', (CAPS.configure(True) or {}).get('style') == 'auto')
    check('"auto" accepte', (CAPS.configure('auto') or {}).get('mesure') is True)
    check('"regle" accepte, et il ne mesure pas', (CAPS.configure('regle') or {}).get('mesure') is False)
    check('"n_importe_quoi" refuse', CAPS.configure('n_importe_quoi') is None)
    check('12 refuse (ni bool, ni str, ni dict)', CAPS.configure(12) is None)
    st = CAPS.configure({'style': 'auto', 'echantillons': 99})
    check('echantillons borne a 4', st and st['echantillons'] == 4, st and st['echantillons'])
    st2 = CAPS.configure({'style': 'auto', 'echantillons': -3})
    check('echantillons borne a 0', st2 and st2['echantillons'] == 0, st2 and st2['echantillons'])
    n = CAPS.notices({'caption_safe': 'pas_un_preset'})
    check('une valeur inconnue se DIT en francais', any('inconnu' in m for m in n), n)
    n2 = CAPS.notices({'caption_safe': True, 'style': 'console',
                       'shots': [{'ui': {'subs': 'off'}}]})
    check('"subs": "off" partout se dit aussi', any('aucun sous-titre' in m for m in n2), n2)
    check('sans la cle, aucun avertissement', CAPS.notices({}) == [])
    # shot_hint : le gros plan dessine de CONSOLE 2D est reconnu comme un plan serre
    hint = CAPS.shot_hint({'scene': {'type': 'face'}})
    check('console "scene.type": "face" -> plan serre', (hint.get('camera') or {}).get('shot') == 'close', hint)
    check('console "scene.type": "room" -> pas serre',
          not ((CAPS.shot_hint({'scene': {'type': 'room'}}).get('camera') or {}).get('shot')))


# ---------------------------------------------------------------- 8
def section8():
    print('\n== 8. sur la scene du defaut : la bouche passe a zero, et le plan est deterministe ==')
    import soustitre_qc as Q
    from cadrage_qc import build
    scene = os.path.join(ROOT, 'examples', 'scenes', 'portrait_peur.json')
    cache = {}
    _e, _l, eng_a = build(scene, '9:16')
    before = Q.measure(eng_a, '9:16', 2, cache)
    _e, _l, eng_b = build(scene, '9:16', [('caption_safe', True)])
    after = Q.measure(eng_b, '9:16', 2, cache)
    nb_a = len([r for r in before if r['bouche'] > .001])
    nb_b = len([r for r in after if r['bouche'] > .001])
    check(f'avant : le texte tombe sur la bouche ({nb_a}/{len(before)} images mesurees)', nb_a > 0, nb_a)
    check(f'apres : plus aucune image ({nb_b}/{len(after)})', nb_b == 0, nb_b)
    check('apres : plus aucune tete touchee', all(r['tete'] <= .001 for r in after),
          [r['t'] for r in after if r['tete'] > .001])
    check('apres : rien hors zone sure', all(r['hors'] <= .001 for r in after))
    check('le minutage n\'a pas bouge', [r['t'] for r in before] == [r['t'] for r in after])
    check('le texte n\'a pas bouge (accents FR compris)',
          [r['texte'] for r in before] == [r['texte'] for r in after])
    check('les accents sont bien la', any('È' in r['texte'] or 'É' in r['texte'] for r in after),
          [r['texte'] for r in after][:2])
    # determinisme : entrer par la DERNIERE image doit donner le meme plan qu'entrer par la premiere
    _e, _l, eng_c = build(scene, '9:16', [('caption_safe', True)])
    from PIL import Image, ImageDraw
    dr = ImageDraw.Draw(Image.new('RGB', (8, 8)))
    last = Q.sub_times(eng_c, 2)[-1]
    Q.text_box(eng_c, last[0], last[2], dr)                      # premier appel : par la fin
    plan_c = {k: v['band'] for k, v in (eng_c.caps.get('_plan') or {}).items()}
    plan_b = {k: v['band'] for k, v in (eng_b.caps.get('_plan') or {}).items()}
    check('le plan de bandes ne depend pas de l\'image par laquelle on entre', plan_b == plan_c,
          (plan_b, plan_c))
    # une seule bande pour tout l'episode ici : donc aucun saut
    check('une seule bande sur les 5 plans : le bandeau ne saute jamais',
          len(set(plan_b.values())) == 1, plan_b)
    return dict(avant_bouche=nb_a, apres_bouche=nb_b, plan=plan_b)


# ---------------------------------------------------------------- 9
def section9():
    """L'INVARIANT QUI A ATTRAPE UN VRAI DEFAUT : la zone sure ne declare jamais dangereuse une position
    que le moteur LIVRE deja. Sinon la politique deplace un sous-titre dont personne ne s'est plaint.

    Le premier `SAFE['16:9']['bottom']` valait 0.900 et refusait la position livree `low` (y=950 sur
    1080). Pire, `clear` ne regardait alors que les visages : la bande etait jugee libre, choisie, et
    l'hysteresis la propageait au plan suivant -- 65,8 % du rectangle de texte hors zone sure, mesure par
    `tools/soustitre_qc.py --aspect 16:9`. Les deux bugs sont corriges ; ces lignes les tiennent fermes."""
    print('\n== 9. la zone sure accepte toutes les positions deja livrees ==')
    from hstudio.engines.pixel3d.render import Layout
    for aspect in ('9:16', '16:9'):
        L = Layout(aspect)
        safe = G.SAFE[aspect]
        h = 56 * 1.15 / L.H          # la ligne de sous-titre pixel3d
        lab = 52. / L.H              # avec la pastille du locuteur
        for nm in ('mid', 'low', 'top'):
            y = L.sub_y[nm] / L.H
            check(f'pixel3d {aspect} : position livree "{nm}" (y={L.sub_y[nm]}) dans la zone sure',
                  G.fits(y, h, lab, safe), f"texte {L.sub_y[nm]:.0f}..{(y + h) * L.H:.0f} "
                                           f"/ zone {safe['top'] * L.H:.0f}..{safe['bottom'] * L.H:.0f}")
    for aspect, (W, H) in (('9:16', (1080, 1920)), ('16:9', (1920, 1080))):
        safe = G.SAFE[aspect]
        fs = 78 if aspect == '9:16' else 70        # console/render.subtitle
        h = fs * 1.6 / H
        for nm, fr in (('mid', .655), ('low', .8), ('top', .3)):
            check(f'console {aspect} : position livree "{nm}" (y={fr * H:.0f}) dans la zone sure',
                  G.fits(fr, h, 46. / H, safe),
                  f"texte {fr * H:.0f}..{(fr + h) * H:.0f} / zone {safe['top'] * H:.0f}..{safe['bottom'] * H:.0f}")
    # et le corollaire : une bande declaree libre est forcement dans la zone sure
    named = {'mid': 800 / 1080., 'low': 950 / 1080., 'top': 300 / 1080.}
    face = dict(rect=(.1, .9, 100 / 1080., 700 / 1080.), mouth=None, eyes=None, weight=1.)
    bad = []
    for aspect, H in (('9:16', 1920), ('16:9', 1080)):
        for hh in (40, 64, 90, 140):
            r = G.choose(named, 'mid', [face], .7, hh / float(H), 52. / H, aspect)
            if r['clear'] and not G.fits(r['y'], hh / float(H), 52. / H, G.SAFE[aspect]):
                bad.append((aspect, hh, r['band'], r['y']))
    check('une bande "libre" est toujours dans la zone sure (les deux conditions, pas une)', not bad, bad)


# ---------------------------------------------------------------- 10
def section10():
    """QUAND LA POLITIQUE NE DEPLACE RIEN, L'IMAGE EST IDENTIQUE AU BIT PRES -- cle posee comprise.

    C'est la moitie qui manquait a la section 1. La section 1 prouve que SANS la cle rien ne bouge ; celle-ci
    prouve que AVEC la cle, sur un episode ou la mesure ne trouve aucun visage sous le bandeau, la cle ne
    coute pas un seul pixel. Un aller-retour normalise rendait 800,00028 au lieu de 800 : `plan_pixel3d`
    reprend desormais le pixel exact de la bande nommee, et ces lignes le tiennent ferme.

    demo20_decors en 16:9 est le cas : neuf plans, aucun visage sous "mid", la politique conserve "mid"."""
    print('\n== 10. bande inchangee => image identique au bit pres (cle posee) ==')
    from hstudio import demos as D
    from hstudio.pipeline import make_engine, duration_of
    import copy
    demo_id, aspect = 'demo20_decors', '16:9'
    sc = D.load(demo_id)
    lines = D.timed_lines(sc['script'], float(sc.get('gap', .3)), float(sc.get('lead', .4)))
    env = D.draft_voice(sc, lines)[1]
    ep = D.episode_of(sc, lines, log=lambda *a: None)
    dur = duration_of(ep, lines)
    hs = {}
    engs = {}
    ts = None
    for tag, keyed in (('sans', False), ('avec', True)):
        e2 = copy.deepcopy(ep)
        e2.pop('caption_safe', None)
        if keyed:
            e2['caption_safe'] = 'auto'
        eng = make_engine('pixel3d', e2, lines, env, dur, aspect)
        if ts is None:
            # les instants mesures sont des MILIEUX DE REPLIQUE : une image prise entre deux repliques ne
            # porte aucun sous-titre, et comparer deux images sans sous-titre ne prouverait rien du tout.
            import soustitre_qc as Q
            ts = [g for g, _k, _s in Q.sub_times(eng, 2)][:6]
        hs[tag] = [hashlib.sha1(np.asarray(eng.frame(t)).tobytes()).hexdigest()[:16] for t in ts]
        engs[tag] = eng
    check(f'les {len(ts)} instants compares portent bien un sous-titre', len(ts) >= 4, ts)
    plan = engs['avec'].caps.get('_plan') or {}
    live = {k: p for k, p in plan.items() if not p.get('skipped')}
    check(f'{demo_id}@{aspect} : la cle est bien active', engs['avec'].caps is not None)
    check('aucun plan deplace (la mesure ne trouve aucun visage sous le bandeau)',
          live and not any(p.get('moved') for p in live.values()),
          {k: (p.get('band'), p.get('y_px')) for k, p in live.items()})
    check('aucune police rapetissee', all(near(p.get('fit', 1.), 1.) for p in live.values()),
          {k: p.get('fit') for k, p in live.items()})
    check('les hauteurs sont les pixels livres, pas des approximations',
          all(float(p['y_px']).is_integer() for p in live.values()),
          {k: p.get('y_px') for k, p in live.items()})
    check(f'{demo_id}@{aspect} : image identique au bit pres, cle posee', hs['sans'] == hs['avec'],
          list(zip(hs['sans'], hs['avec'])))


SECTIONS = {1: section1, 2: section2, 3: section3, 4: section4, 5: section5,
            6: section6, 7: section7, 8: section8, 9: section9, 10: section10}

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--section', type=int, action='append', default=[])
    ap.add_argument('--json', default='')
    a = ap.parse_args()
    want = a.section or sorted(SECTIONS)
    extra = None
    for s in want:
        r = SECTIONS[s]()
        if s == 8:
            extra = r
    print('\n' + '=' * 70)
    print(f'BILAN : {len(OK)} verts, {len(BAD)} rouges')
    for b in BAD:
        print('   ROUGE : ' + b)
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        json.dump(dict(ok=len(OK), bad=len(BAD), failures=BAD, sections=want, section8=extra),
                  open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('ecrit ' + os.path.abspath(a.json))
    sys.exit(1 if BAD else 0)
