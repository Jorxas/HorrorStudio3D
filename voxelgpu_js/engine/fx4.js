// Effets v4 : pluie (traits), neige, braises qui montent, poussière ; reflet planaire générique (sol mouillé, flaque
// noire, glace) avec ondes de gouttes ; vitre ruisselante ; brume colorée en couches.
import * as THREE from 'three';
import { mulberry } from './textures.js';
const V = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);

// ------------------------------------------------------------------ particules autour de la caméra
// kind: 'rain' (traits verticaux), 'snow', 'embers' (montent, lumineuses), 'dust'
export function buildParticles(scene, kind, count, seed = 1) {
  const r = mulberry(seed); const pos = new Float32Array(count * 3), rnd = new Float32Array(count * 4);
  for (let i = 0; i < count; i++) { pos.set([r(), r(), r()], i * 3); rnd.set([r(), r(), r(), r()], i * 4); }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(pos, 3)); g.setAttribute('aRnd', new THREE.BufferAttribute(rnd, 4));
  const K = { rain: 0, snow: 1, embers: 2, dust: 3 }[kind];
  const mat = new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 }, uCam: { value: V() }, uBox: { value: V(24, 16, 24) }, uWind: { value: V(0.3, 0, 0.1) }, uSpeed: { value: 1 }, uSize: { value: 1 }, uScale: { value: 1 }, uInt: { value: 0 }, uCol: { value: new THREE.Color(1, 1, 1) }, uMinY: { value: -1e9 }, uClip: { value: new THREE.Vector4(-1e9, -1e9, 1e9, 1e9) } },
    vertexShader: `attribute vec4 aRnd; uniform float uTime, uSpeed, uSize, uScale, uMinY; uniform vec3 uCam, uBox, uWind; uniform vec4 uClip; varying float vA; varying float vNear; varying float vTw;
      void main(){ vec3 p = position * uBox; float t = uTime * uSpeed;
        ${K === 0 ? 'vec3 off = vec3(uWind.x * t, -14.0 * (0.8 + aRnd.y * 0.4) * t, uWind.z * t);' : ''}
        ${K === 1 ? 'vec3 off = vec3(uWind.x * t + sin(uTime * (0.5 + aRnd.x) + aRnd.y * 6.28) * 0.4, -0.9 * (0.55 + aRnd.y * 0.9) * t, uWind.z * t + cos(uTime * 0.45 + aRnd.z * 6.28) * 0.35);' : ''}
        ${K === 2 ? 'vec3 off = vec3(sin(uTime * (0.8 + aRnd.x) + aRnd.y * 6.28) * 0.6 + uWind.x * t, (0.8 + aRnd.y * 1.6) * t, cos(uTime * (0.7 + aRnd.z) + aRnd.x * 6.28) * 0.6);' : ''}
        ${K === 3 ? 'vec3 off = vec3(sin(uTime * 0.2 + aRnd.y * 6.28) * 0.5, sin(uTime * 0.15 + aRnd.x * 6.28) * 0.3 + 0.05 * t, cos(uTime * 0.18 + aRnd.z * 6.28) * 0.5);' : ''}
        p = mod(p + off - uCam + uBox * 0.5, uBox) + uCam - uBox * 0.5;
        vA = (p.y < uMinY || p.x < uClip.x || p.z < uClip.y || p.x > uClip.z || p.z > uClip.w) ? 0.0 : 1.0;
        vec4 mv = modelViewMatrix * vec4(p, 1.0); gl_Position = projectionMatrix * mv; float d = -mv.z;
        float base = ${['3.0', '24.0', '20.0', '10.0'][K]};
        gl_PointSize = base * uSize * (0.5 + aRnd.w) * uScale / max(d, 0.3);
        vNear = smoothstep(2.0, 0.4, d); vA *= smoothstep(0.15, 0.6, d) * (1.0 - smoothstep(uBox.z * 0.38, uBox.z * 0.5, d));
        vTw = ${K === 2 ? '0.55 + 0.45 * sin(uTime * (3.0 + aRnd.x * 5.0) + aRnd.z * 30.0)' : '1.0'}; }`,
    fragmentShader: `uniform float uInt; uniform vec3 uCol; varying float vA; varying float vNear; varying float vTw;
      void main(){ vec2 q = gl_PointCoord - 0.5;
        ${K === 0 ? 'float a = (1.0 - smoothstep(0.03, 0.09, abs(q.x))) * (1.0 - smoothstep(0.25, 0.5, abs(q.y))) * 0.7;' : 'float d = length(q); float a = 1.0 - smoothstep(mix(0.2, 0.05, vNear), 0.5, d); a *= mix(1.0, 0.4, vNear);'}
        gl_FragColor = vec4(uCol * a * vA * vTw * uInt, 1.0); }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  });
  const pts = new THREE.Points(g, mat); pts.frustumCulled = false; pts.renderOrder = 8; pts.visible = false; scene.add(pts);
  return { pts, mat, set(cam, t, o = {}) { const u = mat.uniforms; u.uTime.value = t; u.uCam.value.copy(cam.position); u.uInt.value = o.i ?? 0; pts.visible = (o.i ?? 0) > 0.001; if (o.col !== undefined) u.uCol.value.set(o.col); if (o.size !== undefined) u.uSize.value = o.size; if (o.speed !== undefined) u.uSpeed.value = o.speed; if (o.box) u.uBox.value.copy(o.box); if (o.wind) u.uWind.value.copy(o.wind); u.uMinY.value = o.minY ?? -1e9; u.uClip.value.copy(o.clip ?? new THREE.Vector4(-1e9, -1e9, 1e9, 1e9)); u.uScale.value = o.scale ?? 1; } };
}

// ------------------------------------------------------------------ reflet planaire générique
// mesh horizontal (y constant) ; le shader mélange la couleur de base (texture), le reflet (flou + déformé par des ondes) et un fresnel.
export function buildReflector(renderer, W, H, opts = {}) {
  const rt = new THREE.WebGLRenderTarget(Math.floor(W / 2), Math.floor(H / 2), { type: THREE.HalfFloatType });
  const texM = new THREE.Matrix4(), bias = new THREE.Matrix4().set(0.5, 0, 0, 0.5, 0, 0.5, 0, 0.5, 0, 0, 0.5, 0.5, 0, 0, 0, 1);
  const vcam = new THREE.PerspectiveCamera();
  const mats = [];
  function makeMaterial(o = {}) {
    const m = new THREE.ShaderMaterial({
      uniforms: { tRef: { value: rt.texture }, uTexM: { value: texM }, tBase: { value: o.map ?? null }, uHasBase: { value: o.map ? 1 : 0 }, uBaseCol: { value: new THREE.Color(o.color ?? 0x101014) }, uTpm: { value: o.tpm ?? 0.5 },
        uRef: { value: o.reflect ?? 0.8 }, uRough: { value: o.rough ?? 0.004 }, uRipple: { value: o.ripple ?? 0.0 }, uTime: { value: 0 }, uGlit: { value: o.glitter ?? 0.0 }, uGlitCol: { value: new THREE.Color(o.glitterCol ?? 0xff5a40) }, uCam: { value: V() }, uTint: { value: new THREE.Color(o.tint ?? 0xffffff) }, uGlow: { value: new THREE.Color(o.glow ?? 0x000000) }, uFog: { value: new THREE.Color(0) }, uFogD: { value: 0 } },
      vertexShader: `uniform mat4 uTexM; varying vec4 vUvP; varying vec3 vW; varying float vDepth; void main(){ vec4 w = modelMatrix * vec4(position,1.0); vW = w.xyz; vUvP = uTexM * w; vec4 mv = viewMatrix * w; vDepth = -mv.z; gl_Position = projectionMatrix * mv; }`,
      fragmentShader: `uniform sampler2D tRef, tBase; uniform float uHasBase, uTpm, uRef, uRough, uRipple, uTime, uFogD, uGlit; uniform vec3 uBaseCol, uCam, uTint, uGlow, uFog, uGlitCol; varying vec4 vUvP; varying vec3 vW; varying float vDepth;
        float h(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
        vec2 ripples(vec2 p){ vec2 acc = vec2(0.0); for (int k = 0; k < 3; k++) { vec2 cell = floor(p * 1.6 + float(k) * 3.7); vec2 f = fract(p * 1.6 + float(k) * 3.7) - 0.5; float ph = h(cell + float(k)); float tt = fract(uTime * 0.9 + ph); vec2 c = vec2(h(cell + 1.3), h(cell + 2.7)) - 0.5; vec2 d = f - c * 0.6; float r = length(d); float ring = sin((r - tt * 0.5) * 60.0) * smoothstep(0.02, 0.0, abs(r - tt * 0.5)) * (1.0 - tt); acc += normalize(d + 1e-4) * ring; } return acc; }
        void main(){ vec2 uv = vUvP.xy / vUvP.w; vec2 rp = ripples(vW.xz) * uRipple; uv += rp * 0.02;
          vec3 r = vec3(0.0); for (int i = 0; i < 7; i++) { float a = float(i) * 0.8976; float rr = float(i > 0) * uRough * (1.0 + float(i) * 0.15); r += texture2D(tRef, uv + vec2(cos(a), sin(a)) * rr).rgb; } r /= 7.0;
          vec3 base = uBaseCol; if (uHasBase > 0.5) base *= texture2D(tBase, vW.xz * uTpm).rgb;
          vec3 v = normalize(uCam - vW); float fr = 0.35 + 0.65 * pow(1.0 - max(v.y, 0.0), 3.0);
          vec3 col = base + r * uTint * uRef * fr + uGlow;
          col += vec3(1.0) * length(rp) * 0.08;
          // paillettes : gouttelettes qui scintillent à la surface (densité forte, taille ~ quelques pixels)
          if (uGlit > 0.0) { for (int k = 0; k < 2; k++) { float sc = k == 0 ? 55.0 : 23.0; vec2 q = vW.xz * sc + float(k) * 17.3; vec2 cell = floor(q); float hh = h(cell + float(k) * 7.0);
            if (hh > 0.62) { vec2 f = fract(q) - 0.5 - (vec2(h(cell + 1.3), h(cell + 4.1)) - 0.5) * 0.5; float d = length(f);
              float tw = 0.3 + 0.7 * pow(0.5 + 0.5 * sin(uTime * (1.5 + hh * 6.0) + hh * 60.0), 4.0); float lum = dot(r, vec3(0.5, 0.3, 0.2));
              col += uGlitCol * uGlit * tw * smoothstep(0.22, 0.04, d) * (0.4 + 2.5 * (hh - 0.62)) * (0.35 + lum * 3.0) * (k == 0 ? 1.0 : 1.6); } } }
          col = mix(col, uFog, 1.0 - exp(-uFogD * uFogD * vDepth * vDepth));
          gl_FragColor = vec4(col, 1.0); }`,
    });
    mats.push(m); return m;
  }
  return {
    rt, makeMaterial,
    render(scene, camera, y0, hide = [], t = 0, fog) {
      for (const m of mats) { m.uniforms.uCam.value.copy(camera.position); m.uniforms.uTime.value = t; if (fog) { m.uniforms.uFog.value.copy(fog.color); m.uniforms.uFogD.value = fog.density; } }
      const p = camera.position; const look = V(0, 0, -1).applyQuaternion(camera.quaternion).add(p); const up = V(0, 1, 0).applyQuaternion(camera.quaternion);
      vcam.position.set(p.x, 2 * y0 - p.y, p.z); vcam.up.set(up.x, -up.y, up.z); vcam.lookAt(look.x, 2 * y0 - look.y, look.z);
      vcam.fov = camera.fov; vcam.aspect = camera.aspect; vcam.near = camera.near; vcam.far = camera.far; vcam.updateProjectionMatrix(); vcam.updateMatrixWorld();
      texM.copy(bias).multiply(vcam.projectionMatrix).multiply(vcam.matrixWorldInverse);
      // cache aussi tout mesh qui utilise un matériau de ce réflecteur (évite la boucle framebuffer/texture)
      const all = [...hide]; scene.traverse((o) => { if (o.isMesh && o.visible && mats.includes(o.material)) all.push(o); });
      const vis = all.map((o) => o.visible); all.forEach((o) => { o.visible = false; });
      const old = renderer.getRenderTarget(), cp = renderer.clippingPlanes;
      renderer.clippingPlanes = [new THREE.Plane(V(0, 1, 0), -y0 + 0.002)]; renderer.setRenderTarget(rt); renderer.clear(); renderer.render(scene, vcam);
      renderer.clippingPlanes = cp; renderer.setRenderTarget(old); all.forEach((o, i) => { o.visible = vis[i]; });
    },
  };
}

// ------------------------------------------------------------------ vitre ruisselante (pluie sur le verre) : couleur de l'extérieur + gouttes + traînées
export function rainGlassMaterial(o = {}) {
  return new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 }, uOut: { value: new THREE.Color(o.out ?? 0x2a0608) }, uOut2: { value: new THREE.Color(o.out2 ?? 0x8a1012) }, uDrop: { value: new THREE.Color(o.drop ?? 0xffd0d0) }, uInt: { value: 1 }, uPass: { value: 0 }, uPassCol: { value: new THREE.Color(o.pass ?? 0xffb060) }, uDrive: { value: 0 } },
    vertexShader: `varying vec2 vUv; varying vec3 vW; void main(){ vUv = uv; vW = (modelMatrix * vec4(position,1.0)).xyz; gl_Position = projectionMatrix * viewMatrix * vec4(vW, 1.0); }`,
    fragmentShader: `uniform float uTime, uInt, uPass, uDrive; uniform vec3 uOut, uOut2, uDrop, uPassCol; varying vec2 vUv; varying vec3 vW;
      float h(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
      void main(){ vec2 p = vec2(vW.x + vW.z, vW.y) * 8.0;
        vec3 col = mix(uOut, uOut2, smoothstep(0.0, 1.0, vUv.y) * 0.6 + 0.4 * h(floor(p * 0.25)));
        // traînées qui descendent
        float lane = floor(p.x * 0.7); float sp = 0.6 + h(vec2(lane, 1.0)) * 1.4; float yy = fract(p.y * 0.06 + uTime * sp * 0.25 + h(vec2(lane, 3.0)));
        float streak = step(0.75, h(vec2(lane, 7.0))) * smoothstep(0.2, 0.0, abs(fract(p.x * 0.7) - 0.5) - 0.1) * smoothstep(0.0, 0.5, yy) * (1.0 - smoothstep(0.85, 1.0, yy));
        // gouttes fixes (pixels)
        vec2 c = floor(p * 0.9); float drop = step(0.93, h(c + floor(uTime * 0.3 + h(c) * 5.0) * 0.01)) * (0.4 + 0.6 * h(c + 9.0));
        // lumières de la route qui défilent (lampadaires, vitrines)
        float zz = vW.z + uDrive; float band = fract(zz / 17.0); float lamp = smoothstep(0.12, 0.0, abs(band - 0.5)) * smoothstep(0.2, 0.9, vUv.y);
        float win = step(0.6, h(vec2(floor(zz / 3.0), 2.0))) * smoothstep(0.55, 0.5, vUv.y) * step(0.15, vUv.y) * step(0.3, fract(zz / 3.0));
        col += uPassCol * uPass * (lamp * 2.2 + win * 0.6 * (0.6 + 0.4 * h(vec2(floor(zz / 3.0), 5.0))));
        col += uDrop * (streak * 0.5 + drop * 0.55) * (1.0 + uPass * lamp * 2.0);
        gl_FragColor = vec4(col * uInt, 1.0); }`,
  });
}

// ------------------------------------------------------------------ nappes de brume (plans additifs qui dérivent)
export function buildMist(scene, n = 10, seed = 3) {
  const r = mulberry(seed); const mats = []; const meshes = [];
  for (let i = 0; i < n; i++) {
    const m = new THREE.ShaderMaterial({ uniforms: { uTime: { value: 0 }, uCol: { value: new THREE.Color(1, 0.1, 0.08) }, uInt: { value: 0 }, uSeed: { value: r() * 10 } },
      vertexShader: `varying vec2 vUv; varying float vD; void main(){ vUv = uv; vec4 mv = modelViewMatrix * vec4(position,1.0); vD = -mv.z; gl_Position = projectionMatrix * mv; }`,
      fragmentShader: `uniform float uTime, uInt, uSeed; uniform vec3 uCol; varying vec2 vUv; varying float vD;
        float h(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
        float n(vec2 p){ vec2 i=floor(p), f=fract(p); f=f*f*(3.0-2.0*f); return mix(mix(h(i),h(i+vec2(1,0)),f.x), mix(h(i+vec2(0,1)),h(i+vec2(1,1)),f.x), f.y); }
        void main(){ vec2 q = vUv * vec2(3.0, 1.5) + vec2(uTime * 0.05 + uSeed, uSeed); float a = n(q) * 0.6 + n(q * 2.3) * 0.4; a *= smoothstep(0.0, 0.35, vUv.y) * (1.0 - smoothstep(0.55, 1.0, vUv.y)) * smoothstep(0.0, 0.2, vUv.x) * (1.0 - smoothstep(0.8, 1.0, vUv.x));
          a *= smoothstep(0.5, 3.0, vD); gl_FragColor = vec4(uCol * a * uInt, 1.0); }`,
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide });
    const me = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), m); me.visible = false; me.renderOrder = 7; scene.add(me); mats.push(m); meshes.push(me);
  }
  return { meshes, set(list, t, col, i) { meshes.forEach((me, k) => { const d = list[k]; if (!d || i <= 0) { me.visible = false; return; } me.visible = true; me.position.copy(d.pos); me.scale.set(d.w, d.h, 1); me.rotation.set(0, d.yaw ?? 0, 0); const u = mats[k].uniforms; u.uTime.value = t; u.uCol.value.set(col); u.uInt.value = i * (d.k ?? 1); }); } };
}
