// « Cité » : un quartier de ville praticable (rue, trottoirs, façades en relief, café avec intérieur, ruelle, monte-charge), un astroport sur un toit
// (navette, tour de contrôle, ville en contrebas, ciel qui s'assombrit avec l'altitude) et deux accessoires pour la Lune (navette posée, balise).
// Tout est déterministe (graines fixes, aucune horloge) : fonction pure de T et de l'env du plan.
// Repères : le plan de géométrie de hstudio/voxelgpu/stagegeo.py (cite / astroport) est écrit avec les MÊMES nombres ; tools/check_demo_cite.py les compare.
//   cité      : centre local x = 60 (rue le long de x, trottoir nord z -5.5..-1.5, chaussée -1.5..5.5, trottoir sud 5.5..9.5), façades nord en z = -5.5 face à +z
//   astroport : centre local x = 130 (dalle 36 x 36, y = 0 au sol du toit, la ville en contrebas)
import * as THREE from 'three';
import { Batch, mat4, grunge, tiles, pixTex, rimify, voxify } from './kit4.js';
import { boxesGeometry } from './boxes.js';
import { mulberry } from './textures.js';
import { PROPS, tv, normEnv, grade } from './horror_kit.js';

export const CX = 60, AX = 190, SX = 270;                       // centres locaux (m) de la cité et de l'astroport : mêmes nombres que stagegeo.py
const V = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
const sh = (h, f) => new THREE.Color(h).multiplyScalar(f);
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x)), lerp = (a, b, k) => a + (b - a) * k;
const cvs = (w, h) => { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; };
const hex = (h) => '#' + new THREE.Color(h).getHexString();

// ---------------------------------------------------------------------------------------------------------------- matériaux de base
const vmat = (o = {}) => voxify(rimify(new THREE.MeshLambertMaterial({ vertexColors: true, emissive: o.emissive ?? 0x000000 }), o.rim ?? 0.5, o.wet ?? 0.2), { var: o.var ?? 0.08, levels: 4, px: o.px ?? 1 / 16, seed: o.seed ?? 0 });
const vox = (boxes, o = {}) => { const m = new THREE.Mesh(boxesGeometry(boxes), o.mat || vmat(o)); m.castShadow = o.cast ?? true; m.receiveShadow = true; return m; };
const basicVox = (boxes, k = 1) => { const m = new THREE.MeshBasicMaterial({ vertexColors: true, fog: true }); m.color.setScalar(k); const me = new THREE.Mesh(boxesGeometry(boxes), m); me.castShadow = false; return me; };

function brickTex(base, mortar, seed) {
  const S = 32, c = cvs(S, S), g = c.getContext('2d'), r = mulberry(seed); const b = new THREE.Color(base), m = new THREE.Color(mortar);
  for (let y = 0; y < S; y++) for (let x = 0; x < S; x++) {
    const row = Math.floor(y / 4), off = (row % 2) * 4, mort = (y % 4 === 0) || ((x + off) % 8 === 0); const f = mort ? 1 : 0.86 + r() * 0.26; const col = mort ? m : b;
    g.fillStyle = `rgb(${Math.min(255, col.r * 255 * f) | 0},${Math.min(255, col.g * 255 * f) | 0},${Math.min(255, col.b * 255 * f) | 0})`; g.fillRect(x, y, 1, 1);
  }
  return pixTex(c);
}
function roofTex(base, seed) {
  const S = 32, c = cvs(S, S), g = c.getContext('2d'), r = mulberry(seed); const b = new THREE.Color(base);
  for (let y = 0; y < S; y++) for (let x = 0; x < S; x++) { const row = Math.floor(y / 4), off = (row % 2) * 4; const edge = (y % 4 === 3) || ((x + off) % 8 === 7); const f = edge ? 0.6 : 0.85 + r() * 0.25;
    g.fillStyle = `rgb(${b.r * 255 * f | 0},${b.g * 255 * f | 0},${b.b * 255 * f | 0})`; g.fillRect(x, y, 1, 1); }
  return pixTex(c);
}
function plankTex(base, seed) {
  const S = 32, c = cvs(S, S), g = c.getContext('2d'), r = mulberry(seed); const b = new THREE.Color(base); const tone = [0.9, 1.0, 0.82, 0.95];
  for (let px = 0; px < 4; px++) { const t = tone[px] * (0.92 + r() * 0.16), j = (r() * 24 | 0) + 4;
    for (let y = 0; y < S; y++) for (let x = 0; x < 8; x++) { const edge = x === 0 || y === j; const f = (edge ? 0.62 : 1) * t * (0.94 + r() * 0.1);
      g.fillStyle = `rgb(${b.r * 255 * f | 0},${b.g * 255 * f | 0},${b.b * 255 * f | 0})`; g.fillRect(px * 8 + x, y, 1, 1); } }
  return pixTex(c);
}
function stripeTex(a, b, n = 8) { const c = cvs(n * 2, 4), g = c.getContext('2d'); g.fillStyle = hex(a); g.fillRect(0, 0, n * 2, 4); g.fillStyle = hex(b); for (let i = 0; i < n; i += 2) g.fillRect(i * 2, 0, 2, 4); return pixTex(c); }
function labelTex(text, { w = 256, h = 64, col = '#ffffff', bg = '#202428', font = 'Inter', weight = '800', border = null } = {}) {
  const c = cvs(w, h), g = c.getContext('2d'); g.fillStyle = bg; g.fillRect(0, 0, w, h); if (border) { g.strokeStyle = border; g.lineWidth = Math.max(2, h / 16); g.strokeRect(g.lineWidth, g.lineWidth, w - 2 * g.lineWidth, h - 2 * g.lineWidth); }
  const L = Array.isArray(text) ? text : [text]; let sz = Math.floor(h / (L.length + 0.7)); g.font = `${weight} ${sz}px ${font}, sans-serif`; while (g.measureText(L.reduce((a, b) => (a.length > b.length ? a : b), '')).width > w * 0.92 && sz > 6) { sz -= 2; g.font = `${weight} ${sz}px ${font}, sans-serif`; }
  g.textBaseline = 'middle'; g.textAlign = 'center'; g.fillStyle = col; L.forEach((s, i) => g.fillText(s, w / 2, h * (i + 1) / (L.length + 1) + 1));
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; t.minFilter = THREE.LinearMipmapLinearFilter; return t;
}
function signPlane(text, w, h, o = {}) { const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ map: labelTex(text, { w: o.px ?? 256, h: Math.round((o.px ?? 256) * h / w), col: o.col, bg: o.bg, border: o.border, font: o.font, weight: o.weight }), color: new THREE.Color().setScalar(o.k ?? 1), fog: true })); return m; }

function sky(group, init) {
  const u = { uTop: { value: new THREE.Color(init.top) }, uMid: { value: new THREE.Color(init.mid) }, uBot: { value: new THREE.Color(init.bot) }, uSun: { value: V(...init.sun).normalize() }, uSunCol: { value: new THREE.Color(init.sunCol ?? 0xfff2d0) }, uSunSize: { value: init.sunSize ?? 0.03 }, uStars: { value: init.stars ?? 0 } };
  const m = new THREE.ShaderMaterial({ uniforms: u, side: THREE.BackSide, depthWrite: false, fog: false,
    vertexShader: 'varying vec3 vD; void main(){ vD = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
    fragmentShader: `uniform vec3 uTop, uMid, uBot, uSun, uSunCol; uniform float uSunSize, uStars; varying vec3 vD;
      float h(vec3 p){ return fract(sin(dot(p, vec3(12.9898, 78.233, 37.719))) * 43758.5453); }
      void main(){ float y = vD.y; vec3 c = y > 0.0 ? mix(uMid, uTop, pow(clamp(y, 0.0, 1.0), 0.6)) : mix(uMid, uBot, clamp(-y * 3.0, 0.0, 1.0));
        float s = max(dot(vD, uSun), 0.0); c += uSunCol * (smoothstep(1.0 - uSunSize, 1.0 - uSunSize * 0.5, s) * 2.5 + pow(s, 24.0) * 0.35 + pow(s, 4.0) * 0.12);
        if (uStars > 0.0) { vec3 q = floor(vD * 420.0); float st = step(0.9965, h(q)); c += vec3(st) * uStars * (0.5 + 0.5 * h(q + 3.1)); }
        gl_FragColor = vec4(c, 1.0); }` });
  const d = new THREE.Mesh(new THREE.SphereGeometry(300, 32, 16), m); d.renderOrder = -10; d.frustumCulled = false; group.add(d); return u;
}

// ---------------------------------------------------------------------------------------------------------------- une ville : matériaux, façades
function cityMats() {
  const M = {
    brick: mat4(brickTex(0xb5523a, 0x8a7a6a, 71), { rim: 0.3, wet: 0.2 }), brickD: mat4(brickTex(0x8a4a3a, 0x6a5a50, 72), { rim: 0.3, wet: 0.2 }),
    plaster: mat4(grunge(0xe2d6c0, { size: 32, noise: 0.06, dark: 0.07, seed: 73 }), { rim: 0.3, wet: 0.2 }),
    stone: mat4(tiles(0xcfc8b8, 0xc2baa8, { size: 32, n: 4, seed: 74, grout: 0x8a8272 }), { rim: 0.3, wet: 0.2 }),
    trim: mat4(grunge(0xf0ece0, { size: 16, noise: 0.05, dark: 0.05, seed: 75 }), { rim: 0.35 }),
    roofM: mat4(roofTex(0x5a5e68, 76), { rim: 0.3, wet: 0.2 }), roofR: mat4(roofTex(0x8a3a2c, 77), { rim: 0.3 }),
    asphalt: mat4(grunge(0x3a3c42, { size: 32, noise: 0.1, dark: 0.12, seed: 78 }), { rim: 0.2, wet: 0.4 }),
    walk: mat4(tiles(0xc8c4bc, 0xb6b2aa, { size: 32, n: 4, seed: 79, grout: 0x8a867e }), { rim: 0.2, wet: 0.2 }),
    plank: mat4(plankTex(0x9a6a3e, 80), { rim: 0.3, wet: 0.3 }), wood: mat4(grunge(0x6a4a2e, { size: 16, noise: 0.12, seed: 81 }), { rim: 0.4 }),
    metal: mat4(grunge(0x4a4e56, { size: 16, noise: 0.12, rust: 0.04, seed: 82 }), { rim: 0.6, shininess: 30, specular: 0x333333 }),
    dark: mat4(grunge(0x1a1c20, { size: 8, noise: 0.1, seed: 83 }), { rim: 0.3 }),
    tile: mat4(tiles(0xe8e4dc, 0x5a5a60, { size: 32, n: 4, seed: 84, grout: 0x3a3a40 }), { rim: 0.3, wet: 0.5 }),
    wall: mat4(grunge(0xd8cdb8, { size: 32, noise: 0.05, dark: 0.06, seed: 85 }), { rim: 0.25 }),
    conc: mat4(grunge(0x8a8c90, { size: 32, noise: 0.1, dark: 0.1, seed: 86 }), { rim: 0.25, wet: 0.2 }),
    pad: mat4(grunge(0x6a6e76, { size: 32, noise: 0.08, dark: 0.12, seed: 87 }), { rim: 0.3, wet: 0.3 }),
    hull: mat4(grunge(0xe4e8ee, { size: 16, noise: 0.05, dark: 0.06, seed: 88 }), { rim: 0.5, shininess: 40, specular: 0x555555 }),
  };
  M.glass = new THREE.MeshPhongMaterial({ color: 0x4a6a8a, transparent: true, opacity: 0.36, shininess: 120, specular: 0xffffff, side: THREE.DoubleSide, depthWrite: false });
  M.glassD = new THREE.MeshPhongMaterial({ color: 0x24384c, shininess: 90, specular: 0xaab8c8 });
  return M;
}
const WALLS = { brick: 'brick', brickD: 'brickD', plaster: 'plaster', stone: 'stone', conc: 'conc' };

// façade : o = { x0, x1, zf (plan de façade), dir (+1 : la façade regarde +z, le corps est derrière en -z), depth, floors, fh, gh (hauteur du rez), wall, tint, trim, roof, y0, far, seed, lit, sign, shop }
function building(ctx, o) {
  const { B, D, GL, LW1, LW2 } = ctx; const r = mulberry(o.seed ?? 1); const dir = o.dir ?? 1, y0 = o.y0 ?? 0, fh = o.fh ?? 3.3, gh = o.gh ?? 3.8, W = o.x1 - o.x0, cx = (o.x0 + o.x1) / 2;
  const H = gh + (o.floors - 1) * fh, wall = WALLS[o.wall ?? 'brick']; const zc = o.zf - dir * o.depth / 2; const Z = (off) => o.zf + dir * off;
  if (o.hollow) B.add({ x: cx, y: y0 + (gh + H) / 2, z: zc, w: W, h: H - gh, d: o.depth, mat: wall, tpm: 1, color: o.tint ?? 0xffffff });          // the ground floor is a real room, built apart: no solid block under the upper floors
  else B.add({ x: cx, y: y0 + H / 2, z: zc, w: W, h: H, d: o.depth, mat: wall, tpm: 1, color: o.tint ?? 0xffffff });
  const trimC = o.trim ?? 0xf0ece0;
  if (o.far) {          // silhouette lointaine : fenêtres en bandes lumineuses seulement
    const n = Math.max(2, Math.round(W / 3)); for (let f = 1; f < o.floors; f++) for (let k = 0; k < n; k++) { if (r() > (o.lit ?? 0.3)) continue; (r() < 0.5 ? LW1 : LW2).push({ x: o.x0 + (k + 0.5) * W / n, y: y0 + gh + (f - 1) * fh + fh * 0.5, z: Z(0.03), w: W / n * 0.5, h: fh * 0.45, d: 0.05, color: 0xffd890 }); }
    B.add({ x: cx, y: y0 + H + 0.15, z: zc, w: W + 0.4, h: 0.3, d: o.depth + 0.4, mat: 'roofM', tpm: 1 }); return H;
  }
  // étages : fenêtres
  const n = Math.max(2, Math.round(W / 3.0)), sp = W / n;
  for (let f = 1; f < o.floors; f++) {
    const yb = y0 + gh + (f - 1) * fh, wy = yb + fh * 0.5;
    for (let k = 0; k < n; k++) {
      const wx = o.x0 + (k + 0.5) * sp, ww = Math.min(1.3, sp * 0.45), wh = fh * 0.55; const lit = r() < (o.lit ?? 0.15);
      B.add({ x: wx, y: wy, z: Z(0.02), w: ww + 0.24, h: wh + 0.24, d: 0.08, mat: 'trim', tpm: 1, color: trimC });                      // encadrement
      (lit ? LW1 : GL).push({ x: wx, y: wy, z: Z(0.07), w: ww, h: wh, d: 0.03, color: lit ? 0xffd890 : 0x2a3c50 });
      D.push({ x: wx, y: wy, z: Z(0.09), w: 0.05, h: wh, d: 0.03, color: 0xe8e4d8 }, { x: wx, y: wy, z: Z(0.09), w: ww, h: 0.05, d: 0.03, color: 0xe8e4d8 });   // croisillons
      B.add({ x: wx, y: wy - wh / 2 - 0.16, z: Z(0.14), w: ww + 0.4, h: 0.1, d: 0.3, mat: 'trim', tpm: 1, color: trimC });               // appui
      B.add({ x: wx, y: wy + wh / 2 + 0.17, z: Z(0.1), w: ww + 0.44, h: 0.12, d: 0.2, mat: 'trim', tpm: 1, color: trimC });            // linteau
      const q = r();
      if (q < 0.22) { D.push({ x: wx - ww * 0.62, y: wy, z: Z(0.1), w: 0.22, h: wh + 0.1, d: 0.06, color: o.shutter ?? 0x3f6a58 }, { x: wx + ww * 0.62, y: wy, z: Z(0.1), w: 0.22, h: wh + 0.1, d: 0.06, color: o.shutter ?? 0x3f6a58 }); }
      else if (q < 0.42) {      // balcon + garde-corps
        D.push({ x: wx, y: wy - wh / 2 - 0.2, z: Z(0.42), w: ww + 0.9, h: 0.1, d: 0.8, color: 0xb8b4aa }); for (let i = 0; i <= 6; i++) D.push({ x: wx - (ww + 0.8) / 2 + i * (ww + 0.8) / 6, y: wy - wh / 2 + 0.15, z: Z(0.8), w: 0.04, h: 0.6, d: 0.04, color: 0x22252a });
        D.push({ x: wx, y: wy - wh / 2 + 0.47, z: Z(0.8), w: ww + 0.9, h: 0.05, d: 0.05, color: 0x22252a }, { x: wx - (ww + 0.8) / 2, y: wy - wh / 2 + 0.15, z: Z(0.6), w: 0.04, h: 0.6, d: 0.4, color: 0x22252a }, { x: wx + (ww + 0.8) / 2, y: wy - wh / 2 + 0.15, z: Z(0.6), w: 0.04, h: 0.6, d: 0.4, color: 0x22252a });
      } else if (q < 0.55) {    // jardinière fleurie
        D.push({ x: wx, y: wy - wh / 2 - 0.12, z: Z(0.22), w: ww + 0.2, h: 0.2, d: 0.26, color: 0x6a3a22 }); for (let i = 0; i < 5; i++) D.push({ x: wx - ww / 2 + i * ww / 4, y: wy - wh / 2 + 0.05, z: Z(0.22), w: 0.14, h: 0.2, d: 0.14, color: [0xd8344a, 0xf0c030, 0xe86aa8, 0x4a9a3a, 0xf0f0f0][(r() * 5) | 0] });
      }
    }
    if (f === 1) B.add({ x: cx, y: yb - 0.08, z: Z(0.1), w: W + 0.3, h: 0.16, d: 0.24, mat: 'trim', tpm: 1, color: trimC });          // bandeau d'étage
  }
  // corniche, parapet, toit
  B.add({ x: cx, y: y0 + H + 0.05, z: Z(0.0), w: W + 0.4, h: 0.3, d: 0.6, mat: 'trim', tpm: 1, color: trimC });
  if (o.roof === 'mansard') { const rz = zc; B.add({ x: cx, y: y0 + H + 0.9, z: Z(-0.5), w: W - 0.2, h: 1.5, d: o.depth - 0.6, mat: 'roofM', tpm: 1 }); for (let k = 0; k < Math.max(2, n - 1); k++) { const lx = o.x0 + (k + 1) * W / Math.max(2, n - 1) / 1 * (W / (W)) ; if (lx > o.x1 - 1) break; D.push({ x: o.x0 + (k + 0.5) * W / Math.max(2, n - 1), y: y0 + H + 0.9, z: Z(-0.45), w: 1.0, h: 1.0, d: 0.5, color: 0x6a6e78 }); GL.push({ x: o.x0 + (k + 0.5) * W / Math.max(2, n - 1), y: y0 + H + 0.9, z: Z(-0.19), w: 0.6, h: 0.6, d: 0.03, color: 0x2a3c50 }); } }
  else { B.add({ x: cx, y: y0 + H + 0.45, z: zc, w: W, h: 0.5, d: o.depth, mat: 'conc', tpm: 1 }); D.push({ x: cx, y: y0 + H + 0.5, z: Z(-0.12), w: W - 0.1, h: 0.9, d: 0.2, color: 0xcfc8b8 });
    for (let k = 0; k < 2; k++) D.push({ x: o.x0 + 1.5 + r() * (W - 3), y: y0 + H + 1.1, z: zc + (r() - 0.5) * (o.depth - 2), w: 1.1, h: 0.7, d: 0.8, color: 0xa8acb4 });             // climatiseurs
    if (r() < 0.5) D.push({ x: o.x0 + 1 + r() * (W - 2), y: y0 + H + 1.6, z: zc, w: 0.6, h: 2.0, d: 0.6, color: 0x7a3a2a });                                                  // cheminée
  }
  // rez-de-chaussée
  if (o.shop !== false) shopFront(ctx, o, { r, dir, Z, gh, W, y0, trimC });
  return H;
}
function shopFront(ctx, o, k) {
  const { B, D, GL, LW1, extras } = ctx; const s = o.shop || {}; const { r, dir, Z, gh, W, y0, trimC } = k; const cx = (o.x0 + o.x1) / 2;
  B.add({ x: cx, y: y0 + 0.3, z: Z(0.06), w: W, h: 0.6, d: 0.14, mat: 'stone', tpm: 1 });                                                    // soubassement
  const doorX = o.x0 + (s.door ?? 0.3) * W, dw = 1.15; const gw = (W - 1.2);
  const segs = [[o.x0 + 0.6, doorX - dw / 2 - 0.1], [doorX + dw / 2 + 0.1, o.x1 - 0.6]];
  for (const [a, b] of segs) { if (b - a < 0.6) continue; GL.push({ x: (a + b) / 2, y: y0 + 1.75, z: Z(0.07), w: b - a, h: 2.1, d: 0.04, color: s.glass ?? 0x4a6270, big: true });
    const m = Math.max(1, Math.round((b - a) / 1.6)); for (let i = 0; i <= m; i++) D.push({ x: a + i * (b - a) / m, y: y0 + 1.75, z: Z(0.1), w: 0.07, h: 2.15, d: 0.08, color: s.frame ?? 0x2a2c30 }); D.push({ x: (a + b) / 2, y: y0 + 2.83, z: Z(0.1), w: b - a, h: 0.07, d: 0.08, color: s.frame ?? 0x2a2c30 }); }
  D.push({ x: doorX - dw / 2 - 0.05, y: y0 + 1.15, z: Z(0.1), w: 0.1, h: 2.3, d: 0.14, color: s.frame ?? 0x2a2c30 }, { x: doorX + dw / 2 + 0.05, y: y0 + 1.15, z: Z(0.1), w: 0.1, h: 2.3, d: 0.14, color: s.frame ?? 0x2a2c30 }, { x: doorX, y: y0 + 2.3, z: Z(0.1), w: dw + 0.2, h: 0.1, d: 0.14, color: s.frame ?? 0x2a2c30 });
  if (!s.noDoor) { D.push({ x: doorX, y: y0 + 1.1, z: Z(0.06), w: dw - 0.1, h: 2.1, d: 0.06, color: s.doorCol ?? 0x3a5a6a }); GL.push({ x: doorX, y: y0 + 1.4, z: Z(0.1), w: dw - 0.4, h: 1.3, d: 0.03, color: 0x4a6a80 }); D.push({ x: doorX + dw / 2 - 0.18, y: y0 + 1.05, z: Z(0.15), w: 0.04, h: 0.35, d: 0.06, color: 0xd8c070 }); }
  if (s.name) {                                                                                                                              // enseigne
    const sg = signPlane(s.name, Math.min(W - 1.0, 4.2), 0.7, { bg: s.bg ?? '#1c2a3a', col: s.fg ?? '#f4ecd8', px: 384, border: s.fg ?? '#f4ecd8' }); sg.position.set(cx, y0 + gh - 0.45, Z(0.14)); if (dir < 0) sg.rotation.y = Math.PI; extras.push(sg);
  }
  if (s.awning) {                                                                                                                            // store à rayures
    const [c1, c2] = s.awning, L = W - 0.4, n = Math.round(L / 0.5); for (let i = 0; i < n; i++) D.push({ x: o.x0 + 0.2 + (i + 0.5) * L / n, y: y0 + 2.95 - 0.05, z: Z(0.95), w: L / n, h: 0.07, d: 1.9, color: i % 2 ? c1 : c2, rx: -dir * 0.2 });
    D.push({ x: cx, y: y0 + 2.62, z: Z(1.82), w: L, h: 0.32, d: 0.04, color: s.awning[0] });
  }
  if (s.cross) { const z = Z(0.2); for (const [dx, dy, w, h] of [[0, 0, 0.5, 0.15], [0, 0, 0.15, 0.5]]) { const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, 0.08), new THREE.MeshBasicMaterial({ color: new THREE.Color(0x30e070).multiplyScalar(2.2) })); m.position.set(o.x1 - 0.9 + dx, y0 + gh + 0.5 + dy, z); extras.push(m); } }
}

// ---------------------------------------------------------------------------------------------------------------- mobilier de rue
function tree(D, x, z, h, r, rnd, trunk = 0x5a3a22, leaf = [0x3a8a3a, 0x4a9a3a, 0x2f7a34]) {
  D.push({ x, y: h * 0.45, z, w: 0.3, h: h * 0.9, d: 0.3, color: trunk }, { x, y: 0.28, z, w: 0.9, h: 0.56, d: 0.9, color: 0x6a5a4a }, { x, y: 0.58, z, w: 0.8, h: 0.06, d: 0.8, color: 0x2a2018 });
  const cy = h + r * 0.25, st = 0.45;
  for (let dx = -r; dx <= r + 1e-6; dx += st) for (let dy = -r * 0.8; dy <= r * 0.85; dy += st) for (let dz = -r; dz <= r + 1e-6; dz += st) { const q = (dx * dx + dz * dz) / (r * r) + dy * dy / (r * r * 0.7); if (q > 1 || q < 0.35) continue; if (q > 0.8 && rnd() < 0.35) continue; const s = st * (1 + rnd() * 0.25); D.push({ x: x + dx, y: cy + dy, z: z + dz, w: s, h: s, d: s, color: sh(leaf[(rnd() * leaf.length) | 0], 0.8 + rnd() * 0.35).getHex() }); }
  D.push({ x, y: cy, z, w: r * 1.2, h: r, d: r * 1.2, color: sh(leaf[0], 0.5).getHex() });
}
function lamp(D, x, z, dir, bulbs) { D.push({ x, y: 2.5, z, w: 0.14, h: 5, d: 0.14, color: 0x2a2c30 }, { x, y: 5.05, z: z + dir * 0.5, w: 0.1, h: 0.1, d: 1.0, color: 0x2a2c30 }, { x, y: 4.95, z: z + dir * 0.95, w: 0.36, h: 0.14, d: 0.32, color: 0x3a3c40 }, { x, y: 0.15, z, w: 0.4, h: 0.3, d: 0.4, color: 0x2a2c30 }); bulbs.push({ x, y: 4.86, z: z + dir * 0.95, w: 0.26, h: 0.06, d: 0.24, color: 0xfff0c0 }); }
function carBoxes(x, z, col, ry = 0, big = false) {
  const L = big ? 5.2 : 3.9, H = big ? 1.9 : 1.2; const B = [{ x: 0, y: 0.55, z: 0, w: L, h: 0.6, d: 1.7, color: col }, { x: big ? 0.4 : -0.2, y: 1.05, z: 0, w: big ? L - 0.8 : 2.1, h: big ? 1.1 : 0.5, d: 1.55, color: sh(col, 0.96).getHex() },
    { x: -0.2, y: 1.06, z: 0.78, w: big ? 3.6 : 1.9, h: 0.38, d: 0.03, color: 0x1e2a36 }, { x: -0.2, y: 1.06, z: -0.78, w: big ? 3.6 : 1.9, h: 0.38, d: 0.03, color: 0x1e2a36 }, { x: L / 2 - 0.1, y: 0.66, z: 0.58, w: 0.04, h: 0.16, d: 0.3, color: 0xfff2d0 }, { x: L / 2 - 0.1, y: 0.66, z: -0.58, w: 0.04, h: 0.16, d: 0.3, color: 0xfff2d0 },
    { x: -L / 2 + 0.1, y: 0.66, z: 0.58, w: 0.04, h: 0.14, d: 0.3, color: 0xc02020 }, { x: -L / 2 + 0.1, y: 0.66, z: -0.58, w: 0.04, h: 0.14, d: 0.3, color: 0xc02020 }];
  for (const [wx, wz] of [[L * 0.3, 0.84], [L * 0.3, -0.84], [-L * 0.3, 0.84], [-L * 0.3, -0.84]]) B.push({ x: wx, y: 0.32, z: wz, w: 0.66, h: 0.66, d: 0.26, color: 0x151517 });
  const c = Math.cos(ry), s = Math.sin(ry); return B.map((b) => ({ ...b, x: x + b.x * c + b.z * s, z: z - b.x * s + b.z * c, ry }));
}
function table(D, x, z, o = {}) {
  const h = o.h ?? 0.75, w = o.w ?? 0.8; D.push({ x, y: h, z, w, h: 0.05, d: o.d ?? w, color: o.top ?? 0xd8c8a8 }, { x, y: h / 2, z, w: 0.08, h: h, d: 0.08, color: 0x3a3a40 }, { x, y: 0.03, z, w: w * 0.55, h: 0.05, d: w * 0.55, color: 0x3a3a40 });
  for (const [dx, dz, ry] of o.chairs ?? []) chair(D, x + dx, z + dz, ry, o.chairCol ?? 0x7a4a2a);
}
function chair(D, x, z, ry, col = 0x7a4a2a) {
  const c = Math.cos(ry), s = Math.sin(ry); const P = (bx, by, bz, w, h, d, cc) => ({ x: x + bx * c + bz * s, y: by, z: z - bx * s + bz * c, w, h, d, color: cc, ry });
  D.push(P(0, 0.45, 0, 0.42, 0.05, 0.42, col), P(0, 0.75, -0.2, 0.42, 0.55, 0.05, col)); for (const [lx, lz] of [[-.18, -.18], [.18, -.18], [-.18, .18], [.18, .18]]) D.push(P(lx, 0.22, lz, 0.05, 0.44, 0.05, 0x2a2420));
}
function stool(D, x, z, col = 0x8a2a2a) { D.push({ x, y: 0.7, z, w: 0.38, h: 0.07, d: 0.38, color: col }, { x, y: 0.35, z, w: 0.06, h: 0.7, d: 0.06, color: 0x3a3a40 }, { x, y: 0.03, z, w: 0.34, h: 0.05, d: 0.34, color: 0x3a3a40 }); }
function umbrella(D, x, z, col1, col2) { D.push({ x, y: 1.2, z, w: 0.05, h: 2.4, d: 0.05, color: 0x3a3a3a }); for (let i = 0; i < 8; i++) { const a = i / 8 * 6.283; D.push({ x: x + Math.cos(a) * 0.9, y: 2.3, z: z + Math.sin(a) * 0.9, w: 1.0, h: 0.06, d: 1.0, color: i % 2 ? col1 : col2, ry: -a }); } D.push({ x, y: 2.42, z, w: 0.9, h: 0.08, d: 0.9, color: col1 }); }

// ---------------------------------------------------------------------------------------------------------------- la cité
function buildCite(ctx0, origin) {
  const { scene } = ctx0; const group = new THREE.Group(); group.position.copy(origin); scene.add(group);
  const root = new THREE.Group(); root.position.set(CX, 0, 0); group.add(root);
  const M = cityMats(); const B = new Batch(); const D = [], GL = [], LW1 = [], LW2 = [], bulbs = [], extras = []; const ctx = { B, D, GL, LW1, LW2, extras }; const r = mulberry(55);
  const sky_ = sky(group, { top: 0x4a86e0, mid: 0xbcd6f4, bot: 0xb0c4d8, sun: [-0.55, 0.5, -0.65], sunCol: 0xfff0c8 });
  // ---- sol
  B.add({ x: 0, y: -0.2, z: 0, w: 260, h: 0.4, d: 160, mat: 'asphalt', tpm: 0.6 });
  B.add({ x: 0, y: 0.01, z: -3.5, w: 130, h: 0.04, d: 4.0, mat: 'walk', tpm: 0.5 }); B.add({ x: 0, y: 0.01, z: 7.5, w: 130, h: 0.04, d: 4.0, mat: 'walk', tpm: 0.5 });          // trottoirs (au ras de la chaussée : pas de marche)
  B.add({ x: 0, y: 0.02, z: -1.5, w: 130, h: 0.06, d: 0.18, mat: 'conc', tpm: 1 }); B.add({ x: 0, y: 0.02, z: 5.5, w: 130, h: 0.06, d: 0.18, mat: 'conc', tpm: 1 });                      // bordures peintes
  for (let x = -60; x < 60; x += 4) D.push({ x, y: 0.045, z: 2.0, w: 1.8, h: 0.02, d: 0.14, color: 0xf0eee2 });                                                                     // axe
  for (const cxw of [-24, 24]) for (let i = 0; i < 7; i++) D.push({ x: cxw, y: 0.045, z: -1.1 + i * 0.95, w: 3.2, h: 0.02, d: 0.5, color: 0xf2f0e6 });                                    // passages piétons (bandes le long de x)
  for (let x = -58; x < 58; x += 9) D.push({ x, y: 0.045, z: 3.6, w: 0.5, h: 0.02, d: 0.5, color: 0x2a2c30 });                                                                       // plaques
  // ---- façades nord (z = -5.5, face à +z)
  const NZ = -5.5; const bld = (o) => building(ctx, { zf: NZ, dir: 1, depth: 12, seed: (o.x0 | 0) + 100, ...o });
  bld({ x0: -44, x1: -30, floors: 6, wall: 'brick', tint: 0xffffff, lit: 0.12, shop: { name: 'BOULANGERIE', bg: '#7a3a22', fg: '#fff2d0', awning: [0xe8d8b0, 0xb83a2a], door: 0.7 }, roof: 'flat' });
  bld({ x0: -30, x1: -16, floors: 5, wall: 'plaster', tint: 0xf0e2c0, lit: 0.12, shutter: 0x3f6a58, shop: { name: 'LIBRAIRIE', bg: '#1f3a2e', fg: '#f0e8c0', door: 0.35, frame: 0x1a2a22 }, roof: 'mansard' });
  bld({ x0: -16, x1: -10.4, floors: 5, wall: 'stone', tint: 0xf4efe0, lit: 0.1, shop: { name: 'PHARMACIE', bg: '#14452c', fg: '#f4fff4', door: 0.5, cross: true, frame: 0x1a2a22 }, roof: 'flat', depth: 30 });
  // café : corps en deux étages au-dessus d'un rez vitré (le rez est construit à part, praticable)
  const CAFE = { x0: -8, x1: 8 };
  bld({ ...CAFE, floors: 3, wall: 'brick', tint: 0xf0d8c0, lit: 0.1, gh: 4.4, shop: false, roof: 'mansard', trim: 0xf4efe0, shutter: 0x6a2a2a, hollow: true });
  bld({ x0: 8, x1: 20, floors: 5, wall: 'stone', tint: 0xf0ead8, lit: 0.1, shop: { name: 'BANQUE DU PORT', bg: '#222a40', fg: '#e8d8a0', door: 0.5, frame: 0x30323a, noDoor: false }, roof: 'flat', trim: 0xfaf4e4 });
  bld({ x0: 20, x1: 31, floors: 5, wall: 'plaster', tint: 0xc8dcea, lit: 0.12, shutter: 0x2a4a7a, shop: { name: 'FLEURS & CIE', bg: '#5a2a4a', fg: '#ffe8f4', awning: [0xe86aa8, 0xf4e8f0], door: 0.4 }, roof: 'mansard' });
  bld({ x0: 31, x1: 46, floors: 11, wall: 'conc', tint: 0xb8c8d8, lit: 0.25, shop: { name: 'OBSERVATOIRE', bg: '#202838', fg: '#a8d8ff', door: 0.5, frame: 0x2a3040 }, roof: 'flat', fh: 3.2 });
  // le fond de la ruelle et l'arrière-café (le monde est fermé : aucun vide)
  B.add({ x: -9.2, y: 4, z: -34.8, w: 2.6, h: 8, d: 0.4, mat: 'brickD', tpm: 1 });
  bld({ x0: -8, x1: 8, zf: -15.6, floors: 4, depth: 18, wall: 'brickD', shop: false, lit: 0, seed: 7 });
  bld({ x0: -60, x1: -44, floors: 5, wall: 'plaster', tint: 0xe8d8c0, lit: 0.1, shop: { name: 'TABAC', bg: '#2a1a12', fg: '#f0d890', door: 0.5 } }); bld({ x0: 46, x1: 62, floors: 7, wall: 'brick', tint: 0xe0d0c0, lit: 0.12, shop: { name: 'CINÉMA', bg: '#2a1020', fg: '#ffd8a0', door: 0.5, awning: [0xc02a3a, 0xf0e0d0] } });
  // ---- façades sud (z = 9.5, face à -z)
  const SZ = 9.5; const sb = (o) => building(ctx, { zf: SZ, dir: -1, depth: 10, seed: (o.x0 | 0) + 300, ...o });
  sb({ x0: -50, x1: -34, floors: 4, wall: 'brick', tint: 0xe8c8b0, lit: 0.12, shop: { name: 'ÉPICERIE', bg: '#2a4a22', fg: '#fff0c0', awning: [0x3a8a3a, 0xf0f0e0], door: 0.5 } });
  sb({ x0: -34, x1: -18, floors: 3, wall: 'plaster', tint: 0xf0d8a0, lit: 0.12, shop: { name: 'MARCHÉ COUVERT', bg: '#4a2a1a', fg: '#ffe0a0', door: 0.5, awning: [0xd8a030, 0xf4ecd0] } });
  sb({ x0: -18, x1: -2, floors: 5, wall: 'stone', tint: 0xdcd4c4, lit: 0.12, shop: { name: 'HÔTEL DES VOYAGES', bg: '#1c2a44', fg: '#f0e0a8', door: 0.5, frame: 0x2a2a30 }, roof: 'mansard' });
  sb({ x0: -2, x1: 14, floors: 4, wall: 'brick', tint: 0xf0c8c0, lit: 0.12, shop: { name: 'CRÊPERIE', bg: '#5a1f1a', fg: '#fff0d8', awning: [0xe8d048, 0xb83a2a], door: 0.4 } });
  sb({ x0: 14, x1: 32, floors: 6, wall: 'plaster', tint: 0xc8d4e0, lit: 0.12, shop: { name: 'LIBRE-SERVICE', bg: '#1a3a4a', fg: '#d8f4ff', door: 0.5 } }); sb({ x0: 32, x1: 62, floors: 4, wall: 'brick', tint: 0xe0d0c0, lit: 0.12, shop: false });
  // ---- skyline lointaine (silhouettes, fenêtres allumées en bandes)
  for (let i = 0; i < 14; i++) { const x0 = -90 + i * 14 + r() * 4, w = 9 + r() * 6; building(ctx, { x0, x1: x0 + w, zf: -44 - r() * 10, dir: 1, depth: 14, floors: 8 + (r() * 12 | 0), fh: 3.2, gh: 3.4, wall: 'conc', tint: [0xb8c4d0, 0xc8c0b8, 0xa8b4c0][i % 3], far: true, lit: 0.35, seed: 400 + i }); }
  for (let i = 0; i < 12; i++) { const x0 = -90 + i * 16 + r() * 4, w = 10 + r() * 6; building(ctx, { x0, x1: x0 + w, zf: 40 + r() * 8, dir: -1, depth: 14, floors: 6 + (r() * 10 | 0), fh: 3.2, gh: 3.4, wall: 'conc', tint: [0xb8c4d0, 0xc8c0b8, 0xa8b4c0][i % 3], far: true, lit: 0.35, seed: 500 + i }); }
  // ---- la tour de l'horloge (sur la banque) : base, fût, cadran nord
  const tx = 14, tz = -9, tH = 7; B.add({ x: tx, y: 20 + tH / 2 - 3.5, z: tz, w: 3.6, h: tH, d: 3.6, mat: 'stone', tpm: 1 }); B.add({ x: tx, y: 20 + tH - 3.5 + 1.1, z: tz, w: 4.2, h: 0.35, d: 4.2, mat: 'trim', tpm: 1 });
  B.add({ x: tx, y: 20 + tH - 3.5 + 2.8, z: tz, w: 3.0, h: 3.0, d: 3.0, mat: 'roofM', tpm: 1 }); D.push({ x: tx, y: 20 + tH - 3.5 + 5, z: tz, w: 0.4, h: 2.4, d: 0.4, color: 0x8a8e98 });
  // ---- rues, mobilier
  for (let x = -54; x <= 54; x += 11) { lamp(D, x, -2.0, -1, bulbs); lamp(D, x + 5.5, 6.0, 1, bulbs); }
  for (const x of [-40, -27, -13, 12, 27, 41]) tree(D, x, -1.0, 3.6, 1.3, r);
  for (const x of [-46, -31, -8, 3, 20, 36]) tree(D, x, 6.3, 3.6, 1.3, r, 0x4a3a28, [0x5a8a3a, 0x6a9a3a, 0x3f7a34]);
  for (const x of [-15, 22, -36]) { D.push({ x, y: 0.45, z: 8.7, w: 1.6, h: 0.08, d: 0.5, color: 0x6a4a2a }, { x, y: 0.8, z: 9.0, w: 1.6, h: 0.5, d: 0.08, color: 0x6a4a2a }, { x: x - 0.7, y: 0.22, z: 8.7, w: 0.08, h: 0.44, d: 0.4, color: 0x2a2c30 }, { x: x + 0.7, y: 0.22, z: 8.7, w: 0.08, h: 0.44, d: 0.4, color: 0x2a2c30 }); }
  for (const x of [-12.5, 17, 38]) D.push({ x, y: 0.5, z: -5.0, w: 0.5, h: 1.0, d: 0.5, color: 0x2a4a3a }, { x, y: 1.02, z: -5.0, w: 0.56, h: 0.06, d: 0.56, color: 0x1a2a22 });
  D.push({ x: -10.8, y: 0.4, z: 6.0, w: 0.3, h: 0.8, d: 0.3, color: 0xc02a2a }, { x: 30, y: 0.4, z: 6.3, w: 0.3, h: 0.8, d: 0.3, color: 0xc02a2a });
  // abribus (sud, x 24..28)
  for (const dx of [24, 28.2]) D.push({ x: dx, y: 1.25, z: 6.3, w: 0.08, h: 2.5, d: 0.08, color: 0x2a2c30 }); D.push({ x: 26.1, y: 2.55, z: 6.9, w: 4.6, h: 0.1, d: 2.0, color: 0x2a2c30 }, { x: 26.1, y: 0.5, z: 7.5, w: 3.8, h: 0.06, d: 0.5, color: 0x8a6a3a });
  GL.push({ x: 26.1, y: 1.35, z: 7.9, w: 4.0, h: 1.9, d: 0.03, color: 0x6a8aaa });
  // marché : étals sur le trottoir sud (x -30..-18)
  for (let i = 0; i < 4; i++) { const x = -30 + i * 3.4, c1 = [0xd8342a, 0x3a8a3a, 0xe8b02a, 0x2a6ac8][i], z0 = 8.0;
    D.push({ x, y: 0.5, z: z0, w: 2.6, h: 0.08, d: 1.1, color: 0x8a6a3a }, { x: x - 1.2, y: 0.25, z: z0, w: 0.1, h: 0.5, d: 1.0, color: 0x5a4a2a }, { x: x + 1.2, y: 0.25, z: z0, w: 0.1, h: 0.5, d: 1.0, color: 0x5a4a2a });
    for (const dx of [-1.25, 1.25]) D.push({ x: x + dx, y: 1.3, z: z0 - 0.5, w: 0.06, h: 2.6, d: 0.06, color: 0x3a2a1a });
    for (let k = 0; k < 6; k++) D.push({ x: x - 1.0 + k * 0.4, y: 2.62 - k * 0.0, z: z0 - 0.1, w: 0.4, h: 0.06, d: 1.5, color: k % 2 ? c1 : 0xf4f0e4, rx: 0.12 });
    for (let k = 0; k < 14; k++) D.push({ x: x - 1.1 + (k % 7) * 0.36, y: 0.62 + (k / 7 | 0) * 0.14, z: z0 - 0.15 + (k / 7 | 0) * 0.3, w: 0.26, h: 0.2, d: 0.26, color: [0xd8342a, 0xf0a020, 0x6aaa2a, 0xe8d040][(r() * 4) | 0] }); }
  // terrasse du café : tables, chaises, parasols (au nord, z -5.5..-1.5)
  const TERR = [[-3.1, -3.0], [-0.2, -3.5], [2.6, -3.1]];
  TERR.forEach(([x, z], i) => { table(D, x, z, { w: 0.8, h: 1.05, top: [0xd8c8a8, 0xe8e0d0][i % 2] }); D.push({ x: x + 0.12, y: 1.1, z: z + 0.05, w: 0.14, h: 0.1, d: 0.14, color: 0xf0f0f0 }); });
  umbrella(D, -3.1, -3.0, 0xc02a2a, 0xf4ecd8); umbrella(D, 2.6, -3.1, 0x2a5a9a, 0xf4ecd8);
  for (let i = 0; i < 7; i++) D.push({ x: -7.8 + i * 2.6, y: 0.5, z: -1.9, w: 0.5, h: 0.5, d: 0.5, color: 0x6a4a2a }, { x: -7.8 + i * 2.6, y: 1.0, z: -1.9, w: 0.46, h: 0.5, d: 0.46, color: 0x3f8a3a });          // jardinières (la terrasse est fermée côté route)
  // voitures garées (sud, voie lente z 4.4) ; la voie nord (z 0.8) est celle des véhicules en mouvement
  const parked = [[-34, 4.5, 0xc83030], [-8, 4.5, 0xe8e4dc], [6, 4.5, 0x2a5ab0], [34, 4.5, 0x2a8a5a], [46, 4.5, 0xd8b030]]; for (const [x, z, c] of parked) D.push(...carBoxes(x, z, c, 0));
  const bigVan = vox(carBoxes(0, 0, 0xe8e8ec, 0, true)); root.add(bigVan);
  // un abri de ruelle : bennes, caisses, tuyaux, escalier de secours (mur est de la pharmacie)
  D.push({ x: -9.2, y: 0.6, z: -20, w: 0.9, h: 1.2, d: 2.2, color: 0x2a5a3a }, { x: -9.2, y: 1.25, z: -20, w: 1.0, h: 0.1, d: 2.3, color: 0x1a3a26 });
  for (let i = 0; i < 4; i++) D.push({ x: -8.7 - (i % 2) * 0.5, y: 0.25 + (i >> 1) * 0.5, z: -14.5 - i * 0.3, w: 0.8, h: 0.5, d: 0.8, color: 0x8a6a3a });
  for (let i = 0; i < 9; i++) D.push({ x: -10.3, y: 3 + i * 0.55, z: -12 - i * 0.5, w: 0.5, h: 0.08, d: 0.55, color: 0x2a2c30 }); D.push({ x: -10.3, y: 4.5, z: -16, w: 0.5, h: 3, d: 0.05, color: 0x2a2c30 });
  D.push({ x: -8.2, y: 5, z: -22, w: 0.14, h: 10, d: 0.14, color: 0x6a6e76 }, { x: -10.2, y: 4, z: -26, w: 0.14, h: 8, d: 0.14, color: 0x6a6e76 });
  // monte-charge au fond de la ruelle : encadrement, indicateur d'étage, porte coulissante
  D.push({ x: -10.3, y: 1.2, z: -34.5, w: 0.2, h: 2.5, d: 0.3, color: 0x3a3e46 }, { x: -8.1, y: 1.2, z: -34.5, w: 0.2, h: 2.5, d: 0.3, color: 0x3a3e46 }, { x: -9.2, y: 2.55, z: -34.5, w: 2.4, h: 0.2, d: 0.3, color: 0x3a3e46 });
  const liftDoorL = vox([{ x: 0, y: 1.1, z: 0, w: 1.05, h: 2.2, d: 0.08, color: 0x8a8e96 }], { rim: 0.6 }), liftDoorR = vox([{ x: 0, y: 1.1, z: 0, w: 1.05, h: 2.2, d: 0.08, color: 0x7a7e86 }], { rim: 0.6 }); root.add(liftDoorL, liftDoorR);
  const liftLamp = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.18, 0.06), new THREE.MeshBasicMaterial({ color: new THREE.Color(0xffa030).multiplyScalar(2) })); liftLamp.position.set(-9.2, 2.8, -34.4); root.add(liftLamp);
  const liftSign = signPlane(['MONTE-CHARGE', 'ACCÈS TOIT'], 1.8, 0.5, { bg: '#e8c020', col: '#1a1a1a', px: 256 }); liftSign.position.set(-9.2, 3.15, -34.33); root.add(liftSign);

  // ---- l'intérieur du café
  const CZ0 = -15.4, CZ1 = -5.9, CXW = 7.8; const CH = 4.1;
  B.add({ x: 0, y: -0.02, z: (CZ0 + CZ1) / 2, w: 2 * CXW, h: 0.06, d: CZ1 - CZ0, mat: 'plank', tpm: 0.5 });                                      // plancher
  B.add({ x: 0, y: CH + 0.1, z: (CZ0 + CZ1) / 2, w: 2 * CXW + 0.4, h: 0.2, d: CZ1 - CZ0 + 0.3, mat: 'plaster', tpm: 0.5 });                       // plafond
  for (let x = -6; x <= 6; x += 3) B.add({ x, y: CH - 0.12, z: (CZ0 + CZ1) / 2, w: 0.22, h: 0.24, d: CZ1 - CZ0, mat: 'wood', tpm: 1 });          // poutres
  B.add({ x: -CXW - 0.1, y: CH / 2, z: (CZ0 + CZ1) / 2, w: 0.2, h: CH, d: CZ1 - CZ0, mat: 'wall', tpm: 0.5 }); B.add({ x: CXW + 0.1, y: CH / 2, z: (CZ0 + CZ1) / 2, w: 0.2, h: CH, d: CZ1 - CZ0, mat: 'wall', tpm: 0.5 });
  B.add({ x: 0, y: CH / 2, z: CZ0 - 0.1, w: 2 * CXW + 0.4, h: CH, d: 0.2, mat: 'wall', tpm: 0.5 });
  for (const sx of [-1, 1]) B.add({ x: sx * (CXW - 0.03), y: 0.55, z: (CZ0 + CZ1) / 2, w: 0.06, h: 1.1, d: CZ1 - CZ0, mat: 'tile', tpm: 0.5 });  // lambris carrelé
  B.add({ x: 0, y: 0.55, z: CZ0 + 0.03, w: 2 * CXW, h: 1.1, d: 0.06, mat: 'tile', tpm: 0.5 });
  // façade vitrée du rez (z = -5.8) : soubassement, montants, grandes vitres, porte (x 4.0..5.2), linteau, enseigne
  const FZ = -5.8; B.add({ x: 0, y: 0.35, z: FZ, w: 2 * CXW + 0.4, h: 0.7, d: 0.3, mat: 'wood', tpm: 1 }); B.add({ x: 0, y: CH + 0.12, z: FZ, w: 2 * CXW + 0.4, h: 0.5, d: 0.34, mat: 'wood', tpm: 1 });
  for (const x of [-7.8, -4.4, -1.0, 2.4, 3.9, 5.3, 6.6, 7.8]) D.push({ x, y: CH / 2 + 0.35, z: FZ, w: 0.14, h: CH - 0.4, d: 0.2, color: 0x3a2418 });
  D.push({ x: 4.6, y: 2.45, z: FZ, w: 1.5, h: 0.12, d: 0.2, color: 0x3a2418 });
  GL.push({ x: -2.9, y: 2.3, z: FZ, w: 9.8, h: 3.2, d: 0.04, color: 0x6a8aa8, big: true }, { x: 6.6 + 0.05, y: 2.3, z: FZ, w: 1.4, h: 3.2, d: 0.04, color: 0x6a8aa8, big: true }, { x: 4.6, y: 3.3, z: FZ, w: 1.3, h: 1.2, d: 0.04, color: 0x6a8aa8, big: true });
  D.push({ x: -2.9, y: 1.1, z: FZ + 0.02, w: 9.8, h: 0.05, d: 0.06, color: 0x3a2418 });
  for (const [x, t] of [[-6, 'CAFÉ'], [-2, 'RELAIS']]) { }
  const cafeSign = signPlane('LE RELAIS DES CHEVALIERS', 6.4, 0.78, { bg: '#2a1810', col: '#f4d890', px: 512, border: '#c8a050' }); cafeSign.position.set(-2.4, CH + 0.12, FZ + 0.2); extras.push(cafeSign);
  for (let i = 0; i < 12; i++) D.push({ x: -7.5 + i * 0.7, y: CH - 0.05 + 0.0, z: FZ + 0.9, w: 0.7, h: 0.06, d: 1.8, color: i % 2 ? 0x2a6a4a : 0xf0e8d0, rx: -0.18 });                                              // store du café
  // bar : comptoir en bois sombre + dessus clair, arrière-bar : étagères, bouteilles, miroir ; tabourets
  const BZ = -13.6; D.push({ x: -1.5, y: 0.55, z: BZ, w: 7.4, h: 1.1, d: 0.9, color: 0x4a2a18 }, { x: -1.5, y: 1.13, z: BZ, w: 7.7, h: 0.08, d: 1.15, color: 0xd8c8a8 }, { x: 2.35, y: 0.55, z: BZ + 1.6, w: 0.9, h: 1.1, d: 3.3, color: 0x4a2a18 }, { x: 2.35, y: 1.13, z: BZ + 1.6, w: 1.15, h: 0.08, d: 3.5, color: 0xd8c8a8 });
  for (let i = 0; i < 6; i++) stool(D, -4.2 + i * 1.15, BZ + 1.2, i % 2 ? 0x8a2a2a : 0x2a4a7a);
  D.push({ x: -1.5, y: 2.2, z: CZ0 + 0.3, w: 7.2, h: 1.9, d: 0.06, color: 0x9ab8c8 }, { x: -1.5, y: 2.2, z: CZ0 + 0.26, w: 7.4, h: 2.1, d: 0.04, color: 0x4a2a18 });   // miroir
  for (let lv = 0; lv < 3; lv++) { D.push({ x: -1.5, y: 1.35 + lv * 0.6, z: CZ0 + 0.4, w: 7.0, h: 0.05, d: 0.3, color: 0x6a4a2a }); for (let k = 0; k < 20; k++) D.push({ x: -4.8 + k * 0.33, y: 1.6 + lv * 0.6, z: CZ0 + 0.4, w: 0.12, h: 0.38 + (k % 3) * 0.06, d: 0.12, color: [0x2a6a3a, 0x8a3a1a, 0xc8a030, 0x3a4a8a, 0x6a2a4a][(k + lv) % 5] }); }
  D.push({ x: -3.2, y: 1.35, z: BZ, w: 0.9, h: 0.5, d: 0.5, color: 0xb0b4bc }, { x: -3.2, y: 1.7, z: BZ, w: 0.5, h: 0.22, d: 0.4, color: 0x4a4e56 }, { x: 0.4, y: 1.25, z: BZ + 0.05, w: 0.6, h: 0.28, d: 0.5, color: 0xd8d0c0 });         // machine à café, caisse
  // salle : 5 tables rondes (carrées ici) et chaises
  const TAB = [[-4.4, -8.6], [-0.4, -7.4], [2.6, -7.8], [4.6, -11.2], [6.3, -8.2]];
  TAB.forEach(([x, z], i) => { table(D, x, z, { w: 0.9, chairs: [[0.75, 0, -Math.PI / 2], [-0.75, 0, Math.PI / 2], [0, 0.75, Math.PI]], chairCol: [0x7a4a2a, 0x2a5a4a][i % 2] }); D.push({ x: x + .15, y: 0.82, z: z + .1, w: .12, h: .1, d: .12, color: 0xf6f6f6 }, { x: x - .2, y: .82, z: z - .1, w: .12, h: .1, d: .12, color: 0xeadcc0 }); });
  // décor « chevaliers » : bouclier + épées croisées sur le mur ouest, râtelier, armure
  const swordB = (ry) => [{ x: 0, y: 0, z: 0, w: 0.06, h: 1.0, d: 0.1, color: 0xd8dce4 }, { x: 0, y: -0.52, z: 0, w: 0.34, h: 0.06, d: 0.1, color: 0x6a4a2a }, { x: 0, y: -0.64, z: 0, w: 0.05, h: 0.2, d: 0.06, color: 0x3a2a1a }];
  D.push({ x: -5.7, y: 2.0, z: -15.3, w: 0.7, h: 0.9, d: 0.1, color: 0x2a4ac0 }, { x: -5.7, y: 2.0, z: -15.22, w: 0.3, h: 0.3, d: 0.05, color: 0xe8c040 });
  D.push({ x: -7.3, y: 0.55, z: -11.1, w: 0.6, h: 1.1, d: 1.8, color: 0x5a3a22 }, { x: -7.3, y: 1.12, z: -11.1, w: 0.66, h: 0.05, d: 1.9, color: 0x8a6a44 }, { x: -6.5, y: 1.95, z: -15.34, w: 2.0, h: 0.9, d: 0.08, color: 0x4a2a18 }, { x: -7.3, y: 1.25, z: -10.3, w: 0.16, h: 0.26, d: 0.16, color: 0xd8c070 });
  D.push({ x: 6.2, y: 0.9, z: -14.6, w: 0.5, h: 1.8, d: 0.4, color: 0x8a8e96 }, { x: 6.2, y: 1.95, z: -14.6, w: 0.5, h: 0.4, d: 0.45, color: 0x9a9ea6 }, { x: 6.2, y: 2.25, z: -14.6, w: 0.4, h: 0.3, d: 0.4, color: 0x9a9ea6 }, { x: 5.9, y: 1.5, z: -14.6, w: 0.14, h: 0.9, d: 0.14, color: 0x8a8e96 }, { x: 6.5, y: 1.5, z: -14.6, w: 0.14, h: 0.9, d: 0.14, color: 0x8a8e96 });   // armure d'apparat
  for (const [x, z] of [[-7.0, -6.6], [7.0, -6.6], [7.0, -9.6]]) D.push({ x, y: 0.4, z, w: 0.5, h: 0.8, d: 0.5, color: 0x6a3a22 }, { x, y: 1.15, z, w: 0.7, h: 0.8, d: 0.7, color: 0x3a8a3a });
  D.push({ x: 3.4, y: 2.2, z: CZ0 + 0.08, w: 0.9, h: 1.2, d: 0.05, color: 0xd8c898 }, { x: 5.2, y: 2.4, z: CZ0 + 0.08, w: 0.7, h: 0.9, d: 0.05, color: 0xc8a888 });      // affiches
  const menu = signPlane(['MENU DU JOUR', 'Café 2  Crêpe 4', 'Soupe 5'], 1.5, 0.9, { bg: '#1a2a22', col: '#f0f0e0', px: 256 }); menu.position.set(-4.6, 2.2, CZ0 + 0.06); extras.push(menu);
  // porte de service (mur ouest, vers la ruelle) : fermée à clé, jamais ouverte
  D.push({ x: -CXW - 0.02, y: 1.05, z: -13.0, w: 0.08, h: 2.1, d: 1.0, color: 0x3a3a40 }, { x: -CXW + 0.04, y: 1.0, z: -12.65, w: 0.08, h: 0.1, d: 0.12, color: 0xc8c8c0 });
  const svc = signPlane('LIVRAISONS', 0.9, 0.22, { bg: '#c8a020', col: '#1a1a1a', px: 128 }); svc.rotation.y = Math.PI / 2; svc.position.set(-CXW + 0.07, 2.35, -13.0); extras.push(svc);
  // porte d'entrée (vantail articulé, lu dans l'env : door_cafe 0..1)
  const leaf = vox([{ x: 0.55, y: 1.1, z: 0, w: 1.1, h: 2.2, d: 0.06, color: 0x5a3a24 }, { x: 0.55, y: 1.4, z: 0.02, w: 0.8, h: 1.2, d: 0.04, color: 0x7a9ab4 }, { x: 0.15, y: 1.0, z: 0.07, w: 0.05, h: 0.4, d: 0.06, color: 0xd8c070 }], { rim: 0.5 }); const hinge = new THREE.Group(); hinge.position.set(4.0, 0, FZ); hinge.add(leaf); root.add(hinge);
  // lumières intérieures (suspensions) : boules lumineuses ; les lumières de la scène sont ajoutées dans look()
  const pend = []; for (const [x, z] of [[-5, -9], [-1.4, -9], [2.6, -9.5], [-1.5, -12.5], [-4, -7]]) { D.push({ x, y: CH - 0.9, z, w: 0.04, h: 1.3, d: 0.04, color: 0x2a2a2a }); pend.push({ x, y: CH - 1.6, z, w: 0.42, h: 0.34, d: 0.42, color: 0xffe2a8 }); }
  const pendM = basicVox(pend, 2.2); root.add(pendM);
  // ---- assemblage
  B.build(M, root, { noCast: ['glass'] });
  root.add(vox(D, { var: 0.07, seed: 3 })); root.add(Object.assign(vox(carBoxes(0, 0, 0xf0c020, 0), {}), { visible: false }));
  const bigG = GL.filter((g) => g.big), smallG = GL.filter((g) => !g.big);
  const gm = (list, mat) => { const m = new THREE.Mesh(boxesGeometry(list), mat); m.castShadow = false; m.receiveShadow = false; return m; };
  const glMatBig = new THREE.MeshPhongMaterial({ vertexColors: true, transparent: true, opacity: 0.3, shininess: 120, specular: 0xffffff, depthWrite: false }); const glMatSm = new THREE.MeshPhongMaterial({ vertexColors: true, shininess: 90, specular: 0x9aa8b8 });
  root.add(gm(bigG, glMatBig), gm(smallG, glMatSm));
  const lit1M = new THREE.MeshBasicMaterial({ vertexColors: true, fog: true }), lit2M = new THREE.MeshBasicMaterial({ vertexColors: true, fog: true }); lit1M.color.setScalar(1.15); lit2M.color.setScalar(0.0);
  const l1 = new THREE.Mesh(boxesGeometry(LW1), lit1M), l2 = new THREE.Mesh(boxesGeometry(LW2.length ? LW2 : [{ x: 0, y: -50, z: 0, w: .01, h: .01, d: .01, color: 0 }]), lit2M); root.add(l1, l2);
  const bulbM = new THREE.MeshBasicMaterial({ vertexColors: true, fog: false }); bulbM.color.setScalar(0.0); root.add(new THREE.Mesh(boxesGeometry(bulbs), bulbM));
  for (const e of extras) root.add(e);
  // cadran de l'horloge (canvas redessiné quand la minute change)
  const clk = cvs(128, 128), cg = clk.getContext('2d'), clkT = new THREE.CanvasTexture(clk); clkT.colorSpace = THREE.SRGBColorSpace; let lastMin = -1;
  const face = new THREE.Mesh(new THREE.PlaneGeometry(2.4, 2.4), new THREE.MeshBasicMaterial({ map: clkT, fog: true })); face.position.set(tx, 20 + tH - 3.5 + 2.8, tz + 1.52); root.add(face);
  const face2 = face.clone(); face2.rotation.y = Math.PI; face2.position.z = tz - 1.52; root.add(face2);
  const drawClock = (minutes) => { if (Math.floor(minutes * 4) === lastMin) return; lastMin = Math.floor(minutes * 4); cg.fillStyle = '#f4f0e0'; cg.fillRect(0, 0, 128, 128); cg.strokeStyle = '#2a2a30'; cg.lineWidth = 8; cg.strokeRect(4, 4, 120, 120); cg.fillStyle = '#2a2a30';
    for (let i = 0; i < 12; i++) { const a = i / 12 * 6.283; cg.fillRect(64 + Math.sin(a) * 50 - 3, 64 - Math.cos(a) * 50 - 3, 6, 6); }
    const m = minutes % 60, hh = (minutes / 60) % 12; const hand = (a, L, w) => { cg.lineWidth = w; cg.beginPath(); cg.moveTo(64, 64); cg.lineTo(64 + Math.sin(a) * L, 64 - Math.cos(a) * L); cg.stroke(); };
    cg.strokeStyle = '#1a1a1e'; hand(hh / 12 * 6.283, 28, 7); hand(m / 60 * 6.283, 44, 4); clkT.needsUpdate = true; };
  drawClock(11 * 60 + 20);
  // circulation : voies z 0.8 (vers +x) et z 3.2 (vers -x) ; véhicules déclarés dans l'env (cars: [{t0, v, lane, col, kind}]) -> boîtes pré-construites
  const traffic = []; for (let i = 0; i < 6; i++) { const col = [0xe8c020, 0xc83030, 0x2a5ab0, 0xe8e4dc, 0x2a8a5a, 0x7a3a8a][i]; const m = vox(carBoxes(0, 0, col, 0, i === 3), { var: 0.04 }); m.visible = false; root.add(m); traffic.push(m); }
  const wInfo = { name: 'cite', group, origin, root, sky_, M, bulbM, lit1M, lit2M, pendM, hinge, liftDoorL, liftDoorR, liftLamp, drawClock, traffic, bigVan, glMatBig };
  wInfo.update = (t) => {};
  return wInfo;
}

// ---------------------------------------------------------------------------------------------------------------- navette, balise, astroport
function shuttleBoxes() {
  const H = 0xe6eaf0, S = 0xc8ccd4, Dk = 0x2a2e38, R = 0xd8442e, Bl = 0x2a5aa8; const Bx = [];
  Bx.push({ x: 0, y: 2.3, z: 0, w: 3.2, h: 2.4, d: 8.4, color: H }, { x: 0, y: 2.0, z: -4.6, w: 2.6, h: 1.9, d: 1.5, color: H }, { x: 0, y: 1.8, z: -5.8, w: 1.8, h: 1.4, d: 1.1, color: S }, { x: 0, y: 1.6, z: -6.6, w: 0.9, h: 0.9, d: 0.6, color: Dk });      // fuselage + nez
  Bx.push({ x: 0, y: 3.15, z: -3.8, w: 2.0, h: 0.1, d: 2.0, color: 0x6ab0e8 }, { x: 0, y: 2.7, z: -5.0, w: 1.7, h: 0.5, d: 0.8, color: 0x6ab0e8 });                                                         // verrière
  Bx.push({ x: 0, y: 1.5, z: 0.6, w: 7.6, h: 0.18, d: 3.6, color: S }, { x: -3.9, y: 1.7, z: 1.4, w: 0.22, h: 0.9, d: 2.6, color: R }, { x: 3.9, y: 1.7, z: 1.4, w: 0.22, h: 0.9, d: 2.6, color: R });               // ailes + dérives
  Bx.push({ x: 0, y: 3.9, z: 3.0, w: 0.2, h: 1.5, d: 2.2, color: R });                                                                                                                                  // empennage
  for (const x of [-0.9, 0, 0.9]) Bx.push({ x, y: 1.9, z: 4.5, w: 0.7, h: 0.7, d: 0.9, color: Dk });                                                                                                  // tuyères
  Bx.push({ x: 0, y: 2.35, z: 0, w: 3.26, h: 0.2, d: 8.0, color: Bl });                                                                                                                                 // bande bleue
  for (const [x, z] of [[-1.3, -1.8], [1.3, -1.8], [-1.3, 2.4], [1.3, 2.4]]) Bx.push({ x, y: 0.55, z, w: 0.14, h: 1.1, d: 0.14, color: Dk }, { x, y: 0.05, z, w: 0.6, h: 0.1, d: 0.6, color: Dk });            // jambes
  for (let i = 0; i < 4; i++) Bx.push({ x: 1.62, y: 2.7, z: -2.2 + i * 1.1, w: 0.04, h: 0.45, d: 0.55, color: 0x6ab0e8 }, { x: -1.62, y: 2.7, z: -2.2 + i * 1.1, w: 0.04, h: 0.45, d: 0.55, color: 0x6ab0e8 });
  return Bx;
}
function buildShuttle() {
  const g = new THREE.Group(); const body = vox(shuttleBoxes(), { rim: 0.6, var: 0.05, px: 1 / 12 }); g.add(body);
  const hatchG = new THREE.Group(); hatchG.position.set(1.62, 0.45, -2.6); hatchG.add(vox([{ x: 1.0, y: 0, z: 0, w: 2.2, h: 0.1, d: 1.3, color: 0x8a8e96 }, { x: 0.1, y: 0.0, z: -0.62, w: 0.1, h: 0.4, d: 0.06, color: 0x2a2e38 }, { x: 0.1, y: 0.0, z: 0.62, w: 0.1, h: 0.4, d: 0.06, color: 0x2a2e38 }])); g.add(hatchG);
  const hatchHole = vox([{ x: 1.64, y: 1.45, z: -2.6, w: 0.05, h: 1.9, d: 1.3, color: 0x14161c }]); g.add(hatchHole);
  const fl = []; for (const x of [-0.9, 0, 0.9]) fl.push({ x, y: 1.9, z: 6.0, w: 0.5, h: 0.5, d: 3.2, color: 0xffa040 }, { x, y: 1.9, z: 5.4, w: 0.3, h: 0.3, d: 2.0, color: 0xfff0c0 });
  const flame = new THREE.Mesh(boxesGeometry(fl), new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.9, blending: THREE.AdditiveBlending, depthWrite: false, fog: false })); flame.visible = false; g.add(flame);
  const flicker = (T) => 0.85 + 0.15 * Math.sin(T * 60) * Math.sin(T * 37);
  return { g, hatchG, hatchHole, flame, legs: null, update(T, a) { const h = clamp(a.hatch ?? 1); hatchG.rotation.z = (1 - h) * (Math.PI / 2) - 0.2 * h; hatchHole.visible = h > 0.05; const th = a.thrust ?? 0; flame.visible = th > 0.02; flame.scale.set(1, 1, th * flicker(T)); flame.position.z = (1 - th) * -2.0; } };
}
PROPS.shuttle = (p) => { const s = buildShuttle(); s.g.rotation.y = 0; return { g: s.g, update: (T) => { const A = p.anim || {}; s.update(T, { hatch: tv(A.hatch, T, 1), thrust: tv(A.thrust, T, 0) }); s.g.position.y = tv(A.lift, T, 0); } }; };
function makeBeacon() {
  const g = new THREE.Group(); const B = [{ x: 0, y: 0.35, z: 0, w: 3.0, h: 0.7, d: 3.0, color: 0x5a5e68 }, { x: 0, y: 3.4, z: 0, w: 0.6, h: 5.4, d: 0.6, color: 0x8a8e98 }, { x: 0, y: 6.2, z: 0, w: 1.6, h: 0.3, d: 1.6, color: 0x4a4e58 }];
  for (const [dx, dz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) B.push({ x: dx * 0.9, y: 2.2, z: dz * 0.9, w: 0.16, h: 3.6, d: 0.16, color: 0x6a6e78, rz: -dx * 0.12, rx: dz * 0.12 });
  B.push({ x: 0, y: 1.0, z: 1.6, w: 1.2, h: 0.9, d: 0.7, color: 0x3a3e48 }, { x: 0, y: 1.2, z: 1.96, w: 0.9, h: 0.4, d: 0.04, color: 0x14222e });         // pupitre de commande
  g.add(vox(B, { rim: 0.6 })); const core = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.7, 0.7), new THREE.MeshBasicMaterial({ color: 0x205880 })); core.position.set(0, 6.8, 0); core.rotation.set(0.6, 0.6, 0); g.add(core);
  const beam = new THREE.Mesh(new THREE.BoxGeometry(0.9, 80, 0.9), new THREE.MeshBasicMaterial({ color: 0x8ad0ff, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, fog: false })); beam.position.set(0, 46, 0); g.add(beam);
  const hc = cvs(128, 128), hg = hc.getContext('2d'), grd = hg.createRadialGradient(64, 64, 2, 64, 64, 62); grd.addColorStop(0, 'rgba(200,240,255,1)'); grd.addColorStop(0.25, 'rgba(120,200,255,0.55)'); grd.addColorStop(1, 'rgba(60,140,255,0)'); hg.fillStyle = grd; hg.fillRect(0, 0, 128, 128); const hT = new THREE.CanvasTexture(hc); hT.colorSpace = THREE.SRGBColorSpace;
  const halo = new THREE.Mesh(new THREE.PlaneGeometry(9, 9), new THREE.MeshBasicMaterial({ map: hT, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, fog: false })); halo.position.set(0, 6.8, 0); g.add(halo); const halo2 = halo.clone(); halo2.rotation.y = Math.PI / 2; g.add(halo2);
  return { g, set(T, on, face) { core.material.color.setRGB(0.12 + 0.2 * on, 0.35 + 1.9 * on, 0.5 + 2.6 * on); core.rotation.y = 0.6 + T * 0.8 * (0.2 + on); beam.material.opacity = 0.32 * on; halo.material.opacity = 0.95 * on; halo.rotation.y = 0; } };
}
PROPS.beacon = (p) => { const b = makeBeacon(); return { g: b.g, update: (T) => b.set(T, tv(p.anim?.on, T, 0), null) }; };
PROPS.mover = (p) => {                 // un objet qui se déplace : boîtes + piste [[t, x, y, z, ry, rx, rz], ...] (linéaire entre deux clés), visible entre t0 et t1
  const g = new THREE.Group(); const inner = new THREE.Group(); g.add(inner); inner.add(vox((p.boxes || []).map((b) => ({ ...b, color: typeof b.color === 'string' ? parseInt(b.color.replace('#', ''), 16) : b.color })), { var: 0.04 }));
  const tr = p.track || [[0, 0, 0, 0, 0]];
  return { g, update: (T) => { let i = 0; while (i < tr.length - 2 && T > tr[i + 1][0]) i++; const a = tr[i], b = tr[Math.min(tr.length - 1, i + 1)], k = b[0] === a[0] ? 0 : clamp((T - a[0]) / (b[0] - a[0]), 0, 1); const L = (j) => lerp(a[j] ?? 0, b[j] ?? 0, k);
    inner.position.set(L(1), L(2), L(3)); inner.rotation.set(L(5), L(4), L(6)); if (p.glow) { /* lueur : le plan peut poser une lumière à part */ } } };
};
PROPS.clockface = (p) => ({ g: new THREE.Group(), update: () => {} });


function planetCanvas(seed, a, b) { const c = cvs(256, 128), g = c.getContext('2d'), r = mulberry(seed); g.fillStyle = hex(a); g.fillRect(0, 0, 256, 128); g.fillStyle = hex(b);
  for (let i = 0; i < 26; i++) { const x = r() * 256, y = 20 + r() * 88; for (let k = 0; k < 12; k++) g.fillRect(x + (r() - 0.5) * 40, y + (r() - 0.5) * 22, 8 + r() * 14, 6 + r() * 10); }
  g.fillStyle = 'rgba(255,255,255,0.75)'; for (let i = 0; i < 40; i++) g.fillRect(r() * 256, r() * 128, 10 + r() * 30, 2 + r() * 4); const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t; }
function buildSelene(ctx0, origin) {
  const { scene } = ctx0; const group = new THREE.Group(); group.position.copy(origin); scene.add(group); const root = new THREE.Group(); root.position.set(SX, 0, 0); group.add(root); const r = mulberry(131);
  const sky_ = sky(group, { top: 0x000000, mid: 0x02030a, bot: 0x050508, sun: [0.8, 0.45, -0.3], sunCol: 0xffffff, sunSize: 0.012, stars: 1.1 });
  const M = cityMats(); const B = new Batch(); B.add({ x: 0, y: -0.5, z: -20, w: 260, h: 1, d: 180, mat: 'conc', tpm: 0.3, color: 0xb8b8bc }); B.build(M, root, { noCast: [] });
  const D = []; for (let i = 0; i < 30; i++) { const cx = (r() - 0.5) * 120, cz = (r() > 0.5 ? 1 : -1) * (7 + r() * 45), R = 1 + r() * 4; for (let a = 0; a < 20; a++) { const an = a / 20 * 6.283; D.push({ x: cx + Math.cos(an) * R, y: 0.12, z: cz + Math.sin(an) * R, w: 0.7, h: 0.25 + r() * 0.2, d: 0.7, color: 0xa0a0a4, ry: r() * 3 }); } }
  for (let i = 0; i < 90; i++) { const x = (r() - 0.5) * 120, z = (r() - 0.5) * 90; if (Math.abs(x) < 16 && Math.abs(z) < 5) continue; D.push({ x, y: 0.15, z, w: 0.2 + r() * 0.7, h: 0.3 + r() * 0.3, d: 0.2 + r() * 0.7, color: 0x8a8a8e, ry: r() * 3 }); }
  for (const [x, z] of [[-10, -3.4], [-8, 3.2], [9, 3.6], [-3, -3.8]]) D.push({ x, y: 0.3, z, w: 1.2, h: 0.6, d: 1.0, color: 0x90909a, ry: x });
  root.add(vox(D, { var: 0.06 }));
  const earth = new THREE.Mesh(new THREE.SphereGeometry(9, 48, 32), new THREE.MeshLambertMaterial({ map: planetCanvas(103, 0x2a5ab8, 0x3a9a4a), emissive: 0x0a1a3a })); earth.position.set(-25, 30, -90); root.add(earth);
  const ship = buildShuttle(); ship.g.position.set(-9, 0, 0); ship.g.rotation.y = -Math.PI / 2; root.add(ship.g);    // posée, nez vers -x, écoutille côté... (rotation de -90° : l'écoutille +x passe côté +z)
  const bc = makeBeacon(); bc.g.position.set(8, 0, -1); root.add(bc.g);
  return { name: 'selene', group, origin, root, sky_, earth, ship, bc, update: (t) => { earth.rotation.y = t * 0.03; } };
}

function buildAstroport(ctx0, origin) {
  const { scene } = ctx0; const group = new THREE.Group(); group.position.copy(origin); scene.add(group); const root = new THREE.Group(); root.position.set(AX, 0, 0); group.add(root);
  const M = cityMats(); const B = new Batch(); const D = [], GL = [], LW1 = [], LW2 = [], extras = []; const ctx = { B, D, GL, LW1, LW2, extras }; const r = mulberry(91);
  const sky_ = sky(group, { top: 0x3f7ad8, mid: 0xbcd6f4, bot: 0xb0c4d8, sun: [0.3, 0.6, -0.7], sunCol: 0xfff0c8, stars: 0 });
  // dalle d'envol 36 x 36 (x -18..18, z -18..18), épaisseur 1 m, peinture
  B.add({ x: 0, y: -0.5, z: 0, w: 36, h: 1.0, d: 36, mat: 'pad', tpm: 0.5 }); B.add({ x: 0, y: -1.5, z: 0, w: 37, h: 1.0, d: 37, mat: 'conc', tpm: 0.5 });
  for (let i = -17; i <= 17; i += 2) { D.push({ x: i, y: 0.02, z: 17.7, w: 1, h: 0.04, d: 0.6, color: i % 4 ? 0xe8c020 : 0x1a1a1a }, { x: i, y: 0.02, z: -17.7, w: 1, h: 0.04, d: 0.6, color: i % 4 ? 0xe8c020 : 0x1a1a1a }, { x: 17.7, y: 0.02, z: i, w: 0.6, h: 0.04, d: 1, color: i % 4 ? 0xe8c020 : 0x1a1a1a }, { x: -17.7, y: 0.02, z: i, w: 0.6, h: 0.04, d: 1, color: i % 4 ? 0xe8c020 : 0x1a1a1a }); }
  for (let a = 0; a < 24; a++) { const an = a / 24 * 6.283; D.push({ x: Math.cos(an) * 8.5, y: 0.02, z: Math.sin(an) * 8.5, w: 1.6, h: 0.04, d: 0.25, color: 0xf2f0e6, ry: -an + Math.PI / 2 }); }
  D.push({ x: 0, y: 0.02, z: 0, w: 0.3, h: 0.04, d: 5, color: 0xf2f0e6 }, { x: 0, y: 0.02, z: 0, w: 5, h: 0.04, d: 0.3, color: 0xf2f0e6 });
  // garde-corps (sauf côté ascenseur) et balises de bord
  for (let i = -18; i <= 18; i += 2) for (const [x, z] of [[i, 18], [i, -18], [18, i], [-18, i]]) { if (Math.abs(x + 18) < 0.1 && Math.abs(z) < 3) continue; D.push({ x, y: 0.55, z, w: 0.07, h: 1.1, d: 0.07, color: 0x2a2c30 }); }
  D.push({ x: 0, y: 1.1, z: 18, w: 36, h: 0.06, d: 0.06, color: 0x2a2c30 }, { x: 0, y: 1.1, z: -18, w: 36, h: 0.06, d: 0.06, color: 0x2a2c30 }, { x: 18, y: 1.1, z: 0, w: 0.06, h: 0.06, d: 36, color: 0x2a2c30 }, { x: -18, y: 1.1, z: 7.5, w: 0.06, h: 0.06, d: 21, color: 0x2a2c30 }, { x: -18, y: 1.1, z: -7.5, w: 0.06, h: 0.06, d: 21, color: 0x2a2c30 });
  const bea = []; for (let i = -16; i <= 16; i += 4) for (const [x, z] of [[i, 17.4], [i, -17.4], [17.4, i], [-17.4, i]]) bea.push({ x, y: 0.12, z, w: 0.22, h: 0.12, d: 0.22, color: 0xff7a30 });
  // cabine de l'ascenseur (côté ouest) : 4 x 3 m, porte vers l'est (la dalle), intérieur éclairé ; murs de 0.2
  const LX0 = -23, LX1 = -18.3, LZ0 = -2.4, LZ1 = 2.4;
  B.add({ x: (LX0 + LX1) / 2, y: 1.45, z: LZ0 - 0.1, w: LX1 - LX0, h: 2.9, d: 0.2, mat: 'metal', tpm: 0.5 }); B.add({ x: (LX0 + LX1) / 2, y: 1.45, z: LZ1 + 0.1, w: LX1 - LX0, h: 2.9, d: 0.2, mat: 'metal', tpm: 0.5 }); B.add({ x: LX0 - 0.1, y: 1.45, z: 0, w: 0.2, h: 2.9, d: LZ1 - LZ0 + 0.4, mat: 'metal', tpm: 0.5 });
  B.add({ x: (LX0 + LX1) / 2, y: 3.0, z: 0, w: LX1 - LX0 + 0.3, h: 0.2, d: LZ1 - LZ0 + 0.4, mat: 'metal', tpm: 0.5 }); B.add({ x: (LX0 + LX1) / 2, y: -0.05, z: 0, w: LX1 - LX0, h: 0.1, d: LZ1 - LZ0, mat: 'tile', tpm: 0.5 });
  B.add({ x: LX1 - 0.1, y: 2.65, z: 0, w: 0.3, h: 0.5, d: 4.8, mat: 'metal', tpm: 0.5 });
  B.add({ x: LX1 - 0.1, y: 1.2, z: -1.7, w: 0.3, h: 2.4, d: 1.4, mat: 'metal', tpm: 0.5 }); B.add({ x: LX1 - 0.1, y: 1.2, z: 1.7, w: 0.3, h: 2.4, d: 1.4, mat: 'metal', tpm: 0.5 });
  const liftSign = signPlane('NIVEAU TOIT', 1.6, 0.35, { bg: '#e8c020', col: '#1a1a1a', px: 256 }); liftSign.position.set(LX1 + 0.08, 2.65, 0); liftSign.rotation.y = Math.PI / 2; extras.push(liftSign);
  D.push({ x: LX0 + 0.3, y: 1.0, z: -2.0, w: 0.06, h: 0.06, d: 3.6, color: 0x8a8e96 }, { x: LX0 + 0.3, y: 1.2, z: 2.0, w: 0.5, h: 0.6, d: 0.04, color: 0x2a2e38 });                  // main courante + panneau de boutons
  const cabLamp = new THREE.Mesh(new THREE.BoxGeometry(2.4, 0.08, 1.2), new THREE.MeshBasicMaterial({ color: new THREE.Color(0xfff0d0).multiplyScalar(2.2) })); cabLamp.position.set((LX0 + LX1) / 2, 2.9, 0); extras.push(cabLamp);
  const cabDoorL = vox([{ x: 0, y: 1.3, z: 0, w: 0.1, h: 2.6, d: 1.0, color: 0x8a8e96 }], { rim: 0.6 }), cabDoorR = vox([{ x: 0, y: 1.3, z: 0, w: 0.1, h: 2.6, d: 1.0, color: 0x7a7e86 }], { rim: 0.6 }); root.add(cabDoorL, cabDoorR);
  // tour de contrôle (est) : fût, cabine vitrée, antennes ; hangar de service (nord) ; réservoir
  B.add({ x: 12, y: 4, z: -13, w: 3, h: 8, d: 3, mat: 'conc', tpm: 0.5 }); B.add({ x: 12, y: 9.0, z: -13, w: 6, h: 2.4, d: 6, mat: 'trim', tpm: 0.5 }); B.add({ x: 12, y: 10.5, z: -13, w: 6.6, h: 0.4, d: 6.6, mat: 'roofM', tpm: 0.5 });
  GL.push({ x: 12, y: 9.0, z: -9.96, w: 5.6, h: 1.8, d: 0.04, color: 0x4a7aa0, big: true }, { x: 8.96, y: 9.0, z: -13, w: 0.04, h: 1.8, d: 5.6, color: 0x4a7aa0, big: true }, { x: 15.04, y: 9.0, z: -13, w: 0.04, h: 1.8, d: 5.6, color: 0x4a7aa0, big: true });
  D.push({ x: 12, y: 12.0, z: -13, w: 0.1, h: 3.4, d: 0.1, color: 0x2a2c30 }, { x: 12, y: 13.2, z: -13, w: 1.6, h: 0.08, d: 0.08, color: 0x2a2c30 }, { x: 13.4, y: 11.6, z: -13, w: 0.8, h: 0.8, d: 0.08, color: 0xd8d8d4, rz: 0.4 });
  B.add({ x: -6, y: 2.5, z: -15.2, w: 12, h: 5, d: 5, mat: 'metal', tpm: 0.5 }); B.add({ x: -6, y: 5.2, z: -15.2, w: 12.4, h: 0.5, d: 5.4, mat: 'roofM', tpm: 0.5 });
  const sg = signPlane('ASTROPORT — QUAI 3', 6.4, 0.9, { bg: '#10202c', col: '#8ad0ff', px: 512, border: '#8ad0ff' }); sg.position.set(-6, 3.4, -12.68); extras.push(sg);
  D.push({ x: 14, y: 1.4, z: 13, w: 2.2, h: 2.8, d: 2.2, color: 0xc8ccd4 }, { x: 14, y: 3.05, z: 13, w: 1.6, h: 0.5, d: 1.6, color: 0xb0b4bc }, { x: -12, y: 0.6, z: 14, w: 1.6, h: 1.2, d: 1.0, color: 0xe8c020 }, { x: -12.9, y: 0.6, z: 14.6, w: 0.1, h: 1.2, d: 1.2, color: 0x2a2c30 });
  // mât d'éclairage, manche à air, projecteurs
  for (const [x, z] of [[-16, -16], [16, 16], [16, -16], [-16, 16]]) { D.push({ x, y: 4.0, z, w: 0.22, h: 8, d: 0.22, color: 0x3a3e46 }, { x, y: 8.1, z, w: 1.3, h: 0.3, d: 0.5, color: 0x2a2c30 }); bea.push({ x, y: 8.0, z, w: 1.1, h: 0.1, d: 0.4, color: 0xfff4d8 }); }
  D.push({ x: 16, y: 2.0, z: 6, w: 0.08, h: 4, d: 0.08, color: 0x6a6e76 }); for (let i = 0; i < 4; i++) D.push({ x: 16, y: 3.8 - i * 0.04, z: 6 + 0.25 + i * 0.5, w: 0.5 - i * 0.07, h: 0.5 - i * 0.07, d: 0.5, color: i % 2 ? 0xf4f0e4 : 0xd8442e });
  // ville en contrebas : un anneau d'immeubles (silhouettes) sous le niveau du toit, avec rues lumineuses
  B.add({ x: 0, y: -62, z: 0, w: 500, h: 1, d: 500, mat: 'asphalt', tpm: 0.2 });
  for (let i = 0; i < 70; i++) { const a = r() * 6.283, d = 34 + r() * 150, x = Math.cos(a) * d, z = Math.sin(a) * d; const w = 8 + r() * 12; const top = -4 - r() * 50; const hh = 62 + top; B.add({ x, y: -62 + hh / 2, z, w, h: hh, d: w, mat: ['conc', 'brickD', 'plaster', 'stone'][i % 4], tpm: 0.5, color: [0xb8c4d0, 0xd8c8b8, 0xc8d0d8][i % 3] }); B.add({ x, y: top + 0.2, z, w: w + 0.4, h: 0.4, d: w + 0.4, mat: 'roofM', tpm: 0.5 });
    for (let k = 0; k < 6; k++) { const f = r(); if (f < 0.5) (r() < 0.5 ? LW1 : LW2).push({ x: x + (r() - 0.5) * (w - 1), y: top - 3 - r() * 25, z: z + (z > 0 ? -w / 2 - 0.03 : w / 2 + 0.03), w: 1.4, h: 1.0, d: 0.05, color: 0xffd890 }); } }
  B.build(M, root, { noCast: ['glass'] }); root.add(vox(D, { var: 0.07, seed: 4 }));
  const gm = (list, mat) => { const m = new THREE.Mesh(boxesGeometry(list), mat); m.castShadow = false; return m; };
  const bigG = GL.filter((g) => g.big); if (bigG.length) root.add(gm(bigG, new THREE.MeshPhongMaterial({ vertexColors: true, transparent: true, opacity: 0.3, shininess: 120, specular: 0xffffff, depthWrite: false })));
  const lit1M = new THREE.MeshBasicMaterial({ vertexColors: true }), lit2M = new THREE.MeshBasicMaterial({ vertexColors: true }); lit1M.color.setScalar(1.1); lit2M.color.setScalar(0.4);
  root.add(new THREE.Mesh(boxesGeometry(LW1.length ? LW1 : [{ x: 0, y: -90, z: 0, w: .01, h: .01, d: .01, color: 0 }]), lit1M), new THREE.Mesh(boxesGeometry(LW2.length ? LW2 : [{ x: 0, y: -90, z: 0, w: .01, h: .01, d: .01, color: 0 }]), lit2M));
  const beaM = new THREE.MeshBasicMaterial({ vertexColors: true, fog: false }); beaM.color.setScalar(1.8); root.add(new THREE.Mesh(boxesGeometry(bea), beaM)); for (const e of extras) root.add(e);
  // la navette (posée au centre, nez vers -z, écoutille côté est), animée par l'env : lift (m), thrust 0..1, hatch 0..1
  const ship = buildShuttle(); ship.g.position.set(0, 0, 0); root.add(ship.g);
  const hazeU = null;
  return { name: 'astroport', group, origin, root, sky_, ship, cabDoorL, cabDoorR, cabLamp, lit2M, beaM, update: () => {}, LX1, LZ0, LZ1 };
}

// ---------------------------------------------------------------------------------------------------------------- les mondes, leur lumière
export function buildCiteWorlds(ctx, wanted, base = new THREE.Vector3(9000, 0, 0), step = 500) {
  const W = []; let idx = 0;
  const mk = (name, build) => { const origin = base.clone().add(V(idx * step, 0, 0)); idx++; if (!wanted.has(name)) return; const w = build(origin); w.name = name; w.origin = origin; w.at = (x, y, z) => origin.clone().add(V(x, y, z)); const look0 = w.look; w.look = (S, T, E = {}) => { const En = normEnv(E); look0(S, T, En); grade(S, En); }; W.push(w); };
  const L = (S, o) => { S.key = { dir: o.dir ?? [-0.5, 0.75, 0.55], color: o.sun ?? 0xfff0d8, i: o.ki ?? 2.0 }; S.hemi = { sky: o.sky ?? 0xa8c4ff, ground: o.gnd ?? 0x6a5a48, i: o.hi ?? 0.85 };
    S.fill = { dir: [0.6, 0.3, 0.8], color: o.fillc ?? 0xb8c8ff, i: o.fi ?? 0.35 }; S.fog = { color: o.fog ?? 0xc8d8f0, d: o.fogd ?? 0.006 }; S.bg = o.bg ?? 0xa8c8ff; S.rim = { color: o.rim ?? 0xffe8d0, i: o.rimi ?? 0.18, pow: 4 }; S.edge = null; S.spark = null;
    S.bloom = o.bloom ?? 0.3; S.bloomThreshold = o.bt ?? 0.92; S.bloomRadius = 0.5; S.contrast = o.con ?? 0.14; S.sat = o.sat ?? 1.12; S.vignette = o.vig ?? 0.32; S.vigCol = 0x050505; S.lift = 0x020202; S.shadowTint = o.st ?? 0xd8e0ff; S.highTint = o.ht ?? 0xfff6ea; S.grain = 0.02; S.lights = []; S.exposure = o.exp ?? 1; };
  const mixc = (a, b, k) => new THREE.Color(a).lerp(new THREE.Color(b), clamp(k)).getHex();

  mk('cite', (origin) => {
    const c = buildCite(ctx, origin); const w = c;
    const cars = []; w.update = () => {};
    w.look = (S, T, E = {}) => {
      const day = E.day ?? 1;                                       // 1 = matin clair, 0 = nuit
      const dusk = clamp(1 - day);
      L(S, { dir: [lerp(-0.55, -0.9, dusk), lerp(0.62, 0.18, dusk), lerp(0.5, -0.3, dusk)], sun: mixc(0xfff0d8, 0xff9050, dusk * 1.4), ki: lerp(2.05, 0.9, dusk * 1.2), hi: lerp(0.9, 0.5, dusk), sky: mixc(0xa8c4ff, 0x3a4a7a, dusk), gnd: mixc(0x6a5a48, 0x2a2024, dusk), fog: mixc(0xc8d8f0, 0x2a3050, dusk), fogd: lerp(0.006, 0.01, dusk), bg: mixc(0xa8c8ff, 0x10182c, dusk), vig: lerp(0.3, 0.45, dusk), exp: lerp(1, 1.12, dusk) });
      const u = c.sky_; u.uTop.value.set(mixc(0x4a86e0, 0x060a1c, dusk)); u.uMid.value.set(mixc(0xbcd6f4, 0x4a3a58, dusk * 0.9)); u.uBot.value.set(mixc(0xb0c4d8, 0x1a2030, dusk)); u.uSunCol.value.set(0xfff0c8).multiplyScalar(1 - dusk * 0.7); u.uStars.value = dusk > 0.7 ? (dusk - 0.7) * 2 : 0;
      c.lit2M.color.setScalar(clamp((E.lit ?? 0) * 1.3, 0, 1.3)); c.lit1M.color.setScalar(1.1 + 0.3 * dusk); c.bulbM.color.setScalar(clamp((E.lamps ?? 0) * 2.4, 0, 2.4)); c.pendM.material.color.setScalar(2.2 * (0.55 + 0.45 * (E.cafe ?? 1)));
      c.hinge.rotation.y = -1.45 * clamp(tv(E.door_cafe, T, 0), 0, 1); c.drawClock(E.clock ?? 11 * 60 + 20);
      const lf = clamp(tv(E.lift_door, T, 0)); c.liftDoorL.position.set(-9.2 - 0.5 - 1.0 * lf * 0.5, 0, -34.5); c.liftDoorR.position.set(-9.2 + 0.5 + 1.0 * lf * 0.5, 0, -34.5); c.liftLamp.material.color.setRGB(2, 1.2, 0.4).multiplyScalar(0.4 + 0.6 * Math.abs(Math.sin(T * 6)) * (E.lift_run ?? 0));
      // véhicules : [{t0, v, lane, col}] ; position = x0 + v * (T - t0), visibles tant qu'ils sont dans [-60, 60]
      const list = E.cars || []; c.traffic.forEach((m, i) => { const cv = list[i]; if (!cv) { m.visible = false; return; } const x = cv.x0 + cv.v * (T - cv.t0); m.visible = x > -62 && x < 62 && T >= cv.t0; m.position.set(x, 0, cv.lane); m.rotation.y = cv.v < 0 ? Math.PI : 0; });
      c.bigVan.position.set(E.van ? E.van[0] : 100, 0, E.van ? E.van[1] : 100); c.bigVan.rotation.y = E.van ? (E.van[2] ?? 0) : 0;
      // lumières : intérieur du café (suspensions), lampadaires (la nuit), fenêtres de la salle
      S.lights = []; const cafe = E.cafe ?? 1; for (const [x, z] of [[-4.6, -9.3], [-0.6, -9.3], [3.2, -10], [-1.5, -12.4]]) S.lights.push({ pos: w.at(CX + x, 3.0, z), color: 0xffd6a0, i: 3.0 * cafe, dist: 7.5, decay: 1.2 });
      if ((E.lamps ?? 0) > 0.05) for (const x of [-40, -18, 4, 26, 48]) S.lights.push({ pos: w.at(CX + x, 4.8, -1.6), color: 0xffd8a0, i: 5 * E.lamps, dist: 14, decay: 1.3 });
      if (E.alley) S.lights.push({ pos: w.at(CX - 9.2, 3.6, -30), color: 0xffe0b0, i: 2.4, dist: 8, decay: 1.2 });
      S.dust = { i: 0.35, col: 0xfff2d8, size: 0.6, box: V(8, 4, 8) }; S.shadowC = w.at(CX, 0, 0); S.shadowS = 20; S.sets = [w.name];
    };
    return w;
  });

  mk('astroport', (origin) => {
    const a = buildAstroport(ctx, origin); const w = a;
    w.look = (S, T, E = {}) => {
      const alt = clamp(E.alt ?? 0); const sp = clamp(alt * 1.25 - 0.1);                // 0 = ciel de jour, 1 = espace
      L(S, { dir: [-0.3, 0.8, -0.5], sun: mixc(0xfff0d8, 0xffffff, sp), ki: lerp(2.1, 2.5, sp), hi: lerp(0.9, 0.18, sp), sky: mixc(0xa8c4ff, 0x1a2038, sp), gnd: mixc(0x6a5a48, 0x1a1a22, sp), fog: mixc(0xc8d8f0, 0x04060c, sp), fogd: lerp(0.005, 0.0008, sp), bg: mixc(0xa8c8ff, 0x010208, sp), bloom: lerp(0.3, 0.6, sp), vig: lerp(0.3, 0.5, sp), exp: lerp(1, 1.05, sp) });
      const u = a.sky_; u.uTop.value.set(mixc(0x3f7ad8, 0x000004, sp)); u.uMid.value.set(mixc(0xbcd6f4, 0x050818, sp)); u.uBot.value.set(mixc(0xb0c4d8, 0x04060c, sp)); u.uStars.value = clamp((sp - 0.35) * 1.8) * 1.2; u.uSunCol.value.set(0xfff0c8);
      const th = clamp(tv(E.thrust, T, 0)), lift = tv(E.lift, T, 0), hatch = clamp(tv(E.hatch, T, 1));
      a.ship.update(T, { hatch, thrust: th }); a.ship.g.position.y = lift; a.ship.g.position.x = tv(E.drift, T, 0);
      const ld = clamp(tv(E.lift_door_roof, T, 0)); a.cabDoorL.position.set(a.LX1 - 0.05, 0, -0.5 - 1.0 * ld); a.cabDoorR.position.set(a.LX1 - 0.05, 0, 0.5 + 1.0 * ld);
      S.lights = [{ pos: w.at(AX + a.LX1 - 2.0, 2.6, 0), color: 0xfff0d0, i: 3.2, dist: 6, decay: 1.2 }]; if (th > 0.05 && lift < 30) S.lights.push({ pos: w.at(AX + (E.drift ? tv(E.drift, T, 0) : 0), lift + 1.2, 6), color: 0xffa860, i: 9 * th, dist: 22, decay: 1.2 });
      S.dust = { i: 0.25, col: 0xfff2d8, size: 0.6, box: V(8, 4, 8) }; S.shadowC = w.at(AX, Math.min(lift, 20), 0); S.shadowS = 24; S.sets = [w.name];
    };
    return w;
  });
  mk('selene', (origin) => {
    const a = buildSelene(ctx, origin); const w = a;
    w.look = (S, T, E = {}) => {
      L(S, { dir: [0.35, 0.6, 0.75], sun: 0xf4f8ff, ki: 2.6, sky: 0x4a5a78, gnd: 0x2a2c34, hi: 1.1, fillc: 0x8aa8e8, fi: 0.7, fog: 0x000000, fogd: 0.0012, bg: 0x000000, con: 0.26, sat: 1.0, vig: 0.4, bloom: 0.6, st: 0xa8b8d8, exp: 1.25 });
      const on = clamp(tv(E.beacon, T, 0)); a.bc.set(T, on, null); a.bc.g.children.forEach(() => {}); const hatch = clamp(tv(E.hatch_moon, T, 1)); a.ship.update(T, { hatch, thrust: 0 }); a.ship.g.position.y = 0;
      S.lights = [{ pos: w.at(SX + 8, 6.8, -1), color: 0x9ad8ff, i: 1.5 + 7 * on, dist: 18, decay: 1.2 }]; S.sets = [w.name]; S.shadowC = w.at(SX, 0, 0); S.shadowS = 22; S.dust = { i: 0.2, col: 0xdddddd, size: 0.5, box: V(8, 4, 8) };
    };
    return w;
  });
  return W;
}
