"""Deutsche Fassung der Demodaten: übersetzt die Motorausgaben unter demo/daten/fr nach demo/daten/de (nur Standardbibliothek).

Der Motor spricht Französisch (Planer, Fähigkeitsbericht, Auswahllisten, Katalog). Die Demo zeigt Deutsch als Standard und Französisch als
Originalsprache; deshalb liegen beide Fassungen nebeneinander:

  demo/daten/fr   Rohausgabe von tools/demo_export.py (unverändert, Originalsprache)
  demo/daten/de   dieselben Daten mit deutschen Beschriftungen, erfundenen deutschen Texten und deutschen Suchwörtern

Was übersetzt wird: Projektnamen, Skripte und Sätze, die Anzeigenamen der Auswahllisten (nach Kennung), die Wörter, Hinweise und Erweiterungsanfragen
des Szenenplaners, Katalognamen, -gruppen, -kategorien, -lizenzen und -beschreibungen. Was nicht übersetzt wird: technische Kennungen (Projektkennung
der Vorschaubilder wird als vorschau_ordner mitgeführt, Motor-Namen wie jump, building, pixel3d, Dateipfade, JSON-Schlüssel, die Episodendatei).
Die Suchwörter (terms) des Planers sind deutsche Wörter, die in den deutschen Texten stehen; die Auswertung (verfügbar, zusammengesetzt, fehlt)
stammt unverändert aus der Motorausgabe. Jeder Eintrag muss in der Tabelle stehen, sonst bricht das Skript ab (kein stilles Französisch).

Aufruf: python tools/demo_deutsch.py   (liest demo/daten/fr, schreibt demo/daten/de)"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATEN = ROOT / 'demo' / 'daten'

# ---------- Projekte ----------
PROJEKT = {  # französische Kennung -> (deutsche Kennung, Name, Teilbezeichnung)
    'nuit_d_orage': ('gewitternacht', 'Gewitternacht', 'DEMO 4'),
    'la_cle_inconnue': ('der_fremde_schluessel', 'Der fremde Schlüssel', 'DEMO 1'),
    'ne_mets_pas_pause': ('nicht_pausieren_level_7', 'Nicht pausieren: Level 7', 'LEVEL 7'),
    'la_ville_sous_leau': ('die_stadt_unter_wasser', 'Die Stadt unter Wasser', 'ENTWURF'),
}
SAETZE = {  # Skriptzeilen
    "Il y a quelqu'un... ?": 'Ist da jemand...?',
    'Maman ?': 'Mama?',
    'Non... non...': 'Nein... nein...',
    'Léa rentre chez elle.': 'Lea kommt nach Hause.',
    "Sur la table... une clé qu'elle n'a jamais vue.": 'Auf dem Tisch... ein Schlüssel, den sie noch nie gesehen hat.',
    "Elle s'assoit, la clé à la main.": 'Sie setzt sich, den Schlüssel in der Hand.',
    'Qui a bien pu la laisser là ?': 'Wer kann ihn nur dort hingelegt haben?',
    'Trois heures du matin. Encore un niveau, et je dors.': 'Drei Uhr morgens. Noch ein Level, dann schlafe ich.',
    'Bienvenue au niveau sept, Noah.': 'Willkommen in Level sieben, Noah.',
    'Attends... Comment il connaît mon prénom ?': 'Moment... Woher kennt er meinen Vornamen?',
    'Prends la clé. Ouvre la porte.': 'Nimm den Schlüssel. Öffne die Tür.',
    "La porte de ma chambre... Elle vient de s'ouvrir.": 'Die Tür zu meinem Zimmer... Sie hat sich gerade geöffnet.',
    "Quelqu'un arrive. Ne mets pas pause.": 'Jemand kommt. Drück nicht auf Pause.',
    "Il y a quelqu'un derrière la porte !": 'Da ist jemand hinter der Tür!',
    'Tu as perdu un cœur.': 'Du hast ein Herz verloren.',
    'Je mets pause... ou pas ?': 'Soll ich pausieren... oder nicht?',
    'Un requin géant nage dans une ville sous-marine.': 'Ein riesiger Hai schwimmt durch eine Unterwasserstadt.',
    'Léa saute au-dessus du ravin, puis grimpe sur la corniche.': 'Lea springt über die Schlucht und klettert dann auf den Felsvorsprung.',
    "Un hélicoptère rouge arrive sous l'orage.": 'Ein roter Hubschrauber kommt im Gewitter an.',
    "Léa saute au-dessus du ravin, puis grimpe sur la corniche. Un hélicoptère rouge arrive sous l'orage.":
        'Lea springt über die Schlucht und klettert dann auf den Felsvorsprung. Ein roter Hubschrauber kommt im Gewitter an.',
}


def satz(text):
    """übersetzt einen Text zeilenweise (Leerzeilen und Zeilenenden bleiben)"""
    if text in SAETZE: return SAETZE[text]
    teile = text.split('\n')
    return '\n'.join(SAETZE[z] if z in SAETZE else z if not z.strip() else fehler('Satz ohne Übersetzung', z) for z in teile)


def fehler(was, was2):
    raise SystemExit(f'demo_deutsch: {was}: {was2!r}')


# ---------- Auswahllisten (nach Kennung) ----------
GROESSEN = {'wide': 'Totale', 'full': 'Ganze Figur', 'medium': 'Halbnahe', 'close': 'Großaufnahme', 'extreme_close': 'Extreme Großaufnahme',
            'two_shot': 'Zwei Figuren', 'ots': 'Über die Schulter', 'dialogue': 'Dialog', 'pov': 'Sicht der Figur', 'insert': 'Objektdetail (Insert)'}
BEWEGUNGEN = {'static': 'Feste Kamera', 'dolly_in': 'Fährt langsam heran', 'dolly_out': 'Fährt langsam zurück', 'track': 'Fährt seitlich mit',
              'orbit': 'Umkreist die Figur', 'crane_up': 'Steigt auf', 'crane_down': 'Sinkt ab', 'follow': 'Folgt der Figur',
              'push_in': 'Fährt langsam heran', 'pull_out': 'Fährt langsam zurück', 'pan_left': 'Gleitet nach links', 'pan_right': 'Gleitet nach rechts',
              'pan_up': 'Gleitet nach oben', 'pan_down': 'Gleitet nach unten', 'drift': 'Langsames Treiben', 'handheld': 'Handkamera'}
UEBERGAENGE = {'cut': 'Schnitt', 'fade': 'Abblende auf Schwarz', 'flash': 'Weißer Blitz'}
GESICHTER = {'angry': 'Wütend', 'creature': 'Monster', 'grin': 'Unheimliches Grinsen', 'happy': 'Fröhlich', 'nervous': 'Besorgt', 'neutral': 'Neutral',
             'sad': 'Traurig', 'scared': 'Verängstigt', 'shocked': 'Schockiert', 'surprised': 'Überrascht', 'alien': 'Außerirdisch', 'bored': 'Gelangweilt',
             'calm': 'Ruhig', 'closed': 'Augen geschlossen', 'confused': 'Verwirrt', 'cool': 'Entspannt', 'crying': 'Weinend', 'determined': 'Entschlossen',
             'disgusted': 'Angewidert', 'dizzy': 'Benommen', 'double': 'Doppelt', 'evil': 'Böse', 'excited': 'Aufgeregt', 'fixed_smile': 'Starres Lächeln',
             'furious': 'Rasend', 'joy': 'Freudig', 'ko': 'K.O.', 'laugh': 'Lachend', 'love': 'Verliebt', 'pain': 'Schmerzverzerrt', 'predator': 'Raubtier',
             'predator_smile': 'Raubtierlächeln', 'proud': 'Stolz', 'robot': 'Roboter', 'shy': 'Schüchtern', 'silly': 'Albern', 'skull': 'Totenkopf',
             'sleeping': 'Schlafend', 'smile_sad': 'Trauriges Lächeln', 'smirk': 'Schiefes Grinsen', 'suspicious': 'Misstrauisch', 'talk': 'Sprechend',
             'thinking': 'Nachdenklich', 'tired': 'Müde', 'urgent': 'Eilig', 'wink': 'Zwinkernd', 'smile': 'Lächeln'}


def liste(paare, tabelle, was):
    return [[k, tabelle[k] if k in tabelle else fehler('Auswahl ohne Übersetzung ' + was, k)] for k, _ in paare]


def optionen(o):
    o = dict(o)
    o['transitions'] = liste(o['transitions'], UEBERGAENGE, 'Übergang')
    o['moves'] = liste(o['moves'], BEWEGUNGEN, 'Bewegung')
    o['faces'] = liste(o['faces'], GESICHTER, 'Gesicht')
    o['sizes'] = liste(o['sizes'], GROESSEN, 'Größe')
    return o


# ---------- Szenenplaner ----------
BEGRIFFE = {'saute': 'springt', 'ravin': 'Schlucht', 'grimpe*': 'klettert*', 'corniche': 'Felsvorsprung', 'helicoptere': 'Hubschrauber', 'orage': 'Gewitter',
            'requin': 'Hai', 'geant': 'riesig*', 'nage': 'schwimmt', 'ville sous-marine': 'Unterwasserstadt', "s'assoit": 'setzt sich', 'ouvre': 'öffne',
            'chambre': 'zimmer*',
            # Begriffe aus der Beschreibung der Szenarien (Anzeige im Fähigkeitsbericht, nicht an einen Text gebunden)
            'nuit': 'Nacht', 'eclair': 'Blitz', 'recule': 'weicht zurück', 'salon': 'Wohnzimmer', 'marche': 'geht', 'regarde': 'schaut', 'prend': 'nimmt'}
BEGRIFFE_PROJEKT = {  # im Fähigkeitsbericht eines Projekts stehen die Wörter groß und ohne Stern, wie sie angezeigt werden
    'ouvre': 'öffnet', 'chambre': 'Zimmer'}
ANGEFRAGT = {'ravin': 'Schlucht', 'corniche': 'Felsvorsprung', 'helicoptere': 'Hubschrauber', 'orage': 'Gewitter', 'requin': 'Hai', 'geant': 'riesig',
             'nage': 'schwimmt', 'ville sous-marine': 'Unterwasserstadt'}
NOTIZEN = {'': '', 'existe dans pixel3d seulement': 'gibt es nur in pixel3d', "aucune nage (pas d'eau praticable)": 'kein Schwimmen (kein begehbares Wasser)',
           "aucun milieu sous-marin (pas de rendu dans l'eau, pas de nage)": 'kein Unterwassermilieu (kein Rendering im Wasser, kein Schwimmen)'}
WIE = {'': '',
       'élément building avec "style": "rock" (falaise praticable), sol bas (ground_y)': 'Element building mit "style": "rock" (begehbare Felswand), tiefer Boden (ground_y)',
       'élément platform (y, rambarde, marquage helipad)': 'Element platform (y, Geländer, Helipad-Markierung)',
       'objet "mover" (vol, vol stationnaire) ou objet du décor': 'Objekt "mover" (Flug, Schwebeflug) oder Dekorobjekt',
       '"size" d\'un mover ou d\'une créature, "scale" d\'un personnage': '"size" eines mover oder einer Kreatur, "scale" einer Figur',
       'objet lightning_bolt (frappe un élément), ou "world": lightning (fenêtres)': 'Objekt lightning_bolt (trifft ein Element) oder "world": lightning (Fenster)',
       'walk_to avec "backwards": true': 'walk_to mit "backwards": true'}
WO = {'engines/pixel3d/world.py weather() (cœur)': 'engines/pixel3d/world.py weather() (Kern)', 'cœur du moteur': 'Kern des Motors'}
VERTRAG = {
    'builder(e, ctx) ajoute blocs, objets, niveaux praticables (ctx.walkable) et repères (compose.py)': 'builder(e, ctx) fügt Blöcke, Objekte, begehbare Ebenen (ctx.walkable) und Marker hinzu (compose.py)',
    'builder(p, color) -> boîtes r3d B()/C(), bas à y = 0, face avant vers -z (rot 0), moins de 80 boîtes ; animation possible avec p["_t"] (temps) quand l\'objet est un "mover"':
        'builder(p, color) -> r3d-Boxen B()/C(), Unterseite bei y = 0, Vorderseite zu -z (rot 0), weniger als 80 Boxen; Animation mit p["_t"] (Zeit) möglich, wenn das Objekt ein "mover" ist',
    'modification du cœur : garder les anciens épisodes identiques (tools/regress.py, tools/regress_v2.py)': 'Änderung am Kern: alte Episoden müssen identisch bleiben (tools/regress.py, tools/regress_v2.py)',
    'builder(color, swing, t, k, posture) -> boîtes face à +z, pieds à y = 0 ; posture "fly" pour le vol': 'builder(color, swing, t, k, posture) -> Boxen mit Blick nach +z, Füße bei y = 0; Haltung "fly" für den Flug',
    'fn(shot, track, action, t0) -> t1 : chemins (shot.walk), segments en l\'air (track.airs), flexions (track.squats), mains (track.reaches), événements sonores (track.events) ; partagé par PIXEL 3D et CONSOLE (acting/motion.py en exemple)':
        'fn(shot, track, action, t0) -> t1: Wege (shot.walk), Luftphasen (track.airs), Kniebeugen (track.squats), Hände (track.reaches), Klangereignisse (track.events); gemeinsam genutzt von PIXEL 3D und CONSOLE (acting/motion.py als Beispiel)',
    'generator(spec) -> spec RoomSet (places.py en exemple) ; ou un décor "composed" sans code': 'generator(spec) -> spec RoomSet (places.py als Beispiel); oder ein "composed"-Dekor ohne Code'}
ABNAHME = {'rendu déterministe (deux rendus identiques)': 'deterministisches Rendering (zwei identische Renderings)',
           'anciens épisodes inchangés (garde de non-régression)': 'alte Episoden unverändert (Schutz gegen Regression)',
           'python -m hstudio extension test <id>, puis promote': 'python -m hstudio extension test <id>, dann promote'}
STATUS = {'demandée': 'angefragt'}
BEDARF = {'manquant': 'fehlend', 'partiel (à rendre natif)': 'teilweise (nativ zu machen)'}
TITEL = {'Hélicoptère': 'Hubschrauber'}
STATUS_ERW = {'stable': 'stabil'}


def nachschlagen(tabelle, wert, was):
    if wert in tabelle: return tabelle[wert]
    fehler('Planer-Text ohne Übersetzung (' + was + ')', wert)


def abnahme(a):
    m = re.fullmatch(r'une scène de test montre « (\w+) » dans un vrai rendu, dans les deux formats', a)
    if m: return f'eine Testszene zeigt „{m.group(1)}“ in einem echten Rendering, in beiden Formaten'
    return nachschlagen(ABNAHME, a, 'Abnahmekriterium')


def anfrage(q):
    q = dict(q)
    if 'asked_by' in q: q['asked_by'] = [nachschlagen(ANGEFRAGT, w, 'asked_by') for w in q['asked_by']]
    if 'context' in q: q['context'] = satz(q['context'])
    for k, t, was in (('approximation', NOTIZEN, 'approximation'), ('where', None, 'where'), ('contract', VERTRAG, 'contract'), ('status', STATUS, 'status'), ('need', BEDARF, 'need')):
        if k not in q: continue
        if k == 'where':
            m = re.fullmatch(r'extension (library/extensions/\w+/ : .*)', q[k])
            q[k] = 'Erweiterung ' + m.group(1) if m else nachschlagen(WO, q[k], 'where')
        else: q[k] = nachschlagen(t, q[k], k)
    if 'acceptance' in q: q['acceptance'] = [abnahme(a) for a in q['acceptance']]
    return q


def bedarf(n, projekt):
    n = dict(n)
    n['terms'] = [(BEGRIFFE_PROJEKT.get(t) if projekt and t in BEGRIFFE_PROJEKT else nachschlagen(BEGRIFFE, t, 'term')) for t in n['terms']]
    n['note'] = nachschlagen(NOTIZEN, n.get('note', ''), 'note')
    n['how'] = nachschlagen(WIE, n.get('how', ''), 'how')
    return n


def planer(rep, projekt=False):
    r = dict(rep)
    if 'needs' in r: r['needs'] = [bedarf(n, projekt) for n in r['needs']]
    if 'requests' in r: r['requests'] = [anfrage(q) for q in r['requests']]
    if 'extensions' in r:
        r['extensions'] = [dict(e, title=nachschlagen(TITEL, e['title'], 'Erweiterung') if e.get('title') else e.get('title'),
                                status=STATUS_ERW.get(e.get('status'), e.get('status'))) for e in r['extensions']]
    return r


def faehigkeiten(cap):
    if not cap: return cap
    cap = dict(cap)
    if cap.get('plan'): cap['plan'] = planer(cap['plan'], projekt=True)
    au = cap.get('audit') or {}
    rq = au.get('requires')
    if rq:
        au = dict(au); rq = dict(rq); rq['needs'] = [bedarf(n, True) for n in rq.get('needs', [])]; rq['requests'] = [anfrage(q) for q in rq.get('requests', [])]; au['requires'] = rq; cap['audit'] = au
    if au.get('gaps'): fehler('Lücken im Fähigkeitsbericht haben noch keine Übersetzung', au['gaps'])
    if cap.get('gap_requests'): cap['gap_requests'] = [anfrage(q) for q in cap['gap_requests']]
    return cap


def projekte_de(liste_fr):
    aus = []
    for p in liste_fr:
        if p['slug'] not in PROJEKT: fehler('Projekt ohne Übersetzung', p['slug'])
        slug, name, teil = PROJEKT[p['slug']]
        q = dict(p, slug=slug, vorschau_ordner=p['slug'])
        q['meta'] = dict(p['meta'], name=name, part_label=teil)
        q['script'] = satz(p['script'])
        q['lines'] = [dict(z, tts=satz(z['tts']) if z['tts'] else '', display=satz(z['display']) if z['display'] else '', text=satz(z['text']) if z['text'] else '') for z in p['lines']]
        q['capabilities'] = faehigkeiten(p['capabilities'])
        q['optionen'] = [optionen(o) for o in p['optionen']]
        aus.append(q)
    return aus


def plan_de(plan_fr):
    aus = {}
    for text, motoren in plan_fr.items():
        aus[satz(text)] = {eng: planer(rep) for eng, rep in motoren.items()}
    return aus


# ---------- Katalog ----------
KATEGORIEN = {'Décors': 'Dekor', 'Lieux': 'Orte', 'Habits et accessoires': 'Kleidung und Zubehör', 'Personnages': 'Figuren', 'Animaux': 'Tiere', 'Créatures': 'Kreaturen',
              'Visages': 'Gesichter', 'Scènes': 'Szenen', 'Écran de la console': 'Konsolenbildschirm', 'Palettes': 'Paletten', 'Interface': 'Oberfläche'}
GRUPPEN = {'PIXEL 3D converti': 'PIXEL 3D konvertiert', 'Tenues': 'Outfits', 'Chapeaux': 'Hüte', 'Coiffures': 'Frisuren', 'Objets en main': 'Gegenstände in der Hand',
           'Personnages animés (PIXEL 3D converti)': 'Animierte Figuren (PIXEL 3D konvertiert)', 'Animaux animés (PIXEL 3D converti)': 'Animierte Tiere (PIXEL 3D konvertiert)',
           'Monstres animés (notre rig)': 'Animierte Monster (unser Rig)', 'Expressions (43)': 'Ausdrücke (43)', 'Décors dessinés à plat': 'Flach gezeichnete Kulissen',
           'Écran pixel vert 160×144': 'Grüner Pixelbildschirm 160×144', 'Palettes de la direction « aplat »': 'Paletten der Richtung „Flächig“',
           'Expressions 2D (20)': '2D-Ausdrücke (20)', 'Personnages 2D': '2D-Figuren', 'Cartes de règle': 'Regelkarten', "Interface à l'écran": 'Bildschirmoberfläche'}
LIZENZEN = {'PIXEL 3D (créé pour ce studio)': 'PIXEL 3D (für dieses Studio geschaffen)', 'créé pour ce studio (original)': 'für dieses Studio geschaffen (Original)',
            'créé pour ce studio (CONSOLE 2D)': 'für dieses Studio geschaffen (KONSOLE 2D)'}
BESCHREIBUNGEN = {
    'très grand, bras trop longs, sans visage, costume noir, tentacules dans le dos': 'sehr groß, zu lange Arme, ohne Gesicht, schwarzer Anzug, Tentakel auf dem Rücken',
    'long visage pâle, yeux et sourire fins qui brillent, chapeau haut': 'langes blasses Gesicht, schmale leuchtende Augen und ein schmales leuchtendes Lächeln, hoher Hut',
    'cornes, ailes qui battent, queue, yeux incandescents, dos voûté': 'Hörner, schlagende Flügel, Schwanz, glühende Augen, gebeugter Rücken',
    "à quatre pattes, membres tordus, tête relevée, épine dorsale saillante ; `height` = sa taille s'il se redressait": 'auf allen vieren, verdrehte Glieder, erhobener Kopf, hervortretende Wirbelsäule; `height` = seine Größe, wenn er sich aufrichten würde',
    'massif, épaules et bras démesurés, petite tête, poings énormes': 'massig, übergroße Schultern und Arme, kleiner Kopf, riesige Fäuste',
    'sans jambes, drapé en lambeaux, flotte au-dessus du sol, yeux pâles': 'ohne Beine, in Fetzen gehüllt, schwebt über dem Boden, blasse Augen',
    'quatre bras supplémentaires qui bougent à leur propre rythme, visage à quatre yeux': 'vier zusätzliche Arme, die sich in ihrem eigenen Rhythmus bewegen, Gesicht mit vier Augen',
    'tête trop grande sur un cou trop long, grands yeux sombres, corps filiforme': 'zu großer Kopf auf zu langem Hals, große dunkle Augen, fadendünner Körper',
    'forme humaine faite de centaines de petits cubes qui frémissent': 'menschliche Gestalt aus Hunderten kleiner, zitternder Würfel',
    'petit, grosse tête pâle, trous noirs à la place des yeux, longs bras qui pendent': 'klein, großer blasser Kopf, schwarze Löcher statt Augen, lange herabhängende Arme',
    "bois, visage peint, membres fins qui sursautent, fils jusqu'à une barre de commande": 'Holz, bemaltes Gesicht, dünne zuckende Glieder, Fäden bis zu einem Spielkreuz',
    'sac sur la tête, paille aux poignets, bras en croix, démarche raide': 'Sack über dem Kopf, Stroh an den Handgelenken, ausgebreitete Arme, steifer Gang',
    'la chambre : lit, console, lampe, fenêtre, porte': 'das Zimmer: Bett, Konsole, Lampe, Fenster, Tür',
    'la même chambre avec une silhouette noire aux yeux blancs': 'dasselbe Zimmer mit einer schwarzen Silhouette mit weißen Augen',
    'lumière sous la porte : warm, orange, red, green, white': 'Licht unter der Tür: warm, orange, red, green, white',
    'la porte, lumière dessous et ombre de deux pieds': 'die Tür, Licht darunter und der Schatten zweier Füße',
    "la porte qui s'ouvre (0 à 1), deux yeux dans l'entrebâillement": 'die sich öffnende Tür (0 bis 1), zwei Augen im Türspalt',
    'couloir sombre en perspective': 'dunkler Flur in Perspektive',
    'couloir avec une silhouette au fond': 'Flur mit einer Silhouette im Hintergrund',
    'fenêtre de nuit et lune': 'Nachtfenster und Mond',
    'silhouette debout derrière la vitre': 'Silhouette, die hinter der Scheibe steht',
    'la console dans les mains, écran visible': 'die Konsole in den Händen, Bildschirm sichtbar',
    "l'écran vert 160x144 en plein cadre": 'der grüne Bildschirm 160x144 im Vollbild',
    'gros plan du visage ; `expression` : voir l\'onglet Visages': 'Großaufnahme des Gesichts; `expression`: siehe Reiter Gesichter',
    'carte de règle avec une ligne dorée et une icône': 'Regelkarte mit einer goldenen Linie und einem Symbol',
    'deux scènes côte à côte': 'zwei Szenen nebeneinander',
    'écran de la console, plein cadre : `scene.screen`': 'Konsolenbildschirm im Vollbild: `scene.screen`',
    'nuit bleue (défaut)': 'blaue Nacht (Standard)',
    'alerte rouge (le jeu punit)': 'roter Alarm (das Spiel bestraft)',
    'vert console (le jeu prend la pièce)': 'Konsolengrün (das Spiel nimmt die Münze)',
    'aube (fin de nuit)': 'Morgengrauen (Ende der Nacht)',
    'personnage de plain-pied dans la pièce (couche de jeu d\'acteur partagée)': 'Figur in voller Größe im Raum (gemeinsame Schauspielebene)',
    'icône de carte de règle': 'Symbol der Regelkarte',
    'niveau, horloge, cœurs : `"ui": {"hud": true}` (réglages dans `hud` à la racine)': 'Level, Uhr, Herzen: `"ui": {"hud": true}` (Einstellungen unter `hud` auf oberster Ebene)',
    '`"ui": {"choice": {"title", "A", "B"}}`': '`"ui": {"choice": {"title", "A", "B"}}`',
    'compte à rebours de la durée du plan : `"ui": {"timer": true}`': 'Countdown der Einstellungsdauer: `"ui": {"timer": true}`',
    'sous-titre à plaque : `"ui": {"subs": "mid"}`': 'Untertitel auf Plakette: `"ui": {"subs": "mid"}`',
    '`"ui": {"endcard": {"title", "part", "headline", "cta", "button"}}` (pensé pour le 9:16)': '`"ui": {"endcard": {"title", "part", "headline", "cta", "button"}}` (für 9:16 gedacht)',
}
M_ZUSATZ = re.compile(r'^gros plan ; en plan large : (`"face": "\w+"`) sur un acteur$')
SCHNIPSEL = [(' dans l\'épisode)', ' in der Episode)'), ('(réglages :', '(Regler:'), ("(à la racine de l'épisode, avec ", '(auf oberster Ebene der Episode, mit '), ('   puis   ', '   dann   ')]

# Anzeigenamen: Zeile "französischer oder englischer Name | deutscher Name". Die Kennungen der Motor-Reihen bleiben als Zusatz in Klammern:
# (od) = Detailobjekt, (qi) = Innenausstattung eines Viertels, (qt) = Fassadenteil eines Viertels (Reihenkürzel des Motors).
NAMEN = """
bed|Bett
nightstand|Nachttisch
desk|Schreibtisch
chair|Stuhl
wardrobe|Kleiderschrank
shelf|Regal
sofa|Sofa
table|Tisch
lamp|Lampe
tv|Fernseher
mirror|Spiegel
boxes|Kartons
plant|Pflanze
painting|Gemälde
rug|Teppich
fridge|Kühlschrank
counter|Theke
locker|Spind
hospital bed|Krankenhausbett
door|Tür
window|Fenster
streetlight|Straßenlaterne
tree|Baum
car|Auto
bench|Bank
fence|Zaun
column|Säule
crate|Kiste
toy|Spielzeug
ac unit|Klimagerät
air vent|Lüftungsschacht
altar|Altar
antenna|Antenne
arcade|Spielautomat
arch|Torbogen
armchair|Sessel
autumn tree|Herbstbaum
balloons|Luftballons
bar|Bar
bare bulb|Nackte Glühbirne
barrel|Fass
bathtub|Badewanne
beach towel|Strandtuch
beach umbrella|Sonnenschirm
bed double|Doppelbett
bicycle|Fahrrad
billboard|Reklametafel
birch|Birke
blackboard|Tafel
blossom tree|Blütenbaum
boat|Boot
books pile|Bücherstapel
bookshelf|Bücherregal
bottles|Flaschen
boulder|Felsblock
bridge|Brücke
broken glass|Glasscherben
bucket|Eimer
bunk bed|Etagenbett
bus|Bus
bus stop|Bushaltestelle
bush|Busch
cactus|Kaktus
cafe table|Cafétisch
cage|Käfig
campfire|Lagerfeuer
candles|Kerzen
cardboard stack|Kartonstapel
cash register|Kasse
castle wall|Burgmauer
cauldron|Kessel
chair knocked|Umgekippter Stuhl
chest|Truhe
child drawing|Kinderzeichnung
chimney stack|Schornstein
christmas tree|Weihnachtsbaum
clock|Uhr
clothes pile|Kleiderhaufen
coat rack|Garderobe
cobweb|Spinnennetz
coffin|Sarg
computer|Computer
concrete pillar|Betonpfeiler
control panel|Schalttafel
counter long|Lange Theke
crib|Kinderbett
cross|Kreuz
crystal|Kristall
cups|Tassen
curtains|Vorhänge
damp stain|Feuchtigkeitsfleck
dead tree|Toter Baum
desk lamp|Schreibtischlampe
dining table|Esstisch
dock|Anlegesteg
doll broken|Kaputte Puppe
door frame|Türrahmen
dumpster|Müllcontainer
dust sheet|Staubschutzlaken
exit sign|Notausgangsschild
fire escape|Feuertreppe
fire extinguisher|Feuerlöscher
fireplace|Kamin
flag|Fahne
floor drain|Bodenablauf
floor lamp|Stehlampe
flowers|Blumen
fountain|Springbrunnen
framed photo|Gerahmtes Foto
gate|Tor
gift pile|Geschenkestapel
graffiti|Graffiti
gravestone|Grabstein
hammock|Hängematte
handprint|Handabdruck
handrail|Handlauf
hay bale|Heuballen
hedge|Hecke
horse cart|Pferdewagen
hospital monitor|Krankenhausmonitor
house|Haus
hydrant|Hydrant
igloo|Iglu
iv stand|Infusionsständer
jerrycan|Kanister
kitchen|Küche
ladder|Leiter
lantern|Laterne
laptop|Laptop
laundry line|Wäscheleine
letterboxes|Briefkästen
light switch|Lichtschalter
log|Baumstamm
mailbox|Briefkasten
market stall|Marktstand
mirror cracked|Gesprungener Spiegel
mushroom|Pilz
neon tube|Neonröhre
note|Notiz
notes wall|Notizwand
noticeboard|Pinnwand
open diary|Offenes Tagebuch
pallet|Palette
palm|Palme
papers scattered|Verstreute Papiere
parking sign|Parkschild
pendant lamp|Hängelampe
phone booth|Telefonzelle
piano|Klavier
picnic|Picknick
picture frames|Bilderrahmen
pine|Kiefer
pipes|Rohre
plastic curtain|Plastikvorhang
police car|Polizeiauto
portal|Portal
poster|Poster
pram|Kinderwagen
puddle ring|Pfützenringe
pumpkin|Kürbis
qi bookcase|Bücherregal (qi)
qi books|Bücher (qi)
qi cakecase|Kuchenvitrine (qi)
qi crates|Kisten (qi)
qi curtain|Vorhang (qi)
qi cushions|Kissen (qi)
qi doormat|Fußmatte (qi)
qi elevator|Aufzug (qi)
qi frame|Rahmen (qi)
qi lamp|Lampe (qi)
qi mailboxes|Briefkästen (qi)
qi mannequin|Schaufensterpuppe (qi)
qi menu|Speisekarte (qi)
qi pendants|Hängelampen (qi)
qi plant|Pflanze (qi)
qi rug|Teppich (qi)
qi shelving|Regalsystem (qi)
qi stairs|Treppe (qi)
qi stool|Hocker (qi)
qi tableware|Geschirr (qi)
qi vase|Vase (qi)
qt ac|Klimagerät (qt)
qt awning|Markise (qt)
qt balcony|Balkon (qt)
qt blade|Auslegerschild (qt)
qt boug|Bougainvillea (qt)
qt canopy|Vordach (qt)
qt chimney|Schornstein (qt)
qt fascia|Ladenschild (qt)
qt fire escape|Feuertreppe (qt)
qt lamp|Lampe (qt)
qt lamp cool|Kaltes Licht (qt)
qt lamp neon|Neonlampe (qt)
qt neon|Neonschild (qt)
qt porch|Vorbau (qt)
qt stoop|Eingangstreppe (qt)
qt terrace|Terrasse (qt)
qt windowbox|Blumenkasten (qt)
radiator|Heizkörper
rock|Fels
rock pile|Steinhaufen
rocket|Rakete
roof vent|Dachlüfter
ruins|Ruinen
sailboat|Segelboot
sandcastle|Sandburg
satellite dish|Satellitenschüssel
scarecrow|Vogelscheuche
school desk|Schulbank
scratch marks|Kratzspuren
shop|Laden
sign|Schild
signpost|Wegweiser
sink|Spüle
skylight|Dachfenster
slide|Rutsche
snow pine|Verschneite Kiefer
snowman|Schneemann
space window|Weltraumfenster
stair flight|Treppenlauf
stair hut|Treppenhäuschen
stairs|Treppe
statue|Statue
steam vent|Dampfaustritt
stove|Herd
stump|Baumstumpf
suitcase|Koffer
swing|Schaukel
tall grass|Hohes Gras
tally marks|Strichliste
tent|Zelt
throne|Thron
toilet|Toilette
torch wall|Wandfackel
tower|Turm
toy scatter|Verstreutes Spielzeug
traffic light|Ampel
trash can|Mülleimer
tree round|Runder Baum
trolley|Rollwagen
truck|Lastwagen
tv old|Alter Fernseher
tv stand|Fernsehtisch
tyre stack|Reifenstapel
vase|Vase
vending machine|Verkaufsautomat
wall clock|Wanduhr
wall crack|Mauerriss
wall sconce|Wandleuchte
wall shelf|Wandregal
washing machine|Waschmaschine
water tank|Wassertank
waterfall|Wasserfall
well|Brunnen
wheelchair|Rollstuhl
wheelie bin|Mülltonne
whiteboard|Whiteboard
od phone rotary|Wählscheibentelefon (od)
od phone desk|Tischtelefon (od)
od smartphone|Smartphone (od)
od switchboard|Vermittlungstafel (od)
od cup|Tasse (od)
od mug|Becher (od)
od glass|Glas (od)
od bottle|Flasche (od)
od plate|Teller (od)
od cutlery|Besteck (od)
od couvert|Gedeck (od)
od book|Buch (od)
od notebook|Notizbuch (od)
od paper|Papier (od)
od keys|Schlüssel (od)
od desk lamp|Schreibtischlampe (od)
od bedside lamp|Nachttischlampe (od)
od nightstand|Nachttisch (od)
od laptop|Laptop (od)
od monitor|Monitor (od)
od computer|Computer (od)
od tv|Fernseher (od)
od tv crt|Röhrenfernseher (od)
od radio|Radio (od)
od clock|Uhr (od)
od crowbar|Brecheisen (od)
od flashlight|Taschenlampe (od)
od candle|Kerze (od)
od photo frame|Bilderrahmen (od)
od plant|Pflanze (od)
od bag|Tasche (od)
od suitcase|Koffer (od)
od kettle|Wasserkocher (od)
od coffee maker|Kaffeemaschine (od)
od toaster|Toaster (od)
od microwave|Mikrowelle (od)
od saucepan|Kochtopf (od)
od frying pan|Bratpfanne (od)
od kitchen knife|Küchenmesser (od)
od cutting board|Schneidebrett (od)
od bowl|Schüssel (od)
od teapot|Teekanne (od)
od pill box|Pillendose (od)
od toothbrush glass|Zahnputzbecher (od)
od soap|Seife (od)
od towel|Handtuch (od)
od hair dryer|Föhn (od)
od carnet|Notizheft (od)
od bouquet|Blumenstrauß (od)
od billet|Ticket (od)
od fusible|Sicherung (od)
od camera view|Kameraansicht (od)
od phone flash|Handyblitz (od)
od typewriter|Schreibmaschine (od)
od tape recorder|Tonbandgerät (od)
od cassette|Kassette (od)
od film camera|Filmkamera (od)
od polaroid|Polaroid (od)
od walkie talkie|Funkgerät (od)
od binoculars|Fernglas (od)
od teddy bear|Teddybär (od)
od porcelain doll|Porzellanpuppe (od)
od music box|Spieluhr (od)
od hand mirror|Handspiegel (od)
od envelope|Briefumschlag (od)
od candelabra|Kerzenleuchter (od)
od axe|Axt (od)
od knife horror|Horrormesser (od)
od syringe|Spritze (od)
helicopter|Hubschrauber
alley|Gasse
appartement|Wohnung
astroport|Raumhafen
attic|Dachboden
automne|Herbst
basement|Keller
bataille|Schlacht
bathroom|Badezimmer
beach|Strand
bedroom|Schlafzimmer
boutique|Boutique
cafe|Café
cafe quartier|Café im Viertel
campsite|Zeltplatz
castle|Burg
cave|Höhle
cimetiere calme|Ruhiger Friedhof
cinema salle|Kinosaal
cite|Wohnsiedlung
city street|Stadtstraße
classroom|Klassenzimmer
corridor|Flur
countryside|Landschaft
desert|Wüste
escalier immeuble|Treppenhaus im Wohnhaus
feu|Feuer
forest|Wald
glace|Eis
graveyard|Friedhof
hall immeuble|Hausflur im Wohnhaus
hospital room|Krankenzimmer
invasion|Invasion
island|Insel
kid bedroom|Kinderzimmer
lab|Labor
lake|See
library|Bibliothek
living room|Wohnzimmer
lune|Mond
lycee riviere|Schule am Fluss
mountain|Berg
office|Büro
parc|Park
park|Park
parking|Parkplatz
phare foret|Leuchtturm im Wald
phare interieur|Leuchtturm innen
pluie|Regen
quartier|Stadtviertel
river|Fluss
salon maison|Wohnzimmer im Haus
selene|Selene
snow village|Schneedorf
snowy forest|Verschneiter Wald
space station|Raumstation
stairwell|Treppenhaus
station|Station
talus|Böschung
throne room|Thronsaal
toit|Dach
vaisseau|Raumschiff
village|Dorf
ville|Stadt
volcano|Vulkan
hoodie|Kapuzenpullover
tshirt|T-Shirt
shirt|Hemd
suit|Anzug
dress|Kleid
coat|Mantel
armor|Rüstung
robe|Gewand
apron|Schürze
lab coat|Laborkittel
uniform|Uniform
spacesuit|Raumanzug
gilet|Weste
pyjama|Schlafanzug
peignoir|Bademantel
chemise nuit|Nachthemd
veste feu|Feuerwehrjacke
polo|Poloshirt
cap|Kappe
beanie|Wollmütze
hood|Kapuze
tophat|Zylinder
crown|Krone
wizard|Zauberhut
witch|Hexenhut
pirate|Piratenhut
chef|Kochmütze
police|Polizeimütze
helmet|Helm
astronaut|Astronautenhelm
cowboy|Cowboyhut
party|Partyhut
casque f1|Rennhelm (F1)
short|Kurz
long|Lang
ponytail|Pferdeschwanz
bun|Dutt
spiky|Stachelig
curly|Lockig
bald|Glatze
strands|Strähnen
strands long|Lange Strähnen
strands ponytail|Strähnen mit Pferdeschwanz
phone|Telefon
cup|Tasse
book|Buch
flashlight|Taschenlampe
candle|Kerze
key|Schlüssel
letter|Brief
flower|Blume
gift|Geschenk
sword|Schwert
ball|Ball
bag|Tasche
umbrella|Regenschirm
balloon|Luftballon
microphone|Mikrofon
staff|Stab
wand|Zauberstab
torch|Fackel
shield|Schild
map|Karte
guitar|Gitarre
bottle|Flasche
apple|Apfel
camera|Kamera
ice cream|Eis am Stiel
newspaper|Zeitung
crowbar|Brecheisen
handset|Hörer
mobile|Handy
mobile 0213|Handy 0213
mobile 0214|Handy 0214
printout|Ausdruck
notebook|Notizbuch
od handset|Hörer (od)
od smartphone montre|Smartphone zeigend (od)
od wine glass|Weinglas (od)
od book open|Offenes Buch (od)
od carnet ouvert|Offenes Notizheft (od)
od carnet montre|Notizheft zeigend (od)
od long fingers|Lange Finger (od)
od food box|Essensbox (od)
od polaroid photo|Polaroidfoto (od)
zombie|Zombie
skeleton|Skelett
vampire|Vampir
robot|Roboter
alien|Außerirdischer
knight|Ritter
doctor|Arzt
nurse|Krankenschwester
firefighter|Feuerwehrmann
king|König
queen|Königin
princess|Prinzessin
superhero|Superheld
ninja|Ninja
student|Student
teacher|Lehrer
businessman|Geschäftsmann
grandpa|Opa
grandma|Oma
kid|Kind
baby|Baby
receptionniste|Empfangsdame
cliente agee|Ältere Kundin
client pyjama|Kunde im Schlafanzug
cliente peignoir|Kundin im Bademantel
client tshirt|Kunde im T-Shirt
cliente nuisette|Kundin im Nachthemd
ado pyjama|Teenager im Schlafanzug
pompier|Feuerwehrmann A
pompier 2|Feuerwehrmann B
chef pompier|Feuerwehrchef
technicien|Techniker
mere fantome|Geistermutter
garcon fantome|Geisterjunge
dog|Hund
cat|Katze
bird|Vogel
horse|Pferd
cow|Kuh
rabbit|Kaninchen
chicken|Huhn
pig|Schwein
sheep|Schaf
duck|Ente
dragon|Drache
spider|Spinne
ghost|Geist
bird fly|Fliegender Vogel
dragon fly|Fliegender Drache
dog sit|Sitzender Hund
cat lie|Liegende Katze
Grand homme maigre|Großer dünner Mann
Homme au chapeau haut|Mann mit hohem Hut
Démon|Dämon
Rampant|Kriecher
Colosse|Koloss
Spectre drapé|Verhüllter Geist
Multi-bras|Vielarmiger
Guetteur|Beobachter
Silhouette de cubes|Würfelsilhouette
Enfant étrange|Seltsames Kind
Marionnette|Marionette
Épouvantail|Vogelscheuche
Chambre|Zimmer
Chambre, silhouette|Zimmer, Silhouette
Chambre, lumière sous la porte|Zimmer, Licht unter der Tür
Porte|Tür
Porte entrouverte|Angelehnte Tür
Couloir|Flur
Couloir, silhouette|Flur, Silhouette
Fenêtre|Fenster
Fenêtre, silhouette|Fenster, Silhouette
Console en main|Konsole in der Hand
Écran plein cadre|Bildschirm im Vollbild
Visage du joueur|Gesicht des Spielers
Carte de règle|Regelkarte
Écran partagé|Geteilter Bildschirm
Écran menu|Bildschirm Menü
Écran text|Bildschirm Text
Écran room|Bildschirm Zimmer
Écran door|Bildschirm Tür
Écran eyes|Bildschirm Augen
Écran static|Bildschirm Rauschen
Écran warning|Bildschirm Warnung
Écran level|Bildschirm Level
Écran pause|Bildschirm Pause
Écran face|Bildschirm Gesicht
Écran timer|Bildschirm Timer
Night|Nacht
Alert|Alarm
Game|Spiel
Dawn|Morgengrauen
angelica|Angelica
continental|Continental
dame bleu pale|Dame in Hellblau
dame champagne|Dame in Champagner
dame ivoire|Dame in Elfenbein
dame lilas|Dame in Flieder
dame menthe|Dame in Mint
dame or|Dame in Gold
dame peche|Dame in Pfirsich
dame rose|Dame in Rosa
dame tartan|Dame in Tartan
dame vieux rose|Dame in Altrosa
eliza|Eliza
eliza souvenir|Eliza (Erinnerung)
hamilton|Hamilton
homme bleu 1|Mann in Blau 1
homme bleu 2|Mann in Blau 2
homme bleu 3|Mann in Blau 3
homme bleu 4|Mann in Blau 4
homme chauve rouge|Glatzköpfiger Mann in Rot
homme rouge 1|Mann in Rot 1
homme rouge 2|Mann in Rot 2
homme rouge 3|Mann in Rot 3
lafayette|Lafayette
laurens|Laurens
lea|Lea
mamie|Omi
noah|Noah
peggy|Peggy
rex|Rex
tom|Tom
veilleur|Nachtwächter
washington|Washington
zoe|Zoe
Règle door x|Regelkarte Tür x
Règle eye x|Regelkarte Auge x
Règle clock x|Regelkarte Uhr x
Règle phone x|Regelkarte Telefon x
Règle console x|Regelkarte Konsole x
Règle bed x|Regelkarte Bett x
Règle bulb|Regelkarte Glühbirne
Cartouche HUD|HUD-Anzeige
Choix A / B|Auswahl A / B
Minuteur|Zeitgeber
Sous-titre|Untertitel
Écran de fin|Endbildschirm
"""
NAME = dict(z.split('|', 1) for z in NAMEN.strip().split('\n'))
# Namen, die in der Gruppe der Hüte oder Figuren anders zu übersetzen sind als sonst (gleicher Schlüssel, andere Bedeutung)
NAME_GRUPPE = {('Tenues', 'robe'): 'Gewand', ('Chapeaux', 'wizard'): 'Zauberhut', ('Chapeaux', 'witch'): 'Hexenhut', ('Chapeaux', 'pirate'): 'Piratenhut',
               ('Chapeaux', 'chef'): 'Kochmütze', ('Chapeaux', 'police'): 'Polizeimütze', ('Chapeaux', 'astronaut'): 'Astronautenhelm', ('Chapeaux', 'cowboy'): 'Cowboyhut',
               ('Chapeaux', 'party'): 'Partyhut', ('Chapeaux', 'antenna'): 'Antennenhut',
               ('Personnages animés (PIXEL 3D converti)', 'wizard'): 'Zauberer', ('Personnages animés (PIXEL 3D converti)', 'witch'): 'Hexe',
               ('Personnages animés (PIXEL 3D converti)', 'pirate'): 'Pirat', ('Personnages animés (PIXEL 3D converti)', 'chef'): 'Koch',
               ('Personnages animés (PIXEL 3D converti)', 'police'): 'Polizist', ('Personnages animés (PIXEL 3D converti)', 'astronaut'): 'Astronaut',
               ('Personnages animés (PIXEL 3D converti)', 'cowboy'): 'Cowboy', ('Personnages 2D', 'wizard'): 'Zauberer', ('Personnages 2D', 'witch'): 'Hexe',
               ('Personnages 2D', 'pirate'): 'Pirat', ('Personnages 2D', 'chef'): 'Koch', ('Personnages 2D', 'police'): 'Polizist', ('Personnages 2D', 'astronaut'): 'Astronaut',
               ('Personnages 2D', 'cowboy'): 'Cowboy', ('Personnages 2D', 'alien'): 'Außerirdischer', ('Personnages animés (PIXEL 3D converti)', 'alien'): 'Außerirdischer',
               ('Personnages 2D', 'robot'): 'Roboter', ('Personnages animés (PIXEL 3D converti)', 'robot'): 'Roboter',
               ('Lieux', 'bus'): 'Bus (innen)', ('Lieux', 'shop'): 'Laden', ('Lieux', 'kitchen'): 'Küche',
               ('Objets en main', 'cup'): 'Tasse'}


def name_de(e):
    n, g = e['name'], e['group']
    if e['category'] == 'Visages':
        k = n.replace(' ', '_')
        if k not in GESICHTER: fehler('Gesicht ohne Übersetzung', n)
        return GESICHTER[k]
    if (g, n) in NAME_GRUPPE: return NAME_GRUPPE[(g, n)]
    if (e['category'], n) in NAME_GRUPPE: return NAME_GRUPPE[(e['category'], n)]
    if n not in NAME: fehler('Katalogname ohne Übersetzung', f"{e['id']} {n}")
    return NAME[n]


def katalog_de(eintraege):
    aus = []
    for e in eintraege:
        q = dict(e)
        q['name'] = name_de(e)
        q['category'] = KATEGORIEN[e['category']] if e['category'] in KATEGORIEN else fehler('Kategorie', e['category'])
        q['group'] = GRUPPEN[e['group']] if e['group'] in GRUPPEN else fehler('Gruppe', e['group'])
        if e.get('license'): q['license'] = LIZENZEN[e['license']] if e['license'] in LIZENZEN else fehler('Lizenz', e['license'])
        if e.get('desc'):
            d = e['desc']; m = M_ZUSATZ.match(d)
            q['desc'] = f'Großaufnahme; in der Totale: {m.group(1)} bei einer Figur' if m else BESCHREIBUNGEN[d] if d in BESCHREIBUNGEN else fehler('Beschreibung', d)
        if e.get('snippet'):
            s = e['snippet']
            for a, b in SCHNIPSEL: s = s.replace(a, b)
            q['snippet'] = s
        aus.append(q)
    return aus


# ---------- Prüfung ----------
FRANZ = re.compile(r"[éèêàçùûôîïœ«»]|\b(le|la|les|une|pour|dans|avec|vous|cette|qui|que|pas|aux|elle|aucun|aucune|votre|vos|chaque|donc|ton|tes|mais|sans)\b")
ERLAUBT = re.compile(r'^(engines/|acting/|library/|extension:|tools/)|^pixel3d$')


def franzoesisch_suchen(x, pfad='', skip=()):
    """gibt Pfade von Zeichenketten zurück, die noch französisch aussehen (Kennungen, Pfade und der Episodentext werden übersprungen)"""
    funde = []
    if isinstance(x, str):
        if FRANZ.search(x.replace('Café', 'Cafe')) and not ERLAUBT.match(x): funde.append((pfad, x[:80]))
    elif isinstance(x, list):
        for i, v in enumerate(x): funde += franzoesisch_suchen(v, f'{pfad}[{i}]', skip)
    elif isinstance(x, dict):
        for k, v in x.items():
            if k in skip: continue
            funde += franzoesisch_suchen(v, f'{pfad}.{k}', skip)
    return funde


def lesen(p): return json.loads(Path(p).read_text(encoding='utf-8'))


def schreiben(p, daten):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(daten, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def uebersetzen(fr=DATEN / 'fr', de=DATEN / 'de'):
    projekte = projekte_de(lesen(fr / 'projekte.json')); plan = plan_de(lesen(fr / 'plan.json')); katalog = katalog_de(lesen(fr / 'katalog.json'))
    # die Episodendatei trägt Motorkennungen (porte, canape) und die in die Bilder gemalten Texte; sie wird nicht angezeigt
    funde = franzoesisch_suchen(projekte, 'projekte', skip=('episode', 'szenario', 'notes', 'datei', 'motor', 'slug', 'vorschau_ordner', 'used', 'source', 'name_id'))
    funde += franzoesisch_suchen(plan, 'plan', skip=('source',)) + franzoesisch_suchen(katalog, 'katalog', skip=('snippet', 'key', 'id', 'thumbs', 'cast', 'styles', 'license_id'))
    if funde: fehler('noch Französisch in den deutschen Daten', funde[:12])
    schreiben(de / 'projekte.json', projekte); schreiben(de / 'plan.json', plan); schreiben(de / 'katalog.json', katalog)
    return len(projekte), len(plan), len(katalog)


if __name__ == '__main__':
    n = uebersetzen()
    print('Deutsche Demodaten geschrieben: %d Projekte, %d Planertexte, %d Katalogeinträge.' % n)
