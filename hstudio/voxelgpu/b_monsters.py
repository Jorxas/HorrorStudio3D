"""Créatures NON humanoïdes animées par notre régie : les archétypes (voxelgpu_js/engine/b_monsters.js) et leurs réglages.

Un démon, une entité, un grand homme maigre ou la créature de « La Dernière Pompe » n'ont pas besoin d'une forme humaine : ils gardent le squelette, les marches, les arrêts, le regard et les
disparitions (`vis`) de notre moteur, mais leur silhouette, leurs matières et leur animation propre (tentacules, ailes, drapé, cubes qui frémissent) sont les leurs. Rien de ce qui est dessiné ici ne
vient d'un autre jeu ou d'un autre moteur : ce sont des formes du genre (le fantastique, l'horreur) redessinées dans notre style.

Dans un épisode :  "casts": {"grand": {"kind": "creature", "archetype": "slender", "height": 3.0, "tentacles": 3, "skin": [230, 226, 218]}}
Cette table est la SOURCE UNIQUE des réglages et de leurs défauts : le contrat porte les valeurs résolues (`p`), le JS ne redéfinit rien.
Les clés de réglage se donnent à la racine du cast (comme `height`) ou dans `p`. Les couleurs : entier, "#rrggbb" ou [r, g, b] (0-255).
Règle du genre (docs/GENRE_HORREUR_20261029.md) : « homme noir » n'est jamais un indice de créature à lui seul ; ces archétypes sont demandés par le scénario, jamais devinés.
"""

BASE_H = 2.1          # hauteur d'un personnage VOXEL à l'échelle 1 (m) : 34 px de 1/16 m

# nom -> libellé, forme (largeur relative sx, hauteur relative sy : seul leur RAPPORT compte, la hauteur finale est `height`), réglages par défaut
ARCH = {
    'slender': dict(label='Grand homme maigre', shape=(0.8, 1.38), note='très grand, bras trop longs, sans visage, costume noir, tentacules dans le dos',
                    defaults=dict(height=2.9, arm=1.45, head=0.95, skin=(230, 226, 218), cloth=(12, 12, 16), accent=(110, 14, 20), tentacles=4, hunch=0.06)),
    'tall_hat_man': dict(label="Homme au chapeau haut", shape=(0.9, 1.22), note='long visage pâle, yeux et sourire fins qui brillent, chapeau haut',
                         defaults=dict(height=2.5, arm=1.15, head=1.0, skin=(222, 218, 206), cloth=(14, 12, 14), accent=(96, 20, 22), eyes=(255, 214, 120), hunch=0.05)),
    'demon': dict(label='Démon', shape=(1.1, 1.1), note='cornes, ailes qui battent, queue, yeux incandescents, dos voûté',
                  defaults=dict(height=2.4, arm=1.1, head=1.05, skin=(104, 28, 26), cloth=(40, 14, 14), accent=(70, 20, 20), horn=(206, 196, 170), wing=(70, 18, 24), eyes=(255, 120, 30), wings=1.0, tail=1.0, hunch=0.3, top='tshirt')),
    'crawler': dict(label='Rampant', shape=(1.0, 1.0), note="à quatre pattes, membres tordus, tête relevée, épine dorsale saillante ; `height` = sa taille s'il se redressait",
                    defaults=dict(height=1.9, arm=1.45, head=1.0, skin=(196, 186, 170), cloth=(60, 52, 48), eyes=(230, 40, 40), belly=13.0, twist=0.45, top='tshirt')),
    'hulk': dict(label='Colosse', shape=(1.5, 1.18), note='massif, épaules et bras démesurés, petite tête, poings énormes',
                 defaults=dict(height=2.7, arm=1.5, head=0.62, skin=(98, 120, 92), cloth=(70, 50, 38), fist=1.9, hunch=0.32, top='tshirt')),
    'wraith': dict(label='Spectre drapé', shape=(0.95, 1.15), note='sans jambes, drapé en lambeaux, flotte au-dessus du sol, yeux pâles',
                   defaults=dict(height=2.4, arm=1.35, head=1.0, skin=(20, 20, 24), cloth=(30, 34, 44), eyes=(200, 230, 255), float=0.22, hunch=0.1)),
    'many_armed': dict(label='Multi-bras', shape=(1.0, 1.0), note='quatre bras supplémentaires qui bougent à leur propre rythme, visage à quatre yeux',
                       defaults=dict(height=2.2, arm=1.2, head=1.0, skin=(176, 160, 140), cloth=(44, 36, 52), eyes=(255, 190, 80), pairs=2, hunch=0.1)),
    'stalker': dict(label='Guetteur', shape=(0.75, 1.15), note='tête trop grande sur un cou trop long, grands yeux sombres, corps filiforme',
                    defaults=dict(height=2.4, arm=1.3, head=1.55, skin=(190, 184, 170), cloth=(36, 36, 40), neck=7.0, hunch=0.14)),
    'swarm_figure': dict(label='Silhouette de cubes', shape=(1.0, 1.0), note='forme humaine faite de centaines de petits cubes qui frémissent',
                         defaults=dict(height=2.0, head=1.0, skin=(150, 136, 126), cloth=(26, 22, 24), eyes=(255, 80, 60), count=800, jitter=0.7)),
    'child_thing': dict(label='Enfant étrange', shape=(0.9, 0.85), note='petit, grosse tête pâle, trous noirs à la place des yeux, longs bras qui pendent',
                        defaults=dict(height=1.2, arm=1.3, head=1.6, skin=(226, 220, 208), cloth=(62, 60, 74), hunch=0.1, top='tshirt')),
    'puppet': dict(label='Marionnette', shape=(1.0, 1.0), note='bois, visage peint, membres fins qui sursautent, fils jusqu\'à une barre de commande',
                   defaults=dict(height=1.3, head=1.0, skin=(204, 164, 112), cloth=(130, 40, 36), cloth2=(50, 60, 110), string=1.0, top='tshirt')),
    'scarecrow': dict(label='Épouvantail', shape=(1.0, 1.05), note='sac sur la tête, paille aux poignets, bras en croix, démarche raide',
                      defaults=dict(height=2.0, arm=1.1, head=1.05, skin=(168, 140, 98), cloth=(120, 84, 56), accent=(210, 180, 90), top='tshirt')),
}
COLOR_KEYS = ('skin', 'cloth', 'cloth2', 'accent', 'eyes', 'horn', 'wing', 'boots')


def _c(v):
    if isinstance(v, int): return v
    if isinstance(v, str): return int(v.lstrip('#'), 16)
    r, g, b = (float(x) for x in v[:3]); k = 255. if max(r, g, b) <= 1. else 1.
    return (int(r * k) << 16) | (int(g * k) << 8) | int(b * k)


def is_arch(d): return isinstance(d, dict) and bool(d.get('archetype'))


def resolve(cid, d):
    """cast avec `archetype` -> cast du contrat : réglages résolus (`p`), échelle (hauteur finale) et étirement (largeur relative). Un cast sans `archetype` est rendu tel quel."""
    if not is_arch(d): return d
    a = d['archetype']
    if a not in ARCH: raise ValueError(f"personnage « {cid} » : archétype inconnu « {a} » (disponibles : {', '.join(ARCH)})")
    A = ARCH[a]; p = dict(A['defaults']); p.update(d.get('p') or {}); p.update({k: d[k] for k in A['defaults'] if k in d})
    unknown = [k for k in (d.get('p') or {}) if k not in A['defaults']]
    if unknown: raise ValueError(f"personnage « {cid} » ({a}) : réglage inconnu {unknown} (connus : {', '.join(A['defaults'])})")
    for k in COLOR_KEYS:
        if k in p: p[k] = _c(p[k])
    sx, sy = A['shape']; scale = float(p['height']) / BASE_H                    # hauteur finale = height : le cinématographe, la foulée et les ombres s'y fient
    out = {k: v for k, v in d.items() if k not in ('p', 'archetype') and k not in A['defaults']}
    out.update(kind='creature', archetype=a, p=p, scale=round(scale, 4), stretch=[round(sx / sy, 4), 1.0, round(sx / sy, 4)], head_scale=round(float(p.get('head', 1.0)) * sx / sy, 4))   # la tête suit l'étroitesse du corps : `head` = sa taille relative à un corps de même proportion
    return out


def entries():
    """fiches pour le catalogue : un archétype = une fiche"""
    out = []
    for k, A in ARCH.items():
        cast = {'kind': 'creature', 'archetype': k}
        out.append(dict(id=f'monstre/{k}', category='Créatures', group='Monstres animés (notre rig)', name=A['label'], key=k, cast=cast, desc=A['note'],
                        license='créé pour ce studio (original)', commercial_ok=True, credit_required=False,
                        snippet='"casts": {"x": {"kind": "creature", "archetype": "%s", "height": %s}}   (réglages : %s)' % (k, A['defaults']['height'], ', '.join(x for x in A['defaults'] if x != 'height'))))
    return out
