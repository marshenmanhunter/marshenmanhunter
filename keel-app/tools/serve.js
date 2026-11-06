// Serves web/ at http://localhost:5173 so you can try the web version or install it as an app.
const http = require('http'), fs = require('fs'), path = require('path');
const root = path.join(__dirname, '..', 'web');
const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.webmanifest': 'application/manifest+json', '.png': 'image/png', '.woff2': 'font/woff2' };
http.createServer((req, res) => {
  let p = decodeURIComponent(new URL(req.url, 'http://x').pathname); if (p.endsWith('/')) p += 'index.html';
  const file = path.join(root, path.normalize(p));
  if (!file.startsWith(root)) { res.writeHead(403); return res.end(); }
  fs.readFile(file, (err, buf) => { if (err) { res.writeHead(404); return res.end('Not found'); } res.writeHead(200, { 'Content-Type': types[path.extname(file)] || 'application/octet-stream' }); res.end(buf); });
}).listen(5173, () => console.log('Keel is running at http://localhost:5173'));
