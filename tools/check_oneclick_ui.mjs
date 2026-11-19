// Frontend check of the one-click panel: loads the real index.html script in a stub DOM and asserts that the
// step list, the button label, the refusals and the brief form say exactly what the backend answered.
// No browser, no network, no API:   node tools/check_oneclick_ui.mjs
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(ROOT, 'hstudio/web/static/index.html'), 'utf8');
const src = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).join('\n');

// ---- a DOM stub that remembers its elements, so we can read what the panel wrote
const ELS = new Map();
function mkEl(id) {
  const e = {
    id, innerHTML: '', textContent: '', className: '', value: '', disabled: false, style: {}, dataset: {}, options: [],
    classList: { _s: new Set(), add(c) { this._s.add(c) }, remove(c) { this._s.delete(c) }, toggle(c, v) { v === undefined ? (this._s.has(c) ? this._s.delete(c) : this._s.add(c)) : (v ? this._s.add(c) : this._s.delete(c)) }, contains(c) { return this._s.has(c) } },
    addEventListener() {}, appendChild() {}, remove() {}, select() {}, add(o) { this.options.push(o) },
  };
  ELS.set(id, e); return e;
}
const el = id => ELS.get(id) || mkEl(id);
const doc = { getElementById: el, querySelector: () => mkEl('_q'), querySelectorAll: () => [], createElement: () => mkEl('_c'),
              addEventListener() {}, body: { appendChild() {} }, execCommand() {} };

// ---- the backend answers we control
let PLAN = null, POSTED = [], PROJECT = null;
const STAGES = [['script', 'Script'], ['voice', 'Voix'], ['align', 'Calage voix / texte'], ['direct', 'Mise en scène'],
                ['mix', 'Mixage du son'], ['render', 'Rendu vidéo'], ['qc', 'Contrôle qualité'],
                ['metadata', 'Titres et packs'], ['thumbnail', 'Miniatures']];
function plan({ done = [], failed = null, problems = [], error = null, renders = { '9:16': [] }, forced = [] }) {
  const stages = STAGES.map(([key, label]) => ({
    key, label, done: done.includes(key), forced: forced.includes(key),
    state: done.includes(key) ? 'done' : (failed === key ? 'error' : 'todo'), at: null, detail: '',
  }));
  const todo = stages.filter(s => (!s.done || s.forced) && s.key !== 'script');
  return { aspects: ['9:16'], voice_mode: 'draft', voice_label: 'Voix de brouillon (gratuite, locale)', stages,
           next: todo.length ? todo[0].key : null, complete: !todo.length, failed, error, updated: null, renders, problems };
}

async function fetchStub(url, opt = {}) {
  const m = (opt && opt.method) || 'GET';
  if (m !== 'GET') POSTED.push({ url, method: m, body: JSON.parse(opt.body || '{}') });
  let data = {};
  if (url.includes('/oneclick')) data = PLAN;
  else if (url.includes('/api/story/options')) data = { genres: ['horror', 'mystery'], voice_modes: ['voice'], engines: ['auto'], voice_sources: {}, qualities: ['standard'], aspects: ['9:16'], stages: STAGES.map(([k, l]) => ({ key: k, label: l })) };
  else if (url.includes('/api/places')) data = ['attic', 'cave'];
  else if (url.includes('/api/characters') || url.includes('/api/demos') || url.includes('/api/projects?') || url.endsWith('/api/projects')) data = [];
  else if (url.includes('/api/story/project')) data = PROJECT;
  else if (url.includes('/api/projects/')) data = { slug: 'x', meta: {}, status: { renders: [] }, lines: [], previews: [], qc: {}, warnings: [] };
  return { ok: true, json: async () => data, text: async () => JSON.stringify(data) };
}

const load = new Function('document', 'window', 'navigator', 'fetch', 'setInterval', 'setTimeout', 'clearInterval', 'clearTimeout',
  'location', 'isSecureContext', 'Option', 'alert', 'confirm', 'Promise',
  src + '\n;return { loadOneClick, ocOpts, runOneClick, forceOneClick, runBrief, loadBriefOptions, brEngine, ocAspects, setCur: s => { cur = s } };');

let ALERTED = null, CONFIRM = true;
const ui = load(doc, { isSecureContext: true, addEventListener() {} }, { clipboard: { writeText: async () => {} } },
                fetchStub, () => 0, f => 0, () => {}, () => {}, { href: '' }, true,
                function Option(t, v) { return { t, v } }, m => { ALERTED = m }, () => CONFIRM, Promise);

const FAIL = [];
const check = (n, ok, d = '') => { console.log(`${ok ? 'OK   ' : 'ÉCHEC'} ${n}` + (d && !ok ? `  (${d})` : '')); if (!ok) FAIL.push(n) };

ui.setCur('demo');
el('oc-quality').value = 'standard';

// ---- a fresh project from a brief: the plan is already in place, the voice is next
PLAN = plan({ done: ['script', 'direct'] });
await ui.loadOneClick();
let steps = el('oc-steps').innerHTML;
check('les 9 étapes sont affichées, dans l\'ordre', STAGES.every(([, l], i) => steps.indexOf(`${i + 1}. ${l}`) >= 0));
check('les étapes faites sont marquées faites', /class="st done"[^>]*>1\. Script ✓/.test(steps) && steps.includes('4. Mise en scène ✓'));
check('l\'étape suivante est désignée', steps.includes('class="st next"') && steps.includes('2. Voix →'));
check('le bouton annonce ce qui reste', el('oc-go').textContent === '▶ Fabriquer (7 étapes)', el('oc-go').textContent);
check('le bouton est actif', el('oc-go').disabled === false);
check('la voix et les rendus sont dits', el('oc-voice').textContent.includes('brouillon') && el('oc-voice').textContent.includes('9:16 : —'), el('oc-voice').textContent);
check('aucun avertissement sans problème', el('oc-problems').innerHTML === '');

// ---- everything done: nothing to redo, the button cannot start a run
PLAN = plan({ done: STAGES.map(([k]) => k), renders: { '9:16': ['x_short_9x16.mp4'] } });
await ui.loadOneClick();
check('parcours complet : le bouton le dit', el('oc-go').textContent === '✓ Tout est déjà fait', el('oc-go').textContent);
check('parcours complet : le bouton est désactivé', el('oc-go').disabled === true);
check('parcours complet : le rendu est nommé', el('oc-voice').textContent.includes('x_short_9x16.mp4'));

// ---- a failed stage: the panel points at it and offers to resume there
PLAN = plan({ done: ['script', 'voice', 'align', 'direct'], failed: 'mix', error: 'Mixage du son : panne' });
await ui.loadOneClick();
steps = el('oc-steps').innerHTML;
check('l\'étape fautive est marquée en erreur', steps.includes('class="st error"') && steps.includes('5. Mixage du son ✗'));
check('le bouton propose de reprendre à l\'étape fautive', el('oc-go').textContent === '▶ Reprendre à : Mixage du son', el('oc-go').textContent);
check('l\'erreur est affichée en français', el('oc-problems').innerHTML.includes('Mixage du son : panne'));
check('les étapes amont restent marquées faites', steps.includes('2. Voix ✓') && steps.includes('4. Mise en scène ✓'));

// ---- a blocking problem: no run is possible, and the reason is shown
PLAN = plan({ done: ['script'], problems: ['Le script est vide : écris-le (ou pars d\'un brief) avant de lancer le parcours.'] });
await ui.loadOneClick();
check('un problème bloquant désactive le bouton', el('oc-go').disabled === true);
check('le problème bloquant est affiché', el('oc-problems').innerHTML.includes('script est vide'));
PLAN = plan({ done: ['script', 'direct'], problems: ['Metteur en scène « claude » demandé sans clé : le parcours basculera sur la mise en scène automatique du studio (gratuite, hors ligne).'] });
await ui.loadOneClick();
check('un simple avertissement ne bloque pas', el('oc-go').disabled === false);
check('l\'avertissement est quand même affiché', el('oc-problems').innerHTML.includes('Metteur en scène'));

// ---- the options really sent to the backend
check('les options par défaut : un format, la qualité choisie, aucun forçage',
  JSON.stringify(ui.ocOpts()) === JSON.stringify({ aspects: ['9:16'], quality: 'standard', force: [] }), JSON.stringify(ui.ocOpts()));
POSTED = [];
el('pv-script').value = 'Une phrase.';
await ui.runOneClick();
const started = POSTED.find(p => p.url.includes('/run/oneclick'));
check('« Fabriquer » enregistre le script puis lance le parcours',
  POSTED.some(p => p.url.includes('/script') && p.method === 'PUT') && !!started, JSON.stringify(POSTED.map(p => p.url)));
check('« Fabriquer » ne force aucune étape', started && started.body.force.length === 0, JSON.stringify(started && started.body));
POSTED = [];
await ui.forceOneClick();
const forced = POSTED.find(p => p.url.includes('/run/oneclick'));
check('« Refaire » force exactement le rendu et le contrôle qualité',
  forced && JSON.stringify(forced.body.force) === JSON.stringify(['render', 'qc']), JSON.stringify(forced && forced.body));
POSTED = []; CONFIRM = false;
await ui.forceOneClick();
check('« Refaire » demande confirmation avant d\'écraser un MP4', POSTED.length === 0, JSON.stringify(POSTED));
CONFIRM = true;

// ---- the brief form
await ui.loadBriefOptions();
check('les genres viennent du backend, traduits', el('br-genre').options.map(o => o.v).join(',') === 'horror,mystery', JSON.stringify(el('br-genre').options));
check('le genre est affiché en français', el('br-genre').options[0].t === 'horreur', el('br-genre').options[0].t);
PROJECT = { slug: 'brief_1', style: 'pixel3d', beats: 9, choices: ['A', 'B'], seconds: 31.2, generator: 'mock', place: 'cave', summary: 's', plan: PLAN, started: true };
POSTED = [];
Object.assign(el('br-genre'), { value: 'horror' }); Object.assign(el('br-duration'), { value: '45' });
Object.assign(el('br-voicemode'), { value: 'voice' }); Object.assign(el('br-engine'), { value: 'pixel3d' });
Object.assign(el('br-hero'), { value: 'Toi' }); Object.assign(el('br-other'), { value: 'Léa' });
Object.assign(el('br-place'), { value: 'cave' }); Object.assign(el('br-premise'), { value: 'un ascenseur' });
Object.assign(el('br-series'), { value: 'Essai' }); Object.assign(el('br-part'), { value: 'PARTIE 2' });
Object.assign(el('br-choices'), { value: '3' }); Object.assign(el('br-prevchoice'), { value: 'A' });
Object.assign(el('br-voice'), { value: 'draft' }); Object.assign(el('br-provider'), { value: 'mock' });
Object.assign(el('br-quality'), { value: 'standard' }); Object.assign(el('br-name'), { value: 'Mon épisode' });
await ui.runBrief(true);
const sent = POSTED.find(p => p.url.includes('/api/story/project'));
check('le brief envoyé reprend tous les champs', sent && sent.body.brief.genre === 'horror' && sent.body.brief.n_choices === 3
  && sent.body.brief.series === 'Essai' && sent.body.brief.previous_choice === 'A' && sent.body.brief.place === 'cave', JSON.stringify(sent && sent.body.brief));
check('la durée part en nombre, pas en texte', sent && sent.body.brief.duration_s === 45, typeof (sent && sent.body.brief.duration_s));
check('la source de la voix et le provider sont envoyés', sent && sent.body.voice_mode === 'draft' && sent.body.provider === 'mock');
check('« Créer et fabriquer » demande bien le lancement', sent && sent.body.run === true && sent.body.opts.aspects.join(',') === '9:16');
check('le résultat du brief est résumé à l\'écran',
  el('br-out').innerHTML.includes('brief_1') && el('br-out').innerHTML.includes('choix A / B') && el('br-out').innerHTML.includes('mock'), el('br-out').innerHTML.slice(0, 160));
check('le gabarit de test est annoncé comme tel dans la page',
  html.includes('gabarit déterministe de test') && html.includes('il n\'invente pas d\'histoire'));
POSTED = [];
await ui.runBrief(false);
const only = POSTED.find(p => p.url.includes('/api/story/project'));
check('« Créer seulement » ne lance rien', only && only.body.run === false, JSON.stringify(only && only.body.run));
Object.assign(el('br-engine'), { value: 'console' });
await ui.runBrief(false);
const con = POSTED.filter(p => p.url.includes('/api/story/project')).pop();
check('en CONSOLE 2D aucun lieu voxel n\'est envoyé', con && con.body.brief.place === '', JSON.stringify(con && con.body.brief.place));

console.log('\n' + (FAIL.length ? `${FAIL.length} ÉCHEC(S) : ` + FAIL.join(', ') : 'Tout est OK.'));
if (FAIL.length) process.exit(1);
