import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { signalsApi } from '../services/api';
import { Signal } from '../types';
import { TradingViewWidget } from '../components/charts/TradingViewWidget';
import { 
  ArrowLeft, 
  Sparkles, 
  Activity, 
  ShieldAlert, 
  Clock, 
  CheckCircle2, 
  Send, 
  Layers, 
  Cpu 
} from 'lucide-react';

export const SignalDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [signal, setSignal] = useState<Signal | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (id) {
      signalsApi.getSignal(id).then((sig) => {
        setSignal(sig);
      }).catch(console.error).finally(() => setLoading(false));
    }
  }, [id]);

  if (loading || !signal) {
    return <div className="p-10 text-center text-gray-400 font-mono">Loading signal research profile...</div>;
  }

  const isDown = signal.direction === 'DOWN' || signal.direction === 'SELL';
  const ai = signal.ai_analysis;
  const tech = signal.technical_snapshot;

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Link
            to="/signals"
            className="p-2 rounded-lg bg-surface-raised hover:bg-surface-border text-gray-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <div className="flex items-center space-x-3">
              <h1 className="text-xl font-bold text-white tracking-wide">{signal.asset_symbol} Research Signal</h1>
              <span
                className={`text-xs font-bold px-2.5 py-0.5 rounded font-mono ${
                  isDown
                    ? 'bg-rose-500/20 text-trade-down border border-rose-500/30'
                    : 'bg-emerald-500/20 text-trade-up border border-emerald-500/30'
                }`}
              >
                {signal.direction}
              </span>
              <span className="text-xs px-2 py-0.5 rounded bg-surface-raised text-gray-300 font-mono">
                {signal.timeframe}
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-1 font-mono">
              Signal ID: {signal.id} • Triggered by: <b className="text-white">{signal.pattern_name} (v{signal.pattern_version})</b>
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <span className="text-xs text-gray-500 font-mono">STATUS:</span>
          <span
            className={`px-3 py-1 rounded text-xs font-mono font-bold ${
              signal.status === 'ACTIVE'
                ? 'bg-emerald-950 text-emerald-300 border border-emerald-800 animate-pulse'
                : 'bg-surface-raised text-gray-300'
            }`}
          >
            {signal.status}
          </span>
        </div>
      </div>

      {/* Main Grid: Chart + AI Card */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Candlestick Chart */}
        <div className="lg:col-span-2 space-y-4">
          <TradingViewWidget
            symbol={signal.asset_symbol}
            timeframe={signal.timeframe}
            height={460}
          />

          {/* Pricing Metrics Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono">
            <div className="glass-card p-3">
              <span className="text-gray-500 block text-[10px]">REFERENCE PRICE</span>
              <span className="text-white font-bold text-sm">{signal.reference_price}</span>
            </div>
            <div className="glass-card p-3">
              <span className="text-gray-500 block text-[10px]">ENTRY TIME</span>
              <span className="text-gray-200 font-medium">{new Date(signal.entry_time).toLocaleTimeString()}</span>
            </div>
            <div className="glass-card p-3">
              <span className="text-gray-500 block text-[10px]">EXPIRY DURATION</span>
              <span className="text-gray-200 font-medium">{signal.duration_minutes ? `${signal.duration_minutes} Mins` : 'N/A'}</span>
            </div>
            <div className="glass-card p-3">
              <span className="text-gray-500 block text-[10px]">SIGNAL STRENGTH</span>
              <span className="text-emerald-400 font-bold">{signal.signal_strength}</span>
            </div>
          </div>
        </div>

        {/* AI Quantitative Analysis Panel */}
        <div className="space-y-4">
          <div className="glass-panel p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-surface-border/80 pb-3">
              <div className="flex items-center space-x-2">
                <Cpu className="w-5 h-5 text-primary" />
                <h2 className="font-bold text-sm text-white">AI Research Assessment</h2>
              </div>
              <span className="text-xs px-2.5 py-1 rounded bg-primary/20 text-primary font-mono font-bold border border-primary/30 shadow-glow-cyan">
                {signal.ai_score}/100
              </span>
            </div>

            {ai ? (
              <div className="space-y-3 text-xs font-mono">
                <div>
                  <span className="text-gray-500 block text-[10px]">AI BIAS & CONFIDENCE</span>
                  <span className="text-white font-semibold">{ai.bias} ({ai.confidence} Confidence)</span>
                </div>

                <div>
                  <span className="text-gray-500 block text-[10px]">STRUCTURAL ASSESSMENT</span>
                  <p className="text-gray-300 text-[11px] leading-relaxed">{ai.structure_assessment}</p>
                </div>

                <div>
                  <span className="text-gray-500 block text-[10px]">AI REASONING</span>
                  <p className="text-gray-300 text-[11px] leading-relaxed bg-surface-raised/60 p-2.5 rounded border border-surface-border/40">
                    {ai.reasoning}
                  </p>
                </div>

                {ai.risks && ai.risks.length > 0 && (
                  <div>
                    <span className="text-rose-400 block text-[10px] flex items-center gap-1">
                      <ShieldAlert className="w-3 h-3" />
                      KEY RISKS
                    </span>
                    <ul className="list-disc list-inside text-[11px] text-gray-400 space-y-0.5 mt-1">
                      {ai.risks.map((r: string, idx: number) => (
                        <li key={idx}>{r}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-xs text-gray-500 font-mono">AI analysis snapshot loading...</p>
            )}
          </div>

          {/* Technical Indicator Snapshot Matrix */}
          {tech && (
            <div className="glass-panel p-4 space-y-2 text-xs font-mono">
              <h3 className="font-semibold text-gray-300 text-xs flex items-center gap-1.5 mb-2">
                <Activity className="w-4 h-4 text-emerald-400" />
                Technical Confluence Matrix
              </h3>
              <div className="grid grid-cols-2 gap-2 text-[11px]">
                <div className="bg-surface-raised p-2 rounded">
                  <span className="text-gray-500 block text-[10px]">RSI (14)</span>
                  <span className="text-white font-semibold">{tech.rsi || 'N/A'}</span>
                </div>
                <div className="bg-surface-raised p-2 rounded">
                  <span className="text-gray-500 block text-[10px]">VOLUME RATIO</span>
                  <span className="text-primary font-semibold">{tech.volume_ratio}x 20SMA</span>
                </div>
                <div className="bg-surface-raised p-2 rounded">
                  <span className="text-gray-500 block text-[10px]">EMA FAST (9)</span>
                  <span className="text-white">{tech.ema_fast || 'N/A'}</span>
                </div>
                <div className="bg-surface-raised p-2 rounded">
                  <span className="text-gray-500 block text-[10px]">EMA SLOW (21)</span>
                  <span className="text-white">{tech.ema_slow || 'N/A'}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
