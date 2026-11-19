// Décors v5 « La marche » : dix mondes posés chacun à son origine, traversés en ligne droite (axe +x, z = 0).
// Ville au matin, parc au printemps, automne, ville sous la pluie, glacier, ruines en feu, bataille, invasion,
// vaisseau spatial, surface de la Lune. Chaque monde : { group, origin, look(S, t), update(t, ctx) }.
import * as THREE from 'three';
import { mat4, grunge, rimify, voxify, tiles } from './kit4.js';
import { boxesGeometry } from './boxes.js';
import { mulberry } from './textures.js';
import { lavaMaterial } from './sets4d.js';

const V = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
const C = (h) => new THREE.Color(h);
const shade = (h, f) => { const c = new THREE.Color(h); c.multiplyScalar(f); return c; };
const vmat = (o = {}) => voxify(rimify(new THREE.MeshLambertMaterial({ vertexColors: true, emissive: o.emissive ?? 0x000000 }), o.rim ?? 0.5, o.wet ?? 0.2), { var: o.var ?? 0.1, levels: 4, px: o.px ?? 1 / 16, seed: o.seed ?? 0 });
function vox(boxes, o = {}) { const m = new THREE.Mesh(boxesGeometry(boxes), o.mat || vmat(o)); m.castShadow = o.cast ?? true; m.receiveShadow = true; return m; }
// géométrie sans couleurs par sommet : on en ajoute des blanches (les matériaux mat4 les utilisent)
const white = (geo) => { const n = geo.attributes.position.count; geo.setAttribute('color', new THREE.Float32BufferAttribute(new Float32Array(n * 3).fill(1), 3)); return geo; };
const glow = (color, k = 1) => new THREE.MeshBasicMaterial({ color: new THREE.Color(color).multiplyScalar(k), fog: false });

// ciel en dégradé (dôme) + soleil / lune optionnels
function sky(group, { top, mid, bot, sun = null, sunCol = 0xfff2d0, sunSize = 0.03, stars = 0 }) {
  const u = { uTop: { value: C(top) }, uMid: { value: C(mid) }, uBot: { value: C(bot) }, uSun: { value: sun ? V(...sun).normalize() : V(0, -1, 0) }, uSunCol: { value: C(sunCol) }, uSunSize: { value: sunSize }, uStars: { value: stars } };
  const m = new THREE.ShaderMaterial({ uniforms: u, side: THREE.BackSide, depthWrite: false, fog: false,
    vertexShader: 'varying vec3 vD; void main(){ vD = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
    fragmentShader: `uniform vec3 uTop, uMid, uBot, uSun, uSunCol; uniform float uSunSize, uStars; varying vec3 vD;
      float h(vec3 p){ return fract(sin(dot(p, vec3(12.9898, 78.233, 37.719))) * 43758.5453); }
      void main(){ float y = vD.y; vec3 c = y > 0.0 ? mix(uMid, uTop, pow(clamp(y, 0.0, 1.0), 0.6)) : mix(uMid, uBot, clamp(-y * 4.0, 0.0, 1.0));
        float s = max(dot(vD, uSun), 0.0); c += uSunCol * (smoothstep(1.0 - uSunSize, 1.0 - uSunSize * 0.5, s) * 2.5 + pow(s, 24.0) * 0.35 + pow(s, 4.0) * 0.12);
        if (uStars > 0.0) { vec3 q = floor(vD * 420.0); float st = step(0.9965, h(q)); c += vec3(st) * uStars * (0.5 + 0.5 * h(q + 3.1)); }
        gl_FragColor = vec4(c, 1.0); }` });
  const d = new THREE.Mesh(new THREE.SphereGeometry(180, 32, 16), m); d.renderOrder = -10; d.frustumCulled = false; group.add(d); return u;
}
// texture de façade : mur + grille de fenêtres (+ vitrine au rez-de-chaussée)
function facadeTex(wall, win, { cols = 4, rows = 6, lit = 0.15, seed = 1, shop = null } = {}) {
  const S = 64; const c = document.createElement('canvas'); c.width = S; c.height = S * rows / cols * 1.0 | 0; const g = c.getContext('2d'); const r = mulberry(seed);
  const hex = (h) => '#' + new THREE.Color(h).getHexString();
  g.fillStyle = hex(wall); g.fillRect(0, 0, c.width, c.height);
  for (let i = 0; i < 300; i++) { g.fillStyle = `rgba(0,0,0,${r() * 0.06})`; g.fillRect(r() * c.width | 0, r() * c.height | 0, 2, 2); }
  const cw = S / cols, rh = c.height / rows;
  for (let y = 0; y < rows; y++) for (let x = 0; x < cols; x++) {
    if (shop && y === rows - 1) continue;
    const on = r() < lit; g.fillStyle = on ? '#ffd890' : hex(win); g.fillRect(x * cw + cw * 0.22, y * rh + rh * 0.2, cw * 0.56, rh * 0.55);
    g.fillStyle = 'rgba(255,255,255,0.25)'; g.fillRect(x * cw + cw * 0.22, y * rh + rh * 0.2, cw * 0.56, 1);
    g.fillStyle = 'rgba(0,0,0,0.25)'; g.fillRect(x * cw + cw * 0.18, y * rh + rh * 0.77, cw * 0.64, 2);
  }
  if (shop) { g.fillStyle = hex(shop); g.fillRect(0, (rows - 1) * rh, S, rh * 0.25); g.fillStyle = '#26303a'; g.fillRect(S * 0.08, (rows - 1) * rh + rh * 0.32, S * 0.84, rh * 0.6); g.fillStyle = 'rgba(255,230,180,0.5)'; g.fillRect(S * 0.12, (rows - 1) * rh + rh * 0.4, S * 0.5, rh * 0.45); }
  const t = new THREE.CanvasTexture(c); t.magFilter = THREE.NearestFilter; t.colorSpace = THREE.SRGBColorSpace; return t;
}
function building(group, x, z, w, h, d, wall, win, o = {}) {
  const tex = facadeTex(wall, win, { cols: Math.max(2, Math.round(w / 2.2)), rows: Math.max(2, Math.round(h / 2.8)), ...o });
  const front = mat4(tex, { rim: 0.4 }); const side = mat4(grunge(shade(wall, 0.9).getHex(), { size: 16, noise: 0.12, seed: o.seed ?? 3 }), { rim: 0.4 });
  const m = new THREE.Mesh(white(new THREE.BoxGeometry(w, h, d)), [side, side, side, side, front, side]); m.position.set(x, h / 2, z); m.castShadow = true; m.receiveShadow = true;
  const g = m.geometry; const uv = g.attributes.uv; // uv 0..1 par face : la façade (face +z) prend toute la texture
  group.add(m);
  if (o.roof !== false) group.add(Object.assign(vox([{ x, y: h + 0.15, z, w: w + 0.3, h: 0.3, d: d + 0.3, color: shade(wall, 0.7) }]), {}));
  return m;
}
function ground(group, w, d, color, o = {}) {
  const m = new THREE.Mesh(white(new THREE.BoxGeometry(w, 0.4, d)), o.mat || mat4(grunge(color, { size: 32, noise: o.noise ?? 0.14, dark: 0.08, seed: o.seed ?? 5 }), { rim: 0.2, wet: o.wet ?? 0.2 }));
  m.position.set(o.x ?? 0, -0.2 + (o.y ?? 0), o.z ?? 0); m.receiveShadow = true; group.add(m);
  const uv = m.geometry.attributes.uv; const rep = o.rep ?? 0.5; for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * w * rep, uv.getY(i) * d * rep);
  const mp = (Array.isArray(m.material) ? m.material[0] : m.material).map; if (mp) { mp.wrapS = mp.wrapT = THREE.RepeatWrapping; } return m;
}
// arbre voxel : tronc qui monte jusque dans la couronne, branches, couronne pleine (bord irrégulier) posée sur le tronc
function treeBoxes(x, z, h, r, cols, rnd, trunk = 0x5a3a22) {
  const B = [{ x, y: h * 0.52, z, w: 0.36, h: h * 1.04, d: 0.36, color: trunk }, { x, y: 0.08, z, w: 0.52, h: 0.16, d: 0.52, color: shade(trunk, 0.85) }];
  for (let i = 0; i < 4; i++) { const a = i * 1.571 + rnd() * 0.6, L = r * 0.9, by = h * (0.72 + rnd() * 0.15);
    B.push({ x: x + Math.cos(a) * L * 0.32, y: by + L * 0.38, z: z + Math.sin(a) * L * 0.32, w: 0.15, h: L, d: 0.15, color: shade(trunk, 0.95), rx: Math.sin(a) * 0.75, rz: -Math.cos(a) * 0.75 }); }
  const cy = h + r * 0.3, st = 0.4;
  for (let dx = -r; dx <= r + 1e-6; dx += st) for (let dy = -r * 0.85; dy <= r * 0.9; dy += st) for (let dz = -r; dz <= r + 1e-6; dz += st) {
    const q = (dx * dx + dz * dz) / (r * r) + (dy * dy) / (r * r * 0.72); if (q > 1 || q < 0.45) continue; if (q > 0.82 && rnd() < 0.35) continue;
    const sz = st * (1.0 + rnd() * 0.3); B.push({ x: x + dx + (rnd() - 0.5) * 0.08, y: cy + dy, z: z + dz + (rnd() - 0.5) * 0.08, w: sz, h: sz, d: sz, color: shade(cols[(rnd() * cols.length) | 0], 0.82 + rnd() * 0.32) });
  }
  B.push({ x, y: cy, z, w: r * 1.25, h: r * 1.05, d: r * 1.25, color: shade(cols[0], 0.55) });
  return B;
}
function lampBoxes(x, z, h = 4.2, col = 0x2a2c30) { return [{ x, y: h / 2, z, w: 0.14, h, d: 0.14, color: col }, { x, y: h, z: z + 0.35, w: 0.12, h: 0.12, d: 0.8, color: col }, { x, y: h - 0.12, z: z + 0.7, w: 0.34, h: 0.14, d: 0.3, color: 0x3a3c40 }]; }
function carBoxes(x, z, col, rnd, ry = 0) {
  const B = [{ x: 0, y: 0.55, z: 0, w: 3.6, h: 0.6, d: 1.6, color: col }, { x: -0.2, y: 1.05, z: 0, w: 2.0, h: 0.5, d: 1.45, color: shade(col, 0.95) },
    { x: -0.2, y: 1.06, z: 0.73, w: 1.8, h: 0.36, d: 0.02, color: 0x2a3440 }, { x: -0.2, y: 1.06, z: -0.73, w: 1.8, h: 0.36, d: 0.02, color: 0x2a3440 }, { x: 0.82, y: 1.04, z: 0, w: 0.02, h: 0.36, d: 1.3, color: 0x2a3440 },
    { x: 1.81, y: 0.62, z: 0.55, w: 0.02, h: 0.14, d: 0.3, color: 0xfff2d0 }, { x: 1.81, y: 0.62, z: -0.55, w: 0.02, h: 0.14, d: 0.3, color: 0xfff2d0 }, { x: -1.81, y: 0.62, z: 0.55, w: 0.02, h: 0.12, d: 0.3, color: 0xd02020 }, { x: -1.81, y: 0.62, z: -0.55, w: 0.02, h: 0.12, d: 0.3, color: 0xd02020 }];
  for (const [wx, wz] of [[1.15, 0.8], [1.15, -0.8], [-1.15, 0.8], [-1.15, -0.8]]) B.push({ x: wx, y: 0.32, z: wz, w: 0.62, h: 0.62, d: 0.24, color: 0x18181a });
  const c = Math.cos(ry), s = Math.sin(ry); return B.map((b) => ({ ...b, x: x + b.x * c + b.z * s, z: z - b.x * s + b.z * c, ry }));
}
function starsPoints(n, R, seed, size = 1.6) {
  const r = mulberry(seed); const p = new Float32Array(n * 3); for (let i = 0; i < n; i++) { const u = r() * 2 - 1, a = r() * 6.283, s = Math.sqrt(1 - u * u); p.set([Math.cos(a) * s * R, Math.abs(u) * R * 0.95 + 2, Math.sin(a) * s * R], i * 3); }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(p, 3));
  const pts = new THREE.Points(g, new THREE.PointsMaterial({ color: 0xffffff, size, sizeAttenuation: false, fog: false })); pts.frustumCulled = false; return pts;
}
function planetTex(seed, a = 0x2a5ab8, b = 0x3a9a4a, c = 0xf2f6ff, bands = false) {
  const W = 256, H = 128; const cv = document.createElement('canvas'); cv.width = W; cv.height = H; const g = cv.getContext('2d'); const r = mulberry(seed); const hex = (h) => '#' + new THREE.Color(h).getHexString();
  g.fillStyle = hex(a); g.fillRect(0, 0, W, H);
  if (bands) { for (let y = 0; y < H; y += 4) { g.fillStyle = `rgba(255,255,255,${0.05 + 0.25 * r()})`; g.fillRect(0, y, W, 2 + r() * 4); } }
  else { for (let i = 0; i < 26; i++) { g.fillStyle = hex(b); const x = r() * W, y = 20 + r() * (H - 40); for (let k = 0; k < 12; k++) g.fillRect(x + (r() - 0.5) * 40, y + (r() - 0.5) * 22, 8 + r() * 14, 6 + r() * 10); }
    for (let i = 0; i < 40; i++) { g.fillStyle = 'rgba(255,255,255,0.75)'; g.fillRect(r() * W, r() * H, 10 + r() * 30, 2 + r() * 4); } g.fillStyle = hex(c); g.fillRect(0, 0, W, 8); g.fillRect(0, H - 8, W, 8); }
  const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; return t;
}

export function footprintTex() {
  const c = document.createElement('canvas'); c.width = 32; c.height = 64; const g = c.getContext('2d'); g.clearRect(0, 0, 32, 64);
  const fill = (a) => `rgba(255,255,255,${a})`;
  g.fillStyle = fill(0.85); g.beginPath(); g.ellipse(16, 48, 10, 12, 0, 0, 7); g.fill(); g.beginPath(); g.ellipse(16, 18, 12, 15, 0, 0, 7); g.fill();
  g.fillStyle = fill(1); for (let y = 6; y < 32; y += 4) g.fillRect(6, y, 20, 2); for (let y = 40; y < 58; y += 4) g.fillRect(8, y, 16, 2);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
// --------------------------------------------------------------------- les mondes
export function buildWorlds(ctx, base = V(3000, 0, 0), step = 400) {
  const { scene } = ctx; const W = [];
  const mk = (name, i) => { const group = new THREE.Group(); const origin = base.clone().add(V(i * step, 0, 0)); group.position.copy(origin); scene.add(group); const w = { name, group, origin, at: (x, y, z) => origin.clone().add(V(x, y, z)), npc: [], update: () => {} }; W.push(w); return w; };
  const day = (S, o = {}) => {
    S.key = { dir: o.dir ?? [-0.5, 0.75, 0.55], color: o.sun ?? 0xfff0d8, i: o.ki ?? 2.0 }; S.hemi = { sky: o.sky ?? 0xa8c4ff, ground: o.gnd ?? 0x6a5a48, i: o.hi ?? 0.85 };
    S.fill = { dir: [0.6, 0.3, 0.8], color: o.fillc ?? 0xb8c8ff, i: o.fi ?? 0.35 }; S.fog = { color: o.fog ?? 0xc8d8f0, d: o.fogd ?? 0.008 }; S.bg = o.bg ?? 0xa8c8ff;
    S.rim = { color: o.rim ?? 0xffe8d0, i: o.rimi ?? 0.18, pow: 4 }; S.edge = null; S.spark = null; S.bloom = o.bloom ?? 0.3; S.bloomThreshold = 0.92; S.bloomRadius = 0.5;
    S.contrast = o.con ?? 0.14; S.sat = o.sat ?? 1.12; S.vignette = o.vig ?? 0.32; S.vigCol = 0x050505; S.lift = 0x020202; S.shadowTint = o.st ?? 0xd8e0ff; S.highTint = o.ht ?? 0xfff6ea; S.grain = 0.02; S.lights = [];
  };

  // ---------------------------------------------------------------- 0. ville au matin
  { const w = mk('ville', 0); const g = w.group; const r = mulberry(11);
    w.skyU = sky(g, { top: 0x4a86e0, mid: 0xbcd6f4, bot: 0xb0c4d8, sun: [-0.6, 0.45, -0.7], sunCol: 0xfff0c8 });
    ground(g, 80, 40, 0x8a8a8e, { z: -6, seed: 12 });                                                                   // chaussée
    const sw = mat4(tiles(0xc8c4bc, 0xb4b0a8, { size: 32, n: 4, seed: 13, grout: 0x8a8680 }), { rim: 0.2 });
    ground(g, 80, 3.8, 0, { mat: sw, z: 0, y: 0.12 }); ground(g, 80, 3.0, 0, { mat: sw, z: -11.5, y: 0.12 });                  // trottoirs
    const B = [];
    for (let x = -38; x < 38; x += 3.2) B.push({ x, y: 0.015, z: -6.2, w: 1.6, h: 0.03, d: 0.16, color: 0xf2f0e6 });          // marquage
    for (let x = -38; x < 38; x += 1) B.push({ x, y: 0.135, z: -1.92, w: 1.0, h: 0.27, d: 0.16, color: 0xa8a49c });             // bordure
    for (let x = -30; x < 30; x += 7) { B.push(...lampBoxes(x, -1.6)); B.push({ x: x + 3.5, y: 0.5, z: -1.4, w: 1.0, h: 0.8, d: 1.0, color: 0x6a5a4a }); B.push(...treeBoxes(x + 3.5, -1.4, 3.1, 1.0, [0x3a8a3a, 0x4a9a3a, 0x2f7a34], r)); }
    B.push(...carBoxes(-6, -3.6, 0xc83030, r), ...carBoxes(5, -3.6, 0x2a5ab0, r), ...carBoxes(14, -3.6, 0xe8e4dc, r));
    g.add(vox(B));
    const pal = [[0xd8b89a, 0x4a5a6a], [0xa8463a, 0x3a4a5a], [0xe8dcc0, 0x5a6a7a], [0x6a8aa8, 0x2a3a4a], [0xc89a6a, 0x4a4a5a], [0xb8c4c8, 0x3a4a5a]];
    let x = -36; let k = 0; while (x < 34) { const bw = 5 + (k * 7 % 4); const bh = 8 + (k * 5 % 9); const p = pal[k % pal.length]; building(g, x + bw / 2, -15.5, bw, bh, 5, p[0], p[1], { seed: 20 + k, shop: k % 2 ? 0xd84a3a : 0x3a8ad8, lit: 0.05 }); x += bw + 0.2; k++; }
    for (let i = 0; i < 6; i++) building(g, -34 + i * 13, -30, 10, 18 + (i * 7 % 10), 6, 0x9aa8b8, 0x5a6a7a, { seed: 40 + i, lit: 0 });
    const car = vox(carBoxes(0, 0, 0xf0c020, r)); g.add(car); w.movers = [car];
    w.update = (t) => { car.position.set(-30 + ((t * 7) % 60), 0, -8.2); };
    w.look = (S) => { day(S, { dir: [-0.6, 0.55, -0.4], sun: 0xffe6c0, ki: 2.1, fog: 0xc8d8ee, bg: 0xbcd6f4 }); S.dust = { i: 0.5, col: 0xfff2d8, size: 0.7, box: V(6, 4, 6) }; }; }

  // ---------------------------------------------------------------- 1. parc au printemps
  { const w = mk('parc', 1); const g = w.group; const r = mulberry(21);
    sky(g, { top: 0x3a7ae0, mid: 0xc8e0ff, bot: 0x9ab87a, sun: [0.3, 0.6, -0.8] });
    ground(g, 90, 60, 0x5aa04a, { z: -10, seed: 22, noise: 0.18 });
    ground(g, 90, 2.4, 0xc8b48a, { z: 0, y: 0.03, seed: 23 });                                                        // allée
    const B = [];
    for (let i = 0; i < 260; i++) { const x = (r() - 0.5) * 70, z = -2 - r() * 30; const c = [0xf06a8a, 0xf8e04a, 0xffffff, 0xb07ae0, 0xf08a3a][i % 5]; B.push({ x, y: 0.08, z, w: 0.14, h: 0.14, d: 0.14, color: c }, { x, y: 0.03, z: z + 0.1, w: 0.04, h: 0.1, d: 0.04, color: 0x3a7a2a }); }
    for (let i = 0; i < 18; i++) { const x = -32 + i * 3.8 + (r() - 0.5) * 2, z = -4 - r() * 18; B.push(...treeBoxes(x, z, 3 + r() * 2, 1.1 + r() * 0.7, i % 3 ? [0x4a9a3a, 0x5aaa44, 0x3a8a34] : [0xf2b8c8, 0xf8d0dc, 0xe898b0], r)); }
    for (let i = 0; i < 4; i++) { const x = -12 + i * 8; B.push({ x, y: 0.42, z: -1.6, w: 1.6, h: 0.08, d: 0.45, color: 0x8a5a32 }, { x, y: 0.7, z: -1.82, w: 1.6, h: 0.4, d: 0.06, color: 0x8a5a32 }, { x: x - 0.7, y: 0.2, z: -1.6, w: 0.08, h: 0.4, d: 0.4, color: 0x2a2a2a }, { x: x + 0.7, y: 0.2, z: -1.6, w: 0.08, h: 0.4, d: 0.4, color: 0x2a2a2a }); }
    for (let i = 0; i < 8; i++) { const x = -40 + i * 11; B.push({ x, y: 1.5 + (i % 3), z: -45, w: 14, h: 3 + (i % 3) * 2, d: 6, color: 0x6aa860 }); }   // collines
    g.add(vox(B, { var: 0.08 }));
    // étang
    const pond = new THREE.Mesh(new THREE.BoxGeometry(9, 0.05, 5), new THREE.MeshPhongMaterial({ color: 0x4a8ac8, shininess: 90, specular: 0xffffff, transparent: true, opacity: 0.85 })); pond.position.set(4, 0.02, -9); g.add(pond);
    w.look = (S) => { day(S, { dir: [0.3, 0.7, -0.6], sun: 0xfff4dc, ki: 2.0, sky: 0xb0d0ff, gnd: 0x5a7a3a, fog: 0xd0e4f8, bg: 0xc8e0ff, sat: 1.18 }); S.snow = { i: 0.9, col: 0xffc8dc, size: 1.2, speed: 0.35 }; }; }

  // ---------------------------------------------------------------- 2. automne
  { const w = mk('automne', 2); const g = w.group; const r = mulberry(31);
    sky(g, { top: 0x5a7ac0, mid: 0xf2c890, bot: 0xb0804a, sun: [-0.5, 0.18, -0.85], sunCol: 0xffc070, sunSize: 0.04 });
    ground(g, 90, 60, 0x9a7a3a, { z: -10, seed: 32 }); ground(g, 90, 2.4, 0xb8a07a, { z: 0, y: 0.03, seed: 33 });
    const B = [];
    for (let i = 0; i < 500; i++) { const x = (r() - 0.5) * 70, z = 1.4 - r() * 30; B.push({ x, y: 0.02, z, w: 0.18, h: 0.03, d: 0.14, color: [0xd8682a, 0xe8a03a, 0xb83a1a, 0xf0c050][i % 4], ry: r() * 3 }); }
    for (let i = 0; i < 20; i++) { const x = -34 + i * 3.6 + (r() - 0.5) * 2, z = -3.5 - r() * 16; B.push(...treeBoxes(x, z, 3.2 + r() * 2, 1.2 + r() * 0.6, i % 2 ? [0xd8682a, 0xe8902a, 0xc84a1a] : [0xe8b03a, 0xd8882a, 0xf0c050], r, 0x4a2a1a)); }
    for (let i = 0; i < 10; i++) B.push({ x: -30 + i * 6.5, y: 0.45, z: -1.7, w: 0.12, h: 0.9, d: 0.12, color: 0x6a4a2a }, { x: -30 + i * 6.5 + 3.25, y: 0.75, z: -1.7, w: 6.5, h: 0.08, d: 0.08, color: 0x6a4a2a });   // barrière
    g.add(vox(B, { var: 0.08 }));
    w.look = (S) => { day(S, { dir: [-0.5, 0.3, -0.85], sun: 0xffb060, ki: 2.3, sky: 0xf0c890, gnd: 0x6a4a2a, fog: 0xe8c090, fogd: 0.012, bg: 0xf2c890, st: 0xd8b8a8, ht: 0xffe8c8, sat: 1.2 });
      S.snow = { i: 1.1, col: 0xe8802a, size: 1.6, speed: 0.4 }; }; }

  // ---------------------------------------------------------------- 3. ville sous la pluie
  { const w = mk('pluie', 3); const g = w.group; const r = mulberry(41);
    sky(g, { top: 0x4a525e, mid: 0x7a8490, bot: 0x5a6068 });
    const wetM = ctx.reflector.makeMaterial({ map: grunge(0x3a3c42, { size: 32, noise: 0.25, seed: 42 }), color: 0xffffff, tpm: 0.35, reflect: 0.75, rough: 0.004, ripple: 1.0, tint: 0xe8f0ff, glitter: 0.2, glitterCol: 0xffe0c0 });
    const pl = new THREE.Mesh(new THREE.PlaneGeometry(120, 80), wetM); pl.rotation.x = -Math.PI / 2; pl.position.set(0, 0.01, -10); g.add(pl); w.reflectY = 0.01;
    const pal = [[0x6a6a72, 0x2a3038], [0x8a5a4a, 0x2a3038], [0x5a6a7a, 0x2a3038], [0x7a7a6a, 0x2a3038]];
    let x = -36; let k = 0; while (x < 34) { const bw = 5 + (k * 3 % 4); const bh = 9 + (k * 5 % 8); building(g, x + bw / 2, -9.5, bw, bh, 5, pal[k % 4][0], pal[k % 4][1], { seed: 50 + k, shop: [0xe8a03a, 0x3ac8a8, 0xd84a6a][k % 3], lit: 0.4 }); x += bw + 0.2; k++; }
    const B = []; for (let x2 = -30; x2 < 30; x2 += 6) B.push(...lampBoxes(x2, -2.5));
    g.add(vox(B));
    w.lamps = []; for (let x2 = -30; x2 < 30; x2 += 6) w.lamps.push(w.at(x2, 4.0, -1.8));
    w.look = (S, t, P) => { day(S, { dir: [0.3, 0.8, 0.4], sun: 0xc8d4e8, ki: 0.7, sky: 0x8a96a8, gnd: 0x2a2c30, hi: 0.7, fog: 0x6a747e, fogd: 0.03, bg: 0x6a747e, con: 0.2, sat: 0.9, vig: 0.45, st: 0xb8c8e0 });
      S.rain = { i: 1.6, col: 0xc8d4ea, size: 7, speed: 1 }; S.reflect = { y: w.origin.y + 0.01 }; S.spark = { i: 1.2, col: 0xffe0c0, den: 0.04, size: 0.02 };
      S.lights = w.lamps.map((p) => ({ pos: p, color: 0xffc070, i: 3, dist: 7 })); }; }

  // ---------------------------------------------------------------- 4. glacier
  { const w = mk('glace', 4); const g = w.group; const r = mulberry(51);
    sky(g, { top: 0x2a6ad8, mid: 0xd8ecff, bot: 0xe8f4ff, sun: [0.5, 0.5, -0.7], sunCol: 0xffffff });
    ground(g, 100, 70, 0xeef4ff, { z: -12, seed: 52, noise: 0.06 });
    const ice = new THREE.MeshPhongMaterial({ color: 0x9ad8ff, emissive: 0x0a3050, shininess: 100, specular: 0xffffff, transparent: true, opacity: 0.82 }); rimify(ice, 0.6, 1.2);
    const B = [];
    for (let i = 0; i < 70; i++) { const x = (r() - 0.5) * 70, z = -2.5 - r() * 30, h = 0.6 + r() * 3.5 * (1 + (-z) / 20); B.push({ x, y: h / 2, z, w: 0.6 + r() * 1.6, h, d: 0.6 + r() * 1.6, color: shade(0xb8e8ff, 0.85 + r() * 0.25), ry: r() * 1.5, rz: (r() - 0.5) * 0.3 }); }
    const im = new THREE.Mesh(boxesGeometry(B), new THREE.MeshPhongMaterial({ vertexColors: true, emissive: 0x0a2a40, shininess: 100, specular: 0xffffff, transparent: true, opacity: 0.85 })); im.castShadow = true; im.receiveShadow = true; g.add(im);
    const M = []; for (let i = 0; i < 9; i++) { const x = -60 + i * 15, h = 18 + (i * 7 % 14); for (let k = 0; k < 6; k++) M.push({ x: x + (k - 2.5) * 2, y: h * (1 - k / 7) / 2, z: -70, w: 16 - k * 2.2, h: h * (1 - k / 7), d: 8, color: k > 3 ? 0xffffff : 0x8a9ab8 }); }
    g.add(vox(M, { var: 0.05 }));
    const snowB = []; for (let i = 0; i < 400; i++) snowB.push({ x: (r() - 0.5) * 60, y: 0.04, z: 1.5 - r() * 25, w: 0.3 + r() * 0.5, h: 0.08, d: 0.3 + r() * 0.5, color: 0xf8fbff });
    g.add(vox(snowB, { var: 0.03 }));
    w.look = (S) => { day(S, { dir: [0.5, 0.55, -0.7], sun: 0xffffff, ki: 2.2, sky: 0xc8e4ff, gnd: 0xa8c8e8, hi: 1.0, fog: 0xd8ecff, fogd: 0.012, bg: 0xd8ecff, st: 0xb8d0ff, ht: 0xf4faff, sat: 1.05, bloom: 0.45 });
      S.snow = { i: 1.4, col: 0xffffff, size: 1, speed: 0.8 }; S.spark = { i: 2, col: 0xd8f0ff, den: 0.05, size: 0.02 }; }; }

  // ---------------------------------------------------------------- 5. ruines en feu
  { const w = mk('feu', 5); const g = w.group; const r = mulberry(61);
    sky(g, { top: 0x2a1410, mid: 0xc8501a, bot: 0x4a1a0a, sun: [-0.3, 0.12, -0.9], sunCol: 0xff6a20, sunSize: 0.06 });
    ground(g, 100, 70, 0x2a2420, { z: -12, seed: 62 });
    const lava = lavaMaterial({ k: 1 }); w.lava = lava;
    for (let i = 0; i < 14; i++) { const m = new THREE.Mesh(new THREE.BoxGeometry(0.3 + r() * 0.5, 0.02, 2 + r() * 6), lava); m.position.set((r() - 0.5) * 40, 0.01, -2.5 - r() * 20); m.rotation.y = r() * 3; g.add(m); }
    const B = [];
    for (let i = 0; i < 16; i++) { const x = -32 + i * 4.2, z = -4 - r() * 14, h = 1 + r() * 5; B.push({ x, y: h / 2, z, w: 3 + r() * 2, h, d: 0.6, color: shade(0x5a4a42, 0.6 + r() * 0.4) });
      for (let k = 0; k < 6; k++) B.push({ x: x + (r() - 0.5) * 3, y: r() * 0.4, z: z + 1 + r() * 2, w: 0.4 + r() * 0.6, h: 0.3 + r() * 0.4, d: 0.4 + r() * 0.6, color: 0x3a302a }); }
    for (let i = 0; i < 5; i++) { const x = -16 + i * 8, z = -14 - (i % 2) * 4; for (let k = 0; k < 4; k++) B.push({ x: x + (k - 1.5) * 1.6, y: 2 + k * 0.6, z, w: 1.2, h: 4 + k * 1.2, d: 1.2, color: 0x2a2220 }); B.push({ x, y: 7.5, z, w: 6, h: 0.6, d: 1.4, color: 0x2a2220, rz: 0.2 }); }
    g.add(vox(B));
    // flammes : grappes de cubes émissifs qui scintillent
    w.flames = [];
    const fm = [glow(0xffd060, 1.8), glow(0xff8a20, 1.6), glow(0xff3a10, 1.3)];
    for (let i = 0; i < 30; i++) { const fg = new THREE.Group(); const x = (r() - 0.5) * 40, z = -2.4 - r() * 12; fg.position.set(x, 0, z); fg.scale.setScalar(1.2 + r() * 1.3); g.add(fg);
      for (let k = 0; k < 7; k++) { const s = 0.18 + r() * 0.3; const m = new THREE.Mesh(new THREE.BoxGeometry(s, s * 1.6, s), fm[k % 3]); m.position.set((r() - 0.5) * 0.6, 0.2 + k * 0.22, (r() - 0.5) * 0.6); m.userData.ph = r() * 6; fg.add(m); }
      w.flames.push(fg); }
    w.update = (t) => { lava.uniforms.uTime.value = t; w.flames.forEach((fg, i) => fg.children.forEach((m, k) => { const f = 0.75 + 0.35 * Math.sin(t * 9 + m.userData.ph + i); m.scale.set(f, f * (1 + 0.3 * Math.sin(t * 13 + k)), f); m.position.y = 0.2 + k * 0.22 * f + 0.05 * Math.sin(t * 7 + k); })); };
    w.look = (S, t) => { day(S, { dir: [-0.4, 0.55, 0.6], sun: 0xffb070, ki: 1.9, sky: 0x8a5a4a, gnd: 0x8a3a1a, hi: 0.8, fillc: 0xff7a30, fi: 0.4, fog: 0x5a2a18, fogd: 0.016, bg: 0x5a1a0a, con: 0.22, sat: 1.08, vig: 0.45, bloom: 0.6, st: 0xb8a8a0, ht: 0xffe0c0 });
      S.embers = { i: 2.5, col: 0xff8a30, size: 1, speed: 1 }; S.rim = { color: 0xff6a20, i: 0.35, pow: 4 };
      S.lights = w.flames.slice(0, 8).map((fg, i) => ({ pos: fg.getWorldPosition(V()).add(V(0, 1, 0)), color: 0xff8a30, i: 2.4 * (0.8 + 0.2 * Math.sin(t * 11 + i)), dist: 8 }));
      S.mist = { list: [0, 1, 2].map((i) => ({ pos: w.at(-8 + i * 8, 1.5, -10), w: 18, h: 6, yaw: 0, k: 1 })), col: 0x2a1a14, i: 0.5 }; }; }

  // ---------------------------------------------------------------- 6. champ de bataille
  { const w = mk('bataille', 6); const g = w.group; const r = mulberry(71);
    sky(g, { top: 0x5a6070, mid: 0xb8a890, bot: 0x7a6a50, sun: [-0.3, 0.35, -0.9], sunCol: 0xffe0b0 });
    ground(g, 100, 70, 0x7a6a4a, { z: -12, seed: 72, noise: 0.2 });
    const B = [];
    for (let i = 0; i < 10; i++) { const x = -30 + i * 6.5, z = -12 - r() * 6; B.push({ x, y: 2, z, w: 0.12, h: 4, d: 0.12, color: 0x4a3a2a }, { x: x + 0.6, y: 3.4, z, w: 1.1, h: 0.8, d: 0.04, color: i % 2 ? 0xc02a2a : 0x2a4ac0 }); }
    for (let i = 0; i < 40; i++) B.push({ x: (r() - 0.5) * 60, y: 0.25, z: -3 - r() * 25, w: 0.5 + r() * 0.8, h: 0.5, d: 0.5 + r() * 0.8, color: 0x6a6258 });
    for (let i = 0; i < 6; i++) B.push({ x: -40 + i * 16, y: 6, z: -60, w: 12, h: 12, d: 6, color: 0x7a7a72 }, { x: -40 + i * 16, y: 13, z: -60, w: 3, h: 3, d: 6, color: 0x6a6a62 });   // remparts au loin
    g.add(vox(B));
    w.look = (S) => { day(S, { dir: [-0.3, 0.45, -0.9], sun: 0xffe0b0, ki: 1.8, sky: 0xb8a890, gnd: 0x5a4a3a, fog: 0xb8a890, fogd: 0.02, bg: 0xb8a890, con: 0.2, sat: 1.0, st: 0xc8c0b8 });
      S.dust = { i: 2.2, col: 0xd8c8a8, size: 1.2, box: V(10, 4, 10) }; }; }

  // ---------------------------------------------------------------- 7. invasion (crépuscule, soucoupes)
  { const w = mk('invasion', 7); const g = w.group; const r = mulberry(81);
    sky(g, { top: 0x1a1440, mid: 0xd86a5a, bot: 0x3a2a3a, sun: [0.6, 0.06, -0.8], sunCol: 0xff8a50, sunSize: 0.05 });
    ground(g, 100, 70, 0x4a4a52, { z: -12, seed: 82 });
    let x = -40; let k = 0; while (x < 40) { const bw = 5 + (k * 3 % 5); const bh = 10 + (k * 7 % 14); building(g, x + bw / 2, -16, bw, bh, 6, 0x3a3a4a, 0x2a2a3a, { seed: 90 + k, lit: 0.35 }); x += bw + 0.4; k++; }
    const sauc = []; const sm = vmat({ var: 0.05 }); const lightM = glow(0x8affc0, 3); const beamM = new THREE.MeshBasicMaterial({ color: 0x8affd0, transparent: true, opacity: 0.18, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide, fog: false });
    for (let i = 0; i < 4; i++) { const sg = new THREE.Group(); const D = []; for (let a = 0; a < 16; a++) { const an = a / 16 * 6.283; D.push({ x: Math.cos(an) * 2.6, y: 0, z: Math.sin(an) * 2.6, w: 1.2, h: 0.35, d: 1.2, color: 0x9aa4b0, ry: -an }); }
      D.push({ x: 0, y: 0.1, z: 0, w: 4.6, h: 0.5, d: 4.6, color: 0x8a94a0 }, { x: 0, y: 0.6, z: 0, w: 2.2, h: 0.9, d: 2.2, color: 0x6ad8b0 });
      sg.add(vox(D, { mat: sm }));
      for (let a = 0; a < 8; a++) { const an = a / 8 * 6.283; const l = new THREE.Mesh(new THREE.BoxGeometry(0.25, 0.15, 0.25), lightM); l.position.set(Math.cos(an) * 3.2, -0.05, Math.sin(an) * 3.2); sg.add(l); }
      const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.8, 3.2, 1, 24, 1, true), beamM); beam.position.y = -0.5; sg.add(beam); sg.userData.beam = beam;
      sg.position.set(-14 + i * 10 + (r() - 0.5) * 3, 14 + r() * 6, -10 - r() * 10); sg.userData.ph = r() * 6; g.add(sg); sauc.push(sg); }
    w.sauc = sauc;
    w.update = (t) => { sauc.forEach((s, i) => { s.rotation.y = t * 0.8 + i; const y = 9 + 5 * Math.sin(t * 0.25 + s.userData.ph) + i * 1.5; s.position.y = y; const b = s.userData.beam; b.scale.set(1, y, 1); b.position.y = -y / 2; }); };
    w.look = (S, t) => { day(S, { dir: [0.45, 0.35, 0.8], sun: 0xff9a70, ki: 1.5, sky: 0x8a6aaa, gnd: 0x3a2a40, hi: 0.95, fillc: 0x6affc0, fi: 0.5, fog: 0x5a3a5a, fogd: 0.02, bg: 0xd86a5a, con: 0.2, sat: 1.15, vig: 0.45, bloom: 0.55 });
      S.lights = sauc.map((s) => ({ pos: s.getWorldPosition(V()).setY(w.origin.y + 1.2), color: 0x8affc0, i: 2.4, dist: 10 })); S.dust = { i: 0.8, col: 0xb8ffe0, size: 0.8, box: V(8, 4, 8) }; }; }

  // ---------------------------------------------------------------- 8. vaisseau spatial
  { const w = mk('vaisseau', 8); const g = w.group; const r = mulberry(91);
    const panel = mat4(tiles(0x8a929c, 0x7a828c, { size: 32, n: 2, seed: 92, grout: 0x4a5058 }), { rim: 0.5, shininess: 40, specular: 0x404850 });
    const dark = mat4(grunge(0x3a4048, { size: 16, noise: 0.1, seed: 93 }), { rim: 0.4 });
    const L = 60, Wd = 7, H = 4.2;
    const fl = new THREE.Mesh(white(new THREE.BoxGeometry(L, 0.3, Wd)), panel); fl.position.set(0, -0.15, -1.2); fl.receiveShadow = true; g.add(fl);
    const ce = new THREE.Mesh(white(new THREE.BoxGeometry(L, 0.3, Wd)), dark); ce.position.set(0, H, -1.2); g.add(ce);
    const B = []; const strip = []; const win = [];
    for (let x = -L / 2; x < L / 2; x += 4) {
      B.push({ x, y: H / 2, z: -4.6, w: 0.5, h: H, d: 0.6, color: 0x6a727c }, { x: x + 2, y: 0.4, z: -4.6, w: 3.5, h: 0.8, d: 0.4, color: 0x5a626c }, { x: x + 2, y: H - 0.4, z: -4.6, w: 3.5, h: 0.8, d: 0.4, color: 0x5a626c });
      B.push({ x, y: H - 0.05, z: -1.2, w: 0.5, h: 0.2, d: Wd, color: 0x5a626c });
      strip.push({ x: x + 2, y: H - 0.2, z: -1.2, w: 3.2, h: 0.06, d: 0.3, color: 0xffffff }); win.push(x + 2);
      for (let k = 0; k < 3; k++) strip.push({ x, y: 1.0 + k * 0.32, z: -4.28, w: 0.14, h: 0.14, d: 0.05, color: [0xff4040, 0x40ff80, 0x40a0ff][k] });   // voyants sur les piliers du fond
    }
    g.add(vox(B, { var: 0.06 })); const st = vox(strip, { mat: new THREE.MeshBasicMaterial({ vertexColors: true, fog: false }), cast: false }); g.add(st);
    // baies vitrées sur l'espace : étoiles + planète derrière
    const glassM = new THREE.MeshPhongMaterial({ color: 0x0a1428, transparent: true, opacity: 0.25, shininess: 120, specular: 0xffffff });
    for (const x of win) { const gl = new THREE.Mesh(new THREE.BoxGeometry(3.5, H - 1.6, 0.05), glassM); gl.position.set(x, H / 2, -4.6); g.add(gl); }
    const outside = new THREE.Group(); outside.position.set(0, 0, -60); g.add(outside);
    outside.add(starsPoints(2500, 60, 94, 1.5));
    const planet = new THREE.Mesh(new THREE.SphereGeometry(16, 48, 32), new THREE.MeshLambertMaterial({ map: planetTex(95, 0xc87a3a, 0, 0xffffff, true) })); planet.position.set(18, 6, -30); outside.add(planet); w.planet = planet;
    w.update = (t) => { planet.rotation.y = t * 0.05; };
    w.look = (S) => { day(S, { dir: [0.2, 1, 0.1], sun: 0xe8f0ff, ki: 0.6, sky: 0x8a9ab8, gnd: 0x2a3038, hi: 0.9, fillc: 0x8ad8ff, fi: 0.3, fog: 0x0a1020, fogd: 0.004, bg: 0x02040a, con: 0.18, sat: 1.05, vig: 0.4, bloom: 0.55, st: 0xc0d0e8 });
      S.lights = [-8, -4, 0, 4, 8].map((x) => ({ pos: w.at(x, H - 0.6, -1.2), color: 0xd8f0ff, i: 2.2, dist: 7 })); S.lights.push({ pos: w.at(0, 6, -30), color: 0xffa060, i: 2, dist: 40 }); }; }

  // ---------------------------------------------------------------- 9. surface de la Lune, la Terre dans le ciel, une lumière au loin
  { const w = mk('lune', 9); const g = w.group; const r = mulberry(101);
    sky(g, { top: 0x000000, mid: 0x02030a, bot: 0x050508, stars: 1.0 });
    ground(g, 140, 100, 0x8a8a8c, { z: -20, seed: 102, noise: 0.2 });
    const B = [];
    for (let i = 0; i < 26; i++) { const cx = (r() - 0.5) * 70, cz0 = -3 - r() * 40, R = 0.8 + r() * 3, cz = Math.min(cz0, -1.8 - R); /* aucun cratère sur le chemin (z≈0) */ for (let a = 0; a < 18; a++) { const an = a / 18 * 6.283; B.push({ x: cx + Math.cos(an) * R, y: 0.1, z: cz + Math.sin(an) * R, w: 0.6, h: 0.2 + r() * 0.15, d: 0.6, color: 0x9a9a9c, ry: an }); } B.push({ x: cx, y: -0.02, z: cz, w: R * 1.5, h: 0.04, d: R * 1.5, color: 0x6a6a6c }); }
    for (let i = 0; i < 60; i++) B.push({ x: (r() - 0.5) * 70, y: 0.15, z: ((z) => Math.abs(z) < 1.6 ? z - 3.2 : z)(1 - r() * 40), w: 0.2 + r() * 0.6, h: 0.3, d: 0.2 + r() * 0.6, color: 0x7a7a7c, ry: r() * 3 });
    g.add(vox(B, { var: 0.06 }));
    const earth = new THREE.Mesh(new THREE.SphereGeometry(9, 48, 32), new THREE.MeshLambertMaterial({ map: planetTex(103), emissive: 0x0a1a3a })); earth.position.set(-25, 30, -90); g.add(earth); w.earth = earth;
    // le but : une porte de lumière au bout du chemin
    const goal = new THREE.Group(); goal.position.set(14, 0, 0); g.add(goal); const gm = glow(0xfff4d8, 4);
    goal.add(Object.assign(new THREE.Mesh(new THREE.BoxGeometry(0.3, 4.2, 2.6), gm), {})); goal.children[0].position.y = 2.1;
    const halo = new THREE.Mesh(new THREE.PlaneGeometry(9, 9), new THREE.MeshBasicMaterial({ color: 0xfff0c8, transparent: true, opacity: 0.35, blending: THREE.AdditiveBlending, depthWrite: false, fog: false })); halo.position.set(-0.2, 2.1, 0); halo.rotation.y = -Math.PI / 2; goal.add(halo);
    w.goal = goal;
    w.update = (t) => { earth.rotation.y = t * 0.03; };
    w.look = (S) => { day(S, { dir: [0.8, 0.5, 0.3], sun: 0xffffff, ki: 2.4, sky: 0x1a1a24, gnd: 0x0a0a0c, hi: 0.35, fillc: 0x6a8ad8, fi: 0.25, fog: 0x000000, fogd: 0.002, bg: 0x000000, con: 0.3, sat: 1.0, vig: 0.45, bloom: 0.7, st: 0xa8b8d8 });
      S.lights = [{ pos: w.at(13, 2.2, 0), color: 0xfff0c8, i: 6, dist: 14 }]; }; }
  return W;
}
