// Rendu GPU du moteur unifié : Chromium (Playwright) + ANGLE/D3D11 + Three.js. Lit un contrat JSON, écrit un MP4 vidéo seul
// (pixels bruts -> ffmpeg, aucun JPEG intermédiaire) et/ou des PNG, et atteste le GPU réellement utilisé par WebGL.
//   node render_unified.js --contract c.json --out video.mp4 [--w 720 --h 1280 --fps 24 --start 0 --end 61]
//                          [--stills 1.5,10 --stills-dir dir] [--gpu nvidia|intel|auto|software] [--luid hi,lo] [--attest a.json]
// Performance (voir docs/PERF_VOXELGPU.md) :
//   --transport bin|b64   bin (défaut) : la page POSTe chaque image brute au serveur local, qui la passe à ffmpeg.
//                         b64 : ancien chemin (page.evaluate -> base64 -> CDP), gardé pour les comparaisons A/B.
//   --encoder x264|nvenc  x264 (défaut, CPU, identique aux rendus livrés) | nvenc (h264_nvenc, GPU) | lossless (référence de qualité) ; --crf / --preset / --qp (nvenc)
//   --ranges 10:11,45:46  plusieurs fenêtres (secondes) au lieu de --start/--end ; --hash f.txt : sha256 de chaque image brute
//   --inflight N          images en vol vers le serveur (défaut 3) ; --profile N : coût par étape sur N images, sans MP4
// Aucune image n'est conservée entre deux rendus : pas de reprise qui mélangerait d'anciennes et de nouvelles images.
const fs = require('fs'), path = require('path'), http = require('http'), crypto = require('crypto'), { spawn } = require('child_process');
let chromium; try { ({ chromium } = require('playwright')); } catch (e) { console.error('playwright introuvable (NODE_PATH ?) :', e.message); process.exit(3); }

const A = {}; for (let i = 2; i < process.argv.length; i++) { const a = process.argv[i]; if (a.startsWith('--')) { const k = a.slice(2); const v = process.argv[i + 1] && !process.argv[i + 1].startsWith('--') ? process.argv[++i] : '1'; A[k] = v; } }
const ROOT = __dirname; const contractPath = path.resolve(A.contract || ''); if (!A.contract || !fs.existsSync(contractPath)) { console.error('--contract <fichier> requis'); process.exit(2); }
const contract = JSON.parse(fs.readFileSync(contractPath, 'utf8'));
const portrait = contract.aspect !== '16:9';
const W = +(A.w || (portrait ? 720 : 1280)), H = +(A.h || (portrait ? 1280 : 720)), FPS = +(A.fps || contract.fps || 24);
const T0 = +(A.start || 0), T1 = +(A.end || contract.duration);
const TRANSPORT = (A.transport || 'bin').toLowerCase();
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg', '.otf': 'font/otf', '.ttf': 'font/ttf', '.css': 'text/css' };

// frames to render, in order: --ranges "a:b,c:d" (seconds) or --start/--end
function frameList() {
  const ranges = A.ranges ? A.ranges.split(',').map((r) => r.split(':').map(Number)) : [[T0, T1]];
  const out = []; for (const [a, b] of ranges) for (let f = Math.round(a * FPS); f < Math.round(b * FPS); f++) out.push(f);
  return out;
}
// ffmpeg arguments after the input. x264 is the reference (what the delivered masters used); nvenc is opt-in.
function encoderArgs() {
  const color = ['-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709'];
  const vf = ['-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p'];
  if ((A.encoder || 'x264').toLowerCase() === 'lossless')   // reference for quality comparisons (SSIM/PSNR), not a delivery format
    return [...vf, '-c:v', 'libx264', '-qp', '0', '-preset', 'ultrafast', '-profile:v', 'high444', '-r', String(FPS), ...color];
  if ((A.encoder || 'x264').toLowerCase() === 'nvenc')
    return [...vf, '-c:v', 'h264_nvenc', '-preset', A.preset || 'p5', '-tune', 'hq', '-rc', 'constqp', '-qp', A.qp || '16', '-spatial-aq', '1', '-profile:v', 'high', '-r', String(FPS), ...color];
  return [...vf, '-c:v', 'libx264', '-preset', A.preset || 'medium', '-crf', A.crf || '14', '-profile:v', 'high', '-r', String(FPS), ...(A.threads ? ['-threads', A.threads] : []), ...color];
}
function startFfmpeg() {
  const ff = spawn('ffmpeg', ['-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', `${W}x${H}`, '-r', String(FPS), '-i', '-',
    ...encoderArgs(), '-movflags', '+faststart', A.out], { stdio: ['pipe', 'inherit', 'inherit'] });
  let ending = false;
  const closed = new Promise((r) => ff.on('close', (code) => { if (!ending) { console.error('ffmpeg arrêté avant la fin, code', code); process.exit(5); } r(code); }));
  ff.stdin.on('error', () => {});
  ff.end = () => { ending = true; ff.stdin.end(); };
  return { ff, closed };
}

// Sink for raw frames: counts, hashes (optional) and feeds ffmpeg in frame order. write() resolves when ffmpeg has accepted the frame.
function makeSink(ffObj, hashes) {
  const st = { done: 0, blocked: 0, next: 0, pending: new Map() };
  async function push(buf) {
    if (hashes) hashes.push(`${st.done}\t${crypto.createHash('sha256').update(buf).digest('hex')}`);
    st.done++;
    if (ffObj) { if (!ffObj.ff.stdin.write(buf)) { const b = Date.now(); await new Promise((r) => ffObj.ff.stdin.once('drain', r)); st.blocked += Date.now() - b; } }
  }
  // out-of-order frames (two in flight) wait until their turn
  async function accept(i, buf) {
    if (i !== st.next) await new Promise((r) => st.pending.set(i, r));
    await push(buf); st.next++;
    const r = st.pending.get(st.next); if (r) { st.pending.delete(st.next); r(); }
  }
  return { st, accept, push };
}

function serve(sinkRef) {
  return new Promise((res) => {
    const srv = http.createServer((req, rsp) => {
      const u = decodeURIComponent(req.url.split('?')[0]);
      if (req.method === 'POST' && u === '/__frame') {
        const chunks = []; req.on('data', (c) => chunks.push(c));
        req.on('end', async () => {
          const buf = Buffer.concat(chunks);
          if (buf.length !== W * H * 4) { console.error('taille de trame inattendue', buf.length); rsp.writeHead(400); return rsp.end(); }
          await sinkRef.sink.accept(+req.headers['x-frame'], buf); rsp.writeHead(204); rsp.end();
        });
        return;
      }
      if (u === '/__contract.json') { rsp.writeHead(200, { 'Content-Type': 'application/json' }); return rsp.end(fs.readFileSync(contractPath)); }
      const p = path.join(ROOT, u); if (!p.startsWith(ROOT)) { rsp.writeHead(403); return rsp.end(); }
      fs.readFile(p, (e, d) => { if (e) { rsp.writeHead(404); return rsp.end(); } rsp.writeHead(200, { 'Content-Type': TYPES[path.extname(p)] || 'application/octet-stream' }); rsp.end(d); });
    });
    srv.listen(0, '127.0.0.1', () => res({ port: srv.address().port, close: () => srv.close() }));
  });
}
function launchArgs() {
  const g = (A.gpu || 'auto').toLowerCase();
  if (g === 'software') return { channel: undefined, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--disable-gpu-sandbox'] };
  const args = ['--ignore-gpu-blocklist', '--enable-gpu', '--enable-gpu-rasterization', '--use-gl=angle', '--use-angle=d3d11', '--disable-gpu-sandbox'];
  if (A.luid) args.push(`--use-adapter-luid=${A.luid}`);
  return { channel: 'chromium', args };
}
(async () => {
  const sinkRef = { sink: null }; const srv = await serve(sinkRef); const L = launchArgs();
  const browser = await chromium.launch({ channel: L.channel, headless: !A.show, args: L.args });
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  const errors = []; page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') { const t = m.text().slice(0, 300); errors.push(t); if (!A.quiet) console.log('console:', m.type(), t); } });
  page.on('pageerror', (e) => { errors.push('PAGEERR ' + e.message); console.log('PAGEERR', e.message); });
  const t0 = Date.now();
  await page.goto(`http://127.0.0.1:${srv.port}/engine/unified.html?contract=/__contract.json&w=${W}&h=${H}${A.msaa ? '&msaa=' + A.msaa : ''}`);
  await page.waitForFunction('window.ready === true', null, { timeout: 600000 });
  const gpu = await page.evaluate('window.gpuInfo()'); const loadS = (Date.now() - t0) / 1000;
  const att = { gpu_request: A.gpu || 'auto', luid_arg: A.luid || null, webgl: gpu, w: W, h: H, fps: FPS, load_s: loadS, browser: browser.version(), contract_sha256: crypto.createHash('sha256').update(fs.readFileSync(contractPath)).digest('hex'), page_errors: errors.slice(0, 20), transport: TRANSPORT, encoder: (A.encoder || 'x264').toLowerCase() };
  console.log('GPU :', gpu.renderer, '| charge en', loadS.toFixed(1), 's');
  if (A.attest) fs.writeFileSync(A.attest, JSON.stringify(att, null, 1));
  if (A.stills) {
    const dir = A['stills-dir'] || '.'; fs.mkdirSync(dir, { recursive: true });
    for (const t of A.stills.split(',').map(Number)) { const d = await page.evaluate(`renderAt(${t}, 'png')`); fs.writeFileSync(path.join(dir, `t_${t.toFixed(2)}.png`), Buffer.from(d.split(',')[1], 'base64')); }
  }
  if (A.profile) {   // cost of each stage of one frame, averaged over N frames spread over the requested range (first 3 frames of each window skipped)
    const list = frameList(), n = Math.min(+A.profile, list.length), acc = {}; let k = 0;
    for (let i = 0; i < n; i++) { const P = await page.evaluate(`profAt(${list[Math.floor(i * list.length / n)] / FPS})`); if (i < 3) continue; for (const [x, v] of Object.entries(P)) acc[x] = (acc[x] || 0) + v; k++; }
    for (const x of Object.keys(acc)) acc[x] = +(acc[x] / k).toFixed(2); att.profile_ms = acc; console.log('PROFIL ms/image :', JSON.stringify(acc));
    if (A.attest) fs.writeFileSync(A.attest, JSON.stringify(att, null, 1));
  }
  if (A.out || A.hash) {
    const list = frameList(); const hashes = A.hash ? [] : null;
    const ffObj = A.out ? startFfmpeg() : null; const ctl = makeSink(ffObj, hashes); sinkRef.sink = ctl;
    const tr = Date.now();
    if (TRANSPORT === 'bin') {
      await page.evaluate(`streamFrames(${JSON.stringify(list)}, ${FPS}, '/__frame', ${+(A.inflight || 3)})`);
    } else {
      for (let i = 0; i < list.length; i++) {
        const b64 = await page.evaluate(`renderAt(${list[i] / FPS}, 'raw')`);
        const buf = Buffer.from(b64, 'base64'); if (buf.length !== W * H * 4) { console.error('taille de trame inattendue', buf.length); process.exit(4); }
        await ctl.push(buf);
        if (!A.quiet && i % 48 === 0) console.log(`image ${i}/${list.length}  ${(ctl.st.done / ((Date.now() - tr) / 1000)).toFixed(1)} i/s`);
      }
    }
    const tRender = (Date.now() - tr) / 1000;
    let ffCode = 0; if (ffObj) { ffObj.ff.end(); ffCode = await ffObj.closed; }
    const sec = (Date.now() - tr) / 1000; const done = ctl.st.done;
    if (ffCode) { console.error('ffmpeg a échoué, code', ffCode); process.exit(5); }
    att.frames = done; att.render_s = sec; att.fps_render = done / sec; att.frames_loop_s = tRender; att.ffmpeg_blocked_s = ctl.st.blocked / 1000;
    if (hashes) fs.writeFileSync(A.hash, hashes.join('\n') + '\n');
    console.log(`TERMINE ${done} images en ${sec.toFixed(1)} s = ${(done / sec).toFixed(1)} i/s (ffmpeg bloquant ${(ctl.st.blocked / 1000).toFixed(1)} s) -> ${A.out || '(hash seul)'}`);
    if (A.attest) fs.writeFileSync(A.attest, JSON.stringify(att, null, 1));
  }
  await browser.close(); srv.close();
})().catch((e) => { console.error('ECHEC', e); process.exit(1); });
