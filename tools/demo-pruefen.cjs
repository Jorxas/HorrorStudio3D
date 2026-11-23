// Browserprüfung der gebauten, zweisprachigen Demo (vorher: node tools/demo-bauen.mjs). Benötigt puppeteer-core (npm install --no-save puppeteer-core)
// und einen installierten Chrome oder Edge (sonst BROWSER_PFAD setzen). dist/ wird wie auf GitHub Pages unter /HorrorStudio3D/ ausgeliefert.
// Geprüft wird die echte Oberfläche mit ihren Beispielprojekten in beiden Sprachen: Deutsch beim Laden, Wechsel zu Französisch über den Schalter
// DE | FR und über ?lang=fr, Rückkehr zu Deutsch; jeweils bei 1440 und 390 Pixeln Breite, ohne Laufzeitfehler, ohne fehlgeschlagene oder externe
// Anfragen, ohne horizontalen Überlauf. In der deutschen Fassung wird außerdem an jeder Ansicht der sichtbare Text samt aria-label, title, placeholder
// und alt auf übrig gebliebenes Französisch durchsucht. Optional: --bild=<datei.png> schreibt die Aufnahme der deutschen Oberfläche (README).
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

// Erwartete Texte je Sprache
const SPRACHEN = {
  de: {
    seite: "", titel: "Horror Studio 3D Demo", hinweis: "erfundenen Daten", h1: "Gewitternacht", p3: "Level 7", p4: "Stadt unter", p1: "Gewitter",
    skript: "Mama?", motorToast: "Studiomotor", motorHinweis: "läuft hier nicht", gespeichert: "Einstellung gespeichert", detail: "Extreme Großaufnahme",
    alles: "Alles verfügbar", stimme: "Stimme", stilwechsel: "vorab im ursprünglichen Stil", leer: "Hier erscheinen die Einstellungen",
    anfrage: "Erweiterungsanfrage", beispiel: "Hai", frei: "Ein Drache über dem Dach.", kategorie: "Orte", vorbereitung: "in Vorbereitung",
    clip: "Noch kein Musikvideo", neu: "Test im Browser", sprache: "DE",
  },
  fr: {
    seite: "fr.html", titel: "Horror Studio 3D Demo", hinweis: "données fictives", h1: "Nuit d'orage", p3: "niveau 7", p4: "ville sous", p1: "Nuit",
    skript: "Maman ?", motorToast: "moteur du studio", motorHinweis: "ne tourne pas ici", gespeichert: "Plan enregistré", detail: "Très gros plan",
    alles: "Tout est disponible", stimme: "voix", stilwechsel: "style d'origine", leer: "Les plans arrivent ici",
    anfrage: "Demande d'extension", beispiel: "requin", frei: "Un dragon sur le toit.", kategorie: "Lieux", vorbereitung: "en préparation",
    clip: "Aucun clip", neu: "Test dans le navigateur", sprache: "FR",
  },
};

// Sucht in der deutschen Fassung nach Französisch: sichtbarer Text und die Attribute aria-label, title, placeholder, alt
const FRANZ_ZEICHEN = /[éèêàçùûôîïœ«»]/, FRANZ_WOERTER = /\b(le|la|les|une|pour|dans|avec|vous|cette|qui|que|pas|aux|elle|aucun|aucune|votre|vos|chaque|donc|ton|tes|mais|sans)\b/;
const franzoesisch = [];
async function scan(seite, ort) {
  const texte = await seite.evaluate(() => {
    const aus = [document.title];
    const sichtbar = e => { const s = getComputedStyle(e); return s.display !== "none" && s.visibility !== "hidden"; };
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n; (n = w.nextNode());) { const p = n.parentElement; if (p && !["SCRIPT", "STYLE"].includes(p.tagName) && sichtbar(p) && n.textContent.trim()) aus.push(n.textContent.trim()); }
    document.querySelectorAll("[aria-label],[title],[placeholder],[alt]").forEach(e => ["aria-label", "title", "placeholder", "alt"].forEach(a => { const v = e.getAttribute(a); if (v) aus.push(v); }));
    document.querySelectorAll("textarea").forEach(e => { if (e.id !== "scr" && e.id !== "pText" && e.id !== "nScript") aus.push(e.value); });
    document.querySelectorAll("option").forEach(e => aus.push(e.textContent));
    return aus;
  });
  for (const t of texte) { const s = t.replaceAll("Café", "Cafe"); if (FRANZ_ZEICHEN.test(s) || FRANZ_WOERTER.test(s)) franzoesisch.push(`${ort}: ${t.slice(0, 120)}`); }
}

async function ablauf(seite, L, de, breit) {
  const s = de ? (ort => scan(seite, ort)) : (() => Promise.resolve());
  await seite.waitForSelector(".plan");
  assert.equal(await seite.title(), L.titel);
  assert.equal(await seite.$eval("html", e => e.lang), de ? "de" : "fr", "html lang passt zur Sprache");
  assert((await text(seite, ".demo-hinweis")).includes(L.hinweis), "Hinweis sichtbar");
  assert.equal(await seite.$eval(".demo-sprache a[aria-current]", e => e.textContent), L.sprache, "aktive Sprache im Schalter markiert");
  assert.equal(await anzahl(seite, ".demo-sprache a"), 2, "Schalter DE | FR");
  assert.equal(await anzahl(seite, ".item"), 4, "vier Projekte in der Liste");
  assert.equal(await text(seite, "h1"), L.h1);
  assert.equal(await anzahl(seite, ".plan"), 6, "sechs Einstellungen");
  assert.equal(await anzahl(seite, ".shot.skeleton"), 2, "zwei Einstellungen ohne Motorbild bleiben leer");
  assert((await seite.$$eval(".shot:not(.skeleton)", e => e.map(x => getComputedStyle(x).backgroundImage))).every(b => b.includes("shot_00")), "Motorbilder als Plankarten");
  assert((await seite.$$eval(".thumb", e => e.map(x => x.style.backgroundImage))).filter(Boolean).length >= 2, "Miniaturen in der Liste");
  await s("Projektansicht");

  // Plan korrigieren: Auswahllisten kommen aus dem echten Motor, Vorschau braucht ihn und sagt das
  await klick(seite, '.plan[data-i="2"]');
  await seite.waitForSelector("#pvGo");
  await warte(900);
  if (bildArgument && de && breit) await seite.screenshot({ path: path.resolve(bildArgument) });
  await s("Schublade");
  assert((await seite.$$eval("#fSize option", o => o.length)) === 10, "zehn Einstellungsgrößen im Stil PS1");
  assert.equal(await seite.$eval("#fSize", e => e.value), "close");
  await seite.select("#fSize", "extreme_close");
  await klick(seite, "#pvGo");
  await toast(seite, L.motorToast);
  assert((await text(seite, "#pvState")).includes(L.motorHinweis), "ehrlicher Hinweis statt erfundener Vorschau");
  await s("Schublade nach Hinweis");
  await klick(seite, "#pvSkip");
  await toast(seite, L.gespeichert);
  await seite.waitForSelector("#drawer.open");
  assert((await text(seite, '.plan[data-i="2"]')).includes(L.detail), "gespeicherte Einstellung ist im Plan sichtbar");
  await seite.keyboard.press("Escape");

  // Reiter, Aktionen, die den Motor bräuchten
  await klick(seite, '.tab[data-tab="script"]');
  assert((await seite.$eval("#scr", e => e.value)).includes(L.skript), "Skript des Szenarios");
  await s("Skript");
  await klick(seite, '.tab[data-tab="journal"]');
  await s("Protokoll");
  await klick(seite, '.tab[data-tab="video"]');
  await s("Video");
  await klick(seite, '.tab[data-tab="caps"]');
  assert((await text(seite, "#content")).includes(L.alles), "Fähigkeitsbericht");
  await s("Fähigkeiten");
  await klick(seite, '.tab[data-tab="plans"]');
  await klick(seite, '[data-run="preview"]');
  await toast(seite, L.motorToast);
  await klick(seite, "#makeBtn");
  await toast(seite, L.stimme);
  await klick(seite, '.seg button[data-style="voxel"]');
  await toast(seite, L.stilwechsel);

  // Anderes Projekt: Console 2D mit Bildern zu vier von neun Plänen; Fähigkeiten mit Begriffen aus dem Szenario
  await seite.evaluate(t => [...document.querySelectorAll(".item")].find(b => b.textContent.includes(t)).click(), L.p3);
  await seite.waitForFunction(t => document.querySelector("h1")?.textContent.includes(t), {}, L.p3);
  assert.equal(await anzahl(seite, ".plan"), 9, "neun Einstellungen");
  assert.equal(await anzahl(seite, ".shot.skeleton"), 5);
  await s("Console-Projekt");
  await klick(seite, '.plan[data-i="1"]');
  await seite.waitForSelector("#pvGo");
  assert.equal(await anzahl(seite, "#fSize option"), 3, "Console 2D kennt drei Größen");
  await s("Console-Schublade");
  await seite.keyboard.press("Escape");
  await seite.evaluate(t => [...document.querySelectorAll(".item")].find(b => b.textContent.includes(t)).click(), L.p1);
  await seite.waitForFunction(t => document.querySelector("h1")?.textContent.includes(t), {}, L.h1);
  await klick(seite, '.tab[data-tab="caps"]');
  await s("Fähigkeiten mit Begriffen");

  // Entwurf ohne Pläne: Fähigkeiten dort analysieren (echte, vorab berechnete Planerausgabe)
  await seite.evaluate(t => [...document.querySelectorAll(".item")].find(b => b.textContent.includes(t)).click(), L.p4);
  await seite.waitForFunction(t => document.querySelector("h1")?.textContent.includes(t), {}, L.p4);
  assert((await text(seite, "#content")).includes(L.leer));
  await s("Entwurf");
  await klick(seite, '.tab[data-tab="caps"]');
  await s("Entwurf Fähigkeiten");
  await klick(seite, "#capTool");
  await seite.waitForSelector("#pForm");
  await klick(seite, "#pGo");
  await seite.waitForSelector(".need.missing");
  assert((await anzahl(seite, ".need")) >= 3, "Bedarfskarten");
  assert((await text(seite, "#pOut")).includes(L.anfrage), "Erweiterungsanfragen des Planers");
  await s("Szenenanalyse");

  // Szene analysieren: Beispieltext, anderer Motor, freier Text (nicht vorbereitet)
  const beispiele = await seite.$$eval("[data-ex]", b => b.length);
  assert.equal(beispiele, 2);
  await klick(seite, '[data-ex="1"]');
  await klick(seite, "#pGo");
  await seite.waitForFunction(t => document.querySelector("#pOut")?.textContent.includes(t), {}, L.beispiel);
  await klick(seite, '[data-ex="0"]');
  await klick(seite, "#pGo");
  await seite.waitForSelector("mark.m.composed");
  await s("Beispiel 1");
  await klick(seite, 'input[name=pEng][value=console]');
  await seite.waitForFunction(() => !document.querySelector("#pGo").disabled && document.querySelector("#pSum"));
  await seite.waitForSelector("mark.m.missing");
  await s("Beispiel 1 Console 2D");
  await seite.$eval("#pText", (e, t) => { e.value = t; e.dispatchEvent(new Event("input")); }, L.frei);
  await klick(seite, "#pGo");
  await seite.waitForSelector('#pOut [role="alert"]');
  assert((await text(seite, "#pOut")).includes(L.motorHinweis), "freier Text: ehrlicher Hinweis");
  await s("Szenenanalyse Fehler");

  // Katalog mit gemalten Miniaturen
  await klick(seite, "#catBtn");
  await seite.waitForSelector(".catcard");
  assert((await anzahl(seite, ".catcard")) > 50, "Katalogkarten");
  await seite.waitForFunction(() => [...document.querySelectorAll(".catcard img")].slice(0, 12).every(i => i.complete && i.naturalWidth > 0));
  await s("Katalog");
  await klick(seite, `.cchip[data-cc="${L.kategorie}"]`);
  assert((await anzahl(seite, ".catcard")) > 20, "Kategorie Orte");
  await klick(seite, ".catcard");
  await seite.waitForSelector(".cdet");
  await s("Katalogeintrag");
  await klick(seite, "#eClose");
  await klick(seite, '[data-cs="console"]');
  assert((await anzahl(seite, ".catcard")) > 20, "Console 2D Katalog");
  await s("Katalog Console 2D");
  await klick(seite, '[data-cs="voxel"]');
  assert((await text(seite, "#cgrid")).includes(L.vorbereitung), "VOXEL: Miniaturen fehlen, das sagt die Oberfläche selbst");
  await s("Katalog VOXEL");

  // Musikvideo, neues Projekt, Speicherverwaltung
  await klick(seite, "#clipBtn");
  await seite.waitForSelector("#cGo");
  assert((await text(seite, "#main")).includes(L.clip));
  await s("Musikvideo");
  await klick(seite, "#newBtn");
  await s("Neues Video");
  await seite.type("#nName", L.neu);
  await klick(seite, "#nGo");
  await seite.waitForFunction(t => document.querySelector("h1")?.textContent === t, {}, L.neu);
  assert.equal(await anzahl(seite, ".item"), 5);
  await klick(seite, "#spaceBtn");
  await seite.waitForSelector(".spacelist");
  assert((await anzahl(seite, ".spacelist li")) === 5);
  await s("Speicher");
  await seite.keyboard.press("Escape");
  await klick(seite, ".itemdel");
  await seite.waitForSelector("#dClean");
  await s("Löschen");
  await klick(seite, "#dDel"); await s("Löschen bestätigen");
  await klick(seite, "#dNo");
}

async function handy(seite, L, de) {
  const s = de ? (ort => scan(seite, ort)) : (() => Promise.resolve());
  await seite.setViewport({ width: 390, height: 844, deviceScaleFactor: 2 });
  for (const [name, aktion] of [
    ["Projektansicht", async () => { await klick(seite, "#menuBtn"); await seite.evaluate(t => [...document.querySelectorAll(".item")].find(b => b.textContent.includes(t)).click(), L.p1); await seite.waitForFunction(() => document.querySelectorAll(".plan").length === 6); }],
    ["Plan-Schublade", async () => { await klick(seite, '.plan[data-i="0"]'); await seite.waitForSelector("#pvGo"); }],
    ["Szene analysieren", async () => { await seite.keyboard.press("Escape"); await klick(seite, "#menuBtn"); await klick(seite, "#planBtn"); await klick(seite, '[data-ex="0"]'); await klick(seite, "#pGo"); await seite.waitForSelector(".need"); }],
    ["Katalog", async () => { await klick(seite, "#menuBtn"); await klick(seite, "#catBtn"); await seite.waitForSelector(".catcard"); }],
    ["Musikvideo", async () => { await klick(seite, "#menuBtn"); await klick(seite, "#clipBtn"); await seite.waitForSelector("#cGo"); }],
  ]) {
    await aktion(); await warte(400);
    const u = await ueberlauf(seite);
    assert(u.dokument <= 0 && u.haupt <= 0, `kein horizontaler Überlauf bei 390 Pixel (${L.sprache}, ${name}): ${JSON.stringify(u)}`);
    await s("Handy " + name);
  }
  assert((await seite.$eval(".demo-sprache", e => e.getBoundingClientRect().right)) <= 390, "Sprachschalter passt auf 390 Pixel");
  await seite.setViewport({ width: 1440, height: 900 });
}

(async () => {
  await new Promise(r => server.listen(0, "127.0.0.1", r));
  const basis = `http://127.0.0.1:${server.address().port}/HorrorStudio3D/`;
  const browser = await puppeteer.launch({ executablePath: browserPfad, headless: true });
  const fehler = [], extern = [], schlecht = [];
  const neueSeite = async () => {
    const seite = await browser.newPage();
    seite.on("pageerror", e => fehler.push("Seitenfehler: " + e.message));
    seite.on("console", m => { if (m.type() === "error") fehler.push("Konsole: " + m.text()); });
    seite.on("request", r => { if (new URL(r.url()).hostname !== "127.0.0.1") extern.push(r.url()); });
    seite.on("response", r => { if (r.status() >= 400) schlecht.push(r.status() + " " + r.url()); });
    seite.on("requestfailed", r => schlecht.push("fehlgeschlagen " + r.url()));
    seite.on("dialog", d => d.accept());
    await seite.setViewport({ width: 1440, height: 900 });
    return seite;
  };
  try {
    // 1. Deutsch ist die Sprache beim Laden; danach Handybreite
    let seite = await neueSeite();
    await seite.goto(basis, { waitUntil: "networkidle0" });
    await ablauf(seite, SPRACHEN.de, true, true);
    await handy(seite, SPRACHEN.de, true);

    // 2. Wechsel zu Französisch über den Schalter: neue Fassung, französische Daten, html lang fr, Rückweg ebenfalls über den Schalter
    await seite.goto(basis, { waitUntil: "networkidle0" });
    await seite.waitForSelector(".plan");
    await Promise.all([seite.waitForNavigation({ waitUntil: "networkidle0" }), klick(seite, '.demo-sprache a[hreflang="fr"]')]);
    assert(seite.url().endsWith("/HorrorStudio3D/fr.html"), "Schalter FR führt zu fr.html: " + seite.url());
    await ablauf(seite, SPRACHEN.fr, false, true);
    await handy(seite, SPRACHEN.fr, false);
    await seite.goto(basis + "fr.html", { waitUntil: "networkidle0" });
    await seite.waitForSelector(".plan");
    await Promise.all([seite.waitForNavigation({ waitUntil: "networkidle0" }), klick(seite, '.demo-sprache a[hreflang="de"]')]);
    await seite.waitForSelector(".plan");
    assert.equal(await seite.$eval("html", e => e.lang), "de", "zurück auf Deutsch");
    assert.equal(await text(seite, "h1"), SPRACHEN.de.h1);
    assert.equal(await text(seite, ".demo-sprache a[aria-current]"), "DE");
    await seite.close();

    // 3. ?lang=fr in der Adresse wählt Französisch, ?lang=de auf der französischen Seite Deutsch; ohne Angabe bleibt es Deutsch
    seite = await neueSeite();
    await seite.goto(basis + "?lang=fr", { waitUntil: "networkidle0" });
    await seite.waitForSelector(".plan");
    assert.equal(await seite.$eval("html", e => e.lang), "fr", "?lang=fr");
    assert.equal(await text(seite, "h1"), SPRACHEN.fr.h1);
    await seite.goto(basis + "fr.html?lang=de", { waitUntil: "networkidle0" });
    await seite.waitForSelector(".plan");
    assert.equal(await seite.$eval("html", e => e.lang), "de", "?lang=de");
    assert.equal(await text(seite, "h1"), SPRACHEN.de.h1);
    await seite.goto(basis + "?x=1", { waitUntil: "networkidle0" });
    await seite.waitForSelector(".plan");
    assert.equal(await seite.$eval("html", e => e.lang), "de", "ohne ?lang bleibt es Deutsch");
    await seite.close();
  } finally { await browser.close(); server.close(); }
  assert.deepEqual(fehler, [], "keine Laufzeitfehler");
  assert.deepEqual(extern, [], "keine externen Anfragen");
  assert.deepEqual(schlecht, [], "keine fehlgeschlagenen Anfragen");
  assert.deepEqual(franzoesisch, [], "kein Französisch in der deutschen Fassung");
  console.log("Browserprüfung der Demo bestanden: echte Oberfläche in zwei Sprachen (Deutsch beim Laden, Schalter DE | FR, ?lang=fr), vier Projekte, Einstellungsschublade, Szenenanalyse, Katalog, Musikvideo, Speicher, Handy 390 Pixel; keine Fehler, keine externen oder fehlgeschlagenen Anfragen, kein Französisch in der deutschen Fassung.");
})().catch(e => { console.error(e); process.exitCode = 1; server.close(); });
