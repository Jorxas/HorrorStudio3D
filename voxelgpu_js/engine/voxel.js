// Generic voxel world + registry-driven chunked mesher with per-vertex ambient occlusion.
import * as THREE from 'three';

export class World {
  constructor(x0, x1, y0, y1, z0, z1) {
    Object.assign(this, { X0: x0, X1: x1, Y0: y0, Y1: y1, Z0: z0, Z1: z1 });
    this.NX = x1 - x0; this.NY = y1 - y0; this.NZ = z1 - z0;
    this.d = new Uint8Array(this.NX * this.NY * this.NZ);
  }
  idx(x, y, z) { return ((x - this.X0) * this.NY + (y - this.Y0)) * this.NZ + (z - this.Z0); }
  inb(x, y, z) { return x >= this.X0 && x < this.X1 && y >= this.Y0 && y < this.Y1 && z >= this.Z0 && z < this.Z1; }
  get(x, y, z) { if (!this.inb(x, y, z)) return y < this.Y0 ? 1 : 0; return this.d[this.idx(x, y, z)]; }
  set(x, y, z, v) { x = Math.floor(x); y = Math.floor(y); z = Math.floor(z); if (this.inb(x, y, z)) this.d[this.idx(x, y, z)] = v; }
  setIfAir(x, y, z, v) { x = Math.floor(x); y = Math.floor(y); z = Math.floor(z); if (this.inb(x, y, z)) { const i = this.idx(x, y, z); if (!this.d[i]) this.d[i] = v; } }
  fill(x0, y0, z0, x1, y1, z1, v) { // inclusive-exclusive box
    for (let x = Math.min(x0, x1); x < Math.max(x0, x1); x++) for (let y = Math.min(y0, y1); y < Math.max(y0, y1); y++) for (let z = Math.min(z0, z1); z < Math.max(z0, z1); z++) this.set(x, y, z, v);
  }
}

// Block registry --------------------------------------------------------
// def: { name, top, side, bottom, mode: 'opaque'|'cutout'|'water', glow: bool }
export const REG = [null];
export const ID = {};
export function defBlock(name, def) {
  const d = { name, mode: 'opaque', ...def }; d.top = d.top || d.all; d.side = d.side || d.all; d.bottom = d.bottom || d.all;
  REG.push(d); ID[name] = REG.length - 1; return ID[name];
}

const FACES = [
  { n: [1, 0, 0], c: [[1, 0, 1], [1, 0, 0], [1, 1, 0], [1, 1, 1]] },
  { n: [-1, 0, 0], c: [[0, 0, 0], [0, 0, 1], [0, 1, 1], [0, 1, 0]] },
  { n: [0, 1, 0], c: [[0, 1, 1], [1, 1, 1], [1, 1, 0], [0, 1, 0]] },
  { n: [0, -1, 0], c: [[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]] },
  { n: [0, 0, 1], c: [[0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]] },
  { n: [0, 0, -1], c: [[1, 0, 0], [0, 0, 0], [0, 1, 0], [1, 1, 0]] },
];
const UVS = [[0, 0], [1, 0], [1, 1], [0, 1]];
const AO = [0.45, 0.64, 0.82, 1.0];
function h3(x, y, z) { let h = Math.imul(x | 0, 374761393) + Math.imul(y | 0, 668265263) + Math.imul(z | 0, 2147483647); h = Math.imul(h ^ (h >>> 13), 1274126177); return ((h ^ (h >>> 16)) >>> 0) / 4294967296; }

// textures: { key: THREE.Texture }, glowKeys: set of texture keys rendered with emissive
export function buildWorldMesh(w, textures, scene, { chunk = 16, glow = {} } = {}) {
  const opaque = new Uint8Array(REG.length); const cut = new Uint8Array(REG.length);
  REG.forEach((d, i) => { if (!d) return; opaque[i] = d.mode === 'opaque' ? 1 : 0; cut[i] = d.mode === 'cutout' ? 1 : 0; });
  const buckets = new Map();
  const occ = (x, y, z) => { const t = w.get(x, y, z); return opaque[t] ? 1 : 0; };
  const { X0, X1, Y0, Y1, Z0, Z1, NY, NZ } = w;
  for (let x = X0; x < X1; x++) for (let y = Y0; y < Y1; y++) for (let z = Z0; z < Z1; z++) {
    const t = w.d[((x - X0) * NY + (y - Y0)) * NZ + (z - Z0)]; if (!t) continue;
    const def = REG[t]; const jit = 0.93 + h3(x, y, z) * 0.09;
    for (let f = 0; f < 6; f++) {
      const F = FACES[f]; const nx = x + F.n[0], ny = y + F.n[1], nz = z + F.n[2];
      const nt = w.get(nx, ny, nz);
      if (def.mode === 'water') { if (f !== 2 || nt) continue; }
      else if (def.mode === 'cutout') { if (opaque[nt] || nt === t) continue; }
      else { if (opaque[nt]) continue; if (f === 3 && y <= Y0) continue; }
      const key = f === 2 ? def.top : f === 3 ? def.bottom : def.side;
      const bkey = key + '|' + Math.floor((x - X0) / chunk) + '_' + Math.floor((z - Z0) / chunk);
      let bk = buckets.get(bkey); if (!bk) { bk = { key, pos: [], nor: [], uv: [], col: [], idx: [] }; buckets.set(bkey, bk); }
      const base = bk.pos.length / 3; const ax = f < 2 ? 0 : f < 4 ? 1 : 2; const t1 = ax === 0 ? 1 : 0, t2 = ax === 2 ? 1 : 2;
      const aos = [];
      for (let i = 0; i < 4; i++) {
        const c = F.c[i]; let py = y + c[1]; if (def.mode === 'water' && c[1] === 1) py = y + 0.82;
        bk.pos.push(x + c[0], py, z + c[2]); bk.nor.push(F.n[0], F.n[1], F.n[2]); bk.uv.push(UVS[i][0], UVS[i][1]);
        const o = [nx, ny, nz]; const s1 = [...o], s2 = [...o], cc = [...o]; const d1 = c[t1] ? 1 : -1, d2 = c[t2] ? 1 : -1;
        s1[t1] += d1; s2[t2] += d2; cc[t1] += d1; cc[t2] += d2;
        const a = occ(...s1), b = occ(...s2), co = occ(...cc); const lvl = (a && b) ? 0 : 3 - (a + b + co); aos.push(lvl);
        const br = (def.mode === 'water' || def.glow) ? 1 : AO[lvl] * jit; bk.col.push(br, br, br);
      }
      if (aos[0] + aos[2] < aos[1] + aos[3]) bk.idx.push(base + 1, base + 2, base + 3, base + 1, base + 3, base);
      else bk.idx.push(base, base + 1, base + 2, base, base + 2, base + 3);
    }
  }
  const mats = {}; const group = new THREE.Group();
  const matFor = (key) => {
    if (mats[key]) return mats[key];
    const tex = textures[key]; let m;
    if (key.startsWith('water')) m = new THREE.MeshStandardMaterial({ map: tex, vertexColors: true, transparent: true, opacity: 0.85, roughness: 0.1, color: 0xcfeeff });
    else if (key.startsWith('leaves') || key.startsWith('cut_')) m = new THREE.MeshLambertMaterial({ map: tex, vertexColors: true, alphaTest: 0.5, side: THREE.DoubleSide });
    else if (glow[key]) { m = new THREE.MeshLambertMaterial({ map: tex, vertexColors: true, emissive: 0xffffff, emissiveMap: glow[key] === true ? tex : glow[key], emissiveIntensity: 0 }); m.userData.glow = true; }
    else m = new THREE.MeshLambertMaterial({ map: tex, vertexColors: true });
    if (!tex) console.warn('missing texture', key);
    mats[key] = m; return m;
  };
  for (const bk of buckets.values()) {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(bk.pos, 3)); g.setAttribute('normal', new THREE.Float32BufferAttribute(bk.nor, 3));
    g.setAttribute('uv', new THREE.Float32BufferAttribute(bk.uv, 2)); g.setAttribute('color', new THREE.Float32BufferAttribute(bk.col, 3));
    g.setIndex(bk.idx); g.computeBoundingSphere();
    const mesh = new THREE.Mesh(g, matFor(bk.key)); mesh.castShadow = !bk.key.startsWith('water'); mesh.receiveShadow = true; group.add(mesh);
  }
  scene.add(group);
  return { group, mats };
}
