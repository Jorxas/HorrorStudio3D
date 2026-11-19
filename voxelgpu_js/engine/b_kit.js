// Kit « B » du moteur unifié : accueille les éléments de PIXEL 3D (V3) dans le peintre VOXEL.
//   * monde `plateau` : un sol et un éclairage réglables par `env`, vide de tout décor ; les décors, murs et meubles y sont POSÉS par plan
//     (`stage.props`, voir `bset`), convertis par hstudio/voxelgpu/b_props.py et b_sets.py. C'est ce qui permet une maison, un bureau, une forêt sans
//     écrire un générateur JS par lieu. Il porte aussi la météo de PIXEL 3D (`env.weather`) et les battants de porte animés (`stage.doors`).
//   * accessoire `bset` : une liste de boîtes { x, y, z, w, h, d, color, emis?, ry? } (centre + dimensions, en mètres, repère du monde) ; les boîtes
//     émissives (néons, lampes, écrans) sont peintes sans ombrage pour que le bloom les fasse rayonner ; `decals` : images de face (enseignes, tableaux) ;
//     `planes` : plaques horizontales texturées (sols procéduraux échantillonnés).
//   * accessoire `bdome` : le ciel dessiné de PIXEL 3D (dégradé, soleil, nuages, étoiles, horizon) en dôme texturé qui suit la caméra.
// Rien ici ne décide : tout vient des données du contrat.
import * as THREE from 'three';
import { boxesGeometry } from './boxes.js';
import { vox, vmat } from './props4.js';
import { Batch, mat4, grunge } from './kit4.js';
import { PROPS, grade, normEnv } from './horror_kit.js';

const V = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
const hex = (v, d) => (typeof v === 'string' ? parseInt(v.replace('#', ''), 16) : (v ?? d));
const dataTex = (d, { nearest = true } = {}) => {
  const bin = atob(d.rgba); const u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
  const t = new THREE.DataTexture(u, d.tw, d.th, THREE.RGBAFormat); t.colorSpace = THREE.SRGBColorSpace;
  t.magFilter = nearest ? THREE.NearestFilter : THREE.LinearFilter; t.minFilter = nearest ? THREE.NearestFilter : THREE.LinearFilter; t.needsUpdate = true; return t;
};

// ------------------------------------------------------------------ accessoire : boîtes de PIXEL 3D
PROPS.bset = (p) => {
  const g = new THREE.Group(); const solid = []; const glow = new Map(); const clear = new Map();
  for (const b of p.boxes || []) {
    const bb = { ...b, color: hex(b.color, 0x808080) };
    if (b.alpha !== undefined && b.alpha < 1) { const q = Math.max(1, Math.round(b.alpha * 10)) / 10, e = b.emis > 0 ? 1 : 0, key = q + ':' + e; if (!clear.has(key)) clear.set(key, [q, e, []]); clear.get(key)[2].push(bb); }     // objets détaillés : vapeur, verre, faisceau (absent des contrats d'avant)
    else if (b.emis > 0) { const k = Math.round(b.emis * 4) / 4; if (!glow.has(k)) glow.set(k, []); glow.get(k).push(bb); } else solid.push(bb);
  }
  if (solid.length) g.add(vox(solid, { rim: p.rim ?? 0.3, var: p.var ?? 0.08 }));
  for (const [k, list] of glow) {
    const m = new THREE.Mesh(boxesGeometry(list), new THREE.MeshBasicMaterial({ vertexColors: true })); m.material.color.setScalar(Math.max(1, k * 1.3)); m.castShadow = false; g.add(m);
  }
  for (const [q, e, list] of clear.values()) {
    const mt = e ? new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: q, depthWrite: false }) : new THREE.MeshLambertMaterial({ vertexColors: true, transparent: true, opacity: q, depthWrite: false });
    const m = new THREE.Mesh(boxesGeometry(list), mt); m.castShadow = false; m.renderOrder = 2; g.add(m);
  }
  // images de face (enseignes, tableaux, fenêtres) : plaques posées sur la face, texels nets ; RGBA en base64, rangées de bas en haut
  for (const d of p.decals || []) {
    const t = dataTex(d);
    const m = d.emis > 0 ? new THREE.MeshBasicMaterial({ map: t, transparent: true, color: new THREE.Color().setScalar(Math.max(1, d.emis * 1.3)) }) : new THREE.MeshLambertMaterial({ map: t, transparent: true });
    const pl = new THREE.Mesh(new THREE.PlaneGeometry(d.w, d.h), m); pl.position.set(d.x, d.y, d.z); pl.rotation.y = d.ry; pl.receiveShadow = true; g.add(pl);
  }
  // images posées à plat (un mot sur un comptoir, un dessin sur une couverture) : plaque horizontale juste au-dessus de la face
  for (const d of p.flats || []) {
    const t = dataTex(d);
    const m = d.emis > 0 ? new THREE.MeshBasicMaterial({ map: t, transparent: true, color: new THREE.Color().setScalar(Math.max(1, d.emis * 1.3)) }) : new THREE.MeshLambertMaterial({ map: t, transparent: true });
    const pl = new THREE.Mesh(new THREE.PlaneGeometry(d.w, d.d), m); pl.rotation.x = -Math.PI / 2; pl.position.set(d.x, d.y, d.z); pl.receiveShadow = true; g.add(pl);
  }
  // sols procéduraux : plaque horizontale (rangée 0 de la texture = z le plus grand), reçoit lumière et ombres
  for (const d of p.planes || []) {
    const pl = new THREE.Mesh(new THREE.PlaneGeometry(d.w, d.d), new THREE.MeshLambertMaterial({ map: dataTex(d) })); pl.rotation.x = -Math.PI / 2; pl.position.set(d.x, d.y, d.z); pl.receiveShadow = true; g.add(pl);
  }
  return { g };
};

// ------------------------------------------------------------------ accessoire : ciel dessiné en dôme (suit la caméra)
PROPS.bdome = (p) => {
  const g = new THREE.Group(); const tex = dataTex(p, { nearest: false });
  const m = new THREE.Mesh(new THREE.SphereGeometry(300, 64, 32), new THREE.MeshBasicMaterial({ map: tex, side: THREE.BackSide, depthWrite: false, fog: false, toneMapped: false }));
  m.renderOrder = -1000; m.frustumCulled = false; m.castShadow = false; const tmp = V();
  m.onBeforeRender = (renderer, scene, camera) => { if (m.parent) { tmp.copy(camera.position); m.parent.worldToLocal(tmp); m.position.copy(tmp); } };
  g.add(m); return { g };
};

// ------------------------------------------------------------------ météo de PIXEL 3D -> particules de VOXEL (approximations : voir BSet.limits)
const WEATHER = {
  rain: ['rain', { i: 1.5, col: 0xb8c8ff, size: 7, speed: 1 }], storm: ['rain', { i: 2.5, col: 0xa8b8e8, size: 7, speed: 1.4 }],
  snow: ['snow', { i: 1.3, col: 0xffffff, size: 7, speed: 1 }], blizzard: ['snow', { i: 2.8, col: 0xf0f4ff, size: 7, speed: 2.2 }],
  leaves: ['snow', { i: 0.6, col: 0xb8742a, size: 9, speed: 0.5 }], petals: ['snow', { i: 0.7, col: 0xf2a8c4, size: 8, speed: 0.45 }],
  fireflies: ['embers', { i: 0.5, col: 0xd8ff6a, size: 5, speed: 0.4 }], embers: ['embers', { i: 1.2, col: 0xff7a30, size: 7, speed: 1 }],
  ash: ['dust', { i: 1.5, col: 0x8c8c8c, size: 5, speed: 0.6 }], dust: ['dust', { i: 1.2, col: 0xc8b890, size: 5, speed: 0.4 }],
  bubbles: ['spark', { i: 0.9, col: 0xb8e8ff, den: 0.05, size: 0.03 }], sparkles: ['spark', { i: 1.4, col: 0xfff0a0, den: 0.07, size: 0.03 }],
};

// ------------------------------------------------------------------ mondes
export function buildBWorlds(ctx, wanted, base = V(12000, 0, 0), step = 600) {
  const { scene } = ctx; const W = []; let idx = 0;
  const mk = (name, build) => {
    if (!wanted.has(name)) { idx++; return; }
    const origin = base.clone().add(V(idx * step, 0, 0)); idx++; const w = build(origin); w.name = name; w.origin = origin; w.update = w.update || (() => {});
    const look0 = w.look; w.look = (S, T, E = {}) => { const En = normEnv(E); look0(S, T, En); grade(S, En); }; w.at = (x, y, z) => origin.clone().add(V(x, y, z)); W.push(w);
  };

  // ---- plateau : sol uni (couleur `floor`), ciel/fond uni (`bg`), lumière du jour ou d'intérieur réglable. Repère de A : x vers la droite, z vers la caméra, y en haut.
  mk('plateau', (origin) => {
    const g = new THREE.Group(); g.position.copy(origin); scene.add(g);
    const floorM = mat4(grunge(0xffffff, { size: 32, noise: 0.12, dark: 0.08, seed: 91 }), { rim: 0.15, wet: 0.3 });
    const floorG = new THREE.Group(); g.add(floorG);                  // le sol : à y = 0, ou à `env.floor_y` (lieu à niveaux : rue au pied des toits, ravin, rivière)
    new Batch().add({ x: 0, y: -0.1, z: 0, w: 600, h: 0.2, d: 600, mat: 'floor', tpm: 0.5 }).build({ floor: floorM }, floorG, { cast: false });
    const w = { group: g }; const doorGroups = {}; const dynGroups = {};
    w.look = (S, T, E = {}) => {
      S.sets = [w.name]; floorM.color.setHex(E.floor ?? 0x6a5a48); floorG.position.y = E.floor_y ?? 0;
      S.key = { dir: E.key_dir ?? [-0.3, 0.85, 0.5], color: E.key_col ?? 0xfff0dc, i: E.key ?? 1.1 };
      S.hemi = { sky: E.hemi_sky ?? 0xb8c0d8, ground: E.hemi_ground ?? 0x40382e, i: E.ambient ?? 0.9 };
      S.fill = { dir: [0.4, 0.3, 1], color: E.fill_col ?? 0x8090b0, i: E.fill ?? 0.25 };
      S.lights = []; S.rim = { color: E.rim_col ?? 0xffffff, i: E.rim ?? 0.06, pow: 5 }; S.edge = null;
      S.fog = { color: E.fog_col ?? E.bg ?? 0x20222c, d: E.fog ?? 0.008 }; S.bg = E.bg ?? 0x20222c; S.lift = E.lift ?? 0x101018;
      S.rain = null; S.spark = null;
      const wx = WEATHER[E.weather]; if (wx) { const o = { ...wx[1], i: wx[1].i * (E.weather_amount ?? 1) }; S[wx[0]] = o; }
      S.exposure = E.exposure ?? 1; S.bloom = E.bloom ?? 0.45; S.bloomThreshold = 0.9; S.bloomRadius = 0.5; S.contrast = E.contrast ?? 0.22; S.vignette = E.vignette ?? 0.45; S.sat = E.sat ?? 1.0; S.dofScale = 0.35; S.grain = 0.03;
      S.shadowC = origin.clone(); S.shadowS = E.shadow_s ?? 9;
    };
    // battants de porte animés : `stage.doors` = { id: { hinge: [x, z], w, h, th, color, yaw: [cap du battant par image] } } ; un groupe par plan, visible seulement pendant le plan
    w.doors = (st, T, FPS) => {
      for (const G of Object.values(doorGroups)) G.visible = false;
      if (!st.doors) return;
      let G = doorGroups[st.id];
      if (!G) {
        G = new THREE.Group(); g.add(G); doorGroups[st.id] = G; G.userData.leaves = {};
        for (const [id, d] of Object.entries(st.doors)) {
          const pivot = new THREE.Group(); pivot.position.set(d.hinge[0], 0, d.hinge[1]);
          pivot.add(vox([{ x: d.w / 2, y: d.h / 2, z: 0, w: d.w, h: d.h, d: d.th, color: hex(d.color, 0x60462f) }, { x: d.w - 0.12, y: d.h * 0.48, z: d.th * 0.9, w: 0.05, h: 0.05, d: 0.08, color: 0xb4aa8c }, { x: d.w - 0.12, y: d.h * 0.48, z: -d.th * 0.9, w: 0.05, h: 0.05, d: 0.08, color: 0xb4aa8c }], { rim: 0.3 }));
          G.add(pivot); G.userData.leaves[id] = pivot;
        }
      }
      G.visible = true; const k = Math.max(0, Math.round((T - st.t0) * FPS));
      for (const [id, d] of Object.entries(st.doors)) G.userData.leaves[id].rotation.y = d.yaw[Math.min(k, d.yaw.length - 1)];
    };
    // calque dynamique d'un plan (`stage.dyn`) : des boîtes qui changent à chaque image (éclair, débris et poussière d'un effondrement, hélicoptère, dragon), écrites par hstudio/voxelgpu/b_fx.py
    //   dyn = { frames: [ { b: [[x, y, z, w, h, d, couleur, émission, rx, ry, rz, opacité], ...], l: [[x, y, z, couleur, intensité, portée], ...] } | null, ... ] }, une entrée par image du plan (repère du monde)
    //   émission > 0 : peint sans ombrage (le bloom la fait rayonner) ; opacité < 1 : poussière translucide. Renvoie les lumières de l'image (le peintre garde les plus proches).
    w.dyn = (st, T, FPS) => {
      for (const G of Object.values(dynGroups)) G.visible = false;
      if (!st.dyn || !st.dyn.frames.length) return [];
      let G = dynGroups[st.id];
      if (!G) { G = new THREE.Group(); g.add(G); dynGroups[st.id] = G; G.userData = { k: -1, meshes: [], mats: {}, solid: vmat({ rim: 0.3, var: 0.08 }) }; }
      G.visible = true; const F = st.dyn.frames; const k = Math.max(0, Math.min(F.length - 1, Math.round((T - st.t0) * FPS)));
      if (k !== G.userData.k) {
        G.userData.k = k; for (const m of G.userData.meshes) { G.remove(m); m.geometry.dispose(); } G.userData.meshes = [];
        const fr = F[k]; const solid = [], glow = new Map(), alpha = new Map();
        for (const r of (fr && fr.b) || []) {
          const bb = { x: r[0], y: r[1], z: r[2], w: r[3], h: r[4], d: r[5], color: r[6], rx: r[8] || 0, ry: r[9] || 0, rz: r[10] || 0 };
          const em = r[7] || 0, op = r[11] ?? 1;
          if (op < 0.98) { const q = Math.max(1, Math.round(op * 5)) / 5; if (!alpha.has(q)) alpha.set(q, []); alpha.get(q).push(bb); }
          else if (em > 0) { const q = Math.round(em * 4) / 4; if (!glow.has(q)) glow.set(q, []); glow.get(q).push(bb); } else solid.push(bb);
        }
        const add = (list, mat, cast) => { const m = new THREE.Mesh(boxesGeometry(list), mat); m.castShadow = cast; m.receiveShadow = cast; m.frustumCulled = false; G.add(m); G.userData.meshes.push(m); };
        if (solid.length) add(solid, G.userData.solid, true);
        for (const [q, list] of glow) { const key = 'g' + q; const mt = G.userData.mats[key] || (G.userData.mats[key] = (() => { const m = new THREE.MeshBasicMaterial({ vertexColors: true }); m.color.setScalar(Math.max(1, q * 1.3)); return m; })()); add(list, mt, false); }
        for (const [q, list] of alpha) { const key = 'a' + q; const mt = G.userData.mats[key] || (G.userData.mats[key] = new THREE.MeshLambertMaterial({ vertexColors: true, transparent: true, opacity: q, depthWrite: false })); add(list, mt, false); }
      }
      const fr = F[k]; return ((fr && fr.l) || []).map((l) => ({ pos: w.at(l[0], l[1], l[2]), color: l[3], i: l[4], dist: l[5], decay: 1.4 }));
    };
    return w;
  });
  return W;
}
