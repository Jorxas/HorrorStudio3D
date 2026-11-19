"""CLIP MUSICAL, étape 1 (utilisée par tools/clip_musical.py et par l'interface) : une musique -> analysis.json,
musique.wav (l'extrait, fondus, -14 LUFS) et FEUILLE_MUSIQUE.md (la partition lisible par le directeur)."""
import subprocess
from pathlib import Path
from . import music_analysis as MA


def _inputs(src, start, dur):
    cmd = ['-ss', f'{start:.3f}'] if start else []
    cmd += ['-i', str(src)]
    if dur: cmd += ['-t', f'{dur:.3f}']
    return cmd


def extract(src, out, start, end, fin, fout):
    """l'extrait avec fondus, à -14 LUFS / crête -1,5 dBTP en DEUX passes (mesure, puis correction linéaire) :
    une seule passe de loudnorm laissait un extrait dynamique à -12,5 LUFS (mesuré sur « Safe Inside »)"""
    import json, re
    dur = (end - start) if end is not None else None
    fades = [f'afade=t=in:st=0:d={fin}'] if fin > 0 else []
    if dur and fout > 0: fades.append(f'afade=t=out:st={max(0., dur - fout):.3f}:d={fout}')
    base = ','.join(fades)
    pre = (base + ',' if base else '') + 'loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json'
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', *_inputs(src, start, dur), '-af', pre, '-f', 'null', '-'], capture_output=True, text=True)
    m = re.search(r'\{[^{}]*"input_i"[^{}]*\}', r.stderr, re.S)
    ln = 'loudnorm=I=-14:TP=-1.5:LRA=11'
    if m:
        d = json.loads(m.group(0))
        ln += (f":measured_I={d['input_i']}:measured_TP={d['input_tp']}:measured_LRA={d['input_lra']}"
               f":measured_thresh={d['input_thresh']}:offset={d['target_offset']}:linear=true")
    af = (base + ',' if base else '') + ln
    subprocess.run(['ffmpeg', '-v', 'error', '-y', *_inputs(src, start, dur), '-af', af, '-ar', '48000', '-ac', '2', str(out)], check=True)


def mmss(t): return f'{int(t // 60)}:{t % 60:05.2f}'


def sheet(A, src, start):
    per = A['beat_period']; bar = 4 * per
    L = [f'# Feuille de musique — {Path(src).name}', '',
         f'Extrait à partir de {start:.2f} s. Tous les temps ci-dessous sont RELATIFS au début du clip (0 = première image).', '',
         f'- tempo : **{A["tempo"]} BPM** (un temps = {per:.3f} s, une mesure de 4 temps = {bar:.2f} s)',
         f'- durée : {A["duration"]:.2f} s ; sommet d\'énergie vers **{A["climax"]:.1f} s**',
         f'- {len(A["beats"])} temps, {len(A["downbeats"])} premiers temps de mesure, {len(A["onsets"])} attaques', '',
         '## Sections', '', '| de | à | niveau | énergie | coupes conseillées (premiers temps) |', '|---|---|---|---|---|']
    for s in A['sections']:
        every = {'fort': 1, 'moyen': 2}.get(s['niveau'], 4)
        d = [x for x in A['downbeats'] if s['t0'] <= x < s['t1']][::every]
        L.append(f'| {s["t0"]:.2f} | {s["t1"]:.2f} | {s["niveau"]} | {s["energy"]:.2f} | ' + ', '.join(f'{x:.2f}' for x in d[:16]) + (' …' if len(d) > 16 else '') + ' |')
    L += ['', '## Silences (moments pour retenir son souffle, puis frapper au premier temps qui suit)', '']
    L += [f'- {a:.2f} → {b:.2f} s ; premier temps après : ' + next((f'{x:.2f} s' for x in A['downbeats'] if x >= b - .05), '—') for a, b in A['silences']] or ['- aucun']
    mesure = 'séparées' in str(A.get('method', ''))
    L += ['', '## Phrases chantées (' + ('MESURÉES sur la voix séparée' if mesure else "ESTIMÉES, sans séparation de la voix — à vérifier à l'oreille") + ')', '']
    L += [f'- {a:.2f} → {b:.2f} s' for a, b in A['vocal']['phrases'][:40]] or ['- aucune détectée']
    L += ['', '## Règles de mise en scène sur la musique', '',
          '- Coupe sur un PREMIER TEMPS de mesure (`M.cuts(a, b, every)`), jamais entre deux temps.',
          '- Section calme : plans longs (2 à 4 mesures), caméra lente, pas de `pulse`.',
          '- Section forte : une coupe par mesure, `"pulse": {"on": "beats", "fov": 2.5, "shake": 0.25}` sur la caméra.',
          '- Silence : couper la lumière ou figer la caméra (`hold`), puis tout rallumer au premier temps qui suit.',
          '- Lumières qui battent : `state_track` avec `M.pulse(...)` sur la clé de lumière du décor.',
          '- Texte à l\'écran : un texte ORIGINAL (jamais les paroles de la chanson), calé sur les phrases.',
          '- La musique d\'un autre artiste peut déclencher une revendication de droits si la vidéo est publiée.', '']
    return '\n'.join(L)



def separate(src, stems_dir):
    """sépare la voix, la batterie, la basse et le reste (Demucs sur le GPU) avec `tools/separate_voice.py`, lancé par un Python
    qui a torch (HSTUDIO_TORCH_PYTHON, sinon le venv TTS « chatterbox » du PC) : le venv du studio n'a pas torch exprès"""
    import os
    py = os.environ.get('HSTUDIO_TORCH_PYTHON') or r'C:\Users\demo\Desktop\Studium\Perso\MainClip\PPS\.venvs\chatterbox\Scripts\python.exe'
    if not Path(py).exists(): raise RuntimeError(f'Python avec torch introuvable : {py} (variable HSTUDIO_TORCH_PYTHON)')
    script = Path(__file__).resolve().parents[2] / 'tools' / 'separate_voice.py'
    subprocess.run([py, str(script), str(src), str(stems_dir)], check=True)
    return Path(stems_dir)


def prepare(src, out_dir, debut=0., fin=None, fondu=(.6, 1.6), label=None, stems=None, anchor=None):
    """-> l'analyse (dict) ; écrit out_dir/analysis.json, musique.wav, FEUILLE_MUSIQUE.md
    `stems` : dossier des pistes séparées (voix.wav, drums.wav, accompagnement.wav) -> voix MESURÉE et premiers temps plus sûrs ;
    `anchor` : instant (s, dans la chanson entière) connu pour être un premier temps de mesure (l'entrée du refrain)"""
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    if stems:
        from . import music_stems as MS
        A = MS.analyse_with_stems(src, stems, anchor)
    else:
        A = MA.analyse(src)                                           # toute la chanson, puis l'extrait : tempo et mesures plus sûrs
    if debut or fin: A = MA.excerpt(A, debut, fin)
    A['source'] = {'fichier': label or Path(src).name, 'debut': debut, 'fin': fin}
    MA.save(A, out / 'analysis.json')
    extract(src, out / 'musique.wav', debut, fin, float(fondu[0]), float(fondu[1]))
    (out / 'FEUILLE_MUSIQUE.md').write_text(sheet(A, src, debut), encoding='utf-8')
    return A
