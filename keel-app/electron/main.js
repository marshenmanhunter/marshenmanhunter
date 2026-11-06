// Desktop shell for Keel. The whole app lives in web/; this file only opens a window
// and gives the page a native "Save as" dialog for exports.
const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const fs = require('fs/promises');

if (!app.requestSingleInstanceLock()) app.quit();

let win = null;
function createWindow() {
  win = new BrowserWindow({
    width: 1320,
    height: 900,
    minWidth: 380,
    minHeight: 560,
    title: 'Keel',
    backgroundColor: '#EEF2EF',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      spellcheck: false
    }
  });
  win.loadFile(path.join(__dirname, '..', 'web', 'index.html'));
  // Keep the app on its own files. Web links open in the default browser.
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//.test(url)) shell.openExternal(url);
    return { action: 'deny' };
  });
  win.webContents.on('will-navigate', (event, url) => {
    if (!url.startsWith('file://')) {
      event.preventDefault();
      if (/^https?:\/\//.test(url)) shell.openExternal(url);
    }
  });
}

ipcMain.handle('keel:save-file', async (event, name, text) => {
  const parent = BrowserWindow.fromWebContents(event.sender);
  const safe = String(name || 'keel-export.txt').replace(/[\\/:*?"<>|]/g, '_');
  const result = await dialog.showSaveDialog(parent, { defaultPath: path.join(app.getPath('documents'), safe) });
  if (result.canceled || !result.filePath) return { status: 'declined' };
  await fs.writeFile(result.filePath, String(text), 'utf8');
  return { status: 'saved' };
});

app.on('second-instance', () => {
  if (win) { if (win.isMinimized()) win.restore(); win.focus(); }
});
app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
});
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
