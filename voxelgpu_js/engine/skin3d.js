// Vêtements en couche 3D (comme le mod « 3D Skin Layers ») : chaque pixel de la couche extérieure
// devient un petit cube en relief, attaché à la bonne partie du corps (il suit les animations).
// Tenues : manteau, capuche, bonnet à pompon, écharpe, moufles, bottes.
import * as THREE from 'three';
import { PX } from './rig.js';

const hsh = (a, b, c) => { const s = Math.sin(a * 12.9898 + b * 78.233 + c * 37.719) * 43758.5453; return s - Math.floor(s); };

// Construit une coque de voxels autour d'une boîte (w,h,d en pixels de skin), centrée en (cx,cy,cz) (en pixels).
// fn(face, i, j, w, h) -> couleur hex ou null ; i de gauche à droite (vu de face), j de haut en bas.
function shell(w, h, d, cx, cy, cz, fn, seed, thick = 0.85) {
  const pos = [], nor = [], col = []; const c = new THREE.Color();
  const pushBox = (x, y, z, sx, sy, sz, color) => {
    c.set(color);
    const F = [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]];
    for (const [nx, ny, nz] of F) {
      // 4 coins de la face
      const ax = nx !== 0 ? [0, 1, 0] : [1, 0, 0], bx = nz !== 0 ? [0, 1, 0] : (ny !== 0 ? [0, 0, 1] : [0, 0, 1]);
      const u = nx !== 0 ? [0, 0, 1] : [1, 0, 0], v = ny !== 0 ? [0, 0, 1] : [0, 1, 0];
      const center = [x + nx * sx / 2, y + ny * sy / 2, z + nz * sz / 2];
      const hu = [u[0] * sx / 2, u[1] * sy / 2, u[2] * sz / 2], hv = [v[0] * sx / 2, v[1] * sy / 2, v[2] * sz / 2];
      let q = [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([a, b]) => [center[0] + hu[0] * a + hv[0] * b, center[1] + hu[1] * a + hv[1] * b, center[2] + hu[2] * a + hv[2] * b]);
      // orientation : normale sortante
      const e1 = [q[1][0] - q[0][0], q[1][1] - q[0][1], q[1][2] - q[0][2]], e2 = [q[2][0] - q[0][0], q[2][1] - q[0][1], q[2][2] - q[0][2]];
      const cr = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]];
      if (cr[0] * nx + cr[1] * ny + cr[2] * nz < 0) q = [q[0], q[3], q[2], q[1]];
      for (const k of [0, 1, 2, 0, 2, 3]) { pos.push(q[k][0] * PX, q[k][1] * PX, q[k][2] * PX); nor.push(nx, ny, nz); col.push(c.r, c.g, c.b); }
      void ax; void bx;
    }
  };
  const faces = {
    front: { n: [0, 0, 1], W: w, H: h, at: (i, j) => [cx - w / 2 + i + 0.5, cy + h / 2 - j - 0.5, cz + d / 2] },
    back: { n: [0, 0, -1], W: w, H: h, at: (i, j) => [cx + w / 2 - i - 0.5, cy + h / 2 - j - 0.5, cz - d / 2] },
    left: { n: [1, 0, 0], W: d, H: h, at: (i, j) => [cx + w / 2, cy + h / 2 - j - 0.5, cz + d / 2 - i - 0.5] },
    right: { n: [-1, 0, 0], W: d, H: h, at: (i, j) => [cx - w / 2, cy + h / 2 - j - 0.5, cz - d / 2 + i + 0.5] },
    top: { n: [0, 1, 0], W: w, H: d, at: (i, j) => [cx - w / 2 + i + 0.5, cy + h / 2, cz - d / 2 + j + 0.5] },
    bottom: { n: [0, -1, 0], W: w, H: d, at: (i, j) => [cx - w / 2 + i + 0.5, cy - h / 2, cz - d / 2 + j + 0.5] },
  };
  for (const name in faces) {
    const f = faces[name];
    for (let j = 0; j < f.H; j++) for (let i = 0; i < f.W; i++) {
      const color = fn(name, i, j, f.W, f.H); if (color == null) continue;
      const tk = thick * (0.8 + 0.35 * hsh(i + seed, j, name.length));
      const [x, y, z] = f.at(i, j); const [nx, ny, nz] = f.n;
      const ox = x + nx * (tk / 2 + 0.02), oy = y + ny * (tk / 2 + 0.02), oz = z + nz * (tk / 2 + 0.02);
      const sx = nx ? tk : 1.04, sy = ny ? tk : 1.04, sz = nz ? tk : 1.04;
      const cc = new THREE.Color(color).multiplyScalar(0.9 + 0.2 * hsh(i * 3 + seed, j * 5, name.length * 7));
      pushBox(ox, oy, oz, sx, sy, sz, cc);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3)); g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  g.computeBoundingSphere(); return g;
}

// outfit: { coat:{color, trim, zip}, hood:{color, fur, up}, beanie:{color, fold, pompom}, scarf:{color, stripe}, mittens, boots }
export function dressUp(ch, outfit, seed = 1) {
  const mat = new THREE.MeshLambertMaterial({ vertexColors: true });
  const add = (geo, parent, y) => { const m = new THREE.Mesh(geo, mat); m.castShadow = true; m.receiveShadow = true; m.position.y = y; parent.add(m); return m; };
  const o = outfit; const parts = [];
  // tête (coque autour de la tête : centre à 4px au-dessus du cou)
  if (o.beanie || o.hood) {
    const b = o.beanie, hd = o.hood;
    parts.push(add(shell(8, 8, 8, 0, 0, 0, (f, i, j, W, H) => {
      if (hd && hd.up) {
        if (f === 'top' || f === 'back') return hd.color;
        if (f === 'left' || f === 'right') return j < 7 ? hd.color : null;
        if (f === 'front') { if (j < 2) return hd.fur ?? hd.color; if (i === 0 || i === 7) return j < 7 ? (hd.fur ?? hd.color) : null; return null; }
        return null;
      }
      if (b) {
        if (f === 'top') return b.color;
        if (f === 'bottom') return null;
        if (j === 2) return b.fold ?? b.color;
        return j < 2 ? b.color : null;
      }
      return null;
    }, seed, 0.9), ch.neck, 4 * PX));
    if (o.beanie && o.beanie.pompom) { const pp = new THREE.Mesh(new THREE.BoxGeometry(3 * PX, 3 * PX, 3 * PX), new THREE.MeshLambertMaterial({ color: o.beanie.pompom })); pp.position.y = 9.6 * PX; pp.castShadow = true; ch.neck.add(pp); parts.push(pp); }
  }
  // torse : manteau + écharpe
  if (o.coat || o.scarf) {
    const c = o.coat, s = o.scarf;
    parts.push(add(shell(8, 12, 4, 0, 0, 0, (f, i, j, W, H) => {
      if (f === 'bottom') return null;
      if (s && j < 2 && f !== 'top') return (s.stripe && (i + j) % 3 === 0) ? s.stripe : s.color;
      if (s && f === 'top') return s.color;
      if (s && f === 'front' && i >= 5 && i <= 6 && j < 8) return (s.stripe && j % 3 === 0) ? s.stripe : s.color;   // pan de l'écharpe
      if (!c) return null;
      if (f === 'front' && c.zip && (i === 3 || i === 4)) return j % 2 ? c.trim ?? c.color : (c.trim ?? c.color);
      if (f === 'front' && c.zip === false && (i === 3) && j % 3 === 1) return c.trim ?? 0x222222;
      if (f === 'front' && j >= 8 && j <= 9 && (i === 1 || i === 6)) return c.pocket ?? c.trim ?? c.color;
      return c.color;
    }, seed + 3, 0.95), ch.torso, 6 * PX));
    if (s && s.tail) { const tail = new THREE.Mesh(new THREE.BoxGeometry(2 * PX, 7 * PX, 1 * PX), new THREE.MeshLambertMaterial({ color: s.color })); tail.position.set(-2.5 * PX, 7.5 * PX, -2.9 * PX); tail.castShadow = true; ch.torso.add(tail); parts.push(tail); ch.scarfTail = tail; }
  }
  // bras : manches + moufles
  if (o.coat || o.mittens) {
    for (const [sh, side] of [[ch.shL, 1], [ch.shR, -1]]) {
      parts.push(add(shell(4, 12, 4, 0, 0, 0, (f, i, j) => {
        if (f === 'top') return o.coat ? o.coat.color : null;
        if (j >= 10) return o.mittens ?? null;
        if (f === 'bottom') return o.mittens ?? null;
        if (!o.coat) return null;
        return j === 9 ? (o.coat.cuff ?? o.coat.trim ?? o.coat.color) : o.coat.color;
      }, seed + 5 + side, 0.85), sh, -4 * PX));
    }
  }
  // jambes : bas du manteau + bottes
  if ((o.coat && o.coat.long) || o.boots) {
    for (const [lg, side] of [[ch.lgL, 1], [ch.lgR, -1]]) {
      parts.push(add(shell(4, 12, 4, 0, 0, 0, (f, i, j) => {
        if (f === 'top' || f === 'bottom') return f === 'bottom' ? (o.boots ?? null) : null;
        if (o.boots && j >= 9) return j === 9 ? (o.bootTrim ?? o.boots) : o.boots;
        if (o.coat && o.coat.long && j < 3) return o.coat.color;
        return null;
      }, seed + 9 + side, 0.8), lg, -6 * PX));
    }
  }
  ch.outfitParts = parts;
  return ch;
}
