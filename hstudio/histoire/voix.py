"""Étape VOIX du kit : devis en caractères, génération ElevenLabs (seulement avec --oui), ou import d'une voix existante.

Règles du propriétaire, tenues ici :
  * voix « recap webton frh » (voice_id jr8GS3OFJ1KR5cNn9suk dans CE compte), modèle eleven_v4 (fichier voix.json) ;
  * rythme soutenu ; l'urgence est plus rapide et la révélation plus lente par la VITESSE DE GÉNÉRATION de chaque partie
    (« # rythme NOM VITESSE » dans script.txt), jamais en accélérant le son après coup ;
  * aucune génération sans accord : sans --oui, on n'écrit qu'un devis (nombre de caractères) ;
  * la clé n'est jamais lue, affichée ni écrite par le kit : c'est ELEVENLABS/client.py qui la charge dans l'environnement.

    python -m hstudio.histoire voix <dossier>                    devis seulement (rien n'est envoyé)
    python -m hstudio.histoire voix <dossier> --oui              génère voix/voix.mp3 + voix/alignement.json
    python -m hstudio.histoire voix <dossier> --importer F.mp3 [--alignement A.json] [--jusqua 40]
                                                                 reprend une voix existante (aucun appel réseau)"""
import os
import shutil
import subprocess
import sys
import tempfile

from . import script as SC
from .common import KitError, Story, read_json, write_json, ENGINE, other_python

DEFAULTS = {'voix_nom': 'recap webton frh', 'voice_id': 'jr8GS3OFJ1KR5cNn9suk', 'modele': 'eleven_v4', 'stabilite': .5, 'similarite': .75,
            'style': 0., 'vitesse_defaut': 1.06, 'respiration_s': .45, 'max_caracteres_par_requete': 2500}
ELEVEN_DIR = os.environ.get('HSTUDIO_ELEVENLABS_DIR') or os.path.join(os.path.expanduser('~'), 'Desktop', 'videpgene', 'ELEVENLABS')


def settings(st):
    s = dict(DEFAULTS)
    if os.path.exists(st.voix_json): s.update(read_json(st.voix_json))
    return s


def _fmt_dur(sec):
    s = int(round(sec)); return f'{s // 60} min {s % 60:02d} s' if s >= 60 else f'{s} s'


def _chunks(text, max_chars):
    """a part longer than one request allows, cut between paragraphs"""
    if len(text) <= max_chars: return [text]
    paras = text.split('\n\n'); out, cur = [], ''
    for p in paras:
        cand = (cur + '\n\n' + p) if cur else p
        if cur and len(cand) > max_chars: out.append(cur); cur = p
        else: cur = cand
    if cur: out.append(cur)
    return out


def quote(folder, log=print, hint=True):
    st = Story(folder); st.need(st.script, 'crée le dossier avec « nouveau » puis écris script.txt')
    s = settings(st); sc = SC.parse(st.script, s['vitesse_defaut'])
    for w in sc['warnings']: log('! ' + w)
    total = sum(p['chars'] for p in sc['parts'])
    log(f"Devis de voix — {st.dir}")
    log(f"Voix : {s['voix_nom']} ({s['voice_id']}), modèle {s['modele']}, stabilité {s['stabilite']}, similarité {s['similarite']}")
    for i, p in enumerate(sc['parts']):
        est = p['chars'] / (15.5 * p['speed'])
        n_req = len(_chunks(p['text'], int(s['max_caracteres_par_requete'])))
        log(f"  {i + 1:2d}. {p['name']:<18s} vitesse {p['speed']:.2f}   {p['chars']:6d} caractères   {len(p['phrases']):3d} phrases   ≈ {_fmt_dur(est)}"
            + (f'   ({n_req} requêtes)' if n_req > 1 else ''))
    log(f"TOTAL : {total} caractères pour {len(sc['phrases'])} phrases (≈ {_fmt_dur(sum(p['chars'] / (15.5 * p['speed']) for p in sc['parts']))} de voix).")
    write_json(os.path.join(st.voix, 'devis.json'), dict(caracteres=total, parties=[{k: p[k] for k in ('name', 'speed', 'chars')} for p in sc['parts']],
                                                          voix=s['voix_nom'], voice_id=s['voice_id'], modele=s['modele']))
    if hint:
        log("Aucune voix n'a été générée. Donne ce nombre de caractères au propriétaire ; APRÈS son accord :")
        log(f'  python -m hstudio.histoire voix "{st.dir}" --oui')
    return total


# ------------------------------------------------------------------ generation (paid: only with --oui)
def generate(folder, redo=False, log=print):
    st = Story(folder)
    if os.path.exists(st.voice) and not redo:
        raise KitError(f'{st.voice} existe déjà : rien n\'est régénéré (ajoute --refaire pour payer une nouvelle voix).')
    total = quote(folder, log, hint=False)
    py = other_python(['elevenlabs', 'dotenv', 'requests'], 'HSTUDIO_PYTHON_ELEVENLABS')
    if py == [sys.executable]:
        _generate_here(st, log); return total
    if not py:
        raise KitError("Aucun Python avec les paquets « elevenlabs », « dotenv » et « requests » : impossible de charger la clé par "
                       "ELEVENLABS/client.py. Indique-en un avec la variable HSTUDIO_PYTHON_ELEVENLABS.")
    log(f'(génération confiée à {" ".join(py)} : ce Python a le paquet elevenlabs)')
    env = dict(os.environ, PYTHONPATH=ENGINE + os.pathsep + os.environ.get('PYTHONPATH', ''), PYTHONIOENCODING='utf-8')
    r = subprocess.run(py + ['-m', 'hstudio.histoire.voix', '--generer-ici', st.dir], cwd=ENGINE, env=env)
    if r.returncode != 0: raise KitError('la génération de la voix a échoué (voir les messages ci-dessus)')
    return total


def _generate_here(st, log=print):
    if not os.path.isdir(ELEVEN_DIR): raise KitError(f'dossier ElevenLabs introuvable : {ELEVEN_DIR} (variable HSTUDIO_ELEVENLABS_DIR)')
    sys.path.insert(0, ELEVEN_DIR)
    import client  # noqa: F401  (loads the key into the environment; prints nothing)
    from .. import tts as T
    key = os.environ.get('ELEVENLABS_API_KEY')
    if not key: raise KitError('clé ElevenLabs absente : ELEVENLABS/.env.local n\'a pas été chargé par client.py')
    s = settings(st); sc = SC.parse(st.script, s['vitesse_defaut'])
    os.makedirs(st.voix, exist_ok=True)
    gap = os.path.join(st.voix, '_respiration.mp3'); GAP = float(s['respiration_s'])
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono', '-t', str(GAP), '-c:a', 'libmp3lame', '-b:a', '192k', gap], check=True)
    files = []; al = {'characters': [], 'starts': [], 'ends': [], 'parts': [], 'source': 'elevenlabs', 'voice_id': s['voice_id'], 'modele': s['modele']}
    off = 0.; used = 0
    for k, p in enumerate(sc['parts']):
        vs = T.voice_settings(stability=float(s['stabilite']), similarity=float(s['similarite']), style=float(s['style']), speed=float(p['speed']))
        t_part = off
        for j, chunk in enumerate(_chunks(p['text'], int(s['max_caracteres_par_requete']))):
            if j: al['characters'].append('\n'); al['starts'].append(round(off, 4)); al['ends'].append(round(off, 4))
            audio, a = T.request_tts(key, s['voice_id'], chunk, model_id=s['modele'], voice_settings=vs)
            path = os.path.join(st.voix, f"partie_{k:02d}_{p['name']}" + (f'_{j}' if j else '') + '.mp3')
            with open(path, 'wb') as f: f.write(audio)
            d = T.ffprobe_duration(path); used += len(chunk)
            for c, s0, e0 in zip(a.get('characters', []), a.get('character_start_times_seconds', []), a.get('character_end_times_seconds', [])):
                al['characters'].append(c); al['starts'].append(round(s0 + off, 4)); al['ends'].append(round(e0 + off, 4))
            files.append(path); off += d
            log(f"partie {k} {p['name']}{f' ({j + 1})' if j else ''} : {len(chunk)} caractères, vitesse {p['speed']}, {d:.1f} s")
        al['parts'].append(dict(name=p['name'], t0=round(t_part, 3), t1=round(off, 3), speed=p['speed']))
        if k < len(sc['parts']) - 1:
            files.append(gap); al['characters'].append('\n'); al['starts'].append(round(off, 4)); al['ends'].append(round(off + GAP, 4)); off += GAP
    T.concat_mp3(files, st.voice, st.voix)
    write_json(st.alignment, al, indent=None)
    log(f'voix.mp3 : {T.ffprobe_duration(st.voice):.2f} s ; {used} caractères consommés. Étape suivante : phrases')


# ------------------------------------------------------------------ import (free)
def import_voice(folder, src, alignment=None, until=None, log=print):
    st = Story(folder)
    if not os.path.isfile(src): raise KitError(f'voix introuvable : {src}')
    if os.path.exists(st.voice) and os.path.abspath(src) != os.path.abspath(st.voice):
        raise KitError(f'{st.voice} existe déjà : supprime-le d\'abord si tu veux le remplacer.')
    os.makedirs(st.voix, exist_ok=True)
    al = None
    if alignment:
        a = read_json(alignment)
        if 'characters' not in a:
            a = a.get('alignment') or a.get('normalized_alignment') or a
        al = {'characters': list(a['characters']), 'starts': list(a.get('starts') or a.get('character_start_times_seconds')),
              'ends': list(a.get('ends') or a.get('character_end_times_seconds')), 'source': 'import', 'origine': os.path.abspath(alignment)}
    cut = None
    if until is not None:
        until = float(until)
        if al:
            cut = _cut_after_phrase(al, until)
        else:
            cut = until
    if cut is not None:
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-t', f'{cut:.3f}', '-c:a', 'libmp3lame', '-b:a', '192k', st.voice], check=True)
        if al:
            keep = [i for i, s in enumerate(al['starts']) if s < cut - .02]
            for k in ('characters', 'starts', 'ends'): al[k] = [al[k][i] for i in keep]
    else:
        shutil.copy(src, st.voice)
    if al: write_json(st.alignment, al, indent=None)
    from .common import duration
    log(f"voix importée : {st.voice} ({duration(st.voice):.2f} s){' coupée à ' + format(cut, '.2f') + ' s' if cut else ''}"
        + ('' if al else " — sans alignement : l'étape phrases calera les phrases sur les silences (approximatif)"))
    log('Aucun appel réseau, aucun caractère consommé. Étape suivante : phrases')


def _cut_after_phrase(al, until):
    """end of the last COMPLETE phrase (line of text) before `until`, plus a short breath"""
    C, S, E = al['characters'], al['starts'], al['ends']
    text = ''.join(C); import re
    best = None
    for m in re.finditer(r'[^\n]+', text):
        seg = m.group(0)
        if re.match(r'^\s*\[[^\]]+\]\s*$', seg) or not SC.clean(seg): continue
        idx = [k for k in range(m.start(), m.end()) if not C[k].isspace()]
        e = E[idx[-1]]
        if e <= until: best = (e, m.end())
    if best is None: raise KitError(f'aucune phrase complète avant {until} s')
    e, after = best
    nxt = next((S[k] for k in range(after, len(C)) if not C[k].isspace()), None)
    return min(e + .5, (nxt - .02) if nxt is not None else e + .5)


if __name__ == '__main__':
    # internal entry: generation delegated to another Python (see generate())
    if len(sys.argv) == 3 and sys.argv[1] == '--generer-ici':
        try:
            _generate_here(Story(sys.argv[2]))
        except KitError as e:
            print(str(e)); sys.exit(1)
    else:
        print(__doc__)
