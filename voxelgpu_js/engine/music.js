// Module « représentation musicale » — côté rendu : lecture de l'analyse (tools/analyze_music.py),
// enveloppes calées sur les temps forts, et langage de caméra (bougé à l'épaule, trajectoires, coups de zoom).
import * as THREE from 'three';

export async function loadMusic(url, offset = 0) {
  const A = await (await fetch(url)).json();
  const sh = (arr) => arr.map((x) => x - offset);
  const beats = sh(A.beats), downs = sh(A.downbeats), onsets = sh(A.onsets);
  const vOn = A.vocal ? sh(A.vocal.onsets) : [], vPh = A.vocal ? A.vocal.phrases.map(([a, b]) => [a - offset, b - offset]) : [];
  const last = (arr, t) => { let lo = 0, hi = arr.length - 1, r = -1; while (lo <= hi) { const m = (lo + hi) >> 1; if (arr[m] <= t) { r = m; lo = m + 1; } else hi = m - 1; } return r; };
  const env = (arr, t, decay) => { const i = last(arr, t); return i < 0 ? 0 : Math.exp(-(t - arr[i]) / decay); };
  const M = {
    A, offset, beats, downs, onsets, vocalOnsets: vOn, vocalPhrases: vPh, tempo: A.tempo, period: A.beat_period,
    beatEnv: (t, decay = 0.16) => env(beats, t, decay),
    downEnv: (t, decay = 0.35) => env(downs, t, decay),
    onsetEnv: (t, decay = 0.12) => env(onsets, t, decay),
    vocalEnv: (t, decay = 0.2) => env(vOn, t, decay),
    beatIndex: (t) => last(beats, t), barIndex: (t) => last(downs, t),
    beatPhase: (t) => { const i = last(beats, t); if (i < 0 || i + 1 >= beats.length) return 0; return (t - beats[i]) / (beats[i + 1] - beats[i]); },
    snap: (t, arr = beats) => arr.reduce((b, x) => Math.abs(x - t) < Math.abs(b - t) ? x : b, arr[0]),
    energy: (t) => { const v = A.energy.v; const k = (t + offset) * A.energy.hz; const i = Math.max(0, Math.min(v.length - 2, Math.floor(k))); const f = Math.min(1, Math.max(0, k - i)); return v[i] * (1 - f) + v[i + 1] * f; },
    energySmooth: (t, w = 1.0) => { let s = 0, n = 0; for (let d = -w; d <= w; d += 0.1) { s += M.energy(t + d); n++; } return s / n; },
    vocalAt: (t) => { if (!A.vocal) return 0; const v = A.vocal.env.v; const i = Math.round((t + offset) * A.vocal.env.hz); return v[Math.max(0, Math.min(v.length - 1, i))]; },
    inRange: (arr, a, b) => arr.filter((x) => x >= a && x < b),
  };
  return M;
}

// bougé « caméra à l'épaule » : bruit lisse déterministe (somme de sinus incommensurables)
export function handheld(t, amp = 1, seed = 0) {
  const n = (f, p) => Math.sin(t * f + p + seed * 7.13) * 0.6 + Math.sin(t * f * 2.31 + p * 1.7 + seed) * 0.3 + Math.sin(t * f * 4.73 + p * 3.1) * 0.1;
  return { x: n(0.9, 1.0) * 0.03 * amp, y: n(1.1, 2.0) * 0.025 * amp, z: n(0.7, 3.0) * 0.02 * amp, rx: n(1.3, 4.0) * 0.006 * amp, ry: n(1.0, 5.0) * 0.008 * amp, rz: n(0.8, 6.0) * 0.008 * amp };
}

// trajectoire lisse (Catmull-Rom) à travers des points THREE.Vector3
export function spline(points, u) {
  const n = points.length - 1; const x = Math.min(0.99999, Math.max(0, u)) * n; const i = Math.floor(x), f = x - i;
  const p0 = points[Math.max(0, i - 1)], p1 = points[i], p2 = points[Math.min(n, i + 1)], p3 = points[Math.min(n, i + 2)];
  const f2 = f * f, f3 = f2 * f;
  return new THREE.Vector3(
    0.5 * ((2 * p1.x) + (-p0.x + p2.x) * f + (2 * p0.x - 5 * p1.x + 4 * p2.x - p3.x) * f2 + (-p0.x + 3 * p1.x - 3 * p2.x + p3.x) * f3),
    0.5 * ((2 * p1.y) + (-p0.y + p2.y) * f + (2 * p0.y - 5 * p1.y + 4 * p2.y - p3.y) * f2 + (-p0.y + 3 * p1.y - 3 * p2.y + p3.y) * f3),
    0.5 * ((2 * p1.z) + (-p0.z + p2.z) * f + (2 * p0.z - 5 * p1.z + 4 * p2.z - p3.z) * f2 + (-p0.z + 3 * p1.z - 3 * p2.z + p3.z) * f3));
}

// orbite autour d'un point
export function orbit(center, radius, angle, height) { return new THREE.Vector3(center.x + Math.sin(angle) * radius, center.y + height, center.z + Math.cos(angle) * radius); }
