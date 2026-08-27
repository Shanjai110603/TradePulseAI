import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { patternsApi, backtestsApi, marketsApi } from '../services/api';
import { Pattern, BacktestResult, Candle } from '../types';
import { TradingViewChart } from '../components/charts/TradingViewChart';
import { 
  Sparkles, 
  Play, 
  TrendingUp, 
  TrendingDown, 
  BarChart2, 
  ArrowLeft, 
  Percent, 
  Award, 
  AlertTriangle, 
  Layers 
} from 'lucide-react';

export const PatternBacktest: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [pattern, setPattern] = useState<Pattern | null>(null);
  const [candles, setCandles] = useState<Candle[]>([]);
  const [candleCount, setCandleCount] = useState(250);
  const [selectedAsset, setSelectedAsset] = useState('EUR/USD');
  const [selectedTimeframe, setSelectedTimeframe] = useState('1M');
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    if (id) {
      patternsApi.getPattern(id).then((p) => {
        setPattern(p);
        if (p.assets_config && p.assets_config.length > 0) {
          setSelectedAsset(p.assets_config[0]);
        }
        if (p.timeframe) {
          setSelectedTimeframe(p.timeframe);
        }
      }).catch(console.error);
    }
  }, [id]);

  useEffect(() => {
    marketsApi.getCandles(selectedAsset, selectedTimeframe, candleCount).then(setCandles).catch(console.error);
  }, [selectedAsset, selectedTimeframe, candleCount]);

  const handleRunBacktest = async () => {
    if (!pattern) return;
    setRunning(true);
    try {
      const res = await backtestsApi.runBacktest({
        pattern_id: pattern.id,
        market_id: pattern.market_id,
        asset_symbol: selectedAsset,
        timeframe: selectedTimeframe,
        candle_count: candleCount
      });
      setBacktestResult(res);
    } catch (e) {
      console.error('Failed to run backtest', e);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Link
            to="/patterns"
            className="p-2 rounded-lg bg-surface-raised hover:bg-surface-border text-gray-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold text-white tracking-wide">Backtesting Terminal</h1>
              <span className="text-xs px-2 py-0.5 rounded bg-primary/20 text-primary font-mono font-semibold border border-primary/30">
                {pattern?.name || 'Pattern'}
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-0.5">
              Replay historical candles in strict chronological order with zero look-ahead bias.
            </p>
          </div>
        </div>

        <button
          disabled={running}
          onClick={handleRunBacktest}
          className="flex items-center space-x-2 px-5 py-2.5 bg-primary hover:bg-primary-hover text-black rounded-xl font-bold text-xs transition-all shadow-glow-cyan disabled:opacity-50"
        >
          <Play className="w-4 h-4 fill-current" />
          <span>{running ? 'Replaying Candles...' : 'Execute Backtest'}</span>
        </button>
      </div>

      {/* Control Bar */}
      <div className="glass-panel p-4 flex flex-wrap items-center justify-between gap-4 text-xs font-mono">
        <div className="flex items-center space-x-4">
          <div className="space-y-1">
            <span className="text-gray-500 block text-[10px]">ASSET PAIR</span>
            <select
              value={selectedAsset}
              onChange={(e) => setSelectedAsset(e.target.value)}
              className="bg-surface-raised border border-surface-border rounded-md px-3 py-1.5 text-white outline-none"
            >
              {['EUR/USD', 'GBP/USD', 'USD/JPY', 'BTC/USDT', 'ETH/USDT'].map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>

          <div className="space-y-1">
            <span className="text-gray-500 block text-[10px]">TIMEFRAME</span>
            <select
              value={selectedTimeframe}
              onChange={(e) => setSelectedTimeframe(e.target.value)}
              className="bg-surface-raised border border-surface-border rounded-md px-3 py-1.5 text-white outline-none"
            >
              {['1M', '5M', '15M', '1H'].map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>

          <div className="space-y-1">
            <span className="text-gray-500 block text-[10px]">REPLAY CANDLE DEPTH</span>
            <select
              value={candleCount}
              onChange={(e) => setCandleCount(Number(e.target.value))}
              className="bg-surface-raised border border-surface-border rounded-md px-3 py-1.5 text-white outline-none"
            >
              <option value={100}>100 Candles</option>
              <option value={250}>250 Candles</option>
              <option value={500}>500 Candles</option>
            </select>
          </div>
        </div>

        <div className="flex items-center space-x-3 text-right">
          <div>
            <span className="text-gray-500 block text-[10px]">SIMULATOR ENGINE</span>
            <span className="text-emerald-400 font-semibold">EVENT-DRIVEN O(N)</span>
          </div>
        </div>
      </div>

      {/* Results Overview if available */}
      {backtestResult && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 animate-in fade-in duration-200">
          <div className="glass-panel p-4">
            <span className="text-xs text-gray-500 font-mono block">WIN RATE</span>
            <p className="text-2xl font-bold text-trade-up mt-1">
              {backtestResult.win_rate_percentage}%
            </p>
            <span className="text-[11px] text-gray-400">
              {backtestResult.winning_signals} Wins / {backtestResult.losing_signals} Losses
            </span>
          </div>

          <div className="glass-panel p-4">
            <span className="text-xs text-gray-500 font-mono block">TOTAL SIGNALS</span>
            <p className="text-2xl font-bold text-white mt-1">
              {backtestResult.total_signals}
            </p>
            <span className="text-[11px] text-gray-400">
              Over {backtestResult.candle_count} candles
            </span>
          </div>

          <div className="glass-panel p-4">
            <span className="text-xs text-gray-500 font-mono block">PROFIT FACTOR</span>
            <p className="text-2xl font-bold text-cyan-400 mt-1">
              {backtestResult.profit_factor != null ? backtestResult.profit_factor.toFixed(2) : 'N/A'}
            </p>
            <span className="text-[11px] text-gray-400">Gross Gain / Loss Ratio</span>
          </div>

          <div className="glass-panel p-4">
            <span className="text-xs text-gray-500 font-mono block">MAX DRAWDOWN</span>
            <p className="text-2xl font-bold text-trade-down mt-1">
              {backtestResult.max_drawdown_percentage != null ? `${backtestResult.max_drawdown_percentage.toFixed(2)}%` : '0.00%'}
            </p>
            <span className="text-[11px] text-gray-400">Peak-to-valley variance</span>
          </div>
        </div>
      )}

      {/* Candlestick Visualization */}
      <div className="space-y-2">
        <h2 className="text-sm font-semibold text-white flex items-center gap-2">
          <BarChart2 className="w-4 h-4 text-primary" />
          Candlestick Timeline Replay
        </h2>
        <TradingViewChart
          candles={candles}
          symbol={selectedAsset}
          timeframe={selectedTimeframe}
          height={440}
        />
      </div>

      {/* Trade Log Table */}
      {backtestResult && backtestResult.signals_log && (
        <div className="glass-panel p-5 space-y-3">
          <h2 className="text-sm font-semibold text-white">Chronological Signal Execution Log</h2>
          <div className="overflow-x-auto max-h-80">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-surface-border text-gray-400">
                  <th className="pb-2">#</th>
                  <th className="pb-2">ENTRY TIME</th>
                  <th className="pb-2">ENTRY PRICE</th>
                  <th className="pb-2">EXIT TIME</th>
                  <th className="pb-2">EXIT PRICE</th>
                  <th className="pb-2">OUTCOME</th>
                  <th className="pb-2 text-right">PNL</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border/40">
                {backtestResult.signals_log.map((t, idx) => (
                  <tr key={idx} className="hover:bg-surface-raised/50 transition-colors">
                    <td className="py-2.5 text-gray-500">{t.trade_number}</td>
                    <td className="py-2.5 text-gray-300">{new Date(t.entry_time).toLocaleTimeString()}</td>
                    <td className="py-2.5 text-white font-semibold">{t.entry_price}</td>
                    <td className="py-2.5 text-gray-300">{new Date(t.exit_time).toLocaleTimeString()}</td>
                    <td className="py-2.5 text-white font-semibold">{t.exit_price}</td>
                    <td className="py-2.5">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          t.outcome === 'WIN'
                            ? 'bg-emerald-950 text-trade-up border border-emerald-800'
                            : 'bg-rose-950 text-trade-down border border-rose-800'
                        }`}
                      >
                        {t.outcome}
                      </span>
                    </td>
                    <td
                      className={`py-2.5 text-right font-bold ${
                        t.pnl_amount >= 0 ? 'text-trade-up' : 'text-trade-down'
                      }`}
                    >
                      {t.pnl_amount >= 0 ? `+$${t.pnl_amount.toFixed(2)}` : `-$${Math.abs(t.pnl_amount).toFixed(2)}`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
