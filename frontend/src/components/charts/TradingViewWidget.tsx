import React, { useEffect, useRef } from 'react';

interface TradingViewWidgetProps {
  symbol?: string;
  timeframe?: string;
  height?: number;
}

// Maps our internal asset names to TradingView symbols
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

// Maps timeframe labels to TradingView interval values
const INTERVAL_MAP: Record<string, string> = {
  '1M': '1',
  '5M': '5',
  '15M': '15',
  '1H': '60',
  '4H': '240',
  '1D': 'D',
};

export const TradingViewWidget: React.FC<TradingViewWidgetProps> = ({
  symbol = 'EUR/USD (OTC)',
  timeframe = '1M',
  height = 440,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetRef = useRef<any>(null);
  const scriptRef = useRef<HTMLScriptElement | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const tvSymbol = SYMBOL_MAP[symbol] || 'FX:EURUSD';
    const tvInterval = INTERVAL_MAP[timeframe] || '1';

    // Clear old widget
    if (containerRef.current) {
      containerRef.current.innerHTML = '';
    }

    // Create wrapper div
    const widgetContainer = document.createElement('div');
    widgetContainer.className = 'tradingview-widget-container__widget';
    widgetContainer.style.height = `${height}px`;
    widgetContainer.style.width = '100%';
    containerRef.current.appendChild(widgetContainer);

    // Create and inject TradingView script
    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      autosize: true,
      symbol: tvSymbol,
      interval: tvInterval,
      timezone: 'Etc/UTC',
      theme: 'dark',
      style: '1',
      locale: 'en',
      backgroundColor: '#0b0e14',
      gridColor: '#161d2a',
      allow_symbol_change: false,
      calendar: false,
      support_host: 'https://www.tradingview.com',
      withdateranges: true,
      hide_side_toolbar: false,
      details: false,
      hotlist: false,
      watchlist: false,
      studies: [
        'RSI@tv-basicstudies',
        'MASimple@tv-basicstudies',
      ],
    });

    containerRef.current.appendChild(script);
    scriptRef.current = script;

    return () => {
      if (containerRef.current) {
        containerRef.current.innerHTML = '';
      }
    };
  }, [symbol, timeframe, height]);

  const displaySymbol = symbol;
  const tvSymbol = SYMBOL_MAP[symbol] || symbol;

  return (
    <div className="relative w-full rounded-xl overflow-hidden border border-surface-border bg-[#0b0e14] shadow-2xl">
      {/* Chart Header */}
      <div className="px-4 py-2.5 border-b border-surface-border/80 flex items-center justify-between bg-surface-raised/60">
        <div className="flex items-center space-x-3">
          <span className="font-mono font-bold text-sm text-white tracking-wide">{displaySymbol}</span>
          <span className="text-[10px] px-2 py-0.5 rounded bg-primary/20 text-primary font-mono font-semibold border border-primary/30">
            {timeframe}
          </span>
          <span className="text-[11px] text-emerald-400 font-mono flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            LIVE DATA — TradingView
          </span>
        </div>
        <div className="text-[10px] text-gray-500 font-mono">
          {tvSymbol}
        </div>
      </div>

      {/* TradingView Widget Container */}
      <div
        ref={containerRef}
        className="tradingview-widget-container w-full"
        style={{ height: `${height}px`, background: '#0b0e14' }}
      />
    </div>
  );
};
