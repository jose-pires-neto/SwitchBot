/**
 * preload.js — Ponte segura entre o processo Electron e a UI web
 */
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    isElectron:     true,
    hideWindow:     ()    => ipcRenderer.send('hide-window'),
    setIgnoreMouse: (v)   => ipcRenderer.send('set-ignore-mouse', v),
    onToggleInput:  (cb)  => ipcRenderer.on('toggle-input', () => cb()),
    onGlobalMouseMove: (cb) => ipcRenderer.on('global-mouse-move', (event, data) => cb(data)),
});
