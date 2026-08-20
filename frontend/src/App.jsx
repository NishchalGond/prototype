import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import OverviewDashboard from './components/OverviewDashboard';
import UploadSection from './components/UploadSection';
import LiveProcessingTracker from './components/LiveProcessingTracker';
import RecordsExplorer from './components/RecordsExplorer';
import JobDetailsView from './components/JobDetailsView';
import ColumnMappingInspector from './components/ColumnMappingInspector';
import Spatial3DCanvas from './components/Spatial3DCanvas';

export default function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [stats, setStats] = useState(null);
  const [activeJobId, setActiveJobId] = useState(null);
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const res = await fetch('/api/dashboard/stats');
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

  return (
    <div className="relative h-screen w-screen bg-[#eef0f4] text-slate-800 font-sans selection:bg-blue-600 selection:text-white overflow-hidden">
      {/* Static Light Canvas */}
      <Spatial3DCanvas />

      {/* Fixed Full Screen Layout */}
      <div className="relative z-10 flex w-full h-full overflow-hidden">
        {/* Sidebar */}
        <Sidebar
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          activeJob={activeJobId ? { id: activeJobId, status: 'RUNNING' } : null}
        />

        {/* Fixed Content Panel */}
        <div className="flex-1 flex flex-col h-full min-w-0 overflow-hidden bg-[#eef0f4]">
          <Header
            onRefresh={fetchStats}
            activeJob={activeJobId ? { id: activeJobId, status: 'PROCESSING' } : null}
            searchQuery={searchQuery}
            setSearchQuery={setSearchQuery}
            setActiveTab={setActiveTab}
          />

          {/* Active View Container */}
          <main className="flex-1 flex flex-col min-h-0 overflow-hidden bg-[#eef0f4]">
            {activeTab === 'overview' && (
              <div className="flex-1 overflow-y-auto">
                <OverviewDashboard
                  stats={stats}
                  setActiveTab={setActiveTab}
                  setSelectedJobId={setSelectedJobId}
                />
              </div>
            )}

            {activeTab === 'upload' && (
              <div className="flex-1 overflow-y-auto">
                <UploadSection
                  onUploadComplete={handleUploadComplete}
                  activeJob={activeJobId}
                />
              </div>
            )}

            {activeTab === 'tracker' && (
              <div className="flex-1 overflow-y-auto">
                <LiveProcessingTracker
                  jobId={activeJobId}
                  onJobCompleted={handleJobFinished}
                  setActiveTab={setActiveTab}
                />
              </div>
            )}

            {activeTab === 'jobs' && (
              <div className="flex-1 overflow-y-auto">
                <JobDetailsView
                  selectedJobId={selectedJobId}
                  setSelectedJobId={setSelectedJobId}
                />
              </div>
            )}

            {activeTab === 'records' && (
              <RecordsExplorer initialQuery={searchQuery} />
            )}

            {activeTab === 'mapping' && (
              <div className="flex-1 overflow-y-auto">
                <ColumnMappingInspector />
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
