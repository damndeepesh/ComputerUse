import React, { useState, useEffect } from 'react';
import { Video, Mic, Monitor } from 'lucide-react';

function RecordingPanel({ isPaused }) {
  const [recordingTime, setRecordingTime] = useState(0);
  const [transcript, setTranscript] = useState([]);
  const [screenshots, setScreenshots] = useState([]);

  useEffect(() => {
    if (!isPaused) {
      const interval = setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [isPaused]);

  // Poll for live transcripts and screenshots
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const response = await fetch('http://localhost:8000/api/recording/status');
        if (response.ok) {
          const data = await response.json();
          if (data.transcript) {
            setTranscript(data.transcript);
          }
          if (data.latest_screenshot) {
            setScreenshots((prev) => [data.latest_screenshot, ...prev.slice(0, 5)]);
          }
        }
      } catch (error) {
        // Silently fail - backend might not be ready
      }
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="p-8">
      <div className="max-w-4xl mx-auto">
        {/* Recording Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center space-x-3 mb-4">
            <div className="w-4 h-4 bg-red-500 rounded-full recording-dot"></div>
            <h2 className="text-3xl font-bold text-white">
              {isPaused ? 'Recording Paused' : 'Recording in Progress'}
            </h2>
          </div>
          <div className="text-5xl font-mono text-white mb-2">{formatTime(recordingTime)}</div>
          <p className="text-slate-400">
            Perform your workflow naturally - AI is watching and learning
          </p>
        </div>

        {/* Live Stats */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 text-center">
            <Monitor className="mx-auto text-blue-400 mb-2" size={24} />
            <div className="text-2xl font-bold text-white">{screenshots.length}</div>
            <div className="text-sm text-slate-400">Screenshots</div>
          </div>

          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 text-center">
            <Mic className="mx-auto text-green-400 mb-2" size={24} />
            <div className="text-2xl font-bold text-white">{transcript.length}</div>
            <div className="text-sm text-slate-400">Transcripts</div>
          </div>

          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 text-center">
            <Video className="mx-auto text-purple-400 mb-2" size={24} />
            <div className="text-2xl font-bold text-white">{formatTime(recordingTime)}</div>
            <div className="text-sm text-slate-400">Duration</div>
          </div>
        </div>

        {/* Live Preview */}
        <div className="grid grid-cols-2 gap-6">
          {/* Screenshots */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-5">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center">
              <Monitor size={20} className="mr-2 text-blue-400" />
              Recent Screenshots
            </h3>
            <div className="space-y-3">
              {screenshots.length === 0 ? (
                <p className="text-slate-500 text-sm text-center py-8">
                  Capturing screenshots...
                </p>
              ) : (
                screenshots.map((screenshot, index) => (
                  <div key={index} className="border border-slate-700 rounded overflow-hidden">
                    <img
                      src={`http://localhost:8000${screenshot}`}
                      alt={`Screenshot ${index}`}
                      className="w-full"
                    />
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Transcripts */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-5">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center">
              <Mic size={20} className="mr-2 text-green-400" />
              Live Transcription
            </h3>
            <div className="space-y-2 max-h-[400px] overflow-y-auto">
              {transcript.length === 0 ? (
                <p className="text-slate-500 text-sm text-center py-8">
                  Listening for commands...
                </p>
              ) : (
                transcript.map((item, index) => (
                  <div
                    key={index}
                    className="bg-slate-900/50 rounded p-3 border border-slate-700"
                  >
                    <div className="text-xs text-slate-500 mb-1">
                      {new Date(item.timestamp).toLocaleTimeString()}
                    </div>
                    <div className="text-slate-200">{item.text}</div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Tips */}
        <div className="mt-8 bg-blue-600/10 border border-blue-500/30 rounded-lg p-6">
          <h4 className="text-white font-semibold mb-3">Tips for Best Results</h4>
          <ul className="text-slate-300 text-sm space-y-2">
            <li>• Perform actions clearly and deliberately</li>
            <li>• Speak commands out loud for better context</li>
            <li>• Wait a moment between different actions</li>
            <li>• Avoid sensitive information (passwords, etc.)</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

export default RecordingPanel;


