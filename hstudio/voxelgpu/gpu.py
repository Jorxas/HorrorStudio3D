r"""GPU selection for the Three.js renderer on Windows: list the D3D adapters (DirectX registry), pick one by vendor,
and give Chromium/ANGLE the `--use-adapter-luid` argument. The proof that the choice worked is NOT the request but what
WebGL itself reports (UNMASKED_RENDERER_WEBGL), recorded by the renderer in the attestation file."""
import re, subprocess, sys

COUNTER = r"(Get-Counter '\GPU Adapter Memory(*)\Dedicated Usage').CounterSamples.InstanceName"


def live_luids():
    """LUIDs (low part) of the adapters present right now, from the GPU performance counters: the DirectX registry
    also keeps adapters of previous boots"""
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-Command', COUNTER], capture_output=True, text=True, timeout=60)
        return {int(m.group(1), 16) for m in re.finditer(r'luid_0x[0-9a-f]+_0x([0-9a-f]+)_phys', r.stdout)}
    except Exception:
        return set()


def adapters():
    """-> [{name, vendor, luid_high, luid_low, luid_arg, live}] (empty off Windows)"""
    if sys.platform != 'win32': return []
    try:
        import winreg
        out = []; live = live_luids()
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\DirectX') as k:
            i = 0
            while True:
                try: sub = winreg.EnumKey(k, i)
                except OSError: break
                i += 1
                try:
                    with winreg.OpenKey(k, sub) as s:
                        name = winreg.QueryValueEx(s, 'Description')[0]; luid = int(winreg.QueryValueEx(s, 'AdapterLuid')[0])
                except OSError: continue
                low = luid & 0xFFFFFFFF; high = luid >> 32
                v = ('nvidia' if 'nvidia' in name.lower() else 'intel' if 'intel' in name.lower() else 'amd' if re.search(r'amd|radeon', name, re.I)
                     else 'microsoft' if 'microsoft' in name.lower() else 'other')
                out.append(dict(name=name, vendor=v, luid_high=high, luid_low=low, luid_arg=f'{high},{low}', live=(not live) or low in live))
        return out
    except Exception:
        return []


def pick(vendor):
    """vendor: 'nvidia' | 'intel' | 'auto' | 'software' -> (gpu flag for the renderer, luid argument or None, adapter dict or None)"""
    v = (vendor or 'auto').lower()
    if v in ('software', 'auto'): return v, None, None
    for a in adapters():
        if a['vendor'] == v and a['live']: return v, a['luid_arg'], a
    raise SystemExit(f'Aucun adaptateur « {vendor} » trouvé parmi : {[a["name"] for a in adapters()]}')


def pick_any():
    """first live hardware adapter in the order nvidia > amd > intel, else the software renderer: (flag, luid or None, adapter or None)"""
    for v in ('nvidia', 'amd', 'intel'):
        for a in adapters():
            if a['vendor'] == v and a['live']: return v if v != 'amd' else 'auto', a['luid_arg'], a
    return 'software', None, None


def nvidia_smi():
    try:
        r = subprocess.run(['nvidia-smi', '--query-gpu=name,driver_version,memory.total', '--format=csv,noheader'], capture_output=True, text=True, timeout=20)
        return r.stdout.strip()
    except Exception as e:
        return f'indisponible ({e})'


if __name__ == '__main__':
    for a in adapters(): print(a)
    print(nvidia_smi())
