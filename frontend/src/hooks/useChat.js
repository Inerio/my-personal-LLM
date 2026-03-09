/**
 * Hook useChat — Gustave Code
 * Gestion complète du state de chat avec streaming SSE.
 *
 * Architecture "background streaming" :
 * - Le stream continue en arrière-plan quand l'utilisateur navigue vers
 *   une autre conversation ou crée un nouveau chat.
 * - Les données du stream sont accumulées dans des refs (toujours à jour).
 * - L'état affiché (messages, activeTools) n'est mis à jour que si
 *   l'utilisateur regarde la conversation en cours de streaming.
 * - Quand l'utilisateur revient sur la conversation en stream, on restaure
 *   depuis les refs au lieu de charger depuis la BDD.
 * - isStreaming est un flag GLOBAL : tant qu'un stream tourne, l'envoi
 *   est bloqué partout.
 */

import { useState, useCallback, useRef } from 'react';
import { sendMessage, savePartialResponse } from '../api/client';

const useChat = () => {
  // ─── State affiché ────────────────────────────────────────
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [activeTools, setActiveTools] = useState([]);
  const [streamMetadata, setStreamMetadata] = useState(null);
  const [error, setError] = useState(null);
  const [streamingConvId, setStreamingConvId] = useState(null);

  // ─── Refs pour le streaming en arrière-plan ───────────────
  const cancelStreamRef = useRef(null);
  const streamStartTimeRef = useRef(null);
  const streamConvIdRef = useRef(null);       // quelle conversation est en stream
  const streamMsgsRef = useRef([]);           // messages accumulés du stream
  const streamToolsRef = useRef([]);          // outils actifs du stream
  const streamProfileRef = useRef(null);      // profil utilisé pour le stream en cours
  const currentConvIdRef = useRef(null);      // miroir ref de currentConversationId

  // ─── Helpers ──────────────────────────────────────────────

  /**
   * L'utilisateur regarde-t-il la conversation en stream ?
   */
  const isViewingStream = () =>
    currentConvIdRef.current != null &&
    currentConvIdRef.current === streamConvIdRef.current;

  /**
   * Met à jour les messages du stream.
   * → ref toujours, state affiché seulement si on regarde le stream.
   */
  const updateStreamMsgs = useCallback((updater) => {
    streamMsgsRef.current = updater(streamMsgsRef.current);
    if (isViewingStream()) {
      setMessages(streamMsgsRef.current);
    }
  }, []);

  /**
   * Met à jour les outils du stream.
   * → ref toujours, state affiché seulement si on regarde le stream.
   */
  const updateStreamTools = useCallback((updater) => {
    streamToolsRef.current = updater(streamToolsRef.current);
    if (isViewingStream()) {
      setActiveTools(streamToolsRef.current);
    }
  }, []);

  /**
   * Nettoyage complet de fin de stream.
   */
  const cleanupStream = useCallback(() => {
    setIsStreaming(false);
    setStreamingConvId(null);
    streamConvIdRef.current = null;
    streamMsgsRef.current = [];
    streamToolsRef.current = [];
    streamProfileRef.current = null;
    cancelStreamRef.current = null;
  }, []);

  // ─── Actions ──────────────────────────────────────────────

  /**
   * Envoyer un message et gérer le streaming de la réponse.
   */
  const send = useCallback((text, profile = 'fast', conversationId = null) => {
    if (!text.trim() || isStreaming) return;

    setError(null);
    setIsStreaming(true);
    setActiveTools([]);
    setStreamMetadata(null);
    streamStartTimeRef.current = Date.now();
    streamToolsRef.current = [];
    streamProfileRef.current = profile;

    const userMessage = {
      id: `temp-user-${Date.now()}`,
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    };

    const assistantMessage = {
      id: `temp-assistant-${Date.now()}`,
      role: 'assistant',
      content: '',
      isStreaming: true,
      tools: [],
      created_at: new Date().toISOString(),
    };

    // Initialiser les refs ET le state affiché en même temps
    setMessages(prev => {
      const newMsgs = [...prev, userMessage, assistantMessage];
      streamMsgsRef.current = newMsgs;
      return newMsgs;
    });

    const convId = conversationId || currentConversationId;
    const sendingFromConvId = currentConvIdRef.current;

    // Si on connaît déjà l'ID, pré-initialiser les refs de stream
    if (convId) {
      streamConvIdRef.current = convId;
      setStreamingConvId(convId);
    }

    // Lancer le streaming SSE
    cancelStreamRef.current = sendMessage(text, convId, profile, {
      onConversationId: (id) => {
        streamConvIdRef.current = id;
        setStreamingConvId(id);

        // Naviguer vers la nouvelle conversation seulement si l'utilisateur
        // n'a pas encore changé de vue depuis l'envoi
        if (currentConvIdRef.current === sendingFromConvId) {
          setCurrentConversationId(id);
          currentConvIdRef.current = id;
        }
      },

      onToken: (token) => {
        updateStreamMsgs(prev => {
          const updated = [...prev];
          const lastMsg = updated[updated.length - 1];
          if (lastMsg && lastMsg.role === 'assistant') {
            updated[updated.length - 1] = {
              ...lastMsg,
              content: lastMsg.content + token,
            };
          }
          return updated;
        });
      },

      onThinking: (token) => {
        updateStreamMsgs(prev => {
          const updated = [...prev];
          const lastMsg = updated[updated.length - 1];
          if (lastMsg && lastMsg.role === 'assistant') {
            updated[updated.length - 1] = {
              ...lastMsg,
              thinking: (lastMsg.thinking || '') + token,
            };
          }
          return updated;
        });
      },

      onToolStart: (data) => {
        updateStreamTools(prev => [...prev, {
          name: data.tool_name,
          input: data.tool_input,
          status: 'running',
        }]);

        updateStreamMsgs(prev => {
          const updated = [...prev];
          const lastMsg = updated[updated.length - 1];
          if (lastMsg && lastMsg.role === 'assistant') {
            updated[updated.length - 1] = {
              ...lastMsg,
              tools: [...(lastMsg.tools || []), {
                name: data.tool_name,
                input: data.tool_input,
                status: 'running',
              }],
            };
          }
          return updated;
        });
      },

      onToolEnd: (data) => {
        updateStreamTools(prev =>
          prev.map(t =>
            t.name === data.tool_name && t.status === 'running'
              ? { ...t, status: 'done', output: data.tool_output }
              : t
          )
        );

        updateStreamMsgs(prev => {
          const updated = [...prev];
          const lastMsg = updated[updated.length - 1];
          if (lastMsg && lastMsg.role === 'assistant' && lastMsg.tools) {
            const updatedTools = lastMsg.tools.map(t =>
              t.name === data.tool_name && t.status === 'running'
                ? { ...t, status: 'done', output: data.tool_output }
                : t
            );
            updated[updated.length - 1] = {
              ...lastMsg,
              tools: updatedTools,
            };
          }
          return updated;
        });
      },

      onDone: (data) => {
        const elapsed = Date.now() - (streamStartTimeRef.current || Date.now());

        setStreamMetadata({
          ...data,
          client_elapsed_ms: elapsed,
        });

        // Finaliser le message assistant (ref + state si visible)
        updateStreamMsgs(prev => {
          const updated = [...prev];
          const lastMsg = updated[updated.length - 1];
          if (lastMsg && lastMsg.role === 'assistant') {
            updated[updated.length - 1] = {
              ...lastMsg,
              id: data.message_id || lastMsg.id,
              isStreaming: false,
              metadata: data,
            };
          }
          return updated;
        });

        // Nettoyage complet
        cleanupStream();
        setActiveTools([]);
      },

      onError: (errorMsg) => {
        setError(errorMsg);

        // Marquer l'erreur dans le message assistant
        updateStreamMsgs(prev => {
          const updated = [...prev];
          const lastMsg = updated[updated.length - 1];
          if (lastMsg && lastMsg.role === 'assistant' && lastMsg.isStreaming) {
            updated[updated.length - 1] = {
              ...lastMsg,
              content: lastMsg.content || `Erreur: ${errorMsg}`,
              isStreaming: false,
              isError: true,
            };
          }
          return updated;
        });

        // Nettoyage complet
        cleanupStream();
        setActiveTools([]);
      },
    });
  }, [isStreaming, currentConversationId, updateStreamMsgs, updateStreamTools, cleanupStream]);

  /**
   * Annuler le streaming en cours.
   * Sauvegarde la réponse partielle en BDD avant de nettoyer.
   */
  const cancelStream = useCallback(() => {
    // Capturer le contenu partiel AVANT d'annuler
    const convId = streamConvIdRef.current;
    const msgs = streamMsgsRef.current;
    const lastMsg = msgs.length > 0 ? msgs[msgs.length - 1] : null;
    const partialContent = lastMsg?.role === 'assistant' ? lastMsg.content : '';
    const partialThinking = lastMsg?.role === 'assistant' ? lastMsg.thinking : null;

    // Annuler le SSE
    if (cancelStreamRef.current) {
      cancelStreamRef.current();
    }

    // Marquer le message comme terminé avec métadonnées (profil, temps)
    if (lastMsg?.role === 'assistant' && lastMsg.isStreaming) {
      const elapsed = Date.now() - (streamStartTimeRef.current || Date.now());
      const profile = streamProfileRef.current;
      const toolsUsed = streamToolsRef.current
        .filter(t => t.status === 'done')
        .map(t => t.name);

      updateStreamMsgs(prev => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          ...updated[updated.length - 1],
          isStreaming: false,
          metadata: {
            profile: profile,
            thinking_time_ms: elapsed,
            tools_used: toolsUsed,
          },
        };
        return updated;
      });
    }

    // Sauvegarder en BDD si on a du contenu
    if (convId && partialContent?.trim()) {
      savePartialResponse(convId, partialContent, partialThinking).catch(err => {
        console.warn('[Gustave] Erreur sauvegarde partielle:', err);
      });
    }

    cleanupStream();
    setActiveTools([]);
  }, [cleanupStream, updateStreamMsgs]);

  /**
   * Charger les messages d'une conversation existante.
   * Si c'est la conversation en cours de streaming → restaure depuis les refs.
   */
  const loadConversation = useCallback((conversationId, existingMessages) => {
    setCurrentConversationId(conversationId);
    currentConvIdRef.current = conversationId;

    // Restaurer depuis les refs si c'est la conversation en stream
    if (conversationId === streamConvIdRef.current) {
      setMessages(streamMsgsRef.current || []);
      setActiveTools(streamToolsRef.current || []);
    } else {
      // Charger depuis la BDD
      const mapped = (existingMessages || []).map(msg => ({
        ...msg,
        thinking: msg.thinking_content || msg.thinking || undefined,
      }));
      setMessages(mapped);
      setActiveTools([]);
    }

    setError(null);
    setStreamMetadata(null);
  }, []);

  /**
   * Réinitialiser pour une nouvelle conversation.
   * NE PAS annuler le stream — il continue en arrière-plan.
   */
  const newConversation = useCallback(() => {
    setCurrentConversationId(null);
    currentConvIdRef.current = null;
    setMessages([]);
    setError(null);
    setStreamMetadata(null);
    setActiveTools([]);
  }, []);

  return {
    messages,
    isStreaming,
    currentConversationId,
    activeTools,
    streamMetadata,
    error,
    streamingConvId,
    send,
    cancelStream,
    loadConversation,
    newConversation,
  };
};

export default useChat;
