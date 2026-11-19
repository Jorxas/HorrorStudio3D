// Le THÉÂTRE de bal dans le peintre VOXEL (version native, hstudio/voxelgpu/b_theatre.py) : ce qui bouge et ce qui éclaire.
//   * accessoire `btheatre` : les deux anneaux du plateau tournant (pivots), les flammes et vitres de lanternes (matières lumineuses par groupes,
//     scintillement fonction du temps), les lentilles des projecteurs, les faisceaux du rideau de lumière (cônes additifs « dans la brume »),
//     leurs flaques au sol et les faisceaux des poursuites ;
//   * `applyTheatre(st, T, S, ...)` : la lumière de scène de l'image, lue telle quelle dans `stage.theatre.frames` (une ligne par image, colonnes
//     `stage.theatre.cols` puis `follow_cols` par poursuite). Lavis = 3 projecteurs larges de face + une clé douce ; contre-jour = projecteur du fond +
//     liseré ; poursuites = projecteurs nets ; bougies et lanternes = lumières ponctuelles. Le peintre ouvre 6 projecteurs et 8 lumières
//     (`spot_pool`, `point_pool` du contrat, main_unified.js).
// Rien ne décide ici : tout vient du contrat. Aucune horloge, aucun hasard : fonction pure de T.
import * as THREE from 'three';
import { boxesGeometry } from './boxes.js';
import { vox, vmat } from './props4.js';
import { PROPS } from './horror_kit.js';

const V = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const flick = (t, s) => 0.84 + 0.1 * Math.sin(t * 9.1 + s * 1.7) * Math.sin(t * 5.3 + s * 0.9) + 0.06 * Math.sin(t * 23.0 + s * 3.1);      // = theatre.flicker (PS1)
const hex = (r, g, b, k = 1) => new THREE.Color().setRGB(clamp(r * k, 0, 1), clamp(g * k, 0, 1), clamp(b * k, 0, 1)).getHex();

// faisceau : cône ouvert, sommet en 0, base à y = -1 ; additif, plus clair au centre (la brume vue de face) et vers la source
const BEAM_VS = `varying float vS; varying vec3 vN; varying vec3 vV; void main(){ vS = -position.y; vec4 mv = modelViewMatrix * vec4(position, 1.0); vV = -mv.xyz; vN = normalMatrix * normal; gl_Position = projectionMatrix * mv; }`;
// Garde-fou : un triangle du cône qui passe derrière l'objectif peut donner, sur quelques pixels, des varyings infinis ou NaN ; une seule valeur NaN/Inf dans l'image HDR
// est étalée par le halo (UnrealBloom, mipmaps) en un grand CARRÉ lumineux. Ces fragments sont jetés et toute sortie est bornée (0..4) : l'image ne dépend que de son temps.
const BEAM_FS = `uniform vec3 uColor; uniform float uI; varying float vS; varying vec3 vN; varying vec3 vV;
  void main(){ float ln = length(vN), lv = length(vV);
    if (!(ln > 1e-5 && ln < 1e5 && lv > 1e-4 && lv < 1e5 && abs(vS) < 1e3)) discard;
    float e = pow(clamp(abs(dot(vN / ln, vV / lv)), 0.0, 1.0), 1.7); float s = clamp(vS, 0.0, 1.0); float fall = pow(1.0 - s, 1.3) * (0.4 + 0.6 * exp(-s * 2.6));
    gl_FragColor = vec4(clamp(uColor * uI * e * fall, 0.0, 4.0), 1.0); }`;
const POOL_FS = `uniform vec3 uColor; uniform float uI; varying vec2 vUv; void main(){ float r = length(vUv - 0.5) * 2.0; if (!(r < 1e3)) discard; float a = pow(clamp(1.0 - r, 0.0, 1.0), 1.4); gl_FragColor = vec4(clamp(uColor * uI * a, 0.0, 4.0), 1.0); }`;
const POOL_VS = `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
// disque au sol vu d'en haut (douche) : plein, anneau (`uRing` = rayon intérieur / rayon) ou tacheté (`uDap`, motif de feuillage, bruit fixe du sol)
const DISC_VS = `varying vec2 vUv; varying vec3 vW; void main(){ vUv = uv; vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
const DISC_FS = `uniform vec3 uColor; uniform float uI, uRing, uDap; varying vec2 vUv; varying vec3 vW;
  float h(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  float n2(vec2 p){ vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f); return mix(mix(h(i), h(i + vec2(1.0, 0.0)), f.x), mix(h(i + vec2(0.0, 1.0)), h(i + vec2(1.0, 1.0)), f.x), f.y); }
  void main(){ float r = length(vUv - 0.5) * 2.0; if (!(r < 1e3)) discard; float a = smoothstep(1.0, 0.9, r);
    if (uRing > 0.001) a *= smoothstep(uRing - 0.05, uRing + 0.05, r);
    if (uDap > 0.001) { vec2 q = (vW.xz - vec2(12000.0, 0.0)); float d = n2(q * 2.2) * 0.7 + n2(q * 5.5) * 0.3; a *= 1.0 - uDap * clamp((d - 0.44) * 7.0, 0.0, 1.0); }
    gl_FragColor = vec4(clamp(uColor * uI * a, 0.0, 4.0), 1.0); }`;
const addMat = (vs, fs) => new THREE.ShaderMaterial({ uniforms: { uColor: { value: new THREE.Color(1, 1, 1) }, uI: { value: 0 } }, vertexShader: vs, fragmentShader: fs, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, fog: false });
const coneGeo = (() => { const g = new THREE.CylinderGeometry(1, 1, 1, 28, 1, true); const p = g.attributes.position; for (let i = 0; i < p.count; i++) { const y = p.getY(i); const top = y > 0; p.setXYZ(i, p.getX(i) * (top ? 0.09 : 1), y - 0.5, p.getZ(i) * (top ? 0.09 : 1)); } g.computeVertexNormals(); return g; })();
const DOWN = V(0, -1, 0);

function orientBeam(m, pos, dir, len, rad) {
  m.position.copy(pos); m.quaternion.setFromUnitVectors(DOWN, dir.clone().normalize()); m.scale.set(rad, len, rad);
}

PROPS.btheatre = (p) => {
  const g = new THREE.Group();
  const floorMat = vmat({ phong: 26, spec: 0x3c3024, rim: 0.18, var: 0.07 });          // bois ciré : un reflet spéculaire des projecteurs
  const pivIn = new THREE.Group(), pivOut = new THREE.Group(); pivIn.position.set(...p.center); pivOut.position.set(...p.center);
  if (p.inner.length) pivIn.add(vox(p.inner, { mat: floorMat, cast: false })); if (p.outer.length) pivOut.add(vox(p.outer, { mat: floorMat, cast: false }));
  g.add(pivIn, pivOut);
  const glow = (list) => { const m = new THREE.Mesh(boxesGeometry(list), new THREE.MeshBasicMaterial({ vertexColors: true })); m.castShadow = false; g.add(m); return m; };
  const flames = p.flames.filter((l) => l.length).map(glow), glass = p.glass.filter((l) => l.length).map(glow), lens = glow(p.lens);
  const beams = [], pools = [];
  for (const b of p.beams) {
    const pos = V(b[0], b[1], b[2]), dir = V(b[3], b[4], b[5]).normalize(), len = p.beam_len, rad = len * Math.tan(p.half);
    const m = new THREE.Mesh(coneGeo, addMat(BEAM_VS, BEAM_FS)); orientBeam(m, pos.clone().addScaledVector(dir, 0.06), dir, len, rad); m.renderOrder = 10; m.frustumCulled = false; g.add(m); beams.push({ m, row: b[6] });
    const t = -pos.y / Math.min(-1e-3, dir.y), hit = pos.clone().addScaledVector(dir, t), pr = t * Math.tan(p.half) * 1.15;
    const pm = new THREE.Mesh(new THREE.CircleGeometry(1, 40), addMat(POOL_VS, POOL_FS)); pm.rotation.x = -Math.PI / 2; pm.position.set(hit.x, 0.03, hit.z); pm.scale.set(pr, pr / Math.max(0.35, -dir.y), 1); pm.renderOrder = 9; g.add(pm); pools.push({ m: pm, row: b[6] });
  }
  const discs = [0, 1, 2].map(() => { const mt = addMat(DISC_VS, DISC_FS); mt.uniforms.uRing = { value: 0 }; mt.uniforms.uDap = { value: 0 }; const m = new THREE.Mesh(new THREE.CircleGeometry(1, 48), mt); m.rotation.x = -Math.PI / 2; m.renderOrder = 9; m.visible = false; g.add(m); return m; });
  const follow = [0, 1].map(() => { const m = new THREE.Mesh(coneGeo, addMat(BEAM_VS, BEAM_FS)); m.renderOrder = 11; m.frustumCulled = false; m.visible = false; g.add(m); return m; });
  g.userData.theatre = { pivIn, pivOut, flames, glass, lens, beams, pools, follow, discs, p };
  return { g };
};

function findTheatre(mine) {
  if (!mine) return null; if (mine._theatre !== undefined) return mine._theatre;
  let t = null; mine.group.traverse((o) => { if (!t && o.userData && o.userData.theatre) t = o.userData.theatre; }); mine._theatre = t; return t;
}

export function applyTheatre(st, T, S, FPS, w, mine, cam) {
  const th = st.theatre, F = th.frames; if (!F || !F.length) return;
  const f = F[clamp(Math.round((T - st.t0) * FPS), 0, F.length - 1)];
  const [wr, wg, wb, wi, br, bg, bb, bi, ar, ag, ab, fr, fg, fb, haze, pr, cu, cr, cg, cb, tin, tout, nf] = f;
  const TH = findTheatre(mine), P = TH ? TH.p : null;
  // ---- lavis, contre-jour, ambiance, brume
  S.hemi = { sky: hex(ar * 2.2 + wr * 0.05 * wi, ag * 2.2 + wg * 0.05 * wi, ab * 2.2 + wb * 0.05 * wi), ground: hex(ar * 0.9, ag * 0.9, ab * 0.9), i: 1.0 };
  S.key = { dir: [0.12, 0.78, 0.62], color: hex(wr, wg, wb), i: 0.36 * wi };
  S.fill = { dir: [0.0, 0.55, -0.84], color: hex(br, bg, bb), i: 0.32 * bi };
  S.rim = { color: hex(br, bg, bb), i: 0.07 + 0.32 * bi, pow: 3.2 };
  S.fog = { color: hex(fr, fg, fb), d: 0.008 + 0.022 * haze }; S.bg = hex(fr, fg, fb, 0.6); S.lift = 0x000000;
  S.bloom = Math.max(S.bloom, 0.55); S.sat = Math.max(S.sat, 1.25); S.bloomThreshold = 0.82; S.bloomRadius = 0.55; S.dofScale = Math.min(S.dofScale, 0.12);      // la scène reste nette au loin (plans larges de salle)
  const spots = [];
  // poursuites d'abord (nettes), puis le lavis de face, puis le contre-jour
  for (let i = 0; i < nf; i++) {
    const o = 23 + i * 16, q = f.slice(o, o + 16); const src = w.at(q[0], q[1], q[2]), aim = w.at(q[3], q[4], q[5]), so = q[15] || 0;
    spots.push({ pos: src, target: aim, color: hex(q[8], q[9], q[10]), i: 260 * q[7] * (1 - 0.35 * so), angle: Math.min(1.4, q[6] * (1 + 0.6 * so)), pen: 0.12 + 0.75 * so, dist: 0, decay: 1.6 });
    if (TH) { const fm = TH.follow[i]; if (fm) {
      // le faisceau commence devant l'objectif : une source de poursuite dans la salle est souvent DERRIÈRE la caméra (aucun triangle ne doit passer derrière elle)
      const d = aim.clone().sub(src); const L = d.length() + 1.4; d.normalize(); let t0 = 0;
      if (cam) { const cd = cam.look.clone().sub(cam.pos).normalize(), ahead = src.clone().sub(cam.pos).dot(cd), cos = d.dot(cd); if (ahead < 0.6 && cos > 0.05) t0 = Math.min(L - 0.5, (0.6 - ahead) / cos); }
      const start = V(q[0], q[1], q[2]).addScaledVector(d, t0), Lr = L - t0;
      fm.visible = haze > 0.01 && so < 0.6 && Lr > 0.5; orientBeam(fm, start, d, Lr, L * Math.tan(q[6])); fm.material.uniforms.uColor.value.setRGB(q[8], q[9], q[10]); fm.material.uniforms.uI.value = 0.09 * q[7] * haze * (1 - so); } }
  }
  if (TH) for (let i = nf; i < TH.follow.length; i++) TH.follow[i].visible = false;
  const op = 23 + nf * 16, np = f[op] | 0;
  for (let i = 0; i < np; i++) {                                      // disques au sol : une douche verticale (projecteur) + le motif au sol (disque additif)
    const q = f.slice(op + 1 + i * 9, op + 10 + i * 9);
    spots.push({ pos: w.at(q[0], 12.65, q[1]), target: w.at(q[0], 0, q[1]), color: hex(q[5], q[6], q[7]), i: 150 * q[4], angle: Math.atan2(q[2] * 1.05, 12.65), pen: 0.15, dist: 0, decay: 1.6 });
    if (TH && TH.discs[i]) { const m = TH.discs[i]; m.visible = true; m.position.set(q[0], 0.035, q[1]); m.scale.set(q[2], q[2], 1); const u = m.material.uniforms; u.uColor.value.setRGB(q[5], q[6], q[7]); u.uI.value = 0.3 * q[4]; u.uRing.value = q[2] > 0 ? q[3] / q[2] : 0; u.uDap.value = q[8]; }
  }
  if (TH) for (let i = np; i < TH.discs.length; i++) TH.discs[i].visible = false;
  if (P && wi > 1e-3) {
    const c = V(P.center[0], 0, P.center[2]);
    for (const p of P.wash) spots.push({ pos: w.at(p[0], p[1], p[2]), target: w.at(p[0] * 0.45, 0, c.z * 0.8), color: hex(wr, wg, wb), i: 95 * wi, angle: 0.56, pen: 0.55, dist: 0, decay: 1.6 });
  }
  if (P && bi > 1e-3) spots.push({ pos: w.at(...P.back), target: w.at(P.center[0], 0, P.center[2] * 0.6), color: hex(br, bg, bb), i: 60 * bi, angle: 0.9, pen: 0.7, dist: 0, decay: 1.6 });
  S.spots = spots;
  // ---- bougies et lanternes : lumières ponctuelles (les 8 plus proches du regard), matières lumineuses qui scintillent
  if (P && pr > 1e-3) {
    P.groups.forEach((gp, i) => S.lights.push({ pos: w.at(gp[0], gp[1], gp[2]), color: 0xffa860, i: (gp[3] > 3 ? 2.2 : 1.1) * pr * flick(T, i), dist: gp[3] > 3 ? 3.4 : 2.2, decay: 1.5 }));
    P.lanterns.forEach((l, i) => S.lights.push({ pos: w.at(l[0], l[1] - 0.1, l[2]), color: 0xff9a50, i: 1.0 * pr * flick(T, 40 + i), dist: 2.6, decay: 1.5 }));
  }
  if (!TH) return;
  TH.pivIn.rotation.y = tin; TH.pivOut.rotation.y = tout;
  TH.flames.forEach((m, i) => m.material.color.setScalar(Math.max(0.05, pr) * 1.35 * flick(T, i * 3 + 1)));
  TH.glass.forEach((m, i) => m.material.color.setScalar(Math.max(0.06, pr) * 1.05 * flick(T, 20 + i)));
  const lensOn = cu > 0.02; TH.lens.material.color.setRGB(lensOn ? cr * (0.5 + 2.8 * cu) : 0.004, lensOn ? cg * (0.5 + 2.8 * cu) : 0.0045, lensOn ? cb * (0.5 + 2.8 * cu) : 0.005);
  for (const b of TH.beams) { const k = cu * haze * (b.row === 0 ? 0.32 : 0.26); b.m.visible = k > 0.002; b.m.material.uniforms.uColor.value.setRGB(cr, cg, cb); b.m.material.uniforms.uI.value = k; }
  for (const b of TH.pools) { const k = cu * (b.row === 0 ? 0.5 : 0.38); b.m.visible = k > 0.002; b.m.material.uniforms.uColor.value.setRGB(cr, cg, cb); b.m.material.uniforms.uI.value = k; }
}
