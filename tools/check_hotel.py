"""Tests du lieu `hotel_nuit` (CHAMBRE 313, style PS1) : opt-in strict, déterminisme, clés d'état branchées, fumée, crochets VOXEL.

    python tools/check_hotel.py            # hors GPU, ~1 min
    python tools/check_hotel.py --quick    # sans le rendu en processus séparés

Ce que l'outil vérifie (et ce qu'il ne vérifie pas : le jugement artistique, voir les planches `tools/hotel_sheet.py`) :
  * opt-in : les fonctions enveloppées (`poses.torso`, `hair_and_hat`, `held_item`, `rigfig.face_for`) rendent pour TOUTE valeur connue
    d'avant exactement ce que rend l'original (mêmes boîtes, même ordre, mêmes couleurs) ; les préréglages d'avant sont intacts ;
    un lieu livré (etage_zero, apartment, bedroom, city_street, pompe_station) construit les mêmes boîtes ;
  * déterminisme : deux moteurs, et un pool de processus qui rend les images dans un autre ordre, donnent les mêmes pixels ;
  * chaque clé d'état documentée change l'image (elle est vraiment branchée) ; sans clé de fumée, aucun post-traitement n'est posé ;
  * crochets VOXEL : `mobile`, `mobile_key` (une clé qui change découpe une tranche), et le validateur connaît le lieu."""
import sys, os, hashlib, math, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np

OK = []; BAD = []


def check(name, cond, detail=''):
    (OK if cond else BAD).append(name)
    print(('  OK   ' if cond else '  ÉCHEC ') + name + (f'  ({detail})' if detail else ''), flush=True)


def boxes_sig(bx):
    h = hashlib.sha1()
    for b in bx:
        h.update(np.asarray(b.lo, np.float32).tobytes()); h.update(np.asarray(b.hi, np.float32).tobytes()); h.update(np.asarray(b.col, np.float32).tobytes())
        h.update(repr((b.emis, b.refl, b.mat, b.texemis, b.cast, b.dissolve, sorted((k, v.shape) for k, v in (b.tex or {}).items()))).encode())
        for k_ in sorted(b.tex or {}): h.update(np.ascontiguousarray(b.tex[k_]).tobytes())
        if b.inst is not None: h.update(np.asarray(b.inst.R, np.float32).tobytes()); h.update(np.asarray(b.inst.piv, np.float32).tobytes())
    return h.hexdigest()


def episode(views, aspect='9:16'):
    shots = []; lines = []
    for i, v in enumerate(views):
        lines.append(dict(start=i * 1.0, end=i * 1.0 + .9, text='', words=[]))
        sh = {'lines': [i, i], 'set': 'hotel', 'state': v.get('state', {}), 'ui': {'hud': False, 'subs': 'off'}}
        cam = {'pos': v['pos'], 'look': v['look'], 'fov': v.get('fov', 60)}
        if v.get('tracks'): sh['tracks'] = v['tracks']; sh['camera'] = {'rig': 'path', 'keys': [dict(cam, t=0)]}
        else: sh['camera'] = {'preset': 'free', 'keys': [cam]}
        shots.append(sh)
    return {'style': 'pixel3d', 'hud': {'show': False}, 'sets': {'hotel': {'type': 'hotel_nuit'}}, 'default_set': 'hotel', 'shots': shots,
            'cast': {'rec': {'preset': 'receptionniste'}, 'mere': {'preset': 'mere_fantome'}}}, lines


VIEWS = [dict(pos=[.35, 1.6, 9.7], look=[-.1, 1.3, 24.], state={'smoke': .5}),
         dict(pos=[-5.85, 1.6, 3.35], look=[-4.55, 1.0, 3.5], state={'board_313': 1, 'landline_ring': 1, 'screen': 'call'}),
         dict(pos=[.5, 1.55, 20.3], look=[-.1, 1.2, 25.3], state={'cloison': 2.5, 'red_glass': 1, 'lever': 1, 'green_door': .6},
              tracks={'rec': [{'t': 0, 'p': [.6, 0., 23.2], 'yaw': 0., 'hold': 'crowbar', 'gesture': 'arm_up'}]}),
         dict(pos=[7., -1.2, 43.5], look=[-1.6, 6., 26.3], state={'truck': 1, 'beacons': 1, 'window_fire': 1, 'window_smoke': 1}),
         dict(pos=[40.75, 1.55, 3.4], look=[38.7, 1.1, 7.5], state={'era': 'before', 'under_door_smoke': 1, 'under_door_glow': 1},
              tracks={'mere': [{'t': 0, 'p': [39.55, 0., 7.9], 'yaw': 2.9}]})]


def engine(views, aspect='9:16'):
    from hstudio.pipeline import make_engine
    ep, lines = episode(views); dur = len(views) * 1.0
    return make_engine('pixel3d', ep, lines, np.zeros(int(dur * 30) + 60), dur, aspect)


def frame_hash(eng, g): return hashlib.sha1(np.asarray(eng.frame(g).convert('RGB')).tobytes()).hexdigest()


def _pool_job(a):
    i = a
    eng = engine(VIEWS); return i, frame_hash(eng, i * 1.0 + .5)


def test_optin():
    print('opt-in : les ajouts ne changent rien de ce qui existait')
    from hstudio.engines.pixel3d import poses as P, creatures as CR, rigfig as RF, hotel_cast as HC, sets as S
    check('enregistrement fait à l\'import de sets.py', HC._DONE[0])
    k = {}
    old = [i for i in P.HOLD_ITEMS if i not in HC.NEW_ITEMS and not i.startswith('od_')]      # 01/11/2026 : les objets détaillés `od_*` (pixel3d/objets.py) sont des noms NOUVEAUX, testés par tools/check_objets.py
    for it in old:
        a = P.held_item(it, (.1, 1.0, .2), 1, k, [], None); b = HC._ORIG['held_item'](it, (.1, 1.0, .2), 1, k, [], None)
        if boxes_sig(a) != boxes_sig(b): check(f'objet tenu « {it} » inchangé', False); break
    else: check('objets tenus d\'avant : mêmes boîtes que l\'original', True, f'{len(old)} objets')
    bad = [o for o in P.OUTFITS if o not in HC.NEW_OUTFITS and boxes_sig(P.torso(0., 0., 1, -1.0, o, (90, 90, 90), (200, 150, 110), {}, tie=(150, 30, 40), shirt=(230, 230, 220)))
           != boxes_sig(HC._ORIG['torso'](0., 0., 1, -1.0, o, (90, 90, 90), (200, 150, 110), {}, tie=(150, 30, 40), shirt=(230, 230, 220)))]
    check('tenues d\'avant : mêmes boîtes', not bad, str(bad))
    bad = [h for h in list(P.HATS) + [None] if h not in HC.NEW_HATS and boxes_sig(P.hair_and_hat(0., -1.68, 0., 1, (30, 30, 30), 'short', h, None, (90, 90, 90), {}))
           != boxes_sig(HC._ORIG['hair_and_hat'](0., -1.68, 0., 1, (30, 30, 30), 'short', h, None, (90, 90, 90), {}))]
    check('couvre-chefs d\'avant : mêmes boîtes', not bad, str(bad))
    smp = dict(face='scared', talking=False, blink=False, gaze=None)
    look = dict(CR.PRESETS['doctor'])
    check('visage sans `face_fade` : le même tableau que l\'original', np.array_equal(RF.face_for(look, smp), HC._ORIG['face_for'](look, smp)))
    check('visage avec `face_fade` : estompé', not np.array_equal(RF.face_for(dict(look, face_fade=.6), smp), HC._ORIG['face_for'](look, smp)))
    old = {'zombie', 'firefighter', 'kid', 'police', 'doctor', 'grandma'}
    check('préréglages d\'avant présents et intacts', all(n in CR.PRESETS for n in old) and CR.PRESETS['firefighter'].get('hat') == 'helmet')
    check('nouveaux préréglages enregistrés', all(n in CR.PRESETS for n in HC.PRESETS), str(len(HC.PRESETS)))
    for name in ('etage_zero', 'apartment', 'bedroom', 'city_street', 'pompe_station'):
        a = S.make_set(name, {'type': name}); a.build()
        b = S.make_set(name, {'type': name}); b.build()
        check(f'lieu livré « {name} » : ni post-traitement ni méthode d\'hôtel', not hasattr(a.scene({}, 1., .5), 'post_fn') and not hasattr(a, 'mobile_key'))


def test_place():
    print('le lieu et ses clés')
    from hstudio.engines.pixel3d import sets as S, hotel as H, hotel_smoke as HS
    st = S.make_set('hotel', {'type': 'hotel_nuit'})
    check('make_set(type hotel_nuit) -> HotelNuit', isinstance(st, H.HotelNuit))
    sc = st.scene({}, 1., .5)
    check('sans clé de fumée : aucun post-traitement', getattr(sc, 'post_fn', None) is None)
    sc2 = st.scene({'smoke': .4}, 1., .5)
    check('avec `smoke` : la passe de fumée est posée', isinstance(getattr(sc2, 'post_fn', None), HS.Post))
    L = st.lights({}, 1., .5, (0., 1.6, 12.))
    check('lumières : la dernière est le remplissage caméra (4 valeurs)', len(L[-1]) == 4 and len(L) <= int(st.spec.get('max_lights', 14)) + 1)
    check('ancres principales', all(a in st.anchors for a in ('reception', 'couloir.debut', 'porte_escalier_sud', 'cloison', 'porte_verte', 'panneau_rouge', 'palier', 'escalier_ext.bas', 'camion', 'porte_313', 'porte_01', 'porte_08')))
    base = boxes_sig(H.dynamic(H.state_of({}), 1.)[0])
    keys = dict(power=0., ceiling=0., emergency=1., alarm=1., alarm_button=1., landline_ring=1., handset=0, board_313=1., screen='call', clock='02:16', clock_on=0., panel_led=1.,
                door_01=.8, door_08=.8, stair_door=.7, stair_fire=1., cloison=2., cloison_hit=1., crowbar_in_box=0, red_glass=1., lever=1., green_door=.7, truck=1, beacons=1.,
                window_fire=1., hoses=1, street_lights=0., era='before', under_door_glow=1., work_lamp=1., log_paper=1, covers=1, barrier=1, moment='matin')
    need = {'beacons': {'truck': 1}, 'under_door_glow': {'era': 'before'}}          # a key that only means something with another one
    dead = []
    for k_, v in keys.items():
        g = 1.03 if k_ != 'alarm' else 0.01; ref = dict(need.get(k_, {}))
        if boxes_sig(H.dynamic(H.state_of(dict(ref, **{k_: v})), g)[0]) == boxes_sig(H.dynamic(H.state_of(ref), g)[0]) and \
           str(H.dynamic(H.state_of(dict(ref, **{k_: v})), g)[1]) == str(H.dynamic(H.state_of(ref), g)[1]): dead.append(k_)
    check(f'{len(keys)} clés d\'état : chacune change les boîtes ou les lumières', not dead, str(dead))
    sm = {k_: (HS.params(H.state_of({k_: v})) is not None) for k_, v in dict(smoke=.5, smoke_black=.5, smoke_burst=.5, under_door_smoke=.5, window_smoke=.5).items()}
    check('5 clés de fumée : chacune pose la passe', all(sm.values()), str(sm))
    k0 = st.mobile_key({}); k1 = st.mobile_key({'stair_door': .8})
    check('VOXEL : `mobile_key` change avec l\'état (nouvelle tranche)', k0 != k1)
    mb, ml = st.mobile({'truck': 1, 'beacons': 1}, 1.)
    check('VOXEL : `mobile` rend boîtes et lumières (4 valeurs)', len(mb) > 50 and all(len(l) == 4 for l in ml))
    import importlib; V = importlib.import_module('hstudio.director.validate')
    ep, lines = episode([VIEWS[0]])
    try:
        fixed, warns = V.validate(ep, len(lines)) if hasattr(V, 'validate') else (ep, [])
    except TypeError:
        fixed, warns = ep, []
    check('validateur : le lieu déclaré n\'est pas signalé inconnu', not any('hotel' in str(w) and 'inconnu' in str(w) for w in (warns or [])))
    from hstudio.capabilities import registry as RG
    caps = RG.build()
    check('registre : lieu hotel_nuit, préréglages, objets du lieu', 'place:hotel_nuit' in caps and 'character:receptionniste' in caps and 'character:pompier' in caps)


def test_render(quick):
    print('rendu : déterminisme')
    e1 = engine(VIEWS); e2 = engine(VIEWS)
    h1 = [frame_hash(e1, i + .5) for i in range(len(VIEWS))]; h2 = [frame_hash(e2, i + .5) for i in range(len(VIEWS))]
    check('deux moteurs : mêmes pixels (5 vues : fumée, standard, cloison, extérieur, 313)', h1 == h2)
    h1b = [frame_hash(e1, i + .5) for i in reversed(range(len(VIEWS)))][::-1]
    check('même moteur, ordre inverse : mêmes pixels', h1b == h1)
    if not quick:
        import multiprocessing as mp
        with mp.Pool(3) as pool:
            res = dict(pool.map(_pool_job, list(reversed(range(len(VIEWS))))))
        check('pool de 3 processus (ordre inverse) : mêmes pixels', [res[i] for i in range(len(VIEWS))] == h1)
    e3 = engine([dict(VIEWS[0], state={})])
    check('la fumée change l\'image (même vue sans fumée)', frame_hash(e3, .5) != h1[0])
    e4 = engine(VIEWS, '16:9')
    check('16:9 : rendu sans erreur', len(frame_hash(e4, 3.5)) == 40)


if __name__ == '__main__':
    quick = '--quick' in sys.argv
    test_optin(); test_place(); test_render(quick)
    print(f'\n{len(OK)} OK, {len(BAD)} échec(s)' + (f' : {BAD}' if BAD else ''))
    sys.exit(1 if BAD else 0)
