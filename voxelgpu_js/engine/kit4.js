// Kit v4 : textures pixel « sales » (grain, taches, rouille), boîtes texturées regroupées par matériau,
// et liseré lumineux (fresnel) partagé par tous les matériaux du style « illustrations ».
import * as THREE from 'three';
import { mulberry } from './textures.js';

// ------------------------------------------------------------------ liseré (rim) global, réglé par plan
export const RIM = { color: { value: new THREE.Color(1.0, 0.08, 0.05) }, strength: { value: 0.0 }, power: { value: 2.6 }, wet: { value: 0.0 },
  spark: { value: 0.0 }, sparkCol: { value: new THREE.Color(1.0, 0.35, 0.25) }, sparkDen: { value: 0.06 }, sparkSize: { value: 0.025 }, time: { value: 0 } };
// liseré fresnel + paillettes « mouillées » (gouttelettes qui scintillent, en espace monde) ; wet = densité relative du matériau
export function rimify(mat, k = 1, wet = 1) {
  mat.userData.rimK = k; mat.userData.wet = wet;
  const prev = mat.onBeforeCompile;
  mat.onBeforeCompile = (sh, r) => {
    if (prev) prev(sh, r);
    sh.uniforms.uRimCol = RIM.color; sh.uniforms.uRimStr = RIM.strength; sh.uniforms.uRimPow = RIM.power; sh.uniforms.uRimK = { value: k };
    sh.uniforms.uSpark = RIM.spark; sh.uniforms.uSparkCol = RIM.sparkCol; sh.uniforms.uSparkDen = RIM.sparkDen; sh.uniforms.uSparkSize = RIM.sparkSize; sh.uniforms.uSparkT = RIM.time; sh.uniforms.uWetK = { value: wet };
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vWPs;').replace('#include <project_vertex>', '#include <project_vertex>\nvWPs = (modelMatrix * vec4(transformed, 1.0)).xyz;');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', `#include <common>
      uniform vec3 uRimCol, uSparkCol; uniform float uRimStr, uRimPow, uRimK, uSpark, uSparkDen, uSparkSize, uSparkT, uWetK; varying vec3 vWPs;
      float sph(vec3 p){ return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }`)
      .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
        { float rimF = 1.0 - clamp(dot(normalize(normal), normalize(vViewPosition)), 0.0, 1.0); totalEmissiveRadiance += uRimCol * uRimStr * uRimK * pow(rimF, uRimPow);
          if (uSpark > 0.0 && uWetK > 0.0) { vec3 q = vWPs / uSparkSize; vec3 cell = floor(q); float h = sph(cell);
            if (h > 1.0 - uSparkDen * uWetK) { vec3 f = fract(q) - 0.5; float d = length(f - (vec3(sph(cell + 1.7), sph(cell + 3.1), sph(cell + 5.3)) - 0.5) * 0.5);
              float tw = 0.35 + 0.65 * pow(0.5 + 0.5 * sin(uSparkT * (2.0 + h * 9.0) + h * 80.0), 3.0);
              float vd = length(vViewPosition); float rad = 0.07 + 0.05 * clamp(vd * 0.15, 0.0, 1.0);
              totalEmissiveRadiance += uSparkCol * uSpark * tw * smoothstep(rad, rad * 0.3, d) * (0.5 + h * 2.0) * smoothstep(0.7, 1.6, vd); } } }`);
  };
  mat.customProgramCacheKey = () => 'rim' + k + 'w' + wet;
  return mat;
}

// ------------------------------------------------------------------ texture « voxel » procédurale (style skin Minecraft) :
// chaque cellule de 1 px (1/16 m) dans l'espace de l'objet reçoit une nuance (paliers), indépendante des UV ;
// option écossais (motif aligné sur la grille). Se combine avec rimify.
export function voxify(mat, o = {}) {
  const U = { uPx: { value: o.px ?? 1 / 16 }, uVar: { value: o.var ?? 0.12 }, uLev: { value: o.levels ?? 4 }, uSeed: { value: o.seed ?? 0 },
    uPlaid: { value: o.plaid ? 1 : 0 }, uPA: { value: new THREE.Color(o.plaid?.[0] ?? 0) }, uPB: { value: new THREE.Color(o.plaid?.[1] ?? 0) }, uPL: { value: new THREE.Color(o.plaid?.[2] ?? 0) }, uPer: { value: o.per ?? 2 }, uDiss: { value: 0 }, uOff: { value: new THREE.Vector3(...(o.off ?? [0, 0, 0])) } };
  mat.userData.vox = U;
  const prev = mat.onBeforeCompile, prevKey = mat.customProgramCacheKey ? mat.customProgramCacheKey.bind(mat) : null;
  mat.onBeforeCompile = (sh, r) => {
    if (prev) prev(sh, r);
    Object.assign(sh.uniforms, U);
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vOP; varying vec3 vON;').replace('#include <begin_vertex>', '#include <begin_vertex>\nvOP = position; vON = normal;');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', `#include <common>
      varying vec3 vOP; varying vec3 vON; uniform float uPx, uVar, uLev, uSeed, uPlaid, uPer, uDiss; uniform vec3 uPA, uPB, uPL, uOff;
      float vh3(vec3 p){ return fract(sin(dot(p, vec3(127.1, 311.7, 74.7)) + uSeed * 13.7) * 43758.5453); }`)
      .replace('#include <color_fragment>', `#include <color_fragment>
      { vec3 an = abs(vON); vec3 cp = floor((vOP - vON * 0.3 * uPx) / uPx + uOff + 0.001);
        float h = floor(vh3(cp) * uLev) / max(uLev - 1.0, 1.0);
        if (uDiss > 0.0 && fract(sin(dot(cp, vec3(12.9898, 78.233, 37.719))) * 43758.5453) < uDiss) discard;
        if (uPlaid > 0.5) { vec2 q = an.x > 0.5 ? cp.zy : (an.y > 0.5 ? cp.xz : cp.xy); vec2 m = mod(q, uPer * 2.0);
          float bx = step(uPer, m.x), by = step(uPer, m.y); vec3 pc = mix(uPA, uPB, (bx + by) * 0.5);
          if (m.x < 0.5 || m.y < 0.5) pc = mix(pc, uPL, (m.x < 0.5 && m.y < 0.5) ? 0.85 : 0.55); diffuseColor.rgb *= pc; }
        diffuseColor.rgb *= 1.0 + uVar * (h * 2.0 - 1.0); }`);
  };
  mat.customProgramCacheKey = () => (prevKey ? prevKey() : '') + '|vox' + (o.plaid ? 'p' : '');
  return mat;
}

// ------------------------------------------------------------------ textures pixel
const cvs = (w, h) => { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; };
export function pixTex(c, { repeat = true } = {}) {
  const t = new THREE.CanvasTexture(c); t.magFilter = THREE.NearestFilter; t.minFilter = THREE.NearestMipmapLinearFilter; t.generateMipmaps = true;
  t.colorSpace = THREE.SRGBColorSpace; if (repeat) t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 8; t.needsUpdate = true; return t;
}
const C3 = (hex) => [(hex >> 16) & 255, (hex >> 8) & 255, hex & 255];
// grain de base + taches sombres + rouille (style « grunge » des illustrations)
export function grunge(base, { size = 32, noise = 0.16, dark = 0.12, rust = 0, rustCol = 0x7a2a12, seed = 1, specks = 0.0, speckCol = 0xffffff } = {}) {
  const c = cvs(size, size), g = c.getContext('2d'), im = g.createImageData(size, size), r = mulberry(seed), b = C3(base), rc = C3(rustCol), sc = C3(speckCol);
  const blob = []; for (let i = 0; i < 6; i++) blob.push([r() * size, r() * size, 2 + r() * size * 0.25]);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    let f = 1 - noise + r() * noise * 2; let col = b.slice();
    for (const [bx, by, br] of blob) { const d = Math.hypot(x - bx, y - by); if (d < br) f *= 1 - dark * (1 - d / br) * (0.6 + r() * 0.8); }
    if (rust > 0 && r() < rust) col = rc.map((v, i) => v * 0.7 + b[i] * 0.3);
    let o = col.map((v) => Math.max(0, Math.min(255, v * f)));
    if (specks > 0 && r() < specks) o = sc;
    const i = (y * size + x) * 4; im.data[i] = o[0]; im.data[i + 1] = o[1]; im.data[i + 2] = o[2]; im.data[i + 3] = 255;
  }
  g.putImageData(im, 0, 0); return pixTex(c);
}
export function plaid(a, b, line, { size = 16, seed = 2 } = {}) {
  const c = cvs(size, size), g = c.getContext('2d'), im = g.createImageData(size, size), r = mulberry(seed);
  const A = C3(a), Bc = C3(b), L = C3(line);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const bx = Math.floor(x / 4) % 2, by = Math.floor(y / 4) % 2; let col = bx ^ by ? A : Bc; if (x % 8 === 0 || y % 8 === 0) col = L;
    const f = 0.9 + r() * 0.2; const i = (y * size + x) * 4; im.data[i] = col[0] * f; im.data[i + 1] = col[1] * f; im.data[i + 2] = col[2] * f; im.data[i + 3] = 255;
  }
  g.putImageData(im, 0, 0); return pixTex(c);
}
export function tiles(a, b, { size = 32, n = 4, seed = 3, grout = 0x222226 } = {}) {
  const c = cvs(size, size), g = c.getContext('2d'), im = g.createImageData(size, size), r = mulberry(seed); const A = C3(a), Bc = C3(b), G = C3(grout); const s = size / n;
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const tx = Math.floor(x / s), ty = Math.floor(y / s); let col = (tx + ty) % 2 ? A : Bc; if (x % s === 0 || y % s === 0) col = G;
    const f = 0.88 + r() * 0.24; const i = (y * size + x) * 4; im.data[i] = col[0] * f; im.data[i + 1] = col[1] * f; im.data[i + 2] = col[2] * f; im.data[i + 3] = 255;
  }
  g.putImageData(im, 0, 0); return pixTex(c);
}
// étiquette de produit (boîte, paquet) : couleurs vives + bandes + « logo »
export function productTex(seed) {
  const r = mulberry(seed * 13 + 7); const size = 16; const c = cvs(size, size), g = c.getContext('2d');
  const pal = [0xd82a2a, 0xf0c020, 0x2a6ad8, 0x2ab04a, 0xf07a1a, 0x8a3ad0, 0xe8e8e8, 0x1a1a1a, 0x20b8c8, 0xe85a9a];
  const col = (h) => '#' + h.toString(16).padStart(6, '0');
  const a = pal[Math.floor(r() * pal.length)], b = pal[Math.floor(r() * pal.length)], d = pal[Math.floor(r() * pal.length)];
  g.fillStyle = col(a); g.fillRect(0, 0, size, size); g.fillStyle = col(b); g.fillRect(0, Math.floor(r() * 6) + 2, size, 3 + Math.floor(r() * 4));
  g.fillStyle = col(d); g.fillRect(4 + Math.floor(r() * 4), 5 + Math.floor(r() * 4), 4 + Math.floor(r() * 3), 3 + Math.floor(r() * 3));
  g.fillStyle = '#ffffff'; for (let i = 0; i < 3; i++) g.fillRect(2 + Math.floor(r() * 10), 12 + Math.floor(r() * 3), 1 + Math.floor(r() * 3), 1);
  return pixTex(c, { repeat: false });
}

// ------------------------------------------------------------------ boîtes texturées, regroupées par matériau
// UV en mètres x texelsPerMeter / taille de la texture : les textures « carrelées » ont la même échelle partout.
const FACES = [
  { n: [1, 0, 0], u: [0, 0, -1], v: [0, 1, 0] }, { n: [-1, 0, 0], u: [0, 0, 1], v: [0, 1, 0] },
  { n: [0, 1, 0], u: [1, 0, 0], v: [0, 0, -1] }, { n: [0, -1, 0], u: [1, 0, 0], v: [0, 0, 1] },
  { n: [0, 0, 1], u: [1, 0, 0], v: [0, 1, 0] }, { n: [0, 0, -1], u: [-1, 0, 0], v: [0, 1, 0] },
];
export class Batch {
  constructor() { this.groups = new Map(); }
  // b: { x,y,z (centre), w,h,d, mat (clé), tpm (texels par mètre / taille texture), color (teinte), rx,ry,rz, fit (une seule fois la texture par face) }
  add(b) { if (!this.groups.has(b.mat)) this.groups.set(b.mat, []); this.groups.get(b.mat).push(b); return this; }
  build(mats, parent, { cast = true, receive = true, noCast = [] } = {}) {
    const out = [];
    for (const [key, list] of this.groups) {
      const pos = [], nor = [], uv = [], col = []; const m = new THREE.Matrix4(), e = new THREE.Euler(), nm = new THREE.Matrix3(), v = new THREE.Vector3(), nv = new THREE.Vector3(), c = new THREE.Color();
      for (const b of list) {
        e.set(b.rx || 0, b.ry || 0, b.rz || 0); m.makeRotationFromEuler(e); nm.setFromMatrix4(m); c.set(b.color ?? 0xffffff);
        const half = [b.w / 2, b.h / 2, b.d / 2]; const tpm = b.tpm ?? 0.5;
        FACES.forEach((f, fi) => {
          if (b.skip && b.skip.includes(fi)) return;
          const cn = f.n.map((k, i) => k * half[i]); const U = f.u.map((k, i) => k * half[i]), Vv = f.v.map((k, i) => k * half[i]);
          const uLen = 2 * Math.hypot(...U), vLen = 2 * Math.hypot(...Vv);
          const corners = [[-1, -1], [1, -1], [1, 1], [-1, 1]];
          const q = corners.map(([a, bb]) => { v.set(cn[0] + U[0] * a + Vv[0] * bb, cn[1] + U[1] * a + Vv[1] * bb, cn[2] + U[2] * a + Vv[2] * bb).applyMatrix4(m); return [v.x + b.x, v.y + b.y, v.z + b.z]; });
          const uvq = corners.map(([a, bb]) => b.fit ? [(a + 1) / 2, (bb + 1) / 2] : [(a + 1) / 2 * uLen * tpm + (b.uo || 0), (bb + 1) / 2 * vLen * tpm + (b.vo || 0)]);
          nv.set(...f.n).applyMatrix3(nm);
          for (const k of [0, 1, 2, 0, 2, 3]) { pos.push(...q[k]); nor.push(nv.x, nv.y, nv.z); uv.push(...uvq[k]); col.push(c.r, c.g, c.b); }
        });
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
      g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2)); g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3)); g.computeBoundingSphere();
      const mesh = new THREE.Mesh(g, mats[key]); mesh.castShadow = cast && !noCast.includes(key); mesh.receiveShadow = receive; parent.add(mesh); out.push(mesh);
    }
    return out;
  }
}
// matériau standard v4 : texture pixel + teinte par sommet + liseré
export function mat4(map, { color = 0xffffff, emissive = 0x000000, emissiveIntensity = 1, rim = 1, wet = 1, transparent = false, side = THREE.FrontSide, shininess = 0, specular = 0x000000 } = {}) {
  const m = shininess > 0 ? new THREE.MeshPhongMaterial({ map, color, vertexColors: true, emissive, emissiveIntensity, shininess, specular, transparent, side })
    : new THREE.MeshLambertMaterial({ map, color, vertexColors: true, emissive, emissiveIntensity, transparent, side });
  return rimify(m, rim, wet);
}
