// Bibliothèque d'animation des personnages v4.1 (bras et jambes articulés : épaule/coude/poignet, hanche/genou/cheville).
// Marche et course humaines (genoux qui plient, pied qui déroule, bras qui balancent avec le coude, bassin et épaules
// en opposition), pieds posés au sol, cinématique inverse des bras (atteindre un point), prises qui se referment
// vraiment (barre, cheville). Tout est fonction du temps (déterministe).
import * as THREE from 'three';
import { PX } from './rig.js';

export const clamp01 = (x) => Math.min(1, Math.max(0, x));
export const ease = (x) => { x = clamp01(x); return x * x * (3 - 2 * x); };
export const eio = (x) => { x = clamp01(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
export const eout = (x) => 1 - Math.pow(1 - clamp01(x), 3);
export const lerp = (a, b, k) => a + (b - a) * k;
export const seg = (t, a, b) => clamp01((t - a) / (b - a));
const wrap = (a) => { a = (a + Math.PI) % (2 * Math.PI); if (a < 0) a += 2 * Math.PI; return a - Math.PI; };
const bump = (p, c, w) => { const v = Math.cos(wrap(p - c) * w); return Math.abs(wrap(p - c) * w) < Math.PI / 2 ? v * v : 0; };
const V3 = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
const hipY = (ch) => ch.hipY ?? 12 * PX;

export function put(ch, x, z, yaw, groundY, dy = 0) { ch.reset(); ch.root.position.set(x, groundY(x, z) + dy, z); ch.root.rotation.y = yaw; }

// ---- jambes : angles « vers l'avant » (cuisse a, genou k = flexion, pied b = pointe relevée, en absolu)
function setLeg(ch, side, a, k, b) {
  const lg = side > 0 ? ch.lgL : ch.lgR, kn = side > 0 ? ch.knL : ch.knR, ft = side > 0 ? ch.ftL : ch.ftR;
  lg.rotation.x = -a; if (kn) kn.rotation.x = k; if (ft) ft.rotation.x = -(b - (a - k));
  const toe = side > 0 ? ch.toeL : ch.toeR; if (toe) toe.rotation.x = Math.min(0, b);   // talon levé : les orteils restent à plat
}
// hauteur du bassin pour que le pied le plus bas touche le sol (repère du personnage)
function footDrop(ch, a, k, b) {
  const L = ch.LEN || { th: 6.5 * PX, sh: 5.5 * PX, ft: 2 * PX }; const H = L.ft;
  const ank = L.th * Math.cos(a) + L.sh * Math.cos(a - k);
  return ank + Math.max(H * Math.cos(b) + 2.3 * PX * Math.sin(b), H * Math.cos(b) - 1.9 * PX * Math.sin(b));   // talon / pli des orteils
}
export function plant(ch, legs, lift = 0) { let d = 0; for (const [a, k, b] of legs) d = Math.max(d, footDrop(ch, a, k, b)); ch.hips.position.y = d + lift; return d; }
// lit les angles actuels d'une jambe (pour poser au sol après une pose manuelle)
export function legAngles(ch, side) {
  const lg = side > 0 ? ch.lgL : ch.lgR, kn = side > 0 ? ch.knL : ch.knR, ft = side > 0 ? ch.ftL : ch.ftR;
  const a = -lg.rotation.x, k = kn ? kn.rotation.x : 0; return [a, k, -(ft ? ft.rotation.x : 0) + (a - k)];
}
export function ground(ch, lift = 0) { return plant(ch, [legAngles(ch, 1), legAngles(ch, -1)], lift); }

// ---- marche humaine : phase en radians, amp ~0.6 (normal) … 1 (pressé)
export function walk(ch, phase, amp = 0.6) {
  const s = amp / 0.6; const legs = [];
  for (const side of [1, -1]) {
    const p = phase + (side > 0 ? 0 : Math.PI);
    const a = 0.36 * s * Math.sin(p);                                                   // cuisse
    const k = s * (0.95 * bump(p, -0.35, 1.05) + 0.16 * bump(p, Math.PI / 2 + 0.5, 2.2));  // genou : plié pendant le pas, léger amorti à l'appui
    const b = s * (0.22 * bump(p, Math.PI / 2 + 0.05, 2.4) - 0.42 * bump(p, -Math.PI / 2 - 0.4, 2.4) + 0.1 * bump(p, 0.15, 1.6)); // talon, appui, poussée
    setLeg(ch, side, a, k, b); legs.push([a, k, b]);
    const sh = side > 0 ? ch.shL : ch.shR, el = side > 0 ? ch.elL : ch.elR;
    sh.rotation.x = 0.62 * a; sh.rotation.z = side * 0.06; if (el) el.rotation.x = -(0.28 + 0.32 * s * (0.5 - 0.5 * Math.sin(p)));
  }
  plant(ch, legs, 0.004 * s * Math.cos(2 * phase));
  ch.hips.rotation.y = 0.07 * s * Math.sin(phase); ch.hips.rotation.z = 0.03 * s * Math.cos(phase);
  ch.torso.rotation.y = -0.12 * s * Math.sin(phase); ch.torso.rotation.x = 0.04 * s; ch.torso.rotation.z = -0.02 * s * Math.cos(phase);
  ch.neck.rotation.y += 0.05 * s * Math.sin(phase); ch.neck.rotation.z += 0.02 * s * Math.cos(phase);
  ch.setHands('relaxed');
}
export function run(ch, phase, amp = 1) {
  const s = amp; const legs = [];
  for (const side of [1, -1]) {
    const p = phase + (side > 0 ? 0 : Math.PI);
    const a = 0.1 + 0.62 * s * Math.sin(p);
    const k = s * (1.7 * bump(p, -0.55, 0.95) + 0.35 * bump(p, Math.PI / 2 + 0.4, 2.0));
    const b = s * (0.15 * bump(p, Math.PI / 2, 2.4) - 0.6 * bump(p, -Math.PI / 2 - 0.3, 2.2) + 0.15 * bump(p, 0.2, 1.6));
    setLeg(ch, side, a, k, b); legs.push([a, k, b]);
    const sh = side > 0 ? ch.shL : ch.shR, el = side > 0 ? ch.elL : ch.elR;
    sh.rotation.x = 0.95 * (a - 0.1) - 0.15; sh.rotation.z = side * 0.1; if (el) el.rotation.x = -(1.25 + 0.25 * Math.sin(p));
  }
  plant(ch, legs, 0.05 * s * Math.max(0, Math.cos(2 * phase - 0.6)));
  ch.hips.rotation.y = 0.1 * s * Math.sin(phase); ch.torso.rotation.y = -0.16 * s * Math.sin(phase); ch.torso.rotation.x = 0.22 * s; ch.neck.rotation.x -= 0.12 * s;
  ch.setHands('fist');
}
export function breathe(ch, t, k = 1) {
  const b = Math.sin(t * 1.9 + ch.root.position.x * 3);
  ch.torso.rotation.x += 0.012 * b * k; ch.shL.rotation.z += (0.04 + 0.012 * b) * k; ch.shR.rotation.z -= (0.04 + 0.012 * b) * k; ch.neck.rotation.x += 0.01 * b * k;
  if (ch.elL) { ch.elL.rotation.x -= 0.1 * k; ch.elR.rotation.x -= 0.1 * k; }
}
// regarde un point du monde (lacet + tangage limités)
export function lookAt(ch, target, k = 1) {
  ch.root.updateMatrixWorld(true); const p = new THREE.Vector3(); ch.neck.getWorldPosition(p);
  const d = target.clone().sub(p); const yawW = Math.atan2(d.x, d.z); let yaw = yawW - ch.root.rotation.y - ch.torso.rotation.y;
  while (yaw > Math.PI) yaw -= 2 * Math.PI; while (yaw < -Math.PI) yaw += 2 * Math.PI;
  const pitch = -Math.atan2(d.y, Math.hypot(d.x, d.z));
  ch.neck.rotation.y += Math.max(-1.1, Math.min(1.1, yaw)) * k; ch.neck.rotation.x += Math.max(-0.6, Math.min(0.7, pitch)) * k;
}
// poses : valeurs de rotation ajoutées, mélangées par k (0..1) — coudes compris
const POSES = {
  coldHug: { shL: [-0.5, 0, -0.32], shR: [-0.5, 0, 0.32], elL: [-1.85, 0, 0], elR: [-1.85, 0, 0], neck: [0.15, 0, 0], torso: [0.08, 0, 0] },
  pockets: { shL: [0.08, 0, 0.12], shR: [0.08, 0, -0.12], elL: [-0.3, 0, 0], elR: [-0.3, 0, 0], torso: [0.03, 0, 0] },
  lookDown: { neck: [0.45, 0, 0], torso: [0.12, 0, 0] },
  lookUp: { neck: [-0.55, 0, 0], torso: [-0.06, 0, 0] },
  reachR: { shR: [-1.4, 0, 0.12], elR: [-0.12, 0, 0] }, reachL: { shL: [-1.4, 0, -0.12], elL: [-0.12, 0, 0] },
  hug: { shL: [-1.1, 0, -0.45], shR: [-1.1, 0, 0.45], elL: [-1.0, 0, 0], elR: [-1.0, 0, 0], torso: [0.1, 0, 0] },
  armsOpen: { shL: [-0.35, 0, 1.0], shR: [-0.35, 0, -1.0], elL: [-0.35, 0, 0], elR: [-0.35, 0, 0], neck: [-0.25, 0, 0] },
  holdLantern: { shR: [-0.35, 0, 0.05], elR: [-0.75, 0, 0] },
  wave: { shR: [-2.5, 0, -0.35], elR: [-0.9, 0, 0] },
  handOut: { shR: [-0.45, 0, -0.15], elR: [-0.45, 0, 0] }, handOutL: { shL: [-0.45, 0, 0.15], elL: [-0.45, 0, 0] },
  sad: { neck: [0.35, 0, 0], torso: [0.15, 0, 0], shL: [0.05, 0, 0.02], shR: [0.05, 0, -0.02], elL: [-0.2, 0, 0], elR: [-0.2, 0, 0] },
  throwR: { shR: [-2.3, 0, 0.1], elR: [-0.6, 0, 0], torso: [-0.1, 0.25, 0] },
  guard: { shL: [-0.7, 0, -0.1], shR: [-0.7, 0, 0.1], elL: [-1.5, 0, 0], elR: [-1.5, 0, 0], torso: [0.12, 0, 0], neck: [0.1, 0, 0] },
};
export function pose(ch, name, k = 1) {
  const p = POSES[name]; if (!p || k <= 0) return;
  for (const part in p) { if (!ch[part]) continue; const [x, y, z] = p[part]; ch[part].rotation.x += x * k; ch[part].rotation.y += y * k; ch[part].rotation.z += z * k; }
}
// assis sur un siège de hauteur seatH : cuisses à l'horizontale, tibias verticaux, pieds à plat
export function sit(ch, k = 1, seatH = 0.48) {
  ch.hips.position.y = lerp(hipY(ch), seatH + 0.02, k);
  for (const side of [1, -1]) { const lg = side > 0 ? ch.lgL : ch.lgR, kn = side > 0 ? ch.knL : ch.knR, ft = side > 0 ? ch.ftL : ch.ftR; lg.rotation.x += -1.5 * k; if (kn) kn.rotation.x += 1.25 * k; if (ft) ft.rotation.x += -0.22 * k; }
  ch.torso.rotation.x += -0.05 * k; if (ch.elL) { ch.elL.rotation.x -= 0.5 * k; ch.elR.rotation.x -= 0.5 * k; ch.shL.rotation.x -= 0.2 * k; ch.shR.rotation.x -= 0.2 * k; }
}
// un genou à terre (genou droit au sol, pied gauche à plat devant)
export function kneel(ch, k = 1) {
  const L = ch.LEN || { th: 5.5 * PX }; const legs = [[1.25 * k, 1.35 * k, 0], [-0.05 * k, 1.6 * k, -1.1 * k]];
  setLeg(ch, 1, ...legs[0]); setLeg(ch, -1, ...legs[1]);
  ch.hips.position.y = lerp(hipY(ch), L.th * Math.cos(0.05) + 2.0 * PX, k); ch.torso.rotation.x += 0.18 * k;
}
export function crouch(ch, k = 1) {
  const legs = [[1.05 * k, 1.95 * k, 0], [1.05 * k, 1.95 * k, 0]]; setLeg(ch, 1, ...legs[0]); setLeg(ch, -1, ...legs[1]);
  plant(ch, legs); ch.torso.rotation.x += 0.4 * k; if (ch.elL) { ch.elL.rotation.x -= 0.6 * k; ch.elR.rotation.x -= 0.6 * k; ch.shL.rotation.x -= 0.4 * k; ch.shR.rotation.x -= 0.4 * k; }
}
// saut : renvoie la hauteur (à ajouter à root.position.y) ; anticipation + atterrissage
export function jump(ch, t, t0, dur = 0.7, height = 0.9) {
  const a = (t - t0) / dur;
  if (a < -0.25 || a > 1.25) return 0;
  if (a < 0) { crouch(ch, ease((a + 0.25) / 0.25) * 0.6); return 0; }
  if (a > 1) { crouch(ch, (1 - ease((a - 1) / 0.25)) * 0.5); return 0; }
  const m = Math.sin(a * Math.PI);
  ch.shL.rotation.x += -2.2 * m; ch.shR.rotation.x += -2.2 * m; if (ch.elL) { ch.elL.rotation.x -= 0.4 * m; ch.elR.rotation.x -= 0.4 * m; }
  setLeg(ch, 1, 0.6 * m, 1.0 * m, -0.3 * m); setLeg(ch, -1, 0.2 * m, 0.7 * m, -0.4 * m);
  return 4 * height * a * (1 - a);
}

// ---- cinématique inverse du bras : place le poignet en target (monde). pole = direction (repère du torse) vers laquelle pointe le coude.
const _m = new THREE.Matrix4(), _q = new THREE.Quaternion();
export function reach(ch, side, target, pole = null) {
  const sg = side === 'L' ? 1 : -1, sh = sg > 0 ? ch.shL : ch.shR, el = sg > 0 ? ch.elL : ch.elR;
  ch.root.updateMatrixWorld(true);
  const T = target.clone().applyMatrix4(_m.copy(sh.parent.matrixWorld).invert()).sub(sh.position);
  const L1 = 4.0 * PX, L2 = 5.05 * PX; const D = Math.min(Math.max(T.length(), Math.abs(L1 - L2) + 1e-3), (L1 + L2) * 0.999);
  const Th = T.clone().normalize(); const al = Math.acos(Math.min(1, Math.max(-1, (L1 * L1 + D * D - L2 * L2) / (2 * L1 * D))));
  const P = (pole ? pole.clone() : V3(sg * 0.55, -0.45, -0.7)); const Pp = P.sub(Th.clone().multiplyScalar(P.dot(Th))).normalize();
  const U = Th.clone().multiplyScalar(Math.cos(al)).add(Pp.clone().multiplyScalar(Math.sin(al)));
  const F = Th.clone().multiplyScalar(D).sub(U.clone().multiplyScalar(L1)).normalize();
  const Y = U.clone().negate(); let Z = F.clone().sub(U.clone().multiplyScalar(F.dot(U))); if (Z.lengthSq() < 1e-8) Z = Pp.clone().negate(); Z.normalize();
  const X = new THREE.Vector3().crossVectors(Y, Z);
  sh.quaternion.setFromRotationMatrix(_m.makeBasis(X, Y, Z));
  el.rotation.set(-Math.acos(Math.min(1, Math.max(-1, U.dot(F)))), 0, 0);
  ch.root.updateMatrixWorld(true);
}
// oriente la main (repère monde) : X, Y, Z = axes locaux voulus de la main
export function orientHand(ch, side, X, Y, Z) {
  const hand = side === 'L' ? ch.handL : ch.handR; hand.parent.updateMatrixWorld(true);
  const qw = new THREE.Quaternion().setFromRotationMatrix(_m.makeBasis(X, Y, Z)); const qp = hand.parent.getWorldQuaternion(_q);
  hand.quaternion.copy(qp.invert().multiply(qw)); hand.updateMatrixWorld(true);
}
// prise d'une barre : axe A (monde, unitaire), point C sur l'axe, rayon r. La paume se plaque, les doigts s'enroulent, le pouce se referme.
export function grip(ch, side, C, A, r = 0.035, pole = null, close = 1, thumbUp = true) {
  const sg = side === 'L' ? 1 : -1; const s = ch.root.scale.x || 1; const A0 = A.clone().normalize(); if (thumbUp && A0.y < 0) A0.negate();
  // 1) approche : poignet vers C pour connaître la direction de l'avant-bras
  reach(ch, side, C, pole);
  const elb = (sg > 0 ? ch.elL : ch.elR).getWorldPosition(V3());
  let Yh = elb.clone().sub(C); Yh.sub(A0.clone().multiplyScalar(Yh.dot(A0))).normalize();
  const Zh = A0.clone(), Xh = new THREE.Vector3().crossVectors(Yh, Zh).normalize();
  // point de prise dans le repère de la main (l'axe de la barre passe là) → position du poignet
  const G = V3(-sg * (1.25 * PX + r / s * 0.9), -2.3 * PX, 0.15 * PX).multiplyScalar(s);
  const wrist = C.clone().sub(Xh.clone().multiplyScalar(G.x)).sub(Yh.clone().multiplyScalar(G.y)).sub(Zh.clone().multiplyScalar(G.z));
  for (let i = 0; i < 2; i++) { reach(ch, side, wrist, pole); orientHand(ch, side, Xh, Yh, Zh); }
  ch.setHand(side, [1.32 * close, 0, 1.0 * close, 1.55 * close]);
}

export function blink(t, seed = 0) { return ((t * 0.31 + seed) % 1) < 0.035; }
export function expr(ch, name, t, seed = 0) { ch.setExpr(name); }
export function talk(ch, k = 1) { if (ch.face) ch.face.talk = k; }
// assouplit un bras resté tendu : la main garde son orientation, le poignet se rapproche un peu de l'épaule et le coude plie
export function soften(ch, side, amount = 0.025, pole = null) {
  const sh = side === 'L' ? ch.shL : ch.shR, hand = side === 'L' ? ch.handL : ch.handR;
  ch.root.updateMatrixWorld(true);
  const S = sh.getWorldPosition(V3()), W = hand.getWorldPosition(V3()), Q = hand.getWorldQuaternion(new THREE.Quaternion());
  const target = S.clone().add(W.sub(S).multiplyScalar(1 - amount));
  // le coude part vers l'arrière et vers l'extérieur, dans le repère du torse
  const sg = side === 'L' ? 1 : -1; reach(ch, side, target, pole || V3(sg * 0.6, -0.2, -1));
  hand.parent.updateMatrixWorld(true); const qp = hand.parent.getWorldQuaternion(new THREE.Quaternion()); hand.quaternion.copy(qp.invert().multiply(Q)); ch.root.updateMatrixWorld(true);
}
// passe automatique : les bras dont le coude n'a pas été réglé ne restent jamais raides
export function relaxArms(ch, amount = 0.022) {
  for (const side of ['L', 'R']) { const el = side === 'L' ? ch.elL : ch.elR; if (!el || Math.abs(el.rotation.x) > 1e-4 || ch['_lock' + side]) continue; soften(ch, side, amount); }
}
// une main de créature (buildGraspHand) qui serre la cheville : paume contre le tibia, doigts enroulés autour
export function grabAnkle(h, ch, side, close = 1, scale = 1.15, up = 0.6, y = -3.4, az = 0.72) {
  const kn = side === 'L' ? ch.knL : ch.knR; ch.root.updateMatrixWorld(true);
  const s = ch.root.scale.x || 1; const k = 0.045 * scale;
  const C = kn.localToWorld(V3(0, y * PX, 0));                      // axe du tibia (y : hauteur sous le genou, en px)
  const A = kn.localToWorld(V3(0, 1, 0)).sub(kn.localToWorld(V3())).normalize();        // axe du tibia
  const back = kn.localToWorld(V3(0, 0, -1)).sub(kn.localToWorld(V3())).normalize();    // arrière de la jambe
  const out = kn.localToWorld(V3(side === 'L' ? 1 : -1, 0, 0)).sub(kn.localToWorld(V3())).normalize();
  // la paume se plaque derrière/à l'extérieur du tibia ; normale de paume (z de la main) vers l'axe
  const n = back.clone().multiplyScalar(Math.cos(az)).add(out.clone().multiplyScalar(Math.sin(az))).normalize().negate();   // az : 0 derrière, π/2 extérieur, π devant
  let Yd = new THREE.Vector3().crossVectors(A, n).normalize(); Yd = Yd.multiplyScalar(Math.cos(up)).add(A.clone().multiplyScalar(Math.sin(up) * 0.4)).normalize();
  const Z = n.clone().sub(Yd.clone().multiplyScalar(n.dot(Yd))).normalize(), X = new THREE.Vector3().crossVectors(Yd, Z);
  h.g.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(X, Yd, Z));
  const half = 2.05 * PX * s + 0.6 * k;     // demi-largeur du tibia + demi-épaisseur de paume
  const palmC = C.clone().sub(n.clone().multiplyScalar(half));
  h.g.position.copy(palmC).sub(Yd.clone().multiplyScalar(2 * k)); if (h.g.parent) h.g.parent.worldToLocal(h.g.position);
  if (h.g.parent) { const qp = h.g.parent.getWorldQuaternion(new THREE.Quaternion()); h.g.quaternion.premultiply(qp.invert()); }
  h.g.scale.setScalar(scale); h.set(1.35 * close, 0.12);
}
