/**
 * TradePulse Personal Edition — Dynamic Multi-Instance Indicator Stack & Pill Engine
 * Supports arbitrary stacking of any of the 27 institutional indicators.
 * Provides Quotex-style floating chart pills, step controls, multi-cloud Bollinger renders, and live synchronization.
 */

const INDICATOR_REGISTRY = {
  BOLLINGER: {
    name: 'Bollinger Bands',
    type: 'overlay',
    badge: 'VOLATILITY',
    icon: '🎯',
    color: '#00f0ff',
    defaultParams: { period: 20, deviation: 2.0, show_cloud: true, min_body_protrusion: 20 },
    paramsConfig: [
      { key: 'period', label: 'Period', type: 'number', min: 2, max: 100, step: 1, default: 20 },
      { key: 'deviation', label: 'Deviation', type: 'number', min: 0.1, max: 10, step: 0.1, default: 2.0 },
      { key: 'min_body_protrusion', label: 'Min Body Protrusion (%)', type: 'number', min: 0, max: 100, step: 5, default: 20 }
    ],
    supportsCloud: true
  },
  EMA: {
    name: 'Moving Average (SMA/EMA)',
    type: 'overlay',
    badge: 'TREND',
    icon: '📈',
    color: '#00f0ff',
    defaultParams: { period: 20, ma_type: 'EMA' },
    paramsConfig: [
      { key: 'period', label: 'Period', type: 'number', min: 2, max: 500, step: 1, default: 20 },
      { key: 'ma_type', label: 'Type', type: 'select', options: ['EMA', 'SMA'], default: 'EMA' }
    ]
  },
  ALLIGATOR: {
    name: 'Alligator (Bill Williams)',
    type: 'overlay',
    badge: 'TREND',
    icon: '🐊',
    color: '#10b981',
    defaultParams: { jaws_period: 13, teeth_period: 8, lips_period: 5 },
    paramsConfig: [
      { key: 'jaws_period', label: 'Jaws Period', type: 'number', min: 5, max: 50, step: 1, default: 13 },
      { key: 'teeth_period', label: 'Teeth Period', type: 'number', min: 3, max: 30, step: 1, default: 8 },
      { key: 'lips_period', label: 'Lips Period', type: 'number', min: 2, max: 20, step: 1, default: 5 }
    ]
  },
  ENVELOPES: {
    name: 'Envelopes',
    type: 'overlay',
    badge: 'BANDS',
    icon: '✉️',
    color: '#f59e0b',
    defaultParams: { period: 14, deviation: 0.1, show_cloud: true },
    paramsConfig: [
      { key: 'period', label: 'Period', type: 'number', min: 2, max: 100, step: 1, default: 14 },
      { key: 'deviation', label: 'Deviation (%)', type: 'number', min: 0.01, max: 5.0, step: 0.01, default: 0.1 }
    ],
    supportsCloud: true
  },
  FRACTAL: {
    name: 'Fractal',
    type: 'overlay',
    badge: 'REVERSAL',
    icon: '🔺',
    color: '#ec4899',
    defaultParams: { period: 5 },
    paramsConfig: [
      { key: 'period', label: 'Period', type: 'number', min: 3, max: 15, step: 2, default: 5 }
    ]
  },
  ICHIMOKU: {
    name: 'Ichimoku Kumo Cloud',
    type: 'overlay',
    badge: 'TREND',
    icon: '☁️',
    color: '#8b5cf6',
    defaultParams: { tenkan: 9, kijun: 26, senkou_b: 52, show_cloud: true },
    paramsConfig: [
      { key: 'tenkan', label: 'Tenkan-sen', type: 'number', min: 3, max: 50, step: 1, default: 9 },
      { key: 'kijun', label: 'Kijun-sen', type: 'number', min: 5, max: 100, step: 1, default: 26 },
      { key: 'senkou_b', label: 'Senkou Span B', type: 'number', min: 10, max: 200, step: 1, default: 52 }
    ],
    supportsCloud: true
  },
  KELTNER: {
    name: 'Keltner Channel',
    type: 'overlay',
    badge: 'CHANNEL',
    icon: '🛡️',
    color: '#06b6d4',
    defaultParams: { ema_period: 20, atr_period: 10, multiplier: 1.5, show_cloud: true },
    paramsConfig: [
      { key: 'ema_period', label: 'EMA Period', type: 'number', min: 5, max: 100, step: 1, default: 20 },
      { key: 'atr_period', label: 'ATR Period', type: 'number', min: 2, max: 50, step: 1, default: 10 },
      { key: 'multiplier', label: 'ATR Multiplier', type: 'number', min: 0.5, max: 5.0, step: 0.1, default: 1.5 }
    ],
    supportsCloud: true
  },
  DONCHIAN: {
    name: 'Donchian Channel',
    type: 'overlay',
    badge: 'CHANNEL',
    icon: '📦',
    color: '#eab308',
    defaultParams: { period: 20, show_cloud: true },
    paramsConfig: [
      { key: 'period', label: 'Period', type: 'number', min: 5, max: 100, step: 1, default: 20 }
    ],
    supportsCloud: true
  },
  SUPERTREND: {
    name: 'Supertrend',
    type: 'overlay',
    badge: 'TREND',
    icon: '🚀',
    color: '#10b981',
    defaultParams: { atr_period: 10, multiplier: 3.0 },
    paramsConfig: [
      { key: 'atr_period', label: 'ATR Period', type: 'number', min: 2, max: 50, step: 1, default: 10 },
      { key: 'multiplier', label: 'Multiplier', type: 'number', min: 0.5, max: 10.0, step: 0.1, default: 3.0 }
    ]
  },
  PSAR: {
    name: 'Parabolic SAR',
    type: 'overlay',
    badge: 'MOMENTUM',
    icon: '⚡',
    color: '#f43f5e',
    defaultParams: { step: 0.02, max_step: 0.2 },
    paramsConfig: [
      { key: 'step', label: 'Acceleration Step', type: 'number', min: 0.005, max: 0.1, step: 0.005, default: 0.02 },
      { key: 'max_step', label: 'Maximum Step', type: 'number', min: 0.05, max: 0.5, step: 0.01, default: 0.2 }
    ]
  },
  ZIGZAG: {
    name: 'Zig Zag',
    type: 'overlay',
    badge: 'SWING',
    icon: '⚡',
    color: '#ec4899',
    defaultParams: { deviation: 5, depth: 12 },
    paramsConfig: [
      { key: 'deviation', label: 'Deviation (%)', type: 'number', min: 1, max: 20, step: 1, default: 5 },
      { key: 'depth', label: 'Depth (Bars)', type: 'number', min: 3, max: 50, step: 1, default: 12 }
    ]
  },
  RSI: {
    name: 'Relative Strength Index (RSI)',
    type: 'oscillator',
    badge: 'MOMENTUM',
    icon: '⚡',
    color: '#8b5cf6',
    defaultParams: { period: 14, overbought: 70, oversold: 30 },
    paramsConfig: [
      { key: 'period', label: 'Period', type: 'number', min: 2, max: 50, step: 1, default: 14 },
      { key: 'overbought', label: 'Overbought Level', type: 'number', min: 50, max: 95, step: 1, default: 70 },
      { key: 'oversold', label: 'Oversold Level', type: 'number', min: 5, max: 50, step: 1, default: 30 }
    ]
  },
  STOCHASTIC: {
    name: 'Stochastic Oscillator',
    type: 'oscillator',
    badge: 'MOMENTUM',
    icon: '🎯',
    color: '#00f0ff',
    defaultParams: { k_period: 14, d_period: 3, overbought: 80, oversold: 20 },
    paramsConfig: [
      { key: 'k_period', label: '%K Period', type: 'number', min: 2, max: 50, step: 1, default: 14 },
      { key: 'd_period', label: '%D Period', type: 'number', min: 1, max: 20, step: 1, default: 3 },
      { key: 'overbought', label: 'Overbought', type: 'number', min: 60, max: 95, step: 1, default: 80 },
      { key: 'oversold', label: 'Oversold', type: 'number', min: 5, max: 40, step: 1, default: 20 }
    ]
  },
  MACD: {
    name: 'MACD Histogram',
    type: 'oscillator',
    badge: 'TREND',
    icon: '📊',
    color: '#00f59b',
    defaultParams: { fast_period: 12, slow_period: 26, signal_period: 9 },
    paramsConfig: [
      { key: 'fast_period', label: 'Fast Period', type: 'number', min: 2, max: 50, step: 1, default: 12 },
      { key: 'slow_period', label: 'Slow Period', type: 'number', min: 5, max: 100, step: 1, default: 26 },
      { key: 'signal_period', label: 'Signal Period', type: 'number', min: 2, max: 30, step: 1, default: 9 }
    ]
  },
  ADX: {
    name: 'ADX / DMI',
    type: 'oscillator',
    badge: 'STRENGTH',
    icon: '🏹',
    color: '#f59e0b',
    defaultParams: { period: 14, min_adx: 25 },
    paramsConfig: [
      { key: 'period', label: 'Period', type: 'number', min: 5, max: 50, step: 1, default: 14 },
      { key: 'min_adx', label: 'Threshold', type: 'number', min: 10, max: 60, step: 1, default: 25 }
    ]
  },
  AROON: {
    name: 'Aroon',
    type: 'oscillator',
    badge: 'TREND',
    icon: '📐',
    color: '#06b6d4',
    defaultParams: { period: 14 },
    paramsConfig: [
      { key: 'period', label: 'Period', type: 'number', min: 5, max: 50, step: 1, default: 14 }
    ]
  },
  AO: {
    name: 'Awesome Oscillator (AO)',
    type: 'oscillator',
    badge: 'MOMENTUM',
    icon: '🔥',
    color: '#ec4899',
    defaultParams: { fast_period: 5, slow_period: 34 },
    paramsConfig: [
      { key: 'fast_period', label: 'Fast Period', type: 'number', min: 2, max: 20, step: 1, default: 5 },
      { key: 'slow_period', label: 'Slow Period', type: 'number', min: 10, max: 60, step: 1, default: 34 }
    ]
  },
  BULLS_BEARS: {
    name: 'Bulls & Bears Power (Elder Ray)',
    type: 'oscillator',
    badge: 'POWER',
    icon: '🐂',
    color: '#10b981',
    defaultParams: { period: 13 },
    paramsConfig: [
      { key: 'period', label: 'Period', type: 'number', min: 3, max: 50, step: 1, default: 13 }
    ]
  },
  CCI: {
    name: 'Commodity Channel Index (CCI)',
    type: 'oscillator',
    badge: 'CYCLE',
    icon: '🧭',
    color: '#3b82f6',
    defaultParams: { period: 20, level: 100 },
    paramsConfig: [
      { key: 'period', label: 'Period', type: 'number', min: 5, max: 100, step: 1, default: 20 },
      { key: 'level', label: 'Boundary Level', type: 'number', min: 50, max: 300, step: 10, default: 100 }
    ]
  },
  DEMARKER: {
    name: 'DeMarker',
    type: 'oscillator',
    badge: 'EXHAUSTION',
    icon: '🔬',
    color: '#f43f5e',
    defaultParams: { period: 14, overbought: 0.7, oversold: 0.3 },
    paramsConfig: [
      { key: 'period', label: 'Period', type: 'number', min: 3, max: 50, step: 1, default: 14 },
      { key: 'overbought', label: 'Overbought', type: 'number', min: 0.5, max: 0.95, step: 0.05, default: 0.7 },
      { key: 'oversold', label: 'Oversold', type: 'number', min: 0.05, max: 0.5, step: 0.05, default: 0.3 }
    ]
  },
  ATR: {
    name: 'Average True Range (ATR)',
    type: 'oscillator',
    badge: 'VOLATILITY',
    icon: '🌊',
    color: '#a855f7',
    defaultParams: { period: 14 },
    paramsConfig: [
      { key: 'period', label: 'Period', type: 'number', min: 2, max: 50, step: 1, default: 14 }
    ]
  },
  MOMENTUM: {
    name: 'Momentum',
    type: 'oscillator',
    badge: 'VELOCITY',
    icon: '💨',
    color: '#00f0ff',
    defaultParams: { period: 10 },
    paramsConfig: [
      { key: 'period', label: 'Period', type: 'number', min: 2, max: 50, step: 1, default: 10 }
    ]
  },
  ROC: {
    name: 'Rate of Change (ROC)',
    type: 'oscillator',
    badge: 'MOMENTUM',
    icon: '🎢',
    color: '#f59e0b',
    defaultParams: { period: 12 },
    paramsConfig: [
      { key: 'period', label: 'Period', type: 'number', min: 2, max: 50, step: 1, default: 12 }
    ]
  },
  WILLIAMS_R: {
    name: 'Williams %R',
    type: 'oscillator',
    badge: 'SNIPER',
    icon: '🎯',
    color: '#ec4899',
    defaultParams: { period: 14, overbought: -20, oversold: -80 },
    paramsConfig: [
      { key: 'period', label: 'Period', type: 'number', min: 3, max: 50, step: 1, default: 14 },
      { key: 'overbought', label: 'Overbought', type: 'number', min: -50, max: -5, step: 5, default: -20 },
      { key: 'oversold', label: 'Oversold', type: 'number', min: -95, max: -50, step: 5, default: -80 }
    ]
  },
  VORTEX: {
    name: 'Vortex Indicator',
    type: 'oscillator',
    badge: 'DIRECTION',
    icon: '🌀',
    color: '#10b981',
    defaultParams: { period: 14 },
    paramsConfig: [
      { key: 'period', label: 'Period', type: 'number', min: 3, max: 50, step: 1, default: 14 }
    ]
  },
  STC: {
    name: 'Schaff Trend Cycle',
    type: 'oscillator',
    badge: 'CYCLE',
    icon: '🎛️',
    color: '#8b5cf6',
    defaultParams: { fast_period: 23, slow_period: 50, cycle_period: 10 },
    paramsConfig: [
      { key: 'fast_period', label: 'Fast Period', type: 'number', min: 5, max: 50, step: 1, default: 23 },
      { key: 'slow_period', label: 'Slow Period', type: 'number', min: 20, max: 100, step: 1, default: 50 },
      { key: 'cycle_period', label: 'Cycle Period', type: 'number', min: 3, max: 30, step: 1, default: 10 }
    ]
  },
  VOLUME_OSC: {
    name: 'Volume Oscillator',
    type: 'oscillator',
    badge: 'VOLUME',
    icon: '🔊',
    color: '#f59e0b',
    defaultParams: { short_period: 5, long_period: 10 },
    paramsConfig: [
      { key: 'short_period', label: 'Short Period', type: 'number', min: 2, max: 20, step: 1, default: 5 },
      { key: 'long_period', label: 'Long Period', type: 'number', min: 5, max: 50, step: 1, default: 10 }
    ]
  }
};

const COLOR_PALETTE = ['#00f0ff', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#3b82f6', '#f43f5e', '#14b8a6'];

// Active Dynamic Strategy Indicator Instances
let strategyIndicatorInstances = [];

function toggleIndicatorCatalogDropdown(e) {
  if (e) e.stopPropagation();
  const dropdown = document.getElementById('indicator-catalog-dropdown');
  if (!dropdown) return;
  dropdown.classList.toggle('show');
}

// Close catalog dropdown on outside click
document.addEventListener('click', (e) => {
  const dropdown = document.getElementById('indicator-catalog-dropdown');
  const btn = document.getElementById('btn-add-indicator-dropdown');
  if (dropdown && dropdown.classList.contains('show')) {
    if (!dropdown.contains(e.target) && (!btn || !btn.contains(e.target))) {
      dropdown.classList.remove('show');
    }
  }
});

function addIndicatorInstance(type, customParams = null, autoRender = true) {
  const meta = INDICATOR_REGISTRY[type.toUpperCase()];
  if (!meta) return;

  const instanceCount = strategyIndicatorInstances.filter(i => i.type.toUpperCase() === type.toUpperCase()).length;
  const instanceNumber = instanceCount + 1;
  const id = `inst_${type.toLowerCase()}_${Date.now()}_${Math.random().toString(36).substr(2, 4)}`;

  // Default color cycle
  const colorIndex = (strategyIndicatorInstances.length) % COLOR_PALETTE.length;
  const chosenColor = customParams?.color || (instanceCount === 1 && type === 'BOLLINGER' ? '#ec4899' : (meta.color || COLOR_PALETTE[colorIndex]));

  const params = Object.assign({}, meta.defaultParams, customParams || {});
  params.color = chosenColor;

  const instance = {
    id: id,
    type: type.toUpperCase(),
    name: meta.name,
    instanceNumber: instanceNumber,
    color: chosenColor,
    enabled: true,
    visibleOnChart: true,
    params: params
  };

  strategyIndicatorInstances.push(instance);

  const dropdown = document.getElementById('indicator-catalog-dropdown');
  if (dropdown) dropdown.classList.remove('show');

  if (autoRender) {
    renderIndicatorCards();
    syncChartIndicatorPills();
    triggerStrategyRecalculate();
  }
  return instance;
}

function duplicateIndicatorInstance(instanceId) {
  const orig = strategyIndicatorInstances.find(i => i.id === instanceId);
  if (!orig) return;
  const copyParams = Object.assign({}, orig.params);
  // Give slightly adjusted color
  const paletteIdx = (strategyIndicatorInstances.length) % COLOR_PALETTE.length;
  copyParams.color = COLOR_PALETTE[paletteIdx];
  addIndicatorInstance(orig.type, copyParams);
}

function removeIndicatorInstance(instanceId) {
  strategyIndicatorInstances = strategyIndicatorInstances.filter(i => i.id !== instanceId);
  renderIndicatorCards();
  syncChartIndicatorPills();
  triggerStrategyRecalculate();
}

function toggleIndicatorInstance(instanceId) {
  const inst = strategyIndicatorInstances.find(i => i.id === instanceId);
  if (!inst) return;
  inst.enabled = !inst.enabled;
  renderIndicatorCards();
  syncChartIndicatorPills();
  triggerStrategyRecalculate();
}

function toggleInstanceChartVisibility(instanceId) {
  const inst = strategyIndicatorInstances.find(i => i.id === instanceId);
  if (!inst) return;
  inst.visibleOnChart = !inst.visibleOnChart;
  syncChartIndicatorPills();
  triggerStrategyRecalculate();
}

function setIndicatorParam(instanceId, paramKey, val) {
  const inst = strategyIndicatorInstances.find(i => i.id === instanceId);
  if (!inst) return;
  inst.params[paramKey] = val;
  syncChartIndicatorPills();
  triggerStrategyRecalculate();
}

function stepIndicatorParam(instanceId, paramKey, delta) {
  const inst = strategyIndicatorInstances.find(i => i.id === instanceId);
  if (!inst) return;
  const meta = INDICATOR_REGISTRY[inst.type];
  const cfg = meta?.paramsConfig?.find(c => c.key === paramKey);
  const curVal = Number(inst.params[paramKey] ?? cfg?.default ?? 0);
  let nextVal = Math.round((curVal + delta) * 100) / 100;
  if (cfg) {
    if (cfg.min !== undefined) nextVal = Math.max(cfg.min, nextVal);
    if (cfg.max !== undefined) nextVal = Math.min(cfg.max, nextVal);
  }
  inst.params[paramKey] = nextVal;

  const inp = document.getElementById(`step-inp-${instanceId}-${paramKey}`);
  if (inp) inp.value = nextVal;

  syncChartIndicatorPills();
  triggerStrategyRecalculate();
}

function setIndicatorColor(instanceId, color) {
  const inst = strategyIndicatorInstances.find(i => i.id === instanceId);
  if (!inst) return;
  inst.color = color;
  inst.params.color = color;
  renderIndicatorCards();
  syncChartIndicatorPills();
  triggerStrategyRecalculate();
}

function setIndicatorCloudToggle(instanceId, enabled) {
  const inst = strategyIndicatorInstances.find(i => i.id === instanceId);
  if (!inst) return;
  inst.params.show_cloud = enabled;
  triggerStrategyRecalculate();
}

function addDualBollingerPreset() {
  clearAllIndicatorInstances(false);
  // Bollinger #1: 10, 2.0 (Cyan Cloud)
  addIndicatorInstance('BOLLINGER', { period: 10, deviation: 2.0, min_body_protrusion: 20, color: '#00f0ff', show_cloud: true }, false);
  // Bollinger #2: 13, 2.5 (Pink Cloud)
  addIndicatorInstance('BOLLINGER', { period: 13, deviation: 2.5, min_body_protrusion: 20, color: '#ec4899', show_cloud: true }, false);
  renderIndicatorCards();
  syncChartIndicatorPills();
  triggerStrategyRecalculate();
  if (window.showToast) showToast('🎯 Dual Bollinger Multi-Cloud setup loaded!', 'success');
}

function addEmaRibbonPreset() {
  clearAllIndicatorInstances(false);
  addIndicatorInstance('EMA', { period: 20, ma_type: 'EMA', color: '#00f0ff' }, false);
  addIndicatorInstance('EMA', { period: 50, ma_type: 'EMA', color: '#f59e0b' }, false);
  addIndicatorInstance('EMA', { period: 200, ma_type: 'EMA', color: '#a855f7' }, false);
  renderIndicatorCards();
  syncChartIndicatorPills();
  triggerStrategyRecalculate();
  if (window.showToast) showToast('📈 Triple EMA Ribbon (20, 50, 200) loaded!', 'success');
}

function clearAllIndicatorInstances(autoRender = true) {
  strategyIndicatorInstances = [];
  if (autoRender) {
    renderIndicatorCards();
    syncChartIndicatorPills();
    triggerStrategyRecalculate();
  }
}

function renderIndicatorCards() {
  const container = document.getElementById('dynamic-indicator-stack');
  const badge = document.getElementById('indicator-stack-badge');
  if (!container) return;

  const count = strategyIndicatorInstances.length;
  if (badge) {
    badge.textContent = `${count} Active`;
    badge.style.color = count > 0 ? 'var(--cyan-bright)' : 'var(--text-dim)';
  }

  if (count === 0) {
    container.innerHTML = `
      <div id="indicator-stack-empty-placeholder" style="text-align: center; padding: 22px 14px; color: var(--text-dim); border: 1px dashed rgba(255,255,255,0.12); border-radius: 8px; background: rgba(0,0,0,0.15);">
        <div style="font-size: 20px; margin-bottom: 6px;">🎯</div>
        <div style="font-size: 11.5px; font-weight: 700; color: var(--text-main); margin-bottom: 3px;">No Indicators In Stack</div>
        <div style="font-size: 10px;">Click <b style="color: var(--cyan-bright);">+ Add Indicator</b> above or choose <b style="color: var(--cyan-bright);">+ Dual BB</b> to add multi-cloud Bollinger Bands.</div>
      </div>
    `;
    return;
  }

  container.innerHTML = strategyIndicatorInstances.map((inst, idx) => {
    const meta = INDICATOR_REGISTRY[inst.type] || {};
    const color = inst.color || meta.color || '#00f0ff';
    const num = inst.instanceNumber > 1 ? ` #${inst.instanceNumber}` : '';
    const badgeType = meta.badge || 'INDICATOR';

    const steppersHtml = (meta.paramsConfig || []).map(cfg => {
      const curVal = inst.params[cfg.key] ?? cfg.default;
      const stepVal = cfg.step || 1;
      if (cfg.type === 'select') {
        const opts = (cfg.options || []).map(o => `<option value="${o}" ${o === curVal ? 'selected' : ''}>${o}</option>`).join('');
        return `
          <div class="stepper-item">
            <span class="stepper-label">${cfg.label}</span>
            <select class="form-input" style="padding: 4px 6px; font-size: 11px;" onchange="setIndicatorParam('${inst.id}', '${cfg.key}', this.value)">
              ${opts}
            </select>
          </div>
        `;
      }
      return `
        <div class="stepper-item">
          <span class="stepper-label">${cfg.label}</span>
          <div class="stepper-box">
            <button type="button" class="stepper-btn" onclick="stepIndicatorParam('${inst.id}', '${cfg.key}', -${stepVal})">−</button>
            <input type="number" id="step-inp-${inst.id}-${cfg.key}" class="stepper-input" value="${curVal}" step="${stepVal}" min="${cfg.min ?? 0}" max="${cfg.max ?? 9999}" onchange="setIndicatorParam('${inst.id}', '${cfg.key}', parseFloat(this.value))">
            <button type="button" class="stepper-btn" onclick="stepIndicatorParam('${inst.id}', '${cfg.key}', ${stepVal})">+</button>
          </div>
        </div>
      `;
    }).join('');

    const swatchChipsHtml = COLOR_PALETTE.map(c => `
      <div class="color-swatch-chip ${c === color ? 'active' : ''}" style="background: ${c}; color: ${c};" onclick="setIndicatorColor('${inst.id}', '${c}')" title="Set indicator color"></div>
    `).join('');

    const cloudToggleHtml = meta.supportsCloud ? `
      <label class="cloud-toggle-label">
        <input type="checkbox" ${inst.params.show_cloud !== false ? 'checked' : ''} onchange="setIndicatorCloudToggle('${inst.id}', this.checked)">
        <span>Fill Cloud</span>
      </label>
    ` : '';

    return `
      <div class="indicator-card ${!inst.enabled ? 'disabled-instance' : ''}" id="card-${inst.id}" style="border-left-color: ${color};">
        <div class="indicator-card-top">
          <div class="card-title-group">
            <input type="checkbox" ${inst.enabled ? 'checked' : ''} onchange="toggleIndicatorInstance('${inst.id}')" title="Enable or disable indicator condition" style="accent-color: ${color}; cursor: pointer;">
            <span style="font-size: 13px;">${meta.icon || '📊'}</span>
            <span class="card-title">${meta.name}${num}</span>
            <span class="card-badge" style="color: ${color}; border: 1px solid ${color}40;">${badgeType}</span>
          </div>
          <div class="card-actions">
            <button type="button" class="card-btn" onclick="duplicateIndicatorInstance('${inst.id}')" title="Duplicate indicator instance">📋</button>
            <button type="button" class="card-btn btn-card-del" onclick="removeIndicatorInstance('${inst.id}')" title="Delete indicator from strategy">🗑️</button>
          </div>
        </div>

        <div class="stepper-grid">
          ${steppersHtml}
        </div>

        <div class="visual-controls-row">
          <div class="swatch-picker-group">
            <span style="font-size: 9.5px; color: var(--text-dim); margin-right: 4px;">COLOR:</span>
            ${swatchChipsHtml}
          </div>
          ${cloudToggleHtml}
        </div>
      </div>
    `;
  }).join('');
}

function syncChartIndicatorPills() {
  const pillContainers = [
    document.getElementById('strat-chart-indicator-pills'),
    document.getElementById('live-chart-indicator-pills')
  ];

  pillContainers.forEach(container => {
    if (!container) return;

    if (strategyIndicatorInstances.length === 0) {
      container.innerHTML = '';
      return;
    }

    container.innerHTML = strategyIndicatorInstances.map(inst => {
      const meta = INDICATOR_REGISTRY[inst.type] || {};
      const color = inst.color || meta.color || '#00f0ff';
      const num = inst.instanceNumber > 1 ? ` #${inst.instanceNumber}` : '';
      const eyeIcon = inst.visibleOnChart ? '👁️' : '🕶️';

      // Summary label
      let summaryText = '';
      if (inst.type === 'BOLLINGER') {
        summaryText = `P${inst.params.period || 20} D${inst.params.deviation || 2.0}`;
      } else if (inst.type === 'EMA') {
        summaryText = `${inst.params.ma_type || 'EMA'} ${inst.params.period || 20}`;
      } else if (inst.type === 'RSI') {
        summaryText = `P${inst.params.period || 14} (${inst.params.oversold}/${inst.params.overbought})`;
      } else if (inst.type === 'STOCHASTIC') {
        summaryText = `${inst.params.k_period || 14},${inst.params.d_period || 3}`;
      } else if (inst.type === 'MACD') {
        summaryText = `${inst.params.fast_period || 12},${inst.params.slow_period || 26},${inst.params.signal_period || 9}`;
      } else if (inst.type === 'SUPERTREND') {
        summaryText = `ATR ${inst.params.atr_period || 10} x${inst.params.multiplier || 3.0}`;
      } else if (inst.type === 'ALLIGATOR') {
        summaryText = `${inst.params.jaws_period}/${inst.params.teeth_period}/${inst.params.lips_period}`;
      } else if (inst.type === 'ENVELOPES') {
        summaryText = `P${inst.params.period} ${inst.params.deviation}%`;
      } else {
        const firstKey = Object.keys(inst.params).find(k => k !== 'color' && k !== 'show_cloud');
        summaryText = firstKey ? `${inst.params[firstKey]}` : '';
      }

      return `
        <div class="indicator-pill ${!inst.visibleOnChart ? 'hidden-on-chart' : ''}" style="border-left: 3px solid ${color};">
          <span class="pill-dot" style="background: ${color};"></span>
          <span class="pill-title">${meta.name?.split(' ')[0] || inst.type}${num}</span>
          <span class="pill-params">${summaryText}</span>
          <button type="button" class="pill-btn" onclick="toggleInstanceChartVisibility('${inst.id}')" title="Toggle visibility on chart">${eyeIcon}</button>
          <button type="button" class="pill-btn" onclick="focusIndicatorCard('${inst.id}')" title="Configure in Strategy Lab">✏️</button>
          <button type="button" class="pill-btn btn-pill-del" onclick="removeIndicatorInstance('${inst.id}')" title="Remove indicator">✕</button>
        </div>
      `;
    }).join('');
  });
}

function focusIndicatorCard(instanceId) {
  if (window.switchView) window.switchView('strategies');
  const card = document.getElementById(`card-${instanceId}`);
  if (card) {
    card.scrollIntoView({ behavior: 'smooth', block: 'center' });
    card.style.boxShadow = '0 0 20px rgba(0, 240, 255, 0.4)';
    setTimeout(() => { card.style.boxShadow = ''; }, 1500);
  }
}

function triggerStrategyRecalculate() {
  if (window.recalculateStrategyVisualizer) {
    window.recalculateStrategyVisualizer();
  }
}

function compileIndicatorFilters() {
  return strategyIndicatorInstances.filter(inst => inst.enabled).map(inst => {
    return {
      indicator: inst.type,
      period: inst.params.period || inst.params.k_period || inst.params.fast_period || inst.params.atr_period || 14,
      condition: 'ACTIVE',
      color: inst.color,
      show_cloud: inst.params.show_cloud !== false,
      visible_on_chart: inst.visibleOnChart !== false,
      params: Object.assign({}, inst.params)
    };
  });
}

function loadIndicatorFilters(indicatorsList) {
  strategyIndicatorInstances = [];
  if (Array.isArray(indicatorsList) && indicatorsList.length > 0) {
    indicatorsList.forEach(ind => {
      const type = (ind.indicator || '').toUpperCase();
      const meta = INDICATOR_REGISTRY[type];
      if (meta) {
        const mergedParams = Object.assign({}, meta.defaultParams, ind.params || {});
        if (ind.color) mergedParams.color = ind.color;
        if (ind.show_cloud !== undefined) mergedParams.show_cloud = ind.show_cloud;
        addIndicatorInstance(type, mergedParams, false);
      }
    });
  } else {
    // Default to Dual Bollinger Setup
    addIndicatorInstance('BOLLINGER', { period: 10, deviation: 2.0, min_body_protrusion: 20, color: '#00f0ff', show_cloud: true }, false);
    addIndicatorInstance('BOLLINGER', { period: 13, deviation: 2.5, min_body_protrusion: 20, color: '#ec4899', show_cloud: true }, false);
  }
  renderIndicatorCards();
  syncChartIndicatorPills();
}

// Expose globals for window access
window.INDICATOR_REGISTRY = INDICATOR_REGISTRY;
window.strategyIndicatorInstances = strategyIndicatorInstances;
window.toggleIndicatorCatalogDropdown = toggleIndicatorCatalogDropdown;
window.addIndicatorInstance = addIndicatorInstance;
window.duplicateIndicatorInstance = duplicateIndicatorInstance;
window.removeIndicatorInstance = removeIndicatorInstance;
window.toggleIndicatorInstance = toggleIndicatorInstance;
window.toggleInstanceChartVisibility = toggleInstanceChartVisibility;
window.stepIndicatorParam = stepIndicatorParam;
window.setIndicatorParam = setIndicatorParam;
window.setIndicatorColor = setIndicatorColor;
window.setIndicatorCloudToggle = setIndicatorCloudToggle;
window.addDualBollingerPreset = addDualBollingerPreset;
window.addEmaRibbonPreset = addEmaRibbonPreset;
window.clearAllIndicatorInstances = clearAllIndicatorInstances;
window.renderIndicatorCards = renderIndicatorCards;
window.syncChartIndicatorPills = syncChartIndicatorPills;
window.focusIndicatorCard = focusIndicatorCard;
window.compileIndicatorFilters = compileIndicatorFilters;
window.loadIndicatorFilters = loadIndicatorFilters;
