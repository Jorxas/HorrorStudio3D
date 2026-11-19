// quick look-dev shots for the town engine
export async function setup(ctx) {
  const { V, buildHumanoid, crowd, creature, decals, town, interiors } = ctx;
  const heroes = {
    narrator: buildHumanoid({ skin: 0xe8b48f, hair: 0x5a3a22, hairStyle: 'short', eyes: 0x5a3a22, shirt: 0x6f7a4e, shirt2: 0x4a5236, shirtStyle: 'camo', pants: 0x2a2a2e, shoes: 0x3a2a1a }, 3),
    theo: buildHumanoid({ skin: 0x8d5a3a, hair: 0x1a1a1a, hairStyle: 'short', eyes: 0x3a2a1a, shirt: 0xd23a2e, shirtStyle: 'tee', sleeves: 'short', pants: 0x3a5a8c, headphones: 0x2f6fd0 }, 4),
    mayor: buildHumanoid({ skin: 0xe8b48f, hair: 0x6a3a1e, hairStyle: 'short', eyes: 0x3a2a1a, shirt: 0x1a1a1e, shirtStyle: 'suit', sash: 0xc0242a, tie: 0x8a1a1a, pants: 0x1a1a1e, tophat: true }, 5),
  };
  for (const h of Object.values(heroes)) ctx.scene.add(h.root);
  const put = (h, x, z, yaw) => { h.root.position.set(x, town.groundY(x, z), z); h.root.rotation.y = yaw; h.root.visible = true; };
  const shots = [];
  const add = (name, dur, fn) => { const t0 = shots.length ? shots[shots.length - 1].t1 : 0; shots.push({ name, t0, t1: t0 + dur, fn }); };
  add('aerial', 1, (lt, u, t, S) => { S.tod = 'noon'; S.cam.pos.set(30, 60, 120); S.cam.look.set(0, 0, 40); S.cam.fov = 60; S.focus = 80; S.dofScale = 0.3; S.shadowS = 90; S.shadowC.set(0, 0, 60);
    let i = 0; for (let z = -30; z < 200; z += 2.2) for (const x of [6.0, 7.0, -6.0, -7.0]) { if (i > 300) break; const p = crowd.people[i++]; Object.assign(p, { on: true, x, y: 0.16, z: z + (x > 0 ? 0 : 1.1), yaw: x > 0 ? 0 : Math.PI, amp: 0.6, phase: t * 8 + i }); } });
  add('street', 1, (lt, u, t, S) => { S.tod = 'morning'; S.cam.pos.set(3.5, 1.6, 60); S.cam.look.set(6.5, 1.2, 40); S.cam.fov = 62; S.focus = 6; S.dofScale = 1.2; S.shadowC.set(5, 0, 50); S.shadowS = 25;
    let i = 0; for (let k = 0; k < 14; k++) { const p = crowd.people[i++]; Object.assign(p, { on: true, x: 6.1 + (k % 2) * 0.8, y: 0.16, z: 56 - k * 2.2, yaw: Math.PI, amp: 0.7, phase: t * 9 + k * 1.3 }); }
    put(heroes.narrator, 6.5, 57, Math.PI); });
  add('bakery', 1, (lt, u, t, S) => { S.tod = 'noon'; S.cam.pos.set(2, 2.2, -12); S.cam.look.set(9, 2, -20); S.cam.fov = 58; S.focus = 9; S.dofScale = 0.8; S.shadowC.set(8, 0, -18); S.shadowS = 20; });
  add('plazaSunset', 1, (lt, u, t, S) => { S.tod = 'sunset'; S.cam.pos.set(3, 1.2, -60); S.cam.look.set(0, 2, -80); S.cam.fov = 60; S.focus = 8; S.dofScale = 0.6; S.shadowC.set(0, 0, -75); S.shadowS = 30; S.rays = 0.6;
    put(heroes.narrator, 0.5, -66, 0); heroes.narrator.lgL.rotation.x = heroes.narrator.lgR.rotation.x = -1.45; heroes.narrator.root.position.y -= 0.6; });
  add('plazaNight', 1, (lt, u, t, S) => { S.tod = 'night'; S.cam.pos.set(2, 1.0, -58); S.cam.look.set(0, 7, -72); S.cam.fov = 62; S.focus = 10; S.dofScale = 0.5; S.shadowC.set(0, 0, -70); S.shadowS = 30;
    put(heroes.narrator, 0.5, -66, 0); creature.root.visible = true; creature.root.position.set(0.5, 0, -70); creature.root.scale.setScalar(1.3); creature.torso.rotation.x = 0.3; creature.neck.rotation.z = 0.3; creature.shR.rotation.x = -0.6;
    decals[0].set(0.5, 0.03, -66, 2.2, 2.2, 0.95); });
  add('bus', 1, (lt, u, t, S) => { S.tod = 'interior'; S.interior = 'bus'; S.cam.pos.set(300, 1.5, 7.6); S.cam.look.set(300, 1.2, -4); S.cam.fov = 70; S.focus = 5; S.dofScale = 0.6;
    interiors.bus.seats.forEach((s, k) => { if (k % 3 !== 0) return; const p = crowd.people[k]; Object.assign(p, { on: true, x: s.x, y: s.y - 0.12, z: s.z + 0.05, yaw: Math.PI, legs: -1.45, amp: 0 }); }); });
  add('hall', 1, (lt, u, t, S) => { S.tod = 'interior'; S.interior = 'hall'; S.cam.pos.set(340, 1.6, -6); S.cam.look.set(340, 1.3, 4); S.cam.fov = 60; S.focus = 4; S.dofScale = 0.8;
    put(heroes.narrator, 340, -2.5, Math.PI); heroes.narrator.root.position.y = 0;
    let i = 0; for (const z of [0, 2.5, 4.5, 7]) for (const sx of [-1, 1]) { const p = crowd.people[i++]; Object.assign(p, { on: true, x: 340 + sx * 1.75, y: 0, z, yaw: -sx * Math.PI / 2 + Math.PI / 2 * 0, amp: 0 }); } });
  add('checker', 1, (lt, u, t, S) => { S.tod = 'morning'; S.cam.pos.set(0, 30, 120); S.cam.look.set(0, 0, 80); S.cam.fov = 55; S.focus = 40; S.dofScale = 0.3; S.shadowC.set(0, 0, 80); S.shadowS = 50;
    let i = 0; for (let z = 50; z < 115; z += 2.6) for (let x = -24; x <= 24; x += 2.6) { if (((Math.round(x / 2.6) + Math.round(z / 2.6)) & 1) || i >= 400) continue; const p = crowd.people[i++]; Object.assign(p, { on: true, x, y: town.groundY(x, z), z, yaw: Math.PI, amp: 0 }); } });
  return { shots, heroes, duration: shots[shots.length - 1].t1 };
}
