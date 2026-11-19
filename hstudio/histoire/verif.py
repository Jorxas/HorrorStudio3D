"""Étape VÉRIFIER du kit : contrôles rapides SANS rendu sur les épisodes construits, puis le contrôle de scène du moteur
(tools/verifier_scene.py, voir docs/QA_SCENE.md) sur chaque version quand il est installé.

Contrôles du kit (ERREUR = à corriger avant de rendre ; ATTENTION = à regarder sur l'aperçu) :
  * titre unique partout, titre du HUD qui tient dans l'image, étiquette PARTIE seulement sur les Shorts ;
  * parties de 3 min au plus ; plans ni trop longs sans coupe ni trop courts ;
  * caméra : champ plausible, pas collée à la tête qu'elle suit, pas de clé jamais vue ;
  * acteurs déclarés dans CAST, expressions / gestes / objets tenus connus du moteur, lieux déclarés ;
  * bruitages : nom connu (sons fabriqués, banque réelle, synthèse), instant dans le film, durée des nappes.

    python -m hstudio.histoire verifier <dossier> [--images] [--sans-scene]
      --images : le contrôle de scène regarde aussi des images basse définition du vrai peintre (plus lent)"""
import math
import os
import subprocess
import sys

from .common import ENGINE, KitError, Story, read_json, write_json
from . import projet as PJ

HEAD_SIZE = {'ps1': .55, 'voxel': .7}       # visible head height in metres, hair included (PS1 cube 0.40 m; VOXEL about 0.5 m)
MAX_FACE_SHARE = .8                           # coarse: the scene QA (tools/verifier_scene.py) measures it exactly and blocks at 100 %
MIN_CAM_DIST = .8
LONG_SETUP, SHORT_SETUP = 9.0, .5
SCENE_TOOL = os.path.join(ENGINE, 'tools', 'verifier_scene.py')


def known_names():
    sys.path.insert(0, ENGINE)
    from hstudio.engines.pixel3d import assets as A, poses as P
    from hstudio.engines.pixel3d import hotel_cast as HC
    from hstudio.engines.pixel3d import sets as _S                     # enregistre aussi les objets tenus détaillés `od_*` (pixel3d/objets.py), lots compris
    from hstudio.acting import gestures as G
    from hstudio.engines.pixel3d import objets as OD
    OD.register()
    holds = set(P.HOLD_ITEMS) | set(HC.NEW_ITEMS) | {'none', None, 'flute', 'flute_pair', 'wine_glass', 'bouquet', 'fan', 'letter'}
    return set(A.FACE_KINDS), set(G.GESTURES) | {'idle', None}, holds


def sound_known(name):
    sys.path.insert(0, ENGINE)
    from hstudio.audio import fabriques as FB, synth as S
    from . import mixage as MX
    return FB.has(name) or MX.library().has(name) or name in S.SFX


def _track_pos(keys, t):
    ks = [k for k in keys if 'p' in k]
    if not ks: return None
    if t <= ks[0]['t']: return ks[0]['p']
    for a, b in zip(ks, ks[1:]):
        if a['t'] <= t <= b['t']:
            if b.get('cut'): return a['p'] if t < b['t'] else b['p']
            u = (t - a['t']) / max(b['t'] - a['t'], 1e-6)
            return [a['p'][i] + (b['p'][i] - a['p'][i]) * u for i in range(3)]
    return ks[-1]['p']


def _effect_types():
    sys.path.insert(0, ENGINE)
    from hstudio.engines.pixel3d import effects as FX
    try:
        from hstudio.capabilities import extensions as _EXT
        _EXT.load_all()
    except Exception: pass
    return set(FX.EFFECTS)


def check_version(st, v, mod, style, faces, gestures, holds, out):
    vdir = st.version_dir(v['id']); ep = read_json(os.path.join(vdir, 'episode.json')); lines = read_json(os.path.join(vdir, 'lines.json'))
    sys.path.insert(0, ENGINE)
    from hstudio.engines.pixel3d.frame import Timeline
    tl = Timeline(ep, lines, float(ep['duration']))
    err = lambda m: out['erreurs'].append(f"{v['id']} : {m}")
    warn = lambda m: out['attentions'].append(f"{v['id']} : {m}")
    first = v['lines'][0]
    if style == 'voxel':                       # 6/11/2026 : les expressions qui n'existent qu'en VOXEL (« worried »…) sont connues d'une histoire VOXEL
        try:
            from hstudio.voxelgpu.contract import EXPRESSIONS as _VOX_EXPR
            faces = set(faces) | set(_VOX_EXPR)
        except Exception: pass
    if ep.get('title') != str(mod.TITRE): err(f"titre « {ep.get('title')} » ≠ « {mod.TITRE} »")
    lab = ep['hud'].get('part', '')
    if v['id'] == 'long_16x9' and lab: err('le film long ne doit pas porter d\'étiquette PARTIE')
    limit = PJ.part_limit(mod)
    if limit > 0 and v['id'].startswith('partie') and v['dur'] > limit + .01: err(f"vidéo de {v['dur']:.1f} s : dépasse la limite explicitement demandée de {limit:g} s")
    if v['id'].startswith('partie') and v['dur'] < 20: warn(f"Short très court ({v['dur']:.1f} s)")
    for k, sh in enumerate(ep['shots']):
        a, b = tl.spans[k]; dur = b - a; P = f"P{k} (phrases {sh['lines'][0] + first}-{sh['lines'][1] + first})"
        if sh.get('set') not in ep['sets']: err(f"{P} : lieu « {sh.get('set')} » absent de LIEUX")
        for o in sh.get('objects') or []:         # 6/11/2026 : un objet de plan de type inconnu est IGNORÉ par le moteur sans rien dire (ex. `{'type': 'light'}` : il n'existe pas)
            if isinstance(o, dict) and o.get('type') not in _effect_types():
                warn(f"{P} : objet de plan « {o.get('type')} » inconnu : le moteur l'ignore (types connus : {', '.join(sorted(_effect_types()))}). Pour éclairer : blocs émissifs `light` dans le décor (cinema_salle : option `projecteurs`)")
        for o in sh.get('objects') or []:         # 6/11/2026 : un assemblage invalide (ex. `emissive: True` au lieu d'un nombre) était écarté SANS message : on le dit
            if isinstance(o, dict) and o.get('type') == 'mover' and o.get('thing') == 'prop:assemblage':
                try:
                    from hstudio.engines.pixel3d.assemblage import validate as _validate_assembly
                    _validate_assembly(o)
                except ValueError as e: err(f"{P} : {e} (un `mover` « prop:assemblage » invalide n'est pas dessiné ; `emissive` et `reflect` sont des NOMBRES, pas True/False)")
        keys = [kk for kk in sh['camera']['keys'] if kk['t'] < 500]
        starts = [0.] + [kk['t'] for kk in keys[1:] if kk.get('cut') and kk['t'] < dur]
        bounds = starts + [dur]
        for i in range(len(starts)):
            seg = bounds[i + 1] - bounds[i]
            if seg > LONG_SETUP and not any(kk['t'] > bounds[i] + .3 and kk['t'] < bounds[i + 1] - .3 for kk in keys): warn(f"{P} : cadrage fixe de {seg:.1f} s (ajoute un mouvement ou une coupe)")
            if seg < SHORT_SETUP and dur > SHORT_SETUP: warn(f"{P} : cadrage de {seg:.2f} s seulement (illisible)")
        for kk in keys:
            if kk['t'] > dur + .05: warn(f"{P} : clé de caméra à {kk['t']:.2f} s après la fin du plan ({dur:.2f} s) : jamais vue")
            if not 12 <= kk['fov'] <= 100: err(f"{P} : champ {kk['fov']} hors de [12, 100]")
            look = kk['look']
            if isinstance(look, dict):
                tr = sh['tracks'].get(look.get('on'))
                p = _track_pos(tr, kk['t']) if tr else None
                if p is not None:
                    hp = [p[0] + look.get('dx', 0.), p[1] + look.get('h', 1.6), p[2] + look.get('dz', 0.)]
                    d = math.dist(kk['pos'], hp)
                    H = 2 * d * math.tan(math.radians(kk['fov']) / 2) * (.72 if v['aspect'] == '16:9' else 1.)
                    share = HEAD_SIZE[style] / max(H, 1e-6)
                    if share > MAX_FACE_SHARE: warn(f"{P} à {kk['t']:.2f} s : la tête de {look['on']} prend {share * 100:.0f} % de la hauteur de l'image (caméra à {d:.2f} m, champ {kk['fov']}) : recule ou élargis")
                    elif d < MIN_CAM_DIST: warn(f"{P} : caméra à {d:.2f} m de la tête de {look['on']} (trop près : déformation, cheveux)")
            elif math.dist(kk['pos'], look) < .3: err(f"{P} : la caméra vise un point à moins de 30 cm d'elle")
        for aid, ks in sh['tracks'].items():
            if aid == '_cam': continue
            if aid not in ep['cast']: warn(f"{P} : acteur « {aid} » absent de CAST (il aura l'apparence par défaut)")
            for kk in ks:
                if 'face' in kk and kk['face'] not in faces: warn(f"{P} : expression « {kk['face']} » inconnue de {aid}")
                if 'gesture' in kk and kk['gesture'] not in gestures: warn(f"{P} : geste « {kk['gesture']} » inconnu de {aid}")
                if 'hold' in kk and kk['hold'] not in holds: warn(f"{P} : objet tenu « {kk['hold']} » inconnu de {aid}")
                if kk['t'] > dur + .05 and kk is not ks[0]: warn(f"{P} : clé de {aid} à {kk['t']:.2f} s après la fin du plan : jamais vue")
    if v['id'] in ('long_16x9', 'complet_9x16') or v['id'].startswith('partie'):
        _hud_fits(ep, v, err)


def _hud_fits(ep, v, err):
    try:
        from PIL import ImageFont, Image, ImageDraw
        from hstudio.paths import FONT_PIXEL
        f = ImageFont.truetype(FONT_PIXEL, 40); d = ImageDraw.Draw(Image.new('RGB', (8, 8)))
    except Exception:
        return
    W = 1920 if v['aspect'] == '16:9' else 1080
    for t in ep['hud'].get('title', [])[:2]:
        w = d.textlength(str(t).upper(), font=f)
        if w + 2 * 52 > W: err(f"titre du HUD « {t} » trop large ({w:.0f} px sur {W}) : coupe-le avec TITRE_HUD = ['…', '…']")


def _quiet(text):
    """the scene tool's output without the engine's repeated notices"""
    keep = [l for l in (text or '').splitlines() if l.strip() and not (l.lstrip().startswith('[') and 'BLOQUANT' not in l)]
    return '\n'.join(keep)


def check(folder, scene=True, images=False, log=print):
    st = Story(folder)
    dec, mod = PJ.build(folder, log, quiet=True)
    faces, gestures, holds = known_names()
    out = {'erreurs': [], 'attentions': [], 'scene': {}}
    for v in dec['versions']: check_version(st, v, mod, dec['style'], faces, gestures, holds, out)
    cues = read_json(st.cues); D = dec['duree_long']
    for c in cues:
        if not sound_known(c['name']) and not c.get('file'): out['erreurs'].append(f"bruitage « {c['name']} » à {c['t']:.2f} s : nom inconnu (python -m hstudio.histoire catalogue --sons)")
        if not 0 <= c['t'] <= D: out['erreurs'].append(f"bruitage « {c['name']} » à {c['t']:.2f} s : hors du film (0 à {D:.1f} s)")
        if not .05 <= c['gain'] <= 1.5: out['attentions'].append(f"bruitage « {c['name']} » à {c['t']:.2f} s : gain {c['gain']} inhabituel (0,3 à 1,3)")
    titles = {read_json(os.path.join(st.version_dir(v['id']), 'episode.json'))['title'] for v in dec['versions']}
    if len(titles) > 1: out['erreurs'].append(f'titres différents selon les versions : {titles}')
    if scene:
        if os.path.exists(SCENE_TOOL):
            for v in dec['versions']:
                if v['id'] == 'complet_9x16' and any(x['id'].startswith('partie') for x in dec['versions']):
                    log('complet_9x16 : aperçu intégral ; contrôle de scène sur les Shorts réellement livrés ci-dessous.')
                    continue
                vdir = st.version_dir(v['id'])
                log(f'contrôle de scène (tools/verifier_scene.py) : {v["id"]}…')
                cmd = [sys.executable, SCENE_TOOL, vdir, '--format', v['aspect'], '--style', dec['style']] + (['--images'] if images else [])
                r = subprocess.run(cmd, cwd=ENGINE, capture_output=True, text=True, encoding='utf-8', errors='replace',
                                   env=dict(os.environ, PYTHONIOENCODING='utf-8'))
                out['scene'][v['id']] = dict(code=r.returncode, sortie=(r.stdout or '')[-4000:], erreurs=(r.stderr or '')[-2000:])
                log(_quiet(r.stdout)[-3000:])
                import re as _re
                m_ = _re.search(r'(\d+) bloquant\(s\), (\d+) à revoir', r.stdout or '')
                if m_ and int(m_.group(2)): out['attentions'].append(f"{v['id']} : contrôle de scène : {m_.group(2)} point(s) à revoir -> {os.path.join(vdir, '_qa', 'rapport_qa.md')}")
                if r.returncode != 0: out['erreurs'].append(f"{v['id']} : le contrôle de scène signale des défauts (code {r.returncode}, voir ci-dessus et docs/QA_SCENE.md)")
        else:
            out['attentions'].append('tools/verifier_scene.py absent : contrôle de scène non fait (voir docs/QA_SCENE.md quand il existera)')
    write_json(os.path.join(st.construit, 'verification.json'), out)
    for m in out['erreurs']: log('ERREUR    ' + m)
    for m in out['attentions']: log('ATTENTION ' + m)
    log(f"{len(out['erreurs'])} erreur(s), {len(out['attentions'])} attention(s) → {os.path.join(st.construit, 'verification.json')}")
    if out['erreurs']: raise KitError('corrige les erreurs avant de rendre')
    return out
