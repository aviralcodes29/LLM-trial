import React, { useState, useEffect } from 'react';
import {
  BookOpen,
  XCircle,
  RefreshCw,
  Database,
  FileText,
  Sparkles,
  Binary,
  Hash,
  ShieldCheck,
  HardDrive,
  MessageSquare,
  X,
  FolderOpen,
  Activity,
  LogOut,
} from 'lucide-react';
import {
  checkHealth,
  fetchDocumentChunks,
  getStoredToken,
  getStoredUser,
  logoutUser,
  fetchCurrentUser,
} from './services/api';
import FileUpload from './components/FileUpload';
import ChatWindow from './components/ChatWindow';
import AuthModal from './components/AuthModal';
import UsageModal from './components/UsageModal';

export function App() {
  const [currentUser, setCurrentUser] = useState(() => getStoredUser());
  const [showAuthModal, setShowAuthModal] = useState(() => !getStoredToken());
  const [showUsageModal, setShowUsageModal] = useState(false);

  const [healthStatus, setHealthStatus] = useState('checking'); // 'checking' | 'connected' | 'error'
  const [healthError, setHealthError] = useState(null);
  const [activeTab, setActiveTab] = useState('chat'); // 'chat' | 'inspector'
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [filterToSelected, setFilterToSelected] = useState(false);
  const [docChunks, setDocChunks] = useState([]);
  const [loadingChunks, setLoadingChunks] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  const verifyBackendHealth = async () => {
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
    const interval = setInterval(() => {
      verifyBackendHealth();
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  // Listen for 401 unauthorized events to trigger re-auth
  useEffect(() => {
    const handleUnauthorized = () => {
      setCurrentUser(null);
      setShowAuthModal(true);
    };
    window.addEventListener('docchat:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('docchat:unauthorized', handleUnauthorized);
  }, []);

  // Refresh profile if token exists
  useEffect(() => {
    if (getStoredToken()) {
      fetchCurrentUser()
        .then((user) => setCurrentUser(user))
        .catch(() => {
          // Token may be invalid or guest
        });
    }
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

  const handleSelectDocument = (doc) => {
    setSelectedDoc(doc);
    if (!doc) {
      setFilterToSelected(false);
      setDocChunks([]);
    }
  };

  const handleAuthSuccess = (user) => {
    setCurrentUser(user);
    setShowAuthModal(false);
    setSelectedDoc(null);
    setDocChunks([]);
  };

  const handleLogout = () => {
    logoutUser();
    setCurrentUser(null);
    setSelectedDoc(null);
    setDocChunks([]);
    setShowAuthModal(true);
  };

  // Render Sidebar Content (shared between Desktop & Mobile)
  const renderSidebarContent = () => (
    <>
      <FileUpload
        key={currentUser?.id || 'guest'}
        selectedDocId={selectedDoc?.doc_id}
        onSelectDocument={(doc) => {
          handleSelectDocument(doc);
          setMobileSidebarOpen(false);
        }}
      />

      {/* Active Document Filter Quick Card */}
      {selectedDoc && (
        <div className="p-3 bg-slate-900/60 rounded-xl border border-slate-800/80 text-xs flex items-center justify-between gap-2 shadow-sm shrink-0">
          <div className="min-w-0">
            <span className="text-[10px] text-slate-400 uppercase font-semibold block">
              Selected Document
            </span>
            <p className="text-slate-200 font-medium truncate text-[11px]">
              {selectedDoc.filename}
            </p>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <button
              type="button"
              onClick={() => setFilterToSelected(!filterToSelected)}
              className={`px-2 py-1 rounded text-[10px] font-medium transition-colors cursor-pointer ${filterToSelected
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                }`}
              title={
                filterToSelected
                  ? 'Chat search limited to this file'
                  : 'Search across all indexed files'
              }
            >
              {filterToSelected ? 'Filter Active' : 'Filter Chat'}
            </button>
            {activeTab !== 'inspector' && (
              <button
                type="button"
                onClick={() => {
                  setActiveTab('inspector');
                  setMobileSidebarOpen(false);
                }}
                className="p-1 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded transition-colors cursor-pointer"
                title="Inspect chunks"
              >
                <Database className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>
      )}

      {/* Production Architecture Specifications Card */}
      <div className="p-4 bg-slate-900/40 rounded-xl border border-slate-800/80 text-xs text-slate-400 space-y-2.5 shrink-0">
        <h4 className="font-semibold text-slate-200 flex items-center gap-1.5 text-xs">
          <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" />
          Phase 6 Production Specs
        </h4>
        <div className="space-y-1.5 text-[11px]">
          <div className="flex justify-between py-1 border-b border-slate-800/60">
            <span>Auth &amp; Database</span>
            <span className="text-indigo-300 font-mono">JWT · SQLite · Bcrypt</span>
          </div>
          <div className="flex justify-between py-1 border-b border-slate-800/60">
            <span>Multi-tenancy</span>
            <span className="text-slate-300 font-mono">Per-User Collections</span>
          </div>
          <div className="flex justify-between py-1 border-b border-slate-800/60">
            <span>Rate Limiting</span>
            <span className="text-amber-300 font-mono">20 chat/m · 10 upl/h</span>
          </div>
          <div className="flex justify-between py-1 border-b border-slate-800/60">
            <span>Cost Tracking</span>
            <span className="text-emerald-300 font-mono">Prompt + Output USD</span>
          </div>
          <div className="flex justify-between py-1">
            <span>Streaming</span>
            <span className="text-slate-300 font-mono">SSE Live Streaming</span>
          </div>
        </div>
      </div>
    </>
  );

  return (
    <div className="flex flex-col h-screen w-screen bg-[#090d16] text-slate-100 overflow-hidden font-sans">
      {/* ── Top Navigation Bar ───────────────────────────────────────── */}
      <header className="h-14 border-b border-slate-800/80 px-3 sm:px-6 flex items-center justify-between bg-slate-950/70 backdrop-blur shrink-0">
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Mobile Sidebar Toggle Button */}
          <button
            type="button"
            onClick={() => setMobileSidebarOpen(!mobileSidebarOpen)}
            className="md:hidden p-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 hover:text-white transition-colors cursor-pointer"
            title="Toggle Documents Sidebar"
            aria-label="Toggle Documents Sidebar"
          >
            <FolderOpen className="w-4 h-4 text-indigo-400" />
          </button>

          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/20 shrink-0">
            <BookOpen className="w-4 h-4 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-bold text-white tracking-tight leading-none">
                DocChat AI
              </h1>
              <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 hidden xs:inline-block">
                Phase 6: Production Hardened
              </span>
            </div>
            <p className="text-[10px] text-slate-400 mt-0.5 hidden sm:block">
              JWT Multi-tenant Auth · Slowapi Rate Limits · SQLite Usage &amp; Cost Tracking
            </p>
          </div>
        </div>

        {/* View Switcher Tabs */}
        <div className="flex items-center bg-slate-900/90 p-1 rounded-xl border border-slate-800 shadow-inner">
          <button
            onClick={() => setActiveTab('chat')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${activeTab === 'chat'
                ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
          >
            <MessageSquare className="w-3.5 h-3.5" />
            <span className="hidden xs:inline">Chat &amp; Q&amp;A</span>
          </button>
          <button
            onClick={() => setActiveTab('inspector')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${activeTab === 'inspector'
                ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
          >
            <Database className="w-3.5 h-3.5" />
            <span className="hidden xs:inline">Inspector</span>
          </button>
        </div>

        {/* Right Section: Usage, Health, User Profile & Logout */}
        <div className="flex items-center gap-2 sm:gap-2.5">
          {/* Usage Analytics Button */}
          <button
            id="view-usage-button"
            type="button"
            onClick={() => setShowUsageModal(true)}
            className="flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-800 rounded-xl text-xs font-medium transition-colors cursor-pointer"
            title="View Token Usage & Cost Analytics"
          >
            <Activity className="w-3.5 h-3.5 text-indigo-400" />
            <span className="hidden md:inline">Usage &amp; Cost</span>
          </button>

          {/* Backend Health Badge */}
          {healthStatus === 'connected' && (
            <div
              id="backend-health-badge"
              className="flex items-center gap-1.5 px-2 sm:px-2.5 py-1.5 rounded-full bg-emerald-950/60 border border-emerald-500/30 text-emerald-400 text-xs font-medium"
              title="FastAPI Backend Online"
            >
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
              </span>
              <span className="text-[11px] hidden lg:inline">Connected</span>
            </div>
          )}

          {healthStatus === 'checking' && (
            <div
              id="backend-health-badge"
              className="flex items-center gap-1.5 px-2 sm:px-2.5 py-1.5 rounded-full bg-amber-950/60 border border-amber-500/30 text-amber-400 text-xs font-medium"
            >
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            </div>
          )}

          {healthStatus === 'error' && (
            <div
              id="backend-health-badge"
              className="flex items-center gap-1.5 px-2 sm:px-2.5 py-1.5 rounded-full bg-rose-950/60 border border-rose-500/30 text-rose-400 text-xs font-medium"
            >
              <XCircle className="w-3.5 h-3.5" />
            </div>
          )}

          {/* User Profile / Logout */}
          {currentUser ? (
            <div className="flex items-center gap-1.5 pl-1.5 border-l border-slate-800/80">
              <div
                className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-900 border border-slate-800 rounded-xl text-xs"
                title={`Signed in as ${currentUser.username}`}
              >
                <div className="w-4 h-4 rounded-full bg-gradient-to-tr from-indigo-500 to-violet-500 flex items-center justify-center text-[9px] font-bold text-white uppercase">
                  {currentUser.username?.[0] || 'U'}
                </div>
                <span className="font-semibold text-slate-200 hidden sm:inline text-[11px]">
                  {currentUser.username}
                </span>
              </div>

              <button
                id="logout-button"
                type="button"
                onClick={handleLogout}
                className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-slate-900 rounded-xl border border-transparent hover:border-slate-800 transition-colors cursor-pointer"
                title="Sign out of DocChat AI"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <button
              id="open-auth-button"
              type="button"
              onClick={() => setShowAuthModal(true)}
              className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold shadow-md shadow-indigo-600/30 transition-colors cursor-pointer"
            >
              Sign In
            </button>
          )}
        </div>
      </header>

      {/* ── Main Layout ──────────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden p-2 sm:p-4 gap-3 sm:gap-4 relative">
        {/* Desktop Left Sidebar */}
        <aside className="w-80 shrink-0 hidden md:flex flex-col gap-3 overflow-y-auto">
          {renderSidebarContent()}
        </aside>

        {/* Mobile Drawer Overlay Backdrop */}
        {mobileSidebarOpen && (
          <div
            className="fixed inset-0 bg-black/70 backdrop-blur-xs z-40 md:hidden animate-fade-in"
            onClick={() => setMobileSidebarOpen(false)}
          />
        )}

        {/* Mobile Slide-in Drawer */}
        <div
          className={`fixed inset-y-0 left-0 w-80 max-w-[85vw] bg-slate-950 p-4 border-r border-slate-800 z-50 flex flex-col gap-3 overflow-y-auto shadow-2xl transition-transform duration-300 md:hidden ${mobileSidebarOpen ? 'translate-x-0' : '-translate-x-full'
            }`}
        >
          <div className="flex items-center justify-between pb-2 border-b border-slate-800/80 shrink-0">
            <div className="flex items-center gap-2">
              <FolderOpen className="w-4 h-4 text-indigo-400" />
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                Document Library
              </h3>
            </div>
            <button
              onClick={() => setMobileSidebarOpen(false)}
              className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          {renderSidebarContent()}
        </div>

        {/* Main Panel */}
        <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {activeTab === 'chat' ? (
            <ChatWindow
              docIds={filterToSelected && selectedDoc ? [selectedDoc.doc_id] : null}
              selectedDoc={filterToSelected ? selectedDoc : null}
              onClearFilter={() => setFilterToSelected(false)}
            />
          ) : (
            /* Chunk Inspector View */
            <div className="flex-1 flex flex-col min-w-0 bg-slate-900/40 rounded-xl border border-slate-800 overflow-hidden">
              <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/40 shrink-0">
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-indigo-400" />
                  <h2 className="text-sm font-semibold text-slate-200">
                    {selectedDoc
                      ? `ChromaDB Chunk Inspector: ${selectedDoc.filename}`
                      : 'Ingestion Pipeline & Vector Store Inspector'}
                  </h2>
                </div>
                {selectedDoc && (
                  <span className="text-xs text-indigo-300 bg-indigo-950/60 border border-indigo-800/60 px-2.5 py-0.5 rounded-full font-mono">
                    {docChunks.length} chunks stored
                  </span>
                )}
              </div>

              <div className="flex-1 overflow-y-auto p-5">
                {selectedDoc ? (
                  <div className="space-y-4">
                    <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-indigo-950/70 border border-indigo-800/50 flex items-center justify-center">
                          <FileText className="w-5 h-5 text-indigo-400" />
                        </div>
                        <div>
                          <h3 className="text-sm font-bold text-white">
                            {selectedDoc.filename}
                          </h3>
                          <p className="text-xs text-slate-400 font-mono mt-0.5">
                            doc_id: {selectedDoc.doc_id}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 text-xs">
                        <div className="text-right">
                          <span className="text-slate-400 block text-[10px] uppercase">
                            Chunks Count
                          </span>
                          <span className="font-semibold text-emerald-400 font-mono text-sm">
                            {docChunks.length}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                          <Binary className="w-3.5 h-3.5 text-indigo-400" />
                          Stored Chunks &amp; Metadata in ChromaDB
                        </h4>
                        {loadingChunks && (
                          <span className="text-xs text-slate-500 flex items-center gap-1">
                            <RefreshCw className="w-3 h-3 animate-spin text-indigo-400" />{' '}
                            Loading chunks…
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
                  <div className="h-full flex flex-col items-center justify-center text-center p-8 max-w-xl mx-auto space-y-6">
                    <div className="w-16 h-16 rounded-2xl bg-indigo-950/60 border border-indigo-800/50 flex items-center justify-center shadow-xl shadow-indigo-950/50">
                      <Database className="w-8 h-8 text-indigo-400" />
                    </div>

                    <div className="space-y-2">
                      <h3 className="text-lg font-bold text-white">
                        Document Ingestion Pipeline Ready
                      </h3>
                      <p className="text-xs text-slate-400 leading-relaxed">
                        Upload a PDF or TXT file using the sidebar panel to trigger the full ingestion pipeline:
                        extract pages, partition into uniform overlapping chunks (~800 characters with 150 overlap),
                        generate Gemini embeddings, and store them persistently in ChromaDB.
                      </p>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full text-left">
                      <div className="p-3 bg-slate-950/70 border border-slate-800/80 rounded-xl space-y-1">
                        <div className="flex items-center gap-1.5 text-indigo-400 text-xs font-semibold">
                          <FileText className="w-3.5 h-3.5" />
                          1. Document Loader
                        </div>
                        <p className="text-[11px] text-slate-400">Extracts text and page numbers from PDF and .txt files.</p>
                      </div>

                      <div className="p-3 bg-slate-950/70 border border-slate-800/80 rounded-xl space-y-1">
                        <div className="flex items-center gap-1.5 text-indigo-400 text-xs font-semibold">
                          <Hash className="w-3.5 h-3.5" />
                          2. Text Chunker
                        </div>
                        <p className="text-[11px] text-slate-400">Splits into ~800 char chunks with 150 overlap and metadata.</p>
                      </div>

                      <div className="p-3 bg-slate-950/70 border border-slate-800/80 rounded-xl space-y-1">
                        <div className="flex items-center gap-1.5 text-indigo-400 text-xs font-semibold">
                          <Sparkles className="w-3.5 h-3.5" />
                          3. Gemini Embedder
                        </div>
                        <p className="text-[11px] text-slate-400">Batched text-embedding-004 with exponential backoff retry.</p>
                      </div>

                      <div className="p-3 bg-slate-950/70 border border-slate-800/80 rounded-xl space-y-1">
                        <div className="flex items-center gap-1.5 text-indigo-400 text-xs font-semibold">
                          <HardDrive className="w-3.5 h-3.5" />
                          4. ChromaDB Storage
                        </div>
                        <p className="text-[11px] text-slate-400">Persistent user-isolated collection with atomic search &amp; delete.</p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 p-3 bg-indigo-950/30 border border-indigo-800/40 rounded-lg text-indigo-300 text-xs">
                      <ShieldCheck className="w-4 h-4 shrink-0 text-indigo-400" />
                      <span>Phase 6 Production Hardening active: JWT Authentication, 20 req/min rate limiting, and SQLite cost tracking.</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </main>
      </div>

      {/* ── Modals ───────────────────────────────────────────────────── */}
      {showAuthModal && (
        <AuthModal
          onAuthSuccess={handleAuthSuccess}
          allowClose={Boolean(currentUser)}
          onClose={() => setShowAuthModal(false)}
        />
      )}

      {showUsageModal && (
        <UsageModal
          isOpen={showUsageModal}
          onClose={() => setShowUsageModal(false)}
        />
      )}
    </div>
  );
}

export default App;
