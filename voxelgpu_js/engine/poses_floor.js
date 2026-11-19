// Poses au sol des scènes dirigées (31/10/2026) : à genoux (`kneel`) et assis par terre, jambes repliées sur le côté (`sit_floor`).
// La logique est celle de PS1 (acting/rig.py, mêmes clés) ; le contrat porte, plan par plan, une valeur 0..1 par image (`stage.poses[id]`) et rien
// quand la clé n'est jamais écrite : les autres films ne lisent pas ce module. Fonction pure de l'image : jambes et bassin sont posés à chaque image.
import { PX } from './rig.js';

const sm = (k) => { k = Math.min(1, Math.max(0, k)); return k * k * (3 - 2 * k); };

function kneelBoth(ch, k) {
  const e = sm(k);
  for (const [lg, kn, ft, toe] of [[ch.lgL, ch.knL, ch.ftL, ch.toeL], [ch.lgR, ch.knR, ch.ftR, ch.toeR]]) {
    lg.rotation.x *= 1 - e;                                         // cuisse droite
    if (kn) kn.rotation.x = kn.rotation.x * (1 - e) + 1.57 * e;     // tibia à plat derrière
    if (ft) ft.rotation.x = ft.rotation.x * (1 - e) + 1.57 * e;     // pied dans le prolongement : plante vers le haut, orteils vers l'arrière
    if (toe) toe.rotation.x *= 1 - e;
  }
  ch.hips.position.y = ch.hips.position.y * (1 - e) + 8.5 * PX * e; // genou au sol : cuisse (6,5 px) + demi-épaisseur du tibia
}

function sitFloor(ch, k) {
  const e = sm(k);
  for (const [lg, kn, ft, side] of [[ch.lgL, ch.knL, ch.ftL, 1], [ch.lgR, ch.knR, ch.ftR, -1]]) {
    lg.rotation.order = 'YXZ';
    lg.rotation.x = lg.rotation.x * (1 - e) - 1.45 * e;             // cuisses à l'horizontale devant
    lg.rotation.y = -0.8 * e + (side > 0 ? 0.12 : -0.05) * e;       // repliées vers le même côté
    if (kn) kn.rotation.x = kn.rotation.x * (1 - e) + 2.3 * e;      // genoux très pliés : les tibias reviennent sous les cuisses
    if (ft) ft.rotation.x = ft.rotation.x * (1 - e) + 0.4 * e;
  }
  ch.hips.position.y = ch.hips.position.y * (1 - e) + 2.6 * PX * e;
  ch.torso.rotation.x -= 0.06 * e; ch.torso.rotation.z += 0.1 * e;
}

export function floorPose(ch, P, j) {
  const at = (a) => (a && a.length ? a[Math.min(j, a.length - 1)] : 0);
  const kn = at(P.kneel), sf = at(P.sit_floor);
  if (!(sf > 0.01)) for (const lg of [ch.lgL, ch.lgR]) if (lg.rotation.order !== 'XYZ') { lg.rotation.order = 'XYZ'; lg.rotation.y = 0; }
  if (kn > 0.01) kneelBoth(ch, kn);
  else if (sf > 0.01) sitFloor(ch, sf);
}
