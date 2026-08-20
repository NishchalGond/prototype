import React, { useEffect, useState } from 'react';
import { ArrowRight, ShieldCheck, Plus, Trash2, Tag, Search, Sparkles } from 'lucide-react';
import Tilt3DCard from './Tilt3DCard';

export default function ColumnMappingInspector() {
  const [mappingData, setMappingData] = useState(null);
  const [testHeader, setTestHeader] = useState('');
  const [matchedField, setMatchedField] = useState(null);
  const [searchField, setSearchField] = useState('');
  const [newAliasText, setNewAliasText] = useState({});
  const [isSavingAlias, setIsSavingAlias] = useState(false);

  useEffect(() => {
    fetchMapping();
  }, []);

  const fetchMapping = async () => {
    try {
      const res = await fetch('/api/column-mappings');
      if (res.ok) {
        const data = await res.json();
        setMappingData(data);
      }
    } catch (err) {
      console.error('Error loading column mappings:', err);
    }
  };

  const handleTestMatch = (query) => {
    setTestHeader(query);
    if (!query.trim() || !mappingData?.aliases) {
      setMatchedField(null);
      return;
    }

    const cleanQuery = query.trim().toUpperCase();
    for (const [targetField, aliasList] of Object.entries(mappingData.aliases)) {
      for (const alias of aliasList) {
        if (alias.toString().toUpperCase() === cleanQuery) {
          setMatchedField(targetField);
          return;
        }
      }
    }
    setMatchedField('UNMAPPED / REQUIRES ALIAS');
  };

  const handleAddAlias = async (targetField) => {
    const aliasVal = newAliasText[targetField]?.trim();
    if (!aliasVal) return;

    setIsSavingAlias(true);
    try {
      const res = await fetch('/api/column-mappings/alias', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_field: targetField, alias: aliasVal }),
      });
      if (res.ok) {
        const updatedData = await res.json();
        setMappingData(updatedData);
        setNewAliasText((prev) => ({ ...prev, [targetField]: '' }));
      }
    } catch (err) {
      console.error('Failed to add custom alias:', err);
    } finally {
      setIsSavingAlias(false);
    }
  };

  const handleRemoveAlias = async (targetField, aliasVal) => {
    try {
      const res = await fetch('/api/column-mappings/alias', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_field: targetField, alias: aliasVal }),
      });
      if (res.ok) {
        const updatedData = await res.json();
        setMappingData(updatedData);
      }
    } catch (err) {
      console.error('Failed to remove custom alias:', err);
    }
  };

  if (!mappingData) {
    return (
      <div className="p-12 text-center text-slate-500 font-mono text-xs space-y-2">
        <Sparkles className="w-6 h-6 animate-pulse text-blue-600 mx-auto" />
        <p>Loading Neumorphic 23-Field Standard Mapping Catalog...</p>
      </div>
    );
  }

  const targetFields = mappingData.target_fields || [];
  const aliases = mappingData.aliases || {};

  const filteredFields = targetFields.filter((field) =>
    field.toLowerCase().includes(searchField.toLowerCase()) ||
    (aliases[field] && aliases[field].some((a) => a.toLowerCase().includes(searchField.toLowerCase())))
  );

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Title Header */}
      <Tilt3DCard className="p-6 rounded-3xl">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <div className="flex items-center space-x-2">
              <span className="px-3 py-1 rounded-full bg-[#eef0f4] text-blue-600 font-mono text-[10px] font-black tracking-wider border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc,inset_-2px_-2px_4px_#ffffff]">
                MAPPING MATRIX V4
              </span>
            </div>
            <h2 className="text-2xl font-black text-slate-800 tracking-tight mt-2">23-Field Standard Mapping Catalog</h2>
            <p className="text-xs text-slate-600 mt-1 font-medium">
              Dynamic alias management engine. Add or remove raw header aliases permanently to standard database target fields.
            </p>
          </div>

          <div className="flex items-center space-x-3 bg-[#eef0f4] px-4 py-2.5 rounded-2xl border border-slate-300/80 font-mono text-xs shadow-[inset_3px_3px_6px_#cbd2dc,inset_-3px_-3px_6px_#ffffff]">
            <Tag className="w-4 h-4 text-emerald-600" />
            <span className="text-slate-600">Total Active Aliases:</span>
            <span className="text-slate-900 font-bold">{mappingData.alias_count?.toLocaleString()}</span>
          </div>
        </div>
      </Tilt3DCard>

      {/* Header Matcher Tester Tool */}
      <Tilt3DCard className="p-6 space-y-4">
        <div className="flex items-center space-x-2 text-xs font-bold text-slate-700 font-mono">
          <ShieldCheck className="w-4 h-4 text-blue-600" />
          <span>HEADER ALIAS MATCHER TESTER</span>
        </div>

        <div className="flex flex-col sm:flex-row gap-3">
          <input
            type="text"
            value={testHeader}
            onChange={(e) => handleTestMatch(e.target.value)}
            placeholder="Type raw header (e.g. FULL NAME, DAR UNIT_NO, REGION, MASTER DEVELOPER, PROPERTY TOWER)..."
            className="flex-1 neumorph-inset text-xs text-slate-800 placeholder-slate-400 rounded-2xl px-4 py-3 focus:outline-none font-mono"
          />
        </div>

        {testHeader && (
          <div className="p-4 rounded-2xl bg-[#eef0f4] border border-slate-300/80 text-xs font-mono flex items-center justify-between shadow-[inset_3px_3px_6px_#cbd2dc]">
            <span className="text-slate-600 font-medium">Raw Input Header: "<span className="text-slate-900 font-bold">{testHeader}</span>"</span>
            <div className="flex items-center space-x-2">
              <ArrowRight className="w-4 h-4 text-blue-600" />
              <span className={`font-bold px-3 py-1 rounded-xl text-xs ${matchedField && matchedField !== 'UNMAPPED / REQUIRES ALIAS' ? 'bg-emerald-100 text-emerald-800 border border-emerald-300' : 'bg-rose-100 text-rose-800 border border-rose-300'}`}>
                {matchedField}
              </span>
            </div>
          </div>
        )}
      </Tilt3DCard>

      {/* Mapping Cards Grid */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <h3 className="text-sm font-bold text-slate-800 flex items-center space-x-2 font-mono">
            <span>Target Fields & Known Aliases ({filteredFields.length})</span>
          </h3>
          <div className="relative">
            <Search className="w-4 h-4 text-blue-600 absolute left-3.5 top-3" />
            <input
              type="text"
              value={searchField}
              onChange={(e) => setSearchField(e.target.value)}
              placeholder="Search target fields or aliases..."
              className="neumorph-inset text-xs text-slate-800 placeholder-slate-400 rounded-2xl pl-10 pr-4 py-2.5 focus:outline-none font-medium w-64"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredFields.map((field) => {
            const aliasList = aliases[field] || [];
            return (
              <Tilt3DCard key={field} className="p-6 space-y-4 flex flex-col justify-between">
                <div className="space-y-3">
                  <div className="flex justify-between items-center border-b border-slate-300/60 pb-3">
                    <h4 className="text-xs font-black text-slate-900 font-mono tracking-wide">{field}</h4>
                    <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-[#eef0f4] text-blue-700 font-bold border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc]">
                      {aliasList.length} Aliases
                    </span>
                  </div>

                  <div className="bg-[#eef0f4] p-3.5 rounded-2xl border border-slate-300/80 max-h-48 overflow-y-auto font-mono text-[11px] space-y-1.5 divide-y divide-slate-300/40 shadow-[inset_3px_3px_6px_#cbd2dc]">
                    {aliasList.length > 0 ? (
                      aliasList.map((alias, idx) => (
                        <div key={idx} className="pt-1.5 flex items-center justify-between group text-slate-700 hover:text-slate-900">
                          <span className="truncate pr-2">• {alias}</span>
                          <button
                            onClick={() => handleRemoveAlias(field, alias)}
                            className="p-1 rounded-md text-slate-400 hover:text-rose-600 hover:bg-rose-100 transition-all opacity-70 group-hover:opacity-100 cursor-pointer"
                            title="Remove Alias"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ))
                    ) : (
                      <span className="text-slate-400 italic text-[10px]">Standard direct match</span>
                    )}
                  </div>
                </div>

                {/* Add Custom Alias Form */}
                <div className="flex items-center space-x-2 pt-2 border-t border-slate-300/60">
                  <input
                    type="text"
                    value={newAliasText[field] || ''}
                    onChange={(e) => setNewAliasText({ ...newAliasText, [field]: e.target.value })}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleAddAlias(field);
                    }}
                    placeholder="Add new custom alias..."
                    className="flex-1 neumorph-inset text-[11px] text-slate-800 placeholder-slate-400 px-3.5 py-2 rounded-xl focus:outline-none font-mono"
                  />
                  <button
                    onClick={() => handleAddAlias(field)}
                    disabled={isSavingAlias || !newAliasText[field]?.trim()}
                    className="neumorph-button-primary px-3.5 py-2 text-xs font-bold flex items-center space-x-1"
                    title="Save Alias Permanently"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Add</span>
                  </button>
                </div>
              </Tilt3DCard>
            );
          })}
        </div>
      </div>
    </div>
  );
}
