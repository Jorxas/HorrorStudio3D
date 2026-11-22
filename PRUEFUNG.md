# Prüfstatus der öffentlichen Ableitung

Stand: 19. November 2026.

tools/check_v3.py wurde im vorhandenen Python-Umfeld erfolgreich ausgeführt. Zwölf echte Standbilder aus drei synthetischen Demos wurden mit dem Python-Motor neu erzeugt. Keine Stimmen, Anbieteraufrufe oder Videoveröffentlichungen. Ein vollständiger Langfilmexport und die gesamte GPU-Regression waren nicht Teil dieser Veröffentlichung.

## Browser-Demo

Die Demo führt die echte Oberfläche aus (`hstudio/web/static/studio.html`, `studio_extras.js`, `publication_bridge.js`); nur die Serverantworten kommen aus `demo/demo-start.js` und den Dateien unter `demo/daten`. `tools/demo-pruefen.cjs` öffnet den Build unter dem Pfad /HorrorStudio3D/ in Chrome und prüft bei 1440 und 390 Pixeln Breite: Projektliste, Plankarten mit Motorbildern, Plan-Schublade mit den Auswahllisten des Motors, die ehrlichen Hinweise, wo der Motor nötig wäre, Fähigkeitsbericht, Szenenanalyse, Katalog, Clip-Seite, neues Projekt und Speicherverwaltung. Ergebnis des letzten Laufs: keine JavaScript-Fehler, keine fehlgeschlagenen Anfragen, keine Anfragen an fremde Hosts, kein horizontaler Überlauf bei 390 Pixeln. Die Seite lädt keine externen Schriften oder Tracker. Eine Content-Security-Policy setzt sie nicht.

Grenzen der Demo: Bilder, Planerausgaben und Katalogminiaturen sind echte Motorausgaben, aber vorab erzeugt und nicht im Browser berechnet. Der Katalog ist eine Auswahl (629 Einträge mit Miniatur im Stil PS1 oder Console 2D), nicht der volle Bestand. Die alte klassische Oberfläche (`/classique`, `/catalogue-classique`) ist nicht Teil der Demo.

## Reproduzierbarkeit

Die Startbefehle stehen in README.md. Test- und Browserprotokolle bleiben lokal; sie enthalten maschinenspezifische temporäre Pfade. Persönliche Logs werden deshalb nicht als Prüfbelege veröffentlicht.

## Grenzen

Ein lokal bestandener Test mit Fixtures ist kein Nachweis einer produktiven Cloud-Freigabe, einer echten Modellausführung oder eines Kundenbetriebs. Die Browser-Demo zeigt vorab erzeugte Motorausgaben und kennzeichnet dort, wo der Motor nötig wäre, dass er nicht läuft.

Die öffentliche Kopie wurde vor dem ersten Push anhand ihrer Git-Dateiliste auf private Benutzerpfade, persönliche Hosts, E-Mail-Adressen und bekannte Schlüsselpräfixe geprüft. Ein solcher Scan ergänzt die begrenzte Dateiauswahl und ersetzt keine unabhängige Sicherheitsprüfung.
