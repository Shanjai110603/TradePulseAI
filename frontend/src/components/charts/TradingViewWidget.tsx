import React, { useEffect, useRef } from 'react';

declare global {
  interface Window {
    TradingView: any;
  }
}

interface TradingViewWidgetProps {
  symbol?: string;
  timeframe?: string;
  height?: number;
}

const SYMBOL_MAP: Record<string, string> = {
  'EUR/USD (OTC)': 'FX:EURUSD',
  'GBP/USD (OTC)': 'FX:GBPUSD',
  'USD/JPY (OTC)': 'FX:USDJPY',
  'BTC/USDT (OTC)': 'BINANCE:BTCUSDT',
  'AUD/CAD (OTC)': 'FX:AUDCAD',
  'EUR/USD': 'FX:EURUSD',
  'GBP/USD': 'FX:GBPUSD',
  'USD/JPY': 'FX:USDJPY',
  'BTC/USDT': 'BINANCE:BTCUSDT',
  'AUD/CAD': 'FX:AUDCAD',
};

const INTERVAL_MAP: Record<string, string> = {
  '1M': '1',
  '5M': '5',
  '15M': '15',
  '1H': '60',
  '4H': '240',
  '1D': 'D',
};

let scriptLoaded = false;
let scriptPromise: Promise<void> | null = null;

function loadTradingViewScript(): Promise<void> {
  if (scriptLoaded) return Promise.resolve();
  if (scriptPromise) return scriptPromise;

  scriptPromise = new Promise((resolve) => {
    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/tv.js';
    script.async = true;
    script.onload = () => {
      scriptLoaded = true;
      resolve();
    };
    document.head.appendChild(script);
  });

  return scriptPromise;
}

export const TradingViewWidget: React.FC<TradingViewWidgetProps> = ({
  symbol = 'EUR/USD (OTC)',
  timeframe = '1M',
  height = 500,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetRef = useRef<any>(null);
  const containerId = 'tv_chart_container';

  const tvSymbol = SYMBOL_MAP[symbol] || 'FX:EURUSD';
  const tvInterval = INTERVAL_MAP[timeframe] || '1';

  // Mount widget once
  useEffect(() => {
    let mounted = true;

    loadTradingViewScript().then(() => {
      if (!mounted || !window.TradingView) return;

      // Clean up previous widget
      if (widgetRef.current) {
        try { widgetRef.current.remove(); } catch (_) {}
        widgetRef.current = null;
      }

      const widget = new window.TradingView.widget({
        container_id: containerId,
        symbol: tvSymbol,
        interval: tvInterval,
        timezone: 'Etc/UTC',
        theme: 'dark',
        style: '1',
        locale: 'en',
        toolbar_bg: '#0b0e14',
        enable_publishing: false,
        hide_side_toolbar: false,
        allow_symbol_change: false,
        withdateranges: true,
        autosize: true,
        studies: ['RSI@tv-basicstudies'],
        backgroundColor: '#0b0e14',
        gridColor: '#161d2a',
        overrides: {
          'mainSeriesProperties.candleStyle.upColor': '#00f298',
          'mainSeriesProperties.candleStyle.downColor': '#ff3366',
          'mainSeriesProperties.candleStyle.wickUpColor': '#00f298',
          'mainSeriesProperties.candleStyle.wickDownColor': '#ff3366',
          'mainSeriesProperties.candleStyle.borderUpColor': '#00f298',
          'mainSeriesProperties.candleStyle.borderDownColor': '#ff3366',
          'paneProperties.background': '#0b0e14',
          'paneProperties.backgroundType': 'solid',
          'scalesProperties.textColor': '#8a99ad',
        },
      });

      widgetRef.current = widget;
    });

    return () => {
      mounted = false;
    };
  }, []); // mount once

  // Smooth symbol/interval switch without remounting
  useEffect(() => {
    if (!widgetRef.current) return;

    const applyChange = () => {
      try {
        const chart = widgetRef.current.chart();
        chart.setSymbol(tvSymbol, tvInterval, () => {});
      } catch (_) {
        // Widget not ready yet — it will have loaded with correct props
      }
    };

    // Give widget a moment to be ready on first load
    const timer = setTimeout(applyChange, 300);
    return () => clearTimeout(timer);
  }, [tvSymbol, tvInterval]);

  return (
    <div
      className="relative w-full rounded-xl overflow-hidden border border-surface-border bg-[#0b0e14] shadow-2xl"
      style={{ height: `${height}px` }}
    >
      {/* Header */}
      <div className="absolute top-0 left-0 right-0 z-10 px-4 py-2 flex items-center justify-between bg-[#0b0e14]/90 backdrop-blur-sm border-b border-surface-border/60">
        <div className="flex items-center space-x-3">
          <span className="font-mono font-bold text-sm text-white">{symbol}</span>
          <span className="text-[10px] px-2 py-0.5 rounded bg-primary/20 text-primary font-mono font-semibold border border-primary/30">
            {timeframe}
          </span>
          <span className="text-[11px] text-emerald-400 font-mono flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            LIVE · TradingView
          </span>
        </div>
        <span className="text-[10px] text-gray-500 font-mono">{tvSymbol}</span>
      </div>

      {/* TradingView widget container — padded top for header */}
      <div
        id={containerId}
        ref={containerRef}
        style={{ position: 'absolute', top: 40, left: 0, right: 0, bottom: 0 }}
      />
    </div>
  );
};
