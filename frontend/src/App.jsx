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

  const handleSend = useCallback((text) => {
    send(text, selectedProfile);
  }, [send, selectedProfile]);

  // Bloquer le changement de profil pendant le streaming
  const handleProfileChange = useCallback((profile) => {
    if (isStreaming) return;
    setSelectedProfile(profile);
  }, [isStreaming]);

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

          <ProfileSelector
            selectedProfile={selectedProfile}
            onSelectProfile={handleProfileChange}
            disabled={isStreaming}
          />
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
