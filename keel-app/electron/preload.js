// Exposes a narrow API to the page: save a text file through the OS dialog, and bank sync.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('keelNative', {
  platform: process.platform,
  saveFile: (name, text) => ipcRenderer.invoke('keel:save-file', String(name), String(text)),
  // Bank sync through SimpleFIN. The access key stays in the main process; the page only sees results.
  bank: {
    status: () => ipcRenderer.invoke('keel:bank-status'),
    claim: token => ipcRenderer.invoke('keel:bank-claim', String(token)),
    accounts: p => ipcRenderer.invoke('keel:bank-accounts', { startDate: p && +p.startDate, balancesOnly: !!(p && p.balancesOnly) }),
    disconnect: () => ipcRenderer.invoke('keel:bank-disconnect')
  }
});
