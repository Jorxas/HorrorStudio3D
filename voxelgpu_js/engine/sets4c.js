// Décor v4 « forêt enneigée » : sol de neige en voxels (marches de 1/8 m, paillettes), sapins sombres chargés de
// neige, rochers et souches, buissons morts, lune carrée géante, lueur rouge qui « respire » au fond, traces de pas,
// silhouettes aux yeux rouges (humanoïdes sombres), mains qui sortent de la neige, trou qui s'ouvre (blocs qui tombent).
// Repère local : chemin le long de -z, de z = +12 à z = -60 ; sol vers y = 0.
import * as THREE from 'three';
import { Batch, mat4, grunge, rimify, voxify } from './kit4.js';
import { boxesGeometry } from './boxes.js';
import { mulberry } from './textures.js';
import { buildGraspHand } from './sets4.js';
const V = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
function hash2(x, z) { const s = Math.sin(x * 127.1 + z * 311.7) * 43758.5453; return s - Math.floor(s); }
function vnoise(x, z) { const xi = Math.floor(x), zi = Math.floor(z), xf = x - xi, zf = z - zi; const u = xf * xf * (3 - 2 * xf), v = zf * zf * (3 - 2 * zf);
  const a = hash2(xi, zi), b = hash2(xi + 1, zi), c = hash2(xi, zi + 1), d = hash2(xi + 1, zi + 1); return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v; }
export const pathX = (z) => Math.sin(z * 0.07) * 2.2 + Math.sin(z * 0.023 + 1) * 3;

// sol voxel : colonnes de CELL m, hauteurs quantifiées ; dessus + flancs visibles
function snowGround(heightAt, x0, x1, z0, z1, cell, q, skip = () => false) {
  const nx = Math.round((x1 - x0) / cell), nz = Math.round((z1 - z0) / cell); const H = new Float32Array((nx + 2) * (nz + 2));
  const hAt = (i, k) => H[(k + 1) * (nx + 2) + (i + 1)];
  for (let k = -1; k <= nz; k++) for (let i = -1; i <= nx; i++) { const x = x0 + (i + 0.5) * cell, z = z0 + (k + 0.5) * cell; H[(k + 1) * (nx + 2) + (i + 1)] = skip(x, z) ? -6 : Math.round(heightAt(x, z) / q) * q; }
  const pos = [], nor = [], col = []; const c0 = new THREE.Color();
  const quad = (a, b, c, d, n, sh) => { for (const p of [a, b, c, a, c, d]) { pos.push(...p); nor.push(...n); col.push(sh, sh, sh); } };
  for (let k = 0; k < nz; k++) for (let i = 0; i < nx; i++) {
    if (hAt(i, k) < -5) continue;
    const h = hAt(i, k), xa = x0 + i * cell, xb = xa + cell, za = z0 + k * cell, zb = za + cell; const sh = 0.93 + hash2(i * 1.3, k * 0.7) * 0.07;
    quad([xa, h, zb], [xb, h, zb], [xb, h, za], [xa, h, za], [0, 1, 0], sh);
    const nb = [[hAt(i + 1, k), [xb, 0, zb], [xb, 0, za], [1, 0, 0]], [hAt(i - 1, k), [xa, 0, za], [xa, 0, zb], [-1, 0, 0]], [hAt(i, k + 1), [xa, 0, zb], [xb, 0, zb], [0, 0, 1]], [hAt(i, k - 1), [xb, 0, za], [xa, 0, za], [0, 0, -1]]];
    for (const [hn, p1, p2, n] of nb) if (hn < h - 1e-4) quad([p1[0], hn, p1[2]], [p2[0], hn, p2[2]], [p2[0], h, p2[2]], [p1[0], h, p1[2]], n, sh * 0.86);
  }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3)); g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3)); g.computeBoundingSphere();
  return g;
}

// silhouette humanoïde sombre aux yeux rouges (squelette compatible anim.js)
export function buildShade4(buildCharacter4, seed = 1) {
  const ch = buildCharacter4({ skin: 0x16121a, brow: 0x0a080c, blush: false, top: { type: 'hoodie', color: 0x18141c }, pants: { color: 0x141018 }, shoes: { type: 'boot', color: 0x0c0a0e }, hair: null }, 50 + seed);
  ch.setExpr = () => {}; ch.faceUpdate = () => {}; ch.faceMat.map = null; ch.faceMat.color.set(0x16121a); ch.faceMat.needsUpdate = true;
  const eyeM = new THREE.MeshBasicMaterial({ color: new THREE.Color(9, 0.4, 0.25) });
  for (const sx of [-1, 1]) { const e = new THREE.Mesh(new THREE.BoxGeometry(0.09, 0.05, 0.02), eyeM); e.position.set(sx * 0.12, 4 / 16 + 0.03, 4 / 16 + 0.012); ch.neck.add(e); }
  ch.eyeM = eyeM; return ch;
}

export function buildForest(ctx, origin = V(400, 0, 0)) {
  const r = mulberry(61);
  const group = new THREE.Group(); group.position.copy(origin); ctx.scene.add(group);
  // relief : chemin creusé, bosses de neige, talus sur les côtés
  const heightAt = (x, z) => { const d = Math.abs(x - pathX(z)); const bank = Math.min(1, Math.max(0, (d - 1.6) / 6)); return 0.12 * vnoise(x * 0.9, z * 0.9) + bank * (0.7 + 0.9 * vnoise(x * 0.18 + 3, z * 0.18)) + 0.35 * vnoise(x * 0.35, z * 0.35) * bank; };
  const HZ = -30, HX = Math.round(pathX(HZ) * 2) / 2, HY = Math.round(heightAt(HX, HZ) / 0.125) * 0.125; const inHole = (x, z) => Math.abs(x - HX) < 2.0 && Math.abs(z - HZ) < 2.0;
  const snowM = voxify(rimify(new THREE.MeshLambertMaterial({ vertexColors: true, color: 0xdfe8ff }), 0.6, 3.0), { var: 0.07, levels: 4, px: 0.25 });
  const ground = new THREE.Mesh(snowGround((x, z) => inHole(x, z) ? HY : heightAt(x, z), -30, 30, -70, 16, 0.5, 0.125, inHole), snowM); ground.receiveShadow = true; group.add(ground);
  const farGround = new THREE.Mesh(new THREE.PlaneGeometry(400, 400), new THREE.MeshLambertMaterial({ color: 0xc8d4f0 })); farGround.rotation.x = -Math.PI / 2; farGround.position.y = -0.3; group.add(farGround);
  const M = {
    bark: mat4(grunge(0x2a1a14, { size: 16, noise: 0.3, dark: 0.3, seed: 62 }), { rim: 0.8, wet: 0.4 }),
    needle: mat4(grunge(0x0e1c18, { size: 16, noise: 0.35, dark: 0.2, seed: 63 }), { rim: 0.9, wet: 0.6 }),
    snow: mat4(grunge(0xeef4ff, { size: 16, noise: 0.08, seed: 64 }), { rim: 0.5, wet: 3.0 }),
    rock: mat4(grunge(0x2a2a30, { size: 16, noise: 0.3, dark: 0.3, seed: 65 }), { rim: 0.8, wet: 0.8 }),
    twig: mat4(grunge(0x1a1414, { size: 8, noise: 0.2, seed: 66 }), { rim: 0.8 }),
    print: mat4(grunge(0x8a9ac8, { size: 8, noise: 0.15, seed: 67 }), { rim: 0.2, wet: 0.5 }),
  };
  const b = new Batch();
  // sapins : tronc + étages de branches carrées dentelées + neige sur chaque étage
  const trees = [];
  const tree = (x, z, h, w) => {
    const gy = heightAt(x, z); trees.push(V(x, gy, z));
    b.add({ x, y: gy + h * 0.45, z, w: w * 0.12, h: h * 0.9, d: w * 0.12, mat: 'bark', tpm: 1 });
    const n = Math.round(h / 0.9);
    for (let k = 0; k < n; k++) { const t = k / n; const y = gy + h * 0.2 + t * h * 0.8; const R = w * 0.5 * (1 - t * 0.88) * (0.85 + r() * 0.3);
      b.add({ x, y, z, w: R * 0.9, h: 0.3, d: R * 0.9, mat: 'needle', ry: r() * 1.6 });
      const nb = 5 + Math.floor(r() * 3); const a0 = r() * 6.28;
      for (let j = 0; j < nb; j++) { const a = a0 + j / nb * 6.28 + (r() - 0.5) * 0.5; const L = R * (0.75 + r() * 0.5); const cx = x + Math.cos(a) * L * 0.55, cz = z + Math.sin(a) * L * 0.55; const ry = -a;
        b.add({ x: cx, y: y - 0.08 - L * 0.06, z: cz, w: L, h: 0.26, d: 0.34 + r() * 0.2, mat: 'needle', ry });
        b.add({ x: x + Math.cos(a) * L * 0.95, y: y - 0.2 - L * 0.08, z: z + Math.sin(a) * L * 0.95, w: 0.3, h: 0.24, d: 0.3, mat: 'needle', ry });
        if (r() < 0.75) b.add({ x: cx + Math.cos(a) * 0.05, y: y + 0.08 - L * 0.06, z: cz + Math.sin(a) * 0.05, w: L * (0.6 + r() * 0.3), h: 0.12, d: 0.3, mat: 'snow', ry }); }
      b.add({ x, y: y + 0.18, z, w: R * 0.6, h: 0.1, d: R * 0.6, mat: 'snow', ry: r() }); }
    b.add({ x, y: gy + h * 1.02, z, w: 0.2, h: 0.5, d: 0.2, mat: 'needle' });
  };
  for (let z = 14; z > -70; z -= 2.1) for (const side of [-1, 1]) { const px = pathX(z); const n = 1 + (r() < 0.35 ? 1 : 0); for (let i = 0; i < n; i++) { const d = 3.2 + r() * 9 + i * 5; tree(px + side * d, z + (r() - 0.5) * 1.4, 8 + r() * 9, 3.2 + r() * 2.4); } }
  for (let i = 0; i < 36; i++) { const z = -70 - r() * 50, x = (r() - 0.5) * 60; tree(x, z, 10 + r() * 10, 3.5 + r() * 2); }
  // rochers, souches, buissons morts
  for (let i = 0; i < 70; i++) { const z = 14 - r() * 80, side = r() < 0.5 ? -1 : 1, x = pathX(z) + side * (2.0 + r() * 5); const gy = heightAt(x, z); const s = 0.4 + r() * 1.0;
    if (r() < 0.5) { b.add({ x, y: gy + s * 0.4, z, w: s * 1.3, h: s * 0.9, d: s, mat: 'rock', ry: r() }); b.add({ x, y: gy + s * 0.88, z, w: s * 1.1, h: 0.14, d: s * 0.8, mat: 'snow', ry: r() }); }
    else for (let j = 0; j < 5; j++) { const a = r() * 6.28; b.add({ x: x + Math.cos(a) * 0.15, y: gy + 0.3, z: z + Math.sin(a) * 0.15, w: 0.04, h: 0.6 + r() * 0.4, d: 0.04, mat: 'twig', rx: (r() - 0.5) * 0.8, rz: (r() - 0.5) * 0.8 }); } }
  // traces de pas (petites, celles de Lina) le long du chemin
  const prints = [];
  for (let z = 10; z > -40; z -= 0.42) { const side = (Math.round(z / 0.42) % 2) ? 1 : -1; const x = pathX(z) + side * 0.12; const gy = heightAt(x, z); b.add({ x, y: gy + 0.005, z, w: 0.12, h: 0.02, d: 0.24, mat: 'print', ry: Math.atan(Math.cos(z * 0.07) * 0.154) }); prints.push(V(x, gy, z)); }
  b.build(M, group, { noCast: ['print'] });
  // lune carrée géante (pixels) + halo
  const mc = document.createElement('canvas'); mc.width = mc.height = 16; const mg = mc.getContext('2d'); for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { const v = 200 + hash2(x, y) * 55 - (hash2(x * 3, y * 7) > 0.8 ? 60 : 0); mg.fillStyle = `rgb(${v - 10},${v},${Math.min(255, v + 20)})`; mg.fillRect(x, y, 1, 1); }
  const mt = new THREE.CanvasTexture(mc); mt.magFilter = THREE.NearestFilter; mt.colorSpace = THREE.SRGBColorSpace;
  const moon = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ map: mt, color: new THREE.Color(1.7, 1.85, 2.3), fog: false })); group.add(moon);
  const halo = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.ShaderMaterial({ uniforms: { uCol: { value: new THREE.Color(0.18, 0.24, 0.55) } }, vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }', fragmentShader: 'uniform vec3 uCol; varying vec2 vUv; void main(){ float d = length(vUv - 0.5) * 2.0; gl_FragColor = vec4(uCol * pow(max(0.0, 1.0 - d), 2.5), 1.0); }', transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false })); group.add(halo);
  // ciel : dégradé + nuages sombres (sphère)
  const sky = new THREE.Mesh(new THREE.SphereGeometry(450, 32, 16), new THREE.ShaderMaterial({ side: THREE.BackSide, depthWrite: false, fog: false, uniforms: { uTop: { value: new THREE.Color(0x0a1230) }, uHor: { value: new THREE.Color(0x1a1a3a) }, uRed: { value: new THREE.Color(0x5a0a10) }, uRedK: { value: 1 } },
    vertexShader: 'varying vec3 vD; void main(){ vD = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }',
    fragmentShader: `uniform vec3 uTop, uHor, uRed; uniform float uRedK; varying vec3 vD; float h(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
      float n(vec2 p){ vec2 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f); return mix(mix(h(i), h(i+vec2(1,0)), f.x), mix(h(i+vec2(0,1)), h(i+vec2(1,1)), f.x), f.y); }
      void main(){ float y = max(vD.y, 0.0); vec3 c = mix(uHor, uTop, pow(y, 0.6)); vec2 q = vD.xz / max(vD.y, 0.08) * 1.5; float cl = n(q) * 0.6 + n(q * 2.3) * 0.4; c = mix(c, vec3(0.05, 0.06, 0.12), smoothstep(0.45, 0.8, cl) * 0.8);
        c += uRed * uRedK * pow(1.0 - y, 6.0) * smoothstep(0.3, -0.9, vD.z); float st = step(0.997, h(floor(vD.xy * 400.0 + vD.z * 77.0))) * smoothstep(0.1, 0.4, y); c += vec3(st * 1.5);
        gl_FragColor = vec4(c, 1.0); }` }));
  group.add(sky);
  // lueur rouge qui respire au fond (+ brume)
  const glowPos = V(pathX(-46), 1.5, -46);
  // silhouettes, mains, trou
  const shades = [];
  const hands = []; for (let i = 0; i < 14; i++) { const h = buildGraspHand(1.0 + r() * 0.4, 80 + i); group.add(h.g); h.g.visible = false; hands.push(h); }
  // trou : 8x8 blocs de neige qui s'effondrent + puits rouge
  const holeC = V(HX, HY, HZ);
  const blkG = new THREE.BoxGeometry(0.5, 0.5, 0.5); const blk = new THREE.InstancedMesh(blkG, M.snow, 64); blk.castShadow = true; group.add(blk); blk.visible = false;
  const blkInfo = []; for (let k = 0; k < 64; k++) blkInfo.push({ x: (k % 8 - 3.5) * 0.5, z: (Math.floor(k / 8) - 3.5) * 0.5, d: r(), sp: (r() - 0.5) * 4 });
  const pit = new THREE.Mesh(new THREE.BoxGeometry(4.2, 30, 4.2), new THREE.MeshBasicMaterial({ color: new THREE.Color(0.02, 0.0, 0.0), side: THREE.BackSide })); pit.position.copy(holeC).add(V(0, -15.2, 0)); group.add(pit); pit.visible = false;
  const pitGlow = new THREE.Mesh(new THREE.PlaneGeometry(4, 4), new THREE.MeshBasicMaterial({ color: new THREE.Color(6, 0.6, 0.1) })); pitGlow.rotation.x = -Math.PI / 2; pitGlow.position.copy(holeC).add(V(0, -24, 0)); group.add(pitGlow); pitGlow.visible = false;
  const m4 = new THREE.Matrix4(), q4 = new THREE.Quaternion(), e4 = new THREE.Euler(), s4 = V(1, 1, 1);
  const forest = {
    group, origin, heightAt, pathX, trees, prints, moon, halo, sky, shades, hands, holeC, blk, pit, pitGlow, glowPos,
    gy(x, z) { return heightAt(x - origin.x, z - origin.z) + origin.y; },
    // position monde d'un point du chemin
    at(z, dx = 0, dy = 0) { const x = pathX(z) + dx; return V(x, heightAt(x, z) + dy, z).add(origin); },
    update(t, S) { // lune : face à la caméra, loin dans le ciel
      const cam = S._cam; if (cam) { const dir = (S.moonDir ? V(...S.moonDir) : V(-0.25, 0.42, -1)).normalize(); const p = cam.clone().addScaledVector(dir, 300); moon.position.copy(p).sub(origin); moon.scale.setScalar(S.moonSize ?? 20); moon.lookAt(cam); halo.position.copy(moon.position).addScaledVector(dir, 2); halo.scale.setScalar((S.moonSize ?? 20) * 5); halo.lookAt(cam); sky.position.copy(cam).sub(origin); }
    },
    // effondrement : k 0 -> 1 (0 = sol intact)
    setHole(k, t) {
      const on = k > 0.001; blk.visible = true; pit.visible = on; pitGlow.visible = on;
      blkInfo.forEach((bi, i) => { const kk = Math.max(0, Math.min(1, (k - bi.d * 0.4) / 0.6)); const fall = kk * kk * 22; e4.set(kk * bi.sp, kk * bi.sp * 0.7, kk * bi.sp * 0.4); q4.setFromEuler(e4);
        m4.compose(V(holeC.x + bi.x, holeC.y - 0.25 - fall, holeC.z + bi.z), q4, s4); blk.setMatrixAt(i, m4); }); blk.instanceMatrix.needsUpdate = true;
    },
  };
  forest.setHole(0, 0);
  return forest;
}
