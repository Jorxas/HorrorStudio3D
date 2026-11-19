// « LE DERNIER BUS » — court métrage d'horreur vertical (9:16), ~6 min, moteur v4 (style des illustrations).
// Le découpage suit la chronologie de la voix (data/dernier_bus_timeline.json). Chaque acte est dans son fichier :
// bus (A), station-service (B), forêt (C), abîme + porte (D, E).
import { buildBus } from './sets4.js';
import { buildStation } from './sets4b.js';
import { buildForest, buildShade4 } from './sets4c.js';
import { buildAbyss } from './sets4d.js';
import { buildPhone, buildLantern, buildFlashlight } from './props4.js';
import { CAST } from './cast4.js';
import { actA } from './act_a.js';
import { actB } from './act_b.js';
import { actC } from './act_c.js';
import { actDE } from './act_de.js';

export const format = 'portrait';
export async function setup(ctx) {
  const { THREE, V, buildCharacter4, anim, scene } = ctx;
  const TL = await (await fetch('../data/dernier_bus_timeline.json')).json();
  const line = Object.fromEntries(TL.lines.map((l) => [l.id, l]));
  const at = (id) => line[id].start, end = (id) => line[id].end;
  // ---- décors (chacun à son origine ; un seul visible à la fois sauf exceptions)
  const bus = buildBus(ctx, V(0, 0, 0));
  const st = buildStation(ctx, V(200, 0, 0));
  const fo = buildForest(ctx, V(400, 0, 0));
  const ab = buildAbyss(ctx, V(600, 0, 0));
  // route (pour les plans extérieurs du bus) : bitume mouillé, lignes, lampadaires, immeubles puis noir
  const road = buildRoad(ctx, V(0, 0, -600));
  // ---- personnages + accessoires
  const noe = buildCharacter4({ ...CAST.noe, top: { type: 'jacketOpen', color: 0x8a8890, shirt: 0x1a1a1e } }, 1); noe.baseScale = 1.0; scene.add(noe.root);
  const lina = buildCharacter4(CAST.lina, 2); lina.baseScale = 0.95; scene.add(lina.root);
  const linaHurt = buildCharacter4({ ...CAST.lina, dirt: true, pants: { ...CAST.lina.pants, torn: true } }, 2); linaHurt.baseScale = 0.95; scene.add(linaHurt.root);
  const shades = [0, 1, 2, 3, 4, 5, 6, 7].map((i) => { const s = buildShade4(buildCharacter4, i); s.baseScale = 1.08 + (i % 3) * 0.06; scene.add(s.root); return s; });
  const phone = buildPhone(); noe.handR.add(phone.g); phone.g.position.set(0.0, -0.17, 0.09); phone.g.rotation.set(-1.25, 0, 0);
  const lantern = buildLantern(); scene.add(lantern.g);
  const torch = buildFlashlight(); lina.handR.add(torch.g); torch.g.position.set(0, -0.2, 0.06); torch.g.rotation.set(Math.PI / 2, 0, 0);
  const actors = [noe, lina, linaHurt, ...shades];
  const shoeProp = noe.lgR.userData.shoe.clone(); scene.add(shoeProp); shoeProp.visible = false;
  // ---- outils
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x)), lerp = (a, b, k) => a + (b - a) * k;
  const ease = (x) => { x = clamp(x); return x * x * (3 - 2 * x); }, easeOut = (x) => 1 - Math.pow(1 - clamp(x), 3), easeIn = (x) => Math.pow(clamp(x), 3);
  const lerpV = (a, b, k) => a.clone().lerp(b, k);
  const ground0 = () => 0;
  const E = { THREE, V, ctx, anim, TL, at, end, line, bus, st, fo, ab, road, noe, lina, linaHurt, shades, phone, lantern, torch, shoeProp, clamp, lerp, ease, easeOut, easeIn, lerpV, ground0 };
  // téléphone tenu devant la poitrine, écran tourné vers les yeux ; le bras se plie tout seul (cinématique inverse)
  const PHQ = new THREE.Quaternion().setFromEuler(new THREE.Euler(-1.25, 0, 0)), PHP = V(0.0, -0.17, 0.09);
  E.holdPhone = (ch, t, vib = 0, o = {}) => {
    ch.neck.rotation.x += o.neck ?? 0.32; ch.shL.rotation.set(-0.15, 0, -0.06); ch.elL.rotation.set(-0.45, 0, 0); ch.setHands('relaxed', 'grip'); ch._lockR = true; phone.g.visible = true;
    ch.root.updateMatrixWorld(true); const s = ch.root.scale.x || 1;
    const P = ch.torso.localToWorld(V(-1.0 / 16 + (o.dx ?? 0), (o.y ?? 6.2) / 16, (o.fwd ?? 7.4) / 16));
    const eyes = ch.head.localToWorld(V(0, 0.4 / 16, 4 / 16));
    const n = eyes.clone().sub(P).normalize(); let u = V(0, 1, 0); u.sub(n.clone().multiplyScalar(u.dot(n))).normalize();
    const Zg = n, Yg = u.clone().negate(), Xg = new THREE.Vector3().crossVectors(Yg, Zg);
    const Qg = new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(Xg, Yg, Zg));
    if (vib) Qg.multiply(new THREE.Quaternion().setFromAxisAngle(V(0, 0, 1), Math.sin(t * 60) * 0.04 * vib));
    const Qh = Qg.clone().multiply(PHQ.clone().invert()); const Hw = P.clone().sub(PHP.clone().multiplyScalar(s).applyQuaternion(Qh));
    for (let i = 0; i < 2; i++) { anim.reach(ch, 'R', Hw, V(-0.5, -1, -0.25)); ch.handR.parent.updateMatrixWorld(true); const qp = ch.handR.parent.getWorldQuaternion(new THREE.Quaternion()); ch.handR.quaternion.copy(qp.invert().multiply(Qh)); }
    ch.root.updateMatrixWorld(true);
  };
  // looks par décor (réglages communs ; chaque plan peut les ajuster ensuite)
  E.lookBus = (S, t, o = {}) => {
    const red = o.red ?? 1; S.sets = o.sets ?? ['bus'];
    S.key = { dir: o.keyDir ?? [-0.1, 0.45, 1.0], color: red > 0.5 ? 0xffb08c : 0xfff0dc, i: o.keyI ?? 1.5 };
    S.hemi = { sky: new THREE.Color(0x4a4a58).lerp(new THREE.Color(0x8a1c12), red).getHex(), ground: new THREE.Color(0x2a2018).lerp(new THREE.Color(0x0a0202), red).getHex(), i: 0.55 };
    S.fill = { dir: [1, 0.3, -0.3], color: 0x5070ff, i: 0.18 };
    S.lights = bus.tubeLights(o.tubes ?? red, t, red > 0.5 ? 2.2 : 1.6, 6);
    S.rim = { color: 0xff2414, i: 0.32 * red, pow: 5 };
    S.edge = red > 0.4 ? { color: 0xff3a26, i: 0.28 * (red - 0.4) / 0.6, rad: 1.4, thr: 0.12, maxD: 7, wrap: 0.6 } : null;
    S.fog = { color: new THREE.Color(0x10141e).lerp(new THREE.Color(0x7a1008), red).getHex(), d: lerp(0.03, 0.05, red) }; S.bg = 0x050204;
    S.dust = { i: 1.4 * red + 0.3, col: red > 0.5 ? 0xff4a30 : 0xfff0d8, size: 0.9, box: V(3, 2.5, 7) };
    S.spark = red > 0.4 ? { i: 1.2 * red, col: 0xff7a60, den: 0.04, size: 0.02 } : null;
    S.bloom = 0.5; S.bloomThreshold = 0.9; S.bloomRadius = 0.55; S.contrast = 0.3; S.vignette = 0.65; S.sat = 1.15; S.dofScale = 0.55;
    S.shadowC = bus.w(0, 0, -6); S.shadowS = 8; S.reflect = { y: bus.liquid.position.y + bus.group.position.y };
    bus.glass.uniforms.uPass.value = o.pass ?? 0; bus.glass.uniforms.uDrive.value = -t * 16;
    bus.glass.uniforms.uOut.value.set(red > 0.5 ? 0x1a0204 : 0x0c1222); bus.glass.uniforms.uOut2.value.set(red > 0.5 ? 0x6a0a0c : 0x2a3a5a);
  };
  // supérette : éclairage « normal » (néons blancs, produits colorés, nuit bleue dehors) ; o.horror (0..1) fait virer au rouge
  E.lookStation = (S, t, o = {}) => {
    const out = o.out ?? false, hz = o.horror ?? 0; S.sets = o.sets ?? ['st']; st.setPanels(hz * 0.8, t, o.flick ?? 0.1);
    S.lights = [...st.panelLights(hz * 0.8, out ? 1.6 : 1.25, 7).slice(0, out ? 2 : 9), ...st.car.lights(o.car ?? 1)]; if (out) S.lights.push(...st.lampLights(4));
    S.key = { dir: o.keyDir ?? [-0.3, 0.8, 0.6], color: 0xfff4ea, i: out ? 0.3 : 0.6 }; S.hemi = { sky: new THREE.Color(0x8a96b0).lerp(new THREE.Color(0x6a2a28), hz).getHex(), ground: 0x14161c, i: 0.5 }; S.fill = { dir: [0.3, 0.3, 1], color: new THREE.Color(0x4a70c0).lerp(new THREE.Color(0xff2a1a), hz).getHex(), i: 0.35 };
    S.rim = { color: 0xff2414, i: 0.15 + 0.2 * hz, pow: 5 }; S.edge = hz > 0.3 ? { color: 0xff3a26, i: 0.5 * (hz - 0.3) / 0.7, rad: 1.6, thr: 0.1, maxD: 12, wrap: 1.2 } : null;
    S.fog = { color: new THREE.Color(0x0c1220).lerp(new THREE.Color(0x3a0606), hz).getHex(), d: out ? 0.022 : 0.012 }; S.bg = 0x05070c;
    S.rain = { i: 1.4, col: 0xb8c8ff, size: 7, speed: 1, clip: new THREE.Vector4(-1e9, st.origin.z + 3.7, 1e9, 1e9) }; S.spark = out ? { i: 1.5, col: 0xd8e4ff, den: 0.04, size: 0.02 } : null;
    S.reflect = { y: 0.02 }; S.dofScale = 0.35; S.bloom = 0.5; S.bloomThreshold = 0.92; S.bloomRadius = 0.5; S.contrast = 0.26; S.vignette = 0.55; S.sat = 1.2;
    S.shadowC = st.w(0, 0, -1); S.shadowS = 9; st.neonM.color.setRGB(0.3, 3.2, 4.0);
  };
  E.lookForest = (S, t, o = {}) => {
    S.sets = ['fo']; S.key = { dir: o.keyDir ?? [-0.35, 0.75, -0.55], color: 0x9ab8ff, i: o.keyI ?? 1.5 }; S.hemi = { sky: 0x4a5a9a, ground: 0x1a1a2a, i: 0.6 }; S.fill = { dir: [0.2, 0.4, 1], color: 0x6a80d0, i: 0.5 };
    S.lights = [{ pos: fo.at(-46, 1.5, 0), color: 0xff2010, i: (o.redGlow ?? 1) * 4 * (0.8 + 0.2 * Math.sin(t * 1.3)), dist: 14, decay: 1.3 }];
    S.fog = { color: 0x141a34, d: 0.025 }; S.bg = 0x0a0c1a; S.moonDir = o.moonDir ?? [0.35, 0.6, -1];
    S.snow = { i: o.snowI ?? 1.4, col: 0xe8f0ff, size: 1, speed: 1 }; S.spark = { i: 1.5, col: 0xe8f0ff, den: 0.04, size: 0.02 }; S.rim = { color: 0xff3020, i: 0.2, pow: 5 };
    S.edge = null; S.dofScale = 0.35; S.shadowS = 12; S.contrast = 0.25; S.sat = 1.15; S.bloom = 0.5; S.bloomThreshold = 0.9;
    S.mist = { list: [0, 1, 2, 3, 4].map((i) => ({ pos: fo.at(-38 - i * 5, (i - 2) * 3, 1.0), w: 26, h: 5, yaw: 0, k: 1 })), col: 0xff1a10, i: (o.redGlow ?? 1) * 0.9 * (0.8 + 0.2 * Math.sin(t * 1.3)) };
  };
  E.lookAbyss = (S, t, o = {}) => {
    S.sets = ['ab']; S.key = { dir: o.keyDir ?? [0.3, 0.7, 0.6], color: 0xffa080, i: 0.8 }; S.hemi = { sky: 0x2a0606, ground: 0x5a1406, i: 0.4 }; S.fill = { dir: [0, -1, 0.35], color: 0xff5a18, i: 0.55 };
    S.lights = ab.lavaLights(o.lightAt ?? ab.w(0, 0, -6)).map((l) => ({ ...l, i: 1.8 })); S.fog = { color: 0x3a0604, d: 0.012 }; S.bg = 0x120302;
    S.embers = { i: 2.2, col: 0xff8a30, size: 1, speed: 1 }; S.spark = { i: 1.5, col: 0xff6a30, den: 0.04, size: 0.02 }; S.rim = { color: 0xff5020, i: 0.25, pow: 5 };
    S.edge = null; S.dofScale = 0.18; S.shadowS = 12; S.contrast = 0.3; S.bloom = 0.45; S.bloomThreshold = 0.95; S.sat = 1.1;
  };
  E.lookCave = (S, t, o = {}) => {
    S.sets = ['ab']; S.key = { dir: o.keyDir ?? [0.2, 0.6, -0.8], color: 0xa8e0ff, i: 0.55 }; S.hemi = { sky: 0x0a2a3a, ground: 0x020808, i: 0.5 }; S.fill = { dir: [0, 0.3, 1], color: 0x40c0ff, i: 0.45 };
    S.lights = ab.caveLights(4, o.near ?? null); S.fog = { color: 0x041a22, d: 0.035 }; S.bg = 0x02080c; S.reflect = { y: ab.origin.y + ab.lake.y };
    S.dust = { i: 1.2, col: 0x8ae8ff, size: 0.8, box: V(6, 4, 6) }; S.spark = { i: 1.5, col: 0x9af0ff, den: 0.04, size: 0.02 }; S.rim = { color: 0x40d8ff, i: 0.2, pow: 5 };
    S.edge = null; S.dofScale = 0.4; S.contrast = 0.26; S.bloom = 0.55; S.bloomThreshold = 0.88; S.sat = 1.15;
    S.mist = { list: [0, 1, 2, 3].map((i) => ({ pos: ab.w((i - 1.5) * 5, ab.lake.y + 0.6, 12 + i * 4), w: 9, h: 2.5, yaw: 0, k: 1 })), col: 0x9ad8e8, i: 0.35 };
  };
  E.lookUnder = (S, t, o = {}) => {
    S.sets = ['ab']; S.underwater = true; S.key = { dir: [0.1, 1, 0.1], color: 0x9af0ff, i: 0.9 }; S.hemi = { sky: 0x2a8aa0, ground: 0x02161a, i: 0.7 }; S.fill = { dir: [0, -1, 0.3], color: 0x0a4a5a, i: 0.3 };
    S.lights = ab.caveLights(3, o.near ?? null); S.fog = { color: 0x06343e, d: 0.16 }; S.bg = 0x041e24; S.reflect = null;
    S.embers = { i: 2.2, col: 0xc8f8ff, size: 0.9, speed: 0.8 }; S.rim = { color: 0x60e0ff, i: 0.3, pow: 4 }; S.edge = null;
    S.mist = { list: [0, 1, 2, 3, 4].map((i) => ({ pos: (o.near ?? ab.w(0, -2, 18)).clone().add(V((i - 2) * 1.6, 2.5, -1.5 - i * 0.7)), w: 1.2, h: 9, yaw: 0.3 * i, k: 1 })), col: 0x60e8ff, i: 0.5 };
    S.dofScale = 0.5; S.bloom = 0.7; S.bloomThreshold = 0.8; S.contrast = 0.2; S.sat = 1.1; S.vignette = 0.75; S.ca = 0.004;
  };
  E.lookGate = (S, t, o = {}) => {
    S.sets = ['ab']; S.key = { dir: o.keyDir ?? [0.3, 0.5, 1], color: 0xffb0a0, i: 0.6 }; S.hemi = { sky: 0x3a0606, ground: 0x1a0303, i: 0.5 }; S.fill = { dir: [0, -1, 0.2], color: 0xff2010, i: 0.35 };
    S.lights = [{ pos: ab.w(0, 33, -64), color: 0xff2010, i: 6, dist: 20 }]; S.fog = { color: 0x3a0404, d: 0.03 }; S.bg = 0x0e0101; S.bloom = 0.5; S.bloomThreshold = 0.92; S.contrast = 0.3;
    S.embers = { i: 1.5, col: 0xff4a20, size: 0.8, speed: 0.6 }; S.spark = { i: 2, col: 0xff4a30, den: 0.04, size: 0.02 }; S.rim = { color: 0xff2414, i: 0.3, pow: 5 };
    S.edge = { color: 0xff3a26, i: 0.3, rad: 1.4, thr: 0.1, maxD: 25, wrap: 0.8 }; S.dofScale = 0.25; S.shadowC = ab.w(0, 30, -58); S.shadowS = 14;
  };
  E.lookRoad = (S, t, o = {}) => {
    S.sets = o.sets ?? ['road', 'bus']; S.key = { dir: [0.4, 0.7, 0.3], color: 0x8aa0ff, i: 0.4 }; S.hemi = { sky: 0x202838, ground: 0x050505, i: 0.45 }; S.fill = { dir: [-1, 0.3, -0.3], color: 0xff6030, i: 0.15 };
    S.rim = { color: 0xff2414, i: 0.15, pow: 5 }; S.edge = null; S.fog = { color: 0x0a0c14, d: 0.022 }; S.bg = 0x05060a;
    S.rain = { i: 1.6, col: 0xc8d0ff, size: 7, speed: 1 }; S.spark = { i: 1.5, col: 0xffc0a0, den: 0.04, size: 0.02 }; S.reflect = { y: road.origin.y + 0.02 };
    S.dofScale = 0.25; S.bloom = 0.6; S.bloomThreshold = 0.85; S.contrast = 0.28; S.vignette = 0.6; S.sat = 1.1;
  };
  // ---- plans
  const shots = [...actA(E), ...actB(E), ...actC(E), ...actDE(E)];
  shots.sort((a, b) => a.t0 - b.t0);
  for (let i = 0; i < shots.length - 1; i++) shots[i].t1 = shots[i + 1].t0;
  shots[shots.length - 1].t1 = TL.duration;
  return {
    shots, duration: TL.duration, sets: { bus, st, fo, ab, road }, E,
    post: (t) => { for (const a of actors) if (a.root.visible) { anim.relaxArms(a); if (a.faceUpdate) a.faceUpdate(t); } },
    reset: () => {
      for (const a of actors) { a.reset(); a.root.visible = false; a.root.position.set(0, -500, 0); }
      noe.setShoe('L', true); noe.setShoe('R', true); shoeProp.visible = false; phone.g.visible = false; phone.g.position.set(0.0, -0.17, 0.09); phone.g.rotation.set(-1.25, 0, 0); noe.handR.children.forEach(c => { c.visible = c === phone.g ? c.visible : true; }); noe.handL.visible = true; for (const a of actors) a.neck.visible = true; lantern.g.visible = false; torch.g.visible = false; lantern.g.position.set(0, -500, 0);
      bus.place(V(0, 0, 0), 0); bus.setDoor(0); bus.showPoles([]); bus.hands.forEach((h) => { h.g.visible = false; }); bus.liquid.position.y = 0.02; bus.liquid.visible = true; bus.setWindows(0xffe8d8, 0.3); bus.driver.visible = true;
      st.hpM.uniforms.uReveal.value = 0; st.backDoor.rotation.y = 0; fo.setHole(0, 0); fo.hands.forEach((h) => { h.g.visible = false; });
      ab.setRunes(0, 0, 0); ab.setDoorGlow(0);
    },
  };
}

// ------------------------------------------------------------------ route de nuit (plans extérieurs du bus)
import * as THREE0 from 'three';
import { Batch, mat4, grunge } from './kit4.js';
import { mulberry } from './textures.js';
function buildRoad(ctx, origin) {
  const THREE = THREE0; const V = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z); const r = mulberry(71);
  const group = new THREE.Group(); group.position.copy(origin); ctx.scene.add(group);
  const asph = grunge(0x16161a, { size: 64, noise: 0.35, dark: 0.3, seed: 72, specks: 0.08, speckCol: 0x34343a });
  const roadM = ctx.reflector.makeMaterial({ map: asph, color: 0xffffff, tpm: 0.3, reflect: 0.7, rough: 0.003, ripple: 1.0, tint: 0xffe8e0, glitter: 0.5, glitterCol: 0xffb090 });
  const plane = new THREE.Mesh(new THREE.PlaneGeometry(200, 1400), roadM); plane.rotation.x = -Math.PI / 2; plane.position.set(0, 0.02, -500); group.add(plane);
  const M = { line: mat4(grunge(0xe8e4d0, { size: 8, noise: 0.3, seed: 73 }), { rim: 0.2 }), pole: mat4(grunge(0x2a2a30, { size: 16, noise: 0.2, rust: 0.1, seed: 74 }), { rim: 0.7, wet: 1.2 }),
    bld: mat4(grunge(0x1a1a22, { size: 32, noise: 0.25, dark: 0.3, seed: 75 }), { rim: 0.5, wet: 0.8 }), shelter: mat4(grunge(0x3a3a44, { size: 16, noise: 0.2, seed: 76 }), { rim: 0.7, wet: 1.4 }),
    bark: mat4(grunge(0x1a120e, { size: 16, noise: 0.25, seed: 77 }), { rim: 0.6 }), needle: mat4(grunge(0x0c1610, { size: 16, noise: 0.3, seed: 78 }), { rim: 0.7 }) };
  const b = new Batch();
  for (let z = 40; z > -1100; z -= 6) b.add({ x: 0, y: 0.03, z, w: 0.14, h: 0.01, d: 3, mat: 'line' });
  for (const sx of [-1, 1]) b.add({ x: sx * 4.2, y: 0.03, z: -500, w: 0.12, h: 0.01, d: 1300, mat: 'line' });
  const lamps = []; for (let z = 30; z > -420; z -= 34) { const x = 6.2; b.add({ x, y: 3.6, z, w: 0.18, h: 7.2, d: 0.18, mat: 'pole' }); b.add({ x: x - 0.9, y: 7.15, z, w: 1.8, h: 0.16, d: 0.3, mat: 'pole' }); lamps.push(V(x - 1.6, 7.0, z)); }
  // immeubles (début du trajet) puis forêt noire
  for (let z = 30; z > -380; z -= 9 + r() * 6) for (const sx of [-1, 1]) { const h = 6 + r() * 20, w = 7 + r() * 6; b.add({ x: sx * (14 + r() * 6 + w / 2), y: h / 2, z, w, h, d: 7 + r() * 4, mat: 'bld' }); }
  for (let z = -400; z > -1100; z -= 4) for (const sx of [-1, 1]) { const x = sx * (8 + r() * 14), h = 7 + r() * 8; b.add({ x, y: h / 2, z, w: 0.4, h, d: 0.4, mat: 'bark' }); for (let k = 0; k < 5; k++) b.add({ x, y: h * 0.35 + k * h * 0.13, z, w: (1 - k / 5) * h * 0.35 + 0.4, h: h * 0.09, d: (1 - k / 5) * h * 0.35 + 0.4, mat: 'needle', ry: k * 0.5 }); }
  // abribus
  b.add({ x: 5.4, y: 2.4, z: 0, w: 1.8, h: 0.1, d: 4, mat: 'shelter' }); for (const dx of [4.55, 6.25]) for (const dz of [-1.95, 1.95]) b.add({ x: dx, y: 1.2, z: dz, w: 0.08, h: 2.4, d: 0.08, mat: 'pole' }); b.add({ x: 6.25, y: 2.2, z: 0, w: 0.08, h: 0.12, d: 4, mat: 'pole' }); b.add({ x: 5.9, y: 0.45, z: 0, w: 0.5, h: 0.08, d: 2.6, mat: 'pole' }); b.add({ x: 6.25, y: 1.6, z: 1.0, w: 0.06, h: 1.4, d: 0.9, mat: 'bld' });
  b.build(M, group, { noCast: ['bld', 'needle', 'bark', 'line'] });
  // fenêtres allumées des immeubles
  const winM = new THREE.MeshBasicMaterial({ color: new THREE.Color(2.4, 1.6, 0.8) });
  for (let i = 0; i < 260; i++) { const z = 30 - r() * 400, sx = r() < 0.5 ? -1 : 1; const w = new THREE.Mesh(new THREE.PlaneGeometry(0.9, 1.2), winM); w.position.set(sx * (13.9 + r() * 0.2), 2 + r() * 18, z); w.rotation.y = -sx * Math.PI / 2; group.add(w); }
  const paneM = new THREE.MeshPhongMaterial({ color: 0x9ab0c8, transparent: true, opacity: 0.12, shininess: 120, specular: 0x888888, depthWrite: false, side: THREE.DoubleSide });
  for (const [x, z, w, ry] of [[6.25, 0, 3.9, Math.PI / 2], [5.4, -1.95, 1.7, 0], [5.4, 1.95, 1.7, 0]]) { const p = new THREE.Mesh(new THREE.PlaneGeometry(w, 2.0), paneM); p.position.set(x, 1.3, z); p.rotation.y = ry; group.add(p); }
  const shelterGlow = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.05, 2.8), new THREE.MeshBasicMaterial({ color: new THREE.Color(4, 4, 4.4) })); shelterGlow.position.set(5.4, 2.33, 0); group.add(shelterGlow);
  return { group, origin, lamps, w(x, y, z) { return V(x, y, z).add(origin); }, lampLights(near, n = 4, i = 6) { return lamps.map((p) => p.clone().add(origin)).sort((a, b) => a.distanceToSquared(near) - b.distanceToSquared(near)).slice(0, n).map((p) => ({ pos: p, color: 0xffa860, i, dist: 22, decay: 1.2 })); } };
}
