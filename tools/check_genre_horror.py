"""python tools/check_genre_horror.py [--fast]
Tests of the genre-horror lane (hstudio/voxelgpu/genre_intent.py, voxelgpu_js/engine/horror_monster.js + horror_kit.js): interpretation, creature data and poses, declared
disappearance (positive AND negative controls against the spatial verifier), mood presets, and the Pompe variants. No GPU, no network, no API. `--fast` skips the two
director builds of Pompe (about 50 s)."""
import copy, json, math, re, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu import genre_intent as G, blocking as B, stagegeo, contract as C
from hstudio.voxelgpu.films import pompe_continuite as N

ok = bad = 0


def check(name, cond, info=''):
    global ok, bad
    if cond: ok += 1; print(f'  OK   {name}')
    else: bad += 1; print(f'  FAIL {name} {info}')


def raises(fn, frag=''):
    try: fn()
    except G.IntentError as e: return frag in str(e), str(e)
    return False, 'aucune exception'


POMPE = ("L'homme qui attendait au fond du parking se tient maintenant juste derrière la vitre. Il n'a ni voiture ni parapluie. L'homme lève lentement la tête. "
         "Sous sa capuche... rien. Pas de visage. Sa main se pose contre la vitre. Le néon clignote. Il disparaît.")

print('1. interprétation')
r = G.interpret(POMPE, 'horror'); e = r['entities'][0]
check('Pompe : « sans visage / capuche » = présence surnaturelle', e['nature'] == 'supernatural' and 'sans_visage' in e['cues'] and e['human_default_forbidden'])
check('…avec une silhouette de créature, pas un humain en manteau', e['monster']['archetype'] == 'faceless_void' and e['monster']['stretch'][1] > 1.1 and e['monster']['finger_len'] > 1.5)
check('« il disparaît » : ne demande aucune marche vers une porte', r['events'][0]['requires_walk'] is False and r['events'][0]['needs_declaration'])
check('…la catégorie doit être déclarée (jamais devinée en silence)', r['events'][0]['allowed'] and r['events'][0]['how'] in G.CATEGORIES + (None,))
n = G.interpret("Un homme en manteau attend dans la nuit.", 'horror')
check('NÉGATIF : un homme en manteau qui attend la nuit reste humain', n['entities'][0]['nature'] == 'human' and not n['entities'][0]['human_default_forbidden'])
n = G.interpret("Un homme noir attend l'autobus, il sourit.", 'horror')
check("NÉGATIF : « homme noir » seul n'est PAS un monstre (peut décrire une personne noire), avertissement", n['entities'][0]['nature'] == 'ambiguous' and n['entities'][0]['monster'] is None and 'personne noire' in n['warnings'][0])
n = G.interpret("Un homme noir à capuche attend dans la nuit. Il disparaît.", 'horror')
check('« homme noir » + capuche + nuit en horreur : créature, avec avertissement sur la couleur de peau', n['entities'][0]['nature'] == 'supernatural' and 'couleur de peau' in n['warnings'][0])
n = G.interpret("Un homme à capuche attend dans la nuit.", 'comedy')
check("NÉGATIF : hors horreur, capuche seule ne fait pas de créature", n['entities'][0]['nature'] == 'human')
n = G.interpret("Il n'a pas de visage. Le vide.", 'drama')
check('deux indices forts font une créature même hors horreur', n['entities'][0]['nature'] == 'supernatural')
n = G.interpret("Marc sort par la porte. Il disparaît derrière la porte.", 'horror')
check("NÉGATIF : un acteur ordinaire qui « disparaît » est refusé comme événement surnaturel", n['events'] == [] or not n['events'][0]['allowed'])
n = G.interpret("L'homme est là. Il disparaît. L'homme n'est plus là.", 'comedy')
check("NÉGATIF : sujet humain + « disparaît » : not allowed, raison en français", n['events'] and not n['events'][0]['allowed'] and 'porte' in n['events'][0]['why'])
check('apostrophes courbes et accents : « n’a pas de visage » est reconnu', G.interpret("Il n’a pas de visage.", 'horror')['entities'][0]['nature'] == 'supernatural')
check('catégorie suggérée : lumières qui s\'éteignent → blackout ; « dans la nuit » → shadow', G.interpret("L'homme est là. Les lumières s'éteignent. L'homme disparaît.", 'horror')['events'][0]['how'] == 'blackout'
      and G.interpret("L'homme sous sa capuche, sans visage. L'homme disparaît dans la nuit.", 'horror')['events'][0]['how'] == 'shadow')

print('2. créature : données, mains, poses')
ce = G.cast_entry('faceless_void'); m = ce['look']['monster']
check('cast_entry : kind faceless (branche du rendu partagé), peau et chaussures sombres', ce['kind'] == 'faceless' and int(m['skin'][1:], 16) < 0x101010 and int(m['boots'][1:], 16) < 0x101010)
check('mains : doigts plus longs et plus fins, main plus grande que la normale', m['finger_len'] >= 1.5 and m['finger_thin'] < 1 and m['hand_scale'] > 1.1)
check('silhouette : plus haute et plus étroite, voûtée, tête penchée', m['stretch'][1] > 1.1 and m['stretch'][0] < 1 and m['hunch'] > .1 and m['head_tilt'] > .1)
check('haut du corps : un manteau long (type coat), pas de cordons ni de ceinture', ce['look']['top']['type'] == 'coat')
check('archétype inconnu : refusé en français', raises(lambda: G.monster_spec('lutin'), 'inconnu')[0])
mk = (ROOT / 'voxelgpu_js/engine/horror_monster.js').read_text(encoding='utf-8'); hk = (ROOT / 'voxelgpu_js/engine/horror_kit.js').read_text(encoding='utf-8')
jd = re.search(r'DEFAULT_MONSTER = \{(.*?)\};', mk, re.S).group(1)


def jnum(k):
    mm = re.search(k + r': (\[[^\]]*\]|[0-9a-fx.]+)', jd); v = mm.group(1)
    return json.loads(v) if v.startswith('[') else (int(v, 16) if v.startswith('0x') else float(v))


A = G.ARCHETYPES['faceless_void']
check('le miroir JS de faceless_void = les données Python', all(jnum(k) == A[k] for k in ('stretch', 'head', 'hunch', 'head_tilt', 'shoulder_drop', 'hand_scale', 'finger_len', 'finger_thin', 'finger_twitch', 'stillness', 'skin', 'hood', 'boots')))
jp = set(re.findall(r'^  (\w+): \(', mk.split('export const MONSTER_POSES')[1].split('export function buildMonster')[0], re.M))
check('les poses de Python (MONSTER_POSES) existent toutes en JS, et inversement', jp == set(G.MONSTER_POSES), (jp ^ set(G.MONSTER_POSES)))
check('NÉGATIF du bug : la peau du monstre vient APRÈS `...spec` (la teinte humaine du modèle de base ne passe plus)', re.search(r'\.\.\.spec, skin: P\.skin, brow: P\.skin', mk) is not None)
check('chaussures de monstre : bottes sombres, pas les baskets à semelle blanche', "shoes: { type: 'boot', color: P.boots }" in mk)
check('mains et doigts agrandis à la construction (la fermeture des doigts de A reste valable)', 'hand.scale.setScalar(P.hand_scale)' in mk and 'f.scale.set(P.finger_thin, P.finger_len, P.finger_thin)' in mk)
check('les couches additives ne valent que sur un corps remis à zéro cette image (pas d\'accumulation)', '_fresh' in mk and 'ch.reset = () => { reset0(); ch._fresh = true; }' in mk)
check('bras pilotés par la cinématique inverse : jamais modifiés par la voussure (_lockL/_lockR)', 'free(' in mk and '_lockL' in mk)
check('fenêtres de disparition : le corps est caché dans la fenêtre, avant tout ajout de pose', mk.index('P.vanish) { if (T >= t0') < mk.index('_fresh) return'))
check('buildFaceless : créature par défaut, ancienne figure sur `look.monster: false` / `human_hooded`', 'spec.monster === false || spec.human_hooded' in hk and 'buildHoodedHuman' in hk)
check('buildExtras appelle monsterUpdate (le rendu partagé appelle déjà extras.update à chaque image)', 'monsterUpdate(ch, T)' in hk)

print('3. disparition déclarée')
geo = stagegeo.station(N.DOORS)
ENV = N.WORLD_ENV; CUTS = [0., 26.27, 27.3, 29.7]


def plan(beats, actors=None):
    return dict(duration=60., actors=actors or {'clerk': dict(kind='human', start='caisse'), 'ghost': dict(kind='faceless', start='parking_loin')}, beats=beats)


def view(beats, actors=None):
    p2, vs, lives = G.split_plan(plan(beats, actors), geo); return G.VanishView(B.compile_plan(p2, geo), vs, lives)


V1 = dict(who='ghost', t=26.6, do='vanish', how='shadow', lights=['panels', 'neon'], until=27.3, appear='cut', at=[.6, 4.6], face=math.pi)
GO = dict(who='ghost', t=6.3, do='go', to='vitre', by=10.8)
v = view([GO, V1, dict(who='ghost', t=31.6, do='go', to=[1.75, 5.5], by=32.5), dict(who='clerk', t=28., do='look', at='ghost')])
check('créature : `shadow` dans le noir (panneaux et néon éteints à 26,6 s) + réapparition par coupe : aucun problème', not G.audit_vanishes(v, geo, world_env=ENV, cuts=CUTS), G.audit_vanishes(v, geo, world_env=ENV, cuts=CUTS))
check('…sans AUCUNE marche vers une porte : un seul déplacement avant la disparition, sa place est tenue', v.xz('ghost', 26.0) == v.xz('ghost', 26.59) and not v.visible('ghost', 26.8) and v.visible('ghost', 27.3) and v.visible('ghost', 10.))
check('…et il est à l\'endroit déclaré à la réapparition', abs(v.xz('ghost', 27.35)[0] - .6) < .01 and abs(v.xz('ghost', 27.35)[1] - 4.6) < .01)
check('chaque vie est auditée par blocking.py tel quel : 0 téléportation, 0 mur', not B.audit(v.C), B.audit(v.C))
check('la vue fusionnée expose un acteur par id (le directeur ne voit pas « ghost#1 »)', set(v.actors) == {'clerk', 'ghost'} and set(v.C.actors) == {'clerk', 'ghost', 'ghost#1'})
check('les références à l\'acteur sont résolues à la vie qui existe à ce moment (regard du pompiste après la réapparition)', any(b.get('at') == 'ghost#1' for b in G.split_plan(plan([GO, V1, dict(who='clerk', t=28., do='look', at='ghost')]), geo)[0]['beats'] if b['who'] == 'clerk'))
check('transparence : sans beat vanish, la vue = la compilation normale', G.VanishView(B.compile_plan(*[plan([GO])] + [geo]), [], {}).xz('ghost', 12.) == B.compile_plan(plan([GO]), geo).xz('ghost', 12.))
# --- négatifs : la déclaration
neg = lambda b, frag, actors=None: raises(lambda: G.split_plan(plan([GO, b], actors), geo), frag)
check('NÉGATIF : catégorie absente → refusée (jamais devinée)', neg(dict(who='ghost', t=20., do='vanish'), 'catégorie')[0])
check('NÉGATIF : catégorie inconnue', neg(dict(who='ghost', t=20., do='vanish', how='teleport'), 'inconnue')[0])
check('NÉGATIF : un acteur ordinaire ne disparaît pas dans le noir', neg(dict(who='clerk', t=20., do='vanish', how='shadow', lights=['panels']), 'ordinaire')[0])
check('NÉGATIF : un acteur ordinaire ne change pas de place par disparition (`at`)', neg(dict(who='clerk', t=20., do='vanish', how='cut', until=27.3, at=[4., 6.]), 'ordinaire')[0])
check('NÉGATIF : un acteur ordinaire ne traverse pas les murs', neg(dict(who='clerk', t=20., do='vanish', how='offscreen', through_walls=True), 'ordinaire')[0])
check('NÉGATIF : réapparition avant la disparition', neg(dict(V1, until=20.), 'avant')[0])
check('NÉGATIF : `at` sans `until`', neg(dict(V1, until=None), 'sans')[0])
check('NÉGATIF : un acteur invisible n\'agit pas (beat dans la fenêtre)', raises(lambda: G.split_plan(plan([GO, V1, dict(who='ghost', t=27., do='go', to=[1., 5.], by=28.)]), geo), 'invisible')[0])
check('NÉGATIF : deux disparitions qui se chevauchent', raises(lambda: G.split_plan(plan([GO, V1, dict(V1, t=26.8, until=28.)]), geo), 'chevauchent')[0])
_p, _vs, _lv = G.split_plan(plan([GO, dict(who='clerk', t=20., do='vanish', how='cut', until=27.3)]), geo)
check('un acteur ordinaire peut sortir par `cut` SANS changer de place : accepté (masque sur une trajectoire valide)', len(_vs) == 1 and not _vs[0]['super'] and _lv['clerk'][1][0] == 'clerk#1')
# --- négatifs : le vérificateur spatial
aud = lambda vv, **kw: G.audit_vanishes(vv, geo, world_env=kw.pop('env', ENV), cuts=kw.pop('cuts', CUTS), **kw)
codes = lambda vs: {x.code for x in vs}
mkv = lambda **o: view([GO, dict(V1, **o)])
check('NÉGATIF shadow en pleine lumière (t = 11 s : panneaux à 1) : refusé', 'pas_dans_le_noir' in codes(aud(mkv(t=11., until=12.3))))
check('NÉGATIF shadow sans `lights` : la cause est exigée', 'cause_absente' in codes(aud(mkv(lights=[]))))
check('NÉGATIF table de lumière inconnue', 'lumière_inconnue' in codes(aud(mkv(lights=['soleil']))))
check('NÉGATIF `cut` hors coupe (t = 26,6 s, coupes à 26,27 et 27,3)', 'coupe_absente' in codes(aud(mkv(how='cut', appear='cut'))))
check('`cut` sur une coupe : accepté pour une créature', not aud(view([GO, dict(V1, t=26.27, how='cut', until=27.3, lights=[])])))
check('NÉGATIF `offscreen` sans les caméras : non vérifiable (rien ne passe en silence)', 'non_vérifiable' in codes(aud(mkv(how='offscreen', appear='cut'))))
check('NÉGATIF `offscreen` alors que le cadre le montre', 'visible_à_l_écran' in codes(aud(mkv(how='offscreen', appear='cut'), in_view=lambda a, t: True)))
check('`offscreen` hors de tout cadre : accepté', not aud(mkv(how='offscreen', appear='cut'), in_view=lambda a, t: False))
check('NÉGATIF `blackout` sans coupure de lumière (elle était déjà basse)', 'coupure_absente' in codes(aud(mkv(how='blackout', appear='cut'), env=dict(ENV, panels=[[0, .05]], neon=[[0, .05]]))))
check('`blackout` : la lumière tombe de 1 à 0,05 juste avant (29,2 s) → accepté', not aud(view([GO, dict(V1, t=30., how='blackout', until=None, appear='blackout', at=None)]), env=dict(ENV, panels=[[0, 1], [28.5, 1], [29.2, .05]], neon=[[0, 1], [28.5, 1], [29.2, .05]])))
check('NÉGATIF `sudden` sans cause visible : refusé', 'cause_absente' in codes(aud(mkv(how='sudden', t=11., until=11.5, appear='cut', lights=['panels']))))
check('`sudden` avec un clignotement de lumière à ±0,6 s : accepté', 'cause_absente' not in codes(aud(mkv(how='sudden', t=25.2, until=27.3, appear='cut', lights=['panels']))))
check('NÉGATIF catégorie surnaturelle sur un acteur ordinaire dans le vérificateur', 'disparition_interdite' in codes(aud(G.VanishView(*[B.compile_plan(plan([GO]), geo), [dict(who='clerk', t=26.6, how='shadow', until=None, appear='shadow', lights=['panels'], through_walls=False, super=False)], {}]))))
check('NÉGATIF réapparition DANS le comptoir : refusée (solide)', 'solide' in codes(aud(mkv(at=[3.0, 1.2]))))
check('NÉGATIF réapparition de l\'autre côté d\'une porte fermée sans `through_walls` : refusée (passage)', 'passage' in codes(aud(mkv(at=[3.2, -9.0]))))
check('…et acceptée avec `through_walls` déclaré', 'passage' not in codes(aud(mkv(at=[3.2, -9.0], through_walls=True))))
# --- négatif de contrôle : un saut ACCIDENTEL d'un acteur normal reste une faute, un saut déclaré de créature est expliqué
EMPTY = C.empty_frame(); ix = {n: i for i, n in enumerate(C.ACTOR_COLS)}


def rows(x, z, vis=1., n=30):
    r = list(EMPTY); r[ix['x']] = x; r[ix['z']] = z; r[ix['vis']] = vis; return [list(r) for _ in range(n)]


def contract(a1, a2, kind=None):
    return dict(fps=30, actor_cols=C.ACTOR_COLS, casts={'a': ({'kind': kind} if kind else {})}, stages=[dict(id='S1', world='station', t0=0., t1=1., actors={'a': rows(*a1)}), dict(id='S2', world='station', t0=1., t1=2., actors={'a': rows(*a2)})])


acc = B.audit_contract(contract((1., 5.), (-3., 12.)), geo)
check('NÉGATIF DE CONTRÔLE : un acteur normal qui saute de 8 m à la coupe est une téléportation (audit existant)', any(x.code == 'téléportation' for x in acc), acc)
decl = [dict(who='a', t=.9, how='cut', until=1., appear='cut', super=True, through_walls=True)]
check('un saut de créature DÉCLARÉ (vanish vérifié) est expliqué par audit_declared', not [x for x in G.audit_declared(contract((1., 5.), (-3., 12.), 'faceless'), geo, decl) if x.code == 'téléportation'])
check('NÉGATIF : le même saut d\'un acteur ordinaire n\'est jamais expliqué, même « déclaré »', any(x.code == 'téléportation' for x in G.audit_declared(contract((1., 5.), (-3., 12.)), geo, [dict(decl[0], super=False)])))
check('NÉGATIF : un saut de créature NON déclaré reste une faute', any(x.code == 'téléportation' for x in G.audit_declared(contract((1., 5.), (-3., 12.), 'faceless'), geo, [])))
cc = contract((1., 5.), (1., 5.), 'faceless'); n_hidden = G.mask_contract(cc, [dict(who='a', t=.5, how='shadow', until=1.5, appear='cut', super=True)])
check('mask_contract : cache exactement la fenêtre (15 images à 30 i/s) et donne les fenêtres au peintre', n_hidden == 30 and cc['casts']['a']['look']['monster']['vanish'][0][:2] == [.5, 1.5], n_hidden)
cc2 = contract((1., 5.), (1., 5.), 'faceless')
check('NÉGATIF : une créature dessinée pendant une disparition déclarée est signalée', any(x.code == 'disparition_visible' for x in G.audit_declared(cc2, geo, [dict(who='a', t=.5, how='shadow', until=1.5, appear='cut', super=True)])))

print('4. ambiances')
check('tous les préréglages sont sans rouge imposé (panneaux, néon, liseré)', all(not G.audit_preset(n) for n in G.MOOD_PRESETS), {n: G.audit_preset(n) for n in G.MOOD_PRESETS})
G.MOOD_PRESETS['_bad'] = dict(label='x', genres=[], mood=[], look={}, env=dict(panel_red=.6, neon_col=[7., .3, .25]), light='')
check('NÉGATIF : un préréglage qui teinte le monde en rouge est refusé', len(G.audit_preset('_bad')) == 2); del G.MOOD_PRESETS['_bad']
check('tous les noms de mood existent dans le contrat (contract.MOODS)', all(m in C.MOODS for p in G.MOOD_PRESETS.values() for m, _ in p['mood']))
check('les clés de `look` sont celles que le rendu partagé accepte (liste blanche)', all(k in ('exposure', 'bloom', 'bloomRadius', 'bloomThreshold', 'sat', 'contrast', 'vignette', 'grain', 'ca', 'mblur', 'dofScale', 'tint', 'shadow_tint', 'high_tint', 'lift', 'bg', 'fog_d', 'fog_color', 'key_i', 'hemi_i', 'key_color') for p in G.MOOD_PRESETS.values() for k in p['look']))
check('aucun préréglage ne fixe une exposition ni un ombre-teinte sombre dans `look` (ils REMPLACENT la valeur calibrée : bug mesuré, image à 3 % de luminance)',
      all('exposure' not in p['look'] and (p['look'].get('shadow_tint') is None or max(int(p['look']['shadow_tint'][i:i + 2], 16) for i in (1, 3, 5)) >= 0x90) for p in G.MOOD_PRESETS.values()))
check('un genre → un préréglage (horror→dread, comedy→calm_day, romance→golden_hour)', G.mood_for('Horreur') == 'dread' and G.mood_for('comedy') == 'calm_day' and G.mood_for('romance') == 'golden_hour' and G.mood_for('inconnu') is None)
ep = dict(shots=[dict(id='a', look=dict(vignette=.9)), dict(id='b')], world_env=dict(neon=[[0, 1]]))
G.apply_preset(ep, 'dread'); check("apply_preset : la lumière de l'histoire (world_env.neon) n'est jamais écrasée, le `look` du plan gagne", ep['world_env']['neon'] == [[0, 1]] and ep['shots'][0]['look']['vignette'] == .9 and ep['shots'][1]['look']['vignette'] == .6)
check('preset(k=0) : poids de mood nuls', all(w == 0 for _, w in G.preset('dread', 0.)['mood']))
check('préréglage inconnu : refusé en français', raises(lambda: G.preset('rose'), 'inconnue')[0])
check('rim, néon et brouillard : dread est froid (pas de liseré rouge)', G.MOOD_PRESETS['dread']['env']['neon_col'][0] <= G.MOOD_PRESETS['dread']['env']['neon_col'][2] + .4 and G.MOOD_PRESETS['dread']['env']['rim_col'] == '#7f93c8')
check('horror_kit.js : les clés d\'env du préréglage sont lues (grade) pour TOUS les mondes du kit (mk enveloppe look)', all(k in hk for k in ('E.exposure_k', 'E.rim_k', 'E.fill_k', 'E.hemi_k', 'E.key_k', 'E.lamp_k', 'E.sat_k', 'E.key_dir', 'E.key_col')) and 'grade(S, En)' in hk and 'normEnv(E)' in hk)
used = {k for p in G.MOOD_PRESETS.values() for k in p['env']}
known = set(re.findall(r'E\.(\w+)', hk)) | {'exposure_k'}
check('toute clé d\'env d\'un préréglage est lue quelque part dans horror_kit.js', used <= known | {'rain', 'lamps', 'canopy', 'fog', 'fog_col', 'bg', 'lift', 'neon', 'neon_col', 'rim_col'}, used - known)

print('5. périmètre : fichiers partagés intacts')
base = '19e2211b88c2b082756e15d3d7c93dbb21e6dea7'
chg = subprocess.run(['git', 'diff', '--name-only', base, 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.split()
dirty = subprocess.run(['git', 'diff', '--name-only'], cwd=ROOT, capture_output=True, text=True).stdout.split()
# fusion branch: camplan / stagegeo / blocking / faceact / director / render_unified are integrated on purpose (B, C, perf, hooks); what must stay untouched is the contract, the film painter and the shipped film module
FORBID = ['hstudio/voxelgpu/contract.py', 'hstudio/voxelgpu/films/pompe_continuite.py']
check('contrat, peintre de film et scénario Pompe livré non modifiés depuis la base 19e2211 (le reste est intégré exprès)', not (set(FORBID) & (set(chg) | set(dirty))), set(FORBID) & (set(chg) | set(dirty)))

# the film painter gained ONE hook (demo narrative mission): the import of cite_kit.js and its worlds in the list; nothing else may change in it
num = subprocess.run(['git', 'diff', '--numstat', base, '--', 'voxelgpu_js/engine/film_unified.js'], cwd=ROOT, capture_output=True, text=True).stdout.split()
add_, del_ = (int(num[0]), int(num[1])) if len(num) >= 2 else (0, 0); body = subprocess.run(['git', 'diff', base, '--', 'voxelgpu_js/engine/film_unified.js'], cwd=ROOT, capture_output=True, text=True).stdout
check('peintre de film : seul le crochet du kit démo (cite_kit.js) a été ajouté (<= 4 lignes ajoutées, <= 2 retirées)', add_ <= 4 and del_ <= 2 and (add_ == 0 or 'cite_kit' in body), (add_, del_))
if '--fast' not in sys.argv:
    print('6. Pompe : variantes (director.build)')
    from hstudio.voxelgpu.films import pompe_genre_preview as P
    from hstudio.voxelgpu import director
    c = P.contract('vanish'); ix = {n: i for i, n in enumerate(c['actor_cols'])}
    check('« vanish » : le plan passe le contrôle avant rendu (corps, mains, portes, caméras, disparition)', c['preflight']['violations'] == [] and c['preflight']['vanishes'][0]['how'] == 'shadow')
    vis = {}
    for st in c['stages']:
        for i, r in enumerate(st['actors']['ghost']): vis[round(st['t0'] + i / 30, 3)] = r[ix['vis']]
    check('le fantôme est invisible de 26,6 s à 27,3 s et visible avant et après', vis[26.5] == 1 and vis[26.667] == 0 and vis[27.1] == 0 and vis[27.3] == 1 and vis[10.0] == 1 and vis[40.0] == 1)
    check('la fenêtre est transmise au peintre (look.monster.vanish) avec la catégorie et la réapparition', c['casts']['ghost']['look']['monster']['vanish'] == [[26.6, 27.3, 'shadow', 'cut']])
    ba = [x for x in G.audit_declared(c, stagegeo.station(N.DOORS), P.G.split_plan(dict(P.episode('vanish')['blocking']['plan'], duration=N.DUR))[1]) if x.code in ('téléportation', 'solide', 'passage')]
    check("le contrat entier passe l'audit de contrat existant (sauts, solides, passages)", not ba, ba)
    cm = P.contract('monster_dread')
    check('« monster_dread » : le même film sans disparition, 0 problème, mêmes 44 plans', cm['preflight']['violations'] == [] and len(cm['stages']) == len(c['stages']) == 44)
    check('le fantôme y est toujours visible (aucune disparition non déclarée)', all(r[ix['vis']] for st in cm['stages'] for r in st['actors'].get('ghost', [])))
    cz = copy.deepcopy(cm); sid = [x['id'] for x in cz['stages']].index('S21'); gr = cz['stages'][sid]['actors']['ghost']
    for r in gr[5:]: r[ix['x']] += 6.
    check('NÉGATIF : un fantôme qui saute de 6 m dans un plan (ghost déplacé à partir de la 6e image de S21) est vu par audit_contract', any(x.code == 'téléportation' for x in B.audit_contract(cz, stagegeo.station(N.DOORS))))
    lg = P.contract('legacy')
    check("« legacy » : la figure d'origine reste disponible (look.monster false)", lg['casts']['ghost']['look']['monster'] is False)

print(f'\n{ok} OK, {bad} échec(s)'); sys.exit(1 if bad else 0)
