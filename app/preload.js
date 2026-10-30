'use strict';
const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('agentgen', {
  onStatus: cb => ipcRenderer.on('agentgen:status', (_e, name, s) => cb(name, s)),
  onLog: cb => ipcRenderer.on('agentgen:log', (_e, line) => cb(line)),
  status: () => ipcRenderer.invoke('agentgen:status'),
  quit: () => ipcRenderer.invoke('agentgen:quit'),
  uninstall: () => ipcRenderer.invoke('agentgen:uninstall'),
  setup: {
    plan: () => ipcRenderer.invoke('agentgen:setup:plan'),
    start: () => ipcRenderer.invoke('agentgen:setup:start'),
    choose: () => ipcRenderer.invoke('agentgen:setup:choose'),
    onEvent: cb => ipcRenderer.on('agentgen:setup:event', (_e, ev) => cb(ev)),
  },
  isApp: true,
});
