'use strict';
const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('agentgen', {
  onStatus: cb => ipcRenderer.on('agentgen:status', (_e, name, s) => cb(name, s)),
  onLog: cb => ipcRenderer.on('agentgen:log', (_e, line) => cb(line)),
  status: () => ipcRenderer.invoke('agentgen:status'),
  quit: () => ipcRenderer.invoke('agentgen:quit'),
  shutdown: () => ipcRenderer.invoke('agentgen:shutdown'),
  uninstall: () => ipcRenderer.invoke('agentgen:uninstall'),
  storage: {
    list: () => ipcRenderer.invoke('agentgen:storage:list'),
    open: id => ipcRenderer.invoke('agentgen:storage:open', id),
    clear: id => ipcRenderer.invoke('agentgen:storage:clear', id),
  },
  setup: {
    plan: () => ipcRenderer.invoke('agentgen:setup:plan'),
    start: () => ipcRenderer.invoke('agentgen:setup:start'),
    onEvent: cb => ipcRenderer.on('agentgen:setup:event', (_e, ev) => cb(ev)),
  },
  isApp: true,
});
