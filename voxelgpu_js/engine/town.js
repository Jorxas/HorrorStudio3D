// Town generator: suburb streets, houses, commercial strip, downtown square, town hall, highway.
import * as THREE from 'three';
import { World, defBlock, ID, buildWorldMesh } from './voxel.js';
import { mulberry, pick, toTex } from './textures.js';
import { makeTextures, roadCanvas, sidewalkCanvas, crosswalkCanvas, signCanvas, weddingPoster } from './towntex.js';
import { label } from './i18n.js';

// ---------------------------------------------------------------- blocks
const B = {};
B.grass = defBlock('grass', { top: 'grassTop', side: 'grassSide', bottom: 'dirt' });
B.dirt = defBlock('dirt', { all: 'dirt' });
B.cobble = defBlock('cobble', { all: 'cobble' });
B.stone = defBlock('stone', { all: 'stone' });
B.concrete = defBlock('concrete', { all: 'concrete' });
B.brick = defBlock('brick', { all: 'brick' });
for (const c of ['White', 'Red', 'Blue', 'Yellow', 'Beige', 'Green', 'Grey']) B['siding' + c] = defBlock('siding' + c, { all: 'siding' + c, top: 'trim' });
for (const c of ['Grey', 'Brown', 'Red', 'Dark']) B['roof' + c] = defBlock('roof' + c, { all: 'roof' + c });
B.trim = defBlock('trim', { all: 'trim' });
B.window = defBlock('window', { all: 'window', top: 'trim', bottom: 'trim' });
B.windowL = defBlock('windowL', { all: 'windowLit', top: 'trim', bottom: 'trim' });
B.door = defBlock('door', { all: 'door', top: 'trim', bottom: 'trim' });
B.garage = defBlock('garage', { all: 'garage', top: 'trim' });
B.plank = defBlock('plank', { all: 'plank' });
B.marble = defBlock('marble', { all: 'marble' });
B.column = defBlock('column', { all: 'column', top: 'trim', bottom: 'trim' });
B.townhall = defBlock('townhall', { all: 'townhall', top: 'trim' });
for (const c of ['Pink', 'Teal', 'Mint', 'Yellow', 'Orange', 'Lavender', 'Sky', 'Cream', 'Green']) B['paint' + c] = defBlock('paint' + c, { all: 'paint' + c, top: 'trim' });
B.shopWin = defBlock('shopWin', { all: 'shopWindowLit', top: 'trim', bottom: 'trim' });
B.water = defBlock('water', { all: 'water', mode: 'water' });
B.leaves = defBlock('leaves', { all: 'leavesOak', mode: 'cutout' });
B.hedge = defBlock('hedge', { all: 'hedge' });
B.log = defBlock('log', { top: 'logTop', bottom: 'logTop', side: 'logSide' });
B.darkWood = defBlock('darkWood', { all: 'darkWood' });
B.glass = defBlock('glass', { all: 'cut_glass', top: 'trim', bottom: 'trim', mode: 'cutout' });
export { B };

const SIDINGS = ['sidingWhite', 'sidingRed', 'sidingBlue', 'sidingYellow', 'sidingBeige', 'sidingWhite', 'sidingGrey', 'sidingGreen'];
const ROOFS = ['roofGrey', 'roofBrown', 'roofDark', 'roofRed', 'roofGrey'];
const PAINTS = ['paintPink', 'paintTeal', 'paintMint', 'paintYellow', 'paintOrange', 'paintLavender', 'paintSky', 'paintCream', 'brick', 'paintGreen', 'brick'];
const AWN = ['awnRed', 'awnGreen', 'awnBlue', 'awnPink', 'awnYellow'];
const SHOPS = ['BAKERY', 'DELI', 'SPORTS', 'CANDY', 'MUSIC', 'COMICS', 'GAMES', 'NEWS', 'FRUIT', 'PHARMACY', 'SOAP', 'BOOKS', 'TOYS', 'CAFE', 'FLOWERS', 'SHOES', 'HATS', 'TEA', 'GIFTS', 'BANK', 'POST', 'DINER'];

export const LAYOUT = {
  mainX: [-5, 5], mainZ: [-52, 244], walkW: 3,
  cross: [[35, 45], [131, 141]], parallelX: [[47, 57], [-57, -47]],
  plaza: { x: [-32, 32], z: [-112, -52], fountain: [0, -82] },
  highwayZ: [246, 262], townLineZ: 232,
};

// world helper: place in "facing" local frame. Local (u = along street, v = away from street, y)
function frame(origin, facing) {
  // facing: direction the FRONT looks toward: '+x','-x','+z','-z'; origin = front-left corner (world ints)
  const [ox, oz] = origin;
  if (facing === '-x') return (u, v) => [ox + v, oz + u];     // front at x=ox, building extends +x
  if (facing === '+x') return (u, v) => [ox - v, oz - u];     // front at x=ox, extends -x
  if (facing === '+z') return (u, v) => [ox + u, oz - v];     // front at z=oz, extends -z
  return (u, v) => [ox - u, oz + v];                          // '-z' front at z=oz, extends +z
}

function house(w, origin, facing, r, info) {
  const F0 = frame(origin, facing);
  const W = 11, D = 9, H = 7;
  const gSide = r() < 0.5 ? -1 : 1; const su = gSide < 0 ? 5 : 0;
  const F = (u, v) => F0(u + su, v);
  const sid = B[pick(r, SIDINGS)], rf = B[pick(r, ROOFS)];
  const set = (u, v, y, b) => { const [x, z] = F(u, v); w.set(x, y, z, b); };
  // foundation + body
  for (let u = 0; u < W; u++) for (let v = 0; v < D; v++) { set(u, v, 0, B.stone); for (let y = 1; y <= H; y++) set(u, v, y, sid); }
  for (let u = 0; u < W; u++) for (let v = 0; v < D; v++) set(u, v, 4, sid);
  // trim band
  for (let u = 0; u < W; u++) { set(u, 0, 4, B.trim); set(u, D - 1, 4, B.trim); } for (let v = 0; v < D; v++) { set(0, v, 4, B.trim); set(W - 1, v, 4, B.trim); }
  // windows front
  const win = (u, v, y) => set(u, v, y, r() < 0.35 ? B.windowL : B.window);
  for (const u of [1, 2, 8, 9]) for (const y of [2, 3]) win(u, 0, y);
  for (const u of [1, 2, 4, 6, 8, 9]) for (const y of [5, 6]) win(u, 0, y);
  for (const y of [1, 2, 3]) set(5, 0, y, y === 3 ? B.trim : B.door);
  // side + back windows
  for (const v of [3, 5]) for (const y of [2, 3, 5, 6]) { win(0, v, y); win(W - 1, v, y); }
  for (const u of [2, 5, 8]) for (const y of [2, 3, 5, 6]) win(u, D - 1, y);
  // roof
  const gableFront = r() < 0.5;
  for (let k = 0; ; k++) {
    const y = H + 1 + k; let any = false;
    if (!gableFront) { // ridge along u
      const v0 = k - 1, v1 = D - k; if (v0 > v1) break;
      for (let u = -1; u <= W; u++) for (let v = v0; v <= v1; v++) {
        const edge = v === v0 || v === v1; const inside = u >= 0 && u < W;
        if (edge || v0 + 1 >= v1) { set(u, v, y, rf); any = true; } else if (inside) set(u, v, y, (u === 0 || u === W - 1) && k === 1 ? B.window : sid);
      }
    } else { // ridge along v (gable faces street)
      const u0 = k - 1, u1 = W - k; if (u0 > u1) break;
      for (let v = -1; v <= D; v++) for (let u = u0; u <= u1; u++) {
        const edge = u === u0 || u === u1; const inside = v >= 0 && v < D;
        if (edge || u0 + 1 >= u1) { set(u, v, y, rf); any = true; } else if (inside) set(u, v, y, (v === 0 && k === 2 && u === 5) ? B.windowL : sid);
      }
    }
    if (!any) break;
  }
  // chimney
  for (let y = 1; y < H + 7; y++) set(W - 2, D - 2, y, B.brick);
  // porch
  for (let u = 3; u <= 7; u++) for (let v = -2; v < 0; v++) set(u, v, 0, B.plank);
  for (const u of [3, 7]) for (let y = 1; y <= 3; y++) set(u, -2, y, B.trim);
  for (let u = 3; u <= 7; u++) for (let v = -2; v < 0; v++) set(u, v, 4, rf);
  // garage (side)
  const gu0 = gSide < 0 ? -5 : W, gu1 = gu0 + 5;
  for (let u = gu0; u < gu1; u++) for (let v = 0; v < 7; v++) { for (let y = 0; y <= 4; y++) set(u, v, y, y === 0 ? B.stone : sid); set(u, v, 5, rf); }
  for (let u = gu0 + 1; u < gu1 - 1; u++) for (let y = 1; y <= 3; y++) set(u, 0, y, B.garage);
  const [px, pz] = F(5.5, -2.5); const [dx, dz] = F(5.5, 0); const [gx, gz] = F(gu0 + 3, -0.5);
  info.houses.push({ facing, front: F(0, 0), porch: [px, pz], door: [dx, dz], garage: [gx, gz], W, D, sid });
}

function shop(w, origin, facing, width, height, r, info, name, opts = {}) {
  const F = frame(origin, facing); const D = 10;
  const mat = opts.mat !== undefined ? opts.mat : B[pick(r, PAINTS)];
  const set = (u, v, y, b) => { const [x, z] = F(u, v); w.set(x, y, z, b); };
  for (let u = 0; u < width; u++) for (let v = 0; v < D; v++) for (let y = 0; y < height; y++) set(u, v, y, mat);
  // storefront
  for (let u = 1; u < width - 1; u++) for (let y = 0; y <= 2; y++) set(u, 0, y, y === 0 ? B.darkWood : B.shopWin);
  const du = Math.floor(width / 2); for (let y = 0; y <= 2; y++) set(du, 0, y, y === 2 ? B.trim : B.door);
  for (let u = 0; u < width; u++) set(u, 0, 3, B.trim);
  // upper windows
  for (let y = 5; y < height - 1; y += 3) for (let u = 1; u < width - 1; u += 2) { set(u, 0, y, r() < 0.5 ? B.windowL : B.window); set(u, 0, y + 1, r() < 0.5 ? B.windowL : B.window); }
  for (let u = -0; u < width; u++) { set(u, 0, height - 1, B.trim); set(u, 0, height, B.trim); }
  if (opts.display) { for (let u = 1; u < du; u++) for (let v = 0; v < 2; v++) for (let y = 0; y <= 2; y++) set(u, v, y, y === 0 ? B.plank : 0); }
  const c0 = F(0, 0), c1 = F(width, 0); const mid = F(width / 2, 0);
  info.shops.push({ name, facing, width, height, a: c0, b: c1, mid, door: F(du + 0.5, -0.5), awn: opts.awn || pick(r, AWN), display: opts.display ? { a: F(1, 0), b: F(du, 0), back: F(du / 2 + 0.5, 2) } : null });
}

function oak(w, x, z, r, y0 = 0) {
  const h = 4 + Math.floor(r() * 3); for (let y = 0; y < h; y++) w.set(x, y0 + y, z, B.log);
  const R = 2.4 + r() * 0.9; const cy = y0 + h;
  for (let dx = -4; dx <= 4; dx++) for (let dy = -3; dy <= 3; dy++) for (let dz = -4; dz <= 4; dz++) {
    if ((dx / R) ** 2 + (dy / (R * 0.8)) ** 2 + (dz / R) ** 2 < 1 + (r() - 0.5) * 0.3) w.setIfAir(x + dx, cy + dy, z + dz, B.leaves);
  }
}

export function buildTown() {
  const w = new World(-90, 90, -2, 40, -140, 270); const r = mulberry(2026);
  const info = { houses: [], shops: [], lamps: [], oldLamps: [], trees: [], fences: [], mailboxes: [], signs: [] };
  // ground
  for (let x = w.X0; x < w.X1; x++) for (let z = w.Z0; z < w.Z1; z++) { w.set(x, -2, z, B.dirt); w.set(x, -1, z, B.grass); }
  const P = LAYOUT.plaza;
  for (let x = P.x[0] - 12; x < P.x[1] + 12; x++) for (let z = -140; z < P.z[1]; z++) w.set(x, -1, z, B.cobble);
  // houses along main street + parallel streets
  const lots = []; for (let z = -8; z < 226; z += 18) { if (LAYOUT.cross.some(([a, b]) => z + 16 > a - 2 && z < b + 2)) continue; lots.push(z); }
  const addFrontage = (h, sideX) => {
    const pz = h.porch[1];
    if (r() < 0.55) info.fences.push({ x: sideX, z0: pz - 6.5, z1: pz + 9.5, gap: [pz - 1.0, pz + 1.0] });
    else if (r() < 0.6) { const hx = sideX > 0 ? Math.floor(sideX + 0.3) : Math.floor(sideX - 0.3); for (let zz = Math.floor(pz - 6); zz < pz + 9; zz++) if (Math.abs(zz + 0.5 - pz) > 1.5) w.set(hx, 0, zz, B.hedge); }
    info.mailboxes.push({ x: sideX - Math.sign(sideX) * 0.35, z: pz + 2.2, yaw: sideX > 0 ? -Math.PI / 2 : Math.PI / 2 });
  };
  for (const z of lots) {
    house(w, [15, z], '-x', r, info); addFrontage(info.houses[info.houses.length - 1], 8.75);
    house(w, [-15, z + 16], '+x', r, info); addFrontage(info.houses[info.houses.length - 1], -8.75);
    for (const [a, b] of LAYOUT.parallelX) {
      house(w, [b + 7, z], '-x', r, info); addFrontage(info.houses[info.houses.length - 1], b + 3.75);
      house(w, [a - 7, z + 16], '+x', r, info); addFrontage(info.houses[info.houses.length - 1], a - 3.75);
    }
    // backyard trees (between the rows)
    oak(w, 27 + Math.floor(r() * 2), z + 3 + Math.floor(r() * 10), r); oak(w, -28 - Math.floor(r() * 2), z + 3 + Math.floor(r() * 10), r);
    if (r() < 0.6) oak(w, 70 + Math.floor(r() * 4), z + 6, r); if (r() < 0.6) oak(w, -73 - Math.floor(r() * 4), z + 9, r);
  }
  // commercial strip near downtown
  shop(w, [8, -24], '-x', 13, 8, r, info, 'BAKERY', { mat: B.brick, awn: 'awnRed', display: true });
  shop(w, [-8, -16], '+x', 13, 7, r, info, 'CORNER MARKET', { mat: B.paintCream, awn: 'awnYellow' });
  // downtown rows
  let k = 0;
  for (let z = P.z[0]; z < P.z[1] - 2; z += 10) { shop(w, [P.x[0], z + 10], '+x', 10, 9 + Math.floor(r() * 6), r, info, SHOPS[(k++) % SHOPS.length]); }
  for (let z = P.z[0]; z < P.z[1] - 2; z += 10) { shop(w, [P.x[1], z], '-x', 10, 9 + Math.floor(r() * 6), r, info, SHOPS[(k++) % SHOPS.length]); }
  for (const [xa, xb] of [[-32, -23], [-23, -14], [-14, -6], [6, 15], [15, 24], [24, 32]]) shop(w, [xb, P.z[1]], '-z', xb - xa, 9 + Math.floor(r() * 5), r, info, SHOPS[(k++) % SHOPS.length]);
  for (const x0 of [-32, 18]) shop(w, [x0, P.z[0]], '+z', 14, 12, r, info, SHOPS[(k++) % SHOPS.length]);
  // town hall
  const th = { x: [-16, 16], z: [-138, -118] };
  for (let x = th.x[0]; x < th.x[1]; x++) for (let z = th.z[0]; z < th.z[1]; z++) { for (let y = 0; y < 13; y++) w.set(x, y, z, B.townhall); w.set(x, 13, z, B.trim); }
  for (let x = th.x[0]; x < th.x[1]; x++) for (const y of [3, 4, 7, 8, 10, 11]) if ((x - th.x[0]) % 3 === 1) w.set(x, y, th.z[1] - 1, B.window);
  for (let x = -2; x <= 2; x++) for (let y = 2; y <= 6; y++) w.set(x, y, th.z[1] - 1, x === 0 || y === 6 ? B.trim : B.door);
  for (let x = -12; x <= 12; x++) for (let z = th.z[1]; z < th.z[1] + 3; z++) { w.set(x, 0, z, B.marble); w.set(x, 1, z, B.marble); w.set(x, 11, z, B.trim); w.set(x, 12, z, B.townhall); }
  for (let x = -12; x <= 12; x += 3) for (let y = 2; y <= 10; y++) w.set(x, y, th.z[1] + 2, B.column);
  for (let x = -14; x <= 14; x++) { w.set(x, 0, th.z[1] + 3, B.marble); w.set(x, 0, th.z[1] + 4, B.marble); w.set(x, 1, th.z[1] + 3, B.marble); }
  for (let kk = 0; kk < 7; kk++) for (let x = -12 + kk * 2; x <= 12 - kk * 2; x++) for (let z = th.z[1]; z < th.z[1] + 3; z++) w.set(x, 13 + kk, z, B.townhall);
  for (let x = -3; x <= 3; x++) for (let z = -132; z <= -126; z++) for (let y = 13; y < 22; y++) w.set(x, y, z, (y === 18 && (x === 0) && z === -126) ? B.windowL : B.townhall);
  for (let kk = 0; kk < 4; kk++) for (let x = -3 + kk; x <= 3 - kk; x++) for (let z = -132 + kk; z <= -126 - kk; z++) w.set(x, 22 + kk, z, B.roofDark);
  info.townHall = { front: [0, th.z[1] + 3], top: 26 };
  // fountain
  const [fx, fz] = P.fountain;
  for (let x = -7; x <= 7; x++) for (let z = -7; z <= 7; z++) {
    const d = Math.hypot(x + 0.5 - 0.5, z + 0.5 - 0.5);
    if (d < 6.2 && d >= 5.0) w.set(fx + x, 0, fz + z, B.stone); else if (d < 5.0) w.set(fx + x, 0, fz + z, B.water);
    if (d < 1.2) for (let y = 0; y < 4; y++) w.set(fx + x, y, fz + z, B.stone);
    if (d < 2.9 && d >= 2.0) w.set(fx + x, 3, fz + z, B.stone); else if (d < 2.0 && d >= 1.2) w.set(fx + x, 3, fz + z, B.water);
    if (d < 0.9) { w.set(fx + x, 4, fz + z, B.stone); w.set(fx + x, 5, fz + z, B.stone); }
  }
  info.fountain = { x: fx + 0.5, z: fz + 0.5, r: 6 };
  // lamps
  for (let z = -40; z < 244; z += 24) { info.lamps.push([7.5, z]); info.lamps.push([-7.5, z + 12]); }
  for (let x = P.x[0] + 4; x < P.x[1]; x += 12) { info.oldLamps.push([x, P.z[0] + 3]); info.oldLamps.push([x, P.z[1] - 3]); }
  for (let z = P.z[0] + 9; z < P.z[1]; z += 12) { info.oldLamps.push([P.x[0] + 3, z]); info.oldLamps.push([P.x[1] - 3, z]); }
  for (const [ax, az] of [[8, 8], [-8, 8], [8, -8], [-8, -8]]) info.oldLamps.push([fx + 0.5 + ax, fz + 0.5 + az]);
  // a few plaza trees
  info.signs.push({ text: 'TOWN LIMIT', x: 10, z: LAYOUT.townLineZ, yaw: Math.PI });
  return { w, info };
}

// ---------------------------------------------------------------- meshes: roads, sidewalks, props
export function buildTownMeshes(scene, info, T) {
  const group = new THREE.Group(); scene.add(group);
  const texCache = {};
  const stripTex = (canvas, rx, ry) => { const t = toTex(canvas, { mip: true }); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(rx, ry); return t; };
  const plane = (tex, w, h, x, y, z, rotY = 0, opts = {}) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshLambertMaterial({ map: tex, transparent: !!opts.transparent, alphaTest: opts.alphaTest || 0, polygonOffset: true, polygonOffsetFactor: -1 - (opts.po || 0), polygonOffsetUnits: -1 }));
    m.rotation.x = -Math.PI / 2; m.rotation.z = rotY; m.position.set(x, y, z); m.receiveShadow = true; group.add(m); return m;
  };
  const roadC = roadCanvas(16, 10);
  // main street (along z)
  const L = LAYOUT;
  { const len = L.mainZ[1] - L.mainZ[0]; plane(stripTex(roadC, 1, len / 16), 10, len, 0, 0.02, (L.mainZ[0] + L.mainZ[1]) / 2); }
  for (const [a, b] of L.parallelX) { const len = 244 + 40; plane(stripTex(roadC, 1, len / 16), 10, len, (a + b) / 2, 0.02, (-40 + 244) / 2); }
  // cross streets (along x)
  for (const [a, b] of L.cross) { const tex = stripTex(roadC, 1, 180 / 16); const m = plane(tex, 10, 180, 0, 0.025, (a + b) / 2, Math.PI / 2); }
  // highway
  { const hc = roadCanvas(16, 16, { dashes: [4, 12] }); const m = plane(stripTex(hc, 1, 180 / 16), 16, 180, 0, 0.03, (L.highwayZ[0] + L.highwayZ[1]) / 2, Math.PI / 2); }
  // crosswalks
  const cw = toTex(crosswalkCanvas(10)); for (const [a, b] of L.cross) for (const zz of [a - 2.2, b + 2.2]) plane(cw, 10, 4, 0, 0.04, zz, 0, { alphaTest: 0.5, po: 2 });
  // sidewalks: raised slabs
  const swTex = (len) => stripTex(sidewalkCanvas(16, 3, true), 1, len / 16);
  const swMat = (len) => new THREE.MeshLambertMaterial({ map: swTex(len) });
  const curbMat = new THREE.MeshLambertMaterial({ map: T.concrete });
  const slab = (x, z, wx, wz, alongZ = true) => {
    const len = alongZ ? wz : wx; const g = new THREE.BoxGeometry(wx, 0.16, wz);
    const top = swMat(len); if (!alongZ) { top.map.rotation = Math.PI / 2; top.map.center.set(0.5, 0.5); }
    const m = new THREE.Mesh(g, [curbMat, curbMat, top, curbMat, curbMat, curbMat]); m.position.set(x, 0.08, z); m.receiveShadow = true; m.castShadow = true; group.add(m); return m;
  };
  const segs = (z0, z1) => { const out = []; let a = z0; for (const [c0, c1] of L.cross) { if (c0 > a && c0 < z1) { out.push([a, c0]); a = c1; } } out.push([a, z1]); return out; };
  for (const [a, b] of segs(-52, 244)) { slab(6.5, (a + b) / 2, 3, b - a); slab(-6.5, (a + b) / 2, 3, b - a); }
  for (const [pa, pb] of L.parallelX) for (const [a, b] of segs(-40, 244)) { slab(pb + 1.5, (a + b) / 2, 3, b - a); slab(pa - 1.5, (a + b) / 2, 3, b - a); }
  for (const [a, b] of L.cross) for (const zz of [a - 1.5, b + 1.5]) for (const [xa, xb] of [[-90, -60], [-44, -8], [8, 44], [60, 90]]) slab((xa + xb) / 2, zz, xb - xa, 3, false);
  // walkways to porches + driveways
  const walkMat = new THREE.MeshLambertMaterial({ map: T.concrete });
  const EDGES = [-60, -44, -8, 8, 44, 60];
  for (const h of info.houses) {
    const [px, pz] = h.porch; const toward = h.facing === '+x' ? 1 : -1;
    const x1 = toward > 0 ? Math.min(...EDGES.filter(e => e > px)) : Math.max(...EDGES.filter(e => e < px));
    const g = new THREE.BoxGeometry(Math.abs(x1 - px), 0.06, 1.6); const m = new THREE.Mesh(g, walkMat); m.position.set((px + x1) / 2, 0.03, pz); m.receiveShadow = true; group.add(m);
    const [gx, gz] = h.garage; const gx1 = toward > 0 ? Math.min(...EDGES.filter(e => e > gx)) : Math.max(...EDGES.filter(e => e < gx));
    const g2 = new THREE.BoxGeometry(Math.abs(gx1 - gx), 0.05, 4); const m2 = new THREE.Mesh(g2, walkMat); m2.position.set((gx + gx1) / 2, 0.025, gz); m2.receiveShadow = true; group.add(m2);
    const st = new THREE.Mesh(new THREE.BoxGeometry(1.0, 0.5, 2.2), new THREE.MeshLambertMaterial({ map: T.stone })); st.position.set(px, 0.25, pz); st.castShadow = st.receiveShadow = true; group.add(st);
  }
  // picket fences (instanced)
  const postGeo = new THREE.BoxGeometry(0.14, 0.95, 0.08), railGeo = new THREE.BoxGeometry(0.06, 0.08, 1);
  const fenceMat = new THREE.MeshLambertMaterial({ color: 0xf4f2ec });
  let nPosts = 0, nRails = 0; for (const f of info.fences) { nPosts += Math.ceil((f.z1 - f.z0) / 0.45); nRails += 2; }
  const posts = new THREE.InstancedMesh(postGeo, fenceMat, nPosts), rails = new THREE.InstancedMesh(railGeo, fenceMat, nRails * 2);
  const o = new THREE.Object3D(); let ip = 0, ir = 0;
  for (const f of info.fences) {
    for (let z = f.z0; z < f.z1; z += 0.45) { if (z > f.gap[0] && z < f.gap[1]) { o.position.set(0, -10, 0); } else o.position.set(f.x, 0.48, z); o.rotation.set(0, Math.PI / 2, 0); o.scale.set(1, 1, 1); o.updateMatrix(); posts.setMatrixAt(ip++, o.matrix); }
    for (const [a, b] of [[f.z0, f.gap[0]], [f.gap[1], f.z1]]) for (const y of [0.3, 0.72]) { o.position.set(f.x + 0.06, y, (a + b) / 2); o.rotation.set(0, 0, 0); o.scale.set(1, 1, Math.max(0.01, b - a)); o.updateMatrix(); if (ir < nRails * 2) rails.setMatrixAt(ir++, o.matrix); }
  }
  posts.count = ip; rails.count = ir; posts.castShadow = rails.castShadow = true; posts.receiveShadow = true; group.add(posts, rails);
  // mailboxes
  const mbMat = new THREE.MeshLambertMaterial({ color: 0x2b2d33 }), mbPost = new THREE.MeshLambertMaterial({ map: T.plank });
  for (const mb of info.mailboxes) {
    const g = new THREE.Group(); const p = new THREE.Mesh(new THREE.BoxGeometry(0.12, 1.0, 0.12), mbPost); p.position.y = 0.5; g.add(p);
    const b = new THREE.Mesh(new THREE.BoxGeometry(0.32, 0.3, 0.55), mbMat); b.position.y = 1.1; g.add(b);
    g.position.set(mb.x, 0, mb.z); g.rotation.y = mb.yaw; g.traverse(q => { if (q.isMesh) q.castShadow = true; }); group.add(g);
  }
  // street lamps (modern) + old lamps (plaza)
  const lampHeads = [], lampMats = [];
  const poleMat = new THREE.MeshLambertMaterial({ color: 0x55585e }), blackMat = new THREE.MeshLambertMaterial({ color: 0x1c1d20 });
  const headMat = new THREE.MeshLambertMaterial({ color: 0xf6f0dc, emissive: 0xffd9a0, emissiveIntensity: 0 });
  for (const [x, z] of info.lamps) {
    const g = new THREE.Group(); const pole = new THREE.Mesh(new THREE.BoxGeometry(0.18, 5.2, 0.18), poleMat); pole.position.y = 2.6; g.add(pole);
    const s = Math.sign(x); const arm = new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.12, 0.14), poleMat); arm.position.set(-s * 0.6, 5.15, 0); g.add(arm);
    const hm = headMat.clone(); const head = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.2, 0.36), hm); head.position.set(-s * 1.2, 5.02, 0); g.add(head);
    g.position.set(x, 0, z); g.traverse(q => { if (q.isMesh) q.castShadow = true; }); group.add(g); lampHeads.push(new THREE.Vector3(x - s * 1.2, 4.8, z)); lampMats.push(hm);
  }
  for (const [x, z] of info.oldLamps) {
    const g = new THREE.Group(); const pole = new THREE.Mesh(new THREE.BoxGeometry(0.2, 3.6, 0.2), blackMat); pole.position.y = 1.8; g.add(pole);
    const base = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.5, 0.42), blackMat); base.position.y = 0.25; g.add(base);
    const hm = headMat.clone(); lampMats.push(hm); const head = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.62, 0.5), hm); head.position.y = 3.95; g.add(head);
    const cap = new THREE.Mesh(new THREE.BoxGeometry(0.66, 0.16, 0.66), blackMat); cap.position.y = 4.32; g.add(cap);
    g.position.set(x, 0, z); g.traverse(q => { if (q.isMesh) q.castShadow = true; }); group.add(g); lampHeads.push(new THREE.Vector3(x, 3.9, z));
  }
  // shop awnings + signs
  const signMeshes = [];
  for (const s of info.shops) {
    const [ax, az] = s.a, [bx, bz] = s.b; const dx = bx - ax, dz = bz - az; const len = Math.hypot(dx, dz);
    const nrm = s.facing === '-x' ? [-1, 0] : s.facing === '+x' ? [1, 0] : s.facing === '+z' ? [0, 1] : [0, -1];
    const ang = Math.atan2(nrm[0], nrm[1]);
    const awn = new THREE.Mesh(new THREE.BoxGeometry(len - 1, 0.1, 1.9), new THREE.MeshLambertMaterial({ map: T[s.awn] }));
    const cx = (ax + bx) / 2 + nrm[0] * 0.95, cz = (az + bz) / 2 + nrm[1] * 0.95;
    awn.position.set(cx, 3.55, cz); awn.rotation.y = ang; awn.rotateX(0.32); awn.castShadow = true; awn.receiveShadow = true; group.add(awn);
    const valance = new THREE.Mesh(new THREE.BoxGeometry(len - 1, 0.32, 0.06), new THREE.MeshLambertMaterial({ map: T[s.awn] })); valance.position.set((ax + bx) / 2 + nrm[0] * 1.85, 3.12, (az + bz) / 2 + nrm[1] * 1.85); valance.rotation.y = ang; group.add(valance);
    const col = { awnRed: '#b8261e', awnGreen: '#1f7a3e', awnBlue: '#24489a', awnPink: '#b04878', awnYellow: '#b8801a' }[s.awn];
    const sc = signCanvas(label(s.name), { bg: s.name === 'CORNER MARKET' ? '#f4e14a' : '#f6f0e0', fg: col, border: '#2a1e14', h: 18 });
    const tex = toTex(sc, { mip: false, repeat: false });
    const sh = 1.05, sw = sh * sc.width / sc.height;
    const sm = new THREE.Mesh(new THREE.PlaneGeometry(Math.min(sw, len - 1.2), sh), new THREE.MeshLambertMaterial({ map: tex, emissive: 0xffffff, emissiveMap: tex, emissiveIntensity: 0 }));
    sm.position.set((ax + bx) / 2 + nrm[0] * 0.04, 4.45, (az + bz) / 2 + nrm[1] * 0.04); sm.rotation.y = ang; group.add(sm); signMeshes.push(sm);
    s.normal = nrm; s.angle = ang;
  }
  // bakery display: cake + wedding poster
  const bakery = info.shops.find(s => s.name === 'BAKERY');
  if (bakery && bakery.display) {
    const [ax, az] = bakery.display.a, [bx2, bz2] = bakery.display.b; const [kx, kz] = bakery.display.back;
    const pt = toTex(weddingPoster(), { mip: false, repeat: false });
    const poster = new THREE.Mesh(new THREE.PlaneGeometry(1.25, 1.72), new THREE.MeshLambertMaterial({ map: pt })); poster.position.set(kx - 0.03, 1.85, (az + bz2) / 2 + 0.6); poster.rotation.y = -Math.PI / 2; group.add(poster);
    bakery.poster = poster.position.clone();
    const cakeG = new THREE.Group(); const tiers = [[0.8, 0.32, 0xf6eee0], [0.58, 0.28, 0xf2d2dc], [0.38, 0.26, 0xf6eee0]]; let y = 1.0;
    for (const [rr, hh, c] of tiers) { const m = new THREE.Mesh(new THREE.BoxGeometry(rr, hh, rr), new THREE.MeshLambertMaterial({ color: c })); m.position.y = y + hh / 2; y += hh; cakeG.add(m); }
    cakeG.position.set(ax + 0.9, 0, (az + bz2) / 2 - 0.9); group.add(cakeG); bakery.cake = cakeG.position.clone();
    const glass = new THREE.Mesh(new THREE.PlaneGeometry(Math.abs(bz2 - az), 3), new THREE.MeshStandardMaterial({ color: 0xbfe0ff, transparent: true, opacity: 0.18, roughness: 0.05, metalness: 0.2, depthWrite: false })); glass.position.set(ax - 0.02, 1.5, (az + bz2) / 2); glass.rotation.y = -Math.PI / 2; group.add(glass);
  }
  // town limit sign
  for (const s of info.signs) {
    const sc = signCanvas(label(s.text), { bg: '#f4f4ee', fg: '#1d3a7a', border: '#1d3a7a', h: 18 }); const tex = toTex(sc, { mip: false, repeat: false });
    const g = new THREE.Group(); const board = new THREE.Mesh(new THREE.PlaneGeometry(4, 4 * sc.height / sc.width), new THREE.MeshLambertMaterial({ map: tex, side: THREE.DoubleSide })); board.position.y = 2.2; g.add(board);
    for (const px of [-1.5, 1.5]) { const p = new THREE.Mesh(new THREE.BoxGeometry(0.12, 2.2, 0.12), poleMat); p.position.set(px, 1.1, -0.05); g.add(p); }
    g.position.set(s.x, 0, s.z); g.rotation.y = s.yaw; g.traverse(q => { if (q.isMesh) q.castShadow = true; }); group.add(g);
  }
  return { group, lampHeads, lampMats, headMat, signMeshes };
}

export function sidewalkY(x, z) {
  const ax = Math.abs(x); const inCross = LAYOUT.cross.some(([a, b]) => z > a && z < b);
  if (z > -52 && z < 244 && ax > 5 && ax < 8 && !inCross) return 0.16;
  for (const [a, b] of LAYOUT.parallelX) if (z > -40 && z < 244 && !inCross && ((x > b && x < b + 3) || (x > a - 3 && x < a))) return 0.16;
  for (const [a, b] of LAYOUT.cross) if ((z > a - 3 && z < a) || (z > b && z < b + 3)) { if (!((ax < 8) || (ax > 44 && ax < 60))) return 0.16; }
  return 0;
}

export function buildTownWorld(scene, prepare) {
  const { T } = makeTextures();
  const { w, info } = buildTown();
  if (prepare) prepare(w, info, B);
  const WM = buildWorldMesh(w, T, scene, { glow: { windowLit: T.windowGlow, shopWindowLit: T.shopGlow } });
  const M = buildTownMeshes(scene, info, T);
  const groundY = (x, z) => { const xi = Math.floor(x), zi = Math.floor(z); for (let y = 3; y >= -1; y--) { const t = w.get(xi, y, zi); if (t && t !== B.leaves && t !== B.water && t !== B.hedge) return y + 1; } return sidewalkY(x, z); };
  return { w, info, T, WM, M, groundY: (x, z) => Math.max(groundY(x, z), sidewalkY(x, z)) };
}
