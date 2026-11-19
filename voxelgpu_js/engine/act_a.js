// Acte A — le dernier bus (0 → ~103 s).
export function actA(E) {
  const { V, THREE, anim, bus, road, st, noe, phone, at, clamp, lerp, ease, easeOut, easeIn, lerpV } = E;
  const shots = []; const add = (name, t0, cam, fn) => shots.push({ name, t0, cam, fn });
  const T = (id, d = -0.3) => at(id) + d;
  const B = (x, y, z) => bus.w(x, y, z);
  const SZ = -6.92, SX = -0.98;                       // siège de Noé (côté fenêtre gauche, entre deux montants)
  const sitNoe = (t, expr = 'neutral', k = 1) => { anim.put(noe, SX, SZ + 0.04, Math.PI, () => bus.group.position.y); anim.sit(noe, k, 0.44); noe.lgL.rotation.x += 0.08 * k; noe.knL.rotation.x -= 0.06 * k; noe.lgR.rotation.x += 0.04 * k; anim.breathe(noe, t, 0.6); if (expr) anim.expr(noe, expr, t, 0.3); noe.root.visible = true; };
  const holdPhone = (t, vib = 0) => { E.holdPhone(noe, t, vib, { neck: 0.32 }); };
  const upd = () => noe.root.updateMatrixWorld(true);
  const HEAD = () => noe.head.getWorldPosition(V()), FACE = () => noe.head.getWorldDirection(V());
  const lift = () => { noe.handR.children.forEach(c => { if (c !== phone.g) c.visible = false; }); noe.handL.visible = false; noe.neck.visible = false; };  // gros plans écran : on masque les mains pour que les doigts ne cachent pas le message
  const SCR = () => phone.screen.getWorldPosition(V()), SCRN = () => V(0, 0, 1).applyQuaternion(phone.screen.getWorldQuaternion(new THREE.Quaternion()));
  // gros plan visage (d = distance) ; side = décalage latéral (repère monde x)
  const faceCam = (d, dx = 0, dy = 0, fov = 46, roll = 0) => { const h = HEAD(), f = FACE(); return { pos: h.clone().addScaledVector(f, d).add(V(dx, dy, 0)), look: h.clone().add(V(0, -0.02, 0)), fov, roll }; };
  // niveau du liquide noir (local) au temps global t
  const LQ = (t) => 0.02 + 0.03 * ease((t - T('A10')) / 4) + 0.2 * ease((t - T('A11')) / 8);
  const liquid = (S, t) => { const lq = LQ(t); bus.liquid.position.y = lq; S.reflect.y = lq + bus.group.position.y; return lq; };
  // mains qui sortent du liquide et avancent dans l'allée (vers Noé, assis en SZ)
  const handsRise = (t, n, from, spread = 1, advance = 0) => {
    bus.hands.forEach((h, i) => {
      if (i >= n) { h.g.visible = false; return; }
      const k = clamp((t - from - h.delay * spread) / 1.1); if (k <= 0) { h.g.visible = false; return; }
      const lq = LQ(t); const z0 = -10.2 + h.delay * 3.4 + (i % 2) * 0.4; const z = Math.min(z0 + advance * (0.6 + h.delay) * clamp((t - from) / 7), SZ - 0.5 - h.delay * 0.3);
      h.g.visible = true; h.g.scale.setScalar(1.0 + (i % 3) * 0.12); h.g.position.set(((i * 0.37) % 1 - 0.5) * 1.0, lq - 0.62 + 0.6 * easeOut(k) + 0.05 * Math.sin(t * 1.7 + i), z);
      h.g.rotation.set(-0.15 + 0.2 * Math.sin(t * 1.1 + i * 2), (i % 5 - 2) * 0.25, 0.25 * Math.sin(t * 0.9 + i));
      h.set(0.12 + 0.4 * (0.5 + 0.5 * Math.sin(t * 2.2 + i * 1.7)), 0.3);
    });
  };
  const headlights = () => [{ pos: B(-1.2, 0.1, -13.3), target: B(-1.4, -0.9, -30), color: 0xfff0d8, i: 45, angle: 0.5, pen: 0.6, dist: 70 }, { pos: B(1.2, 0.1, -13.3), target: B(1.4, -0.9, -30), color: 0xfff0d8, i: 45, angle: 0.5, pen: 0.6, dist: 70 }];
  // ---------------------------------------------------------------- A01 : l'arrêt sous la pluie, le bus arrive face à nous et s'arrête ; Noé monte (titre)
  add('A01_arret', 0,
    (lt) => ({ pos: road.w(5.6, 0.5 + lt * 0.02, -10.5 + lt * 0.12), look: road.w(3.4, 1.5, 4), fov: 58, roll: 0.03 }),
    (lt, u, t, S) => {
      E.lookRoad(S, t); const stop = 4.0; const dz = Math.pow(Math.max(0, stop - lt), 2) * 3.2;
      bus.place(road.w(2.1, 0.95, 11.95 + dz), 0); bus.setTubes(0, t); bus.setWindows(0xe8f0ff, 0.35); bus.setDoor(ease((lt - 4.4) / 0.9)); bus.liquid.visible = false;
      const walk = clamp((lt - 5.4) / 2.0); anim.put(noe, road.w(4.8 - walk * 1.2, 0, 0).x, road.w(0, 0, -0.2 + walk * 0.2).z, -Math.PI / 2 - 0.35 + walk * 0.1, () => road.origin.y); noe.root.visible = true;
      if (walk > 0 && walk < 1) anim.walk(noe, lt * 7, 0.7); else anim.pose(noe, 'pockets'); if (walk <= 0) anim.lookAt(noe, B(0, 1.5, -13), 0.7); anim.expr(noe, 'neutral', t, 0.1);
      S.spots = headlights(); S.lights = [...road.lampLights(road.w(4, 0, 0), 2, 6), { pos: road.w(5.4, 2.2, 0), color: 0xe8f0ff, i: 2.5, dist: 6 }];
      S.focus = 10; S.dofScale = 0.2; S.shadowC = road.w(3, 0, 0); S.shadowS = 10; S.fade = ease(lt / 1.2);
    });
  // ---------------------------------------------------------------- A02 : son visage derrière la vitre ruisselante, puis la vitre « écran mal réglé »
  add('A02_vitre', T('A02'),
    (lt, u, t) => { sitNoe(t, 'neutral'); noe.neck.rotation.y -= 0.85; upd(); const h = HEAD(); return { pos: B(-0.3 + lt * 0.02, h.y + 0.05, SZ - 1.8 + lt * 0.06), look: h.clone().add(V(-0.12, -0.03, 0)), fov: 46, roll: 0.02 }; },
    (lt, u, t, S) => { E.lookBus(S, t, { red: 0, pass: 1.2 }); bus.setTubes(0, t); bus.showPoles([3, 4]); sitNoe(t, 'neutral'); noe.neck.rotation.y -= 0.85; noe.neck.rotation.x += 0.05; anim.pose(noe, 'pockets', 0.5);
      S.focus = 1.85; S.dofScale = 0.6; S.shake = 0.12; S.lights.push({ pos: B(-1.9, 1.7, SZ + ((t * 16) % 17) - 8.5), color: 0xffb060, i: 2.4, dist: 4 }); });
  add('A02_ecran', T('A02', 2.6),
    (lt) => ({ pos: B(-0.95, 1.52, SZ - 0.15), look: B(-1.56, 1.42, SZ - 0.95 - lt * 0.04), fov: 52, roll: -0.04 }),
    (lt, u, t, S) => { E.lookBus(S, t, { red: 0, pass: 1.3 }); bus.setTubes(0, t); bus.showPoles([3]); sitNoe(t, 'neutral'); noe.root.visible = false; S.focus = 0.95; S.dofScale = 0.5; S.shake = 0.15; });
  // ---------------------------------------------------------------- A03 : seul passager ; le chauffeur ne se retourne pas
  add('A03_seul', T('A03'),
    (lt) => ({ pos: B(0.3, 2.05, 0.25 - lt * 0.12), look: B(-0.35, 1.0, -8.5), fov: 58, roll: 0 }),
    (lt, u, t, S) => { E.lookBus(S, t, { red: 0, pass: 1 }); bus.setTubes(0, t); sitNoe(t, 'neutral'); noe.neck.rotation.y -= 0.6; S.focus = 7.0; S.dofScale = 0.25; S.shake = 0.1; });
  add('A03_chauffeur', T('A03', 2.6),
    (lt) => ({ pos: B(0.55, 1.55, -9.7 - lt * 0.08), look: B(-0.85, 1.25, -11.8), fov: 50, roll: 0.02 }),
    (lt, u, t, S) => { E.lookBus(S, t, { red: 0, pass: 1 }); bus.setTubes(0, t); S.focus = 2.6; S.dofScale = 0.45; S.shake = 0.1; S.lights.push({ pos: B(-0.7, 1.15, -12.4), color: 0x40a0ff, i: 1.6, dist: 2.5 }, { pos: B(-0.2, 2.0, -10.8), color: 0xd8e0ff, i: 1.5, dist: 3 }); });
  // ---------------------------------------------------------------- A03b : le bus roule ; la ville, puis plus rien
  add('A03b_route', T('A03b'),
    (lt) => { const bz = -300 - lt * 15; return { pos: road.w(-2.4, 1.25 + lt * 0.05, bz - 16.5 + lt * 0.35), look: road.w(1.6, 1.3, bz - 7), fov: 56, roll: 0.02 }; },
    (lt, u, t, S) => {
      E.lookRoad(S, t); const bz = -300 - lt * 15; bus.place(road.w(2.1, 0.95 + Math.sin(lt * 9) * 0.01, bz), 0); bus.setTubes(0, t); bus.setWindows(0xe8f0ff, 0.45); bus.liquid.visible = false;
      S.spots = headlights(); S.lights = road.lampLights(road.w(2, 0, bz - 6), 3, 7); S.focus = 9; S.mblur = 0.4; S.shadowC = road.w(2, 0, bz - 6); S.shadowS = 12;
      sitNoe(t, 'neutral'); noe.neck.rotation.y -= 0.85;
    });
  // ---------------------------------------------------------------- A04 : le téléphone vibre (notification de Lina) — par-dessus l'épaule
  const otsPhone = (lt, t, expr) => { sitNoe(t, expr); holdPhone(t, 0); upd(); const h = HEAD(), s = SCR(); return { pos: h.clone().add(V(0.85, 0.5, 0.3)), look: s.clone().add(V(0, 0.04, 0)), fov: 46, roll: 0.06 }; };
  add('A04_vibre', T('A04'),
    (lt) => ({ pos: B(-0.45, 1.42, SZ - 1.65), look: B(-0.95, 1.12, SZ - 0.35), fov: 48, roll: 0.04 }),
    (lt, u, t, S) => { E.lookBus(S, t, { red: 0, pass: 0 }); bus.setTubes(0, t); bus.showPoles([3, 4]); sitNoe(t, 'surprised'); holdPhone(t, lt < 1.6 && lt > 0.5 ? 1 : 0); phone.show(lt < 0.5 ? 'off' : 'notif'); S.focus = 1.5; S.dofScale = 0.6; S.shake = 0.08;
      S.lights.push({ pos: SCR().add(V(0, 0.2, 0)), color: 0x9ab4ff, i: lt < 0.5 ? 0 : 0.5, dist: 1.2, decay: 2 }); });
  // ---------------------------------------------------------------- A05 : le message (écran plein cadre)
  add('A05_message', T('A05'),
    (lt, u, t) => { sitNoe(t, 'worried'); holdPhone(t, 0); lift(); upd(); const p = SCR(), n = SCRN(); return { pos: p.clone().addScaledVector(n, 0.36 - lt * 0.008), look: p.clone(), fov: 46, roll: 0 }; },
    (lt, u, t, S) => { E.lookBus(S, t, { red: 0, pass: 0 }); bus.setTubes(0, t); sitNoe(t, 'worried'); holdPhone(t, 0); lift(); phone.show('chat'); S.focus = 0.36; S.dofScale = 0.5; S.shake = 0.05; });
  // ---------------------------------------------------------------- A06 : son visage, inquiet, éclairé par l'écran
  add('A06_visage', T('A06'),
    (lt, u, t) => { sitNoe(t, 'worried'); holdPhone(t, 0); upd(); return faceCam(1.75 - lt * 0.04, 0.1, -0.12, 46, -0.02); },
    (lt, u, t, S) => { E.lookBus(S, t, { red: 0, pass: 0 }); bus.setTubes(0, t); sitNoe(t, 'worried'); holdPhone(t, 0); phone.show('chat'); S.focus = 1.7; S.dofScale = 0.7; S.shake = 0.06;
      S.lights.push({ pos: SCR().add(V(0, 0.15, -0.05)), color: 0x9ab4ff, i: 0.55, dist: 1.4, decay: 2 }); });
  // ---------------------------------------------------------------- A07 : pas de réseau
  add('A07_reseau', T('A07'),
    (lt, u, t) => { sitNoe(t, 'grit'); holdPhone(t, 0); lift(); upd(); const p = SCR(), n = SCRN(); return { pos: p.clone().addScaledVector(n, 0.37), look: p.clone(), fov: 46, roll: 0.02 }; },
    (lt, u, t, S) => { E.lookBus(S, t, { red: 0, pass: 0 }); bus.setTubes(0, t); sitNoe(t, 'grit'); holdPhone(t, 0); lift(); phone.show('call'); S.focus = 0.37; S.dofScale = 0.5; S.shake = 0.06; });
  // ---------------------------------------------------------------- A08-A09 : les néons deviennent rouges, un par un, du fond jusqu'à lui
  const wave = (t) => { const t0 = T('A08', 1.0); return bus.tubes.map((tb, i) => ease((t - t0 - i * 1.3) / 0.35)); };
  add('A08_neons', T('A08'),
    (lt) => ({ pos: B(-0.2, 1.05, SZ - 0.9), look: B(0.05, 2.0 - lt * 0.02, 0.5), fov: 58, roll: 0.03 }),
    (lt, u, t, S) => { const w = wave(t); const red = w.reduce((a, b) => a + b, 0) / 6; E.lookBus(S, t, { red: 0.1 + red * 0.9, tubes: w }); bus.setTubes(w, t);
      sitNoe(t, 'scared'); noe.neck.rotation.y += 2.4; S.focus = 4.5; S.dofScale = 0.35; S.shake = 0.08; });
  add('A09_visage', T('A10', -2.4),
    (lt, u, t) => { sitNoe(t, 'scared'); noe.neck.rotation.y -= 0.35; upd(); return faceCam(1.8, 0.25, 0.0, 46, -0.03); },
    (lt, u, t, S) => { const w = wave(t); E.lookBus(S, t, { red: 1, tubes: w }); bus.setTubes(w, t); sitNoe(t, 'scared'); noe.neck.rotation.y -= 0.35; S.focus = 1.8; S.dofScale = 0.7; S.shake = 0.1; });
  // ---------------------------------------------------------------- A10 : le sol est mouillé (ses baskets dans une pellicule noire)
  add('A10_sol', T('A10'),
    (lt) => ({ pos: B(0.05, 0.1, SZ + 0.9 - lt * 0.05), look: B(-0.1, 0.02, SZ - 4.5), fov: 54, roll: 0.04 }),
    (lt, u, t, S) => { E.lookBus(S, t, { red: 1 }); bus.setTubes(1, t); sitNoe(t, 'worried'); liquid(S, t); S.focus = 1.0; S.dofScale = 0.7; S.shake = 0.05; });
  // ---------------------------------------------------------------- A11 : l'eau monte, noire, épaisse ; il remonte les jambes
  add('A11_monte', T('A11'),
    (lt) => ({ pos: B(0.25, 0.32, SZ + 2.4), look: B(-0.3, 0.28, SZ - 5), fov: 58, roll: -0.02 }),
    (lt, u, t, S) => { E.lookBus(S, t, { red: 1 }); bus.setTubes(1, t); sitNoe(t, 'scared'); noe.lgL.rotation.x -= 0.45 * ease(lt / 3); noe.lgR.rotation.x -= 0.4 * ease(lt / 3); noe.knL.rotation.x += 0.75 * ease(lt / 3); noe.knR.rotation.x += 0.7 * ease(lt / 3); liquid(S, t); S.focus = 3.0; S.dofScale = 0.4; S.shake = 0.06; });
  // ---------------------------------------------------------------- A12 : ça sort d'entre les sièges
  add('A12_sieges', T('A12'),
    (lt) => ({ pos: B(-0.25, 0.55, SZ - 0.75), look: B(0.5, 0.32, SZ - 2.8), fov: 50, roll: 0.06 }),
    (lt, u, t, S) => { E.lookBus(S, t, { red: 1 }); bus.setTubes(1, t); const lq = liquid(S, t); sitNoe(t, 'scared');
      for (let i = 0; i < 3; i++) { const h = bus.hands[i]; h.g.visible = true; h.g.scale.setScalar(1); h.g.position.set(0.42 - i * 0.05, lq - 0.62 + 0.5 * ease((lt - i * 0.6) / 2.5), SZ - 1.8 - i * 0.4); h.g.rotation.set(-0.35, -0.9 + i * 0.3, 0.3); h.set(0.7, 0.2); }
      S.focus = 1.5; S.dofScale = 0.6; });
  // ---------------------------------------------------------------- A13 : quelque chose a bougé, dessous
  add('A13_dessous', T('A13'),
    (lt) => ({ pos: B(-0.1, 0.62, SZ - 0.75), look: B(0.1, 0.24, SZ - 2.6), fov: 50, roll: 0.03 }),
    (lt, u, t, S) => { E.lookBus(S, t, { red: 1 }); bus.setTubes(1, t); const lq = liquid(S, t); sitNoe(t, 'scared');
      const h = bus.hands[3]; h.g.visible = true; h.g.scale.setScalar(1.1); h.g.position.set(0.3 - lt * 0.1, lq - 0.36 + 0.05 * Math.sin(lt * 4), SZ - 3.4 + lt * 0.3); h.g.rotation.set(-1.25, 0.2, 0); h.set(0.25, 0.3);
      S.focus = 1.9; S.dofScale = 0.6; });
  // ---------------------------------------------------------------- A14 : une main, puis dix, puis toute l'allée
  add('A14_une', T('A14'),
    (lt) => ({ pos: B(0.0, 0.55, SZ - 0.6), look: B(0.05, 0.5, SZ - 2.0), fov: 46, roll: 0.02 }),
    (lt, u, t, S) => { E.lookBus(S, t, { red: 1 }); bus.setTubes(1, t); const lq = liquid(S, t);
      const h = bus.hands[4]; h.g.visible = true; h.g.scale.setScalar(1.15); h.g.position.set(0.05, lq - 0.6 + 0.62 * easeOut(lt / 0.9), SZ - 2.0); h.g.rotation.set(-0.12, 0.05, 0.05); h.set(0.05 + 0.3 * ease(lt / 1.5), 0.3); S.focus = 1.4; S.dofScale = 0.7; });
  add('A14_dix', T('A14', 1.0),
    (lt) => ({ pos: B(-0.15, 1.0, SZ - 0.2), look: B(0.1, 0.3, SZ - 3.5), fov: 56, roll: -0.02 }),
    (lt, u, t, S) => { E.lookBus(S, t, { red: 1 }); bus.setTubes(1, t); liquid(S, t); handsRise(t, 10, T('A14', 0.9), 0.6); S.focus = 2.6; S.dofScale = 0.45; });
  add('A14_allee', T('A14', 2.0),
    (lt) => ({ pos: B(0.1, 1.95 - lt * 0.05, SZ + 0.6), look: B(0, 0.35, SZ - 4.5), fov: 58, roll: 0 }),
    (lt, u, t, S) => { E.lookBus(S, t, { red: 1 }); bus.setTubes(1, t); liquid(S, t); handsRise(t, 26, T('A14', 1.6), 0.8); S.focus = 3.4; S.dofScale = 0.3; S.shake = 0.1; });
  // ---------------------------------------------------------------- A15 : à tâtons, elles avancent vers lui
  add('A15_avancent', T('A15'),
    (lt) => ({ pos: B(-0.65, 1.8, SZ + 0.15), look: B(0.1, 0.25, SZ - 3.0 + lt * 0.15), fov: 58, roll: 0.05 }),
    (lt, u, t, S) => { E.lookBus(S, t, { red: 1 }); bus.setTubes(1, t); liquid(S, t); handsRise(t, 26, T('A14', 1.6), 0.8, 2.2); sitNoe(t, 'scared'); noe.root.visible = false; S.focus = 2.6; S.dofScale = 0.4; S.shake = 0.15; });
  // ---------------------------------------------------------------- A16 : accroché à la barre jaune (plan des illustrations), puis la main sur la cheville
  const POLE = bus.poles.reduce((a, p) => (Math.abs(p.local.z - (SZ - 0.1)) < Math.abs(a.local.z - (SZ - 0.1)) ? p : a));
  const standPole = (t) => {
    anim.put(noe, bus.w(-0.3, 0, POLE.local.z + 0.18).x, bus.w(-0.3, 0, POLE.local.z + 0.18).z, -0.08, () => bus.group.position.y); noe.root.visible = true;
    noe.lgR.rotation.set(-0.48, 0, -0.12); noe.knR.rotation.x = 0.7; noe.ftR.rotation.x = -0.2;            // jambe droite devant (c'est elle que la main attrape)
    noe.lgL.rotation.set(0.36 + 0.08 * Math.sin(t * 7), 0, 0.2); noe.knL.rotation.x = 0.3; noe.ftL.rotation.x = -0.12; anim.ground(noe);
    noe.torso.rotation.z = 0.1 + 0.03 * Math.sin(t * 9); noe.torso.rotation.x = 0.1; noe.neck.rotation.set(0.06, -0.12, -0.08);
    anim.grip(noe, 'L', bus.w(POLE.local.x, 1.62, POLE.local.z), V(0, 1, 0), 0.034);
    noe.shR.rotation.set(-0.5 + 0.1 * Math.sin(t * 5), 0, -1.0); noe.elR.rotation.set(-0.55, 0, 0); noe.setHand('R', 'open');
  };
  const heroHands = (t, lq) => { const spots = [[-0.55, 1.7, 1.2, 0.25], [-0.35, 0.65, 1.15, 0.3], [0.05, 0.3, 1.1, 0.1], [-0.5, -0.3, 1.1, 0.35], [0.55, 0.1, 1.0, -0.3], [-0.2, -1.2, 1.05, 0.2], [0.45, -1.3, 1.0, 0], [-0.45, -2.3, 1, 0.3], [0.2, -3.1, 1, -0.2], [-0.1, -4.3, 1, 0.1], [0.45, -5.2, 1, 0], [0.6, 1.0, 1.2, -0.4]];
    bus.hands.forEach((h, i) => { const sp = spots[i]; if (!sp) { h.g.visible = false; return; } const z = POLE.local.z + sp[1]; h.g.visible = true; h.g.scale.setScalar(sp[2]); h.g.position.set(sp[0], lq - 0.05 + 0.08 * Math.sin(t * 1.3 + i), z); h.g.rotation.set(sp[3] * 0.5 - 0.1, Math.atan2(-0.4 - sp[0], POLE.local.z + 2.7 - z) * 0.6, -sp[0] * 0.3); h.set(0.12 + 0.25 * (0.5 + 0.5 * Math.sin(t * 2 + i)), 0.3); }); };
  const hideNearPoles = () => bus.showPoles(bus.poles.map((p, i) => i).filter((i) => bus.poles[i].local.z > POLE.local.z + 0.5));
  add('A16_barre', T('A16'),
    (lt) => ({ pos: B(-0.45 + lt * 0.02, 0.5, POLE.local.z + 2.75), look: B(-0.05, 1.05, POLE.local.z), fov: 60, roll: -0.05 }),
    (lt, u, t, S) => { E.lookBus(S, t, { red: 1 }); bus.setTubes(1, t); const lq = liquid(S, t); standPole(t); noe.setExpr('scream'); heroHands(t, lq); hideNearPoles(); S.focus = 2.8; S.dofScale = 0.5; S.shake = 0.22; });
  add('A16_cheville', T('A16', 3.6),
    (lt) => ({ pos: B(0.85, 0.6, POLE.local.z + 2.5), look: B(-0.25, 0.4, POLE.local.z + 0.2), fov: 40, roll: 0.08 }),
    (lt, u, t, S) => { E.lookBus(S, t, { red: 1 }); bus.setTubes(1, t); const lq = liquid(S, t); standPole(t); noe.setExpr('scream'); heroHands(t, lq); hideNearPoles(); upd();
      const g = easeOut((lt - 0.4) / 0.7); const h = bus.hands[3]; h.g.visible = true; anim.grabAnkle(h, noe, 'R', lerp(0.1, 1, ease((lt - 0.9) / 0.45)), 1.15, 0.6, -1.7, 3.6); h.g.position.y -= (1 - g) * 0.55; { const k = noe.knR.localToWorld(V(0, -1.7 / 16, 0.5)); S.lights.push({ pos: k, color: 0xff6a50, i: 1.4, dist: 1.2, decay: 2 }); }
      S.focus = 2.55; S.dofScale = 0.6; S.shake = 0.15 + 0.45 * ease((lt - 1.1) / 0.3) * (1 - ease((lt - 1.6) / 1)); S.flash = 0.2 * Math.max(0, 1 - Math.abs(lt - 1.15) * 6); });
  // ---------------------------------------------------------------- A17 : freinage brutal ; portes ouvertes sur la station-service
  add('A17_frein', T('A17'),
    (lt) => ({ pos: B(0.4, 1.3, POLE.local.z + 2.2), look: B(-0.15, 1.0, POLE.local.z - 0.4), fov: 60, roll: -0.05 - 0.12 * Math.sin(Math.min(lt, 1.2) * 4) * Math.exp(-lt * 1.5) }),
    (lt, u, t, S) => { E.lookBus(S, t, { red: 1 }); bus.setTubes(1, t); const lq = liquid(S, t); standPole(t); heroHands(t, lq); hideNearPoles(); noe.root.position.z -= 0.22 * easeOut(lt / 0.4);
      noe.torso.rotation.x = 0.35 * Math.exp(-lt * 2) * Math.sin(lt * 8) + 0.1; noe.shR.rotation.set(-1.3, 0, -0.6); noe.elR.rotation.x = -0.4; noe.setExpr('scream'); anim.grip(noe, 'L', bus.w(POLE.local.x, 1.62, POLE.local.z), V(0, 1, 0), 0.034); { const h = bus.hands[3]; h.g.visible = true; anim.grabAnkle(h, noe, 'R', 1, 1.15, 0.6, -1.7, 3.6); } S.shake = 1.2 * Math.exp(-lt * 1.8) + 0.12; S.focus = 2.2; S.dofScale = 0.5; S.mblur = 0.5; });
  const BUS_AT_STATION = () => bus.place(st.w(9.95, 0.95, 15.66), Math.PI / 2);
  add('A17_station', T('A17', 2.0),
    (lt) => ({ pos: st.w(-5.5 + lt * 0.2, 0.75, 8.6), look: st.w(-0.8, 1.5, 14.2), fov: 60, roll: 0.02 }),
    (lt, u, t, S) => { E.lookStation(S, t, { out: true, sets: ['st', 'bus'] }); BUS_AT_STATION(); bus.setTubes(1, t); bus.setWindows(0xff2a1a, 1.1); bus.setDoor(ease((lt - 0.8) / 0.8)); bus.liquid.visible = false;
      S.lights.push(...bus.tubeLights(1, t, 2.5, 6).slice(0, 2)); S.focus = 6; S.dofScale = 0.2; });
  // ---------------------------------------------------------------- A18 : il arrache son pied (la chaussure reste), et il court
  add('A18_pied', T('A18'),
    (lt) => ({ pos: B(0.85, 0.62, POLE.local.z + 2.5), look: B(-0.25, 0.42, POLE.local.z + 0.2), fov: 40, roll: -0.05 }),
    (lt, u, t, S) => { E.lookBus(S, t, { red: 1 }); bus.setTubes(1, t); const lq = liquid(S, t); standPole(t); heroHands(t, lq); hideNearPoles(); noe.setExpr('grit');
      const pull = easeOut((lt - 0.9) / 0.5); upd(); const h = bus.hands[3]; h.g.visible = true; anim.grabAnkle(h, noe, 'R', 1, 1.15, 0.6, -1.7, 3.6);
      const shoeM = noe.ftR.matrixWorld.clone(); const sk = clamp((lt - 1.4) / 2.5); h.g.position.y -= 0.25 * pull + 0.2 * sk;
      noe.lgR.rotation.set(-0.48 - 0.6 * pull, 0, -0.12); noe.knR.rotation.x = 0.7 + 0.9 * pull; noe.setShoe('R', pull < 0.2); noe.torso.rotation.x = 0.1 - 0.25 * pull; anim.grip(noe, 'L', bus.w(POLE.local.x, 1.62, POLE.local.z), V(0, 1, 0), 0.034); upd();
      if (pull > 0.2) { E.shoeProp.visible = true; shoeM.decompose(E.shoeProp.position, E.shoeProp.quaternion, E.shoeProp.scale); E.shoeProp.position.y -= 0.25 * pull + 0.2 * sk; }
      S.focus = 2.55; S.dofScale = 0.6; S.shake = 0.12 + 0.45 * Math.max(0, 1 - Math.abs(lt - 1.1) * 3); });
  add('A18_court', T('A18', 4.4),
    (lt) => ({ pos: st.w(0.9, 0.55, 4.6), look: st.w(-1.6, 1.2, 13.2), fov: 58, roll: 0.03 }),
    (lt, u, t, S) => { E.lookStation(S, t, { out: true, sets: ['st', 'bus'] }); BUS_AT_STATION(); bus.setTubes(1, t); bus.setWindows(0xff2a1a, 1.1); bus.setDoor(1); bus.liquid.visible = false;
      const door = st.w(-2.0, 0, 13.4); const run = clamp((lt - 0.5) / 3.6); const p = lerpV(door, st.w(-0.2, 0, 5.2), ease(run)); const jump = lt < 0.6 ? 0.95 * (1 - ease(lt / 0.6)) : 0;
      anim.put(noe, p.x, p.z, Math.atan2(-0.2 + 2.0, 5.2 - 13.4), () => jump); noe.root.visible = true; if (run < 1) anim.run(noe, lt * 11, 1); noe.setShoe('R', false); noe.setExpr('scared');
      S.lights.push(...bus.tubeLights(1, t, 2.5, 6).slice(0, 2)); S.focus = lerp(8.5, 1.5, ease(run)); S.dofScale = 0.3; S.shake = 0.2; });
  return shots;
}
