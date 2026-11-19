// Monde d'hiver pour le module musique : neige lisse (champ de hauteur), lac gelé avec vrai reflet,
// sapins enneigés, cabane aux fenêtres chaudes, lampadaires, banc, bonhomme de neige,
// ciel de nuit (étoiles, lune, aurore boréale), chute de neige avec bokeh, flaques de lumière.
import * as THREE from 'three';
import { boxesGeometry, boxesMesh, jitter } from './boxes.js';
import { mulberry } from './textures.js';

const V = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
function hash2(x, z) { const s = Math.sin(x * 127.1 + z * 311.7) * 43758.5453; return s - Math.floor(s); }
function vnoise(x, z) {
  const xi = Math.floor(x), zi = Math.floor(z), xf = x - xi, zf = z - zi;
  const u = xf * xf * (3 - 2 * xf), v = zf * zf * (3 - 2 * zf);
  const a = hash2(xi, zi), b = hash2(xi + 1, zi), c = hash2(xi, zi + 1), d = hash2(xi + 1, zi + 1);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
}
const fbm = (x, z) => vnoise(x * 0.025, z * 0.025) * 1.0 + vnoise(x * 0.06 + 5, z * 0.06) * 0.45 + vnoise(x * 0.14 + 9, z * 0.14) * 0.16;

export const LAYOUT = {
  clearing: { x: 0, z: 0, r: 15 },
  cabin: { x: -8, z: 7, w: 7, d: 5.5, facing: 'z-' },        // porte vers -z (vers la clairière)
  lake: { x: 24, z: -24, r: 13, y: -0.06 },
  hill: { x: -32, z: -46, r: 16, h: 7.5 },
  bench: { x: 9.6, z: -12.6, yaw: 2.24 },
  snowman: { x: 12.4, z: -16.4, yaw: -0.6 },
  lamps: [[-4.6, -1.2], [0.8, -4.9], [4.6, -7.2], [11.4, -10.2], [-1.6, 3.0]],
  path: [[-6.5, 3], [-3, -1], [1, -4], [5, -7], [9, -10.5], [12, -13]],
};

function distToPath(x, z) {
  let best = 1e9; const P = LAYOUT.path;
  for (let i = 0; i < P.length - 1; i++) {
    const [ax, az] = P[i], [bx, bz] = P[i + 1]; const dx = bx - ax, dz = bz - az;
    const t = Math.max(0, Math.min(1, ((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz)));
    best = Math.min(best, Math.hypot(x - ax - t * dx, z - az - t * dz));
  }
  return best;
}

export function groundY(x, z) {
  const L = LAYOUT; const r0 = Math.hypot(x - L.clearing.x, z - L.clearing.z);
  let h = (fbm(x, z) - 0.7) * 2.2;                               // dunes douces
  h += Math.max(0, r0 - 30) * 0.06 + Math.max(0, r0 - 60) * 0.12; // collines au loin
  h *= smooth(L.clearing.r * 0.6, L.clearing.r + 10, r0);         // clairière plate
  const pd = distToPath(x, z); h *= 0.35 + 0.65 * smooth(1.2, 4.5, pd);
  const hd = Math.hypot(x - L.hill.x, z - L.hill.z); h += L.hill.h * (1 - smooth(0, L.hill.r, hd)) * (1 - smooth(0, L.hill.r, hd)) * 1.0 + L.hill.h * 0.5 * smooth(L.hill.r * 2, 0, hd) * 0.4;
  const ld = Math.hypot(x - L.lake.x, z - L.lake.z);
  if (ld < L.lake.r + 6) {                                         // berge : remonte juste au-dessus de la glace, fond sous la glace
    const rimY = L.lake.y + 0.06, bedY = L.lake.y - 0.4;
    const k1 = smooth(L.lake.r + 6, L.lake.r + 0.6, ld); h = h * (1 - k1) + rimY * k1;
    const k2 = smooth(L.lake.r + 0.6, L.lake.r - 1.0, ld); h = h * (1 - k2) + bedY * k2;
  }
  return h;
}

// ------------------------------------------------------------------ ciel
function buildNightSky(scene) {
  const mat = new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 }, uMoon: { value: V(-0.35, 0.42, -0.84).normalize() }, uAurora: { value: 0.0 }, uStars: { value: 1.0 },
      uTop: { value: new THREE.Color(0x040814) }, uHor: { value: new THREE.Color(0x1b2c4e) }, uDawn: { value: 0.0 } },
    vertexShader: `varying vec3 vDir; void main(){ vDir = normalize(position); vec4 p = projectionMatrix * modelViewMatrix * vec4(position,1.0); gl_Position = p.xyww; }`,
    fragmentShader: `uniform float uTime, uAurora, uStars, uDawn; uniform vec3 uMoon, uTop, uHor; varying vec3 vDir;
      float h(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
      float n(vec2 p){ vec2 i=floor(p), f=fract(p); f=f*f*(3.0-2.0*f); return mix(mix(h(i),h(i+vec2(1,0)),f.x), mix(h(i+vec2(0,1)),h(i+vec2(1,1)),f.x), f.y); }
      void main(){ vec3 d = normalize(vDir); float e = clamp(d.y, 0.0, 1.0);
        vec3 col = mix(uHor, uTop, pow(e, 0.45));
        // aube : bande chaude à l'horizon
        col = mix(col, mix(vec3(0.95,0.55,0.35), vec3(0.35,0.45,0.75), smoothstep(0.0,0.35,e)), uDawn * (1.0 - smoothstep(0.0, 0.6, e)) * 0.9);
        // étoiles
        vec2 g = vec2(atan(d.z, d.x) * 180.0, asin(d.y) * 180.0); vec2 c = floor(g); float s = h(c);
        float star = step(0.9965, s) * smoothstep(0.4, 0.0, length(fract(g) - 0.5)) * (0.6 + 0.4 * sin(uTime * (1.0 + s * 5.0) + s * 40.0));
        col += vec3(0.9, 0.95, 1.0) * star * uStars * smoothstep(0.02, 0.2, e) * 2.2;
        // aurore boréale : deux rideaux dont le bord bas est net, qui s'estompent vers le haut, avec des rayons verticaux
        float az = atan(d.x, -d.z); vec3 acol = vec3(0.0);
        for (int k = 0; k < 2; k++) { float fk = float(k);
          float base = 0.09 + 0.08 * n(vec2(az * 1.7 + fk * 4.0 + uTime * 0.02, fk * 3.0));
          float fold = n(vec2(az * 3.2 + fk * 9.0 - uTime * 0.05, 2.0 + fk));
          float rays = 0.45 + 0.55 * n(vec2(az * 70.0 + fold * 9.0, uTime * 0.35 + fk * 5.0));
          float above = e - base;
          float shape = smoothstep(-0.008, 0.012, above) * exp(-max(above, 0.0) * (7.5 - fk * 2.5));
          float bright = smoothstep(0.3, 0.75, fold) * rays * shape;
          vec3 c = mix(vec3(0.12, 1.0, 0.52), vec3(0.15, 0.85, 0.95), smoothstep(0.0, 0.1, above));
          c = mix(c, vec3(0.62, 0.32, 0.95), smoothstep(0.1, 0.28, above));
          acol += c * bright; }
        col += acol * uAurora * 1.7 * smoothstep(-0.3, 0.5, cos(az - 0.8));
        // lune
        float m = max(dot(d, normalize(uMoon)), 0.0);
        col += vec3(0.85, 0.9, 1.0) * (smoothstep(0.99955, 0.9997, m) * 2.2 + pow(m, 400.0) * 0.35 + pow(m, 30.0) * 0.06);
        if (d.y < 0.0) col = uHor * 0.8;
        gl_FragColor = vec4(col, 1.0); }`,
    side: THREE.BackSide, depthWrite: false,
  });
  const m = new THREE.Mesh(new THREE.SphereGeometry(450, 48, 24), mat); m.frustumCulled = false; m.renderOrder = -10; scene.add(m);
  return m;
}

// ------------------------------------------------------------------ neige qui tombe (bokeh près de la caméra)
function buildSnowfall(scene, count = 9000) {
  const r = mulberry(77); const pos = new Float32Array(count * 3), rnd = new Float32Array(count * 4);
  for (let i = 0; i < count; i++) { pos.set([r(), r(), r()], i * 3); rnd.set([r(), r(), r(), r()], i * 4); }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(pos, 3)); g.setAttribute('aRnd', new THREE.BufferAttribute(rnd, 4));
  const mat = new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 }, uCam: { value: V() }, uBox: { value: V(36, 22, 36) }, uWind: { value: V(0.6, 0, 0.2) }, uFall: { value: 0.9 }, uSize: { value: 26 }, uScale: { value: 1 }, uInt: { value: 1 }, uGust: { value: 0 }, uCol: { value: new THREE.Color(1.0, 1.02, 1.08) } },
    vertexShader: `attribute vec4 aRnd; uniform float uTime, uFall, uSize, uScale, uGust; uniform vec3 uCam, uBox, uWind; varying float vA; varying float vNear;
      void main(){ vec3 p = position * uBox;
        float sw = sin(uTime * (0.5 + aRnd.x) + aRnd.y * 6.283) * (0.35 + uGust * 1.4);
        vec3 off = vec3(uWind.x * uTime * (0.7 + aRnd.z * 0.6) + sw, -uFall * (0.55 + aRnd.y * 0.9) * uTime, uWind.z * uTime + cos(uTime * 0.45 + aRnd.z * 6.283) * 0.35);
        off.x += uGust * uTime * 2.0 * (0.5 + aRnd.w);
        p = mod(p + off - uCam + uBox * 0.5, uBox) + uCam - uBox * 0.5;
        vec4 mv = modelViewMatrix * vec4(p, 1.0); gl_Position = projectionMatrix * mv;
        float d = -mv.z;
        gl_PointSize = uSize * (0.45 + aRnd.w * 0.9) * uScale / max(d, 0.25);
        vNear = smoothstep(2.2, 0.5, d);
        vA = smoothstep(0.2, 0.7, d) * (1.0 - smoothstep(uBox.z * 0.35, uBox.z * 0.5, d)); }`,
    fragmentShader: `uniform float uInt; uniform vec3 uCol; varying float vA; varying float vNear;
      void main(){ float d = length(gl_PointCoord - 0.5); float edge = mix(0.12, 0.42, vNear);
        float a = 1.0 - smoothstep(0.5 - edge, 0.5, d); a *= mix(1.0, 0.35, vNear);
        gl_FragColor = vec4(uCol * a * vA * uInt, 1.0); }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  });
  const pts = new THREE.Points(g, mat); pts.frustumCulled = false; pts.renderOrder = 8; scene.add(pts);
  return { pts, mat };
}

// ------------------------------------------------------------------ flaques de lumière au sol (additif)
function buildPool(scene, color, radius) {
  const mat = new THREE.ShaderMaterial({ uniforms: { uCol: { value: new THREE.Color(color) }, uInt: { value: 1 } },
    vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`,
    fragmentShader: `uniform vec3 uCol; uniform float uInt; varying vec2 vUv; void main(){ float d = length(vUv - 0.5) * 2.0; float a = pow(max(1.0 - d, 0.0), 2.2); gl_FragColor = vec4(uCol * a * uInt, 1.0); }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, polygonOffset: true, polygonOffsetFactor: -2 });
  const m = new THREE.Mesh(new THREE.PlaneGeometry(radius * 2, radius * 2), mat); m.rotation.x = -Math.PI / 2; m.renderOrder = 3; scene.add(m);
  return m;
}

// ------------------------------------------------------------------ décor
function spruce(r, h) {
  const B = []; const trunk = 0x4a3324, leaf = [0x1d3b2a, 0x234530, 0x183324], snow = 0xf2f6ff;
  B.push({ x: 0, y: 0.6, z: 0, w: 0.45, h: 1.2, d: 0.45, color: trunk });
  const layers = Math.round(4 + h * 0.6);
  for (let k = 0; k < layers; k++) {
    const t = k / layers, w = (1 - t) * (1.4 + h * 0.32) + 0.35, y = 1.0 + k * (h / layers) * 0.95;
    const c = leaf[k % 3];
    B.push({ x: 0, y, z: 0, w, h: 0.62, d: w, color: jitter(c, 0.08, k + h) });
    B.push({ x: 0, y: y + 0.36, z: 0, w: w * 0.86, h: 0.12, d: w * 0.86, color: snow });           // neige sur la couche
    for (let s = 0; s < 2; s++) { const a = s * Math.PI + r() * 0.8; B.push({ x: Math.cos(a) * w * 0.45, y: y + 0.22, z: Math.sin(a) * w * 0.45, w: 0.28, h: 0.1, d: 0.28, color: snow }); }
  }
  B.push({ x: 0, y: 1.0 + h * 0.98, z: 0, w: 0.3, h: 0.5, d: 0.3, color: snow });
  return boxesGeometry(B);
}

function buildCabin(L) {
  const B = [], W = [], c = L.cabin; const log = [0x6b4a30, 0x5e402a], end = 0x8a6644, snow = 0xf4f7ff;
  const hw = c.w / 2, hd = c.d / 2, wallH = 2.8;
  for (let k = 0; k < 9; k++) {
    const y = 0.16 + k * 0.31, col = log[k % 2];
    B.push({ x: 0, y, z: -hd, w: c.w + 0.5, h: 0.3, d: 0.34, color: jitter(col, 0.05, k) });
    B.push({ x: 0, y, z: hd, w: c.w + 0.5, h: 0.3, d: 0.34, color: jitter(col, 0.05, k + 9) });
    B.push({ x: -hw, y: y + 0.15, z: 0, w: 0.34, h: 0.3, d: c.d + 0.5, color: jitter(col, 0.05, k + 3) });
    B.push({ x: hw, y: y + 0.15, z: 0, w: 0.34, h: 0.3, d: c.d + 0.5, color: jitter(col, 0.05, k + 5) });
    for (const sx of [-1, 1]) for (const sz of [-1, 1]) B.push({ x: sx * (hw + 0.3), y, z: sz * (hd + 0.05), w: 0.2, h: 0.26, d: 0.26, color: end });
  }
  // pignons
  for (let k = 0; k < 6; k++) { const y = wallH + 0.15 + k * 0.3, w = c.w * (1 - k / 6.5); for (const sz of [-1, 1]) B.push({ x: 0, y, z: sz * hd, w, h: 0.3, d: 0.3, color: jitter(log[k % 2], 0.05, k + 20) }); }
  // toit (deux pans) + neige
  const ang = 0.52, len = c.w / 2 / Math.cos(ang) + 0.6, ry = wallH + 1.0;
  for (const sx of [-1, 1]) {
    const x = sx * (c.w / 4 + 0.05);
    B.push({ x, y: ry, z: 0, w: len, h: 0.22, d: c.d + 1.2, rz: -sx * ang, color: 0x3b2a20 });
    B.push({ x: x - sx * 0.06, y: ry + 0.2, z: 0, w: len * 0.98, h: 0.3, d: c.d + 1.3, rz: -sx * ang, color: snow });
  }
  B.push({ x: hw - 1.3, y: wallH + 1.9, z: 1.0, w: 0.7, h: 2.0, d: 0.7, color: 0x6a6a70 }); B.push({ x: hw - 1.3, y: wallH + 2.95, z: 1.0, w: 0.8, h: 0.15, d: 0.8, color: snow });
  // porte + cadres de fenêtres (côté -z)
  B.push({ x: 0.9, y: 1.05, z: -hd - 0.18, w: 1.0, h: 2.1, d: 0.08, color: 0x3a2618 });
  for (const wx of [-1.9, 2.6]) { B.push({ x: wx, y: 1.55, z: -hd - 0.19, w: 1.25, h: 0.12, d: 0.1, color: 0x2a1c12 }); B.push({ x: wx, y: 0.85, z: -hd - 0.19, w: 1.25, h: 0.12, d: 0.1, color: 0x2a1c12 }); B.push({ x: wx, y: 1.2, z: -hd - 0.2, w: 0.08, h: 0.8, d: 0.1, color: 0x2a1c12 }); W.push([wx, 1.2]); }
  B.push({ x: 0, y: 0.06, z: -hd - 0.8, w: c.w + 1, h: 0.12, d: 1.2, color: 0x5a3e28 }); // porche
  const g = new THREE.Group(); g.add(boxesMesh(B));
  const winMat = new THREE.MeshBasicMaterial({ color: new THREE.Color(3.2, 1.9, 0.85) });
  for (const [wx, wy] of W) { const m = new THREE.Mesh(new THREE.PlaneGeometry(1.1, 0.7), winMat); m.position.set(wx, wy, -hd - 0.17); m.rotation.y = Math.PI; g.add(m); }
  g.position.set(c.x, groundY(c.x, c.z) - 0.05, c.z);
  return { g, winMat, windows: W.map(([wx, wy]) => V(c.x + wx, wy, c.z - hd - 0.6)) };
}

function lampGeo() {
  return boxesGeometry([
    { x: 0, y: 0.15, z: 0, w: 0.4, h: 0.3, d: 0.4, color: 0x1c1d22 }, { x: 0, y: 1.6, z: 0, w: 0.13, h: 3.0, d: 0.13, color: 0x22242a },
    { x: 0, y: 3.15, z: 0, w: 0.5, h: 0.08, d: 0.5, color: 0x1c1d22 }, { x: 0, y: 3.65, z: 0, w: 0.6, h: 0.1, d: 0.6, color: 0x1c1d22 },
    { x: 0, y: 3.78, z: 0, w: 0.5, h: 0.12, d: 0.5, color: 0xf2f6ff },
    ...[[-1, -1], [1, -1], [-1, 1], [1, 1]].map(([a, b]) => ({ x: a * 0.22, y: 3.4, z: b * 0.22, w: 0.05, h: 0.5, d: 0.05, color: 0x1c1d22 })),
  ]);
}

export function buildSnowman(opts = {}) {
  const s = 0xeef2fa, s2 = 0xe2e8f4, coal = 0x15151a, B = [];
  B.push({ x: 0, y: 0.45, z: 0, w: 0.95, h: 0.9, d: 0.95, color: s }); B.push({ x: 0, y: 1.2, z: 0, w: 0.7, h: 0.62, d: 0.7, color: s2 }); B.push({ x: 0, y: 1.78, z: 0, w: 0.56, h: 0.52, d: 0.56, color: s });
  for (const ex of [-0.12, 0.12]) B.push({ x: ex, y: 1.86, z: 0.29, w: 0.08, h: 0.08, d: 0.04, color: coal });
  for (const by of [1.1, 1.28]) B.push({ x: 0, y: by, z: 0.36, w: 0.07, h: 0.07, d: 0.04, color: coal });
  for (let k = 0; k < 4; k++) B.push({ x: -0.15 + k * 0.1, y: 1.66, z: 0.29, w: 0.05, h: 0.05, d: 0.03, color: coal });
  B.push({ x: 0, y: 1.76, z: 0.42, w: 0.07, h: 0.07, d: 0.28, color: 0xf07a1e });
  B.push({ x: 0, y: 1.5, z: 0, w: 0.76, h: 0.12, d: 0.76, color: opts.scarf ?? 0xc8282e }); B.push({ x: 0.2, y: 1.32, z: 0.38, w: 0.14, h: 0.32, d: 0.06, color: opts.scarf ?? 0xc8282e });
  for (const sx of [-1, 1]) { B.push({ x: sx * 0.62, y: 1.32, z: 0, w: 0.6, h: 0.05, d: 0.05, rz: sx * 0.45, color: 0x4a3020 }); B.push({ x: sx * 0.86, y: 1.5, z: 0, w: 0.18, h: 0.04, d: 0.04, rz: sx * 1.2, color: 0x4a3020 }); }
  if (opts.hat) { B.push({ x: 0, y: 2.06, z: 0, w: 0.66, h: 0.05, d: 0.66, color: coal }); B.push({ x: 0, y: 2.28, z: 0, w: 0.42, h: 0.42, d: 0.42, color: coal }); B.push({ x: 0, y: 2.12, z: 0, w: 0.44, h: 0.07, d: 0.44, color: 0x9a1e24 }); }
  return boxesMesh(B);
}

function benchGeo() {
  const w = 0x7a5232, i = 0x22242a, s = 0xf2f6ff, B = [];
  for (const sx of [-0.8, 0.8]) { B.push({ x: sx, y: 0.22, z: 0, w: 0.08, h: 0.44, d: 0.5, color: i }); B.push({ x: sx, y: 0.6, z: -0.24, w: 0.08, h: 0.5, d: 0.06, color: i }); }
  for (let k = 0; k < 3; k++) B.push({ x: 0, y: 0.46, z: -0.16 + k * 0.16, w: 1.9, h: 0.06, d: 0.13, color: jitter(w, 0.06, k) });
  for (let k = 0; k < 2; k++) B.push({ x: 0, y: 0.68 + k * 0.17, z: -0.27, w: 1.9, h: 0.1, d: 0.05, color: jitter(w, 0.06, k + 4) });
  B.push({ x: 0.55, y: 0.51, z: 0.05, w: 0.7, h: 0.05, d: 0.38, color: s }); B.push({ x: -0.6, y: 0.51, z: 0.0, w: 0.5, h: 0.04, d: 0.3, color: s });
  return boxesGeometry(B);
}

export function buildLantern() {
  const g = new THREE.Group();
  g.add(boxesMesh([{ x: 0, y: 0, z: 0, w: 0.2, h: 0.03, d: 0.2, color: 0x1c1d22 }, { x: 0, y: 0.26, z: 0, w: 0.22, h: 0.04, d: 0.22, color: 0x1c1d22 }, { x: 0, y: 0.31, z: 0, w: 0.06, h: 0.08, d: 0.06, color: 0x1c1d22 },
    ...[[-1, -1], [1, -1], [-1, 1], [1, 1]].map(([a, b]) => ({ x: a * 0.09, y: 0.13, z: b * 0.09, w: 0.025, h: 0.25, d: 0.025, color: 0x1c1d22 }))]));
  const core = new THREE.Mesh(new THREE.BoxGeometry(0.11, 0.17, 0.11), new THREE.MeshBasicMaterial({ color: new THREE.Color(4.0, 2.4, 1.0) })); core.position.y = 0.13; g.add(core);
  const light = new THREE.PointLight(0xffb060, 3.5, 9, 1.6); light.position.y = 0.14; g.add(light);
  return { g, core, light };
}

// ------------------------------------------------------------------ lac gelé : reflet planaire (rendu miroir à mi-résolution)
function buildIce(scene, renderer, L, W, H) {
  const rt = new THREE.WebGLRenderTarget(Math.floor(W / 2), Math.floor(H / 2), { type: THREE.HalfFloatType });
  const texM = new THREE.Matrix4();
  const mat = new THREE.ShaderMaterial({
    uniforms: { tRef: { value: rt.texture }, uTexM: { value: texM }, uCol: { value: new THREE.Color(0x0e2238) }, uRef: { value: 0.0 }, uCenter: { value: new THREE.Vector2(L.lake.x, L.lake.z) }, uR: { value: L.lake.r }, uCam: { value: V() } },
    vertexShader: `uniform mat4 uTexM; varying vec4 vUvP; varying vec3 vW; void main(){ vec4 w = modelMatrix * vec4(position,1.0); vW = w.xyz; vUvP = uTexM * w; gl_Position = projectionMatrix * viewMatrix * w; }`,
    fragmentShader: `uniform sampler2D tRef; uniform vec3 uCol, uCam; uniform float uRef, uR; uniform vec2 uCenter; varying vec4 vUvP; varying vec3 vW;
      float h(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
      float n(vec2 p){ vec2 i=floor(p), f=fract(p); f=f*f*(3.0-2.0*f); return mix(mix(h(i),h(i+vec2(1,0)),f.x), mix(h(i+vec2(0,1)),h(i+vec2(1,1)),f.x), f.y); }
      void main(){ vec2 uv = vUvP.xy / vUvP.w; vec2 wob = vec2(n(vW.xz * 2.0), n(vW.zx * 2.0 + 7.0)) - 0.5; uv += wob * 0.006;
        vec3 r = vec3(0.0); for (int i = 0; i < 5; i++) { float a = float(i) * 1.2566; r += texture2D(tRef, uv + vec2(cos(a), sin(a)) * 0.0025 * float(i > 0)).rgb; } r /= 5.0;
        vec3 v = normalize(uCam - vW); float fr = 0.25 + 0.75 * pow(1.0 - max(v.y, 0.0), 3.0);
        float crack = smoothstep(0.035, 0.0, abs(n(vW.xz * 0.9) - 0.5)) * 0.5 + smoothstep(0.02, 0.0, abs(n(vW.xz * 2.3 + 3.0) - 0.5)) * 0.3;
        float edge = smoothstep(uR - 2.5, uR, length(vW.xz - uCenter));
        vec3 col = uCol + vec3(0.55, 0.7, 0.85) * crack * 0.35;
        col = mix(col, r, fr * uRef);
        col = mix(col, vec3(0.75, 0.82, 0.92), edge * 0.6);
        gl_FragColor = vec4(col, 1.0); }`,
  });
  const m = new THREE.Mesh(new THREE.CircleGeometry(L.lake.r + 0.35, 72), mat); m.rotation.x = -Math.PI / 2; m.position.set(L.lake.x, L.lake.y, L.lake.z); m.receiveShadow = false; scene.add(m);
  const vcam = new THREE.PerspectiveCamera(); const plane = new THREE.Plane(V(0, 1, 0), -L.lake.y);
  const bias = new THREE.Matrix4().set(0.5, 0, 0, 0.5, 0, 0.5, 0, 0.5, 0, 0, 0.5, 0.5, 0, 0, 0, 1);
  return {
    mesh: m, mat,
    render(renderer, scene, camera, strength) {
      mat.uniforms.uRef.value = strength; mat.uniforms.uCam.value.copy(camera.position);
      if (strength <= 0.001) return;
      const y0 = L.lake.y; const p = camera.position.clone(); const look = V(0, 0, -1).applyQuaternion(camera.quaternion).add(camera.position);
      const up = V(0, 1, 0).applyQuaternion(camera.quaternion);
      vcam.position.set(p.x, 2 * y0 - p.y, p.z); vcam.up.set(up.x, -up.y, up.z); vcam.lookAt(look.x, 2 * y0 - look.y, look.z);
      vcam.fov = camera.fov; vcam.aspect = camera.aspect; vcam.near = camera.near; vcam.far = camera.far; vcam.updateProjectionMatrix(); vcam.updateMatrixWorld();
      texM.copy(bias).multiply(vcam.projectionMatrix).multiply(vcam.matrixWorldInverse);
      m.visible = false; const old = renderer.getRenderTarget(); const cp = renderer.clippingPlanes;
      renderer.clippingPlanes = [plane]; renderer.setRenderTarget(rt); renderer.clear(); renderer.render(scene, vcam);
      renderer.clippingPlanes = cp; renderer.setRenderTarget(old); m.visible = true;
    }
  };
}

// ------------------------------------------------------------------ assemblage
export function buildWinterWorld(scene, renderer, W, H) {
  const L = LAYOUT;
  // terrain
  const SIZE = 300, TILES = 6, SEGT = 40, TS = SIZE / TILES;   // tuiles : seules celles dans le champ sont dessinées
  const tileGeos = [];
  for (let ti = 0; ti < TILES; ti++) for (let tj = 0; tj < TILES; tj++) {
    const g = new THREE.PlaneGeometry(TS, TS, SEGT, SEGT); g.rotateX(-Math.PI / 2);
    const cx = -SIZE / 2 + TS * (ti + 0.5), cz = -SIZE / 2 + TS * (tj + 0.5);
    const P = g.attributes.position; const N = new Float32Array(P.count * 3); const e = 0.05;
    for (let i = 0; i < P.count; i++) { const x = P.getX(i) + cx, z = P.getZ(i) + cz; P.setXYZ(i, x, groundY(x, z), z);
      const hx = groundY(x + e, z) - groundY(x - e, z), hz = groundY(x, z + e) - groundY(x, z - e); const n = V(-hx, 2 * e, -hz).normalize(); N.set([n.x, n.y, n.z], i * 3); }
    g.setAttribute('normal', new THREE.BufferAttribute(N, 3)); g.computeBoundingSphere(); tileGeos.push(g);
  }
  const snowMat = new THREE.MeshLambertMaterial({ color: 0xe9f0fb });
  snowMat.onBeforeCompile = (sh) => {
    sh.uniforms.uCamS = { value: V() }; snowMat.userData.sh = sh;
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vWS;').replace('#include <worldpos_vertex>', '#include <worldpos_vertex>\nvWS = (modelMatrix * vec4(transformed,1.0)).xyz;');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying vec3 vWS; uniform vec3 uCamS;\nfloat hs(vec3 p){ return fract(sin(dot(p, vec3(127.1,311.7,74.7)))*43758.5453); }')
      .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
        { vec3 cell = floor(vWS * 28.0); float g = hs(cell); vec3 vv = normalize(uCamS - vWS); float tw = hs(cell + floor(dot(vv, vec3(3.0, 5.0, 7.0)) * 4.0));
          totalEmissiveRadiance += vec3(0.8, 0.9, 1.0) * step(0.9975, g) * step(0.5, tw) * 1.6 * smoothstep(40.0, 4.0, length(uCamS - vWS)); }`);
  };
  const ground = new THREE.Group(); for (const g of tileGeos) { const m = new THREE.Mesh(g, snowMat); m.receiveShadow = true; ground.add(m); } scene.add(ground);
  // sapins (3 variantes, instanciés)
  const r = mulberry(5); const variants = [spruce(r, 5), spruce(r, 7), spruce(r, 9.5)];
  const treeMat = new THREE.MeshLambertMaterial({ vertexColors: true });
  const spots = [[], [], []]; let tries = 0;
  while (tries++ < 6000 && spots.flat().length < 200) {
    const x = (r() - 0.5) * 220, z = (r() - 0.5) * 220; const d0 = Math.hypot(x, z);
    if (d0 < L.clearing.r + 3) continue; if (Math.hypot(x - L.lake.x, z - L.lake.z) < L.lake.r + 3) continue; if (distToPath(x, z) < 3.5) continue;
    if (Math.hypot(x - L.cabin.x, z - L.cabin.z) < 9) continue;
    if (Math.hypot(x - L.hill.x, z - L.hill.z) < 7) continue;
    if (r() > smooth(14, 40, d0) * 0.9 + 0.1) continue;
    spots[Math.floor(r() * 3)].push([x, z, 0.8 + r() * 0.5, r() * 6.28]);
  }
  const extra = [[-15, 14], [-19, 4], [-13, -12], [3, 16], [12, 12], [-22, -22], [30, -6], [36, -30], [14, -38], [-40, -36], [-26, -54]];
  extra.forEach(([x, z], i) => spots[i % 3].push([x, z, 1.0 + (i % 3) * 0.15, i]));
  const trees = []; const CH = 30;                                   // arbres groupés par cases de 30 m (culling caméra et ombres)
  variants.forEach((vg, vi) => {
    const cells = new Map();
    for (const sp of spots[vi]) { const key = Math.floor(sp[0] / CH) + ',' + Math.floor(sp[1] / CH); if (!cells.has(key)) cells.set(key, []); cells.get(key).push(sp); }
    for (const list of cells.values()) {
      const im = new THREE.InstancedMesh(vg, treeMat, list.length); im.castShadow = true; im.receiveShadow = true;
      const o = new THREE.Object3D();
      list.forEach(([x, z, s, a], k) => { o.position.set(x, groundY(x, z) - 0.15, z); o.scale.setScalar(s); o.rotation.y = a; o.updateMatrix(); im.setMatrixAt(k, o.matrix); trees.push([x, z, s * (5 + vi * 2)]); });
      im.computeBoundingSphere(); scene.add(im);
    }
  });
  // cabane
  const cabin = buildCabin(L); scene.add(cabin.g);
  // lampadaires
  const lg = lampGeo(); const lmat = new THREE.MeshLambertMaterial({ vertexColors: true });
  const lampHeadMat = new THREE.MeshBasicMaterial({ color: new THREE.Color(3.4, 2.3, 1.2) });
  const lamps = L.lamps.map(([x, z]) => {
    const y = groundY(x, z); const m = new THREE.Mesh(lg, lmat); m.position.set(x, y, z); m.castShadow = true; scene.add(m);
    const head = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.4, 0.34), lampHeadMat.clone()); head.position.set(x, y + 3.4, z); scene.add(head);
    const pool = buildPool(scene, 0xffa85a, 4.2); pool.position.set(x, y + 0.04, z);
    return { x, z, y, head, pool, on: 1 };
  });
  // 3 vraies lumières seulement, réattribuées à chaque image aux lampadaires allumés les plus proches
  const lampLights = []; for (let i = 0; i < 3; i++) { const l = new THREE.PointLight(0xffb870, 0, 15, 1.5); scene.add(l); lampLights.push(l); }
  // fenêtres de la cabane : lumière chaude sur la neige
  const winLight = new THREE.PointLight(0xffa860, 7, 12, 1.4); winLight.position.copy(cabin.windows[0]).add(V(1.6, 0.4, -0.8)); scene.add(winLight);
  const winPool = buildPool(scene, 0xff9a50, 3.6); winPool.position.set(L.cabin.x + 0.3, groundY(L.cabin.x, L.cabin.z - 4) + 0.05, L.cabin.z - L.cabin.d / 2 - 1.8); winPool.scale.set(1.6, 1, 0.8);
  // banc
  const bench = new THREE.Mesh(benchGeo(), lmat); bench.castShadow = true; bench.receiveShadow = true;
  bench.position.set(L.bench.x, groundY(L.bench.x, L.bench.z), L.bench.z); bench.rotation.y = L.bench.yaw; scene.add(bench);
  // bonhomme de neige (près du lac)
  const snowman = buildSnowman({ hat: true }); snowman.position.set(L.snowman.x, groundY(L.snowman.x, L.snowman.z) - 0.05, L.snowman.z); snowman.rotation.y = L.snowman.yaw; scene.add(snowman);
  const sky = buildNightSky(scene);
  const snow = buildSnowfall(scene);
  const ice = buildIce(scene, renderer, L, W, H);
  // flaques de lumière libres (projecteurs, lanternes...)
  const pools = []; for (let i = 0; i < 4; i++) { const p = buildPool(scene, 0xfff2dc, 2.4); p.visible = false; pools.push(p); }
  return { L, groundY, ground, snowMat, trees, cabin, lamps, lampLights, winLight, winPool, bench, snowman, sky, snow, ice, pools };
}
