"""python tools/read_subtitles.py <video> <out.json> [--step 5] : OCR of the burned-in subtitles (see hstudio/remake/subtitles.py)"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hstudio.remake import subtitles as S
src, out = sys.argv[1], sys.argv[2]; step = int(sys.argv[sys.argv.index('--step') + 1]) if '--step' in sys.argv else 5
t = time.time(); ch, n = S.read(src, step=step, ignore=('QUE FAIS-TU ?', 'Q.UE FAIS-TU ?', 'TU AS CHOISI :'))
Path(out).write_text(json.dumps(dict(frames=n, chunks=ch), ensure_ascii=False, indent=0), encoding='utf-8'); print(src, n, len(ch), round(time.time() - t), 's')
