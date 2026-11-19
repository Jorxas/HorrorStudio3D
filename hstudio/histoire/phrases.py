"""Étape PHRASES du kit : voix/alignement.json (temps de chaque caractère, rendu par ElevenLabs) -> voix/lignes.json
(une phrase par ligne de texte du script, avec son début et sa fin réels) + PHRASES.md (le tableau que le metteur en
scène lit pour écrire ses plans). Les marques « # coupe » et les parties « # rythme » de script.txt sont reportées sur
les phrases. Sans alignement (voix importée seule), les phrases sont calées sur les silences : c'est approximatif.

    python -m hstudio.histoire phrases <dossier>"""
import os
import re

from . import script as SC
from .common import KitError, Story, read_json, write_json, write_text
from .lib import _norm


def _from_alignment(al):
    C, S, E = al['characters'], al['starts'], al['ends']
    text = ''.join(C); out = []; tone = None
    for m in re.finditer(r'[^\n]+', text):
        seg = m.group(0)
        t = re.match(r'^\s*\[([^\]]+)\]\s*$', seg)
        if t: tone = t.group(1); continue
        c = SC.clean(seg)
        if not c: continue
        idx = [k for k in range(m.start(), m.end()) if not C[k].isspace()]
        out.append(dict(start=round(S[idx[0]], 3), end=round(E[idx[-1]], 3), text=c, tone=tone))
    return out


def build(folder, log=print):
    st = Story(folder)
    st.need(st.script, 'écris script.txt')
    st.need(st.voice, 'fais d\'abord l\'étape voix (devis puis --oui, ou --importer)')
    sc = SC.parse(st.script)
    for w in sc['warnings']: log('! ' + w)
    if os.path.exists(st.alignment):
        lines = _from_alignment(read_json(st.alignment)); how = 'alignement ElevenLabs (au caractère près)'
    else:
        from ..align import silence_align
        lines = [dict(text=p['text'], start=0., end=0.) for p in sc['phrases']]
        lines = [dict(start=round(l['start'], 3), end=round(l['end'], 3), text=l['text'], tone=None) for l in silence_align(lines, st.voice)]
        how = 'silences de la voix (APPROXIMATIF : vérifie les temps dans PHRASES.md)'
    ph = sc['phrases']
    if len(lines) > len(ph):
        raise KitError(f'la voix contient {len(lines)} phrases mais script.txt seulement {len(ph)} : le script ne correspond pas à la voix.')
    if len(lines) < len(ph):
        log(f'! la voix ne couvre que les {len(lines)} premières phrases du script (sur {len(ph)}) : les suivantes sont ignorées.')
    for i, (l, p) in enumerate(zip(lines, ph)):
        a, b = _norm(l['text']), _norm(p['text'])
        if a != b and not (a[:24] == b[:24]):
            raise KitError(f"phrase {i} : la voix dit « {l['text'][:60]} » mais le script a « {p['text'][:60]} » (ligne {p['script_line']}).\n"
                           "→ le script a changé depuis la voix : régénère la voix, ou remets le texte d'origine.")
        l.update(tone=l.get('tone') or p['tone'], part=p['part'], coupe=bool(p['coupe']), speaker='narrateur', text=p['text'])
    bad = [i for i in range(1, len(lines)) if lines[i]['start'] < lines[i - 1]['start']]
    if bad: raise KitError(f'phrases dans le désordre aux numéros {bad[:5]} : alignement incohérent')
    write_json(st.lignes, lines)
    rows = ['# PHRASES — numéro, début → fin (secondes du film), durée, ton, partie de voix ; ✂ = un Short peut commencer ici',
            f'# calées par : {how} ; {len(lines)} phrases, voix de {lines[-1]["end"]:.2f} s', '']
    for k, l in enumerate(lines):
        rows.append(f"{'✂' if l['coupe'] else ' '}{k:4d}  {l['start']:7.2f} → {l['end']:7.2f}  ({l['end'] - l['start']:4.1f} s)  "
                    f"[{l['tone'] or '-'}] {{{l['part']}}}  {l['text']}")
    write_text(st.phrases_md, '\n'.join(rows) + '\n')
    n_cut = sum(1 for l in lines if l['coupe'])
    log(f'{len(lines)} phrases calées par {how} ; dernière fin {lines[-1]["end"]:.2f} s ; {n_cut} point(s) de coupe « # coupe ».')
    log(f'→ {st.phrases_md} : lis-le pour écrire histoire.py. Étape suivante : construire / apercu')
    return lines
