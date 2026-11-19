// Accessoires v4 : téléphone (écran dessiné : notification, conversation, pas de réseau, position), lanterne,
// lampe torche, caméra de surveillance, moniteur (image d'une 2e caméra), voiture, canettes / bouteilles / caisse,
// traces de mains sur une vitre (apparition progressive). Tout en voxels texturés + liseré.
import * as THREE from 'three';
import { boxesGeometry } from './boxes.js';
import { rimify, voxify } from './kit4.js';
import { mulberry } from './textures.js';
const V = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);

export const vmat = (o = {}) => voxify(rimify(o.phong ? new THREE.MeshPhongMaterial({ vertexColors: true, shininess: o.phong, specular: o.spec ?? 0x222222 }) : new THREE.MeshLambertMaterial({ vertexColors: true }), o.rim ?? 0.8, o.wet ?? 0.6), { var: o.var ?? 0.1, levels: 4, px: o.px ?? 1 / 16, seed: o.seed ?? 0 });
export function vox(boxes, o = {}) { const m = new THREE.Mesh(boxesGeometry(boxes), o.mat || vmat(o)); m.castShadow = o.cast ?? true; m.receiveShadow = true; return m; }
const glowMat = (r, g, b) => new THREE.MeshBasicMaterial({ color: new THREE.Color(r, g, b) });

// ------------------------------------------------------------------ téléphone
const PHONE_TXT = {
  name: 'Lina',
  msg1: 'Noé. Je suis dans la forêt, derrière la station-service. Quelqu’un me suit.',
  msg2: 'Ne regarde pas les vitres.',
};
function wrap(g, text, maxW) { const words = text.split(' '); const lines = []; let cur = ''; for (const w of words) { const t = cur ? cur + ' ' + w : w; if (g.measureText(t).width > maxW && cur) { lines.push(cur); cur = w; } else cur = t; } if (cur) lines.push(cur); return lines; }
function paintPhone(mode) {
  const W = 360, H = 720; const c = document.createElement('canvas'); c.width = W; c.height = H; const g = c.getContext('2d');
  const bg = g.createLinearGradient(0, 0, 0, H); bg.addColorStop(0, '#141826'); bg.addColorStop(1, '#07080d'); g.fillStyle = bg; g.fillRect(0, 0, W, H);
  if (mode === 'off') { g.fillStyle = '#020203'; g.fillRect(0, 0, W, H); return c; }
  // barre d'état
  g.fillStyle = '#e8ecf4'; g.font = '600 22px Inter, sans-serif'; g.textBaseline = 'top'; g.fillText('00:17', 26, 18);
  const noSig = mode === 'call' || mode === 'map' || mode === 'chat2';
  for (let i = 0; i < 4; i++) { g.fillStyle = noSig ? (i === 0 ? '#e8ecf4' : '#3a3e4a') : '#e8ecf4'; g.fillRect(W - 110 + i * 9, 34 - i * 5, 6, 6 + i * 5); }
  g.strokeStyle = '#e8ecf4'; g.lineWidth = 2; g.strokeRect(W - 62, 20, 34, 17); g.fillStyle = '#e8ecf4'; g.fillRect(W - 59, 23, 13, 11); g.fillRect(W - 27, 25, 3, 7);
  const bubble = (y, text, mine = false, size = 27) => {
    g.font = `500 ${size}px Inter, sans-serif`; const lines = wrap(g, text, W - 120); const lh = size * 1.28; const bw = Math.min(W - 70, Math.max(...lines.map((l) => g.measureText(l).width)) + 40), bh = lines.length * lh + 26;
    const x = mine ? W - 24 - bw : 24; g.fillStyle = mine ? '#2a6af0' : '#2a2e3a'; g.beginPath(); g.roundRect(x, y, bw, bh, 22); g.fill();
    g.fillStyle = '#f2f4f8'; lines.forEach((l, i) => g.fillText(l, x + 20, y + 14 + i * lh)); return y + bh + 16;
  };
  const header = () => { g.fillStyle = '#10131c'; g.fillRect(0, 60, W, 92); g.fillStyle = '#c03a52'; g.beginPath(); g.arc(62, 106, 30, 0, 7); g.fill(); g.fillStyle = '#fff'; g.font = '700 30px Inter, sans-serif'; g.fillText('L', 52, 90); g.font = '700 30px Inter, sans-serif'; g.fillText(PHONE_TXT.name, 108, 80); g.font = '400 18px Inter, sans-serif'; g.fillStyle = '#8a90a0'; g.fillText(noSig ? 'hors ligne' : 'en ligne il y a 2 min', 108, 116); };
  if (mode === 'notif') {
    g.fillStyle = '#e8ecf4'; g.font = '300 96px Inter, sans-serif'; g.textAlign = 'center'; g.fillText('00:17', W / 2, 110); g.font = '500 22px Inter, sans-serif'; g.fillText('samedi 1 novembre', W / 2, 220); g.textAlign = 'left';
    g.fillStyle = 'rgba(60,66,84,0.92)'; g.beginPath(); g.roundRect(18, 300, W - 36, 210, 26); g.fill();
    g.fillStyle = '#c03a52'; g.beginPath(); g.roundRect(36, 318, 40, 40, 10); g.fill(); g.fillStyle = '#fff'; g.font = '700 24px Inter, sans-serif'; g.fillText('L', 48, 326);
    g.font = '700 26px Inter, sans-serif'; g.fillText(PHONE_TXT.name, 90, 322); g.font = '400 18px Inter, sans-serif'; g.fillStyle = '#b8bcc8'; g.fillText('maintenant', W - 130, 326);
    g.fillStyle = '#f2f4f8'; g.font = '500 25px Inter, sans-serif'; wrap(g, PHONE_TXT.msg1, W - 80).forEach((l, i) => g.fillText(l, 38, 376 + i * 32));
  } else if (mode === 'chat') { header(); bubble(200, PHONE_TXT.msg1); }
  else if (mode === 'call') {
    header(); let y = bubble(200, PHONE_TXT.msg1, false, 24);
    g.fillStyle = 'rgba(10,12,18,0.97)'; g.fillRect(0, 0, W, H); g.textAlign = 'center'; g.fillStyle = '#e8ecf4'; g.font = '500 30px Inter, sans-serif'; g.fillText('Appel : Lina', W / 2, 200);
    g.fillStyle = '#ff3a3a'; g.font = '800 40px Inter, sans-serif'; g.fillText('PAS DE RÉSEAU', W / 2, 300); g.strokeStyle = '#ff3a3a'; g.lineWidth = 6; g.beginPath(); g.arc(W / 2, 450, 60, 0, 7); g.stroke(); g.beginPath(); g.moveTo(W / 2 - 42, 492); g.lineTo(W / 2 + 42, 408); g.stroke();
    g.fillStyle = '#c03030'; g.beginPath(); g.arc(W / 2, 610, 44, 0, 7); g.fill(); g.textAlign = 'left';
  } else if (mode === 'map' || mode === 'chat2') {
    header(); let y = 170;
    if (mode === 'chat2') y = bubble(172, PHONE_TXT.msg2, false, 38) + 6;
    // carte : fond sombre, routes, forêt, épingle rouge (sous la conversation)
    const mx = 24, my = y, mw = 250, mh = 170; g.fillStyle = '#1a2a22'; g.beginPath(); g.roundRect(mx, my, mw, mh, 18); g.fill(); g.save(); g.beginPath(); g.roundRect(mx, my, mw, mh, 18); g.clip();
    const r = mulberry(5); for (let i = 0; i < 40; i++) { g.fillStyle = `rgba(20,${60 + r() * 40 | 0},40,0.9)`; g.beginPath(); g.arc(mx + r() * mw, my + r() * mh, 8 + r() * 14, 0, 7); g.fill(); }
    g.strokeStyle = '#d8d0a0'; g.lineWidth = 7; g.beginPath(); g.moveTo(mx - 10, my + 40); g.lineTo(mx + 90, my + 70); g.lineTo(mx + mw + 10, my + 50); g.stroke();
    g.fillStyle = '#ff2a2a'; g.beginPath(); g.arc(mx + 170, my + mh * 0.55, 16, Math.PI, 0); g.lineTo(mx + 170, my + mh * 0.55 + 38); g.closePath(); g.fill(); g.fillStyle = '#fff'; g.beginPath(); g.arc(mx + 170, my + mh * 0.55, 6, 0, 7); g.fill(); g.restore();
    g.fillStyle = '#f2f4f8'; g.font = '600 20px Inter, sans-serif'; g.fillText('Position partagée', mx + 6, my + mh + 10);
  }
  return c;
}
export function buildPhone() {
  const g = new THREE.Group(); const w = 0.12, h = 0.24, d = 0.016;
  g.add(vox([{ x: 0, y: 0, z: 0, w, h, d, color: 0x16161a }, { x: -0.03, y: 0.08, z: -d / 2 - 0.004, w: 0.045, h: 0.05, d: 0.008, color: 0x222228 }, { x: -0.04, y: 0.095, z: -d / 2 - 0.009, w: 0.016, h: 0.016, d: 0.004, color: 0x050508 }], { phong: 60, spec: 0x444444, rim: 1 }));
  const tex = {}; const mat = new THREE.MeshBasicMaterial({ color: new THREE.Color(1.25, 1.25, 1.3) });
  const scr = new THREE.Mesh(new THREE.PlaneGeometry(w * 0.92, h * 0.94), mat); scr.position.z = d / 2 + 0.0008; scr.rotation.z = Math.PI; g.add(scr);
  let cur = null;
  return { g, screen: scr, show(mode) { if (mode === cur) return; cur = mode; if (!tex[mode]) { const t = new THREE.CanvasTexture(paintPhone(mode)); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; tex[mode] = t; } mat.map = tex[mode]; mat.needsUpdate = true; }, light: (k = 1) => ({ color: 0x9ab4ff, i: 0.6 * k, dist: 1.6, decay: 2 }) };
}

// ------------------------------------------------------------------ lanterne (fer noir, flamme rouge-orangé)
export function buildLantern() {
  const g = new THREE.Group(); const k = 0.03; const B = [];
  const iron = 0x1e1a1a;
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) B.push({ x: sx * 2 * k, y: 0, z: sz * 2 * k, w: k * 0.6, h: k * 5, d: k * 0.6, color: iron });
  B.push({ x: 0, y: -2.7 * k, z: 0, w: k * 5, h: k * 0.8, d: k * 5, color: iron }, { x: 0, y: 2.7 * k, z: 0, w: k * 5, h: k * 0.8, d: k * 5, color: iron }, { x: 0, y: 3.6 * k, z: 0, w: k * 3, h: k * 1.2, d: k * 3, color: 0x2a2020 });
  B.push({ x: 0, y: 5.2 * k, z: 0, w: k * 3.2, h: k * 0.5, d: k * 0.5, color: iron }, { x: -1.6 * k, y: 4.6 * k, z: 0, w: k * 0.5, h: k * 1.6, d: k * 0.5, color: iron }, { x: 1.6 * k, y: 4.6 * k, z: 0, w: k * 0.5, h: k * 1.6, d: k * 0.5, color: iron });
  g.add(vox(B, { phong: 40, spec: 0x553322, rim: 1 }));
  const glass = new THREE.Mesh(new THREE.BoxGeometry(k * 3.6, k * 4.4, k * 3.6), new THREE.MeshBasicMaterial({ color: new THREE.Color(0.5, 0.12, 0.05), transparent: true, opacity: 0.55, depthWrite: false })); g.add(glass);
  const flameM = glowMat(6, 1.6, 0.4); const flame = new THREE.Mesh(new THREE.BoxGeometry(k * 1.1, k * 1.8, k * 1.1), flameM); flame.position.y = -0.6 * k; g.add(flame);
  return { g, flame, flameM, glass, set(on, t) { const f = on * (0.85 + 0.15 * Math.sin(t * 17) * Math.sin(t * 5.3)); flameM.color.setRGB(6 * f, 1.6 * f, 0.4 * f); flame.visible = on > 0.01; flame.scale.y = 0.8 + 0.3 * Math.sin(t * 11); glass.material.color.setRGB(0.5 * on + 0.05, 0.12 * on + 0.02, 0.05 * on + 0.02); }, light: (on, t) => ({ color: 0xff7a30, i: 3.2 * on * (0.85 + 0.15 * Math.sin(t * 17)), dist: 7, decay: 1.5 }) };
}

// ------------------------------------------------------------------ lampe torche
export function buildFlashlight() {
  const g = new THREE.Group(); const k = 0.022;
  g.add(vox([{ x: 0, y: 0, z: 0, w: k * 1.6, h: k * 1.6, d: k * 7, color: 0x2a2a30 }, { x: 0, y: 0, z: k * 4, w: k * 2.4, h: k * 2.4, d: k * 1.6, color: 0x3a3a42 }, { x: 0, y: k * 1, z: -k * 1, w: k * 0.6, h: k * 0.4, d: k * 1, color: 0xc02020 }], { phong: 50, rim: 1 }));
  const lensM = glowMat(4, 3.8, 3.2); const lens = new THREE.Mesh(new THREE.BoxGeometry(k * 2, k * 2, k * 0.2), lensM); lens.position.z = k * 4.85; g.add(lens);
  return { g, lens, set(on) { lensM.color.setRGB(4 * on + 0.05, 3.8 * on + 0.05, 3.2 * on + 0.05); } };
}

// ------------------------------------------------------------------ caméra de surveillance (support mural, tête orientable, LED rouge)
export function buildCCTV() {
  const g = new THREE.Group(); const head = new THREE.Group();
  g.add(vox([{ x: 0, y: 0, z: 0, w: 0.12, h: 0.04, d: 0.12, color: 0xd8d8d0 }, { x: 0, y: -0.08, z: 0, w: 0.04, h: 0.14, d: 0.04, color: 0xc8c8c0 }], { rim: 0.6 }));
  head.position.y = -0.16; g.add(head);
  head.add(vox([{ x: 0, y: 0, z: 0.05, w: 0.12, h: 0.11, d: 0.26, color: 0xe4e4dc }, { x: 0, y: 0.065, z: 0.07, w: 0.14, h: 0.02, d: 0.3, color: 0xd0d0c8 }, { x: 0, y: 0, z: 0.185, w: 0.08, h: 0.08, d: 0.02, color: 0x101014 }], { rim: 0.6 }));
  const ledM = glowMat(8, 0.4, 0.3); const led = new THREE.Mesh(new THREE.BoxGeometry(0.018, 0.018, 0.01), ledM); led.position.set(0.035, -0.035, 0.197); head.add(led);
  const lens = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.05, 0.01), new THREE.MeshPhongMaterial({ color: 0x0a0a14, shininess: 120, specular: 0x8888aa })); lens.position.set(0, 0, 0.197); head.add(lens);
  return { g, head, ledM, set(yaw, pitch, t) { head.rotation.set(pitch, yaw, 0, 'YXZ'); const on = Math.sin(t * 6) > 0 ? 1 : 0.15; ledM.color.setRGB(8 * on, 0.4 * on, 0.3 * on); } };
}

// ------------------------------------------------------------------ moniteur : affiche l'image d'une seconde caméra (rendue dans S.preRender)
export function buildMonitor(renderer, w = 0.62, h = 0.42) {
  const g = new THREE.Group();
  g.add(vox([{ x: 0, y: 0, z: -0.06, w: w + 0.08, h: h + 0.08, d: 0.14, color: 0x1a1a1e }, { x: 0, y: h / 2 + 0.25, z: -0.06, w: 0.04, h: 0.5, d: 0.04, color: 0x2a2a2e }], { phong: 40, rim: 0.7 }));
  const rt = new THREE.WebGLRenderTarget(320, 216, { type: THREE.HalfFloatType });
  const cam = new THREE.PerspectiveCamera(70, w / h, 0.05, 60);
  const mat = new THREE.ShaderMaterial({ uniforms: { tMap: { value: rt.texture }, uTime: { value: 0 }, uOn: { value: 1 } },
    vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }',
    fragmentShader: `uniform sampler2D tMap; uniform float uTime, uOn; varying vec2 vUv;
      float h(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233))) * 43758.5453); }
      void main(){ vec2 uv = vUv; uv.x += (h(vec2(floor(uv.y * 90.0), floor(uTime * 12.0))) - 0.5) * 0.004;
        vec3 c = texture2D(tMap, uv).rgb; float l = dot(c, vec3(0.3, 0.55, 0.15)); l = pow(l * 1.6, 0.85);
        vec3 col = vec3(l) * vec3(0.85, 1.0, 0.9); col *= 0.82 + 0.18 * sin(vUv.y * 420.0); col += (h(vUv * 300.0 + uTime) - 0.5) * 0.12;
        col *= smoothstep(0.0, 0.08, vUv.x) * smoothstep(1.0, 0.92, vUv.x) * smoothstep(0.0, 0.08, vUv.y) * smoothstep(1.0, 0.92, vUv.y) * 0.4 + 0.6;
        float rec = step(length(vUv - vec2(0.08, 0.9)), 0.025) * step(0.0, sin(uTime * 6.0)); col = mix(col, vec3(3.0, 0.1, 0.1), rec);
        gl_FragColor = vec4(col * 1.35 * uOn, 1.0); }` });
  const scr = new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat); scr.position.z = 0.012; g.add(scr);
  return {
    g, cam, rt, mat,
    // à appeler depuis S.preRender : rendu de la scène vue par la caméra de surveillance
    render(rend, scene, pos, look, t) { cam.position.copy(pos); cam.lookAt(look); cam.updateMatrixWorld(); mat.uniforms.uTime.value = t; const vis = scr.visible; scr.visible = false; const old = rend.getRenderTarget(); rend.setRenderTarget(rt); rend.clear(); rend.render(scene, cam); rend.setRenderTarget(old); scr.visible = vis; },
  };
}

// ------------------------------------------------------------------ voiture (berline voxel, feux rouges allumés)
export function buildCar(color = 0x3a0c10) {
  const g = new THREE.Group(); const B = []; const dark = 0x0a0a0e, chrome = 0x9a9aa0;
  B.push({ x: 0, y: 0.55, z: 0, w: 1.9, h: 0.5, d: 4.4, color }, { x: 0, y: 0.98, z: -0.15, w: 1.7, h: 0.42, d: 2.3, color });
  B.push({ x: 0, y: 0.32, z: 2.22, w: 1.92, h: 0.2, d: 0.08, color: chrome }, { x: 0, y: 0.32, z: -2.22, w: 1.92, h: 0.2, d: 0.08, color: chrome });
  for (const sx of [-1, 1]) for (const sz of [-1.35, 1.35]) B.push({ x: sx * 0.86, y: 0.33, z: sz, w: 0.28, h: 0.66, d: 0.66, color: 0x0c0c0e }, { x: sx * 0.92, y: 0.33, z: sz, w: 0.06, h: 0.34, d: 0.34, color: 0x6a6a70 });
  g.add(vox(B, { phong: 70, spec: 0x664444, rim: 0.9, wet: 1.6 }));
  const glassM = new THREE.MeshPhongMaterial({ color: 0x050608, shininess: 120, specular: 0x9a8a8a }); rimify(glassM, 0.8, 1.6);
  const gl = new THREE.Mesh(boxesGeometry([{ x: 0, y: 0.99, z: 0.9, w: 1.62, h: 0.36, d: 0.5, color: 0xffffff, rx: -0.5 }, { x: 0, y: 0.99, z: -1.2, w: 1.62, h: 0.36, d: 0.4, color: 0xffffff, rx: 0.5 }, { x: 0.86, y: 1.0, z: -0.15, w: 0.02, h: 0.32, d: 2.0, color: 0xffffff }, { x: -0.86, y: 1.0, z: -0.15, w: 0.02, h: 0.32, d: 2.0, color: 0xffffff }]), glassM); g.add(gl);
  const headM = glowMat(9, 0.8, 0.5), tailM = glowMat(7, 0.3, 0.25);
  for (const sx of [-1, 1]) { const hl = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.14, 0.04), headM); hl.position.set(sx * 0.62, 0.62, 2.21); g.add(hl); const tl = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.12, 0.04), tailM); tl.position.set(sx * 0.66, 0.66, -2.21); g.add(tl); }
  return { g, headM, tailM, set(k) { headM.color.setRGB(9 * k, 0.8 * k, 0.5 * k); tailM.color.setRGB(7 * k, 0.3 * k, 0.25 * k); }, lights(k = 1) { g.updateMatrixWorld(true); const p = g.getWorldPosition(V()); const f = V(0, 0, 1).applyQuaternion(g.getWorldQuaternion(new THREE.Quaternion())); return [{ pos: p.clone().addScaledVector(f, 2.6).add(V(0, 0.6, 0)), color: 0xff1810, i: 3 * k, dist: 9, decay: 1.2 }]; } };
}

// ------------------------------------------------------------------ canettes, bouteilles, paquets, caisse (pour le sol de la supérette)
export function cansBoxes(r, n, area, y0 = 0) {
  const pal = [0xd02a2a, 0x2a8a3a, 0x2a5ad0, 0xe8c020, 0xe8e8e8, 0x8a2ad0, 0xf07a1a];
  const B = [];
  for (let i = 0; i < n; i++) {
    const x = area[0] + r() * (area[2] - area[0]), z = area[1] + r() * (area[3] - area[1]); const col = pal[Math.floor(r() * pal.length)]; const ry = r() * 6.28; const kind = r();
    if (kind < 0.55) { // canette couchée : corps + bandes
      B.push({ x, y: y0 + 0.035, z, w: 0.07, h: 0.07, d: 0.12, color: col, ry }, { x, y: y0 + 0.035, z, w: 0.074, h: 0.074, d: 0.03, color: 0xe8e8e8, ry });
    } else if (kind < 0.8) { B.push({ x, y: y0 + 0.04, z, w: 0.08, h: 0.08, d: 0.24, color: col, ry }, { x, y: y0 + 0.04, z, w: 0.04, h: 0.04, d: 0.3, color: 0xf0f0f0, ry }); }
    else B.push({ x, y: y0 + 0.05, z, w: 0.2, h: 0.1, d: 0.14, color: col, ry, rz: (r() - 0.5) * 0.4 });
  }
  return B;
}
export function crateBoxes(x, y, z, ry = 0, col = 0x8a1418) {
  const B = []; const c = Math.cos(ry), s = Math.sin(ry); const P = (dx, dz) => [x + dx * c + dz * s, z - dx * s + dz * c];
  for (const [dx, dz, w, d] of [[0, 0.2, 0.6, 0.04], [0, -0.2, 0.6, 0.04], [0.28, 0, 0.04, 0.4], [-0.28, 0, 0.04, 0.4]]) { const [px, pz] = P(dx, dz); for (let yy = 0; yy < 3; yy++) B.push({ x: px, y: y + 0.04 + yy * 0.1, z: pz, w, h: 0.05, d, color: col, ry }); }
  const [bx, bz] = P(0, 0); B.push({ x: bx, y: y + 0.01, z: bz, w: 0.58, h: 0.02, d: 0.38, color: col, ry });
  return B;
}

// ------------------------------------------------------------------ traces de mains sur la vitre (de l'intérieur) : apparition par seuil
export function handprintMaterial(seed = 3, n = 46) {
  const S = 512; const c = document.createElement('canvas'); c.width = S; c.height = S; const g = c.getContext('2d'); g.fillStyle = 'rgb(0,0,0)'; g.fillRect(0, 0, S, S);
  const r = mulberry(seed);
  for (let i = 0; i < n; i++) {
    const x = 30 + r() * (S - 60), y = 40 + r() * (S - 90), sc = 0.7 + r() * 0.5, rot = (r() - 0.5) * 0.9, th = Math.floor(20 + 230 * (i / n));
    g.save(); g.translate(x, y); g.rotate(rot); g.scale(sc, sc); g.fillStyle = `rgb(255,${th},0)`;
    g.beginPath(); g.ellipse(0, 6, 15, 18, 0, 0, 7); g.fill();
    for (let f = 0; f < 4; f++) { g.save(); g.translate(-11 + f * 7.3, -10); g.rotate((f - 1.5) * 0.12); g.beginPath(); g.roundRect(-3, -22 + Math.abs(f - 1.5) * 3, 6.2, 24 - Math.abs(f - 1.5) * 3, 3); g.fill(); g.restore(); }
    g.save(); g.translate(15, 4); g.rotate(-0.9); g.beginPath(); g.roundRect(-3, -16, 6.5, 17, 3); g.fill(); g.restore();
    // coulures
    for (let d = 0; d < 3; d++) if (r() < 0.6) { g.fillRect(-10 + r() * 20, 20, 2, 10 + r() * 30); }
    g.restore();
  }
  const tex = new THREE.CanvasTexture(c); tex.minFilter = THREE.LinearFilter; tex.magFilter = THREE.LinearFilter;
  return new THREE.ShaderMaterial({ uniforms: { tMask: { value: tex }, uReveal: { value: 0 }, uCol: { value: new THREE.Color(0.06, 0.012, 0.012) }, uGlow: { value: new THREE.Color(0.9, 0.05, 0.03) }, uRep: { value: new THREE.Vector2(1, 1) } },
    vertexShader: 'varying vec2 vUv; uniform vec2 uRep; void main(){ vUv = uv * uRep; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }',
    fragmentShader: `uniform sampler2D tMask; uniform float uReveal; uniform vec3 uCol, uGlow; varying vec2 vUv;
      void main(){ vec4 m = texture2D(tMask, fract(vUv)); float on = m.r * smoothstep(m.g, m.g + 0.06, uReveal * 1.05);
        if (on < 0.02) discard; gl_FragColor = vec4(uCol + uGlow * on * 0.25, on * 0.92); }`,
    transparent: true, depthWrite: false, side: THREE.DoubleSide });
}
