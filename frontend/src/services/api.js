import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

const TOKEN_KEY = 'docchat_token';
const USER_KEY = 'docchat_user';

export const getStoredToken = () => localStorage.getItem(TOKEN_KEY);
export const setStoredToken = (token) => localStorage.setItem(TOKEN_KEY, token);
export const removeStoredToken = () => localStorage.removeItem(TOKEN_KEY);

export const getStoredUser = () => {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
};
export const setStoredUser = (user) => localStorage.setItem(USER_KEY, JSON.stringify(user));
export const removeStoredUser = () => localStorage.removeItem(USER_KEY);

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 60000, // 60s — LLM calls can take a while
});

// Request interceptor: attach JWT bearer token if available
api.interceptors.request.use((config) => {
  const token = getStoredToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor: handle 401 unauthorized
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // Clear token if expired or invalid
      removeStoredToken();
      removeStoredUser();
      window.dispatchEvent(new CustomEvent('docchat:unauthorized'));
    }
    return Promise.reject(error);
  }
);

/**
 * Check backend connection status via /health endpoint.
 * @returns {Promise<{ status: string }>}
 */
export const checkHealth = async () => {
  const response = await api.get('/health');
  return response.data;
};

// ---------------------------------------------------------------------------
// Authentication API (Phase 6)
// ---------------------------------------------------------------------------

/**
 * Register a new user account.
 * @param {{ username: string, password: string, email?: string }} data
 * @returns {Promise<{ access_token: string, token_type: string, user: Object }>}
 */
export const registerUser = async ({ username, password, email }) => {
  const response = await api.post('/api/auth/register', {
    username,
    password,
    email: email || undefined,
  });
  if (response.data.access_token) {
    setStoredToken(response.data.access_token);
    setStoredUser(response.data.user);
  }
  return response.data;
};

/**
 * Authenticate with username and password.
 * @param {{ username: string, password: string }} data
 * @returns {Promise<{ access_token: string, token_type: string, user: Object }>}
 */
export const loginUser = async ({ username, password }) => {
  const response = await api.post('/api/auth/login', { username, password });
  if (response.data.access_token) {
    setStoredToken(response.data.access_token);
    setStoredUser(response.data.user);
  }
  return response.data;
};

/**
 * Fetch profile information for the authenticated user.
 * @returns {Promise<Object>}
 */
export const fetchCurrentUser = async () => {
  const response = await api.get('/api/auth/me');
  setStoredUser(response.data);
  return response.data;
};

/**
 * Log out user and clear stored credentials.
 */
export const logoutUser = () => {
  removeStoredToken();
  removeStoredUser();
};

/**
 * Retrieve token consumption metrics and estimated USD costs.
 * @returns {Promise<{ total_requests: number, prompt_tokens: number, completion_tokens: number, total_tokens: number, estimated_cost_usd: number, recent_records: Array }>}
 */
export const fetchUsageStats = async () => {
  const response = await api.get('/api/usage');
  return response.data;
};

// ---------------------------------------------------------------------------
// Document Management API
// ---------------------------------------------------------------------------

/**
 * Upload a document file to the backend for ingestion.
 * @param {File} file
 * @returns {Promise<{ doc_id: string, filename: string, chunks_count: number, message: string }>}
 */
export const uploadDocument = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await api.post('/api/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

/**
 * Fetch all indexed documents for the current user.
 * @returns {Promise<{ documents: Array, total_documents: number }>}
 */
export const fetchDocuments = async () => {
  const response = await api.get('/api/upload/documents');
  return response.data;
};

/**
 * Delete an indexed document by ID.
 * @param {string} docId
 * @returns {Promise<any>}
 */
export const deleteDocument = async (docId) => {
  const response = await api.delete(`/api/upload/documents/${docId}`);
  return response.data;
};

/**
 * Fetch chunks and metadata for an indexed document.
 * @param {string} docId
 * @returns {Promise<{ doc_id: string, total_chunks: number, chunks: Array }>}
 */
export const fetchDocumentChunks = async (docId) => {
  const response = await api.get(`/api/documents/${docId}/chunks`);
  return response.data;
};

// ---------------------------------------------------------------------------
// Chat & Q&A API
// ---------------------------------------------------------------------------

/**
 * Send a non-streaming chat question to the backend RAG pipeline.
 * @param {string} question
 * @param {string[]|null} docIds - Optional doc_id filter
 * @param {string|null} sessionId - Session ID for conversation memory
 * @returns {Promise<{ answer: string, sources: Array, session_id?: string, rewritten_query?: string }>}
 */
export const sendChatMessage = async (question, docIds = null, sessionId = null) => {
  const response = await api.post('/api/chat', {
    question,
    doc_ids: docIds && docIds.length > 0 ? docIds : undefined,
    session_id: sessionId || undefined,
    stream: false,
  });
  return response.data;
};

/**
 * Stream a chat question via Server-Sent Events (SSE).
 */
export const streamChatMessage = async ({
  question,
  docIds = null,
  sessionId = null,
  onToken,
  onSources,
  onRewrittenQuery,
  signal,
}) => {
  const token = getStoredToken();
  const headers = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      question,
      doc_ids: docIds && docIds.length > 0 ? docIds : undefined,
      session_id: sessionId || undefined,
      stream: true,
    }),
    signal,
  });

  if (!response.ok) {
    let errorMessage = `Server error ${response.status}`;
    try {
      const errJson = await response.json();
      errorMessage = errJson.detail || errJson.message || errorMessage;
    } catch (e) {
      // ignore
    }
    throw new Error(errorMessage);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith('data:')) continue;
      const jsonStr = trimmed.slice(5).trim();
      if (!jsonStr) continue;

      try {
        const payload = JSON.parse(jsonStr);
        if (payload.type === 'token' && onToken) {
          onToken(payload.content);
        } else if (payload.type === 'sources' && onSources) {
          onSources(payload.sources);
        } else if (payload.type === 'rewritten_query' && onRewrittenQuery) {
          onRewrittenQuery(payload.query);
        } else if (payload.type === 'error') {
          throw new Error(payload.message || 'Stream generation failed');
        }
      } catch (err) {
        if (err.message && err.message.includes('Stream generation failed')) {
          throw err;
        }
        console.warn('Failed to parse SSE chunk:', jsonStr, err);
      }
    }
  }
};

/**
 * Reset conversation memory for a session on the backend.
 * @param {string|null} sessionId
 * @returns {Promise<{ status: string, message: string }>}
 */
export const clearChatSession = async (sessionId = null) => {
  const response = await api.post('/api/chat/clear', {
    session_id: sessionId || undefined,
  });
  return response.data;
};

export default api;
