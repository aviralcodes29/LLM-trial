import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  Bot,
  User,
  BookOpen,
  ChevronDown,
  ChevronUp,
  FileText,
  Copy,
  Check,
  Sparkles,
} from 'lucide-react';

/**
 * SourceCard — expandable citation card under assistant messages.
 */
const SourceCard = ({ source }) => {
  const [expanded, setExpanded] = useState(false);
  const scorePercent = Math.round((source.score ?? 0) * 100);
  const scoreColor =
    scorePercent >= 70
      ? 'text-emerald-400'
      : scorePercent >= 40
      ? 'text-amber-400'
      : 'text-rose-400';

  return (
    <div className="rounded-lg border border-slate-700/60 bg-slate-950/50 overflow-hidden transition-all">
      {/* Card header — always visible */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-slate-800/40 transition-colors group cursor-pointer"
        aria-expanded={expanded}
      >
        <div className="flex items-center gap-2 min-w-0">
          <FileText className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
          <span className="text-[11px] font-medium text-indigo-300 truncate">
            {source.filename}
          </span>
          {source.page != null && (
            <span className="text-[10px] text-slate-500 shrink-0">· p.{source.page}</span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0 ml-2">
          <span className={`text-[10px] font-mono font-semibold ${scoreColor}`}>
            {scorePercent}%
          </span>
          {expanded ? (
            <ChevronUp className="w-3 h-3 text-slate-500 group-hover:text-slate-300 transition-colors" />
          ) : (
            <ChevronDown className="w-3 h-3 text-slate-500 group-hover:text-slate-300 transition-colors" />
          )}
        </div>
      </button>

      {/* Expanded snippet */}
      {expanded && (
        <div className="px-3 pb-3 pt-1 border-t border-slate-800/60 bg-slate-950/80">
          <p className="text-[11px] text-slate-400 italic leading-relaxed line-clamp-6">
            "{source.snippet}"
          </p>
        </div>
      )}
    </div>
  );
};

/**
 * MessageBubble — renders a single chat message (user or assistant).
 * Assistant messages feature:
 *  - react-markdown formatting
 *  - Code block styling
 *  - Copy answer button with visual feedback
 *  - Live streaming typing cursor indicator
 *  - Expandable source citations
 */
const MessageBubble = ({ message, isStreaming = false }) => {
  const isUser = message.role === 'user';
  const hasSources = !isUser && message.sources && message.sources.length > 0;
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (!message.content) return;
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`flex gap-3 mb-2 ${isUser ? 'flex-row-reverse' : 'flex-row'} items-start group`}>
      {/* Avatar */}
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-white shadow-sm mt-0.5 ${
          isUser
            ? 'bg-gradient-to-tr from-indigo-600 to-violet-500'
            : 'bg-gradient-to-tr from-emerald-600 to-teal-500'
        }`}
      >
        {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
      </div>

      {/* Bubble Container */}
      <div className={`max-w-[85%] md:max-w-[78%] flex flex-col gap-2 ${isUser ? 'items-end' : 'items-start'}`}>
        {/* Rewritten Query Sub-header (if contextualized follow-up) */}
        {!isUser && message.rewrittenQuery && (
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-indigo-950/60 border border-indigo-800/40 text-[10px] text-indigo-300">
            <Sparkles className="w-3 h-3 text-indigo-400 shrink-0" />
            <span className="truncate">Context query: "{message.rewrittenQuery}"</span>
          </div>
        )}

        {/* Message Content Bubble */}
        <div
          className={`relative rounded-2xl px-4 py-3 text-sm leading-relaxed ${
            isUser
              ? 'bg-indigo-600 text-white rounded-tr-sm shadow-md shadow-indigo-600/20'
              : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-tl-sm shadow-md shadow-black/20'
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="markdown-body">
              <ReactMarkdown
                components={{
                  p: ({ children }) => (
                    <p className="mb-2 last:mb-0 leading-relaxed text-slate-200">{children}</p>
                  ),
                  strong: ({ children }) => (
                    <strong className="font-semibold text-white">{children}</strong>
                  ),
                  ul: ({ children }) => (
                    <ul className="list-disc pl-5 mb-2 space-y-1 text-slate-300">{children}</ul>
                  ),
                  ol: ({ children }) => (
                    <ol className="list-decimal pl-5 mb-2 space-y-1 text-slate-300">{children}</ol>
                  ),
                  li: ({ children }) => <li className="text-slate-200">{children}</li>,
                  h1: ({ children }) => (
                    <h1 className="text-base font-bold text-white mb-2 mt-1">{children}</h1>
                  ),
                  h2: ({ children }) => (
                    <h2 className="text-sm font-bold text-white mb-1.5 mt-1">{children}</h2>
                  ),
                  h3: ({ children }) => (
                    <h3 className="text-xs font-bold text-indigo-300 uppercase tracking-wider mb-1 mt-1">
                      {children}
                    </h3>
                  ),
                  code({ node, inline, className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || '');
                    return !inline ? (
                      <div className="relative my-2 rounded-lg bg-slate-950/90 border border-slate-800 overflow-hidden font-mono text-xs shadow-inner">
                        <div className="flex items-center justify-between px-3 py-1 bg-slate-900/90 border-b border-slate-800 text-[10px] text-slate-400">
                          <span className="font-semibold text-slate-300">{match ? match[1] : 'code'}</span>
                        </div>
                        <pre className="p-3 overflow-x-auto text-slate-200 text-xs leading-relaxed">
                          <code className={className} {...props}>
                            {children}
                          </code>
                        </pre>
                      </div>
                    ) : (
                      <code
                        className="px-1.5 py-0.5 rounded bg-slate-800/80 text-indigo-300 font-mono text-xs border border-slate-700/50"
                        {...props}
                      >
                        {children}
                      </code>
                    );
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>

              {/* Live Streaming Typing Cursor */}
              {isStreaming && (
                <span
                  className="inline-block w-1.5 h-4 ml-1 bg-indigo-400 animate-pulse align-middle rounded-xs"
                  title="Generating response..."
                />
              )}
            </div>
          )}

          {/* Copy Button for Assistant Messages */}
          {!isUser && message.content && (
            <button
              onClick={handleCopy}
              title={copied ? 'Copied to clipboard!' : 'Copy answer'}
              className="absolute top-2 right-2 p-1 rounded-md text-slate-400 hover:text-white bg-slate-900/70 hover:bg-slate-800 border border-slate-700/50 transition-all opacity-0 group-hover:opacity-100 cursor-pointer shadow-sm"
              aria-label="Copy answer"
            >
              {copied ? (
                <Check className="w-3.5 h-3.5 text-emerald-400" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
            </button>
          )}
        </div>

        {/* Source Citations */}
        {hasSources && (
          <div className="w-full space-y-1 mt-0.5">
            <div className="flex items-center gap-1.5 px-1">
              <BookOpen className="w-3 h-3 text-emerald-500" />
              <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                {message.sources.length} verified source{message.sources.length > 1 ? 's' : ''}
              </span>
            </div>
            <div className="grid gap-1">
              {message.sources.map((src, idx) => (
                <SourceCard key={idx} source={src} index={idx + 1} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default MessageBubble;
