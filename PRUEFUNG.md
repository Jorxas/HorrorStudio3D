# Prüfstatus der öffentlichen Ableitung

Stand: 23. November 2026.

tools/check_v3.py wurde im vorhandenen Python-Umfeld erfolgreich ausgeführt. Zwölf echte Standbilder aus drei synthetischen Demos wurden mit dem Python-Motor neu erzeugt. Keine Stimmen, Anbieteraufrufe oder Videoveröffentlichungen. Ein vollständiger Langfilmexport und die gesamte GPU-Regression waren nicht Teil dieser Veröffentlichung.

## Browser-Demo

Die Demo führt die echte Oberfläche aus (`hstudio/web/static/studio.html`, `studio_extras.js`, `publication_bridge.js`); nur die Serverantworten kommen aus `demo/demo-start.js` und den Dateien unter `demo/daten`. `tools/demo-pruefen.cjs` öffnet den Build unter dem Pfad /HorrorStudio3D/ in Chrome und prüft bei 1440 und 390 Pixeln Breite, jeweils auf Deutsch (Standard beim Laden) und auf Französisch (Originalsprache): Projektliste, Einstellungskarten mit Motorbildern, Einstellungsschublade mit den Auswahllisten des Motors, die ehrlichen Hinweise, wo der Motor nötig wäre, Fähigkeitsbericht, Szenenanalyse, Katalog, Musikvideo-Seite, neues Projekt, Speicherverwaltung und Löschdialog. Außerdem: Wechsel DE zu FR und zurück über den Schalter, `?lang=fr` und `?lang=de`, `html lang` passend zur Sprache. In der deutschen Fassung durchsucht die Prüfung an jeder dieser Ansichten den sichtbaren Text samt aria-label, title, placeholder und alt nach Französisch (Sonderzeichen und häufige Wörter) und scheitert bei einem Fund; der Bau scheitert, wenn ein Fragment der Übersetzungstabelle nicht mehr in der Oberfläche vorkommt, und `tools/demo_deutsch.py`, wenn ein Eintrag der Daten keine Übersetzung hat. Ergebnis des letzten Laufs: keine JavaScript-Fehler, keine fehlgeschlagenen Anfragen, keine Anfragen an fremde Hosts, kein horizontaler Überlauf bei 390 Pixeln, kein Französisch in der deutschen Fassung. Die Seite lädt keine externen Schriften oder Tracker. Eine Content-Security-Policy setzt sie nicht.

Grenzen der Demo: Bilder, Planerausgaben und Katalogminiaturen sind echte Motorausgaben, aber vorab erzeugt und nicht im Browser berechnet. Der Katalog ist eine Auswahl (629 Einträge mit Miniatur im Stil PS1 oder Console 2D), nicht der volle Bestand.

Grenzen der deutschen Fassung: In die Motorbilder sind Texte eingemalt (zum Beispiel Untertitel, „TU DÉCIDES“, „NIVEAU 7“); sie bleiben französisch, weil die Bilder echte Motorausgaben sind. Die deutschen Texte der Beispielprojekte, die Suchwörter der Szenenanalyse, die Anzeigenamen der Motor-Auswahllisten und der Katalogeinträge sind von Hand übersetzt (Tabellen in `tools/demo_deutsch.py` und `demo/sprache/de.txt`), nicht vom Motor in Deutsch erzeugt; die Bewertung der Planer-Ergebnisse stammt unverändert aus dem Motor. Die Reihenkürzel (od), (qi), (qt) hinter manchen Katalognamen sind die Kürzel des Motors. Die Episodendatei der Projekte (Kennungen wie `porte`, `canape`, eingemalte Texte) wird nicht angezeigt und nicht übersetzt. Der lokale Python-Server und der Motor liefern weiterhin französische Meldungen; die Demo ersetzt sie in ihrer Antwortschicht (`demo/demo-start.js`) durch deutsche. Französische Kommentare im Quelltext der Oberfläche bleiben dort erhalten und fehlen in der deutschen Fassung. Die alte klassische Oberfläche (`/classique`, `/catalogue-classique`) ist nicht Teil der Demo.

## Reproduzierbarkeit

Die Startbefehle stehen in README.md. Test- und Browserprotokolle bleiben lokal; sie enthalten maschinenspezifische temporäre Pfade. Persönliche Logs werden deshalb nicht als Prüfbelege veröffentlicht.

## Grenzen

Ein lokal bestandener Test mit Fixtures ist kein Nachweis einer produktiven Cloud-Freigabe, einer echten Modellausführung oder eines Kundenbetriebs. Die Browser-Demo zeigt vorab erzeugte Motorausgaben und kennzeichnet dort, wo der Motor nötig wäre, dass er nicht läuft.

Die öffentliche Kopie wurde vor dem ersten Push anhand ihrer Git-Dateiliste auf private Benutzerpfade, persönliche Hosts, E-Mail-Adressen und bekannte Schlüsselpräfixe geprüft. Ein solcher Scan ergänzt die begrenzte Dateiauswahl und ersetzt keine unabhängige Sicherheitsprüfung.
