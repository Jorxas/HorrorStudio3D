// Actes D et E — l'abîme de lave, puis l'escalier suspendu et la porte (~246.5 → fin).
export function actDE(E) {
  const { V, THREE, anim, ab, noe, linaHurt: lina, shades, lantern, at, clamp, lerp, ease, easeOut, easeIn, lerpV } = E;
  const shots = []; const add = (name, t0, cam, fn) => shots.push({ name, t0, cam, fn });
  const T = (id, d = -0.3) => at(id) + d;
  const A = (x, y, z) => ab.w(x, y, z);
  const LEDGE = 1.5, FAR = 2.6;
  const put = (ch, p, yaw, expr, t, seed = 0.2) => { anim.put(ch, p.x, p.z, yaw, () => p.y); ch.root.visible = true; if (expr) anim.expr(ch, expr, t, seed); if (ch === noe) noe.setShoe('R', false); };
  const yawTo = (a, b) => Math.atan2(b.x - a.x, b.z - a.z);
  // lanterne tenue (main droite de Noé) : position monde + lumière
  const holdLantern = (t, on = 1) => { noe.shR.rotation.set(-0.3, 0, 0.12); noe.elR.rotation.x = -0.55; noe._lockR = true; noe.setHands('relaxed', 'grip'); noe.root.updateMatrixWorld(true); const p = noe.handR.localToWorld(V(-0.03, -0.2, 0.02)); lantern.g.visible = true; lantern.g.position.copy(p).add(V(0, -0.1, 0)); lantern.g.rotation.set(0, noe.root.rotation.y, 0); lantern.set(on, t); return { pos: lantern.g.position.clone().add(V(0, 0.05, 0)), ...lantern.light(on, t) }; };
  const STEP = (i) => { const s = ab.steps[i]; return A(s.x, s.y, s.z); };
  const talkExpr = (t, a, b, seed = 0.6) => (anim.blink(t, seed) ? 'blink' : (Math.sin(t * 13) > 0 && (t % 1.7) < 1.35) ? a : b);
  // ================================================================ ACTE D
  // ---------------------------------------------------------------- D01 : la chute (longue), braises qui remontent, puis le choc
  add('D01_chute', T('D01'),
    (lt) => { if (lt < 3.6) { const y = 30 - lt * 7.5; return { pos: A(0.7, y - 3.6, 19.2), look: A(0, y + 1.5, 18.2), fov: 64, roll: lt * 0.15 }; }
      const k = lt - 3.6; return { pos: A(0.9, ab.lake.y - 2.4 - k * 0.15, 19.6), look: A(0, ab.lake.y - 1.2 - k * 0.2, 18.0), fov: 60, roll: 0.05 * Math.sin(k) }; },
    (lt, u, t, S) => {
      const kids = (y, k) => { put(noe, A(-0.3, y, 18.0), lt * 0.8, k < 0 ? 'scream' : 'scared', t); noe.root.rotation.set(0.5 * Math.sin(lt * 1.3), lt * 0.8, 0.6 * Math.sin(lt)); anim.pose(noe, 'armsOpen', 1); noe.lgL.rotation.x = -0.4 * Math.sin(lt * 5); noe.lgR.rotation.x = 0.4 * Math.sin(lt * 5);
        put(lina, A(0.5, y + 0.6, 18.4), -lt * 0.6, k < 0 ? 'scream' : 'scared', t); lina.root.rotation.set(-0.4 * Math.sin(lt * 1.1), -lt * 0.6, 0.5 * Math.cos(lt)); anim.pose(lina, 'armsOpen', 1); };
      if (lt < 3.6) {   // la chute dans le noir complet
        E.lookCave(S, t); S.sets = []; S.lights = [{ pos: A(0, 30 - lt * 7.5 - 8, 18.5), color: 0x40c8ff, i: 3 * ease(lt / 3.6), dist: 14 }]; S.hemi = { sky: 0x050a10, ground: 0x02060a, i: 0.25 }; S.key.i = 0.2; S.fill.i = 0.3; S.fog = { color: 0x000000, d: 0.02 }; S.bg = 0x000000; S.mist = null; S.reflect = null;
        S.embers = { i: 2.2, col: 0x9ab8d0, size: 0.8, speed: 7 }; S.dust = null; kids(30 - lt * 7.5, -1); S.mblur = 0.6; S.shake = 0.3; S.focus = 3.8; S.dofScale = 0.4;
        S.fade = ease(lt / 0.4); S.flash = 0.9 * Math.max(0, 1 - Math.abs(lt - 3.58) * 8); S.flashCol = 0xc8f4ff; S.shadowC = A(0, 0, 18);
      } else {          // sous l'eau : bulles, rayons, ils coulent puis remontent
        const k = lt - 3.6; E.lookUnder(S, t, { near: A(0, -1.5, 18.2) }); const y = ab.lake.y - 0.8 - 1.2 * easeOut(k / 1.6) + 1.6 * ease((k - 2.0) / 1.2); kids(y, 1);
        noe.root.rotation.set(0.2 * Math.sin(lt), lt * 0.3, 0.3 * Math.sin(lt * 0.8)); lina.root.rotation.set(-0.2 * Math.sin(lt * 0.9), -lt * 0.3, 0.2); noe.shL.rotation.z = 1.6 + 0.5 * Math.sin(lt * 3); noe.shR.rotation.z = -1.6 - 0.5 * Math.sin(lt * 3);
        S.focus = 2.0; S.shake = 0.08 + 0.6 * Math.max(0, 1 - k * 3); S.flash = 0.6 * Math.max(0, 1 - k * 4); S.flashCol = 0xc8f4ff; S.fade = 1 - ease((k - 2.6) / 0.45); S.shadowC = A(0, 0, 18);
      }
    });
  // Noé allongé sur le dos (corniche), il ouvre les yeux
  const lyNoe = (t, lt) => { const p = A(-0.3, LEDGE + 0.12, 6.2); anim.put(noe, p.x, p.z, 0, () => p.y); noe.root.rotation.set(-Math.PI / 2, 0, 0.25); noe.root.position.y = p.y; noe.root.position.z = p.z - 0.4; noe.root.visible = true; noe.setShoe('R', false);
    noe.shL.rotation.set(0, 0, 0.5); noe.shR.rotation.set(0, 0, -0.35); noe.neck.rotation.set(-0.1, 0.25, 0); noe.setExpr(lt < 1.1 ? 'blink' : (lt < 1.3 ? 'neutral' : lt < 1.45 ? 'blink' : 'scared')); };
  // ---------------------------------------------------------------- D02 : il rouvre les yeux ; trop chaud
  add('D02_reveil', T('D02'),
    (lt, u, t) => { lyNoe(t, lt); noe.root.updateMatrixWorld(true); const h = noe.head.getWorldPosition(V()), f = noe.head.getWorldDirection(V()); const feet = noe.root.getWorldPosition(V()).sub(h).setY(0).normalize(); return { pos: h.clone().addScaledVector(f, 1.25).addScaledVector(feet, 0.9), look: h.clone().addScaledVector(feet, 0.1), fov: 46, roll: 0 }; },
    (lt, u, t, S) => { E.lookCave(S, t, { near: A(0, 2, 7) }); lyNoe(t, lt); S.key = { dir: [0.1, 0.5, -1], color: 0xff8a40, i: 0.8 }; S.lights.push({ pos: A(0, 2.5, -2), color: 0xff6a20, i: 3, dist: 9 }); S.focus = 1.5; S.dofScale = 0.8; S.fade = ease(lt / 1.0); S.embers = { i: 1.0, col: 0xffa060, size: 0.8, speed: 0.4 }; S.shadowC = A(0, LEDGE, 6); });
  // ---------------------------------------------------------------- D03 : falaises noires, cascades, pont et château
  add('D03_revele', T('D03'),
    (lt) => { const k = ease(lt / 6.5); return { pos: lerpV(A(-0.5, LEDGE + 0.9, 5.2), A(1.0, LEDGE + 4.2, 7.5), k), look: lerpV(A(0, LEDGE + 1.2, 2), A(-2, 9, -60), ease(lt / 4)), fov: 60, roll: 0 }; },
    (lt, u, t, S) => { E.lookAbyss(S, t, { lightAt: A(0, 0, -4) }); put(noe, A(0.2, LEDGE, 2.6), Math.PI, 'surprised', t); anim.pose(noe, 'lookUp', 0.5); S.focus = lerp(3, 40, ease(lt / 3)); S.dofScale = 0.12; S.shadowC = A(0, LEDGE, 0); S.shadowS = 16; });
  // ---------------------------------------------------------------- D04 : Lina se relève, manteau déchiré, mains brûlées, elle serre les dents
  add('D04_lina', T('D04'),
    (lt) => ({ pos: A(1.3, LEDGE + 0.45, 3.9), look: A(0.5, LEDGE + 1.0, 2.0), fov: 54, roll: 0.05 }),
    (lt, u, t, S) => { E.lookAbyss(S, t, { lightAt: A(0, 0, 1) }); const k = ease((lt - 0.4) / 2.2); put(lina, A(0.5, LEDGE, 2.0), 0.4, 'grit', t); anim.kneel(lina, 1 - k); lina.shL.rotation.set(-0.6 * (1 - k), 0, 0.3); lina.shR.rotation.set(-0.4, 0, -0.4 * k);
      lina.setHands('fist', 'claw'); put(noe, A(-0.6, LEDGE, 2.6), 1.2, 'worried', t); noe.root.visible = false; S.focus = 2.0; S.dofScale = 0.5; S.shadowC = A(0, LEDGE, 2); });
  // ---------------------------------------------------------------- D05 : « Si on est descendus, il y a forcément un chemin pour remonter. »
  add('D05_parle', T('D05'),
    (lt) => ({ pos: A(1.25, LEDGE + 1.5, 3.55), look: A(0.5, LEDGE + 1.45, 2.0), fov: 44, roll: -0.03 }),
    (lt, u, t, S) => { E.lookAbyss(S, t, { lightAt: A(0, 0, 1) }); put(lina, A(0.5, LEDGE, 2.0), 0.45, null, t); lina.setExpr(talkExpr(t, 'shout', 'determined')); lina.neck.rotation.x = -0.12; S.focus = 1.75; S.dofScale = 0.9; S.shadowC = A(0, LEDGE, 2); });
  // ---------------------------------------------------------------- D06 : de colonne en colonne, la lave juste en dessous
  const jumpPath = (ch, lt, phase, speed = 0.9) => { const f = Math.max(0, lt * speed - phase); const i = Math.floor(f), a = f - i; const p0 = i === 0 ? A(0.5, LEDGE, -2.0) : STEP(i - 1), p1 = STEP(Math.min(i, ab.steps.length - 1)); const p = lerpV(p0, p1, ease(a)); p.y += Math.sin(a * Math.PI) * 0.75; return { p, a, yaw: yawTo(p0, p1) }; };
  add('D06_colonnes', T('D06'),
    (lt) => { const f = lt * 0.9; const c = lerpV(STEP(0), STEP(4), clamp(f / 4.6)); return { pos: c.clone().add(V(-3.4, 5.2, 3.6)), look: c.clone().add(V(0.3, 0.6, -0.9)), fov: 56, roll: -0.03 }; },
    (lt, u, t, S) => { E.lookAbyss(S, t, { lightAt: STEP(2) }); const a = jumpPath(noe, lt, 0); put(noe, a.p, a.yaw, 'grit', t); anim.jump(noe, a.a, 0, 1, 0.01); if (a.a > 0.05 && a.a < 0.95) { noe.shL.rotation.x = -2.0; noe.shR.rotation.x = -1.6; noe.lgL.rotation.x = -0.6; noe.lgR.rotation.x = 0.4; }
      const b = jumpPath(lina, lt, 0.7); put(lina, b.p, b.yaw, 'grit', t); if (b.a > 0.05 && b.a < 0.95) { lina.shL.rotation.x = -2.0; lina.shR.rotation.x = -1.6; lina.lgL.rotation.x = -0.6; lina.lgR.rotation.x = 0.4; }
      S.focus = 4.8; S.dofScale = 0.4; S.shadowC = STEP(3); S.shake = 0.15; });
  // ---------------------------------------------------------------- D06b : elle glisse ; il la rattrape par le poignet, au-dessus de la lave
  add('D06b_rattrape', T('D06b'),
    (lt) => { const c = STEP(5); return { pos: c.clone().add(V(2.7, -1.0, 0.9)), look: c.clone().add(V(0.15, -0.5, 0.5)), fov: 58, roll: -0.08 }; },
    (lt, u, t, S) => { E.lookAbyss(S, t, { lightAt: STEP(5) }); const c = STEP(5); const slip = easeIn(clamp((lt - 0.3) / 0.6)); const pull = ease((lt - 5.2) / 1.6);
      put(noe, c.clone().add(V(-0.1, 0, -0.2)), 0.25, lt < 0.5 ? 'surprised' : 'grit', t); anim.kneel(noe, 0.9); noe.torso.rotation.x += 0.55; noe.shR.rotation.set(-2.2 + 0.3 * pull, 0, 0.25); noe.setHands('grip', 'grip');
      const hang = c.clone().add(V(0.25, -1.75 * (1 - pull) + (1 - slip) * 1.75 * (1 - pull), 0.75 - 0.3 * pull)); put(lina, hang, Math.PI + 0.25, slip > 0.5 && pull < 0.8 ? 'scream' : 'scared', t);
      lina.shR.rotation.set(-2.9, 0, 0.1); lina.shL.rotation.set(-0.8 + 0.4 * Math.sin(t * 5), 0, 0.8); lina.lgL.rotation.x = 0.4 * Math.sin(t * 4); lina.lgR.rotation.x = -0.4 * Math.sin(t * 4); lina.setHands('relaxed', 'grip');
      S.focus = 2.0; S.dofScale = 0.5; S.shake = 0.15 + 0.3 * slip * (1 - pull); S.shadowC = c; });
  // ---------------------------------------------------------------- D07 : une vieille lanterne, qui s'allume toute seule
  const LAN = A(-0.6, FAR, -22.2);
  add('D07_lanterne', T('D07'),
    (lt) => (lt < 3.6 ? { pos: A(1.3, FAR + 0.7, -20.1), look: A(-0.55, FAR + 0.3, -22.1), fov: 46, roll: 0.04 } : { pos: A(1.1, FAR + 1.7, -19.9), look: A(-0.45, FAR + 1.5, -21.6), fov: 48, roll: -0.03 }),
    (lt, u, t, S) => { E.lookAbyss(S, t, { lightAt: A(0, 0, -20) }); S.hemi.i = 0.75; S.lights.push({ pos: A(3.5, FAR - 0.5, -21.5), color: 0xff7030, i: 4, dist: 8 }); const pick = ease((lt - 1.6) / 1.4); const on = ease((lt - 3.4) / 0.4) * (0.6 + 0.4 * ease((lt - 3.8) / 1)); put(noe, A(0.35, FAR, -22.55), -Math.PI / 2 - 0.2, lt < 3.4 ? 'worried' : 'surprised', t);
      anim.crouch(noe, 1 - pick * 0.8); noe.shR.rotation.set(-1.0 + 0.5 * pick, 0, 0.12); noe.setHands('relaxed', 'grip');
      if (pick < 0.7) { lantern.g.visible = true; lantern.g.position.copy(LAN).add(V(0, 0.15 + 0.6 * pick, 0)); lantern.g.rotation.set(0, 0.4, 0); lantern.set(on, t); S.lights.push({ pos: LAN.clone().add(V(0, 0.3, 0)), ...lantern.light(on, t) }); }
      else S.lights.push(holdLantern(t, on)); put(lina, A(-1.4, FAR, -21.3), Math.PI + 0.5, 'worried', t);
      S.focus = lt < 3.6 ? 2.6 : 2.4; S.dofScale = 0.6; S.shadowC = A(0, FAR, -21.5); S.shadowS = 6; });
  // ---------------------------------------------------------------- D08 : tout là-haut, l'escalier suspendu et la porte
  add('D08_escalier', T('D08'),
    (lt) => { const k = ease(lt / 7.5); return { pos: A(1.3, FAR + 0.9 + k * 0.6, -18.2 + k * 1.2), look: lerpV(A(-0.3, FAR + 1.2, -22.5), A(0, ab.GY + 6, -66), ease((lt - 0.6) / 5)), fov: 58, roll: 0 }; },
    (lt, u, t, S) => { E.lookAbyss(S, t, { lightAt: A(0, 0, -20) }); put(noe, A(-0.4, FAR, -22.8), Math.PI, 'surprised', t); S.lights.push(holdLantern(t, 1)); anim.pose(noe, 'lookUp', 0.6); put(lina, A(0.5, FAR, -22.5), Math.PI, 'worried', t); anim.pose(lina, 'lookUp', 0.6);
      ab.setStairs(t, 0.3); ab.setRunes(0.12, 0.3, t); S.fog.d = 0.009; S.focus = lerp(5, 40, ease((lt - 1) / 3)); S.dofScale = 0.12; S.shadowC = A(0, FAR, -22); S.shadowS = 10; });
  // ================================================================ ACTE E
  // ---------------------------------------------------------------- E01 : on monte ; les blocs tremblent (plan des illustrations)
  const climb = (lt, i0, speed, phase = 0) => { const f = i0 + Math.max(0, lt * speed - phase); const i = Math.floor(f), a = f - i; const p0 = ab.stairTop(i, 0), p1 = ab.stairTop(i + 1, 0); const p = lerpV(p0, p1, ease(a)); p.y += Math.sin(a * Math.PI) * 0.18; return { p, yaw: yawTo(p0, p1), f }; };
  add('E01_monte', T('E01'),
    (lt) => { const c = climb(lt, 6, 1.3).p; return { pos: c.clone().add(V(1.7, -0.25, 1.5)), look: c.clone().add(V(-0.1, 0.95, -0.6)), fov: 60, roll: -0.08 }; },
    (lt, u, t, S) => { E.lookGate(S, t); ab.setStairs(t, 1.2); ab.setRunes(0.1, 0.3, t); const a = climb(lt, 6, 1.3); put(noe, a.p, a.yaw, 'scared', t); anim.walk(noe, a.f * Math.PI, 0.9); S.lights = [holdLantern(t, 1), { pos: ab.w(0, 33, -64), color: 0xff2010, i: 4, dist: 30 }];
      const b = climb(lt, 4.6, 1.3); put(lina, b.p, b.yaw, 'scared', t); anim.walk(lina, b.f * Math.PI + 1, 0.9); S.focus = 2.2; S.dofScale = 0.6; S.shake = 0.18; S.shadowC = a.p; S.shadowS = 6; });
  // ---------------------------------------------------------------- E02 : dans l'ombre, les yeux rouges ; ils attendent
  const perch = [[-6, 12, -38], [7, 15, -42], [-9, 18, -47], [5, 22, -50], [-4, 26, -56], [9, 24, -55], [-11, 14, -44], [11, 19, -48]];
  const placePerch = (t, n = 8) => shades.forEach((s, i) => { if (i >= n) { s.root.visible = false; return; } const q = A(...perch[i]); anim.put(s, q.x, q.z, yawTo(q, A(0, q.y, -40)), () => q.y); s.root.visible = true; anim.breathe(s, t, 0.3); s.eyeM.color.setRGB(9, 0.4, 0.25);
    const blk = new THREE.Mesh(); });
  const perchBlocks = (() => { const g = new THREE.Group(); const m = new THREE.MeshLambertMaterial({ color: 0x1a1416 }); perch.forEach((p) => { const b = new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.7, 1.4), m); b.position.set(p[0], p[1] - 0.35, p[2]); b.castShadow = true; g.add(b); }); ab.group.add(g); return g; })();
  add('E02_yeux', T('E02'),
    (lt) => { const c = climb(lt, 12, 0.9).p; return { pos: c.clone().add(V(1.7, 1.45, 0.1)), look: A(-5 + lt * 0.6, 15, -44), fov: 60, roll: 0.02 }; },
    (lt, u, t, S) => { E.lookGate(S, t); ab.setStairs(t, 0.8); ab.setRunes(0.1, 0.3, t); const a = climb(lt, 12, 0.9); put(noe, a.p, a.yaw, 'scared', t); anim.walk(noe, a.f * Math.PI, 0.8); anim.lookAt(noe, A(-6, 12, -38), 0.6); S.lights = [holdLantern(t, 1), { pos: ab.w(0, 33, -64), color: 0xff2010, i: 4, dist: 30 }];
      const b = climb(lt, 10.7, 0.9); put(lina, b.p, b.yaw, 'scared', t); anim.walk(lina, b.f * Math.PI + 1, 0.8); placePerch(t); S.focus = 14; S.dofScale = 0.25; S.shake = 0.1; S.shadowC = a.p; S.shadowS = 8; });
  // ---------------------------------------------------------------- E03 : les runes s'allument, comme si elles comptaient nos pas (plan des illustrations)
  add('E03_runes', T('E03'),
    (lt) => ({ pos: A(1.6 - lt * 0.1, ab.GY + 0.45, -53.6 - lt * 0.35), look: A(-0.3, ab.GY + 4.5, -67), fov: 62, roll: 0.03 }),
    (lt, u, t, S) => { E.lookGate(S, t); ab.setStairs(t, 0.4); const ks = ab.pillars.map((p, i) => ease((lt - 0.6 - (i % 3) * 1.25 - (i >= 3 ? 0.25 : 0)) / 0.3)); ab.setRunes(ks, 0.35 + 0.4 * ease((lt - 4) / 1.5), t);
      const k = clamp(lt / 5.6); put(noe, A(-0.4, ab.GY, lerp(-54.5, -58.5, k)), Math.PI, 'scared', t); anim.walk(noe, lt * 5, 0.5); S.lights = [holdLantern(t, 1), { pos: ab.w(0, 33, -64), color: 0xff2010, i: 6, dist: 30 }];
      put(lina, A(0.5, ab.GY, lerp(-54.0, -58.0, k)), Math.PI, 'scared', t); anim.walk(lina, lt * 5 + 1, 0.5); S.focus = 5.5; S.dofScale = 0.3; S.shadowC = A(0, ab.GY, -58); S.shadowS = 10;
      S.extraReflect = true; });
  // ---------------------------------------------------------------- E04 : la porte immense ; derrière, trois coups
  const knocks = (lt) => [3.95, 4.55, 5.15].reduce((a, k) => a + Math.max(0, 1 - Math.abs(lt - k) * 7) * (lt > k - 0.02 ? 1 : 0), 0);
  add('E04_porte', T('E04'),
    (lt) => ({ pos: A(0.6, ab.GY + 1.2, -57.5 + lt * 0.15), look: A(0, ab.DY + 6.5, ab.DZ), fov: 60, roll: 0 }),
    (lt, u, t, S) => { E.lookGate(S, t); const kn = knocks(lt); ab.setRunes(1, 0.7 + 0.8 * kn, t); ab.setDoorGlow(0.15 + kn * 0.8); put(noe, A(-0.45, ab.GY + 1.65, -63.6), Math.PI, 'scared', t); S.lights = [holdLantern(t, 1), { pos: ab.w(0, 33, -64), color: 0xff2010, i: 6 + kn * 8, dist: 30 }];
      put(lina, A(0.45, ab.GY + 1.65, -63.3), Math.PI, 'scared', t); S.shake = 0.08 + kn * 0.9; S.focus = 7; S.dofScale = 0.25; S.flash = kn * 0.12; S.flashCol = 0xff2010; S.shadowC = A(0, ab.GY, -63); });
  // ---------------------------------------------------------------- E05 : une voix. Sa voix.
  add('E05_voix', T('E05'),
    (lt) => ({ pos: A(0.1, ab.GY + 3.05, -61.95), look: A(-0.45, ab.GY + 3.05, -63.6), fov: 44, roll: 0.03 }),
    (lt, u, t, S) => { E.lookGate(S, t); ab.setRunes(1, 0.9, t); ab.setDoorGlow(0.4); put(noe, A(-0.45, ab.GY + 1.65, -63.6), 0.25, lt < 0.6 ? 'scared' : 'surprised', t); anim.lookAt(noe, A(0.1, ab.GY + 3, -62), 0.3); S.lights = [holdLantern(t, 1), { pos: ab.w(0, 33, -64), color: 0xff2010, i: 8, dist: 30 }];
      S.focus = 1.75; S.dofScale = 0.9; S.shake = 0.05; S.shadowC = A(0, ab.GY, -63); });
  // ---------------------------------------------------------------- E06 : « Noé... ouvre. Tu es enfin rentré. » (la fente rougeoie)
  add('E06_fente', T('E06'),
    (lt) => ({ pos: A(0.0, ab.DY + 4.0, ab.DZ + 3.2 - lt * 0.35), look: A(0, ab.DY + 4.6, ab.DZ), fov: 46, roll: 0 }),
    (lt, u, t, S) => { E.lookGate(S, t); ab.setRunes(1, 1.4 + 0.6 * Math.sin(t * 7), t); ab.setDoorGlow(0.6 + 0.4 * Math.sin(t * 9)); S.lights = [{ pos: A(0, ab.DY + 3, ab.DZ + 1.5), color: 0xff2010, i: 10, dist: 12 }];
      S.focus = 3.0; S.dofScale = 0.5; S.shake = 0.12; S.ca = 0.006; S.shadowC = A(0, ab.GY, -63); });
  // ---------------------------------------------------------------- E07 : Lina lui prend la main ; derrière eux, l'escalier tombe bloc après bloc
  const NS = ab.stairs.length;
  add('E07_main', T('E07'),
    (lt) => ({ pos: A(0.25, ab.GY + 2.05, -61.55), look: A(0, ab.GY + 2.5, -63.45), fov: 48, roll: 0 }),
    (lt, u, t, S) => { E.lookGate(S, t); ab.setRunes(1, 1, t); ab.setDoorGlow(0.6); put(noe, A(-0.4, ab.GY + 1.65, -63.45), 0, 'scared', t); put(lina, A(0.4, ab.GY + 1.65, -63.45), 0, 'scared', t);
      const k = ease((lt - 0.4) / 1.0); noe.shL.rotation.set(-0.3 * k, 0, 0.25 * k); lina.shR.rotation.set(-0.3 * k, 0, -0.25 * k); noe.setHands('relaxed', 'grip'); lina.setHands('grip', 'relaxed'); S.lights = [holdLantern(t, 1), { pos: ab.w(0, 33, -64), color: 0xff2010, i: 8, dist: 30 }];
      S.focus = 1.9; S.dofScale = 0.5; S.shadowC = A(0, ab.GY, -63); });
  add('E07_effondre', T('E07', 2.2),
    (lt) => ({ pos: A(2.2, ab.GY + 4.5, -66), look: A(-1.5, ab.GY - 4, -40), fov: 62, roll: 0 }),
    (lt, u, t, S) => { E.lookGate(S, t); ab.setRunes(1, 1, t); ab.setDoorGlow(0.6); ab.setStairs(t, 1.5, NS - 1, lt * 1.6); put(noe, A(-0.4, ab.GY + 1.65, -63.45), 0, 'scared', t); put(lina, A(0.4, ab.GY + 1.65, -63.45), 0, 'scream', t); S.lights = [holdLantern(t, 1), { pos: ab.w(0, 33, -64), color: 0xff2010, i: 8, dist: 30 }];
      S.focus = 12; S.dofScale = 0.2; S.shake = 0.25; S.shadowC = A(0, ab.GY, -60); });
  // ---------------------------------------------------------------- E08 : la porte ou le vide ? (vote)
  add('E08_choix', T('E08'),
    (lt) => { const k = ease(lt / 12); return { pos: A(lerp(2.4, 7.5, k), ab.GY + lerp(3.5, 9, k), lerp(-55.5, -46, k)), look: A(0, ab.GY + lerp(3, 5.5, k), -63.5), fov: 58, roll: 0 }; },
    (lt, u, t, S) => { E.lookGate(S, t); ab.setRunes(1, 1.2, t); ab.setDoorGlow(0.7 + 0.3 * Math.sin(t * 2)); ab.setStairs(t, 1.5, NS - 1, 30); put(noe, A(-0.4, ab.GY + 1.65, -63.45), 0.4, 'determined', t); put(lina, A(0.4, ab.GY + 1.65, -63.45), -0.3, 'scared', t);
      noe.shL.rotation.set(-0.3, 0, 0.25); lina.shR.rotation.set(-0.3, 0, -0.25); S.lights = [holdLantern(t, 1), { pos: ab.w(0, 33, -64), color: 0xff2010, i: 8, dist: 30 }]; placePerch(t, 6);
      S.focus = 10; S.dofScale = 0.2; S.shadowC = A(0, ab.GY, -62); S.fade = 1 - ease((lt - 12.4) / 0.8); });
  return shots;
}
