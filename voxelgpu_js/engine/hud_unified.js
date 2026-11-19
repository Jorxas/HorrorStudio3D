// Interface de jeu du moteur unifié, dessinée sur le canvas 2D après la 3D : cartouche de titre, pile / cœurs + horloge, sous-titres à mots
// colorés (pixel-font Monocraft, largeur de caractère réglable), cartes de choix A/B avec curseur, cartes de fin. Tout est DONNÉE du contrat :
//   hud:      { x, title: [{ text, color, cw, y }], corner: { clock: [{ t, text }], battery: [{ t, bars, color }], hearts: [{ t, full, total }] } }
//   captions: [{ t0, t1, text, words: [[mot, rouge?], ...], lines?: [[indices], ...], y? }]  (l'ancien format words: [[t0, t1, mot]] reste lu par captions_unified.js)
//   cards:    [{ kind: 'box'|'choice'|'endcard', t0, t1, ... }]
// Aucune horloge, aucun hasard : fonction pure de t. cw / x = fractions de la largeur W, y = fractions de la hauteur H.
const FONT = 'Monocraft';
const stepAt = (keys, t, d) => { let v = d; for (const k of keys || []) if (t >= k.t) v = k; return v; };
let ADV = null;
function advance(g) { if (ADV == null) { g.save(); g.font = `100px ${FONT}`; ADV = g.measureText('M').width / 100; g.restore(); } return ADV; }
// police dont la largeur de caractère vaut cw * W
function setFont(g, cw, W) { const sz = Math.max(6, Math.round(cw * W / advance(g))); g.font = `${sz}px ${FONT}`; return sz; }
function text(g, s, x, y, o) { // y = milieu de ligne
  g.textBaseline = 'middle'; g.textAlign = o.align || 'left';
  if (o.stroke) { g.lineJoin = 'round'; g.lineWidth = o.stroke; g.strokeStyle = o.strokeCol || '#000'; g.strokeText(s, x, y); }
  g.fillStyle = o.color || '#fff'; g.fillText(s, x, y);
}
function heart(g, x, y, s, full, col) { // cœur pixel 7 x 6
  const m = ['0110110', '1111111', '1111111', '0111110', '0011100', '0001000'];
  m.forEach((r, j) => [...r].forEach((c, i) => {
    if (c !== '1') return;
    const edge = j === 0 || j === 5 || i === 0 || i === 6 || (j === 1 && (i === 1 || i === 5)) || (j === 3 && (i === 1 || i === 5)) || (j === 4 && (i === 2 || i === 4));
    g.fillStyle = full ? col : (edge ? '#e8e8e8' : '#0a0a0a'); g.fillRect(x + i * s, y + j * s, s, s);
  }));
}
function hud(g, C, t, W, H) {
  const h = C.hud; if (!h || (h.t_end != null && t >= h.t_end)) return; const x0 = (h.x ?? 0.04) * W; g.save();
  for (const l of h.title || []) { setFont(g, l.cw, W); text(g, l.text, x0, l.y * H, { color: l.color, stroke: Math.max(2, W * 0.003), strokeCol: 'rgba(0,0,0,.75)' }); }
  const c = h.corner || {};
  if (c.clock) { const k = stepAt(c.clock, t, c.clock[0]); setFont(g, 0.0285, W); text(g, k.text, 0.957 * W, 0.0646 * H, { align: 'right', color: '#f2f2f2', stroke: W * 0.003, strokeCol: 'rgba(0,0,0,.75)' }); }
  if (c.battery) {
    const k = stepAt(c.battery, t, c.battery[0]); const off = k.blink && Math.floor((t - k.t) / k.blink) % 2 === 1; const bx = 0.863 * W, by = 0.028 * H, bw = 0.09 * W, bh = 0.021 * H, th = Math.max(2, W * 0.0028);
    g.fillStyle = '#0a0a0a'; g.fillRect(bx, by, bw, bh); g.strokeStyle = '#f0f0f0'; g.lineWidth = th; g.strokeRect(bx, by, bw, bh); g.fillStyle = '#f0f0f0'; g.fillRect(bx + bw, by + bh * 0.3, th * 1.6, bh * 0.4);
    const n = 3, gap = th * 1.2, iw = (bw - th * 2 - gap * (n + 1)) / n;
    for (let i = 0; i < (off ? 0 : k.bars); i++) { g.fillStyle = k.color || '#58d85a'; g.fillRect(bx + th + gap + i * (iw + gap), by + th + gap * 0.6, iw, bh - th * 2 - gap * 1.2); }
  }
  if (c.hearts) {
    const k = stepAt(c.hearts, t, c.hearts[0]); const s = Math.max(2, Math.round(W * 0.0042)), gap = s * 2.2; const x = 0.81 * W, y = 0.029 * H;
    for (let i = 0; i < (k.total ?? 3); i++) heart(g, x + i * (7 * s + gap), y, s, i < k.full, '#f03a3a');
  }
  g.restore();
}
function box(g, x0, y0, x1, y1, o = {}) {
  g.fillStyle = o.fill || '#050505'; g.fillRect(x0, y0, x1 - x0, y1 - y0); g.strokeStyle = o.border || '#f2f2f2'; g.lineWidth = o.lw || 3; g.strokeRect(x0, y0, x1 - x0, y1 - y0);
}
function cards(g, C, t, W, H) {
  for (const c of C.cards || []) {
    if (t < c.t0 || t >= c.t1) continue; g.save();
    if (c.kind === 'endcard') {
      const fade = c.fade_out ? Math.max(0, Math.min(1, (c.t1 - t) / c.fade_out)) : 1;                      // fondu sortant : la carte s'efface sur fade_out s
      if (c.bg !== null) { g.globalAlpha = fade; g.fillStyle = c.bg || '#06070b'; g.fillRect(0, 0, W, H); }
      g.globalAlpha = fade;
      for (const l of c.lines) { setFont(g, l.cw, W); text(g, l.text, W / 2, l.y * H, { align: 'center', color: l.color, stroke: l.stroke ? l.stroke * W : 0, strokeCol: l.stroke_col || '#000' }); }
      if (c.button) { const b = c.button; box(g, b.x0 * W, b.y0 * H, b.x1 * W, b.y1 * H, { lw: 3 }); setFont(g, b.cw ?? 0.0275, W); text(g, b.text, W / 2, (b.y0 + b.y1) / 2 * H, { align: 'center', color: '#f2f2f2' }); }
    } else if (c.kind === 'box') {
      box(g, c.x0 * W, c.y0 * H, c.x1 * W, c.y1 * H, {}); setFont(g, c.cw ?? 0.048, W); text(g, c.text, W / 2, (c.y0 + c.y1) / 2 * H, { align: 'center', color: '#f2f2f2' });
    } else if (c.kind === 'choice') {
      const q = c.question; box(g, q.x0 * W, q.y0 * H, q.x1 * W, q.y1 * H, {}); setFont(g, q.cw ?? 0.048, W); text(g, q.text, W / 2, (q.y0 + q.y1) / 2 * H, { align: 'center', color: '#f2f2f2' });
      const sel = stepAt(c.sel, t, { i: -1 }).i;
      c.options.forEach((o, i) => {
        const on = i === sel, x0 = o.x0 * W, x1 = o.x1 * W, y0 = o.y0 * H, y1 = o.y1 * H, mid = (y0 + y1) / 2;
        box(g, x0, y0, x1, y1, { fill: on ? '#1a0508' : '#050505', border: on ? '#f03a2e' : '#f2f2f2', lw: on ? 4 : 3 });
        if (on) { g.fillStyle = '#f2f2f2'; const a = (y1 - y0) * 0.14, cx = x0 + (x1 - x0) * 0.04; g.beginPath(); g.moveTo(cx, mid - a); g.lineTo(cx, mid + a); g.lineTo(cx + a, mid); g.fill(); }
        setFont(g, 0.05, W); text(g, o.key, x0 + (x1 - x0) * 0.13, mid, { align: 'center', color: on ? '#f03a2e' : '#f2f2f2' });
        setFont(g, 0.031, W); const n = o.lines.length, lh = (y1 - y0) * 0.36;
        o.lines.forEach((s, j) => text(g, s, x0 + (x1 - x0) * 0.2, mid + (j - (n - 1) / 2) * lh, { color: on ? '#fff' : '#e6e6e6' }));
      });
    }
    g.restore();
  }
}
// sous-titres : mots [mot, rouge?] ; une ligne par entrée de `lines` si fournie, sinon une seule ligne centrée
function subtitles(g, C, t, W, H) {
  const st = C.caption_style || {}; const cw = st.cw ?? 0.049;
  for (const c of C.captions || []) {
    if (t < c.t0 || t >= c.t1 || !c.words || typeof c.words[0]?.[0] !== 'string') continue;
    g.save(); const sz = setFont(g, cw, W); const y0 = (c.y ?? st.y ?? 0.47) * H; const lines = c.lines || [c.words.map((_, i) => i)];
    lines.forEach((idx, li) => {
      const y = y0 + (li - (lines.length - 1) / 2) * sz * 1.28; const ws = idx.map((i) => c.words[i]); const sp = g.measureText(' ').width;
      const total = ws.reduce((a, w) => a + g.measureText(w[0]).width, 0) + sp * (ws.length - 1); let x = W / 2 - total / 2;
      for (const [w, red] of ws) { const ww = g.measureText(w).width; text(g, w, x, y, { color: red ? (st.hi ?? '#f2392d') : (st.color ?? '#f4f4f4'), stroke: sz * 0.16, strokeCol: 'rgba(0,0,0,.9)' }); x += ww + sp; }
    });
    g.restore();
  }
}
export function drawUI(g, C, t, W, H) { hud(g, C, t, W, H); subtitles(g, C, t, W, H); cards(g, C, t, W, H); }
