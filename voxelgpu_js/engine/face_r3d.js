// Visages du PREMIER moteur (r3d, hstudio « La Dernière Pompe » : chars.py `face_tex`), portés ici pour le peintre VOXEL.
// Même grammaire : une grille de 24 x 24 pixels, yeux blancs à pupille carrée, sourcils en traits, bouche en rectangles ; ouverture de bouche par paliers (0..4).
// Activé par `look.r3d: true` sur un personnage (contrat) ; il remplace seulement le dessin du visage, le reste du personnage (corps, cheveux, vêtements) reste celui de VOXEL.
const WHITE = 'rgb(236,232,222)', DARK = 'rgb(18,14,18)', LIP = 'rgb(110,50,50)';
// noms d'expression du studio -> les 12 visages du premier moteur
export const R3MAP = {
  neutral: 'neutral', calm: 'neutral', tired: 'neutral', talk: 'neutral', closed: 'closed', sleeping: 'closed', blink: 'closed',
  worried: 'worried', nervous: 'worried', surprised: 'worried', uneasy: 'worried', hesitant: 'worried', confused: 'worried',
  scared: 'scared', scaredL: 'scared', scaredR: 'scared', shocked: 'scared', pain: 'scared', scream: 'scream', shout: 'shout', urgent: 'urgent',
  sad: 'sad', cry: 'sad', crying: 'sad', smile_sad: 'sad', determined: 'stern', grit: 'stern', angry: 'stern', furious: 'stern', suspicious: 'stern',
  smirk: 'smirk', smile: 'smirk', grin: 'grin', evil: 'grin', creature: 'blank', skull: 'blank', double: 'blank', whisper: 'whisper', stern: 'stern', blank: 'blank',
};

function line(R, x0, y0, x1, y1, col) {          // trait pixel par pixel (Bresenham), comme PIL ImageDraw.line
  let dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0), sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1, err = dx + dy;
  for (;;) { R(x0, y0, x0, y0, col); if (x0 === x1 && y0 === y1) break; const e2 = 2 * err; if (e2 >= dy) { err += dy; x0 += sx; } if (e2 <= dx) { err += dx; y0 += sy; } }
}

export function drawR3D(g, N, kind, mouth, skinHex) {
  const s = N / 24; g.imageSmoothingEnabled = false;
  g.fillStyle = skinHex; g.fillRect(0, 0, N, N);
  const R = (x0, y0, x1, y1, col) => { g.fillStyle = col; g.fillRect(x0 * s, y0 * s, (x1 - x0 + 1) * s, (y1 - y0 + 1) * s); };
  const ey = 11, my = 17;
  if (['neutral', 'urgent', 'whisper', 'shout', 'stern', 'blank'].includes(kind)) {
    for (const x of [6, 15]) {
      if (kind === 'blank') R(x, ey, x + 2, ey + 1, DARK);
      else { R(x, ey - 1, x + 2, ey + 2, WHITE); R(x + 1, ey, x + 1, ey + 1, DARK); }
    }
    if (['urgent', 'shout', 'stern'].includes(kind)) {
      line(R, 5, ey - 3, 9, ey - 2, DARK); line(R, 14, ey - 2, 18, ey - 3, DARK);
      if (kind === 'stern') { line(R, 5, ey - 2, 9, ey - 1, DARK); line(R, 14, ey - 1, 18, ey - 2, DARK); }
    }
  } else if (['worried', 'scared', 'scream', 'sad'].includes(kind)) {
    for (const x of [5, 15]) { R(x, ey - 1, x + 3, ey + 3, WHITE); R(x + 1, ey, x + 1 + (kind === 'scream' ? 0 : 1), ey + (kind === 'scream' ? 1 : 2), DARK); }
    line(R, 5, ey - 2, 8, ey - 4, DARK); line(R, 15, ey - 4, 18, ey - 2, DARK);
    if (kind === 'sad') { R(5, ey + 4, 5, ey + 6, 'rgb(120,170,230)'); R(18, ey + 4, 18, ey + 6, 'rgb(120,170,230)'); }
  } else if (kind === 'grin') { for (const x of [5, 15]) { R(x, ey - 2, x + 3, ey + 3, WHITE); R(x + 1, ey, x + 1, ey, DARK); } line(R, 5, ey - 4, 8, ey - 4, DARK); line(R, 15, ey - 4, 18, ey - 4, DARK);
  } else if (kind === 'closed') { for (const x of [5, 15]) R(x, ey + 1, x + 3, ey + 1, DARK); }
  else if (kind === 'smirk') { for (const x of [6, 15]) R(x, ey, x + 2, ey + 1, DARK); line(R, 5, ey - 2, 9, ey - 3, DARK); }
  const m = Math.round(mouth * 4);
  if (kind === 'grin') { R(3, my - 3, 3, my - 2, DARK); R(20, my - 3, 20, my - 2, DARK); R(4, my - 2, 19, my + 3, 'rgb(40,6,12)'); for (let x = 4; x <= 19; x += 2) { R(x, my - 2, x, my - 1, WHITE); R(x + 1, my + 2, x + 1, my + 3, WHITE); } return; }
  if (kind === 'scream') { R(8, my - 2, 15, my + 4, 'rgb(60,10,20)'); R(9, my - 2, 14, my - 2, WHITE); R(10, my + 2, 13, my + 3, 'rgb(170,60,70)'); }
  else if (kind === 'shout' || kind === 'urgent') { const h = 2 + Math.max(m, 1); R(8, my - 1, 15, my - 1 + h, 'rgb(80,24,34)'); R(9, my - 1, 14, my - 1, WHITE); }
  else if (m > 0) { const h = Math.max(1, m); R(9, my, 14, my + h, 'rgb(70,25,35)'); if (h > 1) R(10, my, 13, my, WHITE); }
  else if (kind === 'scared' || kind === 'worried') R(10, my, 13, my + 2, 'rgb(60,20,30)');
  else if (kind === 'smirk') { R(9, my + 1, 13, my + 1, LIP); R(14, my, 14, my, LIP); R(15, my - 1, 15, my - 1, LIP); }
  else if (kind === 'sad') { R(9, my + 1, 14, my + 1, LIP); R(8, my + 2, 8, my + 2, LIP); R(15, my + 2, 15, my + 2, LIP); }
  else if (kind === 'stern') R(8, my, 15, my, 'rgb(70,40,40)');
  else R(9, my, 14, my, LIP);
}
