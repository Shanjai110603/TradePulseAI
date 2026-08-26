import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { patternsApi } from '../services/api';
import { Pattern } from '../types';
import { 
  Layers, 
  Plus, 
  Sparkles, 
  Copy, 
  Edit, 
  Trash2, 
  Power, 
  Eye, 
  ImageIcon, 
  CheckCircle, 
  TrendingDown, 
  TrendingUp, 
  Sliders 
} from 'lucide-react';

export const Patterns: React.FC = () => {
  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [loading, setLoading] = useState(true);

  const loadPatterns = async () => {
    try {
      const list = await patternsApi.getPatterns();
      setPatterns(list);
    } catch (err) {
      console.error('Failed to load patterns', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPatterns();
  }, []);

  const handleToggle = async (id: string) => {
    try {
      await patternsApi.togglePattern(id);
      await loadPatterns();
    } catch (e) {
      console.error(e);
    }
  };

  const handleDuplicate = async (id: string) => {
    try {
      await patternsApi.duplicatePattern(id);
      await loadPatterns();
    } catch (e) {
      console.error(e);
    }
  };

  const handleDelete = async (id: string) => {
    if (window.confirm('Are you sure you want to delete this pattern?')) {
      try {
        await patternsApi.deletePattern(id);
        await loadPatterns();
      } catch (e) {
        console.error(e);
      }
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-xl font-bold text-white tracking-wide">Personal Pattern Library</h1>
            <span className="text-xs px-2 py-0.5 rounded-full bg-primary/20 text-primary font-mono font-semibold border border-primary/30">
              {patterns.length} Strategies
            </span>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            Build, test, backtest, and configure deterministic rule sets with AI confirmation filters.
          </p>
        </div>

        <Link
          to="/patterns/new"
          className="flex items-center space-x-2 px-4 py-2.5 bg-primary hover:bg-primary-hover text-black rounded-xl font-semibold text-xs transition-all shadow-glow-cyan"
        >
          <Plus className="w-4 h-4" />
          <span>Create New Pattern</span>
        </Link>
      </div>

      {/* Grid of Pattern Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {patterns.map((p) => {
          const primaryImage = p.images && p.images.length > 0 ? p.images[0] : null;
          const isDown = p.direction === 'DOWN' || p.direction === 'SELL';

          return (
            <div
              key={p.id}
              className={`glass-panel overflow-hidden transition-all flex flex-col justify-between ${
                p.is_active ? 'border-surface-border hover:border-primary/50' : 'opacity-70'
              }`}
            >
              {/* Pattern Visual Reference Area */}
              <div className="relative h-44 bg-surface-raised/80 border-b border-surface-border/60 flex items-center justify-center overflow-hidden group">
                {primaryImage ? (
                  <img
                    src={`http://localhost:8000${primaryImage.file_path}`}
                    alt={p.name}
                    className="w-full h-full object-cover transition-transform group-hover:scale-105"
                    onError={(e) => {
                      // Fallback if local image not found
                      e.currentTarget.style.display = 'none';
                    }}
                  />
                ) : (
                  <div className="flex flex-col items-center space-y-2 text-gray-500">
                    <ImageIcon className="w-10 h-10 text-gray-600" />
                    <span className="text-[11px] font-mono">No reference image uploaded</span>
                  </div>
                )}

                {/* Badges Over Image */}
                <div className="absolute top-3 left-3 flex items-center space-x-2">
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded font-mono shadow-md ${
                      isDown
                        ? 'bg-rose-950/90 text-trade-down border border-rose-800'
                        : 'bg-emerald-950/90 text-trade-up border border-emerald-800'
                    }`}
                  >
                    {p.direction}
                  </span>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-surface/90 text-gray-300 font-mono border border-surface-border">
                    {p.timeframe}
                  </span>
                </div>

                <div className="absolute top-3 right-3">
                  <button
                    onClick={() => handleToggle(p.id)}
                    className={`p-1.5 rounded-lg border backdrop-blur-md transition-colors ${
                      p.is_active
                        ? 'bg-emerald-950/80 text-emerald-400 border-emerald-700/60'
                        : 'bg-surface-raised/80 text-gray-500 border-surface-border'
                    }`}
                    title={p.is_active ? 'Pattern Active (Click to Pause)' : 'Pattern Paused (Click to Activate)'}
                  >
                    <Power className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Card Body */}
              <div className="p-4 space-y-3 flex-1 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between">
                    <h3 className="font-bold text-sm text-white tracking-wide">{p.name}</h3>
                    <span className="text-[10px] text-gray-400 font-mono">v{p.current_version}</span>
                  </div>
                  <p className="text-xs text-gray-400 mt-1 line-clamp-2 leading-relaxed">
                    {p.description || 'Custom configured deterministic pattern logic.'}
                  </p>
                </div>

                {/* Configuration Specs Matrix */}
                <div className="grid grid-cols-3 gap-2 bg-surface-raised/50 p-2.5 rounded-lg border border-surface-border/40 text-[10px] font-mono">
                  <div>
                    <span className="text-gray-500 block">MARKET</span>
                    <span className="text-gray-200 uppercase font-semibold">{p.market_id.replace('_', ' ')}</span>
                  </div>
                  <div>
                    <span className="text-gray-500 block">MIN AI SCORE</span>
                    <span className="text-primary font-semibold">{p.ai_config?.min_score || 70}/100</span>
                  </div>
                  <div>
                    <span className="text-gray-500 block">TREND REQ</span>
                    <span className="text-gray-200 font-semibold">{p.trend_config?.required || 'Any'}</span>
                  </div>
                </div>

                {/* Card Action Controls */}
                <div className="pt-2 border-t border-surface-border/60 flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Link
                      to={`/patterns/${p.id}/backtest`}
                      className="flex items-center space-x-1 px-2.5 py-1 rounded-md bg-cyan-950/40 hover:bg-cyan-900/60 text-cyan-300 border border-cyan-800/60 text-xs font-mono transition-colors"
                    >
                      <Sparkles className="w-3 h-3" />
                      <span>Backtest</span>
                    </Link>
                    <Link
                      to={`/patterns/${p.id}`}
                      className="p-1 rounded hover:bg-surface-border text-gray-400 hover:text-white transition-colors"
                      title="Inspect Rules"
                    >
                      <Eye className="w-4 h-4" />
                    </Link>
                  </div>

                  <div className="flex items-center space-x-1">
                    <button
                      onClick={() => handleDuplicate(p.id)}
                      className="p-1.5 rounded hover:bg-surface-border text-gray-400 hover:text-white transition-colors"
                      title="Duplicate Pattern"
                    >
                      <Copy className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => handleDelete(p.id)}
                      className="p-1.5 rounded hover:bg-rose-950/60 text-gray-400 hover:text-rose-400 transition-colors"
                      title="Delete Pattern"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
