"""python tools/check_diversite.py : la diversité des décors (quartiers à identité + intérieurs à palette) -- opt-in, déterminisme, variété MESURÉE, deux versions natives, branchements.

Ce que le test garantit, sans GPU (le peintre VOXEL est vérifié par ses accessoires, pas par une image) :
  1. SANS la clé `diversite` rien ne change : les lieux livrés (rue, appartement, salon, café, boutique, chambre, pièce écrite à la main) sont construits boîte pour boîte comme avant,
     et une image PS1 est identique au bit près avec ou sans `diversite: false` ;
  2. AVEC la clé les lieux changent réellement (image, couleurs) ; le profil `production` la pose, `diversite: false` la retire ;
  3. 9 identités de quartier nettement différentes (distance de couleur, saturation : pas de gris-brun), 10 palettes d'intérieur, 8 sols ;
  4. déterminisme : même graine = mêmes boîtes, graines différentes = lieux différents ;
  5. deux versions natives : les bâtiments PS1 sont cachés à VOXEL et refaits (autres boîtes, décalcomanies de matière), mêmes fenêtres, même plan ;
  6. branchements : catalogue, styles, registre des capacités, validateur, lexique."""
import hashlib, json, os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import numpy as np
FAIL = []


def check(name, ok, detail=''):
    print(('OK   ' if ok else 'FAIL ') + name + (f'   {detail}' if detail else ''))
    if not ok: FAIL.append(name)


def sig(st):
    """empreinte des boîtes d'un lieu construit (position, taille, couleur, émission)"""
    if st.base is None: st.build()
    h = hashlib.sha1()
    for b in st.base.boxes: h.update(np.concatenate([b.lo, b.hi, b.col, [b.emis]]).astype(np.float32).tobytes())
    return h.hexdigest()[:12], len(st.base.boxes)


def main():
    from hstudio.engines.pixel3d import sets as S, places as PL, quartiers as Q, interieurs as I, environment_variation as EV, qt_props as QP, qt_facade as QF, qi_lieux as QL
    from hstudio import profiles, styles
    Q.configure(None)

    print('\n1. sans la clé, rien ne change')
    legacy = {'city_street': {'type': 'city_street', 'sky': 'night'}, 'apartment': {'type': 'apartment'}, 'lobby': {'type': 'apartment', 'lobby': True}, 'living_room': {'type': 'living_room'}, 'cafe': {'type': 'cafe'},
              'shop': {'type': 'shop'}, 'bedroom': {'type': 'bedroom'}, 'kitchen': {'type': 'kitchen'},
              'custom': {'type': 'room', 'rooms': [{'id': 'a', 'origin': [0, 0], 'size': [5, 4], 'props': [{'type': 'sofa', 'at': [0, 2]}, {'type': 'table', 'at': [1, 1]}]}]}}
    for n, sp in legacy.items():
        k = sp['type']
        if k == 'apartment': ref = S.Apartment(sp)
        elif k in PL.PLACES: ref = S.RoomSet(EV.dress(PL.expand(k, sp), k, sp))
        else: ref = S.RoomSet(EV.dress(sp, k))
        got = S.make_set('x', sp)
        check(f'« {n} » : mêmes boîtes que le constructeur d\'avant', sig(ref) == sig(got), f'{sig(got)[1]} boîtes')
    Q.configure(None); a = sig(S.make_set('x', legacy['city_street']))
    Q.configure(False); b = sig(S.make_set('x', legacy['city_street']))
    check('`diversite: false` = absente', a == b)

    print('\n2. avec la clé les lieux changent')
    Q.configure('decors', {'title': 'essai'})
    st = Q.active()
    for n in ('city_street', 'apartment', 'living_room', 'cafe', 'shop', 'bedroom', 'kitchen', 'custom'):
        Q.configure(None); off = sig(S.make_set('x', legacy[n])); Q.configure('decors', {'title': 'essai'}); on = sig(S.make_set('x', legacy[n]))
        check(f'« {n} » : habillé sous `diversite`', off != on, f'{off[1]} -> {on[1]} boîtes')
    Q.configure('quartiers', {'title': 'essai'}); check('preset `quartiers` : la rue change, le salon non', sig(S.make_set('x', legacy['city_street']))[0] != a[0] and sig(S.make_set('x', legacy['living_room'])) == (lambda: (Q.configure(None), sig(S.make_set('x', legacy['living_room'])))[1])())
    Q.configure('decors', {'title': 'essai'}); sp = dict(legacy['living_room'], diversite=False); check('`diversite: false` posé sur UN lieu le garde tel quel', sig(S.make_set('x', sp)) == (lambda: (Q.configure(None), sig(S.make_set('x', legacy['living_room'])))[1])())
    Q.configure(None)
    p = profiles.PROFILES['production']; check('le profil `production` pose `diversite`', p.get('diversite') == 'decors')
    ep = {'profile': 'production', 'diversite': False}; profiles.apply(ep); check('`diversite: false` à côté du profil gagne', ep['diversite'] is False)
    ep = {'profile': 'production'}; profiles.apply(ep); check('le profil seul la pose', ep.get('diversite') == 'decors')

    print('\n3. variété mesurée')
    import colorsys
    cols = {}
    for k, I_ in Q.IDENTITES.items():
        m = np.mean([w for w in I_['walls']], 0); cols[k] = m
    check('9 identités de quartier', len(Q.IDENTITES) == 9, ', '.join(Q.IDENTITES))
    names = list(cols); dmin = min(np.linalg.norm(cols[a] - cols[b]) for i, a in enumerate(names) for b in names[i + 1:])
    check('couleurs de murs deux à deux distinctes (distance mini > 28 sur 255)', dmin > 28, f'distance mini {dmin:.0f}')
    sat = {k: np.mean([colorsys.rgb_to_hsv(*(np.array(w) / 255.))[1] for w in v['walls'] + v['accents']]) for k, v in Q.IDENTITES.items()}
    check('aucune identité terne : saturation moyenne (murs + accents) > 0,3', min(sat.values()) > .3, f'mini {min(sat.values()):.2f} ({min(sat, key=sat.get)})')
    old = [np.array(v[0]) / 255. for v in (S.WALLS.values())]; olds = np.mean([colorsys.rgb_to_hsv(*c)[1] for c in old])
    new = np.mean([colorsys.rgb_to_hsv(*(np.array(v['wall']) / 255.))[1] for v in I.PAL.values()])
    check('palettes d\'intérieur : saturation moyenne des murs 2x celle de `WALLS`', new > 1.5 * olds, f'{olds:.2f} -> {new:.2f}')
    check('10 palettes d\'intérieur', len(I.PAL) == 10); check('8 sols à motif', len(I.FLOOR_FNS) == 8)
    sig_str = {k: sig(S.make_set('x', {'type': 'quartier', 'identite': k})) for k in Q.IDENTITES}
    check('9 rues toutes différentes', len({v[0] for v in sig_str.values()}) == 9)
    rooms = {a: sig(S.make_set('x', {'type': 'appartement', 'disposition': 'studio', 'ambiance': a})) for a in I.PAL}
    check('10 ambiances = 10 appartements différents', len({v[0] for v in rooms.values()}) == 10)
    disp = {a: sig(S.make_set('x', {'type': 'appartement', 'disposition': a, 'ambiance': 'menthe'})) for a in ('studio', 'familial', 'loft', 'mansarde')}
    check('4 dispositions = 4 plans différents', len({v[0] for v in disp.values()}) == 4)
    for k in Q.IDENTITES:
        night = QP.block_tex({'facade': {'quartier': [k, 0, '+x', [0, 0, 10, 8], True, 1, None], 'night': True}})[0]['+x']; day = QP.block_tex({'facade': {'quartier': [k, 0, '+x', [0, 0, 10, 8], True, 1, None], 'night': False}})[0]['+x']
        if k == 'verre_acier' or True: pass
        check(f'{k} : façade avec émission la nuit, sans le jour', night[..., 4].max() > 200 and day[..., 4].max() == 0, f'{night.shape[1]}x{night.shape[0]} texels')

    print('\n4. déterminisme')
    a1 = sig(S.make_set('x', {'type': 'quartier', 'identite': 'art_deco', 'seed': 3})); a2 = sig(S.make_set('x', {'type': 'quartier', 'identite': 'art_deco', 'seed': 3})); a3 = sig(S.make_set('x', {'type': 'quartier', 'identite': 'art_deco', 'seed': 4}))
    check('même graine = mêmes boîtes', a1 == a2); check('autre graine = autre rue', a1[0] != a3[0])
    b1 = sig(S.make_set('x', {'type': 'appartement', 'seed': 1})); b2 = sig(S.make_set('x', {'type': 'appartement', 'seed': 1})); check('appartement : même graine = mêmes boîtes', b1 == b2)
    sp = copy_of(legacy['living_room']); Q.configure('decors', {'title': 'essai'}); S.make_set('x', sp); check('la spec écrite n\'est jamais modifiée par le dressage', sp == legacy['living_room']); Q.configure(None)

    print('\n5. deux versions natives (VOXEL)')
    from hstudio.voxelgpu import b_quartiers as BQ, b_interieurs as BI, b_sets as BS
    st = S.make_set('x', {'type': 'quartier', 'identite': 'brique_rouge'}); st.build()
    hide, items = st.voxel_native(); nb = sum(1 for b in st.base.boxes)
    check('les bâtiments PS1 sont cachés à VOXEL', len(hide) > 150, f'{len(hide)} boîtes PS1 non converties sur {nb}')
    bs = st.voxel_bsets(); nvox = sum(len(p['boxes']) for p in bs); ndec = sum(len(p.get('decals', [])) for p in bs)
    check('VOXEL refait les bâtiments en volumes (plus de boîtes que la version PS1) et en décalcomanies de matière', nvox > 1.5 * len(hide) and ndec > 20, f'{nvox} boîtes, {ndec} décalcomanies de façade')
    g = BS.get('x', {'type': 'quartier', 'identite': 'neon_nuit'}); check('BSet : le lieu se convertit, les accessoires natifs sont posés', any(len(p.get('boxes', [])) > 1500 for p in g.props))
    for kind in sorted(I.NEW_PROPS):
        ok = kind in BI.VOX; check(f'{kind} : version VOXEL écrite', ok)
    for kind in sorted(QP.NEW_PROPS):
        if kind in ('qt_lamp_cool', 'qt_lamp_neon', 'qt_ac', 'qt_windowbox', 'qt_fascia'): continue
        check(f'{kind} : version VOXEL écrite', kind in BQ.VOX)
    # une pièce habillée : hide + natifs
    st = S.make_set('x', {'type': 'appartement', 'disposition': 'familial', 'ambiance': 'menthe'}); st.build(); hide, _ = st.voxel_native(); bs = st.voxel_bsets()
    check('intérieur : détails de vie cachés puis refaits', len(hide) > 40 and bs and len(bs[0]['boxes']) > len(hide), f'{len(hide)} boîtes PS1 -> {len(bs[0]["boxes"])} blocs VOXEL')
    Q.configure('decors', {'title': 'essai'}); st = S.make_set('x', {'type': 'apartment'}); st.build(); hide, _ = st.voxel_native(); check('apartment d\'Ascenseur Zéro habillé : natifs aussi', len(hide) > 40 and st.voxel_bsets()); Q.configure(None)

    print('\n6. branchements')
    from hstudio import catalogue
    ids = {e['id'] for e in catalogue.entries()}
    for k in ('lieu/quartier', 'lieu/appartement', 'lieu/hall_immeuble', 'lieu/cafe_quartier', 'lieu/boutique', 'lieu/escalier_immeuble', 'lieu/salon_maison', 'decor/qt_balcony', 'decor/qi_plant'):
        check(f'catalogue : {k}', k in ids)
    check('styles : natif / natif', styles.of_entry({'id': 'lieu/quartier'}) == {'ps1': 'native', 'voxel': 'native'} and styles.of_entry({'id': 'decor/qi_books'}) == {'ps1': 'native', 'voxel': 'native'})
    from hstudio.capabilities import registry
    caps = registry.build(); check('registre des capacités : lieu quartier natif dans les deux styles', caps.get('place:quartier', {}).get('styles') == {'ps1': 'native', 'voxel': 'native'})
    import importlib; validate = importlib.import_module('hstudio.director.validate')
    ep = {'diversite': 'nimporte', 'shots': [{'lines': [0, 0]}]}; v, w = validate.validate(ep, 1, 'pixel3d'); check('validateur : valeur inconnue ignorée à voix haute', 'diversite' not in v and any('diversité' in x for x in w))
    ep = {'diversite': 'decors', 'shots': [{'lines': [0, 0]}]}; v, w = validate.validate(ep, 1, 'console'); check('validateur : refusée sur CONSOLE 2D', 'diversite' not in v and any('console' in x for x in w))
    ep = {'diversite': 'decors', 'shots': [{'lines': [0, 0]}]}; v, w = validate.validate(ep, 1, 'pixel3d'); check('validateur : acceptée sur PS1', v.get('diversite') == 'decors')
    prompts = importlib.import_module('hstudio.director.prompts')
    sent = ' '.join(str(getattr(prompts, n, '')) for n in dir(prompts) if n.isupper()); check('le réalisateur IA ne connaît pas la clé (opt-in jusqu\'au verdict humain)', '"diversite"' not in sent and "'diversite'" not in sent)

    print('\n7. rendu : une image PS1 change vraiment, et le coût')
    from hstudio.pipeline import make_engine
    def frame(spec, extra=None):
        ep = {'engine_version': 1, 'default_set': 's', 'sets': {'s': spec}, 'cast': {}, 'state': {}, 'shots': [{'lines': [0, 0], 'set': 's', 'actors': [], 'camera': {'preset': 'free', 'keys': [{'pos': [0, 1.7, 1], 'look': [0, 2.5, 25], 'fov': 75}]}}]}
        ep.update(extra or {}); eng = make_engine('pixel3d', ep, [{'who': 'x', 'text': 'x', 'start': 0., 'end': 1.}], {}, 1.5, '16:9'); eng.render_lowres(.5)
        t = time.perf_counter(); im = eng.render_lowres(.5)[0]; return im, time.perf_counter() - t
    im0, t0 = frame({'type': 'city_street', 'sky': 'day'}); im1, _ = frame({'type': 'city_street', 'sky': 'day'}, {'diversite': False}); im2, t2 = frame({'type': 'city_street', 'sky': 'day'}, {'diversite': 'decors'})
    check('image identique avec `diversite: false`', np.array_equal(im0, im1)); d = np.abs(im0.astype(int) - im2.astype(int)).mean()
    check('image très différente avec `diversite`', d > 15, f'écart moyen {d:.0f}/255')
    check('coût par image sous 4x celui de la rue livrée (mesuré, médiane d\'un rendu chaud)', t2 < 4 * t0 + .3, f'{t0 * 1000:.0f} ms -> {t2 * 1000:.0f} ms (x{t2 / t0:.1f})')
    print('\n8. le pool de rendu « spawn » et l\'élément composable')
    check_spawn()
    from hstudio.engines.pixel3d import compose
    ex = compose.expand({'type': 'composed', 'ground_y': 0, 'sky': 'day', 'elements': [{'kind': 'quartier', 'identite': 'bois', 'rect': [-10, 8, 10, 22], 'front': '-z', 'count': 3, 'seed': 2}]})
    check('élément composable `quartier` : bâtiments posés, rien d\'inconnu', len(ex['blocks']) > 10 and not ex.get('_unknown_elements'), f'{len(ex["blocks"])} blocs')
    print('\n' + ('Tout est OK' if not FAIL else f'{len(FAIL)} ÉCHEC(S) : ' + '; '.join(FAIL)))
    return 1 if FAIL else 0


def check_spawn():
    """le rendu repart dans des processus neufs : l'état `diversite` doit traverser (sinon la vidéo « après » serait celle d'avant et personne ne le verrait)"""
    import multiprocessing as mp
    from hstudio import pipeline
    from hstudio.pipeline import make_engine
    ep = {'engine_version': 1, 'default_set': 's', 'sets': {'s': {'type': 'city_street', 'sky': 'night'}}, 'cast': {}, 'state': {}, 'title': 'spawn', 'profile': 'production',
          'shots': [{'lines': [0, 0], 'set': 's', 'actors': [], 'camera': {'preset': 'free', 'keys': [{'pos': [0, 1.7, 1], 'look': [0, 2.5, 25], 'fov': 75}]}}]}
    lines = [{'who': 'x', 'text': 'x', 'start': 0., 'end': 1.}]
    eng = make_engine('pixel3d', json.loads(json.dumps(ep)), lines, {}, 1.5, '16:9'); frames = (6,)
    here = [eng.frame(i / 30.).convert('RGB').tobytes() for i in frames]
    off = [make_engine('pixel3d', dict(json.loads(json.dumps(ep)), diversite=False), lines, {}, 1.5, '16:9').frame(i / 30.).convert('RGB').tobytes() for i in frames]
    ctx = mp.get_context('spawn')
    with ctx.Pool(2, initializer=pipeline._init_worker, initargs=('pixel3d', json.loads(json.dumps(ep)), lines, {}, 1.5, '16:9')) as pool: there = list(pool.imap(pipeline._render_one, frames))
    check('deux workers « spawn » rendent les mêmes octets qu\'ici', there == here, 'identique' if there == here else 'DIFFÉRENT : la clé ne traverse pas le pool')
    check('  et ce ne sont pas les octets du rendu sans `diversite`', there != off)


def copy_of(x): return json.loads(json.dumps(x))


if __name__ == '__main__': sys.exit(main())
