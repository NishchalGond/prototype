import React, { useEffect, useState } from 'react';
import { Activity, Terminal, RefreshCw, ArrowRight } from 'lucide-react';
import Tilt3DCard from './Tilt3DCard';
import { apiFetch } from '../lib/api';

export default function LiveProcessingTracker({ jobId, onJobCompleted, setActiveTab }) {
  const [jobState, setJobState] = useState(null);
  const [errorLogs, setErrorLogs] = useState([]);
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    if (!jobId) return;

    const pollInterval = setInterval(async () => {
      try {
        const res = await apiFetch(`/api/jobs/${jobId}`);
        if (res.ok) {
          const data = await res.json();
          setJobState(data);

          setLogs((prev) => {
            const timeStr = new Date().toLocaleTimeString();
            const newLog = `[${timeStr}] Batch ${data.current_batch}/${data.total_batches} | Status: ${data.status} | Processed ${data.processed_rows}/${data.total_rows} rows`;
            if (prev.length === 0 || prev[prev.length - 1] !== newLog) {
              return [...prev.slice(-15), newLog];
            }
            return prev;
          });

          if (data.status === 'COMPLETED' || data.status === 'COMPLETED_WITH_ERRORS' || data.status === 'FAILED') {
            clearInterval(pollInterval);
            fetchErrors();
            if (onJobCompleted) onJobCompleted();
          }
        }
      } catch (err) {
        console.error('Polling error:', err);
      }
    }, 700);

    return () => clearInterval(pollInterval);
  }, [jobId]);

  const fetchErrors = async () => {
    try {
      const res = await apiFetch(`/api/jobs/${jobId}/errors`);
      if (res.ok) {
        const data = await res.json();
        setErrorLogs(data.errors || []);
      }
    } catch (err) {
      console.error('Error fetching job error log:', err);
    }
  };

  if (!jobState) {
    return (
      <Tilt3DCard className="p-8 max-w-4xl mx-auto text-center space-y-3">
        <RefreshCw className="w-6 h-6 text-blue-600 animate-spin mx-auto" />
        <p className="text-xs text-slate-600 font-mono">Connecting to Python batch execution engine for Job #{jobId}...</p>
      </Tilt3DCard>
    );
  }

  const steps = ['UPLOADED', 'READING', 'PROCESSING', 'VALIDATING', 'SAVING', 'COMPLETED'];

  const getStepStatus = (stepName) => {
    const order = ['UPLOADED', 'READING', 'PROCESSING', 'VALIDATING', 'SAVING', 'COMPLETED', 'COMPLETED_WITH_ERRORS'];
    const currentIndex = order.indexOf(jobState.status);
    const stepIndex = order.indexOf(stepName);

    if (jobState.status.startsWith('COMPLETED')) return 'completed';
    if (stepIndex < currentIndex) return 'completed';
    if (stepIndex === currentIndex) return 'active';
    return 'upcoming';
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <span className="text-[10px] font-mono uppercase text-blue-700 font-bold px-3 py-1 rounded-full bg-[#eef0f4] border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc]">
            Execution Run #{jobId}
          </span>
          <h2 className="text-xl font-black text-slate-900 tracking-tight mt-2">{jobState.filename}</h2>
        </div>
        <span
          className={`px-3 py-1 text-xs font-bold font-mono rounded-full border ${
            jobState.status === 'COMPLETED'
              ? 'bg-[#eef0f4] text-emerald-700 border-emerald-300 shadow-[inset_2px_2px_4px_#cbd2dc]'
              : jobState.status === 'COMPLETED_WITH_ERRORS'
              ? 'bg-[#eef0f4] text-amber-700 border-amber-300 shadow-[inset_2px_2px_4px_#cbd2dc]'
              : jobState.status === 'FAILED'
              ? 'bg-[#eef0f4] text-rose-700 border-rose-300 shadow-[inset_2px_2px_4px_#cbd2dc]'
              : 'bg-[#eef0f4] text-blue-700 border-blue-300 shadow-[inset_2px_2px_4px_#cbd2dc]'
          }`}
        >
          {jobState.status}
        </span>
      </div>

      {/* Engine Diagnostic Callout Banner */}
      {jobState.message && (
        <div className={`p-4 rounded-2xl border text-xs font-mono space-y-1 bg-[#eef0f4] shadow-[inset_3px_3px_6px_#cbd2dc] ${
          jobState.status === 'FAILED' ? 'border-rose-300 text-rose-700' : 'border-blue-300 text-blue-700'
        }`}>
          <span className="font-bold block uppercase text-[10px] tracking-wider">
            {jobState.status === 'FAILED' ? '⚠ Engine Execution Diagnostic Error:' : 'ℹ Engine Processing Notice:'}
          </span>
          <p className="leading-relaxed font-semibold">{jobState.message}</p>
        </div>
      )}

      {/* Pipeline Stepper */}
      <Tilt3DCard className="p-6">
        <div className="flex justify-between items-center relative">
          <div className="absolute left-0 right-0 top-1/2 h-1 bg-slate-300/80 -z-10 transform -translate-y-1/2"></div>

          {steps.map((step, idx) => {
            const status = getStepStatus(step);
            return (
              <div key={idx} className="flex flex-col items-center space-y-2 bg-[#eef0f4] px-2.5 py-1 rounded-xl border border-white/80 shadow-[3px_3px_6px_#cbd2dc]">
                <div
                  className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                    status === 'completed'
                      ? 'bg-emerald-600 text-white'
                      : status === 'active'
                      ? 'bg-blue-600 text-white animate-pulse'
                      : 'bg-slate-300 text-slate-600'
                  }`}
                >
                  {status === 'completed' ? '✓' : idx + 1}
                </div>
                <span className={`text-[10px] font-mono uppercase font-bold ${
                  status === 'completed' ? 'text-emerald-700' : status === 'active' ? 'text-blue-600' : 'text-slate-500'
                }`}>
                  {step}
                </span>
              </div>
            );
          })}
        </div>
      </Tilt3DCard>

      {/* Progress Bar & Key Metrics */}
      <Tilt3DCard className="p-6 space-y-6">
        <div className="space-y-2">
          <div className="flex justify-between text-xs font-mono font-bold">
            <span className="text-slate-800">BATCH PROGRESS: Batch {jobState.current_batch} / {jobState.total_batches}</span>
            <span className="text-blue-600">{jobState.progress_pct}%</span>
          </div>
          <div className="h-3 w-full bg-[#eef0f4] rounded-full overflow-hidden p-0.5 border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc,inset_-2px_-2px_4px_#ffffff]">
            <div
              className="h-full bg-blue-600 rounded-full transition-all duration-300"
              style={{ width: `${jobState.progress_pct}%` }}
            ></div>
          </div>
        </div>

        {/* Live Counters */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono">
          <div className="p-3.5 rounded-2xl bg-[#eef0f4] border border-slate-300/80 shadow-[inset_3px_3px_6px_#cbd2dc]">
            <span className="text-[10px] text-slate-500 block font-bold">TOTAL PROCESSED</span>
            <span className="text-sm font-black text-slate-900">{jobState.processed_rows} / {jobState.total_rows}</span>
          </div>
          <div className="p-3.5 rounded-2xl bg-[#eef0f4] border border-emerald-300/80 shadow-[inset_3px_3px_6px_#cbd2dc]">
            <span className="text-[10px] text-emerald-700 block font-bold">VALID RECORDS</span>
            <span className="text-sm font-black text-emerald-700">{jobState.valid_rows}</span>
          </div>
          <div className="p-3.5 rounded-2xl bg-[#eef0f4] border border-amber-300/80 shadow-[inset_3px_3px_6px_#cbd2dc]">
            <span className="text-[10px] text-amber-700 block font-bold">DUPLICATES FLAGGED</span>
            <span className="text-sm font-black text-amber-700">{jobState.duplicate_rows}</span>
          </div>
          <div className="p-3.5 rounded-2xl bg-[#eef0f4] border border-rose-300/80 shadow-[inset_3px_3px_6px_#cbd2dc]">
            <span className="text-[10px] text-rose-700 block font-bold">VALIDATION ERRORS</span>
            <span className="text-sm font-black text-rose-700">{jobState.error_rows}</span>
          </div>
        </div>
      </Tilt3DCard>

      {/* Terminal Stream */}
      <Tilt3DCard className="p-5 space-y-3">
        <div className="flex items-center justify-between border-b border-slate-300/60 pb-3">
          <div className="flex items-center space-x-2 text-xs font-bold text-slate-800 font-mono">
            <Terminal className="w-4 h-4 text-blue-600" />
            <span>BATCH ENGINE TERMINAL STREAM</span>
          </div>
          <span className="text-[10px] font-mono text-slate-500">Socket Stream Sync</span>
        </div>

        <div className="neumorph-inset p-4 rounded-2xl font-mono text-xs text-blue-700 space-y-1.5 h-36 overflow-y-auto">
          {logs.map((logLine, i) => (
            <p key={i} className="leading-relaxed">{logLine}</p>
          ))}
        </div>
      </Tilt3DCard>

      {/* Next Actions */}
      {(jobState.status.startsWith('COMPLETED') || jobState.status === 'FAILED') && (
        <div className="flex justify-end space-x-3">
          <button
            onClick={() => setActiveTab('records')}
            className="neumorph-button-primary px-6 py-3 text-xs font-bold flex items-center space-x-2"
          >
            <span>Explore Clean Processed Records</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
}
