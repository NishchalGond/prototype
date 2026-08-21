import React, { useState, useEffect, useRef } from 'react';
import {
  Activity,
  Shield,
  Lock,
  Unlock,
  Maximize2,
  Minimize2,
  Database,
  CheckCircle2,
  AlertTriangle,
  Copy,
  Server,
  Zap,
  TrendingUp,
  HardDrive,
  RefreshCw
} from 'lucide-react';
import DataLinkLogo from './DataLinkLogo';

export default function LiveTelemetryKiosk({ isFullscreenLocked, setIsFullscreenLocked }) {
  const [stats, setStats] = useState(null);
  const [recentRecords, setRecentRecords] = useState([]);
  const [throughput, setThroughput] = useState({ rowsPerSec: 0, mbTransferred: '0.00' });
  const [latency, setLatency] = useState(38);
  const [isLocked, setIsLocked] = useState(false);
  const [showUnlockModal, setShowUnlockModal] = useState(false);
  const [pinInput, setPinInput] = useState('');
  const [pinError, setPinError] = useState(false);
  const [currentTime, setCurrentTime] = useState(new Date());

  const prevCountRef = useRef(0);
  const prevTimeRef = useRef(Date.now());
  const containerRef = useRef(null);

  // Live Clock
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Polling Live Telemetry Data
  useEffect(() => {
    let isMounted = true;

    async function loadTelemetry() {
      const tStart = Date.now();
      try {
        const [statsRes, recsRes] = await Promise.all([
          fetch('/api/dashboard/stats'),
          fetch('/api/records?page=1&limit=10&status=ALL&sort_by=id&sort_dir=desc')
        ]);

        if (!isMounted) return;

        const statsData = statsRes.ok ? await statsRes.json() : null;
        const recsData = recsRes.ok ? await recsRes.json() : { items: [] };

        const tEnd = Date.now();
        setLatency(Math.max(18, tEnd - tStart));
        if (statsData) setStats(statsData);
        setRecentRecords(recsData.items || []);

        if (statsData) {
          const now = Date.now();
          const timeDiffSec = (now - prevTimeRef.current) / 1000;
          const currentTotal = statsData.total_records || 0;

          if (timeDiffSec > 0 && prevCountRef.current > 0) {
            const rowDelta = Math.max(0, currentTotal - prevCountRef.current);
            const rps = Math.round(rowDelta / timeDiffSec);
            setThroughput({
              rowsPerSec: rps,
              mbTransferred: ((currentTotal * 280) / (1024 * 1024)).toFixed(2)
            });
          } else {
            setThroughput(prev => ({
              ...prev,
              mbTransferred: ((currentTotal * 280) / (1024 * 1024)).toFixed(2)
            }));
          }

          prevCountRef.current = currentTotal;
          prevTimeRef.current = now;
        }
      } catch (err) {
        console.error("Telemetry fetch error:", err);
      }
    }

    loadTelemetry();
    const interval = setInterval(loadTelemetry, 2000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  // Fullscreen & Kiosk Lock Handlers
  const enterKioskMode = async () => {
    try {
      if (document.documentElement.requestFullscreen) {
        await document.documentElement.requestFullscreen();
      }
    } catch (e) {
      console.warn("Fullscreen request error:", e);
    }
    setIsLocked(true);
    if (setIsFullscreenLocked) setIsFullscreenLocked(true);
  };

  const handleUnlockAttempt = (e) => {
    e.preventDefault();
    if (pinInput === 'dev123' || pinInput === 'admin' || pinInput === '1234') {
      setIsLocked(false);
      setShowUnlockModal(false);
      setPinInput('');
      setPinError(false);
      if (document.fullscreenElement && document.exitFullscreen) {
        document.exitFullscreen().catch(() => {});
      }
      if (setIsFullscreenLocked) setIsFullscreenLocked(false);
    } else {
      setPinError(true);
      setPinInput('');
    }
  };

  // Keyboard shortcut listener (F11 or Esc)
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'F11') {
        e.preventDefault();
        if (!isLocked) {
          enterKioskMode();
        }
      }
      if (e.key === 'Escape' && isLocked) {
        e.preventDefault();
        setShowUnlockModal(true);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isLocked]);

  const totalRecords = stats?.total_records || 0;
  const validRecords = stats?.valid_records || 0;
  const duplicateRecords = stats?.duplicate_records || 0;
  const incompleteRecords = (stats?.records_by_status?.INCOMPLETE) || (totalRecords - validRecords - duplicateRecords);

  return (
    <div
      ref={containerRef}
      className={`min-h-screen transition-all duration-300 ${
        isLocked
          ? 'fixed inset-0 z-50 bg-[#0B0F17] text-white p-6 sm:p-10 flex flex-col justify-between overflow-hidden select-none'
          : 'space-y-8 p-2 sm:p-4'
      }`}
    >
      {/* Top Header / Telemetry HUD */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-blue-500/20 pb-4">
        <div className="flex items-center space-x-4">
          <div className="w-12 h-12 rounded-2xl bg-blue-950/60 border border-blue-500/40 p-2.5 shadow-[0_0_20px_rgba(37,99,235,0.4)] flex items-center justify-center animate-pulse">
            <DataLinkLogo className="w-8 h-8" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-black tracking-tight text-slate-800 dark:text-white">
                DATALINK LIVE TELEMETRY
              </h1>
              <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 border border-emerald-500/40 text-emerald-400 text-[10px] font-mono font-bold flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                LIVE STREAM
              </span>
            </div>
            <p className="text-xs text-slate-500 font-mono">
              Mission Control • Supabase Cloud Real-Time Ingestion Pipe
            </p>
          </div>
        </div>

        {/* Action Controls & Clock */}
        <div className="flex items-center space-x-4 font-mono text-xs">
          <div className="hidden sm:flex items-center space-x-2 px-3 py-1.5 rounded-xl bg-slate-900/60 border border-slate-700/50 text-slate-300">
            <Server className="w-3.5 h-3.5 text-blue-400" />
            <span>Latency: <strong className="text-emerald-400">{latency}ms</strong></span>
          </div>

          <div className="px-3 py-1.5 rounded-xl bg-slate-900/60 border border-slate-700/50 text-slate-300 font-bold">
            {currentTime.toLocaleTimeString()}
          </div>

          {!isLocked ? (
            <button
              onClick={enterKioskMode}
              className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 active:scale-95 text-white font-bold flex items-center gap-2 shadow-[0_0_15px_rgba(37,99,235,0.5)] transition-all cursor-pointer"
            >
              <Maximize2 className="w-4 h-4" />
              <span>Lock Fullscreen (F11)</span>
            </button>
          ) : (
            <button
              onClick={() => setShowUnlockModal(true)}
              className="px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 active:scale-95 text-white font-bold flex items-center gap-2 shadow-[0_0_15px_rgba(217,119,6,0.5)] transition-all cursor-pointer"
            >
              <Lock className="w-4 h-4" />
              <span>Unlock Kiosk</span>
            </button>
          )}
        </div>
      </div>

      {/* Main KPI Counters Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* Total Ingested */}
        <div className="p-6 rounded-3xl bg-gradient-to-br from-blue-900/20 to-slate-900/40 border border-blue-500/30 shadow-[0_8px_32px_rgba(0,0,0,0.3)] backdrop-blur-md">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider font-mono">Total Transferred</span>
            <Database className="w-5 h-5 text-blue-400" />
          </div>
          <div className="text-3xl sm:text-4xl font-black text-blue-400 font-mono tracking-tight">
            {totalRecords.toLocaleString()}
          </div>
          <div className="mt-3 flex items-center justify-between text-[11px] text-slate-400 font-mono border-t border-blue-500/20 pt-2">
            <span>Payload Size:</span>
            <strong className="text-slate-200">{throughput.mbTransferred} MB</strong>
          </div>
        </div>

        {/* Valid Records */}
        <div className="p-6 rounded-3xl bg-gradient-to-br from-emerald-900/20 to-slate-900/40 border border-emerald-500/30 shadow-[0_8px_32px_rgba(0,0,0,0.3)] backdrop-blur-md">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider font-mono">Valid Outreach Ready</span>
            <CheckCircle2 className="w-5 h-5 text-emerald-400" />
          </div>
          <div className="text-3xl sm:text-4xl font-black text-emerald-400 font-mono tracking-tight">
            {validRecords.toLocaleString()}
          </div>
          <div className="mt-3 flex items-center justify-between text-[11px] text-slate-400 font-mono border-t border-emerald-500/20 pt-2">
            <span>Contactability Rate:</span>
            <strong className="text-emerald-300">
              {totalRecords ? ((validRecords / totalRecords) * 100).toFixed(1) : 0}%
            </strong>
          </div>
        </div>

        {/* Duplicates Preserved */}
        <div className="p-6 rounded-3xl bg-gradient-to-br from-amber-900/20 to-slate-900/40 border border-amber-500/30 shadow-[0_8px_32px_rgba(0,0,0,0.3)] backdrop-blur-md">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider font-mono">Duplicates Handled</span>
            <Copy className="w-5 h-5 text-amber-400" />
          </div>
          <div className="text-3xl sm:text-4xl font-black text-amber-400 font-mono tracking-tight">
            {duplicateRecords.toLocaleString()}
          </div>
          <div className="mt-3 flex items-center justify-between text-[11px] text-slate-400 font-mono border-t border-amber-500/20 pt-2">
            <span>Identity Hash Matches:</span>
            <strong className="text-amber-300">Preserved in DB</strong>
          </div>
        </div>

        {/* Pipeline Throughput */}
        <div className="p-6 rounded-3xl bg-gradient-to-br from-indigo-900/20 to-slate-900/40 border border-indigo-500/30 shadow-[0_8px_32px_rgba(0,0,0,0.3)] backdrop-blur-md">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider font-mono">Pipeline Ingestion Rate</span>
            <Zap className="w-5 h-5 text-indigo-400" />
          </div>
          <div className="text-3xl sm:text-4xl font-black text-indigo-400 font-mono tracking-tight">
            {throughput.rowsPerSec} <span className="text-sm font-normal text-slate-400">rows/s</span>
          </div>
          <div className="mt-3 flex items-center justify-between text-[11px] text-slate-400 font-mono border-t border-indigo-500/20 pt-2">
            <span>PostgreSQL Engine:</span>
            <strong className="text-emerald-400">Active High-Speed</strong>
          </div>
        </div>
      </div>

      {/* Real-Time Live Feed & Top Communities */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Live Incoming Feed Terminal */}
        <div className="lg:col-span-2 p-6 rounded-3xl bg-slate-950/80 border border-slate-800 shadow-2xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-4">
              <div className="flex items-center space-x-2">
                <Activity className="w-4 h-4 text-blue-400" />
                <h2 className="text-sm font-bold uppercase font-mono tracking-wider text-slate-200">
                  Live Streaming Record Feed
                </h2>
              </div>
              <span className="text-[10px] font-mono text-slate-500">Real-Time Ingestion Buffer</span>
            </div>

            <div className="space-y-2.5 overflow-hidden font-mono text-xs">
              {recentRecords.length > 0 ? (
                recentRecords.slice(0, 6).map((rec, idx) => (
                  <div
                    key={rec.id || idx}
                    className="p-2.5 rounded-xl bg-slate-900/60 border border-slate-800/80 flex items-center justify-between hover:bg-slate-800/60 transition-colors"
                  >
                    <div className="flex items-center space-x-3 truncate">
                      <span className="text-slate-500 font-bold">#{rec.id}</span>
                      <strong className="text-slate-100 truncate">{rec.name || 'ANONYMOUS OWNER'}</strong>
                      <span className="text-slate-400 truncate text-[11px]">[{rec.community || 'Dubai Hills'}]</span>
                      <span className="text-slate-500 text-[11px]">Unit {rec.unit_number || 'N/A'}</span>
                    </div>

                    <div className="flex items-center space-x-2 shrink-0">
                      <span className="text-blue-400 text-[11px]">{rec.mobile_1 || rec.email_address || 'No Contact'}</span>
                      <span
                        className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase ${
                          rec.status === 'VALID'
                            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                            : rec.status === 'DUPLICATE'
                            ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                            : 'bg-slate-500/20 text-slate-400 border border-slate-500/30'
                        }`}
                      >
                        {rec.status}
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-8 text-center text-slate-600 font-mono text-xs">
                  Streaming live records from database...
                </div>
              )}
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-900 flex items-center justify-between text-[11px] font-mono text-slate-500">
            <span>Sync Protocol: PostgreSQL Auto-Commit (1,000 chunk)</span>
            <span>Total Ingested Files: <strong className="text-slate-300">{stats?.total_files || 0}</strong></span>
          </div>
        </div>

        {/* Top Communities Breakdown */}
        <div className="p-6 rounded-3xl bg-slate-950/80 border border-slate-800 shadow-2xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-4">
              <div className="flex items-center space-x-2">
                <TrendingUp className="w-4 h-4 text-emerald-400" />
                <h2 className="text-sm font-bold uppercase font-mono tracking-wider text-slate-200">
                  Community Breakdown
                </h2>
              </div>
              <span className="text-[10px] font-mono text-slate-500">Canonical Registers</span>
            </div>

            <div className="space-y-3 font-mono text-xs">
              {stats?.community_distribution?.slice(0, 5).map((c, i) => (
                <div key={i} className="space-y-1">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-300 truncate">{c.name || 'Dubai Hills'}</span>
                    <strong className="text-blue-400">{c.count.toLocaleString()}</strong>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-blue-500 to-cyan-400 rounded-full"
                      style={{ width: `${Math.min(100, (c.count / (totalRecords || 1)) * 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-6 p-3 rounded-2xl bg-blue-950/40 border border-blue-500/20 text-[11px] font-mono text-blue-300 text-center">
            🔒 High-Security Data Pipeline Display
          </div>
        </div>
      </div>

      {/* Kiosk Unlock Modal */}
      {showUnlockModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="w-full max-w-sm p-6 rounded-3xl bg-slate-900 border border-blue-500/40 shadow-2xl text-center space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-blue-600/20 border border-blue-500/40 mx-auto flex items-center justify-center text-blue-400">
              <Shield className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white">Unlock Kiosk Screen</h3>
              <p className="text-xs text-slate-400 font-mono mt-1">
                Enter security key to return to dashboard
              </p>
            </div>

            <form onSubmit={handleUnlockAttempt} className="space-y-3">
              <input
                type="password"
                autoFocus
                placeholder="Enter key (e.g. dev123)"
                value={pinInput}
                onChange={(e) => setPinInput(e.target.value)}
                className="w-full px-4 py-3 rounded-xl bg-slate-950 border border-slate-700 text-white text-center font-mono tracking-widest text-sm focus:outline-none focus:border-blue-500"
              />
              {pinError && (
                <p className="text-xs text-rose-400 font-mono">Invalid key. Try dev123</p>
              )}

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => { setShowUnlockModal(false); setPinError(false); }}
                  className="flex-1 py-2.5 rounded-xl bg-slate-800 text-slate-300 text-xs font-bold hover:bg-slate-700 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 py-2.5 rounded-xl bg-blue-600 text-white text-xs font-bold hover:bg-blue-500 shadow-[0_0_15px_rgba(37,99,235,0.5)] transition-colors"
                >
                  Unlock
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
