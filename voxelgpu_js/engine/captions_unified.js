// Sous-titres facultatifs du moteur unifié, dessinés sur le canvas 2D (police Inter embarquée, zone sûre selon le format).
// contract.captions : [{ t0, t1, text, words?: [[t0, t1, 'mot'], ...] }]    contract.caption_style : { size, y, color, hi, box }
const wrapLines = (g, words, maxW) => { const lines = []; let cur = []; for (const w of words) { const test = [...cur, w].join(' '); if (cur.length && g.measureText(test).width > maxW) { lines.push(cur); cur = [w]; } else cur.push(w); } if (cur.length) lines.push(cur); return lines; };
export function drawCaptions(g, contract, t, W, H) {
  const c = contract.captions.find((c) => t >= c.t0 && t < c.t1 && typeof c.words?.[0]?.[0] !== 'string'); if (!c) return;
  const st = contract.caption_style || {}, portrait = H > W;
  const size = Math.round((st.size ?? (portrait ? 0.045 : 0.05)) * H), y0 = (st.y ?? (portrait ? 0.74 : 0.88)) * H;
  g.save(); g.font = `800 ${size}px Inter`; g.textAlign = 'center'; g.textBaseline = 'middle'; g.lineJoin = 'round';
  const words = (c.words && c.words.length) ? c.words.map((w) => w[2]) : c.text.split(/\s+/);
  const lines = wrapLines(g, words, W * (portrait ? 0.84 : 0.7));
  const fade = Math.min(1, (t - c.t0) / 0.12, (c.t1 - t) / 0.12);
  g.globalAlpha = Math.max(0, fade);
  let idx = 0; const lh = size * 1.18;
  lines.forEach((ln, li) => {
    const y = y0 + (li - (lines.length - 1) / 2) * lh; const total = g.measureText(ln.join(' ')).width; let x = W / 2 - total / 2;
    for (const w of ln) {
      const ww = g.measureText(w).width; const cur = c.words && c.words[idx] && t >= c.words[idx][0] && t < c.words[idx][1];
      g.textAlign = 'left'; g.lineWidth = size * 0.16; g.strokeStyle = 'rgba(0,0,0,0.85)'; g.strokeText(w, x, y);
      g.fillStyle = cur ? (st.hi ?? '#ffd84a') : (st.color ?? '#ffffff'); g.fillText(w, x, y); x += ww + g.measureText(' ').width; idx++;
    }
  });
  g.restore();
}
