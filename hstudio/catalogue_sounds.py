"""Les VRAIS sons du moteur VOXEL (library/audio_real) pour le catalogue : une fiche par banque et par événement, avec un MP3 d'écoute et une forme d'onde.

`entries()` est rapide et n'écrit rien : elle lit `library/audio_real/manifest.json` et les `banks/*/CREDITS.json`, et renvoie les fiches
(`id` 'sonreel/<banque>/<événement>', `category` 'Sons', `group` 'Vrais sons — <banque>', licence, crédit, ligne à copier, `thumb`, `audio`).
`build()` fabrique ce qui manque : un MP3 (toutes les variantes de l'événement mises bout à bout, 0,35 s entre deux, 14 s au plus) dans `catalogue/sounds/`
et une forme d'onde JPEG dans `catalogue/thumbs/`.   python -m hstudio.catalogue_sounds build
Écoute impossible hors de la machine de l'utilisateur : le catalogue est fait pour ça."""
import json, re, subprocess, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / 'library' / 'audio_real'
OUT = ROOT / 'catalogue'
SR = 44100


def slug(s): return re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_')
def pretty(s): return re.sub(r'\s+', ' ', re.sub(r'[_\-]+', ' ', s)).strip()


def _banks():
    out = {}
    for f in sorted((REAL / 'banks').glob('*/CREDITS.json')):
        try: out[f.parent.name] = json.loads(f.read_text(encoding='utf-8'))
        except (OSError, ValueError): pass
    return out


def entries():
    try: man = json.loads((REAL / 'manifest.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): return []
    banks = _banks(); out = []
    for ev, e in sorted((man.get('events') or {}).items()):
        by_bank = {}
        for v in e.get('variants', []): by_bank.setdefault((v.get('credit') or {}).get('bank', '?'), []).append(v)
        for bank, vs in sorted(by_bank.items()):
            b = banks.get(bank, {}); sid = f'sonreel/{bank}/{ev}'
            amb = ev.startswith('amb_')
            snip = ('"audio": {"samples": true, "ambience": [{"t0": 0, "t1": 12, "name": "%s", "gain": 0.3}]}' % ev[4:]) if amb else ('"audio": {"samples": true, "sfx": [{"t": 1.0, "name": "%s", "gain": 0.8}]}' % ev)
            out.append(dict(id=sid, category='Sons', group='Vrais sons — ' + b.get('name', bank), name=pretty(ev[4:] + ' (ambiance)' if amb else ev) + (f' · {len(vs)} variantes' if len(vs) > 1 else ''), key=ev,
                            license=b.get('license', '?'), commercial_ok=bool(b.get('commercial_ok', True)), credit_required=bool(b.get('credit_required', False)), credit_text=b.get('credit_text', ''), source=b.get('source', ''),
                            kind=b.get('kind', ''), snippet=snip, thumb=f'thumbs/{slug(sid)}.jpg', audio=f'sounds/{slug(sid)}.mp3', files=[v['file'] for v in vs]))
    return out


def build(force=False, log=print):
    from PIL import Image, ImageDraw
    from .audio import library as L
    (OUT / 'sounds').mkdir(parents=True, exist_ok=True); (OUT / 'thumbs').mkdir(parents=True, exist_ok=True); n = 0
    for e in entries():
        if not force and (OUT / e['thumb']).exists() and (OUT / e['audio']).exists(): continue
        parts = []
        for f in e['files'][:6]:
            try: a = L.read_wav(str(REAL / f))[0][: int((6 if e['key'].startswith('amb_') else 3.5) * SR)]
            except Exception as ex: log(f'  illisible {f} : {ex}'); continue
            parts += [a, np.zeros(int(.35 * SR), np.float32)]
        if not parts: continue
        x = np.concatenate(parts)[:14 * SR]; tmp = OUT / 'sounds' / '_tmp.wav'; L.write_wav(str(tmp), x)
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(tmp), '-b:a', '96k', str(OUT / e['audio'])], check=True)
        im = Image.new('RGB', (320, 240), (24, 24, 32)); d = ImageDraw.Draw(im); m = max(1, len(x) // 320)
        for i in range(320):
            seg = x[i * m:(i + 1) * m]; a_ = float(np.max(np.abs(seg))) if len(seg) else 0.; d.line([(i, 120 - a_ * 100), (i, 120 + a_ * 100)], fill=(63, 178, 127))
        im.save(OUT / e['thumb'], quality=80); n += 1
    log(f'vrais sons : {n} aperçus fabriqués')
    return n


if __name__ == '__main__':
    sys.path.insert(0, str(ROOT))
    if sys.argv[1:2] == ['build']: build(force='--force' in sys.argv)
    else: print(f'{len(entries())} fiches ; python -m hstudio.catalogue_sounds build')
