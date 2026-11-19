"""Render-cost benchmark (single process): seconds per frame and peak memory for the reference episodes.

  python tools/bench.py [frames_per_case] [demos]     # "demos": also the demo scenarios (acting layer, V3 places/effects)"""
import os, sys, time, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from regress import engine, load
try: import resource
except ImportError: resource = None            # Windows

def peak_mb():
    if resource is not None: return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    import ctypes
    from ctypes import wintypes
    class PMC(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [(n, ctypes.c_size_t) for n in (
            'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
            'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]
    c = PMC(); c.cb = ctypes.sizeof(PMC)
    k32 = ctypes.windll.kernel32; k32.GetCurrentProcess.restype = wintypes.HANDLE      # 64-bit handle, not a C int
    fn = ctypes.windll.psapi.GetProcessMemoryInfo; fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
    fn(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return c.PeakWorkingSetSize / 2 ** 20

def bench(n=8):
    rows = []
    for name in ('partie4', 'console_demo', 'monde'):
        ep, lines, _ = load(name); dur = lines[-1]['end']
        for aspect in ('9:16', '16:9'):
            eng = engine(name, aspect); ts = [dur * (i + .5) / n for i in range(n)]
            eng.frame(ts[0])                                   # warm caches (sets, fonts)
            t0 = time.perf_counter()
            for t in ts: eng.frame(t)
            rows.append((name, aspect, (time.perf_counter() - t0) / n))
    return rows

def bench_demos(n=6, ids=('demo1_mouvement', 'demo2_dialogue', 'demo3_groupe', 'demo5_console', 'demo7_toits', 'demo8_ravin', 'demo9_tempete', 'demo10_console_saut')):
    """n frames spread over each demo: every frame falls in another shot, so camera planning is included"""
    from hstudio import demos
    from hstudio.pipeline import make_engine, duration_of
    rows = []
    for d in ids:
        sc = demos.load(d); lines = demos.timed_lines(sc['script'], float(sc.get('gap', .3)), float(sc.get('lead', .4)))
        env = demos.draft_voice(sc, lines)[1]; ep = demos.episode_of(sc, lines, log=lambda *a: None)
        for aspect in ('9:16', '16:9'):
            eng = make_engine(sc.get('style', 'pixel3d'), json.loads(json.dumps(ep)), lines, env, duration_of(ep, lines), aspect)
            ts = [duration_of(ep, lines) * (i + .5) / n for i in range(n)]
            t0 = time.perf_counter()
            for t in ts: eng.frame(t)
            rows.append((d, aspect, (time.perf_counter() - t0) / n))
    return rows

if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    for name, aspect, s in bench(n): print(f'{name:20s} {aspect:5s} {s:6.3f} s/frame', flush=True)
    if 'demos' in sys.argv[2:]:
        for name, aspect, s in bench_demos(6): print(f'{name:20s} {aspect:5s} {s:6.3f} s/frame', flush=True)
    print(f'peak memory {peak_mb():.0f} MB')
