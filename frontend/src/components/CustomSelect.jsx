import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Check } from 'lucide-react';

export default function CustomSelect({ value, onChange, options = [], placeholder = 'Select Option', className = '' }) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const selectedOption = options.find((opt) => 
    typeof opt === 'object' ? opt.value === value : opt === value
  );

  const displayLabel = selectedOption
    ? (typeof selectedOption === 'object' ? selectedOption.label : selectedOption)
    : placeholder;

  return (
    <div className={`relative inline-block text-left ${className}`} ref={dropdownRef}>
      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={`w-full neumorph-inset text-xs font-semibold text-slate-800 rounded-2xl px-4 py-2.5 flex items-center justify-between transition-all cursor-pointer ${
          isOpen ? 'ring-2 ring-blue-500/40 border-blue-400' : ''
        }`}
      >
        <span className="truncate mr-2">{displayLabel}</span>
        <ChevronDown className={`w-4 h-4 text-blue-600 transition-transform duration-200 ${isOpen ? 'transform rotate-180' : ''}`} />
      </button>

      {/* Floating Neumorphic Popover Card */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-full min-w-[200px] z-50 bg-[#eef0f4] rounded-2xl p-2 border border-white/80 shadow-[9px_9px_18px_#cbd2dc,-9px_-9px_18px_#ffffff] animate-in fade-in zoom-in-95 duration-100 max-h-60 overflow-y-auto">
          <div className="space-y-1">
            {options.map((opt, idx) => {
              const val = typeof opt === 'object' ? opt.value : opt;
              const label = typeof opt === 'object' ? opt.label : opt;
              const isSelected = val === value;

              return (
                <button
                  key={idx}
                  type="button"
                  onClick={() => {
                    onChange(val);
                    setIsOpen(false);
                  }}
                  className={`w-full text-left px-3.5 py-2 rounded-xl text-xs font-medium transition-all flex items-center justify-between cursor-pointer ${
                    isSelected
                      ? 'bg-blue-600 text-white font-bold shadow-[2px_2px_5px_#cbd2dc]'
                      : 'text-slate-700 hover:bg-[#e2e6ed] hover:text-slate-900'
                  }`}
                >
                  <span className="truncate">{label}</span>
                  {isSelected && <Check className="w-3.5 h-3.5 ml-2 text-white flex-shrink-0" />}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
