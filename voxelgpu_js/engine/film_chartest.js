// Banc d'essai des personnages v4.1 : mêmes décors que « Le dernier bus », plans fixes d'une seconde
// (visages, plein pied, marche, course, assis, accroché à la barre, mains, accroupi, à genoux).
import { setup as setupBus } from './film_dernier_bus.js';
import { buildGraspHand } from './sets4.js';
export const format = 'portrait';
export async function setup(ctx) {
  const F = await setupBus(ctx); const E = F.E; const { V, anim, noe, lina, bus, st, THREE } = E;
  const shots = []; let T = 0; const add = (name, cam, fn, dur = 1) => { shots.push({ name, t0: T, cam, fn }); T += dur; };
  // plateau neutre (loin des décors) : sol gris clair à petits carreaux, fond arrondi, éclairage trois points
  const O = V(1000, 0, 0); const stage = new THREE.Group(); stage.position.copy(O); ctx.scene.add(stage);
  { const cv = document.createElement('canvas'); cv.width = cv.height = 64; const g = cv.getContext('2d'); for (let y = 0; y < 8; y++) for (let x = 0; x < 8; x++) { const v = 150 + ((x * 7 + y * 13) % 5) * 6; g.fillStyle = `rgb(${v},${v - 4},${v - 10})`; g.fillRect(x * 8, y * 8, 8, 8); }
    const tx = new THREE.CanvasTexture(cv); tx.magFilter = THREE.NearestFilter; tx.wrapS = tx.wrapT = THREE.RepeatWrapping; tx.repeat.set(20, 20); tx.colorSpace = THREE.SRGBColorSpace;
    const fl = new THREE.Mesh(new THREE.PlaneGeometry(20, 20), new THREE.MeshLambertMaterial({ map: tx })); fl.rotation.x = -Math.PI / 2; fl.receiveShadow = true; stage.add(fl);
    const bg = new THREE.Mesh(new THREE.CylinderGeometry(9, 9, 12, 48, 1, true, Math.PI * 0.5, Math.PI), new THREE.MeshLambertMaterial({ color: 0x8a8f9a, side: THREE.BackSide })); bg.position.set(0, 6, 0); stage.add(bg); }
  const S0 = (S, t) => { S.sets = []; S.key = { dir: [0.6, 0.9, 0.8], color: 0xfff2e4, i: 1.6 }; S.hemi = { sky: 0xb8c4dc, ground: 0x4a4038, i: 0.75 }; S.fill = { dir: [-0.8, 0.3, 0.5], color: 0xa8b8e8, i: 0.45 };
    S.lights = [{ pos: O.clone().add(V(-2, 2.6, -2.5)), color: 0xffe0c0, i: 2.5, dist: 7 }]; S.rim = { color: 0xffe8d0, i: 0.25, pow: 4 }; S.edge = null; S.spark = null; S.fog = { color: 0x8a8f9a, d: 0.01 }; S.bg = 0x8a8f9a;
    S.bloom = 0.25; S.bloomThreshold = 0.95; S.contrast = 0.15; S.vignette = 0.35; S.sat = 1.05; S.dofScale = 0.12; S.shadowC = O.clone(); S.shadowS = 5; S.reflect = null; S.focus = 2; };
  const P = (x, z) => O.clone().add(V(x, 0, z));
  const stand = (ch, x, z, yaw, t, expr = 'neutral') => { anim.put(ch, P(x, z).x, P(x, z).z, yaw, () => 0); ch.root.visible = true; anim.breathe(ch, t); anim.expr(ch, expr, t); };
  const head = (ch) => { ch.root.updateMatrixWorld(true); return ch.head.getWorldPosition(V()); };
  const orbit = (ch, ang, dist, lookH, camH = lookH, fov = 40) => { ch.root.updateMatrixWorld(true); const c = ch.root.position.clone(); const yaw = ch.root.rotation.y + ang; return { pos: c.clone().add(V(Math.sin(yaw) * dist, camH, Math.cos(yaw) * dist)), look: c.clone().add(V(0, lookH, 0)), fov, roll: 0 }; };
  const camFace = (ch, d = 1.2, dx = 0.25, dy = 0) => { const h = head(ch); const f = ch.head.getWorldDirection(V()); return { pos: h.clone().addScaledVector(f, d).add(V(dx, dy, 0)), look: h.clone().add(V(0, -0.03, 0)), fov: 40, roll: 0 }; };
  // 0-4 : visages de Noé (peur, cri, inquiet, déterminé, sourire)
  for (const ex of ['scared', 'scream', 'worried', 'determined', 'smile']) add('noe_' + ex, (lt, u, t) => { stand(noe, 0, 0, 0.3, t, ex); return camFace(noe); }, (lt, u, t, S) => { S0(S, t); stand(noe, 0, 0, 0.3, t, ex); S.focus = 1.2; });
  // 5 : plein pied 3/4
  add('noe_full', (lt, u, t) => { stand(noe, 0, 0, 0.45, 0); return orbit(noe, 0.5, 3.6, 1.0, 1.15, 40); }, (lt, u, t, S) => { S0(S, t); stand(noe, 0, 0, 0.45, t, 'neutral'); S.focus = 3.5; });
  // 6-7 : marche (profil, 3/4)
  add('walk_side', (lt) => { stand(noe, 0, 0, 0, 0); return orbit(noe, Math.PI / 2, 3.8, 0.95, 1.0, 40); }, (lt, u, t, S) => { S0(S, t); stand(noe, 0, 0, 0, t, 'determined'); anim.walk(noe, 1.1, 0.7); S.focus = 3.4; });
  add('walk_34', (lt) => { stand(noe, 0, 0, 0, 0); return orbit(noe, 0.6, 3.8, 0.95, 1.1, 40); }, (lt, u, t, S) => { S0(S, t); stand(noe, 0, 0, 0, t, 'worried'); anim.walk(noe, 2.6, 0.7); S.focus = 3.5; });
  // 8 : course
  add('run', (lt) => { stand(noe, 0, 0, 0, 0); return orbit(noe, 1.3, 3.8, 0.9, 1.0, 40); }, (lt, u, t, S) => { S0(S, t); stand(noe, 0, 0, 0, t, 'scared'); anim.run(noe, 1.3, 1); S.focus = 3.2; });
  // 9 : assis (dans le bus)
  const SZ = -6.92, SX = -0.98;
  add('sit_bus', (lt) => ({ pos: bus.w(0.35, 1.25, SZ + 1.9), look: bus.w(-0.9, 0.85, SZ), fov: 46, roll: 0 }), (lt, u, t, S) => { E.lookBus(S, t, { red: 0 }); S.edge = null; S.spark = null; bus.setTubes(0, t); anim.put(noe, SX, SZ + 0.04, Math.PI, () => bus.group.position.y); anim.sit(noe, 1, 0.44); noe.root.visible = true; anim.expr(noe, 'worried', t); S.focus = 2.1; });
  // 10-11 : accroché à la barre (main en gros plan puis plein pied)
  const POLE = bus.poles.reduce((a, p) => (Math.abs(p.local.z - (SZ - 0.1)) < Math.abs(a.local.z - (SZ - 0.1)) ? p : a));
  const hold = (t) => {
    anim.put(noe, bus.w(-0.12, 0, POLE.local.z + 0.22).x, bus.w(0, 0, POLE.local.z + 0.22).z, -0.6, () => bus.group.position.y); noe.root.visible = true;
    anim.walk(noe, 2.2, 0.75); noe.torso.rotation.x = 0.05; noe.torso.rotation.z = 0.12; anim.expr(noe, 'scream', t);
    const C = bus.w(POLE.local.x, 1.55, POLE.local.z); anim.grip(noe, 'L', C, V(0, 1, 0), 0.034);
    noe.shR.rotation.set(-0.6, 0, -0.5); noe.elR.rotation.set(-0.9, 0, 0); noe.setHand('R', 'open'); noe.neck.rotation.set(0.05, 0.25, -0.08);
  };
  add('pole_hand', (lt) => { hold(0); return { pos: bus.w(POLE.local.x * 0.1, 1.72, POLE.local.z + 0.8), look: bus.w(POLE.local.x, 1.52, POLE.local.z), fov: 40, roll: 0 }; },
    (lt, u, t, S) => { E.lookBus(S, t, { red: 0.3 }); S.edge = null; S.spark = null; bus.setTubes(0, t); hold(t); S.focus = 0.75; });
  add('pole_full', (lt) => ({ pos: bus.w(-0.4, 0.7, POLE.local.z + 2.6), look: bus.w(-0.1, 1.0, POLE.local.z), fov: 58, roll: 0 }),
    (lt, u, t, S) => { E.lookBus(S, t, { red: 0.3 }); S.edge = null; S.spark = null; bus.setTubes(0, t); hold(t); bus.showPoles(bus.poles.map((p, i) => i).filter((i) => bus.poles[i].local.z > POLE.local.z + 0.5)); S.focus = 2.6; });
  // 12-13 : Lina visage + plein pied
  add('lina_face', (lt, u, t) => { stand(lina, 0, 0, -0.3, t, 'scared'); return camFace(lina, 1.2, -0.25); }, (lt, u, t, S) => { S0(S, t); stand(lina, 0, 0, -0.3, t, 'scared'); S.focus = 1.2; });
  add('lina_walk', (lt) => { stand(lina, 0, 0, 0.2, 0); return orbit(lina, 0.6, 3.8, 0.9, 1.1, 40); }, (lt, u, t, S) => { S0(S, t); stand(lina, 0, 0, 0.2, t, 'worried'); anim.walk(lina, 0.8, 0.65); S.focus = 3.5; });
  // 14 : mains (gros plan) poing / ouverte
  add('hands', (lt) => { stand(noe, 0, 0, 0, 0); return orbit(noe, 0.35, 1.9, 1.0, 1.15, 40); },
    (lt, u, t, S) => { S0(S, t); stand(noe, 0, 0, 0, t, 'neutral'); noe.shL.rotation.set(-0.9, 0, 0.25); noe.elL.rotation.x = -0.6; noe.shR.rotation.set(-0.9, 0, -0.25); noe.elR.rotation.x = -0.6; noe.setHands('open', 'fist'); S.focus = 1.2; });
  // 15-16 : accroupi, à genoux
  add('crouch', (lt) => { stand(noe, 0, 0, 0.6, 0); return orbit(noe, 1.2, 3.0, 0.6, 0.8, 40); }, (lt, u, t, S) => { S0(S, t); stand(noe, 0, 0, 0.6, t, 'scared'); anim.crouch(noe, 1); S.focus = 3; });
  add('kneel', (lt) => { stand(noe, 0, 0, 0.6, 0); return orbit(noe, 1.2, 3.0, 0.6, 0.8, 40); }, (lt, u, t, S) => { S0(S, t); stand(noe, 0, 0, 0.6, t, 'determined'); anim.kneel(noe, 1); S.focus = 3; });
  add('close_arm', (lt) => { stand(noe, 0, 0, 0, 0); return orbit(noe, 1.0, 1.3, 0.95, 1.05, 40); }, (lt, u, t, S) => { S0(S, t); stand(noe, 0, 0, 0, t, 'neutral'); noe.shL.rotation.set(-0.5, 0, 0.1); noe.elL.rotation.x = -1.3; noe.setHands('relaxed'); S.focus = 1.3; });
  add('close_leg', (lt) => { stand(noe, 0, 0, 0, 0); return orbit(noe, 1.2, 1.5, 0.35, 0.45, 40); }, (lt, u, t, S) => { S0(S, t); stand(noe, 0, 0, 0, t, 'neutral'); anim.walk(noe, 2.4, 0.8); S.focus = 1.5; });
  add('close_back', (lt) => { stand(noe, 0, 0, 0, 0); return orbit(noe, 2.5, 1.7, 1.5, 1.7, 40); }, (lt, u, t, S) => { S0(S, t); stand(noe, 0, 0, 0, t, 'neutral'); anim.pose(noe, 'armsOpen', 0.6); S.focus = 1.7; });
  add('noe_34', (lt, u, t) => { stand(noe, 0, 0, 0.3, t, 'scared'); return orbit(noe, 0.7, 1.4, 1.75, 1.8, 40); }, (lt, u, t, S) => { S0(S, t); stand(noe, 0, 0, 0.3, t, 'scared'); S.focus = 1.4; });
  add('lina_34', (lt, u, t) => { stand(lina, 0, 0, -0.3, t, 'worried'); return orbit(lina, -0.7, 1.4, 1.65, 1.7, 40); }, (lt, u, t, S) => { S0(S, t); stand(lina, 0, 0, -0.3, t, 'worried'); S.focus = 1.4; });
  add('pole_hand2', (lt) => { hold(0); return { pos: bus.w(POLE.local.x * 0.3, 1.45, POLE.local.z - 0.75), look: bus.w(POLE.local.x, 1.52, POLE.local.z), fov: 40, roll: 0 }; },
    (lt, u, t, S) => { E.lookBus(S, t, { red: 0.3 }); S.edge = null; S.spark = null; bus.setTubes(0, t); hold(t); S.focus = 0.75; });
  add('hands_close', (lt) => { stand(noe, 0, 0, 0, 0); noe.shL.rotation.set(-0.7, 0, 0.3); noe.elL.rotation.x = -0.9; noe.root.updateMatrixWorld(true); const h = noe.handL.getWorldPosition(V()); return { pos: h.clone().add(V(-0.3, 0.25, 0.9)), look: h.clone().add(V(-0.3, -0.05, 0)), fov: 40, roll: 0 }; },
    (lt, u, t, S) => { S0(S, t); stand(noe, 0, 0, 0, t, 'neutral'); noe.shL.rotation.set(-0.7, 0, 0.3); noe.elL.rotation.x = -0.9; noe.shR.rotation.set(-0.7, 0, -0.3); noe.elR.rotation.x = -0.9; noe.setHands('relaxed', 'fist'); S.focus = 1.0; });
  const gh = buildGraspHand(1, 3); ctx.scene.add(gh.g); gh.g.visible = false;
  for (const [nm, az, ang] of [['grab_front', 3.6, 0.6], ['grab_side', 3.6, -1.2], ['grab_back', 0.72, 0.6]]) add(nm, (lt) => { stand(noe, 0, 0, 0, 0); return orbit(noe, ang, 1.3, 0.3, 0.55, 40); },
    (lt, u, t, S) => { S0(S, t); stand(noe, 0, 0, 0, t, 'scared'); gh.g.visible = true; anim.grabAnkle(gh, noe, 'R', 1, 1.15, 0.6, -1.7, az); S.focus = 1.3; });
  // 27 : marche animée (3 s), vitesse accordée au pas pour que le pied d'appui ne glisse pas
  const walkAt = (ch, lt, t, ex) => { const x = -1.5 + lt * 0.95; stand(ch, x, 0, Math.PI / 2, t, ex); anim.walk(ch, lt * 7, 0.6); return x; };
  add('walk_anim', (lt, u, t) => { const x = walkAt(noe, lt, t, 'neutral'); return { pos: P(0.9 + lt * 0.3, 3.6).add(V(0, 1.25, 0)), look: P(x * 0.6, 0).add(V(0, 0.95, 0)), fov: 40, roll: 0 }; },
    (lt, u, t, S) => { S0(S, t); walkAt(noe, lt, t, 'neutral'); S.focus = 3.7; }, 3);
  add('run_anim', (lt, u, t) => { const x = -3 + lt * 3.2; stand(noe, x, 0, Math.PI / 2, t, 'scared'); anim.run(noe, lt * 11, 1); return { pos: P(1.2, 3.8).add(V(0, 1.1, 0)), look: P(x * 0.7, 0).add(V(0, 0.9, 0)), fov: 44, roll: 0 }; },
    (lt, u, t, S) => { S0(S, t); const x = -3 + lt * 3.2; stand(noe, x, 0, Math.PI / 2, t, 'scared'); anim.run(noe, lt * 11, 1); S.focus = 3.8; }, 2);
  for (const [nm, ph, ang] of [['shoe_side', 0.4, Math.PI / 2], ['shoe_push', 2.3, Math.PI / 2], ['shoe_34', 1.2, 0.7]]) add(nm, (lt) => { stand(noe, 0, 0, 0, 0); anim.walk(noe, ph, 0.7); return orbit(noe, ang, 1.5, 0.22, 0.32, 40); },
    (lt, u, t, S) => { S0(S, t); stand(noe, 0, 0, 0, t, 'neutral'); anim.walk(noe, ph, 0.7); S.focus = 1.5; });
  for (let i = 0; i < shots.length - 1; i++) shots[i].t1 = shots[i + 1].t0; shots[shots.length - 1].t1 = T;
  return { ...F, shots, duration: T };
}
