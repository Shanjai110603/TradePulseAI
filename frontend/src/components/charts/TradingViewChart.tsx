import React, { useEffect, useRef } from 'react';
import { createChart, IChartApi, ISeriesApi, CandlestickData, LineData, Time } from 'lightweight-charts';
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
  symbol = 'EUR/USD',
  timeframe = '1M',
  supportLevels = [],
  resistanceLevels = [],
  signalMarker,
  height = 420,
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Clean up prior chart instance
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
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
        vertLine: {
          color: '#00d2ff',
          width: 1,
          style: 3,
        },
        horzLine: {
          color: '#00d2ff',
          width: 1,
          style: 3,
        },
      },
      rightPriceScale: {
        borderColor: '#222f44',
        scaleMargins: {
          top: 0.1,
          bottom: 0.1,
        },
      },
      timeScale: {
        borderColor: '#222f44',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    chartRef.current = chart;

    // Add Candlestick Series (supports multiple lightweight-charts versions)
    const candleSeries = (chart as any).addCandlestickSeries ? (chart as any).addCandlestickSeries({
      upColor: '#00f298',
      downColor: '#ff3366',
      borderVisible: false,
      wickUpColor: '#00f298',
      wickDownColor: '#ff3366',
    }) : (chart as any).addSeries({
      type: 'Candlestick',
      upColor: '#00f298',
      downColor: '#ff3366',
      borderVisible: false,
      wickUpColor: '#00f298',
      wickDownColor: '#ff3366',
    });
    candleSeriesRef.current = candleSeries;

    // Format and load candle data
    if (candles && candles.length > 0) {
      const formattedData: CandlestickData<Time>[] = candles.map((c) => ({
        time: c.timestamp as Time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }));
      candleSeries.setData(formattedData);

      // Add Support Price Lines
      supportLevels.forEach((s) => {
        candleSeries.createPriceLine({
          price: s,
          color: '#00f298',
          lineWidth: 1,
          lineStyle: 2, // Dashed
          axisLabelVisible: true,
          title: `SUP ${s.toFixed(5)}`,
        });
      });

      // Add Resistance Price Lines
      resistanceLevels.forEach((r) => {
        candleSeries.createPriceLine({
          price: r,
          color: '#ff3366',
          lineWidth: 1,
          lineStyle: 2, // Dashed
          axisLabelVisible: true,
          title: `RES ${r.toFixed(5)}`,
        });
      });

      // Add Signal Marker
      if (signalMarker) {
        const isDown = signalMarker.direction === 'DOWN' || signalMarker.direction === 'SELL';
        candleSeries.setMarkers([
          {
            time: signalMarker.timestamp as Time,
            position: isDown ? 'aboveBar' : 'belowBar',
            color: isDown ? '#ff3366' : '#00f298',
            shape: isDown ? 'arrowDown' : 'arrowUp',
            text: signalMarker.text || (isDown ? '🔴 DOWN SIGNAL' : '🟢 UP SIGNAL'),
            size: 2,
          },
        ]);
      }

      chart.timeScale().fitContent();
    }

    // Auto-resize observer
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [candles, supportLevels, resistanceLevels, signalMarker, height]);

  return (
    <div className="relative w-full rounded-xl overflow-hidden border border-surface-border bg-surface">
      {/* Header bar on top of chart */}
      <div className="px-4 py-2.5 border-b border-surface-border/80 flex items-center justify-between bg-surface-raised/60">
        <div className="flex items-center space-x-3">
          <span className="font-mono font-bold text-sm text-white tracking-wide">{symbol}</span>
          <span className="text-[10px] px-2 py-0.5 rounded bg-primary/20 text-primary font-mono font-semibold border border-primary/30">
            {timeframe}
          </span>
          <span className="text-[11px] text-gray-400 font-mono">
            Candles: {candles.length}
          </span>
        </div>
        <div className="flex items-center space-x-3 text-xs font-mono">
          {candles.length > 0 && (
            <div className="flex items-center space-x-2">
              <span className="text-gray-400">Price:</span>
              <span
                className={`font-semibold ${
                  candles[candles.length - 1].close >= candles[candles.length - 1].open
                    ? 'text-trade-up'
                    : 'text-trade-down'
                }`}
              >
                {candles[candles.length - 1].close.toFixed(
                  symbol.includes('BTC') ? 2 : 5
                )}
              </span>
            </div>
          )}
        </div>
      </div>

      <div ref={chartContainerRef} className="w-full" style={{ height: `${height}px` }} />
    </div>
  );
};
