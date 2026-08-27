import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { patternsApi } from '../services/api';
import { Pattern } from '../types';
import { ArrowLeft, Sparkles, Layers, Clock, Cpu, Activity, ImageIcon } from 'lucide-react';

export const PatternDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [pattern, setPattern] = useState<Pattern | null>(null);
  const [versions, setVersions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (id) {
      Promise.all([
        patternsApi.getPattern(id),
        patternsApi.getVersions(id).catch(() => []),
      ]).then(([p, v]) => {
        setPattern(p);
        setVersions(v);
      }).catch(console.error).finally(() => setLoading(false));
    }
  }, [id]);

  if (loading || !pattern) {
    return <div className="p-10 text-center text-gray-400 font-mono">Loading pattern specifications...</div>;
  }

  const isDown = pattern.direction === 'DOWN' || pattern.direction === 'SELL';
  const primaryImage = pattern.images && pattern.images.length > 0 ? pattern.images[0] : null;

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">
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
            <div className="flex items-center space-x-3">
              <h1 className="text-xl font-bold text-white tracking-wide">{pattern.name}</h1>
              <span className="text-xs px-2 py-0.5 rounded bg-primary/20 text-primary font-mono font-semibold border border-primary/30">
                v{pattern.current_version}
              </span>
              <span
                className={`text-xs font-bold px-2 py-0.5 rounded font-mono ${
                  isDown ? 'bg-rose-500/20 text-trade-down' : 'bg-emerald-500/20 text-trade-up'
                }`}
              >
                {pattern.direction}
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-1">{pattern.description}</p>
          </div>
        </div>

        <Link
          to={`/patterns/${pattern.id}/backtest`}
          className="flex items-center space-x-1.5 px-4 py-2 bg-primary hover:bg-primary-hover text-black rounded-xl text-xs font-mono font-bold shadow-glow-cyan"
        >
          <Sparkles className="w-4 h-4" />
          <span>Launch Backtest</span>
        </Link>
      </div>

      {/* Grid: Visual Reference + Rule Specifications */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Visual Reference Image */}
        <div className="glass-panel p-5 space-y-3">
          <h2 className="text-sm font-semibold text-white font-mono flex items-center gap-2">
            <ImageIcon className="w-4 h-4 text-primary" />
            Visual Reference Image
          </h2>
          <div className="h-64 rounded-xl bg-surface-raised/60 border border-surface-border/80 flex items-center justify-center overflow-hidden">
            {primaryImage ? (
              <img
                src={primaryImage.file_path}
                alt={pattern.name}
                className="w-full h-full object-contain"
              />
            ) : (
              <p className="text-xs text-gray-500 font-mono">No reference image uploaded</p>
            )}
          </div>
          <p className="text-[11px] text-gray-400 font-mono">
            Note: The image is your visual reference guide. The code evaluates the parameters on the right deterministically.
          </p>
        </div>

        {/* Deterministic Rule Engine AST Specifications */}
        <div className="glass-panel p-5 space-y-4">
          <h2 className="text-sm font-semibold text-white font-mono flex items-center gap-2">
            <Cpu className="w-4 h-4 text-cyan-400" />
            Machine-Readable Strategy Rules
          </h2>

          <div className="space-y-3 text-xs font-mono">
            <div className="bg-surface-raised p-3 rounded-lg border border-surface-border/60">
              <span className="text-gray-500 block text-[10px]">MARKET & ASSETS</span>
              <span className="text-white font-bold">{pattern.market_id.toUpperCase()}</span>
              <span className="text-gray-300 block mt-0.5">Assets: {pattern.assets_config?.join(', ') || 'EUR/USD'}</span>
            </div>

            <div className="bg-surface-raised p-3 rounded-lg border border-surface-border/60">
              <span className="text-gray-500 block text-[10px]">CANDLESTICK & S/R SEQUENCE (AST)</span>
              <pre className="text-[11px] text-cyan-300 mt-1 overflow-x-auto">
                {JSON.stringify(pattern.rules_config, null, 2)}
              </pre>
            </div>

            <div className="bg-surface-raised p-3 rounded-lg border border-surface-border/60">
              <span className="text-gray-500 block text-[10px]">AI CONFIRMATION FILTER</span>
              <span className="text-primary font-bold">Min Score: {pattern.ai_config?.min_score || 70}/100</span>
              <span className="text-gray-400 block text-[11px]">Required Bias: {pattern.ai_config?.required_bias || 'ANY'}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Version History Table */}
      <div className="glass-panel p-5 space-y-3">
        <h2 className="text-sm font-semibold text-white font-mono flex items-center gap-2">
          <Clock className="w-4 h-4 text-indigo-400" />
          Version Audit History
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-surface-border text-gray-400">
                <th className="pb-2">VERSION</th>
                <th className="pb-2">SUMMARY</th>
                <th className="pb-2 text-right">TIMESTAMP</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border/40">
              {versions.map((v) => (
                <tr key={v.id}>
                  <td className="py-2.5 text-primary font-bold">v{v.version_number}</td>
                  <td className="py-2.5 text-gray-300">{v.change_summary || 'Configuration update'}</td>
                  <td className="py-2.5 text-right text-gray-400">{new Date(v.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
