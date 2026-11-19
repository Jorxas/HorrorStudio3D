// Visages v4.1 : visage paramétrique dessiné à la volée (512 px) sur la face avant de la tête cubique.
// Yeux avec paupières (ouverture, inclinaison, paupière basse), iris + pupille + reflets, sourcils pleins,
// nez discret, bouche à lèvres (largeur, ouverture, coins, dents du haut / du bas, langue), joues, rides de peur,
// sueur, larmes. Les expressions sont des jeux de paramètres : on passe de l'une à l'autre en douceur,
// avec clignements et petits mouvements d'yeux. Coordonnées de dessin 0..128.
import * as THREE from 'three';

const hexs = (h, a = 1) => `rgba(${(h >> 16) & 255},${(h >> 8) & 255},${h & 255},${a})`;
const shade = (h, f) => { const r = Math.min(255, ((h >> 16) & 255) * f) | 0, g = Math.min(255, ((h >> 8) & 255) * f) | 0, b = Math.min(255, (h & 255) * f) | 0; return (r << 16) | (g << 8) | b; };
const mixc = (a, b, k) => { const f = (s) => [(s >> 16) & 255, (s >> 8) & 255, s & 255]; const A = f(a), B = f(b); return ((A[0] + (B[0] - A[0]) * k) << 16) | ((A[1] + (B[1] - A[1]) * k) << 8) | (A[2] + (B[2] - A[2]) * k) | 0; };

export const EXPR4 = ['neutral', 'worried', 'scared', 'scream', 'grit', 'smile', 'sad', 'surprised', 'determined', 'blink', 'lookL', 'lookR', 'scaredL', 'scaredR', 'relief', 'cry', 'shout'];

// paramètres : eo = ouverture des yeux (0 fermé, 1 normal, 1.25 écarquillé) ; tilt = paupière côté nez (+ colère, − tristesse) ;
// low = paupière basse remontée (sourire, plissé) ; iris = taille ; lx, ly = regard ; bi/bo = hauteur sourcil côté nez / extérieur (− = plus haut) ; arch ;
// mw = largeur bouche ; mo = ouverture ; ms = coins (+ sourire, − tristesse) ; tt = dents du haut ; tb = dents du bas ; tg = langue ; mx = décalage ;
// blush, sweat, tear, wr = rides de peur, nl = plis du nez/joues (cri, effort)
// ajouts « expressions de PIXEL 3D » (tous à 0 par défaut : un visage qui ne les demande pas est dessiné exactement comme avant) :
//   teints : pale, green, red (rougeur), bone (crâne), plate (tôle de robot) ; yeux : arc (œil fermé heureux ^), xe (X, assommé), hrt (cœur), star (étincelle), spi (spirale),
//   hol (orbites creuses), alm (amande, extraterrestre), glowe + glowc (œil lumineux, 0 cyan -> 1 ambre), wink (clin d'œil droit) ; asy / asyb : bouche / sourcils asymétriques ;
//   squig (bouche qui tremble) ; zzz (sommeil) ; bags (cernes) ; nbr (pas de sourcils)
const BASE = { eo: 1, tilt: 0, low: 0, iris: 1, lx: 0, ly: 0, bi: 0, bo: 0, arch: 1, mw: 1, mo: 0, ms: 0.1, ua: 1.2, tt: 0, tb: 0, tg: 0, mx: 0, blush: 0.3, sweat: 0, tear: 0, wr: 0, nl: 0, grit: 0,
  pale: 0, green: 0, red: 0, bone: 0, plate: 0, arc: 0, xe: 0, hrt: 0, star: 0, spi: 0, hol: 0, alm: 0, glowe: 0, glowc: 0, wink: 0, asy: 0, asyb: 0, squig: 0, zzz: 0, bags: 0, nbr: 0,
  chin: 0, ul: 0, knit: 0, lidd: 0, dimp: 0, qph: 0 };   // V4 « naturel » : chin = menton qui se plisse (lèvre du bas poussée), ul = lèvre du haut relevée (dégoût, mépris), knit = plis entre les sourcils, lidd = paupière lourde, dimp = fossettes, qph = phase du tremblement
export const PRESETS = {
  neutral: {},
  lookL: { lx: -1 }, lookR: { lx: 1 },
  worried: { eo: 1.05, bi: -6, bo: 2.5, arch: 0.3, ua: 2, mw: 0.8, mo: 0.08, ms: -0.35, blush: 0.5, sweat: 1, wr: 0.6, iris: 0.92 },
  scared: { eo: 1.25, bi: -8, bo: 3, arch: 0.25, mw: 0.8, mo: 0.6, ms: -0.6, ua: 3.5, tt: 0.6, tb: 0.15, tg: 0.4, blush: 0.8, sweat: 2, wr: 1, iris: 0.8 },
  scaredL: { eo: 1.25, bi: -8, bo: 3, arch: 0.25, mw: 0.8, mo: 0.6, ms: -0.6, ua: 3.5, tt: 0.6, tb: 0.15, tg: 0.4, blush: 0.8, sweat: 2, wr: 1, iris: 0.8, lx: -1 },
  scaredR: { eo: 1.25, bi: -8, bo: 3, arch: 0.25, mw: 0.8, mo: 0.6, ms: -0.6, ua: 3.5, tt: 0.6, tb: 0.15, tg: 0.4, blush: 0.8, sweat: 2, wr: 1, iris: 0.8, lx: 1 },
  scream: { eo: 1.3, bi: -9, bo: 3, arch: 0.2, mw: 0.95, mo: 1.15, ms: -0.9, ua: 5, tt: 1, tb: 0.6, tg: 0.8, blush: 1, sweat: 2, wr: 1.2, nl: 0.8, iris: 0.72 },
  shout: { eo: 0.85, tilt: 0.7, bi: 5, bo: -2, arch: 0.4, mw: 1.1, mo: 0.95, ms: -0.5, ua: 3, tt: 1, tb: 0.7, tg: 0.6, blush: 0.6, sweat: 1, nl: 1, iris: 0.95 },
  grit: { eo: 0.8, tilt: 0.7, low: 0.25, bi: 6, bo: -2, arch: 0.3, mw: 1.05, mo: 0.32, ms: -0.15, tt: 1, tb: 1, grit: 1, blush: 0.6, sweat: 2, nl: 1, iris: 0.95 },
  determined: { eo: 0.85, tilt: 0.55, low: 0.15, bi: 4, bo: -1.5, arch: 0.4, mw: 0.85, mo: 0, ms: -0.05, blush: 0.25 },
  smile: { eo: 0.8, low: 0.7, bi: -2, bo: -1, arch: 1.2, mw: 1.1, mo: 0.4, ms: 1, ua: 0.2, tt: 1, tg: 0.5, blush: 0.9, iris: 1.05 },
  relief: { eo: 0.75, low: 0.5, bi: -3, bo: 1, arch: 0.8, mw: 0.9, mo: 0.06, ms: 0.6, blush: 0.7 },
  sad: { eo: 0.85, tilt: -0.7, bi: -6, bo: 3, arch: 0.3, mw: 0.8, mo: 0, ms: -0.7, tear: 1, blush: 0.4, ly: 0.4 },
  cry: { eo: 0.8, tilt: -0.8, low: 0.3, bi: -7, bo: 3, arch: 0.3, mw: 1.0, mo: 0.45, ms: -0.9, ua: 3, tt: 0.4, tg: 0.3, tear: 2, blush: 1, nl: 0.5 },
  surprised: { eo: 1.35, bi: -9, bo: -6, arch: 1.4, mw: 0.6, mo: 0.6, ms: 0, ua: 2.5, tg: 0.2, iris: 0.75, wr: 0.8 },
  blink: { eo: 0 },
  // ---- les 43 expressions de PIXEL 3D (hstudio/director/validate.FACES) : chacune a son préréglage, aucune ne retombe sur « la plus proche » (director.EXPR_MAP)
  closed: { eo: 0 },
  talk: { mw: 0.9, ua: 1.6 },
  urgent: { eo: 1.15, bi: -4, bo: 1, arch: 0.6, mw: 1, mo: 0.5, ms: -0.2, ua: 2.5, tt: 0.5, sweat: 1, blush: 0.5 },
  happy: { eo: 0.85, low: 0.35, bi: -1.5, bo: -1, arch: 1.1, mw: 1.05, mo: 0.05, ms: 0.8, blush: 0.8, iris: 1.05 },
  grin: { eo: 0.8, low: 0.6, bi: -1.5, bo: -0.5, arch: 1.1, mw: 1.2, mo: 0.3, ms: 1, ua: 0.3, tt: 1, tb: 0.5, blush: 0.7 },
  joy: { arc: 1, eo: 0.5, bi: -3, bo: -3, arch: 1.4, mw: 1.15, mo: 0.45, ms: 1, ua: 0.3, tt: 1, tg: 0.4, blush: 1 },
  laugh: { arc: 1, eo: 0.5, bi: -3, bo: -3, arch: 1.4, mw: 1.2, mo: 0.9, ms: 1, ua: 0.3, tt: 1, tb: 0.5, tg: 0.8, blush: 1, nl: 0.6 },
  excited: { star: 1, eo: 1.3, bi: -6, bo: -4, arch: 1.3, mw: 1.05, mo: 0.55, ms: 0.9, ua: 0.4, tt: 1, tg: 0.3, blush: 1, iris: 1.1 },
  love: { hrt: 1, eo: 1, bi: -2, bo: -1, arch: 1.1, mw: 0.95, mo: 0.05, ms: 0.8, blush: 1.1 },
  wink: { wink: 1, eo: 0.9, low: 0.4, bi: -2, bo: -1, arch: 1.2, mw: 1.1, mo: 0.25, ms: 0.9, tt: 0.8, blush: 0.8 },
  silly: { eo: 0.95, bi: -2, bo: -4, arch: 1.2, mw: 1, mo: 0.5, ms: 0.7, tt: 0.6, tg: 1, blush: 0.9, asyb: 0.8 },
  smirk: { eo: 0.8, low: 0.2, tilt: 0.1, bi: -1, bo: 1.5, arch: 0.8, mw: 0.95, ms: 0.6, asy: 1, asyb: 0.6 },
  proud: { eo: 0.7, low: 0.3, bi: -2, bo: -1.5, arch: 1.1, mw: 0.95, ms: 0.5, ly: 0.3, blush: 0.4 },
  shy: { eo: 0.7, bi: -3, bo: 1, arch: 0.5, mw: 0.7, ms: 0.3, ly: 0.8, lx: -0.6, blush: 1.2 },
  calm: { eo: 0.75, low: 0.15, bi: -1, arch: 0.9, mw: 0.95, ms: 0.25, blush: 0.3 },
  shocked: { eo: 1.35, bi: -9, bo: -6, arch: 1.4, mw: 0.55, mo: 1, ms: 0, ua: 3, tg: 0.2, iris: 0.65, wr: 1, sweat: 1.5, pale: 0.7 },
  nervous: { eo: 1, bi: -3, bo: 2.5, arch: 0.4, mw: 0.85, mo: 0.05, ms: -0.2, squig: 1, sweat: 1.5, iris: 0.88, blush: 0.6, lx: -0.5 },
  crying: { eo: 0.05, tilt: -0.8, bi: -7, bo: 3, arch: 0.3, mw: 1, mo: 0.5, ms: -0.9, ua: 3, tt: 0.4, tear: 2, blush: 1, nl: 0.5 },
  angry: { eo: 0.8, tilt: 0.8, low: 0.2, bi: 6, bo: -2.5, arch: 0.2, mw: 1, ms: -0.7, blush: 0.5, red: 0.35 },
  furious: { eo: 0.85, tilt: 1, low: 0.2, bi: 8, bo: -3.5, arch: 0.2, mw: 1.2, mo: 0.55, ms: -1, ua: 3.5, tt: 1, tb: 1, nl: 1, red: 0.8, blush: 0.8, sweat: 1 },
  disgusted: { eo: 0.6, tilt: 0.5, low: 0.5, bi: 3, bo: -2, arch: 0.3, mw: 0.85, mo: 0.15, ms: -0.8, ua: 2, asy: 0.6, nl: 1, green: 0.35 },
  confused: { eo: 1, bi: -5, bo: 1, arch: 0.5, mw: 0.8, mo: 0.05, ms: -0.25, asyb: 1, lx: 0.6, ly: -0.3 },
  suspicious: { eo: 0.6, tilt: 0.5, low: 0.35, bi: 3, bo: -1, arch: 0.4, mw: 0.9, ms: -0.3, lx: 1 },
  thinking: { eo: 0.9, bi: -4, bo: 1, arch: 0.7, mw: 0.7, ms: -0.1, ly: -0.8, lx: 0.6, asyb: 0.5 },
  bored: { eo: 0.45, low: 0.2, tilt: 0.2, bi: 2, arch: 0.4, mw: 0.9, ms: -0.3, ly: 0.5, lx: 1, bags: 0.4 },
  tired: { eo: 0.4, low: 0.3, bi: -1, bo: 2.5, arch: 0.4, mw: 0.85, ms: -0.4, ly: 0.6, bags: 1, blush: 0.1 },
  sleeping: { eo: 0, bi: -1, bo: 1, arch: 0.8, mw: 0.6, mo: 0.25, ms: 0.1, zzz: 1 },
  evil: { eo: 0.62, tilt: 1, low: 0.25, bi: 7, bo: -4, arch: 0.2, mw: 1.25, mo: 0.22, ms: 1, ua: 1, tt: 1, tb: 0.4, asy: 0.5, red: 0.55 },
  cool: { eo: 0.65, low: 0.25, bo: -0.5, arch: 0.8, mw: 0.95, ms: 0.45, asy: 0.6, asyb: 0.3 },
  pain: { eo: 0.05, tilt: -0.5, bi: -5, bo: 3.5, arch: 0.3, mw: 1.05, mo: 0.55, ms: -0.9, ua: 2.5, tt: 1, tb: 0.6, sweat: 2, nl: 1 },
  dizzy: { spi: 1, eo: 1, bi: -3, arch: 0.6, mw: 0.9, mo: 0.35, ms: -0.2, squig: 1, blush: 0.6 },
  smile_sad: { eo: 0.8, tilt: -0.5, bi: -5, bo: 2, arch: 0.4, mw: 0.95, ms: 0.4, ly: 0.3, tear: 0.6, blush: 0.4 },
  ko: { xe: 1, bi: -3, bo: 1, arch: 0.6, mw: 0.9, mo: 0.45, ms: -0.5, tg: 0.7, pale: 0.5 },
  skull: { hol: 1, bone: 1, nbr: 1, mw: 1.2, mo: 0.3, ms: 0, tt: 1, tb: 1, blush: 0 },
  robot: { glowe: 1, glowc: 0, plate: 1, nbr: 1, mw: 1.1, blush: 0 },
  alien: { alm: 1, green: 0.9, nbr: 1, mw: 0.45, ms: -0.1, blush: 0 },
  creature: { glowe: 1, glowc: 1, pale: 0.8, nbr: 1, mw: 1.25, mo: 0.55, ms: -0.5, tt: 1, tb: 1, blush: 0 },
  double: { eo: 0.92, low: 0.1, mw: 1.05, ms: 0.3, pale: 0.2 },
  // ---- 6/11/2026 : les trois expressions « objets du récit » de PIXEL 3D (assets.py) qui n'avaient pas de préréglage VOXEL (elles retombaient sur le visage neutre)
  fixed_smile:     { eo: 0.4, iris: 1.1, bi: 0, bo: 0, arch: 0.4, mw: 1.5, mo: 0.12, ms: 1.3, tt: 1, tb: 0.8, blush: 0, nbr: 1 },                    // sourire large et figé, minuscules yeux noirs
  predator:        { glowe: 1, glowc: 0.85, nbr: 0, bi: 4, bo: -1, arch: 0.35, tilt: 0.5, low: 0.2, mw: 0.95, ms: -0.15, blush: 0 },                // yeux jaunes, sourcils bas
  predator_smile:  { glowe: 1, glowc: 0.85, nbr: 0, bi: 4, bo: -1, arch: 0.35, tilt: 0.5, low: 0.2, mw: 1.2, mo: 0.45, ms: 0.8, tt: 1, tb: 0.15, blush: 0 },   // idem, bouche ouverte, deux crocs
  // ---- V4 : expressions ajoutées (inspirées d'autres styles de visages stylisés, redessinées dans le nôtre ; les noms de PIXEL 3D restent valides)
  contempt:    { eo: 0.55, low: 0.25, tilt: 0.2, bi: 1.5, bo: -0.5, arch: 0.5, mw: 0.9, ms: -0.2, ul: 0.7, asy: 0.8, lidd: 0.3, nl: 0.3, lx: 0.3 },
  sarcastic:   { eo: 0.7, low: 0.15, tilt: 0.15, bi: -3, bo: 1, arch: 1, mw: 0.95, ms: 0.4, asy: 0.9, asyb: 1, lx: 0.5 },
  mocking:     { eo: 0.85, low: 0.3, bi: -2, bo: -1, arch: 1.1, mw: 1.1, mo: 0.3, ms: 0.9, tt: 1, tg: 0.5, asy: 0.5, asyb: 0.6, blush: 0.6, lx: 0.3, dimp: 1 },
  hesitant:    { eo: 1, bi: -5, bo: 2, arch: 0.6, mw: 0.75, ms: -0.15, ly: 0.3, lx: -0.7, squig: 0.4, sweat: 0.5, knit: 0.2 },
  uneasy:      { eo: 0.95, bi: -4, bo: 2, arch: 0.4, mw: 0.8, ms: -0.35, squig: 0.5, lx: -0.6, ly: 0.2, sweat: 1, pale: 0.25, bags: 0.2 },
  adoring:     { eo: 1.05, low: 0.3, bi: -3, bo: -2, arch: 1.2, mw: 0.95, ms: 0.8, blush: 1.1, iris: 1.12, ly: -0.1, dimp: 0.6 },
  dreamy:      { eo: 0.65, low: 0.3, lidd: 0.3, bi: -2, bo: 0.5, arch: 0.9, mw: 0.85, ms: 0.5, ly: -0.5, lx: 0.4, blush: 0.6 },
  jealous:     { eo: 0.7, tilt: 0.5, low: 0.2, bi: 2, bo: 0, arch: 0.4, mw: 0.85, ms: -0.5, ul: 0.3, lx: 1, asy: 0.3, green: 0.15, knit: 0.4 },
  exhausted:   { eo: 0.3, low: 0.4, lidd: 0.7, bi: -1, bo: 3, arch: 0.3, mw: 0.9, mo: 0.12, ms: -0.5, ly: 0.7, bags: 1.2, pale: 0.2, blush: 0 },
  drunk:       { eo: 0.55, lidd: 0.6, low: 0.2, bi: -2, bo: 1, arch: 0.6, mw: 1.1, mo: 0.15, ms: 0.6, asy: 1, asyb: 0.7, lx: 0.5, ly: 0.3, blush: 1.4, red: 0.3, squig: 0.3 },
  shivering:   { eo: 0.8, bi: -4, bo: 1.5, arch: 0.5, mw: 0.8, mo: 0.12, ms: -0.3, tt: 0.5, tb: 0.5, grit: 0.4, squig: 1.2, pale: 0.35, blush: 0 },
  lip_tremble: { eo: 0.65, tilt: -0.6, low: 0.3, bi: -6, bo: 2.5, arch: 0.3, mw: 0.8, mo: 0, ms: -0.8, chin: 1, squig: 1.3, tear: 0.7, blush: 0.7, knit: 0.3 },
  half_smile:  { eo: 0.8, low: 0.3, bi: -1, bo: 0, mw: 0.95, ms: 0.5, asy: 0.7, blush: 0.5, dimp: 0.5 },
  grimace:     { eo: 0.6, tilt: 0.3, low: 0.4, bi: 2, bo: -1, arch: 0.3, mw: 1.15, mo: 0.12, ms: -0.4, tt: 1, tb: 1, grit: 0.6, nl: 0.8, sweat: 1, knit: 0.4 },
  sobbing:     { eo: 0.3, tilt: -0.8, low: 0.5, bi: -7, bo: 3, arch: 0.3, mw: 1, mo: 0.28, ms: -1, ua: 2.5, tt: 0.2, tear: 2, blush: 1, nl: 0.5, chin: 0.8, squig: 0.5, knit: 0.5 },
  yawn:        { eo: 0.25, low: 0.3, bi: -3, bo: -1, arch: 1.2, mw: 0.8, mo: 1, ms: -0.2, ua: 2, tt: 0.3, tg: 0.6, tear: 0.3, bags: 0.4 },
  pout:        { eo: 0.85, bi: -1, bo: 1, arch: 0.8, mw: 0.6, ms: -0.5, chin: 1, ly: 0.3, blush: 0.8 },
  smug:        { eo: 0.6, low: 0.25, lidd: 0.2, bi: -1, bo: -1, arch: 0.9, mw: 1, ms: 0.7, asy: 0.6, ly: 0.2, lx: 0.3, blush: 0.3, dimp: 0.6 },
  bitter:      { eo: 0.7, tilt: 0.3, low: 0.3, bi: 2, bo: 0, mw: 0.9, ms: -0.8, chin: 0.6, ul: 0.2, lidd: 0.2 },
  gloomy:      { eo: 0.55, tilt: -0.4, lidd: 0.4, low: 0.2, bi: -4, bo: 3, mw: 0.85, ms: -0.6, ly: 0.6, bags: 0.6, pale: 0.15, blush: 0.1, chin: 0.3 },
};
// « naturel » (par défaut) : une expression muette garde la bouche FERMÉE sauf cri, surprise, rire, peur marquée, bâillement ; colère = lèvres serrées ou dents serrées (fine bande), pleurs = menton qui se plisse et lèvre qui tremble.
// HSTUDIO_FACE_LEGACY=1 (contrat : face_style = 'legacy') redonne EXACTEMENT les visages d'avant, pour re-rendre un ancien film.
const NAT = {
  cry:       { eo: 0.5, tilt: -0.8, low: 0.45, mo: 0, mw: 0.85, ms: -1, tt: 0, tg: 0, chin: 1, squig: 0.7, tear: 2, nl: 0.4, knit: 0.4 },
  crying:    { eo: 0.05, mo: 0, mw: 0.85, ms: -1, tt: 0, chin: 1, squig: 0.7, tear: 2, nl: 0.4, knit: 0.4 },
  sad:       { chin: 0.45, knit: 0.2, lidd: 0.15 },
  angry:     { mo: 0, ms: -0.8, mw: 0.95, chin: 0.6, knit: 0.8, nl: 0.5, tilt: 0.9 },
  furious:   { eo: 0.8, tilt: 1, mw: 1.15, mo: 0.1, ms: -0.8, ua: 1.2, tt: 1, tb: 1, grit: 1, nl: 1, knit: 1, red: 0.8, sweat: 1 },
  pain:      { eo: 0.1, mw: 1.05, mo: 0.1, ms: -0.9, tt: 1, tb: 1, grit: 0.8, nl: 1, knit: 0.6, ua: 1.5 },
  disgusted: { mo: 0, ms: -0.6, ul: 1, nl: 1.2, knit: 0.4, asy: 0, ua: 1.2 },
  determined:{ chin: 0.3, knit: 0.5 },
  tired:     { lidd: 0.5 }, bored: { lidd: 0.4 },
  smile:     { dimp: 1 }, happy: { dimp: 0.8 }, grin: { dimp: 1 }, joy: { dimp: 1 }, laugh: { dimp: 1 }, relief: { dimp: 0.5 },
};
const legacy = () => !!globalThis.HS_FACE_LEGACY;
export const exprParams = (name) => { const b = { ...BASE, ...(PRESETS[name] || {}) }; if (!legacy()) Object.assign(b, NAT[name] || {}); return b; };

function rr(g, x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.lineTo(x + w - r, y); g.quadraticCurveTo(x + w, y, x + w, y + r); g.lineTo(x + w, y + h - r); g.quadraticCurveTo(x + w, y + h, x + w - r, y + h); g.lineTo(x + r, y + h); g.quadraticCurveTo(x, y + h, x, y + h - r); g.lineTo(x, y + r); g.quadraticCurveTo(x, y, x + r, y); g.closePath(); }
function drop(g, x, y, s) {
  g.beginPath(); g.moveTo(x, y - s * 1.1); g.bezierCurveTo(x + s * 0.2, y - s * 0.5, x + s * 0.75, y - s * 0.05, x + s * 0.7, y + s * 0.35); g.bezierCurveTo(x + s * 0.62, y + s * 0.85, x - s * 0.62, y + s * 0.85, x - s * 0.7, y + s * 0.35); g.bezierCurveTo(x - s * 0.75, y - s * 0.05, x - s * 0.2, y - s * 0.5, x, y - s * 1.1); g.closePath();
  const gr = g.createLinearGradient(x, y - s, x, y + s); gr.addColorStop(0, 'rgba(230,246,255,0.75)'); gr.addColorStop(1, 'rgba(150,200,240,0.6)'); g.fillStyle = gr; g.fill(); g.lineWidth = 0.7; g.strokeStyle = 'rgba(90,140,190,0.8)'; g.stroke();
  g.fillStyle = 'rgba(255,255,255,0.95)'; g.beginPath(); g.ellipse(x - s * 0.25, y + s * 0.15, s * 0.16, s * 0.26, -0.3, 0, 7); g.fill();
}

// dessine le visage complet dans le contexte g (déjà mis à l'échelle 0..128)
export function drawFace(g, spec, P) {
  const p = { ...BASE, ...P };
  let skin = spec.skin ?? 0xf0a874; const brow = spec.brow ?? 0x2a1610, line = 0x2a120e, lineS = hexs(line);
  if (p.pale > 0) skin = mixc(skin, 0xb9c4bb, 0.5 * Math.min(1, p.pale)); if (p.green > 0) skin = mixc(skin, 0x6faa68, 0.75 * Math.min(1, p.green));
  if (p.bone > 0) skin = mixc(skin, 0xe6dfc9, Math.min(1, p.bone)); if (p.plate > 0) skin = mixc(skin, 0x7d8a96, 0.85 * Math.min(1, p.plate));
  const skinD = shade(skin, 0.82), skinL = shade(skin, 1.07);
  const nat = !globalThis.HS_FACE_LEGACY;     // visage « naturel » (lèvres pleines, ombres d'orbites, plis) ; false = rendu d'avant à l'identique
  // --- peau : grille voxel discrète + ombre des cheveux + bords plus sombres (volume)
  g.fillStyle = hexs(skin); g.fillRect(0, 0, 128, 128);
  let sd = 7 + (spec.seed ?? 0) * 13; const rnd = () => { sd = (sd * 16807) % 2147483647; return sd / 2147483647; };
  for (let y = 0; y < 8; y++) for (let x = 0; x < 8; x++) { g.fillStyle = hexs(shade(skin, 0.975 + rnd() * 0.045)); g.fillRect(x * 16, y * 16, 16.1, 16.1); }
  let gr = g.createLinearGradient(0, 0, 0, 30); gr.addColorStop(0, 'rgba(60,20,10,0.4)'); gr.addColorStop(1, 'rgba(60,20,10,0)'); g.fillStyle = gr; g.fillRect(0, 0, 128, 30);
  gr = g.createLinearGradient(0, 108, 0, 128); gr.addColorStop(0, 'rgba(90,30,15,0)'); gr.addColorStop(1, 'rgba(90,30,15,0.22)'); g.fillStyle = gr; g.fillRect(0, 108, 128, 20);
  for (const sx of [0, 1]) { gr = g.createLinearGradient(sx ? 128 : 0, 0, sx ? 114 : 14, 0); gr.addColorStop(0, 'rgba(90,30,15,0.2)'); gr.addColorStop(1, 'rgba(90,30,15,0)'); g.fillStyle = gr; g.fillRect(sx ? 114 : 0, 0, 14, 128); }
  if (p.red > 0.02) { const rg = g.createRadialGradient(64, 64, 8, 64, 64, 76); rg.addColorStop(0, `rgba(225,45,32,${0.34 * Math.min(1, p.red)})`); rg.addColorStop(1, `rgba(225,45,32,${0.12 * Math.min(1, p.red)})`); g.fillStyle = rg; g.fillRect(0, 0, 128, 128); }   // colère : le visage s'empourpre
  if (p.plate > 0.5) { g.strokeStyle = 'rgba(40,50,60,0.55)'; g.lineWidth = 1; for (const x of [6, 122]) for (const y of [6, 122]) { g.beginPath(); g.arc(x, y, 2.2, 0, 7); g.stroke(); } g.beginPath(); g.moveTo(0, 36); g.lineTo(128, 36); g.moveTo(0, 82); g.lineTo(128, 82); g.stroke(); }   // robot : rivets et joints de tôle
  // --- joues (rougeur douce + petits traits quand c'est fort)
  for (const cx of [27, 101]) {
    const rg = g.createRadialGradient(cx, 84, 1, cx, 84, 14); rg.addColorStop(0, `rgba(232,88,78,${0.26 * p.blush})`); rg.addColorStop(1, 'rgba(232,88,78,0)'); g.fillStyle = rg; g.fillRect(cx - 15, 69, 30, 30);
    if (p.blush > 0.65) { g.strokeStyle = `rgba(196,60,52,${0.7 * (p.blush - 0.5) * 2})`; g.lineWidth = 1.2; g.lineCap = 'round'; for (let i = 0; i < 3; i++) { g.beginPath(); g.moveTo(cx - 5 + i * 4, 87); g.lineTo(cx - 2.8 + i * 4, 81.5); g.stroke(); } }
  }
  // --- rides de peur (front) et plis du nez / joues (cri, effort)
  if (p.wr > 0.05) { g.strokeStyle = hexs(skinD, 0.5 * Math.min(1, p.wr)); g.lineWidth = 1.1; g.lineCap = 'round'; for (const y of [20, 25]) { g.beginPath(); g.moveTo(52, y + 1.5); g.quadraticCurveTo(64, y - 2.5, 76, y + 1.5); g.stroke(); } }
  if (p.nl > 0.05) { g.strokeStyle = hexs(skinD, 0.6 * Math.min(1, p.nl)); g.lineWidth = 1.3; for (const sx of [-1, 1]) { g.beginPath(); g.moveTo(64 + sx * 9, 79); g.quadraticCurveTo(64 + sx * 16, 86, 64 + sx * 17 * p.mw, 95); g.stroke(); } }
  if (nat) {   // volumes peints : orbites, pommettes, front, menton (le visage perd son aspect d'aplat)
    for (const cx of [39, 89]) {
      let rg = g.createRadialGradient(cx, 62, 3, cx, 62, 26); rg.addColorStop(0, 'rgba(90,40,30,0)'); rg.addColorStop(0.7, 'rgba(90,40,30,0.08)'); rg.addColorStop(1, 'rgba(90,40,30,0)'); g.fillStyle = rg; g.fillRect(cx - 28, 34, 56, 56);
      rg = g.createRadialGradient(cx, 82, 1, cx, 82, 13); rg.addColorStop(0, hexs(skinL, 0.3)); rg.addColorStop(1, hexs(skinL, 0)); g.fillStyle = rg; g.fillRect(cx - 14, 68, 28, 28);
    }
    let lg = g.createRadialGradient(64, 22, 2, 64, 22, 30); lg.addColorStop(0, hexs(skinL, 0.28)); lg.addColorStop(1, hexs(skinL, 0)); g.fillStyle = lg; g.fillRect(24, 4, 80, 40);
    lg = g.createRadialGradient(64, 116, 1, 64, 116, 16); lg.addColorStop(0, hexs(skinL, 0.12)); lg.addColorStop(1, hexs(skinL, 0)); g.fillStyle = lg; g.fillRect(40, 102, 48, 26);
    lg = g.createLinearGradient(0, 99, 0, 112); lg.addColorStop(0, hexs(skinD, 0.1)); lg.addColorStop(1, hexs(skinD, 0)); g.fillStyle = lg; g.fillRect(46, 99, 36, 13);   // creux sous la lèvre (léger : le relief fait le reste)
  }
  // --- nez : ombre douce sous le nez + narines + petit reflet
  gr = g.createRadialGradient(64, 82, 0.5, 64, 82, 7); gr.addColorStop(0, hexs(skinD, nat ? 0.22 : 0.55)); gr.addColorStop(1, hexs(skinD, 0)); g.fillStyle = gr; g.fillRect(56, 76, 16, 12);
  g.fillStyle = hexs(shade(skin, 0.62), 0.75); for (const sx of [-1, 1]) { g.beginPath(); g.ellipse(64 + sx * 2.6, 81.6, 1.3, 0.8, 0, 0, 7); g.fill(); }
  g.fillStyle = hexs(skinL, 0.6); g.fillRect(62.5, 74, 3, 3);
  if (p.bone > 0.5) { g.fillStyle = 'rgba(30,24,20,0.9)'; g.beginPath(); g.moveTo(64, 74); g.lineTo(58.5, 86); g.lineTo(69.5, 86); g.closePath(); g.fill(); }   // crâne : le nez est un trou
  // --- yeux
  const eyeY = 58 + (p.ly > 0 ? 0.5 : 0);
  const eye = (cx, side) => {    // side −1 : œil gauche de l'image (droit du personnage), +1 : œil droit
    if (p.xe > 0.5) { g.strokeStyle = lineS; g.lineWidth = 3.2; g.lineCap = 'round'; const s = 7; g.beginPath(); g.moveTo(cx - s, eyeY - s + 2); g.lineTo(cx + s, eyeY + s + 2); g.moveTo(cx + s, eyeY - s + 2); g.lineTo(cx - s, eyeY + s + 2); g.stroke(); return; }   // assommé : yeux en croix
    if (p.hrt > 0.5) { const s = 9.5, y = eyeY + 1; g.fillStyle = '#e8284a'; g.beginPath(); g.moveTo(cx, y + s * 0.8); g.bezierCurveTo(cx - s * 1.6, y - s * 0.1, cx - s * 0.7, y - s * 1.25, cx, y - s * 0.4); g.bezierCurveTo(cx + s * 0.7, y - s * 1.25, cx + s * 1.6, y - s * 0.1, cx, y + s * 0.8); g.fill(); g.lineWidth = 1.2; g.strokeStyle = '#7a0a22'; g.stroke(); g.fillStyle = 'rgba(255,255,255,0.85)'; g.beginPath(); g.ellipse(cx - s * 0.5, y - s * 0.5, s * 0.22, s * 0.15, -0.5, 0, 7); g.fill(); return; }   // amoureux : yeux en cœur
    if (p.spi > 0.5) { g.fillStyle = '#f6f2ee'; g.beginPath(); g.ellipse(cx, eyeY + 1, 14, 13, 0, 0, 7); g.fill(); g.lineWidth = 1; g.strokeStyle = lineS; g.stroke(); g.lineWidth = 1.9; g.strokeStyle = '#1a1014'; g.lineCap = 'round'; g.beginPath(); for (let k = 0; k <= 60; k++) { const a = k * 0.2 * side, r = 0.4 + k * 0.19; const x = cx + Math.cos(a) * r, y = eyeY + 1 + Math.sin(a) * r; if (!k) g.moveTo(x, y); else g.lineTo(x, y); } g.stroke(); return; }   // étourdi : spirale
    if (p.hol > 0.5) { g.fillStyle = '#0c0808'; g.beginPath(); g.ellipse(cx, eyeY + 1, 12.5, 14, 0, 0, 7); g.fill(); g.lineWidth = 1.6; g.strokeStyle = hexs(shade(skin, 0.7)); g.stroke(); g.fillStyle = 'rgba(255,255,255,0.08)'; g.beginPath(); g.ellipse(cx - 3, eyeY - 4, 3, 2, 0, 0, 7); g.fill(); return; }   // crâne : orbites creuses
    if (p.alm > 0.5) { g.save(); g.translate(cx, eyeY + 1); g.rotate(-side * 0.38); g.fillStyle = '#05070a'; g.beginPath(); g.ellipse(0, 0, 15.5, 8.6, 0, 0, 7); g.fill(); g.fillStyle = 'rgba(180,255,200,0.55)'; g.beginPath(); g.ellipse(-4, -2.6, 3.4, 1.5, 0, 0, 7); g.fill(); g.restore(); return; }   // extraterrestre : grands yeux en amande
    if (p.glowe > 0.5) {   // robot (cyan, visière) ou créature (ambre, fente) : œil lumineux sans pupille
      const warm = p.glowc > 0.5, c1 = warm ? '255,190,70' : '90,235,255';
      g.fillStyle = '#06080c'; if (warm) { g.beginPath(); g.ellipse(cx, eyeY + 1, 14, 12, 0, 0, 7); g.fill(); } else g.fillRect(cx - 14, eyeY - 6, 28, 15);
      const gl = g.createRadialGradient(cx, eyeY + 1, 1, cx, eyeY + 1, 15); gl.addColorStop(0, `rgba(${c1},1)`); gl.addColorStop(0.55, `rgba(${c1},0.55)`); gl.addColorStop(1, `rgba(${c1},0)`); g.fillStyle = gl; g.fillRect(cx - 17, eyeY - 14, 34, 30);
      g.fillStyle = `rgba(${c1},1)`; if (warm) { g.beginPath(); g.ellipse(cx, eyeY + 1, 9, 7.5, 0, 0, 7); g.fill(); g.fillStyle = '#1a0a04'; g.fillRect(cx - 1.2, eyeY - 6.5, 2.4, 15); } else { g.fillRect(cx - 10, eyeY - 2.5, 20, 7); g.fillStyle = 'rgba(255,255,255,0.9)'; g.fillRect(cx - 6, eyeY - 0.5, 12, 3); }
      return; }
    if (p.arc > 0.5) { g.strokeStyle = lineS; g.lineWidth = 3; g.lineCap = 'round'; g.beginPath(); g.moveTo(cx - 13, eyeY + 4); g.quadraticCurveTo(cx, eyeY - 9, cx + 13, eyeY + 4); g.stroke(); return; }   // rire, joie : œil fermé en arc ^
    const W = 30, H0 = 25 * Math.min(1.35, Math.max(0, p.eo)); const open = (p.wink > 0.5 && side > 0) ? 0 : Math.max(0, Math.min(1.35, p.eo));   // clin d'œil : l'œil droit de l'image
    const x0 = cx - W / 2, top = eyeY - 12.5 * Math.max(open, 0.9), bot = eyeY + 12.5;
    const inner = side < 0 ? x0 + W : x0;  // coin côté nez
    // paupière supérieure : ligne de x0 à x0+W, hauteur selon ouverture + inclinaison (côté nez plus bas si colère)
    const lidY = (x) => { const u = (x - x0) / W; const nearNose = side < 0 ? u : 1 - u; const tilt = p.tilt * 6 * (nearNose - 0.5); const arch = -3.2 * Math.sin(u * Math.PI); return bot - (25 * open) + tilt + arch * Math.min(1, open + 0.2) + (nat ? p.lidd * 5 * Math.min(1, open) : 0); };
    const lowY = (x) => { const u = (x - x0) / W; return bot - p.low * 8 * Math.sin(u * Math.PI) - 1.5 * Math.sin(u * Math.PI); };
    if (open < 0.08) {   // fermé : ligne de cils courbe
      g.strokeStyle = lineS; g.lineWidth = 2.6; g.lineCap = 'round'; g.beginPath(); g.moveTo(x0 + 1, eyeY + 4); g.quadraticCurveTo(cx, eyeY + 9, x0 + W - 1, eyeY + 4); g.stroke();
      if (spec.lashes) { g.lineWidth = 1.4; const ox = side < 0 ? x0 + 1 : x0 + W - 1; g.beginPath(); g.moveTo(ox, eyeY + 4); g.lineTo(ox + side * 3, eyeY + 2.5); g.stroke(); }
      return;
    }
    // blanc de l'œil (forme : entre paupière haute et basse)
    const shape = () => { g.beginPath(); g.moveTo(x0, lidY(x0)); for (let x = x0; x <= x0 + W + 0.01; x += W / 12) g.lineTo(x, lidY(x)); for (let x = x0 + W; x >= x0 - 0.01; x -= W / 12) g.lineTo(x, Math.max(lidY(x) + 0.5, lowY(x))); g.closePath(); };
    g.save(); shape(); g.fillStyle = '#f6f2ee'; g.fill(); g.clip();
    gr = g.createLinearGradient(0, top, 0, top + 12); gr.addColorStop(0, 'rgba(120,100,120,0.45)'); gr.addColorStop(1, 'rgba(120,100,120,0)'); g.fillStyle = gr; g.fillRect(x0, top - 2, W, 14);
    // iris + pupille + reflets
    const ir = 8.6 * p.iris; const ix = cx + p.lx * 6.5 - side * 1.6 + (p.mx || 0) * 0, iy = eyeY + 1.5 + p.ly * 4;
    const ig = g.createRadialGradient(ix, iy, 1, ix, iy, ir); const ic = spec.iris ?? 0x4a2a18; ig.addColorStop(0, hexs(shade(ic, 1.25))); ig.addColorStop(0.7, hexs(ic)); ig.addColorStop(1, hexs(shade(ic, 0.55)));
    g.fillStyle = ig; g.beginPath(); g.ellipse(ix, iy, ir, ir * 1.08, 0, 0, 7); g.fill(); g.lineWidth = 0.9; g.strokeStyle = hexs(shade(ic, 0.4)); g.stroke();
    g.fillStyle = '#0a0608'; g.beginPath(); g.ellipse(ix, iy + 0.3, ir * 0.48, ir * 0.52, 0, 0, 7); g.fill();
    g.fillStyle = 'rgba(255,255,255,0.97)'; g.beginPath(); g.ellipse(ix - ir * 0.38, iy - ir * 0.42, ir * 0.28, ir * 0.26, 0, 0, 7); g.fill();
    g.fillStyle = 'rgba(255,255,255,0.7)'; g.beginPath(); g.ellipse(ix + ir * 0.35, iy + ir * 0.38, ir * 0.12, ir * 0.12, 0, 0, 7); g.fill();
    // ombre portée de la paupière sur l'œil
    g.beginPath(); g.moveTo(x0 - 1, lidY(x0) - 1); for (let x = x0; x <= x0 + W + 0.01; x += W / 12) g.lineTo(x, lidY(x) + 2.6); g.lineTo(x0 + W + 1, top - 20); g.lineTo(x0 - 1, top - 20); g.closePath(); g.fillStyle = 'rgba(80,40,40,0.22)'; g.fill();
    g.restore();
    // trait de paupière supérieure (épais, se prolonge un peu au coin extérieur) + paupière basse fine
    g.strokeStyle = lineS; g.lineCap = 'round'; g.lineJoin = 'round'; g.lineWidth = 2.8;
    g.beginPath(); g.moveTo(x0 - 0.5, lidY(x0)); for (let x = x0; x <= x0 + W + 0.01; x += W / 12) g.lineTo(x, lidY(x)); g.stroke();
    const outer = side < 0 ? x0 : x0 + W; g.lineWidth = 2.2; g.beginPath(); g.moveTo(outer, lidY(outer)); g.lineTo(outer + side * 2.4, lidY(outer) - 1.6); g.stroke();
    if (spec.lashes) { g.lineWidth = 1.5; for (let k = 0; k < 3; k++) { const x = outer - side * k * 3.2; g.beginPath(); g.moveTo(x, lidY(x)); g.lineTo(x + side * (2.6 - k * 0.5), lidY(x) - 3.4 + k * 0.6); g.stroke(); } }
    g.lineWidth = 1.0; g.strokeStyle = hexs(line, 0.55); g.beginPath(); for (let x = x0 + 2; x <= x0 + W - 2 + 0.01; x += W / 12) { const y = Math.max(lidY(x) + 0.5, lowY(x)); if (x === x0 + 2) g.moveTo(x, y); else g.lineTo(x, y); } g.stroke();
    // pli de paupière au-dessus (donne du volume), plus marqué quand l'œil est grand ouvert
    g.strokeStyle = hexs(skinD, 0.65); g.lineWidth = 1.0; g.beginPath(); g.moveTo(x0 + 3, lidY(x0 + 3) - 3.2 - 1.5 * Math.max(0, open - 1)); g.quadraticCurveTo(cx, lidY(cx) - 4.8 - 2 * Math.max(0, open - 1), x0 + W - 3, lidY(x0 + W - 3) - 3.2 - 1.5 * Math.max(0, open - 1)); g.stroke();
    if (p.low > 0.3) { g.strokeStyle = hexs(skinD, 0.5); g.beginPath(); g.moveTo(x0 + 5, bot + 3); g.quadraticCurveTo(cx, bot + 5.5 - p.low * 4, x0 + W - 5, bot + 3); g.stroke(); }
  };
  eye(39, -1); eye(89, 1);
  if (p.star > 0.5) for (const cx of [39, 89]) { const sx = cx - 2, sy = eyeY - 3, r = 6.2; g.fillStyle = 'rgba(255,246,170,0.97)'; g.beginPath(); for (let k = 0; k < 8; k++) { const a = k * Math.PI / 4, rr_ = k % 2 ? r * 0.3 : r; const x = sx + Math.sin(a) * rr_, y = sy - Math.cos(a) * rr_; if (!k) g.moveTo(x, y); else g.lineTo(x, y); } g.closePath(); g.fill(); g.lineWidth = 0.7; g.strokeStyle = 'rgba(190,120,20,0.9)'; g.stroke(); }   // enthousiaste : étincelle dans l'œil
  if (p.bags > 0.05) { g.strokeStyle = hexs(shade(skin, 0.62), 0.6 * Math.min(1, p.bags)); g.lineWidth = 1.5; g.lineCap = 'round'; for (const cx of [39, 89]) { g.beginPath(); g.moveTo(cx - 12, eyeY + 17); g.quadraticCurveTo(cx, eyeY + 21.5, cx + 12, eyeY + 17); g.stroke(); g.beginPath(); g.moveTo(cx - 9, eyeY + 20.5); g.quadraticCurveTo(cx, eyeY + 24, cx + 9, eyeY + 20.5); g.stroke(); } }   // fatigue : cernes
  // --- sourcils : formes pleines effilées (bi = côté nez, bo = extérieur ; négatif = plus haut)
  for (const side of [-1, 1]) {
    if (p.nbr > 0.5) continue;
    const as = p.asyb > 0 ? p.asyb * (side > 0 ? -4 : 1.2) : 0;     // sourcils asymétriques : celui de droite (image) plus haut
    const xi = 64 + side * 9, xo = 64 + side * 40, yi = 39 + p.bi + as, yo = 38 + p.bo + as, ym = (yi + yo) / 2 - 3.2 * p.arch;
    const th = (u) => 4.6 - 2.2 * u;  // épaisseur : plus épais côté nez
    g.beginPath(); g.moveTo(xi, yi - th(0) / 2); g.quadraticCurveTo((xi + xo) / 2, ym - th(0.5) / 2, xo, yo - th(1) / 2); g.lineTo(xo + side * 1.2, yo + 0.4);
    g.quadraticCurveTo((xi + xo) / 2, ym + th(0.5) / 2 + 0.8, xi, yi + th(0) / 2); g.closePath(); g.fillStyle = hexs(brow); g.fill();
    g.lineWidth = 0.6; g.strokeStyle = hexs(shade(brow, 0.6), 0.8); g.stroke();
  }
  if (nat && p.knit > 0.05) { g.strokeStyle = hexs(skinD, 0.55 * Math.min(1, p.knit)); g.lineWidth = 1.3; g.lineCap = 'round'; for (const dx of [-2.6, 2.6]) { g.beginPath(); g.moveTo(64 + dx, 30); g.quadraticCurveTo(64 + dx * 1.5, 38, 64 + dx * 0.9, 45); g.stroke(); } }   // plis du front entre les sourcils (colère, effort, souci)
  // --- bouche
  const cx = 64 + p.mx * 4, my = 96, hw = 13 * p.mw, open = Math.max(0, p.mo), sm = p.ms, GG = nat ? 6 : 9;
  const cornerY = my - sm * 4.5, oh = open * 22;                // coins (sourire = plus haut), hauteur d'ouverture
  const upY = (u) => my - (open > 0.02 ? 2.2 * open : 0) - p.ua * Math.pow(Math.sin(u * Math.PI), 0.7) * (open > 0.02 ? Math.min(1, open * 2) : 0.25);  // lèvre du haut (u : 0..1), arche ua
  const loY = (u) => my + oh * Math.pow(Math.sin(u * Math.PI), 0.8) * (1 - 0.25 * sm) + Math.sin(u * Math.PI) * (open > 0.02 ? 0 : 0.6);
  const X = (u) => cx - hw + 2 * hw * u, Yc0 = (u, y) => y + (cornerY - my) * Math.pow(Math.abs(2 * u - 1), sm < 0 ? 1.3 : 2.2);
  const Yc = (p.asy > 0 || p.squig > 0) ? (u, y) => Yc0(u, y) - p.asy * (u - 0.5) * 6 + p.squig * 1.7 * Math.sin(u * Math.PI * 5 + p.qph) : Yc0;   // bouche de travers (sourire en coin) ou qui tremble
  if (p.plate > 0.5) {   // robot : une grille à la place de la bouche
    g.fillStyle = 'rgba(20,26,32,0.9)'; g.fillRect(cx - hw, my - 5, 2 * hw, 12); g.strokeStyle = 'rgba(150,165,180,0.85)'; g.lineWidth = 1.1; for (let k = 1; k < 7; k++) { const x = cx - hw + 2 * hw * k / 7; g.beginPath(); g.moveTo(x, my - 5); g.lineTo(x, my + 7); g.stroke(); } g.strokeRect(cx - hw, my - 5, 2 * hw, 12);
  } else if (open < 0.02 && !p.grit) {
    // bouche fermée : trait avec coins + ombre de lèvre inférieure
    if (nat) {   // lèvres pleines : lèvre du bas bombée, lèvre du haut avec son arc, ligne de bouche, pli du menton, dents si la lèvre se relève
      const lipC = mixc(skin, 0xa8402f, 0.5), lipD = shade(lipC, 0.8), lipL = shade(lipC, 1.14);
      const ln = (u) => Yc(u, my - 0.9 * p.chin + 0.4 * Math.sin(u * Math.PI) * (1 - sm));
      const thL = 4.6 + 2.6 * p.chin - 0.8 * p.ul, thU = 3.0 - 0.6 * p.chin, bow = (u) => 1 - 0.3 * Math.exp(-Math.pow((u - 0.5) / 0.1, 2));
      const up = (u) => ln(u) - p.ul * 2.4 * Math.max(0, 1 - 2.2 * u);                   // lèvre du haut relevée du côté gauche (dégoût, mépris)
      const fill = (top, bot, col) => { g.beginPath(); for (let k = 0; k <= 16; k++) { const u = k / 16; if (!k) g.moveTo(X(u), top(u)); else g.lineTo(X(u), top(u)); } for (let k = 16; k >= 0; k--) { const u = k / 16; g.lineTo(X(u), bot(u)); } g.closePath(); g.fillStyle = hexs(col); g.fill(); };
      if (p.ul > 0.05) { g.fillStyle = '#f1ebe0'; g.beginPath(); for (let k = 1; k <= 8; k++) { const u = k / 16; if (k === 1) g.moveTo(X(u), up(u)); else g.lineTo(X(u), up(u)); } for (let k = 8; k >= 1; k--) { const u = k / 16; g.lineTo(X(u), ln(u) + 0.6); } g.closePath(); g.fill(); }
      fill((u) => ln(u), (u) => ln(u) + thL * Math.pow(Math.sin(u * Math.PI), 0.7), lipC);
      g.strokeStyle = hexs(lipL, 0.6); g.lineWidth = 1.2; g.lineCap = 'round'; g.beginPath(); for (let k = 5; k <= 11; k++) { const u = k / 16; const y = ln(u) + thL * 0.5 * Math.pow(Math.sin(u * Math.PI), 0.7); if (k === 5) g.moveTo(X(u), y); else g.lineTo(X(u), y); } g.stroke();
      fill((u) => up(u) - thU * bow(u) * Math.pow(Math.sin(u * Math.PI), 0.8), (u) => ln(u), lipD);
      g.strokeStyle = hexs(0x4a1612, 0.9); g.lineWidth = 1.5; g.beginPath(); for (let k = 0; k <= 16; k++) { const u = k / 16; if (!k) g.moveTo(X(u), ln(u)); else g.lineTo(X(u), ln(u)); } g.stroke();
      if (p.chin > 0.05) { g.fillStyle = hexs(skinD, 0.34 * Math.min(1, p.chin)); g.beginPath(); g.ellipse(cx, my + thL + 6.2, 4.6, 1.8, 0, 0, 7); g.fill(); g.strokeStyle = hexs(skinD, 0.5 * Math.min(1, p.chin)); g.lineWidth = 1; g.beginPath(); g.moveTo(cx - 9, my + thL + 2.6); g.quadraticCurveTo(cx, my + thL + 4.6, cx + 9, my + thL + 2.6); g.stroke(); }
    } else {
    g.strokeStyle = hexs(0x4a1612); g.lineWidth = 2.0; g.lineCap = 'round'; g.beginPath(); for (let k = 0; k <= 12; k++) { const u = k / 12; const y = Yc(u, my + 0.4 * Math.sin(u * Math.PI) * (1 - sm)); if (!k) g.moveTo(X(u), y); else g.lineTo(X(u), y); } g.stroke();
    g.strokeStyle = hexs(skinD, 0.55); g.lineWidth = 1.6; g.beginPath(); g.moveTo(cx - hw * 0.45, my + 4.5); g.quadraticCurveTo(cx, my + 6.3, cx + hw * 0.45, my + 4.5); g.stroke();
    }
  } else {
    const path = () => { g.beginPath(); for (let k = 0; k <= 16; k++) { const u = k / 16; const y = Yc(u, upY(u)); if (!k) g.moveTo(X(u), y); else g.lineTo(X(u), y); } for (let k = 16; k >= 0; k--) { const u = k / 16; g.lineTo(X(u), Yc(u, Math.max(upY(u) + 0.5, loY(u) + (p.grit ? GG * Math.sin(u * Math.PI) : 0)))); } g.closePath(); };
    path(); g.save(); g.fillStyle = '#3a0a10'; g.fill(); g.clip();
    gr = g.createLinearGradient(0, my - 3, 0, my + oh + 2); gr.addColorStop(0, 'rgba(15,0,3,0.85)'); gr.addColorStop(1, 'rgba(70,10,16,0.3)'); g.fillStyle = gr; g.fillRect(cx - hw - 4, my - 6, 2 * hw + 8, oh + 18);
    // langue
    if (p.tg > 0.02 && open > 0.1) { g.fillStyle = '#c8403c'; g.beginPath(); g.ellipse(cx, my + oh * 0.95, hw * 0.62, Math.max(2.5, oh * 0.42 * p.tg), 0, 0, 7); g.fill(); g.fillStyle = 'rgba(255,160,150,0.45)'; g.beginPath(); g.ellipse(cx - hw * 0.15, my + oh * 0.72, hw * 0.22, 1.4, 0, 0, 7); g.fill(); g.strokeStyle = 'rgba(120,20,25,0.6)'; g.lineWidth = 0.8; g.beginPath(); g.moveTo(cx, my + oh * 0.7); g.lineTo(cx, my + oh * 0.95); g.stroke(); }
    // dents du haut / du bas (bandes qui suivent les lèvres), séparations discrètes
    const teeth = (yf, hgt, dir) => { g.beginPath(); for (let k = 0; k <= 16; k++) { const u = k / 16; const y = Yc(u, yf(u)); if (!k) g.moveTo(X(u), y - dir * 3); else g.lineTo(X(u), y - dir * 3); } for (let k = 16; k >= 0; k--) { const u = k / 16; g.lineTo(X(u), Yc(u, yf(u)) + dir * hgt * Math.pow(Math.sin(u * Math.PI), 0.35)); } g.closePath(); g.fillStyle = '#f7f2ea'; g.fill();
      g.strokeStyle = 'rgba(150,130,125,0.55)'; g.lineWidth = 0.6; for (let k = 2; k < 7; k++) { const u = k / 8; const y = Yc(u, yf(u)); g.beginPath(); g.moveTo(X(u), y); g.lineTo(X(u), y + dir * hgt * 0.8); g.stroke(); } };
    if (p.tt > 0.02) teeth(upY, 4.2 * Math.min(1, p.tt) * (p.grit ? 1.15 : 1), 1);
    if (p.tb > 0.02) teeth((u) => Math.max(upY(u) + 0.5, loY(u) + (p.grit ? GG * Math.sin(u * Math.PI) : 0)), 3.4 * Math.min(1, p.tb), -1);
    g.restore();
    path(); g.lineWidth = 1.7; g.lineJoin = 'round'; g.strokeStyle = '#3a0c0c'; g.stroke();
    if (nat) {   // lèvres autour de l'ouverture
      const lipC = mixc(skin, 0xa8402f, 0.5), lipD = shade(lipC, 0.8); const lowL = (u) => Math.max(upY(u) + 0.5, loY(u) + (p.grit ? GG * Math.sin(u * Math.PI) : 0));
      const band = (f1, f2, col) => { g.beginPath(); for (let k = 0; k <= 16; k++) { const u = k / 16; if (!k) g.moveTo(X(u), f1(u)); else g.lineTo(X(u), f1(u)); } for (let k = 16; k >= 0; k--) { const u = k / 16; g.lineTo(X(u), f2(u)); } g.closePath(); g.fillStyle = hexs(col); g.fill(); };
      band((u) => Yc(u, lowL(u)) + 0.8, (u) => Yc(u, lowL(u)) + 0.8 + (3.6 + 1.6 * p.chin) * Math.pow(Math.sin(u * Math.PI), 0.6), lipC);
      band((u) => Yc(u, upY(u)) - 2.8 * Math.pow(Math.sin(u * Math.PI), 0.8), (u) => Yc(u, upY(u)) - 0.2, lipD);
    }
    // lèvre inférieure : reflet doux sous l'ouverture
    g.strokeStyle = hexs(shade(skin, 1.12), 0.6); g.lineWidth = 1.4; g.beginPath(); g.moveTo(cx - hw * 0.4, my + oh + 3.2 + (p.grit ? GG : 0)); g.quadraticCurveTo(cx, my + oh + 4.4 + (p.grit ? GG : 0), cx + hw * 0.4, my + oh + 3.2 + (p.grit ? GG : 0)); g.stroke();
  }
  if (nat && p.dimp > 0.05 && p.ms > 0.3) { g.strokeStyle = hexs(skinD, 0.5 * Math.min(1, p.dimp)); g.lineWidth = 1.2; g.lineCap = 'round'; for (const sx of [-1, 1]) { const x = cx + sx * (hw + 1.8), y = cornerY; g.beginPath(); g.moveTo(x, y - 3.4); g.quadraticCurveTo(x + sx * 3.4, y, x, y + 3.2); g.stroke(); } }   // fossettes de sourire
  if (p.zzz > 0.5) { g.fillStyle = 'rgba(205,225,255,0.95)'; g.strokeStyle = 'rgba(40,60,110,0.85)'; g.lineWidth = 0.9; g.textAlign = 'center'; for (const [x, y, s] of [[112, 104, 22], [117, 84, 16], [119, 69, 12]]) { g.font = `bold ${s}px sans-serif`; g.lineWidth = 1.6; g.strokeText('Z', x, y); g.fillText('Z', x, y); } }   // sommeil : les Z
  // --- sueur / larmes / saleté
  if (p.sweat >= 0.5) drop(g, 109, 47, 4.4);
  if (p.sweat >= 1.5) drop(g, 18, 92, 3.8);
  if (p.tear > 0.05) { g.fillStyle = 'rgba(175,220,255,0.8)'; g.fillRect(25, 70, 2.6, 13 * p.tear); g.fillRect(103, 70, 2.6, 8 * p.tear); drop(g, 26.3, 70 + 13 * p.tear, 3.0); }
  if (spec.dirt) {
    g.fillStyle = hexs(shade(skin, 0.6), 0.5); g.beginPath(); g.ellipse(28, 106, 7, 3, 0.3, 0, 7); g.fill(); g.beginPath(); g.ellipse(100, 28, 5, 2.4, -0.4, 0, 7); g.fill();
    g.strokeStyle = 'rgba(150,25,20,0.9)'; g.lineWidth = 1.4; g.beginPath(); g.moveTo(96, 22); g.lineTo(104, 27); g.stroke(); g.beginPath(); g.moveTo(98, 21); g.lineTo(103, 24); g.stroke();
  }
}

// texture dynamique par personnage : on ne redessine que si les paramètres (arrondis) changent
export function faceRig(spec, N = 512) {
  const c = document.createElement('canvas'); c.width = c.height = N; const g = c.getContext('2d');
  const tex = new THREE.CanvasTexture(c); tex.magFilter = THREE.LinearFilter; tex.minFilter = THREE.LinearMipmapLinearFilter; tex.generateMipmaps = true; tex.anisotropy = 8; tex.colorSpace = THREE.SRGBColorSpace;
  let key = ''; const api = { tex, set: null, cb: null };      // cb(q) : appelé à chaque changement d'expression (relief du visage, face_relief.js)
  const set = (P) => {
    const q = {}; for (const k in P) q[k] = typeof P[k] === 'number' ? Math.round(P[k] * 40) / 40 : P[k];
    const nk = JSON.stringify(q); if (nk === key) return; key = nk;
    g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, N, N); g.setTransform(N / 128, 0, 0, N / 128, 0, 0); drawFace(g, spec, q); tex.needsUpdate = true;
    if (api.cb) api.cb(q);
  };
  api.set = set;
  return api;
}
// compatibilité : texture fixe d'une expression
export function paintFace(spec, expr) { const r = faceRig(spec, 256); r.set(exprParams(expr)); return r.tex; }
// petits mouvements d'yeux et clignements, déterministes en fonction du temps
const hash = (n) => { const s = Math.sin(n * 127.1 + 311.7) * 43758.5453; return s - Math.floor(s); };
export function blinkAmount(t, seed = 0) {
  const per = 3.2 + seed * 1.3; const k = Math.floor((t + seed * 7) / per); const t0 = k * per + hash(k + seed * 31) * (per - 0.4) - seed * 7; const d = t - t0;
  if (d < 0 || d > 0.2) return 0; return d < 0.07 ? d / 0.07 : 1 - (d - 0.07) / 0.13;
}
export function saccade(t, seed = 0) { const k = Math.floor(t / 1.35 + seed * 3.1); return [(hash(k * 1.7 + seed) - 0.5) * 0.35, (hash(k * 2.3 + seed + 9) - 0.5) * 0.25]; }

// micro-mouvements du visage (naturel) : sourcils qui dérivent, souffle des lèvres, léger clignement des paupières, tremblement de lèvre qui vit ; fonction pure du temps
export function micro(P, t, seed = 0, k = 1) {
  if (globalThis.HS_FACE_LEGACY || !globalThis.HS_FACE_MICRO) return P;      // micro-mouvements : OFF par défaut (effet « vague » jugé daté) ; contrat `face_micro: true` pour les réactiver
  const s = seed * 1.7;
  P.bi += k * 0.5 * Math.sin(t * 0.9 + s); P.bo += k * 0.4 * Math.sin(t * 0.77 + s * 2.1);
  P.ms += k * 0.05 * Math.sin(t * 0.5 + s * 3); P.eo *= 1 + k * 0.03 * Math.sin(t * 1.3 + s); P.asyb += k * 0.1 * Math.sin(t * 0.6 + s * 1.3);
  P.mw *= 1 + k * 0.012 * Math.sin(t * 1.9 + s);
  if (P.squig > 0.05) { P.qph = t * 22 + s; if (P.chin > 0.3) P.chin *= 1 + 0.1 * Math.sin(t * 17 + s); }
  return P;
}

// bouche qui parle : la parole ouvre la bouche PAR-DESSUS l'expression ; voyelles rondes (o, u : bouche étroite) et larges (i, é : bouche large, dents du haut visibles) en alternance
export function talkMouth(P, t, talk) {
  if (!(talk > 0)) return;
  const syl = Math.abs(Math.sin(t * 10.5 + Math.sin(t * 3.7) * 2));
  if (globalThis.HS_FACE_LEGACY) { P.mo = Math.max(P.mo, talk * (0.08 + 0.42 * syl)); P.mw = Math.max(0.7, P.mw - 0.1 * syl * talk); return; }
  const vis = 0.5 + 0.5 * Math.sin(t * 6.3 + Math.sin(t * 2.1) * 1.7);          // 0 : voyelle ronde, 1 : voyelle large
  P.mo = Math.max(P.mo, talk * (0.07 + 0.36 * syl * (1 - 0.3 * vis)));
  P.mw = Math.max(0.62, P.mw * (1 - 0.3 * (1 - vis) * talk * syl) + 0.1 * vis * talk * syl);
  if (P.mo > 0.12) P.tt = Math.max(P.tt, talk * (0.2 + 0.5 * vis));
  if (P.mo > 0.22 && vis > 0.6) P.tb = Math.max(P.tb, 0.3 * talk);
}
