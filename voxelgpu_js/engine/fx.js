import * as THREE from 'three';
import { FullScreenQuad } from 'three/addons/postprocessing/Pass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { mulberry } from './textures.js';

// ------------------------------------------------------------- sky
export function buildSky(scene) {
  const mat = new THREE.ShaderMaterial({
    uniforms: { sunDir: { value: new THREE.Vector3(0, 1, 0) }, top: { value: new THREE.Color(0x3d8fe6) }, horizon: { value: new THREE.Color(0xd8f0ff) }, sunCol: { value: new THREE.Color(1.0, 0.92, 0.75) }, sunPower: { value: 1.0 } },
    vertexShader: `varying vec3 vDir; void main(){ vDir = normalize(position); vec4 p = projectionMatrix * modelViewMatrix * vec4(position,1.0); gl_Position = p.xyww; }`,
    fragmentShader: `uniform vec3 sunDir, top, horizon, sunCol; uniform float sunPower; varying vec3 vDir;
      void main(){ vec3 d = normalize(vDir); float h = clamp(d.y, 0.0, 1.0);
        vec3 col = mix(horizon, top, pow(h, 0.55));
        float s = max(dot(d, normalize(sunDir)), 0.0);
        col = mix(col, vec3(1.0,0.95,0.85), pow(s, 6.0)*0.55);
        col += sunCol * (pow(s, 900.0) * 40.0 + pow(s, 60.0) * 1.2 + pow(s, 8.0) * 0.25) * sunPower;
        if (d.y < 0.0) col = mix(horizon, vec3(0.55,0.68,0.5), clamp(-d.y*3.0,0.0,1.0));
        gl_FragColor = vec4(col, 1.0); }`,
    side: THREE.BackSide, depthWrite: false,
  });
  const m = new THREE.Mesh(new THREE.SphereGeometry(400, 32, 16), mat); m.frustumCulled = false; m.renderOrder = -10;
  scene.add(m); return m;
}

// ------------------------------------------------------------- volumetric light shafts (axis billboards)
export function buildShafts(scene, sunDir, list, opts = {}) {
  const mat = new THREE.ShaderMaterial({
    uniforms: { uInt: { value: 1.0 }, uCol: { value: new THREE.Color(opts.color ?? 0xffe6a0) }, uTime: { value: 0 }, uFadeIn: { value: opts.fadeIn ?? 0.35 }, uFadeOut: { value: opts.fadeOut ?? 0.55 } },
    vertexShader: `varying vec2 vUv; varying float vViewZ; void main(){ vUv = uv; vec4 mv = modelViewMatrix * vec4(position,1.0); vViewZ = -mv.z; gl_Position = projectionMatrix * mv; }`,
    fragmentShader: `uniform float uInt, uTime, uFadeIn, uFadeOut; uniform vec3 uCol; varying vec2 vUv; varying float vViewZ;
      void main(){ float x = (vUv.x - 0.5) * 2.0; float a = exp(-x*x*3.0);
        a *= smoothstep(0.0, uFadeIn, vUv.y) * (1.0 - smoothstep(uFadeOut, 1.0, vUv.y));
        a *= 0.75 + 0.25 * sin(vUv.y * 7.0 + uTime * 0.6 + x * 2.0);
        a *= smoothstep(1.0, 4.0, vViewZ);
        gl_FragColor = vec4(uCol * a * uInt, 1.0); }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
  });
  const geo = new THREE.PlaneGeometry(1, 1);
  const shafts = [];
  for (const s of list) {
    const m = new THREE.Mesh(geo, mat); m.frustumCulled = false; m.renderOrder = 5;
    m.userData = s; shafts.push(m); scene.add(m);
  }
  const axis = sunDir.clone().normalize();
  const tmp = new THREE.Vector3(), X = new THREE.Vector3(), Z = new THREE.Vector3(), M = new THREE.Matrix4();
  return {
    mat, shafts,
    update(camera, intensity, t) {
      mat.uniforms.uInt.value = intensity; mat.uniforms.uTime.value = t;
      for (const m of shafts) {
        const { x, z, ground, len, width, w } = m.userData;
        const bottom = new THREE.Vector3(x, ground, z);
        const center = bottom.clone().addScaledVector(axis, len * 0.5);
        tmp.copy(camera.position).sub(center);
        Z.copy(tmp).addScaledVector(axis, -tmp.dot(axis)).normalize();
        X.crossVectors(axis, Z).normalize();
        M.makeBasis(X.clone().multiplyScalar(width), axis.clone().multiplyScalar(len), Z);
        M.setPosition(center);
        m.matrixAutoUpdate = false; m.matrix.copy(M); m.matrixWorldNeedsUpdate = true;
        m.visible = intensity > 0.001 && (w === undefined || w > 0);
      }
    }
  };
}

// ------------------------------------------------------------- particles (dust motes / fireflies)
export function buildMotes(scene, count, seed, opts) {
  const r = mulberry(seed);
  const pos = new Float32Array(count * 3), rnd = new Float32Array(count * 4);
  for (let i = 0; i < count; i++) { pos[i * 3] = r(); pos[i * 3 + 1] = r(); pos[i * 3 + 2] = r(); rnd[i * 4] = r(); rnd[i * 4 + 1] = r(); rnd[i * 4 + 2] = r(); rnd[i * 4 + 3] = r(); }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(pos, 3)); g.setAttribute('aRnd', new THREE.BufferAttribute(rnd, 4));
  const mat = new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 }, uMin: { value: new THREE.Vector3() }, uSize: { value: new THREE.Vector3(10, 6, 10) }, uCol: { value: new THREE.Color(opts.color) }, uPt: { value: opts.size }, uScale: { value: 1 }, uInt: { value: 1 }, uBlink: { value: opts.blink ? 1 : 0 } },
    vertexShader: `attribute vec4 aRnd; uniform float uTime, uPt, uScale, uBlink; uniform vec3 uMin, uSize; varying float vA;
      void main(){ vec3 p = position;
        p.x += sin(uTime*(0.3+aRnd.x*0.5) + aRnd.y*6.28)*0.04;
        p.z += cos(uTime*(0.25+aRnd.z*0.5) + aRnd.x*6.28)*0.04;
        p.y = fract(p.y + uTime*(0.006 + aRnd.w*0.012)*(uBlink>0.5?0.3:1.0) + sin(uTime*0.7+aRnd.z*6.0)*0.01);
        vec3 wp = uMin + p * uSize;
        vec4 mv = modelViewMatrix * vec4(wp, 1.0);
        gl_Position = projectionMatrix * mv;
        float tw = uBlink > 0.5 ? smoothstep(0.2, 1.0, sin(uTime*(1.5+aRnd.y*2.0) + aRnd.x*30.0)*0.5+0.5) : (0.6 + 0.4*sin(uTime*2.0+aRnd.w*20.0));
        vA = tw * smoothstep(0.0,0.08,p.y) * (1.0 - smoothstep(0.9,1.0,p.y)) * smoothstep(0.4, 1.5, -mv.z);
        gl_PointSize = uPt * (0.5 + aRnd.z) * uScale / max(-mv.z, 0.1); }`,
    fragmentShader: `uniform vec3 uCol; uniform float uInt; varying float vA; void main(){ vec2 c = gl_PointCoord - 0.5; float d = length(c); float a = 1.0 - smoothstep(0.0, 0.5, d); a = a*a; gl_FragColor = vec4(uCol * a * vA * uInt, 1.0); }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  });
  const pts = new THREE.Points(g, mat); pts.frustumCulled = false; pts.renderOrder = 6; scene.add(pts);
  return { pts, mat, set(min, size, t, scale, intensity) { mat.uniforms.uMin.value.copy(min); mat.uniforms.uSize.value.copy(size); mat.uniforms.uTime.value = t; mat.uniforms.uScale.value = scale; mat.uniforms.uInt.value = intensity; pts.visible = intensity > 0.001; } };
}

// ------------------------------------------------------------- falling leaves
export function buildFallingLeaves(scene, count, seed) {
  const r = mulberry(seed);
  const geo = new THREE.PlaneGeometry(0.16, 0.16);
  const mat = new THREE.MeshLambertMaterial({ color: 0x6fbf3f, side: THREE.DoubleSide });
  const mat2 = new THREE.MeshLambertMaterial({ color: 0x9fd257, side: THREE.DoubleSide });
  const im = new THREE.InstancedMesh(geo, mat, count); const im2 = new THREE.InstancedMesh(geo, mat2, count);
  im.castShadow = false; im2.castShadow = false; im.frustumCulled = false; im2.frustumCulled = false;
  const data = []; for (let i = 0; i < count * 2; i++) data.push([r(), r(), r(), r(), r()]);
  scene.add(im); scene.add(im2);
  const o = new THREE.Object3D();
  return {
    set(min, size, t, on) {
      im.visible = im2.visible = on;
      if (!on) return;
      for (let i = 0; i < count * 2; i++) {
        const [a, b, c, d, e] = data[i];
        const y = 1 - ((b + t * (0.05 + d * 0.05)) % 1);
        o.position.set(min.x + (a + Math.sin(t * 0.8 + e * 9) * 0.03) * size.x, min.y + y * size.y, min.z + (c + Math.cos(t * 0.7 + d * 9) * 0.03) * size.z);
        o.rotation.set(t * (1 + e) + a * 9, t * (0.7 + d) + b * 5, t * 0.5 + c * 7);
        o.updateMatrix();
        (i < count ? im : im2).setMatrixAt(i % count, o.matrix);
      }
      im.instanceMatrix.needsUpdate = true; im2.instanceMatrix.needsUpdate = true;
    }
  };
}

// ------------------------------------------------------------- post pipeline
export function buildPost(renderer, W, H) {
  const hf = THREE.HalfFloatType;
  const depthTex = new THREE.DepthTexture(W, H); depthTex.type = THREE.UnsignedIntType;
  const rtScene = new THREE.WebGLRenderTarget(W, H, { type: hf, samples: (window.MSAA ?? 4), depthTexture: depthTex });
  const hw = Math.floor(W / 2), hh = Math.floor(H / 2);
  const rtDof = new THREE.WebGLRenderTarget(W, H, { type: hf });
  const rtDofHalf = new THREE.WebGLRenderTarget(hw, hh, { type: hf }); rtDofHalf.texture.minFilter = rtDofHalf.texture.magFilter = THREE.LinearFilter;
  const rtMask = new THREE.WebGLRenderTarget(hw, hh, { type: hf });
  const rtRays = new THREE.WebGLRenderTarget(hw, hh, { type: hf });
  const bloom = new UnrealBloomPass(new THREE.Vector2(W, H), 0.55, 0.6, 1.0);

  const dofMat = new THREE.ShaderMaterial({
    uniforms: { tColor: { value: null }, tDepth: { value: null }, uNear: { value: 0.1 }, uFar: { value: 500 }, uFocus: { value: 5 }, uScale: { value: 1 }, uMaxBlur: { value: 12 }, uPx: { value: new THREE.Vector2(1 / W, 1 / H) } },
    vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`,
    fragmentShader: `uniform sampler2D tColor, tDepth; uniform float uNear, uFar, uFocus, uScale, uMaxBlur; uniform vec2 uPx; varying vec2 vUv;
      float lin(float d){ return (uNear*uFar)/(uFar - d*(uFar-uNear)); }
      float coc(float z){ return clamp(abs(1.0/uFocus - 1.0/z) * uScale, 0.0, 1.0) * uMaxBlur; }
      void main(){
        vec4 c0 = texture2D(tColor, vUv); float cz = c0.a; float cs = coc(cz);
        vec3 col = c0.rgb; float tot = 1.0;
        if (uMaxBlur < 0.5) { gl_FragColor = vec4(col,1.0); return; }
        for (int i = 0; i < 28; i++) {
          float fi = float(i);
          float radius = sqrt((fi + 0.5) / 28.0) * uMaxBlur;
          float ang = fi * 2.39996323;
          vec2 tc = vUv + vec2(cos(ang), sin(ang)) * uPx * radius;
          vec4 s4 = texture2D(tColor, tc); vec3 sc = s4.rgb; float sz = s4.a; float ss = coc(sz);
          if (sz > cz) ss = clamp(ss, 0.0, cs * 2.0);
          float m = smoothstep(radius - 1.0, radius + 1.0, ss);
          col += mix(col / tot, sc, m); tot += 1.0;
        }
        gl_FragColor = vec4(col / tot, 1.0);
      }`,
    depthTest: false, depthWrite: false,
  });
  const rtPrep = new THREE.WebGLRenderTarget(hw, hh, { type: hf }); rtPrep.texture.minFilter = rtPrep.texture.magFilter = THREE.NearestFilter;
  const prepMat = new THREE.ShaderMaterial({
    uniforms: { tColor: { value: null }, tDepth: { value: null }, uNear: { value: 0.1 }, uFar: { value: 500 } },
    vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`,
    fragmentShader: `uniform sampler2D tColor, tDepth; uniform float uNear, uFar; varying vec2 vUv;
      void main(){ float d = texture2D(tDepth, vUv).r; gl_FragColor = vec4(texture2D(tColor, vUv).rgb, (uNear*uFar)/(uFar - d*(uFar-uNear))); }`,
    depthTest: false, depthWrite: false,
  });
  const compMat = new THREE.ShaderMaterial({
    uniforms: { tColor: { value: null }, tBlur: { value: null }, tDepth: { value: null }, uNear: { value: 0.1 }, uFar: { value: 500 }, uFocus: { value: 5 }, uScale: { value: 1 }, uMaxBlur: { value: 12 } },
    vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`,
    fragmentShader: `uniform sampler2D tColor, tBlur, tDepth; uniform float uNear, uFar, uFocus, uScale, uMaxBlur; varying vec2 vUv;
      float lin(float d){ return (uNear*uFar)/(uFar - d*(uFar-uNear)); }
      void main(){ float z = lin(texture2D(tDepth, vUv).r); float cs = clamp(abs(1.0/uFocus - 1.0/z) * uScale, 0.0, 1.0) * uMaxBlur;
        vec3 sharp = texture2D(tColor, vUv).rgb; vec3 bl = texture2D(tBlur, vUv).rgb;
        gl_FragColor = vec4(mix(sharp, bl, smoothstep(0.6, 2.2, cs)), 1.0); }`,
    depthTest: false, depthWrite: false,
  });
  const maskMat = new THREE.ShaderMaterial({
    uniforms: { tColor: { value: null }, tDepth: { value: null }, uSun: { value: new THREE.Vector2(0.5, 0.5) }, uAspect: { value: W / H } },
    vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`,
    fragmentShader: `uniform sampler2D tColor, tDepth; uniform vec2 uSun; uniform float uAspect; varying vec2 vUv;
      void main(){ float d = texture2D(tDepth, vUv).r; float sky = step(0.99999, d);
        vec3 c = texture2D(tColor, vUv).rgb; vec2 dv = (vUv - uSun) * vec2(uAspect, 1.0); float fall = exp(-dot(dv,dv) * 3.0);
        gl_FragColor = vec4(min(c, vec3(6.0)) * sky * (0.25 + fall), 1.0); }`,
    depthTest: false, depthWrite: false,
  });
  const raysMat = new THREE.ShaderMaterial({
    uniforms: { tMask: { value: null }, uSun: { value: new THREE.Vector2(0.5, 0.5) } },
    vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`,
    fragmentShader: `uniform sampler2D tMask; uniform vec2 uSun; varying vec2 vUv;
      void main(){ vec2 delta = (vUv - uSun) * (0.92 / 56.0); vec2 c = vUv; float il = 1.0; vec3 acc = vec3(0.0);
        for (int i = 0; i < 56; i++) { c -= delta; acc += texture2D(tMask, c).rgb * il; il *= 0.965; }
        gl_FragColor = vec4(acc / 56.0, 1.0); }`,
    depthTest: false, depthWrite: false,
  });
  const finalMat = new THREE.ShaderMaterial({
    uniforms: { tColor: { value: null }, tRays: { value: null }, uRays: { value: 0 }, uExposure: { value: 1 }, uSat: { value: 1.12 }, uVig: { value: 0.35 }, uTime: { value: 0 }, uRes: { value: new THREE.Vector2(W, H) }, uWarm: { value: 0.0 }, uFade: { value: 1.0 }, uDistort: { value: 0.0 }, uPeep: { value: 0.0 }, uGrain: { value: 0.018 }, uTint: { value: new THREE.Vector3(1, 1, 1) }, uLift: { value: new THREE.Vector3(0.012, 0.018, 0.02) } },
    vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`,
    fragmentShader: `uniform sampler2D tColor, tRays; uniform float uRays, uExposure, uSat, uVig, uTime, uWarm, uFade, uDistort, uPeep, uGrain; uniform vec2 uRes; uniform vec3 uLift, uTint; varying vec2 vUv;
      vec3 aces(vec3 x){ const float a=2.51, b=0.03, c=2.43, d=0.59, e=0.14; return clamp((x*(a*x+b))/(x*(c*x+d)+e), 0.0, 1.0); }
      float hash(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233))) * 43758.5453); }
      vec3 toSRGB(vec3 c){ return mix(c*12.92, 1.055*pow(c, vec3(1.0/2.4)) - 0.055, step(0.0031308, c)); }
      void main(){
        vec2 cc = (vUv - 0.5); vec2 ccA = cc * vec2(uRes.x / uRes.y, 1.0); float r2 = dot(ccA, ccA);
        vec2 uv = 0.5 + cc * (1.0 + uDistort * r2) / (1.0 + uDistort * 0.32);
        vec2 ca = (uv - 0.5) * 0.0018;
        vec3 c; c.r = texture2D(tColor, uv + ca).r; c.g = texture2D(tColor, uv).g; c.b = texture2D(tColor, uv - ca).b;
        c += texture2D(tRays, uv).rgb * uRays * vec3(1.0, 0.9, 0.7);
        c *= uTint;
        c *= uExposure;
        c *= mix(vec3(1.0), vec3(1.06, 1.0, 0.9), uWarm);
        c = aces(c);
        float l = dot(c, vec3(0.2126, 0.7152, 0.0722)); c = mix(vec3(l), c, uSat);
        c = toSRGB(clamp(c, 0.0, 1.0));
        c = c + uLift * (1.0 - c);
        c = mix(c, c*c*(3.0-2.0*c), 0.18);
        vec2 v = (vUv - 0.5) * vec2(0.85, 1.0); c *= 1.0 - uVig * pow(length(v) * 1.35, 2.6);
        c += (hash(vUv * uRes + fract(uTime) * 100.0) - 0.5) * uGrain;
        if (uPeep > 0.0) { float pr = length(ccA); c *= mix(1.0, 1.0 - smoothstep(0.255, 0.275, pr), uPeep); c *= mix(1.0, 1.0 - 0.6 * smoothstep(0.12, 0.27, pr), uPeep); }
        c *= uFade;
        gl_FragColor = vec4(c, 1.0); }`,
    depthTest: false, depthWrite: false,
  });
  const quad = new FullScreenQuad(null);
  const blackTex = new THREE.DataTexture(new Uint8Array([0, 0, 0, 255]), 1, 1); blackTex.needsUpdate = true;

  return {
    rtScene, bloom, finalMat, dofMat, rtDof,
    render(scene, camera, P) {
      renderer.setRenderTarget(rtScene); renderer.clear(); renderer.render(scene, camera);
      // DOF
      prepMat.uniforms.tColor.value = rtScene.texture; prepMat.uniforms.tDepth.value = rtScene.depthTexture; prepMat.uniforms.uNear.value = camera.near; prepMat.uniforms.uFar.value = camera.far;
      quad.material = prepMat; renderer.setRenderTarget(rtPrep); quad.render(renderer);
      dofMat.uniforms.tColor.value = rtPrep.texture;
      dofMat.uniforms.uNear.value = camera.near; dofMat.uniforms.uFar.value = camera.far;
      const mb = P.maxBlur * (H / 1280);
      dofMat.uniforms.uFocus.value = P.focus; dofMat.uniforms.uScale.value = P.dofScale; dofMat.uniforms.uMaxBlur.value = mb * 0.5;
      dofMat.uniforms.uPx.value.set(1 / hw, 1 / hh);
      quad.material = dofMat; renderer.setRenderTarget(rtDofHalf); quad.render(renderer);
      const cu = compMat.uniforms; cu.tColor.value = rtScene.texture; cu.tBlur.value = rtDofHalf.texture; cu.tDepth.value = rtScene.depthTexture;
      cu.uNear.value = camera.near; cu.uFar.value = camera.far; cu.uFocus.value = P.focus; cu.uScale.value = P.dofScale; cu.uMaxBlur.value = mb;
      quad.material = compMat; renderer.setRenderTarget(rtDof); quad.render(renderer);
      // god rays
      let raysOn = false;
      if (P.rays > 0.001 && P.sunScreen) {
        raysOn = true;
        maskMat.uniforms.tColor.value = rtScene.texture; maskMat.uniforms.tDepth.value = rtScene.depthTexture; maskMat.uniforms.uSun.value.copy(P.sunScreen);
        quad.material = maskMat; renderer.setRenderTarget(rtMask); quad.render(renderer);
        raysMat.uniforms.tMask.value = rtMask.texture; raysMat.uniforms.uSun.value.copy(P.sunScreen);
        quad.material = raysMat; renderer.setRenderTarget(rtRays); quad.render(renderer);
      }
      // bloom (adds into rtDof)
      bloom.strength = P.bloom; bloom.radius = P.bloomRadius ?? 0.6; bloom.threshold = P.bloomThreshold ?? 1.0;
      bloom.render(renderer, null, rtDof, 0, false);
      // final
      const u = finalMat.uniforms; u.tColor.value = rtDof.texture; u.tRays.value = raysOn ? rtRays.texture : blackTex; u.uRays.value = P.rays;
      u.uExposure.value = P.exposure; u.uSat.value = P.sat ?? 1.12; u.uVig.value = P.vignette ?? 0.35; u.uTime.value = P.t; u.uWarm.value = P.warm ?? 0; u.uFade.value = P.fade ?? 1; u.uDistort.value = P.distort ?? 0; u.uPeep.value = P.peep ?? 0; u.uGrain.value = P.grain ?? 0.018; if (P.tint) u.uTint.value.set(...P.tint); else u.uTint.value.set(1, 1, 1);
      quad.material = finalMat; renderer.setRenderTarget(null); quad.render(renderer);
    }
  };
}
