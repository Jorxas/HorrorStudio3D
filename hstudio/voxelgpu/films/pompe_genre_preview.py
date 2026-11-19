"""Micro-preview of the genre-horror lane on « La Dernière Pompe » (the final scenario module `pompe_continuite.py` is NOT touched: this builds variants of its episode).

Variants (each is the same 44 cuts, the same blocking, the same cameras; only what the lane owns changes):
  legacy         the figure as it was: a man in a hood (`look.monster: false`), the world's own light
  monster        the creature (genre_intent.cast_entry): silhouette, black long-fingered hands, hollow hood
  monster_dread  the creature + the `dread` mood preset (cold moon key, no red neon, no unmotivated rim)
  vanish         monster_dread, and « il disparaît » played as a DECLARED vanish: in the dark (`shadow`, the pump panels and the neon are out) at t = 26.6 s he is gone
                 without walking anywhere, and at the cut of 27.3 s he stands beside the door (`cut`), as the narration says
Nothing here renders a film: `contract()` builds the data, `tools/genre_horror_preview.py` draws a handful of stills.
"""
import copy
import math
from contextlib import contextmanager

from . import pompe_continuite as N
from .. import blocking as BLK, director, genre_intent as G

VARIANTS = ('legacy', 'monster', 'monster_dread', 'vanish')
VANISH = dict(who='ghost', t=26.6, do='vanish', how='shadow', lights=['panels', 'neon'], until=27.3, appear='cut', at=[0.6, 4.6], face=math.pi)
VANISH_WINDOW = (26.27, 27.3)        # the beats of the ghost that the vanish replaces: the walk into the dark (26.2 -> 27.3) and the walk back beside the door (27.4 -> 29.0)


@contextmanager
def wired():
    """the two integration hooks (`compile_episode`, `preflight`) put in place for the duration of a build, then restored: director.py is not edited"""
    c0, p0 = BLK.compile_episode, BLK.preflight
    BLK.compile_episode = G.compile_episode
    BLK.preflight = lambda ep, blk, geo, shots, aspect='9:16', strict=True: G.preflight(ep, blk, geo, shots, aspect, strict)
    try: yield
    finally: BLK.compile_episode, BLK.preflight = c0, p0


def _vanish_plan(plan):
    out = copy.deepcopy(plan); gone = []
    for b in out['beats']:
        if b['who'] == 'ghost' and b['do'] in ('go', 'run') and VANISH_WINDOW[0] - .1 <= b['t'] < 29.1 and b['t'] > 26.:
            gone.append(b)
    out['beats'] = [b for b in out['beats'] if b not in gone] + [dict(VANISH)]
    return out, gone


def episode(variant='monster_dread'):
    if variant not in VARIANTS: raise ValueError('variante inconnue : %r (connues : %s)' % (variant, ', '.join(VARIANTS)))
    ep = N.episode()
    ep['title'] = 'La Dernière Pompe — aperçu genre horreur (%s)' % variant
    ghost = copy.deepcopy(ep['casts']['ghost'])
    if variant == 'legacy':
        ghost.setdefault('look', {})['monster'] = False
        ep['casts']['ghost'] = ghost; return ep
    vs = []
    if variant == 'vanish':
        ep['blocking']['plan'], _ = _vanish_plan(ep['blocking']['plan'])
        plan2, vs, _ = G.split_plan(dict(ep['blocking']['plan'], duration=ep['duration']))
    ep['casts']['ghost'] = G.cast_entry('faceless_void', hood=ghost.get('hood'), vanishes=vs)
    if variant in ('monster_dread', 'vanish'):
        G.apply_preset(ep, 'dread', 1.)
    return ep


def contract(variant='monster_dread', aspect='9:16'):
    ep = episode(variant)
    if variant == 'vanish':
        with wired(): return director.build(ep, aspect, ep['fps'])
    return director.build(ep, aspect, ep['fps'])


GALLERY = ('dread', 'calm_day', 'golden_hour', 'cold_dawn', 'clean_future')


def gallery_contract(preset, aspect='9:16'):
    """the SAME station, the same cameras and cuts, with a human cast and the story's night tables removed, under one preset: the voxel graphics and light rig reused outside horror"""
    ep = N.episode(); ep['title'] = 'La station — aperçu ambiance (%s)' % preset
    ep['world_env'] = {}; ep['casts']['ghost'] = {'preset': 'npc', 'variant': 2}
    G.apply_preset(ep, preset, 1., keep_env=False)
    for sh in ep['shots']: sh['env'] = {k: v for k, v in (sh.get('env') or {}).items() if k in ('outside', 'gain')}
    return director.build(ep, aspect, ep['fps'])
