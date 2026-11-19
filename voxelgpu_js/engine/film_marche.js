// « La marche » — 1 min, vertical, sans dialogue. Noé marche vers un but qu'on ne connaît pas ; autour de lui
// les mondes et les époques défilent en fondus enchaînés (ville au matin, parc, automne, pluie, glacier, feu,
// bataille, invasion, vaisseau, Lune). Des gens apparaissent à côté de lui puis disparaissent.
import { buildWorlds, footprintTex } from './sets5.js';
import { CAST } from './cast4.js';
import { boxesGeometry } from './boxes.js';

export const format = 'portrait';
export async function setup(ctx) {
  const { THREE, V, buildCharacter4, anim, scene } = ctx;
  const worlds = buildWorlds(ctx);
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x)), lerp = (a, b, k) => a + (b - a) * k, ease = (x) => { x = clamp(x); return x * x * (3 - 2 * x); };
  // ---- personnages
  const noe = buildCharacter4({ ...CAST.noe, top: { type: 'jacketOpen', color: 0x8a8890, shirt: 0x1a1a1e } }, 1); scene.add(noe.root);
  const lina = buildCharacter4({ ...CAST.lina, hat: null, top: { type: 'jacketOpen', color: 0x8a1a24, shirt: 0xf2eee8 } }, 2); lina.baseScale = 0.95; scene.add(lina.root);
  const SK = [0xf0a874, 0xc88a5a, 0x8a5a3a, 0xf2c4a0, 0x6a4028, 0xe8b088];
  const HAIR = [{ style: 'curly', color: 0x1a1210, color2: 0x2a1a14 }, { style: 'long', color: 0xc8a050, color2: 0xd8b060 }, { style: 'curly', color: 0x5a3a20, color2: 0x6a4a2a }, { style: 'long', color: 0x1a1a1a, color2: 0x2a2a2a }, { style: 'curly', color: 0x8a4a20, color2: 0x9a5a2a }];
  const TOPS = [0x3a6ab0, 0x2a8a5a, 0xd8a03a, 0x6a3a8a, 0xc84a3a, 0x4a4a52, 0xe8e4dc, 0x2a2a30];
  const npc = []; for (let i = 0; i < 10; i++) { const c = buildCharacter4({ skin: SK[i % SK.length], brow: 0x2a1810, hair: HAIR[i % HAIR.length], top: { type: i % 3 ? 'hoodie' : 'jacketOpen', color: TOPS[i % TOPS.length], shirt: 0x1a1a1e }, pants: { color: [0x2a3a5a, 0x2a2a30, 0x5a4a3a, 0x3a3a42][i % 4] }, shoes: { type: 'sneaker', color: [0x1a1a1e, 0xe8e8e8, 0x8a2a2a][i % 3], sole: 0xf0f0ee } }, 30 + i); c.baseScale = 0.94 + (i % 4) * 0.03; scene.add(c.root); npc.push(c); }
  const aliens = []; for (let i = 0; i < 3; i++) { const a = buildCharacter4({ skin: 0x7ac46a, brow: 0x3a6a2a, iris: 0x050505, hair: null, top: { type: 'leather', color: 0xb8c0c8 }, pants: { color: 0x9aa0a8 }, shoes: { type: 'boot', color: 0x6a7078 } }, 60 + i); a.baseScale = 1.05; a.face.extra = { iris: 1.75, brow: 0 }; scene.add(a.root); aliens.push(a); }
  // accessoires : parapluies, épées, boucliers (accrochés aux mains)
  const vm = new THREE.MeshLambertMaterial({ vertexColors: true });
  const prop = (boxes) => { const m = new THREE.Mesh(boxesGeometry(boxes), vm); m.castShadow = true; m.visible = false; return m; };
  const umb = npc.slice(0, 3).map((c, i) => { const col = [0x2a2a30, 0xc83a3a, 0x3a6ac8][i]; const B = [{ x: 0, y: -0.05, z: 0.05, w: 0.04, h: 1.0, d: 0.04, color: 0x2a2a2a }];
    for (let k = 0; k < 8; k++) { const a = k / 8 * 6.283; B.push({ x: Math.cos(a) * 0.32, y: -0.58 + 0.06, z: 0.05 + Math.sin(a) * 0.32, w: 0.5, h: 0.06, d: 0.5, color: col, ry: -a }); } B.push({ x: 0, y: -0.48, z: 0.05, w: 0.7, h: 0.1, d: 0.7, color: col });
    const m = prop(B); m.rotation.x = Math.PI; c.handR.add(m); return m; });
  const swords = npc.slice(3, 9).map((c) => { const m = prop([{ x: 0, y: -0.45, z: 0, w: 0.05, h: 0.8, d: 0.1, color: 0xd8dce4 }, { x: 0, y: -0.04, z: 0, w: 0.06, h: 0.06, d: 0.32, color: 0x6a4a2a }, { x: 0, y: 0.06, z: 0, w: 0.05, h: 0.16, d: 0.05, color: 0x3a2a1a }]); m.position.set(0, -0.15, 0.05); c.handR.add(m); return m; });
  const shields = npc.slice(3, 9).map((c, i) => { const col = i % 2 ? 0xc02a2a : 0x2a4ac0; const m = prop([{ x: 0.07, y: -0.1, z: 0, w: 0.06, h: 0.6, d: 0.5, color: col }, { x: 0.1, y: -0.1, z: 0, w: 0.04, h: 0.2, d: 0.2, color: 0xe8c040 }]); c.handL.add(m); return m; });
  const helmets = npc.slice(3, 9).map((c) => { const m = prop([{ x: 0, y: 0.31, z: 0, w: 0.56, h: 0.14, d: 0.56, color: 0x9aa0a8 }, { x: 0, y: 0.12, z: -0.27, w: 0.56, h: 0.4, d: 0.06, color: 0x8a9098 }, { x: 0, y: 0.42, z: 0, w: 0.08, h: 0.12, d: 0.4, color: 0xc02a2a }]); m.position.y = 4 / 16; c.neck.add(m); return m; });
  const actors = [noe, lina, ...npc, ...aliens];
  // ---- empreintes de pas (neige, poussière de Lune, terre de la bataille) : une à chaque pose du talon, elles restent
  const fpTex = footprintTex(); const PRINTS = { glace: [0x34445e, 0.9], lune: [0x16161a, 1.0], bataille: [0x1e1208, 0.9], automne: [0x3a2208, 0.6], parc: [0x5a4020, 0.6] };
  const prints = {}; for (const [name, [col, op]] of Object.entries(PRINTS)) { const w = worlds.find((x) => x.name === name); const m = new THREE.MeshLambertMaterial({ map: fpTex, color: col, transparent: true, opacity: op, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2 });
    prints[name] = []; for (let k = 0; k < 44; k++) { const d = new THREE.Mesh(new THREE.PlaneGeometry(0.34, 0.5), m); d.rotation.set(-Math.PI / 2, 0, -Math.PI / 2); d.visible = false; d.receiveShadow = true; w.group.add(d); prints[name].push(d); } }

  // ---- calendrier : 10 mondes, fondus de 1,2 s
  const T0 = [0, 6, 12, 18, 24, 30, 36, 42, 48, 54], END = 61, DIS = 1.2, SPEED = 0.95;
  const mid = (i) => ((T0[i]) + (i < 9 ? T0[i + 1] + DIS : END)) / 2;
  const walkerPos = (i, T) => worlds[i].at((T - mid(i)) * SPEED, 0, 0);
  const placePrints = (i, T) => { const w = worlds[i], pool = prints[w.name]; if (!pool) return; let n = 0;
    const tA = T0[i] - 1, tB = T;   // pas posés depuis l'entrée dans ce monde
    for (let k = Math.ceil((tA * 7 - Math.PI / 2) / Math.PI); ; k++) { const tk = (Math.PI / 2 + k * Math.PI) / 7; if (tk > tB || n >= pool.length) break;
      const side = k % 2 === 0 ? 1 : -1; const P = walkerPos(i, tk).sub(w.origin); const d = pool[n++]; d.visible = true; d.position.set(P.x + 0.24, (w.name === 'parc' ? 0.035 : 0) + 0.006, P.z - side * 0.128); }
    for (; n < pool.length; n++) pool[n].visible = false; };
  // caméra : fonctions lisses du temps global (identiques dans les deux images d'un fondu)
  const K = [[0, 0.3, 7.5, 1.7, 1.6, 46], [6, 0.7, 6.2, 1.5, 1.5, 46], [14, 1.1, 5.8, 1.4, 1.45, 46], [22, 0.85, 5.6, 1.6, 1.5, 46], [27, 1.45, 5.8, 2.1, 1.25, 46], [30, 0.5, 6.0, 1.0, 1.7, 48],
    [38, 0.95, 6.8, 1.6, 1.4, 48], [45, 0.55, 6.5, 0.8, 2.2, 52], [52, 1.3, 5.2, 1.5, 1.5, 48], [57, 1.5, 6.0, 3.1, 0.85, 46], [61, 2.45, 8.5, 2.6, 1.2, 48]];
  const camK = (T) => { let j = 0; while (j < K.length - 2 && T > K[j + 1][0]) j++; const a = K[j], b = K[j + 1]; const k = ease((T - a[0]) / (b[0] - a[0])); return a.map((v, n) => lerp(v, b[n], k)); };
  const camAt = (i, T) => { const [, an, d, h, lh, fov] = camK(T); const P = walkerPos(i, T); return { pos: P.clone().add(V(Math.cos(an) * d, h, Math.sin(an) * d)), look: P.clone().add(V(0.25, lh, 0)), fov, roll: 0.012 * Math.sin(T * 0.4) }; };
  // ---- Noé : marche continue (même phase partout), expression selon le monde
  const EXPR = ['neutral', 'smile', 'relief', 'sad', 'determined', 'scared', 'grit', 'surprised', 'neutral', 'determined'];
  const walkNoe = (i, T) => { const P = walkerPos(i, T); anim.put(noe, P.x, P.z, Math.PI / 2, () => P.y); noe.root.visible = true; anim.walk(noe, T * 7, 0.62); anim.expr(noe, EXPR[i], T);
    if (i === 2 && T > T0[2] + 3.6) noe.setExpr('sad'); if (i === 9 && T > 58.5) noe.setExpr('relief'); if (i === 5) noe.neck.rotation.y += 0.25 * Math.sin(T * 0.9); return P; };
  // personnage qui marche (le long de x) ; z = couloir ; speed négatif = sens inverse
  const walker = (ch, w, x0, z, T, tStart, speed = 0.95, expr = 'neutral', phase = 0) => { const x = x0 + (T - tStart) * speed; const P = w.at(x, 0, z); anim.put(ch, P.x, P.z, speed >= 0 ? Math.PI / 2 : -Math.PI / 2, () => P.y); ch.root.visible = true;
    anim.walk(ch, T * 7 * Math.abs(speed) / 0.95 + phase, 0.6); anim.expr(ch, expr, T); return P; };
  // ---- figurants par monde
  const CASTF = [
    (w, T) => { walker(npc[0], w, 7, -1.2, T, T0[0], -1.1, 'neutral', 1); walker(npc[1], w, -9, -11.4, T, T0[0], 1.0, 'smile', 2); walker(npc[2], w, 9, -12.0, T, T0[0], -0.9, 'neutral', 3);
      const p = w.at(2.6, 0, -1.55); anim.put(npc[6], p.x, p.z, -0.3, () => p.y); npc[6].root.visible = true; anim.breathe(npc[6], T); anim.pose(npc[6], 'lookDown', 0.7 + 0.15 * Math.sin(T * 0.7)); npc[6].neck.rotation.y += 0.25 * Math.sin(T * 0.45); npc[6].shR.rotation.set(-0.5, 0, 0.2); npc[6].elR.rotation.x = -1.4 + 0.08 * Math.sin(T * 3); npc[6].setHand('R', 'grip'); npc[6].setHand('L', [0.4 + 0.3 * Math.max(0, Math.sin(T * 6)), 0, 0.3, 0.4]); npc[6].lgR.rotation.x = -0.12; anim.ground(npc[6]); anim.expr(npc[6], T % 4 < 2.5 ? 'neutral' : 'smile', T); },
    (w, T) => { const P = walkerPos(1, T); const p = P.clone().add(V(0.45, 0, -1.05)); anim.put(lina, p.x, p.z, Math.PI / 2, () => p.y); lina.root.visible = true; anim.walk(lina, T * 7 + 2.6, 0.58); anim.expr(lina, 'smile', T, 0.7);
      lina.neck.rotation.y += -0.5 * ease((T - T0[1] - 1.5) / 1); noe.neck.rotation.y += 0.35 * ease((T - T0[1] - 2.2) / 1);
      const b = w.at(-4, 0, -1.25); anim.put(npc[4], b.x, b.z, 0, () => b.y); npc[4].root.visible = true; anim.sit(npc[4], 1, 0.42); anim.breathe(npc[4], T); anim.expr(npc[4], 'smile', T, 0.4); npc[4].neck.rotation.y += 0.6 * Math.sin(T * 0.5) - 0.3; npc[4].neck.rotation.x += 0.1 * Math.sin(T * 0.8); npc[4].shL.rotation.x -= 0.3; npc[4].elL.rotation.x = -0.9; },
    (w, T) => { const stop = T0[2] + 3.0; const P = walkerPos(2, Math.min(T, stop)); const p = P.clone().add(V(0.45, 0, -1.05)); anim.put(lina, p.x, p.z, Math.PI / 2 - 0.6 * ease((T - stop) / 0.8), () => p.y); lina.root.visible = true;
      if (T < stop) anim.walk(lina, T * 7 + 2.6, 0.58); else { anim.breathe(lina, T); anim.pose(lina, 'wave', ease((T - stop - 0.6) / 0.6)); } anim.expr(lina, T < stop ? 'relief' : 'sad', T, 0.7); },
    (w, T) => { for (let k = 0; k < 3; k++) { walker(npc[k], w, 6 + k * 3.5, -1.4 - k * 0.5, T, T0[3], -1.0, 'neutral', k); npc[k].shR.rotation.set(-0.9, 0, 0.1); npc[k].elR.rotation.x = -0.9; npc[k].setHand('R', 'grip'); umb[k].visible = true; } },
    (w, T) => {},
    (w, T) => { const r = clamp((T - T0[5]) / 7); const p = w.at(8 - r * 22, 0, -6); anim.put(npc[7], p.x, p.z, -Math.PI / 2, () => p.y); npc[7].root.visible = true; anim.run(npc[7], T * 11, 1); anim.expr(npc[7], 'scream', T); },
    (w, T) => { const pairs = [[3, 4, -2.2, -2.6], [5, 6, 1.8, -3.2], [7, 8, -0.4, -5.2]];
      pairs.forEach(([a, b, x, z], n) => { const base = walkerPos(6, T).x - w.origin.x; const cx = x + base * 0.6; for (const [ci, s] of [[a, 1], [b, -1]]) { const c = npc[ci]; const p = w.at(cx + s * 0.75, 0, z); anim.put(c, p.x, p.z, s > 0 ? Math.PI / 2 : -Math.PI / 2, () => p.y); c.root.visible = true;
          const ph = T * 5.5 + n * 1.3 + (s > 0 ? 0 : Math.PI); const hit = Math.max(0, Math.sin(ph));
          c.lgL.rotation.x = -0.4; c.knL.rotation.x = 0.5; c.lgR.rotation.x = 0.35; c.knR.rotation.x = 0.25; anim.ground(c); c.torso.rotation.x = 0.15 + 0.15 * hit; c.torso.rotation.y = 0.3 * Math.sin(ph);
          c.shR.rotation.set(-2.4 + 2.2 * hit, 0, 0.2); c.elR.rotation.x = -0.4 - 0.6 * (1 - hit); c.shL.rotation.set(-1.2, 0, -0.35); c.elL.rotation.x = -1.2; c.setHands('fist', 'fist'); anim.expr(c, n % 2 ? 'shout' : 'grit', T); swords[ci - 3].visible = shields[ci - 3].visible = helmets[ci - 3].visible = true; } }); },
    (w, T) => { const wx = walkerPos(7, T).x - w.origin.x; const lt = T - mid(7);
      // les extraterrestres marchent avec lui, en arrière-plan, de part et d'autre (dans le champ de la caméra, hors des couloirs des fuyards)
      const OFF = [[-0.9, -2.6], [-5.2, -2.3], [-5.2, -3.7]];
      aliens.forEach((a, k) => { const p = w.at(wx + OFF[k][0] - lt * 0.15 + 0.2 * Math.sin(T * 0.6 + k), 0, OFF[k][1] + 0.12 * Math.sin(T * 0.45 + k * 2));
        anim.put(a, p.x, p.z, Math.PI / 2 - 0.08 * Math.sin(T * 0.6 + k), () => p.y); a.root.visible = true; anim.walk(a, T * 5.9 + k * 1.7, 0.5); a.torso.rotation.x += 0.05;
        a.neck.rotation.y += k === 1 ? -0.55 + 0.2 * Math.sin(T * 0.7) : 0.4 * Math.sin(T * 0.8 + k); a.neck.rotation.x += k === 0 ? -0.35 : 0.08 * Math.sin(T * 1.1 + k);
        if (k === 0) { a.shR.rotation.set(-2.45, 0, -0.6); a.elR.rotation.x = -0.15; a.setHand('R', 'point'); a._lockR = true; }
        else if (k === 2) { a.shL.rotation.x += -0.35; a.elL.rotation.x = -0.6; a.setHands('open', 'relaxed'); }
        a.face.extra = { iris: 1.75, brow: 0 }; a.setExpr(k === 1 ? 'surprised' : 'neutral'); });
      for (let k = 0; k < 3; k++) { const r = T - T0[7] - k * 0.8; const p = w.at(9 - r * 3.4, 0, -1.6 - k * 1.4); anim.put(npc[k], p.x, p.z, -Math.PI / 2, () => p.y); npc[k].root.visible = true; anim.run(npc[k], T * 11 + k, 1); anim.expr(npc[k], 'scream', T); } },
    (w, T) => { const p = w.at(6 - (T - T0[8]) * 0.9, 0, -2.4); anim.put(npc[9], p.x, p.z, -Math.PI / 2, () => p.y); npc[9].root.visible = true; anim.walk(npc[9], T * 6.5, 0.55); anim.expr(npc[9], 'smile', T); npc[9].neck.rotation.y -= 0.5; },
    (w, T) => {},
  ];
  // ---- plans
  const shots = worlds.map((w, i) => ({
    name: `${i}_${w.name}`, t0: T0[i], dissolve: i ? DIS : 0,
    cam: (lt, u, T) => { walkNoe(i, T); return camAt(i, T); },
    fn: (lt, u, T, S) => {
      w.look(S, T); S.sets = [w.name]; const P = walkNoe(i, T); CASTF[i](w, T); placePrints(i, T);
      S.shadowC = P.clone(); S.shadowS = 14; S.focus = camK(T)[2]; S.dofScale = 0.35; S.mblur = 0.15;
      if (w.reflectY !== undefined) S.reflect = { y: w.origin.y + w.reflectY };
      if (i === 0) S.fade = ease(T / 0.8);
      if (i === 9) { const k = ease((T - 59.0) / 2.0); S.flash = k; S.flashCol = 0xffffff; S.exposure = 1 + 1.5 * k; }
    },
  }));
  for (let i = 0; i < shots.length - 1; i++) shots[i].t1 = shots[i + 1].t0; shots[shots.length - 1].t1 = END;
  const sets = {}; worlds.forEach((w) => { sets[w.name] = { group: w.group, update: (t) => w.update(t) }; });
  return {
    shots, duration: END, sets,
    reset: () => {
      for (const a of actors) { a.reset(); a.root.visible = false; a.root.position.set(0, -500, 0); }
      for (const m of [...umb, ...swords, ...shields, ...helmets]) m.visible = false;
    },
    post: (t) => { for (const a of actors) if (a.root.visible) { anim.relaxArms(a); if (a.faceUpdate) a.faceUpdate(t); } },
  };
}
