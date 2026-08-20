import React from 'react';
import { Search, RefreshCw, Cloud } from 'lucide-react';

export default function Header({ onRefresh, activeJob, searchQuery, setSearchQuery, setActiveTab }) {
  return (
    <header className="h-16 bg-[#eef0f4] border-b border-slate-300/60 px-6 flex items-center justify-between sticky top-0 z-20 shadow-[0_4px_12px_#cbd2dc]">
      {/* Debossed Neumorphic Search Input */}
      <div className="relative w-80">
        <Search className="w-4 h-4 absolute left-3.5 top-1/2 transform -translate-y-1/2 text-blue-600" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => {
            setSearchQuery(e.target.value);
            if (e.target.value.trim().length > 0) {
              setActiveTab('records');
            }
          }}
          placeholder="Search Name, Community, Unit, Mobile..."
          className="w-full neumorph-inset text-xs text-slate-800 placeholder-slate-400 rounded-2xl pl-10 pr-4 py-2.5 focus:outline-none font-medium"
        />
      </div>

      {/* Center Status Pill */}
      {activeJob ? (
        <div className="flex items-center space-x-2 bg-[#eef0f4] border border-blue-200 px-4 py-1.5 rounded-full text-xs text-blue-700 font-semibold shadow-[inset_3px_3px_6px_#cbd2dc]">
          <span className="w-2 h-2 rounded-full bg-blue-600 animate-ping"></span>
          <span className="font-mono font-bold">Job #{activeJob.id}: {activeJob.status}</span>
        </div>
      ) : (
        <div className="flex items-center space-x-2 bg-[#eef0f4] border border-emerald-200 px-3.5 py-1 rounded-full text-[11px] text-slate-700 font-medium shadow-[inset_3px_3px_6px_#cbd2dc]">
          <Cloud className="w-3.5 h-3.5 text-emerald-600" />
          <span className="font-mono text-emerald-700 font-bold">Supabase Cloud Engine Online</span>
        </div>
      )}

      {/* Right Controls */}
      <div className="flex items-center space-x-3">
        <button
          onClick={onRefresh}
          title="Sync Pipeline Stats"
          className="neumorph-button px-3.5 py-2 text-slate-700 hover:text-slate-900 text-xs flex items-center space-x-1.5 font-bold"
        >
          <RefreshCw className="w-3.5 h-3.5 text-blue-600" />
          <span className="hidden sm:inline">Sync Data</span>
        </button>

        <div className="h-4 w-[1px] bg-slate-300"></div>

        <div className="flex items-center space-x-2.5">
          <div className="w-9 h-9 rounded-2xl bg-[#eef0f4] border border-white/80 flex items-center justify-center text-xs font-black text-blue-600 shadow-[inset_3px_3px_6px_#cbd2dc,inset_-3px_-3px_6px_#ffffff]">
            AD
          </div>
          <div className="hidden md:block text-left">
            <p className="text-xs font-bold text-slate-800 leading-tight">Admin Operator</p>
            <p className="text-[10px] text-slate-500 font-mono">System Owner</p>
          </div>
        </div>
      </div>
    </header>
  );
}
