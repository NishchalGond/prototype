import React, { useState } from 'react';
import { Lock, Eye, EyeOff, KeyRound, ShieldCheck, Sun, Moon, ArrowRight, Sparkles, Mail, UserCheck } from 'lucide-react';
import DataLinkLogo from './DataLinkLogo';
import { setSession } from '../lib/api';
import { COMPANY_DOMAIN, EMAIL_PLACEHOLDER } from '../lib/org';

export default function AuthLockScreen({ onAuthenticate, theme, toggleTheme }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isShaking, setIsShaking] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Please provide both email address and password.');
      return;
    }

    setIsLoading(true);
    setError('');

    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), password })
      });

      if (res.ok) {
        const data = await res.json();
        setSession(data.access_token, data.user);
        onAuthenticate(data.user);
      } else if (res.status >= 500 || res.status === 502 || res.status === 504) {
        // The dev proxy answers 500 when the API is not listening, so a dead
        // backend used to read as "check your credentials" -- which sends
        // someone hunting through passwords for a server that is simply down.
        setError('The server is not responding. Check that the backend is '
                 + 'running, then try again.');
        setIsShaking(true);
        setTimeout(() => setIsShaking(false), 600);
      } else {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || 'Authentication failed. Please check credentials.');
        setIsShaking(true);
        setTimeout(() => setIsShaking(false), 600);
      }
    } catch (err) {
      // A network failure must not grant access. The previous fallback signed
      // the user in locally as ADMIN whenever the request threw, which meant
      // anyone could reach the dashboard by taking the API offline -- and the
      // session it created had no token, so every later call would 401 anyway.
      setError('Cannot reach the authentication service. Check your connection and try again.');
      setIsShaking(true);
      setTimeout(() => setIsShaking(false), 600);
    } finally {
      setIsLoading(false);
    }
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
          className="neumorph-button p-3 rounded-2xl flex items-center gap-2 text-xs font-bold transition-transform hover:scale-105 active:scale-95 cursor-pointer"
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
      <div className={`relative z-10 w-full max-w-[420px] mx-4 transition-all duration-300 ${isShaking ? 'animate-shake' : ''}`}>
        <div className="neumorph-card p-8 sm:p-10 flex flex-col items-center text-center relative overflow-visible shadow-2xl">
          
          {/* Floating Logo Badge */}
          <div className="relative -mt-20 mb-6">
            <div className="w-22 h-22 rounded-3xl bg-[var(--card-bg)] neumorph-inset flex items-center justify-center p-3.5 shadow-xl border border-blue-500/30">
              <DataLinkLogo className="w-12 h-12" />
            </div>
            <div className="absolute -bottom-1 -right-1 p-1.5 rounded-full bg-blue-600 text-white shadow-md">
              <ShieldCheck className="w-3.5 h-3.5" />
            </div>
          </div>

          {/* Title & Badge */}
          <div className="space-y-1 mb-6">
            <div className="flex items-center justify-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-blue-500" />
              <span className="text-[10px] font-mono font-black tracking-widest text-blue-600 uppercase">
                RBAC SECURITY GATE
              </span>
            </div>
            <h1 className="text-2xl font-black tracking-tight text-[#0F172A] dark:text-[#F8FAFC]">
              DATALINK ENGINE
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">
              Enterprise Real Estate Ingestion & Deduplication
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="w-full space-y-3.5">
            {/* Email Input */}
            <div className="relative text-left">
              <label className="block text-[10px] font-mono font-black text-slate-500 uppercase tracking-wider mb-1 ml-1">
                Operator Email
              </label>
              <div className="relative">
                <div className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none">
                  <Mail className="w-4 h-4 text-blue-500" />
                </div>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => { setEmail(e.target.value); setError(''); }}
                  placeholder={EMAIL_PLACEHOLDER}
                  autoFocus
                  required
                  className="w-full neumorph-inset rounded-2xl pl-11 pr-4 py-3 text-xs font-bold text-slate-800 dark:text-slate-100 focus:outline-none transition-all"
                />
              </div>
            </div>

            {/* Password Input */}
            <div className="relative text-left">
              <label className="block text-[10px] font-mono font-black text-slate-500 uppercase tracking-wider mb-1 ml-1">
                Access Password
              </label>
              <div className="relative">
                <div className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none">
                  <KeyRound className="w-4 h-4 text-blue-500" />
                </div>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); setError(''); }}
                  placeholder="Enter password..."
                  required
                  className="w-full neumorph-inset rounded-2xl pl-11 pr-11 py-3 text-xs font-bold text-slate-800 dark:text-slate-100 focus:outline-none transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  tabIndex={-1}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-blue-500 transition-colors p-1 cursor-pointer"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Error Message */}
            {error && (
              <div className="text-xs font-bold text-rose-500 bg-rose-500/10 border border-rose-500/30 py-2 px-3 rounded-xl animate-fade-in text-left">
                {error}
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full neumorph-button-primary py-3.5 rounded-2xl font-black text-xs uppercase tracking-wider flex items-center justify-center gap-2 group transition-all mt-2 cursor-pointer shadow-lg"
            >
              {isLoading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  <span>Authenticate Session</span>
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </>
              )}
            </button>
          </form>

          {/* --- Single sign-on ------------------------------------------
              UI only, by request: there is no OAuth flow behind these yet.
              They are rendered disabled and say so, rather than as live
              buttons that silently do nothing -- a sign-in control that looks
              real and is not is worse than an obviously unfinished one,
              because someone locked out will keep clicking it.
              To make these work: register an app (Entra ID for Microsoft,
              Google Cloud console for Google), add a
              /api/auth/oauth/{provider} callback that verifies the returned
              token and issues the same JWT /api/auth/login already does, then
              swap the handler here. Match on the verified email against an
              existing User row rather than creating accounts on the fly --
              otherwise anyone in the tenant gets in, and role assignment stops
              being a decision anybody made. */}
          <div className="mt-5 space-y-3">
            <div className="flex items-center gap-3" aria-hidden="true">
              <span className="h-px flex-1 bg-slate-300/70" />
              <span className="text-[10px] font-mono text-slate-400 font-bold">
                OR CONTINUE WITH
              </span>
              <span className="h-px flex-1 bg-slate-300/70" />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                disabled
                title="Google sign-in is not connected yet"
                className="neumorph-button py-2.5 rounded-xl text-xs font-bold text-slate-500 flex items-center justify-center gap-2 opacity-60 cursor-not-allowed"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" aria-hidden="true">
                  <path fill="#4285F4" d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.5h6.5a5.6 5.6 0 0 1-2.4 3.7v3h3.9c2.3-2.1 3.5-5.2 3.5-8.9z"/>
                  <path fill="#34A853" d="M12 24c3.2 0 5.9-1.1 7.9-2.9l-3.9-3c-1 .7-2.4 1.1-4 1.1-3.1 0-5.7-2.1-6.6-4.9H1.4v3.1A12 12 0 0 0 12 24z"/>
                  <path fill="#FBBC05" d="M5.4 14.3a7.2 7.2 0 0 1 0-4.6V6.6H1.4a12 12 0 0 0 0 10.8l4-3.1z"/>
                  <path fill="#EA4335" d="M12 4.8c1.8 0 3.3.6 4.6 1.8l3.4-3.4A12 12 0 0 0 1.4 6.6l4 3.1C6.3 6.9 8.9 4.8 12 4.8z"/>
                </svg>
                Google
              </button>

              {/* Company mail is on Outlook, so this is the one that will
                  actually matter: Microsoft Entra ID (formerly Azure AD).
                  Signing in with the work account people already have beats
                  another password for them to forget. */}
              <button
                type="button"
                disabled
                title="Microsoft sign-in is not connected yet"
                className="neumorph-button py-2.5 rounded-xl text-xs font-bold text-slate-500 flex items-center justify-center gap-2 opacity-60 cursor-not-allowed"
              >
                <svg className="w-4 h-4" viewBox="0 0 23 23" aria-hidden="true">
                  <path fill="#F25022" d="M1 1h10v10H1z"/>
                  <path fill="#7FBA00" d="M12 1h10v10H12z"/>
                  <path fill="#00A4EF" d="M1 12h10v10H1z"/>
                  <path fill="#FFB900" d="M12 12h10v10H12z"/>
                </svg>
                Microsoft
              </button>
            </div>

            <p className="text-[10px] text-slate-400 text-center">
              Single sign-on is not connected yet. Use your {COMPANY_DOMAIN} email and password.
            </p>
          </div>

        </div>
      </div>
    </div>
  );
}
