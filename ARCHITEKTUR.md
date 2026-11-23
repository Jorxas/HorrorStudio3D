# Architektur

Ein lokales Studio verbindet Szenenbeschreibung, Figuren, Kamera, zwei Bildrichtungen, Ton und Qualitätsprüfung. Das öffentliche Repository enthält den Motor und synthetische Beispiele, keine privaten Geschichten oder Stimmen.

## Verantwortungsgrenzen

Die lokale Anwendung enthält den eigentlichen Dienst beziehungsweise Motor. Die öffentliche Browser-Demo führt dieselbe Oberfläche (`hstudio/web/static`) aus, ersetzt aber den Python-Server durch `demo/demo-start.js`, das die API-Aufrufe aus vorab mit dem echten Motor erzeugten Dateien beantwortet (`tools/demo_export.py`, `tools/demo-bauen.mjs`). Die Demo ist zweisprachig (Deutsch Standard, Französisch Originalsprache): Der Bau erzeugt aus derselben Quelle `index.html` (deutsch) und `fr.html`, die deutsche Fassung mit der Fragmenttabelle `demo/sprache/de.txt` und den Daten unter `demo/daten/de` (`tools/demo_deutsch.py`). Ihre Daten stammen nicht aus einer produktiven Installation.

## Prüfbarkeit

Tests verwenden isolierte temporäre Daten. Anbieteraufrufe und Kontozugriffe gehören nicht zur öffentlichen Demo. Ein bestandener Vertragstest mit lokalen Fixtures ist kein Nachweis einer produktiven Anbieterfreigabe.
