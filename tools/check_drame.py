"""Contrôles hors GPU des éléments ajoutés le 9/11/2026 pour la série dramatique « Le Choix de Demain » (partie 1) :
lieux `lycee_riviere` et `cimetiere_calme`, interface `ui.messages`, casque autour du cou (`headphones: 'cou'`).

    PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv\\Scripts\\python.exe tools/check_drame.py
"""
import inspect, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import numpy as np

OK = []; BAD = []


def check(name, cond, detail=''):
    (OK if cond else BAD).append(name)
    print(('ok   ' if cond else 'ÉCHEC'), name, ('' if cond else f': {detail}'))


from hstudio.engines.pixel3d import places as PL, sets as S, lycee_riviere as LR, cimetiere_calme as CC


def inside(blocks, p):
    """is point p (x, y, z) inside one of the blocks ({'at': bottom centre, 'size'})"""
    for b in blocks:
        (x, y, z), (w, h, d) = b['at'], b['size']
        if abs(p[0] - x) <= w / 2 and y <= p[1] <= y + h and abs(p[2] - z) <= d / 2: return True
    return False


# 1. enregistrement : rien n'est remplacé
check('lieux « lycee_riviere » et « cimetiere_calme » enregistrés', 'lycee_riviere' in PL.PLACES and 'cimetiere_calme' in PL.PLACES)
for n in ('graveyard', 'river', 'city_street', 'cinema_salle', 'quartier'):
    check(f'lieu d\'avant « {n} » toujours là (même fonction)', n in PL.PLACES and PL.PLACES[n] is not LR.lycee and PL.PLACES[n] is not CC.cimetiere)

# 2. le lycée
L = PL.expand('lycee_riviere', {})
check('lycée : extérieur, ciel « sunset » par défaut', L.get('outdoor') and L.get('sky') == 'sunset')
for a in ('start', 'parvis', 'porte', 'portail', 'rue', 'passerelle', 'passerelle.milieu', 'fixation', 'atelier', 'fenetre_classe'):
    check(f'lycée : repère « {a} »', a in L['anchors'])
B = L['blocks']
check('lycée : la fenêtre de la classe est OUVERTE (centre de l\'ouverture hors de tout bloc)', not inside(B, (-7.5, 5.1, -.15)))
check('lycée : un personnage tient dans la classe (plancher à 3,4, au-dessus vide)', inside(B, (-7.5, 3.3, -.9)) and not inside(B, (-7.5, 4.5, -.9)) and not inside(B, (-7.5, 5.6, -.9)))
B0 = PL.expand('lycee_riviere', {'fenetre_classe': False})['blocks']
check('lycée : sans `fenetre_classe`, la façade est pleine', inside(B0, (-7.5, 5.1, -.15)))
hs = lambda bl: sorted((round(b['at'][0], 2), round(b['at'][1], 2)) for b in bl if b['size'][2] == .03 and b['color'] == [24, 22, 22] and b['at'][1] > 10)
check('lycée : l\'heure de l\'horloge change les aiguilles', hs(PL.expand('lycee_riviere', {'heure': '17:42'})['blocks']) != hs(PL.expand('lycee_riviere', {'heure': '09:15'})['blocks']))
hanger = lambda bl: [b for b in bl if abs(b['at'][0] - 1.4) < .01 and abs(b['at'][2] - 50.0) < .01 and b['size'][1] > .3]
check('passerelle : suspentes intactes sans fixation rompue', len(hanger(PL.expand('lycee_riviere', {'passerelle': {'fixation_rompue': False}})['blocks'])) == 1)
check('passerelle : une suspente arrachée (z 50,5) avec `fixation_rompue`',
      not [b for b in B if abs(b['at'][0] - 1.4) < .01 and abs(b['at'][2] - 50.5) < .3 and b['size'][1] > .5])
check('passerelle : le tablier n\'est pas un bloc plein (vide entre l\'eau et les planches)', not inside(B, (0., .15, 50.0)) and inside(B, (0., .4, 50.0)))
nb = len(PL.expand('lycee_riviere', {'passerelle': False})['blocks'])
check('passerelle : `passerelle: False` la retire', nb < len(B) - 100, f'{nb} contre {len(B)}')
texts = [p.get('text') for p in L['props'] if p.get('type') == 'note']
check('lycée : enseigne, passerelle et atelier lisibles (notes)', ['LYCEE', 'DES AMANDIERS'] in texts and ['PASSERELLE', 'DES TILLEULS'] in texts and ['ATELIER', 'DES RIVES'] in texts)
check('lycée : `fete` ajoute la banderole', ['FETE DE FIN', "D'ANNEE"] in [p.get('text') for p in PL.expand('lycee_riviere', {'fete': True})['props'] if p.get('type') == 'note'])
st = S.make_set('lycee_riviere', {'type': 'lycee_riviere', 'fete': True}); st.build()
check('lycée : construit par PIXEL 3D (boîtes, lumières)', len(st.base.boxes) > 500 and len(st.light_defs) > 8, f'{len(st.base.boxes)} boîtes')

# 3. le cimetière
Cm = PL.expand('cimetiere_calme', {'weather': 'rain'})
check('cimetière : extérieur, ciel couvert, pluie transmise', Cm.get('outdoor') and Cm.get('sky') == 'overcast' and Cm.get('weather') == 'rain')
for a in ('entree', 'tombe', 'devant_tombe', 'banc', 'chapelle', 'rang2'):
    check(f'cimetière : repère « {a} »', a in Cm['anchors'])
check('cimetière : la tombe porte « LINA / 18 ANS » (note gravée)', any(p.get('type') == 'note' and p.get('text') == ['LINA', '18 ANS'] for p in Cm['props']))
check('cimetière : bouquet détaillé avec la photo (od_bouquet debout, photo portrait)', any(p.get('type') == 'od_bouquet' and p.get('debout') and p.get('photo') == 'portrait' for p in Cm['props']))
check('cimetière : `fleurs: blocs` = bouquet en blocs + cadre photo', any(p.get('type') == 'od_photo_frame' for p in PL.expand('cimetiere_calme', {'tombe': {'fleurs': 'blocs'}})['props']))
Cn = PL.expand('cimetiere_calme', {'tombe': {'nom': 'MARC', 'texte': '1950-2020'}})
check('cimetière : nom et texte réglables', any(p.get('text') == ['MARC', '1950-2020'] for p in Cn['props']))
C0 = PL.expand('cimetiere_calme', {'tombe': False})
check('cimetière : `tombe: False` = aucune tombe gravée', not any(p.get('type') == 'note' for p in C0['props']))
check('cimetière : rien d\'horreur (pas de château, d\'arbre mort, de croix lumineuse)', not any(p.get('type') in ('dead_tree', 'castle_wall', 'tower', 'statue') for p in Cm['props']))
st = S.make_set('cimetiere_calme', {'type': 'cimetiere_calme'}); st.build()
check('cimetière : construit par PIXEL 3D', len(st.base.boxes) > 150, f'{len(st.base.boxes)} boîtes')

# 4. VOXEL : les deux lieux se traduisent (même spec = même objet)
from hstudio.voxelgpu import b_sets as BS
for name, spec in (('lycee_riviere', {'type': 'lycee_riviere', 'sky': 'overcast'}), ('cimetiere_calme', {'type': 'cimetiere_calme', 'weather': 'rain'})):
    b = BS.get(name, spec)
    check(f'VOXEL : {name} traduit (décor, sol, ciel)', len(b.props) >= 3 and b.env.get('ambient') == 1.45)
check('VOXEL : la pluie du cimetière devient des particules', BS.get('cimetiere_calme', {'type': 'cimetiere_calme', 'weather': 'rain'}).env.get('weather') == 'rain')

# 5. ui.messages (2D, commun aux deux styles)
from PIL import Image, ImageDraw
from hstudio.engines.pixel3d import render as R


class _Fake:
    def __init__(self, a): self.aspect = a; self.L = R.Layout(a)


def draw(m, T, a='9:16'):
    f = _Fake(a); W, H = f.L.W, f.L.H
    im = Image.new('RGB', (W, H), (120, 90, 70)); d = ImageDraw.Draw(im); R.Pixel3DEngine.messages(f, d, m, T)
    return np.asarray(im).astype(np.int32)


blank = np.asarray(Image.new('RGB', (1080, 1920), (120, 90, 70))).astype(np.int32)
m = {'nom': 'Lina', 'heure': '17:42', 'messages': [{'texte': 'Bonjour.', 'at': 0.}, {'texte': "J'ai besoin de te parler.", 'at': 2.}]}
a1, a2 = draw(m, 1.0), draw(m, 2.5)
check('messages : la carte est dessinée', np.abs(a1 - blank).sum() > 0)
check('messages : un message apparaît à son instant `at`', np.abs(a2 - a1).sum() > 0 and a2[1200:].sum() == blank[1200:].sum())
check('messages : texte long coupé en lignes, dans la carte', np.abs(draw({'nom': 'X', 'messages': ['mot ' * 40]}, 0.)[:, :100] - blank[:, :100]).sum() == 0)
check('messages : 16:9 aussi', np.abs(draw(m, 3., '16:9') - np.asarray(Image.new('RGB', (1920, 1080), (120, 90, 70))).astype(np.int32)).sum() > 0)
src = inspect.getsource(R.Pixel3DEngine.compose)
check('messages : opt-in (dessinée seulement avec ui.messages)', "if ui.get('messages'): self.messages(" in src)

# 5 bis. ui.appel (9/11/2026, partie 2 de « Le Choix de Demain ») : l'écran d'appel, commun aux deux styles
def draw_call(a, T, asp='9:16'):
    f = _Fake(asp); W, H = f.L.W, f.L.H
    im = Image.new('RGB', (W, H), (120, 90, 70)); d = ImageDraw.Draw(im); R.Pixel3DEngine.appel(f, d, a, T)
    return np.asarray(im).astype(np.int32)
ca = {'nom': 'Nora', 'sous_titre': 'Secours 112', 'couleur': [214, 72, 64], 'debut': 10, 'parle': [[0., 2.]], 'y': 170}
c1, c2, c3 = draw_call(ca, 1.0), draw_call(ca, 1.2), draw_call(ca, 3.0)
check('appel : la carte est dessinée', np.abs(c1 - blank).sum() > 0)
check("appel : l'onde de voix bouge quand la personne parle, plate sinon", np.abs(c1 - c2).sum() > 0 and np.abs(draw_call(ca, 3.0) - draw_call(ca, 3.05)).sum() == 0)
check('appel : le minuteur avance (10 s + temps du plan)', np.abs(draw_call(ca, 2.5) - draw_call(ca, 3.6)).sum() > 0)
check('appel : « sonne » et « termine » dessinés autrement', np.abs(draw_call(dict(ca, etat='sonne'), 1.) - c1).sum() > 0 and np.abs(draw_call(dict(ca, termine=.5), 1.) - c1).sum() > 0)
check('appel : la carte reste dans la moitié haute (visages cadrés en bas)', c1[1000:].sum() == blank[1000:].sum())
check("appel : sortant « appelle », puis « pas de réponse » à l'instant donné ; « décroche » passe en cours", np.abs(draw_call(dict(ca, etat='appelle'), 1.) - c1).sum() > 0
      and np.abs(draw_call(dict(ca, etat='appelle', sans_reponse=1.5), 1.) - draw_call(dict(ca, etat='appelle', sans_reponse=1.5), 1.6)).sum() > 0
      and np.abs(draw_call(dict(ca, etat='sonne', decroche=.5), 1.) - c1).sum() == 0)
check('appel : 16:9 aussi', np.abs(draw_call(ca, 1., '16:9') - np.asarray(Image.new('RGB', (1920, 1080), (120, 90, 70))).astype(np.int32)).sum() > 0)
check('appel : opt-in (dessiné seulement avec ui.appel)', "if ui.get('appel'): self.appel(" in src)

# 5 ter. lycee_riviere : le préau (option `preau`)
from hstudio.engines.pixel3d import lycee_riviere as LR_
l0, l1 = LR_.lycee({'type': 'lycee_riviere'}), LR_.lycee({'type': 'lycee_riviere', 'preau': True})
check('préau : absent par défaut (lieu inchangé)', len(l0['blocks']) == len(LR_.lycee({'type': 'lycee_riviere', 'preau': False})['blocks']) and 'preau' not in l0['anchors'])
check('préau : toit, piliers, mur, bancs et repères avec `preau`', len(l1['blocks']) > len(l0['blocks']) + 10 and all(k in l1['anchors'] for k in ('preau', 'preau.banc', 'preau.banc2'))
      and sum(1 for p in l1['props'] if p.get('type') == 'bench') == sum(1 for p in l0['props'] if p.get('type') == 'bench') + 2)
roof = [b for b in l1['blocks'] if abs(b['at'][1] - 3.2) < 1e-6 and b['size'][0] > 9]
check("préau : on tient debout dessous (toit à 3,2 m) et le banc est à l'abri", roof and inside(l1['blocks'], (18.4, 1.0, .4)) is False)
check('préau : hors de la façade du lycée (x > 15,4), le parvis reste libre', all(b['at'][0] - b['size'][0] / 2 >= 15.3 for b in LR_.preau_blocks({})))

# 6. casque autour du cou
from hstudio.engines.pixel3d import assets as A
hp = lambda v: [b for b in A.figure(0., 0., headphones=v, backpack=False) if tuple(int(round(float(c) * 255)) for c in b.col[:3]) == (26, 26, 32)]
neck, head = hp('cou'), hp(True)
check('PS1 : casque au cou sous la tête (y < 1,5), pas sur les oreilles', neck and all(b.hi[1] < 1.5 for b in neck), str([(round(float(b.lo[1]), 2), round(float(b.hi[1]), 2)) for b in neck]))
check('PS1 : casque sur la tête inchangé (headphones=True)', head and any(b.lo[1] > 1.55 for b in head))
from hstudio.voxelgpu import b_chars as BC
v1 = BC.resolve('x', {'outfit': 'hoodie', 'headphones': True}); v0 = BC.resolve('x', {'outfit': 'hoodie'})
v2 = BC.resolve('x', {'outfit': 'hoodie', 'headphones': 'cou'})
check('VOXEL : sans « cou », le personnage est identique (headphones=True ignoré comme avant)', v1.get('bx') == v0.get('bx') and v1.get('look') == v0.get('look'))
hb = (v2.get('bx') or {}).get('head') or []
check('VOXEL : « cou » ajoute le casque sous la tête', len(hb) >= 3 and all(b['y'] < -.3 for b in hb[-5:]))

# 7. le kit : `apercu --habille` (images VOXEL avec l'habillage final), opt-in
from hstudio.histoire import rendu as RD_, apercu as AP_, cli as CLI_
check('kit : apercu --habille branché (cli -> apercu -> voxel_stills), désactivé par défaut',
      inspect.signature(RD_.voxel_stills).parameters['habille'].default is False and inspect.signature(AP_.make).parameters['habille'].default is False
      and "'--habille'" in inspect.getsource(CLI_))
check('kit : l\'habillage passe par le même compose que le rendu', 'eng.compose(' in inspect.getsource(RD_.voxel_stills))

# 8. règle du propriétaire (9/11/2026) : la miniature ouvre la vidéo livrée pendant un très court instant (étape livrer), mesurée sur le fichier
import subprocess, tempfile
from PIL import Image as _Im
from hstudio.histoire import livraison as LV
check('livrer : miniature au début par défaut (0,4 s), coupée par MINIATURE_DEBUT = 0', abs(LV.MINIATURE_DEBUT - .4) < 1e-9 and "getattr(mod, 'MINIATURE_DEBUT'" in inspect.getsource(LV.deliver))
with tempfile.TemporaryDirectory() as td:
    v = os.path.join(td, 'v.mp4'); w = os.path.join(td, 'a.wav'); th = os.path.join(td, 'm.png'); o1 = os.path.join(td, 'o1.mp4'); o2 = os.path.join(td, 'o2.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=0x2a6a3a:s=108x192:r=30:d=2', '-pix_fmt', 'yuv420p', v], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=f=440:d=2', w], check=True)
    _Im.new('RGB', (72, 128), (230, 60, 160)).save(th)
    LV.mux(v, w, o1, 2.0, th, .4, (108, 192)); LV.mux(v, w, o2, 2.0)
    check('livrer : la miniature est à l\'image au début (mesurée), plus après', LV.thumb_shown(o1, th, (108, 192), .1) < 22. and LV.thumb_shown(o1, th, (108, 192), 1.0) > 60.)
    check('livrer : sans miniature, l\'image est copiée telle quelle (pas de miniature)', LV.thumb_shown(o2, th, (108, 192), .1) > 60.)
    check('livrer : une miniature d\'un autre format n\'est pas posée (9:16 sur 16:9)', LV.thumb_fits(th, (108, 192)) and not LV.thumb_fits(th, (192, 108)))

# 9. décision du propriétaire (9/11/2026) : jamais de flou en VOXEL (profondeur de champ coupée par le kit ; clés opt-in du peintre)
from hstudio.histoire import projet as PJ_
from hstudio.voxelgpu import from_ps1 as FP_
class _M: TITRE = 'T'; LIEUX = {'x': {'type': 'corridor'}}; CAST = {}; STYLE = 'voxel'; EPISODE = {}
class _P(_M): STYLE = 'ps1'
class _K(_M): EPISODE = {'dof': .35}
ev, ep_ = PJ_._episode(_M, [], '', 10.), PJ_._episode(_P, [], '', 10.)
check('kit : histoire VOXEL nette (dof 0, mblur faible), PS1 sans ces clés', ev.get('dof') == 0. and ev.get('mblur', 1) < .1 and 'dof' not in ep_)
check('kit : EPISODE peut remettre la profondeur de champ', PJ_._episode(_K, [], '', 10.).get('dof') == .35)
check('peintre : dof / mblur lus sur l\'épisode ou le plan (absents = valeurs du peintre)', "for kk in ('dof', 'mblur')" in inspect.getsource(FP_.build))

print(f'\n{len(OK)}/{len(OK) + len(BAD)} OK')
sys.exit(1 if BAD else 0)
