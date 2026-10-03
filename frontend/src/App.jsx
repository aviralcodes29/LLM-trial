import React, { useState, useEffect } from 'react';
import {
  BookOpen, CheckCircle, XCircle, RefreshCw, Layers, Database,
  FileText, Sparkles, Binary, Hash, ArrowRight, ShieldCheck,
} from 'lucide-react';
import { checkHealth, fetchDocumentChunks } from './services/api';
import FileUpload from './components/FileUpload';

export function App() {
  const [healthStatus, setHealthStatus] = useState('checking'); // 'checking' | 'connected' | 'error'
  const [healthError, setHealthError] = useState(null);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [docChunks, setDocChunks] = useState([]);
  const [loadingChunks, setLoadingChunks] = useState(false);

  const verifyBackendHealth = async () => {
    setHealthStatus('checking');
    setHealthError(null);
    try {
      const data = await checkHealth();
      if (data?.status === 'ok') {
        setHealthStatus('connected');
      } else {
        setHealthStatus('error');
        setHealthError('Unexpected health response');
      }
    } catch (err) {
      setHealthStatus('error');
      setHealthError(err.message || 'Cannot reach FastAPI backend');
    }
  };

  useEffect(() => {
    verifyBackendHealth();
  }, []);

  // When a document is selected, fetch its indexed chunks from ChromaDB
  useEffect(() => {
    if (!selectedDoc?.doc_id) {
      setDocChunks([]);
      return;
    }

    const loadChunks = async () => {
      setLoadingChunks(true);
      try {
        const data = await fetchDocumentChunks(selectedDoc.doc_id);
        setDocChunks(data.chunks || []);
      } catch (err) {
        console.error('Failed to load chunks:', err);
        setDocChunks([]);
      } finally {
        setLoadingChunks(false);
      }
    };

    loadChunks();
  }, [selectedDoc]);

  return (
    <div className="flex flex-col h-screen w-screen bg-[#090d16] text-slate-100 overflow-hidden font-sans">
      {/* ── Top Navigation Bar ───────────────────────────────────────── */}
      <header className="h-14 border-b border-slate-800/80 px-6 flex items-center justify-between bg-slate-950/70 backdrop-blur shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <BookOpen className="w-4 h-4 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-bold text-white tracking-tight leading-none">DocChat AI</h1>
              <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                Phase 2: Ingestion
              </span>
            </div>
            <p className="text-[10px] text-slate-400 mt-0.5">Document Ingestion Pipeline · ChromaDB Vector Storage</p>
          </div>
        </div>

        {/* Backend Health Badge */}
        <div className="flex items-center gap-2">
          {healthStatus === 'connected' && (
            <div
              id="backend-health-badge"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-950/60 border border-emerald-500/30 text-emerald-400 text-xs font-medium"
            >
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
              </span>
              <CheckCircle className="w-3.5 h-3.5" />
              <span>Backend Connected</span>
            </div>
          )}

          {healthStatus === 'checking' && (
            <div
              id="backend-health-badge"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-amber-950/60 border border-amber-500/30 text-amber-400 text-xs font-medium"
            >
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              <span>Checking Backend…</span>
            </div>
          )}

          {healthStatus === 'error' && (
            <div
              id="backend-health-badge"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-rose-950/60 border border-rose-500/30 text-rose-400 text-xs font-medium"
            >
              <XCircle className="w-3.5 h-3.5" />
              <span>Backend Offline: {healthError}</span>
              <button
                onClick={verifyBackendHealth}
                className="ml-1 px-2 py-0.5 bg-rose-900/50 hover:bg-rose-800 rounded text-[11px] text-rose-200 transition-colors"
              >
                Retry
              </button>
            </div>
          )}
        </div>
      </header>

      {/* ── Main Layout ──────────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden p-4 gap-4">
        {/* Left Sidebar: Document Upload & List */}
        <aside className="w-80 shrink-0 flex flex-col gap-4 overflow-y-auto">
          <FileUpload
            selectedDocId={selectedDoc?.doc_id}
            onSelectDocument={(doc) => setSelectedDoc(doc)}
          />

          {/* Pipeline Specifications Card */}
          <div className="p-4 bg-slate-900/40 rounded-xl border border-slate-800/80 text-xs text-slate-400 space-y-2.5">
            <h4 className="font-semibold text-slate-200 flex items-center gap-1.5 text-xs">
              <Layers className="w-3.5 h-3.5 text-indigo-400" />
              Phase 2 Pipeline Specs
            </h4>
            <div className="space-y-1.5 text-[11px]">
              <div className="flex justify-between py-1 border-b border-slate-800/60">
                <span>Loader</span>
                <span className="text-slate-300 font-mono">pypdf & Text (Pages)</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800/60">
                <span>Chunk Size / Overlap</span>
                <span className="text-slate-300 font-mono">~800 / 150 chars</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800/60">
                <span>Embedder</span>
                <span className="text-slate-300 font-mono">text-embedding-004</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800/60">
                <span>Vector Store</span>
                <span className="text-slate-300 font-mono">ChromaDB (Persistent)</span>
              </div>
              <div className="flex justify-between py-1">
                <span>Max File Size</span>
                <span className="text-slate-300 font-mono">10 MB</span>
              </div>
            </div>
          </div>
        </aside>

        {/* Main Panel: Ingestion Inspector & Pipeline Viewer */}
        <main className="flex-1 flex flex-col min-w-0 bg-slate-900/40 rounded-xl border border-slate-800 overflow-hidden">
          {/* Top Panel Banner */}
          <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/40">
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-indigo-400" />
              <h2 className="text-sm font-semibold text-slate-200">
                {selectedDoc ? `ChromaDB Chunk Inspector: ${selectedDoc.filename}` : 'Ingestion Pipeline & Vector Store Inspector'}
              </h2>
            </div>
            {selectedDoc && (
              <span className="text-xs text-indigo-300 bg-indigo-950/60 border border-indigo-800/60 px-2.5 py-0.5 rounded-full font-mono">
                {docChunks.length} chunks stored
              </span>
            )}
          </div>

          {/* Content Area */}
          <div className="flex-1 overflow-y-auto p-5">
            {selectedDoc ? (
              <div className="space-y-4">
                {/* Document Metadata Summary Header */}
                <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-indigo-950/70 border border-indigo-800/50 flex items-center justify-center">
                      <FileText className="w-5 h-5 text-indigo-400" />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-white">{selectedDoc.filename}</h3>
                      <p className="text-xs text-slate-400 font-mono mt-0.5">doc_id: {selectedDoc.doc_id}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 text-xs">
                    <div className="text-right">
                      <span className="text-slate-400 block text-[10px] uppercase">Chunks Count</span>
                      <span className="font-semibold text-emerald-400 font-mono text-sm">{docChunks.length}</span>
                    </div>
                  </div>
                </div>

                {/* Stored Chunks List */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                      <Binary className="w-3.5 h-3.5 text-indigo-400" />
                      Stored Chunks & Metadata in ChromaDB
                    </h4>
                    {loadingChunks && (
                      <span className="text-xs text-slate-500 flex items-center gap-1">
                        <RefreshCw className="w-3 h-3 animate-spin text-indigo-400" /> Loading chunks…
                      </span>
                    )}
                  </div>

                  {docChunks.length > 0 ? (
                    <div className="space-y-2.5">
                      {docChunks.map((chunk, idx) => {
                        const meta = chunk.metadata || {};
                        return (
                          <div
                            key={chunk.chunk_id || idx}
                            className="p-3.5 bg-slate-950/70 rounded-lg border border-slate-800/80 hover:border-slate-700 transition-colors text-xs"
                          >
                            <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-800/60 text-[11px]">
                              <div className="flex items-center gap-2">
                                <span className="px-2 py-0.5 rounded bg-indigo-900/50 text-indigo-300 font-mono font-medium">
                                  Chunk #{meta.chunk_index !== undefined ? meta.chunk_index : idx}
                                </span>
                                {meta.page_number && (
                                  <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
                                    Page {meta.page_number}
                                  </span>
                                )}
                                <span className="text-slate-500 font-mono text-[10px]">
                                  {chunk.chunk_id}
                                </span>
                              </div>
                              <span className="text-slate-400 font-mono text-[10px]">
                                {meta.char_count || chunk.text?.length || 0} characters
                              </span>
                            </div>

                            <p className="text-slate-300 font-mono leading-relaxed whitespace-pre-wrap bg-slate-900/40 p-2.5 rounded border border-slate-800/40 text-[11px]">
                              {chunk.text}
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    !loadingChunks && (
                      <p className="text-xs text-slate-500 italic p-4 text-center">
                        No chunks retrieved for this document.
                      </p>
                    )
                  )}
                </div>
              </div>
            ) : (
              /* Empty state / Architecture diagram when no document selected */
              <div className="h-full flex flex-col items-center justify-center text-center p-8 max-w-xl mx-auto space-y-6">
                <div className="w-16 h-16 rounded-2xl bg-indigo-950/60 border border-indigo-800/50 flex items-center justify-center shadow-xl shadow-indigo-950/50">
                  <Database className="w-8 h-8 text-indigo-400" />
                </div>

                <div className="space-y-2">
                  <h3 className="text-lg font-bold text-white">Document Ingestion Pipeline Ready</h3>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    Upload a PDF or TXT file using the sidebar panel to trigger the full ingestion pipeline:
                    extract pages, partition into uniform overlapping chunks (~800 characters with 150 overlap),
                    generate Gemini embeddings, and store them persistently in ChromaDB.
                  </p>
                </div>

                {/* 4 Pipeline Steps Visual */}
                <div className="grid grid-cols-2 gap-3 w-full text-left">
                  <div className="p-3 bg-slate-950/70 border border-slate-800/80 rounded-xl space-y-1">
                    <div className="flex items-center gap-1.5 text-indigo-400 text-xs font-semibold">
                      <FileText className="w-3.5 h-3.5" />
                      1. Document Loader
                    </div>
                    <p className="text-[11px] text-slate-400">Extracts text and page numbers from PDF (pypdf) and .txt files.</p>
                  </div>

                  <div className="p-3 bg-slate-950/70 border border-slate-800/80 rounded-xl space-y-1">
                    <div className="flex items-center gap-1.5 text-indigo-400 text-xs font-semibold">
                      <Hash className="w-3.5 h-3.5" />
                      2. Text Chunker
                    </div>
                    <p className="text-[11px] text-slate-400">Splits into ~800 character chunks with 150 overlap and metadata preservation.</p>
                  </div>

                  <div className="p-3 bg-slate-950/70 border border-slate-800/80 rounded-xl space-y-1">
                    <div className="flex items-center gap-1.5 text-indigo-400 text-xs font-semibold">
                      <Sparkles className="w-3.5 h-3.5" />
                      3. Gemini Embedder
                    </div>
                    <p className="text-[11px] text-slate-400">Batched calls to text-embedding-004 with exponential backoff on rate limits.</p>
                  </div>

                  <div className="p-3 bg-slate-950/70 border border-slate-800/80 rounded-xl space-y-1">
                    <div className="flex items-center gap-1.5 text-indigo-400 text-xs font-semibold">
                      <HardDrive className="w-3.5 h-3.5" />
                      4. ChromaDB Storage
                    </div>
                    <p className="text-[11px] text-slate-400">Persistent vector collection with add_chunks(), list_documents(), delete_document().</p>
                  </div>
                </div>

                <div className="flex items-center gap-2 p-3 bg-indigo-950/30 border border-indigo-800/40 rounded-lg text-indigo-300 text-xs">
                  <ShieldCheck className="w-4 h-4 shrink-0 text-indigo-400" />
                  <span>Phase 2 strictly focuses on Ingestion. RAG chat retrieval is scheduled for Phase 3.</span>
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;
