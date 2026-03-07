/**
 * ThinkingIndicator — Gustave Code
 * Animation "Le modele reflechit..." avec temps ecoule et outils actifs.
 * Theme Clair Obscure — points dores pulsants.
 */

import React, { useState, useEffect } from 'react';

const ThinkingIndicator = ({ activeTools }) => {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setElapsed(prev => prev + 1);
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  const formatTime = (seconds) => {
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
  };

  const hasActiveTools = activeTools && activeTools.some(t => t.status === 'running');

  return (
    <div className="bg-assistant-bubble rounded-2xl rounded-bl-md px-4 py-3 max-w-[80%] inline-block border border-border-color/20">
      <div className="flex items-center gap-3">
        {/* Dots animation — or patiné */}
        <div className="flex items-center gap-1">
          <div className="typing-dot w-2 h-2 bg-accent rounded-full" />
          <div className="typing-dot w-2 h-2 bg-accent rounded-full" />
          <div className="typing-dot w-2 h-2 bg-accent rounded-full" />
        </div>

        {/* Texte */}
        <span className="text-sm text-text-secondary">
          {hasActiveTools
            ? 'Utilisation d\'un outil...'
            : 'Reflexion en cours...'
          }
        </span>

        {/* Temps ecoule */}
        <span className="text-xs text-accent-dim/60 font-mono">
          {formatTime(elapsed)}
        </span>
      </div>

      {/* Outils en cours */}
      {hasActiveTools && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {activeTools
            .filter(t => t.status === 'running')
            .map((tool, idx) => (
              <span
                key={idx}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-accent/15 text-accent animate-pulse"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="animate-spin"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                {tool.name?.replace(/_tool$/, '').replace(/_/g, ' ')}
              </span>
            ))}
        </div>
      )}
    </div>
  );
};

export default ThinkingIndicator;
