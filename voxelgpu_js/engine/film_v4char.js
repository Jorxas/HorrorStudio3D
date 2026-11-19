// Essai v4 : planche personnages (lumière neutre) pour vérifier visages, cheveux, vêtements.
import { CAST } from './film_v4test.js';
import { buildGraspHand } from './sets4.js';
export async function setup(ctx) {
  const { V, THREE, buildCharacter4, anim } = ctx;
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(40, 40), new THREE.MeshLambertMaterial({ color: 0x3a3a40 })); floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; ctx.scene.add(floor);
  const noe = buildCharacter4(CAST.noe, 1); noe.baseScale = 1; ctx.scene.add(noe.root);
  const lina = buildCharacter4(CAST.lina, 2); lina.baseScale = 1; ctx.scene.add(lina.root);
  const hands = [0, 1, 2].map((i) => { const h = buildGraspHand(1.2, i + 5); h.g.position.set(-0.45 + i * 0.45, 0.25, 1.0); h.g.rotation.set(-0.15, 0.3 * (i - 1), 0); h.set([0.15, 0.45, 0.9][i], 0.28); ctx.scene.add(h.g); return h; });
  const view = (yaw, expr) => (lt, u, t, S) => {
    anim.put(noe, -0.75, 0, yaw, () => 0); anim.put(lina, 0.75, 0, yaw, () => 0);
    noe.setExpr(expr); lina.setExpr(expr);
    S.sets = []; S.bg = 0x22242a; S.fog = { color: 0x22242a, d: 0.0 };
    S.hemi = { sky: 0xffffff, ground: 0x404040, i: 0.9 }; S.key = { dir: [0.5, 0.9, 0.8], color: 0xfff4ea, i: 1.6 }; S.fill = { dir: [-0.8, 0.3, 0.5], color: 0xbcd0ff, i: 0.4 };
    S.rim = { color: 0xff2a1a, i: 0.6, pow: 2.4 }; S.dofScale = 0; S.bloom = 0.3; S.mblur = 0; S.shadowC.set(0, 0, 0); S.shadowS = 4; S.grain = 0.01; S.vignette = 0.2;
  };
  const cam = (lt, u) => ({ pos: V(0, 1.2, 4.6), look: V(0, 1.0, 0), fov: 52, roll: 0 });
  const camF = (lt, u) => ({ pos: V(-0.75, 1.55, 1.9), look: V(-0.75, 1.5, 0), fov: 40, roll: 0 });
  const camL = (lt, u) => ({ pos: V(0.75, 1.55, 1.9), look: V(0.75, 1.5, 0), fov: 40, roll: 0 });
  const shots = [
    { name: 'front', t0: 0, t1: 1, cam, fn: view(0, 'neutral') },
    { name: 'three4', t0: 1, t1: 2, cam, fn: view(0.6, 'scared') },
    { name: 'back', t0: 2, t1: 3, cam, fn: view(Math.PI, 'neutral') },
    { name: 'faceN', t0: 3, t1: 4, cam: camF, fn: view(0.25, 'scream') },
    { name: 'faceL', t0: 4, t1: 5, cam: camL, fn: view(-0.25, 'worried') },
    { name: 'hands', t0: 5, t1: 6, cam: () => ({ pos: V(0, 0.75, 3.3), look: V(0, 0.65, 1.0), fov: 40, roll: 0 }), fn: view(0, 'neutral') },
  ];
  return { shots, duration: 6, sets: {}, reset: () => { noe.reset(); lina.reset(); } };
}
