// Baut die öffentliche Browser-Demo nach dist/ (Aufruf: node tools/demo-bauen.mjs).
// Die Oberfläche ist die echte: hstudio/web/static/studio.html, studio_extras.js und publication_bridge.js werden gelesen und nur
// in drei Punkten angepasst, damit sie als statische Seite unter /HorrorStudio3D/ laufen:
//   1. absolute Adressen (/api/..., /catalogue/..., /studio_extras.js) werden relativ,
//   2. demo/demo-start.js wird vor der Oberfläche geladen und beantwortet die API-Aufrufe aus demo/daten (kein Server nötig),
//   3. ein Hinweisstreifen, der Titel, der Katalogstil PS1 und das Format 16:9 (so wurden die Motorbilder gemalt).
// Keine Abhängigkeiten, nur Node 20 oder neuer.
import { readFile, writeFile, mkdir, cp, rm, readdir, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const wurzel = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const statisch = path.join(wurzel, "hstudio/web/static");
const demo = path.join(wurzel, "demo");
const dist = path.join(wurzel, "dist");

const HINWEIS = "Öffentliche Demo mit erfundenen Daten. Die Bilder sind echte, vorab gerenderte Ausgaben des Motors; Rendern, Stimme und Veröffentlichung laufen hier nicht.";

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

await rm(dist, { recursive: true, force: true });
await mkdir(dist, { recursive: true });

let seite = relativ(await readFile(path.join(statisch, "studio.html"), "utf8"), "studio.html");
seite = einfuegen(seite, "<title>Studio vidéo</title>", '<title>Horror Studio 3D Demo</title>\n<link rel="icon" href="favicon.svg" type="image/svg+xml">', "title");
seite = einfuegen(seite, "</style>\n</head>", `.demo-hinweis{padding:7px 16px;background:var(--brand-soft);color:var(--ink-2);border-bottom:1px solid var(--line);font-size:12.5px;line-height:1.4;text-align:center}
body{display:flex;flex-direction:column}
.app{flex:1 1 0;min-height:0;height:auto}
.drawer{top:var(--hinweis-h,0px)}
</style>
</head>`, "style");
seite = einfuegen(seite, "<body>\n<div class=\"app\">", `<body>\n<div class="demo-hinweis" lang="de" role="note">${HINWEIS}</div>\n<div class="app">`, "body");
seite = einfuegen(seite, "<script>\nconst $=", '<script src="demo-start.js"></script>\n<script>\nconst $=', "Hauptskript");
const NACH_STUDIO = `</script>
<script>
// Demo: Katalogminiaturen im Stil PS1, Motorbilder im Format 16:9, Plan-Schublade unter dem Hinweisstreifen
S.lastStyle = 'ps1'; S.aspect = '16:9';
const hinweis = document.querySelector('.demo-hinweis'), hoehe = () => document.documentElement.style.setProperty('--hinweis-h', hinweis.offsetHeight + 'px');
hoehe(); addEventListener('resize', hoehe);
</script>
<script src="studio_extras.js"></script>`;
seite = einfuegen(seite, '</script>\n<script src="studio_extras.js"></script>', NACH_STUDIO, "studio_extras");
await writeFile(path.join(dist, "index.html"), seite);
for (const name of ["studio_extras.js", "publication_bridge.js"]) {
  await writeFile(path.join(dist, name), relativ(await readFile(path.join(statisch, name), "utf8"), name));
}

await cp(path.join(demo, "demo-start.js"), path.join(dist, "demo-start.js"));
await cp(path.join(demo, "favicon.svg"), path.join(dist, "favicon.svg"));
await cp(path.join(demo, "daten"), path.join(dist, "daten"), { recursive: true });
await cp(path.join(demo, "katalog"), path.join(dist, "catalogue"), { recursive: true });
// Vorschaubilder liegen dort, wo die Oberfläche sie anfordert: api/projects/<projekt>/file/preview/shot_00N.jpg
for (const projekt of await readdir(path.join(demo, "vorschau"))) {
  await cp(path.join(demo, "vorschau", projekt), path.join(dist, "api/projects", projekt, "file/preview"), { recursive: true });
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
console.log(`Demo gebaut: dist/ mit ${dateien} Dateien, ${(bytes / 1048576).toFixed(1)} MB.`);
