// Procedural pixel-art textures for the town (16 px per block) + pixel signs and posters.
import * as THREE from 'three';
import { painter, mulberry, pick, toTex, C } from './textures.js';

function tile(seed, fn, w = 16, h = 16) { const p = painter(w, h); const r = mulberry(seed); fn(p, r, w, h); return p.done(); }
const shade = (hex, f) => { const c = C(hex); return [Math.min(255, c[0] * f) | 0, Math.min(255, c[1] * f) | 0, Math.min(255, c[2] * f) | 0]; };
const noiseFill = (p, r, cols, w = 16, h = 16) => { for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) p.set(x, y, pick(r, cols)); };

export function townCanvases() {
  const T = {};
  // ground
  T.grassTop = tile(11, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { let c = pick(r, [0x5ca83c, 0x52a035, 0x66b345, 0x6fbd4b, 0x4c962f]); if (r() < 0.05) c = 0x7fcf55; p.set(x, y, c); } });
  T.grassSide = tile(13, (p, r) => { noiseFill(p, r, [0x79553a, 0x6b4a31, 0x8a6243, 0x5f412a]); for (let x = 0; x < 16; x++) { const d = 3 + (r() < 0.5 ? 1 : 0); for (let y = 0; y < d; y++) p.set(x, y, pick(r, [0x5ca83c, 0x52a035, 0x66b345])); } });
  T.dirt = tile(12, (p, r) => noiseFill(p, r, [0x79553a, 0x6b4a31, 0x8a6243, 0x5f412a, 0x94704f]));
  T.asphalt = tile(30, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { let c = pick(r, [0x3b3e44, 0x35383e, 0x41444b, 0x30333a, 0x393c42]); if (r() < 0.04) c = 0x5a5d63; p.set(x, y, c); } });
  T.concrete = tile(31, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { let c = pick(r, [0xbdbdb6, 0xb4b4ad, 0xc4c4bd, 0xadada6]); if (x === 0 || y === 0) c = 0x96968f; p.set(x, y, c); } });
  T.cobble = tile(32, (p, r) => {
    const pts = []; for (let i = 0; i < 9; i++) pts.push([r() * 16, r() * 16, pick(r, [0x8a7a68, 0x9a8874, 0x7d6e5e, 0xa39079, 0x887565, 0x948472])]);
    for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) {
      let b1 = 1e9, b2 = 1e9, col = 0;
      for (const [px, py, c] of pts) for (const ox of [-16, 0, 16]) for (const oy of [-16, 0, 16]) { const d = (x - px - ox) ** 2 + (y - py - oy) ** 2; if (d < b1) { b2 = b1; b1 = d; col = c; } else if (d < b2) b2 = d; }
      const edge = Math.sqrt(b2) - Math.sqrt(b1) < 1.1;
      p.set(x, y, edge ? 0x4f453c : shade(col, 0.9 + r() * 0.2));
    }
  });
  T.stone = tile(33, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { let c = pick(r, [0x8c8c86, 0x7e7e78, 0x999993, 0x737370]); if (y % 8 === 0 || (x + (y >> 3) * 8) % 16 === 0) c = 0x5f5f5a; p.set(x, y, c); } });
  T.brick = tile(34, (p, r) => {
    for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) {
      const row = y >> 2; const off = (row % 2) * 4; const mort = y % 4 === 3 || (x + off) % 8 === 7;
      p.set(x, y, mort ? pick(r, [0xb9b0a3, 0xaaa294]) : pick(r, [0xb5402f, 0xa63a2b, 0xc04a36, 0x9c3426]));
    }
  });
  const siding = (seed, base) => tile(seed, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { const k = y % 4; const f = k === 0 ? 1.08 : k === 3 ? 0.82 : 0.97 + r() * 0.04; p.set(x, y, shade(base, f)); } });
  T.sidingWhite = siding(40, 0xe9e7e0); T.sidingRed = siding(41, 0xa8322c); T.sidingBlue = siding(42, 0x8b9bb0); T.sidingYellow = siding(43, 0xdcb54e); T.sidingBeige = siding(44, 0xd8c7a3); T.sidingGreen = siding(45, 0x8fb08a); T.sidingGrey = siding(46, 0xa9a9a6);
  const roof = (seed, base) => tile(seed, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { const row = y >> 2; const off = (row % 2) * 3; const k = y % 4; let f = k === 3 ? 0.7 : 0.92 + r() * 0.16; if ((x + off) % 6 === 0) f *= 0.8; p.set(x, y, shade(base, f)); } });
  T.roofGrey = roof(50, 0x4d5057); T.roofBrown = roof(51, 0x6b4a36); T.roofRed = roof(52, 0x7c2e28); T.roofDark = roof(53, 0x33353a);
  T.trim = tile(54, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) p.set(x, y, pick(r, [0xf2f0ea, 0xebe9e2, 0xf6f4ef])); });
  const windowTex = (seed, lit) => tile(seed, (p, r) => {
    for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) {
      const frame = x < 2 || x > 13 || y < 2 || y > 13 || x === 7 || x === 8 || y === 7;
      let c;
      if (frame) c = 0xf3f1ea;
      else if (lit) { const g = 1 - y / 22; c = shade(0xffd27a, 0.85 + g * 0.3 + r() * 0.05); }
      else { const g = (x + y) / 30; c = shade(0x3d5f86, 0.75 + g * 0.5); if (Math.abs(x - y) < 2 && x < 7) c = 0x9fc3e3; }
      p.set(x, y, c);
    }
  });
  T.window = windowTex(55, false); T.windowLit = windowTex(56, true);
  T.cut_glass = tile(97, (p) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { p.set(x, y, 0xbfdcf0, (x + 2 * y) % 13 === 0 ? 70 : 0); } });
  T.windowGlow = tile(57, (p) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { const frame = x < 2 || x > 13 || y < 2 || y > 13 || x === 7 || x === 8 || y === 7; p.set(x, y, frame ? 0x000000 : 0xffc870); } });
  T.door = tile(58, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { let c = pick(r, [0x6b3f24, 0x734429, 0x63391f]); if (x === 0 || x === 15) c = 0xf0eee8; if ((x === 3 || x === 12) && y > 2) c = 0x52301b; if (x === 12 && y === 9) c = 0xd8b84a; p.set(x, y, c); } });
  T.garage = tile(59, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { let c = y % 4 === 3 ? 0xc9c9c3 : pick(r, [0xf1f1ec, 0xeaeae4]); p.set(x, y, c); } });
  T.plank = tile(60, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { let c = pick(r, [0xa77a4c, 0x9c6f43, 0xb08454]); if (y % 4 === 0) c = 0x7c5631; p.set(x, y, c); } });
  T.marble = tile(61, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { let c = pick(r, [0xdedcd6, 0xe6e4de, 0xd4d2cc]); if (Math.abs(Math.sin(x * 0.6 + y * 0.35) - 0.3) < 0.08) c = 0xb9b6ae; p.set(x, y, c); } });
  T.column = tile(62, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { const fl = x % 4 === 0; p.set(x, y, fl ? 0xc9c6bc : pick(r, [0xefece4, 0xe7e4dc])); } });
  T.townhall = tile(63, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { let c = pick(r, [0xe3dccb, 0xdcd4c2, 0xe9e2d2]); if (y % 8 === 7) c = 0xc2b9a5; p.set(x, y, c); } });
  const paint = (seed, base) => tile(seed, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) p.set(x, y, shade(base, 0.94 + r() * 0.1)); });
  T.paintPink = paint(70, 0xe58aa6); T.paintTeal = paint(71, 0x4fb2a8); T.paintMint = paint(72, 0x8fd1a6); T.paintYellow = paint(73, 0xf0c94e); T.paintOrange = paint(74, 0xe98a3e); T.paintLavender = paint(75, 0xa58fd1); T.paintSky = paint(76, 0x6fb0e0); T.paintCream = paint(77, 0xece0bf); T.paintGreen = paint(78, 0x3f9c55);
  T.shopWindow = tile(79, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { let c; if (y > 13) c = 0x3b2c22; else { const g = (x + y * 0.5) / 24; c = shade(0x5d84a8, 0.8 + g * 0.5); if (Math.abs(x - y * 0.7) < 1.2) c = 0xbfd9ee; if (y > 9 && (x * 7 + y) % 5 === 0) c = pick(r, [0xe0573f, 0xf0c94e, 0x6fb35a, 0xd77ab0]); } p.set(x, y, c); } });
  T.shopWindowLit = tile(80, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { let c; if (y > 13) c = 0x3b2c22; else { c = shade(0xffd48a, 0.85 + r() * 0.15); if (y > 9 && (x * 7 + y) % 5 === 0) c = pick(r, [0xe0573f, 0xf0c94e, 0x6fb35a, 0xd77ab0]); } p.set(x, y, c); } });
  T.shopGlow = tile(81, (p) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) p.set(x, y, y > 13 ? 0x000000 : 0xffb860); });
  T.water = tile(24, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { let c = pick(r, [0x3a9ad6, 0x4aa6e0, 0x3590cc]); if ((x + y * 3) % 11 === 0) c = 0x8fd6f7; p.set(x, y, c); } });
  T.leavesOak = tile(20, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { const c = pick(r, [0x3e8f2c, 0x4ba336, 0x347d25, 0x5bb342, 0x2c6e1f]); p.set(x, y, c, r() < 0.15 ? 0 : 255); } });
  T.hedge = tile(21, (p, r) => noiseFill(p, r, [0x3a8a2a, 0x469a33, 0x2f7a22, 0x52a83a]));
  T.logSide = tile(16, (p, r) => { const col = []; for (let x = 0; x < 16; x++) col.push(pick(r, [0x5a4126, 0x684b2c, 0x4c361f])); for (let x = 0; x < 16; x++) for (let y = 0; y < 16; y++) p.set(x, y, r() < 0.12 ? 0x3f2c18 : col[x]); });
  T.logTop = tile(17, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { const d = Math.max(Math.abs(x - 7.5), Math.abs(y - 7.5)); p.set(x, y, d > 6.6 ? 0x5a4126 : (Math.floor(d) % 2 ? 0xa8824f : 0x94703f)); } });
  T.locker = tile(82, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { let c = shade(0x2f6fc0, 0.95 + r() * 0.08); if (x === 0 || x === 15) c = 0x1f4f90; if (y < 5 && y % 2 === 0 && x > 3 && x < 12) c = 0x1a4580; if (x === 12 && y > 7 && y < 11) c = 0xc8c8c8; p.set(x, y, c); } });
  T.ceiling = tile(83, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) p.set(x, y, (x === 0 || y === 0) ? 0xc8c8c2 : pick(r, [0xeeeeea, 0xe8e8e3])); });
  T.lightPanel = tile(84, (p) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) p.set(x, y, (x < 1 || y < 1 || x > 14 || y > 14) ? 0xb0b0aa : 0xffffff); });
  T.busYellow = paint(85, 0xf2b81f); T.busSeat = tile(86, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) p.set(x, y, shade(0x6a5a3a, 0.9 + r() * 0.15)); });
  T.black = paint(87, 0x121214); T.metal = paint(88, 0x6c7078); T.white = paint(89, 0xf4f4f0); T.red = paint(90, 0xd23a2e); T.darkWood = paint(91, 0x4a2f1c);
  // awnings: vertical stripes
  const awning = (seed, a, b) => tile(seed, (p, r) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) p.set(x, y, shade((x >> 2) % 2 ? a : b, 0.95 + r() * 0.08)); });
  T.awnRed = awning(92, 0xd8382e, 0xf4f0e8); T.awnGreen = awning(93, 0x2f9c55, 0xf4f0e8); T.awnBlue = awning(94, 0x3a6fc8, 0xf4f0e8); T.awnPink = awning(95, 0xe07aa6, 0xf4f0e8); T.awnYellow = awning(96, 0xf0b52e, 0xf4f0e8);
  return T;
}

// ---------------------------------------------------------------- road / sidewalk strips (drawn at 16 px per block)
export function roadCanvas(lenBlocks, widthBlocks, opts = {}) {
  const W = widthBlocks * 16, Hh = lenBlocks * 16; const p = painter(W, Hh); const r = mulberry(opts.seed || 5);
  for (let y = 0; y < Hh; y++) for (let x = 0; x < W; x++) { let c = pick(r, [0x3b3e44, 0x35383e, 0x41444b, 0x30333a]); if (r() < 0.03) c = 0x55585e; p.set(x, y, c); }
  const cx = W / 2;
  if (opts.center !== false) for (let y = 0; y < Hh; y++) { p.set(cx - 3, y, 0xf2c230); p.set(cx - 2, y, 0xf2c230); p.set(cx + 1, y, 0xf2c230); p.set(cx + 2, y, 0xf2c230); }
  if (opts.edges !== false) for (let y = 0; y < Hh; y++) { p.set(6, y, 0xe8e8e4); p.set(7, y, 0xe8e8e4); p.set(W - 7, y, 0xe8e8e4); p.set(W - 8, y, 0xe8e8e4); }
  if (opts.dashes) for (let y = 0; y < Hh; y++) if ((y % 64) < 32) for (const lx of opts.dashes) { p.set(lx * 16, y, 0xe8e8e4); p.set(lx * 16 + 1, y, 0xe8e8e4); }
  return p.done();
}
export function crosswalkCanvas(widthBlocks) {
  const W = widthBlocks * 16, Hh = 4 * 16; const p = painter(W, Hh);
  for (let y = 0; y < Hh; y++) for (let x = 0; x < W; x++) p.set(x, y, (x % 16) < 9 && y > 2 && y < Hh - 3 ? 0xeeeeea : 0x000000, (x % 16) < 9 && y > 2 && y < Hh - 3 ? 255 : 0);
  return p.done();
}
export function sidewalkCanvas(lenBlocks, widthBlocks, lanes = true) {
  const W = widthBlocks * 16, Hh = lenBlocks * 16; const p = painter(W, Hh); const r = mulberry(9);
  for (let y = 0; y < Hh; y++) for (let x = 0; x < W; x++) { let c = pick(r, [0xbdbdb6, 0xb4b4ad, 0xc4c4bd, 0xadada6]); if (y % 32 === 0) c = 0x8f8f88; p.set(x, y, c); }
  if (lanes) {
    for (let y = 0; y < Hh; y++) { p.set(W / 2 - 1, y, 0xf0c02a); p.set(W / 2, y, 0xf0c02a); p.set(3, y, 0xf0c02a); p.set(W - 4, y, 0xf0c02a); }
    for (let y = 0; y < Hh; y += 48) for (let x = 3; x < W - 3; x++) { p.set(x, y, 0xf0c02a); p.set(x, y + 1, 0xf0c02a); }
  }
  return p.done();
}

// ---------------------------------------------------------------- pixel signs
export function signCanvas(text, { bg = '#f4efe2', fg = '#7a2a1a', border = '#3a2a1a', h = 18, scale = 1, font = 'bold 13px "Inter Display", "DejaVu Sans", sans-serif' } = {}) {
  const tmp = document.createElement('canvas').getContext('2d'); tmp.font = font; const tw = Math.ceil(tmp.measureText(text).width);
  const c = document.createElement('canvas'); c.width = tw + 10; c.height = h; const g = c.getContext('2d');
  g.fillStyle = border; g.fillRect(0, 0, c.width, h); g.fillStyle = bg; g.fillRect(1, 1, c.width - 2, h - 2);
  g.font = font; g.fillStyle = fg; g.textBaseline = 'middle'; g.textAlign = 'center'; g.fillText(text, c.width / 2, h / 2 + 1);
  // hard-threshold alpha for pixel look
  const im = g.getImageData(0, 0, c.width, h); g.putImageData(im, 0, 0);
  return c;
}

export function weddingPoster() {
  const p = painter(32, 44);
  for (let y = 0; y < 44; y++) for (let x = 0; x < 32; x++) {
    let c = y < 14 ? 0xbcd9f0 : y < 24 ? 0xe8dcc0 : 0x6fb04e;
    if (y >= 14 && y < 24 && (x % 6 === 2) && y > 16 && y < 21) c = 0x8a6a4a;
    if (y >= 30 && y < 34 && x > 10 && x < 22) c = 0xc8c2b4;
    p.set(x, y, c);
  }
  for (let y = 0; y < 44; y++) { p.set(0, y, 0xf8f8f4); p.set(31, y, 0xf8f8f4); } for (let x = 0; x < 32; x++) { p.set(x, 0, 0xf8f8f4); p.set(x, 43, 0xf8f8f4); }
  const fig = (x0, body, hair, skin) => { for (let y = 18; y < 22; y++) for (let x = x0; x < x0 + 4; x++) p.set(x, y, skin); for (let x = x0; x < x0 + 4; x++) p.set(x, 18, hair); p.set(x0 - 1, 18, hair); p.set(x0 - 1, 19, hair); for (let y = 22; y < 36; y++) for (let x = x0 - 1; x < x0 + 5; x++) p.set(x, y, body); };
  fig(5, 0xf4f2ee, 0xd8441e, 0xf2c9a0); fig(24, 0x22242a, 0x6a3a1e, 0xe8b88e);
  for (let x = 9; x < 23; x++) p.set(x, 27 + Math.round(Math.sin((x - 9) / 13 * Math.PI) * 2), 0xffffff);
  return p.done();
}

export function makeTextures() {
  const C2 = townCanvases(); const T = {};
  for (const k in C2) T[k] = toTex(C2[k], { nearestMip: k.startsWith('leaves') });
  return { T, canvases: C2 };
}
