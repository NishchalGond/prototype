import React from 'react';
import { 
  LayoutDashboard, 
  Upload, 
  Database, 
  Activity, 
  Layers,
  X
} from 'lucide-react';
import DataLinkLogo from './DataLinkLogo';

export const navItems = [
  { id: 'overview', label: 'Overview Dashboard', icon: LayoutDashboard, shortLabel: 'Overview' },
  { id: 'upload', label: 'Data Ingestion & Upload', icon: Upload, shortLabel: 'Upload' },
  { id: 'jobs', label: 'Processing Jobs', icon: Activity, shortLabel: 'Jobs' },
  { id: 'records', label: 'Processed Records', icon: Database, shortLabel: 'Records' },
  { id: 'mapping', label: 'Column Mapping Schema', icon: Layers, shortLabel: 'Schema' },
];

export default function Sidebar({ activeTab, setActiveTab, activeJob, theme, mobileOpen, setMobileOpen }) {
  const isDark = theme === 'dark';

  return (
    <>
      {/* Desktop Persistent Sidebar */}
      <aside className="hidden md:flex w-64 bg-[var(--bg-main)] border-r border-slate-500/20 flex-col justify-between h-screen sticky top-0 z-30 select-none shadow-[8px_0_16px_rgba(0,0,0,0.06)] transition-colors duration-200 shrink-0">
        <div>
          {/* Brand Header */}
          <div className="p-5 border-b border-slate-500/20 flex items-center space-x-3">
            <div className="w-10 h-10 rounded-2xl bg-[var(--card-bg)] neumorph-inset flex items-center justify-center border border-white/10 p-2 shadow-[inset_2px_2px_4px_#cbd2dc,inset_-2px_-2px_4px_#ffffff] shrink-0">
              <DataLinkLogo className="w-6 h-6" />
            </div>
            <div>
              <h1 
                style={{ color: isDark ? '#F8FAFC' : '#0F172A' }}
                className="font-black text-sm tracking-tight leading-tight"
              >
                DATALINK ENGINE
              </h1>
              <span 
                style={{ 
                  color: isDark ? '#60A5FA' : '#2563EB',
                  backgroundColor: isDark ? 'rgba(37,99,235,0.2)' : 'rgba(37,99,235,0.12)',
                  borderColor: isDark ? 'rgba(59,130,246,0.3)' : 'rgba(37,99,235,0.25)'
                }}
                className="text-[10px] font-mono uppercase tracking-wider font-black px-2 py-0.5 rounded-full border inline-block mt-0.5 shadow-xs"
              >
                {isDark ? 'DARK NEUMORPHIC' : 'WHITE NEUMORPHIC'}
              </span>
            </div>
          </div>

          {/* Navigation Items */}
          <nav className="p-4 space-y-3 mt-2">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              const hasBadge = item.id === 'jobs' && activeJob;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  style={{
                    color: isActive ? '#2563EB' : (isDark ? '#E2E8F0' : '#0F172A')
                  }}
                  className={`w-full flex items-center justify-between px-4 py-3 rounded-2xl font-black text-xs transition-all duration-200 cursor-pointer ${
                    isActive
                      ? 'neumorph-inset border border-blue-500/40 bg-blue-500/10 shadow-inner'
                      : 'neumorph-button hover:opacity-90'
                  }`}
                >
                  <div className="flex items-center space-x-3">
                    <Icon 
                      style={{ color: isActive ? '#2563EB' : (isDark ? '#94A3B8' : '#475569') }}
                      className="w-4 h-4" 
                    />
                    <span>{item.label}</span>
                  </div>
                  {hasBadge && (
                    <span 
                      style={{
                        color: '#2563EB',
                        backgroundColor: isDark ? 'rgba(37,99,235,0.2)' : 'rgba(37,99,235,0.15)',
                        borderColor: 'rgba(37,99,235,0.3)'
                      }}
                      className="border text-[10px] font-black px-2 py-0.5 rounded-full"
                    >
                      1 Active
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
            <span 
              style={{ color: isDark ? '#E2E8F0' : '#0F172A' }}
              className="text-[11px] font-black"
            >
              Pipeline Engine
            </span>
            <span className="flex items-center text-[10px] text-emerald-600 dark:text-emerald-400 font-mono font-bold px-2 py-0.5 rounded-full border border-emerald-500/30 bg-emerald-500/10">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5 animate-pulse"></span>
              ACTIVE
            </span>
          </div>
          <div className="text-[11px] font-mono space-y-0.5">
            <p 
              style={{ color: isDark ? '#F8FAFC' : '#0F172A' }}
              className="font-black"
            >
              FastAPI + Python 3.11
            </p>
            <p 
              style={{ color: isDark ? '#94A3B8' : '#475569' }}
              className="font-semibold"
            >
              Direct In-Process Batching
            </p>
            <p 
              style={{ color: '#2563EB' }}
              className="font-black"
            >
              Supabase Cloud DB
            </p>
          </div>
        </div>
      </aside>

      {/* Mobile Slide-Over Drawer */}
      {mobileOpen && (
        <div 
          className="fixed inset-0 z-50 md:hidden bg-slate-900/60 backdrop-blur-sm flex transition-opacity animate-in fade-in"
          onClick={() => setMobileOpen(false)}
        >
          <div 
            className="w-4/5 max-w-xs bg-[var(--bg-main)] h-full flex flex-col justify-between p-5 border-r border-slate-500/20 shadow-2xl animate-in slide-in-from-left duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            <div>
              {/* Drawer Header */}
              <div className="flex items-center justify-between pb-4 border-b border-slate-500/20">
                <div className="flex items-center space-x-3">
                  <div className="w-9 h-9 rounded-2xl bg-[var(--card-bg)] neumorph-inset flex items-center justify-center p-1.5 border border-white/10 shrink-0">
                    <DataLinkLogo className="w-5 h-5" />
                  </div>
                  <div>
                    <h2 className="font-black text-xs text-slate-900 dark:text-slate-100 tracking-tight">
                      DATALINK ENGINE
                    </h2>
                    <span className="text-[9px] font-mono font-bold text-blue-600 dark:text-blue-400">
                      Mobile Control
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => setMobileOpen(false)}
                  className="neumorph-button p-2 rounded-xl text-slate-700 dark:text-slate-300"
                  aria-label="Close Navigation"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Navigation Items */}
              <nav className="space-y-2.5 mt-5">
                {navItems.map((item) => {
                  const Icon = item.icon;
                  const isActive = activeTab === item.id;
                  return (
                    <button
                      key={item.id}
                      onClick={() => {
                        setActiveTab(item.id);
                        setMobileOpen(false);
                      }}
                      className={`w-full flex items-center justify-between px-3.5 py-3 rounded-2xl font-black text-xs transition-all ${
                        isActive
                          ? 'neumorph-inset border border-blue-500/40 text-blue-600 dark:text-blue-400 bg-blue-500/10'
                          : 'neumorph-button text-slate-800 dark:text-slate-200'
                      }`}
                    >
                      <div className="flex items-center space-x-3">
                        <Icon className={`w-4 h-4 ${isActive ? 'text-blue-600 dark:text-blue-400' : 'text-slate-500 dark:text-slate-400'}`} />
                        <span>{item.label}</span>
                      </div>
                      {item.id === 'jobs' && activeJob && (
                        <span className="bg-blue-600 text-white text-[9px] font-bold px-2 py-0.5 rounded-full">
                          Active
                        </span>
                      )}
                    </button>
                  );
                })}
              </nav>
            </div>

            {/* Mobile Footer Status */}
            <div className="p-3 rounded-2xl bg-[var(--card-bg)] border border-slate-500/20 neumorph-inset space-y-1 text-[11px] font-mono">
              <div className="flex items-center justify-between font-bold text-slate-800 dark:text-slate-200">
                <span>Supabase DB</span>
                <span className="text-emerald-500 text-[10px]">ONLINE</span>
              </div>
              <p className="text-slate-500 dark:text-slate-400 text-[10px]">Direct Mobile Link</p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

{/* Mobile Native Bottom Navigation Bar */}
export function MobileBottomNav({ activeTab, setActiveTab, activeJob }) {
  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-[var(--bg-main)]/95 backdrop-blur-lg border-t border-slate-500/20 px-2 py-1.5 flex items-center justify-around shadow-[0_-4px_16px_rgba(0,0,0,0.08)]">
      {navItems.map((item) => {
        const Icon = item.icon;
        const isActive = activeTab === item.id;
        const hasBadge = item.id === 'jobs' && activeJob;

        return (
          <button
            key={item.id}
            onClick={() => setActiveTab(item.id)}
            className={`relative flex flex-col items-center justify-center py-1 px-2.5 rounded-xl transition-all ${
              isActive 
                ? 'text-blue-600 dark:text-blue-400 font-black' 
                : 'text-slate-600 dark:text-slate-400 font-medium hover:text-slate-900 dark:hover:text-slate-100'
            }`}
          >
            <div className={`p-1 rounded-xl transition-all ${isActive ? 'bg-blue-500/15 neumorph-inset shadow-xs' : ''}`}>
              <Icon className="w-5 h-5" />
            </div>
            <span className="text-[10px] mt-0.5 tracking-tight">{item.shortLabel}</span>
            {hasBadge && (
              <span className="absolute top-1 right-2 w-2 h-2 bg-blue-600 rounded-full animate-ping" />
            )}
          </button>
        );
      })}
    </nav>
  );
}
