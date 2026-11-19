// Petit assembleur de géométrie « voxel » : une liste de boîtes colorées -> une seule BufferGeometry
// (positions, normales, couleurs par sommet). Sert aux décors, aux accessoires et aux couches 3D des skins.
import * as THREE from 'three';

const FACES = [
  { n: [1, 0, 0], v: [[1, -1, 1], [1, -1, -1], [1, 1, -1], [1, 1, 1]], shade: 0.86 },
  { n: [-1, 0, 0], v: [[-1, -1, -1], [-1, -1, 1], [-1, 1, 1], [-1, 1, -1]], shade: 0.86 },
  { n: [0, 1, 0], v: [[-1, 1, 1], [1, 1, 1], [1, 1, -1], [-1, 1, -1]], shade: 1.0 },
  { n: [0, -1, 0], v: [[-1, -1, -1], [1, -1, -1], [1, -1, 1], [-1, -1, 1]], shade: 0.7 },
  { n: [0, 0, 1], v: [[-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]], shade: 0.93 },
  { n: [0, 0, -1], v: [[1, -1, -1], [-1, -1, -1], [-1, 1, -1], [1, 1, -1]], shade: 0.93 },
];

// boxes: [{ x, y, z (centre), w, h, d, color (hex ou THREE.Color), rx?, ry?, rz?, skip?: [indices de faces] }]
export function boxesGeometry(boxes, { bakeShade = false } = {}) {
  const pos = [], nor = [], col = []; const c = new THREE.Color(); const m = new THREE.Matrix4(), e = new THREE.Euler(), v = new THREE.Vector3(), nn = new THREE.Vector3();
  const nm = new THREE.Matrix3();
  for (const b of boxes) {
    c.set(b.color);
    const hasRot = b.rx || b.ry || b.rz;
    if (hasRot) { e.set(b.rx || 0, b.ry || 0, b.rz || 0); m.makeRotationFromEuler(e); nm.setFromMatrix4(m); }
    FACES.forEach((f, fi) => {
      if (b.skip && b.skip.includes(fi)) return;
      const q = f.v.map(([sx, sy, sz]) => {
        v.set(sx * b.w / 2, sy * b.h / 2, sz * b.d / 2); if (hasRot) v.applyMatrix4(m);
        return [v.x + b.x, v.y + b.y, v.z + b.z];
      });
      nn.set(...f.n); if (hasRot) nn.applyMatrix3(nm);
      const s = bakeShade ? f.shade : 1;
      for (const idx of [0, 1, 2, 0, 2, 3]) { pos.push(...q[idx]); nor.push(nn.x, nn.y, nn.z); col.push(c.r * s, c.g * s, c.b * s); }
    });
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  g.computeBoundingSphere();
  return g;
}

export function boxesMesh(boxes, mat = null, opts = {}) {
  const m = new THREE.Mesh(boxesGeometry(boxes, opts), mat || new THREE.MeshLambertMaterial({ vertexColors: true }));
  m.castShadow = true; m.receiveShadow = true; return m;
}

// variation de couleur douce (bruit) pour éviter les aplats
export function jitter(hex, amt, seed) { const c = new THREE.Color(hex); const s = Math.sin(seed * 91.7) * 43758.5453; const f = 1 + ((s - Math.floor(s)) - 0.5) * 2 * amt; return c.multiplyScalar(f); }
