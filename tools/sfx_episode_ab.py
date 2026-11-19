"""Integration check on a REAL episode: the whole mixer, the real voice, library ON vs OFF.

    python tools/sfx_episode_ab.py [--shots 12] [--episode examples/etage_zero_partie4]

Unlike tests/test_sfx_library.py (unit level), this runs `hstudio.audio.mixer.Mixer.run()` itself on
`examples/etage_zero_partie4` (the reference episode, quality bar) with its real ElevenLabs voice and its
real 72 sfx cues: voice effects, cue placement, bed, heartbeat, ambience, ducking, compression and the
-14 LUFS two-pass loudnorm. It writes two mixes of the same excerpt - one with the sound library, one
forced back to pure synthesis - and measures what changed.

This needs ffmpeg. If it is not on PATH, the imageio-ffmpeg binary is used for this tool only; the studio
itself still expects a system ffmpeg (`python -m hstudio check`).
"""
import json, os, shutil, subprocess, sys, tempfile
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hstudio.audio                                      # noqa: installs the provider
from hstudio.audio import synth as S, library as L, mixer as MX

SR = S.SR


def ensure_ffmpeg():
    """prefers hstudio.ffmpeg_path when it exists (feature/render-toolchain), then PATH, then imageio-ffmpeg"""
    try:
        from hstudio import ffmpeg_path                 # arrives with the render-toolchain lot
        found = ffmpeg_path.ensure()
        if found.get('ffmpeg'): return f"hstudio.ffmpeg_path -> {found['ffmpeg']}"
    except Exception: pass
    if shutil.which('ffmpeg'): return 'ffmpeg (PATH système)'
    try: import imageio_ffmpeg
    except ImportError: raise SystemExit('ffmpeg introuvable et imageio-ffmpeg non installé : impossible de mixer.')
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    d = os.path.join(tempfile.gettempdir(), 'hstudio_ffmpeg')
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
    if not os.path.exists(dst): shutil.copy2(exe, dst)
    os.environ['PATH'] = d + os.pathsep + os.environ.get('PATH', '')
    return f'imageio-ffmpeg ({os.path.basename(exe)}) — ffmpeg absent du système'


def load_episode(root, n_shots):
    """lines + per-line metadata + shot spans, the same way pipeline.merged_lines / step_mix do"""
    ep = json.load(open(os.path.join(root, 'episode.json'), encoding='utf-8'))
    tim = json.load(open(os.path.join(root, 'timings_reference.json'), encoding='utf-8'))
    meta = ep.get('lines') or {}
    lines = []
    for i, t in enumerate(tim):
        l = dict(t); m = meta.get(str(i), {}) or {}
        for k in ('keywords', 'label', 'label_color', 'voice_fx', 'sfx', 'no_subtitle', 'silence_before'):
            if m.get(k) is not None: l[k] = m[k]
        lines.append(l)
    shots = ep['shots'][:n_shots]
    last_line = max(s['lines'][1] for s in shots)
    lines = lines[:last_line + 1]
    spans = []
    for k, s in enumerate(shots):
        a, b = s['lines']
        t0 = 0. if k == 0 else spans[-1][1]
        spans.append((t0, float(lines[min(b, len(lines) - 1)]['end']) + (.35 if k < len(shots) - 1 else 1.2)))
    ep = dict(ep, shots=shots)
    return ep, lines, spans, spans[-1][1]


def cut_voice(src, dst, dur):
    subprocess.run(f'ffmpeg -v error -y -i "{src}" -t {dur + .5:.2f} -ac 1 -ar {SR} "{dst}"', shell=True, check=True)


def rd(p):
    import wave
    with wave.open(p) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        ch = w.getnchannels()
    return a.reshape(-1, ch).mean(1) if ch > 1 else a


def mix(ep, lines, spans, dur, voice, out, enabled, tag):
    ep = dict(ep, sfx_library=enabled)
    wd = os.path.join(tempfile.gettempdir(), f'hstudio_ab_{tag}')
    os.makedirs(wd, exist_ok=True)
    L.LIB.used = {}
    mx = MX.Mixer(voice, lines, ep, dur, ep.get('style', 'pixel3d'), wd)
    mx.run(spans, out)
    shutil.rmtree(wd, ignore_errors=True)
    return dict(L.LIB.used)


def voice_mask(lines, n):
    m = np.zeros(n, bool)
    for l in lines:
        for a, b in (l.get('segs') or [[l['start'], l['end']]]):
            m[int(a * SR):min(n, int(b * SR))] = True
    return m


def main():
    av = sys.argv[1:]
    n_shots = int(av[av.index('--shots') + 1]) if '--shots' in av else 12
    root = av[av.index('--episode') + 1] if '--episode' in av else os.path.join('examples', 'etage_zero_partie4')
    out_dir = os.path.join('docs', 'audio_ab'); os.makedirs(out_dir, exist_ok=True)
    print(f'ffmpeg : {ensure_ffmpeg()}')
    ep, lines, spans, dur = load_episode(root, n_shots)
    cues = [c if isinstance(c, dict) else {'name': c} for s in ep['shots'] for c in (s.get('sfx') or [])]
    covered = [c for c in cues if L.LIB.has(c.get('name', ''))]
    print(f"épisode {root} : {len(ep['shots'])} plans, {len(lines)} répliques, {dur:.1f} s")
    print(f"cues sfx de l'extrait : {len(cues)}, dont {len(covered)} couvertes par la bibliothèque "
          f"({', '.join(sorted({c['name'] for c in covered})) or 'aucune'})")
    voice = os.path.join(tempfile.gettempdir(), 'hstudio_ab_voice.wav')
    cut_voice(os.path.join(root, 'voice.mp3'), voice, dur)
    res = {}
    for enabled, name in ((False, 'episode_synth'), (True, 'episode_library')):
        p = os.path.join(out_dir, f'{name}.wav')
        used = mix(ep, lines, spans, dur, voice, p, enabled, name)
        a = rd(p); res[name] = dict(path=p, rms=float(np.sqrt((a.astype(np.float64) ** 2).mean())),
                                    peak=float(np.abs(a).max()), used=used, n=len(a))
        print(f"  {name:18} rms {res[name]['rms']:.5f}  pic {res[name]['peak']:.3f}  "
              f"samples servis : {sum(used.values())} {used if used else ''}")
    a, b = rd(res['episode_synth']['path']), rd(res['episode_library']['path'])
    n = min(len(a), len(b)); a, b = a[:n], b[:n]
    vm = voice_mask(lines, n)
    def r(x): return float(np.sqrt((x.astype(np.float64) ** 2).mean() + 1e-20))
    d_all = 20 * np.log10(r(b) / r(a)); d_voice = 20 * np.log10(r(b[vm]) / r(a[vm])); d_sfx = 20 * np.log10(r(b[~vm]) / r(a[~vm]))
    print(f"\nécart bibliothèque vs synthèse : global {d_all:+.2f} dB | "
          f"pendant la voix {d_voice:+.2f} dB | hors voix (effets seuls) {d_sfx:+.2f} dB")
    print(f"identiques ? {'oui' if np.array_equal(a, b) else 'non (les sons ont bien changé)'}")
    rep = dict(episode=root, shots=len(ep['shots']), seconds=round(dur, 2), cues=len(cues),
               cues_covered=len(covered), mixes=res,
               delta_db=dict(global_=round(float(d_all), 2), during_voice=round(float(d_voice), 2),
                             effects_only=round(float(d_sfx), 2)),
               note=('Même épisode, même voix ElevenLabs, même mixeur ; seule la source des bruitages change. '
                     'Un écart proche de 0 dB pendant la voix montre que la voix reste au même niveau.'))
    with open(os.path.join(out_dir, 'episode_ab.json'), 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print(f'-> {out_dir}/episode_synth.wav, episode_library.wav, episode_ab.json')


if __name__ == '__main__':
    main()
