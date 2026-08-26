import React, { useEffect, useState } from 'react';
import { marketsApi } from '../services/api';
import { Market, Asset } from '../types';
import { Globe, ArrowRight, Layers, CheckCircle2, Shield, Activity } from 'lucide-react';

export const Markets: React.FC = () => {
  const [markets, setMarkets] = useState<Market[]>([]);
  const [selectedMarketId, setSelectedMarketId] = useState<string>('digital_options');
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    marketsApi.getMarkets().then((mList) => {
      setMarkets(mList);
      if (mList.length > 0) {
        setSelectedMarketId(mList[0].id);
      }
    }).catch(console.error).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (selectedMarketId) {
      marketsApi.getAssets(selectedMarketId).then(setAssets).catch(console.error);
    }
  }, [selectedMarketId]);

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <div className="flex items-center space-x-2">
          <Globe className="w-5 h-5 text-primary" />
          <h1 className="text-xl font-bold text-white tracking-wide">Multi-Market Asset Explorer</h1>
        </div>
        <p className="text-xs text-gray-400 mt-1">
          Explore supported market categories, normalized feeds, and asset precision tiers.
        </p>
      </div>

      {/* Market Category Tabs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {markets.map((m) => (
          <button
            key={m.id}
            onClick={() => setSelectedMarketId(m.id)}
            className={`p-4 rounded-xl border text-left transition-all ${
              selectedMarketId === m.id
                ? 'bg-surface-raised border-primary text-white shadow-glow-cyan'
                : 'glass-panel text-gray-400 hover:text-white'
            }`}
          >
            <span className="font-bold text-sm block">{m.name}</span>
            <span className="text-[10px] text-gray-500 uppercase font-mono block mt-1">{m.market_type}</span>
          </button>
        ))}
      </div>

      {/* Assets Grid */}
      <div className="glass-panel p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white font-mono">
            Supported Assets ({assets.length})
          </h2>
          <span className="text-xs text-emerald-400 font-mono flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            Data Provider: Live / Deterministic
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {assets.map((a) => (
            <div key={a.id} className="glass-card p-3.5 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-bold text-sm text-white font-mono">{a.symbol}</span>
                <span className="text-[10px] px-2 py-0.5 rounded bg-surface-border text-gray-300 font-mono">
                  {a.base_asset}/{a.quote_asset}
                </span>
              </div>
              <p className="text-xs text-gray-400">{a.name}</p>
              <div className="pt-2 border-t border-surface-border/50 flex items-center justify-between text-[10px] font-mono text-gray-500">
                <span>Precision: {a.price_precision}d</span>
                <span>Min: {a.min_movement}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
