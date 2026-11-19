// Acte B — la station-service (~103 → ~173.6 s).
export function actB(E) {
  const { V, anim, st, noe, phone, shades, at, clamp, lerp, ease, easeOut, lerpV } = E;
  const shots = []; const add = (name, t0, cam, fn) => shots.push({ name, t0, cam, fn });
  const T = (id, d = -0.3) => at(id) + d;
  const W = (x, y, z) => st.w(x, y, z); const g0 = () => 0;
  const noeAt = (x, z, yaw, expr, t) => { anim.put(noe, W(x, 0, 0).x, W(0, 0, z).z, yaw, g0); noe.root.visible = true; noe.setShoe('R', false); anim.expr(noe, expr, t, 0.2); };
  const holdPhone = (t, vib = 0) => { E.holdPhone(noe, t, vib, { neck: 0.3 }); };
  const lift = () => { noe.handR.children.forEach((c) => { if (c !== phone.g) c.visible = false; }); noe.handL.visible = false; noe.neck.visible = false; };  // gros plans écran : mains masquées
  const ghost = shades[0];
  // ---------------------------------------------------------------- B01 : la boutique ouverte, éclairée, vide ; il entre
  add('B01_entree', T('B01'),
    (lt) => ({ pos: W(-1.65, 0.32, -5.0 + lt * 0.05), look: W(0.2, 1.15, 3.5), fov: 62, roll: 0.02 }),
    (lt, u, t, S) => { E.lookStation(S, t, {}); const k = ease(lt / 4.5); noeAt(0, lerp(4.8, 1.6, k), Math.PI, 'worried', t); if (k > 0 && k < 1) anim.walk(noe, lt * 6, 0.6); anim.lookAt(noe, W(-2, 1.5, -2), 0.6 * k); S.focus = 6.5; S.dofScale = 0.35; });
  // ---------------------------------------------------------------- B02 : canettes au sol, rayons à moitié vides (travelling bas)
  add('B02_canettes', T('B02'),
    (lt) => ({ pos: W(-1.55 + Math.sin(lt * 0.4) * 0.05, 0.16, -3.4 + lt * 0.12), look: W(-1.6, 1.05, 1.5), fov: 58, roll: -0.03 }),
    (lt, u, t, S) => { E.lookStation(S, t, {}); const k = clamp(lt / 7); noeAt(-1.6, lerp(1.4, -1.2, k), Math.PI, 'worried', t); anim.walk(noe, lt * 4.5, 0.4); anim.lookAt(noe, W(-2.6, 1.0, -1.5 + lt * 0.3), 0.7); S.focus = 3.4; S.dofScale = 0.6; });
  // ---------------------------------------------------------------- B03 : la caméra de surveillance tourne vers lui
  add('B03_camera', T('B03'),
    (lt) => ({ pos: W(-1.05, 2.3, -5.7), look: W(-1.6, 3.0, -6.6), fov: 46, roll: 0.05 }),
    (lt, u, t, S) => { E.lookStation(S, t, { flick: 0.4 }); st.cctv.set(lerp(0.9, 0.0, ease((lt - 1.2) / 3.5)), 0.32, t); noeAt(-1.4, 0.25, 1.35, 'worried', t); S.focus = 1.25; S.dofScale = 0.8; });
  // ---------------------------------------------------------------- B03b : l'écran de la caisse… quelqu'un derrière lui
  const monitorView = (S, ghostOn) => { S.preRender = (rend, scene, tt) => { if (ghostOn) { ghost.root.visible = true; } st.monitor.render(rend, scene, W(-1.6, 2.95, -6.6), W(-1.5, 0.6, 0.0), tt); ghost.root.visible = false; }; };
  const ghostPose = (t) => { anim.put(ghost, W(-1.6, 0, 0).x, W(0, 0, -0.9).z, 0.0, g0); ghost.root.visible = false; anim.breathe(ghost, t, 0.4); };
  add('B03b_ecran', T('B03b'),
    (lt) => ({ pos: W(-2.6, 1.85, 1.0), look: W(2.9, 2.0, 0.35), fov: 50, roll: 0.02 }),
    (lt, u, t, S) => { E.lookStation(S, t, {}); st.cctv.set(0, 0.32, t); noeAt(-1.4, 0.25, 1.35, 'worried', t); anim.lookAt(noe, W(3.0, 2.25, 0.35), 1); ghostPose(t); monitorView(S, true); S.focus = 5.1; S.dofScale = 0.5; });
  add('B03b_zoom', T('B03b', 4.4),
    (lt) => { const k = ease(lt / 4.5); return { pos: lerpV(W(1.7, 2.05, 0.55), W(2.55, 2.22, 0.5), k), look: W(3.0, 2.25, 0.35), fov: 46, roll: 0 }; },
    (lt, u, t, S) => { E.lookStation(S, t, { flick: 0.3, horror: 0.2 * ease((lt - 1.6) / 0.5) }); st.cctv.set(0, 0.32, t); noeAt(-1.4, 0.25, 1.35, 'worried', t); ghostPose(t); monitorView(S, lt > 1.6); S.focus = 0.9; S.dofScale = 0.4; S.shake = 0.08; });
  // ---------------------------------------------------------------- B03c : il se retourne — le rayon est vide
  add('B03c_retourne', T('B03c'),
    (lt) => ({ pos: W(-1.55, 1.45, -1.75), look: W(-1.4, 1.42, 0.25), fov: 46, roll: 0.03 }),
    (lt, u, t, S) => { E.lookStation(S, t, { horror: 0.25 }); const k = easeOut((lt - 0.2) / 0.45); noeAt(-1.4, 0.25, lerp(1.35, Math.PI, k), lt < 0.3 ? 'worried' : 'scream', t); S.focus = 1.3; S.dofScale = 0.8; S.mblur = 0.8; S.shake = 0.2; });
  add('B03c_vide', T('B03c', 1.9),
    (lt) => ({ pos: W(-1.45, 1.45, 0.45), look: W(-1.6, 1.0, -5.5), fov: 54, roll: -0.02 }),
    (lt, u, t, S) => { E.lookStation(S, t, { flick: 0.6, horror: 0.15 }); noeAt(-1.4, 0.25, Math.PI, 'scared', t); noe.root.visible = false; S.focus = 3.0; S.dofScale = 0.4; S.shake = 0.1; });
  // ---------------------------------------------------------------- B04 : la voiture dehors, phares rouges, personne au volant
  add('B04_voiture', T('B04'),
    (lt) => ({ pos: W(1.45 + lt * 0.04, 1.4, 1.45 + lt * 0.08), look: W(4.6, 0.9, 8.2), fov: 44, roll: 0 }),
    (lt, u, t, S) => { E.lookStation(S, t, {}); noeAt(0.85, 2.65, 0.45, 'worried', t); anim.lookAt(noe, W(4.6, 1.0, 8.2), 1); S.focus = 6.5; S.dofScale = 0.5; });
  // ---------------------------------------------------------------- B05 / B06 : le téléphone : une position, puis « Ne regarde pas les vitres. »
  add('B05_position', T('B05'),
    (lt, u, t) => { noeAt(1.2, 1.4, 2.8, 'worried', t); holdPhone(t, 0); lift(); noe.root.updateMatrixWorld(true); const p = phone.screen.getWorldPosition(V()); const n = V(0, 0, 1).applyQuaternion(phone.screen.getWorldQuaternion(new E.THREE.Quaternion())); return { pos: p.clone().addScaledVector(n, 0.42).add(V(0.02, 0.04, 0)), look: p.clone().add(V(0, 0.02, 0)), fov: 42, roll: 0.03 }; },
    (lt, u, t, S) => { E.lookStation(S, t, {}); noeAt(1.2, 1.4, 2.8, 'worried', t); holdPhone(t, lt < 1.2 ? 1 : 0); lift(); phone.show('map'); noe.root.updateMatrixWorld(true); S.focus = 0.42; S.dofScale = 0.5;
      S.lights.push({ pos: W(1.2, 1.25, 1.0), color: 0x9ab4ff, i: 0.7, dist: 1.4, decay: 2 }); });
  add('B06_vitres', T('B06'),
    (lt, u, t) => { noeAt(1.2, 1.4, 2.8, 'scared', t); holdPhone(t, 0); lift(); noe.root.updateMatrixWorld(true); const p = phone.screen.getWorldPosition(V()); const n = V(0, 0, 1).applyQuaternion(phone.screen.getWorldQuaternion(new E.THREE.Quaternion())); return { pos: p.clone().addScaledVector(n, 0.42 - lt * 0.01).add(V(0, 0.03, 0)), look: p.clone().add(V(0, 0.02, 0)), fov: 42, roll: 0 }; },
    (lt, u, t, S) => { E.lookStation(S, t, {}); noeAt(1.2, 1.4, 2.8, 'scared', t); holdPhone(t, 0); lift(); phone.show('chat2'); noe.root.updateMatrixWorld(true); S.focus = 0.42; S.dofScale = 0.5; });
  // ---------------------------------------------------------------- B07 : évidemment, j'ai regardé (pose de l'illustration)
  add('B07_regarde', T('B07'),
    (lt) => ({ pos: W(0.15, 0.4, 0.05), look: W(1.05, 1.25, 1.55), fov: 60, roll: -0.06 }),
    (lt, u, t, S) => { E.lookStation(S, t, {}); noeAt(1.2, 1.4, 2.8, 'scared', t); holdPhone(t, 0); phone.show('chat2'); noe.neck.rotation.x -= 0.3 + 0.25 * ease(lt / 1.6); noe.neck.rotation.y += 0.35 * ease(lt / 1.6);
      noe.lgL.rotation.set(-0.4, 0, 0.15); noe.lgR.rotation.set(0.3, 0, -0.18); noe.hips.position.y -= 0.05; noe.shL.rotation.set(-0.8, 0, -0.6); noe.setHands('open', 'grip'); S.focus = 1.6; S.dofScale = 0.6; });
  // ---------------------------------------------------------------- B08 : des dizaines de traces de mains, toutes de l'intérieur
  add('B08_traces', T('B08'),
    (lt) => ({ pos: W(-0.3 + lt * 0.03, 1.15, -1.6 + lt * 0.18), look: W(0.2, 1.55, 3.5), fov: 58, roll: 0 }),
    (lt, u, t, S) => { E.lookStation(S, t, { flick: 0.2 + 0.6 * ease((lt - 3) / 2), horror: 0.75 * ease((lt - 1.5) / 3.5) }); st.hpM.uniforms.uReveal.value = ease((lt - 0.4) / 4.2); noeAt(1.2, 1.4, 2.8, 'scream', t); holdPhone(t, 0); phone.show('chat2');
      S.focus = 4.9; S.dofScale = 0.35; S.shake = 0.06 + 0.1 * ease(lt / 5); });
  // ---------------------------------------------------------------- B09 : par la porte de derrière
  add('B09_sortie', T('B09'),
    (lt) => ({ pos: W(3.1 - lt * 0.05, 1.15, -6.3), look: W(2.0, 1.0, -1.5), fov: 58, roll: 0.04 }),
    (lt, u, t, S) => { E.lookStation(S, t, { flick: 0.7, horror: 0.8 }); st.hpM.uniforms.uReveal.value = 1; const k = clamp((lt - 0.2) / 2.6); const p = lerpV(V(1.9, 0, 0.8), V(3.45, 0, -6.4), ease(k));
      noeAt(p.x, p.z, Math.atan2(3.45 - 1.9, -6.4 - 0.8), 'scared', t); if (k < 1) anim.run(noe, lt * 10, 1); st.backDoor.rotation.y = 1.4 * easeOut((lt - 2.6) / 0.5);
      S.focus = lerp(6, 1.2, ease(k)); S.dofScale = 0.5; S.shake = 0.2; S.fade = 1 - ease((lt - 5.6) / 0.6); S.flash = 0.6 * ease((lt - 3.0) / 0.5) * (1 - ease((lt - 3.6) / 0.6)); });
  return shots;
}
