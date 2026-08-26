import React, { useEffect, useState } from 'react';
import { adminApi } from '../services/api';
import { Shield, Activity, Database, Server, Radio, Cpu, Send } from 'lucide-react';

export const Admin: React.FC = () => {
  const [health, setHealth] = useState<any>(null);
  const [metrics, setMetrics] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    try {
      const [h, m] = await Promise.all([
        adminApi.getHealth(),
        adminApi.getMetrics().catch(() => null),
      ]);
      setHealth(h);
      setMetrics(m);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, []);

  if (loading || !health) {
    return <div className="p-10 text-center text-gray-400 font-mono">Loading system diagnostic telemetry...</div>;
  }

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <div className="flex items-center space-x-2">
          <Shield className="w-5 h-5 text-emerald-400" />
          <h1 className="text-xl font-bold text-white tracking-wide">System Health & Diagnostic Monitor</h1>
        </div>
        <p className="text-xs text-gray-400 mt-1">
          Real-time telemetry for background workers, data feeds, AI providers, and database latency.
        </p>
      </div>

      {/* Subsystem Telemetry Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-xs font-mono">
        <div className="glass-panel p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-gray-400 font-semibold flex items-center gap-1.5">
              <Database className="w-4 h-4 text-primary" />
              DATABASE
            </span>
            <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 font-bold border border-emerald-800">
              {health.database.status.toUpperCase()}
            </span>
          </div>
          <p className="text-[11px] text-gray-400">Driver: {health.database.url_type.toUpperCase()}</p>
        </div>

        <div className="glass-panel p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-gray-400 font-semibold flex items-center gap-1.5">
              <Radio className="w-4 h-4 text-cyan-400" />
              MARKET FEED
            </span>
            <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 font-bold border border-emerald-800">
              ACTIVE
            </span>
          </div>
          <p className="text-[11px] text-gray-400">Provider: {health.market_data_provider.active_provider.toUpperCase()}</p>
        </div>

        <div className="glass-panel p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-gray-400 font-semibold flex items-center gap-1.5">
              <Cpu className="w-4 h-4 text-indigo-400" />
              AI LAYER
            </span>
            <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 font-bold border border-emerald-800">
              {health.ai_provider.status.toUpperCase()}
            </span>
          </div>
          <p className="text-[11px] text-gray-400">Provider: {health.ai_provider.active_provider.toUpperCase()}</p>
        </div>

        <div className="glass-panel p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-gray-400 font-semibold flex items-center gap-1.5">
              <Send className="w-4 h-4 text-sky-400" />
              TELEGRAM BOT
            </span>
            <span className="px-2 py-0.5 rounded bg-surface-raised text-gray-300 font-bold border border-surface-border">
              {health.telegram.test_mode ? 'TEST MODE' : 'LIVE'}
            </span>
          </div>
          <p className="text-[11px] text-gray-400">Dispatcher: READY</p>
        </div>
      </div>

      {/* Process & Worker Status */}
      <div className="glass-panel p-5 space-y-4">
        <h2 className="text-sm font-semibold text-white font-mono flex items-center gap-2">
          <Server className="w-4 h-4 text-primary" />
          Background Asynchronous Workers
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
          <div className="glass-card p-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-white font-bold">Deterministic Pattern Evaluator</span>
              <span className="text-emerald-400 font-semibold">RUNNING (10s interval)</span>
            </div>
            <p className="text-gray-400 text-[11px]">
              Scans active user patterns across multi-timeframe candlestick feeds.
            </p>
          </div>

          <div className="glass-card p-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-white font-bold">Signal Lifecycle & Expiry Tracker</span>
              <span className="text-emerald-400 font-semibold">RUNNING (Continuous)</span>
            </div>
            <p className="text-gray-400 text-[11px]">
              Monitors active signals against live ticks and resolves outcome completions.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
