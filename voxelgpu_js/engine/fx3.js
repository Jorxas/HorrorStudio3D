// Post-traitement v3 (module musique) : profondeur de champ, flou de mouvement de caméra (reprojection
// avec la caméra de l'image précédente), halo, étalonnage en deux tons (ombres / hautes lumières),
// aberration chromatique réglable, flash blanc, fondu, bandes cinéma, grain.
import * as THREE from 'three';
import { FullScreenQuad } from 'three/addons/postprocessing/Pass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';

const VS = `varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`;
const mk = (uniforms, fs) => new THREE.ShaderMaterial({ uniforms, vertexShader: VS, fragmentShader: fs, depthTest: false, depthWrite: false });

export function buildPost3(renderer, W, H) {
  const hf = THREE.HalfFloatType;
  const depthTex = new THREE.DepthTexture(W, H); depthTex.type = THREE.UnsignedIntType;
  const rtScene = new THREE.WebGLRenderTarget(W, H, { type: hf, samples: (window.MSAA ?? 4), depthTexture: depthTex });
  const hw = Math.floor(W / 2), hh = Math.floor(H / 2);
  const rtPrep = new THREE.WebGLRenderTarget(hw, hh, { type: hf }); rtPrep.texture.minFilter = rtPrep.texture.magFilter = THREE.NearestFilter;
  const rtHalf = new THREE.WebGLRenderTarget(hw, hh, { type: hf }); rtHalf.texture.minFilter = rtHalf.texture.magFilter = THREE.LinearFilter;
  const rtDof = new THREE.WebGLRenderTarget(W, H, { type: hf }), rtMB = new THREE.WebGLRenderTarget(W, H, { type: hf });
  const bloom = new UnrealBloomPass(new THREE.Vector2(W, H), 0.6, 0.6, 1.0);
  const quad = new FullScreenQuad(null);
  const LIN = `uniform float uNear, uFar; float lin(float d){ return (uNear*uFar)/(uFar - d*(uFar-uNear)); }`;
  const prep = mk({ tColor: { value: null }, tDepth: { value: null }, uNear: { value: 0.1 }, uFar: { value: 500 } },
    `uniform sampler2D tColor, tDepth; ${LIN} varying vec2 vUv; void main(){ gl_FragColor = vec4(texture2D(tColor, vUv).rgb, lin(texture2D(tDepth, vUv).r)); }`);
  const dof = mk({ tColor: { value: null }, uFocus: { value: 5 }, uScale: { value: 1 }, uMaxBlur: { value: 12 }, uPx: { value: new THREE.Vector2(1 / hw, 1 / hh) } },
    `uniform sampler2D tColor; uniform float uFocus, uScale, uMaxBlur; uniform vec2 uPx; varying vec2 vUv;
     float coc(float z){ return clamp(abs(1.0/uFocus - 1.0/z) * uScale, 0.0, 1.0) * uMaxBlur; }
     void main(){ vec4 c0 = texture2D(tColor, vUv); float cz = c0.a; float cs = coc(cz); vec3 col = c0.rgb; float tot = 1.0;
       if (uMaxBlur < 0.5) { gl_FragColor = vec4(col,1.0); return; }
       for (int i = 0; i < 32; i++) { float fi = float(i); float r = sqrt((fi + 0.5) / 32.0) * uMaxBlur; float a = fi * 2.39996323;
         vec4 s4 = texture2D(tColor, vUv + vec2(cos(a), sin(a)) * uPx * r); float ss = coc(s4.a); if (s4.a > cz) ss = clamp(ss, 0.0, cs * 2.0);
         float m = smoothstep(r - 1.0, r + 1.0, ss); col += mix(col / tot, s4.rgb, m); tot += 1.0; }
       gl_FragColor = vec4(col / tot, 1.0); }`);
  const comp = mk({ tColor: { value: null }, tBlur: { value: null }, tDepth: { value: null }, uNear: { value: 0.1 }, uFar: { value: 500 }, uFocus: { value: 5 }, uScale: { value: 1 }, uMaxBlur: { value: 12 } },
    `uniform sampler2D tColor, tBlur, tDepth; uniform float uFocus, uScale, uMaxBlur; ${LIN} varying vec2 vUv;
     void main(){ float z = lin(texture2D(tDepth, vUv).r); float cs = clamp(abs(1.0/uFocus - 1.0/z) * uScale, 0.0, 1.0) * uMaxBlur;
       gl_FragColor = vec4(mix(texture2D(tColor, vUv).rgb, texture2D(tBlur, vUv).rgb, smoothstep(0.6, 2.2, cs)), 1.0); }`);
  // liseré néon (v4) : les bords d'un objet devant un fond plus lointain reçoivent une lueur colorée (HDR -> halo)
  const rtEdge = new THREE.WebGLRenderTarget(W, H, { type: hf });
  const edge = mk({ tColor: { value: null }, tDepth: { value: null }, uNear: { value: 0.1 }, uFar: { value: 500 }, uPx: { value: new THREE.Vector2(1 / W, 1 / H) }, uCol: { value: new THREE.Color(1, 0.1, 0.05) }, uStr: { value: 2 }, uRad: { value: 2 }, uThr: { value: 0.12 }, uMaxD: { value: 30 }, uLum: { value: 0.0 }, uWrap: { value: 0.0 } },
    `uniform sampler2D tColor, tDepth; uniform vec2 uPx; uniform vec3 uCol; uniform float uStr, uRad, uThr, uMaxD, uLum, uWrap; ${LIN} varying vec2 vUv;
     void main(){ vec3 c = texture2D(tColor, vUv).rgb; float zc = lin(texture2D(tDepth, vUv).r); float e = 0.0; vec3 wrap = vec3(0.0); float wn = 0.0;
       for (int i = 0; i < 8; i++) { float a = float(i) * 0.785398; vec2 d = vec2(cos(a), sin(a));
         vec2 u1 = vUv + d * uPx * uRad, u2 = vUv + d * uPx * uRad * 0.5;
         float z1 = lin(texture2D(tDepth, u1).r), z2 = lin(texture2D(tDepth, u2).r);
         float e1 = clamp((z1 - zc) / zc - uThr, 0.0, 1.0), e2 = 0.7 * clamp((z2 - zc) / zc - uThr, 0.0, 1.0);
         e = max(e, max(e1, e2)); float w = step(0.001, e1); wrap += texture2D(tColor, vUv + d * uPx * uRad * 2.5).rgb * w; wn += w; }
       e = smoothstep(0.0, 0.3, e) * (1.0 - smoothstep(uMaxD * 0.4, uMaxD, zc)) * smoothstep(0.45, 1.3, zc);
       wrap /= max(wn, 1.0);
       float l = dot(c, vec3(0.3, 0.5, 0.2)); c += uCol * uStr * e * mix(1.0, clamp(0.3 + l * 2.0, 0.0, 1.5), uLum);
       c += wrap * uWrap * e;
       gl_FragColor = vec4(c, 1.0); }`);
  // flou de mouvement : chaque pixel est reprojeté avec la caméra de l'instant précédent
  const mblur = mk({ tColor: { value: null }, tDepth: { value: null }, uInvVP: { value: new THREE.Matrix4() }, uPrevVP: { value: new THREE.Matrix4() }, uAmt: { value: 0 }, uDebug: { value: 0 } },
    `uniform sampler2D tColor, tDepth; uniform mat4 uInvVP, uPrevVP; uniform float uAmt, uDebug; varying vec2 vUv;
     void main(){ float d = texture2D(tDepth, vUv).r; vec4 cp = vec4(vUv * 2.0 - 1.0, d * 2.0 - 1.0, 1.0); vec4 wp = uInvVP * cp; wp /= wp.w;
       vec4 pp = uPrevVP * wp; vec2 puv = (pp.xy / pp.w) * 0.5 + 0.5; vec2 vel = (vUv - puv) * uAmt;
       float L = length(vel); if (L > 0.045) vel *= 0.045 / L;
       if (uDebug > 0.5) { gl_FragColor = vec4(abs(vel) * 40.0, d > 0.99999 ? 1.0 : 0.0, 1.0); return; }
       vec3 acc = vec3(0.0); for (int i = 0; i < 10; i++) { float k = float(i) / 9.0 - 0.5; acc += texture2D(tColor, vUv + vel * k).rgb; }
       gl_FragColor = vec4(acc / 10.0, 1.0); }`);
  const fin = mk({ tColor: { value: null }, uExposure: { value: 1 }, uSat: { value: 1.05 }, uVig: { value: 0.4 }, uVigCol: { value: new THREE.Color(0, 0, 0) }, uTime: { value: 0 }, uRes: { value: new THREE.Vector2(W, H) },
      uShadow: { value: new THREE.Color(1, 1, 1) }, uHigh: { value: new THREE.Color(1, 1, 1) }, uContrast: { value: 0.12 }, uLift: { value: new THREE.Color(0, 0, 0) }, uCA: { value: 0.0015 }, uFlash: { value: 0 }, uFlashCol: { value: new THREE.Color(1, 1, 1) }, uFade: { value: 1 }, uBars: { value: 0 }, uGrain: { value: 0.03 }, uTint: { value: new THREE.Color(1, 1, 1) } },
    `uniform sampler2D tColor; uniform float uExposure, uSat, uVig, uTime, uContrast, uCA, uFlash, uFade, uBars, uGrain; uniform vec2 uRes; uniform vec3 uShadow, uHigh, uLift, uVigCol, uFlashCol, uTint; varying vec2 vUv;
     vec3 aces(vec3 x){ const float a=2.51, b=0.03, c=2.43, d=0.59, e=0.14; return clamp((x*(a*x+b))/(x*(c*x+d)+e), 0.0, 1.0); }
     float hash(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233))) * 43758.5453); }
     vec3 toSRGB(vec3 c){ return mix(c*12.92, 1.055*pow(c, vec3(1.0/2.4)) - 0.055, step(0.0031308, c)); }
     void main(){ vec2 cc = vUv - 0.5; vec2 ca = cc * uCA * (1.0 + dot(cc, cc) * 4.0);
       vec3 c; c.r = texture2D(tColor, vUv + ca).r; c.g = texture2D(tColor, vUv).g; c.b = texture2D(tColor, vUv - ca).b;
       c *= uTint * uExposure; c = aces(c);
       float l = dot(c, vec3(0.2126, 0.7152, 0.0722)); c = mix(vec3(l), c, uSat);
       c *= mix(uShadow, uHigh, smoothstep(0.05, 0.7, l));                 // étalonnage deux tons
       c = toSRGB(clamp(c, 0.0, 1.0)); c = c + uLift * (1.0 - c); c = mix(c, c*c*(3.0-2.0*c), uContrast);
       vec2 v = cc * vec2(uRes.x / uRes.y * 0.75, 1.0); c = mix(c, uVigCol, uVig * smoothstep(0.25, 0.95, length(v) * 1.25));
       c += (hash(vUv * uRes + fract(uTime * 7.0) * 100.0) - 0.5) * uGrain;
       c = mix(c, uFlashCol, uFlash); c *= uFade;
       if (abs(cc.y) > 0.5 - uBars) c = vec3(0.0);
       gl_FragColor = vec4(c, 1.0); }`);
  const pvp = new THREE.Matrix4();
  return {
    rtScene, bloom, fin,
    render(scene, camera, P, prevCam) {
      renderer.setRenderTarget(rtScene); renderer.clear(); renderer.render(scene, camera);
      let sceneTex = rtScene.texture;
      if (P.edge && P.edge.i > 0) { const e = edge.uniforms; e.tColor.value = rtScene.texture; e.tDepth.value = rtScene.depthTexture; e.uNear.value = camera.near; e.uFar.value = camera.far;
        e.uCol.value.set(P.edge.color ?? 0xff1a10); e.uStr.value = P.edge.i; e.uRad.value = (P.edge.rad ?? 2.2) * (H / 1280); e.uThr.value = P.edge.thr ?? 0.12; e.uMaxD.value = P.edge.maxD ?? 30; e.uLum.value = P.edge.lum ?? 0; e.uWrap.value = P.edge.wrap ?? 0;
        quad.material = edge; renderer.setRenderTarget(rtEdge); quad.render(renderer); sceneTex = rtEdge.texture; }
      Object.assign(prep.uniforms, {}); prep.uniforms.tColor.value = sceneTex; prep.uniforms.tDepth.value = rtScene.depthTexture; prep.uniforms.uNear.value = camera.near; prep.uniforms.uFar.value = camera.far;
      quad.material = prep; renderer.setRenderTarget(rtPrep); quad.render(renderer);
      const mb = (P.maxBlur ?? 10) * (H / 720);
      dof.uniforms.tColor.value = rtPrep.texture; dof.uniforms.uFocus.value = P.focus; dof.uniforms.uScale.value = P.dofScale; dof.uniforms.uMaxBlur.value = mb * 0.5;
      quad.material = dof; renderer.setRenderTarget(rtHalf); quad.render(renderer);
      const cu = comp.uniforms; cu.tColor.value = sceneTex; cu.tBlur.value = rtHalf.texture; cu.tDepth.value = rtScene.depthTexture; cu.uNear.value = camera.near; cu.uFar.value = camera.far; cu.uFocus.value = P.focus; cu.uScale.value = P.dofScale; cu.uMaxBlur.value = mb;
      quad.material = comp; renderer.setRenderTarget(rtDof); quad.render(renderer);
      let src = rtDof;
      if ((P.mblur ?? 0) > 0.001 && prevCam) {
        const u = mblur.uniforms; u.tColor.value = rtDof.texture; u.tDepth.value = rtScene.depthTexture;
        u.uInvVP.value.copy(camera.projectionMatrix).multiply(camera.matrixWorldInverse).invert();
        pvp.copy(prevCam.projectionMatrix).multiply(prevCam.matrixWorldInverse); u.uPrevVP.value.copy(pvp); u.uAmt.value = P.mblur; u.uDebug.value = window.MBDEBUG ? 1 : 0;
        quad.material = mblur; renderer.setRenderTarget(rtMB); quad.render(renderer); src = rtMB;
      }
      bloom.strength = P.bloom ?? 0.6; bloom.radius = P.bloomRadius ?? 0.65; bloom.threshold = P.bloomThreshold ?? 0.9;
      bloom.render(renderer, null, src, 0, false);
      const f = fin.uniforms; f.tColor.value = src.texture;
      f.uExposure.value = P.exposure ?? 1; f.uSat.value = P.sat ?? 1.05; f.uVig.value = P.vignette ?? 0.45; f.uTime.value = P.t; f.uContrast.value = P.contrast ?? 0.12;
      f.uShadow.value.set(P.shadowTint ?? 0xffffff); f.uHigh.value.set(P.highTint ?? 0xffffff); f.uLift.value.set(P.lift ?? 0x000000); f.uCA.value = P.ca ?? 0.0015;
      f.uFlash.value = P.flash ?? 0; f.uFlashCol.value.set(P.flashCol ?? 0xffffff); f.uFade.value = P.fade ?? 1; f.uBars.value = P.bars ?? 0; f.uGrain.value = P.grain ?? 0.03;
      f.uTint.value.set(P.tint ?? 0xffffff); f.uVigCol.value.set(P.vigCol ?? 0x000000);
      quad.material = fin; renderer.setRenderTarget(null); quad.render(renderer);
    }
  };
}
