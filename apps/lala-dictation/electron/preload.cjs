const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("lalaDictation", {
  onState: (cb) => {
    const handler = (_e, data) => cb(data);
    ipcRenderer.on("overlay:state", handler);
    return () => ipcRenderer.removeListener("overlay:state", handler);
  },
  onDictationStart: (cb) => {
    const handler = () => cb();
    ipcRenderer.on("dictation:start", handler);
    return () => ipcRenderer.removeListener("dictation:start", handler);
  },
  onDictationStop: (cb) => {
    const handler = () => cb();
    ipcRenderer.on("dictation:stop", handler);
    return () => ipcRenderer.removeListener("dictation:stop", handler);
  },
  onDictationCancel: (cb) => {
    const handler = () => cb();
    ipcRenderer.on("dictation:cancel", handler);
    return () => ipcRenderer.removeListener("dictation:cancel", handler);
  },
  getSettings: () => ipcRenderer.invoke("settings:get"),
  setCleanup: (level) => ipcRenderer.invoke("settings:setCleanup", level),
  polish: (raw) => ipcRenderer.invoke("polish:run", raw),
  complete: (rawText) => ipcRenderer.invoke("dictation:complete", rawText),
  completeAudio: (arrayBuffer) =>
    ipcRenderer.invoke("dictation:completeAudio", arrayBuffer),
  setLevel: (level) => ipcRenderer.send("dictation:level", level),
  cancel: () => ipcRenderer.send("overlay:cancel"),
});
