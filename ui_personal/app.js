/**
 * TradePulse Personal Edition — UI Controller & State Manager
 * Real Live Markets Currencies Only | Single Personal Telegram Bot | Gated Scanner
 */

const PersonalState = {
  activeView: 'markets',
  connected: false,
  toolActive: false,
  scanningPaused: true,
  sessionToken: null,
  assets: [],
  payouts: {},
  prices: {},
  strategies: [],
  selectedStrategyId: null,
  history: [],
  telegramToken: '',
  telegramChatId: '',
  telegramConfig: {},
  selectedTemplateKey: 'signal',
  scheduleConfig: {
    enabled: false,
    allowed_days: ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"],
    start_time: "00:00",
    end_time: "23:59",
    use_utc: true
  },
  activeChartPair: 'EUR/USD'
};

const TEMPLATE_TOKENS = {
  signal: [
    "{strategy}", "{asset}", "{payout}", "{arrow}", "{dir_badge}", 
    "{chart_timeframe}", "{timeframe}", "{expiry}", "{entry_time}"
  ],
  pre_signal: [
    "{strategy}", "{asset}", "{dir_badge}", "{timeframe}", "{expiry}", 
    "{payout}", "{remaining_seconds}", "{stake_line}"
  ],
  outcome: [
    "{header}", "{asset}", "{strategy}", "{direction}", "{outcome_badge}", 
    "{entry_price}", "{exit_price}", "{pnl_text}"
  ],
  circuit_breaker: [
    "{cb_reason}", "{net_pnl}", "{total_trades}"
  ]
};

let chartEngine = null;

// ============================================================================
// Initialization & pywebview Handshake
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
  chartEngine = new InteractiveChartEngine('interactiveChartCanvas');
  window.chartEngine = chartEngine;

  // Initialize PyWebView bridge
  if (window.pywebview && window.pywebview.api) {
    onBridgeReady();
  } else {
    window.addEventListener('pywebviewready', onBridgeReady);
  }

  // Periodic broker dock position sync & schedule check
  setInterval(() => {
    if (PersonalState.activeView === 'broker') {
      syncBrokerStation();
    }
    evaluateScheduleStatusUI();
  }, 1000);
});

function onBridgeReady() {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.get_initial_state) {
    window.pywebview.api.get_initial_state().then(state => {
      initAppState(state);
    }).catch(e => console.error('[INIT ERROR]', e));
  }
}

function initAppState(state) {
  if (!state) return;
  PersonalState.connected = !!state.connected;
  PersonalState.sessionToken = state.session_token;
  PersonalState.toolActive = !!state.tool_active;
  PersonalState.scanningPaused = state.scanning_paused !== false;
  PersonalState.assets = state.assets || [];
  PersonalState.payouts = state.payouts || {};
  PersonalState.prices = state.prices || {};
  PersonalState.strategies = state.strategies || [];
  PersonalState.history = state.signals || [];
  PersonalState.telegramToken = state.telegram_token || '';

  if (state.telegram_manager) {
    PersonalState.telegramConfig = state.telegram_manager;
    if (state.telegram_manager.bot_token) {
      PersonalState.telegramToken = state.telegram_manager.bot_token;
    }
    const channels = state.telegram_manager.channels || [];
    if (channels.length > 0) {
      PersonalState.telegramChatId = channels[0].id || '';
    } else if (state.telegram_chat_id) {
      PersonalState.telegramChatId = Array.isArray(state.telegram_chat_id) ? (state.telegram_chat_id[0] || '') : String(state.telegram_chat_id);
    }
  } else if (state.telegram_chat_id) {
    PersonalState.telegramChatId = Array.isArray(state.telegram_chat_id) ? (state.telegram_chat_id[0] || '') : String(state.telegram_chat_id);
  }

  if (state.advanced_filters && state.advanced_filters.session_scheduler) {
    PersonalState.scheduleConfig = { ...PersonalState.scheduleConfig, ...state.advanced_filters.session_scheduler };
  }

  PersonalState.license = state.license || {};
  updateLicenseStatusUI();

  updateBrokerStatusUI();
  updateMasterScannerUI();
  updateTelegramUI();
  updateTelegramRulesUI();
  renderLiveMarketsTable();
  populateChartPairSelector();
  renderStrategiesList();
  if (PersonalState.strategies.length > 0) {
    selectStrategyForEditing(PersonalState.strategies[0].id);
  } else {
    createNewStrategy();
  }
  renderHistoryTable();
  initTemplateEditor();
  initScheduleUI();
}

// ============================================================================
// View Navigation & Docking
// ============================================================================
function switchView(viewName) {
  PersonalState.activeView = viewName;
  document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
  document.querySelectorAll('.view-pane').forEach(pane => pane.classList.remove('active'));

  const navItem = document.getElementById(`nav-${viewName}`);
  const viewPane = document.getElementById(`view-${viewName}`);
  if (navItem) navItem.classList.add('active');
  if (viewPane) viewPane.classList.add('active');

  // If entering chart, trigger resize & history bootstrap
  if (viewName === 'chart' && chartEngine) {
    setTimeout(() => {
      chartEngine.resize();
      fetchCandlesForPair(PersonalState.activeChartPair);
    }, 60);
  }

  // If entering or leaving embedded broker, update native visibility
  if (window.pywebview && window.pywebview.api && window.pywebview.api.set_broker_visible) {
    const isBroker = (viewName === 'broker');
    window.pywebview.api.set_broker_visible(isBroker);
    if (isBroker) {
      setTimeout(syncBrokerStation, 100);
    }
  }
}
window.switchView = switchView;

function syncBrokerStation() {
  const dock = document.getElementById('broker-station-dock');
  if (!dock || PersonalState.activeView !== 'broker') return;
  const rect = dock.getBoundingClientRect();
  if (rect.width > 20 && rect.height > 20 && window.pywebview && window.pywebview.api && window.pywebview.api.sync_broker_position) {
    window.pywebview.api.sync_broker_position(
      Math.round(rect.left),
      Math.round(rect.top),
      Math.round(rect.width),
      Math.round(rect.height),
      true
    );
  }
}

// ============================================================================
// Master Gated Bot Scanner Controller
// ============================================================================
function toggleMasterScanner() {
  if (!PersonalState.connected && !PersonalState.sessionToken) {
    showToast('⚠️ Quotex Login Required! Please log in to your account in the Quotex Terminal first.', 'error');
    switchView('broker');
    return;
  }

  const newActiveState = !PersonalState.toolActive;
  if (window.pywebview && window.pywebview.api && window.pywebview.api.set_tool_active) {
    window.pywebview.api.set_tool_active(newActiveState).then(res => {
      if (res && res.success) {
        PersonalState.toolActive = res.active;
        PersonalState.scanningPaused = res.paused;
        updateMasterScannerUI();
        showToast(res.active ? '⚡ Personal Live Scanner STARTED!' : '⏸ Scanner PAUSED.', res.active ? 'success' : 'info');
      } else {
        showToast(res && res.error ? res.error : 'Failed to toggle scanner', 'error');
      }
    });
  }
}
window.toggleMasterScanner = toggleMasterScanner;

function updateMasterScannerUI() {
  const btn = document.getElementById('master-scanner-btn');
  const icon = document.getElementById('master-scanner-icon');
  const text = document.getElementById('master-scanner-text');
  if (!btn || !icon || !text) return;

  if (!PersonalState.connected && !PersonalState.sessionToken) {
    btn.className = 'master-scanner-btn locked';
    icon.textContent = '🔒';
    text.textContent = 'Login to Quotex First';
  } else if (PersonalState.toolActive && !PersonalState.scanningPaused) {
    btn.className = 'master-scanner-btn active';
    icon.textContent = '⚡';
    text.textContent = 'Scanner Active (Live)';
  } else {
    btn.className = 'master-scanner-btn paused';
    icon.textContent = '▶️';
    text.textContent = 'Start Bot Scanner';
  }
}

function updateBrokerStatusUI() {
  const pill = document.getElementById('broker-status-pill');
  const txt = document.getElementById('broker-status-text');
  if (!pill || !txt) return;

  if (PersonalState.connected || (PersonalState.sessionToken && PersonalState.sessionToken.length > 10)) {
    pill.className = 'status-pill connected';
    txt.textContent = 'Quotex: Connected (Live)';
  } else {
    pill.className = 'status-pill disconnected';
    txt.textContent = 'Quotex: Disconnected (Login Required)';
  }
}

function updateTelegramUI() {
  const isLinked = !!(PersonalState.telegramToken && PersonalState.telegramChatId);
  const pill = document.getElementById('telegram-status-pill');
  const txt = document.getElementById('telegram-status-text');
  const cardStatus = document.getElementById('tg-card-status');
  const cardTarget = document.getElementById('tg-card-target-id');
  const statLink = document.getElementById('stat-telegram-link');
  const tokenInput = document.getElementById('personal-tg-token');
  const chatIdInput = document.getElementById('personal-tg-chat-id');

  if (tokenInput && PersonalState.telegramToken && !tokenInput.value) {
    tokenInput.value = PersonalState.telegramToken;
  }
  if (chatIdInput && PersonalState.telegramChatId && !chatIdInput.value) {
    chatIdInput.value = PersonalState.telegramChatId;
  }

  if (pill && txt) {
    if (isLinked) {
      pill.className = 'status-pill connected';
      txt.textContent = 'Telegram: Linked';
    } else {
      pill.className = 'status-pill disconnected';
      txt.textContent = 'Telegram: Not Linked';
    }
  }

  if (cardStatus) {
    cardStatus.textContent = isLinked ? 'Active & Ready' : 'Pending Link';
    cardStatus.style.color = isLinked ? 'var(--emerald)' : 'var(--gold)';
  }

  if (cardTarget) {
    cardTarget.textContent = PersonalState.telegramChatId ? PersonalState.telegramChatId : 'None Configured';
  }

  if (statLink) {
    statLink.textContent = isLinked ? 'Linked' : 'Offline';
  }
}

// ============================================================================
// Real Live Markets Table (NO OTC, NO MARKET SOURCE COLUMN)
// ============================================================================
function renderLiveMarketsTable() {
  const tbody = document.getElementById('live-markets-tbody');
  const countBadge = document.getElementById('markets-count-badge');
  const activePairsStat = document.getElementById('stat-active-pairs');
  if (!tbody) return;

  const liveAssets = (PersonalState.assets || []).filter(a => {
    const sym = a.symbol || '';
    return !sym.includes('(OTC)') && !sym.toLowerCase().includes('_otc') && sym.includes('/');
  });

  if (countBadge) countBadge.textContent = `${liveAssets.length} Pairs`;
  if (activePairsStat) activePairsStat.textContent = liveAssets.length;

  if (liveAssets.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 20px; color: var(--text-dim);">No real Live Market pairs available.</td></tr>';
    return;
  }

  tbody.innerHTML = liveAssets.map(a => {
    const sym = a.symbol;
    const price = PersonalState.prices[sym] ? formatLivePrice(sym, PersonalState.prices[sym]) : '---';
    const payout = PersonalState.payouts[sym] ? `${PersonalState.payouts[sym]}%` : '85%';

    return `
      <tr>
        <td>
          <div class="pair-badge">
            <div class="pair-flag">💱</div>
            <span>${sym}</span>
          </div>
        </td>
        <td class="rate-cell" id="rate-${sanitizeId(sym)}">${price}</td>
        <td><span class="payout-pill">${payout}</span></td>
        <td style="text-align: right;">
          <button class="btn-secondary" style="padding: 4px 10px; font-size: 11px;" onclick="openPairChart('${sym}')">
            📈 Chart
          </button>
        </td>
      </tr>
    `;
  }).join('');
}
window.renderLiveMarketsTable = renderLiveMarketsTable;
window.renderForexTable = renderLiveMarketsTable;

function openPairChart(symbol) {
  PersonalState.activeChartPair = symbol;
  const sel = document.getElementById('chart-pair-select');
  if (sel) sel.value = symbol;
  switchView('chart');
}
window.openPairChart = openPairChart;

function formatLivePrice(symbol, price) {
  const num = parseFloat(price);
  if (isNaN(num)) return price;
  if (symbol.includes('JPY')) return num.toFixed(3);
  return num.toFixed(5);
}

function sanitizeId(str) {
  return (str || '').toLowerCase().replace(/[^a-z0-9]/g, '_');
}

function refreshMarketRates() {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.get_initial_state) {
    window.pywebview.api.get_initial_state().then(state => {
      if (state) {
        PersonalState.payouts = state.payouts || {};
        PersonalState.prices = state.prices || {};
        renderLiveMarketsTable();
        showToast('Refreshed Live Market rates', 'info');
      }
    });
  }
}
window.refreshMarketRates = refreshMarketRates;

// ============================================================================
// Interactive Live Chart Controls
// ============================================================================
function populateChartPairSelector() {
  const sel = document.getElementById('chart-pair-select');
  if (!sel) return;

  const liveAssets = (PersonalState.assets || []).filter(a => !a.symbol.includes('(OTC)') && a.symbol.includes('/'));
  sel.innerHTML = liveAssets.map(a => `<option value="${a.symbol}">${a.symbol}</option>`).join('');
  if (PersonalState.activeChartPair) sel.value = PersonalState.activeChartPair;
}

function changeChartPair(pair) {
  PersonalState.activeChartPair = pair;
  if (chartEngine) {
    chartEngine.setSymbol(pair);
    fetchCandlesForPair(pair);
  }
}
window.changeChartPair = changeChartPair;

function fetchCandlesForPair(symbol, tf = '1M') {
  const reqTf = tf || (chartEngine ? chartEngine.timeframe : '1M');
  if (window.pywebview && window.pywebview.api && window.pywebview.api.get_candles_for_chart) {
    window.pywebview.api.get_candles_for_chart(symbol, reqTf).then(candles => {
      if (chartEngine && Array.isArray(candles)) {
        chartEngine.setCandles(candles);
      }
    });
  }
}

function setChartTimeframe(tf) {
  document.querySelectorAll('#btn-tf-1m, #btn-tf-5m, #btn-tf-15m').forEach(b => b.classList.remove('active'));
  const btn = document.getElementById(`btn-tf-${tf.toLowerCase()}`);
  if (btn) btn.classList.add('active');

  if (chartEngine) {
    chartEngine.timeframe = tf;
    fetchCandlesForPair(PersonalState.activeChartPair, tf);
    showToast(`Timeframe set to ${tf}`, 'info');
  }
}
window.setChartTimeframe = setChartTimeframe;

function toggleHeikinAshi() {
  if (chartEngine) {
    const isHA = !chartEngine.heikinAshi;
    chartEngine.setHeikinAshi(isHA);
    const btn = document.getElementById('btn-chart-ha');
    if (btn) {
      btn.textContent = isHA ? '📊 Heikin-Ashi' : '🕯️ Regular';
      btn.className = isHA ? 'btn-secondary active' : 'btn-secondary';
    }
    showToast(`Switched chart to ${isHA ? 'Heikin-Ashi Smoothed Trend' : 'Regular Candlesticks'}`, 'info');
  }
}
window.toggleHeikinAshi = toggleHeikinAshi;

function toggleChartIndicator(ind) {
  if (chartEngine) {
    if (ind === 'ema') {
      chartEngine.toggleIndicator('ema20');
      chartEngine.toggleIndicator('ema50');
      const btn = document.getElementById('btn-ind-ema');
      if (btn) btn.classList.toggle('active', chartEngine.indicators.ema20);
      showToast('Toggled EMA 20/50 lines', 'info');
    } else if (ind === 'bb') {
      chartEngine.toggleIndicator('bb');
      const btn = document.getElementById('btn-ind-bb');
      if (btn) btn.classList.toggle('active', chartEngine.indicators.bb);
      showToast('Toggled Bollinger Bands Cloud', 'info');
    }
  }
}
window.toggleChartIndicator = toggleChartIndicator;

// ============================================================================
// Complete Strategy Customizer Lab
// ============================================================================
function renderStrategiesList() {
  const container = document.getElementById('strategies-list-container');
  const countIndicator = document.getElementById('strat-count-indicator');
  if (!container) return;

  const strats = PersonalState.strategies || [];
  const activeCount = strats.filter(s => s.enabled).length;
  if (countIndicator) countIndicator.textContent = `${activeCount} / ${strats.length} Active`;

  if (strats.length === 0) {
    container.innerHTML = `
      <div style="padding: 28px 16px; text-align: center; color: var(--text-dim); background: rgba(255,255,255,0.02); border-radius: 8px; border: 1px dashed var(--border);">
        <div style="font-size: 24px; margin-bottom: 8px;">📂</div>
        <div style="font-weight: 700; font-size: 13px; color: var(--text-main);">No Strategies Configured</div>
        <div style="font-size: 11px; margin-top: 6px; line-height: 1.4;">
          Your Personal Strategy Library is empty.<br>
          Select an archetype preset or click <strong>"+ New Strategy"</strong> to construct custom algorithmic rules.
        </div>
      </div>
    `;
    return;
  }

  container.innerHTML = strats.map(s => {
    const isSel = (s.id === PersonalState.selectedStrategyId);
    return `
      <div class="strategy-item-card ${isSel ? 'selected' : ''}" onclick="selectStrategyForEditing('${s.id}')">
        <div>
          <div style="font-weight: 700; color: #fff; font-size: 13px;">${escapeHtml(s.name)}</div>
          <div style="font-size: 11px; color: var(--text-dim); margin-top: 2px;">
            ${s.timeframe || '1M'} • Expiry: ${s.expiry_minutes}m • Min: ${s.min_payout}% • ${s.direction || 'BOTH'}
          </div>
        </div>
        <label style="cursor: pointer;" onclick="event.stopPropagation();">
          <input type="checkbox" ${s.enabled ? 'checked' : ''} onchange="togglePersonalStrategy('${s.id}', this.checked)">
        </label>
      </div>
    `;
  }).join('');
}

function selectStrategyForEditing(strategyId) {
  PersonalState.selectedStrategyId = strategyId;
  renderStrategiesList();

  const strat = PersonalState.strategies.find(s => s.id === strategyId);
  if (!strat) return;

  document.getElementById('strat-form-title').textContent = `Edit Strategy: ${strat.name}`;
  document.getElementById('strat-active-id-badge').textContent = strat.id;
  document.getElementById('strat-id-input').value = strat.id;
  document.getElementById('strat-name-input').value = strat.name;
  document.getElementById('strat-tf-select').value = strat.timeframe || '1M';
  document.getElementById('strat-exp-input').value = strat.expiry_minutes || 2;
  document.getElementById('strat-payout-input').value = strat.min_payout || 80;
  document.getElementById('strat-direction-select').value = strat.direction || 'BOTH';
  document.getElementById('strat-cooldown-select').value = String(strat.cooldown_seconds || 120);
  document.getElementById('strat-mtg1-toggle').checked = !!strat.martingale_mtg1;

  // Filters & Triggers
  const filters = strat.filters || {};
  const trend = filters.trend || {};
  const anatomy = filters.candle_anatomy || {};
  const pa = filters.price_action || {};
  const smc = filters.smc || {};
  const inds = filters.indicators || [];

  document.getElementById('strat-trend-filter').checked = !!trend.enabled;
  document.getElementById('strat-trend-mtf').value = trend.mtf_timeframe || '5M';
  document.getElementById('strat-trend-ema').value = String(trend.ema_period || 20);

  document.getElementById('strat-body-ratio').value = String(anatomy.min_body_ratio || 0.50);
  document.getElementById('strat-max-wick').value = String(anatomy.max_opposing_wick || 0.35);
  document.getElementById('strat-doji-filter').checked = anatomy.filter_preceding_doji !== false;

  document.getElementById('strat-engulfing-filter').checked = !!pa.require_engulfing;
  document.getElementById('strat-sr-breakout-filter').checked = !!pa.require_sr_breakout;

  document.getElementById('strat-rsi-filter').checked = inds.some(i => (i.indicator || '').toUpperCase() === 'RSI');
  document.getElementById('strat-bollinger-filter').checked = inds.some(i => (i.indicator || '').toUpperCase() === 'BOLLINGER');
  document.getElementById('strat-stochastic-filter').checked = inds.some(i => (i.indicator || '').toUpperCase() === 'STOCHASTIC');
  document.getElementById('strat-macd-filter').checked = inds.some(i => (i.indicator || '').toUpperCase() === 'MACD');
  document.getElementById('strat-supertrend-filter').checked = inds.some(i => ['SUPERTREND', 'ST'].includes((i.indicator || '').toUpperCase()));
  document.getElementById('strat-sar-filter').checked = inds.some(i => ['PARABOLIC_SAR', 'SAR', 'PSAR'].includes((i.indicator || '').toUpperCase()));
  document.getElementById('strat-ao-filter').checked = inds.some(i => ['AWESOME_OSCILLATOR', 'AO'].includes((i.indicator || '').toUpperCase()));
  document.getElementById('strat-williams-filter').checked = inds.some(i => ['WILLIAMS_R', 'WILLIAMS_%R', 'WR'].includes((i.indicator || '').toUpperCase()));
  document.getElementById('strat-cci-filter').checked = inds.some(i => (i.indicator || '').toUpperCase() === 'CCI');
  document.getElementById('strat-demarker-filter').checked = inds.some(i => ['DEMARKER', 'DEM'].includes((i.indicator || '').toUpperCase()));
  document.getElementById('strat-elder-filter').checked = inds.some(i => ['BULLS_POWER', 'BEARS_POWER', 'ELDER'].includes((i.indicator || '').toUpperCase()));
  document.getElementById('strat-alligator-filter').checked = inds.some(i => (i.indicator || '').toUpperCase() === 'ALLIGATOR');
  document.getElementById('strat-keltner-filter').checked = inds.some(i => ['KELTNER', 'DONCHIAN', 'ENVELOPES'].includes((i.indicator || '').toUpperCase()));
  document.getElementById('strat-vortex-filter').checked = inds.some(i => (i.indicator || '').toUpperCase() === 'VORTEX');

  document.getElementById('strat-smc-fvg').checked = !!smc.fvg_enabled;
  document.getElementById('strat-smc-sweep').checked = !!smc.liquidity_sweep_enabled;
  document.getElementById('strat-smc-bos').checked = !!smc.bos_enabled;
  document.getElementById('strat-smc-ob').checked = !!smc.order_block_enabled;

  const presetSelect = document.getElementById('strat-archetype-preset');
  if (presetSelect) presetSelect.value = "";

  const delBtn = document.getElementById('btn-delete-strategy');
  if (delBtn) delBtn.style.display = 'inline-block';
}
window.selectStrategyForEditing = selectStrategyForEditing;

function applyArchetypePreset(presetKey) {
  if (!presetKey) return;

  const presets = {
    dual_bollinger_protrusion: {
      name: "Dual Bollinger Protrusion 1M",
      tf: "1M", exp: 1, payout: 80, dir: "BOTH", cd: 120, mtg1: false,
      trend: false, trendMtf: "5M", trendEma: "20",
      bodyRatio: "0.20", maxWick: "0.40", doji: true,
      engulfing: false, srBreakout: false,
      rsi: false, bollinger: true, stoch: false, macd: false,
      supertrend: false, sar: false, ao: false, williams: false, cci: false, demarker: false, elder: false, alligator: false, keltner: false, vortex: false,
      fvg: false, sweep: false, bos: false, ob: false
    },
    logus_trend: {
      name: "Logu's Trend Momentum",
      tf: "1M", exp: 1, payout: 80, dir: "BOTH", cd: 120, mtg1: false,
      trend: true, trendMtf: "5M", trendEma: "20",
      bodyRatio: "0.50", maxWick: "0.30", doji: true,
      engulfing: false, srBreakout: false,
      rsi: false, bollinger: false, stoch: false, macd: false,
      supertrend: false, sar: false, ao: false, williams: false, cci: false, demarker: false, elder: false, alligator: false, keltner: false, vortex: false,
      fvg: false, sweep: false, bos: false, ob: false
    },
    mtf_engulfing: {
      name: "MTF Engulfing Momentum",
      tf: "1M", exp: 2, payout: 80, dir: "BOTH", cd: 120, mtg1: false,
      trend: true, trendMtf: "5M", trendEma: "20",
      bodyRatio: "0.65", maxWick: "0.30", doji: true,
      engulfing: true, srBreakout: false,
      rsi: false, bollinger: false, stoch: false, macd: false,
      supertrend: false, sar: false, ao: false, williams: false, cci: false, demarker: false, elder: false, alligator: false, keltner: false, vortex: false,
      fvg: false, sweep: false, bos: false, ob: false
    },
    snr_wick: {
      name: "S&R Pin Bar Rejection",
      tf: "5M", exp: 5, payout: 80, dir: "BOTH", cd: 180, mtg1: false,
      trend: false, trendMtf: "5M", trendEma: "20",
      bodyRatio: "0.15", maxWick: "0.45", doji: true,
      engulfing: false, srBreakout: false,
      rsi: true, bollinger: true, stoch: false, macd: false,
      supertrend: false, sar: false, ao: false, williams: false, cci: false, demarker: false, elder: false, alligator: false, keltner: false, vortex: false,
      fvg: false, sweep: false, bos: false, ob: false
    },
    ema_bounce: {
      name: "EMA Dynamic Retest & Bounce",
      tf: "5M", exp: 5, payout: 80, dir: "BOTH", cd: 180, mtg1: false,
      trend: true, trendMtf: "5M", trendEma: "20",
      bodyRatio: "0.35", maxWick: "0.35", doji: true,
      engulfing: false, srBreakout: false,
      rsi: false, bollinger: false, stoch: true, macd: false,
      supertrend: false, sar: false, ao: false, williams: false, cci: false, demarker: false, elder: false, alligator: false, keltner: false, vortex: false,
      fvg: false, sweep: false, bos: false, ob: false
    },
    bollinger_mean: {
      name: "Bollinger Mean Reversion",
      tf: "1M", exp: 2, payout: 82, dir: "BOTH", cd: 150, mtg1: false,
      trend: false, trendMtf: "5M", trendEma: "20",
      bodyRatio: "0.25", maxWick: "0.40", doji: true,
      engulfing: false, srBreakout: false,
      rsi: true, bollinger: true, stoch: false, macd: false,
      supertrend: false, sar: false, ao: false, williams: false, cci: false, demarker: false, elder: false, alligator: false, keltner: false, vortex: false,
      fvg: false, sweep: false, bos: false, ob: false
    },
    bollinger_squeeze: {
      name: "Bollinger Squeeze Breakout",
      tf: "1M", exp: 2, payout: 80, dir: "BOTH", cd: 180, mtg1: false,
      trend: true, trendMtf: "5M", trendEma: "20",
      bodyRatio: "0.65", maxWick: "0.25", doji: true,
      engulfing: false, srBreakout: true,
      rsi: false, bollinger: true, stoch: false, macd: false,
      supertrend: false, sar: false, ao: false, williams: false, cci: false, demarker: false, elder: false, alligator: false, keltner: false, vortex: false,
      fvg: false, sweep: false, bos: false, ob: false
    },
    bollinger_rsi: {
      name: "Bollinger + RSI Extreme Confluence",
      tf: "5M", exp: 5, payout: 85, dir: "BOTH", cd: 180, mtg1: true,
      trend: false, trendMtf: "5M", trendEma: "20",
      bodyRatio: "0.20", maxWick: "0.45", doji: true,
      engulfing: false, srBreakout: false,
      rsi: true, bollinger: true, stoch: false, macd: false,
      supertrend: false, sar: false, ao: false, williams: false, cci: false, demarker: false, elder: false, alligator: false, keltner: false, vortex: false,
      fvg: false, sweep: false, bos: false, ob: false
    },
    supertrend_trend: {
      name: "Supertrend ATR Trend Follower",
      tf: "1M", exp: 2, payout: 80, dir: "BOTH", cd: 120, mtg1: false,
      trend: true, trendMtf: "5M", trendEma: "20",
      bodyRatio: "0.60", maxWick: "0.25", doji: true,
      engulfing: false, srBreakout: false,
      rsi: false, bollinger: false, stoch: false, macd: false,
      supertrend: true, sar: false, ao: false, williams: false, cci: false, demarker: false, elder: false, alligator: false, keltner: false, vortex: false,
      fvg: false, sweep: false, bos: false, ob: false
    },
    sar_reversal: {
      name: "Parabolic SAR Flip Sniper",
      tf: "1M", exp: 2, payout: 80, dir: "BOTH", cd: 150, mtg1: false,
      trend: false, trendMtf: "5M", trendEma: "20",
      bodyRatio: "0.40", maxWick: "0.35", doji: true,
      engulfing: false, srBreakout: false,
      rsi: false, bollinger: false, stoch: false, macd: false,
      supertrend: false, sar: true, ao: false, williams: false, cci: false, demarker: false, elder: false, alligator: false, keltner: false, vortex: false,
      fvg: false, sweep: false, bos: false, ob: false
    },
    ao_momentum: {
      name: "Awesome Oscillator Zero-Line Scalper",
      tf: "1M", exp: 1, payout: 80, dir: "BOTH", cd: 120, mtg1: false,
      trend: true, trendMtf: "5M", trendEma: "20",
      bodyRatio: "0.55", maxWick: "0.30", doji: true,
      engulfing: false, srBreakout: false,
      rsi: false, bollinger: false, stoch: false, macd: false,
      supertrend: false, sar: false, ao: true, williams: false, cci: false, demarker: false, elder: false, alligator: false, keltner: false, vortex: false,
      fvg: false, sweep: false, bos: false, ob: false
    },
    williams_extreme: {
      name: "Williams %R Extreme Boundary Reversal",
      tf: "5M", exp: 5, payout: 82, dir: "BOTH", cd: 180, mtg1: false,
      trend: false, trendMtf: "5M", trendEma: "20",
      bodyRatio: "0.30", maxWick: "0.40", doji: true,
      engulfing: false, srBreakout: false,
      rsi: false, bollinger: false, stoch: false, macd: false,
      supertrend: false, sar: false, ao: false, williams: true, cci: false, demarker: false, elder: false, alligator: false, keltner: false, vortex: false,
      fvg: false, sweep: false, bos: false, ob: false
    },
    alligator_breakout: {
      name: "Alligator Lips/Teeth/Jaw Expansion",
      tf: "5M", exp: 5, payout: 80, dir: "BOTH", cd: 180, mtg1: false,
      trend: true, trendMtf: "5M", trendEma: "20",
      bodyRatio: "0.50", maxWick: "0.30", doji: true,
      engulfing: true, srBreakout: false,
      rsi: false, bollinger: false, stoch: false, macd: false,
      supertrend: false, sar: false, ao: false, williams: false, cci: false, demarker: false, elder: false, alligator: true, keltner: false, vortex: false,
      fvg: false, sweep: false, bos: false, ob: false
    },
    keltner_squeeze: {
      name: "Keltner & Donchian Breakout",
      tf: "1M", exp: 2, payout: 80, dir: "BOTH", cd: 180, mtg1: false,
      trend: true, trendMtf: "5M", trendEma: "20",
      bodyRatio: "0.65", maxWick: "0.25", doji: true,
      engulfing: false, srBreakout: true,
      rsi: false, bollinger: false, stoch: false, macd: false,
      supertrend: false, sar: false, ao: false, williams: false, cci: false, demarker: false, elder: false, alligator: false, keltner: true, vortex: false,
      fvg: false, sweep: false, bos: false, ob: false
    },
    vortex_flow: {
      name: "Vortex Flow Directional Cross",
      tf: "5M", exp: 5, payout: 80, dir: "BOTH", cd: 180, mtg1: false,
      trend: true, trendMtf: "5M", trendEma: "20",
      bodyRatio: "0.50", maxWick: "0.30", doji: true,
      engulfing: false, srBreakout: false,
      rsi: false, bollinger: false, stoch: false, macd: false,
      supertrend: false, sar: false, ao: false, williams: false, cci: false, demarker: false, elder: false, alligator: false, keltner: false, vortex: true,
      fvg: false, sweep: false, bos: false, ob: false
    },
    smc_orderblock: {
      name: "SMC Order Block & FVG",
      tf: "5M", exp: 5, payout: 80, dir: "BOTH", cd: 240, mtg1: false,
      trend: true, trendMtf: "15M", trendEma: "50",
      bodyRatio: "0.40", maxWick: "0.35", doji: true,
      engulfing: false, srBreakout: false,
      rsi: false, bollinger: false, stoch: false, macd: false,
      supertrend: false, sar: false, ao: false, williams: false, cci: false, demarker: false, elder: false, alligator: false, keltner: false, vortex: false,
      fvg: true, sweep: true, bos: true, ob: true
    },
    breakout_momentum: {
      name: "Volatility Breakout Momentum",
      tf: "5M", exp: 5, payout: 80, dir: "BOTH", cd: 180, mtg1: false,
      trend: true, trendMtf: "5M", trendEma: "20",
      bodyRatio: "0.70", maxWick: "0.25", doji: true,
      engulfing: false, srBreakout: true,
      rsi: false, bollinger: false, stoch: false, macd: true,
      supertrend: false, sar: false, ao: false, williams: false, cci: false, demarker: false, elder: false, alligator: false, keltner: false, vortex: false,
      fvg: false, sweep: false, bos: false, ob: false
    },
    ultra_confluence: {
      name: "Ultra Confluence Pro Matrix",
      tf: "1M", exp: 2, payout: 85, dir: "BOTH", cd: 180, mtg1: true,
      trend: true, trendMtf: "5M", trendEma: "50",
      bodyRatio: "0.55", maxWick: "0.30", doji: true,
      engulfing: true, srBreakout: false,
      rsi: true, bollinger: false, stoch: false, macd: false,
      supertrend: true, sar: true, ao: false, williams: false, cci: false, demarker: false, elder: false, alligator: false, keltner: false, vortex: false,
      fvg: true, sweep: false, bos: false, ob: false
    }
  };

  const p = presets[presetKey];
  if (!p) return;

  document.getElementById('strat-name-input').value = p.name;
  document.getElementById('strat-tf-select').value = p.tf;
  document.getElementById('strat-exp-input').value = p.exp;
  document.getElementById('strat-payout-input').value = p.payout;
  document.getElementById('strat-direction-select').value = p.dir;
  document.getElementById('strat-cooldown-select').value = String(p.cd);
  document.getElementById('strat-mtg1-toggle').checked = !!p.mtg1;

  document.getElementById('strat-trend-filter').checked = !!p.trend;
  document.getElementById('strat-trend-mtf').value = p.trendMtf;
  document.getElementById('strat-trend-ema').value = p.trendEma;

  document.getElementById('strat-body-ratio').value = p.bodyRatio;
  document.getElementById('strat-max-wick').value = p.maxWick;
  document.getElementById('strat-doji-filter').checked = !!p.doji;

  document.getElementById('strat-engulfing-filter').checked = !!p.engulfing;
  document.getElementById('strat-sr-breakout-filter').checked = !!p.srBreakout;

  document.getElementById('strat-rsi-filter').checked = !!p.rsi;
  document.getElementById('strat-bollinger-filter').checked = !!p.bollinger;
  document.getElementById('strat-stochastic-filter').checked = !!p.stoch;
  document.getElementById('strat-macd-filter').checked = !!p.macd;
  document.getElementById('strat-supertrend-filter').checked = !!p.supertrend;
  document.getElementById('strat-sar-filter').checked = !!p.sar;
  document.getElementById('strat-ao-filter').checked = !!p.ao;
  document.getElementById('strat-williams-filter').checked = !!p.williams;
  document.getElementById('strat-cci-filter').checked = !!p.cci;
  document.getElementById('strat-demarker-filter').checked = !!p.demarker;
  document.getElementById('strat-elder-filter').checked = !!p.elder;
  document.getElementById('strat-alligator-filter').checked = !!p.alligator;
  document.getElementById('strat-keltner-filter').checked = !!p.keltner;
  document.getElementById('strat-vortex-filter').checked = !!p.vortex;

  document.getElementById('strat-smc-fvg').checked = !!p.fvg;
  document.getElementById('strat-smc-sweep').checked = !!p.sweep;
  document.getElementById('strat-smc-bos').checked = !!p.bos;
  document.getElementById('strat-smc-ob').checked = !!p.ob;

  showToast(`Loaded archetype preset: ${p.name}`, 'info');
}
window.applyArchetypePreset = applyArchetypePreset;

function createNewStrategy() {
  PersonalState.selectedStrategyId = null;
  renderStrategiesList();

  const randomSuffix = Math.floor(1000 + Math.random() * 9000);
  const newId = `strat_custom_${randomSuffix}`;

  document.getElementById('strat-form-title').textContent = 'Create New Custom Strategy';
  document.getElementById('strat-active-id-badge').textContent = newId;
  document.getElementById('strat-id-input').value = newId;
  document.getElementById('strat-name-input').value = `Custom Strategy #${randomSuffix}`;
  document.getElementById('strat-tf-select').value = '1M';
  document.getElementById('strat-exp-input').value = '2';
  document.getElementById('strat-payout-input').value = '80';
  document.getElementById('strat-direction-select').value = 'BOTH';
  document.getElementById('strat-cooldown-select').value = '120';
  document.getElementById('strat-mtg1-toggle').checked = false;

  document.getElementById('strat-trend-filter').checked = true;
  document.getElementById('strat-trend-mtf').value = '5M';
  document.getElementById('strat-trend-ema').value = '20';

  document.getElementById('strat-body-ratio').value = '0.50';
  document.getElementById('strat-max-wick').value = '0.35';
  document.getElementById('strat-doji-filter').checked = true;

  document.getElementById('strat-engulfing-filter').checked = false;
  document.getElementById('strat-sr-breakout-filter').checked = false;

  document.getElementById('strat-rsi-filter').checked = false;
  document.getElementById('strat-bollinger-filter').checked = false;
  document.getElementById('strat-stochastic-filter').checked = false;
  document.getElementById('strat-macd-filter').checked = false;
  document.getElementById('strat-supertrend-filter').checked = false;
  document.getElementById('strat-sar-filter').checked = false;
  document.getElementById('strat-ao-filter').checked = false;
  document.getElementById('strat-williams-filter').checked = false;
  document.getElementById('strat-cci-filter').checked = false;
  document.getElementById('strat-demarker-filter').checked = false;
  document.getElementById('strat-elder-filter').checked = false;
  document.getElementById('strat-alligator-filter').checked = false;
  document.getElementById('strat-keltner-filter').checked = false;
  document.getElementById('strat-vortex-filter').checked = false;

  document.getElementById('strat-smc-fvg').checked = false;
  document.getElementById('strat-smc-sweep').checked = false;
  document.getElementById('strat-smc-bos').checked = false;
  document.getElementById('strat-smc-ob').checked = false;

  const presetSelect = document.getElementById('strat-archetype-preset');
  if (presetSelect) presetSelect.value = "";

  const delBtn = document.getElementById('btn-delete-strategy');
  if (delBtn) delBtn.style.display = 'none';
}
window.createNewStrategy = createNewStrategy;

function savePersonalStrategy(e) {
  if (e) e.preventDefault();
  const stratId = document.getElementById('strat-id-input')?.value || `strat_${Date.now()}`;
  const name = document.getElementById('strat-name-input')?.value.trim();
  const tf = document.getElementById('strat-tf-select')?.value;
  const exp = parseInt(document.getElementById('strat-exp-input')?.value || '2', 10);
  const minP = parseInt(document.getElementById('strat-payout-input')?.value || '80', 10);
  const dir = document.getElementById('strat-direction-select')?.value || 'BOTH';
  const cd = parseInt(document.getElementById('strat-cooldown-select')?.value || '120', 10);
  const mtg1 = document.getElementById('strat-mtg1-toggle')?.checked || false;

  const trendEnabled = document.getElementById('strat-trend-filter')?.checked || false;
  const trendMtf = document.getElementById('strat-trend-mtf')?.value || '5M';
  const trendEma = parseInt(document.getElementById('strat-trend-ema')?.value || '20', 10);

  const minBodyRatio = parseFloat(document.getElementById('strat-body-ratio')?.value || '0.50');
  const maxOpposingWick = parseFloat(document.getElementById('strat-max-wick')?.value || '0.35');
  const dojiFilter = document.getElementById('strat-doji-filter')?.checked !== false;

  const engulfingEnabled = document.getElementById('strat-engulfing-filter')?.checked || false;
  const srBreakoutEnabled = document.getElementById('strat-sr-breakout-filter')?.checked || false;

  const rsiEnabled = document.getElementById('strat-rsi-filter')?.checked || false;
  const bollingerEnabled = document.getElementById('strat-bollinger-filter')?.checked || false;
  const stochEnabled = document.getElementById('strat-stochastic-filter')?.checked || false;
  const macdEnabled = document.getElementById('strat-macd-filter')?.checked || false;
  const supertrendEnabled = document.getElementById('strat-supertrend-filter')?.checked || false;
  const sarEnabled = document.getElementById('strat-sar-filter')?.checked || false;
  const aoEnabled = document.getElementById('strat-ao-filter')?.checked || false;
  const williamsEnabled = document.getElementById('strat-williams-filter')?.checked || false;
  const cciEnabled = document.getElementById('strat-cci-filter')?.checked || false;
  const demarkerEnabled = document.getElementById('strat-demarker-filter')?.checked || false;
  const elderEnabled = document.getElementById('strat-elder-filter')?.checked || false;
  const alligatorEnabled = document.getElementById('strat-alligator-filter')?.checked || false;
  const keltnerEnabled = document.getElementById('strat-keltner-filter')?.checked || false;
  const vortexEnabled = document.getElementById('strat-vortex-filter')?.checked || false;

  const indicatorsList = [];
  if (rsiEnabled) {
    indicatorsList.push({ indicator: 'RSI', period: 14, condition: 'BETWEEN', min_val: 20, max_val: 80 });
  }
  if (bollingerEnabled) {
    indicatorsList.push({ indicator: 'BOLLINGER', period: 20, condition: 'BETWEEN', min_val: 0, max_val: 1 });
  }
  if (stochEnabled) {
    indicatorsList.push({ indicator: 'STOCHASTIC', period: 14, condition: 'BETWEEN', min_val: 0, max_val: 100 });
  }
  if (macdEnabled) {
    indicatorsList.push({ indicator: 'MACD', period: 12, condition: 'BETWEEN', min_val: -999999, max_val: 999999 });
  }
  if (supertrendEnabled) {
    indicatorsList.push({ indicator: 'SUPERTREND', period: 10, condition: 'BULLISH' });
  }
  if (sarEnabled) {
    indicatorsList.push({ indicator: 'PARABOLIC_SAR', period: 14, condition: 'BULLISH' });
  }
  if (aoEnabled) {
    indicatorsList.push({ indicator: 'AWESOME_OSCILLATOR', period: 34, condition: 'BULLISH' });
  }
  if (williamsEnabled) {
    indicatorsList.push({ indicator: 'WILLIAMS_R', period: 14, condition: 'BETWEEN', min_val: -100, max_val: 0 });
  }
  if (cciEnabled) {
    indicatorsList.push({ indicator: 'CCI', period: 20, condition: 'GT', value: 0 });
  }
  if (demarkerEnabled) {
    indicatorsList.push({ indicator: 'DEMARKER', period: 14, condition: 'BETWEEN', min_val: 0, max_val: 1 });
  }
  if (elderEnabled) {
    indicatorsList.push({ indicator: 'BULLS_POWER', period: 13, condition: 'GT', value: 0 });
  }
  if (alligatorEnabled) {
    indicatorsList.push({ indicator: 'ALLIGATOR', period: 13, condition: 'BULLISH' });
  }
  if (keltnerEnabled) {
    indicatorsList.push({ indicator: 'KELTNER', period: 20, condition: 'BETWEEN', min_val: 0, max_val: 999999 });
  }
  if (vortexEnabled) {
    indicatorsList.push({ indicator: 'VORTEX', period: 14, condition: 'BULLISH' });
  }

  const smcFvg = document.getElementById('strat-smc-fvg')?.checked || false;
  const smcSweep = document.getElementById('strat-smc-sweep')?.checked || false;
  const smcBos = document.getElementById('strat-smc-bos')?.checked || false;
  const smcOb = document.getElementById('strat-smc-ob')?.checked || false;

  const payload = {
    id: stratId,
    name: name,
    enabled: true,
    direction: dir,
    timeframe: tf,
    expiry_minutes: exp,
    min_payout: minP,
    cooldown_seconds: cd,
    martingale_mtg1: mtg1,
    assets: ["ALL_REAL"],
    filters: {
      trend: { enabled: trendEnabled, mtf_timeframe: trendMtf, ema_period: trendEma, require_alignment: trendEnabled },
      candle_anatomy: { min_body_ratio: minBodyRatio, max_opposing_wick: maxOpposingWick, filter_preceding_doji: dojiFilter, filter_spike_multiplier: 2.8 },
      indicators: indicatorsList,
      price_action: { require_engulfing: engulfingEnabled, require_sr_breakout: srBreakoutEnabled, min_sr_clearance_pct: 0.1 },
      smc: { fvg_enabled: smcFvg, liquidity_sweep_enabled: smcSweep, bos_enabled: smcBos, order_block_enabled: smcOb }
    }
  };

  if (window.pywebview && window.pywebview.api && window.pywebview.api.save_strategy) {
    window.pywebview.api.save_strategy(payload).then(res => {
      showToast(`Strategy '${name}' saved successfully!`, 'success');
      PersonalState.selectedStrategyId = stratId;
      if (window.pywebview.api.get_strategies) {
        window.pywebview.api.get_strategies().then(s => {
          PersonalState.strategies = s;
          renderStrategiesList();
        });
      }
    });
  }
}
window.savePersonalStrategy = savePersonalStrategy;

function deleteCurrentStrategy() {
  const stratId = document.getElementById('strat-id-input')?.value;
  if (!stratId) return;

  if (window.pywebview && window.pywebview.api && window.pywebview.api.delete_strategy) {
    window.pywebview.api.delete_strategy(stratId).then(res => {
      showToast('Strategy deleted', 'info');
      if (window.pywebview.api.get_strategies) {
        window.pywebview.api.get_strategies().then(s => {
          PersonalState.strategies = s;
          if (PersonalState.strategies.length > 0) {
            selectStrategyForEditing(PersonalState.strategies[0].id);
          } else {
            createNewStrategy();
          }
        });
      }
    });
  }
}
window.deleteCurrentStrategy = deleteCurrentStrategy;

function togglePersonalStrategy(id, enabled) {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.toggle_strategy) {
    window.pywebview.api.toggle_strategy(id, enabled).then(() => {
      const s = PersonalState.strategies.find(x => x.id === id);
      if (s) s.enabled = enabled;
      renderStrategiesList();
    });
  }
}
window.togglePersonalStrategy = togglePersonalStrategy;

// ============================================================================
// Single Personal Telegram Bot Integration & Delivery Rules
// ============================================================================
function updateTelegramUI() {
  const tokInp = document.getElementById('personal-tg-token');
  const chatInp = document.getElementById('personal-tg-chat-id');
  const pill = document.getElementById('telegram-status-pill');
  const txt = document.getElementById('telegram-status-text');

  if (tokInp) tokInp.value = PersonalState.telegramToken || '';
  if (chatInp) chatInp.value = PersonalState.telegramChatId || '';

  const isLinked = !!(PersonalState.telegramToken && PersonalState.telegramChatId);
  if (pill && txt) {
    if (isLinked) {
      pill.className = 'status-pill connected';
      txt.textContent = 'Telegram: Linked';
    } else {
      pill.className = 'status-pill';
      txt.textContent = 'Telegram: Not Linked';
    }
  }
}
window.updateTelegramUI = updateTelegramUI;

function savePersonalTelegramCredentials(e) {
  if (e) e.preventDefault();
  const token = document.getElementById('personal-tg-token')?.value.trim();
  const chatId = document.getElementById('personal-tg-chat-id')?.value.trim();

  if (!token || !chatId) {
    showToast('Please enter both Bot Token and Personal Chat ID', 'error');
    return;
  }

  PersonalState.telegramToken = token;
  PersonalState.telegramChatId = chatId;

  persistTelegramManagerFull('Telegram Bot credentials linked successfully!');
}
window.savePersonalTelegramCredentials = savePersonalTelegramCredentials;

function updateTelegramRulesUI() {
  const cfg = PersonalState.telegramConfig || {};
  const chkSignals = document.getElementById('rule-send-signals');
  const chkPre = document.getElementById('rule-send-presignals');
  const chkOutcomes = document.getElementById('rule-send-outcomes');
  const chkSeq = document.getElementById('rule-sequential-lock');
  const chkCharts = document.getElementById('rule-attach-charts');

  if (chkSignals) chkSignals.checked = (cfg.send_signals !== false);
  if (chkPre) chkPre.checked = (cfg.send_pre_signals !== false);
  if (chkOutcomes) chkOutcomes.checked = (cfg.send_outcomes !== false);
  if (chkSeq) chkSeq.checked = (cfg.sequential_trade_lock !== false);
  if (chkCharts) chkCharts.checked = (cfg.attach_chart_photo !== false);
}

function saveTelegramDeliveryRules() {
  const sendSignals = document.getElementById('rule-send-signals')?.checked ?? true;
  const sendPre = document.getElementById('rule-send-presignals')?.checked ?? true;
  const sendOutcomes = document.getElementById('rule-send-outcomes')?.checked ?? true;
  const seqLock = document.getElementById('rule-sequential-lock')?.checked ?? true;
  const attachCharts = document.getElementById('rule-attach-charts')?.checked ?? true;

  PersonalState.telegramConfig.send_signals = sendSignals;
  PersonalState.telegramConfig.send_pre_signals = sendPre;
  PersonalState.telegramConfig.send_outcomes = sendOutcomes;
  PersonalState.telegramConfig.sequential_trade_lock = seqLock;
  PersonalState.telegramConfig.attach_chart_photo = attachCharts;

  persistTelegramManagerFull('Message delivery rules updated!');
}
window.saveTelegramDeliveryRules = saveTelegramDeliveryRules;

function persistTelegramManagerFull(successToast) {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.update_telegram_manager_config) {
    const payload = {
      bot_token: PersonalState.telegramToken,
      channels: [
        {
          id: PersonalState.telegramChatId,
          title: 'Personal Channel',
          enabled: true
        }
      ],
      send_signals: PersonalState.telegramConfig.send_signals !== false,
      send_pre_signals: PersonalState.telegramConfig.send_pre_signals !== false,
      send_outcomes: PersonalState.telegramConfig.send_outcomes !== false,
      sequential_trade_lock: PersonalState.telegramConfig.sequential_trade_lock !== false,
      attach_chart_photo: PersonalState.telegramConfig.attach_chart_photo !== false
    };

    window.pywebview.api.update_telegram_manager_config(payload).then(res => {
      updateTelegramUI();
      if (res && res.config) {
        PersonalState.telegramConfig = res.config;
      }
      showToast(successToast || 'Saved successfully', 'success');
    }).catch(err => {
      showToast('Failed to save Telegram configuration', 'error');
    });
  }
}

function sendTestPersonalSignal() {
  const chatId = PersonalState.telegramChatId || document.getElementById('personal-tg-chat-id')?.value.trim();

  if (!chatId) {
    showToast('Please configure your Telegram Chat ID first.', 'error');
    switchView('telegram');
    return;
  }

  if (window.pywebview && window.pywebview.api && window.pywebview.api.test_send_telegram_channel) {
    const msg = '🔔 <b>TradePulse Personal Signal Ping</b>\n<i>Live market engine operational!</i>';
    window.pywebview.api.test_send_telegram_channel(chatId, msg).then(res => {
      if (res && res.success) {
        showToast('Test signal sent to your personal Telegram!', 'success');
      } else {
        showToast(res && res.error ? res.error : 'Failed to send test signal', 'error');
      }
    }).catch(e => {
      showToast('Failed to trigger test signal', 'error');
    });
  }
}
window.sendTestPersonalSignal = sendTestPersonalSignal;

// ============================================================================
// User-Friendly Message Appearance & Card Style Customizer
// ============================================================================
PersonalState.cardStyle = 'vip';
PersonalState.cardPreviewTab = 'signal';
PersonalState.cardOptions = {
  strategy: true,
  payout: true,
  timing: true,
  guidelines: true
};

function initTemplateEditor() {
  updateCardPreview();
}

function selectCardStyle(style) {
  PersonalState.cardStyle = style;
  const vipBtn = document.getElementById('style-btn-vip');
  const minBtn = document.getElementById('style-btn-minimal');
  if (vipBtn && minBtn) {
    if (style === 'vip') {
      vipBtn.style.borderColor = 'var(--cyan-bright)';
      vipBtn.style.background = 'rgba(0, 240, 255, 0.08)';
      minBtn.style.borderColor = 'var(--border)';
      minBtn.style.background = 'transparent';
    } else {
      minBtn.style.borderColor = 'var(--cyan-bright)';
      minBtn.style.background = 'rgba(0, 240, 255, 0.08)';
      vipBtn.style.borderColor = 'var(--border)';
      vipBtn.style.background = 'transparent';
    }
  }
  updateCardPreview();
}
window.selectCardStyle = selectCardStyle;

function onCardOptionChanged() {
  PersonalState.cardOptions.strategy = document.getElementById('card-opt-strategy')?.checked ?? true;
  PersonalState.cardOptions.payout = document.getElementById('card-opt-payout')?.checked ?? true;
  PersonalState.cardOptions.timing = document.getElementById('card-opt-timing')?.checked ?? true;
  PersonalState.cardOptions.guidelines = document.getElementById('card-opt-guidelines')?.checked ?? true;
  updateCardPreview();
}
window.onCardOptionChanged = onCardOptionChanged;

function switchPreviewTab(tab) {
  PersonalState.cardPreviewTab = tab;
  ['sig', 'pre', 'out'].forEach(k => {
    const el = document.getElementById(`prev-tab-${k}`);
    if (el) el.classList.remove('active');
  });
  if (tab === 'signal') document.getElementById('prev-tab-sig')?.classList.add('active');
  if (tab === 'pre_signal') document.getElementById('prev-tab-pre')?.classList.add('active');
  if (tab === 'outcome') document.getElementById('prev-tab-out')?.classList.add('active');
  updateCardPreview();
}
window.switchPreviewTab = switchPreviewTab;

function buildTemplateStrings() {
  const isVip = (PersonalState.cardStyle === 'vip');
  const opt = PersonalState.cardOptions;

  let sigTmpl = '';
  if (isVip) {
    sigTmpl = "🚀 <b>SIGNAL ALERT: {strategy}</b>\n" +
      "────────────────────────\n" +
      "📊 <b>Asset:</b> <code>{asset}</code>\n" +
      (opt.payout ? "💰 <b>Payout:</b> <b>{payout}%</b>\n" : "") +
      "{arrow} <b>Direction:</b> <b>{dir_badge}</b>\n" +
      (opt.timing ? "⏱ <b>Timeframe:</b> <b>{chart_timeframe}</b>\n⌛ <b>Expiry:</b> <b>{expiry} Mins</b>\n🕒 <b>Entry:</b> <b>Next Candle Open ({entry_time})</b>\n" : "");
    if (opt.guidelines) {
      sigTmpl += "────────────────────────\n<i>Place trade immediately on candle open.</i>";
    }
  } else {
    sigTmpl = "⚡ <b>{asset} — {dir_badge}</b>\n" +
      (opt.strategy ? "🎯 Strategy: {strategy}\n" : "") +
      (opt.payout ? "💰 Payout: {payout}%\n" : "") +
      (opt.timing ? "⌛ Expiry: {expiry}m | Entry: {entry_time}\n" : "");
  }

  let preTmpl = '';
  if (isVip) {
    preTmpl = "⚡ <b>PRE-SIGNAL RADAR: PREPARE ENTRY</b>\n" +
      "────────────────────────\n" +
      "📊 <b>Asset:</b> <code>{asset}</code>\n" +
      "🎯 <b>Direction:</b> <b>{dir_badge}</b>\n" +
      (opt.timing ? "⏱ <b>Timeframe:</b> <b>{timeframe}</b> (Expiry: {expiry}m)\n" : "") +
      (opt.payout ? "💰 <b>Payout:</b> <b>{payout}%</b>\n" : "") +
      "⏳ <b>Candle Close In:</b> <b>~{remaining_seconds}s</b>\n" +
      (opt.strategy ? "🧠 <b>Pattern:</b> {strategy}\n" : "") +
      "{stake_line}" +
      "────────────────────────\n" +
      "<i>Prepare pair & stake in Quotex. Entry on candle close.</i>";
  } else {
    preTmpl = "⚡ <b>PRE-ALERT: {asset} ({dir_badge})</b>\n" +
      "⏳ Candle Close: ~{remaining_seconds}s\n" +
      (opt.payout ? "💰 Payout: {payout}%\n" : "") +
      "{stake_line}";
  }

  let outTmpl = "{header}\n" +
    "────────────────────────\n" +
    "📊 <b>Asset:</b> <code>{asset}</code>\n" +
    (opt.strategy ? "🎯 <b>Strategy:</b> <code>{strategy}</code>\n" : "") +
    "📌 <b>Direction:</b> <b>{direction}</b>\n" +
    "🏁 <b>Result:</b> <b>{outcome_badge}</b>\n" +
    "━━━━━━━━━━━━━━━━━━━━\n" +
    "💵 <b>Entry Strike:</b> <code>{entry_price}</code>\n" +
    "🏁 <b>Exit Price:</b>   <code>{exit_price}</code>\n" +
    "{pnl_text}\n" +
    "━━━━━━━━━━━━━━━━━━━━\n" +
    "🔒 <i>TradePulse Real-Time Verification</i>";

  return {
    signal: sigTmpl.trim(),
    pre_signal: preTmpl.trim(),
    outcome: outTmpl.trim(),
    circuit_breaker: DEFAULT_TEMPLATES.circuit_breaker
  };
}

function updateCardPreview() {
  const box = document.getElementById('template-preview-box');
  if (!box) return;

  const templates = buildTemplateStrings();
  const tab = PersonalState.cardPreviewTab || 'signal';
  let raw = templates[tab] || templates.signal;

  raw = raw
    .replace(/{strategy}/g, 'Dual Bollinger Protrusion')
    .replace(/{asset}/g, 'EUR/USD')
    .replace(/{payout}/g, '85')
    .replace(/{arrow}/g, '🟢')
    .replace(/{dir_badge}/g, 'CALL (BUY)')
    .replace(/{direction}/g, 'CALL')
    .replace(/{chart_timeframe}/g, '1M')
    .replace(/{timeframe}/g, '1M')
    .replace(/{expiry}/g, '1')
    .replace(/{entry_time}/g, '14:35:00')
    .replace(/{remaining_seconds}/g, '20')
    .replace(/{stake_line}/g, '💵 <b>Stake:</b> $25.00 (Kelly Edge)\n')
    .replace(/{header}/g, '🎉 <b>TRADE WON — EUR/USD (CALL)</b>')
    .replace(/{outcome_badge}/g, 'WIN (PROFIT)')
    .replace(/{entry_price}/g, '1.08450')
    .replace(/{exit_price}/g, '1.08472')
    .replace(/{pnl_text}/g, '💰 <b>Net Return:</b> +$21.25');

  box.innerHTML = raw.replace(/\n/g, '<br>');
}
window.updateCardPreview = updateCardPreview;

function saveUserCardPreferences() {
  const tmpls = buildTemplateStrings();
  if (window.pywebview && window.pywebview.api && window.pywebview.api.update_telegram_manager_config) {
    const payload = {
      templates: tmpls
    };
    window.pywebview.api.update_telegram_manager_config(payload).then(res => {
      showToast('Message appearance preferences saved!', 'success');
    }).catch(e => {
      showToast('Saved preferences locally', 'info');
    });
  } else {
    showToast('Saved appearance preferences', 'success');
  }
}
window.saveUserCardPreferences = saveUserCardPreferences;

function resetCardStyleToDefault() {
  PersonalState.cardStyle = 'vip';
  PersonalState.cardOptions = {
    strategy: true,
    payout: true,
    timing: true,
    guidelines: true
  };
  const chkStrat = document.getElementById('card-opt-strategy');
  const chkPay = document.getElementById('card-opt-payout');
  const chkTime = document.getElementById('card-opt-timing');
  const chkGuide = document.getElementById('card-opt-guidelines');
  if (chkStrat) chkStrat.checked = true;
  if (chkPay) chkPay.checked = true;
  if (chkTime) chkTime.checked = true;
  if (chkGuide) chkGuide.checked = true;
  selectCardStyle('vip');
  showToast('Reset to default VIP card style', 'info');
}
window.resetCardStyleToDefault = resetCardStyleToDefault;

// ============================================================================
// Trading Hours & Session Schedule Controller
// ============================================================================
function initScheduleUI() {
  const sched = PersonalState.scheduleConfig;
  const chk = document.getElementById('pref-schedule-toggle');
  const startInp = document.getElementById('sched-start-time');
  const endInp = document.getElementById('sched-end-time');
  const tzSel = document.getElementById('sched-tz-select');

  if (chk) chk.checked = !!sched.enabled;
  if (startInp) startInp.value = sched.start_time || '00:00';
  if (endInp) endInp.value = sched.end_time || '23:59';
  if (tzSel) tzSel.value = sched.use_utc ? 'utc' : 'local';

  renderScheduleDays();
  evaluateScheduleStatusUI();
}

function renderScheduleDays() {
  const container = document.getElementById('sched-days-container');
  if (!container) return;
  const allowed = new Set(PersonalState.scheduleConfig.allowed_days || []);

  const days = [
    { code: "Mo", label: "Mon" },
    { code: "Tu", label: "Tue" },
    { code: "We", label: "Wed" },
    { code: "Th", label: "Thu" },
    { code: "Fr", label: "Fri" },
    { code: "Sa", label: "Sat" },
    { code: "Su", label: "Sun" }
  ];

  container.innerHTML = days.map(d => {
    const isActive = allowed.has(d.code);
    const style = isActive
      ? 'background: rgba(0, 240, 255, 0.2); border-color: var(--cyan-bright); color: #fff;'
      : 'opacity: 0.45; border-style: dashed;';
    return `<button type="button" class="token-chip" style="${style}" onclick="toggleSchedDay('${d.code}')">${d.label}</button>`;
  }).join('');
}

function toggleSchedDay(dayCode) {
  let days = PersonalState.scheduleConfig.allowed_days || [];
  if (days.includes(dayCode)) {
    days = days.filter(d => d !== dayCode);
  } else {
    days.push(dayCode);
  }
  PersonalState.scheduleConfig.allowed_days = days;
  renderScheduleDays();
  saveTradingSchedule();
}
window.toggleSchedDay = toggleSchedDay;

function applySessionPreset(preset) {
  if (preset === 'london') {
    PersonalState.scheduleConfig.start_time = "08:00";
    PersonalState.scheduleConfig.end_time = "17:00";
    PersonalState.scheduleConfig.use_utc = true;
    PersonalState.scheduleConfig.allowed_days = ["Mo", "Tu", "We", "Th", "Fr"];
  } else if (preset === 'ny') {
    PersonalState.scheduleConfig.start_time = "13:00";
    PersonalState.scheduleConfig.end_time = "22:00";
    PersonalState.scheduleConfig.use_utc = true;
    PersonalState.scheduleConfig.allowed_days = ["Mo", "Tu", "We", "Th", "Fr"];
  } else if (preset === 'overlap') {
    PersonalState.scheduleConfig.start_time = "13:00";
    PersonalState.scheduleConfig.end_time = "17:00";
    PersonalState.scheduleConfig.use_utc = true;
    PersonalState.scheduleConfig.allowed_days = ["Mo", "Tu", "We", "Th", "Fr"];
  } else if (preset === 'all_weekdays') {
    PersonalState.scheduleConfig.start_time = "00:00";
    PersonalState.scheduleConfig.end_time = "23:59";
    PersonalState.scheduleConfig.use_utc = true;
    PersonalState.scheduleConfig.allowed_days = ["Mo", "Tu", "We", "Th", "Fr"];
  }

  PersonalState.scheduleConfig.enabled = true;
  initScheduleUI();
  saveTradingSchedule();
  showToast(`Applied ${preset.toUpperCase()} trading preset!`, 'success');
}
window.applySessionPreset = applySessionPreset;

function toggleTradingSchedule(enabled) {
  PersonalState.scheduleConfig.enabled = enabled;
  saveTradingSchedule();
}
window.toggleTradingSchedule = toggleTradingSchedule;

function saveTradingSchedule() {
  const startInp = document.getElementById('sched-start-time')?.value || '00:00';
  const endInp = document.getElementById('sched-end-time')?.value || '23:59';
  const tzSel = document.getElementById('sched-tz-select')?.value || 'utc';
  const enabled = document.getElementById('pref-schedule-toggle')?.checked ?? false;

  PersonalState.scheduleConfig.start_time = startInp;
  PersonalState.scheduleConfig.end_time = endInp;
  PersonalState.scheduleConfig.use_utc = (tzSel === 'utc');
  PersonalState.scheduleConfig.enabled = enabled;

  if (window.pywebview && window.pywebview.api && window.pywebview.api.update_advanced_filters_config) {
    window.pywebview.api.update_advanced_filters_config({
      session_scheduler: {
        enabled: PersonalState.scheduleConfig.enabled,
        allowed_days: PersonalState.scheduleConfig.allowed_days,
        start_time: PersonalState.scheduleConfig.start_time,
        end_time: PersonalState.scheduleConfig.end_time,
        use_utc: PersonalState.scheduleConfig.use_utc
      }
    }).then(() => {
      evaluateScheduleStatusUI();
    });
  }
}
window.saveTradingSchedule = saveTradingSchedule;

function evaluateScheduleStatusUI() {
  const label = document.getElementById('sched-status-label');
  if (!label) return;

  const cfg = PersonalState.scheduleConfig;
  if (!cfg.enabled) {
    label.textContent = '🟢 24/7 Active (Schedule Filter Disabled)';
    label.style.color = 'var(--emerald)';
    return;
  }

  const now = new Date();
  const dayIndex = cfg.use_utc ? now.getUTCDay() : now.getDay();
  const dayCodeMap = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];
  const currentDayCode = dayCodeMap[dayIndex];

  const allowedDays = new Set(cfg.allowed_days || []);
  if (!allowedDays.has(currentDayCode)) {
    label.textContent = `🟡 Standby (Today is ${currentDayCode} — Market Paused)`;
    label.style.color = 'var(--gold)';
    return;
  }

  const h = cfg.use_utc ? now.getUTCHours() : now.getHours();
  const m = cfg.use_utc ? now.getUTCMinutes() : now.getMinutes();
  const nowMins = h * 60 + m;

  const [sH, sM] = (cfg.start_time || "00:00").split(':').map(Number);
  const [eH, eM] = (cfg.end_time || "23:59").split(':').map(Number);
  const startMins = sH * 60 + sM;
  const endMins = eH * 60 + eM;

  let inWindow = false;
  if (startMins <= endMins) {
    inWindow = (nowMins >= startMins && nowMins <= endMins);
  } else {
    inWindow = (nowMins >= startMins || nowMins <= endMins);
  }

  if (inWindow) {
    label.textContent = `🟢 Session Active (${cfg.start_time} - ${cfg.end_time} ${cfg.use_utc ? 'UTC' : 'Local'})`;
    label.style.color = 'var(--emerald)';
  } else {
    label.textContent = `🟡 Standby (Outside Scheduled Hours: ${cfg.start_time} - ${cfg.end_time})`;
    label.style.color = 'var(--gold)';
  }
}

// ============================================================================
// Real-Time Event Listeners
// ============================================================================
window.onBatchTicks = function(ticks) {
  if (!ticks) return;
  for (const [sym, data] of Object.entries(ticks)) {
    PersonalState.prices[sym] = data.price;
    const rateEl = document.getElementById(`rate-${sanitizeId(sym)}`);
    if (rateEl) rateEl.textContent = formatLivePrice(sym, data.price);
    if (sym === PersonalState.activeChartPair && chartEngine) {
      chartEngine.updateLiveTick(data.price);
    }
  }
};

window.onSignalFired = function(sig) {
  if (!sig) return;
  PersonalState.history.unshift(sig);
  renderHistoryTable();
  const sigCount = document.getElementById('stat-signals-today');
  if (sigCount) sigCount.textContent = PersonalState.history.length;
  showToast(`🚀 Signal Fired: ${sig.direction} on ${sig.asset_symbol} (${sig.strategy_name})`, 'success');
};

window.onTradeOutcome = function(sig) {
  if (!sig) return;
  const isWin = sig.status === 'WIN';
  showToast(`${isWin ? '🎉 WON' : '🛑 LOST'} Trade: ${sig.asset_symbol} (${sig.direction})`, isWin ? 'success' : 'error');
  if (window.pywebview && window.pywebview.api && window.pywebview.api.get_performance_stats) {
    window.pywebview.api.get_performance_stats().then(stats => {
      const wrEl = document.getElementById('stat-winrate');
      if (wrEl && stats) wrEl.textContent = `${stats.win_rate || 0}%`;
    });
  }
};

function renderHistoryTable() {
  const tbody = document.getElementById('personal-history-tbody');
  if (!tbody) return;
  if (!PersonalState.history || PersonalState.history.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; padding: 20px; color: var(--text-dim);">No personal trade signals recorded yet.</td></tr>';
    return;
  }
  tbody.innerHTML = PersonalState.history.map(s => {
    const isWin = s.status === 'WIN';
    const isLoss = s.status === 'LOSS';
    const badgeColor = isWin ? 'var(--emerald)' : (isLoss ? 'var(--rose)' : 'var(--gold)');
    const audit = s.audit_trail || {};
    const mfe = audit.mfe !== undefined ? `+${audit.mfe}` : '-';
    const mae = audit.mae !== undefined ? `-${audit.mae}` : '-';
    return `
      <tr>
        <td style="font-family: var(--font-mono); font-size: 11px;">${s.created_at ? new Date(s.created_at).toLocaleTimeString() : '-'}</td>
        <td style="font-weight: 700; color: #fff;">${s.asset_symbol}</td>
        <td>${s.strategy_name || 'Confluence'}</td>
        <td style="font-weight: 700; color: ${s.direction === 'CALL' ? 'var(--emerald)' : 'var(--rose)'};">${s.direction}</td>
        <td style="font-family: var(--font-mono);">${s.entry_price || '-'}</td>
        <td style="font-family: var(--font-mono);">${s.exit_price || '-'}</td>
        <td style="font-family: var(--font-mono); font-size: 11px; color: var(--emerald);">${mfe}</td>
        <td style="font-family: var(--font-mono); font-size: 11px; color: var(--rose);">${mae}</td>
        <td><span style="font-weight: 800; color: ${badgeColor};">${s.status || 'ACTIVE'}</span></td>
      </tr>
    `;
  }).join('');
}

// ============================================================================
// Safeguards Controls
// ============================================================================
function toggleSafeguard(type, enabled) {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.update_advanced_filters_config) {
    const payload = {};
    if (type === 'news') {
      payload.news_calendar = { enabled: enabled };
    } else if (type === 'risk') {
      payload.risk_manager = { enabled: enabled };
    }
    window.pywebview.api.update_advanced_filters_config(payload).then(() => {
      showToast(`Safeguard updated: ${type} is ${enabled ? 'ENABLED' : 'DISABLED'}`, 'info');
    });
  }
}
window.toggleSafeguard = toggleSafeguard;

function navigateBroker(url) {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.navigate_broker) {
    window.pywebview.api.navigate_broker(url);
  }
}
window.navigateBroker = navigateBroker;

function refreshBrokerTerminal() {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.reload_broker) {
    window.pywebview.api.reload_broker();
  }
}
window.refreshBrokerTerminal = refreshBrokerTerminal;

// ============================================================================
// Toast System & Helpers
// ============================================================================
function showToast(msg, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<span>${type === 'success' ? '✅' : (type === 'error' ? '🛑' : 'ℹ️')}</span><span>${escapeHtml(msg)}</span>`;
  container.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}
window.showToast = showToast;

function escapeHtml(str) {
  return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ============================================================================
// 1-Year Subscription & Single-PC License Management
// ============================================================================
function updateLicenseStatusUI() {
  // Developer license check handled in background; not displayed on user interface.
}
window.updateLicenseStatusUI = updateLicenseStatusUI;

function openLicenseModal() {}
window.openLicenseModal = openLicenseModal;

function closeLicenseModal() {}
window.closeLicenseModal = closeLicenseModal;

function copyHWID() {
  const hwid = PersonalState.license?.hwid || document.getElementById('lic-modal-hwid')?.textContent.trim();
  if (hwid) {
    navigator.clipboard.writeText(hwid).then(() => {
      showToast('Copied Machine HWID to clipboard!', 'info');
    });
  }
}
window.copyHWID = copyHWID;

function handleActivateLicense(e) {
  if (e) e.preventDefault();
  const key = document.getElementById('lic-modal-key-input')?.value.trim();
  const server = document.getElementById('lic-modal-server-input')?.value.trim();

  if (!key) {
    showToast('Please enter your subscription license key', 'error');
    return;
  }

  if (window.pywebview && window.pywebview.api && window.pywebview.api.activate_license) {
    window.pywebview.api.activate_license(key, server).then(res => {
      if (res && res.success) {
        PersonalState.license = res.license || {};
        updateLicenseStatusUI();
        showToast('🎉 Subscription verified and bound to this machine!', 'success');
        closeLicenseModal();
      } else {
        showToast(res && res.message ? res.message : 'License verification failed', 'error');
        if (res && res.license) {
          PersonalState.license = res.license;
          updateLicenseStatusUI();
        }
      }
    }).catch(err => {
      showToast('Network error contacting master licensing server', 'error');
    });
  }
}
window.handleActivateLicense = handleActivateLicense;

// ============================================================================
// Technical Indicators & Analysis Tools Modal Controller
// ============================================================================
function openIndicatorsModal() {
  document.getElementById('indicators-modal')?.classList.add('active');
}
window.openIndicatorsModal = openIndicatorsModal;

function closeIndicatorsModal() {
  document.getElementById('indicators-modal')?.classList.remove('active');
}
window.closeIndicatorsModal = closeIndicatorsModal;

function toggleToolIndicator(name) {
  const chk = document.getElementById(`tool-chk-${name}`);
  if (chk) {
    chk.checked = !chk.checked;
  }
  if (chartEngine) {
    if (name === 'ema') {
      chartEngine.indicators.ema20 = chk ? chk.checked : !chartEngine.indicators.ema20;
      chartEngine.indicators.ema50 = chartEngine.indicators.ema20;
      chartEngine.render();
    } else if (name === 'bb') {
      chartEngine.indicators.bb = chk ? chk.checked : !chartEngine.indicators.bb;
      chartEngine.render();
    } else {
      showToast(`${name.toUpperCase()} indicator overlay enabled`, 'info');
    }
  }
}
window.toggleToolIndicator = toggleToolIndicator;

// ============================================================================
// Interactive Backtesting & Strategy Simulation Controller
// ============================================================================
function openBacktestModal() {
  const sel = document.getElementById('bt-strategy-select');
  if (sel && PersonalState.strategies) {
    sel.innerHTML = PersonalState.strategies.map(s => `
      <option value="${s.id}" ${s.id === PersonalState.selectedStrategyId ? 'selected' : ''}>
        ${s.name} (${s.timeframe} • ${s.expiry_minutes}m)
      </option>
    `).join('');
  }
  document.getElementById('backtest-modal')?.classList.add('active');
}
window.openBacktestModal = openBacktestModal;

function closeBacktestModal() {
  document.getElementById('backtest-modal')?.classList.remove('active');
}
window.closeBacktestModal = closeBacktestModal;

function executeBacktest() {
  const stratId = document.getElementById('bt-strategy-select')?.value;
  const symbol = document.getElementById('bt-symbol-select')?.value || 'EUR/USD';
  const payout = parseFloat(document.getElementById('bt-payout-input')?.value || '85');

  if (!stratId) {
    showToast('Please select a strategy to backtest', 'error');
    return;
  }

  showToast(`Running simulation for '${stratId}' on ${symbol}...`, 'info');

  if (window.pywebview && window.pywebview.api && window.pywebview.api.run_strategy_backtest_custom) {
    window.pywebview.api.run_strategy_backtest_custom(stratId, symbol, payout).then(res => {
      if (!res || res.error) {
        showToast(res ? res.error : 'Backtest returned no data', 'error');
        return;
      }
      renderBacktestResults(res);
      showToast(`Simulation complete: ${res.win_rate}% Win Rate (${res.total_signals} trades)`, 'success');
    }).catch(e => {
      showToast('Backtest execution failed', 'error');
    });
  }
}
window.executeBacktest = executeBacktest;

function renderBacktestResults(res) {
  document.getElementById('bt-empty-state').style.display = 'none';
  const container = document.getElementById('bt-results-container');
  if (container) container.style.display = 'block';

  const wr = document.getElementById('bt-stat-winrate');
  if (wr) wr.textContent = `${res.win_rate || 0}%`;

  const counts = document.getElementById('bt-stat-counts');
  if (counts) counts.textContent = `${res.wins || 0}W / ${res.losses || 0}L (${res.draws || 0} Draws)`;

  const pf = document.getElementById('bt-stat-pf');
  if (pf) pf.textContent = `${res.profit_factor || 0.00}`;

  const ev = document.getElementById('bt-stat-ev');
  if (ev) ev.textContent = `EV: ${res.ev_per_trade >= 0 ? '+' : ''}$${res.ev_per_trade || 0.00} / $10`;

  const dd = document.getElementById('bt-stat-dd');
  if (dd) dd.textContent = `$${res.max_drawdown || 0.00}`;

  const net = document.getElementById('bt-stat-net');
  if (net) net.textContent = `Net: ${res.net_profit >= 0 ? '+' : ''}$${res.net_profit || 0.00}`;

  const mfeMae = document.getElementById('bt-stat-mfe-mae');
  if (mfeMae) mfeMae.textContent = `+${res.avg_mfe || 0} / -${res.avg_mae || 0}`;

  const tbody = document.getElementById('bt-trades-tbody');
  if (tbody && res.signals) {
    tbody.innerHTML = res.signals.map((s, idx) => {
      const isWin = s.outcome === 'WIN';
      const isLoss = s.outcome === 'LOSS';
      const badgeColor = isWin ? 'var(--emerald)' : (isLoss ? 'var(--rose)' : 'var(--gold)');
      return `
        <tr>
          <td style="font-family: var(--font-mono); font-size: 11px;">#${s.bar_index || idx + 1} (${s.timestamp ? new Date(s.timestamp * 1000).toLocaleTimeString() : '-'})</td>
          <td style="font-weight: 700; color: ${s.direction === 'CALL' ? 'var(--emerald)' : 'var(--rose)'};">${s.direction}</td>
          <td style="font-family: var(--font-mono);">${s.entry_price || '-'}</td>
          <td style="font-family: var(--font-mono);">${s.exit_price || '-'}</td>
          <td style="font-family: var(--font-mono); color: var(--emerald);">+${s.mfe || 0}</td>
          <td style="font-family: var(--font-mono); color: var(--rose);">-${s.mae || 0}</td>
          <td><span style="font-weight: 800; color: ${badgeColor};">${s.outcome}</span></td>
        </tr>
      `;
    }).join('');
  }
}

// ============================================================================
// Quant Expected Value & Kelly Stake Sizing
// ============================================================================
function recalcQuantEV() {
  const payout = parseFloat(document.getElementById('strat-payout-input')?.value || '85');
  const winRate = parseFloat(document.getElementById('stat-winrate')?.textContent || '62.5');

  if (window.pywebview && window.pywebview.api && window.pywebview.api.calculate_quant_ev) {
    window.pywebview.api.calculate_quant_ev(payout, winRate, 1000.0).then(res => {
      if (!res) return;
      const be = document.getElementById('quant-be-rate');
      if (be) be.textContent = `${res.break_even_win_rate}% (at ${res.payout_pct}% Payout)`;

      const kelly = document.getElementById('quant-kelly-stake');
      if (kelly) kelly.textContent = `${res.half_kelly_recommended_pct}% ($${res.recommended_stake_amount} / $1k)`;

      const evVal = document.getElementById('quant-ev-value');
      if (evVal) {
        evVal.textContent = `${res.ev_per_10_dollar_trade >= 0 ? '+' : ''}$${res.ev_per_10_dollar_trade} / $10`;
        evVal.style.color = res.has_positive_edge ? 'var(--cyan-bright)' : 'var(--rose)';
      }

      const badge = document.getElementById('quant-edge-badge');
      if (badge) {
        badge.textContent = res.has_positive_edge ? 'Positive Edge' : 'Negative Edge';
        badge.style.background = res.has_positive_edge ? 'rgba(16, 185, 129, 0.2)' : 'rgba(244, 63, 94, 0.2)';
        badge.style.color = res.has_positive_edge ? 'var(--emerald)' : 'var(--rose)';
      }
    });
  }
}
window.recalcQuantEV = recalcQuantEV;

// ============================================================================
// Telegram HD Chart Test Dispatch
// ============================================================================
function sendTestTelegramChart() {
  const chatId = PersonalState.telegramChatId || document.getElementById('personal-tg-chat-id')?.value.trim();
  if (!chatId) {
    showToast('Please configure your Telegram Chat ID first', 'error');
    return;
  }
  showToast('Rendering and dispatching HD candlestick chart to Telegram...', 'info');
  if (window.pywebview && window.pywebview.api && window.pywebview.api.test_send_telegram_chart) {
    window.pywebview.api.test_send_telegram_chart(chatId).then(res => {
      if (res && res.success) {
        showToast('📸 HD Candlestick Chart photo sent to your Telegram!', 'success');
      } else {
        showToast(res && res.error ? res.error : 'Failed to send chart photo', 'error');
      }
    }).catch(e => {
      showToast('Chart dispatch request failed', 'error');
    });
  }
}
window.sendTestTelegramChart = sendTestTelegramChart;

