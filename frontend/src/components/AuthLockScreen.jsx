import React, { useState } from 'react';
import { Lock, Eye, EyeOff, KeyRound, ShieldCheck, Sun, Moon, ArrowRight, Sparkles } from 'lucide-react';

export default function AuthLockScreen({ onAuthenticate, theme, toggleTheme }) {
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isShaking, setIsShaking] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!password) {
      setError('Please enter your access key');
      return;
    }

    setIsLoading(true);
    setError('');

    // Simulate swift verification
    setTimeout(() => {
      if (password === 'dev123') {
        setIsLoading(false);
        onAuthenticate();
      } else {
        setIsLoading(false);
        setError('Incorrect password. Access denied.');
        setIsShaking(true);
        setTimeout(() => setIsShaking(false), 600);
      }
    }, 300);
  };

  const isDark = theme === 'dark';

  return (
    <div className={`relative h-screen w-screen flex items-center justify-center overflow-hidden transition-colors duration-300 ${isDark ? 'bg-[#14171d] text-slate-100' : 'bg-[#eef0f4] text-slate-800'}`}>
      {/* Background Wallpaper with dynamic overlay */}
      <div 
        className="absolute inset-0 bg-cover bg-center bg-no-repeat transition-opacity duration-700 pointer-events-none scale-105"
        style={{ 
          backgroundImage: 'url(/wallpaper.jpg)',
          opacity: isDark ? 0.35 : 0.12
        }}
      />
      
      {/* Ambient Radial Gradient Glow */}
      <div className={`absolute inset-0 pointer-events-none ${isDark ? 'bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-blue-900/20 via-transparent to-black/60' : 'bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-blue-500/10 via-transparent to-transparent'}`} />

      {/* Top Theme Switcher */}
      <div className="absolute top-6 right-6 z-20">
        <button
          type="button"
          onClick={toggleTheme}
          title={`Switch to ${isDark ? 'Light' : 'Dark'} Mode`}
          className="neumorph-button p-3 rounded-2xl flex items-center gap-2 text-xs font-bold transition-transform hover:scale-105 active:scale-95"
        >
          {isDark ? (
            <>
              <Sun className="w-4 h-4 text-amber-400 animate-spin-slow" />
              <span className="text-slate-300">Light Mode</span>
            </>
          ) : (
            <>
              <Moon className="w-4 h-4 text-blue-600" />
              <span className="text-slate-700">Dark Mode</span>
            </>
          )}
        </button>
      </div>

      {/* Central Neumorphic Lock Box */}
      <div className={`relative z-10 w-full max-w-[400px] mx-4 transition-all duration-300 ${isShaking ? 'animate-shake' : ''}`}>
        <div className="neumorph-card p-8 sm:p-10 flex flex-col items-center text-center relative overflow-visible">
          
          {/* Floating Profile / System Avatar Emblem */}
          <div className="relative -mt-20 mb-6">
            <div className="w-24 h-24 rounded-full overflow-hidden p-1 shadow-[0_0_25px_rgba(37,99,235,0.45)] border-2 border-blue-500/40 bg-[#1e232b] flex items-center justify-center transition-transform hover:scale-105">
              <img 
                src="/wallpaper.jpg" 
                alt="System Emblem" 
                className="w-full h-full object-cover rounded-full filter contrast-125"
                onError={(e) => {
                  e.target.style.display = 'none';
                  e.target.nextSibling.style.display = 'flex';
                }}
              />
              <div className="hidden w-full h-full rounded-full items-center justify-center bg-blue-600 text-white">
                <Lock className="w-8 h-8" />
              </div>
            </div>
            <div className="absolute -bottom-1 -right-1 p-1.5 rounded-full bg-blue-600 text-white shadow-lg">
              <ShieldCheck className="w-3.5 h-3.5" />
            </div>
          </div>

          {/* Title & Badge */}
          <div className="space-y-1 mb-6">
            <div className="flex items-center justify-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-blue-500" />
              <span className="text-[10px] font-mono font-black tracking-widest text-blue-600 uppercase">
                SECURITY VERIFICATION
              </span>
            </div>
            <h1 className="text-2xl font-black tracking-tight">DATALINK ENGINE</h1>
            <p className="text-xs text-slate-400 font-medium">Enter system access password to proceed</p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="w-full space-y-4">
            <div className="relative">
              <div className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none">
                <KeyRound className="w-4 h-4 text-blue-500" />
              </div>
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => { setPassword(e.target.value); setError(''); }}
                placeholder="Enter password..."
                autoFocus
                className="w-full neumorph-inset rounded-2xl pl-11 pr-11 py-3 text-sm font-medium focus:outline-none transition-all"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                tabIndex={-1}
                className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-blue-500 transition-colors p-1"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>

            {/* Error Message */}
            {error && (
              <div className="text-xs font-semibold text-rose-500 bg-rose-500/10 border border-rose-500/20 py-2 px-3 rounded-xl animate-fade-in">
                {error}
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full neumorph-button-primary py-3.5 rounded-2xl font-bold text-sm flex items-center justify-center gap-2 group transition-all"
            >
              {isLoading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  <span>Unlock System</span>
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </>
              )}
            </button>
          </form>

          {/* System Footer Note */}
          <div className="mt-8 pt-4 border-t border-slate-500/20 w-full flex items-center justify-between text-[11px] text-slate-400 font-mono">
            <span>v2.4 Protected</span>
            <span>Key: dev123</span>
          </div>

        </div>
      </div>
    </div>
  );
}
