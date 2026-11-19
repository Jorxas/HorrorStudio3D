"""Statische Demo-Bilder mit dem echten lokalen Motor, ohne Sprachdienst oder Videoexport."""
import json
import sys
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hstudio.demos import load, timed_lines
from hstudio.pipeline import make_engine

ZIEL = Path(__file__).parent / "bilder"
ZIEL.mkdir(exist_ok=True)
protokoll = []
for demo in ("demo1_mouvement", "demo4_tension", "demo5_console"):
    szene = load(demo)
    episode = szene["episode"]
    zeilen = timed_lines(szene["script"], float(szene.get("gap", .3)), float(szene.get("lead", .4)))
    for i, text in enumerate(szene["script"]):
        if text.get("who"):
            episode.setdefault("lines", {}).setdefault(str(i), {})["speaker"] = text["who"]
    motor = make_engine(szene.get("style", "pixel3d"), episode, zeilen, np.zeros(10), zeilen[-1]["end"] + .1, "16:9")
    dauer = zeilen[-1]["end"]
    for i, anteil in enumerate((.15, .40, .65, .85)):
        zeit = round(dauer * anteil, 3)
        bild = motor.frame(zeit)
        bild.thumbnail((768, 432))
        name = f"{demo}-{i}.png"
        bild.save(ZIEL / name)
        protokoll.append({"szene": demo, "datei": name, "sekunden": zeit, "motor": szene.get("style", "pixel3d"), "breite": bild.width, "hoehe": bild.height})
(ZIEL / "herkunft.json").write_text(json.dumps(protokoll, indent=2), encoding="utf-8")
print(f"{len(protokoll)} echte Motorbilder erstellt; keine Sprach- oder Plattformanfragen.")
