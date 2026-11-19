"""The expressive PIXEL 3D look is opt-in: without the new keys nothing changes, with them the face is 48x48,
the hair is built from layered cubic strands and the box budget stays bounded. No API, no render of a whole episode."""
import os, sys, hashlib
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hstudio.engines.pixel3d import assets as A
from hstudio.engines.pixel3d import poses as P
from hstudio.engines.pixel3d import rigfig
from hstudio.acting import rig


def _sample(**kw):
    s = dict(x=0., y=0., z=0., heading=0., rig={}, face='neutral', talking=False, blink=False, gaze=None)
    s.update(kw); return s


def test_v2_face_unchanged():
    """the 24x24 painter still answers on the legacy path (pixel-for-pixel equality is guarded by tools/regress.py)"""
    for kind in ('neutral', 'scared', 'angry', 'joy'):
        a = A.face_tex(kind, 0, .8, .0)
        assert a.shape == (24, 24, 4), kind
    # the default look must still take the 24x24 path
    f = rigfig.face_for({}, _sample(face='angry'))
    assert f.shape == (24, 24, 4)


def test_hd_face_opt_in():
    f = rigfig.face_for({'face_detail': 'hd'}, _sample(face='angry'))
    assert f.shape == (A.HD_SIZE, A.HD_SIZE, 4)
    # every declared expression paints something, and all 43 kinds stay reachable
    for kind in A.FACE_KINDS:
        a = A.face_tex_hd(kind, 0, .0)
        assert a.shape == (A.HD_SIZE, A.HD_SIZE, 4), kind
        assert a[..., :3].std() > 2, kind                     # not a flat square
    assert set(A.HD_KINDS) <= set(A.FACE_KINDS)


def test_hd_face_deterministic_and_expressive():
    a = A.face_tex_hd('angry', 0, .0)
    b = A.face_tex_hd('angry', 0, .0)
    assert hashlib.sha1(a.tobytes()).hexdigest() == hashlib.sha1(b.tobytes()).hexdigest()
    # distinct emotions must differ, and the gaze must move pixels
    kinds = ('neutral', 'angry', 'sad', 'joy', 'surprised', 'evil')
    digests = {k: hashlib.sha1(A.face_tex_hd(k, 0, .0).tobytes()).hexdigest() for k in kinds}
    assert len(set(digests.values())) == len(kinds)
    assert not np.array_equal(A.face_tex_hd('neutral', 0, .0, gaze='left'), A.face_tex_hd('neutral', 0, .0, gaze='right'))
    assert not np.array_equal(A.face_tex_hd('neutral', .75, .0), A.face_tex_hd('neutral', 0, .0))
    assert not np.array_equal(A.face_tex_hd('neutral', 0, .0, blink=True), A.face_tex_hd('neutral', 0, .0))


def test_strand_hair_boxes():
    k = {}
    base = P.hair_and_hat(0., 0., 0., 1, A.HAIR, 'long', None, None, A.HOOD, k)
    for style, budget in (('strands', 12), ('strands_long', 16), ('strands_ponytail', 15)):
        bx = P.hair_and_hat(0., 0., 0., 1, A.HAIR, style, None, None, A.HOOD, k)
        assert len(bx) <= budget, (style, len(bx))
        assert len(bx) > len(base) - 2, (style, len(bx))
        cols = {tuple(b.col) for b in bx}
        assert len(cols) >= 3, (style, cols)               # layered tones = strands read as separate locks
    # a hat still wins over the strands (no hair through a helmet)
    hatted = P.hair_and_hat(0., 0., 0., 1, A.HAIR, 'strands_long', 'beanie', None, A.HOOD, k)
    assert len(hatted) <= 12
    assert len(hatted) == len(P.hair_and_hat(0., 0., 0., 1, A.HAIR, 'long', 'beanie', None, A.HOOD, k))
    assert set(P.STRAND_STYLES) <= set(P.HAIR_STYLES)


def test_outfit_detail_budget():
    bx = P.outfit_detail(0., 0., 1, -rig.PELVIS_Y, 'hoodie', A.HOOD, {})
    assert 0 < len(bx) <= 4
    assert len({tuple(b.col) for b in bx}) >= 2


def test_build_box_budget():
    """the expressive look must not explode the box count of a character"""
    look_v2 = {'hair_style': 'ponytail'}
    look_hd = {'hair_style': 'strands_ponytail', 'face_detail': 'hd', 'detail': True,
               'hair2': [150, 96, 58], 'iris': [96, 140, 120], 'accent': [28, 92, 70]}
    s = _sample()
    n_v2 = len(rigfig.build(s, look_v2, rigfig.face_for(look_v2, s))[0])
    n_hd = len(rigfig.build(s, look_hd, rigfig.face_for(look_hd, s))[0])
    assert n_hd > n_v2                                      # really adds geometry
    assert n_hd - n_v2 <= 16, (n_v2, n_hd)                  # but a bounded amount
    assert n_hd <= int(n_v2 * 1.6), (n_v2, n_hd)


def test_library_lea_hd_present_and_lea_untouched():
    import json
    from hstudio.acting import cast as CAST
    lea = json.load(open(os.path.join(CAST.CHAR_DIR, 'lea.json'), encoding='utf-8'))
    assert 'face_detail' not in lea['look'] and 'detail' not in lea['look']
    hd = json.load(open(os.path.join(CAST.CHAR_DIR, 'lea_hd.json'), encoding='utf-8'))
    assert hd['look']['face_detail'] == 'hd'
    assert hd['look']['hair_style'] in P.STRAND_STYLES


if __name__ == '__main__':
    import traceback
    fails = 0
    for name, fn in sorted(list(globals().items())):
        if name.startswith('test_') and callable(fn):
            try:
                fn(); print('OK   ' + name)
            except Exception:
                fails += 1; print('FAIL ' + name); traceback.print_exc()
    print(('ALL OK' if not fails else f'{fails} FAILED'))
    sys.exit(1 if fails else 0)
