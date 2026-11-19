// Extra effects for v2: time-of-day sky with stars, ground shadow decals (pools / tar), shadow thread.
import * as THREE from 'three';

export function buildSky2(scene) {
  const mat = new THREE.ShaderMaterial({
    uniforms: { sunDir: { value: new THREE.Vector3(0, 1, 0) }, top: { value: new THREE.Color(0x3d8fe6) }, horizon: { value: new THREE.Color(0xd8f0ff) }, glow: { value: new THREE.Color(1, 0.9, 0.7) }, sunCol: { value: new THREE.Color(1, 0.95, 0.8) }, sunPower: { value: 1 }, sunSize: { value: 900 }, stars: { value: 0 }, haze: { value: 0.5 } },
    vertexShader: `varying vec3 vDir; void main(){ vDir = normalize(position); vec4 p = projectionMatrix * modelViewMatrix * vec4(position,1.0); gl_Position = p.xyww; }`,
    fragmentShader: `uniform vec3 sunDir, top, horizon, glow, sunCol; uniform float sunPower, sunSize, stars, haze; varying vec3 vDir;
      float hash(vec3 p){ return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }
      void main(){ vec3 d = normalize(vDir); float h = clamp(d.y, 0.0, 1.0);
        vec3 col = mix(horizon, top, pow(h, 0.48));
        float s = max(dot(d, normalize(sunDir)), 0.0);
        col = mix(col, glow, pow(s, 5.0) * haze * (1.0 - h * 0.6));
        col += sunCol * (pow(s, sunSize) * 30.0 + pow(s, 48.0) * 0.9) * sunPower;
        if (stars > 0.0) { vec3 q = floor(d * 260.0); float st = hash(q); float b = smoothstep(0.9965, 1.0, st) * smoothstep(0.02, 0.25, d.y); col += vec3(0.9, 0.95, 1.0) * b * 2.2 * stars; }
        if (d.y < 0.0) col = mix(horizon, horizon * 0.6, clamp(-d.y * 3.0, 0.0, 1.0));
        gl_FragColor = vec4(col, 1.0); }`,
    side: THREE.BackSide, depthWrite: false,
  });
  const m = new THREE.Mesh(new THREE.SphereGeometry(450, 32, 16), mat); m.frustumCulled = false; m.renderOrder = -10; scene.add(m); return m;
}

// Soft black decal on the ground (shadow pool / tar). shape 0 = disc, 1 = irregular blob, 2 = elongated finger
export function buildDecal(scene, { shape = 0, seed = 1 } = {}) {
  const mat = new THREE.ShaderMaterial({
    uniforms: { uOp: { value: 0.92 }, uSeed: { value: seed }, uShape: { value: shape }, uTime: { value: 0 } },
    vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`,
    fragmentShader: `uniform float uOp, uSeed, uShape, uTime; varying vec2 vUv;
      void main(){ vec2 p = vUv * 2.0 - 1.0; float a = atan(p.y, p.x); float r = length(p);
        float edge = 1.0;
        if (uShape > 0.5) edge = 0.82 + 0.08 * sin(a * 3.0 + uSeed) + 0.06 * sin(a * 7.0 + uSeed * 2.3 + uTime * 0.7) + 0.04 * sin(a * 13.0 + uSeed * 5.1);
        float al = 1.0 - smoothstep(edge - 0.08, edge, r);
        gl_FragColor = vec4(0.012, 0.012, 0.016, al * uOp); }`,
    transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4,
  });
  const m = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat); m.rotation.x = -Math.PI / 2; m.renderOrder = 2; m.visible = false; scene.add(m);
  return { mesh: m, mat, set(x, y, z, rx, rz, op = 0.92, rot = 0) { m.visible = rx > 0.01 && op > 0.01; m.position.set(x, y, z); m.scale.set(rx, rz, 1); m.rotation.z = rot; mat.uniforms.uOp.value = op; } };
}

// whipping thread made of segments
export function buildThread(scene, n = 40) {
  const mat = new THREE.MeshBasicMaterial({ color: 0x040406 });
  const segs = []; for (let i = 0; i < n; i++) { const s = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.06, 0.32), mat); s.castShadow = true; s.visible = false; scene.add(s); segs.push(s); }
  return {
    segs,
    set(fn, on = true) { // fn(i/n) -> [x,y,z,width]
      for (let i = 0; i < n; i++) { const s = segs[i]; s.visible = on; if (!on) continue; const a = fn(i / n), b = fn((i + 1) / n); s.position.set((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2); s.rotation.set(0, Math.atan2(b[0] - a[0], b[2] - a[2]), 0); const len = Math.hypot(b[0] - a[0], b[2] - a[2]); s.scale.set(a[3] ?? 1, 1, Math.max(0.01, len / 0.32 * 1.15)); }
    }
  };
}

// Time-of-day presets
export const TOD = {
  noon: { sun: [0.25, 0.9, 0.35], sunCol: 0xfff4e4, sunI: 3.3, hemiSky: 0xbfd9ff, hemiGround: 0x6b7a52, hemiI: 1.5, fog: 0xd2e4f2, fogD: 0.003, top: 0x3d8de6, horizon: 0xd4eaff, glow: 0xffffff, haze: 0.2, stars: 0, exposure: 1.0, night: 0, warm: 0, sat: 1.12, fillI: 0.4, sunSize: 1200 },
  morning: { sun: [-0.45, 0.55, 0.7], sunCol: 0xfff0d8, sunI: 3.2, hemiSky: 0xc4dcff, hemiGround: 0x6b7a52, hemiI: 1.45, fog: 0xd8e6f2, fogD: 0.005, top: 0x4790e0, horizon: 0xdcecff, glow: 0xfff2dc, haze: 0.35, stars: 0, exposure: 1.0, night: 0, warm: 0.1, sat: 1.12, fillI: 0.4, sunSize: 1000 },
  golden: { sunPow: 0.5, sun: [0.12, 0.2, 0.97], sunCol: 0xffb36a, sunI: 3.6, hemiSky: 0xffb4a0, hemiGround: 0x6a4a3a, hemiI: 1.05, fog: 0xf2a585, fogD: 0.0065, top: 0x9a6ac0, horizon: 0xffa27a, glow: 0xffd2a0, haze: 0.9, stars: 0, exposure: 1.02, night: 0, warm: 0.7, sat: 1.15, fillI: 0.3, sunSize: 700 },
  sunset: { sunPow: 0.4, sun: [0.05, 0.085, 0.995], sunCol: 0xff9550, sunI: 3.2, hemiSky: 0xd88aa0, hemiGround: 0x4a3030, hemiI: 0.95, fog: 0xe8907a, fogD: 0.007, top: 0x7a58b0, horizon: 0xff9a74, glow: 0xffc490, haze: 1.0, stars: 0, exposure: 1.05, night: 0, warm: 0.85, sat: 1.15, fillI: 0.28, sunSize: 600 },
  dusk: { sun: [0.05, 0.03, 0.998], sunCol: 0xff7a40, sunI: 1.6, hemiSky: 0x8a6aa8, hemiGround: 0x2a2030, hemiI: 0.8, fog: 0x8a6090, fogD: 0.008, top: 0x34306e, horizon: 0xd8707a, glow: 0xff9a70, haze: 0.8, stars: 0.3, exposure: 1.1, night: 0.6, warm: 0.4, sat: 1.12, fillI: 0.25, sunSize: 600 },
  night: { sun: [-0.35, 0.6, -0.55], sunCol: 0xa8bcff, sunI: 1.35, hemiSky: 0x3a52a0, hemiGround: 0x22243a, hemiI: 1.05, fog: 0x14204a, fogD: 0.008, top: 0x0c1a4e, horizon: 0x2a4290, glow: 0x3a4a9a, haze: 0.2, stars: 1, exposure: 1.3, night: 1, warm: 0, sat: 1.08, fillI: 0.22, sunSize: 3000 },
  interior: { sun: [0.2, 0.9, 0.3], sunCol: 0xffffff, sunI: 0.0, hemiSky: 0xf2f4ff, hemiGround: 0x9a9890, hemiI: 2.2, fog: 0xdde6f0, fogD: 0.002, top: 0x8ab8f0, horizon: 0xeef6ff, glow: 0xffffff, haze: 0.1, stars: 0, exposure: 1.0, night: 0, warm: 0.05, sat: 1.1, fillI: 0.5, sunSize: 1200 },
};
