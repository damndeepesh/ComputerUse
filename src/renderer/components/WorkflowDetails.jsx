import React from 'react';
import { Play, Square, MousePointer, Keyboard, Clock as ClockIcon, AlertCircle } from 'lucide-react';

function WorkflowDetails({ workflow, isExecuting, executionStep, onExecute, onStopExecution }) {
  const getStepIcon = (type) => {
    switch (type) {
      case 'click':
        return <MousePointer size={16} className="text-blue-400" />;
      case 'type':
        return <Keyboard size={16} className="text-green-400" />;
      case 'wait':
        return <ClockIcon size={16} className="text-yellow-400" />;
      default:
        return <AlertCircle size={16} className="text-slate-400" />;
    }
  };

  return (
    <div className="p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-start justify-between mb-4">
            <div className="flex-1">
              <h2 className="text-3xl font-bold text-white mb-2">
                {workflow.name || `Workflow ${workflow.id}`}
              </h2>
              <p className="text-slate-400">
                {workflow.description || 'No description provided'}
              </p>
            </div>

            <div className="flex space-x-2">
              {!isExecuting ? (
                <button
                  onClick={onExecute}
                  className="flex items-center space-x-2 px-6 py-3 bg-gradient-to-r from-green-600 to-green-700 hover:from-green-700 hover:to-green-800 text-white rounded-lg transition shadow-lg shadow-green-500/30"
                >
                  <Play size={20} />
                  <span>Execute Workflow</span>
                </button>
              ) : (
                <button
                  onClick={onStopExecution}
                  className="flex items-center space-x-2 px-6 py-3 bg-red-600 hover:bg-red-700 text-white rounded-lg transition"
                >
                  <Square size={20} />
                  <span>Stop</span>
                </button>
              )}
            </div>
          </div>

          {/* Metadata */}
          <div className="flex items-center space-x-6 text-sm text-slate-400">
            <div>
              <span className="font-medium">Steps:</span> {workflow.steps?.length || 0}
            </div>
            <div>
              <span className="font-medium">Created:</span>{' '}
              {new Date(workflow.created_at).toLocaleDateString()}
            </div>
          </div>
        </div>

        {/* Execution Progress */}
        {isExecuting && (
          <div className="mb-6 p-4 bg-blue-600/20 border border-blue-500/50 rounded-lg">
            <div className="flex items-center space-x-3 mb-2">
              <div className="w-4 h-4 bg-blue-500 rounded-full recording-dot"></div>
              <span className="text-white font-medium">Executing Workflow</span>
            </div>
            <div className="w-full bg-slate-700 rounded-full h-2">
              <div
                className="bg-gradient-to-r from-blue-500 to-purple-500 h-2 rounded-full transition-all duration-300"
                style={{
                  width: `${((executionStep + 1) / (workflow.steps?.length || 1)) * 100}%`,
                }}
              ></div>
            </div>
            <div className="mt-2 text-sm text-slate-400">
              Step {executionStep + 1} of {workflow.steps?.length || 0}
            </div>
          </div>
        )}

        {/* Steps List */}
        <div className="space-y-3">
          <h3 className="text-xl font-bold text-white mb-4">Workflow Steps</h3>

          {!workflow.steps || workflow.steps.length === 0 ? (
            <div className="text-center py-12 bg-slate-800/30 border border-slate-700 rounded-lg">
              <AlertCircle className="mx-auto text-slate-600 mb-3" size={32} />
              <p className="text-slate-400">No steps in this workflow</p>
            </div>
          ) : (
            workflow.steps.map((step, index) => (
              <div
                key={index}
                className={`p-5 rounded-lg border transition ${
                  isExecuting && executionStep === index
                    ? 'step-active border-blue-500 text-white'
                    : 'bg-slate-800/50 border-slate-700 hover:border-slate-600'
                }`}
              >
                <div className="flex items-start space-x-4">
                  {/* Step Number */}
                  <div
                    className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center font-bold ${
                      isExecuting && executionStep === index
                        ? 'bg-white/20 text-white'
                        : 'bg-slate-700 text-slate-300'
                    }`}
                  >
                    {index + 1}
                  </div>

                  {/* Step Content */}
                  <div className="flex-1">
                    <div className="flex items-center space-x-2 mb-2">
                      {getStepIcon(step.action)}
                      <span className="font-semibold text-white capitalize">
                        {step.action || 'Unknown Action'}
                      </span>
                    </div>

                    <p className="text-slate-300 mb-3">
                      {step.description || 'No description'}
                    </p>

                    {/* Step Details */}
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      {step.action === 'click' && step.x !== undefined && (
                        <div className="bg-slate-900/50 p-2 rounded">
                          <span className="text-slate-500">Position:</span>{' '}
                          <span className="text-slate-300">
                            ({step.x}, {step.y})
                          </span>
                        </div>
                      )}

                      {step.action === 'type' && step.text && (
                        <div className="bg-slate-900/50 p-2 rounded col-span-2">
                          <span className="text-slate-500">Text:</span>{' '}
                          <span className="text-slate-300 font-mono">{step.text}</span>
                        </div>
                      )}

                      {step.action === 'wait' && step.duration && (
                        <div className="bg-slate-900/50 p-2 rounded">
                          <span className="text-slate-500">Duration:</span>{' '}
                          <span className="text-slate-300">{step.duration}s</span>
                        </div>
                      )}

                      {step.timestamp && (
                        <div className="bg-slate-900/50 p-2 rounded">
                          <span className="text-slate-500">Time:</span>{' '}
                          <span className="text-slate-300">
                            {new Date(step.timestamp).toLocaleTimeString()}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Screenshot Preview */}
                    {step.screenshot && (
                      <div className="mt-3">
                        <img
                          src={`http://localhost:8000${step.screenshot}`}
                          alt={`Step ${index + 1}`}
                          className="rounded border border-slate-700 max-w-sm"
                          onError={(e) => {
                            console.error('Failed to load screenshot:', step.screenshot);
                            e.target.style.display = 'none';
                          }}
                          onLoad={() => console.log('Screenshot loaded:', step.screenshot)}
                        />
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

export default WorkflowDetails;


