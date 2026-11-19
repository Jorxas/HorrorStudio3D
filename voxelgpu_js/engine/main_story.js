// Runtime v4 « histoire » (style illustrations) : décors interchangeables, personnages v4, liseré lumineux,
// sols mouillés réfléchissants, pluie / neige / braises, brume colorée, post-traitement v3. renderAt(t) reste pur.
import * as THREE from 'three';
import { buildCharacter4 } from './chars4.js';
import * as anim from './anim.js';
import * as kit from './kit4.js';
import { boxesGeometry, boxesMesh } from './boxes.js';
import { buildParticles, buildReflector, buildMist, rainGlassMaterial } from './fx4.js';
import { buildPost3 } from './fx3.js';
import { handheld, spline, orbit } from './music.js';
import { mulberry } from './textures.js';

const V = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
const params = new URLSearchParams(location.search);
const FILM = params.get('film') || 'film_dernier_bus';
// polices embarquées (Inter) chargées avant de dessiner les écrans de téléphone : même rendu sur toutes les machines
await Promise.all([300, 400, 500, 600, 700, 800, 900].map((w) => document.fonts.load(`${w} 24px Inter`).catch(() => null)));
const film = await import(`./${FILM}.js`);
const landscape = film.format === 'landscape';
const W = +(params.get('w') || (landscape ? 1920 : 1080)), H = +(params.get('h') || (landscape ? 1080 : 1920));   // défaut moteur : 1080x1920
window.MSAA = params.has('msaa') ? +params.get('msaa') : 4;

const canvas = document.createElement('canvas'); document.body.appendChild(canvas);
const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, preserveDrawingBuffer: true });
renderer.setPixelRatio(1); renderer.setSize(W, H, false);
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap; renderer.toneMapping = THREE.NoToneMapping;
const scene = new THREE.Scene(); scene.background = new THREE.Color(0x050203);
const camera = new THREE.PerspectiveCamera(50, W / H, 0.04, 600), prevCam = new THREE.PerspectiveCamera(50, W / H, 0.04, 600);
scene.fog = new THREE.FogExp2(0x200406, 0.03);
const hemi = new THREE.HemisphereLight(0xff3a2a, 0x1a0606, 0.6); scene.add(hemi);
const key = new THREE.DirectionalLight(0xff4a3a, 1.5); key.castShadow = true; key.shadow.mapSize.set(2048, 2048); key.shadow.bias = -0.0005; key.shadow.normalBias = 0.03; key.shadow.camera.near = 0.5; key.shadow.camera.far = 200; key.shadow.radius = 3; scene.add(key, key.target);
const fill = new THREE.DirectionalLight(0x8ab4ff, 0.3); scene.add(fill, fill.target);
const pool = []; for (let i = 0; i < 4; i++) { const l = new THREE.PointLight(0xff3020, 0, 12, 1.6); scene.add(l); pool.push(l); }
const spots = []; for (let i = 0; i < 2; i++) { const s = new THREE.SpotLight(0xfff0d0, 0, 30, 0.42, 0.55, 1.4); scene.add(s, s.target); spots.push(s); }
const parts = { rain: buildParticles(scene, 'rain', 7000, 1), snow: buildParticles(scene, 'snow', 7000, 2), embers: buildParticles(scene, 'embers', 2500, 3), dust: buildParticles(scene, 'dust', 1500, 4) };
const mist = buildMist(scene, 12);
const reflector = buildReflector(renderer, W, H);
const post = buildPost3(renderer, W, H);

const ctx = { THREE, V, scene, camera, renderer, W, H, aspect: W / H, buildCharacter4, anim, kit, boxesGeometry, boxesMesh, reflector, rainGlassMaterial, handheld, spline, orbit, mulberry, spots };
const F = await film.setup(ctx);

const D = () => ({
  cam: { pos: V(0, 1.6, 4), look: V(0, 1.2, 0), fov: 50, roll: 0 }, focus: 4, dofScale: 1.2, maxBlur: 12, shake: 0,
  exposure: 1.0, bloom: 0.9, bloomRadius: 0.75, bloomThreshold: 0.75, sat: 1.12, contrast: 0.2, vignette: 0.55, vigCol: 0x050000, grain: 0.035, ca: 0.0022,
  shadowTint: 0xffd8d8, highTint: 0xfff2ea, lift: 0x060000, tint: 0xffffff, flash: 0, flashCol: 0xffffff, fade: 1, bars: 0, mblur: 0.3,
  hemi: { sky: 0xff3a2a, ground: 0x1a0606, i: 0.6 }, key: { dir: [0.4, 0.8, -0.5], color: 0xff4a3a, i: 1.5 }, fill: { dir: [-0.5, 0.4, 0.6], color: 0x8ab4ff, i: 0.3 },
  fog: { color: 0x200406, d: 0.03 }, bg: 0x050203, shadowC: V(0, 0, 0), shadowS: 10,
  lights: [], spots: [], rim: { color: 0xff1a10, i: 0.5, pow: 4.0 }, edge: null, spark: null,
  rain: null, snow: null, embers: null, dust: null, mist: null, reflect: null, sets: [], underwater: false,
});

function applyCam(cam, c, t, S) {
  const p = c.pos.clone(), l = c.look.clone();
  if (S && S.shake) { const h = handheld(t, S.shake, 5); p.x += h.x; p.y += h.y; p.z += h.z; l.x += h.x * 0.5; l.y += h.y * 0.5; }
  cam.position.copy(p); cam.up.set(0, 1, 0); cam.lookAt(l); if (c.roll) cam.rotateZ(c.roll);
  cam.fov = c.fov; cam.updateProjectionMatrix(); cam.updateMatrixWorld();
}
function apply(S, t) {
  for (const [name, set] of Object.entries(F.sets || {})) { const on = S.sets.includes(name); set.group.visible = on; if (on && set.update) set.update(t, S); }
  hemi.color.set(S.hemi.sky); hemi.groundColor.set(S.hemi.ground); hemi.intensity = S.hemi.i;
  const kd = V(...S.key.dir).normalize(); key.color.set(S.key.color); key.intensity = S.key.i; key.position.copy(S.shadowC).addScaledVector(kd, 60); key.target.position.copy(S.shadowC);
  const sc = key.shadow.camera; sc.left = -S.shadowS; sc.right = S.shadowS; sc.top = S.shadowS; sc.bottom = -S.shadowS; sc.updateProjectionMatrix();
  const fd = V(...S.fill.dir).normalize(); fill.color.set(S.fill.color); fill.intensity = S.fill.i; fill.position.copy(S.shadowC).addScaledVector(fd, 50); fill.target.position.copy(S.shadowC);
  scene.fog.color.set(S.fog.color); scene.fog.density = S.fog.d; scene.background.set(S.bg);
  const tgt = S.cam.look; const L = [...S.lights].sort((a, b) => a.pos.distanceToSquared(tgt) - b.pos.distanceToSquared(tgt));
  pool.forEach((l, i) => { const d = L[i]; if (!d) { l.intensity = 0; return; } l.position.copy(d.pos); l.color.set(d.color ?? 0xff3020); l.intensity = d.i ?? 6; l.distance = d.dist ?? 12; l.decay = d.decay ?? 1.6; });
  spots.forEach((s, i) => { const d = S.spots[i]; if (!d) { s.intensity = 0; return; } s.position.copy(d.pos); s.target.position.copy(d.target); s.target.updateMatrixWorld(); s.color.set(d.color ?? 0xfff0d0); s.intensity = d.i ?? 30; s.angle = d.angle ?? 0.42; s.penumbra = d.pen ?? 0.55; s.distance = d.dist ?? 30; });
  kit.RIM.color.value.set(S.rim.color); kit.RIM.strength.value = S.rim.i; kit.RIM.power.value = S.rim.pow;
  kit.RIM.spark.value = S.spark?.i ?? 0; kit.RIM.sparkCol.value.set(S.spark?.col ?? 0xff5a40); kit.RIM.sparkDen.value = S.spark?.den ?? 0.06; kit.RIM.sparkSize.value = S.spark?.size ?? 0.025; kit.RIM.time.value = t;
  for (const k of ['rain', 'snow', 'embers', 'dust']) parts[k].set(camera, t, S[k] ? { ...S[k], scale: H / 1280 } : { i: 0 });
  mist.set(S.mist?.list || [], t, S.mist?.col ?? 0xff2010, S.mist?.i ?? 0);
}

// rend un plan au temps t sur le canvas WebGL
function renderShot(shot, t) {
  const dur = shot.t1 - shot.t0, lt = t - shot.t0, u = Math.min(1, Math.max(0, lt / dur));
  const S = D(); F.reset && F.reset();
  const dt = 1 / 30; const ltp = Math.max(0, lt - dt), tp = t - (lt - ltp);
  const cp = shot.cam(ltp, Math.min(1, Math.max(0, ltp / dur)), tp, D());
  const c = shot.cam(lt, u, t, S); S.cam = c;
  shot.fn(lt, u, t, S, shot);
  if (F.post) F.post(t, S);
  if (window.OVR) Object.assign(S, window.OVR);
  applyCam(prevCam, cp, tp, S); applyCam(camera, c, t, S);
  S._cam = camera.position.clone();
  apply(S, t);
  scene.updateMatrixWorld(true);
  if (S.preRender) S.preRender(renderer, scene, t);
  if (S.reflect) reflector.render(scene, camera, S.reflect.y, S.reflect.hide || [], t, scene.fog);
  const mv = prevCam.position.distanceTo(camera.position) / Math.max(1, S.focus) + (1 - prevCam.getWorldDirection(V()).dot(camera.getWorldDirection(V()))) * 40 + Math.abs(prevCam.fov - camera.fov) * 0.01;
  post.render(scene, camera, { ...S, t, mblur: mv > 0.004 ? S.mblur : 0 }, prevCam);
}
// fondu enchaîné : un plan qui a « dissolve: d » se mélange au plan précédent pendant ses d premières secondes
const mixCanvas = document.createElement('canvas'); mixCanvas.width = W; mixCanvas.height = H; const mix2d = mixCanvas.getContext('2d');
window.renderAt = (t, fmt = 'jpeg') => {
  const i = F.shots.findIndex(s => t >= s.t0 && t < s.t1); const shot = F.shots[i < 0 ? F.shots.length - 1 : i];
  const d = shot.dissolve || 0, prev = i > 0 ? F.shots[i - 1] : null;
  if (d > 0 && prev && t < shot.t0 + d) {
    const k0 = (t - shot.t0) / d, k = k0 * k0 * (3 - 2 * k0);
    renderShot(prev, t); mix2d.globalAlpha = 1; mix2d.drawImage(canvas, 0, 0);
    renderShot(shot, t); mix2d.globalAlpha = k; mix2d.drawImage(canvas, 0, 0); mix2d.globalAlpha = 1;
    return mixCanvas.toDataURL(fmt === 'png' ? 'image/png' : 'image/jpeg', 0.94);
  }
  renderShot(shot, t);
  return canvas.toDataURL(fmt === 'png' ? 'image/png' : 'image/jpeg', 0.94);
};
window.filmInfo = { duration: F.duration, shots: F.shots.map(s => [s.name, s.t0, s.t1]), W, H };
window.__dbg = { scene, renderer, F, camera, THREE };
window.ready = true;
