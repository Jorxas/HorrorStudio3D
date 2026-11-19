// Objets détaillés tenus en main (hstudio/voxelgpu/b_objets.py) : version VOXEL native des téléphones, combinés, tasses, verres, livres, papiers, clés,
// pied-de-biche, lampe torche, bougie, cadre, sac, valise. Le contrat donne, par personnage, la liste des objets qu'il tient dans le film
// (`casts[id].held.items` : boîtes + décalcomanies + lumières, repère de la paume) et, par plan, l'objet tenu à chaque image (`stage.held[id]`, -1 = rien).
// L'objet suit la paume de la main qui le tient (droite `handR` ou gauche `handL`) en gardant l'orientation du personnage, comme dans PIXEL 3D ;
// la main se referme dessus. Sans la clé `held` dans le contrat, rien n'est construit. Fonction pure du temps : aucun hasard, aucune horloge.
import * as THREE from 'three';
import { boxesGroup } from './b_chars.js';
import { PX } from './rig.js';

const hex = (v, d) => (typeof v === 'string' ? parseInt(v.replace('#', ''), 16) : (v ?? d));
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const wrap = (ch, name, fn) => { const f0 = ch[name]; ch[name] = (...a) => { const r = f0 ? f0(...a) : undefined; fn(...a); return r; }; };

export function attachHeld(ch, def) {
  const H = def.held; if (!H || !H.items || !H.items.length) return;
  const palm = { R: new THREE.Object3D(), L: new THREE.Object3D() };
  palm.R.position.set(0, -1.3 * PX, 0.6 * PX); ch.handR.add(palm.R);
  palm.L.position.set(0, -1.3 * PX, 0.6 * PX); ch.handL.add(palm.L);
  const groups = H.items.map((it) => {
    const g = new THREE.Group(); g.add(boxesGroup(it.boxes, it.decals, { rim: 0.4, var: 0.05 })); g.visible = false; ch.root.add(g);
    g.userData.side = it.side === 'L' ? 'L' : 'R';
    g.userData.lights = (it.lights || []).map((l) => { const o = new THREE.Object3D(); o.position.set(...l.at); g.add(o); return { obj: o, color: hex(l.color, 0xffffff), i: l.i, dist: l.dist }; });
    return g;
  });
  let cur = -1; const tmp = new THREE.Vector3();
  ch.heldTrack = (st, id, T, FPS) => {              // appelé par film_unified.js (perform) : quel objet à cette image
    const tr = st.held && st.held[id]; let k = -1;
    if (tr && tr.length) k = tr[clamp(Math.round((T - st.t0) * FPS), 0, tr.length - 1)];
    if (k >= groups.length) k = -1;
    if (k !== cur) { if (cur >= 0) groups[cur].visible = false; if (k >= 0) groups[k].visible = true; cur = k; }
    ch.heldLights = k >= 0 && groups[k].userData.lights.length ? groups[k].userData.lights : null;
  };
  ch.heldUpdate = () => {                            // la paume, une fois les bras posés
    if (cur < 0) return; const g = groups[cur];
    ch.root.updateMatrixWorld(true); palm[g.userData.side].getWorldPosition(tmp); g.position.copy(ch.root.worldToLocal(tmp));
  };
  wrap(ch, 'faceUpdate', () => { if (cur < 0) return; ch.heldUpdate(); ch.setHand(groups[cur].userData.side, 'grip'); });
}
