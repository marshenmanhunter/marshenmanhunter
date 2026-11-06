// Exposes one narrow function to the page: save a text file through the OS dialog.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('keelNative', {
  platform: process.platform,
  saveFile: (name, text) => ipcRenderer.invoke('keel:save-file', String(name), String(text))
});
