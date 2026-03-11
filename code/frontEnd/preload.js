const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("nettower", {
  startSession: (sessionConfig) => ipcRenderer.invoke("runtime:start-session", sessionConfig),
  stopSession: () => ipcRenderer.invoke("runtime:stop-session"),
  getStatus: () => ipcRenderer.invoke("runtime:get-status"),
  getTopology: (options) => ipcRenderer.invoke("runtime:get-topology", options),
});
