import React from 'react';
import { 
  LayoutDashboard, 
  Upload, 
  Database, 
  Activity, 
  Layers
} from 'lucide-react';
import DataLinkLogo from './DataLinkLogo';

export default function Sidebar({ activeTab, setActiveTab, activeJob, theme }) {
  const isDark = theme === 'dark';

  const navItems = [
    { id: 'overview', label: 'Overview Dashboard', icon: LayoutDashboard },
    { id: 'upload', label: 'Data Ingestion & Upload', icon: Upload },
    { id: 'jobs', label: 'Processing Jobs', icon: Activity, badge: activeJob ? '1 Active' : null },
    { id: 'records', label: 'Processed Records', icon: Database },
    { id: 'mapping', label: 'Column Mapping Schema', icon: Layers },
  ];

  return (
    <aside className="w-64 bg-[var(--bg-main)] border-r border-slate-500/20 flex flex-col justify-between h-screen sticky top-0 z-30 select-none shadow-[8px_0_16px_rgba(0,0,0,0.06)] transition-colors duration-200">
      <div>
        {/* Brand Header */}
        <div className="p-5 border-b border-slate-500/20 flex items-center space-x-3">
          <div className="w-10 h-10 rounded-2xl bg-[var(--card-bg)] neumorph-inset flex items-center justify-center border border-white/10 p-2 shadow-[inset_2px_2px_4px_#cbd2dc,inset_-2px_-2px_4px_#ffffff]">
            <DataLinkLogo className="w-6 h-6" />
          </div>
          <div>
            <h1 className="font-black text-sm tracking-tight leading-tight text-slate-800 dark:text-slate-100">DATALINK ENGINE</h1>
            <span className="text-[10px] font-mono uppercase tracking-wider text-blue-600 dark:text-blue-400 font-black px-2 py-0.5 rounded-full neumorph-inset border border-blue-500/20 inline-block mt-0.5">
              {isDark ? 'DARK NEUMORPHIC' : 'WHITE NEUMORPHIC'}
            </span>
          </div>
        </div>

        {/* Navigation Items */}
        <nav className="p-4 space-y-3 mt-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center justify-between px-4 py-3 rounded-2xl font-bold text-xs transition-all duration-200 cursor-pointer ${
                  isActive
                    ? 'text-blue-500 neumorph-inset border border-blue-500/30'
                    : 'text-slate-400 hover:text-slate-200 neumorph-button'
                }`}
              >
                <div className="flex items-center space-x-3">
                  <Icon className={`w-4 h-4 ${isActive ? 'text-blue-500' : 'text-slate-400'}`} />
                  <span>{item.label}</span>
                </div>
                {item.badge && (
                  <span className="bg-blue-500/20 text-blue-400 border border-blue-500/30 text-[10px] font-bold px-2 py-0.5 rounded-full">
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Engine Status Card Footer */}
      <div className="p-4 m-3 rounded-2xl bg-[var(--card-bg)] border border-slate-500/20 neumorph-inset space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-slate-400 font-medium">Pipeline Engine</span>
          <span className="flex items-center text-[10px] text-emerald-500 font-mono font-bold px-2 py-0.5 rounded-full border border-emerald-500/30 bg-emerald-500/10">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5 animate-pulse"></span>
            ACTIVE
          </span>
        </div>
        <div className="text-[11px] font-mono space-y-0.5">
          <p className="font-bold text-slate-200">FastAPI + Python 3.11</p>
          <p className="text-slate-400">Direct In-Process Batching</p>
          <p className="text-blue-500 font-bold">Supabase Cloud DB</p>
        </div>
      </div>
    </aside>
  );
}
