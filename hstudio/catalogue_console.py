"""Catalogue CONSOLE 2D : tout ce que le moteur `engines/console` sait peindre, avec sa miniature et la ligne à copier dans un épisode.

Le style CONSOLE 2D (`style: "console"`, direction artistique `"art": "aplat"`) n'a ni les décors ni les lieux de PS1 / VOXEL : il a ses scènes dessinées à plat, ses palettes, ses visages, ses personnages
de la bibliothèque et son interface. Les fiches ne sont donc PAS dans la règle des deux versions (`styles.py`) : elles portent `styles: {"console": "native"}` et vivent dans l'onglet CONSOLE 2D.

Les miniatures sont peintes par le vrai `ConsoleEngine` (une image 16:9 par fiche, ~0,1 s chacune, aucune GPU), enregistrées dans `catalogue/thumbs_console/<id>.jpg` (320x240).
`python -m hstudio.catalogue build console` ne fait que ce qui manque ; `python -m hstudio.catalogue_console sheet` fait des planches de contrôle.
"""
import json, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'catalogue'
DIR = 'thumbs_console'
W, H = 320, 240
LIC = dict(license='créé pour ce studio (CONSOLE 2D)', commercial_ok=True, credit_required=False)

ROOM, FIG = {'type': 'room'}, {'type': 'room', 'figure': True}
SCENES = [   # (clé, nom, scène, clés racine d'épisode, description)
    ('room', 'Chambre', ROOM, {}, 'la chambre : lit, console, lampe, fenêtre, porte'),
    ('room_figure', 'Chambre, silhouette', FIG, {}, 'la même chambre avec une silhouette noire aux yeux blancs'),
    ('room_light', 'Chambre, lumière sous la porte', {'type': 'room', 'light_under': 'orange'}, {}, 'lumière sous la porte : warm, orange, red, green, white'),
    ('door', 'Porte', {'type': 'door', 'light_under': 'orange', 'feet': True}, {}, 'la porte, lumière dessous et ombre de deux pieds'),
    ('door_open', 'Porte entrouverte', {'type': 'door', 'open': .35, 'eyes': True}, {}, 'la porte qui s\'ouvre (0 à 1), deux yeux dans l\'entrebâillement'),
    ('hallway', 'Couloir', {'type': 'hallway'}, {}, 'couloir sombre en perspective'),
    ('hallway_figure', 'Couloir, silhouette', {'type': 'hallway', 'figure': True}, {}, 'couloir avec une silhouette au fond'),
    ('window', 'Fenêtre', {'type': 'window'}, {}, 'fenêtre de nuit et lune'),
    ('window_silhouette', 'Fenêtre, silhouette', {'type': 'window', 'silhouette': 'adulte', 'silhouette_x': .5}, {}, 'silhouette debout derrière la vitre'),
    ('console', 'Console en main', {'type': 'console', 'screen': {'type': 'menu', 'title': 'START', 'items': ['JOUER', 'QUITTER'], 'cursor': 0}}, {}, 'la console dans les mains, écran visible'),
    ('screen', 'Écran plein cadre', {'type': 'screen', 'screen': {'type': 'warning', 'text': 'ATTENTION', 'text2': 'NE PAS ÉTEINDRE'}}, {}, 'l\'écran vert 160x144 en plein cadre'),
    ('face', 'Visage du joueur', {'type': 'face', 'expression': 'scared'}, {}, 'gros plan du visage ; `expression` : voir l\'onglet Visages'),
    ('rule_card', 'Carte de règle', {'type': 'rule_card', 'number': 3, 'lines': ['NE REGARDE PAS', 'LA PORTE'], 'highlight': 1, 'icon': 'door_x'}, {}, 'carte de règle avec une ligne dorée et une icône'),
    ('split', 'Écran partagé', {'type': 'split', 'left': {'type': 'door'}, 'right': {'type': 'room'}}, {}, 'deux scènes côte à côte'),
]
SCREENS = [  # types de l'écran pixel de la console (160x144, vert)
    ('menu', {'type': 'menu', 'title': 'MENU', 'items': ['JOUER', 'OPTIONS'], 'cursor': 1, 'heart': True}), ('text', {'type': 'text', 'speaker': 'VOIX', 'text': 'TU ES SEUL ?'}),
    ('room', {'type': 'room', 'figure': True}), ('door', {'type': 'door', 'open': .4, 'eyes': True}), ('eyes', {'type': 'eyes'}), ('static', {'type': 'static', 'text': 'PAS DE SIGNAL'}),
    ('warning', {'type': 'warning', 'text': 'ATTENTION', 'text2': 'ELLE ARRIVE'}), ('level', {'type': 'level', 'title': 'NIVEAU 2', 'subtitle': 'LE COULOIR'}),
    ('pause', {'type': 'pause', 'items': ['REPRENDRE', 'QUITTER'], 'cursor': 0}), ('face', {'type': 'face', 'mood': 'grin'}), ('timer', {'type': 'timer', 'seconds': 10}),
]
ICONS = ('door_x', 'eye_x', 'clock_x', 'phone_x', 'console_x', 'bed_x', 'bulb')
PALETTES = {'night': 'nuit bleue (défaut)', 'alert': 'alerte rouge (le jeu punit)', 'game': 'vert console (le jeu prend la pièce)', 'dawn': 'aube (fin de nuit)'}
UI = [  # (clé, nom, ui du plan, description)
    ('hud', 'Cartouche HUD', {'hud': True, 'subs': 'off'}, 'niveau, horloge, cœurs : `"ui": {"hud": true}` (réglages dans `hud` à la racine)'),
    ('choice', 'Choix A / B', {'hud': False, 'subs': 'off', 'choice': {'title': 'QUI CROIS-TU ?', 'A': 'LA CONSOLE', 'B': 'LA VOIX'}}, '`"ui": {"choice": {"title", "A", "B"}}`'),
    ('timer', 'Minuteur', {'hud': False, 'subs': 'off', 'timer': True}, 'compte à rebours de la durée du plan : `"ui": {"timer": true}`'),
    ('subs', 'Sous-titre', {'hud': False}, 'sous-titre à plaque : `"ui": {"subs": "mid"}`'),
    ('endcard', 'Écran de fin', {'endcard': {'title': 'NE METS PAS PAUSE', 'part': 'PARTIE 2', 'headline': 'A OU B ?', 'cta': 'VOTE EN COMMENTAIRE', 'button': 'ABONNE-TOI'}}, '`"ui": {"endcard": {"title", "part", "headline", "cta", "button"}}` (pensé pour le 9:16)'),
]


def slug(s): return re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_')


def pretty(s): return re.sub(r'\s+', ' ', re.sub(r'[_\-]+', ' ', s)).strip()


def thumb_rel(entry_id): return f'{DIR}/{slug(entry_id)}.jpg'


def _shot(scene, **kw): return json.dumps(dict({'lines': [0, 0], 'scene': scene}, **kw), ensure_ascii=False)


def _expressions():
    from .engines.console import figure2d as F2
    return sorted(F2.EXPR)


def _characters():
    """personnages jouables en 2D : les « presets » de la bibliothèque (humains, monstres, métiers) et les personnages à identité fixe ; les animaux n'ont pas de corps 2D"""
    from .engines.pixel3d.creatures import PRESETS
    from .acting import cast as CA
    out = [(k, {'preset': k}) for k in PRESETS]
    try: out += [(c['id'], {'ref': c['id']}) for c in CA.list_characters() if c.get('id') and not str(c['id']).endswith('_hd')]
    except Exception: pass
    return out


def entries():
    """toutes les fiches CONSOLE 2D (sans miniature encore)"""
    out = []

    def add(i, cat, group, name, key, snippet, desc=''): out.append(dict(id=i, category=cat, group=group, name=name, key=key, snippet=snippet, desc=desc, styles={'console': 'native'}, **LIC))
    for k, name, sc, ep, desc in SCENES: add(f'console/scene/{k}', 'Scènes', 'Décors dessinés à plat', name, k, _shot(sc), desc)
    for k, sc in SCREENS: add(f'console/ecran/{k}', 'Écran de la console', 'Écran pixel vert 160×144', 'Écran ' + pretty(k), k, _shot({'type': 'screen', 'screen': sc}), 'écran de la console, plein cadre : `scene.screen`')
    for k, label in PALETTES.items(): add(f'console/palette/{k}', 'Palettes', 'Palettes de la direction « aplat »', pretty(k).capitalize(), k, '"palette": "%s"   (à la racine de l\'épisode, avec "art": "aplat")' % k, label)
    for k in _expressions(): add(f'console/visage/{k}', 'Visages', 'Expressions 2D (20)', pretty(k), k, _shot({'type': 'face', 'expression': k}), 'gros plan ; en plan large : `"face": "%s"` sur un acteur' % k)
    for k, c in _characters(): add(f'console/perso/{k}', 'Personnages', 'Personnages 2D', pretty(k), k, '"cast": {"%s": %s}   puis   "actors": [{"id": "%s", "on": "bed"}]' % (k, json.dumps(c), k), 'personnage de plain-pied dans la pièce (couche de jeu d\'acteur partagée)')
    for ic in ICONS: add(f'console/regle/{ic}', 'Interface', 'Cartes de règle', 'Règle ' + pretty(ic), ic, _shot({'type': 'rule_card', 'number': 1, 'lines': ['RÈGLE', 'À SUIVRE'], 'highlight': 1, 'icon': ic}), 'icône de carte de règle')
    for k, name, ui, desc in UI: add(f'console/ui/{k}', 'Interface', 'Interface à l\'écran', name, k, _shot({'type': 'room'}, ui=ui), desc)
    return out


# ------------------------------------------------------------------ rendu
def _spec(eid):
    """id de fiche -> (scène, clés racine, acteur+cast ou None, ui, plan d'appareil)"""
    p = eid.split('/'); kind, key = p[1], p[2]
    cam = {'move': 'static'}
    if kind == 'scene':
        sc = next(s for k, _, s, _, _ in SCENES if k == key); return dict(scene=sc, ui={'hud': False, 'subs': 'off'}, cam=cam)
    if kind == 'ecran': return dict(scene={'type': 'screen', 'screen': dict(SCREENS)[key]}, ui={'hud': False, 'subs': 'off'}, cam=cam)
    if kind == 'palette': return dict(scene={'type': 'room', 'figure': True}, root={'palette': key}, ui={'hud': False, 'subs': 'off'}, cam=cam)
    if kind == 'visage': return dict(scene={'type': 'face', 'expression': key}, ui={'hud': False, 'subs': 'off'}, cam=cam, crop=True)
    if kind == 'perso':
        c = dict(_characters())[key]; return dict(scene={'type': 'room'}, cast={'x': c}, actors=[{'id': 'x', 'face': 'neutral'}], ui={'hud': False, 'subs': 'off'}, cam={'move': 'static', 'zoom': 1.45, 'focus': [.47, .50]}, crop=True)
    if kind == 'regle': return dict(scene={'type': 'rule_card', 'number': 1, 'lines': ['RÈGLE', 'À SUIVRE'], 'highlight': 1, 'icon': key}, ui={'hud': False, 'subs': 'off'}, cam=cam)
    if kind == 'ui':
        ui = next(u for k, _, u, _ in UI if k == key)
        sh = dict(scene={'type': 'room'}, ui=ui, cam=cam)
        if key == 'subs': sh['text'] = 'ELLE EST DERRIÈRE LA PORTE'
        if key == 'endcard': sh['aspect'] = '9:16'
        return sh
    raise ValueError(eid)


def render(eid):
    """id de fiche -> image PIL 320x240 peinte par le vrai ConsoleEngine"""
    import numpy as np
    from PIL import Image
    from .engines.console.render import ConsoleEngine
    s = _spec(eid); shot = {'lines': [0, 0], 'scene': s['scene'], 'camera': s['cam'], 'ui': s['ui']}
    if s.get('actors'): shot['actors'] = s['actors']
    ep = {'style': 'console', 'engine_version': 2, 'art': 'aplat', 'hud': {'level': 'NIVEAU 3', 'clock': '3:33', 'show': True}, 'lines': {}, 'cast': s.get('cast') or {}, 'shots': [shot]}
    ep.update(s.get('root') or {})
    txt = s.get('text') or 'x'
    lines = [{'tts': txt, 'display': txt, 'text': txt, 'tags': [], 'dialogue': True, 'i': 0, 'start': .2, 'end': 3., 'segs': [[.2, 3.]]}]
    asp = s.get('aspect', '16:9'); eng = ConsoleEngine(ep, lines, np.zeros(10), 3.4, asp); im = eng.frame(1.4).convert('RGB')
    if s.get('crop'):                                                          # portraits : 16:9 réduit à la hauteur 240, recadré au centre
        im = im.resize((int(round(im.width * H / im.height)), H), Image.LANCZOS); x0 = (im.width - W) // 2
        return im.crop((x0, 0, x0 + W, H))
    k = min(W / im.width, H / im.height); im = im.resize((int(round(im.width * k)), int(round(im.height * k))), Image.LANCZOS)    # scènes : image entière, bandes à la couleur de l'encre
    out = Image.new('RGB', (W, H), (11, 10, 20)); out.paste(im, ((W - im.width) // 2, (H - im.height) // 2)); return out


def build(entries_=None, force=False, log=print):
    """peint les miniatures manquantes ; renvoie {'ok': n, 'failed': {id: message}, 'seconds': s}"""
    t0 = time.time(); es = entries_ if entries_ is not None else entries(); ok, failed = 0, {}
    (OUT / DIR).mkdir(parents=True, exist_ok=True)
    for e in es:
        if not str(e['id']).startswith('console/'): continue
        out = OUT / thumb_rel(e['id'])
        if out.exists() and not force: continue
        try: render(e['id']).save(out, quality=86); ok += 1
        except Exception as ex: failed[e['id']] = f'{type(ex).__name__}: {str(ex)[:140]}'
    log(f'CONSOLE 2D : {ok} peintes, {len(failed)} en échec ({time.time() - t0:.0f} s)')
    return dict(ok=ok, failed=failed, seconds=round(time.time() - t0, 1))


def sheets(out=None, cols=5):
    """planches de contrôle par catégorie -> projects/catalogue_console_sheets/planche_<cat>.jpg"""
    from PIL import Image, ImageDraw
    out = Path(out or ROOT / 'projects' / 'catalogue_console_sheets'); out.mkdir(parents=True, exist_ok=True); by = {}
    for e in entries(): by.setdefault(e['id'].split('/')[1], []).append(e)
    for kind, es in by.items():
        ims = []
        for e in es:
            try: im = render(e['id'])
            except Exception as ex: print('ERREUR', e['id'], type(ex).__name__, str(ex)[:100]); continue
            d = ImageDraw.Draw(im); d.rectangle([0, 0, 7 * len(e['key']) + 8, 14], fill=(0, 0, 0)); d.text((4, 2), e['key'], fill=(255, 255, 255)); ims.append(im)
        if not ims: continue
        c = min(cols, len(ims)); r = (len(ims) + c - 1) // c; sh = Image.new('RGB', (W * c, H * r), (20, 20, 24))
        for i, im in enumerate(ims): sh.paste(im, ((i % c) * W, (i // c) * H))
        sh.save(out / f'planche_{kind}.jpg', quality=85); print(kind, len(ims), '->', out / f'planche_{kind}.jpg')


if __name__ == '__main__':
    sys.path.insert(0, str(ROOT))
    a = sys.argv[1:]
    if a[:1] == ['sheet']: sheets()
    elif a[:1] == ['build']: build(force='force' in a)
    else: print('usage : python -m hstudio.catalogue_console [build [force] | sheet]')
