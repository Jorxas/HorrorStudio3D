// Créature surnaturelle du kit horreur : « homme noir / capuche / sans visage / néant » n'est PAS un homme en manteau.
//   * silhouette anormale : plus haute et plus étroite, voûtée, tête penchée, capuche creuse et pointue, manteau en lambeaux
//   * mains : peau noire (jamais la teinte humaine du modèle de base), main plus grande, doigts 1,9 fois plus longs et fins, tressaillements
//   * poses monstrueuses : tête qui s'incline, voussure, bras qui se tendent, griffes (table `poses` du personnage, temps absolu du film)
//   * disparition : fenêtres [t0, t1, comment, réapparition] ; le Python (genre_intent.py) décide si elles sont permises, ici on ne fait que les dessiner
// Données reçues par le seul canal que le rendu partagé transmet à buildFaceless : `look.monster` du contrat. Tout est fonction du temps (aucun hasard).
import * as THREE from 'three';
import { vox } from './props4.js';

const PX = 1 / 16;
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const sm = (k) => { k = clamp(k); return k * k * (3 - 2 * k); };
const hash = (n) => { const s = Math.sin(n * 127.1 + 311.7) * 43758.5453; return s - Math.floor(s); };
const num = (v, d) => (v == null ? d : typeof v === 'number' ? v : parseInt(String(v).replace('#', ''), 16));

// miroir de ARCHETYPES['faceless_void'] de genre_intent.py (tools/check_genre_horror.py compare les deux)
export const DEFAULT_MONSTER = { stretch: [0.88, 1.16, 0.88], head: 1.08, hunch: 0.16, head_tilt: 0.2, shoulder_drop: 0.1, hand_scale: 1.22, finger_len: 1.9, finger_thin: 0.7, finger_twitch: 0.5, stillness: 0.85, void_depth: 1.0, skin: 0x08080b, hood: 0x14161c, boots: 0x0a0a0c };
export const monsterParams = (spec) => { const m = (spec && typeof spec === 'object') ? spec : {}; const o = { ...DEFAULT_MONSTER, ...m }; for (const k of ['skin', 'hood', 'boots']) o[k] = num(o[k], DEFAULT_MONSTER[k]); o.poses = m.poses || []; o.vanish = m.vanish || []; o.fade = m.fade ?? 0.35; return o; };

// poses : deltas sur la posture de base, poids w 0..1 ; `free(side)` = le bras n'est pas piloté par la cinématique inverse (contact, atteinte)
export const MONSTER_POSES = {
  still: () => {},
  head_tilt: (ch, w) => { ch.neck.rotation.z += 0.55 * w; ch.neck.rotation.x += 0.12 * w; },
  loom: (ch, w) => { ch.torso.rotation.x += 0.3 * w; ch.neck.rotation.x -= 0.18 * w; },
  stoop: (ch, w) => { ch.torso.rotation.x += 0.5 * w; ch.neck.rotation.x -= 0.35 * w; ch.neck.rotation.z += 0.2 * w; },
  reach: (ch, w, free) => { if (free('R')) { ch.shR.rotation.x += -1.25 * w; ch.elR.rotation.x += -0.08 * w; } if (free('L')) { ch.shL.rotation.x += -0.35 * w; } },
  claw: (ch, w) => { if (w > 0.05) { ch.setHand('L', 'claw'); ch.setHand('R', 'claw'); } },
  twitch: (ch, w, free, T) => { ch.neck.rotation.z += 0.18 * w * (hash(Math.floor(T * 11)) - 0.5) * 2; },
};

export function buildMonster(buildCharacter4, spec = {}, seed = 40) {
  const P = monsterParams(spec.monster), hoodCol = P.hood, col = (k) => new THREE.Color(hoodCol).multiplyScalar(k).getHex();
  // la peau, les chaussures et la capuche viennent du monstre : le modèle de base (teinte humaine, semelles blanches) ne passe PAS
  const ch = buildCharacter4({ ...spec, skin: P.skin, brow: P.skin, hair: null, hat: null, top: spec.top || { type: 'hoodie', color: hoodCol, shirt: 0x0a0a0c }, shoes: { type: 'boot', color: P.boots } }, seed);
  ch.setExpr = () => {}; ch.faceUpdate = () => {}; ch.faceMat.map = null; ch.faceMat.color.set(0x010102); ch.faceMat.needsUpdate = true;
  const B = [{ x: 0, y: 4.2, z: -4.8, w: 9.8, h: 9.8, d: 1.5, color: col(1) }, { x: 0, y: 8.8, z: -0.4, w: 9.8, h: 1.6, d: 9.8, color: col(1.1) }, { x: 0, y: 4.2, z: 4.9, w: 9.8, h: 1.2, d: 1.0, color: col(0.8) },
    { x: 4.9, y: 4.2, z: -0.2, w: 1.5, h: 9.8, d: 9.6, color: col(0.9) }, { x: -4.9, y: 4.2, z: -0.2, w: 1.5, h: 9.8, d: 9.6, color: col(0.9) }, { x: 0, y: -1.2, z: -0.8, w: 11.4, h: 2.4, d: 8.2, color: col(0.85) }, { x: 0, y: 8.0, z: 5.1, w: 7.6, h: 1.0, d: 0.8, color: col(0.6) },
    // sommet de capuche en pointe, penché vers l'arrière : la silhouette n'est plus celle d'une tête humaine
    { x: 0, y: 10.1, z: -0.9, w: 8.6, h: 1.6, d: 9.2, color: col(1.05) }, { x: 0, y: 11.5, z: -1.8, w: 6.4, h: 1.6, d: 7.6, color: col(0.95) }, { x: 0, y: 12.9, z: -2.9, w: 4.0, h: 1.6, d: 5.6, color: col(0.9) }, { x: 0, y: 14.1, z: -4.0, w: 2.0, h: 1.2, d: 3.4, color: col(0.8) },
    // l'intérieur : un trou plus profond que la tête (le néant), liséré plus sombre sur le front
    { x: 0, y: 5.0, z: 4.55, w: 8.0, h: 8.6, d: 0.5, color: 0x000001 }, { x: 0, y: 9.5, z: 4.7, w: 8.6, h: 0.9, d: 0.7, color: col(0.5) }];
  ch.neck.add(vox(B.map((b) => ({ ...b, x: b.x * PX, y: b.y * PX, z: b.z * PX, w: b.w * PX, h: b.h * PX, d: b.d * PX })), { var: 0.06 }));
  // manteau en lambeaux : cinq pans de longueurs inégales sur le bas du torse (graine fixe)
  const H = []; for (let i = 0; i < 5; i++) { const len = 4 + hash(i * 3.7 + seed) * 5; H.push({ x: (i - 2) * 1.9, y: -len / 2 + 0.4, z: 2.6 - (i % 2) * 0.4, w: 1.8, h: len, d: 0.7, color: col(0.7 + 0.1 * (i % 3)) }); H.push({ x: (i - 2) * 1.9, y: -len / 2 + 0.4, z: -2.8, w: 1.8, h: len * 0.9, d: 0.7, color: col(0.6) }); }
  ch.torso.add(vox(H.map((b) => ({ ...b, x: b.x * PX, y: b.y * PX, z: b.z * PX, w: b.w * PX, h: b.h * PX, d: b.d * PX })), { var: 0.05 }));
  // mains : jamais la teinte humaine, plus grandes, doigts longs et fins (même hiérarchie : la fermeture des doigts de A reste valable)
  for (const [hand, fs, th] of [[ch.handL, ch.fingersL, ch.thumbL], [ch.handR, ch.fingersR, ch.thumbR]]) {
    hand.scale.setScalar(P.hand_scale); for (const f of fs) f.scale.set(P.finger_thin, P.finger_len, P.finger_thin); th.scale.set(P.finger_thin, P.finger_len * 0.85, P.finger_thin);
  }
  // les couches de monsterUpdate s'ajoutent à la pose de base : elles ne valent que sur un corps remis à zéro CETTE image (sinon elles s'accumuleraient)
  const reset0 = ch.reset; ch.reset = () => { reset0(); ch._fresh = true; };
  ch.stretch = [...P.stretch]; ch.headScale = P.head; ch.isMonster = true; ch.monster = P; return ch;
}

// appelé à chaque image après la pose de base (buildExtras) : voussure, tête penchée, tressaillements des doigts, poses déclarées, fenêtres de disparition
export function monsterUpdate(ch, T) {
  const P = ch.monster; if (!P) return;
  for (const [t0, t1] of P.vanish) { if (T >= t0 && T < t1) { ch.root.visible = false; return; } }
  if (!ch._fresh) return; ch._fresh = false;
  const free = (s) => !(s === 'L' ? ch._lockL : ch._lockR);
  if (ch.archUpdate) ch.archUpdate(T, free);          // archétypes non humanoïdes (b_monsters.js) : leur animation propre, après la pose de base de la régie
  const still = P.stillness;
  ch.torso.rotation.x += P.hunch * (0.9 + 0.1 * Math.sin(T * 0.4));
  ch.neck.rotation.x -= P.hunch * 0.5;
  ch.neck.rotation.z += P.head_tilt * (0.75 + 0.25 * Math.sin(T * 0.31 + 1.3)) * (1 - 0.3 * still);
  if (free('L')) ch.shL.rotation.z += P.shoulder_drop; if (free('R')) ch.shR.rotation.z -= P.shoulder_drop;
  // tressaillements : un doigt se crispe par à-coups (tranches de 1/6 s, un tirage fixe par tranche), le reste du temps la main est trop immobile
  for (const [fs, side, key] of [[ch.fingersL, 1, 'L'], [ch.fingersR, -1, 'R']]) {
    if (!free(key)) continue; const n = Math.floor(T * 6), u = T * 6 - n;
    fs.forEach((f, i) => { const h = hash(n * 1.3 + i * 7.31 + (side > 0 ? 31 : 0) + 5.5); if (h > 0.8) f.rotation.z += -side * P.finger_twitch * Math.pow(Math.sin(Math.PI * u), 2) * (0.6 + h); });
  }
  for (const p of P.poses) { const ramp = p.ramp ?? 0.3; if (T < p.t0 - ramp || T > p.t1 + ramp) continue; const w = (p.k ?? 1) * sm((T - (p.t0 - ramp)) / (2 * ramp)) * (1 - sm((T - p.t1) / (2 * ramp + 1e-6))); const f = MONSTER_POSES[p.name]; if (f) f(ch, w, free, T); }
  // disparition douce « ombre » : le corps s'enfonce dans l'obscurité avant la fenêtre et en ressort après ; les autres catégories sont des coupes franches
  const fade = P.fade;
  for (const [t0, t1, how, appear] of P.vanish) {
    if (how === 'shadow' && T >= t0 - fade && T < t0) ch.root.position.y -= 2.6 * sm((T - (t0 - fade)) / fade);
    if ((appear || how) === 'shadow' && t1 < 1e8 && T >= t1 && T < t1 + fade) ch.root.position.y -= 2.6 * (1 - sm((T - t1) / fade));
  }
}
