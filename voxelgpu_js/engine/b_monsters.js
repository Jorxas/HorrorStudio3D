// Archétypes de créatures NON humanoïdes, sur le squelette de NOTRE moteur (chars4.js) : mêmes os, mêmes marches, mêmes visages possibles, même grain (vox), même lumière.
//   slender, tall_hat_man, demon, crawler, hulk, wraith, many_armed, stalker, swarm_figure, child_thing, puppet, scarecrow
// Une créature = le squelette humain ENTIER (la régie le pilote comme un autre acteur : trajets, arrêts, regard, disparitions par `vis`) + des volumes ajoutés sur les os,
// des os allongés ou masqués, et une couche d'animation propre (`ch.archUpdate`, appelée à chaque image par monsterUpdate, après la pose de base de la régie).
// Les réglages arrivent déjà résolus du contrat (`def.p`, voir hstudio/voxelgpu/b_monsters.py : source unique des défauts) ; la hauteur et l'étirement sont dans `def.scale` / `def.stretch`.
// Aucun hasard hors `mulberry` à graine fixe : tout est fonction du temps.
import * as THREE from 'three';
import { vox } from './props4.js';
import { boxesGeometry } from './boxes.js';
import { mulberry } from './textures.js';
import { monsterParams } from './horror_monster.js';

const PX = 1 / 16, TAU = Math.PI * 2;
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const sm = (k) => { k = clamp(k); return k * k * (3 - 2 * k); };
const num = (v, d) => (v == null ? d : typeof v === 'number' ? v : Array.isArray(v) ? (((v[0] & 255) << 16) | ((v[1] & 255) << 8) | (v[2] & 255)) : parseInt(String(v).replace('#', ''), 16));
const shade = (h, k) => new THREE.Color(h).multiplyScalar(k).getHex();
const P_ = (b) => ({ ...b, x: b.x * PX, y: b.y * PX, z: b.z * PX, w: b.w * PX, h: b.h * PX, d: b.d * PX });
const add = (parent, boxes, o = {}) => { const m = vox(boxes.map(P_), { var: 0.05, rim: 0.45, ...o }); parent.add(m); return m; };
// boîtes lumineuses (yeux, bouches) : sans ombrage, au-dessus de 1 pour que le bloom les fasse rayonner
const glow = (parent, boxes, k = 2.4) => {
  const m = new THREE.Mesh(boxesGeometry(boxes.map(P_)), new THREE.MeshBasicMaterial({ vertexColors: true })); m.material.color.setScalar(k); m.castShadow = false; parent.add(m); return m;
};
const hide = (g) => { g.traverse((o) => { if (o.isMesh) o.visible = false; }); };
const grp = (parent, x = 0, y = 0, z = 0) => { const g = new THREE.Group(); g.position.set(x * PX, y * PX, z * PX); parent.add(g); return g; };
function paintFace(ch, draw, size = 32) {
  const c = document.createElement('canvas'); c.width = c.height = size; const g = c.getContext('2d'); draw(g, size);
  const t = new THREE.CanvasTexture(c); t.magFilter = THREE.NearestFilter; t.minFilter = THREE.NearestFilter; t.colorSpace = THREE.SRGBColorSpace;
  ch.faceMat.map = t; ch.faceMat.color.set(0xffffff); ch.faceMat.needsUpdate = true;
}
const blankFace = (ch, col) => { ch.faceMat.map = null; ch.faceMat.color.set(col); ch.faceMat.needsUpdate = true; };
// bras allongé : l'os et tout ce qui est dessous s'étirent, la main reprend sa taille ; la cinématique inverse de la régie reçoit les longueurs vraies
function longArms(ch, k, handK = 1, fingerLen = 1, fingerThin = 1) {
  for (const [sh, hand, fs, th] of [[ch.shL, ch.handL, ch.fingersL, ch.thumbL], [ch.shR, ch.handR, ch.fingersR, ch.thumbR]]) {
    sh.scale.y = k; hand.scale.set(handK, handK / k, handK);
    if (fs) for (const f of fs) f.scale.set(fingerThin, fingerLen, fingerThin); if (th) th.scale.set(fingerThin, fingerLen * 0.85, fingerThin);
  }
  if (ch.LEN) { ch.LEN.up *= k; ch.LEN.fo *= k; }
}
// une chaîne de segments (tentacule, queue, cheveux, lanière) : segments[i] = groupe articulé ; rendu par `sway`
function chain(parent, x, y, z, n, len, w, color, dir = -1) {
  const root = grp(parent, x, y, z); const segs = []; let p = root;
  for (let i = 0; i < n; i++) {
    const g = grp(p, 0, i ? dir * len : 0, 0); const ww = w * (1 - i / (n + 1.5)); add(g, [{ x: 0, y: dir * len / 2, z: 0, w: ww, h: len + 0.15, d: ww, color: shade(color, 1 - i * 0.05) }]); segs.push(g); p = g;
  }
  return { root, segs };
}
const sway = (c, T, ph, amp, spd = 1.1, along = 0.55) => { c.segs.forEach((g, i) => { g.rotation.x = amp * Math.sin(T * spd * TAU * 0.25 + ph + i * along); g.rotation.z = amp * 0.6 * Math.sin(T * spd * TAU * 0.2 + ph * 1.7 + i * along * 1.3); }); };
const gaitK = (ch) => ((ch._gait | 0) > 0 ? 1 : 0);

// ================================================================== les archétypes
export const ARCH = {
  // très grand, bras trop longs, sans visage, costume noir ; quatre tentacules fins dans le dos
  slender: {
    build(ch, P) {
      blankFace(ch, P.skin); longArms(ch, P.arm, 1, 1.9, 0.7);
      add(ch.torso, [{ x: 0, y: 6.5, z: 2.25, w: 1.0, h: 6.2, d: 0.35, color: P.accent }]);
      ch._tend = P.tentacles > 0 ? Array.from({ length: P.tentacles }, (_, i) => chain(ch.torso, (i - (P.tentacles - 1) / 2) * 2.4, 7.5 - (i % 2) * 2.5, -2.4, 6, 6.0, 2.4, shade(P.cloth, 1.6), -1)) : [];
      ch._tend.forEach((c, i) => { c.root.rotation.x = 2.2; c.root.rotation.y = (i - (P.tentacles - 1) / 2) * 0.45; });
      ch._ph = 0.3;
    },
    update(ch, T, P) {
      ch._tend.forEach((c, i) => sway(c, T, i * 1.3, 0.32, 1.0, 0.5));
      ch.neck.rotation.z += 0.12 * Math.sin(T * 0.37 + 0.6) + 0.05 * (1 - gaitK(ch)); ch.torso.rotation.x += P.hunch;
    },
  },
  // homme au chapeau haut, long visage pâle, deux yeux et un sourire fins qui brillent
  tall_hat_man: {
    build(ch, P) {
      blankFace(ch, P.skin); longArms(ch, P.arm, 1, 1.4, 0.8);
      add(ch.head, [{ x: 0, y: 4.4, z: 0, w: 11.2, h: 0.9, d: 11.2, color: P.cloth }, { x: 0, y: 8.6, z: 0, w: 7.6, h: 7.6, d: 7.6, color: P.cloth }, { x: 0, y: 5.6, z: 0, w: 7.9, h: 1.3, d: 7.9, color: P.accent }]);
      const E = [{ x: -1.9, y: 0.9, z: 4.06, w: 1.5, h: 0.7, d: 0.2, color: P.eyes }, { x: 1.9, y: 0.9, z: 4.06, w: 1.5, h: 0.7, d: 0.2, color: P.eyes },
        { x: 0, y: -2.0, z: 4.06, w: 4.4, h: 0.5, d: 0.2, color: P.eyes }, { x: -2.4, y: -1.5, z: 4.06, w: 0.6, h: 0.6, d: 0.2, color: P.eyes }, { x: 2.4, y: -1.5, z: 4.06, w: 0.6, h: 0.6, d: 0.2, color: P.eyes }];
      glow(ch.head, E, 2.2);
    },
    update(ch, T, P) { ch.neck.rotation.z += 0.08 * Math.sin(T * 0.5); ch.torso.rotation.x += P.hunch * 0.5; },
  },
  // cornes, ailes qui battent, queue, yeux incandescents, dos voûté
  demon: {
    build(ch, P) {
      blankFace(ch, P.skin);
      for (const sx of [-1, 1]) {   // cornes : trois segments qui se courbent vers l'avant
        const hb = []; for (let i = 0; i < 4; i++) hb.push({ x: sx * (2.4 + i * 0.5), y: 4.2 + i * 2.0, z: -0.8 + i * 0.9, w: 1.9 - i * 0.4, h: 2.3, d: 1.9 - i * 0.4, color: shade(P.horn, 1 - i * 0.07) }); add(ch.head, hb);
      }
      glow(ch.head, [{ x: -1.9, y: 0.6, z: 4.06, w: 1.6, h: 0.8, d: 0.2, color: P.eyes }, { x: 1.9, y: 0.6, z: 4.06, w: 1.6, h: 0.8, d: 0.2, color: P.eyes }], 2.6);
      add(ch.head, [{ x: 0, y: -2.3, z: 4.06, w: 4.6, h: 0.9, d: 0.3, color: 0x180505 }, { x: -1.7, y: -1.8, z: 4.1, w: 0.5, h: 0.9, d: 0.2, color: P.horn }, { x: 1.7, y: -1.8, z: 4.1, w: 0.5, h: 0.9, d: 0.2, color: P.horn }]);
      ch._wings = [];
      if (P.wings > 0) for (const sx of [-1, 1]) {
        const w0 = grp(ch.torso, sx * 2.6, 9.4, -2.6); const wb = [];
        // bras d'aile (humérus + avant-bras) puis trois doigts en éventail depuis le poignet, une membrane festonnée tendue entre eux
        wb.push({ x: sx * 3.2, y: 1.0, z: 0, w: 6.4, h: 1.5, d: 1.5, color: P.horn }, { x: sx * 8.6, y: 3.6, z: 0, w: 5.2, h: 1.4, d: 1.4, color: P.horn });
        for (const [ang, L] of [[0.42, 16], [-0.05, 18], [-0.55, 14]]) for (let k = 1; k <= Math.round(L / 2.6); k++) wb.push({ x: sx * (11 + Math.cos(ang) * k * 2.6), y: 4.4 + Math.sin(ang) * k * 2.6, z: 0, w: 2.8, h: 1.1, d: 1.1, color: shade(P.horn, 0.92) });
        for (let i = 0; i < 6; i++) { const top = 3.4 - i * 0.2 + (i > 3 ? -1.2 * (i - 3) : 0), bot = -7.5 + (i % 2) * 1.6 + i * 1.1; wb.push({ x: sx * (6.5 + i * 3.7), y: (top + bot) / 2, z: -0.1, w: 3.9, h: top - bot, d: 0.6, color: shade(P.wing, 1.3 - i * 0.06) }); }
        add(w0, wb, { rim: 0.6 }); w0.scale.setScalar(P.wings * 1.25); ch._wings.push([w0, sx]);
      }
      ch._tail = P.tail > 0 ? chain(ch.hips, 0, -1.5, -2.2, 6, 4.2 * P.tail, 2.4, P.skin, -1) : null; if (ch._tail) ch._tail.root.rotation.x = 2.5;
      add(ch.torso, [{ x: 0, y: 8.8, z: -2.6, w: 6.4, h: 1.4, d: 1.4, color: shade(P.skin, 0.7) }, { x: 0, y: 6, z: -2.8, w: 1.0, h: 6, d: 0.9, color: shade(P.skin, 0.65) }]);
    },
    update(ch, T, P) {
      const run = gaitK(ch), a = 0.38 + 0.3 * run, f = Math.sin(T * (2.0 + 1.4 * run) * 1.0);
      ch._wings.forEach(([w, sx]) => { w.rotation.z = sx * (0.5 + a * 0.45 * f); w.rotation.y = -sx * (0.6 + 0.12 * f); });
      if (ch._tail) sway(ch._tail, T, 0, 0.3, 1.2, 0.6);
      ch.torso.rotation.x += P.hunch; ch.neck.rotation.x -= P.hunch * 0.6;
    },
  },
  // à quatre pattes, membres tordus, tête relevée : le même squelette, mis à l'horizontale
  crawler: {
    build(ch, P) {
      blankFace(ch, P.skin);
      glow(ch.head, [{ x: -1.9, y: 0.6, z: 4.06, w: 1.4, h: 1.0, d: 0.2, color: P.eyes }, { x: 1.9, y: 0.6, z: 4.06, w: 1.4, h: 1.0, d: 0.2, color: P.eyes }], 2.0);
      add(ch.head, [{ x: 0, y: -2.2, z: 4.06, w: 4.8, h: 1.1, d: 0.3, color: 0x120505 }]);
      const sp = []; for (let i = 0; i < 6; i++) sp.push({ x: 0, y: 1.5 + i * 1.8, z: -2.5, w: 1.0 + (i % 2) * 0.6, h: 1.3, d: 1.5, color: shade(P.skin, 0.75) }); add(ch.torso, sp);
      longArms(ch, P.arm, 1.15, 1.5, 0.8);
    },
    update(ch, T, P, free) {
      const g = gaitK(ch), ph = ch._phase || 0, w = Math.sin(ph), v = Math.sin(ph + Math.PI);
      ch.hips.position.y = (P.belly + 0.4 * Math.abs(Math.sin(ph)) * g) * PX; ch.hips.rotation.x = 1.28; ch.torso.rotation.x = -0.18;
      ch.neck.rotation.x = -1.12 + 0.1 * Math.sin(T * 1.7); ch.neck.rotation.z = P.twist * (0.7 + 0.3 * Math.sin(T * 0.6));
      for (const [sh, el, s, ph2] of [[ch.shL, ch.elL, 1, w], [ch.shR, ch.elR, -1, v]]) { if (!free(s > 0 ? 'L' : 'R')) continue; sh.rotation.x = -1.28 - 0.1 + 0.55 * g * ph2; sh.rotation.z = s * -0.35; el.rotation.x = -0.15 - 0.4 * g * Math.max(0, -ph2); }
      for (const [lg, kn, s, ph2] of [[ch.lgL, ch.knL, 1, v], [ch.lgR, ch.knR, -1, w]]) { lg.rotation.x = -1.28 + 0.1 + 0.5 * g * ph2; lg.rotation.z = s * 0.25; kn.rotation.x = 0.95 + 0.5 * g * Math.max(0, ph2); }
    },
  },
  // massif : épaules, bras et mains démesurés, petite tête
  hulk: {
    build(ch, P) {
      blankFace(ch, P.skin); longArms(ch, P.arm, P.fist, 1.0, 1.25);
      paintFace(ch, (g, S) => { g.fillStyle = '#' + P.skin.toString(16).padStart(6, '0'); g.fillRect(0, 0, S, S); g.fillStyle = '#16080a'; g.fillRect(S * 0.2, S * 0.36, S * 0.2, S * 0.1); g.fillRect(S * 0.6, S * 0.36, S * 0.2, S * 0.1); g.fillRect(S * 0.22, S * 0.66, S * 0.56, S * 0.1); g.fillStyle = '#e8d8b8'; for (let i = 0; i < 4; i++) g.fillRect(S * (0.26 + i * 0.13), S * 0.62, S * 0.07, S * 0.06); });
      add(ch.torso, [{ x: -6.6, y: 11.4, z: 0, w: 4.4, h: 3.2, d: 5.4, color: shade(P.skin, 0.85) }, { x: 6.6, y: 11.4, z: 0, w: 4.4, h: 3.2, d: 5.4, color: shade(P.skin, 0.85) }, { x: 0, y: 8.8, z: 2.3, w: 8.6, h: 1.0, d: 0.7, color: shade(P.skin, 0.7) }, { x: 0, y: 5.8, z: 2.3, w: 7.2, h: 1.0, d: 0.7, color: shade(P.skin, 0.7) }]);
    },
    update(ch, T, P) { const b = Math.sin(T * 1.6) * 0.03; ch.torso.rotation.x += P.hunch + b; ch.neck.rotation.x -= P.hunch * 0.8; ch.shL.rotation.z += 0.18; ch.shR.rotation.z -= 0.18; },
  },
  // drapé flottant : pas de jambes, un linceul en lambeaux, les pieds ne touchent pas le sol
  wraith: {
    build(ch, P) {
      blankFace(ch, 0x020204); ch.lgL.visible = false; ch.lgR.visible = false; longArms(ch, P.arm, 1, 1.7, 0.7);
      const hb = [{ x: 0, y: 4.2, z: -4.8, w: 9.8, h: 9.8, d: 1.5, color: P.cloth }, { x: 0, y: 8.8, z: -0.4, w: 9.8, h: 1.6, d: 9.8, color: shade(P.cloth, 1.1) }, { x: 4.9, y: 4.2, z: -0.2, w: 1.5, h: 9.8, d: 9.6, color: shade(P.cloth, 0.9) }, { x: -4.9, y: 4.2, z: -0.2, w: 1.5, h: 9.8, d: 9.6, color: shade(P.cloth, 0.9) },
        { x: 0, y: 10.4, z: -1.2, w: 7.6, h: 2.0, d: 7.6, color: shade(P.cloth, 0.95) }, { x: 0, y: 12.2, z: -2.2, w: 4.6, h: 1.8, d: 5.4, color: shade(P.cloth, 0.9) }];
      add(ch.neck, hb);
      glow(ch.head, [{ x: -1.8, y: 0.4, z: 4.0, w: 1.4, h: 1.0, d: 0.2, color: P.eyes }, { x: 1.8, y: 0.4, z: 4.0, w: 1.4, h: 1.0, d: 0.2, color: P.eyes }], 2.6);
      ch._drape = []; const N = 7;
      for (let i = 0; i < N; i++) { const a = (i / N) * TAU, r = 4.8; const c = chain(ch.hips, Math.cos(a) * r, 1.5, Math.sin(a) * r * 0.7, 4, 4.2 + (i % 3) * 1.4, 4.2, P.cloth, -1); c.root.rotation.y = a; ch._drape.push(c); }
      add(ch.hips, [{ x: 0, y: -2, z: 0, w: 9.6, h: 5, d: 6.6, color: shade(P.cloth, 0.9) }]);
    },
    update(ch, T, P) {
      ch.root.position.y += P.float + 0.07 * Math.sin(T * 1.4); ch._drape.forEach((c, i) => sway(c, T, i * 0.9, 0.22, 0.9, 0.55));
      ch.torso.rotation.x += P.hunch; ch.neck.rotation.z += 0.1 * Math.sin(T * 0.45);
      ch.hips.rotation.x += 0.12 * gaitK(ch);
    },
  },
  // deux paires de bras supplémentaires qui bougent à leur propre rythme
  many_armed: {
    build(ch, P) {
      blankFace(ch, P.skin); longArms(ch, P.arm, 1, 1.2, 0.85);
      paintFace(ch, (g, S) => { g.fillStyle = '#' + P.skin.toString(16).padStart(6, '0'); g.fillRect(0, 0, S, S); g.fillStyle = '#0a0608'; for (let i = 0; i < 4; i++) { const x = S * (0.2 + (i % 2) * 0.4), y = S * (0.28 + Math.floor(i / 2) * 0.22); g.fillRect(x, y, S * 0.2, S * 0.12); } });
      glow(ch.head, [{ x: -1.9, y: 1.7, z: 4.05, w: 1.0, h: 0.6, d: 0.15, color: P.eyes }, { x: 1.9, y: 1.7, z: 4.05, w: 1.0, h: 0.6, d: 0.15, color: P.eyes }, { x: -1.9, y: -0.5, z: 4.05, w: 1.0, h: 0.6, d: 0.15, color: P.eyes }, { x: 1.9, y: -0.5, z: 4.05, w: 1.0, h: 0.6, d: 0.15, color: P.eyes }], 2.0);
      ch._extra = [];
      for (let i = 0; i < P.pairs; i++) for (const sx of [-1, 1]) {
        const a = grp(ch.torso, sx * 4.0, 8.2 - i * 3.6, 0.4); const up = add(a, [{ x: 0, y: -3.2, z: 0, w: 2.6, h: 6.4, d: 2.6, color: P.cloth }]); const e = grp(a, 0, -6.2, 0);
        add(e, [{ x: 0, y: -3.0, z: 0, w: 2.4, h: 6.0, d: 2.4, color: P.skin }, { x: 0, y: -6.6, z: 0, w: 2.8, h: 2.4, d: 2.6, color: shade(P.skin, 0.85) }]); ch._extra.push([a, e, sx, i]);
      }
    },
    update(ch, T, P) { ch._extra.forEach(([a, e, sx, i]) => { a.rotation.z = sx * (0.55 + 0.45 * Math.sin(T * 1.3 + i * 1.6 + sx)); a.rotation.x = -0.5 + 0.55 * Math.sin(T * 0.9 + i * 2.1 + (sx > 0 ? 0 : 1.4)); e.rotation.x = -0.7 + 0.5 * Math.sin(T * 1.7 + i + sx * 0.8); }); ch.torso.rotation.x += P.hunch; },
  },
  // tête trop grande sur un cou trop long, grands yeux sombres, corps filiforme
  stalker: {
    build(ch, P) {
      blankFace(ch, P.skin); longArms(ch, P.arm, 1, 1.5, 0.75);
      const ext = P.neck; ch.head.position.y += ext * PX; add(ch.neck, [{ x: 0, y: 2 + ext / 2, z: 0, w: 2.6, h: ext + 1, d: 2.6, color: shade(P.skin, 0.9) }]);
      paintFace(ch, (g, S) => { g.fillStyle = '#' + P.skin.toString(16).padStart(6, '0'); g.fillRect(0, 0, S, S); g.fillStyle = '#050304'; g.fillRect(S * 0.12, S * 0.3, S * 0.3, S * 0.3); g.fillRect(S * 0.58, S * 0.3, S * 0.3, S * 0.3); g.fillStyle = '#d8d4c4'; g.fillRect(S * 0.2, S * 0.4, S * 0.08, S * 0.08); g.fillRect(S * 0.66, S * 0.4, S * 0.08, S * 0.08); g.fillStyle = '#1a0a0c'; g.fillRect(S * 0.28, S * 0.78, S * 0.44, S * 0.06); });
    },
    update(ch, T, P) { const snap = Math.pow(Math.max(0, Math.sin(T * 0.7)), 12); ch.neck.rotation.z += 0.18 * Math.sin(T * 0.43) + 0.3 * snap; ch.neck.rotation.x += 0.12 * Math.sin(T * 0.9 + 1); ch.torso.rotation.x += P.hunch; },
  },
  // silhouette faite de petits cubes qui frémissent (insectes, cendres, parasites) : le squelette est invisible, la forme se recompose à chaque image
  swarm_figure: {
    build(ch, P) {
      hide(ch.root); const rnd = mulberry(77); const N = P.count;
      const vol = [[ch.torso, [0, 5.5, 0], [8, 11, 4.2], 0.27], [ch.head, [0, 0, 0], [8, 8, 8], 0.14], [ch.shL, [0, -1, 0], [3.9, 6.5, 3.9], 0.07], [ch.shR, [0, -1, 0], [3.9, 6.5, 3.9], 0.07], [ch.elL, [0, -3, 0], [3.8, 8, 3.8], 0.07], [ch.elR, [0, -3, 0], [3.8, 8, 3.8], 0.07],
        [ch.lgL, [0, -3.4, 0], [4, 7, 4], 0.09], [ch.lgR, [0, -3.4, 0], [4, 7, 4], 0.09], [ch.knL, [0, -2.8, 0], [4, 5.6, 4], 0.07], [ch.knR, [0, -2.8, 0], [4, 5.6, 4], 0.07]];
      ch._cells = []; for (const [bone, c, s, share] of vol) { const n = Math.round(N * share); for (let i = 0; i < n; i++) ch._cells.push({ bone, p: [c[0] + (rnd() - 0.5) * s[0], c[1] + (rnd() - 0.5) * s[1], c[2] + (rnd() - 0.5) * s[2]], s: 0.9 + rnd() * 1.1, ph: rnd() * TAU, sp: 2 + rnd() * 5 }); }
      const geo = new THREE.BoxGeometry(PX, PX, PX); const mat = new THREE.MeshLambertMaterial({ color: 0xffffff });
      const im = new THREE.InstancedMesh(geo, mat, ch._cells.length); const col = new THREE.Color(); const dark = new THREE.Color(P.cloth), lite = new THREE.Color(P.skin);
      ch._cells.forEach((c, i) => { col.copy(dark).lerp(lite, rnd() * 0.6); if (rnd() < 0.05) col.set(P.eyes).multiplyScalar(0.9); im.setColorAt(i, col); }); im.castShadow = true; im.frustumCulled = false; ch.root.add(im); ch._im = im;
      const eyes = grp(ch.head, 0, 0, 0); glow(eyes, [{ x: -1.9, y: 0.6, z: 4.4, w: 1.8, h: 1.4, d: 0.6, color: P.eyes }, { x: 1.9, y: 0.6, z: 4.4, w: 1.8, h: 1.4, d: 0.6, color: P.eyes }], 3.2);
      ch._m4 = new THREE.Matrix4(); ch._inv = new THREE.Matrix4(); ch._v = new THREE.Vector3(); ch._q = new THREE.Quaternion(); ch._sc = new THREE.Vector3(); ch._pos = new THREE.Vector3();
    },
    update(ch, T, P) {
      ch.root.updateMatrixWorld(true); ch._inv.copy(ch.root.matrixWorld).invert(); const im = ch._im, m = ch._m4;
      ch._cells.forEach((c, i) => {
        const j = P.jitter * 1.1, d = (a) => Math.sin(T * c.sp + c.ph * a) * j; ch._v.set(c.p[0] + d(1), c.p[1] + d(2.3), c.p[2] + d(3.1)).multiplyScalar(PX);
        ch._v.applyMatrix4(c.bone.matrixWorld).applyMatrix4(ch._inv); const s = c.s * (0.8 + 0.3 * Math.sin(T * c.sp * 0.7 + c.ph)); ch._sc.setScalar(s * 1.05); m.compose(ch._v, ch._q.identity(), ch._sc); im.setMatrixAt(i, m);
      });
      im.instanceMatrix.needsUpdate = true;
    },
  },
  // petit, grosse tête pâle, trous noirs à la place des yeux, longs bras qui pendent
  child_thing: {
    build(ch, P) {
      blankFace(ch, P.skin); longArms(ch, P.arm, 1, 1.0, 0.9);
      paintFace(ch, (g, S) => { g.fillStyle = '#' + P.skin.toString(16).padStart(6, '0'); g.fillRect(0, 0, S, S); g.fillStyle = '#030203'; g.fillRect(S * 0.16, S * 0.3, S * 0.26, S * 0.34); g.fillRect(S * 0.58, S * 0.3, S * 0.26, S * 0.34); g.fillStyle = '#5a1a1c'; g.fillRect(S * 0.32, S * 0.76, S * 0.36, S * 0.05); });
      add(ch.head, [{ x: 0, y: 4.4, z: 0, w: 8.4, h: 0.8, d: 8.4, color: shade(P.cloth, 0.6) }]);
    },
    update(ch, T, P) { const j = Math.floor(T * 7), h = Math.sin(j * 12.9898) * 43758.5453; const r = h - Math.floor(h); if (r > 0.82) ch.neck.rotation.z += 0.35 * (r - 0.82) * 5; ch.neck.rotation.x += 0.1; ch.torso.rotation.x += P.hunch; ch.shL.rotation.z += 0.12; ch.shR.rotation.z -= 0.12; },
  },
  // marionnette de bois : membres fins articulés, visage peint, fils jusqu'à une barre de commande
  puppet: {
    build(ch, P) {
      for (const g of [ch.shL, ch.shR]) { g.scale.x = 0.72; g.scale.z = 0.72; } for (const g of [ch.lgL, ch.lgR]) { g.scale.x = 0.78; g.scale.z = 0.78; }
      paintFace(ch, (g, S) => { g.fillStyle = '#' + P.skin.toString(16).padStart(6, '0'); g.fillRect(0, 0, S, S); g.fillStyle = '#1a1008'; g.fillRect(S * 0.2, S * 0.3, S * 0.18, S * 0.18); g.fillRect(S * 0.62, S * 0.3, S * 0.18, S * 0.18); g.fillStyle = '#c03030'; g.fillRect(S * 0.12, S * 0.55, S * 0.16, S * 0.12); g.fillRect(S * 0.72, S * 0.55, S * 0.16, S * 0.12); g.fillRect(S * 0.28, S * 0.72, S * 0.44, S * 0.08); });
      const pts = [[ch.head, 0, 4.6, 0], [ch.handL, 0, -2.5, 0], [ch.handR, 0, -2.5, 0], [ch.knL, 0, 0, 1.6], [ch.knR, 0, 0, 1.6]];
      ch._strings = pts.map(() => { const m = new THREE.Mesh(new THREE.BoxGeometry(0.012, 1, 0.012), new THREE.MeshBasicMaterial({ color: 0xcfc8b4 })); m.castShadow = false; m.frustumCulled = false; ch.root.add(m); return m; });
      ch._pts = pts; ch._bar = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.03, 0.05), new THREE.MeshBasicMaterial({ color: 0x6a4a2a })); ch._bar.castShadow = false; ch.root.add(ch._bar);
      ch._v1 = new THREE.Vector3(); ch._v2 = new THREE.Vector3(); ch._inv = new THREE.Matrix4();
    },
    update(ch, T, P) {
      const j = (a) => Math.sin(T * 5.3 + a) * Math.sin(T * 1.7 + a * 2);
      ch.neck.rotation.z += 0.12 * j(0.4); ch.shL.rotation.z += 0.1 * j(1.3); ch.shR.rotation.z -= 0.1 * j(2.2); ch.elL.rotation.x -= 0.15 * Math.abs(j(3)); ch.elR.rotation.x -= 0.15 * Math.abs(j(4));
      ch.root.updateMatrixWorld(true); ch._inv.copy(ch.root.matrixWorld).invert(); const top = P.string * 2.1, wob = 0.05 * Math.sin(T * 1.1);
      ch._bar.position.set(wob, top * 1 / ch.root.scale.y, 0); const bw = [[0, 0], [-0.22, 0.0], [0.22, 0.0], [-0.12, 0.08], [0.12, -0.08]];
      ch._pts.forEach(([bone, x, y, z], i) => { ch._v1.set(x * PX, y * PX, z * PX).applyMatrix4(bone.matrixWorld).applyMatrix4(ch._inv); ch._v2.set(bw[i][0] + wob, ch._bar.position.y, bw[i][1]);
        const s = ch._strings[i]; const d = ch._v2.clone().sub(ch._v1); const L = d.length(); s.position.copy(ch._v1).addScaledVector(d, 0.5); s.scale.set(1, L, 1); s.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.normalize()); });
    },
  },
  // épouvantail : sac sur la tête, paille aux poignets, bras en croix, démarche raide
  scarecrow: {
    build(ch, P) {
      paintFace(ch, (g, S) => { g.fillStyle = '#' + P.skin.toString(16).padStart(6, '0'); g.fillRect(0, 0, S, S); g.fillStyle = '#120a06'; for (const x of [0.2, 0.62]) { g.fillRect(S * x, S * 0.3, S * 0.18, S * 0.18); g.fillStyle = P.skin ? '#' + shade(P.skin, 1.2).toString(16).padStart(6, '0') : '#aa9'; g.fillRect(S * (x + 0.04), S * 0.34, S * 0.1, S * 0.03); g.fillStyle = '#120a06'; }
        g.fillRect(S * 0.2, S * 0.7, S * 0.6, S * 0.06); for (let i = 0; i < 5; i++) g.fillRect(S * (0.22 + i * 0.12), S * 0.66, S * 0.04, S * 0.14); });
      const straw = P.accent, tufts = []; for (let i = 0; i < 6; i++) tufts.push({ x: (i - 2.5) * 1.4, y: -1.4 - (i % 2) * 1.0, z: 0.9 * (i % 3 - 1), w: 0.7, h: 3.0, d: 0.7, color: shade(straw, 0.85 + 0.12 * (i % 3)) });
      for (const hd of [ch.handL, ch.handR]) add(hd, tufts); add(ch.neck, tufts.map((t) => ({ ...t, y: 1.4 + (t.y + 1.4) * -1, h: 2.4 })));
      add(ch.head, [{ x: 0, y: 4.5, z: 0, w: 12.4, h: 0.8, d: 12.4, color: shade(P.cloth, 0.7) }, { x: 0, y: 7.0, z: 0, w: 7.4, h: 4.6, d: 7.4, color: shade(P.cloth, 0.85) }, { x: 0, y: 5.2, z: 0, w: 7.8, h: 1.0, d: 7.8, color: P.accent }]);
      longArms(ch, P.arm, 1, 1.0, 1.0);
    },
    update(ch, T, P, free) { if (free('L')) { ch.shL.rotation.z += 1.35; ch.shL.rotation.x *= 0.2; } if (free('R')) { ch.shR.rotation.z -= 1.35; ch.shR.rotation.x *= 0.2; } ch.neck.rotation.z += 0.2 * Math.sin(T * 0.8) * 0.5 + 0.12; ch.torso.rotation.z += 0.05 * Math.sin(T * 0.9); },
  },
};

export function buildArchetype(buildCharacter4, def, seed = 80) {
  const A = ARCH[def.archetype]; if (!A) throw new Error(`archétype inconnu : ${def.archetype} (disponibles : ${Object.keys(ARCH).join(', ')})`);
  const P = { ...(def.p || {}) }; for (const k of ['skin', 'cloth', 'cloth2', 'accent', 'eyes', 'horn', 'wing', 'boots']) if (k in P) P[k] = num(P[k], 0x808080);
  const top = P.coat === false ? { type: 'tshirt', color: P.cloth } : { type: P.top || 'coat', color: P.cloth, shirt: P.accent };
  const ch = buildCharacter4({ skin: P.skin, brow: P.skin, hair: null, hat: null, top, pants: { color: P.cloth2 ?? shade(P.cloth, 0.85) }, shoes: { type: 'boot', color: P.boots ?? 0x0c0c10 } }, seed);
  ch.setExpr = () => {}; ch.faceUpdate = () => {}; ch.isArchetype = def.archetype; ch.P = P;
  A.build(ch, P);
  ch.headScale = P.head ?? 1;
  ch.monster = { ...monsterParams({}), hunch: 0, head_tilt: 0, shoulder_drop: 0, finger_twitch: 0, stillness: 1, poses: [], vanish: def.vanish || [] };
  ch.archUpdate = (T, free) => { if (A.update) A.update(ch, T, P, free); };
  const reset0 = ch.reset; ch.reset = () => { reset0(); ch._fresh = true; };
  return ch;
}
