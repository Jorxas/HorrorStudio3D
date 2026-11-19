// petit serveur de fichiers statiques intégré (évite de dépendre d'un serveur externe)
const http = require('http'), fs = require('fs'), path = require('path');
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg', '.ttf': 'font/ttf', '.wasm': 'application/wasm', '.css': 'text/css' };
module.exports = function serve(root) {
  return new Promise((res) => {
    const srv = http.createServer((req, rsp) => { const u = decodeURIComponent(req.url.split('?')[0]); const p = path.join(root, u); if (!p.startsWith(root)) { rsp.writeHead(403); return rsp.end(); }
      fs.readFile(p, (e, d) => { if (e) { rsp.writeHead(404); return rsp.end(); } rsp.writeHead(200, { 'Content-Type': TYPES[path.extname(p)] || 'application/octet-stream' }); rsp.end(d); }); });
    srv.listen(0, '127.0.0.1', () => res({ port: srv.address().port, close: () => srv.close() }));
  });
};
