"""Explicit box assemblies: reusable moving scenery, with no new renderer or file input."""
import math

MATERIALS = ('wood', 'metal', 'fabric', 'plaster', 'stone', 'card', 'door', 'glass', 'light')


def validate(p):
    blocks = p.get('blocks')
    if not isinstance(blocks, list) or not 1 <= len(blocks) <= 128:
        raise ValueError('assemblage : blocks doit contenir de 1 à 128 blocs')
    for i, b in enumerate(blocks):
        if not isinstance(b, dict):
            raise ValueError(f'assemblage : bloc {i} invalide')
        for key in ('at', 'size', 'color'):
            v = b.get(key)
            if not isinstance(v, (list, tuple)) or len(v) != 3 or any(
                isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in v
            ):
                raise ValueError(f'assemblage : bloc {i}, {key} attend trois nombres finis')
        if any(x <= 0 for x in b['size']):
            raise ValueError(f'assemblage : bloc {i}, dimensions strictement positives requises')
        if any(not 0 <= x <= 255 for x in b['color']):
            raise ValueError(f'assemblage : bloc {i}, couleur hors de 0 à 255')
        if b.get('material', 'plaster') not in MATERIALS:
            raise ValueError(f'assemblage : bloc {i}, matériau inconnu')
        for key in ('emissive', 'reflect'):
            x = b.get(key, 0.)
            if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x < 0:
                raise ValueError(f'assemblage : bloc {i}, {key} invalide')
        if b.get('facade') or b.get('roof'):
            raise ValueError('assemblage : utiliser des volumes colorés, sans texture de façade ou de toit')
    return blocks


def boxes(p):
    from .sets import block_box
    return [block_box(b) for b in validate(p)]
