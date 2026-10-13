import React, { useState, useEffect } from 'react';
import {
  Activity,
  DollarSign,
  Layers,
  RefreshCw,
  X,
  Clock,
  Sparkles,
  Zap,
  TrendingUp,
  ShieldAlert,
} from 'lucide-react';
import { fetchUsageStats } from '../services/api';

export function UsageModal({ isOpen, onClose }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchUsageStats();
      setStats(data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to fetch usage metrics.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadStats();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const promptPercent =
    stats && stats.total_tokens > 0
      ? Math.round((stats.prompt_tokens / stats.total_tokens) * 100)
      : 0;
  const completionPercent = 100 - promptPercent;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
      <div className="w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-2xl p-5 sm:p-6 shadow-2xl shadow-indigo-950/50 flex flex-col max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800 shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-indigo-950/80 border border-indigo-800/60 flex items-center justify-center">
              <TrendingUp className="w-4 h-4 text-indigo-400" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white leading-tight">
                Token Usage &amp; Cost Tracking
              </h3>
              <p className="text-[11px] text-slate-400">
                Live consumption metrics recorded per authenticated request
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={loadStats}
              disabled={loading}
              className="p-1.5 rounded-lg bg-slate-800/80 text-slate-300 hover:text-white hover:bg-slate-700 transition-colors cursor-pointer"
              title="Refresh usage statistics"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-indigo-400' : ''}`} />
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg bg-slate-800/80 text-slate-400 hover:text-white hover:bg-slate-700 transition-colors cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto py-4 space-y-4 pr-1">
          {error && (
            <div className="p-3 bg-rose-950/50 border border-rose-500/30 rounded-xl text-xs text-rose-300 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          {/* Metric KPI Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {/* Total Tokens */}
            <div className="p-3.5 bg-slate-950/80 border border-slate-800/80 rounded-xl">
              <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                Total Tokens
              </span>
              <div className="flex items-baseline gap-1 mt-1">
                <span className="text-xl font-bold font-mono text-indigo-300">
                  {stats ? stats.total_tokens.toLocaleString() : '—'}
                </span>
                <span className="text-[10px] text-slate-500">tok</span>
              </div>
            </div>

            {/* Estimated Cost */}
            <div className="p-3.5 bg-slate-950/80 border border-slate-800/80 rounded-xl">
              <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                Estimated Cost
              </span>
              <div className="flex items-baseline gap-1 mt-1">
                <span className="text-xl font-bold font-mono text-emerald-400">
                  ${stats ? stats.estimated_cost_usd.toFixed(6) : '0.000000'}
                </span>
                <span className="text-[10px] text-slate-500">USD</span>
              </div>
            </div>

            {/* Total Requests */}
            <div className="p-3.5 bg-slate-950/80 border border-slate-800/80 rounded-xl">
              <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                API Calls
              </span>
              <div className="flex items-baseline gap-1 mt-1">
                <span className="text-xl font-bold font-mono text-white">
                  {stats ? stats.total_requests : 0}
                </span>
                <span className="text-[10px] text-slate-500">reqs</span>
              </div>
            </div>

            {/* Active Rate Limits */}
            <div className="p-3.5 bg-slate-950/80 border border-slate-800/80 rounded-xl">
              <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                Rate Limit
              </span>
              <div className="mt-1 space-y-0.5 text-[10px] font-mono text-amber-300">
                <div>20 chat / min</div>
                <div className="text-slate-400">10 uploads / hr</div>
              </div>
            </div>
          </div>

          {/* Token Breakdown Bar */}
          {stats && stats.total_tokens > 0 && (
            <div className="p-4 bg-slate-950/50 border border-slate-800/80 rounded-xl space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-300 font-medium">Token Distribution</span>
                <div className="flex items-center gap-3 text-[11px] font-mono">
                  <span className="text-indigo-400">
                    Prompt: {stats.prompt_tokens.toLocaleString()} ({promptPercent}%)
                  </span>
                  <span className="text-violet-400">
                    Completion: {stats.completion_tokens.toLocaleString()} ({completionPercent}%)
                  </span>
                </div>
              </div>
              <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden flex">
                <div
                  style={{ width: `${promptPercent}%` }}
                  className="bg-indigo-500 h-full transition-all duration-500"
                  title={`Prompt tokens: ${promptPercent}%`}
                />
                <div
                  style={{ width: `${completionPercent}%` }}
                  className="bg-violet-500 h-full transition-all duration-500"
                  title={`Completion tokens: ${completionPercent}%`}
                />
              </div>
            </div>
          )}

          {/* Recent API Requests Table */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-indigo-400" />
                Recent Recorded Activity
              </h4>
              <span className="text-[10px] text-slate-500 font-mono">
                Last {stats?.recent_records?.length || 0} events
              </span>
            </div>

            {stats && stats.recent_records && stats.recent_records.length > 0 ? (
              <div className="overflow-x-auto rounded-xl border border-slate-800/80">
                <table className="w-full text-left text-xs text-slate-300 font-mono">
                  <thead className="bg-slate-950/90 text-slate-400 text-[10px] uppercase border-b border-slate-800">
                    <tr>
                      <th className="py-2.5 px-3">Endpoint</th>
                      <th className="py-2.5 px-3">Model</th>
                      <th className="py-2.5 px-3 text-right">Prompt</th>
                      <th className="py-2.5 px-3 text-right">Completion</th>
                      <th className="py-2.5 px-3 text-right">Total</th>
                      <th className="py-2.5 px-3 text-right">Cost (USD)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 bg-slate-950/40">
                    {stats.recent_records.map((r) => (
                      <tr key={r.id} className="hover:bg-slate-900/40 transition-colors">
                        <td className="py-2 px-3 text-indigo-300 font-medium">{r.endpoint}</td>
                        <td className="py-2 px-3 text-slate-400 text-[11px]">{r.model}</td>
                        <td className="py-2 px-3 text-right text-slate-400">{r.prompt_tokens}</td>
                        <td className="py-2 px-3 text-right text-slate-400">{r.completion_tokens}</td>
                        <td className="py-2 px-3 text-right text-slate-200 font-semibold">{r.total_tokens}</td>
                        <td className="py-2 px-3 text-right text-emerald-400 font-semibold">
                          ${r.estimated_cost.toFixed(6)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-6 bg-slate-950/40 rounded-xl border border-slate-800/60 text-center text-xs text-slate-500 italic">
                No API usage logged yet. Send chat queries or upload documents to see live cost tracking.
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="pt-3 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-500 shrink-0">
          <span>Rates: Input ~$0.075 / 1M · Output ~$0.30 / 1M</span>
          <button
            onClick={onClose}
            className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-200 hover:bg-slate-700 text-xs font-medium cursor-pointer transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

export default UsageModal;
