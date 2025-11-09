import React from 'react';
import { Activity, Zap, Clock, CheckCircle } from 'lucide-react';

function Dashboard({ workflows }) {
  const totalWorkflows = workflows.length;
  const totalSteps = workflows.reduce((acc, w) => acc + (w.steps?.length || 0), 0);
  const avgStepsPerWorkflow = totalWorkflows > 0 ? (totalSteps / totalWorkflows).toFixed(1) : 0;

  return (
    <div className="p-8">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-12">
          <h2 className="text-4xl font-bold text-white mb-4">Welcome to AGI Assistant</h2>
          <p className="text-slate-400 text-lg">
            Watch, learn, and automate your desktop workflows with AI
          </p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-3 gap-6 mb-12">
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 backdrop-blur-sm">
            <div className="flex items-center justify-between mb-4">
              <Activity className="text-blue-500" size={28} />
              <span className="text-3xl font-bold text-white">{totalWorkflows}</span>
            </div>
            <p className="text-slate-400">Total Workflows</p>
          </div>

          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 backdrop-blur-sm">
            <div className="flex items-center justify-between mb-4">
              <Zap className="text-yellow-500" size={28} />
              <span className="text-3xl font-bold text-white">{totalSteps}</span>
            </div>
            <p className="text-slate-400">Total Steps</p>
          </div>

          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 backdrop-blur-sm">
            <div className="flex items-center justify-between mb-4">
              <Clock className="text-green-500" size={28} />
              <span className="text-3xl font-bold text-white">{avgStepsPerWorkflow}</span>
            </div>
            <p className="text-slate-400">Avg Steps/Workflow</p>
          </div>
        </div>

        {/* Getting Started */}
        <div className="bg-gradient-to-br from-blue-600/20 to-purple-600/20 border border-blue-500/30 rounded-xl p-8">
          <h3 className="text-2xl font-bold text-white mb-6">Getting Started</h3>
          <div className="space-y-4">
            <div className="flex items-start space-x-4">
              <div className="flex-shrink-0 w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center text-white font-bold">
                1
              </div>
              <div>
                <h4 className="text-white font-semibold mb-1">Start Recording</h4>
                <p className="text-slate-300">Click "Start Recording" and perform your workflow normally</p>
              </div>
            </div>

            <div className="flex items-start space-x-4">
              <div className="flex-shrink-0 w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center text-white font-bold">
                2
              </div>
              <div>
                <h4 className="text-white font-semibold mb-1">AI Analysis</h4>
                <p className="text-slate-300">Our AI will analyze your actions and create a workflow</p>
              </div>
            </div>

            <div className="flex items-start space-x-4">
              <div className="flex-shrink-0 w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center text-white font-bold">
                3
              </div>
              <div>
                <h4 className="text-white font-semibold mb-1">Automate</h4>
                <p className="text-slate-300">Click play on any workflow to automate it instantly</p>
              </div>
            </div>
          </div>
        </div>

        {/* Features */}
        <div className="mt-12 grid grid-cols-2 gap-6">
          <div className="bg-slate-800/30 border border-slate-700 rounded-xl p-6">
            <CheckCircle className="text-green-500 mb-3" size={24} />
            <h4 className="text-white font-semibold mb-2">100% Local</h4>
            <p className="text-slate-400 text-sm">All processing happens on your machine. Your data never leaves.</p>
          </div>

          <div className="bg-slate-800/30 border border-slate-700 rounded-xl p-6">
            <CheckCircle className="text-green-500 mb-3" size={24} />
            <h4 className="text-white font-semibold mb-2">AI-Powered</h4>
            <p className="text-slate-400 text-sm">Uses Phi-3 to understand and automate complex workflows.</p>
          </div>

          <div className="bg-slate-800/30 border border-slate-700 rounded-xl p-6">
            <CheckCircle className="text-green-500 mb-3" size={24} />
            <h4 className="text-white font-semibold mb-2">Smart Learning</h4>
            <p className="text-slate-400 text-sm">Recognizes patterns and suggests automations automatically.</p>
          </div>

          <div className="bg-slate-800/30 border border-slate-700 rounded-xl p-6">
            <CheckCircle className="text-green-500 mb-3" size={24} />
            <h4 className="text-white font-semibold mb-2">Full Control</h4>
            <p className="text-slate-400 text-sm">Edit, pause, or stop any automation at any time.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;


