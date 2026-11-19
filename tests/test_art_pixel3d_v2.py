"""PIXEL 3D art direction v2 (hstudio/engines/pixel3d/art.py): the contract of an opt-in prototype.

  python -m pytest tests/test_art_pixel3d_v2.py -q

What is checked, in this order of importance:
1. off by default -- with no "art" key nothing changes, neither the boxes nor a single pixel;
2. the key really switches it on, and an unknown name is refused loudly instead of silently rendering something;
3. determinism -- the same frame twice gives the same bytes, and two engines in one process do not leak state;
4. coverage -- every name of assets.FACE_KINDS draws a 48x48 face, every outfit / hair style / hat builds a body;
5. the silhouette stays close to the shipped one (the cinematographer's framings were tuned for it);
6. the second increment's three fixes stay fixed -- a readable eye, a back of the head that is not one flat
   block, and furniture dressing that only ever happens indoors.
"""
import os, sys, hashlib
import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path: sys.path.insert(0, ROOT)

from hstudio.engines.pixel3d import art, rigfig, r3d
from hstudio.engines.pixel3d import assets as A
from hstudio.engines.pixel3d import poses as P
from hstudio.director.validate import validate

SAMPLE = dict(x=.0, z=.0, heading=.4, rig=dict(t=1.2, phase=.9, gait=.6, seed=3.), visible=1, talking=0, face='neutral')
LOOK = dict(hood=(170, 70, 60), jeans=(40, 44, 70), hair=(70, 40, 26), skin=(214, 160, 124), hair_style='ponytail')


@pytest.fixture(autouse=True)
def _off():
    """every test starts and ends with the art direction off: it is a global, like r3d.configure(aspect)"""
    art.configure(None)
    yield
    art.configure(None)


def bbox(boxes):
    lo = np.min([(b.wlo if b.inst is not None else b.lo) for b in boxes], 0)
    hi = np.max([(b.whi if b.inst is not None else b.hi) for b in boxes], 0)
    return hi - lo


# ------------------------------------------------------------------ 1. off by default
def test_inert_without_the_key():
    assert art.active() is None
    assert art.configure(None) is None and art.configure(False) is None and art.configure({}) is None
    for f in art.FEATURES: assert not art.on(f)
    assert art.detail() == 0.
    assert art.decor([], 2.6) == []


def test_default_build_is_the_original_one():
    face = rigfig.face_for(LOOK, SAMPLE)
    assert face.shape == (24, 24, 4)                       # the shipped face, not the 48x48 one
    boxes, _ = rigfig.build(SAMPLE, LOOK, face)
    art.configure('voxel_hd')
    hd = rigfig.face_for(LOOK, SAMPLE)
    assert hd.shape == (48, 48, 4)
    art.configure(None)
    again, _ = rigfig.build(SAMPLE, LOOK, rigfig.face_for(LOOK, SAMPLE))
    assert len(again) == len(boxes)
    for a, b in zip(boxes, again):
        assert np.array_equal(a.lo, b.lo) and np.array_equal(a.hi, b.hi) and np.array_equal(a.col, b.col)


# ------------------------------------------------------------------ 2. the key, and only known presets
def test_configure_resolves_presets_and_overrides():
    st = art.configure('voxel_hd')
    assert st['name'] == 'voxel_hd' and st['figure'] and st['grade']
    st = art.configure({'style': 'voxel_hd', 'grade': False, 'detail': .0})
    assert st['figure'] and not st['grade'] and art.detail() == 0.
    assert art.configure('does_not_exist') is None, 'an unknown preset must not fall back to something'
    assert art.configure(123) is None


def test_validate_refuses_an_unknown_art_and_keeps_a_known_one():
    base = dict(shots=[{'lines': [0, 0]}], lines={})
    ep, W = validate(dict(base, art='voxel_hd'), 1, 'pixel3d')
    assert ep.get('art') == 'voxel_hd' and not [w for w in W if 'artistique' in w]
    ep, W = validate(dict(base, art='bidon'), 1, 'pixel3d')
    assert 'art' not in ep and any('bidon' in w for w in W)
    ep, W = validate(dict(base, art='voxel_hd'), 1, 'console')
    assert 'art' not in ep and any('pixel3d' in w for w in W), 'the console style never takes the voxel art direction'


# ------------------------------------------------------------------ 3. determinism and no leak between engines
def test_figure_and_face_are_deterministic():
    art.configure('voxel_hd')
    f1 = art.face_hd('scared', .5, (210, 150, 110), (30, 24, 20), 'left', None, None, False, False, None)
    f2 = art.face_hd('scared', .5, (210, 150, 110), (30, 24, 20), 'left', None, None, False, False, None)
    assert hashlib.sha1(f1.tobytes()).hexdigest() == hashlib.sha1(f2.tobytes()).hexdigest()
    b1 = bbox(art.figure(SAMPLE, LOOK, f1)[0]); b2 = bbox(art.figure(SAMPLE, LOOK, f1)[0])
    assert np.allclose(b1, b2)


def test_grade_is_deterministic_and_shaped():
    art.configure('voxel_hd')
    img = np.random.default_rng(1).random((r3d.RH, r3d.RW, 3)).astype(np.float32) * 1.4
    a = art.grade(img, .5, 1.0, 12); b = art.grade(img, .5, 1.0, 12)
    assert a.shape == (r3d.RH, r3d.RW, 3) and a.dtype == np.uint8
    assert np.array_equal(a, b)
    assert not np.array_equal(a, art.grade(img, .5, 1.0, 13)), 'the film grain must follow the frame'


def test_use_restores_a_state_per_engine():
    one = art.configure('voxel_hd')
    art.configure(None)                                    # a second engine was built meanwhile
    assert art.active() is None
    art.use(one)
    assert art.on('figure') and art.active()['name'] == 'voxel_hd'


# ------------------------------------------------------------------ 4. coverage
def test_every_expression_draws_a_face():
    art.configure('voxel_hd')
    seen = set()
    for kind in A.FACE_KINDS:
        tex = art.face_hd(kind)
        assert tex.shape == (48, 48, 4), kind
        assert tex[..., 3].min() == 255, kind                       # fully opaque: it is a head surface
        seen.add(hashlib.sha1(tex.tobytes()).hexdigest())
    assert len(seen) >= len(A.FACE_KINDS) - 2, 'expressions must not collapse onto each other'


def test_mouth_blink_and_gaze_change_the_face():
    art.configure('voxel_hd')
    base = art.face_hd('neutral')
    assert not np.array_equal(base, art.face_hd('neutral', .8))
    assert not np.array_equal(base, art.face_hd('neutral', 0., A.SKIN, A.HAIR, 'left'))
    assert not np.array_equal(base, art.face_hd('neutral', 0., A.SKIN, A.HAIR, None, None, None, False, True))


def test_every_outfit_hair_and_hat_builds():
    art.configure('voxel_hd')
    face = art.face_hd('neutral')
    for outfit in P.OUTFITS:
        for style in P.HAIR_STYLES:
            look = dict(LOOK, outfit=outfit, hair_style=style)
            boxes, sk = art.figure(SAMPLE, look, face)
            assert len(boxes) > 20, (outfit, style)
    for hat in P.HATS:
        boxes, _ = art.figure(SAMPLE, dict(LOOK, hat=hat), face)
        assert len(boxes) > 20, hat


def test_held_items_still_light_the_scene():
    art.configure('voxel_hd')
    lights = []
    art.figure(dict(SAMPLE, hold='flashlight'), LOOK, art.face_hd('neutral'), lights=lights)
    assert lights, 'a torch must still add its light'


# ------------------------------------------------------------------ 5. silhouette and set dressing
def test_silhouette_stays_close_to_the_shipped_body():
    """the cinematographer frames on the shipped proportions: the v2 body may be richer, not a different size"""
    face0 = rigfig.face_for(LOOK, SAMPLE)
    old = bbox(rigfig.build(SAMPLE, LOOK, face0)[0])
    art.configure('voxel_hd')
    new = bbox(art.figure(SAMPLE, LOOK, art.face_hd('neutral'))[0])
    assert abs(new[1] - old[1]) < .05, f'height {new[1]:.3f} vs {old[1]:.3f}'
    assert new[0] < old[0] * 1.10, f'width {new[0]:.3f} vs {old[0]:.3f}'
    assert new[2] < old[2] * 1.15, f'depth {new[2]:.3f} vs {old[2]:.3f}'   # ponytail and backpack sit a little deeper


def test_detail_zero_drops_the_optional_geometry():
    art.configure({'style': 'voxel_hd', 'detail': .0})
    lean = len(art.figure(SAMPLE, LOOK, art.face_hd('neutral'))[0])
    art.configure('voxel_hd')
    full = len(art.figure(SAMPLE, LOOK, art.face_hd('neutral'))[0])
    assert lean < full


def test_decor_finds_walls_and_caches_them():
    from hstudio.engines.pixel3d.r3d import B, M_WOODV, M_FABRIC
    art.configure('voxel_hd')
    walls = [B((-3, 0, 0), (6, 2.65, .1), (120, 100, 80), mat=M_WOODV),
             B((-3, 0, 0), (.1, 2.65, 6), (120, 100, 80), mat=M_WOODV),
             B((0, 0, 0), (.6, .6, .6), (80, 80, 80), mat=M_FABRIC)]        # a crate is not a wall
    one = art.decor(walls, 2.65)
    assert len(one) == 6, 'skirting + cornice + rail on each of the two walls'
    assert art.decor(walls, 2.65) is one, 'the same set must not be scanned twice'
    for b in one: assert not b.cast, 'a moulding must not throw a shadow across the room'
    art.configure(None)
    assert art.decor(walls, 2.65) == []


def test_decor_gives_up_on_a_set_full_of_walls():
    from hstudio.engines.pixel3d.r3d import B, M_PLASTER
    art.configure('voxel_hd')
    many = [B((i, 0, 0), (.1, 2.6, 4), (120, 120, 120), mat=M_PLASTER) for i in range(art.MAX_WALLS + 4)]
    assert art.decor(many, 2.6) == []


# ------------------------------------------------------------------ 6. the second increment, defect by defect
LUMA = np.array([.299, .587, .114], np.float32)


def _room():
    """two walls, a sofa and a desk top: the smallest thing the furniture pass calls a room"""
    from hstudio.engines.pixel3d.r3d import B, M_WOODV, M_FABRIC
    return [B((-3, 0, 0), (6, 2.65, .1), (120, 100, 80), mat=M_WOODV),
            B((-3, 0, 0), (.1, 2.65, 6), (120, 100, 80), mat=M_WOODV),
            B((-1, 0, 1.5), (2, .45, .9), (52, 70, 62), mat=M_FABRIC),
            B((-.6, .75, 4.), (1.2, .05, .8), (120, 86, 56), mat=M_WOODV)]


def test_an_open_eye_keeps_the_white_on_both_sides_of_the_iris():
    """defect 1: a 7 px iris filled the lid slit, so the eye read as a pale ring with white only in the corners.
    The eye's middle row must go sclera -> iris -> pupil -> iris -> sclera."""
    art.configure('voxel_hd')
    lum = (art.face_hd('neutral')[..., :3].astype(np.float32) / 255. * LUMA).sum(-1)
    for cx in (14, 33):
        row = lum[22, cx - 5:cx + 6]
        assert row[0] > .75 and row[-1] > .75, f'sclera lost at cx={cx}: {row.round(2)}'
        assert row[len(row) // 2] < .25, f'the pupil must be the dark value at cx={cx}: {row.round(2)}'
        assert row[0] - row[3] > .3, 'the iris must be darker than the sclera beside it'


def test_every_expression_still_draws_a_pupil_or_a_closed_lid():
    """the narrower iris must not have turned a wide-eyed expression into a blank white oval"""
    art.configure('voxel_hd')
    for kind in A.FACE_KINDS:
        lum = (art.face_hd(kind)[..., :3].astype(np.float32) / 255. * LUMA).sum(-1)
        assert lum[14:30, 6:43].min() < .30, kind


def test_the_back_of_the_head_is_not_one_flat_block():
    """defect 2: from behind the hair was a single dark plate. It must now carry several shells and shades."""
    art.configure('voxel_hd')
    bx = art.hair_layers((70, 40, 26), 'ponytail', None, {}, 0.)
    back = [b for b in bx if (b.lo[2] + b.hi[2]) / 2 < -.12]
    assert len(back) >= 5, f'only {len(back)} boxes behind the head'
    shades = {tuple(np.round(b.col * 255).astype(int).tolist()) for b in back}
    assert len(shades) >= 3, f'the back of the head carries {len(shades)} shade(s)'


def test_the_back_of_the_head_does_not_grow_deeper():
    """the extra shells are shading, not volume: the cinematographer was tuned on the shipped depth"""
    art.configure('voxel_hd')
    for style in ('short', 'long', 'ponytail', 'bun', 'curly', 'spiky'):
        bx = art.hair_layers((70, 40, 26), style, None, {}, 0.)
        assert min(float(b.lo[2]) for b in bx) > -.45, style


def test_furniture_dresses_a_room_and_leaves_the_outdoors_alone():
    """a box carries no name: indoors its size is a fair guess, outdoors the same block is a rock"""
    art.configure('voxel_hd')
    assert art.furniture(_room(), 2.65), 'a sofa and a desk in a room must be dressed'
    assert art.furniture([_room()[2]], None) == [], 'no ceiling and no walls: nothing may be dressed'
    assert art.furniture(_room()[2:], None) == [], 'one sofa alone is not a room'


def test_set_dressing_is_deterministic():
    """same set, same dressing -- accessories are seeded from the surface, never from a clock (AGENTS.md)"""
    art.configure('voxel_hd')
    a = art.furniture(_room(), 2.65)
    b = art.furniture(_room(), 2.65)
    assert len(a) == len(b) and a is not b
    for x, y in zip(a, b):
        assert np.array_equal(x.lo, y.lo) and np.array_equal(x.hi, y.hi) and np.array_equal(x.col, y.col)


def test_dressing_never_casts_a_shadow_and_respects_the_cap():
    art.configure('voxel_hd')
    for b in art.furniture(_room(), 2.65):
        assert not b.cast, 'set dressing must not throw new shadows across the room'
    assert len(art.furniture(_room() * 40, 2.65)) <= art.MAX_DRESS


def test_detail_zero_keeps_only_the_plain_dressing():
    art.configure({'style': 'voxel_hd', 'detail': .0})
    lean = len(art.furniture(_room(), 2.65))
    art.configure('voxel_hd')
    full = len(art.furniture(_room(), 2.65))
    assert 0 < lean < full, (lean, full)


def test_an_accessory_never_grows_through_a_prop_already_there():
    """the set's own props win: a surface already covered gets nothing on top of it"""
    from hstudio.engines.pixel3d.r3d import B, M_WOODV
    art.configure('voxel_hd')
    free = _room()
    taken = free + [B((-.6, .80, 4.), (1.2, .4, .8), (90, 90, 90), mat=M_WOODV)]   # the desk is buried
    assert len(art.furniture(taken, 2.65)) < len(art.furniture(free, 2.65))


def test_decor_still_returns_only_mouldings_when_there_is_no_furniture():
    """the wall pass and the furniture pass stay separable -- decor() is still the single hook"""
    from hstudio.engines.pixel3d.r3d import B, M_WOODV
    art.configure('voxel_hd')
    walls = [B((-3, 0, 0), (6, 2.65, .1), (120, 100, 80), mat=M_WOODV),
             B((-3, 0, 0), (.1, 2.65, 6), (120, 100, 80), mat=M_WOODV)]
    assert len(art.decor(walls, 2.65)) == 6
