import React, { useState } from 'react';
import { Bot, User, BookOpen, ChevronDown, ChevronUp, FileText, Percent } from 'lucide-react';

/**
 * SourceCard — expandable citation card under assistant messages.
 */
const SourceCard = ({ source, index }) => {
  const [expanded, setExpanded] = useState(false);
  const scorePercent = Math.round((source.score ?? 0) * 100);
  const scoreColor =
    scorePercent >= 70 ? 'text-emerald-400' :
    scorePercent >= 40 ? 'text-amber-400' : 'text-rose-400';

  return (
    <div className="rounded-lg border border-slate-700/60 bg-slate-950/50 overflow-hidden transition-all">
      {/* Card header — always visible */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-slate-800/40 transition-colors group"
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
          {expanded
            ? <ChevronUp className="w-3 h-3 text-slate-500 group-hover:text-slate-300 transition-colors" />
            : <ChevronDown className="w-3 h-3 text-slate-500 group-hover:text-slate-300 transition-colors" />
          }
        </div>
      </button>

      {/* Expanded snippet */}
      {expanded && (
        <div className="px-3 pb-3 pt-1 border-t border-slate-800/60">
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
 * Assistant messages show expandable source citation cards below the answer.
 */
const MessageBubble = ({ message }) => {
  const isUser = message.role === 'user';
  const hasSources = !isUser && message.sources && message.sources.length > 0;

  return (
    <div className={`flex gap-3 mb-1 ${isUser ? 'flex-row-reverse' : 'flex-row'} items-start`}>
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

      {/* Bubble */}
      <div className={`max-w-[82%] flex flex-col gap-2 ${isUser ? 'items-end' : 'items-start'}`}>
        <div
          className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
            isUser
              ? 'bg-indigo-600 text-white rounded-tr-sm shadow-md shadow-indigo-600/20'
              : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-tl-sm shadow-md shadow-black/20'
          }`}
        >
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>

        {/* Source Citations */}
        {hasSources && (
          <div className="w-full space-y-1">
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
