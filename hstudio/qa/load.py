"""Loading a directed-scene episode folder (episode.json + lines.json) and guessing its format / style."""
import json, re
from pathlib import Path


class Episode:
    def __init__(self, folder, ep, lines, aspect, style):
        self.dir = Path(folder); self.ep = ep; self.lines = lines; self.aspect = aspect; self.style = style
        self.duration = float(ep.get('duration') or (lines[-1]['end'] + 1.2 if lines else 1.))


def guess_aspect(folder, ep):
    n = str(folder).lower().replace('\\', '/')
    if re.search(r'9\s*[x_:]\s*16', n): return '9:16'
    if re.search(r'16\s*[x_:]\s*9', n): return '16:9'
    a = ep.get('aspect')
    return a if a in ('9:16', '16:9') else '16:9'


def guess_style(folder, ep):
    if ep.get('style') == 'console': return 'console'
    n = str(folder).lower()
    if ep.get('voxel_mirror') or 'voxel' in n or ep.get('words'): return 'voxel'
    return 'ps1'


def load(folder, aspect=None, style=None):
    d = Path(folder)
    ep = json.loads((d / 'episode.json').read_text(encoding='utf-8'))
    lp = d / 'lines.json'
    lines = json.loads(lp.read_text(encoding='utf-8')) if lp.exists() else []
    return Episode(d, ep, lines, aspect or guess_aspect(d, ep), (style or guess_style(d, ep)).lower())


def spans(ep, lines, duration):
    """the engine's own shot spans (engines/pixel3d/frame.Timeline): [(t0, t1)] in film seconds"""
    from ..engines.pixel3d.frame import Timeline                                # CONSOLE 2D uses the very same class
    return list(Timeline(ep, lines, duration).spans)
