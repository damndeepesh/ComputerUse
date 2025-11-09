const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Screen capture APIs
  getSources: () => ipcRenderer.invoke('get-sources'),
  startRecording: (sourceId) => ipcRenderer.invoke('start-recording', sourceId),
  stopRecording: () => ipcRenderer.invoke('stop-recording'),
  
  // Workflow execution with nut.js
  executeWorkflowNutjs: (steps) => ipcRenderer.invoke('execute-workflow-nutjs', steps),
  cancelExecution: () => ipcRenderer.invoke('cancel-execution'),
  
  // Execution logs
  getExecutionLogs: () => ipcRenderer.invoke('get-execution-logs'),
  clearExecutionLogs: () => ipcRenderer.invoke('clear-execution-logs'),
  onExecutionLog: (callback) => {
    const subscription = (event, log) => callback(log);
    ipcRenderer.on('execution-log', subscription);
    return () => ipcRenderer.removeListener('execution-log', subscription);
  },

  // System Settings deep links
  openPrivacyPane: (pane) => ipcRenderer.invoke('open-privacy-pane', pane),
  automationSelfTest: () => ipcRenderer.invoke('automation-self-test'),
  
  // Backend status
  checkBackendStatus: () => ipcRenderer.invoke('check-backend-status'),
  onBackendError: (callback) => {
    const subscription = (event, error) => callback(error);
    ipcRenderer.on('backend-error', subscription);
    return () => ipcRenderer.removeListener('backend-error', subscription);
  },
  onBackendLog: (callback) => {
    const subscription = (event, log) => callback(log);
    ipcRenderer.on('backend-log', subscription);
    return () => ipcRenderer.removeListener('backend-log', subscription);
  },
  onBackendErrorLog: (callback) => {
    const subscription = (event, error) => callback(error);
    ipcRenderer.on('backend-error-log', subscription);
    return () => ipcRenderer.removeListener('backend-error-log', subscription);
  },
  onBackendStatus: (callback) => {
    const subscription = (event, status) => callback(status);
    ipcRenderer.on('backend-status', subscription);
    return () => ipcRenderer.removeListener('backend-status', subscription);
  },
});


