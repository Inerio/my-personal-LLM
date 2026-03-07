/**
 * Client API — Gustave Code
 * Communication avec le backend FastAPI.
 *
 * REST (axios)  : passe par le proxy React (URLs relatives, pas de CORS).
 * SSE streaming : connexion directe au backend (le proxy React peut
 *                 bufferiser ou couper les flux longue durée).
 */

import axios from 'axios';

// URL complète du backend (pour SSE + fallback)
const BACKEND_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// REST : URLs relatives → proxy React s'en charge en dev
const apiClient = axios.create({
  baseURL: process.env.REACT_APP_API_URL || '',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 15000, // 15s timeout pour les requêtes REST
});

// ============================================
// Conversations
// ============================================

export const getConversations = async (limit = 50) => {
  const response = await apiClient.get(`/conversations?limit=${limit}`);
  return response.data;
};

export const getConversation = async (conversationId) => {
  const response = await apiClient.get(`/conversations/${conversationId}`);
  return response.data;
};

export const deleteConversation = async (conversationId) => {
  const response = await apiClient.delete(`/conversations/${conversationId}`);
  return response.data;
};

export const renameConversation = async (conversationId, title) => {
  const response = await apiClient.patch(
    `/conversations/${conversationId}/title?title=${encodeURIComponent(title)}`
  );
  return response.data;
};

export const savePartialResponse = async (conversationId, content, thinkingContent = null) => {
  const response = await apiClient.post(
    `/conversations/${conversationId}/save-partial`,
    { content, thinking_content: thinkingContent }
  );
  return response.data;
};

// ============================================
// Modèles & Profils
// ============================================

export const getProfiles = async () => {
  const response = await apiClient.get('/models/profiles');
  return response.data;
};

export const getModels = async () => {
  const response = await apiClient.get('/models');
  return response.data;
};

// ============================================
// Health Check
// ============================================

export const getHealth = async () => {
  const response = await apiClient.get('/health');
  return response.data;
};

// ============================================
// Chat SSE Streaming
// ============================================

/**
 * Envoyer un message et recevoir la réponse en streaming SSE.
 * Le streaming passe directement par le backend (pas de proxy)
 * pour éviter le buffering et les timeouts.
 *
 * @param {string} message - Le message de l'utilisateur
 * @param {string|null} conversationId - ID conversation existante ou null
 * @param {string} profile - Profil qualité: 'fast', 'llama', 'mixtral'
 * @param {object} callbacks - Callbacks pour chaque type d'événement
 * @returns {function} Fonction pour annuler le stream
 */
export const sendMessage = (message, conversationId, profile, callbacks) => {
  const abortController = new AbortController();

  const startStream = async () => {
    try {
      // SSE direct vers le backend (pas de proxy React)
      const url = `${BACKEND_URL}/chat`;

      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          conversation_id: conversationId,
          profile: profile || 'fast',
        }),
        signal: abortController.signal,
      });

      if (!response.ok) {
        const errText = await response.text().catch(() => '');
        throw new Error(
          response.status === 502 || response.status === 503
            ? 'Le backend ne répond pas. Vérifiez que les services sont démarrés.'
            : `Erreur serveur (${response.status}): ${errText || response.statusText}`
        );
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Parser les événements SSE
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Garder le dernier morceau incomplet

        let eventType = null;
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.substring(7).trim();
          } else if (line.startsWith('data: ') && eventType) {
            try {
              const data = JSON.parse(line.substring(6));

              switch (eventType) {
                case 'conversation_id':
                  callbacks.onConversationId?.(data.id);
                  break;
                case 'token':
                  callbacks.onToken?.(data.token);
                  break;
                case 'thinking':
                  callbacks.onThinking?.(data.token);
                  break;
                case 'tool_start':
                  callbacks.onToolStart?.(data);
                  break;
                case 'tool_end':
                  callbacks.onToolEnd?.(data);
                  break;
                case 'done':
                  callbacks.onDone?.(data);
                  break;
                case 'error':
                  callbacks.onError?.(data.message || 'Erreur inconnue');
                  break;
                default:
                  break;
              }
            } catch (e) {
              console.warn('Erreur parsing SSE:', e, line);
            }
            eventType = null;
          }
          // Les lignes commençant par ":" sont des commentaires SSE (keepalive) — on les ignore
        }
      }
    } catch (error) {
      if (error.name === 'AbortError') return;

      // Log complet pour debug (visible dans la console navigateur F12)
      console.error('[Gustave] Erreur SSE:', error);

      // Messages d'erreur clairs selon le type
      let userMessage;
      const msg = (error.message || '').toLowerCase();

      if (msg.includes('failed to fetch') || msg.includes('networkerror') || msg.includes('network')) {
        userMessage = 'Impossible de joindre le backend. Vérifiez que tous les services sont démarrés dans le launcher.';
      } else if (msg.includes('timeout') || msg.includes('aborted')) {
        userMessage = 'La requête a expiré. Le modèle met peut-être trop de temps à répondre.';
      } else {
        userMessage = error.message || 'Erreur de connexion au serveur';
      }

      callbacks.onError?.(userMessage);
    }
  };

  startStream();

  // Retourner une fonction pour annuler
  return () => abortController.abort();
};

export default apiClient;
