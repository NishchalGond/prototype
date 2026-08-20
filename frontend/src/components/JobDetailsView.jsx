import React, { useEffect, useState } from 'react';
import { AlertTriangle, RefreshCw, Activity } from 'lucide-react';
import Tilt3DCard from './Tilt3DCard';

export default function JobDetailsView({ selectedJobId, setSelectedJobId }) {
  const [jobs, setJobs] = useState([]);
  const [activeJobData, setActiveJobData] = useState(null);
  const [errors, setErrors] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchJobsList();
  }, []);

  useEffect(() => {
    if (selectedJobId) {
      fetchJobDetails(selectedJobId);
    }
  }, [selectedJobId]);

  const fetchJobsList = async () => {
    try {
      const res = await fetch('/api/jobs');
      if (res.ok) {
        const data = await res.json();
        const jobList = data.items || data.jobs || [];
        setJobs(jobList);
        if (jobList.length > 0 && !selectedJobId) {
          setSelectedJobId(jobList[0].id);
        }
      }
    } catch (err) {
      console.error('Error fetching jobs:', err);
    }
  };

  const fetchJobDetails = async (jobId) => {
    setLoading(true);
    try {
      const [statusRes, errorRes] = await Promise.all([
        fetch(`/api/jobs/${jobId}`),
        fetch(`/api/jobs/${jobId}/errors`)
      ]);

      if (statusRes.ok) {
        const sData = await statusRes.json();
        setActiveJobData(sData);
      }
      if (errorRes.ok) {
        const eData = await errorRes.json();
        setErrors(eData.errors || []);
      }
    } catch (err) {
      console.error('Error fetching job audit details:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 h-full w-full max-w-[1450px] mx-auto flex flex-col min-h-0 overflow-hidden space-y-4">
      {/* Title Header (Fixed Top) */}
      <Tilt3DCard className="p-5 rounded-3xl flex-shrink-0">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <div className="flex items-center space-x-2">
              <span className="px-3 py-1 rounded-full bg-[#eef0f4] text-blue-600 font-mono text-[10px] font-black tracking-wider border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc,inset_-2px_-2px_4px_#ffffff]">
                AUDIT ENGINE LOGS
              </span>
            </div>
            <h2 className="text-2xl font-black text-slate-800 tracking-tight mt-2">Job Execution Audit & Errors</h2>
            <p className="text-xs text-slate-600 mt-1 font-medium">
              Detailed batch execution history and row-level validation error audit logs.
            </p>
          </div>
        </div>
      </Tilt3DCard>

      {/* Main 2-Column Dashboard Panel (Fits Viewport Height) */}
      <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-3 gap-4 overflow-hidden">
        {/* Left Column: History List */}
        <Tilt3DCard className="lg:col-span-1 p-4 rounded-3xl flex flex-col min-h-0 overflow-hidden">
          <div className="flex items-center justify-between border-b border-slate-300/60 pb-3 flex-shrink-0">
            <div className="flex items-center space-x-2">
              <Activity className="w-4 h-4 text-blue-600" />
              <span className="text-xs font-bold text-slate-800 tracking-wide">Execution Runs</span>
            </div>
            <button onClick={fetchJobsList} className="neumorph-button p-1.5 text-slate-600 hover:text-slate-900" title="Refresh list">
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto pr-1 space-y-2.5 mt-3">
            {jobs.map((job) => {
              const isSelected = selectedJobId === job.id;
              return (
                <button
                  key={job.id}
                  onClick={() => setSelectedJobId(job.id)}
                  className={`w-full text-left p-3.5 rounded-2xl transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-[#eef0f4] border border-blue-300 shadow-[inset_3px_3px_6px_#cbd2dc,inset_-3px_-3px_6px_#ffffff]'
                      : 'bg-[#eef0f4] border border-white/80 shadow-[4px_4px_10px_#cbd2dc,-4px_-4px_10px_#ffffff] hover:bg-slate-100'
                  }`}
                >
                  <div className="flex justify-between items-start">
                    <span className="font-mono text-xs font-bold text-blue-600">#{job.id}</span>
                    <span
                      className={`text-[9px] font-mono font-bold px-2 py-0.5 rounded-full uppercase border ${
                        job.status === 'COMPLETED'
                          ? 'bg-[#eef0f4] text-emerald-700 border-emerald-300 shadow-[inset_2px_2px_4px_#cbd2dc]'
                          : 'bg-[#eef0f4] text-amber-700 border-amber-300 shadow-[inset_2px_2px_4px_#cbd2dc]'
                      }`}
                    >
                      {job.status}
                    </span>
                  </div>
                  <p className="text-xs text-slate-800 font-bold truncate mt-1.5">{job.filename}</p>
                  <div className="flex justify-between text-[10px] text-slate-500 font-mono mt-2 pt-2 border-t border-slate-300/40">
                    <span>Rows: {job.total_rows?.toLocaleString() || 0}</span>
                    <span className="text-rose-600 font-bold">Errors: {job.error_rows || 0}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </Tilt3DCard>

        {/* Right Column: Selected Job Details */}
        <div className="lg:col-span-2 flex flex-col min-h-0 overflow-hidden space-y-4">
          {activeJobData ? (
            <>
              {/* Summary Card */}
              <Tilt3DCard className="p-5 rounded-3xl space-y-3 flex-shrink-0">
                <div className="flex justify-between items-center border-b border-slate-300/60 pb-3">
                  <div>
                    <span className="text-[10px] font-mono text-blue-600 font-bold uppercase">Audit Scope #{activeJobData.id}</span>
                    <h3 className="text-base font-bold text-slate-800">{activeJobData.filename}</h3>
                  </div>
                  <span className="text-xs font-mono text-slate-500 font-bold">Batch Size: {activeJobData.batch_size}</span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
                  <div className="p-3.5 rounded-2xl bg-[#eef0f4] border border-slate-300/80 shadow-[inset_3px_3px_6px_#cbd2dc]">
                    <span className="text-slate-500 text-[10px] block font-semibold">TOTAL ROWS</span>
                    <span className="text-slate-900 font-black text-sm">{activeJobData.total_rows?.toLocaleString()}</span>
                  </div>
                  <div className="p-3.5 rounded-2xl bg-[#eef0f4] border border-emerald-300/80 shadow-[inset_3px_3px_6px_#cbd2dc]">
                    <span className="text-emerald-700 text-[10px] block font-semibold">VALID ROWS</span>
                    <span className="text-emerald-700 font-black text-sm">{activeJobData.valid_rows?.toLocaleString()}</span>
                  </div>
                  <div className="p-3.5 rounded-2xl bg-[#eef0f4] border border-amber-300/80 shadow-[inset_3px_3px_6px_#cbd2dc]">
                    <span className="text-amber-700 text-[10px] block font-semibold">DUPLICATES</span>
                    <span className="text-amber-700 font-black text-sm">{activeJobData.duplicate_rows?.toLocaleString()}</span>
                  </div>
                  <div className="p-3.5 rounded-2xl bg-[#eef0f4] border border-rose-300/80 shadow-[inset_3px_3px_6px_#cbd2dc]">
                    <span className="text-rose-700 text-[10px] block font-semibold">ERRORS LOGGED</span>
                    <span className="text-rose-700 font-black text-sm">{activeJobData.error_rows?.toLocaleString()}</span>
                  </div>
                </div>
              </Tilt3DCard>

              {/* Row Errors Table */}
              <Tilt3DCard className="p-5 rounded-3xl flex-1 flex flex-col min-h-0 overflow-hidden space-y-3">
                <div className="flex items-center space-x-2 border-b border-slate-300/60 pb-3 flex-shrink-0">
                  <AlertTriangle className="w-4 h-4 text-rose-600" />
                  <h3 className="text-sm font-bold text-slate-800">Row-Level Error Trail ({errors.length})</h3>
                </div>

                <div className="overflow-auto flex-1 min-h-0">
                  <table className="w-full text-left text-xs font-mono">
                    <thead>
                      <tr className="border-b border-slate-300/80 text-slate-500 text-[11px] bg-[#eef0f4] sticky top-0 z-10">
                        <th className="p-2.5 font-bold">BATCH</th>
                        <th className="p-2.5 font-bold">ROW INDEX</th>
                        <th className="p-2.5 font-bold">FIELD</th>
                        <th className="p-2.5 font-bold">ERROR REASON</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 font-sans">
                      {errors.length > 0 ? (
                        errors.map((errItem, idx) => (
                          <tr key={idx} className="hover:bg-slate-100/80">
                            <td className="p-2.5 font-mono text-slate-600 font-bold">{errItem.batch || 1}</td>
                            <td className="p-2.5 font-mono text-slate-600">{errItem.row_index || errItem.row}</td>
                            <td className="p-2.5 font-mono text-rose-600 font-bold">{errItem.field || 'General'}</td>
                            <td className="p-2.5 text-slate-700 font-medium">{errItem.reason || errItem.error_message}</td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan="4" className="py-10 text-center text-slate-500 font-mono text-xs">
                            No row-level errors recorded for this job run.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </Tilt3DCard>
            </>
          ) : (
            <Tilt3DCard className="p-8 text-center text-slate-500 font-mono text-xs flex-1 flex items-center justify-center">
              Select an execution run from the left history panel to view detailed audit logs.
            </Tilt3DCard>
          )}
        </div>
      </div>
    </div>
  );
}
