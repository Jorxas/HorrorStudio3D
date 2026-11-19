// Kit « horreur » du moteur unifié : de quoi monter une scène de peur sans écrire de JS, uniquement avec des données de scène.
//   * mondes  : station-service sous la pluie (supérette + parking + pompes), bus de nuit (intérieur), toit de bus inondé, talus herbeux avec bus et tunnel
//   * props   : accessoires posés par plan (`stage.props`) : panneaux, affiches, disjoncteur, portes qui s'ouvrent, bouton d'alarme, tube néon, main, rétroviseur…
//   * figures : silhouette à capuche sans visage (`kind: "faceless"`), créature haute à tête de cible (`kind: "creature"`) — même squelette que les autres
//   * env     : réglages de lumière du décor, chacun un nombre OU une table [[t, valeur], ...] (temps absolu du film), évalués par `tv`
// Rien ici ne décide : fonctions pures du temps, aucun hasard hors `mulberry` à graine fixe.
import * as THREE from 'three';
import { Batch, mat4, grunge, rimify } from './kit4.js';
import { boxesGeometry } from './boxes.js';
import { vox } from './props4.js';
import { buildStation } from './sets4b.js';
import { buildReserve } from './reserve.js';
import { buildBus, buildGraspHand } from './sets4.js';
import { mulberry } from './textures.js';
import { buildMonster, monsterUpdate, MONSTER_POSES, DEFAULT_MONSTER } from './horror_monster.js';
export { MONSTER_POSES, DEFAULT_MONSTER };

const V = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
const PX = 1 / 16;
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
// mat4 materials read per-vertex colours: a plain plane has none (it would render black), so give it white ones
const white = (geo) => { const n = geo.attributes.position.count; geo.setAttribute('color', new THREE.Float32BufferAttribute(new Float32Array(n * 3).fill(1), 3)); return geo; };

// ------------------------------------------------------------------ valeur à l'instant T : nombre ou [[t, v], ...] (linéaire entre deux clés)
export function tv(v, T, d = 0) {
  if (v == null) return d; if (typeof v === 'number') return v; if (!Array.isArray(v) || !v.length) return d;
  if (T <= v[0][0]) return v[0][1];
  for (let i = 0; i < v.length - 1; i++) if (T < v[i + 1][0]) { const k = (T - v[i][0]) / Math.max(1e-6, v[i + 1][0] - v[i][0]); return v[i][1] + (v[i + 1][1] - v[i][1]) * k; }
  return v[v.length - 1][1];
}
export const evalEnv = (env, T) => { const o = {}; for (const [k, v] of Object.entries(env || {})) o[k] = (Array.isArray(v) && Array.isArray(v[0])) ? tv(v, T) : v; return o; };

// ------------------------------------------------------------------ textures de texte (Monocraft)
function labelTex(lines, { w = 256, h = 64, col = '#ffffff', bg = null, font = 'Monocraft', size = null, border = null, align = 'center' } = {}) {
  const c = document.createElement('canvas'); c.width = w; c.height = h; const g = c.getContext('2d'); if (globalThis.HS_MIRROR) { g.translate(w, 0); g.scale(-1, 1); } if (bg) { g.fillStyle = bg; g.fillRect(0, 0, w, h); } else g.clearRect(0, 0, w, h);
  if (border) { g.strokeStyle = border; g.lineWidth = Math.max(2, w / 64); g.strokeRect(g.lineWidth / 2, g.lineWidth / 2, w - g.lineWidth, h - g.lineWidth); }
  const L = Array.isArray(lines) ? lines : [lines]; const sz = size ?? Math.floor(h / (L.length + 0.6)); g.font = `${sz}px ${font}`; g.textBaseline = 'middle'; g.textAlign = align; g.fillStyle = col;
  L.forEach((s, i) => g.fillText(s, align === 'center' ? w / 2 : 8, h * (i + 1) / (L.length + 1) + 1));
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.magFilter = THREE.NearestFilter; t.minFilter = THREE.LinearMipmapLinearFilter; t.anisotropy = 8; return t;
}
const emissiveMat = (map, k = 1) => new THREE.MeshBasicMaterial({ map, color: new THREE.Color(k, k, k), transparent: true, side: THREE.DoubleSide, fog: true });
const plane = (w, h, mat) => new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat);

// ------------------------------------------------------------------ accessoires : { type, at:[x,y,z], yaw, ...paramètres, anim: { open|on|press: [[t, v], ...] } }
export const PROPS = {
  // panneau lumineux ou mat : { text | lines, w, h, col, bg, emit, border }
  // photo : image réelle (data URI JPEG/PNG dans `data`) sur un plan { w, h, emit }
  photo: (p) => { const g = new THREE.Group(); const w = p.w ?? 0.3, h = p.h ?? 0.4; const c = document.createElement('canvas'); c.width = 8; c.height = 8; const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; const im = new Image(); im.onload = () => { c.width = im.width; c.height = im.height; c.getContext('2d').drawImage(im, 0, 0); t.needsUpdate = true; }; im.src = p.data; g.add(plane(w, h, emissiveMat(t, p.emit ?? 1))); return { g }; },
  sign: (p) => { const g = new THREE.Group(); const w = p.w ?? 0.8, h = p.h ?? 0.25; const m = plane(w, h, emissiveMat(labelTex(p.lines || p.text || '', { w: p.px ?? 256, h: Math.round((p.px ?? 256) * h / w), col: p.col || '#ff2a20', bg: p.bg || '#0a0202', border: p.border }), p.emit ?? 1)); g.add(m); return { g }; },
  // affiche du plan électrique : bandeau bleu, zone RÉSERVE entourée de rouge avec éclair, BOUTIQUE, croix rouge
  poster_plan: (p) => { const w = p.w ?? 0.8, h = p.h ?? 1.0; const c = document.createElement('canvas'); c.width = 256; c.height = Math.round(256 * h / w); const g2 = c.getContext('2d'); const W = 256, H = c.height;
    g2.fillStyle = '#f0ede6'; g2.fillRect(0, 0, W, H); g2.fillStyle = '#2c58b0'; g2.fillRect(0, 0, W, H * 0.12); g2.fillStyle = '#fff'; g2.font = `${Math.floor(H * 0.075)}px Monocraft`; g2.textBaseline = 'middle'; g2.textAlign = 'center'; g2.fillText(p.title || 'PLAN ÉLECTRIQUE', W / 2, H * 0.065);
    g2.strokeStyle = '#d83a2a'; g2.lineWidth = 5; g2.strokeRect(W * 0.08, H * 0.2, W * 0.84, H * 0.36); g2.fillStyle = '#d83a2a'; g2.textAlign = 'left'; g2.font = `${Math.floor(H * 0.06)}px Monocraft`; if (p.zone) g2.fillText(p.zone, W * 0.12, H * 0.255);
    g2.fillStyle = '#f2a02a'; g2.beginPath(); g2.arc(W * 0.5, H * 0.4, H * 0.1, 0, 7); g2.fill(); g2.strokeStyle = '#d83a2a'; g2.lineWidth = 4; g2.stroke(); g2.fillStyle = '#fff'; g2.beginPath(); g2.moveTo(W * 0.53, H * 0.32); g2.lineTo(W * 0.45, H * 0.41); g2.lineTo(W * 0.5, H * 0.41); g2.lineTo(W * 0.47, H * 0.49); g2.lineTo(W * 0.56, H * 0.38); g2.lineTo(W * 0.5, H * 0.38); g2.fill();
    g2.fillStyle = '#9a9a98'; g2.textAlign = 'center'; g2.font = `${Math.floor(H * 0.11)}px Monocraft`; if (p.label) g2.fillText(p.label, W / 2, H * 0.7); else { g2.strokeStyle = '#8a8a88'; g2.lineWidth = 3; g2.strokeRect(W * 0.1, H * 0.6, W * 0.8, H * 0.22); g2.beginPath(); g2.moveTo(W * 0.1, H * 0.7); g2.lineTo(W * 0.9, H * 0.7); g2.moveTo(W * 0.5, H * 0.6); g2.lineTo(W * 0.5, H * 0.56); g2.stroke(); for (const sx of [0.25, 0.5, 0.75]) g2.strokeRect(W * (sx - 0.06), H * 0.64, W * 0.12, H * 0.03); } g2.strokeStyle = '#d83a2a'; g2.lineWidth = 6; g2.beginPath(); g2.moveTo(W * 0.1, H * 0.86); g2.lineTo(W * 0.18, H * 0.94); g2.moveTo(W * 0.18, H * 0.86); g2.lineTo(W * 0.1, H * 0.94); g2.stroke();
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.magFilter = THREE.NearestFilter; const g = new THREE.Group(); g.add(plane(w, h, new THREE.MeshLambertMaterial({ map: t, emissive: 0x303030, emissiveMap: t }))); return { g }; },
  // coffret de disjoncteurs : { lever: 0..1 (levier rouge), label }
  breaker_box: (p) => { const g = new THREE.Group(); const w = p.w ?? 0.55, h = p.h ?? 0.75; const B = [{ x: 0, y: 0, z: 0, w, h, d: 0.1, color: 0x8a9096 }, { x: 0, y: 0, z: 0.055, w: w - 0.06, h: h - 0.06, d: 0.02, color: 0x2a2c30 }];
    for (let r = 0; r < 6; r++) for (let c = 0; c < 4; c++) B.push({ x: (c - 1.5) * 0.1, y: h * 0.28 - r * 0.075, z: 0.075, w: 0.07, h: 0.05, d: 0.03, color: (r + c) % 5 === 0 ? 0xd8d8d0 : 0x14161a });
    g.add(vox(B, { rim: 0.3 })); const lab = plane(w * 0.8, h * 0.1, emissiveMat(labelTex(p.label || 'DISJONCTEUR', { w: 256, h: 40, col: '#e8e8e8', bg: '#14161a' }), 0.9)); lab.position.set(0, h * 0.42, 0.07); g.add(lab);
    const lever = vox([{ x: 0, y: 0, z: 0, w: 0.05, h: 0.16, d: 0.05, color: 0xd02a1e }], { rim: 0.4 }); lever.position.set(0, -h * 0.4, 0.09); g.add(lever);
    return { g, update(T) { lever.rotation.x = -0.9 * tv(p.anim?.lever, T, 0); } }; },
  // porte à gauche ou à droite : { w, h, color, sign, hinge: 'l'|'r', maxOpen (rad) } ; anim.open 0..1
  door: (p) => { const g = new THREE.Group(); const w = p.w ?? 0.95, h = p.h ?? 2.1, hl = (p.hinge ?? 'l') === 'l'; const pivot = new THREE.Group(); pivot.position.x = hl ? -w / 2 : w / 2; g.add(pivot);
    const off = hl ? w / 2 : -w / 2; const B = [{ x: off, y: h / 2, z: 0, w, h, d: 0.06, color: p.color ?? 0x6c7a62 }, { x: off + (hl ? 0.38 : -0.38) * w, y: h * 0.5, z: 0.06, w: 0.06, h: 0.06, d: 0.1, color: 0xd0d0d0 }];
    for (let i = 0; i < 6; i++) B.push({ x: off, y: 0.3 + i * (h - 0.6) / 5, z: 0.035, w: w * 0.9, h: 0.05, d: 0.02, color: p.stripe ?? 0x56624e });
    pivot.add(vox(B, { rim: 0.4 })); if (p.sign) { const s = plane(0.34, 0.12, emissiveMat(labelTex(p.sign, { w: 128, h: 48, col: '#2a2208', bg: '#f2d22a', border: '#a88a10' }), 0.9)); s.position.set(off, h * 0.78, 0.07); pivot.add(s); }
    const frame = vox([{ x: 0, y: h / 2 + 0.05, z: -0.02, w: w + 0.16, h: h + 0.1, d: 0.04, color: 0x1a1a1e }], { rim: 0.2 }); g.add(frame);
    return { g, update(T) { pivot.rotation.y = (hl ? 1 : -1) * (p.maxOpen ?? 1.4) * tv(p.anim?.open, T, 0); } }; },
  // bouton d'alarme : plaque orange à liseré jaune pointillé + cube rouge (blanc quand anim.on = 1)
  alarm_button: (p) => { const g = new THREE.Group(); const w = p.w ?? 0.62, h = p.h ?? 0.46; const c = document.createElement('canvas'); c.width = 256; c.height = Math.round(256 * h / w); const g2 = c.getContext('2d'); g2.fillStyle = '#e08a22'; g2.fillRect(0, 0, 256, c.height);
    g2.fillStyle = '#f2d84a'; for (let x = 6; x < 250; x += 16) { g2.fillRect(x, 6, 9, 7); g2.fillRect(x, c.height - 13, 9, 7); } for (let y = 6; y < c.height - 10; y += 16) { g2.fillRect(6, y, 7, 9); g2.fillRect(243, y, 7, 9); }
    g2.fillStyle = '#7a2c08'; g2.font = `${Math.floor(c.height * 0.24)}px Monocraft`; g2.textBaseline = 'middle'; g2.textAlign = 'center'; g2.fillText(p.text || 'ALARM', 128, c.height * 0.8);
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.magFilter = THREE.NearestFilter; const pl = plane(w, h, new THREE.MeshLambertMaterial({ map: t, emissive: 0x4a2208, emissiveMap: t })); g.add(pl);
    const btn = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.2, 0.12), new THREE.MeshBasicMaterial({ color: new THREE.Color(2.6, 0.22, 0.16) })); btn.position.set(0, h * 0.16, 0.07); g.add(btn);
    const base = vox([{ x: 0, y: h * 0.16, z: 0.02, w: 0.26, h: 0.26, d: 0.04, color: 0x5a1a10 }], { rim: 0.3 }); g.add(base);
    return { g, update(T) { const on = tv(p.anim?.on, T, 0), press = tv(p.anim?.press, T, 0); btn.material.color.setRGB(1.3 + 0.5 * on, 0.14 + 0.9 * on, 0.1 + 0.85 * on); btn.position.z = 0.07 - 0.05 * press; } }; },
  // plaque de prix : cadre bleu, chiffres rouges en deux lignes
  price_sign: (p) => { const g = new THREE.Group(); const w = p.w ?? 1.0, h = p.h ?? 1.5; g.add(vox([{ x: 0, y: 0, z: -0.04, w: w + 0.12, h: h + 0.12, d: 0.08, color: 0x1c3c9c }], { rim: 0.4 }));
    const m = plane(w, h, emissiveMat(labelTex(p.lines || ['1.74', '0.99'], { w: 128, h: Math.round(128 * h / w), col: '#ff3a3a', bg: '#10163a', size: 44 }), p.emit ?? 1)); g.add(m); return { g }; },
  // tube fluorescent : { len, thick, col, emit } ; anim.on 0..1 (scintillement par table)
  tube: (p) => { const g = new THREE.Group(); const m = new THREE.MeshBasicMaterial({ color: new THREE.Color(3, 3, 3.2) }); const t = new THREE.Mesh(new THREE.BoxGeometry(p.thick ?? 0.08, 0.05, p.len ?? 1.3), m); g.add(t);
    const hold = vox([{ x: 0, y: 0.04, z: 0, w: (p.thick ?? 0.08) + 0.06, h: 0.03, d: (p.len ?? 1.3) + 0.08, color: 0x2a2c30 }], { rim: 0.2 }); g.add(hold);
    return { g, update(T) { const on = tv(p.anim?.on, T, 1) * (p.emit ?? 1); const c = p.col ? new THREE.Color(p.col) : new THREE.Color(1, 1, 1.05); m.color.setRGB(c.r * 3 * on, c.g * 3 * on, c.b * 3.2 * on); } }; },
  // main sombre qui sort d'un cadre (celle de A) : { scale, curl } ; anim.curl
  hand: (p) => { const h = buildGraspHand(p.scale ?? 1, p.seed ?? 5); h.g.rotation.x = p.tilt ?? 0; return { g: h.g, update(T) { h.set(tv(p.anim?.curl, T, p.curl ?? 0.2), p.spread ?? 0.25); } }; },
  // rétroviseur avec deux yeux : { w, h }
  mirror_eyes: (p) => { const g = new THREE.Group(); const w = p.w ?? 0.5, h = p.h ?? 0.16; g.add(vox([{ x: 0, y: 0, z: -0.02, w: w + 0.06, h: h + 0.06, d: 0.04, color: 0x2a2020 }], { rim: 0.3 })); const m = plane(w, h, new THREE.MeshBasicMaterial({ color: 0x0a0608 })); g.add(m);
    const eye = new THREE.MeshBasicMaterial({ color: new THREE.Color(2.2, 2.1, 1.7) }); for (const sx of [-1, 1]) { const e = new THREE.Mesh(new THREE.BoxGeometry(w * 0.2, h * 0.28, 0.01), eye); e.position.set(sx * w * 0.16, 0, 0.01); g.add(e); const pu = new THREE.Mesh(new THREE.BoxGeometry(w * 0.07, h * 0.2, 0.012), new THREE.MeshBasicMaterial({ color: 0x1a1210 })); pu.position.set(sx * w * 0.16, 0, 0.016); g.add(pu); } return { g }; },
  // pièce fermée vue de l'intérieur : { size:[w,h,d], wall, floor, ceil, trim } posée au sol, centrée sur `at` (pour les décors que le monde n'a pas : réserve, local technique)
  room: (p) => { const [w, h, d] = p.size || [4, 2.6, 3.5], t = 0.12, c = (v, k) => typeof v === 'string' ? parseInt(v.replace('#', ''), 16) : (v ?? k);
    const B = [{ x: 0, y: -t / 2, z: 0, w: w + 2 * t, h: t, d: d + 2 * t, color: c(p.floor, 0x2a2a30) }, { x: 0, y: h + t / 2, z: 0, w: w + 2 * t, h: t, d: d + 2 * t, color: c(p.ceil, 0x3a3a40) },
      { x: -w / 2 - t / 2, y: h / 2, z: 0, w: t, h, d, color: c(p.wall, 0x5a5a62) }, { x: w / 2 + t / 2, y: h / 2, z: 0, w: t, h, d, color: c(p.wall, 0x5a5a62) },
      { x: 0, y: h / 2, z: -d / 2 - t / 2, w, h, d: t, color: c(p.wall, 0x5a5a62) }, { x: 0, y: h / 2, z: d / 2 + t / 2, w, h, d: t, color: c(p.wall, 0x5a5a62) }];
    if (p.skirt !== false) for (const [x, z, ww, dd] of [[0, -d / 2 + 0.03, w, 0.06], [0, d / 2 - 0.03, w, 0.06], [-w / 2 + 0.03, 0, 0.06, d], [w / 2 - 0.03, 0, 0.06, d]]) B.push({ x, y: 0.09, z, w: ww, h: 0.18, d: dd, color: c(p.trim, 0x2a2a2e) });
    return { g: vox(B, { rim: 0.3 }) }; },
  // boîte de voxels libre : { boxes: [{x,y,z,w,h,d,color}] } pour tout ce que le catalogue n'a pas encore
  boxes: (p) => ({ g: vox((p.boxes || []).map((b) => ({ ...b, color: typeof b.color === 'string' ? parseInt(b.color.replace('#', ''), 16) : b.color })), { rim: p.rim ?? 0.4 }) }),
};
export function buildProps(list, parent) {
  const out = []; const g = new THREE.Group(); g.visible = false; parent.add(g);
  for (const p of list || []) {
    const f = PROPS[p.type]; if (!f) throw new Error(`accessoire inconnu : ${p.type} (disponibles : ${Object.keys(PROPS).join(', ')})`);
    const o0 = f(p); const o = (p.t0 != null || p.t1 != null) ? { ...o0, update: (T) => { const on = T >= (p.t0 ?? -1e9) && T < (p.t1 ?? 1e9); h.visible = on; if (on && o0.update) o0.update(T); } } : o0; const h = new THREE.Group(); h.add(o.g); h.position.set(...(p.at || [0, 0, 0])); h.rotation.y = p.yaw || 0; if (p.rot) h.rotation.set(...p.rot, 'YXZ'); if (p.scale) h.scale.setScalar(p.scale); g.add(h); out.push(o);
  }
  return { group: g, update: (T) => out.forEach((o) => o.update && o.update(T)) };
}

// ------------------------------------------------------------------ figures
// « sans visage » = créature surnaturelle (horror_monster.js : silhouette anormale, mains longues, capuche creuse). `look.monster: false` ou `human_hooded: true`
// redonne l'ancienne figure (un homme en capuche), gardée telle quelle pour les films déjà faits.
export function buildFaceless(buildCharacter4, spec = {}, seed = 40) {
  if (spec.monster === false || spec.human_hooded) return buildHoodedHuman(buildCharacter4, spec, seed);
  return buildMonster(buildCharacter4, spec, seed);
}
// silhouette à capuche, visage noir : même squelette que les autres personnages, donc mêmes marches, bras, têtes
export function buildHoodedHuman(buildCharacter4, spec = {}, seed = 40) {
  const hoodCol = spec.hood ?? 0x1a1d24, col = (k) => new THREE.Color(hoodCol).multiplyScalar(k).getHex();
  const ch = buildCharacter4({ skin: 0x050506, brow: 0x050506, hair: null, ...spec, top: spec.top || { type: 'hoodie', color: hoodCol }, shoes: spec.shoes || { type: 'boot', color: 0x101014 } }, seed);
  ch.setExpr = () => {}; ch.faceUpdate = () => {}; ch.faceMat.map = null; ch.faceMat.color.set(0x020203); ch.faceMat.needsUpdate = true;
  const B = [{ x: 0, y: 4.2, z: -4.8, w: 9.8, h: 9.8, d: 1.5, color: col(1) }, { x: 0, y: 8.8, z: -0.4, w: 9.8, h: 1.6, d: 9.8, color: col(1.1) }, { x: 0, y: 4.2, z: 4.9, w: 9.8, h: 1.2, d: 1.0, color: col(0.8) },
    { x: 4.9, y: 4.2, z: -0.2, w: 1.5, h: 9.8, d: 9.6, color: col(0.9) }, { x: -4.9, y: 4.2, z: -0.2, w: 1.5, h: 9.8, d: 9.6, color: col(0.9) }, { x: 0, y: -1.2, z: -0.8, w: 11.4, h: 2.4, d: 8.2, color: col(0.85) }, { x: 0, y: 8.0, z: 5.1, w: 7.6, h: 1.0, d: 0.8, color: col(0.6) }]
    .map((b) => ({ ...b, x: b.x * PX, y: b.y * PX, z: b.z * PX, w: b.w * PX, h: b.h * PX, d: b.d * PX }));
  ch.neck.add(vox(B, { var: 0.06 })); return ch;
}
// créature haute et mince, tête en cible rouge et crème, côtes peintes : { height (échelle y), width (échelle x/z), rings }
export function buildCreature(buildCharacter4, spec = {}, seed = 60) {
  const skin = spec.skin ?? 0xe9d8c0;
  const ch = buildCharacter4({ skin, brow: skin, hair: null, top: { type: 'leather', color: skin }, pants: { color: new THREE.Color(skin).multiplyScalar(0.92).getHex() }, shoes: { type: 'boot', color: new THREE.Color(skin).multiplyScalar(0.8).getHex() } }, seed);
  const S = 32, c = document.createElement('canvas'); c.width = c.height = S; const g = c.getContext('2d'); g.fillStyle = '#efe0c8'; g.fillRect(0, 0, S, S);
  const rings = spec.rings || ['#d5281c', '#f2e6d0', '#d5281c', '#f2e6d0', '#a01410']; rings.forEach((col, i) => { const r = S * (0.5 - i * 0.085); g.fillStyle = col; g.beginPath(); g.ellipse(S / 2, S / 2, r * 0.9, r, 0, 0, 7); g.fill(); });
  g.fillStyle = '#12060a'; g.beginPath(); g.ellipse(S / 2, S * 0.52, S * 0.1, S * 0.14, 0, 0, 7); g.fill();
  const tex = new THREE.CanvasTexture(c); tex.magFilter = THREE.NearestFilter; tex.minFilter = THREE.NearestFilter; tex.colorSpace = THREE.SRGBColorSpace;
  ch.setExpr = () => {}; ch.faceUpdate = () => {}; ch.faceMat.map = tex; ch.faceMat.color.set(0xffffff); ch.faceMat.needsUpdate = true;
  const rib = []; for (let i = 0; i < 6; i++) rib.push({ x: 0, y: (4.6 + i * 1.15) * PX, z: 2.2 * PX, w: 6.6 * PX, h: 0.55 * PX, d: 0.3 * PX, color: 0xb89c88 });
  ch.torso.add(vox(rib, { var: 0.04 })); ch.stretch = [spec.width ?? 0.62, spec.height ?? 1.55, spec.width ?? 0.62]; ch.headScale = spec.head ?? 1.0; ch.isCreature = true; return ch;
}

// objets attachés à un os d'un personnage : extras: [{ bone: 'torso'|'neck'|'handR'|'handL'|'head'|..., at:[x,y,z], boxes:[{x,y,z,w,h,d,color}], t0, t1 }]
// les boîtes sont en px du personnage (1/16 m) ; t0 / t1 (temps absolu du film) bornent la visibilité
export function buildExtras(ch, list) {
  const out = list.map((ex) => { const bone = ch[ex.bone]; if (!bone) throw new Error(`os inconnu : ${ex.bone}`);
    const B = ex.boxes.map((b) => ({ ...b, color: typeof b.color === 'string' ? parseInt(b.color.replace('#', ''), 16) : b.color, x: b.x * PX, y: b.y * PX, z: b.z * PX, w: b.w * PX, h: b.h * PX, d: b.d * PX }));
    const m = vox(B, { var: 0.04 }); if (ex.at) m.position.set(...ex.at.map((v) => v * PX)); m.visible = false; bone.add(m); return { m, t0: ex.t0 ?? -1e9, t1: ex.t1 ?? 1e9 }; });
  return { update: (T) => { out.forEach((o) => { o.m.visible = T >= o.t0 && T < o.t1; }); if (ch.monster) monsterUpdate(ch, T); } };
}

// gain d'un plan (calibrage de luminosité sur la source) : lumière ambiante, clé, remplissage, lampes du décor et exposition
function applyGain(S, g) { if (g == null || g === 1) return; S.hemi.i *= g; S.key.i *= g; S.fill.i *= g; S.exposure *= Math.max(0.5, g); for (const l of S.lights) l.i *= g; }

// ------------------------------------------------------------------ mondes
function lampLights(st, k) { return st.lampLights(4 * k); }

// Réglages de lumière MOTIVÉE, lus dans l'env de n'importe quel monde du kit (nombre ou table [[t, v], ...]), appliqués après la lumière du monde :
//   exposure_k / bloom_k : gains de l'exposition et du bloom (le `look` du plan, lui, REMPLACE la valeur : il ne sert pas à baisser une exposition calibrée)
//   rim_k / fill_k / hemi_k / key_k : gains du liseré, du remplissage, de l'ambiante, de la clé (un liseré sans source se coupe avec rim_k = 0)
//   lamp_k : gain des lampes du décor ; sat_k : gain de saturation ; key_dir : [x, y, z] direction de la clé (la lune, un lampadaire) ; key_col
//   tint / shadow_tint / high_tint : étalonnage global (#rrggbb)
// Les couleurs d'env peuvent s'écrire "#rrggbb" : elles sont converties en entiers avant que le monde les lise.
const HEX = /^#[0-9a-f]{6}$/i;
export const normEnv = (E) => { const o = { ...E }; for (const [k, v] of Object.entries(o)) if (typeof v === 'string' && HEX.test(v)) o[k] = parseInt(v.slice(1), 16); return o; };
export function grade(S, E) {
  if (E.rim_k != null && S.rim) S.rim = { ...S.rim, i: S.rim.i * E.rim_k };
  if (E.fill_k != null && S.fill) S.fill.i *= E.fill_k; if (E.hemi_k != null && S.hemi) S.hemi.i *= E.hemi_k; if (E.key_k != null && S.key) S.key.i *= E.key_k;
  if (E.exposure_k != null) S.exposure *= E.exposure_k; if (E.bloom_k != null) S.bloom *= E.bloom_k;
  if (E.lamp_k != null && S.lights) for (const l of S.lights) l.i *= E.lamp_k;
  if (E.sat_k != null) S.sat *= E.sat_k;
  if (Array.isArray(E.key_dir) && S.key) S.key.dir = E.key_dir.slice(0, 3); if (E.key_col != null && S.key) S.key.color = E.key_col;
  for (const [k, key] of [['tint', 'tint'], ['shadow_tint', 'shadowTint'], ['high_tint', 'highTint']]) if (E[k] != null) S[key] = E[k];
}
export function buildHorrorWorlds(ctx, wanted, base = V(6000, 0, 0), step = 400) {
  const { scene, reflector } = ctx; const W = []; let idx = 0;
  const mk = (name, build) => { if (!wanted.has(name)) { idx++; return; } const origin = base.clone().add(V(idx * step, 0, 0)); idx++; const w = build(origin); w.name = name; w.origin = origin;
    const look0 = w.look; w.look = (S, T, E = {}) => { const En = normEnv(E); look0(S, T, En); grade(S, En); }; w.at = (x, y, z) => origin.clone().add(V(x, y, z)); W.push(w); };
  const cool = (S, o) => { S.exposure = o.exposure ?? 1; S.bloom = o.bloom ?? 0.5; S.bloomThreshold = 0.9; S.bloomRadius = 0.5; S.contrast = o.contrast ?? 0.26; S.vignette = o.vignette ?? 0.55; S.sat = o.sat ?? 1.0; S.dofScale = 0.35; S.grain = 0.035; };

  // ---- station-service : repère de A (intérieur x ∈ [-4.5, 4.5], z ∈ [-7, 3.5], vitrine z = 3.5, parking z > 3.5)
  mk('station', (origin) => {
    const st = buildStation(ctx, origin, { reserve: true, carAt: [4.2, 7.3], clear: [[-0.5, -14.5, 5.5, -6.5], [7.5, -16, 12, 8]] }); const res = buildReserve(ctx, st); const w = { group: st.group, st, res };
    w.update = (t) => st.update(t); w.reflectY = 0.02;
    w.look = (S, T, E = {}) => {
      const pan = E.panels ?? 1, red = E.panel_red ?? 0, flick = E.flick ?? 0.08, out = (E.outside ?? 0) > 0.5;
      S.sets = [w.name]; res.update(T, E); st.setPanels(red, T, flick); const f = pan; st.panelM.forEach((m) => m.color.multiplyScalar(f));
      S.lights = [...st.panelLights(red, (out ? 1.5 : 1.25) * pan, 7).slice(0, out ? 2 : 9), ...st.car.lights(E.car ?? 1)]; if ((E.lamps ?? 1) > 0) S.lights.push(...lampLights(st, E.lamps ?? 1)); S.lights.push(...res.lights(E));
      if (E.torch) S.lights.push({ pos: st.w(...E.torch), color: 0xfff0d0, i: 4, dist: 7 });
      const gain = E.gain ?? 1, moon = (E.moon ?? 1.7) * gain;
      if ((E.canopy ?? 0) > 0) S.lights.push({ pos: st.w(-11, 3.5, 12), color: 0xdfe8ff, i: 6 * E.canopy, dist: 13, decay: 1.2 });
      S.key = { dir: [-0.3, 0.8, 0.6], color: 0xa8bcff, i: (out ? 0.9 : 0.7) * moon }; S.hemi = { sky: new THREE.Color(0x7a8ab4).lerp(new THREE.Color(0x6a2a28), red).getHex(), ground: 0x1c202c, i: (E.ambient ?? 1.9) * gain };
      S.fill = { dir: [0.3, 0.3, 1], color: 0x4a5a9a, i: 0.25 }; S.rim = { color: E.rim_col ?? (red > 0.3 ? 0xff2414 : 0x6a8aff), i: E.rim ?? (0.12 + 0.2 * red), pow: 5 }; S.edge = null;
      S.fog = { color: new THREE.Color(E.fog_col ?? 0x50688a).lerp(new THREE.Color(0x3a0606), red).getHex(), d: E.fog ?? 0.03 }; S.bg = E.bg ?? 0x3a4a64; S.lift = E.lift ?? 0x131a28;
      S.rain = (E.rain ?? 1) > 0 ? { i: 1.4 * (E.rain ?? 1), col: 0xb8c8ff, size: 7, speed: 1, clip: E.rain_zone ? new THREE.Vector4(origin.x + E.rain_zone[0], origin.z + E.rain_zone[1], origin.x + E.rain_zone[2], origin.z + E.rain_zone[3]) : new THREE.Vector4(-1e9, origin.z + 3.7, 1e9, 1e9) } : null; S.spark = out ? { i: 0.7, col: 0xd8e4ff, den: 0.02, size: 0.018 } : null;
      S.reflect = { y: 0.02 }; cool(S, { exposure: 1.6, ...E, ...(E.gain != null ? { exposure: 1.6 * Math.max(.5, E.gain) } : {}) }); S.shadowC = st.w(0, 0, -1); S.shadowS = 9;
      const nk = E.neon ?? 0.3; st.neonM.color.setRGB((E.neon_col ? E.neon_col[0] : 7) * nk, (E.neon_col ? E.neon_col[1] : 0.3) * nk, (E.neon_col ? E.neon_col[2] : 0.25) * nk); st.signM.color.setScalar(2.6 * clamp(E.sign ?? 1, 0, 2));
    };
    return w;
  });

  // ---- bus de nuit (intérieur) + sol extérieur sombre pour les plans à travers les vitres
  mk('bus', (origin) => {
    const bus = buildBus(ctx, origin); const w = { group: bus.group, bus };
    const out = new THREE.Mesh(new THREE.PlaneGeometry(200, 200), new THREE.MeshLambertMaterial({ color: 0x0b0d14 })); out.rotation.x = -Math.PI / 2; out.position.set(0, -0.96, -6); out.receiveShadow = true; bus.group.add(out);
    const inner = []; bus.group.traverse((o) => { if (o.material === bus.glass) inner.push(o); });
    w.update = (t, S) => bus.update(t, S);
    w.look = (S, T, E = {}) => {
      const red = E.red ?? 0.6; inner.forEach((m) => { m.visible = !(E.see_out ?? 1); }); bus.setWindows(E.window_col ?? 0x1a2030, E.window_glow ?? 0.06); S.sets = [w.name]; bus.setTubes(E.tubes ?? red, T); bus.setDoor(E.door ?? 0); bus.showPoles(E.hide_poles || []);
      bus.hands.forEach((h, i) => { h.g.visible = (E.hands ?? 0) > i / 26; });
      S.key = { dir: E.key_dir ?? [-0.1, 0.45, 1.0], color: red > 0.5 ? 0xffb08c : 0xfff0dc, i: E.key_i ?? 1.5 };
      S.hemi = { sky: new THREE.Color(0x4a4a58).lerp(new THREE.Color(0x8a1c12), red).getHex(), ground: new THREE.Color(0x2a2018).lerp(new THREE.Color(0x0a0202), red).getHex(), i: E.ambient ?? 0.55 };
      S.fill = { dir: [1, 0.3, -0.3], color: 0x5070ff, i: 0.18 }; S.lights = bus.tubeLights(E.tubes ?? red, T, (E.tube_i ?? 2.2) * (E.power ?? 1), 6);
      S.rim = { color: 0xff2414, i: 0.32 * red, pow: 5 }; S.edge = red > 0.4 ? { color: 0xff3a26, i: 0.28 * (red - 0.4) / 0.6, rad: 1.4, thr: 0.12, maxD: 7, wrap: 0.6 } : null;
      S.fog = { color: new THREE.Color(0x10141e).lerp(new THREE.Color(0x7a1008), red).getHex(), d: E.fog ?? (0.03 + 0.02 * red) }; S.bg = 0x050204;
      S.dust = { i: 1.4 * red + 0.3, col: red > 0.5 ? 0xff4a30 : 0xfff0d8, size: 0.9, box: V(3, 2.5, 7) }; S.spark = red > 0.4 ? { i: 1.2 * red, col: 0xff7a60, den: 0.04, size: 0.02 } : null;
      S.rain = (E.rain ?? 0) > 0 ? { i: E.rain, col: 0xb8c8ff, size: 7, speed: 1 } : null;
      cool(S, { bloom: 0.5, contrast: 0.3, vignette: 0.65, sat: 1.15, ...E }); S.dofScale = 0.55; S.shadowC = bus.w(0, 0, -6); S.shadowS = 8; S.reflect = { y: bus.liquid.position.y + bus.group.position.y };
      bus.glass.uniforms.uPass.value = E.pass ?? 0; bus.glass.uniforms.uDrive.value = -T * (E.drive ?? 0); bus.glass.uniforms.uOut.value.set(red > 0.5 ? 0x1a0204 : 0x0c1222); bus.glass.uniforms.uOut2.value.set(red > 0.5 ? 0x6a0a0c : 0x2a3a5a); applyGain(S, E.gain);
    };
    return w;
  });

  // ---- toit du bus au-dessus de l'eau : dalle claire, trappe avec échelle, eau noire réfléchissante, tunnel et lampadaire au loin
  mk('toit', (origin) => {
    const g = new THREE.Group(); g.position.copy(origin); scene.add(g); const r = mulberry(77); const w = { group: g };
    const roofM = mat4(grunge(0xb4aabc, { size: 32, noise: 0.1, dark: 0.12, seed: 71 }), { rim: 0.4, wet: 1.2 });
    const b = new Batch(); const L = 14, Wd = 3.0, HX = 0.5, HZ = 0.5;
    b.add({ x: 0, y: -0.1, z: 0, w: L, h: 0.2, d: Wd, mat: 'roof', tpm: 0.6 });
    for (const sz of [-1, 1]) b.add({ x: 0, y: 0.03, z: sz * (Wd / 2 - 0.05), w: L, h: 0.06, d: 0.1, mat: 'rim' });
    for (const sx of [-1, 1]) b.add({ x: sx * (L / 2 - 0.05), y: 0.03, z: 0, w: 0.1, h: 0.06, d: Wd, mat: 'rim' });
    for (let i = -5; i <= 5; i += 2.5) b.add({ x: i, y: 0.012, z: 0, w: 0.5, h: 0.02, d: Wd - 0.3, mat: 'vent' });
    // trappe : cadre épais, trou sombre, marches
    b.add({ x: 2.2, y: 0.04, z: 0, w: HX + 0.35, h: 0.08, d: HZ + 0.35, mat: 'frame' });
    b.add({ x: 2.2, y: 0.045, z: 0, w: HX, h: 0.1, d: HZ, mat: 'hole' });
    for (let i = 0; i < 4; i++) b.add({ x: 2.2 + 0.1, y: -0.12 - i * 0.18, z: 0, w: 0.5, h: 0.08, d: 0.5 - i * 0.04, mat: 'step' });
    b.build({ roof: roofM, rim: mat4(grunge(0x6a6070, { size: 16, noise: 0.15, seed: 72 }), { rim: 0.5 }), vent: mat4(grunge(0x8a8090, { size: 16, noise: 0.15, seed: 73 }), { rim: 0.4 }), frame: mat4(grunge(0x4a4250, { size: 16, noise: 0.2, seed: 74 }), { rim: 0.6 }), hole: new THREE.MeshBasicMaterial({ color: 0x050408 }), step: mat4(grunge(0x6a6a72, { size: 16, noise: 0.2, seed: 75 }), { rim: 0.4 }) }, g, { noCast: ['vent'] });
    const wetM = reflector.makeMaterial({ color: 0x06080e, reflect: 0.8, rough: 0.003, ripple: 1.0, tint: 0xd8e0ff, glitter: 0.15, glitterCol: 0xff6a50 });
    const water = new THREE.Mesh(new THREE.PlaneGeometry(220, 220), wetM); water.rotation.x = -Math.PI / 2; water.position.set(0, -1.2, 0); g.add(water); w.reflectY = -1.2;
    const far = []; for (let i = 0; i < 5; i++) far.push({ x: -60 + i * 28, y: 4, z: -40 - (i % 2) * 8, w: 8, h: 8, d: 6, color: 0x0c0e14 }); g.add(vox(far, { rim: 0.2 }));
    const lamp = vox([{ x: 0, y: 3.5, z: 0, w: 0.16, h: 7, d: 0.16, color: 0x2a2a30 }, { x: 0, y: 6.9, z: 0.6, w: 0.3, h: 0.14, d: 1.4, color: 0x2a2a30 }]); lamp.position.set(-9, -1.2, -10); g.add(lamp); w.lampPos = V(-9, 5.6, -9.4); w.update = () => {};
    w.look = (S, T, E = {}) => {
      S.sets = [w.name]; S.key = { dir: [-0.3, 0.9, 0.5], color: 0xc8d0ff, i: E.key ?? 0.5 }; S.hemi = { sky: 0x4a5878, ground: 0x14121a, i: E.ambient ?? 0.55 }; S.fill = { dir: [0.4, 0.3, 1], color: 0x5a6aa8, i: 0.3 };
      S.lights = [{ pos: w.lampPos.clone().add(origin), color: E.lamp_col ?? 0xff9a50, i: 5 * (E.lamp ?? 1), dist: 22, decay: 1.2 }, { pos: V(0, 4, 3).add(origin), color: E.glow_col ?? 0xff4a30, i: 2.4 * (E.glow ?? 1), dist: 12, decay: 1.4 }];
      S.fog = { color: 0x0a0e1a, d: E.fog ?? 0.018 }; S.bg = 0x05070e; S.rim = { color: 0xff3a24, i: 0.25, pow: 5 }; S.edge = null; S.spark = { i: 1.4, col: 0xc8d4ff, den: 0.04, size: 0.02 };
      S.rain = { i: 1.6 * (E.rain ?? 1), col: 0xc8d4ff, size: 7, speed: 1 }; S.reflect = { y: origin.y - 1.2 }; cool(S, E); S.shadowC = V(0, 0, 0).add(origin); S.shadowS = 9; applyGain(S, E.gain);
    };
    return w;
  });

  // ---- talus herbeux : route mouillée avec le bus, herbe sombre, tunnel au fond, lampadaire (x le long du bus, z vers la caméra)
  mk('talus', (origin) => {
    const g = new THREE.Group(); g.position.copy(origin); scene.add(g); const r = mulberry(88); const w = { group: g };
    const bus = buildBus(ctx, V(6, 0.95, -6).add(origin)); bus.place(V(6, 0.95, -6).add(origin), Math.PI / 2); bus.liquid.visible = false; w.bus = bus;
    const asphalt = reflector.makeMaterial({ map: grunge(0x14161c, { size: 64, noise: 0.35, dark: 0.3, seed: 81 }), color: 0xffffff, tpm: 0.3, reflect: 0.7, rough: 0.003, ripple: 1.0, tint: 0xe8f0ff, glitter: 0.2, glitterCol: 0xff8a70 });
    const road = new THREE.Mesh(new THREE.PlaneGeometry(220, 7.4), asphalt); road.rotation.x = -Math.PI / 2; road.position.set(0, 0.02, -6); g.add(road);
    const grass = mat4(grunge(0x1e4a26, { size: 32, noise: 0.28, dark: 0.2, seed: 82, specks: 0.1, speckCol: 0x34703a }), { rim: 0.2, wet: 0.5 });
    for (const [z0, z1] of [[-3.2, 40], [-80, -9.3]]) { const m = new THREE.Mesh(white(new THREE.PlaneGeometry(260, z1 - z0)), grass); m.rotation.x = -Math.PI / 2; m.position.set(0, 0.04, (z0 + z1) / 2); m.receiveShadow = true; const uv = m.geometry.attributes.uv; for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * 130, uv.getY(i) * 130 * (z1 - z0) / 260); const mp = m.material.map; if (mp) mp.wrapS = mp.wrapT = THREE.RepeatWrapping; g.add(m); }
    const B = []; // tunnel au fond (axe de la route), arbres sombres, lampadaire
    B.push({ x: -62, y: 3, z: -6, w: 3, h: 6, d: 9, color: 0x1a1c22 }, { x: -62, y: 6.4, z: -6, w: 3, h: 1.2, d: 11, color: 0x20222a }, { x: -62, y: 3, z: -11.2, w: 3, h: 6, d: 1.2, color: 0x22242c }, { x: -62, y: 3, z: 0, w: 3, h: 6, d: 1.2, color: 0x22242c });
    for (let i = 0; i < 40; i++) { const x = -60 + r() * 120, z = -14 - r() * 40, h = 5 + r() * 5; B.push({ x, y: h / 2, z, w: 0.5, h, d: 0.5, color: 0x120e0c }); for (let k = 0; k < 5; k++) B.push({ x, y: h * 0.35 + k * h * 0.13, z, w: (1 - k / 5) * h * 0.35 + 0.4, h: h * 0.09, d: (1 - k / 5) * h * 0.35 + 0.4, color: 0x0a1810, ry: k * 0.4 }); }
    B.push({ x: -14, y: 3.5, z: -2, w: 0.16, h: 7, d: 0.16, color: 0x2a2a30 }, { x: -14, y: 6.95, z: -2.6, w: 0.3, h: 0.14, d: 1.4, color: 0x2a2a30 });
    g.add(vox(B, { rim: 0.3 }));
    w.update = (t, S) => bus.update(t, S);
    w.look = (S, T, E = {}) => {
      S.sets = [w.name]; S.key = { dir: [-0.3, 0.9, 0.4], color: 0x9ab4ff, i: E.key ?? 1.4 }; S.hemi = { sky: 0x5a70a0, ground: 0x1a3a1c, i: E.ambient ?? 1.7 }; S.fill = { dir: [0.4, 0.3, 1], color: 0x5a6aa8, i: 0.5 };
      bus.setTubes(E.tubes ?? 0.7, T); S.lights = [...bus.tubeLights(E.tubes ?? 0.7, T, 1.6, 6), { pos: V(-14, 6.6, -2.6).add(origin), color: 0xff9a50, i: 5 * (E.lamp ?? 1), dist: 20, decay: 1.2 }];
      S.fog = { color: 0x16243a, d: E.fog ?? 0.016 }; S.bg = 0x0c141e; S.lift = 0x0a120e; S.rim = { color: E.rim_col ?? 0x5a8a6a, i: E.rim ?? 0.1, pow: 5 }; S.edge = null; S.spark = { i: 1.2, col: 0xc8d4ff, den: 0.04, size: 0.02 };
      S.rain = { i: 1.5 * (E.rain ?? 1), col: 0xc8d4ff, size: 7, speed: 1 }; S.reflect = { y: origin.y + 0.02 }; cool(S, { exposure: 1.5, sat: 1.2, ...E }); S.shadowC = V(0, 0, -3).add(origin); S.shadowS = 12; applyGain(S, E.gain);
      bus.glass.uniforms.uOut.value.set(0x1a0204); bus.glass.uniforms.uOut2.value.set(0x6a0a0c); bus.setWindows(E.window_col ?? 0xffb090, E.window_glow ?? 0.5);
    };
    return w;
  });
  return W;
}
