/* Studio vidéo : ajouts de l'interface (chargé par studio.html).
   1. Catalogue : tout ce que le studio sait dessiner, avec le choix du style (PS1 / VOXEL / Console 2D) ; PS1 et VOXEL montrent les MÊMES éléments, chacun peint dans son style.
   2. Espace disque : taille de chaque vidéo, « libérer l'espace », suppression définitive, corbeille.
   3. Tiroir d'un plan : générer le résultat (un court clip) AVANT de valider un changement (cadrage, mouvement, expression, transition).
   Utilise les globales de studio.html : S, $, $$, esc, api, toast, setRail, closeDrawer, renderList, renderMain, openProject, urlOf, STYLES, styleOf. */
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

/* ------------------------------------------------------------------ utilitaires */
const fmt = b => { b = +b || 0; if (b >= 1073741824) return (b / 1073741824).toFixed(b >= 10737418240 ? 0 : 1).replace('.', ',') + ' Go'; if (b >= 1048576) return Math.round(b / 1048576) + ' Mo'; if (b >= 1024) return Math.round(b / 1024) + ' Ko'; return b + ' o'; };
const openModal = html => { $('#modalBody').innerHTML = html; $('#modal').classList.add('open'); };
const closeModal = () => $('#modal').classList.remove('open');
$('#modal').addEventListener('click', e => { if (e.target.id === 'modal') closeModal(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape' && $('#modal').classList.contains('open')) closeModal(); });
const STYLE_NAMES = { ps1: 'PS1', voxel: 'VOXEL', console: 'Console 2D' };

/* ------------------------------------------------------------------ 2. espace disque */
async function loadStorage(force) {
  try { S.storage = await api('GET', 'api/storage' + (force ? '?refresh=true' : '')); } catch (e) { S.storage = S.storage || null; }
  decorateList();
}
function decorateList() {
  const list = $('#list'); if (!list) return; const sz = (S.storage && S.storage.projects) || {};
  $$('.item', list).forEach(b => {
    if (b.parentElement.classList.contains('itemrow')) return;
    const slug = b.dataset.slug, row = document.createElement('div'); row.className = 'itemrow'; b.replaceWith(row); row.append(b);
    const del = document.createElement('button'); del.className = 'itemdel'; del.title = 'Supprimer ou libérer de l\'espace'; del.setAttribute('aria-label', 'Supprimer cette vidéo ou libérer de l\'espace'); del.textContent = '🗑'; del.onclick = e => { e.stopPropagation(); openDelete(slug); }; row.append(del);
    const s = sz[slug], small = $('small', b); if (s && small && !$('.sizetag', small)) small.insertAdjacentHTML('beforeend', ` · <span class="sizetag">${fmt(s.total)}</span>`);
  });
  const foot = $('#foot');
  if (foot && S.storage) foot.innerHTML = `${S.projects.length} vidéo${S.projects.length > 1 ? 's' : ''} · ${fmt(S.storage.total_bytes)} <button class="linkbtn" id="spaceBtn">Gérer l'espace</button>`, $('#spaceBtn').onclick = openSpace;
}
function projName(slug) { const p = (S.projects || []).find(x => x.slug === slug); return (p && (p.name || p.slug)) || slug; }
async function openDelete(slug) {
  await loadStorage(true); const s = ((S.storage || {}).projects || {})[slug] || { total: 0, generated: 0 }, name = projName(slug), keep = Math.max(0, s.total - s.generated);
  openModal(`<div><h2 style="margin:0 0 4px">Supprimer « ${esc(name)} »</h2><div class="sub">Ce projet occupe <b>${fmt(s.total)}</b> sur ton disque.</div></div>
  <div class="bar" aria-hidden="true"><i style="width:${s.total ? Math.round(100 * s.generated / s.total) : 0}%"></i></div>
  <div class="hint" style="margin-top:-8px">${fmt(s.generated)} sont des fichiers que le studio sait refaire (vidéo, aperçus, fichiers de travail) ; ${fmt(keep)} sont à toi (script, voix, plans).</div>
  <div style="display:grid;gap:10px">
    <button class="btn soft" id="dClean" style="text-align:left"><b>Libérer l'espace · ${fmt(s.generated)}</b><br><span class="hint">Supprime la vidéo, les aperçus et les fichiers de travail. Tu gardes ton script, ta voix et tes plans : tu pourras refaire la vidéo.</span></button>
    <button class="btn danger" id="dDel" style="text-align:left"><b>Supprimer entièrement · ${fmt(s.total)}</b><br><span style="font-weight:400;font-size:13px">Efface tout le projet. Impossible à annuler.</span></button>
    <button class="linkbtn" id="dTrash" style="justify-self:start">Mettre à la corbeille à la place (récupérable, ne libère pas d'espace)</button></div>
  <div style="display:flex;justify-content:flex-end"><button class="btn" id="dNo">Annuler</button></div>`);
  $('#dNo').onclick = closeModal;
  if (s.generated < 1024) { const c = $('#dClean'); c.disabled = true; c.style.opacity = .55; c.innerHTML = '<b>Rien à libérer</b><br><span class="hint">Ce projet ne contient aucune vidéo ni aucun aperçu à effacer.</span>'; } else $('#dClean').onclick = () => doRemove(slug, 'clean');
  $('#dTrash').onclick = () => doRemove(slug, 'trash');
  $('#dDel').onclick = () => { const b = $('#dDel'); if (b.dataset.sure) return doRemove(slug, 'delete'); b.dataset.sure = '1'; b.innerHTML = '<b>Oui, supprimer pour de bon</b><br><span style="font-weight:400;font-size:13px">Dernière confirmation : « ' + esc(name) + ' » sera effacé définitivement.</span>'; };
}
async function doRemove(slug, mode) {
  try {
    const r = mode === 'clean' ? await api('POST', `api/projects/${slug}/clean`) : await api('DELETE', `api/projects/${slug}${mode === 'delete' ? '?definitif=true' : ''}`);
    closeModal(); toast(mode === 'clean' ? `Espace libéré : ${fmt(r.freed)}` : mode === 'delete' ? `Supprimé · ${fmt(r.freed)} libérés` : 'Mis à la corbeille');
    if (mode !== 'clean' && S.slug === slug) { S.slug = null; S.p = null; S.ep = null; closeDrawer(); }
    S.projects = await api('GET', 'api/projects'); renderList(); await loadStorage(true);
    if (mode === 'clean' && S.slug === slug) await openProject(slug, true); else renderMain();
  } catch (e) { toast(e.message, true); }
}
async function openSpace() {
  await loadStorage(true); const st = S.storage || { projects: {}, trash: [], trash_bytes: 0, total_bytes: 0 };
  const rows = Object.entries(st.projects).sort((a, b) => b[1].total - a[1].total), max = rows.length ? rows[0][1].total || 1 : 1;
  openModal(`<div><h2 style="margin:0 0 4px">Espace disque</h2><div class="sub">${rows.length} projets · <b>${fmt(st.total_bytes)}</b>${st.trash_bytes ? ` · corbeille ${fmt(st.trash_bytes)}` : ''}</div></div>
  <ul class="spacelist">${rows.map(([slug, s]) => `<li><div class="n"><b>${esc(projName(slug))}</b><div class="bar"><i style="width:${Math.max(2, Math.round(100 * s.total / max))}%"></i></div></div><span class="sizetag">${fmt(s.total)}</span><button class="btn sm" data-del="${esc(slug)}">Supprimer…</button></li>`).join('') || '<li class="hint">Aucun projet.</li>'}</ul>
  ${st.trash.length ? `<div class="panel" style="padding:14px"><b>Corbeille · ${fmt(st.trash_bytes)}</b><ul class="spacelist" style="margin-top:8px">${st.trash.map(t => `<li><div class="n"><b>${esc(t.slug)}</b></div><span class="sizetag">${fmt(t.size)}</span><button class="btn sm" data-restore="${esc(t.name)}">Restaurer</button></li>`).join('')}</ul><div style="margin-top:10px"><button class="btn danger sm" id="trEmpty">Vider la corbeille et libérer ${fmt(st.trash_bytes)}</button></div></div>` : ''}
  <div style="display:flex;justify-content:flex-end"><button class="btn" id="spClose">Fermer</button></div>`);
  $('#spClose').onclick = closeModal; $$('[data-del]', $('#modalBody')).forEach(b => b.onclick = () => openDelete(b.dataset.del));
  $$('[data-restore]', $('#modalBody')).forEach(b => b.onclick = async () => { try { await api('POST', `api/trash/${encodeURIComponent(b.dataset.restore)}/restore`); toast('Projet restauré'); S.projects = await api('GET', 'api/projects'); renderList(); openSpace(); } catch (e) { toast(e.message, true); } });
  const te = $('#trEmpty'); if (te) te.onclick = async () => { try { const r = await api('DELETE', 'api/trash'); toast(`Corbeille vidée · ${fmt(r.freed)} libérés`); await loadStorage(true); openSpace(); } catch (e) { toast(e.message, true); } };
}

/* ------------------------------------------------------------------ 1. catalogue */
const CAT = { all: null, style: null, cat: '', q: '', ref: false, shown: 96 };
const statusOf = (e, s) => (e.styles && e.styles[s]) || (e.styles ? null : (s === 'console' ? null : 'native'));
const inStyle = (e, s) => s === 'console' ? !!(e.styles && e.styles.console) || e.category === 'Console 2D' : (e.category !== 'Console 2D' && !!statusOf(e, s));
const thumbOf = (e, s) => (e.thumbs && e.thumbs[s]) || (s === 'voxel' ? e.thumb : null) || (e.category === 'Sons' ? e.thumb : null);
const STLAB = { native: 'natif', converted: 'converti', approx: 'approché' };
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
  const rule = s === 'console' ? 'Le style Console 2D a son propre catalogue : pixel art plat façon console.' : 'PS1 et VOXEL présentent exactement les mêmes éléments : seule la manière de les dessiner change. Une pastille dit si l\'élément est dessiné « natif » dans ce style, « converti » depuis l\'autre, ou « approché ».';
  m.innerHTML = `<div class="top"><div class="title-row"><div><h1>Catalogue</h1><div class="sub">Tout ce que le studio sait dessiner · ${all.length.toLocaleString('fr-FR')} éléments en style ${STYLE_NAMES[s]}</div></div><span class="spacer"></span>
      <div class="seg" role="group" aria-label="Style du catalogue">${STYLES.map(x => `<button data-cs="${x.id}" class="${x.id === s ? 'on' : ''}" title="${esc(x.desc)}">${x.name}</button>`).join('')}</div></div>
    <div class="rule" role="note"><span aria-hidden="true">ℹ️</span><span>${rule}</span></div>
    <div class="catbar"><input type="search" id="cq" placeholder="Chercher : zombie, lit, église, lampe, squelette…" value="${esc(CAT.q)}" autocomplete="off" aria-label="Chercher dans le catalogue">${refN ? `<button class="btn ${CAT.ref ? 'soft' : ''} sm" id="cref" title="Les modèles importés servent d'inspiration : ils ne sont pas utilisés tels quels dans les films.">${CAT.ref ? 'Masquer' : 'Afficher'} les références d'inspiration (${refN})</button>` : ''}</div>
    <div class="catchips" role="group" aria-label="Catégories"><button class="cchip ${CAT.cat ? '' : 'on'}" data-cc="">Tout<small>${pool.length}</small></button>${cats.map(([c, n]) => `<button class="cchip ${CAT.cat === c ? 'on' : ''}" data-cc="${esc(c)}">${esc(c)}<small>${n}</small></button>`).join('')}</div></div>
    <div class="content"><div class="catgrid" id="cgrid"></div><div style="text-align:center;margin-top:20px" id="cmore"></div></div>`;
  $$('[data-cs]', m).forEach(b => b.onclick = () => { CAT.style = b.dataset.cs; CAT.cat = ''; CAT.shown = 96; renderCatalogue(); });
  $$('[data-cc]', m).forEach(b => b.onclick = () => { CAT.cat = b.dataset.cc; CAT.shown = 96; renderCatalogue(); });
  const cq = $('#cq'); let t; cq.oninput = () => { clearTimeout(t); t = setTimeout(() => { CAT.q = cq.value; CAT.shown = 96; const pos = cq.selectionStart; renderCatalogue(); const n = $('#cq'); n.focus(); n.setSelectionRange(pos, pos); }, 200); };
  const cr = $('#cref'); if (cr) cr.onclick = () => { CAT.ref = !CAT.ref; renderCatalogue(); };
  const g = $('#cgrid'), vis = list.slice(0, CAT.shown);
  if (!CAT.all || !CAT.all.length) g.innerHTML = '<div class="empty" style="grid-column:1/-1"><div class="art">📚</div><h2>Catalogue vide</h2><p>Lance « python -m hstudio.catalogue build » dans le dossier du studio.</p></div>';
  else if (!list.length) g.innerHTML = '<div class="empty" style="grid-column:1/-1"><div class="art">🔎</div><h2>Rien ne correspond</h2><p>Essaie un autre mot ou une autre catégorie.</p></div>';
  g.innerHTML = g.innerHTML || vis.map((e, i) => { const th = thumbOf(e, s), st = statusOf(e, s) || (s === 'console' ? 'native' : null);
    return `<button class="catcard" data-i="${i}" aria-label="${esc(e.name)}"><div class="catimg">${th ? `<img loading="lazy" alt="" src="catalogue/${esc(th)}">` : `Image ${STYLE_NAMES[s]} en préparation`}</div><div class="cm"><b title="${esc(e.name)}">${esc(e.name)}</b><span class="g">${esc(e.group || e.category)}</span><div class="chips">${st ? `<span class="st ${st}">${STLAB[st] || st}</span>` : ''}${e.credit_required ? '<span class="chip warn" title="Crédit à publier">crédit</span>' : ''}</div></div></button>`; }).join('');
  $$('.catcard', g).forEach(b => b.onclick = () => openEntry(vis[+b.dataset.i]));
  const mo = $('#cmore'); if (list.length > CAT.shown) { mo.innerHTML = `<button class="btn">Voir plus (${list.length - CAT.shown} restants)</button>`; mo.firstChild.onclick = () => { CAT.shown += 192; renderCatalogue(); }; }
}
function openEntry(e) {
  const s = CAT.style, other = s === 'ps1' ? 'voxel' : 'ps1', th = thumbOf(e, s), tho = thumbOf(e, other), stm = e.styles || {};
  const rowSt = Object.entries(stm).map(([k, v]) => `<span class="st ${v}">${STYLE_NAMES[k] || k} : ${STLAB[v] || v}</span>`).join(' ');
  openModal(`<div class="cdet" style="display:grid;gap:14px"><div style="display:flex;gap:10px;align-items:flex-start"><div style="flex:1"><h2 style="margin:0">${esc(e.name)}</h2><div class="sub">${esc(e.category)} · ${esc(e.group || '')}</div></div><button class="btn sm" id="eClose">Fermer</button></div>
  ${(s !== 'console' && th && tho && stm[other]) ? `<div class="two"><figure><img alt="" src="catalogue/${esc(th)}">${STYLE_NAMES[s]}</figure><figure><img alt="" src="catalogue/${esc(tho)}">${STYLE_NAMES[other]}</figure></div>` : th ? `<img alt="" src="catalogue/${esc(th)}">` : `<div class="catimg" style="aspect-ratio:16/7">Image ${STYLE_NAMES[s]} en préparation</div>`}
  ${e.audio ? `<audio controls autoplay src="catalogue/${esc(e.audio)}"></audio>` : ''}
  ${rowSt ? `<div class="chips">${rowSt}</div>` : ''}
  <div class="hint">${e.credit_required ? `<b>Licence ${esc(e.license || '')}.</b> À mettre dans la description de la vidéo : ${esc(e.credit_text || '')}` : `Licence : ${esc(e.license || 'créé pour ce studio')}${e.source ? ' · ' + esc(e.source) : ''}`}</div>
  ${e.desc ? `<div class="hint">${esc(e.desc)}</div>` : ''}
  ${e.snippet ? `<div><div style="font-weight:600;font-size:13px;color:var(--ink-2);margin-bottom:6px">À copier dans un épisode</div><pre id="eSnip">${esc(e.snippet)}</pre><div style="margin-top:8px"><button class="btn primary sm" id="eCopy">Copier la ligne</button></div></div>` : ''}</div>`);
  $('#eClose').onclick = closeModal; const cp = $('#eCopy'); if (cp) cp.onclick = async () => { try { await navigator.clipboard.writeText(e.snippet); cp.textContent = 'Copié ✓'; } catch (_) { const r = document.createRange(); r.selectNode($('#eSnip')); getSelection().removeAllRanges(); getSelection().addRange(r); cp.textContent = 'Sélectionné : Ctrl+C'; } setTimeout(() => cp.textContent = 'Copier la ligne', 1800); };
}

/* ------------------------------------------------------------------ 3. tiroir d'un plan : voir le résultat avant de valider */
const PV = { clip: null, stale: true, busy: false };
async function enhanceDrawer(i, directed) {
  const d = $('#drawer'); if (!d || !S.p) return; const style = styleOf(S.p.meta || {}); let opts = null;
  try { opts = await api('GET', `api/shot_preview/options?style=${style}&slug=${encodeURIComponent(S.slug)}&index=${i}`); } catch (e) { return; }            // module d'aperçu absent : on garde l'ancien bouton
  if (S.sel !== i) return; PV.clip = null; PV.stale = true; PV.busy = false;
  const body = $('.body', d), foot = $('.foot', d), row = $('.field-row', d), cur0 = opts.current || {};
  const fill = (el, list, cur) => { if (!el) return; el.innerHTML = list.map(([v, n]) => `<option value="${esc(v)}" ${cur === v ? 'selected' : ''}>${esc(n)}</option>`).join(''); };   // les listes du style (Console 2D n'a ni les mêmes cadrages ni les mêmes mouvements)
  fill($('#fSize', d), opts.sizes, cur0.size); fill($('#fMove', d), opts.moves, cur0.move);
  $$('[data-actor]', d).forEach(sel => { const a = ((S.ep.shots[i].actors || []).filter(a => a && a.id))[+sel.dataset.actor]; fill(sel, opts.faces, a && a.face || 'neutral'); });
  if (row && opts.transitions && opts.transitions.length > 1 && !$('#fTrans', d)) {
    const cur = cur0.transition || opts.transitions[0][0];
    row.insertAdjacentHTML('afterend', `<label>Transition d'entrée<select id="fTrans">${opts.transitions.map(([v, n]) => `<option value="${esc(v)}" ${cur === v ? 'selected' : ''}>${esc(n)}</option>`).join('')}</select></label>`);
  }
  const pvDiv = $('.preview', d); if (pvDiv) { pvDiv.classList.add('pvbox'); pvDiv.id = 'pvBox'; }
  body.insertAdjacentHTML('beforeend', `<div class="pvstate" id="pvState" aria-live="polite"><span>Choisis un réglage, puis clique sur « Voir le résultat » : tu valides seulement si ça te plaît.</span></div><div class="progress" id="pvProg" style="display:none"><i></i></div>`);
  foot.innerHTML = `<button class="btn primary" id="pvGo" style="flex:1">▶ Voir le résultat</button><button class="btn" id="pvOk" disabled>Valider</button>`;
  foot.insertAdjacentHTML('afterend', `<div style="padding:0 20px 14px;text-align:right"><button class="linkbtn" id="pvSkip">Enregistrer sans regarder</button></div>`);
  const markStale = () => { if (PV.clip) { PV.stale = true; $('#pvOk').disabled = true; $('#pvState').innerHTML = '<span class="pvstale">Le réglage a changé : regarde de nouveau le résultat avant de valider.</span>'; } };
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
  PV.busy = true; go.disabled = true; ok.disabled = true; prog.style.display = 'block'; $('i', prog).style.width = '4%'; st.innerHTML = '<span>Le studio prépare ce plan…</span>';
  try {
    await api('POST', `api/projects/${S.slug}/shot_preview`, { index: i, patch: collectPatch(directed), aspect: S.aspect || '9:16' });
    for (;;) {
      await new Promise(r => setTimeout(r, 900)); const j = await api('GET', `api/projects/${S.slug}/job`); if (S.sel !== i) { PV.busy = false; return; }
      $('i', prog).style.width = Math.max(4, Math.round((j.progress || 0) * 100)) + '%'; st.innerHTML = `<span>${esc(j.detail || j.name || 'En cours…')}</span>`;
      if (j.state === 'done') { PV.clip = j.result && j.result.file; break; } if (j.state === 'error') throw new Error('Le clip n\'a pas pu être fait : ouvre le Journal pour voir pourquoi.');
    }
    const box = $('#pvBox'); box.innerHTML = `<video controls autoplay loop muted playsinline src="${urlOf(PV.clip)}"></video>`;
    PV.stale = false; ok.disabled = false; st.innerHTML = '<span>Voici le résultat. <b>Il te plaît ?</b> Valide pour l\'enregistrer, ou change le réglage et regarde de nouveau.</span>';
  } catch (e) { st.innerHTML = `<span class="pvstale">${esc(e.message)}</span>`; toast(e.message, true); }
  finally { PV.busy = false; go.disabled = false; prog.style.display = 'none'; go.textContent = '▶ Revoir avec ce réglage'; }
}
async function validateShot(i, directed) {
  try {
    const r = await api('POST', `api/projects/${S.slug}/shot_apply`, { index: i, patch: collectPatch(directed) }); (r.warnings || []).slice(0, 2).forEach(w => toast(String(w), true));
    toast('Plan enregistré'); await openProject(S.slug, true); openDrawer(i);
  } catch (e) { toast(e.message, true); }
}

/* ------------------------------------------------------------------ accroches avec studio.html */
window.openCatalogue = openCatalogue; window.renderCatalogue = renderCatalogue; window.decorateList = decorateList; window.enhanceDrawer = enhanceDrawer; window.openSpace = openSpace;
const btn = $('#catBtn'); if (btn) btn.onclick = openCatalogue;
loadStorage(); setInterval(() => { if (!document.hidden) loadStorage(); }, 60000);
if (location.hash === '#catalogue') openCatalogue();
})();
