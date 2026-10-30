'use strict';
const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('agentgen', {
  onStatus: cb => ipcRenderer.on('agentgen:status', (_e, name, s) => cb(name, s)),
  onLog: cb => ipcRenderer.on('agentgen:log', (_e, line) => cb(line)),
  status: () => ipcRenderer.invoke('agentgen:status'),
  isApp: true,
});
