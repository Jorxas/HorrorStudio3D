// Personnages et créatures de PIXEL 3D dans le peintre VOXEL (voir hstudio/voxelgpu/b_chars.py).
//   * attachCastExtras : accroche aux os d'un personnage de chars4.js les boîtes que le contrat lui donne (`def.bx`) :
//       head  -> chapeau, coiffure, lunettes, barbe (repère du centre de la tête, accroché au cou, comme les cheveux)
//       torso -> tenue (jupe, robe, armure, blouse...), sac, cape (repère du bassin, comme le torse)
//       hold  -> objet tenu : il suit la paume de la main principale (`handR`) en gardant l'orientation du personnage, comme dans PIXEL 3D ; main refermée
//       lumières tenues (lampe torche, bougie, torche, bâton) : `ch.heldLights`, lues par film_unified.js à chaque image
//   * buildAnimal : un animal = un vrai squelette de chars4.js caché (toute l'animation du film marche telle quelle : marche, course, regard...) + des poses de boîtes :
//       12 poses de marche (choisies par la phase de marche), 12 de repos (choisies par le temps). Rien n'est aléatoire : fonction pure du temps et de la phase.
import * as THREE from 'three';
import { boxesGeometry } from './boxes.js';
import { vox } from './props4.js';
import { PX } from './rig.js';

const hex = (v, d) => (typeof v === 'string' ? parseInt(v.replace('#', ''), 16) : (v ?? d));

// boîtes { x, y, z, w, h, d, color, emis? } (+ plaques d'image) -> groupe ; les boîtes émissives sont peintes sans ombrage pour que le bloom les fasse rayonner
export function boxesGroup(boxes, decals, o = {}) {
  const g = new THREE.Group(); const solid = []; const glow = new Map(); const clear = [];
  for (const b of boxes || []) {
    const bb = { ...b, color: hex(b.color, 0x808080) };
    if (b.alpha < 1) clear.push(bb);
    else if (b.emis > 0) { const k = Math.round(b.emis * 4) / 4; if (!glow.has(k)) glow.set(k, []); glow.get(k).push(bb); } else solid.push(bb);
  }
  if (solid.length) g.add(vox(solid, { rim: o.rim ?? 0.5, var: o.var ?? 0.06 }));
  for (const [k, list] of glow) { const m = new THREE.Mesh(boxesGeometry(list), new THREE.MeshBasicMaterial({ vertexColors: true })); m.material.color.setScalar(Math.max(1, k * 1.3)); m.castShadow = false; g.add(m); }
  if (clear.length) { const m = new THREE.Mesh(boxesGeometry(clear), new THREE.MeshLambertMaterial({ vertexColors: true, transparent: true, opacity: clear[0].alpha, depthWrite: false })); m.castShadow = false; m.renderOrder = 2; g.add(m); }
  for (const d of decals || []) {
    const bin = atob(d.rgba); const u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
    const t = new THREE.DataTexture(u, d.tw, d.th, THREE.RGBAFormat); t.colorSpace = THREE.SRGBColorSpace; t.magFilter = t.minFilter = THREE.NearestFilter; t.needsUpdate = true;
    const pl = new THREE.Mesh(new THREE.PlaneGeometry(d.w, d.h), new THREE.MeshLambertMaterial({ map: t, transparent: true })); pl.position.set(d.x, d.y, d.z); pl.rotation.y = d.ry || 0; g.add(pl);
  }
  return g;
}

const wrap = (ch, name, fn) => { const f0 = ch[name]; ch[name] = (...a) => { const r = f0 ? f0(...a) : undefined; fn(...a); return r; }; };

export function attachCastExtras(ch, def) {
  const bx = def.bx; if (!bx) return;
  if (bx.head && bx.head.length) { const g = boxesGroup(bx.head); g.position.y = 4 * PX; ch.neck.add(g); }
  if (bx.torso && bx.torso.length) ch.torso.add(boxesGroup(bx.torso));
  if (bx.hold && bx.hold.length) {
    const held = new THREE.Group(); held.add(boxesGroup(bx.hold, bx.hold_decals || null, { rim: 0.4 })); ch.root.add(held);      // `hold_decals` : écran, étiquette, page d'un objet détaillé (b_objets.py) ; absent = comme avant
    const palm = new THREE.Object3D(); palm.position.set(0, -1.3 * PX, 0.6 * PX); ch.handR.add(palm);              // paume de la main principale (PIXEL 3D : main droite du personnage = handR)
    const tmp = new THREE.Vector3();
    ch.heldUpdate = () => { ch.root.updateMatrixWorld(true); palm.getWorldPosition(tmp); held.position.copy(ch.root.worldToLocal(tmp)); };
    ch.heldLights = (bx.hold_lights || []).map((l) => { const o = new THREE.Object3D(); o.position.set(...l.at); held.add(o); return { obj: o, color: hex(l.color, 0xffffff), i: l.i, dist: l.dist }; });
    wrap(ch, 'faceUpdate', () => { ch.heldUpdate(); ch.setHand('R', 'grip'); });
  }
}

export function buildAnimal(buildCharacter4, def, seed) {
  const ch = buildCharacter4({ skin: 0x808080, hair: null }, seed);                      // le squelette (os, longueurs, API d'animation) ; ses volumes sont cachés
  ch.root.traverse((o) => { if (o.isMesh) o.visible = false; });
  const F = def.frames; const mkSet = (list) => list.map((fr) => { const g = boxesGroup(fr.boxes, fr.decals, { rim: 0.35, var: 0.05 }); g.visible = false; ch.root.add(g); return g; });
  const walk = mkSet(F.walk); const idle = F.idle === F.walk ? walk : mkSet(F.idle); let cur = null;
  const TAU = Math.PI * 2;
  wrap(ch, 'faceUpdate', (t) => {
    const gait = ch._gait | 0; let g;
    if (gait > 0) { const ph = (((ch._phase || 0) / TAU) % 1 + 1) % 1; g = walk[Math.floor(ph * walk.length) % walk.length]; }
    else g = idle[Math.floor(Math.max(0, t) * (F.idle_hz || 8)) % idle.length];
    if (g !== cur) { if (cur) cur.visible = false; g.visible = true; cur = g; }
  });
  ch.isAnimal = true;
  return ch;
}
