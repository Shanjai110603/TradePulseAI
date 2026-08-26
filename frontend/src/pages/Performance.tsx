import React, { useEffect, useState } from 'react';
import { performanceApi } from '../services/api';
import { PerformanceOverview } from '../types';
import { BarChart3, TrendingUp, Award, Zap, Percent, PieChart, ShieldCheck } from 'lucide-react';

export const Performance: React.FC = () => {
  const [data, setData] = useState<PerformanceOverview | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    performanceApi.getOverview().then(setData).catch(console.error).finally(() => setLoading(false));
  }, []);

  if (loading || !data) {
    return <div className="p-10 text-center text-gray-400 font-mono">Loading performance analytics...</div>;
  }

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <div className="flex items-center space-x-2">
          <BarChart3 className="w-5 h-5 text-primary" />
          <h1 className="text-xl font-bold text-white tracking-wide">Performance & Alpha Analytics</h1>
        </div>
        <p className="text-xs text-gray-400 mt-1">
          Quantitative auditing and win-rate correlations distinguishing backtests vs live research signal outcomes.
        </p>
      </div>

      {/* Overview Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="glass-panel p-4">
          <span className="text-xs text-gray-500 font-mono block">ALL-TIME WIN RATE</span>
          <p className="text-3xl font-bold text-trade-up mt-1">{data.overall_win_rate}%</p>
          <span className="text-[11px] text-gray-400">Calculated over {data.total_signals_all_time} verified setups</span>
        </div>

        <div className="glass-panel p-4">
          <span className="text-xs text-gray-500 font-mono block">DIGITAL OPTIONS RATE</span>
          <p className="text-3xl font-bold text-cyan-400 mt-1">{data.digital_options_win_rate}%</p>
          <span className="text-[11px] text-gray-400">Fixed-time duration signals</span>
        </div>

        <div className="glass-panel p-4">
          <span className="text-xs text-gray-500 font-mono block">STANDARD MARKETS RATE</span>
          <p className="text-3xl font-bold text-indigo-400 mt-1">{data.standard_markets_win_rate}%</p>
          <span className="text-[11px] text-gray-400">TP/SL Risk-Reward models</span>
        </div>
      </div>

      {/* AI Score vs Win Rate Correlation */}
      <div className="glass-panel p-5 space-y-4">
        <h2 className="text-sm font-semibold text-white font-mono flex items-center gap-2">
          <Award className="w-4 h-4 text-primary" />
          AI Score vs. Win-Rate Correlation Curve
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          {data.ai_correlation.map((c) => (
            <div key={c.score_bucket} className="glass-card p-3.5 space-y-1">
              <span className="text-[10px] text-gray-500 font-mono block">AI SCORE {c.score_bucket}</span>
              <p className="text-xl font-bold text-white font-mono">{c.win_rate}%</p>
              <span className="text-[11px] text-gray-400 font-mono">{c.total_signals} Verified Signals</span>
            </div>
          ))}
        </div>
      </div>

      {/* Pattern Breakdown Table */}
      <div className="glass-panel p-5 space-y-4">
        <h2 className="text-sm font-semibold text-white font-mono">Individual Strategy Performance</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-surface-border text-gray-400">
                <th className="pb-3">STRATEGY</th>
                <th className="pb-3">TOTAL SIGNALS</th>
                <th className="pb-3">WINS</th>
                <th className="pb-3">LOSSES</th>
                <th className="pb-3">WIN RATE</th>
                <th className="pb-3">BEST ASSET</th>
                <th className="pb-3 text-right">AVG AI SCORE</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border/50">
              {data.pattern_stats.map((p) => (
                <tr key={p.pattern_id} className="hover:bg-surface-raised/40">
                  <td className="py-3 font-bold text-white">{p.pattern_name}</td>
                  <td className="py-3 text-gray-300">{p.total_signals}</td>
                  <td className="py-3 text-trade-up font-semibold">{p.wins}</td>
                  <td className="py-3 text-trade-down font-semibold">{p.losses}</td>
                  <td className="py-3 text-trade-up font-bold">{p.win_rate}%</td>
                  <td className="py-3 text-cyan-300">{p.best_asset} ({p.best_timeframe})</td>
                  <td className="py-3 text-right text-primary font-semibold">{p.average_ai_score}/100</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
