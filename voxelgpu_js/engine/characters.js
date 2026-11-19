import * as THREE from 'three';
import { painter, toTex, mulberry, pick, C } from './textures.js';

export const PX = 1 / 16;

// Minecraft-style box UV layout on a 64x64 skin
function boxUV(geo, w, h, d, u, v) {
  const R = { px: [u + d + w, v + d, d, h], nx: [u, v + d, d, h], py: [u + d, v, w, d], ny: [u + d + w, v, w, d], pz: [u + d, v + d, w, h], nz: [u + 2 * d + w, v + d, w, h] };
  const order = ['px', 'nx', 'py', 'ny', 'pz', 'nz'];
  const uv = geo.attributes.uv;
  for (let f = 0; f < 6; f++) {
    const [x0, y0, rw, rh] = R[order[f]];
    for (let i = 0; i < 4; i++) { const k = f * 4 + i; const uu = uv.getX(k), vv = uv.getY(k); uv.setXY(k, (x0 + uu * rw) / 64, 1 - (y0 + (1 - vv) * rh) / 64); }
  }
  uv.needsUpdate = true;
}
function partMesh(w, h, d, u, v, mat, inflate = 0) {
  const g = new THREE.BoxGeometry((w + inflate) * PX, (h + inflate) * PX, (d + inflate) * PX);
  boxUV(g, w, h, d, u, v);
  const m = new THREE.Mesh(g, mat); m.castShadow = true; m.receiveShadow = true; return m;
}
function paintBox(p, u, v, w, h, d, F) {
  const rect = { front: [u + d, v + d, w, h], back: [u + 2 * d + w, v + d, w, h], right: [u, v + d, d, h], left: [u + d + w, v + d, d, h], top: [u + d, v, w, d], bottom: [u + d + w, v, w, d] };
  for (const k in rect) { const fn = F[k] || F.all; if (!fn) continue; const [x0, y0, rw, rh] = rect[k]; p.fill(x0, y0, rw, rh, (x, y) => fn(x, y, rw, rh, k)); }
}

// ---------------------------------------------------------------- skins
function faceRows(def, expr) {
  const { H, H2, Hs, S, L, W, I1, I2, P, M, sideHair } = def;
  const side = sideHair ? H : S;
  const rows = [
    [H, H, H, H, H, H, H, H],
    [H, H2, H, H, H, H, H2, H],
    def.bangs,
    [side, L, L, S, S, L, L, side],
    [side, W, I1, S, S, I1, W, side],
    [side, I2, I2, S, S, I2, I2, side],
    [side, P, S, S, S, S, P, side],
    [sideHair ? Hs : S, S, S, M, M, S, S, sideHair ? Hs : S],
  ];
  const setEyes = (r3, r4, r5) => { rows[3][1] = r3[0]; rows[3][2] = r3[1]; rows[3][5] = r3[2]; rows[3][6] = r3[3]; rows[4][1] = r4[0]; rows[4][2] = r4[1]; rows[4][5] = r4[2]; rows[4][6] = r4[3]; rows[5][1] = r5[0]; rows[5][2] = r5[1]; rows[5][5] = r5[2]; rows[5][6] = r5[3]; };
  if (expr === 'lookL') setEyes([L, L, L, L], [I1, W, I1, W], [I2, I2, I2, I2]);
  if (expr === 'lookR') setEyes([L, L, L, L], [W, I1, W, I1], [I2, I2, I2, I2]);
  if (expr === 'blink') setEyes([S, S, S, S], [S, S, S, S], [L, L, L, L]);
  if (expr === 'happy') { setEyes([S, S, S, S], [L, L, L, L], [S, S, S, S]); rows[6][2] = def.Md; rows[6][5] = def.Md; }
  if (expr === 'smile') { rows[6][2] = def.Md; rows[6][5] = def.Md; }
  if (expr === 'surprised') { setEyes([L, L, L, L], [W, I1, I1, W], [I2, I2, I2, I2]); rows[7][3] = 0x5a2a2a; rows[7][4] = 0x5a2a2a; }
  if (expr === 'lookUp') setEyes([W, I1, I1, W], [I2, I2, I2, I2], [S, S, S, S]);
  return rows;
}

function noisy(r, cols) { return () => pick(r, cols); }

function linaSkin(expr) {
  const p = painter(64, 64); p.clear(); const r = mulberry(101);
  const hair = [0x2e1f18, 0x34241b, 0x281a13], H = 0x2e1f18, H2 = 0x46301f, Hs = 0x20150f;
  const S = 0xeab792, Ss = 0xd9a27c;
  const def = { H, H2, Hs, S, L: 0x1d1626, W: 0xffffff, I1: 0x1f6b3a, I2: 0x3dae5e, P: 0xeea596, M: 0xb8665a, Md: 0xd9937a, sideHair: true, bangs: [H, H, S, S, H, S, S, H] };
  const face = faceRows(def, expr);
  const hr = noisy(r, hair);
  paintBox(p, 0, 0, 8, 8, 8, { front: (x, y) => face[y][x], top: hr, back: hr, left: hr, right: hr, bottom: () => Ss });
  // hat layer (volume hair)
  paintBox(p, 32, 0, 8, 8, 8, {
    top: hr, back: hr,
    left: (x, y) => (y < 7 || x > 1) ? hr() : null, right: (x, y) => (y < 7 || x < 6) ? hr() : null,
    front: (x, y) => (y < 2 || (y === 2 && (x < 2 || x === 4 || x > 5)) || ((x === 0 || x === 7) && y < 6)) ? hr() : null,
  });
  // body: yellow rain jacket, green shirt, backpack straps
  const J = [0xf0b232, 0xe8aa2c, 0xf6bb3c], Js = 0xd18f1e, G = 0x2f6b3a, ST = 0x6b4527;
  const jr = noisy(r, J);
  paintBox(p, 16, 16, 8, 12, 4, {
    front: (x, y) => {
      if ((x === 1 || x === 6) && y < 9) return y === 4 ? 0xc8c8c8 : ST;
      if (y < 3 && x >= 3 && x <= 4) return G; if (y === 0 && (x === 2 || x === 5)) return G;
      if (y >= 3 && x === 3) return 0xb07a1a; if (y >= 3 && x === 4) return Js;
      if (y === 11) return 0xc98a1e; if (y >= 8 && y <= 9 && (x === 0 || x === 7)) return Js;
      return jr();
    },
    back: (x, y) => y < 3 ? (y === 2 ? Js : 0xe0a02a) : (y === 11 ? 0xc98a1e : jr()),
    left: (x, y) => y === 11 ? 0xc98a1e : jr(), right: (x, y) => y === 11 ? 0xc98a1e : jr(),
    top: () => Js, bottom: () => 0x3a5a8c,
  });
  const arm = { all: (x, y) => y < 9 ? jr() : y === 9 ? Js : S, top: () => Js, bottom: () => S };
  paintBox(p, 40, 16, 4, 12, 4, arm); paintBox(p, 32, 48, 4, 12, 4, arm);
  const JE = [0x3a5a8c, 0x34507e, 0x41639a]; const jer = noisy(r, JE);
  const leg = { all: (x, y) => y < 9 ? jer() : y === 9 ? 0x5274aa : y === 10 ? 0x6b4527 : 0x4a2f19, top: () => 0x3a5a8c, bottom: () => 0x3a2614 };
  paintBox(p, 0, 16, 4, 12, 4, leg); paintBox(p, 16, 48, 4, 12, 4, leg);
  return p.done();
}

function maloSkin(expr) {
  const p = painter(64, 64); p.clear(); const r = mulberry(202);
  const hair = [0xc8642a, 0xd06c2e, 0xb85a24], H = 0xc8642a, H2 = 0xe58444, Hs = 0xa04e20;
  const S = 0xf2c7a5, Ss = 0xe0b08c, F = 0xd99a72;
  const def = { H, H2, Hs, S, L: 0x1d1626, W: 0xffffff, I1: 0x2a4fa8, I2: 0x4f86e0, P: F, M: 0xc07060, Md: 0xe0a888, sideHair: false, bangs: [H, H, S, H, S, S, H, H] };
  const face = faceRows(def, expr);
  const hr = noisy(r, hair);
  paintBox(p, 0, 0, 8, 8, 8, { front: (x, y) => face[y][x], top: hr, back: (x, y) => y < 6 ? hr() : Ss, left: (x, y) => y < 3 ? hr() : (y === 4 && x === 4 ? Ss : S), right: (x, y) => y < 3 ? hr() : (y === 4 && x === 3 ? Ss : S), bottom: () => Ss });
  paintBox(p, 32, 0, 8, 8, 8, {
    top: hr, back: (x, y) => y < 5 ? hr() : null,
    left: (x, y) => y < 2 || (y === 2 && x % 2 === 0) ? hr() : null, right: (x, y) => y < 2 || (y === 2 && x % 2 === 1) ? hr() : null,
    front: (x, y) => (y < 1 || (y === 1 && x !== 3 && x !== 5)) ? hr() : null,
  });
  const flannel = (x, y, u0 = 0) => { const a = (x + u0) % 4 === 0, b = y % 4 === 0; if (a && b) return 0x5a160f; if (a || b) return 0x7d2018; return r() < 0.15 ? 0xd8584a : 0xc23b2e; };
  const tee = [0xf0f0ea, 0xe6e6e0];
  paintBox(p, 16, 16, 8, 12, 4, {
    front: (x, y) => (x >= 2 && x <= 5) ? (y === 0 && (x === 3 || x === 4) ? Ss : pick(r, tee)) : flannel(x, y),
    back: (x, y) => flannel(x, y, 1), left: (x, y) => flannel(x, y, 2), right: (x, y) => flannel(x, y, 3),
    top: (x, y) => flannel(x, y), bottom: () => 0xa8956a,
  });
  const arm = { all: (x, y) => y < 7 ? flannel(x, y) : y === 7 ? 0xd8584a : (r() < 0.12 ? F : S), top: (x, y) => flannel(x, y), bottom: () => S };
  paintBox(p, 40, 16, 4, 12, 4, arm); paintBox(p, 32, 48, 4, 12, 4, arm);
  const K = [0xa8956a, 0x9a875d, 0xb09d72];
  const leg = { all: (x, y) => y < 10 ? pick(r, K) : y === 10 ? (x === 1 ? 0xd23a2a : 0xeeeeee) : 0x8a8a8a, top: () => 0xa8956a, bottom: () => 0x6a6a6a };
  paintBox(p, 0, 16, 4, 12, 4, leg); paintBox(p, 16, 48, 4, 12, 4, leg);
  return p.done();
}

// ---------------------------------------------------------------- rig
export const EXPRS = ['neutral', 'lookL', 'lookR', 'blink', 'happy', 'smile', 'surprised', 'lookUp'];

export function buildHumanoid(skinFn, opts = {}) {
  const tex = {}; for (const e of EXPRS) tex[e] = toTex(skinFn(e), { mip: false, repeat: false });
  const mat = new THREE.MeshLambertMaterial({ map: tex.neutral });
  const headMat = new THREE.MeshLambertMaterial({ map: tex.neutral });
  const hatMat = new THREE.MeshLambertMaterial({ map: tex.neutral, alphaTest: 0.5, side: THREE.DoubleSide });
  const root = new THREE.Group();
  const hips = new THREE.Group(); hips.position.y = 12 * PX; root.add(hips);
  const torso = new THREE.Group(); hips.add(torso);
  const body = partMesh(8, 12, 4, 16, 16, mat); body.position.y = 6 * PX; torso.add(body);
  const neck = new THREE.Group(); neck.position.y = 12 * PX; torso.add(neck);
  const head = partMesh(8, 8, 8, 0, 0, headMat); head.position.y = 4 * PX; neck.add(head);
  const hat = partMesh(8, 8, 8, 32, 0, hatMat, 0.9); hat.position.y = 4 * PX; neck.add(hat);
  const shL = new THREE.Group(); shL.position.set(6 * PX, 10 * PX, 0); torso.add(shL);
  const armL = partMesh(4, 12, 4, 32, 48, mat); armL.position.y = -4 * PX; shL.add(armL);
  const shR = new THREE.Group(); shR.position.set(-6 * PX, 10 * PX, 0); torso.add(shR);
  const armR = partMesh(4, 12, 4, 40, 16, mat); armR.position.y = -4 * PX; shR.add(armR);
  const handL = new THREE.Group(); handL.position.y = -10 * PX; shL.add(handL);
  const handR = new THREE.Group(); handR.position.y = -10 * PX; shR.add(handR);
  const lgL = new THREE.Group(); lgL.position.set(2 * PX, 0, 0); hips.add(lgL);
  const legL = partMesh(4, 12, 4, 16, 48, mat); legL.position.y = -6 * PX; lgL.add(legL);
  const lgR = new THREE.Group(); lgR.position.set(-2 * PX, 0, 0); hips.add(lgR);
  const legR = partMesh(4, 12, 4, 0, 16, mat); legR.position.y = -6 * PX; lgR.add(legR);
  const ch = { root, hips, torso, neck, head, shL, shR, handL, handR, lgL, lgR, tex, headMat, hatMat, expr: 'neutral' };
  ch.setExpr = (e) => { if (ch.expr === e) return; ch.expr = e; headMat.map = tex[e]; headMat.needsUpdate = true; };
  ch.reset = () => {
    hips.position.set(0, 12 * PX, 0); hips.rotation.set(0, 0, 0); torso.rotation.set(0, 0, 0); neck.rotation.set(0, 0, 0);
    shL.rotation.set(0, 0, 0); shR.rotation.set(0, 0, 0); lgL.rotation.set(0, 0, 0); lgR.rotation.set(0, 0, 0); root.rotation.set(0, 0, 0);
  };
  return ch;
}

export function buildLina() {
  const ch = buildHumanoid(linaSkin);
  const hairMat = new THREE.MeshLambertMaterial({ color: 0x2c1e17 });
  const back = new THREE.Mesh(new THREE.BoxGeometry(8.6 * PX, 12 * PX, 1.3 * PX), hairMat); back.position.set(0, 1.5 * PX, -4.75 * PX); back.castShadow = true; ch.neck.add(back);
  const tip = new THREE.Mesh(new THREE.BoxGeometry(7 * PX, 2 * PX, 1.1 * PX), hairMat); tip.position.set(0, -5.5 * PX, -4.6 * PX); tip.castShadow = true; ch.neck.add(tip);
  // backpack
  const bpMat = new THREE.MeshLambertMaterial({ color: 0x7a5230 }), bpDark = new THREE.MeshLambertMaterial({ color: 0x5c3c22 });
  const bp = new THREE.Mesh(new THREE.BoxGeometry(6 * PX, 7 * PX, 3 * PX), bpMat); bp.position.set(0, 4.5 * PX, -3.5 * PX); bp.castShadow = true; ch.torso.add(bp);
  const flap = new THREE.Mesh(new THREE.BoxGeometry(6.2 * PX, 2.5 * PX, 3.2 * PX), bpDark); flap.position.set(0, 7.2 * PX, -3.5 * PX); ch.torso.add(flap);
  const pocket = new THREE.Mesh(new THREE.BoxGeometry(4 * PX, 2.5 * PX, 1 * PX), bpDark); pocket.position.set(0, 2.6 * PX, -5.4 * PX); ch.torso.add(pocket);
  ch.extras = { back, bp };
  return ch;
}
export function buildMalo() { return buildHumanoid(maloSkin); }

export function buildBasket(miscT) {
  const g = new THREE.Group();
  const wm = new THREE.MeshLambertMaterial({ map: miscT.wicker });
  const base = new THREE.Mesh(new THREE.BoxGeometry(7 * PX, 4 * PX, 5 * PX), wm); base.position.y = -7 * PX; base.castShadow = true; g.add(base);
  const hm = new THREE.MeshLambertMaterial({ color: 0x8c6230 });
  const h1 = new THREE.Mesh(new THREE.BoxGeometry(0.8 * PX, 5 * PX, 0.8 * PX), hm); h1.position.set(-3 * PX, -3 * PX, 0); g.add(h1);
  const h2 = h1.clone(); h2.position.x = 3 * PX; g.add(h2);
  const h3 = new THREE.Mesh(new THREE.BoxGeometry(6.8 * PX, 0.8 * PX, 0.8 * PX), hm); h3.position.set(0, -0.6 * PX, 0); g.add(h3);
  const cap = new THREE.MeshLambertMaterial({ map: miscT.capRed });
  for (const [x, z] of [[-1.8, 0.5], [1.5, -0.8], [0.2, 1.2]]) { const m = new THREE.Mesh(new THREE.BoxGeometry(3 * PX, 1.6 * PX, 3 * PX), cap); m.position.set(x * PX, -4.6 * PX, z * PX); g.add(m); }
  return g;
}

export function buildHandMushroom(miscT) {
  const g = new THREE.Group();
  const st = new THREE.Mesh(new THREE.BoxGeometry(1.6 * PX, 3 * PX, 1.6 * PX), new THREE.MeshLambertMaterial({ map: miscT.stem })); st.position.y = 0; g.add(st);
  const cp = new THREE.Mesh(new THREE.BoxGeometry(4.5 * PX, 2 * PX, 4.5 * PX), new THREE.MeshLambertMaterial({ map: miscT.capRed })); cp.position.y = 2.2 * PX; g.add(cp);
  g.traverse(o => { if (o.isMesh) o.castShadow = true; });
  return g;
}

// ---------------------------------------------------------------- moss creature
let mossMats = null;
export function buildMossling(T, misc, variant = 0) {
  if (!mossMats) {
    const tex = T.moss.clone(); tex.repeat.set(10 / 16, 9 / 16); tex.needsUpdate = true;
    const texD = T.mossDark.clone(); texD.needsUpdate = true;
    const eye = new THREE.MeshBasicMaterial({ color: 0xffffff }); eye.color.setRGB(2.3, 2.15, 1.15);
    mossMats = {
      body: [0xffffff, 0xe0ffd8, 0xc8f0b0, 0xb8f0d8].map(c => new THREE.MeshLambertMaterial({ map: tex, color: c })),
      dark: new THREE.MeshLambertMaterial({ map: texD }), eye,
      mouth: new THREE.MeshBasicMaterial({ color: 0x1c2a12 }),
      sprout: new THREE.MeshLambertMaterial({ map: misc.leafSprout }),
      petal: new THREE.MeshLambertMaterial({ color: 0xfff6f0 }), petalPink: new THREE.MeshLambertMaterial({ color: 0xffa8d2 }),
      center: new THREE.MeshLambertMaterial({ color: 0xffd23a }),
      cap: new THREE.MeshLambertMaterial({ map: misc.capRed }),
    };
  }
  const M = mossMats;
  const root = new THREE.Group();
  const body = new THREE.Group(); root.add(body);
  const box = (w, h, d, m, x, y, z, parent = body) => { const b = new THREE.Mesh(new THREE.BoxGeometry(w * PX, h * PX, d * PX), m); b.position.set(x * PX, y * PX, z * PX); b.castShadow = true; b.receiveShadow = true; parent.add(b); return b; };
  const bm = M.body[variant % 4];
  box(10, 9, 10, bm, 0, 6.5, 0);
  const feet = [];
  for (const [x, z] of [[-3, 3], [3, 3], [-3, -3], [3, -3]]) feet.push(box(3, 2, 3, M.dark, x, 1, z, root));
  const eyes = [box(2, 3, 0.6, M.eye, -2.2, 7.3, 5.1), box(2, 3, 0.6, M.eye, 2.2, 7.3, 5.1)];
  box(2, 0.8, 0.5, M.mouth, 0, 4.4, 5.05);
  const top = new THREE.Group(); top.position.y = 11 * PX; body.add(top);
  if (variant === 4) { box(6, 2, 6, M.cap, 0, 1, 0, top); box(4, 1.2, 4, M.cap, 0, 2.4, 0, top); }
  else {
    box(1, 3, 1, M.sprout, 0, 1.5, 0, top);
    const l1 = box(3.5, 0.7, 2, M.sprout, 1.6, 3, 0, top); l1.rotation.z = 0.5;
    const l2 = box(3.5, 0.7, 2, M.sprout, -1.6, 3.3, 0, top); l2.rotation.z = -0.5;
    if (variant === 1 || variant === 5) { box(1.6, 1.6, 1.6, variant === 5 ? M.petalPink : M.petal, 3, 0.8, 2.5, top); box(0.8, 0.8, 0.8, M.center, 3, 1.4, 3.2, top); }
  }
  const mk = { root, body, eyes, top, feet, variant };
  mk.setBlink = (b) => { for (const e of eyes) e.scale.y = b ? 0.18 : 1; };
  return mk;
}
