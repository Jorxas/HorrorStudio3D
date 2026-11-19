// Décors v4 (d'après les illustrations) : bus de nuit, supérette, forêt enneigée, abîme de lave, porte rouge.
// Chaque décor : { group, lights[], update(t,S), ... } placé à sa propre position dans le monde.
import * as THREE from 'three';
import { Batch, mat4, grunge, tiles, productTex, rimify, voxify } from './kit4.js';
import { boxesGeometry } from './boxes.js';
import { rainGlassMaterial } from './fx4.js';
import { mulberry } from './textures.js';
const V = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);

// ------------------------------------------------------------------ mains qui sortent du liquide (voxels sombres, mouillés)
export function buildGraspHand(scale = 1, seed = 1) {
  // avant-bras 3x3 voxels, paume 4x4x2, quatre doigts écartés (2 phalanges) + pouce ; matière noire mouillée
  const r = mulberry(seed); const g = new THREE.Group(); const k = 0.045 * scale;
  const mat = voxify(rimify(new THREE.MeshPhongMaterial({ vertexColors: true, shininess: 40, specular: 0x1a0c0c }), 1.2, 1.0), { var: 0.18, levels: 4, px: k });
  const col = () => new THREE.Color(0x342c38).multiplyScalar(0.7 + r() * 0.6);
  const B = [];
  for (let y = -11; y < 0; y++) { const tp = y > -3 ? 0.88 : 1.0; for (let x = -1; x <= 1; x++) for (let z = -1; z <= 1; z++) if (!(Math.abs(x) === 1 && Math.abs(z) === 1 && r() < 0.5)) B.push({ x: x * k * tp, y: (y + 0.5) * k, z: z * k * tp, w: k * 1.02, h: k * 1.02, d: k * 1.02, color: col() }); }
  for (let y = 0; y < 4; y++) for (let x = -1.5; x <= 1.5; x++) for (const z of [-0.5, 0.5]) B.push({ x: x * k, y: (y + 0.5) * k, z: z * k * 0.9, w: k, h: k, d: k * 0.92, color: col() });
  const armM = new THREE.Mesh(boxesGeometry(B), mat); armM.castShadow = true; g.add(armM);
  const fingers = [];
  const finger = (x, y, l1, l2, rz = 0, w = 0.9) => {
    const f = new THREE.Group(); f.position.set(x * k, y * k, 0); f.rotation.z = rz; g.add(f);
    const s1 = new THREE.Mesh(boxesGeometry([{ x: 0, y: l1 * 0.5 * k, z: 0, w: k * w, h: l1 * k, d: k * w, color: col() }]), mat); f.add(s1);
    const j = new THREE.Group(); j.position.y = l1 * k; f.add(j);
    const s2 = new THREE.Mesh(boxesGeometry([{ x: 0, y: l2 * 0.5 * k, z: 0, w: k * w * 0.92, h: l2 * k, d: k * w * 0.92, color: col() }, { x: 0, y: (l2 - 0.2) * k, z: k * 0.3, w: k * 0.6, h: k * 0.35, d: k * 0.3, color: 0x4a1010 }]), mat); j.add(s2);
    s1.castShadow = s2.castShadow = true; return { f, j, rz };
  };
  for (let i = 0; i < 4; i++) fingers.push(finger(-1.5 + i, 4, [2.2, 2.6, 2.5, 1.9][i], [2.0, 2.2, 2.1, 1.7][i]));
  const th = finger(-1.9, 1.3, 1.8, 1.5, 0.6, 1.0);
  return { g, fingers, set(curl, spread = 0.25) { fingers.forEach(({ f, j }, i) => { f.rotation.set(curl * 0.7, 0, -(i - 1.5) * spread); j.rotation.set(curl * 1.0, 0, 0); }); th.f.rotation.set(curl * 0.3, 0, 0.45 + spread * 0.8); th.j.rotation.set(curl * 0.5, 0, -0.25); } };
}

// silhouette sombre aux yeux rouges
export function buildShade(seed = 1, h = 1.9) {
  const r = mulberry(seed); const g = new THREE.Group(); const B = []; const k = h / 30;
  const col = () => new THREE.Color(0x0e0a0c).multiplyScalar(0.7 + r() * 0.6);
  for (let y = 0; y < 30; y += 1.5) { const w = y > 22 ? 5 : y > 12 ? 7 : 4.5; for (let x = -w / 2; x <= w / 2; x += 1.5) if (r() < 0.92) B.push({ x: x * k + (r() - 0.5) * k, y: y * k, z: (r() - 0.5) * 2 * k, w: 1.6 * k, h: 1.6 * k, d: 3 * k, color: col() }); }
  const m = new THREE.Mesh(boxesGeometry(B), rimify(new THREE.MeshLambertMaterial({ vertexColors: true }), 0.8)); m.castShadow = true; g.add(m);
  const eyeM = new THREE.MeshBasicMaterial({ color: new THREE.Color(6, 0.3, 0.2) });
  for (const sx of [-1, 1]) { const e = new THREE.Mesh(new THREE.BoxGeometry(0.9 * k, 0.6 * k, 0.4 * k), eyeM); e.position.set(sx * 1.1 * k, 26.5 * k, 1.6 * k); g.add(e); }
  return { g, eyeM };
}

// ------------------------------------------------------------------ bus de nuit (intérieur + carrosserie extérieure, porte, poste de conduite)
// repère local : x ∈ [-1.5, 1.5], plancher y = 0, avant (chauffeur) en z = -13, arrière en z = +0.6. Roues : sol à y = -0.95.
// bus.place(pos, yaw) déplace tout (lumières, sièges, barres recalculés en coordonnées monde).
function signTex(text) {
  const c = document.createElement('canvas'); c.width = 256; c.height = 32; const g = c.getContext('2d'); g.fillStyle = '#080402'; g.fillRect(0, 0, 256, 32);
  g.font = '700 22px Inter, sans-serif'; g.textBaseline = 'middle'; g.fillStyle = '#ffae2a'; g.fillText(text, 10, 17);
  const im = g.getImageData(0, 0, 256, 32); for (let y = 0; y < 32; y++) for (let x = 0; x < 256; x++) if (x % 2 || y % 2) { const i = (y * 256 + x) * 4; im.data[i] *= 0.25; im.data[i + 1] *= 0.25; im.data[i + 2] *= 0.25; }
  g.putImageData(im, 0, 0); const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.magFilter = THREE.NearestFilter; return t;
}
export function glassOutMaterial(o = {}) {
  return new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 }, uTint: { value: new THREE.Color(o.tint ?? 0xff2a1a) }, uGlow: { value: o.glow ?? 1.0 }, uDrop: { value: new THREE.Color(o.drop ?? 0xffd0c8) } },
    vertexShader: `varying vec2 vUv; varying vec3 vW; void main(){ vUv = uv; vW = (modelMatrix * vec4(position,1.0)).xyz; gl_Position = projectionMatrix * viewMatrix * vec4(vW, 1.0); }`,
    fragmentShader: `uniform float uTime, uGlow; uniform vec3 uTint, uDrop; varying vec2 vUv; varying vec3 vW;
      float h(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
      void main(){ vec2 p = vec2(vW.x + vW.z, vW.y) * 8.0;
        float lane = floor(p.x * 0.7); float sp = 0.6 + h(vec2(lane, 1.0)) * 1.4; float yy = fract(p.y * 0.06 + uTime * sp * 0.25 + h(vec2(lane, 3.0)));
        float streak = step(0.7, h(vec2(lane, 7.0))) * smoothstep(0.2, 0.0, abs(fract(p.x * 0.7) - 0.5) - 0.1) * smoothstep(0.0, 0.5, yy) * (1.0 - smoothstep(0.85, 1.0, yy));
        vec2 c = floor(p * 2.6); vec2 fc = fract(p * 2.6) - 0.5; float drop = step(0.92, h(c + floor(uTime * 0.3 + h(c) * 5.0) * 0.01)) * (0.4 + 0.6 * h(c + 9.0)) * smoothstep(0.42, 0.18, length(fc));
        vec3 col = uTint * uGlow * (0.55 + 0.45 * smoothstep(0.0, 1.0, vUv.y)) + uDrop * (streak * 0.5 + drop * 0.7) * (0.3 + uGlow * 0.7);
        gl_FragColor = vec4(col, 0.32 + 0.4 * (streak + drop)); }`,
    transparent: true, depthWrite: false,
  });
}
export function buildBus(ctx, origin = V(0, 0, 0)) {
  const { reflector } = ctx; const r = mulberry(11);
  const group = new THREE.Group(); group.position.copy(origin); ctx.scene.add(group);
  const M = {
    seat: mat4(grunge(0x26304e, { size: 32, noise: 0.3, dark: 0.35, seed: 1, specks: 0.06, speckCol: 0x0a0a0e }), { rim: 0.45, wet: 1.4 }),
    seatEdge: mat4(grunge(0x2a1a1c, { size: 16, noise: 0.2, seed: 2 }), { rim: 0.4 }),
    pole: mat4(grunge(0xe8a820, { size: 16, noise: 0.15, dark: 0.25, rust: 0.22, rustCol: 0x6a1a0a, seed: 3 }), { shininess: 50, specular: 0x664422, rim: 0.5 }),
    wall: mat4(grunge(0x4a1a1a, { size: 32, noise: 0.25, dark: 0.35, rust: 0.05, seed: 4, specks: 0.04, speckCol: 0x120404 }), { rim: 0.25, wet: 0.8 }),
    ceil: mat4(grunge(0x3a1a1c, { size: 32, noise: 0.3, dark: 0.4, seed: 5, specks: 0.06, speckCol: 0x0a0202 }), { rim: 0.2 }),
    frame: mat4(grunge(0x1c181e, { size: 16, noise: 0.2, seed: 6 }), { shininess: 30, specular: 0x331111, rim: 0.35 }),
    btn: mat4(grunge(0xc01818, { size: 8, noise: 0.1, seed: 7 }), { emissive: 0x500000, rim: 0.3 }),
    tube: new THREE.MeshBasicMaterial({ color: new THREE.Color(5.5, 1.2, 1.0) }),
    floor: mat4(grunge(0x141014, { size: 32, noise: 0.3, seed: 8 })),
    body: mat4(grunge(0x1c2c3e, { size: 32, noise: 0.22, dark: 0.3, rust: 0.06, rustCol: 0x5a2a12, seed: 9, specks: 0.03, speckCol: 0x0a0a10 }), { shininess: 60, specular: 0x334455, rim: 0.7, wet: 1.6 }),
    stripe: mat4(grunge(0xb01818, { size: 16, noise: 0.15, rust: 0.05, seed: 10 }), { shininess: 60, specular: 0x442222, rim: 0.7, wet: 1.6 }),
    under: mat4(grunge(0x0c0c0e, { size: 16, noise: 0.2, seed: 12 }), { rim: 0.4 }),
    tire: mat4(grunge(0x101012, { size: 16, noise: 0.25, seed: 13 }), { rim: 0.6, wet: 1.2 }),
    hub: mat4(grunge(0x8a8a90, { size: 8, noise: 0.2, rust: 0.2, seed: 14 }), { shininess: 60, specular: 0x666666, rim: 0.6 }),
    dash: mat4(grunge(0x18181c, { size: 16, noise: 0.2, seed: 15 }), { rim: 0.4 }),
    uniform: mat4(grunge(0x14161c, { size: 16, noise: 0.2, seed: 16 }), { rim: 0.9 }),
  };
  const b = new Batch(); const L = 13, Wd = 3.0, Hh = 2.4, DZ0 = -12.6, DZ1 = -11.3; // porte (côté +x)
  // plancher, plafond, murs bas / haut (coupés à la porte), montants de fenêtres
  b.add({ x: 0, y: -0.05, z: -L / 2, w: Wd, h: 0.1, d: L + 1.2, mat: 'floor', tpm: 1.2 });
  b.add({ x: 0, y: Hh + 0.05, z: -L / 2, w: Wd, h: 0.1, d: L + 1.2, mat: 'ceil', tpm: 1.2 });
  const wallRun = (sx, z0, z1) => { const d = z1 - z0, zc = (z0 + z1) / 2; b.add({ x: sx * (Wd / 2 + 0.05), y: 0.48, z: zc, w: 0.1, h: 0.96, d, mat: 'wall', tpm: 1.2 }); b.add({ x: sx * (Wd / 2 + 0.05), y: 2.17, z: zc, w: 0.1, h: 0.46, d, mat: 'wall', tpm: 1.2 });
    b.add({ x: sx * (Wd / 2 + 0.01), y: 0.97, z: zc, w: 0.14, h: 0.06, d, mat: 'frame' }); b.add({ x: sx * (Wd / 2 + 0.01), y: 1.95, z: zc, w: 0.14, h: 0.06, d, mat: 'frame' }); };
  wallRun(-1, -L, 0.6); wallRun(1, DZ1, 0.6); wallRun(1, -L, DZ0);
  for (const sx of [-1, 1]) {
    b.add({ x: sx * (Wd / 2 - 0.12), y: Hh - 0.12, z: -L / 2, w: 0.3, h: 0.12, d: L, mat: 'ceil', tpm: 1.2, rz: sx * 0.6 });
    for (let z = 0; z >= -L; z -= 1.3) if (!(sx > 0 && z < DZ1 && z > DZ0)) b.add({ x: sx * (Wd / 2 + 0.02), y: 1.45, z, w: 0.12, h: 1.0, d: 0.12, mat: 'frame' });
    b.add({ x: sx * 0.52, y: 2.06, z: -L / 2 + 1, w: 0.05, h: 0.05, d: L - 2, mat: 'pole', tpm: 2 });
  }
  b.add({ x: 0, y: Hh / 2, z: 0.65, w: Wd, h: Hh, d: 0.1, mat: 'wall', tpm: 1.2 });
  // poste de conduite : cloison, tableau de bord, siège du chauffeur, volant
  b.add({ x: -0.75, y: 0.55, z: -10.95, w: 1.4, h: 1.1, d: 0.06, mat: 'frame' });
  b.add({ x: 0, y: 0.75, z: -12.75, w: Wd - 0.1, h: 0.5, d: 0.5, mat: 'dash', tpm: 1.5 });
  b.add({ x: -0.85, y: 0.45, z: -11.75, w: 0.6, h: 0.12, d: 0.55, mat: 'seat' }); b.add({ x: -0.85, y: 0.85, z: -11.45, w: 0.6, h: 0.75, d: 0.1, mat: 'seat' });
  b.add({ x: -0.85, y: 1.02, z: -12.32, w: 0.5, h: 0.06, d: 0.06, mat: 'frame', rx: 0.5 }); b.add({ x: -0.85, y: 0.95, z: -12.45, w: 0.06, h: 0.25, d: 0.06, mat: 'frame', rx: 0.5 });
  // sièges par paires (pas dans la cabine)
  const seats = [];
  for (let z = -1.4; z > -10.6; z -= 0.92) for (const sx of [-1, 1]) {
    const cx = sx * 0.98;
    b.add({ x: cx, y: 0.38, z, w: 0.84, h: 0.11, d: 0.46, mat: 'seat', tpm: 0.9 });
    b.add({ x: cx, y: 0.7, z: z + 0.26, w: 0.84, h: 0.58, d: 0.11, mat: 'seat', tpm: 0.9, rx: 0.12 });
    b.add({ x: cx, y: 1.0, z: z + 0.3, w: 0.86, h: 0.07, d: 0.16, mat: 'seatEdge' });
    b.add({ x: cx - sx * 0.3, y: 0.16, z, w: 0.05, h: 0.32, d: 0.05, mat: 'frame' });
    seats.push({ local: V(cx, 0.42, z), pos: V() });
  }
  // carrosserie extérieure
  const X = Wd / 2 + 0.16;
  for (const sx of [-1, 1]) {
    const run = (z0, z1) => { const d = z1 - z0, zc = (z0 + z1) / 2; b.add({ x: sx * X, y: 0.2, z: zc, w: 0.08, h: 1.5, d, mat: 'body', tpm: 1 }); b.add({ x: sx * (X + 0.01), y: 0.72, z: zc, w: 0.08, h: 0.14, d, mat: 'stripe', tpm: 1 }); b.add({ x: sx * X, y: 2.28, z: zc, w: 0.08, h: 0.62, d, mat: 'body', tpm: 1 }); };
    if (sx > 0) { run(DZ1, 0.75); run(-L - 0.15, DZ0); b.add({ x: X, y: 2.28, z: (DZ0 + DZ1) / 2, w: 0.08, h: 0.62, d: DZ1 - DZ0, mat: 'body' }); } else run(-L - 0.15, 0.75);
    for (let z = 0.2; z >= -L; z -= 1.3) if (!(sx > 0 && z < DZ1 + 0.1 && z > DZ0 - 0.1)) b.add({ x: sx * (X + 0.02), y: 1.47, z, w: 0.1, h: 1.0, d: 0.1, mat: 'body' });
    b.add({ x: sx * (X - 0.02), y: -0.42, z: -L / 2 + 0.3, w: 0.06, h: 0.26, d: L + 0.8, mat: 'under' });
    for (const wz of [-10.6, -1.6]) { b.add({ x: sx * (X - 0.12), y: -0.47, z: wz, w: 0.36, h: 0.96, d: 0.96, mat: 'tire' }); b.add({ x: sx * (X + 0.06), y: -0.47, z: wz, w: 0.04, h: 0.42, d: 0.42, mat: 'hub' }); }
  }
  b.add({ x: 0, y: 2.62, z: -L / 2 + 0.3, w: 2 * X + 0.08, h: 0.12, d: L + 1.0, mat: 'body', tpm: 1 });
  b.add({ x: 0, y: -0.3, z: -L / 2 + 0.3, w: 2 * X, h: 0.5, d: L + 0.8, mat: 'under' });
  b.add({ x: 0, y: 0.25, z: -L - 0.2, w: 2 * X + 0.08, h: 1.4, d: 0.1, mat: 'body' }); b.add({ x: 0, y: 0.72, z: -L - 0.26, w: 2 * X + 0.1, h: 0.14, d: 0.06, mat: 'stripe' });
  b.add({ x: 0, y: 2.48, z: -L - 0.2, w: 2 * X + 0.08, h: 0.36, d: 0.1, mat: 'body' }); b.add({ x: 0, y: -0.38, z: -L - 0.28, w: 2 * X, h: 0.18, d: 0.12, mat: 'hub' });
  b.add({ x: 0, y: 0.6, z: 0.8, w: 2 * X + 0.08, h: 2.3, d: 0.1, mat: 'body' }); b.add({ x: 0, y: 2.2, z: 0.8, w: 2 * X + 0.08, h: 0.8, d: 0.1, mat: 'body' }); b.add({ x: 0, y: 0.72, z: 0.86, w: 2 * X + 0.1, h: 0.14, d: 0.06, mat: 'stripe' });
  b.build(M, group, { noCast: ['wall', 'ceil', 'floor', 'frame', 'body', 'under', 'stripe'] });
  // barres jaunes verticales (alternées) + boutons d'arrêt — maillages séparés pour pouvoir les masquer
  const poles = []; let pk = 0;
  for (let z = -1.0; z > -10.6; z -= 1.84) {
    const sx = (pk++ % 2) ? 1 : -1, px = sx * 0.52; const pb = new Batch(); pb.add({ x: 0, y: Hh / 2, z: 0, w: 0.065, h: Hh, d: 0.065, mat: 'pole', tpm: 2.5 });
    if (r() < 0.6) pb.add({ x: 0, y: 1.45, z: 0, w: 0.1, h: 0.14, d: 0.1, mat: 'btn' });
    const pg = new THREE.Group(); pg.position.set(px, 0, z - 0.05); group.add(pg); pb.build(M, pg); poles.push({ local: V(px, 0, z - 0.05), pos: V(), mesh: pg });
  }
  // néons du plafond
  const tubes = []; const tubeMats = [];
  for (let i = 0; i < 6; i++) { const z = -0.9 - i * 2.0; const mt = M.tube.clone(); tubeMats.push(mt); const t = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.05, 1.3), mt); t.position.set(0, Hh - 0.03, z); group.add(t); const h = new THREE.Mesh(new THREE.BoxGeometry(0.26, 0.06, 1.42), M.frame); h.position.set(0, Hh, z); group.add(h); tubes.push({ local: V(0, Hh - 0.25, z), pos: V() }); }
  // vitres ruisselantes (intérieur) + vitres extérieures transparentes (on voit l'intérieur éclairé)
  const glass = rainGlassMaterial({ out: 0x1a0204, out2: 0x6a0a0c, drop: 0xffc8c0 });
  const glassOut = glassOutMaterial({ tint: 0xffe8d8, glow: 0.35 });
  const winSeg = (sx, z0, z1, inner) => { const d = z1 - z0; const g = new THREE.Mesh(new THREE.PlaneGeometry(d, 0.98), inner ? glass : glassOut); g.position.set(sx * (inner ? Wd / 2 + 0.06 : X + 0.05), 1.46, (z0 + z1) / 2); g.rotation.y = inner ? -sx * Math.PI / 2 : sx * Math.PI / 2; group.add(g); return g; };
  for (const inner of [true, false]) { winSeg(-1, -L, 0.6, inner); winSeg(1, DZ1, 0.6, inner); winSeg(1, -L, DZ0, inner); }
  const wsIn = new THREE.Mesh(new THREE.PlaneGeometry(Wd - 0.1, 1.25), glass); wsIn.position.set(0, 1.62, -L - 0.12); group.add(wsIn);
  const wsOut = new THREE.Mesh(new THREE.PlaneGeometry(2 * X, 1.25), glassOut); wsOut.position.set(0, 1.62, -L - 0.27); wsOut.rotation.y = Math.PI; group.add(wsOut);
  const back = new THREE.Mesh(new THREE.PlaneGeometry(1.8, 0.9), glass); back.position.set(0, 1.5, 0.59); back.rotation.y = Math.PI; group.add(back);
  // porte : deux vantaux vitrés qui glissent
  const doorM = mat4(grunge(0x1c2c3e, { size: 16, noise: 0.2, seed: 17 }), { shininess: 60, specular: 0x334455, rim: 0.7 });
  const doors = [0, 1].map((i) => { const dg = new THREE.Group(); const dd = (DZ1 - DZ0) / 2; const db = new Batch(); db.add({ x: 0, y: 0.25, z: 0, w: 0.06, h: 1.55, d: dd, mat: 'd' }); db.add({ x: 0, y: 2.05, z: 0, w: 0.06, h: 0.15, d: dd, mat: 'd' }); db.add({ x: 0, y: 1.45, z: 0, w: 0.06, h: 1.1, d: 0.05, mat: 'd' }); db.build({ d: doorM }, dg);
    const pane = new THREE.Mesh(new THREE.PlaneGeometry(dd * 0.9, 0.95), glassOut); pane.rotation.y = Math.PI / 2; pane.position.set(0.035, 1.47, 0); dg.add(pane);
    dg.position.set(X, 0, DZ0 + dd * (i + 0.5)); group.add(dg); return { g: dg, z0: DZ0 + dd * (i + 0.5), dir: i ? 1 : -1, dd }; });
  // chauffeur (silhouette sombre, casquette, ne se retourne jamais)
  const drv = new Batch(); const U = 'u';
  drv.add({ x: 0, y: 0.75, z: 0, w: 0.5, h: 0.62, d: 0.3, mat: U }); drv.add({ x: 0, y: 1.22, z: -0.02, w: 0.36, h: 0.36, d: 0.34, mat: U, color: 0x8a6a5a });
  drv.add({ x: 0, y: 1.42, z: -0.03, w: 0.4, h: 0.1, d: 0.38, mat: U }); drv.add({ x: 0, y: 1.39, z: -0.24, w: 0.34, h: 0.04, d: 0.14, mat: U });
  for (const sx of [-1, 1]) drv.add({ x: sx * 0.3, y: 0.9, z: -0.25, w: 0.13, h: 0.13, d: 0.5, mat: U, rx: 0.3 });
  const driver = new THREE.Group(); driver.position.set(-0.85, 0, -11.75); drv.build({ u: M.uniform }, driver); group.add(driver);
  // panneau de destination + phares + feux arrière
  const signM = new THREE.MeshBasicMaterial({ map: signTex('13   DERNIER BUS'), color: new THREE.Color(2.2, 2.2, 2.2) });
  const sign = new THREE.Mesh(new THREE.PlaneGeometry(2.4, 0.3), signM); sign.position.set(0, 2.45, -L - 0.26); sign.rotation.y = Math.PI; group.add(sign);
  const headM = new THREE.MeshBasicMaterial({ color: new THREE.Color(6, 5.6, 4.6) }), tailM = new THREE.MeshBasicMaterial({ color: new THREE.Color(5, 0.25, 0.2) });
  for (const sx of [-1, 1]) { const hl = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.22, 0.05), headM); hl.position.set(sx * 1.2, 0.05, -L - 0.27); group.add(hl); const tl = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.5, 0.05), tailM); tl.position.set(sx * 1.45, 0.4, 0.87); group.add(tl); }
  const dashM = new THREE.MeshBasicMaterial({ color: new THREE.Color(0.3, 1.6, 2.4) }); for (let i = 0; i < 5; i++) { const d = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.03, 0.01), dashM); d.position.set(-1.1 + i * 0.12, 1.01, -12.49); group.add(d); }
  // flaque noire réfléchissante (niveau variable)
  const liquidMat = reflector.makeMaterial({ color: 0x1a0306, reflect: 1.1, rough: 0.002, ripple: 0.7, tint: 0xffd8d8, glitter: 0.35, glitterCol: 0xff6a50 });
  const liquid = new THREE.Mesh(new THREE.PlaneGeometry(Wd, L), liquidMat); liquid.rotation.x = -Math.PI / 2; liquid.position.set(0, 0.02, -L / 2); group.add(liquid);
  // mains
  const hands = []; for (let i = 0; i < 26; i++) { const h = buildGraspHand(0.9 + r() * 0.5, i + 3); group.add(h.g); h.g.visible = false; hands.push({ ...h, x: (r() - 0.5) * 2.3, z: -1.2 - r() * 9.5, delay: r(), yaw: r() * 6.28 }); }
  const lights = tubes.map((p) => ({ pos: p.pos, color: 0xff2414, i: 5, dist: 7 }));
  const bus = {
    group, origin, seats, poles, tubes, tubeMats, glass, glassOut, liquid, liquidMat, hands, L, Wd, Hh, lights, doors, driver, headM, tailM, signM, X,
    update(t, S) { glass.uniforms.uTime.value = t; glassOut.uniforms.uTime.value = t; },
    showPoles(hide = []) { poles.forEach((p, i) => { p.mesh.visible = !hide.includes(i); }); },
    // niveau des tubes : 0 = blanc froid, 1 = rouge ; k peut être un tableau (un niveau par tube)
    setTubes(k, t) { tubeMats.forEach((m, i) => { const ki = Array.isArray(k) ? k[i] : k; const fl = 0.85 + 0.15 * Math.sin(t * 40 + i * 7) * (Math.sin(t * 3 + i) > 0.8 ? 1 : 0); m.color.setRGB((2.2 + 3.3 * ki) * fl, (2.1 - 1.0 * ki) * fl, (2.4 - 1.5 * ki) * fl); }); },
    tubeLights(k, t, i = 2.2, dist = 6) { return tubes.map((p, n) => { const ki = Array.isArray(k) ? k[n] : k; const c = new THREE.Color().setRGB(0.85 + 0.15 * ki, 0.85 - 0.72 * ki, 0.9 - 0.82 * ki); return { pos: p.pos, color: c.getHex(), i, dist, decay: 1.3 }; }); },
    setDoor(open) { doors.forEach((d) => { d.g.position.z = d.z0 + d.dir * d.dd * 0.95 * open; }); },
    setWindows(col, glow) { glassOut.uniforms.uTint.value.set(col); glassOut.uniforms.uGlow.value = glow; },
    place(pos = V(), yaw = 0) {
      group.position.copy(pos); group.rotation.set(0, yaw, 0); group.updateMatrixWorld(true);
      for (const a of [seats, poles, tubes]) for (const e of a) e.pos.copy(e.local).applyMatrix4(group.matrixWorld);
    },
    // point du bus (repère local) -> monde
    w(x, y, z) { return V(x, y, z).applyMatrix4(group.matrixWorld); },
  };
  bus.place(origin, 0);
  return bus;
}
