// Décor v4 « abîme de lave » + « porte » : lac de lave animé, corniche d'atterrissage, colonnes de basalte à franchir,
// falaises noires et cascades de lave, stalactites, château gothique et pont au loin, fumées ; puis escalier de blocs
// flottants suspendus à des chaînes jusqu'à la plateforme de la porte (piliers à runes, dalles aux joints lumineux,
// porte géante à emblème), blocs à la dérive, silhouettes aux yeux rouges sur les blocs.
// Repère local : lave en y = 0 ; corniche autour de (0, 1.5, 0) ; colonnes vers -z ; porte vers (0, 30, -62).
import * as THREE from 'three';
import { Batch, mat4, grunge, rimify } from './kit4.js';
import { boxesGeometry } from './boxes.js';
import { mulberry } from './textures.js';
const V = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);

const NOISE = `float h21(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
  float vn(vec2 p){ vec2 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f); return mix(mix(h21(i), h21(i+vec2(1,0)), f.x), mix(h21(i+vec2(0,1)), h21(i+vec2(1,1)), f.x), f.y); }
  float fbm(vec2 p){ float a = 0.5, s = 0.0; for (int i = 0; i < 4; i++) { s += a * vn(p); p *= 2.07; a *= 0.5; } return s; }
  vec3 lavaRamp(float v){ vec3 c = mix(vec3(0.03, 0.006, 0.004), vec3(1.2, 0.1, 0.015), smoothstep(0.4, 0.56, v)); c = mix(c, vec3(3.2, 0.75, 0.06), smoothstep(0.56, 0.72, v)); return mix(c, vec3(5.0, 2.6, 0.7), smoothstep(0.8, 0.95, v)); }`;
export function lavaMaterial({ fall = false, k = 1 } = {}) {
  return new THREE.ShaderMaterial({ uniforms: { uTime: { value: 0 }, uK: { value: k } },
    vertexShader: 'varying vec3 vW; varying vec2 vUv; void main(){ vUv = uv; vW = (modelMatrix * vec4(position,1.0)).xyz; gl_Position = projectionMatrix * viewMatrix * vec4(vW,1.0); }',
    fragmentShader: `uniform float uTime, uK; varying vec3 vW; varying vec2 vUv; ${NOISE}
      void main(){ ${fall ? 'vec2 p = vec2((vW.x + vW.z) * 0.9, vW.y * 0.35 + uTime * 1.6); float v = fbm(p * vec2(3.0, 1.0)) * 0.7 + 0.42 + 0.12 * sin(p.y * 3.0); v = clamp(v, 0.0, 1.0);'
        : 'vec2 p = vW.xz * 0.22; vec2 w = vec2(fbm(p + uTime * 0.03), fbm(p + 4.1 - uTime * 0.025)); float v = fbm(p * 1.6 + w * 1.8 + vec2(uTime * 0.05, 0.0)); float cr = smoothstep(0.08, 0.0, abs(fbm(p * 3.0 + w) - 0.5)); v = clamp(v * 1.05 - 0.1 + cr * 0.42, 0.0, 1.0);'}
        vec3 c = lavaRamp(v) * uK * 0.8; float px = step(0.5, fract(vW.x * 8.0)) * step(0.5, fract(vW.z * 8.0)); c *= 0.92 + 0.08 * px; gl_FragColor = vec4(c, 1.0); }`, fog: false });
}
function runeTex(seed, n = 3) {
  const W = 32, H = 128; const c = document.createElement('canvas'); c.width = W; c.height = H; const g = c.getContext('2d'); g.fillStyle = '#000'; g.fillRect(0, 0, W, H); const r = mulberry(seed);
  g.fillStyle = '#fff'; const cx = W / 2;
  g.fillRect(cx - 1, 6, 2, H - 12);
  for (let i = 0; i < n; i++) { const y = 18 + i * (H - 30) / n; const s = 3 + Math.floor(r() * 4); g.fillRect(cx - s - 2, y, 2 * s + 4, 2); g.fillRect(cx - 4, y - 4, 8, 2); g.fillRect(cx - 4, y + 4, 8, 2); g.fillRect(cx - 6, y - 2, 2, 6); g.fillRect(cx + 4, y - 2, 2, 6); if (r() < 0.6) { g.fillRect(cx - s - 4, y - 6, 2, 14); g.fillRect(cx + s + 2, y - 6, 2, 14); } }
  for (let i = 0; i < 6; i++) g.fillRect(cx - 1 + (r() < 0.5 ? -4 : 3), H - 14 + i * 2, 2, 1 + r() * 4);
  const t = new THREE.CanvasTexture(c); t.magFilter = THREE.NearestFilter; t.minFilter = THREE.LinearFilter; return t;
}
function emblemTex() {
  const S = 64; const c = document.createElement('canvas'); c.width = S; c.height = S * 2; const g = c.getContext('2d'); g.fillStyle = '#000'; g.fillRect(0, 0, S, S * 2); g.fillStyle = '#fff';
  const cx = S / 2; g.fillRect(cx - 2, 8, 4, S * 2 - 16);
  for (const [y, w] of [[30, 10], [64, 18], [98, 10]]) { g.fillRect(cx - w, y, 2 * w, 4); }
  for (let k = 0; k < 4; k++) { const s = 10 - k * 2; g.fillRect(cx - s, 64 - s, 2, 2 * s); g.fillRect(cx + s - 2, 64 - s, 2, 2 * s); g.fillRect(cx - s, 64 - s, 2 * s, 2); g.fillRect(cx - s, 64 + s - 2, 2 * s, 2); }
  for (let i = 0; i < 12; i++) g.fillRect(cx - 1 + ((i % 3) - 1) * 5, 108 + i * 1.5, 2, 3);
  const t = new THREE.CanvasTexture(c); t.magFilter = THREE.NearestFilter; return t;
}

export function buildAbyss(ctx, origin = V(600, 0, 0)) {
  const r = mulberry(91);
  const group = new THREE.Group(); group.position.copy(origin); ctx.scene.add(group);
  const M = {
    rock: mat4(grunge(0x1c1618, { size: 32, noise: 0.4, dark: 0.35, rust: 0.04, rustCol: 0x8a1a08, seed: 92, specks: 0.05, speckCol: 0x5a0a04 }), { shininess: 40, specular: 0x442222, rim: 0.8, wet: 1.6 }),
    rock2: mat4(grunge(0x2a2224, { size: 32, noise: 0.35, dark: 0.3, seed: 93, specks: 0.04, speckCol: 0x0a0606 }), { rim: 0.8, wet: 1.2 }),
    tile: mat4(grunge(0x201a1e, { size: 32, noise: 0.3, dark: 0.25, seed: 94, specks: 0.05, speckCol: 0x4a0a08 }), { shininess: 70, specular: 0x553333, rim: 0.8, wet: 2.0 }),
    iron: mat4(grunge(0x1a1618, { size: 16, noise: 0.25, rust: 0.12, rustCol: 0x4a1a0a, seed: 95 }), { shininess: 50, specular: 0x443333, rim: 0.9, wet: 1.0 }),
    castle: mat4(grunge(0x161214, { size: 32, noise: 0.3, seed: 96 }), { rim: 0.5, wet: 0.4 }),
  };
  const glowRed = new THREE.MeshBasicMaterial({ color: new THREE.Color(7, 0.35, 0.15) });
  const glowWin = new THREE.MeshBasicMaterial({ color: new THREE.Color(3.2, 0.6, 0.1) });
  // lave
  const lavaM = lavaMaterial(); const lava = new THREE.Mesh(new THREE.PlaneGeometry(500, 500), lavaM); lava.rotation.x = -Math.PI / 2; group.add(lava);
  const b = new Batch();
  const col = (x, z, top, w = 1.2, mat = 'rock') => { const n = Math.ceil(top + 2); for (let k = 0; k < 2; k++) b.add({ x: x + (k ? 0.12 : 0), y: (top - 2) / 2, z: z + (k ? -0.1 : 0.05), w: w * (k ? 0.82 : 1), h: top + 2, d: w * (k ? 1.02 : 0.86), mat, tpm: 0.8 }); b.add({ x, y: top + 0.04, z, w: w * 0.92, h: 0.08, d: w * 0.8, mat: 'rock2' }); return V(x, top, z); };
  // corniche d'atterrissage (blocs irréguliers)
  for (let x = -4.5; x <= 4.5; x += 1.0) for (let z = -2.5; z <= 6.5; z += 1.0) { const top = 1.5 + (r() - 0.5) * 0.12 + (Math.abs(x) > 3.6 ? r() * 0.8 : 0); b.add({ x, y: top / 2 - 1, z, w: 1.02, h: top + 2, d: 1.02, mat: r() < 0.7 ? 'rock' : 'rock2' }); }
  // colonnes à franchir (vers -z) + corniche lointaine
  const steps = []; let cx = 0.5;
  for (let i = 0; i < 9; i++) { const z = -4.2 - i * 1.75; cx += (r() - 0.5) * 1.6; cx = Math.max(-2.5, Math.min(2.5, cx)); steps.push(col(cx, z, 1.5 + (r() - 0.5) * 0.5 + i * 0.12, 1.15)); }
  const far = V(0, 2.6, -24);
  for (let x = -4; x <= 4; x += 1.0) for (let z = -27.5; z <= -20.5; z += 1.0) { const top = 2.6 + (r() - 0.5) * 0.12; b.add({ x, y: top / 2 - 1, z, w: 1.02, h: top + 2, d: 1.02, mat: r() < 0.7 ? 'rock' : 'rock2' }); }
  // colonnes décoratives, falaises, cascades de lave
  for (let i = 0; i < 70; i++) { const side = r() < 0.5 ? -1 : 1; const x = side * (5 + r() * 18), z = 10 - r() * 90; col(x, z, 0.8 + r() * (Math.abs(x) > 12 ? 12 : 4), 1.2 + r() * 1.6, r() < 0.6 ? 'rock' : 'rock2'); }
  const falls = [];
  for (const side of [-1, 1]) for (let z = 14; z > -110; z -= 2.2) { const x = side * (22 + r() * 6); const hgt = 18 + r() * 26; b.add({ x, y: hgt / 2 - 1, z, w: 4 + r() * 4, h: hgt, d: 2.4, mat: r() < 0.7 ? 'rock' : 'rock2' }); if (r() < 0.16) falls.push([x - side * 2.6, z, hgt]); }
  // stalactites (au-dessus)
  for (let i = 0; i < 60; i++) { const x = (r() - 0.5) * 70, z = 10 - r() * 120, y = 46 + r() * 10; for (let k = 0; k < 4; k++) { const s = (4 - k) * 0.7 * (0.6 + r() * 0.6); b.add({ x: x + (r() - 0.5) * 0.4, y: y - k * 2.6, z, w: s, h: 2.8, d: s, mat: 'rock2' }); } }
  // château gothique + pont au loin
  const CZ = -150;
  for (let i = 0; i < 26; i++) { const x = (r() - 0.5) * 80, h = 20 + r() * 45, w = 4 + r() * 6; b.add({ x, y: h / 2, z: CZ - r() * 30, w, h, d: w, mat: 'castle' }); for (let k = 0; k < 3; k++) b.add({ x: x + (r() - 0.5) * w * 0.6, y: h + 2 + k * 3, z: CZ - 10, w: w * (0.5 - k * 0.12), h: 4, d: w * 0.5, mat: 'castle' }); }
  for (let x = -40; x <= 40; x += 2) { b.add({ x, y: 16, z: CZ + 40, w: 2.1, h: 1.2, d: 4, mat: 'castle' }); if (Math.abs(x % 10) < 0.5) b.add({ x, y: 8, z: CZ + 40, w: 2.4, h: 16, d: 3.6, mat: 'castle' }); }
  // ---------------- escalier de blocs flottants vers la porte
  const stairs = []; const SZ0 = -28.2, GY = 30, GZ = -62;
  for (let i = 0; i < 44; i++) { const t = i / 43; const z = SZ0 - t * (GZ - SZ0) * -1 + 0; const ang = t * 1.4; const x = Math.sin(ang * 2.2) * 5 * (1 - t); stairs.push({ p: V(x, 2.6 + t * (GY - 2.6), SZ0 + t * (GZ + 6 - SZ0)), seed: r(), drop: r() }); }
  // plateforme de la porte : dalles + piliers à runes + porte
  const plat = new Batch();
  for (let x = -5; x <= 5; x += 1.25) for (let z = GZ + 7; z >= GZ - 1; z -= 1.25) plat.add({ x, y: GY - 0.3, z, w: 1.2, h: 0.6, d: 1.2, mat: 'tile' });
  for (let k = 0; k < 6; k++) plat.add({ x: 0, y: GY + 0.15 + k * 0.3, z: GZ - 1.5 - k * 0.6, w: 6 - k * 0.3, h: 0.3, d: 0.6, mat: 'tile' });
  const pillars = [];
  for (const side of [-1, 1]) for (let k = 0; k < 3; k++) { const x = side * 4.6, z = GZ + 6 - k * 3.2, h = 5 + k * 1.5; plat.add({ x, y: GY + h / 2, z, w: 1.1, h, d: 1.1, mat: 'rock' }); plat.add({ x, y: GY + h + 0.2, z, w: 1.4, h: 0.4, d: 1.4, mat: 'rock2' }); pillars.push({ x, z, h }); }
  // porte : cadre, tours, vantaux
  const DW = 7, DH = 13, DZ = GZ - 5.5, DY = GY + 1.8;
  plat.add({ x: -DW / 2 - 1.2, y: DY + DH / 2 + 1, z: DZ, w: 2.4, h: DH + 2, d: 2.4, mat: 'rock' }); plat.add({ x: DW / 2 + 1.2, y: DY + DH / 2 + 1, z: DZ, w: 2.4, h: DH + 2, d: 2.4, mat: 'rock' });
  plat.add({ x: 0, y: DY + DH + 1.6, z: DZ, w: DW + 4.8, h: 3.2, d: 2.4, mat: 'rock' });
  for (let k = 0; k < 5; k++) { plat.add({ x: 0, y: DY + DH + 3.5 + k * 1.6, z: DZ, w: DW - k * 1.4, h: 1.6, d: 2.2, mat: 'rock2' }); }
  for (const s of [-1, 1]) for (let k = 0; k < 4; k++) plat.add({ x: s * (DW / 2 + 1.2), y: DY + DH + 2.4 + k * 2.2, z: DZ, w: 1.6 - k * 0.3, h: 2.4, d: 1.6 - k * 0.3, mat: 'rock2' });
  plat.add({ x: -DW / 4, y: DY + DH / 2, z: DZ + 0.2, w: DW / 2 - 0.05, h: DH, d: 0.6, mat: 'iron', tpm: 0.6 }); plat.add({ x: DW / 4, y: DY + DH / 2, z: DZ + 0.2, w: DW / 2 - 0.05, h: DH, d: 0.6, mat: 'iron', tpm: 0.6 });
  for (let k = 0; k < 6; k++) plat.add({ x: 0, y: DY + 1 + k * 2.2, z: DZ + 0.55, w: DW - 0.2, h: 0.25, d: 0.12, mat: 'iron' });
  b.build(M, group, { noCast: ['castle'] });
  const platMeshes = plat.build(M, group);
  // runes (piliers) et emblème (porte)
  const runeMats = []; pillars.forEach((p, i) => { const m = new THREE.MeshBasicMaterial({ map: runeTex(i + 3), color: new THREE.Color(0, 0, 0), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }); runeMats.push(m);
    const pl = new THREE.Mesh(new THREE.PlaneGeometry(0.5, p.h * 0.8), m); pl.position.set(p.x - Math.sign(p.x) * 0.56, GY + p.h * 0.5, p.z); pl.rotation.y = -Math.sign(p.x) * Math.PI / 2; group.add(pl);
    const pl2 = new THREE.Mesh(new THREE.PlaneGeometry(0.5, p.h * 0.8), m); pl2.position.set(p.x, GY + p.h * 0.5, p.z + 0.56); group.add(pl2); });
  const emblemM = new THREE.MeshBasicMaterial({ map: emblemTex(), color: new THREE.Color(5, 0.25, 0.12), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false });
  const emblem = new THREE.Mesh(new THREE.PlaneGeometry(2.2, 6.6), emblemM); emblem.position.set(0, DY + DH * 0.55, DZ + 0.62); group.add(emblem);
  const seamM = new THREE.MeshBasicMaterial({ color: new THREE.Color(6, 0.3, 0.1) }); const seam = new THREE.Mesh(new THREE.BoxGeometry(0.08, DH, 0.05), seamM); seam.position.set(0, DY + DH / 2, DZ + 0.52); group.add(seam);
  const doorGlowM = new THREE.MeshBasicMaterial({ color: new THREE.Color(0, 0, 0) }); const doorGlow = new THREE.Mesh(new THREE.BoxGeometry(DW - 0.4, 0.2, 0.3), doorGlowM); doorGlow.position.set(0, DY + 0.1, DZ + 0.6); group.add(doorGlow);
  // joints lumineux des dalles (bords de la plateforme)
  for (const s of [-1, 1]) { const e = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.05, 9), glowRed); e.position.set(s * 5.62, GY + 0.02, GZ + 3); group.add(e); }
  for (let z = GZ + 7.6; z >= GZ - 1; z -= 1.25) { const e = new THREE.Mesh(new THREE.BoxGeometry(11, 0.02, 0.03), new THREE.MeshBasicMaterial({ color: new THREE.Color(2.2, 0.08, 0.04) })); e.position.set(0, GY + 0.005, z); group.add(e); }
  // cascades de lave
  const fallM = lavaMaterial({ fall: true, k: 0.6 }); for (const [x, z, h] of falls) { const f = new THREE.Mesh(new THREE.PlaneGeometry(2.2, h), fallM); f.position.set(x, h / 2, z); f.rotation.y = x > 0 ? -Math.PI / 2 : Math.PI / 2; group.add(f); }
  for (let i = 0; i < 8; i++) { const x = (r() - 0.5) * 70, h = 30 + r() * 20; const f = new THREE.Mesh(new THREE.PlaneGeometry(1.6, h), fallM); f.position.set(x, h / 2, CZ + 42); group.add(f); }
  // ---------------- grotte du lac souterrain (derrière la corniche) : eau sombre, cristaux bleus, vapeur
  const cave = new Batch(); const CZ0 = 7, CZ1 = 34, LW = 1.2;
  for (let z = CZ0 - 9; z <= CZ1; z += 2.2) for (const sx of [-1, 1]) { const w = z < CZ0 ? 6.5 : 11 + Math.sin(z * 0.7) * 1.5; cave.add({ x: sx * (w + 1.5), y: 4, z, w: 3 + r() * 1.5, h: 14, d: 2.4, mat: r() < 0.6 ? 'rock' : 'rock2' }); }
  for (let z = CZ0 - 9; z <= CZ1; z += 2.4) for (let x = -12; x <= 12; x += 2.6) { const y = (z < CZ0 ? 7.5 : 10) + r() * 1.5; cave.add({ x, y, z, w: 2.8, h: 1.6 + r(), d: 2.6, mat: 'rock2' }); if (r() < 0.3) cave.add({ x: x + (r() - 0.5), y: y - 1.6, z, w: 0.5, h: 1.6 + r(), d: 0.5, mat: 'rock' }); }
  cave.add({ x: 0, y: 4, z: CZ1 + 1.5, w: 28, h: 14, d: 3, mat: 'rock' });
  for (let x = -11; x <= 11; x += 2.2) for (let z = CZ0; z <= CZ1; z += 2.2) cave.add({ x: x + (r() - 0.5), y: -6.5 + r() * 1.5, z: z + (r() - 0.5), w: 2.3, h: 1.4, d: 2.3, mat: 'rock2' });
  for (let i = 0; i < 26; i++) { const sx = r() < 0.5 ? -1 : 1; const x = sx * (6 + r() * 4.5), z = CZ0 + 1 + r() * (CZ1 - CZ0 - 2); cave.add({ x, y: LW - 0.3 + r() * 0.5, z, w: 1 + r() * 1.5, h: 1.2, d: 1 + r() * 1.5, mat: 'rock' }); }
  cave.build(M, group, { noCast: ['rock2'] });
  const crystM = new THREE.MeshBasicMaterial({ color: new THREE.Color(0.6, 2.6, 3.4) }); const crystals = [];
  for (let i = 0; i < 34; i++) { const sx = r() < 0.5 ? -1 : 1; const x = sx * (7 + r() * 3.5), z = CZ0 + 1 + r() * (CZ1 - CZ0 - 3), y = LW + r() * 5; const g = new THREE.Group(); g.position.set(x, y, z);
    for (let k = 0; k < 3 + Math.floor(r() * 3); k++) { const h = 0.3 + r() * 0.9; const c = new THREE.Mesh(new THREE.BoxGeometry(0.12 + r() * 0.1, h, 0.12 + r() * 0.1), crystM); c.position.set((r() - 0.5) * 0.4, h / 2, (r() - 0.5) * 0.4); c.rotation.set((r() - 0.5) * 0.8, r(), (r() - 0.5) * 0.8); g.add(c); }
    group.add(g); crystals.push(V(x, y + 0.4, z)); }
  // eau : surface réfléchissante (vue d'en haut) + surface vue d'en dessous (scintillement)
  const waterM = ctx.reflector.makeMaterial({ color: 0x021216, reflect: 1.1, rough: 0.004, ripple: 0.5, tint: 0xb8f0ff, glitter: 0.5, glitterCol: 0x8ae8ff });
  const water = new THREE.Mesh(new THREE.PlaneGeometry(26, CZ1 - CZ0 + 0.5), waterM); water.rotation.x = -Math.PI / 2; water.position.set(0, LW, (CZ0 + CZ1) / 2); group.add(water);
  const underM = new THREE.ShaderMaterial({ uniforms: { uTime: { value: 0 } }, side: THREE.BackSide, fog: false,
    vertexShader: 'varying vec3 vW; void main(){ vW = (modelMatrix * vec4(position,1.0)).xyz; gl_Position = projectionMatrix * viewMatrix * vec4(vW,1.0); }',
    fragmentShader: `uniform float uTime; varying vec3 vW; ${NOISE}
      void main(){ vec2 p = vW.xz * 0.6; float n = fbm(p + uTime * 0.15) * 0.6 + fbm(p * 2.3 - uTime * 0.1) * 0.4; float c = smoothstep(0.45, 0.75, n);
        vec3 col = mix(vec3(0.02, 0.18, 0.22), vec3(0.5, 1.6, 1.8), c); gl_FragColor = vec4(col, 1.0); }` });
  const under = new THREE.Mesh(new THREE.PlaneGeometry(26, CZ1 - CZ0 + 0.5), underM); under.rotation.x = -Math.PI / 2; under.position.set(0, LW - 0.01, (CZ0 + CZ1) / 2); group.add(under); under.visible = false;
  // fenêtres du château
  for (let i = 0; i < 40; i++) { const w = new THREE.Mesh(new THREE.PlaneGeometry(0.8, 2.4 + r() * 3), glowWin); w.position.set((r() - 0.5) * 70, 10 + r() * 40, CZ + 12); group.add(w); }
  // blocs d'escalier (instanciés : tremblement, chute) + gouttes + chaînes
  const blockG = boxesGeometry([{ x: 0, y: 0, z: 0, w: 1.3, h: 0.55, d: 0.9, color: 0xffffff }, { x: -0.3, y: -0.45, z: 0.1, w: 0.35, h: 0.4, d: 0.35, color: 0xbbbbbb }, { x: 0.35, y: -0.55, z: -0.15, w: 0.25, h: 0.6, d: 0.25, color: 0xbbbbbb }, { x: 0.05, y: -0.95, z: 0.05, w: 0.18, h: 0.3, d: 0.18, color: 0x999999 }]);
  const stairM = mat4(grunge(0x1e181c, { size: 32, noise: 0.35, dark: 0.3, seed: 97, specks: 0.05, speckCol: 0x4a0a06 }), { shininess: 60, specular: 0x553333, rim: 0.9, wet: 2.0 });
  const stairMesh = new THREE.InstancedMesh(blockG, stairM, stairs.length); stairMesh.castShadow = true; stairMesh.receiveShadow = true; group.add(stairMesh);
  const linkG = boxesGeometry([{ x: 0, y: 0.25, z: 0, w: 0.08, h: 0.5, d: 0.3, color: 0xffffff }, { x: 0, y: 0.55, z: 0, w: 0.3, h: 0.5, d: 0.08, color: 0xffffff }]);
  const chainN = stairs.length * 6 + 120; const chain = new THREE.InstancedMesh(linkG, M.iron, chainN); group.add(chain);
  // chaînes : au-dessus de chaque bloc (montent dans le noir) + grandes chaînes décoratives
  const chainDefs = []; stairs.forEach((s, i) => { if (i % 2) return; for (let k = 0; k < 12; k++) chainDefs.push({ st: i, dy: 0.4 + k * 0.62 }); });
  const deco = []; for (let i = 0; i < 4; i++) { const a = V((r() - 0.5) * 30, GY + 6 + r() * 10, GZ + 10 - r() * 20), c = V((r() - 0.5) * 30, GY - 2 + r() * 6, GZ + 10 - r() * 20); deco.push([a, c]); }
  // blocs flottants décoratifs + silhouettes posées dessus
  for (let i = 0; i < 50; i++) { const x = (r() - 0.5) * 60, y = 6 + r() * 40, z = -20 - r() * 60; if (Math.abs(x) < 7 && z < -26) continue; const s = 0.8 + r() * 3; const bb = new Batch(); bb.add({ x: 0, y: 0, z: 0, w: s, h: s * 0.6, d: s, mat: 'rock' }); for (let k = 0; k < 3; k++) bb.add({ x: (r() - 0.5) * s * 0.6, y: -s * 0.4 - r() * s * 0.5, z: (r() - 0.5) * s * 0.6, w: s * 0.2, h: s * 0.4, d: s * 0.2, mat: 'rock2' }); const g = new THREE.Group(); g.position.set(x, y, z); bb.build(M, g); group.add(g); }
  const shades = [];
  const m4 = new THREE.Matrix4(), q4 = new THREE.Quaternion(), e4 = new THREE.Euler(), s1 = V(1, 1, 1);
  const ab = {
    group, origin, lava, lavaM, fallM, steps, far, stairs, GY, GZ, DZ, DY, DW, DH, pillars, runeMats, emblemM, seamM, doorGlowM, shades,
    w(x, y, z) { return V(x, y, z).add(origin); },
    // position monde (dessus) de la marche i, avec le tremblement en cours
    stairTop(i, t, shake = 0) { const s = stairs[Math.max(0, Math.min(stairs.length - 1, i))]; return s.p.clone().add(V(Math.sin(t * 23 + s.seed * 40) * 0.02 * shake, 0.28 + Math.sin(t * 17 + s.seed * 9) * 0.03 * shake, 0)).add(origin); },
    update(t, S) { lavaM.uniforms.uTime.value = t; fallM.uniforms.uTime.value = t; underM.uniforms.uTime.value = t; under.visible = !!S.underwater; water.visible = !S.underwater; },
    lake: { y: LW, z0: CZ0, z1: CZ1, water, under, crystals, crystM },
    caveLights(n = 4, near = null) { const L = crystals.map((c) => c.clone().add(origin)); if (near) L.sort((a, b) => a.distanceToSquared(near) - b.distanceToSquared(near)); return L.slice(0, n).map((p) => ({ pos: p, color: 0x40d8ff, i: 2.2, dist: 7, decay: 1.4 })); },
    // escalier : tremblement (shake), effondrement (collapse = indice de marche à partir duquel ça tombe, et temps de chute)
    setStairs(t, shake = 0, collapseFrom = 999, collapseT = 0) {
      stairs.forEach((s, i) => { let y = 0, rx = 0, rz = 0; const sh = shake * (0.5 + s.seed); if (i <= collapseFrom && collapseT > 0) { const tt = Math.max(0, collapseT - (collapseFrom - i) * 0.18 - s.drop * 0.1); y = -tt * tt * 6; rx = tt * (s.seed - 0.5) * 3; rz = tt * (s.drop - 0.5) * 3; }
        e4.set(rx + Math.sin(t * 19 + s.seed * 30) * 0.01 * sh, s.seed * 0.5 - 0.25, rz + Math.sin(t * 23 + s.drop * 30) * 0.012 * sh); q4.setFromEuler(e4);
        m4.compose(V(s.p.x + Math.sin(t * 23 + s.seed * 40) * 0.02 * sh, s.p.y + y + Math.sin(t * 17 + s.seed * 9) * 0.025 * sh, s.p.z), q4, s1); stairMesh.setMatrixAt(i, m4); s.cur = y; });
      stairMesh.instanceMatrix.needsUpdate = true;
      let n = 0; for (const cd of chainDefs) { const s = stairs[cd.st]; e4.set(0, (cd.dy * 3.1) % 1.57, 0); q4.setFromEuler(e4); m4.compose(V(s.p.x, s.p.y + (s.cur || 0) + cd.dy, s.p.z), q4, s1); chain.setMatrixAt(n++, m4); }
      for (const [a, c] of deco) { const L = a.distanceTo(c); const k = Math.floor(L / 0.62); for (let j = 0; j < k && n < chainN; j++) { const p = a.clone().lerp(c, j / k); p.y -= Math.sin(Math.PI * j / k) * 2.5; const d = c.clone().sub(a).normalize(); q4.setFromUnitVectors(V(0, 1, 0), d); e4.setFromQuaternion(q4); m4.compose(p, q4, s1); chain.setMatrixAt(n++, m4); } }
      chain.count = n; chain.instanceMatrix.needsUpdate = true;
    },
    // runes : k par pilier (0..1)
    setRunes(ks, door = 0, t = 0) { runeMats.forEach((m, i) => { const k = Array.isArray(ks) ? (ks[i] ?? 0) : ks; const f = k * (0.85 + 0.15 * Math.sin(t * 9 + i)); m.color.setRGB(6 * f, 0.3 * f, 0.12 * f); }); const fd = door * (0.8 + 0.2 * Math.sin(t * 5)); emblemM.color.setRGB(5 * fd, 0.25 * fd, 0.12 * fd); seamM.color.setRGB(6 * fd, 0.3 * fd, 0.1 * fd); },
    setDoorGlow(k) { doorGlowM.color.setRGB(8 * k, 0.5 * k, 0.15 * k); },
    lavaLights(around, n = 3) { const L = []; for (let i = 0; i < n; i++) { const a = i / n * 6.28; L.push({ pos: around.clone().add(V(Math.cos(a) * 4, 0.6, Math.sin(a) * 4)), color: 0xff5a10, i: 3, dist: 9, decay: 1.4 }); } return L; },
  };
  ab.setStairs(0, 0); ab.setRunes(0, 0, 0);
  return ab;
}
