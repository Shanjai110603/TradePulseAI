import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { signalsApi } from '../services/api';
import { Signal } from '../types';
import { Radio, Filter, Eye, ChevronRight, Sparkles, Clock, CheckCircle2, AlertCircle } from 'lucide-react';

export const Signals: React.FC = () => {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [directionFilter, setDirectionFilter] = useState('ALL');
  const [loading, setLoading] = useState(true);

  const loadSignals = async () => {
    try {
      const data = await signalsApi.getSignals({ limit: 100 });
      setSignals(data);
    } catch (e) {
      console.error('Failed to load signals', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSignals();
    const interval = setInterval(loadSignals, 6000);
    return () => clearInterval(interval);
  }, []);

  const filteredSignals = signals.filter((s) => {
    if (statusFilter !== 'ALL' && s.status !== statusFilter) return false;
    if (directionFilter !== 'ALL' && s.direction !== directionFilter) return false;
    return true;
  });

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <Radio className="w-5 h-5 text-emerald-400 animate-pulse" />
            <h1 className="text-xl font-bold text-white tracking-wide">Live Research Signal Stream</h1>
            <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-300 font-mono font-semibold border border-emerald-800">
              {filteredSignals.length} Matches
            </span>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            Real-time verified signal candidates generated from active user patterns and enriched with AI scores.
          </p>
        </div>

        {/* Filter Controls */}
        <div className="flex items-center space-x-3 text-xs font-mono">
          <div className="flex bg-surface-raised rounded-lg p-1 border border-surface-border">
            {['ALL', 'ACTIVE', 'EXPIRED', 'COMPLETED'].map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`px-3 py-1 rounded transition-colors ${
                  statusFilter === st
                    ? 'bg-primary text-black font-bold shadow-glow-cyan'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                {st}
              </button>
            ))}
          </div>

          <div className="flex bg-surface-raised rounded-lg p-1 border border-surface-border">
            {['ALL', 'DOWN', 'UP'].map((dir) => (
              <button
                key={dir}
                onClick={() => setDirectionFilter(dir)}
                className={`px-3 py-1 rounded transition-colors ${
                  directionFilter === dir
                    ? 'bg-surface-border text-white font-bold'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                {dir}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Signals List Cards */}
      <div className="space-y-3">
        {filteredSignals.length === 0 ? (
          <div className="glass-panel p-10 text-center text-gray-500 space-y-2">
            <Radio className="w-8 h-8 mx-auto text-gray-600" />
            <p className="text-sm">No signals matching filter criteria.</p>
          </div>
        ) : (
          filteredSignals.map((sig) => {
            const isDown = sig.direction === 'DOWN' || sig.direction === 'SELL';
            return (
              <div
                key={sig.id}
                className="glass-panel p-4 hover:border-primary/40 transition-all flex flex-col md:flex-row items-start md:items-center justify-between gap-4"
              >
                {/* Left Block */}
                <div className="flex items-center space-x-4">
                  <div
                    className={`w-12 h-12 rounded-xl flex flex-col items-center justify-center font-mono font-bold text-xs border ${
                      isDown
                        ? 'bg-rose-950/60 text-trade-down border-rose-800'
                        : 'bg-emerald-950/60 text-trade-up border-emerald-800'
                    }`}
                  >
                    <span>{isDown ? 'PUT' : 'CALL'}</span>
                    <span className="text-[10px]">{sig.timeframe}</span>
                  </div>

                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="font-bold text-base text-white">{sig.asset_symbol}</span>
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded font-mono ${
                          isDown
                            ? 'bg-rose-500/20 text-trade-down'
                            : 'bg-emerald-500/20 text-trade-up'
                        }`}
                      >
                        {sig.direction}
                      </span>
                      <span className="text-xs text-gray-400 font-mono">• {sig.pattern_name}</span>
                    </div>

                    <div className="flex items-center space-x-4 text-xs font-mono text-gray-400 mt-1">
                      <span>Ref Price: <b className="text-white">{sig.reference_price}</b></span>
                      <span>Entry: <b>{new Date(sig.entry_time).toLocaleTimeString()}</b></span>
                      {sig.duration_minutes && <span>Expiry: <b>{sig.duration_minutes}m</b></span>}
                    </div>
                  </div>
                </div>

                {/* Right Block */}
                <div className="flex items-center space-x-4 w-full md:w-auto justify-between md:justify-end">
                  {/* AI Score Badge */}
                  <div className="text-right">
                    <span className="text-[10px] text-gray-500 font-mono block">AI SCORE</span>
                    <span className="px-2.5 py-1 rounded bg-primary/15 text-primary border border-primary/30 font-bold font-mono text-xs shadow-glow-cyan">
                      {sig.ai_score}/100
                    </span>
                  </div>

                  {/* Status Badge */}
                  <div className="text-right">
                    <span className="text-[10px] text-gray-500 font-mono block">STATUS</span>
                    <span
                      className={`px-2.5 py-1 rounded text-xs font-mono font-semibold ${
                        sig.status === 'ACTIVE'
                          ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                          : 'bg-surface-raised text-gray-400 border border-surface-border'
                      }`}
                    >
                      {sig.status}
                    </span>
                  </div>

                  {/* Details Link */}
                  <Link
                    to={`/signals/${sig.id}`}
                    className="p-2 rounded-lg bg-surface-raised hover:bg-surface-border text-gray-300 hover:text-white transition-colors"
                  >
                    <ChevronRight className="w-5 h-5" />
                  </Link>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
