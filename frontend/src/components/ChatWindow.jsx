/**
 * ChatWindow — Gustave Code
 * Zone d'affichage des messages avec auto-scroll et ecran d'accueil.
 * Theme Clair Obscure — ecran d'accueil style livre ancien dore.
 */

import React, { useEffect, useRef } from 'react';
import MessageBubble from './MessageBubble';
import ThinkingIndicator from './ThinkingIndicator';

const ChatWindow = ({ messages, isStreaming, activeTools, error }) => {
  const messagesEndRef = useRef(null);

  // Auto-scroll vers le bas
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isStreaming, activeTools]);

  // Ecran d'accueil si pas de messages
  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-center max-w-lg">
          {/* Logo G dore — style feuille d'or */}
          <div
            className="text-7xl mb-6 font-bold text-accent select-none font-display"
            style={{ textShadow: '0 0 40px rgba(201, 168, 76, 0.15)' }}
          >
            G
          </div>

          {/* Ligne decorative doree */}
          <div className="gold-line w-32 mx-auto mb-4" />

          <h2 className="text-2xl font-bold mb-3 text-text-primary font-display tracking-wide">
            Gustave Code
          </h2>
          <p className="text-text-secondary mb-8 leading-relaxed text-sm">
            Assistant IA personnel local. Propulse par des modeles open-source de pointe.
            Vos donnees restent sur votre machine.
          </p>

          <div className="grid grid-cols-2 gap-3 text-left">
            <SuggestionCard
              title="Questions complexes"
              text="Utilisez le profil LLaMA pour les analyses approfondies"
            />
            <SuggestionCard
              title="Recherche web"
              text="Je peux chercher des infos actualisees sur internet"
            />
            <SuggestionCard
              title="Code"
              text="Je peux ecrire et expliquer du code dans tous les langages"
            />
            <SuggestionCard
              title="Calculs"
              text="Mathematiques, conversions, statistiques..."
            />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className="flex-1 overflow-y-auto py-4"
      style={{ scrollBehavior: 'smooth' }}
    >
      {/* Messages */}
      {messages.map((message, index) => (
        <MessageBubble key={message.id || index} message={message} />
      ))}

      {/* Indicateur de reflexion si streaming actif et pas encore de contenu */}
      {isStreaming && messages.length > 0 && (
        (() => {
          const lastMsg = messages[messages.length - 1];
          if (lastMsg?.role === 'assistant' && lastMsg?.isStreaming && !lastMsg?.content) {
            return (
              <div className="px-4 mb-4">
                <ThinkingIndicator activeTools={activeTools} />
              </div>
            );
          }
          return null;
        })()
      )}

      {/* Erreur globale */}
      {error && (
        <div className="px-4 mb-4">
          <div className="bg-red-950/20 border border-red-900/30 rounded-lg p-3 text-sm text-red-300">
            <span className="font-semibold">Erreur:</span> {error}
          </div>
        </div>
      )}

      <div ref={messagesEndRef} />
    </div>
  );
};


/**
 * Carte de suggestion — bordure doree subtile.
 */
const SuggestionCard = ({ title, text }) => (
  <div className="bg-bg-secondary/50 border border-border-color/40 rounded-lg p-3 hover:border-accent/30 hover:bg-bg-secondary/80 transition-all duration-200 cursor-default group">
    <span className="text-sm font-semibold text-text-primary group-hover:text-accent transition-colors">{title}</span>
    <p className="text-xs text-text-secondary mt-1">{text}</p>
  </div>
);

export default ChatWindow;
