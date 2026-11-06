// Offline support for the web install. Serves the app shell from cache, then refreshes it.
const CACHE = 'keel-v3';
const SHELL = ['./', 'index.html', 'sample.js', 'manifest.webmanifest', 'fonts/fonts.css',
  'fonts/public-sans-latin-400-normal.woff2', 'fonts/public-sans-latin-500-normal.woff2', 'fonts/public-sans-latin-600-normal.woff2', 'fonts/public-sans-latin-700-normal.woff2',
  'fonts/schibsted-grotesk-latin-500-normal.woff2', 'fonts/schibsted-grotesk-latin-600-normal.woff2', 'fonts/schibsted-grotesk-latin-700-normal.woff2', 'fonts/schibsted-grotesk-latin-800-normal.woff2',
  'fonts/ibm-plex-mono-latin-400-normal.woff2', 'fonts/ibm-plex-mono-latin-500-normal.woff2',
  'icons/icon-192.png', 'icons/icon-512.png', 'icons/apple-touch-icon.png'];
self.addEventListener('install', e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET' || new URL(e.request.url).origin !== location.origin) return;
  e.respondWith(caches.match(e.request).then(hit => {
    const net = fetch(e.request).then(res => { if (res.ok) caches.open(CACHE).then(c => c.put(e.request, res.clone())); return res; }).catch(() => hit);
    return hit || net;
  }));
});
