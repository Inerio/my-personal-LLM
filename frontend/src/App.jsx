/**
 * App — Gustave Code
 * Layout principal : Sidebar + Chat Window
 */

import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import ChatWindow from './components/ChatWindow';
import InputBar from './components/InputBar';
import ProfileSelector from './components/ProfileSelector';
import useChat from './hooks/useChat';
import { getConversations, getConversation, getHealth } from './api/client';

function App() {
  const [conversations, setConversations] = useState([]);
  const [selectedProfile, setSelectedProfile] = useState('fast');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [health, setHealth] = useState(null);

  const {
    messages,
    isStreaming,
    currentConversationId,
    activeTools,
    error,
    streamingConvId,
    send,
    cancelStream,
    loadConversation,
    newConversation,
  } = useChat();

  // Charger les conversations au démarrage
  useEffect(() => {
    loadConversations();
    checkHealth();
  }, []);

  // Recharger la sidebar :
  // - dès qu'un conversation_id arrive (nouvelle conv visible immédiatement)
  // - quand le stream se termine (titre mis à jour par le backend)
  // - quand streamingConvId change (nouvelle conversation créée en arrière-plan)
  useEffect(() => {
    loadConversations();
  }, [currentConversationId, isStreaming, streamingConvId]);

  const loadConversations = async () => {
    try {
      const data = await getConversations();
      setConversations(data);
    } catch (err) {
      console.error('Erreur chargement conversations:', err);
    }
  };

  const checkHealth = async () => {
    try {
      const data = await getHealth();
      setHealth(data);
    } catch (err) {
      setHealth({ status: 'error', ollama_connected: false });
    }
  };

  const handleSelectConversation = useCallback(async (conversationId) => {
    // Déjà sur cette conversation → rien à faire
    if (conversationId === currentConversationId) return;

    // Navigation libre — le stream continue en arrière-plan
    try {
      const data = await getConversation(conversationId);
      loadConversation(conversationId, data.messages || []);
    } catch (err) {
      console.error('Erreur chargement conversation:', err);
    }
  }, [loadConversation, currentConversationId]);

  const handleNewConversation = useCallback(() => {
    // Navigation libre — le stream continue en arrière-plan
    newConversation();
  }, [newConversation]);

  const handlePurgeAll = useCallback(async () => {
    // Popup de confirmation avant suppression totale
    const confirmed = window.confirm(
      'Supprimer toutes les conversations et la mémoire ?\n\n' +
      'Cette action est irréversible. Toutes les conversations, ' +
      'messages et la mémoire long-terme seront effacés.'
    );
    if (!confirmed) return;

    // 1. Annuler tout stream en cours
    if (isStreaming) {
      cancelStream();
    }

    // 2. Supprimer toutes les conversations + purger ChromaDB
    try {
      const { deleteAllConversations } = await import('./api/client');
      const result = await deleteAllConversations();
      console.log('[Gustave] Tout supprimé:', result);
    } catch (err) {
      console.error('[Gustave] Erreur suppression totale:', err);
    }

    // 3. Reset l'interface
    newConversation();
    setConversations([]);
  }, [isStreaming, cancelStream, newConversation]);

  const handleSend = useCallback((text) => {
    send(text, selectedProfile);
  }, [send, selectedProfile]);

  // Bloquer le changement de profil pendant le streaming
  const handleProfileChange = useCallback((profile) => {
    if (isStreaming) return;
    setSelectedProfile(profile);
  }, [isStreaming]);

  const handleRenameConversation = useCallback(async (conversationId, newTitle) => {
    try {
      const { renameConversation } = await import('./api/client');
      await renameConversation(conversationId, newTitle);
      loadConversations();
    } catch (err) {
      console.error('Erreur renommage:', err);
    }
  }, []);

  const handleDeleteConversation = useCallback(async (conversationId) => {
    try {
      const { deleteConversation } = await import('./api/client');
      await deleteConversation(conversationId);

      // Si on supprime la conversation en stream, annuler le stream
      if (streamingConvId === conversationId) {
        cancelStream();
      }

      if (currentConversationId === conversationId) {
        newConversation();
      }

      loadConversations();
    } catch (err) {
      console.error('Erreur suppression:', err);
    }
  }, [currentConversationId, streamingConvId, newConversation, cancelStream]);

  return (
    <div className="flex h-screen bg-bg-primary text-text-primary overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        isOpen={sidebarOpen}
        isStreaming={isStreaming}
        streamingConvId={streamingConvId}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onDeleteConversation={handleDeleteConversation}
        onRenameConversation={handleRenameConversation}
        health={health}
      />

      {/* Zone principale */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Header avec profil */}
        <header className="flex items-center justify-between px-4 py-3 border-b border-border-color bg-bg-secondary">
          <div className="flex items-center gap-3">
            {!sidebarOpen && (
              <button
                onClick={() => setSidebarOpen(true)}
                className="p-2 rounded-lg hover:bg-bg-tertiary transition-colors"
                title="Ouvrir le menu"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
              </button>
            )}
            <h1 className="text-lg font-semibold font-display tracking-wide text-accent">Gustave Code</h1>
          </div>

          <div className="flex items-center gap-2">
            {/* Bouton tout effacer (conversations + mémoire) */}
            <button
              onClick={handlePurgeAll}
              disabled={conversations.length === 0}
              className={`
                p-2 rounded-lg border border-border-color bg-bg-tertiary/50
                transition-all duration-150
                ${conversations.length === 0
                  ? 'opacity-25 cursor-not-allowed'
                  : 'hover:bg-bg-tertiary hover:border-red-500/30 cursor-pointer'
                }
              `}
              title="Tout effacer (conversations + mémoire)"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-text-secondary">
                <path d="m7 21-4.3-4.3c-1-1-1-2.5 0-3.4l9.6-9.6c1-1 2.5-1 3.4 0l5.6 5.6c1 1 1 2.5 0 3.4L13 21"/>
                <path d="M22 21H7"/>
                <path d="m5 11 9 9"/>
              </svg>
            </button>

            <ProfileSelector
              selectedProfile={selectedProfile}
              onSelectProfile={handleProfileChange}
              disabled={isStreaming}
            />
          </div>
        </header>

        {/* Messages */}
        <ChatWindow
          messages={messages}
          isStreaming={isStreaming}
          activeTools={activeTools}
          error={error}
        />

        {/* Barre de saisie */}
        <InputBar
          onSend={handleSend}
          isStreaming={isStreaming}
          onCancel={cancelStream}
          selectedProfile={selectedProfile}
          streamingElsewhere={isStreaming && currentConversationId !== streamingConvId}
        />
      </div>
    </div>
  );
}

export default App;
