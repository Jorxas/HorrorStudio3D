"""Geometrie et politique de placement du bandeau de sous-titres. AUCUN import moteur, AUCUNE image.

Tout est en coordonnees NORMALISEES d'image : un rectangle est `(x0, x1, y0, y1)` avec x et y dans 0..1,
**y vers le bas** (0 = haut du cadre). Les deux moteurs (pixel3d, console 2d) et les deux formats (9:16,
16:9) parlent donc la meme langue, et cette politique se teste sans rendre une seule image
(`tools/check_soustitres.py`).

CE QUE CE FICHIER DECIDE : la hauteur `y` du haut du texte, et rien d'autre. L'alignement reste centre,
le decoupage en morceaux et le minutage restent ceux de `engines/common.build_subs` (pas touches), les
couleurs, le contour, le mot-cle rouge et la pastille du locuteur restent ceux du moteur.

CE QUE CE FICHIER NE FAIT PAS : il ne detecte rien. Il recoit des rectangles deja mesures (tete, bouche,
yeux) et il choisit une bande parmi des candidates. Pas de GPU, pas d'OCR, pas de reseau.

----------------------------------------------------------------------------------------------------
LA ZONE SURE 9:16, ET D'OU VIENNENT SES QUATRE NOMBRES

Ce ne sont pas des nombres inventes : trois des quatre sont deja dans le moteur, ce fichier les ecrit.

| bord | valeur 9:16 | en pixels sur 1080x1920 | pourquoi |
|---|---|---|---|
| haut | 0.155 | 298 | le cartouche HUD occupe 52..190 (titre deux lignes a y=52 puis `part` a +104) et la rangee de coeurs est a la meme hauteur (`engines/pixel3d/render.Layout`). 298 laisse ~108 px de marge. |
| bas | 0.880 | 1690 | la position `low` livree pose le texte a 1560 et il finit vers 1624 (0.846). Les plateformes verticales dessinent leur propre legende et leur rail de boutons sous cette ligne. 0.880 est donc la convention DEJA livree, ecrite, pas une nouvelle. |
| cotes | 0.052 | 56 | la marge gauche du HUD en 9:16, reprise telle quelle. |
| gap | 0.016 | 31 | l'ecart minimum entre le texte et la boite de tete : le contour de 5 px, plus une respiration. |

RIEN ICI NE CHANGE LE CADRE. Pas de bande noire, pas de letterbox, pas de recadrage : le 9:16 reste plein
et l'image dessous est exactement celle que le moteur a rendue. On deplace du TEXTE.
"""

# Les quatre bords, par format. `gap` est l'ecart minimum texte <-> tete.
SAFE = {
    '9:16': dict(top=.155, bottom=.880, side=.052, gap=.016),
    '16:9': dict(top=.120, bottom=.945, side=.050, gap=.022),
}

# REGLE QUI FIXE LE BORD BAS, et qui a deja corrige un nombre de ce tableau : la zone sure ne doit JAMAIS
# declarer dangereuse une position que le moteur livre deja. Le premier 16:9 essaye ici valait 0.900, et il
# refusait la position livree `low` (y=950 sur 1080, le texte finit a 1014 soit 0.939) : la politique
# deplacait alors un sous-titre 16:9 dont personne ne s'est plaint. 0.945 accepte la position livree et
# laisse le bord servir a ce pour quoi il est fait -- empecher d'ALLER plus bas qu'elle.
# `tools/check_soustitres.py` section 9 verifie cet invariant sur les deux moteurs et les deux formats.

# Ordre editorial des bandes nommees quand celle demandee par le plan n'est pas libre. `low` d'abord :
# c'est la place du sous-titre au cinema, celle qui risque le moins de couvrir une information narrative.
FALLBACK_ORDER = ('low', 'mid', 'top')

# Ce que couvrir coute. La bouche est le defaut signale par le proprietaire : elle coute le plus cher.
# Les yeux ensuite (le regard porte le jeu), puis le reste de la tete, puis ce qui n'est que proche.
W_MOUTH, W_EYES, W_HEAD, W_NEAR = 1000., 400., 60., 6.
W_ORDER = 1.0        # penalite par rang dans l'ordre editorial : a egalite, on reste pres du plan
W_MOVE = 12.0        # penalite de deplacement : a egalite, on ne bouge pas le bandeau d'un plan a l'autre


def clamp(x, a=0., b=1.):
    return a if x < a else (b if x > b else x)


def area(r):
    return (max(0., r[1] - r[0]) * max(0., r[3] - r[2])) if r else 0.


def inter(a, b):
    """aire de l'intersection de deux rectangles normalises (0 si disjoints)"""
    if a is None or b is None:
        return 0.
    w = min(a[1], b[1]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[2], b[2])
    return (w * h) if (w > 0 and h > 0) else 0.


def covered(text, zone):
    """part du RECTANGLE DE TEXTE couverte par `zone` (0..1). C'est la mesure qui compte pour la
    lisibilite : un texte a moitie dans un visage est illisible meme si le visage est enorme."""
    at = area(text)
    return (inter(text, zone) / at) if at > 0 else 0.


def grow(r, dx, dy):
    return None if r is None else (r[0] - dx, r[1] + dx, r[2] - dy, r[3] + dy)


def text_rect(y, w, h, label_h=0.):
    """rectangle occupe par un sous-titre centre : `y` = haut du texte, `w`/`h` = taille du texte,
    `label_h` = la pastille du locuteur dessinee AU-DESSUS (elle doit rester dans le cadre aussi)."""
    return (clamp((1. - w) / 2.), clamp((1. + w) / 2.), y - label_h, y + h)


def fits(y, h, label_h, safe):
    """le texte (pastille comprise) tient-il entre les deux bords horizontaux de la zone sure ?

    La tolerance est 1e-6 et pas 1e-9, et ce n'est pas de la negligence : `candidates()` arrondit les
    hauteurs a 1e-6 pour que deux candidates egales se reconnaissent. Une bande construite POUR toucher
    le bord (`bas_zone_sure` vaut exactement `bottom - h`) ressortait donc de l'arrondi a 3e-7 au-dela
    du bord, se voyait refusee, et recevait la penalite de 1e6 reservee au hors-cadre -- alors qu'elle
    est precisement le dernier recours garanti. 1e-6 de 1920 px fait 0,002 px : la tolerance est sous le
    pixel, l'invariant tient."""
    return (y - label_h) >= safe['top'] - 1e-6 and (y + h) <= safe['bottom'] + 1e-6


def candidates(named, declared, protect, h, label_h, safe):
    """les bandes examinees, dans l'ordre editorial, avec leur nom.

    - d'abord celle que le plan demande (`ui.subs`), pour ne jamais trahir une intention de mise en scene
      qui ne pose pas de probleme ;
    - puis les bandes nommees du moteur, dans l'ordre `low`, `mid`, `top` ;
    - puis deux bandes DERIVEES de la mesure, utiles quand aucune des trois ne passe : juste sous le
      menton, et juste au-dessus du crane.

    Les bandes derivees sont les seules positions que ce module invente, et elles sont bornees par la
    zone sure : il n'y a aucun chemin par lequel le sous-titre sort du cadre ou passe sous le rail de la
    plateforme."""
    out = []
    seen = set()

    def add(name, y):
        y = round(float(y), 6)
        if (name, y) in seen:
            return
        seen.add((name, y))
        out.append((name, y))

    if declared in named:
        add(declared, named[declared])
    for nm in FALLBACK_ORDER:
        if nm in named:
            add(nm, named[nm])
    if protect:
        bot = max(z['rect'][3] for z in protect)
        top = min(z['rect'][2] for z in protect)
        y_chin = bot + safe['gap']
        if fits(y_chin, h, label_h, safe):
            add('sous_menton', y_chin)
        y_crown = top - safe['gap'] - h
        if fits(y_crown, h, label_h, safe):
            add('sur_front', y_crown)
    # dernier recours garanti dans la zone sure : le bas de la zone sure elle-meme
    add('bas_zone_sure', safe['bottom'] - h)
    return out


def cost(y, w, h, label_h, protect, safe, rank=0, prev_y=None):
    """ce que coute une bande : d'abord ce qu'elle couvre, puis des details de confort.

    Le cout se lit : `clear` = la bande ne touche aucune tete, et les termes de confort (`rank`,
    `prev_y`) ne peuvent pas a eux seuls rendre une bande libre plus chere qu'une bande qui couvre un
    visage -- W_NEAR, W_ORDER et W_MOVE sont tous tres en dessous de W_HEAD."""
    t = text_rect(y, w, h, label_h)
    near = grow(t, safe['gap'], safe['gap'])
    c = 0.
    parts = dict(bouche=0., yeux=0., tete=0., proche=0.)
    for z in protect:
        k = float(z.get('weight', 1.))
        m = covered(t, z.get('mouth')) * k
        e = covered(t, z.get('eyes')) * k
        hd = covered(t, z['rect']) * k
        nr = max(0., covered(near, z['rect']) * k - hd)
        parts['bouche'] += m
        parts['yeux'] += e
        parts['tete'] += hd
        parts['proche'] += nr
        c += W_MOUTH * m + W_EYES * e + W_HEAD * hd + W_NEAR * nr
    # `clear` = "cette bande est utilisable telle quelle". Elle exige DEUX choses, et pas une : ne couvrir
    # aucun visage, ET tenir dans la zone sure. Oublier la seconde a coute un vrai defaut : en 16:9 la
    # politique choisissait `low` (y=950) parce qu'aucun visage n'y etait, alors que 65,8 % du rectangle de
    # texte sortait de la zone sure -- et l'hysteresis, qui ne regarde que `clear`, propageait l'erreur au
    # plan suivant. Les deux branches de `choose` lisent `clear` : la condition doit etre complete ici.
    inside = fits(y, h, label_h, safe)
    clear = inside and parts['tete'] <= 1e-9 and parts['bouche'] <= 1e-9 and parts['yeux'] <= 1e-9
    c += W_ORDER * rank
    if prev_y is not None:
        c += W_MOVE * abs(y - prev_y)
    if not inside:
        c += 1e6          # hors zone sure : jamais choisi s'il existe autre chose
    return c, clear, parts


def choose(named, declared, protect, w, h, label_h=0., aspect='9:16', prev=None, safe=None):
    """LA decision. -> dict(band, y, clear, cost, parts, reason, tried)

    `named`   : les bandes du moteur, normalisees  {'mid': .4583, 'low': .8125, 'top': .2187}
    `declared`: ce que le plan demande (`ui.subs`), 'mid' par defaut
    `protect` : [{'rect': (x0,x1,y0,y1), 'mouth': rect|None, 'eyes': rect|None, 'weight': 1.}, ...]
    `w`, `h`  : largeur et hauteur du texte, normalisees (la PLUS LARGE replique du plan : la bande ne
                bouge pas d'une replique a l'autre, donc elle doit convenir a la plus large)
    `label_h` : hauteur de la pastille du locuteur, dessinee au-dessus du texte
    `prev`    : (nom, y) de la bande du plan precedent -- l'hysteresis qui evite les sauts
    """
    safe = safe or SAFE.get(aspect, SAFE['9:16'])
    cands = candidates(named, declared, protect, h, label_h, safe)
    prev_y = prev[1] if prev else None
    rows = []
    for i, (nm, y) in enumerate(cands):
        c, clear, parts = cost(y, w, h, label_h, protect, safe, i, prev_y)
        rows.append(dict(band=nm, y=y, cost=round(c, 4), clear=clear,
                         parts={k: round(v, 4) for k, v in parts.items()}))
    # 1. on garde la bande du plan precedent si elle est encore libre ici : le bandeau ne bouge pas
    if prev:
        for r in rows:
            if r['band'] == prev[0] and r['clear'] and abs(r['y'] - prev[1]) < 1e-6:
                return dict(r, tried=rows, reason='maintenue (bande du plan precedent, toujours libre)')
    # 2. sinon la premiere bande libre dans l'ordre editorial
    for r in rows:
        if r['clear']:
            return dict(r, tried=rows, reason='premiere bande libre')
    # 3. sinon la moins mauvaise, et on le dit
    best = min(rows, key=lambda r: r['cost'])
    return dict(best, tried=rows, reason='aucune bande libre : cout minimal (defaut residuel declare)')


# ---------------------------------------------------------------- largeur : ne pas masquer par du texte enorme
def fit_width(w, aspect='9:16', safe=None, floor=.55):
    """facteur a appliquer a la taille de police pour que le texte tienne entre les marges laterales.
    1.0 = rien a faire. Jamais en dessous de `floor` : plus petit, le sous-titre devient illisible, et
    mieux vaut un texte un peu large qu'un texte minuscule (accessibilite)."""
    safe = safe or SAFE.get(aspect, SAFE['9:16'])
    room = 1. - 2. * safe['side']
    if w <= room or w <= 0:
        return 1.0
    return max(floor, room / w)
