// Builds the standalone app in web/ from the Claude artifact page in src/.
// Run with: npm run build:web
// The page in src/keel-budget.html is the same file published as the Claude artifact.
// This script wraps it in a full HTML document, swaps Google Fonts for bundled fonts,
// and adds desktop, iOS and offline support. It fails loudly if an expected spot moved.
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const src = fs.readFileSync(path.join(root, 'src', 'keel-budget.html'), 'utf8');
let page = src;

function replaceOnce(from, to, label) {
  const n = page.split(from).length - 1;
  if (n !== 1) throw new Error(`build-web: expected exactly one match for "${label}", found ${n}`);
  page = page.replace(from, to);
}

// 1. Drop the artifact-only head lines; they move into a real <head> below.
page = page
  .replace(/<title>[^<]*<\/title>\n/, '')
  .replace(/<meta name="claude:viewport-fit-sides"[^>]*>\n/, '')
  .replace(/<link rel="preconnect"[^>]*>\n/g, '')
  .replace(/<link rel="stylesheet" href="https:\/\/fonts\.googleapis\.com[^>]*>\n/, '');
if (/fonts\.googleapis/.test(page)) throw new Error('build-web: Google Fonts link still present');

// 2. Save-status text for a standalone install.
replaceOnce(
  "local: ['local', 'Saved in this browser only. Open it inside Claude to save to your account.']",
  "local: ['local', (window.keelNative ? 'Saved on this computer.' : (window.Capacitor ? 'Saved on this device.' : 'Saved in this browser.')) + ' Export a backup from Categories now and then.']",
  'status text'
);

// 3. Real file saves: a save dialog on desktop, a download in a browser.
replaceOnce(
  "  openModal('text', { title, text, note: 'Copy this text and paste it into a file named ' + filename + '.' });\n}",
  `  if (window.keelNative && window.keelNative.saveFile) {
    try { const r = await window.keelNative.saveFile(filename, text); if (r && r.status === 'saved') toast('Saved ' + filename); return; } catch (e) {}
  } else if (!window.claude && !window.Capacitor) {
    try {
      const url = URL.createObjectURL(new Blob([text], { type: filename.endsWith('.json') ? 'application/json' : 'text/csv' }));
      const a = document.createElement('a'); a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 5000); toast('Downloaded ' + filename); return;
    } catch (e) {}
  }
  openModal('text', { title, text, note: 'Copy this text and paste it into a file named ' + filename + '.' });
}`,
  'offerFile'
);

// 4. A "Try it with sample data" button on the welcome screen.
replaceOnce(
  'style="height:42px;padding:0 20px">Create my budget</button>`}</div></section></div>`;',
  'style="height:42px;padding:0 20px">Create my budget</button>${window.KEEL_SAMPLE ? ` <button class="btn" data-act="load-sample" style="height:42px;padding:0 20px">Try it with sample data</button>` : \'\'}`}</div></section></div>`;',
  'onboarding buttons'
);
replaceOnce(
  "    case 'onboard-start':",
  `    case 'load-sample': { const smp = window.KEEL_SAMPLE(); S.settings = normalizeSettings(smp.settings); S.months = smp.months; S.phase = 'ready'; changed('settings', ...Object.keys(S.months).map(ym => 'm-' + ym)); location.hash = '#overview'; break; }
    case 'onboard-start':`,
  'load-sample action'
);

const head = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Keel Budget</title>
<meta name="theme-color" content="#1E5A44">
<meta name="description" content="Keel: budgets, accounts, forecasts, reimbursements and shared costs in one private app.">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" type="image/png" href="icons/icon-192.png">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="Keel">
<link rel="stylesheet" href="fonts/fonts.css">
<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0;font:14px system-ui,-apple-system,"Segoe UI",sans-serif}img{max-width:100%}[hidden]{display:none!important}</style>
<script src="sample.js"></script>
</head>
<body>
`;
const tail = `
<script>
if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost') && !window.Capacitor) {
  navigator.serviceWorker.register('sw.js').catch(() => {});
}
</script>
</body>
</html>
`;
fs.writeFileSync(path.join(root, 'web', 'index.html'), head + page.trim() + '\n' + tail);

// Sample data, shifted so its last month lines up with the current month.
const sample = fs.readFileSync(path.join(root, 'src', 'sample.json'), 'utf8');
fs.writeFileSync(path.join(root, 'web', 'sample.js'), `// Made-up household for "Try it with sample data". Generated by tools/build-web.js.
(function () {
  var DATA = ${sample.trim()};
  var BASE = '2026-11';
  function pad(n) { return String(n).padStart(2, '0'); }
  function addM(ym, n) { var y = +ym.slice(0, 4), m = +ym.slice(5, 7) + n; y += Math.floor((m - 1) / 12); m = ((m - 1) % 12 + 12) % 12 + 1; return y + '-' + pad(m); }
  function dim(ym) { return new Date(+ym.slice(0, 4), +ym.slice(5, 7), 0).getDate(); }
  function shiftStr(s, k) {
    if (/^\\d{4}-\\d{2}-\\d{2}$/.test(s)) { var ym = addM(s.slice(0, 7), k); return ym + '-' + pad(Math.min(+s.slice(8), dim(ym))); }
    if (/^\\d{4}-\\d{2}$/.test(s)) return addM(s, k);
    return s;
  }
  function walk(v, k) {
    if (Array.isArray(v)) return v.map(function (x) { return walk(x, k); });
    if (v && typeof v === 'object') { var o = {}; Object.keys(v).forEach(function (key) { o[shiftStr(key, k)] = walk(v[key], k); }); return o; }
    return typeof v === 'string' ? shiftStr(v, k) : v;
  }
  window.KEEL_SAMPLE = function () {
    var now = new Date(), cur = now.getFullYear() + '-' + pad(now.getMonth() + 1);
    var k = (+cur.slice(0, 4) - +BASE.slice(0, 4)) * 12 + (+cur.slice(5, 7) - +BASE.slice(5, 7));
    return walk(JSON.parse(JSON.stringify(DATA)), k);
  };
})();
`);
console.log('web/index.html and web/sample.js built from src/');
