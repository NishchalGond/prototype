import React, { useState, useEffect } from 'react';
import {
  Upload,
  FileCheck,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  Play,
  FileCode,
  Layers,
  Layers3,
  Plus,
  Trash2,
  FileSpreadsheet,
  ShieldCheck,
  ArrowRight,
} from 'lucide-react';
import Tilt3DCard from './Tilt3DCard';
import CustomSelect from './CustomSelect';

export default function UploadSection({ onUploadComplete, activeJob }) {
  const [fileQueue, setFileQueue] = useState([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [batchSize, setBatchSize] = useState(500);
  const [isProcessingQueue, setIsProcessingQueue] = useState(false);
  const [isInspectingQueue, setIsInspectingQueue] = useState(false);
  const [activeQueueIndex, setActiveQueueIndex] = useState(null);
  const [selectedFileForRemap, setSelectedFileForRemap] = useState(null);
  const [columnOverrides, setColumnOverrides] = useState({});
  const [targetFieldsList, setTargetFieldsList] = useState([]);
  const [globalError, setGlobalError] = useState(null);

  useEffect(() => {
    fetchMappingSchema();

    // Window-level drag listeners to enable dropping files from anywhere
    const onWindowDragOver = (e) => {
      e.preventDefault();
      setIsDragOver(true);
    };
    const onWindowDragLeave = (e) => {
      if (e.clientX === 0 || e.clientY === 0) {
        setIsDragOver(false);
      }
    };
    const onWindowDrop = (e) => {
      e.preventDefault();
      setIsDragOver(false);
    };

    window.addEventListener('dragover', onWindowDragOver);
    window.addEventListener('dragleave', onWindowDragLeave);
    window.addEventListener('drop', onWindowDrop);

    return () => {
      window.removeEventListener('dragover', onWindowDragOver);
      window.removeEventListener('dragleave', onWindowDragLeave);
      window.removeEventListener('drop', onWindowDrop);
    };
  }, []);

  const fetchMappingSchema = async () => {
    try {
      const res = await fetch('/api/column-mappings');
      if (res.ok) {
        const data = await res.json();
        setTargetFieldsList(data.target_fields || []);
      }
    } catch (err) {
      console.error('Failed to fetch mapping schema:', err);
    }
  };

  const getFilesFromDataTransfer = async (dataTransfer) => {
    const validExtensions = ['.xlsx', '.xls', '.csv'];
    const files = [];

    // Helper to read directory recursively when user drags a folder
    const readEntry = async (entry) => {
      if (!entry) return;
      if (entry.isFile) {
        const file = await new Promise((resolve) => entry.file(resolve));
        if (file) {
          const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
          if (validExtensions.includes(ext) && !file.name.startsWith('~$') && !file.name.startsWith('._')) {
            files.push(file);
          }
        }
      } else if (entry.isDirectory) {
        const dirReader = entry.createReader();
        const entries = await new Promise((resolve) => {
          const allEntries = [];
          const readBatch = () => {
            dirReader.readEntries((results) => {
              if (!results || !results.length) {
                resolve(allEntries);
              } else {
                allEntries.push(...results);
                readBatch();
              }
            }, () => resolve(allEntries));
          };
          readBatch();
        });
        for (const child of entries) {
          await readEntry(child);
        }
      }
    };

    if (dataTransfer.items && dataTransfer.items.length > 0) {
      const items = Array.from(dataTransfer.items);
      for (const item of items) {
        if (item.webkitGetAsEntry) {
          const entry = item.webkitGetAsEntry();
          if (entry) {
            await readEntry(entry);
            continue;
          }
        }
        const file = item.getAsFile();
        if (file) {
          const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
          if (validExtensions.includes(ext) && !file.name.startsWith('~$') && !file.name.startsWith('._')) {
            files.push(file);
          }
        }
      }
    } else if (dataTransfer.files && dataTransfer.files.length > 0) {
      for (const file of Array.from(dataTransfer.files)) {
        const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
        if (validExtensions.includes(ext) && !file.name.startsWith('~$') && !file.name.startsWith('._')) {
          files.push(file);
        }
      }
    }

    return files;
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setIsDragOver(true);
    } else if (e.type === 'dragleave') {
      setIsDragOver(false);
    }
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    
    const files = await getFilesFromDataTransfer(e.dataTransfer);
    if (files.length > 0) {
      addFilesToQueue(files);
    } else {
      setGlobalError('Please select or drop valid Excel (.xlsx, .xls) or CSV (.csv) files.');
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      addFilesToQueue(Array.from(e.target.files));
    }
  };

  const addFilesToQueue = (files) => {
    const validExtensions = ['.xlsx', '.xls', '.csv'];
    const newItems = files
      .filter((f) => {
        const ext = f.name.substring(f.name.lastIndexOf('.')).toLowerCase();
        return validExtensions.includes(ext) && !f.name.startsWith('~$') && !f.name.startsWith('._');
      })
      .map((f) => ({
        id: Math.random().toString(36).substring(2, 9),
        file: f,
        name: f.name,
        size: f.size,
        status: 'QUEUED',
        processedRows: 0,
        totalRows: 0,
        error: null,
        uploadResult: null,
      }));

    if (newItems.length === 0) {
      setGlobalError('Please select valid Excel (.xlsx, .xls) or CSV (.csv) files.');
      return;
    }

    setGlobalError(null);
    setFileQueue((prev) => [...prev, ...newItems]);
  };

  const removeFromQueue = (id) => {
    setFileQueue((prev) => prev.filter((item) => item.id !== id));
    if (selectedFileForRemap && selectedFileForRemap.id === id) {
      setSelectedFileForRemap(null);
    }
  };

  const clearQueue = () => {
    setFileQueue([]);
    setSelectedFileForRemap(null);
    setActiveQueueIndex(null);
  };

  const inspectSingleFile = async (item) => {
    const formData = new FormData();
    formData.append('file', item.file);

    const res = await fetch('/api/upload/inspect', {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `Failed to inspect file ${item.name}`);
    }

    const data = await res.json();
    return data;
  };

  const inspectQueueFile = async (item) => {
    setFileQueue((prev) =>
      prev.map((f) => (f.id === item.id ? { ...f, status: 'INSPECTING', error: null } : f))
    );

    try {
      const result = await inspectSingleFile(item);
      setFileQueue((prev) =>
        prev.map((f) =>
          f.id === item.id
            ? {
                ...f,
                status: 'INSPECTED',
                uploadResult: result,
                totalRows: result.total_rows_estimate || 0,
              }
            : f
        )
      );

      const initialMap = {};
      if (result.mapped_columns_preview) {
        result.mapped_columns_preview.forEach((c) => {
          initialMap[c.raw_header] = c.mapped_target || '';
        });
      }

      setSelectedFileForRemap({
        ...item,
        uploadResult: result,
      });
      setColumnOverrides(initialMap);
    } catch (err) {
      setFileQueue((prev) =>
        prev.map((f) => (f.id === item.id ? { ...f, status: 'FAILED', error: err.message } : f))
      );
    }
  };

  const inspectAllQueueFiles = async () => {
    if (isInspectingQueue || isProcessingQueue) return;
    setIsInspectingQueue(true);

    for (let i = 0; i < fileQueue.length; i++) {
      const item = fileQueue[i];
      if (item.status === 'QUEUED' || item.status === 'FAILED') {
        setActiveQueueIndex(i);
        await inspectQueueFile(item);
      }
    }

    setIsInspectingQueue(false);
    setActiveQueueIndex(null);
  };

  const processSingleFile = async (fileIndex) => {
    const queueItem = fileQueue[fileIndex];
    if (!queueItem) return;

    setActiveQueueIndex(fileIndex);
    setFileQueue((prev) =>
      prev.map((f, idx) => (idx === fileIndex ? { ...f, status: 'PROCESSING', error: null } : f))
    );

    try {
      const formData = new FormData();
      formData.append('file', queueItem.file);

      const uploadRes = await fetch(`/api/upload?batch_size=${batchSize}`, {
        method: 'POST',
        body: formData,
      });

      if (!uploadRes.ok) {
        const errData = await uploadRes.json();
        throw new Error(errData.detail || 'File upload failed');
      }

      const uploadData = await uploadRes.json();
      const jobId = uploadData.job_id;

      if (Object.keys(columnOverrides).length > 0 && selectedFileForRemap?.id === queueItem.id) {
        await fetch(`/api/jobs/${jobId}/mapping-overrides`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ overrides: columnOverrides }),
        });
      }

      const startRes = await fetch(`/api/jobs/${jobId}/start`, { method: 'POST' });
      if (!startRes.ok) {
        const errData = await startRes.json();
        throw new Error(errData.detail || 'Failed to start processing job');
      }

      let isFinished = false;
      while (!isFinished) {
        await new Promise((r) => setTimeout(r, 1000));
        const statusRes = await fetch(`/api/jobs/${jobId}`);
        if (statusRes.ok) {
          const sData = await statusRes.json();
          setFileQueue((prev) =>
            prev.map((f, idx) =>
              idx === fileIndex
                ? {
                    ...f,
                    processedRows: sData.processed_rows || 0,
                    totalRows: sData.total_rows || f.totalRows,
                  }
                : f
            )
          );

          if (sData.status === 'COMPLETED' || sData.status === 'COMPLETED_WITH_ERRORS') {
            isFinished = true;
            setFileQueue((prev) =>
              prev.map((f, idx) =>
                idx === fileIndex ? { ...f, status: 'COMPLETED', jobResult: sData } : f
              )
            );
            if (onUploadComplete) onUploadComplete(jobId);
          } else if (sData.status === 'FAILED') {
            isFinished = true;
            setFileQueue((prev) =>
              prev.map((f, idx) =>
                idx === fileIndex
                  ? { ...f, status: 'FAILED', error: sData.error_message || 'Processing failed' }
                  : f
              )
            );
          }
        }
      }
    } catch (err) {
      console.error(`Error processing file ${queueItem.name}:`, err);
      setFileQueue((prev) =>
        prev.map((f, idx) =>
          idx === fileIndex ? { ...f, status: 'FAILED', error: err.message } : f
        )
      );
    } finally {
      setActiveQueueIndex(null);
    }
  };

  const startBatchQueueProcessing = async () => {
    if (isProcessingQueue || fileQueue.length === 0) return;
    setIsProcessingQueue(true);

    for (let i = 0; i < fileQueue.length; i++) {
      if (fileQueue[i].status !== 'COMPLETED') {
        await processSingleFile(i);
      }
    }

    setIsProcessingQueue(false);
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Title Header */}
      <Tilt3DCard className="p-6 rounded-3xl">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <div className="flex items-center space-x-2">
              <span className="px-3 py-1 rounded-full bg-[#eef0f4] text-blue-600 font-mono text-[10px] font-black tracking-wider border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc,inset_-2px_-2px_4px_#ffffff]">
                MULTI-REGISTER BATCH STUDIO
              </span>
            </div>
            <h2 className="text-2xl font-black text-slate-800 tracking-tight mt-2">Ingestion & Inspection Studio</h2>
            <p className="text-xs text-slate-600 mt-1 font-medium">
              Upload multiple registers. Inspect schema mappings across all files with <strong>Inspect All</strong>, then execute automated batch queueing with <strong>Run All</strong> directly into Supabase.
            </p>
          </div>

          {/* Global Action Controls */}
          {fileQueue.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={clearQueue}
                disabled={isProcessingQueue || isInspectingQueue}
                className="neumorph-button px-3.5 py-2 text-slate-700 font-bold text-xs"
              >
                Clear Queue
              </button>

              <button
                onClick={inspectAllQueueFiles}
                disabled={
                  isInspectingQueue ||
                  isProcessingQueue ||
                  !fileQueue.some((f) => f.status === 'QUEUED' || f.status === 'FAILED')
                }
                className="neumorph-button px-4 py-2 text-blue-600 font-bold text-xs flex items-center space-x-2"
              >
                {isInspectingQueue ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin text-blue-600" />
                    <span>Inspecting Files...</span>
                  </>
                ) : (
                  <>
                    <FileCode className="w-3.5 h-3.5 text-blue-600" />
                    <span>Inspect All ({fileQueue.filter((f) => f.status === 'QUEUED').length})</span>
                  </>
                )}
              </button>

              <button
                onClick={startBatchQueueProcessing}
                disabled={isProcessingQueue || isInspectingQueue || fileQueue.every((f) => f.status === 'COMPLETED')}
                className="neumorph-button-primary px-5 py-2 text-xs font-bold flex items-center space-x-2"
              >
                {isProcessingQueue ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin text-white" />
                    <span>Running Batch Queue...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 fill-white" />
                    <span>Run All ({fileQueue.filter((f) => f.status !== 'COMPLETED').length} Files)</span>
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      </Tilt3DCard>

      {/* Drag & Drop Multi-File Zone */}
      <Tilt3DCard className="p-8 text-center border border-slate-300/80">
        <div
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
          className="space-y-4"
        >
          <input
            type="file"
            id="file-upload-multi"
            accept=".xlsx,.xls,.csv"
            multiple
            onChange={handleFileChange}
            className="hidden"
          />

          <div className="w-16 h-16 mx-auto rounded-3xl bg-[#eef0f4] border border-white/80 flex items-center justify-center text-blue-600 shadow-[inset_4px_4px_8px_#cbd2dc,inset_-4px_-4px_8px_#ffffff]">
            <Layers3 className="w-8 h-8 text-blue-600" />
          </div>

          <div className="space-y-2">
            <p className="text-lg font-black text-slate-800 tracking-tight">
              Drag and drop multiple Excel or CSV files here
            </p>
            <p className="text-xs text-slate-500 font-mono">
              Select 1 or 20+ registers simultaneously (.xlsx, .xls, .csv). Batch engine processes files sequentially.
            </p>
            <label
              htmlFor="file-upload-multi"
              className="neumorph-button-primary inline-flex items-center space-x-2 px-6 py-3 text-xs font-black"
            >
              <Plus className="w-4 h-4" />
              <span>Select Multiple Files</span>
            </label>
          </div>
        </div>
      </Tilt3DCard>

      {globalError && (
        <div className="p-4 rounded-2xl bg-[#eef0f4] border border-rose-300 text-rose-700 text-xs font-mono font-bold flex items-center space-x-2 shadow-[inset_3px_3px_6px_#cbd2dc]">
          <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          <span>{globalError}</span>
        </div>
      )}

      {/* Multi-File Batch Queue List */}
      {fileQueue.length > 0 && (
        <Tilt3DCard className="p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-300/60 pb-3">
            <div className="flex items-center space-x-2 font-mono text-xs font-bold text-slate-800">
              <Layers className="w-4 h-4 text-blue-600" />
              <span>INGESTION QUEUE PIPELINE ({fileQueue.length} FILES)</span>
            </div>

            {/* Batch Size Selector */}
            <div className="flex items-center space-x-2">
              <span className="text-xs text-slate-600 font-medium">Batch Size:</span>
              <CustomSelect
                value={batchSize}
                onChange={(val) => setBatchSize(Number(val))}
                options={[
                  { label: '250 rows / batch', value: 250 },
                  { label: '500 rows / batch', value: 500 },
                  { label: '1000 rows / batch', value: 1000 },
                ]}
              />
            </div>
          </div>

          <div className="space-y-2.5 max-h-96 overflow-y-auto pr-1">
            {fileQueue.map((item, idx) => (
              <div
                key={item.id}
                className={`p-3.5 rounded-2xl border transition-all flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs font-mono ${
                  activeQueueIndex === idx
                    ? 'bg-[#eef0f4] border-blue-400 shadow-[inset_3px_3px_6px_#cbd2dc,inset_-3px_-3px_6px_#ffffff]'
                    : item.status === 'COMPLETED'
                    ? 'bg-[#eef0f4] border-emerald-300 shadow-[4px_4px_10px_#cbd2dc,-4px_-4px_10px_#ffffff]'
                    : item.status === 'FAILED'
                    ? 'bg-[#eef0f4] border-rose-300 shadow-[4px_4px_10px_#cbd2dc,-4px_-4px_10px_#ffffff]'
                    : 'bg-[#eef0f4] border-slate-300/80 shadow-[4px_4px_10px_#cbd2dc,-4px_-4px_10px_#ffffff]'
                }`}
              >
                <div className="flex items-center space-x-3 min-w-0">
                  <div className="w-9 h-9 rounded-xl bg-[#eef0f4] border border-slate-300/80 flex items-center justify-center text-blue-600 flex-shrink-0 shadow-[inset_2px_2px_4px_#cbd2dc]">
                    <FileSpreadsheet className="w-5 h-5" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center space-x-2 flex-wrap">
                      <p className="font-bold text-slate-800 truncate max-w-xs sm:max-w-md">{item.name}</p>
                      {item.name.toLowerCase().includes('consolidated') && (
                        <span className="px-2 py-0.5 rounded-md bg-amber-500/20 text-amber-700 text-[10px] font-bold border border-amber-300">
                          Pre-Consolidated File
                        </span>
                      )}
                    </div>
                    <p className="text-[10px] text-slate-500">
                      {(item.size / 1024).toFixed(1)} KB | Status: <span className="text-slate-900 font-bold">{item.status}</span>
                      {item.totalRows > 0 && ` | ${item.totalRows.toLocaleString()} rows`}
                    </p>
                  </div>
                </div>

                {/* Status Badges & Controls */}
                <div className="flex items-center space-x-2 flex-shrink-0 self-end sm:self-center">
                  {item.status === 'QUEUED' && (
                    <span className="px-2.5 py-1 rounded-lg bg-[#eef0f4] text-slate-700 text-[10px] font-bold border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc]">
                      QUEUED
                    </span>
                  )}

                  {item.status === 'INSPECTING' && (
                    <span className="px-2.5 py-1 rounded-lg bg-[#eef0f4] text-blue-700 text-[10px] font-bold border border-blue-300 flex items-center space-x-1 shadow-[inset_2px_2px_4px_#cbd2dc]">
                      <RefreshCw className="w-3 h-3 animate-spin text-blue-600" />
                      <span>INSPECTING</span>
                    </span>
                  )}

                  {item.status === 'INSPECTED' && (
                    <span className="px-2.5 py-1 rounded-lg bg-[#eef0f4] text-blue-700 text-[10px] font-bold border border-blue-300 flex items-center space-x-1 shadow-[inset_2px_2px_4px_#cbd2dc]">
                      <FileCode className="w-3 h-3 text-blue-600" />
                      <span>INSPECTED ({item.uploadResult?.mapped_target_count || 0} mapped)</span>
                    </span>
                  )}

                  {item.status === 'PROCESSING' && (
                    <span className="px-2.5 py-1 rounded-lg bg-[#eef0f4] text-emerald-700 text-[10px] font-bold border border-emerald-300 flex items-center space-x-1 shadow-[inset_2px_2px_4px_#cbd2dc]">
                      <RefreshCw className="w-3 h-3 animate-spin text-emerald-600" />
                      <span>PROCESSING</span>
                    </span>
                  )}

                  {item.status === 'COMPLETED' && (
                    <span className="px-2.5 py-1 rounded-lg bg-[#eef0f4] text-emerald-700 text-[10px] font-bold border border-emerald-300 flex items-center space-x-1 shadow-[inset_2px_2px_4px_#cbd2dc]">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      <span>INGESTED ({item.processedRows || item.totalRows} rows)</span>
                    </span>
                  )}

                  {item.status === 'FAILED' && (
                    <span className="px-2.5 py-1 rounded-lg bg-[#eef0f4] text-rose-700 text-[10px] font-bold border border-rose-300 flex items-center space-x-1 shadow-[inset_2px_2px_4px_#cbd2dc]">
                      <AlertCircle className="w-3.5 h-3.5 text-rose-600" />
                      <span>FAILED</span>
                    </span>
                  )}

                  {/* Actions per file */}
                  {item.status !== 'COMPLETED' && item.status !== 'PROCESSING' && (
                    <>
                      <button
                        onClick={() => inspectQueueFile(item)}
                        className="neumorph-button px-2.5 py-1 text-blue-600 text-[10px] font-bold flex items-center space-x-1"
                        title="Inspect Column Headers"
                      >
                        <FileCode className="w-3 h-3" />
                        <span>Inspect</span>
                      </button>
                      <button
                        onClick={() => processSingleFile(idx)}
                        className="neumorph-button-primary px-2.5 py-1 text-[10px] font-bold flex items-center space-x-1"
                        title="Process File Now"
                      >
                        <Play className="w-3 h-3 fill-white" />
                        <span>Run</span>
                      </button>
                    </>
                  )}

                  <button
                    onClick={() => removeFromQueue(item.id)}
                    disabled={isProcessingQueue}
                    className="neumorph-button p-1.5 text-slate-500 hover:text-rose-600"
                    title="Remove from Queue"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </Tilt3DCard>
      )}

      {/* Column Remapping Studio for Inspected File */}
      {selectedFileForRemap && selectedFileForRemap.uploadResult && (
        <Tilt3DCard className="p-6 space-y-5">
          <div className="flex justify-between items-center border-b border-slate-300/60 pb-3">
            <div className="flex items-center space-x-2">
              <ShieldCheck className="w-5 h-5 text-blue-600" />
              <div>
                <h3 className="text-sm font-bold text-slate-800">
                  Header Remapping Studio: {selectedFileForRemap.name}
                </h3>
                <p className="text-xs text-slate-600 font-medium">Verify or override target field mappings before running.</p>
              </div>
            </div>
            <button
              onClick={() => setSelectedFileForRemap(null)}
              className="neumorph-button px-3 py-1.5 text-xs text-slate-700 font-bold"
            >
              Close Studio
            </button>
          </div>

          {selectedFileForRemap.uploadResult.mapped_columns_preview && (
            <div className="space-y-3">
              <div className="flex justify-between items-center text-xs font-mono font-bold text-slate-700">
                <span>DETECTED RAW COLUMNS ({selectedFileForRemap.uploadResult.header_count})</span>
                <span className="text-blue-600">
                  {selectedFileForRemap.uploadResult.mapped_count} / {selectedFileForRemap.uploadResult.header_count} Mapped
                </span>
              </div>

              <div className="max-h-60 overflow-y-auto rounded-2xl border border-slate-300/80 bg-[#eef0f4] p-2 space-y-2 shadow-[inset_3px_3px_6px_#cbd2dc]">
                {selectedFileForRemap.uploadResult.mapped_columns_preview.map((colItem, idx) => {
                  const currentMappedField = columnOverrides[colItem.raw_header] || '';
                  return (
                    <div key={idx} className="p-2.5 flex items-center justify-between gap-3 text-xs font-mono bg-[#eef0f4] rounded-xl border border-white/80 shadow-[3px_3px_6px_#cbd2dc]">
                      <div className="flex items-center space-x-2 font-bold text-slate-900 max-w-[200px] truncate">
                        <Layers className="w-3.5 h-3.5 text-blue-600" />
                        <span title={colItem.raw_header}>{colItem.raw_header}</span>
                      </div>

                      <ArrowRight className="w-4 h-4 text-slate-400 flex-shrink-0" />

                      <CustomSelect
                        value={currentMappedField}
                        onChange={(val) => {
                          setColumnOverrides((prev) => ({
                            ...prev,
                            [colItem.raw_header]: val,
                          }));
                        }}
                        placeholder="-- Unmapped / Ignore --"
                        options={[
                          { label: '-- Unmapped / Ignore --', value: '' },
                          ...targetFieldsList.map((tf) => ({ label: tf, value: tf }))
                        ]}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </Tilt3DCard>
      )}
    </div>
  );
}
