// Décor v4 « station-service » : supérette (rayons pleins de produits, frigos lumineux, carrelage mouillé
// réfléchissant, néons au plafond, comptoir + caisse + moniteur de surveillance, caméra au plafond, sortie de secours),
// façade vitrée sous la pluie (vitres transparentes ruisselantes, traces de mains), parking mouillé, voiture aux
// phares rouges, auvent des pompes, lampadaires, sapins sombres derrière.
// Repère local : intérieur x ∈ [-4.5, 4.5], z ∈ [-7, 3.5] (vitrine en z = 3.5), plafond 3.2 ; parking en z > 3.5.
import * as THREE from 'three';
import { Batch, mat4, grunge, tiles, productTex, rimify } from './kit4.js';
import { boxesGeometry } from './boxes.js';
import { mulberry } from './textures.js';
import { vox, vmat, buildCCTV, buildMonitor, buildCar, cansBoxes, crateBoxes, handprintMaterial } from './props4.js';
import { glassOutMaterial } from './sets4.js';
const V = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);

function textTex(text, { w = 512, h = 96, font = '800 64px Inter, sans-serif', col = '#ff2a20', bg = '#0a0202' } = {}) {
  const c = document.createElement('canvas'); c.width = w; c.height = h; const g = c.getContext('2d'); g.fillStyle = bg; g.fillRect(0, 0, w, h);
  g.font = font; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillStyle = col; g.fillText(text, w / 2, h / 2 + 2);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t;
}

export function buildStation(ctx, origin = V(200, 0, 0), opts = {}) {
  const RES = !!opts.reserve;      // unified studio: a real doorway in the back wall (the back room, reserve.js), no painted-on door; every other call builds the shop exactly as before
  const { reflector } = ctx; const r = mulberry(21);
  const group = new THREE.Group(); group.position.copy(origin); ctx.scene.add(group);
  const M = {
    wall: mat4(grunge(0xd8d0c8, { size: 32, noise: 0.12, dark: 0.3, seed: 31, specks: 0.05, speckCol: 0x5a4a42 }), { rim: 0.3, wet: 0.5 }),
    wallLow: mat4(tiles(0xe8e2da, 0xd0c8c0, { size: 32, n: 4, seed: 32, grout: 0x8a827a }), { rim: 0.3, wet: 0.8 }),
    ceil: mat4(tiles(0xc8c4bc, 0xbcb8b0, { size: 32, n: 2, seed: 33, grout: 0x4a4644 }), { rim: 0.15, wet: 0.2 }),
    shelf: mat4(grunge(0x3a3e46, { size: 16, noise: 0.15, dark: 0.2, rust: 0.05, seed: 34 }), { shininess: 40, specular: 0x333333, rim: 0.6 }),
    shelfEdge: mat4(grunge(0xf0f0ea, { size: 16, noise: 0.08, seed: 35 }), { rim: 0.4 }),
    frame: mat4(grunge(0x141418, { size: 16, noise: 0.15, seed: 36 }), { shininess: 40, specular: 0x333333, rim: 0.7 }),
    counter: mat4(grunge(0x8a1a1e, { size: 16, noise: 0.15, dark: 0.2, seed: 37 }), { shininess: 30, specular: 0x331111, rim: 0.5 }),
    counterTop: mat4(grunge(0x2a2a2e, { size: 16, noise: 0.1, seed: 38 }), { shininess: 60, specular: 0x444444, rim: 0.5 }),
    fridge: mat4(grunge(0xe8e8e4, { size: 16, noise: 0.08, seed: 39 }), { rim: 0.4 }),
    facade: mat4(grunge(0x2a2a30, { size: 32, noise: 0.2, dark: 0.3, rust: 0.04, seed: 40 }), { rim: 0.6, wet: 1.4 }),
    facadeRed: mat4(grunge(0x9a1418, { size: 16, noise: 0.15, seed: 41 }), { rim: 0.6, wet: 1.4 }),
    canopy: mat4(grunge(0xd8d8d4, { size: 16, noise: 0.15, dark: 0.2, seed: 42 }), { rim: 0.6, wet: 1.2 }),
    pump: mat4(grunge(0xb01a1a, { size: 16, noise: 0.12, seed: 43 }), { shininess: 40, specular: 0x442222, rim: 0.7, wet: 1.4 }),
    pole: mat4(grunge(0x3a3a40, { size: 16, noise: 0.2, rust: 0.1, seed: 44 }), { rim: 0.7, wet: 1.2 }),
    bark: mat4(grunge(0x1a120e, { size: 16, noise: 0.25, seed: 45 }), { rim: 0.7, wet: 0.5 }),
    needle: mat4(grunge(0x0c1610, { size: 16, noise: 0.3, seed: 46 }), { rim: 0.8, wet: 0.8 }),
    curb: mat4(grunge(0x6a6a68, { size: 16, noise: 0.2, seed: 47 }), { rim: 0.5, wet: 1.4 }),
    dark: mat4(grunge(0x0c0c0e, { size: 8, noise: 0.1, seed: 48 }), { rim: 0.3 }),
  };
  for (let i = 0; i < 10; i++) M['p' + i] = mat4(productTex(i + 3), { rim: 0.5, wet: 0.4 });
  const b = new Batch(); const X0 = -4.5, X1 = 4.5, Z0 = -7, Z1 = 3.5, HH = 3.2;
  // murs, plafond (le sol est le réflecteur)
  b.add({ x: X0 - 0.1, y: HH / 2, z: (Z0 + Z1) / 2, w: 0.2, h: HH, d: Z1 - Z0, mat: 'wall', tpm: 0.6 }); b.add({ x: X1 + 0.1, y: HH / 2, z: (Z0 + Z1) / 2, w: 0.2, h: HH, d: Z1 - Z0, mat: 'wall', tpm: 0.6 });
  if (!RES) b.add({ x: 0, y: HH / 2, z: Z0 - 0.1, w: X1 - X0 + 0.4, h: HH, d: 0.2, mat: 'wall', tpm: 0.6 });
  else {   // doorway x 3.0..3.9, 2.25 m high
    b.add({ x: (X0 - 0.2 + 3.0) / 2, y: HH / 2, z: Z0 - 0.1, w: 3.0 - (X0 - 0.2), h: HH, d: 0.2, mat: 'wall', tpm: 0.6 }); b.add({ x: (3.9 + X1 + 0.2) / 2, y: HH / 2, z: Z0 - 0.1, w: X1 + 0.2 - 3.9, h: HH, d: 0.2, mat: 'wall', tpm: 0.6 });
    b.add({ x: 3.45, y: (2.25 + HH) / 2, z: Z0 - 0.1, w: 0.9, h: HH - 2.25, d: 0.2, mat: 'wall', tpm: 0.6 });
    for (const x of [2.97, 3.93]) b.add({ x, y: 1.125, z: Z0 - 0.1, w: 0.06, h: 2.25, d: 0.26, mat: 'frame' }); b.add({ x: 3.45, y: 2.28, z: Z0 - 0.1, w: 1.0, h: 0.06, d: 0.26, mat: 'frame' });
  }
  for (const x of [X0, X1]) b.add({ x: x + (x < 0 ? 0.02 : -0.02), y: 0.6, z: (Z0 + Z1) / 2, w: 0.04, h: 1.2, d: Z1 - Z0, mat: 'wallLow', tpm: 0.5 });
  b.add({ x: 0, y: HH + 0.05, z: (Z0 + Z1) / 2 + 2, w: X1 - X0 + 0.4, h: 0.1, d: Z1 - Z0 + 4, mat: 'ceil', tpm: 0.5 });
  // vitrine : montants + traverse + porte double au centre
  for (const x of [-4.5, -3.0, -1.5, -0.9, 0.9, 1.5, 3.0, 4.5]) b.add({ x, y: HH / 2, z: Z1, w: 0.1, h: HH, d: 0.12, mat: 'frame' });
  b.add({ x: 0, y: 0.08, z: Z1, w: 9.1, h: 0.16, d: 0.14, mat: 'frame' }); b.add({ x: 0, y: 2.45, z: Z1, w: 9.1, h: 0.1, d: 0.14, mat: 'frame' }); b.add({ x: 0, y: HH - 0.05, z: Z1, w: 9.1, h: 0.1, d: 0.14, mat: 'frame' });
  b.add({ x: 0, y: 1.1, z: Z1, w: 1.8, h: 0.06, d: 0.1, mat: 'frame' });
  // rayons : 3 îlots doubles + rayonnage mural gauche ; produits (certains rayons à moitié vides)
  const shelfUnit = (cx, z0, z1, depth, levels, sides, sparse) => {
    const L = z1 - z0, zc = (z0 + z1) / 2;
    b.add({ x: cx, y: 0.95, z: zc, w: 0.06, h: 1.9, d: L, mat: 'shelf' });
    for (const s of sides) { const xs = cx + s * depth / 2;
      for (let lv = 0; lv < levels; lv++) { const y = 0.12 + lv * 0.42; b.add({ x: cx + s * depth / 4, y, z: zc, w: depth / 2, h: 0.04, d: L, mat: 'shelf' }); b.add({ x: xs, y: y + 0.03, z: zc, w: 0.02, h: 0.07, d: L, mat: 'shelfEdge' });
        // produits
        let z = z0 + 0.08; while (z < z1 - 0.1) { const kind = r(); const w = 0.12 + r() * 0.16; if (r() < sparse) { z += w + 0.05; continue; }
          const pm = 'p' + Math.floor(r() * 10); const hgt = kind < 0.4 ? 0.22 + r() * 0.12 : kind < 0.7 ? 0.28 : 0.16 + r() * 0.1;
          if (kind < 0.7) b.add({ x: cx + s * (depth / 4 + 0.02), y: y + 0.02 + hgt / 2, z: z + w / 2, w: depth / 2 - 0.08, h: hgt, d: w, mat: pm, fit: true, ry: (r() - 0.5) * 0.1 });
          else { for (let k = 0; k < 2; k++) b.add({ x: cx + s * (depth / 4 - 0.04 + k * 0.12), y: y + 0.02 + 0.13, z: z + w / 2, w: 0.08, h: 0.26, d: 0.08, mat: pm, fit: true }); }
          z += w + 0.02; } }
      b.add({ x: xs, y: 1.95, z: zc, w: 0.04, h: 0.1, d: L, mat: 'shelfEdge' }); }
  };
  shelfUnit(-2.6, -5.6, -0.6, 0.8, 5, [-1, 1], 0.3); shelfUnit(-0.6, -5.6, -0.6, 0.8, 5, [-1, 1], 0.45); shelfUnit(1.4, -5.6, -1.6, 0.8, 5, [-1, 1], 0.35);
  shelfUnit(-4.3, -6.6, 2.0, 0.4, 5, [1], 0.25);
  // frigos du fond (portes vitrées éclairées)
  for (let i = 0; i < 5; i++) { const x = -3.4 + i * 1.3; b.add({ x, y: 1.05, z: Z0 + 0.35, w: 1.25, h: 2.1, d: 0.7, mat: 'fridge' }); for (let lv = 0; lv < 4; lv++) for (let k = 0; k < 6; k++) b.add({ x: x - 0.45 + k * 0.18, y: 0.35 + lv * 0.45, z: Z0 + 0.62, w: 0.1, h: 0.26, d: 0.1, mat: 'p' + Math.floor(r() * 10), fit: true }); }
  // comptoir + caisse
  b.add({ x: 3.3, y: 0.5, z: 1.2, w: 1.8, h: 1.0, d: 0.7, mat: 'counter' }); b.add({ x: 3.95, y: 0.5, z: -0.3, w: 0.7, h: 1.0, d: 2.4, mat: 'counter' });
  b.add({ x: 3.3, y: 1.03, z: 1.2, w: 1.9, h: 0.06, d: 0.8, mat: 'counterTop' }); b.add({ x: 3.95, y: 1.03, z: -0.3, w: 0.8, h: 0.06, d: 2.5, mat: 'counterTop' });
  b.add({ x: 3.5, y: 1.2, z: 1.15, w: 0.4, h: 0.3, d: 0.35, mat: 'dark' }); b.add({ x: 3.5, y: 1.42, z: 1.1, w: 0.36, h: 0.22, d: 0.04, mat: 'frame', rx: -0.3 });
  for (let i = 0; i < 6; i++) for (let k = 0; k < 4; k++) b.add({ x: 4.38, y: 1.35 + k * 0.22, z: -1.2 + i * 0.3, w: 0.12, h: 0.16, d: 0.24, mat: 'p' + Math.floor(r() * 10), fit: true });
  // façade extérieure (au-dessus de la vitrine) + enseigne, avancée du toit
  b.add({ x: 0, y: HH + 0.6, z: Z1 + 0.05, w: 9.6, h: 1.2, d: 0.3, mat: 'facade', tpm: 0.5 }); b.add({ x: 0, y: HH + 1.25, z: Z1 + 0.7, w: 10, h: 0.12, d: 1.6, mat: 'facade' });
  b.add({ x: 0, y: HH + 0.05, z: Z1 + 0.5, w: 9.6, h: 0.08, d: 1.0, mat: 'facadeRed' });
  b.add({ x: -6.2, y: 2.2, z: Z0 / 2 + 1, w: 3.4, h: 4.4, d: Z1 - Z0 + 1, mat: 'facade', tpm: 0.5 }); b.add({ x: 6.2, y: 2.2, z: Z0 / 2 + 1, w: 3.4, h: 4.4, d: Z1 - Z0 + 1, mat: 'facade', tpm: 0.5 });
  b.add({ x: 0, y: 0.06, z: Z1 + 0.6, w: 16, h: 0.12, d: 1.2, mat: 'curb' });
  // auvent + pompes
  b.add({ x: -11, y: 4.2, z: 12, w: 8, h: 0.5, d: 6, mat: 'canopy' }); b.add({ x: -11, y: 3.9, z: 12, w: 7.8, h: 0.1, d: 5.8, mat: 'facadeRed' });
  for (const [px, pz] of [[-13.5, 10], [-8.5, 10], [-13.5, 14], [-8.5, 14]]) b.add({ x: px, y: 2.0, z: pz, w: 0.3, h: 4.0, d: 0.3, mat: 'pole' });
  for (const px of [-12.5, -9.5]) { b.add({ x: px, y: 0.1, z: 12, w: 1.2, h: 0.2, d: 3, mat: 'curb' }); b.add({ x: px, y: 0.9, z: 12, w: 0.6, h: 1.6, d: 0.5, mat: 'pump' }); b.add({ x: px, y: 1.3, z: 12.26, w: 0.4, h: 0.3, d: 0.02, mat: 'dark' }); }
  // lampadaires
  const lamps = [V(-7, 0, 20), V(8, 0, 18), V(18, 0, 6)];
  for (const p of lamps) { b.add({ x: p.x, y: 3.2, z: p.z, w: 0.16, h: 6.4, d: 0.16, mat: 'pole' }); b.add({ x: p.x, y: 6.35, z: p.z - 0.5, w: 0.3, h: 0.14, d: 1.2, mat: 'pole' }); }
  // sapins sombres autour (derrière la boutique et au fond du parking)
  const trees = [];
  for (let i = 0; i < 46; i++) { const a = r(); let x, z; if (a < 0.5) { x = -26 + r() * 52; z = Z0 - 3 - r() * 22; } else { x = (r() < 0.5 ? -1 : 1) * (14 + r() * 16); z = -5 + r() * 40; } trees.push([x, z, 7 + r() * 8]); }
  for (let i = 0; i < 16; i++) trees.push([-30 + r() * 60, 30 + r() * 10, 8 + r() * 7]);
  const clear = opts.clear || []; for (const [x, z, h] of trees) { if (clear.some((c) => x > c[0] - 0.5 && x < c[2] + 0.5 && z > c[1] - 0.5 && z < c[3] + 0.5)) continue; b.add({ x, y: h / 2, z, w: 0.5, h, d: 0.5, mat: 'bark' }); for (let k = 0; k < 6; k++) { const y = h * 0.3 + k * h * 0.12, s = (1 - k / 6) * h * 0.38 + 0.4; b.add({ x, y, z, w: s, h: h * 0.08, d: s, mat: 'needle', ry: k * 0.4 }); } }
  b.build(M, group, { noCast: ['ceil', 'wall', 'facade', 'needle', 'bark', 'canopy', 'curb'] });
  // néons du plafond (panneaux), bande rouge au-dessus de la porte, enseigne, panneau SORTIE
  const panelM = []; const panels = [];
  for (const [x, z] of [[-2.6, -4.5], [-2.6, -1.0], [-0.6, -4.5], [-0.6, -1.0], [1.4, -4.0], [1.4, -0.6], [3.0, 1.5], [-2.0, 2.0], [0.8, 2.2]]) { const m = new THREE.MeshBasicMaterial({ color: new THREE.Color(2.8, 2.8, 3.0) }); panelM.push(m); const p = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.05, 1.3), m); p.position.set(x, HH - 0.03, z); group.add(p); panels.push({ local: V(x, HH - 0.4, z), pos: V() }); }
  const neonM = new THREE.MeshBasicMaterial({ color: new THREE.Color(7, 0.3, 0.25) }); const neon = new THREE.Mesh(new THREE.BoxGeometry(8.6, 0.06, 0.06), neonM); neon.position.set(0, 2.62, Z1 - 0.12); group.add(neon);
  const signM = new THREE.MeshBasicMaterial({ map: textTex('STATION 24/24'), color: new THREE.Color(2.6, 2.6, 2.6) }); const sign = new THREE.Mesh(new THREE.PlaneGeometry(5.2, 0.95), signM); sign.position.set(0, HH + 0.62, Z1 + 0.22); group.add(sign);
  const exitM = new THREE.MeshBasicMaterial({ map: textTex('SORTIE', { w: 256, h: 96, col: '#ffffff', bg: '#0a8a3a', font: '800 56px Inter, sans-serif' }), color: new THREE.Color(2.2, 2.2, 2.2) }); const exit = new THREE.Mesh(new THREE.PlaneGeometry(0.7, 0.26), exitM); exit.position.set(3.4, 2.5, Z0 + 0.02); if (!RES) group.add(exit);
  // porte de secours (fond, à droite)
  const backDoor = new THREE.Group(); backDoor.position.set(3.0, 0, Z0 + 0.03); if (!RES) group.add(backDoor); backDoor.add(vox([{ x: 0.45, y: 1.05, z: 0, w: 0.9, h: 2.1, d: 0.06, color: 0x6a6a70 }, { x: 0.8, y: 1.05, z: 0.06, w: 0.06, h: 0.06, d: 0.1, color: 0xd0d0d0 }, { x: 0.45, y: 1.1, z: 0.04, w: 0.8, h: 0.06, d: 0.06, color: 0xc01818 }], { rim: 0.6 }));
  const doorFrame = vox([{ x: 3.45, y: 1.1, z: Z0 + 0.02, w: 1.05, h: 2.25, d: 0.05, color: 0x2a2a2e }], { rim: 0.4 }); if (!RES) group.add(doorFrame);
  // vitrine : verre transparent ruisselant (des deux côtés) + traces de mains
  const glassM = glassOutMaterial({ tint: 0x10204a, glow: 0.2, drop: 0xd8e4ff }); glassM.side = THREE.DoubleSide;
  const panes = []; for (const [x0, x1] of [[-4.45, -3.05], [-2.95, -1.55], [-1.45, -0.95], [0.95, 1.45], [1.55, 2.95], [3.05, 4.45]]) { const p = new THREE.Mesh(new THREE.PlaneGeometry(x1 - x0, HH - 0.2), glassM); p.position.set((x0 + x1) / 2, HH / 2, Z1); group.add(p); panes.push(p); }
  const doorPanes = [-0.45, 0.45].map((x) => { const p = new THREE.Mesh(new THREE.PlaneGeometry(0.86, 2.3), glassM); p.position.set(x, 1.2, Z1 + 0.02); group.add(p); return p; });
  const hpM = handprintMaterial(5, 54); hpM.uniforms.uRep.value.set(2.6, 1.0); const hp = new THREE.Mesh(new THREE.PlaneGeometry(8.9, 2.9), hpM); hp.position.set(0, 1.55, Z1 - 0.03); hp.rotation.y = Math.PI; group.add(hp);
  // sol : carrelage mouillé dedans, bitume mouillé dehors (un seul plan réfléchissant chacun, même hauteur)
  const floorTex = tiles(0x1a1a1e, 0x2a2a30, { size: 32, n: 2, seed: 50, grout: 0x0a0a0c }); floorTex.wrapS = floorTex.wrapT = THREE.RepeatWrapping;
  const floorM = reflector.makeMaterial({ map: floorTex, color: 0xffffff, tpm: 0.6, reflect: 0.35, rough: 0.003, ripple: 0.0, tint: 0xffffff, glitter: 0.0, glitterCol: 0xff8a70 });
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(X1 - X0, Z1 - Z0), floorM); floor.rotation.x = -Math.PI / 2; floor.position.set(0, 0.02, (Z0 + Z1) / 2); group.add(floor);
  const asphTex = grunge(0x18181c, { size: 64, noise: 0.35, dark: 0.3, seed: 51, specks: 0.08, speckCol: 0x3a3a3e });
  const lotM = reflector.makeMaterial({ map: asphTex, color: 0xffffff, tpm: 0.35, reflect: 0.7, rough: 0.003, ripple: 1.0, tint: 0xffe0e0, glitter: 0.5, glitterCol: 0xff8a70 });
  const lot = new THREE.Mesh(new THREE.PlaneGeometry(90, 60), lotM); lot.rotation.x = -Math.PI / 2; lot.position.set(0, 0.02, Z1 + 30.05); group.add(lot);
  // lignes de parking
  const lines = new Batch(); for (let i = 0; i < 6; i++) lines.add({ x: 2 + i * 2.8, y: 0.03, z: 8, w: 0.1, h: 0.01, d: 4.5, mat: 'l' }); lines.build({ l: mat4(grunge(0xd8d8c8, { size: 8, noise: 0.3, seed: 52 }), { rim: 0.2 }) }, group, { cast: false });
  // débris au sol
  const deb = [...cansBoxes(r, 46, [-3.6, -6, 2.6, 2.8]), ...crateBoxes(-1.6, 0, 0.6, 0.4), ...crateBoxes(0.6, 0, -6.0, -0.2, 0x1a5a9a)];
  group.add(vox(deb, { phong: 50, spec: 0x553333, rim: 0.8, wet: 1.0, px: 1 / 32 }));
  // caméra, moniteur, voiture
  const cctv = buildCCTV(); cctv.g.position.set(-1.6, HH - 0.02, -6.75); group.add(cctv.g);
  const monitor = buildMonitor(ctx.renderer); monitor.g.position.set(3.0, 2.25, 0.35); monitor.g.rotation.y = -Math.PI / 2 - 0.35; group.add(monitor.g);
  const car = buildCar(0x2a0a0e); car.g.position.set(...(opts.carAt || [4.6, 8.2]).slice(0, 1), 0, (opts.carAt || [4.6, 8.2])[1]); car.g.rotation.y = Math.PI + 0.25; group.add(car.g);
  // ombre portée « quelqu'un » dans le rayon (visible seulement sur le moniteur)
  const st = {
    group, origin, panels, panelM, neonM, cctv, monitor, car, hp, hpM, glassM, backDoor, lamps, signM, exitM, Z0, Z1, HH, floor, lot,
    update(t) { glassM.uniforms.uTime.value = t; },
    // panneaux : k = 0 blanc froid, 1 rouge ; flick = scintillement
    setPanels(k, t, flick = 0) { panelM.forEach((m, i) => { const f = 1 - flick * ((Math.sin(t * 31 + i * 5) > 0.7 && Math.sin(t * 2.3 + i) > 0.3) ? 0.85 : 0); m.color.setRGB((2.8 + 1.6 * k) * f, (2.8 - 2.5 * k) * f, (3.0 - 2.7 * k) * f); }); },
    panelLights(k, i = 1.6, dist = 7) { const c = new THREE.Color().setRGB(1, 1 - 0.85 * k, 1 - 0.88 * k).getHex(); return panels.map((p) => ({ pos: p.pos, color: c, i, dist, decay: 1.4 })); },
    lampLights(i = 4) { return lamps.map((p) => ({ pos: p.clone().add(V(0, 6.0, -0.5)).add(origin), color: 0xffa050, i, dist: 16, decay: 1.2 })); },
    w(x, y, z) { return V(x, y, z).add(origin); },
  };
  for (const p of panels) p.pos.copy(p.local).add(origin);
  return st;
}
