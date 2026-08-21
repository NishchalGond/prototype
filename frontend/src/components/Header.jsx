import React from 'react';
import { Search, RefreshCw, Cloud, Sun, Moon, LogOut } from 'lucide-react';

export default function Header({ onRefresh, activeJob, searchQuery, setSearchQuery, setActiveTab, theme, toggleTheme, onLogout, currentUser }) {
  const isDark = theme === 'dark';
  const role = currentUser?.role || 'ADMIN';
  const fullName = currentUser?.full_name || 'Admin Operator';
  const initials = fullName
    .split(' ')
    .map((n) => n[0])
    .slice(0, 2)
    .join('')
    .toUpperCase() || 'AD';

  return (
    <header className="h-16 bg-[var(--bg-main)] border-b border-slate-500/20 px-6 flex items-center justify-between sticky top-0 z-20 shadow-[0_4px_12px_rgba(0,0,0,0.08)] transition-colors duration-200">
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
          className="w-full neumorph-inset text-xs placeholder-slate-400 rounded-2xl pl-10 pr-4 py-2.5 focus:outline-none font-medium transition-all text-slate-800 dark:text-slate-100"
        />
      </div>

      {/* Center Status Pill */}
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

      {/* Right Controls */}
      <div className="flex items-center space-x-3">
        {/* Sync Data Button */}
        <button
          onClick={onRefresh}
          title="Sync Pipeline Stats"
          className="neumorph-button px-3.5 py-2 text-xs flex items-center space-x-1.5 font-bold transition-transform hover:scale-105 active:scale-95 cursor-pointer text-slate-800 dark:text-slate-200"
        >
          <RefreshCw className="w-3.5 h-3.5 text-blue-500" />
          <span className="hidden sm:inline">Sync Data</span>
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

        <div className="h-4 w-[1px] bg-slate-500/20"></div>

        {/* User Profile & Role Badge */}
        <div className="flex items-center space-x-2.5 px-3 py-1 rounded-xl bg-[var(--card-bg)] neumorph-button cursor-default select-none border border-slate-300/60 dark:border-white/5">
          {/* Avatar Icon */}
          <div className="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-black bg-blue-600 text-white shadow-sm">
            {initials}
          </div>
          
          {/* Name and Role */}
          <div className="hidden md:flex flex-col text-left justify-center">
            <span 
              className="text-xs font-black leading-none"
              style={{ color: isDark ? '#F8FAFC' : '#0F172A' }}
            >
              {fullName}
            </span>
            <div className="flex items-center gap-1 mt-0.5">
              <span className={`text-[8px] font-mono font-black uppercase px-1.5 py-0.5 rounded leading-none ${
                role === 'ADMIN'
                  ? 'bg-rose-500 text-white'
                  : role === 'DATA_PROCESSOR'
                  ? 'bg-emerald-600 text-white'
                  : 'bg-slate-600 text-white'
              }`}>
                {role}
              </span>
            </div>
          </div>
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
