"""Erzeugt die Daten der öffentlichen Browser-Demo aus dem echten Python-Motor (einmalig, Ergebnisse werden eingecheckt).

Die Demo zeigt die echte Oberfläche (hstudio/web/static/studio.html). Ihre Serverantworten kommen aus den Dateien, die dieses Skript schreibt:

  demo/daten/projekte.json   drei Projekte aus echten Szenarien (examples/demos) mit Zeilen, Plänen, Fähigkeitsbericht, Reglerlisten und
                             den echten Stand der Bildzuordnung, dazu ein erfundener Entwurf ohne Pläne
  demo/daten/plan.json       echte Ausgaben des Szenenplaners (hstudio.capabilities.planner) für die vorbereiteten Texte
  demo/daten/katalog.json    Katalogeinträge, für die der Motor eine Miniatur gemalt hat
  demo/vorschau/<projekt>/   die zwölf Motorbilder aus demo/bilder als JPEG (Name wie im echten Studio: shot_00N.jpg)
  demo/katalog/thumbs_*/     vom Motor gemalte Katalogminiaturen (PS1 per CPU-Raytracing, Console 2D)

Nichts davon wird im Browser berechnet. Aufruf: python tools/demo_export.py [--miniaturen ORDNER]
(ORDNER enthält bereits gemalte Miniaturen thumbs_ps1/; sonst werden sie in einem temporären Ordner neu gemalt, etwa zwei Minuten.)"""
import argparse, json, os, re, shutil, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('PYTHONUTF8', '1')

DEMO = ROOT / 'demo'
BILDER = DEMO / 'bilder'
DATEN = DEMO / 'daten'
VORSCHAU = DEMO / 'vorschau'
KATALOG = DEMO / 'katalog'

# Welche echten Szenarien als Projekt erscheinen. Namen und Texte der Projekte sind erfunden; Skript, Pläne und Zeiten stammen aus dem Szenario.
PROJEKTE = [
    dict(slug='nuit_d_orage', demo='demo4_tension', name="Nuit d'orage", teil='DÉMO 4'),
    dict(slug='la_cle_inconnue', demo='demo1_mouvement', name='La clé inconnue', teil='DÉMO 1'),
    dict(slug='ne_mets_pas_pause', demo='demo5_console', name='Ne mets pas pause : niveau 7', teil='NIVEAU 7'),
]
ENTWURF = dict(slug='la_ville_sous_leau', name="La ville sous l'eau", teil='ENTWURF',
               script="Un requin géant nage dans une ville sous-marine.\nLéa saute au-dessus du ravin, puis grimpe sur la corniche.\nUn hélicoptère rouge arrive sous l'orage.")
# Die zwei Beispieltexte der Oberfläche (studio.html, EXAMPLES); der Test der Demo prüft, dass sie dort noch stehen.
BEISPIELE = ["Léa saute au-dessus du ravin, puis grimpe sur la corniche. Un hélicoptère rouge arrive sous l'orage.", 'Un requin géant nage dans une ville sous-marine.']
KATALOG_PRAEFIXE = ('decor', 'lieu', 'visage', 'monstre', 'perso', 'console')


def lesen(p): return json.loads(Path(p).read_text(encoding='utf-8'))


def schreiben(p, daten):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(daten, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def stil_von(meta):
    from hstudio import shot_preview as SP
    return SP.style_of(meta, {})


def caps_lesen(cap):
    """wie hstudio/web/server.py _read_caps: Lücken der Prüfung bekommen ihre Erweiterungsanfrage"""
    from hstudio.capabilities import planner
    au = cap.get('audit') or {}; style = au.get('style') or 'pixel3d'
    have = {q.get('id') for q in ((cap.get('plan') or {}).get('requests') or []) + ((au.get('requires') or {}).get('requests') or [])}
    extra = []
    for g in au.get('gaps') or []:
        rid = f"{g['kind']}_{g['name']}"
        if rid in have: continue
        have.add(rid)
        q = planner.request({'kind': g['kind'], 'name': g['name'], 'terms': [g.get('where', '')]}, style, f"{g.get('where', '')} : {g.get('consequence', '')}")
        extra.append(dict(q, need='manquant'))
    if extra: cap['gap_requests'] = extra
    return cap


def bild_zuordnung(zeilen, plaene, protokoll, szene):
    """Welcher Plan war zu den vier festgehaltenen Zeitpunkten im Bild? -> {Plannummer: Dateiname des Motorbilds}"""
    fenster = []
    for i, sh in enumerate(plaene):
        a, b = sh['lines']; fenster.append((i, zeilen[a]['start'], zeilen[b]['end']))
    ergebnis = {}
    for eintrag in [p for p in protokoll if p['szene'] == szene]:
        t = eintrag['sekunden']
        drin = [i for i, a, b in fenster if a <= t <= b]
        i = drin[0] if drin else min(fenster, key=lambda f: min(abs(t - f[1]), abs(t - f[2])))[0]
        assert i not in ergebnis, f'zwei Bilder für Plan {i} in {szene}'
        ergebnis[i] = eintrag
    return ergebnis


def vorschau_bilder(slug, zuordnung, n_plaene):
    from PIL import Image
    ziel = VORSCHAU / slug
    if ziel.exists(): shutil.rmtree(ziel)
    ziel.mkdir(parents=True)
    namen = []
    for i in range(n_plaene):
        e = zuordnung.get(i)
        if not e: namen.append(''); continue
        name = f'shot_{i:03d}.jpg'
        Image.open(BILDER / e['datei']).convert('RGB').save(ziel / name, quality=88, optimize=True)
        namen.append(name)
    return namen


def projekt_aus_szenario(p, protokoll, start):
    from hstudio import demos, shot_preview as SP
    from hstudio.capabilities.audit import report_project
    sc = demos.load(p['demo']); stil = sc.get('style', 'pixel3d')
    zeilen = demos.timed_lines(sc['script'], float(sc.get('gap', .3)), float(sc.get('lead', .4)))
    text = sc.get('description', '') + '\n' + '\n'.join(s.get('text', '') for s in sc['script'])
    protokol = []
    ep = demos.episode_of(sc, zeilen, log=protokol.append)
    cap = caps_lesen(report_project(sc['episode'], stil, text, protokol.append))
    meta = dict(name=p['name'], style=stil, render_engine='pixel3d', series=None, part_label=p['teil'], created=start, notes='Szenario ' + p['demo'], director='')
    zuordnung = bild_zuordnung(zeilen, ep['shots'], protokoll, p['demo'])
    vorschau = vorschau_bilder(p['slug'], zuordnung, len(ep['shots']))
    optionen = []
    for i in range(len(ep['shots'])):
        o = SP.options(stil_von(meta), ep, i); o['current'] = SP.current(ep, i, stil_von(meta)); optionen.append(o)
    script = '\n'.join(s.get('text', '') for s in sc['script'])
    groesse_vorschau = sum((VORSCHAU / p['slug'] / n).stat().st_size for n in vorschau if n)
    ep_text = json.dumps(ep, ensure_ascii=False)
    gesamt = groesse_vorschau + len(script.encode()) + len(ep_text.encode()) + len(json.dumps(zeilen, ensure_ascii=False).encode()) + len(json.dumps(cap, ensure_ascii=False).encode())
    return dict(slug=p['slug'], meta=meta, szenario=p['demo'], script=script, episode=ep_text, lines=zeilen, warnings=[], capabilities=cap, previews=vorschau,
                status=dict(script=True, voice=False, lines=True, episode=True, mix=False, thumbnail=False, metadata=False, renders=[]),
                optionen=optionen, groesse=dict(total=gesamt, generated=groesse_vorschau),
                bilder=[dict(plan=i, datei=e['datei'], sekunden=e['sekunden'], motor=e['motor']) for i, e in sorted(zuordnung.items())])


def entwurf(start):
    meta = dict(name=ENTWURF['name'], style='pixel3d', render_engine='pixel3d', series=None, part_label=ENTWURF['teil'], created=start, notes='erfundener Entwurf ohne Pläne', director='')
    return dict(slug=ENTWURF['slug'], meta=meta, szenario=None, script=ENTWURF['script'], episode='', lines=[], warnings=[], capabilities=None, previews=[],
                status=dict(script=True, voice=False, lines=False, episode=False, mix=False, thumbnail=False, metadata=False, renders=[]),
                optionen=[], groesse=dict(total=len(ENTWURF['script'].encode()), generated=0), bilder=[])


def planer_ausgabe(text, engine):
    """wie hstudio/web/server.py plan_scene (ohne die Anfrage zum Schreiben der Erweiterungsanfragen)"""
    from hstudio.capabilities import planner, extensions
    rep = planner.plan(text[:20000], engine=engine)
    rep['extensions'] = [{'id': m['id'], 'title': m.get('title', ''), 'status': m.get('status'), 'loaded': m['id'] in extensions.LOADED, 'problem': extensions.PROBLEMS.get(m['id'])} for m in extensions.manifests()]
    return rep


def katalog_bauen(cache):
    """Katalogeinträge mit gemalter Miniatur. PS1: hstudio.catalogue_ps1 (CPU), Console 2D: hstudio.catalogue_console. VOXEL (GPU) wird nicht gemalt."""
    from PIL import Image
    from hstudio import catalogue as C, catalogue_ps1 as P1, catalogue_console as CC, styles
    P1.OUT = cache; CC.OUT = cache
    eintraege = [e for e in C.entries() if str(e['id']).split('/', 1)[0] in KATALOG_PRAEFIXE]
    P1.build(eintraege, only={'decor', 'lieu', 'visage', 'monstre', 'perso'}, log=print)
    CC.build([e for e in eintraege if e['id'].startswith('console/')], log=print)
    if KATALOG.exists(): shutil.rmtree(KATALOG)
    ergebnis = []
    for e in eintraege:
        i = str(e['id'])
        e = dict(e); e.pop('thumb', None)
        if i.startswith('console/'):
            e['styles'] = {'console': 'native'}; rel = CC.thumb_rel(i); schluessel = 'console'
        else:
            e['styles'] = styles.of_entry(e); rel = P1.thumb_rel(i); schluessel = 'ps1'
        quelle = cache / rel
        if not quelle.exists(): continue
        ziel = KATALOG / rel; ziel.parent.mkdir(parents=True, exist_ok=True)
        Image.open(quelle).convert('RGB').save(ziel, quality=70, optimize=True)
        e['thumbs'] = {schluessel: rel}
        ergebnis.append(e)
    return ergebnis


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--miniaturen', help='Ordner mit bereits gemalten Miniaturen (thumbs_ps1/, thumbs_console/)')
    a = ap.parse_args()
    protokoll = lesen(BILDER / 'herkunft.json')
    start = 1792000000
    projekte = [projekt_aus_szenario(p, protokoll, start - 86400 * k) for k, p in enumerate(PROJEKTE)] + [entwurf(start - 86400 * 9)]
    schreiben(DATEN / 'projekte.json', projekte)
    texte = BEISPIELE + [p['script'] for p in projekte]
    plan = {}
    for t in texte:
        plan[t.strip()] = {eng: planer_ausgabe(t.strip(), eng) for eng in ('pixel3d', 'console')}
    schreiben(DATEN / 'plan.json', plan)
    cache = Path(a.miniaturen) if a.miniaturen else Path(tempfile.mkdtemp(prefix='hs_katalog_'))
    katalog = katalog_bauen(cache)
    schreiben(DATEN / 'katalog.json', katalog)
    n_bild = sum(1 for p in projekte for n in p['previews'] if n)
    print(f'{len(projekte)} Projekte, {n_bild} Vorschaubilder, {len(plan)} Planertexte, {len(katalog)} Katalogeinträge mit Miniatur.')


if __name__ == '__main__':
    main()
