// Essai décors forêt + abîme + porte.
import { buildForest } from './sets4c.js';
import { buildAbyss } from './sets4d.js';
import { CAST } from './film_v4test.js';
export async function setup(ctx) {
  const { V, buildCharacter4, anim, THREE } = ctx;
  const fo = buildForest(ctx, V(400, 0, 0)); const ab = buildAbyss(ctx, V(600, 0, 0));
  const lina = buildCharacter4(CAST.lina, 2); ctx.scene.add(lina.root);
  const shots = [
    { name: 'forest', t0: 0, t1: 5, cam: () => ({ pos: fo.at(4, 0.4, 0.35), look: fo.at(-14, 0, 4.2), fov: 62, roll: 0 }),
      fn: (lt, u, t, S) => { S.sets = ['fo']; const p = fo.at(-1.5, 0.3); anim.put(lina, p.x, p.z, 0.2, () => p.y); lina.setExpr('scared');
        S.key = { dir: [-0.35, 0.75, -0.55], color: 0x9ab8ff, i: 1.5 }; S.hemi = { sky: 0x4a5a9a, ground: 0x1a1a2a, i: 0.6 }; S.fill = { dir: [0.2, 0.4, 1], color: 0x6a80d0, i: 0.5 };
        S.lights = [{ pos: fo.at(-40, 1.5, 1), color: 0xff2010, i: 4, dist: 14, decay: 1.3 }]; S.fog = { color: 0x141a34, d: 0.025 }; S.bg = 0x0a0c1a; S.moonDir = [0.35, 0.6, -1];
        S.snow = { i: 1.4, col: 0xe8f0ff, size: 1, speed: 1 }; S.spark = { i: 9, col: 0xcfe0ff, den: 0.07, size: 0.03 }; S.rim = { color: 0xff3020, i: 0.3, pow: 5 };
        S.edge = { color: 0xff3a26, i: 1.1, rad: 2.0, thr: 0.1, maxD: 14, wrap: 2.2 }; S.focus = 5.5; S.dofScale = 0.35; S.shadowC = fo.at(-2); S.shadowS = 14; S.contrast = 0.25; S.sat = 1.15;
        S.mist = { list: [0, 1, 2, 3].map((i) => ({ pos: fo.at(-30 - i * 6, (i - 1.5) * 3, 1.2), w: 26, h: 5, yaw: 0, k: 1 })), col: 0xff1a10, i: 0.9 }; } },
    { name: 'abyss', t0: 5, t1: 10, cam: () => ({ pos: ab.w(1.2, 2.1, 5.5), look: ab.w(0, 4, -40), fov: 62, roll: 0.03 }),
      fn: (lt, u, t, S) => { S.sets = ['ab']; const p = ab.w(0, 1.5, 2); anim.put(lina, p.x, p.z, Math.PI, () => p.y); lina.setExpr('determined');
        S.key = { dir: [0.3, 0.7, 0.6], color: 0xff8a5a, i: 0.7 }; S.hemi = { sky: 0x3a0806, ground: 0x8a2008, i: 0.45 }; S.fill = { dir: [0, -1, 0.35], color: 0xff6a20, i: 1.0 };
        S.lights = ab.lavaLights(ab.w(0, 0, -6)); S.fog = { color: 0x4a0806, d: 0.012 }; S.bg = 0x1a0402;
        S.embers = { i: 2.5, col: 0xff8a30, size: 1, speed: 1 }; S.spark = { i: 8, col: 0xff6a30, den: 0.05, size: 0.03 }; S.rim = { color: 0xff5020, i: 0.35, pow: 5 };
        S.edge = { color: 0xff5a20, i: 1.1, rad: 2.0, thr: 0.1, maxD: 20, wrap: 2.2 }; S.focus = 6; S.dofScale = 0.3; S.shadowC = ab.w(0, 1.5, 0); S.shadowS = 12; S.contrast = 0.25; } },
    { name: 'gate', t0: 10, t1: 15, cam: () => ({ pos: ab.w(1.5, 31.2, -50), look: ab.w(0, 36, -67), fov: 62, roll: 0 }),
      fn: (lt, u, t, S) => { S.sets = ['ab']; const p = ab.w(0, 30, -57); anim.put(lina, p.x, p.z, Math.PI, () => p.y); ab.setStairs(t, 1); ab.setRunes(1, 1, t);
        S.key = { dir: [0.3, 0.5, 1], color: 0xff8060, i: 0.5 }; S.hemi = { sky: 0x4a0808, ground: 0x2a0404, i: 0.6 }; S.fill = { dir: [0, -1, 0.2], color: 0xff2a10, i: 0.5 };
        S.lights = [{ pos: ab.w(0, 33, -64), color: 0xff2010, i: 6, dist: 20 }]; S.fog = { color: 0x5a0606, d: 0.03 }; S.bg = 0x1a0202;
        S.embers = { i: 1.5, col: 0xff4a20, size: 0.8, speed: 0.6 }; S.spark = { i: 8, col: 0xff4a30, den: 0.05, size: 0.03 }; S.rim = { color: 0xff2414, i: 0.35, pow: 5 };
        S.edge = { color: 0xff3a26, i: 1.2, rad: 2.0, thr: 0.1, maxD: 25, wrap: 2.2 }; S.focus = 12; S.dofScale = 0.3; S.shadowC = ab.w(0, 30, -60); S.shadowS = 12; } },
  ];
  return { shots, duration: 15, sets: { fo, ab }, reset: () => { lina.reset(); } };
}
