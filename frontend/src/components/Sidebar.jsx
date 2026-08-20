import React from 'react';
import { 
  LayoutDashboard, 
  Upload, 
  Database, 
  Activity, 
  Sparkles,
  Layers
} from 'lucide-react';

export default function Sidebar({ activeTab, setActiveTab, activeJob }) {
  const navItems = [
    { id: 'overview', label: 'Overview Dashboard', icon: LayoutDashboard },
    { id: 'upload', label: 'Data Ingestion & Upload', icon: Upload },
    { id: 'jobs', label: 'Processing Jobs', icon: Activity, badge: activeJob ? '1 Active' : null },
    { id: 'records', label: 'Processed Records', icon: Database },
    { id: 'mapping', label: 'Column Mapping Schema', icon: Layers },
  ];

  return (
    <aside className="w-64 bg-[#eef0f4] border-r border-slate-300/60 flex flex-col justify-between h-screen sticky top-0 z-30 select-none shadow-[8px_0_16px_#cbd2dc]">
      <div>
        {/* Brand Header */}
        <div className="p-5 border-b border-slate-300/60 flex items-center space-x-3">
          <div className="w-10 h-10 rounded-2xl bg-[#eef0f4] shadow-[inset_3px_3px_6px_#cbd2dc,inset_-3px_-3px_6px_#ffffff] flex items-center justify-center border border-white/80">
            <Sparkles className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <h1 className="font-black text-sm text-slate-800 tracking-tight leading-tight">DATALINK ENGINE</h1>
            <span className="text-[10px] font-mono uppercase tracking-wider text-blue-600 font-bold bg-[#eef0f4] px-2.5 py-0.5 rounded-full border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc,inset_-2px_-2px_4px_#ffffff]">
              WHITE NEUMORPHIC
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
                    ? 'bg-[#eef0f4] text-blue-600 border border-slate-300/60 shadow-[inset_4px_4px_8px_#cbd2dc,inset_-4px_-4px_8px_#ffffff]'
                    : 'text-slate-600 hover:text-slate-900 bg-[#eef0f4] shadow-[5px_5px_12px_#cbd2dc,-5px_-5px_12px_#ffffff]'
                }`}
              >
                <div className="flex items-center space-x-3">
                  <Icon className={`w-4 h-4 ${isActive ? 'text-blue-600' : 'text-slate-500'}`} />
                  <span>{item.label}</span>
                </div>
                {item.badge && (
                  <span className="bg-blue-100 text-blue-700 border border-blue-200 text-[10px] font-bold px-2 py-0.5 rounded-full">
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Engine Status Card Footer */}
      <div className="p-4 m-3 rounded-2xl bg-[#eef0f4] border border-slate-300/60 shadow-[inset_4px_4px_8px_#cbd2dc,inset_-4px_-4px_8px_#ffffff] space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-slate-500 font-medium">Pipeline Engine</span>
          <span className="flex items-center text-[10px] text-emerald-700 font-mono font-bold bg-[#eef0f4] px-2 py-0.5 rounded-full border border-emerald-200 shadow-[2px_2px_5px_#cbd2dc]">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5"></span>
            ACTIVE
          </span>
        </div>
        <div className="text-[11px] text-slate-600 font-mono space-y-0.5">
          <p className="text-slate-800 font-bold">FastAPI + Python 3.12</p>
          <p className="text-slate-500">Direct In-Process Batching</p>
          <p className="text-blue-600 font-bold">Supabase Cloud DB</p>
        </div>
      </div>
    </aside>
  );
}
