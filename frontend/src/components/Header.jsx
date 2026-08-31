/** Top Navigation Header with Search and Theme Controls */
import React from 'react';
import { Search, RefreshCw, Cloud, Sun, Moon, LogOut, ShieldCheck } from 'lucide-react';
import DataLinkLogo from './DataLinkLogo';

export default function Header({ 
  onRefresh, 
  activeJob, 
  searchQuery, 
  setSearchQuery, 
  setActiveTab, 
  theme, 
  toggleTheme, 
  onLogout, 
  currentUser 
}) {
  const isDark = theme === 'dark';
  const role = currentUser?.role || 'ADMIN';
  const fullName = currentUser?.full_name || 'Admin Operator';

  return (
    <header className="h-16 bg-[var(--bg-main)] border-b border-slate-500/20 px-3 sm:px-6 flex items-center justify-between sticky top-0 z-20 shadow-[0_4px_12px_rgba(0,0,0,0.08)] transition-colors duration-200">
      {/* Left: Search Input */}
      <div className="flex items-center space-x-2 sm:space-x-3 flex-1 max-w-md">
        {/* Debossed Neumorphic Search Input */}
        <div className="relative w-full max-w-[220px] sm:max-w-xs md:w-80">
          <Search className="w-3.5 h-3.5 sm:w-4 sm:h-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-blue-600" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              if (e.target.value.trim().length > 0) {
                setActiveTab('records');
              }
            }}
            placeholder="Search records..."
            className="w-full neumorph-inset text-[11px] sm:text-xs placeholder-slate-400 rounded-2xl pl-8 sm:pl-10 pr-3 py-2 focus:outline-none font-medium transition-all text-slate-800 dark:text-slate-100"
          />
        </div>
      </div>

      {/* Center Status Pill (hidden on small phone viewports) */}
      <div className="hidden lg:flex items-center">
        {activeJob ? (
          <div className="flex items-center space-x-2 bg-[var(--card-bg)] border border-blue-400/40 px-4 py-1.5 rounded-full text-xs text-blue-500 font-semibold neumorph-inset">
            <span className="w-2 h-2 rounded-full bg-blue-600 animate-ping"></span>
            <span className="font-mono font-bold">Job #{activeJob.id}: {activeJob.status}</span>
          </div>
        ) : (
          <div className="flex items-center space-x-2 bg-[var(--card-bg)] border border-emerald-500/30 px-3.5 py-1 rounded-full text-[11px] font-medium neumorph-inset">
            <Cloud className="w-3.5 h-3.5 text-emerald-500" />
            <span className="font-mono text-emerald-600 dark:text-emerald-400 font-bold">Supabase Cloud Engine Online</span>
          </div>
        )}
      </div>

      {/* Right Controls */}
      <div className="flex items-center space-x-1.5 sm:space-x-3 shrink-0">
        {/* Sync Data Button */}
        <button
          onClick={onRefresh}
          title="Sync Pipeline Stats"
          className="neumorph-button px-2.5 sm:px-3.5 py-2 text-xs flex items-center space-x-1 font-bold transition-transform hover:scale-105 active:scale-95 cursor-pointer text-slate-800 dark:text-slate-200"
        >
          <RefreshCw className="w-3.5 h-3.5 text-blue-500" />
          <span className="hidden sm:inline">Sync</span>
        </button>

        {/* Theme Toggle Button */}
        <button
          onClick={toggleTheme}
          title={`Switch to ${isDark ? 'Light' : 'Dark'} Mode`}
          className="neumorph-button p-2 text-xs flex items-center justify-center transition-transform hover:scale-105 active:scale-95 cursor-pointer"
        >
          {isDark ? (
            <Sun className="w-4 h-4 text-amber-400" />
          ) : (
            <Moon className="w-4 h-4 text-blue-600" />
          )}
        </button>

        <div className="hidden sm:block h-4 w-[1px] bg-slate-500/20"></div>

        {/* Admin Logo Icon */}
        <div 
          title={`${fullName} (${role})`}
          className="neumorph-button p-2 text-xs flex items-center justify-center select-none cursor-default text-blue-600 dark:text-blue-400"
        >
          <ShieldCheck className="w-4 h-4 text-blue-600 dark:text-blue-400" />
        </div>

        {/* Logout / Lock Button */}
        <button
          onClick={onLogout}
          title="Log Out Session"
          className="neumorph-button p-2 text-rose-500 hover:text-rose-600 transition-transform hover:scale-105 active:scale-95 cursor-pointer"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}
