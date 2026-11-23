// Baut die öffentliche, zweisprachige Browser-Demo nach dist/ (Aufruf: node tools/demo-bauen.mjs).
// Die Oberfläche ist die echte: hstudio/web/static/studio.html, studio_extras.js und publication_bridge.js werden gelesen und nur
// in wenigen Punkten angepasst, damit sie als statische Seite unter /HorrorStudio3D/ laufen:
//   1. absolute Adressen (/api/..., /catalogue/..., /studio_extras.js) werden relativ,
//   2. demo/demo-start.js wird vor der Oberfläche geladen und beantwortet die API-Aufrufe aus demo/daten/<sprache> (kein Server nötig),
//   3. ein Hinweisstreifen mit Sprachwahl DE | FR, der Titel, der Katalogstil PS1 und das Format 16:9 (so wurden die Motorbilder gemalt).
// Zwei Sprachen: Deutsch ist der Standard (dist/index.html), Französisch ist die Originalsprache der Oberfläche (dist/fr.html, auch über ?lang=fr).
// Die Quelldateien der Oberfläche bleiben französisch; die deutsche Fassung entsteht hier aus der Tabelle demo/sprache/de.txt (Fragment für Fragment,
// jedes Fragment muss vorkommen) und den deutschen Daten unter demo/daten/de (tools/demo_deutsch.py). Danach prüft der Bau die deutsche Fassung auf
// übrig gebliebenes Französisch. Keine Abhängigkeiten, nur Node 20 oder neuer.
import { readFile, writeFile, mkdir, cp, rm, readdir, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const wurzel = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const statisch = path.join(wurzel, "hstudio/web/static");
const demo = path.join(wurzel, "demo");
const dist = path.join(wurzel, "dist");

const SPRACHEN = {
  de: {
    seite: "index.html", titel: "Horror Studio 3D Demo",
    hinweis: "Öffentliche Demo mit erfundenen Daten. Die Bilder sind echte, vorab gerenderte Ausgaben des Motors; Rendern, Stimme und Veröffentlichung laufen hier nicht.",
    wahl: "Sprache",
  },
  fr: {
    seite: "fr.html", titel: "Horror Studio 3D Demo",
    hinweis: "Démo publique avec des données fictives. Les images sont de vraies sorties du moteur, rendues à l'avance ; le rendu, la voix et la publication ne fonctionnent pas ici.",
    wahl: "Langue",
  },
};

function relativ(text, datei) {
  const neu = text.replaceAll("\r\n", "\n")
    .replace(/(['"`])\/(api|catalogue)\//g, "$1$2/")
    .replace(/src="\/(studio_extras|publication_bridge)\.js"/g, 'src="$1.js"');
  const rest = neu.match(/(['"`(])\/(api|catalogue|studio_extras|publication_bridge)[/.]/g);
  if (rest) throw new Error(`${datei}: absolute Adresse übrig: ${[...new Set(rest)].join(" ")}`);
  return neu;
}
function einfuegen(text, suche, ersatz, name) {
  if (!text.includes(suche)) throw new Error(`Die Oberfläche hat sich geändert: ${name} nicht gefunden.`);
  return text.replace(suche, () => ersatz);
}

/* ---------- Übersetzungstabelle ---------- */
async function tabelleLesen() {
  const zeilen = (await readFile(path.join(demo, "sprache/de.txt"), "utf8")).replaceAll("\r", "").split("\n");
  const paare = [];
  for (const roh of zeilen) {
    const zeile = roh.replace(/\s+$/, "");
    if (!zeile || zeile.startsWith("#")) continue;
    const k = zeile.indexOf(" :::");
    if (k < 0) throw new Error("Tabelle: Trenner ::: fehlt in: " + zeile.slice(0, 60));
    paare.push([zeile.slice(0, k), zeile.slice(k + 4).replace(/^ /, "")]);
  }
  const seen = new Set();
  for (const [fr] of paare) { if (seen.has(fr)) throw new Error("Tabelle: Fragment doppelt: " + fr.slice(0, 60)); seen.add(fr); }
  return paare;
}
const maskiere = s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
function uebersetzer(paare) {
  const karte = new Map(paare), zaehler = new Map(paare.map(([fr]) => [fr, 0]));
  const muster = new RegExp(paare.map(([fr]) => fr).sort((a, b) => b.length - a.length).map(maskiere).join("|"), "g");
  return {
    anwenden: text => text.replace(muster, m => { zaehler.set(m, zaehler.get(m) + 1); return karte.get(m); }),
    ungenutzt: () => [...zaehler].filter(([, n]) => n === 0).map(([fr]) => fr),
    treffer: () => [...zaehler.values()].reduce((a, b) => a + b, 0),
  };
}
// Entfernt die französischen Kommentare der deutschen Fassung: ganze Kommentarzeilen, CSS-Kommentare, den Kopfkommentar von studio_extras.js
function ohneKommentare(text, art) {
  let t = text;
  if (art === "html") t = t.replace(/<style>[\s\S]*?<\/style>/g, s => s.replace(/\/\*[\s\S]*?\*\//g, ""));
  if (art === "js") t = t.replace(/^\/\*[\s\S]*?\*\/\n/, "");
  return t.replace(/^[ \t]*\/\*[^\n]*?\*\/[ \t]*\n/gm, "").replace(/^[ \t]*\/\/[^\n]*\n/gm, "");
}

/* ---------- eine Sprachfassung bauen ---------- */
async function fassung(lang, quelle, tabelle) {
  const L = SPRACHEN[lang];
  let seite = relativ(quelle.studio, "studio.html");
  seite = einfuegen(seite, "<title>Studio vidéo</title>", `<title>${L.titel}</title>\n<link rel="icon" href="favicon.svg" type="image/svg+xml">`, "title");
  seite = einfuegen(seite, "</style>\n</head>", `.demo-hinweis{display:flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:4px 18px;padding:7px 16px;background:var(--brand-soft);color:var(--ink-2);border-bottom:1px solid var(--line);font-size:12.5px;line-height:1.4;text-align:center}
.demo-sprache{display:inline-flex;align-items:center;gap:7px;font-weight:700;letter-spacing:.03em}
.demo-sprache a{color:var(--ink-2);text-decoration:none;padding:2px 5px;border-radius:6px}
.demo-sprache a:hover{color:var(--brand);text-decoration:underline;text-underline-offset:3px}
.demo-sprache a[aria-current]{color:var(--brand);background:var(--card);box-shadow:inset 0 0 0 1px var(--line)}
body{display:flex;flex-direction:column}
.app{flex:1 1 0;min-height:0;height:auto}
.drawer{top:var(--hinweis-h,0px)}
</style>
</head>`, "style");
  seite = einfuegen(seite, "<body>\n<div class=\"app\">", `<body>\n@@HINWEIS@@\n<div class="app">`, "body");
  seite = einfuegen(seite, "<script>\nconst $=", `@@WEICHE@@<script src="demo-start.js"></script>\n<script>\nconst $=`, "Hauptskript");
  // Kennungen, die die Beispielprojekte benutzen, die Oberfläche aber nicht beschriftet (sonst stünde die rohe Kennung auf der Plankarte)
  seite = einfuegen(seite, "['follow','Suit le personnage']]", "['follow','Suit le personnage'],['handheld','Caméra à l\\'épaule'],['drift','Dérive lente']]", "MOVES");
  seite = einfuegen(seite, "['insert','Détail (insert)']]", "['insert','Détail (insert)'],['medium_full','Plan américain']]", "CAM_SIZES");
  const NACH_STUDIO = `</script>
<script>
// Demo: Katalogminiaturen im Stil PS1, Motorbilder im Format 16:9, Plan-Schublade unter dem Hinweisstreifen
S.lastStyle = 'ps1'; S.aspect = '16:9';
const hinweis = document.querySelector('.demo-hinweis'), hoehe = () => document.documentElement.style.setProperty('--hinweis-h', hinweis.offsetHeight + 'px');
hoehe(); addEventListener('resize', hoehe);
</script>
<script src="studio_extras.${lang}.js"></script>`;
  seite = einfuegen(seite, '</script>\n<script src="studio_extras.js"></script>', NACH_STUDIO, "studio_extras");
  seite = einfuegen(seite, '<script src="publication_bridge.js"></script>', `<script src="publication_bridge.${lang}.js"></script>`, "publication_bridge");
  let extras = relativ(quelle.extras, "studio_extras.js"), bruecke = relativ(quelle.bruecke, "publication_bridge.js");
  let bericht = null;
  if (lang === "de") {
    const u = uebersetzer(tabelle);
    seite = u.anwenden(ohneKommentare(seite, "html")); extras = u.anwenden(ohneKommentare(extras, "js")); bruecke = u.anwenden(bruecke);
    const fehlend = u.ungenutzt();
    if (fehlend.length) throw new Error("Übersetzungstabelle: Fragmente nicht gefunden (Oberfläche geändert?):\n  " + fehlend.join("\n  "));
    bericht = u.treffer();
  }
  const aktuell = a => ` hreflang="${a}" lang="${a}"${a === lang ? ' aria-current="true"' : ""}`;
  const hinweis = `<div class="demo-hinweis" lang="${lang}" role="note"><span>${L.hinweis}</span><nav class="demo-sprache" aria-label="${L.wahl}"><a href="./"${aktuell("de")}>DE</a><span aria-hidden="true">|</span><a href="fr.html"${aktuell("fr")}>FR</a></nav></div>`;
  // ?lang=fr bzw. ?lang=de wählt die andere Fassung, bevor die Seite lädt
  const weiche = lang === "de"
    ? `<script>if(/[?&]lang=fr(&|$)/.test(location.search))location.replace('fr.html'+location.search+location.hash)</script>\n`
    : `<script>if(/[?&]lang=de(&|$)/.test(location.search))location.replace(location.pathname.replace(/[^/]*$/,'')+location.hash)</script>\n`;
  seite = seite.replace("@@HINWEIS@@", () => hinweis).replace("@@WEICHE@@", () => weiche)
    .replace(/<html lang="fr">/, `<html lang="${lang}">`);
  if (!seite.includes(`<html lang="${lang}">`)) throw new Error("html lang nicht gesetzt");
  return { seite, extras, bruecke, bericht };
}

await rm(dist, { recursive: true, force: true });
await mkdir(dist, { recursive: true });

const quelle = {
  studio: await readFile(path.join(statisch, "studio.html"), "utf8"),
  extras: await readFile(path.join(statisch, "studio_extras.js"), "utf8"),
  bruecke: await readFile(path.join(statisch, "publication_bridge.js"), "utf8"),
};
const tabelle = await tabelleLesen();
let treffer = 0;
for (const lang of Object.keys(SPRACHEN)) {
  const f = await fassung(lang, quelle, tabelle);
  await writeFile(path.join(dist, SPRACHEN[lang].seite), f.seite);
  await writeFile(path.join(dist, `studio_extras.${lang}.js`), f.extras);
  await writeFile(path.join(dist, `publication_bridge.${lang}.js`), f.bruecke);
  if (f.bericht != null) treffer = f.bericht;
}

await cp(path.join(demo, "demo-start.js"), path.join(dist, "demo-start.js"));
await cp(path.join(demo, "favicon.svg"), path.join(dist, "favicon.svg"));
await cp(path.join(demo, "daten"), path.join(dist, "daten"), { recursive: true });
await cp(path.join(demo, "katalog"), path.join(dist, "catalogue"), { recursive: true });
// Vorschaubilder liegen dort, wo die Oberfläche sie anfordert: api/projects/<projekt>/file/preview/shot_00N.jpg (je Sprache mit eigener Projektkennung)
for (const lang of Object.keys(SPRACHEN)) {
  const projekte = JSON.parse(await readFile(path.join(demo, "daten", lang, "projekte.json"), "utf8"));
  for (const p of projekte) {
    const ordner = path.join(demo, "vorschau", p.vorschau_ordner || p.slug);
    if (!p.previews.some(Boolean)) continue;
    await cp(ordner, path.join(dist, "api/projects", p.slug, "file/preview"), { recursive: true });
  }
}
await writeFile(path.join(dist, ".nojekyll"), "");

let dateien = 0, bytes = 0;
async function zaehlen(ordner) {
  for (const e of await readdir(ordner, { withFileTypes: true })) {
    const p = path.join(ordner, e.name);
    if (e.isDirectory()) await zaehlen(p); else { dateien++; bytes += (await stat(p)).size; }
  }
}
await zaehlen(dist);
console.log(`Demo gebaut: dist/ mit ${dateien} Dateien, ${(bytes / 1048576).toFixed(1)} MB; ${tabelle.length} Fragmente der Übersetzungstabelle, ${treffer} Ersetzungen in der deutschen Fassung.`);
