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

const DEFAULT_TEMPLATES = {
  signal: "🚀 <b>SIGNAL ALERT: {strategy}</b>\n" +
    "────────────────────────\n" +
    "📊 <b>Asset:</b> <code>{asset}</code>\n" +
    "💰 <b>Payout:</b> <b>{payout}%</b>\n" +
    "{arrow} <b>Direction:</b> <b>{dir_badge}</b>\n" +
    "⏱ <b>Timeframe:</b> <b>{chart_timeframe}</b>\n" +
    "⌛ <b>Expiry:</b> <b>{expiry} Mins</b>\n" +
    "🕒 <b>Entry:</b> <b>Next Candle Open ({entry_time})</b>\n" +
    "────────────────────────\n" +
    "<i>Place trade immediately on candle open.</i>",
  pre_signal: "⚡ <b>PRE-SIGNAL RADAR: PREPARE ENTRY</b>\n" +
    "────────────────────────\n" +
    "📊 <b>Asset:</b> <code>{asset}</code>\n" +
    "🎯 <b>Direction:</b> <b>{dir_badge}</b>\n" +
    "⏱ <b>Timeframe:</b> <b>{timeframe}</b> (Expiry: {expiry}m)\n" +
    "💰 <b>Payout:</b> <b>{payout}%</b>\n" +
    "⏳ <b>Candle Close In:</b> <b>~{remaining_seconds}s</b>\n" +
    "🧠 <b>Pattern:</b> {strategy}\n" +
    "{stake_line}" +
    "────────────────────────\n" +
    "<i>Prepare pair & stake in Quotex. Entry on candle close.</i>",
  outcome: "{header}\n" +
    "────────────────────────\n" +
    "📊 <b>Asset:</b> <code>{asset}</code>\n" +
    "🎯 <b>Strategy:</b> <code>{strategy}</code>\n" +
    "📌 <b>Direction:</b> <b>{direction}</b>\n" +
    "🏁 <b>Result:</b> <b>{outcome_badge}</b>\n" +
    "━━━━━━━━━━━━━━━━━━━━\n" +
    "💵 <b>Entry Strike:</b> <code>{entry_price}</code>\n" +
    "🏁 <b>Exit Price:</b>   <code>{exit_price}</code>\n" +
    "{pnl_text}\n" +
    "━━━━━━━━━━━━━━━━━━━━\n" +
    "🔒 <i>TradePulse Real-Time Verification</i>",
  circuit_breaker: "🛑 <b>TRADEPULSE CIRCUIT BREAKER ACTIVATED</b>\n" +
    "━━━━━━━━━━━━━━━━━━━━\n" +
    "⚠️ <b>Signal Scanner Auto-Paused</b>\n" +
    "• <b>Trigger Reason:</b> <b>{cb_reason}</b>\n" +
    "• <b>Session Net PnL:</b> <b>{net_pnl}</b>\n" +
    "• <b>Total Trades:</b> <b>{total_trades}</b>\n" +
    "━━━━━━━━━━━━━━━━━━━━\n" +
    "🔒 <i>Scanner halted to safeguard capital. Manage in TradePulse Terminal.</i>"
};

let chartEngine = null;

// ============================================================================
// HTML & Attribute Sanitizers (XSS Defense)
// ============================================================================
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function escapeAttr(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function escapeJsString(str) {
  if (!str) return '';
  return String(str)
    .replace(/\\/g, '\\\\')
    .replace(/'/g, "\\'")
    .replace(/"/g, '\\"')
    .replace(/</g, '\\x3c')
    .replace(/>/g, '\\x3e');
}

// ============================================================================
// Initialization & pywebview Handshake
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
  chartEngine = new InteractiveChartEngine('interactiveChartCanvas');
  window.chartEngine = chartEngine;

  // Initialize live message appearance preview immediately on load
  initTemplateEditor();

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
  changeChartPair(PersonalState.activeChartPair || 'EUR/USD');
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

  // If entering strategies view, initialize and resize strategy visualizer
  if (viewName === 'strategies') {
    setTimeout(() => {
      if (!strategyChartEngine) {
        initStrategyVisualizer();
      } else {
        strategyChartEngine.resize();
        fetchCandlesForStrategyPreview(activeStrategyPreviewPair);
      }
    }, 60);
  }

  // If entering telegram view, refresh the live message card preview
  if (viewName === 'telegram') {
    updateCardPreview();
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
    const safeJsSym = escapeJsString(sym);
    const price = PersonalState.prices[sym] ? formatLivePrice(sym, PersonalState.prices[sym]) : '---';
    const payout = PersonalState.payouts[sym] ? `${PersonalState.payouts[sym]}%` : '85%';

    return `
      <tr>
        <td>
          <div class="pair-badge">
            <div class="pair-flag">💱</div>
            <span>${escapeHtml(sym)}</span>
          </div>
        </td>
        <td class="rate-cell" id="rate-${sanitizeId(sym)}">${escapeHtml(price)}</td>
        <td><span class="payout-pill">${escapeHtml(payout)}</span></td>
        <td style="text-align: right;">
          <button class="btn-secondary" style="padding: 4px 10px; font-size: 11px;" onclick="openPairChart('${safeJsSym}')">
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
  const pairs = liveAssets.length > 0 ? liveAssets.map(a => a.symbol) : ALL_REAL_FOREX_PAIRS;
  sel.innerHTML = pairs.map(sym => `<option value="${sym}">${sym}</option>`).join('');
  if (PersonalState.activeChartPair) {
    sel.value = PersonalState.activeChartPair;
  }
}

function updateChartHudStats(candles, symbol) {
  if (!candles || candles.length === 0) return;
  const last = candles[candles.length - 1];
  const first = candles[0];

  const priceEl = document.getElementById('chart-hud-price');
  const changeEl = document.getElementById('chart-hud-change');
  const highEl = document.getElementById('chart-hud-high');
  const lowEl = document.getElementById('chart-hud-low');
  const spreadEl = document.getElementById('chart-hud-spread');
  const payoutEl = document.getElementById('chart-hud-payout');

  if (priceEl) priceEl.textContent = formatLivePrice(symbol, last.close);

  if (changeEl) {
    const diff = last.close - first.open;
    const pct = ((diff / first.open) * 100).toFixed(2);
    const isPos = diff >= 0;
    changeEl.textContent = `${isPos ? '+' : ''}${pct}%`;
    changeEl.style.color = isPos ? 'var(--emerald)' : 'var(--rose)';
    if (priceEl) priceEl.style.color = isPos ? 'var(--emerald)' : 'var(--rose)';
  }

  let highest = -Infinity;
  let lowest = Infinity;
  for (let i = 0; i < candles.length; i++) {
    if (candles[i].high > highest) highest = candles[i].high;
    if (candles[i].low < lowest) lowest = candles[i].low;
  }

  if (highEl && highest !== -Infinity) highEl.textContent = formatLivePrice(symbol, highest);
  if (lowEl && lowest !== Infinity) lowEl.textContent = formatLivePrice(symbol, lowest);

  if (spreadEl) {
    const isJpy = symbol.includes('JPY');
    const spreadPips = (isJpy ? 0.012 : 0.00008) * (isJpy ? 100 : 10000);
    spreadEl.textContent = `${spreadPips.toFixed(1)} pips`;
  }

  if (payoutEl) {
    const payout = PersonalState.payouts[symbol] || 85;
    payoutEl.textContent = `${payout}% PAYOUT`;
  }
}
window.updateChartHudStats = updateChartHudStats;

function changeChartPair(pair) {
  if (!pair) return;
  PersonalState.activeChartPair = pair;

  // Sync Dropdown
  const sel = document.getElementById('chart-pair-select');
  if (sel && sel.value !== pair) sel.value = pair;

  // Sync Top Pair Chips
  const chipSanitized = sanitizeId(pair);
  document.querySelectorAll('[id^="chip-pair-"]').forEach(chip => {
    chip.classList.toggle('active', chip.id === `chip-pair-${chipSanitized}`);
  });

  // Update Payout badge
  const payout = PersonalState.payouts[pair] || 85;
  const payoutEl = document.getElementById('chart-hud-payout');
  if (payoutEl) payoutEl.textContent = `${payout}% PAYOUT`;

  // Update Live Rate from state if available
  const curPrice = PersonalState.prices[pair];
  if (curPrice) {
    const priceEl = document.getElementById('chart-hud-price');
    if (priceEl) priceEl.textContent = formatLivePrice(pair, curPrice);
  }

  // Update Chart Engine
  if (chartEngine) {
    chartEngine.setSymbol(pair);
    fetchCandlesForPair(pair);
  }
}
window.changeChartPair = changeChartPair;

function fetchCandlesForPair(symbol, tf = '1M') {
  const reqTf = tf || (chartEngine ? chartEngine.timeframe : '1M');
  const targetSymbol = symbol || PersonalState.activeChartPair || 'EUR/USD';

  if (window.pywebview && window.pywebview.api && window.pywebview.api.get_candles_for_chart) {
    window.pywebview.api.get_candles_for_chart(targetSymbol, reqTf).then(candles => {
      if (chartEngine && Array.isArray(candles)) {
        chartEngine.setCandles(candles);
        updateChartHudStats(candles, targetSymbol);
      }
    }).catch(err => {
      console.warn('Error fetching candles:', err);
    });
  }
}
window.fetchCandlesForPair = fetchCandlesForPair;

function setChartTimeframe(tf) {
  document.querySelectorAll('#btn-tf-1m, #btn-tf-3m, #btn-tf-5m, #btn-tf-15m, #btn-tf-30m').forEach(b => b.classList.remove('active'));
  const btn = document.getElementById(`btn-tf-${tf.toLowerCase()}`);
  if (btn) btn.classList.add('active');

  if (chartEngine) {
    chartEngine.timeframe = tf;
    fetchCandlesForPair(PersonalState.activeChartPair, tf);
    showToast(`Timeframe set to ${tf}`, 'info');
  }
}
window.setChartTimeframe = setChartTimeframe;

function setChartStyle(style) {
  if (chartEngine) {
    chartEngine.setChartMode(style);
    showToast(`Chart style changed to ${style}`, 'info');
  }
}
window.setChartStyle = setChartStyle;

function toggleChartOverlay(overlay) {
  if (!chartEngine) return;
  if (overlay === 'ema') {
    chartEngine.toggleIndicator('ema20');
    chartEngine.toggleIndicator('ema50');
    const active = chartEngine.indicators.ema20;
    const btn = document.getElementById('btn-ind-ema');
    if (btn) btn.classList.toggle('active', active);
    showToast(`EMA 20/50 Ribbon ${active ? 'Enabled' : 'Disabled'}`, 'info');
  } else if (overlay === 'bb') {
    chartEngine.toggleIndicator('bb');
    const active = chartEngine.indicators.bb;
    const btn = document.getElementById('btn-ind-bb');
    if (btn) btn.classList.toggle('active', active);
    showToast(`Bollinger Cloud ${active ? 'Enabled' : 'Disabled'}`, 'info');
  } else if (overlay === 'supertrend') {
    chartEngine.toggleIndicator('supertrend');
    const active = chartEngine.indicators.supertrend;
    const btn = document.getElementById('btn-ind-supertrend');
    if (btn) btn.classList.toggle('active', active);
    showToast(`Supertrend ATR Ribbon ${active ? 'Enabled' : 'Disabled'}`, 'info');
  } else if (overlay === 'sr') {
    chartEngine.toggleIndicator('sr');
    const active = chartEngine.indicators.sr;
    const btn = document.getElementById('btn-ind-sr');
    if (btn) btn.classList.toggle('active', active);
    showToast(`Support & Resistance Pivots ${active ? 'Enabled' : 'Disabled'}`, 'info');
  }
}
window.toggleChartOverlay = toggleChartOverlay;

function toggleChartSubPanel(panel) {
  if (!chartEngine) return;
  if (panel === 'rsi') {
    chartEngine.toggleIndicator('rsi');
    const active = chartEngine.indicators.rsi;
    const btn = document.getElementById('btn-sub-rsi');
    if (btn) btn.classList.toggle('active', active);
    showToast(`RSI (14) Sub-Panel ${active ? 'Enabled' : 'Disabled'}`, 'info');
  } else if (panel === 'macd') {
    chartEngine.toggleIndicator('macd');
    const active = chartEngine.indicators.macd;
    const btn = document.getElementById('btn-sub-macd');
    if (btn) btn.classList.toggle('active', active);
    showToast(`MACD Histogram Sub-Panel ${active ? 'Enabled' : 'Disabled'}`, 'info');
  } else if (panel === 'volume') {
    chartEngine.toggleIndicator('volume');
    const active = chartEngine.indicators.volume;
    const btn = document.getElementById('btn-sub-volume');
    if (btn) btn.classList.toggle('active', active);
    showToast(`Volume Histogram ${active ? 'Enabled' : 'Disabled'}`, 'info');
  }
}
window.toggleChartSubPanel = toggleChartSubPanel;

function setChartDrawing(tool) {
  if (!chartEngine) return;
  chartEngine.setDrawingTool(tool);
  if (tool === 'clear') {
    showToast('Cleared all chart drawings', 'info');
  } else if (tool === 'hline') {
    showToast('Click anywhere on chart to place Horizontal S&R Ray', 'info');
  } else if (tool === 'trendline') {
    showToast('Click two points on chart to draw Trendline', 'info');
  }
}
window.setChartDrawing = setChartDrawing;

function chartZoom(dir) {
  if (!chartEngine) return;
  if (dir < 0) {
    chartEngine.zoomIn();
  } else {
    chartEngine.zoomOut();
  }
}
window.chartZoom = chartZoom;

function chartResetView() {
  if (!chartEngine) return;
  chartEngine.resetView();
  showToast('Chart zoom & pan reset to default', 'info');
}
window.chartResetView = chartResetView;

// ============================================================================
// Complete Strategy Customizer Lab
// ============================================================================
const ALL_REAL_FOREX_PAIRS = [
  "EUR/USD", "GBP/USD", "USD/JPY", "USD/CAD", "USD/CHF", "AUD/USD", "NZD/USD",
  "EUR/GBP", "EUR/JPY", "EUR/AUD", "EUR/CAD", "EUR/CHF", "EUR/NZD",
  "GBP/JPY", "GBP/AUD", "GBP/CAD", "GBP/CHF", "GBP/NZD",
  "AUD/JPY", "AUD/CAD", "AUD/CHF", "AUD/NZD",
  "CAD/JPY", "CAD/CHF", "CHF/JPY",
  "NZD/JPY", "NZD/CAD", "NZD/CHF"
];

const MAJOR_REAL_FOREX_PAIRS = [
  "EUR/USD", "GBP/USD", "USD/JPY", "USD/CAD", "USD/CHF", "AUD/USD", "NZD/USD"
];

let personalCurrentScope = 'ALL_REAL';
let personalSelectedCustomAssets = new Set(ALL_REAL_FOREX_PAIRS);

// ============================================================================
// VISUAL STRATEGY STUDIO CONTROLLER & REAL-TIME BENCH
// ============================================================================
let strategyChartEngine = null;
let activeStrategyPreviewPair = 'EUR/USD';
let activeStrategyPreviewTf = '1M';
let savedStrategyBaselineWR = 0;
let strategyFormDebounceTimer = null;

function initStrategyVisualizer() {
  const canvas = document.getElementById('strategyVisualizerCanvas');
  if (!canvas) return;

  if (!strategyChartEngine) {
    strategyChartEngine = new InteractiveChartEngine('strategyVisualizerCanvas');
  }

  // Populate pair selector with all 28 Real Forex pairs
  const sel = document.getElementById('strat-preview-pair-select');
  if (sel) {
    sel.innerHTML = ALL_REAL_FOREX_PAIRS.map(sym => `<option value="${sym}">${sym}</option>`).join('');
    sel.value = activeStrategyPreviewPair;
  }

  fetchCandlesForStrategyPreview(activeStrategyPreviewPair);
}
window.initStrategyVisualizer = initStrategyVisualizer;

function setStrategyPreviewTf(tf) {
  activeStrategyPreviewTf = tf;
  document.querySelectorAll('[id^="btn-strat-tf-"]').forEach(btn => {
    btn.classList.toggle('active', btn.id === `btn-strat-tf-${tf.toLowerCase()}`);
  });
  if (strategyChartEngine) {
    strategyChartEngine.timeframe = tf;
  }
  fetchCandlesForStrategyPreview(activeStrategyPreviewPair);
}
window.setStrategyPreviewTf = setStrategyPreviewTf;

function changeStrategyPreviewPair(pair) {
  if (!pair) return;
  activeStrategyPreviewPair = pair;
  const sel = document.getElementById('strat-preview-pair-select');
  if (sel && sel.value !== pair) sel.value = pair;
  fetchCandlesForStrategyPreview(pair);
}
window.changeStrategyPreviewPair = changeStrategyPreviewPair;

function fetchCandlesForStrategyPreview(pair) {
  if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.get_candles_for_chart) {
    return;
  }
  window.pywebview.api.get_candles_for_chart(pair, activeStrategyPreviewTf).then(candles => {
    if (candles && candles.length > 0 && strategyChartEngine) {
      strategyChartEngine.setCandles(candles);
      strategyChartEngine.symbol = pair;
      strategyChartEngine.timeframe = activeStrategyPreviewTf;
      recalculateStrategyVisualizer();
    }
  }).catch(err => {
    console.error('Error fetching candles for strategy visualizer:', err);
  });
}
window.fetchCandlesForStrategyPreview = fetchCandlesForStrategyPreview;

function onStrategyFormChange() {
  if (strategyFormDebounceTimer) clearTimeout(strategyFormDebounceTimer);
  strategyFormDebounceTimer = setTimeout(() => {
    recalculateStrategyVisualizer();
  }, 40);
}
window.onStrategyFormChange = onStrategyFormChange;

function recalculateStrategyVisualizer() {
  if (!strategyChartEngine || !strategyChartEngine.candles || strategyChartEngine.candles.length === 0) return;
  if (typeof StrategyEvaluator === 'undefined') return;

  const currentStrat = compileCurrentStrategyForm();
  if (!currentStrat) return;

  // 1. Configure chart indicators matching strategy
  strategyChartEngine.setStrategyConfig(currentStrat);

  // 2. Evaluate strategy on visible authentic candles
  const evalResult = StrategyEvaluator.evaluateStrategy(currentStrat, strategyChartEngine.candles);

  // 3. Set signal markers (CALL/PUT arrows + WIN/LOSS tags) on canvas
  strategyChartEngine.setSignalMarkers(evalResult.results_log);

  // 4. Update HUD Performance Stats
  const sigEl = document.getElementById('hud-strat-signals');
  const winEl = document.getElementById('hud-strat-wins');
  const lossEl = document.getElementById('hud-strat-losses');
  const wrEl = document.getElementById('hud-strat-winrate');
  const pfEl = document.getElementById('hud-strat-pf');

  if (sigEl) sigEl.textContent = evalResult.total_signals;
  if (winEl) winEl.textContent = evalResult.wins;
  if (lossEl) lossEl.textContent = evalResult.losses;
  if (wrEl) {
    wrEl.textContent = `${evalResult.win_rate}%`;
    wrEl.style.color = evalResult.win_rate >= 60 ? 'var(--emerald)' : (evalResult.win_rate >= 54 ? 'var(--cyan-bright)' : 'var(--rose)');
  }
  if (pfEl) pfEl.textContent = evalResult.profit_factor.toFixed(2);

  // 5. Update A/B Diff Badge
  const diffBadge = document.getElementById('strat-diff-badge');
  if (diffBadge) {
    if (savedStrategyBaselineWR > 0) {
      const diff = evalResult.win_rate - savedStrategyBaselineWR;
      const isPos = diff >= 0;
      diffBadge.style.display = 'inline-block';
      diffBadge.textContent = `vs Saved: ${isPos ? '+' : ''}${diff.toFixed(1)}% WR`;
      diffBadge.style.color = isPos ? 'var(--emerald)' : 'var(--rose)';
      diffBadge.style.borderColor = isPos ? 'rgba(0, 245, 155, 0.4)' : 'rgba(255, 51, 102, 0.4)';
    } else {
      diffBadge.style.display = 'none';
    }
  }

  // 6. Update Active Bar Rule Radar
  updateActiveRuleRadar(currentStrat);
}
window.recalculateStrategyVisualizer = recalculateStrategyVisualizer;

function updateActiveRuleRadar(currentStrat) {
  if (!strategyChartEngine || !strategyChartEngine.candles || typeof StrategyEvaluator === 'undefined') return;
  const radar = StrategyEvaluator.evaluateActiveBarRadar(currentStrat, strategyChartEngine.candles, strategyChartEngine.livePrice);

  const summaryEl = document.getElementById('strat-radar-summary');
  const chipsEl = document.getElementById('strat-radar-chips');

  if (summaryEl) {
    summaryEl.textContent = `${radar.summary} (${radar.score}% MET)`;
    summaryEl.style.color = radar.score >= 70 ? 'var(--emerald)' : (radar.score >= 50 ? 'var(--cyan-bright)' : 'var(--text-dim)');
  }

  if (chipsEl) {
    chipsEl.innerHTML = radar.rules.map(r => {
      let clickAction = '';
      if (r.name.includes('Bollinger') || r.name.includes('Dev')) {
        clickAction = `onclick="focusStrategyRule('bollinger')" title="Click to tune Bollinger Band Contact settings"`;
      } else if (r.name.includes('Body') || r.name.includes('Ratio')) {
        clickAction = `onclick="focusStrategyRule('body')" title="Click to tune Candle Anatomy settings"`;
      } else if (r.name.includes('RSI')) {
        clickAction = `onclick="focusStrategyRule('rsi')" title="Click to tune RSI settings"`;
      } else {
        clickAction = `onclick="focusStrategyRule('general')"`;
      }
      return `
        <button type="button" class="token-chip ${r.passed ? 'active' : ''}" ${clickAction} style="cursor: pointer; font-size: 10px; padding: 2px 8px; background: ${r.passed ? 'rgba(0, 245, 155, 0.18)' : 'rgba(255,255,255,0.06)'}; color: ${r.passed ? 'var(--emerald)' : 'var(--amber)'}; border-color: ${r.passed ? 'rgba(0, 245, 155, 0.4)' : 'rgba(245, 158, 11, 0.3)'}; transition: all 0.2s;">
          ${r.passed ? '✅' : '⏳'} ${r.name}
        </button>
      `;
    }).join('');
  }

  strategyChartEngine.updateLiveConfluenceRadar(radar);
}

function focusStrategyRule(ruleKey) {
  if (ruleKey === 'bollinger') {
    const sec = document.getElementById('sec-ind-bollinger');
    const checkbox = document.getElementById('strat-bollinger-filter');
    const drawer = document.getElementById('ind-params-bollinger');
    if (checkbox && !checkbox.checked) {
      checkbox.checked = true;
      toggleIndicatorDrawer('bollinger', true);
    } else if (drawer) {
      drawer.style.display = 'grid';
    }
    if (sec) {
      sec.scrollIntoView({ behavior: 'smooth', block: 'center' });
      sec.style.transition = 'all 0.4s ease';
      sec.style.background = 'rgba(0, 240, 255, 0.15)';
      sec.style.boxShadow = '0 0 15px rgba(0, 240, 255, 0.6)';
      sec.style.borderColor = 'var(--cyan-bright)';
      setTimeout(() => {
        sec.style.background = '';
        sec.style.boxShadow = '';
        sec.style.borderColor = 'transparent';
      }, 2500);
    }
    const devInput = document.getElementById('ind-bb-dev');
    if (devInput) {
      setTimeout(() => devInput.focus(), 300);
    }
    recalculateStrategyVisualizer();
    if (typeof showToast === 'function') showToast('Focused on Bollinger Band Contact rules', 'info');
  } else if (ruleKey === 'body') {
    const el = document.getElementById('strat-body-ratio');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      el.focus();
    }
  } else if (ruleKey === 'rsi') {
    const sec = document.getElementById('sec-ind-rsi');
    if (sec) sec.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}
window.focusStrategyRule = focusStrategyRule;

function compileCurrentStrategyForm() {
  const id = document.getElementById('strat-id-input')?.value || 'temp_strat';
  const name = document.getElementById('strat-name-input')?.value || 'Custom Strategy';
  const tf = document.getElementById('strat-tf-select')?.value || '1M';
  const expiry = parseInt(document.getElementById('strat-exp-input')?.value, 10) || 2;
  const payout = parseFloat(document.getElementById('strat-payout-input')?.value) || 80;
  const direction = document.getElementById('strat-direction-select')?.value || 'BOTH';
  const cooldown = parseInt(document.getElementById('strat-cooldown-select')?.value, 10) || 120;

  const trendEnabled = document.getElementById('strat-trend-filter')?.checked || false;
  const trendMtf = document.getElementById('strat-trend-mtf')?.value || '5M';
  const trendEma = parseInt(document.getElementById('strat-trend-ema')?.value, 10) || 20;

  const bodyRatio = parseFloat(document.getElementById('strat-body-ratio')?.value || 0.20);
  const maxWick = parseFloat(document.getElementById('strat-max-wick')?.value || 0.40);
  const filterDoji = document.getElementById('strat-doji-filter')?.checked || false;

  const indicators = [];

  // 1. Bollinger Bands
  if (document.getElementById('strat-bollinger-filter')?.checked) {
    indicators.push({
      indicator: 'BOLLINGER',
      params: {
        period_1: parseInt(document.getElementById('ind-bb-p1')?.value, 10) || 10,
        period_2: parseInt(document.getElementById('ind-bb-p2')?.value, 10) || 13,
        deviation: parseFloat(document.getElementById('ind-bb-dev')?.value) || 2.0,
        min_body_protrusion: parseFloat(document.getElementById('ind-bb-protrusion')?.value) || 20
      }
    });
  }

  // 2. Supertrend
  if (document.getElementById('strat-supertrend-filter')?.checked) {
    indicators.push({
      indicator: 'SUPERTREND',
      params: {
        atr_period: parseInt(document.getElementById('ind-st-period')?.value, 10) || 10,
        multiplier: parseFloat(document.getElementById('ind-st-mult')?.value) || 3.0
      }
    });
  }

  // 3. Parabolic SAR
  if (document.getElementById('strat-sar-filter')?.checked) {
    indicators.push({
      indicator: 'PARABOLIC_SAR',
      params: {
        step: parseFloat(document.getElementById('ind-sar-step')?.value) || 0.02,
        max_step: parseFloat(document.getElementById('ind-sar-max')?.value) || 0.2
      }
    });
  }

  // 4. Moving Average
  if (document.getElementById('strat-ma-filter')?.checked) {
    indicators.push({
      indicator: 'MOVING_AVERAGE',
      params: {
        period: parseInt(document.getElementById('ind-ma-period')?.value, 10) || 14,
        type: document.getElementById('ind-ma-type')?.value || 'SMA'
      }
    });
  }

  // 5. Keltner Channel
  if (document.getElementById('strat-keltner-filter')?.checked) {
    indicators.push({
      indicator: 'KELTNER',
      params: {
        ema_period: parseInt(document.getElementById('ind-keltner-period')?.value, 10) || 20,
        atr_period: parseInt(document.getElementById('ind-keltner-atr')?.value, 10) || 10,
        multiplier: parseFloat(document.getElementById('ind-keltner-mult')?.value) || 1.0
      }
    });
  }

  // 6. Donchian Channel
  if (document.getElementById('strat-donchian-filter')?.checked) {
    indicators.push({
      indicator: 'DONCHIAN',
      params: {
        period: parseInt(document.getElementById('ind-donchian-period')?.value, 10) || 20
      }
    });
  }

  // 7. Envelopes
  if (document.getElementById('strat-envelopes-filter')?.checked) {
    indicators.push({
      indicator: 'ENVELOPES',
      params: {
        period: parseInt(document.getElementById('ind-env-period')?.value, 10) || 14,
        deviation_pct: parseFloat(document.getElementById('ind-env-dev')?.value) || 0.1
      }
    });
  }

  // 8. Alligator
  if (document.getElementById('strat-alligator-filter')?.checked) {
    indicators.push({
      indicator: 'ALLIGATOR',
      params: {
        jaw_period: parseInt(document.getElementById('ind-allig-jaw')?.value, 10) || 13,
        teeth_period: parseInt(document.getElementById('ind-allig-teeth')?.value, 10) || 8,
        lips_period: parseInt(document.getElementById('ind-allig-lips')?.value, 10) || 5
      }
    });
  }

  // 9. Ichimoku Cloud
  if (document.getElementById('strat-ichimoku-filter')?.checked) {
    indicators.push({
      indicator: 'ICHIMOKU',
      params: {
        tenkan_period: parseInt(document.getElementById('ind-ichi-tenkan')?.value, 10) || 9,
        kijun_period: parseInt(document.getElementById('ind-ichi-kijun')?.value, 10) || 26,
        senkou_b_period: parseInt(document.getElementById('ind-ichi-senkou')?.value, 10) || 52
      }
    });
  }

  // 10. Fractal
  if (document.getElementById('strat-fractal-filter')?.checked) {
    indicators.push({
      indicator: 'FRACTAL',
      params: {
        period: parseInt(document.getElementById('ind-frac-period')?.value, 10) || 2
      }
    });
  }

  // 11. Zig Zag
  if (document.getElementById('strat-zigzag-filter')?.checked) {
    indicators.push({
      indicator: 'ZIGZAG',
      params: {
        depth: parseInt(document.getElementById('ind-zz-depth')?.value, 10) || 12,
        deviation: parseFloat(document.getElementById('ind-zz-dev')?.value) || 5,
        backstep: parseInt(document.getElementById('ind-zz-backstep')?.value, 10) || 3
      }
    });
  }

  // 12. RSI
  if (document.getElementById('strat-rsi-filter')?.checked) {
    indicators.push({
      indicator: 'RSI',
      params: {
        period: parseInt(document.getElementById('ind-rsi-period')?.value, 10) || 14,
        overbought: parseInt(document.getElementById('ind-rsi-ob')?.value, 10) || 70,
        oversold: parseInt(document.getElementById('ind-rsi-os')?.value, 10) || 30
      }
    });
  }

  // 13. Stochastic
  if (document.getElementById('strat-stochastic-filter')?.checked) {
    indicators.push({
      indicator: 'STOCHASTIC',
      params: {
        k_period: parseInt(document.getElementById('ind-stoch-k')?.value, 10) || 14,
        d_period: parseInt(document.getElementById('ind-stoch-d')?.value, 10) || 3,
        overbought: parseInt(document.getElementById('ind-stoch-ob')?.value, 10) || 80,
        oversold: parseInt(document.getElementById('ind-stoch-os')?.value, 10) || 20
      }
    });
  }

  // 14. MACD
  if (document.getElementById('strat-macd-filter')?.checked) {
    indicators.push({
      indicator: 'MACD',
      params: {
        fast_period: parseInt(document.getElementById('ind-macd-fast')?.value, 10) || 12,
        slow_period: parseInt(document.getElementById('ind-macd-slow')?.value, 10) || 26,
        signal_period: parseInt(document.getElementById('ind-macd-signal')?.value, 10) || 9
      }
    });
  }

  // 15. Awesome Oscillator
  if (document.getElementById('strat-ao-filter')?.checked) {
    indicators.push({
      indicator: 'AWESOME_OSCILLATOR',
      params: {
        fast_period: parseInt(document.getElementById('ind-ao-fast')?.value, 10) || 5,
        slow_period: parseInt(document.getElementById('ind-ao-slow')?.value, 10) || 34
      }
    });
  }

  // 16. Williams %R
  if (document.getElementById('strat-williams-filter')?.checked) {
    indicators.push({
      indicator: 'WILLIAMS_R',
      params: {
        period: parseInt(document.getElementById('ind-wr-period')?.value, 10) || 14,
        overbought: parseInt(document.getElementById('ind-wr-ob')?.value, 10) || -20,
        oversold: parseInt(document.getElementById('ind-wr-os')?.value, 10) || -80
      }
    });
  }

  // 17. CCI
  if (document.getElementById('strat-cci-filter')?.checked) {
    indicators.push({
      indicator: 'CCI',
      params: {
        period: parseInt(document.getElementById('ind-cci-period')?.value, 10) || 20,
        overbought: parseInt(document.getElementById('ind-cci-ob')?.value, 10) || 100,
        oversold: parseInt(document.getElementById('ind-cci-os')?.value, 10) || -100
      }
    });
  }

  // 18. DeMarker
  if (document.getElementById('strat-demarker-filter')?.checked) {
    indicators.push({
      indicator: 'DEMARKER',
      params: {
        period: parseInt(document.getElementById('ind-dem-period')?.value, 10) || 14,
        overbought: parseFloat(document.getElementById('ind-dem-ob')?.value) || 0.7,
        oversold: parseFloat(document.getElementById('ind-dem-os')?.value) || 0.3
      }
    });
  }

  // 19. Bulls & Bears Power (Elder Ray)
  if (document.getElementById('strat-elder-filter')?.checked) {
    indicators.push({
      indicator: 'ELDER_RAY',
      params: {
        period: parseInt(document.getElementById('ind-elder-period')?.value, 10) || 13
      }
    });
  }

  // 20. ADX
  if (document.getElementById('strat-adx-filter')?.checked) {
    indicators.push({
      indicator: 'ADX',
      params: {
        period: parseInt(document.getElementById('ind-adx-period')?.value, 10) || 14
      }
    });
  }

  // 21. Aroon
  if (document.getElementById('strat-aroon-filter')?.checked) {
    indicators.push({
      indicator: 'AROON',
      params: {
        period: parseInt(document.getElementById('ind-aroon-period')?.value, 10) || 14
      }
    });
  }

  // 22. ATR
  if (document.getElementById('strat-atr-filter')?.checked) {
    indicators.push({
      indicator: 'ATR',
      params: {
        period: parseInt(document.getElementById('ind-atr-period')?.value, 10) || 14
      }
    });
  }

  // 23. Momentum
  if (document.getElementById('strat-momentum-filter')?.checked) {
    indicators.push({
      indicator: 'MOMENTUM',
      params: {
        period: parseInt(document.getElementById('ind-mom-period')?.value, 10) || 10
      }
    });
  }

  // 24. ROC
  if (document.getElementById('strat-roc-filter')?.checked) {
    indicators.push({
      indicator: 'ROC',
      params: {
        period: parseInt(document.getElementById('ind-roc-period')?.value, 10) || 9
      }
    });
  }

  // 25. Vortex
  if (document.getElementById('strat-vortex-filter')?.checked) {
    indicators.push({
      indicator: 'VORTEX',
      params: {
        period: parseInt(document.getElementById('ind-vortex-period')?.value, 10) || 14
      }
    });
  }

  // 26. Schaff Trend Cycle
  if (document.getElementById('strat-stc-filter')?.checked) {
    indicators.push({
      indicator: 'SCHAFF_TREND_CYCLE',
      params: {
        fast_period: parseInt(document.getElementById('ind-stc-fast')?.value, 10) || 23,
        slow_period: parseInt(document.getElementById('ind-stc-slow')?.value, 10) || 50,
        cycle_period: parseInt(document.getElementById('ind-stc-cycle')?.value, 10) || 10
      }
    });
  }

  // 27. Volume Oscillator
  if (document.getElementById('strat-volosc-filter')?.checked) {
    indicators.push({
      indicator: 'VOLUME_OSCILLATOR',
      params: {
        short_period: parseInt(document.getElementById('ind-vo-short')?.value, 10) || 5,
        long_period: parseInt(document.getElementById('ind-vo-long')?.value, 10) || 10
      }
    });
  }

  const confToggle = document.getElementById('strat-confluence-toggle')?.checked || false;
  const confMin = parseInt(document.getElementById('strat-confluence-min')?.value, 10) || 2;
  const confScore = parseInt(document.getElementById('strat-confluence-score')?.value, 10) || 75;

  const smc = {
    fvg_enabled: document.getElementById('strat-smc-fvg')?.checked || false,
    liquidity_sweep_enabled: document.getElementById('strat-smc-sweep')?.checked || false,
    bos_enabled: document.getElementById('strat-smc-bos')?.checked || false,
    order_block_enabled: document.getElementById('strat-smc-ob')?.checked || false
  };

  return {
    id,
    name,
    timeframe: tf,
    expiry_minutes: expiry,
    min_payout: payout,
    direction,
    cooldown_seconds: cooldown,
    filters: {
      trend: { enabled: trendEnabled, mtf_timeframe: trendMtf, ema_period: trendEma },
      candle_anatomy: { min_body_ratio: bodyRatio, max_opposing_wick: maxWick, filter_preceding_doji: filterDoji },
      indicators,
      confluence: {
        enabled: confToggle,
        min_agreeing_factors: confMin,
        min_quality_score: confScore,
        min_factors: confToggle ? confMin : 1
      },
      smc
    }
  };

}

function revertStrategyChanges() {
  const currentId = document.getElementById('strat-id-input')?.value;
  if (!currentId) return;
  selectStrategyForEditing(currentId);
  showToast('Reverted parameters to saved strategy', 'info');
}
window.revertStrategyChanges = revertStrategyChanges;

// 28-Pair Confluence Matrix Modal Controller
function open28PairMatrixModal() {
  const modal = document.getElementById('matrix-modal');
  if (modal) {
    modal.classList.add('active');
    run28PairStrategyEvaluation();
  }
}
window.open28PairMatrixModal = open28PairMatrixModal;

function close28PairMatrixModal() {
  const modal = document.getElementById('matrix-modal');
  if (modal) modal.classList.remove('active');
}
window.close28PairMatrixModal = close28PairMatrixModal;

async function run28PairStrategyEvaluation() {
  const tbody = document.getElementById('matrix-results-tbody');
  const loadBar = document.getElementById('matrix-loading-bar');
  const progressFill = document.getElementById('matrix-progress-fill');
  const progressPct = document.getElementById('matrix-progress-pct');
  const btn = document.getElementById('btn-run-matrix-eval');

  if (!tbody) return;
  tbody.innerHTML = '';
  if (loadBar) loadBar.style.display = 'block';
  if (btn) btn.disabled = true;

  const currentStrat = compileCurrentStrategyForm();
  let profitableCount = 0;
  let totalWR = 0;
  let testedCount = 0;

  for (let i = 0; i < ALL_REAL_FOREX_PAIRS.length; i++) {
    const pair = ALL_REAL_FOREX_PAIRS[i];
    const pct = Math.round(((i + 1) / ALL_REAL_FOREX_PAIRS.length) * 100);
    if (progressFill) progressFill.style.width = `${pct}%`;
    if (progressPct) progressPct.textContent = `${pct}% (${pair})`;

    try {
      let candles = [];
      if (window.pywebview && window.pywebview.api && window.pywebview.api.get_candles_for_chart) {
        candles = await window.pywebview.api.get_candles_for_chart(pair, '1M');
      }

      if (candles && candles.length >= 25 && typeof StrategyEvaluator !== 'undefined') {
        const res = StrategyEvaluator.evaluateStrategy(currentStrat, candles);
        testedCount++;
        totalWR += res.win_rate;
        if (res.win_rate >= 55) profitableCount++;

        const curRate = candles[candles.length - 1].close;
        const payout = PersonalState.payouts[pair] || 85;
        const isProfitable = res.win_rate >= 55;

        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>${pair}</strong></td>
          <td style="font-family: var(--font-mono);">${formatLivePrice(pair, curRate)}</td>
          <td><span class="nav-badge" style="background: rgba(0, 245, 155, 0.1); color: var(--emerald);">${payout}%</span></td>
          <td>${res.total_signals}</td>
          <td><span style="color: var(--emerald);">${res.wins}W</span> / <span style="color: var(--rose);">${res.losses}L</span></td>
          <td><strong style="color: ${isProfitable ? 'var(--emerald)' : 'var(--rose)'}; font-size: 12px;">${res.win_rate}%</strong></td>
          <td style="font-family: var(--font-mono);">${res.profit_factor.toFixed(2)}</td>
          <td>
            <button type="button" class="btn-secondary" style="font-size: 10px; padding: 2px 8px;" onclick="close28PairMatrixModal(); changeStrategyPreviewPair('${pair}');">
              👁️ View
            </button>
          </td>
        `;
        tbody.appendChild(tr);
      }
    } catch (e) {
      console.debug('Matrix eval error for', pair, e);
    }
  }

  if (loadBar) loadBar.style.display = 'none';
  if (btn) btn.disabled = false;

  const profEl = document.getElementById('matrix-profitable-pairs');
  const avgWrEl = document.getElementById('matrix-avg-wr');
  if (profEl) profEl.textContent = `${profitableCount} / ${testedCount}`;
  if (avgWrEl && testedCount > 0) avgWrEl.textContent = `${(totalWR / testedCount).toFixed(1)}%`;
}
window.run28PairStrategyEvaluation = run28PairStrategyEvaluation;

function toggleIndicatorDrawer(key, show) {
  const drawer = document.getElementById(`ind-params-${key}`);
  if (drawer) {
    drawer.style.display = show ? 'grid' : 'none';
  }
}
window.toggleIndicatorDrawer = toggleIndicatorDrawer;

function setPersonalAssetScope(scope) {
  personalCurrentScope = scope;
  const pillAll = document.getElementById('scope-pill-all');
  const pillMajors = document.getElementById('scope-pill-majors');
  const pillCustom = document.getElementById('scope-pill-custom');
  const badge = document.getElementById('strat-asset-scope-badge');
  const customContainer = document.getElementById('strat-custom-assets-container');

  if (pillAll) pillAll.classList.toggle('active', scope === 'ALL_REAL');
  if (pillMajors) pillMajors.classList.toggle('active', scope === 'MAJORS');
  if (pillCustom) pillCustom.classList.toggle('active', scope === 'CUSTOM');

  if (scope === 'ALL_REAL') {
    if (badge) badge.textContent = 'All Real Forex (28 Pairs)';
    if (customContainer) customContainer.style.display = 'none';
  } else if (scope === 'MAJORS') {
    if (badge) badge.textContent = 'Major 7 Pairs';
    if (customContainer) customContainer.style.display = 'none';
  } else {
    if (badge) badge.textContent = `Custom (${personalSelectedCustomAssets.size} Pairs)`;
    if (customContainer) customContainer.style.display = 'block';
    renderPersonalAssetChips();
  }
}
window.setPersonalAssetScope = setPersonalAssetScope;

function togglePersonalAssetChip(pair) {
  if (personalSelectedCustomAssets.has(pair)) {
    personalSelectedCustomAssets.delete(pair);
  } else {
    personalSelectedCustomAssets.add(pair);
  }
  const badge = document.getElementById('strat-asset-scope-badge');
  if (badge && personalCurrentScope === 'CUSTOM') {
    badge.textContent = `Custom (${personalSelectedCustomAssets.size} Pairs)`;
  }
  renderPersonalAssetChips();
}
window.togglePersonalAssetChip = togglePersonalAssetChip;

function selectPersonalAssetGroup(type) {
  if (type === 'ALL') {
    ALL_REAL_FOREX_PAIRS.forEach(p => personalSelectedCustomAssets.add(p));
  } else if (type === 'NONE') {
    personalSelectedCustomAssets.clear();
  }
  const badge = document.getElementById('strat-asset-scope-badge');
  if (badge && personalCurrentScope === 'CUSTOM') {
    badge.textContent = `Custom (${personalSelectedCustomAssets.size} Pairs)`;
  }
  renderPersonalAssetChips();
}
window.selectPersonalAssetGroup = selectPersonalAssetGroup;

function filterPersonalAssetChips(query) {
  renderPersonalAssetChips(query);
}
window.filterPersonalAssetChips = filterPersonalAssetChips;

function renderPersonalAssetChips(filterQuery = '') {
  const container = document.getElementById('strat-asset-chips-grid');
  if (!container) return;

  const q = (filterQuery || '').trim().toUpperCase();
  const pairsToShow = ALL_REAL_FOREX_PAIRS.filter(p => !q || p.toUpperCase().includes(q));

  container.innerHTML = pairsToShow.map(pair => {
    const isSelected = personalSelectedCustomAssets.has(pair);
    return `
      <div class="personal-asset-chip ${isSelected ? 'active' : ''}" onclick="togglePersonalAssetChip('${pair}')">
        <span>${isSelected ? '✓' : '+'}</span>
        <span>${pair}</span>
      </div>
    `;
  }).join('');
}

function renderStrategiesList() {
  const strats = PersonalState.strategies || [];
  const masterSelect = document.getElementById('strategy-master-select');
  if (masterSelect) {
    masterSelect.innerHTML = strats.map(s => `
      <option value="${s.id}" ${s.id === PersonalState.selectedStrategyId ? 'selected' : ''}>
        ${s.enabled ? '⚡' : '⏸️'} ${escapeHtml(s.name)} (${s.timeframe || '1M'} • ${s.direction || 'BOTH'})
      </option>
    `).join('');
    if (PersonalState.selectedStrategyId) {
      masterSelect.value = PersonalState.selectedStrategyId;
    }
  }

  const container = document.getElementById('strategies-list-container');
  const countIndicator = document.getElementById('strat-count-indicator');
  if (countIndicator) {
    const activeCount = strats.filter(s => s.enabled).length;
    countIndicator.textContent = `${activeCount} / ${strats.length} Active`;
  }
  if (!container) return;

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

  // Asset scope
  const assets = strat.assets || ["ALL_REAL"];
  if (assets.includes("ALL_REAL") || assets.length === 0 || assets.length === ALL_REAL_FOREX_PAIRS.length) {
    personalSelectedCustomAssets = new Set(ALL_REAL_FOREX_PAIRS);
    setPersonalAssetScope('ALL_REAL');
  } else if (assets.length === MAJOR_REAL_FOREX_PAIRS.length && assets.every(p => MAJOR_REAL_FOREX_PAIRS.includes(p))) {
    personalSelectedCustomAssets = new Set(MAJOR_REAL_FOREX_PAIRS);
    setPersonalAssetScope('MAJORS');
  } else {
    personalSelectedCustomAssets = new Set(assets);
    setPersonalAssetScope('CUSTOM');
  }

  // Filters & Triggers
  const filters = strat.filters || {};
  const trend = filters.trend || {};
  const anatomy = filters.candle_anatomy || {};
  const pa = filters.price_action || {};
  const smc = filters.smc || {};
  const inds = filters.indicators || [];
  const conf = filters.confluence || {};

  document.getElementById('strat-trend-filter').checked = !!trend.enabled;
  document.getElementById('strat-trend-mtf').value = trend.mtf_timeframe || '5M';
  document.getElementById('strat-trend-ema').value = String(trend.ema_period || 20);

  // Precision candle anatomy values
  const bodyRatio = anatomy.min_body_ratio !== undefined ? Number(anatomy.min_body_ratio).toFixed(2) : '0.20';
  const maxWick = anatomy.max_opposing_wick !== undefined ? Number(anatomy.max_opposing_wick).toFixed(2) : '0.40';
  document.getElementById('strat-body-ratio').value = bodyRatio;
  document.getElementById('strat-max-wick').value = maxWick;
  document.getElementById('strat-doji-filter').checked = anatomy.filter_preceding_doji !== false;

  if (document.getElementById('strat-sr-clearance-input')) {
    document.getElementById('strat-sr-clearance-input').value = String(pa.min_sr_clearance_pct ?? 0.05);
  }
  if (document.getElementById('strat-pinbar-ratio-input')) {
    document.getElementById('strat-pinbar-ratio-input').value = String(anatomy.min_rejection_wick_ratio ?? 2.0);
  }

  document.getElementById('strat-engulfing-filter').checked = !!pa.require_engulfing;
  document.getElementById('strat-sr-breakout-filter').checked = !!pa.require_sr_breakout;

  // Technical Indicators & Drawers
  const syncInd = (key, names, cbId, paramMap) => {
    const found = inds.find(i => names.includes((i.indicator || '').toUpperCase()));
    const active = !!found;
    const cb = document.getElementById(cbId);
    if (cb) cb.checked = active;
    toggleIndicatorDrawer(key, active);
    if (found && found.params && paramMap) {
      for (const [elId, paramKey, defaultVal] of paramMap) {
        const el = document.getElementById(elId);
        if (el) el.value = found.params[paramKey] ?? defaultVal;
      }
    }
  };

  // 1. Bollinger
  syncInd('bollinger', ['BOLLINGER'], 'strat-bollinger-filter', [
    ['ind-bb-p1', 'period_1', 10],
    ['ind-bb-p2', 'period_2', 13],
    ['ind-bb-dev', 'deviation', 2.0],
    ['ind-bb-protrusion', 'min_body_protrusion', 20]
  ]);

  // 2. Supertrend
  syncInd('supertrend', ['SUPERTREND', 'ST'], 'strat-supertrend-filter', [
    ['ind-st-period', 'atr_period', 10],
    ['ind-st-mult', 'multiplier', 3.0]
  ]);

  // 3. Parabolic SAR
  syncInd('sar', ['PARABOLIC_SAR', 'SAR', 'PSAR'], 'strat-sar-filter', [
    ['ind-sar-step', 'step', 0.02],
    ['ind-sar-max', 'max_step', 0.2]
  ]);

  // 4. Moving Average
  syncInd('ma', ['MOVING_AVERAGE', 'MA', 'SMA_EMA'], 'strat-ma-filter', [
    ['ind-ma-period', 'period', 14],
    ['ind-ma-type', 'type', 'SMA']
  ]);

  // 5. Keltner Channel
  syncInd('keltner', ['KELTNER', 'DONCHIAN_KELTNER'], 'strat-keltner-filter', [
    ['ind-keltner-period', 'ema_period', 20],
    ['ind-keltner-atr', 'atr_period', 10],
    ['ind-keltner-mult', 'multiplier', 1.0]
  ]);

  // 6. Donchian Channel
  syncInd('donchian', ['DONCHIAN'], 'strat-donchian-filter', [
    ['ind-donchian-period', 'period', 20]
  ]);

  // 7. Envelopes
  syncInd('envelopes', ['ENVELOPES'], 'strat-envelopes-filter', [
    ['ind-env-period', 'period', 14],
    ['ind-env-dev', 'deviation_pct', 0.1]
  ]);

  // 8. Alligator
  syncInd('alligator', ['ALLIGATOR'], 'strat-alligator-filter', [
    ['ind-allig-jaw', 'jaw_period', 13],
    ['ind-allig-teeth', 'teeth_period', 8],
    ['ind-allig-lips', 'lips_period', 5]
  ]);

  // 9. Ichimoku Cloud
  syncInd('ichimoku', ['ICHIMOKU'], 'strat-ichimoku-filter', [
    ['ind-ichi-tenkan', 'tenkan_period', 9],
    ['ind-ichi-kijun', 'kijun_period', 26],
    ['ind-ichi-senkou', 'senkou_b_period', 52]
  ]);

  // 10. Fractal
  syncInd('fractal', ['FRACTAL'], 'strat-fractal-filter', [
    ['ind-frac-period', 'period', 2]
  ]);

  // 11. Zig Zag
  syncInd('zigzag', ['ZIGZAG', 'ZIG_ZAG'], 'strat-zigzag-filter', [
    ['ind-zz-depth', 'depth', 12],
    ['ind-zz-dev', 'deviation', 5],
    ['ind-zz-backstep', 'backstep', 3]
  ]);

  // 12. RSI
  syncInd('rsi', ['RSI'], 'strat-rsi-filter', [
    ['ind-rsi-period', 'period', 14],
    ['ind-rsi-ob', 'overbought', 70],
    ['ind-rsi-os', 'oversold', 30]
  ]);

  // 13. Stochastic
  syncInd('stoch', ['STOCHASTIC'], 'strat-stochastic-filter', [
    ['ind-stoch-k', 'k_period', 14],
    ['ind-stoch-d', 'd_period', 3],
    ['ind-stoch-ob', 'overbought', 80],
    ['ind-stoch-os', 'oversold', 20]
  ]);

  // 14. MACD
  syncInd('macd', ['MACD'], 'strat-macd-filter', [
    ['ind-macd-fast', 'fast_period', 12],
    ['ind-macd-slow', 'slow_period', 26],
    ['ind-macd-signal', 'signal_period', 9]
  ]);

  // 15. Awesome Oscillator
  syncInd('ao', ['AWESOME_OSCILLATOR', 'AO'], 'strat-ao-filter', [
    ['ind-ao-fast', 'fast_period', 5],
    ['ind-ao-slow', 'slow_period', 34]
  ]);

  // 16. Williams %R
  syncInd('williams', ['WILLIAMS_R', 'WILLIAMS_%R', 'WR'], 'strat-williams-filter', [
    ['ind-wr-period', 'period', 14],
    ['ind-wr-ob', 'overbought', -20],
    ['ind-wr-os', 'oversold', -80]
  ]);

  // 17. CCI
  syncInd('cci', ['CCI'], 'strat-cci-filter', [
    ['ind-cci-period', 'period', 20],
    ['ind-cci-ob', 'overbought', 100],
    ['ind-cci-os', 'oversold', -100]
  ]);

  // 18. DeMarker
  syncInd('demarker', ['DEMARKER', 'DEM'], 'strat-demarker-filter', [
    ['ind-dem-period', 'period', 14],
    ['ind-dem-ob', 'overbought', 0.7],
    ['ind-dem-os', 'oversold', 0.3]
  ]);

  // 19. Bulls & Bears Power (Elder Ray)
  syncInd('elder', ['BULLS_POWER', 'BEARS_POWER', 'ELDER', 'ELDER_RAY'], 'strat-elder-filter', [
    ['ind-elder-period', 'period', 13]
  ]);

  // 20. ADX
  syncInd('adx', ['ADX'], 'strat-adx-filter', [
    ['ind-adx-period', 'period', 14]
  ]);

  // 21. Aroon
  syncInd('aroon', ['AROON'], 'strat-aroon-filter', [
    ['ind-aroon-period', 'period', 14]
  ]);

  // 22. ATR
  syncInd('atr', ['ATR'], 'strat-atr-filter', [
    ['ind-atr-period', 'period', 14]
  ]);

  // 23. Momentum
  syncInd('momentum', ['MOMENTUM'], 'strat-momentum-filter', [
    ['ind-mom-period', 'period', 10]
  ]);

  // 24. ROC
  syncInd('roc', ['ROC'], 'strat-roc-filter', [
    ['ind-roc-period', 'period', 9]
  ]);

  // 25. Vortex
  syncInd('vortex', ['VORTEX'], 'strat-vortex-filter', [
    ['ind-vortex-period', 'period', 14]
  ]);

  // 26. Schaff Trend Cycle
  syncInd('stc', ['SCHAFF', 'STC', 'SCHAFF_TREND_CYCLE'], 'strat-stc-filter', [
    ['ind-stc-fast', 'fast_period', 23],
    ['ind-stc-slow', 'slow_period', 50],
    ['ind-stc-cycle', 'cycle_period', 10]
  ]);

  // 27. Volume Oscillator
  syncInd('volosc', ['VOLUME_OSCILLATOR', 'VO'], 'strat-volosc-filter', [
    ['ind-vo-short', 'short_period', 5],
    ['ind-vo-long', 'long_period', 10]
  ]);


  // Confluence Matrix
  if (document.getElementById('strat-confluence-toggle')) {
    document.getElementById('strat-confluence-toggle').checked = !!conf.enabled;
    document.getElementById('strat-confluence-min').value = String(conf.min_agreeing_factors ?? 2);
    document.getElementById('strat-confluence-score').value = String(conf.min_quality_score ?? 75);
  }

  // SMC
  document.getElementById('strat-smc-fvg').checked = !!smc.fvg_enabled;
  document.getElementById('strat-smc-sweep').checked = !!smc.liquidity_sweep_enabled;
  document.getElementById('strat-smc-bos').checked = !!smc.bos_enabled;
  document.getElementById('strat-smc-ob').checked = !!smc.order_block_enabled;

  const presetSelect = document.getElementById('strat-archetype-preset');
  if (presetSelect) presetSelect.value = "";

  const delBtn = document.getElementById('btn-delete-strategy');
  if (delBtn) delBtn.style.display = 'inline-block';

  // Set preview pair if strategy specifies assets
  if (strat.assets && strat.assets.length > 0 && strat.assets[0] !== 'ALL_REAL') {
    activeStrategyPreviewPair = strat.assets[0];
    const pairSel = document.getElementById('strat-preview-pair-select');
    if (pairSel) pairSel.value = activeStrategyPreviewPair;
  }

  // Update Visual Studio
  if (!strategyChartEngine) {
    initStrategyVisualizer();
  } else {
    fetchCandlesForStrategyPreview(activeStrategyPreviewPair);
  }
  const masterSelect = document.getElementById('strategy-master-select');
  if (masterSelect && masterSelect.value !== id) {
    masterSelect.value = id;
  }
}
window.selectStrategyForEditing = selectStrategyForEditing;

function duplicateCurrentStrategy() {
  const curId = PersonalState.selectedStrategyId;
  const strat = PersonalState.strategies.find(s => s.id === curId);
  if (!strat) return;
  const clone = JSON.parse(JSON.stringify(strat));
  clone.id = 'strat_' + Date.now();
  clone.name = clone.name + ' (Copy)';
  PersonalState.strategies.unshift(clone);
  PersonalState.selectedStrategyId = clone.id;
  renderStrategiesList();
  selectStrategyForEditing(clone.id);
  showToast(`Duplicated "${clone.name}"`, 'success');
}
window.duplicateCurrentStrategy = duplicateCurrentStrategy;

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

  const allDrawerKeys = ['bollinger', 'supertrend', 'sar', 'ma', 'keltner', 'donchian', 'envelopes', 'alligator', 'ichimoku', 'fractal', 'zigzag', 'rsi', 'stoch', 'macd', 'ao', 'williams', 'cci', 'demarker', 'elder', 'adx', 'aroon', 'atr', 'momentum', 'roc', 'vortex', 'stc', 'volosc'];
  allDrawerKeys.forEach(k => toggleIndicatorDrawer(k, false));

  const allIndicatorKeys = [
    { key: 'bollinger', cb: 'strat-bollinger-filter' },
    { key: 'supertrend', cb: 'strat-supertrend-filter' },
    { key: 'sar', cb: 'strat-sar-filter' },
    { key: 'ma', cb: 'strat-ma-filter' },
    { key: 'keltner', cb: 'strat-keltner-filter' },
    { key: 'donchian', cb: 'strat-donchian-filter' },
    { key: 'envelopes', cb: 'strat-envelopes-filter' },
    { key: 'alligator', cb: 'strat-alligator-filter' },
    { key: 'ichimoku', cb: 'strat-ichimoku-filter' },
    { key: 'fractal', cb: 'strat-fractal-filter' },
    { key: 'zigzag', cb: 'strat-zigzag-filter' },
    { key: 'rsi', cb: 'strat-rsi-filter' },
    { key: 'stoch', cb: 'strat-stochastic-filter' },
    { key: 'macd', cb: 'strat-macd-filter' },
    { key: 'ao', cb: 'strat-ao-filter' },
    { key: 'williams', cb: 'strat-williams-filter' },
    { key: 'cci', cb: 'strat-cci-filter' },
    { key: 'demarker', cb: 'strat-demarker-filter' },
    { key: 'elder', cb: 'strat-elder-filter' },
    { key: 'adx', cb: 'strat-adx-filter' },
    { key: 'aroon', cb: 'strat-aroon-filter' },
    { key: 'atr', cb: 'strat-atr-filter' },
    { key: 'momentum', cb: 'strat-momentum-filter' },
    { key: 'roc', cb: 'strat-roc-filter' },
    { key: 'vortex', cb: 'strat-vortex-filter' },
    { key: 'stc', cb: 'strat-stc-filter' },
    { key: 'volosc', cb: 'strat-volosc-filter' }
  ];

  allIndicatorKeys.forEach(item => {
    const active = !!p[item.key];
    const cb = document.getElementById(item.cb);
    if (cb) cb.checked = active;
    toggleIndicatorDrawer(item.key, active);
  });

  // Configure specific parameters & drawers per archetype
  if (presetKey === 'dual_bollinger_protrusion') {
    if (document.getElementById('ind-bb-p1')) document.getElementById('ind-bb-p1').value = "10";
    if (document.getElementById('ind-bb-p2')) document.getElementById('ind-bb-p2').value = "13";
    if (document.getElementById('ind-bb-dev')) document.getElementById('ind-bb-dev').value = "2.0";
    if (document.getElementById('ind-bb-protrusion')) document.getElementById('ind-bb-protrusion').value = "30";
    toggleIndicatorDrawer('bollinger', true);
    if (document.getElementById('strat-confluence-toggle')) document.getElementById('strat-confluence-toggle').checked = false;
    setPersonalAssetScope('ALL_REAL');
  } else if (presetKey === 'ultra_confluence') {
    toggleIndicatorDrawer('rsi', true);
    toggleIndicatorDrawer('supertrend', true);
    toggleIndicatorDrawer('sar', true);
    if (document.getElementById('strat-confluence-toggle')) {
      document.getElementById('strat-confluence-toggle').checked = true;
      document.getElementById('strat-confluence-min').value = "3";
      document.getElementById('strat-confluence-score').value = "80";
    }
  } else {
    if (document.getElementById('strat-confluence-toggle')) document.getElementById('strat-confluence-toggle').checked = false;
  }


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
  document.getElementById('strat-exp-input').value = '1';
  document.getElementById('strat-payout-input').value = '80';
  document.getElementById('strat-direction-select').value = 'BOTH';
  document.getElementById('strat-cooldown-select').value = '120';
  document.getElementById('strat-mtg1-toggle').checked = false;

  setPersonalAssetScope('ALL_REAL');

  document.getElementById('strat-trend-filter').checked = false;
  document.getElementById('strat-trend-mtf').value = '5M';
  document.getElementById('strat-trend-ema').value = '20';

  document.getElementById('strat-body-ratio').value = '0.20';
  document.getElementById('strat-max-wick').value = '0.40';
  document.getElementById('strat-doji-filter').checked = true;
  if (document.getElementById('strat-sr-clearance-input')) document.getElementById('strat-sr-clearance-input').value = '0.05';
  if (document.getElementById('strat-pinbar-ratio-input')) document.getElementById('strat-pinbar-ratio-input').value = '2.0';

  document.getElementById('strat-engulfing-filter').checked = false;
  document.getElementById('strat-sr-breakout-filter').checked = false;

  const allIndicatorKeys = [
    { key: 'bollinger', cb: 'strat-bollinger-filter', defaultActive: true },
    { key: 'supertrend', cb: 'strat-supertrend-filter' },
    { key: 'sar', cb: 'strat-sar-filter' },
    { key: 'ma', cb: 'strat-ma-filter' },
    { key: 'keltner', cb: 'strat-keltner-filter' },
    { key: 'donchian', cb: 'strat-donchian-filter' },
    { key: 'envelopes', cb: 'strat-envelopes-filter' },
    { key: 'alligator', cb: 'strat-alligator-filter' },
    { key: 'ichimoku', cb: 'strat-ichimoku-filter' },
    { key: 'fractal', cb: 'strat-fractal-filter' },
    { key: 'zigzag', cb: 'strat-zigzag-filter' },
    { key: 'rsi', cb: 'strat-rsi-filter' },
    { key: 'stoch', cb: 'strat-stochastic-filter' },
    { key: 'macd', cb: 'strat-macd-filter' },
    { key: 'ao', cb: 'strat-ao-filter' },
    { key: 'williams', cb: 'strat-williams-filter' },
    { key: 'cci', cb: 'strat-cci-filter' },
    { key: 'demarker', cb: 'strat-demarker-filter' },
    { key: 'elder', cb: 'strat-elder-filter' },
    { key: 'adx', cb: 'strat-adx-filter' },
    { key: 'aroon', cb: 'strat-aroon-filter' },
    { key: 'atr', cb: 'strat-atr-filter' },
    { key: 'momentum', cb: 'strat-momentum-filter' },
    { key: 'roc', cb: 'strat-roc-filter' },
    { key: 'vortex', cb: 'strat-vortex-filter' },
    { key: 'stc', cb: 'strat-stc-filter' },
    { key: 'volosc', cb: 'strat-volosc-filter' }
  ];

  allIndicatorKeys.forEach(item => {
    const cb = document.getElementById(item.cb);
    if (cb) cb.checked = !!item.defaultActive;
    toggleIndicatorDrawer(item.key, !!item.defaultActive);
  });


  if (document.getElementById('strat-confluence-toggle')) {
    document.getElementById('strat-confluence-toggle').checked = false;
  }

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
  const exp = parseInt(document.getElementById('strat-exp-input')?.value || '1', 10);
  const minP = parseInt(document.getElementById('strat-payout-input')?.value || '80', 10);
  const dir = document.getElementById('strat-direction-select')?.value || 'BOTH';
  const cd = parseInt(document.getElementById('strat-cooldown-select')?.value || '120', 10);
  const mtg1 = document.getElementById('strat-mtg1-toggle')?.checked || false;

  let assetList = ["ALL_REAL"];
  if (personalCurrentScope === 'MAJORS') {
    assetList = MAJOR_REAL_FOREX_PAIRS;
  } else if (personalCurrentScope === 'CUSTOM') {
    assetList = Array.from(personalSelectedCustomAssets);
    if (assetList.length === 0) assetList = ["ALL_REAL"];
  }

  const trendEnabled = document.getElementById('strat-trend-filter')?.checked || false;
  const trendMtf = document.getElementById('strat-trend-mtf')?.value || '5M';
  const trendEma = parseInt(document.getElementById('strat-trend-ema')?.value || '20', 10);

  const minBodyRatio = parseFloat(document.getElementById('strat-body-ratio')?.value || '0.20');
  const maxOpposingWick = parseFloat(document.getElementById('strat-max-wick')?.value || '0.40');
  const dojiFilter = document.getElementById('strat-doji-filter')?.checked !== false;

  const srClearance = parseFloat(document.getElementById('strat-sr-clearance-input')?.value || '0.05');
  const pinbarRatio = parseFloat(document.getElementById('strat-pinbar-ratio-input')?.value || '2.0');

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
    const period = parseInt(document.getElementById('ind-rsi-period')?.value || '14', 10);
    const ob = parseFloat(document.getElementById('ind-rsi-ob')?.value || '70');
    const os = parseFloat(document.getElementById('ind-rsi-os')?.value || '30');
    indicatorsList.push({
      indicator: 'RSI',
      period: period,
      condition: 'BETWEEN',
      min_val: os,
      max_val: ob,
      params: { period, overbought: ob, oversold: os }
    });
  }
  if (bollingerEnabled) {
    const p1 = parseInt(document.getElementById('ind-bb-p1')?.value || '10', 10);
    const p2 = parseInt(document.getElementById('ind-bb-p2')?.value || '13', 10);
    const dev = parseFloat(document.getElementById('ind-bb-dev')?.value || '2.0');
    const protrusion = parseFloat(document.getElementById('ind-bb-protrusion')?.value || '20');
    indicatorsList.push({
      indicator: 'BOLLINGER',
      period: p1,
      condition: 'BETWEEN',
      min_val: 0,
      max_val: 1,
      params: { period_1: p1, period_2: p2, deviation: dev, min_body_protrusion: protrusion }
    });
  }
  if (stochEnabled) {
    const k = parseInt(document.getElementById('ind-stoch-k')?.value || '14', 10);
    const d = parseInt(document.getElementById('ind-stoch-d')?.value || '3', 10);
    const ob = parseFloat(document.getElementById('ind-stoch-ob')?.value || '80');
    const os = parseFloat(document.getElementById('ind-stoch-os')?.value || '20');
    indicatorsList.push({
      indicator: 'STOCHASTIC',
      period: k,
      condition: 'BETWEEN',
      min_val: os,
      max_val: ob,
      params: { k_period: k, d_period: d, overbought: ob, oversold: os }
    });
  }
  if (macdEnabled) {
    const fast = parseInt(document.getElementById('ind-macd-fast')?.value || '12', 10);
    const slow = parseInt(document.getElementById('ind-macd-slow')?.value || '26', 10);
    const sig = parseInt(document.getElementById('ind-macd-signal')?.value || '9', 10);
    indicatorsList.push({
      indicator: 'MACD',
      period: fast,
      condition: 'BETWEEN',
      min_val: -999999,
      max_val: 999999,
      params: { fast_period: fast, slow_period: slow, signal_period: sig }
    });
  }
  if (supertrendEnabled) {
    const atr = parseInt(document.getElementById('ind-st-period')?.value || '10', 10);
    const mult = parseFloat(document.getElementById('ind-st-mult')?.value || '3.0');
    indicatorsList.push({
      indicator: 'SUPERTREND',
      period: atr,
      condition: 'BULLISH',
      params: { atr_period: atr, multiplier: mult }
    });
  }
  if (sarEnabled) {
    const step = parseFloat(document.getElementById('ind-sar-step')?.value || '0.02');
    const maxA = parseFloat(document.getElementById('ind-sar-max')?.value || '0.2');
    indicatorsList.push({
      indicator: 'PARABOLIC_SAR',
      period: 14,
      condition: 'BULLISH',
      params: { step: step, max_step: maxA }
    });
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

  const confluenceEnabled = document.getElementById('strat-confluence-toggle')?.checked || false;
  const confluenceMin = parseInt(document.getElementById('strat-confluence-min')?.value || '2', 10);
  const confluenceScore = parseFloat(document.getElementById('strat-confluence-score')?.value || '75');

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
    assets: assetList,
    filters: {
      trend: { enabled: trendEnabled, mtf_timeframe: trendMtf, ema_period: trendEma, require_alignment: trendEnabled },
      candle_anatomy: { min_body_ratio: minBodyRatio, max_opposing_wick: maxOpposingWick, filter_preceding_doji: dojiFilter, filter_spike_multiplier: 2.8, min_rejection_wick_ratio: pinbarRatio },
      indicators: indicatorsList,
      price_action: { require_engulfing: engulfingEnabled, require_sr_breakout: srBreakoutEnabled, min_sr_clearance_pct: srClearance },
      confluence: { enabled: confluenceEnabled, min_agreeing_factors: confluenceMin, min_quality_score: confluenceScore },
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
  selectCardStyle(PersonalState.cardStyle || 'vip');
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
  const opt = PersonalState.cardOptions || {
    strategy: true,
    payout: true,
    timing: true,
    guidelines: true
  };

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

  const defaultCb = (typeof DEFAULT_TEMPLATES !== 'undefined' && DEFAULT_TEMPLATES.circuit_breaker)
    ? DEFAULT_TEMPLATES.circuit_breaker
    : "🛑 <b>TRADEPULSE CIRCUIT BREAKER ACTIVATED</b>\n━━━━━━━━━━━━━━━━━━━━\n⚠️ <b>Signal Scanner Auto-Paused</b>\n• <b>Trigger Reason:</b> <b>{cb_reason}</b>\n• <b>Session Net PnL:</b> <b>{net_pnl}</b>\n• <b>Total Trades:</b> <b>{total_trades}</b>\n━━━━━━━━━━━━━━━━━━━━\n🔒 <i>Scanner halted to safeguard capital. Manage in TradePulse Terminal.</i>";

  return {
    signal: sigTmpl.trim(),
    pre_signal: preTmpl.trim(),
    outcome: outTmpl.trim(),
    circuit_breaker: defaultCb
  };
}

function updateCardPreview() {
  try {
    const box = document.getElementById('template-preview-box');
    if (!box) return;

    const templates = buildTemplateStrings();
    const tab = PersonalState.cardPreviewTab || 'signal';
    let raw = templates[tab] || templates.signal || '';

    const now = new Date();
    const istHours = String(now.getHours()).padStart(2, '0');
    const istMins = String(now.getMinutes()).padStart(2, '0');
    const istTime = `${istHours}:${istMins}:00`;

    const mockReplacements = {
      '{strategy}': 'Dual Bollinger Protrusion',
      '{asset}': 'EUR/USD',
      '{payout}': '85',
      '{arrow}': '🟢',
      '{dir_badge}': 'CALL (BUY)',
      '{direction}': 'CALL',
      '{chart_timeframe}': '1M',
      '{timeframe}': '1M',
      '{expiry}': '1',
      '{entry_time}': istTime,
      '{remaining_seconds}': '20',
      '{stake_line}': '💵 <b>Stake:</b> $25.00 (Kelly Edge)\n',
      '{header}': '🎉 <b>TRADE WON — EUR/USD (CALL)</b>',
      '{outcome_badge}': 'WIN (PROFIT) ✅',
      '{entry_price}': '1.08450',
      '{exit_price}': '1.08472',
      '{pnl_text}': '💰 <b>Net Return:</b> +$21.25',
      '{cb_reason}': 'Max Daily Loss Safeguard Hit',
      '{net_pnl}': '-$50.00',
      '{total_trades}': '12'
    };

    for (const [key, val] of Object.entries(mockReplacements)) {
      raw = raw.split(key).join(val);
    }

    box.innerHTML = raw.replace(/\n/g, '<br>');
  } catch (err) {
    console.error('[CARD PREVIEW ERROR]', err);
  }
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
    if (sym === PersonalState.activeChartPair) {
      const hudPrice = document.getElementById('chart-hud-price');
      if (hudPrice) {
        hudPrice.textContent = formatLivePrice(sym, data.price);
      }
      if (chartEngine) {
        chartEngine.updateLiveTick(data.price);
        if (chartEngine.candles && chartEngine.candles.length > 0) {
          updateChartHudStats(chartEngine.candles, sym);
        }
      }
    }

    if (sym === activeStrategyPreviewPair) {
      if (strategyChartEngine) {
        strategyChartEngine.updateLiveTick(data.price);
        const currentStrat = compileCurrentStrategyForm();
        if (currentStrat) {
          updateActiveRuleRadar(currentStrat);
        }
      }
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
  const lic = PersonalState.license || {};
  const isLicensed = lic.licensed === true;
  const statusPill = document.getElementById('license-status-pill');
  const statusText = document.getElementById('license-status-text');

  if (statusText) {
    if (isLicensed) {
      const daysLeft = lic.days_remaining !== undefined ? `${lic.days_remaining}d` : 'Active';
      statusText.textContent = `License: Active (${daysLeft})`;
      if (statusPill) {
        statusPill.classList.remove('offline', 'disconnected', 'error');
        statusPill.classList.add('online');
      }
    } else {
      statusText.textContent = 'License: Unlicensed';
      if (statusPill) {
        statusPill.classList.remove('online');
        statusPill.classList.add('disconnected');
      }
    }
  }

  const statVal = document.getElementById('lic-status-val');
  if (statVal) {
    statVal.textContent = isLicensed ? 'Active & Bound' : (lic.revoked ? 'Revoked' : 'Unlicensed');
    statVal.style.color = isLicensed ? 'var(--emerald)' : 'var(--rose)';
  }

  const clientName = document.getElementById('lic-client-name');
  if (clientName) {
    clientName.textContent = lic.client_name || (isLicensed ? 'Verified Subscriber' : '--');
  }

  const expiryVal = document.getElementById('lic-expiry-val');
  if (expiryVal) {
    if (lic.expires_at) {
      try {
        expiryVal.textContent = new Date(lic.expires_at).toLocaleString();
      } catch (e) {
        expiryVal.textContent = lic.expires_at;
      }
    } else {
      expiryVal.textContent = isLicensed ? '1 Year Active' : '--';
    }
  }

  const hwidEl = document.getElementById('lic-modal-hwid');
  if (hwidEl && lic.hwid) {
    hwidEl.textContent = lic.hwid;
  }
}
window.updateLicenseStatusUI = updateLicenseStatusUI;

function openLicenseModal() {
  const modal = document.getElementById('lic-modal');
  if (!modal) return;
  modal.classList.add('active');
  if (window.pywebview && window.pywebview.api && window.pywebview.api.get_license_status) {
    window.pywebview.api.get_license_status().then(lic => {
      if (lic) {
        PersonalState.license = lic;
        updateLicenseStatusUI();
      }
    }).catch(e => console.error('Failed to fetch license status', e));
  } else {
    updateLicenseStatusUI();
  }
}
window.openLicenseModal = openLicenseModal;

function closeLicenseModal() {
  const modal = document.getElementById('lic-modal');
  if (modal) modal.classList.remove('active');
}
window.closeLicenseModal = closeLicenseModal;

window.onLicenseRevoked = function(reason) {
  showToast(`License Revoked: ${reason}`, 'error');
  if (PersonalState.license) {
    PersonalState.license.licensed = false;
    PersonalState.license.revoked = true;
  }
  updateLicenseStatusUI();
  updateMasterScannerUI();
};

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

// ============================================================================
// Strategy Optimizer & Monte Carlo Stress-Test Controller
// ============================================================================
function openOptimizerModal() {
  const modal = document.getElementById('optimizer-modal');
  if (modal) modal.classList.add('active');
}
window.openOptimizerModal = openOptimizerModal;

function closeOptimizerModal() {
  const modal = document.getElementById('optimizer-modal');
  if (modal) modal.classList.remove('active');
}
window.closeOptimizerModal = closeOptimizerModal;

function executeOptimizerSweep() {
  const sym = document.getElementById('opt-symbol-select')?.value || 'EUR/USD';
  const payout = parseFloat(document.getElementById('opt-payout-input')?.value || '85');
  const btn = document.getElementById('btn-run-optimizer');

  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏳ Sweeping 48 Setups...';
  }

  showToast(`Running 48-combination parameter sweep for ${sym}...`, 'info');

  if (window.pywebview && window.pywebview.api && window.pywebview.api.run_strategy_optimizer) {
    window.pywebview.api.run_strategy_optimizer(sym, payout).then(res => {
      if (btn) {
        btn.disabled = false;
        btn.textContent = '⚡ Run Grid Sweep';
      }
      if (!res || res.error) {
        showToast(res ? res.error : 'Optimizer execution returned no data', 'error');
        return;
      }
      renderOptimizerResults(res, payout);
      showToast(`Grid sweep complete: Evaluated ${res.total_combinations_tested || 48} parameter setups!`, 'success');
    }).catch(err => {
      if (btn) {
        btn.disabled = false;
        btn.textContent = '⚡ Run Grid Sweep';
      }
      showToast('Optimizer execution failed: ' + (err || 'Unknown error'), 'error');
    });
  } else {
    if (btn) {
      btn.disabled = false;
      btn.textContent = '⚡ Run Grid Sweep';
    }
    showToast('Strategy Optimizer API not available', 'error');
  }
}
window.executeOptimizerSweep = executeOptimizerSweep;

function renderOptimizerResults(res, payout) {
  const emptyState = document.getElementById('opt-empty-state');
  const resultsContainer = document.getElementById('opt-results-container');
  const mcContainer = document.getElementById('opt-monte-carlo-container');
  const tbody = document.getElementById('opt-results-tbody');

  if (emptyState) emptyState.style.display = 'none';
  if (resultsContainer) resultsContainer.style.display = 'block';

  const rows = res.ranked_results || [];
  if (tbody) {
    if (rows.length === 0) {
      tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; padding: 20px; color: var(--text-dim);">No positive expectancy configurations found for current market data.</td></tr>';
    } else {
      tbody.innerHTML = rows.map((r, idx) => {
        const evColor = (r.ev_per_trade || 0) >= 0 ? 'var(--cyan-bright)' : 'var(--rose)';
        const evSign = (r.ev_per_trade || 0) >= 0 ? '+' : '';
        const params = r.parameters || {};
        return `
          <tr>
            <td style="font-weight: 800; color: #fff;">#${idx + 1}</td>
            <td style="font-family: var(--font-mono);">${params.rsi_period || '-'}</td>
            <td style="font-family: var(--font-mono);">${params.rsi_ob || 70} / ${params.rsi_os || 30}</td>
            <td style="font-family: var(--font-mono);">${params.bb_dev || '2.0'}σ</td>
            <td style="font-weight: 700; color: var(--emerald);">${r.win_rate || 0}%</td>
            <td style="font-family: var(--font-mono);">${r.total_signals || 0}</td>
            <td style="font-weight: 700; color: ${evColor}; font-family: var(--font-mono);">${evSign}$${r.ev_per_trade || 0}</td>
            <td style="font-family: var(--font-mono);">${r.profit_factor || 0}</td>
            <td style="font-family: var(--font-mono); color: var(--cyan-bright);">${r.recommended_stake_pct || 0}%</td>
          </tr>
        `;
      }).join('');
    }
  }

  // Run Monte Carlo permutation stress test on top configuration
  const topResult = rows[0];
  if (topResult && topResult.wins !== undefined && topResult.losses !== undefined) {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.run_monte_carlo_test) {
      window.pywebview.api.run_monte_carlo_test(topResult.wins, topResult.losses, payout, 500, 10.0).then(mc => {
        if (!mc) return;
        if (mcContainer) mcContainer.style.display = 'block';
        const streakEl = document.getElementById('mc-stat-streak');
        const ddEl = document.getElementById('mc-stat-dd');
        const ruinEl = document.getElementById('mc-stat-ruin');
        const medianEl = document.getElementById('mc-stat-median');

        if (streakEl) streakEl.textContent = mc.percentile_95_max_consecutive_losses || 0;
        if (ddEl) ddEl.textContent = `$${mc.percentile_95_drawdown || 0.00}`;
        if (ruinEl) {
          const ruinVal = mc.probability_of_ruin_pct || 0.0;
          ruinEl.textContent = `${ruinVal}%`;
          ruinEl.style.color = ruinVal > 5 ? 'var(--rose)' : 'var(--emerald)';
        }
        if (medianEl) {
          const med = mc.median_expected_profit || 0.0;
          medianEl.textContent = `${med >= 0 ? '+' : ''}$${med}`;
        }
      }).catch(err => console.error('MC error', err));
    }
  }
}

// ============================================================================
// Institutional Forex Market Hours & Weekend Closure Handler
// ============================================================================
async function updateMarketSessionUI() {
  if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.get_market_session_status) {
    return;
  }
  try {
    const status = await window.pywebview.api.get_market_session_status();
    if (!status) return;

    PersonalState.isMarketOpen = status.is_open;

    // 1. Update Strategy Lab Market Badge
    const stratBadge = document.getElementById('strat-market-status-badge');
    if (stratBadge) {
      if (status.is_open) {
        stratBadge.textContent = '🟢 LIVE MARKET';
        stratBadge.style.color = 'var(--emerald)';
        stratBadge.style.borderColor = 'rgba(0, 245, 155, 0.3)';
        stratBadge.style.background = 'rgba(0, 245, 155, 0.15)';
      } else {
        stratBadge.textContent = `🟡 WEEKEND STANDBY (${status.time_until_reopen ? 'in ' + status.time_until_reopen : 'Sun 21:00 UTC'})`;
        stratBadge.style.color = 'var(--amber)';
        stratBadge.style.borderColor = 'rgba(245, 158, 11, 0.4)';
        stratBadge.style.background = 'rgba(245, 158, 11, 0.15)';
      }
    }

    // 2. Update Live Chart Station Feed Badge
    const chartBadge = document.getElementById('chart-feed-badge');
    if (chartBadge) {
      if (status.is_open) {
        chartBadge.textContent = 'REAL-TIME FEED';
        chartBadge.style.color = 'var(--emerald)';
      } else {
        chartBadge.textContent = `WEEKEND STANDBY — FRIDAY SETTLEMENT (${status.time_until_reopen ? 'Reopens in ' + status.time_until_reopen : 'Sun 21:00 UTC'})`;
        chartBadge.style.color = 'var(--amber)';
      }
    }

    // 3. Update Global Top Bar Market Mode Pill
    const marketPill = document.querySelector('.top-status-pill');
    if (marketPill) {
      if (status.is_open) {
        marketPill.textContent = '● LIVE MARKETS';
        marketPill.style.color = 'var(--emerald)';
        marketPill.style.background = 'rgba(0, 245, 155, 0.12)';
      } else {
        marketPill.textContent = '● WEEKEND STANDBY';
        marketPill.style.color = 'var(--amber)';
        marketPill.style.background = 'rgba(245, 158, 11, 0.15)';
        marketPill.title = status.status_desc;
      }
    }
  } catch (err) {
    console.debug('Error updating market session UI:', err);
  }
}
window.updateMarketSessionUI = updateMarketSessionUI;

// Start periodic polling for market session status every 15s
setInterval(updateMarketSessionUI, 15000);
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(updateMarketSessionUI, 1000);
});

