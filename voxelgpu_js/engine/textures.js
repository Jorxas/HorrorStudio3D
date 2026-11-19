import * as THREE from 'three';

export function mulberry(seed) {
  return function () {
    seed |= 0; seed = seed + 0x6D2B79F5 | 0;
    let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}
export const C = (h) => [(h >> 16) & 255, (h >> 8) & 255, h & 255];
export const pick = (r, arr) => arr[Math.floor(r() * arr.length) % arr.length];

export function painter(w, h) {
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  const ctx = c.getContext('2d'); const img = ctx.createImageData(w, h);
  return {
    c, w, h,
    set(x, y, col, a = 255) {
      x = Math.round(x); y = Math.round(y);
      if (x < 0 || y < 0 || x >= w || y >= h) return;
      const i = (y * w + x) * 4; const cc = typeof col === 'number' ? C(col) : col;
      img.data[i] = cc[0]; img.data[i + 1] = cc[1]; img.data[i + 2] = cc[2]; img.data[i + 3] = a;
    },
    fill(x0, y0, rw, rh, fn) { for (let y = 0; y < rh; y++) for (let x = 0; x < rw; x++) { const v = fn(x, y); if (v === null || v === undefined) continue; if (Array.isArray(v) && v.length === 2) this.set(x0 + x, y0 + y, v[0], v[1]); else this.set(x0 + x, y0 + y, v); } },
    clear(col = 0x000000) { const cc = C(col); for (let i = 0; i < w * h; i++) { img.data[i * 4] = cc[0]; img.data[i * 4 + 1] = cc[1]; img.data[i * 4 + 2] = cc[2]; img.data[i * 4 + 3] = 0; } },
    done() { ctx.putImageData(img, 0, 0); return c; }
  };
}

export function toTex(canvas, { mip = true, srgb = true, repeat = true, nearestMip = false } = {}) {
  const t = new THREE.CanvasTexture(canvas);
  t.magFilter = THREE.NearestFilter;
  t.minFilter = mip ? (nearestMip ? THREE.NearestMipmapNearestFilter : THREE.NearestMipmapLinearFilter) : THREE.NearestFilter;
  t.generateMipmaps = mip;
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  if (repeat) { t.wrapS = t.wrapT = THREE.RepeatWrapping; }
  t.anisotropy = 8;
  t.needsUpdate = true;
  return t;
}

function tile(seed, fn, size = 16) { const p = painter(size, size); const r = mulberry(seed); fn(p, r, size); return p.done(); }

const G = [0x58a63a, 0x4e9a33, 0x62b142, 0x6cbb48, 0x46902e, 0x5aab3c];
const G2 = [0x4f9a2f, 0x5fae38, 0x6fc044, 0x3f8526, 0x7ccc50];
const D = [0x79553a, 0x6b4a31, 0x8a6243, 0x5f412a, 0x94704f, 0x7d5a3d];
const P = [0xa48455, 0x9a7a4c, 0xb0905f, 0x8c6c42, 0xa98a5a];
const BARK = [0x5a4126, 0x684b2c, 0x4c361f, 0x765734];

export function blockTextures() {
  const T = {};
  T.grassTop = tile(11, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { let c = pick(r, G); if (r() < 0.06) c = 0x7cca52; if (r() < 0.03) c = 0x3c7f27; p.set(x, y, c); } });
  T.dirt = tile(12, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { let c = pick(r, D); if (r() < 0.04) c = 0x9a9a90; p.set(x, y, c); } });
  T.grassSide = tile(13, (p, r) => {
    for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) p.set(x, y, pick(r, D));
    for (let x = 0; x < 16; x++) { const d = 3 + (r() < 0.5 ? 1 : 0) + (r() < 0.25 ? 1 : 0); for (let y = 0; y < d; y++) p.set(x, y, pick(r, G)); }
  });
  T.pathTop = tile(14, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { let c = pick(r, P); if (r() < 0.05) c = 0x7d6038; p.set(x, y, c); } });
  T.pathSide = tile(15, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) p.set(x, y, y < 2 ? pick(r, P) : pick(r, D)); });
  T.logSide = tile(16, (p, r) => {
    const col = []; for (let x = 0; x < 16; x++) col.push(pick(r, BARK));
    for (let x = 0; x < 16; x++) for (let y = 0; y < 16; y++) { let c = col[x]; if (r() < 0.12) c = 0x3f2c18; if (r() < 0.08) c = 0x82633d; p.set(x, y, c); }
  });
  T.logTop = tile(17, (p, r) => {
    for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) {
      const d = Math.max(Math.abs(x - 7.5), Math.abs(y - 7.5)); let c;
      if (d > 6.6) c = pick(r, BARK); else c = (Math.floor(d) % 2 ? 0xa8824f : 0x94703f);
      if (r() < 0.08) c = 0x8a6838; p.set(x, y, c);
    }
  });
  T.birchSide = tile(18, (p, r) => {
    const W = [0xe8e4d8, 0xd8d4c6, 0xf2efe6, 0xdedad0];
    for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) p.set(x, y, pick(r, W));
    for (let k = 0; k < 7; k++) { const y = Math.floor(r() * 16), x = Math.floor(r() * 14), l = 1 + Math.floor(r() * 3); for (let i = 0; i < l; i++) p.set(x + i, y, r() < 0.6 ? 0x2b2b2b : 0x55554f); }
  });
  T.giantBark = tile(19, (p, r) => {
    const B2 = [0x4a3520, 0x3d2b19, 0x56402a, 0x5f4830];
    const col = []; for (let x = 0; x < 16; x++) col.push(pick(r, B2));
    for (let x = 0; x < 16; x++) for (let y = 0; y < 16; y++) {
      let c = col[x]; if (r() < 0.14) c = 0x2e2012; if (r() < 0.07) c = 0x6e5636;
      if (r() < 0.10) c = pick(r, [0x4f8a33, 0x5f9a3c, 0x3f7a2a]);
      p.set(x, y, c);
    }
  });
  const leaf = (seed, pal, holes = 0.2, extra = null) => tile(seed, (p, r) => {
    for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) {
      let c = pick(r, pal);
      if (extra && r() < extra.p) c = pick(r, extra.cols);
      if (r() < holes) p.set(x, y, c, 0); else p.set(x, y, c);
    }
  });
  T.leavesOak = leaf(20, [0x3e8f2c, 0x4ba336, 0x347d25, 0x5bb342, 0x2c6e1f, 0x46992f]);
  T.leavesBirch = leaf(21, [0x6fae3c, 0x80bd47, 0x5f9c33, 0x8fca55, 0x76b540]);
  T.leavesGiant = leaf(22, [0x3f9a46, 0x4fb354, 0x2f8040, 0x5cc062, 0x46a64c], 0.16, { p: 0.07, cols: [0xffd6ef, 0xffb3dc, 0xfff2a8, 0xffffff] });
  T.mossyStone = tile(23, (p, r) => {
    const S = [0x7d7d78, 0x6c6c68, 0x8c8c86, 0x5e5e5a];
    for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) {
      let c = pick(r, S);
      const m = Math.sin(x * 0.7 + 1.3) + Math.cos(y * 0.6 + x * 0.2) + r() * 0.8;
      if (m > 1.1) c = pick(r, [0x4f8a33, 0x5f9a3c, 0x447a2c]);
      p.set(x, y, c);
    }
  });
  T.water = tile(24, (p, r) => {
    for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { let c = pick(r, [0x2f8fd0, 0x3a9ade, 0x2a80c0, 0x3494d6]); if ((x + y * 3) % 11 === 0 && r() < 0.6) c = 0x7fd0f5; p.set(x, y, c); }
  });
  T.moss = tile(25, (p, r) => {
    for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { let c = pick(r, [0x5aa83a, 0x4c9a30, 0x6bb847, 0x3f8a28, 0x7cc455, 0x56a43a]); p.set(x, y, c); }
  });
  T.mossDark = tile(26, (p, r) => {
    for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) p.set(x, y, pick(r, [0x3f7f2a, 0x356f24, 0x4a8c31]));
  });
  return T;
}

// ---------- plant sprites (16x16, alpha) -----------
export function plantTextures() {
  const T = {};
  T.tallGrass = tile(40, (p, r) => {
    p.clear(0x4f9a2f);
    for (let b = 0; b < 10; b++) {
      const x = 1 + Math.floor(r() * 14); const h = 5 + Math.floor(r() * 10); const lean = (r() - 0.5) * 0.6; const c = pick(r, G2);
      for (let i = 0; i < h; i++) p.set(x + lean * i, 15 - i, i > h - 3 ? 0x86d25a : c);
    }
  });
  T.fern = tile(41, (p, r) => {
    p.clear(0x3f8526);
    const fronds = [[7, -0.35], [8, 0.35], [7.5, 0]];
    for (const [x0, lean] of fronds) {
      const h = 12 + Math.floor(r() * 3);
      for (let i = 0; i < h; i++) {
        const x = x0 + lean * i; const y = 15 - i; p.set(x, y, 0x3a7d24);
        if (i > 2 && i % 2 === 0) { const L = Math.max(1, Math.floor((h - i) / 3)); for (let k = 1; k <= L; k++) { p.set(x - k, y + (k > 1 ? 1 : 0), pick(r, [0x4f9a2f, 0x5cab38])); p.set(x + k, y + (k > 1 ? 1 : 0), pick(r, [0x4f9a2f, 0x5cab38])); } }
      }
    }
  });
  const flower = (seed, petal, center, petalAlt) => tile(seed, (p, r) => {
    p.clear(0x3f8526);
    for (let y = 8; y < 16; y++) p.set(7, y, 0x3f8a28);
    p.set(6, 12, 0x4f9a2f); p.set(5, 11, 0x4f9a2f); p.set(8, 13, 0x4f9a2f); p.set(9, 12, 0x4f9a2f);
    const pts = [[6, 5], [7, 4], [8, 5], [7, 6], [6, 6], [8, 6], [6, 7], [8, 7], [7, 7], [5, 6], [9, 6], [7, 5]];
    for (const [x, y] of pts) p.set(x, y, r() < 0.3 ? petalAlt : petal);
    p.set(7, 6, center);
  });
  T.poppy = flower(42, 0xe8302a, 0x2a1a10, 0xc41f1a);
  T.dandelion = flower(43, 0xf7d530, 0xe0a51a, 0xffe96a);
  T.cornflower = flower(44, 0x4f7cf0, 0x1e2f80, 0x6f97ff);
  T.daisy = flower(45, 0xf4f4f0, 0xf2c230, 0xdcdcd8);
  T.pinkTulip = flower(46, 0xf59ac8, 0x6a8a30, 0xe07ab0);
  T.glowFlower = tile(47, (p, r) => {
    p.clear(0x3f8526);
    for (let y = 7; y < 16; y++) p.set(7, y, 0x3f8a28);
    p.set(6, 12, 0x4f9a2f); p.set(8, 11, 0x4f9a2f); p.set(5, 13, 0x4f9a2f);
    const pts = [[6, 3], [7, 2], [8, 3], [5, 4], [6, 4], [7, 4], [8, 4], [9, 4], [6, 5], [7, 5], [8, 5], [7, 6]];
    for (const [x, y] of pts) p.set(x, y, r() < 0.4 ? 0xbffcff : 0x7ff0ff);
    p.set(7, 4, 0xffffff); p.set(7, 3, 0xffffff);
  });
  T.bush = tile(48, (p, r) => {
    p.clear(0x3e8f2c);
    for (let y = 3; y < 16; y++) for (let x = 0; x < 16; x++) { const dx = (x - 7.5) / 8, dy = (y - 11) / 8; if (dx * dx + dy * dy < 0.9 + r() * 0.2 && r() > 0.12) p.set(x, y, pick(r, [0x3e8f2c, 0x4ba336, 0x347d25, 0x5bb342])); }
  });
  return T;
}

// ---------- misc model textures -----------
export function miscTextures() {
  const T = {};
  T.capRed = tile(60, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) p.set(x, y, pick(r, [0xd8352a, 0xc42b22, 0xe5463a])); for (let k = 0; k < 7; k++) { const x = Math.floor(r() * 14), y = Math.floor(r() * 14); p.set(x, y, 0xf6f0e6); p.set(x + 1, y, 0xf6f0e6); p.set(x, y + 1, 0xe8e0d4); } });
  T.capBrown = tile(61, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) p.set(x, y, pick(r, [0x9a6a44, 0x8a5c3a, 0xa8784e])); });
  T.stem = tile(62, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) p.set(x, y, pick(r, [0xefe6d2, 0xe2d8c0, 0xf6efdf])); });
  T.capGlow = tile(63, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) p.set(x, y, pick(r, [0x6fe8ff, 0x9af2ff, 0x52d6f2])); for (let k = 0; k < 5; k++) p.set(Math.floor(r() * 16), Math.floor(r() * 16), 0xffffff); });
  T.wicker = tile(64, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { const a = ((x + (y >> 1)) % 4 < 2) !== ((y % 4) < 2); p.set(x, y, a ? pick(r, [0xb8843f, 0xc8954c]) : pick(r, [0x8c6230, 0x7a542a])); } });
  T.lantern = tile(65, (p, r) => {
    for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) {
      const edge = x < 2 || x > 13 || y < 2 || y > 13 || x === 7 || x === 8;
      p.set(x, y, edge ? pick(r, [0x3a3530, 0x2a2622]) : pick(r, [0xffe9a8, 0xffd27a, 0xfff4cc]));
    }
  });
  T.leafSprout = tile(66, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) p.set(x, y, pick(r, [0x6fc449, 0x7fd257, 0x5cb53c])); });
  return T;
}
