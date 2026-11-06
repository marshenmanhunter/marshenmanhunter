// SimpleFIN Bridge client for the desktop app. Runs in the main process, so the access key
// never reaches the page. The key is encrypted with the operating system's keychain
// (Keychain on Mac, DPAPI on Windows) through Electron's safeStorage.
const { app, safeStorage } = require('electron');
const path = require('path');
const fs = require('fs/promises');

const file = () => path.join(app.getPath('userData'), 'simplefin.bin');

async function saveAccess(url) {
  const data = safeStorage.isEncryptionAvailable() ? Buffer.concat([Buffer.from('enc:'), safeStorage.encryptString(url)]) : Buffer.from('raw:' + url);
  await fs.writeFile(file(), data, { mode: 0o600 });
}
async function loadAccess() {
  try {
    const buf = await fs.readFile(file()), tag = buf.subarray(0, 4).toString();
    if (tag === 'enc:') return safeStorage.decryptString(buf.subarray(4));
    if (tag === 'raw:') return buf.subarray(4).toString();
  } catch (e) { /* not connected */ }
  return null;
}
async function clearAccess() { await fs.rm(file(), { force: true }); }

function decodeToken(token) {
  const clean = String(token || '').replace(/\s+/g, '');
  let url; try { url = Buffer.from(clean, 'base64').toString('utf8'); } catch (e) { return null; }
  return /^https:\/\/\S+$/.test(url) ? url : null;
}
function splitAccess(access) {
  const u = new URL(access);
  if (u.protocol !== 'https:' || !u.username) throw new Error('bad access url');
  const auth = 'Basic ' + Buffer.from(decodeURIComponent(u.username) + ':' + decodeURIComponent(u.password)).toString('base64');
  u.username = ''; u.password = '';
  return { base: u.toString().replace(/\/$/, ''), auth };
}

async function claim(token) {
  const url = decodeToken(token);
  if (!url) return { ok: false, message: 'That does not look like a SimpleFIN setup token. Copy the whole token from SimpleFIN and paste it again.' };
  let res; try { res = await fetch(url, { method: 'POST' }); } catch (e) { return { ok: false, message: 'Could not reach SimpleFIN. Check your internet connection.' }; }
  if (res.status === 403) return { ok: false, status: 403, message: 'SimpleFIN refused this token. It was already used or is wrong. If you did not use it yourself, someone else may have: turn it off at SimpleFIN and create a new one.' };
  if (!res.ok) return { ok: false, status: res.status, message: 'SimpleFIN returned an error (' + res.status + '). Try again in a few minutes.' };
  const access = (await res.text()).trim();
  try { splitAccess(access); } catch (e) { return { ok: false, message: 'SimpleFIN sent back something unexpected. Create a new token and try again.' }; }
  await saveAccess(access);
  return { ok: true };
}

async function accounts(p) {
  const access = await loadAccess();
  if (!access) return { ok: false, message: 'Not connected.' };
  let parts; try { parts = splitAccess(access); } catch (e) { return { ok: false, message: 'The saved connection is damaged. Disconnect and connect again.' }; }
  const q = new URLSearchParams();
  if (p && p.startDate) q.set('start-date', String(Math.floor(+p.startDate)));
  if (p && p.balancesOnly) q.set('balances-only', '1');
  q.set('pending', '1');
  let res; try { res = await fetch(parts.base + '/accounts?' + q, { headers: { Authorization: parts.auth } }); } catch (e) { return { ok: false, message: 'Could not reach SimpleFIN. Check your internet connection.' }; }
  if (res.status === 403) return { ok: false, status: 403, message: 'SimpleFIN no longer accepts this connection. Disconnect, then connect again with a new token.' };
  if (res.status === 402) return { ok: false, status: 402, message: 'Your SimpleFIN subscription needs payment. Renew it at SimpleFIN, then sync again.' };
  if (!res.ok) return { ok: false, status: res.status, message: 'SimpleFIN returned an error (' + res.status + '). Try again later.' };
  try { return { ok: true, data: await res.json() }; } catch (e) { return { ok: false, message: 'SimpleFIN sent data Keel could not read.' }; }
}

module.exports = {
  status: async () => ({ connected: !!(await loadAccess()) }),
  claim, accounts,
  disconnect: async () => { await clearAccess(); return { ok: true }; },
  _test: { decodeToken, splitAccess, saveAccess }
};
