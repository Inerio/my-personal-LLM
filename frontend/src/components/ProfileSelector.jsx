/**
 * ProfileSelector — Gustave Code
 * Selecteur de profil de qualite (3 modeles non censures).
 * Theme Clair Obscure — tons or/ambre/bronze.
 */

import React, { useState } from 'react';

const PROFILES = [
  {
    id: 'fast',
    name: 'Rapide',
    description: 'Qwen 2.5 14B Abliterated',
    detail: 'Reponses rapides, usage quotidien. Modele non censure, sans filtre.',
    tag: 'LIBRE',
    borderColor: 'border-amber-500/40',
    textColor: 'text-amber-400',
  },
  {
    id: 'llama',
    name: 'LLaMA 3.3',
    description: 'LLaMA 3.3 70B Abliterated',
    detail: 'Multilingue, 128K tokens de contexte. Performances proches du 405B, non censure.',
    tag: 'LIBRE',
    borderColor: 'border-orange-700/40',
    textColor: 'text-orange-300',
  },
  {
    id: 'mixtral',
    name: 'Dolphin Mixtral',
    description: 'Dolphin Mixtral 8x22B (Eric Hartford)',
    detail: 'Architecture MoE, 141B parametres. Tres lent, gourmand en RAM. Non censure.',
    tag: 'LIBRE',
    borderColor: 'border-red-900/40',
    textColor: 'text-red-400',
  },
];

const ProfileSelector = ({ selectedProfile, onSelectProfile, disabled = false }) => {
  const [isOpen, setIsOpen] = useState(false);
  const selected = PROFILES.find(p => p.id === selectedProfile) || PROFILES[0];

  return (
    <div className="relative">
      {/* Bouton principal */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`
          flex items-center gap-2 px-3 py-2 rounded-lg
          border ${selected.borderColor} bg-bg-tertiary/50
          transition-all duration-150 text-sm font-medium
          hover:bg-bg-tertiary cursor-pointer
        `}
      >
        <span className={selected.textColor}>{selected.name}</span>
        <svg
          xmlns="http://www.w3.org/2000/svg" width="14" height="14"
          viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
          className={`text-text-secondary transition-transform ${isOpen ? 'rotate-180' : ''}`}
        >
          <polyline points="6,9 12,15 18,9"/>
        </svg>
      </button>

      {/* Dropdown */}
      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />

          {/* Menu */}
          <div className="absolute right-0 top-full mt-2 z-50 w-96 max-h-[70vh] overflow-y-auto rounded-xl bg-bg-secondary border border-border-color shadow-2xl shadow-black/50">
            <div className="p-2">
              <p className="px-3 py-2 text-xs font-semibold text-text-secondary uppercase tracking-wider font-display">
                Modele IA
                {disabled && <span className="ml-2 normal-case tracking-normal text-text-secondary/50">(selection verrouillee)</span>}
              </p>
              <div className="gold-line mb-2" />
              {PROFILES.map(profile => (
                <button
                  key={profile.id}
                  onClick={() => {
                    if (!disabled) {
                      onSelectProfile(profile.id);
                      setIsOpen(false);
                    }
                  }}
                  className={`
                    w-full text-left px-3 py-3 rounded-lg mb-1
                    transition-all duration-150
                    ${disabled && profile.id !== selectedProfile
                      ? 'opacity-40 cursor-not-allowed border border-transparent'
                      : profile.id === selectedProfile
                        ? `bg-bg-tertiary border ${profile.borderColor}`
                        : 'hover:bg-bg-tertiary/50 border border-transparent cursor-pointer'
                    }
                  `}
                >
                  <div className="flex items-center gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`font-semibold text-sm ${profile.textColor}`}>
                          {profile.name}
                        </span>
                        {profile.tag && (
                          <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-accent/15 text-accent-dim tracking-wider">
                            {profile.tag}
                          </span>
                        )}
                        {profile.id === selectedProfile && (
                          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className="text-accent"><polyline points="20,6 9,17 4,12"/></svg>
                        )}
                      </div>
                      <p className="text-xs text-text-secondary mt-0.5">
                        {profile.description}
                      </p>
                      <p className="text-xs text-text-secondary/60 mt-0.5">
                        {profile.detail}
                      </p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default ProfileSelector;
