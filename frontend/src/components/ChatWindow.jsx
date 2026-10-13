import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Send,
  Sparkles,
  RotateCcw,
  Square,
  FileQuestion,
  HelpCircle,
  Lightbulb,
  FileText,
  AlertCircle,
  Plus,
} from 'lucide-react';
import MessageBubble from './MessageBubble';
import { streamChatMessage, clearChatSession } from '../services/api';

const EXAMPLE_QUESTIONS = [
  {
    icon: Lightbulb,
    title: 'Document Overview',
    prompt: 'What is this document about? Give a concise overview.',
    tag: 'Overview',
  },
  {
    icon: FileText,
    title: 'Key Takeaways',
    prompt: 'What are the main key points or takeaways discussed?',
    tag: 'Highlights',
  },
  {
    icon: HelpCircle,
    title: 'Deep Summary',
    prompt: 'Summarize the key sections and conclusions in detail.',
    tag: 'Summary',
  },
];

/**
 * ChatWindow — Phase 4: Live SSE Streaming + Conversation Memory + UX
 */
const ChatWindow = ({ docIds = null, selectedDoc = null, onClearFilter = null }) => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionId, setSessionId] = useState(() =>
    'session_' + Math.random().toString(36).substring(2, 10)
  );
  const [errorBanner, setErrorBanner] = useState(null);

  const bottomRef = useRef(null);
  const inputRef = useRef(null);
  const abortControllerRef = useRef(null);

  // Auto-scroll to bottom as tokens stream in
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isStreaming]);

  // Clean up abort controller on unmount
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  const handleSendMessage = useCallback(
    async (overrideText = null) => {
      const question = (overrideText !== null ? overrideText : input).trim();
      if (!question || isStreaming) return;

      setErrorBanner(null);
      setInput('');

      // Add user message to UI
      const userMessage = { role: 'user', content: question, sources: [] };
      setMessages((prev) => [...prev, userMessage]);

      // Prepare assistant placeholder message for streaming
      const assistantMessageIndex = messages.length + 1;
      const initialAssistantMessage = {
        role: 'assistant',
        content: '',
        sources: [],
        rewrittenQuery: null,
      };
      setMessages((prev) => [...prev, initialAssistantMessage]);

      setIsStreaming(true);

      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      try {
        await streamChatMessage({
          question,
          docIds,
          sessionId,
          signal: abortController.signal,
          onToken: (token) => {
            setMessages((prev) => {
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
          onSources: (sources) => {
            setMessages((prev) => {
              const updated = [...prev];
              const lastMsg = updated[updated.length - 1];
              if (lastMsg && lastMsg.role === 'assistant') {
                updated[updated.length - 1] = {
                  ...lastMsg,
                  sources: sources || [],
                };
              }
              return updated;
            });
          },
          onRewrittenQuery: (rewritten) => {
            setMessages((prev) => {
              const updated = [...prev];
              const lastMsg = updated[updated.length - 1];
              if (lastMsg && lastMsg.role === 'assistant') {
                updated[updated.length - 1] = {
                  ...lastMsg,
                  rewrittenQuery: rewritten,
                };
              }
              return updated;
            });
          },
        });
      } catch (err) {
        if (err.name === 'AbortError') {
          // User aborted manually via "Stop generating"
          setMessages((prev) => {
            const updated = [...prev];
            const lastMsg = updated[updated.length - 1];
            if (lastMsg && lastMsg.role === 'assistant') {
              updated[updated.length - 1] = {
                ...lastMsg,
                content: lastMsg.content + (lastMsg.content ? '\n\n*(Generation stopped by user)*' : '*(Generation stopped)*'),
              };
            }
            return updated;
          });
        } else {
          const detail = err.message || 'Stream connection error';
          setErrorBanner(detail);
          setMessages((prev) => {
            const updated = [...prev];
            const lastMsg = updated[updated.length - 1];
            if (lastMsg && lastMsg.role === 'assistant' && !lastMsg.content) {
              updated[updated.length - 1] = {
                ...lastMsg,
                content: `⚠️ **Request failed:** ${detail}\n\nMake sure the backend is active and documents are indexed.`,
              };
            }
            return updated;
          });
        }
      } finally {
        setIsStreaming(false);
        abortControllerRef.current = null;
        setTimeout(() => inputRef.current?.focus(), 80);
      }
    },
    [input, isStreaming, docIds, sessionId, messages.length]
  );

  const handleStopGenerating = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  const handleNewChat = async () => {
    if (isStreaming) {
      abortControllerRef.current?.abort();
    }
    try {
      await clearChatSession(sessionId);
    } catch (e) {
      console.warn('Failed to clear session on backend:', e);
    }
    const newId = 'session_' + Math.random().toString(36).substring(2, 10);
    setSessionId(newId);
    setMessages([]);
    setErrorBanner(null);
    setInput('');
    setTimeout(() => inputRef.current?.focus(), 100);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-950/40 rounded-2xl border border-slate-800/80 overflow-hidden shadow-xl">
      {/* ── Header ──────────────────────────────────────────────────── */}
      <div className="px-5 py-3 border-b border-slate-800/80 flex items-center justify-between bg-slate-900/50 backdrop-blur shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <Sparkles className="w-4 h-4 text-indigo-400 shrink-0" />
          <h2 className="text-sm font-semibold text-slate-200 truncate">Grounded Document Q&amp;A</h2>

          {selectedDoc ? (
            <span className="ml-1 flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-indigo-950/80 border border-indigo-700/50 text-[10px] text-indigo-300 font-medium">
              <span className="truncate max-w-[130px]">Filter: {selectedDoc.filename}</span>
              {onClearFilter && (
                <button
                  type="button"
                  onClick={onClearFilter}
                  title="Search across all documents"
                  className="hover:text-white text-indigo-400 font-bold ml-0.5 cursor-pointer"
                >
                  ×
                </button>
              )}
            </span>
          ) : (
            <span className="ml-1 px-2 py-0.5 rounded-full bg-indigo-950/60 border border-indigo-700/30 text-[10px] text-indigo-300 font-mono hidden sm:inline-block">
              All Documents
            </span>
          )}
        </div>

        {/* Header Actions */}
        <div className="flex items-center gap-2">
          {/* New Chat Button */}
          <button
            onClick={handleNewChat}
            title="Start a new chat session"
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium text-slate-300 hover:text-white bg-slate-800/60 hover:bg-slate-700 border border-slate-700/60 transition-all cursor-pointer shadow-sm active:scale-95"
          >
            <Plus className="w-3.5 h-3.5 text-indigo-400" />
            <span className="hidden sm:inline">New Chat</span>
          </button>

          {/* Reset / Clear Button */}
          {messages.length > 0 && (
            <button
              onClick={handleNewChat}
              title="Reset conversation"
              className="p-1.5 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-slate-800 transition-colors cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* ── Error Banner (if any) ────────────────────────────────────── */}
      {errorBanner && (
        <div className="px-4 py-2 bg-rose-950/70 border-b border-rose-800/60 text-xs text-rose-300 flex items-center justify-between">
          <div className="flex items-center gap-2 min-w-0">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span className="truncate">{errorBanner}</span>
          </div>
          <button
            onClick={() => setErrorBanner(null)}
            className="text-rose-400 hover:text-white text-xs ml-2 cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* ── Message Area / Empty State ───────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-5 py-5 space-y-4 scroll-smooth">
        {messages.length === 0 ? (
          /* Empty State Screen with 3 Clickable Example Questions */
          <div className="h-full flex flex-col items-center justify-center max-w-lg mx-auto text-center py-6">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-indigo-600/30 to-violet-600/30 border border-indigo-500/30 flex items-center justify-center mb-4 shadow-xl shadow-indigo-950/40">
              <FileQuestion className="w-7 h-7 text-indigo-400" />
            </div>

            <h3 className="text-lg font-bold text-white tracking-tight mb-1">
              DocChat AI Conversation
            </h3>
            <p className="text-xs text-slate-400 max-w-sm mb-6 leading-relaxed">
              Ask questions grounded strictly in your uploaded documents. Powered by Gemini,
              ChromaDB vector search, multi-turn memory, and live token streaming.
            </p>

            <div className="w-full space-y-2 text-left">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 block px-1">
                Try an example question
              </span>
              <div className="grid gap-2">
                {EXAMPLE_QUESTIONS.map((ex, idx) => {
                  const Icon = ex.icon;
                  return (
                    <button
                      key={idx}
                      onClick={() => handleSendMessage(ex.prompt)}
                      className="group flex items-center justify-between p-3 rounded-xl bg-slate-900/60 hover:bg-slate-900 border border-slate-800 hover:border-indigo-500/50 transition-all text-left cursor-pointer shadow-sm hover:shadow-indigo-950/30 active:scale-[0.99]"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-8 h-8 rounded-lg bg-indigo-950/70 border border-indigo-800/40 flex items-center justify-center shrink-0 group-hover:bg-indigo-900/80 transition-colors">
                          <Icon className="w-4 h-4 text-indigo-400" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-xs font-semibold text-slate-200 group-hover:text-indigo-200 transition-colors">
                            {ex.title}
                          </p>
                          <p className="text-[11px] text-slate-400 truncate">
                            {ex.prompt}
                          </p>
                        </div>
                      </div>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800/80 text-slate-400 shrink-0 ml-2 group-hover:text-indigo-300 group-hover:bg-indigo-950/80 border border-transparent group-hover:border-indigo-800/40 transition-colors">
                        {ex.tag}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        ) : (
          /* Render Messages */
          messages.map((msg, idx) => (
            <MessageBubble
              key={idx}
              message={msg}
              isStreaming={isStreaming && idx === messages.length - 1 && msg.role === 'assistant'}
            />
          ))
        )}

        <div ref={bottomRef} />
      </div>

      {/* ── Input Form & Stop Generating Button ───────────────────────── */}
      <div className="px-4 pb-4 pt-2.5 border-t border-slate-800/80 bg-slate-900/30 shrink-0">
        {/* Floating Stop Generating Indicator */}
        {isStreaming && (
          <div className="flex justify-center mb-2">
            <button
              type="button"
              onClick={handleStopGenerating}
              className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-800/90 hover:bg-rose-950/80 text-slate-200 hover:text-rose-200 border border-slate-700 hover:border-rose-700/60 text-xs font-medium shadow-md transition-all cursor-pointer active:scale-95"
            >
              <Square className="w-3 h-3 fill-rose-400 text-rose-400" />
              <span>Stop generating</span>
            </button>
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="flex items-end gap-2"
        >
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              id="chat-input"
              rows={1}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                e.target.style.height = 'auto';
                e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
              }}
              onKeyDown={handleKeyDown}
              placeholder={
                isStreaming
                  ? 'Generating response…'
                  : 'Ask a question or follow up on your documents…'
              }
              disabled={isStreaming}
              className="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-4 py-3 pr-4 text-sm text-slate-100
                         placeholder-slate-500 resize-none focus:outline-none focus:border-indigo-500
                         focus:ring-1 focus:ring-indigo-500/50 transition-all leading-relaxed
                         disabled:opacity-60 disabled:cursor-not-allowed"
              style={{ minHeight: '48px', maxHeight: '120px' }}
            />
          </div>

          {isStreaming ? (
            <button
              type="button"
              onClick={handleStopGenerating}
              className="flex items-center justify-center w-11 h-11 bg-rose-600/90 hover:bg-rose-600 text-white rounded-xl transition-all shadow-md shadow-rose-600/20 active:scale-95 shrink-0 cursor-pointer"
              title="Stop generating"
            >
              <Square className="w-4 h-4 fill-white" />
            </button>
          ) : (
            <button
              type="submit"
              id="chat-send-btn"
              disabled={!input.trim()}
              className="flex items-center justify-center w-11 h-11 bg-indigo-600 hover:bg-indigo-500
                         disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-indigo-600
                         text-white rounded-xl transition-all shadow-md shadow-indigo-600/20
                         active:scale-95 shrink-0 cursor-pointer"
              title="Send (Enter)"
            >
              <Send className="w-4 h-4" />
            </button>
          )}
        </form>

        <p className="text-[10px] text-slate-500 mt-2 text-center">
          Enter to send · Shift+Enter for new line · Multi-turn memory active · Grounded in uploaded files only
        </p>
      </div>
    </div>
  );
};

export default ChatWindow;
