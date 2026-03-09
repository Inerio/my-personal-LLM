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

export const purgeMemory = async () => {
  const response = await apiClient.delete('/conversations/memory/purge');
  return response.data;
};

export const deleteAllConversations = async () => {
  const response = await apiClient.delete('/conversations/all');
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

// Timeout de connexion initiale par profil (ms)
// Les gros modèles mettent beaucoup plus de temps à charger
const PROFILE_CONNECT_TIMEOUTS = {
  fast: 60_000,       // 1 min
  llama: 300_000,     // 5 min (CPU offloading)
  mixtral: 600_000,   // 10 min (modèle massif)
};

// Timeout entre deux chunks SSE (ms) — si aucun chunk ni keepalive
// pendant cette durée, on considère la connexion morte
const STREAM_INACTIVITY_TIMEOUT = 120_000; // 2 min

/**
 * Diagnostiquer la cause d'une erreur en vérifiant l'état des services.
 * Appelé après un timeout ou une perte de connexion pour donner un
 * message précis à l'utilisateur.
 */
const diagnoseError = async (profile) => {
  try {
    const resp = await fetch(`${BACKEND_URL}/health`, { signal: AbortSignal.timeout(5000) });
    if (!resp.ok) {
      return 'Le serveur backend ne répond plus. Relancez les services depuis le launcher.';
    }
    const health = await resp.json();

    if (!health.ollama_connected) {
      return (
        'Ollama a crashé (probablement un manque de mémoire). ' +
        'Relancez Ollama depuis le launcher.'
      );
    }

    // Backend + Ollama OK → c'est un vrai timeout d'inactivité
    const profileLabels = { fast: 'Rapide', llama: 'Qualité', mixtral: 'Expert' };
    const label = profileLabels[profile] || profile;
    return (
      `Le modèle ${label} a mis trop de temps à répondre. ` +
      'Essayez un prompt plus court ou le profil Rapide.'
    );
  } catch {
    // Même le health check échoue → backend complètement HS
    return 'Le serveur backend ne répond plus. Relancez tous les services depuis le launcher.';
  }
};

/**
 * Forcer le déchargement d'un modèle Ollama de la RAM.
 * Appelé après annulation d'un stream sur un profil lourd
 * pour libérer la mémoire immédiatement.
 */
const forceUnloadModel = (profile) => {
  fetch(`${BACKEND_URL}/models/unload`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ profile }),
  }).then(() => {
    console.log(`[Gustave] Déchargement forcé du modèle (${profile})`);
  }).catch(() => {
    // Pas grave si ça échoue — best effort
  });
};

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

  // Refs de timers partagées — accessibles depuis la fonction cancel
  let connectTimerRef = null;
  let inactivityTimerRef = null;
  let cancelled = false;

  const clearAllTimers = () => {
    if (connectTimerRef) { clearTimeout(connectTimerRef); connectTimerRef = null; }
    if (inactivityTimerRef) { clearTimeout(inactivityTimerRef); inactivityTimerRef = null; }
  };

  const startStream = async () => {
    // Timer de connexion initiale (attend le premier byte du serveur)
    const connectTimeout = PROFILE_CONNECT_TIMEOUTS[profile] || 60_000;
    connectTimerRef = setTimeout(async () => {
      abortController.abort();
      // Diagnostic : health check pour savoir pourquoi ça ne se connecte pas
      const errorMsg = await diagnoseError(profile);
      if (!cancelled) callbacks.onError?.(errorMsg);
    }, connectTimeout);

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

      // Connexion établie, annuler le timer de connexion
      if (connectTimerRef) { clearTimeout(connectTimerRef); connectTimerRef = null; }

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

      // Timer d'inactivité — reset à chaque chunk reçu
      const resetInactivityTimer = () => {
        if (inactivityTimerRef) clearTimeout(inactivityTimerRef);
        inactivityTimerRef = setTimeout(async () => {
          console.warn('[Gustave] Timeout inactivité SSE — diagnostic en cours...');
          abortController.abort();
          // Diagnostic : health check pour savoir ce qui a cassé
          const errorMsg = await diagnoseError(profile);
          if (!cancelled) callbacks.onError?.(errorMsg);
        }, STREAM_INACTIVITY_TIMEOUT);
      };
      resetInactivityTimer();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // Données reçues — reset le timer d'inactivité
        resetInactivityTimer();

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

      // Stream terminé proprement — nettoyer les timers
      clearAllTimers();

    } catch (error) {
      // Toujours nettoyer les timers, même sur erreur
      clearAllTimers();

      if (error.name === 'AbortError') return;

      // Log complet pour debug (visible dans la console navigateur F12)
      console.error('[Gustave] Erreur SSE:', error);

      // Diagnostic précis via health check
      const userMessage = await diagnoseError(profile);
      if (!cancelled) callbacks.onError?.(userMessage);
    }
  };

  startStream();

  // Retourner une fonction pour annuler proprement
  return () => {
    cancelled = true;       // Empêche les callbacks d'erreur tardifs
    clearAllTimers();        // Nettoie TOUS les timers (connectTimer + inactivityTimer)
    abortController.abort(); // Coupe le fetch

    // Forcer le déchargement du modèle pour les profils lourds
    // → libère immédiatement la RAM au lieu d'attendre keep_alive
    if (profile === 'mixtral' || profile === 'llama') {
      forceUnloadModel(profile);
    }
  };
};

export default apiClient;
