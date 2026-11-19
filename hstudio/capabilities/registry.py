"""What the studio can represent, read from the code itself (never a hand-kept list that could drift from it).

build() -> {"kind:name": {"kind", "name", "engines": {"pixel3d": status, "console": status}, "source"}}
status per engine: "native" (drawn as such), "composed" (built by a generator from parameters), "partial" (an
approximation exists, see "note"), absent = not available in that engine. Extensions add their own entries."""
from . import extensions

P3 = {'pixel3d': 'native'}; BOTH = {'pixel3d': 'native', 'console': 'native'}

def build():
    from ..engines.pixel3d import places as PL, world as W, compose as CO, creatures as CR, poses as P, effects as FX
    from ..engines.pixel3d.sets import PROP_TYPES, PREFABS
    from ..engines.pixel3d.assets import FACE_KINDS
    from ..acting import timeline as TL, cinema as CI, cast as CA
    import importlib; V = importlib.import_module('hstudio.director.validate')     # (the package exports a function of that name)
    from ..audio import synth as S, ambience as AMB, music as MU
    extensions.ensure_loaded()
    caps = {}
    def add(kind, name, engines, source, **kw):
        caps[f'{kind}:{name}'] = dict(kind=kind, name=name, engines=dict(engines), source=source, **kw)
    for n in list(PL.PLACES) + list(PREFABS): add('place', n, P3, 'engines/pixel3d/places.py')
    add('place', 'composed', {'pixel3d': 'composed'}, 'engines/pixel3d/compose.py', note='lieu assemblé à partir d\'éléments (immeubles, falaises, plateformes, rues, quartiers)')
    for e in CO.BUILDERS: add('element', e, {'pixel3d': 'composed'}, 'engines/pixel3d/compose.py')
    for st in CO.STYLES: add('style', st, {'pixel3d': 'composed'}, 'engines/pixel3d/compose.py')
    for p in PROP_TYPES: add('prop', p, P3, 'engines/pixel3d/world.py')
    for s in W.SKY_NAMES: add('sky', s, P3, 'engines/pixel3d/world.py')
    for w in W.WEATHERS: add('weather', w, P3, 'engines/pixel3d/world.py')
    for g in W.GROUNDS: add('ground', g, P3, 'engines/pixel3d/world.py')
    for a in CR.ANIMALS: add('creature', a, P3, 'engines/pixel3d/creatures.py')
    for pr in CR.PRESETS: add('character', pr, {'pixel3d': 'native', 'console': 'partial'}, 'engines/pixel3d/creatures.py', note='aplats plus simples en CONSOLE')
    for c in CA.list_characters(): add('character', c['id'], BOTH, 'library/characters', label=c.get('name', ''))
    for v in sorted(V.VERBS | set(TL.VERBS)): add('action', v, BOTH, 'acting/motion.py' if v in TL.VERBS else 'acting/timeline.py')
    for g in P.GESTURES: add('gesture', g, BOTH, 'engines/pixel3d/poses.py')
    for f in FACE_KINDS: add('expression', f, BOTH, 'engines/pixel3d/assets.py')
    for o in ('phone', 'arm', 'debris', 'dust', 'glass_burst', 'eyes', 'prop', 'light', 'hands_push'): add('effect', o, P3, 'engines/pixel3d/frame.py')
    for o in FX.EFFECTS: add('effect', o, P3, 'engines/pixel3d/effects.py')
    for w in ('door', 'lightning', 'lights'): add('event', w, BOTH, 'acting/timeline.py')
    for s in sorted(V.SHOTS): add('camera', s, BOTH if s in ('wide', 'full', 'close', 'medium') else P3, 'acting/cinema.py')
    for m in sorted(V.MOVES2): add('camera_move', m, P3, 'acting/cinema.py')
    for s in S.SFX: add('sound', s, BOTH, 'audio')
    for a in AMB.AMBIENCES: add('ambience', a, BOTH, 'audio/ambience.py')
    for m in MU.NAMES: add('music', m, BOTH, 'audio/music.py')
    for s in V.SCENES: add('console_scene', s, {'console': 'native'}, 'engines/console/render.py')
    for pl in ('bedroom', 'kid_bedroom'):                    # the console's own places: its bedroom is the "room" scene
        if f'place:{pl}' in caps: caps[f'place:{pl}']['engines']['console'] = 'native'
    add('feature', 'levels', {'pixel3d': 'composed', 'console': 'partial'}, 'engines/pixel3d/compose.py, acting/motion.py',
        note='CONSOLE : niveaux simples ("levels" de la scène, le lit)')
    add('feature', 'scale', P3, 'effects.py (size), creatures.py, rigfig.py (scale)')
    add('feature', 'carry', P3, 'engines/pixel3d/effects.py (carry)', note='un personnage transporté par un mobile')
    _style_matrix(caps, add)
    for c in extensions.provided():
        e = dict(P3) if c['kind'] not in ('action', 'sound') else dict(BOTH)
        add(c['kind'], c['name'], e, c['source'], terms=c.get('terms', []), label=c.get('label', ''))
    return caps

def has(caps, kind, name, engine='pixel3d'):
    c = caps.get(f'{kind}:{name}')
    return c is not None and engine in c['engines']


# ------------------------------------------------------------------ styles PS1 / VOXEL (hstudio/styles.py)
SHARED = ('action', 'gesture', 'event', 'camera', 'camera_move', 'sound', 'ambience', 'music')          # régie, caméra et son : les mêmes dans les deux styles
CONVERTED = ('prop', 'place', 'character', 'creature', 'expression')                                    # nés dans PIXEL 3D, repeints par VOXEL (voxelgpu/b_*.py)
APPROX = ('sky', 'weather', 'ground', 'effect', 'element', 'style', 'feature')                          # VOXEL les rend en approchant (reflets, matières, éclairs non portés)


def _style_matrix(caps, add):
    """ajoute à chaque capacité `styles` = {"ps1": statut, "voxel": statut}, puis les éléments nés dans VOXEL (craft, banques .vox, looks, monstres, mondes) avec leur version PS1"""
    for c in caps.values():
        k = c['kind']; e = c['engines']
        ps1 = e.get('pixel3d')
        voxel = 'native' if k in SHARED else 'converted' if k in CONVERTED else 'approx' if k in APPROX else None
        c['styles'] = {kk: v for kk, v in (('ps1', ps1), ('voxel', voxel)) if v}
    try:
        from ..voxelgpu import craft, b_look, b_monsters, vox_import as VI, worlds as WD
        from ..engines.pixel3d import ps1_worlds as PW
    except Exception as ex:                                  # un module absent n'empêche pas le reste du registre
        caps['feature:styles_error'] = dict(kind='feature', name='styles_error', engines={}, source='capabilities/registry.py', note=str(ex)); return
    P = {'pixel3d': 'composed'}
    for n, c in caps.items():                                  # quartiers et intérieurs à deux versions natives (pixel3d/qt_*.py + voxelgpu/b_quartiers.py ; interieurs.py + b_interieurs.py)
        if (c['kind'] == 'place' and c['name'] in ('quartier', 'appartement', 'salon_maison', 'cafe_quartier', 'boutique', 'hall_immeuble', 'escalier_immeuble', 'theatre_bal')) or (c['kind'] == 'prop' and c['name'].startswith(('qt_', 'qi_', 'od_'))):
            c['styles'] = {'ps1': 'native', 'voxel': 'native'}
    for n in PW.LOOK:                                          # ces lieux PS1 sont les mondes VOXEL reconstruits
        if f'place:{n}' in caps: caps[f'place:{n}']['styles'] = {'ps1': 'converted', 'voxel': 'native'}
    def both(kind, name, source, **kw):
        add(kind, name, P, source, **kw); caps[f'{kind}:{name}']['styles'] = {'ps1': 'converted', 'voxel': 'native'}
    for n in sorted(craft.load_all()): both('craft', n, 'voxelgpu/craft*.py')
    for bank in sorted(VI.BANKS.glob('*')):
        if bank.is_dir():
            for f in sorted(bank.glob('*.vox')): both('vox', f'{bank.name}/{f.stem}', f'voxelgpu_js/assets_vox/{bank.name}')
    for e in b_look.entries(): both('look', e['key'], 'voxelgpu/b_look.py')
    for n in b_monsters.ARCH:
        add('monster', n, P, 'voxelgpu/b_monsters.py', note="PS1 : silhouette humaine mise à l'échelle (pas de tentacules, d'ailes ni d'animation propre)")
        caps[f'monster:{n}']['styles'] = {'ps1': 'approx', 'voxel': 'native'}
    for n in WD.WORLDS:
        ps1 = 'converted' if n in PW.LOOK else 'approx' if n in PW.ALIAS else None
        add('world', n, {'pixel3d': 'composed'} if ps1 else {}, 'voxelgpu_js/engine (mondes)', **({'note': 'PS1 : le lieu le plus proche (%s), ciel et météo du monde' % PW.ALIAS[n][0]} if ps1 == 'approx' else {}))
        caps[f'world:{n}']['styles'] = {k: v for k, v in (('ps1', ps1), ('voxel', 'native')) if v}
    add('feature', 'words_3d', {}, 'voxelgpu_js/engine/film_unified.js (words), audio/music_cues.py (words_on_syllables)', note='mots en cubes posés dans la scène, sur les syllabes chantées d\'un clip musical (docs/FORMAT_EPISODE.md, « Mots 3D »)')
    caps['feature:words_3d']['styles'] = {'voxel': 'native'}
    # théâtre de bal (lieu `theatre_bal`) et sa lumière de scène (clé `stage_light`) : deux versions natives (pixel3d/theatre.py, voxelgpu/b_theatre.py + theatre_kit.js)
    add('feature', 'stage_light', {'pixel3d': 'native'}, 'engines/pixel3d/stage_light.py + theatre.py, voxelgpu/b_theatre.py, voxelgpu_js/engine/theatre_kit.js',
        note='lumière de scène du théâtre : lavis (bleu nuit, ambre, violet, magenta, lavande, blanc froid, noir), poursuites, rideau de projecteurs, disques au sol, plateau tournant')
    caps['feature:stage_light']['styles'] = {'ps1': 'native', 'voxel': 'native'}
    # costumes de bal XVIIIe (clé de cast `costume`) : deux versions natives, PS1 (pixel3d/costumes.py) et VOXEL (voxelgpu_js/engine/b_costumes.js)
    from ..engines.pixel3d import costumes as COS
    NAT = {'ps1': 'native', 'voxel': 'native'}; SRC = 'engines/pixel3d/costumes.py + voxelgpu_js/engine/b_costumes.js'
    for n in COS.PRESETS:
        add('costume', n, {'pixel3d': 'native'}, SRC, label=COS.describe(n)); caps[f'costume:{n}']['styles'] = dict(NAT)
    for kd in COS.KINDS:
        add('garment', kd, {'pixel3d': 'native'}, SRC, label={'gown': 'robe de bal à paniers', 'coat': 'redingote (habit, uniforme)'}[kd]); caps[f'garment:{kd}']['styles'] = dict(NAT)
    for h in COS.HAIR:
        add('hair', h, {'pixel3d': 'native'}, SRC, label=COS.HAIR_LABEL[h]); caps[f'hair:{h}']['styles'] = dict(NAT)
    for i in COS.ITEMS:
        add('item', i, {'pixel3d': 'native'}, SRC, label=COS.ITEM_LABEL[i]); caps[f'item:{i}']['styles'] = dict(NAT)
    for bd in COS.BEARDS:
        add('beard', bd, {'pixel3d': 'native'}, SRC); caps[f'beard:{bd}']['styles'] = dict(NAT)
    # objets détaillés (clé d'épisode `objets`, 01/11/2026) : objets tenus `od_*` en deux versions natives (pixel3d/objets.py + voxelgpu/b_objets.py, piste `held` de b_objets.js)
    from ..engines.pixel3d import objets as OD
    for h in OD.HELD:
        add('item', h, {'pixel3d': 'native'}, 'engines/pixel3d/objets.py + voxelgpu/b_objets.py', label=OD.HELD_LABELS.get(h, h)); caps[f'item:{h}']['styles'] = dict(NAT)
    add('feature', 'objets_detailles', {'pixel3d': 'native'}, 'engines/pixel3d/objets.py + voxelgpu/b_objets.py + voxelgpu_js/engine/b_objets.js',
        note="clé d'épisode `objets` (profil production) : téléphones, combiné et cordon, smartphone lisible, standard, tasses, verres, lampes, écrans, horloge... détaillés, posés et tenus")
    caps['feature:objets_detailles']['styles'] = dict(NAT)
    add('feature', 'skirt_flare', {'pixel3d': 'native'}, SRC, note="jupe qui s'évase en tournant (fonction pure de la vitesse de rotation) et que les jambes ne traversent pas")
    caps['feature:skirt_flare']['styles'] = dict(NAT)
    add('feature', 'face_skin', {'pixel3d': 'native'}, 'engines/pixel3d/face_skin.py + voxelgpu_js/engine/b_costumes.js (setupSkinFace)',
        note='tête peinte en pixel art façon skin (16 x 16 par face), yeux, sourcils et bouche animés ; clé de costume `face_skin`')
    caps['feature:face_skin']['styles'] = dict(NAT)
    for fname, note in (('side_left', 'piste dirigée `side: "left"` : geste en miroir au bras gauche, objet tenu dans la main gauche'),
                        ('kneel', 'piste dirigée `kneel` (0..1) : à genoux ; une robe se pose au sol'), ('sit_floor', 'piste dirigée `sit_floor` (0..1) : assis par terre, jambes repliées')):
        add('feature', fname, {'pixel3d': 'native'}, 'acting/rig.py + acting/directed.py, voxelgpu_js/engine/poses_floor.js', note=note); caps[f'feature:{fname}']['styles'] = dict(NAT)
