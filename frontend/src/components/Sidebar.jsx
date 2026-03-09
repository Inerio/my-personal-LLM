/**
 * Sidebar — Gustave Code
 * Liste des conversations + nouveau chat + statut système.
 * Thème Clair Obscure — sidebar style panneau de livre ancien.
 */

import React, { useState, useRef, useEffect } from 'react';

const Sidebar = ({
  conversations,
  currentConversationId,
  isOpen,
  isStreaming = false,
  streamingConvId = null,
  onToggle,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onRenameConversation,
  health,
}) => {
  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const editInputRef = useRef(null);

  // Focus l'input dès qu'on passe en mode édition
  useEffect(() => {
    if (editingId && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editingId]);

  if (!isOpen) return null;

  const startEditing = (conv, e) => {
    e.stopPropagation();
    setEditingId(conv.id);
    setEditTitle(conv.title);
  };

  const confirmEdit = () => {
    const trimmed = editTitle.trim();
    if (trimmed && trimmed !== conversations.find(c => c.id === editingId)?.title) {
      onRenameConversation(editingId, trimmed);
    }
    setEditingId(null);
  };

  const cancelEdit = () => {
    setEditingId(null);
  };

  const handleEditKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      confirmEdit();
    } else if (e.key === 'Escape') {
      cancelEdit();
    }
  };

  // Grouper les conversations par date
  const groupByDate = (convs) => {
    const groups = { today: [], yesterday: [], week: [], older: [] };
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1);
    const weekAgo = new Date(today); weekAgo.setDate(today.getDate() - 7);

    convs.forEach(conv => {
      const date = new Date(conv.created_at);
      if (date >= today) groups.today.push(conv);
      else if (date >= yesterday) groups.yesterday.push(conv);
      else if (date >= weekAgo) groups.week.push(conv);
      else groups.older.push(conv);
    });

    return groups;
  };

  const groups = groupByDate(conversations);

  const renderGroup = (title, convs) => {
    if (convs.length === 0) return null;
    return (
      <div key={title} className="mb-4">
        <h3 className="px-3 py-1 text-xs font-semibold text-accent-dim/80 uppercase tracking-wider">
          {title}
        </h3>
        {convs.map(conv => (
          <div
            key={conv.id}
            onClick={() => editingId !== conv.id && onSelectConversation(conv.id)}
            className={`
              w-full text-left px-3 py-2.5 rounded-lg mx-1 mb-0.5
              text-sm transition-all duration-150 group cursor-pointer
              flex items-center justify-between
              ${conv.id === currentConversationId
                ? 'bg-bg-tertiary text-text-primary border-l-2 border-accent/50'
                : 'text-text-secondary hover:bg-bg-tertiary/50 hover:text-text-primary border-l-2 border-transparent'
              }
            `}
          >
            {/* Titre ou input d'édition */}
            {editingId === conv.id ? (
              <input
                ref={editInputRef}
                type="text"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                onKeyDown={handleEditKeyDown}
                onBlur={confirmEdit}
                className="flex-1 bg-bg-primary/80 text-text-primary text-sm px-2 py-0.5 rounded border border-accent/40 outline-none focus:border-accent"
                onClick={(e) => e.stopPropagation()}
              />
            ) : (
              <span className="truncate flex-1 flex items-center gap-2">
                {conv.id === streamingConvId && (
                  <span className="flex-shrink-0 w-2 h-2 rounded-full bg-accent animate-pulse" title="Réponse en cours..." />
                )}
                {conv.title}
              </span>
            )}

            {/* Boutons d'action (visibles au hover) */}
            {editingId !== conv.id && (
              <div className="opacity-0 group-hover:opacity-100 flex items-center gap-0.5 flex-shrink-0 transition-all">
                {/* Bouton éditer */}
                <button
                  onClick={(e) => startEditing(conv, e)}
                  className="p-1 hover:text-accent transition-colors"
                  title="Renommer"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                </button>
                {/* Bouton supprimer */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteConversation(conv.id);
                  }}
                  className="p-1 hover:text-red-400 transition-colors"
                  title="Supprimer"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3,6 5,6 21,6"/><path d="M19,6v14a2,2,0,0,1-2,2H7a2,2,0,0,1-2-2V6m3,0V4a2,2,0,0,1,2-2h4a2,2,0,0,1,2,2v2"/></svg>
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    );
  };

  return (
    <aside className="w-72 flex flex-col bg-bg-secondary border-r border-border-color h-full flex-shrink-0">
      {/* Header sidebar */}
      <div className="p-3 border-b border-border-color">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-semibold text-text-secondary font-display tracking-wide">Conversations</span>
          <button
            onClick={onToggle}
            className="p-1.5 rounded-lg hover:bg-bg-tertiary transition-colors text-text-secondary hover:text-accent"
            title="Fermer le menu"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="9" y1="3" x2="9" y2="21"/></svg>
          </button>
        </div>

        <button
          onClick={onNewConversation}
          className="
            w-full flex items-center gap-2 px-3 py-2.5 rounded-lg
            border border-border-color hover:border-accent/40
            text-sm text-text-primary hover:text-accent
            transition-all duration-200 hover:bg-bg-tertiary/30
          "
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          Nouveau chat
        </button>
      </div>

      {/* Liste des conversations */}
      <div className="flex-1 overflow-y-auto py-2 px-1">
        {conversations.length === 0 ? (
          <div className="px-4 py-8 text-center text-text-secondary text-sm">
            <p className="mb-1">Aucune conversation</p>
            <p className="text-xs opacity-70">Commencez par envoyer un message !</p>
          </div>
        ) : (
          <>
            {renderGroup("Aujourd'hui", groups.today)}
            {renderGroup("Hier", groups.yesterday)}
            {renderGroup("Cette semaine", groups.week)}
            {renderGroup("Plus ancien", groups.older)}
          </>
        )}
      </div>

      {/* Footer — Statut système */}
      <div className="p-3 border-t border-border-color">
        <div className="flex items-center gap-2 text-xs text-text-secondary">
          <div className={`w-2 h-2 rounded-full ${
            health?.ollama_connected ? 'bg-amber-500' :
            health?.status === 'error' ? 'bg-red-800' : 'bg-amber-800'
          }`} />
          <span>
            {health?.ollama_connected ? 'Ollama connecté' :
             health?.status === 'error' ? 'Backend déconnecté' : 'Ollama non disponible'}
          </span>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
