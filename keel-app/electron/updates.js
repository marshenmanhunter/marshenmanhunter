// Update checks for the desktop app, using releases published on GitHub.
// Windows (installed version): downloads the update in the background, then asks to restart.
// Mac: Apple only lets signed apps replace themselves, so Keel shows a download button instead.
// The portable Windows exe cannot replace itself either, so it gets the download button too.
const { app, shell } = require('electron');

const RELEASES = 'https://github.com/marshenmanhunter/marshenmanhunter/releases/latest';
const CHECK_EVERY = 6 * 60 * 60 * 1000;

let send = () => {};
let state = { status: 'idle', current: app.getVersion() };
let updater = null;

function set(next) { state = { ...state, ...next, current: app.getVersion() }; send(state); }

// Only the installed Windows build (NSIS) can install updates by itself.
const canSelfInstall = () => process.platform === 'win32' && !process.env.PORTABLE_EXECUTABLE_DIR;

function start(notify) {
  send = notify;
  if (!app.isPackaged) { set({ status: 'dev' }); return; }
  try { updater = require('electron-updater').autoUpdater; } catch (e) { set({ status: 'error', message: 'Update checks are not available in this build.' }); return; }
  updater.autoDownload = canSelfInstall();
  updater.autoInstallOnAppQuit = canSelfInstall();
  updater.allowPrerelease = false;
  updater.on('checking-for-update', () => set({ status: 'checking' }));
  updater.on('update-not-available', () => set({ status: 'current', checkedAt: Date.now() }));
  updater.on('update-available', info => set({ status: canSelfInstall() ? 'downloading' : 'available', version: info.version, checkedAt: Date.now() }));
  updater.on('download-progress', p => set({ status: 'downloading', percent: Math.round(p.percent || 0) }));
  updater.on('update-downloaded', info => set({ status: 'ready', version: info.version }));
  updater.on('error', err => set({ status: 'error', message: 'Could not check for updates. ' + String((err && err.message) || '').split('\n')[0].slice(0, 160) }));
  check();
  setInterval(check, CHECK_EVERY);
}

function check() {
  if (!updater) return state;
  updater.checkForUpdates().catch(() => {});
  return state;
}

function install() {
  if (updater && state.status === 'ready') { setImmediate(() => updater.quitAndInstall(false, true)); return { ok: true }; }
  shell.openExternal(RELEASES);
  return { ok: true, opened: true };
}

module.exports = { start, check, install, status: () => state, openDownload: () => shell.openExternal(RELEASES) };
