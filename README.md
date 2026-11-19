# Horror Studio 3D – prozedurale Erzählwelten

Ein lokales Studio verbindet Szenenbeschreibung, Figuren, Kamera, zwei Bildrichtungen, Ton und Qualitätsprüfung. Das öffentliche Repository enthält den Motor und synthetische Beispiele, keine privaten Geschichten oder Stimmen.

**Technik:** Python, NumPy, Pillow, Three.js, FFmpeg.

[Interaktive Demo](https://jorxas.github.io/HorrorStudio3D/) · [Portfolio](https://jorxas.github.io/Portfolio/) · [Architektur](ARCHITEKTUR.md) · [Prüfstatus](PRUEFUNG.md)

## Ausprobieren

Die vollständige Projektseite mit Demo liegt in `site/index.html`. Sie arbeitet mit erfundenen Daten. Externe Dienste, Anbieter-Konten und Hintergrundaufträge werden dort nicht ausgeführt. Die Oberfläche kennzeichnet die jeweiligen Simulationen.

## Demo lokal öffnen

~~~sh
python -m http.server 8080 --bind 127.0.0.1 --directory site
~~~

Danach http://127.0.0.1:8080 öffnen. Die Demo benötigt weder Konten noch Modellgewichte.

## Lokal prüfen

~~~sh
python -m pip install -r requirements.txt
python -m hstudio --help
~~~

Die genauen geprüften Befehle und Grenzen stehen in [PRUEFUNG.md](PRUEFUNG.md). Produktive Schlüssel, persönliche Daten und Modelle gehören ausschließlich in die lokale Installation.

## Herkunft

Dies ist eine für die Veröffentlichung geprüfte Ableitung eines bestehenden lokalen Projekts. [HERKUNFT.md](HERKUNFT.md) trennt den ursprünglichen Entwicklungsstand von den jetzt ausgeführten Veröffentlichungsarbeiten. Die ursprünglichen Oberflächen und technischen Bezeichner sind teilweise französisch oder englisch. Neue Präsentation und Dokumentation sind deutsch.

## Rechte und Abhängigkeiten

Für eigenen Quellcode wird hier keine zusätzliche Nutzungslizenz eingeräumt. Die Lizenzen der genannten Bibliotheken und Modelle gelten unabhängig davon. Fremde Modelle, Stimmen, Medien und Zugangsdaten werden nicht mitgeliefert. Siehe [DRITTANBIETER.md](DRITTANBIETER.md).

## Beispiele und Bilder

`python tools/check_v3.py` prüft Planer, Erweiterungen und Bildlogik. `python demo/bilder_erstellen.py` erzeugt zwölf stille Demobilder ohne Sprachdienst. Die Schriften unter `assets/fonts/` stehen unter ihren mitgelieferten SIL-OFL-Lizenzen.

## Lokaler Studiomotor

Nach Installation der Python-Abhängigkeiten zeigt `python -m hstudio --help` die vorhandenen Werkzeuge. `python -m hstudio web --port 8767 --no-browser` startet die lokale Oberfläche; diese Veröffentlichung richtet keine Sprach- oder Veröffentlichungskonten ein. Für reines Betrachten genügt die statische Demo. Der GPU-Pfad besitzt zusätzliche Node-Abhängigkeiten unter `voxelgpu_js/`; die dokumentierte Abnahme umfasst den Python-Motor.
