"""Les personnages des banques importées, REFONDUS dans le système de personnages du studio.

Un personnage importé (Mini Mike : figurines à grosse tête ; KayKit : aventuriers et squelettes) est une figure rigide : il ne marche pas, ne parle pas, et son style (voxels
« Lego ») ne ressemble pas aux corps, aux visages et aux tenues de VOXEL / `b_chars.py`. On ne le peint donc pas : on LIT ce qu'il est et on le RECRÉE avec nos pièces.

  1. analyse des couleurs du modèle par bandes de hauteur (peau = couleur du visage, cheveux ou couvre-chef = haut de la tête, haut du corps, bas du corps, chaussures) ;
  2. table de correspondance par nom : le métier ou le rôle (religieuse, infirmière, policier, zombie, squelette mage...) choisit la tenue, le chapeau, la coiffure, l'objet en main
     parmi ceux du studio (12 tenues, 15 chapeaux, 7 coiffures, 26 objets, 28 personnages prêts) ;
  3. le résultat est un `cast` ordinaire (clés de `b_chars.py`), écrit dans `voxelgpu_js/assets_vox/<banque>/LOOKS.json`.

Utilisation dans un épisode voxel : `casts: {"nonne": {"b_look": "mmmm/chr_nun"}}` ; toute clé écrite à côté surcharge le look (`{"b_look": "mmmm/chr_nun", "skin": "#c88c64", "hold": "book"}`).
Le personnage obtenu est un vrai acteur du studio : il marche, parle, change de visage (43 expressions), prend la lumière comme les autres.

Licence : un look est une IDÉE (métier, tenue, couleurs) lue sur le modèle, jamais sa géométrie ni ses voxels ; la mention de la banque d'origine est gardée dans le catalogue (`credit_required`)
par prudence : l'utilisateur décide de la publier ou non. Les banques CC0 n'exigent rien.
"""
import colorsys, json, re
from collections import defaultdict
from pathlib import Path
from . import vox_import as VI

# fraction de la hauteur où commence la tête : figurines à grosse tête (Mini Mike) / proportions normales (KayKit)
HEAD_FROM = {'mmmm': .54, 'kk_adventurers': .74, 'kk_skeletons': .74}
BANK_CHARS = ('mmmm', 'kk_adventurers', 'kk_skeletons')
NOT_CHARACTER = re.compile(r'^(alien_(egg|saucer|lift|tool)|chr_bedroll)')
KK_CHARS = {'kk_adventurers': ('barbarian', 'knight', 'mage', 'rogue', 'rogue_hooded'), 'kk_skeletons': ('skeleton_minion', 'skeleton_mage', 'skeleton_rogue', 'skeleton_warrior')}
LOOKS = VI.BANKS


def _q(c): return (c[0] >> 5, c[1] >> 5, c[2] >> 5)


def _rgb(c): return ((c >> 16) & 255, (c >> 8) & 255, c & 255)


def _dist(a, b): return sum((x - y) ** 2 for x, y in zip(a, b)) ** .5


def _dominant(cnt, skip=None, skip_dark=False, d=34):
    """couleur dominante (poids cumulé) d'un dictionnaire {(r, g, b): poids}, hors des couleurs proches de `skip`"""
    bins = defaultdict(lambda: [0., [0., 0., 0.]])
    for c, w in cnt.items():
        if skip and any(_dist(c, s) < d for s in skip): continue
        if skip_dark and max(c) < 46: continue
        b = bins[_q(c)]; b[0] += w; b[1] = [b[1][i] + c[i] * w for i in range(3)]
    if not bins: return None
    w, s = max(bins.values(), key=lambda v: v[0]); return tuple(int(round(v / w)) for v in s)


def _skinlike(c):
    h, sa, v = colorsys.rgb_to_hsv(*(x / 255. for x in c)); return h <= .12 and sa >= .12 and v >= .28 and not (sa > .9 and v > .8)      # beige à brun foncé ; l'orangé vif d'un casque n'en est pas


def _skin_of(face):
    """la couleur de peau du visage : la teinte « peau » dominante si elle pèse au moins le quart du visage (un chapeau blanc ou des lunettes ne doivent pas l'emporter), sinon la couleur dominante (peaux vertes, bleues)"""
    tot = sum(face.values()) or 1.; sk = {c: w for c, w in face.items() if _skinlike(c)}
    if sk and sum(sk.values()) >= .04 * tot and sum(1 for w in sk.values() if w) and sum(sk.values()) >= 2: return _dominant(sk)
    return _dominant(face, skip_dark=True) or (240, 168, 116)


def analyze(path, head_from=.5):
    """un .vox de personnage -> les couleurs lues par bandes : skin, hair (sous un chapeau), headtop (chapeau ou cheveux du dessus), top, accent, pants, shoes + `ratio` (largeur / hauteur)"""
    m = VI.load(path); boxes = m['boxes']; ys0 = min(b['y0'] for b in boxes); H = max(b['y0'] + b['h'] for b in boxes) - ys0
    xs0 = min(b['x0'] for b in boxes); xs1 = max(b['x0'] + b['w'] for b in boxes)
    # trois « photos » du modèle : de face (couleur de la matière la plus avancée en z pour chaque cellule x, y), de dos (la plus reculée) et de dessus (la plus haute pour chaque x, z)
    front, back, topv = {}, {}, {}
    for b in boxes:
        c = _rgb(b['color']); z1 = b['z0'] + b['d']; y1 = b['y0'] + b['h']
        for x in range(b['x0'], b['x0'] + b['w']):
            for y in range(b['y0'], y1):
                if (x, y) not in front or z1 > front[(x, y)][0]: front[(x, y)] = (z1, c)
                if (x, y) not in back or b['z0'] < back[(x, y)][0]: back[(x, y)] = (b['z0'], c)
            for z in range(b['z0'], z1):
                if (x, z) not in topv or y1 > topv[(x, z)][0]: topv[(x, z)] = (y1, c)
    face, torso, legs, shoes, hairb, topc = (defaultdict(float) for _ in range(6))
    for (x, y), (_, c) in front.items():
        t = (y + .5 - ys0) / H
        if t >= head_from:
            u = (t - head_from) / (1 - head_from)
            if .1 <= u <= .75: face[c] += 1
        elif t >= .30: torso[c] += 1
        elif t >= .08: legs[c] += 1
        else: shoes[c] += 1
    for (x, y), (_, c) in back.items():
        t = (y + .5 - ys0) / H
        if t >= head_from and (t - head_from) / (1 - head_from) < .9: hairb[c] += 1
    for (x, z), (y1, c) in topv.items():
        if (y1 - ys0) / H >= head_from + .55 * (1 - head_from): topc[c] += 1
    skin = _skin_of(face)
    headtop = _dominant(topc, skip=[skin]) or skin
    hair = _dominant(hairb, skip=[skin]) or headtop
    top = _dominant(torso) or (90, 90, 100); accent = _dominant(torso, skip=[top]) or top
    pants = _dominant(legs) or (44, 44, 50); sh = _dominant(shoes) or (30, 30, 34)
    return dict(skin=skin, hair=hair, headtop=headtop, top=top, accent=accent, pants=pants, shoes=sh, ratio=round((xs1 - xs0) / H, 2), height=int(H))


# ---------------------------------------------------------------------------------------------------------------- correspondance par nom
# clés : celles de b_chars.py. Une valeur '@nom' est une couleur lue sur le modèle : @skin @hair @headtop @top @accent @pants @shoes.
# Sans règle de couleur, `colorize()` en pose de raisonnables : peau, cheveux, haut (`hood`), bas (`jeans`), couleur du chapeau.
R = {
    'army': dict(outfit='uniform', hat='helmet', hair_style='short'),
    'army4': dict(outfit='uniform', hat='helmet', hold='torch'),
    'base': dict(outfit='tshirt', hair_style='bald'),
    'beardo1': dict(outfit='shirt', beard=True), 'beardo2': dict(outfit='shirt', beard=True, hat='cap'),
    'beardo3': dict(outfit='robe', hat='hood', hair_style='bald', beard=True), 'beardo4': dict(outfit='robe', hat='hood', hair_style='bald', beard=True),
    'beau': dict(outfit='shirt', beard=True), 'bridget': dict(outfit='tshirt', hair_style='long'), 'bro': dict(outfit='tshirt', hair_style='spiky'),
    'brookie': dict(outfit='tshirt', hair_style='long'), 'butcher': dict(outfit='apron', beard='mustache', hair_style='short'),
    'chef': dict(outfit='apron', hat='chef', hair_style='bald'), 'cop': dict(outfit='uniform', hat='police'), 'riotcop': dict(outfit='armor', hat='helmet', hold='shield'),
    'costume1': dict(outfit='tshirt', hat='party'), 'costume2': dict(outfit='tshirt', hat='party'), 'costume3': dict(outfit='coat', hat='tophat'), 'costume4': dict(outfit='dress'),
    'eskimo': dict(outfit='coat', hat='hood'), 'fatkid': dict(outfit='tshirt', hair_style='short', scale=.9),
    'goth': dict(outfit='coat', hair_style='long'), 'hazmat': dict(outfit='spacesuit', hat='astronaut', skin=[226, 172, 124]), 'headphones': dict(outfit='hoodie', hair_style='short'),
    'hobo1': dict(outfit='coat', hat='beanie'), 'hunter': dict(outfit='coat', hat='cap'),
    'janitor': dict(outfit='uniform', hat='cap'), 'lady1': dict(outfit='dress', hair_style='long'), 'lady2': dict(outfit='dress', hair_style='bun'), 'lady3': dict(outfit='dress', hair_style='long'),
    'lady4': dict(outfit='dress', hair_style='curly'), 'mailman': dict(outfit='uniform', hat='cap', backpack=True), 'mayor': dict(outfit='suit', hat='tophat'),
    'mechanic': dict(outfit='apron', hat='cap'), 'mike': dict(outfit='hoodie', hair_style='short'), 'mission1': dict(outfit='suit', glasses='sun'), 'mission2': dict(outfit='suit', glasses='sun'),
    'naked': dict(outfit='tshirt', hair_style='short', dress=True), 'naked2': dict(outfit='tshirt', hair_style='short', dress=True, skin=[252, 204, 152], hair=[100, 48, 0], beard=True), 'nun': dict(outfit='robe', hat='hood', hair_style='bald'), 'nurse': dict(outfit='tshirt', hair_style='bun'),
    'paramedic': dict(outfit='uniform', hat='cap'), 'ponytail': dict(outfit='tshirt', hair_style='ponytail'), 'priest': dict(outfit='robe', hold='book', hair_style='short'),
    'punk': dict(outfit='coat', hair_style='spiky'), 'raver': dict(outfit='tshirt', hair_style='spiky'), 'robot': dict(b_preset='robot'), 'scientist': dict(outfit='lab_coat', glasses=True),
    'sign': dict(outfit='tshirt', hold='map'), 'sports': dict(outfit='tshirt', hold='ball'), 'suit': dict(outfit='suit', hair_style='short'), 'sumo': dict(outfit='tshirt', hair_style='bun', scale=1.12),
    'super': dict(outfit='tshirt', cape='@accent'), 'thief': dict(outfit='hoodie', hat='beanie', hold='bag'), 'worker': dict(outfit='uniform', hat='helmet'),
    'zombie': dict(b_preset='zombie'),
    # extraterrestres et créatures de la banque : on prend le préréglage le plus proche, les couleurs viennent du modèle
    'alien_bot': dict(b_preset='robot'), 'alien_crawl': dict(b_preset='alien', skin='@top'), 'alien_engi': dict(b_preset='alien'), 'alien_eye': dict(b_preset='alien'), 'alien_infected': dict(b_preset='zombie'),
    # KayKit
    'barbarian': dict(outfit='armor', hair_style='long', beard=True, hold='sword', skin=[190, 140, 104]), 'knight': dict(b_preset='knight', skin=[226, 172, 124]), 'mage': dict(b_preset='wizard', skin=[226, 172, 124]),
    'rogue': dict(outfit='coat', hat='hood', hold='sword', skin=[226, 172, 124]), 'rogue_hooded': dict(outfit='coat', hat='hood', hold='sword', skin=[214, 160, 116]),
    'skeleton_minion': dict(b_preset='skeleton'), 'skeleton_mage': dict(b_preset='skeleton', hat='wizard', hold='staff'), 'skeleton_rogue': dict(b_preset='skeleton', hat='hood', hold='sword'),
    'skeleton_warrior': dict(b_preset='skeleton', hat='helmet', hold='sword'),
}
# bas du corps de ces rôles : la couleur du `jeans` reste celle du modèle ; la peau n'est pas recolorée pour les squelettes et les robots (le préréglage a la sienne)
KEEP_PRESET_SKIN = ('skeleton', 'robot')


def rule_for(name):
    """`chr_nun` -> sa règle ; `chr_army1a` / `chr_cop2` / `alien_engi2c` -> celle de la famille"""
    n = re.sub(r'^chr_', '', name)
    if n in R: return n, R[n]
    base = re.sub(r'(?<=\d)[a-d]$', '', n)                                  # image 1a / 1b d'une même figurine
    if base in R: return base, R[base]
    fam = re.sub(r'\d+[a-d]?$', '', n)
    if fam in R: return fam, R[fam]
    fam2 = re.sub(r'\d+[a-d]?$', '', name)                                  # alien_bot1 -> alien_bot
    if fam2 in R: return fam2, R[fam2]
    return None, None


CLOTHES = [(200, 64, 64), (62, 92, 150), (222, 220, 214), (62, 122, 84), (186, 152, 64), (96, 96, 104), (150, 90, 150), (210, 120, 60)]
JEANS = [(50, 60, 92), (44, 44, 50), (84, 78, 66), (60, 70, 100)]


def _dress(a, skin, rule):
    """un haut (ou un bas) de la couleur de la peau serait un corps nu : on prend l'autre couleur du haut, sinon un vêtement ordinaire (déterministe d'après les couleurs lues)"""
    a = dict(a); k = (sum(a['skin']) + sum(a['hair'])) % 97
    if rule.get('dress'):                      # figurines d'origine sans vêtement : toujours habillées
        a['top'] = CLOTHES[k % len(CLOTHES)]; a['pants'] = JEANS[k % len(JEANS)]; return a
    if _dist(a['top'], skin) < 48:
        a['top'] = a['accent'] if _dist(a['accent'], a['skin']) >= 60 else CLOTHES[k % len(CLOTHES)]
    if _dist(a['pants'], skin) < 48: a['pants'] = JEANS[k % len(JEANS)]
    return a


def colorize(rule, a):
    """règle + couleurs lues -> `cast` de b_chars (couleurs en [r, g, b])"""
    cast = {}
    for k, v in rule.items():
        if k == 'dress': continue
        cast[k] = list(a[v[1:]]) if isinstance(v, str) and v.startswith('@') else v
    preset = cast.get('b_preset'); outfit = cast.get('outfit'); style = cast.get('hair_style', 'short'); hat = cast.get('hat')
    a = _dress(a, cast.get('skin') or a['skin'], rule)
    if preset not in KEEP_PRESET_SKIN: cast.setdefault('skin', list(a['skin']))
    if preset in ('robot', 'alien'):
        if not (isinstance(rule.get('skin'), str) and rule['skin'].startswith('@')): cast['skin'] = list(a['skin'])
        cast['hood'] = list(a['top']); cast['jeans'] = list(a['pants'])
    elif preset is None or preset in ('zombie', 'knight', 'wizard'):
        if outfit not in (None, 'spacesuit') or preset in ('zombie',): cast['hood'] = list(a['top'])
        elif outfit == 'spacesuit': cast['hood'] = list(a['top'])
        cast['jeans'] = list(a['pants'])
        if outfit in ('suit', 'shirt') and 'tie' not in cast: cast['tie'] = list(a['accent'])
        if outfit == 'suit': cast['shirt'] = [236, 234, 226]
    if style != 'bald' and preset not in KEEP_PRESET_SKIN and 'hair' not in rule:
        cast['hair'] = list(a['hair'] if (hat and hat != 'none') else a['headtop'])
    if hat and hat not in ('none', 'antenna', 'astronaut', 'party', 'crown'): cast['hat_color'] = list(a['headtop'])
    if hat == 'hood': cast['hat_color'] = list(a['headtop'])
    if cast.get('beard') and 'hair' not in cast: cast['hair'] = list(a['hair'])
    if preset == 'zombie':
        for kk in ('hood', 'jeans'):
            if kk in cast: cast[kk] = [int(v * .8) for v in cast[kk]]
    if preset == 'skeleton': cast.pop('skin', None)
    if preset == 'zombie' and rule.get('b_preset') == 'zombie': cast['skin'] = [int(.45 * a['skin'][i] + .55 * (120, 160, 110)[i]) for i in range(3)]      # teint verdâtre, la teinte d'origine reste lisible
    return cast


def bank_chars(bank):
    """noms (sans .vox) des personnages d'une banque"""
    d = VI.BANKS / bank
    if bank == 'mmmm': return sorted(p.stem for p in d.glob('*.vox') if re.match(r'^(chr_|alien_)', p.stem) and not NOT_CHARACTER.match(p.stem))
    return [n for n in KK_CHARS.get(bank, ()) if (d / f'{n}.vox').exists()]


def build(banks=BANK_CHARS, log=print):
    """analyse tous les personnages et écrit voxelgpu_js/assets_vox/<banque>/LOOKS.json"""
    n_all = 0
    for bank in banks:
        out = {}
        for name in bank_chars(bank):
            fam, rule = rule_for(name)
            if rule is None: log(f'  sans règle : {bank}/{name}'); continue
            a = analyze(VI.BANKS / bank / f'{name}.vox', HEAD_FROM.get(bank, .5))
            out[name] = dict(cast=colorize(rule, a), family=fam, read=dict(skin=a['skin'], hair=a['hair'], headtop=a['headtop'], top=a['top'], pants=a['pants']))
        (VI.BANKS / bank / 'LOOKS.json').write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8'); n_all += len(out); log(f'{bank} : {len(out)} looks')
    return n_all


def _load_looks(bank):
    try: return json.loads((VI.BANKS / bank / 'LOOKS.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): return {}


def find(name):
    """`mmmm/chr_nun` ou `chr_nun` -> (banque, nom, fiche)"""
    if '/' in name:
        b, n = name.split('/', 1); L = _load_looks(b)
        if n in L: return b, n, L[n]
    else:
        for b in BANK_CHARS:
            L = _load_looks(b)
            if name in L: return b, name, L[name]
    raise KeyError(f'look inconnu : {name!r} (voir le catalogue, catégorie Personnages > Importés refondus)')


def expand(d):
    """un cast {"b_look": "mmmm/chr_nun", ...surcharges} -> le cast complet du look, surchargé par les autres clés"""
    b, n, L = find(d['b_look']); out = dict(L['cast'])
    for k, v in d.items():
        if k != 'b_look': out[k] = v
    return out


def _group(name):
    """army1, army1a, army1b : une même figurine (images d'animation) -> `army1`"""
    return re.sub(r'(?<=\d)[a-d]$', '', name)


def entries():
    """fiches du catalogue : une par personnage refondu (les images a/b d'une même figurine sont regroupées : la première seule est listée, toutes restent utilisables par `b_look`)"""
    out = []
    for bank in BANK_CHARS:
        try: cr = json.loads((VI.BANKS / bank / 'CREDITS.json').read_text(encoding='utf-8'))
        except (OSError, ValueError): cr = {}
        seen = set()
        for name, L in sorted(_load_looks(bank).items()):
            if _group(name) in seen: continue
            seen.add(_group(name))
            key = f'{bank}/{name}'; label = re.sub(r'^(chr|alien)_', '', name).replace('_', ' ')
            out.append(dict(id=f'look/{key}', category='Personnages', group='Importés refondus (style du studio)', name=label, key=key, cast=L['cast'], license=cr.get('license', '?'),
                            commercial_ok=bool(cr.get('commercial_ok', True)), credit_required=bool(cr.get('credit_required', False)), credit_text=cr.get('credit_text', ''), source=cr.get('source', ''),
                            snippet='"casts": {"x": {"b_look": "%s"}}' % key))
    return out


if __name__ == '__main__':
    import sys
    print(build(), 'looks écrits')
