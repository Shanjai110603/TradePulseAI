import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { patternsApi, signalsApi, telegramApi, performanceApi } from '../services/api';
import { Pattern, Signal, TelegramStatus, PerformanceOverview } from '../types';
import { TradingViewWidget } from '../components/charts/TradingViewWidget';
import { 
  Activity, 
  Layers, 
  Radio, 
  TrendingUp, 
  Zap, 
  ArrowUpRight, 
  ArrowDownRight, 
  Send, 
  Sparkles, 
  Plus, 
  Eye, 
  CheckCircle2, 
  Clock, 
  Percent 
} from 'lucide-react';

export const Dashboard: React.FC = () => {
  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [perfOverview, setPerfOverview] = useState<PerformanceOverview | null>(null);
  const [selectedAsset, setSelectedAsset] = useState('EUR/USD (OTC)');
  const [selectedTimeframe, setSelectedTimeframe] = useState('1M');
  const [tgStatus, setTgStatus] = useState<TelegramStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [pList, sList, tg, perf] = await Promise.all([
          patternsApi.getPatterns(),
          signalsApi.getSignals({ limit: 15 }),
          telegramApi.getStatus().catch(() => null),
          performanceApi.getOverview().catch(() => null),
        ]);
        setPatterns(pList);
        setSignals(sList);
        if (tg) setTgStatus(tg);
        if (perf) setPerfOverview(perf);
      } catch (err) {
        console.error('Error loading dashboard data', err);
      } finally {
        setLoading(false);
      }
    };

    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, []);

  const activePatterns = patterns.filter((p) => p.is_active);
  const activeSignals = signals.filter((s) => s.status === 'ACTIVE');

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Top Stat Banners */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="glass-panel p-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-gray-400 font-mono">ACTIVE SIGNALS</p>
            <p className="text-2xl font-bold text-white mt-1">{activeSignals.length}</p>
            <p className="text-[11px] text-emerald-400 flex items-center gap-1 mt-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
              Live tracking in progress
            </p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shadow-glow-cyan">
            <Radio className="w-6 h-6" />
          </div>
        </div>

        <div className="glass-panel p-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-gray-400 font-mono">ACTIVE PATTERNS</p>
            <p className="text-2xl font-bold text-white mt-1">{activePatterns.length} <span className="text-xs text-gray-500 font-normal">/ {patterns.length}</span></p>
            <p className="text-[11px] text-gray-400 mt-1">Scanning 1M & 5M feeds</p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <Layers className="w-6 h-6" />
          </div>
        </div>

        <div className="glass-panel p-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-gray-400 font-mono">HISTORICAL WIN RATE</p>
            <p className="text-2xl font-bold text-trade-up mt-1">
              {perfOverview ? `${perfOverview.overall_win_rate}%` : '---'}
            </p>
            <p className="text-[11px] text-gray-400 mt-1 truncate max-w-[150px]">
              {perfOverview?.pattern_stats?.[0]?.pattern_name 
                ? `${perfOverview.pattern_stats[0].pattern_name}`
                : 'Verified Signal Outcomes'}
            </p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-trade-up shadow-glow-green">
            <Percent className="w-6 h-6" />
          </div>
        </div>

        <div className="glass-panel p-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-gray-400 font-mono">TELEGRAM BROADCAST</p>
            <p className="text-base font-bold text-white mt-1">
              24/7 ACTIVE
            </p>
            <p className="text-[11px] text-emerald-400 font-medium flex items-center gap-1 mt-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              @{tgStatus?.bot_username || 'TradePulse_101_bot'}
            </p>
          </div>
          <div className="w-12 h-12 rounded-xl border bg-emerald-500/10 border-emerald-500/30 text-emerald-400 flex items-center justify-center shadow-glow-green">
            <Send className="w-6 h-6" />
          </div>
        </div>
      </div>

      {/* Main Center Grid: Interactive Chart + Active Patterns */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Interactive Chart Column (2 spans) */}
        <div className="lg:col-span-2 space-y-3">
          {/* Asset & Timeframe Controls */}
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center space-x-2">
              <Activity className="w-4 h-4 text-primary" />
              <h2 className="text-base font-semibold text-white">Live Quotex OTC Chart</h2>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex bg-surface-raised rounded-lg p-0.5 border border-surface-border">
                {['EUR/USD (OTC)', 'GBP/USD (OTC)', 'USD/JPY (OTC)', 'BTC/USDT (OTC)', 'AUD/CAD (OTC)'].map((sym) => (
                  <button
                    key={sym}
                    onClick={() => setSelectedAsset(sym)}
                    className={`px-2.5 py-1 text-xs font-mono rounded-md transition-colors ${
                      selectedAsset === sym
                        ? 'bg-primary text-black font-semibold'
                        : 'text-gray-400 hover:text-white'
                    }`}
                  >
                    {sym}
                  </button>
                ))}
              </div>
              <div className="flex bg-surface-raised rounded-lg p-0.5 border border-surface-border text-xs font-mono">
                {['1M', '5M', '15M', '1H'].map((tf) => (
                  <button
                    key={tf}
                    onClick={() => setSelectedTimeframe(tf)}
                    className={`px-2.5 py-1 rounded transition-colors ${
                      selectedTimeframe === tf
                        ? 'bg-primary text-black font-bold'
                        : 'text-gray-400 hover:text-white'
                    }`}
                  >
                    {tf}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Real TradingView Live Chart — fills full height */}
          <TradingViewWidget
            symbol={selectedAsset}
            timeframe={selectedTimeframe}
            height={500}
          />
        </div>

        {/* Active Pattern Cards */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-white flex items-center gap-2">
              <Layers className="w-4 h-4 text-indigo-400" />
              Active Patterns ({activePatterns.length})
            </h2>
            <Link
              to="/patterns/new"
              className="text-xs text-primary hover:underline flex items-center gap-1 font-medium"
            >
              <Plus className="w-3.5 h-3.5" />
              Create
            </Link>
          </div>

          <div className="space-y-3 max-h-[480px] overflow-y-auto pr-1">
            {patterns.length === 0 ? (
              <div className="glass-panel p-6 text-center text-gray-400 space-y-3">
                <Layers className="w-8 h-8 text-gray-500 mx-auto" />
                <p className="text-xs">No active patterns found.</p>
                <Link
                  to="/patterns/new"
                  className="inline-block px-3 py-1.5 bg-primary text-black text-xs font-semibold rounded-lg"
                >
                  Build First Pattern
                </Link>
              </div>
            ) : (
              patterns.map((p) => (
                <div
                  key={p.id}
                  className={`glass-panel p-3.5 transition-all ${
                    p.is_active ? 'border-primary/40' : 'opacity-60'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="font-semibold text-sm text-white">{p.name}</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-raised text-gray-400 font-mono">
                          v{p.current_version}
                        </span>
                      </div>
                      <p className="text-xs text-gray-400 mt-1 line-clamp-1">{p.description}</p>
                    </div>

                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded font-mono ${
                        p.direction === 'DOWN' || p.direction === 'SELL'
                          ? 'bg-rose-500/20 text-trade-down border border-rose-500/30'
                          : 'bg-emerald-500/20 text-trade-up border border-emerald-500/30'
                      }`}
                    >
                      {p.direction}
                    </span>
                  </div>

                  <div className="grid grid-cols-3 gap-2 mt-3 pt-2 border-t border-surface-border/60 text-[11px] font-mono">
                    <div>
                      <span className="text-gray-500 block text-[10px]">TIMEFRAME</span>
                      <span className="text-gray-200 font-medium">{p.timeframe}</span>
                    </div>
                    <div>
                      <span className="text-gray-500 block text-[10px]">MIN AI SCORE</span>
                      <span className="text-primary font-medium">{p.ai_config?.min_score || 75}+</span>
                    </div>
                    <div className="text-right">
                      <span className="text-gray-500 block text-[10px]">STATUS</span>
                      <span className={p.is_active ? 'text-emerald-400 font-semibold' : 'text-gray-500'}>
                        {p.is_active ? 'ACTIVE' : 'PAUSED'}
                      </span>
                    </div>
                  </div>

                  <div className="mt-3 flex items-center justify-between pt-2 border-t border-surface-border/40">
                    <Link
                      to={`/patterns/${p.id}/backtest`}
                      className="text-xs text-cyan-400 hover:text-cyan-300 font-mono flex items-center gap-1"
                    >
                      <Sparkles className="w-3.5 h-3.5" />
                      Backtest
                    </Link>
                    <Link
                      to={`/patterns/${p.id}`}
                      className="text-xs text-gray-400 hover:text-white font-mono flex items-center gap-1"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      Inspect
                    </Link>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Bottom Live Signals Stream */}
      <div className="glass-panel p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Radio className="w-4 h-4 text-emerald-400 animate-pulse" />
            <h2 className="text-base font-semibold text-white">Recent Research Signals</h2>
            <span className="text-xs text-gray-500 font-mono">({signals.length} total)</span>
          </div>
          <Link to="/signals" className="text-xs text-primary hover:underline font-medium">
            View All Signals →
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-surface-border text-gray-400">
                <th className="pb-3 font-medium">ASSET</th>
                <th className="pb-3 font-medium">DIRECTION</th>
                <th className="pb-3 font-medium">PATTERN</th>
                <th className="pb-3 font-medium">REF PRICE</th>
                <th className="pb-3 font-medium">ENTRY TIME</th>
                <th className="pb-3 font-medium">AI SCORE</th>
                <th className="pb-3 font-medium">STATUS</th>
                <th className="pb-3 font-medium text-right">ACTION</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border/50">
              {signals.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-6 text-center text-gray-500">
                    No signals generated yet. Background scanner is actively monitoring feeds.
                  </td>
                </tr>
              ) : (
                signals.slice(0, 5).map((sig) => (
                  <tr key={sig.id} className="hover:bg-surface-raised/40 transition-colors">
                    <td className="py-3 font-bold text-white">{sig.asset_symbol}</td>
                    <td className="py-3">
                      <span
                        className={`px-2 py-0.5 rounded font-bold ${
                          sig.direction === 'DOWN' || sig.direction === 'SELL'
                            ? 'bg-rose-500/20 text-trade-down'
                            : 'bg-emerald-500/20 text-trade-up'
                        }`}
                      >
                        {sig.direction}
                      </span>
                    </td>
                    <td className="py-3 text-gray-300">{sig.pattern_name}</td>
                    <td className="py-3 font-semibold text-white">{sig.reference_price}</td>
                    <td className="py-3 text-gray-400">
                      {new Date(sig.entry_time).toLocaleTimeString()}
                    </td>
                    <td className="py-3">
                      <span className="px-2 py-0.5 rounded bg-primary/10 text-primary border border-primary/20 font-bold">
                        {sig.ai_score}/100
                      </span>
                    </td>
                    <td className="py-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                          sig.status === 'ACTIVE'
                            ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                            : 'bg-surface-raised text-gray-400'
                        }`}
                      >
                        {sig.status}
                      </span>
                    </td>
                    <td className="py-3 text-right">
                      <Link
                        to={`/signals/${sig.id}`}
                        className="px-2.5 py-1 rounded bg-surface-raised hover:bg-surface-border text-gray-200 hover:text-white transition-colors"
                      >
                        Details
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
