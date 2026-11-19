"""Offline checks of the story layer (hstudio/director/story.py): no rendering, no network, no API key.

It proves the bridge, not the writing: a Brief becomes an Outline whose beats carry camera/action intentions, the
outline becomes the EXISTING script format (hstudio/script.py) and an episode that hstudio/director/validate.py
accepts for BOTH engines, with every intention still there afterwards. The outlines used here come from the
deterministic MOCK fixture: it invents nothing, it only lets the conversion be tested for free.

  python tools/check_story.py
"""
import os, sys, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
FAIL = []
def check(name, ok, detail=''):
    print(f"{'OK   ' if ok else 'ÉCHEC'} {name}" + (f'  ({detail})' if detail and not ok else '')); ok or FAIL.append(name)

from hstudio.director import story as ST
from hstudio.director.validate import validate, SHOTS, MOVES2, SCENES, FACES
from hstudio.script import parse_script


def vocabulary_checks():
    """the story layer may never name something the engines do not have"""
    from hstudio.engines.pixel3d.sets import PLACE_TYPES
    from hstudio.engines.pixel3d import world as WD
    from hstudio.audio import music as MU, ambience as AMB
    for g, look in ST.GENRES.items():
        check(f'genre {g} : musique connue', look['music'] in MU.NAMES, look['music'])
        check(f'genre {g} : décors connus', all(p in PLACE_TYPES for p in look['places']), str(look['places']))
        check(f'genre {g} : expression connue', look['face'] in FACES, look['face'])
        check(f'genre {g} : ambiance connue', look['ambience'] in AMB.AMBIENCES, look['ambience'])
        check(f'genre {g} : météo connue', look['weather'] in WD.WEATHERS + ('none',), look['weather'])
    check('intentions caméra connues', all(s in SHOTS and m in MOVES2 for s, m in ST.ROLE_CAMERA.values()), str(ST.ROLE_CAMERA))
    check('scènes CONSOLE connues', set(ST.CONSOLE_SCENE.values()) <= SCENES, str(set(ST.CONSOLE_SCENE.values()) - SCENES))


def mock_checks():
    b = ST.Brief(genre='horror', duration_s=60, seed=3)
    a, c = ST.mock_outline(b), ST.mock_outline(b)
    check('MOCK déterministe (même brief, même plan)', a.to_json() == c.to_json())
    check('MOCK explicitement étiqueté', a.is_mock and a.summary.startswith(ST.MOCK_TAG) and a.generator == 'mock', a.summary[:40])
    d = ST.mock_outline(ST.Brief(genre='horror', duration_s=60, seed=4))
    check('MOCK : la graine change le décor', d.place != a.place, f'{a.place} / {d.place}')
    o = ST.Outline.from_json(a.to_json())
    check('Outline sérialisable aller-retour', o.to_dict() == a.to_dict())
    check('Brief sérialisable aller-retour', ST.Brief.from_dict(b.to_dict()) == b)
    check('Beat sérialisable aller-retour', ST.Beat.from_dict(a.beats[0].to_dict()) == a.beats[0])


def _calls_no_api():
    """build(provider='mock') must not reach providers.call at all"""
    from hstudio.director import providers
    old = providers.call
    providers.call = lambda *a, **k: (_ for _ in ()).throw(AssertionError('appel API interdit'))
    try:
        o = ST.build(ST.Brief(genre='mystery', duration_s=45), provider='mock')
        return bool(o.beats)
    except AssertionError:
        return False
    finally:
        providers.call = old


def outline_checks():
    check('aucun appel fournisseur en mode mock', _calls_no_api())
    for genre in ST.GENRES:
        for mode in ST.VOICE_MODES:
            for dur, nc in ((30, 2), (60, 2), (120, 3)):
                br = ST.Brief(genre=genre, duration_s=dur, voice_mode=mode, n_choices=nc, seed=5)
                o = ST.mock_outline(br); P = o.problems()
                check(f'plan {genre}/{mode}/{dur}s/{nc} choix : cohérent', not P, '; '.join(P[:3]))
                check(f'plan {genre}/{mode}/{dur}s : durée indicative tenue',
                      abs(o.seconds() - dur) <= dur * ST.DURATION_TOL, f'{o.seconds():.0f} s')
    o = ST.mock_outline(ST.Brief(voice_mode='voice'))
    check('voix off : aucune réplique attribuée', not o.speakers())
    o = ST.mock_outline(ST.Brief(voice_mode='dialogue'))
    check('dialogue : chaque ligne a un locuteur', all(b.speaker for b in o.beats))
    o = ST.mock_outline(ST.Brief(voice_mode='hybrid'))
    check('hybride : voix off ET répliques', any(b.speaker for b in o.beats) and any(not b.speaker for b in o.beats))


def choice_checks():
    for nc in (2, 3):
        o = ST.mock_outline(ST.Brief(genre='adventure', duration_s=60, n_choices=nc))
        check(f'{nc} choix produits', len(o.choices) == nc, str(len(o.choices)))
        check(f'{nc} choix : cartes <= 12 caractères', all(len(l) <= 12 for c in o.choices for l in c.card()),
              str([c.card() for c in o.choices]))
        check(f'{nc} choix : tous raisonnés', all(c.reason.strip() for c in o.choices))
        keys = [ST.slug(c.label) for c in o.choices] + [ST.slug(c.reason) for c in o.choices]
        check(f'{nc} choix : sémantiquement différents', len(set(keys)) == len(keys), str(keys))
        ep = o.to_episode()
        ui = next((s['ui']['choice'] for s in ep['shots'] if (s.get('ui') or {}).get('choice')), None)
        check(f'{nc} choix : carte ui.choice dans l\'épisode', ui is not None and all(c.letter in ui for c in o.choices), str(ui))
        check(f'{nc} choix : branches conservées dans l\'épisode', len(ep.get('choices') or []) == nc)


def bridge_checks():
    """the two real bridges: script.parse_script and director.validate.validate, for both engines"""
    for engine in ('pixel3d', 'console'):
        for mode in ('voice', 'dialogue', 'hybrid'):
            br = ST.Brief(genre='horror' if engine == 'pixel3d' else 'mystery', duration_s=60,
                          voice_mode=mode, engine=engine, n_choices=2, seed=2)
            o = ST.mock_outline(br)
            lines = parse_script(o.to_script_text())
            check(f'{engine}/{mode} : 1 beat = 1 ligne du script existant', len(lines) == len(o.beats),
                  f'{len(lines)} lignes pour {len(o.beats)} beats')
            check(f'{engine}/{mode} : textes du script alignés',
                  all(l['text'] == b.script_line() for l, b in zip(lines, o.beats)),
                  str([(l['text'], b.script_line()) for l, b in zip(lines, o.beats) if l['text'] != b.script_line()][:1]))
            ep = o.to_episode(len(lines))
            vep, W = validate(ep, len(lines), br.resolve_engine())
            bad = [w for w in W if 'inconnu' in w or 'inconnue' in w]
            check(f'{engine}/{mode} : validate sans valeur inconnue', not bad, '; '.join(bad[:3]))
            lost = o.check_episode(vep)
            check(f'{engine}/{mode} : aucune intention perdue après validate', not lost, '; '.join(lost[:3]))
            cov = [s['lines'] for s in vep['shots']]
            check(f'{engine}/{mode} : couverture contiguë de toutes les lignes',
                  cov[0][0] == 0 and cov[-1][1] == len(lines) - 1 and all(cov[i + 1][0] == cov[i][1] + 1 for i in range(len(cov) - 1)),
                  str(cov[:3]))
            check(f'{engine}/{mode} : notes d\'intention présentes',
                  all((s.get('intent') or {}).get('note') for s in vep['shots']))
            if engine == 'console':
                check('console : chaque plan a une scène connue', all((s.get('scene') or {}).get('type') in SCENES for s in vep['shots']))
            else:
                check('pixel3d : chaque plan a un décor connu', all(s.get('set') == o.place for s in vep['shots']))
            check(f'{engine}/{mode} : épisode sérialisable JSON', isinstance(json.dumps(vep, ensure_ascii=False), str))


def planner_checks():
    """the V3 capability planner must be able to read the outline's text (no crash, a real report)"""
    from hstudio.capabilities import planner
    o = ST.mock_outline(ST.Brief(genre='adventure', duration_s=45))
    rep = planner.plan(o.to_script_text(), engine='pixel3d')
    check('planner V3 : rapport sur le texte du plan', isinstance(rep, dict) and 'needs' in rep, str(type(rep)))


if __name__ == '__main__':
    vocabulary_checks(); mock_checks(); outline_checks(); choice_checks(); bridge_checks(); planner_checks()
    print()
    if FAIL: print(f'{len(FAIL)} ÉCHEC(S) : ' + ', '.join(FAIL[:10])); sys.exit(1)
    print('Tout est bon.')
