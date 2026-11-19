// Film runtime v2: town world, crowds, heroes, creature, time of day, deterministic renderAt(t).
import * as THREE from 'three';
import { buildTownWorld, LAYOUT, B } from './town.js';
import { buildHumanoid, buildProp, buildShadowThing, PX } from './rig.js';
import { buildCrowd } from './crowd.js';
import { buildSky2, buildDecal, buildThread, TOD } from './fx2.js';
import { buildShafts, buildMotes, buildPost } from './fx.js';
import { buildInteriors } from './interiors.js';
import { mulberry } from './textures.js';

const V = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
const params = new URLSearchParams(location.search);
const W = +(params.get('w') || 1080), H = +(params.get('h') || 1920);
window.MSAA = params.has('msaa') ? +params.get('msaa') : 4;
const FILM = params.get('film') || 'film_town';

const canvas = document.createElement('canvas'); document.body.appendChild(canvas);
const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, preserveDrawingBuffer: true });
renderer.setPixelRatio(1); renderer.setSize(W, H, false);
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap; renderer.toneMapping = THREE.NoToneMapping;

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(50, W / H, 0.06, 600);
scene.fog = new THREE.FogExp2(0xd2e4f2, 0.005);
const hemi = new THREE.HemisphereLight(0xcfe8ff, 0x5d7a3c, 1.4); scene.add(hemi);
const sun = new THREE.DirectionalLight(0xfff0d0, 3.2); sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048); sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.04; sun.shadow.camera.near = 1; sun.shadow.camera.far = 400; sun.shadow.radius = 2;
scene.add(sun, sun.target);
const fill = new THREE.DirectionalLight(0xe6eeff, 0.4); scene.add(fill, fill.target);
const lampLights = []; for (let i = 0; i < 6; i++) { const l = new THREE.PointLight(0xffc880, 0, 16, 1.4); l.visible = false; scene.add(l); lampLights.push(l); }
const spot = new THREE.PointLight(0xffd8a0, 0, 20, 1.3); spot.visible = false; scene.add(spot);

// ---------------------------------------------------------------- world & actors
const film = await import(`./${FILM}.js`);
const town = buildTownWorld(scene, film.prepareWorld);
const interiors = buildInteriors(scene, town.T);
for (const k of ['bus', 'hall']) interiors[k].group.traverse(o => { if (o.isPointLight) { o.userData.interior = k; o.visible = false; } });
const sky = buildSky2(scene);
const crowd = buildCrowd(scene, 420, 11, film.crowdOpts || {});
const creature = buildShadowThing(); scene.add(creature.root); creature.root.visible = false;
const decals = []; for (let i = 0; i < 8; i++) decals.push(buildDecal(scene, { shape: i % 2, seed: i * 1.7 }));
const thread = buildThread(scene, 44);
const motes = buildMotes(scene, 700, 5, { color: new THREE.Color(1.4, 1.3, 1.05), size: 22 });
const shaftList = []; const rr = mulberry(91);
for (let k = 0; k < 40; k++) shaftList.push({ x: -20 + rr() * 40, z: -120 + rr() * 300, ground: 0, len: 40, width: 1 + rr() * 3 });
let shafts = null; // created lazily per sun direction
const oneLamp = new THREE.Mesh(new THREE.BoxGeometry(0.52, 0.64, 0.52), new THREE.MeshBasicMaterial({ color: 0xffffff })); oneLamp.material.color.setRGB(3, 2.5, 1.6); oneLamp.visible = false; scene.add(oneLamp);

const ctx = { THREE, V, scene, camera, town, LAYOUT, B, crowd, creature, decals, thread, interiors, buildHumanoid, buildProp, PX, mulberry, sky };
const F = await film.setup(ctx);
// Re-timing (doublage, montage) : ?retime=fichier.json donne, pour chaque plan, ses nouvelles bornes T0/T1
// et la correspondance avec le temps d'origine du plan : lt = o + r * (T - T0), u = (o + ru * (T - T0)) / durée.
// Le film lui-même ne change pas.
let RETIME = null;
if (params.get('retime')) {
  const R = await (await fetch(params.get('retime'))).json();
  const byName = Object.fromEntries(F.shots.map(s => [s.name, s]));
  RETIME = R.shots.map(x => ({ ...x, shot: byName[x.name] }));
  if (RETIME.some(x => !x.shot)) throw new Error('retime: plan inconnu ' + RETIME.find(x => !x.shot).name);
  F.duration = R.duration ?? RETIME[RETIME.length - 1].T1;
}
let ENV = []; try { ENV = await (await fetch(F.envelope || './envelope.json')).json(); } catch (e) { }
ctx.envAt = (t) => ENV[Math.max(0, Math.min(ENV.length - 1, Math.round(t * 30)))] || 0;

function lerpTod(a, b, k) {
  const A = TOD[a], Bb = TOD[b || a]; if (!b || k <= 0) return { ...A }; if (k >= 1) return { ...Bb };
  const o = {};
  for (const key in A) {
    const x = A[key], y = Bb[key] ?? x;
    if (Array.isArray(x)) o[key] = x.map((v, i) => v + (y[i] - v) * k);
    else if (typeof x === 'number' && (key === 'sunCol' || key.startsWith('hemi') || key === 'fog' || key === 'top' || key === 'horizon' || key === 'glow') && key !== 'hemiI') o[key] = new THREE.Color(x).lerp(new THREE.Color(y), k).getHex();
    else if (typeof x === 'number') o[key] = x + (y - x) * k;
  }
  return o;
}

function D() {
  return {
    cam: { pos: V(0, 2, 10), look: V(0, 1, 0), fov: 55, roll: 0 }, shake: 0.004, focus: 8, dofScale: 0.8, maxBlur: 10,
    tod: 'noon', tod2: null, todK: 0, exposure: null, bloom: 0.45, bloomRadius: 0.55, rays: 0, shafts: 0, distort: 0.12,
    shadowC: V(0, 0, 0), shadowS: 30, sunDir: null, lamps: 'auto', lampOne: null, interior: null, motes: null, vignette: 0.35, tint: null, fade: 1,
  };
}

function resetAll() {
  for (const h of Object.values(F.heroes || {})) { h.reset(); h.root.visible = false; h.setExpr('neutral'); }
  for (const p of Object.values(F.props || {})) p.visible = false;
  crowd.clear(); creature.reset(); creature.root.visible = false;
  for (const d of decals) d.mesh.visible = false; thread.set(() => [0, 0, 0], false);
  oneLamp.visible = false;
}

const post = buildPost(renderer, W, H);
function apply(S, t) {
  const P = lerpTod(S.tod, S.tod2, S.todK); if (S.todOver) Object.assign(P, S.todOver);
  const sd = (S.sunDir ? V(...S.sunDir) : V(...P.sun)).normalize();
  camera.fov = S.cam.fov; camera.updateProjectionMatrix();
  const sh = S.shake; const off = V(Math.sin(t * 1.7) * 0.6 + Math.sin(t * 3.1 + 1.3) * 0.4, Math.sin(t * 1.3 + 0.5) * 0.6 + Math.sin(t * 2.7 + 2.1) * 0.4, Math.sin(t * 1.1 + 2.3) * 0.5).multiplyScalar(sh);
  camera.position.copy(S.cam.pos).add(off); camera.up.set(Math.sin(S.cam.roll), Math.cos(S.cam.roll), 0); camera.lookAt(S.cam.look.clone().addScaledVector(off, 0.4)); camera.updateMatrixWorld();
  // sun / moon
  sun.position.copy(S.shadowC).addScaledVector(sd, 160); sun.target.position.copy(S.shadowC); sun.target.updateMatrixWorld();
  sun.color.setHex(P.sunCol); sun.intensity = P.sunI;
  const sc = sun.shadow.camera; sc.left = -S.shadowS; sc.right = S.shadowS; sc.top = S.shadowS; sc.bottom = -S.shadowS; sc.updateProjectionMatrix();
  hemi.color.setHex(P.hemiSky); hemi.groundColor.setHex(P.hemiGround); hemi.intensity = P.hemiI;
  fill.position.copy(camera.position).add(V(0, 1.5, 0)); fill.target.position.copy(S.cam.look); fill.target.updateMatrixWorld(); fill.intensity = P.fillI;
  scene.fog.color.setHex(P.fog); scene.fog.density = P.fogD;
  const su = sky.material.uniforms; su.sunDir.value.copy(sd); su.top.value.setHex(P.top); su.horizon.value.setHex(P.horizon); su.glow.value.setHex(P.glow); su.sunCol.value.setHex(P.sunCol); su.haze.value = P.haze; su.stars.value = P.stars; su.sunSize.value = P.sunSize; su.sunPower.value = P.night > 0.5 ? 0.15 : (P.sunPow ?? 1);
  // night: windows, signs, lamps
  const night = P.night; const mats = town.WM.mats;
  const wl = S.winLevel ?? night; if (mats.windowLit) { mats.windowLit.map = wl > 0.15 ? town.T.windowLit : town.T.window; mats.windowLit.emissiveIntensity = wl * 1.3; }
  if (mats.shopWindowLit) { mats.shopWindowLit.map = night > 0.3 ? town.T.shopWindowLit : town.T.shopWindow; mats.shopWindowLit.emissiveIntensity = night * 1.1; }
  for (const m of town.M.signMeshes) m.material.emissiveIntensity = night * 0.5;
  const lampsOn = S.lamps === 'auto' ? night > 0.4 : S.lamps === 'on' || S.lamps === 'fn';
  const lvl = (p) => S.lamps === 'fn' ? S.lampFn(p) : (lampsOn ? 1 : 0);
  town.M.lampHeads.forEach((p, i) => { const m = town.M.lampMats[i]; if (m) m.emissiveIntensity = 2.4 * lvl(p); });
  const tgt = S.cam.look; const cands = lampsOn ? town.M.lampHeads.map(p => [p, p.distanceToSquared(tgt) * 0.6 + p.distanceToSquared(camera.position) * 0.4, lvl(p)]).filter(c => c[2] > 0.02).sort((a, b) => a[1] - b[1]) : [];
  lampLights.forEach((l, i) => { const c = cands[i]; l.visible = !!c && c[1] < 70 * 70; if (l.visible) { l.position.copy(c[0]).add(V(0, -0.3, 0)); l.intensity = 14 * c[2]; } });
  if (S.lamps === 'one' && S.lampOne) { oneLamp.visible = true; oneLamp.position.copy(S.lampOne); spot.visible = true; spot.position.copy(S.lampOne).add(V(0, -0.4, 0)); spot.intensity = 22; } else { spot.visible = false; }
  for (const k of ['bus', 'hall']) interiors[k].group.traverse(o => { if (o.isPointLight) o.visible = S.interior === k; });
  if (S.motes) { const m = S.motes; motes.set(m.c.clone().sub(m.s.clone().multiplyScalar(0.5)), m.s, t, H / 1280, m.i ?? 1); } else motes.set(V(), V(1, 1, 1), t, 1, 0);
  crowd.update();
  const fwd = V(); camera.getWorldDirection(fwd); let sunScreen = null;
  if (fwd.dot(sd) > 0.1 && night < 0.5) { const p = camera.position.clone().addScaledVector(sd, 300).project(camera); sunScreen = new THREE.Vector2(p.x * 0.5 + 0.5, p.y * 0.5 + 0.5); }
  return { peep: S.peep, grain: S.grain, focus: S.focus, dofScale: S.dofScale, maxBlur: S.maxBlur, exposure: S.exposure ?? P.exposure, bloom: S.bloom, bloomRadius: S.bloomRadius, bloomThreshold: 1.0, rays: S.rays, sunScreen, sat: P.sat, vignette: S.vignette, warm: P.warm, distort: S.distort, tint: S.tint, fade: S.fade, t };
}

window.renderAt = (t, fmt = 'jpeg') => {
  let shot, lt, u;
  if (RETIME) {
    const R = RETIME.find(x => t >= x.T0 && t < x.T1) || RETIME[RETIME.length - 1];
    // r : vitesse de l'action ; ru : vitesse du mouvement de caméra (u), pour étirer un plan sans ralenti
    shot = R.shot; const ln = t - R.T0; lt = R.o + R.r * ln; t = shot.t0 + lt;
    u = Math.min(1, Math.max(0, (R.o + (R.ru ?? R.r) * ln) / (shot.t1 - shot.t0)));
  } else {
    shot = F.shots.find(s => t >= s.t0 && t < s.t1) || F.shots[F.shots.length - 1]; lt = t - shot.t0;
    u = Math.min(1, Math.max(0, lt / (shot.t1 - shot.t0)));
  }
  const S = D(); resetAll();
  shot.fn(lt, u, t, S, shot);
  scene.updateMatrixWorld(true);
  const P = apply(S, t);
  post.render(scene, camera, P);
  return canvas.toDataURL(fmt === 'png' ? 'image/png' : 'image/jpeg', 0.94);
};
window.filmInfo = { duration: F.duration, shots: F.shots.map(s => [s.name, s.t0, s.t1]), retime: !!RETIME };
window.ready = true;
