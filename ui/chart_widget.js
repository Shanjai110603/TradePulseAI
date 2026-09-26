/**
 * TradePulse Pro Interactive Candlestick Chart Station Engine
 * Real-time tick aggregation, hardware-accelerated Canvas, Pan & Zoom,
 * EMA 20/50, S/R Dynamic Pivots, Volume Bars, RSI(14) Sub-Chart & Signal Overlays.
 */

class InteractiveChartEngine {
  constructor(canvasId) {
    this.canvasId = canvasId;
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');

    // Data State
    this.symbol = 'EUR/USD (OTC)';
    this.timeframe = '1M';
    this.candles = [];
    this.activeSignal = null;
    this.livePrice = null;
    this.lastTickTime = Date.now();

    // View & Interaction State
    this.visibleBars = 45;      // How many bars fit on screen
    this.minVisibleBars = 12;   // Maximum zoom in
    this.maxVisibleBars = 180;  // Maximum zoom out
    this.panOffset = 0;         // 0 = rightmost / newest candle visible
    this.autoFollow = true;     // Automatically stay at right edge on new ticks
    this.isDragging = false;
    this.dragStartX = 0;
    this.dragStartPan = 0;

    // Crosshair & Hover
    this.mouseX = -1;
    this.mouseY = -1;
    this.hoveredCandle = null;

    // Indicators Visibility
    this.indicators = {
      ema20: true,
      ema50: true,
      pivots: true,
      rsi: false,
      volume: true
    };

    // Animation & Render throttling
    this._rafPending = false;

    this._bindEvents();
    this.resize();
  }

  resize() {
    if (!this.canvas || !this.canvas.parentElement) return;
    const rect = this.canvas.parentElement.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.width = Math.max(300, rect.width || 800);
    this.height = Math.max(260, rect.height || 500);

    this.canvas.width = Math.floor(this.width * dpr);
    this.canvas.height = Math.floor(this.height * dpr);
    this.canvas.style.width = `${this.width}px`;
    this.canvas.style.height = `${this.height}px`;

    this.ctx.setTransform(1, 0, 0, 1, 0, 0);
    this.ctx.scale(dpr, dpr);
    this.scheduleRender();
  }

  _bindEvents() {
    if (!this.canvas) return;

    // Mouse Move & Crosshair
    this.canvas.addEventListener('mousemove', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      this.mouseX = e.clientX - rect.left;
      this.mouseY = e.clientY - rect.top;

      if (this.isDragging) {
        const deltaX = this.mouseX - this.dragStartX;
        const barWidth = (this.width - 65) / this.visibleBars;
        const barDelta = deltaX / barWidth;
        this.panOffset = Math.max(0, Math.min(this.candles.length - 10, this.dragStartPan + barDelta));
        this.autoFollow = (this.panOffset <= 0.5);
        this._updateAutoFollowButton();
      }

      this.scheduleRender();
    });

    // Mouse Down (Start Pan Drag)
    this.canvas.addEventListener('mousedown', (e) => {
      if (e.button !== 0) return; // Left click only
      this.isDragging = true;
      const rect = this.canvas.getBoundingClientRect();
      this.dragStartX = e.clientX - rect.left;
      this.dragStartPan = this.panOffset;
      this.canvas.style.cursor = 'grabbing';
    });

    // Mouse Up (End Pan Drag)
    window.addEventListener('mouseup', () => {
      if (this.isDragging) {
        this.isDragging = false;
        if (this.canvas) this.canvas.style.cursor = 'crosshair';
      }
    });

    // Mouse Leave
    this.canvas.addEventListener('mouseleave', () => {
      this.mouseX = -1;
      this.mouseY = -1;
      this.hoveredCandle = null;
      this._updateHUD(null);
      this.scheduleRender();
    });

    // Mouse Wheel (Interactive Zoom)
    this.canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY > 0 ? 1.15 : 0.87;
      this.zoom(zoomFactor);
    }, { passive: false });

    // Touch Support for tablets/laptops
    let touchStartX = 0;
    this.canvas.addEventListener('touchstart', (e) => {
      if (e.touches.length === 1) {
        this.isDragging = true;
        touchStartX = e.touches[0].clientX;
        this.dragStartPan = this.panOffset;
      }
    }, { passive: true });

    this.canvas.addEventListener('touchmove', (e) => {
      if (this.isDragging && e.touches.length === 1) {
        const deltaX = e.touches[0].clientX - touchStartX;
        const barWidth = (this.width - 65) / this.visibleBars;
        this.panOffset = Math.max(0, Math.min(this.candles.length - 10, this.dragStartPan + (deltaX / barWidth)));
        this.autoFollow = (this.panOffset <= 0.5);
        this._updateAutoFollowButton();
        this.scheduleRender();
      }
    }, { passive: true });

    this.canvas.addEventListener('touchend', () => {
      this.isDragging = false;
    });

    window.addEventListener('resize', () => {
      this.resize();
    });
  }

  zoom(factor) {
    this.visibleBars = Math.max(this.minVisibleBars, Math.min(this.maxVisibleBars, Math.round(this.visibleBars * factor)));
    this.scheduleRender();
  }

  resetZoom() {
    this.visibleBars = 45;
    this.panOffset = 0;
    this.autoFollow = true;
    this._updateAutoFollowButton();
    this.scheduleRender();
  }

  toggleAutoFollow() {
    this.autoFollow = !this.autoFollow;
    if (this.autoFollow) {
      this.panOffset = 0;
    }
    this._updateAutoFollowButton();
    this.scheduleRender();
  }

  _updateAutoFollowButton() {
    const btn = document.getElementById('btn-chart-autofollow');
    if (btn) {
      btn.classList.toggle('active', this.autoFollow);
    }
  }

  toggleIndicator(name) {
    if (this.indicators[name] !== undefined) {
      this.indicators[name] = !this.indicators[name];
      const btn = document.getElementById(`btn-ind-${name}`);
      if (btn) {
        btn.classList.toggle('active', this.indicators[name]);
      }
      this.scheduleRender();
    }
  }

  setData(symbol, candles, timeframe = '1M', activeSignal = null) {
    this.symbol = symbol;
    this.timeframe = timeframe;

    // Filter, sanitize, and validate incoming candles
    const valid = [];
    if (Array.isArray(candles)) {
      for (const c of candles) {
        if (
          c && typeof c.timestamp === 'number' && c.timestamp >= 1000000000 &&
          typeof c.open === 'number' && c.open > 0 &&
          typeof c.close === 'number' && c.close > 0 &&
          typeof c.high === 'number' && typeof c.low === 'number'
        ) {
          valid.push({
            timestamp: Math.floor(c.timestamp),
            open: c.open,
            high: Math.max(c.high, c.open, c.close),
            low: Math.min(c.low, c.open, c.close),
            close: c.close,
            volume: c.volume || 100,
            is_forming: !!c.is_forming
          });
        }
      }
    }

    // Sort strictly in ascending chronological order
    valid.sort((a, b) => a.timestamp - b.timestamp);

    // Deduplicate by timestamp (keeps most recent version of same second)
    const deduped = [];
    for (const c of valid) {
      if (deduped.length === 0 || c.timestamp > deduped[deduped.length - 1].timestamp) {
        deduped.push(c);
      } else if (c.timestamp === deduped[deduped.length - 1].timestamp) {
        deduped[deduped.length - 1] = c;
      }
    }

    this.candles = deduped;
    this.activeSignal = activeSignal;

    if (this.candles.length > 0) {
      this.livePrice = this.candles[this.candles.length - 1].close;
      this._updatePriceBadge(this.livePrice);
    } else {
      this.livePrice = null;
    }

    this.scheduleRender();
  }

  /**
   * Real-time tick aggregation: updates the forming candle or rolls over to a new candle.
   * Robust against clock skew, duplicates, and stalled ticks.
   */
  onLiveTick(symbol, price) {
    if (symbol !== this.symbol || typeof price !== 'number' || isNaN(price) || price <= 0) return;

    // Reject extreme single-tick outliers (>20% for crypto, >4% for FX from active price or candle close)
    const refPrice = this.livePrice || (this.candles && this.candles.length > 0 ? this.candles[this.candles.length - 1].close : null);
    if (refPrice && refPrice > 0) {
      const isCrypto = /BTC|ETH|SOL|XRP/i.test(this.symbol || '');
      const maxJump = isCrypto ? 0.20 : 0.04;
      const diffRatio = Math.abs(price - refPrice) / refPrice;
      if (diffRatio > maxJump) {
        return; // Outlier or corrupt frame: reject
      }
    }

    this.livePrice = price;
    this.lastTickTime = Date.now();
    this._updatePriceBadge(price);

    const tfSeconds = this._getTfSeconds(this.timeframe);
    const nowSec = Math.floor(Date.now() / 1000);
    const currentPeriodBoundary = Math.floor(nowSec / tfSeconds) * tfSeconds;

    if (!this.candles || this.candles.length === 0) {
      this.candles = [{
        timestamp: currentPeriodBoundary,
        open: price,
        high: price,
        low: price,
        close: price,
        volume: 100,
        is_forming: true
      }];
    } else {
      const lastCandle = this.candles[this.candles.length - 1];

      if (lastCandle.timestamp === currentPeriodBoundary) {
        // Active forming candle: update H, L, C, Vol
        lastCandle.close = price;
        lastCandle.high = Math.max(lastCandle.high, price);
        lastCandle.low = Math.min(lastCandle.low, price);
        lastCandle.volume = (lastCandle.volume || 100) + 5;
        lastCandle.is_forming = true;
      } else if (lastCandle.timestamp < currentPeriodBoundary) {
        // Genuine period rollover: seal previous bar and start new candle
        lastCandle.is_forming = false;
        const prevClose = (typeof lastCandle.close === 'number' && lastCandle.close > 0) ? lastCandle.close : price;

        const missedPeriods = Math.floor((currentPeriodBoundary - lastCandle.timestamp) / tfSeconds);
        if (missedPeriods > 1) {
          // If periods were missed (e.g. tab switch), fetch authentic backend history in background
          if (window.pywebview && window.pywebview.api && window.pywebview.api.get_candles_for_chart) {
            window.pywebview.api.get_candles_for_chart(this.symbol, this.timeframe).then(candles => {
              if (candles && candles.length > 0) {
                this.setData(this.symbol, candles, this.timeframe);
              }
            }).catch(() => {});
          }
        }

        const newCandle = {
          timestamp: currentPeriodBoundary,
          open: prevClose,
          high: Math.max(prevClose, price),
          low: Math.min(prevClose, price),
          close: price,
          volume: 100,
          is_forming: true
        };
        this.candles.push(newCandle);

        // Keep rolling buffer within reasonable limits
        if (this.candles.length > 300) {
          this.candles.shift();
        }
      } else {
        // Clock skew guard: lastCandle timestamp is ahead of local period boundary
        lastCandle.close = price;
        lastCandle.high = Math.max(lastCandle.high, price);
        lastCandle.low = Math.min(lastCandle.low, price);
        lastCandle.volume = (lastCandle.volume || 100) + 5;
        lastCandle.is_forming = true;
      }
    }

    // If mouse is not inspecting a past candle, update HUD with latest candle
    if (!this.hoveredCandle && this.candles.length > 0) {
      this._updateHUD(this.candles[this.candles.length - 1]);
    }

    this.scheduleRender();
  }

  /**
   * Seamlessly seals completed candle when official event arrives from backend engine.
   */
  onCandleCompleted(symbol, completedCandle) {
    if (symbol !== this.symbol || !completedCandle) return;
    const tfSeconds = this._getTfSeconds(this.timeframe);
    if (tfSeconds !== 60) return; // Direct 1M events match 1M timeframe

    const ts = Math.floor(completedCandle.timestamp || 0);
    if (ts < 1000000000) return;

    let updated = false;
    for (let i = this.candles.length - 1; i >= 0; i--) {
      if (this.candles[i].timestamp === ts) {
        this.candles[i] = {
          timestamp: ts,
          open: completedCandle.open,
          high: Math.max(completedCandle.high, completedCandle.open, completedCandle.close),
          low: Math.min(completedCandle.low, completedCandle.open, completedCandle.close),
          close: completedCandle.close,
          volume: completedCandle.volume || 100,
          is_forming: false
        };
        updated = true;
        break;
      }
    }
    if (!updated && this.candles.length > 0 && ts > this.candles[this.candles.length - 1].timestamp) {
      this.candles.push({
        timestamp: ts,
        open: completedCandle.open,
        high: Math.max(completedCandle.high, completedCandle.open, completedCandle.close),
        low: Math.min(completedCandle.low, completedCandle.open, completedCandle.close),
        close: completedCandle.close,
        volume: completedCandle.volume || 100,
        is_forming: false
      });
      if (this.candles.length > 300) this.candles.shift();
    }

    // Immediately start the new forming candle for the active minute if not already present
    const nowSec = Math.floor(Date.now() / 1000);
    const nextBoundary = (Math.floor(nowSec / 60)) * 60;
    if (this.candles.length > 0 && this.candles[this.candles.length - 1].timestamp < nextBoundary) {
      const p = completedCandle.close;
      this.candles.push({
        timestamp: nextBoundary,
        open: p,
        high: p,
        low: p,
        close: p,
        volume: 10,
        is_forming: true
      });
      if (this.candles.length > 300) this.candles.shift();
    }

    this.scheduleRender();
  }

  /**
   * Heartbeat check called every second: ensures new candle begins even if no ticks arrive.
   */
  checkPeriodRollover() {
    if (!this.candles || this.candles.length === 0) return;
    const tfSeconds = this._getTfSeconds(this.timeframe);
    const nowSec = Math.floor(Date.now() / 1000);
    const currentPeriodBoundary = Math.floor(nowSec / tfSeconds) * tfSeconds;
    const lastCandle = this.candles[this.candles.length - 1];

    if (lastCandle.timestamp < currentPeriodBoundary) {
      lastCandle.is_forming = false;
      const prevClose = lastCandle.close || this.livePrice || 1.0;

      const missedPeriods = Math.floor((currentPeriodBoundary - lastCandle.timestamp) / tfSeconds);
      if (missedPeriods > 1) {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.get_candles_for_chart) {
          window.pywebview.api.get_candles_for_chart(this.symbol, this.timeframe).then(candles => {
            if (candles && candles.length > 0) {
              this.setData(this.symbol, candles, this.timeframe);
            }
          }).catch(() => {});
        }
      }

      const newCandle = {
        timestamp: currentPeriodBoundary,
        open: prevClose,
        high: prevClose,
        low: prevClose,
        close: prevClose,
        volume: 10,
        is_forming: true
      };
      this.candles.push(newCandle);
      if (this.candles.length > 300) this.candles.shift();
      this.scheduleRender();
    }
  }

  _getTfSeconds(tf) {
    const upper = (tf || '1M').toUpperCase();
    if (upper.includes('3M')) return 180;
    if (upper.includes('5M')) return 300;
    if (upper.includes('15M')) return 900;
    return 60;
  }

  getPrecision(price) {
    if (window.AppState && window.AppState.precisions) {
      if (window.AppState.precisions[this.symbol] !== undefined) {
        return window.AppState.precisions[this.symbol];
      }
      const cleanSym = (this.symbol || '').replace(/\s*\(OTC\)/i, '').trim();
      if (window.AppState.precisions[cleanSym] !== undefined) {
        return window.AppState.precisions[cleanSym];
      }
      if (window.AppState.precisions[cleanSym + ' (OTC)'] !== undefined) {
        return window.AppState.precisions[cleanSym + ' (OTC)'];
      }
    }
    const sym = (this.symbol || '').toUpperCase();
    if (sym.includes('BTC') || sym.includes('ETH') || sym.includes('SOL') || sym.includes('XAU') || 
        sym.includes('INDEX') || sym.includes('STOCK') || sym.includes('US500') || sym.includes('NAS') ||
        sym.includes('BOEING') || sym.includes('APPLE') || sym.includes('TESLA') || sym.includes('AMAZON')) {
      return 2;
    }
    if (sym.includes('JPY')) {
      return 3;
    }
    if (sym.includes('INR') || sym.includes('BRL') || sym.includes('PKR') || 
        sym.includes('BDT') || sym.includes('EGP') || sym.includes('PHP') || 
        sym.includes('TRY') || sym.includes('IDR') || sym.includes('ZAR') || sym.includes('MXN') ||
        sym.includes('ARS') || sym.includes('COP') || sym.includes('NGN') || sym.includes('DZD')) {
      return 4;
    }
    const p = typeof price === 'number' ? price : (this.livePrice || 0);
    if (p >= 1000) return 2;
    if (p >= 50) return 4;
    if (p < 10) return 5;
    return 4;
  }

  _updatePriceBadge(price) {
    const priceEl = document.getElementById('chart-live-price');
    if (priceEl && typeof price === 'number') {
      const decimals = this.getPrecision(price);
      priceEl.textContent = price.toFixed(decimals);
    }
  }

  _updateHUD(candle) {
    if (!candle) {
      const symEl = document.getElementById('hud-symbol');
      if (symEl) symEl.textContent = this.symbol;
      return;
    }
    const decimals = this.getPrecision(candle.close);
    const symEl = document.getElementById('hud-symbol');
    const openEl = document.getElementById('hud-open');
    const highEl = document.getElementById('hud-high');
    const lowEl = document.getElementById('hud-low');
    const closeEl = document.getElementById('hud-close');
    const changeEl = document.getElementById('hud-change');
    const volEl = document.getElementById('hud-volume');

    if (symEl) symEl.textContent = this.symbol;
    if (openEl) openEl.textContent = candle.open.toFixed(decimals);
    if (highEl) highEl.textContent = candle.high.toFixed(decimals);
    if (lowEl) lowEl.textContent = candle.low.toFixed(decimals);
    if (closeEl) closeEl.textContent = candle.close.toFixed(decimals);

    if (changeEl) {
      const diff = candle.close - candle.open;
      const pct = candle.open > 0 ? (diff / candle.open) * 100 : 0;
      const sign = pct >= 0 ? '+' : '';
      changeEl.textContent = `${sign}${pct.toFixed(2)}%`;
      changeEl.className = pct >= 0 ? 'hud-val-up' : 'hud-val-down';
    }

    if (volEl) {
      volEl.textContent = Math.round(candle.volume || 100);
    }
  }

  scheduleRender() {
    if (!this._rafPending) {
      this._rafPending = true;
      requestAnimationFrame(() => {
        this._rafPending = false;
        this.render();
      });
    }
  }

  // Calculation Helpers
  _calcEMA(data, period) {
    if (!data || data.length === 0) return [];
    const k = 2 / (period + 1);
    const ema = [];
    let prev = null;
    for (let i = 0; i < data.length; i++) {
      const c = data[i].close;
      if (i === 0) {
        prev = c;
      } else {
        prev = c * k + prev * (1 - k);
      }
      ema.push(prev);
    }
    return ema;
  }

  _calcRSI(data, period = 14) {
    if (!data || data.length < period + 1) return [];
    const rsi = [];
    let gains = 0;
    let losses = 0;

    for (let i = 1; i <= period; i++) {
      const diff = data[i].close - data[i - 1].close;
      if (diff >= 0) gains += diff;
      else losses -= diff;
    }
    let avgGain = gains / period;
    let avgLoss = losses / period;

    for (let i = 0; i < period; i++) rsi.push(50);
    const firstRS = avgLoss === 0 ? 100 : avgGain / avgLoss;
    rsi.push(100 - 100 / (1 + firstRS));

    for (let i = period + 1; i < data.length; i++) {
      const diff = data[i].close - data[i - 1].close;
      const gain = diff > 0 ? diff : 0;
      const loss = diff < 0 ? -diff : 0;
      avgGain = (avgGain * (period - 1) + gain) / period;
      avgLoss = (avgLoss * (period - 1) + loss) / period;
      const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
      rsi.push(100 - 100 / (1 + rs));
    }
    return rsi;
  }

  _calcPivots(candles) {
    if (!candles || candles.length < 5) return { support: null, resistance: null };
    let highest = -Infinity;
    let lowest = Infinity;
    for (const c of candles) {
      if (c.high > highest) highest = c.high;
      if (c.low < lowest) lowest = c.low;
    }
    return {
      support: lowest !== Infinity ? lowest : null,
      resistance: highest !== -Infinity ? highest : null
    };
  }

  render() {
    if (!this.ctx || !this.width || !this.height) return;
    const ctx = this.ctx;
    const w = this.width;
    const h = this.height;

    // Background Gradient (Dark Quotex Professional Theme)
    const bgGrad = ctx.createLinearGradient(0, 0, 0, h);
    bgGrad.addColorStop(0, '#0a0e17');
    bgGrad.addColorStop(1, '#06090e');
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, w, h);

    if (!this.candles || this.candles.length === 0) {
      ctx.fillStyle = '#64748b';
      ctx.font = '14px "Plus Jakarta Sans", sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(`Awaiting authentic live candlestick stream for ${this.symbol || 'market'}...`, w / 2, h / 2);
      return;
    }

    // Layout Dimensions
    const priceRightMargin = 72;
    const bottomTimeMargin = 26;
    const rsiPaneHeight = this.indicators.rsi ? Math.floor(h * 0.22) : 0;
    const plotW = w - priceRightMargin;
    const plotH = h - bottomTimeMargin - rsiPaneHeight;

    // Viewport bar capacity (defaults to ~45-55 bars, matching Quotex pro terminal)
    const capacitySlots = Math.max(25, this.visibleBars || 48);
    // In Quotex (Image 3), live chart has ~3-4 slots breathing space on right before price scale
    const rightPaddingSlots = 3;
    const candleSlotW = Math.max(8, Math.min(28, plotW / capacitySlots));
    // Candle body width clamped to crisp Quotex standard (never giant boxes!)
    const barW = Math.max(3, Math.min(13, Math.floor(candleSlotW * 0.68)));

    // Determine how many bars can fit across plotW
    const maxFittingBars = Math.max(5, Math.floor(plotW / candleSlotW) - rightPaddingSlots);
    const totalBars = this.candles.length;
    const visCount = Math.min(maxFittingBars, totalBars);

    let endIdx = totalBars - Math.floor(this.panOffset);
    let startIdx = endIdx - visCount;

    if (startIdx < 0) {
      startIdx = 0;
      endIdx = Math.min(visCount, totalBars);
    }
    if (endIdx > totalBars) {
      endIdx = totalBars;
      startIdx = Math.max(0, endIdx - visCount);
    }

    const visibleCandles = this.candles.slice(startIdx, endIdx);
    const visibleCount = visibleCandles.length;
    if (visibleCount === 0) return;

    // Center X calculation for candle i in visibleCandles (0 to visibleCount - 1):
    // In live auto-follow mode, newest candle is on right side with rightPaddingSlots margin
    const rightmostCenter = (plotW - (rightPaddingSlots * candleSlotW) - (candleSlotW / 2)) + (this.panOffset * candleSlotW);
    const getCandleX = (idx) => rightmostCenter - ((visibleCount - 1 - idx) * candleSlotW);

    // Calculate Dynamic Price Range for visible window
    let minPrice = Infinity;
    let maxPrice = -Infinity;
    let maxVolume = 0;

    for (const c of visibleCandles) {
      if (c.low < minPrice) minPrice = c.low;
      if (c.high > maxPrice) maxPrice = c.high;
      if ((c.volume || 100) > maxVolume) maxVolume = c.volume || 100;
    }

    // Include current live price in vertical bounds
    if (this.livePrice !== null && typeof this.livePrice === 'number' && !isNaN(this.livePrice) && this.livePrice > 0) {
      if (this.livePrice < minPrice) minPrice = this.livePrice;
      if (this.livePrice > maxPrice) maxPrice = this.livePrice;
    }

    if (minPrice === maxPrice || minPrice === Infinity || minPrice <= 0) {
      const base = (this.livePrice && this.livePrice > 0) ? this.livePrice : (visibleCandles[0] ? visibleCandles[0].close : 1.0);
      minPrice = base * 0.999;
      maxPrice = base * 1.001;
    }

    // Outlier protection: prevent rogue single-tick spike from flattening visible chart
    const midIdx = Math.floor(visibleCount / 2);
    const medianPrice = (visibleCandles[midIdx] && visibleCandles[midIdx].close > 0) ? visibleCandles[midIdx].close : (this.livePrice || 1.0);
    if (medianPrice > 0) {
      minPrice = Math.max(minPrice, medianPrice * 0.70);
      maxPrice = Math.min(maxPrice, medianPrice * 1.30);
    }

    const padding = (maxPrice - minPrice) * 0.12;
    minPrice -= padding;
    maxPrice += padding;
    const priceRange = maxPrice - minPrice;

    const getY = (price) => plotH - ((price - minPrice) / priceRange) * plotH;

    // Horizontal Price Grid Lines & Right Axis Labels
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;
    const gridSteps = 6;
    const decimals = this.getPrecision(maxPrice);

    for (let i = 0; i <= gridSteps; i++) {
      const p = minPrice + (priceRange / gridSteps) * i;
      const y = getY(p);

      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(plotW, y);
      ctx.stroke();

      // Right Axis Label
      ctx.fillStyle = '#64748b';
      ctx.font = '10px "JetBrains Mono", monospace';
      ctx.textAlign = 'left';
      ctx.fillText(p.toFixed(decimals), plotW + 8, y + 3.5);
    }

    // Right Price Axis Divider Line
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
    ctx.beginPath();
    ctx.moveTo(plotW, 0);
    ctx.lineTo(plotW, plotH);
    ctx.stroke();

    // Bottom Time Axis Divider Line
    ctx.beginPath();
    ctx.moveTo(0, plotH);
    ctx.lineTo(w, plotH);
    ctx.stroke();

    // Volume Histogram Bars (Base)
    if (this.indicators.volume && maxVolume > 0) {
      const maxVolHeight = plotH * 0.16;
      for (let i = 0; i < visibleCount; i++) {
        const c = visibleCandles[i];
        const cx = getCandleX(i);
        if (cx < -candleSlotW || cx > plotW + candleSlotW) continue;
        const vol = c.volume || 100;
        const vH = Math.max(2, (vol / maxVolume) * maxVolHeight);
        const isBull = c.close >= c.open;

        ctx.fillStyle = isBull ? 'rgba(16, 185, 129, 0.22)' : 'rgba(239, 68, 68, 0.22)';
        ctx.fillRect(Math.round(cx - barW / 2), plotH - vH, barW, vH);
      }
    }

    // Dynamic S/R Pivot Lines
    if (this.indicators.pivots) {
      const pivots = this._calcPivots(visibleCandles);
      if (pivots.resistance) {
        const resY = getY(pivots.resistance);
        ctx.strokeStyle = 'rgba(239, 68, 68, 0.6)';
        ctx.setLineDash([4, 4]);
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(0, resY);
        ctx.lineTo(plotW, resY);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.fillStyle = '#ef4444';
        ctx.font = '9px "JetBrains Mono", monospace';
        ctx.textAlign = 'right';
        ctx.fillText('RES ' + pivots.resistance.toFixed(decimals), plotW - 6, resY - 4);
      }
      if (pivots.support) {
        const supY = getY(pivots.support);
        ctx.strokeStyle = 'rgba(16, 185, 129, 0.6)';
        ctx.setLineDash([4, 4]);
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(0, supY);
        ctx.lineTo(plotW, supY);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.fillStyle = '#10b981';
        ctx.font = '9px "JetBrains Mono", monospace';
        ctx.textAlign = 'right';
        ctx.fillText('SUP ' + pivots.support.toFixed(decimals), plotW - 6, supY + 11);
      }
    }

    // EMAs Calculation across entire dataset, mapped to visible indices
    if (this.indicators.ema50) {
      const fullEma50 = this._calcEMA(this.candles, 50);
      this._drawEMALine(fullEma50, startIdx, endIdx, getCandleX, getY, 'rgba(234, 179, 8, 0.85)', 1.5);
    }
    if (this.indicators.ema20) {
      const fullEma20 = this._calcEMA(this.candles, 20);
      this._drawEMALine(fullEma20, startIdx, endIdx, getCandleX, getY, 'rgba(0, 240, 255, 0.95)', 1.6);
    }

    // Render Candlesticks
    let hoveredCandle = null;
    let hoveredX = -1;
    let lastTimeLabelX = -100;

    for (let i = 0; i < visibleCount; i++) {
      const c = visibleCandles[i];
      const cx = getCandleX(i);
      if (cx < -candleSlotW || cx > plotW + candleSlotW) continue;

      const isBull = c.close >= c.open;
      const color = isBull ? '#00e676' : '#ff1744';

      // Check mouse hover
      if (Math.abs(this.mouseX - cx) <= candleSlotW / 2) {
        hoveredCandle = c;
        hoveredX = cx;
      }

      // High-Low Wick: crisp, centered 1.2px line
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      const wickX = Math.round(cx) + 0.5;
      let wickYHigh = getY(c.high);
      let wickYLow = getY(c.low);
      // Flat doji protection: if high == low (flat candle), provide subtle 2.5px vertical spine
      if (Math.abs(wickYLow - wickYHigh) < 1.0) {
        wickYHigh -= 2.5;
        wickYLow += 2.5;
      }
      ctx.moveTo(wickX, wickYHigh);
      ctx.lineTo(wickX, wickYLow);
      ctx.stroke();

      // Candle Body: centered, proportional (clamped 3-13px)
      const topY = getY(Math.max(c.open, c.close));
      const bottomY = getY(Math.min(c.open, c.close));
      const bodyH = Math.max(2.0, bottomY - topY);

      ctx.fillStyle = color;
      ctx.fillRect(Math.round(cx - barW / 2), topY, barW, bodyH);

      // Time Axis Label (strictly non-overlapping with pixel distance guard)
      const isLastBar = (i === visibleCount - 1);
      const distFromLast = cx - lastTimeLabelX;

      if ((distFromLast >= 60 && (!isLastBar || distFromLast >= 45)) || (isLastBar && distFromLast >= 55)) {
        if (cx >= 20 && cx <= plotW - 10) {
          const dt = new Date(c.timestamp * 1000);
          const timeStr = dt.toTimeString().substring(0, 5);
          ctx.fillStyle = '#94a3b8';
          ctx.font = '10px "JetBrains Mono", monospace';
          ctx.textAlign = 'center';
          ctx.fillText(timeStr, cx, plotH + 16);
          lastTimeLabelX = cx;

          // Subtle vertical time grid tick
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
          ctx.beginPath();
          ctx.moveTo(cx, 0);
          ctx.lineTo(cx, plotH);
          ctx.stroke();
        }
      }
    }

    // Forming Candle Countdown Timer (Quotex style)
    const lastVisibleBar = visibleCandles[visibleCount - 1];
    if (lastVisibleBar && (endIdx === totalBars && this.panOffset <= 1)) {
      const formX = getCandleX(visibleCount - 1);
      if (formX >= 0 && formX <= plotW) {
        // Vertical dashed guideline at active bar
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
        ctx.setLineDash([3, 3]);
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(formX, 0);
        ctx.lineTo(formX, plotH);
        ctx.stroke();
        ctx.setLineDash([]);

        // Timer badge
        const nowSec = Math.floor(Date.now() / 1000);
        const secLeft = Math.max(0, 60 - (nowSec % 60));
        const timerText = `00:${secLeft < 10 ? '0' : ''}${secLeft}`;
        const badgeW = 44;
        const badgeH = 16;
        const badgeY = Math.max(10, Math.min(plotH - 25, getY(lastVisibleBar.close) - 26));

        ctx.fillStyle = '#0f172a';
        ctx.fillRect(formX - badgeW / 2, badgeY, badgeW, badgeH);
        ctx.strokeStyle = 'rgba(0, 240, 255, 0.6)';
        ctx.lineWidth = 1;
        ctx.strokeRect(formX - badgeW / 2, badgeY, badgeW, badgeH);
        ctx.fillStyle = '#00f0ff';
        ctx.font = 'bold 9px "JetBrains Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText(timerText, formX, badgeY + 11.5);
      }
    }

    // Live Current Price Horizontal Dashed Line & Badge
    if (this.livePrice !== null) {
      const liveY = getY(this.livePrice);
      if (liveY >= 0 && liveY <= plotH) {
        ctx.strokeStyle = 'rgba(0, 240, 255, 0.75)';
        ctx.setLineDash([3, 3]);
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(0, liveY);
        ctx.lineTo(plotW, liveY);
        ctx.stroke();
        ctx.setLineDash([]);

        // Right Axis Live Price Pill
        ctx.fillStyle = '#00f0ff';
        ctx.fillRect(plotW + 2, liveY - 9, priceRightMargin - 4, 18);
        ctx.fillStyle = '#070a10';
        ctx.font = 'bold 10px "JetBrains Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText(this.livePrice.toFixed(decimals), plotW + priceRightMargin / 2, liveY + 3.5);
      }
    }

    // Active Signal Strike Line & Target Marker
    if (this.activeSignal && this.activeSignal.entry_price) {
      const isCall = (this.activeSignal.direction || '').toUpperCase() === 'CALL';
      const sigColor = isCall ? '#00e676' : '#ff1744';
      const sigY = getY(this.activeSignal.entry_price);

      if (sigY >= 0 && sigY <= plotH) {
        ctx.strokeStyle = sigColor;
        ctx.setLineDash([6, 3]);
        ctx.lineWidth = 1.8;
        ctx.beginPath();
        ctx.moveTo(0, sigY);
        ctx.lineTo(plotW, sigY);
        ctx.stroke();
        ctx.setLineDash([]);

        // Badge on chart
        ctx.fillStyle = sigColor;
        ctx.fillRect(plotW - 140, sigY - 10, 134, 20);
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 10px "JetBrains Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText(`TARGET ${isCall ? '▲ CALL' : '▼ PUT'} @ ${this.activeSignal.entry_price.toFixed(decimals)}`, plotW - 73, sigY + 4);
      }
    }

    // RSI Sub-Chart Rendering (if active)
    if (this.indicators.rsi) {
      this._renderRSIPane(startIdx, endIdx, getCandleX, plotW, plotH, rsiPaneHeight, w, h);
    }

    // Crosshair & Inspection Tooltip HUD
    if (this.mouseX >= 0 && this.mouseX <= plotW && this.mouseY >= 0 && this.mouseY <= plotH) {
      const cx = hoveredX > 0 ? hoveredX : this.mouseX;
      const cy = this.mouseY;

      // Crosshair Lines
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.28)';
      ctx.setLineDash([4, 4]);
      ctx.lineWidth = 1;

      // Vertical line
      ctx.beginPath();
      ctx.moveTo(cx, 0);
      ctx.lineTo(cx, plotH + rsiPaneHeight);
      ctx.stroke();

      // Horizontal line
      ctx.beginPath();
      ctx.moveTo(0, cy);
      ctx.lineTo(plotW, cy);
      ctx.stroke();
      ctx.setLineDash([]);

      // Floating Price Badge on Right Axis
      const hoverPrice = maxPrice - (cy / plotH) * priceRange;
      ctx.fillStyle = '#334155';
      ctx.fillRect(plotW + 2, cy - 9, priceRightMargin - 4, 18);
      ctx.fillStyle = '#f8fafc';
      ctx.font = '10px "JetBrains Mono", monospace';
      ctx.textAlign = 'center';
      ctx.fillText(hoverPrice.toFixed(decimals), plotW + priceRightMargin / 2, cy + 3.5);

      // Time Badge at Bottom Axis
      if (hoveredCandle) {
        const dt = new Date(hoveredCandle.timestamp * 1000);
        const timeStr = dt.toLocaleTimeString();
        ctx.fillStyle = '#334155';
        ctx.fillRect(cx - 36, plotH + 3, 72, 18);
        ctx.fillStyle = '#f8fafc';
        ctx.font = '10px "JetBrains Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText(timeStr, cx, plotH + 15);
      }
    }

    // Update HUD with hovered candle or latest candle
    this.hoveredCandle = hoveredCandle;
    if (hoveredCandle) {
      this._updateHUD(hoveredCandle);
    }
  }

  _drawEMALine(fullData, startIdx, endIdx, getCandleX, getY, color, width) {
    if (!fullData || fullData.length === 0) return;
    const ctx = this.ctx;
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.beginPath();

    let started = false;
    for (let i = startIdx; i < endIdx; i++) {
      const val = fullData[i];
      if (val === undefined || val === null) continue;
      const x = typeof getCandleX === 'function' ? getCandleX(i - startIdx) : ((i - startIdx) * getCandleX + getCandleX / 2);
      if (x < -30 || x > this.width + 30) continue;
      const y = getY(val);

      if (!started) {
        ctx.moveTo(x, y);
        started = true;
      } else {
        ctx.lineTo(x, y);
      }
    }
    if (started) ctx.stroke();
  }

  _renderRSIPane(startIdx, endIdx, getCandleX, plotW, plotH, rsiH, fullW, fullH) {
    const ctx = this.ctx;
    const rsiTop = plotH + 24;
    const rsiBottom = fullH - 8;
    const rsiPlotH = rsiBottom - rsiTop;

    // Divider Line
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, rsiTop);
    ctx.lineTo(fullW, rsiTop);
    ctx.stroke();

    // RSI Reference Bands (70 / 30)
    const y70 = rsiTop + rsiPlotH * 0.30;
    const y30 = rsiTop + rsiPlotH * 0.70;

    ctx.strokeStyle = 'rgba(239, 68, 68, 0.35)';
    ctx.setLineDash([2, 2]);
    ctx.beginPath();
    ctx.moveTo(0, y70);
    ctx.lineTo(plotW, y70);
    ctx.stroke();

    ctx.strokeStyle = 'rgba(16, 185, 129, 0.35)';
    ctx.beginPath();
    ctx.moveTo(0, y30);
    ctx.lineTo(plotW, y30);
    ctx.stroke();
    ctx.setLineDash([]);

    // Labels
    ctx.fillStyle = '#94a3b8';
    ctx.font = '9px "JetBrains Mono", monospace';
    ctx.textAlign = 'left';
    ctx.fillText('RSI (14)', 8, rsiTop + 13);
    ctx.fillText('70', plotW + 6, y70 + 3);
    ctx.fillText('30', plotW + 6, y30 + 3);

    // Plot RSI Curve
    const fullRsi = this._calcRSI(this.candles, 14);
    if (fullRsi.length > 0) {
      ctx.strokeStyle = '#c084fc';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      let started = false;

      for (let i = startIdx; i < endIdx; i++) {
        const val = fullRsi[i];
        if (val === undefined || val === null) continue;
        const x = typeof getCandleX === 'function' ? getCandleX(i - startIdx) : ((i - startIdx) * getCandleX + getCandleX / 2);
        if (x < -30 || x > plotW + 30) continue;
        const y = rsiTop + (1 - (val / 100)) * rsiPlotH;

        if (!started) {
          ctx.moveTo(x, y);
          started = true;
        } else {
          ctx.lineTo(x, y);
        }
      }
      if (started) ctx.stroke();
    }
  }
}

// Global Chart Controller instance
window.LiveChartEngine = {
  instance: null,
  activeSymbol: 'EUR/USD (OTC)',
  activeTimeframe: '1M',

  _heartbeatInterval: null,
  _lastMetaTime: 0,

  init() {
    if (!this.instance && document.getElementById('liveStationCanvas')) {
      this.instance = new InteractiveChartEngine('liveStationCanvas');
    }
    if (!this._heartbeatInterval) {
      this._heartbeatInterval = setInterval(() => {
        if (this.instance) {
          this.instance.checkPeriodRollover();
        }
      }, 1000);
    }
  },

  setSymbol(symbol, timeframe = '1M', activeSignal = null) {
    this.init();
    if (!symbol) return;
    this.activeSymbol = symbol;
    this.activeTimeframe = timeframe;

    // Prime Quotex broker WebSocket to immediately stream ticks and history for newly chosen asset
    const wsCode = (window.AppState && window.AppState.symbolsToWs && window.AppState.symbolsToWs[symbol]) || symbol;
    if (window.__tp_prime_asset) {
      window.__tp_prime_asset(wsCode);
    }

    // Update Dropdown Selection if present
    const sel = document.getElementById('chart-asset-select');
    if (sel && sel.value !== symbol) {
      sel.value = symbol;
    }

    // Update Quick Watchlist active pill
    if (window.populateChartQuickWatchlist) {
      window.populateChartQuickWatchlist();
    }

    // Update live source badge and payout badge
    this.updateAssetMeta(symbol);

    // Refresh candles from python backend
    this.refresh(activeSignal);
  },

  updateAssetMeta(symbol) {
    if (!symbol) return;
    const now = Date.now();
    if (now - this._lastMetaTime < 400) return;
    this._lastMetaTime = now;

    const isOtc = symbol.includes('(OTC)') || symbol.toLowerCase().includes('_otc');
    const sourceEl = document.getElementById('chart-live-source');
    if (sourceEl) {
      sourceEl.textContent = isOtc ? 'QUOTEX OTC' : 'REAL MARKET';
      sourceEl.className = isOtc ? 'feed-badge feed-quotex' : 'feed-badge feed-real';
    }

    const payoutEl = document.getElementById('chart-live-payout');
    if (payoutEl && window.AppState && window.AppState.payouts) {
      const payout = window.AppState.payouts[symbol];
      if (payout !== undefined && payout !== null) {
        payoutEl.textContent = `${payout}%`;
        let pClass = 'payout-mid';
        if (payout >= 85) pClass = 'payout-high';
        else if (payout < 80) pClass = 'payout-low';
        payoutEl.className = `payout-badge ${pClass}`;
      } else {
        payoutEl.textContent = isOtc ? '85%' : '80%';
      }
    }

    // Check if active signal exists for this pair
    const banner = document.getElementById('chart-signal-banner');
    if (banner) {
      let foundSig = null;
      if (window.AppState && Array.isArray(window.AppState.signals)) {
        foundSig = window.AppState.signals.find(s => s.asset_symbol === symbol && !s.resolved);
      }
      if (foundSig) {
        banner.style.display = 'flex';
        const dirEl = document.getElementById('chart-signal-dir');
        const entryEl = document.getElementById('chart-signal-entry');
        const pipsEl = document.getElementById('chart-signal-pips');
        const confEl = document.getElementById('chart-signal-conf');
        const isCall = (foundSig.direction || '').toUpperCase() === 'CALL';

        if (dirEl) {
          dirEl.textContent = isCall ? 'CALL ▲' : 'PUT ▼';
          dirEl.className = isCall ? 'signal-tag tag-call' : 'signal-tag tag-put';
        }
        if (entryEl) entryEl.textContent = `Entry: ${foundSig.entry_price}`;
        if (confEl) confEl.textContent = `${Math.round(foundSig.confluence_score || 85)}% Confluence`;
        if (pipsEl && window.AppState && window.AppState.prices[symbol]) {
          const cur = window.AppState.prices[symbol];
          const diff = isCall ? (cur - foundSig.entry_price) : (foundSig.entry_price - cur);
          pipsEl.textContent = diff >= 0 ? `▲ +${(diff * 10000).toFixed(1)} Pips ITM` : `▼ -${(Math.abs(diff) * 10000).toFixed(1)} Pips OTM`;
        }
      } else {
        banner.style.display = 'none';
      }
    }
  },

  switchTimeframe(tf) {
    this.activeTimeframe = tf;
    if (this.instance) {
      this.instance.timeframe = tf;
    }
    document.querySelectorAll('.btn-station-tf').forEach(b => b.classList.remove('active'));
    const btn = document.getElementById(`station-tf-${tf.toLowerCase()}`);
    if (btn) btn.classList.add('active');

    this.refresh();
  },

  onLiveTick(symbol, price) {
    if (this.instance && symbol === this.activeSymbol) {
      this.instance.onLiveTick(symbol, price);
      this.updateAssetMeta(symbol);
    }
  },

  onCandleCompleted(payload) {
    if (!payload || !this.instance) return;
    const symbol = payload.symbol;
    const candle = payload.candle;
    if (symbol === this.activeSymbol && candle) {
      this.instance.onCandleCompleted(symbol, candle);
    }
  },

  refresh(activeSignal = null) {
    if (!this.activeSymbol) return;
    if (window.pywebview && window.pywebview.api && window.pywebview.api.get_candles_for_chart) {
      window.pywebview.api.get_candles_for_chart(this.activeSymbol, this.activeTimeframe)
        .then(candles => {
          if (this.instance) {
            this.instance.setData(this.activeSymbol, candles, this.activeTimeframe, activeSignal);
          }
        })
        .catch(err => console.debug('[LIVE_CHART] Error loading candles:', err));
    }
  },

  resize() {
    if (this.instance) {
      this.instance.resize();
    }
  }
};

// Global Handler Functions called directly from index.html onclick/onchange
window.onStationAssetChanged = function(symbol) {
  if (window.LiveChartEngine) {
    window.LiveChartEngine.setSymbol(symbol, window.LiveChartEngine.activeTimeframe);
  }
};

window.switchStationTf = function(tf) {
  if (window.LiveChartEngine) {
    window.LiveChartEngine.switchTimeframe(tf);
  }
};

window.toggleStationIndicator = function(name) {
  if (window.LiveChartEngine && window.LiveChartEngine.instance) {
    window.LiveChartEngine.instance.toggleIndicator(name);
  }
};

window.zoomStationChart = function(factor) {
  if (window.LiveChartEngine && window.LiveChartEngine.instance) {
    window.LiveChartEngine.instance.zoom(factor);
  }
};

window.resetStationChartZoom = function() {
  if (window.LiveChartEngine && window.LiveChartEngine.instance) {
    window.LiveChartEngine.instance.resetZoom();
  }
};

window.toggleStationAutoFollow = function() {
  if (window.LiveChartEngine && window.LiveChartEngine.instance) {
    window.LiveChartEngine.instance.toggleAutoFollow();
  }
};

// Maintain compatibility with existing TradePulseChart calls
window.TradePulseChart = {
  open(symbol, timeframe = '1M', activeSignal = null) {
    if (window.switchView) {
      window.switchView('chart');
    }
    if (window.LiveChartEngine) {
      window.LiveChartEngine.setSymbol(symbol, timeframe, activeSignal);
    }
  },
  close() {},
  refresh() {
    if (window.LiveChartEngine) {
      window.LiveChartEngine.refresh();
    }
  }
};

// Immediate live chart synchronizer when authentic Quotex candles are received
window.onHistoryBootstrapped = function(payload) {
  if (!payload || !payload.symbol || !payload.candles) return;
  if (window.LiveChartEngine && window.LiveChartEngine.activeSymbol === payload.symbol) {
    if (window.LiveChartEngine.instance) {
      window.LiveChartEngine.instance.setData(payload.symbol, payload.candles, window.LiveChartEngine.activeTimeframe || '1M');
      console.log(`[LIVE CHART] 1:1 synchronized ${payload.candles.length} authentic Quotex bars for ${payload.symbol}`);
    }
  }
};
