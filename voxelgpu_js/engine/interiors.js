// Interior sets built from textured boxes: school bus and school hallway.
import * as THREE from 'three';

function box(group, T, key, w, h, d, x, y, z, opts = {}) {
  const tex = T[key].clone(); tex.needsUpdate = true; tex.repeat.set(opts.rx ?? Math.max(1, w), opts.ry ?? Math.max(1, h));
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), opts.basic ? new THREE.MeshBasicMaterial({ map: tex, color: opts.color ?? 0xffffff }) : new THREE.MeshLambertMaterial({ map: tex, color: opts.color ?? 0xffffff, emissive: opts.emissive ?? 0x000000 }));
  m.position.set(x, y, z); m.castShadow = !opts.noShadow; m.receiveShadow = true; group.add(m); return m;
}

export function buildInteriors(scene, T) {
  const out = {};
  // ---------------- school bus (origin 300,0,0), interior x in [-1.7,1.7], z in [-8,8]
  { const g = new THREE.Group(); g.position.set(300, 0, 0); scene.add(g);
    box(g, T, 'busSeat', 3.6, 0.1, 17, 0, -0.05, 0, { rx: 3, ry: 17, color: 0x5a5a60 });
    box(g, T, 'white', 3.6, 0.1, 17, 0, 2.55, 0, { rx: 1, ry: 1, color: 0xf2f2ee });
    for (const sx of [-1, 1]) {
      box(g, T, 'busYellow', 0.1, 1.05, 17, sx * 1.8, 0.52, 0);
      box(g, T, 'busYellow', 0.1, 0.5, 17, sx * 1.8, 2.3, 0);
      for (let z = -7.5; z < 8; z += 1.5) box(g, T, 'busYellow', 0.12, 1.1, 0.2, sx * 1.8, 1.6, z);
      const sky = new THREE.Mesh(new THREE.PlaneGeometry(17, 1.0), new THREE.MeshBasicMaterial({ color: 0xffffff })); sky.material.color.setRGB(1.9, 2.05, 2.3); sky.position.set(sx * 1.84, 1.6, 0); sky.rotation.y = -sx * Math.PI / 2; g.add(sky);
      for (let z = -6.5; z < 7; z += 1.3) { box(g, T, 'busSeat', 1.1, 0.18, 0.8, sx * 1.05, 0.55, z, { rx: 1, ry: 1 }); box(g, T, 'busSeat', 1.1, 0.75, 0.16, sx * 1.05, 0.95, z - 0.42, { rx: 1, ry: 1 }); }
    }
    box(g, T, 'busYellow', 3.6, 2.6, 0.1, 0, 1.3, -8.4); const ws = new THREE.Mesh(new THREE.PlaneGeometry(3.0, 0.9), new THREE.MeshBasicMaterial({ color: 0xffffff })); ws.material.color.setRGB(2.0, 2.1, 2.3); ws.position.set(0, 1.75, -8.33); g.add(ws);
    box(g, T, 'busYellow', 3.6, 2.6, 0.1, 0, 1.3, 8.4);
    const l1 = new THREE.PointLight(0xfff4e0, 6, 12, 1.2); l1.position.set(0, 2.3, -3); g.add(l1); const l2 = l1.clone(); l2.position.z = 3; g.add(l2);
    out.bus = { origin: new THREE.Vector3(300, 0, 0), seats: [] };
    for (const sx of [-1, 1]) for (let z = -6.5; z < 7; z += 1.3) out.bus.seats.push(new THREE.Vector3(300 + sx * 1.05, 0.6, z));
    out.bus.group = g;
  }
  // ---------------- school hallway (origin 340,0,0): x in [-2.6,2.6], z in [-14,14]
  { const g = new THREE.Group(); g.position.set(340, 0, 0); scene.add(g);
    box(g, T, 'marble', 5.4, 0.1, 30, 0, -0.05, 0, { rx: 5, ry: 30 });
    box(g, T, 'ceiling', 5.4, 0.1, 30, 0, 3.6, 0, { rx: 5, ry: 30 });
    for (let z = -12; z <= 12; z += 4) { const p = box(g, T, 'lightPanel', 1.6, 0.04, 0.9, 0, 3.54, z, { rx: 1, ry: 1, basic: true, noShadow: true }); p.material.color.setRGB(2.6, 2.6, 2.5); }
    for (const sx of [-1, 1]) {
      for (let z = -14; z < 14; z += 0.9) { box(g, T, 'locker', 0.6, 2.3, 0.86, sx * 2.4, 1.15, z + 0.45, { rx: 1, ry: 1 }); }
      box(g, T, 'paintCream', 0.1, 1.3, 30, sx * 2.72, 2.95, 0, { rx: 30, ry: 1 });
    }
    box(g, T, 'paintCream', 5.4, 3.6, 0.1, 0, 1.8, -14.5); box(g, T, 'paintCream', 5.4, 3.6, 0.1, 0, 1.8, 14.5);
    for (const z of [-8, 0, 8]) { const l = new THREE.PointLight(0xf4f6ff, 7, 10, 1.3); l.position.set(0, 3.2, z); g.add(l); }
    out.hall = { origin: new THREE.Vector3(340, 0, 0), group: g };
  }
  return out;
}
