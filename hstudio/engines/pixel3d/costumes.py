"""18th-century ball costumes (opt-in cast key `costume`): the shared LOGIC and the PS1-native geometry.

Same rule as every element of the catalogue: two native versions. This module holds what both styles share --
the presets, the resolution of a cast entry into a full costume, the spin rate of a character and the skirt flare
it gives -- and draws the PS1 (PIXEL 3D) version on the shared skeleton (`acting/rig.py`). The VOXEL version is
drawn by `voxelgpu_js/engine/b_costumes.js` from the spec `hstudio/voxelgpu/b_costumes.py` puts in the contract.

Cast syntax (everything optional except `costume`; a cast without the key never reaches this module):
    "angelica": {"costume": "angelica"}                                   a ready character (PRESETS)
    "x": {"costume": {"preset": "dame_lilas", "skirt": [200, 170, 220]}}  a preset with overrides
    "y": {"costume": {"type": "gown", "bodice": [..], "skirt": [..], "stomacher": [..], "lace": [..], "sleeves": "elbow",
                      "hair": "updo", "hair_color": [..], "skin": [..], "veil": true, "crown": true, "hold": "bouquet"}}
    "z": {"costume": {"type": "coat", "coat": [..], "facings": [..], "waistcoat": [..], "breeches": [..], "footwear": "boots",
                      "epaulettes": true, "hair": "queue", "beard": "goatee"}}
Colours are [r, g, b] (0-255) or "#rrggbb". A track key `"hold": "flute"` (or bouquet, fan, letter...) shows an
accessory for that stretch of the shot; `"hold": "none"` hides the costume's default one.

Determinism: no clock, no unseeded randomness. The flare is a pure function of the spin rate, and the spin rate is
the mean yaw velocity over a fixed window of the character's own track (`spin_rate`).
"""
import functools, json, math
import numpy as np
from .r3d import C, orient, M_FABRIC, M_METAL
from . import poses as P
from ...acting import rig

# ------------------------------------------------------------------ vocabulary (generic, reusable options)
KINDS = ('gown', 'coat')
HAIR = ('big_curls', 'updo', 'updo_curls', 'side_ponytail', 'queue', 'short', 'shaved', 'puff', 'afro_crown')
BEARDS = ('goatee', 'short_full', 'mustache', 'stubble')
SLEEVES = ('elbow', 'wrist')
FOOTWEAR = ('boots', 'shoes')
ITEMS = ('flute', 'flute_pair', 'wine_glass', 'bouquet', 'fan', 'letter')     # accessories drawn natively by both styles
HAIR_LABEL = {'big_curls': 'grande chevelure bouclée (anglaises, demi-queue)', 'updo': 'chignon relevé', 'updo_curls': 'boucles relevées en chignon',
              'side_ponytail': 'demi-queue, longue queue sur l\'épaule', 'queue': 'catogan (queue basse et ruban)', 'short': 'cheveux courts',
              'shaved': 'crâne rasé', 'puff': 'houppe bouclée relevée', 'afro_crown': 'afro relevée en couronne'}
PARTS = None                  # measurement hook (tools/check_costumes.py sets a dict): emitted boxes filed by part ("leg", "skirt", "tail")
ITEM_LABEL = {'flute': 'flûte de champagne (main droite)', 'flute_pair': 'une flûte dans chaque main', 'wine_glass': 'verre à vin (main droite)',
              'bouquet': 'bouquet de fleurs blanches', 'fan': 'éventail', 'letter': 'lettre'}

WHITE_LACE = (246, 244, 236); GOLD = (214, 172, 70); BLACK_BOOT = (24, 22, 24); RIBBON = (22, 20, 24)

GOWN = dict(type='gown', skin=(214, 160, 124), hair='updo', hair_color=(52, 34, 24), brow=None, beard=None, earrings=None,
            bodice=(70, 120, 170), skirt=None, petticoat=None, stomacher=None, lace=WHITE_LACE, trim=None, sleeves='elbow',
            stomacher_style='point', buttons=None, rosette=None, belt=None, plaid=None, ribbon=None,
            veil=None, veil_dots=True, crown=None, hold=None, hold_left=None, scale=None)
COAT = dict(type='coat', skin=(214, 160, 124), hair='queue', hair_color=(40, 28, 22), brow=None, beard=None, earrings=None,
            coat=(30, 38, 74), facings=(232, 220, 190), collar=None, cuffs=None, buttons=GOLD, waistcoat=(228, 216, 184), jabot=WHITE_LACE,
            breeches=(232, 224, 200), stockings=(240, 238, 232), footwear='boots', boots=BLACK_BOOT, epaulettes=None, ribbon=RIBBON,
            hold=None, hold_left=None, scale=None)

# Ready characters. Read from the reference stills as COSTUME and HEAD traits (skin tone, hair volume and shape, beard,
# earrings) and rebuilt in the studio's block style. `library/characters/<id>.json` points at them ("costume": "<id>").
PRESETS = {
    # -- principal roles
    'angelica': dict(GOWN, skin=(112, 70, 48), hair='big_curls', hair_color=(18, 13, 12), brow=(20, 12, 10), earrings=GOLD,
                     bodice=(136, 78, 40), skirt=(146, 86, 44), petticoat=(212, 174, 130), stomacher=(222, 190, 132), sleeves='wrist',
                     buttons=(176, 140, 90), rosette=(236, 178, 182), hold='flute'),
    'eliza': dict(GOWN, skin=(238, 204, 184), hair='updo', hair_color=(56, 34, 24), brow=(52, 32, 24), earrings=(236, 232, 224),
                  bodice=(44, 150, 158), skirt=(48, 158, 164), stomacher=(120, 196, 198), sleeves='elbow', rosette=(232, 240, 240),
                  veil=(250, 250, 252), crown=((250, 250, 248), (150, 200, 236), (250, 250, 248), (176, 214, 240)), hold='bouquet'),
    'eliza_souvenir': dict(GOWN, skin=(238, 204, 184), hair='side_ponytail', hair_color=(56, 34, 24), brow=(52, 32, 24), earrings=(236, 232, 224),
                           bodice=(44, 150, 158), skirt=(48, 158, 164), stomacher=(120, 196, 198), sleeves='elbow', rosette=(232, 240, 240)),
    'peggy': dict(GOWN, skin=(184, 128, 92), hair='updo_curls', hair_color=(66, 42, 28), brow=(46, 30, 22), earrings=GOLD,
                  bodice=(222, 188, 100), skirt=(230, 198, 112), stomacher=(244, 224, 160), sleeves='elbow', rosette=(236, 210, 220),
                  belt=(200, 168, 80), hold='flute'),
    'hamilton': dict(COAT, skin=(204, 156, 118), hair='queue', hair_color=(22, 16, 14), brow=(24, 16, 12), beard='goatee',
                     coat=(26, 32, 70), facings=(234, 222, 192), waistcoat=(230, 218, 188), breeches=(234, 226, 204), hold='flute'),
    # -- recognisable secondary roles
    'laurens': dict(COAT, skin=(178, 124, 90), hair='queue', hair_color=(60, 38, 24), brow=(44, 28, 20),
                    coat=(28, 36, 76), facings=(232, 220, 188), waistcoat=(228, 214, 178), breeches=(232, 224, 198), hold='flute_pair'),
    'lafayette': dict(COAT, skin=(104, 66, 46), hair='puff', hair_color=(20, 15, 13), brow=(18, 12, 10), beard='short_full',
                      coat=(34, 52, 120), facings=(240, 240, 236), waistcoat=(240, 238, 232), breeches=(240, 238, 232), hold='flute'),
    'washington': dict(COAT, skin=(96, 62, 44), hair='shaved', hair_color=(24, 18, 16), brow=(20, 14, 12), scale=1.08,
                       coat=(20, 24, 44), facings=(26, 32, 58), waistcoat=(206, 178, 126), breeches=(214, 190, 140), epaulettes=GOLD, hold='flute'),
    'homme_chauve_rouge': dict(COAT, skin=(98, 62, 44), hair='shaved', hair_color=(24, 18, 16), brow=(20, 14, 12), scale=1.03,
                               coat=(184, 30, 36), facings=(26, 32, 70), waistcoat=(236, 232, 222), breeches=(240, 238, 232), hold='flute'),
}
# -- the ensemble: ten ladies (pastel silks, varied skin tones and up-dos) and gentlemen in blue and in red
_DAMES = [
    ('dame_ivoire', (238, 230, 210), (246, 240, 224), (232, 206, 180), 'updo', (40, 26, 20)),
    ('dame_or', (226, 196, 120), (236, 212, 140), (110, 72, 50), 'updo_curls', (24, 16, 14)),
    ('dame_peche', (240, 176, 140), (250, 214, 186), (230, 192, 166), 'updo', (120, 66, 34)),
    ('dame_rose', (236, 170, 186), (246, 206, 214), (150, 100, 72), 'afro_crown', (22, 16, 14)),
    ('dame_lilas', (188, 166, 216), (220, 206, 236), (240, 210, 190), 'updo_curls', (196, 160, 96)),
    ('dame_vieux_rose', (196, 128, 140), (226, 178, 184), (196, 140, 104), 'updo', (52, 32, 22)),
    ('dame_tartan', (232, 168, 186), (246, 210, 220), (226, 186, 160), 'updo_curls', (88, 52, 30)),
    ('dame_bleu_pale', (168, 196, 226), (210, 226, 242), (126, 84, 60), 'updo', (20, 15, 13)),
    ('dame_menthe', (160, 212, 186), (210, 236, 222), (236, 200, 178), 'updo', (150, 96, 50)),
    ('dame_champagne', (230, 210, 172), (244, 232, 206), (170, 112, 80), 'afro_crown', (28, 20, 16)),
]
for _n, _c, _st, _sk, _h, _hc in _DAMES:
    PRESETS[_n] = dict(GOWN, skin=_sk, hair=_h, hair_color=_hc, bodice=_c, skirt=_c, stomacher=_st, sleeves='elbow',
                       earrings=GOLD if _sk[0] < 200 else (236, 232, 224), hold='flute',
                       plaid=((232, 168, 186), (210, 140, 160), (246, 226, 232)) if _n == 'dame_tartan' else None)
_HOMMES = [   # (id, coat, facings, collar, waistcoat, breeches, skin, hair, hair colour, beard)
    ('homme_bleu_1', (26, 34, 72), (234, 222, 192), None, (230, 218, 188), (238, 234, 222), (226, 180, 146), 'queue', (60, 40, 26), None),
    ('homme_bleu_2', (24, 30, 66), (240, 240, 236), None, (236, 232, 222), (240, 238, 232), (120, 78, 54), 'short', (22, 16, 14), None),
    ('homme_bleu_3', (30, 38, 80), (180, 30, 38), (180, 30, 38), (236, 232, 222), (240, 238, 232), (196, 146, 108), 'queue', (30, 22, 18), 'stubble'),
    ('homme_bleu_4', (22, 28, 62), (234, 222, 192), None, (230, 218, 188), (238, 234, 222), (236, 196, 166), 'short', (150, 100, 56), None),
    ('homme_rouge_1', (182, 30, 36), (26, 32, 70), None, (236, 232, 222), (240, 238, 232), (222, 172, 136), 'queue', (40, 28, 20), None),
    ('homme_rouge_2', (176, 28, 34), (240, 240, 236), None, (236, 232, 222), (240, 238, 232), (140, 94, 66), 'short', (24, 18, 15), 'mustache'),
    ('homme_rouge_3', (186, 34, 38), (26, 32, 70), None, (236, 232, 222), (240, 238, 232), (238, 200, 170), 'queue', (176, 120, 70), None),
    ('continental', (32, 50, 104), (214, 190, 140), None, (214, 190, 140), (214, 190, 140), (210, 160, 122), 'queue', (58, 40, 28), None),
]
for _n, _c, _f, _col, _w, _b, _sk, _h, _hc, _bd in _HOMMES:
    PRESETS[_n] = dict(COAT, coat=_c, facings=_f, collar=_col, waistcoat=_w, breeches=_b, skin=_sk, hair=_h, hair_color=_hc, beard=_bd, hold='flute',
                       epaulettes=GOLD if _n == 'continental' else None)
ENSEMBLE_DAMES = [d[0] for d in _DAMES]
ENSEMBLE_HOMMES = [h[0] for h in _HOMMES]
for _p in PRESETS.values(): _p.setdefault('face_skin', True)
PRINCIPAUX = ['angelica', 'eliza', 'eliza_souvenir', 'peggy', 'hamilton', 'laurens', 'lafayette', 'washington', 'homme_chauve_rouge']

COLOR_KEYS = ('skin', 'hair_color', 'brow', 'earrings', 'bodice', 'skirt', 'petticoat', 'stomacher', 'lace', 'trim', 'buttons', 'rosette', 'belt',
              'ribbon', 'veil', 'coat', 'facings', 'collar', 'cuffs', 'waistcoat', 'jabot', 'breeches', 'stockings', 'boots', 'epaulettes')
WARN = []                     # unknown values, said once in French ([costume] ...), never silently replaced


def _say(msg):
    if msg not in WARN: WARN.append(msg); print('[costume] ' + msg)


def _rgb(c, d=None):
    if c is None or c is False: return d
    if c is True: return d
    if isinstance(c, str):
        s = c.lstrip('#')
        if len(s) == 6: return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
        return d
    v = [float(x) for x in list(c)[:3]]
    if max(v) <= 1.0 and any(isinstance(x, float) for x in list(c)[:3]): v = [x * 255 for x in v]
    return tuple(int(max(0, min(255, round(x)))) for x in v)


def _tone(c, k):
    """k > 0 lighter, k < 0 darker"""
    o = (255, 248, 236) if k > 0 else (0, 0, 0)
    return tuple(int(round(c[i] + (o[i] - c[i]) * abs(k))) for i in range(3))


@functools.lru_cache(maxsize=256)
def _resolve_json(raw):
    v = json.loads(raw)
    cos, top = v['c'], v['t']
    if isinstance(cos, str): cos = {'preset': cos}
    if not isinstance(cos, dict): return None
    pre = cos.get('preset')
    if pre is not None and pre not in PRESETS:
        _say(f'préréglage « {pre} » inconnu : costume ignoré (connus : {", ".join(sorted(PRESETS))})'); return None
    kind = cos.get('type') or (PRESETS[pre]['type'] if pre else 'gown')
    if kind not in KINDS: _say(f'type « {kind} » inconnu (gown, coat) : costume ignoré'); return None
    base = dict(PRESETS[pre]) if pre else dict(GOWN if kind == 'gown' else COAT)
    for k, x in cos.items():
        if k in ('preset', 'type'): continue
        base[k] = x
    for k in ('skin', 'hair_color'):                         # top-level cast colours keep their usual meaning
        if top.get(k) is not None: base[k] = top[k]
    out = dict(base, type=kind, preset=pre)
    for k in COLOR_KEYS:
        if k in ('veil', 'epaulettes', 'earrings', 'rosette', 'belt', 'buttons', 'brow', 'collar', 'cuffs', 'trim', 'petticoat', 'skirt', 'stomacher', 'ribbon'):
            if out.get(k) is True: out[k] = {'veil': (250, 250, 252), 'epaulettes': GOLD, 'earrings': GOLD, 'rosette': (236, 200, 206), 'belt': GOLD,
                                             'buttons': GOLD, 'ribbon': RIBBON}.get(k)
        if k in out: out[k] = _rgb(out[k], None)
    if out.get('crown') is True: out['crown'] = ((250, 250, 248), (176, 214, 240))
    if out.get('crown'): out['crown'] = tuple(_rgb(c, (250, 250, 248)) for c in (out['crown'] if isinstance(out['crown'][0], (list, tuple, str)) else [out['crown']]))
    if out.get('plaid'): out['plaid'] = tuple(_rgb(c, (200, 200, 200)) for c in out['plaid'])
    if out.get('hair') not in HAIR: _say(f'coiffure « {out.get("hair")} » inconnue : « short » (connues : {", ".join(HAIR)})'); out['hair'] = 'short'
    if out.get('beard') not in (None,) + BEARDS: _say(f'barbe « {out.get("beard")} » inconnue, ignorée (connues : {", ".join(BEARDS)})'); out['beard'] = None
    for h in ('hold', 'hold_left'):
        if out.get(h) not in (None,) + ITEMS + P.HOLD_ITEMS: _say(f'accessoire « {out.get(h)} » inconnu, ignoré (connus : {", ".join(ITEMS)})'); out[h] = None
    if kind == 'gown':
        if out.get('sleeves') not in SLEEVES: out['sleeves'] = 'elbow'
        out['skirt'] = out.get('skirt') or out['bodice']; out['stomacher'] = out.get('stomacher') or _tone(out['bodice'], .45)
        out['petticoat'] = out.get('petticoat') or None; out['trim'] = out.get('trim') or _tone(out['skirt'], -.12)
    else:
        if out.get('footwear') not in FOOTWEAR: out['footwear'] = 'boots'
        out['collar'] = out.get('collar') or out['facings']; out['cuffs'] = out.get('cuffs') or out['facings']
    out['brow'] = out.get('brow') or _tone(out['hair_color'], -.2)
    out['hair2'] = _tone(out['hair_color'], .16)
    return out


def _freeze(v):
    if isinstance(v, (list, tuple)): return [_freeze(x) for x in v]
    if isinstance(v, dict): return {k: _freeze(x) for k, x in v.items()}
    return v


def spec_of(look):
    """cast look -> full costume (dict, colours as tuples) or None when the cast has no `costume` key"""
    if not isinstance(look, dict) or not look.get('costume'): return None
    top = {k: look.get(k) for k in ('skin',) if look.get(k) is not None}
    if look.get('hair') is not None and look.get('costume'): top['hair_color'] = look['hair']
    try: raw = json.dumps({'c': _freeze(look['costume']), 't': _freeze(top)}, sort_keys=True)
    except TypeError: return None
    return _resolve_json(raw)


def wants(look): return spec_of(look) is not None


def any_costume(looks): return any(wants(l) for l in looks.values())


def face_for(look, sample, mouth_env=0.):
    """head textures of a costumed character: the painted pixel head (face_skin.py, dict of faces) or the engine's 24 x 24 face"""
    from . import face_skin as FS
    from . import rigfig
    cs = spec_of(look)
    tx = FS.textures(cs, sample, mouth_env)
    if tx is not None: return tx
    return rigfig.face_for(face_look(look, cs), sample, mouth_env)


def face_look(look, cs):
    """the look the 24x24 face reads (skin, brows/beard colour, no painted fringe: every style here clears the forehead)"""
    lk = dict(look, skin=cs['skin'], hair=cs['hair_color'], hair_style='bald')
    bd = cs.get('beard')
    lk['beard'] = {'goatee': 'mustache', 'short_full': 'full', 'mustache': 'mustache', 'stubble': 'stubble'}.get(bd) if bd else None
    return lk


# ------------------------------------------------------------------ spin -> flare (shared by both styles)
SPIN_WIN = (-.2, -.1, 0., .1, .2)          # s: the window of the mean yaw velocity
W0, W1 = 1.2, 7.0                          # rad/s: below W0 a turn does not lift the skirt, from W1 it is fully flared


def _wrap(a): return (a + math.pi) % (2 * math.pi) - math.pi


def spin_rate(headings, times):
    """mean yaw velocity (rad/s) of a sequence of headings (unwrapped step by step)"""
    tot = 0.
    for i in range(1, len(headings)): tot += _wrap(headings[i] - headings[i - 1])
    dt = times[-1] - times[0]
    return tot / dt if dt > 1e-6 else 0.


def flare(spin):
    """skirt flare 0..1: a PURE function of the spin rate (rad/s), sign kept (the twist trails the turn)"""
    w = abs(float(spin)); k = max(0., min(1., (w - W0) / (W1 - W0))); k = k * k * (3 - 2 * k)
    return math.copysign(k, spin) if k > 0 else 0.


PANNIER_REST = (.44, .90, .25)            # where a free hand rests on the panniers (character-local, x towards that hand's side)


def _rest_arms(rg):
    """a gown's free arms rest ON the panniers instead of hanging into them: a reach towards PANNIER_REST for every arm that no
    gesture and no reach is using. Written in the sample's rig, so PS1 (rig.solve) and VOXEL (the contract's arm columns) agree"""
    from ...acting.gestures import GESTURES
    used = {1: 0., -1: 0.}; m = -1 if rg.get('left') else 1             # `side: left` : le geste est joué par l'autre bras
    for (g, w, _) in rg.get('gestures') or []:
        main, other = GESTURES.get(g, ('down', 'down'))
        if main != 'down': used[m] = max(used[m], float(w))
        if other != 'down': used[-m] = max(used[-m], float(w))
    sm_ = lambda x: (lambda k: k * k * (3 - 2 * k))(max(0., min(1., float(x or 0.))))
    drop = .37 * sm_(rg.get('kneel')) + .67 * sm_(rg.get('sit_floor'))  # à genoux / par terre : les paniers descendent avec le bassin, les mains aussi
    reach = dict(rg.get('reach') or {}); add = False
    for side in (1, -1):
        free = 1. - used[side]
        if free > 1e-3 and not (side in reach and reach[side][1] > 1e-3):
            reach[side] = ((side * PANNIER_REST[0], PANNIER_REST[1] - drop, PANNIER_REST[2]), free); add = True
    return dict(rg, reach=reach) if add else rg


def add_spin(sa, samp, looks, T):
    """costumed characters only: adds `spin` (rad/s, for the skirt flare) and rests a gown's free arms on the panniers.
    Without any costume: the very same dict, untouched"""
    ids = [a for a in samp if wants(looks.get(a))]
    if not ids: return samp
    dur = float(getattr(sa, 'dur', T + 1.) or (T + 1.))
    ts = [min(max(0., T + d), dur) for d in SPIN_WIN]
    hs = {a: [] for a in ids}
    for t in ts:
        s2 = samp if abs(t - T) < 1e-9 else sa.sample(t)
        for a in ids: hs[a].append(float((s2.get(a) or samp[a])['heading']))
    out = dict(samp)
    for a in ids:
        d = dict(samp[a], spin=round(spin_rate(hs[a], ts), 4))
        if spec_of(looks.get(a))['type'] == 'gown' and isinstance(d.get('rig'), dict) and not d['rig'].get('sit', 0.) > .5: d['rig'] = _rest_arms(d['rig'])
        out[a] = d
    return out


def held(cs, sample):
    """(right item, left item) for this frame: the track's `hold` wins over the costume's default; "none" hides.
    `side: "left"` on the track (rig flag `left`) swaps the hands: the gesture and the object go to the LEFT arm"""
    r, l = _held(cs, sample)
    rg = sample.get('rig')
    return (l, r) if isinstance(rg, dict) and rg.get('left') else (r, l)


def _held(cs, sample):
    h = sample.get('hold')
    if h == 'none': return None, None
    if h in ITEMS + P.HOLD_ITEMS:
        if h == 'flute_pair': return 'flute', 'flute'
        return h, (cs.get('hold_left') if h == cs.get('hold') else None)
    r = cs.get('hold'); l = cs.get('hold_left')
    if r == 'flute_pair': return 'flute', 'flute'
    return r, l


# ------------------------------------------------------------------ PS1 geometry
def _scaled(bx, s):
    if s != 1.0:
        for b in bx: b.lo = b.lo * s; b.hi = b.hi * s
    return bx


def _octa(y0, y1, al, ar, bb, bf, col, k, mat=M_FABRIC):
    """one slab of a bell, a rounded octagon from three boxes (asymmetric extents: left/right/back/front)"""
    cy, h = (y0 + y1) / 2, abs(y1 - y0)
    out = []
    for fx, fz in ((1., .60), (.60, 1.), (.86, .86)):
        x0, x1, z0, z1 = -al * fx, ar * fx, -bb * fz, bf * fz
        out.append(C(((x0 + x1) / 2, cy, (z0 + z1) / 2), (x1 - x0, h, z1 - z0), col, mat=mat, **k))
    return out


# bell profile, relative to the pelvis: (top, bottom, a = half width, b = half depth). The last tier ends on the floor.
_TIER_KEYS = ((.08, .27, .20), (-.02, .40, .31), (-.14, .49, .40), (-.30, .57, .48), (-.48, .63, .55), (-.66, .69, .63), (-.80, .70, .64))
def _tiers(n=10):
    out = []
    for i in range(n):
        u0, u1 = i / n, (i + 1) / n
        def at(u):
            f = u * (len(_TIER_KEYS) - 1); j = min(int(f), len(_TIER_KEYS) - 2); w = f - j; a, b = _TIER_KEYS[j], _TIER_KEYS[j + 1]
            return tuple(a[q] + (b[q] - a[q]) * w for q in range(3))
        y0 = at(u0)[0]; y1 = at(u1)[0]; m = at((u0 + u1) / 2)
        out.append((y0, None if i == n - 1 else y1, m[1], m[2]))
    return tuple(out)
TIERS = _tiers()
LEG_MARGIN = .125


def _leg_points(sk):
    """points of both legs (thigh and shin axes, ankle, heel, toe) in character-local coordinates"""
    J = sk.joints; pts = []
    for tag in 'LR':
        hip, kn, an = J['hip' + tag], J['kn' + tag], J['an' + tag]
        for i in range(7): pts.append(hip + (kn - hip) * (i / 6))
        for i in range(1, 7): pts.append(kn + (an - kn) * (i / 6))
        Rf, of = sk.frames['foot' + tag]
        for q in ((0, .04, .165), (0, .04, -.105), (0, .04, .03)): pts.append(of + Rf @ np.asarray(q, np.float32))
    return pts


def skirt_extents(sk, pel, Rsk, fl, wave):
    """per tier: (y0, y1, a_left, a_right, b_back, b_front), the bell widened by the flare and PUSHED by the legs so that
    no leg point (+ its half thickness) is ever outside: the skirt cannot be crossed by a leg, by construction"""
    pts = [Rsk.T @ (p - pel) for p in _leg_points(sk)]
    floor = -float(pel[1]) + .012
    cz = min(1., max(.12, (float(pel[1]) - .012) / .788)); pool = 1 + .55 * (1 - cz)      # pelvis low (seated, kneeling, on the floor): the bell settles on the floor and spreads
    out = []
    n = len(TIERS)
    for i, (y0, y1, a, b) in enumerate(TIERS):
        y0, a, b = max(y0 * cz, floor + .02), a * pool, b * pool
        y1 = floor if y1 is None else max(y1 * cz, floor)
        fr = i / (n - 1)
        g = 1 + abs(fl) * .55 * fr * fr
        lb = lambda kk: abs(fl) * .16 * (kk / n) ** 2              # each tier boundary lifts by the same amount above and below: no gap
        y0, y1 = y0 + lb(i), y1 + lb(i + 1)
        y1 = min(y1, y0 - .02)
        aa = a * g * (1 + .07 * abs(fl) * math.sin(wave + 1.7 * i)); bb_ = b * g * (1 + .07 * abs(fl) * math.cos(wave + 1.7 * i))
        al, ar, bk, bf = aa, aa, bb_, bb_
        for p in pts:
            if not (y1 - .06 <= p[1] <= y0 + .06): continue
            x, z = float(p[0]), float(p[2])
            ex, ez = abs(x) + LEG_MARGIN, abs(z) + LEG_MARGIN
            if (ex / aa) ** 2 + (ez / bb_) ** 2 <= 1: continue
            if ez / bb_ >= ex / aa:
                need = ez / math.sqrt(max(.08, 1 - (ex / aa) ** 2)) if ex < aa else ez * 1.6
                if z >= 0: bf = max(bf, need)
                else: bk = max(bk, need)
            else:
                need = ex / math.sqrt(max(.08, 1 - (ez / bb_) ** 2)) if ez < bb_ else ex * 1.6
                if x >= 0: ar = max(ar, need)
                else: al = max(al, need)
        out.append((y0, y1, al, ar, bk, bf))
    return out


def inside_skirt(ext, p):
    """True when the point p (skirt frame, relative to the pelvis) lies inside the bell `ext` (skirt_extents)"""
    for (y0, y1, al, ar, bk, bf) in ext:
        if y1 - 1e-6 <= p[1] <= y0 + 1e-6:
            a = ar if p[0] >= 0 else al; b = bf if p[2] >= 0 else bk
            return (p[0] / a) ** 2 + (p[2] / b) ** 2 <= 1.0 + 1e-6
    return None                    # above or below the skirt


def _hair_boxes(cs, k):
    """hair, beard, earrings in the HEAD frame (origin = head centre, head .40 x .40 x .38, face towards +z)"""
    st = cs['hair']; h = cs['hair_color']; h2 = cs['hair2']; hd = _tone(h, -.25); bx = []
    cap = lambda w=.43, y=.215, t=.07: bx.append(C((0, y, -.01), (w, t, .42), h, **k))
    if st == 'shaved' and cs.get('face_skin'): pass                         # painted on the head (face_skin.py)
    elif st == 'shaved':
        bx.append(C((0, .202, -.01), (.405, .012, .39), _tone(cs['skin'], -.35), **k))
    elif st in ('short', 'queue', 'updo', 'side_ponytail'):
        cap(); bx.append(C((0, .03, -.205), (.42, .36, .05), h, **k))
        for s in (-1, 1): bx.append(C((s * .212, .08, -.06), (.03, .20, .26), h, **k))
        if st == 'queue':
            bx.append(C((0, -.24, -.235), (.085, .30, .07), h, **k)); bx.append(C((0, -.42, -.235), (.06, .10, .05), hd, **k))
            rb = cs.get('ribbon') or RIBBON
            bx.append(C((0, -.10, -.245), (.15, .05, .03), rb, **k)); bx.append(C((0, -.15, -.25), (.04, .08, .025), rb, **k))
        elif st == 'updo':
            bx.append(C((0, .19, -.25), (.22, .17, .13), h, **k)); bx.append(C((0, .22, -.25), (.12, .09, .14), h2, **k))
            for s in (-1, 1): bx.append(C((s * .205, -.03, .10), (.035, .13, .05), h, **k))
        elif st == 'side_ponytail':
            bx.append(C((0, .10, -.24), (.16, .10, .06), h, **k))
            bx.append(C((.20, -.10, .02), (.08, .14, .10), h, **k)); bx.append(C((.24, -.36, .10), (.09, .36, .09), h, **k)); bx.append(C((.25, -.58, .12), (.07, .14, .07), hd, **k))
    elif st in ('updo_curls', 'puff', 'afro_crown'):
        cap(.45, .22, .08); bx.append(C((0, .03, -.21), (.43, .36, .06), h, **k))
        for s in (-1, 1): bx.append(C((s * .215, .07, -.06), (.04, .22, .28), h, **k))
        if st == 'updo_curls':
            bx.append(C((0, .30, -.08), (.34, .14, .30), h, **k)); bx.append(C((0, .34, -.06), (.22, .08, .22), h2, **k))
            for dx, dz in ((-.13, .06), (.13, .04), (0, .12), (-.06, -.18), (.08, -.17)): bx.append(C((dx, .33, dz), (.09, .08, .09), h2 if dx > 0 else hd, **k))
            for s in (-1, 1): bx.append(C((s * .20, -.06, .09), (.04, .16, .05), h, **k))
        elif st == 'puff':
            bx.append(C((0, .33, -.04), (.40, .20, .38), h, **k)); bx.append(C((0, .44, -.04), (.30, .08, .28), h2, **k))
        else:
            bx.append(C((0, .31, -.04), (.56, .20, .50), h, **k)); bx.append(C((0, .43, -.04), (.46, .08, .40), h2, **k))
            for s in (-1, 1): bx.append(C((s * .27, .20, -.04), (.06, .18, .44), h, **k))
    elif st == 'big_curls':
        bx.append(C((0, .24, -.03), (.56, .13, .52), h, **k)); bx.append(C((0, .28, -.03), (.44, .07, .40), h2, **k))
        for s in (-1, 1):
            bx.append(C((s * .275, .02, -.05), (.13, .48, .44), h, **k))
            bx.append(C((s * .29, -.26, -.09), (.14, .22, .34), hd, **k))
            bx.append(C((s * .24, -.10, .13), (.07, .20, .07), h2, **k))
        bx.append(C((0, -.02, -.25), (.62, .56, .16), h, **k))
        bx.append(C((0, -.42, -.25), (.56, .34, .14), hd, **k))
        bx.append(C((0, -.66, -.23), (.40, .18, .10), h, **k))
        for dx, dy in ((-.2, .1), (.18, -.12), (-.05, -.3), (.22, -.38), (-.24, -.48)): bx.append(C((dx, dy, -.335), (.10, .10, .05), h2, **k))
    bd = None if cs.get('face_skin') else cs.get('beard')               # a painted head carries its own beard
    if bd == 'goatee':
        bx.append(C((0, -.175, .193), (.11, .07, .02), h, **k)); bx.append(C((0, -.11, .195), (.15, .022, .015), h, **k))
        for s in (-1, 1): bx.append(C((s * .07, -.145, .193), (.02, .055, .015), h, **k))
    elif bd == 'short_full':
        bx.append(C((0, -.17, .19), (.36, .09, .03), h, **k))
        for s in (-1, 1): bx.append(C((s * .185, -.08, .14), (.04, .2, .12), h, **k))
    ear = cs.get('earrings')
    if ear:
        for s in (-1, 1): bx.append(C((s * .205, -.07, .04), (.025, .05, .025), ear, emis=.15, **k))
    return bx


def _veil_head(cs, k, fl):
    """veil + crown of flowers, head frame; the back sheet lifts with the flare"""
    v = cs.get('veil'); bx = []; kv = dict(k, dissolve=max(.45, float(k.get('dissolve', 0.) or 0.)))
    if v:
        bx.append(C((0, .265, -.12), (.50, .03, .30), v, **kv))                     # behind the crown: never over the forehead
        for s in (-1, 1): bx.append(C((s * .272, -.06, -.165), (.02, .62, .22), v, **kv))   # behind the ears: the face stays clear, even in three-quarter view
    cr = cs.get('crown')
    if cr:
        green = (90, 150, 90)
        ring = [(-.20, .07), (-.12, .17), (0, .20), (.12, .17), (.20, .07), (.21, -.08), (.12, -.2), (0, -.22), (-.12, -.2), (-.21, -.08)]
        for i, (x, z) in enumerate(ring):
            bx.append(C((x, .235, z), (.07, .06, .07), cr[i % len(cr)], **k))
            if i % 2: bx.append(C((x * .9, .215, z * .9), (.05, .03, .05), green, **k))
    return bx


def _veil_back(cs, k):
    v = cs.get('veil')
    if not v: return []
    kv = dict(k, dissolve=max(.45, float(k.get('dissolve', 0.) or 0.)))
    return [C((0, .27, -.205), (.56, .80, .02), v, **kv)]


def _item_boxes(item, k, col=None):
    """an accessory upright at the hand (hand = origin), same convention as poses.held_item"""
    if item in P.HOLD_ITEMS: return P.held_item(item, (0., 0., 0.), 1, k, None, col)
    bx = []; glass = (214, 228, 236)
    if item in ('flute', 'wine_glass'):
        wine = (238, 220, 140)
        bx.append(C((0, -.02, .06), (.06, .008, .06), glass, **k)); bx.append(C((0, .025, .06), (.012, .09, .012), glass, **k))
        if item == 'flute':
            bx.append(C((0, .13, .06), (.05, .13, .05), glass, refl=.25, **dict(k, dissolve=max(.3, float(k.get('dissolve', 0.) or 0.)))))
            bx.append(C((0, .115, .06), (.038, .085, .038), wine, emis=.12, **k))
        else:
            bx.append(C((0, .11, .06), (.08, .09, .08), glass, refl=.25, **dict(k, dissolve=max(.3, float(k.get('dissolve', 0.) or 0.)))))
            bx.append(C((0, .095, .06), (.066, .045, .066), (150, 30, 50), **k))
    elif item == 'bouquet':
        green = (80, 140, 76)
        bx.append(C((0, -.03, .07), (.05, .20, .05), green, **k))
        bx.append(C((0, .10, .08), (.20, .10, .20), (246, 246, 240), **k)); bx.append(C((0, .15, .08), (.14, .06, .14), (250, 250, 246), **k))
        for dx, dz in ((-.08, .02), (.07, -.05), (0, .1)): bx.append(C((dx, .13, .08 + dz), (.04, .04, .04), (170, 206, 236), **k))
        for dx in (-.11, .1): bx.append(C((dx, .17, .08), (.02, .1, .02), green, **k))
        bx.append(C((0, .02, .105), (.07, .06, .02), (240, 236, 226), **k))
    elif item == 'fan':
        c = tuple(col or (236, 226, 236))
        for i, a in enumerate((-.6, -.2, .2, .6)):
            bx.append(C((math.sin(a) * .08, .08 + math.cos(a) * .05, .07), (.07, .12, .008), c if i % 2 else _tone(c, -.1), **k))
        bx.append(C((0, .01, .07), (.02, .04, .01), (120, 90, 60), **k))
    return bx


def build(sample, look, face, k=None, spec=None, lights=None):
    """boxes of one costumed character for one frame (same contract as rigfig.build: -> (boxes, skeleton))"""
    cs = spec_of(look); k = k or {}
    s = float(look.get('scale') or cs.get('scale') or 1.)
    sk = rig.solve(sample['rig'])
    Rw = rig.rot_y(sample['heading']); base = np.array([sample['x'], float(sample.get('y', 0.)), sample['z']], np.float32)
    out = []

    def emit(boxes, frame, part=None):
        R, o = frame
        bx = orient(_scaled(boxes, s), 0., Rw @ (np.asarray(o, np.float32) * s) + base, Rw @ R)
        if PARTS is not None and part: PARTS.setdefault(part, []).extend(bx)
        out.extend(bx)

    J = sk.joints; skin = cs['skin']; Rt, pel = sk.frames['torso']
    fl = flare(float(sample.get('spin', 0.) or 0.)); wave = 2. * float(sample['heading'])
    gown = cs['type'] == 'gown'
    if gown:
        bod = cs['bodice']; lace = cs['lace']
        # -- legs (inside the bell; drawn so that a flare shows real feet)
        for tag in 'LR':
            emit([C((0, -rig.THIGH / 2 + .03, 0), (.17, rig.THIGH + .10, .19), (236, 232, 226), mat=M_FABRIC, **k)], sk.frames['thigh' + tag], 'leg')
            emit([C((0, -rig.SHIN / 2 + .01, 0), (.15, rig.SHIN + .06, .17), (236, 232, 226), mat=M_FABRIC, **k)], sk.frames['shin' + tag], 'leg')
            emit([C((0, .04, .03), (.17, .08, .25), _tone(cs['skirt'], -.45), **k)], sk.frames['foot' + tag], 'leg')
        # -- bodice, stomacher, square neckline with lace
        tb = [C((0, .46, 0), (.47, .38, .26), bod, mat=M_FABRIC, **k), C((0, .17, 0), (.38, .26, .22), bod, mat=M_FABRIC, **k),
              C((0, .62, 0), (.52, .05, .24), bod, mat=M_FABRIC, **k)]
        stc = cs['stomacher']
        widths = ((.58, .20), (.48, .19), (.38, .17), (.28, .14), (.19, .10), (.11, .06)) if cs.get('stomacher_style') != 'round' else ((.58, .20), (.48, .20), (.38, .19), (.28, .17), (.18, .13), (.10, .07))
        for y, w in widths: tb.append(C((0, y - .075, .133 if y > .36 else .114), (w, .10, .012), stc, **k))          # sous l'encolure : la peau du décolleté reste visible
        if cs.get('buttons'):
            for y in (.47, .40, .33, .26, .19): tb.append(C((0, y, .143 if y > .30 else .124), (.026, .026, .012), cs['buttons'], **k))
        tb.append(C((0, .60, .137), (.30, .075, .012), skin, **k))
        tb.append(C((0, .558, .14), (.34, .03, .014), lace, **k))
        for s_ in (-1, 1): tb.append(C((s_ * .165, .60, .14), (.032, .08, .014), lace, **k))
        for x in (-.14, -.07, 0., .07, .14): tb.append(C((x, .537, .142), (.034, .02, .01), lace, **k))
        tb.append(C((0, .63, -.128), (.30, .03, .012), lace, **k))
        if cs.get('rosette'): tb.append(C((0, .555, .152), (.05, .05, .02), cs['rosette'], **k))
        if cs.get('belt'): tb.append(C((0, .09, .114), (.38, .03, .014), cs['belt'], **k))
        tb += _veil_back(cs, k)
        emit(tb, sk.frames['torso'])
        # -- the bell: tiers in the pelvis frame, twisted by the trailing turn, widened by the flare, pushed by the legs
        Rsk = rig.rot_y(-.22 * fl)
        ext = skirt_extents(sk, np.asarray(pel, np.float32), Rsk, fl, wave)
        sb = []; skc = cs['skirt']; pt = cs.get('petticoat'); plaid = cs.get('plaid'); n = len(ext)
        for i, (y0, y1, al, ar, bk, bf) in enumerate(ext):
            col = skc if not plaid else (plaid[0] if i % 2 == 0 else plaid[1])
            sb += _octa(y0, y1, al, ar, bk, bf, col, k)
            if pt and i >= 1:
                w = .05 + .30 * (i / (n - 1)); sb.append(C((0, (y0 + y1) / 2, bf + .006), (2 * min(w, .55 * min(al, ar)), y0 - y1, .012), pt, mat=M_FABRIC, **k))
            if plaid: sb.append(C((0, (y0 + y1) / 2, bf + .004), (.03, y0 - y1, .008), plaid[2], **k))
            if cs.get('veil') and i >= 1:
                kv = dict(k, dissolve=max(.45, float(k.get('dissolve', 0.) or 0.)))
                sb.append(C((0, (y0 + y1) / 2, -bk - .016), (1.1 * min(al, ar), y0 - y1, .015), cs['veil'], **kv))
        y0, y1, al, ar, bk, bf = ext[-1]
        sb += _octa(y1 + .05, y1, al * 1.01, ar * 1.01, bk * 1.01, bf * 1.01, cs['trim'], k)
        emit(sb, (Rsk, pel), 'skirt')
        # -- arms: sleeves to the elbow (lace frill) or to the wrist (lace cuff)
        for tag in 'LR':
            emit([C((0, -rig.UPPER / 2 + .03, 0), (.12, rig.UPPER + .08, .13), bod, mat=M_FABRIC, **k)], sk.frames['upper' + tag])
            if cs['sleeves'] == 'elbow':
                emit([C((0, -rig.FORE / 2 + .02, 0), (.10, rig.FORE + .03, .11), skin, **k), C((0, -.03, 0), (.17, .07, .17), lace, **k), C((0, -.075, 0), (.15, .03, .15), _tone(lace, -.06), **k)], sk.frames['fore' + tag])
            else:
                emit([C((0, -rig.FORE / 2 + .02, 0), (.11, rig.FORE + .03, .12), bod, mat=M_FABRIC, **k), C((0, -rig.FORE + .005, 0), (.15, .06, .15), lace, **k)], sk.frames['fore' + tag])
            emit([C((0, -.02, 0), (.10, .11, .11), skin, **k)], sk.frames['hand' + tag])
    else:
        coat = cs['coat']; fac = cs['facings']; btn = cs['buttons'] or GOLD; wc = cs['waistcoat']
        for tag in 'LR':
            emit([C((0, -rig.THIGH / 2 + .03, 0), (.18, rig.THIGH + .10, .21), cs['breeches'], mat=M_FABRIC, **k)], sk.frames['thigh' + tag], 'leg')
            sh = [C((0, -rig.SHIN / 2 + .01, 0), (.16, rig.SHIN + .06, .18), cs['stockings'], mat=M_FABRIC, **k)]
            if cs['footwear'] == 'boots':
                sh += [C((0, -rig.SHIN / 2 - .02, .0), (.19, rig.SHIN - .02, .21), cs['boots'], **k), C((0, -.05, 0), (.21, .07, .23), _tone(cs['boots'], .12), **k)]
            emit(sh, sk.frames['shin' + tag], 'leg')
            ft = [C((0, .04, .03), (.19, .08, .27), cs['boots'], **k)]
            if cs['footwear'] == 'shoes': ft.append(C((0, .075, .10), (.07, .02, .03), GOLD, emis=.2, **k))
            emit(ft, sk.frames['foot' + tag], 'leg')
        tb = [C((0, .33, 0), (.52, .64, .29), coat, mat=M_FABRIC, **k), C((0, .30, .148), (.16, .52, .012), wc, mat=M_FABRIC, **k)]
        for s_ in (-1, 1):
            tb.append(C((s_ * .118, .40, .151), (.075, .46, .014), fac, mat=M_FABRIC, **k))
            for y in (.56, .47, .38, .29): tb.append(C((s_ * .122, y, .162), (.03, .03, .012), btn, emis=.15, **k))
        for y in (.48, .40, .32, .24, .16): tb.append(C((0, y, .157), (.02, .02, .01), btn, emis=.12, **k))
        tb.append(C((0, .675, -.03), (.42, .09, .26), cs['collar'], mat=M_FABRIC, **k))
        tb.append(C((0, .64, .095), (.17, .06, .07), WHITE_LACE, **k))
        jb = cs.get('jabot') or WHITE_LACE
        tb += [C((0, .56, .168), (.11, .12, .035), jb, **k), C((0, .48, .17), (.08, .07, .03), _tone(jb, -.05), **k), C((-.02, .53, .19), (.05, .05, .02), _tone(jb, -.1), **k)]
        if cs.get('epaulettes'):
            for s_ in (-1, 1): tb += [C((s_ * .27, .655, 0), (.15, .035, .15), cs['epaulettes'], emis=.2, **k), C((s_ * .33, .61, 0), (.04, .07, .16), cs['epaulettes'], emis=.15, **k)]
        emit(tb, sk.frames['torso'])
        # coat skirts (basques): side panels outside the thighs, back panels that swing back with each thigh
        for side, tag in ((1, 'R'), (-1, 'L')):
            d = J['kn' + tag] - J['hip' + tag]; a = math.atan2(float(d[2]), -float(d[1]))           # thigh forward angle
            o_side = pel + np.asarray((side * .238, .04, -.02), np.float32)
            emit([C((0, -.22, 0), (.028, .46, .25), coat, mat=M_FABRIC, **k), C((0, -.43, .1), (.03, .04, .06), fac, **k)], (rig.rot_y(0.), o_side))
            o_back = pel + np.asarray((side * .128, .04, -.152), np.float32)
            th = max(0., -a) * 1.05 + .06
            hip, kn, an = J['hip' + tag], J['kn' + tag], J['an' + tag]
            for p in [hip + (kn - hip) * (i / 6) for i in range(7)] + [kn + (an - kn) * (i / 6) for i in range(1, 4)]:
                q = p - o_back; yq, zq = float(q[1]), float(q[2])          # the panel is pushed back past every point of its own leg (+ half its thickness)
                if yq > 0 or yq < -.52: continue
                L = math.hypot(yq, zq)
                if L > 1e-6: th = max(th, math.asin(min(1., .135 / L)) - math.atan2(zq, -yq) + .02)
            emit([C((0, -.22, -.012), (.214, .46, .025), coat, mat=M_FABRIC, **k)], (rig.rot_x(th), o_back), 'tail')
            emit([C((side * .06, -.10, -.026), (.03, .03, .01), btn, emis=.12, **k)], (rig.rot_x(th), o_back))
        for tag in 'LR':
            emit([C((0, -rig.UPPER / 2 + .03, 0), (.13, rig.UPPER + .08, .14), coat, mat=M_FABRIC, **k)], sk.frames['upper' + tag])
            emit([C((0, -rig.FORE / 2 + .02, 0), (.12, rig.FORE + .03, .13), coat, mat=M_FABRIC, **k), C((0, -rig.FORE + .06, 0), (.155, .10, .16), cs['cuffs'], mat=M_FABRIC, **k),
                  C((0, -rig.FORE - .005, 0), (.14, .04, .14), WHITE_LACE, **k)], sk.frames['fore' + tag])
            emit([C((0, -.02, 0), (.12, .12, .12), skin, **k)], sk.frames['hand' + tag])
    # -- head: face texture, hair, beard, earrings, veil and crown
    hb = [C((0, 0, 0), (.40, .40, .38), skin, tex=face if isinstance(face, dict) else {'+z': face}, **k)] + _hair_boxes(cs, k)
    emit(hb, sk.frames['head'])
    vh = _veil_head(cs, k, fl)
    if vh: emit(vh, sk.frames['head'])
    if cs.get('veil'):
        Rh, oh = sk.frames['head']
        emit([C((0, -.42, -.012), (.54, .84, .02), cs['veil'], **dict(k, dissolve=max(.45, float(k.get('dissolve', 0.) or 0.))))], (Rh @ rig.rot_x(.12 + .7 * abs(fl)), oh + Rh @ np.asarray((0, .1, -.215), np.float32)))
    # -- accessories (track `hold` or the costume's default), upright at the hands like poses.held_item
    right, left = held(cs, sample)
    for item, hand in ((right, 'haR'), (left, 'haL')):
        if not item: continue
        ib = _item_boxes(item, k)
        if hand == 'haL':
            for b in ib: lo, hi = b.lo.copy(), b.hi.copy(); b.lo = np.array([-hi[0], lo[1], lo[2]], np.float32); b.hi = np.array([-lo[0], hi[1], hi[2]], np.float32)
        emit(ib, (Rt, J[hand]))
    return out, sk


# ------------------------------------------------------------------ descriptions (registry, catalogue, docs)
def describe(name):
    cs = _resolve_json(json.dumps({'c': {'preset': name}, 't': {}}, sort_keys=True))
    if cs['type'] == 'gown':
        acc = ', '.join(x for x in ((ITEM_LABEL.get(cs['hold']) if cs.get('hold') else ''), 'voile' if cs.get('veil') else '', 'couronne de fleurs' if cs.get('crown') else '') if x)
        return f"robe à paniers, manches {'au coude' if cs['sleeves'] == 'elbow' else 'au poignet'}, {HAIR_LABEL[cs['hair']]}" + (f', {acc}' if acc else '')
    return f"redingote, {HAIR_LABEL[cs['hair']]}, {'bottes' if cs['footwear'] == 'boots' else 'souliers'}" + (', épaulettes' if cs.get('epaulettes') else '') + (f", barbe {cs['beard']}" if cs.get('beard') else '')
