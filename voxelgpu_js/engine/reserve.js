// L'arrière-boutique de la station-service : une vraie pièce derrière le mur du fond de la supérette (repère local de la station).
// Intérieur x ∈ [0.6, 4.4], z ∈ [-12.0, -7.2], hauteur 2.8. On y entre par la porte du fond de la supérette (x 3.0..3.9, battant à charnière
// côté ouest qui s'ouvre vers l'intérieur) ; une porte de service donne dehors, dans le mur est (z -11.55..-10.45).
// Elle se reconnaît à son décor, sans écrire un seul mot : tableau électrique (coffret gris, levier rouge, pictogramme d'éclair), étagères métalliques
// chargées de cartons et de bidons, établi avec outils sur panneau perforé, tuyaux au plafond, fût, seau et balai, tube fluorescent.
// Les nombres sont ceux de hstudio/voxelgpu/stagegeo.py (tools/check_blocking.py compare les deux fichiers).
// Tout est fonction du temps (env : res_door, svc_door, res_tube, res_light, res_lever, svc_shake), aucun hasard hors graine fixe.
import * as THREE from 'three';
import { vox } from './props4.js';
import { mulberry } from './textures.js';

const V = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);

export const RESERVE = { x0: 0.6, x1: 4.4, z0: -12.0, z1: -7.2, h: 2.8, door: { x: 3.0, w: 0.9, h: 2.25, hinge: 'w' }, service: { z0: -11.55, z1: -10.45, h: 2.2 } };

export function buildReserve(ctx, st) {
  const R = RESERVE, g = new THREE.Group(); st.group.add(g); const r = mulberry(5);
  const W = 0x6a6c72, W2 = 0x5a5c62, F = 0x2a2c30;
  const B = [];
  // sol, plafond, murs (face intérieure plus claire que le béton extérieur)
  B.push({ x: 2.5, y: -0.04, z: -9.6, w: 4.0, h: 0.1, d: 5.0, color: F });
  B.push({ x: 2.5, y: R.h + 0.07, z: -9.6, w: 4.2, h: 0.15, d: 5.2, color: 0x3c3e44 });
  B.push({ x: R.x0 - 0.1, y: R.h / 2, z: -9.6, w: 0.2, h: R.h, d: 4.8, color: W });
  B.push({ x: 2.5, y: R.h / 2, z: R.z0 - 0.1, w: 4.2, h: R.h, d: 0.2, color: W });
  B.push({ x: R.x1 + 0.1, y: R.h / 2, z: (R.z0 - 0.2 + R.service.z0) / 2, w: 0.2, h: R.h, d: R.service.z0 - (R.z0 - 0.2), color: W });
  B.push({ x: R.x1 + 0.1, y: R.h / 2, z: (R.service.z1 + R.z1) / 2, w: 0.2, h: R.h, d: R.z1 - R.service.z1, color: W });
  B.push({ x: R.x1 + 0.1, y: (R.service.h + R.h) / 2, z: (R.service.z0 + R.service.z1) / 2, w: 0.2, h: R.h - R.service.h, d: R.service.z1 - R.service.z0, color: W });
  for (const [x, z, w, d] of [[R.x0 + 0.02, -9.6, 0.04, 4.8], [2.5, R.z0 + 0.02, 4.0, 0.04], [R.x1 - 0.02, -9.6, 0.04, 4.8]]) B.push({ x, y: 0.5, z, w, h: 1.0, d, color: 0x4c4e54 });     // soubassement
  // étagères métalliques à l'est (z -10.2 .. -8.5) : montants, quatre niveaux, cartons et bidons
  const sx = 4.15;
  for (const z of [-10.2, -8.5]) for (const dx of [-0.25, 0.25]) B.push({ x: sx + dx - 0.02, y: 0.95, z, w: 0.05, h: 1.9, d: 0.05, color: 0x3a4a6a });
  for (let lv = 0; lv < 4; lv++) {
    const y = 0.25 + lv * 0.52; B.push({ x: sx - 0.02, y, z: -9.35, w: 0.55, h: 0.04, d: 1.75, color: 0x8a8e96 });
    let z = -10.1; while (z < -8.65) { const w = 0.22 + r() * 0.28, h = 0.2 + r() * 0.2; const kind = r();
      if (kind < 0.6) B.push({ x: sx - 0.02, y: y + 0.02 + h / 2, z: z + w / 2, w: 0.42, h, d: w, color: [0xa08a60, 0x8c7850, 0xb09a70][Math.floor(r() * 3)], ry: (r() - 0.5) * 0.08 });
      else B.push({ x: sx - 0.02, y: y + 0.02 + 0.17, z: z + w / 2, w: 0.2, h: 0.34, d: Math.min(w, 0.22), color: [0xc03020, 0xd8b020, 0x2a6a3a][Math.floor(r() * 3)] });
      z += w + 0.06; } }
  // établi dans l'angle nord-ouest, panneau perforé et silhouettes d'outils, étau
  B.push({ x: 0.95, y: 0.88, z: -11.35, w: 0.7, h: 0.07, d: 1.3, color: 0x7a5a38 }); for (const [dx, dz] of [[-0.3, -0.6], [0.3, -0.6], [-0.3, 0.6], [0.3, 0.6]]) B.push({ x: 0.95 + dx, y: 0.42, z: -11.35 + dz, w: 0.06, h: 0.84, d: 0.06, color: 0x3a3c42 });
  B.push({ x: 1.45, y: 1.6, z: R.z0 + 0.03, w: 1.6, h: 0.9, d: 0.04, color: 0x4a4e58 });
  for (let i = 0; i < 5; i++) { B.push({ x: 0.9 + i * 0.28, y: 1.72, z: R.z0 + 0.07, w: 0.05, h: 0.4 - (i % 2) * 0.1, d: 0.04, color: [0xc8c8c0, 0xc03020, 0xd8b020, 0xc8c8c0, 0x2a6a9a][i] }); B.push({ x: 0.9 + i * 0.28, y: 1.48, z: R.z0 + 0.07, w: 0.12, h: 0.1, d: 0.04, color: 0x9a9aa2 }); }
  B.push({ x: 0.82, y: 0.99, z: -11.65, w: 0.14, h: 0.14, d: 0.2, color: 0x2a2a30 }, { x: 1.05, y: 0.94, z: -11.1, w: 0.04, h: 0.04, d: 0.32, color: 0x8a5a2a }, { x: 1.05, y: 0.945, z: -11.28, w: 0.1, h: 0.05, d: 0.06, color: 0xa0a0a8 });
  // fût, seau, balai, caisse
  B.push({ x: 1.8, y: 0.45, z: -8.75, w: 0.46, h: 0.9, d: 0.46, color: 0x2a4a8a }, { x: 1.8, y: 0.93, z: -8.75, w: 0.5, h: 0.06, d: 0.5, color: 0x1a2a5a });
  B.push({ x: 1.15, y: 0.14, z: -7.75, w: 0.3, h: 0.28, d: 0.3, color: 0xc8a020 }, { x: 0.78, y: 0.9, z: -7.62, w: 0.05, h: 1.8, d: 0.05, color: 0x8a6a3a }, { x: 0.78, y: 0.05, z: -7.66, w: 0.34, h: 0.1, d: 0.12, color: 0x6a5a40 });
  B.push({ x: 2.3, y: 0.2, z: -11.55, w: 0.6, h: 0.4, d: 0.4, color: 0xa08a60 }, { x: 2.35, y: 0.5, z: -11.6, w: 0.5, h: 0.2, d: 0.34, color: 0x8c7850 });
  // tuyaux au plafond, tache d'humidité (la fuite d'eau du circuit)
  B.push({ x: 2.5, y: 2.6, z: -8.6, w: 3.9, h: 0.1, d: 0.1, color: 0x5a6a7a }, { x: 2.5, y: 2.6, z: -10.3, w: 3.9, h: 0.1, d: 0.1, color: 0x5a6a7a }, { x: 1.2, y: 2.62, z: -9.5, w: 0.1, h: 0.1, d: 1.8, color: 0x7a5a3a });
  B.push({ x: 3.4, y: R.h - 0.004, z: -9.3, w: 0.95, h: 0.012, d: 0.8, color: 0x2a2a28 }, { x: 3.4, y: R.h - 0.002, z: -9.3, w: 0.55, h: 0.012, d: 0.5, color: 0x161614 });
  // tableau électrique : sur le mur ouest, face à l'est. Coffret + porte ouverte + rangées de disjoncteurs + panneau d'avertissement jaune à éclair
  const px = R.x0 + 0.08, pz = -9.0;
  B.push({ x: px, y: 1.45, z: pz, w: 0.16, h: 0.98, d: 0.7, color: 0x8a9096 }, { x: px + 0.085, y: 1.45, z: pz, w: 0.02, h: 0.88, d: 0.6, color: 0x24262a });
  for (let row = 0; row < 7; row++) for (let c = 0; c < 4; c++) B.push({ x: px + 0.1, y: 1.82 - row * 0.1, z: pz - 0.24 + c * 0.16, w: 0.03, h: 0.07, d: 0.1, color: (row + c) % 6 === 0 ? 0xd8d8d0 : 0x14161a });
  B.push({ x: px + 0.04, y: 1.45, z: pz + 0.55, w: 0.03, h: 0.98, d: 0.4, color: 0x7a8086, ry: 0.5 });                                           // porte du coffret, entrouverte
  B.push({ x: px + 0.1, y: 2.08, z: pz + 0.0, w: 0.03, h: 0.24, d: 0.3, color: 0xf0c020 }); B.push({ x: px + 0.12, y: 2.08, z: pz + 0.02, w: 0.02, h: 0.14, d: 0.04, color: 0x14120a, ry: 0.5 }, { x: px + 0.12, y: 2.03, z: pz - 0.03, w: 0.02, h: 0.06, d: 0.04, color: 0x14120a, ry: -0.5 });
  g.add(vox(B, { rim: 0.35, var: 0.04 }));
  // levier principal (rouge) du tableau : tourne selon env.res_lever
  const lever = vox([{ x: 0, y: 0, z: 0, w: 0.03, h: 0.22, d: 0.05, color: 0xd02a1e }, { x: 0, y: 0.12, z: 0, w: 0.05, h: 0.05, d: 0.09, color: 0x8a1a10 }], { rim: 0.5 }); lever.position.set(px + 0.12, 1.12, pz); g.add(lever);
  // tube fluorescent
  const tubeM = new THREE.MeshBasicMaterial({ color: new THREE.Color(3, 3, 3.2) }); const tube = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.05, 1.5), tubeM); tube.position.set(2.5, R.h - 0.1, -9.6); g.add(tube);
  g.add(vox([{ x: 2.5, y: R.h - 0.045, z: -9.6, w: 0.18, h: 0.03, d: 1.6, color: 0x2a2c30 }], { rim: 0.2 }));
  // panneau de sortie vert au-dessus de la porte de service (un pictogramme, pas un mot : un bonhomme qui court + une flèche)
  const sg = vox([{ x: 0, y: 0, z: 0, w: 0.04, h: 0.24, d: 0.62, color: 0x0a8a3a }, { x: -0.025, y: -0.02, z: 0.0, w: 0.01, h: 0.12, d: 0.06, color: 0xf0f0f0 }, { x: -0.025, y: 0.07, z: 0.0, w: 0.01, h: 0.06, d: 0.06, color: 0xf0f0f0 }, { x: -0.025, y: 0.0, z: 0.18, w: 0.01, h: 0.04, d: 0.18, color: 0xf0f0f0 }], { rim: 0.2 });
  sg.position.set(R.x1 - 0.04, R.service.h + 0.18, (R.service.z0 + R.service.z1) / 2); g.add(sg); const exitM = [sg];
  // portes. Intérieure : charnière côté ouest (x 3.0), s'ouvre vers l'intérieur de la pièce (z décroissant). Service : charnière sud (z -10.45), s'ouvre vers l'intérieur aussi
  const mkLeaf = (w, h, color, handleSide) => vox([{ x: w / 2, y: h / 2, z: 0, w, h, d: 0.06, color }, { x: handleSide, y: h * 0.48, z: 0.07, w: 0.05, h: 0.05, d: 0.1, color: 0xd0d0d0 },
    ...[0.3, 0.9, 1.5, 1.95].map((y) => ({ x: w / 2, y, z: 0.035, w: w * 0.9, h: 0.05, d: 0.02, color: 0x4e5a4a }))], { rim: 0.4 });
  const dpiv = new THREE.Group(); dpiv.position.set(R.door.x, 0, R.z1 + 0.1); dpiv.add(mkLeaf(R.door.w, R.door.h, 0x7a8a6a, R.door.w - 0.1)); g.add(dpiv);
  // plaque d'éclair sur la porte (jaune, pas de texte)
  dpiv.add(vox([{ x: R.door.w / 2, y: 1.62, z: -0.04, w: 0.3, h: 0.3, d: 0.02, color: 0xf0c020 }, { x: R.door.w / 2, y: 1.62, z: -0.055, w: 0.05, h: 0.2, d: 0.01, color: 0x14120a, ry: 0.3 }], { rim: 0.2 }));
  const spiv = new THREE.Group(); spiv.position.set(R.x1, 0, R.service.z1); spiv.rotation.order = 'YXZ';
  const sleaf = vox([{ x: 0, y: R.service.h / 2, z: -0.55, w: 0.07, h: R.service.h, d: 1.1, color: 0x3a6a5a }, { x: 0.05, y: 1.0, z: -0.25, w: 0.06, h: 0.05, d: 0.5, color: 0xd8d8d8 }, { x: -0.04, y: 1.0, z: -0.25, w: 0.06, h: 0.05, d: 0.5, color: 0xd8d8d8 }, { x: 0.04, y: 0.3, z: -0.55, w: 0.02, h: 0.1, d: 1.0, color: 0xf0c020 }, { x: 0.04, y: 1.75, z: -0.55, w: 0.02, h: 0.1, d: 1.0, color: 0xf0c020 }, { x: 0.04, y: 1.45, z: -0.55, w: 0.02, h: 0.3, d: 0.4, color: 0x14181c }], { rim: 0.5 }); spiv.add(sleaf); g.add(spiv);
  return {
    group: g, tubeM, lever, dpiv, spiv, sg,
    update(T, E) {
      const open = Math.max(0, Math.min(1, E.res_door ?? 0)), svc = Math.max(0, Math.min(1, E.svc_door ?? 0));
      dpiv.rotation.y = 1.45 * open;                                   // 1.45 rad = 83° wide open ; l'entrebâillement = 0.5 (0.72 rad : 21 cm de jour)
      spiv.rotation.y = 1.45 * svc + 0.012 * Math.sin(T * 61) * (E.svc_shake ?? 0);
      spiv.position.x = R.x1 + 0.006 * Math.sin(T * 47) * (E.svc_shake ?? 0);
      const tb = E.res_tube ?? 0; tubeM.color.setRGB(3 * tb, 3 * tb, 3.2 * tb); lever.rotation.x = -0.9 * (E.res_lever ?? 0);
    },
    lights(E) { const k = E.res_light ?? 0; return k > 0.01 ? [{ pos: st.w(2.5, 2.35, -9.6), color: 0xd8e4ff, i: 3.4 * k, dist: 7.5, decay: 1.2 }] : []; },
  };
}
