"""Tests de la tranche verticale ECLAIRAGE NARRATIF (hstudio/engines/pixel3d/lighting.py).
Hors ligne, sans API, sans voix. Sort 1 au moindre echec.

  python tools/check_lighting.py

Ce qu'on verifie :
  - par defaut rien ne bouge : un episode sans bloc "lighting" rend exactement les memes pixels ;
  - determinisme : deux rendus du meme instant donnent les memes octets, et un autre processus aussi ;
  - les formes d'onde sont bornees, sans alea ni horloge ;
  - chaque valeur invalide retombe sur un repli ANNONCE (message francais, pas de remplacement muet) ;
  - le budget CPU tient : au plus MAX_EXTRA lumieres ajoutees, et jamais de rayon d'ombre en plus ;
  - la lumiere fait vraiment ce qu'elle dit : halo vert -> vert, alarme rouge -> rouge, contre-jour ->
    le fond gagne plus que le sujet, eclair -> flash bref ;
  - lisibilite : pendant le clignotement, le visage ne tombe jamais sous le seuil de « image noire » de
    hstudio/acting/qc.py.
"""
import os, sys, io, json, copy, math, hashlib, subprocess
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import light_sheet as LS
from hstudio.engines.pixel3d import lighting as LT, r3d
from hstudio.engines.pixel3d.frame import build_frame

FAIL = []
def check(name, ok, detail=''):
    print(f"{'OK   ' if ok else 'ECHEC'} {name}" + (f'  ({detail})' if detail and not ok else '')); ok or FAIL.append(name)

def sha(a): return hashlib.sha1(np.asarray(a).tobytes()).hexdigest()[:16]

class Ctx:
    """le minimum que lighting.plan attend d'un FrameContext (pour les tests unitaires)"""
    def __init__(self, ep=None): self.ep = ep or {}; self.fx_flash = 0.

class St:
    """un decor minimal : des reperes, comme en sort make_set"""
    spec = {}
    anchors = {'console': (1.9, 2.6), 'porte': (-2.5, 1.5), 'x': (0., 2.)}

def grab(printed):
    out = io.StringIO(); old = sys.stdout; sys.stdout = out
    try: printed()
    finally: sys.stdout = old
    return out.getvalue()


# ------------------------------------------------------------------ 1. opt-in
def opt_in_checks():
    ep = LS.scene(); before = LS.strip_lighting(ep)
    eb = LS.engine(before); eb2 = LS.engine(before)
    ts = LS.shot_times(ep)
    same = all(sha(eb.render_lowres(t)[0]) == sha(eb2.render_lowres(t)[0]) for t in ts)
    check('sans bloc "lighting" : deux moteurs rendent les memes pixels', same)
    # le module n'est meme pas sollicite : aucune lumiere ajoutee, aucun avertissement
    ctx = Ctx({})
    L, extra = LT.plan(ctx, {}, St(), {}, ((0, 1.6, 0), 0, 0, 0, 1.), None, [], 0, 0., 0., 0.)
    check('sans intention : aucune lumiere ajoutee', extra == [] and L == [])
    check('sans intention : aucun avertissement', not getattr(ctx, 'lighting_warnings', []))
    # "lighting": "none" sur un plan annule l'intention de l'episode
    ctx = Ctx({'lighting': {'mood': 'red'}})
    check('"lighting": "none" sur un plan annule celle de l\'episode', LT.intent(ctx, {'lighting': 'none'}) is None)
    check('l\'intention de l\'episode sert de defaut au plan', (LT.intent(Ctx({'lighting': {'mood': 'red'}}), {}) or {}).get('mood') == 'red')
    merged = LT.intent(Ctx({'lighting': {'mood': 'red', 'fill': .5}}), {'lighting': {'mood': 'cold'}})
    check('le plan surcharge cle par cle', merged == {'mood': 'cold', 'fill': .5}, str(merged))


# ------------------------------------------------------------------ 2. determinisme
def determinism_checks():
    ep = LS.scene(); ts = LS.shot_times(ep)
    e1, e2 = LS.engine(ep), LS.engine(ep)
    h1 = [sha(e1.render_lowres(t)[0]) for t in ts]
    h2 = [sha(e2.render_lowres(t)[0]) for t in ts]
    check('determinisme : deux moteurs, memes octets', h1 == h2, f'{h1} != {h2}')
    h3 = [sha(e1.render_lowres(t)[0]) for t in ts]
    check('determinisme : rejouer le meme instant donne la meme image', h1 == h3)
    # autre processus (pas de cache partage, pas d'horloge)
    code = ("import sys, hashlib, numpy as np; sys.path.insert(0, r'%s'); sys.path.insert(0, r'%s');"
            "import light_sheet as LS; e = LS.engine(LS.scene());"
            "print(' '.join(hashlib.sha1(np.asarray(e.render_lowres(t)[0]).tobytes()).hexdigest()[:16] for t in LS.shot_times(LS.scene())))"
            % (ROOT, os.path.join(ROOT, 'tools')))
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, cwd=ROOT)
    out = [l for l in r.stdout.split('\n') if l.strip()]
    check('determinisme : un autre processus donne les memes octets', bool(out) and out[-1].split() == h1, (r.stdout + r.stderr)[-400:])
    # les formes d'onde restent bornees et ne dependent que du temps
    for shape in LT.SHAPES:
        vals = [LT.wave(shape, i / 60., 6., .8) for i in range(600)]
        check(f'onde {shape} : bornee dans [1-depth, 1]', all(.199 <= v <= 1.0001 for v in vals), f'{min(vals):.3f}..{max(vals):.3f}')
        check(f'onde {shape} : rejouable', [LT.wave(shape, i / 60., 6., .8) for i in range(600)] == vals)


# ------------------------------------------------------------------ 3. repli explicite
def fallback_checks():
    cam = ((0., 1.6, 0.), 0., 0., 0., 1.)
    class Sc: ambient = (.05, .05, .06); fog = (.01, .01, .01)
    cases = [
        ({'mood': 'mauve'}, 'mood', 'ambiance inconnue'),
        ({'mood': 'red', 'mood_power': 9}, 'mood_power', 'puissance hors bornes'),
        ({'halo': {'from': 'x', 'color': 'rose'}}, 'color', 'couleur inconnue'),
        ({'halo': {'color': 'red'}}, 'from', '« from » manquant'),
        ({'halo': 'console'}, 'halo', 'halo illisible'),
        ({'flicker': {'shape': 'zigzag'}}, 'shape', 'forme inconnue'),
        ({'flicker': {'on': ['mur']}}, 'on', 'cible inconnue'),
        ({'storm': 'fort'}, 'storm', 'orage illisible'),
        ({'tempete': True}, 'inconnue', 'cle inconnue'),
    ]
    for block, needle, label in cases:
        ctx = Ctx({})
        txt = grab(lambda: LT.plan(ctx, {'lighting': block}, St(), {}, cam, Sc(), [], 0, 0., 0., 0.))
        ws = getattr(ctx, 'lighting_warnings', [])
        check(f'repli annonce : {label}', any(needle in w for w in ws) and '[eclairage]' in txt, f'{ws} / {txt!r}')
    # un repli ne doit jamais faire planter le rendu
    ctx = Ctx({})
    L, extra = LT.plan(ctx, {'lighting': {'mood': 'mauve', 'halo': [{'from': 'x', 'color': 'rose', 'power': 'beaucoup'}],
                                          'flicker': {'shape': 'zigzag', 'rate': 'vite'}, 'back': 'oui', 'storm': {'at': ['tard']}}},
                       St(), {}, cam, Sc(), [], 0, 0., 0., 0.)
    check('un bloc entierement faux rend quand meme (replis)', isinstance(extra, list))
    check('un bloc entierement faux est entierement signale', len(getattr(ctx, 'lighting_warnings', [])) >= 5,
          str(getattr(ctx, 'lighting_warnings', [])))


# ------------------------------------------------------------------ 4. budget CPU
def budget_checks():
    ep = LS.scene(); before = LS.strip_lighting(ep); ts = LS.shot_times(ep)
    eb, ea = LS.engine(before), LS.engine(ep)
    for t in ts:
        Lb = build_frame(eb.ctx, t)[2]; La = build_frame(ea.ctx, t)[2]
        sb = sum(1 for l in Lb if len(l) > 4 and l[4]); sa = sum(1 for l in La if len(l) > 4 and l[4])
        check(f'budget t={t:5.2f} : pas un rayon d\'ombre de plus', sa <= sb, f'{sb} -> {sa}')
        check(f'budget t={t:5.2f} : au plus {LT.MAX_EXTRA} lumieres ajoutees', len(La) - len(Lb) <= LT.MAX_EXTRA, f'{len(Lb)} -> {len(La)}')
    # la demande deraisonnable est bornee, pas honoree
    cam = ((0., 1.6, 0.), 0., 0., 0., 1.)
    class Sc: ambient = (.05, .05, .06); fog = (.01, .01, .01)
    ctx = Ctx({})
    halos = [{'from': [0, 2], 'color': 'green', 'power': 1} for _ in range(8)]
    L, extra = LT.plan(ctx, {'lighting': {'halo': halos, 'back': 1.5}}, St(), {}, cam, Sc(), [], 0, 0., 0., 0.)
    check('8 halos demandes : le plafond tient', len(extra) <= LT.MAX_EXTRA, str(len(extra)))
    check('8 halos demandes : le plafond est annonce', any('halo' in w for w in ctx.lighting_warnings))
    check('aucune lumiere ajoutee ne lance de rayon d\'ombre', all(l[4] is False for l in extra))


# ------------------------------------------------------------------ 5. la lumiere fait ce qu'elle dit
def _mean_rgb(a): return np.asarray(a, np.float32).reshape(-1, 3).mean(0)

def effect_checks():
    ep = LS.scene(); before = LS.strip_lighting(ep)
    eb, ea = LS.engine(before), LS.engine(ep)
    # plan 1 : halo vert -> le vert gagne plus que le rouge
    b = _mean_rgb(eb.render_lowres(2.25)[0]); a = _mean_rgb(ea.render_lowres(2.25)[0])
    check('halo vert : le vert monte plus que le rouge', (a[1] - b[1]) > (a[0] - b[0]) + 2., f'dR {a[0]-b[0]:.1f} dV {a[1]-b[1]:.1f}')
    # plan 2 : alarme rouge -> le rouge domine
    b = _mean_rgb(eb.render_lowres(6.53)[0]); a = _mean_rgb(ea.render_lowres(6.53)[0])
    check('alarme rouge : le rouge domine', (a[0] - b[0]) > (a[1] - b[1]) + 5. and a[0] > a[2], f'dR {a[0]-b[0]:.1f} dV {a[1]-b[1]:.1f} dB {a[2]-b[2]:.1f}')
    # le clignotement fait vraiment varier l'image dans le plan 2 (creux vs crete)
    lo = _mean_rgb(ea.render_lowres(5.05)[0]).mean(); hi = _mean_rgb(ea.render_lowres(6.53)[0]).mean()
    check('clignotement : creux et crete nettement differents', hi > lo * 1.6, f'{lo:.1f} vs {hi:.1f}')
    # l'eclair est bref : tres clair juste apres la frappe, revenu a la normale 1 s plus tard
    t_strike = 8.05 + .75; peak = _mean_rgb(ea.render_lowres(t_strike)[0]).mean(); after = _mean_rgb(ea.render_lowres(t_strike + 1.0)[0]).mean()
    check('eclair : flash bref puis retour', peak > after * 1.5, f'{peak:.1f} -> {after:.1f}')
    # contre-jour : le fond gagne plus de lumiere que le sujet (c'est la definition)
    img_b = np.asarray(eb.render_lowres(11.56)[0], np.float32); img_a = np.asarray(ea.render_lowres(11.56)[0], np.float32)
    h, w = img_b.shape[:2]
    sub = (slice(int(h * .35), int(h * .8)), slice(int(w * .3), int(w * .7)))      # le sujet occupe le centre du cadre
    edge = (slice(0, int(h * .3)), slice(0, w))                                   # le fond : haut du cadre
    d_sub = (img_a[sub] - img_b[sub]).mean(); d_edge = (img_a[edge] - img_b[edge]).mean()
    check('contre-jour : le fond gagne plus que le sujet', d_edge > d_sub, f'fond {d_edge:+.1f} sujet {d_sub:+.1f}')


# ------------------------------------------------------------------ 6. lisibilite des visages
def face_checks():
    """qc.py appelle « image presque noire » une luminance moyenne < .035 ; on applique le meme seuil
    a la zone du visage, sur tout le plan 2 (celui qui clignote a 7 Hz)."""
    ep = LS.scene(); before = LS.strip_lighting(ep)
    eb, ea = LS.engine(before), LS.engine(ep)
    worst_a = worst_b = 9.
    for i in range(24):
        t = 4.05 + i * (4.0 / 24)
        for eng, key in ((eb, 'b'), (ea, 'a')):
            img, _, _, _ = eng.render_lowres(t)
            o = eng.qc_observe(t) or {}
            p = (o.get('people') or {}).get('lea') or {}
            uv = p.get('uv')
            if not uv: continue
            H, W = img.shape[:2]
            cx = int((uv[0] + 1) / 2 * W); cy = int((1 - uv[1]) / 2 * H)
            x0, x1 = max(0, cx - 10), min(W, cx + 10); y0, y1 = max(0, cy - 10), min(H, cy + 10)
            if x1 <= x0 or y1 <= y0: continue
            lum = (np.asarray(img[y0:y1, x0:x1], np.float32) / 255. * np.array([.3, .59, .11], np.float32)).sum(-1).mean()
            if key == 'a': worst_a = min(worst_a, lum)
            else: worst_b = min(worst_b, lum)
    check('visage lisible pendant le clignotement (seuil qc .035)', worst_a >= .035, f'pire luminance {worst_a:.3f}')
    print(f'      (reference sans intention : pire luminance {worst_b:.3f} ; avec intention : {worst_a:.3f})')


if __name__ == '__main__':
    opt_in_checks(); determinism_checks(); fallback_checks(); budget_checks(); effect_checks(); face_checks()
    print('\n' + ('Tout est OK' if not FAIL else f'{len(FAIL)} echec(s) : ' + ', '.join(FAIL)))
    sys.exit(1 if FAIL else 0)
