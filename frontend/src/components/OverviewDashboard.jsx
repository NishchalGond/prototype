import React from 'react';
import { 
  Database, 
  FileCheck2, 
  TrendingUp, 
  Copy, 
  Upload, 
  Search, 
  ArrowRight,
  PieChart,
  Activity,
  Sparkles,
  Box
} from 'lucide-react';
import Tilt3DCard from './Tilt3DCard';
import DataLinkLogo from './DataLinkLogo';

export default function OverviewDashboard({ stats, setActiveTab, setSelectedJobId }) {
  if (!stats) {
    return (
      <div className="p-20 text-center text-slate-500 font-mono text-xs flex flex-col items-center justify-center space-y-5 h-full">
        <div className="w-16 h-16 rounded-3xl bg-[#eef0f4] p-3 border border-blue-400/40 shadow-[inset_3px_3px_6px_#cbd2dc,inset_-3px_-3px_6px_#ffffff] flex items-center justify-center animate-pulse">
          <DataLinkLogo className="w-10 h-10" />
        </div>
        <p className="text-slate-800 font-black text-sm tracking-widest uppercase">CONNECTING TO SUPABASE CLOUD...</p>
        <p className="text-slate-500 text-xs">Loading live telemetry and canonical real estate registers</p>
      </div>
    );
  }

  const statCards = [
    {
      title: 'Total Clean Records',
      value: stats.total_records.toLocaleString(),
      subtitle: `${stats.valid_records.toLocaleString()} Validated Rows`,
      icon: Database,
      badge: 'Supabase Cloud',
      iconBg: 'bg-[#eef0f4] text-blue-600 border-white/80 shadow-[inset_3px_3px_6px_#cbd2dc,inset_-3px_-3px_6px_#ffffff]',
    },
    {
      title: 'Pipeline Success Rate',
      value: `${stats.success_rate}%`,
      subtitle: `${stats.total_errors} Flagged Warnings`,
      icon: TrendingUp,
      badge: 'Real Verification',
      iconBg: 'bg-[#eef0f4] text-emerald-600 border-white/80 shadow-[inset_3px_3px_6px_#cbd2dc,inset_-3px_-3px_6px_#ffffff]',
    },
    {
      title: 'Duplicates Filtered',
      value: stats.duplicate_records.toLocaleString(),
      subtitle: 'Dedup Rules Applied',
      icon: Copy,
      badge: 'In-Engine',
      iconBg: 'bg-[#eef0f4] text-amber-600 border-white/80 shadow-[inset_3px_3px_6px_#cbd2dc,inset_-3px_-3px_6px_#ffffff]',
    },
    {
      title: 'Source Files Ingested',
      value: stats.total_files.toLocaleString(),
      subtitle: `${stats.total_jobs} Execution Runs`,
      icon: FileCheck2,
      badge: 'Multi-Format',
      iconBg: 'bg-[#eef0f4] text-violet-600 border-white/80 shadow-[inset_3px_3px_6px_#cbd2dc,inset_-3px_-3px_6px_#ffffff]',
    },
  ];

  return (
    <div className="p-6 space-y-8 relative z-10 max-w-7xl mx-auto">
      {/* Neumorphic Soft Hero Header */}
      <Tilt3DCard className="p-8">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
          <div className="space-y-2">
            <div className="flex items-center space-x-2">
              <span className="px-3 py-1 rounded-full bg-[#eef0f4] text-blue-600 font-mono text-[10px] font-black tracking-widest border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc,inset_-2px_-2px_4px_#ffffff] flex items-center space-x-1.5">
                <Sparkles className="w-3.5 h-3.5 text-blue-600" />
                <span>NEUMORPHIC DASHBOARD V4</span>
              </span>
              <span className="px-2.5 py-1 rounded-full bg-[#eef0f4] text-slate-600 font-mono text-[10px] font-bold border border-slate-300/80 shadow-[2px_2px_5px_#cbd2dc]">
                TACTILE LIGHT UI
              </span>
            </div>
            <h2 className="text-3xl md:text-4xl font-black text-slate-800 tracking-tight leading-tight">
              Real Estate Data Processing Engine
            </h2>
            <p className="text-xs md:text-sm text-slate-600 max-w-2xl font-medium">
              Real-time batch ingestion, column standardization (1 sq.m = 10.7639 sq.ft), global international phone cleaning, and row-level traceability on Supabase Cloud.
            </p>
          </div>

          <div className="flex items-center space-x-3">
            <button
              onClick={() => setActiveTab('upload')}
              className="neumorph-button-primary px-6 py-3.5 text-xs font-black flex items-center space-x-2"
            >
              <Upload className="w-4 h-4" />
              <span>Ingest Register File</span>
            </button>
            <button
              onClick={() => setActiveTab('records')}
              className="neumorph-button px-6 py-3.5 text-slate-700 font-bold text-xs flex items-center space-x-2"
            >
              <Search className="w-4 h-4 text-blue-600" />
              <span>Explore Dataset</span>
            </button>
          </div>
        </div>
      </Tilt3DCard>

      {/* Neumorphic KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {statCards.map((card, idx) => {
          const Icon = card.icon;
          return (
            <Tilt3DCard key={idx} className="p-6 space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-600 tracking-wide">{card.title}</span>
                <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-[#eef0f4] text-slate-700 border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc] font-bold">
                  {card.badge}
                </span>
              </div>

              <div className="flex items-baseline justify-between pt-1">
                <h3 className="text-3xl font-black text-slate-900 tracking-tight">{card.value}</h3>
                <div className={`p-3 rounded-2xl border ${card.iconBg}`}>
                  <Icon className="w-5 h-5" />
                </div>
              </div>

              <p className="text-[11px] text-slate-500 font-mono pt-1 border-t border-slate-300/60">{card.subtitle}</p>
            </Tilt3DCard>
          );
        })}
      </div>

      {/* Middle Section: Community Breakdown & Ingestion Audit Table */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Top Communities Distribution Card */}
        <Tilt3DCard className="p-6 space-y-5">
          <div className="flex items-center justify-between border-b border-slate-300/60 pb-3">
            <div className="flex items-center space-x-2">
              <PieChart className="w-4 h-4 text-blue-600" />
              <h3 className="text-sm font-bold text-slate-800 tracking-wide">Community Distribution</h3>
            </div>
            <span className="text-[10px] font-mono text-emerald-700 font-bold bg-[#eef0f4] px-2 py-0.5 rounded-full border border-emerald-200 shadow-[inset_2px_2px_4px_#cbd2dc]">CANONICAL REAL DATA</span>
          </div>

          <div className="space-y-4">
            {stats.community_distribution && stats.community_distribution.length > 0 ? (
              stats.community_distribution.map((item, index) => {
                const maxCount = stats.community_distribution[0]?.count || 1;
                const percentage = Math.round((item.count / maxCount) * 100);
                return (
                  <div key={index} className="space-y-1.5">
                    <div className="flex justify-between text-xs font-medium">
                      <span className="text-slate-800 truncate max-w-[180px] font-bold">{item.name}</span>
                      <span className="font-mono text-blue-600 font-bold">{item.count.toLocaleString()} records</span>
                    </div>
                    <div className="h-2.5 w-full bg-[#eef0f4] rounded-full overflow-hidden p-0.5 border border-slate-300/60 shadow-[inset_2px_2px_4px_#cbd2dc,inset_-2px_-2px_4px_#ffffff]">
                      <div
                        className="h-full bg-blue-600 rounded-full transition-all duration-500"
                        style={{ width: `${percentage}%` }}
                      ></div>
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="p-8 text-center border border-dashed border-slate-300 rounded-2xl space-y-2 bg-[#eef0f4]">
                <Box className="w-8 h-8 text-slate-400 mx-auto" />
                <p className="text-xs text-slate-600 font-medium">No records ingested yet</p>
                <p className="text-[11px] text-slate-400 font-mono">Upload an Excel register to view real community breakdown.</p>
              </div>
            )}
          </div>
        </Tilt3DCard>

        {/* Recent Ingestion Runs Table */}
        <Tilt3DCard className="lg:col-span-2 p-6 space-y-5">
          <div className="flex items-center justify-between border-b border-slate-300/60 pb-3">
            <div className="flex items-center space-x-2">
              <Activity className="w-4 h-4 text-emerald-600" />
              <h3 className="text-sm font-bold text-slate-800 tracking-wide">Ingestion Runs Audit Pipeline</h3>
            </div>
            <button
              onClick={() => setActiveTab('jobs')}
              className="text-xs text-blue-600 hover:text-blue-800 font-bold flex items-center space-x-1 cursor-pointer transition-colors"
            >
              <span>View History</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-300/80 text-slate-500 font-mono text-[11px]">
                  <th className="pb-3 font-bold">JOB ID</th>
                  <th className="pb-3 font-bold">SOURCE FILE</th>
                  <th className="pb-3 font-bold">STATUS</th>
                  <th className="pb-3 font-bold text-right">TOTAL ROWS</th>
                  <th className="pb-3 font-bold text-right">ERRORS</th>
                  <th className="pb-3 font-bold text-right">ACTION</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 font-sans">
                {(stats.recent_jobs || stats.items) && (stats.recent_jobs || stats.items).length > 0 ? (
                  (stats.recent_jobs || stats.items).map((job) => (
                    <tr key={job.id} className="hover:bg-slate-200/50 transition-colors group">
                      <td className="py-3.5 font-bold text-blue-600 font-mono">#{job.id}</td>
                      <td className="py-3.5 text-slate-800 font-medium font-sans truncate max-w-[170px]">{job.filename}</td>
                      <td className="py-3.5">
                        <span
                          className={`px-2.5 py-0.5 text-[10px] font-bold rounded-full uppercase tracking-wider border ${
                            job.status === 'COMPLETED'
                              ? 'bg-[#eef0f4] text-emerald-700 border-emerald-300 shadow-[inset_2px_2px_4px_#cbd2dc]'
                              : job.status === 'COMPLETED_WITH_ERRORS'
                              ? 'bg-[#eef0f4] text-amber-700 border-amber-300 shadow-[inset_2px_2px_4px_#cbd2dc]'
                              : job.status === 'FAILED'
                              ? 'bg-[#eef0f4] text-rose-700 border-rose-300 shadow-[inset_2px_2px_4px_#cbd2dc]'
                              : 'bg-[#eef0f4] text-blue-700 border-blue-300 shadow-[inset_2px_2px_4px_#cbd2dc]'
                          }`}
                        >
                          {job.status}
                        </span>
                      </td>
                      <td className="py-3.5 text-right font-bold text-slate-700 font-mono">{job.total_rows?.toLocaleString() || 0}</td>
                      <td className="py-3.5 text-right text-rose-600 font-bold font-mono">{job.error_rows || 0}</td>
                      <td className="py-3.5 text-right">
                        <button
                          onClick={() => {
                            setSelectedJobId(job.id);
                            setActiveTab('jobs');
                          }}
                          className="text-[11px] text-blue-600 hover:text-blue-800 underline font-bold cursor-pointer transition-colors"
                        >
                          Audit Run
                        </button>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="6" className="py-8 text-center text-slate-500 font-mono">
                      No ingestion runs recorded yet. Ingest an Excel file to begin processing.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Tilt3DCard>
      </div>
    </div>
  );
}
