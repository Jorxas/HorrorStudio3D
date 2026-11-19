"""Geometry and shared motion of explicit box assemblies; no network or paid calls."""
import copy
from types import SimpleNamespace
import numpy as np
from hstudio.engines.pixel3d import effects, sets
from hstudio.engines.pixel3d.assemblage import validate
from hstudio.voxelgpu import b_fx
from hstudio.capabilities.audit import audit_episode


def assembly():
    return {'type': 'mover', 'thing': 'prop:assemblage', 'blocks': [
        {'at': [0, 0, 0], 'size': [6, .16, 6], 'color': [119, 124, 130], 'material': 'wood'},
        {'at': [0, .16, 0], 'size': [.4, .2, .4], 'color': [90, 80, 60]}],
        'path': [[0, 2.8, 3], [0, 7.5, 3]], 'dur': 2, 'pitch': 0, 'bank': 0}


def test_shared_motion_and_immutable_source():
    o = assembly(); before = copy.deepcopy(o)
    heights = []
    for t in (0., .5, 1., 2., 4., .5):
        fx = SimpleNamespace(T=t, g=t)
        bx, lt = effects.mover(fx, o)
        rows, vl = b_fx.mover(fx, o)
        assert rows == b_fx.boxes_rows(bx)
        assert lt == vl == []
        assert len(bx) == 2
        assert np.allclose(bx[0].hi - bx[0].lo, [6, .16, 6])
        lo = bx[0].lo if bx[0].inst is None else bx[0].inst.R @ bx[0].lo + bx[0].inst.piv
        heights.append(float(lo[1]))
    assert abs(heights[0] - 2.8) < 1e-5
    assert abs(heights[3] - 7.5) < 1e-5
    assert heights[3] == heights[4]
    assert heights[1] == heights[5]
    assert o == before


def test_size_visibility_audit():
    o = assembly(); o['size'] = 2; o['wait'] = False; o['stay'] = False; o['start'] = 1
    assert effects.mover(SimpleNamespace(T=0, g=0), o) == ([], [])
    assert effects.mover(SimpleNamespace(T=5, g=5), o) == ([], [])
    bx, _ = effects.mover(SimpleNamespace(T=2, g=2), o)
    assert np.allclose(bx[0].hi - bx[0].lo, [12, .32, 12])
    rep = audit_episode({'shots': [{'objects': [o]}]}, 'pixel3d')
    assert rep['ok'], rep
    assert 'assemblage' in sets.PROP_TYPES


def test_invalid_geometry_is_explicit():
  for mutate in [
    lambda o: o.pop('blocks'), lambda o: o.update(blocks=[]),
    lambda o: o.update(blocks=o['blocks'] * 65),
    lambda o: o['blocks'][0].update(at=[0, float('nan'), 0]),
    lambda o: o['blocks'][0].update(size=[1, -1, 1]),
    lambda o: o['blocks'][0].update(size=[1, float('inf'), 1]),
    lambda o: o['blocks'][0].update(color=[256, 0, 0]),
    lambda o: o['blocks'][0].update(material='inconnu'),
    lambda o: o['blocks'][0].update(emissive=float('nan')),
    lambda o: o['blocks'][0].update(reflect=-1),
    lambda o: o['blocks'][0].update(facade={'style': 'brick'}),
  ]:
    o = assembly(); mutate(o)
    try: validate(o)
    except ValueError as e: assert 'assemblage' in str(e)
    else: raise AssertionError('Invalid assembly accepted')


if __name__ == '__main__':
    test_shared_motion_and_immutable_source()
    test_size_visibility_audit()
    test_invalid_geometry_is_explicit()
    print('Assemblages : mouvement PS1/VOXEL, taille, visibilité, déterminisme, audit et 11 refus invalides OK.')
