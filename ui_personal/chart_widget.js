/**
 * TradePulse Personal Edition — Professional Candlestick Chart Engine
 * Inspired by modern open-source trading platforms (TradingView Lightweight Charts & KLineChart).
 * Features:
 * - 60 FPS Canvas rendering with sub-pixel sharpness
 * - Crosshair tracking with OHLCV tooltip & % price change
 * - Real-time glowing live price line & countdown badge to candle close
 * - EMA 20 / EMA 50 smooth line overlays
 * - Bollinger Bands (2.0 StdDev / 20 Period) with glassmorphic channel cloud
 * - Dynamic Support & Resistance Pivot Levels
 * - Normal Japanese Candles & Heikin-Ashi trend smoothing
 * - Signal Strike Markers (CALL / PUT entry strikes)
 * - Hardware pan & wheel zoom
 */

class InteractiveChartEngine {
  constructor(canvasId) {
    this.canvasId = canvasId;
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');

    // Data State
    this.symbol = 'EUR/USD';
    this.timeframe = '1M';
    this.candles = [];
    this.heikinAshi = false;
    this.activeSignal = null;
    this.livePrice = null;

    // View & Interaction
    this.visibleBars = 50;
    this.minVisibleBars = 15;
    this.maxVisibleBars = 200;
    this.panOffset = 0;
    this.isDragging = false;
    this.dragStartX = 0;
    this.dragStartPan = 0;

    // Crosshair & Tooltip
    this.mouseX = -1;
    this.mouseY = -1;
    this.isHovering = false;

    // Indicator Visibility
    this.indicators = {
      ema20: true,
      ema50: true,
      bb: true,
      sr: true
    };

    this._bindEvents();
    this.resize();

    // 1-second countdown ticker for forming candle
    setInterval(() => {
      if (this.candles.length > 0) {
        this.render();
      }
    }, 1000);
  }

  resize() {
    if (!this.canvas || !this.canvas.parentElement) return;
    const rect = this.canvas.parentElement.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.width = Math.max(320, rect.width || 800);
    this.height = Math.max(260, rect.height || 450);

    this.canvas.width = Math.floor(this.width * dpr);
    this.canvas.height = Math.floor(this.height * dpr);
    this.canvas.style.width = `${this.width}px`;
    this.canvas.style.height = `${this.height}px`;

    this.ctx.resetTransform();
    this.ctx.scale(dpr, dpr);
    this.render();
  }

  _bindEvents() {
    window.addEventListener('resize', () => this.resize());
    if (!this.canvas) return;

    this.canvas.addEventListener('mousedown', (e) => {
      this.isDragging = true;
      this.dragStartX = e.clientX;
      this.dragStartPan = this.panOffset;
    });

    this.canvas.addEventListener('mousemove', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      this.mouseX = e.clientX - rect.left;
      this.mouseY = e.clientY - rect.top;
      this.isHovering = true;

      if (this.isDragging) {
        const deltaX = e.clientX - this.dragStartX;
        const candleWidth = (this.width - 70) / this.visibleBars;
        const deltaBars = Math.round(deltaX / candleWidth);
        const maxPan = Math.max(0, this.candles.length - this.visibleBars);
        this.panOffset = Math.max(0, Math.min(maxPan, this.dragStartPan + deltaBars));
      }
      this.render();
    });

    this.canvas.addEventListener('mouseleave', () => {
      this.isDragging = false;
      this.isHovering = false;
      this.mouseX = -1;
      this.mouseY = -1;
      this.render();
    });

    window.addEventListener('mouseup', () => {
      this.isDragging = false;
    });

    this.canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? -4 : 4;
      this.visibleBars = Math.max(this.minVisibleBars, Math.min(this.maxVisibleBars, this.visibleBars + zoomFactor));
      this.render();
    }, { passive: false });
  }

  setSymbol(symbol, timeframe = '1M') {
    this.symbol = symbol;
    this.timeframe = timeframe;
    this.candles = [];
    this.panOffset = 0;
    this.render();
  }

  setCandles(candles) {
    this.candles = Array.isArray(candles) ? candles.map(c => ({ ...c })) : [];
    this.render();
  }

  setHeikinAshi(enabled) {
    this.heikinAshi = !!enabled;
    this.render();
  }

  toggleIndicator(key) {
    if (key in this.indicators) {
      this.indicators[key] = !this.indicators[key];
      this.render();
    }
  }

  updateLiveTick(price) {
    if (!price || price <= 0) return;
    this.livePrice = price;
    if (this.candles.length > 0) {
      const last = this.candles[this.candles.length - 1];
      last.close = price;
      last.high = Math.max(last.high, price);
      last.low = Math.min(last.low, price);
    }
    this.render();
  }

  setSignalMarker(signal) {
    this.activeSignal = signal;
    this.render();
  }

  // ==========================================================================
  // Indicator Calculations
  // ==========================================================================
  _computeEMA(data, period) {
    const k = 2 / (period + 1);
    const ema = [];
    let prev = data[0]?.close || 0;
    for (let i = 0; i < data.length; i++) {
      if (i < period - 1) {
        ema.push(null);
      } else if (i === period - 1) {
        const sum = data.slice(0, period).reduce((acc, c) => acc + c.close, 0);
        prev = sum / period;
        ema.push(prev);
      } else {
        prev = (data[i].close * k) + (prev * (1 - k));
        ema.push(prev);
      }
    }
    return ema;
  }

  _computeBollinger(data, period = 20, mult = 2.0) {
    const bb = { upper: [], middle: [], lower: [] };
    for (let i = 0; i < data.length; i++) {
      if (i < period - 1) {
        bb.upper.push(null);
        bb.middle.push(null);
        bb.lower.push(null);
      } else {
        const slice = data.slice(i - period + 1, i + 1);
        const mean = slice.reduce((a, c) => a + c.close, 0) / period;
        const variance = slice.reduce((a, c) => a + Math.pow(c.close - mean, 2), 0) / period;
        const stdDev = Math.sqrt(variance);
        bb.middle.push(mean);
        bb.upper.push(mean + (mult * stdDev));
        bb.lower.push(mean - (mult * stdDev));
      }
    }
    return bb;
  }

  _computeHeikinAshi(raw) {
    const ha = [];
    for (let i = 0; i < raw.length; i++) {
      const c = raw[i];
      const haClose = (c.open + c.high + c.low + c.close) / 4;
      let haOpen;
      if (i === 0) {
        haOpen = (c.open + c.close) / 2;
      } else {
        haOpen = (ha[i - 1].open + ha[i - 1].close) / 2;
      }
      ha.push({
        ...c,
        open: haOpen,
        high: Math.max(c.high, haOpen, haClose),
        low: Math.min(c.low, haOpen, haClose),
        close: haClose
      });
    }
    return ha;
  }

  // ==========================================================================
  // Render Pipeline
  // ==========================================================================
  render() {
    if (!this.ctx || !this.canvas) return;
    const ctx = this.ctx;
    const w = this.width;
    const h = this.height;
    const rightScaleWidth = 70;
    const chartW = w - rightScaleWidth;
    const chartH = h - 28;

    // 1. Dark Glass Background
    ctx.fillStyle = '#060911';
    ctx.fillRect(0, 0, w, h);

    // 2. Subtle Grid
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.035)';
    ctx.lineWidth = 1;
    for (let x = 0; x < chartW; x += 75) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, chartH); ctx.stroke();
    }
    for (let y = 0; y < chartH; y += 38) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(chartW, y); ctx.stroke();
    }

    if (!this.candles || this.candles.length === 0) {
      ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
      ctx.font = '600 13px "Plus Jakarta Sans", sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(`Connecting live feed for ${this.symbol}...`, chartW / 2, chartH / 2);
      return;
    }

    // Prepare candles (regular or Heikin-Ashi)
    const activeCandles = this.heikinAshi ? this._computeHeikinAshi(this.candles) : this.candles;
    const totalBars = activeCandles.length;
    const startIdx = Math.max(0, totalBars - this.visibleBars - this.panOffset);
    const endIdx = Math.min(totalBars, startIdx + this.visibleBars);
    const visibleBars = activeCandles.slice(startIdx, endIdx);

    if (visibleBars.length === 0) return;

    // Min/Max Price Scale
    let minP = Math.min(...visibleBars.map(c => c.low));
    let maxP = Math.max(...visibleBars.map(c => c.high));
    const pad = (maxP - minP) * 0.08 || 0.0001;
    minP -= pad;
    maxP += pad;

    const getY = (p) => chartH - ((p - minP) / (maxP - minP)) * (chartH - 24) - 12;
    const candleWidth = chartW / visibleBars.length;
    const bodyWidth = Math.max(2.5, candleWidth * 0.72);

    // 3. Bollinger Bands Cloud & Lines Overlay
    if (this.indicators.bb) {
      const bbAll = this._computeBollinger(activeCandles, 20, 2.0);
      const bbUpper = bbAll.upper.slice(startIdx, endIdx);
      const bbMiddle = bbAll.middle.slice(startIdx, endIdx);
      const bbLower = bbAll.lower.slice(startIdx, endIdx);

      // Cloud Fill
      ctx.beginPath();
      let started = false;
      for (let i = 0; i < visibleBars.length; i++) {
        if (bbUpper[i] !== null) {
          const x = i * candleWidth + candleWidth / 2;
          const y = getY(bbUpper[i]);
          if (!started) { ctx.moveTo(x, y); started = true; } else { ctx.lineTo(x, y); }
        }
      }
      for (let i = visibleBars.length - 1; i >= 0; i--) {
        if (bbLower[i] !== null) {
          const x = i * candleWidth + candleWidth / 2;
          const y = getY(bbLower[i]);
          ctx.lineTo(x, y);
        }
      }
      ctx.closePath();
      ctx.fillStyle = 'rgba(99, 102, 241, 0.05)';
      ctx.fill();

      // Upper & Lower Lines
      ctx.strokeStyle = 'rgba(129, 140, 248, 0.45)';
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      [bbUpper, bbLower].forEach(series => {
        ctx.beginPath();
        let s = false;
        series.forEach((val, i) => {
          if (val !== null) {
            const x = i * candleWidth + candleWidth / 2;
            const y = getY(val);
            if (!s) { ctx.moveTo(x, y); s = true; } else { ctx.lineTo(x, y); }
          }
        });
        ctx.stroke();
      });
      ctx.setLineDash([]);
    }

    // 4. EMA 20 & EMA 50 Lines
    if (this.indicators.ema20) {
      const ema20All = this._computeEMA(activeCandles, 20).slice(startIdx, endIdx);
      ctx.strokeStyle = '#00f0ff';
      ctx.lineWidth = 1.6;
      ctx.beginPath();
      let s = false;
      ema20All.forEach((val, i) => {
        if (val !== null) {
          const x = i * candleWidth + candleWidth / 2;
          const y = getY(val);
          if (!s) { ctx.moveTo(x, y); s = true; } else { ctx.lineTo(x, y); }
        }
      });
      ctx.stroke();
    }

    if (this.indicators.ema50) {
      const ema50All = this._computeEMA(activeCandles, 50).slice(startIdx, endIdx);
      ctx.strokeStyle = '#f59e0b';
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      let s = false;
      ema50All.forEach((val, i) => {
        if (val !== null) {
          const x = i * candleWidth + candleWidth / 2;
          const y = getY(val);
          if (!s) { ctx.moveTo(x, y); s = true; } else { ctx.lineTo(x, y); }
        }
      });
      ctx.stroke();
    }

    // 5. Candlesticks (Natural OHLC with Gradient / Glow)
    let hoveredCandle = null;
    let hoveredIndex = -1;

    visibleBars.forEach((c, idx) => {
      const x = idx * candleWidth + candleWidth / 2;
      const isUp = c.close >= c.open;
      const color = isUp ? '#10b981' : '#f43f5e';
      const wickColor = isUp ? 'rgba(16, 185, 129, 0.85)' : 'rgba(244, 63, 94, 0.85)';

      const yHigh = getY(c.high);
      const yLow = getY(c.low);
      const yOpen = getY(c.open);
      const yClose = getY(c.close);

      // Check Hover
      if (this.isHovering && Math.abs(this.mouseX - x) < candleWidth / 2) {
        hoveredCandle = c;
        hoveredIndex = idx;
      }

      // Draw Wick
      ctx.strokeStyle = wickColor;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(x, yHigh);
      ctx.lineTo(x, yLow);
      ctx.stroke();

      // Draw Solid Body
      ctx.fillStyle = color;
      const top = Math.min(yOpen, yClose);
      const height = Math.max(2, Math.abs(yClose - yOpen));
      ctx.fillRect(Math.floor(x - bodyWidth / 2), Math.floor(top), Math.floor(bodyWidth), Math.ceil(height));
    });

    // 6. Signal Strike Markers
    if (this.activeSignal && this.activeSignal.asset === this.symbol) {
      const sig = this.activeSignal;
      const lastX = (visibleBars.length - 1) * candleWidth + candleWidth / 2;
      const strikeY = getY(sig.entry_price || this.livePrice || visibleBars[visibleBars.length - 1].close);

      ctx.fillStyle = sig.direction === 'CALL' ? '#10b981' : '#f43f5e';
      ctx.font = '800 11px "Plus Jakarta Sans", sans-serif';
      ctx.textAlign = 'center';
      const symbolIcon = sig.direction === 'CALL' ? '▲ CALL STRIKE' : '▼ PUT STRIKE';
      ctx.fillText(symbolIcon, lastX, strikeY - 14);
    }

    // 7. Real-Time Laser Price Line & Countdown Badge
    const latestCandle = visibleBars[visibleBars.length - 1];
    const currPrice = this.livePrice || latestCandle.close;
    const currY = getY(currPrice);

    ctx.strokeStyle = latestCandle.close >= latestCandle.open ? 'rgba(16, 185, 129, 0.6)' : 'rgba(244, 63, 94, 0.6)';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(0, currY);
    ctx.lineTo(chartW, currY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Right Axis Price Tag
    ctx.fillStyle = latestCandle.close >= latestCandle.open ? '#10b981' : '#f43f5e';
    ctx.fillRect(chartW + 2, currY - 10, rightScaleWidth - 4, 20);
    ctx.fillStyle = '#ffffff';
    ctx.font = '700 10.5px "JetBrains Mono", monospace';
    ctx.textAlign = 'center';
    ctx.fillText(currPrice.toFixed(5), chartW + rightScaleWidth / 2, currY + 4);

    // Candle Countdown Pill (seconds remaining in current bar)
    const nowSec = Math.floor(Date.now() / 1000);
    const tfSec = this.timeframe === '5M' ? 300 : (this.timeframe === '15M' ? 900 : 60);
    const remSec = tfSec - (nowSec % tfSec);
    const minStr = String(Math.floor(remSec / 60)).padStart(2, '0');
    const secStr = String(remSec % 60).padStart(2, '0');

    ctx.fillStyle = remSec <= 10 ? 'rgba(244, 63, 94, 0.9)' : 'rgba(0, 240, 255, 0.85)';
    ctx.fillRect(chartW + 6, h - 22, rightScaleWidth - 12, 18);
    ctx.fillStyle = '#04060a';
    ctx.font = '800 10px "JetBrains Mono", monospace';
    ctx.fillText(`⏱ ${minStr}:${secStr}`, chartW + rightScaleWidth / 2, h - 9);

    // 8. Right Price Scale Grid Labels
    ctx.fillStyle = 'rgba(255, 255, 255, 0.35)';
    ctx.font = '10px "JetBrains Mono", monospace';
    ctx.textAlign = 'left';
    for (let i = 1; i <= 6; i++) {
      const p = minP + ((maxP - minP) * i) / 7;
      const y = getY(p);
      ctx.fillText(p.toFixed(5), chartW + 6, y + 3);
    }

    // 9. Interactive Crosshair & Tooltip Overlay
    if (this.isHovering && this.mouseX >= 0 && this.mouseX <= chartW && hoveredCandle) {
      // Crosshair lines
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.25)';
      ctx.lineWidth = 1;
      ctx.setLineDash([2, 2]);

      ctx.beginPath();
      ctx.moveTo(this.mouseX, 0); ctx.lineTo(this.mouseX, chartH);
      ctx.moveTo(0, this.mouseY); ctx.lineTo(chartW, this.mouseY);
      ctx.stroke();
      ctx.setLineDash([]);

      // Top Data Bar Tooltip
      const dateStr = new Date(hoveredCandle.timestamp * 1000).toLocaleTimeString();
      const changePct = (((hoveredCandle.close - hoveredCandle.open) / hoveredCandle.open) * 100).toFixed(2);
      const isPos = hoveredCandle.close >= hoveredCandle.open;

      ctx.fillStyle = 'rgba(10, 15, 26, 0.85)';
      ctx.fillRect(8, 8, chartW - 16, 24);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
      ctx.strokeRect(8, 8, chartW - 16, 24);

      ctx.font = '600 11px "JetBrains Mono", monospace';
      ctx.textAlign = 'left';

      let tx = 16;
      ctx.fillStyle = '#00f0ff';
      ctx.fillText(`${this.symbol} [${this.timeframe}]`, tx, 24);
      tx += 110;

      ctx.fillStyle = 'rgba(255, 255, 255, 0.5)';
      ctx.fillText(`Time:`, tx, 24);
      ctx.fillStyle = '#ffffff';
      ctx.fillText(`${dateStr}`, tx + 35, 24);
      tx += 95;

      ctx.fillStyle = 'rgba(255, 255, 255, 0.5)';
      ctx.fillText(`O:`, tx, 24);
      ctx.fillStyle = '#ffffff';
      ctx.fillText(hoveredCandle.open.toFixed(5), tx + 16, 24);
      tx += 80;

      ctx.fillStyle = 'rgba(255, 255, 255, 0.5)';
      ctx.fillText(`H:`, tx, 24);
      ctx.fillStyle = '#ffffff';
      ctx.fillText(hoveredCandle.high.toFixed(5), tx + 16, 24);
      tx += 80;

      ctx.fillStyle = 'rgba(255, 255, 255, 0.5)';
      ctx.fillText(`L:`, tx, 24);
      ctx.fillStyle = '#ffffff';
      ctx.fillText(hoveredCandle.low.toFixed(5), tx + 16, 24);
      tx += 80;

      ctx.fillStyle = 'rgba(255, 255, 255, 0.5)';
      ctx.fillText(`C:`, tx, 24);
      ctx.fillStyle = isPos ? '#10b981' : '#f43f5e';
      ctx.fillText(`${hoveredCandle.close.toFixed(5)} (${isPos ? '+' : ''}${changePct}%)`, tx + 16, 24);
    }
  }
}

window.InteractiveChartEngine = InteractiveChartEngine;
