// Essai v4 : Noé dans le bus, mains qui sortent du liquide noir (comparaison avec l'illustration 1).
import { buildBus } from './sets4.js';
export const CAST = {
  noe: { skin: 0xf0a874, brow: 0x24140e, hair: { style: 'curly', color: 0x3a2418, color2: 0x523422 }, top: { type: 'hoodie', color: 0x4a474e }, pants: { color: 0x2c2c32, plaid: [0x55555c, 0x2c2c32, 0x7a7a82] }, shoes: { type: 'sneaker', color: 0x1a1a1e, sole: 0xf0f0ee } },
  lina: { skin: 0xf2b088, brow: 0x3a2014, lashes: true, hair: { style: 'long', color: 0x5a3420, color2: 0x70442a }, hat: { type: 'beanie', color: 0x8a1a24, fur: 0xf2eee8, snow: true }, top: { type: 'coat', color: 0x8a1a24, plaid: [0xa82434, 0x5e0e16, 0xe6d6ce], fur: 0xf2eee8 }, pants: { color: 0x2c2a30, plaid: [0x3a3840, 0x26242a, 0x4c4a52] }, shoes: { type: 'boot', color: 0x5a3a24, fur: 0xf2eee8 } },
};
export async function setup(ctx) {
  const { V, buildCharacter4, anim } = ctx;
  const bus = buildBus(ctx, V(0, 0, 0));
  const noe = buildCharacter4(CAST.noe, 1); noe.baseScale = 1.0; ctx.scene.add(noe.root);
  const lina = buildCharacter4(CAST.lina, 2); lina.baseScale = 0.9; ctx.scene.add(lina.root);
  const shots = [{
    name: 'test', t0: 0, t1: 10,
    cam: (lt, u) => ({ pos: V(-0.45, 0.48, 0.1), look: V(-0.05, 1.02, -2.75), fov: 60, roll: -0.05 }),
    fn: (lt, u, t, S) => {
      S.sets = ['bus']; bus.setTubes(1, t); bus.showPoles([0]);
      anim.put(noe, -0.3, -2.72, -0.08, () => 0.0);
      noe.hips.position.y -= 0.035; noe.torso.rotation.z = 0.1; noe.torso.rotation.x = 0.06;
      noe.lgL.rotation.set(-0.35, 0, 0.12); noe.lgR.rotation.set(0.32, 0, -0.22);
      noe.shL.rotation.set(-0.05, 0, 2.45); noe.shR.rotation.set(-0.45, 0, -1.05); noe.handL.rotation.set(0, -0.4, -0.75); noe.setHands('grip', 'open'); noe.setExpr('scream'); noe.neck.rotation.set(0.06, -0.12, -0.08);
      lina.root.visible = false;
      S.lights = bus.lights.map((l) => ({ ...l, i: 2.2, dist: 6, decay: 1.3 })); S.focus = 2.95; S.dofScale = 0.55; S.maxBlur = 12; S.shadowC.set(0, 0, -2.6); S.shadowS = 4;
      S.key = { dir: [-0.1, 0.45, 1.0], color: 0xffb08c, i: 1.7 }; S.hemi = { sky: 0x8a1c12, ground: 0x0a0202, i: 0.55 }; S.fill = { dir: [1, 0.3, -0.3], color: 0x5070ff, i: 0.18 };
      S.rim = { color: 0xff2414, i: 0.32, pow: 5 }; S.edge = { color: 0xff3a26, i: 1.3, rad: 2.0, thr: 0.1, maxD: 7, wrap: 2.0 }; S.dust = { i: 2.2, col: 0xff4a30, size: 1.0, box: V(3, 2.5, 7) }; S.spark = { i: 14, col: 0xff7a60, den: 0.07, size: 0.03 }; S.fog = { color: 0x7a1008, d: 0.05 }; S.bg = 0x0a0102;
      S.bloom = 0.6; S.bloomThreshold = 0.85; S.bloomRadius = 0.6; S.contrast = 0.3; S.vignette = 0.65; S.sat = 1.15;
      S.reflect = { y: 0.02 };
      const spots = [[-0.55, -0.55, 1.2, 0.25], [-0.35, -1.6, 1.15, 0.3], [0.05, -1.95, 1.1, 0.1], [-0.5, -2.6, 1.1, 0.35], [0.55, -2.1, 1.0, -0.3], [-0.2, -3.6, 1.05, 0.2], [0.45, -3.6, 1.0, 0], [-0.45, -4.6, 1, 0.3], [0.2, -5.4, 1, -0.2], [-0.1, -6.6, 1, 0.1], [0.45, -7.5, 1, 0], [0.6, -1.3, 1.2, -0.4]];
      bus.hands.forEach((h, i) => { const sp = window.NOHANDS ? null : spots[i]; if (!sp) { h.g.visible = false; return; } h.g.visible = true; h.g.scale.setScalar(sp[2]); h.g.position.set(sp[0], 0.12 + 0.08 * Math.sin(t * 1.3 + i), sp[1]); h.g.rotation.set(sp[3] * 0.6 - 0.15, Math.atan2(-0.45 - sp[0], 0.1 - sp[1]) + 0.3 * Math.sin(i * 2.1), -sp[0] * 0.4); h.set(0.15 + 0.25 * Math.sin(t * 2 + i), 0.28); });
    },
  }, {
    name: 'ext', t0: 10, t1: 20,
    cam: (lt, u) => ({ pos: V(6.5, 0.6, -15.5), look: V(0, 0.8, -8), fov: 55, roll: 0 }),
    fn: (lt, u, t, S) => {
      S.sets = ['bus']; bus.setTubes(0, t); bus.setDoor(0.8); bus.setWindows(0xfff0e0, 0.5); bus.showPoles([]);
      noe.root.visible = false; lina.root.visible = false; bus.hands.forEach((h) => { h.g.visible = false; });
      S.lights = bus.tubeLights(0, t, 2.2, 6); S.focus = 9; S.dofScale = 0.3;
      S.key = { dir: [0.5, 0.6, 0.4], color: 0x8aa0ff, i: 0.6 }; S.hemi = { sky: 0x30384a, ground: 0x050505, i: 0.5 }; S.fill = { dir: [-1, 0.3, -0.3], color: 0xff4020, i: 0.2 };
      S.rim = { color: 0xff2414, i: 0.3, pow: 5 }; S.edge = { color: 0xff3a26, i: 1.0, rad: 2.0, thr: 0.1, maxD: 20, wrap: 1.5 }; S.fog = { color: 0x0a0c14, d: 0.03 }; S.bg = 0x05060a;
      S.rain = { i: 1.2, col: 0xc8d0ff, size: 1, speed: 1 }; S.spark = { i: 8, col: 0xffa080, den: 0.06, size: 0.03 };
    },
  }];
  return { shots, duration: 20, sets: { bus }, reset: () => { noe.reset(); lina.reset(); noe.root.visible = true; } };
}
