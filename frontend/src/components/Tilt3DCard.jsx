import React from 'react';

export default function Tilt3DCard({ children, className = '' }) {
  return (
    <div className={`neumorph-card-interactive ${className}`}>
      {children}
    </div>
  );
}
