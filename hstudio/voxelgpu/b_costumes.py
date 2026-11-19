"""18th-century ball costumes in VOXEL: the contract side (opt-in cast key `costume`).

The costume itself (presets, resolution, spin -> flare) is decided ONCE, by `engines/pixel3d/costumes.py`, the logic
both styles share. This module only writes what the VOXEL painter needs into the contract:
  * casts[id]["costume"]  the resolved costume, colours as "#rrggbb", plus the accessories this character ever holds
  * casts[id]["look"]     the base body of chars4.js under the costume (skin, sleeves, stockings, shoes, brows) and
                          `hair: null` (the costume draws its own hair, natively, in b_costumes.js)
  * stage["costume"]      per frame and per costumed character: `f` the signed skirt flare (from the spin rate computed
                          by PS1's logic) and `h` / `l` the index of the accessory in each hand (-1: none)
A contract without any costumed character has none of these keys: it is byte for byte the contract of before.
The geometry is VOXEL-native (voxelgpu_js/engine/b_costumes.js): gores of a bell skirt hinged at the panniers, pushed by
the legs, flared by the spin; coat tails that swing back with each thigh; hair, beards, lace, veil and flowers in cubes.
"""
from ..engines.pixel3d import costumes as COS


# traits propres à un rôle, sur le visage de VOXEL (face4.js) : joues moins fardées pour les hommes, paupières lourdes, fossettes
FACE_TWEAKS = {'angelica': {'blush': .14}, 'eliza': {'blush': .3}, 'eliza_souvenir': {'blush': .25}, 'peggy': {'blush': .2, 'dimp': .5},
               'hamilton': {'blush': .05, 'lidd': .25}, 'laurens': {'blush': .08, 'dimp': .4}, 'lafayette': {'blush': .04}, 'washington': {'blush': .03, 'lidd': .2},
               'homme_chauve_rouge': {'blush': .04, 'dimp': .5}}


MATTE = .82                 # same cap as b_costumes.js matte(): a costume colour never goes brighter than this (fabric is matte, a stage spot must not burn it)


FABRIC = ('lace', 'bodice', 'skirt', 'petticoat', 'stomacher', 'trim', 'rosette', 'belt', 'veil', 'coat', 'facings', 'collar', 'cuffs', 'waistcoat', 'jabot', 'breeches', 'stockings')


def _hex(c, matte=False):
    if c is None: return None
    m = max(c[:3]) / 255.
    if matte and m > MATTE: c = [v * MATTE / m for v in c[:3]]
    return '#%02x%02x%02x' % tuple(int(round(max(0, min(255, v)))) for v in c[:3])


def _mix(a, b, k): return tuple(int(round(a[i] + (b[i] - a[i]) * k)) for i in range(3))


def js_spec(cs, items):
    """resolved costume (costumes.spec_of) -> the JSON the painter reads"""
    out = {k: v for k, v in cs.items() if not isinstance(v, tuple) and k not in ('preset', 'hair2', 'crown', 'plaid')}
    cols = {k: _hex(v, k in FABRIC) for k, v in cs.items() if isinstance(v, tuple) and v and isinstance(v[0], (int, float))}
    out['colors'] = cols
    if cs.get('crown'): out['crown'] = [_hex(c) for c in cs['crown']]
    if cs.get('plaid'): out['plaid'] = [_hex(c) for c in cs['plaid']]
    out['preset'] = cs.get('preset')
    out['items'] = list(items)
    from ..engines.pixel3d import face_skin as FS
    sk = FS.skin_of(cs)
    if sk is not None: out['face_skin'] = FS.to_contract(sk)            # tête peinte en pixels (même peinture que PS1), composée par b_costumes.js
    else: out.pop('face_skin', None)
    return out


def base_look(cs):
    """the chars4.js body under the costume: what shows of it (skin, sleeves, stockings, feet) takes the costume's colours"""
    skin = cs['skin']; lk = {'skin': _hex(skin), 'brow': _hex(cs['brow']), 'hair': None, 'iris': _hex(_mix(cs['hair_color'], (60, 40, 30), .5))}
    if cs['type'] == 'gown':
        lk['top'] = {'type': 'plain', 'color': _hex(cs['bodice'], True), 'shirt': _hex(cs['bodice'], True)}
        if cs['sleeves'] == 'elbow': lk['top']['sleeve'] = 'short'
        lk['pants'] = {'color': _hex((236, 232, 226), True)}
        lk['shoes'] = {'type': 'boot', 'color': _hex(_mix(cs['skirt'], (0, 0, 0), .5)), 'sole': _hex(_mix(cs['skirt'], (0, 0, 0), .6))}
        lk['lashes'] = True
    else:
        lk['top'] = {'type': 'coat', 'color': _hex(cs['coat'], True), 'shirt': _hex(cs['waistcoat'], True)}
        lk['pants'] = {'color': _hex(cs['breeches'], True)}
        lk['shoes'] = {'type': 'boot', 'color': _hex(cs['boots']), 'sole': _hex(_mix(cs['boots'], (0, 0, 0), .3))}
    return lk


def items_of(cs, aid, baked):
    """every accessory this character holds in the film (costume default + track `hold` values), in a fixed order"""
    seen = []
    for it in (cs.get('hold'), cs.get('hold_left')):
        for x in (('flute',) if it == 'flute_pair' else (it,)):
            if x and x not in seen: seen.append(x)
    for bs in baked:
        for fr in bs.frames:
            s = fr['samp'].get(aid)
            if not s: continue
            for x in COS.held(cs, s):
                if x and x not in seen: seen.append(x)
    return [x for x in seen if x in COS.ITEMS or x in ('flower', 'book', 'candle', 'cup')]


def resolve_casts(casts, looks, baked):
    """casts (contract, built by from_ps1) -> the same, with `costume` / `look` / `scale` for costumed characters only"""
    for aid, d in casts.items():
        cs = COS.spec_of(looks.get(aid))
        if cs is None: continue
        items = items_of(cs, aid, baked)
        d['costume'] = js_spec(cs, items)
        d['look'] = {**(d.get('look') or {}), **base_look(cs)}
        d['scale'] = float(looks[aid].get('scale') or cs.get('scale') or (.94 if cs['type'] == 'gown' else 1.0))
        d['preset'] = 'npc'
        for k in ('kind', 'archetype', 'bx'): d.pop(k, None)
        d['face'] = dict(FACE_TWEAKS.get(cs.get('preset') or '', {'blush': .12 if cs['type'] == 'coat' else .22}))      # réglages fixes du visage de VOXEL (face4.js), jamais l'ouverture des yeux
    return casts


def add_stage_tracks(stage, casts, frames, i0, e1, n):
    """stage["costume"] = {id: {"f": [flare per frame], "h": [right item], "l": [left item]}} for costumed characters"""
    out = {}
    for aid, d in casts.items():
        cs_js = d.get('costume')
        if not cs_js or aid not in (stage.get('actors') or {}): continue
        items = cs_js.get('items') or []
        cs = None
        f, h, l = [], [], []
        for j in range(i0, e1):
            s = frames[min(j, n - 1)]['samp'].get(aid) or {}
            f.append(round(COS.flare(float(s.get('spin', 0.) or 0.)), 3))
            if items:
                if cs is None: cs = _spec_from_js(d)
                r, lt = COS.held(cs, s)
                h.append(items.index(r) if r in items else -1); l.append(items.index(lt) if lt in items else -1)
        e = {}
        if any(v != 0 for v in f): e['f'] = f
        if items: e['h'] = h; e['l'] = l
        if e: out[aid] = e
    if out: stage['costume'] = out


def _spec_from_js(d):
    c = d['costume']; return {'hold': c.get('hold'), 'hold_left': c.get('hold_left')}


def entries():
    """catalogue sheets: one per ready character (same shape as b_look.entries / b_monsters.entries)"""
    out = []
    for name in COS.PRINCIPAUX + COS.ENSEMBLE_DAMES + COS.ENSEMBLE_HOMMES:
        grp = 'Bal XVIIIe — rôles' if name in COS.PRINCIPAUX else 'Bal XVIIIe — ensemble'
        out.append(dict(id=f'costume/{name}', category='Personnages', group=grp, name=name.replace('_', ' '), key=name, license='créé pour ce studio (original)',
                        commercial_ok=True, credit_required=False, note=COS.describe(name), reference=False,
                        snippet='"cast": {"%s": {"costume": "%s"}}' % (name, name)))
    return out


def add_floor_poses(stage, frames, ids, i0, e1, n):
    """stage["poses"] = {id: {"kneel": [..], "sit_floor": [..]}} when a directed track kneels or sits on the floor (voxelgpu_js/engine/poses_floor.js);
    nothing at all otherwise. Generic: any character, costumed or not."""
    out = {}
    for a in ids:
        d = {}
        for key in ('kneel', 'sit_floor'):
            v = [round(float((((frames[min(j, n - 1)]['samp'].get(a) or {}).get('rig') or {}).get(key, 0.)) or 0.), 3) for j in range(i0, e1)]
            if any(x > 0 for x in v): d[key] = v
        if d: out[a] = d
    if out: stage['poses'] = out
