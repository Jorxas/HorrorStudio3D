// Costumes de bal du XVIIIe siècle, version VOXEL native (voir hstudio/engines/pixel3d/costumes.py pour la logique commune
// et hstudio/voxelgpu/b_costumes.py pour le contrat). Rien n'est décidé ici : la forme vient du costume résolu (`def.costume`),
// l'évasement de la jupe et les accessoires tenus viennent du contrat image par image (`st.costume[id]`). Fonction pure du temps.
//   * robe à paniers : corsage satiné, plastron en pointe, encolure carrée bordée de dentelle, manches au coude ou au poignet à volants,
//     jupe en cloche faite de LÉS (panneaux) articulés : à la taille (poussés par les cuisses, ex. assis) et aux paniers (évasement de la
//     valse + poussés par les jambes). Les jambes ne peuvent pas sortir de la jupe : chaque lé est poussé au-delà du point de jambe le plus
//     proche (+ son épaisseur), à chaque image, d'après la pose réelle des jambes.
//   * redingote : revers, boutons dorés, gilet, col montant, jabot, parements, basques (les panneaux arrière suivent la cuisse qui recule),
//     culotte, bas, bottes ou souliers, épaulettes.
//   * coiffures en cubes (boucles, chignon, catogan, houppe, afro en couronne...), barbes, boucles d'oreilles, voile translucide semé de
//     pois, couronne de fleurs, accessoires tenus (flûte, verre à vin, bouquet, éventail, lettre).
import * as THREE from 'three';
import { boxesGeometry } from './boxes.js';
import { rimify, voxify } from './kit4.js';
import { mulberry } from './textures.js';
import { PX } from './rig.js';
import { exprParams, blinkAmount, saccade, talkMouth } from './face4.js';

const col = (v, d = 0x808080) => (v == null ? d : typeof v === 'number' ? v : parseInt(String(v).replace('#', ''), 16));
const shade = (h, f) => { const c = new THREE.Color(h); c.multiplyScalar(f); return c; };
const mixc = (a, b, k) => new THREE.Color(a).lerp(new THREE.Color(b), k);
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const wrapA = (a) => { a = (a + Math.PI) % (2 * Math.PI); if (a < 0) a += 2 * Math.PI; return a - Math.PI; };
// une boîte en PX (repère du groupe) -> boîte de boxes.js en mètres
const B = (x, y, z, w, h, d, color, o = {}) => ({ x: x * PX, y: y * PX, z: z * PX, w: w * PX, h: h * PX, d: d * PX, color, ...o });

const MATS = {};
function mat(kind, seed = 0, extra = null) {
  const key = kind + '|' + seed + '|' + (extra ? JSON.stringify(extra) : ''); if (MATS[key]) return MATS[key];
  let m;
  // liseré (rim) réduit sur les tissus : les petits cubes de dentelle et de volants offrent beaucoup de faces rasantes, et le contre-jour de scène
  // (theatre_kit : RIM jusqu'à 0,39) les faisait briller comme des néons ; le satin garde un peu plus de liseré que la dentelle
  if (kind === 'satin') m = voxify(rimify(new THREE.MeshPhongMaterial({ vertexColors: true, shininess: 52, specular: 0x4a3e30 }), 0.6, 0.55), { var: 0.05, levels: 3, seed });          // satin : reflets plus francs (itération 2)
  else if (kind === 'gold') m = voxify(rimify(new THREE.MeshPhongMaterial({ vertexColors: true, shininess: 70, specular: 0x8a7040 }), 0.45, 0.4), { var: 0.04, levels: 2, seed });
  else if (kind === 'plaid') m = voxify(rimify(new THREE.MeshPhongMaterial({ vertexColors: true, shininess: 26, specular: 0x241e1a }), 0.6, 0.5), { var: 0.04, levels: 3, seed, plaid: extra, per: 2 });
  else if (kind === 'veil') { m = new THREE.MeshLambertMaterial({ vertexColors: true, transparent: true, opacity: 0.24, depthWrite: false, side: THREE.DoubleSide }); }
  else if (kind === 'glass') { m = new THREE.MeshPhongMaterial({ vertexColors: true, transparent: true, opacity: 0.55, shininess: 90, specular: 0xffffff, depthWrite: false }); }
  else if (kind === 'hair') m = voxify(rimify(new THREE.MeshLambertMaterial({ vertexColors: true }), 1, 0.5), { var: 0.05, levels: 3, seed });
  else m = voxify(rimify(new THREE.MeshLambertMaterial({ vertexColors: true }), 0.35, 0.5), { var: 0.07, levels: 3, seed });
  MATS[key] = m; return m;
}
// Un tissu est mat : la composante la plus claire d'une couleur de costume est plafonnée (blanc de dentelle ≈ 0,64 en lumière linéaire, comme un vrai
// tissu blanc) ; sinon une poursuite de scène brûle la dentelle, les jabots et les robes ivoire jusqu'au seuil du bloom (halo de néon). Les couleurs plus
// sombres que le plafond ne changent pas.
const MATTE = 0.82;
export function matte(c, cap = MATTE) {
  const h = typeof c === 'number' ? c : new THREE.Color(c).getHex(); let r = (h >> 16) & 255, g = (h >> 8) & 255, b = h & 255; const m = Math.max(r, g, b) / 255;
  if (m <= cap) return h; const f = cap / m; r = Math.round(r * f); g = Math.round(g * f); b = Math.round(b * f); return (r << 16) | (g << 8) | b;
}
let KEEP = null;                                                                 // la peau du personnage en cours de construction n'est pas un tissu : jamais plafonnée
function mesh(boxes, m, cast = true) { for (const b of boxes) if (!(KEEP && typeof b.color === 'number' && KEEP.has(b.color))) b.color = matte(b.color); const o = new THREE.Mesh(boxesGeometry(boxes), m); o.castShadow = cast; o.receiveShadow = true; return o; }

// ------------------------------------------------------------------------------------------------ jupe en cloche (repère du bassin)
const N_GORES = 24;
const WAIST = [3.2, 4.7, 2.7];                                                   // y, demi-largeur (x), demi-profondeur (z) en PX
const UP = [[3.2, 4.7, 2.7], [2.2, 6.4, 4.6], [0.6, 8.0, 6.2], [-1.2, 9.0, 7.2]];
const LO = [[-1.2, 9.0, 7.2], [-4.0, 9.8, 8.1], [-7.0, 10.4, 8.8], [-10.0, 10.9, 9.4], [-13.4, 11.4, 10.0]];
const R_of = (th, a, b) => 1 / Math.sqrt((Math.sin(th) / a) ** 2 + (Math.cos(th) / b) ** 2);
const LEG_M = 3.0;                                                              // demi-épaisseur d'une jambe + demi-épaisseur d'un lé

function buildSkirt(ch, C, seed) {
  const root = new THREE.Group(); ch.hips.add(root);
  const r = mulberry(seed * 13 + 5); const gores = [];
  const skirt = col(C.colors.skirt), pet = C.colors.petticoat ? col(C.colors.petticoat) : null, trim = col(C.colors.trim, shade(skirt, 0.85).getHex());
  const plaid = C.plaid ? C.plaid.map((c) => col(c)) : null;
  const m = plaid ? mat('plaid', seed, plaid) : mat('satin', seed);
  const veil = C.colors.veil ? col(C.colors.veil) : null;
  for (let i = 0; i < N_GORES; i++) {
    const th = (2 * Math.PI * i) / N_GORES, front = Math.abs(wrapA(th));
    const pleat = i % 2 ? 0.2 : 0, tone = i % 2 ? 0.94 : 1.02;
    const G = new THREE.Group(); G.rotation.y = th; root.add(G);
    const Rw = R_of(th, WAIST[1], WAIST[2]);
    const W = new THREE.Group(); W.position.set(0, WAIST[0] * PX, Rw * PX); G.add(W);                // charnière de taille
    const segs = (prof, y0, r0, part) => {
      const out = [];
      for (let k = 0; k < prof.length - 1; k++) {
        const [ya, aa, ba] = prof[k], [yb, ab, bb] = prof[k + 1]; const RA = R_of(th, aa, ba), RB = R_of(th, ab, bb);
        const L = Math.hypot(ya - yb, RB - RA) + 0.4, tilt = Math.atan2(RB - RA, ya - yb), Rm = (RA + RB) / 2;
        const f = part === 'lo' ? (k + 0.5) / (prof.length - 1) : -0.2;
        const open = 0.1 + 0.62 * Math.max(0, f);
        let c = plaid ? 0xffffff : shade(skirt, tone).getHex();
        if (pet && front < open) c = shade(pet, tone).getHex();
        else if (pet && front < open + 0.26 && part === 'lo') c = shade(skirt, 0.78).getHex();          // bord de l'ouverture (parement)
        out.push(B(0, (ya + yb) / 2 - y0, Rm - r0 + pleat, (2 * Math.PI * Rm / N_GORES) * 1.24, L, 0.9, c, { rx: -tilt }));
      }
      return out;
    };
    const mu = mesh(segs(UP, WAIST[0], Rw, 'up'), m); mu.userData.skirt = true; W.add(mu);
    const Rh = R_of(th, LO[0][1], LO[0][2]);
    const Hn = new THREE.Group(); Hn.position.set(0, (LO[0][0] - WAIST[0]) * PX, (Rh - Rw) * PX); W.add(Hn);       // charnière des paniers
    const lo = segs(LO, LO[0][0], Rh, 'lo');
    const [yl, al, bl] = LO[LO.length - 1], Rl = R_of(th, al, bl);
    lo.push(B(0, yl - LO[0][0] + 0.5, Rl - Rh + pleat + 0.25, (2 * Math.PI * Rl / N_GORES) * 1.26, 1.2, 1.2, trim));            // ourlet
    const ml = mesh(lo, m); ml.userData.skirt = true; Hn.add(ml);
    if (veil && front > Math.PI - 0.75) {                                                                      // voile de mariée : il descend jusqu'au sol sur l'arrière de la jupe
      const vb = [], dots = [];
      for (let k = 0; k < LO.length - 1; k++) {
        const [ya, aa, ba] = LO[k], [yb, ab, bb] = LO[k + 1]; const RA = R_of(th, aa, ba) + 1.1, RB = R_of(th, ab, bb) + 1.25;
        const tilt = Math.atan2(RB - RA, ya - yb), Rm = (RA + RB) / 2, L = Math.hypot(ya - yb, RB - RA) + 0.3;
        vb.push(B(0, (ya + yb) / 2 - LO[0][0], Rm - Rh, (2 * Math.PI * Rm / N_GORES) * 1.18, L, 0.25, veil, { rx: -tilt }));
        if (C.veil_dots !== false) for (let q = 0; q < 2; q++) dots.push(B((r() - 0.5) * 2.2, (ya + yb) / 2 - LO[0][0] + (r() - 0.5) * 2.2, Rm - Rh + 0.18, 0.32, 0.32, 0.12, 0xffffff, { rx: -tilt }));
      }
      Hn.add(mesh(vb, mat('veil'), false)); if (dots.length) Hn.add(mesh(dots, mat('cloth', 3), false));
    }
    gores.push({ th, W, Hn, Rw, Rh });
  }
  // ceinture de taille : cache la jonction corsage / jupe
  root.add(mesh([B(0, WAIST[0] + 0.15, 0, 2 * WAIST[1] + 0.6, 1.1, 2 * WAIST[2] + 0.6, col(C.colors.belt || C.colors.bodice))], C.colors.belt ? mat('gold', seed) : mat('satin', seed)));
  return { root, gores };
}

// points des jambes (repère du personnage, PX) : cuisses, genoux, tibias, chevilles, talons, pointes ; marge = demi-épaisseur
const LEG_PTS = [['lg', 0, -1.0, 0], ['lg', 0, -3.4, 0], ['lg', 0, -5.6, 0], ['kn', 0, 0, 0], ['kn', 0, -2.75, 0], ['kn', 0, -4.6, 0], ['ft', 0, 0, 0], ['ft', 0, -1.9, -2.3], ['toe', 0, 0.2, 2.0]];
const _v = new THREE.Vector3();
function legPoints(ch, frame, only = null) {
  const out = [];
  for (const side of only ? [only] : ['L', 'R']) {
    const g = { lg: side === 'L' ? ch.lgL : ch.lgR, kn: side === 'L' ? ch.knL : ch.knR, ft: side === 'L' ? ch.ftL : ch.ftR, toe: side === 'L' ? ch.toeL : ch.toeR };
    for (const [k, x, y, z] of LEG_PTS) { if (!g[k]) continue; _v.set(x * PX, y * PX, z * PX); g[k].localToWorld(_v); frame.worldToLocal(_v); out.push([_v.x / PX, _v.y / PX, _v.z / PX]); }
  }
  return out;
}

const _qh = new THREE.Quaternion(), _qy = new THREE.Quaternion(), _UPV = new THREE.Vector3(0, 1, 0);
const HEM_Y = LO[LO.length - 1][0] - LO[0][0] - 0.25, HEM_Z = -0.5, HEM_M = 0.3;   // point le plus bas d'un lé (repère des paniers, PX, prudent) ; marge au sol
function updateSkirt(ch, S, fl, sit, yawW) {
  const af = Math.abs(fl);
  // la jupe pend d'aplomb : elle suit le bassin en lacet (et l'évasement), pas en roulis ni en tangage (sinon l'ourlet plonge sous le sol à chaque pas)
  _qh.setFromEuler(ch.hips.rotation); _qy.setFromAxisAngle(_UPV, ch.hips.rotation.y - 0.18 * fl); S.root.quaternion.copy(_qh).invert().multiply(_qy);
  // bassin bas (à genoux, par terre) : la jupe se tasse jusqu'au sol et s'étale autour, sans jamais passer sous le plancher ; sur un siège elle garde
  // sa longueur (elle couvre les genoux et retombe devant les tibias) et seul le garde-fou du plancher, lé par lé, raccourcit l'arrière
  const c0 = Math.min(1, Math.max(0.12, (ch.hips.position.y / PX - 0.6) / 13.4)), c = c0 + (1 - c0) * clamp(sit, 0, 1);
  S.root.scale.set(1 + 0.55 * (1 - c), c, 1 + 0.55 * (1 - c));                     // ourlet à 0,5 px au-dessus du sol
  S.root.updateMatrixWorld(true); ch.root.updateMatrixWorld(true);
  const pts = legPoints(ch, S.root); const n = S.gores.length, step = (2 * Math.PI) / n;
  const pushW = new Float32Array(n), pushH = new Float32Array(n);
  for (const [x, y, z] of pts) {
    const rad = Math.hypot(x, z), al = Math.atan2(x, z);
    for (let i = 0; i < n; i++) {
      const g = S.gores[i], d = wrapA(al - g.th); if (Math.abs(d) > 2.2 * step) continue;
      const q = rad * Math.cos(d) + LEG_M;
      if (y > LO[0][0]) {            // partie haute (taille -> paniers) : charnière de taille
        let RA = null; for (let k = 0; k < UP.length - 1; k++) if (y <= UP[k][0] && y >= UP[k + 1][0]) { const u = (UP[k][0] - y) / (UP[k][0] - UP[k + 1][0]); RA = R_of(g.th, UP[k][1] + (UP[k + 1][1] - UP[k][1]) * u, UP[k][2] + (UP[k + 1][2] - UP[k][2]) * u); }
        if (RA === null || q <= RA) continue;
        const A = Math.max(0.6, WAIST[0] - y), Bc = RA - g.Rw; const need = q - g.Rw, hyp = Math.hypot(A, Bc);
        pushW[i] = Math.max(pushW[i], Math.max(0, Math.asin(clamp(need / hyp, -1, 1)) - Math.atan2(Bc, A)));
      } else {
        let RL = null; for (let k = 0; k < LO.length - 1; k++) if (y <= LO[k][0] && y >= LO[k + 1][0] - 1.5) { const u = clamp((LO[k][0] - y) / (LO[k][0] - LO[k + 1][0]), 0, 1); RL = R_of(g.th, LO[k][1] + (LO[k + 1][1] - LO[k][1]) * u, LO[k][2] + (LO[k + 1][2] - LO[k][2]) * u); }
        if (RL === null) continue;
        const Rh = g.Rh + (WAIST[0] - LO[0][0]) * Math.sin(pushW[i]);
        if (q <= RL + (Rh - g.Rh)) continue;
        const A = Math.max(0.6, LO[0][0] - y), Bc = RL - g.Rh; const need = q - Rh, hyp = Math.hypot(A, Bc);
        pushH[i] = Math.max(pushH[i], Math.max(0, Math.asin(clamp(need / hyp, -1, 1)) - Math.atan2(Bc, A)) + 0.02);
      }
    }
  }
  const fall = [1, 0.8, 0.45, 0.2], hy = ch.hips.position.y / PX;
  for (let i = 0; i < n; i++) {
    const g = S.gores[i]; let w = 0, h = 0;
    for (let j = -3; j <= 3; j++) { const k = (i + j + n) % n, f = fall[Math.abs(j)]; w = Math.max(w, pushW[k] * f); h = Math.max(h, pushH[k] * f); }
    const lobes = 1 + 0.22 * Math.sin(3 * g.th + 2 * yawW);
    const flareA = af * 0.62 * lobes, sitA = sit * 0.95 * Math.max(0, Math.cos(g.th));
    const ww = Math.max(w, sitA * 0.6), hh0 = Math.max(h, flareA, sitA * 0.5);
    // sur un siège, l'angle des paniers est un angle ABSOLU (la partie haute couvre les cuisses, la partie basse retombe devant les tibias) : sans
    // cela il s'ajoutait à celui de la taille et les lés de devant pointaient vers le haut comme des planches. Debout, marche, tour : inchangé
    const hh = hh0 - ww * clamp(sit, 0, 1);
    g.W.rotation.x = -ww; g.Hn.rotation.x = -hh;
    g.W.scale.x = 1 + 0.6 * Math.sin(ww); g.Hn.scale.x = 1 + 0.85 * Math.sin(Math.max(0, hh));
    // garde-fou du plancher, lé par lé : si l'ourlet de ce lé passait sous le sol (arrière d'une jupe sur un siège, creux du pas), sa partie basse
    // se tasse juste assez ; debout, l'ourlet est à 0,35 px du sol et rien ne change
    const a = ww + hh, ca = Math.cos(a), yHn = WAIST[0] + (LO[0][0] - WAIST[0]) * Math.cos(ww) + (g.Rh - g.Rw) * Math.sin(ww);
    const R = (HEM_M - hy) / c - yHn - HEM_Z * Math.sin(a);
    g.Hn.scale.y = ca > 0.05 ? clamp(R / (HEM_Y * ca), 0.05, 1) : 1;
  }
}

// ------------------------------------------------------------------------------------------------ corsage (repère du torse)
function buildBodice(ch, C, seed) {
  const bod = col(C.colors.bodice), st = col(C.colors.stomacher), lace = col(C.colors.lace, 0xf6f4ec), skin = col(C.colors.skin);
  const sat = [], cloth = [], lc = [];
  sat.push(B(0, 7.7, 0, 8.7, 9.2, 4.7, bod));                                     // corsage (au-dessus de la base du torse)
  sat.push(B(0, 12.1, 0, 7.6, 0.6, 4.3, bod));
  // plastron en pointe (ou arrondi), plus clair, posé devant
  const rows = C.stomacher_style === 'round' ? [[9.2, 5.0], [8.0, 4.9], [6.8, 4.6], [5.6, 4.1], [4.4, 3.4], [3.3, 2.5], [2.3, 1.4]] : [[9.2, 5.2], [8.0, 4.6], [6.8, 4.0], [5.6, 3.3], [4.4, 2.6], [3.3, 1.9], [2.2, 1.2], [1.3, 0.6]];
  for (const [y, w] of rows) sat.push(B(0, y, 2.42, w, 1.25, 0.25, st));
  if (C.colors.buttons) for (let y = 8.6; y > 2.4; y -= 1.05) cloth.push(B(0, y, 2.62, 0.62, 0.62, 0.3, col(C.colors.buttons)));
  if (C.colors.belt) cloth.push(B(0, 3.6, 2.45, 8.9, 0.8, 0.3, col(C.colors.belt)), B(0, 3.6, 2.62, 1.4, 1.2, 0.3, shade(col(C.colors.belt), 1.15).getHex()));
  // encolure carrée : peau du haut de la poitrine, bordée d'un volant de dentelle (petits cubes alternés)
  cloth.push(B(0, 10.85, 2.4, 6.0, 2.7, 0.22, skin));
  for (let x = -3.3; x <= 3.31; x += 0.66) { const k = Math.round((x + 3.3) / 0.66) % 2; lc.push(B(x, 9.45 - k * 0.22, 2.58, 0.72, 0.62 + k * 0.2, 0.35, k ? shade(lace, 0.93).getHex() : lace)); }
  for (const s of [-1, 1]) for (let y = 9.6; y <= 12.3; y += 0.62) { const k = Math.round((y - 9.6) / 0.62) % 2; lc.push(B(s * (3.25 + k * 0.15), y, 2.56, 0.62, 0.66, 0.35, k ? shade(lace, 0.93).getHex() : lace)); }
  for (let x = -3.3; x <= 3.31; x += 0.66) { const k = Math.round((x + 3.3) / 0.66) % 2; lc.push(B(x, 12.35 + k * 0.12, -2.25, 0.7, 0.55, 0.4, k ? shade(lace, 0.93).getHex() : lace)); }
  for (const s of [-1, 1]) lc.push(B(s * 3.4, 12.45, 0.2, 0.55, 0.5, 4.4, lace));                                 // sur les épaules
  if (C.colors.rosette) { const ro = col(C.colors.rosette); lc.push(B(0, 9.5, 2.85, 1.1, 1.1, 0.5, ro), B(-0.6, 9.5, 2.8, 0.6, 0.6, 0.4, shade(ro, 0.9).getHex()), B(0.6, 9.5, 2.8, 0.6, 0.6, 0.4, shade(ro, 0.9).getHex()), B(0, 10.1, 2.8, 0.6, 0.5, 0.4, shade(ro, 1.05).getHex()), B(0, 8.9, 2.75, 0.4, 0.6, 0.3, 0x5a8a50)); }
  ch.torso.add(mesh(sat, mat('satin', seed + 1)));
  ch.torso.add(mesh(cloth, mat('cloth', seed + 2)));
  ch.torso.add(mesh(lc, mat('cloth', seed + 3)));
}

// volants de dentelle au coude ou au poignet (repère du coude)
function buildSleeveLace(ch, C, seed) {
  const lace = col(C.colors.lace, 0xf6f4ec);
  for (const el of [ch.elL, ch.elR]) {
    const lb = []; const y0 = C.sleeves === 'elbow' ? -0.3 : -4.3;
    for (let a = 0; a < 12; a++) {
      const an = (a / 12) * 2 * Math.PI, rr = 2.35 + (a % 2) * 0.25;
      lb.push(B(Math.sin(an) * rr, y0 - 0.2 - (a % 2) * 0.25, Math.cos(an) * rr, 1.45, 1.3, 0.5, a % 2 ? shade(lace, 0.92).getHex() : lace, { ry: an }));
      lb.push(B(Math.sin(an) * (rr + 0.35), y0 - 1.15, Math.cos(an) * (rr + 0.35), 1.35, 0.9, 0.45, a % 2 ? lace : shade(lace, 0.9).getHex(), { ry: an, rx: 0.35 }));
    }
    if (C.sleeves === 'elbow') lb.push(B(0, 0.6, 0, 4.1, 1.4, 4.1, col(C.colors.bodice)));
    el.add(mesh(lb, mat('cloth', seed + 4)));
  }
}

// ------------------------------------------------------------------------------------------------ redingote
function buildCoat(ch, C, seed) {
  const coat = col(C.colors.coat), fac = col(C.colors.facings), wc = col(C.colors.waistcoat), btn = col(C.colors.buttons, 0xd6ac46), collar = col(C.colors.collar || C.colors.facings), cuffs = col(C.colors.cuffs || C.colors.facings), jab = col(C.colors.jabot, 0xf6f4ec);
  const cloth = [], gold = [];
  cloth.push(B(0, 6.0, 2.28, 3.4, 10.2, 0.25, wc));                                                         // gilet (dans l'ouverture)
  for (let y = 10.2; y > 1.4; y -= 1.1) gold.push(B(0, y, 2.46, 0.5, 0.5, 0.25, btn));
  for (const s of [-1, 1]) {
    cloth.push(B(s * 2.55, 7.9, 2.34, 1.7, 8.6, 0.3, fac));                                                  // revers
    cloth.push(B(s * 3.25, 11.6, 2.3, 1.3, 1.6, 0.3, fac, { rz: s * 0.5 }));
    for (const y of [10.4, 9.6, 7.6, 6.8, 4.8, 4.0]) gold.push(B(s * 2.7, y, 2.6, 0.8, 0.8, 0.35, btn));      // boutons dorés par paires
    cloth.push(B(s * 5.0, 1.0, 2.25, 0.45, 0.45, 0.2, btn));
  }
  // col montant (dos et côtés), cravate blanche, jabot à volants
  cloth.push(B(0, 12.9, -1.6, 7.2, 2.4, 1.4, collar), B(-3.3, 12.8, 0.2, 1.2, 2.2, 3.2, collar), B(3.3, 12.8, 0.2, 1.2, 2.2, 3.2, collar));
  cloth.push(B(0, 12.4, 1.75, 3.6, 1.4, 0.9, 0xf2f0ea));
  const jr = mulberry(seed * 7 + 11);
  for (let k = 0; k < 7; k++) { const y = 11.9 - k * 0.62, w = 2.4 - k * 0.12 + (k % 2) * 0.3; cloth.push(B((jr() - 0.5) * 0.4, y, 2.7 + (k % 2) * 0.22, w, 0.75, 0.55, k % 2 ? shade(jab, 0.92).getHex() : jab)); }
  if (C.colors.epaulettes) {
    const ep = col(C.colors.epaulettes);
    for (const s of [-1, 1]) { gold.push(B(s * 5.6, 12.75, 0, 3.8, 0.6, 3.9, ep), B(s * 7.2, 12.3, 0, 0.7, 1.2, 4.1, shade(ep, 0.9).getHex())); for (let k = 0; k < 7; k++) gold.push(B(s * 7.55, 11.3 - (k % 2) * 0.25, -1.8 + k * 0.6, 0.4, 1.7, 0.4, shade(ep, 0.92 + (k % 2) * 0.12).getHex())); }
  }
  ch.torso.add(mesh(cloth, mat('cloth', seed + 1)));
  if (gold.length) ch.torso.add(mesh(gold, mat('gold', seed + 2)));
  // parements de manche + dentelle au poignet (repère du coude)
  for (const el of [ch.elL, ch.elR]) {
    const cb = [B(0, -3.45, 0, 4.4, 1.7, 4.4, cuffs), B(0, -3.2, 2.25, 0.55, 0.55, 0.3, btn), B(0, -3.9, 2.25, 0.55, 0.55, 0.3, btn)];
    for (let a = 0; a < 10; a++) { const an = (a / 10) * 2 * Math.PI; cb.push(B(Math.sin(an) * 2.0, -4.75, Math.cos(an) * 2.0, 1.4, 0.9, 0.45, a % 2 ? 0xf2f0ea : 0xe4e0d8, { ry: an })); }
    el.add(mesh(cb, mat('cloth', seed + 3)));
  }
  // basques (repère du bassin) : panneaux de côté (hors des cuisses) et panneaux arrière articulés
  const tails = [];
  for (const s of [-1, 1]) {
    const side = new THREE.Group(); side.position.set(s * 4.75 * PX, 1.0 * PX, 0); ch.hips.add(side);
    side.add(mesh([B(0, -4.2, -0.6, 0.6, 8.6, 4.3, coat), B(0, -8.3, 0.4, 0.65, 0.6, 1.2, fac)], mat('cloth', seed + 5)));
    const back = new THREE.Group(); back.position.set(s * 2.6 * PX, 1.0 * PX, -2.75 * PX); ch.hips.add(back);
    const tm = mesh([B(0, -4.3, -0.3, 4.1, 8.8, 0.6, coat)], mat('cloth', seed + 6)); tm.userData.tail = true; back.add(tm);
    back.add(mesh([B(s * 1.2, -1.2, -0.65, 0.6, 0.6, 0.3, btn), B(s * 1.2, -3.4, -0.65, 0.6, 0.6, 0.3, btn)], mat('gold', seed + 6)));
    tails.push({ g: back, side: s > 0 ? 'L' : 'R', lg: s > 0 ? ch.lgL : ch.lgR });
  }
  // bas blancs, bottes hautes ou souliers à boucle (repère du genou / de la cheville)
  const br = col(C.colors.breeches);
  ch.hips.add(mesh([B(0, -0.4, 2.12, 0.35, 2.4, 0.12, shade(br, 0.72).getHex()), B(0, 0.85, 2.12, 7.6, 0.35, 0.12, shade(br, 0.8).getHex())], mat('cloth', seed + 9)));
  for (const [lg, sd] of [[ch.lgL, 1], [ch.lgR, -1]]) lg.add(mesh([B(-sd * 1.85, -3.4, 2.07, 0.3, 6.6, 0.1, shade(br, 0.74).getHex()), B(-sd * 1.85, -3.4, -2.07, 0.3, 6.6, 0.1, shade(br, 0.74).getHex())], mat('cloth', seed + 10)));
  for (const [kn, ft] of [[ch.knL, ch.ftL], [ch.knR, ch.ftR]]) {
    const lb = [B(0, -2.75, 0, 4.15, 5.6, 4.2, col(C.colors.stockings, 0xf0eee8)), B(0, -0.2, 0, 4.25, 1.0, 4.3, col(C.colors.breeches))];
    if (C.footwear === 'boots') { const bt = col(C.colors.boots, 0x181618); lb.push(B(0, -3.3, 0, 4.5, 4.6, 4.55, bt), B(0, -0.9, 0, 4.75, 1.3, 4.8, shade(bt, 1.25).getHex())); }
    kn.add(mesh(lb, mat('cloth', seed + 7)));
    if (C.footwear !== 'boots') ft.add(mesh([B(0, -0.55, 1.3, 1.6, 0.9, 0.35, 0xd6ac46)], mat('gold', seed + 8)));
  }
  return tails;
}

// ------------------------------------------------------------------------------------------------ têtes : coiffures, barbes, bijoux (PX, centre de la tête)
function hairBoxes(C, seed) {
  const r = mulberry(seed * 31 + 7); const H = [], T = [];                            // H : suit la tête ; T : repose sur le dos / l'épaule (repère tête, accroché au torse)
  const h0 = col(C.colors.hair_color), h1 = mixc(h0, 0x7a5840, 0.3).getHex(), hm = mixc(h0, 0x7a5840, 0.13).getHex(), hd = shade(h0, 0.62).getHex();   // reflets chauds : des boucles noires restent lisibles
  const pick = () => { const v = r(); return v < 0.48 ? h0 : v < 0.72 ? hm : v < 0.87 ? hd : h1; };
  const cube = (L, x, y, z, s, c) => L.push(B(x, y, z, s, s, s, c ?? pick()));
  const st = C.hair;
  // calotte plaquée (cheveux tirés en arrière) : dessus, arrière, côtés au-dessus des oreilles ; front dégagé
  const cap = (R = 4.35, s = 1.0, nape = -2.6, temple = 0.6, front = 3.0) => {
    const stp = 0.85;
    for (let x = -4.0; x <= 4.01; x += stp) for (let z = -4.0; z <= front + 0.01; z += stp) cube(H, x + (r() - 0.5) * 0.2, R + (r() - 0.3) * 0.25 - (Math.abs(x) > 3.4 ? 0.3 : 0), z, s);
    for (let x = -4.0; x <= 4.01; x += stp) for (let y = nape; y <= 4.2; y += stp) cube(H, x, y, -R - (r() - 0.3) * 0.25, s);
    for (const sx of [-1, 1]) for (let y = temple; y <= 4.2; y += stp) for (let z = -4.0; z <= 1.6; z += stp) { if (z > 0.4 && y < 1.6) continue; cube(H, sx * (R + (r() - 0.3) * 0.2), y, z, s); }
    for (const sx of [-1, 1]) for (let y = nape; y < temple; y += stp) for (let z = -4.0; z <= -1.2; z += stp) cube(H, sx * R, y, z, s);
    for (let x = -3.6; x <= 3.61; x += 0.9) cube(H, x, 3.75 + (r() - 0.5) * 0.3, 4.05, 0.9);                       // ligne du front
  };
  const curl = (L, x, y, z, k = 1) => { const c = pick(); L.push(B(x, y, z, 1.2 * k, 1.2 * k, 1.2 * k, c), B(x + 0.45 * k, y - 0.55 * k, z + 0.2, 0.9 * k, 0.9 * k, 0.9 * k, shade(c, 0.85).getHex()), B(x - 0.35 * k, y - 0.9 * k, z - 0.15, 0.8 * k, 0.8 * k, 0.8 * k, c)); };
  if (st === 'shaved' && C.face_skin) {                                                                         // tête peinte : le ras du crâne est dans la texture ; oreilles en relief
    const ear = shade(col(C.colors.skin), 0.9).getHex();
    for (const s of [-1, 1]) H.push(B(s * 4.15, -0.7, -0.3, 0.5, 1.9, 1.3, ear), B(s * 4.3, -0.7, -0.3, 0.2, 1.1, 0.6, shade(col(C.colors.skin), 0.72).getHex()));
  } else if (st === 'shaved') {
    const sk = mixc(col(C.colors.skin), h0, 0.22).getHex(), hi = mixc(col(C.colors.skin), 0xffffff, 0.12).getHex();
    H.push(B(0, 4.04, -0.6, 7.6, 0.12, 6.4, sk), B(0, 2.0, -4.04, 7.6, 3.6, 0.12, sk), B(1.2, 4.1, 1.2, 2.2, 0.06, 1.6, hi));
  } else if (st === 'short' || st === 'queue' || st === 'updo' || st === 'side_ponytail') {
    cap(4.35, 1.0, st === 'short' ? -2.2 : -2.8, st === 'short' ? 0.0 : 0.6, st === 'short' ? 3.4 : 2.8);
    if (st === 'queue') {                                                                                      // catogan : queue basse + nœud de ruban noir
      const rb = col(C.colors.ribbon, 0x161418);
      for (let y = -3.0; y >= -11.5; y -= 0.8) { const k = (y + 3) / -8.5; cube(T, (r() - 0.5) * 0.4, y, -4.7 + k * 1.9, 1.35 - k * 0.45); }
      H.push(B(0, -2.6, -4.9, 1.2, 1.2, 1.0, rb), B(-1.3, -2.4, -4.95, 1.5, 1.0, 0.6, rb, { rz: 0.4 }), B(1.3, -2.4, -4.95, 1.5, 1.0, 0.6, rb, { rz: -0.4 }));
      T.push(B(-0.5, -4.0, -4.6, 0.6, 2.2, 0.4, rb, { rz: 0.15 }), B(0.5, -4.1, -4.6, 0.6, 2.4, 0.4, rb, { rz: -0.15 }));
    } else if (st === 'updo') {
      for (let k = 0; k < 40; k++) { const a = r() * Math.PI * 2, e = r(); cube(H, Math.cos(a) * 1.9 * e, 4.4 + Math.sin(a) * 1.2 * e + 0.6, -3.4 + (r() - 0.5) * 2.2, 1.1); }   // chignon au sommet arrière
      for (const s of [-1, 1]) for (let y = 0.8; y > -2.2; y -= 0.7) cube(H, s * (4.25 + (r() - 0.5) * 0.2), y, 2.2, 0.75);   // mèches aux tempes
    } else if (st === 'side_ponytail') {
      for (let k = 0; k < 18; k++) cube(H, 1.5 + (r() - 0.5) * 2, 2.6 + (r() - 0.5) * 1.4, -4.6 + (r() - 0.5) * 0.6, 1.0);
      const path = [[3.8, -3.0, -1.4], [4.6, -4.6, 0.8], [4.3, -6.5, 2.6], [3.9, -9.0, 3.3], [3.6, -11.8, 3.5], [3.5, -13.5, 3.4]];   // queue sur l'épaule droite, devant (+x : le monde VOXEL est le miroir de PS1, voir buildItems)
      for (let k = 0; k < path.length - 1; k++) for (let u = 0; u < 1; u += 0.34) { const a = path[k], b = path[k + 1]; const p = [0, 1, 2].map((j) => a[j] + (b[j] - a[j]) * u); const w = 1.6 - 0.12 * k; cube(T, p[0], p[1], p[2], w); cube(T, p[0] - 0.5, p[1] - 0.3, p[2] - 0.4, w * 0.8); }
      H.push(B(3.6, -2.4, -3.0, 1.3, 1.0, 1.0, col(C.colors.ribbon || C.colors.bodice, 0x2a8a90)));
    }
  } else if (st === 'big_curls') {
    // très grande chevelure bouclée : volume en couches (plus serré devant, demi-queue), longues anglaises dans le dos jusqu'au milieu du dos
    for (const [R, p] of [[4.4, 1], [5.1, 0.85], [5.8, 0.55], [6.4, 0.25]]) {
      const stp = 0.95;
      for (let x = -R; x <= R + 0.01; x += stp) for (let z = -R; z <= R + 0.01; z += stp) { if (r() > p) continue; const front = z > 1.5; if (front && R > 4.6) continue; cube(H, x + (r() - 0.5) * 0.5, R - 0.4 + r() * 0.5 - (Math.hypot(x, z) > R * 0.95 ? 0.6 : 0), Math.min(z, 3.2) + (r() - 0.5) * 0.4, 1.0 + r() * 0.5); }
      for (const sx of [-1, 1]) for (let y = -3.5; y <= R - 0.2; y += stp) for (let z = -R; z <= 2.6; z += stp) { if (r() > p) continue; if (z > 0.5 && y < -1.0 && R < 5.0) continue; cube(H, sx * (R + (r() - 0.3) * 0.4), y + (r() - 0.5) * 0.4, z + (r() - 0.5) * 0.4, 1.0 + r() * 0.55); }
      for (let x = -R; x <= R + 0.01; x += stp) for (let y = -3.5; y <= R - 0.2; y += stp) { if (r() > p) continue; cube(H, x + (r() - 0.5) * 0.4, y, -R - r() * 0.4, 1.0 + r() * 0.55); }
    }
    for (let x = -3.4; x <= 3.41; x += 0.85) cube(H, x, 3.95 + r() * 0.3, 4.0, 0.95);
    for (const sx of [-1, 1]) for (let k = 0; k < 4; k++) curl(H, sx * (4.6 + r() * 0.4), 0.4 - k * 1.3, 2.2 + r() * 0.6, 0.85);          // boucles devant les oreilles
    for (let k = 0; k < 230; k++) {                                                                             // anglaises dans le dos (reposent sur le dos)
      const y = -3.2 - r() * 10.5, wy = 6.6 - Math.max(0, (-y - 4)) * 0.22, x = (r() * 2 - 1) * wy, z = -3.3 - r() * (3.6 - Math.max(0, (-y - 7)) * 0.25) - Math.abs(x) * 0.05;
      curl(T, x, y, z, 0.8 + r() * 0.35);
    }
  } else if (st === 'updo_curls' || st === 'puff' || st === 'afro_crown') {
    cap(4.35, 1.0, -2.6, st === 'updo_curls' ? 0.4 : 0.0, 3.0);
    const n = st === 'puff' ? 170 : st === 'afro_crown' ? 260 : 150;
    for (let k = 0; k < n; k++) {
      const a = r() * Math.PI * 2, e = Math.sqrt(r());
      if (st === 'puff') cube(H, Math.cos(a) * 3.6 * e, 4.6 + r() * 3.8 * (1 - e * 0.45), -0.6 + Math.sin(a) * 3.2 * e, 1.15 + r() * 0.4);
      else if (st === 'afro_crown') { const rr = 4.6 + r() * 1.8; cube(H, Math.cos(a) * rr * (0.75 + 0.25 * e), 3.2 + r() * 3.4 - (rr - 4.6) * 0.5, Math.sin(a) * rr * (0.75 + 0.25 * e) - 0.6, 1.2 + r() * 0.5); }
      else cube(H, Math.cos(a) * 3.8 * e, 4.3 + r() * 3.3 * (1 - e * 0.55), -1.2 + Math.sin(a) * 3.3 * e, 1.15 + r() * 0.45);
    }
    if (st === 'updo_curls') { for (const sx of [-1, 1]) for (let k = 0; k < 3; k++) curl(H, sx * (4.4 + r() * 0.3), 0.6 - k * 1.2, 1.8 + r() * 0.5, 0.75); for (let k = 0; k < 10; k++) curl(H, (r() - 0.5) * 5, 1.5 - r() * 3.5, -4.7 - r() * 0.5, 0.8); }
  }
  // barbes (devant le visage : la bouche est vers y = -1,9, le nez vers -0,8)
  const bc = shade(h0, 1.0).getHex(), z0 = 4.18;
  if (C.face_skin) { /* barbe peinte sur la tête (face_skin) */ }
  else if (C.beard === 'goatee') {
    for (const s of [-1, 1]) H.push(B(s * 1.15, -1.42, z0, 1.35, 0.38, 0.32, bc), B(s * 1.0, -2.55, z0, 0.32, 1.2, 0.28, bc));
    H.push(B(0, -3.35, z0, 1.9, 1.15, 0.4, bc), B(0, -3.85, 2.8, 1.7, 0.4, 2.4, bc));
  } else if (C.beard === 'short_full') {
    const bs = mixc(h0, col(C.colors.skin), 0.18).getHex();
    for (const x of [-2.1, -0.7, 0.7, 2.1]) H.push(B(x, -3.55, z0, 1.45, 0.9, 0.3, shade(bs, 0.95 + r() * 0.12).getHex()));
    for (const s of [-1, 1]) H.push(B(s * 3.4, -2.6, z0 - 0.05, 0.9, 1.6, 0.3, bs), B(s * 4.05, -2.2, 2.6, 0.25, 1.8, 3.0, bs), B(s * 1.15, -1.42, z0, 1.3, 0.38, 0.3, bs));
    H.push(B(0, -4.04, 2.6, 6.4, 0.25, 3.2, bs));
  } else if (C.beard === 'mustache') { for (const s of [-1, 1]) H.push(B(s * 1.15, -1.42, z0, 1.4, 0.42, 0.35, bc)); }
  else if (C.beard === 'stubble') { H.push(B(0, -3.2, z0 - 0.05, 5.8, 1.5, 0.2, mixc(col(C.colors.skin), h0, 0.45).getHex())); }
  return { H, T };
}

function buildHead(ch, C, seed) {
  const { H, T } = hairBoxes(C, seed);
  if (H.length) { const m = mesh(H, mat('hair', seed + 9)); m.position.y = 4 * PX; ch.neck.add(m); }
  if (T.length) { const m = mesh(T, mat('hair', seed + 10)); m.position.y = 16 * PX; ch.torso.add(m); }          // centre de la tête dans le repère du torse : cou (12) + 4
  const acc = [], gold = [];
  if (C.colors.earrings) for (const s of [-1, 1]) gold.push(B(s * 4.15, -1.3, 0.8, 0.45, 0.45, 0.45, col(C.colors.earrings)), B(s * 4.18, -2.0, 0.8, 0.5, 0.75, 0.5, col(C.colors.earrings)));
  if (C.crown) {                                                                                              // couronne de fleurs (blanches et bleu ciel) et feuilles, posée sur le voile
    const cr = C.crown.map((c) => col(c)), rr = 5.0;
    for (let k = 0; k < 18; k++) {
      const a = (k / 18) * 2 * Math.PI, x = Math.sin(a) * rr, z = Math.cos(a) * rr * 0.92 - 0.6, y = 5.5 + (Math.cos(a) > 0.3 ? 0 : 0.35);
      if (k % 3 !== 2) { const c = cr[k % cr.length]; acc.push(B(x, y, z, 1.7, 1.0, 1.7, c), B(x, y + 0.55, z, 1.1, 0.5, 1.1, shade(c, 1.08).getHex()), B(x, y + 0.85, z, 0.5, 0.35, 0.5, 0xf2d878)); }
      else acc.push(B(x, y - 0.1, z, 1.2, 0.55, 1.2, 0x5a9858), B(x * 1.05, y + 0.25, z * 1.05, 0.6, 0.5, 0.6, 0x6aa866));
    }
  }
  if (gold.length) { const m = mesh(gold, mat('gold', seed + 11)); m.position.y = 4 * PX; ch.neck.add(m); }
  if (acc.length) { const m = mesh(acc, mat('cloth', seed + 12)); m.position.y = 4 * PX; ch.neck.add(m); }
  if (C.colors.veil) {                                                                                        // voile : posé sous la couronne, il tombe derrière la tête et encadre le visage ; puis le dos ; puis l'arrière de la jupe
    const v = col(C.colors.veil), vh = [], dots = [], r = mulberry(seed * 5 + 1), lace = 0xf6f4ee;
    vh.push(B(0, 5.35, -2.6, 10.4, 0.2, 2.2, v));                                                                 // sur le dessus, derrière la couronne (jamais au-dessus du front)
    vh.push(B(0, 6.15, -3.0, 10.4, 0.2, 3.6, v, { rx: 0.42 }));                                                   // par-dessus le chignon
    for (const [y, w, z] of [[3.6, 8.8, -5.5], [1.4, 9.8, -5.75], [-0.8, 10.8, -6.0], [-3.0, 11.8, -6.3]]) {          // derrière la tête : il s'élargit en tombant, arrondi (trois pans par rang)
      vh.push(B(0, y, z, w * 0.56, 2.25, 0.2, v));
      for (const s of [-1, 1]) vh.push(B(s * w * 0.4, y, z + w * 0.085, w * 0.3, 2.25, 0.2, v, { ry: -s * 0.55 }));
    }
    for (const s of [-1, 1]) {
      for (const [y, x, d] of [[3.8, 4.7, 3.0], [1.6, 5.1, 3.3], [-0.6, 5.5, 3.6], [-2.8, 5.9, 3.9]]) vh.push(B(s * x, y, -5.9 + d / 2, 0.2, 2.25, d, v));    // pans en escalier DERRIÈRE les oreilles : le visage reste dégagé, même de trois quarts
      for (let y = -3.8; y < 4.9; y += 0.62) { const x = y > 2.7 ? 4.7 : y > 0.5 ? 5.1 : y > -1.7 ? 5.5 : 5.9, d = y > 2.7 ? 3.0 : y > 0.5 ? 3.3 : y > -1.7 ? 3.6 : 3.9; dots.push(B(s * x, y, -5.9 + d + 0.1, 0.3, 0.5, 0.35, lace)); }   // bord festonné
    }
    for (let k = 0; k < 34; k++) { const s = k % 2 ? 1 : -1; { const yy = -3.6 + r() * 8.4, xx = (yy > 2.7 ? 4.7 : yy > 0.5 ? 5.1 : yy > -1.7 ? 5.5 : 5.9) + 0.12; dots.push(B(s * xx, yy, -5.6 + r() * 2.8, 0.1, 0.26, 0.26, 0xffffff)); } dots.push(B((r() - 0.5) * 9.8, -3.6 + r() * 8.6, -6.0, 0.26, 0.26, 0.1, 0xffffff)); }
    const hv = new THREE.Group(); hv.position.y = 4 * PX; ch.neck.add(hv); hv.add(mesh(vh, mat('veil'), false)); hv.add(mesh(dots, mat('cloth', 4), false));
    const back = new THREE.Group(); back.position.set(0, 12.4 * PX, -3.2 * PX); ch.torso.add(back);            // pan du dos (repère du torse), en pente douce au-dessus des paniers ; s'écarte avec l'évasement
    const bv = [], bd = [];
    for (const [y, z, w, h, rx] of [[-3.0, -0.75, 11.2, 6.2, 0.24], [-8.6, -2.6, 13.0, 5.6, 0.42]]) {               // pan du dos arrondi : un centre et deux ailes qui reviennent vers l'avant
      bv.push(B(0, y, z, w * 0.56, h, 0.2, v, { rx }));
      for (const s of [-1, 1]) bv.push(B(s * w * 0.4, y, z + w * 0.08, w * 0.3, h, 0.2, v, { rx, ry: -s * 0.5 }));
    }
    for (let q = 0; q < 26; q++) { const yy = -r() * 11.4, z = yy > -6 ? -0.75 + (yy + 3) * 0.24 : -2.6 + (yy + 8.6) * 0.42; bd.push(B((r() - 0.5) * 11, yy, z - 0.15, 0.26, 0.26, 0.1, 0xffffff)); }
    back.add(mesh(bv, mat('veil'), false)); back.add(mesh(bd, mat('cloth', 5), false));
    return back;
  }
  return null;
}

// ------------------------------------------------------------------------------------------------ tête peinte en pixels (« skin », face_skin.py)
// La peinture vient du contrat (la même que PS1) : grilles 16 x 16 de la face, des côtés, de l'arrière et du dessus, et des calques qui bougent :
// yeux (ouverts / mi-clos / fermés / écarquillés, iris selon le regard), sourcils (bouts intérieur et extérieur), bouche (fermée, sourire, moue,
// trois ouvertures, sourire ouvert). Ils sont choisis à chaque image à partir de la MÊME couche visage que le visage du moteur (applyFace : blink, mo, ms,
// lx, bi, bo, expression) ou de l'expression + clignement + parole. La texture n'est repeinte que quand l'état change. Fonction pure du temps.
const B36 = '0123456789abcdefghijklmnopqrstuvwxyz';
const FACE_MATTE = 0.62;
// Blancs des yeux et dents : mats comme les tissus, plafond plus bas (FACE_MATTE). Ce sont les couleurs claires et neutres que seuls les calques yeux / bouche
// emploient (jamais les grilles de peau) ; sous une poursuite forte, elles brûlaient jusqu'au bloom (yeux et dents « lampes »). La peau ne change pas.
function mattePal(S) {
  const inGrid = new Set(); for (const rows of Object.values(S.grids || {})) for (const r of rows) for (const ch of r) inGrid.add(B36.indexOf(ch));
  const inSprite = new Set(); for (const L of [S.eyes, S.mouth]) for (const v of Object.values(L || {})) for (const [, , i] of v) inSprite.add(i);
  return S.pal.map((hx, i) => {
    if (!inSprite.has(i) || inGrid.has(i)) return hx;
    const h = parseInt(hx.slice(1), 16), r = (h >> 16) & 255, g = (h >> 8) & 255, b = h & 255;
    if (Math.max(r, g, b) - Math.min(r, g, b) > 40) return hx;                       // une couleur franche (iris, lèvres) n'est pas un blanc
    return '#' + matte(h, FACE_MATTE).toString(16).padStart(6, '0');
  });
}
function setupSkinFace(ch, S) {
  const pal = mattePal(S);
  const mk = () => { const c = document.createElement('canvas'); c.width = c.height = 16; return c; };
  const paint = (g, rows) => { for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { g.fillStyle = pal[B36.indexOf(rows[y][x])]; g.fillRect(x, y, 1, 1); } };
  const dots = (g, list) => { for (const [x, y, i] of list || []) { g.fillStyle = pal[i]; g.fillRect(x, y, 1, 1); } };
  const tex = (c) => { const t = new THREE.CanvasTexture(c); t.magFilter = t.minFilter = THREE.NearestFilter; t.generateMipmaps = false; t.colorSpace = THREE.SRGBColorSpace; return t; };
  const M = (t) => rimify(new THREE.MeshLambertMaterial({ map: t }), 1, 0.15);
  const side = mk(); paint(side.getContext('2d'), S.grids.side);
  const sideM = mk(); { const g = sideM.getContext('2d'); g.translate(16, 0); g.scale(-1, 1); g.drawImage(side, 0, 0); }
  const back = mk(); paint(back.getContext('2d'), S.grids.back); const top = mk(); paint(top.getContext('2d'), S.grids.top);
  const face = mk(); const fg = face.getContext('2d'); const faceT = tex(face);
  ch.head.traverse((o) => { if (o !== ch.head && o.isMesh) o.visible = false; });               // le relief du visage du moteur s'efface : la tête redevient un cube peint
  const under = Array.isArray(ch.head.material) ? ch.head.material[3] : ch.head.material;
  ch.head.material = [M(tex(side)), M(tex(sideM)), M(tex(top)), under, M(faceT), M(tex(back))];        // ordre de three.js : +x, -x, +y, -y, +z (visage), -z
  let last = '';
  ch.faceUpdate = (t) => {
    const F = ch.face; let P;
    if (F.layer) {
      const L = F.layer, N = exprParams('neutral'); P = { ...N };
      for (const [nm, iv] of [[L.e1, L.i1], [L.e2, L.i2]]) { if (!nm || !(iv > 0)) continue; const pe = exprParams(nm === 'blink' ? 'neutral' : nm); for (const k in P) if (typeof P[k] === 'number') P[k] += iv * (pe[k] - N[k]); }
      P.eo = Math.max(0, P.eo * (1 - L.blink)); P.lx = L.lx; P.ly = L.ly; P.bi += L.bdi; P.bo += L.bdo; P.mo = Math.max(0, P.mo + L.mo); P.ms += L.ms;
    } else {
      P = { ...exprParams(F.want === 'blink' ? 'neutral' : F.want) };
      const b = F.want === 'blink' ? 1 : blinkAmount(t, F.seed); P.eo *= 1 - b; const [sx, sy] = saccade(t, F.seed); P.lx += sx; P.ly += sy;
    }
    talkMouth(P, t, F.talk);
    const eyes = P.eo < 0.3 ? 'closed' : P.eo < 0.62 ? 'half' : P.eo > 1.2 ? 'wide' : 'open';
    const dx = P.lx > 0.45 ? 1 : P.lx < -0.45 ? -1 : 0, q = (v) => (v > 2.5 ? 1 : v < -2.5 ? -1 : 0);
    const mo = P.mo, ms = P.ms;
    const mouth = mo < 0.1 ? (ms > 0.35 ? 'smile' : ms < -0.35 ? 'frown' : 'closed') : mo < 0.35 ? (ms > 0.5 ? 'smile_open' : 'open1') : mo < 0.7 ? (ms > 0.5 ? 'smile_open' : 'open2') : 'open3';
    const key = `${eyes}_${dx}|${q(P.bi)}_${q(P.bo)}|${mouth}`; if (key === last) return; last = key;
    paint(fg, S.grids.front); dots(fg, S.brows[`${q(P.bi)}_${q(P.bo)}`]); dots(fg, S.eyes[`${eyes}_${dx}`]); dots(fg, S.mouth[mouth]); faceT.needsUpdate = true;
  };
  ch.skinFace = true;
}

// ------------------------------------------------------------------------------------------------ accessoires tenus (mètres, repère du personnage, à la paume)
function itemBoxes(name, side) {
  const S = name === 'bouquet' ? 1.6 : 1.45; const P = (x, y, z, w, h, d, c) => ({ x: side * x * S, y: y * S, z: z * S, w: w * S, h: h * S, d: d * S, color: c });
  const glass = 0xeef6fa, wine = 0xf6e08a, out = { solid: [], clear: [] };
  if (name === 'flute' || name === 'wine_glass') {
    out.clear.push(P(0, -0.10, 0.03, 0.085, 0.012, 0.085, glass), P(0, -0.02, 0.03, 0.018, 0.16, 0.018, glass));
    if (name === 'flute') { out.clear.push(P(0, 0.17, 0.03, 0.075, 0.2, 0.075, glass)); out.solid.push(P(0, 0.145, 0.03, 0.056, 0.13, 0.056, wine)); }
    else { out.clear.push(P(0, 0.13, 0.03, 0.12, 0.13, 0.12, glass)); out.solid.push(P(0, 0.105, 0.03, 0.1, 0.065, 0.1, 0x96223a)); }
  } else if (name === 'bouquet') {
    const r = mulberry(17);
    for (let k = 0; k < 7; k++) out.solid.push(P((r() - 0.5) * 0.05, -0.05, 0.04 + (r() - 0.5) * 0.04, 0.02, 0.22, 0.02, 0x4a8a46));
    for (let k = 0; k < 34; k++) { const a = r() * 6.283, e = Math.sqrt(r()); const c = r() < 0.75 ? (r() < 0.5 ? 0xf8f8f2 : 0xeeeee4) : (r() < 0.6 ? 0xa8d0ee : 0x6aa866); out.solid.push(P(Math.cos(a) * 0.12 * e, 0.12 + (1 - e) * 0.07 + r() * 0.03, 0.05 + Math.sin(a) * 0.12 * e, 0.045, 0.045, 0.045, c)); }
    for (let k = 0; k < 5; k++) { const a = r() * 6.283; out.solid.push(P(Math.cos(a) * 0.13, 0.17 + r() * 0.03, 0.05 + Math.sin(a) * 0.13, 0.012, 0.05, 0.012, 0x5a9a50)); }
    out.solid.push(P(0, 0.0, 0.05, 0.06, 0.05, 0.06, 0xf2eee4));
  } else if (name === 'fan') {
    for (let k = 0; k < 7; k++) { const a = -1.05 + k * 0.35; out.solid.push({ x: side * Math.sin(a) * 0.1, y: 0.03 + Math.cos(a) * 0.1, z: 0.06, w: 0.06, h: 0.2, d: 0.008, color: k % 2 ? 0xf0e4ee : 0xe2c8da, rz: -side * a }); }
    out.solid.push(P(0, -0.04, 0.06, 0.03, 0.06, 0.02, 0x7a5a3a));
  } else if (name === 'letter') {
    out.solid.push(P(0, 0.06, 0.07, 0.18, 0.23, 0.008, 0xf2ead6)); for (let k = 0; k < 5; k++) out.solid.push(P(0, 0.12 - k * 0.03, 0.075, 0.13, 0.008, 0.004, 0x6a5a4a));
  } else if (name === 'flower') { out.solid.push(P(0, 0.12, 0.04, 0.018, 0.26, 0.018, 0x4a8a46), P(0, 0.27, 0.04, 0.08, 0.07, 0.08, 0xe84a6a)); }
  return out;
}

function buildItems(ch, C) {
  const names = C.items || []; if (!names.length) return null;
  const hands = {};
  // La main « droite » du costume (PS1 : main principale, côté +x de PIXEL 3D) est handL de chars4 : le demi-tour PS1 -> VOXEL change la main
  // du repère, et film_unified.arms fait jouer les gestes du bras principal de PS1 par le bras L. L'objet suit donc le bras qui fait le geste
  // (toast « arm_up » compris) ; avec `mirror` (théâtre, voxel_mirror), l'image retournée le montre dans la main droite, comme en PS1.
  for (const [side, hand, sg] of [['R', ch.handL, 1], ['L', ch.handR, -1]]) {
    const held = new THREE.Group(); ch.root.add(held);
    const palm = new THREE.Object3D(); palm.position.set(0, -1.3 * PX, 0.6 * PX); hand.add(palm);
    const groups = names.map((n) => { const ib = itemBoxes(n, sg); const g = new THREE.Group(); if (ib.solid.length) g.add(mesh(ib.solid, mat('cloth', 21), true)); if (ib.clear.length) g.add(mesh(ib.clear, mat('glass'), false)); g.visible = false; held.add(g); return g; });
    hands[side] = { held, palm, groups, cur: -1 };
  }
  return hands;
}

// ------------------------------------------------------------------------------------------------ accroche et mise à jour par image
export function attachCostume(ch, def, seed, id = null) {
  const C = def.costume; if (!C) return;
  KEEP = new Set([col((C.colors || {}).skin, -1)]);
  (globalThis.__costumes ||= {})[id ?? Object.keys(globalThis.__costumes).length] = ch;          // outil de mesure (voxelgpu_js/costume_probe.js) : lecture seule, aucun effet sur l'image
  C.colors = C.colors || {};
  const gown = C.type === 'gown';
  const st = { gown, skirt: null, tails: null, veilBack: null, items: null };
  if (gown) { buildBodice(ch, C, seed); buildSleeveLace(ch, C, seed); st.skirt = buildSkirt(ch, C, seed); }
  else st.tails = buildCoat(ch, C, seed);
  st.veilBack = buildHead(ch, C, seed);
  if (C.face_skin) setupSkinFace(ch, C.face_skin);
  st.items = buildItems(ch, C);
  const tmp = new THREE.Vector3();
  ch.costume = st;
  // accessoires : la main se referme, l'objet suit la paume en gardant l'orientation du personnage (comme b_chars.js)
  if (st.items) {
    const f0 = ch.faceUpdate;
    ch.faceUpdate = (...a) => {
      const r = f0 ? f0(...a) : undefined;
      ch.root.updateMatrixWorld(true);
      for (const side of ['R', 'L']) { const H = st.items[side]; if (H.cur < 0) continue; H.palm.getWorldPosition(tmp); H.held.position.copy(ch.root.worldToLocal(tmp)); ch.setHand(side, 'grip'); }
      return r;
    };
  }
  ch.costumeUpdate = (stage, id, T, f, FPS, ci) => {
    const tr = stage.costume && stage.costume[id];
    const j = tr ? clamp(Math.round((T - stage.t0) * FPS), 0, ((tr.f || tr.h || [0]).length) - 1) : 0;
    const fl = tr && tr.f ? tr.f[Math.min(j, tr.f.length - 1)] : 0;
    if (st.skirt) updateSkirt(ch, st.skirt, fl, f[ci.sit] || 0, f[ci.yaw]);
    if (st.tails) {                                     // basques : le panneau arrière passe derrière chaque point de SA jambe (+ demi-épaisseur), jamais au travers
      ch.root.updateMatrixWorld(true);
      for (const t of st.tails) {
        const a = -t.lg.rotation.x; let th = Math.max(0, -a) * 1.05 + 0.08 + Math.abs(fl) * 0.35;
        const hp = t.g.position;
        for (const [x, y, z] of legPoints(ch, ch.hips, t.side)) {
          const yq = y - hp.y / PX, zq = z - hp.z / PX; if (yq > 0 || yq < -10.5) continue;
          const L = Math.hypot(yq, zq); if (L > 1e-6) th = Math.max(th, Math.asin(Math.min(1, 2.45 / L)) - Math.atan2(zq, -yq) + 0.03);
        }
        t.g.rotation.x = th;
      }
    }
    if (st.veilBack) st.veilBack.rotation.x = 0.1 + Math.abs(fl) * 0.75;
    if (st.items) for (const [side, key] of [['R', 'h'], ['L', 'l']]) {
      const H = st.items[side]; const k = tr && tr[key] ? tr[key][Math.min(j, tr[key].length - 1)] : -1;
      if (k !== H.cur) { if (H.cur >= 0) H.groups[H.cur].visible = false; if (k >= 0) H.groups[k].visible = true; H.cur = k; }
    }
  };
}
