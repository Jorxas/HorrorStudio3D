"""Les lieux de PIXEL 3D (V3) dans le peintre VOXEL : pièces, maisons, rues, forêts, plages... construits par PIXEL 3D, peints par VOXEL.

`sets.make_set(nom, spec)` est le point d'entrée de PIXEL 3D : il rend un lieu (`RoomSet`) dont `.base.boxes` sont toutes les boîtes (murs, sol, plafond, portes,
fenêtres, meubles, arbres, bâtiments), `.light_defs` ses lumières, `.anchors` ses points de passage, `.room_rects` ses sols, `.base.floor_fn` son sol procédural et
`.base.sky_fn` son ciel dessiné. On le prend tel quel (38 lieux prêts, les pièces décrites par `rooms`/`props`/`blocks`, les lieux composés) et on le traduit :

  * géométrie : toutes les boîtes passent par `b_props.boxes_to_bset` (même demi-tour, même agrandissement que les décors seuls) -> accessoires `bset` posés sur le monde `plateau`
  * sols : `floor_fn` est ÉCHANTILLONNÉ sur une grille (parquet, damier, carrelage, tapis, sable, neige, eau, chemins, étangs) et posé en plaque texturée ; seul le reflet est perdu
  * ciel : `sky_fn` (dégradé, soleil, nuages, étoiles, lune, horizon de montagnes ou de ville) est échantillonné en dôme texturé qui suit la caméra ; le soleil règle la lumière du jour
  * météo : `weather` du lieu (ou du plan) -> particules de VOXEL (pluie, neige, braises, poussière, étincelles) ; approximations déclarées dans `BSet.limits`
  * lumières : celles du lieu (le peintre garde les 4 plus proches du regard) ; les lumières scintillantes (`flick`) deviennent des tables d'intensité dans le temps du film
  * portes : le battant d'une porte fermée est un élément animé (pivot à la charnière) dont l'angle, image par image, vient de la régie (l'acteur ouvre la porte)
  * la régie : `BSetWorld` prête à la régie de VOXEL les ancres, obstacles (murs, meubles), sièges, portes et limites de PIXEL 3D, dans le même repère (demi-tour + agrandissement) ;
    la caméra reste dans la pièce, à distance des murs, avec un champ élargi (`fov_boost`)

Repère : le demi-tour fait de VOXEL un monde où un personnage tourné vers la caméra regarde vers +z (`"facing": "+z"`), comme dans tous les mondes de VOXEL.
Limites restantes (listées dans `BSet.limits`, jamais passées sous silence) : reflets du sol, matières procédurales des murs, éclairs, fenêtres animées.
"""
import copy, json, math
import numpy as np
from ..acting.timeline import World
from . import b_props as BP

K = BP.PROP_SCALE
_SKY_HORIZON = {'day': (.70, .82, .96), 'sunset': (1., .52, .28), 'dawn': (.98, .74, .64), 'night': (.04, .06, .13), 'overcast': (.72, .74, .76), 'storm': (.26, .28, .31)}
_CACHE = {}
LIGHT_GAIN_INDOOR = 3.4


def _hex(c): return BP._hex(c)


def _copy_box(b):
    n = copy.copy(b); n.lo = np.array(b.lo, np.float32); n.hi = np.array(b.hi, np.float32)
    if b.inst is not None: n.inst = copy.copy(b.inst)
    if getattr(b, 'wlo', None) is not None: n.wlo = np.array(b.wlo, np.float32); n.whi = np.array(b.whi, np.float32)
    return n


def _png(a):
    """tableau (h, w, 3|4) de flottants 0..1 ou d'octets -> (w, h, base64 RGBA, rangées de bas en haut pour une DataTexture)"""
    import base64
    a = np.asarray(a)
    if a.dtype != np.uint8: a = (np.clip(a, 0, 1) * 255 + .5).astype(np.uint8)
    if a.shape[2] == 3: a = np.concatenate([a, np.full(a.shape[:2] + (1,), 255, np.uint8)], 2)
    a = np.ascontiguousarray(a[::-1])
    return int(a.shape[1]), int(a.shape[0]), base64.b64encode(a.tobytes()).decode('ascii')


class BSetWorld(World):
    """la régie de VOXEL vue sur un lieu de PIXEL 3D : mêmes ancres, obstacles, sièges, portes, limites, au demi-tour et à l'agrandissement près"""
    camera_heading = 0.             # un personnage tourné vers la caméra regarde vers +z, comme dans tous les mondes de VOXEL

    def __init__(self, sw, indoor):
        self.sw = sw; self.indoor = indoor
        a = {n: (-K * p[0], -K * p[1]) for n, p in sw.st.anchors.items()}
        x0, z0, x1, z1 = sw.bounds(); b = (-K * x1, -K * z1, -K * x0, -K * z0)
        super().__init__(anchors=a, bounds=b)
        self._obs = [(-K * o[2], -K * o[3], -K * o[0], -K * o[1]) for o in sw.obstacles()]
        self.rect = b; self.has_levels = sw.has_levels
        self.fov_boost = 1.22 if indoor else 1.0          # une pièce est étroite : le champ plus large garde le personnage entier sans reculer dans le mur
        spec = getattr(sw.st, 'spec', {}) or {}; rooms = spec.get('rooms') or []
        if indoor and rooms:                 # l'intérieur réel des pièces (la marge de 0,5 m des limites de déplacement est DEHORS, derrière le mur)
            xs0 = [r.get('origin', [0, 0])[0] - r['size'][0] / 2 for r in rooms]; xs1 = [r.get('origin', [0, 0])[0] + r['size'][0] / 2 for r in rooms]
            zs0 = [r.get('origin', [0, 0])[1] for r in rooms]; zs1 = [r.get('origin', [0, 0])[1] + r['size'][1] for r in rooms]
            self.inner = (-K * max(xs1), -K * max(zs1), -K * min(xs0), -K * min(zs0)); self.height = max(float(r.get('height', spec.get('height', 2.6))) for r in rooms) * K
        else: self.inner = None; self.height = 2.5 * K
        self.doors = {}
        for did, dr in (getattr(sw, 'doors', {}) or {}).items(): self.doors[did] = dr

    def anchor(self, name):
        p = self.sw.anchor(name)
        return None if p is None else (-K * p[0], -K * p[1])

    def obstacles(self): return self._obs

    def door(self, name):
        dr = self.doors.get(name)
        if dr is None: return None
        hx, hz = dr['hinge']; fx, fz = dr['handle_front']; hd = dr['handle']
        def handle(a): x, y, z = hd(a); return (-K * x, y * K, -K * z)
        return dict(dr, hinge=(-K * hx, -K * hz), width=dr['width'] * K, handle=handle, handle_front=(-K * fx, -K * fz), facing=dr['facing'] + math.pi)

    def seat(self, name):
        s = self.sw.seat(name)
        return None if s is None else (-K * s[0], -K * s[1], s[2] + math.pi, s[3] * K)

    def item(self, name):
        it = self.sw.item(name)
        return None if it is None else (-K * it[0], it[1] * K, -K * it[2])

    def ground_y(self, x, z): return self.sw.ground_y(-x / K, -z / K)

    def camera_box(self):
        if self.inner:
            x0, z0, x1, z1 = self.inner; m = .5                     # à distance des murs : un mur à 30 cm de l'objectif remplit l'image
            return (x0 + m, z0 + m, x1 - m, z1 - m, .3, self.height - .3)
        x0, z0, x1, z1 = self.rect
        return (x0 - 12., z0 - 12., x1 + 12., z1 + 14., .25, 14.)

    def blocked_for_camera(self, p):
        bx0, bz0, bx1, bz1, y0, y1 = self.camera_box()
        if not (bx0 <= p[0] <= bx1 and bz0 <= p[2] <= bz1 and y0 <= p[1] <= y1): return True
        m = .22 if self.indoor else 0.
        return any(o[0] - m <= p[0] <= o[2] + m and o[1] - m <= p[2] <= o[3] + m for o in self._obs) if self.indoor else False


class BSet:
    def __init__(self, name, spec, hide_groups=()):
        from ..engines.pixel3d import sets as S, world as W, stage as ST
        self.name = name; self.spec = spec; self.limits = []
        self.st = S.make_set(name, spec)
        if getattr(self.st, 'base', None) is None: self.st.build()
        sc = self.st.base; sp = getattr(self.st, 'spec', spec) or spec; self.sp = sp
        self.indoor = not sp.get('outdoor', False) and bool(sp.get('rooms'))
        self.sw = ST.SetWorld(self.st, None, None, sp); self.world = BSetWorld(self.sw, self.indoor)
        stats = {}
        door_boxes = {di['box'] for di in (getattr(self.st, 'door_info', {}) or {}).values()}                  # les battants de porte sont animés : ils ne font pas partie du décor fixe
        nat_hide, nat_items = (self.st.voxel_native() if hasattr(self.st, 'voxel_native') else (set(), []))        # éléments que VOXEL fait lui-même (arbres, voiture...) au lieu de repeindre ceux de PS1
        for gid in hide_groups: nat_hide = set(nat_hide) | set((getattr(self.st, 'groups', {}) or {}).get(gid, []))          # V3 : un élément de lieu composé que VOXEL refait lui-même (la tour qui s'effondre : b_fx.py)
        self.floor_y = K * float(getattr(sc, 'floor_y', 0.) or 0.)                 # V3 : lieu à niveaux (toits, ravin) : le sol est à `ground_y`, pas à 0
        from . import b_objets as BO
        od_hide, od_nat = BO.natives(sc.boxes)                                     # objets détaillés (marqueurs de pixel3d/objets.py) : VOXEL les repeint en version native ; rien sans objet détaillé
        if od_hide: nat_hide = set(nat_hide) | od_hide
        self.props = [BP.boxes_to_bset([_copy_box(b) for i, b in enumerate(sc.boxes) if i not in door_boxes and i not in nat_hide], 0, 0., 0., 0., K, stats)]
        if od_nat: self.props.append(BP.boxes_to_bset(od_nat, 0, 0., 0., 0., K, stats))
        if nat_items:
            vit = [dict(it, at=[-K * it['at'][0], -K * it['at'][-1]]) for it in nat_items]
            np_, nl_ = BP.convert_props(vit); self.props += np_
        for nb in (self.st.voxel_bsets() if hasattr(self.st, 'voxel_bsets') else []): self.props.append(nb)      # lieux dont VOXEL construit lui-même les volumes (voxelgpu/b_quartiers.py) : accessoires déjà au repère de VOXEL
        rects = getattr(self.st, 'room_rects', []) or []
        floor = self._floor(sc, rects, stats)
        if floor: self.props.append(floor)
        sky = self._sky(sc)
        if sky: self.props.append(sky)
        if spec.get('type') == 'composed':                                    # V3 : le dessus des falaises, en sable et terre à grain de cubes (b_fx.py)
            from . import b_fx as _BX
            self.props += _BX.rock_tops(spec)
        self.light_defs = list(getattr(self.st, 'light_defs', []) or [])
        gain = LIGHT_GAIN_INDOOR if self.indoor else 2.2
        self.lights = [(BP.light_to_voxel(pos, col, pw, rad, gain=gain), fl, pos) for (pos, col, pw, rad, fl) in self.light_defs]
        self.doors = self._doors()
        if stats.get('textures_lost'): self.limits.append(f"{stats['textures_lost']} image(s) de face non portée(s) (repère tourné)")
        self.limits.append('sols : reflets (flaques, parquet ciré) non portés ; matières procédurales des murs : couleur seule')
        if sp.get('weather') and sp.get('weather') != 'none': self.limits.append(f"météo « {sp['weather']} » : approximation par les particules de VOXEL")
        gk = sp.get('ground', 'asphalt' if sp.get('outdoor') else 'concrete')
        g = S.FLOORS.get(gk) or W.GROUNDS.get(gk) or (.3, .3, .3)
        skyname = sp.get('sky') or ('night' if sp.get('outdoor') else None)
        ambient = np.asarray(getattr(sc, 'ambient', (.1, .1, .1)), float); fog = np.asarray(getattr(sc, 'fog', (.05, .05, .06)), float)
        sk = S.sky_of(sp) if sp.get('outdoor') else None
        if sp.get('outdoor') and skyname in _SKY_HORIZON: bg = _SKY_HORIZON[skyname]; day = skyname in ('day', 'overcast', 'dawn', 'sunset')
        else: bg = tuple(fog); day = False
        fogd = float(getattr(sc, 'fogk', .02)) * (.35 if self.indoor else .12)                       # la brume de PIXEL 3D est un coefficient de lancer de rayons, pas une densité d'exponentielle
        self.env = dict(floor=_hex(g), bg=_hex(bg), fog_col=_hex(bg), fog=round(min(.03, fogd), 4),
                        ambient=round(float(1.0 + 6. * ambient.mean()) if not day else 1.45, 3), key=1.5 if day else (.45 if self.indoor else .6),
                        hemi_sky=_hex(np.clip(ambient / max(ambient.max(), 1e-3) * .6 + .35, 0, 1)), exposure=1.18 if self.indoor else 1.05)
        if sk:                                                                                          # le soleil (ou la lune) de PIXEL 3D règle la clé, dans le repère de VOXEL
            sx, sy, sz = (float(v) for v in sk['sun']); n = math.sqrt(sx * sx + sy * sy + sz * sz) or 1.
            self.env.update(key_dir=[round(-sx / n, 3), round(sy / n, 3), round(-sz / n, 3)], key_col=_hex(sk['sun_col']), key=round(max(.35, float(sk['power'])), 2),
                            hemi_sky=_hex(np.clip(np.asarray(sk['ambient'], float) * 2.2 + .25, 0, 1)))
        if sp.get('weather') and sp['weather'] != 'none': self.env['weather'] = sp['weather']
        if self.floor_y: self.env['floor_y'] = round(self.floor_y, 3)
        self.env.update(getattr(self.st, 'voxel_env', None) or {})                                  # réglages propres au lieu (théâtre : sol hors scène noir) ; absents ailleurs

    # ---- sol : floor_fn échantillonné
    def _floor(self, sc, rects, stats):
        fn = getattr(sc, 'floor_fn', None)
        if fn is None or getattr(self.st, 'voxel_floor', True) is False: return None          # `voxel_floor = False` : le lieu pose son propre plancher en volumes (théâtre)
        try:
            if self.indoor and rects: x0 = min(r[0] for r in rects); z0 = min(r[1] for r in rects); x1 = max(r[2] for r in rects); z1 = max(r[3] for r in rects); ppm = 12.
            else:
                x0, z0, x1, z1 = self.sw.bounds(); ppm = 4.
                cx, cz = (x0 + x1) / 2, (z0 + z1) / 2; hw = min((x1 - x0) / 2, 40.); hd = min((z1 - z0) / 2, 50.); x0, x1, z0, z1 = cx - hw, cx + hw, cz - hd, cz + hd
            vx0, vx1, vz0, vz1 = -K * x1, -K * x0, -K * z1, -K * z0; w = vx1 - vx0; d = vz1 - vz0
            tw = int(min(1024, max(8, round(w * ppm)))); th = int(min(1024, max(8, round(d * ppm)))); ss = 2
            xs = vx0 + (np.arange(tw * ss) + .5) / (tw * ss) * w; zs = vz1 - (np.arange(th * ss) + .5) / (th * ss) * d          # rangée 0 = z le plus grand (bas de la texture)
            X, Z = np.meshgrid(xs, zs); P = np.stack([-X / K, np.zeros_like(X), -Z / K], -1).reshape(-1, 3).astype(np.float32)
            alb, _ = fn(P); alb = np.asarray(alb, np.float32).reshape(th * ss, tw * ss, 3)
            alb = alb.reshape(th, ss, tw, ss, 3).mean((1, 3))
            tw_, th_, b64 = _png(alb[::-1])                                         # _png remet les rangées de bas en haut : on lui donne l'image dans l'ordre « haut = z le plus petit »
            return dict(type='bset', boxes=[], planes=[dict(x=round((vx0 + vx1) / 2, 3), y=round(self.floor_y + .03, 3), z=round((vz0 + vz1) / 2, 3), w=round(w, 3), d=round(d, 3), tw=tw_, th=th_, rgba=b64)])
        except Exception as e:
            self.limits.append(f'sol procédural non échantillonné ({type(e).__name__}) : couleur moyenne'); return None

    # ---- ciel : sky_fn échantillonné en dôme
    def _sky(self, sc):
        fn = getattr(sc, 'sky_fn', None)
        if fn is None: return None
        try:
            TW, TH = 768, 192
            phi = (np.arange(TW) + .5) / TW * 2 * math.pi; th = (np.arange(TH) + .5) / TH * math.pi            # th = 0 en haut
            PH, TH_ = np.meshgrid(phi, th)
            dx = -np.cos(PH) * np.sin(TH_); dy = np.cos(TH_); dz = np.sin(PH) * np.sin(TH_)                     # la sphère de three.js ; puis le repère de PIXEL 3D (demi-tour)
            D = np.stack([-dx, dy, -dz], -1).reshape(-1, 3).astype(np.float32)
            col = np.asarray(fn(D), np.float32).reshape(TH, TW, 3)
            tw, thh, b64 = _png(col)                                                                  # _png inverse les rangées : texture row 0 = bas
            return dict(type='bdome', tw=tw, th=thh, rgba=b64)
        except Exception as e:
            self.limits.append(f'ciel dessiné non échantillonné ({type(e).__name__}) : couleur unie'); return None

    # ---- portes : battants animés
    def _doors(self):
        out = {}
        for did, dr in (self.world.doors or {}).items():
            d = self.world.door(did)
            out[did] = dict(hinge=[round(d['hinge'][0], 4), round(d['hinge'][1], 4)], w=round(d['width'], 4), h=round(2.08 * K, 3), th=round(.06 * K, 3), color=_hex([c / 255. for c in dr['color']]), fn=dr['yaw'])
        return out

    def stage_parts(self, t0=0., t1=0.):
        """les accessoires, lumières (avec leur scintillement dans le temps du film t0..t1) et réglages de lumière d'un plan dans ce lieu"""
        lights = []
        from ..engines.pixel3d.sets import flicker_hash
        for lt, fl, pos in self.lights:
            l = dict(lt)
            if fl:
                hz = 20. if fl == 'soft' else 10.; keys = []; px, pz = pos[0], pos[2]
                for j in range(int(math.ceil((t1 - t0) * hz)) + 2):
                    t = t0 + j / hz
                    k = (.84 + .16 * math.sin(t * 9.3 + px * 3.7) * math.sin(t * 5.1 + pz * 2.3)) if fl == 'soft' else (.2 if flicker_hash(t, 10, int(px * 10)) > .6 else 1.)
                    keys.append([round(t, 3), round(l['i'] * k, 3)])
                l['i'] = keys
            lights.append(l)
        return dict(world='plateau', props=copy.deepcopy(self.props), lights=lights, env=dict(self.env))

    def door_tracks(self, sa, frames, j0, fps, lead=0.):
        """{id: {hinge, w, h, th, color, yaw: [angle du battant par image]}} : l'angle vient de la régie (l'acteur ouvre la porte), +demi-tour pour le repère de VOXEL"""
        out = {}
        for did, d in self.doors.items():
            ang = (lambda tt: sa.door_angle(did, tt)) if hasattr(sa, 'door_angle') else (lambda tt: 0.)
            out[did] = {k: v for k, v in d.items() if k != 'fn'}
            out[did]['yaw'] = [round(d['fn'](ang(j / fps)) + math.pi, 4) for j in range(j0, j0 + frames)]
        return out


def get(name, spec, hide_groups=()):
    """un lieu converti, gardé en mémoire (même nom et même spec = même objet) ; `hide_groups` : éléments d'un lieu composé repeints à part (effondrement)"""
    key = name + '|' + json.dumps(spec, sort_keys=True, default=str) + ('|' + ','.join(sorted(hide_groups)) if hide_groups else '')
    from ..engines.pixel3d import quartiers as QT                  # la clé d'épisode `diversite` change les lieux construits : même nom + même spec + autre clé = autre lieu
    key += QT.signature()
    from ..engines.pixel3d import objets as OD                     # la clé `objets` change aussi les lieux construits (les noms d'avant deviennent détaillés)
    key += OD.signature()
    if key not in _CACHE: _CACHE[key] = BSet(name, spec, hide_groups)
    return _CACHE[key]
