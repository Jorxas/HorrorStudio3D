// node tools/anim_probe.mjs  < cases.json  >  results.json
// Runs the painter's REAL leg animation (voxelgpu_js/engine/anim.js: walk, run, sit, plant, footDrop) on a skeleton made of bare THREE groups (no DOM, no GPU)
// and prints, per case, where the ankles and the heel / toe points of both feet are in the character's frame. hstudio/voxelgpu/footkin.py is a Python port of the
// same maths; tools/check_facephysics.py compares the two so they cannot drift apart.
// cases: [{mode: 0|1|2, phase, amp, sit, seat_h}]  ->  [{L: {ankle:[x,y,z], heel:[y,z], toe:[y,z]}, R: {...}, hips: y}]
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');
const three = pathToFileURL(path.join(root, 'voxelgpu_js/vendor/three/build/three.module.js')).href;
let src = fs.readFileSync(path.join(root, 'voxelgpu_js/engine/anim.js'), 'utf8');
src = src.replace("import * as THREE from 'three';", `import * as THREE from '${three}';`).replace("import { PX } from './rig.js';", 'const PX = 1 / 16;');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'animprobe-'));
const file = path.join(tmp, 'anim_copy.mjs');
fs.writeFileSync(file, src);
const anim = await import(pathToFileURL(file).href);
const THREE = await import(three);
const PX = 1 / 16;

function skeleton() {
  const G = () => new THREE.Group();
  const root_ = G(), hips = G(), torso = G(), neck = G(); hips.position.y = 14 * PX; root_.add(hips); hips.add(torso); torso.add(neck);
  const mkArm = () => { const sh = G(), el = G(), hand = G(); sh.add(el); el.add(hand); torso.add(sh); return { sh, el, hand }; };
  const L = mkArm(), R = mkArm();
  const mkLeg = (x) => { const lg = G(), kn = G(), ft = G(), toe = G(); lg.position.set(x, 0, 0); kn.position.y = -6.5 * PX; ft.position.y = -5.5 * PX; hips.add(lg); lg.add(kn); kn.add(ft); ft.add(toe);
    const heel = G(); heel.position.set(0, -2 * PX, -2.3 * PX); const tip = G(); tip.position.set(0, -2 * PX, 1.9 * PX); ft.add(heel); ft.add(tip); return { lg, kn, ft, toe, heel, tip }; };
  const l = mkLeg(2 * PX), r = mkLeg(-2 * PX);
  const ch = { hipY: 14 * PX, root: root_, hips, torso, neck, shL: L.sh, shR: R.sh, elL: L.el, elR: R.el, handL: L.hand, handR: R.hand,
    lgL: l.lg, lgR: r.lg, knL: l.kn, knR: r.kn, ftL: l.ft, ftR: r.ft, toeL: l.toe, toeR: r.toe, LEN: { up: 4 * PX, fo: 6.4 * PX, th: 6.5 * PX, sh: 5.5 * PX, ft: 2 * PX },
    setHands() {}, setHand() {}, _parts: { l, r } };
  return ch;
}
const w = (o) => { o.updateWorldMatrix(true, false); return o.getWorldPosition(new THREE.Vector3()); };
const cases = JSON.parse(fs.readFileSync(0, 'utf8'));
const out = cases.map((c) => {
  const ch = skeleton(); ch.root.updateMatrixWorld(true);
  if (c.sit > 0.02) anim.sit(ch, c.sit, c.seat_h);
  else if (c.mode === 2) anim.run(ch, c.phase, c.amp);
  else if (c.mode === 1) anim.walk(ch, c.phase, c.amp);
  ch.root.updateMatrixWorld(true);
  const one = (p) => { const a = w(p.ft), h = w(p.heel), t = w(p.tip); return { ankle: [a.x, a.y, a.z], heel: [h.y, h.z], toe: [t.y, t.z] }; };
  return { L: one(ch._parts.l), R: one(ch._parts.r), hips: ch.hips.position.y };
});
process.stdout.write(JSON.stringify(out));
