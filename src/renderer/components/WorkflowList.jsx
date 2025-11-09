import React from 'react';
import { FileText, Trash2, Clock } from 'lucide-react';

function WorkflowList({ workflows, selectedWorkflow, onSelectWorkflow, onDeleteWorkflow }) {
  const formatDate = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  return (
    <div className="p-6">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-white mb-2">Workflows</h2>
        <p className="text-sm text-slate-400">{workflows.length} total workflows</p>
      </div>

      {workflows.length === 0 ? (
        <div className="text-center py-12">
          <FileText className="mx-auto text-slate-600 mb-4" size={48} />
          <p className="text-slate-400 mb-2">No workflows yet</p>
          <p className="text-sm text-slate-500">Start recording to create your first workflow</p>
        </div>
      ) : (
        <div className="space-y-3">
          {workflows.map((workflow) => (
            <div
              key={workflow.id}
              onClick={() => onSelectWorkflow(workflow)}
              className={`workflow-card cursor-pointer p-4 rounded-lg border transition ${
                selectedWorkflow?.id === workflow.id
                  ? 'bg-blue-600/20 border-blue-500'
                  : 'bg-slate-800/50 border-slate-700 hover:border-slate-600'
              }`}
            >
              <div className="flex items-start justify-between mb-2">
                <h3 className="font-semibold text-white flex-1 pr-2">
                  {workflow.name || `Workflow ${workflow.id}`}
                </h3>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteWorkflow(workflow.id);
                  }}
                  className="p-1 hover:bg-red-500/20 rounded transition text-slate-400 hover:text-red-400"
                >
                  <Trash2 size={16} />
                </button>
              </div>

              <p className="text-sm text-slate-400 mb-3 line-clamp-2">
                {workflow.description || 'No description'}
              </p>

              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-500">
                  {workflow.steps?.length || 0} steps
                </span>
                <div className="flex items-center text-slate-500">
                  <Clock size={12} className="mr-1" />
                  {formatDate(workflow.created_at)}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default WorkflowList;


