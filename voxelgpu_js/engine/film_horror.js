// Original horror short (FR): "La règle des volets" — built on the v2 town engine.
let ROOM = null;
export const crowdOpts = { creepy: true, pale: true };

// carve Jade's bedroom on the 2nd floor of an east-side house, with see-through windows
export function prepareWorld(w, info, B) {
  const hs = info.houses.filter(h => h.facing === '-x' && Math.abs(h.front[0] - 15) < 0.6);
  const h = hs.reduce((b, x) => Math.abs(x.porch[1] - 100) < Math.abs(b.porch[1] - 100) ? x : b, hs[0]);
  const [fx, fz] = h.front;
  for (let v = 1; v <= 7; v++) for (let u = 1; u <= 9; u++) { w.set(fx + v, 4, fz + u, B.plank); w.set(fx + v, 5, fz + u, 0); w.set(fx + v, 6, fz + u, 0); }
  for (const u of [1, 2, 3, 4, 5, 6, 7, 8, 9]) for (const y of [5, 6]) w.set(fx, y, fz + u, B.glass);
  ROOM = { fx, fz, house: h, win: { x: fx + 0.5, z: fz + 4.5 } };
}

export async function setup(ctx) {
  const { THREE, V, scene, buildHumanoid, crowd, creature, decals, town, mulberry, PX } = ctx;
  const gy = (x, z) => town.groundY(x, z);
  const clamp01 = (x) => Math.min(1, Math.max(0, x));
  const ease = (x) => { x = clamp01(x); return x * x * (3 - 2 * x); };
  const eio = (x) => { x = clamp01(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
  const eout = (x) => { x = clamp01(x); return 1 - Math.pow(1 - x, 3); };
  const lerp = (a, b, k) => a + (b - a) * k;
  const seg = (lt, a, b) => clamp01((lt - a) / (b - a));
  const TL = await (await fetch('./horror_timeline.json')).json();
  const LN = Object.fromEntries(TL.lines.map(l => [l.id, l]));

  const heroes = {
    jade: buildHumanoid({ skin: 0xf2c9a0, hair: 0x5a3622, hairStyle: 'long', eyes: 0x3a6a4a, shirt: 0x9ac4e8, shirtStyle: 'tee', sleeves: 'long', pants: 0x7a9ac8, shoes: 0xe8e8e8, female: true }, 21),
    mom: buildHumanoid({ skin: 0xe8b48f, hair: 0x5a3a22, hairStyle: 'bun', eyes: 0x4a3a2a, shirt: 0xd88aa8, shirtStyle: 'tee', sleeves: 'long', pants: 0xb87090, female: true }, 22),
    fake: buildHumanoid({ skin: 0xd8c4b4, hair: 0x5a3a22, hairStyle: 'bun', eyes: 0x4a3a2a, shirt: 0xb07890, shirtStyle: 'tee', sleeves: 'long', pants: 0x905870, female: true }, 23),
  };
  heroes.jade.baseScale = 0.86;
  for (const h of Object.values(heroes)) scene.add(h.root);
  const R = ROOM; const WIN = V(R.win.x, 6.2, R.win.z);
  const roomLight = new THREE.PointLight(0xffb070, 0, 9, 1.4); roomLight.position.set(R.fx + 4, 6.7, R.fz + 5); scene.add(roomLight);
  const porchLight = new THREE.PointLight(0xffd8a0, 0, 7, 1.6); porchLight.position.set(R.fx - 0.6, 3.8, R.fz + 5.5); scene.add(porchLight);
  // props: bed, lamp, door panel
  const props = {};
  const mat = (c) => new THREE.MeshLambertMaterial({ color: c });
  const boxM = (w, h, d, m, x = 0, y = 0, z = 0) => { const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m); b.position.set(x, y, z); b.castShadow = true; b.receiveShadow = true; return b; };
  const bed = new THREE.Group(); bed.add(boxM(1.2, 0.5, 2.2, mat(0x6a4a2a), 0, 0.25, 0)); bed.add(boxM(1.15, 0.2, 2.1, mat(0xe8e2d8), 0, 0.6, 0.02)); bed.add(boxM(1.16, 0.12, 1.4, mat(0x6a8ac8), 0, 0.72, 0.38)); bed.add(boxM(0.8, 0.18, 0.4, mat(0xf4f4f0), 0, 0.78, -0.8));
  bed.position.set(R.fx + 6.4, 5, R.fz + 7.5); scene.add(bed); props.bed = bed;
  const lamp = new THREE.Group(); lamp.add(boxM(0.5, 0.6, 0.5, mat(0x5a3a2a), 0, 0.3, 0)); const sh = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.34, 0.42), new THREE.MeshBasicMaterial({ color: 0xffffff })); sh.material.color.setRGB(3.2, 2.3, 1.2); sh.position.y = 0.85; lamp.add(sh);
  lamp.position.set(R.fx + 6.6, 5, R.fz + 5.6); scene.add(lamp);
  const doorPanel = boxM(0.12, 2.0, 0.95, new THREE.MeshLambertMaterial({ map: town.T.door }), R.fx - 0.07, 2.0, R.fz + 5.5); scene.add(doorPanel);

  const put = (h, x, z, yaw, y) => { h.root.position.set(x, y ?? gy(x, z), z); h.root.rotation.y = yaw; h.root.visible = true; return h; };
  const blink = (t, s) => ((t * 0.31 + s) % 1) < 0.036;
  const expr = (h, e, t, s = 0.3) => h.setExpr(blink(t, s) && e !== 'happy' && e !== 'hollow' ? 'blink' : e);
  function idle(h, t, s = 1) { const b = Math.sin(t * 2.1 + h.root.position.x); h.hips.position.y += 0.005 * b * s; h.shL.rotation.z += 0.04 * s; h.shR.rotation.z -= 0.04 * s; }
  function walk(h, phase, amp = 0.6) { const s = Math.sin(phase); h.lgL.rotation.x = s * amp; h.lgR.rotation.x = -s * amp; h.shL.rotation.x = -s * amp * 0.85; h.shR.rotation.x = s * amp * 0.85; }
  const cam = (S, p0, p1, l0, l1, k, fov) => { S.cam.pos.lerpVectors(p0, p1, k); S.cam.look.lerpVectors(l0, l1, k); if (fov) S.cam.fov = fov; };
  const focusOn = (S, p, sc) => { S.focus = S.cam.pos.distanceTo(p); if (sc !== undefined) S.dofScale = sc; };
  let PI = 0; const person = (o) => { const p = crowd.people[PI++]; if (!p) return null; Object.assign(p, { on: true, amp: 0, lean: 0, headYaw: 0, headPitch: 0, armL: 0, armR: 0, legs: 0, scale: 1 }, o); if (o.y === undefined) p.y = gy(p.x, p.z); return p; };

  // the silent crowd: grid in the street facing the house; snap = heads turn up to the window
  const ZC = R.fz + 5;
  function silentCrowd(t, { snap = 0, n = 320, range = [ZC - 34, ZC + 44], sway = 1, aisle = false } = {}) {
    let c = 0; const r = mulberry(17);
    for (let z = range[0]; z < range[1]; z += 2.6) for (let x = -13.5; x <= 11; x += 2.5) {
      if (c >= n) break; const ix = Math.round(x / 2.5), iz = Math.round(z / 2.6); if ((ix + iz) & 1) continue;
      if (x > 8.4 && Math.abs(z - ZC) < 9) continue; // keep the front lawn of the house clear
      if (aisle && x > -1.4 && x < 2.2) continue;
      const px = x + (r() - 0.5) * 0.5, pz = z + (r() - 0.5) * 0.5; const yawHouse = Math.atan2(R.fx - px, ZC - pz) * 0.25 + Math.PI / 2 * 0.75;
      const dx = WIN.x - px, dz = WIN.z - pz, dy = WIN.y - 1.7; const yawWin = Math.atan2(dx, dz);
      const k = clamp01(snap * 1.3 - r() * 0.3);
      const yaw = yawHouse + Math.sin(t * 0.3 + px) * 0.01 * sway;
      person({ x: px, z: pz, yaw, headYaw: lerp(0, ((yawWin - yaw + Math.PI * 3) % (Math.PI * 2)) - Math.PI, k), headPitch: lerp(0, -Math.atan2(dy, Math.hypot(dx, dz)) * 0.9, k), skin: Math.floor(r() * 32), armL: 0.02, armR: 0.02 });
      c++;
    }
  }
  const horror = (S, extra = {}) => {
    S.tod = 'night'; S.todOver = { fog: 0x0b1226, fogD: 0.016, hemiI: 0.66, sunI: 0.8, sat: 0.72, exposure: 1.3, top: 0x070d26, horizon: 0x18244e, ...extra }; S.tint = [0.9, 0.97, 1.1]; S.vignette = 0.62; S.grain = 0.045; S.bloom = 0.5;
  };
  const roomOn = (k = 1) => { roomLight.intensity = 16 * k; };
  const reset = () => { doorPanel.visible = true; PI = 0; roomLight.intensity = 0; porchLight.intensity = 0; doorPanel.position.x = R.fx - 0.07; doorPanel.rotation.z = 0; };

  const shots = []; const SH = Object.fromEntries(TL.shots.map(s => [s.name, s]));
  const add = (name, fn) => shots.push({ name, t0: SH[name].t0, t1: SH[name].t1, fn: (lt, u, t, S, sh) => { reset(); fn(lt, u, t, S, sh); } });

  add('aerial', (lt, u, t, S) => {
    horror(S, { fogD: 0.011 }); S.winLevel = 1; S.lamps = 'on'; roomOn();
    cam(S, V(-40, 46, ZC + 70), V(-20, 22, ZC + 32), V(10, 2, ZC + 6), V(12, 3, ZC + 2), eout(u), 56); S.focus = S.cam.pos.distanceTo(S.cam.look); S.dofScale = 0.3; S.shadowC.set(0, 0, ZC); S.shadowS = 40;
  });
  add('windows', (lt, u, t, S) => {
    horror(S); const k = eio(seg(lt, 1.0, 4.4)); S.winLevel = 1 - k; S.lamps = 'on'; roomOn();
    cam(S, V(-2.5, 1.5, ZC - 22), V(-2.2, 1.5, ZC - 20), V(16, 4.5, ZC - 4), V(16, 4.8, ZC - 2), u, 60); S.focus = 18; S.dofScale = 0.35; S.shadowC.set(10, 0, ZC - 10); S.shadowS = 25;
  });
  add('litwin', (lt, u, t, S) => {
    horror(S); S.winLevel = 0; S.lamps = 'on'; roomOn();
    put(heroes.jade, R.fx + 1.6, R.fz + 4.6, -Math.PI / 2, 5); idle(heroes.jade, t); expr(heroes.jade, 'neutral', t);
    cam(S, V(-1, 1.8, ZC - 6), V(3.5, 2.8, ZC - 3), WIN.clone().add(V(0, -0.6, 0)), WIN, eio(u), 46); focusOn(S, WIN, 0.6); S.shadowC.set(12, 0, ZC); S.shadowS = 14;
  });
  add('ots', (lt, u, t, S) => {
    horror(S); S.winLevel = 0; S.lamps = 'on'; roomOn(); const k = eio(seg(lt, 0, 1.6));
    put(heroes.jade, lerp(R.fx + 3.2, R.fx + 1.3, k), R.fz + 4.6, -Math.PI / 2, 5); walk(heroes.jade, lt * 6, 0.45 * (1 - k)); expr(heroes.jade, 'neutral', t);
    cam(S, V(R.fx + 5.2, 6.75, R.fz + 6.4), V(R.fx + 4.3, 6.7, R.fz + 5.9), V(R.fx, 5.7, R.fz + 4.6), V(R.fx, 5.6, R.fz + 4.5), u, 62); focusOn(S, V(R.fx + 1.5, 6, R.fz + 4.6), 0.8); S.shadowC.set(R.fx, 0, ZC); S.shadowS = 10;
  });
  add('pov', (lt, u, t, S) => {
    horror(S); S.winLevel = 0; S.lamps = 'on'; roomOn(0.6); silentCrowd(t);
    cam(S, V(R.fx + 0.3, 6.5, R.fz + 4.5), V(R.fx + 0.25, 6.5, R.fz + 4.5), V(6, 2.5, ZC - 1), V(2, 0, ZC - 2), eio(u), 70); S.distort = 0.15; S.focus = 14; S.dofScale = 0.3; S.shadowC.set(0, 0, ZC); S.shadowS = 30;
  });
  add('faces', (lt, u, t, S) => {
    horror(S); S.winLevel = 0; S.lamps = 'on'; roomOn(); silentCrowd(t);
    const z = lerp(ZC - 10, ZC - 4, eio(u)); cam(S, V(6.6, 1.5, z), V(6.6, 1.5, z), V(-4, 1.7, z + 3.2), V(-4, 1.7, z + 3.2), 1, 54); S.focus = 2.5; S.dofScale = 0.9; S.shadowC.set(0, 0, z); S.shadowS = 14;
    S.cam.look.lerp(V(-2.7, 1.62, z + 0.2), 0.0);
  });
  add('lamps', (lt, u, t, S) => {
    horror(S); S.winLevel = 0; roomOn(); silentCrowd(t, { range: [ZC - 30, ZC + 60], aisle: true });
    const zOff = lerp(ZC + 75, ZC - 6, clamp01(lt / 3.4)); S.lamps = 'fn'; S.lampFn = (p) => (p.z > zOff ? 0 : 1) * (p.z > zOff - 6 && p.z < zOff ? 0.4 + 0.6 * (Math.sin(t * 60) > 0 ? 1 : 0) : 1);
    cam(S, V(0.4, 0.9, ZC - 12), V(0.4, 0.95, ZC - 11), V(0, 3, ZC + 50), V(0, 3, ZC + 50), u, 58); S.focus = 20; S.dofScale = 0.35; S.shadowC.set(0, 0, ZC + 10); S.shadowS = 30;
  });
  const thingWalk = (t, z, s = 1.6) => { creature.root.visible = true; creature.root.position.set(0.3, 0, z); creature.root.scale.setScalar(s); creature.root.rotation.y = Math.PI; const ph = t * 1.6; creature.lgL.rotation.x = Math.sin(ph) * 0.35; creature.lgR.rotation.x = -Math.sin(ph) * 0.35; creature.shL.rotation.x = -Math.sin(ph) * 0.25; creature.shR.rotation.x = Math.sin(ph) * 0.25; creature.hips.position.y = 7 + Math.abs(Math.cos(ph)) * 0.2; creature.neck.rotation.z = 0.12 * Math.sin(t * 0.7); };
  add('thing', (lt, u, t, S) => {
    horror(S, { fogD: 0.02 }); S.winLevel = 0; S.lamps = 'off'; roomOn(); silentCrowd(t, { range: [ZC - 20, ZC + 70], aisle: true });
    thingWalk(t, lerp(ZC + 95, ZC + 70, u));
    cam(S, V(-1.2, 1.2, ZC + 30), V(-1.2, 1.25, ZC + 31), V(0.3, 9, ZC + 80), V(0.3, 10, ZC + 78), u, 54); S.focus = 50; S.dofScale = 0.25; S.shadowC.set(0, 0, ZC + 50); S.shadowS = 40;
  });
  add('snap', (lt, u, t, S) => {
    horror(S); S.winLevel = 0; S.lamps = 'off'; roomOn(0.6);
    const snapT = LN.H9.start - SH.snap.t0 + 0.35; const snap = clamp01((lt - snapT) / 0.25);
    silentCrowd(t, { snap, aisle: true }); thingWalk(t, ZC + 62);
    cam(S, V(R.fx + 0.25, 6.5, R.fz + 4.5), V(R.fx + 0.23, 6.5, R.fz + 4.5), V(2, 0, ZC - 2), V(1, 0, ZC - 2.5), u, 70); S.distort = 0.18; S.focus = 13; S.dofScale = 0.3; S.shadowC.set(0, 0, ZC); S.shadowS = 30;
    if (snap > 0) S.shake = 0.004 + 0.02 * (1 - clamp01((lt - snapT) / 0.6));
  });
  // knocks at given times: arm strikes and door shudders
  const knocks = () => { const s = LN.H10.start - SH.door.t0; return [s + 1.45, s + 1.85, s + 2.25]; };
  add('door', (lt, u, t, S) => {
    horror(S, { hemiI: 0.5 }); S.winLevel = 0; S.lamps = 'off'; porchLight.intensity = 4;
    put(heroes.fake, R.fx - 1.0, R.fz + 5.5, Math.PI / 2, 1); heroes.fake.root.scale.set(0.92, 1.32, 0.92); heroes.fake.setExpr('hollow'); heroes.fake.neck.rotation.z = 0.12;
    let hit = 0; for (const kt of knocks()) { const d = lt - kt; if (d > -0.18 && d < 0.18) hit = Math.max(hit, 1 - Math.abs(d) / 0.18); }
    heroes.fake.shR.rotation.x = -1.4 - 0.35 * hit; doorPanel.rotation.z = 0.01 * hit; doorPanel.position.x = R.fx - 0.07 + 0.015 * hit;
    cam(S, V(R.fx - 4.2, 0.8, R.fz + 2.2), V(R.fx - 4.0, 0.85, R.fz + 2.5), V(R.fx - 0.8, 2.2, R.fz + 5.4), V(R.fx - 0.8, 2.4, R.fz + 5.4), u, 52); focusOn(S, V(R.fx - 1, 2, R.fz + 5.5), 0.6); S.shadowC.set(R.fx, 0, R.fz + 5); S.shadowS = 10;
    if (hit > 0.5) S.shake = 0.01;
  });
  add('peep', (lt, u, t, S) => {
    horror(S, { hemiI: 0.5 }); S.winLevel = 0; S.lamps = 'off'; porchLight.intensity = 8;
    const lean = eio(seg(lt, 0.3, 3.0));
    put(heroes.fake, R.fx - lerp(2.3, 1.45, lean), R.fz + 5.5, Math.PI / 2, 1); heroes.fake.root.scale.set(0.92, 1.32, 0.92); heroes.fake.setExpr('hollow');
    heroes.fake.torso.rotation.x = 0.18 * lean; heroes.fake.neck.rotation.x = 0.3 * lean; heroes.fake.neck.rotation.z = 0.25 * Math.sin(lt * 0.6) + 0.15;
    const sp = ctx.envAt(t); heroes.fake.neck.rotation.x += sp * 0.06 * Math.sin(t * 11);
    doorPanel.visible = false; cam(S, V(R.fx - 0.08, 2.75, R.fz + 5.5), V(R.fx - 0.08, 2.75, R.fz + 5.5), V(R.fx - 2.5, 3.15, R.fz + 5.5), V(R.fx - 2.5, 3.1, R.fz + 5.5), 1, 92); S.distort = 1.1; S.peep = 1; S.focus = 1.2; S.dofScale = 0.2; S.vignette = 0.3; S.shadowC.set(R.fx, 0, R.fz + 5); S.shadowS = 8; S.grain = 0.06;
  });
  add('twist', (lt, u, t, S) => {
    horror(S, { hemiI: 0.5 }); S.winLevel = 0; S.lamps = 'off'; roomOn(0.8);
    const turn = eio(seg(lt, 0.3, 1.0));
    put(heroes.jade, R.fx + 1.4, R.fz + 4.6, -Math.PI / 2 + turn * Math.PI * 0.85, 5); expr(heroes.jade, turn > 0.5 ? 'scared' : 'neutral', t);
    put(heroes.mom, R.fx + 2.4, R.fz + 3.6, Math.PI * 0.75, 5); heroes.mom.setExpr('scared'); heroes.mom.shR.rotation.x = -1.2 * ease(seg(lt, 1.2, 1.8)); heroes.mom.neck.rotation.y = -0.3;
    cam(S, V(R.fx + 5.8, 6.3, R.fz + 4.4), V(R.fx + 5.4, 6.3, R.fz + 4.3), V(R.fx + 2.0, 6.2, R.fz + 3.8), V(R.fx + 2.0, 6.2, R.fz + 3.8), u, 58); focusOn(S, V(R.fx + 1.8, 6.2, R.fz + 4.2), 0.9); S.shadowC.set(R.fx, 0, ZC); S.shadowS = 10;
  });
  add('final', (lt, u, t, S) => {
    horror(S, { fogD: 0.012, horizon: 0x2a3a6e, glow: 0x7a8ac8, haze: 0.9 }); S.sunDir = [0.9, 0.32, 0.12]; S.winLevel = 0; S.lamps = 'off'; roomOn(); porchLight.intensity = 3;
    silentCrowd(t, { snap: 1, aisle: true });
    creature.root.visible = true; creature.root.position.set(R.fx + 12, 0, R.fz + 7); creature.root.scale.setScalar(1.7); creature.root.rotation.y = -Math.PI / 2; creature.torso.rotation.x = 0.25 + 0.1 * eio(u); creature.neck.rotation.z = 0.35 * eio(u); creature.shL.rotation.z = 0.3; creature.shR.rotation.z = -0.35;
    put(heroes.fake, R.fx - 1.0, R.fz + 5.5, -Math.PI / 2, 1); heroes.fake.root.scale.set(0.92, 1.32, 0.92); heroes.fake.setExpr('hollow'); heroes.fake.neck.rotation.x = -0.5;
    cam(S, V(-2.6, 2.0, ZC - 14), V(-4.2, 3.2, ZC - 17.5), V(15, 9, ZC + 3), V(16, 11, ZC + 4), eio(u), 58); S.focus = 24; S.dofScale = 0.3; S.shadowC.set(5, 0, ZC); S.shadowS = 30;
  });
  { const lampT = []; for (const p of town.M.lampHeads) { if (Math.abs(p.x) > 9 || p.z < ZC - 6 || p.z > ZC + 75) continue; lampT.push(+(SH.lamps.t0 + (ZC + 75 - p.z) / 81 * 3.4).toFixed(3)); } lampT.sort((a, b) => a - b);
    window.HORROR_INFO = { ZC, lampT, knocks: knocks().map(k => +(k + SH.door.t0).toFixed(3)), snap: +(LN.H9.start + 0.35).toFixed(3) }; }
  return { shots, heroes, props: {}, duration: TL.duration, envelope: './horror_env.json' };
}
