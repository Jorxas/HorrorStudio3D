// Relief du visage : la face avant de la tête est remplacée par une « plaque » finement maillée qui porte la MÊME texture (face4.js) mais dont chaque sommet est
// repoussé vers l'avant selon un champ de hauteurs : nez, arcades sourcilières, orbites creuses, paupières, pommettes, lèvres, menton, front. La lumière, les ombres et la
// silhouette (vue de profil, trois quarts) font alors le volume : le visage n'est plus un dessin collé sur un bloc. Le champ de hauteurs suit l'expression (face4.js
// paramètres) : paupières qui s'abaissent, sourcils qui descendent, lèvres qui s'ouvrent ou se plissent (menton), pommettes qui montent au sourire, plis du nez.
// Rien ici n'est aléatoire ; rien n'est appliqué si globalThis.HS_FACE_LEGACY (rendu d'avant à l'identique).
import * as THREE from 'three';
import { PX } from './rig.js';

const gs = (x, y, cx, cy, sx, sy) => Math.exp(-0.5 * (((x - cx) / sx) ** 2 + ((y - cy) / sy) ** 2));
const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const sstep = (a, b, x) => { const t = clamp((x - a) / (b - a)); return t * t * (3 - 2 * t); };

export function buildFaceRelief(head, faceMat, N = 44) {
  const n1 = N + 1, S = 8;                                   // la tête fait 8 px ; coordonnées en px, origine au centre de la tête, face avant à z = +4
  const X = new Float32Array(n1 * n1), Y = new Float32Array(n1 * n1), pos = new Float32Array(n1 * n1 * 3), uv = new Float32Array(n1 * n1 * 2), fade = new Float32Array(n1 * n1); const idx = [];
  for (let j = 0; j < n1; j++) for (let i = 0; i < n1; i++) {
    const k = j * n1 + i, x = -S / 2 + S * i / N, y = S / 2 - S * j / N; X[k] = x; Y[k] = y; uv[k * 2] = i / N; uv[k * 2 + 1] = 1 - j / N;
    fade[k] = sstep(0, 0.9, S / 2 - Math.abs(x)) * sstep(0, 0.9, S / 2 - Math.abs(y));        // le relief s'efface au bord pour raccorder la plaque à la tête
    pos[k * 3] = x * PX; pos[k * 3 + 1] = y * PX; pos[k * 3 + 2] = (S / 2) * PX;
  }
  for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) { const a = j * n1 + i, b = (j + 1) * n1 + i, c = j * n1 + i + 1, d = (j + 1) * n1 + i + 1; idx.push(a, b, c, c, b, d); }
  const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.BufferAttribute(pos, 3)); geo.setAttribute('uv', new THREE.BufferAttribute(uv, 2)); geo.setIndex(idx);
  const mesh = new THREE.Mesh(geo, faceMat); mesh.castShadow = false; mesh.receiveShadow = true; head.add(mesh);   // le relief ne projette PAS d'ombre (le nez noircissait la lèvre) : il reçoit celles des cheveux et du corps

  const update = (P) => {
    const oh = Math.max(0, P.mo) * 22 / 16, my = -2.0 - clamp(P.ms, -1, 1) * 0.0;               // ligne de bouche (px), ouverture
    const lipw = Math.max(0.5, 1.5 * P.mw), close = clamp(1 - P.eo) + P.lidd * 0.15, smile = Math.max(0, P.ms), chin = P.chin || 0;
    const by = 1.5 - (P.bi + P.bo) * 0.5 / 16 * 0.9 - (P.knit || 0) * 0.12;                      // hauteur des arcades : suit les sourcils
    const tilt = (P.tilt || 0) * 0.1;
    for (let k = 0; k < n1 * n1; k++) {
      const x = X[k], y = Y[k]; let h = 0.02;
      h += 0.3 * gs(x, y, 0, -0.5, 0.55, 1.1) + 0.17 * gs(x, y, 0, -1.05, 0.7, 0.5) + 0.06 * (gs(x, y, -0.85, -1.12, 0.34, 0.3) + gs(x, y, 0.85, -1.12, 0.34, 0.3)) + 0.12 * (P.nl || 0) * (gs(x, y, -0.7, -0.6, 0.35, 0.6) + gs(x, y, 0.7, -0.6, 0.35, 0.6));  // nez (+ plis)
      h += 0.26 * (gs(x, y, -1.65, by - tilt * (-1.65 > 0 ? -1 : 1), 1.15, 0.28) + gs(x, y, 1.65, by + tilt, 1.15, 0.28)) + 0.14 * (P.knit || 0) * gs(x, y, 0, 1.3, 0.5, 0.6);                // arcades, entre-sourcils
      for (const sx of [-1, 1]) {
        h -= 0.14 * gs(x, y, sx * 1.56, 0.35, 0.95, 0.7);                                                                   // orbite creuse
        h += (0.06 + 0.14 * close) * gs(x, y, sx * 1.56, 0.8 - close * 0.55, 0.9, 0.26);                                    // paupière : bombée, descend quand l'œil se ferme
        h += (0.15 + 0.2 * smile + 0.06 * (P.blush || 0)) * gs(x, y, sx * 2.25, -1.15, 0.85, 0.8);                           // pommette (monte au sourire)
        if ((P.bags || 0) > 0.05) h += 0.05 * P.bags * gs(x, y, sx * 1.56, -0.45, 0.9, 0.2);                                  // cernes
      }
      h += 0.1 * gs(x, y, 0, my + 0.05, lipw * 0.9, 0.34) + (0.13 + 0.07 * chin) * gs(x, y, 0, my - 0.38 - oh, lipw * 0.9, 0.36);          // lèvres du haut et du bas
      if (oh > 0.02) h -= 0.18 * Math.min(1, oh * 2) * gs(x, y, 0, my - oh * 0.5 - 0.1, lipw * 0.75, Math.max(0.2, oh * 0.5));         // cavité de la bouche ouverte
      h += (0.13 + 0.05 * chin) * gs(x, y, 0, -3.3 + chin * 0.1, 1.0, 0.65) + 0.09 * chin * gs(x, y, 0, -2.9, 0.9, 0.5);                  // menton (se plisse, pleurs)
      h += 0.1 * gs(x, y, 0, 2.6, 2.2, 1.2) - 0.07 * (gs(x, y, -2.6, -2.3, 0.7, 0.5) + gs(x, y, 2.6, -2.3, 0.7, 0.5)) * Math.max(0, smile);   // front ; plis aux commissures
      pos[k * 3 + 2] = (S / 2 + (globalThis.HS_RELIEF_K ?? 1) * h * fade[k]) * PX;   // HS_RELIEF_K : intensité du relief (contrat : relief_k), 1 par défaut
    }
    geo.attributes.position.needsUpdate = true; geo.computeVertexNormals();
  };
  return { mesh, update };
}
