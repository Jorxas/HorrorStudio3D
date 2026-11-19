"""SOUS-TITRES SURS -- EXPERIMENTAL, OPT-IN (cle d'episode "caption_safe").

Sans la cle, `configure()` rend None, aucun appel de ce paquet n'a lieu et le sous-titre est pose exactement
ou il etait pose, au pixel pres. C'est verifie plutot qu'affirme : `tools/regress.py`, `tools/regress_v2.py`,
`tools/regress_aplat.py` et `tools/check_soustitres.py` section 1.

LE DEFAUT CORRIGE, tel que le proprietaire l'a vu. Dans les cinq videos voxel premium du 25/10 le bandeau
de sous-titres couvre la bouche des personnages en plan serre. Ce n'est pas une impression : la position
livree par defaut est `ui.subs = "mid"`, et en 9:16 `mid` pose le texte a y=880 sur 1920
(`engines/pixel3d/render.Layout.sub_y`), c'est-a-dire au MILIEU du cadre -- exactement la ou un gros plan
vertical pose un visage. Mesure sur `examples/scenes/portrait_peur.json` (la scene d'essai de ce lot-la,
quatre plans serres sur deux visages) : sur 4 des 5 plans le rectangle de texte est ENTIEREMENT dans la
boite de tete, et sur 3 des 5 il tombe sur la bande de la bouche. Voir docs/SUBTITLE_SAFE_9X16.md.

CE QUE CA FAIT. Une fois par episode, le planificateur mesure ou sont les visages dans chaque plan
(`probe3d.faces_at`, qui relit le tampon d'indices du lanceur de rayons -- aucune detection, aucun GPU),
puis choisit pour chaque plan UNE bande de sous-titre parmi les bandes nommees du moteur et deux bandes
derivees de la mesure (`geometry.choose`). Le resultat est un plan de bandes, un par plan de montage.

CE QUE CA NE FAIT PAS, et il faut le lire avant de juger :

- ca ne supprime pas les sous-titres et ca ne les sort pas du cadre : toute bande candidate est bornee par
  la zone sure, le texte reste centre, le minutage et le decoupage de `engines/common.build_subs` ne sont
  pas touches d'une virgule, les accents FR, les labels de locuteur et le mot-cle rouge non plus ;
- ca ne pose aucune bande noire et ne recadre rien : le 9:16 reste plein ;
- ca ne touche ni la camera, ni les acteurs, ni les corps. **Le haut du crane coupe et les cheveux
  lateraux qui masquent le visage NE SONT PAS traites ici** -- c'est du cadrage, donc le lot camera. Ce
  module les MESURE (la boite de tete mesuree est celle des pixels visibles, donc une tete coupee par le
  bord se voit dans le rapport) mais il ne les corrige pas ;
- ca ne bouge pas le sous-titre pendant un plan : la bande est decidee par PLAN, pas par image ni par
  replique. Un changement de bande ne peut donc arriver que sur un montage cut, la ou l'oeil l'attend.

LES PRESETS

    "caption_safe": true                    = "auto"
    "caption_safe": "auto"                  mesure les visages, choisit la bande par plan (recommande)
    "caption_safe": "regle"                 AUCUNE mesure : zone sure + levee 9:16 sur les plans serres.
                                            Pour le moteur console 2d, ou pour une machine pressee.
    "caption_safe": {"style": "auto", "echantillons": 3, "ajuster_largeur": true}
    "caption_safe": false | absente         le sous-titre livre, au pixel pres

`echantillons` = combien d'instants d'un plan sont mesures (la zone protegee est leur UNION, ce qui rend
la bande valable pendant tout le plan). 1 est moins cher et moins sur ; au-dela de 4 on paye sans gagner.
"""
from . import geometry as G

# Les plans serres : ceux ou un visage occupe le milieu du cadre vertical. Liste reprise telle quelle de
# `engines/pixel3d/acted.CLEAR_FACE_SHOTS` et de `tools/cadrage_qc.TIGHT`, pour ne pas en inventer une.
TIGHT_SHOTS = ('close', 'closeup', 'extreme_close', 'medium', 'medium_full', 'ots', 'dialogue', 'two_shot')

PRESETS = {
    # la configuration retenue : on mesure, et la bande est stable sur toute la duree d'un plan
    'auto': dict(mesure=True, echantillons=3, ajuster_largeur=True, stabilite='plan'),
    # sans mesure : la regle seule (zone sure + levee 9:16 sur les plans serres). Moins sur, gratuit.
    'regle': dict(mesure=False, echantillons=0, ajuster_largeur=True, stabilite='plan'),
}

_STATE = None


def configure(value):
    """-> l'etat de ce module pour un episode, ou None (= le sous-titre livre, au pixel pres)"""
    if not value:
        return None
    if value is True:
        st = dict(PRESETS['auto'], style='auto')
    elif isinstance(value, str):
        if value not in PRESETS:
            return None
        st = dict(PRESETS[value], style=value)
    elif isinstance(value, dict):
        style = value.get('style', 'auto')
        if style not in PRESETS:
            return None
        st = dict(PRESETS[style], style=style)
        for k in ('mesure', 'echantillons', 'ajuster_largeur', 'stabilite'):
            if k in value:
                st[k] = value[k]
    else:
        return None
    st['echantillons'] = max(0, min(4, int(st.get('echantillons', 3))))
    st['_plan'] = None          # le plan de bandes, calcule une seule fois, a la premiere image
    return st


def use(state):
    global _STATE
    _STATE = state


def active():
    return _STATE


def notices(ep):
    """ce qu'il faut dire en francais quand la cle est posee dans une situation qui la rend inutile"""
    out = []
    v = (ep or {}).get('caption_safe')
    if not v:
        return out
    st = configure(v)
    if st is None:
        out.append(f'"caption_safe": {v!r} inconnu, ignore (sous-titres livres conserves) ; '
                   f'connus : {", ".join(sorted(PRESETS))}')
        return out
    if (ep or {}).get('style') not in (None, 'pixel3d') and st['mesure']:
        out.append('"caption_safe" en mode mesure demande la geometrie 3D des visages : hors pixel3d '
                   'seule la regle de zone sure s\'applique (equivalent de "regle")')
    shots = (ep or {}).get('shots') or []
    if shots and all(((s.get('ui') or {}).get('subs') == 'off') for s in shots):
        out.append('"caption_safe" pose alors que tous les plans ont "subs": "off" : aucun sous-titre a placer')
    return out


# ---------------------------------------------------------------- le plan de bandes, un par plan de montage
def _cues_of_shot(eng, k):
    """les repliques de sous-titre qui tombent dans le plan k -> [(a, b, texte, a_un_label)]"""
    t0, t1 = eng.ctx.tl.spans[k] if hasattr(eng, 'ctx') else eng.tl.spans[k]
    lines = eng.lines
    out = []
    for s in eng.subs:
        if s['b'] <= t0 or s['a'] >= t1:
            continue
        txt = ' '.join(w for w, _ in s['words'])
        ln = lines[s['line']] if 0 <= s['line'] < len(lines) else {}
        out.append((max(s['a'], t0), min(s['b'], t1), txt, bool(ln.get('label'))))
    return out


def _sample_times(cues, n):
    """instants mesures dans un plan : les milieux de replique, repartis. Deterministe."""
    if not cues or n <= 0:
        return []
    mids = [(a + b) / 2. for a, b, _t, _l in cues]
    if len(mids) <= n:
        return mids
    step = (len(mids) - 1) / float(n - 1) if n > 1 else 0.
    return [mids[int(round(i * step))] for i in range(n)]


def plan_pixel3d(state, eng, measure=None):
    """-> {k: dict(band, y_px, ...)} pour tous les plans de l'episode. Calcule UNE fois.

    Deux passes, et c'est voulu : la premiere mesure et choisit plan par plan dans l'ordre du montage,
    la seconde est l'hysteresis (`geometry.choose(prev=...)`). Faire les deux dans l'ordre du montage et
    une seule fois rend le resultat INDEPENDANT de l'image par laquelle on entre -- un outil qui ne rend
    qu'une image a 7,3 s obtient la meme bande qu'un rendu complet.
    """
    from ..engines.common import font as _font
    from PIL import Image, ImageDraw
    L = eng.L
    W, H = L.W, L.H
    aspect = eng.aspect
    safe = G.SAFE.get(aspect, G.SAFE['9:16'])
    named = {k: v / float(H) for k, v in L.sub_y.items() if k in ('mid', 'low', 'top')}
    probe = measure or (_probe3d if state['mesure'] else None)
    scratch = ImageDraw.Draw(Image.new('RGB', (8, 8)))
    base_size = int(state.get('_taille', 56))
    fnt = _font(_FONT(), base_size)
    line_h = base_size * 1.15                      # la police pixel ne porte pas de metrique utile : 1.15 em
    label_h = 52.                                  # la pastille du locuteur est dessinee a y-52 (render.compose)

    out = {}
    prev = None
    for k in range(len(eng.ctx.tl.spans)):
        cues = _cues_of_shot(eng, k)
        shot = eng.ep['shots'][k] if k < len(eng.ep.get('shots') or []) else {}
        ui = shot.get('ui') or {}
        declared = ui.get('subs', 'mid')
        # `frame.apply_cut` autorise un plan a redeclarer son `ui` a l'interieur de lui-meme
        # (`shot["cuts"]`). La bande, elle, est decidee UNE fois pour le plan : c'est le choix qui evite
        # les sauts. Une coupe qui redemande une autre position est donc remplacee -- ce qui est
        # exactement l'objet de l'option -- mais on le DIT plutot que de le taire, et le rapport porte la
        # liste. Un `"subs": "off"` dans une coupe reste respecte : c'est le moteur qui le lit, pas nous.
        cut_subs = sorted({(c.get('ui') or {}).get('subs') for c in (shot.get('cuts') or [])
                           if isinstance(c, dict) and (c.get('ui') or {}).get('subs')} - {declared})
        if declared == 'off' or not cues:
            out[k] = dict(band=declared, declared=declared, y_px=None, skipped=True, cues=len(cues))
            continue
        widest = max(scratch.textlength(t, font=fnt) for _a, _b, t, _l in cues)
        lab = any(l for _a, _b, _t, l in cues)
        # ajuster la largeur AVANT de choisir la bande : un texte rapetisse occupe un rectangle plus etroit
        kfit = G.fit_width(widest / W, aspect, safe) if state['ajuster_largeur'] else 1.0
        w_n = min(1., (widest * kfit) / W)
        # la HAUTEUR, elle, est celle de la police PLEINE, et pas celle de la police rapetissee. Le
        # rapetissement est decide par replique (`place3d`), la bande par plan : une replique courte du
        # meme plan est dessinee en taille pleine et serait donc plus HAUTE que ce que la bande a prevu.
        # Prendre la hauteur pleine ici rend la bande valable pour la replique la plus haute du plan.
        h_n = line_h / H
        lab_n = (label_h / H) if lab else 0.
        zones, info = ([], {})
        if probe is not None:
            ts = _sample_times(cues, state['echantillons'])
            zones, info = _union_zones(probe, eng.ctx, ts, aspect)
        if not zones:
            # pas de mesure (ou aucun visage mesure) -> la REGLE : en 9:16, un plan serre leve le texte
            # hors de la bande centrale, et la zone sure borne tout le reste.
            y_n, band, reason = _rule(named, declared, shot, aspect, h_n, lab_n, safe)
            res = dict(band=band, y=y_n, clear=None, cost=None, parts={}, reason=reason, tried=[])
        else:
            res = G.choose(named, declared, zones, w_n, h_n, lab_n, aspect, prev=prev, safe=safe)
        # Quand la bande retenue est une bande NOMMEE du moteur, on reprend son pixel exact au lieu du
        # retour de l'aller-retour normalise. `geometry` arrondit a 1e-6, ce qui rendait 800,00028 au lieu
        # de 800 : invisible a l'oeil, mais ca voulait dire qu'un plan ou la politique ne change RIEN
        # n'etait quand meme pas identique au pixel pres. Ici « meme bande » veut dire « meme pixel », et
        # ca se verifie (tools/check_soustitres.py section 10).
        y_px = float(L.sub_y[res['band']]) if res['band'] in L.sub_y else res['y'] * H
        out[k] = dict(band=res['band'], y_px=y_px, y=y_px / H, clear=res.get('clear'),
                      cost=res.get('cost'), parts=res.get('parts') or {}, reason=res.get('reason'),
                      declared=declared, moved=abs(y_px - float(L.sub_y.get(declared, y_px))) > .5,
                      fit=round(kfit, 4), width_px=round(widest * kfit, 1), cues=len(cues),
                      cut_subs=cut_subs, zones=zones, info=info, tried=res.get('tried') or [])
        if cut_subs:
            print(f'[sous-titres] plan {k} : une coupe demande aussi "subs": '
                  f'{", ".join(cut_subs)} ; la bande du plan ("{res["band"]}") est conservee '
                  f'sur toute sa duree pour ne pas faire sauter le bandeau')
        prev = (res['band'], res['y'])
    return out


def _FONT():
    from ..paths import FONT_PIXEL
    return FONT_PIXEL


def _probe3d(ctx, g, aspect):
    from .probe3d import faces_at
    return faces_at(ctx, g, aspect)


def _union_zones(probe, ctx, times, aspect):
    """l'union, sur plusieurs instants, des zones a proteger. Une tete qui bouge pendant le plan protege
    donc tout le chemin qu'elle a parcouru : c'est ce qui rend une bande valable pour tout le plan."""
    acc = []
    info = {}
    for g in times:
        zones, nfo = probe(ctx, g, aspect)
        info = nfo or info
        for z in zones:
            acc.append(z)
    if not acc:
        return [], info
    # une seule zone fusionnee par "colonne" de l'image : deux personnages cote a cote restent deux zones
    # (sinon on protegerait tout le cadre), mais la meme tete a trois instants n'en fait qu'une.
    groups = []
    for z in sorted(acc, key=lambda z: z['rect'][0]):
        placed = False
        for gr in groups:
            if G.inter(gr[0]['rect'], z['rect']) > 0:
                gr.append(z)
                placed = True
                break
        if not placed:
            groups.append([z])
    out = []
    for gr in groups:
        out.append(dict(rect=_hull([z['rect'] for z in gr]),
                        mouth=_hull([z['mouth'] for z in gr if z.get('mouth')]),
                        eyes=_hull([z['eyes'] for z in gr if z.get('eyes')]),
                        share=round(max(z.get('share', 0.) for z in gr), 5), weight=1.))
    return out, info


def _hull(rects):
    rects = [r for r in rects if r]
    if not rects:
        return None
    return (min(r[0] for r in rects), max(r[1] for r in rects),
            min(r[2] for r in rects), max(r[3] for r in rects))


def _rule(named, declared, shot, aspect, h_n, lab_n, safe):
    """la REGLE, sans aucune mesure : zone sure + levee 9:16 sur les plans serres.

    C'est le mode "regle", et c'est aussi le filet quand la mesure ne rend aucun visage (plan sans
    personnage, insert, pov). Elle ne peut pas savoir ou est la bouche ; elle sait seulement qu'en 9:16 un
    plan serre met un visage au milieu du cadre, et que `mid` est au milieu du cadre."""
    kind = ((shot.get('camera') or {}).get('shot') or '').lower()
    tight = kind in TIGHT_SHOTS
    y = named.get(declared, named.get('mid', .5))
    why = 'regle : position du plan conservee'
    if aspect == '9:16' and tight and declared in ('mid', None):
        y = named.get('low', y)
        why = f'regle : plan serre ({kind}) en 9:16, bandeau descendu de "mid" a "low"'
    y2 = min(max(y, safe['top'] + lab_n), safe['bottom'] - h_n)
    if abs(y2 - y) > 1e-9:
        why += ' ; borne par la zone sure'
    return y2, (declared if abs(y2 - named.get(declared, -1)) < 1e-9 else 'low' if abs(y2 - named.get('low', -1)) < 1e-9 else 'zone_sure'), why


# ---------------------------------------------------------------- ce que le moteur appelle, par image
def place3d(state, eng, g, declared, sub, draw, F, y_default):
    """-> (y_px, police, largeur_px). Appele par engines/pixel3d/render.compose, une fois par image.

    Pas de mesure ici : tout est deja decide (plan_pixel3d, une fois). Cette fonction ne fait que lire la
    bande du plan courant et, si la replique est trop large pour les marges, rapetisser la police."""
    if state.get('_plan') is None:
        # Une option opt-in ne doit pas faire tomber un rendu de plusieurs minutes. Si la mesure echoue
        # (scene exotique, memoire), on le DIT une fois et on revient a la position livree : le rendu
        # continue, le sous-titre est a sa place d'origine, et le rapport n'a pas menti.
        try:
            state['_plan'] = plan_pixel3d(state, eng)
        except Exception as e:
            state['_plan'] = {}
            print(f'[sous-titres] mesure impossible ({type(e).__name__}: {str(e)[:120]}) : '
                  f'positions livrees conservees pour tout l\'episode')
    k = eng.ctx.tl.at(g)[0]
    p = state['_plan'].get(k)
    text = ' '.join(w for w, _ in sub['words'])
    fnt = F(56)
    tw = draw.textlength(text, font=fnt)
    if p is None or p.get('y_px') is None:
        return y_default, fnt, tw
    if state['ajuster_largeur']:
        kfit = G.fit_width(tw / float(eng.L.W), eng.aspect)
        if kfit < 1.0:
            fnt = F(max(18, int(56 * kfit)))
            tw = draw.textlength(text, font=fnt)
    return p['y_px'], fnt, tw


def shot_hint(shot):
    """-> un plan que `_rule` sait lire, pour un moteur qui ne nomme pas ses plans comme pixel3d.

    CONSOLE 2D ne declare pas `camera.shot` : il declare un TYPE DE SCENE (`scene.type`). Deux de ces
    types mettent un visage au milieu du cadre -- `face` (le gros plan dessine) et `split` quand il porte
    un visage. Les autres (`door`, `room`, `hallway`, `window`) cadrent une piece, pas une tete."""
    if not isinstance(shot, dict):
        return {}
    cam = shot.get('camera') or {}
    if cam.get('shot'):
        return shot
    typ = (shot.get('scene') or {}).get('type')
    if typ == 'face':
        return dict(shot, camera=dict(cam, shot='close'))
    return shot


def place_rule(state, declared, named_px, H, aspect, shot, h_px, label_px=0.):
    """-> y_px. La regle seule, pour un moteur qui n'a pas de geometrie de visage (console 2d)."""
    safe = G.SAFE.get(aspect, G.SAFE['9:16'])
    named = {k: v / float(H) for k, v in named_px.items() if k in ('mid', 'low', 'top')}
    y, _band, _why = _rule(named, declared, shot or {}, aspect, h_px / float(H), label_px / float(H), safe)
    return y * H
