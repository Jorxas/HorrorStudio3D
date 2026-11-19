// Personnages v4 (style des illustrations) : grosse tête (10 px au lieu de 8), visage cartoon HD, cheveux en cubes
// qui débordent (bouclés, longs), mains avec doigts, baskets à semelle blanche, bottes à fourrure, sweat à capuche
// avec cordons, manteau écossais à fourrure, veste en cuir... Même structure de groupes que rig.js : anim.js marche tel quel.
import * as THREE from 'three';
import { PX } from './rig.js';
import { boxesGeometry } from './boxes.js';
import { faceRig, exprParams, blinkAmount, saccade, micro, talkMouth } from './face4.js';
import { drawR3D, R3MAP } from './face_r3d.js';
import { buildFaceRelief } from './face_relief.js';
import { grunge, plaid, rimify, voxify } from './kit4.js';
import { mulberry } from './textures.js';

const lam = (opts) => rimify(new THREE.MeshLambertMaterial(opts), 1, 0.15);
const vlam = (color, vo = {}) => voxify(rimify(new THREE.MeshLambertMaterial({ color }), 1, 0.5), vo);
const vmat = (vo = { var: 0.12 }) => voxify(rimify(new THREE.MeshLambertMaterial({ vertexColors: true }), 1, 0.5), vo);
const shade = (h, f) => { const c = new THREE.Color(h); c.multiplyScalar(f); return c; };
const mk = (geo, mat) => { const m = new THREE.Mesh(geo, mat); m.castShadow = true; m.receiveShadow = true; return m; };
const box = (w, h, d) => new THREE.BoxGeometry(w * PX, h * PX, d * PX);

// cheveux : coque de petits cubes en couches autour de la tête (coordonnées en px, tête 10x10x10 centrée en 0),
// frange en mèches irrégulières, longues mèches ondulées pour 'long'. Palette : base, variante, ombre, reflet.
function hairCubes(style, col, col2, r, bare = false) {     // bare : un chapeau couvre le dessus de la tête (ni calotte ni frange) ; sans effet par défaut
  const B = []; const curly = style === 'curly', long = style === 'long' || style === 'longStraight';
  const dark = shade(col, 0.75), hi = shade(col2, 1.2);
  const pick = () => { const v = r(); return v < 0.55 ? col : v < 0.84 ? col2 : v < 0.95 ? dark : hi; };
  const HS = 0.8; const c = (x, y, z, s, sy) => B.push({ x: x * HS * PX, y: y * HS * PX, z: z * HS * PX, w: s * 0.66 * PX, h: (sy ?? s) * 0.66 * PX, d: s * 0.66 * PX, color: shade(pick(), 0.95 + r() * 0.1) });
  const step = curly ? 0.68 : 0.64, size = () => curly ? 0.95 + r() * 0.55 : 0.85 + r() * 0.4;
  const layers = curly ? [[5.0, 1], [5.45, 0.8], [5.85, 0.35]] : [[5.0, 1], [5.4, 0.65], [5.75, 0.2]];
  for (const [out, prob] of layers) {
    const round = (a, b) => { const e = Math.max(Math.abs(a), Math.abs(b)) / 5.6; return e > 0.86 ? (e - 0.86) * (out - 4.6) * 2.2 : 0; };
    for (let x = -5.6; x <= 5.6; x += step) for (let z = -5.6; z <= 5.6; z += step) { if (r() > prob) continue; if (bare) continue; c(x + (r() - 0.5) * 0.5, out + r() * 0.45 - round(x, z), z + (r() - 0.5) * 0.5, size()); }
    for (const sx of [-1, 1]) for (let y = curly ? -2.6 : -4.2; y <= 5.6; y += step) for (let z = -5.6; z <= 5.6; z += step) {
      if (z > 3.4 && y < (curly ? -0.8 : 0.5)) continue; if (r() > prob) continue;
      c(sx * (out + r() * 0.4 - round(y, z) * 0.5), y + (r() - 0.5) * 0.5, z + (r() - 0.5) * 0.5, size());
    }
    for (let x = -5.6; x <= 5.6; x += step) for (let y = curly ? -4.2 : -5; y <= 5.6; y += step) { if (r() > prob) continue; c(x + (r() - 0.5) * 0.5, y + (r() - 0.5) * 0.5, -(out + r() * 0.4 - round(x, y) * 0.5), size()); }
  }
  // frange : mèches de longueurs variées devant le front (s'arrête au niveau des sourcils)
  if (!bare) for (let x = -5.3; x <= 5.3; x += 0.64) {
    const edge = Math.abs(x) / 5.3; const len = curly ? 0.8 + r() * 1.0 + edge * 1.0 : 0.7 + r() * 0.9 + edge * 1.6;
    for (let y = 5.5; y > 5.5 - len; y -= 0.7) c(x + (r() - 0.5) * 0.4 + (curly ? Math.sin(y * 2.1 + x) * 0.25 : 0), y, 5.15 + r() * 0.5 + (5.5 - y) * 0.04, curly ? 0.85 + r() * 0.45 : 0.8 + r() * 0.35);
  }
  if (curly && !bare) for (let i = 0; i < 60; i++) { const a = r() * Math.PI * 2, e = r() * 1.2; const x = Math.cos(a) * 5.6, z = Math.sin(a) * 5.6; c(x, 3.5 + e * 2.6, Math.min(z, 4.8), 0.9 + r() * 0.5); }
  if (long) {
    // mèches ondulées dans le dos (reposent sur le dos sous la tête) et devant les épaules
    const wav = (y, ph) => Math.sin(y * 0.55 + ph) * 0.55;
    for (let x = -5.2; x <= 5.2; x += 0.62) { const ph = r() * 6; const end = -10 - r() * 6 - (1 - Math.abs(x) / 5.2) * 1.5; for (let y = -4; y >= end; y -= 0.62) { const z = y < -5.2 ? -3.0 - r() * 0.7 : -5.6 - r() * 0.5; c(x + wav(y, ph), y, z, 0.85 + r() * 0.35, 1.0); } }
    for (const sx of [-1, 1]) for (let k = 0; k < 4; k++) {
      const ph = r() * 6, x0 = sx * (5.6 - k * 0.7), z0 = 0.5 + k * 1.05, end = -9 - r() * 5;
      for (let y = 1; y >= end; y -= 0.62) { const below = y < -5.2; c(below ? sx * (3.9 + k * 0.45) + wav(y, ph) * 0.6 : x0 + wav(y, ph) * 0.4, y, below ? 3.05 + k * 0.25 + r() * 0.3 : z0, 0.85 + r() * 0.35, 1.0); }
    }
  }
  return B;
}
function ringCubes(w, d, y, col, r, size = 1.5, k = 1) { const B = []; const per = 2 * (w + d); for (let s = 0; s < per; s += size * 0.9) { let x, z; if (s < w) { x = -w / 2 + s; z = d / 2; } else if (s < w + d) { x = w / 2; z = d / 2 - (s - w); } else if (s < 2 * w + d) { x = w / 2 - (s - w - d); z = -d / 2; } else { x = -w / 2; z = -d / 2 + (s - 2 * w - d); } const sz = size * (0.85 + r() * 0.45); B.push({ x: x * PX, y: (y + r() * 0.4) * PX, z: z * PX, w: sz * PX, h: sz * k * PX, d: sz * PX, color: shade(col, 0.9 + r() * 0.15) }); } return B; }

export function buildCharacter4(spec, seed = 1) {
  const r = mulberry(seed * 7 + 3);
  const skin = spec.skin ?? 0xf0a874;
  const faces = {}; const fr = faceRig({ seed, ...spec }); fr.set(exprParams('neutral'));
  const skinMat = vlam(skin, { var: 0.045, levels: 3, seed });
  const faceMat = lam({ map: fr.tex });
  const headMats = [skinMat, skinMat, skinMat, skinMat, faceMat, skinMat];
  const root = new THREE.Group(), hips = new THREE.Group(); hips.position.y = 14 * PX; root.add(hips);
  const torso = new THREE.Group(); hips.add(torso);
  const neck = new THREE.Group(); neck.position.y = 12 * PX; torso.add(neck);
  const head = mk(box(8, 8, 8), headMats); head.position.y = 4 * PX; neck.add(head);
  if (!globalThis.HS_FACE_LEGACY) {   // relief du visage (face_relief.js) : la face avant devient une plaque en relief qui porte la même texture ; la face plate d'origine n'est plus dessinée
    const relief = buildFaceRelief(head, faceMat); head.material[4] = new THREE.MeshBasicMaterial({ visible: false }); fr.cb = relief.update; relief.update(exprParams('neutral'));
  }
  const hairCol = spec.hair?.color ?? 0x2a1a12, hairCol2 = spec.hair?.color2 ?? 0x3e2618;
  if (spec.hair) { const hg = mk(boxesGeometry(hairCubes(spec.hair.style, hairCol, hairCol2, r, !!spec.hair.bare)), vmat({ var: 0.05, levels: 3, seed: seed + 2 })); hg.position.y = 4 * PX; neck.add(hg); }
  // haut
  const top = spec.top || { type: 'hoodie', color: 0x1e1c22 };
  const topMat = top.type === 'leather' ? voxify(rimify(new THREE.MeshPhongMaterial({ color: top.color, shininess: 55, specular: 0x4a3a3a }), 1, 0.6), { var: 0.1, levels: 4, seed: seed + 1 })
    : vlam(top.plaid ? 0xffffff : top.color, { var: top.plaid ? 0.08 : 0.12, levels: 4, seed: seed + 1, plaid: top.plaid, per: top.per ?? 2 });
  const shirtMat = vlam(top.shirt ?? 0x18181c, { var: 0.1, seed: seed + 9 });
  const det = []; // détails en cubes du torse (repère du torse)
  const bodyY = 6.1, tc = top.color, rib = shade(tc, 0.72), seam = shade(tc, 0.6);
  // bande côtelée (poignets, bas du pull) : fines côtes verticales alternées
  const ribBand = (B, cx, cy, cz, w, h, d, col) => { const n = Math.max(4, Math.round(w / 0.55)); for (let k = 0; k < n; k++) { const f = k % 2 ? 0.86 : 1.0; const x = cx - w / 2 + (k + 0.5) * w / n; B.push({ x: x * PX, y: cy * PX, z: cz * PX, w: (w / n + 0.02) * PX, h: h * PX, d: d * PX, color: shade(col, f) }); } };
  if (top.type === 'jacketOpen' || top.type === 'leather') {
    { const sm = mk(box(7.6, 12, 3.8), shirtMat); sm.position.set(0, bodyY * PX, 0); torso.add(sm); }
    const pan = (w, x, z, d = 4.4) => { const m = mk(box(w, 12.2, d), topMat); m.position.set(x * PX, bodyY * PX, z * PX); torso.add(m); };
    pan(8.4, 0, -0.35, 3.8); pan(2.7, -2.85, 0.35, 3.8); pan(2.7, 2.85, 0.35, 3.8);
    // bords de la veste ouverte (fermeture éclair), col de t-shirt, poches, coutures d'épaule
    for (const sx of [-1, 1]) {
      det.push({ x: sx * 1.58 * PX, y: bodyY * PX, z: 2.27 * PX, w: 0.34 * PX, h: 12.0 * PX, d: 0.2 * PX, color: 0x8e8e94 });                      // zip
      det.push({ x: sx * 1.9 * PX, y: bodyY * PX, z: 2.28 * PX, w: 0.3 * PX, h: 12.1 * PX, d: 0.16 * PX, color: seam });                         // couture du bord
      det.push({ x: sx * 3.0 * PX, y: 3.4 * PX, z: 2.28 * PX, w: 1.9 * PX, h: 0.3 * PX, d: 0.18 * PX, color: seam });                            // poche (fente)
      det.push({ x: sx * 3.6 * PX, y: 2.2 * PX, z: 2.28 * PX, w: 0.28 * PX, h: 2.4 * PX, d: 0.16 * PX, color: seam });
    }
    det.push({ x: 0, y: 11.75 * PX, z: 1.92 * PX, w: 3.0 * PX, h: 0.5 * PX, d: 0.12 * PX, color: shade(top.shirt ?? 0x18181c, 1.6) });          // col rond du t-shirt
    if (top.type === 'jacketOpen') {
      for (const sx of [-1, 1]) det.push({ x: sx * 1.75 * PX, y: 9.4 * PX, z: 2.36 * PX, w: 0.55 * PX, h: 4.4 * PX, d: 0.5 * PX, color: 0xe8e6e2 }, { x: sx * 1.75 * PX, y: 7.0 * PX, z: 2.4 * PX, w: 0.75 * PX, h: 0.75 * PX, d: 0.6 * PX, color: 0xbab8b4 }); // cordons
      ribBand(det, 0, 0.5, 0, 8.6, 1.2, 4.0, rib);
    } else { det.push({ x: -2.4 * PX, y: 10.6 * PX, z: 2.45 * PX, w: 2.2 * PX, h: 1.4 * PX, d: 0.6 * PX, color: shade(tc, 1.1), rz: 0.4 }, { x: 2.4 * PX, y: 10.6 * PX, z: 2.45 * PX, w: 2.2 * PX, h: 1.4 * PX, d: 0.6 * PX, color: shade(tc, 1.1), rz: -0.4 }); det.push({ x: 0, y: 0.8 * PX, z: 0, w: 8.6 * PX, h: 1.1 * PX, d: 4.8 * PX, color: 0x4a2e1c }, { x: 0, y: 0.8 * PX, z: 2.45 * PX, w: 1.6 * PX, h: 1.3 * PX, d: 0.3 * PX, color: 0xb89a5a }); }
  } else {
    const len = top.type === 'coat' ? 14 : 12.2; const m = mk(box(8.4, len, 4.4), topMat); m.position.set(0, (bodyY - (len - 12.2) / 2) * PX, 0); torso.add(m);
    if (top.type === 'hoodie') {
      det.push({ x: 0, y: 3.0 * PX, z: 2.3 * PX, w: 6.2 * PX, h: 3.2 * PX, d: 0.3 * PX, color: shade(tc, 0.86) });                // poche kangourou
      det.push({ x: 0, y: 4.65 * PX, z: 2.46 * PX, w: 6.2 * PX, h: 0.22 * PX, d: 0.1 * PX, color: seam });
      for (const sx of [-1, 1]) det.push({ x: sx * 1.3 * PX, y: 9.0 * PX, z: 2.35 * PX, w: 0.55 * PX, h: 4.2 * PX, d: 0.5 * PX, color: 0xe8e6e2 }, { x: sx * 1.3 * PX, y: 6.8 * PX, z: 2.4 * PX, w: 0.75 * PX, h: 0.75 * PX, d: 0.6 * PX, color: 0xbab8b4 });
      ribBand(det, 0, 0.5, 0, 8.6, 1.2, 4.7, rib);
    }
    if (top.type === 'coat' && top.fur) { det.push(...ringCubes(8.6, 4.6, -1.6, top.fur, r, 1.6)); for (let y = 10; y > -1.5; y -= 1.6) det.push({ x: 0, y: y * PX, z: 2.4 * PX, w: 1.5 * PX, h: 1.6 * PX, d: 0.6 * PX, color: shade(top.fur, 0.92 + r() * 0.1) }); det.push({ x: 0, y: 3.2 * PX, z: 0, w: 8.7 * PX, h: 1 * PX, d: 4.7 * PX, color: 0x2a1a14 }); }
  }
  // col / capuche autour du cou : relie la tête au torse (dos plus épais, côtés, devant ouvert)
  if (top.type === 'hoodie' || top.type === 'jacketOpen') {
    const hc = shade(tc, 0.9), hd = shade(tc, 0.74);
    det.push({ x: 0, y: 12.55 * PX, z: -1.75 * PX, w: 7.4 * PX, h: 2.6 * PX, d: 2.0 * PX, color: hc }, { x: 0, y: 11.6 * PX, z: -2.75 * PX, w: 7.8 * PX, h: 3.0 * PX, d: 1.1 * PX, color: hd });   // capuche repliée dans le dos
    for (const sx of [-1, 1]) det.push({ x: sx * 3.05 * PX, y: 12.5 * PX, z: 0.15 * PX, w: 1.5 * PX, h: 1.9 * PX, d: 3.4 * PX, color: hc }, { x: sx * 2.35 * PX, y: 12.35 * PX, z: 1.75 * PX, w: 1.4 * PX, h: 1.4 * PX, d: 0.8 * PX, color: hd });
  } else if (top.type === 'coat' && top.fur) det.push(...ringCubes(7.6, 4.2, 12.2, top.fur, r, 1.7));
  else det.push({ x: 0, y: 12.45 * PX, z: -0.4 * PX, w: 6.6 * PX, h: 1.2 * PX, d: 3.6 * PX, color: shade(tc, 0.85) });
  if (det.length) torso.add(mk(boxesGeometry(det), vmat({ var: 0.08, levels: 4, seed: seed + 5 })));
  // épaules arrondies : pente du trapèze vers le bras (cache le raccord quand le bras se lève)
  for (const sx of [-1, 1]) { const c = mk(box(2.9, 2.0, 4.2), topMat); c.position.set(sx * 4.75 * PX, 11.35 * PX, 0); c.rotation.z = -sx * 0.42; torso.add(c); }
  // cou (dépasse à peine du col)
  { const nk = mk(box(3.4, 1.6, 3.2), skinMat); nk.position.y = 0.1 * PX; neck.add(nk); }
  // bras : épaule → coude → poignet ; mains à phalanges (doigts qui s'enroulent vraiment)
  const sleeveMat = topMat;
  const sleeveLow = top.sleeve === 'none' || top.sleeve === 'short' ? skinMat : sleeveMat, sleeveUp = top.sleeve === 'none' ? skinMat : sleeveMat;      // manches courtes / bras nus (tenues de PIXEL 3D) ; sans effet par défaut
  const cuffCol = top.fur && top.type === 'coat' ? null : shade(tc, 0.78);
  const arm = (side) => {
    const sh = new THREE.Group(); sh.position.set(side * 6.1 * PX, 10.2 * PX, 0); torso.add(sh);
    const up = mk(box(3.9, 6.1, 3.9), sleeveUp); up.position.y = -1.05 * PX; sh.add(up);                 // +2.0 .. -4.1
    const el = new THREE.Group(); el.position.y = -4.0 * PX; sh.add(el);
    const ej = mk(box(3.72, 2.0, 3.72), sleeveLow); el.add(ej);                                          // pli du coude
    const fo = mk(box(3.8, 4.0, 3.8), sleeveLow); fo.position.y = -2.0 * PX; el.add(fo);                 // 0 .. -4.0
    const cb = []; if (cuffCol === null) cb.push(...ringCubes(4.1, 4.1, -4.4, top.fur, r, 1.4)); else ribBand(cb, 0, -4.45, 0, 4.06, 1.3, 4.06, cuffCol);
    if (sleeveLow === sleeveMat) el.add(mk(boxesGeometry(cb), vmat({ var: 0.06, levels: 3, seed: seed + 6 })));
    const hand = new THREE.Group(); hand.position.y = -5.05 * PX; el.add(hand);                         // poignet
    const wr = mk(box(2.3, 0.9, 2.6), skinMat); wr.position.y = 0.25 * PX; hand.add(wr);
    const palm = mk(box(2.5, 2.7, 3.2), skinMat); palm.position.y = -1.3 * PX; hand.add(palm);
    const knk = mk(box(2.4, 0.5, 3.15), skinMat); knk.position.set(-side * 0.08 * PX, -2.62 * PX, 0); hand.add(knk);        // jointures
    // doigts : épais comme la paume, séparés par de fines rainures ; z avant = index
    const LEN = [0.78, 0.94, 1.0, 0.92]; const fingers = [];
    for (let i = 0; i < 4; i++) {
      const L = LEN[i]; const f = new THREE.Group(); f.position.set(-side * 0.12 * PX, -2.8 * PX, (-1.18 + i * 0.787) * PX);
      const p1 = mk(box(1.55, 1.45 * L, 0.74), skinMat); p1.position.y = -0.68 * L * PX; f.add(p1);
      const f2 = new THREE.Group(); f2.position.y = -1.38 * L * PX; f.add(f2);
      const p2 = mk(box(1.42, 1.15 * L, 0.7), skinMat); p2.position.y = -0.55 * L * PX; f2.add(p2);
      hand.add(f); f.userData.tip = f2; fingers.push(f);
    }
    const th = new THREE.Group(); th.position.set(-side * 0.7 * PX, -0.85 * PX, 1.62 * PX);
    const t1 = mk(box(1.05, 1.35, 1.0), skinMat); t1.position.y = -0.62 * PX; th.add(t1);
    const th2 = new THREE.Group(); th2.position.y = -1.25 * PX; th.add(th2); const t2 = mk(box(0.95, 1.05, 0.92), skinMat); t2.position.y = -0.48 * PX; th2.add(t2);
    th.userData.tip = th2; hand.add(th);
    return { sh, el, hand, fingers, thumb: th };
  };
  const L = arm(1), Rr = arm(-1);
  // bassin (pantalon) : comble le haut des cuisses quand elles se plient
  const pants = spec.pants || { color: 0x2a2a30 };
  const pantsMat = vlam(pants.plaid ? 0xffffff : pants.color, { var: pants.plaid ? 0.08 : 0.12, levels: 4, seed: seed + 4, plaid: pants.plaid, per: pants.per ?? 2 });
  { const pb = mk(box(8.2, 2.6, 4.15), pantsMat); pb.position.y = -0.2 * PX; hips.add(pb); }
  // jambes : hanche → genou → cheville ; chaussures détaillées (semelle, lacets, bout renforcé)
  const leg = (side) => {
    const g = new THREE.Group(); g.position.set(side * 2.05 * PX, 0, 0); hips.add(g);
    const th = mk(box(4.0, 6.9, 4.1), pantsMat); th.position.y = -3.35 * PX; g.add(th);                  // +0.1 .. -6.8
    const kn = new THREE.Group(); kn.position.y = -6.5 * PX; g.add(kn);
    const kj = mk(box(3.85, 1.9, 3.95), pantsMat); kn.add(kj);
    const shn = mk(box(4.0, 5.5, 4.1), pantsMat); shn.position.y = -2.75 * PX; kn.add(shn);             // 0 .. -5.5
    const ft = new THREE.Group(); ft.position.y = -5.5 * PX; kn.add(ft);                                  // cheville (2 px au-dessus du sol)
    const toe = new THREE.Group(); toe.position.set(0, -1.95 * PX, 1.95 * PX); ft.add(toe);              // pli des orteils (articulation de la basket)
    const sh = spec.shoes || { type: 'sneaker', color: 0x1a1a1e, sole: 0xf2f2f0 };
    const sb = [], tb = [], pb = []; const sole = sh.sole ?? 0xf2f2f0, sc = sh.color;
    const P = (b) => ({ ...b, x: b.x * PX, y: b.y * PX, z: b.z * PX, w: b.w * PX, h: b.h * PX, d: b.d * PX });
    if (sh.type === 'boot') {
      sb.push(P({ x: 0, y: -0.2, z: -0.2, w: 4.5, h: 3.4, d: 4.2, color: sc }), P({ x: 0, y: -1.7, z: -0.1, w: 4.6, h: 0.6, d: 4.5, color: shade(sc, 0.55) }));
      sb.push(P({ x: 0, y: 0.6, z: 1.92, w: 0.5, h: 2.0, d: 0.14, color: shade(sc, 0.7) }));
      tb.push(P({ x: 0, y: 1.05, z: 0.7, w: 4.4, h: 1.5, d: 1.5, color: sc }), P({ x: 0, y: 0.25, z: 0.75, w: 4.6, h: 0.6, d: 1.7, color: shade(sc, 0.55) }), P({ x: 0, y: 1.0, z: 1.48, w: 4.0, h: 1.2, d: 0.16, color: shade(sc, 0.8) }));
      if (sh.fur) sb.push(...ringCubes(4.6, 4.8, 1.8, sh.fur, r, 1.5));
    } else {
      const panel = new THREE.Color(sc).getHSL({}).l < 0.2 ? new THREE.Color(0x5e5e66) : shade(sc, 1.4), white = shade(sole, 0.97);
      sb.push(P({ x: 0, y: 0.35, z: -0.4, w: 3.9, h: 0.8, d: 3.6, color: shade(sc, 0.8) }));                         // col (caché sous l'ourlet)
      sb.push(P({ x: 0, y: -0.7, z: -1.35, w: 4.3, h: 1.6, d: 2.0, color: sc }));                                    // contrefort du talon
      sb.push(P({ x: 0, y: -0.25, z: -2.3, w: 3.2, h: 0.9, d: 0.2, color: white }));                                  // languette du talon
      sb.push(P({ x: 0, y: -0.85, z: 0.85, w: 4.35, h: 1.5, d: 2.2, color: sc }));                                   // cou-de-pied
      for (const sx of [-1, 1]) sb.push(P({ x: sx * 2.19, y: -0.95, z: 0.4, w: 0.06, h: 0.9, d: 2.6, color: panel }));   // empiècement latéral
      for (const sx of [-1, 1]) sb.push(P({ x: sx * 2.23, y: -1.05, z: 0.25, w: 0.06, h: 0.32, d: 2.2, color: white, rx: -0.3 }));   // virgule blanche
      for (let k = 0; k < 3; k++) sb.push(P({ x: 0, y: -0.05 - k * 0.16, z: 0.05 + k * 0.6, w: 2.7, h: 0.22, d: 0.34, color: 0xf6f4f0 }));   // lacets
      sb.push(P({ x: 0, y: 0.05, z: 0.4, w: 2.0, h: 0.2, d: 1.2, color: panel }));                                   // languette
      sb.push(P({ x: 0, y: -1.62, z: -0.2, w: 4.55, h: 0.76, d: 4.3, color: sole }), P({ x: 0, y: -1.96, z: -0.2, w: 4.45, h: 0.1, d: 4.2, color: shade(sole, 0.5) }));   // semelle épaisse
      sb.push(P({ x: 0, y: -1.42, z: -0.2, w: 4.58, h: 0.08, d: 4.32, color: shade(sole, 0.82) }));                   // liseré de semelle
      // avant du pied (articulé) : dessus en pente douce vers la pointe, bout en caoutchouc, semelle légèrement relevée
      tb.push(P({ x: 0, y: 1.22, z: 0.6, w: 4.3, h: 1.05, d: 1.2, color: sc }));
      tb.push(P({ x: 0, y: 1.08, z: 1.55, w: 4.2, h: 0.78, d: 0.7, color: sc }));
      tb.push(P({ x: 0, y: 0.95, z: 2.08, w: 3.9, h: 0.55, d: 0.36, color: white }));
      tb.push(P({ x: 0, y: 0.35, z: 1.0, w: 4.5, h: 0.7, d: 2.0, color: sole }), P({ x: 0, y: 0.48, z: 2.12, w: 4.2, h: 0.5, d: 0.3, color: sole }), P({ x: 0, y: 0.03, z: 0.95, w: 4.4, h: 0.1, d: 1.9, color: shade(sole, 0.5) }));
      tb.push(P({ x: 0, y: 0.75, z: 1.0, w: 4.52, h: 0.08, d: 2.0, color: shade(sole, 0.82) }));
      pb.push(P({ x: 0, y: 0.75, z: 0, w: 4.4, h: 1.3, d: 4.45, color: shade(pants.color, 0.78) }));                  // ourlet (recouvre le col)
    }
    if (pants.torn) pb.push({ x: 0, y: 2.6 * PX, z: 2.08 * PX, w: 2 * PX, h: 1.6 * PX, d: 0.2 * PX, color: skin }, { x: 0.6 * PX, y: 0.2 * PX, z: 2.08 * PX, w: 1.4 * PX, h: 1 * PX, d: 0.2 * PX, color: skin });
    if (pb.length) kn.add(mk(boxesGeometry(pb.map((b) => ({ ...b, y: b.y - 5.5 * PX }))), vmat({ var: 0.08 })));
    const shoe = mk(boxesGeometry(sb), vmat({ var: 0.07, levels: 3 })); ft.add(shoe);
    const toeShoe = mk(boxesGeometry(tb), vmat({ var: 0.07, levels: 3 })); toe.add(toeShoe);
    const sock = mk(boxesGeometry([{ x: 0, y: -0.9 * PX, z: -0.3 * PX, w: 4.1 * PX, h: 2.3 * PX, d: 4.0 * PX, color: 0xe8e4dc }]), vmat({ var: 0.05 })); sock.visible = false; ft.add(sock);
    const toeSock = mk(boxesGeometry([{ x: 0, y: 0.75 * PX, z: 0.7 * PX, w: 4.0 * PX, h: 1.4 * PX, d: 1.6 * PX, color: 0xe0dad0 }]), vmat({ var: 0.05 })); toeSock.visible = false; toe.add(toeSock);
    shoe.userData.pair = toeShoe; sock.userData.pair = toeSock; g.userData.toe = toe;
    g.userData.shoe = shoe; g.userData.sock = sock; g.userData.kn = kn; g.userData.ft = ft;
    return g;
  };
  const lgL = leg(1), lgR = leg(-1);
  // bonnet
  if (spec.hat?.type === 'beanie') {
    const hb = []; const hcol = spec.hat.color;
    for (let x = -4.6; x <= 4.6; x += 1.15) for (let z = -4.6; z <= 4.6; z += 1.15) hb.push({ x: x * PX, y: (5.4 + r() * 0.4) * PX, z: z * PX, w: 1.3 * PX, h: 2.3 * PX, d: 1.3 * PX, color: shade(hcol, 0.9 + r() * 0.16) });
    hb.push(...ringCubes(9.6, 9.6, 3.6, spec.hat.fur ?? 0xf0ece4, r, 1.5, 1.2));
    if (spec.hat.snow) for (let i = 0; i < 18; i++) hb.push({ x: (r() - 0.5) * 7.4 * PX, y: (6.9 + r() * 0.5) * PX, z: (r() - 0.5) * 7.4 * PX, w: 1.0 * PX, h: 0.6 * PX, d: 1.0 * PX, color: 0xf6f8ff });
    const hm = mk(boxesGeometry(hb), vmat({ var: 0.07, levels: 3 })); hm.position.y = 4 * PX; neck.add(hm);
  }
  const ch = { hipY: 14 * PX, root, hips, torso, neck, head, shL: L.sh, shR: Rr.sh, elL: L.el, elR: Rr.el, handL: L.hand, handR: Rr.hand, lgL, lgR, knL: lgL.userData.kn, knR: lgR.userData.kn, ftL: lgL.userData.ft, ftR: lgR.userData.ft,
    spec, faces, faceMat, expr: 'neutral', fingersL: L.fingers, fingersR: Rr.fingers, thumbL: L.thumb, thumbR: Rr.thumb,
    // longueurs des segments (m) pour la cinématique inverse : épaule→coude, coude→centre de la paume, hanche→genou, genou→cheville, cheville→sol
    LEN: { up: 4.0 * PX, fo: 6.4 * PX, th: 6.5 * PX, sh: 5.5 * PX, ft: 2.0 * PX }, toeL: lgL.userData.toe, toeR: lgR.userData.toe };
  // visage : on note l'expression voulue ; faceUpdate(t) (appelé une fois par image) fait la transition, les clignements et le regard
  const F = ch.face = { want: 'neutral', seed: seed * 0.37, base: exprParams('neutral'), from: null, t0: 0, lastT: -1e9, talk: 0, extra: null };
  ch.setExpr = (e) => { ch.expr = e; F.want = e; };
  ch.faceUpdate = (t) => {
    if (!faceMat.map) return;
    if (F.layer) {   // couche visage du studio (hstudio/voxelgpu/faceact.py) : émotions pondérées, regard, paupières, sourcils déjà calculés ; rien de aléatoire ici
      const L = F.layer, N = exprParams('neutral'), P = { ...N };
      for (const [nm, iv] of [[L.e1, L.i1], [L.e2, L.i2]]) { if (!nm || !(iv > 0)) continue; const pe = exprParams(nm === 'blink' ? 'neutral' : nm); for (const k in P) if (typeof P[k] === 'number') P[k] += iv * (pe[k] - N[k]); }
      P.eo = Math.max(0, P.eo * (1 - L.blink)); P.lx = L.lx; P.ly = L.ly; P.bi += L.bdi; P.bo += L.bdo; P.mo = Math.max(0, P.mo + L.mo); P.ms += L.ms; P.tilt += L.tilt;
      talkMouth(P, t, F.talk);
      F.lastT = t; micro(P, t, F.seed); fr.set(P); return;
    }
    const target = exprParams(F.want === 'blink' ? 'neutral' : F.want); const jump = t < F.lastT - 0.02 || t - F.lastT > 0.4;
    if (jump) { F.cur = F.want; F.from = null; F.base = target; }
    else if (F.want !== F.cur) { F.from = { ...F.base }; F.cur = F.want; F.t0 = t; }
    F.lastT = t; let P = target;
    if (F.from) { const k = Math.min(1, (t - F.t0) / 0.2); const e = k * k * (3 - 2 * k); P = {}; for (const key in target) P[key] = typeof target[key] === 'number' ? F.from[key] + (target[key] - F.from[key]) * e : target[key]; if (k >= 1) F.from = null; }
    F.base = { ...P }; P = { ...P };
    const b = F.want === 'blink' ? 1 : blinkAmount(t, F.seed); P.eo *= 1 - b;
    const [sx, sy] = saccade(t, F.seed); P.lx += sx; P.ly += sy;
    talkMouth(P, t, F.talk);
    if (F.extra) Object.assign(P, F.extra);
    micro(P, t, F.seed); fr.set(P);
  };
  if (spec.r3d) {   // visages du premier moteur (face_r3d.js) : 24x24 pixels, mêmes 12 expressions, bouche par paliers ; remplace seulement le dessin du visage
    const cv = fr.tex.image, g2 = cv.getContext('2d'), N2 = cv.width, skinHex = '#' + (skin >>> 0).toString(16).padStart(6, '0'); let last = '';
    ch.faceUpdate = (t) => {
      const kind = R3MAP[F.want] || 'neutral'; let m = 0;
      if (F.talk > 0) { const syl = Math.abs(Math.sin(t * 10.5 + Math.sin(t * 3.7) * 2)); m = F.talk * (0.25 + 0.75 * syl); }
      const k = kind + '|' + Math.round(m * 4); if (k === last) return; last = k;
      g2.setTransform(1, 0, 0, 1, 0, 0); g2.clearRect(0, 0, N2, N2); drawR3D(g2, N2, kind, m, skinHex); fr.tex.needsUpdate = true;
    };
  }
  // poses de main : [courbure phalange 1, écartement, pouce, courbure phalange 2]
  const HP = { relaxed: [0.5, 0.06, 0.3, 0.55], fist: [1.5, 0, 1.0, 1.7], open: [-0.05, 0.16, -0.25, 0.0], claw: [0.7, 0.2, 0.5, 1.1], grip: [1.25, 0, 0.9, 1.45], point: [1.5, 0, 0.9, 1.7], pinch: [0.6, 0.05, 0.9, 0.7] };
  const setOne = (fs, th, side, pose) => {
    const [c1, spread, tc1, c2] = Array.isArray(pose) ? pose : (HP[pose] || HP.relaxed);
    fs.forEach((f, i) => { const k = pose === 'point' && i === 3 ? 0.05 : 1; f.rotation.set((i - 1.5) * spread * 0.5, 0, -side * c1 * k); f.userData.tip.rotation.set(0, 0, -side * c2 * k); });
    th.rotation.set(-tc1 * 0.7, 0, side * (0.35 - 0.95 * Math.max(0, tc1 - 0.4))); th.userData.tip.rotation.set(-tc1 * 0.25, 0, -side * 0.9 * Math.max(0, tc1 - 0.4));
  };
  ch.setHand = (which, pose) => { if (which === 'L') setOne(L.fingers, L.thumb, 1, pose); else setOne(Rr.fingers, Rr.thumb, -1, pose); };
  ch.setHands = (left = 'relaxed', right = left) => { setOne(L.fingers, L.thumb, 1, left); setOne(Rr.fingers, Rr.thumb, -1, right); };
  ch.setShoe = (side, on) => { const g = side === 'L' ? lgL : lgR; g.userData.shoe.visible = on; g.userData.sock.visible = !on; g.userData.shoe.userData.pair.visible = on; g.userData.sock.userData.pair.visible = !on; };
  ch.reset = () => { hips.position.set(0, ch.hipY, 0); for (const g of [hips, torso, neck, ch.shL, ch.shR, ch.elL, ch.elR, ch.handL, ch.handR, lgL, lgR, ch.knL, ch.knR, ch.ftL, ch.ftR, ch.toeL, ch.toeR, root]) g.rotation.set(0, 0, 0); root.scale.setScalar(ch.baseScale || 1); ch.setHands('relaxed'); F.talk = 0; F.extra = null; ch._lockL = ch._lockR = false; };
  ch.reset();
  return ch;
}
