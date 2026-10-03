import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 60000, // 60s — LLM calls can take a while
});

/**
 * Check backend connection status via /health endpoint.
 * @returns {Promise<{ status: string }>}
 */
export const checkHealth = async () => {
  const response = await api.get('/health');
  return response.data;
};

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
 * Fetch all indexed documents from the backend.
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

/**
 * Send a chat question to the backend RAG pipeline.
 * @param {string} question
 * @param {string[]|null} docIds - Optional doc_id filter
 * @param {Array} chatHistory
 * @returns {Promise<{ answer: string, sources: Array }>}
 */
export const sendChatMessage = async (question, docIds = null, chatHistory = []) => {
  const response = await api.post('/api/chat', {
    question,
    doc_ids: docIds && docIds.length > 0 ? docIds : undefined,
    chat_history: chatHistory,
  });
  return response.data;
};

export default api;
