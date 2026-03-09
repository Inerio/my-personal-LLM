/**
 * ChatWindow — Gustave Code
 * Zone d'affichage des messages avec auto-scroll et écran d'accueil.
 * Thème Clair Obscure — écran d'accueil style livre ancien doré.
 */

import React, { useEffect, useRef } from 'react';
import MessageBubble from './MessageBubble';

const ChatWindow = ({ messages, isStreaming, activeTools, error }) => {
  const messagesEndRef = useRef(null);

  // Auto-scroll vers le bas
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isStreaming, activeTools]);

  // Écran d'accueil si pas de messages
  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-center max-w-lg">
          {/* Logo G doré — style feuille d'or */}
          <div
            className="text-7xl mb-6 font-bold text-accent select-none font-display"
            style={{ textShadow: '0 0 40px rgba(201, 168, 76, 0.15)' }}
          >
            G
          </div>

          {/* Ligne décorative dorée */}
          <div className="gold-line w-32 mx-auto mb-4" />

          <h2 className="text-2xl font-bold mb-3 text-text-primary font-display tracking-wide">
            Gustave Code
          </h2>
          <p className="text-text-secondary mb-8 leading-relaxed text-sm">
            Assistant IA personnel local. Propulsé par des modèles open-source de pointe.
            Vos données restent sur votre machine.
          </p>

          <div className="grid grid-cols-2 gap-3 text-left">
            <SuggestionCard
              title="Questions complexes"
              text="Utilisez le profil Qualité pour les analyses approfondies"
            />
            <SuggestionCard
              title="Recherche web"
              text="Je peux chercher des infos actualisées sur internet"
            />
            <SuggestionCard
              title="Code"
              text="Je peux écrire et expliquer du code dans tous les langages"
            />
            <SuggestionCard
              title="Calculs"
              text="Mathématiques, conversions, statistiques..."
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

      {/* Erreur globale — masquée si déjà affichée dans une bulle message */}
      {error && !(messages.length > 0 && messages[messages.length - 1]?.isError) && (
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
 * Carte de suggestion — bordure dorée subtile.
 */
const SuggestionCard = ({ title, text }) => (
  <div className="bg-bg-secondary/50 border border-border-color/40 rounded-lg p-3 hover:border-accent/30 hover:bg-bg-secondary/80 transition-all duration-200 cursor-default group">
    <span className="text-sm font-semibold text-text-primary group-hover:text-accent transition-colors">{title}</span>
    <p className="text-xs text-text-secondary mt-1">{text}</p>
  </div>
);

export default ChatWindow;
