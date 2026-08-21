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
                {item.badge && (
                  <span 
                    style={{
                      color: '#2563EB',
                      backgroundColor: isDark ? 'rgba(37,99,235,0.2)' : 'rgba(37,99,235,0.15)',
                      borderColor: 'rgba(37,99,235,0.3)'
                    }}
                    className="border text-[10px] font-black px-2 py-0.5 rounded-full"
                  >
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
  );
}
