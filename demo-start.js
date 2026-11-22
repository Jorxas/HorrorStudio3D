/* Öffentliche Demo: Die echte Oberfläche (hstudio/web/static/studio.html, studio_extras.js, publication_bridge.js) läuft unverändert.
   Dieses Skript ersetzt nur den lokalen Python-Server: Es beantwortet die API-Aufrufe der Oberfläche aus den Dateien unter daten/, die
   tools/demo_export.py mit dem echten Motor erzeugt hat. Projekte, Texte und Namen sind erfunden; die Bilder sind echte, vorab gerenderte
   Motorbilder. Nichts wird im Browser gerendert, kein Aufruf verlässt diese Seite, ein Neuladen setzt alle Änderungen zurück.
   Wird vor studio.html geladen (siehe tools/demo-bauen.mjs). Wo der Motor, die GPU, Stimmen oder Konten nötig wären, antwortet es mit
   einem ehrlichen Hinweis statt mit einem erfundenen Ergebnis. */
(function () {
'use strict';
const BASIS = location.pathname.replace(/[^/]*$/, '');                 // z. B. /HorrorStudio3D/ auf GitHub Pages
const original = window.fetch.bind(window);
const MOTOR = 'Demo: Der Studiomotor (Python, GPU, Stimme) läuft hier nicht, deshalb entstehen keine neuen Bilder, Stimmen oder Videos. Die gezeigten Bilder sind echte, vorab gerenderte Motorausgaben.';

const antwort = (daten, status) => new Response(JSON.stringify(daten), { status: status || 200, headers: { 'Content-Type': 'application/json' } });
const fehler = (status, text) => antwort({ detail: text }, status);
const kopie = x => JSON.parse(JSON.stringify(x));
const laden = name => original(BASIS + 'daten/' + name).then(r => { if (!r.ok) throw new Error(name + ': ' + r.status); return r.json(); });

let zustand = null;
function bereit() {
  return zustand || (zustand = Promise.all([laden('projekte.json'), laden('plan.json'), laden('katalog.json')]).then(([projekte, plan, katalog]) => {
    const z = { projekte: new Map(), papierkorb: [], plan, katalog };
    projekte.forEach(p => z.projekte.set(p.slug, p));
    return z;
  }));
}

/* ---------- Pläne: Portierung von hstudio/shot_preview.py (apply_patch, current), nur für die Modi, die die Demoprojekte brauchen ---------- */
const ZOOM = { wide: 1.0, medium: 1.25, close: 1.55 };
const ALIAS = { closeup: 'close', high_corner: 'wide', low: 'full', push_in: 'dolly_in', pull_out: 'dolly_out', push: 'dolly_in' };
const ids = liste => new Set(liste.map(x => x[0]));
const gefuehrt = sh => { const c = sh.camera || {}; return c.rig === 'path' || !!sh.tracks || (c.preset === 'free' && !!c.keys); };

function aktuell(ep, index, modus) {
  const sh = ep.shots[index], cam = sh.camera || {}, fx = sh.fx || {};
  let groesse, bewegung;
  if (modus === 'console') {
    let z = parseFloat(cam.zoom || 1); if (isNaN(z)) z = 1;
    groesse = 'wide'; Object.keys(ZOOM).forEach(k => { if (Math.abs(ZOOM[k] - z) < Math.abs(ZOOM[groesse] - z)) groesse = k; });
    bewegung = cam.move || 'drift';
  } else {
    groesse = cam.shot || ALIAS[cam.preset] || cam.preset || 'wide'; bewegung = ALIAS[cam.move] || cam.move || 'static';
  }
  const gesichter = {};
  ep.shots.slice(0, index + 1).forEach(s => (s.actors || []).forEach(a => { if (a && a.id && (a.face || !(a.id in gesichter))) gesichter[a.id] = a.face || 'neutral'; }));
  const hier = new Set((sh.actors || []).filter(a => a && a.id).map(a => a.id));
  [].concat(cam.on || []).forEach(x => { if (typeof x === 'string') hier.add(x); });
  const bekannt = new Set(Object.keys(gesichter).concat(Object.keys(ep.cast || {})));
  const faces = {}; [...hier].sort().forEach(k => { if (bekannt.has(k)) faces[k] = gesichter[k] || 'neutral'; });
  return { mode: modus, size: groesse, move: bewegung, faces, transition: fx.fade_in ? 'fade' : fx.flash ? 'flash' : 'cut', directed: gefuehrt(sh) };
}

function anwenden(ep, index, patch, opt) {
  const sh = ep.shots[index]; patch = patch || {};
  if (patch.camera) {
    if (gefuehrt(sh)) throw new Error('La caméra de ce plan est écrite à la main, image par image : elle ne se règle pas ici.');
    const sz = patch.camera.shot, mv = patch.camera.move, c = Object.assign({}, sh.camera || {});
    if (sz != null && !ids(opt.sizes).has(sz)) throw new Error('Cadrage « ' + sz + ' » indisponible pour ce plan.');
    if (mv != null && !ids(opt.moves).has(mv)) throw new Error('Mouvement « ' + mv + ' » indisponible pour ce plan.');
    if (opt.mode === 'console') { if (sz != null) c.zoom = ZOOM[sz]; if (mv != null) c.move = mv; }
    else { if (sz != null) { c.shot = sz; delete c.preset; } if (mv === 'static') delete c.move; else if (mv != null) c.move = mv; }
    sh.camera = c;
  }
  (patch.actors || []).forEach(a => {
    if (!ids(opt.faces).has(a.face)) throw new Error('Expression « ' + a.face + ' » indisponible pour ce plan.');
    let ziel = (sh.actors || []).find(x => x && x.id === a.id);
    if (!ziel) {
      const bekannt = ep.shots.slice(0, index).some(s => (s.actors || []).some(x => x && x.id === a.id)) || a.id in (ep.cast || {});
      if (!bekannt) throw new Error('Le personnage « ' + a.id + ' » n\'est pas dans ce plan.');
      ziel = { id: a.id }; (sh.actors = sh.actors || []).push(ziel);
    }
    ziel.face = a.face;
  });
  if (patch.transition != null) {
    if (!ids(opt.transitions).has(patch.transition)) throw new Error('Transition « ' + patch.transition + ' » indisponible dans ce style.');
    const vor = index ? ep.shots[index - 1] : null, fx = Object.assign({}, sh.fx || {}), vfx = vor ? Object.assign({}, vor.fx || {}) : null;
    delete fx.fade_in; delete fx.flash; if (vfx) delete vfx.fade_out;
    if (patch.transition === 'fade') { fx.fade_in = 0.6; if (vfx) vfx.fade_out = 0.6; } else if (patch.transition === 'flash') fx.flash = 0.9;
    [[sh, fx], [vor, vfx]].forEach(([s, f]) => { if (!s) return; if (f && Object.keys(f).length) s.fx = f; else delete s.fx; });
  }
  if ('note' in patch) { const n = String(patch.note || '').trim(); if (n) sh.note = n; else delete sh.note; }
  return ep;
}

/* ---------- Hilfen ---------- */
const eintrag = p => ({ slug: p.slug, name: p.meta.name, style: p.meta.style, render_engine: p.meta.render_engine, series: p.meta.series, part_label: p.meta.part_label,
  created: p.meta.created, status: p.status, preview: !!(p.previews && p.previews[0]) });
const slugify = s => (String(s || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 60)) || 'video';
const holen = (z, slug) => z.projekte.get(decodeURIComponent(slug));
const nicht_gefunden = () => fehler(404, 'projet introuvable');

async function bearbeiten(methode, pfad, abfrage, body, z) {
  let m;
  if (pfad === '/api/projects') {
    if (methode === 'GET') return antwort([...z.projekte.values()].map(eintrag).sort((a, b) => b.created - a.created));
    if (methode === 'POST') {
      let slug = slugify(body.name), n = 2; const basis = slug; while (z.projekte.has(slug)) slug = basis + '_' + n++;
      const meta = { name: body.name || 'Nouvel épisode', style: body.style || 'pixel3d', render_engine: body.render_engine || 'pixel3d', series: null, part_label: null, created: Date.now() / 1000, notes: '', director: '' };
      const script = body.script || '';
      z.projekte.set(slug, { slug, meta, szenario: null, script, episode: '', lines: [], warnings: [], capabilities: null, previews: [],
        status: { script: !!script, voice: false, lines: false, episode: false, mix: false, thumbnail: false, metadata: false, renders: [] },
        optionen: [], groesse: { total: script.length, generated: 0 }, bilder: [] });
      return antwort({ slug });
    }
  }
  if ((m = /^\/api\/projects\/([^/]+)$/.exec(pfad))) {
    const p = holen(z, m[1]); if (!p) return nicht_gefunden();
    if (methode === 'GET') return antwort({ slug: p.slug, meta: p.meta, status: p.status, script: p.script, episode: p.episode, lines: p.lines, warnings: p.warnings, metadata: null, job: null, qc: {},
      capabilities: p.capabilities, previews: p.previews });
    if (methode === 'DELETE') {
      const gesamt = p.groesse.total; z.projekte.delete(p.slug);
      if (abfrage.get('definitif') !== 'true') z.papierkorb.push({ name: p.slug + '_papierkorb', slug: p.slug, size: gesamt, projekt: p });
      return antwort({ ok: true, freed: abfrage.get('definitif') === 'true' ? gesamt : 0, definitif: abfrage.get('definitif') === 'true' });
    }
  }
  if ((m = /^\/api\/projects\/([^/]+)\/(meta|script|episode|clean|job|duplicate)$/.exec(pfad))) {
    const p = holen(z, m[1]); if (!p) return nicht_gefunden();
    const was = m[2];
    if (was === 'job') return antwort({});
    if (was === 'meta' && methode === 'PUT') {
      const stilwechsel = ('style' in body && body.style !== p.meta.style) || ('render_engine' in body && body.render_engine !== p.meta.render_engine);
      if (stilwechsel && p.previews.some(Boolean)) return fehler(409, 'Demo: Die Vorschaubilder dieses Projekts sind vorab im ursprünglichen Stil gerendert; ein anderer Stil würde neu gerendert und braucht den Motor, der hier nicht läuft. Im Entwurf oder in einem neuen Projekt lässt sich der Stil wählen.');
      Object.assign(p.meta, body); return antwort({ ok: true });
    }
    if (was === 'script' && methode === 'PUT') { p.script = body.script || ''; p.status.script = !!p.script; return antwort({ ok: true }); }
    if (was === 'episode' && methode === 'PUT') {
      try { p.episode = JSON.stringify(JSON.parse(body.episode)); } catch (e) { return fehler(400, 'JSON invalide : ' + e.message); }
      return antwort({ ok: true, warnings: [] });
    }
    if (was === 'clean' && methode === 'POST') {
      const frei = p.groesse.generated; p.groesse.total -= frei; p.groesse.generated = 0; p.previews = p.previews.map(() => ''); return antwort({ ok: true, freed: frei });
    }
  }
  if ((m = /^\/api\/projects\/([^/]+)\/run\/([a-z_]+)$/.exec(pfad)) && methode === 'POST') return holen(z, m[1]) ? fehler(409, MOTOR) : nicht_gefunden();
  if ((m = /^\/api\/projects\/([^/]+)\/shot_preview$/.exec(pfad)) && methode === 'POST') return holen(z, m[1]) ? fehler(409, MOTOR) : nicht_gefunden();
  if ((m = /^\/api\/projects\/([^/]+)\/shot_apply$/.exec(pfad)) && methode === 'POST') {
    const p = holen(z, m[1]); if (!p) return nicht_gefunden();
    const i = body.index; if (!p.episode || !Number.isInteger(i)) return fehler(400, 'Numéro de plan manquant.');
    try { const ep = JSON.parse(p.episode); anwenden(ep, i, body.patch, p.optionen[i]); p.episode = JSON.stringify(ep); } catch (e) { return fehler(400, e.message); }
    return antwort({ ok: true, warnings: [] });
  }
  if (pfad === '/api/shot_preview/options' && methode === 'GET') {
    const p = holen(z, abfrage.get('slug') || ''), i = parseInt(abfrage.get('index'), 10);
    if (!p || !(i >= 0) || !p.optionen[i]) return fehler(400, 'Demo: Auswahllisten gibt es nur für die Pläne der Beispielprojekte.');
    const o = kopie(p.optionen[i]); o.current = aktuell(JSON.parse(p.episode), i, o.mode); return antwort(o);
  }
  if (pfad === '/api/storage' && methode === 'GET') {
    const projekte = {}; z.projekte.forEach(p => { projekte[p.slug] = { total: p.groesse.total, generated: p.groesse.generated }; });
    const korb = z.papierkorb.map(t => ({ name: t.name, slug: t.slug, size: t.size })), summe = Object.values(projekte).reduce((a, v) => a + v.total, 0);
    return antwort({ projects: projekte, trash: korb, trash_bytes: korb.reduce((a, t) => a + t.size, 0), total_bytes: summe });
  }
  if (pfad === '/api/trash' && methode === 'DELETE') { const frei = z.papierkorb.reduce((a, t) => a + t.size, 0); z.papierkorb = []; return antwort({ ok: true, freed: frei }); }
  if ((m = /^\/api\/trash\/([^/]+)\/restore$/.exec(pfad)) && methode === 'POST') {
    const k = z.papierkorb.findIndex(t => t.name === decodeURIComponent(m[1])); if (k < 0) return fehler(404, 'introuvable');
    const t = z.papierkorb.splice(k, 1)[0]; z.projekte.set(t.slug, t.projekt); return antwort({ ok: true, slug: t.slug });
  }
  if (pfad === '/api/catalogue' && methode === 'GET') return antwort(z.katalog);
  if (pfad === '/api/clips') return methode === 'GET' ? antwort([]) : fehler(409, 'Demo: Die Musikanalyse (Tempo, Takte, Sektionen) braucht Python und ffmpeg und läuft hier nicht.');
  if (pfad === '/api/plan' && methode === 'POST') {
    const text = String(body.text || '').trim(), eng = body.engine === 'console' ? 'console' : 'pixel3d', vorbereitet = z.plan[text];
    if (!vorbereitet) return fehler(400, 'Demo: Der Szenenplaner (Python) läuft hier nicht. Vorbereitet sind die beiden Beispieltexte und die Skripte der Projekte; deren Ergebnisse sind echte Ausgaben des Planers.');
    return antwort(vorbereitet[eng]);
  }
  if (pfad === '/api/publication/status') return antwort({ enabled: false });
  return fehler(404, 'Demo: Diese Funktion gibt es in der öffentlichen Demo nicht.');
}

window.fetch = async function (eingabe, optionen) {
  const adresse = new URL(typeof eingabe === 'string' ? eingabe : eingabe instanceof URL ? eingabe.href : eingabe.url, location.href);
  let pfad = adresse.pathname.startsWith(BASIS) ? '/' + adresse.pathname.slice(BASIS.length) : adresse.pathname;
  if (adresse.origin !== location.origin || !pfad.startsWith('/api/') || /^\/api\/projects\/[^/]+\/file\//.test(pfad)) return original(eingabe, optionen);
  const methode = ((optionen && optionen.method) || 'GET').toUpperCase();
  let body = {}; if (optionen && typeof optionen.body === 'string' && optionen.body) { try { body = JSON.parse(optionen.body); } catch (e) { body = {}; } }
  try { return await bearbeiten(methode, pfad, adresse.searchParams, body, await bereit()); }
  catch (e) { return fehler(500, 'Demo: ' + e.message); }
};
})();
