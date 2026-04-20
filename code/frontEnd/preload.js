const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("nettower", {
  startSession: (sessionConfig) => ipcRenderer.invoke("runtime:start-session", sessionConfig),
  stopSession: () => ipcRenderer.invoke("runtime:stop-session"),
  getStatus: () => ipcRenderer.invoke("runtime:get-status"),
  getTopology: (options) => ipcRenderer.invoke("runtime:get-topology", options),
  getLocalIdentity: () => ipcRenderer.invoke("runtime:get-local-identity"),
  getSessionSettings: () => ipcRenderer.invoke("runtime:get-session-settings"),
  updateSessionSettings: (settingsPatch) => ipcRenderer.invoke("runtime:update-session-settings", settingsPatch),
});
