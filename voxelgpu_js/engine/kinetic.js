// Typographie cinétique en voxels : chaque mot est fait de petits cubes (police pixel Monocraft, OFL),
// posé DANS la scène (ombres, profondeur de champ, reflets), avec des animations d'entrée / sortie
// calées sur le temps. Tout est fonction pure du temps : update(t, items) place les mots visibles.
import * as THREE from 'three';

let FONT = null;
export async function loadPixelFont(url = './assets/pixelfont.json') { FONT = await (await fetch(url)).json(); return FONT; }

const hash = (n) => { const s = Math.sin(n * 127.1 + 311.7) * 43758.5453; return s - Math.floor(s); };
const clamp01 = (x) => Math.min(1, Math.max(0, x));
const easeOutBack = (x) => { const c1 = 1.9, c3 = c1 + 1; x = clamp01(x); return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };
const easeOut = (x) => 1 - Math.pow(1 - clamp01(x), 3);
const easeIn = (x) => Math.pow(clamp01(x), 2.2);

// texte -> liste de cellules [x, y, indexLettre] (x vers la droite, y vers le haut, ligne de base à y=0)
const layoutCache = new Map();
export function layout(text, tracking = 1) {
  const key = text + '|' + tracking; if (layoutCache.has(key)) return layoutCache.get(key);
  const cells = []; let x = 0, li = 0, maxTop = 0, minBot = 0;
  for (const ch of text) {
    const g = FONT.glyphs[ch] || FONT.glyphs[ch.toLowerCase()] || FONT.glyphs['?'];
    if (g.space) { x += 3; li++; continue; }
    const w = g.rows[0].length;
    g.rows.forEach((row, j) => {
      const yy = 7 - 1 - (g.top + j);            // cap row 0 -> y = 6 ; descenders go below 0
      for (let i = 0; i < row.length; i++) if (row[i] === '#') { cells.push([x + i, yy, li]); maxTop = Math.max(maxTop, yy); minBot = Math.min(minBot, yy); }
    });
    x += w + tracking; li++;
  }
  const res = { cells, width: Math.max(1, x - tracking), top: maxTop + 1, bottom: minBot, letters: li };
  layoutCache.set(key, res); return res;
}

export function buildKinetic(scene, { pool = 36, maxCells = 520, depth = 1.6 } = {}) {
  const geo = new THREE.BoxGeometry(1, 1, depth);
  const words = [];
  for (let i = 0; i < pool; i++) {
    const mat = new THREE.MeshLambertMaterial({ color: 0xffffff, emissive: 0xffffff, emissiveIntensity: 0.3, transparent: false });
    const im = new THREE.InstancedMesh(geo, mat, maxCells); im.castShadow = true; im.receiveShadow = true; im.frustumCulled = false; im.visible = false;
    im.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    const g = new THREE.Group(); g.add(im); scene.add(g);
    words.push({ g, im, mat, text: null });
  }
  const M = new THREE.Matrix4(), Q = new THREE.Quaternion(), P = new THREE.Vector3(), Sv = new THREE.Vector3(), E = new THREE.Euler();
  const col = new THREE.Color(), emi = new THREE.Color();

  // item: { text, t0, t1, pos:Vector3, rot:[x,y,z], size (hauteur des capitales en m), color, glow, inStyle, outStyle, seed, align }
  function draw(w, it, t) {
    const L = layout(it.text, it.tracking ?? 1);
    const px = (it.size ?? 0.5) / 7;
    const ax = it.align === 'left' ? 0 : it.align === 'right' ? -L.width : -L.width / 2;
    const ay = -3.5;                                 // centre vertical sur la hauteur des capitales
    w.g.position.copy(it.pos);
    const bob = Math.sin(t * 1.3 + (it.seed ?? 0) * 7) * 0.012 * (it.size ?? 0.5) * (it.float ?? 1);
    w.g.position.y += bob;
    w.g.rotation.set(it.rot?.[0] ?? 0, it.rot?.[1] ?? 0, (it.rot?.[2] ?? 0) + Math.sin(t * 0.9 + (it.seed ?? 0) * 3) * 0.015 * (it.float ?? 1), it.order || 'YXZ');
    w.g.scale.setScalar(px);
    col.set(it.color ?? 0xf4ead8); w.mat.color.copy(col);
    emi.copy(col); w.mat.emissive.copy(emi); w.mat.emissiveIntensity = (it.glow ?? 0.35) * (it.glowMul ?? 1);
    const inS = it.inStyle || 'pop', outS = it.outStyle || 'shrink';
    const lt = t - it.t0, ot = it.t1 != null ? t - it.t1 : -1;
    const stag = it.stagger ?? 0.035; let n = 0;
    for (const [cx, cy, li] of L.cells) {
      const ls = lt - li * stag;                      // temps propre de la lettre
      if (ls < 0 && inS !== 'none') continue;
      let x = cx + ax + 0.5, y = cy + ay + 0.5, z = 0, s = 1, rx = 0, ry = 0, rz = 0;
      const h1 = hash(cx * 13.1 + cy * 7.7 + li * 3.3 + (it.seed ?? 0)), h2 = hash(cx * 3.9 + cy * 11.3 + 1.7 + (it.seed ?? 0)), h3 = hash(cx * 5.3 - cy * 2.1 + 9.1);
      // entrées
      if (inS === 'pop') { const k = easeOutBack(ls / 0.22); s = Math.max(0.0001, k); z = (1 - clamp01(ls / 0.22)) * 6; }
      else if (inS === 'drop') { const k = clamp01(ls / 0.35); const b = 1 - easeOut(k); y += b * 30 + Math.abs(Math.sin(k * Math.PI * 2)) * (1 - k) * 3; s = 1; }
      else if (inS === 'rise') { const k = easeOut(ls / 0.45); y -= (1 - k) * 12; s = 0.0001 + k; }
      else if (inS === 'slide') { const k = easeOut(ls / 0.3); x -= (1 - k) * 20; s = clamp01(ls / 0.1); }
      else if (inS === 'assemble') { const k = easeOut((lt - h1 * 0.25) / 0.5); if (lt < h1 * 0.25) continue; x += (h1 - 0.5) * 40 * (1 - k); y += (h2 - 0.3) * 30 * (1 - k); z += (h3 - 0.5) * 40 * (1 - k); rx = (1 - k) * 6 * h2; ry = (1 - k) * 6 * h1; s = 0.3 + 0.7 * k; }
      else if (inS === 'type') { s = ls > 0 ? 1 : 0.0001; }
      // sorties
      if (ot > 0) {
        if (outS === 'shrink') { const k = clamp01(ot / 0.25); s *= 1 - easeIn(k); if (k >= 1) continue; }
        else if (outS === 'scatter') {               // les cubes s'envolent comme de la neige
          const k = ot / (1.6 + h3);
          if (k >= 1) continue;
          x += (h1 - 0.5) * 14 * k + Math.sin(ot * 3 + h2 * 9) * 1.5 * k; y += (h2 * 10 + 6) * k * k * 1.5; z += (h3 - 0.5) * 18 * k;
          rx += ot * (2 + h1 * 4); ry += ot * (1 + h2 * 3); s *= 1 - easeIn(k);
        }
        else if (outS === 'fall') { const k = clamp01(ot / 0.6); y -= k * k * 40; rx += k * 3 * (h1 - 0.5); if (k >= 1) continue; }
        else if (outS === 'cut') { continue; }
      }
      if (s < 0.001) continue;
      P.set(x, y, z); E.set(rx, ry, rz); Q.setFromEuler(E); Sv.set(s, s, s);
      M.compose(P, Q, Sv); w.im.setMatrixAt(n++, M);
      if (n >= w.im.count) break;
    }
    w.im.count = n; w.im.instanceMatrix.needsUpdate = true; w.im.visible = n > 0; w.g.visible = n > 0;
  }

  return {
    words,
    update(t, items) {
      let k = 0;
      for (const it of items) {
        if (t < it.t0 - 0.001 || (it.t1 != null && t > it.t1 + 3.5)) continue;
        if (k >= words.length) break;
        const w = words[k++]; w.im.count = 520; draw(w, it, t);
      }
      for (; k < words.length; k++) { words[k].g.visible = false; words[k].im.visible = false; }
    },
    hideAll() { for (const w of words) { w.g.visible = false; w.im.visible = false; } },
  };
}

// Place un mot dans le cadre d'une caméra : ndc (x,y dans [-1,1]), à une distance donnée, tourné vers la caméra
// avec une petite inclinaison (comme dans les clips en typographie 3D). cam: {pos, look, fov, roll}, aspect: largeur/hauteur.
export function placeInFrame(cam, aspect, ndcX, ndcY, dist, { yaw = 0, pitch = 0, roll = 0 } = {}) {
  const pos = cam.pos.clone(), fwd = cam.look.clone().sub(pos).normalize();
  const up0 = new THREE.Vector3(0, 1, 0);
  const right = new THREE.Vector3().crossVectors(fwd, up0).normalize();
  const up = new THREE.Vector3().crossVectors(right, fwd).normalize();
  if (cam.roll) { right.applyAxisAngle(fwd, cam.roll); up.applyAxisAngle(fwd, cam.roll); }
  const th = Math.tan((cam.fov ?? 50) * Math.PI / 360);
  const p = pos.addScaledVector(fwd, dist).addScaledVector(right, ndcX * th * aspect * dist).addScaledVector(up, ndcY * th * dist);
  // orientation : face à la caméra (le mot regarde vers -fwd)
  const m = new THREE.Matrix4().makeBasis(right, up, fwd.clone().negate());
  const e = new THREE.Euler().setFromRotationMatrix(m, 'YXZ');
  return { pos: p, rot: [e.x + pitch, e.y + yaw, e.z + roll], order: 'YXZ' };
}
