// Acte C — la forêt enneigée (~173.6 → ~246.5 s).
export function actC(E) {
  const { V, THREE, anim, fo, noe, lina, shades, torch, at, clamp, lerp, ease, easeOut, easeIn, lerpV } = E;
  const shots = []; const add = (name, t0, cam, fn) => shots.push({ name, t0, cam, fn });
  const T = (id, d = -0.3) => at(id) + d;
  const P = (z, dx = 0, dy = 0) => fo.at(z, dx, dy);
  const gy = (x, z) => fo.gy(x, z);
  const putOn = (ch, z, dx, yaw, expr, t) => { const p = P(z, dx); anim.put(ch, p.x, p.z, yaw, (x, zz) => gy(x, zz)); ch.root.visible = true; if (expr) anim.expr(ch, expr, t, ch === lina ? 0.6 : 0.2); };
  const noeSet = (z, dx, yaw, expr, t) => { putOn(noe, z, dx, yaw, expr, t); noe.setShoe('R', false); };
  const yawTo = (a, b) => Math.atan2(b.x - a.x, b.z - a.z);
  // lampe de Lina : bras tendu, faisceau (projecteur 0)
  const torchOn = (S, k = 1, angle = 0.32) => { torch.g.visible = true; torch.set(k); lina.root.updateMatrixWorld(true); const p = torch.lens.getWorldPosition(V()); const d = V(0, 0, 1).applyQuaternion(torch.lens.getWorldQuaternion(new THREE.Quaternion()));
    S.spots = [{ pos: p, target: p.clone().addScaledVector(d, 10), color: 0xffe8c0, i: 60 * k, angle, pen: 0.5, dist: 30 }]; };
  const aimTorch = (yawOff = 0, pitch = 0) => { lina.shR.rotation.set(-1.45 + pitch, yawOff, 0.12); lina.handR.rotation.set(0, 0, 0); lina.setHands('relaxed', 'grip'); };
  const shadePos = [[-24, -4.2], [-26, 3.8], [-29, -5.5], [-31, 2.6], [-27.5, 6.2], [-33, -2.4], [-35, 4.9], [-30, -8]];
  const placeShades = (t, rush = 0, n = 8) => shades.forEach((s, i) => { if (i >= n) { s.root.visible = false; return; } const [z, dx] = shadePos[i]; const p = P(z + rush * (12 + i), dx * (1 - rush * 0.6)); anim.put(s, p.x, p.z, yawTo(p, P(-17, 0)), (x, zz) => gy(x, zz)); s.root.visible = true;
    if (rush > 0) anim.run(s, t * 12 + i, 1.1); else anim.breathe(s, t, 0.3); s.eyeM.color.setRGB(9, 0.4, 0.25); });
  // ---------------------------------------------------------------- C01 : la pluie devient neige, d'un coup
  add('C01_neige', T('C01'),
    (lt) => ({ pos: P(1.5, 0.6, 0.35), look: P(8, 0, 1.4), fov: 60, roll: 0.02 }),
    (lt, u, t, S) => { E.lookForest(S, t, { snowI: lt < 1.6 ? 0 : 1.6, moonDir: [-0.4, 0.55, 1] }); const k = clamp(lt / 2.2); noeSet(lerp(11, 5.5, ease(k)), 0, Math.PI, lt < 2.2 ? 'scared' : 'surprised', t); if (k < 1) anim.run(noe, lt * 10, 1); else anim.lookAt(noe, P(5.5, 0, 6), 0.8);
      if (lt < 1.6) S.rain = { i: 1.4, col: 0xc8d0ff, size: 1, speed: 1 }; S.flash = 0.35 * Math.max(0, 1 - Math.abs(lt - 1.6) * 5); S.focus = 4.5; S.shadowC = P(5); S.fade = ease(lt / 0.6); });
  // ---------------------------------------------------------------- C02 : la lune, trop grosse, trop carrée
  add('C02_lune', T('C02'),
    (lt) => ({ pos: P(7.5, 0.6, 0.35), look: P(-20, 0.3, 11 + lt * 1.2), fov: 62, roll: 0.0 }),
    (lt, u, t, S) => { E.lookForest(S, t, { moonDir: [0.32, 0.62, -1] }); noeSet(3.0, 0.5, Math.PI + 0.15, 'surprised', t); anim.pose(noe, 'lookUp', 0.8); S.moonSize = 30; S.focus = 12; S.dofScale = 0.25; S.shadowC = P(0); });
  // ---------------------------------------------------------------- C03 : des petites traces de pas
  add('C03_traces', T('C03'),
    (lt) => ({ pos: P(2.6, -0.05, 0.38), look: P(-1.5, 0.05, 0.02), fov: 50, roll: 0.04 }),
    (lt, u, t, S) => { E.lookForest(S, t, { keyI: 1.7 }); const k = ease((lt - 0.5) / 1.4); noeSet(0.4, 1.05, Math.PI - 0.6, 'worried', t); anim.crouch(noe, k); anim.pose(noe, 'lookDown', k); noe.shR.rotation.x -= 0.8 * k; S.focus = 1.6; S.dofScale = 0.7; S.shadowC = P(1); });
  // ---------------------------------------------------------------- C04 : au fond, une lumière rouge qui respire
  const breath = (t) => 0.55 + 0.45 * Math.sin(t * 1.6) ** 2;
  add('C04_lueur', T('C04'),
    (lt) => ({ pos: P(6.6 - lt * 0.15, 0.7, 1.85), look: P(-40, -0.2, 1.2), fov: 52, roll: 0 }),
    (lt, u, t, S) => { E.lookForest(S, t, { redGlow: 1.6 * breath(t) }); noeSet(3.2, 0.2, Math.PI, 'worried', t); S.focus = 3.5; S.dofScale = 0.4; S.shadowC = P(0); });
  // ---------------------------------------------------------------- C05 : elle crie son nom
  add('C05_cri', T('C05'),
    (lt) => ({ pos: P(1.35, -0.85, 1.72), look: P(3.2, 0.2, 1.74), fov: 44, roll: -0.03 }),
    (lt, u, t, S) => { E.lookForest(S, t, { redGlow: 1.2 }); noeSet(3.2, 0.2, Math.PI, lt < 0.4 ? 'worried' : 'surprised', t); noe.neck.rotation.y += 0.55 * easeOut((lt - 0.35) / 0.25); S.focus = 2.0; S.dofScale = 0.7; S.shake = 0.15; S.mblur = 0.6; S.shadowC = P(2); });
  // ---------------------------------------------------------------- C06 : Lina, la lampe braquée sur les arbres, elle tremble (plan des illustrations)
  const LZ = -18.5;
  add('C06_lina', T('C06'),
    (lt) => ({ pos: P(LZ + 2.9, 0.55, 0.45), look: P(LZ, -0.3, 1.25), fov: 58, roll: 0.07 }),
    (lt, u, t, S) => { E.lookForest(S, t, { moonDir: [-0.55, 0.6, -1], redGlow: 1.2 }); putOn(lina, LZ, -0.3, 1.1, 'scream', t); aimTorch(0.1 + 0.05 * Math.sin(t * 13), 0.04 * Math.sin(t * 17)); lina.torso.rotation.z = 0.05 * Math.sin(t * 21);
      lina.lgL.rotation.set(-0.45, 0, 0.1); lina.lgR.rotation.set(0.35, 0, -0.1); lina.neck.rotation.y = -0.55; torchOn(S, 1);
      fo.hands.forEach((h, i) => { if (i > 4) { h.g.visible = false; return; } const p = P(LZ + 1.6 - i * 0.35, -1.4 + i * 0.6); h.g.visible = true; h.g.position.copy(p).sub(fo.origin).add(V(0, -0.35 + 0.08 * Math.sin(t * 2 + i), 0)); h.g.rotation.set(-0.2, i, 0.2); h.set(0.2 + 0.2 * Math.sin(t * 3 + i), 0.3); h.g.visible = lt > 2.2 && false; });
      placeShades(t, 0, 3); S.focus = 2.9; S.dofScale = 0.55; S.shadowC = P(LZ); });
  // ---------------------------------------------------------------- C06b : elle se jette dans ses bras
  add('C06b_bras', T('C06b'),
    (lt) => ({ pos: P(LZ + 4.2, 3.6, 1.7), look: P(LZ + 1.85, 0, 1.3), fov: 52, roll: 0 }),
    (lt, u, t, S) => { E.lookForest(S, t, { redGlow: 1.0 }); const k = easeOut(lt / 0.9); const ln = lerpV(P(LZ + 0.2, 0), P(LZ + 1.55, 0.02), k);
      anim.put(lina, ln.x, ln.z, 0, (x, z) => gy(x, z)); lina.root.visible = true; if (k < 1) anim.run(lina, lt * 10, 1); anim.pose(lina, 'hug', k); lina.setExpr('cry'); torch.g.visible = true; torch.set(1);
      noeSet(LZ + 2.1, 0, Math.PI, 'relief', t); anim.pose(noe, 'hug', ease((lt - 0.5) / 0.5)); torchOn(S, 1, 0.4); S.focus = 4.2; S.dofScale = 0.5; S.shadowC = P(LZ + 2); });
  // ---------------------------------------------------------------- C07 : Lina parle (« ils ne bougent que quand la lumière s'éteint »)
  add('C07_parle', T('C07'),
    (lt) => ({ pos: P(LZ + 3.15, 0.95, 1.62), look: P(LZ + 1.5, 0, 1.58), fov: 44, roll: -0.03 }),
    (lt, u, t, S) => { E.lookForest(S, t, { redGlow: 1.0 }); putOn(lina, LZ + 1.5, 0, 0.55, null, t); const talk = Math.sin(t * 14) > 0 && (lt % 1.6) < 1.3; lina.setExpr(anim.blink(t, 0.6) ? 'blink' : talk ? 'scared' : 'worried');
      aimTorch(-0.9, 0.35); lina.shR.rotation.x += 0.5; torchOn(S, 0.45, 0.5); noeSet(LZ + 2.35, -0.2, Math.PI - 0.4, 'worried', t); noe.root.visible = false; S.focus = 1.85; S.dofScale = 0.8; S.shadowC = P(LZ + 1.5);
      S.lights.push({ pos: P(LZ + 1.8, 0.1, 0.9), color: 0xffe0b0, i: 1.0, dist: 2.2, decay: 2 }); });
  // ---------------------------------------------------------------- C08 : derrière elle, des silhouettes aux yeux rouges, immobiles
  add('C08_silhouettes', T('C08'),
    (lt) => ({ pos: P(LZ + 3.6, 1.35, 0.4), look: P(LZ - 10, 1.0, 0), fov: 48, roll: 0 }),
    (lt, u, t, S) => { E.lookForest(S, t, { redGlow: 1.3 }); putOn(lina, LZ + 2.2, 0.35, Math.PI + 0.3, 'scared', t); aimTorch(0.3, 0.1); torchOn(S, 0.9); placeShades(t, 0, 8); noeSet(LZ + 2.8, -0.4, Math.PI, 'scared', t); noe.root.visible = false;
      S.focus = lerp(1.3, 9, ease((lt - 0.8) / 1.8)); S.dofScale = 0.9; S.shadowC = P(LZ - 4); S.shadowS = 16; });
  // ---------------------------------------------------------------- C09 : la lampe grésille, une fois, deux fois
  const flick = (lt) => { const off = (lt > 0.6 && lt < 0.85) || (lt > 1.9 && lt < 2.25) || (lt > 2.4 && lt < 2.55); return off ? 0.05 : 1; };
  add('C09_grésille', T('C09'),
    (lt) => ({ pos: P(LZ + 0.55, 0.05, 1.25), look: P(LZ + 2.2, 0.3, 1.2), fov: 46, roll: 0.05 }),
    (lt, u, t, S) => { E.lookForest(S, t, { redGlow: 1.3, keyI: 1.2 }); putOn(lina, LZ + 2.2, 0.35, Math.PI + 0.3, 'scared', t); aimTorch(0.3, 0.1); torchOn(S, flick(lt)); placeShades(t, 0, 8); noeSet(LZ + 2.8, -0.4, Math.PI, 'scared', t);
      S.focus = 0.9; S.dofScale = 0.9; S.shadowC = P(LZ); S.exposure = 0.75 + 0.25 * flick(lt); });
  // ---------------------------------------------------------------- C10 : puis elle s'est éteinte (seuls les yeux)
  add('C10_noir', T('C10'),
    (lt) => ({ pos: P(LZ + 3.2, 1.3, 0.3), look: P(LZ - 9, 1.1, 0), fov: 50, roll: 0 }),
    (lt, u, t, S) => { E.lookForest(S, t, { redGlow: 0.4, keyI: 0.25 }); putOn(lina, LZ + 2.2, 0.35, Math.PI + 0.3, 'scared', t); aimTorch(0.3, 0.1); torch.g.visible = true; torch.set(0); placeShades(t, 0, 8); noeSet(LZ + 2.8, -0.4, Math.PI, 'scared', t);
      S.hemi.i = 0.15; S.fill.i = 0.1; S.exposure = 0.55; S.focus = 8; S.dofScale = 0.4; S.snow.i = 0.5; S.shadowC = P(LZ); });
  // ---------------------------------------------------------------- C11 : ils ont couru, tous en même temps
  add('C11_ruee', T('C11'),
    (lt) => ({ pos: P(LZ + 2.0, 1.0, 0.2), look: P(LZ - 8, 1.1, 0), fov: 54, roll: 0.05 * Math.sin(lt * 7) }),
    (lt, u, t, S) => { E.lookForest(S, t, { redGlow: 0.8, keyI: 0.5 }); placeShades(t, ease(lt / 3) * 0.75, 8); torch.g.visible = false; S.exposure = 0.7; S.focus = 5; S.dofScale = 0.5; S.shake = 0.6; S.mblur = 0.8; S.shadowC = P(LZ - 5); });
  // ---------------------------------------------------------------- C12 : des mains sortent de la neige, partout
  add('C12_mains', T('C12'),
    (lt) => ({ pos: P(LZ + 5.4, 0.5, 1.1), look: P(LZ + 2.2, 0, 0.8), fov: 60, roll: -0.04 }),
    (lt, u, t, S) => { E.lookForest(S, t, { redGlow: 1.0, keyI: 1.0 }); putOn(lina, LZ + 2.0, 0.4, 0.3, 'scream', t); noeSet(LZ + 2.4, -0.35, -0.2, 'scream', t); anim.pose(noe, 'armsOpen', 0.4); torch.g.visible = false;
      fo.hands.forEach((h, i) => { const a = i / 14 * 6.28, rr = 1.0 + (i % 3) * 0.55; const c = P(LZ + 2.2); const x = c.x + Math.cos(a) * rr, z = c.z + Math.sin(a) * rr; const k = easeOut((lt - (i % 7) * 0.18) / 0.6); if (k <= 0) { h.g.visible = false; return; }
        h.g.visible = true; h.g.position.set(x - fo.origin.x, gy(x, z) - 0.6 + 0.62 * k, z - fo.origin.z); h.g.rotation.set(-0.15 * Math.cos(a), Math.atan2(c.x - x, c.z - z), 0.15 * Math.sin(a)); h.set(0.15 + 0.35 * Math.sin(t * 3 + i), 0.32); });
      S.dust = { i: 2.5, col: 0xe8f0ff, size: 1.2, box: V(5, 3, 5) }; S.focus = 3.2; S.dofScale = 0.6; S.shake = 0.3; S.shadowC = P(LZ + 2); });
  // ---------------------------------------------------------------- C13 : il attrape Lina par le bras ; ils courent
  add('C13_course', T('C13'),
    (lt) => { const z = LZ - 1 - lt * 1.6; return { pos: P(z - 4.6, 0.7, 1.2), look: P(z + 0.3, 0.0, 1.1), fov: 56, roll: 0.03 * Math.sin(lt * 9) }; },
    (lt, u, t, S) => { E.lookForest(S, t, { redGlow: 1.4 }); const z = LZ - 1 - lt * 1.6; noeSet(z - 0.4, -0.3, Math.PI, 'scared', t); anim.run(noe, lt * 11, 1); noe.shL.rotation.set(0.6, 0, 0.5);
      putOn(lina, z + 0.3, 0.35, Math.PI, 'scream', t); anim.run(lina, lt * 11 + 1.5, 1); lina.shR.rotation.set(-0.9, 0, -0.5); torch.g.visible = false;
      shades.forEach((s, i) => { if (i > 4) { s.root.visible = false; return; } const p = P(z + 5 + i * 1.3, (i - 2) * 1.4); anim.put(s, p.x, p.z, Math.PI, (x, zz) => gy(x, zz)); s.root.visible = true; anim.run(s, lt * 12 + i, 1.1); });
      S.focus = 4.5; S.dofScale = 0.4; S.shake = 0.45; S.mblur = 0.6; S.shadowC = P(z); });
  // ---------------------------------------------------------------- C14 : le sol s'ouvre sous leurs pieds
  add('C14_trou', T('C14'),
    (lt) => { const c = fo.holeC.clone().add(fo.origin); const fall = easeIn((lt - 1.4) / 2.5); return { pos: c.clone().add(V(0.5, 5.2 - fall * 12, 1.6 - fall * 1.4)), look: c.clone().add(V(0, -2.0 - fall * 12, 0)), fov: 62, roll: 0.15 * fall }; },
    (lt, u, t, S) => { E.lookForest(S, t, { redGlow: 1.0 }); const k = clamp((lt - 0.5) / 1.6); fo.setHole(k, t); const c = fo.holeC.clone().add(fo.origin); const fall = easeIn((lt - 1.0) / 1.8) * 16;
      const yN = c.y - fall, yL = c.y - fall * 0.92; anim.put(noe, c.x - 0.3, c.z + 0.3, Math.PI, () => (k > 0.15 ? yN : c.y)); noe.root.visible = true; noe.setShoe('R', false); noe.setExpr('scream'); anim.pose(noe, 'armsOpen', 0.8);
      anim.put(lina, c.x + 0.35, c.z - 0.1, Math.PI, () => (k > 0.2 ? yL : c.y)); lina.root.visible = true; lina.setExpr('scream'); anim.pose(lina, 'armsOpen', 0.8);
      S.lights.push({ pos: c.clone().add(V(0, -8, 0)), color: 0xff3010, i: 10 * k, dist: 18, decay: 1.2 }); S.focus = 3.5; S.dofScale = 0.4; S.shake = 0.4 * k; S.shadowC = c; S.fade = 1 - ease((lt - 5.4) / 0.8); });
  return shots;
}
