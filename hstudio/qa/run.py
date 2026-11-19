"""Orchestration of the scene QA: editorial checks, dense geometric checks, sparse probes (in a pool of processes), image checks
(PS1: the real painter's low-resolution image; VOXEL: stills of the GPU painter; CONSOLE: the console engine's own frames)."""
import json, math, os, tempfile, time
from pathlib import Path
import numpy as np
from .report import Report, Issue, BLOQUANT, A_REVOIR, INFO
from . import load as LD, editorial as ED, checks as CK, probe as PB

MAX_WORKERS = 6                                     # at most 6 PS1 processes on this machine

_W = {}


def _winit(ep, lines, aspect, duration):
    _W['p'] = PB.Probe(ep, lines, aspect, duration)


def _wmeasure(a):
    g, image = a
    return _W['p'].measure(g, image=image)


def measure_all(E, times, images, workers, log):
    gs = [(g, images) for g, _k, _s in times]
    if workers <= 1 or len(gs) < 24:
        P = PB.Probe(E.ep, E.lines, E.aspect, E.duration)
        return [P.measure(g, image=im) for g, im in gs]
    import multiprocessing as mp
    out = []; t0 = time.time()
    with mp.get_context('spawn').Pool(min(workers, MAX_WORKERS), initializer=_winit, initargs=(E.ep, E.lines, E.aspect, E.duration)) as pool:
        for i, m in enumerate(pool.imap(_wmeasure, gs, chunksize=3)):
            out.append(m)
            if log and i % 60 == 0: log(f'[qa] instant {i}/{len(gs)}  {time.time() - t0:.0f} s')
    return out


def verify(folder, aspect=None, style=None, images=False, workers=MAX_WORKERS, log=print, E=None):
    """-> Report. Never modifies the episode."""
    t0 = time.time()
    E = E or LD.load(folder, aspect, style)
    rep = Report(E.dir, E.aspect, E.style, 'éditorial + géométrie' + (' + images' if images else ''))
    ED.check(E, rep)
    if E.style == 'console':
        rep.mode = 'éditorial' + (' + images' if images else '')
        if images: _console_images(E, rep, log)
        rep.stats['durée du contrôle'] = f'{time.time() - t0:.1f} s'
        return rep
    try:
        P = PB.Probe(E.ep, E.lines, E.aspect, E.duration)
    except Exception as e:
        rep.add(Issue('rendu.erreur', BLOQUANT, f'le moteur refuse l\'épisode ({type(e).__name__} : {e})', 'aucune image ne peut être calculée', 'corriger d\'abord les erreurs éditoriales'))
        return rep
    try: CK.dense(P, E, rep, E.style)
    except Exception as e: rep.add(Issue('rendu.erreur', BLOQUANT, f'contrôle dense impossible ({type(e).__name__} : {e})', 'une piste ou une caméra est illisible pour le moteur', 'lire le message'))
    times = CK.sample_times(P.spans, P.ep['shots'])
    ps1_images = images and E.style == 'ps1'
    M = measure_all(E, times, ps1_images, workers, log)
    if images and E.style == 'voxel':
        try: _voxel_images(E, M, log)
        except Exception as e: rep.note(f'images VOXEL non vérifiées : {type(e).__name__} : {str(e)[:200]}')
    CK.from_measures(M, E, rep, E.style, images)
    rep.stats.update({'plans': len(P.ep['shots']), 'instants mesurés': len(M), 'durée du film': f'{E.duration:.1f} s', 'durée du contrôle': f'{time.time() - t0:.1f} s'})
    if images:
        im = [m['image'] for m in M if m.get('image')]
        if im: rep.stats['luminance moyenne (min / médiane)'] = f'{min(x["mean"] for x in im):.1f} / {float(np.median([x["mean"] for x in im])):.1f}'
    if E.style == 'voxel':
        rep.note('VOXEL : la géométrie est mesurée sur la logique PS1 que VOXEL reprend (personnages ×1,1, demi-tour) ; les volumes VOXEL (têtes, robes) sont un peu plus grands.')
    return rep


# ------------------------------------------------------------------------------------------------ VOXEL stills
def _voxel_images(E, M, log):
    """stills of the real GPU painter at the measured instants (one GPU job, low definition) -> m['image'] for each instant"""
    from ..voxelgpu import from_ps1, contract as C, render
    tmp = Path(tempfile.mkdtemp(prefix='qa_vox_'))
    cp = E.dir / 'contract.json'
    if not (cp.exists() and cp.stat().st_mtime >= (E.dir / 'episode.json').stat().st_mtime and C.load(cp).get('aspect') == E.aspect):
        c = from_ps1.build(E.ep, E.lines, E.duration, E.aspect, 30, lambda *_: None); cp = tmp / 'contract.json'; C.save(c, cp)
    ts = sorted({round(m['g'], 2) for m in M if 'error' not in m})
    size = (480, 270) if E.aspect == '16:9' else (270, 480)
    render.run_painter(cp, stills=ts, stills_dir=tmp / 'st', size=size, quiet=True, fallback=True)
    from PIL import Image
    for m in M:
        if 'error' in m: continue
        f = tmp / 'st' / f't_{round(m["g"], 2):.2f}.png'
        if f.exists():
            a = np.asarray(Image.open(f).convert('RGB')); m['image'] = PB.image_stats(a); m['image']['finite'] = True
    if log: log(f'[qa] images VOXEL : {sum(1 for m in M if m.get("image"))} / {len(M)} ({tmp})')


# ------------------------------------------------------------------------------------------------ CONSOLE 2D frames
def _console_images(E, rep, log):
    from ..pipeline import make_engine
    import copy
    ep = copy.deepcopy(E.ep)
    eng = make_engine('console', ep, E.lines, np.zeros(int(E.duration * 30) + 90), E.duration, E.aspect)
    sp = eng.tl.spans
    for k, (a, b) in enumerate(sp):
        g = (a + b) / 2.
        try: im = np.asarray(eng.frame(g).convert('RGB').resize((216, 384) if E.aspect == '9:16' else (384, 216)))
        except Exception as e:
            rep.add(Issue('rendu.erreur', BLOQUANT, f'image CONSOLE impossible ({type(e).__name__} : {e})', 'le rendu s\'arrêterait', 'lire le message', shot=k, t=g)); continue
        s = PB.image_stats(im)
        if s['mean'] < CK.BLACK_MEAN and s['p95'] < 12:
            rep.add(Issue('image.noire', BLOQUANT, f'image noire (luminance {s["mean"]:.1f})', 'rien ne se voit', 'vérifier la scène du plan', shot=k, t=g))
        if s['clip'] > CK.BURN_WARN:
            rep.add(Issue('image.brulee', A_REVOIR, f'{s["clip"] * 100:.0f} % de l\'image est blanc brûlé', 'les détails disparaissent', 'changer la palette ou la scène', shot=k, t=g))


# ------------------------------------------------------------------------------------------------ reports on disk
def write(rep, out_dir, name='rapport_qa'):
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    md = out_dir / f'{name}.md'; js = out_dir / f'{name}.json'
    md.write_text(rep.markdown(), encoding='utf-8'); js.write_text(json.dumps(rep.to_json(), ensure_ascii=False, indent=1), encoding='utf-8')
    return md, js


def gate(folder, style=None, aspect=None, force=False, log=print, images=False, workers=MAX_WORKERS):
    """what the render tools call BEFORE drawing anything: -> True to go on. Prints a short French summary and writes the report
    in <folder>/_qa/. With blocking errors and no `force`: False (the caller refuses to render)."""
    try:
        rep = verify(folder, aspect, style, images=images, workers=workers, log=None)
    except Exception as e:
        log(f'[qa] contrôle impossible ({type(e).__name__} : {e}) : rendu {"forcé" if force else "refusé"}')
        return bool(force)
    try: md, _ = write(rep, Path(folder) / '_qa')
    except OSError: md = None
    c = rep.counts()
    log(f'[qa] {c[BLOQUANT]} bloquant(s), {c[A_REVOIR]} à revoir, {c[INFO]} info' + (f' — rapport : {md}' if md else ''))
    for i in rep.blocking()[:12]: log(f'[qa]   BLOQUANT {i.where()} : {i.msg} -> {i.fix}')
    if rep.ok(): return True
    if force:
        log('[qa] --forcer : rendu malgré les erreurs bloquantes'); return True
    log('[qa] rendu refusé : corriger les erreurs bloquantes (tools/verifier_scene.py ... --corriger) ou relancer avec --forcer')
    return False
