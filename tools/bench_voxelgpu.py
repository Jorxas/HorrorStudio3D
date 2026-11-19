"""Benchmark of the VOXELGPU renderer on REAL frames of a contract (no synthetic scene).

    python tools/bench_voxelgpu.py CONTRACT.json [--windows 10:13.33,45:48.33,80:83.33] [--repeats 3]
                                   [--configs legacy,bin_x264,bin_nvenc] [--concurrent 1] [--size 1080x1920] [--out DIR]

Each config renders the same frames; configs are interleaved inside every repeat so that slow drifts of the machine (antivirus,
other jobs) hit all of them alike, and the MEDIAN is reported. `legacy` is the previous transport (base64 through CDP) with
x264, `bin_*` the binary transport. With --concurrent N, N independent copies of the config start together (aggregate i/s).
GPU load is sampled once a second from the Windows "GPU Engine" counters (3D and VideoEncode engines, dedicated memory)."""
import argparse, json, statistics, subprocess, sys, threading, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu import gpu as G, render as R  # noqa: E402

CONFIGS = {
    'legacy': ['--transport', 'b64'],
    'bin_x264': [],
    'bin_nvenc': ['--encoder', 'nvenc'],
    'bin_nvenc_p5': ['--encoder', 'nvenc', '--preset', 'p5'],
    'bin_x264_fast': ['--preset', 'fast'],
    'hash_only': ['--transport', 'bin', '--hash', 'HASHFILE'],      # render + transfer without encoding: upper bound of the painter
}
SAMPLER = r"""
while ($true) {
  $e = Get-Counter '\GPU Engine(*)\Utilization Percentage','\GPU Adapter Memory(*)\Dedicated Usage' -ErrorAction SilentlyContinue
  $d3 = 0; $enc = 0; $mem = 0
  foreach ($s in $e.CounterSamples) {
    if ($s.Path -match 'gpu engine') { if ($s.InstanceName -match 'engtype_3D') { $d3 += $s.CookedValue } elseif ($s.InstanceName -match 'engtype_VideoEncode') { $enc += $s.CookedValue } }
    elseif ($s.CookedValue -gt $mem) { $mem = $s.CookedValue }
  }
  "{0:N1} {1:N1} {2:N0}" -f $d3, $enc, ($mem/1MB)
}
"""


class GpuSampler:
    def __init__(self):
        self.rows = []; self.p = None

    def start(self):
        self.p = subprocess.Popen(['powershell', '-NoProfile', '-Command', SAMPLER], stdout=subprocess.PIPE, text=True)
        self.t = threading.Thread(target=self._read, daemon=True); self.t.start()

    def _read(self):
        for line in self.p.stdout:
            try: self.rows.append(tuple(float(x.replace(',', '.')) for x in line.split()))
            except ValueError: pass

    def stop(self):
        if self.p: self.p.kill()
        r = self.rows; self.rows = []
        if not r: return {}
        return dict(gpu3d_mean=round(statistics.mean(x[0] for x in r), 1), gpu3d_max=round(max(x[0] for x in r), 1), nvenc_mean=round(statistics.mean(x[1] for x in r), 1), vram_max_mib=round(max(x[2] for x in r)), samples=len(r))


def run_once(name, contract, windows, size, workdir, luid, k, extra):
    w, h = size
    out = workdir / f'{name}_{k}.mp4'; att = workdir / f'{name}_{k}.json'
    cmd = ['node', str(R.JS / 'render_unified.js'), '--contract', str(contract), '--w', str(w), '--h', str(h), '--gpu', 'nvidia', '--luid', luid, '--ranges', windows, '--quiet', '--attest', str(att), *CONFIGS[name], *extra]
    if 'HASHFILE' in cmd: cmd[cmd.index('HASHFILE')] = str(workdir / f'{name}_{k}.hash')
    else: cmd += ['--out', str(out)]
    return subprocess.Popen(cmd, env=R.node_env(), cwd=str(R.JS), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True), att


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('contract'); ap.add_argument('--windows', default='10:13.33,45:48.33,80:83.33'); ap.add_argument('--repeats', type=int, default=3)
    ap.add_argument('--configs', default='legacy,bin_x264,bin_nvenc'); ap.add_argument('--concurrent', type=int, default=1); ap.add_argument('--size', default='1080x1920')
    ap.add_argument('--out', default=str(ROOT / 'projects' / 'bench_perf' / 'run')); ap.add_argument('--no-gpu-sampler', action='store_true')
    a = ap.parse_args()
    size = tuple(int(x) for x in a.size.split('x')); workdir = Path(a.out).resolve(); workdir.mkdir(parents=True, exist_ok=True)
    _, luid, ad = G.pick('nvidia'); contract = Path(a.contract).resolve()
    nframes = sum(round((float(y) - float(x)) * 30) for x, y in (r.split(':') for r in a.windows.split(',')))
    print(f'GPU {ad["name"]} (luid {luid}) | {G.nvidia_smi()} | {nframes} images x {a.concurrent} rendu(s) par essai', flush=True)
    res = {c: [] for c in a.configs.split(',')}
    for rep in range(a.repeats):
        for c in res:
            smp = GpuSampler();
            if not a.no_gpu_sampler: smp.start(); time.sleep(2.5)
            t0 = time.time(); procs = [run_once(c, contract, a.windows, size, workdir, luid, f'{rep}_{i}', []) for i in range(a.concurrent)]
            for p, _ in procs: p.wait()
            wall = time.time() - t0; g = smp.stop() if not a.no_gpu_sampler else {}
            fails = [p.returncode for p, _ in procs if p.returncode]
            if fails: print(c, 'ECHEC', fails, procs[0][0].stdout.read()[-400:]); continue
            atts = [json.loads(att.read_text(encoding='utf-8')) for _, att in procs]
            r = dict(wall_s=round(wall, 1), agg_ips=round(nframes * a.concurrent / wall, 2), render_ips=round(statistics.mean(x.get('fps_render', 0) for x in atts), 2),
                     loop_s=round(statistics.mean(x.get('frames_loop_s', 0) for x in atts), 1), **g)
            res[c].append(r); print(f'rep {rep} {c:14s}', r, flush=True)
    print('\nMEDIANE (sur %d essais, %d images, %d rendu(s) simultané(s))' % (a.repeats, nframes, a.concurrent))
    base = None
    for c, rs in res.items():
        if not rs: continue
        med = statistics.median(r['agg_ips'] for r in rs); base = base or med
        print(f'  {c:14s} {med:6.2f} i/s agrégé  (x{med / base:.2f})  wall médian {statistics.median(r["wall_s"] for r in rs):.1f} s' + (f'  GPU 3D moy {statistics.median(r.get("gpu3d_mean", 0) for r in rs)}% max {max(r.get("gpu3d_max", 0) for r in rs)}% NVENC {statistics.median(r.get("nvenc_mean", 0) for r in rs)}% VRAM max {max(r.get("vram_max_mib", 0) for r in rs)} MiB' if 'gpu3d_mean' in rs[0] else ''))
    (workdir / 'bench_result.json').write_text(json.dumps(res, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
