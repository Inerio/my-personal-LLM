/**
 * InputBar — Gustave Code
 * Barre de saisie avec envoi, annulation et raccourcis clavier.
 * Thème Clair Obscure — input style encrier doré.
 */

import React, { useState, useRef, useEffect } from 'react';

const InputBar = ({ onSend, isStreaming, onCancel, selectedProfile, streamingElsewhere = false }) => {
  const [input, setInput] = useState('');
  const textareaRef = useRef(null);

  // Focus auto au chargement
  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  // Re-focus après fin de streaming
  useEffect(() => {
    if (!isStreaming) {
      textareaRef.current?.focus();
    }
  }, [isStreaming]);

  // Auto-resize du textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
    }
  }, [input]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || isStreaming) return;
    onSend(text);
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const profileLabel = {
    fast: 'Rapide',
    llama: 'Qualité',
    mixtral: 'Expert',
  };

  return (
    <div className="border-t border-border-color bg-bg-secondary p-4">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-end gap-2 bg-bg-tertiary rounded-2xl border border-border-color gold-glow transition-all duration-200 p-2">
          {/* Textarea */}
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              isStreaming
                ? (streamingElsewhere
                  ? 'Réponse en cours dans une autre conversation...'
                  : 'Réponse en cours...')
                : 'Écrivez votre message... (Enter pour envoyer)'
            }
            disabled={isStreaming}
            rows={1}
            className="
              flex-1 bg-transparent text-text-primary placeholder-text-secondary/40
              resize-none outline-none text-sm leading-relaxed px-2 py-1.5
              disabled:opacity-40
            "
            style={{ maxHeight: '200px' }}
          />

          {/* Boutons */}
          <div className="flex items-center gap-1 flex-shrink-0">
            {isStreaming ? (
              <button
                onClick={onCancel}
                className="
                  p-2.5 rounded-xl bg-red-900/25 text-red-400
                  hover:bg-red-900/40 transition-colors
                "
                title="Annuler"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2" fill="currentColor"/>
                </svg>
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!input.trim()}
                className={`
                  p-2.5 rounded-xl transition-all duration-200
                  ${input.trim()
                    ? 'bg-accent text-bg-primary hover:bg-accent-hover shadow-lg shadow-accent/15'
                    : 'bg-bg-primary/50 text-text-secondary/20 cursor-not-allowed'
                  }
                `}
                title="Envoyer (Enter)"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22,2 15,22 11,13 2,9"/>
                </svg>
              </button>
            )}
          </div>
        </div>

        {/* Info sous la barre */}
        <div className="flex items-center justify-between mt-2 px-2">
          <p className="text-xs text-text-secondary/30">
            Shift+Enter pour retour à la ligne
          </p>
          <p className="text-xs text-text-secondary/30">
            Profil actif: {profileLabel[selectedProfile] || selectedProfile}
          </p>
        </div>
      </div>
    </div>
  );
};

export default InputBar;
