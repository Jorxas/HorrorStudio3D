// Remake of the 3-minute "shadow town" story, shot by shot, in the voxel style.
// Timing follows the reference cuts (engine/ref_shots.json); audio = original track.
export async function setup(ctx) {
  const { THREE, V, scene, buildHumanoid, buildProp, crowd, creature, decals, thread, town, interiors, mulberry, PX } = ctx;
  const info = town.info;
  const gy = (x, z) => town.groundY(x, z);
  const clamp01 = (x) => Math.min(1, Math.max(0, x));
  const ease = (x) => { x = clamp01(x); return x * x * (3 - 2 * x); };
  const eio = (x) => { x = clamp01(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
  const eout = (x) => { x = clamp01(x); return 1 - Math.pow(1 - x, 3); };
  const lerp = (a, b, k) => a + (b - a) * k;
  const seg = (lt, a, b) => clamp01((lt - a) / (b - a));
  const wrap = (a) => { while (a > Math.PI) a -= 2 * Math.PI; while (a < -Math.PI) a += 2 * Math.PI; return a; };

  // ---------------------------------------------------------------- cast
  const heroes = {
    me: buildHumanoid({ skin: 0xe8b48f, hair: 0x5a3a22, hairStyle: 'short', eyes: 0x5a3a22, shirt: 0x6f7a4e, shirt2: 0x4a5236, shirtStyle: 'camo', pants: 0x2a2a2e, shoes: 0x3a2a1a }, 3),
    theo: buildHumanoid({ skin: 0x8d5a3a, hair: 0x1a1a1a, hairStyle: 'short', eyes: 0x3a2a1a, shirt: 0xd23a2e, shirtStyle: 'tee', sleeves: 'short', pants: 0x3a5a8c, headphones: 0x2f6fd0 }, 4),
    mayor: buildHumanoid({ skin: 0xe8b48f, hair: 0x6a3a1e, hairStyle: 'short', eyes: 0x3a2a1a, shirt: 0x1a1a1e, shirtStyle: 'suit', sash: 0xc0242a, tie: 0x8a1a1a, pants: 0x1a1a1e, shoes: 0x111111, tophat: true }, 5),
    mom: buildHumanoid({ skin: 0x8d5a3a, hair: 0x1a1a1a, hairStyle: 'bun', eyes: 0x3a2a1a, shirt: 0x3fa04a, shirtStyle: 'tee', pants: 0x2f3f6a, female: true }, 6),
    grocer: buildHumanoid({ skin: 0xf2c9a0, hair: 0xc8402a, hairStyle: 'long', eyes: 0x3a8a4a, shirt: 0xf0c02e, shirtStyle: 'tee', sleeves: 'short', pants: 0x3a3a40, female: true }, 7),
    guard: buildHumanoid({ skin: 0xd9a27c, hair: 0x4a2a1a, hairStyle: 'short', eyes: 0x3a2a1a, shirt: 0xd6e83a, shirt2: 0x2a2a2a, shirtStyle: 'stripes', sleeves: 'short', pants: 0x1f2f4a }, 8),
    ladder: buildHumanoid({ skin: 0xe8b48f, hair: 0x6a3a1e, hairStyle: 'short', eyes: 0x3a6ab0, shirt: 0x2f5fb0, shirtStyle: 'tee', pants: 0x2a3f6a, cap: 0x2f5fb0 }, 9),
    porchman: buildHumanoid({ skin: 0xd9a27c, hair: 0x2a1a12, hairStyle: 'short', eyes: 0x3a2a1a, shirt: 0xe07a2e, shirtStyle: 'tee', pants: 0x5a4a3a }, 10),
    neighbor: buildHumanoid({ skin: 0xf2c9a0, hair: 0x8a6a3a, hairStyle: 'short', eyes: 0x3a6ab0, shirt: 0x3a9a4a, shirtStyle: 'flannel', pants: 0x3a3a3e }, 11),
    granny: buildHumanoid({ skin: 0xf2c9a0, hair: 0xd8d8d4, hairStyle: 'bun', eyes: 0x5a5a6a, shirt: 0x9a7ac0, shirtStyle: 'dress', female: true, glasses: true }, 12),
  };
  heroes.me.baseScale = 0.86; heroes.theo.baseScale = 0.86;
  for (const h of Object.values(heroes)) scene.add(h.root);
  // shadow-only double of the mayor (renders only into the shadow map)
  const mayorShadow = buildHumanoid(heroes.mayor.spec, 5);
  mayorShadow.root.traverse(o => { if (o.isMesh) { o.material = o.material.clone(); o.material.colorWrite = false; o.material.depthWrite = false; } });
  scene.add(mayorShadow.root); heroes.mayorShadow = mayorShadow;

  // ---------------------------------------------------------------- props
  const props = {};
  const addProp = (k, obj) => { obj.visible = false; scene.add(obj); props[k] = obj; return obj; };
  const mat = (c) => new THREE.MeshLambertMaterial({ color: c });
  const boxM = (w, h, d, m, x = 0, y = 0, z = 0) => { const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m); b.position.set(x, y, z); b.castShadow = true; b.receiveShadow = true; return b; };
  function makeBus(color = 0xf2b81f) {
    const g = new THREE.Group(); const y = mat(color), blk = mat(0x1a1c22), gl = mat(0x2a3f5a);
    g.add(boxM(2.6, 2.4, 10, y, 0, 1.6, 0)); g.add(boxM(2.66, 0.75, 8.4, gl, 0, 2.1, -0.4)); g.add(boxM(2.62, 0.12, 10.02, blk, 0, 1.1, 0));
    g.add(boxM(2.4, 1.2, 1.4, y, 0, 1.0, 5.6)); for (const [x, z] of [[-1.2, -3.4], [1.2, -3.4], [-1.2, 3.2], [1.2, 3.2]]) g.add(boxM(0.35, 0.9, 0.9, blk, x, 0.45, z));
    return g;
  }
  function makeCar(color) {
    const g = new THREE.Group(); const b = mat(color), blk = mat(0x1a1c22), gl = mat(0x2a3f5a);
    g.add(boxM(1.8, 0.8, 4, b, 0, 0.75, 0)); g.add(boxM(1.6, 0.65, 2.1, gl, 0, 1.45, -0.2)); g.add(boxM(1.62, 0.12, 2.2, b, 0, 1.82, -0.2));
    for (const [x, z] of [[-0.9, -1.3], [0.9, -1.3], [-0.9, 1.3], [0.9, 1.3]]) g.add(boxM(0.3, 0.6, 0.6, blk, x, 0.3, z));
    return g;
  }
  function makeTruck(color) {
    const g = new THREE.Group(); g.add(boxM(2.6, 3.2, 9, mat(0xd8d8d4), 0, 2.2, -1.5)); g.add(boxM(2.5, 2.6, 2.6, mat(color), 0, 1.7, 4.3)); g.add(boxM(2.3, 0.9, 0.1, mat(0x2a3f5a), 0, 2.4, 5.61));
    for (const z of [-4.5, -2.5, 4]) for (const x of [-1.3, 1.3]) g.add(boxM(0.35, 1, 1, mat(0x1a1c22), x, 0.5, z)); return g;
  }
  addProp('bus', makeBus()); addProp('bus2', makeBus(0x3a9a4a));
  const carCols = [0xc0302a, 0x2f5fb0, 0xe8e8e2, 0x2a2a2e, 0x8a8a8e, 0x3a8a4a];
  for (let i = 0; i < 6; i++) addProp('car' + i, makeCar(carCols[i]));
  addProp('truck1', makeTruck(0xc0302a)); addProp('truck2', makeTruck(0x2f6fd0)); addProp('truck3', makeTruck(0x3a8a4a));
  addProp('stop', buildProp('stop')); addProp('bag', buildProp('bag')); addProp('ladderP', buildProp('ladder')); addProp('bike', buildProp('bike')); addProp('sub', buildProp('sign'));
  const oranges = []; for (let i = 0; i < 6; i++) oranges.push(addProp('or' + i, buildProp('orange')));
  const boxes = []; for (let i = 0; i < 5; i++) { const b = boxM(0.7, 0.5, 0.6, mat(0xb8905a)); boxes.push(addProp('box' + i, b)); }
  const chair = new THREE.Group(); { const w = mat(0x6a4a2a); chair.add(boxM(0.8, 0.1, 0.8, w, 0, 0.75, 0)); chair.add(boxM(0.8, 0.9, 0.1, w, 0, 1.25, -0.37)); for (const [x, z] of [[-0.35, -0.35], [0.35, -0.35], [-0.35, 0.35], [0.35, 0.35]]) chair.add(boxM(0.08, 0.75, 0.08, w, x, 0.37, z)); }
  addProp('chair', chair);
  const shoes = new THREE.Group(); shoes.add(boxM(0.22, 0.14, 0.38, mat(0x3a2414), -0.14, 0.07, 0)); shoes.add(boxM(0.22, 0.14, 0.38, mat(0x3a2414), 0.14, 0.07, 0.04)); addProp('shoes', shoes);
  const film = new THREE.Group(); { const f = boxM(0.12, 0.95, 0.12, mat(0xf4f2ec)); for (let i = 0; i < 14; i++) { const p = f.clone(); p.position.set(i * 0.42, 0.48, 0); film.add(p); } film.add(boxM(5.6, 0.08, 0.06, mat(0xf4f2ec), 2.75, 0.3, 0.06)); film.add(boxM(5.6, 0.08, 0.06, mat(0xf4f2ec), 2.75, 0.72, 0.06)); }
  addProp('fence', film);
  const hands = new THREE.Group(); { const hm = new THREE.MeshBasicMaterial({ color: 0x040406 }); for (const sx of [-1, 1]) { const arm = boxM(3.4, 40, 0.3, hm, sx * 6, -10, 0); arm.rotation.z = sx * 0.35; hands.add(arm); for (const f of [-1, 0, 1]) { const fg = boxM(0.8, 8, 0.3, hm, sx * 6 - sx * 6.5 + f * 1.3, 12, 0); fg.rotation.z = sx * 0.35 + f * 0.22; hands.add(fg); } } }
  addProp('hands', hands);

  // ---------------------------------------------------------------- helpers
  const put = (h, x, z, yaw, yOff = 0) => { h.root.position.set(x, gy(x, z) + yOff, z); h.root.rotation.y = yaw; h.root.visible = true; return h; };
  const show = (k, x, y, z, ry = 0, rx = 0, rz = 0) => { const p = props[k]; p.visible = true; p.position.set(x, y, z); p.rotation.set(rx, ry, rz); return p; };
  function idle(h, t, s = 1) { const b = Math.sin(t * 2.1 + h.root.position.x); h.hips.position.y += 0.006 * b * s; h.torso.rotation.x += 0.012 * b * s; h.shL.rotation.z += (0.05 + 0.015 * Math.sin(t * 2.1)) * s; h.shR.rotation.z -= (0.05 + 0.015 * Math.sin(t * 2.3)) * s; h.neck.rotation.y += 0.04 * Math.sin(t * 0.53 + h.root.position.z) * s; }
  function walk(h, phase, amp = 0.75, lean = 0.06) { const s = Math.sin(phase); h.lgL.rotation.x = s * amp; h.lgR.rotation.x = -s * amp; h.shL.rotation.x = -s * amp * 0.85; h.shR.rotation.x = s * amp * 0.85; h.hips.position.y = 12 * PX + Math.abs(Math.cos(phase)) * amp * 0.08; h.torso.rotation.x = lean; h.neck.rotation.x = -lean * 0.7; }
  function sit(h) { h.lgL.rotation.x = h.lgR.rotation.x = -1.45; h.lgL.rotation.z = 0.08; h.lgR.rotation.z = -0.08; }
  function lookAt(h, tgt, w = 1) { const p = h.root.position; const dx = tgt.x - p.x, dz = tgt.z - p.z; const rel = Math.max(-1.2, Math.min(1.2, wrap(Math.atan2(dx, dz) - h.root.rotation.y))); const pitch = Math.max(-0.7, Math.min(0.7, Math.atan2(-(tgt.y - p.y - 1.6 * h.root.scale.y), Math.hypot(dx, dz)))); h.neck.rotation.y += rel * w; h.neck.rotation.x += pitch * w; }
  const blink = (t, s) => ((t * 0.31 + s) % 1) < 0.036;
  const expr = (h, e, t, s = 0.3) => h.setExpr(blink(t, s) && e !== 'happy' ? 'blink' : e);
  const cam = (S, p0, p1, l0, l1, k, fov) => { S.cam.pos.lerpVectors(p0, p1, k); S.cam.look.lerpVectors(l0, l1, k); if (fov) S.cam.fov = fov; };
  const focusOn = (S, p, scale) => { S.focus = S.cam.pos.distanceTo(p); if (scale !== undefined) S.dofScale = scale; };
  const yawTo = (a, bx, bz) => Math.atan2(bx - a.x, bz - a.z);
  let PI = 0; const person = (o) => { const p = crowd.people[PI++]; if (!p) return null; Object.assign(p, { on: true, amp: 0, lean: 0, headYaw: 0, headPitch: 0, armL: 0, armR: 0, legs: 0, scale: 1 }, o); if (o.y === undefined) p.y = gy(p.x, p.z); return p; };
  const crowdReset = () => { PI = 0; };
  // single-file line walking along z on a sidewalk
  function line(x, z0, n, spacing, dir, t, speed = 1.3, opts = {}) { for (let k = 0; k < n; k++) { const z = z0 - dir * k * spacing + dir * speed * t; person({ x: x + (opts.jx ? Math.sin(k * 7.1) * opts.jx : 0), z, yaw: dir > 0 ? 0 : Math.PI, amp: 0.6, phase: t * speed * 4.4 + k * 1.7, skin: (k * 5 + (opts.skin || 0)) % 32, ...(opts.o || {}) }); } }
  function scatter(x0, x1, z0, z1, n, seed, t, opts = {}) {
    const r = mulberry(seed); const cell = Math.sqrt((x1 - x0) * (z1 - z0) / n); const out = [];
    for (let x = x0 + cell / 2; x < x1; x += cell) for (let z = z0 + cell / 2; z < z1; z += cell) {
      if (out.length >= n) break; const jx = (r() - 0.5) * cell * 0.6, jz = (r() - 0.5) * cell * 0.6; const a = r() * 6.28; const mv = opts.move ?? 0.4; const sp = r() < 0.6 ? mv : 0;
      const px = x + jx + Math.sin(a) * sp * t, pz = z + jz + Math.cos(a) * sp * t;
      if (opts.avoid && opts.avoid(px, pz)) continue;
      out.push(person({ x: px, z: pz, yaw: opts.yaw ?? a, amp: sp ? 0.5 : 0, phase: t * 4 + r() * 6, skin: Math.floor(r() * 32), ...(opts.o || {}) }));
    }
    return out;
  }
  const inFountain = (x, z) => Math.hypot(x - info.fountain.x, z - info.fountain.z) < 7.2;
  const eastHouses = info.houses.filter(h => h.facing === '-x' && Math.abs(h.front[0] - 15) < 0.6).sort((a, b) => a.porch[1] - b.porch[1]);
  const westHouses = info.houses.filter(h => h.facing === '+x' && Math.abs(h.front[0] + 15) < 0.6).sort((a, b) => a.porch[1] - b.porch[1]);
  const houseNear = (list, z) => list.reduce((b, h) => Math.abs(h.porch[1] - z) < Math.abs(b.porch[1] - z) ? h : b, list[0]);
  const PH = houseNear(eastHouses, 70), NH = houseNear(eastHouses, 88);   // porch man / neighbor
  const FH = houseNear(westHouses, 100);                                   // moving-in family
  const GH = houseNear(eastHouses, 160);                                   // grocery woman / theo's mom
  const plazaShops = info.shops.filter(s => s.name !== 'BAKERY' || s.mid[0] < 0).filter(s => s.facing === '+x' || s.facing === '-x' || s.facing === '-z');
  const plazaBakery = info.shops.find(s => s.name === 'BAKERY' && s.mid[0] < -20);
  const F0 = V(info.fountain.x, 0, info.fountain.z);
  const CHAIR = V(0.5, 0, -63.5);
  const lampNearMayor = V(8, 3.9, -109);

  // plaza crowd placements helpers
  function shadeCrowd(t, k = 1, n = 160, seed = 3) { // people standing in doorways / under awnings along plaza edges
    const r = mulberry(seed); let c = 0;
    for (const s of info.shops) {
      if (!s.normal || c >= n) continue; const [ax, az] = s.a, [bx, bz] = s.b; if (Math.max(Math.abs(ax), Math.abs(bx)) > 45 || az > -40) continue;
      for (let j = 0; j < 4 && c < n; j++) { const f = (j + 0.5) / 4; const x = lerp(ax, bx, f) + s.normal[0] * (0.7 + r() * 0.8) * k, z = lerp(az, bz, f) + s.normal[1] * (0.7 + r() * 0.8) * k; person({ x, z, yaw: Math.atan2(-s.normal[0] * -1, -s.normal[1] * -1) + (r() - 0.5) * 0.6, skin: Math.floor(r() * 32), headYaw: (r() - 0.5) * 0.4 }); c++; }
    }
    return c;
  }

  // ---------------------------------------------------------------- shots
  const REF = await (await fetch('./ref_shots.json')).json();
  const T = (i) => REF[i];
  const shots = [];
  const add = (name, t0, t1, fn) => shots.push({ name, t0, t1, fn });
  const ref = (i, fn, name) => add(name || ('s' + i), T(i).t0, T(i).t1, fn);
  const split = (i, at, fnA, fnB) => { add('s' + i + 'a', T(i).t0, at, fnA); add('s' + i + 'b', at, T(i).t1, fnB); };

  // #0 aerial establishing — descend over town
  ref(0, (lt, u, t, S) => {
    S.tod = 'noon'; const k = eout(u);
    cam(S, V(70, 120, 230), V(22, 24, 112), V(0, 0, 30), V(2, 0, 78), k, 58); S.focus = S.cam.pos.distanceTo(S.cam.look); S.dofScale = 0.25; S.shadowS = 70; S.shadowC.set(0, 0, 80);
    line(6.2, 130, 28, 2.4, -1, t, 1.3); line(-6.2, 40, 28, 2.4, 1, t, 1.3, { skin: 3 }); line(6.2, 210, 20, 2.4, -1, t, 1.3, { skin: 9 });
    show('bus', 2.3, 0, 96 - t * 6, Math.PI); show('car0', -2.4, 0, 70 + t * 7, 0); show('car2', 2.4, 0, 140 - t * 6, Math.PI);
  });
  // #1 top-down street
  ref(1, (lt, u, t, S) => {
    S.tod = 'noon'; cam(S, V(-1, 32, 94), V(-1, 32, 91), V(0, 0, 90), V(0, 0, 87), u, 56); S.focus = 32; S.dofScale = 0.3; S.shadowS = 20; S.shadowC.set(0, 0, 90);
    line(6.0, 104, 10, 2.6, -1, t, 1.4); line(-6.0, 76, 10, 2.6, 1, t, 1.4, { skin: 4 }); show('bus', 2.4, 0, 96 - t * 5, Math.PI); show('bus2', -2.4, 0, 80 + t * 4, 0);
  });
  // #2 single file walking toward camera on sidewalk
  ref(2, (lt, u, t, S) => {
    S.tod = 'morning'; const z = 120 - lt * 1.3;
    cam(S, V(4.4, 1.25, z - 3.2), V(4.6, 1.3, z - 3.0), V(6.6, 1.25, z + 6), V(6.6, 1.3, z + 6), u, 64); focusOn(S, V(6.5, 1.3, z + 1), 1.0); S.shadowC.set(6, 0, z + 6); S.shadowS = 18;
    for (let k = 0; k < 12; k++) person({ x: 6.5, z: z + 1.2 + k * 2.3, yaw: Math.PI, amp: 0.65, phase: t * 5.6 + k * 1.9, skin: (k * 7 + 2) % 32 });
  });
  // #3 sidewalk lanes, low camera, someone walks past
  ref(3, (lt, u, t, S) => {
    S.tod = 'morning'; cam(S, V(6.9, 0.45, 151), V(6.9, 0.5, 150.5), V(6.2, 0.6, 146), V(6.2, 0.9, 146), u, 72); S.distort = 0.25; focusOn(S, V(6.4, 0.6, 149), 0.9); S.shadowC.set(6, 0, 148); S.shadowS = 10;
    person({ x: 6.3, z: 149.6 - lt * 1.25, yaw: Math.PI, amp: 0.7, phase: t * 5.5, skin: 21 }); person({ x: 6.5, z: 142 - lt * 1.25, yaw: Math.PI, amp: 0.65, phase: t * 5.5 + 2, skin: 6 });
  });
  // #4 bus interior, one kid per row
  ref(4, (lt, u, t, S) => {
    S.tod = 'interior'; S.interior = 'bus'; cam(S, V(300.2, 1.35, 7.7), V(300.15, 1.35, 7.3), V(300, 1.15, -3), V(300, 1.15, -3), u, 74); S.focus = 4; S.dofScale = 0.6; S.distort = 0.2;
    interiors.bus.seats.forEach((s, k) => { const row = k % 11; const side = k < 11 ? 0 : 1; if ((row + side) % 2) return; person({ x: s.x, y: s.y - 0.1, z: s.z + 0.05, yaw: Math.PI, legs: -1.45, skin: (k * 3) % 32, headYaw: Math.sin(t + k) * 0.2 }); });
  });
  // #5 bakery exterior then window close-up
  const bk = info.shops.find(s => s.name === 'BAKERY' && s.display);
  split(5, 10.7, (lt, u, t, S) => {
    S.tod = 'noon'; cam(S, V(1.5, 2.4, -3), V(1.8, 2.6, -6), V(9, 2.2, -16), V(9, 2.4, -18), eio(u), 60); focusOn(S, V(8, 2, -16), 0.6); S.shadowC.set(8, 0, -16); S.shadowS = 20;
    line(6.4, -2, 6, 2.5, -1, t, 1.2); person({ x: 7.2, z: -10.5, yaw: Math.PI / 2 + 0.3, skin: 12 }); show('car1', -2.4, 0, -30 + t * 2, 0);
  }, (lt, u, t, S) => {
    S.tod = 'noon'; const p = bk.poster, c = bk.cake;
    cam(S, V(5.6, 1.7, p.z - 0.6), V(7.2, 1.8, p.z - 0.15), V(p.x, 1.6, p.z - 0.2), V(p.x, 1.82, p.z), eio(u), 46); focusOn(S, V(p.x, 1.8, p.z), 1.2); S.shadowC.set(9, 0, p.z); S.shadowS = 8;
  });
  // #6 noon plaza shopping
  ref(6, (lt, u, t, S) => {
    S.tod = 'noon'; cam(S, V(-2.2, 1.6, -54), V(-1.8, 1.6, -57), V(0, 1.4, -80), V(0, 1.4, -83), u, 64); focusOn(S, V(-0.8, 1.2, -58), 0.7); S.shadowC.set(0, 0, -78); S.shadowS = 34;
    scatter(-28, 28, -108, -56, 90, 6, t, { avoid: inFountain, move: 0.6 });
    person({ x: -1.2, z: -57.5 - lt * 1.2, yaw: Math.PI, amp: 0.7, phase: t * 5, skin: 14 }); person({ x: 0.4, z: -58.5 - lt * 1.2, yaw: Math.PI, amp: 0.7, phase: t * 5 + 1.5, skin: 23 });
  });
  // #7 sunset: everyone sprints indoors
  ref(7, (lt, u, t, S) => {
    S.tod = 'sunset'; cam(S, V(0.6, 1.2, 150), V(0.6, 1.3, 151.5), V(0, 2.2, 200), V(0, 2.2, 200), u, 58); S.focus = 30; S.dofScale = 0.5; S.rays = 0.35; S.bloom = 0.3; S.exposure = 0.85; S.shadowC.set(0, 0, 175); S.shadowS = 40;
    const r = mulberry(7); for (let k = 0; k < 24; k++) { const side = k % 2 ? 1 : -1; const z0 = 160 + r() * 50; const x = side * (5.5 + r() * 2) + side * lt * 3; person({ x, z: z0, yaw: side * Math.PI / 2, amp: 1.0, lean: 0.2, phase: t * 13 + k, skin: k % 32 }); }
  });
  // #8 moving in, nobody told us
  ref(8, (lt, u, t, S) => {
    S.tod = 'morning'; const [px, pz] = FH.porch; cam(S, V(-5.5, 2.2, pz + 7), V(-5.5, 2.3, pz + 5.5), V(px - 1, 1.4, pz - 1), V(px - 1, 1.5, pz - 1), u, 58); focusOn(S, V(px + 2, 1.2, pz), 0.7); S.shadowC.set(px, 0, pz); S.shadowS = 14;
    put(heroes.me, px + 3.2, pz + 1.2, Math.PI / 2 + 0.6); idle(heroes.me, t); expr(heroes.me, 'smile', t);
    for (let k = 0; k < 3; k++) { const p = person({ x: px + 1 + k * 1.4, z: pz - 1.5 + Math.sin(k) * 1.2, yaw: -Math.PI / 2 + k, skin: 20 + k, armL: -1.2, armR: -1.2 }); show('box' + k, p.x + Math.sin(p.yaw) * 0.45, 1.25, p.z + Math.cos(p.yaw) * 0.45, p.yaw); }
    show('box3', px + 2.2, 0.25, pz + 2.6, 0.3); show('box4', px + 2.9, 0.25, pz + 2.2, 1.1);
  });
  // #9 walking to school with Theo, shoulder to shoulder
  ref(9, (lt, u, t, S) => {
    S.tod = 'morning'; const z = 70 + lt * 1.1;
    cam(S, V(6.4, 1.25, z + 3.4), V(6.4, 1.3, z + 3.3), V(6.4, 1.15, z), V(6.4, 1.15, z), u, 56); focusOn(S, V(6.4, 1.3, z), 1.4); S.shadowC.set(6, 0, z); S.shadowS = 12;
    put(heroes.me, 5.95, z, 0); walk(heroes.me, t * 5.2, 0.6); expr(heroes.me, 'smile', t, 0.2); lookAt(heroes.me, V(7, 1.4, z + 0.3), 0.3 * Math.sin(t));
    put(heroes.theo, 6.85, z + 0.1, 0); walk(heroes.theo, t * 5.2 + 3.1, 0.6); expr(heroes.theo, 'happy', t, 0.6); lookAt(heroes.theo, V(5.9, 1.4, z), 0.5);
  });
  // #10 shadows cross on the sidewalk (high angle)
  ref(10, (lt, u, t, S) => {
    S.tod = 'morning'; S.sunDir = [-0.75, 0.38, 0.55]; const z = 74 + lt * 1.1;
    cam(S, V(3.6, 6.5, z - 2.5), V(3.8, 6.2, z - 2.0), V(6.6, 0, z + 1.2), V(6.6, 0, z + 1.5), u, 60); focusOn(S, V(6.4, 0.5, z), 0.4); S.shadowC.set(6, 0, z); S.shadowS = 8;
    put(heroes.me, 6.05 + lt * 0.15, z, 0.1); walk(heroes.me, t * 5.2, 0.6); put(heroes.theo, 6.85 - lt * 0.12, z + 0.2, -0.1); walk(heroes.theo, t * 5.2 + 3.1, 0.6);
  });
  // #11 the whole street rose (people turn and stare)
  ref(11, (lt, u, t, S) => {
    S.tod = 'morning'; cam(S, V(-3, 9, 64), V(-3, 8.6, 66), V(4, 0.5, 82), V(4, 0.6, 83), u, 60); S.focus = 18; S.dofScale = 0.3; S.shadowC.set(0, 0, 80); S.shadowS = 26;
    const turn = ease(seg(lt, 0.25, 0.8));
    for (let k = 0; k < 9; k++) person({ x: -6.4, z: 92 - k * 2.6, yaw: lerp(0, Math.PI / 2, turn), amp: 0.6 * (1 - turn), phase: t * 5 + k, skin: (k * 3 + 1) % 32, headYaw: turn * 0.3 });
    for (let k = 0; k < 6; k++) person({ x: 6.4, z: 96 - k * 2.6, yaw: lerp(Math.PI, -Math.PI / 2 + 0.4, turn), amp: 0.6 * (1 - turn), phase: t * 5 + k, skin: (k * 5 + 11) % 32 });
    put(heroes.me, 6.0, 76, 0); put(heroes.theo, 6.8, 76.2, 0);
  });
  // #12 woman drops her groceries
  ref(12, (lt, u, t, S) => {
    S.tod = 'morning'; const [px, pz] = GH.porch; const x = 7.0, z = pz - 3;
    cam(S, V(3.0, 1.2, z - 2.6), V(3.2, 1.15, z - 2.4), V(x, 1.2, z), V(x, 1.0, z), u, 58); focusOn(S, V(x, 1.2, z), 1.0); S.shadowC.set(x, 0, z); S.shadowS = 8;
    put(heroes.grocer, x, z, -Math.PI / 2 - 0.4); expr(heroes.grocer, 'surprised', t); heroes.grocer.shL.rotation.x = -0.4; heroes.grocer.shR.rotation.x = -0.9 + 0.8 * ease(seg(lt, 0.1, 0.3));
    const fall = seg(lt, 0.15, 0.55); const b = show('bag', x - 0.5, lerp(1.2, 0.2, eout(fall)), z - 0.2, 0.3, 0, fall * 1.2);
    oranges.forEach((o, i) => { const a = i * 1.1; const d = fall > 0.9 ? (lt - 0.5) * (0.6 + i * 0.15) : 0; show('or' + i, x - 0.6 + Math.cos(a) * (0.2 + d), lerp(1.0, 0.07, eout(fall)) + Math.abs(Math.sin(lt * 10 + i)) * 0.1 * (1 - fall), z - 0.2 + Math.sin(a) * (0.2 + d), lt * 4); });
  });
  // #13 crossing guard blows his whistle
  ref(13, (lt, u, t, S) => {
    S.tod = 'morning'; const x = 7.0, z = 128.5;
    cam(S, V(3.0, 0.9, z + 3.8), V(4.6, 1.2, z + 2.4), V(x, 1.5, z), V(x, 1.6, z), eio(u), 66); S.distort = 0.2; focusOn(S, V(x, 1.5, z), 0.8); S.shadowC.set(x, 0, z); S.shadowS = 12;
    put(heroes.guard, x, z, yawTo(V(x, 0, z), S.cam.pos.x, S.cam.pos.z) - 0.4); expr(heroes.guard, 'surprised', t);
    const puff = Math.abs(Math.sin(t * 7)); heroes.guard.shR.rotation.x = -1.6 + puff * 0.2; heroes.guard.shR.rotation.z = -0.2; heroes.guard.neck.rotation.x = -0.15 - puff * 0.12; heroes.guard.hips.position.y += puff * 0.03;
    heroes.guard.handL.add(props.stop); props.stop.visible = true; props.stop.position.set(0, -0.1, 0.1); props.stop.rotation.set(-1.5, 0, 0); heroes.guard.shL.rotation.x = -1.5;
  });
  // #14 Theo's mom yanks him into a hedge
  ref(14, (lt, u, t, S) => {
    S.tod = 'morning'; const z = 160;
    cam(S, V(5.0, 1.3, z + 2.8), V(5.2, 1.3, z + 2.5), V(8.4, 1.0, z), V(8.8, 1.0, z), u, 60); focusOn(S, V(8, 1, z), 0.8); S.shadowC.set(8, 0, z); S.shadowS = 10;
    const pull = eio(seg(lt, 0.25, 0.9));
    put(heroes.theo, lerp(6.6, 9.8, pull), z + 0.3, lerp(0, Math.PI / 2, pull)); heroes.theo.torso.rotation.x = 0.3 * pull; heroes.theo.shL.rotation.x = -1.4 * pull; expr(heroes.theo, 'surprised', t);
    put(heroes.mom, lerp(9.2, 10.8, pull), z + 0.5, -Math.PI / 2 + 0.3); heroes.mom.shR.rotation.x = -1.3; heroes.mom.torso.rotation.x = -0.2 * pull; walk(heroes.mom, lt * 8, 0.5 * pull); expr(heroes.mom, 'scared', t);
    put(heroes.me, 6.0, z - 1.4, 0.2); expr(heroes.me, 'surprised', t);
    for (let zz = z - 4; zz < z + 5; zz++) if (Math.abs(zz - z) > 0) { }
  });
  // #15 man on a ladder climbs higher (bakery side wall)
  ref(15, (lt, u, t, S) => {
    S.tod = 'morning'; const lx = 14.5, lz = -24.6;
    show('ladderP', lx, 0, lz - 1.1, 0, 0.16, 0);
    const climb = lt * 0.45; const yb = 3.2 + climb;
    put(heroes.ladder, lx, lz - 0.75 + (yb) * -0.0, Math.PI, 0); heroes.ladder.root.position.set(lx, yb, lz - 0.95 + yb * 0.16 - 0.5); heroes.ladder.root.rotation.y = 0;
    walk(heroes.ladder, t * 4, 0.35); heroes.ladder.shL.rotation.x = -2.6 + Math.sin(t * 4) * 0.3; heroes.ladder.shR.rotation.x = -2.6 - Math.sin(t * 4) * 0.3; heroes.ladder.torso.rotation.x = 0.15;
    cam(S, V(lx + 2.2, 1.0, lz - 4.2), V(lx + 2.0, 0.9, lz - 4.0), V(lx, yb + 1, lz), V(lx, yb + 1.6, lz), u, 70); S.distort = 0.22; focusOn(S, V(lx, yb + 1, lz - 0.8), 0.7); S.shadowC.set(lx, 0, lz); S.shadowS = 12;
  });
  // #16 school hallway: everyone shuffles away
  ref(16, (lt, u, t, S) => {
    S.tod = 'interior'; S.interior = 'hall'; const z = -4 + lt * 1.0;
    cam(S, V(340, 1.45, z + 4.6), V(340, 1.45, z + 4.4), V(340, 1.2, z), V(340, 1.2, z), u, 62); focusOn(S, V(340, 1.3, z), 0.7); S.distort = 0.15;
    put(heroes.me, 340, z, 0); heroes.me.root.position.y = 0; walk(heroes.me, t * 5, 0.55); expr(heroes.me, 'neutral', t);
    let i = 0; for (const zz of [-1, 1.5, 3.5, 5.5, 8, 10.5]) for (const sx of [-1, 1]) { const near = clamp01(1 - Math.abs(zz - z - 1.5) / 3.5); const x = 340 + sx * lerp(1.2, 1.8, Math.max(near, zz < z ? 1 : 0)); person({ x, y: 0, z: zz, yaw: (zz < z) ? 0 : Math.PI, headYaw: sx * 0.6 * near, skin: (i++ * 7) % 32, armL: -0.1, amp: near * 0.3, phase: t * 6 }); }
  });
  // #17 walking alone, people keep away
  ref(17, (lt, u, t, S) => {
    S.tod = 'morning'; const z = 30 - lt * 1.1;
    cam(S, V(6.5, 1.0, z - 3.4), V(6.5, 1.0, z - 3.0), V(6.5, 1.2, z + 2), V(6.5, 1.2, z + 2), u, 66); S.distort = 0.2; focusOn(S, V(6.5, 1.2, z), 1.2); S.shadowC.set(6, 0, z); S.shadowS = 12;
    put(heroes.me, 6.5, z, Math.PI); walk(heroes.me, t * 5, 0.55, 0.1); expr(heroes.me, 'neutral', t); heroes.me.neck.rotation.x = 0.25;
    for (let k = 0; k < 5; k++) person({ x: 6.5, z: z + 8 + k * 3, yaw: Math.PI, amp: 0.6, phase: t * 5 + k, skin: (k * 9) % 32 });
    for (let k = 0; k < 4; k++) person({ x: 6.0 + (k % 2), z: z - 9 - k * 3, yaw: 0, amp: 0.6, phase: t * 5 + k, skin: (k * 4 + 3) % 32, headYaw: 0.5 });
  });
  // #18 corner market: nobody would say why
  ref(18, (lt, u, t, S) => {
    S.tod = 'morning'; const mk = info.shops.find(s => s.name === 'CORNER MARKET'); const [mx, mz] = mk.mid;
    cam(S, V(3.5, 2.4, mz + 2.5), V(3.2, 2.4, mz + 1.6), V(mx - 2, 2.8, mz), V(mx - 2, 2.8, mz), u, 56); focusOn(S, V(mx + 1.5, 1.2, mz), 0.6); S.shadowC.set(mx, 0, mz); S.shadowS = 14;
    put(heroes.me, -6.6, mz + 0.4, -Math.PI / 2 + 0.4); expr(heroes.me, 'neutral', t); lookAt(heroes.me, V(mx - 1, 1.5, mz), 0.7);
    person({ x: mx + 1.3, z: mk.door[1], yaw: Math.PI / 2, skin: 30, armR: -0.4 });
  });
  // #19 that evening the sun went orange
  ref(19, (lt, u, t, S) => {
    S.tod = 'golden'; cam(S, V(-3.2, 1.6, 80), V(-3.0, 1.6, 82), V(-6, 1.2, 100), V(-6, 1.2, 102), u, 62); focusOn(S, V(-6.5, 1.2, 92), 0.6); S.shadowC.set(-4, 0, 90); S.shadowS = 25; S.rays = 0.3;
    person({ x: -6.6, z: 90 + lt * 1.2, yaw: 0, amp: 0.65, phase: t * 5.5, skin: 4 }); person({ x: -6.4, z: 99 + lt * 1.2, yaw: 0, amp: 0.6, phase: t * 5.5 + 2, skin: 17 });
  });
  // #20 shadows stretching (low tilted camera on the street)
  ref(20, (lt, u, t, S) => {
    S.tod = 'sunset'; cam(S, V(2.0, 0.55, 60), V(2.2, 0.6, 62.5), V(-3, 0, 52), V(-3, 0, 54), u, 70); S.cam.roll = 0.35; S.distort = 0.25; S.focus = 4; S.dofScale = 0.5; S.shadowC.set(0, 0, 58); S.shadowS = 30;
    for (let k = 0; k < 8; k++) person({ x: k % 2 ? 6.4 : -6.4, z: 72 + k * 4, yaw: Math.PI, amp: 0.6, phase: t * 5 + k, skin: (k * 5) % 32 });
  });
  // #21 long black fingers: silhouettes against the sun
  ref(21, (lt, u, t, S) => {
    S.tod = 'sunset'; cam(S, V(0.4, 1.0, 120), V(0.4, 1.0, 121.5), V(0, 2.4, 170), V(0, 2.4, 170), u, 56); S.focus = 22; S.dofScale = 0.5; S.rays = 0.35; S.bloom = 0.3; S.exposure = 0.85; S.shadowC.set(0, 0, 135); S.shadowS = 30;
    for (let k = 0; k < 6; k++) person({ x: (k % 2 ? 1 : -1) * (2 + k * 0.6), z: 136 + k * 3.5 + lt * 0.8, yaw: 0, amp: 0.6, phase: t * 5 + k, skin: (k * 7) % 32 });
  });
  // #22 man runs for his porch; shadows overlap on the fence
  const FZ = NH.porch[1] - 4.5;
  ref(22, (lt, u, t, S) => {
    S.tod = 'sunset'; S.sunDir = [0.32, 0.1, 0.94]; const [px, pz] = PH.porch;
    const run = eio(seg(lt, 0, 3.0)); const mx = lerp(7.2, px - 0.3, run), mz = lerp(pz + 7, pz, run);
    show('fence', 8.8, 0, FZ, 0);
    put(heroes.porchman, mx, mz, yawTo(V(mx, 0, mz), px, pz)); walk(heroes.porchman, t * 12, 0.95 * (1 - seg(lt, 2.7, 3.2)), 0.2); expr(heroes.porchman, 'scared', t);
    put(heroes.neighbor, 11.5, FZ + 1.2, Math.PI - 0.3); idle(heroes.neighbor, t); expr(heroes.neighbor, 'neutral', t);
    const k = eio(u); cam(S, V(4.5, 2.2, pz + 12), V(5.5, 9, FZ + 6), V(9.5, 0.8, pz + 3), V(11, 0, FZ - 2), k, 60); focusOn(S, V(10, 0.5, FZ), 0.5); S.shadowC.set(10, 0, FZ - 2); S.shadowS = 16;
  });
  // #23 just for a second (wide houses)
  ref(23, (lt, u, t, S) => { S.tod = 'sunset'; cam(S, V(-4, 2.0, FZ - 6), V(-4, 2.0, FZ - 5), V(15, 3.5, FZ + 2), V(15, 3.5, FZ + 2), u, 58); S.focus = 18; S.dofScale = 0.4; S.shadowC.set(10, 0, FZ); S.shadowS = 22;
    put(heroes.porchman, PH.porch[0] - 0.2, PH.porch[1], -Math.PI / 2, 1); put(heroes.neighbor, 11.5, FZ + 1.2, Math.PI - 0.3); });
  // #24 shadows turn to tar, something climbs out of the seam
  const SEAM = V(10.4, 0, FZ - 1.5);
  split(24, 51.9, (lt, u, t, S) => {
    S.tod = 'sunset'; S.sunDir = [0.32, 0.1, 0.94];
    cam(S, V(6.0, 7.5, SEAM.z + 7), V(6.4, 6.8, SEAM.z + 5.5), V(SEAM.x, 0, SEAM.z), V(SEAM.x, 0, SEAM.z - 0.5), u, 60); focusOn(S, SEAM, 0.4); S.shadowC.copy(SEAM); S.shadowS = 14;
    show('fence', 8.8, 0, FZ, 0); put(heroes.neighbor, 11.5, FZ + 1.2, Math.PI - 0.3); put(heroes.porchman, PH.porch[0] - 0.2, PH.porch[1], -Math.PI / 2);
    const k = ease(seg(lt, 0.3, 2.0)); decals[0].set(SEAM.x, 0.05, SEAM.z, 1.2 + k * 0.8, 3.5 + k * 1.5, 0.6 + 0.35 * k, 0.3); decals[1].set(SEAM.x + 0.6, 0.051, SEAM.z - 2.5, 0.8 * k + 0.01, 2.5, 0.9 * k, -0.4);
  }, (lt, u, t, S) => {
    S.tod = 'sunset'; S.sunDir = [0.32, 0.1, 0.94]; const rise = eout(seg(lt, 0.1, 2.3));
    cam(S, V(SEAM.x - 3.5, 0.8, SEAM.z + 5), V(SEAM.x - 3.8, 0.7, SEAM.z + 5.4), V(SEAM.x, 3 + rise * 5, SEAM.z), V(SEAM.x, 4 + rise * 6, SEAM.z), u, 66); S.distort = 0.2; focusOn(S, SEAM, 0.5); S.shadowC.copy(SEAM); S.shadowS = 16;
    show('fence', 8.8, 0, FZ, 0); decals[0].set(SEAM.x, 0.05, SEAM.z, 2.0, 5, 0.95, 0.3);
    creature.root.visible = true; creature.root.position.copy(SEAM); creature.root.scale.set(0.8, 0.8 * Math.max(0.02, rise), 0.8); creature.root.rotation.y = Math.atan2(-3.5, 5); creature.torso.rotation.x = 0.4 * (1 - rise); creature.shL.rotation.z = 0.6 * (1 - rise); creature.shR.rotation.z = -0.6 * (1 - rise);
  });
  const standThing = (s = 0.8) => { creature.root.visible = true; creature.root.position.copy(SEAM); creature.root.scale.setScalar(s); };
  // #25 tall thin flat as paper (look up, then edge-on)
  ref(25, (lt, u, t, S) => {
    S.tod = 'sunset'; standThing(0.8); creature.root.rotation.y = lerp(0.6, 0.6 + Math.PI / 2, eio(u)); creature.shL.rotation.z = 0.1; creature.shR.rotation.z = -0.1;
    cam(S, V(SEAM.x - 6, 0.6, SEAM.z + 7), V(SEAM.x - 6.5, 0.6, SEAM.z + 6), V(SEAM.x, 8, SEAM.z), V(SEAM.x, 8.5, SEAM.z), u, 70); S.distort = 0.2; S.focus = 10; S.dofScale = 0.3; S.rays = 0.6; S.shadowC.copy(SEAM); S.shadowS = 20;
    put(heroes.neighbor, 11.5, FZ + 1.2, Math.PI - 0.3); expr(heroes.neighbor, 'scared', t);
  });
  // #26 no face, no front, no back — orbit close on the silhouette
  ref(26, (lt, u, t, S) => {
    S.tod = 'sunset'; standThing(0.8); creature.root.rotation.y = 0.2; creature.neck.rotation.z = 0.15 * Math.sin(lt * 1.5);
    const a = lerp(-0.6, 0.5, eio(u)); const c = V(SEAM.x, 9.5, SEAM.z);
    cam(S, V(c.x + Math.sin(a) * 7, 6.5, c.z + Math.cos(a) * 7), V(c.x + Math.sin(a) * 7, 6.5, c.z + Math.cos(a) * 7), c, c, 1, 58); S.focus = 7; S.dofScale = 0.6; S.shadowC.copy(SEAM); S.shadowS = 16;
  });
  // #27 stood between the two men, turning its head (choosing)
  ref(27, (lt, u, t, S) => {
    S.tod = 'sunset'; standThing(0.8); creature.root.rotation.y = -Math.PI / 2 + 0.2; creature.neck.rotation.y = 1.0 * Math.sin(lt * 1.6); creature.torso.rotation.x = 0.12;
    put(heroes.neighbor, 11.5, FZ + 1.2, Math.PI - 0.3); expr(heroes.neighbor, 'scared', t); put(heroes.porchman, PH.porch[0] - 0.2, PH.porch[1], -Math.PI / 2 - 0.4); expr(heroes.porchman, 'scared', t);
    show('fence', 8.8, 0, FZ, 0);
    cam(S, V(-1.5, 2.2, SEAM.z - 2), V(-1.0, 2.2, SEAM.z - 1.2), V(SEAM.x, 5, SEAM.z + 2), V(SEAM.x, 5, SEAM.z + 2), u, 64); S.focus = 12; S.dofScale = 0.35; S.rays = 0.4; S.shadowC.copy(SEAM); S.shadowS = 20;
  });
  // #28 it folds around the man on the porch; they slide into the pavement; shoes left
  split(28, 64.0, (lt, u, t, S) => {
    S.tod = 'sunset'; const [px, pz] = PH.porch; const wrapK = eio(seg(lt, 0.2, 1.8)), sink = eio(seg(lt, 1.6, 2.8));
    put(heroes.porchman, px + 0.6, pz, -Math.PI / 2, 1 - 0.0); heroes.porchman.root.position.y = 1 - sink * 2.2; heroes.porchman.root.scale.set(1 - sink * 0.6, 1, 1 - sink * 0.6); expr(heroes.porchman, 'scared', t); heroes.porchman.shL.rotation.z = 0.5; heroes.porchman.shR.rotation.z = -0.5;
    creature.root.visible = true; creature.root.position.set(px - 1.0, -sink * 6, pz); creature.root.scale.set(0.55 * (1 - wrapK * 0.5), 0.55, 0.55); creature.root.rotation.y = Math.PI / 2;
    creature.torso.rotation.x = 0.9 * wrapK; creature.shL.rotation.x = -2.2 * wrapK; creature.shR.rotation.x = -2.2 * wrapK; creature.shL.rotation.z = -0.6 * wrapK; creature.shR.rotation.z = 0.6 * wrapK;
    cam(S, V(px - 7.5, 2.0, pz + 2.5), V(px - 7.0, 2.1, pz + 2.2), V(px + 0.5, 1.8, pz), V(px + 0.5, 1.4, pz), u, 60); focusOn(S, V(px, 1.5, pz), 0.5); S.shadowC.set(px, 0, pz); S.shadowS = 12;
  }, (lt, u, t, S) => {
    S.tod = 'sunset'; const [px, pz] = PH.porch; show('shoes', px + 0.6, 1.0, pz, Math.PI / 2 + 0.2);
    cam(S, V(px - 1.8, 1.45, pz + 0.7), V(px - 1.6, 1.4, pz + 0.6), V(px + 0.6, 1.0, pz), V(px + 0.6, 1.0, pz), u, 52); focusOn(S, V(px + 0.6, 1.0, pz), 0.9); S.shadowC.set(px, 0, pz); S.shadowS = 8;
  });
  // #29 next morning, bike
  ref(29, (lt, u, t, S) => {
    S.tod = 'morning'; const [gx, gz] = FH.garage; const k = eio(seg(lt, 0, 2.3)); const x = lerp(gx - 1, -6, k), z = gz + Math.sin(k * 3) * 0.3;
    put(heroes.me, x, z, Math.PI / 2 - 0.2 + k * 0.8, 0.35); heroes.me.lgL.rotation.x = -0.9 + Math.sin(t * 8) * 0.5; heroes.me.lgR.rotation.x = -0.9 - Math.sin(t * 8) * 0.5; heroes.me.shL.rotation.x = heroes.me.shR.rotation.x = -1.1; expr(heroes.me, 'neutral', t);
    show('bike', x, 0.02, z, Math.PI / 2 - 0.2 + k * 0.8);
    cam(S, V(gx - 2, 1.3, gz + 5), V(gx - 2.6, 1.3, gz + 4.6), V(gx - 2, 1.0, gz), V(-5, 1.0, gz), u, 60); focusOn(S, V(x, 1.0, z), 0.8); S.shadowC.set(gx, 0, gz); S.shadowS = 12;
  });
  // #30 I could see the sign
  ref(30, (lt, u, t, S) => {
    S.tod = 'morning'; const z = 200 + lt * 6; put(heroes.me, 2.4, z, 0, 0.35); heroes.me.lgL.rotation.x = -0.9 + Math.sin(t * 9) * 0.5; heroes.me.lgR.rotation.x = -0.9 - Math.sin(t * 9) * 0.5; heroes.me.shL.rotation.x = heroes.me.shR.rotation.x = -1.1;
    show('bike', 2.4, 0.02, z, 0); cam(S, V(2.6, 1.2, z - 3.5), V(2.6, 1.2, z - 3.5), V(2.4, 1.3, z + 30), V(2.4, 1.3, z + 30), 1, 58); S.focus = 4; S.dofScale = 0.5; S.shadowC.set(2, 0, z + 10); S.shadowS = 25;
  });
  // #31 the highway
  ref(31, (lt, u, t, S) => {
    S.tod = 'morning'; cam(S, V(-22, 22, 228), V(-20, 22, 230), V(2, 0, 252), V(4, 0, 253), u, 58); S.focus = 30; S.dofScale = 0.3; S.shadowC.set(0, 0, 250); S.shadowS = 40;
    show('truck1', -10 + lt * 14, 0, 250, Math.PI / 2); show('truck2', 30 - lt * 12, 0, 256, -Math.PI / 2); show('car3', -40 + lt * 16, 0, 249, Math.PI / 2); show('truck3', 60 - lt * 13, 0, 257, -Math.PI / 2);
  });
  // #32 people stepping out of their houses
  ref(32, (lt, u, t, S) => {
    S.tod = 'morning'; cam(S, V(3.2, 1.7, 197), V(3.2, 1.7, 196), V(12, 1.3, 185), V(12, 1.3, 184), u, 62); S.focus = 10; S.dofScale = 0.4; S.shadowC.set(10, 0, 185); S.shadowS = 30;
    for (const h of eastHouses.concat(westHouses)) { if (h.porch[1] < 140 || h.porch[1] > 215) continue; for (let k = 0; k < 2; k++) { const st = k * 0.6; const kk = clamp01((lt - st) / 1.6); const sx = h.facing === '-x' ? -1 : 1; person({ x: h.porch[0] + sx * kk * 3.5 + k * 0.5 * sx, z: h.porch[1] + k * 0.8, yaw: sx > 0 ? Math.PI / 2 : -Math.PI / 2, amp: kk > 0 && kk < 1 ? 0.6 : 0, phase: t * 5 + k, skin: (Math.floor(h.porch[1]) + k * 13) % 32 }); } }
  });
  // #33 dozens, then hundreds (aerial)
  const checker = (t, n = 400, z0 = 150, z1 = 214, k = 1) => { let c = 0; for (let z = z0; z < z1; z += 2.4) for (let x = -13.2; x <= 13.3; x += 2.4) { const ix = Math.round(x / 2.4), iz = Math.round(z / 2.4); if (((ix + iz) & 1) || c >= n) continue; const f = mulberry(ix * 31 + iz)(); if (f > k) continue; person({ x, z, yaw: Math.PI, skin: (ix * 7 + iz * 3) & 31, headYaw: Math.sin(t * 0.5 + ix) * 0.2 }); c++; } return c; };
  ref(33, (lt, u, t, S) => { S.tod = 'morning'; cam(S, V(0, 36, 228), V(0, 40, 230), V(0, 0, 186), V(0, 0, 186), u, 56); S.focus = 45; S.dofScale = 0.2; S.shadowC.set(0, 0, 185); S.shadowS = 45; checker(t, 420, 150, 220, lerp(0.35, 1, eout(u))); });
  // #34 perfect checkerboard
  ref(34, (lt, u, t, S) => { S.tod = 'morning'; const k = eio(u); cam(S, V(0, 30, 196), V(0, 16, 186), V(0, 0, 185.9), V(0, 0, 175.9), k, 58); S.focus = S.cam.pos.y; S.dofScale = 0.25; S.shadowC.set(0, 0, 182); S.shadowS = 34; checker(t, 420, 150, 220); });
  // #35 the mayor stepped forward
  const MAYZ = 166;
  ref(35, (lt, u, t, S) => { S.tod = 'morning'; const z = MAYZ + 3 - lt * 1.0; put(heroes.mayor, 0.4, z, Math.PI); walk(heroes.mayor, t * 4.5, 0.5); expr(heroes.mayor, 'neutral', t);
    cam(S, V(-0.6, 1.5, z - 4), V(-0.6, 1.5, z - 3.6), V(0.4, 1.6, z), V(0.4, 1.6, z), u, 60); focusOn(S, V(0.4, 1.6, z), 0.9); S.shadowC.set(0, 0, z); S.shadowS = 14; checker(t, 420, 168, 220); });
  // #36 even his shadow wore a little hat
  ref(36, (lt, u, t, S) => { S.tod = 'morning'; S.sunDir = [0.15, 0.42, 0.9]; const z = MAYZ; put(heroes.mayor, 0.4, z, Math.PI);
    cam(S, V(0.7, 6.0, z - 1.6), V(0.7, 5.8, z - 1.5), V(0.4, 0, z - 2.7), V(0.4, 0, z - 2.6), u, 60); focusOn(S, V(0.4, 0, z - 3.5), 0.4); S.shadowC.set(0, 0, z - 3); S.shadowS = 8; checker(t, 60, 168, 190); });
  // #37 "you crossed a shadow," he said
  ref(37, (lt, u, t, S) => { S.tod = 'morning'; put(heroes.mayor, 0.4, MAYZ, Math.PI); idle(heroes.mayor, t); expr(heroes.mayor, 'neutral', t); heroes.mayor.shR.rotation.x = -0.5 - 0.3 * Math.sin(t * 3);
    cam(S, V(-4.5, 1.4, MAYZ - 6), V(-4.2, 1.4, MAYZ - 5.6), V(0.4, 1.6, MAYZ), V(0.4, 1.6, MAYZ), u, 62); focusOn(S, V(0.4, 1.6, MAYZ), 0.6); S.shadowC.set(0, 0, MAYZ); S.shadowS = 16; checker(t, 300, 168, 220);
    put(heroes.me, 0.5, MAYZ - 3.5, 0); });
  // #38 over the mayor's shoulder: tonight it comes for you or the boy
  ref(38, (lt, u, t, S) => { S.tod = 'morning'; put(heroes.mayor, 0.4, MAYZ, Math.PI); idle(heroes.mayor, t);
    put(heroes.me, 0.6, MAYZ - 3.2, 0); expr(heroes.me, 'scared', t); idle(heroes.me, t);
    cam(S, V(-0.3, 1.9, MAYZ + 1.6), V(-0.2, 1.9, MAYZ + 1.4), V(0.6, 1.2, MAYZ - 3.2), V(0.6, 1.2, MAYZ - 3.2), u, 60); focusOn(S, V(0.6, 1.3, MAYZ - 3.2), 0.9); S.shadowC.set(0, 0, MAYZ); S.shadowS = 14; checker(t, 300, 168, 220); });
  // #39 he pointed back toward the square
  ref(39, (lt, u, t, S) => { S.tod = 'morning'; put(heroes.mayor, 0.4, MAYZ, Math.PI); const pt = ease(seg(lt, 1.2, 1.7)); heroes.mayor.shR.rotation.x = -1.55 * pt; heroes.mayor.root.rotation.y = Math.PI + pt * 0.0; expr(heroes.mayor, 'neutral', t); heroes.mayor.neck.rotation.y = 0.3 * pt;
    cam(S, V(-1.4, 1.0, MAYZ + 2.8), V(-1.6, 1.0, MAYZ + 3.4), V(0.4, 1.8, MAYZ - 2), V(0.4, 1.8, MAYZ - 4), u, 68); S.distort = 0.2; focusOn(S, V(0.4, 1.8, MAYZ), 0.6); S.shadowC.set(0, 0, MAYZ); S.shadowS = 16; checker(t, 300, 172, 220);
    put(heroes.me, 1.6, MAYZ + 2.2, 0); expr(heroes.me, 'scared', t); });
  // #40 they sat me down in the middle of the square at sunset; town backs away
  split(40, 88.6, (lt, u, t, S) => {
    S.tod = 'golden'; const k = eio(seg(lt, 0, 2.2)); const z = lerp(-55, -63.5, k);
    put(heroes.me, 0.5, z, Math.PI, 0.4); sit(heroes.me); heroes.me.root.position.y = 0.05; expr(heroes.me, 'scared', t); show('chair', 0.5, 0, z + 0.1, Math.PI);
    for (const [dx, dz, sk] of [[-0.9, 0.2, 5], [0.9, 0.3, 9], [-0.8, 1.3, 13], [0.8, 1.3, 18]]) person({ x: 0.5 + dx, z: z + dz, yaw: Math.PI, amp: 0.55, phase: t * 5 + dz * 3, skin: sk, armL: -0.9, armR: -0.9 });
    cam(S, V(-1.5, 1.4, z - 3.2), V(-1.5, 1.4, z - 2.8), V(0.5, 1.2, z), V(0.5, 1.2, z), u, 62); focusOn(S, V(0.5, 1.2, z), 0.8); S.shadowC.set(0, 0, z - 5); S.shadowS = 16;
  }, (lt, u, t, S) => {
    S.tod = 'golden'; put(heroes.me, CHAIR.x, CHAIR.z, Math.PI); sit(heroes.me); heroes.me.root.position.y = 0.5; show('chair', CHAIR.x, 0, CHAIR.z + 0.1, Math.PI);
    const back = eio(seg(lt, 0, 2.5)); const r = mulberry(44);
    for (let k = 0; k < 120; k++) { const ang = r() * 6.28; const d0 = 6 + r() * 14; const sx = Math.cos(ang), sz = Math.sin(ang); let x = CHAIR.x + sx * d0, z = CHAIR.z - 15 + sz * d0 * 1.3; const ex = Math.sign(x) * 29.5, ez = z; x = lerp(x, Math.abs(x) > 12 ? ex : x, back); z = lerp(z, Math.abs(x) <= 12 ? (z > -82 ? -54.5 : -109.5) : z, back);
      if (inFountain(x, z)) continue; person({ x, z, yaw: Math.atan2(CHAIR.x - x, CHAIR.z - z), amp: back < 1 ? 0.5 : 0, phase: t * 4 + k, skin: k & 31 }); }
    cam(S, V(0.5, 3.5, -100), V(0.5, 3.6, -99), V(0.5, 0.8, -60), V(0.5, 0.8, -60), u, 50); S.focus = 37; S.dofScale = 0.3; S.rays = 0.3; S.bloom = 0.3; S.exposure = 0.88; S.shadowC.set(0, 0, -80); S.shadowS = 40;
  });
  // #41 into the shade (people under awnings), then the only shadow in the square (top-down)
  split(41, 93.4, (lt, u, t, S) => {
    S.tod = 'sunset'; cam(S, V(-22, 1.7, -76), V(-22.5, 1.7, -78), V(-31, 1.6, -88), V(-31, 1.6, -91), u, 60); focusOn(S, V(-30, 1.5, -86), 0.6); S.shadowC.set(-25, 0, -82); S.shadowS = 20;
    shadeCrowd(t, 1, 140);
  }, (lt, u, t, S) => {
    S.tod = 'sunset'; put(heroes.me, CHAIR.x, CHAIR.z, Math.PI); sit(heroes.me); heroes.me.root.position.y = 0.5; show('chair', CHAIR.x, 0, CHAIR.z + 0.1, Math.PI); decals[2].set(CHAIR.x, 0.045, CHAIR.z - 0.4 - 4.5, 0.42, 4.5, 0.7);
    cam(S, V(1.5, 13, -64), V(1.5, 12.4, -65), V(0.5, 0, -68.5), V(0.5, 0, -69.5), u, 60); S.focus = 13; S.dofScale = 0.2; S.shadowC.set(0.5, 0, -72); S.shadowS = 16; shadeCrowd(t, 1, 140);
  });
  // #42 the shadow stretches longer and longer
  ref(42, (lt, u, t, S) => {
    S.tod = 'golden'; S.tod2 = 'sunset'; S.todK = eio(u); const el = lerp(0.2, 0.05, eio(u)); S.sunDir = [0.04, el, 1]; { const L = lerp(5, 11, eio(u)); decals[2].set(CHAIR.x, 0.045, CHAIR.z - 0.4 - L / 2, 0.42, L / 2, 0.7); }
    put(heroes.me, CHAIR.x, CHAIR.z, Math.PI); sit(heroes.me); heroes.me.root.position.y = 0.5; show('chair', CHAIR.x, 0, CHAIR.z + 0.1, Math.PI);
    cam(S, V(-2.6, 1.3, CHAIR.z + 2.5), V(-2.4, 1.2, CHAIR.z + 1.8), V(0.5, 0.2, CHAIR.z - 8), V(0.5, 0.2, CHAIR.z - 10), u, 64); S.focus = 9; S.dofScale = 0.4; S.shadowC.set(0.5, 0, CHAIR.z - 10); S.shadowS = 18; S.rays = 0.3; shadeCrowd(t, 1, 80);
  });
  // #43 all the way to the fountain
  ref(43, (lt, u, t, S) => {
    S.tod = 'sunset'; S.sunDir = [0.04, 0.045, 1]; decals[2].set(CHAIR.x, 0.045, CHAIR.z - 0.4 - 6, 0.42, 6, 0.72); put(heroes.me, CHAIR.x, CHAIR.z, Math.PI); sit(heroes.me); heroes.me.root.position.y = 0.5; show('chair', CHAIR.x, 0, CHAIR.z + 0.1, Math.PI);
    cam(S, V(-5, 1.0, F0.z + 9.5), V(-5.3, 1.0, F0.z + 10), V(F0.x, 0.6, F0.z + 5), V(F0.x, 0.6, F0.z + 5), u, 64); S.distort = 0.18; S.focus = 7; S.dofScale = 0.5; S.shadowC.set(0.5, 0, -75); S.shadowS = 18;
  });
  // #44 "don't move," the mayor called from the shade
  ref(44, (lt, u, t, S) => {
    S.tod = 'sunset'; put(heroes.mayor, 0.5, -114.6, 0); idle(heroes.mayor, t); heroes.mayor.shR.rotation.x = -0.9 * ease(seg(lt, 0.3, 0.7)); expr(heroes.mayor, 'neutral', t);
    cam(S, V(0.5, 3.0, -86), V(0.5, 3.2, -88), V(0.5, 5, -116), V(0.5, 5, -116), u, 50); S.focus = 27; S.dofScale = 0.4; S.shadowC.set(0, 0, -105); S.shadowS = 25; shadeCrowd(t, 1, 80);
  });
  // #45 street lights die one by one; the thing climbs out of my shadow
  split(45, 101.7, (lt, u, t, S) => {
    S.tod = 'dusk'; S.lamps = lt < 0.7 ? 'on' : 'off'; const L = V(-3.5, 3.9, -55);
    cam(S, V(-1.5, 1.6, -58.8), V(-1.6, 1.6, -58.6), L.clone().add(V(0, -0.8, 0)), L.clone().add(V(0, -0.8, 0)), u, 50); S.focus = 4.6; S.dofScale = 0.6; S.shadowC.set(-4, 0, -58); S.shadowS = 12;
  }, (lt, u, t, S) => {
    S.tod = 'night'; S.lamps = 'off'; const rise = eout(seg(lt, 0.4, 2.3));
    put(heroes.me, CHAIR.x, CHAIR.z, Math.PI); sit(heroes.me); heroes.me.root.position.y = 0.5; show('chair', CHAIR.x, 0, CHAIR.z + 0.1, Math.PI); expr(heroes.me, 'scared', t);
    decals[0].set(CHAIR.x, 0.04, CHAIR.z - 1.5, 1.2, 2.4, 0.9);
    creature.root.visible = true; creature.root.position.set(CHAIR.x, 0, CHAIR.z - 1.6); creature.root.scale.set(0.5, 0.5 * Math.max(0.02, rise), 0.5); creature.root.rotation.y = 0;
    cam(S, V(CHAIR.x + 1.5, 1.4, CHAIR.z + 4), V(CHAIR.x + 1.6, 1.4, CHAIR.z + 4.4), V(CHAIR.x, 1.6 + rise * 2, CHAIR.z - 1.5), V(CHAIR.x, 2.0 + rise * 2.5, CHAIR.z - 1.5), u, 62); focusOn(S, V(CHAIR.x, 1.4, CHAIR.z), 0.6); S.shadowC.set(0, 0, CHAIR.z); S.shadowS = 12;
  });
  // night plaza setup helper
  const nightPlaza = (S, t, opts = {}) => { S.tod = 'night'; S.lamps = opts.lamps ?? 'off'; put(heroes.me, CHAIR.x, CHAIR.z, Math.PI); sit(heroes.me); heroes.me.root.position.y = 0.5; show('chair', CHAIR.x, 0, CHAIR.z + 0.1, Math.PI); expr(heroes.me, 'scared', t); if (opts.crowd !== false) shadeCrowd(t, 1, opts.n ?? 120); };
  const thingAt = (s, x = CHAIR.x, z = CHAIR.z - 2.2, yaw = 0) => { creature.root.visible = true; creature.root.position.set(x, 0, z); creature.root.scale.setScalar(s); creature.root.rotation.y = yaw; return creature; };
  // #46 it rose up taller than the town hall and bent down
  ref(46, (lt, u, t, S) => {
    nightPlaza(S, t); const grow = eout(seg(lt, 0, 2.5)); const bend = eio(seg(lt, 2.6, 4.4));
    const c = thingAt(lerp(0.6, 2.3, grow)); c.torso.rotation.x = 0.9 * bend; c.neck.rotation.x = 0.5 * bend; c.shL.rotation.z = 0.25; c.shR.rotation.z = -0.25; decals[0].set(CHAIR.x, 0.04, CHAIR.z - 1.5, 1.4, 2.6, 0.92);
    cam(S, V(10, 1.2, -55.5), V(9, 1.4, -54.5), V(1, 10, -66), V(1, 12, -66), u, 66); S.distort = 0.15; S.focus = 17; S.dofScale = 0.35; S.shadowC.set(0, 0, -68); S.shadowS = 30;
  });
  // #47 its faceless head an inch from mine
  ref(47, (lt, u, t, S) => {
    nightPlaza(S, t, { crowd: false }); const c = thingAt(1.15, CHAIR.x, CHAIR.z - 7.4); c.hips.position.y = 1.6; c.lgL.rotation.x = -1.2; c.lgR.rotation.x = -1.0; c.torso.rotation.x = 1.42; c.neck.rotation.x = 0.1; c.neck.rotation.z = 0.25 * Math.sin(lt * 1.3); c.shL.rotation.x = -1.2; c.shR.rotation.x = -1.3; c.shL.rotation.z = 0.5; c.shR.rotation.z = -0.5;
    cam(S, V(CHAIR.x + 3.2, 1.6, CHAIR.z + 0.5), V(CHAIR.x + 3.4, 1.6, CHAIR.z + 0.8), V(CHAIR.x - 0.2, 2.2, CHAIR.z - 0.6), V(CHAIR.x - 0.2, 2.2, CHAIR.z - 0.6), u, 58); focusOn(S, V(CHAIR.x, 1.5, CHAIR.z), 0.8); S.shadowC.set(0, 0, CHAIR.z); S.shadowS = 12;
    lookAt(heroes.me, V(CHAIR.x, 3, CHAIR.z - 1.5), 0.8);
  });
  // #48 it reached one long arm down and touched my shadow; nothing happened
  ref(48, (lt, u, t, S) => {
    nightPlaza(S, t); const c = thingAt(2.3); c.torso.rotation.x = 0.7; const reach = eio(seg(lt, 0.2, 1.6)) * (1 - eio(seg(lt, 2.6, 3.4))) + eio(seg(lt, 3.4, 4.0)) * 0.8;
    c.shR.rotation.x = lerp(0, -0.5, reach); c.shR.rotation.z = lerp(-0.2, 0.15, reach); decals[0].set(CHAIR.x, 0.04, CHAIR.z - 1.5, 1.2, 2.6, 0.9);
    cam(S, V(-6, 1.0, CHAIR.z - 9), V(-6.4, 1.0, CHAIR.z - 9.5), V(CHAIR.x, 2.5, CHAIR.z - 2), V(CHAIR.x, 2.5, CHAIR.z - 2), u, 64); S.distort = 0.15; focusOn(S, V(CHAIR.x, 1, CHAIR.z - 2), 0.5); S.shadowC.set(0, 0, CHAIR.z - 3); S.shadowS = 18;
  });
  // #49 it tilted its head like it didn't understand
  ref(49, (lt, u, t, S) => {
    nightPlaza(S, t); const c = thingAt(2.3); c.torso.rotation.x = 0.35; c.neck.rotation.z = 0.5 * ease(seg(lt, 0.6, 1.4)); c.shL.rotation.z = 0.5; c.shR.rotation.z = -0.6; c.shR.rotation.x = -0.3;
    cam(S, V(14, 1.6, -54), V(13.5, 1.6, -53.5), V(1, 11, -66), V(1, 11, -66), u, 62); S.focus = 18; S.dofScale = 0.35; S.shadowC.set(0, 0, -66); S.shadowS = 30;
  });
  // #50 then footsteps (shop doorways at night)
  ref(50, (lt, u, t, S) => {
    S.tod = 'night'; S.lamps = 'off'; const s = plazaShops.find(s => s.facing === '+x' && s.mid[1] < -80) || plazaShops[0]; const [mx, mz] = s.mid;
    cam(S, V(mx + 9, 1.6, mz + 2), V(mx + 8.6, 1.6, mz + 1.8), V(mx, 1.8, mz), V(mx, 1.8, mz), u, 58); focusOn(S, V(mx + 1, 1.2, mz), 0.6); S.shadowC.set(mx + 4, 0, mz); S.shadowS = 12;
    shadeCrowd(t, 1, 140); put(heroes.theo, mx + 1.2, mz - 1.5, Math.PI / 2); expr(heroes.theo, 'scared', t);
  });
  // #51 Theo runs into the square yelling my name
  ref(51, (lt, u, t, S) => {
    nightPlaza(S, t); const s0 = V(-28, 0, -86); const k = clamp01(lt / 3.4); const p = s0.clone().lerp(V(CHAIR.x - 0.9, 0, CHAIR.z - 0.4), eio(k));
    put(heroes.theo, p.x, p.z, yawTo(p, CHAIR.x, CHAIR.z)); walk(heroes.theo, t * 13, 1.0, 0.25); expr(heroes.theo, 'surprised', t);
    const c = thingAt(2.3); c.torso.rotation.x = 0.4; c.shR.rotation.x = -0.4;
    cam(S, V(p.x + 3.5, 1.4, p.z + 3.5), V(p.x + 3.5, 1.4, p.z + 3.5), p.clone().add(V(0, 1.1, 0)), p.clone().add(V(0, 1.1, 0)), 1, 60); focusOn(S, p.clone().add(V(0, 1, 0)), 0.8); S.shadowC.copy(p); S.shadowS = 14;
  });
  // #52 his shadow slammed into mine
  ref(52, (lt, u, t, S) => {
    nightPlaza(S, t, { crowd: false }); const k = eio(seg(lt, 0, 0.8)); put(heroes.theo, CHAIR.x - lerp(2.5, 0.9, k), CHAIR.z - 0.3, Math.PI / 2); walk(heroes.theo, t * 12, 0.9 * (1 - k)); expr(heroes.theo, 'scared', t);
    const pool = eout(seg(lt, 0.6, 2.4)); decals[0].set(CHAIR.x - 0.4, 0.04, CHAIR.z - 0.8, 1.6 + pool * 1.6, 2.4 + pool * 1.2, 0.95); decals[1].set(CHAIR.x - 1.4, 0.041, CHAIR.z - 1.2, 1.2 * (1 - pool) + 0.01, 1.6, 0.9);
    const c = thingAt(2.3); c.torso.rotation.x = 0.6; c.shR.rotation.x = -0.4;
    cam(S, V(CHAIR.x + 2.5, 2.4, CHAIR.z + 3), V(CHAIR.x + 2.3, 2.6, CHAIR.z + 3.2), V(CHAIR.x - 0.6, 0.6, CHAIR.z - 0.6), V(CHAIR.x - 0.6, 0.6, CHAIR.z - 0.6), u, 60); focusOn(S, V(CHAIR.x - 0.5, 0.8, CHAIR.z), 0.6); S.shadowC.set(0, 0, CHAIR.z); S.shadowS = 12;
  });
  const kidsInPool = (S, t, poolR = 3.2) => { put(heroes.theo, CHAIR.x - 0.9, CHAIR.z - 0.3, Math.PI / 2 + 0.3); expr(heroes.theo, 'scared', t); idle(heroes.theo, t); decals[0].set(CHAIR.x - 0.4, 0.04, CHAIR.z - 0.6, poolR, poolR * 0.95, 0.96); };
  // #53 one thick black pool; the thing flinches
  split(53, 126.5, (lt, u, t, S) => {
    nightPlaza(S, t); kidsInPool(S, t); const c = thingAt(2.3); c.torso.rotation.x = 0.5; c.shR.rotation.x = -0.5;
    cam(S, V(6, 7, CHAIR.z + 5), V(5.5, 7.5, CHAIR.z + 5.5), V(CHAIR.x, 0, CHAIR.z - 1), V(CHAIR.x, 0, CHAIR.z - 1), u, 58); S.focus = 10; S.dofScale = 0.4; S.shadowC.set(0, 0, CHAIR.z - 2); S.shadowS = 16;
  }, (lt, u, t, S) => {
    nightPlaza(S, t); kidsInPool(S, t); const fl = eout(seg(lt, 0.6, 1.1)); const c = thingAt(2.3); c.torso.rotation.x = 0.6 - 0.5 * fl; c.shR.rotation.x = lerp(-0.6, 0.9, fl); c.shR.rotation.z = lerp(0.1, -0.8, fl); c.root.position.z -= fl * 0.8;
    cam(S, V(F0.x + 7, 1.0, F0.z + 7.5), V(F0.x + 6.6, 1.0, F0.z + 7.8), V(CHAIR.x, 6, CHAIR.z - 2), V(CHAIR.x, 6, CHAIR.z - 2), u, 66); S.distort = 0.15; S.focus = 14; S.dofScale = 0.4; S.shadowC.set(0, 0, CHAIR.z - 4); S.shadowS = 20;
  });
  // #54 it couldn't step on a shadow that thick
  ref(54, (lt, u, t, S) => {
    nightPlaza(S, t); kidsInPool(S, t, 3.4); const c = thingAt(2.3, CHAIR.x, CHAIR.z - 4.5); c.torso.rotation.x = 0.2; c.lgL.rotation.x = 0.2 * Math.sin(lt * 2); c.lgR.rotation.x = -0.2 * Math.sin(lt * 2);
    cam(S, V(CHAIR.x - 4, 0.8, CHAIR.z - 9), V(CHAIR.x - 3.6, 0.8, CHAIR.z - 9.6), V(CHAIR.x, 1.2, CHAIR.z), V(CHAIR.x, 1.4, CHAIR.z), u, 66); S.distort = 0.15; focusOn(S, V(CHAIR.x, 1, CHAIR.z), 0.5); S.shadowC.set(0, 0, CHAIR.z - 4); S.shadowS = 16;
  });
  // #55 it wasn't the touching (high angle, legs foreground)
  ref(55, (lt, u, t, S) => { nightPlaza(S, t); kidsInPool(S, t, 3.4); const c = thingAt(2.3, CHAIR.x + 1, CHAIR.z - 3.5, 0.4);
    cam(S, V(CHAIR.x + 4, 9, CHAIR.z - 8), V(CHAIR.x + 4, 9.2, CHAIR.z - 8.2), V(CHAIR.x, 0, CHAIR.z), V(CHAIR.x, 0, CHAIR.z), u, 62); S.focus = 12; S.dofScale = 0.3; S.shadowC.set(0, 0, CHAIR.z - 3); S.shadowS = 16; });
  // #56 flashback: it was never the touching (sunset lawn + lamp shadows)
  ref(56, (lt, u, t, S) => { S.tod = 'sunset'; S.sunDir = [0.32, 0.1, 0.94]; show('fence', 8.8, 0, FZ, 0); put(heroes.neighbor, 11.5, FZ + 1.2, Math.PI - 0.3);
    cam(S, V(4, 9, FZ + 8), V(4.2, 9, FZ + 7.5), V(11, 0, FZ - 3), V(11, 0, FZ - 3.5), u, 60); S.focus = 12; S.dofScale = 0.3; S.shadowC.set(10, 0, FZ - 3); S.shadowS = 16; S.tint = [1.05, 0.95, 0.85]; });
  // #57 it only ever came for the people standing alone
  ref(57, (lt, u, t, S) => { nightPlaza(S, t); kidsInPool(S, t, 3.4); const c = thingAt(2.3, CHAIR.x - 1, CHAIR.z - 2.5, -0.3); c.torso.rotation.x = 0.3; c.shL.rotation.x = -0.6;
    cam(S, V(9, 1.4, CHAIR.z + 8), V(8.6, 1.4, CHAIR.z + 8.6), V(CHAIR.x, 5, CHAIR.z - 2), V(CHAIR.x, 5.2, CHAIR.z - 2), u, 62); S.focus = 12; S.dofScale = 0.4; S.shadowC.set(0, 0, CHAIR.z - 2); S.shadowS = 16; });
  // #58 for fifty years this town (day flashback, people spaced)
  ref(58, (lt, u, t, S) => { S.tod = 'morning'; S.tint = [1.04, 1.0, 0.92]; cam(S, V(3.2, 1.2, 60), V(3.2, 1.2, 61), V(6.4, 1.5, 80), V(6.4, 1.5, 81), u, 60); focusOn(S, V(6.4, 1.2, 66), 0.6); S.shadowC.set(5, 0, 70); S.shadowS = 20;
    line(6.4, 66, 10, 2.8, -1, lt, 1.2); line(5.8, 70, 6, 2.8, 1, lt, 1.2, { skin: 5 }); });
  // #59 spacing itself out like a buffet (high angle, lanes)
  ref(59, (lt, u, t, S) => { S.tod = 'morning'; S.tint = [1.04, 1.0, 0.92]; cam(S, V(2, 8, 70), V(2.2, 8, 71.5), V(6.5, 0, 76), V(6.5, 0, 77.5), u, 58); S.focus = 9; S.dofScale = 0.3; S.shadowC.set(6, 0, 76); S.shadowS = 12;
    for (let k = 0; k < 8; k++) person({ x: k % 2 ? 7.1 : 5.9, z: 70 + k * 1.5 + lt * 1.1, yaw: 0, amp: 0.6, phase: t * 5 + k, skin: (k * 11) % 32 }); });
  // #60 handing it one lonely person at a time (sunset porch, arm folding)
  ref(60, (lt, u, t, S) => { S.tod = 'sunset'; const [px, pz] = PH.porch; S.tint = [1.05, 0.95, 0.85];
    creature.root.visible = true; creature.root.position.set(px - 1.0, 0, pz); creature.root.scale.setScalar(0.55); creature.root.rotation.y = Math.PI / 2; creature.torso.rotation.x = 0.8; creature.shR.rotation.x = -1.8 * eio(u);
    put(heroes.porchman, px + 0.6, pz, -Math.PI / 2); heroes.porchman.root.position.y = 1; expr(heroes.porchman, 'scared', t);
    cam(S, V(px - 8, 2.5, pz - 2), V(px - 7.6, 2.5, pz - 1.6), V(px, 2, pz), V(px, 2, pz), u, 58); focusOn(S, V(px, 1.5, pz), 0.5); S.shadowC.set(px, 0, pz); S.shadowS = 12; });
  // #61 I grabbed Theo's hand and yelled at the doorways
  split(61, 145.0, (lt, u, t, S) => {
    nightPlaza(S, t); kidsInPool(S, t, 3.2); heroes.me.root.position.y = gy(CHAIR.x, CHAIR.z); heroes.me.lgL.rotation.x = heroes.me.lgR.rotation.x = 0; heroes.me.shR.rotation.x = -0.8; heroes.theo.shL.rotation.x = -0.8; props.chair.position.x += 1.2;
    const c = thingAt(2.3, CHAIR.x, CHAIR.z - 5); c.torso.rotation.x = 0.3;
    cam(S, V(CHAIR.x + 3, 3.5, CHAIR.z + 3.5), V(CHAIR.x + 3, 3.6, CHAIR.z + 3.3), V(CHAIR.x - 0.4, 0.8, CHAIR.z - 0.4), V(CHAIR.x - 0.4, 0.8, CHAIR.z - 0.4), u, 58); focusOn(S, V(CHAIR.x - 0.4, 1, CHAIR.z), 0.6); S.shadowC.set(0, 0, CHAIR.z); S.shadowS = 12;
  }, (lt, u, t, S) => {
    nightPlaza(S, t); kidsInPool(S, t, 3.2); heroes.me.root.position.y = gy(CHAIR.x, CHAIR.z); heroes.me.lgL.rotation.x = heroes.me.lgR.rotation.x = 0; heroes.me.root.rotation.y = -Math.PI / 2; heroes.me.shL.rotation.x = -1.6 * ease(seg(lt, 0.1, 0.4)); props.chair.visible = false;
    cam(S, V(CHAIR.x + 3.4, 1.7, CHAIR.z + 1.6), V(CHAIR.x + 3.5, 1.7, CHAIR.z + 1.7), V(-30, 1.8, CHAIR.z - 18), V(-30, 1.8, CHAIR.z - 20), u, 58); focusOn(S, V(CHAIR.x, 1.2, CHAIR.z), 0.5); S.shadowC.set(-10, 0, CHAIR.z - 10); S.shadowS = 25;
  });
  // #62 an old woman stepped out of the bakery
  ref(62, (lt, u, t, S) => {
    S.tod = 'night'; S.lamps = 'off'; const s = plazaBakery || plazaShops[0]; const [mx, mz] = s.mid; const k = eio(seg(lt, 0.3, 2.3));
    put(heroes.granny, mx + s.normal[0] * lerp(0.6, 4, k), mz + s.normal[1] * lerp(0.6, 4, k), Math.atan2(s.normal[0], s.normal[1])); walk(heroes.granny, t * 4, 0.45 * (k > 0 && k < 1 ? 1 : 0)); expr(heroes.granny, 'neutral', t);
    cam(S, V(mx + s.normal[0] * 10 + 3, 2.0, mz + s.normal[1] * 10 + 4), V(mx + s.normal[0] * 9.5 + 3, 2.0, mz + s.normal[1] * 9.5 + 3.6), V(mx, 2.2, mz), V(mx, 2.0, mz), u, 56); focusOn(S, V(mx + s.normal[0] * 2, 1.2, mz), 0.5); S.shadowC.set(mx + s.normal[0] * 4, 0, mz); S.shadowS = 12;
    shadeCrowd(t, 1, 140);
  });
  // #63 her shadow on ours... then all of them, hundreds
  const joiners = (t, k, n) => { const r = mulberry(63); for (let i = 0; i < n; i++) { const a = r() * 6.28; const d0 = 18 + r() * 12; const d = lerp(d0, 3.4 + Math.sqrt(i) * 0.55, clamp01(k * 1.15 - i / n * 0.6)); const x = CHAIR.x + Math.cos(a) * d, z = CHAIR.z - 3 + Math.sin(a) * d * 1.2; if (inFountain(x, z)) continue; person({ x, z, yaw: Math.atan2(CHAIR.x - x, CHAIR.z - z), amp: 0.6, phase: t * 7 + i, skin: i & 31, lean: 0.12 }); } };
  ref(63, (lt, u, t, S) => {
    nightPlaza(S, t, { crowd: false }); kidsInPool(S, t, lerp(3.2, 6, eio(u))); heroes.me.root.position.y = gy(CHAIR.x, CHAIR.z); heroes.me.lgL.rotation.x = heroes.me.lgR.rotation.x = 0; props.chair.visible = false;
    put(heroes.granny, CHAIR.x + 1.4, CHAIR.z - 1.6, -Math.PI / 2); put(heroes.guard, CHAIR.x - 2.0, CHAIR.z - 2.4, Math.PI / 2 * eio(seg(lt, 0.6, 1.2)) + 0.3); put(heroes.mom, CHAIR.x + 0.4, CHAIR.z - 3.0, Math.PI);
    joiners(t, eio(seg(lt, 1.2, 3.7)), 90); const c = thingAt(2.3, CHAIR.x, CHAIR.z - 9); c.torso.rotation.x = 0.2;
    cam(S, V(CHAIR.x + 5, 8, CHAIR.z + 6), V(CHAIR.x + 6, 10, CHAIR.z + 8), V(CHAIR.x, 0, CHAIR.z - 2), V(CHAIR.x, 0, CHAIR.z - 3), u, 60); S.focus = 12; S.dofScale = 0.3; S.shadowC.set(0, 0, CHAIR.z - 4); S.shadowS = 20;
  });
  // #64 pouring out of the shade into one giant black puddle
  ref(64, (lt, u, t, S) => {
    nightPlaza(S, t, { crowd: false }); kidsInPool(S, t, lerp(6, 22, eio(u))); heroes.me.root.position.y = gy(CHAIR.x, CHAIR.z); heroes.me.lgL.rotation.x = heroes.me.lgR.rotation.x = 0; props.chair.visible = false;
    joiners(t, 0.7 + 0.3 * u, 260); const c = thingAt(2.3 - u * 0.4, CHAIR.x, CHAIR.z - 12); c.torso.rotation.x = 0.1; c.shL.rotation.z = 0.4; c.shR.rotation.z = -0.4;
    cam(S, V(-14, 18, -50), V(-12, 22, -46), V(0, 0, -74), V(0, 0, -74), u, 58); S.focus = 32; S.dofScale = 0.2; S.shadowC.set(0, 0, -72); S.shadowS = 34;
  });
  // #65 thinner and thinner, smaller and smaller
  ref(65, (lt, u, t, S) => {
    nightPlaza(S, t, { crowd: false }); kidsInPool(S, t, 22); props.chair.visible = false; heroes.me.root.position.y = 0; heroes.me.lgL.rotation.x = heroes.me.lgR.rotation.x = 0;
    joiners(t, 1, 200); const k = eio(u); const c = thingAt(lerp(1.9, 0.6, k), CHAIR.x, CHAIR.z - 12); c.root.scale.x = lerp(1.9, 0.12, k); c.root.scale.z = lerp(1.9, 0.2, k);
    cam(S, V(CHAIR.x + 2, 0.7, CHAIR.z - 3), V(CHAIR.x + 2, 0.7, CHAIR.z - 3.4), V(CHAIR.x, 8, CHAIR.z - 12), V(CHAIR.x, 3, CHAIR.z - 12), u, 70); S.distort = 0.18; S.focus = 9; S.dofScale = 0.4; S.shadowC.set(0, 0, CHAIR.z - 8); S.shadowS = 16;
  });
  // #66-67 a single black thread whipping on the cobblestones, looking for a crack
  const threadPath = (t, cx, cz, len, dir) => (f) => [cx + Math.sin(t * 6 + f * 9) * 0.6 * f + dir[0] * f * len, 0.04, cz + dir[1] * f * len + Math.cos(t * 5 + f * 7) * 0.4 * f, 1.2 - f * 0.8];
  ref(66, (lt, u, t, S) => {
    S.tod = 'night'; S.lamps = 'off'; const cx = CHAIR.x + 4 - lt * 1.2, cz = CHAIR.z - 6; thread.set(threadPath(t, cx, cz, 5, [-0.6, -0.8]));
    cam(S, V(cx + 3, 1.6, cz + 3), V(cx + 2.6, 1.4, cz + 2.8), V(cx - 1, 0, cz - 1.5), V(cx - 1.4, 0, cz - 2), u, 60); S.focus = 4; S.dofScale = 0.6; S.shadowC.set(cx, 0, cz); S.shadowS = 10; joiners(t, 1, 120);
  });
  ref(67, (lt, u, t, S) => {
    S.tod = 'night'; S.lamps = 'off'; const cx = 10 - lt * 0.3, cz = CHAIR.z - 14 - lt * 6; thread.set(threadPath(t, cx, cz, 4, [0.1, -1]));
    cam(S, V(cx + 0.5, 0.9, cz + 6), V(cx + 0.3, 0.9, cz + 5), V(cx, 0.1, cz - 4), V(cx, 0.1, cz - 4), u, 64); S.focus = 5; S.dofScale = 0.6; S.shadowC.set(cx, 0, cz); S.shadowS = 12;
  });
  // #68 found one: the mayor at the very back of the square
  ref(68, (lt, u, t, S) => {
    S.tod = 'night'; S.lamps = 'one'; S.lampOne = lampNearMayor; put(heroes.mayor, lampNearMayor.x + 0.7, lampNearMayor.z + 0.6, 0); idle(heroes.mayor, t);
    joiners(t, 1, 200); kidsInPool(S, t, 20); heroes.theo.root.visible = false;
    cam(S, V(-9, 2.4, -70), V(-9, 2.6, -72), V(6, 2.5, -110), V(7, 2.5, -110), u, 50); S.focus = 30; S.dofScale = 0.35; S.shadowC.set(4, 0, -100); S.shadowS = 25;
  });
  // #69 alone under the one street light that still worked
  ref(69, (lt, u, t, S) => {
    S.tod = 'night'; S.lamps = 'one'; S.lampOne = lampNearMayor; put(heroes.mayor, lampNearMayor.x + 0.7, lampNearMayor.z + 0.6, 0); idle(heroes.mayor, t); expr(heroes.mayor, 'neutral', t);
    cam(S, V(lampNearMayor.x - 5, 1.2, lampNearMayor.z + 7), V(lampNearMayor.x - 4.6, 1.2, lampNearMayor.z + 6.4), V(lampNearMayor.x + 0.7, 1.8, lampNearMayor.z), V(lampNearMayor.x + 0.7, 1.8, lampNearMayor.z), u, 56); focusOn(S, V(lampNearMayor.x + 0.7, 1.4, lampNearMayor.z + 0.6), 0.5); S.shadowC.set(lampNearMayor.x, 0, lampNearMayor.z); S.shadowS = 10;
  });
  // #70 with his own little shadow (high angle)
  ref(70, (lt, u, t, S) => {
    S.tod = 'night'; S.lamps = 'one'; S.lampOne = lampNearMayor; put(heroes.mayor, lampNearMayor.x + 0.7, lampNearMayor.z + 0.6, 0.3); idle(heroes.mayor, t);
    cam(S, V(lampNearMayor.x + 2.4, 4.5, lampNearMayor.z + 3.6), V(lampNearMayor.x + 2.3, 4.4, lampNearMayor.z + 3.4), V(lampNearMayor.x + 0.7, 0.5, lampNearMayor.z + 0.6), V(lampNearMayor.x + 0.7, 0.6, lampNearMayor.z + 0.6), u, 56); focusOn(S, V(lampNearMayor.x + 0.7, 1, lampNearMayor.z + 0.6), 0.6); S.shadowC.set(lampNearMayor.x, 0, lampNearMayor.z); S.shadowS = 8;
  });
  // #71 and his own little hat (close top-down)
  ref(71, (lt, u, t, S) => {
    S.tod = 'night'; S.lamps = 'one'; S.lampOne = lampNearMayor; put(heroes.mayor, lampNearMayor.x + 0.7, lampNearMayor.z + 0.6, 0.3); expr(heroes.mayor, 'neutral', t); heroes.mayor.neck.rotation.x = -0.4;
    const m = heroes.mayor.root.position; cam(S, V(m.x + 0.6, 3.4, m.z + 1.4), V(m.x + 0.55, 3.3, m.z + 1.3), V(m.x, 2.0, m.z), V(m.x, 2.0, m.z), u, 52); focusOn(S, V(m.x, 2.2, m.z), 0.8); S.shadowC.copy(m); S.shadowS = 6;
  });
  // #72 the thread slid under his shoe; the street light died
  ref(72, (lt, u, t, S) => {
    S.tod = 'night'; const dead = lt > 3.6; S.lamps = dead ? 'off' : 'one'; S.lampOne = lampNearMayor; put(heroes.mayor, lampNearMayor.x + 0.7, lampNearMayor.z + 0.6, 0); idle(heroes.mayor, t);
    const k = clamp01(lt / 3.3); const cx = lerp(0, lampNearMayor.x + 0.7, k), cz = lerp(-96, lampNearMayor.z + 1.2, k); if (k < 1) thread.set(threadPath(t, cx, cz, 2.5 * (1 - k * 0.7), [0, 1]));
    cam(S, V(lampNearMayor.x - 3, 3, -92), V(lampNearMayor.x - 3, 3.1, -94), V(lampNearMayor.x, 2, -110), V(lampNearMayor.x, 2, -110), u, 50); S.focus = 15; S.dofScale = 0.4; S.shadowC.set(lampNearMayor.x, 0, -104); S.shadowS = 16;
    if (dead) S.exposure = 0.75;
  });
  // #73 now the mayor's shadow waves at me (day, top-down)
  ref(73, (lt, u, t, S) => {
    S.tod = 'morning'; S.sunDir = [0.5, 0.5, 0.7]; const z = -80 + lt * 1.2, x = -8;
    put(heroes.mayor, x, z, 0); walk(heroes.mayor, t * 4.5, 0.5); heroes.mayor.root.traverse(o => { if (o.isMesh) o.castShadow = false; });
    put(mayorShadow, x, z, 0); walk(mayorShadow, t * 4.5, 0.5); mayorShadow.shR.rotation.x = -2.6; mayorShadow.shR.rotation.z = -0.4 * Math.sin(t * 7) - 0.2;
    scatter(-28, 28, -108, -56, 60, 73, t, { avoid: (px, pz) => inFountain(px, pz) || Math.hypot(px - x, pz - z) < 3, move: 0.6 });
    cam(S, V(x + 1.5, 8.5, z + 2.5), V(x + 1.5, 8.5, z + 3.5), V(x - 1.2, 0, z - 1.0), V(x - 1.2, 0, z), u, 60); S.focus = 9; S.dofScale = 0.2; S.shadowC.set(x, 0, z); S.shadowS = 14;
  });
  // #74 like and subscribe — then shadow hands rise into the sky
  split(74, 179.25, (lt, u, t, S) => {
    S.tod = 'noon'; put(heroes.me, F0.x, F0.z + 7.4, 0); expr(heroes.me, 'smile', t); heroes.me.shL.rotation.x = heroes.me.shR.rotation.x = -1.2;
    show('sub', F0.x, 1.05, F0.z + 7.4 + 0.42, 0); props.sub.scale.setScalar(1.15);
    cam(S, V(F0.x, 1.5, F0.z + 11), V(F0.x, 1.5, F0.z + 10.6), V(F0.x, 1.3, F0.z + 7.4), V(F0.x, 1.3, F0.z + 7.4), u, 56); focusOn(S, V(F0.x, 1.2, F0.z + 7.4), 0.8); S.shadowC.copy(F0); S.shadowS = 14;
  }, (lt, u, t, S) => {
    S.tod = 'noon'; const k = eout(u * 1.6); show('hands', F0.x, lerp(-24, 4, k), F0.z - 30, 0);
    cam(S, V(F0.x, 2, F0.z + 10), V(F0.x, 2, F0.z + 10), V(F0.x, 25, F0.z - 30), V(F0.x, 25, F0.z - 30), 1, 60); S.focus = 50; S.dofScale = 0.1; S.shadowC.copy(F0); S.shadowS = 20;
  });

  // keep crowd index fresh per frame
  for (const s of shots) { const fn = s.fn; s.fn = (lt, u, t, S, sh) => { crowdReset(); heroes.mayor.root.traverse(o => { if (o.isMesh) o.castShadow = true; }); fn(lt, u, t, S, sh); }; }
  shots.sort((a, b) => a.t0 - b.t0);
  return { shots, heroes, props, duration: 179.9 };
}
