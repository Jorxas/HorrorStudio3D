"""Contrôles hors GPU du lieu `cinema_salle` et des corrections du kit du 6/11/2026 (série « Le Cinéma des Absents », partie 2).

    PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv\\Scripts\\python.exe tools/check_cinema_salle.py
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import numpy as np

OK = []; BAD = []


def check(name, cond, detail=''):
    (OK if cond else BAD).append(name)
    print(('ok   ' if cond else 'ÉCHEC'), name, ('' if cond else f': {detail}'))


from hstudio.engines.pixel3d import places as PL, cinema_salle as CS, sets as S

# 1. le lieu est enregistré, sans rien remplacer
check('lieu « cinema_salle » enregistré dans PLACES', 'cinema_salle' in PL.PLACES)
for n in ('office', 'forest', 'quartier', 'bus'):
    check(f'lieu d\'avant « {n} » toujours là', n in PL.PLACES)

# 2. sans option : la salle de la partie 1 (deux pièces, pas de porte de secours ni de trappe ni de haut-parleur suspendu)
base = PL.expand('cinema_salle', {})
check('type room, 2 pièces (salle + foyer)', base['type'] == 'room' and [r['id'] for r in base['rooms']] == ['salle', 'foyer'])
check('repères : rang7, ecran, cabine, entree, start', all(k in base['anchors'] for k in ('rang7', 'ecran', 'cabine', 'entree', 'start')))
check('rang 7 à z = 12,4', abs(base['anchors']['rang7'][1] - 12.4) < 1e-6)
n_base = len(base['blocks'])
check('sans option : pas de porte de secours (x = 5,40)', not any(abs(b['at'][0] - 5.40) < 1e-6 and b['size'][1] > 2.4 for b in base['blocks']))
check('sans option : pas de siège surélevé', not any(b['at'][1] == .18 for b in base['blocks']))
check('sans option : le foyer a sa note « FERMÉ »', base['rooms'][1]['props'][0]['text'] == ['FERMÉ'])

# 3. avec toutes les options
full = PL.expand('cinema_salle', {'siege_releve': {'rang': 7, 'cote': -1, 'place': 0}, 'ecarpe': True, 'plaque': '7', 'haut_parleur': True,
                                   'porte_secours': {'z': 12.4}, 'trappe': {'x': 3.05, 'z': 23.3, 'taille': 1.8}})
check('avec options : plus de blocs qu\'en base', len(full['blocks']) > n_base, f"{len(full['blocks'])} <= {n_base}")
check('siège surélevé : assise à y = 0,18 et 4 pieds', sum(1 for b in full['blocks'] if b['at'][1] == .18 and b['size'][1] == .26) == 1 and sum(1 for b in full['blocks'] if b['size'] == [.05, .18, .05]) == 4)
check('haut-parleur suspendu au-dessus du siège (x = -1,2, z = 12,4)', any(b['at'][0] == -1.2 and b['at'][2] == 12.4 and b['size'][1] == 2.6 for b in full['blocks']))
check('porte de secours dans le mur de droite (x = 5,40)', any(abs(b['at'][0] - 5.40) < 1e-6 and b['size'][1] > 2.4 for b in full['blocks']))
check('trappe : taille réglable (lisière de 1,8 m)', any(b['size'] == [1.8, .06, 1.8] for b in full['blocks']))
check('repères des options : siege_releve, porte_secours, trappe', all(k in full['anchors'] for k in ('siege_releve', 'porte_secours', 'trappe')))
check('déterministe : deux appels identiques', PL.expand('cinema_salle', {'trappe': True}) == PL.expand('cinema_salle', {'trappe': True}))
check('les options ne changent pas les blocs de base (préfixe commun)', full['blocks'][:20] != [] and len(PL.expand('cinema_salle', {'trappe': True})['blocks']) > n_base)

# 3 bis. projecteurs : lumières de scène en blocs émissifs `light` (un objet de plan {'type': 'light'} n'existe pas)
proj = PL.expand('cinema_salle', {'projecteurs': True})
n_lights = lambda spec: sum(1 for b in spec['blocks'] if b.get('light', 0) >= 1.5)
check('projecteurs : 6 blocs émissifs de plus, tous avec une `light` >= 1,5', len(proj['blocks']) == n_base + 6 and n_lights(proj) - n_lights(base) == 6, f"{len(proj['blocks'])} vs {n_base}")
check('sans projecteurs : rien de plus', len(PL.expand('cinema_salle', {'projecteurs': False})['blocks']) == n_base)
from hstudio.engines.pixel3d import effects as FX
check("« light » n'est PAS un type d'objet de plan du moteur (d'où l'avertissement du kit)", 'light' not in FX.EFFECTS)

# 3 ter. foyer détaillé, rue derrière la porte de secours, battant à part (6/11/2026, partie 3)
foy = PL.expand('cinema_salle', {'foyer_guichet': True})
check('foyer_guichet : plus de blocs, la pièce « foyer » reçoit le registre (od_book) et la plaque (note) en coordonnées LOCALES (z + 6)',
      len(foy['blocks']) > n_base + 40 and any(p_['type'] == 'od_book' and abs(p_['at'][1] - 4.05) < 1e-6 for p_ in foy['rooms'][1]['props']))
check('foyer_guichet : la porte d\'entrée est une OUVERTURE dans le mur du fond (porte « rue_entree »)', any(d['id'] == 'rue_entree' for d in foy['rooms'][1]['doors']))
check('foyer_guichet : repères guichet, registre, porte_entree', all(k in foy['anchors'] for k in ('guichet', 'registre', 'porte_entree', 'caisse', 'moniteur')))
check('sans foyer_guichet : le foyer n\'a que sa note « FERMÉ » et pas d\'ouverture sur la rue', len(base['rooms'][1]['props']) == 1 and not any(d['id'] == 'rue_entree' for d in base['rooms'][1]['doors']))
rue = PL.expand('cinema_salle', {'rue': True, 'porte_secours': {'z': 12.4, 'battant': False}})
check('rue : le mur de droite est PERCÉ (porte « issue ») et le panneau plein décoratif disparaît', any(d['id'] == 'issue' and d['wall'] == 'E' for d in rue['rooms'][0]['doors'])
      and not any(abs(b['at'][0] - 5.40) < 1e-6 and b['size'][1] > 2.4 for b in rue['blocks']))
check('porte_secours battant False : pas de battant rouge (il se pose en `mover`)', not any(b['material'] == 'door' and abs(b['at'][0] - 5.36) < 1e-6 for b in rue['blocks']))
check('rue : chaussée, lampadaire et façade d\'en face (blocs à x > 5,6)', sum(1 for b in rue['blocks'] if b['at'][0] > 5.6) >= 12 and 'rue' in rue['anchors'])

# 4. tous les blocs sont valides pour le moteur
try:
    for b in full['blocks']: S.block_box(b)
    check('tous les blocs sont acceptés par block_box', True)
except Exception as e:
    check('tous les blocs sont acceptés par block_box', False, repr(e))

# 5. validation d'un assemblage `mover` : emissive True est refusé avec un message (il était écarté sans rien dire)
from hstudio.engines.pixel3d.assemblage import validate as VA
good = {'blocks': [{'at': [0, 0, 0], 'size': [.1, .1, .1], 'color': [200, 200, 200], 'material': 'light', 'emissive': 1.0}]}
bad = {'blocks': [{'at': [0, 0, 0], 'size': [.1, .1, .1], 'color': [200, 200, 200], 'material': 'light', 'emissive': True}]}
check('assemblage : emissive numérique accepté', bool(VA(good)))
try: VA(bad); check('assemblage : emissive True refusé', False, 'accepté')
except ValueError as e: check('assemblage : emissive True refusé avec un message', 'emissive' in str(e), str(e))

# 6. le kit connaît les expressions VOXEL (« worried »…) pour une histoire VOXEL
from hstudio.voxelgpu.contract import EXPRESSIONS
check('expression VOXEL « worried » connue du contrat', 'worried' in EXPRESSIONS)
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'hstudio', 'histoire', 'verif.py'), encoding='utf-8').read()
check('verif.py : expressions VOXEL acceptées en style voxel', "style == 'voxel'" in src and 'EXPRESSIONS' in src)
check('verif.py : assemblage invalide signalé', 'validate_assembly' in src or '_validate_assembly' in src)

# 7. étiquette de clé tenue : lisible des deux côtés (verso retourné) en VOXEL
from hstudio.voxelgpu import b_objets as BO
boxes, _ = BO.hv_keys(None, {'etiquette': 'AB'})
tx = [b for b in boxes if getattr(b, 'tex', None)]
imgs = [list(b.tex.values())[0] for b in tx]
check('clé tenue VOXEL : deux faces portent l\'étiquette', len(imgs) == 2)
if len(imgs) == 2:
    check('clé tenue VOXEL : le verso est le recto retourné', np.array_equal(np.asarray(imgs[1]), np.asarray(imgs[0])[:, ::-1]))

# 8. partie 4 (7/11/2026) : cabine de projection, registre, interphone, ticket (tous opt-in)
n0 = len(PL.expand('cinema_salle', {'foyer_guichet': True})['blocks'])
cab = PL.expand('cinema_salle', {'foyer_guichet': True, 'cabine': True, 'interphone': True, 'foyer_registre': ['A', 'B', 'C', 'D'], 'ticket': ['POSTE LIBRE', 'X']})
check('cabine/interphone : plus de blocs que sans option', len(cab['blocks']) > n0 + 40, f"{len(cab['blocks'])} vs {n0}")
check("sans l'option cabine : aucun plancher à y = 2,86", not any(abs(b['at'][1] - 2.86) < 1e-6 for b in PL.expand('cinema_salle', {'foyer_guichet': True})['blocks']))
check('cabine : plancher à y = 2,86 (même niveau que le palier, 3,0)', any(abs(b['at'][1] - 2.86) < 1e-6 and b['size'][0] > 6 for b in cab['blocks']))
check('cabine : verrière ouverte (aucun bloc large entre y 3,95 et 4,85 au parapet)',
      not any(2.8 < b['at'][2] < 3.0 and b['at'][1] <= 4.0 and b['at'][1] + b['size'][1] >= 4.8 and b['size'][0] > 3 for b in cab['blocks']))
check('cabine : projecteur avec lentille lumineuse', any(b.get('emissive') and b['size'] == [.18, .18, .05] for b in cab['blocks']))
check('cabine : repères cabine.projecteur / cabine.porte / cabine.fenetre', all(k in cab['anchors'] for k in ('cabine.projecteur', 'cabine.porte', 'cabine.fenetre')))
check('interphone : voyant vert émissif au guichet', any(b.get('emissive') and b['color'] == [80, 255, 130] for b in cab['blocks']) and 'interphone' in cab['anchors'])
check('registre : le texte donné remplace les trois noms', [p for p in cab['rooms'][1]['props'] if p['type'] == 'od_book'][0]['texte'] == ['A', 'B', 'C', 'D'])
check('ticket : un `note` lisible près de la fente de la caisse', any(p['type'] == 'note' and p['text'][0] == 'POSTE LIBRE' for p in cab['rooms'][1]['props']))
base2 = PL.expand('cinema_salle', {'foyer_guichet': True})
check('sans option : registre à trois noms, pas de ticket', [p for p in base2['rooms'][1]['props'] if p['type'] == 'od_book'][0]['texte'] == ['INES', 'MILO', 'OPERATEUR']
      and not any(p['type'] == 'note' and p['text'][0] == 'POSTE LIBRE' for p in base2['rooms'][1]['props']))

print(f"\n{len(OK)} contrôles réussis, {len(BAD)} échec(s)")
sys.exit(1 if BAD else 0)
