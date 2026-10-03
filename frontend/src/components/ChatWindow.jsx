import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Sparkles, RotateCcw, Loader2, MessageSquare } from 'lucide-react';
import MessageBubble from './MessageBubble';
import { sendChatMessage } from '../services/api';

const WELCOME_MESSAGE = {
  role: 'assistant',
  content:
    '👋 Welcome to **DocChat AI**! Upload a document from the sidebar, then ask any question.\n\n' +
    'I will answer strictly from your documents and always cite my sources.',
  sources: [],
};

/**
 * ChatWindow — main conversation interface for Phase 3 RAG chat.
 *
 * Features:
 *  - Input with send button + keyboard shortcut (Enter to send)
 *  - Loading indicator while awaiting backend response
 *  - Auto-scroll to latest message
 *  - Optional doc_ids prop to restrict retrieval scope
 *  - Clear conversation button
 */
const ChatWindow = ({ docIds = null }) => {
  const [messages, setMessages] = useState([WELCOME_MESSAGE]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSubmit = useCallback(
    async (e) => {
      e?.preventDefault();
      const question = input.trim();
      if (!question || isLoading) return;

      // Add user message immediately
      setMessages((prev) => [...prev, { role: 'user', content: question, sources: [] }]);
      setInput('');
      setIsLoading(true);

      try {
        const response = await sendChatMessage(question, docIds);
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: response.answer,
            sources: response.sources || [],
          },
        ]);
      } catch (err) {
        const detail = err.response?.data?.detail || err.message || 'Unknown error';
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: `⚠️ **Request failed:** ${detail}\n\nMake sure the backend is running and a document has been uploaded.`,
            sources: [],
          },
        ]);
      } finally {
        setIsLoading(false);
        // Re-focus input after response
        setTimeout(() => inputRef.current?.focus(), 100);
      }
    },
    [input, isLoading, docIds]
  );

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const clearConversation = () => {
    setMessages([WELCOME_MESSAGE]);
    setInput('');
    inputRef.current?.focus();
  };

  const msgCount = messages.filter((m) => m.role !== 'assistant' || m !== WELCOME_MESSAGE).length;

  return (
    <div className="flex flex-col h-full bg-slate-950/40 rounded-2xl border border-slate-800/80 overflow-hidden shadow-xl">
      {/* ── Header ──────────────────────────────────────────────────── */}
      <div className="px-5 py-3.5 border-b border-slate-800/80 flex items-center justify-between bg-slate-900/50 backdrop-blur shrink-0">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-indigo-400" />
          <h2 className="text-sm font-semibold text-slate-200">Grounded Document Q&amp;A</h2>
          <span className="ml-1 px-2 py-0.5 rounded-full bg-indigo-950/60 border border-indigo-700/30 text-[10px] text-indigo-300 font-mono">
            RAG · Phase 3
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-slate-500 font-mono hidden sm:block">
            Gemini · ChromaDB
          </span>
          {messages.length > 1 && (
            <button
              onClick={clearConversation}
              title="Clear conversation"
              className="p-1.5 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-slate-800 transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* ── Message List ─────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-5 py-5 space-y-5 scroll-smooth">
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}

        {/* Loading indicator */}
        {isLoading && (
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-emerald-600 to-teal-500 flex items-center justify-center shrink-0 shadow-sm">
              <Loader2 className="w-4 h-4 text-white animate-spin" />
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-2xl rounded-tl-sm px-4 py-3 shadow-md">
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <span className="flex gap-1">
                  {[0, 1, 2].map((i) => (
                    <span
                      key={i}
                      className="inline-block w-1.5 h-1.5 rounded-full bg-indigo-500"
                      style={{ animation: `bounce 1.2s ${i * 0.2}s ease-in-out infinite` }}
                    />
                  ))}
                </span>
                <span>Searching documents and generating answer…</span>
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* ── Input Form ───────────────────────────────────────────────── */}
      <div className="px-4 pb-4 pt-3 border-t border-slate-800/80 bg-slate-900/30 shrink-0">
        <form onSubmit={handleSubmit} className="flex items-end gap-2">
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              id="chat-input"
              rows={1}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                // Auto-grow textarea up to 5 rows
                e.target.style.height = 'auto';
                e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
              }}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question about your documents…"
              disabled={isLoading}
              className="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-4 py-3 pr-4 text-sm text-slate-100
                         placeholder-slate-500 resize-none focus:outline-none focus:border-indigo-500
                         focus:ring-1 focus:ring-indigo-500/50 transition-all leading-relaxed
                         disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ minHeight: '48px', maxHeight: '120px' }}
            />
          </div>
          <button
            type="submit"
            id="chat-send-btn"
            disabled={!input.trim() || isLoading}
            className="flex items-center justify-center w-11 h-11 bg-indigo-600 hover:bg-indigo-500
                       disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-indigo-600
                       text-white rounded-xl transition-all shadow-md shadow-indigo-600/20
                       active:scale-95 shrink-0"
            title="Send (Enter)"
          >
            {isLoading
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <Send className="w-4 h-4" />
            }
          </button>
        </form>
        <p className="text-[10px] text-slate-600 mt-2 text-center">
          Enter to send · Shift+Enter for new line · Answers grounded in uploaded documents only
        </p>
      </div>

      {/* Bounce animation keyframes */}
      <style>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
          40% { transform: translateY(-6px); opacity: 1; }
        }
      `}</style>
    </div>
  );
};

export default ChatWindow;
