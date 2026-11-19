// Essai décor station-service.
import { buildStation } from './sets4b.js';
import { CAST } from './film_v4test.js';
export async function setup(ctx) {
  const { V, buildCharacter4, anim } = ctx;
  const st = buildStation(ctx, V(200, 0, 0)); const O = st.origin;
  const noe = buildCharacter4(CAST.noe, 1); ctx.scene.add(noe.root);
  const look = (S, t, out) => {
    S.sets = ['st']; st.setPanels(0.15, t, 0.3);
    S.lights = [...st.panelLights(0.15, 1.4, 7), ...st.car.lights(1)]; if (out) S.lights.push(...st.lampLights(4));
    S.key = { dir: [-0.3, 0.8, 0.6], color: 0xffd8c8, i: 0.5 }; S.hemi = { sky: 0x6a2a28, ground: 0x0a0202, i: 0.45 }; S.fill = { dir: [0.3, 0.3, 1], color: 0xff2a1a, i: 0.5 };
    S.rim = { color: 0xff2414, i: 0.3, pow: 5 }; S.edge = { color: 0xff3a26, i: 1.2, rad: 2.0, thr: 0.1, maxD: 12, wrap: 2.0 }; S.fog = { color: 0x3a0606, d: 0.03 }; S.bg = 0x0a0204;
    S.rain = { i: 1.4, col: 0xffb0a0, size: 1, speed: 1, clip: new ctx.THREE.Vector4(-1e9, O.z + 3.7, 1e9, 1e9) }; S.spark = { i: 10, col: 0xff8a70, den: 0.05, size: 0.025 };
    S.reflect = { y: 0.02 }; S.dofScale = 0.4; S.bloom = 0.7; S.bloomThreshold = 0.8; S.contrast = 0.28; S.vignette = 0.6; S.sat = 1.15;
  };
  const shots = [
    { name: 'in', t0: 0, t1: 5, cam: () => ({ pos: O.clone().add(V(-1.6, 0.35, -5.2)), look: O.clone().add(V(0.6, 1.2, 3.5)), fov: 62, roll: 0.02 }),
      fn: (lt, u, t, S) => { look(S, t, false); S.focus = 6; anim.put(noe, O.x - 0.2, O.z + 1.6, Math.PI + 0.3, () => 0); noe.setExpr('worried'); } },
    { name: 'out', t0: 5, t1: 10, cam: () => ({ pos: O.clone().add(V(3, 1.2, 16)), look: O.clone().add(V(0, 1.8, 0)), fov: 60, roll: 0 }),
      fn: (lt, u, t, S) => { look(S, t, true); S.focus = 14; anim.put(noe, O.x - 0.2, O.z + 6, Math.PI, () => 0); } },
    { name: 'mon', t0: 10, t1: 15, cam: () => ({ pos: O.clone().add(V(1.6, 1.7, 0.5)), look: O.clone().add(V(3.0, 2.25, 0.35)), fov: 50, roll: 0 }),
      fn: (lt, u, t, S) => { look(S, t, false); S.focus = 1.4; anim.put(noe, O.x - 0.2, O.z - 2.5, Math.PI, () => 0); st.cctv.set(0.6, 0.5, t);
        S.preRender = (rend, scene, tt) => st.monitor.render(rend, scene, O.clone().add(V(-4.2, 2.95, -6.4)), O.clone().add(V(0, 0.8, -1.5)), tt); } },
  ];
  return { shots, duration: 15, sets: { st }, reset: () => { noe.reset(); } };
}
