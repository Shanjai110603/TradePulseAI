import React, { useEffect, useRef } from 'react';
import { createChart, IChartApi, CandlestickSeries, ISeriesApi, Time } from 'lightweight-charts';
import { Candle } from '../../types';

interface TradingViewChartProps {
  candles: Candle[];
  symbol?: string;
  timeframe?: string;
  supportLevels?: number[];
  resistanceLevels?: number[];
  signalMarker?: {
    timestamp: number;
    price: number;
    direction: 'UP' | 'DOWN' | 'BUY' | 'SELL';
    text?: string;
  };
  fastEma?: number[];
  slowEma?: number[];
  height?: number;
}

export const TradingViewChart: React.FC<TradingViewChartProps> = ({
  candles,
  symbol = 'EUR/USD (OTC)',
  timeframe = '1M',
  supportLevels = [],
  resistanceLevels = [],
  signalMarker,
  height = 440,
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const priceLinesRef = useRef<any[]>([]);
  const lastSymbolRef = useRef<string>('');
  const lastCandleTimestampRef = useRef<number>(0);

  // 1. Initialize Chart Instance ONCE
  useEffect(() => {
    if (!chartContainerRef.current) return;

    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
    }

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: height,
      layout: {
        background: { color: '#0b0e14' },
        textColor: '#8a99ad',
        fontSize: 11,
        fontFamily: 'JetBrains Mono, monospace',
      },
      grid: {
        vertLines: { color: '#161d2a' },
        horzLines: { color: '#161d2a' },
      },
      crosshair: {
        mode: 1,
        vertLine: { color: '#00d2ff', width: 1, style: 3 },
        horzLine: { color: '#00d2ff', width: 1, style: 3 },
      },
      rightPriceScale: {
        borderColor: '#222f44',
        scaleMargins: { top: 0.12, bottom: 0.12 },
        autoScale: true,
      },
      timeScale: {
        borderColor: '#222f44',
        timeVisible: true,
        secondsVisible: false,
        shiftVisibleRangeOnNewBar: true,
      },
    });

    chartRef.current = chart;

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#00f298',
      downColor: '#ff3366',
      borderVisible: false,
      wickUpColor: '#00f298',
      wickDownColor: '#ff3366',
    });

    candleSeriesRef.current = candleSeries;
    lastSymbolRef.current = '';

    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
        candleSeriesRef.current = null;
      }
    };
  }, [height]);

  // 2. Smooth Candle Updates without Resetting View
  useEffect(() => {
    if (!candleSeriesRef.current || !candles || candles.length === 0) return;

    const formattedData = candles
      .filter((c) =>
        c.timestamp != null &&
        isFinite(c.open) && isFinite(c.high) &&
        isFinite(c.low) && isFinite(c.close) &&
        c.high >= c.low
      )
      .map((c) => ({
        time: Math.floor(c.timestamp) as Time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
      .sort((a, b) => (a.time as number) - (b.time as number));

    if (formattedData.length === 0) return;

    const latestCandle = formattedData[formattedData.length - 1];
    const latestTimestamp = latestCandle.time as number;

    // If symbol changed or first load for this symbol
    if (lastSymbolRef.current !== symbol) {
      candleSeriesRef.current.setData(formattedData);
      chartRef.current?.timeScale().fitContent();
      lastSymbolRef.current = symbol;
      lastCandleTimestampRef.current = latestTimestamp;
    } else {
      // If updating the active forming candle in real-time
      if (latestTimestamp === lastCandleTimestampRef.current) {
        candleSeriesRef.current.update(latestCandle);
      } else {
        // A new candle has just spawned
        candleSeriesRef.current.update(latestCandle);
        lastCandleTimestampRef.current = latestTimestamp;
      }
    }

    // Static Support/Resistance Price Lines
    if (priceLinesRef.current.length === 0 && supportLevels.length > 0) {
      supportLevels.forEach((s) => {
        if (candleSeriesRef.current) {
          const line = candleSeriesRef.current.createPriceLine({
            price: s,
            color: '#00f298',
            lineWidth: 1,
            lineStyle: 2,
            axisLabelVisible: true,
            title: `SUP ${s.toFixed(5)}`,
          });
          priceLinesRef.current.push(line);
        }
      });

      resistanceLevels.forEach((r) => {
        if (candleSeriesRef.current) {
          const line = candleSeriesRef.current.createPriceLine({
            price: r,
            color: '#ff3366',
            lineWidth: 1,
            lineStyle: 2,
            axisLabelVisible: true,
            title: `RES ${r.toFixed(5)}`,
          });
          priceLinesRef.current.push(line);
        }
      });
    }

    if (signalMarker && candleSeriesRef.current) {
      const isDown = signalMarker.direction === 'DOWN' || signalMarker.direction === 'SELL';
      (candleSeriesRef.current as any).setMarkers?.([
        {
          time: Math.floor(signalMarker.timestamp) as Time,
          position: isDown ? 'aboveBar' : 'belowBar',
          color: isDown ? '#ff3366' : '#00f298',
          shape: isDown ? 'arrowDown' : 'arrowUp',
          text: signalMarker.text || (isDown ? '🔴 PUT' : '🟢 CALL'),
          size: 2,
        },
      ]);
    }
  }, [candles, symbol, supportLevels, resistanceLevels, signalMarker]);

  const latestCandle = candles && candles.length > 0 ? candles[candles.length - 1] : null;
  const isUp = latestCandle ? latestCandle.close >= latestCandle.open : true;

  return (
    <div className="relative w-full rounded-xl overflow-hidden border border-surface-border bg-surface shadow-2xl">
      {/* Live Chart Header */}
      <div className="px-4 py-2.5 border-b border-surface-border/80 flex items-center justify-between bg-surface-raised/60">
        <div className="flex items-center space-x-3">
          <span className="font-mono font-bold text-sm text-white tracking-wide">{symbol}</span>
          <span className="text-[10px] px-2 py-0.5 rounded bg-primary/20 text-primary font-mono font-semibold border border-primary/30">
            {timeframe}
          </span>
          <span className="text-[11px] text-emerald-400 font-mono flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
            LIVE STREAM
          </span>
        </div>
        <div className="flex items-center space-x-3 text-xs font-mono">
          {latestCandle && (
            <div className="flex items-center space-x-2">
              <span className="text-gray-400">Live Price:</span>
              <span className={`font-bold text-sm px-2 py-0.5 rounded ${isUp ? 'text-trade-up bg-emerald-950/60 border border-emerald-800/60' : 'text-trade-down bg-rose-950/60 border border-rose-800/60'}`}>
                {latestCandle.close.toFixed(symbol.includes('BTC') ? 2 : (symbol.includes('JPY') ? 3 : 5))}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Lightweight Charts Canvas */}
      <div ref={chartContainerRef} className="w-full" style={{ height: `${height}px` }} />
    </div>
  );
};
