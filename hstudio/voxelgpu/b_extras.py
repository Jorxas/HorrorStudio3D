"""Figurants animés pour VOXEL : des personnages de fond qui vivent la scène (marchent, s'arrêtent, discutent, s'assoient, réagissent, fuient), sans jamais traverser un décor, un autre
corps ni un personnage principal, et sans jamais être cadrés à la place des personnages principaux.

PIXEL 3D avait `acting/background.py` (3 à 5 figurants, voies mesurées à la main pour un seul lieu). Ici, tout est CALCULÉ sur le monde du plan : le rectangle marchable, les obstacles réels
(`world.obstacles()`, qui contiennent les décors du plan grâce à `b_space.ObsWorld`), les sièges, la position des personnages principaux dans le temps. Le module ne dessine rien et n'invente
aucun verbe : il écrit, pour chaque figurant, des `actors` et des `actions` de la régie existante (`walk_to`, `run_to`, `wait`, `look_around`, `turn_to`, `react`, `exit`, `sit`...) et des entrées
`speech` (la bouche qui parle), exactement comme le ferait un auteur d'épisode. L'épisode reste la seule source de vérité.

CLÉ D'ÉPISODE OU DE PLAN (opt-in : sans elle, rien ne change d'un octet) :

  "extras": {
    "count": 8,                         # nombre de figurants (plafond MAX = 16 ; au-delà : message et plafonnement)
    "troupe": "auto",                   # "auto" (variée et plausible pour le lieu) | liste de noms d'identités, de `b_look`, de `b_preset`, ou de casts
    "seed": 3,                          # l'unique source de hasard : même épisode = même contrat
    "keep_clear": 3.0,                  # mètres gardés entre un figurant et tout personnage principal (jamais cadré à leur place, jamais dans leur dialogue)
    "mix": {"walk": .5, "idle": .2, "talk_pairs": .2, "sit": .1},
    "lanes": "auto",                    # ou une liste de lignes [[x, z], ...] que les marcheurs suivent
    "beats": [ {"shot": 2, "do": "flee", "from": "monstre", "at": 1.1},      # "from" : un point [x, z] ou l'id d'un personnage
               {"shot": 0, "do": "life"} ],                                  # do : life | flee | freeze | stare | back  (+ "who", "frac", "radius")
    "spacing": true                     # défaut : vrai (voir plus bas)
  }

GARANTIES, toutes mesurées par `tools/check_voxelgpu.py` : jamais dans un obstacle, jamais à moins de `keep_clear` d'un principal (sauf poussée de la séparation du chantier 6, au plus .3 m),
jamais à travers un autre corps (la séparation de `b_space.py` est forcée quand il y a des figurants), entrées et sorties par les bords, déterminisme, exclusion de la caméra (le cast porte
`"extra": true` : `director.CameraPlan` ne les prend jamais pour sujets et `ShotActing.speech` ne les prend jamais pour interlocuteurs d'un principal).
"""
import copy, math, random, warnings
import numpy as np
from ..acting.timeline import Grid, SPEEDS
from . import b_space as SP

MAX = 16
STEP = .4                                           # pas de la grille de planification (m)
BODY_CLEAR = .45                                    # marge autour des obstacles pour le passage d'un corps
KEY = 'extras'

# ------------------------------------------------------------------------------------------------------------------ identités
# Un figurant est un cast ordinaire de `b_chars.py` (tenue, chapeau, coiffure, objet en main) : il a le corps, le visage et la lumière des personnages principaux. La silhouette porte l'identité.
IDENT = {
    'passante':   dict(outfit='coat', hat='beanie', hat_color=[182, 74, 62], hair_style='ponytail', hair=[54, 38, 30], hood=[92, 80, 102], jeans=[46, 44, 54], skin=[226, 188, 154], hold='phone'),
    'flaneur':    dict(outfit='hoodie', hat='cap', hat_color=[40, 46, 60], hair_style='short', hair=[28, 22, 18], hood=[62, 122, 104], jeans=[58, 60, 70], skin=[172, 116, 84]),
    'vendeur':    dict(outfit='apron', hat='none', hair_style='bald', hood=[232, 228, 218], jeans=[70, 66, 62], skin=[206, 150, 112], scale=1.04),
    'mamie':      dict(outfit='dress', hat='hood', hat_color=[108, 66, 92], hair_style='bun', hair=[220, 220, 224], glasses=True, hood=[146, 94, 124], skin=[224, 196, 170], scale=.94, hold='bag'),
    'ado':        dict(outfit='tshirt', hat='none', hair_style='spiky', hair=[220, 180, 70], hood=[220, 70, 60], jeans=[44, 52, 92], skin=[216, 172, 136], backpack=True, scale=.9, hold='phone'),
    'joggeur':    dict(outfit='tshirt', hat='cap', hat_color=[220, 220, 224], hair_style='short', hair=[88, 62, 40], hood=[40, 150, 200], jeans=[30, 30, 36], skin=[200, 150, 116]),
    'homme_affaires': dict(outfit='suit', hat='none', hair_style='short', hair=[40, 36, 34], hood=[40, 44, 58], jeans=[40, 44, 58], skin=[222, 178, 140], tie=[160, 40, 44], hold='newspaper'),
    'ouvrier':    dict(outfit='uniform', hat='helmet', hat_color=[230, 190, 40], hood=[210, 120, 40], jeans=[60, 66, 84], skin=[186, 130, 96], scale=1.03),
    'touriste':   dict(outfit='shirt', hat='cap', hat_color=[200, 60, 60], hair_style='short', hair=[150, 110, 60], hood=[240, 226, 180], jeans=[150, 130, 96], skin=[232, 188, 150], backpack=True, hold='camera'),
    'enfant':     dict(outfit='hoodie', hat='beanie', hat_color=[240, 190, 40], hair_style='short', hair=[110, 70, 40], hood=[60, 120, 200], jeans=[60, 70, 110], skin=[230, 184, 146], scale=.66, hold='ball'),
    'parent':     dict(outfit='coat', hat='none', hair_style='long', hair=[90, 56, 34], hood=[120, 56, 52], jeans=[50, 50, 60], skin=[226, 180, 142], hold='bag'),
    'livreur':    dict(outfit='hoodie', hat='cap', hat_color=[220, 120, 30], hair_style='short', hair=[30, 26, 24], hood=[230, 150, 40], jeans=[40, 44, 54], skin=[190, 136, 100], backpack=True),
    'policier':   dict(outfit='uniform', hat='police', hood=[30, 40, 90], jeans=[26, 32, 70], hair_style='short', hair=[40, 30, 24], skin=[206, 160, 124]),
    'etudiante':  dict(outfit='coat', hat='none', hair_style='curly', hair=[60, 40, 30], hood=[90, 120, 90], jeans=[50, 56, 76], skin=[190, 136, 106], backpack=True, hold='book'),
    'serveur':    dict(outfit='apron', hat='none', hair_style='short', hair=[50, 36, 28], hood=[236, 232, 222], jeans=[30, 30, 36], skin=[214, 168, 132], hold='cup'),
    'client':     dict(outfit='shirt', hat='none', hair_style='short', hair=[70, 50, 36], hood=[110, 90, 70], jeans=[56, 60, 76], skin=[224, 178, 140], hold='cup'),
    'docteur':    dict(outfit='lab_coat', hat='none', hair_style='short', hair=[48, 44, 40], hood=[236, 238, 240], jeans=[44, 56, 78], skin=[216, 170, 134]),
    'infirmiere': dict(outfit='uniform', hat='none', hair_style='bun', hair=[56, 40, 30], hood=[120, 190, 206], jeans=[120, 190, 206], skin=[226, 184, 150]),
    'eleve':      dict(outfit='hoodie', hat='none', hair_style='spiky', hair=[40, 30, 24], hood=[60, 90, 150], jeans=[50, 56, 76], skin=[210, 160, 124], scale=.86, backpack=True),
    'promeneur':  dict(outfit='coat', hat='tophat', hat_color=[40, 36, 40], hair_style='short', hair=[160, 160, 164], hood=[70, 64, 60], jeans=[50, 46, 44], skin=[226, 186, 150], hold='umbrella'),
}
TROUPE = {                                         # troupes « auto » par genre de lieu : les premiers noms sont les plus probables
    'street':   ['passante', 'flaneur', 'vendeur', 'mamie', 'ado', 'homme_affaires', 'ouvrier', 'livreur', 'touriste', 'etudiante', 'parent', 'enfant', 'policier', 'joggeur'],
    'park':     ['joggeur', 'parent', 'enfant', 'mamie', 'promeneur', 'ado', 'touriste', 'flaneur', 'etudiante', 'enfant'],
    'nature':   ['touriste', 'promeneur', 'joggeur', 'flaneur', 'ado'],
    'cafe':     ['serveur', 'client', 'etudiante', 'client', 'mamie', 'homme_affaires'],
    'school':   ['eleve', 'eleve', 'eleve', 'etudiante', 'eleve', 'serveur'],
    'hospital': ['infirmiere', 'docteur', 'client', 'mamie', 'infirmiere'],
    'interior': ['client', 'mamie', 'etudiante', 'homme_affaires', 'ado', 'parent'],
}
NIGHT = {'enfant', 'joggeur', 'touriste', 'eleve'}  # peu probables la nuit


def kind_of(wname, tags, set_name, indoor):
    n = (set_name or '').lower()
    if indoor:
        return 'cafe' if 'cafe' in n else 'school' if ('class' in n or 'school' in n) else 'hospital' if ('hospital' in n or 'lab' in n) else 'interior'
    if any(w in n for w in ('park', 'garden', 'campsite', 'lake', 'beach', 'island')): return 'park'
    if any(w in n for w in ('forest', 'mountain', 'desert', 'countryside', 'cave', 'volcano')): return 'nature'
    if wname == 'parc' or 'nature' in (tags or ()) and 'urban' not in (tags or ()): return 'park'
    return 'street'


def _rng(*key): return random.Random('|'.join(str(k) for k in key))


def _pick(seq, rng, n):
    """n identités tirées dans `seq` (les premières sont les plus probables), sans répétition tant que la liste n'est pas épuisée"""
    out = []; pool = list(seq)
    for _ in range(n):
        if not pool: pool = list(seq)
        out.append(pool.pop(int(rng.random() * min(len(pool), 4))))
    return out


def cast_of(item, rng, i, scale_jitter=.04):
    """un élément de `troupe` -> un cast de `b_chars` marqué `extra` (taille et cheveux variés par la graine)"""
    if isinstance(item, dict): d = copy.deepcopy(item)
    elif isinstance(item, str) and item in IDENT: d = dict(preset='npc', variant=i % 4, **copy.deepcopy(IDENT[item]))
    elif isinstance(item, str) and '/' in item: d = dict(b_look=item)
    elif isinstance(item, str): d = dict(b_preset=item)
    else: raise ValueError(f'figurant inconnu : {item!r} (identités : {", ".join(IDENT)})')
    base = float(d.get('scale', 1.)); d['scale'] = round(base * (1. + (rng.random() - .5) * 2 * scale_jitter), 3)
    d['extra'] = True
    return d


# ------------------------------------------------------------------------------------------------------------------ le monde de planification
class Area:
    """grille de planification : obstacles réels du monde + hors du rectangle marchable + disques autour des personnages principaux (`keep_clear`)"""

    def __init__(self, world, zones, keep, leads_clear):
        self.g = Grid(world, radius=BODY_CLEAR, cell=STEP); g = self.g
        xs = g.x0 + np.arange(g.nx) * g.c; zs = g.z0 + np.arange(g.nz) * g.c; self.xs, self.zs = xs, zs
        rect = getattr(world, 'rect', None)
        if rect is None: b = world.bounds(); rect = (b[0] + 1., b[1] + 1., b[2] - 1., b[3] - 1.)
        self.rect = tuple(float(v) for v in rect); x0, z0, x1, z1 = self.rect
        inside = ((xs >= x0 + .5) & (xs <= x1 - .5))[:, None] & ((zs >= z0 + .5) & (zs <= z1 - .5))[None, :]
        g.block |= ~inside
        self.keep = keep; self.zones = list(zones)
        for (x, z, r) in zones:                                          # personnages principaux : disque de `keep_clear` autour de chaque position échantillonnée
            g.block |= ((xs[:, None] - x) ** 2 + (zs[None, :] - z) ** 2) < (r * keep) ** 2
        self.leads_clear = leads_clear; self.view = None; self.centre = None

    def free(self, x, z):
        i, j = self.g.cell(x, z)
        if not self.g.free(i, j): return False
        px, pz = self.g.pos(i, j)
        return abs(px - x) <= self.g.c and abs(pz - z) <= self.g.c

    def spot(self, rng, avoid=(), behind=True, gap=1.3, tries=100, rmin=3.5, rmax=11.):
        """un endroit libre où se tenir : DANS LE CHAMP DE LA CAMÉRA (estimée sur les principaux), derrière eux (ou parfois devant) ; sans caméra connue : autour du centre de la scène"""
        v = self.view
        if v is None: return self.sample(rng, near=self.centre, rmin=rmin, rmax=rmax, avoid=avoid, gap=gap, behind=True if behind else None) if self.centre else self.sample(rng, avoid=avoid, gap=gap)
        x0, z0, x1, z1 = self.rect
        for _ in range(tries):
            back = behind if behind is not None else True
            if back and rng.random() < .75 or v['d'] < 5.5: r = v['d'] + 2.0 + rng.random() * 8.5
            else: r = 2.8 + rng.random() * max(.5, v['d'] - 4.)
            a = v['dir'] + (rng.random() * 2 - 1) * v['half'] * .85; p = (v['pos'][0] + math.cos(a) * r, v['pos'][1] + math.sin(a) * r)
            if not (x0 + 1. <= p[0] <= x1 - 1. and z0 + 1. <= p[1] <= z1 - 1.): continue
            if self.free(*p) and all(math.hypot(p[0] - q[0], p[1] - q[1]) >= gap for q in avoid): return p
        return self.sample(rng, near=self.centre, rmin=rmin, rmax=rmax, avoid=avoid, gap=gap) if self.centre else None

    def clear(self, p, k=1.):
        """vrai si p est hors des disques `keep_clear` des personnages principaux"""
        return all(math.hypot(p[0] - x, p[1] - z) >= r * self.keep * k for (x, z, r) in self.zones)

    def route(self, a, b):
        """chemin libre de a à b (liste de points) ou None"""
        if not (self.free(*a) and self.free(*b)):
            a = self.g.nearest_free(*a) if not self.free(*a) else a; b = self.g.nearest_free(*b) if not self.free(*b) else b
            if not (self.free(*a) and self.free(*b)): return None
        pts = self.g.path(a, b)
        if len(pts) < 2: return None
        if any(not self.g.line_free(pts[i], pts[i + 1]) for i in range(len(pts) - 1)): return None
        return [tuple(map(float, p)) for p in pts]

    def sample(self, rng, near=None, rmin=0., rmax=1e9, tries=80, avoid=(), gap=1.3, behind=None):
        """un point libre au hasard (autour de `near` entre rmin et rmax), à `gap` des points `avoid`"""
        x0, z0, x1, z1 = self.rect
        for _ in range(tries):
            if near is None: p = (x0 + 1. + rng.random() * (x1 - x0 - 2.), z0 + 1. + rng.random() * (z1 - z0 - 2.))
            else:
                r = rmin + rng.random() * (min(rmax, 40.) - rmin); th = rng.random() * 2 * math.pi
                p = (near[0] + math.cos(th) * r, near[1] + math.sin(th) * r)
                if behind is not None and rng.random() < .7 and p[1] > near[1] + 1.: p = (p[0], 2 * near[1] - p[1])        # plutôt derrière les personnages (loin de la caméra, +z)
            if not (x0 + 1. <= p[0] <= x1 - 1. and z0 + 1. <= p[1] <= z1 - 1.): continue
            if self.free(*p) and all(math.hypot(p[0] - q[0], p[1] - q[1]) >= gap for q in avoid): return p
        return None

    def boundary(self, rng, side, avoid=()):
        x0, z0, x1, z1 = self.rect; m = 1.0
        for _ in range(40):
            u = .1 + .8 * rng.random()
            p = {'W': (x0 + m, z0 + u * (z1 - z0)), 'E': (x1 - m, z0 + u * (z1 - z0)), 'N': (x0 + u * (x1 - x0), z0 + m), 'S': (x0 + u * (x1 - x0), z1 - m)}[side]
            if self.free(*p) and all(math.hypot(p[0] - q[0], p[1] - q[1]) >= 1.3 for q in avoid): return p
        return None


def _dist(pts): return sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1))


def _cut(pts, d):
    """le point à la distance d le long de la ligne, et la ligne tronquée jusque-là"""
    out = [pts[0]]; acc = 0.
    for i in range(len(pts) - 1):
        L = math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        if acc + L >= d - 1e-9:
            u = (d - acc) / L if L > 1e-9 else 0.; p = (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * u, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * u)
            return p, out + [p]
        acc += L; out.append(pts[i + 1])
    return pts[-1], out


class Script:
    """les actions d'un figurant, avec une estimation du temps (distance / vitesse) pour couper la vie ordinaire au moment d'une réaction"""

    def __init__(self, eid, pos, limit):
        self.eid = eid; self.pos = tuple(pos); self.t = 0.; self.limit = limit; self.acts = []; self.speech = []; self.done = False

    def _add(self, **a): self.acts.append(dict(who=self.eid, **a))
    def room(self): return not self.done and self.t < self.limit - .05

    def wait(self, d, **kw):
        if not self.room(): return
        d = min(d, self.limit - self.t); self._add(do='wait', dur=round(d, 2), **kw); self.t += d

    def look(self, d, amount=1.):
        if not self.room(): return
        d = min(d, self.limit - self.t); self._add(do='look_around', dur=round(d, 2), amount=amount); self.t += d

    def walk(self, pts, speed='walk', verb='walk_to', extra=None):
        """parcourt la ligne `pts` (le premier point est la position courante) ; coupée net à la limite de temps"""
        if len(pts) < 2 or not self.room(): return
        v = SPEEDS[speed] if speed in SPEEDS else float(speed); L = _dist(pts); T = L / v + .45 + .4
        if self.t + T > self.limit:
            d = max(0., (self.limit - self.t - .85) * v)
            if d < .25: self.done = True; return
            _, pts = _cut(pts, d); self.done = True; T = self.limit - self.t
        for p in pts[1:]: self._add(do=verb, to=[round(p[0], 3), round(p[1], 3)], speed=speed, **(extra or {}))
        self.pos = pts[-1]; self.t += T


# ------------------------------------------------------------------------------------------------------------------ l'expansion d'un plan
def wants(shot, ep):
    return bool(shot.get(KEY, ep.get(KEY))) and shot.get(KEY) is not False


def _cfg(shot, ep):
    base = ep.get(KEY) if isinstance(ep.get(KEY), dict) else {}
    sh = shot.get(KEY)
    if sh is False: return None
    c = {**base, **(sh if isinstance(sh, dict) else {})}
    if not c and sh is not True and ep.get(KEY) is not True: return None
    return c


def expand(shot, k, ep, world, casts, states, make_sa, dur, wname, tags, indoor, set_name, scale_of, resolve, fps=24, cam_probe=None):
    """plan -> (plan avec figurants, rapport). `make_sa(plan)` construit le `ShotActing` des seuls principaux (pour connaître leur trajet) ; `resolve(id, cast)` habille un cast (b_chars / b_monsters)."""
    cfg = _cfg(shot, ep)
    if cfg is None: return None
    seed = int(cfg.get('seed', 0)); keep = float(cfg.get('keep_clear', 3.0)); n_req = int(cfg.get('count', 6)); n = min(n_req, MAX)
    rep = dict(shot=k, requested=n_req, placed=0, capped=n_req > MAX, roles={}, skipped=[])
    if n_req > MAX:
        msg = f'figurants : {n_req} demandés, plafonnés à {MAX} (contrat et rendu raisonnables) ; réduire `count` ou scinder en plusieurs plans'
        warnings.warn(msg); rep['message'] = msg
    ex_ids = [f'fig_{i}' for i in range(n)]
    all_ex = {a for a, c in casts.items() if (c or {}).get('extra')} | set(ex_ids)
    lead_shot = dict(shot, absent=sorted(set(shot.get('absent') or []) | all_ex)); lead_shot[KEY] = False
    sa0 = make_sa(lead_shot)
    # ---- les personnages principaux dans le temps : positions échantillonnées -> disques interdits ; centre de la scène
    zones = []; cx = cz = 0.; cn = 0
    for t in np.arange(0., dur + .001, .25):
        smp = sa0.sample(float(t))
        for a, s in smp.items():
            if not s.get('visible', True): continue
            r = SP.RADIUS * scale_of(casts, a) * (1.2 if (casts.get(a) or {}).get('kind') in ('creature', 'faceless') else 1.)
            zones.append((s['x'], s['z'], 1.)); cx += s['x']; cz += s['z']; cn += 1
    zones = _thin(zones)
    centre = (cx / cn, cz / cn) if cn else None
    area = Area(world, zones, keep, True); area.centre = centre
    if cam_probe is not None and centre:                                                                   # la caméra, estimée sur les principaux seuls : où regarde-t-elle ? les figurants se tiennent dans son champ
        poses = cam_probe(sa0)
        if poses:
            px = sum(p[0][0] for p in poses) / len(poses); pz = sum(p[0][2] for p in poses) / len(poses)
            fx = sum(p[1][0] - p[0][0] for p in poses) / len(poses); fz = sum(p[1][2] - p[0][2] for p in poses) / len(poses)
            fov = sum(p[2] for p in poses) / len(poses); asp = poses[0][3]
            half = math.atan(math.tan(math.radians(fov) / 2.) * asp)
            area.view = dict(pos=(px, pz), dir=math.atan2(fz, fx), half=min(half, math.radians(70.)), d=math.hypot(centre[0] - px, centre[1] - pz))
    # ---- troupe
    troupe = cfg.get('troupe', 'auto')
    if troupe == 'auto' or troupe is None:
        pool = TROUPE[kind_of(wname, tags, set_name, indoor)]
        night = 'night' in (tags or ()) or bool(cfg.get('night'))
        pool = [p for p in pool if not (night and p in NIGHT)] or pool
        troupe = _pick(pool, _rng(seed, 'troupe'), n)
    troupe = list(troupe)
    new_casts = {}
    for i, eid in enumerate(ex_ids):
        if eid not in casts: new_casts[eid] = resolve(eid, cast_of(troupe[i % len(troupe)], _rng(seed, 'cast', i), i))
    # ---- rôles (persistants : même figurant, même rôle d'un plan à l'autre)
    mix = dict(cfg.get('mix') or dict(walk=.5, idle=.2, talk_pairs=.2, sit=.1))                         # un `mix` écrit par l'auteur REMPLACE le défaut (ce qui n'y figure pas vaut zéro)
    if indoor: mix['walk'] = min(mix.get('walk', .5), .3)
    names = [r for r in ('walk', 'idle', 'talk_pairs', 'sit') if mix.get(r, 0) > 0]; wts = [mix[r] for r in names]
    roles = {}
    for i, eid in enumerate(ex_ids):
        r = _rng(seed, 'role', i).random() * sum(wts); acc = 0.; role = names[-1]
        for nm, w in zip(names, wts):
            acc += w
            if r <= acc: role = nm; break
        roles[eid] = role
    talkers = [e for e in ex_ids if roles[e] == 'talk_pairs']
    if len(talkers) % 2: roles[talkers[-1]] = 'idle'
    seats = _free_seats(world, shot, area)
    for e in ex_ids:
        if roles[e] == 'sit' and not seats: roles[e] = 'idle'
    # ---- beats de ce plan
    beats = [b for b in (cfg.get('beats') or []) if b.get('shot') in (None, k) or (isinstance(b.get('shot'), (list, tuple)) and k in b['shot'])]
    beats = [b for b in beats if b.get('do', 'life') != 'life']
    actors, actions, speech = [], [], []
    taken = [(states[e]['x'], states[e]['z']) for e in ex_ids if e in states and not states[e].get('gone')]
    pair_plan = {}
    for j in range(0, len(talkers) - len(talkers) % 2, 2): pair_plan[talkers[j]] = talkers[j + 1]
    partner = {**pair_plan, **{v: k_ for k_, v in pair_plan.items()}}
    done_pairs = set()
    for i, eid in enumerate(ex_ids):
        rng = _rng(seed, 'plan', k, i); role = roles[eid]
        st = states.get(eid); alive = bool(st) and not st.get('gone')
        pos = (st['x'], st['z']) if alive else None
        beat = _beat_for(eid, beats, rng, seed, k, i)
        try:
            if role == 'talk_pairs':
                if eid in done_pairs: continue
                other = partner[eid]; done_pairs |= {eid, other}
                r = _talk(eid, other, states, area, rng, dur, taken, scale_of, casts, beat, sa0, centre, beats, seed, k, i)
                if r is None: rep['skipped'].append(eid); rep['skipped'].append(other); continue
                _merge(r, actors, actions, speech)
                rep['roles'][eid] = rep['roles'][other] = 'talk_pairs'
            elif role == 'sit':
                r = _sit(eid, st, alive, seats, area, rng, dur, beat, sa0, centre, casts, taken)
                if r is None: rep['skipped'].append(eid); continue
                _merge(r, actors, actions, speech); rep['roles'][eid] = 'sit'
            elif role == 'walk':
                r = _walk(eid, pos, alive, area, rng, dur, taken, centre, cfg, beat, sa0, indoor)
                if r is None: rep['skipped'].append(eid); continue
                _merge(r, actors, actions, speech); rep['roles'][eid] = 'walk'
            else:
                r = _idle(eid, pos, alive, area, rng, dur, taken, centre, beat, sa0)
                if r is None: rep['skipped'].append(eid); continue
                _merge(r, actors, actions, speech); rep['roles'][eid] = 'idle'
        except _Skip:
            rep['skipped'].append(eid)
    shot2 = dict(shot); shot2['actors'] = list(shot.get('actors') or []) + actors; shot2['actions'] = list(shot.get('actions') or []) + actions
    if speech: shot2['speech'] = list(shot.get('speech') or []) + speech
    rep['placed'] = len({a['id'] for a in actors} | {x for x in ex_ids if x in states and not states[x].get('gone') and x not in rep['skipped']})
    return shot2, new_casts, rep


class _Skip(Exception): pass


def _thin(zs, gap=.3):
    out = []
    for z in zs:
        if not out or all(math.hypot(z[0] - o[0], z[1] - o[1]) > gap for o in out[-40:]): out.append(z)
    return out


def _merge(part, actors, actions, speech):
    a, c, s = part; actors += a; actions += c; speech += s


def _free_seats(world, shot, area):
    """les sièges du monde (VoxWorld.seats, BSetWorld) que ni un principal ni un autre figurant n'occupe et qui sont hors du disque des principaux"""
    seats = dict(getattr(world, 'seats', None) or {})
    sw = getattr(world, 'sw', None)
    if not seats and sw is not None: seats = dict(getattr(sw, '_seats', {}))
    used = {x.get('on') for x in (shot.get('actors') or []) if x.get('on')} | {x.get('on') for x in (shot.get('actions') or []) if x.get('do') == 'sit'}
    out = []; seen = [tuple(map(float, world.seat(n)[:2])) for n in used if n and world.seat(n) is not None]
    for n in sorted(seats):
        p = world.seat(n)
        if n in used or p is None or not area.clear((p[0], p[1])): continue
        q = (float(p[0]), float(p[1]))
        if any(math.hypot(q[0] - o[0], q[1] - o[1]) < .3 for o in seen): continue                       # un siège a souvent plusieurs noms (`chair`, `chair.1`) : une seule personne dessus
        seen.append(q); out.append((n, q))
    return out


# ------------------------------------------------------------------------------------------------------------------ les réactions (beats)
def _beat_for(eid, beats, rng, seed, k, i):
    """la réaction qui concerne ce figurant dans ce plan (ou None) : retard propre à chacun (graine) ; `who`, `frac` et `radius` choisissent qui réagit"""
    for b in beats:
        who = b.get('who')
        if who and eid not in who: continue
        if _rng(seed, 'frac', k, i, b.get('at', 0)).random() > float(b.get('frac', 1.)): continue
        return dict(b, delay=.12 + .45 * _rng(seed, 'delay', k, i).random())
    return None


def _threat_point(b, sa0, at):
    f = b.get('from')
    if isinstance(f, str) and f in getattr(sa0, 'tracks', {}):
        return tuple(sa0.position(sa0.tracks[f], at))
    if isinstance(f, (list, tuple)) and len(f) >= 2: return (float(f[0]), float(f[-1]))
    return None


def _react(sc, area, beat, sa0, rng, exit_ok=True):
    """ajoute la réaction `beat` (flee | freeze | stare | back) à partir de la position estimée du script"""
    if beat is None: return
    at = float(beat.get('at', 1.)) + beat['delay']; T = _threat_point(beat, sa0, float(beat.get('at', 1.)))
    kind = beat.get('do', 'flee'); p = sc.pos
    if T is not None: dist_t = math.hypot(p[0] - T[0], p[1] - T[1]); at += dist_t / 14.
    if kind == 'flee':
        best = None
        for side in 'WENS':
            for _ in range(3):
                q = area.boundary(rng, side)
                if q is None: continue
                rt = area.route(p, q)
                if rt is None: continue
                score = math.hypot(q[0] - T[0], q[1] - T[1]) if T else rng.random()
                if best is None or score > best[0]: best = (score, q, rt)
        sc._add(do='react', kind='flinch', at=round(at, 2))
        if T is not None: sc._add(do='turn_to', target=[round(T[0], 2), round(T[1], 2)], dur=.3)
        if best and exit_ok:
            for q in best[2][1:]: sc._add(do='run_to', to=[round(q[0], 3), round(q[1], 3)], speed='run')
            sc._add(do='exit', to=[round(best[1][0], 3), round(best[1][1], 3)], speed='run')
        return
    sc._add(do='react', kind='startle', at=round(at, 2))
    if kind == 'back' and T is not None:
        u = np.array(p) - np.array(T); L = float(np.hypot(*u)) or 1.; u = u / L
        for dstep in (3.0, 2.2, 1.4):
            q = (p[0] + u[0] * dstep, p[1] + u[1] * dstep)
            if area.free(*q) and area.route(p, q): sc._add(do='walk_to', to=[round(q[0], 3), round(q[1], 3)], speed='slow', backwards=True, face=[round(T[0], 2), round(T[1], 2)]); break
    if T is not None: sc._add(do='look_at', target=[round(T[0], 2), 1.7, round(T[1], 2)], dur=max(1., float(beat.get('hold', 99.))))
    sc._add(do='wait', dur=float(beat.get('hold', 99.)) if kind != 'freeze' else 99.)


# ------------------------------------------------------------------------------------------------------------------ les rôles
def _limit(beat, dur):
    return dur if beat is None else max(.6, float(beat.get('at', 1.)) + beat['delay'] - .05)


def _split(pts, d):
    """le point à la distance d le long de la ligne, et la ligne qui reste à parcourir depuis ce point"""
    acc = 0.
    for i in range(len(pts) - 1):
        L = math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        if acc + L >= d - 1e-9:
            u = (d - acc) / L if L > 1e-9 else 0.; p = (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * u, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * u)
            return p, [p] + list(pts[i + 1:])
        acc += L
    return pts[-1], [pts[-1]]


def _walk(eid, pos, alive, area, rng, dur, taken, centre, cfg, beat, sa0, indoor):
    """un marcheur : il traverse le lieu d'un bord à l'autre (point de passage près de la scène, de préférence derrière les principaux), ou il rôde dans une pièce"""
    if indoor: return _wander(eid, pos, alive, area, rng, dur, taken, centre, beat, sa0)
    x0, z0, x1, z1 = area.rect; along_x = (x1 - x0) >= (z1 - z0)
    side_a, side_b = ('W', 'E') if along_x else ('N', 'S')
    if rng.random() < .5: side_a, side_b = side_b, side_a
    lanes = cfg.get('lanes'); sp = rng.choice(['slow', 'stroll', 'walk', 'walk', 'hurry'])
    if isinstance(lanes, list) and lanes:                                       # voies écrites à la main : on les suit (et on vérifie qu'elles sont libres)
        ln = [tuple(map(float, p)) for p in lanes[int(rng.random() * len(lanes))]]
        if rng.random() < .5: ln = ln[::-1]
        start = pos if alive else ln[0]; X = ln[-1]; full = [start]
        for a, b in zip([start] + ln[1:-1], ln[1:]):
            r = area.route(a, b)
            if r is None: raise _Skip
            full += r[1:]
    else:
        start = pos if alive else area.boundary(rng, side_a, taken); X = area.boundary(rng, side_b)
        if start is None or X is None: raise _Skip
        full = None
        for _ in range(12):
            V = area.spot(rng, behind=True, rmin=4., rmax=10.)
            r1 = area.route(start, V) if V else None; r2 = area.route(V, X) if V else None
            if r1 and r2: full = r1 + r2[1:]; break
        if full is None:
            full = area.route(start, X)
            if full is None: raise _Skip
    L = _dist(full); actors = []; t_enter = 0.
    if not alive:
        if rng.random() < .65:                                                  # déjà dans le lieu quand le plan commence
            _, full = _split(full, L * rng.random() * .55)
            if len(full) < 2: raise _Skip
        else: t_enter = .3 + rng.random() * min(5., dur * .5)                  # il entre par le bord pendant le plan
        actors.append(dict(id=eid, at=[round(full[0][0], 3), round(full[0][1], 3)], facing=[round(full[1][0], 3), round(full[1][1], 3)], **({'visible': [round(t_enter - .05, 2), 1e9]} if t_enter > 0 else {})))
        taken.append(full[0])
    sc = Script(eid, full[0], _limit(beat, dur))
    if t_enter > 0: sc._add(do='wait', dur=round(t_enter, 2)); sc.t = t_enter
    sc.walk(full, sp)
    if sc.room() and beat is None: sc._add(do='exit', to=[round(X[0], 3), round(X[1], 3)], speed=sp)
    if beat is not None: _react(sc, area, beat, sa0, rng)
    return actors, sc.acts, sc.speech


def _wander(eid, pos, alive, area, rng, dur, taken, centre, beat, sa0):
    start = pos if alive else area.spot(rng, avoid=taken, behind=None)
    if start is None: raise _Skip
    actors = [] if alive else [dict(id=eid, at=[round(start[0], 3), round(start[1], 3)], facing=round(rng.random() * 360 - 180))]
    taken.append(start); sc = Script(eid, start, _limit(beat, dur)); sc.look(rng.random() * 1.5 + .4)
    guard = 0
    while sc.room() and guard < 20:
        guard += 1; q = area.sample(rng, near=sc.pos, rmin=1.5, rmax=5., avoid=[])
        r = area.route(sc.pos, q) if q else None
        if r: sc.walk(r, rng.choice(['slow', 'stroll', 'walk']))
        sc.look(1.2 + 2. * rng.random()); sc.wait(.5 + 2. * rng.random())
    if beat is not None: _react(sc, area, beat, sa0, rng, exit_ok=False)
    return actors, sc.acts, sc.speech


def _idle(eid, pos, alive, area, rng, dur, taken, centre, beat, sa0):
    start = pos if alive else area.spot(rng, avoid=taken, behind=True)
    if start is None: raise _Skip
    actors = [] if alive else [dict(id=eid, at=[round(start[0], 3), round(start[1], 3)], facing=round(rng.random() * 360 - 180))]
    taken.append(start); sc = Script(eid, start, _limit(beat, dur))
    guard = 0
    while sc.room() and guard < 40:
        guard += 1; c = rng.random()
        if c < .45: sc.look(1.4 + 2.2 * rng.random())
        elif c < .75: sc.wait(.8 + 2.5 * rng.random())
        else:                                                                    # un petit pas de côté : ils ne restent pas figés
            q = area.sample(rng, near=sc.pos, rmin=.8, rmax=1.8, avoid=[])
            r = area.route(sc.pos, q) if q else None
            if r: sc.walk(r, 'slow')
    if beat is not None: _react(sc, area, beat, sa0, rng)
    return actors, sc.acts, sc.speech


def _talk(a, b, states, area, rng, dur, taken, scale_of, casts, beat, sa0, centre, beats, seed, k, i):
    sa_, sb_ = states.get(a), states.get(b); alive = bool(sa_) and not sa_.get('gone') and bool(sb_) and not sb_.get('gone')
    gap = max(1.7, SP.conv_dist(casts.get(a), scale_of(casts, a), casts.get(b), scale_of(casts, b)) + .2)
    if alive: pa, pb = (sa_['x'], sa_['z']), (sb_['x'], sb_['z'])
    else:
        for _ in range(30):
            p = area.spot(rng, avoid=taken, behind=True)
            if p is None: return None
            th = rng.random() * math.pi; q = (p[0] + math.cos(th) * gap, p[1] + math.sin(th) * gap)
            if area.free(*q) and all(math.hypot(q[0] - t[0], q[1] - t[1]) >= 1.3 for t in taken): pa, pb = p, q; break
        else: return None
        taken += [pa, pb]
    actors = [] if alive else [dict(id=a, at=[round(pa[0], 3), round(pa[1], 3)], facing=[round(pb[0], 3), round(pb[1], 3)]), dict(id=b, at=[round(pb[0], 3), round(pb[1], 3)], facing=[round(pa[0], 3), round(pa[1], 3)])]
    lim = _limit(beat, dur); acts, speech = [], []
    if alive:
        for who, me, you in ((a, pa, pb), (b, pb, pa)): acts.append(dict(who=who, do='turn_to', to=[round(you[0], 3), round(you[1], 3)], target=[round(you[0], 3), round(you[1], 3)]))
    t = .4 + rng.random() * 1.2; who = a; guard = 0
    while t < lim - .9 and guard < 60:
        guard += 1; d = 1.3 + 2.0 * rng.random()
        speech.append([round(t, 2), round(min(lim - .1, t + d), 2), who]); t += d + .3 + .8 * rng.random(); who = b if who == a else a
    out_actors = actors; out_acts = acts
    if beat is not None:                                                         # les deux réagissent, chacun à son rythme (le même `beat`, retards différents : celui de chacun)
        for e, p in ((a, pa), (b, pb)):
            bb = _beat_for(e, [beat], rng, seed, k, i + (0 if e == a else 1)) or dict(beat, delay=beat['delay'])
            sc = Script(e, p, 0.); sc.done = True; _react(sc, area, bb, sa0, rng); out_acts += sc.acts
    return out_actors, out_acts, speech


def _sit(eid, st, alive, seats, area, rng, dur, beat, sa0, centre, casts, taken):
    if alive and st.get('posture') == 'sit': actors = []; p = (st['x'], st['z'])
    else:
        if not seats: return None
        pick = min(seats, key=lambda s: math.hypot(s[1][0] - centre[0], s[1][1] - centre[1]) + 6. * rng.random()) if centre else seats[int(rng.random() * len(seats))]
        seats.remove(pick); actors = [dict(id=eid, on=pick[0])]; p = pick[1]; taken.append(p)                          # ceux qui se tiennent debout évitent les assis
    sc = Script(eid, p, _limit(beat, dur)); guard = 0
    while sc.room() and guard < 40:
        guard += 1
        if rng.random() < .5: sc.look(1.5 + 2. * rng.random())
        else: sc.wait(1. + 3. * rng.random())
    if beat is not None:
        sc._add(do='react', kind='startle', at=round(float(beat.get('at', 1.)) + beat['delay'], 2))
        if beat.get('do') == 'flee': sc._add(do='stand')
    return actors, sc.acts, sc.speech


# ------------------------------------------------------------------------------------------------------------------ audit
def audit(contract, keep=3.0, extra_rects=()):
    """contrat -> mesures sur les figurants (cast `extra`) : images où deux corps se chevauchent (tous acteurs), distance minimale d'un figurant à un personnage principal, images sous `keep - .3`,
    images où un figurant est dans l'emprise d'un décor du plan (ou d'un rectangle donné), nombre de figurants qui bougent, entrées (premières images invisibles) et sorties. Ne modifie rien."""
    casts = contract.get('casts') or {}; ci = SP.CI
    ex = {a for a, c in casts.items() if (c or {}).get('extra')}
    def scale_of(cs, a):
        d = cs.get(a) or {}; return float(d.get('scale') or (.95 if d.get('preset') == 'lina' else 1.05 if d.get('preset') == 'alien' else 1.))
    rep = dict(extras=len(ex), frames=0, overlap_frames=0, min_to_leads=None, below_keep_frames=0, penetration_frames=0, moving=0, entered=0, exited=0)
    moving = set(); ent = set(); ext = set()
    for st in contract['stages']:
        rows = st.get('actors') or {}; ids = list(rows); n = min((len(r) for r in rows.values()), default=0)
        rects = SP.footprints(st.get('props')) + list(extra_rects); leads = [a for a in ids if a not in ex]
        for j in range(n):
            vis = [a for a in ids if rows[a][j][ci['vis']] > .5]
            for i, a in enumerate(vis):
                for b in vis[i + 1:]:
                    d = math.hypot(rows[a][j][ci['x']] - rows[b][j][ci['x']], rows[a][j][ci['z']] - rows[b][j][ci['z']])
                    if d < SP.phys_dist(casts.get(a), scale_of(casts, a), casts.get(b), scale_of(casts, b)) - .03: rep['overlap_frames'] += 1      # 3 cm de tolérance (pieds qui se frôlent)
                    if (a in ex) != (b in ex) and not ((a in ex) and (b in ex)):
                        rep['min_to_leads'] = d if rep['min_to_leads'] is None else min(rep['min_to_leads'], d)
                        if d < keep - .3: rep['below_keep_frames'] += 1
            for a in vis:
                if a in ex and rows[a][j][ci['sit']] < .5 and SP._inside((rows[a][j][ci['x']], rows[a][j][ci['z']]), rects, margin=.0): rep['penetration_frames'] += 1       # un figurant assis est SUR la chaise, pas dedans
        for a in ex:
            if a not in rows: continue
            r = rows[a]; xs = [(q[ci['x']], q[ci['z']]) for q in r if q[ci['vis']] > .5]
            if len(xs) > 1 and max(math.hypot(p[0] - xs[0][0], p[1] - xs[0][1]) for p in xs) > 1.0: moving.add(a)
            if r and r[0][ci['vis']] < .5 and any(q[ci['vis']] > .5 for q in r): ent.add(a)
            if r and r[-1][ci['vis']] < .5 and any(q[ci['vis']] > .5 for q in r): ext.add(a)
        rep['frames'] += n
    rep['moving'] = len(moving); rep['entered'] = len(ent); rep['exited'] = len(ext)
    if rep['min_to_leads'] is not None: rep['min_to_leads'] = round(rep['min_to_leads'], 2)
    return rep
