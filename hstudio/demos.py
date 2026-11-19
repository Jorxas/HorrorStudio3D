"""Demo scenarios (examples/demos/*.json) -> real projects rendered by the production pipeline.

A scenario holds the script (who says what, how long), the voices of the draft babble, and the episode written in the
episode DSL (what a director would produce). build() creates a normal project in projects/, writes the draft voice,
the timings, the validated episode, then runs the mix and the render exactly like any episode (no pre-made video).
The draft voice costs nothing; to hear real voices, generate the voice with ElevenLabs in the studio afterwards."""
import os, re, json, glob
import numpy as np
from . import paths

DEMO_DIR = os.path.join(paths.ROOT, 'examples', 'demos')

def _order(path):                                  # demo2 before demo10
    m = re.match(r'demo(\d+)', os.path.basename(path)); return (int(m.group(1)) if m else 999, os.path.basename(path))

def list_demos():
    out = []
    for f in sorted(glob.glob(os.path.join(DEMO_DIR, '*.json')), key=_order):
        try: d = json.load(open(f, encoding='utf-8'))
        except Exception: continue
        out.append({'id': os.path.splitext(os.path.basename(f))[0], 'title': d.get('title', ''), 'description': d.get('description', ''),
                    'style': d.get('style', 'pixel3d'), 'aspects': d.get('aspects', ['9:16', '16:9'])})
    return out

def load(demo_id):
    sc = json.load(open(os.path.join(DEMO_DIR, demo_id + '.json'), encoding='utf-8'))
    # V3: a scenario may carry a "narrative" block (story intentions) instead of a written "episode". It is
    # then compiled by director/narrative.py before anything else reads it, so prepare(), build(),
    # state_after() and every tool see a perfectly ordinary episode. Additive and guarded: no delivered
    # scenario holds that key, so every existing demo takes exactly the path it took before.
    if sc.get('narrative'):
        from .director.narrative import scenario
        sc = scenario(sc)
    return sc

def timed_lines(script, gap=.3, start=.4):
    lines = []; t = start
    for i, s in enumerate(script):
        txt = s.get('text', '')
        d = float(s.get('dur') or max(1.2, min(6., .45 + .068 * len(txt))))
        lines.append({'tts': txt, 'display': txt, 'text': txt, 'tags': [], 'dialogue': bool(s.get('who')), 'i': i,
                      'start': round(t, 3), 'end': round(t + d, 3), 'segs': [[round(t, 3), round(t + d, 3)]]})
        t += d + float(s.get('gap', gap))
    return lines

def draft_voice(sc, lines):
    """(signal, mouth envelope) of the draft babble of a scenario"""
    from .audio import scratch_voice as SV
    speakers = [s.get('who') for s in sc['script']]
    return SV.render(lines, speakers if sc.get('voice', 'draft') == 'draft' else [None] * len(lines), dict(sc.get('voices', {})), lines[-1]['end'] + float(sc.get('tail', 1.2)))

def lines_with_meta(ep, lines):
    """the lines as the *renderer* receives them in production: the episode's per-line metadata merged in.

    `pipeline.merged_lines` does this from a project on disk. A tool that builds an engine straight from a
    scenario (tools/regress_aplat.py, tools/aplat_sheet.py) needs the same thing without writing a project,
    otherwise it renders subtitles with no speaker label and no keyword, i.e. not what ships. Additive: no
    existing caller is changed, the pipeline keeps its own path."""
    meta = (ep.get('lines') or {})
    out = []
    for i, l in enumerate(lines):
        l = dict(l); m = meta.get(str(i), {}) or {}
        for k in ('keywords', 'label', 'label_color', 'voice_fx', 'sfx', 'no_subtitle', 'silence_before'):
            if m.get(k) is not None: l[k] = m[k]
        out.append(l)
    return out

def episode_of(sc, lines, log=print):
    """the validated episode of a scenario (what prepare() writes), without touching any project"""
    from .director.validate import validate
    script = sc['script']; style = sc.get('style', 'pixel3d')
    ep = json.loads(json.dumps(sc['episode']))
    if ep.get('series'):                    # continuity replayed from the scenario it follows, never from the order of the renders
        ep['series_state'] = state_after(sc['follows']) if sc.get('follows') else {}
        if sc.get('follows'): log(f"Continuité : reprend l'état de fin de {sc['follows']} : " + (', '.join(f"{a} tient {v['hold']}" for a, v in ep['series_state'].items() if v.get('hold')) or 'rien à reprendre'))
    meta = ep.setdefault('lines', {}); names = sc.get('names', {})
    for i, s in enumerate(script):
        m = meta.setdefault(str(i), {})
        if s.get('who'):
            m.setdefault('speaker', s['who'])
            if names.get(s['who']) and sc.get('labels', True): m.setdefault('label', names[s['who']]); m.setdefault('label_color', sc.get('label_colors', {}).get(s['who'], 'cream'))
        for k in ('sfx', 'voice_fx', 'keywords'):
            if s.get(k): m[k] = s[k]
    ep, W = validate(ep, len(lines), style)
    for w in W: log('Avertissement : ' + w)
    return ep

def prepare(demo_id, log=print, name=None, slug=None):
    """create the project (voice, timings, episode); returns the Project

    `slug` builds the same scenario under another project name. Sans lui, une démo se reconstruit sur place,
    ce qui est le bon défaut (elle est reproductible) mais écrase le rendu que le propriétaire avait gardé :
    une preuve se fabrique donc sous un nom neuf, et `Project.create` refuse de réutiliser un dossier existant."""
    from .pipeline import Project
    from .audio import scratch_voice as SV
    sc = load(demo_id); style = sc.get('style', 'pixel3d'); target = slug or demo_id
    pr = Project(target)                       # one project per demo, rebuilt in place (the demo is reproducible)
    if pr.meta and pr.meta.get('demo') == demo_id: pr.meta.update(name=name or sc.get('title', demo_id), style=style, part_label=sc.get('part', 'DÉMO')); pr.save()
    else: pr = Project.create(name or sc.get('title', demo_id), style, part_label=sc.get('part', 'DÉMO'), notes='démo : ' + demo_id, slug=target)
    for f in ('mix.wav', 'qc_9x16.json', 'qc_16x9.json'):
        if pr.exists(f): os.remove(pr.p(f))
    script = sc['script']; lines = timed_lines(script, float(sc.get('gap', .3)), float(sc.get('lead', .4)))
    sig, env = draft_voice(sc, lines)
    os.makedirs(pr.p('work'), exist_ok=True)
    SV.write_mp3(sig, pr.p('voice.mp3'), pr.p('work')); np.save(pr.p('env.npy'), env)
    open(pr.p('script.txt'), 'w', encoding='utf-8').write('\n'.join(s.get('text', '') for s in script))
    pr.write_json('lines.json', lines)
    from .capabilities.audit import report_project        # V3: needs of the scenario, gaps reported (capabilities.json)
    pr.write_json('capabilities.json', report_project(sc['episode'], style, sc.get('description', '') + '\n' + '\n'.join(s.get('text', '') for s in script), log))
    ep = episode_of(sc, lines, log)
    pr.write_json('episode.json', ep)
    pr.meta.update(demo=demo_id, voice='brouillon'); pr.save()
    log(f'Projet {pr.slug} prêt : {len(lines)} lignes, {lines[-1]["end"]:.1f} s, voix de brouillon.')
    return pr

def build(demo_id, aspects=None, quality='standard', log=print, progress=None, qc_only=False):
    """project + mix + quality control + render for each aspect; qc_only: stop after the quality control"""
    from .pipeline import load_settings, step_mix, step_render, step_qc
    pr = prepare(demo_id, log)
    s = load_settings()
    if not qc_only: step_mix(pr, s, log)
    outs = []
    for a in (aspects or load(demo_id).get('aspects', ['16:9'])):
        step_qc(pr, s, a, log)
        if not qc_only: outs.append(step_render(pr, s, a, quality, progress, log))
    return pr, outs

def state_after(demo_id):
    """what the characters keep at the end of a demo scenario (computed by the acting layer, nothing is rendered)"""
    from .pipeline import end_states
    sc = load(demo_id); ep = json.loads(json.dumps(sc['episode'])); ep['style'] = sc.get('style', 'pixel3d')
    if ep.get('series'): ep['series_state'] = state_after(sc['follows']) if sc.get('follows') else {}
    lines = timed_lines(sc['script'], float(sc.get('gap', .3)), float(sc.get('lead', .4)))
    for i, s in enumerate(sc['script']):
        if s.get('who'): ep.setdefault('lines', {}).setdefault(str(i), {}).setdefault('speaker', s['who'])
    return {a: {'hold': v['hold']} for a, v in end_states(ep, lines, ep['style']).items() if v.get('hold')}
