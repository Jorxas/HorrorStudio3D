"""Offline checks of the series memory (hstudio/director/saga.py): no rendering of video, no network, no API.

It plays a real little series: 3 episodes, 2 library characters (Léa and Tom), an object kept from one episode to
the next, a fork A vs B, then a coherent following episode. It proves the three rules the module must never break:
a vote is never invented, a branch only inherits from its own ancestors, and regenerating a branch touches nothing
else. Nothing is written inside library/: the arc is saved in a temporary folder.

The stories themselves come from the deterministic MOCK fixture of director/story.py: it fills a fixed skeleton and
invents nothing. What is proved here is the memory, not the writing.

  python tools/check_saga.py
"""
import os, sys, json, copy, tempfile, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
FAIL = []
def check(name, ok, detail=''):
    print(f"{'OK   ' if ok else 'ÉCHEC'} {name}" + (f'  ({detail})' if detail and not ok else '')); ok or FAIL.append(name)

def raises(exc, fn, *a, **k):
    try: fn(*a, **k)
    except exc as e: return e
    except Exception as e: return ('autre exception', type(e).__name__, str(e))
    return None

from hstudio.director import saga as SG, story as ST
from hstudio.script import parse_script

SERIES = 'saga_verif'
CHARS = ['lea', 'tom']


# ---------------------------------------------------------------- branch paths and state


def path_checks():
    check('chemin canonique', SG.canon('a/b') == 'A/B' and SG.canon(['A', 'C']) == 'A/C' and SG.canon(None) == '')
    check('parent de A/B', SG.parent_of('A/B') == 'A' and SG.parent_of('A') == '' and SG.parent_of('') is None)
    check('ancêtres de A/B/C', SG.ancestors('A/B/C') == ['', 'A', 'A/B', 'A/B/C'])
    check('lettre de branche invalide refusée', isinstance(raises(SG.UnknownBranch, SG.canon, 'A/D'), SG.UnknownBranch))


def state_checks():
    s0 = SG.State(characters={'lea': {'hold': 'key'}}, events=['la cave est ouverte'])
    s1 = s0.evolve({'characters': {'tom': {'hold': 'flashlight'}}, 'events': ['la cave est ouverte', 'Tom a eu peur'],
                    'places': {'basement': {'visited': 1}}})
    check('evolve ne modifie pas l\'état de départ', s0.characters == {'lea': {'hold': 'key'}} and s0.events == ['la cave est ouverte'])
    check('evolve cumule les personnages', s1.holders() == {'lea': 'key', 'tom': 'flashlight'}, str(s1.holders()))
    check('evolve dédoublonne les évènements', s1.events == ['la cave est ouverte', 'Tom a eu peur'], str(s1.events))
    s2 = s1.evolve({'places': {'basement': {'visited': 1, 'changed': {'porte': 'ouverte'}}}})
    check('evolve compte les visites', s2.places['basement']['visited'] == 2 and s2.places['basement']['changed'] == {'porte': 'ouverte'})
    s3 = s2.evolve({'items': {'map': 'lea'}})
    check('un objet donné devient ce que le personnage tient', s3.characters['lea']['hold'] == 'map' and s3.items['map'] == 'lea')
    s4 = s3.evolve({'characters': {'lea': {'look': {'hat': 'cap'}, 'knows': ['le code']}}})
    s5 = s4.evolve({'characters': {'lea': {'look': {'outfit': 'coat'}, 'knows': ['le code', 'le nom']}}})
    check('l\'apparence durable se cumule', s5.characters['lea']['look'] == {'hat': 'cap', 'outfit': 'coat'}, str(s5.characters['lea'].get('look')))
    check('ce que le personnage sait se cumule sans doublon', s5.characters['lea']['knows'] == ['le code', 'le nom'], str(s5.characters['lea'].get('knows')))
    flat = SG.to_series_state(s5)
    check('état à plat lisible par les moteurs', flat['lea']['hold'] == 'map' and flat['lea']['look']['hat'] == 'cap' and 'tom' in flat, str(flat))


# ---------------------------------------------------------------- the little series


def episode(arc, path, *, genre, delta, title, seed=3, ending=''):
    """writes one episode of the series on its own branch and returns (outline, episode validé, node)"""
    br = SG.brief_for(arc, path, genre=genre, duration_s=40, voice_mode='dialogue', engine='pixel3d',
                      hero='Léa', other='Tom', n_choices=2, seed=seed, off_vote=(path == 'B'))
    o = ST.build(br, provider='mock')
    lines = ST.mock_timing(parse_script(o.to_script_text()))
    ep, W = SG.episode_for(arc, path, o, len(lines))
    node = SG.node_from_outline(arc, path, o, delta=delta, title=title, ending=ending)
    arc.put(node)
    return o, ep, node, lines, W


def series_checks(root):
    arc = SG.Arc(series=SERIES, title='Série de vérification', characters=list(CHARS))

    # ---- épisode 1 : le pilote. Léa ramasse la clé.
    o1, ep1, n1, l1, W1 = episode(arc, '', genre='horror', title='PARTIE 1',
                                  delta={'characters': {'lea': {}, 'tom': {}}, 'items': {'key': 'lea'},
                                         'places': {'basement': {'visited': 1}}, 'events': ['Léa a ramassé la clé']})
    check('épisode 1 écrit sur la branche pilote', n1.path == '' and arc.node('') is not None)
    check('épisode 1 : validate sans valeur inconnue', not [w for w in W1 if 'inconnu' in w], '; '.join(W1[:2]))
    check('épisode 1 : deux choix écrits', n1.letters() == ['A', 'B'], str(n1.letters()))
    check('épisode 1 : Léa tient la clé à la fin', n1.state().holders().get('lea') == 'key', str(n1.state().holders()))

    # ---- le vote n'est pas inventé
    e = raises(SG.VoteUndefined, arc.next_path, '')
    check('sans vote : la suite est REFUSÉE', isinstance(e, SG.VoteUndefined), str(e))
    check('le refus liste les options réellement écrites',
          isinstance(e, SG.VoteUndefined) and [o['letter'] for o in e.options] == ['A', 'B'], str(e))
    e2 = raises(SG.VoteUndefined, SG.brief_for, arc, 'A')
    check('sans vote : impossible de préparer l\'épisode suivant', isinstance(e2, SG.VoteUndefined), str(e2))
    prop = arc.proposal('')
    check('la proposition ne contient que ce qui a été écrit',
          [p['letter'] for p in prop] == ['A', 'B'] and all(p.get('reason') for p in prop), str(prop))
    check('le pilote est en attente de vote', [n.path for n in arc.waiting_for_vote()] == [''])
    check('un vote non proposé est refusé', isinstance(raises(SG.SagaError, arc.record_vote, '', 'C'), SG.SagaError))

    # ---- le public choisit A
    arc.record_vote('', 'A')
    check('après le vote, la branche suivante est A', arc.next_path('') == 'A')
    check('le pilote n\'attend plus de vote', arc.waiting_for_vote() == [])
    check('la branche A est ouverte', [n.path for n in arc.open_branches()] == [''])

    # ---- épisode 2 sur A : Tom prend la lampe. La clé de Léa doit être héritée.
    o2, ep2, n2, l2, W2 = episode(arc, 'A', genre='mystery', title='PARTIE 2', seed=1,
                                  delta={'items': {'flashlight': 'tom'}, 'events': ['Tom a pris la lampe'],
                                         'constraints': ['Léa ne lâche plus la clé']})
    inherited = ep2.get('series_state') or {}
    check('épisode 2 hérite : Léa a toujours la clé', inherited.get('lea', {}).get('hold') == 'key', str(inherited))
    check('épisode 2 : le choix précédent est rappelé dans le brief',
          'A' in (o2.brief.previous_choice or ''), repr(o2.brief.previous_choice))
    check('épisode 2 porte la série', ep2.get('series') == SERIES)
    from hstudio.acting import cast as CASTLIB
    r1, r2 = CASTLIB.resolve_cast(copy.deepcopy(ep1)), CASTLIB.resolve_cast(copy.deepcopy(ep2))
    check('épisode 2 : les personnages viennent bien de la bibliothèque',
          (r2.get('lea') or {}).get('name') == 'Léa' and (r2.get('tom') or {}).get('name'),
          str({k: (v or {}).get('name') for k, v in r2.items()}))
    check('épisode 1 et 2 : Léa a la MÊME apparence et la MÊME voix',
          r1['lea'].get('look' ) == r2['lea'].get('look') and r1['lea'].get('hair_style') == r2['lea'].get('hair_style')
          and r1['lea'].get('voice') == r2['lea'].get('voice') and r1['lea'].get('hood') == r2['lea'].get('hood'),
          str((r1['lea'].get('voice'), r2['lea'].get('voice'))))
    check('épisode 2 : Léa ET Tom tiennent un objet à la fin', n2.state().holders() == {'lea': 'key', 'tom': 'flashlight'},
          str(n2.state().holders()))

    # ---- un arc alternatif B, écrit exprès à côté
    e3 = raises(SG.SagaError, SG.brief_for, arc, 'B')
    check('la branche non votée doit être demandée exprès', isinstance(e3, SG.SagaError), str(e3))
    o3, ep3, n3, l3, W3 = episode(arc, 'B', genre='sad', title='PARTIE 2 (arc B)', seed=4,
                                  delta={'events': ['Léa est repartie sans ouvrir']})
    check('la branche B existe à côté de A', arc.node('B') is not None and arc.node('A') is not None)
    check('A est la branche votée, B est un arc alternatif', arc.is_canonical('A') and not arc.is_canonical('B'))

    # ---- AUCUNE FUITE entre branches voisines
    stA, stB = arc.state_at('A'), arc.state_at('B')
    check('A et B héritent du MÊME pilote', stA.holders() == stB.holders() == {'lea': 'key'}, f'{stA.holders()} / {stB.holders()}')
    check('la lampe prise sur A n\'existe PAS sur B', 'flashlight' not in n3.state().items and
          n3.state().holders().get('tom') is None, str(n3.state().holders()))
    check('l\'évènement de B n\'existe PAS sur A', 'Léa est repartie sans ouvrir' not in n2.state().events, str(n2.state().events))
    check('l\'évènement de A n\'existe PAS sur B', 'Tom a pris la lampe' not in n3.state().events, str(n3.state().events))
    check('la contrainte de A n\'existe PAS sur B', n3.state().constraints == [], str(n3.state().constraints))

    # ---- épisode 3 : on continue sur A après un nouveau vote
    arc.record_vote('A', 'B')
    check('la branche suivante de A est A/B', arc.next_path('A') == 'A/B')
    o4, ep4, n4, l4, W4 = episode(arc, 'A/B', genre='mystery', title='PARTIE 3', seed=2,
                                  delta={'events': ['la cave est refermée']})
    inh = ep4.get('series_state') or {}
    check('épisode 3 hérite des DEUX objets de sa branche',
          inh.get('lea', {}).get('hold') == 'key' and inh.get('tom', {}).get('hold') == 'flashlight', str(inh))
    check('épisode 3 hérite des évènements de sa branche',
          set(['Léa a ramassé la clé', 'Tom a pris la lampe']) <= set(n4.state().events), str(n4.state().events))
    check('épisode 3 n\'hérite de RIEN de la branche voisine B',
          'Léa est repartie sans ouvrir' not in n4.state().events, str(n4.state().events))
    check('épisode 3 : le brief rappelle le choix B du public', 'B' in (o4.brief.previous_choice or ''), repr(o4.brief.previous_choice))
    check('la série compte 4 épisodes écrits sur 3 branches + 1 arc alternatif', len(arc.nodes) == 4, str(sorted(arc.nodes)))

    # ---- idempotence : régénérer A ne casse rien autour
    before = json.loads(arc.to_json())
    sib_before = copy.deepcopy(arc.node('B').to_dict())
    child_before = copy.deepcopy(arc.node('A/B').to_dict())
    episode(arc, 'A', genre='mystery', title='PARTIE 2', seed=1,
            delta={'items': {'flashlight': 'tom'}, 'events': ['Tom a pris la lampe'], 'constraints': ['Léa ne lâche plus la clé']})
    check('régénérer A ne duplique pas de noeud', len(arc.nodes) == 4, str(sorted(arc.nodes)))
    check('régénérer A garde le vote déjà enregistré', arc.node('A').vote == 'B', arc.node('A').vote)
    check('régénérer A ne touche pas la branche voisine B', arc.node('B').to_dict() == sib_before)
    check('régénérer A ne supprime pas son enfant A/B', arc.node('A/B').to_dict() == child_before)
    check('régénérer A à l\'identique redonne le même arc', json.loads(arc.to_json()) == before)

    # ---- fin naturelle : une raison, pas un quota
    check('on ne peut pas déclarer finie une branche qui a une suite',
          isinstance(raises(SG.SagaError, arc.mark_ending, 'A', 'trop tôt'), SG.SagaError))
    arc.mark_ending('A/B', 'Léa a refermé la cave : l\'histoire est bouclée.')
    check('la branche A/B est terminée', arc.is_ended('A/B') and arc.node('A/B').choices == [])
    check('une branche terminée ne propose plus de suite', isinstance(raises(SG.StoryEnded, arc.next_path, 'A/B'), SG.StoryEnded))
    check('une branche terminée ne propose plus de choix', isinstance(raises(SG.StoryEnded, arc.proposal, 'A/B'), SG.StoryEnded))
    check('la fin porte une raison', 'bouclée' in arc.node('A/B').ending)
    check('une fin sans raison est refusée', isinstance(raises(SG.SagaError, arc.mark_ending, 'B', '  '), SG.SagaError))
    check('aucun nombre d\'épisodes cible dans le modèle',
          not any(k in SG.Arc.__dataclass_fields__ for k in ('length', 'n_episodes', 'target', 'total')))
    check('B reste ouvert : une fin ne ferme pas les autres arcs', not arc.is_ended('B'))

    # ---- persistance
    p = SG.save(arc, root)
    check('arc enregistré', os.path.exists(p))
    again = SG.Arc.from_dict(json.load(open(p, encoding='utf-8')))
    check('arc relu identique', again.to_dict() == arc.to_dict())
    check('JSON lisible et accentué', 'Léa' in open(p, encoding='utf-8').read())
    check('arc cohérent', arc.problems() == [], '; '.join(arc.problems()[:3]))
    return arc, (ep4, l4)


# ---------------------------------------------------------------- migrations and the existing library


def migration_checks(root):
    legacy = {'id': 'vieille_serie', 'title': 'Vieille série', 'characters': ['lea', 'tom'],
              'episodes': [{'id': 'p1', 'title': 'Partie 1', 'project': 'p1'}],
              'state': {'lea': {'hold': 'key', 'look': {'hat': 'cap'}}}}
    arc = SG.Arc.from_dict(SG.legacy_series_to_arc(copy.deepcopy(legacy)))
    check('migration v0 : la mémoire à plat devient le pilote', list(arc.nodes) == [''], str(list(arc.nodes)))
    check('migration v0 : rien n\'est perdu', arc.node('').state().holders() == {'lea': 'key'} and
          arc.node('').state().characters['lea']['look'] == {'hat': 'cap'}, str(arc.node('').state().to_dict()))
    check('migration v0 : l\'import est marqué, pas déguisé en épisode', arc.node('').generator == 'import' and
          'import' in arc.node('').ending)
    check('migration v0 : le fichier d\'origine n\'est pas modifié', legacy['state'] == {'lea': {'hold': 'key', 'look': {'hat': 'cap'}}})
    check('migration : une sauvegarde v0 sans état reste lisible', SG.Arc.from_dict({'series': 'x'}).nodes == {})
    e = raises(SG.SagaError, SG.Arc.from_dict, {'version': 99, 'series': 'x'})
    check('une sauvegarde plus récente est refusée clairement', isinstance(e, SG.SagaError) and 'version' in str(e).lower(), str(e))
    check('arc inexistant : on repart d\'un arc vide, sans rien écrire',
          SG.load('serie_qui_nexiste_pas_du_tout', root).nodes == {} and
          not os.path.exists(SG.path_of('serie_qui_nexiste_pas_du_tout', root)))
    # cast.remember() keeps its own contract: we never write library/series/<id>.json
    from hstudio.acting import cast as CAST
    check('cast.remember n\'est pas remplacé', callable(CAST.remember) and callable(CAST.ensure_series))
    before = CAST.series('tu_decides_demo')
    SG.load('tu_decides_demo', root)
    check('lire un arc ne modifie pas la série de la bibliothèque', CAST.series('tu_decides_demo') == before)


# ---------------------------------------------------------------- the memory really reaches the engine


def engine_checks(arc, last):
    """the carried object must survive all the way into the acting layer, not just the JSON"""
    import numpy as np
    from hstudio.pipeline import end_states
    ep, lines = last
    ends = end_states(copy.deepcopy(ep), lines, 'pixel3d')
    check('couche acting : Léa tient encore la clé à la fin de l\'épisode 3',
          (ends.get('lea') or {}).get('hold') == 'key', str({k: v.get('hold') for k, v in ends.items()}))
    check('couche acting : Tom tient encore la lampe', (ends.get('tom') or {}).get('hold') == 'flashlight',
          str({k: v.get('hold') for k, v in ends.items()}))
    # the same episode WITHOUT the series memory must not hand them the objects out of nowhere
    bare = copy.deepcopy(ep); bare['series_state'] = {}
    ends0 = end_states(bare, lines, 'pixel3d')
    check('sans mémoire de série, personne ne tient l\'objet', not (ends0.get('lea') or {}).get('hold'),
          str({k: v.get('hold') for k, v in ends0.items()}))


if __name__ == '__main__':
    root = tempfile.mkdtemp(prefix='hstudio_saga_')
    try:
        path_checks(); state_checks()
        arc, last = series_checks(root)
        migration_checks(root)
        engine_checks(arc, last)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print()
    if FAIL: print(f'{len(FAIL)} ÉCHEC(S) : ' + ', '.join(FAIL[:10])); sys.exit(1)
    print('Tout est bon.')
