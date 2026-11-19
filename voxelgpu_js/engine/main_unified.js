// Runtime « unifié » : le moteur voxel A (Three.js, GPU) piloté par un contrat JSON écrit par Horror Studio (B).
// Copie isolée de main_story.js (le fichier d'origine de A n'est pas modifié). Différences voulues :
//   * le film n'est pas un module écrit à la main mais film_unified.js, qui lit le contrat (?contract=<url>) ;
//   * les valeurs par défaut de l'image sont neutres (pas de brouillard rouge imposé) : chaque plan règle sa lumière ;
//   * renderAt(t, 'raw') renvoie des pixels RGBA bruts (base64), sans passage par un JPEG ; sous-titres facultatifs dessinés ici ;
//   * window.gpuInfo() : le GPU réellement utilisé par WebGL (pour l'attestation) ;
//   * renderAt reste une fonction pure du temps.
import * as THREE from 'three';
import { buildCharacter4 } from './chars4.js';
import * as anim from './anim.js';
import * as kit from './kit4.js';
import { boxesGeometry, boxesMesh } from './boxes.js';
import { buildParticles, buildReflector, buildMist, rainGlassMaterial } from './fx4.js';
import { buildPost3 } from './fx3.js';
import { handheld, spline, orbit } from './music.js';
import { mulberry } from './textures.js';
import { drawCaptions } from './captions_unified.js';
import { drawUI } from './hud_unified.js';

const V = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
const params = new URLSearchParams(location.search);
await Promise.all([300, 400, 500, 600, 700, 800, 900].map((w) => document.fonts.load(`${w} 24px Inter`).catch(() => null)));
await document.fonts.load('24px Monocraft').catch(() => null);
const contract = await (await fetch(params.get('contract'))).json();
const film = await import('./film_unified.js');
const landscape = contract.aspect === '16:9';
const W = +(params.get('w') || (landscape ? 1920 : 1080)), H = +(params.get('h') || (landscape ? 1080 : 1920));
window.MSAA = params.has('msaa') ? +params.get('msaa') : 4;

const canvas = document.createElement('canvas'); document.body.appendChild(canvas);
const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, preserveDrawingBuffer: true });
renderer.setPixelRatio(1); renderer.setSize(W, H, false);
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap; renderer.toneMapping = THREE.NoToneMapping;
const scene = new THREE.Scene(); scene.background = new THREE.Color(0x101418);
const camera = new THREE.PerspectiveCamera(50, W / H, 0.04, 600), prevCam = new THREE.PerspectiveCamera(50, W / H, 0.04, 600);
scene.fog = new THREE.FogExp2(0x9aa8b8, 0.01);
const hemi = new THREE.HemisphereLight(0xbfd0ff, 0x4a4036, 0.8); scene.add(hemi);
const key = new THREE.DirectionalLight(0xfff0d8, 1.8); key.castShadow = true; key.shadow.mapSize.set(2048, 2048); key.shadow.bias = -0.0005; key.shadow.normalBias = 0.03; key.shadow.camera.near = 0.5; key.shadow.camera.far = 200; key.shadow.radius = 3; scene.add(key, key.target);
const fill = new THREE.DirectionalLight(0x8ab4ff, 0.3); scene.add(fill, fill.target);
// réservoirs de lumières : 4 ponctuelles + 2 projecteurs ; un contrat peut en demander plus (`point_pool`, `spot_pool` : le théâtre, hstudio/voxelgpu/b_theatre.py). Absents = 4 et 2, comme avant.
const NPOINT = Math.max(4, Math.min(12, contract.point_pool | 0)), NSPOT = Math.max(2, Math.min(8, contract.spot_pool | 0));
const pool = []; for (let i = 0; i < NPOINT; i++) { const l = new THREE.PointLight(0xffc080, 0, 12, 1.6); scene.add(l); pool.push(l); }
const spots = []; for (let i = 0; i < NSPOT; i++) { const s = new THREE.SpotLight(0xfff0d0, 0, 30, 0.42, 0.55, 1.4); scene.add(s, s.target); spots.push(s); }
const parts = { rain: buildParticles(scene, 'rain', 7000, 1), snow: buildParticles(scene, 'snow', 7000, 2), embers: buildParticles(scene, 'embers', 2500, 3), dust: buildParticles(scene, 'dust', 1500, 4) };
const mist = buildMist(scene, 12);
const reflector = buildReflector(renderer, W, H);
const post = buildPost3(renderer, W, H);

const ctx = { THREE, V, scene, camera, renderer, W, H, aspect: W / H, buildCharacter4, anim, kit, boxesGeometry, boxesMesh, reflector, rainGlassMaterial, handheld, spline, orbit, mulberry, spots, contract };
const F = await film.setup(ctx);

// image par défaut NEUTRE : lumière du jour douce, sans teinte de genre. Les plans (film_unified.js) règlent le reste.
const D = () => ({
  cam: { pos: V(0, 1.6, 4), look: V(0, 1.2, 0), fov: 50, roll: 0 }, focus: 4, dofScale: 1.2, maxBlur: 12, shake: 0,
  exposure: 1.0, bloom: 0.5, bloomRadius: 0.6, bloomThreshold: 0.85, sat: 1.1, contrast: 0.15, vignette: 0.35, vigCol: 0x050505, grain: 0.025, ca: 0.0015,
  shadowTint: 0xe8ecff, highTint: 0xfff6ea, lift: 0x030303, tint: 0xffffff, flash: 0, flashCol: 0xffffff, fade: 1, bars: 0, mblur: 0.2,
  hemi: { sky: 0xbfd0ff, ground: 0x4a4036, i: 0.8 }, key: { dir: [0.4, 0.8, -0.5], color: 0xfff0d8, i: 1.8 }, fill: { dir: [-0.5, 0.4, 0.6], color: 0x8ab4ff, i: 0.3 },
  fog: { color: 0x9aa8b8, d: 0.01 }, bg: 0x101418, shadowC: V(0, 0, 0), shadowS: 10,
  lights: [], spots: [], rim: { color: 0xffffff, i: 0.15, pow: 4.0 }, edge: null, spark: null,
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
  pool.forEach((l, i) => { const d = L[i]; if (!d) { l.intensity = 0; return; } l.position.copy(d.pos); l.color.set(d.color ?? 0xffc080); l.intensity = d.i ?? 6; l.distance = d.dist ?? 12; l.decay = d.decay ?? 1.6; });
  spots.forEach((s, i) => { const d = S.spots[i]; if (!d) { s.intensity = 0; return; } s.position.copy(d.pos); s.target.position.copy(d.target); s.target.updateMatrixWorld(); s.color.set(d.color ?? 0xfff0d0); s.intensity = d.i ?? 30; s.angle = d.angle ?? 0.42; s.penumbra = d.pen ?? 0.55; s.distance = d.dist ?? 30; });
  kit.RIM.color.value.set(S.rim.color); kit.RIM.strength.value = S.rim.i; kit.RIM.power.value = S.rim.pow;
  kit.RIM.spark.value = S.spark?.i ?? 0; kit.RIM.sparkCol.value.set(S.spark?.col ?? 0xff5a40); kit.RIM.sparkDen.value = S.spark?.den ?? 0.06; kit.RIM.sparkSize.value = S.spark?.size ?? 0.025; kit.RIM.time.value = t;
  for (const k of ['rain', 'snow', 'embers', 'dust']) parts[k].set(camera, t, S[k] ? { ...S[k], scale: H / 1280 } : { i: 0 });
  mist.set(S.mist?.list || [], t, S.mist?.col ?? 0xff2010, S.mist?.i ?? 0);
}

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
// tout passe par un canvas 2D : fondus enchaînés, sous-titres, lecture des pixels (RGBA, origine en haut à gauche)
const mixCanvas = document.createElement('canvas'); mixCanvas.width = W; mixCanvas.height = H;
const mix2d = mixCanvas.getContext('2d', { willReadFrequently: true });
// contrat `mirror` : mise en page de PIXEL 3D. Le passage de PIXEL 3D (repère main gauche, x vers la droite de l'image) à VOXEL (three.js, main droite) est un demi-tour qui INVERSE gauche et droite de l'image ;
// l'image 3D est donc retournée ici, avant les sous-titres et le HUD (dessinés ensuite, jamais retournés). Sans la clé, rien ne change.
const MIRROR = !!contract.mirror;
const blit = () => { if (MIRROR) { mix2d.save(); mix2d.translate(W, 0); mix2d.scale(-1, 1); mix2d.drawImage(canvas, 0, 0); mix2d.restore(); } else mix2d.drawImage(canvas, 0, 0); };
function compose(t) {
  const i = F.shots.findIndex(s => t >= s.t0 && t < s.t1); const shot = F.shots[i < 0 ? F.shots.length - 1 : i];
  const d = shot.dissolve || 0, prev = i > 0 ? F.shots[i - 1] : null;
  mix2d.globalAlpha = 1;
  if (d > 0 && prev && t < shot.t0 + d) {
    const k0 = (t - shot.t0) / d, k = k0 * k0 * (3 - 2 * k0);
    renderShot(prev, t); blit();
    renderShot(shot, t); mix2d.globalAlpha = k; blit(); mix2d.globalAlpha = 1;
  } else { renderShot(shot, t); blit(); }
  if (contract.captions && contract.captions.length) drawCaptions(mix2d, contract, t, W, H);
  if (contract.hud || contract.cards || contract.captions) drawUI(mix2d, contract, t, W, H);
}
function b64(u8) { let s = ''; const n = 0x8000; for (let i = 0; i < u8.length; i += n) s += String.fromCharCode.apply(null, u8.subarray(i, i + n)); return btoa(s); }
window.renderAt = (t, fmt = 'raw') => {
  compose(t);
  if (fmt === 'raw') return b64(new Uint8Array(mix2d.getImageData(0, 0, W, H).data.buffer));
  return mixCanvas.toDataURL(fmt === 'png' ? 'image/png' : 'image/jpeg', 0.94);
};
// binary transport: render frames f0..f1-1 and POST each raw RGBA frame to the local server (no base64, no CDP payload).
// At most `inflight` POSTs are pending, so the next frame renders while the previous one travels; the server answers
// once ffmpeg has accepted the frame, which is the back-pressure. `list` is an explicit array of frame numbers.
window.streamFrames = async (list, fps, url, inflight = 3) => {
  const pend = [];
  for (let i = 0; i < list.length; i++) {
    compose(list[i] / fps);
    const px = new Uint8Array(mix2d.getImageData(0, 0, W, H).data.buffer);
    pend.push(fetch(url, { method: 'POST', headers: { 'X-Frame': String(i) }, body: new Blob([px]) }).then((r) => { if (!r.ok) throw new Error('frame ' + i + ' refused: ' + r.status); }));
    if (pend.length >= inflight) await pend.shift();
  }
  await Promise.all(pend);
  return list.length;
};
// per-stage cost of one frame (ms), for `render_unified.js --profile`. gl.finish() makes the GPU time visible, so this is a
// diagnostic and not the production path; it draws exactly the pixels renderAt draws.
window.profAt = (t) => {
  const gl = renderer.getContext(), P = {}; let a = performance.now();
  const lap = (k) => { const b = performance.now(); P[k] = b - a; a = b; };
  const i = F.shots.findIndex(s => t >= s.t0 && t < s.t1); const shot = F.shots[i < 0 ? F.shots.length - 1 : i];
  renderShot(shot, t); lap('js_submit'); gl.finish(); lap('gpu_wait');
  mix2d.globalAlpha = 1; mix2d.drawImage(canvas, 0, 0); lap('canvas_copy');
  if (contract.captions && contract.captions.length) drawCaptions(mix2d, contract, t, W, H);
  if (contract.hud || contract.cards || contract.captions) drawUI(mix2d, contract, t, W, H); lap('ui_2d');
  const px = new Uint8Array(mix2d.getImageData(0, 0, W, H).data.buffer); lap('get_image_data');
  b64(px); lap('base64');
  return P;
};
window.gpuInfo = () => {
  const gl = renderer.getContext(); const e = gl.getExtension('WEBGL_debug_renderer_info');
  return { renderer: e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER), vendor: e ? gl.getParameter(e.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR), version: gl.getParameter(gl.VERSION), maxTex: gl.getParameter(gl.MAX_TEXTURE_SIZE) };
};
window.filmInfo = { duration: F.duration, shots: F.shots.map(s => [s.name, s.t0, s.t1]), W, H, fps: contract.fps };
window.__dbg = { scene, renderer, F, camera, THREE };
window.ready = true;
