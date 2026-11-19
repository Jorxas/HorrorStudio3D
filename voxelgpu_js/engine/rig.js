// Parametric Minecraft-style characters: skins from a spec, rigged humanoids, accessories, shadow creature.
import * as THREE from 'three';
import { painter, toTex, mulberry, pick, C } from './textures.js';
import { label } from './i18n.js';

export const PX = 1 / 16;
export function boxUV(geo, w, h, d, u, v) {
  const R = { px: [u + d + w, v + d, d, h], nx: [u, v + d, d, h], py: [u + d, v, w, d], ny: [u + d + w, v, w, d], pz: [u + d, v + d, w, h], nz: [u + 2 * d + w, v + d, w, h] };
  const order = ['px', 'nx', 'py', 'ny', 'pz', 'nz']; const uv = geo.attributes.uv;
  for (let f = 0; f < 6; f++) { const [x0, y0, rw, rh] = R[order[f]]; for (let i = 0; i < 4; i++) { const k = f * 4 + i; const uu = uv.getX(k), vv = uv.getY(k); uv.setXY(k, (x0 + uu * rw) / 64, 1 - (y0 + (1 - vv) * rh) / 64); } }
  uv.needsUpdate = true; return geo;
}
export function partGeo(w, h, d, u, v, inflate = 0) { return boxUV(new THREE.BoxGeometry((w + inflate) * PX, (h + inflate) * PX, (d + inflate) * PX), w, h, d, u, v); }
function paintBox(p, u, v, w, h, d, F) {
  const rect = { front: [u + d, v + d, w, h], back: [u + 2 * d + w, v + d, w, h], right: [u, v + d, d, h], left: [u + d + w, v + d, d, h], top: [u + d, v, w, d], bottom: [u + d + w, v, w, d] };
  for (const k in rect) { const fn = F[k] || F.all; if (!fn) continue; const [x0, y0, rw, rh] = rect[k]; p.fill(x0, y0, rw, rh, (x, y) => fn(x, y, rw, rh, k)); }
}
const sh = (hex, f) => { const c = C(hex); return [Math.min(255, c[0] * f) | 0, Math.min(255, c[1] * f) | 0, Math.min(255, c[2] * f) | 0]; };

export const EXPRS = ['neutral', 'lookL', 'lookR', 'blink', 'happy', 'smile', 'surprised', 'scared', 'lookUp', 'hollow'];

function face(spec, expr) {
  const S = spec.skin, H = spec.hair, L = 0x1d1626, W = 0xffffff, I1 = sh(spec.eyes, 0.7), I2 = spec.eyes;
  const M = sh(S, 0.72), P = spec.female ? sh(S, 0.93) : S; const Md = sh(S, 0.86);
  const bald = spec.hairStyle === 'bald';
  const sideHair = ['long', 'bob', 'bun'].includes(spec.hairStyle);
  const side = sideHair ? H : S;
  const rows = [
    [H, H, H, H, H, H, H, H],
    bald ? [S, S, S, S, S, S, S, S] : [H, H, H, H, H, H, H, H],
    bald ? [S, S, S, S, S, S, S, S] : (spec.hairStyle === 'spiky' ? [H, S, H, S, S, H, S, H] : [side, H, S, S, H, S, S, side]),
    [side, L, L, S, S, L, L, side],
    [side, W, I1, S, S, I1, W, side],
    [side, I2, I2, S, S, I2, I2, side],
    [side, P, S, S, S, S, P, side],
    [sideHair ? H : S, S, S, M, M, S, S, sideHair ? H : S],
  ];
  if (spec.glasses) { rows[4][0] = rows[4][7] = 0x222222; rows[3][3] = rows[3][4] = 0x222222; }
  if (spec.beard) { rows[7] = [S, spec.beard, spec.beard, M, M, spec.beard, spec.beard, S]; rows[6][1] = rows[6][6] = spec.beard; }
  const E = (r3, r4, r5) => { for (const [i, row] of [[3, r3], [4, r4], [5, r5]]) { rows[i][1] = row[0]; rows[i][2] = row[1]; rows[i][5] = row[2]; rows[i][6] = row[3]; } };
  if (expr === 'lookL') E([L, L, L, L], [I1, W, I1, W], [I2, I2, I2, I2]);
  if (expr === 'lookR') E([L, L, L, L], [W, I1, W, I1], [I2, I2, I2, I2]);
  if (expr === 'blink') E([S, S, S, S], [S, S, S, S], [L, L, L, L]);
  if (expr === 'happy') { E([S, S, S, S], [L, L, L, L], [S, S, S, S]); rows[6][2] = Md; rows[6][5] = Md; }
  if (expr === 'smile') { rows[6][2] = Md; rows[6][5] = Md; }
  if (expr === 'surprised') { E([L, L, L, L], [W, I1, I1, W], [I2, I2, I2, I2]); rows[7][3] = rows[7][4] = 0x4a1e1e; }
  if (expr === 'scared') { E([W, W, W, W], [W, L, L, W], [W, W, W, W]); rows[7][3] = rows[7][4] = 0x3a1414; rows[6][3] = rows[6][4] = 0x3a1414; }
  if (expr === 'lookUp') E([W, I1, I1, W], [I2, I2, I2, I2], [S, S, S, S]);
  if (expr === 'hollow') { E([0x101014, 0x101014, 0x101014, 0x101014], [0xf4f4f0, 0xf4f4f0, 0xf4f4f0, 0xf4f4f0], [0xe8e8e4, 0xe8e8e4, 0xe8e8e4, 0xe8e8e4]); rows[7][3] = rows[7][4] = S; rows[6][1] = rows[6][6] = S; }
  return rows;
}

// spec: { skin, hair, hairStyle, eyes, shirt, shirt2, shirtStyle, sleeves, pants, shoes, female, sash, tie, glasses, beard }
export function paintSkin(spec, expr = 'neutral', seed = 1) {
  const p = painter(64, 64); p.clear(); const r = mulberry(seed);
  const n = (c, a = 0.06) => sh(c, 1 - a + r() * a * 2);
  const S = spec.skin, H = spec.hair, SH = spec.shirt, S2 = spec.shirt2 ?? 0xf2f2ee, PA = spec.pants, SO = spec.shoes ?? 0x2a2a2e;
  const F = face(spec, expr);
  const hs = spec.hairStyle || 'short';
  const hairAt = (x, y, sideF) => { if (hs === 'bald') return y < 1 ? n(H) : n(S, 0.03); if (['long', 'bob', 'bun'].includes(hs)) return n(H); return y < (sideF ? 3 : 6) ? n(H) : n(S, 0.03); };
  paintBox(p, 0, 0, 8, 8, 8, { front: (x, y) => F[y][x], top: () => (hs === 'bald' ? n(S) : n(H)), back: (x, y) => hairAt(x, y, false), left: (x, y) => hairAt(x, y, true), right: (x, y) => hairAt(x, y, true), bottom: () => sh(S, 0.85) });
  if (['long', 'bob', 'bun', 'curly'].includes(hs)) paintBox(p, 32, 0, 8, 8, 8, { top: () => n(H), back: () => n(H), left: (x, y) => (y < 7 || x > 1) ? n(H) : null, right: (x, y) => (y < 7 || x < 6) ? n(H) : null, front: (x, y) => (y < 2 || ((x === 0 || x === 7) && y < 6)) ? n(H) : null });
  if (hs === 'spiky' || hs === 'short') paintBox(p, 32, 0, 8, 8, 8, { top: () => n(H), front: (x, y) => (y < 1 || (y === 1 && x % 3 !== 1)) ? n(H) : null, back: (x, y) => y < 4 ? n(H) : null, left: (x, y) => y < 2 ? n(H) : null, right: (x, y) => y < 2 ? n(H) : null });
  // torso
  const st = spec.shirtStyle || 'tee';
  const torsoF = (x, y, w, h, face) => {
    if (st === 'stripes') return Math.floor(y / 2) % 2 ? n(S2) : n(SH);
    if (st === 'camo') { const v = Math.sin(x * 1.7 + y * 0.9 + (face === 'back' ? 3 : 0)) + Math.cos(y * 1.3 - x * 0.7); return v > 0.8 ? n(S2) : v < -0.6 ? n(sh(SH, 0.7)) : n(SH); }
    if (st === 'flannel') { const a = x % 4 === 0, b = y % 4 === 0; return a && b ? sh(SH, 0.45) : (a || b) ? sh(SH, 0.65) : n(SH); }
    if (st === 'suit') {
      if (face === 'front') {
        if (spec.sash && Math.abs((x) - (7 - y * 0.6)) < 0.9) return spec.sash;
        if (x >= 3 && x <= 4 && y < 6) return (x === 3 || x === 4) && y > 0 && spec.tie ? spec.tie : 0xf2f2ee;
        if ((x === 2 || x === 5) && y < 4) return 0xf2f2ee;
      }
      return n(SH, 0.04);
    }
    if (st === 'hoodie') { if (face === 'front' && y > 6 && y < 10 && x > 1 && x < 6) return sh(SH, 0.85); if (face === 'front' && y < 4 && (x === 3 || x === 4)) return 0xeeeeee; return n(SH); }
    if (st === 'jacket') { if (face === 'front' && x >= 3 && x <= 4) return n(S2); return n(SH); }
    if (st === 'vest') { if (Math.floor(y / 3) === 2) return 0xe8e8e0; return n(SH); }
    if (st === 'dress') return n(SH);
    if (face === 'front' && y === 0 && x >= 3 && x <= 4) return sh(S, 0.9);
    return n(SH);
  };
  paintBox(p, 16, 16, 8, 12, 4, { all: torsoF, top: () => n(SH), bottom: () => (st === 'dress' ? n(SH) : n(PA)) });
  const sleeveRows = spec.sleeves === 'short' ? 4 : 10;
  const armF = (x, y, w, h, face) => y < sleeveRows ? (st === 'stripes' ? (Math.floor(y / 2) % 2 ? n(S2) : n(SH)) : st === 'flannel' ? torsoF(x, y, w, h, face) : st === 'camo' ? torsoF(x + 3, y, w, h, face) : st === 'vest' ? n(spec.sleeve ?? 0xf0f0ea) : n(SH)) : n(S, 0.03);
  paintBox(p, 40, 16, 4, 12, 4, { all: armF, top: () => n(SH), bottom: () => n(S) }); paintBox(p, 32, 48, 4, 12, 4, { all: armF, top: () => n(SH), bottom: () => n(S) });
  const legF = (x, y) => { if (st === 'dress' && y < 6) return n(SH); if (st === 'dress') return y > 9 ? n(SO) : n(S, 0.03); return y < 10 ? n(PA) : (y === 10 ? n(SO) : sh(SO, 0.7)); };
  paintBox(p, 0, 16, 4, 12, 4, { all: legF, top: () => n(PA), bottom: () => n(SO) }); paintBox(p, 16, 48, 4, 12, 4, { all: legF, top: () => n(PA), bottom: () => n(SO) });
  return p.done();
}

export function randomSpec(r) {
  const skins = [0xf2c9a0, 0xe8b48f, 0xd9a27c, 0xb57b52, 0x8d5a3a, 0x6b4128, 0xf6d5b8];
  const hairs = [0x2b1d16, 0x3a271d, 0x6a3a1e, 0xb8862f, 0xd8b05a, 0x1a1a1a, 0x8a4a22, 0xc8642a, 0x9a9a9a];
  const cols = [0xd23a2e, 0x2f6fd0, 0x3fa04a, 0xf0c02e, 0x8a4ad0, 0xf07a2e, 0x2fb0b0, 0xe8e8e2, 0x222428, 0xd85a9a, 0x6a8a3a, 0x7a3a2a, 0x4a5a8a];
  const pants = [0x2f3f6a, 0x3a5a8c, 0x2a2a2e, 0x6a5a40, 0x8a8a84, 0x4a3a2a, 0x1f2f4a];
  const female = r() < 0.48;
  return {
    skin: pick(r, skins), hair: pick(r, hairs), hairStyle: female ? pick(r, ['long', 'bob', 'bun', 'long']) : pick(r, ['short', 'short', 'spiky', 'bald', 'short']),
    eyes: pick(r, [0x3d6ab0, 0x5a3a22, 0x3a8a4a, 0x2a2a2a]), shirt: pick(r, cols), shirt2: pick(r, cols), shirtStyle: pick(r, ['tee', 'tee', 'stripes', 'hoodie', 'jacket', female ? 'dress' : 'flannel', 'tee']),
    sleeves: r() < 0.5 ? 'short' : 'long', pants: pick(r, pants), shoes: pick(r, [0x2a2a2e, 0xeeeeee, 0x5a3a22, 0x8a2a2a]), female,
  };
}

// ---------------------------------------------------------------- humanoid
export function buildHumanoid(spec, seed = 1) {
  const tex = {}; for (const e of EXPRS) tex[e] = toTex(paintSkin(spec, e, seed), { mip: false, repeat: false });
  const mat = new THREE.MeshLambertMaterial({ map: tex.neutral }), headMat = new THREE.MeshLambertMaterial({ map: tex.neutral });
  const hatMat = new THREE.MeshLambertMaterial({ map: tex.neutral, alphaTest: 0.5, side: THREE.DoubleSide });
  const mk = (geo, m) => { const me = new THREE.Mesh(geo, m); me.castShadow = true; me.receiveShadow = true; return me; };
  const root = new THREE.Group(), hips = new THREE.Group(); hips.position.y = 12 * PX; root.add(hips);
  const torso = new THREE.Group(); hips.add(torso);
  const body = mk(partGeo(8, 12, 4, 16, 16), mat); body.position.y = 6 * PX; torso.add(body);
  const neck = new THREE.Group(); neck.position.y = 12 * PX; torso.add(neck);
  const head = mk(partGeo(8, 8, 8, 0, 0), headMat); head.position.y = 4 * PX; neck.add(head);
  const hat = mk(partGeo(8, 8, 8, 32, 0, 0.9), hatMat); hat.position.y = 4 * PX; neck.add(hat);
  const shL = new THREE.Group(); shL.position.set(6 * PX, 10 * PX, 0); torso.add(shL);
  const armL = mk(partGeo(4, 12, 4, 32, 48), mat); armL.position.y = -4 * PX; shL.add(armL);
  const shR = new THREE.Group(); shR.position.set(-6 * PX, 10 * PX, 0); torso.add(shR);
  const armR = mk(partGeo(4, 12, 4, 40, 16), mat); armR.position.y = -4 * PX; shR.add(armR);
  const handL = new THREE.Group(); handL.position.y = -10 * PX; shL.add(handL);
  const handR = new THREE.Group(); handR.position.y = -10 * PX; shR.add(handR);
  const lgL = new THREE.Group(); lgL.position.set(2 * PX, 0, 0); hips.add(lgL); const legL = mk(partGeo(4, 12, 4, 16, 48), mat); legL.position.y = -6 * PX; lgL.add(legL);
  const lgR = new THREE.Group(); lgR.position.set(-2 * PX, 0, 0); hips.add(lgR); const legR = mk(partGeo(4, 12, 4, 0, 16), mat); legR.position.y = -6 * PX; lgR.add(legR);
  const ch = { root, hips, torso, neck, head, shL, shR, handL, handR, lgL, lgR, tex, headMat, expr: 'neutral', spec };
  ch.setExpr = (e) => { if (ch.expr === e || !tex[e]) return; ch.expr = e; headMat.map = tex[e]; headMat.needsUpdate = true; };
  ch.reset = () => { hips.position.set(0, 12 * PX, 0); for (const g of [hips, torso, neck, shL, shR, lgL, lgR, root]) g.rotation.set(0, 0, 0); root.scale.setScalar(ch.baseScale || 1); };
  // accessories
  const acc = (geo, color, parent, pos) => { const m = mk(geo, new THREE.MeshLambertMaterial({ color })); m.position.set(...pos); parent.add(m); return m; };
  if (spec.tophat) { acc(new THREE.BoxGeometry(11 * PX, 1.2 * PX, 11 * PX), 0x141416, neck, [0, 8.8 * PX, 0]); acc(new THREE.BoxGeometry(7.5 * PX, 7 * PX, 7.5 * PX), 0x141416, neck, [0, 12.5 * PX, 0]); acc(new THREE.BoxGeometry(7.7 * PX, 1.2 * PX, 7.7 * PX), 0x8a1a1a, neck, [0, 9.8 * PX, 0]); }
  if (spec.cap) { acc(new THREE.BoxGeometry(8.8 * PX, 2.6 * PX, 8.8 * PX), spec.cap, neck, [0, 8.5 * PX, 0]); acc(new THREE.BoxGeometry(8 * PX, 0.8 * PX, 4 * PX), spec.cap, neck, [0, 7.4 * PX, 5.5 * PX]); }
  if (spec.headphones) { acc(new THREE.BoxGeometry(10 * PX, 1.2 * PX, 2 * PX), spec.headphones, neck, [0, 8.9 * PX, 0]); for (const sx of [-1, 1]) acc(new THREE.BoxGeometry(1.6 * PX, 3.5 * PX, 3 * PX), spec.headphones, neck, [sx * 4.6 * PX, 4.5 * PX, 0]); }
  if (spec.backpack) { acc(new THREE.BoxGeometry(6 * PX, 7 * PX, 3 * PX), spec.backpack, torso, [0, 5 * PX, -3.5 * PX]); }
  return ch;
}

export function buildProp(kind, T) {
  const g = new THREE.Group(); const m = (geo, mat, pos, rot) => { const x = new THREE.Mesh(geo, mat); x.position.set(...pos); if (rot) x.rotation.set(...rot); x.castShadow = true; g.add(x); return x; };
  if (kind === 'stop') { m(new THREE.BoxGeometry(0.06, 1.3, 0.06), new THREE.MeshLambertMaterial({ color: 0x8a8a8a }), [0, 0.2, 0]); const c = document.createElement('canvas'); c.width = c.height = 16; const x = c.getContext('2d'); x.fillStyle = '#d02a22'; x.beginPath(); for (let i = 0; i < 8; i++) { const a = Math.PI / 8 + i * Math.PI / 4; x.lineTo(8 + 7.5 * Math.cos(a), 8 + 7.5 * Math.sin(a)); } x.fill(); x.fillStyle = '#fff'; x.fillRect(3, 7, 10, 2); const t = toTex(c, { mip: false, repeat: false }); m(new THREE.PlaneGeometry(0.75, 0.75), new THREE.MeshLambertMaterial({ map: t, transparent: true, alphaTest: 0.5, side: THREE.DoubleSide }), [0, 0.95, 0.04]); }
  if (kind === 'bag') { m(new THREE.BoxGeometry(0.36, 0.42, 0.26), new THREE.MeshLambertMaterial({ color: 0xc8a676 }), [0, -0.2, 0.05]); m(new THREE.BoxGeometry(0.12, 0.12, 0.12), new THREE.MeshLambertMaterial({ color: 0xf08a20 }), [0.06, 0.05, 0.05]); m(new THREE.BoxGeometry(0.1, 0.18, 0.1), new THREE.MeshLambertMaterial({ color: 0x5aa83a }), [-0.08, 0.06, 0.02]); }
  if (kind === 'orange') m(new THREE.BoxGeometry(0.14, 0.14, 0.14), new THREE.MeshLambertMaterial({ color: 0xf08a20 }), [0, 0.07, 0]);
  if (kind === 'ladder') { const wd = new THREE.MeshLambertMaterial({ color: 0xb08a4a }); for (const x of [-0.32, 0.32]) m(new THREE.BoxGeometry(0.1, 7, 0.1), wd, [x, 3.5, 0]); for (let y = 0.4; y < 7; y += 0.5) m(new THREE.BoxGeometry(0.64, 0.07, 0.08), wd, [0, y, 0]); }
  if (kind === 'bike') { const blk = new THREE.MeshLambertMaterial({ color: 0x1a1a1c }), frm = new THREE.MeshLambertMaterial({ color: 0x2a8a3a }); for (const z of [-0.45, 0.45]) m(new THREE.BoxGeometry(0.06, 0.6, 0.6), blk, [0, 0.3, z]); m(new THREE.BoxGeometry(0.06, 0.06, 0.95), frm, [0, 0.55, 0]); m(new THREE.BoxGeometry(0.06, 0.45, 0.06), frm, [0, 0.72, -0.2]); m(new THREE.BoxGeometry(0.5, 0.05, 0.05), blk, [0, 0.95, 0.4]); m(new THREE.BoxGeometry(0.06, 0.4, 0.06), frm, [0, 0.75, 0.38]); }
  if (kind === 'sign') { const c = document.createElement('canvas'); c.width = 48; c.height = 12; const x = c.getContext('2d'); x.fillStyle = '#d42020'; x.fillRect(0, 0, 48, 12); x.fillStyle = '#fff'; const txt = label('SUBSCRIBE'); x.font = 'bold 9px "Inter Display", sans-serif'; const fs = Math.min(9, 9 * 45 / x.measureText(txt).width); x.font = `bold ${fs.toFixed(2)}px "Inter Display", sans-serif`; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText(txt, 24, 6.5); const t = toTex(c, { mip: false, repeat: false }); m(new THREE.BoxGeometry(1.1, 0.3, 0.05), new THREE.MeshLambertMaterial({ map: t }), [0, 0, 0]); }
  return g;
}

// ---------------------------------------------------------------- shadow creature (flat, tall, no face)
export function buildShadowThing() {
  const mat = new THREE.MeshBasicMaterial({ color: 0x040406 });
  const mk = (w, h, d) => { const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat); m.castShadow = true; return m; };
  const root = new THREE.Group(); const hips = new THREE.Group(); hips.position.y = 7; root.add(hips);
  const torso = new THREE.Group(); hips.add(torso); const body = mk(2.0, 5.2, 0.22); body.position.y = 2.6; torso.add(body);
  const neck = new THREE.Group(); neck.position.y = 5.2; torso.add(neck); const head = mk(1.55, 1.9, 0.22); head.position.y = 0.95; neck.add(head);
  const arm = (sx) => { const s = new THREE.Group(); s.position.set(sx * 1.25, 4.9, 0); torso.add(s); const a = mk(0.42, 8.5, 0.18); a.position.y = -4.25; s.add(a); const hand = new THREE.Group(); hand.position.y = -8.5; s.add(hand); for (const fx of [-0.15, 0, 0.15]) { const f = mk(0.09, 1.5, 0.08); f.position.set(fx * 1.4, -0.7, 0); f.rotation.z = fx * 0.8; hand.add(f); } return s; };
  const shL = arm(1), shR = arm(-1);
  const leg = (sx) => { const l = new THREE.Group(); l.position.set(sx * 0.55, 0, 0); hips.add(l); const g = mk(0.55, 7, 0.2); g.position.y = -3.5; l.add(g); return l; };
  const lgL = leg(1), lgR = leg(-1);
  const t = { root, hips, torso, neck, head, shL, shR, lgL, lgR, mat };
  t.reset = () => { for (const g of [hips, torso, neck, shL, shR, lgL, lgR, root]) g.rotation.set(0, 0, 0); root.scale.set(1, 1, 1); hips.position.y = 7; };
  return t;
}
