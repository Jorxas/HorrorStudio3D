"""Vérifications des costumes XVIIIe (clé de cast `costume`), sans réseau, sans clé :

    python tools/check_costumes.py            opt-in, déterminisme, évasement, traversées PS1 mesurées sur la géométrie émise, câblage
    python tools/check_costumes.py --voxel    + traversées mesurées DANS le peintre VOXEL (navigateur logiciel, aucun GPU : voxelgpu_js/costume_probe.js)

Ce qui est mesuré, et comment :
  * opt-in : un épisode SANS `costume` donne les mêmes octets d'image PS1 et le même contrat VOXEL (empreinte SHA-256) que le moteur
    dont les crochets des costumes sont neutralisés ; le contrat n'a aucune clé `costume`.
  * déterminisme : deux moteurs neufs -> mêmes octets ; deux contrats -> même empreinte ; l'évasement est une fonction pure de la vitesse
    de rotation, et la piste `f` du contrat VOXEL est exactement `costumes.flare(spin)` des échantillons de PS1 (une seule logique).
  * traversée PS1 : 27 points de chaque boîte de jambe émise doivent être DANS une boîte de jupe émise (marche à 4 vitesses sur un cycle
    complet, course, assis, accroupi, à genoux, tour sur soi) ; pour la redingote : aucun point de jambe dans un panneau arrière des basques.
  * traversée VOXEL (--voxel) : même idée dans la vraie page du peintre, par lancer de rayons depuis l'axe de la jupe.
"""
import copy, hashlib, json, math, os, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import numpy as np
from hstudio.engines.pixel3d import costumes as COS
from hstudio.acting import rig

PI = math.pi; RES = []


def check(name, ok, detail=''):
    RES.append(bool(ok)); print(('OK    ' if ok else 'ÉCHEC ') + name + (f'   {detail}' if detail != '' else ''), flush=True)


def grid_pts(b, n=3):
    """n^3 points of a (possibly oriented) r3d box, world coordinates"""
    lo, hi = b.lo, b.hi; out = []
    for fx in np.linspace(.02, .98, n):
        for fy in np.linspace(.02, .98, n):
            for fz in np.linspace(.02, .98, n):
                p = lo + (hi - lo) * np.array([fx, fy, fz], np.float32)
                out.append(p if b.inst is None else b.inst.R @ p + b.inst.piv)
    return out


def inside_box(b, p, eps=1e-4):
    q = p if b.inst is None else b.inst.R.T @ (p - b.inst.piv)
    return bool(np.all(q >= b.lo - eps) and np.all(q <= b.hi + eps))


def sample(**rg):
    r = dict(t=1., seed=0., phase=0., gait=0., run=0., stride=1.25, sit=0., crouch=0., gestures=[], head=(0., 0.), reach={}); r.update(rg)
    return dict(x=0., y=0., z=0., heading=0., rig=r, face='neutral', hold=None, spin=rg.pop('spin', 0.) if 'spin' in rg else 0.)


def ps1_traversal(cid, poses):
    """-> (points tested, points of legs outside the skirt / inside a coat tail)"""
    from hstudio.engines.pixel3d.r3d import C
    tested = bad = 0; worst = 0.
    for s in poses:
        COS.PARTS = {}
        COS.build(s, {'costume': cid}, None, {}, None, [])
        parts = COS.PARTS; COS.PARTS = None
        legs = parts.get('leg', []); skirt = parts.get('skirt', []); tails = parts.get('tail', [])
        if skirt:
            ys = [b.wlo[1] for b in skirt]; floor_top = min(ys); waist = max(b.whi[1] for b in skirt)
            for lb in legs:
                for p in grid_pts(lb):
                    if p[1] > waist - .02: continue
                    q = p.copy(); q[1] = max(q[1], floor_top + .002); tested += 1
                    if not any(inside_box(b, q) for b in skirt): bad += 1
        for tb in tails:
            for lb in legs:
                for p in grid_pts(lb, 4):
                    tested += 1
                    if inside_box(tb, p, -1e-4): bad += 1
    return tested, bad


def poses_walk():
    out = []
    for stride, run in ((.9, 0.), (1.25, 0.), (1.6, 0.), (2.1, .6)):
        for i in range(24):
            out.append(sample(phase=2 * PI * i / 24, gait=1., run=run, stride=stride))
    return out


def poses_other():
    return [sample(sit=1.), sample(sit=.5), sample(crouch=1.), sample(crouch=.5), sample(spin=7.5), sample(spin=-4.), sample(phase=1., gait=1., spin=6.),
            sample(kneel=1.), sample(kneel=.5), sample(sit_floor=1.), sample(sit_floor=.5)]


def directed(cast, dur=2.0, spin=False, walk=False):
    tracks = {}
    for i, cid in enumerate(cast):
        x = (i - (len(cast) - 1) / 2) * 1.8
        if spin: tracks[cid] = [{'t': j * .25, 'p': [x, 0, 0], 'yaw': PI + sum([0, .2, .8, 1.5, 1.6, 1.6, 1.6, 1.5, .9, .3][:j + 1]), 'face': 'happy'} for j in range(10)]
        elif walk: tracks[cid] = [{'t': 0, 'p': [x - 1.2, 0, 0], 'yaw': PI / 2}, {'t': dur, 'p': [x + 1.2, 0, 0], 'yaw': PI / 2}]
        else: tracks[cid] = [{'t': 0, 'p': [x, 0, 0], 'yaw': PI}]
    ep = {'style': 'pixel3d', 'genre': 'drama', 'music': 'none', 'duration': dur, 'default_set': 'room', 'cast': cast,
          'sets': {'room': {'type': 'room', 'clean': True, 'ambient': [.4, .4, .4], 'rooms': [{'id': 'a', 'origin': [0, -8], 'size': [14, 14], 'light': 'warm'}]}},
          'hud': {'title': [], 'part': '', 'hearts': []},
          'shots': [{'lines': [0, 0], 'pre': 0., 'set': 'room', 'ui': {'hud': False, 'subs': 'off'}, 'tracks': tracks,
                     'camera': {'rig': 'path', 'keys': [{'t': 0, 'pos': [0, 1.4, -6], 'look': [0, 1.0, 0], 'fov': 50}]}}]}
    return ep, [{'start': 0., 'end': dur, 'text': '', 'speaker': 'n'}]


def ps1_bytes(ep, lines, t):
    from hstudio.pipeline import make_engine
    e = make_engine('pixel3d', copy.deepcopy(ep), lines, np.zeros(200), lines[-1]['end'], '9:16')
    return np.asarray(e.frame(t).convert('RGB')).tobytes()


def contract(ep, lines):
    from hstudio.voxelgpu import from_ps1, contract as C
    c = from_ps1.build(copy.deepcopy(ep), lines, lines[-1]['end'], '9:16', 24, None)
    return c, C.digest(c)


class neutralised:
    """the costume hooks replaced by no-ops: the engine as it was before this module"""
    def __enter__(self):
        from hstudio.voxelgpu import b_costumes as BCO
        self.s = (COS.add_spin, COS.wants, BCO.resolve_casts, BCO.add_stage_tracks)
        COS.add_spin = lambda sa, samp, looks, T: samp; COS.wants = lambda look: False
        BCO.resolve_casts = lambda casts, looks, baked: casts; BCO.add_stage_tracks = lambda *a, **k: None
    def __exit__(self, *a):
        from hstudio.voxelgpu import b_costumes as BCO
        COS.add_spin, COS.wants, BCO.resolve_casts, BCO.add_stage_tracks = self.s


def main():
    voxel = '--voxel' in sys.argv
    # ---------------------------------------------------------------- opt-in
    plain = {'hero': {'outfit': 'hoodie', 'hood': [180, 70, 60]}, 'zoe': {'outfit': 'dress', 'hair_style': 'long', 'headphones': False}}
    ep0, l0 = directed(plain, walk=True)
    samp = {'hero': {'heading': 0.}}
    check('sans costume : add_spin rend le MÊME objet (aucune copie, aucune clé ajoutée)', COS.add_spin(None, samp, {'hero': {}}, 0.) is samp)
    check('sans costume : spec_of / wants = rien', COS.spec_of({}) is None and COS.spec_of({'outfit': 'dress'}) is None and not COS.wants(None))
    a = ps1_bytes(ep0, l0, .9)
    with neutralised(): b = ps1_bytes(ep0, l0, .9)
    check('PS1 sans costume : mêmes octets que le moteur sans les crochets des costumes', a == b, f'{len(a)} octets')
    c1, d1 = contract(ep0, l0)
    with neutralised(): c0, d0 = contract(ep0, l0)
    check('VOXEL sans costume : même contrat (empreinte SHA-256) que sans les crochets', d1 == d0, d1[:16])
    check('VOXEL sans costume : aucune clé `costume` dans le contrat', not any('costume' in v for v in c1['casts'].values()) and not any('costume' in s for s in c1['stages']))
    # ---------------------------------------------------------------- determinism and the flare function
    cast = {'angelica': {'costume': 'angelica'}, 'hamilton': {'costume': 'hamilton'}, 'eliza': {'costume': 'eliza'}}
    ep1, l1 = directed(cast, spin=True, dur=2.5)
    x1 = ps1_bytes(ep1, l1, 1.1); x2 = ps1_bytes(ep1, l1, 1.1)
    check('PS1 avec costumes : deux moteurs neufs, mêmes octets', x1 == x2, hashlib.sha256(x1).hexdigest()[:16])
    check('PS1 avec costumes : l\'image change vraiment (ce n\'est pas l\'image sans costume)', x1 != ps1_bytes(directed({k: {} for k in cast}, spin=True, dur=2.5)[0], l1, 1.1))
    ca, da = contract(ep1, l1); cb, db = contract(ep1, l1)
    check('VOXEL avec costumes : deux contrats, même empreinte', da == db, da[:16])
    fl = [COS.flare(w) for w in np.linspace(-12, 12, 241)]
    check('évasement : 0 au repos et sous le seuil, 1 au-delà, monotone, impair', COS.flare(0) == 0 and COS.flare(COS.W0) == 0 and abs(COS.flare(COS.W1) - 1) < 1e-9
          and all(fl[i] <= fl[i + 1] + 1e-12 for i in range(len(fl) - 1)) and all(abs(COS.flare(w) + COS.flare(-w)) < 1e-12 for w in (1, 3, 5, 9)))
    check('évasement : fonction pure (mêmes entrées -> mêmes sorties, 1000 appels)', len({COS.flare(5.3) for _ in range(1000)}) == 1)
    st = ca['stages'][0]; tr = st.get('costume', {})
    check('contrat : piste d\'évasement présente pour les robes qui tournent', 'f' in tr.get('angelica', {}) and max(abs(v) for v in tr['angelica']['f']) > .8, f"max {max(abs(v) for v in tr.get('angelica', {}).get('f', [0])):.2f}")
    # same logic in both styles: recompute the PS1 spin of each baked frame and compare with the contract's track
    from hstudio.voxelgpu import from_ps1, ps1_bake as PB
    from hstudio.engines.pixel3d.render import Pixel3DEngine
    eng = Pixel3DEngine(copy.deepcopy(ep1), l1, from_ps1._env_from_lines(l1, 2.5), 2.5, '9:16'); baked = PB.bake(eng, 24, None)
    want = [round(COS.flare(fr['samp']['angelica'].get('spin', 0.)), 3) for fr in baked[0].frames]
    check('les deux styles lisent le même évasement (piste VOXEL == flare(spin) de PS1, image par image)', tr['angelica']['f'][:len(want)] == want, f'{len(want)} images')
    h = tr.get('eliza', {}).get('h')
    check('accessoires : piste par image dans le contrat (bouquet d\'Eliza tenu)', h is not None and all(v == ca['casts']['eliza']['costume']['items'].index('bouquet') for v in h))
    # ---------------------------------------------------------------- painted pixel heads (face_skin)
    from hstudio.engines.pixel3d import face_skin as FS
    sk = FS.skin_of(COS.spec_of({'costume': 'hamilton'}))
    full = sk is not None and all(f'{e}_{d}' in sk['eyes'] for e in FS.EYE_STATES for d in (-1, 0, 1)) and all(m in sk['mouth'] for m in FS.MOUTHS) and len(sk['brows']) == 9
    check('tête peinte : grilles 16 x 16 (face, côtés, arrière, dessus) et tous les calques animés (yeux, sourcils, bouche)', full and all(len(g) == 16 and all(len(r) == 16 for r in g) for g in sk['grids'].values()))
    el = COS.spec_of({'costume': 'eliza'}); base = dict(x=0., z=0., heading=0., rig={}, face='neutral', talking=False, blink=False)
    t0_ = FS.textures(el, base, 0.)['+z']; tb = FS.textures(el, dict(base, blink=True), 0.)['+z']
    tt = FS.textures(el, dict(base, talking=True), .8)['+z']; ta = FS.textures(el, dict(base, face='angry'), 0.)['+z']
    eye = lambda a: a[5:8, 3:13]; mouth = lambda a: a[10:16, 4:12]; brow = lambda a: a[2:6]
    check('tête peinte PS1 : les paupières se ferment au clignement, la bouche s\'ouvre en parlant, les sourcils suivent la colère',
          not np.array_equal(eye(t0_), eye(tb)) and not np.array_equal(mouth(t0_), mouth(tt)) and not np.array_equal(brow(t0_), brow(ta)))
    check('tête peinte : déterministe (deux calculs, mêmes octets)', np.array_equal(t0_, FS.textures(el, dict(base), 0.)['+z']))
    cc = ca['casts']
    check('contrat : la tête peinte voyage vers VOXEL (palette, grilles, calques)', all('face_skin' in cc[a]['costume'] and len(cc[a]['costume']['face_skin']['grids']['front']) == 16 for a in ('angelica', 'hamilton', 'eliza')))
    c_off, _ = contract(*directed({'x': {'costume': {'preset': 'peggy', 'face_skin': False}}}))
    check('opt-in par personnage : "face_skin": false rend le visage du moteur (aucune tête peinte dans le contrat)', 'face_skin' not in c_off['casts']['x']['costume'])
    # ---------------------------------------------------------------- traversals measured on the emitted PS1 geometry
    for cid in ('angelica', 'eliza', 'dame_tartan', 'peggy'):
        n, bad = ps1_traversal(cid, poses_walk()); check(f'PS1 {cid} : marche (4 allures, cycle complet), aucun point de jambe hors de la jupe', bad == 0, f'{bad} / {n} points')
        n, bad = ps1_traversal(cid, poses_other()); check(f'PS1 {cid} : assis, accroupi, tour sur soi, aucun point de jambe hors de la jupe', bad == 0, f'{bad} / {n} points')
    for cid in ('hamilton', 'washington', 'homme_rouge_1'):
        n, bad = ps1_traversal(cid, poses_walk() + poses_other()); check(f'PS1 {cid} : basques, aucun point de jambe dans un panneau', bad == 0, f'{bad} / {n} points')
    # ---------------------------------------------------------------- the floor: a settling skirt never goes under it (seated, kneeling, on the floor)
    for cid in ('angelica', 'eliza'):
        worst = 0.
        for p in [sample(sit=1.), sample(kneel=1.), sample(kneel=.5), sample(sit_floor=1.)]:
            COS.PARTS = {}; COS.build(p, {'costume': cid}, None, {}, None, []); sk_ = COS.PARTS.get('skirt', []); COS.PARTS = None
            worst = min(worst, min(float(b.wlo[1]) for b in sk_))
        check(f'PS1 {cid} : assise, à genoux, par terre, la jupe se pose sans passer sous le plancher', worst > -.005, f'point le plus bas {worst * 100:.1f} cm')
    # ---------------------------------------------------------------- directed keys of 31/10/2026: side left, arms_wide, kneel, sit_floor (generic)
    from hstudio.acting.gestures import GESTURES
    s0 = rig.solve(dict(t=1., gestures=[('arm_up', 1., 1.)])); s1 = rig.solve(dict(t=1., gestures=[('arm_up', 1., 1.)], left=True))
    check('`side: left` : le geste passe au bras gauche (main gauche au-dessus de la tête), sans la clé rien ne change',
          s1.joints['haL'][1] > 1.7 and s1.joints['haR'][1] < 1.1 and s0.joints['haR'][1] > 1.7 and np.allclose(rig.solve(dict(t=1., gestures=[('arm_up', 1., 1.)])).joints['haR'], s0.joints['haR']))
    smp = dict(base, rig={'left': True}); cs_a = COS.spec_of({'costume': 'angelica'})
    check("`side: left` : l'objet tenu passe dans la main gauche (robe : flûte à gauche)", COS.held(cs_a, smp) == (None, 'flute') and COS.held(cs_a, base) == ('flute', None))
    from hstudio.engines.pixel3d import rigfig
    bx_r, sk_r = rigfig.build(dict(base, hold='flower', rig={'t': 1.}), {'outfit': 'shirt'}, np.zeros((24, 24, 4), np.uint8))
    bx_l, sk_l = rigfig.build(dict(base, hold='flower', rig={'t': 1., 'left': True}), {'outfit': 'shirt'}, np.zeros((24, 24, 4), np.uint8))
    near = lambda bx, hand: sum(1 for b in bx if b.inst is not None and float(np.linalg.norm(b.inst.piv - hand)) < 1e-4)
    check('`side: left` sans costume (PS1) : la fleur tenue suit la main gauche', near(bx_l, sk_l.joints['haL']) >= 2 and near(bx_r, sk_r.joints['haR']) >= 2)
    sw = rig.solve(dict(t=1., gestures=[('arms_wide', 1., 1.)])); sv = rig.solve(dict(t=1., gestures=[('arms_wide_up', 1., 1.)]))
    check("gestes `arms_wide` (bras tendus à l'horizontale) et `arms_wide_up` (en V)", 'arms_wide' in GESTURES and 'arms_wide_up' in GESTURES
          and all(abs(float(sw.joints[h][1]) - 1.40) < .08 and abs(float(sw.joints[h][0])) > .75 for h in ('haL', 'haR')) and all(float(sv.joints[h][1]) > 1.65 for h in ('haL', 'haR')))
    kn = rig.solve(dict(t=1., kneel=1.)); sf = rig.solve(dict(t=1., sit_floor=1.))
    check('`kneel` : bassin à hauteur de cuisse, genoux au sol ; `sit_floor` : bassin au ras du sol', abs(float(kn.joints['pelvis'][1]) - .43) < .03 and max(float(kn.joints['knL'][1]), float(kn.joints['knR'][1])) < .14
          and float(sf.joints['pelvis'][1]) < .2, f"bassin {kn.joints['pelvis'][1]:.2f} / {sf.joints['pelvis'][1]:.2f} m, genou {kn.joints['knL'][1]:.2f} m")
    epk, lk = directed({'kx': {'outfit': 'hoodie'}}); epk['shots'][0]['tracks']['kx'] = [{'t': 0, 'p': [0, 0, 0], 'yaw': PI, 'kneel': 0.}, {'t': 1., 'p': [0, 0, 0], 'yaw': PI, 'kneel': 1.}]
    ck, _ = contract(epk, lk)
    check('contrat : piste `poses` (à genoux) pour ce personnage seulement, absente des autres films', 'poses' in ck['stages'][0] and max(ck['stages'][0]['poses']['kx']['kneel']) == 1.0 and 'poses' not in c1['stages'][0])
    mx = max(int(cc['angelica']['costume']['colors']['lace'][i:i + 2], 16) for i in (1, 3, 5))
    check("dentelle mate : la couleur de dentelle envoyée au peintre est plafonnée (pas de néon sous une poursuite), la peau ne l'est pas",
          mx <= 210 and cc['eliza']['costume']['colors']['skin'] == '#eeccb8', f'max dentelle {mx}/255')
    # ---------------------------------------------------------------- wiring: presets, library, registry, docs, unknown values said in French
    ok = all(COS.spec_of({'costume': p}) is not None for p in COS.PRESETS)
    check(f'{len(COS.PRESETS)} préréglages résolus (rôles, 10 dames, hommes en bleu et en rouge)', ok and len(COS.ENSEMBLE_DAMES) == 10 and len(COS.ENSEMBLE_HOMMES) >= 8)
    COS.WARN.clear(); r = COS.spec_of({'costume': 'inconnu_xyz'})
    check('préréglage inconnu : ignoré ET dit en français (jamais remplacé en silence)', r is None and any('inconnu' in w for w in COS.WARN))
    COS.WARN.clear(); r = COS.spec_of({'costume': {'preset': 'peggy', 'hair': 'mohawk'}})
    check('coiffure inconnue : « short », dit en français', r is not None and r['hair'] == 'short' and COS.WARN)
    from hstudio.acting import cast as CA
    lib = {c['id']: c for c in CA.list_characters()}
    check('bibliothèque : chaque personnage du bal a sa fiche et se résout en costume', all(p in lib and COS.spec_of(lib[p]['look']) is not None for p in COS.PRINCIPAUX + COS.ENSEMBLE_DAMES + COS.ENSEMBLE_HOMMES))
    from hstudio.capabilities import registry
    caps = registry.build()
    check('registre des capacités : costumes, coiffures et accessoires, natifs PS1 et VOXEL', all(caps.get(f'costume:{p}', {}).get('styles') == {'ps1': 'native', 'voxel': 'native'} for p in COS.PRESETS) and 'hair:big_curls' in caps and 'item:flute' in caps)
    doc = (ROOT / 'docs' / 'FORMAT_EPISODE.md').read_text(encoding='utf-8')
    check('docs/FORMAT_EPISODE.md : clés et exemple à copier', all(k in doc for k in ('"costume"', 'big_curls', 'flute', 'stomacher', 'facings', 'veil')))
    # ---------------------------------------------------------------- VOXEL, measured in the painter (software browser)
    if voxel:
        castv = {'w_ang': {'costume': 'angelica'}, 'w_eli': {'costume': 'eliza'}, 'w_ham': {'costume': 'hamilton'}, 'w_tar': {'costume': 'dame_tartan'}}
        epw, lw = directed(castv, walk=True, dur=3.0)
        eps, ls_ = directed({'s_eli': {'costume': 'eliza'}, 's_ang': {'costume': 'angelica'}}, spin=True, dur=2.5)
        epz = copy.deepcopy(epw); epz['shots'][0]['tracks'] = {k: [{'t': 0, 'p': v[0]['p'], 'yaw': PI, 'sit': 1.0}] for k, v in epw['shots'][0]['tracks'].items()}
        env = dict(os.environ); A = Path(r'C:\Users\demo\Videos\moteur_voxel\node_modules')
        if not (ROOT / 'voxelgpu_js' / 'node_modules').exists() and A.exists(): env['NODE_PATH'] = str(A)
        epg = copy.deepcopy(epw); epg['shots'][0]['tracks'] = {k: [{'t': 0, 'p': v[0]['p'], 'yaw': PI, 'kneel': 0.}, {'t': 1.0, 'p': v[0]['p'], 'yaw': PI, 'kneel': 1.0}] for k, v in epw['shots'][0]['tracks'].items()}
        epf = copy.deepcopy(epw); epf['shots'][0]['tracks'] = {k: [{'t': 0, 'p': v[0]['p'], 'yaw': PI, 'sit_floor': 0.}, {'t': 1.0, 'p': v[0]['p'], 'yaw': PI, 'sit_floor': 1.0}] for k, v in epw['shots'][0]['tracks'].items()}
        for tag, (ep, ll, times) in {'marche': (epw, lw, [.4 + .1 * i for i in range(24)]), 'tour': (eps, ls_, [.2 * i for i in range(1, 12)]), 'assis': (epz, lw, [1.0, 2.0]),
                                     'à genoux': (epg, lw, [.5, 1.2, 2.0]), 'assis par terre': (epf, lw, [.5, 1.2, 2.0])}.items():
            c, _ = contract(ep, ll); td = Path(tempfile.mkdtemp(prefix='ckcost_')); from hstudio.voxelgpu import contract as Cn; Cn.save(c, td / 'c.json')
            r = subprocess.run(['node', str(ROOT / 'voxelgpu_js' / 'costume_probe.js'), str(td / 'c.json'), ','.join(f'{t:.2f}' for t in times), str(td / 'm.json')], env=env, cwd=str(ROOT / 'voxelgpu_js'), capture_output=True, text=True, timeout=900)
            if r.returncode or not (td / 'm.json').exists(): check(f'VOXEL {tag} : mesure dans le peintre', False, r.stderr[-300:] + r.stdout[-300:]); continue
            m = json.loads((td / 'm.json').read_text(encoding='utf-8'))
            pts = sum(v['points'] for f in m for v in f['chars'].values()); out = sum(v['outside'] for f in m for v in f['chars'].values()); tails = sum(v['tail_hits'] for f in m for v in f['chars'].values())
            worst = max([v['worst_cm'] for f in m for v in f['chars'].values()] + [0])
            fl = [v['floor_cm'] for f in m for v in f['chars'].values() if v.get('floor_cm') is not None]
            if fl: check(f'VOXEL {tag} : la jupe ne passe jamais sous le plancher', min(fl) > -0.5, f'ourlet le plus bas {min(fl):.1f} cm au-dessus du sol')
            check(f'VOXEL {tag} : aucun point de jambe hors de la jupe ni dans une basque (mesuré dans le peintre, {len(times)} instants)', out == 0 and tails == 0, f'{out} hors jupe (pire {worst:.1f} cm), {tails} dans une basque, sur {pts} points')
    n_ok = sum(RES); print(f'\n{n_ok} / {len(RES)} vérifications OK'); sys.exit(0 if n_ok == len(RES) else 1)


if __name__ == '__main__':
    main()
