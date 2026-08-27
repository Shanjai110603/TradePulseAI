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
  height = 480,
}) => {
  const tvSymbol = SYMBOL_MAP[symbol] || 'FX:EURUSD';
  const tvInterval = INTERVAL_MAP[timeframe] || '1';

  const src = `https://www.tradingview.com/widgetembed/?frameElementId=tradingview_chart&symbol=${encodeURIComponent(tvSymbol)}&interval=${tvInterval}&theme=dark&style=1&locale=en&toolbar_bg=%230b0e14&enable_publishing=0&hide_side_toolbar=0&allow_symbol_change=0&studies=RSI%40tv-basicstudies&withdateranges=1&autosize=1&backgroundColor=%230b0e14`;

  return (
    <div className="relative w-full rounded-xl overflow-hidden border border-surface-border bg-[#0b0e14] shadow-2xl flex flex-col" style={{ height: `${height + 48}px` }}>
      {/* Chart Header */}
      <div className="flex-shrink-0 px-4 py-2.5 border-b border-surface-border/80 flex items-center justify-between bg-surface-raised/60">
        <div className="flex items-center space-x-3">
          <span className="font-mono font-bold text-sm text-white tracking-wide">{symbol}</span>
          <span className="text-[10px] px-2 py-0.5 rounded bg-primary/20 text-primary font-mono font-semibold border border-primary/30">
            {timeframe}
          </span>
          <span className="text-[11px] text-emerald-400 font-mono flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            LIVE · TradingView
          </span>
        </div>
        <span className="text-[10px] text-gray-500 font-mono">{tvSymbol}</span>
      </div>

      {/* Full-Height TradingView iFrame */}
      <div className="flex-1 w-full overflow-hidden">
        <iframe
          key={`${tvSymbol}-${tvInterval}`}
          src={src}
          id="tradingview_chart"
          title="TradingView Live Chart"
          frameBorder="0"
          allowTransparency={true}
          scrolling="no"
          allowFullScreen={true}
          style={{
            width: '100%',
            height: '100%',
            minHeight: `${height}px`,
            display: 'block',
            border: 'none',
          }}
        />
      </div>
    </div>
  );
};
