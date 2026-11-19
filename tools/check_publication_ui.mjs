// Frontend check of the publication panel: loads the real index.html script in a stub DOM and asserts that
// pubHtml() renders the two platform packs and that the copy controls resolve to the right text.
// No browser, no network, no API:   node tools/check_publication_ui.mjs
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(ROOT, 'hstudio/web/static/index.html'), 'utf8');
const src = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).join('\n');

const el = () => ({ innerHTML: '', textContent: '', className: '', style: {}, dataset: {}, classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
                    addEventListener() {}, appendChild() {}, remove() {}, select() {}, add() {}, value: '', options: [] });
const doc = { getElementById: el, querySelector: el, querySelectorAll: () => [], createElement: el,
              addEventListener() {}, body: { appendChild() {} }, execCommand() {} };
let copied = null;
const nav = { clipboard: { writeText: t => { copied = t; return Promise.resolve() } } };
const api = new Function('document', 'window', 'navigator', 'fetch', 'setInterval', 'setTimeout', 'location', 'isSecureContext', 'Option', 'alert', 'confirm',
  src + '\n;return { pubHtml, pubField, pubSheet, cpf, cpFlash, getPUB: () => PUB };');
const ui = api(doc, { isSecureContext: true, addEventListener() {} }, nav, () => Promise.resolve({ json: () => ({}) }),
               () => 0, f => 0, { href: '' }, true, function Option(t, v) { return { t, v } }, () => {}, () => true);

const FAIL = [];
const check = (n, ok, d = '') => { console.log(`${ok ? 'OK   ' : 'ÉCHEC'} ${n}` + (d && !ok ? `  (${d})` : '')); if (!ok) FAIL.push(n) };
const pack = JSON.parse(readFileSync(join(ROOT, 'tests/fixtures/publication_pack.json'), 'utf8')).platforms;

const h = ui.pubHtml(pack);
check('panneau rendu pour un épisode interactif', h.includes('YouTube Shorts') && h.includes('TikTok'));
check('titre YouTube affiché', h.includes(pack.youtube_shorts.title.replace(/&/g, '&amp;')), pack.youtube_shorts.title);
check('légende TikTok affichée', h.includes('tiktok.caption'));
check('vote et options affichés', h.includes(pack.vote_line) && pack.choices.every(c => h.includes(c.text)));
check('hashtags des deux plateformes séparés', h.includes('youtube_shorts.hashtags') && h.includes('tiktok.hashtags'));
check('boutons de copie présents', (h.match(/cpf\(this,/g) || []).length >= 5 && (h.match(/pubSheet\(/g) || []).length === 2);
check('compteur de longueur du titre', h.includes(`${pack.youtube_shorts.title.length}/70`));
check('aucun envoi automatique annoncé', h.includes('aucun envoi automatique'));

check('copie : titre YouTube', ui.pubField('youtube_shorts.title') === pack.youtube_shorts.title);
check('copie : légende TikTok', ui.pubField('tiktok.caption') === pack.tiktok.caption);
check('copie : hashtags préfixés #', ui.pubField('tiktok.hashtags') === pack.tiktok.hashtags.map(x => '#' + x).join(' '));
check('copie : chemin inconnu -> chaîne vide', ui.pubField('youtube_shorts.inexistant') === '');
const sheet = ui.pubSheet('yt');
check('fiche YouTube = titre + description + tags', sheet.startsWith(pack.youtube_shorts.title) && sheet.includes(pack.youtube_shorts.description));
check('fiche TikTok = légende + hashtags', ui.pubSheet('tk').startsWith(pack.tiktok.caption));
const btn = { textContent: 'copier', dataset: {} };
ui.cpf(btn, 'tiktok.caption');
check('clic « copier » écrit dans le presse-papier', copied === pack.tiktok.caption, String(copied).slice(0, 40));
check('clic « copier » montre une confirmation', btn.textContent === 'copié ✓', btn.textContent);

check('ancien projet sans « platforms » : aucun panneau', ui.pubHtml(null) === '' && ui.pubHtml({}) === '');
const flat = { series: 'Histoire', style: 'pixel3d', choices: [], youtube_shorts: { title: 'T', description: 'D' }, tiktok: { caption: 'C' } };
const hf = ui.pubHtml(flat);
check('épisode sans choix : aucun vote inventé dans l’UI', hf.includes('Aucun choix écrit') && !hf.includes('A ou B'));

if (process.argv.includes('--html')) {      // aperçu autonome du panneau, ouvrable dans un navigateur
  const css = (html.match(/<style>([\s\S]*?)<\/style>/) || [])[1] || '';
  writeFileSync(join(ROOT, 'proofs/ui_panel_preview.html'),
    `<!doctype html><meta charset="utf-8"><style>${css}</style><body style="padding:18px"><main>${h}</main></body>`, 'utf8');
  console.log('aperçu écrit : proofs/ui_panel_preview.html');
}
console.log('\n' + (FAIL.length ? 'ÉCHECS : ' + FAIL.join(', ') : 'Tout est OK.'));
process.exit(FAIL.length ? 1 : 0);
