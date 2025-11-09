import React, { useState, useEffect } from 'react';
import { Play, Square, Trash2, CheckCircle, Code, List, Terminal, Volume2, X } from 'lucide-react';

function App() {
  const [workflows, setWorkflows] = useState([]);
  const [selectedWorkflow, setSelectedWorkflow] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeTab, setActiveTab] = useState('steps'); // 'steps', 'json', 'logs'
  const [executionLogs, setExecutionLogs] = useState([]);
  const [isExecuting, setIsExecuting] = useState(false);
  const [showAudioModal, setShowAudioModal] = useState(false);
  const [audioData, setAudioData] = useState(null);
  const [loadingAudio, setLoadingAudio] = useState(false);
  const [showPermsModal, setShowPermsModal] = useState(false);
  const [backendError, setBackendError] = useState(null);
  const [backendStatus, setBackendStatus] = useState(null);

  // Run a quick automation self-test on load to decide if we should show the permissions modal
  useEffect(() => {
    (async () => {
      try {
        const result = await window.electronAPI?.automationSelfTest?.();
        if (!result?.success) {
          console.warn('Automation self-test failed:', result?.error, result?.details);
          setShowPermsModal(true);
        } else {
          console.log('✅ Automation self-test passed');
        }
      } catch (e) {
        console.error('Automation self-test error:', e);
        // If test fails unexpectedly, show modal
        setShowPermsModal(true);
      }
    })();
  }, []);

  // Fetch recording status from backend
  useEffect(() => {
    let retryCount = 0;
    const checkStatus = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/recording/status');
        if (response.ok) {
          const data = await response.json();
          setIsRecording(data.is_recording);
          retryCount = 0; // Reset on success
        }
      } catch (error) {
        // Only log errors after backend should be ready (30 seconds)
        if (retryCount > 30) {
          console.error('Error fetching status:', error);
        }
        retryCount++;
      }
    };
    
    checkStatus();
    const statusInterval = setInterval(checkStatus, 1000); // Check every second
    return () => clearInterval(statusInterval);
  }, []);

  // Fetch workflows
  useEffect(() => {
    fetchWorkflows();
    const interval = setInterval(fetchWorkflows, 3000); // Poll more frequently
    return () => clearInterval(interval);
  }, []);

  // Listen to execution logs from Electron
  useEffect(() => {
    if (window.electronAPI?.onExecutionLog) {
      const unsubscribe = window.electronAPI.onExecutionLog((log) => {
        setExecutionLogs(prev => [...prev, log]);
      });
      return unsubscribe;
    }
  }, []);

  // Listen to backend errors and status
  useEffect(() => {
    if (window.electronAPI?.onBackendError) {
      const unsubscribe = window.electronAPI.onBackendError((error) => {
        console.error('Backend error received:', error);
        setBackendError(error);
        setBackendStatus(null);
      });
      return unsubscribe;
    }
  }, []);

  useEffect(() => {
    if (window.electronAPI?.onBackendStatus) {
      const unsubscribe = window.electronAPI.onBackendStatus((status) => {
        console.log('Backend status:', status);
        setBackendStatus(status);
        if (status.status === 'ready') {
          setBackendError(null);
        }
      });
      return unsubscribe;
    }
  }, []);

  useEffect(() => {
    if (window.electronAPI?.onBackendLog) {
      const unsubscribe = window.electronAPI.onBackendLog((log) => {
        console.log('[Backend]', log);
      });
      return unsubscribe;
    }
  }, []);

  useEffect(() => {
    if (window.electronAPI?.onBackendErrorLog) {
      const unsubscribe = window.electronAPI.onBackendErrorLog((error) => {
        console.error('[Backend Error]', error);
      });
      return unsubscribe;
    }
  }, []);

  // Global Escape handler to cancel execution
  useEffect(() => {
    if (!isExecuting) return;
    const onKeyDown = async (e) => {
      if (e.key === 'Escape') {
        try {
          await window.electronAPI?.cancelExecution?.();
          setExecutionLogs(prev => [...prev, `[${new Date().toISOString()}] 🛑 Cancel requested (Esc)`]);
        } catch (err) {
          console.error('Cancel failed:', err);
        }
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isExecuting]);

  const fetchWorkflows = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/workflows');
      if (response.ok) {
        const data = await response.json();
        setWorkflows(data);
        setIsProcessing(false); // Done processing
        
        // Log workflow step counts for debugging
        if (data && data.length > 0) {
          data.forEach(w => {
            if (w.steps && w.steps.length === 0) {
              console.warn(`⚠️ Workflow "${w.name}" (ID: ${w.id}) has 0 steps`);
            }
          });
        }
      }
    } catch (error) {
      // Only log if backend should be ready (after initial startup period)
      // Connection refused during startup is expected
      if (!error.message.includes('Failed to fetch') || error.message.includes('timeout')) {
        console.error('Error fetching workflows:', error);
      }
    }
  };

  const handleStartRecording = async () => {
    try {
      console.log('🎬 START RECORDING clicked');
      const response = await fetch('http://localhost:8000/api/recording/start', { method: 'POST' });
      const data = await response.json();
      console.log('START response:', data);
      if (response.ok) {
        setIsRecording(true);
        console.log('✅ Recording STARTED');
      }
    } catch (error) {
      console.error('❌ Error starting recording:', error);
    }
  };

  const handleStopRecording = async () => {
    try {
      console.log('⏹️ STOP RECORDING clicked');
      // Immediately update UI to show stop button is responsive
      setIsRecording(false);
      setIsProcessing(true);
      
      // Make the API call with timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout (increased)
      
      try {
        const response = await fetch('http://localhost:8000/api/recording/stop', { 
          method: 'POST',
          signal: controller.signal,
          headers: {
            'Content-Type': 'application/json'
          }
        });
        clearTimeout(timeoutId);
        
        const data = await response.json();
        console.log('STOP response:', data);
        
        // Always update state based on response, even if request had errors
        if (data.is_recording === false) {
          setIsRecording(false);
          console.log('✅ Recording state: STOPPED');
        }
        
        if (response.ok && data.success) {
          console.log('✅ Recording STOPPED, processing workflow...');
          // Fetch workflows more aggressively after stop
          setTimeout(fetchWorkflows, 1000);
          setTimeout(fetchWorkflows, 3000);
          setTimeout(fetchWorkflows, 5000);
        } else {
          console.error('❌ Stop recording failed:', data);
          // Still update state to false if the response says it's not recording
          if (data.is_recording === false) {
            setIsRecording(false);
          }
        }
      } catch (fetchError) {
        clearTimeout(timeoutId);
        if (fetchError.name === 'AbortError') {
          console.error('❌ Stop recording request timed out after 10 seconds');
          // Even on timeout, assume recording stopped (user clicked stop button)
          setIsRecording(false);
        } else {
          console.error('❌ Error stopping recording:', fetchError);
          // Still update UI even if request failed - user clicked stop, so assume it stopped
          setIsRecording(false);
        }
      } finally {
        // Ensure processing state is cleared
        setTimeout(() => setIsProcessing(false), 2000);
      }
    } catch (error) {
      console.error('❌ Error in handleStopRecording:', error);
      // Ensure UI is updated even on error
      setIsRecording(false);
      setIsProcessing(false);
    }
  };

  const handleDeleteWorkflow = async (id) => {
    try {
      const response = await fetch(`http://localhost:8000/api/workflows/${id}`, { method: 'DELETE' });
      if (response.ok) {
        if (selectedWorkflow?.id === id) {
          setSelectedWorkflow(null);
        }
        fetchWorkflows();
      }
    } catch (error) {
      console.error('Error deleting workflow:', error);
    }
  };

  const handleOpenAudioModal = async (workflowId) => {
    setLoadingAudio(true);
    setShowAudioModal(true);
    try {
      const response = await fetch(`http://localhost:8000/api/workflows/${workflowId}/audio`);
      if (response.ok) {
        const data = await response.json();
        setAudioData(data);
      } else {
        setAudioData({ audio_files: [], transcripts: [], has_audio: false });
      }
    } catch (error) {
      console.error('Error fetching audio data:', error);
      setAudioData({ audio_files: [], transcripts: [], has_audio: false });
    } finally {
      setLoadingAudio(false);
    }
  };

  const handleExecuteWorkflow = async (id) => {
    if (!confirm('Execute this workflow? (Make sure to switch to the window where you want to execute)')) return;
    
    try {
      setIsExecuting(true);
      setExecutionLogs([]);
      setActiveTab('logs'); // Switch to logs tab
      
      // Find the workflow
      const workflow = workflows.find(w => w.id === id);
      if (!workflow) {
        alert('Workflow not found');
        return;
      }
      
      // Use nut.js for execution
      if (window.electronAPI?.executeWorkflowNutjs) {
        console.log('🚀 Executing workflow with nut.js');
        console.log('   Workflow ID:', workflow.id);
        console.log('   Workflow Name:', workflow.name);
        console.log('   Steps count:', workflow.steps?.length || 0);
        console.log('   Steps:', workflow.steps);
        
        // Log step breakdown
        if (workflow.steps && workflow.steps.length > 0) {
          const stepTypes = {};
          workflow.steps.forEach(step => {
            const action = (step?.action || 'unknown').toLowerCase();
            stepTypes[action] = (stepTypes[action] || 0) + 1;
          });
          console.log('   Step breakdown:', stepTypes);
          console.log('   First 3 steps:', workflow.steps.slice(0, 3).map(s => ({
            action: s.action,
            description: s.description?.substring(0, 50),
            x: s.x,
            y: s.y
          })));
          
          // Warn if workflow has no click/scroll actions (mouse won't move)
          const hasMouseActions = stepTypes['click'] > 0 || stepTypes['scroll'] > 0;
          if (!hasMouseActions) {
            const warningMsg = `⚠️ WARNING: This workflow has NO click or scroll actions!\n\n` +
              `Step breakdown: ${JSON.stringify(stepTypes)}\n\n` +
              `The mouse will NOT move because there are no click/scroll steps to execute.\n\n` +
              `This workflow only has: ${Object.keys(stepTypes).join(', ')}\n\n` +
              `Do you want to execute it anyway?`;
            
            if (!confirm(warningMsg)) {
              setIsExecuting(false);
              return;
            }
          }
        }
        
        if (!workflow.steps || workflow.steps.length === 0) {
          alert('Workflow has no steps to execute!');
          return;
        }
        
        const result = await window.electronAPI.executeWorkflowNutjs(workflow.steps);
        
        console.log('   Execution result:', result);
        
        if (result.success) {
          setExecutionLogs(prev => [...prev, '\n✅ Workflow completed successfully!']);
          alert('Workflow executed successfully!');
        } else {
          setExecutionLogs(prev => [...prev, `\n❌ Workflow failed: ${result.error || 'Unknown error'}`]);
          alert(`Workflow failed: ${result.error || 'Unknown error'}`);
        }
      } else {
        console.error('⚠️  nut.js executor not available, falling back to backend');
        // Fallback to backend execution
        const response = await fetch(`http://localhost:8000/api/workflows/${id}/execute`, { method: 'POST' });
        if (response.ok) {
          alert('Workflow executed!');
        } else {
          alert('Workflow execution failed!');
        }
      }
    } catch (error) {
      console.error('Error executing workflow:', error);
      setExecutionLogs(prev => [...prev, `\n❌ Error: ${error.message}`]);
      alert(`Error: ${error.message}`);
    } finally {
      setIsExecuting(false);
    }
  };

  return (
    <div className="h-screen flex flex-col bg-black text-white">
      {/* Backend Error/Status Banner */}
      {(backendError || backendStatus) && (
        <div className={`px-4 py-3 border-b ${backendError ? 'bg-red-900/20 border-red-800' : 'bg-blue-900/20 border-blue-800'}`}>
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <h3 className={`font-semibold ${backendError ? 'text-red-400' : 'text-blue-400'}`}>
                {backendError ? '⚠️ Backend Error' : 'ℹ️ Backend Status'}
              </h3>
              <p className="text-sm text-gray-300 mt-1">
                {backendError?.message || backendStatus?.message}
              </p>
              {backendError?.details && (
                <p className="text-xs text-gray-400 mt-1">{backendError.details}</p>
              )}
              {backendError?.suggestion && (
                <div className="mt-2 p-2 bg-gray-900 rounded text-xs text-gray-300 whitespace-pre-line">
                  {backendError.suggestion}
                </div>
              )}
              {backendError?.debugInfo && (
                <details className="mt-2">
                  <summary className="text-xs text-gray-500 cursor-pointer">Show Debug Info</summary>
                  <pre className="mt-1 p-2 bg-gray-900 rounded text-xs text-gray-400 overflow-auto">
                    {JSON.stringify(backendError.debugInfo, null, 2)}
                  </pre>
                </details>
              )}
            </div>
            <button
              onClick={() => {
                setBackendError(null);
                setBackendStatus(null);
              }}
              className="ml-4 text-gray-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}
      
      {/* Permission Modal */}
      {showPermsModal && (
        <div className="fixed inset-0 bg-black bg-opacity-80 flex items-center justify-center z-50">
          <div className="bg-gray-900 border border-gray-800 rounded-lg w-full max-w-lg p-4">
            <h2 className="text-lg font-bold mb-2">Grant macOS Permissions</h2>
            <p className="text-xs text-gray-300 mb-3">
              To capture and replay keyboard/mouse globally, enable Accessibility, Input Monitoring,
              and Screen Recording for this app.
            </p>
            <div className="grid grid-cols-1 gap-2 mb-3">
              <button
                onClick={() => window.electronAPI?.openPrivacyPane?.('accessibility')}
                className="px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded text-sm text-left"
              >
                Open Accessibility
              </button>
              <button
                onClick={() => window.electronAPI?.openPrivacyPane?.('inputMonitoring')}
                className="px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded text-sm text-left"
              >
                Open Input Monitoring
              </button>
              <button
                onClick={() => window.electronAPI?.openPrivacyPane?.('screenRecording')}
                className="px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded text-sm text-left"
              >
                Open Screen Recording
              </button>
            </div>
            <p className="text-[11px] text-gray-500 mb-3">
              <strong>Required permissions:</strong>
              <br />• <strong>Accessibility</strong> - Control mouse/keyboard during execution
              <br />• <strong>Input Monitoring</strong> - Capture keyboard input during recording
              <br />• <strong>Screen Recording</strong> - Capture screenshots during recording
              <br />
              <br />In each panel, find "Automato" (or your app name) and toggle it ON. If missing, run the app once,
              then reopen the panel. You may need to quit and reopen the app for changes to take effect.
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowPermsModal(false)}
                className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 rounded text-sm"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Header */}
      <div className="px-4 py-2 border-b border-gray-800 flex items-center justify-between">
        <h1 className="text-lg font-bold">AGI Assistant</h1>
        
        {isRecording ? (
          <button
            onClick={handleStopRecording}
            className="px-4 py-1.5 bg-red-600 hover:bg-red-700 rounded flex items-center gap-1.5 text-sm transition"
          >
            <Square className="w-3.5 h-3.5" />
            Stop
          </button>
        ) : (
          <button
            onClick={handleStartRecording}
            className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 rounded flex items-center gap-1.5 text-sm transition"
          >
            <Play className="w-3.5 h-3.5" />
            Record
          </button>
        )}
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Workflows Sidebar */}
        <div className="w-64 border-r border-gray-800 overflow-y-auto">
          <div className="p-3">
            <h2 className="text-xs font-semibold text-gray-400 mb-2">
              WORKFLOWS ({workflows.length})
            </h2>
            
            {workflows.length === 0 ? (
              <p className="text-gray-600 text-xs">
                No workflows yet.<br/>Start recording to create one.
              </p>
            ) : (
              <div className="space-y-1.5">
                {workflows.map((workflow) => (
                  <div
                    key={workflow.id}
                    onClick={() => setSelectedWorkflow(workflow)}
                    className={`p-2 rounded cursor-pointer border transition ${
                      selectedWorkflow?.id === workflow.id
                        ? 'bg-gray-800 border-blue-600'
                        : 'bg-gray-900 border-gray-800 hover:border-gray-700'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-1.5">
                      <div className="flex-1 min-w-0">
                        <h3 className="font-medium text-xs truncate">{workflow.name}</h3>
                        <p className="text-xs text-gray-500 mt-0.5">
                          {workflow.steps?.length || 0} steps
                        </p>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteWorkflow(workflow.id);
                        }}
                        className="text-gray-600 hover:text-red-500 transition flex-shrink-0"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Workflow Details */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {selectedWorkflow ? (
            <>
              {/* Workflow Header */}
              <div className="px-4 pt-3 pb-2 border-b border-gray-800">
                <div className="flex items-start justify-between mb-2">
                  <div className="flex-1 min-w-0">
                    <h2 className="text-lg font-bold mb-1 truncate">{selectedWorkflow.name}</h2>
                    {selectedWorkflow.description && (
                      <p className="text-gray-400 text-xs truncate">{selectedWorkflow.description}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleOpenAudioModal(selectedWorkflow.id)}
                      className="px-3 py-1.5 rounded flex items-center gap-1.5 text-sm transition bg-purple-600 hover:bg-purple-700"
                      title="View Audio & Transcript"
                    >
                      <Volume2 className="w-3.5 h-3.5" />
                      Audio
                    </button>
                    <button
                      onClick={() => handleExecuteWorkflow(selectedWorkflow.id)}
                      disabled={isExecuting}
                      className={`px-3 py-1.5 rounded flex items-center gap-1.5 text-sm transition flex-shrink-0 ${
                        isExecuting 
                          ? 'bg-gray-700 cursor-not-allowed' 
                          : 'bg-green-600 hover:bg-green-700'
                      }`}
                    >
                      <Play className="w-3.5 h-3.5" />
                      {isExecuting ? 'Running...' : 'Execute'}
                    </button>
                  </div>
                </div>

                {/* Tabs */}
                <div className="flex gap-1">
                  <button
                    onClick={() => setActiveTab('steps')}
                    className={`px-3 py-1.5 rounded-t flex items-center gap-1.5 text-xs transition ${
                      activeTab === 'steps'
                        ? 'bg-gray-900 text-white border-b-2 border-blue-600'
                        : 'bg-gray-800 text-gray-400 hover:text-white'
                    }`}
                  >
                    <List className="w-3.5 h-3.5" />
                    Steps ({selectedWorkflow.steps?.length || 0})
                  </button>
                  <button
                    onClick={() => setActiveTab('json')}
                    className={`px-3 py-1.5 rounded-t flex items-center gap-1.5 text-xs transition ${
                      activeTab === 'json'
                        ? 'bg-gray-900 text-white border-b-2 border-blue-600'
                        : 'bg-gray-800 text-gray-400 hover:text-white'
                    }`}
                  >
                    <Code className="w-3.5 h-3.5" />
                    JSON
                  </button>
                  <button
                    onClick={() => setActiveTab('logs')}
                    className={`px-3 py-1.5 rounded-t flex items-center gap-1.5 text-xs transition ${
                      activeTab === 'logs'
                        ? 'bg-gray-900 text-white border-b-2 border-blue-600'
                        : 'bg-gray-800 text-gray-400 hover:text-white'
                    }`}
                  >
                    <Terminal className="w-3.5 h-3.5" />
                    Logs
                    {executionLogs.length > 0 && (
                      <span className="bg-blue-600 text-xs px-1.5 py-0.5 rounded-full">
                        {executionLogs.length}
                      </span>
                    )}
                  </button>
                </div>
              </div>

              {/* Tab Content */}
              <div className="flex-1 overflow-y-auto p-3">
                {/* Steps Tab */}
                {activeTab === 'steps' && (
                  <div className="space-y-2">
                    {selectedWorkflow.steps?.length === 0 ? (
                      <p className="text-gray-600 text-xs">No steps recorded for this workflow.</p>
                    ) : (
                      selectedWorkflow.steps?.map((step, index) => (
                        <div key={index} className="bg-gray-900 border border-gray-800 rounded p-2.5">
                          <div className="flex items-start gap-2">
                            <div className="w-6 h-6 bg-gray-800 rounded flex items-center justify-center text-xs font-bold flex-shrink-0">
                              {index + 1}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-1.5 mb-1.5">
                                <span className="text-blue-400 font-mono text-xs px-1.5 py-0.5 bg-gray-800 rounded">
                                  {step.action}
                                </span>
                                <p className="text-xs text-gray-300 truncate">{step.description}</p>
                              </div>
                              
                              {/* Show action details */}
                              <div className="text-xs text-gray-500 font-mono">
                                {step.x !== undefined && step.y !== undefined && (
                                  <span className="mr-2">({step.x}, {step.y})</span>
                                )}
                                {step.text && (
                                  <span className="mr-2">"{step.text.substring(0, 20)}{step.text.length > 20 ? '...' : ''}"</span>
                                )}
                                {step.open_delay_seconds !== undefined && step.open_delay_seconds !== null && (
                                  <span className="mr-2">open delay: {step.open_delay_seconds}s</span>
                                )}
                                {step.keys && step.keys.length > 0 && (
                                  <span className="mr-2">{step.keys.join('+')}</span>
                                )}
                              </div>
                              
                              {step.screenshot && (
                                <img
                                  src={`http://localhost:8000${step.screenshot}`}
                                  alt={`Step ${index + 1}`}
                                  className="rounded border border-gray-700 max-w-xs mt-2"
                                  onError={(e) => e.target.style.display = 'none'}
                                />
                              )}
                            </div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}

                {/* JSON Tab */}
                {activeTab === 'json' && (
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-xs font-semibold text-gray-400">JSON</h3>
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(JSON.stringify(selectedWorkflow, null, 2));
                          alert('Copied!');
                        }}
                        className="px-2 py-1 bg-gray-800 hover:bg-gray-700 rounded text-xs"
                      >
                        Copy
                      </button>
                    </div>
                    <pre className="bg-gray-900 border border-gray-800 rounded p-2 text-xs font-mono overflow-x-auto">
                      {JSON.stringify(selectedWorkflow, null, 2)}
                    </pre>
                  </div>
                )}

                {/* Logs Tab */}
                {activeTab === 'logs' && (
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-xs font-semibold text-gray-400">LOGS</h3>
                      <button
                        onClick={() => setExecutionLogs([])}
                        className="px-2 py-1 bg-gray-800 hover:bg-gray-700 rounded text-xs"
                      >
                        Clear
                      </button>
                    </div>
                    <div className="bg-gray-900 border border-gray-800 rounded p-2 font-mono text-xs h-80 overflow-y-auto">
                      {executionLogs.length === 0 ? (
                        <p className="text-gray-600 text-xs">No logs yet.</p>
                      ) : (
                        executionLogs.map((log, index) => (
                          <div key={index} className="mb-0.5 text-gray-300">
                            {log}
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="h-full flex items-center justify-center">
              <div className="text-center">
                <CheckCircle className="w-12 h-12 text-gray-700 mx-auto mb-3" />
                <h2 className="text-lg font-bold text-gray-600">No Workflow Selected</h2>
                <p className="text-gray-700 mt-1 text-sm">Select a workflow or create a new one</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Audio & Transcript Modal */}
      {showAudioModal && (
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50">
          <div className="bg-gray-900 border border-gray-800 rounded-lg w-full max-w-3xl max-h-[90vh] flex flex-col m-4">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between">
              <h2 className="text-xl font-bold flex items-center gap-2">
                <Volume2 className="w-5 h-5" />
                Audio Recording & Transcript
              </h2>
              <button
                onClick={() => {
                  setShowAudioModal(false);
                  setAudioData(null);
                }}
                className="text-gray-400 hover:text-white transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="flex-1 overflow-y-auto p-6">
              {loadingAudio ? (
                <div className="flex items-center justify-center py-12">
                  <p className="text-gray-400">Loading audio data...</p>
                </div>
              ) : audioData && audioData.has_audio ? (
                <div className="space-y-6">
                  {/* Audio Player Section */}
                  <div>
                    <h3 className="text-sm font-semibold text-gray-400 mb-3">AUDIO RECORDING</h3>
                    {audioData.audio_files.map((audioFile, index) => {
                      const audioUrl = `http://localhost:8000${audioFile.url}`;
                      return (
                        <div key={index} className="bg-gray-800 rounded p-4 mb-4">
                          <div className="mb-3">
                            <p className="text-xs text-gray-500 mb-1">File: {audioFile.filename}</p>
                            {audioFile.exists === false && (
                              <p className="text-xs text-yellow-500 mb-1">⚠️ File may not be accessible</p>
                            )}
                          </div>
                          <audio
                            controls
                            className="w-full"
                            src={audioUrl}
                            onError={(e) => {
                              console.error('Audio load error:', e);
                              console.error('Audio URL:', audioUrl);
                              console.error('Audio file data:', audioFile);
                            }}
                            onLoadedData={() => {
                              console.log('Audio loaded successfully:', audioUrl);
                            }}
                          >
                            Your browser does not support the audio element.
                          </audio>
                          <p className="text-xs text-gray-600 mt-2">URL: {audioUrl}</p>
                        </div>
                      );
                    })}
                  </div>

                  {/* Transcript Section */}
                  <div>
                    <h3 className="text-sm font-semibold text-gray-400 mb-3">TRANSCRIPT</h3>
                    {audioData.transcripts && audioData.transcripts.length > 0 ? (
                      <div className="bg-gray-800 rounded p-4 space-y-3">
                        {audioData.transcripts.map((transcript, index) => (
                          <div key={index} className="border-b border-gray-700 last:border-b-0 pb-3 last:pb-0">
                            <p className="text-xs text-gray-500 mb-2">
                              {new Date(transcript.timestamp).toLocaleString()}
                            </p>
                            <p className="text-sm text-gray-200">{transcript.text}</p>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="bg-gray-800 rounded p-4">
                        <p className="text-gray-400 text-sm">No transcript available</p>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-center py-12">
                  <div className="text-center">
                    <Volume2 className="w-12 h-12 text-gray-700 mx-auto mb-3" />
                    <p className="text-gray-400">No audio recording available for this workflow</p>
                    <p className="text-gray-600 text-xs mt-2">Audio is recorded when you start a workflow recording</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
