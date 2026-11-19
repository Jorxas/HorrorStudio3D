import * as THREE from 'three';
import { mulberry, pick, toTex, blockTextures, plantTextures, miscTextures } from './textures.js';

export const B = { AIR: 0, GRASS: 1, DIRT: 2, PATH: 3, LOG: 4, LOGX: 5, BIRCH: 6, LEAF: 7, LEAFB: 8, LEAFG: 9, STONE: 10, WATER: 11, GLOG: 12, MOSS: 13 };
const OPAQUE = new Set([B.GRASS, B.DIRT, B.PATH, B.LOG, B.LOGX, B.BIRCH, B.STONE, B.GLOG, B.MOSS]);
const LEAVES = new Set([B.LEAF, B.LEAFB, B.LEAFG]);

const X0 = -60, X1 = 60, Z0 = -108, Z1 = 40, Y0 = -6, Y1 = 46;
const NX = X1 - X0, NY = Y1 - Y0, NZ = Z1 - Z0;

export const KEY = {
  clearing: new THREE.Vector3(0.5, 0, 0.5),
  glade: new THREE.Vector3(0.5, 0, -60),
  tree: new THREE.Vector3(0.5, 0, -69.5),
  doorFront: new THREE.Vector3(0.5, 0, -66),
  pond: new THREE.Vector3(-9.5, 0, -55),
};
export function pathX(z) { return 0.5 + 2.2 * Math.sin((z + 6) * 0.09); }

function hash2(x, z) { let h = Math.imul(x | 0, 374761393) + Math.imul(z | 0, 668265263); h = Math.imul(h ^ (h >>> 13), 1274126177); return ((h ^ (h >>> 16)) >>> 0) / 4294967296; }
function hash3(x, y, z) { return hash2(x * 7 + y * 131, z * 13 - y * 71); }
function vnoise(x, z) { const xi = Math.floor(x), zi = Math.floor(z); const xf = x - xi, zf = z - zi; const u = xf * xf * (3 - 2 * xf), v = zf * zf * (3 - 2 * zf); const a = hash2(xi, zi), b = hash2(xi + 1, zi), c = hash2(xi, zi + 1), d = hash2(xi + 1, zi + 1); return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v; }
const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
const dist2 = (x, z, cx, cz) => Math.hypot(x - cx, z - cz);

export function terrainH(x, z) {
  const n = vnoise(x * 0.055 + 10, z * 0.055 + 3) * 2.4 + vnoise(x * 0.13, z * 0.13 + 7) * 1.0;
  let h = n - 1.2;
  let flat = 0;
  flat = Math.max(flat, 1 - smooth(7.5, 11.5, dist2(x, z, 0.5, 0.5)));
  if (z > -48 && z < -2) flat = Math.max(flat, 1 - smooth(2.5, 6, Math.abs(x - pathX(z))));
  flat = Math.max(flat, 1 - smooth(19, 25, dist2(x, z, 0.5, -60)));
  h = h + (-1 - h) * flat;
  const rb = Math.max(0, 1 - ((z + 40.5) / 6.0) ** 2) * (1 - smooth(18, 28, Math.abs(x)));
  h = Math.max(h, -1 + 2.3 * rb);
  return Math.round(h);
}

export class World {
  constructor() { this.d = new Uint8Array(NX * NY * NZ); this.extra = { mushrooms: [], lanterns: [], glowShrooms: [] }; }
  idx(x, y, z) { return ((x - X0) * NY + (y - Y0)) * NZ + (z - Z0); }
  inb(x, y, z) { return x >= X0 && x < X1 && y >= Y0 && y < Y1 && z >= Z0 && z < Z1; }
  get(x, y, z) { if (y < Y0) return B.DIRT; if (!this.inb(x, y, z)) return B.AIR; return this.d[this.idx(x, y, z)]; }
  set(x, y, z, v) { if (!this.inb(x, y, z)) return; this.d[this.idx(x, y, z)] = v; }
  setIfAir(x, y, z, v) { if (!this.inb(x, y, z)) return; const i = this.idx(x, y, z); if (this.d[i] === B.AIR) this.d[i] = v; }
  top(x, z) { for (let y = Y1 - 1; y >= Y0; y--) { const t = this.get(x, y, z); if (t !== B.AIR && !LEAVES.has(t)) return y; } return Y0; }
  groundTop(x, z) { for (let y = 8; y >= Y0; y--) { const t = this.get(x, y, z); if (t === B.GRASS || t === B.PATH || t === B.DIRT || t === B.STONE) return y; } return -1; }
}

// ------------------------------------------------------------ generation
function blob(w, cx, cy, cz, rx, ry, rz, type, r, rough = 0.35) {
  for (let x = Math.floor(cx - rx - 1); x <= Math.ceil(cx + rx + 1); x++)
    for (let y = Math.floor(cy - ry - 1); y <= Math.ceil(cy + ry + 1); y++)
      for (let z = Math.floor(cz - rz - 1); z <= Math.ceil(cz + rz + 1); z++) {
        const dx = (x + 0.5 - cx) / rx, dy = (y + 0.5 - cy) / ry, dz = (z + 0.5 - cz) / rz;
        const d = dx * dx + dy * dy + dz * dz;
        if (d < 1 + (hash3(x, y, z) - 0.5) * rough * 2) w.setIfAir(x, y, z, type);
      }
}
function oak(w, x, y0, z, r) {
  const h = 5 + Math.floor(r() * 3); const R = 2.5 + r() * 0.8;
  for (let y = 0; y < h; y++) w.set(x, y0 + y, z, B.LOG);
  blob(w, x + 0.5, y0 + h - 0.5, z + 0.5, R, R * 0.8, R, B.LEAF, r);
}
function birch(w, x, y0, z, r) {
  const h = 6 + Math.floor(r() * 4); const R = 1.9 + r() * 0.6;
  for (let y = 0; y < h; y++) w.set(x, y0 + y, z, B.BIRCH);
  blob(w, x + 0.5, y0 + h - 0.8, z + 0.5, R, R * 1.35, R, B.LEAFB, r);
}
function bigOak(w, x, y0, z, r, hMin = 11, hMax = 16) {
  const h = hMin + Math.floor(r() * (hMax - hMin));
  for (let y = 0; y < h; y++) for (let dx = 0; dx < 2; dx++) for (let dz = 0; dz < 2; dz++) w.set(x + dx, y0 + y, z + dz, B.LOG);
  // roots
  for (const [dx, dz] of [[-1, 0], [2, 1], [0, -1], [1, 2]]) if (r() < 0.7) w.set(x + dx, y0, z + dz, B.LOG);
  const nb = 3 + Math.floor(r() * 2); const a0 = r() * 6.28;
  for (let b = 0; b < nb; b++) {
    const a = a0 + b * 6.28 / nb + (r() - 0.5) * 0.6; const len = 3 + Math.floor(r() * 2);
    let bx = x + 1, by = y0 + h - 4 - Math.floor(r() * 3), bz = z + 1;
    for (let i = 0; i < len; i++) { bx += Math.cos(a); bz += Math.sin(a); by += (i % 2 === 0 ? 1 : 0); w.set(Math.floor(bx), by, Math.floor(bz), B.LOG); }
    blob(w, bx + 0.5, by + 1.2, bz + 0.5, 3.0 + r() * 0.8, 2.2, 3.0 + r() * 0.8, B.LEAF, r);
  }
  blob(w, x + 1, y0 + h + 0.5, z + 1, 4.3 + r() * 0.8, 3.0, 4.3 + r() * 0.8, B.LEAF, r);
}

function giantTree(w, r) {
  const cx = 0, cz = -70; // trunk block x in [-3,3], z in [-73,-67]
  for (let y = -1; y < 23; y++) {
    const half = y < 11 ? 3 : y < 17 ? 2 : 1;
    for (let dx = -half; dx <= half; dx++) for (let dz = -half; dz <= half; dz++) {
      if (half >= 2 && Math.abs(dx) === half && Math.abs(dz) === half) continue; // chamfer
      w.set(cx + dx, y, cz + dz, B.GLOG);
    }
  }
  // flared base
  for (let dx = -4; dx <= 4; dx++) for (let dz = -4; dz <= 4; dz++) {
    const m = Math.max(Math.abs(dx), Math.abs(dz)); if (m !== 4) continue; if (Math.abs(dx) === 4 && Math.abs(dz) === 4) continue;
    if (Math.abs(dx) <= 1 && dz === 4) continue; // keep door free
    if (hash2(dx, dz) < 0.75) { w.set(cx + dx, 0, cz + dz, B.GLOG); if (hash2(dz, dx) < 0.4) w.set(cx + dx, 1, cz + dz, B.GLOG); }
  }
  // roots
  const roots = [[1, 1], [-1, 1], [1, -1], [-1, -1], [1, 0.25], [-1, 0.3], [0.2, -1]];
  for (const [ax, az] of roots) {
    const n = Math.hypot(ax, az); let px = cx + ax / n * 4, pz = cz + az / n * 4;
    const len = 3 + Math.floor(hash2(ax * 10, az * 10) * 4);
    for (let i = 0; i < len; i++) { px += ax / n; pz += az / n; w.set(Math.floor(px), 0, Math.floor(pz), B.GLOG); if (i < 1) w.set(Math.floor(px), 1, Math.floor(pz), B.GLOG); }
  }
  // branches
  const br = [[0.9, 0.4, 14], [-0.9, 0.5, 15], [0.3, -1, 16], [-0.5, -0.9, 13], [0.95, -0.4, 18], [-0.8, 0.9, 18], [0.1, 1, 17]];
  const ends = [];
  for (const [ax, az, y0] of br) {
    const n = Math.hypot(ax, az); let px = cx + 0.5, py = y0, pz = cz + 0.5;
    const len = 7 + Math.floor(hash2(y0, ax * 9) * 3);
    for (let i = 0; i < len; i++) { px += ax / n; pz += az / n; if (i % 2 === 1) py += 1; w.set(Math.floor(px), py, Math.floor(pz), B.GLOG); w.set(Math.floor(px), py - 1, Math.floor(pz), B.GLOG); }
    ends.push([px, py, pz]);
  }
  // canopy
  blob(w, cx + 0.5, 25, cz + 0.5, 12.5, 5.5, 12.5, B.LEAFG, r, 0.3);
  for (const [px, py, pz] of ends) blob(w, px, py + 1.5, pz, 5.2, 3.4, 5.2, B.LEAFG, r, 0.35);
  // hanging vines from canopy
  for (let k = 0; k < 70; k++) {
    const a = r() * 6.28, rad = 4 + r() * 12; const x = Math.floor(cx + Math.cos(a) * rad), z = Math.floor(cz + Math.sin(a) * rad);
    let y = 30; while (y > 8 && w.get(x, y, z) !== B.LEAFG) y--; if (y <= 8) continue;
    const L = 2 + Math.floor(r() * 5); for (let i = 1; i <= L; i++) w.setIfAir(x, y - i, z, B.LEAFG);
    if (k < 16 && r() < 0.9) w.extra.lanterns.push(new THREE.Vector3(x + 0.5, y - L - 0.6, z + 0.5));
  }
  // door: carve opening on +z face (front block row z=-67), depth 3
  for (let z = -67; z >= -69; z--) {
    for (let x = -1; x <= 1; x++) for (let y = 0; y <= 3; y++) w.set(x, y, z, B.AIR);
    w.set(0, 4, z, B.AIR);
  }
  // glowing mushrooms on roots / base
  for (let k = 0; k < 26; k++) {
    const a = r() * 6.28, rad = 4.5 + r() * 5;
    const x = cx + 0.5 + Math.cos(a) * rad, z = cz + 0.5 + Math.sin(a) * rad;
    if (Math.abs(x - 0.5) < 2.2 && z > -67) continue;
    const gy = w.top(Math.floor(x), Math.floor(z)) + 1;
    w.extra.glowShrooms.push(new THREE.Vector3(x, gy, z));
  }
}

export function generate() {
  const w = new World(); const r = mulberry(777);
  // terrain
  for (let x = X0; x < X1; x++) for (let z = Z0; z < Z1; z++) {
    const h = terrainH(x, z);
    for (let y = Y0; y <= h; y++) w.set(x, y, z, y === h ? B.GRASS : B.DIRT);
    if (z > -48 && z < -3 && Math.abs(x + 0.5 - pathX(z)) < 1.5) w.set(x, h, z, B.PATH);
  }
  // pond
  for (let x = -16; x <= -3; x++) for (let z = -62; z <= -48; z++) {
    const d = dist2(x + 0.5, z + 0.5, KEY.pond.x, KEY.pond.z) + (hash2(x, z) - 0.5) * 0.8;
    if (d < 3.7) { w.set(x, -1, z, B.WATER); w.set(x, -2, z, B.DIRT); }
  }
  // fallen log in clearing (north edge)
  for (let x = -8; x <= -3; x++) w.set(x, 0, -7, B.LOGX);
  // mossy stones
  const stones = [[5, 3], [-6, 4], [7, -18], [-6, -24], [6, -33], [-12, -50], [12, -62], [-14, -66], [9, -48], [-3, 9], [10, 8]];
  for (const [sx, sz] of stones) { const y = terrainH(sx, sz) + 1; w.set(sx, y, sz, B.STONE); if (r() < 0.6) w.set(sx + 1, y, sz, B.STONE); if (r() < 0.4) w.set(sx, y, sz + 1, B.STONE); if (r() < 0.3) w.set(sx, y + 1, sz, B.STONE); }

  giantTree(w, r);

  const forbid = (x, z) => {
    if (dist2(x, z, 0.5, 0.5) < 9.5) return true;
    if (z > -49 && z < -2 && Math.abs(x - pathX(z)) < 3.6) return true;
    if (dist2(x, z, 0.5, -60) < 21) return true;
    if (z > -40 && z < -33 && Math.abs(x) < 5) return true;
    // establishing camera corridor
    { const ax = 4, az = 9, bx = 10, bz = 18; const t = Math.max(0, Math.min(1, ((x - ax) * (bx - ax) + (z - az) * (bz - az)) / ((bx - ax) ** 2 + (bz - az) ** 2))); if (dist2(x, z, ax + t * (bx - ax), az + t * (bz - az)) < 5.5) return true; }
    // forest-run camera line (right of path)
    if (z > -36 && z < -10 && Math.abs(x - (pathX(z) + 5.8)) < 2.2) return true;
    return false;
  };
  // forced big oaks: left of path and around glade
  const forced = [];
  for (let z = -12; z > -40; z -= 7) forced.push(['big', Math.floor(pathX(z) - 6 - r() * 2), z]);
  for (let z = -15; z > -40; z -= 8) forced.push(['big', Math.floor(pathX(z) + 9 + r() * 2), z]);
  for (let a = 0; a < 6.28; a += 0.42) { const rad = 23 + r() * 3; const x = Math.floor(0.5 + Math.cos(a) * rad), z = Math.floor(-60 + Math.sin(a) * rad); if (z > -42 && Math.abs(x) < 10) continue; forced.push(['big', x, z]); }
  forced.push(['big', -11, -3]); forced.push(['big', 10, -6]); forced.push(['big', -9, 9]); forced.push(['oak', 12, 3]); forced.push(['birch', -12, 5]);
  // thin birches between run-camera and path (foreground parallax)
  const place = (type, x, z) => {
    const y0 = terrainH(x, z) + 1;
    if (w.get(x, y0, z) !== B.AIR) return;
    if (type === 'big') bigOak(w, x, y0, z, r); else if (type === 'oak') oak(w, x, y0, z, r); else birch(w, x, y0, z, r);
  };
  for (const [t, x, z] of forced) place(t, x, z);
  for (let gx = X0 + 2; gx < X1 - 3; gx += 4.3) for (let gz = Z0 + 2; gz < Z1 - 3; gz += 4.3) {
    const x = Math.floor(gx + r() * 3), z = Math.floor(gz + r() * 3);
    if (forbid(x, z)) continue;
    const q = r(); place(q < 0.25 ? 'big' : q < 0.62 ? 'oak' : 'birch', x, z);
  }
  // ridge bushes (hide the glade until the reveal)
  for (let x = -12; x <= 12; x++) for (let z = -42; z <= -39; z++) {
    if (Math.abs(x + 0.5 - pathX(z)) < 1.6) continue;
    const y = terrainH(x, z) + 1; if (w.get(x, y, z) !== B.AIR) continue;
    const hgt = Math.abs(x) < 4 ? 2 : 1 + (hash2(x, z) < 0.5 ? 1 : 0);
    for (let k = 0; k < hgt; k++) w.set(x, y + k, z, B.LEAF);
  }
  // clearing mushrooms
  const mpos = [[-0.5, -3.3, 1], [0.15, -3.85, 0.85], [-1.05, -3.9, 0.9], [0.85, -2.85, 1.05], [-2.6, 2.9, 1], [-3.1, 2.4, 0.8], [4.2, 1.5, 1.2], [-4.5, -2.5, 0.9], [5.5, -3.8, 0.9], [2.8, 1.6, 0.9]];
  for (const [mx, mz, s] of mpos) w.extra.mushrooms.push({ x: mx, z: mz, s, red: true });
  for (let k = 0; k < 18; k++) { const a = r() * 6.28, rad = 12 + r() * 30; const x = Math.cos(a) * rad, z = -20 + Math.sin(a) * rad * 1.4; if (forbid(x, z) && dist2(x, z, 0.5, 0.5) < 9.5) continue; w.extra.mushrooms.push({ x, z, s: 0.8 + r() * 0.5, red: r() < 0.5 }); }
  return w;
}

// ------------------------------------------------------------ meshing
const FACES = [
  { n: [1, 0, 0], c: [[1, 0, 1], [1, 0, 0], [1, 1, 0], [1, 1, 1]] },
  { n: [-1, 0, 0], c: [[0, 0, 0], [0, 0, 1], [0, 1, 1], [0, 1, 0]] },
  { n: [0, 1, 0], c: [[0, 1, 1], [1, 1, 1], [1, 1, 0], [0, 1, 0]] },
  { n: [0, -1, 0], c: [[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]] },
  { n: [0, 0, 1], c: [[0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]] },
  { n: [0, 0, -1], c: [[1, 0, 0], [0, 0, 0], [0, 1, 0], [1, 1, 0]] },
];
const UVS = [[0, 0], [1, 0], [1, 1], [0, 1]];

function faceMat(t, f) {
  switch (t) {
    case B.GRASS: return f === 2 ? 'grassTop' : f === 3 ? 'dirt' : 'grassSide';
    case B.DIRT: return 'dirt';
    case B.PATH: return f === 2 ? 'pathTop' : f === 3 ? 'dirt' : 'pathSide';
    case B.LOG: return f === 2 || f === 3 ? 'logTop' : 'logSide';
    case B.LOGX: return f === 0 || f === 1 ? 'logTop' : 'logSideR';
    case B.BIRCH: return f === 2 || f === 3 ? 'logTop' : 'birchSide';
    case B.LEAF: return 'leavesOak';
    case B.LEAFB: return 'leavesBirch';
    case B.LEAFG: return 'leavesGiant';
    case B.STONE: return 'mossyStone';
    case B.WATER: return 'water';
    case B.GLOG: return f === 2 || f === 3 ? 'logTop' : 'giantBark';
    case B.MOSS: return 'moss';
  }
  return 'dirt';
}
const AO = [0.42, 0.62, 0.8, 1.0];

export function buildMeshes(w, scene) {
  const tex = blockTextures();
  const T = {}; for (const k in tex) T[k] = toTex(tex[k], { nearestMip: k.startsWith('leaves') });
  const buckets = {};
  const bucket = (k) => buckets[k] || (buckets[k] = { pos: [], nor: [], uv: [], col: [], idx: [] });
  const CH = 16;
  const occ = (x, y, z) => { const t = w.get(x, y, z); return OPAQUE.has(t) || LEAVES.has(t) ? 1 : 0; };
  for (let x = X0; x < X1; x++) for (let y = Y0; y < Y1; y++) for (let z = Z0; z < Z1; z++) {
    const t = w.d[((x - X0) * NY + (y - Y0)) * NZ + (z - Z0)]; if (t === B.AIR) continue;
    const jitter = 0.92 + hash3(x, y, z) * 0.1;
    for (let f = 0; f < 6; f++) {
      const F = FACES[f]; const nx = x + F.n[0], ny = y + F.n[1], nz = z + F.n[2];
      const nt = w.get(nx, ny, nz);
      if (t === B.WATER) { if (f !== 2 || nt !== B.AIR) continue; }
      else if (LEAVES.has(t)) { if (OPAQUE.has(nt) || nt === t) continue; }
      else { if (OPAQUE.has(nt)) continue; if (f === 3 && y <= Y0) continue; }
      let key = faceMat(t, f); let rot = false;
      if (key === 'logSideR') { key = 'logSide'; rot = true; }
      const bk = bucket(key + '|' + Math.floor((x - X0) / CH) + '_' + Math.floor((z - Z0) / CH)); const base = bk.pos.length / 3;
      const ax = f < 2 ? 0 : f < 4 ? 1 : 2; const t1 = ax === 0 ? 1 : 0, t2 = ax === 2 ? 1 : 2;
      const aos = [];
      for (let i = 0; i < 4; i++) {
        const c = F.c[i];
        let py = y + c[1]; if (t === B.WATER && c[1] === 1) py = y + 0.86;
        bk.pos.push(x + c[0], py, z + c[2]); bk.nor.push(F.n[0], F.n[1], F.n[2]);
        const uvv = rot ? [UVS[i][1], 1 - UVS[i][0]] : UVS[i]; bk.uv.push(uvv[0], uvv[1]);
        const o = [nx, ny, nz]; const s1 = [...o], s2 = [...o], cc = [...o];
        const d1 = c[t1] ? 1 : -1, d2 = c[t2] ? 1 : -1;
        s1[t1] += d1; s2[t2] += d2; cc[t1] += d1; cc[t2] += d2;
        const a = occ(...s1), b = occ(...s2), co = occ(...cc);
        const lvl = (a && b) ? 0 : 3 - (a + b + co); aos.push(lvl);
        const br = (t === B.WATER ? 1 : AO[lvl]) * jitter; bk.col.push(br, br, br);
      }
      if (aos[0] + aos[2] < aos[1] + aos[3]) bk.idx.push(base + 1, base + 2, base + 3, base + 1, base + 3, base);
      else bk.idx.push(base, base + 1, base + 2, base, base + 2, base + 3);
    }
  }
  const mats = {};
  const group = new THREE.Group();
  for (const kk in buckets) {
    const k = kk.split('|')[0];
    const bk = buckets[kk]; const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(bk.pos, 3));
    g.setAttribute('normal', new THREE.Float32BufferAttribute(bk.nor, 3));
    g.setAttribute('uv', new THREE.Float32BufferAttribute(bk.uv, 2));
    g.setAttribute('color', new THREE.Float32BufferAttribute(bk.col, 3));
    g.setIndex(bk.idx); g.computeBoundingSphere();
    let m = mats[k];
    if (m) {} else if (k === 'water') m = new THREE.MeshStandardMaterial({ map: T[k], vertexColors: true, transparent: true, opacity: 0.82, roughness: 0.08, metalness: 0.0, color: 0xbfe8ff });
    else if (k.startsWith('leaves')) m = new THREE.MeshLambertMaterial({ map: T[k], vertexColors: true, alphaTest: 0.5, side: THREE.DoubleSide });
    else m = new THREE.MeshLambertMaterial({ map: T[k], vertexColors: true });
    mats[k] = m;
    const mesh = new THREE.Mesh(g, m); mesh.castShadow = k !== 'water'; mesh.receiveShadow = true; mesh.name = k;
    group.add(mesh);
  }
  scene.add(group);
  return { group, mats, tex: T };
}

// ------------------------------------------------------------ plants
const EXCL = [[4.6, -55.2, 1.6], [4.0, -55.9, 1.2], [-0.6, -6.0, 1.3], [-0.3, -8.0, 1.2], [0.0, -9.8, 1.2], [-1.2, -5.0, 1.0], [-0.2, -4.0, 1.4], [-0.9, -5.6, 1.0], [-1.4, -7.3, 0.8], [-1.0, -6.6, 0.9], [-0.6, -4.6, 1.4], [0.8, -6.0, 1.0], [-0.1, -58.6, 1.2], [-0.6, -57.5, 0.9], [1.7, -57.3, 0.9], [0.5, -64.4, 1.0]];
export function buildPlants(w, scene, windUniform) {
  const PT = plantTextures(); const T = {}; for (const k in PT) T[k] = toTex(PT[k], { nearestMip: true, repeat: false });
  const r = mulberry(4242);
  const lists = {};
  const add = (k, x, y, z, s) => { const kk = k + '|' + Math.floor((x - X0) / 16) + '_' + Math.floor((z - Z0) / 16); (lists[kk] || (lists[kk] = [])).push([x, y, z, s, r() * 3.14]); };
  const pmats = {};
  for (let x = X0 + 1; x < X1 - 1; x++) for (let z = Z0 + 1; z < Z1 - 1; z++) {
    const y = w.groundTop(x, z); if (y < -2) continue;
    const t = w.get(x, y, z); if (t !== B.GRASS) continue;
    if (w.get(x, y + 1, z) !== B.AIR) continue;
    const cx = x + 0.5 + (r() - 0.5) * 0.5, cz = z + 0.5 + (r() - 0.5) * 0.5, cy = y + 1;
    const dA = dist2(cx, cz, 0.5, 0.5), dB = dist2(cx, cz, 0.5, -60), dT = dist2(cx, cz, 0.5, -69.5);
    const q = r(); const s = 0.75 + r() * 0.45;
    // keep spots near characters clear
    if (dist2(cx, cz, -1, 1) < 1.3 || dist2(cx, cz, 1.4, -2.0) < 1.3) continue;
    let ex = false; for (const [ex0, ez0, er] of EXCL) if (dist2(cx, cz, ex0, ez0) < er) { ex = true; break; } if (ex) continue;
    if (dB < 19) {
      if (dT < 6.5) { if (q < 0.15) add('glowFlower', cx, cy, cz, s); continue; }
      if (Math.abs(cx - 0.5) < 2 && cz > -66 && cz < -50) { if (q < 0.1) add('tallGrass', cx, cy, cz, s * 0.8); continue; }
      if (q < 0.07 && dT < 14) add('glowFlower', cx, cy, cz, s);
      else if (q < 0.28) add(pick(r, ['dandelion', 'daisy', 'poppy', 'cornflower', 'pinkTulip', 'daisy']), cx, cy, cz, s);
      else if (q < 0.52) add('tallGrass', cx, cy, cz, s);
    } else if (dA < 8.5) {
      if (q < 0.12) add(pick(r, ['daisy', 'poppy', 'dandelion', 'cornflower']), cx, cy, cz, s);
      else if (q < 0.4) add('tallGrass', cx, cy, cz, s);
      else if (q < 0.45) add('fern', cx, cy, cz, s);
    } else {
      if (q < 0.34) add('tallGrass', cx, cy, cz, s);
      else if (q < 0.46) add('fern', cx, cy, cz, s * 1.1);
      else if (q < 0.5) add(pick(r, ['poppy', 'dandelion', 'cornflower', 'daisy']), cx, cy, cz, s);
      else if (q < 0.52) add('bush', cx, cy, cz, s * 1.2);
    }
  }
  // extra ferns around the fallen log
  for (let k = 0; k < 14; k++) add('fern', -8.5 + r() * 5.3, 0, -5.8 - r() * 3.0, 0.9 + r() * 0.4);
  for (let k = 0; k < 8; k++) add('tallGrass', -7 + r() * 3.5, 0, -8.3 - r() * 0.8, 0.8 + r() * 0.3);
  const group = new THREE.Group();
  for (const kk in lists) {
    const k = kk.split('|')[0];
    const L = lists[kk]; const pos = [], uv = [], nor = [], idx = [];
    for (const [x, y, z, s, a] of L) {
      for (let p = 0; p < 2; p++) {
        const ang = a + p * Math.PI / 2; const dx = Math.cos(ang) * 0.5 * s, dz = Math.sin(ang) * 0.5 * s; const h = s;
        const b = pos.length / 3;
        pos.push(x - dx, y, z - dz, x + dx, y, z + dz, x + dx, y + h, z + dz, x - dx, y + h, z - dz);
        uv.push(0, 0, 1, 0, 1, 1, 0, 1); for (let i = 0; i < 4; i++) nor.push(0, 1, 0);
        idx.push(b, b + 1, b + 2, b, b + 2, b + 3);
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2)); g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3)); g.setIndex(idx); g.computeBoundingSphere();
    let m = pmats[k];
    if (!m) {
    if (k === 'glowFlower') { m = new THREE.MeshBasicMaterial({ map: T[k], alphaTest: 0.5, side: THREE.DoubleSide }); m.color.setRGB(2.2, 2.8, 3.0); }
    else m = new THREE.MeshLambertMaterial({ map: T[k], alphaTest: 0.5, side: THREE.DoubleSide });
    m.onBeforeCompile = (sh) => {
      sh.uniforms.uWind = windUniform;
      sh.vertexShader = 'uniform float uWind;\n' + sh.vertexShader.replace('#include <begin_vertex>', `#include <begin_vertex>
        float sw = uv.y * uv.y;
        transformed.x += sin(uWind * 1.6 + position.x * 0.8 + position.z * 0.45) * 0.07 * sw;
        transformed.z += cos(uWind * 1.3 + position.x * 0.5 + position.z * 0.7) * 0.05 * sw;`);
    };
    pmats[k] = m; }
    const mesh = new THREE.Mesh(g, m); mesh.castShadow = k !== 'glowFlower'; mesh.receiveShadow = true; group.add(mesh);
  }
  scene.add(group);
  return group;
}

// ------------------------------------------------------------ props (mushrooms, lanterns)
export function buildProps(w, scene) {
  const MT = miscTextures(); const T = {}; for (const k in MT) T[k] = toTex(MT[k]);
  const PX = 1 / 16;
  const capRed = new THREE.MeshLambertMaterial({ map: T.capRed }), capBrown = new THREE.MeshLambertMaterial({ map: T.capBrown }), stem = new THREE.MeshLambertMaterial({ map: T.stem });
  const capGlow = new THREE.MeshBasicMaterial({ map: T.capGlow }); capGlow.color.setRGB(2.0, 2.6, 2.8);
  const group = new THREE.Group();
  const mush = (x, y, z, s, capMat) => {
    const g = new THREE.Group();
    const st = new THREE.Mesh(new THREE.BoxGeometry(2 * PX, 4 * PX, 2 * PX), stem); st.position.y = 2 * PX; g.add(st);
    const cp = new THREE.Mesh(new THREE.BoxGeometry(6 * PX, 2.5 * PX, 6 * PX), capMat); cp.position.y = 5 * PX; g.add(cp);
    const cp2 = new THREE.Mesh(new THREE.BoxGeometry(4 * PX, 1.2 * PX, 4 * PX), capMat); cp2.position.y = 6.8 * PX; g.add(cp2);
    g.position.set(x, y, z); g.scale.setScalar(s * 1.05); g.rotation.y = hash2(x * 10, z * 10) * 3;
    g.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
    group.add(g); return g;
  };
  for (const m of w.extra.mushrooms) { const y = w.groundTop(Math.floor(m.x), Math.floor(m.z)) + 1; mush(m.x, y, m.z, m.s, m.red ? capRed : capBrown); }
  for (const p of w.extra.glowShrooms) mush(p.x, p.y, p.z, 0.8 + hash2(p.x * 3, p.z * 3) * 0.7, capGlow);
  // lanterns
  const lanMat = new THREE.MeshBasicMaterial({ map: T.lantern }); lanMat.color.setRGB(3.2, 2.6, 1.7);
  const vineMat = new THREE.MeshLambertMaterial({ color: 0x3c7a2a });
  for (const p of w.extra.lanterns) {
    const l = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.5, 0.42), lanMat); l.position.copy(p); group.add(l);
    const v = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.8, 0.06), vineMat); v.position.set(p.x, p.y + 0.62, p.z); group.add(v);
  }
  scene.add(group);
  return { group, T, mush, mats: { capRed, stem } };
}
