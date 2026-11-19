"""Pont entre le studio (pipeline voix -> calage -> rendu) et le moteur VOXEL V4 (GPU).

Le studio garde TOUT : projets, voix, calage (`lines.json`), contrôle du fichier produit, aperçu, publication.
Seul le dernier maillon change, et seulement pour un projet qui le demande (`render_engine: "voxel"` dans son
project.json, choisi dans l'interface) : au lieu de la lancer de rayons CPU (PIXEL 3D), le plan est peint sur le GPU.

Un épisode « voxel » est l'épisode du DSL de `docs/VOXELGPU.md` (stage, casts, actors, actions, camera...). Le pont
ajoute seulement ce que le studio sait et pas lui : le temps. Un plan peut porter `"lines": [a, b]` (comme les plans
PIXEL 3D) au lieu de `"dur"` : sa durée et sa parole viennent alors de la voix calée, les sous-titres viennent des
phrases, la voix du projet est posée sur le son (le lit sonore baisse sous chaque phrase). Rien n'est remplacé en
silence : un plan sans monde voxel, un acteur absent, une durée impossible = une erreur claire avant tout rendu.
"""
import json, os, re, shutil, subprocess, time
from pathlib import Path
from . import contract as C, director, render, qa, audio as VA
from .worlds import WORLDS

KEY = 'render_engine'                       # clé de project.json (et de settings.json en valeur par défaut globale)
CRF = {'max': 16, 'standard': 20, 'tiktok': 20}
TAG = {'9:16': 'short_9x16', '16:9': 'long_16x9'}
SIZE = {'9:16': (1080, 1920), '16:9': (1920, 1080)}
MUSIC_OF = {'horror': 'horror', 'horreur': 'horror', 'thriller': 'horror', 'noir': 'mystery', 'mystery': 'mystery', 'comedy': 'comedy', 'romance': 'romance',
            'drama': 'sad', 'sad': 'sad', 'adventure': 'adventure', 'action': 'action', 'scifi': 'epic', 'fantasy': 'epic', 'epic': 'epic', 'calm': 'calm'}
_TAGS = re.compile(r'\[[^\]]*\]')


def wants_voxel(pr, settings=None):
    return str(pr.meta.get(KEY) or (settings or {}).get(KEY) or 'pixel3d').lower() == 'voxel'


def _clean(text):
    return re.sub(r'\s+', ' ', _TAGS.sub('', text or '')).strip()


def check(ep):
    """-> liste de problèmes (français) qui empêchent de peindre cet épisode sur le moteur voxel ; [] si tout va bien"""
    bad = []
    if not ep.get('shots'): return ['aucun plan dans episode.json']
    casts = set((ep.get('casts') or {}).keys())
    if not casts: bad.append("pas de « casts » : le moteur voxel a besoin de la liste des personnages (preset noe|lina|npc|alien)")
    for i, s in enumerate(ep['shots']):
        if s.get('set') is not None:               # un lieu de PIXEL 3D peint par VOXEL (b_sets.py) : le nom doit être dans `sets` de l'épisode, ou la spec écrite dans le plan
            if isinstance(s['set'], str) and s['set'] not in (ep.get('sets') or {}): bad.append(f"plan {i} : lieu « {s['set']} » absent de `sets` (définis : {', '.join(ep.get('sets') or {}) or 'aucun'})")
        elif s.get('stage') not in WORLDS:
            what = s.get('stage') or s.get('world')
            bad.append(f"plan {i} : monde « {what} » inconnu du moteur voxel (disponibles : {', '.join(WORLDS)}) ; ou donne un lieu de PIXEL 3D avec `set`")
        if 'dur' not in s and 'lines' not in s: bad.append(f'plan {i} : ni « dur » ni « lines »')
        for a in [x.get('id') for x in s.get('actors') or []] + [x.get('who') for x in s.get('actions') or []]:
            if a and casts and a not in casts: bad.append(f'plan {i} : le personnage « {a} » n’est pas dans casts')
    return bad


def timed_episode(pr, ep, lines, duration):
    """épisode voxel avec les durées, la parole, les sous-titres et le son tirés de la voix calée du projet"""
    ep = json.loads(json.dumps(ep)); shots = ep['shots']; n = len(shots)
    start = []
    for i, s in enumerate(shots):
        if 'lines' in s:
            a = max(0, min(len(lines) - 1, int(s['lines'][0]))); start.append(0. if i == 0 else float(lines[a]['start']))
        else: start.append(None)
    for i in range(n):
        if start[i] is None: start[i] = (start[i - 1] + float(shots[i - 1]['dur'])) if i else 0.
    for i, s in enumerate(shots):
        end = start[i + 1] if i + 1 < n else duration
        if 'dur' not in s: s['dur'] = round(max(.5, end - start[i]), 3)
        if 'lines' in s and not s.get('speech'):
            ids = {x.get('id') for x in s.get('actors') or []} | {x.get('who') for x in s.get('actions') or []}
            sp = []
            for j in range(int(s['lines'][0]), min(len(lines) - 1, int(s['lines'][1])) + 1):
                who = lines[j].get('speaker')
                if who in ids: sp.append([round(max(0., lines[j]['start'] - start[i]), 3), round(min(s['dur'], lines[j]['end'] - start[i]), 3), who])
            if sp: s['speech'] = sp
        s.pop('lines', None)
    ep['duration'] = round(float(duration), 3)
    if not ep.get('captions'):
        ep['captions'] = [{'t0': round(float(l['start']), 3), 't1': round(float(l['end']), 3), 'text': _clean(l.get('text'))} for l in lines if _clean(l.get('text')) and not l.get('no_subtitle')]
    if not ep.get('audio'):
        style = MUSIC_OF.get(str(ep.get('music') or ep.get('genre') or 'horror').lower(), 'mystery')
        ep['audio'] = {'music': [{'t0': 0., 't1': ep['duration'], 'style': style, 'gain': .35, 'fade': 1.5}], 'foley': {'steps': True, 'gain': .5}}
    a = ep['audio']
    if pr.exists('voice.mp3') and 'voice' not in a: a['voice'] = {'wav': pr.p('voice.mp3'), 'duck': .55, 'bed_ceiling': .35}
    ep.setdefault('genre', 'horror' if str(ep.get('music', '')).startswith('horr') else ep.get('genre', 'neutral'))
    return ep


def contract_of(pr, aspect, log=print, spacing=None):
    from ..pipeline import merged_lines, duration_of
    lines, ep = merged_lines(pr)
    from . import from_ps1
    if from_ps1.is_ps1(ep):                       # épisode du studio (format PIXEL 3D) : la logique (régie, caméras, collisions) reste celle du style PS1, VOXEL ne fait que peindre
        from ..acting import background as _bg
        ep = _bg.apply(ep)
        dur = float(ep['duration']) if ep.get('duration') else lines[-1]['end'] + 1.2
        side = timed_episode(pr, ep, lines, dur)
        c = from_ps1.build(ep, lines, dur, aspect, side.get('fps', 24), log, extras=dict(captions=side['captions'], audio=side['audio'], genre=side.get('genre')))
        from ..shot_preview import apply_to_contract; c = apply_to_contract(c, ep)      # fondus / flashs de plan (`fx`) : l'aperçu d'un plan et le rendu final font la même chose
        problems = C.validate(c)
        if problems: raise RuntimeError('Contrat voxel refusé : ' + ' ; '.join(problems[:6]))
        return c
    bad = check(ep)
    if bad: raise RuntimeError('Cet épisode ne peut pas être peint par le moteur VOXEL V4 :\n  - ' + '\n  - '.join(bad[:12]) + '\nChoisis « PIXEL 3D (V3) » pour ce projet, ou donne un monde voxel à chaque plan.')
    dur = float(ep['duration']) if ep.get('duration') else lines[-1]['end'] + 1.2
    vep = timed_episode(pr, ep, lines, dur)
    if spacing is not None: vep['spacing'] = spacing
    else: vep.setdefault('spacing', True)          # épisodes du studio : les corps ne se traversent pas, on parle à distance de conversation, les décors du plan sont des obstacles (b_space.py)
    c = director.build(vep, aspect, vep.get('fps'))
    problems = C.validate(c)
    if problems: raise RuntimeError('Contrat voxel refusé : ' + ' ; '.join(problems[:6]))
    return c


def step_mix(pr, settings, log=print):
    """le « mix.wav » du studio, composé sur le contrat voxel (voix, lit sonore baissé sous la voix, pas, musique)"""
    c = contract_of(pr, '9:16', log); os.makedirs(pr.p('work'), exist_ok=True)
    VA.compose(c, pr.p('mix.wav'))
    log(f'Mixage voxel terminé ({c["duration"]:.1f} s).')


def _stills(pr, settings, aspect, times, outdir):
    """images fixes peintes par le moteur voxel (GPU) aux instants donnés -> {t: chemin PNG}"""
    c = contract_of(pr, aspect); work = Path(pr.p('work', 'voxel_stills')); work.mkdir(parents=True, exist_ok=True)
    cpath = work / 'contract.json'; C.save(c, cpath); outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    w, h = render.SIZES[aspect]
    render.run_painter(cpath, None, settings.get('voxel_gpu') or 'nvidia', (w, h), stills=times, stills_dir=outdir, quiet=True, fallback=True)
    return c, {t: outdir / f't_{t:.2f}.png' for t in times}


def step_preview(pr, settings, aspect='9:16', log=print):
    """une image par plan (au milieu), peinte par le moteur voxel -> planche de contrôle + JPEG par plan"""
    from PIL import Image
    c = contract_of(pr, aspect); st = c['stages']
    times = [round(s['t0'] + (s['t1'] - s['t0']) * .6, 2) for s in st]
    tmp = pr.p('work', 'voxel_prev'); _, files = _stills(pr, settings, aspect, times, tmp)
    d = pr.p('preview'); os.makedirs(d, exist_ok=True)
    for f in os.listdir(d): os.remove(os.path.join(d, f))
    thumbs = []
    for k, t in enumerate(times):
        im = Image.open(files[t]).convert('RGB'); im.save(os.path.join(d, f'shot_{k:03d}.jpg'), quality=88)
        thumbs.append(im.resize((max(1, im.width // 5), max(1, im.height // 5))))
    cols = 10 if aspect == '9:16' else 6; tw, th = thumbs[0].size
    sheet = Image.new('RGB', (tw * cols, th * ((len(thumbs) + cols - 1) // cols)))
    for k, im in enumerate(thumbs): sheet.paste(im, ((k % cols) * tw, (k // cols) * th))
    sheet.save(pr.p('preview_sheet.jpg'), quality=85)
    log(f'Aperçu VOXEL V4 : {len(thumbs)} plans.')
    return [s['t0'] for s in st]


def step_qc(pr, settings, aspect='9:16', log=print, frames=True):
    """contrôle qualité sous le moteur voxel : la mise en scène est auditée À LA CONSTRUCTION du contrat (corps, visages,
    caméras, disparitions : `director.build` refuse ce qui est faux), puis le fichier produit est vérifié sur disque"""
    from .. import mediacheck as M
    c = contract_of(pr, aspect)                    # lève une erreur claire si l'audit de mise en scène échoue
    want = SIZE[aspect]; tag = TAG[aspect]; d = pr.p('renders')
    found = sorted(os.path.join(d, f) for f in (os.listdir(d) if os.path.isdir(d) else []) if f.endswith('.mp4') and tag in f and '.ECARTE-' not in f)
    rep = {'engine': 'voxel-v4', 'aspect': aspect, 'score': None, 'issues': [], 'staging': f'contrat voxel construit et validé : {len(c["stages"])} plans, {c["duration"]:.1f} s, audit de mise en scène sans refus'}
    if not found: rep['encoded'] = {'ok': None, 'reason': 'aucun rendu ' + aspect + ' sur le disque'}
    else:
        v = M.describe(found[-1], want=want); rep['encoded'] = v
        if not v['ok']: rep['issues'].append({'level': 'error', 'code': 'render_unusable', 'message': v['reason']})
    pr.write_json(f"qc_{aspect.replace(':', 'x')}.json", rep)
    log('Contrôle (moteur VOXEL V4) : ' + rep['staging'] + ('. ' + M.summary(rep['encoded']) if found else '. Aucun rendu à vérifier.'))
    return rep


def step_thumbnail(pr, settings, log=print):
    """image brute du film (sans texte) en 16:9 et en 9:16 : le texte et l'habillage viennent de la miniature finale"""
    from PIL import Image
    for aspect, name, size in (('16:9', 'thumbnail_16x9.jpg', (1280, 720)), ('9:16', 'cover_9x16.jpg', (1080, 1920))):
        c = contract_of(pr, aspect); t = round(c['duration'] * .35, 2)
        _, files = _stills(pr, settings, aspect, [t], pr.p('work', 'voxel_thumb_' + aspect.replace(':', 'x')))
        Image.open(files[t]).convert('RGB').resize(size, Image.LANCZOS).save(pr.p(name), quality=92)
    log('Images de miniature (moteur VOXEL V4) : thumbnail_16x9.jpg et cover_9x16.jpg, sans texte.')


def step_render(pr, settings, aspect='9:16', quality=None, progress=None, log=print, frames=None, verify='full'):
    from .. import mediacheck as M
    q = quality or settings.get('quality', 'max'); W, H = SIZE[aspect]
    c = contract_of(pr, aspect, log)
    VA.compose(c, pr.p('mix.wav'))          # toujours refait : un mix.wav du moteur PIXEL 3D ne correspond pas à ce film
    os.makedirs(pr.p('renders'), exist_ok=True); os.makedirs(pr.p('work'), exist_ok=True)
    tag = TAG[aspect]; out = pr.p('renders', f'{pr.slug}_{tag}{"_tiktok" if q == "tiktok" else ""}.mp4'); tmp = pr.p('work', f'voxel_{tag}.mp4')
    work = Path(pr.p('work', f'voxel_{tag}')); work.mkdir(parents=True, exist_ok=True)
    cpath = work / 'contract.json'; C.save(c, cpath)
    t0 = time.time(); n = int(round(c['duration'] * c['fps']))
    if progress: progress(0., f'moteur VOXEL V4 (GPU) : {n} images à peindre')
    try:
        gpu = (settings.get('voxel_gpu') or 'nvidia')
        for transport in ('bin', 'b64'):     # le transport binaire a échoué sur certains films (docs/FUSION_FINALE §4) : le b64, plus lent, passe
            try:
                render.run_painter(cpath, work / 'video_only.mp4', gpu, (W, H), attest=work / 'attestation.json', crf=CRF.get(q, 16), quiet=True, fallback=True, transport=transport)
                break
            except RuntimeError as e:
                if transport == 'b64' or 'Failed to fetch' not in str(e): raise
                log('Transport binaire GPU refusé (Failed to fetch) : nouvel essai en base64, plus lent.')
        render.mux(work / 'video_only.mp4', pr.p('mix.wav'), tmp, c['duration'])
    except BaseException as e:
        log(f'Rendu {aspect} (voxel) interrompu : {type(e).__name__}: {str(e)[:300]}'); raise
    if q == 'tiktok':                       # même plafond de débit que la qualité « tiktok » du studio
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', tmp, '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-maxrate', '1300k', '-bufsize', '2600k', '-c:a', 'copy', '-movflags', '+faststart', out], check=True)
    else: shutil.copyfile(tmp, out)
    v = M.describe(out, want=(W, H), full=verify == 'full')
    if not v['ok']:
        kept = M.quarantine(out, v['reason'])
        raise RuntimeError(f"Rendu {aspect} inutilisable : {v['reason']}. Écarté sous {os.path.basename(kept)}.")
    att = json.loads((work / 'attestation.json').read_text(encoding='utf-8')) if (work / 'attestation.json').exists() else {}
    pr.write_json(f'verify_{tag}.json', dict(v, engine='voxel-v4', gpu=(att.get('webgl') or {}).get('renderer'), frames_expected=n, seconds=round(time.time() - t0, 1)))
    if progress: progress(1., 'terminé')
    log(f'Rendu {aspect} VOXEL V4 terminé : {os.path.basename(out)} ({time.time() - t0:.0f} s, {(att.get("webgl") or {}).get("renderer", "GPU ?")}). ' + M.summary(v))
    return out
