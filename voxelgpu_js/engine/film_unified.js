// « Film » unifié : lit le contrat JSON écrit par Horror Studio (hstudio/voxelgpu) et peint avec le moteur voxel A.
// Horror Studio décide (régie, trajets, caméra, expressions, gestes, durées) ; ce module ne décide rien : il pose les
// personnages de A (chars4 / anim) aux positions du contrat, tend les bras vers les cibles de la régie, règle la lumière
// du plan (monde de A + ambiance de genre) et renvoie la caméra du contrat. Aucune horloge, aucun hasard : fonction pure de t.
import { buildWorlds, footprintTex } from './sets5.js';
import { CAST } from './cast4.js';
import { boxesGeometry } from './boxes.js';
import { buildHorrorWorlds, buildProps, buildFaceless, buildCreature, buildExtras, evalEnv, tv } from './horror_kit.js';
import { buildCiteWorlds } from './cite_kit.js';
import { buildBWorlds } from './b_kit.js';
import { buildAnimal, attachCastExtras } from './b_chars.js';
import { attachCostume } from './b_costumes.js';
import { attachHeld } from './b_objets.js';
import { floorPose } from './poses_floor.js';
import { buildArchetype } from './b_monsters.js';
import { buildKinetic, loadPixelFont, placeInFrame, layout as kinLayout } from './kinetic.js';
import { applyTheatre } from './theatre_kit.js';

export const format = 'portrait';
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x)), lerp = (a, b, k) => a + (b - a) * k, ease = (x) => { x = clamp(x); return x * x * (3 - 2 * x); };
const col = (v, d = 0xffffff) => (v == null ? d : typeof v === 'number' ? v : parseInt(String(v).replace('#', ''), 16));
const wrapA = (a) => { a = (a + Math.PI) % (2 * Math.PI); if (a < 0) a += 2 * Math.PI; return a - Math.PI; };

// ---------------------------------------------------------------- ambiances de genre (appliquées après la lumière du monde)
export const MOODS = {
  neutral: () => {},
  warm: (S, k, M) => { M.key(S, 0xffd0a0, k * 0.6); M.hemi(S, 0xffe0c8, 0x7a6048, k * 0.5); S.highTint = M.mix(S.highTint, 0xffe2c4, k); S.sat *= 1 + 0.08 * k; S.bloom += 0.15 * k; },
  comedy: (S, k) => { S.sat *= 1 + 0.25 * k; S.contrast = lerp(S.contrast, 0.1, k); S.bloom = lerp(S.bloom, 0.25, k); S.vignette = lerp(S.vignette, 0.18, k); S.grain = lerp(S.grain, 0.012, k); S.exposure *= 1 + 0.05 * k; },
  romance: (S, k, M) => { M.key(S, 0xffc8a0, k * 0.8); M.hemi(S, 0xffd8c8, 0x8a5a50, k * 0.7); M.fog(S, 0xf8d8d0, k * 0.6); S.bloom += 0.5 * k; S.bloomRadius = lerp(S.bloomRadius, 0.95, k); S.bloomThreshold = lerp(S.bloomThreshold, 0.7, k); S.sat *= 1 + 0.18 * k; S.vignette = lerp(S.vignette, 0.42, k); },
  drama: (S, k, M) => { S.sat *= 1 - 0.28 * k; S.contrast = lerp(S.contrast, 0.3, k); S.vignette = lerp(S.vignette, 0.52, k); S.hemi.i *= 1 - 0.25 * k; M.fog(S, 0x8a96a4, k * 0.5); S.shadowTint = M.mix(S.shadowTint, 0xb8c8e0, k); },
  adventure: (S, k, M) => { S.sat *= 1 + 0.2 * k; S.contrast = lerp(S.contrast, 0.22, k); M.key(S, 0xfff0c0, k * 0.5); S.bloom += 0.1 * k; },
  noir: (S, k, M) => { S.sat *= 1 - 0.85 * k; S.contrast = lerp(S.contrast, 0.5, k); S.vignette = lerp(S.vignette, 0.75, k); S.grain = lerp(S.grain, 0.07, k); M.key(S, 0xe8f0ff, k); S.key.i *= 1 + 0.6 * k; S.hemi.i *= 1 - 0.2 * k; S.exposure *= 1 + 0.25 * k; M.fog(S, 0x30383e, k); S.fog.d *= 1 + 0.8 * k; S.shadowTint = M.mix(S.shadowTint, 0x8090a0, k); },
  thriller: (S, k, M) => { M.key(S, 0xb0ffe0, k * 0.7); M.hemi(S, 0x5a9a8a, 0x1a2a28, k * 0.8); M.fog(S, 0x20403a, k * 0.8); S.fog.d *= 1 + 0.6 * k; S.rim = { color: 0x40ffc0, i: lerp(S.rim.i, 0.35, k), pow: 4 }; S.sat *= 1 - 0.2 * k; S.contrast = lerp(S.contrast, 0.32, k); S.vignette = lerp(S.vignette, 0.58, k); },
  horror: (S, k, M) => { M.fog(S, 0x200406, k); S.fog.d = lerp(S.fog.d, 0.035, k); M.hemi(S, 0xff3a2a, 0x1a0606, k); S.hemi.i = lerp(S.hemi.i, 0.35, k); M.key(S, 0xff6a50, k); S.key.i = lerp(S.key.i, 1.1, k); S.rim = { color: 0xff1a10, i: lerp(S.rim.i, 0.5, k), pow: 4 }; S.vignette = lerp(S.vignette, 0.62, k); S.grain = lerp(S.grain, 0.05, k); },
  scifi: (S, k, M) => { M.key(S, 0xa8d0ff, k * 0.7); M.hemi(S, 0x5a8aff, 0x1a2030, k * 0.6); S.rim = { color: 0x40d0ff, i: lerp(S.rim.i, 0.45, k), pow: 4 }; S.bloom += 0.5 * k; S.bloomThreshold = lerp(S.bloomThreshold, 0.7, k); S.sat *= 1 + 0.12 * k; S.contrast = lerp(S.contrast, 0.24, k); S.tint = M.mix(S.tint, 0xe8f4ff, k); },
  fantasy: (S, k, M) => { S.bloom += 0.7 * k; S.bloomRadius = lerp(S.bloomRadius, 1.0, k); S.sat *= 1 + 0.25 * k; S.rim = { color: 0xc8a0ff, i: lerp(S.rim.i, 0.3, k), pow: 4 }; S.tint = M.mix(S.tint, 0xf0e8ff, k); M.hemi(S, 0xc8b0ff, 0x4a3a60, k * 0.5); },
  western: (S, k, M) => { S.sat *= 1 - 0.18 * k; S.tint = M.mix(S.tint, 0xffe0b0, k); S.highTint = M.mix(S.highTint, 0xffd890, k); S.vignette = lerp(S.vignette, 0.5, k); M.fog(S, 0xd8b890, k * 0.7); S.grain = lerp(S.grain, 0.05, k); },
  dusk: (S, k, M) => { S.key.dir = [lerp(S.key.dir[0], -0.85, k), lerp(S.key.dir[1], 0.22, k), lerp(S.key.dir[2], -0.4, k)]; M.key(S, 0xff9050, k); M.hemi(S, 0x8a78c0, 0x3a2a30, k * 0.9); M.fog(S, 0xc89a90, k * 0.8); S.bg = M.mix(S.bg, 0xe0a080, k); S.tint = M.mix(S.tint, 0xffe0d0, k * 0.8); S.sat *= 1 + 0.12 * k; S.vignette = lerp(S.vignette, 0.45, k); },
  night: (S, k, M) => { M.key(S, 0x7a96ff, k); S.key.i = lerp(S.key.i, 0.55, k); M.hemi(S, 0x2a3a6a, 0x10141c, k); S.hemi.i = lerp(S.hemi.i, 0.8, k); S.exposure *= 1 + 0.3 * k; M.fog(S, 0x0a1020, k); S.fog.d *= 1 + 0.5 * k; S.bg = M.mix(S.bg, 0x060a14, k); S.lift = M.mix(S.lift, 0x02040a, k); S.sat *= 1 - 0.12 * k; S.bloom += 0.4 * k; S.vignette = lerp(S.vignette, 0.55, k); },
};
const helpers = (THREE) => {
  const mix = (a, b, k) => new THREE.Color(a).lerp(new THREE.Color(b), clamp(k)).getHex();
  return { mix, key: (S, c, k) => { S.key.color = mix(S.key.color, c, k); }, hemi: (S, sky, gnd, k) => { S.hemi.sky = mix(S.hemi.sky, sky, k); S.hemi.ground = mix(S.hemi.ground, gnd, k); }, fog: (S, c, k) => { S.fog.color = mix(S.fog.color, c, k); } };
};
// réglages numériques libres d'un plan (liste blanche) : "look": { "exposure": 1.1, "fog_d": 0.02, "tint": "#ffeedd", ... }
const LOOK_KEYS = { exposure: 'n', bloom: 'n', bloomRadius: 'n', bloomThreshold: 'n', sat: 'n', contrast: 'n', vignette: 'n', grain: 'n', ca: 'n', mblur: 'n', dofScale: 'n', tint: 'c', shadowTint: 'c', highTint: 'c', lift: 'c', bg: 'c' };

// ---------------------------------------------------------------- personnages (A) : modèles de base + retouches du contrat
const SK = [0xf0a874, 0xc88a5a, 0x8a5a3a, 0xf2c4a0, 0x6a4028, 0xe8b088];
const HAIR = [{ style: 'curly', color: 0x1a1210, color2: 0x2a1a14 }, { style: 'long', color: 0xc8a050, color2: 0xd8b060 }, { style: 'curly', color: 0x5a3a20, color2: 0x6a4a2a }, { style: 'long', color: 0x1a1a1a, color2: 0x2a2a2a }, { style: 'curly', color: 0x8a4a20, color2: 0x9a5a2a }];
const TOPS = [0x3a6ab0, 0x2a8a5a, 0xd8a03a, 0x6a3a8a, 0xc84a3a, 0x4a4a52, 0xe8e4dc, 0x2a2a30];
function baseSpec(def, idx) {
  const p = def.preset || 'npc', v = def.variant ?? idx;
  if (p === 'noe') return { ...CAST.noe, top: { type: 'jacketOpen', color: 0x8a8890, shirt: 0x1a1a1e } };
  if (p === 'lina') return { ...CAST.lina, hat: null, top: { type: 'jacketOpen', color: 0x8a1a24, shirt: 0xf2eee8 } };
  if (p === 'alien') return { skin: 0x7ac46a, brow: 0x3a6a2a, iris: 0x050505, hair: null, top: { type: 'leather', color: 0xb8c0c8 }, pants: { color: 0x9aa0a8 }, shoes: { type: 'boot', color: 0x6a7078 } };
  return { skin: SK[v % SK.length], brow: 0x2a1810, hair: HAIR[v % HAIR.length], top: { type: v % 3 ? 'hoodie' : 'jacketOpen', color: TOPS[v % TOPS.length], shirt: 0x1a1a1e }, pants: { color: [0x2a3a5a, 0x2a2a30, 0x5a4a3a, 0x3a3a42][v % 4] }, shoes: { type: 'sneaker', color: [0x1a1a1e, 0xe8e8e8, 0x8a2a2a][v % 3], sole: 0xf0f0ee } };
}
function reviveSpec(o) { // retouches du contrat : couleurs "#rrggbb" -> entiers
  if (Array.isArray(o)) return o.map(reviveSpec);
  if (o && typeof o === 'object') { const r = {}; for (const [k, v] of Object.entries(o)) r[k] = (/^(color|color2|skin|brow|iris|shirt|sole|fur|hood)$/.test(k) && typeof v === 'string') ? col(v) : reviveSpec(v); return r; }
  return o;
}

export async function setup(ctx) {
  const { THREE, V, buildCharacter4, anim, scene, contract: C } = ctx; const M = helpers(THREE);
  const HORROR = new Set(['station', 'bus', 'toit', 'talus']); const wantH = new Set(C.stages.map((s) => s.world).filter((n) => HORROR.has(n)));
  const CITE = new Set(['cite', 'astroport', 'selene']); const wantC = new Set(C.stages.map((s) => s.world).filter((n) => CITE.has(n)));
  const BKIT = new Set(['plateau']); const wantB = new Set(C.stages.map((s) => s.world).filter((n) => BKIT.has(n)));
  const worlds = [...buildWorlds(ctx), ...buildHorrorWorlds(ctx, wantH), ...buildCiteWorlds(ctx, wantC), ...buildBWorlds(ctx, wantB)]; const byName = Object.fromEntries(worlds.map((w) => [w.name, w])); globalThis.__worlds = byName;   // outil tools/dump_world_boxes.js : lit la géométrie des mondes pour le style PS1
  const FPS = C.fps || 24;
  // ---- mots 3D d'un clip musical (contrat `words`, hstudio/voxelgpu/contract.py clean_words) : cubes posés DANS la scène (kinetic.js), peints par VOXEL seulement.
  // Un mot appartient au plan où il COMMENCE (il disparaît à la coupe) ; sans la clé, rien n'est chargé ni dessiné.
  const WORDS = C.words || []; let kin = null; const MIRRORED = !!C.mirror;
  if (WORDS.length) { await loadPixelFont('./assets/pixelfont.json'); kin = buildKinetic(scene, { pool: clamp(WORDS.length, 1, 24) }); }
  globalThis.HS_FACE_LEGACY = C.face_style === 'legacy'; globalThis.HS_MIRROR = !!C.mirror;       // `mirror` : image 3D retournée par main_unified.js ; les textes dessinés ici (labelTex) sont écrits à l'envers pour se relire
  globalThis.HS_RELIEF_K = C.relief_k ?? 0; globalThis.HS_FACE_MICRO = C.face_micro ?? false;   // visage « naturel » par défaut ; 'legacy' (HSTUDIO_FACE_LEGACY=1) = rendu d'avant à l'identique

  // ---- casting
  const ids = Object.keys(C.casts || {}); const chars = {}; const acc = {}; const extras = {};
  ids.forEach((id, i) => {
    const def = C.casts[id]; const spec = { ...baseSpec(def, i), ...reviveSpec(def.look || {}) };
    const sd = def.seed ?? (def.preset === 'noe' ? 1 : def.preset === 'lina' ? 2 : 30 + i);
    const ch = def.kind === 'animal' ? buildAnimal(buildCharacter4, def, sd) : def.archetype ? buildArchetype(buildCharacter4, def, sd) : def.kind === 'faceless' ? buildFaceless(buildCharacter4, { ...spec, hair: null, hood: col(def.hood, 0x1a1d24) }, sd) : def.kind === 'creature' ? buildCreature(buildCharacter4, { ...def.creature, skin: col(def.skin, 0xe9d8c0) }, sd) : buildCharacter4(spec, sd);
    if (def.stretch) ch.stretch = def.stretch; if (def.head_scale) ch.headScale = def.head_scale; ch.baseScale = def.scale ?? (def.preset === 'lina' ? 0.95 : def.preset === 'alien' ? 1.05 : 0.94 + (i % 4) * 0.03);
    if (def.face && !def.kind) ch.face.extra = def.face; else if (def.kind) { /* faceless / creature : visage peint par le kit */ } else if (def.preset === 'alien') ch.face.extra = { iris: 1.75, brow: 0 };
    scene.add(ch.root); chars[id] = ch; acc[id] = []; extras[id] = buildExtras(ch, def.extras || []); attachCastExtras(ch, def);
    if (def.costume) attachCostume(ch, def, sd, id);            // costumes XVIIIe (contrat `costume`, b_costumes.js) ; absent = rien
    if (def.held) attachHeld(ch, def);                          // objets détaillés tenus en main, image par image (contrat `held`, b_objets.js) ; absent = rien
    const vm = new THREE.MeshLambertMaterial({ vertexColors: true });
    const prop = (boxes) => { const m = new THREE.Mesh(boxesGeometry(boxes), vm); m.castShadow = true; m.visible = false; return m; };
    for (const a of def.accessories || []) {
      if (a === 'umbrella') { const cc = col(def.umbrella_color, 0x2a2a30); const B = [{ x: 0, y: -0.05, z: 0.05, w: 0.04, h: 1.0, d: 0.04, color: 0x2a2a2a }];
        for (let k = 0; k < 8; k++) { const an = k / 8 * 6.283; B.push({ x: Math.cos(an) * 0.32, y: -0.58 + 0.06, z: 0.05 + Math.sin(an) * 0.32, w: 0.5, h: 0.06, d: 0.5, color: cc, ry: -an }); } B.push({ x: 0, y: -0.48, z: 0.05, w: 0.7, h: 0.1, d: 0.7, color: cc });
        const m = prop(B); m.rotation.x = Math.PI; ch.handR.add(m); acc[id].push(m); }
      if (a === 'sword') { const m = prop([{ x: 0, y: -0.45, z: 0, w: 0.05, h: 0.8, d: 0.1, color: 0xd8dce4 }, { x: 0, y: -0.04, z: 0, w: 0.06, h: 0.06, d: 0.32, color: 0x6a4a2a }, { x: 0, y: 0.06, z: 0, w: 0.05, h: 0.16, d: 0.05, color: 0x3a2a1a }]); m.position.set(0, -0.15, 0.05); ch.handR.add(m); acc[id].push(m); }
      if (a === 'shield') { const cc = col(def.shield_color, 0x2a4ac0); const m = prop([{ x: 0.07, y: -0.1, z: 0, w: 0.06, h: 0.6, d: 0.5, color: cc }, { x: 0.1, y: -0.1, z: 0, w: 0.04, h: 0.2, d: 0.2, color: 0xe8c040 }]); ch.handL.add(m); acc[id].push(m); }
      if (a === 'helmet') { const m = prop([{ x: 0, y: 0.31, z: 0, w: 0.56, h: 0.14, d: 0.56, color: 0x9aa0a8 }, { x: 0, y: 0.12, z: -0.27, w: 0.56, h: 0.4, d: 0.06, color: 0x8a9098 }, { x: 0, y: 0.42, z: 0, w: 0.08, h: 0.12, d: 0.4, color: 0xc02a2a }]); m.position.y = 4 / 16; ch.neck.add(m); acc[id].push(m); }
    }
  });

  // ---- empreintes de pas : une par talon posé (événements calculés par la régie), réservoir de décalques par monde
  const fpTex = footprintTex(); const printsPool = {};
  for (const st of C.stages) if (st.prints && !printsPool[st.id]) {
    const w = byName[st.world]; const m = new THREE.MeshLambertMaterial({ map: fpTex, color: col(st.prints.color, 0x2a2a2a), transparent: true, opacity: st.prints.opacity ?? 0.8, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2 });
    printsPool[st.id] = Array.from({ length: 44 }, () => { const d = new THREE.Mesh(new THREE.PlaneGeometry(0.34, 0.5), m); d.rotation.order = 'XYZ'; d.rotation.x = -Math.PI / 2; d.visible = false; d.receiveShadow = true; w.group.add(d); return d; });
  }

  for (const st of C.stages) if (st.props_ref && !st.props) st.props = C.prop_sets[st.props_ref];      // décors d'un lieu lourd écrits une seule fois dans le contrat (`prop_sets`)
  const propCache = {}; const stageProps = {}; for (const st of C.stages) if (st.props && st.props.length) { const key = st.world + (st.props_ref ? '#' + st.props_ref : JSON.stringify(st.props)); stageProps[st.id] = propCache[key] || (propCache[key] = buildProps(st.props, byName[st.world].group)); stageProps[st.id].key = key; }

  // ---- lecture du contrat
  const cols = C.actor_cols; const ci = Object.fromEntries(cols.map((n, i) => [n, i]));
  const sample = (arr, t, st) => { // interpolation entre deux images du contrat (colonnes continues) ; discrètes : image la plus proche
    const x = clamp((t - st.t0) * FPS, 0, arr.length - 1), i0 = Math.floor(x), i1 = Math.min(arr.length - 1, i0 + 1), a = x - i0; const A = arr[i0], B = arr[i1]; if (a < 1e-6 || A === B) return A;
    const o = A.slice(); for (let j = 0; j < o.length; j++) { const n = cols[j]; if (n === 'vis' || n === 'expr' || n === 'gait' || n === 'handp' || n === 'handn' || n === 'seat_h') { o[j] = a < 0.5 ? A[j] : B[j]; } else if (n === 'yaw') o[j] = A[j] + wrapA(B[j] - A[j]) * a; else o[j] = lerp(A[j], B[j], a); } return o;
  };
  const camAt = (st, t) => { const x = clamp((t - st.t0) * FPS, 0, st.camera.length - 1), i0 = Math.floor(x), i1 = Math.min(st.camera.length - 1, i0 + 1), a = x - i0; const A = st.camera[i0], B = st.camera[i1]; const g = (j) => lerp(A[j], B[j], a);
    return { pos: [g(0), g(1), g(2)], look: [g(3), g(4), g(5)], fov: g(6), roll: g(7) }; };
  const HAND = ['relaxed', 'fist', 'open', 'point', 'grip'];
  const EXPR = C.expressions || ['neutral'];
  const K_ARM = 0.57 / 0.60;   // bras de A (4 + 5,05 px) / bras du squelette de B
  const _v = V();

  function arms(ch, f, yaw, w, T) {
    if (w < 0.03) { const hp0 = HAND[f[ci.handp] | 0], hn0 = HAND[f[ci.handn] | 0]; if (hp0 && hp0 !== 'relaxed') ch.setHand('L', hp0); if (hn0 && hn0 !== 'relaxed') ch.setHand('R', hn0); return; }
    const c = Math.cos(yaw), s = Math.sin(yaw), sc = ch.root.scale.x * K_ARM;
    for (const [side, p] of [['L', 'p'], ['R', 'n']]) {
      const sh = side === 'L' ? ch.shL : ch.shR, hand = side === 'L' ? ch.handL : ch.handR;
      ch.root.updateMatrixWorld(true);
      const shW = sh.getWorldPosition(V()), cur = hand.getWorldPosition(V());
      const h = [f[ci['h' + p + 'x']], f[ci['h' + p + 'y']], f[ci['h' + p + 'z']]], e = [f[ci['e' + p + 'x']], f[ci['e' + p + 'y']], f[ci['e' + p + 'z']]];
      const want = shW.clone().add(V(h[0] * c + h[2] * s, h[1], -h[0] * s + h[2] * c).multiplyScalar(sc));
      const tgt = cur.lerp(want, ease(w));
      anim.reach(ch, side, tgt, V(e[0], e[1], e[2]));
      if (side === 'L') ch._lockL = true; else ch._lockR = true;
      const hp = HAND[f[ci['hand' + p]] | 0]; if (hp && hp !== 'relaxed') ch.setHand(side, hp);
    }
  }
  // contacts : la main se pose EXACTEMENT sur un point du monde (vitre, porte, lampe sur le comptoir...) ; calculées par hstudio/voxelgpu/blocking.py,
  // clés [T absolu, x, y, z, poids] dans le repère local du monde. Rien n'est inventé ici : avant la première clé et après la dernière, la main reste à la pose normale.
  function applyContacts(ch, id, st, T) {
    for (const c of st.contacts || []) {
      if (c.who !== id) continue; const k = c.keys; if (!k.length || T < k[0][0] || T > k[k.length - 1][0]) continue;
      let j = 0; while (j < k.length - 2 && T > k[j + 1][0]) j++;
      const a = k[j], b = k[j + 1], u = clamp((T - a[0]) / Math.max(1e-6, b[0] - a[0]), 0, 1), w = lerp(a[4], b[4], u); if (w < 0.01) continue;
      const P = st.W.at(lerp(a[1], b[1], u), lerp(a[2], b[2], u), lerp(a[3], b[3], u));
      ch.root.updateMatrixWorld(true); const hand = c.hand === 'L' ? ch.handL : ch.handR; const cur = hand.getWorldPosition(V());
      anim.reach(ch, c.hand, cur.lerp(P, ease(w)), null); if (c.hand === 'L') ch._lockL = true; else ch._lockR = true;
      ch.setHand(c.hand, c.pose || 'grip');
    }
  }
  // couche visage : une ligne par image et par personnage (contrat : face_cols), lue telle quelle
  const FCOLS = C.face_cols || []; const fi = Object.fromEntries(FCOLS.map((n, i) => [n, i]));
  function applyFace(ch, id, st, T) {
    const rows = st.faces && st.faces[id]; if (!rows || !rows.length) { if (ch.face) ch.face.layer = null; return; }
    const x = clamp((T - st.t0) * FPS, 0, rows.length - 1), i0 = Math.floor(x), i1 = Math.min(rows.length - 1, i0 + 1), a = x - i0, A = rows[i0], B = rows[i1], g = (n) => lerp(A[fi[n]], B[fi[n]], a);
    ch.face.layer = { lx: g('lx'), ly: g('ly'), blink: g('blink'), bdi: g('bdi'), bdo: g('bdo'), mo: g('mo'), ms: g('ms'), tilt: g('tilt'), e1: EXPR[A[fi.e1] | 0], i1: g('i1'), e2: EXPR[A[fi.e2] | 0], i2: g('i2') };
  }
  // apparition / disparition dans le vide (clé `dissolve` d'un acteur de PIXEL 3D) : les cubes du corps s'éteignent un par un ; les visages (autre matériau) se fondent
  function setDissolve(ch, d) {
    if (!ch._dm) { ch._dm = []; ch.root.traverse((o) => { if (o.isMesh) for (const m of (Array.isArray(o.material) ? o.material : [o.material])) if (m && m.visible !== false) ch._dm.push([o, m]); }); }
    for (const [o, m] of ch._dm) {
      if (m.userData.vox) m.userData.vox.uDiss.value = d;
      else { if (m.userData._o0 === undefined) m.userData._o0 = [m.opacity, m.transparent]; m.transparent = d > 0 || m.userData._o0[1]; m.opacity = m.userData._o0[0] * (1 - d); }
      o.castShadow = d < 0.4 ? (o.userData._cs ?? (o.userData._cs = o.castShadow)) : false;
    }
  }
  function perform(id, st, T) {
    const ch = chars[id], arr = st.actors[id]; if (!arr) return null;
    const f = sample(arr, T, st); if (!f[ci.vis]) return null;
    const P = st.W.at(f[ci.x], f[ci.y], f[ci.z]), yaw = f[ci.yaw];
    anim.put(ch, P.x, P.z, yaw, () => P.y); ch.root.visible = true;
    { const dt = st.dissolve_tracks && st.dissolve_tracks[id]; const dd = dt ? dt[clamp(Math.round((T - st.t0) * FPS), 0, dt.length - 1)] : 0; if (dt || ch._dm) setDissolve(ch, dd || 0); }
    const gait = f[ci.gait], amp = f[ci.amp], sit = f[ci.sit], cr = f[ci.crouch], air = f[ci.air]; ch._gait = gait; ch._phase = f[ci.phase];     // lus par les animaux (b_chars.js) pour choisir leur pose de marche
    if (sit > 0.02) { anim.sit(ch, sit, f[ci.seat_h]); anim.breathe(ch, T, 1 - sit * 0.6); }
    else if (cr > 0.02) { anim.crouch(ch, cr); }
    else if (gait === 2) anim.run(ch, f[ci.phase], amp);
    else if (gait === 1) anim.walk(ch, f[ci.phase], amp);
    else anim.breathe(ch, T);
    const fp = st.poses && st.poses[id]; if (fp) floorPose(ch, fp, clamp(Math.round((T - st.t0) * FPS), 0, 1e6));     // à genoux / assis par terre (contrat `poses`, scènes dirigées) ; absent = rien
    if (air > 0.05) { const m = air; ch.shL.rotation.x += -2.0 * m; ch.shR.rotation.x += -2.0 * m; anim.pose(ch, 'armsOpen', 0.3 * m); }
    ch.torso.rotation.x += f[ci.lean] * 0.8;
    arms(ch, f, yaw, f[ci.armw], T); applyContacts(ch, id, st, T);
    ch.neck.rotation.y += clamp(f[ci.hyaw], -1.1, 1.1); ch.neck.rotation.x += -clamp(f[ci.hpit], -0.6, 0.6);
    ch.setExpr(EXPR[f[ci.expr] | 0] || 'neutral'); ch.face.talk = f[ci.talk]; applyFace(ch, id, st, T);
    if (gait === 0 && sit <= 0.02 && cr <= 0.02 && air <= 0.05 && !(fp && ch.hips.position.y < ch.hipY - 1e-4)) anim.ground(ch);
    if (ch.stretch) { const b = ch.baseScale, st = ch.stretch, hs = ch.headScale ?? 1; ch.root.scale.set(b * st[0], b * st[1], b * st[2]); ch.neck.scale.set(hs / st[0], hs / st[1], hs / st[0]); }
    for (const m of acc[id]) m.visible = true;
    if (ch.costumeUpdate) ch.costumeUpdate(st, id, T, f, FPS, ci);           // jupe (évasement, jambes), basques, voile, accessoires : après la pose des jambes
    if (ch.heldTrack) ch.heldTrack(st, id, T, FPS);                           // objet détaillé tenu à cette image (`stage.held`)
    return P;
  }

  // ---- plans
  const shots = C.stages.map((st, i) => {
    const w = byName[st.world]; if (!w) throw new Error(`monde inconnu : ${st.world}`); st.W = w;
    const fxAt = (T, S) => { for (const e of C.fx || []) { if (T < e.t0 || T > e.t1) continue; const k = (T - e.t0) / Math.max(1e-6, e.t1 - e.t0);
      if (e.type === 'fade') S.fade = Math.min(S.fade, lerp(e.from ?? 0, e.to ?? 1, ease(k))); else if (e.type === 'flash') { S.flash = Math.max(S.flash, lerp(e.from ?? 0, e.to ?? 1, ease(k)) * (e.peak ?? 1)); S.flashCol = col(e.color, 0xffffff); if (e.exposure) S.exposure += e.exposure * S.flash; }
      else if (e.type === 'shake') S.shake = Math.max(S.shake, (e.amount ?? 0.5) * Math.sin(Math.PI * k)); else if (e.type === 'bars') S.bars = e.amount ?? 0.1; } };
    const camera = (T) => { const c = camAt(st, T); return { pos: w.at(...c.pos), look: w.at(...c.look), fov: c.fov, roll: c.roll }; };
    const place = (T) => { for (const id of ids) { const ch = chars[id]; if (st.actors[id]) perform(id, st, T); } };
    const drawWords = (shot, T) => {
      const last = shot === shots[shots.length - 1], items = [];
      WORDS.forEach((wd, idx) => {
        if (wd.t0 < shot.t0 - 1e-6 || (wd.t0 >= shot.t1 - 1e-6 && !last)) return;
        const cam = camera(wd.lock === 'world' ? wd.t0 : T), dist = wd.dist ?? 3.2;                      // `frame` : suit la caméra ; `world` : reste là où la caméra la voyait à l'instant t0
        const asp = ctx.aspect, frameW = 2 * Math.tan((cam.fov ?? 50) * Math.PI / 360) * asp * dist; let size = wd.size ?? 0.5;
        const wm = kinLayout(wd.text, wd.tracking ?? 1).width * size / 7, mx = (wd.maxw ?? 0.82) * frameW; if (wm > mx) size *= mx / wm;      // jamais plus large que le cadre
        const nx = wd.ndc ? wd.ndc[0] : 0, ny = wd.ndc ? wd.ndc[1] : 0, sg = MIRRORED ? -1 : 1;           // image retournée (`mirror`) : position, tilt et lettres sont inversés d'avance
        const pl = placeInFrame(cam, asp, sg * nx, ny, dist, { yaw: sg * (wd.yaw ?? 0), pitch: wd.pitch ?? 0, roll: sg * (wd.roll ?? 0) });
        items.push({ text: wd.text, t0: wd.t0, t1: wd.t1, pos: pl.pos, rot: pl.rot, order: pl.order, size, color: col(wd.color, 0xf4ead8), glow: wd.glow, inStyle: wd.in, outStyle: wd.out, seed: wd.seed ?? idx, tracking: wd.tracking, stagger: wd.stagger, float: wd.float, align: wd.align });
      });
      kin.update(T, items);
      if (MIRRORED) for (const w of kin.words) if (w.g.visible) w.g.scale.x = -Math.abs(w.g.scale.x);
    };
    return {
      name: `${i}_${st.id}`, t0: st.t0, t1: st.t1 + (st.tail || 0), dissolve: st.dissolve || 0,
      cam: (lt, u, T) => { place(T); return camera(T); },
      fn: (lt, u, T, S, shot) => {
        const E = evalEnv(st.env, T); w.look(S, T, E); S.sets = [w.name];
        const mine = stageProps[st.id]; for (const pr of Object.values(propCache)) pr.group.visible = pr === mine; if (mine) mine.update(T);
        if (w.doors) w.doors(st, T, FPS);              // battants de porte animés du monde `plateau` (b_kit.js)
        if (w.dyn) for (const l of w.dyn(st, T, FPS)) S.lights.push(l);      // calque dynamique du plan (éclair, débris, hélicoptère, dragon : b_fx.py) et ses lumières
        for (const id of ids) extras[id].update(T);
        for (const id of ids) { const hl = chars[id].heldLights; if (hl && chars[id].root.visible) { chars[id].heldUpdate(); for (const l of hl) S.lights.push({ pos: l.obj.getWorldPosition(V()), color: l.color, i: l.i, dist: l.dist, decay: 1.4 }); } }      // lumières tenues (lampe torche, bougie, torche, bâton)
        for (const lt of st.lights || []) S.lights.push({ pos: w.at(...lt.at), color: col(lt.color, 0xffffff), i: tv(lt.i ?? 3, T), dist: lt.dist ?? 8, decay: lt.decay ?? 1.4 });
        const hlp = M; const mood = st.mood; const list = Array.isArray(mood) ? mood : mood ? [[mood, 1]] : [];
        for (const m of list) { const [name, k] = Array.isArray(m) ? m : [m, 1]; if (MOODS[name]) MOODS[name](S, k, hlp); else throw new Error(`ambiance inconnue : ${name}`); }
        for (const [k, v] of Object.entries(st.look || {})) { const key = k.replace(/_(.)/g, (_, c) => c.toUpperCase()); if (key === 'fogD') S.fog.d = v; else if (key === 'fogColor') S.fog.color = col(v); else if (key === 'keyI') S.key.i = v; else if (key === 'hemiI') S.hemi.i = v; else if (key === 'keyColor') S.key.color = col(v); else if (LOOK_KEYS[key] === 'n') S[key] = v; else if (LOOK_KEYS[key] === 'c') S[key] = col(v); }
        const fa = st.focus_actor && chars[st.focus_actor] && chars[st.focus_actor].root.visible ? chars[st.focus_actor].root.position.clone() : null;
        const c = camera(T); S.shadowC = (fa || c.look).clone(); S.shadowS = st.shadow_s ?? 14;
        S.focus = Math.max(1, c.pos.distanceTo(c.look)); S.dofScale = st.dof ?? 0.35; S.mblur = st.mblur ?? 0.15;
        if (w.reflectY !== undefined) S.reflect = { y: w.origin.y + w.reflectY };
        const pool = printsPool[st.id];
        if (pool) { let n = 0; const pr = st.prints; const stp = (st.steps && st.steps[pr.actor]) || [];
          for (let j = Math.max(0, stp.length - 44); j < stp.length; j++) { const [ts, x, z, hd, side] = stp[j]; if (ts > T + 1e-6 || n >= pool.length) continue; const wp = w.at(x, 0, z); const d = pool[n++]; d.visible = true;
            const fx = Math.sin(hd), fz = Math.cos(hd), rx = Math.cos(hd), rz = -Math.sin(hd); d.position.set(wp.x - w.origin.x + fx * 0.24 + rx * side * 0.128, (pr.y ?? 0) + 0.006, wp.z - w.origin.z + fz * 0.24 + rz * side * 0.128); d.rotation.z = hd + Math.PI; }
          for (; n < pool.length; n++) pool[n].visible = false; }
        const gp = (spec, ch0) => { if (Array.isArray(spec)) return w.at(...spec); const a = chars[spec.on]; const base = a && a.root.visible ? a.root.position.clone() : w.at(0, 0, 0); const yaw = a ? a.root.rotation.y : 0; return base.add(V(Math.sin(yaw) * (spec.fwd || 0) + (spec.dx || 0), (spec.h ?? 1.2) + (spec.dy || 0), Math.cos(yaw) * (spec.fwd || 0) + (spec.dz || 0))); };
        S.spots = (st.spots || []).map((sp) => ({ pos: gp(sp.from), target: gp(sp.to), color: col(sp.color, 0xfff0d0), i: tv(sp.i ?? 30, T), angle: sp.angle ?? 0.42, pen: sp.pen ?? 0.55, dist: sp.dist ?? 14 }));
        if (st.shake) S.shake = Math.max(S.shake, tv(st.shake, T));
        if (st.theatre) applyTheatre(st, T, S, FPS, w, mine, c);       // théâtre : lumière de scène de l'image (theatre_kit.js) ; aucun autre plan n'a la clé
        fxAt(T, S);
        if (kin) drawWords(shot, T);
      },
    };
  });
  for (let i = 0; i < shots.length - 1; i++) shots[i].t1 = shots[i + 1].t0; shots[shots.length - 1].t1 = C.duration;
  const sets = {}; worlds.forEach((w) => { sets[w.name] = { group: w.group, update: (t) => w.update(t) }; });
  return {
    shots, duration: C.duration, sets,
    reset: () => { if (kin) kin.hideAll(); for (const id of ids) { const a = chars[id]; a.reset(); a.root.visible = false; a.root.position.set(0, -500, 0); for (const m of acc[id]) m.visible = false; } },
    post: (t) => { for (const id of ids) { const a = chars[id]; if (a.root.visible) { anim.relaxArms(a); if (a.faceUpdate) a.faceUpdate(t); } } },
  };
}
