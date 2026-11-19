"""OBJETS DÉTAILLÉS (01/11/2026), version PS1 native : la bibliothèque des objets du quotidien, posés et tenus en main.

Plainte du propriétaire : « au niveau des tasses de café, des appareils, téléphones et tout le reste, il faut arrêter de faire des briques ».
Ce module dessine ces objets en boîtes PS1 avec de la FORME (anse, cadran, combiné, cordon spiralé, pied, abat-jour) et du DÉTAIL peint
(écran lisible, étiquette, clavier, page imprimée, aiguilles), dans le style du moteur : boîtes nettes + textures en pixels.
La version VOXEL native est `voxelgpu/b_objets.py` (règle des deux versions, docs/REGLE_DEUX_VERSIONS.md) : même plan, autre exécution.

Trois entrées, et rien d'autre ne change :
  * des types de décor NOUVEAUX `od_*` (toujours disponibles : un nom nouveau ne touche aucun film d'avant), voir KINDS ;
  * des objets tenus NOUVEAUX `od_*` (clé `hold`), voir HELD ;
  * la clé d'épisode `objets` (posée par le profil `production`) : les noms d'AVANT deviennent leur version détaillée
    (`tv`, `nightstand`, `desk_lamp`, `computer`, `laptop`, `clock`, `wall_clock`, `plant`, `cups`, `bottles`, `framed_photo`, `suitcase`, `candles`,
    `note`, `tv_old`, `tv_stand` posés ; `phone`, `mobile*`, `handset`, `cup`, `book`, `notebook`, `printout`, `key`, `bottle`, `bag`,
    `flashlight`, `candle`, `crowbar` tenus). Sans la clé : `prop_hook` rend None et `held_item` rend la main à l'original, boîte pour boîte.

Repère d'un décor : face avant vers -z, x à droite vu de face, y = 0 posé (la clé `y` du décor le soulève, comme partout).
Repère d'un objet tenu : P(lat, haut, avant) autour de la main (lat > 0 vers l'extérieur de la main droite), droit dans le repère du torse.
Chaque décor `od_*` commence par deux MARQUEURS (boîtes cachées de taille nulle) : ils disent à VOXEL quel objet est là, où et tourné comment,
pour qu'il le repeigne dans sa version native au lieu de convertir les boîtes PS1 (`natives()`). Ils ne sont ni vus, ni ombrés, ni obstacles.
Rien d'aléatoire non semé, aucune horloge."""
import json, math
import numpy as np
from .r3d import B, C, Box, M_FABRIC, M_WOODV, M_PLASTER, M_METAL, M_CARD
from . import objets_tex as T

# ================================================================== clé d'épisode `objets`
PRESETS = {'detailles': dict(decors=True, tenus=True), 'decors': dict(decors=True, tenus=False), 'tenus': dict(decors=False, tenus=True)}
_STATE = None


def configure(spec, episode=None):
    """`spec` = la clé d'épisode `objets` : None / False (absente), un nom de PRESETS, True (= detailles), ou un dict
    {"style": "detailles", "decors": bool, "tenus": bool, "contenu": {nom d'objet tenu: {réglages}}}. -> état résolu, ou None"""
    global _STATE
    _STATE = None
    if not spec: return None
    if spec is True: name, over = 'detailles', {}
    elif isinstance(spec, str): name, over = spec, {}
    elif isinstance(spec, dict): name = spec.get('style') or spec.get('preset') or 'detailles'; over = spec
    else: return None
    if name not in PRESETS: return None
    st = dict(PRESETS[name]); st['name'] = name
    for k in ('decors', 'tenus'):
        if k in over: st[k] = bool(over[k])
    cont = over.get('contenu') or over.get('tenus_contenu') or {}
    st['contenu'] = {str(k): dict(v) for k, v in cont.items() if isinstance(v, dict)} if isinstance(cont, dict) else {}
    _STATE = st
    return st


def use(state):
    """re-pose l'état avant de rendre (le pool « spawn » reconstruit le moteur par processus)"""
    global _STATE
    _STATE = state
    return state


def active(): return _STATE


def signature():
    s = _STATE
    return '' if not s else 'od:' + json.dumps({k: s[k] for k in ('name', 'decors', 'tenus', 'contenu')}, sort_keys=True, ensure_ascii=True)


def notices(ep):
    s = _STATE
    if not s: return []
    return [f'objets « {s["name"]} » : téléphones, tasses, lampes, écrans, papiers... détaillés (posés{" et tenus" if s["tenus"] else ""}) ; '
            'sans cette clé les objets d\'avant restent identiques']


def _cfg(name):
    """réglages d'un objet tenu, écrits dans la clé d'épisode : {"objets": {"contenu": {"od_smartphone": {"ecran": "appel", "nom": "MAMAN"}}}}"""
    s = _STATE
    return dict((s or {}).get('contenu', {}).get(name) or {})


def _g(p, *names, default=None):
    for n in names:
        if p.get(n) is not None: return p[n]
    return default


def _sh(c, k): return tuple(max(0, min(255, int(v * k))) for v in c[:3])


def _col(c, d):
    if c is None or c == (): return tuple(d)
    return tuple(int(v) for v in list(c)[:3])


# ================================================================== small builders
def rnd(x, y, z, w, h, d, col, k=None, **kw):
    """prisme « rond » : croix de deux boîtes + un carré à 86 % (silhouette octogonale) ; y = le bas"""
    k = k or {}
    return [C((x, y + h / 2, z), (w, h, d * .62), col, **kw, **k), C((x, y + h / 2, z), (w * .62, h, d), col, **kw, **k), C((x, y + h / 2, z), (w * .87, h, d * .87), col, **kw, **k)]


def rnd2(x, y, z, w, h, d, col, k=None, **kw):
    k = k or {}
    return [C((x, y + h / 2, z), (w, h, d * .66), col, **kw, **k), C((x, y + h / 2, z), (w * .66, h, d), col, **kw, **k)]


def coil(pts, col=(30, 30, 34), s=.0085, step=.0085, r=.0045, k=None):
    """cordon spiralé : petits cubes le long d'une ligne brisée, décalés en alternance (les spires)"""
    k = k or {}; out = []; acc = 0
    P = [np.asarray(p, np.float32) for p in pts]
    for a, b in zip(P[:-1], P[1:]):
        v = b - a; L = float(np.linalg.norm(v))
        if L < 1e-6: continue
        u = v / L; side = np.cross(u, np.array([0, 1, 0], np.float32))
        if np.linalg.norm(side) < 1e-3: side = np.array([1, 0, 0], np.float32)
        side = side / np.linalg.norm(side); up = np.cross(side, u)
        n = max(1, int(L / step))
        for i in range(n):
            q = a + v * (i + .5) / n; ph = acc % 4; acc += 1
            off = side * r * (1 if ph in (0, 1) else -1) + up * r * (1 if ph in (1, 2) else -1) * .7
            out.append(C(tuple(q + off), (s, s, s), col, cast=False, **k))
    return out


def line(a, b, w, col, n=None, k=None, **kw):
    """segment épais en boîtes alignées (escalier) : un bras de lampe, un manche, une aiguille"""
    k = k or {}; a = np.asarray(a, float); b = np.asarray(b, float); L = float(np.linalg.norm(b - a))
    n = n or max(1, int(L / (w * 1.4)))
    seg = (b - a) / n; sz = np.abs(seg) + w
    return [C(tuple(a + seg * (i + .5)), tuple(sz), col, **kw, **k) for i in range(n)]


def bands(x0, x1, y0, z0, z1, h, img, col, n, face='-z', step=(0., .01), texemis=0., k=None, **kw):
    """une image posée sur n bandes horizontales en escalier (écran incliné, pupitre) : bande i porte la tranche i de l'image.
    step = (montée y, recul z) entre deux bandes ; face '-z' = image lue de face."""
    k = k or {}; img = np.asarray(img); H = img.shape[0]; out = []
    for i in range(n):
        r0 = int(round(H * i / n)); r1 = int(round(H * (i + 1) / n))
        sl = np.ascontiguousarray(img[r0:r1])
        yb = y0 + h * (n - 1 - i) / n; zz = z0 + step[1] * (n - 1 - i)
        out.append(B((x0, yb, zz), (x1 - x0, h / n, z1 - z0), col, tex={face: sl}, texemis=texemis, **kw, **k))
    return out


# ================================================================== markers (VOXEL repaints the object in its native version)
MARK_BASE = 1.0e6
_REG = {}          # code -> (kind, params)
_CODES = {}        # (kind, params json) -> code


def _code(kind, p):
    key = (kind, json.dumps({k: v for k, v in (p or {}).items() if k not in ('at', 'rot', 'y', 'id', 'group')}, sort_keys=True, default=str))
    c = _CODES.get(key)
    if c is None:
        c = len(_CODES) + 1; _CODES[key] = c; _REG[c] = (kind, json.loads(key[1]))
    return c


def _markers(kind, p, n):
    a = Box((0, 0, 0), (0, 0, 0), (0, 0, 0), hidden=True, grain=MARK_BASE + _code(kind, p), cast=False, noref=True)
    b = Box((.001, 0, 0), (.001, 0, 0), (0, 0, 0), hidden=True, grain=MARK_BASE + n, cast=False, noref=True)
    return [a, b]


def is_marker(b):
    return bool(getattr(b, 'hidden', False)) and getattr(b, 'grain', 0) >= MARK_BASE and float(np.abs(np.asarray(b.hi) - np.asarray(b.lo)).max()) < 1e-9


def read_markers(boxes):
    """[(index du 1er marqueur, kind, params, x, y, z, rot, n boîtes de l'objet)] des objets détaillés d'une liste de boîtes (déjà posées)"""
    out = []; bx = list(boxes); i = 0
    while i < len(bx) - 1:
        a = bx[i]
        if is_marker(a) and is_marker(bx[i + 1]):
            code = int(round(a.grain - MARK_BASE)); n = int(round(bx[i + 1].grain - MARK_BASE))
            if code in _REG:
                kind, p = _REG[code]
                pa = np.asarray(a.lo, float); pb = np.asarray(bx[i + 1].lo, float); dx, dz = pb[0] - pa[0], pb[2] - pa[2]
                rot = 0 if dx > 5e-4 else 2 if dx < -5e-4 else 1 if dz < 0 else 3
                out.append((i, kind, p, float(pa[0]), float(pa[1]), float(pa[2]), rot, n))
                i += 2 + n; continue
        i += 1
    return out


# ================================================================== the objects (PS1)
METAL = (186, 188, 196); BRASS = (196, 160, 80); BLACK = (28, 28, 32); IVORY = (222, 216, 198); WOOD = (110, 72, 44)


def k_phone_rotary(p, c):
    """téléphone fixe à cadran (années 1960-80) : socle bombé en trois gradins, cadran chiffré, combiné sur sa fourche, cordon spiralé, cordon de ligne"""
    col = _col(c, BLACK); dk = _sh(col, .6); lab = str(_g(p, 'numero', 'label', default=''))[:4]
    out = [C((0, .006, .01), (.22, .012, .23), dk),
           C((0, .041, .01), (.21, .058, .22), col),                                     # y .012 -> .07
           C((0, .0875, .03), (.19, .035, .18), col),                                    # y .07 -> .105
           C((0, .1125, .035), (.15, .015, .13), col),                                   # y .105 -> .12
           C((0, .094, -.08), (.12, .045, .045), col)]                                    # remplit derrière le haut du cadran
    out.append(B((-.05, .016, -.107), (.1, .1, .007), col, tex={'-z': T.rotary_dial(col, lab or '')}))
    out.append(C((.036, .03, -.112), (.008, .012, .006), METAL, mat=M_METAL))            # butée du cadran
    out.append(C((.078, .022, -.102), (.014, .009, .004), (255, 60, 40) if _g(p, 'voyant', default=False) else (80, 24, 20), emis=2.4 if _g(p, 'voyant', default=False) else 0., cast=False))
    if _g(p, 'combine', 'handset', default=True):
        out += [C((.05, .126, .035), (.016, .016, .05), dk), C((-.05, .126, .035), (.016, .016, .05), dk)]          # fourche
        out += [C((0, .142, .035), (.17, .02, .034), col),                              # manche
                C((.085, .135, .035), (.052, .036, .062), col), C((-.085, .135, .035), (.052, .036, .062), col),
                C((.085, .1165, .035), (.04, .002, .05), _sh(col, 1.6)), C((-.085, .1165, .035), (.04, .002, .05), _sh(col, 1.6))]   # bords des pavillons
        a = (-.105, .125, .04)
    else:
        out += [C((.05, .128, .035), (.016, .02, .05), dk), C((-.05, .128, .035), (.016, .02, .05), dk), C((.05, .124, .035), (.01, .014, .01), METAL, mat=M_METAL), C((-.05, .124, .035), (.01, .014, .01), METAL, mat=M_METAL)]
        a = (-.1, .05, .06)
    if _g(p, 'cordon', 'cord', default=True):
        out += coil([a, (-.122, .08, .05), (-.13, .02, .03), (-.17, .007, -.03), (-.15, .007, -.1), (-.106, .015, -.06)], dk)
    out.append(C((0, .012, .16), (.008, .008, .08), dk))                                   # cordon de ligne vers le mur
    return out


def k_phone_desk(p, c):
    """téléphone de bureau à touches : coque en pente, clavier en quatre rangées, petit écran, touches de fonction, voyant, combiné couché sur deux fourches, cordon spiralé"""
    col = _col(c, IVORY); dk = _sh(col, .55); keyc = _col(_g(p, 'touches'), (230, 226, 214) if sum(col) < 400 else (56, 56, 62))
    out = [C((0, .015, 0), (.2, .03, .22), col), C((0, .04, .05), (.2, .02, .12), col), C((0, .057, .08), (.2, .014, .06), col)]
    kp = T.keypad(4, 3, keyc, (24, 24, 28) if sum(keyc) > 400 else (230, 230, 236), dk)
    H = kp.shape[0]
    for r in range(4):                                                                     # rangée 0 = « 1 2 3 », au fond
        sl = np.ascontiguousarray(kp[int(H * r / 4):int(H * (r + 1) / 4)])
        zb = -.012 - r * .022; yt = .034 - r * .002
        out.append(B((-.01, .03, zb - .02), (.075, yt - .03 + .004, .02), col, tex={'+y': T.flat(sl)}))
    if _g(p, 'ecran', 'screen', default=True) is not False:
        txt = str(_g(p, 'ecran', 'screen', default='')) if isinstance(_g(p, 'ecran', 'screen'), str) else T.hhmm(_g(p, 'heure', 'time'), '02:13')
        out.append(B((-.0, .05, .049), (.075, .014, .002), (40, 60, 40), tex={'-z': T.lcd(txt or '02:13', 36, 10)}, texemis=.55, cast=False))
    for i, fc in enumerate(((190, 40, 40), (70, 70, 76), (70, 70, 76), (60, 130, 70))):
        out.append(C((.0 + i * .02, .052, .01), (.014, .006, .012), fc))
    on = bool(_g(p, 'voyant', default=False))
    out.append(C((.085, .046, .045), (.01, .006, .01), (255, 60, 40) if on else (90, 26, 22), emis=2.5 if on else 0., cast=False))
    if _g(p, 'combine', 'handset', default=True):
        hy = .066
        out += [C((-.06, hy, -.06), (.03, .02, .02), dk), C((-.06, hy + .01, .07), (.03, .04, .02), dk),
                C((-.06, hy + .028, .005), (.038, .02, .19), col),
                C((-.06, hy + .022, .082), (.052, .032, .052), col), C((-.06, hy + .022, -.075), (.052, .032, .052), col),
                C((-.06, hy + .0055, .082), (.04, .002, .04), _sh(col, .75)), C((-.06, hy + .0055, -.075), (.04, .002, .04), _sh(col, .75))]
        a = (-.075, hy + .01, -.1)
    else:
        a = (-.1, .02, -.05)
    if _g(p, 'cordon', 'cord', default=True):
        out += coil([a, (-.1, .035, -.125), (-.13, .008, -.09), (-.14, .008, .0), (-.105, .02, .05)], dk)
    out.append(C((0, .01, .14), (.008, .008, .06), dk))
    return out


def k_smartphone(p, c):
    """smartphone posé écran vers le haut (`debout: true` : debout contre un support, écran vers l'avant) ; coque, boutons, écran lisible configurable"""
    case = _col(c, (44, 48, 66)); W_, L_ = .074, .154
    scr = _screen_img(p)
    if _g(p, 'debout', default=False):
        out = [B((-W_ / 2, .03, -.004), (W_, L_, .009), case), B((-W_ / 2 + .004, .03 + .005, -.0055), (W_ - .008, L_ - .01, .002), (20, 24, 40), tex={'-z': scr}, texemis=.9, cast=False)]
        out += [B((-.05, 0, -.03), (.1, .012, .06), (60, 60, 66), mat=M_METAL), B((-.04, .012, .004), (.08, .06, .01), (60, 60, 66), mat=M_METAL), B((-.045, .012, -.03), (.09, .022, .01), (60, 60, 66), mat=M_METAL)]
        return out
    out = [B((-W_ / 2, 0, -L_ / 2), (W_, .009, L_), case),
           B((-W_ / 2 + .004, .009, -L_ / 2 + .005), (W_ - .008, .0015, L_ - .01), (20, 24, 40), tex={'+y': T.flat(scr)}, texemis=.9, cast=False),
           C((W_ / 2 + .001, .005, .03), (.003, .004, .02), _sh(case, .7)), C((W_ / 2 + .001, .005, .0), (.003, .004, .012), _sh(case, .7)), C((-W_ / 2 - .001, .005, .02), (.003, .004, .03), _sh(case, .7))]
    return out


def _screen_img(p, default_mode='verrou'):
    tx = _g(p, 'texte', 'text', 'lignes')
    mode = _g(p, 'ecran', 'screen', default=default_mode)
    if mode == 'image':
        return T.image_locale(str(p.get('image_locale','')),str(p.get('image_sha256','')))
    if isinstance(mode, (list, tuple)): tx, mode = mode, 'lignes'
    if mode not in ('verrou', 'appel', 'message', 'lignes', 'noir'): mode = 'lignes' if tx else default_mode
    return T.phone_screen(mode, T.hhmm(_g(p, 'heure', 'time'), '02:13'), str(_g(p, 'date', default='VEN. 31 OCT')), str(_g(p, 'nom', 'name', default='INCONNU')), T.lines(tx))


def k_switchboard(p, c):
    """standard téléphonique de réception (années 70) : coffre en bois, pupitre en gradins (une rangée de voyants par étage, numérotés), jacks,
    fiches branchées et leurs cordons qui pendent, clés de commande, cadran, plaque « STANDARD », combiné d'opératrice sur le côté"""
    wood = _col(c, (92, 60, 38)); panel = (54, 50, 44)
    rows = [str(r) for r in (_g(p, 'etages', 'rows', default=['3', '2', '1', '0']))][:6]
    n = int(_g(p, 'chambres', 'rooms', default=13)); lit = tuple(str(x) for x in (_g(p, 'allumes', 'lit', default=[]) or []))
    plugged = [str(x) for x in (_g(p, 'fiches', 'plugs', default=['104', '212']) or [])]
    W_ = .74; x0 = -W_ / 2 + .04; x1 = W_ / 2 - .04; nr = len(rows); step_h, step_d = .065, .055
    out = [B((-W_ / 2, 0, -.2), (W_, .08, .44), wood, mat=M_WOODV),                       # coffre
           B((-W_ / 2, 0, -.205), (W_, .012, .45), _sh(wood, .7), mat=M_WOODV),
           B((-W_ / 2 - .02, 0, -.2), (.02, .08 + nr * step_h + .03, .44), _sh(wood, .85), mat=M_WOODV), B((W_ / 2, 0, -.2), (.02, .08 + nr * step_h + .03, .44), _sh(wood, .85), mat=M_WOODV)]
    pl = T.plate(str(_g(p, 'plaque', default='STANDARD')), 48, 9)
    out.append(B((-.12, .025, -.207), (.24, .045, .004), (176, 150, 90), tex={'-z': pl}))
    for i, r in enumerate(rows):                                                           # rangée 0 (dernier étage) au fond, en haut
        j = nr - 1 - i; y = .08 + j * step_h; z = -.14 + j * step_d
        out.append(B((x0, y, z), (x1 - x0, step_h, .44 - (z + .2)), panel))
        strip = T.switch_strip(r, n, lit)
        out.append(B((x0, y + .006, z - .003), (x1 - x0, step_h - .012, .003), panel, tex={'-z': strip}, texemis=.12))
        out.append(B((x0, y + step_h, z), (x1 - x0, .002, step_d if j < nr - 1 else .2), panel, tex={'+y': T.flat(T.jack_strip(n))}))
        cell = (x1 - x0) / (8 + n * 7 + 2)
        for k_ in range(n):
            lab = f'{r}{k_ + 1:02d}'
            cx = x0 + (8 + k_ * 7 + 2.5) * cell
            if lab in lit: out.append(C((cx, y + step_h * .3, z - .007), (.012, .014, .008), (255, 150, 40), emis=2.2, cast=False))
            if lab in plugged:                                                               # fiche branchée sur la marche, cordon qui pend en boucle vers l'avant
                out += [C((cx, y + step_h + .02, z + .02), (.012, .04, .012), (30, 30, 34)), C((cx, y + step_h + .045, z + .02), (.014, .012, .014), (190, 40, 40) if k_ % 2 else (40, 90, 170))]
                out += line((cx, y + step_h + .05, z + .02), (cx - .03, .1, -.19), .007, (34, 30, 28), n=8, cast=False)
                out += line((cx - .03, .1, -.19), (cx - .06, .085, -.17), .007, (34, 30, 28), n=2, cast=False)
    for i in range(8):                                                                     # clés de commande sur l'avant du coffre
        x = -.3 + i * .045; out += [C((x, .085, -.17), (.02, .01, .02), (40, 38, 34)), C((x, .1, -.172), (.008, .025, .008), (200, 40, 40) if i % 3 == 0 else (30, 30, 34))]
    out += [B((.17, .08, -.19), (.12, .006, .12), (36, 34, 32)), C((.23, .087, -.13), (.09, .008, .09), (30, 30, 34))]   # cadran d'opératrice
    out.append(B((.19, .088, -.175), (.08, .002, .08), (30, 30, 34), tex={'+y': T.flat(T.rotary_dial((30, 30, 34), ''))}))
    hs = (24, 24, 28)                                                                       # combiné d'opératrice accroché sur le côté gauche
    out += [C((-W_ / 2 - .045, .2, .0), (.03, .16, .04), hs), C((-W_ / 2 - .045, .29, .0), (.045, .04, .05), hs), C((-W_ / 2 - .045, .11, .0), (.045, .04, .05), hs),
            C((-W_ / 2 - .025, .25, .0), (.02, .02, .02), METAL, mat=M_METAL)]
    out += coil([(-W_ / 2 - .045, .09, .0), (-W_ / 2 - .06, .03, -.05), (-W_ / 2 - .02, .01, -.12)], (30, 30, 30))
    return out


def k_cup(p, c):
    """tasse de café sur sa soucoupe : pied, corps « rond », filet doré, café avec sa crème, anse en boucle, cuillère, vapeur légère"""
    col = _col(c, (238, 236, 230)); rim = _sh(col, 1.06)
    out = [] if _g(p, 'soucoupe', default=True) is False else [C((0, .005, 0), (.15, .01, .1), col), C((0, .005, 0), (.1, .01, .15), col), C((0, .005, 0), (.13, .01, .13), col), C((0, .0105, 0), (.06, .001, .06), _sh(col, .9))]
    y0 = .011 if out else 0.
    out += [C((0, y0 + .005, 0), (.048, .01, .048), _sh(col, .92))]
    out += rnd(0, y0 + .01, 0, .084, .066, .084, col)
    out += [C((0, y0 + .074, 0), (.086, .006, .06), rim), C((0, y0 + .074, 0), (.06, .006, .086), rim)]
    out += [C((0, y0 + .066, 0), (.0866, .004, .0606), (200, 160, 60)), C((0, y0 + .066, 0), (.0606, .004, .0866), (200, 160, 60))]   # filet doré
    if _g(p, 'cafe', 'plein', default=True):
        out.append(B((-.034, y0 + .0705, -.034), (.068, .002, .068), (70, 40, 22), tex={'+y': T.flat(T.crema())}))
    out += [C((.054, y0 + .06, 0), (.026, .01, .014), col), C((.068, y0 + .043, 0), (.01, .036, .014), col), C((.054, y0 + .026, 0), (.026, .01, .014), col)]
    if out and _g(p, 'cuillere', 'spoon', default=True) and _g(p, 'soucoupe', default=True) is not False:
        out += [C((-.02, y0 + .003, -.05), (.06, .004, .009), METAL, mat=M_METAL), C((.016, y0 + .004, -.05), (.018, .005, .015), METAL, mat=M_METAL)]
    if _g(p, 'vapeur', 'steam', default=True):
        for k_ in range(4):
            out.append(C((.012 * math.sin(k_ * 2.1 + .4), y0 + .095 + .028 * k_, -.006 + .01 * math.cos(k_ * 1.6)), (.014, .02, .014), (222, 224, 228), dissolve=.52 + .12 * k_, cast=False))
    return out


def k_mug(p, c):
    """mug : gros corps, impression sur la face avant (texte ou motif), anse épaisse, café, vapeur"""
    col = _col(c, (60, 120, 150)); ink = _col(_g(p, 'encre'), (250, 246, 236))
    out = rnd(0, 0, 0, .095, .105, .095, col)
    pr = T.mug_print(str(_g(p, 'texte', 'text', default='')), str(_g(p, 'motif', default='coeur')), col, ink)
    out.append(B((-.03, .022, -.0485), (.06, .06, .002), col, tex={'-z': pr}))
    out += [C((0, .1035, 0), (.0955, .004, .06), _sh(col, 1.15)), C((0, .1035, 0), (.06, .004, .0955), _sh(col, 1.15))]
    if _g(p, 'cafe', 'plein', default=True): out.append(B((-.038, .099, -.038), (.076, .002, .076), (66, 38, 20), tex={'+y': T.flat(T.crema())}))
    out += [C((.06, .085, 0), (.03, .016, .02), col), C((.078, .053, 0), (.014, .05, .02), col), C((.06, .022, 0), (.03, .016, .02), col)]
    if _g(p, 'vapeur', 'steam', default=False):
        for k_ in range(5): out.append(C((.01 * math.sin(k_ * 1.9), .13 + .035 * k_, 0), (.02, .024, .02), (220, 222, 226), dissolve=.42 + .11 * k_, cast=False))
    return out


LIQ = {'eau': (120, 170, 214), 'vin': (110, 18, 34), 'whisky': (196, 120, 40), 'lait': (240, 238, 228), 'biere': (220, 160, 40), 'jus': (240, 150, 40)}


def k_glass(p, c):
    """verre : `modele` gobelet (défaut) ou `pied` (verre à vin) ; parois translucides tramées, liquide `contenu` (eau, vin, whisky avec glaçons, lait, bière, vide)"""
    glass = _col(c, (190, 206, 216)); mod = _g(p, 'modele', default='gobelet'); cont = _g(p, 'contenu', default='vin' if mod == 'pied' else 'eau')
    out = []
    if mod == 'pied':
        out += [C((0, .003, 0), (.07, .006, .07), glass, refl=.3), C((0, .045, 0), (.008, .08, .008), glass, refl=.3)]
        if cont in LIQ: out += rnd2(0, .09, 0, .06, .035, .06, LIQ[cont], refl=.2)
        out += rnd2(0, .085, 0, .074, .1, .074, glass, refl=.35, dissolve=.74, cast=False)
        out += _rim_ps1(.037, .186, glass)
        return out
    out += rnd2(0, 0, 0, .07, .012, .07, glass, refl=.3)
    if cont in LIQ:
        out += rnd2(0, .012, 0, .062, .06, .062, LIQ[cont], refl=.15)
        if cont == 'whisky': out += [C((-.01, .07, .005), (.024, .022, .024), (226, 236, 240), refl=.3), C((.013, .066, -.008), (.02, .02, .02), (226, 236, 240), refl=.3)]
    out += rnd2(0, .012, 0, .072, .088, .072, glass, refl=.35, dissolve=.74, cast=False)
    out += _rim_ps1(.036, .1, glass)
    return out


def _rim_ps1(r, y, glass):
    """bord clair d'un verre : un anneau (huit côtés), pas un couvercle"""
    c = _sh(glass, 1.25); t = .004; a = r * .62
    return [C((0, y, -r), (a * 2, .003, t), c, emis=.15, cast=False), C((0, y, r), (a * 2, .003, t), c, emis=.15, cast=False), C((-r, y, 0), (t, .003, a * 2), c, emis=.15, cast=False),
            C((r, y, 0), (t, .003, a * 2), c, emis=.15, cast=False)] + [C((sx * r * .8, y, sz * r * .8), (t * 1.5, .003, t * 1.5), c, emis=.15, cast=False) for sx in (-1, 1) for sz in (-1, 1)]


BOTTLES = {'vin': ((40, 70, 46), (110, 18, 34), 'CHATEAU', '1998'), 'biere': ((110, 66, 26), (220, 160, 40), 'BIERE', 'BLONDE'),
           'eau': ((170, 200, 220), (150, 190, 214), 'SOURCE', '1,5 L'), 'whisky': ((150, 92, 34), (196, 120, 40), 'WHISKY', '12 ANS')}


def k_bottle(p, c):
    """bouteille : `modele` vin (défaut), biere, eau, whisky ; verre teinté avec reflet, épaulement, goulot, capsule, étiquette lisible devant (et contre-étiquette)"""
    mod = _g(p, 'modele', default='vin'); g_, liq, t1, t2 = BOTTLES.get(mod, BOTTLES['vin']); glass = _col(c, g_)
    et = str(_g(p, 'etiquette', 'texte', 'text', default=t1)); sous = str(_g(p, 'sous', default=t2))
    if mod == 'whisky':
        out = [B((-.045, 0, -.03), (.09, .17, .06), glass, refl=.35), B((-.03, .17, -.02), (.06, .02, .04), glass, refl=.35), C((0, .2, 0), (.03, .04, .03), glass, refl=.3), C((0, .232, 0), (.036, .026, .036), (30, 26, 22))]
        out.append(B((-.035, .04, -.032), (.07, .07, .002), (230, 220, 190), tex={'-z': T.label(et, sous, (232, 222, 196), (60, 30, 20))}))
        return out
    h = {'vin': .2, 'biere': .14, 'eau': .22}.get(mod, .2); w = {'vin': .074, 'biere': .062, 'eau': .084}.get(mod, .074)
    out = rnd(0, 0, 0, w, h, w, glass, refl=.35, dissolve=.25 if mod == 'eau' else 0.)
    out += rnd2(0, h, 0, w * .78, .025, w * .78, glass, refl=.35) + rnd2(0, h + .025, 0, w * .4, .07 if mod != 'biere' else .045, w * .4, glass, refl=.3)
    top = h + .025 + (.07 if mod != 'biere' else .045)
    out.append(C((0, top - .012, 0), (w * .45, .03, w * .45), {'vin': (150, 20, 30), 'biere': (200, 170, 60), 'eau': (40, 90, 190)}.get(mod, (150, 20, 30)), mat=M_METAL if mod == 'biere' else 0))
    out.append(C((w * .33, h * .55, -w * .3), (.006, h * .7, .004), (230, 240, 236), emis=.25, cast=False))      # reflet vertical
    lab = T.label(et, sous, (236, 226, 200) if mod != 'eau' else (60, 120, 200), (90, 20, 30) if mod != 'eau' else (250, 250, 250))
    out.append(B((-w * .36, h * .22, -w * .5 - .002), (w * .72, h * .42, .002), (236, 226, 200), tex={'-z': lab}))
    out.append(B((-w * .3, h * .3, w * .5), (w * .6, h * .3, .002), (236, 226, 200), tex={'+z': T.label('', 'CONTRE', (236, 226, 200), (90, 90, 90))}))
    return out


def k_plate(p, c):
    """assiette : aile en croix, filet bleu peint sur le dessus, fond creusé ; `contenu` : vide (défaut), gateau, pain, fruits"""
    col = _col(c, (240, 238, 232)); out = [C((0, .006, 0), (.24, .012, .16), col), C((0, .006, 0), (.16, .012, .24), col), C((0, .006, 0), (.21, .012, .21), col)]
    out.append(B((-.1, .012, -.1), (.2, .001, .2), col, tex={'+y': T.flat(T.plate_top(32, col, _col(_g(p, 'filet'), (60, 90, 160))))}))
    cont = _g(p, 'contenu', default='vide')
    if cont == 'gateau': out += [C((0, .03, 0), (.08, .035, .06), (120, 70, 40)), C((0, .049, 0), (.08, .004, .06), (240, 230, 220)), C((.015, .055, 0), (.015, .01, .015), (200, 30, 40))]
    elif cont == 'pain': out += [C((-.02, .024, 0), (.1, .024, .06), (210, 160, 90)), C((-.02, .037, 0), (.096, .003, .056), (240, 220, 180))]
    elif cont == 'fruits': out += [C((-.03, .03, -.02), (.05, .05, .05), (220, 40, 40)), C((.03, .028, .02), (.045, .045, .045), (240, 190, 40)), C((.0, .027, .04), (.04, .04, .04), (110, 180, 60))]
    return out


def k_cutlery(p, c):
    """couverts posés à plat : fourchette (quatre dents) à gauche, couteau (lame + manche) et cuillère à droite ; `ecart` : place d'une assiette entre les deux"""
    m = _col(c, METAL); hd = _col(_g(p, 'manche'), m); e = float(_g(p, 'ecart', default=.17))
    out = []
    x = -e                                                                                  # fourchette, dents vers le fond (+z)
    out += [C((x, .003, -.04), (.012, .005, .1), hd, mat=M_METAL), C((x, .003, .025), (.016, .004, .03), m, mat=M_METAL), C((x, .003, .03), (.024, .004, .012), m, mat=M_METAL)]
    for i in range(4): out.append(C((x - .0095 + i * .0063, .003, .055), (.003, .003, .036), m, mat=M_METAL))
    x = e                                                                                   # couteau
    out += [C((x, .004, -.05), (.014, .007, .085), hd if hd != m else (60, 40, 30), mat=M_WOODV if hd == m else M_METAL), C((x, .002, .05), (.016, .003, .115), _sh(m, 1.05), mat=M_METAL), C((x - .004, .0025, .1), (.008, .003, .01), _sh(m, 1.05), mat=M_METAL)]
    x = e + .035                                                                            # cuillère
    out += [C((x, .003, -.035), (.011, .005, .11), hd, mat=M_METAL), C((x, .003, .045), (.03, .006, .045), m, mat=M_METAL), C((x, .006, .045), (.02, .002, .032), _sh(m, .8), mat=M_METAL)]
    return out


def k_couvert(p, c):
    """une place à table : assiette, couverts, verre à pied, serviette pliée"""
    out = k_plate(dict(p), None) + k_cutlery(dict(p, ecart=.155), None)
    out += [B((-.24, 0, -.07), (.06, .008, .12), _col(_g(p, 'serviette'), (180, 40, 50)), mat=M_FABRIC)]
    g = k_glass({'modele': 'pied', 'contenu': _g(p, 'contenu_verre', default='vin')}, None)
    for b in g: b.lo = b.lo + np.array([.16, 0, .16], np.float32); b.hi = b.hi + np.array([.16, 0, .16], np.float32)
    return out + g


def k_book(p, c):
    """livre : fermé couché (défaut ; couverture avec titre et auteur, dos titré, tranche de pages, signet) ; `ouvert` (deux pages lisibles) ; `debout` (sur une étagère, dos vers l'avant)"""
    col = _col(c, (120, 30, 36)); titre = str(_g(p, 'titre', 'title', default='LE SILENCE')); aut = str(_g(p, 'auteur', default='M. ARNAUD'))
    W_, H_, D_ = .15, .03, .22
    if _g(p, 'ouvert', 'open', default=False):
        pg = T.open_pages(T.lines(_g(p, 'texte', 'text')))
        out = [B((-W_ - .005, 0, -D_ / 2 - .005), (2 * W_ + .01, .004, D_ + .01), col)]
        out += [B((-W_, .004, -D_ / 2), (W_ - .004, .012, D_), (232, 226, 206)), B((.004, .004, -D_ / 2), (W_ - .004, .012, D_), (232, 226, 206)),
                B((-.012, .004, -D_ / 2), (.024, .008, D_), (210, 200, 176))]
        Wt = pg.shape[1] // 2
        out.append(B((-W_ + .004, .016, -D_ / 2 + .004), (W_ - .012, .001, D_ - .008), (238, 232, 212), tex={'+y': T.flat(np.ascontiguousarray(pg[:, :Wt]))}))
        out.append(B((.008, .016, -D_ / 2 + .004), (W_ - .012, .001, D_ - .008), (238, 232, 212), tex={'+y': T.flat(np.ascontiguousarray(pg[:, Wt:]))}))
        out.append(C((.0, .018, D_ / 2 - .03), (.006, .002, .07), (190, 30, 40)))
        return out
    if _g(p, 'debout', default=False):
        return [B((-H_ / 2, 0, -D_ / 2 + .03), (H_, D_ * .95, .15), (232, 226, 206), tex={'+y': T.page_edge(16, 30)}),
                B((-H_ / 2 - .002, 0, -D_ / 2 + .02), (H_ + .004, D_, .006), col, tex={'-z': T.book_spine(titre, col)}),
                B((-H_ / 2 - .004, 0, -D_ / 2 + .02), (.004, D_, .16), col), B((H_ / 2, 0, -D_ / 2 + .02), (.004, D_, .16), col)]
    out = [B((-W_ / 2, 0, -D_ / 2), (W_, .004, D_), col),
           B((-W_ / 2 + .004, .004, -D_ / 2 + .003), (W_ - .006, H_ - .008, D_ - .006), (232, 226, 206), tex={'-z': T.page_edge(40, 6), '+x': T.page_edge(40, 6), '+z': T.page_edge(40, 6)}),
           B((-W_ / 2, H_ - .004, -D_ / 2), (W_, .004, D_), col, tex={'+y': T.flat(T.book_cover(titre, aut, col))}),
           B((-W_ / 2 - .005, 0, -D_ / 2), (.006, H_, D_), _sh(col, .85), tex={'-x': np.ascontiguousarray(np.rot90(T.book_spine(titre, col), 1))}),
           C((.03, .015, D_ / 2 + .02), (.006, .002, .045), (190, 30, 40))]
    return out


def k_notebook(p, c):
    """carnet à spirale : couverture, élastique, anneaux sur le haut ; `ouvert` (défaut) : page lignée écrite à la main (`texte`), stylo à côté"""
    col = _col(c, (40, 44, 60)); W_, D_ = .1, .15
    if _g(p, 'ouvert', 'open', default=True):
        out = [B((-W_ / 2, 0, -D_ / 2), (W_, .003, D_), col), B((-W_ / 2 + .002, .003, -D_ / 2 + .002), (W_ - .004, .008, D_ - .004), (232, 230, 220)),
               B((-W_ / 2 + .003, .011, -D_ / 2 + .004), (W_ - .006, .001, D_ - .012), (240, 238, 228), tex={'+y': T.flat(T.notebook_page(T.lines(_g(p, 'texte', 'text'))))})]
        for i in range(9): out.append(C((-W_ / 2 + .008 + i * .0105, .014, D_ / 2 - .004), (.004, .008, .008), (170, 172, 180), mat=M_METAL))
    else:
        out = [B((-W_ / 2, 0, -D_ / 2), (W_, .012, D_), col, tex={'+y': T.flat(T.notebook_cover(col))}), C((W_ / 2 - .015, .0125, 0), (.006, .001, D_), (20, 20, 22))]
        for i in range(9): out.append(C((-W_ / 2 + .008 + i * .0105, .012, D_ / 2 - .004), (.004, .008, .008), (170, 172, 180), mat=M_METAL))
    if _g(p, 'stylo', 'pen', default=True):
        out += [C((W_ / 2 + .02, .005, 0), (.009, .009, .13), (30, 60, 160)), C((W_ / 2 + .02, .005, .07), (.007, .007, .015), (220, 220, 226), mat=M_METAL), C((W_ / 2 + .024, .009, .045), (.002, .002, .03), METAL, mat=M_METAL)]
    return out


def k_paper(p, c):
    """feuille A4 imprimée lisible (`texte`, `titre`, `entete`) : à plat (défaut, lue depuis l'avant), `mur: true` (affichée, verticale, à `hauteur`), ou `pile` de feuilles"""
    pap = _col(c, (238, 236, 228))
    img = T.paper(T.lines(_g(p, 'texte', 'text'), ('RAPPORT DE NUIT', '', '02:13 APPEL CH 313', '02:14 LIGNE COUPEE', '02:16 PERSONNE', '', 'VU PAR : M. R.')),
                  str(_g(p, 'titre', 'title', default='')), entete=bool(_g(p, 'entete', default=True)), pli=bool(_g(p, 'pli', default=False)), papier=pap, surligne=str(_g(p, 'surligne', default='')))
    if _g(p, 'mur', 'wall', default=False):
        y = float(_g(p, 'hauteur', default=1.3))
        return [B((-.105, y, -.003), (.21, .297, .003), pap, tex={'-z': img}, texemis=float(_g(p, 'lueur', default=.1))), C((0, y + .285, -.005), (.012, .012, .004), (200, 40, 40))]
    out = []
    if _g(p, 'pile', default=False):
        for i in range(3): out.append(B((-.103 + .004 * i, .002 * i, -.146 - .003 * i), (.21, .002, .297), _sh(pap, .96)))
    y = .006 if out else 0.
    out.append(B((-.105, y, -.1485), (.21, .002, .297), pap, tex={'+y': T.flat(img)}, texemis=float(_g(p, 'lueur', default=.1))))
    return out


def k_keys(p, c):
    """trousseau posé : anneau, trois clés (laiton, acier, petite), porte-clés d'hôtel numéroté (`etiquette`, défaut 313) ou en cuir"""
    br = _col(c, BRASS); out = [C((0, .002, -.017), (.03, .004, .004), METAL, mat=M_METAL), C((0, .002, .017), (.03, .004, .004), METAL, mat=M_METAL),
                               C((-.017, .002, 0), (.004, .004, .03), METAL, mat=M_METAL), C((.017, .002, 0), (.004, .004, .03), METAL, mat=M_METAL)]
    for (dx, dz, col, L) in ((.03, .01, br, .055), (.02, .03, METAL, .05), (-.015, .035, (150, 152, 160), .035)):
        ang = math.atan2(dz, dx); ux, uz = math.cos(ang), math.sin(ang)
        out.append(C((dx * .9, .003, dz * .9), (.022, .005, .022), col, mat=M_METAL))
        out += line((dx * .9 + ux * .012, .003, dz * .9 + uz * .012), (dx * .9 + ux * L, .003, dz * .9 + uz * L), .008, col, mat=M_METAL)
        for t in (.5, .7, .85): out.append(C((dx * .9 + ux * L * t - uz * .006, .003, dz * .9 + uz * L * t + ux * .006), (.006, .004, .006), col, mat=M_METAL))
    tg = _g(p, 'etiquette', 'tag', default='313')
    if tg:
        out += [C((-.02, .003, -.02), (.008, .004, .008), METAL, mat=M_METAL), B((-.075, 0, -.06), (.05, .006, .035), (190, 50, 36), tex={'+y': T.flat(T.tag(str(tg)))})]
    else:
        out.append(B((-.06, 0, -.045), (.035, .008, .02), (110, 60, 36), mat=M_FABRIC))
    return out


def k_desk_lamp(p, c):
    """lampe de bureau : `modele` banquier (défaut : socle et tige en laiton, abat-jour de verre vert, chaînette) ou articulee (bras à ressort, tête conique)"""
    on = float(_g(p, 'allumee', 'on', default=1.) or 0.)
    if _g(p, 'modele', default='banquier') == 'articulee':
        col = _col(c, (56, 92, 132))
        out = [C((0, .012, 0), (.18, .024, .16), _sh(col, .8), mat=M_METAL), C((0, .03, .02), (.04, .02, .04), (40, 40, 44), mat=M_METAL)]
        out += line((0, .04, .02), (0, .3, .06), .022, col, mat=M_METAL) + line((0, .3, .06), (0, .36, -.16), .02, col, mat=M_METAL)
        out += line((.014, .06, .03), (.014, .28, .065), .006, (190, 190, 196), mat=M_METAL)
        out += [C((0, .3, .06), (.035, .03, .03), (40, 40, 44), mat=M_METAL),
                C((0, .335, -.2), (.13, .05, .12), col, mat=M_METAL), C((0, .3, -.21), (.17, .03, .16), col, mat=M_METAL), C((0, .284, -.21), (.13, .004, .12), (255, 236, 186), emis=1.8 * on, cast=False)]
        return out
    br = BRASS; sh = _col(c, (24, 104, 58))
    out = [C((0, .01, 0), (.2, .02, .13), br, mat=M_METAL, refl=.2), C((0, .025, 0), (.16, .01, .1), _sh(br, .9), mat=M_METAL), C((0, .15, .02), (.018, .24, .018), br, mat=M_METAL)]
    out += [C((0, .262, -.01), (.28, .02, .1), br, mat=M_METAL),
            C((0, .285, -.012), (.27, .03, .11), sh, refl=.25), C((0, .305, -.012), (.25, .02, .08), sh, refl=.25), C((0, .318, -.012), (.2, .01, .05), _sh(sh, 1.2), refl=.25),
            C((0, .253, -.012), (.24, .004, .09), (255, 238, 186), emis=1.8 * on, cast=False)]
    out += [C((.09, .23 - .012 * i, -.06), (.004, .006, .004), br, mat=M_METAL) for i in range(5)] + [C((.09, .17, -.06), (.008, .012, .008), br, mat=M_METAL)]
    return out


def k_bedside_lamp(p, c):
    """lampe de chevet : pied en céramique galbé (quatre étages), bague en laiton, abat-jour de tissu évasé (trois étages) éclairé de l'intérieur, interrupteur sur le fil"""
    base = _col(c, (180, 90, 70)); shade = _col(_g(p, 'abat_jour', 'shade'), (236, 216, 176)); on = float(_g(p, 'allumee', 'on', default=1.) or 0.)
    out = [C((0, .01, 0), (.1, .02, .1), _sh(base, .8)), C((0, .05, 0), (.12, .06, .12), base, refl=.15), C((0, .1, 0), (.1, .04, .1), base, refl=.15), C((0, .135, 0), (.06, .03, .06), base, refl=.15),
           C((0, .16, 0), (.024, .02, .024), BRASS, mat=M_METAL), C((0, .2, 0), (.012, .06, .012), BRASS, mat=M_METAL)]
    out += [C((0, .215, 0), (.26, .04, .26), shade, mat=M_FABRIC), C((0, .255, 0), (.22, .04, .22), shade, mat=M_FABRIC), C((0, .29, 0), (.18, .03, .18), shade, mat=M_FABRIC),
            C((0, .195, 0), (.22, .004, .22), (255, 226, 170), emis=1.4 * on, cast=False), C((0, .306, 0), (.14, .003, .14), (255, 236, 196), emis=.8 * on, cast=False)]
    out += line((0, .02, .05), (0, .006, .14), .006, (240, 240, 236)) + [C((0, .008, .1), (.016, .01, .03), (240, 240, 236))]
    return out


def k_nightstand(p, c):
    """table de chevet : caisson, tiroir avec bouton, plateau débordant, pieds ; lampe de chevet et un livre posés dessus (remplace `nightstand`)"""
    wood = _col(c, (90, 66, 46))
    out = [B((-.22, .06, -.2), (.44, .44, .4), wood, mat=M_WOODV), B((-.235, .5, -.215), (.47, .025, .43), _sh(wood, 1.1), mat=M_WOODV),
           B((-.2, .3, -.206), (.4, .17, .008), _sh(wood, .9), mat=M_WOODV), C((0, .385, -.212), (.03, .02, .012), BRASS, mat=M_METAL),
           B((-.2, .08, -.206), (.4, .19, .008), _sh(wood, .85), mat=M_WOODV)]
    out += [B((x, 0, z), (.035, .06, .035), _sh(wood, .7), mat=M_WOODV) for x in (-.21, .175) for z in (-.19, .155)]
    for b in k_bedside_lamp(p, _g(p, 'lampe')): b.lo = b.lo + np.array([.04, .525, .03], np.float32); b.hi = b.hi + np.array([.04, .525, .03], np.float32); out.append(b)
    if _g(p, 'livre', default=True):
        for b in k_book({'titre': 'NUIT'}, (40, 60, 110)): b.lo = b.lo + np.array([-.1, .525, -.07], np.float32); b.hi = b.hi + np.array([-.1, .525, -.07], np.float32); out.append(b)
    return out


def k_laptop(p, c):
    """ordinateur portable ouvert : coque alu, clavier et pavé tactile peints, charnière, écran incliné en quatre bandes (contenu `ecran`), logo au dos"""
    alu = _col(c, (176, 178, 186)); on = _g(p, 'ecran', 'screen', default='bureau') not in ('noir', 'off', False)
    out = [B((-.17, 0, -.12), (.34, .018, .24), alu, mat=M_METAL), B((-.168, .018, -.118), (.336, .001, .236), alu, tex={'+y': T.flat(T.laptop_deck())}),
           C((0, .022, .118), (.3, .01, .012), _sh(alu, .7), mat=M_METAL)]
    scr = _computer_img(p, 'bureau')
    out += bands(-.165, .165, .028, .112, .126, .21, scr, (16, 18, 24), 1, '-z', (0., 0.), texemis=.9 if on else 0., cast=False)      # une seule plaque : les marches d'un écran penché rayaient le texte (planche)
    out.append(B((-.17, .025, .126), (.34, .214, .006), alu, mat=M_METAL))                 # dos de l'écran (coque), logo dessus
    out.append(C((0, .135, .17), (.03, .03, .002), (230, 232, 240), emis=.3 * float(on), cast=False))
    out += [B((-.17, .232, .124), (.34, .008, .012), alu, mat=M_METAL)]
    return out


def _computer_img(p, default='bureau'):
    mode = _g(p, 'ecran', 'screen', default=default)
    tx = _g(p, 'texte', 'text', 'lignes')
    if isinstance(mode, (list, tuple)): tx, mode = mode, 'lignes'
    if mode in (False, 'off'): mode = 'noir'
    if mode not in ('bureau', 'texte', 'mail', 'appel', 'noir', 'lignes'): mode = 'lignes' if tx else default
    return T.computer_screen(mode, T.lines(tx), str(_g(p, 'titre', 'title', default='')), 64, 40, T.hhmm(_g(p, 'heure', 'time'), '02:13'))


def k_monitor(p, c):
    """écran d'ordinateur : pied, colonne, dalle à bordure, écran lisible (`ecran`, `texte`, `titre`), voyant ; `clavier` (défaut) : clavier et souris devant"""
    col = _col(c, (40, 40, 44)); on = _g(p, 'ecran', 'screen', default='bureau') not in ('noir', 'off', False)
    out = [C((0, .006, .03), (.22, .012, .16), col, mat=M_METAL), C((0, .11, .07), (.05, .2, .03), col, mat=M_METAL),
           B((-.27, .14, .04), (.54, .34, .035), col, mat=M_METAL), C((0, .31, .075), (.14, .2, .02), _sh(col, .8), mat=M_METAL)]
    out.append(B((-.25, .16, .038), (.5, .3, .002), (10, 14, 20), tex={'-z': _computer_img(p)}, texemis=.85 if on else 0., cast=False))
    out.append(C((.24, .147, .037), (.008, .005, .003), (80, 220, 120) if on else (40, 60, 40), emis=2. if on else 0., cast=False))
    if _g(p, 'clavier', 'keyboard', default=True):
        out += [B((-.2, 0, -.2), (.4, .015, .14), (36, 36, 40)), B((-.195, .015, -.195), (.39, .001, .13), (36, 36, 40), tex={'+y': T.flat(T.keyboard_top())})]
        out += [C((.29, .012, -.13), (.055, .024, .09), (40, 40, 46)), C((.29, .025, -.15), (.003, .002, .04), (90, 90, 100))]
        out += line((.29, .006, -.085), (.2, .006, .02), .005, (30, 30, 34))
    return out


def k_computer(p, c):
    """poste de travail (remplace `computer`) : bureau à pieds, écran et clavier, unité centrale sous le plateau (voyant), mug, papiers"""
    top = _col(c, (120, 90, 60)); out = [B((-.7, .74, -.35), (1.4, .05, .7), top, mat=M_WOODV)] + [B((x, 0, z), (.05, .74, .05), (60, 44, 30)) for x in (-.65, .6) for z in (-.3, .25)]
    for b in k_monitor(dict(p, clavier=True), None): b.lo = b.lo + np.array([0, .79, .05], np.float32); b.hi = b.hi + np.array([0, .79, .05], np.float32); out.append(b)
    out += [B((.35, 0, -.2), (.2, .45, .45), (44, 44, 50), mat=M_METAL), C((.45, .4, -.205), (.01, .01, .004), (80, 220, 120), emis=2., cast=False), C((.45, .34, -.205), (.12, .012, .004), (20, 20, 22))]
    for b in k_mug({'texte': 'CAFE'}, (180, 60, 50)): b.lo = b.lo + np.array([-.5, .79, -.1], np.float32); b.hi = b.hi + np.array([-.5, .79, -.1], np.float32); out.append(b)
    for b in k_paper({'pile': True, 'texte': _g(p, 'papier')}, None): b.lo = b.lo + np.array([-.42, .79, .12], np.float32); b.hi = b.hi + np.array([-.42, .79, .12], np.float32); out.append(b)
    return out


def k_tv(p, c):
    """télévision à écran plat sur meuble bas : meuble à deux portes et boutons, pied, cadre, écran (`ecran` : neige, mire, journal, film, noir, `texte`), voyant de veille, télécommande"""
    cab = _col(c, (60, 44, 30)); mode = _tv_mode(p); W_ = float(_g(p, 'largeur', default=1.0))
    out = [B((-.6, 0, -.25), (1.2, .45, .5), cab, mat=M_WOODV), B((-.6, .45, -.255), (1.2, .02, .51), _sh(cab, 1.15), mat=M_WOODV),
           B((-.58, .05, -.256), (.575, .36, .006), _sh(cab, .9), mat=M_WOODV), B((.005, .05, -.256), (.575, .36, .006), _sh(cab, .9), mat=M_WOODV),
           C((-.03, .23, -.262), (.02, .05, .008), BRASS, mat=M_METAL), C((.03, .23, -.262), (.02, .05, .008), BRASS, mat=M_METAL)]
    out += [B((-.15, .47, -.08), (.3, .015, .16), (30, 30, 34), mat=M_METAL), B((-.03, .485, -.01), (.06, .06, .03), (30, 30, 34), mat=M_METAL)]
    h = W_ * .58
    out += [B((-W_ / 2, .53, -.03), (W_, h, .045), (18, 18, 22), mat=M_METAL)]
    out.append(B((-W_ / 2 + .02, .55, -.032), (W_ - .04, h - .04, .002), (20, 30, 50), tex={'-z': T.tv_screen(mode, T.lines(_g(p, 'texte', 'text')))}, texemis=0. if mode == 'noir' else .9, cast=False))
    out.append(C((W_ / 2 - .04, .54, -.034), (.008, .005, .002), (255, 40, 30) if mode == 'noir' else (60, 200, 90), emis=2.2, cast=False))
    out += [C((.38, .47, -.12), (.05, .012, .15), (26, 26, 30)), C((.38, .477, -.17), (.012, .002, .012), (200, 40, 40), emis=.5)] + [C((.37 + .01 * (i % 2), .477, -.14 + .012 * (i // 2)), (.006, .002, .006), (120, 120, 126)) for i in range(6)]
    return out


def _tv_mode(p):
    on = _g(p, 'on', 'allumee', default=1)
    m = _g(p, 'ecran', 'screen', default='neige' if on else 'noir')
    if isinstance(m, (list, tuple)): return 'lignes'
    if not on or m in (False, 'off'): return 'noir'
    return m if m in ('neige', 'mire', 'journal', 'film', 'noir', 'lignes') else 'neige'


def k_tv_crt(p, c):
    """vieux téléviseur à tube : caisse en bois sur pieds, écran bombé (cadre en gradins), boutons de chaîne, grille de haut-parleur, antenne en « oreilles de lapin »"""
    wood = _col(c, (96, 64, 40)); mode = _tv_mode(p)
    out = [B((-.36, .12, -.3), (.72, .52, .52), wood, mat=M_WOODV)] + [B((x, 0, z), (.035, .12, .035), (40, 30, 22)) for x in (-.32, .29) for z in (-.26, .17)]
    out += [B((-.32, .17, -.305), (.46, .42, .006), (30, 28, 26)), B((-.305, .185, -.31), (.43, .39, .006), (40, 38, 36))]
    out.append(B((-.29, .2, -.316), (.4, .36, .006), (30, 40, 50), tex={'-z': T.tv_screen(mode, T.lines(_g(p, 'texte', 'text')), 64, 52)}, texemis=0. if mode == 'noir' else .95, refl=.15, cast=False))
    out += [B((.16, .2, -.305), (.16, .36, .006), (40, 36, 30), tex={'-z': T.grille(16, 36, (60, 50, 40))}),
            C((.24, .5, -.31), (.05, .05, .02), (200, 196, 186)), C((.24, .43, -.31), (.04, .04, .02), (200, 196, 186)), C((.24, .5, -.322), (.01, .03, .004), (60, 60, 60))]
    out += [C((0, .655, 0), (.12, .03, .08), (40, 40, 44), mat=M_METAL)] + line((-.03, .67, 0), (-.18, .98, .05), .012, METAL, mat=M_METAL) + line((.03, .67, 0), (.2, .95, -.04), .012, METAL, mat=M_METAL)
    return out


def k_radio(p, c):
    """radio : `modele` ancienne (défaut : caisse en bois, toile de haut-parleur, cadran de fréquences lumineux, deux boutons, touches) ou reveil (radio-réveil, heure LED `heure`)"""
    on = bool(_g(p, 'allumee', 'on', default=True))
    if _g(p, 'modele', default='ancienne') == 'reveil':
        col = _col(c, (30, 30, 34))
        out = [B((-.11, 0, -.06), (.22, .07, .12), col), B((-.1, .07, -.05), (.2, .012, .1), _sh(col, 1.3))]
        out.append(B((-.07, .012, -.062), (.1, .045, .002), (12, 8, 8), tex={'-z': T.led_clock(T.hhmm(_g(p, 'heure', 'time'), '02:13'), True)}, texemis=1.2, cast=False))
        out += [B((.04, .012, -.062), (.06, .045, .002), col, tex={'-z': T.grille(12, 10, col)})] + [C((-.06 + i * .04, .084, 0), (.03, .006, .018), (80, 80, 86)) for i in range(4)]
        return out
    wood = _col(c, (110, 70, 40))
    out = [B((-.2, .02, -.09), (.4, .24, .18), wood, mat=M_WOODV), B((-.18, .26, -.08), (.36, .03, .16), wood, mat=M_WOODV), B((-.2, .0, -.09), (.4, .02, .18), _sh(wood, .6))]
    out.append(B((-.19, .03, -.092), (.38, .22, .002), wood, tex={'-z': T.radio_face(on)}, texemis=.25 if on else 0.))
    out += [C((.05, .06, -.1), (.04, .04, .02), (226, 214, 180)), C((.15, .06, -.1), (.04, .04, .02), (226, 214, 180)), C((.05, .06, -.111), (.006, .025, .004), (60, 50, 40)), C((.15, .06, -.111), (.006, .025, .004), (60, 50, 40))]
    out += [C((-.12 + i * .05, .3, -.03), (.035, .015, .04), (236, 230, 210)) for i in range(5)]
    return out


def k_clock(p, c):
    """horloge à l'heure `heure` : `modele` murale (défaut : boîtier rond en gradins, cadran découpé dans les mêmes gradins, aiguilles, trotteuse, `hauteur`),
    led (afficheur à sept segments), reveil (réveil à deux cloches posé)"""
    hh = T.hhmm(_g(p, 'heure', 'time'), '10:10'); mod = _g(p, 'modele', default='murale')
    if mod == 'led':
        y = float(_g(p, 'hauteur', default=2.1)); on = bool(_g(p, 'allumee', 'on', default=True))
        return [B((-.17, y - .07, -.05), (.34, .14, .05), (16, 14, 14), mat=M_METAL), B((-.155, y - .058, -.052), (.31, .116, .002), (12, 8, 8), tex={'-z': T.led_clock(hh, on)}, texemis=1.3 if on else 0., cast=False)]
    if mod == 'reveil':
        rim = _col(c, (190, 40, 40)); S = .11; y0 = .02
        out = _disk(0, y0 + S / 2, -.0, S, .045, rim, T.clock_face(hh, 32, rim, (240, 236, 224), (30, 28, 26)), n=7)
        out += [C((-.035, y0 + S + .012, 0), (.04, .025, .03), BRASS, mat=M_METAL), C((.035, y0 + S + .012, 0), (.04, .025, .03), BRASS, mat=M_METAL), C((0, y0 + S + .008, 0), (.012, .02, .012), BRASS, mat=M_METAL),
                C((-.035, y0 - .01, 0), (.012, .02, .012), BRASS, mat=M_METAL), C((.035, y0 - .01, 0), (.012, .02, .012), BRASS, mat=M_METAL)]
        out += line((-.03, y0 + S + .03, 0), (.03, y0 + S + .03, 0), .008, BRASS, mat=M_METAL)
        for b in out: b.lo = b.lo + np.array([0, .01, 0], np.float32); b.hi = b.hi + np.array([0, .01, 0], np.float32)
        return out
    y = float(_g(p, 'hauteur', 'at_y', default=2.0)); S = float(_g(p, 'taille', default=.34)); rim = _col(c, (46, 42, 40))
    out = _disk(0, y, 0., S, .05, rim, T.clock_face(hh, 40, rim, (236, 232, 218), (30, 28, 26)), n=9)
    out.append(C((0, y, -.056), (.012, .012, .008), (30, 28, 26)))
    return out


def _disk(x, yc, z, S, depth, col, img, n=9, glass=True):
    """disque vertical (face -z) en n gradins horizontaux : chaque gradin porte la tranche de l'image qui lui revient ; z = la face arrière"""
    out = []; Hs, Ws = img.shape[:2]
    for i in range(n):
        y0 = -S / 2 + S * i / n; y1 = -S / 2 + S * (i + 1) / n; ym = (y0 + y1) / 2
        hw = math.sqrt(max(0., (S / 2) ** 2 - ym ** 2)) * 1.04
        hw = max(hw, S * .18)
        r0 = int(round(Hs * (1 - (i + 1) / n))); r1 = int(round(Hs * (1 - i / n)))
        c0 = int(round(Ws * (.5 - hw / S))); c1 = int(round(Ws * (.5 + hw / S)))
        sl = np.ascontiguousarray(img[r0:max(r1, r0 + 1), max(0, c0):min(Ws, max(c1, c0 + 1))])
        out.append(B((x - hw, yc + y0, z - depth), (2 * hw, y1 - y0, depth), col, tex={'-z': sl}, refl=.12 if glass else 0., mat=M_METAL))
    return out


def k_crowbar(p, c):
    """pied-de-biche couché : barre hexagonale peinte (éclats de peinture), col de cygne en gradins, pied fendu, biseau à l'autre bout"""
    col = _col(c, (150, 26, 24)); st = (80, 82, 88); L = .76
    out = [C((0, .014, 0), (L - .12, .026, .026), col, mat=M_METAL)]
    for i, (dx, dy) in enumerate(((.33, .02), (.36, .035), (.385, .055), (.395, .078), (.385, .098))):
        out.append(C((dx, dy, 0), (.03, .028, .026), col, mat=M_METAL))
    out += [C((.36, .11, .007), (.04, .012, .009), st, mat=M_METAL), C((.36, .11, -.007), (.04, .012, .009), st, mat=M_METAL), C((.338, .106, 0), (.012, .01, .004), (20, 20, 22))]
    out += [C((-.33, .012, 0), (.06, .02, .028), col, mat=M_METAL), C((-.375, .01, 0), (.04, .012, .034), st, mat=M_METAL), C((-.4, .007, 0), (.02, .006, .036), st, mat=M_METAL)]
    for x in (-.2, -.05, .12, .24): out.append(C((x, .0275, .004), (.018, .002, .012), st, mat=M_METAL))
    return out


def k_flashlight(p, c):
    """lampe torche couchée : corps moleté, tête évasée, verre, bouton, dragonne ; `allumee` : faisceau visible (cône tramé) devant (-z)"""
    col = _col(c, (40, 40, 46)); on = bool(_g(p, 'allumee', 'on', default=False)); out = []
    out += [C((0, .02, .02), (.032, .032, .15), col, mat=M_METAL), C((0, .02, .02), (.026, .036, .15), col, mat=M_METAL)]
    for z in (.0, .03, .06): out.append(C((0, .02, z), (.036, .036, .012), _sh(col, .7), mat=M_METAL))
    out += [C((0, .025, -.065), (.05, .05, .04), _sh(col, 1.2), mat=M_METAL), C((0, .025, -.09), (.052, .052, .01), METAL, mat=M_METAL),
            C((0, .025, -.096), (.04, .04, .003), (255, 248, 220) if on else (150, 160, 170), emis=3. if on else 0., refl=.3, cast=False),
            C((0, .04, -.02), (.01, .008, .014), (200, 40, 40)), C((0, .02, .1), (.03, .03, .01), _sh(col, .8), mat=M_METAL)]
    out += line((0, .02, .105), (.02, .004, .17), .004, (60, 60, 70)) + line((.02, .004, .17), (-.02, .004, .17), .004, (60, 60, 70))
    if on:
        for i in range(5):
            w = .05 + i * .07; out.append(C((0, .025 + i * .004, -.13 - i * .12), (w, w * .7, .11), (255, 246, 210), emis=.4 - .06 * i, dissolve=.7 + .05 * i, cast=False))
    return out


def k_candle(p, c):
    """bougie : `modele` pilier (défaut : cire en croix, coulures, flaque de cire, mèche, flamme à deux couleurs, bougeoir à anse) ou chandelier (bougie fine sur haut bougeoir)"""
    wax = _col(c, (236, 226, 196)); lit = bool(_g(p, 'allumee', 'on', default=True)); out = []
    if _g(p, 'modele', default='pilier') == 'chandelier':
        out += [C((0, .008, 0), (.1, .016, .1), BRASS, mat=M_METAL, refl=.2), C((0, .03, 0), (.04, .03, .04), BRASS, mat=M_METAL), C((0, .11, 0), (.02, .13, .02), BRASS, mat=M_METAL),
                C((0, .14, 0), (.032, .012, .032), BRASS, mat=M_METAL), C((0, .18, 0), (.06, .008, .06), BRASS, mat=M_METAL)]
        out += rnd2(0, .184, 0, .022, .16, .022, wax) + [C((.012, .3, 0), (.006, .03, .006), wax)]
        top = .344
    else:
        if _g(p, 'bougeoir', default=True):
            out += [C((0, .006, 0), (.11, .012, .11), BRASS, mat=M_METAL, refl=.2), C((0, .006, 0), (.13, .012, .08), BRASS, mat=M_METAL), C((0, .016, 0), (.08, .008, .08), BRASS, mat=M_METAL)]
            out += [C((.08, .02, 0), (.012, .03, .012), BRASS, mat=M_METAL), C((.072, .036, 0), (.03, .008, .012), BRASS, mat=M_METAL)]
        y0 = .02 if out else 0.; h = float(_g(p, 'hauteur', default=.11))
        out += rnd(0, y0, 0, .055, h, .055, wax) + [C((0, y0 + .003, 0), (.075, .006, .075), _sh(wax, .97))]
        out += [C((.027, y0 + h - .025, .005), (.008, .03, .008), wax), C((-.022, y0 + h - .018, -.016), (.008, .02, .008), wax), C((.008, y0 + h - .035, -.027), (.008, .05, .008), wax)]
        out.append(C((0, y0 + h - .003, 0), (.04, .006, .04), _sh(wax, .9)))
        top = y0 + h
    out.append(C((0, top + .006, 0), (.004, .012, .004), (30, 24, 20)))
    if lit:
        out += [C((0, top + .02, 0), (.01, .02, .01), (255, 240, 180), emis=2.8, cast=False), C((0, top + .026, 0), (.016, .032, .016), (255, 150, 50), emis=1.6, dissolve=.45, cast=False)]
    return out


def k_photo_frame(p, c):
    """cadre photo : moulure à deux gradins, passe-partout, photo (`photo` : portrait, couple, famille, enfant, paysage, maison ; `raye` : visage barré), reflet ;
    posé avec son chevalet (défaut) ou `mur: true` à `hauteur`"""
    fr = _col(c, (70, 46, 30)); W_, H_ = float(_g(p, 'largeur', default=.18)), float(_g(p, 'haut', default=.23))
    img = T.photo(str(_g(p, 'photo', default='portrait')), int(_g(p, 'seed', default=0)), 24, 30, bool(_g(p, 'raye', default=False)))
    wall = _g(p, 'mur', 'wall', default=False); y = float(_g(p, 'hauteur', 'at_y', default=1.5)) - H_ / 2 if wall else .0
    out = [B((-W_ / 2, y, -.012), (W_, .02, .022), fr, mat=M_WOODV), B((-W_ / 2, y + H_ - .02, -.012), (W_, .02, .022), fr, mat=M_WOODV),
           B((-W_ / 2, y + .02, -.012), (.02, H_ - .04, .022), fr, mat=M_WOODV), B((W_ / 2 - .02, y + .02, -.012), (.02, H_ - .04, .022), fr, mat=M_WOODV),
           B((-W_ / 2 + .02, y + .02, -.006), (W_ - .04, H_ - .04, .006), _sh(fr, 1.3), mat=M_WOODV),
           B((-W_ / 2 + .026, y + .026, -.008), (W_ - .052, H_ - .052, .002), (236, 230, 214)),
           B((-W_ / 2 + .04, y + .04, -.009), (W_ - .08, H_ - .08, .001), (150, 150, 150), tex={'-z': img}, refl=.12)]
    if not wall: out += line((0, y + H_ * .7, .01), (0, .0, .1), .016, _sh(fr, .7))
    return out


def k_plant(p, c):
    """plante en pot : pot en terre cuite évasé avec bord et soucoupe, terreau ; `espece` monstera (défaut), ficus, sansevieria, cactus, fougere ; `taille`"""
    pot = _col(c, (176, 92, 60)); s = float(_g(p, 'taille', 'size', default=1.)); sp = _g(p, 'espece', 'kind', default='monstera')
    g1, g2, g3 = (40, 110, 52), (62, 140, 70), (30, 90, 44)
    out = [C((0, .01 * s, 0), (.34 * s, .02 * s, .34 * s), _sh(pot, .75)), C((0, .08 * s, 0), (.22 * s, .12 * s, .22 * s), pot), C((0, .19 * s, 0), (.26 * s, .1 * s, .26 * s), pot),
           C((0, .255 * s, 0), (.3 * s, .03 * s, .3 * s), _sh(pot, 1.1)), C((0, .265 * s, 0), (.25 * s, .012 * s, .25 * s), (52, 36, 26))]
    y0 = .27 * s
    if sp == 'cactus':
        out += [C((0, y0 + .2 * s, 0), (.1 * s, .4 * s, .1 * s), (70, 140, 80)), C((.08 * s, y0 + .18 * s, 0), (.08 * s, .05 * s, .05 * s), (70, 140, 80)), C((.105 * s, y0 + .26 * s, 0), (.05 * s, .14 * s, .05 * s), (70, 140, 80)),
                C((-.07 * s, y0 + .26 * s, 0), (.06 * s, .04 * s, .05 * s), (70, 140, 80)), C((-.09 * s, y0 + .32 * s, 0), (.045 * s, .1 * s, .045 * s), (70, 140, 80)), C((0, y0 + .41 * s, 0), (.05 * s, .03 * s, .05 * s), (236, 80, 130))]
        for i in range(8): out.append(C(((-.05 + .1 * (i % 2)) * s, y0 + (.06 + .045 * i) * s, -.051 * s), (.006, .006, .004), (240, 236, 210), cast=False))
        return out
    if sp == 'sansevieria':
        for i, (dx, dz, h) in enumerate(((0, 0, .7), (-.06, .03, .55), (.06, -.02, .6), (.03, .06, .45), (-.04, -.05, .5), (.08, .05, .38))):
            out += [C((dx * s, y0 + h * s / 2, dz * s), (.05 * s, h * s, .015 * s), g1 if i % 2 else g2), C((dx * s, y0 + h * s / 2, dz * s - .008 * s), (.054 * s, h * s * .96, .004 * s), (190, 190, 80))]
        return out
    if sp == 'ficus':
        out += [C((0, y0 + .3 * s, 0), (.03 * s, .6 * s, .03 * s), (100, 72, 46)), C((.05 * s, y0 + .45 * s, 0), (.1 * s, .02 * s, .02 * s), (100, 72, 46))]
        rng = np.random.default_rng(int(_g(p, 'seed', default=1)))
        for i in range(16):
            a = rng.uniform(0, 6.283); r = rng.uniform(.04, .2); yy = rng.uniform(.5, .9)
            out.append(C((math.cos(a) * r * s, y0 + yy * s, math.sin(a) * r * s), (.08 * s, .03 * s, .06 * s), [g1, g2, g3][i % 3]))
        return out
    if sp == 'fougere':
        for i in range(7):
            a = i * 6.283 / 7; ux, uz = math.cos(a), math.sin(a)
            for j in range(5):
                r = (.04 + j * .06) * s; yy = y0 + (.05 + .07 * j - .012 * j * j) * s
                out.append(C((ux * r, yy, uz * r), ((.06 if abs(ux) > .5 else .03) * s, .015 * s, (.03 if abs(ux) > .5 else .06) * s), g2 if j % 2 else g1))
        return out
    stems = ((-.06, .02, .55, -.24, .1), (.07, -.03, .62, .26, -.08), (.0, .07, .72, .03, .26), (-.03, -.07, .48, -.1, -.25), (.04, .04, .4, .22, .2))
    for i, (sx, sz, h, lx, lz) in enumerate(stems):
        out += line((sx * s, y0, sz * s), ((sx + lx * .5) * s, y0 + h * s, (sz + lz * .5) * s), .016 * s, g3, n=5)
        cx, cy, cz = (sx + lx * .6) * s, y0 + (h + .04) * s, (sz + lz * .6) * s
        gx, gz = (1 if lx >= 0 else -1), (1 if lz >= 0 else -1)
        out += [C((cx, cy, cz), (.18 * s, .02 * s, .15 * s), g1 if i % 2 else g2), C((cx, cy + .011 * s, cz), (.15 * s, .004 * s, .014 * s), (34, 84, 42)),
                C((cx + gx * .1 * s, cy - .025 * s, cz + gz * .06 * s), (.07 * s, .018 * s, .1 * s), g3 if i % 2 else g1),          # bout de feuille qui retombe
                C((cx - .03 * s, cy + .002 * s, cz + gz * .07 * s), (.03 * s, .022 * s, .02 * s), (30, 30, 26))]                  # découpe de la feuille (monstera)
    return out


def k_bag(p, c):
    """sac : `modele` main (défaut : corps trapèze, rabat, fermoir doré, deux anses, surpiqûre), cabas (sac de courses à longues anses), dos (sac à dos : poche, sangles)"""
    col = _col(c, (120, 60, 40)); mod = _g(p, 'modele', default='main'); dk = _sh(col, .7)
    if mod == 'dos':
        out = [B((-.15, 0, -.08), (.3, .42, .16), col, mat=M_FABRIC), B((-.13, .04, -.11), (.26, .18, .04), dk, mat=M_FABRIC), C((0, .23, -.11), (.2, .008, .006), (200, 200, 206), mat=M_METAL),
               C((0, .43, 0), (.08, .02, .02), dk)] + [B((x, .05, .08), (.04, .34, .02), dk, mat=M_FABRIC) for x in (-.11, .07)]
        return out
    if mod == 'cabas':
        out = [B((-.2, 0, -.07), (.4, .34, .14), col, mat=M_FABRIC), B((-.2, .3, -.072), (.4, .04, .002), dk)]
        for x in (-.12, .12): out += line((x, .33, -.06), (x, .52, -.04), .025, dk, mat=M_FABRIC) + line((x, .52, -.04), (x * .5, .56, -.04), .025, dk, mat=M_FABRIC)
        out += line((-.06, .56, -.04), (.06, .56, -.04), .025, dk, mat=M_FABRIC)
        return out
    out = [B((-.14, 0, -.06), (.28, .12, .12), col), B((-.12, .12, -.055), (.24, .06, .11), col),
           B((-.125, .09, -.064), (.25, .09, .006), dk, tex={'-z': T.stitch(24, 10, dk)}), C((0, .1, -.069), (.03, .022, .005), BRASS, mat=M_METAL, refl=.3)]
    for x in (-.07, .07): out += [C((x, .2, 0), (.016, .04, .016), dk), C((x * .6, .235, 0), (.06, .016, .016), dk)]
    out += [C((-.12, .003, -.05), (.012, .006, .012), BRASS, mat=M_METAL), C((.12, .003, -.05), (.012, .006, .012), BRASS, mat=M_METAL)]
    return out


def k_suitcase(p, c):
    """valise : `modele` rigide (défaut : coque à nervures, coins, poignée télescopique `poignee: sortie`, poignée de transport, quatre roulettes, fermeture, étiquette `etiquette`)
    ou cuir (valise ancienne : deux sangles à boucle, coins en laiton, poignée de cuir, autocollants)"""
    mod = _g(p, 'modele', default='rigide')
    if mod == 'cuir':
        col = _col(c, (110, 66, 40)); out = [B((-.32, 0, -.1), (.64, .44, .2), col, mat=M_CARD), B((-.325, .2, -.105), (.65, .03, .21), _sh(col, .7))]
        for x in (-.18, .18): out += [B((x - .02, 0, -.106), (.04, .44, .212), (60, 36, 22)), C((x, .32, -.11), (.035, .03, .006), BRASS, mat=M_METAL)]
        for x in (-.32, .3):
            for y in (0, .41): out.append(B((x, y, -.104), (.02, .03, .208), BRASS, mat=M_METAL))
        out += [C((0, .46, 0), (.14, .025, .03), (60, 36, 22)), C((-.06, .45, 0), (.015, .03, .02), BRASS), C((.06, .45, 0), (.015, .03, .02), BRASS)]
        out += [B((-.27, .08, -.104), (.08, .06, .002), (230, 200, 80), tex={'-z': T.label('PARIS', '', (230, 200, 80), (40, 40, 90), 16, 12)}), B((.05, .27, -.104), (.07, .05, .002), (190, 60, 50), tex={'-z': T.label('NICE', '', (190, 60, 50), (250, 240, 220), 16, 12)})]
        return out
    col = _col(c, (60, 90, 140)); dk = _sh(col, .7)
    out = [B((-.2, .04, -.12), (.4, .58, .24), col), B((-.2, .04, -.125), (.4, .58, .005), col, tex={'-z': T.ribs(24, 36, col)}),
           B((-.202, .3, -.122), (.404, .015, .244), (30, 30, 34))]
    for x in (-.2, .17):
        for y in (.04, .59): out.append(B((x, y, -.123), (.03, .03, .246), dk))
    for x in (-.16, .16):
        for z in (-.09, .09): out += [C((x, .02, z), (.03, .04, .03), (24, 24, 26)), C((x, .042, z), (.04, .006, .04), (60, 60, 66))]
    out += [C((0, .5, -.125), (.1, .022, .02), (30, 30, 34)), C((-.05, .5, -.12), (.012, .03, .012), (30, 30, 34)), C((.05, .5, -.12), (.012, .03, .012), (30, 30, 34))]
    up = _g(p, 'poignee', default='rentree') == 'sortie'; ht = .42 if up else .03
    out += [C((-.08, .62 + ht / 2, .09), (.016, ht, .016), (150, 152, 160), mat=M_METAL), C((.08, .62 + ht / 2, .09), (.016, ht, .016), (150, 152, 160), mat=M_METAL), C((0, .62 + ht + .012, .09), (.2, .024, .03), (30, 30, 34))]
    et = _g(p, 'etiquette', default='M. ROUX - CH 313')
    if et:
        out += line((.14, .5, -.13), (.16, .4, -.14), .004, (200, 196, 180)) + [B((.12, .3, -.15), (.07, .1, .003), (226, 214, 180), tex={'-z': T.label(str(et).split(' - ')[0], (str(et).split(' - ') + [''])[1], (226, 214, 180), (30, 30, 60), 16, 22)})]
    out.append(B((-.15, .38, -.126), (.08, .08, .002), (240, 190, 60), tex={'-z': T.label('NY', '', (240, 190, 60), (180, 30, 30), 16, 16, False)}))
    return out


KINDS = {'od_phone_rotary': k_phone_rotary, 'od_phone_desk': k_phone_desk, 'od_smartphone': k_smartphone, 'od_switchboard': k_switchboard,
         'od_cup': k_cup, 'od_mug': k_mug, 'od_glass': k_glass, 'od_bottle': k_bottle, 'od_plate': k_plate, 'od_cutlery': k_cutlery, 'od_couvert': k_couvert,
         'od_book': k_book, 'od_notebook': k_notebook, 'od_paper': k_paper, 'od_keys': k_keys, 'od_desk_lamp': k_desk_lamp, 'od_bedside_lamp': k_bedside_lamp,
         'od_nightstand': k_nightstand, 'od_laptop': k_laptop, 'od_monitor': k_monitor, 'od_computer': k_computer, 'od_tv': k_tv, 'od_tv_crt': k_tv_crt,
         'od_radio': k_radio, 'od_clock': k_clock, 'od_crowbar': k_crowbar, 'od_flashlight': k_flashlight, 'od_candle': k_candle, 'od_photo_frame': k_photo_frame,
         'od_plant': k_plant, 'od_bag': k_bag, 'od_suitcase': k_suitcase}

LABELS = {'od_phone_rotary': 'téléphone fixe à cadran', 'od_phone_desk': 'téléphone de bureau à touches', 'od_smartphone': 'smartphone', 'od_switchboard': 'standard téléphonique',
          'od_cup': 'tasse de café', 'od_mug': 'mug', 'od_glass': 'verre', 'od_bottle': 'bouteille', 'od_plate': 'assiette', 'od_cutlery': 'couverts', 'od_couvert': 'place à table',
          'od_book': 'livre', 'od_notebook': 'carnet', 'od_paper': 'feuille imprimée', 'od_keys': 'clés', 'od_desk_lamp': 'lampe de bureau', 'od_bedside_lamp': 'lampe de chevet',
          'od_nightstand': 'table de chevet', 'od_laptop': 'ordinateur portable', 'od_monitor': "écran d'ordinateur", 'od_computer': 'poste de travail', 'od_tv': 'télévision',
          'od_tv_crt': 'téléviseur à tube', 'od_radio': 'radio', 'od_clock': 'horloge', 'od_crowbar': 'pied-de-biche', 'od_flashlight': 'lampe torche', 'od_candle': 'bougie',
          'od_photo_frame': 'cadre photo', 'od_plant': 'plante', 'od_bag': 'sac', 'od_suitcase': 'valise'}

LIGHTS = {   # kind -> [(position locale, couleur, puissance, rayon, scintillement)] (même forme que world.PROP_LIGHTS)
    'od_desk_lamp': [((0, .24, -.02), (1, .86, .6), .8, 2.0, False)], 'od_bedside_lamp': [((0, .2, 0), (1, .82, .56), .9, 2.4, False)],
    'od_nightstand': [((.04, .72, .03), (1, .82, .56), .9, 2.4, False)], 'od_candle': [((0, .2, 0), (1, .62, .3), .6, 2.0, 'soft')],
    'od_tv': [((0, .8, -.6), (.5, .62, .95), .55, 2.2, True)], 'od_tv_crt': [((0, .4, -.6), (.5, .62, .95), .5, 2.0, True)],
    'od_monitor': [((0, .3, -.4), (.55, .7, 1.), .35, 1.4, False)], 'od_laptop': [((0, .15, -.3), (.55, .7, 1.), .3, 1.2, False)],
    'od_computer': [((0, 1.1, -.4), (.5, .7, 1.), .45, 1.6, False)],
}


def prop(kind, p=None, c=None):
    """boîtes PS1 d'un objet détaillé (repère local, face avant vers -z), précédées de leurs deux marqueurs"""
    p = dict(p or {}); fn = KINDS[kind]
    bx = fn(p, c)
    pm = dict(p)
    if c and pm.get('color') is None: pm['color'] = [int(v) for v in c][:3]             # la couleur donnée à part (prop_boxes, hôtel) voyage avec le marqueur jusqu'à VOXEL
    return _markers(kind, pm, len(bx)) + bx


# ================================================================== the objects held in the hand (PS1)
def _faces(f):
    """faces logiques -> clés de face du monde, selon le sens du repère de la main (f = +1 : avant = +z)"""
    return {'front': '+z' if f > 0 else '-z', 'back': '-z' if f > 0 else '+z', 'out': '+x' if f > 0 else '-x', 'in': '-x' if f > 0 else '+x'}


def h_handset(P, F, k, lights, col, cfg):
    """combiné tenu à l'oreille (geste `phone`) : écouteur contre l'oreille, micro devant la bouche, manche en biais dans la main, cordon spiralé qui pend"""
    col = _col(col, (30, 30, 34)); dk = _sh(col, .55); out = []
    ear = (-.112, .165, -.06); mic = (-.118, .0, .085)
    out += [C(P(*ear), (.032, .07, .066), col, **k), C(P(ear[0] - .018, ear[1], ear[2]), (.006, .052, .05), dk, **k)]
    out += [C(P(*mic), (.034, .064, .064), col, **k), C(P(mic[0] - .019, mic[1], mic[2]), (.006, .046, .046), dk, **k)]
    for i in range(4):
        t = (i + .5) / 4; q = (ear[0] + (mic[0] - ear[0]) * t + .012, ear[1] - .03 + (mic[1] + .03 - ear[1] + .03) * t, ear[2] + .03 + (mic[2] - .03 - ear[2] - .03) * t)
        out.append(C(P(*q), (.03, .05, .05), col, **k))
    pts = [P(mic[0], mic[1] - .035, mic[2]), P(-.1, -.15, .1), P(-.08, -.3, .08), P(-.06, -.42, .04)]
    out += coil(pts, dk, k=k)
    return out


def h_smartphone(P, F, k, lights, col, cfg, faces='holder'):
    """smartphone tenu : écran vers celui qui le tient (`od_smartphone`), vers l'extérieur (`od_smartphone_montre`), ou des deux côtés (anciens `phone`, `mobile`)"""
    case = _col(col, (44, 48, 66)); scr = _screen_img(cfg); back = T.phone_back(case); out = []
    c0 = (0, .06, .05)
    tx = {}
    if faces in ('holder', 'both'): tx[F['back']] = scr
    if faces in ('out', 'both'): tx[F['front']] = scr
    if faces == 'holder': tx[F['front']] = back
    if faces == 'out': tx[F['back']] = back
    out.append(C(P(*c0), (.074, .152, .009), case, **k))
    for key_, im in tx.items():
        fw = .0046 if key_ == F['front'] else -.0046
        is_scr = im is scr
        out.append(C(P(c0[0], c0[1], c0[2] + fw), (.066 if is_scr else .072, .14 if is_scr else .15, .001), (20, 24, 40) if is_scr else case, tex={key_: im}, texemis=.9 if is_scr else 0., cast=False, **k))
    out += [C(P(.0385, .09, .05), (.003, .02, .004), _sh(case, .7), **k), C(P(-.0385, .085, .05), (.003, .03, .004), _sh(case, .7), **k)]
    if lights is not None and faces != 'out': lights.append((P(0, .09, -.06), (.55, .62, 1.), .3, .8))
    return out


def h_cup(P, F, k, lights, col, cfg):
    """tasse tenue par l'anse : le corps devant le poing, le café visible, vapeur"""
    col = _col(col, (238, 236, 230)); out = []
    b0 = (-.035, -.01, .075)
    out += rnd(P(*b0)[0], P(*b0)[1], P(*b0)[2], .084, .066, .084, col, k)
    t = P(b0[0], b0[1] + .066, b0[2])
    out += [C(t, (.086, .006, .06), _sh(col, 1.06), **k), C(t, (.06, .006, .086), _sh(col, 1.06), **k), C((t[0], t[1] - .004, t[2]), (.07, .002, .05), (70, 40, 22), **k)]
    out += [C(P(.012, .045, .075), (.03, .01, .014), col, **k), C(P(.025, .028, .075), (.01, .036, .014), col, **k), C(P(.012, .012, .075), (.03, .01, .014), col, **k)]
    if cfg.get('vapeur', True):
        for i in range(4): out.append(C(P(b0[0] + .01 * math.sin(i * 1.7), .09 + .035 * i, b0[2]), (.018, .022, .018), (220, 222, 226), dissolve=.45 + .12 * i, cast=False, **k))
    return out


def h_mug(P, F, k, lights, col, cfg):
    col = _col(col, (60, 120, 150)); out = []
    b0 = (-.045, -.03, .07); q = P(*b0)
    out += rnd(q[0], q[1], q[2], .095, .105, .095, col, k)
    pr = T.mug_print(str(cfg.get('texte', '')), str(cfg.get('motif', 'coeur')), col)
    out.append(C(P(b0[0], b0[1] + .052, b0[2] + .049), (.06, .06, .002), col, tex={F['front']: pr}, **k))
    out.append(C(P(b0[0], b0[1] + .103, b0[2]), (.076, .002, .076), (66, 38, 20), **k))
    out += [C(P(.012, .055, .07), (.03, .016, .02), col, **k), C(P(.025, .023, .07), (.014, .05, .02), col, **k), C(P(.012, -.008, .07), (.03, .016, .02), col, **k)]
    return out


def h_glass(P, F, k, lights, col, cfg, wine=False):
    g = _col(col, (190, 206, 216)); out = []
    if wine:
        b = (0, .02, .06); q = P(*b)
        out += [C(P(0, -.03, .06), (.06, .006, .06), g, refl=.3, **k), C(P(0, .0, .06), (.008, .06, .008), g, refl=.3, **k)]
        out += rnd2(q[0], q[1] + .015, q[2], .06, .03, .06, LIQ.get(cfg.get('contenu', 'vin'), LIQ['vin']), k)
        out += rnd2(q[0], q[1] + .01, q[2], .074, .09, .074, g, k, refl=.35, dissolve=.62, cast=False)
        return out
    q = P(-.02, -.02, .07)
    out += rnd2(q[0], q[1], q[2], .07, .012, .07, g, k, refl=.3) + rnd2(q[0], q[1] + .012, q[2], .062, .06, .062, LIQ.get(cfg.get('contenu', 'eau'), LIQ['eau']), k, dissolve=.25)
    out += rnd2(q[0], q[1] + .012, q[2], .072, .088, .072, g, k, refl=.35, dissolve=.6, cast=False)
    return out


def h_bottle(P, F, k, lights, col, cfg):
    """bouteille tenue par le col : étiquette tournée vers l'avant"""
    mod = cfg.get('modele', 'vin'); g_, liq, t1, t2 = BOTTLES.get(mod, BOTTLES['vin']); glass = _col(col, g_); out = []
    q = P(0, -.24, .05); w = .074
    out += rnd(q[0], q[1], q[2], w, .2, w, glass, k, refl=.35)
    out += rnd2(q[0], q[1] + .2, q[2], w * .78, .025, w * .78, glass, k, refl=.35) + rnd2(q[0], q[1] + .225, q[2], w * .4, .07, w * .4, glass, k, refl=.3)
    out.append(C((q[0], q[1] + .307, q[2]), (w * .45, .03, w * .45), (150, 20, 30), **k))
    out.append(C(P(0, -.15, .05 + w * .5 + .001), (w * .72, .085, .002), (236, 226, 200), tex={F['front']: T.label(str(cfg.get('etiquette', t1)), str(cfg.get('sous', t2)))}, **k))
    return out


def h_book(P, F, k, lights, col, cfg, opened=False):
    col = _col(col, (120, 30, 36)); titre = str(cfg.get('titre', 'LE SILENCE')); aut = str(cfg.get('auteur', 'M. ARNAUD')); out = []
    if opened:                                                                             # livre ouvert face au lecteur, tenu par le bas
        q = P(-.06, .1, .12)
        pg = T.open_pages(T.lines(cfg.get('texte')))
        out += [C(P(-.06, .1, .126), (.31, .22, .008), col, **k), C(P(-.06, .1, .116), (.3, .21, .012), (232, 226, 206), **k), C(P(-.06, .1, .112), (.02, .21, .006), (200, 190, 166), **k)]
        out.append(C(P(-.06, .1, .1095), (.29, .2, .001), (238, 232, 212), tex={F['back']: pg}, **k))
        return out
    q = P(-.03, .08, .07)
    out += [C(q, (.15, .22, .03), col, **k), C((q[0], q[1], q[2]), (.144, .214, .024), (232, 226, 206), **k),
            C(P(-.03, .08, .07 + .016), (.15, .22, .002), col, tex={F['front']: T.book_cover(titre, aut, col)}, **k),
            C(P(-.03, .08, .07 - .016), (.15, .22, .002), _sh(col, .9), **k)]
    return out


def h_notebook(P, F, k, lights, col, cfg):
    col = _col(col, (40, 44, 60)); out = []
    q = P(-.01, .07, .09)
    out += [C(q, (.1, .15, .012), col, **k), C(P(-.01, .07, .09 - .0065), (.094, .144, .001), (240, 238, 228), tex={F['back']: T.notebook_page(T.lines(cfg.get('texte')))}, **k),
            C(P(-.01, .07, .09 + .0065), (.1, .15, .001), col, tex={F['front']: T.notebook_cover(col)}, **k)]
    for i in range(9): out.append(C(P(-.01 - .042 + i * .0105, .147, .09), (.004, .008, .016), (170, 172, 180), **k))
    return out


def h_paper(P, F, k, lights, col, cfg):
    """feuille tenue droite, lisible des deux côtés (comme le journal du standard)"""
    pap = _col(col, (238, 236, 228))
    img = T.paper(T.lines(cfg.get('texte'), ('RAPPORT DE NUIT', '', '02:13 APPEL CH 313', '02:14 LIGNE COUPEE', '02:16 PERSONNE')), str(cfg.get('titre', '')),
                  entete=bool(cfg.get('entete', True)), surligne=str(cfg.get('surligne', '')))
    return [C(P(-.02, .1, .13), (.21, .297, .002), pap, tex={F['front']: img, F['back']: img}, texemis=.12, **k)]


def h_keys(P, F, k, lights, col, cfg):
    """trousseau qui pend des doigts : anneau, clés, porte-clés numéroté"""
    br = _col(col, BRASS); out = [C(P(0, -.05, .05), (.004, .03, .03), METAL, **k)]
    for i, (dx, cc, L) in enumerate(((-.012, br, .06), (.0, METAL, .055), (.014, (150, 152, 160), .04))):
        out += [C(P(dx, -.075, .05), (.02, .02, .006), cc, **k), C(P(dx, -.085 - L / 2, .05), (.008, L, .004), cc, **k), C(P(dx + .006, -.095 - L * .6, .05), (.006, .008, .004), cc, **k)]
    tg = cfg.get('etiquette', '313')
    if tg: out.append(C(P(-.03, -.12, .052), (.035, .05, .006), (190, 50, 36), tex={F['front']: T.tag(str(tg), 14, 18), F['back']: np.ascontiguousarray(T.tag(str(tg), 14, 18)[:, ::-1])}, **k))   # 6/11/2026 : verso retourné, texte lisible des deux côtés
    return out


def h_crowbar(P, F, k, lights, col, cfg):
    """pied-de-biche tenu droit : col de cygne en haut (gradins), pied fendu, biseau en bas, éclats de peinture"""
    col = _col(col, (150, 26, 24)); st = (80, 82, 88); out = [C(P(0, .2, .02), (.028, .6, .028), col, mat=M_METAL, **k)]
    for (dy, df) in ((.52, .03), (.545, .045), (.565, .07), (.575, .095), (.565, .118)):
        out.append(C(P(0, dy, df), (.026, .03, .03), col, mat=M_METAL, **k))
    out += [C(P(.007, .55, .135), (.009, .012, .035), st, mat=M_METAL, **k), C(P(-.007, .55, .135), (.009, .012, .035), st, mat=M_METAL, **k)]
    out += [C(P(0, -.12, .028), (.026, .06, .03), st, mat=M_METAL, **k), C(P(0, -.16, .035), (.02, .03, .034), st, mat=M_METAL, **k)]
    out += [C(P(0, -.03, .02), (.036, .1, .036), (30, 30, 34), **k)]
    for y in (.12, .3, .42): out.append(C(P(.0145, y, .02), (.002, .02, .012), st, **k))
    return out


def h_flashlight(P, F, k, lights, col, cfg):
    """lampe torche tenue, faisceau devant (cône tramé) et lumière qui éclaire loin devant"""
    col = _col(col, (40, 40, 46)); out = [C(P(0, 0, .06), (.034, .034, .15), col, mat=M_METAL, **k)]
    for z in (.03, .06, .09): out.append(C(P(0, 0, z), (.038, .038, .01), _sh(col, .7), **k))
    out += [C(P(0, 0, .15), (.05, .05, .04), _sh(col, 1.2), mat=M_METAL, **k), C(P(0, 0, .172), (.052, .052, .006), METAL, mat=M_METAL, **k),
            C(P(0, 0, .176), (.04, .04, .002), (255, 248, 220), emis=3., cast=False, **k), C(P(0, .02, .08), (.01, .006, .014), (200, 40, 40), **k)]
    if cfg.get('faisceau', True):
        for i in range(5):
            w = .05 + i * .065; out.append(C(P(0, 0, .26 + i * .13), (w, w * .8, .12), (255, 246, 210), emis=.35 - .05 * i, dissolve=.72 + .045 * i, cast=False, **k))
    if lights is not None: lights.append((P(0, 0, 2.5), (1, .95, .82), 2.4 * .45, 3.6 * 1.3))
    return out


def h_candle(P, F, k, lights, col, cfg):
    wax = _col(col, (236, 226, 196)); out = []
    q = P(0, -.01, .05)
    out += [C((q[0], q[1], q[2]), (.11, .012, .11), BRASS, mat=M_METAL, **k), C(P(.05, .0, .05), (.03, .008, .012), BRASS, **k)]
    out += rnd(q[0], q[1] + .006, q[2], .05, .1, .05, wax, k)
    out += [C(P(.022, .07, .06), (.008, .025, .008), wax, **k), C(P(0, .102, .05), (.004, .012, .004), (30, 24, 20), **k),
            C(P(0, .118, .05), (.014, .024, .014), (255, 236, 160), emis=3.2, cast=False, **k), C(P(0, .126, .05), (.02, .04, .02), (255, 150, 50), emis=2.2, dissolve=.25, cast=False, **k)]
    if lights is not None: lights.append((P(0, .3, .1), (1, .62, .3), .9, 2.4))
    return out


def h_photo_frame(P, F, k, lights, col, cfg):
    """cadre photo tenu, la photo tournée vers l'avant (on la montre) ; le dos (carton, chevalet) vers celui qui tient"""
    fr = _col(col, (70, 46, 30)); img = T.photo(str(cfg.get('photo', 'portrait')), int(cfg.get('seed', 0)), 24, 30, bool(cfg.get('raye', False)))
    q = P(-.02, .1, .08)
    return [C(q, (.18, .23, .022), fr, mat=M_WOODV, **k), C(P(-.02, .1, .08 + .0115), (.14, .19, .001), (236, 230, 214), **k),
            C(P(-.02, .1, .08 + .0125), (.1, .15, .001), (150, 150, 150), tex={F['front']: img}, refl=.12, **k), C(P(-.02, .08, .08 - .012), (.12, .16, .002), (150, 120, 80), **k)]


def h_bag(P, F, k, lights, col, cfg):
    col = _col(col, (120, 60, 40)); dk = _sh(col, .7)
    out = [C(P(0, -.24, .0), (.28, .12, .12), col, **k), C(P(0, -.15, .0), (.24, .06, .11), col, **k), C(P(0, -.17, .062), (.25, .09, .004), dk, **k), C(P(0, -.17, .066), (.03, .022, .005), BRASS, **k)]
    out += [C(P(-.07, -.09, 0), (.016, .08, .016), dk, **k), C(P(.07, -.09, 0), (.016, .08, .016), dk, **k), C(P(0, -.045, 0), (.15, .016, .016), dk, **k)]
    return out


def h_suitcase(P, F, k, lights, col, cfg):
    """valise portée par sa poignée de transport, qui pend le long de la jambe"""
    col = _col(col, (60, 90, 140)); dk = _sh(col, .7)
    q = P(0, -.36, 0)
    out = [C(q, (.24, .58, .4), col, **k), C(P(0, -.36, 0), (.244, .015, .404), (30, 30, 34), **k)]
    for dy in (-.28, .28):
        for dz in (-.19, .19): out.append(C(P(0, -.36 + dy, dz), (.246, .03, .03), dk, **k))
    out += [C(P(0, -.03, 0), (.03, .025, .1), (30, 30, 34), **k), C(P(0, -.06, -.04), (.02, .03, .012), (30, 30, 34), **k), C(P(0, -.06, .04), (.02, .03, .012), (30, 30, 34), **k)]
    return out


HELD = {'od_handset': h_handset, 'od_smartphone': lambda *a: h_smartphone(*a, faces='holder'), 'od_smartphone_montre': lambda *a: h_smartphone(*a, faces='out'),
        'od_cup': h_cup, 'od_mug': h_mug, 'od_glass': h_glass, 'od_wine_glass': lambda *a: h_glass(*a, wine=True), 'od_bottle': h_bottle,
        'od_book': h_book, 'od_book_open': lambda *a: h_book(*a, opened=True), 'od_notebook': h_notebook, 'od_paper': h_paper, 'od_keys': h_keys,
        'od_crowbar': h_crowbar, 'od_flashlight': h_flashlight, 'od_candle': h_candle, 'od_photo_frame': h_photo_frame, 'od_bag': h_bag, 'od_suitcase': h_suitcase}

HELD_LABELS = {'od_handset': 'combiné (à l\'oreille, geste phone)', 'od_smartphone': 'smartphone, écran vers celui qui le tient', 'od_smartphone_montre': 'smartphone, écran montré vers l\'avant',
               'od_cup': 'tasse de café', 'od_mug': 'mug', 'od_glass': 'verre d\'eau', 'od_wine_glass': 'verre à vin', 'od_bottle': 'bouteille (par le col)', 'od_book': 'livre fermé, couverture vers l\'avant',
               'od_book_open': 'livre ouvert face au lecteur', 'od_notebook': 'carnet ouvert', 'od_paper': 'feuille imprimée', 'od_keys': 'clés (trousseau)', 'od_crowbar': 'pied-de-biche',
               'od_flashlight': 'lampe torche (faisceau)', 'od_candle': 'bougie sur bougeoir', 'od_photo_frame': 'cadre photo montré', 'od_bag': 'sac à main', 'od_suitcase': 'valise'}

# anciens noms tenus -> version détaillée sous la clé (avec les réglages qui reproduisent leur contenu d'avant)
UP_HELD = {'phone': ('od_smartphone', dict(_faces='both')), 'mobile': ('od_smartphone', dict(_faces='both', heure='02:16')), 'mobile_0213': ('od_smartphone', dict(_faces='both', heure='02:13')),
           'mobile_0214': ('od_smartphone', dict(_faces='both', heure='02:14')), 'handset': ('od_handset', dict(couleur=(122, 34, 36))), 'cup': ('od_cup', {}), 'book': ('od_book', {}), 'notebook': ('od_notebook', dict(texte=['313 ?'])),
           'printout': ('od_paper', dict(texte=['JOURNAL STANDARD', 'NUIT DU 30 AU 31', '', 'HEURE POSTE DUREE', '23:52 CH106 00:18', '00:37 EXT   01:04', '02:13 CH313 00:47', '02:14 EXT   00:22', '', 'POUR ENQUETE'],
                                         entete=False, surligne='02:13')),
           'key': ('od_keys', {}), 'bottle': ('od_bottle', {}), 'bag': ('od_bag', {}), 'flashlight': ('od_flashlight', {}), 'candle': ('od_candle', {}), 'crowbar': ('od_crowbar', {})}


def held(name, hand, f, k, lights=None, col=None, cfg=None):
    """boîtes d'un objet détaillé tenu (nom `od_*`), autour de la main"""
    x, y, z = hand
    P = lambda lat, up, fwd: (x + lat * f, y + up, z + fwd * f)
    F = _faces(f); F['f'] = f
    c = dict(_cfg(name)); c.update(cfg or {})
    if col is None and c.get('couleur') is not None: col = tuple(c['couleur'])          # couleur réglée dans la clé (ou celle du combiné bordeaux de l'hôtel)
    fn = HELD[name]
    if name == 'od_smartphone' and c.get('_faces'): out = h_smartphone(P, F, {}, lights, col, c, faces=c['_faces'])
    else: out = fn(P, F, {}, lights, col, c)
    # the character's flags (reflection only, no reflection, dissolve) are applied AFTER: an object may carry its own dissolve (steam, glass, beam)
    k = k or {}
    if k:
        for b in out:
            if 'hidden' in k: b.hidden = bool(k['hidden'])
            if 'noref' in k: b.noref = bool(k['noref'])
            if k.get('dissolve'): b.dissolve = max(float(b.dissolve or 0.), float(k['dissolve']))
    return out


# ================================================================== upgrades of the legacy names (under the key only)
def _y(p, d): return float(p.get('y', d))


UP_PROPS = {
    'tv': lambda p, c: ('od_tv', dict(p)),
    'tv_stand': lambda p, c: ('od_tv', dict(p, largeur=1.15)),
    'tv_old': lambda p, c: ('od_tv_crt', dict(p)),
    'nightstand': lambda p, c: ('od_nightstand', dict(p)),
    'desk_lamp': lambda p, c: ('od_desk_lamp', dict(p, modele='articulee')),
    'computer': lambda p, c: ('od_computer', dict(p)),
    'laptop': lambda p, c: ('od_laptop', dict(p)),
    'clock': lambda p, c: ('od_clock', dict(p, hauteur=2.15, heure=p.get('heure', '03:00'))),
    'wall_clock': lambda p, c: ('od_clock', dict(p, hauteur=float(p.get('at_y', 2.02)), heure=f"{int(p.get('hour', 3)):02d}:{int(p.get('minute', 33 if p.get('stopped') else 7)):02d}")),
    'plant': lambda p, c: ('od_plant', dict(p, taille=float(p.get('size', 1.)) * 1.15)),
    'framed_photo': lambda p, c: ('od_photo_frame', dict(p, mur=True, largeur=float(p.get('width', .34)), haut=float(p.get('height', .42)), hauteur=float(p.get('at_y', 1.56)), raye=bool(p.get('scratched')))),
    'suitcase': lambda p, c: ('od_suitcase', dict(p, modele='cuir')),
    'candles': lambda p, c: ('od_candle', dict(p, bougeoir=True)),
}


def _cups(p, c):
    """`cups` (deux tasses fumantes sur leurs soucoupes, à `y` interne) -> deux tasses détaillées au même endroit"""
    y = float(p.get('y', .8)); out = []
    for dx, dz in ((-.12, -.03), (.13, .05)):
        for b in k_cup({'vapeur': True}, c): b.lo = b.lo + np.array([dx, y, dz], np.float32); b.hi = b.hi + np.array([dx, y, dz], np.float32); out.append(b)
    return out


def _note(p, c):
    """`note` (feuille au mur ou à plat, à `y` interne) -> feuille imprimée détaillée, même texte"""
    y = float(p.get('y', 1.0)); w = float(p.get('w', .3)); lines_ = p.get('text') if isinstance(p.get('text'), list) else [p.get('text', '')]
    if p.get('art'): return None
    if p.get('flat'):
        out = k_paper({'texte': lines_, 'entete': False}, c)
        for b in out: b.lo = b.lo * np.array([w / .21, 1, w / .21], np.float32) + np.array([0, y, 0], np.float32); b.hi = b.hi * np.array([w / .21, 1, w / .21], np.float32) + np.array([0, y, 0], np.float32)
        return out
    out = k_paper({'texte': lines_, 'entete': False, 'mur': True, 'hauteur': 0.}, c)
    for b in out: b.lo = b.lo * np.array([w / .21, w / .21, 1], np.float32) + np.array([0, y, 0], np.float32); b.hi = b.hi * np.array([w / .21, w / .21, 1], np.float32) + np.array([0, y, 0], np.float32)
    return out


def _bottles(p, c):
    rng = np.random.default_rng(int(p.get('seed', 0)) * 23 + 7); out = []
    mods = ('vin', 'biere', 'vin', 'eau')
    for k_ in range(int(p.get('count', 4))):
        x = float(rng.uniform(-.22, .22)); z = float(rng.uniform(-.18, .18))
        for b in k_bottle({'modele': mods[k_ % 4]}, None): b.lo = b.lo + np.array([x, 0, z], np.float32); b.hi = b.hi + np.array([x, 0, z], np.float32); out.append(b)
    return out


UP_RAW = {'cups': _cups, 'note': _note, 'bottles': _bottles}


def prop_hook(kind, p, c):
    """appelé en tête de `sets.prop_boxes` : None sans la clé (le constructeur d'avant fait son travail), sinon la version détaillée du nom d'avant"""
    s = _STATE
    if s is None or not s.get('decors') or (p or {}).get('objets') is False: return None
    if kind in UP_PROPS:
        k2, p2 = UP_PROPS[kind](dict(p or {}), c)
        return prop(k2, p2, c)
    if kind in UP_RAW:
        bx = UP_RAW[kind](dict(p or {}), c)
        if bx is None: return None
        return _markers('_raw:' + kind, dict(p or {}), len(bx)) + bx
    return None


# ================================================================== registration
_ORIG = {}
_DONE = [False]


def held_item(item, hand, f, k, lights=None, col=None):
    if hand is not None:
        if item in HELD: return held(item, hand, f, k, lights, col)
        s = _STATE
        if s is not None and s.get('tenus') and item in UP_HELD:
            name, cfg = UP_HELD[item]
            c = dict(cfg); c.update(_cfg(item))
            return held(name, hand, f, k, lights, col, c)
    return _ORIG['held_item'](item, hand, f, k, lights, col)


class Registre:
    """ce qu'un LOT d'objets (fichier `objets_<lot>.py` de ce dossier, découvert tout seul) appelle dans sa fonction `enregistrer(R)` :
        R.objet('od_grille_pain', fn, 'grille-pain', lumieres=[...])     décor posé, version PS1 : fn(p, c) -> boîtes (repère local, face avant vers -z, y = 0 posé)
        R.tenu('od_grille_pain', fn, 'grille-pain tenu')                 objet tenu, version PS1 : fn(P, F, k, lights, col, cfg) -> boîtes (voir h_cup)
        R.ancien_decor('toaster', 'od_grille_pain', lambda p: dict(p))   un nom d'AVANT devient détaillé, sous la clé `objets` seulement
        R.ancien_tenu('toaster', 'od_grille_pain', {})
    Un nom déjà pris n'est jamais remplacé (ajouts seulement, comme partout)."""
    def __init__(self, source): self.source = source; self.noms = []

    def objet(self, kind, fn, label='', lumieres=None):
        if not kind.startswith('od_') or kind in KINDS: raise ValueError(f'[objets] {self.source} : nom « {kind} » refusé (préfixe od_ obligatoire, ou nom déjà pris)')
        KINDS[kind] = fn; LABELS[kind] = label or kind; self.noms.append(kind)
        if lumieres: LIGHTS[kind] = list(lumieres)

    def tenu(self, name, fn, label=''):
        if not name.startswith('od_') or name in HELD: raise ValueError(f'[objets] {self.source} : objet tenu « {name} » refusé (préfixe od_ obligatoire, ou nom déjà pris)')
        HELD[name] = fn; HELD_LABELS[name] = label or name; self.noms.append(name)

    def ancien_decor(self, old, kind, traduire=None):
        if old in UP_PROPS or old in UP_RAW: raise ValueError(f'[objets] {self.source} : « {old} » a déjà une version détaillée')
        UP_PROPS[old] = (lambda kk, tr: (lambda p, c: (kk, (tr or dict)(dict(p)))))(kind, traduire)

    def ancien_tenu(self, old, name, reglages=None):
        if old in UP_HELD: raise ValueError(f'[objets] {self.source} : « {old} » a déjà une version détaillée')
        UP_HELD[old] = (name, dict(reglages or {}))


LOTS = []          # lots d'objets chargés : [(module, [noms])], dans l'ordre alphabétique des fichiers (déterministe)


def _load_lots():
    """découvre et charge les fichiers `objets_<lot>.py` (sauf objets_tex) : chacun a une fonction `enregistrer(R)`. Un lot en échec est dit, jamais tu."""
    import importlib, pkgutil, os
    here = os.path.dirname(os.path.abspath(__file__))
    for m in sorted(pkgutil.iter_modules([here]), key=lambda m: m.name):
        if not m.name.startswith('objets_') or m.name in ('objets_tex',): continue
        try:
            mod = importlib.import_module(f'{__package__}.{m.name}')
            if hasattr(mod, 'enregistrer'):
                R = Registre(m.name); mod.enregistrer(R); LOTS.append((m.name, R.noms))
        except Exception as e:
            print(f'[objets] lot « {m.name} » non chargé : {type(e).__name__} : {e}')


def register():
    """installe les décors `od_*`, leurs lumières, les objets tenus `od_*` et l'enveloppe de `poses.held_item` (une fois par processus, ajouts seulement)"""
    if _DONE[0]: return
    from . import world as W, poses as P, sets as S
    _load_lots()
    for kind in KINDS:
        W.PROPS.setdefault(kind, (lambda kk: (lambda p, c: prop(kk, p, c)))(kind))
        if kind not in S.PROP_TYPES: S.PROP_TYPES.append(kind)
    for kind, l in LIGHTS.items(): W.PROP_LIGHTS.setdefault(kind, l)
    _ORIG['held_item'] = P.held_item; P.held_item = held_item
    P.HOLD_ITEMS = tuple(P.HOLD_ITEMS) + tuple(i for i in HELD if i not in P.HOLD_ITEMS)
    _DONE[0] = True
