import React, { useState, useEffect } from 'react';
import {
  UploadCloud, FileText, CheckCircle2, AlertCircle, Loader2,
  Trash2, RefreshCw, Library, HardDrive, Check,
} from 'lucide-react';
import { uploadDocument, fetchDocuments, deleteDocument } from '../services/api';

/**
 * FileUpload — Document ingestion component for Phase 2.
 *
 * Features:
 *  - Drag-and-drop file upload with visual active state
 *  - Upload progress / ingestion processing state
 *  - Success and error feedback messages
 *  - Sidebar list of uploaded documents with chunk count and delete button
 *  - Document selection for chunk inspection
 */
const FileUpload = ({ onDocumentsChange, onSelectDocument, selectedDocId }) => {
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadStatus, setUploadStatus] = useState('idle'); // idle | uploading | success | error
  const [uploadProgress, setUploadProgress] = useState(0);
  const [message, setMessage] = useState('');
  const [documents, setDocuments] = useState([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [isDragging, setIsDragging] = useState(false);

  // ── Fetch indexed documents from backend ───────────────────────────────
  const loadDocuments = async () => {
    setLoadingDocs(true);
    try {
      const data = await fetchDocuments();
      const docList = Array.isArray(data) ? data : (data?.documents || []);
      setDocuments(docList);
      onDocumentsChange?.(docList.map((d) => d.doc_id));
      if (docList.length > 0 && !selectedDocId) {
        onSelectDocument?.(docList[0]);
      }
    } catch {
      // Backend may still be initializing
    } finally {
      setLoadingDocs(false);
    }
  };

  useEffect(() => {
    loadDocuments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Drag & Drop Handlers ──────────────────────────────────────────────
  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      validateAndSetFile(file);
    }
  };

  // ── File Selection ────────────────────────────────────────────────────
  const handleFileChange = (e) => {
    if (e.target.files?.[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (file) => {
    const validExtensions = ['.pdf', '.txt', '.md'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();

    if (!validExtensions.includes(ext)) {
      setUploadStatus('error');
      setMessage(`Unsupported file type '${ext}'. Please choose a .pdf, .txt, or .md file.`);
      setSelectedFile(null);
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      setUploadStatus('error');
      setMessage(`File exceeds 10 MB limit (${(file.size / 1024 / 1024).toFixed(1)} MB).`);
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);
    setUploadStatus('idle');
    setMessage('');
  };

  // ── Upload Execution ──────────────────────────────────────────────────
  const handleUpload = async () => {
    if (!selectedFile) return;
    setUploadStatus('uploading');
    setUploadProgress(25);
    setMessage('Parsing document and extracting pages…');

    const progressTimer = setInterval(() => {
      setUploadProgress((prev) => {
        if (prev < 85) return prev + 15;
        return prev;
      });
    }, 400);

    try {
      const res = await uploadDocument(selectedFile);
      clearInterval(progressTimer);
      setUploadProgress(100);
      setUploadStatus('success');
      const chunksCount = res.chunks_count || res.number_of_chunks || 0;
      setMessage(res.message || `Successfully ingested '${res.filename}' into ChromaDB (${chunksCount} chunks indexed).`);
      setSelectedFile(null);

      const fileInput = document.getElementById('doc-upload');
      if (fileInput) fileInput.value = '';

      await loadDocuments();
      if (res.doc_id) {
        onSelectDocument?.({ doc_id: res.doc_id, filename: res.filename, chunks_count: chunksCount });
      }
    } catch (err) {
      clearInterval(progressTimer);
      setUploadStatus('error');
      setMessage(err.response?.data?.detail || err.message || 'Upload failed. Check backend logs.');
    }
  };

  // ── Delete Execution ──────────────────────────────────────────────────
  const handleDelete = async (e, docId) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to remove this document and delete its chunks from ChromaDB?')) {
      return;
    }

    setDeletingId(docId);
    try {
      await deleteDocument(docId);
      const updatedDocs = documents.filter((d) => d.doc_id !== docId);
      setDocuments(updatedDocs);
      onDocumentsChange?.(updatedDocs.map((d) => d.doc_id));
      if (selectedDocId === docId) {
        onSelectDocument?.(updatedDocs[0] || null);
      }
    } catch (err) {
      console.error('Delete failed:', err);
      alert('Failed to delete document: ' + (err.response?.data?.detail || err.message));
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="flex flex-col gap-4 p-4 bg-slate-900/60 rounded-xl border border-slate-800 backdrop-blur-sm">
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-800/80">
        <div>
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-1.5">
            <HardDrive className="w-4 h-4 text-indigo-400" />
            Document Ingestion
          </h3>
          <p className="text-[11px] text-slate-400 mt-0.5">Phase 2: Loader · Chunker · Vectorstore</p>
        </div>
        <button
          onClick={loadDocuments}
          disabled={loadingDocs}
          title="Refresh indexed documents"
          className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loadingDocs ? 'animate-spin text-indigo-400' : ''}`} />
        </button>
      </div>

      {/* Drag & Drop Zone */}
      <label
        htmlFor="doc-upload"
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`flex flex-col items-center justify-center p-5 border-2 border-dashed rounded-xl cursor-pointer transition-all duration-200 text-center
          ${isDragging
            ? 'border-indigo-500 bg-indigo-950/30 scale-[1.01]'
            : 'border-slate-700/80 hover:border-indigo-500/70 bg-slate-950/40 hover:bg-slate-900/40'
          }`}
      >
        <UploadCloud className={`w-8 h-8 mb-2 transition-transform duration-200 ${isDragging ? 'text-indigo-400 scale-125' : 'text-slate-400 hover:text-indigo-400'}`} />
        <span className="text-xs font-semibold text-slate-200">
          {isDragging ? 'Drop file to upload' : 'Click or drag document here'}
        </span>
        <span className="text-[10px] text-slate-400 mt-1">PDF (.pdf) or Text (.txt, .md)</span>
        <span className="text-[9px] text-slate-500 mt-0.5">Max size: 10 MB</span>
        <input
          id="doc-upload"
          type="file"
          accept=".pdf,.txt,.md"
          className="hidden"
          onChange={handleFileChange}
        />
      </label>

      {/* Selected File Stage */}
      {selectedFile && (
        <div className="flex flex-col gap-2 p-3 bg-slate-800/60 rounded-lg border border-slate-700/70 text-xs">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 truncate">
              <FileText className="w-4 h-4 text-indigo-400 shrink-0" />
              <span className="truncate text-slate-200 font-medium">{selectedFile.name}</span>
            </div>
            <span className="text-[10px] text-slate-400 font-mono shrink-0 ml-2">
              {(selectedFile.size / 1024).toFixed(1)} KB
            </span>
          </div>

          <button
            onClick={handleUpload}
            disabled={uploadStatus === 'uploading'}
            id="upload-btn"
            className="w-full py-2 px-3 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-900/50
                       text-white rounded-lg text-xs font-semibold transition-all shadow-md
                       shadow-indigo-600/20 flex items-center justify-center gap-2 cursor-pointer disabled:cursor-not-allowed"
          >
            {uploadStatus === 'uploading' ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Ingesting ({uploadProgress}%)…
              </>
            ) : (
              'Ingest Document'
            )}
          </button>
        </div>
      )}

      {/* Progress Bar (during upload) */}
      {uploadStatus === 'uploading' && (
        <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
          <div
            className="bg-indigo-500 h-1.5 rounded-full transition-all duration-300"
            style={{ width: `${uploadProgress}%` }}
          />
        </div>
      )}

      {/* Status Alert Message */}
      {message && (
        <div
          className={`flex items-start gap-2 p-3 rounded-lg text-xs transition-all ${
            uploadStatus === 'success'
              ? 'bg-emerald-950/40 text-emerald-300 border border-emerald-800/40'
              : uploadStatus === 'error'
              ? 'bg-rose-950/40 text-rose-300 border border-rose-800/40'
              : 'bg-indigo-950/40 text-indigo-300 border border-indigo-800/40'
          }`}
        >
          {uploadStatus === 'success' ? (
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400 mt-0.5" />
          ) : (
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          )}
          <span className="leading-relaxed">{message}</span>
        </div>
      )}

      {/* Uploaded Documents List */}
      <div className="space-y-2 mt-1">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Library className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Indexed Documents ({documents.length})
            </span>
          </div>
          {documents.length > 0 && (
            <span className="text-[10px] text-slate-500">
              {documents.reduce((acc, d) => acc + (d.chunks_count || 0), 0)} total chunks
            </span>
          )}
        </div>

        {documents.length > 0 ? (
          <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1 custom-scrollbar">
            {documents.map((doc) => {
              const isSelected = selectedDocId === doc.doc_id;
              return (
                <div
                  key={doc.doc_id}
                  onClick={() => onSelectDocument?.(doc)}
                  className={`flex items-center justify-between p-2.5 rounded-lg border text-xs cursor-pointer transition-all duration-150 group ${
                    isSelected
                      ? 'bg-indigo-950/40 border-indigo-500/50 text-indigo-200 shadow-sm'
                      : 'bg-slate-950/50 hover:bg-slate-800/50 border-slate-800/80 text-slate-300'
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText className={`w-4 h-4 shrink-0 ${isSelected ? 'text-indigo-400' : 'text-slate-400 group-hover:text-indigo-400'}`} />
                    <div className="min-w-0">
                      <p className="font-medium text-[11px] truncate">{doc.filename}</p>
                      <p className="text-[10px] text-slate-500 flex items-center gap-1">
                        <span>{doc.chunks_count} chunks</span>
                        {doc.file_type && <span className="uppercase text-[9px] px-1 py-0.2 bg-slate-800 rounded">{doc.file_type}</span>}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-1 ml-2 shrink-0">
                    {isSelected && (
                      <Check className="w-3.5 h-3.5 text-indigo-400 mr-1" title="Selected" />
                    )}
                    <button
                      onClick={(e) => handleDelete(e, doc.doc_id)}
                      disabled={deletingId === doc.doc_id}
                      title="Delete document and its chunks"
                      className="p-1 text-slate-500 hover:text-rose-400 hover:bg-rose-950/40 rounded transition-colors opacity-70 group-hover:opacity-100"
                    >
                      {deletingId === doc.doc_id ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin text-rose-400" />
                      ) : (
                        <Trash2 className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          !loadingDocs && (
            <div className="p-4 border border-dashed border-slate-800 rounded-lg text-center">
              <p className="text-[11px] text-slate-500 italic">No documents indexed yet.</p>
              <p className="text-[10px] text-slate-600 mt-1">Upload a PDF or TXT above to start.</p>
            </div>
          )
        )}
      </div>
    </div>
  );
};

export default FileUpload;
