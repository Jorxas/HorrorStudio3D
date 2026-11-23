(function () {
'use strict';
const css = document.createElement('style');
css.textContent = `
.itemrow{display:flex;align-items:center;gap:2px;position:relative} .itemrow .item{flex:1;min-width:0;padding-right:6px}
.itemdel{border:0;background:none;border-radius:9px;width:32px;height:32px;display:grid;place-items:center;color:var(--ink-3);opacity:0;transition:opacity .15s,background .15s,color .15s;flex:none}
.itemrow:hover .itemdel,.itemdel:focus-visible,.itemrow:focus-within .itemdel{opacity:1} .itemdel:hover{background:var(--bad-soft);color:var(--bad)}
@media(hover:none){.itemdel{opacity:.7}}
.sizetag{color:var(--ink-3);font-weight:600}
.catbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:14px 0 4px}
.catbar input[type=search]{flex:1;min-width:200px;border:1px solid var(--line);background:var(--card);border-radius:11px;padding:9px 13px;color:var(--ink);font:inherit}
.catchips{display:flex;gap:7px;flex-wrap:wrap;margin:10px 0 14px}
.cchip{border:1px solid var(--line);background:var(--card);border-radius:999px;padding:5px 12px;font-size:13px;font-weight:600;color:var(--ink-2)} .cchip small{color:var(--ink-3);margin-left:4px;font-weight:600}
.cchip.on{background:var(--brand);border-color:var(--brand);color:#fff} .cchip.on small{color:#dcd9ff}
.catgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(168px,1fr));gap:16px}
.catcard{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;box-shadow:var(--shadow);cursor:pointer;text-align:left;padding:0;display:flex;flex-direction:column;transition:transform .15s,box-shadow .15s}
.catcard:hover{transform:translateY(-3px);box-shadow:var(--shadow-lg)}
.catimg{aspect-ratio:4/3;background:linear-gradient(160deg,var(--paper),var(--line));display:grid;place-items:center;color:var(--ink-3);font-size:12px;text-align:center;padding:8px} .catimg img{width:100%;height:100%;object-fit:cover;display:block}
.catcard .cm{padding:9px 11px 11px;display:grid;gap:5px} .catcard b{font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap} .catcard .g{font-size:12px;color:var(--ink-3);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.st.converted{background:var(--brand-soft);color:var(--info-ink)} .st.approx{background:var(--warn-soft);color:var(--warn-ink)} .st.shared{background:var(--ok-soft);color:var(--ok-ink)}
.rule{display:flex;gap:10px;align-items:flex-start;padding:10px 14px;border-radius:12px;background:var(--brand-soft);color:var(--ink-2);font-size:13px;margin:6px 0 0}
.cdet img{width:100%;border-radius:12px;border:1px solid var(--line);display:block;background:var(--paper)}
.cdet .two{display:grid;grid-template-columns:1fr 1fr;gap:10px} .cdet .two figure{margin:0;display:grid;gap:4px;font-size:12px;color:var(--ink-3);font-weight:600}
.cdet pre{margin:0;background:var(--paper);border:1px solid var(--line);border-radius:10px;padding:10px 12px;font:12.5px/1.5 ui-monospace,Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere;color:var(--ink)}
.btn.danger{background:var(--bad);border-color:var(--bad);color:#fff} .btn.danger:hover{background:#b93434}
.spacelist{display:grid;gap:6px;max-height:46vh;overflow:auto;margin:0;padding:0;list-style:none}
.spacelist li{display:flex;gap:10px;align-items:center;padding:8px 10px;border:1px solid var(--line);border-radius:11px;background:var(--card)} .spacelist .n{flex:1;min-width:0} .spacelist .n b{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bar{height:6px;border-radius:99px;background:var(--line);overflow:hidden} .bar i{display:block;height:100%;background:var(--brand)}
.pvbox{position:relative} .pvbox video{max-height:48vh;width:100%;border-radius:12px;background:#000;display:block}
.pvstate{font-size:13px;color:var(--ink-2);display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.pvstale{color:var(--warn-ink);font-weight:600}
`;
document.head.append(css);

const fmt = b => { b = +b || 0; if (b >= 1073741824) return (b / 1073741824).toFixed(b >= 10737418240 ? 0 : 1).replace('.', ',') + ' GB'; if (b >= 1048576) return Math.round(b / 1048576) + ' MB'; if (b >= 1024) return Math.round(b / 1024) + ' KB'; return b + ' B'; };
const openModal = html => { $('#modalBody').innerHTML = html; $('#modal').classList.add('open'); };
const closeModal = () => $('#modal').classList.remove('open');
$('#modal').addEventListener('click', e => { if (e.target.id === 'modal') closeModal(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape' && $('#modal').classList.contains('open')) closeModal(); });
const STYLE_NAMES = { ps1: 'PS1', voxel: 'VOXEL', console: 'Konsole 2D' };

async function loadStorage(force) {
  try { S.storage = await api('GET', 'api/storage' + (force ? '?refresh=true' : '')); } catch (e) { S.storage = S.storage || null; }
  decorateList();
}
function decorateList() {
  const list = $('#list'); if (!list) return; const sz = (S.storage && S.storage.projects) || {};
  $$('.item', list).forEach(b => {
    if (b.parentElement.classList.contains('itemrow')) return;
    const slug = b.dataset.slug, row = document.createElement('div'); row.className = 'itemrow'; b.replaceWith(row); row.append(b);
    const del = document.createElement('button'); del.className = 'itemdel'; del.title = 'Löschen oder Speicher freigeben'; del.setAttribute('aria-label', 'Dieses Video löschen oder Speicher freigeben'); del.textContent = '🗑'; del.onclick = e => { e.stopPropagation(); openDelete(slug); }; row.append(del);
    const s = sz[slug], small = $('small', b); if (s && small && !$('.sizetag', small)) small.insertAdjacentHTML('beforeend', ` · <span class="sizetag">${fmt(s.total)}</span>`);
  });
  const foot = $('#foot');
  if (foot && S.storage) foot.innerHTML = `${S.projects.length} Video${S.projects.length > 1 ? 's' : ''} · ${fmt(S.storage.total_bytes)} <button class="linkbtn" id="spaceBtn">Speicher verwalten</button>`, $('#spaceBtn').onclick = openSpace;
}
function projName(slug) { const p = (S.projects || []).find(x => x.slug === slug); return (p && (p.name || p.slug)) || slug; }
async function openDelete(slug) {
  await loadStorage(true); const s = ((S.storage || {}).projects || {})[slug] || { total: 0, generated: 0 }, name = projName(slug), keep = Math.max(0, s.total - s.generated);
  openModal(`<div><h2 style="margin:0 0 4px">„${esc(name)}“ löschen</h2><div class="sub">Dieses Projekt belegt <b>${fmt(s.total)}</b> auf deiner Festplatte.</div></div>
  <div class="bar" aria-hidden="true"><i style="width:${s.total ? Math.round(100 * s.generated / s.total) : 0}%"></i></div>
  <div class="hint" style="margin-top:-8px">${fmt(s.generated)} ist Material, das das Studio neu erzeugen kann (Video, Vorschauen, Arbeitsdateien); ${fmt(keep)} gehören dir (Skript, Stimme, Einstellungen).</div>
  <div style="display:grid;gap:10px">
    <button class="btn soft" id="dClean" style="text-align:left"><b>Speicher freigeben · ${fmt(s.generated)}</b><br><span class="hint">Löscht das Video, die Vorschauen und die Arbeitsdateien. Skript, Stimme und Einstellungen bleiben erhalten: Du kannst das Video neu erstellen.</span></button>
    <button class="btn danger" id="dDel" style="text-align:left"><b>Vollständig löschen · ${fmt(s.total)}</b><br><span style="font-weight:400;font-size:13px">Löscht das ganze Projekt. Nicht rückgängig zu machen.</span></button>
    <button class="linkbtn" id="dTrash" style="justify-self:start">Stattdessen in den Papierkorb legen (wiederherstellbar, gibt keinen Speicher frei)</button></div>
  <div style="display:flex;justify-content:flex-end"><button class="btn" id="dNo">Abbrechen</button></div>`);
  $('#dNo').onclick = closeModal;
  if (s.generated < 1024) { const c = $('#dClean'); c.disabled = true; c.style.opacity = .55; c.innerHTML = '<b>Nichts freizugeben</b><br><span class="hint">Dieses Projekt enthält kein Video und keine Vorschau zum Löschen.</span>'; } else $('#dClean').onclick = () => doRemove(slug, 'clean');
  $('#dTrash').onclick = () => doRemove(slug, 'trash');
  $('#dDel').onclick = () => { const b = $('#dDel'); if (b.dataset.sure) return doRemove(slug, 'delete'); b.dataset.sure = '1'; b.innerHTML = '<b>Ja, endgültig löschen</b><br><span style="font-weight:400;font-size:13px">Letzte Bestätigung: „' + esc(name) + '“ wird endgültig gelöscht.</span>'; };
}
async function doRemove(slug, mode) {
  try {
    const r = mode === 'clean' ? await api('POST', `api/projects/${slug}/clean`) : await api('DELETE', `api/projects/${slug}${mode === 'delete' ? '?definitif=true' : ''}`);
    closeModal(); toast(mode === 'clean' ? `Speicher freigegeben: ${fmt(r.freed)}` : mode === 'delete' ? `Gelöscht · ${fmt(r.freed)} freigegeben` : 'In den Papierkorb gelegt');
    if (mode !== 'clean' && S.slug === slug) { S.slug = null; S.p = null; S.ep = null; closeDrawer(); }
    S.projects = await api('GET', 'api/projects'); renderList(); await loadStorage(true);
    if (mode === 'clean' && S.slug === slug) await openProject(slug, true); else renderMain();
  } catch (e) { toast(e.message, true); }
}
async function openSpace() {
  await loadStorage(true); const st = S.storage || { projects: {}, trash: [], trash_bytes: 0, total_bytes: 0 };
  const rows = Object.entries(st.projects).sort((a, b) => b[1].total - a[1].total), max = rows.length ? rows[0][1].total || 1 : 1;
  openModal(`<div><h2 style="margin:0 0 4px">Speicherplatz</h2><div class="sub">${rows.length} Projekte · <b>${fmt(st.total_bytes)}</b>${st.trash_bytes ? ` · Papierkorb ${fmt(st.trash_bytes)}` : ''}</div></div>
  <ul class="spacelist">${rows.map(([slug, s]) => `<li><div class="n"><b>${esc(projName(slug))}</b><div class="bar"><i style="width:${Math.max(2, Math.round(100 * s.total / max))}%"></i></div></div><span class="sizetag">${fmt(s.total)}</span><button class="btn sm" data-del="${esc(slug)}">Löschen …</button></li>`).join('') || '<li class="hint">Kein Projekt.</li>'}</ul>
  ${st.trash.length ? `<div class="panel" style="padding:14px"><b>Papierkorb · ${fmt(st.trash_bytes)}</b><ul class="spacelist" style="margin-top:8px">${st.trash.map(t => `<li><div class="n"><b>${esc(t.slug)}</b></div><span class="sizetag">${fmt(t.size)}</span><button class="btn sm" data-restore="${esc(t.name)}">Wiederherstellen</button></li>`).join('')}</ul><div style="margin-top:10px"><button class="btn danger sm" id="trEmpty">Papierkorb leeren und ${fmt(st.trash_bytes)} freigeben</button></div></div>` : ''}
  <div style="display:flex;justify-content:flex-end"><button class="btn" id="spClose">Schließen</button></div>`);
  $('#spClose').onclick = closeModal; $$('[data-del]', $('#modalBody')).forEach(b => b.onclick = () => openDelete(b.dataset.del));
  $$('[data-restore]', $('#modalBody')).forEach(b => b.onclick = async () => { try { await api('POST', `api/trash/${encodeURIComponent(b.dataset.restore)}/restore`); toast('Projekt wiederhergestellt'); S.projects = await api('GET', 'api/projects'); renderList(); openSpace(); } catch (e) { toast(e.message, true); } });
  const te = $('#trEmpty'); if (te) te.onclick = async () => { try { const r = await api('DELETE', 'api/trash'); toast(`Papierkorb geleert · ${fmt(r.freed)} freigegeben`); await loadStorage(true); openSpace(); } catch (e) { toast(e.message, true); } };
}

const CAT = { all: null, style: null, cat: '', q: '', ref: false, shown: 96 };
const statusOf = (e, s) => (e.styles && e.styles[s]) || (e.styles ? null : (s === 'console' ? null : 'native'));
const inStyle = (e, s) => s === 'console' ? !!(e.styles && e.styles.console) || e.category === 'Konsole 2D' : (e.category !== 'Konsole 2D' && !!statusOf(e, s));
const thumbOf = (e, s) => (e.thumbs && e.thumbs[s]) || (s === 'voxel' ? e.thumb : null) || (e.category === 'Sons' ? e.thumb : null);
const STLAB = { native: 'nativ', converted: 'konvertiert', approx: 'angenähert' };
async function openCatalogue() {
  S.view = 'catalogue'; S.slug = null; S.p = null; S.ep = null; closeDrawer(); renderList(); setRail('catalogue');
  if (!CAT.style) CAT.style = (S.lastStyle && S.lastStyle !== 'console') ? S.lastStyle : 'voxel';
  if (!CAT.all) { try { CAT.all = await api('GET', 'api/catalogue'); } catch (e) { CAT.all = []; toast(e.message, true); } }
  renderMain(); try { history.replaceState(null, '', '#catalogue'); } catch (e) { }
}
function renderCatalogue() {
  const m = $('#main'), s = CAT.style, all = (CAT.all || []).filter(e => (CAT.ref || !e.reference) && inStyle(e, s));
  const q = CAT.q.trim().toLowerCase(), qf = e => !q || (e.name + ' ' + (e.key || '') + ' ' + (e.group || '') + ' ' + (e.category || '')).toLowerCase().includes(q);
  const pool = all.filter(qf), counts = {}; pool.forEach(e => counts[e.category] = (counts[e.category] || 0) + 1);
  const cats = Object.entries(counts).sort((a, b) => b[1] - a[1]), list = pool.filter(e => !CAT.cat || e.category === CAT.cat);
  const refN = (CAT.all || []).filter(e => e.reference && inStyle(e, s)).length;
  const rule = s === 'console' ? 'Der Stil Konsole 2D hat seinen eigenen Katalog: flache Pixelgrafik im Konsolenlook.' : 'PS1 und VOXEL zeigen genau dieselben Elemente: Nur die Art, sie zu zeichnen, ändert sich. Eine Plakette sagt, ob das Element in diesem Stil „nativ“ gezeichnet, aus dem anderen „konvertiert“ oder „angenähert“ ist.';
  m.innerHTML = `<div class="top"><div class="title-row"><div><h1>Katalog</h1><div class="sub">Alles, was das Studio zeichnen kann · ${all.length.toLocaleString('de-DE')} Elemente im Stil ${STYLE_NAMES[s]}</div></div><span class="spacer"></span>
      <div class="seg" role="group" aria-label="Stil des Katalogs">${STYLES.map(x => `<button data-cs="${x.id}" class="${x.id === s ? 'on' : ''}" title="${esc(x.desc)}">${x.name}</button>`).join('')}</div></div>
    <div class="rule" role="note"><span aria-hidden="true">ℹ️</span><span>${rule}</span></div>
    <div class="catbar"><input type="search" id="cq" placeholder="Suchen: Zombie, Bett, Kirche, Lampe, Skelett …" value="${esc(CAT.q)}" autocomplete="off" aria-label="Im Katalog suchen">${refN ? `<button class="btn ${CAT.ref ? 'soft' : ''} sm" id="cref" title="Importierte Modelle dienen als Inspiration: In den Filmen werden sie nicht unverändert verwendet.">${CAT.ref ? 'Inspirationsreferenzen ausblenden' : 'Inspirationsreferenzen anzeigen'} (${refN})</button>` : ''}</div>
    <div class="catchips" role="group" aria-label="Kategorien"><button class="cchip ${CAT.cat ? '' : 'on'}" data-cc="">Alle<small>${pool.length}</small></button>${cats.map(([c, n]) => `<button class="cchip ${CAT.cat === c ? 'on' : ''}" data-cc="${esc(c)}">${esc(c)}<small>${n}</small></button>`).join('')}</div></div>
    <div class="content"><div class="catgrid" id="cgrid"></div><div style="text-align:center;margin-top:20px" id="cmore"></div></div>`;
  $$('[data-cs]', m).forEach(b => b.onclick = () => { CAT.style = b.dataset.cs; CAT.cat = ''; CAT.shown = 96; renderCatalogue(); });
  $$('[data-cc]', m).forEach(b => b.onclick = () => { CAT.cat = b.dataset.cc; CAT.shown = 96; renderCatalogue(); });
  const cq = $('#cq'); let t; cq.oninput = () => { clearTimeout(t); t = setTimeout(() => { CAT.q = cq.value; CAT.shown = 96; const pos = cq.selectionStart; renderCatalogue(); const n = $('#cq'); n.focus(); n.setSelectionRange(pos, pos); }, 200); };
  const cr = $('#cref'); if (cr) cr.onclick = () => { CAT.ref = !CAT.ref; renderCatalogue(); };
  const g = $('#cgrid'), vis = list.slice(0, CAT.shown);
  if (!CAT.all || !CAT.all.length) g.innerHTML = '<div class="empty" style="grid-column:1/-1"><div class="art">📚</div><h2>Katalog leer</h2><p>Starte „python -m hstudio.catalogue build“ im Studioordner.</p></div>';
  else if (!list.length) g.innerHTML = '<div class="empty" style="grid-column:1/-1"><div class="art">🔎</div><h2>Nichts passt</h2><p>Versuche ein anderes Wort oder eine andere Kategorie.</p></div>';
  g.innerHTML = g.innerHTML || vis.map((e, i) => { const th = thumbOf(e, s), st = statusOf(e, s) || (s === 'console' ? 'native' : null);
    return `<button class="catcard" data-i="${i}" aria-label="${esc(e.name)}"><div class="catimg">${th ? `<img loading="lazy" alt="" src="catalogue/${esc(th)}">` : `Bild ${STYLE_NAMES[s]} in Vorbereitung`}</div><div class="cm"><b title="${esc(e.name)}">${esc(e.name)}</b><span class="g">${esc(e.group || e.category)}</span><div class="chips">${st ? `<span class="st ${st}">${STLAB[st] || st}</span>` : ''}${e.credit_required ? '<span class="chip warn" title="Quellenangabe zu veröffentlichen">Quellenangabe</span>' : ''}</div></div></button>`; }).join('');
  $$('.catcard', g).forEach(b => b.onclick = () => openEntry(vis[+b.dataset.i]));
  const mo = $('#cmore'); if (list.length > CAT.shown) { mo.innerHTML = `<button class="btn">Mehr anzeigen (${list.length - CAT.shown} übrig)</button>`; mo.firstChild.onclick = () => { CAT.shown += 192; renderCatalogue(); }; }
}
function openEntry(e) {
  const s = CAT.style, other = s === 'ps1' ? 'voxel' : 'ps1', th = thumbOf(e, s), tho = thumbOf(e, other), stm = e.styles || {};
  const rowSt = Object.entries(stm).map(([k, v]) => `<span class="st ${v}">${STYLE_NAMES[k] || k} : ${STLAB[v] || v}</span>`).join(' ');
  openModal(`<div class="cdet" style="display:grid;gap:14px"><div style="display:flex;gap:10px;align-items:flex-start"><div style="flex:1"><h2 style="margin:0">${esc(e.name)}</h2><div class="sub">${esc(e.category)} · ${esc(e.group || '')}</div></div><button class="btn sm" id="eClose">Schließen</button></div>
  ${(s !== 'console' && th && tho && stm[other]) ? `<div class="two"><figure><img alt="" src="catalogue/${esc(th)}">${STYLE_NAMES[s]}</figure><figure><img alt="" src="catalogue/${esc(tho)}">${STYLE_NAMES[other]}</figure></div>` : th ? `<img alt="" src="catalogue/${esc(th)}">` : `<div class="catimg" style="aspect-ratio:16/7">Bild ${STYLE_NAMES[s]} in Vorbereitung</div>`}
  ${e.audio ? `<audio controls autoplay src="catalogue/${esc(e.audio)}"></audio>` : ''}
  ${rowSt ? `<div class="chips">${rowSt}</div>` : ''}
  <div class="hint">${e.credit_required ? `<b>Lizenz ${esc(e.license || '')}.</b> In die Videobeschreibung zu übernehmen: ${esc(e.credit_text || '')}` : `Lizenz: ${esc(e.license || 'für dieses Studio geschaffen')}${e.source ? ' · ' + esc(e.source) : ''}`}</div>
  ${e.desc ? `<div class="hint">${esc(e.desc)}</div>` : ''}
  ${e.snippet ? `<div><div style="font-weight:600;font-size:13px;color:var(--ink-2);margin-bottom:6px">In eine Episode zu kopieren</div><pre id="eSnip">${esc(e.snippet)}</pre><div style="margin-top:8px"><button class="btn primary sm" id="eCopy">Zeile kopieren</button></div></div>` : ''}</div>`);
  $('#eClose').onclick = closeModal; const cp = $('#eCopy'); if (cp) cp.onclick = async () => { try { await navigator.clipboard.writeText(e.snippet); cp.textContent = 'Kopiert ✓'; } catch (_) { const r = document.createRange(); r.selectNode($('#eSnip')); getSelection().removeAllRanges(); getSelection().addRange(r); cp.textContent = 'Markiert: Strg+C'; } setTimeout(() => cp.textContent = 'Zeile kopieren', 1800); };
}

const PV = { clip: null, stale: true, busy: false };
async function enhanceDrawer(i, directed) {
  const d = $('#drawer'); if (!d || !S.p) return; const style = styleOf(S.p.meta || {}); let opts = null;
  try { opts = await api('GET', `api/shot_preview/options?style=${style}&slug=${encodeURIComponent(S.slug)}&index=${i}`); } catch (e) { return; }            
  if (S.sel !== i) return; PV.clip = null; PV.stale = true; PV.busy = false;
  const body = $('.body', d), foot = $('.foot', d), row = $('.field-row', d), cur0 = opts.current || {};
  const fill = (el, list, cur) => { if (!el) return; el.innerHTML = list.map(([v, n]) => `<option value="${esc(v)}" ${cur === v ? 'selected' : ''}>${esc(n)}</option>`).join(''); };   
  fill($('#fSize', d), opts.sizes, cur0.size); fill($('#fMove', d), opts.moves, cur0.move);
  $$('[data-actor]', d).forEach(sel => { const a = ((S.ep.shots[i].actors || []).filter(a => a && a.id))[+sel.dataset.actor]; fill(sel, opts.faces, a && a.face || 'neutral'); });
  if (row && opts.transitions && opts.transitions.length > 1 && !$('#fTrans', d)) {
    const cur = cur0.transition || opts.transitions[0][0];
    row.insertAdjacentHTML('afterend', `<label>Einblendung zu Beginn<select id="fTrans">${opts.transitions.map(([v, n]) => `<option value="${esc(v)}" ${cur === v ? 'selected' : ''}>${esc(n)}</option>`).join('')}</select></label>`);
  }
  const pvDiv = $('.preview', d); if (pvDiv) { pvDiv.classList.add('pvbox'); pvDiv.id = 'pvBox'; }
  body.insertAdjacentHTML('beforeend', `<div class="pvstate" id="pvState" aria-live="polite"><span>Wähle eine Einstellung und klicke auf „Ergebnis ansehen“: Du bestätigst nur, wenn es dir gefällt.</span></div><div class="progress" id="pvProg" style="display:none"><i></i></div>`);
  foot.innerHTML = `<button class="btn primary" id="pvGo" style="flex:1">▶ Ergebnis ansehen</button><button class="btn" id="pvOk" disabled>Bestätigen</button>`;
  foot.insertAdjacentHTML('afterend', `<div style="padding:0 20px 14px;text-align:right"><button class="linkbtn" id="pvSkip">Ohne Ansehen speichern</button></div>`);
  const markStale = () => { if (PV.clip) { PV.stale = true; $('#pvOk').disabled = true; $('#pvState').innerHTML = '<span class="pvstale">Die Einstellung hat sich geändert: Sieh dir das Ergebnis erneut an, bevor du bestätigst.</span>'; } };
  $$('select,textarea', body).forEach(el => el.addEventListener('change', markStale)); $$('textarea', body).forEach(el => el.addEventListener('input', markStale));
  $('#pvGo').onclick = () => previewShot(i, directed); $('#pvOk').onclick = () => validateShot(i, directed); $('#pvSkip').onclick = () => validateShot(i, directed);
}
function collectPatch(directed) {
  const d = $('#drawer'), p = {}; if (!directed) {
    p.camera = { shot: $('#fSize', d).value, move: $('#fMove', d).value };
    p.actors = $$('[data-actor]', d).map(s => { const a = ((S.ep.shots[S.sel].actors || []).filter(a => a && a.id))[+s.dataset.actor]; return a ? { id: a.id, face: s.value } : null; }).filter(Boolean);
  }
  const t = $('#fTrans', d); if (t) p.transition = t.value; const n = $('#fNote', d); if (n) p.note = n.value.trim(); return p;
}
async function previewShot(i, directed) {
  if (PV.busy) return; const go = $('#pvGo'), ok = $('#pvOk'), st = $('#pvState'), prog = $('#pvProg');
  PV.busy = true; go.disabled = true; ok.disabled = true; prog.style.display = 'block'; $('i', prog).style.width = '4%'; st.innerHTML = '<span>Das Studio bereitet diese Einstellung vor …</span>';
  try {
    await api('POST', `api/projects/${S.slug}/shot_preview`, { index: i, patch: collectPatch(directed), aspect: S.aspect || '9:16' });
    for (;;) {
      await new Promise(r => setTimeout(r, 900)); const j = await api('GET', `api/projects/${S.slug}/job`); if (S.sel !== i) { PV.busy = false; return; }
      $('i', prog).style.width = Math.max(4, Math.round((j.progress || 0) * 100)) + '%'; st.innerHTML = `<span>${esc(j.detail || j.name || 'Läuft …')}</span>`;
      if (j.state === 'done') { PV.clip = j.result && j.result.file; break; } if (j.state === 'error') throw new Error('Der Clip konnte nicht erstellt werden: Öffne das Protokoll, um den Grund zu sehen.');
    }
    const box = $('#pvBox'); box.innerHTML = `<video controls autoplay loop muted playsinline src="${urlOf(PV.clip)}"></video>`;
    PV.stale = false; ok.disabled = false; st.innerHTML = '<span>Hier ist das Ergebnis. <b>Gefällt es dir?</b> Bestätige, um es zu speichern, oder ändere die Einstellung und sieh es dir erneut an.</span>';
  } catch (e) { st.innerHTML = `<span class="pvstale">${esc(e.message)}</span>`; toast(e.message, true); }
  finally { PV.busy = false; go.disabled = false; prog.style.display = 'none'; go.textContent = '▶ Mit dieser Einstellung erneut ansehen'; }
}
async function validateShot(i, directed) {
  try {
    const r = await api('POST', `api/projects/${S.slug}/shot_apply`, { index: i, patch: collectPatch(directed) }); (r.warnings || []).slice(0, 2).forEach(w => toast(String(w), true));
    toast('Einstellung gespeichert'); await openProject(S.slug, true); openDrawer(i);
  } catch (e) { toast(e.message, true); }
}

window.openCatalogue = openCatalogue; window.renderCatalogue = renderCatalogue; window.decorateList = decorateList; window.enhanceDrawer = enhanceDrawer; window.openSpace = openSpace;
const btn = $('#catBtn'); if (btn) btn.onclick = openCatalogue;
loadStorage(); setInterval(() => { if (!document.hidden) loadStorage(); }, 60000);
if (location.hash === '#catalogue') openCatalogue();
})();
