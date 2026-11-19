// Instanced crowd: hundreds of Minecraft-style people sharing a skin atlas (8x4 skins), animated per instance.
import * as THREE from 'three';
import { partGeo, paintSkin, randomSpec, PX } from './rig.js';
import { mulberry, toTex } from './textures.js';

export function buildCrowd(scene, maxN = 400, seed = 7, opts = {}) {
  const r = mulberry(seed);
  const atlas = document.createElement('canvas'); atlas.width = 512; atlas.height = 256; const g = atlas.getContext('2d');
  const specs = [];
  for (let i = 0; i < 32; i++) { const s = randomSpec(r); if (opts.pale) s.skin = [0xe6d6c8, 0xd8c8bc, 0xcab8aa, 0xbfb0a6][i % 4]; specs.push(s); g.drawImage(paintSkin(s, opts.creepy ? 'hollow' : 'neutral', 100 + i), (i % 8) * 64, Math.floor(i / 8) * 64); }
  const tex = toTex(atlas, { mip: false, repeat: false });
  const aSkin = new THREE.InstancedBufferAttribute(new Float32Array(maxN), 1);
  const mat = new THREE.MeshLambertMaterial({ map: tex });
  mat.onBeforeCompile = (sh) => {
    sh.vertexShader = 'attribute float aSkin;\n' + sh.vertexShader.replace('#include <uv_vertex>', `#include <uv_vertex>
      vMapUv = vec2((vMapUv.x + mod(aSkin, 8.0)) / 8.0, (vMapUv.y + (3.0 - floor(aSkin / 8.0 + 0.001))) / 4.0);`);
  };
  const defs = { body: [8, 12, 4, 16, 16], head: [8, 8, 8, 0, 0], armL: [4, 12, 4, 32, 48], armR: [4, 12, 4, 40, 16], legL: [4, 12, 4, 16, 48], legR: [4, 12, 4, 0, 16] };
  const parts = {};
  for (const k in defs) {
    const geo = partGeo(...defs[k]); geo.setAttribute('aSkin', aSkin);
    const im = new THREE.InstancedMesh(geo, mat, maxN); im.castShadow = true; im.receiveShadow = true; im.frustumCulled = false; im.count = 0; scene.add(im); parts[k] = im;
  }
  const people = []; for (let i = 0; i < maxN; i++) people.push({ x: 0, y: 0, z: 0, yaw: 0, phase: r() * 6.28, amp: 0, lean: 0, headYaw: 0, headPitch: 0, armL: 0, armR: 0, legs: 0, scale: 1, skin: i % 32, on: false });
  const M = new THREE.Matrix4(), R = new THREE.Matrix4(), T = new THREE.Matrix4(), base = new THREE.Matrix4(), hipsM = new THREE.Matrix4(), torsoM = new THREE.Matrix4(), tmp = new THREE.Matrix4();
  const tr = (x, y, z) => T.makeTranslation(x, y, z);
  return {
    people, specs, parts,
    clear() { for (const p of people) p.on = false; },
    update() {
      let n = 0;
      for (const p of people) {
        if (!p.on) continue;
        const s = Math.sin(p.phase) * p.amp;
        base.makeRotationY(p.yaw).premultiply(tr(p.x, p.y, p.z)); if (p.scale !== 1) base.multiply(tmp.makeScale(p.scale, p.scale, p.scale));
        hipsM.copy(base).multiply(tr(0, 12 * PX + Math.abs(Math.cos(p.phase)) * p.amp * 0.06, 0));
        torsoM.copy(hipsM).multiply(R.makeRotationX(p.lean));
        parts.body.setMatrixAt(n, M.copy(torsoM).multiply(tr(0, 6 * PX, 0)));
        parts.head.setMatrixAt(n, M.copy(torsoM).multiply(tr(0, 12 * PX, 0)).multiply(R.makeRotationY(p.headYaw)).multiply(tmp.makeRotationX(p.headPitch)).multiply(tr(0, 4 * PX, 0)));
        parts.armL.setMatrixAt(n, M.copy(torsoM).multiply(tr(6 * PX, 10 * PX, 0)).multiply(R.makeRotationX(-s * 0.85 + p.armL)).multiply(tmp.makeRotationZ(0.05)).multiply(tr(0, -4 * PX, 0)));
        parts.armR.setMatrixAt(n, M.copy(torsoM).multiply(tr(-6 * PX, 10 * PX, 0)).multiply(R.makeRotationX(s * 0.85 + p.armR)).multiply(tmp.makeRotationZ(-0.05)).multiply(tr(0, -4 * PX, 0)));
        parts.legL.setMatrixAt(n, M.copy(hipsM).multiply(tr(2 * PX, 0, 0)).multiply(R.makeRotationX(s + p.legs)).multiply(tr(0, -6 * PX, 0)));
        parts.legR.setMatrixAt(n, M.copy(hipsM).multiply(tr(-2 * PX, 0, 0)).multiply(R.makeRotationX(-s + p.legs)).multiply(tr(0, -6 * PX, 0)));
        aSkin.array[n] = p.skin; n++;
      }
      for (const k in parts) { parts[k].count = n; parts[k].instanceMatrix.needsUpdate = true; }
      aSkin.needsUpdate = true;
      return n;
    }
  };
}
