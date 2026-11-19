"""Style PS1 : les éléments qui existaient seulement dans VOXEL (recettes « craft », modèles .vox des banques) donnent des boîtes pour le lancer de rayons de PIXEL 3D.

Les deux styles 3D partagent les mêmes identifiants : `craft:oak_tree`, `vox:kk_halloween/coffin` (aussi acceptés : `{"type": "craft", "name": ...}`, `{"type": "vox", "name": ...}`).
Choisir PS1 pour une vidéo donne la version PS1 de ces éléments, choisir VOXEL la version VOXEL ; l'épisode ne change pas.

Repères : VOXEL regarde vers +z et pose le centre de chaque boîte ; PIXEL 3D regarde vers -z (face d'un accessoire non tourné vers le spectateur) et pose le coin bas.
Une boîte tournée (`ry`) devient la boîte alignée sur les axes qui l'enveloppe (le lancer de rayons de PS1 ne sait tracer que des boîtes alignées)."""
import math
from .r3d import Box

MAX_BOXES = 1400          # au-delà, les plus petites boîtes sont regroupées par leur ordre d'écriture (le coût d'un rayon est proportionnel au nombre de boîtes)


def _rgb(c): return ((c >> 16) & 255, (c >> 8) & 255, c & 255)


def from_vox_boxes(boxes, scale=1.):
    """boîtes au format VOXEL (centre x, y, z, taille w, h, d, color entier, emis, ry) -> boîtes PS1 en repère local (face avant vers -z)"""
    out = []
    for b in boxes:
        w, h, d = b['w'] * scale, b['h'] * scale, b['d'] * scale; ry = b.get('ry', 0.) or 0.
        if ry:
            c, s = abs(math.cos(ry)), abs(math.sin(ry)); w, d = w * c + d * s, w * s + d * c
        cx, cy, cz = b['x'] * scale, b['y'] * scale, -b['z'] * scale
        e = float(b.get('emis', 0.) or 0.)
        out.append(Box((cx - w / 2., cy - h / 2., cz - d / 2.), (cx + w / 2., cy + h / 2., cz + d / 2.), _rgb(int(b['color'])), emis=e, grain=.04 if e else .07))
    if len(out) > MAX_BOXES: out = sorted(out, key=lambda b: -float((b.hi - b.lo).prod()))[:MAX_BOXES]
    return out


def craft_boxes(name, seed=0, scale=1.):
    from ...voxelgpu import craft
    craft.load_all()
    boxes, _lights = craft.build(name, seed)
    return from_vox_boxes(boxes, scale)


def vox_boxes(name, height=None, length=None, scale=None):
    from ...voxelgpu import vox_import
    d = vox_import.bset(name, scale=scale, height=height, length=length)
    return from_vox_boxes(d['boxes'])


def boxes(kind, p):
    """accessoire PS1 `kind` (`craft:nom`, `vox:banque/nom`, `craft`/`vox` avec `name`, ou un `bset` déjà converti) + paramètres `p` -> boîtes locales"""
    kind = str(kind); name = p.get('name')
    sc = float(p.get('scale', 1.))
    if kind.startswith('craft:') or (kind == 'craft' and name): return craft_boxes(kind.split(':', 1)[1] if ':' in kind else name, int(p.get('seed', 0)), sc)
    if kind.startswith('vox:') or (kind == 'vox' and name):
        return vox_boxes(kind.split(':', 1)[1] if ':' in kind else name, height=(float(p['height']) if p.get('height') else None),
                         length=(float(p['length']) if p.get('length') else None), scale=(float(p['unit']) if p.get('unit') else None))
    if kind == 'bset': return from_vox_boxes(p.get('boxes', []), sc)
    return []


def is_element(kind):
    k = str(kind); return k.startswith(('craft:', 'vox:')) or k in ('craft', 'vox', 'bset')


# ---------------------------------------------------------------- personnages
# Les looks VOXEL (`b_look`) et les personnages prêts (`b_preset`) utilisent déjà les clés de PIXEL 3D : il suffit de les développer. Les archétypes de monstres de VOXEL
# (animés par leur propre squelette) sont traduits en silhouette PS1 : le corps humain du studio, mis à l'échelle, avec la tenue, la tête et les couleurs de l'archétype.
BASE_H_PS1 = 1.8
ARCH_PS1 = {
    'slender': dict(outfit='suit', hair_style='bald', face='blank', hat=None),
    'tall_hat_man': dict(outfit='suit', hair_style='bald', hat='tophat', hat_color=(14, 12, 14), face='smirk'),
    'demon': dict(outfit='tshirt', hair_style='spiky', face='evil'),
    'crawler': dict(outfit='tshirt', hair_style='long', face='pain'),
    'hulk': dict(outfit='tshirt', hair_style='bald', face='furious'),
    'wraith': dict(outfit='robe', hat='hood', face='blank'),
    'many_armed': dict(outfit='coat', hair_style='bald', face='double'),
    'stalker': dict(outfit='shirt', hair_style='bald', face='creature'),
    'swarm_figure': dict(outfit='hoodie', hat='hood', face='blank'),
    'child_thing': dict(outfit='tshirt', hair_style='bald', face='blank'),
    'puppet': dict(outfit='tshirt', hair_style='short', face='silly'),
    'scarecrow': dict(outfit='shirt', hat='cowboy', hat_color=(210, 180, 90), face='blank'),
}


def _tup(c):
    if c is None: return None
    if isinstance(c, int): return _rgb(c)
    if isinstance(c, str): return _rgb(int(c.lstrip('#'), 16))
    return tuple(int(v) for v in c[:3])


def archetype_cast(d):
    """cast VOXEL `{"kind": "creature", "archetype": ...}` -> cast PS1 (humain mis à l'échelle, tenue et tête de l'archétype)"""
    from ...voxelgpu import b_monsters as BM
    a = d['archetype']; A = BM.ARCH[a]; p = dict(A['defaults']); p.update(d.get('p') or {}); p.update({k: d[k] for k in A['defaults'] if k in d})
    out = {k: v for k, v in d.items() if k not in ('p', 'archetype', 'kind') and k not in A['defaults']}
    out.update(ARCH_PS1.get(a, {})); out.update({k: v for k, v in d.items() if k in ('outfit', 'hat', 'face', 'hair_style')})
    cloth = _tup(p.get('cloth')) or (30, 30, 34)
    out.update(skin=_tup(p.get('skin')) or (200, 190, 180), hood=cloth, jeans=_tup(p.get('cloth2')) or cloth, hair=_tup(p.get('accent')) or cloth,
               scale=round(float(p.get('height', BM.BASE_H)) / BASE_H_PS1 * (.78 if a in ('hulk',) else 1.), 3), headphones=False, backpack=False)
    if p.get('eyes') and 'eyes' not in out: out['eyes'] = _tup(p['eyes'])
    return out


def normalize_episode(ep):
    """développe dans `ep['cast']` ce qui vient de VOXEL (`b_look`, `b_preset`, archétypes) pour que le style PS1 le comprenne ; sans effet sur un épisode PIXEL 3D ordinaire"""
    cast = ep.get('cast')
    if not isinstance(cast, dict): return ep
    for cid, d in list(cast.items()):
        if not isinstance(d, dict): continue
        if d.get('b_look'):
            from ...voxelgpu import b_look
            d = b_look.expand(d)
        if d.get('archetype'): d = archetype_cast(d)
        if 'b_preset' in d: d = dict(d); d['preset'] = d.pop('b_preset')
        cast[cid] = d
    return ep
