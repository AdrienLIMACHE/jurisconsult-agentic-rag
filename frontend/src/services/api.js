/**
 * frontend/src/services/api.js
 * Client HTTP & SSE pour communiquer avec le backend FastAPI Agentic RAG (TP2 + TP3 LangGraph).
 */

const BASE_URL = '/api';

export async function getRandomCases(limit = 30) {
  const res = await fetch(`${BASE_URL}/cases/random?limit=${limit}`);
  if (!res.ok) {
    return [];
  }
  return res.json();
}

export async function searchCases(query, topK = 30) {
  const res = await fetch(`${BASE_URL}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, top_k: topK, mode: 'hybrid' }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Erreur lors de la recherche.');
  }
  return res.json();
}

export async function getCaseDetail(affaireId) {
  const res = await fetch(`${BASE_URL}/cases/${affaireId}`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Erreur lors de la récupération de l'affaire.");
  }
  return res.json();
}

export async function getSummary(affaireId, forceRefresh = false) {
  const res = await fetch(`${BASE_URL}/summary`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ affaire_id: affaireId, force_refresh: forceRefresh }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Erreur lors de la génération du résumé.');
  }
  return res.json();
}

export async function askQuestion(affaireId, question, useAgent = true) {
  const threadId = affaireId ? `session_${affaireId}` : 'session_global';
  const res = await fetch(`${BASE_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      affaire_id: affaireId || null,
      question,
      thread_id: threadId,
      use_agent: useAgent,
    }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Erreur lors du chat Agentic RAG.');
  }
  return res.json();
}

export async function getAgentGraphInfo() {
  const res = await fetch(`${BASE_URL}/agent/graph`);
  if (!res.ok) return null;
  return res.json();
}

export async function getHealth() {
  const res = await fetch(`${BASE_URL}/health`);
  if (!res.ok) return { status: 'offline', cases_loaded: 0 };
  return res.json();
}

export async function getCacheStats() {
  const res = await fetch(`${BASE_URL}/summary/cache`);
  if (!res.ok) return { total_cached: 0, cached_affaire_ids: [] };
  return res.json();
}
