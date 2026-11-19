"""Script parsing: ElevenLabs v3/v4 tagged script -> lines.
- one non-empty line of the script = one narrative line (one breath, as in the ElevenLabs workflow)
- [tags] are kept for the voice and removed from subtitles
- *mot* marks a keyword (shown in colour); the director can add more keywords
- a line made only of tags ([long pause]) becomes a pause, not a subtitle
"""
import re
TAG = re.compile(r'\[[^\]]*\]')

def clean_display(s):
    s = TAG.sub('', s).strip()
    s = re.sub(r'\s+', ' ', s)
    return s

def parse_script(text):
    lines = []
    for raw in text.replace('\r', '').split('\n'):
        raw = raw.strip()
        if not raw: continue
        tags = [t[1:-1].strip().lower() for t in TAG.findall(raw)]
        disp = clean_display(raw)
        if not disp.replace('*', '').strip():
            if lines: lines[-1]['pause_after'] = True
            continue
        quote = bool(re.search(r'[«"“]', disp))
        lines.append({'tts': raw, 'display': disp, 'text': disp.replace('*', ''), 'tags': tags, 'dialogue': quote})
    for i, l in enumerate(lines): l['i'] = i
    return lines

def tts_text(lines):
    """text sent to ElevenLabs: keep tags, drop *markup*, one line per breath"""
    return '\n\n'.join(l['tts'].replace('*', '') for l in lines)
