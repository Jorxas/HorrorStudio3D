// Browserprüfung der gebauten Demo (vorher: node tools/demo-bauen.mjs). Benötigt puppeteer-core (npm install --no-save puppeteer-core)
// und einen installierten Chrome oder Edge (sonst BROWSER_PFAD setzen). dist/ wird wie auf GitHub Pages unter /HorrorStudio3D/ ausgeliefert.
// Geprüft wird die echte Oberfläche mit ihren Beispielprojekten: keine Laufzeitfehler, keine fehlgeschlagenen oder externen Anfragen,
// kein horizontaler Überlauf bei 390 Pixel Breite. Optional: --bild=<datei.png> schreibt die Aufnahme der Oberfläche (README).
const fs = require("node:fs"), path = require("node:path"), http = require("node:http"), assert = require("node:assert/strict");
const puppeteer = require("puppeteer-core");
const dist = path.resolve(__dirname, "../dist");
const bildArgument = process.argv.find(a => a.startsWith("--bild="))?.slice(7);
const typen = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".json": "application/json", ".jpg": "image/jpeg", ".png": "image/png", ".svg": "image/svg+xml" };
const server = http.createServer((anfrage, antwort) => {
  let pfad = decodeURIComponent(new URL(anfrage.url, "http://x").pathname);
  if (!pfad.startsWith("/HorrorStudio3D/")) { antwort.statusCode = 404; return antwort.end("nicht gefunden"); }
  pfad = pfad.replace(/^\/HorrorStudio3D/, "") || "/";
  if (pfad.endsWith("/")) pfad += "index.html";
  const datei = path.join(dist, pfad);
  if (!datei.startsWith(dist) || !fs.existsSync(datei) || fs.statSync(datei).isDirectory()) { antwort.statusCode = 404; return antwort.end("nicht gefunden"); }
  antwort.setHeader("Content-Type", typen[path.extname(datei)] || "application/octet-stream");
  antwort.end(fs.readFileSync(datei));
});
const browserPfad = process.env.BROWSER_PFAD || ["C:/Program Files/Google/Chrome/Application/chrome.exe", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", "C:/Program Files/Microsoft/Edge/Application/msedge.exe", "/usr/bin/google-chrome", "/usr/bin/chromium"].find(f => fs.existsSync(f));
if (!browserPfad) throw new Error("BROWSER_PFAD auf einen installierten Chrome oder Edge setzen.");
// Die Oberfläche animiert ihre Karten und scrollt weich; ein Mausklick auf bewegte Elemente trifft sonst daneben. Deshalb: warten, dann DOM-Klick.
const klick = async (seite, sel) => { await seite.waitForSelector(sel, { visible: true }); await seite.$eval(sel, e => e.click()); };
const warte = ms => new Promise(r => setTimeout(r, ms));
const text = (seite, sel) => seite.$eval(sel, e => e.textContent);
const anzahl = (seite, sel) => seite.$$eval(sel, e => e.length);
const toast = (seite, teil) => seite.waitForFunction(t => [...document.querySelectorAll(".toast")].some(e => e.textContent.includes(t)), { timeout: 5000 }, teil);
const ueberlauf = seite => seite.evaluate(() => ({ dokument: document.documentElement.scrollWidth - innerWidth, haupt: (() => { const m = document.querySelector("main"); return m ? m.scrollWidth - m.clientWidth : 0; })() }));

(async () => {
  await new Promise(r => server.listen(0, "127.0.0.1", r));
  const basis = `http://127.0.0.1:${server.address().port}/HorrorStudio3D/`;
  const browser = await puppeteer.launch({ executablePath: browserPfad, headless: true });
  const fehler = [], extern = [], schlecht = [];
  try {
    const seite = await browser.newPage();
    seite.on("pageerror", e => fehler.push("Seitenfehler: " + e.message));
    seite.on("console", m => { if (m.type() === "error") fehler.push("Konsole: " + m.text()); });
    seite.on("request", r => { if (new URL(r.url()).hostname !== "127.0.0.1") extern.push(r.url()); });
    seite.on("response", r => { if (r.status() >= 400) schlecht.push(r.status() + " " + r.url()); });
    seite.on("requestfailed", r => schlecht.push("fehlgeschlagen " + r.url()));
    seite.on("dialog", d => d.accept());
    await seite.setViewport({ width: 1440, height: 900 });
    await seite.goto(basis, { waitUntil: "networkidle0" });
    await seite.waitForSelector(".plan");

    // Rahmen: Titel, Hinweis, vier Projekte, erstes Projekt geöffnet
    assert.equal(await seite.title(), "Horror Studio 3D Demo");
    assert((await text(seite, ".demo-hinweis")).includes("erfundenen Daten"), "Hinweis sichtbar");
    assert.equal(await anzahl(seite, ".item"), 4, "vier Projekte in der Liste");
    assert.equal(await text(seite, "h1"), "Nuit d'orage");
    assert.equal(await anzahl(seite, ".plan"), 6, "sechs Pläne");
    assert.equal(await anzahl(seite, ".shot.skeleton"), 2, "zwei Pläne ohne Motorbild bleiben leer");
    assert((await seite.$$eval(".shot:not(.skeleton)", e => e.map(x => getComputedStyle(x).backgroundImage))).every(b => b.includes("shot_00")), "Motorbilder als Plankarten");
    assert((await seite.$$eval(".thumb", e => e.map(x => x.style.backgroundImage))).filter(Boolean).length >= 2, "Miniaturen in der Liste");

    // Plan korrigieren: Auswahllisten kommen aus dem echten Motor, Vorschau braucht ihn und sagt das
    await klick(seite, '.plan[data-i="2"]');
    await seite.waitForSelector("#pvGo");
    await warte(900);
    if (bildArgument) await seite.screenshot({ path: path.resolve(bildArgument) });
    assert((await seite.$$eval("#fSize option", o => o.length)) === 10, "zehn Einstellungsgrößen im Stil PS1");
    assert.equal(await seite.$eval("#fSize", e => e.value), "close");
    await seite.select("#fSize", "extreme_close");
    await klick(seite, "#pvGo");
    await toast(seite, "Studiomotor");
    assert((await text(seite, "#pvState")).includes("läuft hier nicht"), "ehrlicher Hinweis statt erfundener Vorschau");
    await klick(seite, "#pvSkip");
    await toast(seite, "Plan enregistré");
    await seite.waitForSelector("#drawer.open");
    assert((await text(seite, '.plan[data-i="2"]')).includes("Très gros plan"), "gespeicherte Einstellung ist im Plan sichtbar");
    await seite.keyboard.press("Escape");

    // Reiter, Aktionen, die den Motor bräuchten
    await klick(seite, '.tab[data-tab="script"]');
    assert((await seite.$eval("#scr", e => e.value)).includes("Maman ?"), "Skript des Szenarios");
    await klick(seite, '.tab[data-tab="caps"]');
    assert((await text(seite, "#content")).includes("Tout est disponible"), "Fähigkeitsbericht");
    await klick(seite, '.tab[data-tab="plans"]');
    await klick(seite, '[data-run="preview"]');
    await toast(seite, "Studiomotor");
    await klick(seite, "#makeBtn");
    await toast(seite, "voix");
    await klick(seite, '.seg button[data-style="voxel"]');
    await toast(seite, "vorab im ursprünglichen Stil");

    // Anderes Projekt: Console 2D mit Bildern zu vier von neun Plänen
    await seite.evaluate(() => [...document.querySelectorAll(".item")].find(b => b.textContent.includes("niveau 7")).click());
    await seite.waitForFunction(() => document.querySelector("h1")?.textContent.includes("niveau 7"));
    assert.equal(await anzahl(seite, ".plan"), 9, "neun Pläne");
    assert.equal(await anzahl(seite, ".shot.skeleton"), 5);
    await klick(seite, '.plan[data-i="1"]');
    await seite.waitForSelector("#pvGo");
    assert.equal(await anzahl(seite, "#fSize option"), 3, "Console 2D kennt drei Größen");
    await seite.keyboard.press("Escape");

    // Entwurf ohne Pläne: Fähigkeiten dort analysieren (echte, vorab berechnete Planerausgabe)
    await seite.evaluate(() => [...document.querySelectorAll(".item")].find(b => b.textContent.includes("ville sous")).click());
    await seite.waitForFunction(() => document.querySelector("h1")?.textContent.includes("ville sous"));
    assert((await text(seite, "#content")).includes("Les plans arrivent ici"));
    await klick(seite, '.tab[data-tab="caps"]');
    await klick(seite, "#capTool");
    await seite.waitForSelector("#pForm");
    await klick(seite, "#pGo");
    await seite.waitForSelector(".need.missing");
    assert((await anzahl(seite, ".need")) >= 3, "Bedarfskarten");
    assert((await text(seite, "#pOut")).includes("Demande d'extension"), "Erweiterungsanfragen des Planers");

    // Szene analysieren: Beispieltext, anderer Motor, freier Text (nicht vorbereitet)
    const beispiele = await seite.$$eval("[data-ex]", b => b.length);
    assert.equal(beispiele, 2);
    await klick(seite, '[data-ex="1"]');
    await klick(seite, "#pGo");
    await seite.waitForFunction(() => document.querySelector("#pOut")?.textContent.includes("requin"));
    await klick(seite, 'input[name=pEng][value=console]');
    await seite.waitForFunction(() => !document.querySelector("#pGo").disabled && document.querySelector("#pSum"));
    await seite.$eval("#pText", (e, t) => { e.value = t; e.dispatchEvent(new Event("input")); }, "Ein Drache über dem Dach.");
    await klick(seite, "#pGo");
    await seite.waitForSelector('#pOut [role="alert"]');
    assert((await text(seite, "#pOut")).includes("läuft hier nicht"), "freier Text: ehrlicher Hinweis");

    // Katalog mit gemalten Miniaturen
    await klick(seite, "#catBtn");
    await seite.waitForSelector(".catcard");
    assert((await anzahl(seite, ".catcard")) > 50, "Katalogkarten");
    await seite.waitForFunction(() => [...document.querySelectorAll(".catcard img")].slice(0, 12).every(i => i.complete && i.naturalWidth > 0));
    await klick(seite, '.cchip[data-cc="Lieux"]');
    assert((await anzahl(seite, ".catcard")) > 20, "Kategorie Lieux");
    await klick(seite, ".catcard");
    await seite.waitForSelector(".cdet");
    await klick(seite, "#eClose");
    await klick(seite, '[data-cs="console"]');
    assert((await anzahl(seite, ".catcard")) > 20, "Console 2D Katalog");
    await klick(seite, '[data-cs="voxel"]');
    assert((await text(seite, "#cgrid")).includes("en préparation"), "VOXEL: Miniaturen fehlen, das sagt die Oberfläche selbst");

    // Clip musical, neues Projekt, Speicherverwaltung
    await klick(seite, "#clipBtn");
    await seite.waitForSelector("#cGo");
    assert((await text(seite, "#main")).includes("Aucun clip"));
    await klick(seite, "#newBtn");
    await seite.type("#nName", "Test im Browser");
    await klick(seite, "#nGo");
    await seite.waitForFunction(() => document.querySelector("h1")?.textContent === "Test im Browser");
    assert.equal(await anzahl(seite, ".item"), 5);
    await klick(seite, "#spaceBtn");
    await seite.waitForSelector(".spacelist");
    assert((await anzahl(seite, ".spacelist li")) === 5);
    await seite.keyboard.press("Escape");

    // Handy: kein horizontaler Überlauf
    await seite.setViewport({ width: 390, height: 844, deviceScaleFactor: 2 });
    for (const [name, aktion] of [
      ["Projektansicht", async () => { await klick(seite, "#menuBtn"); await seite.evaluate(() => [...document.querySelectorAll(".item")].find(b => b.textContent.includes("Nuit")).click()); await seite.waitForFunction(() => document.querySelectorAll(".plan").length === 6); }],
      ["Plan-Schublade", async () => { await klick(seite, '.plan[data-i="0"]'); await seite.waitForSelector("#pvGo"); }],
      ["Szene analysieren", async () => { await seite.keyboard.press("Escape"); await klick(seite, "#menuBtn"); await klick(seite, "#planBtn"); await klick(seite, '[data-ex="0"]'); await klick(seite, "#pGo"); await seite.waitForSelector(".need"); }],
      ["Katalog", async () => { await klick(seite, "#menuBtn"); await klick(seite, "#catBtn"); await seite.waitForSelector(".catcard"); }],
      ["Clip musical", async () => { await klick(seite, "#menuBtn"); await klick(seite, "#clipBtn"); await seite.waitForSelector("#cGo"); }],
    ]) {
      await aktion(); await warte(400);
      const u = await ueberlauf(seite);
      assert(u.dokument <= 0 && u.haupt <= 0, `kein horizontaler Überlauf bei 390 Pixel (${name}): ${JSON.stringify(u)}`);
    }
  } finally { await browser.close(); server.close(); }
  assert.deepEqual(fehler, [], "keine Laufzeitfehler");
  assert.deepEqual(extern, [], "keine externen Anfragen");
  assert.deepEqual(schlecht, [], "keine fehlgeschlagenen Anfragen");
  console.log("Browserprüfung der Demo bestanden: echte Oberfläche mit vier Projekten, Planschublade, Szenenanalyse, Katalog, Clip, Speicher, Handy 390 Pixel; keine Fehler, keine externen oder fehlgeschlagenen Anfragen.");
})().catch(e => { console.error(e); process.exitCode = 1; server.close(); });
