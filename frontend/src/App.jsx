import React, { useState, useEffect } from 'react';
import Sidebar, { MobileBottomNav } from './components/Sidebar';
import Header from './components/Header';
import OverviewDashboard from './components/OverviewDashboard';
import UploadSection from './components/UploadSection';
import LiveProcessingTracker from './components/LiveProcessingTracker';
import RecordsExplorer from './components/RecordsExplorer';
import CallQueue from './components/CallQueue';
import UserManagement from './components/UserManagement';
import ExecutiveDashboard from './components/ExecutiveDashboard';
import ForcePasswordChange from './components/ForcePasswordChange';
import JobDetailsView from './components/JobDetailsView';
import ColumnMappingInspector from './components/ColumnMappingInspector';
import Spatial3DCanvas from './components/Spatial3DCanvas';
import AuthLockScreen from './components/AuthLockScreen';
import { apiFetch, clearSession } from './lib/api';

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(() => {
    return localStorage.getItem('datalink_auth') === 'authenticated';
  });

  const [currentUser, setCurrentUser] = useState(() => {
    try {
      const saved = localStorage.getItem('datalink_user');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('datalink_theme') || 'light';
  });

  const [activeTab, setActiveTab] = useState('overview');
  const [stats, setStats] = useState(null);
  const [activeJobId, setActiveJobId] = useState(null);
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  // Sync theme with document classList
  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    localStorage.setItem('datalink_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  const handleAuthenticate = (user) => {
    localStorage.setItem('datalink_auth', 'authenticated');
    if (user) {
      setCurrentUser(user);
      localStorage.setItem('datalink_user', JSON.stringify(user));
    }
    setIsAuthenticated(true);
  };

  const handleLogout = () => {
    clearSession();
    setCurrentUser(null);
    setIsAuthenticated(false);
  };

  // apiFetch emits this when the API rejects the token (expired, revoked, or
  // the user was deactivated). Without it a stale session keeps rendering the
  // dashboard shell while every request underneath it fails.
  useEffect(() => {
    const onUnauthorized = () => {
      setCurrentUser(null);
      setIsAuthenticated(false);
    };
    window.addEventListener('datalink:unauthorized', onUnauthorized);
    return () => window.removeEventListener('datalink:unauthorized', onUnauthorized);
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      fetchStats();
    }
  }, [isAuthenticated]);

  const fetchStats = async () => {
    try {
      const res = await apiFetch('/api/dashboard/stats');
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (err) {
      console.error('Failed to fetch dashboard stats:', err);
    }
  };

  const handleUploadComplete = (jobId) => {
    setActiveJobId(jobId);
    setSelectedJobId(jobId);
    setActiveTab('tracker');
  };

  const handleJobFinished = () => {
    fetchStats();
  };

  // If not authenticated, display the Neumorphic Lock Screen
  if (!isAuthenticated) {
    return (
      <AuthLockScreen 
        onAuthenticate={handleAuthenticate}
        theme={theme}
        toggleTheme={toggleTheme}
      />
    );
  }

  // The API refuses every route except /auth/me and /auth/password while this
  // is set, so rendering the app would show a wall of failed requests.
  if (currentUser?.must_change_password) {
    return (
      <ForcePasswordChange
        user={currentUser}
        onChanged={(user) => {
          setCurrentUser(user);
          localStorage.setItem('datalink_user', JSON.stringify(user));
        }}
        onLogout={handleLogout}
      />
    );
  }

  return (
    <div className={`relative h-screen w-screen bg-[var(--bg-main)] text-[var(--text-main)] font-sans selection:bg-blue-600 selection:text-white overflow-hidden transition-colors duration-200`}>
      {/* Dynamic 3D Spatial Canvas */}
      <Spatial3DCanvas theme={theme} />

      {/* Fixed Full Screen Layout */}
      <div className="relative z-10 flex w-full h-full overflow-hidden">
        {/* Desktop Persistent Sidebar */}
        <Sidebar
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          activeJob={activeJobId ? { id: activeJobId, status: 'RUNNING' } : null}
          theme={theme}
          userRole={currentUser?.role}
        />

        {/* Fixed Content Panel */}
        <div className="flex-1 flex flex-col h-full min-w-0 overflow-hidden bg-[var(--bg-main)]">
          <Header
            onRefresh={fetchStats}
            activeJob={activeJobId ? { id: activeJobId, status: 'PROCESSING' } : null}
            searchQuery={searchQuery}
            setSearchQuery={setSearchQuery}
            setActiveTab={setActiveTab}
            theme={theme}
            toggleTheme={toggleTheme}
            onLogout={handleLogout}
            currentUser={currentUser}
          />

          {/* Active View Container (with bottom padding on mobile for the bottom nav) */}
          <main className="flex-1 flex flex-col min-h-0 overflow-hidden bg-[var(--bg-main)] pb-14 md:pb-0">
            {activeTab === 'overview' && (
              <div className="flex-1 overflow-y-auto">
                <OverviewDashboard
                  stats={stats}
                  setActiveTab={setActiveTab}
                  setSelectedJobId={setSelectedJobId}
                  theme={theme}
                />
              </div>
            )}

            {activeTab === 'upload' && (
              <div className="flex-1 overflow-y-auto">
                <UploadSection
                  onUploadComplete={handleUploadComplete}
                  activeJob={activeJobId}
                  theme={theme}
                />
              </div>
            )}

            {activeTab === 'tracker' && (
              <div className="flex-1 overflow-y-auto">
                <LiveProcessingTracker
                  jobId={activeJobId}
                  onJobCompleted={handleJobFinished}
                  setActiveTab={setActiveTab}
                  theme={theme}
                />
              </div>
            )}

            {activeTab === 'jobs' && (
              <div className="flex-1 overflow-y-auto">
                <JobDetailsView
                  selectedJobId={selectedJobId}
                  setSelectedJobId={setSelectedJobId}
                  theme={theme}
                />
              </div>
            )}

            {activeTab === 'records' && (
              <RecordsExplorer initialQuery={searchQuery} theme={theme} />
            )}

            {activeTab === 'queue' && <CallQueue />}

            {activeTab === 'team' && <UserManagement currentUser={currentUser} />}

            {activeTab === 'executive' && <ExecutiveDashboard />}

            {activeTab === 'mapping' && (
              <div className="flex-1 overflow-y-auto">
                <ColumnMappingInspector theme={theme} />
              </div>
            )}
          </main>
        </div>
      </div>

      {/* Native Mobile Bottom Navigation Bar (< md) */}
      <MobileBottomNav
        userRole={currentUser?.role}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        activeJob={activeJobId}
      />
    </div>
  );
}
