import React from 'react';

export default function DataLinkLogo({ className = "w-6 h-6", glow = true }) {
  return (
    <div className={`relative flex items-center justify-center ${className}`}>
      {glow && (
        <div className="absolute inset-0 bg-blue-500/25 rounded-xl blur-xs transform scale-110 pointer-events-none" />
      )}
      <svg
        viewBox="0 0 48 48"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="w-full h-full relative z-10 drop-shadow-sm transition-transform duration-300 hover:scale-110"
      >
        <defs>
          <linearGradient id="datalinkGradient1" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#2563EB" />
            <stop offset="50%" stopColor="#4F46E5" />
            <stop offset="100%" stopColor="#06B6D4" />
          </linearGradient>
          <linearGradient id="datalinkGradient2" x1="100%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#60A5FA" />
            <stop offset="100%" stopColor="#3B82F6" />
          </linearGradient>
          <linearGradient id="coreGlow" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#38BDF8" />
            <stop offset="100%" stopColor="#818CF8" />
          </linearGradient>
        </defs>

        {/* Outer Hexagonal Shield */}
        <path
          d="M24 4L42 14.5V33.5L24 44L6 33.5V14.5L24 4Z"
          stroke="url(#datalinkGradient1)"
          strokeWidth="3.2"
          strokeLinejoin="round"
        />

        {/* Inner Interlocking Data Prism */}
        <path
          d="M24 13L35 19.5V31L24 37.5L13 31V19.5L24 13Z"
          fill="url(#datalinkGradient1)"
          fillOpacity="0.2"
          stroke="url(#datalinkGradient2)"
          strokeWidth="2"
          strokeLinejoin="round"
        />

        {/* Central Pipeline Vectors */}
        <path
          d="M24 13V25M24 25L13 31M24 25L35 31"
          stroke="url(#coreGlow)"
          strokeWidth="2.5"
          strokeLinecap="round"
        />

        {/* Glowing Quantum Core */}
        <circle cx="24" cy="25" r="4" fill="#FFFFFF" />
        <circle cx="24" cy="25" r="2" fill="#2563EB" />
        
        {/* Interconnected Network Nodes */}
        <circle cx="24" cy="4" r="2.5" fill="#3B82F6" />
        <circle cx="42" cy="14.5" r="2.5" fill="#4F46E5" />
        <circle cx="42" cy="33.5" r="2.5" fill="#06B6D4" />
        <circle cx="24" cy="44" r="2.5" fill="#3B82F6" />
        <circle cx="6" cy="33.5" r="2.5" fill="#06B6D4" />
        <circle cx="6" cy="14.5" r="2.5" fill="#4F46E5" />
      </svg>
    </div>
  );
}
