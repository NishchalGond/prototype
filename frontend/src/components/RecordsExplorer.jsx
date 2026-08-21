import React, { useState, useEffect, useRef } from 'react';
import { Search, ChevronLeft, ChevronRight, X, ArrowUpDown, ArrowUp, ArrowDown, Edit3, Save, CheckCircle2, AlertCircle, Download, FileSpreadsheet, FileText, Loader2 } from 'lucide-react';
import CustomSelect from './CustomSelect';

export default function RecordsExplorer({ initialQuery = '' }) {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isExporting, setIsExporting] = useState(null); // 'csv' | 'xlsx' | null
  const [search, setSearch] = useState(initialQuery);
  const [community, setCommunity] = useState('');
  const [propertyType, setPropertyType] = useState('');
  const [bedroom, setBedroom] = useState('');
  const [status, setStatus] = useState('');
  const [sourceFile, setSourceFile] = useState('');
  const [sortBy, setSortBy] = useState('name');
  const [sortDir, setSortDir] = useState('asc');
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(25);
  const [totalPages, setTotalPages] = useState(1);
  const [totalRecords, setTotalRecords] = useState(0);
  const [filterOptions, setFilterOptions] = useState({ communities: [], property_types: [], bedroom_types: [], source_files: [], statuses: [] });

  // Modal & Editing States
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editForm, setEditForm] = useState({});
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const overlayRef = useRef(null);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        setSelectedRecord(null);
        setIsEditing(false);
      }
    };
    if (selectedRecord) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedRecord]);

  useEffect(() => {
    fetchFilterOptions();
  }, []);

  useEffect(() => {
    fetchRecords();
  }, [search, community, propertyType, bedroom, status, sourceFile, sortBy, sortDir, page, limit]);

  const fetchFilterOptions = async () => {
    try {
      const res = await fetch('/api/records/filters');
      if (res.ok) {
        const data = await res.json();
        setFilterOptions((prev) => ({
          ...prev,
          communities: data.communities || prev.communities,
          property_types: data.property_types || prev.property_types,
          bedroom_types: data.bedrooms || data.bedroom_types || prev.bedroom_types,
          source_files: data.source_files || prev.source_files,
          statuses: data.statuses || ['VALID', 'DUPLICATE', 'ERROR']
        }));
      }
    } catch (err) {
      console.error('Error fetching filter options:', err);
    }
  };

  const fetchRecords = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        limit: limit.toString(),
        sort_by: sortBy,
        sort_dir: sortDir
      });
      if (search) params.append('q', search);
      if (community) params.append('community', community);
      if (propertyType) params.append('property_type', propertyType);
      if (bedroom) params.append('bedroom', bedroom);
      if (status) params.append('status', status);
      if (sourceFile) params.append('source_file', sourceFile);

      const res = await fetch(`/api/records?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        const items = data.items || data.records || [];
        setRecords(items);
        setTotalPages(data.total_pages || 1);
        setTotalRecords(data.total || 0);

        if (data.filter_options) {
          setFilterOptions({
            communities: data.filter_options.communities || [],
            property_types: data.filter_options.property_types || [],
            bedroom_types: data.filter_options.bedrooms || data.filter_options.bedroom_types || [],
            source_files: data.filter_options.source_files || [],
            statuses: data.filter_options.statuses || ['VALID', 'DUPLICATE', 'ERROR']
          });
        }
      }
    } catch (err) {
      console.error('Error fetching records:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleHeaderSort = (field) => {
    if (sortBy === field) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortDir('asc');
    }
    setPage(1);
  };

  const renderSortIndicator = (field) => {
    if (sortBy !== field) return <ArrowUpDown className="w-3 h-3 ml-1 opacity-40 inline" />;
    return sortDir === 'asc' ? (
      <ArrowUp className="w-3 h-3 ml-1 text-emerald-400 inline" />
    ) : (
      <ArrowDown className="w-3 h-3 ml-1 text-emerald-400 inline" />
    );
  };

  const openRecordModal = (record) => {
    setSelectedRecord(record);
    setEditForm({ ...record });
    setIsEditing(false);
    setSaveSuccess(false);
    setSaveError(null);
  };

  const handleSaveChanges = async () => {
    if (!selectedRecord) return;
    setIsSaving(true);
    setSaveError(null);
    setSaveSuccess(false);

    try {
      const res = await fetch(`/api/records/${selectedRecord.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editForm)
      });

      if (res.ok) {
        const updatedRecord = await res.json();
        setSelectedRecord(updatedRecord);
        setEditForm({ ...updatedRecord });
        setIsEditing(false);
        setSaveSuccess(true);

        // Update local list
        setRecords((prev) => prev.map((r) => (r.id === updatedRecord.id ? updatedRecord : r)));
        setTimeout(() => setSaveSuccess(false), 4000);
      } else {
        const errData = await res.json();
        setSaveError(errData.detail || 'Failed to update record in database.');
      }
    } catch (err) {
      console.error('Save error:', err);
      setSaveError('Network error saving changes to database.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleExport = async (format) => {
    if (isExporting) return;
    setIsExporting(format);
    try {
      const params = new URLSearchParams({
        format: format,
        sort_by: sortBy,
        sort_dir: sortDir,
      });
      if (search) params.append('q', search);
      if (community) params.append('community', community);
      if (propertyType) params.append('property_type', propertyType);
      if (bedroom) params.append('bedroom', bedroom);
      if (status) params.append('status', status);
      if (sourceFile) params.append('source_file', sourceFile);

      const res = await fetch(`/api/records/export?${params.toString()}`);
      if (!res.ok) {
        throw new Error('Export failed. Please check your query or try again.');
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `datalink_records_export_${new Date().toISOString().slice(0, 10)}.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export error:', err);
      alert('Failed to export data: ' + err.message);
    } finally {
      setIsExporting(null);
    }
  };

  return (
    <div className="p-6 h-full w-full max-w-[1450px] mx-auto flex flex-col min-h-0 overflow-hidden space-y-4">
      {/* Top Header & Filter Controls (Fixed, non-scrolling) */}
      <div className="flex-shrink-0 space-y-4">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <h2 className="text-2xl font-black text-slate-800 tracking-tight">Processed Dataset Explorer</h2>
            <p className="text-xs text-slate-600 mt-1 font-medium">
              Search, filter, and inspect normalized records across all ingested builder registers ({totalRecords.toLocaleString()} records). Click any row to view or edit.
            </p>
          </div>

          {/* Export Action Buttons */}
          <div className="flex items-center gap-2.5 flex-wrap">
            <button
              onClick={() => handleExport('xlsx')}
              disabled={isExporting !== null}
              className="neumorph-btn px-4 py-2.5 rounded-2xl flex items-center space-x-2 text-xs font-bold text-emerald-600 hover:text-emerald-700 active:scale-95 transition-all shadow-xs disabled:opacity-50"
              title="Download filtered records as an Excel spreadsheet (.xlsx)"
            >
              {isExporting === 'xlsx' ? (
                <Loader2 className="w-4 h-4 animate-spin text-emerald-600" />
              ) : (
                <FileSpreadsheet className="w-4 h-4 text-emerald-600" />
              )}
              <span>{isExporting === 'xlsx' ? 'Exporting Excel...' : 'Export Excel (.xlsx)'}</span>
            </button>

            <button
              onClick={() => handleExport('csv')}
              disabled={isExporting !== null}
              className="neumorph-btn px-4 py-2.5 rounded-2xl flex items-center space-x-2 text-xs font-bold text-blue-600 hover:text-blue-700 active:scale-95 transition-all shadow-xs disabled:opacity-50"
              title="Download filtered records as a CSV file (.csv)"
            >
              {isExporting === 'csv' ? (
                <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
              ) : (
                <FileText className="w-4 h-4 text-blue-600" />
              )}
              <span>{isExporting === 'csv' ? 'Exporting CSV...' : 'Export CSV (.csv)'}</span>
            </button>
          </div>
        </div>

        {/* Filter Bar */}
        <div className="neumorph-card p-4 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3">
            {/* Search Input */}
            <div className="relative lg:col-span-2">
              <Search className="w-4 h-4 absolute left-3.5 top-3 text-blue-600" />
              <input
                type="text"
                value={search}
                onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                placeholder="Search Name, Community, Unit, Mobile..."
                className="w-full neumorph-inset text-xs text-slate-800 placeholder-slate-400 rounded-2xl pl-10 pr-4 py-2.5 focus:outline-none font-medium"
              />
            </div>

            {/* Community Filter */}
            <CustomSelect
              value={community}
              onChange={(val) => { setCommunity(val); setPage(1); }}
              placeholder="All Communities"
              options={[
                { label: 'All Communities', value: '' },
                ...filterOptions.communities.map((c) => ({ label: c, value: c }))
              ]}
            />

            {/* Property Type Filter (Residential, Commercial, Land, etc.) */}
            <CustomSelect
              value={propertyType}
              onChange={(val) => { setPropertyType(val); setPage(1); }}
              placeholder="All Property Types"
              options={[
                { label: 'All Property Types', value: '' },
                { label: 'Residential', value: 'Residential' },
                { label: 'Commercial', value: 'Commercial' },
                { label: 'Land', value: 'Land' },
                ...(filterOptions.property_types || [])
                  .filter((pt) => !['Residential', 'Commercial', 'Land', 'LAND'].includes(pt))
                  .map((pt) => ({ label: pt, value: pt }))
              ]}
            />

            {/* Bedroom Filter */}
            <CustomSelect
              value={bedroom}
              onChange={(val) => { setBedroom(val); setPage(1); }}
              placeholder="All Bedroom Types"
              options={[
                { label: 'All Bedroom Types', value: '' },
                { label: 'Studio', value: 'Studio' },
                { label: '1 BR (1 Bedroom)', value: '1 BR' },
                { label: '2 BR (2 Bedroom)', value: '2 BR' },
                { label: '3 BR (3 Bedroom)', value: '3 BR' },
                { label: '4 BR (4 Bedroom)', value: '4 BR' },
                { label: '5 BR (5 Bedroom)', value: '5 BR' },
                { label: '6+ BR (Luxury Villa)', value: '6 BR' },
                { label: 'Penthouse', value: 'PENTHOUSE' },
                { label: 'Retail / Commercial', value: 'Retail' },
              ]}
            />

            {/* Status Filter */}
            <CustomSelect
              value={status}
              onChange={(val) => { setStatus(val); setPage(1); }}
              placeholder="All Valid Records"
              options={[
                { label: 'All Valid Records (Default)', value: '' },
                { label: 'VALID Only (Outreach-Ready)', value: 'VALID' },
                { label: 'DUPLICATE Only (Preserved Duplicates)', value: 'DUPLICATE' },
                { label: 'INCOMPLETE (No Name/Contact)', value: 'INCOMPLETE' },
                { label: 'ERROR / INVALID Only', value: 'INVALID' },
                { label: 'Show All (Valid + Duplicates + Incomplete)', value: 'ALL' },
              ]}
            />
          </div>
        </div>
      </div>

      {/* Main Table Container (Fills remaining height, internal scrolling only) */}
      <div className="neumorph-card rounded-3xl overflow-hidden p-2 flex-1 flex flex-col min-h-0">
        <div className="overflow-auto flex-1 min-h-0">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-300/80 bg-[#eef0f4] text-slate-700 font-mono text-[11px] whitespace-nowrap sticky top-0 z-10 shadow-xs">
                <th
                  onClick={() => handleHeaderSort('name')}
                  className="px-4 py-3.5 font-bold cursor-pointer hover:text-blue-600 transition-colors select-none group whitespace-nowrap min-w-[200px] max-w-[240px]"
                  title="Click to sort A ➔ Z or Z ➔ A by Name"
                >
                  <span className="flex items-center space-x-1.5">
                    <span>NAME</span>
                    {renderSortIndicator('name')}
                  </span>
                </th>
                <th
                  onClick={() => handleHeaderSort('developer')}
                  className="px-4 py-3.5 font-bold cursor-pointer hover:text-blue-600 transition-colors select-none group whitespace-nowrap min-w-[160px] max-w-[200px]"
                  title="Click to sort A ➔ Z or Z ➔ A by Developer"
                >
                  <span className="flex items-center space-x-1.5">
                    <span>DEVELOPER</span>
                    {renderSortIndicator('developer')}
                  </span>
                </th>
                <th
                  onClick={() => handleHeaderSort('community')}
                  className="px-4 py-3.5 font-bold cursor-pointer hover:text-blue-600 transition-colors select-none group whitespace-nowrap min-w-[140px] max-w-[180px]"
                  title="Click to sort A ➔ Z or Z ➔ A"
                >
                  <span className="flex items-center space-x-1.5">
                    <span>COMMUNITY</span>
                    {renderSortIndicator('community')}
                  </span>
                </th>
                <th
                  onClick={() => handleHeaderSort('building_cluster')}
                  className="px-4 py-3.5 font-bold cursor-pointer hover:text-blue-600 transition-colors select-none group whitespace-nowrap min-w-[140px] max-w-[180px]"
                  title="Click to sort A ➔ Z or Z ➔ A"
                >
                  <span className="flex items-center space-x-1.5">
                    <span>BUILDING</span>
                    {renderSortIndicator('building_cluster')}
                  </span>
                </th>
                <th
                  onClick={() => handleHeaderSort('unit_number')}
                  className="px-4 py-3.5 font-bold cursor-pointer hover:text-blue-600 transition-colors select-none group whitespace-nowrap min-w-[110px]"
                  title="Click to sort Unit Numbers"
                >
                  <span className="flex items-center space-x-1.5">
                    <span>UNIT</span>
                    {renderSortIndicator('unit_number')}
                  </span>
                </th>
                <th
                  onClick={() => handleHeaderSort('bedroom')}
                  className="px-4 py-3.5 font-bold cursor-pointer hover:text-blue-600 transition-colors select-none group whitespace-nowrap min-w-[100px]"
                  title="Click to sort Bedroom Types"
                >
                  <span className="flex items-center space-x-1.5">
                    <span>BEDROOM</span>
                    {renderSortIndicator('bedroom')}
                  </span>
                </th>
                <th
                  onClick={() => handleHeaderSort('procedure_value')}
                  className="px-4 py-3.5 font-bold cursor-pointer hover:text-blue-600 transition-colors select-none group whitespace-nowrap min-w-[130px]"
                  title="Click to sort Procedure Value High ➔ Low"
                >
                  <span className="flex items-center space-x-1.5">
                    <span>VALUE (AED)</span>
                    {renderSortIndicator('procedure_value')}
                  </span>
                </th>
                <th
                  onClick={() => handleHeaderSort('mobile_1')}
                  className="px-4 py-3.5 font-bold cursor-pointer hover:text-blue-600 transition-colors select-none group whitespace-nowrap min-w-[130px]"
                  title="Click to sort Mobile Numbers"
                >
                  <span className="flex items-center space-x-1.5">
                    <span>MOBILE</span>
                    {renderSortIndicator('mobile_1')}
                  </span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-300/60 font-sans">
              {loading ? (
                <tr>
                  <td colSpan="8" className="py-10 text-center text-slate-400 font-mono whitespace-nowrap">
                    Searching records database...
                  </td>
                </tr>
              ) : records.length > 0 ? (
                records.map((r) => (
                  <tr
                    key={r.id}
                    onClick={() => openRecordModal(r)}
                    className="hover:bg-[#e2e6ed] cursor-pointer transition-colors group"
                    title={`Click row to inspect full details • Status: ${r.status || 'VALID'}`}
                  >
                    <td className="px-4 py-3.5 font-black text-slate-900 group-hover:text-blue-700 transition-colors max-w-[200px] truncate" title={r.name || 'N/A'}>
                      <div className="flex items-center space-x-2.5">
                        {/* Luminous Status Indicator Dot */}
                        <span
                          title={
                            r.status === 'DUPLICATE'
                              ? 'Duplicate Record (Preserved)'
                              : r.status === 'VALID'
                              ? 'Valid Outreach Ready'
                              : r.status === 'INCOMPLETE'
                              ? 'Incomplete (Missing Contact/Name)'
                              : 'Invalid / Error'
                          }
                          className={`w-2.5 h-2.5 rounded-full shrink-0 shadow-xs ${
                            r.status === 'DUPLICATE'
                              ? 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)] animate-pulse'
                              : r.status === 'VALID'
                              ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]'
                              : r.status === 'INCOMPLETE'
                              ? 'bg-indigo-400 dark:bg-indigo-500'
                              : 'bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.6)]'
                          }`}
                        />
                        <span className="truncate">{r.name || 'N/A'}</span>
                        {r.status === 'DUPLICATE' && (
                          <span className="text-[9px] font-mono font-black uppercase px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-700 dark:text-amber-300 border border-amber-500/30">
                            DUP
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3.5 text-slate-700 font-semibold max-w-[160px] truncate" title={r.developer || 'N/A'}>
                      {r.developer || 'N/A'}
                    </td>
                    <td className="px-4 py-3.5 text-slate-700 font-semibold max-w-[150px] truncate" title={r.community || 'N/A'}>
                      {r.community || 'N/A'}
                    </td>
                    <td className="px-4 py-3.5 text-slate-700 font-semibold max-w-[140px] truncate" title={r.building_cluster || r.building || 'N/A'}>
                      {r.building_cluster || r.building || 'N/A'}
                    </td>
                    <td className="px-4 py-3.5 font-mono text-blue-700 font-black whitespace-nowrap">
                      {r.unit_number || r.unit || (r.plot_number ? `Plot ${r.plot_number}` : 'N/A')}
                    </td>
                    <td className="px-4 py-3.5 font-mono text-slate-700 font-medium whitespace-nowrap">
                      {r.bedroom || r.bedroom_type || 'N/A'}
                    </td>
                    <td className="px-4 py-3.5 font-mono text-emerald-700 font-black whitespace-nowrap">
                      {r.procedure_value ? `AED ${Number(r.procedure_value).toLocaleString('en-US')}` : 'N/A'}
                    </td>
                    <td className="px-4 py-3.5 font-mono text-slate-700 font-medium whitespace-nowrap">
                      {r.mobile_1 || r.mobile || 'N/A'}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="8" className="py-10 text-center text-slate-500 font-mono">
                    No records found matching filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        <div className="p-4 border-t border-slate-300/80 flex items-center justify-between font-mono text-xs text-slate-600 bg-[#eef0f4]">
          <div>
            Showing page <span className="text-slate-900 font-bold">{page}</span> of{' '}
            <span className="text-slate-900 font-bold">{totalPages}</span> ({totalRecords.toLocaleString()} total records)
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="neumorph-button p-2 text-slate-700 disabled:opacity-40"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="neumorph-button p-2 text-slate-700 disabled:opacity-40"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Record Inspector Detail & Editing Modal */}
      {selectedRecord && (
        <div
          ref={overlayRef}
          onClick={(e) => {
            if (e.target === overlayRef.current) {
              setSelectedRecord(null);
              setIsEditing(false);
            }
          }}
          className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-md flex items-center justify-center p-4 cursor-pointer"
        >
          <div className="neumorph-card max-w-2xl w-full rounded-3xl p-6 space-y-4 border border-white/80 bg-[#eef0f4] shadow-[12px_12px_30px_#cbd2dc,-12px_-12px_30px_#ffffff] text-slate-800 animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="flex justify-between items-center border-b border-slate-300/80 pb-3">
              <div>
                <span className="text-[10px] font-mono text-blue-600 font-bold uppercase">
                  Record Inspector #{selectedRecord.id}
                </span>
                <h3 className="text-lg font-black text-slate-900">
                  {isEditing ? (
                    <span className="text-emerald-600 flex items-center space-x-1.5">
                      <Edit3 className="w-4 h-4" />
                      <span>Editing Record Data</span>
                    </span>
                  ) : (
                    selectedRecord.name || selectedRecord.developer || 'Record Details'
                  )}
                </h3>
              </div>

              {/* Action Buttons: Edit / Save / Cancel / Close */}
              <div className="flex items-center space-x-2">
                {!isEditing ? (
                  <button
                    onClick={() => setIsEditing(true)}
                    className="neumorph-button-primary px-3.5 py-1.5 text-xs font-bold flex items-center space-x-1.5"
                  >
                    <Edit3 className="w-3.5 h-3.5" />
                    <span>Edit Record</span>
                  </button>
                ) : (
                  <>
                    <button
                      onClick={handleSaveChanges}
                      disabled={isSaving}
                      className="neumorph-button-primary px-4 py-1.5 text-xs font-bold flex items-center space-x-1.5"
                    >
                      {isSaving ? (
                        <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                      ) : (
                        <Save className="w-3.5 h-3.5" />
                      )}
                      <span>Save to Database</span>
                    </button>
                    <button
                      onClick={() => {
                        setIsEditing(false);
                        setEditForm({ ...selectedRecord });
                      }}
                      className="neumorph-button px-3 py-1.5 text-slate-700 text-xs font-bold"
                    >
                      Cancel
                    </button>
                  </>
                )}

                <button
                  onClick={() => {
                    setSelectedRecord(null);
                    setIsEditing(false);
                  }}
                  className="neumorph-button p-1.5 text-slate-600 hover:text-slate-900"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Notification Banners */}
            {saveSuccess && (
              <div className="p-3 rounded-2xl bg-emerald-950/80 border border-emerald-500/40 text-emerald-300 text-xs font-mono font-bold flex items-center space-x-2 animate-in fade-in">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span>✓ Record updated and saved to SQLite database successfully!</span>
              </div>
            )}

            {saveError && (
              <div className="p-3 rounded-2xl bg-rose-950/80 border border-rose-800/80 text-rose-300 text-xs font-mono font-bold flex items-center space-x-2 animate-in fade-in">
                <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                <span>⚠ Error: {saveError}</span>
              </div>
            )}

            {/* Modal Body */}
            <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-1">
              {/* Top Hero Banner: Property Value & Date */}
              <div className="p-4 rounded-2xl bg-[#eef0f4] border border-slate-300/80 shadow-[inset_3px_3px_6px_#cbd2dc,inset_-3px_-3px_6px_#ffffff] flex items-center justify-between">
                <div>
                  <span className="text-emerald-700 text-[10px] block font-black uppercase tracking-wider">PROCEDURE VALUE (PROPERTY VALUE AED)</span>
                  {isEditing ? (
                    <input
                      type="number"
                      value={editForm.procedure_value || ''}
                      onChange={(e) => setEditForm({ ...editForm, procedure_value: e.target.value ? Number(e.target.value) : null })}
                      placeholder="e.g. 1050000"
                      className="neumorph-inset text-emerald-700 font-black text-sm rounded-xl px-2.5 py-1 mt-1 focus:outline-none font-mono"
                    />
                  ) : (
                    <span className="text-emerald-700 text-lg font-black font-mono">
                      {selectedRecord.procedure_value ? `AED ${Number(selectedRecord.procedure_value).toLocaleString('en-US')}` : 'N/A / Unspecified'}
                    </span>
                  )}
                </div>

                <div className="text-right">
                  <span className="text-blue-700 text-[10px] block font-black uppercase tracking-wider">STATUS</span>
                  {isEditing ? (
                    <select
                      value={editForm.status || 'VALID'}
                      onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}
                      className="neumorph-inset text-slate-800 font-bold text-xs rounded-xl px-2 py-1 mt-1 focus:outline-none font-mono"
                    >
                      <option value="VALID">VALID</option>
                      <option value="INCOMPLETE">INCOMPLETE</option>
                      <option value="DUPLICATE">DUPLICATE</option>
                      <option value="ERROR">ERROR</option>
                    </select>
                  ) : (
                    <span className={`text-xs font-black font-mono px-2.5 py-1 rounded-full border inline-block ${
                      selectedRecord.status === 'VALID'
                        ? 'text-emerald-700 bg-emerald-500/10 border-emerald-500/30'
                        : selectedRecord.status === 'INCOMPLETE'
                        ? 'text-amber-700 bg-amber-500/10 border-amber-500/30'
                        : selectedRecord.status === 'DUPLICATE'
                        ? 'text-purple-700 bg-purple-500/10 border-purple-500/30'
                        : 'text-rose-700 bg-rose-500/10 border-rose-500/30'
                    }`}>
                      {selectedRecord.status}
                    </span>
                  )}
                </div>
              </div>

              {/* Section 1: Location & Property Identity */}
              <div className="space-y-2">
                <span className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-wider block">1. Location & Property Identification</span>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 text-xs font-mono">
                  {/* Community */}
                  <div className="p-2.5 rounded-xl bg-[#eef0f4] border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc]">
                    <span className="text-slate-500 text-[10px] block font-bold">COMMUNITY</span>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editForm.community || ''}
                        onChange={(e) => setEditForm({ ...editForm, community: e.target.value })}
                        className="neumorph-inset text-slate-800 font-bold rounded-lg px-2 py-1 mt-1 w-full focus:outline-none"
                      />
                    ) : (
                      <span className="text-slate-900 font-bold">{selectedRecord.community || 'N/A'}</span>
                    )}
                  </div>

                  {/* Sub-Community */}
                  <div className="p-2.5 rounded-xl bg-[#eef0f4] border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc]">
                    <span className="text-slate-500 text-[10px] block font-bold">SUB-COMMUNITY</span>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editForm.sub_community || ''}
                        onChange={(e) => setEditForm({ ...editForm, sub_community: e.target.value })}
                        className="neumorph-inset text-slate-800 font-bold rounded-lg px-2 py-1 mt-1 w-full focus:outline-none"
                      />
                    ) : (
                      <span className="text-slate-900 font-bold">{selectedRecord.sub_community || 'N/A'}</span>
                    )}
                  </div>

                  {/* Building */}
                  <div className="p-2.5 rounded-xl bg-[#eef0f4] border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc]">
                    <span className="text-slate-500 text-[10px] block font-bold">BUILDING / CLUSTER</span>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editForm.building_cluster || ''}
                        onChange={(e) => setEditForm({ ...editForm, building_cluster: e.target.value })}
                        className="neumorph-inset text-slate-800 font-bold rounded-lg px-2 py-1 mt-1 w-full focus:outline-none"
                      />
                    ) : (
                      <span className="text-slate-900 font-bold">{selectedRecord.building_cluster || selectedRecord.building || 'N/A'}</span>
                    )}
                  </div>

                  {/* Unit Number */}
                  <div className="p-2.5 rounded-xl bg-[#eef0f4] border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc]">
                    <span className="text-slate-500 text-[10px] block font-bold">UNIT NUMBER</span>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editForm.unit_number || ''}
                        onChange={(e) => setEditForm({ ...editForm, unit_number: e.target.value })}
                        className="neumorph-inset text-blue-700 font-bold rounded-lg px-2 py-1 mt-1 w-full focus:outline-none"
                      />
                    ) : (
                      <span className="text-blue-700 font-black">{selectedRecord.unit_number || selectedRecord.unit || 'N/A'}</span>
                    )}
                  </div>

                  {/* Bedroom */}
                  <div className="p-2.5 rounded-xl bg-[#eef0f4] border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc]">
                    <span className="text-slate-500 text-[10px] block font-bold">BEDROOM</span>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editForm.bedroom || ''}
                        onChange={(e) => setEditForm({ ...editForm, bedroom: e.target.value })}
                        className="neumorph-inset text-slate-800 font-bold rounded-lg px-2 py-1 mt-1 w-full focus:outline-none"
                      />
                    ) : (
                      <span className="text-slate-900 font-bold">{selectedRecord.bedroom || selectedRecord.bedroom_type || 'N/A'}</span>
                    )}
                  </div>

                  {/* Size */}
                  <div className="p-2.5 rounded-xl bg-[#eef0f4] border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc]">
                    <span className="text-slate-500 text-[10px] block font-bold">SIZE (SQ.FT)</span>
                    {isEditing ? (
                      <input
                        type="number"
                        value={editForm.size || ''}
                        onChange={(e) => setEditForm({ ...editForm, size: e.target.value ? Number(e.target.value) : null })}
                        className="neumorph-inset text-slate-800 font-bold rounded-lg px-2 py-1 mt-1 w-full focus:outline-none"
                      />
                    ) : (
                      <span className="text-slate-900 font-bold">{selectedRecord.size ? `${selectedRecord.size} sq.ft` : 'N/A'}</span>
                    )}
                  </div>

                  {/* Property Type */}
                  <div className="p-2.5 rounded-xl bg-[#eef0f4] border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc]">
                    <span className="text-slate-500 text-[10px] block font-bold">PROPERTY TYPE</span>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editForm.property_type || ''}
                        onChange={(e) => setEditForm({ ...editForm, property_type: e.target.value })}
                        className="neumorph-inset text-slate-800 font-bold rounded-lg px-2 py-1 mt-1 w-full focus:outline-none"
                      />
                    ) : (
                      <span className="text-slate-900 font-bold">{selectedRecord.property_type || 'N/A'}</span>
                    )}
                  </div>

                  {/* Developer */}
                  <div className="p-2.5 rounded-xl bg-[#eef0f4] border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc]">
                    <span className="text-slate-500 text-[10px] block font-bold">DEVELOPER</span>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editForm.developer || ''}
                        onChange={(e) => setEditForm({ ...editForm, developer: e.target.value })}
                        className="neumorph-inset text-slate-800 font-bold rounded-lg px-2 py-1 mt-1 w-full focus:outline-none"
                      />
                    ) : (
                      <span className="text-slate-900 font-bold">{selectedRecord.developer || 'N/A'}</span>
                    )}
                  </div>

                  {/* Project */}
                  <div className="p-2.5 rounded-xl bg-[#eef0f4] border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc]">
                    <span className="text-slate-500 text-[10px] block font-bold">PROJECT</span>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editForm.project || ''}
                        onChange={(e) => setEditForm({ ...editForm, project: e.target.value })}
                        className="neumorph-inset text-slate-800 font-bold rounded-lg px-2 py-1 mt-1 w-full focus:outline-none"
                      />
                    ) : (
                      <span className="text-slate-900 font-bold">{selectedRecord.project || 'N/A'}</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Section 2: Person & Contact Information */}
              <div className="space-y-2">
                <span className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-wider block">2. Personal Contact & Identity</span>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 text-xs font-mono">
                  {/* Name */}
                  <div className="p-2.5 rounded-xl bg-[#eef0f4] border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc] col-span-2">
                    <span className="text-slate-500 text-[10px] block font-bold">NAME</span>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editForm.name || ''}
                        onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                        className="neumorph-inset text-slate-800 font-bold rounded-lg px-2 py-1 mt-1 w-full focus:outline-none"
                      />
                    ) : (
                      <span className="text-slate-900 font-black">{selectedRecord.name || 'N/A'}</span>
                    )}
                  </div>

                  {/* Party Type */}
                  <div className="p-2.5 rounded-xl bg-[#eef0f4] border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc]">
                    <span className="text-slate-500 text-[10px] block font-bold">TYPE (BUYER/SELLER)</span>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editForm.party_type || ''}
                        onChange={(e) => setEditForm({ ...editForm, party_type: e.target.value })}
                        className="neumorph-inset text-slate-800 font-bold rounded-lg px-2 py-1 mt-1 w-full focus:outline-none"
                      />
                    ) : (
                      <span className="text-slate-900 font-bold">{selectedRecord.party_type || 'N/A'}</span>
                    )}
                  </div>

                  {/* Mobile 1 */}
                  <div className="p-2.5 rounded-xl bg-[#eef0f4] border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc]">
                    <span className="text-slate-500 text-[10px] block font-bold">MOBILE 1</span>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editForm.mobile_1 || ''}
                        onChange={(e) => setEditForm({ ...editForm, mobile_1: e.target.value })}
                        className="neumorph-inset text-slate-800 font-bold rounded-lg px-2 py-1 mt-1 w-full focus:outline-none"
                      />
                    ) : (
                      <span className="text-slate-900 font-bold">{selectedRecord.mobile_1 || selectedRecord.mobile || 'N/A'}</span>
                    )}
                  </div>

                  {/* Mobile 2 */}
                  <div className="p-2.5 rounded-xl bg-[#eef0f4] border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc]">
                    <span className="text-slate-500 text-[10px] block font-bold">MOBILE 2</span>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editForm.mobile_2 || ''}
                        onChange={(e) => setEditForm({ ...editForm, mobile_2: e.target.value })}
                        className="neumorph-inset text-slate-800 font-bold rounded-lg px-2 py-1 mt-1 w-full focus:outline-none"
                      />
                    ) : (
                      <span className="text-slate-900 font-bold">{selectedRecord.mobile_2 || 'N/A'}</span>
                    )}
                  </div>

                  {/* Mobile 3 */}
                  <div className="p-2.5 rounded-xl bg-[#eef0f4] border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc]">
                    <span className="text-slate-500 text-[10px] block font-bold">MOBILE 3</span>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editForm.mobile_3 || ''}
                        onChange={(e) => setEditForm({ ...editForm, mobile_3: e.target.value })}
                        className="neumorph-inset text-slate-800 font-bold rounded-lg px-2 py-1 mt-1 w-full focus:outline-none"
                      />
                    ) : (
                      <span className="text-slate-900 font-bold">{selectedRecord.mobile_3 || 'N/A'}</span>
                    )}
                  </div>

                  {/* Email Address */}
                  <div className="p-2.5 rounded-xl bg-[#eef0f4] border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc] col-span-2">
                    <span className="text-slate-500 text-[10px] block font-bold">EMAIL ADDRESS</span>
                    {isEditing ? (
                      <input
                        type="email"
                        value={editForm.email_address || ''}
                        onChange={(e) => setEditForm({ ...editForm, email_address: e.target.value })}
                        className="neumorph-inset text-slate-800 font-bold rounded-lg px-2 py-1 mt-1 w-full focus:outline-none"
                      />
                    ) : (
                      <span className="text-slate-900 font-bold">{selectedRecord.email_address || 'N/A'}</span>
                    )}
                  </div>

                  {/* PI Number */}
                  <div className="p-2.5 rounded-xl bg-[#eef0f4] border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc]">
                    <span className="text-slate-500 text-[10px] block font-bold">PI NUMBER / ID</span>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editForm.pi_number || ''}
                        onChange={(e) => setEditForm({ ...editForm, pi_number: e.target.value })}
                        className="neumorph-inset text-slate-800 font-bold rounded-lg px-2 py-1 mt-1 w-full focus:outline-none"
                      />
                    ) : (
                      <span className="text-slate-900 font-bold">{selectedRecord.pi_number || 'N/A'}</span>
                    )}
                  </div>

                  {/* Nationality */}
                  <div className="p-2.5 rounded-xl bg-[#eef0f4] border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc]">
                    <span className="text-slate-500 text-[10px] block font-bold">NATIONALITY</span>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editForm.nationality || ''}
                        onChange={(e) => setEditForm({ ...editForm, nationality: e.target.value })}
                        className="neumorph-inset text-slate-800 font-bold rounded-lg px-2 py-1 mt-1 w-full focus:outline-none"
                      />
                    ) : (
                      <span className="text-slate-900 font-bold">{selectedRecord.nationality || 'N/A'}</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Section 3: Land & Registry Metadata */}
              <div className="space-y-2">
                <span className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-wider block">3. Land & Municipality Registry</span>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs font-mono">
                  {/* Plot Reg No */}
                  <div className="p-2.5 rounded-xl bg-[#eef0f4] border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc]">
                    <span className="text-slate-500 text-[10px] block font-bold">PLOT REG. NO</span>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editForm.plot_reg_no || ''}
                        onChange={(e) => setEditForm({ ...editForm, plot_reg_no: e.target.value })}
                        className="neumorph-inset text-slate-800 font-bold rounded-lg px-2 py-1 mt-1 w-full focus:outline-none"
                      />
                    ) : (
                      <span className="text-slate-900 font-bold">{selectedRecord.plot_reg_no || 'N/A'}</span>
                    )}
                  </div>

                  {/* Plot Number */}
                  <div className="p-2.5 rounded-xl bg-[#eef0f4] border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc]">
                    <span className="text-slate-500 text-[10px] block font-bold">PLOT NUMBER</span>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editForm.plot_number || ''}
                        onChange={(e) => setEditForm({ ...editForm, plot_number: e.target.value })}
                        className="neumorph-inset text-slate-800 font-bold rounded-lg px-2 py-1 mt-1 w-full focus:outline-none"
                      />
                    ) : (
                      <span className="text-slate-900 font-bold">{selectedRecord.plot_number || 'N/A'}</span>
                    )}
                  </div>

                  {/* DMNO */}
                  <div className="p-2.5 rounded-xl bg-[#eef0f4] border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc]">
                    <span className="text-slate-500 text-[10px] block font-bold">DMNO</span>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editForm.dmno || ''}
                        onChange={(e) => setEditForm({ ...editForm, dmno: e.target.value })}
                        className="neumorph-inset text-slate-800 font-bold rounded-lg px-2 py-1 mt-1 w-full focus:outline-none"
                      />
                    ) : (
                      <span className="text-slate-900 font-bold">{selectedRecord.dmno || 'N/A'}</span>
                    )}
                  </div>

                  {/* DMSUBNO */}
                  <div className="p-2.5 rounded-xl bg-[#eef0f4] border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc]">
                    <span className="text-slate-500 text-[10px] block font-bold">DMSUBNO</span>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editForm.dmsubno || ''}
                        onChange={(e) => setEditForm({ ...editForm, dmsubno: e.target.value })}
                        className="neumorph-inset text-slate-800 font-bold rounded-lg px-2 py-1 mt-1 w-full focus:outline-none"
                      />
                    ) : (
                      <span className="text-slate-900 font-bold">{selectedRecord.dmsubno || 'N/A'}</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Provenance Footer */}
              <div className="p-2.5 rounded-xl bg-[#eef0f4] border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc] font-mono text-xs">
                <span className="text-slate-500 text-[10px] block font-bold">SOURCE FILE PROVENANCE</span>
                <span className="text-emerald-700 font-bold">{selectedRecord.source_file} (Row #{selectedRecord.source_row})</span>
              </div>
            </div>

            <div className="pt-2 flex justify-between items-center border-t border-slate-300/80">
              <span className="text-[10px] font-mono text-slate-500">Click any row in the dataset table to inspect or edit.</span>
              <button
                onClick={() => {
                  setSelectedRecord(null);
                  setIsEditing(false);
                }}
                className="neumorph-button-primary px-5 py-2.5 text-xs font-bold"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
